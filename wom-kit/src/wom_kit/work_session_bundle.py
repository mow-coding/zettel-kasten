"""Private prepared-session payloads, never approval or execution authority.

An old payload is reconstructed against its exact immutable predecessor, not
the newest registry. Only the existing authenticated claim can authorize it.
No discovery, native input, credential access or automatic resume occurs here.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from pathlib import Path
import stat
from typing import Any
import uuid

from . import exact_operation_manifest as exact
from . import project_update_transaction as durable
from . import work_session_operation as operation
from . import work_session_registry as registry
from .exact_human_approval import (
    _archive_identity, exact_human_approval_archive_identity_sha256,
    exact_human_approval_context_sha256,
)
from .exact_human_approval_windows import ExactHumanApprovalContext, ExactHumanApprovalOperation


BUNDLE_SCHEMA = "wom-kit/work-session-private-plan/v1"
CONTEXT_BUNDLE_SCHEMA = "wom-kit/work-session-private-context-plan/v1"
PRIVATE_ROOT = ("profiles", "local", "work-sessions", "plans")
MAX_BUNDLE_BYTES = 2 * registry.MAX_GENERATION_BYTES
_ERRORS = frozenset({
    "work_session_bundle_invalid", "work_session_bundle_missing",
    "work_session_bundle_changed", "work_session_bundle_path_unsafe",
    "work_session_bundle_lock_required", "work_session_bundle_durability_unknown",
    "work_session_bundle_context_missing", "work_session_bundle_context_invalid",
})
_REQUEST_KEYS = frozenset({
    "action", "client_app_ref", "work_session_ref", "label", "claim_ref", "target_app_ref",
})
_CONTEXT_KEYS = frozenset({
    "operation", "archive_identity_sha256", "plan_sha256", "target_binding_sha256",
    "reviewer_claim", "review_binding_codes", "warning_codes",
})


@dataclass(frozen=True, repr=False)
class ContextBoundSessionDecision:
    """Original private context plus payload, never authenticated authority."""

    prepared: operation.PreparedSessionDecision
    context: ExactHumanApprovalContext

    def __repr__(self) -> str:
        return "<ContextBoundSessionDecision private payload, no approval authority>"


class WorkSessionBundleError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code if type(code) is str and code in _ERRORS else "work_session_bundle_invalid"
        super().__init__(self.code)


def _fail(code: str = "work_session_bundle_invalid") -> WorkSessionBundleError:
    return WorkSessionBundleError(code)


def _canonical(value: Any) -> bytes:
    raw = json.dumps(value, ensure_ascii=True, sort_keys=True,
                     separators=(",", ":"), allow_nan=False).encode("ascii")
    if len(raw) > MAX_BUNDLE_BYTES:
        raise _fail()
    return raw


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _strict_document(raw: bytes) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or len(raw) > MAX_BUNDLE_BYTES:
        raise _fail()

    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise _fail()
            result[key] = value
        return result

    def reject_constant(_value):
        raise _fail()

    value = json.loads(raw, object_pairs_hook=object_pairs, parse_constant=reject_constant)
    if type(value) is not dict or _canonical(value) != raw:
        raise _fail()
    return value


def _document(prepared: operation.PreparedSessionDecision) -> dict[str, Any]:
    if type(prepared) is not operation.PreparedSessionDecision:
        raise _fail()
    prepared.validate()
    transition = prepared.transition
    basis = {
        "schema": BUNDLE_SCHEMA,
        "archive_identity_sha256": prepared.manifest.archive_identity_sha256,
        "transition": {
            "action": transition.action, "before_sha256": transition.before_sha256,
            "after": transition.after._document, "result_refs": list(transition.result_refs),
            "plan_sha256": transition.plan_sha256, "request": transition._request,
            "generated_refs": list(transition._generated_refs),
        },
        "source_ascii": prepared.source_bytes.decode("ascii"),
        "manifest": prepared.manifest.document(),
    }
    return {**basis, "bundle_sha256": _sha(_canonical(basis))}


def _check_store(store: registry.WorkSessionRegistryStore) -> None:
    if type(store) is not registry.WorkSessionRegistryStore:
        raise _fail()
    if store.path != store.root.joinpath(*registry.PRIVATE_ROOT):
        raise _fail("work_session_bundle_path_unsafe")
    store._observe_names()  # Reparse/root identity check without creating files.
    actual_root, archive_id = _archive_identity(store.root)
    if (not os.path.samefile(actual_root, store.root)
            or exact_human_approval_archive_identity_sha256(archive_id) != store.archive_identity_sha256):
        raise _fail("work_session_bundle_changed")


def _check_lock(store, held_lock) -> None:
    if type(held_lock) is not exact.ExactOperationWriterLock:
        raise _fail("work_session_bundle_lock_required")
    try:
        held_lock.verify_held()
        if not os.path.samefile(held_lock.archive_root, store.root):
            raise _fail("work_session_bundle_lock_required")
    except (OSError, exact.ExactOperationManifestError):
        raise _fail("work_session_bundle_lock_required") from None


def _plans_directory(store) -> Path | None:
    _check_store(store)
    current = store.root
    for component in PRIVATE_ROOT:
        current = current / component
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            return None
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or exact._path_is_reparse(info):
            raise _fail("work_session_bundle_path_unsafe")
    return current


def _read_control(path: Path, *, maximum: int) -> bytes:
    """Read through a retained parent, never a racing ancestor replacement."""
    with durable._bound_directory_for_move(path.parent) as parent:
        if os.name == "nt":
            raw = exact._read_plain_file(path, max_bytes=maximum, heartbeat=lambda: None)
        else:
            # The same plain-file contract as exact._read_plain_file, addressed
            # relative to the retained POSIX directory instead of its pathname.
            before = os.stat(path.name, dir_fd=parent.descriptor, follow_symlinks=False)
            if not exact._safe_regular_stat(before, max_bytes=maximum):
                raise _fail("work_session_bundle_path_unsafe")
            descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent.descriptor)
            try:
                opened = os.fstat(descriptor)
                if (not exact._safe_regular_stat(opened, max_bytes=maximum)
                        or (opened.st_dev, opened.st_ino, opened.st_size)
                        != (before.st_dev, before.st_ino, before.st_size)):
                    raise _fail("work_session_bundle_path_unsafe")
                chunks, remaining = [], opened.st_size + 1
                while remaining:
                    chunk = os.read(descriptor, min(64 * 1024, remaining))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    remaining -= len(chunk)
                raw = b"".join(chunks)
                after = os.fstat(descriptor)
                named = os.stat(path.name, dir_fd=parent.descriptor, follow_symlinks=False)
                identity = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
                if (len(raw) != opened.st_size or identity(before) != identity(after)
                        or identity(after) != identity(named)
                        or not exact._safe_regular_stat(after, max_bytes=maximum)
                        or not exact._safe_regular_stat(named, max_bytes=maximum)):
                    raise _fail("work_session_bundle_changed")
            finally:
                os.close(descriptor)
        durable._assert_named_reservation_directory_identity(path.parent, parent.identity)
        return raw


def _generation(store, revision: int, names: tuple[str, ...]) -> registry.RegistrySnapshot:
    if revision == 0:
        return registry.RegistrySnapshot.empty(store.archive_identity_sha256)
    name = f"{revision:012d}.json"
    if name not in names:
        raise _fail("work_session_bundle_changed")
    raw = _read_control(store.path / name, maximum=registry.MAX_GENERATION_BYTES)
    snapshot = registry.RegistrySnapshot(_strict_document(raw))
    if (snapshot.revision != revision
            or snapshot._document["archive_identity_sha256"] != store.archive_identity_sha256):
        raise _fail("work_session_bundle_changed")
    return snapshot


def _decode(store, raw: bytes, manifest_sha256: str) -> operation.PreparedSessionDecision:
    _check_store(store)
    if not registry._is_digest(manifest_sha256):
        raise _fail()
    document = _strict_document(raw)
    if set(document) != {"schema", "archive_identity_sha256", "transition", "source_ascii", "manifest", "bundle_sha256"}:
        raise _fail()
    basis = {key: value for key, value in document.items() if key != "bundle_sha256"}
    if (document["schema"] != BUNDLE_SCHEMA
            or document["archive_identity_sha256"] != store.archive_identity_sha256
            or not registry._is_digest(document["bundle_sha256"])
            or not hmac.compare_digest(document["bundle_sha256"], _sha(_canonical(basis)))):
        raise _fail()
    row = document["transition"]
    if type(row) is not dict or set(row) != {"action", "before_sha256", "after", "result_refs", "plan_sha256", "request", "generated_refs"}:
        raise _fail()
    if (type(row["request"]) is not dict or set(row["request"]) != _REQUEST_KEYS
            or row["request"]["action"] != row["action"]
            or type(row["result_refs"]) is not list or len(row["result_refs"]) > 2
            or type(row["generated_refs"]) is not list or len(row["generated_refs"]) > 2
            or type(document["source_ascii"]) is not str):
        raise _fail()
    transition = registry.RegistryTransition(
        row["action"], row["before_sha256"], registry.RegistrySnapshot(row["after"]),
        tuple(row["result_refs"]), row["plan_sha256"], row["request"], tuple(row["generated_refs"]),
    )
    transition.validate()
    if transition.after.revision < 1:
        raise _fail()
    names = store._observe_names()
    current = store.read()
    if names != store._observe_names() or current.revision != len(names):
        raise _fail("work_session_bundle_changed")
    previous = _generation(store, transition.after.revision - 1, names)
    if previous.sha256 != transition.before_sha256:
        raise _fail("work_session_bundle_changed")
    generated = iter(transition._generated_refs)
    rebuilt = registry.plan_transition(previous, **transition._request,
                                       _ref_factory=lambda _prefix: next(generated))
    if next(generated, None) is not None or rebuilt != transition:
        raise _fail()
    prepared = operation.prepare_session_decision(rebuilt)
    if (prepared.manifest.manifest_sha256 != manifest_sha256
            or prepared.manifest.document() != document["manifest"]
            or prepared.source_bytes != document["source_ascii"].encode("ascii")):
        raise _fail()
    target_name = f"{transition.after.revision:012d}.json"
    if target_name in names:
        target = _generation(store, transition.after.revision, names)
        if target.sha256 != transition.after.sha256:
            raise _fail("work_session_bundle_changed")
    elif current.sha256 != transition.before_sha256:
        raise _fail("work_session_bundle_changed")
    _check_store(store)
    if (names != store._observe_names() or store.read().sha256 != current.sha256
            or _generation(store, previous.revision, names).sha256 != previous.sha256):
        raise _fail("work_session_bundle_changed")
    if target_name in names and _generation(store, transition.after.revision, names).sha256 != transition.after.sha256:
        raise _fail("work_session_bundle_changed")
    return prepared


def _read_bundle_raw(store, manifest_sha256):
    if not registry._is_digest(manifest_sha256):
        raise _fail()
    directory = _plans_directory(store)
    if directory is None:
        raise _fail("work_session_bundle_missing")
    path = directory / (manifest_sha256[7:] + ".json")
    try:
        raw = _read_control(path, maximum=MAX_BUNDLE_BYTES)
    except FileNotFoundError:
        raise _fail("work_session_bundle_missing") from None
    return raw


def _load(store, manifest_sha256):
    return _decode(store, _read_bundle_raw(store, manifest_sha256), manifest_sha256)


def _context_document(context: ExactHumanApprovalContext) -> dict[str, Any]:
    if type(context) is not ExactHumanApprovalContext:
        raise _fail("work_session_bundle_context_invalid")
    # Deliberately explicit: native-only preview text is never persisted, even
    # in a private plan. Keep the existing authority hash contract unchanged.
    return {
        "operation": context.operation.value,
        "archive_identity_sha256": context.archive_identity_sha256,
        "plan_sha256": context.plan_sha256,
        "target_binding_sha256": context.target_binding_sha256,
        "reviewer_claim": context.reviewer_claim,
        "review_binding_codes": list(context.review_binding_codes),
        "warning_codes": list(context.warning_codes),
    }


def _factory_context(store, prepared, context) -> ExactHumanApprovalContext:
    if type(context) is not ExactHumanApprovalContext:
        raise _fail("work_session_bundle_context_invalid")
    _check_store(store)
    _root, archive_id = _archive_identity(store.root)
    expected = prepared.context(archive_id=archive_id, reviewer_claim=context.reviewer_claim)
    if not hmac.compare_digest(exact_human_approval_context_sha256(expected),
                               exact_human_approval_context_sha256(context)):
        raise _fail("work_session_bundle_context_invalid")
    return expected


def _context_bound_document(prepared, context):
    basis = {
        "schema": CONTEXT_BUNDLE_SCHEMA,
        "prepared": _document(prepared),
        "context": _context_document(context),
        "context_sha256": exact_human_approval_context_sha256(context),
    }
    return {**basis, "bundle_sha256": _sha(_canonical(basis))}


def _decode_context_bound(store, raw, manifest_sha256) -> ContextBoundSessionDecision:
    document = _strict_document(raw)
    if document.get("schema") == BUNDLE_SCHEMA:
        # A valid old payload lacks context; a corrupt one remains invalid.
        _decode(store, raw, manifest_sha256)
        raise _fail("work_session_bundle_context_missing")
    if set(document) != {"schema", "prepared", "context", "context_sha256", "bundle_sha256"}:
        raise _fail("work_session_bundle_context_invalid")
    basis = {key: value for key, value in document.items() if key != "bundle_sha256"}
    if (document["schema"] != CONTEXT_BUNDLE_SCHEMA
            or not registry._is_digest(document["bundle_sha256"])
            or not hmac.compare_digest(document["bundle_sha256"], _sha(_canonical(basis)))
            or not registry._is_digest(document["context_sha256"])):
        raise _fail("work_session_bundle_context_invalid")
    prepared = _decode(store, _canonical(document["prepared"]), manifest_sha256)
    row = document["context"]
    if (type(row) is not dict or set(row) != _CONTEXT_KEYS
            or type(row["review_binding_codes"]) is not list
            or type(row["warning_codes"]) is not list):
        raise _fail("work_session_bundle_context_invalid")
    context = ExactHumanApprovalContext(
        operation=ExactHumanApprovalOperation(row["operation"]),
        archive_identity_sha256=row["archive_identity_sha256"], plan_sha256=row["plan_sha256"],
        target_binding_sha256=row["target_binding_sha256"], reviewer_claim=row["reviewer_claim"],
        review_binding_codes=tuple(row["review_binding_codes"]), warning_codes=tuple(row["warning_codes"]),
    )
    if not hmac.compare_digest(exact_human_approval_context_sha256(context), document["context_sha256"]):
        raise _fail("work_session_bundle_context_invalid")
    original = _factory_context(store, prepared, context)
    return ContextBoundSessionDecision(prepared=prepared, context=original)


def load_context_bound_session_decision(
    store: registry.WorkSessionRegistryStore, *, manifest_sha256: str,
) -> ContextBoundSessionDecision:
    """Load the original context; still requires its authenticated old claim.

    There is intentionally no reviewer/default override or pure-plan upgrade.
    """
    code = "work_session_bundle_invalid"
    try:
        return _decode_context_bound(store, _read_bundle_raw(store, manifest_sha256), manifest_sha256)
    except WorkSessionBundleError as error:
        code = error.code
    except Exception:
        pass
    raise _fail(code)


def load_prepared_session_decision(
    store: registry.WorkSessionRegistryStore, *, manifest_sha256: str,
) -> operation.PreparedSessionDecision:
    """Read only; a valid payload grants no approval, claim or resume authority."""
    code = "work_session_bundle_invalid"
    try:
        return _load(store, manifest_sha256)
    except WorkSessionBundleError as error:
        code = error.code
    except Exception:
        pass
    # Avoid retaining private parser/path values in an exception context chain.
    raise _fail(code)


def _persist_validated_payload(store, raw, frozen, held_lock, *, validate_saved) -> None:
    """One no-overwrite writer for pure and context-bound private payloads."""
    manifest_sha = frozen.manifest.manifest_sha256
    directory = _plans_directory(store)
    if directory is not None and os.path.lexists(directory / (manifest_sha[7:] + ".json")):
        existing = _read_bundle_raw(store, manifest_sha)
        validate_saved(store, existing, manifest_sha)
        if existing != raw:
            raise _fail("work_session_bundle_changed")
        _check_lock(store, held_lock)
        return
    if store.read().sha256 != frozen.transition.before_sha256:
        raise _fail("work_session_bundle_changed")
    try:
        directory = exact._ensure_private_directory(store.root, PRIVATE_ROOT)
        durable._require_directory_durable(directory)
        info = os.lstat(directory)
        directory_identity = (info.st_dev, info.st_ino)
        pending = directory / (".pending_" + uuid.uuid4().hex)
        destination = directory / (manifest_sha[7:] + ".json")
        registry._write_private_pending(pending, raw, root=store.root)
        durable._require_directory_durable(directory)
        _check_lock(store, held_lock)
        _check_store(store)
        if store.read().sha256 != frozen.transition.before_sha256:
            raise _fail("work_session_bundle_changed")
        durable._assert_named_reservation_directory_identity(directory, directory_identity)
        if _read_control(pending, maximum=MAX_BUNDLE_BYTES) != raw:
            raise _fail("work_session_bundle_changed")
        durable._atomic_move_file_no_replace(pending, destination)
        durable._require_directory_durable(directory)
        durable._assert_named_reservation_directory_identity(directory, directory_identity)
    except WorkSessionBundleError:
        raise
    except Exception:
        raise _fail("work_session_bundle_durability_unknown") from None
    restored = _read_bundle_raw(store, manifest_sha)
    validate_saved(store, restored, manifest_sha)
    if restored != raw:
        raise _fail("work_session_bundle_changed")
    _check_lock(store, held_lock)


def _save(store, prepared, held_lock) -> None:
    _check_store(store)
    _check_lock(store, held_lock)
    # Serialize/parse before callbacks or writes to detach every private view.
    raw = _canonical(_document(prepared))
    frozen = _decode(store, raw, prepared.manifest.manifest_sha256)
    _persist_validated_payload(store, raw, frozen, held_lock, validate_saved=_decode)


def save_context_bound_session_decision(
    store: registry.WorkSessionRegistryStore, prepared: operation.PreparedSessionDecision, *,
    context: ExactHumanApprovalContext, held_lock: exact.ExactOperationWriterLock,
) -> None:
    """Save exact context once, without creating approval or replacing a plan.

    A bundle hash is integrity/identity evidence, not a MAC: only the existing
    broker can authenticate approval for this original context on resume.
    """
    code = "work_session_bundle_invalid"
    try:
        _check_store(store)
        _check_lock(store, held_lock)
        raw = _canonical(_context_bound_document(prepared, context))
        frozen = _decode_context_bound(store, raw, prepared.manifest.manifest_sha256)
        _persist_validated_payload(store, raw, frozen.prepared, held_lock, validate_saved=_decode_context_bound)
        return
    except WorkSessionBundleError as error:
        code = error.code
    except Exception:
        pass
    raise _fail(code)


def save_prepared_session_decision(
    store: registry.WorkSessionRegistryStore, prepared: operation.PreparedSessionDecision, *,
    held_lock: exact.ExactOperationWriterLock,
) -> None:
    """Persist exact private payload, without a claim, receipt or registry write.

    A matching existing bundle is checked and reused, never overwritten.
    Pending/published bytes survive any uncertain durability boundary.
    """
    code = "work_session_bundle_invalid"
    try:
        _save(store, prepared, held_lock)
        return
    except WorkSessionBundleError as error:
        code = error.code
    except Exception:
        pass
    raise _fail(code)
