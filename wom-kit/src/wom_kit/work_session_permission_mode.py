"""Held facade for the `set-permission-mode` work-session action (v0.4.24).

Modelled on the handoff facade: one fresh human decision on the exact claimed
session, its original resume, and its explicit original re-review. The
decision is bound to the registry post-image that carries the permission,
recorded on the actor as a `human_session_decision`, and the actor's observed
binding is re-saved because the session revision moves.
"""

from __future__ import annotations

from . import exact_human_approval as approval
from . import work_session_actor as actor
from . import work_session_actor_execution as actor_guard
from . import work_session_bundle as bundle
from . import work_session_claim as claim
from . import work_session_establishment as establishment
from . import work_session_execution as execution
from . import work_session_lifecycle as lifecycle
from . import work_session_permission as permission_rules
from . import work_session_registry as registry
from . import work_session_rereview as rereview
from . import work_session_state as state

_ERRORS = frozenset({
    "work_session_permission_mode_invalid",
    "work_session_permission_mode_current_unavailable",
    "work_session_task_context_required",
    "work_session_task_context_mismatch",
    "work_session_task_context_changed",
    "work_session_original_operation_missing",
    "work_session_original_operation_pending",
    "work_session_original_operation_changed",
    "work_session_original_operation_kind_unsupported",
}) | permission_rules._ERRORS


class WorkSessionPermissionModeError(RuntimeError):
    def __init__(self, code: str = "work_session_permission_mode_invalid", *, original_commit_verified: bool = False) -> None:
        super().__init__(code if code in _ERRORS else "work_session_permission_mode_invalid")
        self.code = code if code in _ERRORS else "work_session_permission_mode_invalid"
        self.original_commit_verified = original_commit_verified


def _safe_call(call):
    try:
        return call()
    except WorkSessionPermissionModeError:
        raise
    except permission_rules.WorkSessionPermissionError as error:
        raise WorkSessionPermissionModeError(error.code) from None
    except (registry.WorkSessionRegistryError, actor.WorkSessionActorError, bundle.WorkSessionBundleError,
            execution.WorkSessionExecutionError, actor_guard.WorkSessionTaskSelectionError,
            claim.WorkSessionClaimError, state.WorkSessionStateError, lifecycle.WorkSessionLifecycleError) as error:
        code = error.args[0] if error.args and error.args[0] in _ERRORS else "work_session_permission_mode_invalid"
        raise WorkSessionPermissionModeError(code) from None
    except Exception:
        raise WorkSessionPermissionModeError() from None


def _assert_selected(routing, selected):
    current = routing._read(current=False)
    if current is None or current.sha256 != selected.sha256:
        raise WorkSessionPermissionModeError("work_session_task_context_changed")


def _bound_decision(store, pointer, *, app, route, session):
    if type(pointer) is not dict or pointer.get("kind") != "human_session_decision":
        raise WorkSessionPermissionModeError("work_session_original_operation_changed")
    bound = bundle.load_context_bound_session_decision(store, manifest_sha256=pointer["manifest_sha256"])
    prepared, binding = bound.prepared, bound.prepared.manifest.work_session_binding
    request = prepared.transition._request
    if (prepared.transition.action != "set-permission-mode" or binding.client_app_ref != app
            or binding.work_session_ref != session or prepared.task_route_ref != route
            or prepared.manifest.archive_identity_sha256 != store.archive_identity_sha256
            or request["client_app_ref"] != app or request["work_session_ref"] != session
            or approval.exact_human_approval_context_sha256(bound.context) != pointer["context_sha256"]):
        raise WorkSessionPermissionModeError("work_session_original_operation_changed")
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
        raise WorkSessionPermissionModeError("work_session_original_operation_changed")
    store._require_held_lock(held)


def _current_permission(store, *, held, expected, permission):
    """The session stays claimed under the same claim; only the permission moved."""
    with store._read_boundary():
        bundle._check_store(store)
        first = store.read()
        row = first._document["sessions"].get(expected.work_session_ref)
        if (row is None or first.binding(expected.work_session_ref) != expected
                or row["state"] != "claimed" or row["claim_ref"] is None
                or row.get("permission") != permission
                or first._document["workstreams"][row["workstream_ref"]]["active_session_ref"] != expected.work_session_ref
                or store.read().sha256 != first.sha256):
            raise WorkSessionPermissionModeError("work_session_permission_mode_current_unavailable")
        bundle._check_store(store)
        store._require_held_lock(held)
    return expected, row["claim_ref"]


def _finish(store, routing, selected, bound, result, *, held, app, route, session, publish):
    expected = bound.prepared.manifest.work_session_binding
    permission = bound.prepared.transition._request["permission"]
    if (type(result) is not dict or result.get("ok") is not True
            or result.get("independent_post_verification") is not True
            or result.get("work_session_binding") != expected.document()):
        raise WorkSessionPermissionModeError("work_session_original_operation_changed")
    pointer = {"kind": "human_session_decision", "manifest_sha256": bound.prepared.manifest.manifest_sha256,
               "context_sha256": approval.exact_human_approval_context_sha256(bound.context)}
    if _bound_decision(store, pointer, app=app, route=route, session=session) != bound:
        raise WorkSessionPermissionModeError("work_session_original_operation_changed", original_commit_verified=True)
    try:
        _assert_selected(routing, selected)
        current, claim_ref = _current_permission(store, held=held, expected=expected, permission=permission)
    except Exception:
        raise WorkSessionPermissionModeError("work_session_permission_mode_current_unavailable", original_commit_verified=True) from None
    if publish:
        try:
            selected = routing.save(expected_sha256=selected.sha256, held_lock=held,
                work_session_ref=session, observed_binding=current, claim_ref=claim_ref,
                pending_manifest_sha256=None, pending_context_sha256=None,
                pending_registry_intent_plan_sha256=None,
                last_completed_operation=actor.CompletedOperationSelector.from_document(pointer))
        except Exception:
            raise WorkSessionPermissionModeError("work_session_task_context_changed", original_commit_verified=True) from None
    elif (selected.document()["observed_binding"] != current.document()
          or selected.document()["claim_ref"] != claim_ref):
        raise WorkSessionPermissionModeError("work_session_task_context_changed", original_commit_verified=True)
    try:
        _assert_selected(routing, selected)
        store._require_held_lock(held)
    except Exception:
        raise WorkSessionPermissionModeError("work_session_task_context_changed", original_commit_verified=True) from None
    mode = permission_rules.MODE_MANUAL if permission is None else permission["mode"]
    return {**result, "schema": "wom-kit/work-session-permission-mode-result/v1",
            "state": "claimed", "permission_mode": mode,
            "permitted_operations": [] if permission is None else list(permission["operations"]),
            "original_commit_verified": True, "current_state_verified": True,
            "current_claim_ownership_verified": True, "claim_tokens_echoed": False,
            "routing_is_write_authority": False, "dialog_skipped_for_this_decision": False,
            "task_continuation": selected.public_summary(), "original_operation_already_completed": not publish}


def _set_permission_mode_held(root, *, held, client_app_ref, task_route_ref, work_session_ref,
                              permission, original_resume, reviewer_claim=None):
    """Set manual / limited / allow_all on the exact claimed session, or resume the original."""
    def run():
        if type(original_resume) is not bool or (original_resume and reviewer_claim is not None):
            raise WorkSessionPermissionModeError()
        if not original_resume and (type(reviewer_claim) is not str or not reviewer_claim):
            raise WorkSessionPermissionModeError()
        registry._validate_permission(permission)
        if work_session_ref is None:
            raise WorkSessionPermissionModeError("work_session_task_context_required")
        if not registry._ref(work_session_ref, "work_session"):
            raise WorkSessionPermissionModeError("work_session_task_context_mismatch")
        store, routing = lifecycle._routing(root, held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref)
        selected = routing._read(current=False)
        if selected is None:
            raise WorkSessionPermissionModeError("work_session_task_context_required")
        document = selected.document()
        if document["work_session_ref"] != work_session_ref:
            raise WorkSessionPermissionModeError("work_session_task_context_mismatch")
        if document.get("pending_registry_intent_plan_sha256") is not None:
            raise WorkSessionPermissionModeError("work_session_original_operation_pending")
        pending_selector = selected.pending_operation()
        pending = pending_selector is not None
        if pending and pending_selector.document()["kind"] in actor._DOMAIN_OPERATION_KINDS:
            raise WorkSessionPermissionModeError("work_session_original_operation_kind_unsupported")
        scope = dict(app=client_app_ref, route=task_route_ref, session=work_session_ref)
        if original_resume:
            pointer = (pending_selector.document() if pending else document.get("last_completed_operation"))
            if pointer is None:
                raise WorkSessionPermissionModeError("work_session_original_operation_missing")
            if pointer["kind"] in actor._DOMAIN_OPERATION_KINDS:
                raise WorkSessionPermissionModeError("work_session_original_operation_kind_unsupported")
            bound = _bound_decision(store, pointer, **scope)
            _verify_origin(root, store, routing, selected, held=held, **scope)
            if pending:
                _pending_predecessor(store, selected, bound, held=held, session=work_session_ref)
            _assert_selected(routing, selected)
            result = execution._resume_session_decision_held(root, held=held,
                manifest_sha256=pointer["manifest_sha256"], completed_only=not pending)
            return _finish(store, routing, selected, bound, result, held=held, publish=pending, **scope)
        if pending:
            raise WorkSessionPermissionModeError("work_session_original_operation_pending")
        expected = actor_guard._require_actor_selection_for_write_held(root, held=held,
            client_app_ref=client_app_ref, task_route_ref=task_route_ref, work_session_ref=work_session_ref)
        if expected.document() != document["observed_binding"]:
            raise WorkSessionPermissionModeError("work_session_task_context_changed")
        origin = _verify_origin(root, store, routing, selected, held=held, **scope)
        origin_bound = establishment.load_original_establishment(store, selector=origin,
            client_app_ref=client_app_ref, task_route_ref=task_route_ref, work_session_ref=work_session_ref)
        published = {}

        def before_claim(prepared, context):
            _assert_selected(routing, selected)
            current = actor_guard._require_actor_selection_for_write_held(root, held=held,
                client_app_ref=client_app_ref, task_route_ref=task_route_ref, work_session_ref=work_session_ref)
            if (current != expected or prepared.transition.action != "set-permission-mode"
                    or prepared.transition._request["claim_ref"] != document["claim_ref"]
                    or prepared.transition._request["permission"] != permission
                    or prepared.task_route_ref != task_route_ref
                    or prepared.manifest.work_session_binding.client_app_ref != client_app_ref
                    or prepared.manifest.work_session_binding.work_session_ref != work_session_ref
                    or establishment.load_original_establishment(store, selector=origin,
                        client_app_ref=client_app_ref, task_route_ref=task_route_ref,
                        work_session_ref=work_session_ref) != origin_bound):
                raise WorkSessionPermissionModeError("work_session_original_operation_changed")
            published["actor"] = routing.save(expected_sha256=selected.sha256, held_lock=held,
                work_session_ref=work_session_ref, observed_binding=expected, claim_ref=document["claim_ref"],
                pending_manifest_sha256=prepared.manifest.manifest_sha256,
                pending_context_sha256=approval.exact_human_approval_context_sha256(context),
                pending_registry_intent_plan_sha256=None, established_origin=origin)

        result = execution._execute_session_decision_held(root, held=held, action="set-permission-mode",
            client_app_ref=client_app_ref, task_route_ref=task_route_ref, work_session_ref=work_session_ref,
            claim_ref=document["claim_ref"], permission=permission, reviewer_claim=reviewer_claim,
            before_claim_publication=before_claim)
        selected_after = published.get("actor")
        if selected_after is None:
            raise WorkSessionPermissionModeError("work_session_original_operation_changed")
        pending_selector = selected_after.pending_operation()
        if pending_selector is None or pending_selector.document()["kind"] != "human_session_decision":
            raise WorkSessionPermissionModeError("work_session_original_operation_kind_unsupported")
        bound = _bound_decision(store, pending_selector.document(), **scope)
        return _finish(store, routing, selected_after, bound, result, held=held, publish=True, **scope)
    return _safe_call(run)


def _review_original_permission_mode_held(root, *, held, client_app_ref, task_route_ref, work_session_ref):
    """Explicit original re-review only when its pending claim is truly absent."""
    def run():
        if work_session_ref is None:
            raise WorkSessionPermissionModeError("work_session_task_context_required")
        if not registry._ref(work_session_ref, "work_session"):
            raise WorkSessionPermissionModeError("work_session_task_context_mismatch")
        store, routing = lifecycle._routing(root, held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref)
        selected = routing._read(current=False)
        if selected is None:
            raise WorkSessionPermissionModeError("work_session_original_operation_missing")
        document = selected.document()
        if document["work_session_ref"] != work_session_ref:
            raise WorkSessionPermissionModeError("work_session_task_context_mismatch")
        if document.get("pending_registry_intent_plan_sha256") is not None:
            raise WorkSessionPermissionModeError("work_session_original_operation_pending")
        pending_selector = selected.pending_operation()
        pending = pending_selector is not None
        pointer = (pending_selector.document() if pending else document.get("last_completed_operation"))
        if pointer is None:
            raise WorkSessionPermissionModeError("work_session_original_operation_missing")
        if pointer["kind"] in actor._DOMAIN_OPERATION_KINDS:
            raise WorkSessionPermissionModeError("work_session_original_operation_kind_unsupported")
        scope = dict(app=client_app_ref, route=task_route_ref, session=work_session_ref)
        bound = _bound_decision(store, pointer, **scope)
        origin = _verify_origin(root, store, routing, selected, held=held, **scope)
        origin_bound = establishment.load_original_establishment(store, selector=origin,
            client_app_ref=client_app_ref, task_route_ref=task_route_ref, work_session_ref=work_session_ref)

        def assert_selected():
            _assert_selected(routing, selected)
            if _bound_decision(store, pointer, **scope) != bound:
                raise WorkSessionPermissionModeError("work_session_original_operation_changed")
            if pending:
                _pending_predecessor(store, selected, bound, held=held, session=work_session_ref)
            if establishment.load_original_establishment(store, selector=origin,
                    client_app_ref=client_app_ref, task_route_ref=task_route_ref,
                    work_session_ref=work_session_ref) != origin_bound:
                raise WorkSessionPermissionModeError("work_session_original_operation_changed")
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
