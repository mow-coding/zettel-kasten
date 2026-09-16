"""Claim a human-created/accepted task with its original private intent.

Internal composition only: native input and caller claim tokens are absent.
Actor pointers select records, never grant approval or current ownership.
The initial unselected-intent cut can leave an orphan intent, not a claim;
after actor pending publication all continuations use that exact original.
"""

from pathlib import Path

from . import work_session_actor as actor
from . import work_session_establishment as establishment
from . import work_session_lifecycle as lifecycle
from . import work_session_registry as registry
from . import work_session_registry_intent as intents
from .work_session_binding import WorkSessionBinding
from .work_session_wait import WorkSessionWaitError, wait_for_archive_writer


_ERRORS = frozenset({
    "work_session_claim_invalid", "work_session_claim_changed", "work_session_claim_unavailable",
    "work_session_claim_ownership_unavailable", "work_session_claim_cancelled",
    "work_session_task_context_required", "work_session_task_context_mismatch",
    "work_session_original_operation_pending", "work_session_original_operation_changed",
    "work_session_lock_required",
})


class WorkSessionClaimError(ValueError):
    def __init__(self, code="work_session_claim_invalid", *, original_commit_verified=False):
        self.code = code if type(code) is str and code in _ERRORS else "work_session_claim_invalid"
        self.original_commit_verified = original_commit_verified is True
        super().__init__(self.code)


def _safe_call(call):
    code, committed = "work_session_claim_unavailable", False
    try:
        return call()
    except WorkSessionClaimError as error:
        code, committed = error.code, error.original_commit_verified
    except lifecycle.WorkSessionLifecycleError as error:
        if error.code in _ERRORS:
            code = error.code
    except registry.WorkSessionRegistryError as error:
        if error.args == ("work_session_lock_required",):
            code = "work_session_lock_required"
    except actor.WorkSessionActorError as error:
        if error.code == "work_session_actor_changed":
            code = "work_session_claim_changed"
    except intents.WorkSessionRegistryIntentError as error:
        if error.code == "work_session_registry_intent_changed":
            code = "work_session_original_operation_changed"
    except establishment.WorkSessionEstablishmentError as error:
        if error.code in {"work_session_task_context_mismatch", "work_session_lock_required"}:
            code = error.code
        elif error.code in {"work_session_establishment_invalid", "work_session_establishment_changed"}:
            code = "work_session_original_operation_changed"
    except WorkSessionWaitError as error:
        code = "work_session_claim_cancelled" if error.args == ("work_session_wait_cancelled",) else "work_session_claim_changed"
    except Exception:
        pass
    raise WorkSessionClaimError(code, original_commit_verified=committed)


def _match_intent(intent, *, client_app_ref, work_session_ref):
    document = intents._strict_document(intent._raw)
    request = {"action": "claim", "client_app_ref": client_app_ref, "work_session_ref": work_session_ref,
               "label": None, "claim_ref": None, "target_app_ref": None}
    if document["request"] != request:
        raise WorkSessionClaimError("work_session_original_operation_changed")
    return document["generated_refs"][0]


def _assert_selection(routing, expected):
    # Selector integrity/CAS is independent of current ownership. In
    # particular a later pause must not erase an original committed outcome.
    current = routing._read(current=False)
    if current is None or current.sha256 != expected.sha256:
        raise WorkSessionClaimError("work_session_claim_changed")


def _verify_original_establishment(root, store, routing, selected, *, held, client_app_ref,
                                   task_route_ref, work_session_ref, key_provider,
                                   original_establishment_selector):
    def verify():
        pointer = original_establishment_selector
        if type(pointer) is not establishment.EstablishmentSelector:
            raise WorkSessionClaimError("work_session_original_operation_changed")
        pointer = establishment.EstablishmentSelector.from_document(pointer.document())
        recorded = selected.document().get("established_origin")
        if recorded is not None and establishment.EstablishmentSelector.from_document(recorded) != pointer:
            raise WorkSessionClaimError("work_session_original_operation_changed")
        # The immutable origin is distinct from last_completed_operation. It
        # still needs the exact original completed MAC and app/route/session.
        _assert_selection(routing, selected)
        bound = establishment.verify_original_establishment_held(
            root, store, held=held, selector=pointer, client_app_ref=client_app_ref,
            task_route_ref=task_route_ref, work_session_ref=work_session_ref, key_provider=key_provider,
        )
        _assert_selection(routing, selected)
        store._require_held_lock(held)
        return bound
    return _safe_call(verify)


def _verify_original_create(root, store, routing, selected, *, held, client_app_ref,
                            task_route_ref, work_session_ref, key_provider, original_create_selector):
    """Legacy create-only call contract; normalization never rewrites evidence."""
    def verify():
        _verify_original_establishment(
            root, store, routing, selected, held=held, client_app_ref=client_app_ref,
            task_route_ref=task_route_ref, work_session_ref=work_session_ref, key_provider=key_provider,
            original_establishment_selector=establishment.EstablishmentSelector.from_original_create(original_create_selector),
        )
    return _safe_call(verify)


def _finish(store, routing, selected, outcome, *, held, client_app_ref, work_session_ref, publish):
    restored = intents.load_registry_intent(store, plan_sha256=outcome.intent.plan_sha256, held_lock=held)
    if restored._raw != outcome.intent._raw:
        raise WorkSessionClaimError("work_session_original_operation_changed")
    claim_ref = _match_intent(outcome.intent, client_app_ref=client_app_ref, work_session_ref=work_session_ref)
    expected = outcome.transition.after.binding(work_session_ref)
    if outcome.transition.after._document["sessions"][work_session_ref]["claim_ref"] != claim_ref:
        raise WorkSessionClaimError("work_session_original_operation_changed")
    _assert_selection(routing, selected)
    try:
        binding = store.require_claimed_binding(
            client_app_ref=client_app_ref, work_session_ref=work_session_ref, claim_ref=claim_ref,
            held_lock=held, expected_binding=expected,
        )
    except registry.WorkSessionRegistryError:
        # Original commit evidence remains true; a pause/handoff/later claim
        # or unavailable current observation must not be presented as ownership.
        raise WorkSessionClaimError("work_session_claim_ownership_unavailable", original_commit_verified=True) from None
    _assert_selection(routing, selected)
    if publish:
        selected = routing.save(
            expected_sha256=selected.sha256, held_lock=held, work_session_ref=work_session_ref,
            observed_binding=binding, claim_ref=claim_ref,
            pending_manifest_sha256=None, pending_context_sha256=None,
            pending_registry_intent_plan_sha256=None,
            last_completed_operation=actor.CompletedOperationSelector.from_document({
                "kind": "registry_transition", "plan_sha256": outcome.intent.plan_sha256,
            }),
        )
    elif (selected.document()["claim_ref"] != claim_ref
          or selected.document()["observed_binding"] != binding.document()):
        raise WorkSessionClaimError("work_session_claim_changed", original_commit_verified=True)
    store._require_held_lock(held)
    return {
        **outcome.public_summary(), "schema": "wom-kit/work-session-task-claim-result/v1", "ok": True,
        "original_commit_verified": True, "current_claim_ownership_verified": True,
        "current_claim_authority_evaluated": True,
        "work_session_binding": binding.document(), "task_continuation": selected.public_summary(),
        "claim_tokens_echoed": False, "routing_is_write_authority": False,
        "original_operation_already_completed": not publish,
    }


def _claim_task_held(root, *, held, client_app_ref, task_route_ref, work_session_ref, key_provider=None):
    def run():
        if work_session_ref is None:
            raise WorkSessionClaimError("work_session_task_context_required")
        if not registry._ref(work_session_ref, "work_session"):
            raise WorkSessionClaimError("work_session_task_context_mismatch")
        store, routing = lifecycle._routing(root, held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref)
        selected = routing._read(current=False)
        if selected is None:
            raise WorkSessionClaimError("work_session_task_context_required")
        document = selected.document()
        if document["work_session_ref"] != work_session_ref:
            raise WorkSessionClaimError("work_session_task_context_mismatch")
        if document["pending_manifest_sha256"] is not None:
            raise WorkSessionClaimError("work_session_original_operation_pending")
        pending = document.get("pending_registry_intent_plan_sha256")
        completed = document.get("last_completed_operation")
        if pending is not None:
            intent = intents.load_registry_intent(store, plan_sha256=pending, held_lock=held)
            _match_intent(intent, client_app_ref=client_app_ref, work_session_ref=work_session_ref)
            _verify_original_establishment(root, store, routing, selected, held=held, client_app_ref=client_app_ref,
                                    task_route_ref=task_route_ref, work_session_ref=work_session_ref, key_provider=key_provider,
                                    original_establishment_selector=intent.original_establishment_selector)
        elif completed is not None and completed["kind"] == "registry_transition":
            # A terminal pointer is no permission to execute a pending intent.
            outcome = intents.observe_committed_registry_intent(store, plan_sha256=completed["plan_sha256"], held_lock=held)
            _verify_original_establishment(root, store, routing, selected, held=held, client_app_ref=client_app_ref,
                                    task_route_ref=task_route_ref, work_session_ref=work_session_ref, key_provider=key_provider,
                                    original_establishment_selector=outcome.intent.original_establishment_selector)
            return _finish(store, routing, selected, outcome, held=held, client_app_ref=client_app_ref,
                           work_session_ref=work_session_ref, publish=False)
        else:
            if document.get("established_origin") is not None:
                origin = establishment.EstablishmentSelector.from_document(document["established_origin"])
            else:
                if completed is None or completed["kind"] != "human_session_decision":
                    raise WorkSessionClaimError("work_session_original_operation_changed")
                origin = establishment.EstablishmentSelector.from_original_create({
                    "manifest_sha256": completed["manifest_sha256"], "context_sha256": completed["context_sha256"],
                })
            bound = _verify_original_establishment(
                root, store, routing, selected, held=held, client_app_ref=client_app_ref,
                task_route_ref=task_route_ref, work_session_ref=work_session_ref, key_provider=key_provider,
                original_establishment_selector=origin,
            )
            if (bound.prepared.manifest.work_session_binding.document() != document["observed_binding"]
                    or document["claim_ref"] is not None):
                raise WorkSessionClaimError("work_session_original_operation_changed")
            _assert_selection(routing, selected)
            before = store.read()
            session = before._document["sessions"].get(work_session_ref)
            if (session is None or session["state"] != "created" or session["claim_ref"] is not None
                    or before.binding(work_session_ref).document() != document["observed_binding"]):
                raise WorkSessionClaimError("work_session_claim_changed")
            transition = registry.plan_transition(before, action="claim", client_app_ref=client_app_ref,
                                                   work_session_ref=work_session_ref)
            intent = intents.prepare_registry_intent(store, transition, held_lock=held,
                                                      original_establishment_selector=origin)
            intents.save_registry_intent(store, intent, held_lock=held)
            _assert_selection(routing, selected)
            # This CAS comes before the first actual registry claim mutation.
            # A crash before it leaves only an unselected orphan intent.
            selected = routing.save(
                expected_sha256=selected.sha256, held_lock=held, work_session_ref=work_session_ref,
                observed_binding=WorkSessionBinding.from_document(document["observed_binding"]), claim_ref=None,
                pending_registry_intent_plan_sha256=intent.plan_sha256,
            )
        _assert_selection(routing, selected)
        outcome = intents.observe_or_apply_registry_intent(store, plan_sha256=intent.plan_sha256, held_lock=held)
        if outcome.intent._raw != intent._raw:
            raise WorkSessionClaimError("work_session_original_operation_changed")
        return _finish(store, routing, selected, outcome, held=held, client_app_ref=client_app_ref,
                       work_session_ref=work_session_ref, publish=True)
    return _safe_call(run)


def _claim_task_core(root, *, client_app_ref, task_route_ref, work_session_ref,
                     cancel_requested=lambda: False, progress=lambda _event: None, key_provider=None):
    def run():
        with wait_for_archive_writer(Path(root), cancel_requested=cancel_requested, progress=progress) as held:
            return _claim_task_held(root, held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref,
                                    work_session_ref=work_session_ref, key_provider=key_provider)
    return _safe_call(run)
