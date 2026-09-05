"""Pause, resume or complete a task through its original private intent.

The public service owns the single OS lock and actual runtime guard. This held
facade adds no approval, lock, secret input, latest-task inference or raw claim
argument. A fresh resume claims a paused session; original_resume only follows
the already selected operation and never prepares another claim. Completion
only closes registry ownership; it never deletes or cleans up archive data.
"""

from . import work_session_actor as actor
from . import work_session_actor_execution as actor_guard
from . import work_session_bundle as bundle
from . import work_session_claim as claim
from . import work_session_lifecycle as lifecycle
from . import work_session_registry as registry
from . import work_session_registry_intent as intents
from .work_session_binding import WorkSessionBinding


_ERRORS = frozenset({
    "work_session_state_invalid", "work_session_state_changed", "work_session_state_unavailable",
    "work_session_state_current_unavailable", "work_session_state_action_mismatch",
    "work_session_task_context_required", "work_session_task_context_mismatch",
    "work_session_task_context_changed", "work_session_original_operation_pending",
    "work_session_original_operation_missing", "work_session_original_operation_changed",
    "work_session_lock_required",
})


class WorkSessionStateError(ValueError):
    def __init__(self, code="work_session_state_invalid", *, original_commit_verified=False):
        self.code = code if type(code) is str and code in _ERRORS else "work_session_state_invalid"
        self.original_commit_verified = original_commit_verified is True
        super().__init__(self.code)


def _safe_call(call):
    code, committed = "work_session_state_unavailable", False
    try:
        return call()
    except WorkSessionStateError as error:
        code, committed = error.code, error.original_commit_verified
    except (lifecycle.WorkSessionLifecycleError, claim.WorkSessionClaimError,
            actor_guard.WorkSessionTaskSelectionError) as error:
        code = error.code if error.code in _ERRORS else "work_session_state_current_unavailable"
    except registry.WorkSessionRegistryError as error:
        code = "work_session_lock_required" if error.args == ("work_session_lock_required",) else "work_session_state_changed"
    except actor.WorkSessionActorError:
        code = "work_session_state_changed"
    except intents.WorkSessionRegistryIntentError:
        code = "work_session_original_operation_changed"
    except Exception:
        pass
    # Neither private selectors nor underlying filesystem/key error text escape.
    raise WorkSessionStateError(code, original_commit_verified=committed)


def _assert_selected(routing, expected):
    current = routing._read(current=False)
    if current is None or current.sha256 != expected.sha256:
        raise WorkSessionStateError("work_session_task_context_changed")


def _match_intent(intent, *, action=None, client_app_ref, work_session_ref):
    document = intents._strict_document(intent._raw)
    request = document["request"]
    if (request["client_app_ref"] != client_app_ref or request["work_session_ref"] != work_session_ref
            or request["action"] not in {"claim", "pause", "resume", "complete"}):
        raise WorkSessionStateError("work_session_original_operation_changed")
    if action is not None and request["action"] != action:
        raise WorkSessionStateError("work_session_state_action_mismatch")
    if intent.original_create_selector is None:
        raise WorkSessionStateError("work_session_original_operation_changed")
    return document


def _verify_create(root, store, routing, selected, *, held, app, route, session, selector):
    claim._verify_original_create(
        root, store, routing, selected, held=held, client_app_ref=app,
        task_route_ref=route, work_session_ref=session, key_provider=None,
        original_create_selector=selector,
    )


def _unclaimed_binding(store, *, held, app, session, expected, state):
    """Explicit paused/completed topology, never current claimed ownership."""
    if state not in {"paused", "completed"}:
        raise WorkSessionStateError("work_session_state_invalid")
    def observe():
        snapshot = store.read()
        value = snapshot._document["sessions"].get(session)
        binding = snapshot.binding(session)
        if (value is None or value["client_app_ref"] != app or value["state"] != state
                or value["claim_ref"] is not None
                or snapshot._document["workstreams"][value["workstream_ref"]]["active_session_ref"]
                    != (session if state == "paused" else None)
                or binding != expected):
            raise WorkSessionStateError("work_session_state_current_unavailable")
        return binding
    store._require_held_lock(held)
    with store._read_boundary():
        bundle._check_store(store)
        first = observe()
        if observe() != first:
            raise WorkSessionStateError("work_session_state_changed")
        bundle._check_store(store)
        store._require_held_lock(held)
    return first


def _source_selector(store, selected, *, held, app, session):
    document = selected.document()
    pointer = document.get("last_completed_operation")
    if pointer is None or pointer["kind"] != "registry_transition":
        raise WorkSessionStateError("work_session_original_operation_missing")
    original = intents.load_registry_intent(store, plan_sha256=pointer["plan_sha256"], held_lock=held)
    _match_intent(original, client_app_ref=app, work_session_ref=session)
    outcome = intents.observe_committed_registry_intent(store, plan_sha256=original.plan_sha256, held_lock=held)
    if (outcome.intent._raw != original._raw
            or outcome.transition.after.binding(session).document() != document["observed_binding"]
            or outcome.transition.after._document["sessions"][session]["claim_ref"] != document["claim_ref"]):
        raise WorkSessionStateError("work_session_original_operation_changed")
    return original.original_create_selector


def _pending_source(store, intent, selected, *, held):
    document = intents._strict_document(intent._raw)
    names = store._observe_names()
    before = bundle._generation(store, document["before_revision"], names)
    routing = selected.document()
    session = routing["work_session_ref"]
    if (before.sha256 != document["before_sha256"]
            or before.binding(session).document() != routing["observed_binding"]
            or before._document["sessions"][session]["claim_ref"] != routing["claim_ref"]
            or names != store._observe_names()):
        raise WorkSessionStateError("work_session_original_operation_changed")
    store._require_held_lock(held)


def _finish(store, routing, selected, outcome, *, held, action, app, session, publish):
    restored = intents.observe_committed_registry_intent(store, plan_sha256=outcome.intent.plan_sha256, held_lock=held)
    if restored.intent._raw != outcome.intent._raw or restored.transition != outcome.transition:
        raise WorkSessionStateError("work_session_original_operation_changed")
    document = _match_intent(restored.intent, action=action, client_app_ref=app, work_session_ref=session)
    expected = restored.transition.after.binding(session)
    after = restored.transition.after._document["sessions"][session]
    expected_state = {"pause": "paused", "resume": "claimed", "complete": "completed"}[action]
    expected_claim = document["generated_refs"][0] if action == "resume" else None
    if after["state"] != expected_state or after["claim_ref"] != expected_claim:
        raise WorkSessionStateError("work_session_original_operation_changed")
    _assert_selected(routing, selected)
    try:
        if action in {"pause", "complete"}:
            current = _unclaimed_binding(store, held=held, app=app, session=session,
                                         expected=expected, state=expected_state)
        else:
            current = store.require_claimed_binding(client_app_ref=app, work_session_ref=session,
                claim_ref=expected_claim, expected_binding=expected, held_lock=held)
    except Exception:
        raise WorkSessionStateError("work_session_state_current_unavailable", original_commit_verified=True) from None
    _assert_selected(routing, selected)
    if publish:
        try:
            selected = routing.save(expected_sha256=selected.sha256, held_lock=held,
                work_session_ref=session, observed_binding=current, claim_ref=expected_claim,
                pending_manifest_sha256=None, pending_context_sha256=None,
                pending_registry_intent_plan_sha256=None,
                last_completed_operation=actor.CompletedOperationSelector.from_document({
                    "kind": "registry_transition", "plan_sha256": restored.intent.plan_sha256,
                }))
        except Exception:
            raise WorkSessionStateError("work_session_state_changed", original_commit_verified=True) from None
    elif (selected.document()["observed_binding"] != current.document()
          or selected.document()["claim_ref"] != expected_claim):
        raise WorkSessionStateError("work_session_state_changed", original_commit_verified=True)
    _assert_selected(routing, selected)
    store._require_held_lock(held)
    return {**restored.public_summary(), "schema": "wom-kit/work-session-task-state-result/v1", "ok": True,
            "original_commit_verified": True, "independent_post_verification": True,
            "state": after["state"], "current_state_verified": True,
            "current_claim_ownership_verified": action == "resume", "current_claim_authority_evaluated": True,
            "work_session_binding": current.document(), "task_continuation": selected.public_summary(),
            "claim_tokens_echoed": False, "routing_is_write_authority": False,
            "original_operation_already_completed": not publish}


def _transition_task_held(root, *, held, action, original_resume,
                          client_app_ref, task_route_ref, work_session_ref):
    def run():
        if type(action) is not str or action not in {"pause", "resume", "complete"} or type(original_resume) is not bool:
            raise WorkSessionStateError()
        if work_session_ref is None:
            raise WorkSessionStateError("work_session_task_context_required")
        if not registry._ref(work_session_ref, "work_session"):
            raise WorkSessionStateError("work_session_task_context_mismatch")
        store, routing = lifecycle._routing(root, held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref)
        selected = routing._read(current=False)
        if selected is None:
            raise WorkSessionStateError("work_session_task_context_required")
        document = selected.document()
        if document["work_session_ref"] != work_session_ref:
            raise WorkSessionStateError("work_session_task_context_mismatch")
        if document["pending_manifest_sha256"] is not None:
            raise WorkSessionStateError("work_session_original_operation_pending")
        pending = document.get("pending_registry_intent_plan_sha256")
        if original_resume:
            pointer = document.get("last_completed_operation")
            if pending is None and (pointer is None or pointer["kind"] != "registry_transition"):
                raise WorkSessionStateError("work_session_original_operation_missing")
            plan = pending if pending is not None else pointer["plan_sha256"]
            intent = intents.load_registry_intent(store, plan_sha256=plan, held_lock=held)
            _match_intent(intent, action=action, client_app_ref=client_app_ref, work_session_ref=work_session_ref)
            _verify_create(root, store, routing, selected, held=held, app=client_app_ref,
                           route=task_route_ref, session=work_session_ref, selector=intent.original_create_selector)
            if pending is None:
                outcome = intents.observe_committed_registry_intent(store, plan_sha256=plan, held_lock=held)
                return _finish(store, routing, selected, outcome, held=held, action=action,
                               app=client_app_ref, session=work_session_ref, publish=False)
            _pending_source(store, intent, selected, held=held)
        else:
            if pending is not None:
                raise WorkSessionStateError("work_session_original_operation_pending")
            expected = WorkSessionBinding.from_document(document["observed_binding"])
            if action in {"pause", "complete"}:
                current = actor_guard._require_actor_selection_for_write_held(root, held=held,
                    client_app_ref=client_app_ref, task_route_ref=task_route_ref, work_session_ref=work_session_ref)
                if current != expected:
                    raise WorkSessionStateError("work_session_state_changed")
            else:
                if document["claim_ref"] is not None:
                    raise WorkSessionStateError("work_session_state_current_unavailable")
                _unclaimed_binding(store, held=held, app=client_app_ref, session=work_session_ref,
                                     expected=expected, state="paused")
            _assert_selected(routing, selected)
            selector = _source_selector(store, selected, held=held, app=client_app_ref, session=work_session_ref)
            _verify_create(root, store, routing, selected, held=held, app=client_app_ref,
                           route=task_route_ref, session=work_session_ref, selector=selector)
            before = store.read()
            if (before.binding(work_session_ref) != expected
                    or before._document["sessions"][work_session_ref]["claim_ref"] != document["claim_ref"]):
                raise WorkSessionStateError("work_session_state_changed")
            transition = registry.plan_transition(before, action=action, client_app_ref=client_app_ref,
                work_session_ref=work_session_ref, claim_ref=document["claim_ref"] if action != "resume" else None)
            intent = intents.prepare_registry_intent(store, transition, held_lock=held, original_create_selector=selector)
            intents.save_registry_intent(store, intent, held_lock=held)
            _assert_selected(routing, selected)
            # One pending CAS precedes mutation. An unselected orphan intent is
            # not discovered as authority when original_resume has no selector.
            selected = routing.save(expected_sha256=selected.sha256, held_lock=held,
                work_session_ref=work_session_ref, observed_binding=expected, claim_ref=document["claim_ref"],
                pending_registry_intent_plan_sha256=intent.plan_sha256)
        _assert_selected(routing, selected)
        outcome = intents.observe_or_apply_registry_intent(store, plan_sha256=intent.plan_sha256, held_lock=held)
        if outcome.intent._raw != intent._raw:
            raise WorkSessionStateError("work_session_original_operation_changed")
        return _finish(store, routing, selected, outcome, held=held, action=action,
                       app=client_app_ref, session=work_session_ref, publish=True)
    return _safe_call(run)
