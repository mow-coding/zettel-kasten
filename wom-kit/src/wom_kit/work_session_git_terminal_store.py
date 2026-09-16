"""Durable storage of signed Git assertions, never a backup-completion claim.

The original claim selects one execution filename; no directory scan, inferred
context, new approval, provider or Git call is used. Existing unsigned v1 domain
receipts are preserved and refused, not upgraded. Loading returns strict data
only. Saving requires original started readiness and reauthenticates both MACs
and the common receipt/checkpoints around no-replace durable publication.
"""

from __future__ import annotations

from contextlib import ExitStack
import os
import stat
import uuid

from . import exact_human_approval as approval
from . import exact_operation_manifest as exact
from . import git_backup_writer as writer
from . import project_update_transaction as durable
from . import work_session_bundle as controls
from . import work_session_git_terminal as terminal
from . import work_session_registry as registry


ENVELOPE_SCHEMA = "wom-kit/git-backup-completion/v2"
RECEIPT_ROOT = ("receipts", "ops", "git-backups")
MAX_ENVELOPE_BYTES = terminal.MAX_RECORD_BYTES + 4096
_ERRORS = frozenset({
    "work_session_git_terminal_store_invalid", "work_session_git_terminal_store_missing",
    "work_session_git_terminal_store_conflict", "work_session_git_terminal_store_changed",
    "work_session_git_terminal_store_authentication_invalid",
    "work_session_git_terminal_store_path_unsafe", "work_session_git_terminal_store_lock_required",
    "work_session_git_terminal_store_durability_unknown",
})


class GitTerminalStoreError(RuntimeError):
    def __init__(self, code="work_session_git_terminal_store_invalid"):
        self.code = code if type(code) is str and code in _ERRORS else "work_session_git_terminal_store_invalid"
        super().__init__(self.code)


def _safe_call(call):
    code = "work_session_git_terminal_store_invalid"
    try:
        return call()
    except GitTerminalStoreError as error:
        code = error.code
    except Exception:
        pass
    raise GitTerminalStoreError(code)


def _held(prepared, held):
    failed = False
    try:
        writer._require_git_backup_held_lock(prepared, held)
    except Exception:
        failed = True
    if failed:
        raise GitTerminalStoreError("work_session_git_terminal_store_lock_required")


def _selector(prepared, claim, held):
    if type(claim) is not approval._ClaimedExactHumanApproval:
        raise GitTerminalStoreError()
    frozen = writer._freeze_validated_prepared(prepared)
    _held(frozen, held)
    reference = claim.public_reference()
    authority = exact.ExactOperationApprovalAuthority.from_reference(reference)
    execution = exact.exact_operation_execution_sha256(frozen.manifest, approval_authority=authority)
    return frozen, reference, execution


def _directory(root):
    current = root
    for part in RECEIPT_ROOT:
        current = current / part
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            return None
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or exact._path_is_reparse(info):
            raise GitTerminalStoreError("work_session_git_terminal_store_path_unsafe")
    return current


def _encode(record):
    basis = {"schema": ENVELOPE_SCHEMA, "terminal_record": record._document()}
    raw = writer._canonical({**basis, "receipt_sha256": writer._sha256_json(basis)}) + b"\n"
    if len(raw) > MAX_ENVELOPE_BYTES:
        raise GitTerminalStoreError()
    return raw


def _decode(raw, prepared, reference, execution):
    if type(raw) is not bytes or not raw or len(raw) > MAX_ENVELOPE_BYTES:
        raise GitTerminalStoreError()
    document = writer._strict_json(raw)
    if document.get("schema") == writer.GIT_BACKUP_DOMAIN_RECEIPT_SCHEMA:
        raise GitTerminalStoreError("work_session_git_terminal_store_conflict")
    if (set(document) != {"schema", "terminal_record", "receipt_sha256"}
            or document["schema"] != ENVELOPE_SCHEMA
            or not terminal._is_digest(document["receipt_sha256"])
            or writer._canonical(document) + b"\n" != raw
            or document["receipt_sha256"] != writer._sha256_json({
                name: value for name, value in document.items() if name != "receipt_sha256"
            })):
        raise GitTerminalStoreError()
    record = terminal._GitTerminalRecord(terminal._canonical(document["terminal_record"]))
    payload = record._document()["payload"]
    if (payload["manifest_sha256"] != prepared.manifest.manifest_sha256
            or payload["execution_sha256"] != execution
            or payload["approval_reference"] != reference):
        raise GitTerminalStoreError("work_session_git_terminal_store_changed")
    return record


def _read(prepared, reference, execution):
    directory = _directory(prepared.root)
    if directory is None:
        raise GitTerminalStoreError("work_session_git_terminal_store_missing")
    missing = False
    try:
        raw = controls._read_control(directory / (execution[7:] + ".json"), maximum=MAX_ENVELOPE_BYTES)
    except FileNotFoundError:
        missing = True
    if missing:
        raise GitTerminalStoreError("work_session_git_terminal_store_missing")
    return raw, _decode(raw, prepared, reference, execution)


def _load_git_terminal_record_held(prepared, *, claim, held) -> terminal._GitTerminalRecord:
    """Select by the exact claim reference; return data, not authentication."""
    def load():
        frozen, reference, execution = _selector(prepared, claim, held)
        raw, record = _read(frozen, reference, execution)
        if _selector(frozen, claim, held)[1:] != (reference, execution):
            raise GitTerminalStoreError("work_session_git_terminal_store_changed")
        if _read(frozen, reference, execution)[0] != raw:
            raise GitTerminalStoreError("work_session_git_terminal_store_changed")
        _held(frozen, held)
        return record
    return _safe_call(load)


def _guard(prepared, context, claim, record, reference, held):
    _held(prepared, held)
    failed = False
    try:
        if claim.assert_ready_for_context(context) != reference:
            raise ValueError()
        verified = terminal._authenticate_git_terminal_record_with_claim(
            prepared, context=context, record=record, claim=claim,
        )
        if verified._record._raw != record._raw or claim.assert_ready_for_context(context) != reference:
            raise ValueError()
    except Exception:
        failed = True
    if failed:
        raise GitTerminalStoreError("work_session_git_terminal_store_authentication_invalid")
    _held(prepared, held)


def _flush_receipt_chain(root):
    """Persist the fixed leaf-to-root directory entries without a scan.

    The generic exact-directory creator cannot promise Windows parent fsync.
    Retain each real parent, flush child then owner through the archive root,
    and reject identity drift or unsupported durability instead of weakening it.
    """
    paths = [root]
    for part in RECEIPT_ROOT:
        paths.append(paths[-1] / part)
    with ExitStack() as stack:
        bindings = [stack.enter_context(durable._bound_directory_for_move(path)) for path in paths]
        for path, binding in reversed(list(zip(paths, bindings))):
            durable._assert_named_reservation_directory_identity(path, binding.identity)
            durable._require_directory_durable(path)
            durable._assert_named_reservation_directory_identity(path, binding.identity)
        for path, binding in zip(paths, bindings):
            durable._assert_named_reservation_directory_identity(path, binding.identity)


def _save_git_terminal_record_held(prepared, *, context, claim, record, held) -> terminal._GitTerminalRecord:
    """No signing, no replacement; repeat confirms durability and reauthenticates.

    Failures after publication preserve the original bytes and report failure.
    A subsequent succeeded claim may load/verify, but cannot call this writer.
    """
    def save():
        if type(record) is not terminal._GitTerminalRecord:
            raise GitTerminalStoreError()
        detached = terminal._GitTerminalRecord(record._raw)
        frozen, reference, execution = _selector(prepared, claim, held)
        _guard(frozen, context, claim, detached, reference, held)
        raw = _encode(detached)
        _decode(raw, frozen, reference, execution)
        directory = _directory(frozen.root)
        if directory is not None and os.path.lexists(directory / (execution[7:] + ".json")):
            existing_raw, _existing = _read(frozen, reference, execution)
            if existing_raw != raw:
                raise GitTerminalStoreError("work_session_git_terminal_store_conflict")
            failed = False
            try:
                with durable._bound_directory_for_move(directory) as parent:
                    _flush_receipt_chain(frozen.root)
                    durable._assert_named_reservation_directory_identity(directory, parent.identity)
            except Exception:
                failed = True
            if failed:
                raise GitTerminalStoreError("work_session_git_terminal_store_durability_unknown")
        else:
            failed = False
            try:
                directory = exact._ensure_private_directory(frozen.root, RECEIPT_ROOT)
                with durable._bound_directory_for_move(directory) as parent:
                    _flush_receipt_chain(frozen.root)
                    pending = directory / (".pending_" + uuid.uuid4().hex)
                    destination = directory / (execution[7:] + ".json")
                    registry._write_private_pending(pending, raw, root=frozen.root)
                    durable._require_directory_durable(directory)
                    if controls._read_control(pending, maximum=MAX_ENVELOPE_BYTES) != raw:
                        raise GitTerminalStoreError("work_session_git_terminal_store_changed")
                    _guard(frozen, context, claim, detached, reference, held)
                    durable._assert_named_reservation_directory_identity(directory, parent.identity)
                    durable._atomic_move_file_no_replace(pending, destination, expected_parent_identity=parent.identity)
                    durable._require_directory_durable(directory)
                    durable._assert_named_reservation_directory_identity(directory, parent.identity)
            except GitTerminalStoreError:
                raise
            except Exception:
                failed = True
            if failed:
                raise GitTerminalStoreError("work_session_git_terminal_store_durability_unknown")
        # Read AFTER the durability flush, including identical-repeat recovery.
        confirmed_raw, confirmed = _read(frozen, reference, execution)
        if confirmed_raw != raw:
            raise GitTerminalStoreError("work_session_git_terminal_store_changed")
        _guard(frozen, context, claim, confirmed, reference, held)
        if _read(frozen, reference, execution)[0] != raw:
            raise GitTerminalStoreError("work_session_git_terminal_store_changed")
        _held(frozen, held)
        return confirmed
    return _safe_call(save)
