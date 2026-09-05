"""Human-confirmed same-session claim recovery, never lock or ownership theft.

A stale actor assertion is historical routing data, not current authority.
The original create/accept MAC, explicit app/task/session and a fresh exact
registry preimage precede the existing native decision. No PID, timeout,
pathname inference, new actor store or nonhuman recovery intent is used.
"""

from . import exact_human_approval as approval
from . import exact_human_approval_workflow as workflow
from . import work_session_actor as actor
from . import work_session_bundle as bundle
from . import work_session_claim as claim
from . import work_session_establishment as establishment
from . import work_session_execution as execution
from . import work_session_lifecycle as lifecycle
from . import work_session_registry as registry
from . import work_session_rereview as rereview
from . import work_session_state as state
from .work_session_binding import WorkSessionBinding


_ERRORS = frozenset({
    "work_session_recovery_invalid", "work_session_recovery_unavailable",
    "work_session_recovery_current_unavailable", "work_session_task_context_required",
    "work_session_task_context_mismatch", "work_session_task_context_changed",
    "work_session_original_operation_pending", "work_session_original_operation_missing",
    "work_session_original_operation_changed", "work_session_lock_required",
    "work_session_original_operation_kind_unsupported",
}) | workflow.ExactHumanApprovalWorkflowError._CODES


class WorkSessionRecoveryError(ValueError):
    def __init__(self, code="work_session_recovery_invalid", *, original_commit_verified=False):
        self.code = code if type(code) is str and code in _ERRORS else "work_session_recovery_invalid"
        self.original_commit_verified = original_commit_verified is True
        super().__init__(self.code)


def _safe_call(call):
    code, committed = "work_session_recovery_unavailable", False
    try:
        return call()
    except WorkSessionRecoveryError as error:
        code, committed = error.code, error.original_commit_verified
    except (lifecycle.WorkSessionLifecycleError, claim.WorkSessionClaimError,
            state.WorkSessionStateError, rereview.WorkSessionRereviewError,
            workflow.ExactHumanApprovalWorkflowError) as error:
        if type(error.code) is str and error.code in _ERRORS:
            code = error.code
    except registry.WorkSessionRegistryError as error:
        if error.args == ("work_session_lock_required",):
            code = "work_session_lock_required"
    except actor.WorkSessionActorError:
        code = "work_session_task_context_changed"
    except Exception:
        pass
    raise WorkSessionRecoveryError(code, original_commit_verified=committed)


def _selected(root, *, held, app, route, session):
    if session is None:
        raise WorkSessionRecoveryError("work_session_task_context_required")
    if not registry._ref(session, "work_session"):
        raise WorkSessionRecoveryError("work_session_task_context_mismatch")
    store, routing = lifecycle._routing(root, held=held, client_app_ref=app, task_route_ref=route)
    selected = routing._read(current=False)
    if selected is None:
        raise WorkSessionRecoveryError("work_session_task_context_required")
    if selected.document()["work_session_ref"] != session:
        raise WorkSessionRecoveryError("work_session_task_context_mismatch")
    if selected.document().get("pending_registry_intent_plan_sha256") is not None:
        raise WorkSessionRecoveryError("work_session_original_operation_pending")
    return store, routing, selected


def _assert_selected(routing, selected):
    current = routing._read(current=False)
    if current is None or current.sha256 != selected.sha256:
        raise WorkSessionRecoveryError("work_session_task_context_changed")


def _claimed_snapshot(snapshot, *, app, session):
    row = snapshot._document["sessions"].get(session)
    if (row is None or row["client_app_ref"] != app or row["state"] != "claimed"
            or not registry._ref(row["claim_ref"], "claim") or row["handoff_app_ref"] is not None
            or snapshot._document["workstreams"][row["workstream_ref"]]["active_session_ref"] != session):
        raise WorkSessionRecoveryError("work_session_recovery_current_unavailable")
    return snapshot


def _current_preimage(store, *, held, app, session):
    with store._read_boundary():
        bundle._check_store(store)
        first = _claimed_snapshot(store.read(), app=app, session=session)
        if store.read().sha256 != first.sha256:
            raise WorkSessionRecoveryError("work_session_original_operation_changed")
        bundle._check_store(store)
        store._require_held_lock(held)
    return first


def _verify_origin(root, store, routing, selected, *, held, app, route, session):
    origin = state._source_selector(store, selected, held=held, app=app, session=session)
    bound = claim._verify_original_establishment(root, store, routing, selected, held=held,
        client_app_ref=app, task_route_ref=route, work_session_ref=session,
        key_provider=None, original_establishment_selector=origin)
    return origin, bound


def _bound_original(store, pointer, *, held, app, route, session):
    if type(pointer) is not dict or pointer.get("kind") != "human_session_decision":
        raise WorkSessionRecoveryError("work_session_original_operation_changed")
    bound = bundle.load_context_bound_session_decision(store, manifest_sha256=pointer["manifest_sha256"])
    prepared, transition = bound.prepared, bound.prepared.transition
    binding = prepared.manifest.work_session_binding
    request = {"action": "recover", "client_app_ref": app, "work_session_ref": session,
               "label": None, "claim_ref": None, "target_app_ref": None}
    if (transition.action != "recover" or transition._request != request
            or prepared.task_route_ref != route or binding.client_app_ref != app
            or binding.work_session_ref != session
            or prepared.manifest.archive_identity_sha256 != store.archive_identity_sha256
            or approval.exact_human_approval_context_sha256(bound.context) != pointer["context_sha256"]
            or len(transition._generated_refs) != 1):
        raise WorkSessionRecoveryError("work_session_original_operation_changed")
    names = store._observe_names()
    before = bundle._generation(store, transition.after.revision - 1, names)
    _claimed_snapshot(before, app=app, session=session)
    _claimed_snapshot(transition.after, app=app, session=session)
    new_claim = transition._generated_refs[0]
    if (before.sha256 != transition.before_sha256
            or transition.after._document["sessions"][session]["claim_ref"] != new_claim
            or before._document["sessions"][session]["claim_ref"] == new_claim
            or names != store._observe_names()):
        raise WorkSessionRecoveryError("work_session_original_operation_changed")
    store._require_held_lock(held)
    return bound


def _pointer(selected):
    document = selected.document()
    pending_selector = selected.pending_operation()
    pending = pending_selector is not None
    pointer = (pending_selector.document() if pending
               else document.get("last_completed_operation"))
    if pointer is None:
        raise WorkSessionRecoveryError("work_session_original_operation_missing")
    if pointer["kind"] == "git_backup":
        raise WorkSessionRecoveryError("work_session_original_operation_kind_unsupported")
    return pointer, pending


def _finish(store, routing, selected, bound, result, *, held, app, route, session, publish):
    expected = bound.prepared.manifest.work_session_binding
    if (type(result) is not dict or result.get("ok") is not True
            or result.get("independent_post_verification") is not True
            or result.get("work_session_binding") != expected.document()):
        raise WorkSessionRecoveryError("work_session_original_operation_changed")
    pointer = {"kind": "human_session_decision", "manifest_sha256": bound.prepared.manifest.manifest_sha256,
               "context_sha256": approval.exact_human_approval_context_sha256(bound.context)}
    try:
        if _bound_original(store, pointer, held=held, app=app, route=route, session=session) != bound:
            raise WorkSessionRecoveryError()
        _assert_selected(routing, selected)
        new_claim = bound.prepared.transition._generated_refs[0]
        current = store.require_claimed_binding(client_app_ref=app, work_session_ref=session,
            claim_ref=new_claim, expected_binding=expected, held_lock=held)
    except Exception:
        raise WorkSessionRecoveryError("work_session_recovery_current_unavailable", original_commit_verified=True) from None
    if publish:
        try:
            selected = routing.save(expected_sha256=selected.sha256, held_lock=held,
                work_session_ref=session, observed_binding=current, claim_ref=new_claim,
                pending_manifest_sha256=None, pending_context_sha256=None,
                pending_registry_intent_plan_sha256=None,
                last_completed_operation=actor.CompletedOperationSelector.from_document(pointer))
        except Exception:
            raise WorkSessionRecoveryError("work_session_task_context_changed", original_commit_verified=True) from None
    elif (selected.document()["observed_binding"] != current.document()
          or selected.document()["claim_ref"] != new_claim):
        raise WorkSessionRecoveryError("work_session_task_context_changed", original_commit_verified=True)
    try:
        _assert_selected(routing, selected)
        store._require_held_lock(held)
    except Exception:
        raise WorkSessionRecoveryError("work_session_task_context_changed", original_commit_verified=True) from None
    return {**result, "schema": "wom-kit/work-session-task-recovery-result/v1", "state": "claimed",
            "original_commit_verified": True, "current_state_verified": True,
            "current_claim_ownership_verified": True, "current_claim_authority_evaluated": True,
            "ownership_transferred": False, "artifact_responsibility_transferred": False,
            "claim_tokens_echoed": False, "routing_is_write_authority": False,
            "task_continuation": selected.public_summary(), "original_operation_already_completed": not publish}


def _recover_task_held(root, *, held, client_app_ref, task_route_ref, work_session_ref,
                        original_resume, reviewer_claim=None):
    """Fresh human recovery or only the selected original; never latest/TTL."""
    def run():
        if type(original_resume) is not bool or (original_resume and reviewer_claim is not None):
            raise WorkSessionRecoveryError()
        if not original_resume and (type(reviewer_claim) is not str or not reviewer_claim):
            raise WorkSessionRecoveryError()
        scope = dict(app=client_app_ref, route=task_route_ref, session=work_session_ref)
        store, routing, selected = _selected(root, held=held, **scope)
        document = selected.document()
        pending_selector = selected.pending_operation()
        if ((pending_selector is not None and pending_selector.document()["kind"] == "git_backup")
                or (original_resume and (document.get("last_completed_operation") or {}).get("kind") == "git_backup"
                    and pending_selector is None)):
            raise WorkSessionRecoveryError("work_session_original_operation_kind_unsupported")
        if not original_resume and document["pending_manifest_sha256"] is not None:
            raise WorkSessionRecoveryError("work_session_original_operation_pending")
        # Complete authentication before entering the next broker/key consumer.
        origin, origin_bound = _verify_origin(root, store, routing, selected, held=held, **scope)
        if original_resume:
            pointer, pending = _pointer(selected)
            bound = _bound_original(store, pointer, held=held, **scope)
            _assert_selected(routing, selected)
            result = execution._resume_session_decision_held(root, held=held,
                manifest_sha256=bound.prepared.manifest.manifest_sha256, completed_only=not pending)
            return _finish(store, routing, selected, bound, result, held=held, publish=pending, **scope)
        before = _current_preimage(store, held=held, app=client_app_ref, session=work_session_ref)
        published = {}

        def before_claim(prepared, context):
            pointer = {"kind": "human_session_decision", "manifest_sha256": prepared.manifest.manifest_sha256,
                       "context_sha256": approval.exact_human_approval_context_sha256(context)}
            bound = _bound_original(store, pointer, held=held, **scope)
            _assert_selected(routing, selected)
            if (bound.prepared != prepared or bound.context != context
                    or prepared.transition.before_sha256 != before.sha256
                    or _current_preimage(store, held=held, app=client_app_ref, session=work_session_ref).sha256 != before.sha256
                    or establishment.load_original_establishment(store, selector=origin,
                        client_app_ref=client_app_ref, task_route_ref=task_route_ref,
                        work_session_ref=work_session_ref) != origin_bound):
                raise WorkSessionRecoveryError("work_session_original_operation_changed")
            # Preserve stale assertions as history. Pending blocks fresh writers;
            # only the exact original decision can issue the replacement claim.
            published["actor"] = routing.save(expected_sha256=selected.sha256, held_lock=held,
                work_session_ref=work_session_ref, observed_binding=WorkSessionBinding.from_document(document["observed_binding"]),
                claim_ref=document["claim_ref"], pending_manifest_sha256=pointer["manifest_sha256"],
                pending_context_sha256=pointer["context_sha256"], pending_registry_intent_plan_sha256=None,
                established_origin=origin)

        result = execution._execute_session_decision_held(root, held=held, action="recover",
            client_app_ref=client_app_ref, task_route_ref=task_route_ref, work_session_ref=work_session_ref,
            reviewer_claim=reviewer_claim, before_claim_publication=before_claim)
        selected = published.get("actor")
        if selected is None:
            raise WorkSessionRecoveryError("work_session_original_operation_changed")
        pointer, _pending = _pointer(selected)
        bound = _bound_original(store, pointer, held=held, **scope)
        return _finish(store, routing, selected, bound, result, held=held, publish=True, **scope)
    return _safe_call(run)


def _review_original_recovery_held(root, *, held, client_app_ref, task_route_ref, work_session_ref):
    """Re-review this exact pending recovery only when its claim is absent."""
    def run():
        scope = dict(app=client_app_ref, route=task_route_ref, session=work_session_ref)
        store, routing, selected = _selected(root, held=held, **scope)
        pointer, pending = _pointer(selected)
        bound = _bound_original(store, pointer, held=held, **scope)
        origin, origin_bound = _verify_origin(root, store, routing, selected, held=held, **scope)

        def assert_selected():
            _assert_selected(routing, selected)
            if (_bound_original(store, pointer, held=held, **scope) != bound
                    or establishment.load_original_establishment(store, selector=origin,
                        client_app_ref=client_app_ref, task_route_ref=task_route_ref,
                        work_session_ref=work_session_ref) != origin_bound):
                raise WorkSessionRecoveryError("work_session_original_operation_changed")

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
