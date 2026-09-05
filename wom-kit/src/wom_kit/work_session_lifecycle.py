"""Task-scoped human starts and original continuation, using the existing runner.

Internal composition for the public lifecycle facade. Registration/claim and
CLI/MCP routing are separate. Callers retain explicit opaque app/task selectors;
humans do not locate manifests, claims, checkpoints or private actor files.
"""

import hmac
from pathlib import Path

from . import exact_human_approval as approval
from . import exact_human_approval_workflow as workflow
from . import work_session_actor as actor
from . import work_session_bundle as bundle
from . import work_session_execution as execution
from . import work_session_establishment as establishment
from . import work_session_registry as registry
from .work_session_wait import wait_for_archive_writer


_ERRORS = frozenset({
    "work_session_task_context_required", "work_session_task_context_mismatch",
    "work_session_task_context_changed", "work_session_task_already_selected",
    "work_session_original_operation_pending", "work_session_original_operation_missing",
    "work_session_original_operation_changed", "work_session_lifecycle_unavailable",
    "work_session_lock_required",
}) | workflow.ExactHumanApprovalWorkflowError._CODES


class WorkSessionLifecycleError(ValueError):
    def __init__(self, code="work_session_lifecycle_unavailable"):
        self.code = code if type(code) is str and code in _ERRORS else "work_session_lifecycle_unavailable"
        super().__init__(self.code)


def _safe_call(call):
    code = "work_session_lifecycle_unavailable"
    try:
        return call()
    except WorkSessionLifecycleError as error:
        code = error.code
    except workflow.ExactHumanApprovalWorkflowError as error:
        if type(error.code) is str and error.code in workflow.ExactHumanApprovalWorkflowError._CODES:
            code = error.code
    except registry.WorkSessionRegistryError as error:
        if error.args == ("work_session_lock_required",):
            code = "work_session_lock_required"
    except actor.WorkSessionActorError as error:
        if error.code == "work_session_actor_changed":
            code = "work_session_task_context_changed"
    except Exception:
        pass
    # The public-facing exception must not retain private labels or nested paths.
    raise WorkSessionLifecycleError(code)


def _routing(root, *, held, client_app_ref, task_route_ref):
    for value, prefix in ((client_app_ref, "client_app"), (task_route_ref, "task_route")):
        if value is None:
            raise WorkSessionLifecycleError("work_session_task_context_required")
        if not registry._ref(value, prefix):
            raise WorkSessionLifecycleError("work_session_task_context_mismatch")
    store, _archive_id = execution._store(root)
    store._require_held_lock(held)
    routing = actor.WorkSessionActorStore(store, client_app_ref=client_app_ref, task_route_ref=task_route_ref)
    return store, routing


def _assert_actor(routing, expected):
    current = routing.read()
    if (current.sha256 if current else None) != (expected.sha256 if expected else None):
        raise WorkSessionLifecycleError("work_session_task_context_changed")
    return current


def _has_pending(document):
    return (document.get("pending_manifest_sha256") is not None
            or document.get("pending_registry_intent_plan_sha256") is not None)


def _bound_establishment(store, *, action, client_app_ref, task_route_ref, manifest_sha256, context_sha256):
    if type(action) is not str or action not in {"create", "accept"}:
        raise WorkSessionLifecycleError("work_session_original_operation_changed")
    bound = bundle.load_context_bound_session_decision(store, manifest_sha256=manifest_sha256)
    prepared = bound.prepared
    binding = prepared.manifest.work_session_binding
    if (prepared.transition.action != action or binding.client_app_ref != client_app_ref
            or prepared.manifest.archive_identity_sha256 != store.archive_identity_sha256
            or prepared.task_route_ref != task_route_ref
            or not hmac.compare_digest(approval.exact_human_approval_context_sha256(bound.context), context_sha256)):
        raise WorkSessionLifecycleError("work_session_original_operation_changed")
    return bound


def _bound_create(store, *, client_app_ref, task_route_ref, manifest_sha256, context_sha256):
    """Historical create-only reader; an accept bundle is not an old create."""
    return _bound_establishment(store, action="create", client_app_ref=client_app_ref,
        task_route_ref=task_route_ref, manifest_sha256=manifest_sha256, context_sha256=context_sha256)


def _origin(bound):
    return establishment.EstablishmentSelector.from_document({
        "action": bound.prepared.transition.action,
        "manifest_sha256": bound.prepared.manifest.manifest_sha256,
        "context_sha256": approval.exact_human_approval_context_sha256(bound.context),
    })


def _finish_establishment(store, routing, selected, *, held, bound, result):
    """Publish a continuation pointer only after the original runner verified it."""
    expected_binding = bound.prepared.manifest.work_session_binding
    if (type(result) is not dict or result.get("ok") is not True
            or result.get("independent_post_verification") is not True
            or result.get("work_session_binding") != expected_binding.document()):
        raise WorkSessionLifecycleError("work_session_original_operation_changed")
    _assert_actor(routing, selected)
    store._require_held_lock(held)
    # Create and accept establish a session, not current claim ownership.
    current = store.read()
    session = current._document["sessions"].get(expected_binding.work_session_ref)
    if (session is None or current.binding(expected_binding.work_session_ref) != expected_binding
            or session["state"] != "created" or session["claim_ref"] is not None):
        raise WorkSessionLifecycleError("work_session_original_operation_changed")
    completed = actor.CompletedOperationSelector.from_document({
        "kind": "human_session_decision",
        "manifest_sha256": bound.prepared.manifest.manifest_sha256,
        "context_sha256": approval.exact_human_approval_context_sha256(bound.context),
    })
    updated = routing.save(
        expected_sha256=selected.sha256, held_lock=held,
        work_session_ref=expected_binding.work_session_ref, observed_binding=expected_binding,
        claim_ref=None, pending_manifest_sha256=None, pending_context_sha256=None,
        pending_registry_intent_plan_sha256=None, last_completed_operation=completed,
        established_origin=_origin(bound),
    )
    return {**result, "task_continuation": updated.public_summary(), "claim_required": True}


def _finish_create(store, routing, selected, *, held, bound, result):
    if bound.prepared.transition.action != "create":
        raise WorkSessionLifecycleError("work_session_original_operation_changed")
    return _finish_establishment(store, routing, selected, held=held, bound=bound, result=result)


def _establish_task_held(root, *, held, action, client_app_ref, task_route_ref, reviewer_claim,
                         label=None, predecessor_work_session_ref=None, native=None, key_provider=None):
    def run():
        if type(action) is not str or action not in {"create", "accept"}:
            raise WorkSessionLifecycleError("work_session_original_operation_changed")
        if ((action == "create" and predecessor_work_session_ref is not None)
                or (action == "accept" and (label is not None
                    or not registry._ref(predecessor_work_session_ref, "work_session")))):
            raise WorkSessionLifecycleError("work_session_task_context_mismatch")
        store, routing = _routing(root, held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref)
        original = routing.read()
        document = original.document() if original else {}
        if _has_pending(document):
            raise WorkSessionLifecycleError("work_session_original_operation_pending")
        if document.get("work_session_ref") is not None or document.get("last_completed_operation") is not None:
            raise WorkSessionLifecycleError("work_session_task_already_selected")
        published = {}

        def before_claim(prepared, context):
            if (prepared.transition.action != action
                    or prepared.manifest.work_session_binding.client_app_ref != client_app_ref
                    or prepared.task_route_ref != task_route_ref):
                raise WorkSessionLifecycleError("work_session_original_operation_changed")
            _assert_actor(routing, original)
            pending = routing.save(
                expected_sha256=original.sha256 if original else None, held_lock=held,
                pending_manifest_sha256=prepared.manifest.manifest_sha256,
                pending_context_sha256=approval.exact_human_approval_context_sha256(context),
                pending_registry_intent_plan_sha256=None,
            )
            published["actor"] = pending

        result = execution._execute_session_decision_held(
            root, held=held, action=action, client_app_ref=client_app_ref,
            task_route_ref=task_route_ref,
            work_session_ref=predecessor_work_session_ref,
            label=label, reviewer_claim=reviewer_claim, native=native, key_provider=key_provider,
            before_claim_publication=before_claim,
        )
        pending = published.get("actor")
        if pending is None:
            raise WorkSessionLifecycleError("work_session_original_operation_changed")
        values = pending.document()
        bound = _bound_establishment(store, action=action, client_app_ref=client_app_ref, task_route_ref=task_route_ref,
                              manifest_sha256=values["pending_manifest_sha256"],
                              context_sha256=values["pending_context_sha256"])
        return _finish_establishment(store, routing, pending, held=held, bound=bound, result=result)
    return _safe_call(run)


def _create_task_held(root, *, held, client_app_ref, task_route_ref, label, reviewer_claim,
                      native=None, key_provider=None):
    return _establish_task_held(root, held=held, action="create", client_app_ref=client_app_ref,
        task_route_ref=task_route_ref, label=label, reviewer_claim=reviewer_claim,
        native=native, key_provider=key_provider)


def _resume_task_establishment_held(root, *, held, action, client_app_ref, task_route_ref, key_provider=None):
    def run():
        store, routing = _routing(root, held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref)
        selected = routing.read()
        if selected is None:
            raise WorkSessionLifecycleError("work_session_original_operation_missing")
        document = selected.document()
        if document.get("pending_registry_intent_plan_sha256") is not None:
            # Never fall through another pending operation to an older success.
            raise WorkSessionLifecycleError("work_session_original_operation_pending")
        pending = document["pending_manifest_sha256"] is not None
        pointer = ({"kind": "human_session_decision", "manifest_sha256": document["pending_manifest_sha256"],
                    "context_sha256": document["pending_context_sha256"]} if pending
                   else document.get("last_completed_operation"))
        if pointer is None:
            raise WorkSessionLifecycleError("work_session_original_operation_missing")
        if pointer["kind"] != "human_session_decision":
            raise WorkSessionLifecycleError("work_session_original_operation_changed")
        bound = _bound_establishment(store, action=action, client_app_ref=client_app_ref, task_route_ref=task_route_ref,
                              manifest_sha256=pointer["manifest_sha256"], context_sha256=pointer["context_sha256"])
        if document["work_session_ref"] not in {None, bound.prepared.manifest.work_session_binding.work_session_ref}:
            raise WorkSessionLifecycleError("work_session_task_context_mismatch")
        if (document.get("established_origin") is not None
                and document["established_origin"] != _origin(bound).document()):
            raise WorkSessionLifecycleError("work_session_original_operation_changed")
        _assert_actor(routing, selected)
        result = execution._resume_session_decision_held(
            root, held=held, manifest_sha256=pointer["manifest_sha256"],
            completed_only=not pending, key_provider=key_provider,
        )
        if pending:
            return _finish_establishment(store, routing, selected, held=held, bound=bound, result=result)
        _assert_actor(routing, selected)
        return {**result, "task_continuation": selected.public_summary(),
                "original_task_operation_already_completed": True}
    return _safe_call(run)


def _resume_task_create_held(root, *, held, client_app_ref, task_route_ref, key_provider=None):
    return _resume_task_establishment_held(root, held=held, action="create", client_app_ref=client_app_ref,
        task_route_ref=task_route_ref, key_provider=key_provider)


def _create_task_core(root, *, client_app_ref, task_route_ref, label, reviewer_claim,
                      cancel_requested=lambda: False, progress=lambda _event: None,
                      native=None, key_provider=None):
    def run():
        with wait_for_archive_writer(Path(root), cancel_requested=cancel_requested, progress=progress) as held:
            return _create_task_held(root, held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref,
                                     label=label, reviewer_claim=reviewer_claim, native=native, key_provider=key_provider)
    return _safe_call(run)


def _resume_task_create_core(root, *, client_app_ref, task_route_ref,
                             cancel_requested=lambda: False, progress=lambda _event: None, key_provider=None):
    def run():
        with wait_for_archive_writer(Path(root), cancel_requested=cancel_requested, progress=progress) as held:
            return _resume_task_create_held(root, held=held, client_app_ref=client_app_ref,
                                            task_route_ref=task_route_ref, key_provider=key_provider)
    return _safe_call(run)
