"""Original private register/claim intents; never current ownership or approval.

The caller owns the same archive lock and persists its explicit bootstrap/app
selector before committing. This module never discovers a latest intent, opens
human approval, changes actor routing or invents a replacement opaque reference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import hmac
import json
import os
from pathlib import Path
import stat
from typing import Any
import uuid

from . import exact_operation_manifest as exact
from . import project_update_transaction as durable
from . import work_session_bundle as bundle
from . import work_session_registry as registry


INTENT_SCHEMA = "wom-kit/work-session-private-registry-intent/v1"
PRIVATE_ROOT = ("profiles", "local", "work-sessions", "registry-intents")
MAX_INTENT_BYTES = 64 * 1024
_REQUEST_KEYS = frozenset({"action", "client_app_ref", "work_session_ref", "label", "claim_ref", "target_app_ref"})
_DOCUMENT_KEYS = frozenset({"schema", "archive_identity_sha256", "before_revision", "before_sha256",
                            "request", "generated_refs", "after_sha256", "plan_sha256", "intent_sha256"})
_ERRORS = frozenset({"work_session_registry_intent_invalid", "work_session_registry_intent_missing",
                    "work_session_registry_intent_changed", "work_session_registry_intent_path_unsafe",
                    "work_session_registry_intent_lock_required", "work_session_registry_intent_durability_unknown",
                    "work_session_registry_intent_action_refused"})
_DEPENDENCY_ERRORS = {
    "work_session_bundle_changed": "work_session_registry_intent_changed",
    "work_session_bundle_path_unsafe": "work_session_registry_intent_path_unsafe",
    "work_session_bundle_lock_required": "work_session_registry_intent_lock_required",
    "work_session_registry_changed": "work_session_registry_intent_changed",
    "work_session_path_unsafe": "work_session_registry_intent_path_unsafe",
    "work_session_lock_required": "work_session_registry_intent_lock_required",
    "work_session_claim_conflict": "work_session_registry_intent_changed",
    "work_session_durability_unknown": "work_session_registry_intent_durability_unknown",
}


class WorkSessionRegistryIntentError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code if type(code) is str and code in _ERRORS else "work_session_registry_intent_invalid"
        super().__init__(self.code)


def _fail(code="work_session_registry_intent_invalid"):
    return WorkSessionRegistryIntentError(code)


def _safe_call(call):
    code = "work_session_registry_intent_invalid"
    try:
        return call()
    except WorkSessionRegistryIntentError as error:
        code = error.code
    except (bundle.WorkSessionBundleError, registry.WorkSessionRegistryError) as error:
        reason = error.args[0] if len(error.args) == 1 and type(error.args[0]) is str else None
        code = _DEPENDENCY_ERRORS.get(reason, code)
    except Exception:
        pass
    # Raise outside the handler so private reader/parser paths and labels are
    # absent even from the exception's retained context/cause chain.
    raise _fail(code)


def _canonical(value: Any) -> bytes:
    raw = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
    if len(raw) > MAX_INTENT_BYTES:
        raise _fail()
    return raw


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _strict_document(raw: bytes) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or len(raw) > MAX_INTENT_BYTES:
        raise _fail()
    # Reuse duplicate-key/nonfinite/canonical rejection, then enforce the
    # narrower intent limit and exact action-specific original request shape.
    document = bundle._strict_document(raw)
    if set(document) != _DOCUMENT_KEYS or document["schema"] != INTENT_SCHEMA:
        raise _fail()
    revision = document["before_revision"]
    if type(revision) is not int or not 0 <= revision < 10**12 - 1:
        raise _fail()
    for name in ("archive_identity_sha256", "before_sha256", "after_sha256", "plan_sha256", "intent_sha256"):
        if not registry._is_digest(document[name]):
            raise _fail()
    request, generated = document["request"], document["generated_refs"]
    if type(request) is not dict or set(request) != _REQUEST_KEYS:
        raise _fail()
    action = request["action"]
    if type(action) is not str or action not in {"register-app", "claim"}:
        raise _fail("work_session_registry_intent_action_refused")
    if type(generated) is not list or len(generated) != 1:
        raise _fail()
    if request["claim_ref"] is not None or request["target_app_ref"] is not None:
        raise _fail()
    if action == "register-app":
        if request["client_app_ref"] is not None or request["work_session_ref"] is not None:
            raise _fail()
        registry._label(request["label"])
        if not registry._ref(generated[0], "client_app"):
            raise _fail()
    elif (request["label"] is not None or not registry._ref(request["client_app_ref"], "client_app")
          or not registry._ref(request["work_session_ref"], "work_session")
          or not registry._ref(generated[0], "claim")):
        raise _fail()
    basis = {key: value for key, value in document.items() if key != "intent_sha256"}
    if not hmac.compare_digest(document["intent_sha256"], _sha(_canonical(basis))):
        raise _fail()
    return document


@dataclass(frozen=True, repr=False)
class RegistryTransitionIntent:
    _raw: bytes = field(repr=False)

    def __post_init__(self):
        _safe_call(lambda: _strict_document(self._raw))

    def __repr__(self):
        return "RegistryTransitionIntent(<private original request; no ownership authority>)"

    @property
    def plan_sha256(self):
        return _safe_call(lambda: _strict_document(self._raw)["plan_sha256"])

    def public_summary(self):
        def summary():
            document = _strict_document(self._raw)
            return {"schema": "wom-kit/work-session-registry-intent-summary/v1",
                    "action": document["request"]["action"], "plan_sha256": document["plan_sha256"],
                    "intent_sha256": document["intent_sha256"], "before_revision": document["before_revision"],
                    "current_claim_authority_evaluated": False, "human_approval_granted": False,
                    "private_labels_echoed": False, "claim_refs_echoed": False}
        return _safe_call(summary)


@dataclass(frozen=True, repr=False)
class RegistryIntentOutcome:
    status: str
    transition: registry.RegistryTransition = field(repr=False)
    intent: RegistryTransitionIntent = field(repr=False)

    def __post_init__(self):
        _safe_call(self._validate)

    def _validate(self):
        if (type(self.status) is not str or self.status not in {"committed", "already_committed"}
                or type(self.transition) is not registry.RegistryTransition
                or type(self.intent) is not RegistryTransitionIntent):
            raise _fail()
        self.transition.validate()
        document = _strict_document(self.intent._raw)
        if (document["plan_sha256"] != self.transition.plan_sha256
                or document["after_sha256"] != self.transition.after.sha256):
            raise _fail()

    def __repr__(self):
        return "RegistryIntentOutcome(<private original transition; not current ownership>)"

    def public_summary(self):
        def summary():
            self._validate()
            return {**self.intent.public_summary(), "status": self.status,
                    "target_revision": self.transition.after.revision,
                    "target_sha256": self.transition.after.sha256,
                    "current_claim_authority_evaluated": False}
        return _safe_call(summary)


def _check(store, held_lock):
    bundle._check_store(store)
    bundle._check_lock(store, held_lock)


def _decode(store, raw, plan_sha256, held_lock):
    _check(store, held_lock)
    if not registry._is_digest(plan_sha256):
        raise _fail()
    document = _strict_document(raw)
    if document["archive_identity_sha256"] != store.archive_identity_sha256 or document["plan_sha256"] != plan_sha256:
        raise _fail("work_session_registry_intent_changed")
    names = store._observe_names()
    current = store.read()
    if names != store._observe_names() or current.revision != len(names):
        raise _fail("work_session_registry_intent_changed")
    previous = bundle._generation(store, document["before_revision"], names)
    if previous.sha256 != document["before_sha256"]:
        raise _fail("work_session_registry_intent_changed")
    generated = iter(document["generated_refs"])
    rebuilt = registry.plan_transition(previous, **document["request"], _ref_factory=lambda _prefix: next(generated))
    if (next(generated, None) is not None or rebuilt.human_decision_required
            or rebuilt.after.sha256 != document["after_sha256"] or rebuilt.plan_sha256 != plan_sha256):
        raise _fail()
    target_name = f"{rebuilt.after.revision:012d}.json"
    committed = target_name in names
    if committed:
        if bundle._generation(store, rebuilt.after.revision, names).sha256 != rebuilt.after.sha256:
            raise _fail("work_session_registry_intent_changed")
    elif current.revision != previous.revision or current.sha256 != previous.sha256:
        raise _fail("work_session_registry_intent_changed")
    _check(store, held_lock)
    if (names != store._observe_names() or store.read().sha256 != current.sha256
            or bundle._generation(store, previous.revision, names).sha256 != previous.sha256):
        raise _fail("work_session_registry_intent_changed")
    if committed and bundle._generation(store, rebuilt.after.revision, names).sha256 != rebuilt.after.sha256:
        raise _fail("work_session_registry_intent_changed")
    bundle._check_lock(store, held_lock)
    return rebuilt, committed


def _prepare(store, transition, held_lock):
    _check(store, held_lock)
    if type(transition) is not registry.RegistryTransition:
        raise _fail()
    transition.validate()
    if transition.action not in {"register-app", "claim"}:
        raise _fail("work_session_registry_intent_action_refused")
    basis = {"schema": INTENT_SCHEMA, "archive_identity_sha256": store.archive_identity_sha256,
             "before_revision": transition.after.revision - 1, "before_sha256": transition.before_sha256,
             "request": transition._request, "generated_refs": list(transition._generated_refs),
             "after_sha256": transition.after.sha256, "plan_sha256": transition.plan_sha256}
    raw = _canonical({**basis, "intent_sha256": _sha(_canonical(basis))})
    rebuilt, _committed = _decode(store, raw, transition.plan_sha256, held_lock)
    if rebuilt != transition:
        raise _fail()
    return RegistryTransitionIntent(raw)


def prepare_registry_intent(store, transition, *, held_lock) -> RegistryTransitionIntent:
    return _safe_call(lambda: _prepare(store, transition, held_lock))


def _directory(store):
    bundle._check_store(store)
    current = store.root
    for component in PRIVATE_ROOT:
        current = current / component
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            return None
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or exact._path_is_reparse(info):
            raise _fail("work_session_registry_intent_path_unsafe")
    return current


def _read_raw(store, plan_sha256):
    if not registry._is_digest(plan_sha256):
        raise _fail()
    directory = _directory(store)
    if directory is None:
        raise _fail("work_session_registry_intent_missing")
    try:
        return bundle._read_control(directory / (plan_sha256[7:] + ".json"), maximum=MAX_INTENT_BYTES)
    except FileNotFoundError:
        raise _fail("work_session_registry_intent_missing") from None


def _load(store, plan_sha256, held_lock):
    _check(store, held_lock)
    raw = _read_raw(store, plan_sha256)
    _decode(store, raw, plan_sha256, held_lock)
    return RegistryTransitionIntent(raw)


def load_registry_intent(store, *, plan_sha256, held_lock) -> RegistryTransitionIntent:
    """Load an explicit original intent, never the newest app or claim."""
    return _safe_call(lambda: _load(store, plan_sha256, held_lock))


def _save(store, intent, held_lock):
    _check(store, held_lock)
    if type(intent) is not RegistryTransitionIntent:
        raise _fail()
    raw, plan_sha = intent._raw, intent.plan_sha256
    rebuilt, _committed = _decode(store, raw, plan_sha, held_lock)
    directory = _directory(store)
    if directory is not None:
        try:
            existing = _read_raw(store, plan_sha)
        except WorkSessionRegistryIntentError as error:
            if error.code != "work_session_registry_intent_missing":
                raise
        else:
            _decode(store, existing, plan_sha, held_lock)
            if existing != raw:
                raise _fail("work_session_registry_intent_changed")
            bundle._check_lock(store, held_lock)
            return
    # Never manufacture an original intent after an already completed commit.
    if store.read().sha256 != rebuilt.before_sha256:
        raise _fail("work_session_registry_intent_changed")
    try:
        directory = exact._ensure_private_directory(store.root, PRIVATE_ROOT)
        durable._require_directory_durable(directory)
        with durable._bound_directory_for_move(directory) as retained:
            identity = retained.identity
            pending = directory / (".pending_" + uuid.uuid4().hex)
            destination = directory / (plan_sha[7:] + ".json")
            registry._write_private_pending(pending, raw, root=store.root)
            durable._require_directory_durable(directory)
            _check(store, held_lock)
            if store.read().sha256 != rebuilt.before_sha256:
                raise _fail("work_session_registry_intent_changed")
            durable._assert_named_reservation_directory_identity(directory, identity)
            if bundle._read_control(pending, maximum=MAX_INTENT_BYTES) != raw:
                raise _fail("work_session_registry_intent_changed")
            durable._atomic_move_file_no_replace(pending, destination, expected_parent_identity=identity)
            durable._require_directory_durable(directory)
            durable._assert_named_reservation_directory_identity(directory, identity)
    except WorkSessionRegistryIntentError:
        raise
    except Exception:
        raise _fail("work_session_registry_intent_durability_unknown") from None
    restored = _load(store, plan_sha, held_lock)
    if restored._raw != raw:
        raise _fail("work_session_registry_intent_changed")
    bundle._check_lock(store, held_lock)


def save_registry_intent(store, intent, *, held_lock) -> None:
    return _safe_call(lambda: _save(store, intent, held_lock))


def _observe_or_apply(store, plan_sha256, held_lock):
    intent = _load(store, plan_sha256, held_lock)
    transition, committed = _decode(store, intent._raw, plan_sha256, held_lock)
    if _read_raw(store, plan_sha256) != intent._raw:
        raise _fail("work_session_registry_intent_changed")
    _check(store, held_lock)
    if not committed:
        store.commit(transition, held_lock=held_lock)
    restored = _load(store, plan_sha256, held_lock)
    verified, completed = _decode(store, restored._raw, plan_sha256, held_lock)
    if not completed or restored._raw != intent._raw or verified != transition:
        raise _fail("work_session_registry_intent_changed")
    bundle._check_lock(store, held_lock)
    return RegistryIntentOutcome("already_committed" if committed else "committed", verified, restored)


def observe_or_apply_registry_intent(store, *, plan_sha256, held_lock) -> RegistryIntentOutcome:
    """Verify an original commit or commit its unchanged exact predecessor.

    A historical claim here is outcome evidence, never current claim authority.
    Fresh domain writes still require the independent claimed-binding guard.
    """
    return _safe_call(lambda: _observe_or_apply(store, plan_sha256, held_lock))
