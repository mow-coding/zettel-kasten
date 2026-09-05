"""Private session state and CAS storage, not an approval or app attestation.

The orchestration owns native approval and an already-held archive OS lock.
This internal store preserves immutable generations using the existing durable
no-replace filesystem primitives. It neither opens an approval nor guesses a
dead owner from a clock. No private label or claimant enters public summaries.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat
import uuid
from typing import Any, Callable

from . import exact_operation_manifest as exact
from . import project_update_transaction as durable
from .work_session_binding import WorkSessionBinding


REGISTRY_SCHEMA = "wom-kit/work-session-private-registry/v1"
PLAN_SCHEMA = "wom-kit/work-session-transition/v1"
PRIVATE_ROOT = ("profiles", "local", "work-sessions", "generations")
MAX_GENERATION_BYTES = 16 * 1024 * 1024
MAX_ENTITIES = 100_000
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_GENERATION_NAME = re.compile(r"([0-9]{12})\.json\Z")
_ACTIONS = frozenset({"register-app", "create", "claim", "pause", "resume",
                      "handoff", "accept", "complete", "recover"})
_HUMAN_ACTIONS = frozenset({"create", "handoff", "accept", "recover"})
_STATES = frozenset({"created", "claimed", "paused", "handoff_pending", "handed_off", "completed"})
_ERRORS = frozenset({"work_session_registry_invalid", "work_session_registry_changed",
                    "work_session_path_unsafe", "work_session_durability_unknown",
                    "work_session_claim_conflict", "work_session_transition_invalid",
                    "work_session_human_authority_required", "work_session_lock_required"})


class WorkSessionRegistryError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code if code in _ERRORS else "work_session_registry_invalid")


def _fail(code: str) -> WorkSessionRegistryError:
    return WorkSessionRegistryError(code)


def _canonical(value: Any) -> bytes:
    try:
        raw = json.dumps(value, ensure_ascii=True, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise _fail("work_session_registry_invalid") from None
    if len(raw) > MAX_GENERATION_BYTES:
        raise _fail("work_session_registry_invalid")
    return raw


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _is_digest(value: Any) -> bool:
    return type(value) is str and _DIGEST.fullmatch(value) is not None


def _ref(value: Any, prefix: str) -> bool:
    return type(value) is str and re.fullmatch(re.escape(prefix) + r"_[0-9a-f]{32}", value) is not None


def _new_ref(prefix: str) -> str:
    return prefix + "_" + uuid.uuid4().hex


def _label(value: Any) -> str:
    if (type(value) is not str or not value or value != value.strip()
            or len(value) > 120 or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise _fail("work_session_registry_invalid")
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise _fail("work_session_registry_invalid") from None
    # Labels are not credentials. Keep their raw form private regardless of shape;
    # the native renderer must also apply the existing sensitive-preview filter.
    return value


def _label_digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_private_pending(path: Path, raw: bytes, *, root: Path) -> None:
    """Publish no private bytes through a replaceable parent pathname."""
    with durable._bound_directory_for_move(path.parent) as parent:
        if os.name == "nt":
            # All ancestors are retained without FILE_SHARE_DELETE, so the
            # existing exclusive-create writer cannot follow a swapped parent.
            durable._write_new(path, raw, within=root)
        else:
            if not isinstance(parent.descriptor, int):
                raise _fail("work_session_path_unsafe")
            # A renamed POSIX ancestor does not invalidate an open descriptor.
            # Address the retained directory, not its possibly replaced name.
            descriptor = os.open(
                path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600, dir_fd=parent.descriptor,
            )
            try:
                opened = os.fstat(descriptor)
                if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
                    raise _fail("work_session_path_unsafe")
                durable._write_all(descriptor, raw)
                os.fsync(descriptor)
                os.fsync(parent.descriptor)
            finally:
                os.close(descriptor)
            # A replacement is refused before the final generation is exposed.
            durable._assert_named_reservation_directory_identity(path.parent, parent.identity)


def _validate_document(document: Any) -> None:
    if type(document) is not dict or set(document) != {
        "schema", "archive_identity_sha256", "revision", "previous_sha256",
        "apps", "workstreams", "sessions",
    }:
        raise _fail("work_session_registry_invalid")
    revision = document["revision"]
    if (document["schema"] != REGISTRY_SCHEMA or not _is_digest(document["archive_identity_sha256"])
            or type(revision) is not int or not 0 <= revision < 10**12
            or (revision == 0 and document["previous_sha256"] is not None)
            or (revision > 0 and not _is_digest(document["previous_sha256"]))):
        raise _fail("work_session_registry_invalid")
    for name in ("apps", "workstreams", "sessions"):
        if type(document[name]) is not dict or len(document[name]) > MAX_ENTITIES:
            raise _fail("work_session_registry_invalid")
    apps, streams, sessions = (document[name] for name in ("apps", "workstreams", "sessions"))
    if revision == 0 and any((apps, streams, sessions)):
        raise _fail("work_session_registry_invalid")
    for ref, app in apps.items():
        if (not _ref(ref, "client_app") or type(app) is not dict
                or set(app) != {"label", "identity_level"}
                or type(app["identity_level"]) is not str
                or app["identity_level"] not in {"self_declared", "human_confirmed"}):
            raise _fail("work_session_registry_invalid")
        _label(app["label"])
    for ref, stream in streams.items():
        if (not _ref(ref, "workstream") or type(stream) is not dict
                or set(stream) != {"label", "active_session_ref"}):
            raise _fail("work_session_registry_invalid")
        _label(stream["label"])
        active = stream["active_session_ref"]
        if active is not None and (not _ref(active, "work_session") or active not in sessions):
            raise _fail("work_session_registry_invalid")
    for ref, session in sessions.items():
        if (not _ref(ref, "work_session") or type(session) is not dict
                or set(session) != {"client_app_ref", "workstream_ref", "revision", "state",
                                    "claim_ref", "predecessor_ref", "handoff_app_ref"}
                or not _ref(session["client_app_ref"], "client_app")
                or not _ref(session["workstream_ref"], "workstream")
                or session["client_app_ref"] not in apps or session["workstream_ref"] not in streams
                or type(session["revision"]) is not int or session["revision"] < 1
                or type(session["state"]) is not str
                or session["state"] not in _STATES):
            raise _fail("work_session_registry_invalid")
        predecessor = session["predecessor_ref"]
        if predecessor is not None and (not _ref(predecessor, "work_session")
                or predecessor not in sessions or predecessor == ref
                or sessions[predecessor]["workstream_ref"] != session["workstream_ref"]):
            raise _fail("work_session_registry_invalid")
        claim = session["claim_ref"]
        if ((session["state"] == "claimed" and not _ref(claim, "claim"))
                or (session["state"] != "claimed" and claim is not None)):
            raise _fail("work_session_registry_invalid")
        destination = session["handoff_app_ref"]
        if (session["state"] == "handoff_pending") != (destination is not None):
            raise _fail("work_session_registry_invalid")
        if destination is not None and (not _ref(destination, "client_app")
                or destination not in apps or destination == session["client_app_ref"]):
            raise _fail("work_session_registry_invalid")
        active = streams[session["workstream_ref"]]["active_session_ref"]
        if session["state"] not in {"completed", "handed_off"} and active != ref:
            raise _fail("work_session_registry_invalid")
        if active == ref and session["state"] in {"completed", "handed_off"}:
            raise _fail("work_session_registry_invalid")


@dataclass(frozen=True, repr=False)
class RegistrySnapshot:
    _document: dict[str, Any] = field(repr=False)

    def __post_init__(self) -> None:
        _validate_document(self._document)
        object.__setattr__(self, "_document", json.loads(_canonical(self._document)))

    def __repr__(self) -> str:
        return "RegistrySnapshot(<private>)"

    @classmethod
    def empty(cls, archive_identity_sha256: str) -> "RegistrySnapshot":
        return cls({"schema": REGISTRY_SCHEMA, "archive_identity_sha256": archive_identity_sha256,
                    "revision": 0, "previous_sha256": None, "apps": {}, "workstreams": {}, "sessions": {}})

    @property
    def revision(self) -> int:
        return self._document["revision"]

    @property
    def sha256(self) -> str:
        _validate_document(self._document)
        return _digest(self._document)

    def public_summary(self) -> dict[str, Any]:
        return {"schema": "wom-kit/work-session-registry-summary/v1", "revision": self.revision,
                "snapshot_sha256": self.sha256, "app_count": len(self._document["apps"]),
                "workstream_count": len(self._document["workstreams"]),
                "session_count": len(self._document["sessions"]), "private_labels_echoed": False}

    def binding(self, session_ref: str) -> WorkSessionBinding:
        _validate_document(self._document)
        if not _ref(session_ref, "work_session"):
            raise _fail("work_session_registry_invalid")
        session = self._document["sessions"].get(session_ref)
        if session is None:
            raise _fail("work_session_registry_invalid")
        return WorkSessionBinding.build(
            client_app_ref=session["client_app_ref"], workstream_ref=session["workstream_ref"],
            work_session_ref=session_ref, revision=session["revision"],
            archive_identity_sha256=self._document["archive_identity_sha256"],
            client_app_label_sha256=_label_digest(self._document["apps"][session["client_app_ref"]]["label"]),
            workstream_label_sha256=_label_digest(self._document["workstreams"][session["workstream_ref"]]["label"]),
        )


@dataclass(frozen=True, repr=False)
class RegistryTransition:
    action: str
    before_sha256: str
    after: RegistrySnapshot = field(repr=False)
    result_refs: tuple[str, ...]
    plan_sha256: str
    _request: dict[str, Any] = field(repr=False)
    _generated_refs: tuple[str, ...] = field(repr=False)

    def __repr__(self) -> str:
        return "RegistryTransition(<private>)"

    @property
    def human_decision_required(self) -> bool:
        self.validate()
        return self.action in _HUMAN_ACTIONS

    def _basis(self) -> dict[str, Any]:
        return {"schema": PLAN_SCHEMA, "action": self.action, "before_sha256": self.before_sha256,
                "after_sha256": self.after.sha256, "result_refs": list(self.result_refs)}

    def validate(self) -> None:
        if (type(self.action) is not str or self.action not in _ACTIONS
                or not _is_digest(self.before_sha256) or not _is_digest(self.plan_sha256)
                or type(self.after) is not RegistrySnapshot
                or self.after._document["previous_sha256"] != self.before_sha256
                or not hmac.compare_digest(self.plan_sha256, _digest(self._basis()))):
            raise _fail("work_session_transition_invalid")


def plan_transition(snapshot: RegistrySnapshot, *, action: str, client_app_ref: str | None = None,
                    work_session_ref: str | None = None, label: str | None = None,
                    claim_ref: str | None = None, target_app_ref: str | None = None,
                    _ref_factory: Callable[[str], str] = _new_ref) -> RegistryTransition:
    """Plan one exact transition; does not grant approval or write any file."""
    if type(snapshot) is not RegistrySnapshot or type(action) is not str or action not in _ACTIONS:
        raise _fail("work_session_transition_invalid")
    for value, prefix in ((client_app_ref, "client_app"), (work_session_ref, "work_session"),
                          (claim_ref, "claim"), (target_app_ref, "client_app")):
        if value is not None and not _ref(value, prefix):
            raise _fail("work_session_transition_invalid")
    before_sha256 = snapshot.sha256
    request = {"action": action, "client_app_ref": client_app_ref, "work_session_ref": work_session_ref,
               "label": label, "claim_ref": claim_ref, "target_app_ref": target_app_ref}
    document = deepcopy(snapshot._document)
    apps, streams, sessions = (document[name] for name in ("apps", "workstreams", "sessions"))
    generated: list[str] = []

    def new_ref(prefix: str) -> str:
        value = _ref_factory(prefix)
        if (not _ref(value, prefix) or value in generated or value in apps or value in streams
                or value in sessions or any(row["claim_ref"] == value for row in sessions.values())):
            raise _fail("work_session_transition_invalid")
        generated.append(value)
        return value

    refs: tuple[str, ...]
    if action == "register-app":
        if any(value is not None for value in (client_app_ref, work_session_ref, claim_ref, target_app_ref)):
            raise _fail("work_session_transition_invalid")
        app_ref = new_ref("client_app")
        apps[app_ref] = {"label": _label(label), "identity_level": "self_declared"}
        refs = (app_ref,)
    else:
        if client_app_ref not in apps:
            raise _fail("work_session_transition_invalid")
        if action == "create":
            if any(value is not None for value in (work_session_ref, claim_ref, target_app_ref)):
                raise _fail("work_session_transition_invalid")
            stream_ref, session_ref = new_ref("workstream"), new_ref("work_session")
            streams[stream_ref] = {"label": _label(label), "active_session_ref": session_ref}
            sessions[session_ref] = {"client_app_ref": client_app_ref, "workstream_ref": stream_ref,
                                     "revision": 1, "state": "created", "claim_ref": None,
                                     "predecessor_ref": None, "handoff_app_ref": None}
            apps[client_app_ref]["identity_level"] = "human_confirmed"
            refs = (stream_ref, session_ref)
        else:
            if label is not None or work_session_ref not in sessions:
                raise _fail("work_session_transition_invalid")
            session = sessions[work_session_ref]
            state = session["state"]
            stream = streams[session["workstream_ref"]]
            if action == "accept":
                if (state != "handoff_pending" or session["handoff_app_ref"] != client_app_ref
                        or claim_ref is not None or target_app_ref is not None):
                    raise _fail("work_session_claim_conflict")
                next_ref = new_ref("work_session")
                sessions[next_ref] = {"client_app_ref": client_app_ref, "workstream_ref": session["workstream_ref"],
                                      "revision": 1, "state": "created", "claim_ref": None,
                                      "predecessor_ref": work_session_ref, "handoff_app_ref": None}
                session.update(state="handed_off", handoff_app_ref=None)
                stream["active_session_ref"] = next_ref
                apps[client_app_ref]["identity_level"] = "human_confirmed"
                refs = (next_ref,)
            else:
                if session["client_app_ref"] != client_app_ref:
                    raise _fail("work_session_claim_conflict")
                if action in {"claim", "resume"}:
                    required = "created" if action == "claim" else "paused"
                    if state != required or claim_ref is not None or target_app_ref is not None:
                        raise _fail("work_session_claim_conflict")
                    session.update(state="claimed", claim_ref=new_ref("claim"))
                elif action == "recover":
                    # Recovery is a new exact human decision under the OS lock,
                    # never a conclusion inferred from PID or heartbeat age.
                    if state != "claimed" or claim_ref is not None or target_app_ref is not None:
                        raise _fail("work_session_claim_conflict")
                    session["claim_ref"] = new_ref("claim")
                else:
                    if (state != "claimed" or not _ref(claim_ref, "claim")
                            or not hmac.compare_digest(session["claim_ref"], claim_ref)):
                        raise _fail("work_session_claim_conflict")
                    if action == "handoff":
                        if target_app_ref not in apps or target_app_ref == client_app_ref:
                            raise _fail("work_session_transition_invalid")
                        session.update(state="handoff_pending", handoff_app_ref=target_app_ref, claim_ref=None)
                    elif action in {"pause", "complete"}:
                        if target_app_ref is not None:
                            raise _fail("work_session_transition_invalid")
                        session.update(state="paused" if action == "pause" else "completed", claim_ref=None)
                        if action == "complete":
                            stream["active_session_ref"] = None
                    else:
                        raise _fail("work_session_transition_invalid")
                refs = (work_session_ref,)
            session["revision"] += 1
    document["revision"] += 1
    document["previous_sha256"] = before_sha256
    after = RegistrySnapshot(document)
    basis = {"schema": PLAN_SCHEMA, "action": action, "before_sha256": before_sha256,
             "after_sha256": after.sha256, "result_refs": list(refs)}
    return RegistryTransition(action, before_sha256, after, refs, _digest(basis), request, tuple(generated))


class WorkSessionRegistryStore:
    """Internal private persistence. Callers provide lock and exact authority.

    Human transitions require an authority checker bound to the plan SHA; the
    future non-injectable broker wrapper supplies it. This core is not a CLI
    approval route. A label digest and CAS alone are not human authority.
    """

    def __init__(self, archive_root: Path, archive_identity_sha256: str) -> None:
        self.root = Path(os.path.abspath(archive_root))
        self.archive_identity_sha256 = archive_identity_sha256
        RegistrySnapshot.empty(archive_identity_sha256)
        try:
            durable._safe_existing_chain(self.root, directory=True)
            info = os.lstat(self.root)
            self._root_identity = (info.st_dev, info.st_ino)
        except (OSError, durable.ProjectUpdateTransactionError):
            raise _fail("work_session_path_unsafe") from None
        self.path = self.root.joinpath(*PRIVATE_ROOT)

    def __repr__(self) -> str:
        return "WorkSessionRegistryStore(<private>)"

    def _observe_names(self) -> tuple[str, ...]:
        current = self.root
        try:
            durable._safe_existing_chain(self.root, directory=True)
            info = os.lstat(self.root)
            if (info.st_dev, info.st_ino) != self._root_identity:
                raise _fail("work_session_path_unsafe")
            for component in PRIVATE_ROOT:
                current = current / component
                try:
                    info = os.lstat(current)
                except FileNotFoundError:
                    return ()
                if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or exact._path_is_reparse(info):
                    raise _fail("work_session_path_unsafe")
            names = []
            with os.scandir(self.path) as entries:
                for entry in entries:
                    if len(names) >= MAX_ENTITIES:
                        raise _fail("work_session_registry_invalid")
                    if _GENERATION_NAME.fullmatch(entry.name):
                        names.append(entry.name)
                    elif not re.fullmatch(r"\.pending_[0-9a-f]{32}", entry.name):
                        raise _fail("work_session_path_unsafe")
            return tuple(sorted(names))
        except (OSError, durable.ProjectUpdateTransactionError):
            raise _fail("work_session_path_unsafe") from None

    def read(self) -> RegistrySnapshot:
        before = self._observe_names()
        if not before:
            return RegistrySnapshot.empty(self.archive_identity_sha256)
        # Validate the consecutive names so a missing generation cannot silently
        # become the new current state. Only the two newest full snapshots need
        # reading; immutable older generations remain private recovery evidence.
        if any(name != f"{index:012d}.json" for index, name in enumerate(before, 1)):
            raise _fail("work_session_registry_invalid")
        documents = []
        try:
            for name in before[-2:]:
                raw = exact._read_plain_file(self.path / name, max_bytes=MAX_GENERATION_BYTES, heartbeat=lambda: None)
                value = json.loads(raw)
                if _canonical(value) != raw:
                    raise _fail("work_session_registry_invalid")
                snapshot = RegistrySnapshot(value)
                if (snapshot._document["archive_identity_sha256"] != self.archive_identity_sha256
                        or snapshot.revision != int(name[:12])):
                    raise _fail("work_session_registry_invalid")
                documents.append(snapshot)
        except (OSError, ValueError, TypeError):
            raise _fail("work_session_registry_invalid") from None
        parent = documents[-2] if len(documents) == 2 else RegistrySnapshot.empty(self.archive_identity_sha256)
        if (documents[-1]._document["previous_sha256"] != parent.sha256 or before != self._observe_names()):
            raise _fail("work_session_registry_changed")
        return documents[-1]

    def commit(self, plan: RegistryTransition, *, held_lock: exact.ExactOperationWriterLock,
               verify_human_authority: Callable[[str], bool] | None = None) -> RegistrySnapshot:
        if type(plan) is not RegistryTransition:
            raise _fail("work_session_transition_invalid")
        plan.validate()
        if type(held_lock) is not exact.ExactOperationWriterLock:
            raise _fail("work_session_lock_required")
        try:
            held_lock.verify_held()
            if not os.path.samefile(held_lock.archive_root, self.root):
                raise _fail("work_session_lock_required")
        except (OSError, exact.ExactOperationManifestError):
            raise _fail("work_session_lock_required") from None
        current = self.read()
        if (not hmac.compare_digest(current.sha256, plan.before_sha256)
                or plan.after.revision != current.revision + 1
                or plan.after._document["archive_identity_sha256"] != self.archive_identity_sha256):
            raise _fail("work_session_registry_changed")
        # Rebuild from the current state and the exact planned opaque outputs.
        # Rehashing a forged post-image cannot turn register-app into a hidden
        # human-confirmed start, a claim takeover or an unrelated state edit.
        supplied_refs = iter(plan._generated_refs)
        try:
            rebuilt = plan_transition(current, **plan._request,
                                      _ref_factory=lambda _prefix: next(supplied_refs))
            exhausted = next(supplied_refs, None) is None
        except (StopIteration, TypeError, ValueError):
            raise _fail("work_session_transition_invalid") from None
        if not exhausted or rebuilt.plan_sha256 != plan.plan_sha256:
            raise _fail("work_session_transition_invalid")
        if plan.human_decision_required:
            try:
                accepted = verify_human_authority is not None and verify_human_authority(plan.plan_sha256) is True
            except Exception:
                accepted = False
            if not accepted:
                raise _fail("work_session_human_authority_required")
        # Callback cannot change state or held-lock authority behind the CAS.
        held_lock.verify_held()
        if self.read().sha256 != plan.before_sha256:
            raise _fail("work_session_registry_changed")
        plan.validate()
        try:
            exact._ensure_private_directory(self.root, PRIVATE_ROOT)
            durable._require_directory_durable(self.path)
            pending = self.path / (".pending_" + uuid.uuid4().hex)
            destination = self.path / f"{plan.after.revision:012d}.json"
            _write_private_pending(pending, _canonical(plan.after._document), root=self.root)
            durable._require_directory_durable(self.path)
            held_lock.verify_held()
            if self.read().sha256 != plan.before_sha256:
                raise _fail("work_session_registry_changed")
            durable._atomic_move_file_no_replace(pending, destination)
            durable._require_directory_durable(self.path)
        except (OSError, durable.ProjectUpdateTransactionError, exact.ExactOperationManifestError):
            # Keep a pending image or published generation after any uncertainty.
            # Never undo a completed transition or overwrite an existing image.
            raise _fail("work_session_durability_unknown") from None
        result = self.read()
        if result.sha256 != plan.after.sha256:
            raise _fail("work_session_registry_changed")
        return result
