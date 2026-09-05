"""Original self-declared app registration with caller-retained selectors.

Preview performs no writes. The harness retains that exact content-free
selection before apply, and supplies the original private label separately.
No latest-intent discovery, human approval, app attestation or actor bootstrap
is introduced here. An existing intent always precedes original replay.
"""

from pathlib import Path

from . import exact_human_approval as approval
from . import work_session_registry as registry
from . import work_session_registry_intent as intents
from .work_session_wait import WorkSessionWaitError, wait_for_archive_writer


SELECTION_SCHEMA = "wom-kit/work-session-registration-selection/v1"
_SELECTION_KEYS = frozenset({
    "schema", "archive_identity_sha256", "client_app_ref", "plan_sha256",
    "before_sha256", "label_sha256",
})
_ERRORS = frozenset({
    "work_session_registration_invalid", "work_session_registration_changed",
    "work_session_registration_unavailable", "work_session_registration_path_unsafe",
    "work_session_registration_cancelled", "work_session_registration_durability_unknown",
})
_DEPENDENCY_ERRORS = {
    "work_session_registry_changed": "work_session_registration_changed",
    "work_session_path_unsafe": "work_session_registration_path_unsafe",
    "work_session_durability_unknown": "work_session_registration_durability_unknown",
    "work_session_registry_intent_changed": "work_session_registration_changed",
    "work_session_registry_intent_path_unsafe": "work_session_registration_path_unsafe",
    "work_session_registry_intent_durability_unknown": "work_session_registration_durability_unknown",
    "work_session_wait_cancelled": "work_session_registration_cancelled",
    "work_session_wait_root_changed": "work_session_registration_changed",
}


class WorkSessionRegistrationError(ValueError):
    def __init__(self, code="work_session_registration_invalid"):
        self.code = code if type(code) is str and code in _ERRORS else "work_session_registration_invalid"
        super().__init__(self.code)


def _safe_call(call):
    code = "work_session_registration_unavailable"
    try:
        return call()
    except WorkSessionRegistrationError as error:
        code = error.code
    except (registry.WorkSessionRegistryError, intents.WorkSessionRegistryIntentError, WorkSessionWaitError) as error:
        reason = error.args[0] if len(error.args) == 1 and type(error.args[0]) is str else None
        code = _DEPENDENCY_ERRORS.get(reason, "work_session_registration_invalid")
    except Exception:
        pass
    # No private label, input, parser detail, filesystem path or nested cause.
    raise WorkSessionRegistrationError(code)


def _store(root):
    resolved, archive_id = approval._archive_identity(root)
    return registry.WorkSessionRegistryStore(
        resolved, approval.exact_human_approval_archive_identity_sha256(archive_id),
    )


def _selection(value):
    if (type(value) is not dict or any(type(key) is not str for key in value)
            or set(value) != _SELECTION_KEYS or type(value["schema"]) is not str
            or value["schema"] != SELECTION_SCHEMA
            or not registry._ref(value["client_app_ref"], "client_app")
            or any(not registry._is_digest(value[key]) for key in
                   ("archive_identity_sha256", "plan_sha256", "before_sha256", "label_sha256"))):
        raise WorkSessionRegistrationError()
    # Detach caller-owned dictionary before waiting or invoking progress.
    return dict(value)


def preview_registration(root, *, label) -> dict:
    """Return one original selection, without lock, intent, actor or writes.

    The caller must retain this result before apply; losing it is not permission
    to infer a most recent registration or silently issue another app identity.
    """
    def run():
        original_label = registry._label(label)
        store = _store(root)
        before = store.read()
        transition = registry.plan_transition(before, action="register-app", label=original_label)
        if (store.read().sha256 != before.sha256
                or _store(store.root).archive_identity_sha256 != store.archive_identity_sha256):
            raise WorkSessionRegistrationError("work_session_registration_changed")
        return _selection({
            "schema": SELECTION_SCHEMA, "archive_identity_sha256": store.archive_identity_sha256,
            "client_app_ref": transition.result_refs[0], "plan_sha256": transition.plan_sha256,
            "before_sha256": before.sha256, "label_sha256": registry._label_digest(original_label),
        })
    return _safe_call(run)


def _match_original(store, selected, label, intent):
    document = intents._strict_document(intent._raw)
    request = {"action": "register-app", "client_app_ref": None, "work_session_ref": None,
               "label": label, "claim_ref": None, "target_app_ref": None}
    if (document["archive_identity_sha256"] != store.archive_identity_sha256
            or document["before_sha256"] != selected["before_sha256"]
            or document["plan_sha256"] != selected["plan_sha256"]
            or document["generated_refs"] != [selected["client_app_ref"]]
            or document["request"] != request):
        raise WorkSessionRegistrationError("work_session_registration_changed")


def apply_or_resume_registration(root, *, selection, label,
                                 cancel_requested=lambda: False, progress=lambda _event: None) -> dict:
    """Apply or observe only the caller's unchanged original registration.

    A missing intent can be saved only while the exact predecessor is current.
    An already committed app without that intent is never backfilled with newly
    manufactured original evidence. Registration itself is self-declared, not
    native human approval or permission to write in a claimed work session.
    """
    def run():
        selected = _selection(selection)
        original_label = registry._label(label)
        store = _store(root)
        if (selected["archive_identity_sha256"] != store.archive_identity_sha256
                or selected["label_sha256"] != registry._label_digest(original_label)):
            raise WorkSessionRegistrationError("work_session_registration_changed")
        with wait_for_archive_writer(Path(store.root), cancel_requested=cancel_requested, progress=progress) as held:
            store._require_held_lock(held)
            # Revalidate named archive identity after any lock wait.
            if _store(store.root).archive_identity_sha256 != selected["archive_identity_sha256"]:
                raise WorkSessionRegistrationError("work_session_registration_changed")
            try:
                intent = intents.load_registry_intent(store, plan_sha256=selected["plan_sha256"], held_lock=held)
            except intents.WorkSessionRegistryIntentError as error:
                if error.code != "work_session_registry_intent_missing":
                    raise
                before = store.read()
                if before.sha256 != selected["before_sha256"]:
                    raise WorkSessionRegistrationError("work_session_registration_changed")
                transition = registry.plan_transition(
                    before, action="register-app", label=original_label,
                    _ref_factory=lambda _prefix: selected["client_app_ref"],
                )
                if (transition.plan_sha256 != selected["plan_sha256"]
                        or transition.result_refs != (selected["client_app_ref"],)):
                    raise WorkSessionRegistrationError("work_session_registration_changed")
                intent = intents.prepare_registry_intent(store, transition, held_lock=held)
                _match_original(store, selected, original_label, intent)
                intents.save_registry_intent(store, intent, held_lock=held)
            _match_original(store, selected, original_label, intent)
            outcome = intents.observe_or_apply_registry_intent(
                store, plan_sha256=selected["plan_sha256"], held_lock=held,
            )
            _match_original(store, selected, original_label, outcome.intent)
            if (outcome.transition.action != "register-app"
                    or outcome.transition.result_refs != (selected["client_app_ref"],)):
                raise WorkSessionRegistrationError("work_session_registration_changed")
            store._require_held_lock(held)
            if _store(store.root).archive_identity_sha256 != selected["archive_identity_sha256"]:
                raise WorkSessionRegistrationError("work_session_registration_changed")
            return {
                **outcome.public_summary(), "schema": "wom-kit/work-session-registration-result/v1",
                "ok": True, "client_app_ref": selected["client_app_ref"],
                "identity_level": "self_declared", "identity_is_app_attestation": False,
                "routing_is_write_authority": False,
            }
    return _safe_call(run)
