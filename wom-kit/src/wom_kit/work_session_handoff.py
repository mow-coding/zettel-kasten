"""Exact outgoing handoff, not acceptance or artifact responsibility transfer.

Internal held facade only. The service owns the archive lock/runtime guard.
The current actor supplies its private claim; callers never provide native/key
implementations, claims, approval contexts or replacement resume reviewers.
Original resume selects only the saved handoff, never an establishment or a
new approval. Acceptance and subsequent ownership remain separate operations.
"""

from . import exact_human_approval as approval
from . import exact_human_approval_workflow as workflow
from . import work_session_actor as actor
from . import work_session_actor_execution as actor_guard
from . import work_session_bundle as bundle
from . import work_session_claim as claim
from . import work_session_establishment as establishment
from . import work_session_execution as execution
from . import work_session_lifecycle as lifecycle
from . import work_session_registry as registry
from . import work_session_rereview as rereview
from . import work_session_state as state


_ERRORS = frozenset({
    "work_session_handoff_invalid", "work_session_handoff_unavailable",
    "work_session_handoff_current_unavailable", "work_session_task_context_required",
    "work_session_task_context_mismatch", "work_session_task_context_changed",
    "work_session_original_operation_pending", "work_session_original_operation_missing",
    "work_session_original_operation_changed", "work_session_task_ownership_unavailable",
    "work_session_lock_required",
    "work_session_original_operation_kind_unsupported",
}) | workflow.ExactHumanApprovalWorkflowError._CODES


class WorkSessionHandoffError(ValueError):
    def __init__(self, code="work_session_handoff_invalid", *, original_commit_verified=False):
        self.code = code if type(code) is str and code in _ERRORS else "work_session_handoff_invalid"
        self.original_commit_verified = original_commit_verified is True
        super().__init__(self.code)


def _safe_call(call):
    code, committed = "work_session_handoff_unavailable", False
    try:
        return call()
    except WorkSessionHandoffError as error:
        code, committed = error.code, error.original_commit_verified
    except (lifecycle.WorkSessionLifecycleError, actor_guard.WorkSessionTaskSelectionError,
            workflow.ExactHumanApprovalWorkflowError, rereview.WorkSessionRereviewError) as error:
        if type(error.code) is str and error.code in _ERRORS:
            code = error.code
    except actor.WorkSessionActorError as error:
        if error.code == "work_session_actor_changed":
            code = "work_session_task_context_changed"
    except Exception:
        pass
    raise WorkSessionHandoffError(code, original_commit_verified=committed)


def _assert_selected(routing, selected):
    # After the actual handoff commit the pending actor still records the old
    # claim. Historical routing must be readable without claiming it is live.
    current = routing._read(current=False)
    if current is None or current.sha256 != selected.sha256:
        raise WorkSessionHandoffError("work_session_task_context_changed")


def _bound_handoff(store, pointer, *, app, route, session, target):
    if type(pointer) is not dict or pointer.get("kind") != "human_session_decision":
        raise WorkSessionHandoffError("work_session_original_operation_changed")
    bound = bundle.load_context_bound_session_decision(store, manifest_sha256=pointer["manifest_sha256"])
    prepared, binding = bound.prepared, bound.prepared.manifest.work_session_binding
    request = prepared.transition._request
    if (prepared.transition.action != "handoff" or binding.client_app_ref != app
            or binding.work_session_ref != session or prepared.task_route_ref != route
            or prepared.manifest.archive_identity_sha256 != store.archive_identity_sha256
            or request["client_app_ref"] != app or request["work_session_ref"] != session
            or request["target_app_ref"] != target
            or approval.exact_human_approval_context_sha256(bound.context) != pointer["context_sha256"]):
        raise WorkSessionHandoffError("work_session_original_operation_changed")
    return bound


def _verify_origin(root, store, routing, selected, *, held, app, route, session):
    origin = state._source_selector(store, selected, held=held, app=app, session=session)
    claim._verify_original_establishment(root, store, routing, selected, held=held,
        client_app_ref=app, task_route_ref=route, work_session_ref=session,
        key_provider=None, original_establishment_selector=origin)
    return origin


def _pending_predecessor(store, selected, bound, *, held, session):
    names = store._observe_names()
    previous = bundle._generation(store, bound.prepared.transition.after.revision - 1, names)
    document = selected.document()
    if (previous.sha256 != bound.prepared.transition.before_sha256
            or previous.binding(session).document() != document["observed_binding"]
            or previous._document["sessions"][session]["claim_ref"] != document["claim_ref"]
            or document["claim_ref"] != bound.prepared.transition._request["claim_ref"]
            or names != store._observe_names()):
        raise WorkSessionHandoffError("work_session_original_operation_changed")
    store._require_held_lock(held)


def _current_handoff(store, *, held, expected, target):
    with store._read_boundary():
        bundle._check_store(store)
        first = store.read()
        row = first._document["sessions"].get(expected.work_session_ref)
        if (row is None or first.binding(expected.work_session_ref) != expected
                or row["state"] != "handoff_pending" or row["claim_ref"] is not None
                or row["handoff_app_ref"] != target
                or first._document["workstreams"][row["workstream_ref"]]["active_session_ref"] != expected.work_session_ref
                or store.read().sha256 != first.sha256):
            raise WorkSessionHandoffError("work_session_handoff_current_unavailable")
        bundle._check_store(store)
        store._require_held_lock(held)
    return expected


def _finish(store, routing, selected, bound, result, *, held, app, route, session, target, publish):
    expected = bound.prepared.manifest.work_session_binding
    if (type(result) is not dict or result.get("ok") is not True
            or result.get("independent_post_verification") is not True
            or result.get("work_session_binding") != expected.document()):
        raise WorkSessionHandoffError("work_session_original_operation_changed")
    pointer = {"kind": "human_session_decision", "manifest_sha256": bound.prepared.manifest.manifest_sha256,
               "context_sha256": approval.exact_human_approval_context_sha256(bound.context)}
    if _bound_handoff(store, pointer, app=app, route=route, session=session, target=target) != bound:
        raise WorkSessionHandoffError("work_session_original_operation_changed", original_commit_verified=True)
    try:
        _assert_selected(routing, selected)
        current = _current_handoff(store, held=held, expected=expected, target=target)
    except Exception:
        raise WorkSessionHandoffError("work_session_handoff_current_unavailable", original_commit_verified=True) from None
    if publish:
        try:
            selected = routing.save(expected_sha256=selected.sha256, held_lock=held,
                work_session_ref=session, observed_binding=current, claim_ref=None,
                pending_manifest_sha256=None, pending_context_sha256=None,
                pending_registry_intent_plan_sha256=None,
                last_completed_operation=actor.CompletedOperationSelector.from_document(pointer))
        except Exception:
            raise WorkSessionHandoffError("work_session_task_context_changed", original_commit_verified=True) from None
    elif (selected.document()["observed_binding"] != current.document()
          or selected.document()["claim_ref"] is not None):
        raise WorkSessionHandoffError("work_session_task_context_changed", original_commit_verified=True)
    try:
        _assert_selected(routing, selected)
        store._require_held_lock(held)
    except Exception:
        raise WorkSessionHandoffError("work_session_task_context_changed", original_commit_verified=True) from None
    return {**result, "schema": "wom-kit/work-session-task-handoff-result/v1",
            "state": "handoff_pending", "target_app_ref": target,
            "original_commit_verified": True, "current_state_verified": True,
            "current_claim_ownership_verified": False, "current_claim_authority_evaluated": True,
            "ownership_transferred": False, "artifact_responsibility_transferred": False,
            "claim_tokens_echoed": False, "routing_is_write_authority": False,
            "task_continuation": selected.public_summary(), "original_operation_already_completed": not publish}


def _handoff_task_held(root, *, held, client_app_ref, task_route_ref, work_session_ref,
                       target_app_ref, original_resume, reviewer_claim=None):
    """Start one exact handoff, or resume only the explicitly selected original.

    A fresh handoff needs a new human decision. Original resume never accepts
    a replacement reviewer, resolves a latest operation, or automatically
    re-approves a pre-claim interruption. Public discovery is a separate layer.
    """
    def run():
        if type(original_resume) is not bool or (original_resume and reviewer_claim is not None):
            raise WorkSessionHandoffError()
        if not original_resume and (type(reviewer_claim) is not str or not reviewer_claim):
            raise WorkSessionHandoffError()
        for value, prefix in ((work_session_ref, "work_session"), (target_app_ref, "client_app")):
            if value is None:
                raise WorkSessionHandoffError("work_session_task_context_required")
            if not registry._ref(value, prefix):
                raise WorkSessionHandoffError("work_session_task_context_mismatch")
        store, routing = lifecycle._routing(root, held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref)
        selected = routing._read(current=False)
        if selected is None:
            raise WorkSessionHandoffError("work_session_task_context_required")
        document = selected.document()
        if document["work_session_ref"] != work_session_ref:
            raise WorkSessionHandoffError("work_session_task_context_mismatch")
        if document.get("pending_registry_intent_plan_sha256") is not None:
            raise WorkSessionHandoffError("work_session_original_operation_pending")
        pending_selector = selected.pending_operation()
        pending = pending_selector is not None
        if pending and pending_selector.document()["kind"] == "git_backup":
            raise WorkSessionHandoffError("work_session_original_operation_kind_unsupported")
        scope = dict(app=client_app_ref, route=task_route_ref, session=work_session_ref, target=target_app_ref)
        if original_resume:
            pointer = (pending_selector.document() if pending
                       else document.get("last_completed_operation"))
            if pointer is None:
                raise WorkSessionHandoffError("work_session_original_operation_missing")
            if pointer["kind"] == "git_backup":
                raise WorkSessionHandoffError("work_session_original_operation_kind_unsupported")
            bound = _bound_handoff(store, pointer, **scope)
            _verify_origin(root, store, routing, selected, held=held, app=client_app_ref,
                           route=task_route_ref, session=work_session_ref)
            if pending:
                _pending_predecessor(store, selected, bound, held=held, session=work_session_ref)
            _assert_selected(routing, selected)
            result = execution._resume_session_decision_held(root, held=held,
                manifest_sha256=pointer["manifest_sha256"], completed_only=not pending)
            return _finish(store, routing, selected, bound, result, held=held, publish=pending, **scope)
        if pending:
            raise WorkSessionHandoffError("work_session_original_operation_pending")
        expected = actor_guard._require_actor_selection_for_write_held(root, held=held,
            client_app_ref=client_app_ref, task_route_ref=task_route_ref, work_session_ref=work_session_ref)
        if expected.document() != document["observed_binding"]:
            raise WorkSessionHandoffError("work_session_task_context_changed")
        origin = _verify_origin(root, store, routing, selected, held=held, app=client_app_ref,
                                route=task_route_ref, session=work_session_ref)
        origin_bound = establishment.load_original_establishment(store, selector=origin,
            client_app_ref=client_app_ref, task_route_ref=task_route_ref, work_session_ref=work_session_ref)
        published = {}

        def before_claim(prepared, context):
            # This callback runs inside the existing claim publication boundary.
            # Only read identity/ownership here: never nest a key consumer.
            _assert_selected(routing, selected)
            current = actor_guard._require_actor_selection_for_write_held(root, held=held,
                client_app_ref=client_app_ref, task_route_ref=task_route_ref, work_session_ref=work_session_ref)
            if (current != expected or prepared.transition.action != "handoff"
                    or prepared.transition._request["claim_ref"] != document["claim_ref"]
                    or prepared.transition._request["target_app_ref"] != target_app_ref
                    or prepared.task_route_ref != task_route_ref
                    or prepared.manifest.work_session_binding.client_app_ref != client_app_ref
                    or prepared.manifest.work_session_binding.work_session_ref != work_session_ref
                    or establishment.load_original_establishment(store, selector=origin,
                        client_app_ref=client_app_ref, task_route_ref=task_route_ref,
                        work_session_ref=work_session_ref) != origin_bound):
                raise WorkSessionHandoffError("work_session_original_operation_changed")
            published["actor"] = routing.save(expected_sha256=selected.sha256, held_lock=held,
                work_session_ref=work_session_ref, observed_binding=expected, claim_ref=document["claim_ref"],
                pending_manifest_sha256=prepared.manifest.manifest_sha256,
                pending_context_sha256=approval.exact_human_approval_context_sha256(context),
                pending_registry_intent_plan_sha256=None, established_origin=origin)

        result = execution._execute_session_decision_held(root, held=held, action="handoff",
            client_app_ref=client_app_ref, task_route_ref=task_route_ref, work_session_ref=work_session_ref,
            claim_ref=document["claim_ref"], target_app_ref=target_app_ref, reviewer_claim=reviewer_claim,
            before_claim_publication=before_claim)
        selected = published.get("actor")
        if selected is None:
            raise WorkSessionHandoffError("work_session_original_operation_changed")
        pending_selector = selected.pending_operation()
        if pending_selector is None or pending_selector.document()["kind"] != "human_session_decision":
            raise WorkSessionHandoffError("work_session_original_operation_kind_unsupported")
        bound = _bound_handoff(store, pending_selector.document(), **scope)
        return _finish(store, routing, selected, bound, result, held=held, publish=True, **scope)
    return _safe_call(run)


def _review_original_handoff_held(root, *, held, client_app_ref, task_route_ref,
                                   work_session_ref, target_app_ref):
    """Explicit original re-review only when its pending claim is truly absent.

    Original origin authentication finishes before the shared scanner/broker
    consumes any key. Existing claims use only their original resume path.
    No replacement reviewer, target, private claim or authority is accepted.
    """
    def run():
        for value, prefix in ((work_session_ref, "work_session"), (target_app_ref, "client_app")):
            if value is None:
                raise WorkSessionHandoffError("work_session_task_context_required")
            if not registry._ref(value, prefix):
                raise WorkSessionHandoffError("work_session_task_context_mismatch")
        store, routing = lifecycle._routing(root, held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref)
        selected = routing._read(current=False)
        if selected is None:
            raise WorkSessionHandoffError("work_session_original_operation_missing")
        document = selected.document()
        if document["work_session_ref"] != work_session_ref:
            raise WorkSessionHandoffError("work_session_task_context_mismatch")
        if document.get("pending_registry_intent_plan_sha256") is not None:
            raise WorkSessionHandoffError("work_session_original_operation_pending")
        pending_selector = selected.pending_operation()
        pending = pending_selector is not None
        pointer = (pending_selector.document() if pending
                   else document.get("last_completed_operation"))
        if pointer is None:
            raise WorkSessionHandoffError("work_session_original_operation_missing")
        if pointer["kind"] == "git_backup":
            raise WorkSessionHandoffError("work_session_original_operation_kind_unsupported")
        scope = dict(app=client_app_ref, route=task_route_ref, session=work_session_ref, target=target_app_ref)
        bound = _bound_handoff(store, pointer, **scope)
        origin = _verify_origin(root, store, routing, selected, held=held,
                                app=client_app_ref, route=task_route_ref, session=work_session_ref)
        origin_bound = establishment.load_original_establishment(store, selector=origin,
            client_app_ref=client_app_ref, task_route_ref=task_route_ref, work_session_ref=work_session_ref)

        def assert_selected():
            _assert_selected(routing, selected)
            if _bound_handoff(store, pointer, **scope) != bound:
                raise WorkSessionHandoffError("work_session_original_operation_changed")
            if pending:
                _pending_predecessor(store, selected, bound, held=held, session=work_session_ref)
            # Pure bundle checks only: this closure also runs in the existing
            # publication key consumer and may not authenticate with another.
            if establishment.load_original_establishment(store, selector=origin,
                    client_app_ref=client_app_ref, task_route_ref=task_route_ref,
                    work_session_ref=work_session_ref) != origin_bound:
                raise WorkSessionHandoffError("work_session_original_operation_changed")
            store._require_held_lock(held)

        def finalize_original(result):
            return _finish(store, routing, selected, bound, result, held=held, publish=pending, **scope)

        def resume_original():
            assert_selected()
            result = execution._resume_session_decision_held(root, held=held,
                manifest_sha256=bound.prepared.manifest.manifest_sha256, completed_only=not pending)
            return finalize_original(result)

        return rereview._review_bound_original_held(store, routing, selected, bound, held=held, pending=pending,
            assert_selected=assert_selected, resume_original=resume_original, finalize_original=finalize_original)
    return _safe_call(run)
