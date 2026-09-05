"""Authenticated control plane for one legacy project-update handoff.

This module deliberately owns no project-domain writer.  It records and
reconciles only the reversible control effects required to replace an
``approval_bound`` legacy transaction with a freshly approved current-schema
transaction.  Every public exception is a fixed, path-free reason code.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import stat
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterator, Mapping


RECOVERY_INTENT_SCHEMA = (
    "wom-kit/project-update-legacy-prewrite-recovery-intent/v0.4.19"
)
FRESH_APPROVAL_SEED_SCHEMA = (
    "wom-kit/project-update-legacy-fresh-approval-seed/v0.4.19"
)
RECOVERY_CHECKPOINT_SCHEMA = (
    "wom-kit/project-update-legacy-prewrite-recovery-checkpoint/v0.4.19"
)
ACTIVE_LOCATOR_SCHEMA = (
    "wom-kit/project-update-legacy-prewrite-active-locator/v0.4.19"
)
PROSPECTIVE_PLAN_SCHEMA = (
    "wom-kit/project-update-legacy-prospective-plan/v0.4.19"
)
FRESH_RESERVATION_SCHEMA = (
    "wom-kit/project-update-legacy-fresh-reservation/v0.4.19"
)
FRESH_ALLOCATION_SCHEMA = (
    "wom-kit/project-update-legacy-fresh-allocation/v0.4.19"
)
TERMINAL_RECEIPT_SCHEMA = (
    "wom-kit/project-update-legacy-terminal-receipt/v0.4.19"
)
CANCELLATION_RESULT_RECORD_SCHEMA = (
    "wom-kit/project-update-legacy-cancellation-result-record/v0.4.19"
)
CANCELLATION_RESULT_SCHEMA = (
    "wom-kit/project-version-update-legacy-recovery-result/v0.4.19"
)
CANCELLATION_TERMINAL_FINALIZATION_SCHEMA = (
    "wom-kit/project-version-update-cancellation-terminal-finalization/v0.4.19"
)
CANCELLATION_TERMINAL_HANDOFF_SCHEMA = (
    "wom-kit/project-version-update-cancellation-terminal-handoff/v0.4.19"
)
CANCELLATION_TERMINAL_PAYLOAD_SCHEMA = (
    "wom-kit/project-version-update-cancellation-terminal-payload/v0.4.19"
)
CANCELLATION_TERMINAL_DELIVERY_CAPABILITY_SCHEMA = (
    "wom-kit/project-version-update-cancellation-terminal-"
    "delivery-capability/v0.4.19"
)
CANCELLATION_PLAN_SCHEMA = (
    "wom-kit/project-update-legacy-cancellation-plan/v0.4.19"
)
CANCELLATION_STAGE_EVIDENCE_SCHEMA = (
    "wom-kit/project-update-legacy-cancellation-stage-evidence/v0.4.19"
)
CANCELLATION_CLEANUP_EVIDENCE_SCHEMA = (
    "wom-kit/project-update-legacy-cancellation-cleanup-evidence/v0.4.19"
)
CANCELLATION_RESTORE_EVIDENCE_SCHEMA = (
    "wom-kit/project-update-legacy-cancellation-restore-evidence/v0.4.19"
)
FRESH_TRANSACTION_INVENTORY_INDEX_SCHEMA = (
    "wom-kit/project-update-legacy-fresh-transaction-inventory-index/v0.4.19"
)
FRESH_TRANSACTION_INVENTORY_CHUNK_SCHEMA = (
    "wom-kit/project-update-legacy-fresh-transaction-inventory-chunk/v0.4.19"
)
PRE_FETCH_REF_SNAPSHOT_SCHEMA = (
    "wom-kit/project-update-legacy-pre-fetch-ref-snapshot/v0.4.19"
)
POST_FETCH_REF_SNAPSHOT_SCHEMA = (
    "wom-kit/project-update-legacy-post-fetch-ref-snapshot/v0.4.19"
)

RECOVERY_ROOT_LOGICAL = (
    ".zettel-kasten/private/version-update-legacy-recovery/recoveries"
)
ACTIVE_LOCATOR_LOGICAL = (
    ".zettel-kasten/private/version-update-terminal/legacy-prewrite-active.json"
)
TERMINAL_HANDOFF_LOGICAL = (
    ".zettel-kasten/private/version-update-terminal/active.json"
)
RECOVERY_GUARD_LOGICAL = (
    ".zettel-kasten/private/version-update-terminal/legacy-prewrite.guard"
)
TRANSACTION_ROOT_LOGICAL = ".zettel-kasten/private/version-updates"
LOCK_LOGICAL = ".zettel-kasten/version-update.lock"

_RECOVERY_REF_RE = re.compile(r"^recovery_[0-9a-f]{32}$")
_TRANSACTION_REF_RE = re.compile(r"^update_[0-9a-f]{32}$")
_SHA_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_STATE_RE = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
_TARGET_TAG_RE = re.compile(r"^v[0-9A-Za-z][0-9A-Za-z.+-]{0,79}$")
_MAX_DOCUMENT_BYTES = 1024 * 1024
_MAX_TREE_ENTRIES = 200_000
_MAX_TREE_BYTES = 4 * 1024 * 1024 * 1024
_MAX_TREE_DEPTH = 256
_MAX_INVENTORY_CHUNK_RECORDS = 1_000
_TARGET_INVENTORY_CHUNK_BYTES = 512 * 1024
_MAX_INVENTORY_MANIFEST_BYTES = 256 * 1024 * 1024
_MAC_DOMAIN = b"wom-kit/project-update-legacy-recovery/mac/v0.4.19\0"
_DOCUMENT_DOMAIN = b"wom-kit/project-update-legacy-recovery/document/v0.4.19\0"
_CHECKPOINT_LOCATOR_STATE = {
    "legacy_eligibility_verified": "legacy_eligible",
    "old_transaction_staged": "old_transaction_staged",
    "fresh_transaction_allocated": "fresh_transaction_allocated",
    "fresh_reservation_bound": "fresh_reservation_bound",
    "fresh_plan_sealed": "fresh_plan_sealed",
    "fresh_lock_backlinked": "fresh_lock_backlinked",
    "fresh_transaction_completed": "fresh_transaction_completed",
    "cancelled_fresh_staged": "cancelled_fresh_staged",
    "cancelled_fresh_cleaned": "cancelled_fresh_cleaned",
    "unapproved_restored": "unapproved_restored",
}
_ALLOWED_LOCATOR_FORWARD_TRANSITIONS = frozenset(
    {
        ("intent_sealed", "legacy_eligibility_verified"),
        ("legacy_eligible", "old_transaction_staged"),
        ("old_transaction_staged", "fresh_transaction_allocated"),
        ("fresh_transaction_allocated", "fresh_reservation_bound"),
        ("fresh_reservation_bound", "fresh_plan_sealed"),
        ("fresh_plan_sealed", "fresh_lock_backlinked"),
        ("fresh_plan_sealed", "cancelled_fresh_staged"),
        ("fresh_lock_backlinked", "fresh_transaction_completed"),
        ("cancelled_fresh_staged", "cancelled_fresh_cleaned"),
        ("cancelled_fresh_cleaned", "unapproved_restored"),
    }
)

PUBLIC_FAILURE_CODES = frozenset(
    {
        "project_update_legacy_recovery_binding_invalid",
        "project_update_legacy_recovery_key_invalid",
        "project_update_legacy_recovery_path_unsafe",
        "project_update_legacy_recovery_platform_unsupported",
        "project_update_legacy_recovery_state_changed",
        "project_update_legacy_recovery_state_ambiguous",
        "project_update_legacy_recovery_authentication_invalid",
        "project_update_legacy_recovery_commit_failed",
        "project_update_legacy_recovery_guard_unavailable",
        "project_update_legacy_recovery_lock_replace_unavailable",
        "project_update_legacy_recovery_lock_replace_ambiguous",
    }
)


class LegacyProjectUpdateRecoveryError(RuntimeError):
    """One fixed, privacy-safe recovery failure."""

    _CODES = PUBLIC_FAILURE_CODES

    def __init__(self, code: str) -> None:
        selected = (
            code
            if code in self._CODES
            else "project_update_legacy_recovery_state_ambiguous"
        )
        self.code = selected
        super().__init__(selected)


def _fail(code: str) -> LegacyProjectUpdateRecoveryError:
    return LegacyProjectUpdateRecoveryError(code)


def _checkpoint_chain_state(
    checkpoints: Iterator[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
) -> str:
    """Return the exact locator state for one valid full checkpoint prefix."""

    state = "intent_sealed"
    seen: set[str] = set()
    for checkpoint in checkpoints:
        phase = checkpoint.get("phase")
        if (
            type(phase) is not str
            or phase in seen
            or checkpoint.get("stage") != "verified"
            or (state, phase) not in _ALLOWED_LOCATOR_FORWARD_TRANSITIONS
        ):
            raise _fail("project_update_legacy_recovery_state_changed")
        seen.add(phase)
        state = _CHECKPOINT_LOCATOR_STATE[phase]
    return state


def _canonical(value: Mapping[str, Any]) -> bytes:
    try:
        return (
            json.dumps(
                dict(value),
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise _fail("project_update_legacy_recovery_binding_invalid") from None


def sha256_bytes(raw: bytes) -> str:
    if type(raw) is not bytes:
        raise _fail("project_update_legacy_recovery_binding_invalid")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def sha256_document(value: Mapping[str, Any]) -> str:
    return sha256_bytes(_canonical(value))


def _transaction_semantic_sha256(value: Mapping[str, Any]) -> str:
    """Match the project-update transaction semantic-document digest.

    Recovery control documents bind their complete on-disk bytes, including
    the canonical trailing newline.  The three semantic evidence slots in the
    terminal receipt instead use the transaction layer's canonical JSON bytes
    without that storage newline.  Keeping this helper narrow prevents those
    two deliberately distinct digest domains from being interchanged.
    """

    canonical_storage = _canonical(value)
    if not canonical_storage.endswith(b"\n"):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    return sha256_bytes(canonical_storage[:-1])


def _cancellation_delivery_payload_sha256(
    value: Mapping[str, Any],
) -> str:
    """Digest the public cancellation payload in its delivery domain.

    The terminal handoff does not bind the on-disk cancellation-result
    document.  It binds the content-free public result projection used by the
    project-update transaction layer, whose canonical JSON omits the storage
    newline.  Keep that semantic digest separate from both the authenticated
    handoff MAC and the create-only recovery-document digest.
    """

    canonical_storage = _canonical(value)
    if not canonical_storage.endswith(b"\n"):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    return sha256_bytes(canonical_storage[:-1])


def _validated_key(value: bytes | bytearray | memoryview) -> bytearray:
    try:
        raw = bytes(value)
    except (TypeError, ValueError):
        raise _fail("project_update_legacy_recovery_key_invalid") from None
    if len(raw) != 32:
        raise _fail("project_update_legacy_recovery_key_invalid")
    return bytearray(raw)


def _payload(document: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(document)
    result.pop("authentication", None)
    return result


def authenticated_document(
    document: Mapping[str, Any],
    key: bytes | bytearray | memoryview,
) -> dict[str, Any]:
    secret = _validated_key(key)
    try:
        payload = _payload(document)
        result = dict(payload)
        result["authentication"] = {
            "algorithm": "hmac-sha256",
            "mac": "hmac-sha256:"
            + hmac.new(
                secret,
                _MAC_DOMAIN + _canonical(payload),
                hashlib.sha256,
            ).hexdigest(),
        }
        return result
    finally:
        for index in range(len(secret)):
            secret[index] = 0


def verify_authenticated_document(
    document: Mapping[str, Any],
    key: bytes | bytearray | memoryview,
) -> dict[str, Any]:
    if not isinstance(document, Mapping):
        raise _fail("project_update_legacy_recovery_authentication_invalid")
    auth = document.get("authentication")
    if (
        not isinstance(auth, Mapping)
        or set(auth) != {"algorithm", "mac"}
        or auth.get("algorithm") != "hmac-sha256"
        or not isinstance(auth.get("mac"), str)
        or re.fullmatch(r"hmac-sha256:[0-9a-f]{64}", auth["mac"]) is None
    ):
        raise _fail("project_update_legacy_recovery_authentication_invalid")
    expected = authenticated_document(_payload(document), key)
    if not hmac.compare_digest(
        str(auth["mac"]), str(expected["authentication"]["mac"])
    ):
        raise _fail("project_update_legacy_recovery_authentication_invalid")
    return _payload(document)


def _is_reparse(info: os.stat_result) -> bool:
    return bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _safe_directory(path: Path) -> os.stat_result:
    try:
        info = os.lstat(path)
    except LegacyProjectUpdateRecoveryError:
        raise
    except BaseException:
        raise _fail("project_update_legacy_recovery_path_unsafe") from None
    if (
        not stat.S_ISDIR(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or _is_reparse(info)
    ):
        raise _fail("project_update_legacy_recovery_path_unsafe")
    return info


@contextmanager
def _retained_directory(
    path: Path,
    *,
    expected_identity: tuple[int, int] | None = None,
) -> Iterator[os.stat_result]:
    """Retain one real directory while its entries are observed.

    A fresh guard is used for each DFS frame.  Its parent frame remains open
    during recursion, so a queued child is opened and identity-checked before
    control can advance to a sibling.  Peak handles are therefore bounded by
    tree depth instead of total entry count.  On Windows the shared Win32
    guard opens with ``OPEN_REPARSE_POINT`` and omits ``FILE_SHARE_DELETE``;
    non-Windows retains the existing fail-closed lstat checks only.
    """

    candidate = Path(os.path.abspath(str(path)))
    before = _safe_directory(candidate)
    before_identity = (int(before.st_dev), int(before.st_ino))
    if expected_identity is not None and before_identity != expected_identity:
        raise _fail("project_update_legacy_recovery_state_changed")
    guard: Any = None
    if os.name == "nt":
        try:
            from . import private_metadata_win32

            guard = (
                private_metadata_win32._PrivateMetadataMutationGuard
                ._for_low_level_ntfs_probe(candidate)
            )
            guard.validate_all()
            held = _safe_directory(candidate)
        except BaseException:
            if guard is not None:
                try:
                    guard.terminal_release_after_failure()
                except BaseException:
                    pass
            raise _fail("project_update_legacy_recovery_path_unsafe") from None
        if (int(held.st_dev), int(held.st_ino)) != before_identity:
            try:
                guard.close()
            except BaseException:
                pass
            raise _fail("project_update_legacy_recovery_state_changed")
    else:
        held = before
    try:
        yield held
        after = _safe_directory(candidate)
        if (int(after.st_dev), int(after.st_ino)) != before_identity:
            raise _fail("project_update_legacy_recovery_state_changed")
        if guard is not None:
            try:
                guard.validate_all()
            except BaseException:
                raise _fail(
                    "project_update_legacy_recovery_state_changed"
                ) from None
    finally:
        if guard is not None:
            try:
                guard.close()
            except BaseException:
                try:
                    guard.terminal_release_after_failure()
                except BaseException:
                    pass
                raise _fail(
                    "project_update_legacy_recovery_state_ambiguous"
                ) from None


@contextmanager
def _retained_parent_chains(
    project_root: Path,
    *parents: Path,
) -> Iterator[None]:
    """Retain every real ancestor from project root through target parents."""

    root = Path(os.path.abspath(str(project_root)))
    requested: dict[str, Path] = {}
    for supplied in parents:
        parent = Path(os.path.abspath(str(supplied)))
        try:
            relative = parent.relative_to(root)
        except ValueError:
            raise _fail("project_update_legacy_recovery_path_unsafe") from None
        current = root
        requested[os.path.normcase(str(current))] = current
        for part in relative.parts:
            current = current / part
            requested[os.path.normcase(str(current))] = current
    ordered = sorted(
        requested.values(),
        key=lambda item: (len(item.parts), os.path.normcase(str(item))),
    )
    with ExitStack() as stack:
        for directory in ordered:
            stack.enter_context(_retained_directory(directory))
        yield


def _safe_regular(path: Path, *, maximum: int = _MAX_DOCUMENT_BYTES) -> os.stat_result:
    try:
        info = os.lstat(path)
    except OSError:
        raise _fail("project_update_legacy_recovery_path_unsafe") from None
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or _is_reparse(info)
        or int(info.st_nlink) != 1
        or int(info.st_size) < 0
        or int(info.st_size) > maximum
    ):
        raise _fail("project_update_legacy_recovery_path_unsafe")
    return info


def _read_regular(path: Path, *, maximum: int = _MAX_DOCUMENT_BYTES) -> bytes:
    before = _safe_regular(path, maximum=maximum)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        raise _fail("project_update_legacy_recovery_path_unsafe") from None
    try:
        opened = os.fstat(descriptor)
        if (
            (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
            or not stat.S_ISREG(opened.st_mode)
            or int(opened.st_nlink) != 1
            or int(opened.st_size) > maximum
        ):
            raise _fail("project_update_legacy_recovery_state_changed")
        remaining = int(opened.st_size)
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(descriptor, min(remaining, 65536))
            if not chunk:
                raise _fail("project_update_legacy_recovery_state_changed")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise _fail("project_update_legacy_recovery_state_changed")
        if os.name == "nt":
            import msvcrt
            from . import legacy_cleanup_bound_delete

            legacy_cleanup_bound_delete._reject_windows_alternate_streams(
                msvcrt.get_osfhandle(descriptor),
                directory=False,
            )
        after = os.fstat(descriptor)
    except LegacyProjectUpdateRecoveryError:
        raise
    except BaseException:
        raise _fail("project_update_legacy_recovery_path_unsafe") from None
    finally:
        os.close(descriptor)
    named = _safe_regular(path, maximum=maximum)
    if (
        (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        or (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino)
    ):
        raise _fail("project_update_legacy_recovery_state_changed")
    return b"".join(chunks)


def _hash_regular(
    path: Path,
    *,
    maximum: int,
) -> tuple[str, int, tuple[int, int], int]:
    """Hash one stable single-link file without retaining its bytes."""

    before = _safe_regular(path, maximum=maximum)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if (
            (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
            or not stat.S_ISREG(opened.st_mode)
            or int(opened.st_nlink) != 1
            or int(opened.st_size) < 0
            or int(opened.st_size) > maximum
        ):
            raise _fail("project_update_legacy_recovery_state_changed")
        digest = hashlib.sha256()
        remaining = int(opened.st_size)
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1024 * 1024))
            if not chunk:
                raise _fail("project_update_legacy_recovery_state_changed")
            digest.update(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise _fail("project_update_legacy_recovery_state_changed")
        if os.name == "nt":
            import msvcrt
            from . import legacy_cleanup_bound_delete

            legacy_cleanup_bound_delete._reject_windows_alternate_streams(
                msvcrt.get_osfhandle(descriptor),
                directory=False,
            )
        after = os.fstat(descriptor)
    except LegacyProjectUpdateRecoveryError:
        raise
    except BaseException:
        raise _fail("project_update_legacy_recovery_path_unsafe") from None
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
    named = _safe_regular(path, maximum=maximum)
    if (
        (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        or (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino)
    ):
        raise _fail("project_update_legacy_recovery_state_changed")
    return (
        "sha256:" + digest.hexdigest(),
        int(opened.st_size),
        (int(opened.st_dev), int(opened.st_ino)),
        int(opened.st_mtime_ns),
    )


def _fsync_directory(path: Path) -> None:
    # Reuse the transaction layer's Windows CreateFileW +
    # FlushFileBuffers implementation.  A best-effort directory fsync is not
    # sufficient here: every locator, journal, move, and lock-handoff
    # checkpoint depends on the parent namespace being durably committed.
    try:
        from . import project_update_transaction

        project_update_transaction._require_directory_durable(path)
    except BaseException:
        raise _fail("project_update_legacy_recovery_commit_failed") from None


def _control_project_root(path: Path) -> Path:
    """Return the lexical project root for a private control-plane leaf."""

    candidate = Path(os.path.abspath(str(path)))
    for parent in candidate.parents:
        if parent.name == ".zettel-kasten":
            return parent.parent
    # Low-level isolated tests and the public lock primitive may provide a
    # sibling-only fixture.  Retain that exact parent rather than silently
    # walking an unrelated ancestor chain.
    return candidate.parent


def _write_new(
    path: Path,
    raw: bytes,
    *,
    _failpoint: Callable[[str, Path], None] | None = None,
) -> None:
    """Publish complete bytes create-only; a final name is never partial.

    Windows writes through a retained delete-on-close temporary handle.  The
    same exact handle is flushed, re-read, renamed without replacement, and
    made durable before delete-on-close is cancelled.  No error path unlinks a
    name, so a raced replacement can never be mistaken for our temporary.
    """

    if type(raw) is not bytes or not callable(_failpoint) and _failpoint is not None:
        raise _fail("project_update_legacy_recovery_binding_invalid")
    target = Path(os.path.abspath(str(path)))
    project_root = _control_project_root(target)
    try:
        if os.path.lexists(target):
            if hmac.compare_digest(
                _read_regular(target, maximum=max(len(raw), 1)), raw
            ):
                return
            raise _fail("project_update_legacy_recovery_state_changed")
        if os.name != "nt":
            # POSIX test/development hosts use a complete temporary plus an
            # atomic hard-link create.  Apply remains Windows-only elsewhere.
            temporary = target.with_name(
                f".{target.name}.{secrets.token_hex(16)}.wom-publish"
            )
            descriptor: int | None = None
            try:
                descriptor = os.open(
                    temporary,
                    os.O_RDWR | os.O_CREAT | os.O_EXCL,
                    0o600,
                )
                offset = 0
                while offset < len(raw):
                    written = os.write(descriptor, raw[offset : offset + 65536])
                    if written <= 0:
                        raise OSError("write_incomplete")
                    offset += written
                os.fsync(descriptor)
                os.lseek(descriptor, 0, os.SEEK_SET)
                observed = b""
                while len(observed) < len(raw):
                    chunk = os.read(descriptor, len(raw) - len(observed))
                    if not chunk:
                        raise OSError("read_incomplete")
                    observed += chunk
                if os.read(descriptor, 1) or not hmac.compare_digest(observed, raw):
                    raise OSError("bytes_changed")
                if _failpoint is not None:
                    _failpoint("publish_temp_flushed_and_bound", temporary)
                os.link(temporary, target, follow_symlinks=False)
                _fsync_directory(target.parent)
                if _failpoint is not None:
                    _failpoint("publish_target_durable", target)
                # The retained descriptor still identifies our inode.  POSIX
                # unlink has no compare-and-delete primitive, so only remove
                # the temp while its current name remains that exact inode.
                named = os.lstat(temporary)
                opened = os.fstat(descriptor)
                if (int(named.st_dev), int(named.st_ino)) != (
                    int(opened.st_dev),
                    int(opened.st_ino),
                ):
                    raise OSError("temporary_name_changed")
                os.unlink(temporary)
                _fsync_directory(target.parent)
            finally:
                if descriptor is not None:
                    os.close(descriptor)
            if not hmac.compare_digest(
                _read_regular(target, maximum=max(len(raw), 1)), raw
            ):
                raise OSError("publish_unproved")
            return

        import ctypes
        import msvcrt
        from ctypes import wintypes
        from . import private_metadata_win32

        class FileDispositionInformationEx(ctypes.Structure):
            _fields_ = [("Flags", wintypes.DWORD)]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_file = kernel32.CreateFileW
        create_file.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        create_file.restype = wintypes.HANDLE
        set_information = kernel32.SetFileInformationByHandle
        set_information.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        set_information.restype = wintypes.BOOL
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL
        invalid_handle = wintypes.HANDLE(-1).value
        descriptor = None
        raw_handle: int | None = None
        temporary: Path | None = None
        with _retained_parent_chains(project_root, target.parent):
            for _ in range(8):
                candidate = target.with_name(
                    f".{target.name}.{secrets.token_hex(16)}.wom-publish"
                )
                ctypes.set_last_error(0)
                handle = create_file(
                    str(candidate),
                    0x80000000 | 0x40000000 | 0x00010000,
                    0x00000001,
                    None,
                    1,
                    0x00000080 | 0x04000000,
                    None,
                )
                value = handle if isinstance(handle, int) else getattr(handle, "value", None)
                if value not in {None, invalid_handle}:
                    raw_handle = int(value)
                    temporary = candidate
                    break
                if ctypes.get_last_error() not in {80, 183}:
                    raise OSError("temporary_create_failed")
            if raw_handle is None or temporary is None:
                raise OSError("temporary_name_exhausted")
            try:
                descriptor = msvcrt.open_osfhandle(
                    raw_handle,
                    os.O_RDWR | getattr(os, "O_BINARY", 0),
                )
                raw_handle = msvcrt.get_osfhandle(descriptor)
                offset = 0
                while offset < len(raw):
                    written = os.write(descriptor, raw[offset : offset + 65536])
                    if written <= 0:
                        raise OSError("write_incomplete")
                    offset += written
                os.fsync(descriptor)

                def exact_binding(named_path: Path) -> tuple[int, int, int, int, str]:
                    before = os.fstat(descriptor)
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    digest = hashlib.sha256()
                    remaining = len(raw)
                    while remaining:
                        chunk = os.read(descriptor, min(remaining, 1024 * 1024))
                        if not chunk:
                            raise OSError("read_incomplete")
                        digest.update(chunk)
                        remaining -= len(chunk)
                    if os.read(descriptor, 1):
                        raise OSError("read_overflow")
                    after = os.fstat(descriptor)
                    named = os.lstat(named_path)
                    binding = (
                        int(before.st_dev),
                        int(before.st_ino),
                        int(before.st_size),
                        int(before.st_mtime_ns),
                        digest.hexdigest(),
                    )
                    if (
                        binding[:4]
                        != (
                            int(after.st_dev), int(after.st_ino),
                            int(after.st_size), int(after.st_mtime_ns),
                        )
                        or binding[:2] != (int(named.st_dev), int(named.st_ino))
                        or int(named.st_nlink) != 1
                        or binding[2] != len(raw)
                        or binding[4] != hashlib.sha256(raw).hexdigest()
                        or stat.S_ISLNK(named.st_mode)
                        or _is_reparse(named)
                    ):
                        raise OSError("binding_changed")
                    return binding

                creation = exact_binding(temporary)
                if _failpoint is not None:
                    _failpoint("publish_temp_flushed_and_bound", temporary)
                rename = private_metadata_win32.file_rename_info_buffer(
                    target,
                    replace_if_exists=False,
                )
                if not set_information(
                    raw_handle, 3, rename.backing, rename.api_buffer_size
                ):
                    raise OSError("rename_failed")
                if exact_binding(target) != creation:
                    raise OSError("postrename_changed")
                _fsync_directory(target.parent)
                if _failpoint is not None:
                    _failpoint("publish_target_durable", target)
                keep = FileDispositionInformationEx(0x00000008)
                if not set_information(
                    raw_handle,
                    21,
                    ctypes.byref(keep),
                    ctypes.sizeof(keep),
                ):
                    raise OSError("delete_on_close_cancel_failed")
                if exact_binding(target) != creation:
                    raise OSError("committed_binding_changed")
                if _failpoint is not None:
                    _failpoint("publish_delete_on_close_cancelled", target)
            finally:
                if descriptor is not None:
                    os.close(descriptor)
                elif raw_handle is not None:
                    close_handle(raw_handle)
        if not hmac.compare_digest(
            _read_regular(target, maximum=max(len(raw), 1)), raw
        ):
            raise OSError("publish_unproved")
    except LegacyProjectUpdateRecoveryError:
        raise
    except BaseException:
        # A concurrent exact publication is idempotent.  Every other state is
        # fixed/path-free and is preserved for inspection.
        try:
            if os.path.lexists(target) and hmac.compare_digest(
                _read_regular(target, maximum=max(len(raw), 1)), raw
            ):
                return
        except BaseException:
            pass
        raise _fail("project_update_legacy_recovery_commit_failed") from None


def _parse_json(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("ascii"), object_pairs_hook=_unique_pairs)
    except (UnicodeError, ValueError, json.JSONDecodeError):
        raise _fail("project_update_legacy_recovery_binding_invalid") from None
    if not isinstance(value, dict):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    return value


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate")
        result[key] = value
    return result


@dataclass(frozen=True)
class RecoveryPaths:
    project_root: Path
    recovery_ref: str
    recovery_root: Path
    locator_path: Path
    guard_path: Path
    old_transaction_vault: Path
    cancelled_fresh_transaction_vault: Path

    @classmethod
    def build(cls, project_root: Path | str, recovery_ref: str) -> "RecoveryPaths":
        project = Path(os.path.abspath(str(project_root)))
        if _RECOVERY_REF_RE.fullmatch(str(recovery_ref)) is None:
            raise _fail("project_update_legacy_recovery_binding_invalid")
        _safe_directory(project)
        recovery_root = project.joinpath(
            *PurePosixPath(RECOVERY_ROOT_LOGICAL).parts,
            recovery_ref,
        )
        return cls(
            project_root=project,
            recovery_ref=recovery_ref,
            recovery_root=recovery_root,
            locator_path=project.joinpath(
                *PurePosixPath(ACTIVE_LOCATOR_LOGICAL).parts
            ),
            guard_path=project.joinpath(
                *PurePosixPath(RECOVERY_GUARD_LOGICAL).parts
            ),
            old_transaction_vault=recovery_root / "old-transaction",
            cancelled_fresh_transaction_vault=(
                recovery_root / "cancelled-fresh-transaction"
            ),
        )


@contextmanager
def legacy_recovery_process_guard(
    project_root: Path | str,
    *,
    terminal_control_lease_held: Callable[[], bool],
) -> Iterator[Path]:
    """Serialize legacy recovery in one project with a crash-released lock.

    Global ordering is **terminal-control lease before recovery guard**.  The
    caller supplies a side-effect-free verifier for that already-held lease;
    this primitive never acquires the terminal lock itself.  The persistent
    zero-byte guard is only a rendezvous name.  Ownership is
    the live OS handle: process termination releases it automatically, while
    a stale file alone grants no ownership and needs no TTL-based stealing.
    """

    if not callable(terminal_control_lease_held):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    try:
        terminal_held = terminal_control_lease_held()
    except BaseException:
        raise _fail("project_update_legacy_recovery_state_ambiguous") from None
    if type(terminal_held) is not bool or not terminal_held:
        raise _fail("project_update_legacy_recovery_state_ambiguous")
    project = Path(os.path.abspath(str(project_root)))
    _safe_directory(project)
    guard = project.joinpath(*PurePosixPath(RECOVERY_GUARD_LOGICAL).parts)
    _safe_directory(guard.parent)
    descriptor: int | None = None
    raw_handle: int | None = None
    if os.name == "nt":
        import ctypes
        import msvcrt
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_file = kernel32.CreateFileW
        create_file.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        create_file.restype = wintypes.HANDLE
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL
        invalid_handle = wintypes.HANDLE(-1).value
        parent_stack = ExitStack()
        try:
            parent_stack.enter_context(
                _retained_parent_chains(project, guard.parent)
            )
            handle = create_file(
                str(guard),
                0x80000000 | 0x40000000,
                0x00000001,
                None,
                4,
                0x00000080 | 0x00200000,
                None,
            )
            value = (
                handle
                if isinstance(handle, int)
                else getattr(handle, "value", None)
            )
            if value in {None, invalid_handle}:
                raise OSError("guard_open_failed")
            raw_handle = int(value)
            descriptor = msvcrt.open_osfhandle(
                raw_handle,
                os.O_RDWR | getattr(os, "O_BINARY", 0),
            )
            raw_handle = None
            opened = os.fstat(descriptor)
            named = _safe_regular(guard, maximum=0)
            if (
                int(opened.st_size) != 0
                or int(opened.st_nlink) != 1
                or (int(opened.st_dev), int(opened.st_ino))
                != (int(named.st_dev), int(named.st_ino))
            ):
                raise OSError("guard_binding_failed")
            _fsync_directory(guard.parent)
        except BaseException:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
                descriptor = None
            elif raw_handle is not None:
                close_handle(raw_handle)
                raw_handle = None
            parent_stack.close()
            raise _fail(
                "project_update_legacy_recovery_guard_unavailable"
            ) from None
        try:
            yield guard
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    raise _fail(
                        "project_update_legacy_recovery_state_ambiguous"
                    ) from None
            elif raw_handle is not None:
                if not close_handle(raw_handle):
                    raise _fail(
                        "project_update_legacy_recovery_state_ambiguous"
                    ) from None
            parent_stack.close()
        return

    # The non-Windows branch exists for deterministic CI only; recovery apply
    # remains Windows-only.  flock still makes concurrency semantics honest.
    try:
        import fcntl

        descriptor = os.open(guard, os.O_RDWR | os.O_CREAT, 0o600)
        if os.fstat(descriptor).st_size != 0:
            raise OSError("guard_not_empty")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BaseException:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
            descriptor = None
        raise _fail("project_update_legacy_recovery_guard_unavailable") from None
    try:
        yield guard
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                raise _fail(
                    "project_update_legacy_recovery_state_ambiguous"
                ) from None


def new_recovery_ref() -> str:
    return "recovery_" + secrets.token_hex(16)


def fresh_approval_seed_document(
    *,
    recovery_ref: str,
    reviewer: str,
    old_transaction_ref: str,
    old_transaction_sha256: str,
    archive_identity_sha256: str,
    project_identity_sha256: str,
    requested_target_tag: str,
) -> dict[str, Any]:
    """Bind the raw reviewer inside the ignored authenticated private plane.

    The recovery intent records only the authenticated document digest.  This
    prevents the reviewer value from being copied into a locator, checkpoint,
    public result, or fixed error while still making a resumed approval use the
    exact original human context.
    """

    try:
        reviewer_bytes = reviewer.encode("utf-8")
    except (AttributeError, UnicodeError):
        raise _fail("project_update_legacy_recovery_binding_invalid") from None
    values = {
        "archive_identity_sha256": archive_identity_sha256,
        "old_transaction_ref": old_transaction_ref,
        "old_transaction_sha256": old_transaction_sha256,
        "project_identity_sha256": project_identity_sha256,
        "recovery_ref": recovery_ref,
        "requested_target_tag": requested_target_tag,
        "reviewer": reviewer,
        "schema": FRESH_APPROVAL_SEED_SCHEMA,
    }
    if (
        _RECOVERY_REF_RE.fullmatch(recovery_ref) is None
        or _TRANSACTION_REF_RE.fullmatch(old_transaction_ref) is None
        or not reviewer_bytes
        or len(reviewer_bytes) > 4096
        or reviewer.strip() == ""
        or _TARGET_TAG_RE.fullmatch(requested_target_tag) is None
        or any(
            _SHA_RE.fullmatch(str(value)) is None
            for name, value in values.items()
            if name.endswith("sha256")
        )
    ):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    return values


def recovery_intent_document(
    *,
    recovery_ref: str,
    old_transaction_ref: str,
    old_transaction_sha256: str,
    old_claim_sha256: str,
    old_lock_sha256: str,
    old_live_components_sha256: str,
    archive_identity_sha256: str,
    project_identity_sha256: str,
    fresh_approval_seed_document_sha256: str,
) -> dict[str, Any]:
    values = {
        "archive_identity_sha256": archive_identity_sha256,
        "fresh_approval_seed_document_sha256": (
            fresh_approval_seed_document_sha256
        ),
        "old_claim_sha256": old_claim_sha256,
        "old_live_components_sha256": old_live_components_sha256,
        "old_lock_sha256": old_lock_sha256,
        "old_transaction_ref": old_transaction_ref,
        "old_transaction_sha256": old_transaction_sha256,
        "project_identity_sha256": project_identity_sha256,
        "recovery_ref": recovery_ref,
        "schema": RECOVERY_INTENT_SCHEMA,
    }
    if (
        _RECOVERY_REF_RE.fullmatch(recovery_ref) is None
        or _TRANSACTION_REF_RE.fullmatch(old_transaction_ref) is None
        or any(_SHA_RE.fullmatch(str(values[name])) is None for name in values if name.endswith("sha256"))
    ):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    return values


def prospective_plan_document(
    *,
    recovery_ref: str,
    fresh_allocation_document_sha256: str,
    fresh_transaction_ref: str,
    fresh_intent_sha256: str,
    fresh_transaction_inventory_sha256: str,
    fresh_transaction_inventory_document_sha256: str,
    fresh_approval_plan_sha256: str,
    fresh_approval_target_binding_sha256: str,
    fresh_approval_context_sha256: str,
    fresh_recovery_binding_sha256: str,
    post_ref_snapshot_document_sha256: str,
    post_ref_snapshot_sha256: str,
    old_abandonment_sha256: str,
) -> dict[str, Any]:
    """Build the exact pre-approval plan sealed by one recovery."""

    values = {
        "fresh_allocation_document_sha256": (
            fresh_allocation_document_sha256
        ),
        "fresh_approval_plan_sha256": fresh_approval_plan_sha256,
        "fresh_approval_context_sha256": fresh_approval_context_sha256,
        "fresh_intent_sha256": fresh_intent_sha256,
        "fresh_approval_target_binding_sha256": (
            fresh_approval_target_binding_sha256
        ),
        "fresh_recovery_binding_sha256": fresh_recovery_binding_sha256,
        "fresh_transaction_inventory_sha256": (
            fresh_transaction_inventory_sha256
        ),
        "fresh_transaction_inventory_document_sha256": (
            fresh_transaction_inventory_document_sha256
        ),
        "fresh_transaction_ref": fresh_transaction_ref,
        "old_abandonment_sha256": old_abandonment_sha256,
        "post_ref_snapshot_document_sha256": (
            post_ref_snapshot_document_sha256
        ),
        "post_ref_snapshot_sha256": post_ref_snapshot_sha256,
        "recovery_ref": recovery_ref,
        "schema": PROSPECTIVE_PLAN_SCHEMA,
    }
    if (
        _RECOVERY_REF_RE.fullmatch(recovery_ref) is None
        or _TRANSACTION_REF_RE.fullmatch(fresh_transaction_ref) is None
        or any(
            _SHA_RE.fullmatch(str(value)) is None
            for name, value in values.items()
            if name.endswith("sha256")
        )
    ):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    return values


def fresh_reservation_document(
    *,
    recovery_ref: str,
    fresh_transaction_ref: str,
    fresh_reservation_sha256: str,
    fresh_allocation_document_sha256: str,
    old_abandonment_sha256: str,
) -> dict[str, Any]:
    values = {
        "fresh_allocation_document_sha256": (
            fresh_allocation_document_sha256
        ),
        "fresh_reservation_sha256": fresh_reservation_sha256,
        "fresh_transaction_ref": fresh_transaction_ref,
        "old_abandonment_sha256": old_abandonment_sha256,
        "recovery_ref": recovery_ref,
        "schema": FRESH_RESERVATION_SCHEMA,
    }
    if (
        _RECOVERY_REF_RE.fullmatch(recovery_ref) is None
        or _TRANSACTION_REF_RE.fullmatch(fresh_transaction_ref) is None
        or _SHA_RE.fullmatch(fresh_reservation_sha256) is None
        or _SHA_RE.fullmatch(fresh_allocation_document_sha256) is None
        or _SHA_RE.fullmatch(old_abandonment_sha256) is None
    ):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    return values


def fresh_allocation_document(
    *,
    recovery_ref: str,
    prepared_reservation_document: Mapping[str, Any],
    old_abandonment_sha256: str,
    pre_ref_snapshot_document_sha256: str,
    pre_ref_snapshot_sha256: str,
    transport_cache_policy: str = "retained_transport_cache",
) -> dict[str, Any]:
    """Bind the exact prepared reservation before it can create a directory."""

    try:
        from . import project_update_transaction

        prepared = project_update_transaction.ProjectUpdateReservation.from_document(
            dict(prepared_reservation_document)
        )
        exact_prepared_document = prepared.document()
        prepared_document_sha256 = prepared.sha256
    except BaseException:
        raise _fail("project_update_legacy_recovery_binding_invalid") from None

    values = {
        "fresh_created_at": prepared.created_at,
        "fresh_ownership_nonce": prepared.ownership_nonce,
        "fresh_transaction_ref": prepared.transaction_ref,
        "old_abandonment_sha256": old_abandonment_sha256,
        "prepared_reservation_document_sha256": prepared_document_sha256,
        "pre_ref_snapshot_document_sha256": (
            pre_ref_snapshot_document_sha256
        ),
        "pre_ref_snapshot_sha256": pre_ref_snapshot_sha256,
        "project_identity_sha256": prepared.project_identity_sha256,
        "recovery_ref": recovery_ref,
        "requested_target_tag": prepared.requested_target_tag,
        "schema": FRESH_ALLOCATION_SCHEMA,
        "transport_cache_policy": transport_cache_policy,
    }
    if (
        _RECOVERY_REF_RE.fullmatch(recovery_ref) is None
        or _SHA_RE.fullmatch(old_abandonment_sha256) is None
        or _SHA_RE.fullmatch(pre_ref_snapshot_document_sha256) is None
        or _SHA_RE.fullmatch(pre_ref_snapshot_sha256) is None
        or transport_cache_policy != "retained_transport_cache"
        or exact_prepared_document != dict(prepared_reservation_document)
    ):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    return values


def _prepared_reservation_from_allocation(
    allocation: Mapping[str, Any],
) -> Any:
    """Reconstruct and validate the exact prepared transaction authority."""

    try:
        from . import project_update_transaction

        fresh_ref = allocation["fresh_transaction_ref"]
        logical = f"{project_update_transaction.TRANSACTION_ROOT_LOGICAL}/{fresh_ref}"
        prepared = project_update_transaction.ProjectUpdateReservation(
            transaction_ref=fresh_ref,
            transaction_logical_ref=logical,
            project_identity_sha256=allocation["project_identity_sha256"],
            requested_target_tag=allocation["requested_target_tag"],
            ownership_nonce=allocation["fresh_ownership_nonce"],
            runtime_candidate_logical_ref=(
                f"{logical}/{project_update_transaction.RUNTIME_CANDIDATE_NAME}"
            ),
            runtime_candidate_seal_logical_ref=(
                f"{logical}/{project_update_transaction.RUNTIME_CANDIDATE_SEAL_NAME}"
            ),
            created_at=allocation["fresh_created_at"],
        )
        if prepared.sha256 != allocation.get(
            "prepared_reservation_document_sha256"
        ):
            raise ValueError("prepared_reservation_digest_changed")
        return prepared
    except BaseException:
        raise _fail("project_update_legacy_recovery_binding_invalid") from None


def cancellation_result_document() -> dict[str, Any]:
    """Return the single canonical content-free denial projection."""

    reason = "project_version_update_legacy_recovery_unapproved_restored"
    return {
        "approved": False,
        "blockers": [reason],
        "dry_run": False,
        "effects_state": "none",
        "files_written": [],
        "files_written_scope": "project_domain_only",
        "ok": False,
        "private_values_echoed": False,
        "project_domain_writes_performed": False,
        "reason_code": reason,
        "reason_codes": [reason],
        "schema": CANCELLATION_RESULT_SCHEMA,
        "state": "unapproved_restored",
        "status": "unapproved_restored",
        "terminal_finalization": {
            "automatic_retry_allowed": False,
            "claim_succeeded_verified": False,
            "domain_writer_entered": False,
            "durable_result_delivery_acknowledged": False,
            "durable_terminal_handoff_ready": True,
            "fresh_approval_granted": False,
            "fresh_transaction_retired": True,
            "old_lock_preserved": True,
            "old_transaction_restored": True,
            "outcome": "unapproved_restored",
            "private_identifiers_echoed": False,
            "private_paths_echoed": False,
            "schema": CANCELLATION_TERMINAL_FINALIZATION_SCHEMA,
        },
    }


def cancellation_plan_document(
    *,
    recovery_ref: str,
    intent_sha256: str,
    fresh_transaction_ref: str,
    prospective_plan_document_sha256: str,
    fresh_approval_plan_sha256: str,
    fresh_approval_context_sha256: str,
    claim_absence_evidence_sha256: str,
    old_transaction_ref: str,
    old_transaction_sha256: str,
    old_lock_sha256: str,
    old_abandonment_sha256: str,
    fresh_transaction_inventory_sha256: str,
    fresh_transaction_inventory_document_sha256: str,
    cancellation_result_sha256: str,
    cancellation_result_document_sha256: str,
) -> dict[str, Any]:
    """Seal every authority needed before the first destructive cancel step."""

    values = {
        "cancellation_result_document_sha256": (
            cancellation_result_document_sha256
        ),
        "cancellation_result_sha256": cancellation_result_sha256,
        "claim_absence_evidence_sha256": claim_absence_evidence_sha256,
        "fresh_approval_context_sha256": fresh_approval_context_sha256,
        "fresh_approval_plan_sha256": fresh_approval_plan_sha256,
        "fresh_transaction_inventory_document_sha256": (
            fresh_transaction_inventory_document_sha256
        ),
        "fresh_transaction_inventory_sha256": (
            fresh_transaction_inventory_sha256
        ),
        "fresh_transaction_ref": fresh_transaction_ref,
        "intent_sha256": intent_sha256,
        "old_abandonment_sha256": old_abandonment_sha256,
        "old_lock_sha256": old_lock_sha256,
        "old_transaction_ref": old_transaction_ref,
        "old_transaction_sha256": old_transaction_sha256,
        "prospective_plan_document_sha256": prospective_plan_document_sha256,
        "recovery_ref": recovery_ref,
        "schema": CANCELLATION_PLAN_SCHEMA,
    }
    if (
        _RECOVERY_REF_RE.fullmatch(recovery_ref) is None
        or _TRANSACTION_REF_RE.fullmatch(fresh_transaction_ref) is None
        or _TRANSACTION_REF_RE.fullmatch(old_transaction_ref) is None
        or any(
            type(value) is not str or _SHA_RE.fullmatch(value) is None
            for name, value in values.items()
            if name.endswith("sha256")
        )
    ):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    return values


def cancellation_stage_evidence_document(
    *,
    recovery_ref: str,
    intent_sha256: str,
    fresh_transaction_ref: str,
    cancellation_plan_document_sha256: str,
    claim_absence_evidence_sha256: str,
    fresh_transaction_inventory_sha256: str,
    fresh_transaction_inventory_document_sha256: str,
    stage_state: str,
) -> dict[str, Any]:
    values = {
        "cancellation_plan_document_sha256": (
            cancellation_plan_document_sha256
        ),
        "claim_absence_evidence_sha256": claim_absence_evidence_sha256,
        "fresh_transaction_inventory_document_sha256": (
            fresh_transaction_inventory_document_sha256
        ),
        "fresh_transaction_inventory_sha256": (
            fresh_transaction_inventory_sha256
        ),
        "fresh_transaction_ref": fresh_transaction_ref,
        "intent_sha256": intent_sha256,
        "recovery_ref": recovery_ref,
        "schema": CANCELLATION_STAGE_EVIDENCE_SCHEMA,
        "stage_state": stage_state,
    }
    if (
        _RECOVERY_REF_RE.fullmatch(recovery_ref) is None
        or _TRANSACTION_REF_RE.fullmatch(fresh_transaction_ref) is None
        or stage_state not in {"staged", "already_staged"}
        or any(
            type(value) is not str or _SHA_RE.fullmatch(value) is None
            for name, value in values.items()
            if name.endswith("sha256")
        )
    ):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    return values


def cancellation_cleanup_evidence_document(
    *,
    recovery_ref: str,
    intent_sha256: str,
    fresh_transaction_ref: str,
    cancellation_plan_document_sha256: str,
    cancellation_stage_evidence_document_sha256: str,
    fresh_transaction_inventory_sha256: str,
    fresh_transaction_inventory_document_sha256: str,
    cleanup_state: str,
) -> dict[str, Any]:
    values = {
        "cancellation_plan_document_sha256": (
            cancellation_plan_document_sha256
        ),
        "cancellation_stage_evidence_document_sha256": (
            cancellation_stage_evidence_document_sha256
        ),
        "cleanup_state": cleanup_state,
        "fresh_transaction_inventory_document_sha256": (
            fresh_transaction_inventory_document_sha256
        ),
        "fresh_transaction_inventory_sha256": (
            fresh_transaction_inventory_sha256
        ),
        "fresh_transaction_ref": fresh_transaction_ref,
        "intent_sha256": intent_sha256,
        "recovery_ref": recovery_ref,
        "schema": CANCELLATION_CLEANUP_EVIDENCE_SCHEMA,
    }
    if (
        _RECOVERY_REF_RE.fullmatch(recovery_ref) is None
        or _TRANSACTION_REF_RE.fullmatch(fresh_transaction_ref) is None
        or cleanup_state not in {"deleted_exact", "already_absent"}
        or any(
            type(value) is not str or _SHA_RE.fullmatch(value) is None
            for name, value in values.items()
            if name.endswith("sha256")
        )
    ):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    return values


def cancellation_restore_evidence_document(
    *,
    recovery_ref: str,
    intent_sha256: str,
    fresh_transaction_ref: str,
    cancellation_plan_document_sha256: str,
    cancellation_cleanup_evidence_document_sha256: str,
    old_transaction_ref: str,
    old_transaction_sha256: str,
    old_lock_sha256: str,
    restore_state: str,
) -> dict[str, Any]:
    values = {
        "cancellation_cleanup_evidence_document_sha256": (
            cancellation_cleanup_evidence_document_sha256
        ),
        "cancellation_plan_document_sha256": (
            cancellation_plan_document_sha256
        ),
        "fresh_transaction_ref": fresh_transaction_ref,
        "intent_sha256": intent_sha256,
        "old_lock_sha256": old_lock_sha256,
        "old_transaction_ref": old_transaction_ref,
        "old_transaction_sha256": old_transaction_sha256,
        "recovery_ref": recovery_ref,
        "restore_state": restore_state,
        "schema": CANCELLATION_RESTORE_EVIDENCE_SCHEMA,
    }
    if (
        _RECOVERY_REF_RE.fullmatch(recovery_ref) is None
        or _TRANSACTION_REF_RE.fullmatch(fresh_transaction_ref) is None
        or _TRANSACTION_REF_RE.fullmatch(old_transaction_ref) is None
        or restore_state not in {"restored", "already_restored"}
        or any(
            type(value) is not str or _SHA_RE.fullmatch(value) is None
            for name, value in values.items()
            if name.endswith("sha256")
        )
    ):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    return values


def terminal_receipt_document(
    *,
    recovery_ref: str,
    outcome: str,
    intent_sha256: str,
    journal_head_sha256: str,
    fresh_transaction_ref: str,
    old_transaction_inventory_sha256: str,
    fresh_transaction_completed_sha256: str | None = None,
    claim_evidence_sha256: str | None = None,
    old_lock_backup_sha256: str | None = None,
    claim_absence_evidence_sha256: str | None = None,
    cancelled_fresh_staging_sha256: str | None = None,
    cancelled_fresh_transaction_inventory_sha256: str | None = None,
    cancelled_fresh_transaction_inventory_document_sha256: str | None = None,
    cancelled_fresh_cleanup_evidence_sha256: str | None = None,
    restored_old_transaction_sha256: str | None = None,
    preserved_old_lock_sha256: str | None = None,
    cancellation_plan_document_sha256: str | None = None,
    cancellation_result_document_sha256: str | None = None,
    cancellation_result_sha256: str | None = None,
    cancelled_fresh_staging_document_sha256: str | None = None,
    cancelled_fresh_cleanup_evidence_document_sha256: str | None = None,
    restored_evidence_sha256: str | None = None,
    restored_evidence_document_sha256: str | None = None,
) -> dict[str, Any]:
    """Build one outcome-specific terminal proof without invented evidence.

    A successful claim and a claimless preapproval restoration have disjoint
    authorities.  Keeping their exact field sets disjoint prevents callers
    from filling unavailable success evidence with sentinel digests merely to
    satisfy a common schema.
    """

    common = {
        "fresh_transaction_ref": fresh_transaction_ref,
        "intent_sha256": intent_sha256,
        "journal_head_sha256": journal_head_sha256,
        "old_transaction_inventory_sha256": (
            old_transaction_inventory_sha256
        ),
        "outcome": outcome,
        "recovery_ref": recovery_ref,
        "schema": TERMINAL_RECEIPT_SCHEMA,
    }
    success_evidence = {
        "claim_evidence_sha256": claim_evidence_sha256,
        "fresh_transaction_completed_sha256": (
            fresh_transaction_completed_sha256
        ),
        "old_lock_backup_sha256": old_lock_backup_sha256,
    }
    restored_evidence = {
        "cancellation_plan_document_sha256": (
            cancellation_plan_document_sha256
        ),
        "cancellation_result_document_sha256": (
            cancellation_result_document_sha256
        ),
        "cancellation_result_sha256": cancellation_result_sha256,
        "cancelled_fresh_cleanup_evidence_sha256": (
            cancelled_fresh_cleanup_evidence_sha256
        ),
        "cancelled_fresh_cleanup_evidence_document_sha256": (
            cancelled_fresh_cleanup_evidence_document_sha256
        ),
        "cancelled_fresh_staging_sha256": cancelled_fresh_staging_sha256,
        "cancelled_fresh_staging_document_sha256": (
            cancelled_fresh_staging_document_sha256
        ),
        "cancelled_fresh_transaction_inventory_sha256": (
            cancelled_fresh_transaction_inventory_sha256
        ),
        "cancelled_fresh_transaction_inventory_document_sha256": (
            cancelled_fresh_transaction_inventory_document_sha256
        ),
        "claim_absence_evidence_sha256": claim_absence_evidence_sha256,
        "preserved_old_lock_sha256": preserved_old_lock_sha256,
        "restored_evidence_document_sha256": (
            restored_evidence_document_sha256
        ),
        "restored_evidence_sha256": restored_evidence_sha256,
        "restored_old_transaction_sha256": restored_old_transaction_sha256,
    }
    if (
        _RECOVERY_REF_RE.fullmatch(recovery_ref) is None
        or _TRANSACTION_REF_RE.fullmatch(fresh_transaction_ref) is None
        or outcome not in {"success", "unapproved_restored"}
    ):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    selected = success_evidence if outcome == "success" else restored_evidence
    rejected = restored_evidence if outcome == "success" else success_evidence
    values = dict(common)
    values.update(selected)
    if (
        any(value is not None for value in rejected.values())
        or any(
            type(value) is not str or _SHA_RE.fullmatch(value) is None
            for name, value in values.items()
            if name.endswith("sha256")
        )
    ):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    return values


@dataclass(frozen=True)
class ResolvedPendingCancellationTerminal:
    """Bounded proof of a cancellation capsule awaiting locator retirement.

    The delivery capability itself, the raw reviewer, paths, and the public
    result body deliberately do not leave the authenticated resolver.  The
    service receives only the exact digests needed to finish the already
    authorized terminal-control transition without reopening approval or a
    project-domain writer.
    """

    recovery_ref: str
    outcome: str
    archive_identity_sha256: str
    intent_sha256: str
    journal_head_sha256: str
    active_locator_state: str
    active_locator_sha256: str
    terminal_receipt_document_sha256: str
    cancellation_result_document_sha256: str
    cancellation_result_sha256: str
    result_payload_sha256: str
    terminal_handoff_document_sha256: str
    delivery_capability_sha256: str


@dataclass(frozen=True)
class ResolvedActiveRecovery:
    """Private, authenticated state used only by the project-update service."""

    paths: RecoveryPaths
    locator: Mapping[str, Any]
    intent: Mapping[str, Any]
    fresh_approval_seed: Mapping[str, Any]
    checkpoints: tuple[Mapping[str, Any], ...]
    pre_fetch_ref_snapshot: Mapping[str, Any] | None
    fresh_allocation: Mapping[str, Any] | None
    fresh_reservation: Mapping[str, Any] | None
    fresh_transaction_inventory: Mapping[str, Any] | None
    post_fetch_ref_snapshot: Mapping[str, Any] | None
    prospective_plan: Mapping[str, Any] | None
    cancellation_result: Mapping[str, Any] | None
    cancellation_plan: Mapping[str, Any] | None
    cancellation_stage_evidence: Mapping[str, Any] | None
    cancellation_cleanup_evidence: Mapping[str, Any] | None
    cancellation_restore_evidence: Mapping[str, Any] | None
    terminal_receipt: Mapping[str, Any] | None
    intent_sha256: str
    fresh_approval_seed_document_sha256: str
    journal_head_sha256: str | None
    locator_sha256: str
    locator_journal_head_sha256: str | None
    pending_checkpoint: Mapping[str, Any] | None
    pre_fetch_ref_snapshot_document_sha256: str | None
    pre_fetch_ref_snapshot_sha256: str | None
    fresh_allocation_document_sha256: str | None
    fresh_reservation_document_sha256: str | None
    fresh_transaction_inventory_document_sha256: str | None
    fresh_transaction_inventory_sha256: str | None
    post_fetch_ref_snapshot_document_sha256: str | None
    post_fetch_ref_snapshot_sha256: str | None
    prospective_plan_document_sha256: str | None
    cancellation_result_document_sha256: str | None
    cancellation_result_sha256: str | None
    cancellation_plan_document_sha256: str | None
    cancellation_stage_evidence_document_sha256: str | None
    cancellation_cleanup_evidence_document_sha256: str | None
    cancellation_restore_evidence_document_sha256: str | None
    terminal_receipt_document_sha256: str | None
    fresh_transaction_ref: str | None
    pending_cancellation_terminal: (
        ResolvedPendingCancellationTerminal | None
    )


@dataclass(frozen=True)
class ResolvedTerminalRecovery:
    """Bounded authenticated proof for one retired cancellation terminal.

    Only fixed identifiers and digests needed to bind a restart delivery
    capsule leave the resolver.  In particular, the private approval seed,
    its raw reviewer, filesystem paths, and the public result projection are
    deliberately not exposed.
    """

    recovery_ref: str
    outcome: str
    archive_identity_sha256: str
    project_identity_sha256: str
    intent_sha256: str
    journal_head_sha256: str
    fresh_transaction_ref: str
    terminal_locator_sha256: str
    terminal_receipt_document_sha256: str
    cancellation_result_document_sha256: str
    cancellation_result_sha256: str
    cancellation_plan_document_sha256: str
    cancellation_stage_evidence_document_sha256: str
    cancellation_stage_evidence_sha256: str
    cancellation_cleanup_evidence_document_sha256: str
    cancellation_cleanup_evidence_sha256: str
    cancellation_restore_evidence_document_sha256: str
    cancellation_restore_evidence_sha256: str


def _resolve_pending_cancellation_terminal(
    *,
    paths: RecoveryPaths,
    key: bytes | bytearray | memoryview,
    locator: Mapping[str, Any],
    locator_sha256: str,
    intent: Mapping[str, Any],
    intent_sha256: str,
    journal_head_sha256: str | None,
    terminal_receipt: Mapping[str, Any] | None,
    terminal_receipt_document_sha256: str | None,
    cancellation_result_document_sha256: str | None,
    cancellation_result_sha256: str | None,
) -> ResolvedPendingCancellationTerminal | None:
    """Authenticate the one capsule-before-locator-retirement boundary.

    An absent handoff is not inferred as a cancellation: the caller may still
    be at the receipt-only durable prefix.  Once a handoff exists, however,
    every authority must be present and exact.  This function is read-only;
    any collision or drift is preserved for explicit reconciliation.
    """

    handoff_path = paths.project_root.joinpath(
        *PurePosixPath(TERMINAL_HANDOFF_LOGICAL).parts
    )
    terminal_locator_path = paths.recovery_root / "terminal-locator.json"
    locator_transition_path = _locator_transition_path(paths.locator_path)
    with _retained_parent_chains(
        paths.project_root,
        paths.recovery_root,
        handoff_path.parent,
    ):
        if os.path.lexists(terminal_locator_path):
            raise _fail("project_update_legacy_recovery_state_ambiguous")
        if not os.path.lexists(handoff_path):
            return None
        handoff_raw = _read_regular(handoff_path)
        handoff = verify_authenticated_document(
            _parse_json(handoff_raw), key
        )
        payload = handoff.get("payload")
        handoff_keys = {"payload", "schema", "state"}
        payload_keys = {
            "archive_identity_sha256",
            "cancellation_result_document_sha256",
            "delivery_capability_sha256",
            "intent_sha256",
            "outcome",
            "recovery_ref",
            "result_payload_sha256",
            "schema",
            "terminal_receipt_sha256",
        }
        if (
            set(handoff) != handoff_keys
            or handoff.get("schema")
            != CANCELLATION_TERMINAL_HANDOFF_SCHEMA
            or handoff.get("state") != "terminal_ready_unapproved"
            or not isinstance(payload, Mapping)
            or set(payload) != payload_keys
            or payload.get("schema")
            != CANCELLATION_TERMINAL_PAYLOAD_SCHEMA
            or payload.get("outcome") != "unapproved_restored"
            or _RECOVERY_REF_RE.fullmatch(
                str(payload.get("recovery_ref") or "")
            )
            is None
            or any(
                type(payload.get(name)) is not str
                or _SHA_RE.fullmatch(str(payload.get(name))) is None
                for name in (
                    "archive_identity_sha256",
                    "cancellation_result_document_sha256",
                    "delivery_capability_sha256",
                    "intent_sha256",
                    "result_payload_sha256",
                    "terminal_receipt_sha256",
                )
            )
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")

        binding = {
            name: payload[name]
            for name in (
                "archive_identity_sha256",
                "cancellation_result_document_sha256",
                "intent_sha256",
                "outcome",
                "recovery_ref",
                "result_payload_sha256",
                "terminal_receipt_sha256",
            )
        }
        capability_document = authenticated_document(
            {
                "schema": CANCELLATION_TERMINAL_DELIVERY_CAPABILITY_SCHEMA,
                **binding,
            },
            key,
        )
        authentication = capability_document.get("authentication")
        capability = (
            authentication.get("mac")
            if isinstance(authentication, Mapping)
            else None
        )
        if (
            type(capability) is not str
            or re.fullmatch(r"hmac-sha256:[0-9a-f]{64}", capability)
            is None
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        capability_sha256 = sha256_bytes(capability.encode("ascii"))

        if (
            locator.get("state") != "unapproved_restored"
            or locator.get("recovery_ref") != paths.recovery_ref
            or locator.get("intent_sha256") != intent_sha256
            or locator.get("journal_head_sha256") != journal_head_sha256
            or terminal_receipt is None
            or terminal_receipt.get("outcome") != "unapproved_restored"
            or terminal_receipt.get("recovery_ref") != paths.recovery_ref
            or terminal_receipt.get("intent_sha256") != intent_sha256
            or terminal_receipt.get("journal_head_sha256")
            != journal_head_sha256
            or terminal_receipt_document_sha256 is None
            or cancellation_result_document_sha256 is None
            or cancellation_result_sha256 is None
            or payload.get("recovery_ref") != paths.recovery_ref
            or payload.get("archive_identity_sha256")
            != intent.get("archive_identity_sha256")
            or payload.get("intent_sha256") != intent_sha256
            or payload.get("terminal_receipt_sha256")
            != terminal_receipt_document_sha256
            or payload.get("cancellation_result_document_sha256")
            != cancellation_result_document_sha256
            or payload.get("result_payload_sha256")
            != _cancellation_delivery_payload_sha256(
                cancellation_result_document()
            )
            or cancellation_result_sha256
            != sha256_document(cancellation_result_document())
            or payload.get("delivery_capability_sha256")
            != capability_sha256
            or locator.get("terminal_receipt_sha256") is not None
        ):
            raise _fail("project_update_legacy_recovery_state_changed")

        selected_locator = (
            paths.locator_path
            if os.path.lexists(paths.locator_path)
            else locator_transition_path
        )
        if (
            not os.path.lexists(selected_locator)
            or sha256_bytes(_read_regular(selected_locator)) != locator_sha256
            or not hmac.compare_digest(
                _read_regular(handoff_path), handoff_raw
            )
            or os.path.lexists(terminal_locator_path)
        ):
            raise _fail("project_update_legacy_recovery_state_ambiguous")

        return ResolvedPendingCancellationTerminal(
            recovery_ref=paths.recovery_ref,
            outcome="unapproved_restored",
            archive_identity_sha256=str(intent["archive_identity_sha256"]),
            intent_sha256=intent_sha256,
            journal_head_sha256=str(journal_head_sha256),
            active_locator_state=str(locator["state"]),
            active_locator_sha256=locator_sha256,
            terminal_receipt_document_sha256=(
                terminal_receipt_document_sha256
            ),
            cancellation_result_document_sha256=(
                cancellation_result_document_sha256
            ),
            cancellation_result_sha256=cancellation_result_sha256,
            result_payload_sha256=str(payload["result_payload_sha256"]),
            terminal_handoff_document_sha256=sha256_bytes(handoff_raw),
            delivery_capability_sha256=capability_sha256,
        )


class LegacyRecoveryStore:
    """Create/read an authenticated create-only recovery record chain."""

    def __init__(
        self,
        project_root: Path | str,
        recovery_ref: str,
        key: bytes | bytearray | memoryview,
    ) -> None:
        self.paths = RecoveryPaths.build(project_root, recovery_ref)
        self._key = _validated_key(key)

    def close(self) -> None:
        for index in range(len(self._key)):
            self._key[index] = 0

    def __enter__(self) -> "LegacyRecoveryStore":
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def write_fresh_approval_seed(
        self,
        document: Mapping[str, Any],
    ) -> str:
        """Create the sole private raw-reviewer record before intent sealing."""

        if (
            document.get("schema") != FRESH_APPROVAL_SEED_SCHEMA
            or document.get("recovery_ref") != self.paths.recovery_ref
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        # Re-run the public constructor as an exact schema/value validator.
        try:
            validated = fresh_approval_seed_document(
                recovery_ref=str(document["recovery_ref"]),
                reviewer=document["reviewer"],
                old_transaction_ref=str(document["old_transaction_ref"]),
                old_transaction_sha256=str(document["old_transaction_sha256"]),
                archive_identity_sha256=str(
                    document["archive_identity_sha256"]
                ),
                project_identity_sha256=str(
                    document["project_identity_sha256"]
                ),
                requested_target_tag=str(document["requested_target_tag"]),
            )
        except (KeyError, TypeError):
            raise _fail("project_update_legacy_recovery_binding_invalid") from None
        if dict(document) != validated:
            raise _fail("project_update_legacy_recovery_binding_invalid")
        project = self.paths.project_root
        recoveries = project.joinpath(*PurePosixPath(RECOVERY_ROOT_LOGICAL).parts)
        for directory in (
            project / ".zettel-kasten",
            project / ".zettel-kasten" / "private",
            recoveries.parent,
            recoveries,
            self.paths.recovery_root,
        ):
            if not os.path.lexists(directory):
                try:
                    directory.mkdir(mode=0o700)
                except OSError:
                    raise _fail(
                        "project_update_legacy_recovery_commit_failed"
                    ) from None
                _fsync_directory(directory.parent)
            _safe_directory(directory)
        path = self.paths.recovery_root / "fresh-approval-seed.json"
        if not os.path.lexists(path):
            try:
                with os.scandir(self.paths.recovery_root) as iterator:
                    if {entry.name for entry in iterator}:
                        raise _fail(
                            "project_update_legacy_recovery_state_changed"
                        )
            except LegacyProjectUpdateRecoveryError:
                raise
            except OSError:
                raise _fail(
                    "project_update_legacy_recovery_path_unsafe"
                ) from None
        return self._write_authenticated_create_only(path, validated)

    def read_fresh_approval_seed(self) -> dict[str, Any]:
        payload = self._read_authenticated_exact(
            self.paths.recovery_root / "fresh-approval-seed.json",
            schema=FRESH_APPROVAL_SEED_SCHEMA,
            keys=frozenset(
                {
                    "archive_identity_sha256",
                    "old_transaction_ref",
                    "old_transaction_sha256",
                    "project_identity_sha256",
                    "recovery_ref",
                    "requested_target_tag",
                    "reviewer",
                    "schema",
                }
            ),
        )
        try:
            validated = fresh_approval_seed_document(
                recovery_ref=str(payload["recovery_ref"]),
                reviewer=payload["reviewer"],
                old_transaction_ref=str(payload["old_transaction_ref"]),
                old_transaction_sha256=str(payload["old_transaction_sha256"]),
                archive_identity_sha256=str(
                    payload["archive_identity_sha256"]
                ),
                project_identity_sha256=str(
                    payload["project_identity_sha256"]
                ),
                requested_target_tag=str(payload["requested_target_tag"]),
            )
        except (KeyError, TypeError):
            raise _fail("project_update_legacy_recovery_binding_invalid") from None
        if validated != payload:
            raise _fail("project_update_legacy_recovery_binding_invalid")
        return payload

    def initialize(
        self,
        intent: Mapping[str, Any],
        *,
        _failpoint: Callable[[str], None] | None = None,
    ) -> str:
        try:
            validated_intent = recovery_intent_document(
                recovery_ref=str(intent["recovery_ref"]),
                old_transaction_ref=str(intent["old_transaction_ref"]),
                old_transaction_sha256=str(intent["old_transaction_sha256"]),
                old_claim_sha256=str(intent["old_claim_sha256"]),
                old_lock_sha256=str(intent["old_lock_sha256"]),
                old_live_components_sha256=str(
                    intent["old_live_components_sha256"]
                ),
                archive_identity_sha256=str(
                    intent["archive_identity_sha256"]
                ),
                project_identity_sha256=str(
                    intent["project_identity_sha256"]
                ),
                fresh_approval_seed_document_sha256=str(
                    intent["fresh_approval_seed_document_sha256"]
                ),
            )
        except (KeyError, TypeError):
            raise _fail("project_update_legacy_recovery_binding_invalid") from None
        if (
            intent.get("schema") != RECOVERY_INTENT_SCHEMA
            or intent.get("recovery_ref") != self.paths.recovery_ref
            or dict(intent) != validated_intent
            or (_failpoint is not None and not callable(_failpoint))
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")

        def failpoint(stage: str) -> None:
            if _failpoint is None:
                return
            try:
                _failpoint(stage)
            except BaseException:
                raise _fail(
                    "project_update_legacy_recovery_commit_failed"
                ) from None

        project = self.paths.project_root
        terminal_root = self.paths.locator_path.parent
        recoveries = project.joinpath(*PurePosixPath(RECOVERY_ROOT_LOGICAL).parts)
        for directory in (
            project / ".zettel-kasten",
            project / ".zettel-kasten" / "private",
            terminal_root,
            recoveries.parent,
            recoveries,
        ):
            if not os.path.lexists(directory):
                try:
                    directory.mkdir(mode=0o700)
                except OSError:
                    raise _fail("project_update_legacy_recovery_commit_failed") from None
                _fsync_directory(directory.parent)
            _safe_directory(directory)
        seed_path = self.paths.recovery_root / "fresh-approval-seed.json"
        seed_raw = _read_regular(seed_path)
        seed = self.read_fresh_approval_seed()
        seed_document_sha256 = sha256_bytes(seed_raw)
        if (
            intent.get("fresh_approval_seed_document_sha256")
            != seed_document_sha256
            or seed.get("old_transaction_ref")
            != intent.get("old_transaction_ref")
            or seed.get("old_transaction_sha256")
            != intent.get("old_transaction_sha256")
            or seed.get("archive_identity_sha256")
            != intent.get("archive_identity_sha256")
            or seed.get("project_identity_sha256")
            != intent.get("project_identity_sha256")
        ):
            raise _fail("project_update_legacy_recovery_state_changed")
        signed = authenticated_document(dict(intent), self._key)
        raw = _canonical(signed)
        digest = sha256_bytes(raw)
        locator_selected = (
            self.paths.locator_path
            if os.path.lexists(self.paths.locator_path)
            else _locator_transition_path(self.paths.locator_path)
        )
        if os.path.lexists(locator_selected):
            locator = self.read_locator()
            locator_raw = _read_regular(locator_selected)
            locator_sha256 = sha256_bytes(locator_raw)
            if locator.get("intent_sha256") != digest:
                raise _fail("project_update_legacy_recovery_state_changed")
            if locator.get("state") == "intent_sealed":
                intent_path = self.paths.recovery_root / "intent.json"
                if not hmac.compare_digest(_read_regular(intent_path), raw):
                    raise _fail(
                        "project_update_legacy_recovery_state_changed"
                    )
                return digest
            if locator.get("state") != "allocating":
                raise _fail("project_update_legacy_recovery_state_changed")
        else:
            locator_sha256 = self.publish_locator(
                state="allocating",
                intent_sha256=digest,
                journal_head_sha256=None,
                previous_locator_sha256=None,
                allocating_intent=intent,
            )
        failpoint("allocating_locator_durable")
        try:
            self.paths.recovery_root.mkdir(mode=0o700)
        except FileExistsError:
            pass
        except OSError:
            raise _fail("project_update_legacy_recovery_commit_failed") from None
        _safe_directory(self.paths.recovery_root)
        try:
            with os.scandir(self.paths.recovery_root) as iterator:
                if not {entry.name for entry in iterator}.issubset(
                    {"fresh-approval-seed.json", "intent.json"}
                ):
                    raise _fail(
                        "project_update_legacy_recovery_state_changed"
                    )
        except LegacyProjectUpdateRecoveryError:
            raise
        except OSError:
            raise _fail("project_update_legacy_recovery_path_unsafe") from None
        _fsync_directory(self.paths.recovery_root.parent)
        failpoint("recovery_root_durable")
        intent_path = self.paths.recovery_root / "intent.json"
        if os.path.lexists(intent_path):
            if not hmac.compare_digest(_read_regular(intent_path), raw):
                raise _fail("project_update_legacy_recovery_state_changed")
        else:
            _write_new(intent_path, raw)
        failpoint("intent_durable")
        self.publish_locator(
            state="intent_sealed",
            intent_sha256=digest,
            journal_head_sha256=None,
            previous_locator_sha256=locator_sha256,
        )
        failpoint("intent_locator_durable")
        return digest

    def publish_locator(
        self,
        *,
        state: str,
        intent_sha256: str,
        journal_head_sha256: str | None,
        previous_locator_sha256: str | None,
        terminal_receipt_sha256: str | None = None,
        allocating_intent: Mapping[str, Any] | None = None,
    ) -> str:
        if (
            _STATE_RE.fullmatch(state) is None
            or _SHA_RE.fullmatch(intent_sha256) is None
            or (
                journal_head_sha256 is not None
                and _SHA_RE.fullmatch(journal_head_sha256) is None
            )
            or (
                previous_locator_sha256 is not None
                and _SHA_RE.fullmatch(previous_locator_sha256) is None
            )
            or (
                terminal_receipt_sha256 is not None
                and _SHA_RE.fullmatch(terminal_receipt_sha256) is None
            )
            or ((state == "terminal_completed") != (terminal_receipt_sha256 is not None))
            or ((state == "allocating") != (allocating_intent is not None))
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        locator_payload = {
                "intent_sha256": intent_sha256,
                "journal_head_sha256": journal_head_sha256,
                "previous_locator_sha256": previous_locator_sha256,
                "recovery_ref": self.paths.recovery_ref,
                "schema": ACTIVE_LOCATOR_SCHEMA,
                "state": state,
        }
        if terminal_receipt_sha256 is not None:
            locator_payload["terminal_receipt_sha256"] = terminal_receipt_sha256
        if allocating_intent is not None:
            if (
                allocating_intent.get("schema") != RECOVERY_INTENT_SCHEMA
                or allocating_intent.get("recovery_ref")
                != self.paths.recovery_ref
            ):
                raise _fail("project_update_legacy_recovery_binding_invalid")
            signed_intent = authenticated_document(
                dict(allocating_intent), self._key
            )
            if sha256_bytes(_canonical(signed_intent)) != intent_sha256:
                raise _fail("project_update_legacy_recovery_binding_invalid")
            locator_payload["allocating_intent"] = signed_intent
        locator = authenticated_document(
            locator_payload,
            self._key,
        )
        raw = _canonical(locator)
        path = self.paths.locator_path
        transition = _locator_transition_path(path)
        new_digest = sha256_bytes(raw)
        if not os.path.lexists(path) and not os.path.lexists(transition):
            _write_new(path, raw)
            return new_digest
        current: bytes | None = None
        transitioned: bytes | None = None
        if os.path.lexists(path):
            current = _read_regular(path)
        if os.path.lexists(transition):
            transitioned = _read_regular(transition)
        if current is not None and hmac.compare_digest(current, raw):
            if transitioned is not None:
                if previous_locator_sha256 is None or sha256_bytes(
                    transitioned
                ) != previous_locator_sha256:
                    raise _fail("project_update_legacy_recovery_state_ambiguous")
                _delete_exact_regular_bytes(
                    self.paths.project_root,
                    transition,
                    transitioned,
                )
            return new_digest
        previous_raw = current if current is not None else transitioned
        if (
            previous_raw is None
            or previous_locator_sha256 is None
            or sha256_bytes(previous_raw) != previous_locator_sha256
            or (current is not None and transitioned is not None)
        ):
            raise _fail("project_update_legacy_recovery_state_changed")
        verify_authenticated_document(_parse_json(previous_raw), self._key)
        current_digest = previous_locator_sha256
        history = self.paths.recovery_root / "locator-history"
        if not os.path.lexists(history):
            try:
                history.mkdir(mode=0o700)
            except OSError:
                raise _fail("project_update_legacy_recovery_commit_failed") from None
            _fsync_directory(history.parent)
        history_path = history / (current_digest.removeprefix("sha256:") + ".json")
        if os.path.lexists(history_path):
            if not hmac.compare_digest(
                _read_regular(history_path), previous_raw
            ):
                raise _fail("project_update_legacy_recovery_state_changed")
        else:
            _write_new(history_path, previous_raw)
        if current is not None:
            _move_exact_regular_no_replace(
                self.paths.project_root,
                path,
                transition,
                previous_raw,
            )
        elif not hmac.compare_digest(
            _read_regular(transition),
            previous_raw,
        ):
            raise _fail("project_update_legacy_recovery_state_changed")
        _write_new(path, raw)
        if not hmac.compare_digest(_read_regular(path), raw):
            raise _fail("project_update_legacy_recovery_state_changed")
        if os.path.lexists(transition):
            _delete_exact_regular_bytes(
                self.paths.project_root,
                transition,
                previous_raw,
            )
        return new_digest

    def read_locator(self) -> dict[str, Any]:
        selected = (
            self.paths.locator_path
            if os.path.lexists(self.paths.locator_path)
            else _locator_transition_path(self.paths.locator_path)
        )
        payload = verify_authenticated_document(
            _parse_json(_read_regular(selected)),
            self._key,
        )
        ordinary_keys = {
                "intent_sha256",
                "journal_head_sha256",
                "previous_locator_sha256",
                "recovery_ref",
                "schema",
                "state",
        }
        terminal_keys = ordinary_keys | {"terminal_receipt_sha256"}
        allocating_keys = ordinary_keys | {"allocating_intent"}
        allowed_states = {
            "allocating",
            "intent_sealed",
            "terminal_completed",
            *_CHECKPOINT_LOCATOR_STATE.values(),
        }
        if (
            frozenset(payload)
            not in {
                frozenset(ordinary_keys),
                frozenset(terminal_keys),
                frozenset(allocating_keys),
            }
            or payload.get("schema") != ACTIVE_LOCATOR_SCHEMA
            or payload.get("recovery_ref") != self.paths.recovery_ref
            or payload.get("state") not in allowed_states
            or _SHA_RE.fullmatch(str(payload.get("intent_sha256"))) is None
            or (
                payload.get("journal_head_sha256") is not None
                and _SHA_RE.fullmatch(
                    str(payload.get("journal_head_sha256"))
                )
                is None
            )
            or (
                payload.get("previous_locator_sha256") is not None
                and _SHA_RE.fullmatch(
                    str(payload.get("previous_locator_sha256"))
                )
                is None
            )
            or (
                payload.get("state") in {"allocating", "intent_sealed"}
                and payload.get("journal_head_sha256") is not None
            )
            or (
                payload.get("state") not in {"allocating", "intent_sealed"}
                and payload.get("journal_head_sha256") is None
            )
            or ((payload.get("state") == "terminal_completed") != (set(payload) == terminal_keys))
            or ((payload.get("state") == "allocating") != (set(payload) == allocating_keys))
            or (
                set(payload) == terminal_keys
                and _SHA_RE.fullmatch(
                    str(payload.get("terminal_receipt_sha256"))
                )
                is None
            )
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        if payload.get("state") == "allocating":
            nested = payload.get("allocating_intent")
            if not isinstance(nested, Mapping):
                raise _fail("project_update_legacy_recovery_binding_invalid")
            intent = verify_authenticated_document(nested, self._key)
            if (
                intent.get("schema") != RECOVERY_INTENT_SCHEMA
                or intent.get("recovery_ref") != self.paths.recovery_ref
                or sha256_bytes(_canonical(dict(nested)))
                != payload.get("intent_sha256")
            ):
                raise _fail("project_update_legacy_recovery_binding_invalid")
        return payload

    def _write_authenticated_create_only(
        self,
        path: Path,
        document: Mapping[str, Any],
    ) -> str:
        raw = _canonical(authenticated_document(dict(document), self._key))
        if os.path.lexists(path):
            if not hmac.compare_digest(_read_regular(path), raw):
                raise _fail("project_update_legacy_recovery_state_changed")
        else:
            _write_new(path, raw)
        return sha256_bytes(raw)

    def _read_authenticated_exact(
        self,
        path: Path,
        *,
        schema: str,
        keys: frozenset[str],
    ) -> dict[str, Any]:
        payload = verify_authenticated_document(
            _parse_json(_read_regular(path)),
            self._key,
        )
        if (
            frozenset(payload) != keys
            or payload.get("schema") != schema
            or payload.get("recovery_ref") != self.paths.recovery_ref
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        return payload

    def read_intent(self) -> tuple[dict[str, Any], str]:
        path = self.paths.recovery_root / "intent.json"
        raw = _read_regular(path)
        payload = verify_authenticated_document(_parse_json(raw), self._key)
        expected_keys = {
            "archive_identity_sha256",
            "fresh_approval_seed_document_sha256",
            "old_claim_sha256",
            "old_live_components_sha256",
            "old_lock_sha256",
            "old_transaction_ref",
            "old_transaction_sha256",
            "project_identity_sha256",
            "recovery_ref",
            "schema",
        }
        if (
            set(payload) != expected_keys
            or payload.get("schema") != RECOVERY_INTENT_SCHEMA
            or payload.get("recovery_ref") != self.paths.recovery_ref
            or _TRANSACTION_REF_RE.fullmatch(
                str(payload.get("old_transaction_ref"))
            )
            is None
            or any(
                type(value) is not str or _SHA_RE.fullmatch(value) is None
                for name, value in payload.items()
                if name.endswith("sha256")
            )
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        return payload, sha256_bytes(raw)

    def write_pre_fetch_ref_snapshot(
        self,
        snapshot: Mapping[str, Any],
    ) -> dict[str, str]:
        if not isinstance(snapshot, Mapping):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        semantic_sha256 = sha256_document(dict(snapshot))
        document = {
            "recovery_ref": self.paths.recovery_ref,
            "schema": PRE_FETCH_REF_SNAPSHOT_SCHEMA,
            "snapshot": dict(snapshot),
            "snapshot_sha256": semantic_sha256,
        }
        if len(_canonical(authenticated_document(document, self._key))) > _MAX_DOCUMENT_BYTES:
            raise _fail("project_update_legacy_recovery_binding_invalid")
        document_sha256 = self._write_authenticated_create_only(
            self.paths.recovery_root / "pre-fetch-ref-snapshot.json",
            document,
        )
        return {
            "pre_ref_snapshot_document_sha256": document_sha256,
            "pre_ref_snapshot_sha256": semantic_sha256,
        }

    def read_pre_fetch_ref_snapshot(self) -> dict[str, Any]:
        path = self.paths.recovery_root / "pre-fetch-ref-snapshot.json"
        raw = _read_regular(path)
        payload = verify_authenticated_document(_parse_json(raw), self._key)
        if (
            set(payload)
            != {"recovery_ref", "schema", "snapshot", "snapshot_sha256"}
            or payload.get("schema") != PRE_FETCH_REF_SNAPSHOT_SCHEMA
            or payload.get("recovery_ref") != self.paths.recovery_ref
            or not isinstance(payload.get("snapshot"), Mapping)
            or _SHA_RE.fullmatch(str(payload.get("snapshot_sha256"))) is None
            or sha256_document(dict(payload["snapshot"]))
            != payload["snapshot_sha256"]
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        return {
            "pre_ref_snapshot": dict(payload["snapshot"]),
            "pre_ref_snapshot_document_sha256": sha256_bytes(raw),
            "pre_ref_snapshot_sha256": payload["snapshot_sha256"],
        }

    def write_post_fetch_ref_snapshot(
        self,
        snapshot: Mapping[str, Any],
        *,
        pre_ref_snapshot_document_sha256: str,
        pre_ref_snapshot_sha256: str,
        requested_target_tag: str,
        transport_cache_policy: str = "retained_transport_cache",
    ) -> dict[str, str]:
        if (
            not isinstance(snapshot, Mapping)
            or _SHA_RE.fullmatch(pre_ref_snapshot_document_sha256) is None
            or _SHA_RE.fullmatch(pre_ref_snapshot_sha256) is None
            or _TARGET_TAG_RE.fullmatch(requested_target_tag) is None
            or transport_cache_policy != "retained_transport_cache"
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        semantic_sha256 = sha256_document(dict(snapshot))
        document = {
            "pre_ref_snapshot_document_sha256": (
                pre_ref_snapshot_document_sha256
            ),
            "pre_ref_snapshot_sha256": pre_ref_snapshot_sha256,
            "recovery_ref": self.paths.recovery_ref,
            "requested_target_tag": requested_target_tag,
            "schema": POST_FETCH_REF_SNAPSHOT_SCHEMA,
            "snapshot": dict(snapshot),
            "snapshot_sha256": semantic_sha256,
            "transport_cache_policy": transport_cache_policy,
        }
        if len(_canonical(authenticated_document(document, self._key))) > _MAX_DOCUMENT_BYTES:
            raise _fail("project_update_legacy_recovery_binding_invalid")
        document_sha256 = self._write_authenticated_create_only(
            self.paths.recovery_root / "post-fetch-ref-snapshot.json",
            document,
        )
        return {
            "post_ref_snapshot_document_sha256": document_sha256,
            "post_ref_snapshot_sha256": semantic_sha256,
        }

    def read_post_fetch_ref_snapshot(self) -> dict[str, Any]:
        path = self.paths.recovery_root / "post-fetch-ref-snapshot.json"
        raw = _read_regular(path)
        payload = verify_authenticated_document(_parse_json(raw), self._key)
        expected = {
            "pre_ref_snapshot_document_sha256",
            "pre_ref_snapshot_sha256",
            "recovery_ref",
            "requested_target_tag",
            "schema",
            "snapshot",
            "snapshot_sha256",
            "transport_cache_policy",
        }
        if (
            set(payload) != expected
            or payload.get("schema") != POST_FETCH_REF_SNAPSHOT_SCHEMA
            or payload.get("recovery_ref") != self.paths.recovery_ref
            or not isinstance(payload.get("snapshot"), Mapping)
            or _SHA_RE.fullmatch(str(payload.get("snapshot_sha256"))) is None
            or _SHA_RE.fullmatch(
                str(payload.get("pre_ref_snapshot_document_sha256"))
            )
            is None
            or _SHA_RE.fullmatch(str(payload.get("pre_ref_snapshot_sha256")))
            is None
            or _TARGET_TAG_RE.fullmatch(
                str(payload.get("requested_target_tag"))
            )
            is None
            or payload.get("transport_cache_policy")
            != "retained_transport_cache"
            or sha256_document(dict(payload["snapshot"]))
            != payload["snapshot_sha256"]
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        return {
            "post_ref_snapshot": dict(payload["snapshot"]),
            "post_ref_snapshot_document_sha256": sha256_bytes(raw),
            "post_ref_snapshot_sha256": payload["snapshot_sha256"],
            "pre_ref_snapshot_document_sha256": payload[
                "pre_ref_snapshot_document_sha256"
            ],
            "pre_ref_snapshot_sha256": payload["pre_ref_snapshot_sha256"],
            "requested_target_tag": payload["requested_target_tag"],
            "transport_cache_policy": payload["transport_cache_policy"],
        }

    def write_fresh_allocation(self, document: Mapping[str, Any]) -> str:
        expected_keys = {
            "fresh_created_at",
            "fresh_ownership_nonce",
            "fresh_transaction_ref",
            "old_abandonment_sha256",
            "prepared_reservation_document_sha256",
            "pre_ref_snapshot_document_sha256",
            "pre_ref_snapshot_sha256",
            "project_identity_sha256",
            "recovery_ref",
            "requested_target_tag",
            "schema",
            "transport_cache_policy",
        }
        if (
            document.get("schema") != FRESH_ALLOCATION_SCHEMA
            or document.get("recovery_ref") != self.paths.recovery_ref
            or set(document) != expected_keys
            or any(
                type(value) is not str or _SHA_RE.fullmatch(value) is None
                for name, value in document.items()
                if name.endswith("sha256")
            )
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        _prepared_reservation_from_allocation(document)
        return self._write_authenticated_create_only(
            self.paths.recovery_root / "fresh-allocation.json",
            document,
        )

    def read_fresh_allocation(self) -> dict[str, Any]:
        payload = self._read_authenticated_exact(
            self.paths.recovery_root / "fresh-allocation.json",
            schema=FRESH_ALLOCATION_SCHEMA,
            keys=frozenset(
                {
                    "fresh_created_at",
                    "fresh_ownership_nonce",
                    "fresh_transaction_ref",
                    "old_abandonment_sha256",
                    "prepared_reservation_document_sha256",
                    "pre_ref_snapshot_document_sha256",
                    "pre_ref_snapshot_sha256",
                    "project_identity_sha256",
                    "recovery_ref",
                    "requested_target_tag",
                    "schema",
                    "transport_cache_policy",
                }
            ),
        )
        if (
            _TRANSACTION_REF_RE.fullmatch(
                str(payload.get("fresh_transaction_ref"))
            )
            is None
            or any(
                type(value) is not str or _SHA_RE.fullmatch(value) is None
                for name, value in payload.items()
                if name.endswith("sha256")
            )
            or payload.get("transport_cache_policy")
            != "retained_transport_cache"
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        _prepared_reservation_from_allocation(payload)
        return payload

    def write_fresh_reservation(self, document: Mapping[str, Any]) -> str:
        try:
            validated = fresh_reservation_document(
                recovery_ref=str(document["recovery_ref"]),
                fresh_transaction_ref=str(document["fresh_transaction_ref"]),
                fresh_reservation_sha256=str(
                    document["fresh_reservation_sha256"]
                ),
                fresh_allocation_document_sha256=str(
                    document["fresh_allocation_document_sha256"]
                ),
                old_abandonment_sha256=str(
                    document["old_abandonment_sha256"]
                ),
            )
        except (KeyError, TypeError):
            raise _fail("project_update_legacy_recovery_binding_invalid") from None
        if (
            document.get("schema") != FRESH_RESERVATION_SCHEMA
            or document.get("recovery_ref") != self.paths.recovery_ref
            or dict(document) != validated
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        return self._write_authenticated_create_only(
            self.paths.recovery_root / "fresh-reservation.json",
            document,
        )

    def read_fresh_reservation(self) -> dict[str, Any]:
        payload = self._read_authenticated_exact(
            self.paths.recovery_root / "fresh-reservation.json",
            schema=FRESH_RESERVATION_SCHEMA,
            keys=frozenset(
                {
                    "fresh_allocation_document_sha256",
                    "fresh_reservation_sha256",
                    "fresh_transaction_ref",
                    "old_abandonment_sha256",
                    "recovery_ref",
                    "schema",
                }
            ),
        )
        if (
            _TRANSACTION_REF_RE.fullmatch(
                str(payload.get("fresh_transaction_ref"))
            )
            is None
            or any(
                type(value) is not str or _SHA_RE.fullmatch(value) is None
                for name, value in payload.items()
                if name.endswith("sha256")
            )
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        return payload

    def write_fresh_transaction_inventory(
        self,
        *,
        fresh_transaction_ref: str,
        inventory: Mapping[str, Any],
        _failpoint: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Durably seal a bounded full inventory before human approval.

        The manifest is immutable and sharded so the 200,000-entry safety
        bound does not collide with the generic one-megabyte control-document
        reader.  Chunks are published first; the authenticated index is the
        sole authority and is published last.
        """

        if (
            _TRANSACTION_REF_RE.fullmatch(fresh_transaction_ref) is None
            or (_failpoint is not None and not callable(_failpoint))
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")

        def failpoint(stage: str) -> None:
            if _failpoint is not None:
                _failpoint(stage)

        _validated_tree_inventory(inventory)
        records = [dict(item) for item in inventory["records"]]
        inventory_sha256 = sha256_document(dict(inventory))
        final_root = self.paths.recovery_root / "fresh-transaction-inventory"
        prepared_root = (
            self.paths.recovery_root / "fresh-transaction-inventory.prepared"
        )
        final_exists = os.path.lexists(final_root)
        prepared_exists = os.path.lexists(prepared_root)
        if final_exists and prepared_exists:
            raise _fail("project_update_legacy_recovery_state_ambiguous")
        if final_exists:
            sealed = self.read_fresh_transaction_inventory()
            sealed_inventory = sealed["fresh_transaction_inventory"]
            if (
                sealed.get("fresh_transaction_ref") != fresh_transaction_ref
                or sealed.get("fresh_transaction_inventory_sha256")
                != inventory_sha256
                or sealed_inventory != dict(inventory)
            ):
                raise _fail("project_update_legacy_recovery_state_changed")
            return {
                "entry_count": int(inventory["entry_count"]),
                "fresh_transaction_inventory_document_sha256": sealed[
                    "fresh_transaction_inventory_document_sha256"
                ],
                "fresh_transaction_inventory_sha256": inventory_sha256,
                "fresh_transaction_ref": fresh_transaction_ref,
                "total_bytes": int(inventory["total_bytes"]),
            }
        root = prepared_root
        chunks_root = root / "chunks"
        for directory in (root, chunks_root):
            if not os.path.lexists(directory):
                try:
                    directory.mkdir(mode=0o700)
                except FileExistsError:
                    pass
                except OSError:
                    raise _fail(
                        "project_update_legacy_recovery_commit_failed"
                    ) from None
                _fsync_directory(directory.parent)
            _safe_directory(directory)
        failpoint("prepared_root_durable")

        groups: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []
        current_estimate = 0
        for record in records:
            record_size = len(_canonical(record))
            if record_size > _TARGET_INVENTORY_CHUNK_BYTES:
                raise _fail("project_update_legacy_recovery_binding_invalid")
            if current and (
                len(current) >= _MAX_INVENTORY_CHUNK_RECORDS
                or current_estimate + record_size
                > _TARGET_INVENTORY_CHUNK_BYTES
            ):
                groups.append(current)
                current = []
                current_estimate = 0
            current.append(record)
            current_estimate += record_size
        if current:
            groups.append(current)

        chunk_descriptors: list[dict[str, Any]] = []
        total_document_bytes = 0
        expected_chunk_names: set[str] = set()
        for sequence, group in enumerate(groups, start=1):
            chunk_document = {
                "fresh_transaction_ref": fresh_transaction_ref,
                "records": group,
                "recovery_ref": self.paths.recovery_ref,
                "schema": FRESH_TRANSACTION_INVENTORY_CHUNK_SCHEMA,
                "sequence": sequence,
            }
            raw = _canonical(
                authenticated_document(chunk_document, self._key)
            )
            if len(raw) > _MAX_DOCUMENT_BYTES:
                raise _fail("project_update_legacy_recovery_binding_invalid")
            name = f"{sequence:08d}.json"
            expected_chunk_names.add(name)
            path = chunks_root / name
            digest = self._write_authenticated_create_only(
                path,
                chunk_document,
            )
            failpoint("chunk_durable")
            total_document_bytes += len(raw)
            chunk_descriptors.append(
                {
                    "document_bytes": len(raw),
                    "document_sha256": digest,
                    "record_count": len(group),
                    "sequence": sequence,
                }
            )
        try:
            with os.scandir(chunks_root) as iterator:
                observed_names = {entry.name for entry in iterator}
        except OSError:
            raise _fail("project_update_legacy_recovery_path_unsafe") from None
        if observed_names != expected_chunk_names:
            raise _fail("project_update_legacy_recovery_state_changed")

        index_document = {
            "chunk_count": len(chunk_descriptors),
            "chunks": chunk_descriptors,
            "entry_count": int(inventory["entry_count"]),
            "fresh_transaction_inventory_sha256": inventory_sha256,
            "fresh_transaction_ref": fresh_transaction_ref,
            "recovery_ref": self.paths.recovery_ref,
            "root_identity": list(inventory["root_identity"]),
            "schema": FRESH_TRANSACTION_INVENTORY_INDEX_SCHEMA,
            "total_bytes": int(inventory["total_bytes"]),
        }
        index_raw = _canonical(
            authenticated_document(index_document, self._key)
        )
        total_document_bytes += len(index_raw)
        if (
            len(index_raw) > _MAX_DOCUMENT_BYTES
            or total_document_bytes > _MAX_INVENTORY_MANIFEST_BYTES
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        index_path = root / "index.json"
        index_sha256 = self._write_authenticated_create_only(
            index_path,
            index_document,
        )
        failpoint("index_durable")
        try:
            with os.scandir(root) as iterator:
                root_names = {entry.name for entry in iterator}
        except OSError:
            raise _fail("project_update_legacy_recovery_path_unsafe") from None
        if root_names != {"chunks", "index.json"}:
            raise _fail("project_update_legacy_recovery_state_changed")
        move_directory_no_replace(prepared_root, final_root)
        failpoint("inventory_published")
        sealed = self.read_fresh_transaction_inventory()
        if (
            sealed.get("fresh_transaction_ref") != fresh_transaction_ref
            or sealed.get("fresh_transaction_inventory_document_sha256")
            != index_sha256
            or sealed.get("fresh_transaction_inventory_sha256")
            != inventory_sha256
            or sealed.get("fresh_transaction_inventory") != dict(inventory)
        ):
            raise _fail("project_update_legacy_recovery_state_changed")
        return {
            "entry_count": int(inventory["entry_count"]),
            "fresh_transaction_inventory_document_sha256": index_sha256,
            "fresh_transaction_inventory_sha256": inventory_sha256,
            "fresh_transaction_ref": fresh_transaction_ref,
            "total_bytes": int(inventory["total_bytes"]),
        }

    def read_fresh_transaction_inventory(self) -> dict[str, Any]:
        """Read and cross-verify the complete immutable sharded inventory."""

        root = self.paths.recovery_root / "fresh-transaction-inventory"
        chunks_root = root / "chunks"
        index_path = root / "index.json"
        with _retained_parent_chains(
            self.paths.project_root,
            root,
            chunks_root,
        ):
            try:
                with os.scandir(root) as iterator:
                    if {entry.name for entry in iterator} != {
                        "chunks",
                        "index.json",
                    }:
                        raise _fail(
                            "project_update_legacy_recovery_state_changed"
                        )
            except LegacyProjectUpdateRecoveryError:
                raise
            except OSError:
                raise _fail(
                    "project_update_legacy_recovery_path_unsafe"
                ) from None
            index_raw = _read_regular(index_path)
            index = verify_authenticated_document(
                _parse_json(index_raw),
                self._key,
            )
            expected_index_keys = {
                "chunk_count",
                "chunks",
                "entry_count",
                "fresh_transaction_inventory_sha256",
                "fresh_transaction_ref",
                "recovery_ref",
                "root_identity",
                "schema",
                "total_bytes",
            }
            if (
                set(index) != expected_index_keys
                or index.get("schema")
                != FRESH_TRANSACTION_INVENTORY_INDEX_SCHEMA
                or index.get("recovery_ref") != self.paths.recovery_ref
                or _TRANSACTION_REF_RE.fullmatch(
                    str(index.get("fresh_transaction_ref"))
                )
                is None
                or type(index.get("chunks")) is not list
                or type(index.get("chunk_count")) is not int
                or index["chunk_count"] != len(index["chunks"])
                or index["chunk_count"] > _MAX_TREE_ENTRIES
                or _SHA_RE.fullmatch(
                    str(index.get("fresh_transaction_inventory_sha256"))
                )
                is None
            ):
                raise _fail("project_update_legacy_recovery_binding_invalid")
            expected_names = {
                f"{sequence:08d}.json"
                for sequence in range(1, index["chunk_count"] + 1)
            }
            try:
                with os.scandir(chunks_root) as iterator:
                    if {entry.name for entry in iterator} != expected_names:
                        raise _fail(
                            "project_update_legacy_recovery_state_changed"
                        )
            except LegacyProjectUpdateRecoveryError:
                raise
            except OSError:
                raise _fail(
                    "project_update_legacy_recovery_path_unsafe"
                ) from None
            records: list[dict[str, Any]] = []
            total_document_bytes = len(index_raw)
            for sequence, descriptor in enumerate(index["chunks"], start=1):
                if (
                    not isinstance(descriptor, Mapping)
                    or set(descriptor)
                    != {
                        "document_bytes",
                        "document_sha256",
                        "record_count",
                        "sequence",
                    }
                    or descriptor.get("sequence") != sequence
                    or type(descriptor.get("record_count")) is not int
                    or not 0 < descriptor["record_count"]
                    <= _MAX_INVENTORY_CHUNK_RECORDS
                    or type(descriptor.get("document_bytes")) is not int
                    or not 0 < descriptor["document_bytes"]
                    <= _MAX_DOCUMENT_BYTES
                    or _SHA_RE.fullmatch(
                        str(descriptor.get("document_sha256"))
                    )
                    is None
                ):
                    raise _fail(
                        "project_update_legacy_recovery_binding_invalid"
                    )
                raw = _read_regular(
                    chunks_root / f"{sequence:08d}.json"
                )
                total_document_bytes += len(raw)
                if (
                    total_document_bytes > _MAX_INVENTORY_MANIFEST_BYTES
                    or len(records) + descriptor["record_count"]
                    > _MAX_TREE_ENTRIES
                    or len(raw) != descriptor["document_bytes"]
                    or sha256_bytes(raw) != descriptor["document_sha256"]
                ):
                    raise _fail(
                        "project_update_legacy_recovery_state_changed"
                    )
                chunk = verify_authenticated_document(
                    _parse_json(raw),
                    self._key,
                )
                if (
                    set(chunk)
                    != {
                        "fresh_transaction_ref",
                        "records",
                        "recovery_ref",
                        "schema",
                        "sequence",
                    }
                    or chunk.get("schema")
                    != FRESH_TRANSACTION_INVENTORY_CHUNK_SCHEMA
                    or chunk.get("recovery_ref") != self.paths.recovery_ref
                    or chunk.get("fresh_transaction_ref")
                    != index["fresh_transaction_ref"]
                    or chunk.get("sequence") != sequence
                    or type(chunk.get("records")) is not list
                    or len(chunk["records"]) != descriptor["record_count"]
                ):
                    raise _fail(
                        "project_update_legacy_recovery_binding_invalid"
                    )
                for item in chunk["records"]:
                    if not isinstance(item, Mapping):
                        raise _fail(
                            "project_update_legacy_recovery_binding_invalid"
                        )
                    records.append(dict(item))
            try:
                with os.scandir(chunks_root) as iterator:
                    if {entry.name for entry in iterator} != expected_names:
                        raise _fail(
                            "project_update_legacy_recovery_state_changed"
                        )
            except LegacyProjectUpdateRecoveryError:
                raise
            except OSError:
                raise _fail(
                    "project_update_legacy_recovery_path_unsafe"
                ) from None
            inventory = {
                "entry_count": index.get("entry_count"),
                "records": records,
                "root_identity": index.get("root_identity"),
                "schema": "wom-kit/project-update-legacy-tree/v0.4.19",
                "total_bytes": index.get("total_bytes"),
            }
            _validated_tree_inventory(inventory)
            semantic_sha256 = sha256_document(inventory)
            if (
                semantic_sha256
                != index["fresh_transaction_inventory_sha256"]
            ):
                raise _fail("project_update_legacy_recovery_state_changed")
            return {
                "fresh_transaction_inventory": inventory,
                "fresh_transaction_inventory_document_sha256": (
                    sha256_bytes(index_raw)
                ),
                "fresh_transaction_inventory_sha256": semantic_sha256,
                "fresh_transaction_ref": index["fresh_transaction_ref"],
            }

    def write_prospective_plan(self, document: Mapping[str, Any]) -> str:
        try:
            validated = prospective_plan_document(
                recovery_ref=str(document["recovery_ref"]),
                fresh_allocation_document_sha256=str(
                    document["fresh_allocation_document_sha256"]
                ),
                fresh_transaction_ref=str(document["fresh_transaction_ref"]),
                fresh_intent_sha256=str(document["fresh_intent_sha256"]),
                fresh_transaction_inventory_sha256=str(
                    document["fresh_transaction_inventory_sha256"]
                ),
                fresh_transaction_inventory_document_sha256=str(
                    document[
                        "fresh_transaction_inventory_document_sha256"
                    ]
                ),
                fresh_approval_plan_sha256=str(
                    document["fresh_approval_plan_sha256"]
                ),
                fresh_approval_target_binding_sha256=str(
                    document["fresh_approval_target_binding_sha256"]
                ),
                fresh_approval_context_sha256=str(
                    document["fresh_approval_context_sha256"]
                ),
                fresh_recovery_binding_sha256=str(
                    document["fresh_recovery_binding_sha256"]
                ),
                post_ref_snapshot_document_sha256=str(
                    document["post_ref_snapshot_document_sha256"]
                ),
                post_ref_snapshot_sha256=str(
                    document["post_ref_snapshot_sha256"]
                ),
                old_abandonment_sha256=str(
                    document["old_abandonment_sha256"]
                ),
            )
        except (KeyError, TypeError):
            raise _fail("project_update_legacy_recovery_binding_invalid") from None
        if (
            document.get("schema") != PROSPECTIVE_PLAN_SCHEMA
            or document.get("recovery_ref") != self.paths.recovery_ref
            or dict(document) != validated
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        return self._write_authenticated_create_only(
            self.paths.recovery_root / "prospective-plan.json",
            document,
        )

    def read_prospective_plan(self) -> dict[str, Any]:
        return self._read_authenticated_exact(
            self.paths.recovery_root / "prospective-plan.json",
            schema=PROSPECTIVE_PLAN_SCHEMA,
            keys=frozenset(
                {
                    "fresh_allocation_document_sha256",
                    "fresh_approval_context_sha256",
                    "fresh_approval_plan_sha256",
                    "fresh_approval_target_binding_sha256",
                    "fresh_intent_sha256",
                    "fresh_recovery_binding_sha256",
                    "fresh_transaction_inventory_document_sha256",
                    "fresh_transaction_inventory_sha256",
                    "fresh_transaction_ref",
                    "old_abandonment_sha256",
                    "post_ref_snapshot_document_sha256",
                    "post_ref_snapshot_sha256",
                    "recovery_ref",
                    "schema",
                }
            ),
        )

    def write_cancellation_result(
        self,
        document: Mapping[str, Any],
    ) -> dict[str, str]:
        expected = cancellation_result_document()
        if not isinstance(document, Mapping) or dict(document) != expected:
            raise _fail("project_update_legacy_recovery_binding_invalid")
        semantic_sha256 = sha256_document(expected)
        record = {
            "recovery_ref": self.paths.recovery_ref,
            "result": expected,
            "result_sha256": semantic_sha256,
            "schema": CANCELLATION_RESULT_RECORD_SCHEMA,
        }
        document_sha256 = self._write_authenticated_create_only(
            self.paths.recovery_root / "cancellation-result.json",
            record,
        )
        return {
            "cancellation_result_document_sha256": document_sha256,
            "cancellation_result_sha256": semantic_sha256,
        }

    def read_cancellation_result(self) -> dict[str, Any]:
        path = self.paths.recovery_root / "cancellation-result.json"
        payload = self._read_authenticated_exact(
            path,
            schema=CANCELLATION_RESULT_RECORD_SCHEMA,
            keys=frozenset(
                {"recovery_ref", "result", "result_sha256", "schema"}
            ),
        )
        result = payload.get("result")
        if (
            not isinstance(result, Mapping)
            or dict(result) != cancellation_result_document()
            or _SHA_RE.fullmatch(str(payload.get("result_sha256"))) is None
            or sha256_document(dict(result)) != payload.get("result_sha256")
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        return {
            "cancellation_result": dict(result),
            "cancellation_result_document_sha256": sha256_bytes(
                _read_regular(path)
            ),
            "cancellation_result_sha256": payload["result_sha256"],
        }

    def write_cancellation_plan(self, document: Mapping[str, Any]) -> str:
        try:
            validated = cancellation_plan_document(
                recovery_ref=str(document["recovery_ref"]),
                intent_sha256=str(document["intent_sha256"]),
                fresh_transaction_ref=str(document["fresh_transaction_ref"]),
                prospective_plan_document_sha256=str(
                    document["prospective_plan_document_sha256"]
                ),
                fresh_approval_plan_sha256=str(
                    document["fresh_approval_plan_sha256"]
                ),
                fresh_approval_context_sha256=str(
                    document["fresh_approval_context_sha256"]
                ),
                claim_absence_evidence_sha256=str(
                    document["claim_absence_evidence_sha256"]
                ),
                old_transaction_ref=str(document["old_transaction_ref"]),
                old_transaction_sha256=str(
                    document["old_transaction_sha256"]
                ),
                old_lock_sha256=str(document["old_lock_sha256"]),
                old_abandonment_sha256=str(
                    document["old_abandonment_sha256"]
                ),
                fresh_transaction_inventory_sha256=str(
                    document["fresh_transaction_inventory_sha256"]
                ),
                fresh_transaction_inventory_document_sha256=str(
                    document[
                        "fresh_transaction_inventory_document_sha256"
                    ]
                ),
                cancellation_result_sha256=str(
                    document["cancellation_result_sha256"]
                ),
                cancellation_result_document_sha256=str(
                    document["cancellation_result_document_sha256"]
                ),
            )
        except (KeyError, TypeError):
            raise _fail("project_update_legacy_recovery_binding_invalid") from None
        if (
            document.get("schema") != CANCELLATION_PLAN_SCHEMA
            or document.get("recovery_ref") != self.paths.recovery_ref
            or dict(document) != validated
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        return self._write_authenticated_create_only(
            self.paths.recovery_root / "cancellation-plan.json",
            document,
        )

    def read_cancellation_plan(self) -> dict[str, Any]:
        payload = self._read_authenticated_exact(
            self.paths.recovery_root / "cancellation-plan.json",
            schema=CANCELLATION_PLAN_SCHEMA,
            keys=frozenset(
                {
                    "cancellation_result_document_sha256",
                    "cancellation_result_sha256",
                    "claim_absence_evidence_sha256",
                    "fresh_approval_context_sha256",
                    "fresh_approval_plan_sha256",
                    "fresh_transaction_inventory_document_sha256",
                    "fresh_transaction_inventory_sha256",
                    "fresh_transaction_ref",
                    "intent_sha256",
                    "old_abandonment_sha256",
                    "old_lock_sha256",
                    "old_transaction_ref",
                    "old_transaction_sha256",
                    "prospective_plan_document_sha256",
                    "recovery_ref",
                    "schema",
                }
            ),
        )
        if (
            _TRANSACTION_REF_RE.fullmatch(
                str(payload.get("fresh_transaction_ref"))
            )
            is None
            or _TRANSACTION_REF_RE.fullmatch(
                str(payload.get("old_transaction_ref"))
            )
            is None
            or any(
                type(value) is not str or _SHA_RE.fullmatch(value) is None
                for name, value in payload.items()
                if name.endswith("sha256")
            )
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        return payload

    def write_cancellation_stage_evidence(
        self,
        document: Mapping[str, Any],
    ) -> str:
        try:
            validated = cancellation_stage_evidence_document(
                recovery_ref=str(document["recovery_ref"]),
                intent_sha256=str(document["intent_sha256"]),
                fresh_transaction_ref=str(document["fresh_transaction_ref"]),
                cancellation_plan_document_sha256=str(
                    document["cancellation_plan_document_sha256"]
                ),
                claim_absence_evidence_sha256=str(
                    document["claim_absence_evidence_sha256"]
                ),
                fresh_transaction_inventory_sha256=str(
                    document["fresh_transaction_inventory_sha256"]
                ),
                fresh_transaction_inventory_document_sha256=str(
                    document[
                        "fresh_transaction_inventory_document_sha256"
                    ]
                ),
                stage_state=str(document["stage_state"]),
            )
        except (KeyError, TypeError):
            raise _fail("project_update_legacy_recovery_binding_invalid") from None
        if (
            document.get("schema") != CANCELLATION_STAGE_EVIDENCE_SCHEMA
            or document.get("recovery_ref") != self.paths.recovery_ref
            or dict(document) != validated
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        return self._write_authenticated_create_only(
            self.paths.recovery_root / "cancellation-stage-evidence.json",
            document,
        )

    def read_cancellation_stage_evidence(self) -> dict[str, Any]:
        payload = self._read_authenticated_exact(
            self.paths.recovery_root / "cancellation-stage-evidence.json",
            schema=CANCELLATION_STAGE_EVIDENCE_SCHEMA,
            keys=frozenset(
                {
                    "cancellation_plan_document_sha256",
                    "claim_absence_evidence_sha256",
                    "fresh_transaction_inventory_document_sha256",
                    "fresh_transaction_inventory_sha256",
                    "fresh_transaction_ref",
                    "intent_sha256",
                    "recovery_ref",
                    "schema",
                    "stage_state",
                }
            ),
        )
        if (
            payload.get("stage_state") not in {"staged", "already_staged"}
            or _TRANSACTION_REF_RE.fullmatch(
                str(payload.get("fresh_transaction_ref"))
            )
            is None
            or any(
                type(value) is not str or _SHA_RE.fullmatch(value) is None
                for name, value in payload.items()
                if name.endswith("sha256")
            )
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        return payload

    def write_cancellation_cleanup_evidence(
        self,
        document: Mapping[str, Any],
    ) -> str:
        try:
            validated = cancellation_cleanup_evidence_document(
                recovery_ref=str(document["recovery_ref"]),
                intent_sha256=str(document["intent_sha256"]),
                fresh_transaction_ref=str(document["fresh_transaction_ref"]),
                cancellation_plan_document_sha256=str(
                    document["cancellation_plan_document_sha256"]
                ),
                cancellation_stage_evidence_document_sha256=str(
                    document[
                        "cancellation_stage_evidence_document_sha256"
                    ]
                ),
                fresh_transaction_inventory_sha256=str(
                    document["fresh_transaction_inventory_sha256"]
                ),
                fresh_transaction_inventory_document_sha256=str(
                    document[
                        "fresh_transaction_inventory_document_sha256"
                    ]
                ),
                cleanup_state=str(document["cleanup_state"]),
            )
        except (KeyError, TypeError):
            raise _fail("project_update_legacy_recovery_binding_invalid") from None
        if (
            document.get("schema") != CANCELLATION_CLEANUP_EVIDENCE_SCHEMA
            or document.get("recovery_ref") != self.paths.recovery_ref
            or dict(document) != validated
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        return self._write_authenticated_create_only(
            self.paths.recovery_root / "cancellation-cleanup-evidence.json",
            document,
        )

    def read_cancellation_cleanup_evidence(self) -> dict[str, Any]:
        payload = self._read_authenticated_exact(
            self.paths.recovery_root / "cancellation-cleanup-evidence.json",
            schema=CANCELLATION_CLEANUP_EVIDENCE_SCHEMA,
            keys=frozenset(
                {
                    "cancellation_plan_document_sha256",
                    "cancellation_stage_evidence_document_sha256",
                    "cleanup_state",
                    "fresh_transaction_inventory_document_sha256",
                    "fresh_transaction_inventory_sha256",
                    "fresh_transaction_ref",
                    "intent_sha256",
                    "recovery_ref",
                    "schema",
                }
            ),
        )
        if (
            payload.get("cleanup_state") not in {
                "deleted_exact",
                "already_absent",
            }
            or _TRANSACTION_REF_RE.fullmatch(
                str(payload.get("fresh_transaction_ref"))
            )
            is None
            or any(
                type(value) is not str or _SHA_RE.fullmatch(value) is None
                for name, value in payload.items()
                if name.endswith("sha256")
            )
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        return payload

    def write_cancellation_restore_evidence(
        self,
        document: Mapping[str, Any],
    ) -> str:
        try:
            validated = cancellation_restore_evidence_document(
                recovery_ref=str(document["recovery_ref"]),
                intent_sha256=str(document["intent_sha256"]),
                fresh_transaction_ref=str(document["fresh_transaction_ref"]),
                cancellation_plan_document_sha256=str(
                    document["cancellation_plan_document_sha256"]
                ),
                cancellation_cleanup_evidence_document_sha256=str(
                    document[
                        "cancellation_cleanup_evidence_document_sha256"
                    ]
                ),
                old_transaction_ref=str(document["old_transaction_ref"]),
                old_transaction_sha256=str(
                    document["old_transaction_sha256"]
                ),
                old_lock_sha256=str(document["old_lock_sha256"]),
                restore_state=str(document["restore_state"]),
            )
        except (KeyError, TypeError):
            raise _fail("project_update_legacy_recovery_binding_invalid") from None
        if (
            document.get("schema") != CANCELLATION_RESTORE_EVIDENCE_SCHEMA
            or document.get("recovery_ref") != self.paths.recovery_ref
            or dict(document) != validated
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        return self._write_authenticated_create_only(
            self.paths.recovery_root / "cancellation-restore-evidence.json",
            document,
        )

    def read_cancellation_restore_evidence(self) -> dict[str, Any]:
        payload = self._read_authenticated_exact(
            self.paths.recovery_root / "cancellation-restore-evidence.json",
            schema=CANCELLATION_RESTORE_EVIDENCE_SCHEMA,
            keys=frozenset(
                {
                    "cancellation_cleanup_evidence_document_sha256",
                    "cancellation_plan_document_sha256",
                    "fresh_transaction_ref",
                    "intent_sha256",
                    "old_lock_sha256",
                    "old_transaction_ref",
                    "old_transaction_sha256",
                    "recovery_ref",
                    "restore_state",
                    "schema",
                }
            ),
        )
        if (
            payload.get("restore_state") not in {"restored", "already_restored"}
            or _TRANSACTION_REF_RE.fullmatch(
                str(payload.get("fresh_transaction_ref"))
            )
            is None
            or _TRANSACTION_REF_RE.fullmatch(
                str(payload.get("old_transaction_ref"))
            )
            is None
            or any(
                type(value) is not str or _SHA_RE.fullmatch(value) is None
                for name, value in payload.items()
                if name.endswith("sha256")
            )
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        return payload

    def write_terminal_receipt(self, document: Mapping[str, Any]) -> str:
        try:
            common = {
                "recovery_ref": str(document["recovery_ref"]),
                "outcome": str(document["outcome"]),
                "intent_sha256": str(document["intent_sha256"]),
                "journal_head_sha256": str(
                    document["journal_head_sha256"]
                ),
                "fresh_transaction_ref": str(
                    document["fresh_transaction_ref"]
                ),
                "old_transaction_inventory_sha256": str(
                    document["old_transaction_inventory_sha256"]
                ),
            }
            if document.get("outcome") == "success":
                validated = terminal_receipt_document(
                    **common,
                    fresh_transaction_completed_sha256=str(
                        document["fresh_transaction_completed_sha256"]
                    ),
                    claim_evidence_sha256=str(
                        document["claim_evidence_sha256"]
                    ),
                    old_lock_backup_sha256=str(
                        document["old_lock_backup_sha256"]
                    ),
                )
            elif document.get("outcome") == "unapproved_restored":
                validated = terminal_receipt_document(
                    **common,
                    claim_absence_evidence_sha256=str(
                        document["claim_absence_evidence_sha256"]
                    ),
                    cancelled_fresh_staging_sha256=str(
                        document["cancelled_fresh_staging_sha256"]
                    ),
                    cancelled_fresh_transaction_inventory_sha256=str(
                        document[
                            "cancelled_fresh_transaction_inventory_sha256"
                        ]
                    ),
                    cancelled_fresh_transaction_inventory_document_sha256=str(
                        document[
                            "cancelled_fresh_transaction_inventory_document_sha256"
                        ]
                    ),
                    cancelled_fresh_cleanup_evidence_sha256=str(
                        document[
                            "cancelled_fresh_cleanup_evidence_sha256"
                        ]
                    ),
                    restored_old_transaction_sha256=str(
                        document["restored_old_transaction_sha256"]
                    ),
                    preserved_old_lock_sha256=str(
                        document["preserved_old_lock_sha256"]
                    ),
                    cancellation_plan_document_sha256=str(
                        document["cancellation_plan_document_sha256"]
                    ),
                    cancellation_result_document_sha256=str(
                        document["cancellation_result_document_sha256"]
                    ),
                    cancellation_result_sha256=str(
                        document["cancellation_result_sha256"]
                    ),
                    cancelled_fresh_staging_document_sha256=str(
                        document[
                            "cancelled_fresh_staging_document_sha256"
                        ]
                    ),
                    cancelled_fresh_cleanup_evidence_document_sha256=str(
                        document[
                            "cancelled_fresh_cleanup_evidence_document_sha256"
                        ]
                    ),
                    restored_evidence_sha256=str(
                        document["restored_evidence_sha256"]
                    ),
                    restored_evidence_document_sha256=str(
                        document["restored_evidence_document_sha256"]
                    ),
                )
            else:
                raise KeyError("outcome")
        except (KeyError, TypeError):
            raise _fail("project_update_legacy_recovery_binding_invalid") from None
        if (
            document.get("schema") != TERMINAL_RECEIPT_SCHEMA
            or document.get("recovery_ref") != self.paths.recovery_ref
            or dict(document) != validated
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        return self._write_authenticated_create_only(
            self.paths.recovery_root / "terminal-receipt.json",
            document,
        )

    def read_terminal_receipt(self) -> dict[str, Any]:
        path = self.paths.recovery_root / "terminal-receipt.json"
        payload = verify_authenticated_document(
            _parse_json(_read_regular(path)),
            self._key,
        )
        common = {
            "fresh_transaction_ref",
            "intent_sha256",
            "journal_head_sha256",
            "old_transaction_inventory_sha256",
            "outcome",
            "recovery_ref",
            "schema",
        }
        success = common | {
            "claim_evidence_sha256",
            "fresh_transaction_completed_sha256",
            "old_lock_backup_sha256",
        }
        restored = common | {
            "cancellation_plan_document_sha256",
            "cancellation_result_document_sha256",
            "cancellation_result_sha256",
            "cancelled_fresh_cleanup_evidence_sha256",
            "cancelled_fresh_cleanup_evidence_document_sha256",
            "cancelled_fresh_staging_sha256",
            "cancelled_fresh_staging_document_sha256",
            "cancelled_fresh_transaction_inventory_document_sha256",
            "cancelled_fresh_transaction_inventory_sha256",
            "claim_absence_evidence_sha256",
            "preserved_old_lock_sha256",
            "restored_evidence_document_sha256",
            "restored_evidence_sha256",
            "restored_old_transaction_sha256",
        }
        expected = success if payload.get("outcome") == "success" else restored
        if (
            frozenset(payload) != frozenset(expected)
            or payload.get("schema") != TERMINAL_RECEIPT_SCHEMA
            or payload.get("recovery_ref") != self.paths.recovery_ref
            or payload.get("outcome")
            not in {"success", "unapproved_restored"}
            or _TRANSACTION_REF_RE.fullmatch(
                str(payload.get("fresh_transaction_ref"))
            )
            is None
            or any(
                type(value) is not str or _SHA_RE.fullmatch(value) is None
                for name, value in payload.items()
                if name.endswith("sha256")
            )
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        return payload

    def publish_terminal_locator_and_retire(
        self,
        *,
        intent_sha256: str,
        journal_head_sha256: str,
        previous_locator_sha256: str,
        terminal_receipt_sha256: str,
    ) -> dict[str, str]:
        receipt_path = self.paths.recovery_root / "terminal-receipt.json"
        receipt_raw = _read_regular(receipt_path)
        receipt = self.read_terminal_receipt()
        terminal_path = self.paths.recovery_root / "terminal-locator.json"
        if os.path.lexists(terminal_path):
            if os.path.lexists(self.paths.locator_path) or os.path.lexists(
                _locator_transition_path(self.paths.locator_path)
            ):
                raise _fail(
                    "project_update_legacy_recovery_state_ambiguous"
                )
            terminal_raw = _read_regular(terminal_path)
            terminal = verify_authenticated_document(
                _parse_json(terminal_raw), self._key
            )
            terminal_sha256 = sha256_bytes(terminal_raw)
            if (
                sha256_bytes(receipt_raw) != terminal_receipt_sha256
                or terminal.get("state") != "terminal_completed"
                or terminal.get("intent_sha256") != intent_sha256
                or terminal.get("journal_head_sha256")
                != journal_head_sha256
                or terminal.get("terminal_receipt_sha256")
                != terminal_receipt_sha256
            ):
                raise _fail("project_update_legacy_recovery_state_changed")
            return {
                "terminal_locator_sha256": terminal_sha256,
                "retired_locator_sha256": terminal_sha256,
            }
        selected_locator = (
            self.paths.locator_path
            if os.path.lexists(self.paths.locator_path)
            else _locator_transition_path(self.paths.locator_path)
        )
        current_raw = _read_regular(selected_locator)
        current = self.read_locator()
        expected_preterminal_state = (
            "fresh_transaction_completed"
            if receipt.get("outcome") == "success"
            else "unapproved_restored"
        )
        current_sha256 = sha256_bytes(current_raw)
        if (
            sha256_bytes(receipt_raw) != terminal_receipt_sha256
            or receipt.get("intent_sha256") != intent_sha256
            or receipt.get("journal_head_sha256") != journal_head_sha256
            or current.get("intent_sha256") != intent_sha256
            or current.get("journal_head_sha256") != journal_head_sha256
        ):
            raise _fail("project_update_legacy_recovery_state_changed")
        if current.get("state") == "terminal_completed":
            if current.get("terminal_receipt_sha256") != terminal_receipt_sha256:
                raise _fail("project_update_legacy_recovery_state_changed")
            retired_sha256 = self.retire_locator(
                expected_locator_sha256=current_sha256,
            )
            return {
                "terminal_locator_sha256": current_sha256,
                "retired_locator_sha256": retired_sha256,
            }
        if (
            current_sha256 != previous_locator_sha256
            or current.get("state") != expected_preterminal_state
        ):
            raise _fail("project_update_legacy_recovery_state_changed")
        locator_sha256 = self.publish_locator(
            state="terminal_completed",
            intent_sha256=intent_sha256,
            journal_head_sha256=journal_head_sha256,
            previous_locator_sha256=previous_locator_sha256,
            terminal_receipt_sha256=terminal_receipt_sha256,
        )
        retired_sha256 = self.retire_locator(
            expected_locator_sha256=locator_sha256,
        )
        return {
            "terminal_locator_sha256": locator_sha256,
            "retired_locator_sha256": retired_sha256,
        }

    def retire_locator(self, *, expected_locator_sha256: str) -> str:
        """Move the exact authenticated active locator into this recovery."""

        if _SHA_RE.fullmatch(expected_locator_sha256) is None:
            raise _fail("project_update_legacy_recovery_binding_invalid")
        terminal = self.paths.recovery_root / "terminal-locator.json"
        active_exists = os.path.lexists(self.paths.locator_path)
        terminal_exists = os.path.lexists(terminal)
        if active_exists and terminal_exists:
            raise _fail("project_update_legacy_recovery_state_ambiguous")
        selected = self.paths.locator_path if active_exists else terminal
        if not os.path.lexists(selected):
            raise _fail("project_update_legacy_recovery_state_ambiguous")
        current = _read_regular(selected)
        if sha256_bytes(current) != expected_locator_sha256:
            raise _fail("project_update_legacy_recovery_state_changed")
        payload = verify_authenticated_document(_parse_json(current), self._key)
        if (
            payload.get("state") != "terminal_completed"
            or payload.get("recovery_ref") != self.paths.recovery_ref
        ):
            raise _fail("project_update_legacy_recovery_state_changed")
        if active_exists:
            _move_exact_regular_no_replace(
                self.paths.project_root,
                self.paths.locator_path,
                terminal,
                current,
            )
        if os.path.lexists(self.paths.locator_path) or not hmac.compare_digest(
            _read_regular(terminal), current
        ):
            raise _fail("project_update_legacy_recovery_state_ambiguous")
        return expected_locator_sha256

    def append_checkpoint(
        self,
        *,
        phase: str,
        stage: str,
        intent_sha256: str,
        evidence_sha256: str,
        expected_previous_checkpoint_sha256: str | None,
    ) -> str:
        if (
            _STATE_RE.fullmatch(phase) is None
            or stage not in {"intent", "verified"}
            or _SHA_RE.fullmatch(intent_sha256) is None
            or _SHA_RE.fullmatch(evidence_sha256) is None
            or (
                expected_previous_checkpoint_sha256 is not None
                and _SHA_RE.fullmatch(expected_previous_checkpoint_sha256)
                is None
            )
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        chain = self._read_checkpoint_chain(intent_sha256=intent_sha256)
        previous = chain[-1][1] if chain else None
        intended = {
            "evidence_sha256": evidence_sha256,
            "intent_sha256": intent_sha256,
            "phase": phase,
            "previous_checkpoint_sha256": (
                expected_previous_checkpoint_sha256
            ),
            "recovery_ref": self.paths.recovery_ref,
            "schema": RECOVERY_CHECKPOINT_SCHEMA,
            "sequence": len(chain) if chain else 0,
            "stage": stage,
        }
        if previous != expected_previous_checkpoint_sha256:
            if chain:
                tail_payload, tail_digest = chain[-1]
                intended["sequence"] = len(chain)
                if dict(tail_payload) == intended:
                    return tail_digest
            raise _fail("project_update_legacy_recovery_state_changed")
        current_state = _checkpoint_chain_state(
            tuple(payload for payload, _digest in chain)
        )
        if (
            stage != "verified"
            or (current_state, phase)
            not in _ALLOWED_LOCATOR_FORWARD_TRANSITIONS
        ):
            raise _fail("project_update_legacy_recovery_state_changed")
        sequence = len(chain) + 1
        checkpoint = authenticated_document(
            {
                "evidence_sha256": evidence_sha256,
                "intent_sha256": intent_sha256,
                "phase": phase,
                "previous_checkpoint_sha256": previous,
                "recovery_ref": self.paths.recovery_ref,
                "schema": RECOVERY_CHECKPOINT_SCHEMA,
                "sequence": sequence,
                "stage": stage,
            },
            self._key,
        )
        raw = _canonical(checkpoint)
        checkpoints = self.paths.recovery_root / "checkpoints"
        if not os.path.lexists(checkpoints):
            try:
                checkpoints.mkdir(mode=0o700)
            except FileExistsError:
                pass
            except OSError:
                raise _fail(
                    "project_update_legacy_recovery_commit_failed"
                ) from None
            _fsync_directory(checkpoints.parent)
        _safe_directory(checkpoints)
        checkpoint_path = checkpoints / f"{sequence:08d}.json"
        digest = self._write_authenticated_create_only(
            checkpoint_path,
            _payload(checkpoint),
        )
        return digest

    def _read_checkpoint_chain(
        self,
        *,
        intent_sha256: str,
    ) -> tuple[tuple[dict[str, Any], str], ...]:
        if _SHA_RE.fullmatch(intent_sha256) is None:
            raise _fail("project_update_legacy_recovery_binding_invalid")
        checkpoints = self.paths.recovery_root / "checkpoints"
        if not os.path.lexists(checkpoints):
            return ()
        try:
            _safe_directory(checkpoints)
            with os.scandir(checkpoints) as iterator:
                entries = sorted(iterator, key=lambda item: item.name)
        except OSError:
            raise _fail("project_update_legacy_recovery_path_unsafe") from None
        if any(
            re.fullmatch(r"[0-9]{8}\.json", entry.name) is None
            for entry in entries
        ):
            raise _fail("project_update_legacy_recovery_state_changed")
        chain: list[tuple[dict[str, Any], str]] = []
        previous: str | None = None
        for sequence, entry in enumerate(entries, start=1):
            if entry.name != f"{sequence:08d}.json":
                raise _fail("project_update_legacy_recovery_state_changed")
            raw = _read_regular(Path(entry.path))
            payload = verify_authenticated_document(_parse_json(raw), self._key)
            if (
                set(payload)
                != {
                    "evidence_sha256",
                    "intent_sha256",
                    "phase",
                    "previous_checkpoint_sha256",
                    "recovery_ref",
                    "schema",
                    "sequence",
                    "stage",
                }
                or payload.get("schema") != RECOVERY_CHECKPOINT_SCHEMA
                or payload.get("recovery_ref") != self.paths.recovery_ref
                or payload.get("sequence") != sequence
                or payload.get("previous_checkpoint_sha256") != previous
                or payload.get("intent_sha256") != intent_sha256
                or _SHA_RE.fullmatch(str(payload.get("evidence_sha256")))
                is None
                or payload.get("stage") != "verified"
            ):
                raise _fail("project_update_legacy_recovery_state_changed")
            digest = sha256_bytes(raw)
            chain.append((payload, digest))
            previous = digest
        _checkpoint_chain_state(
            tuple(payload for payload, _digest in chain)
        )
        return tuple(chain)

    def read_checkpoints(
        self,
        *,
        intent_sha256: str,
    ) -> tuple[Mapping[str, Any], ...]:
        return tuple(
            payload
            for payload, _digest in self._read_checkpoint_chain(
                intent_sha256=intent_sha256
            )
        )


def resolve_active_recovery(
    project_root: Path | str,
    archive_root: Path | str,
    key_provider: Any,
    *,
    create_if_missing: bool = False,
) -> ResolvedActiveRecovery:
    """Resolve one active locator into an entirely authenticated private view."""

    if (
        type(create_if_missing) is not bool
        or create_if_missing
        or not callable(getattr(key_provider, "use_key", None))
    ):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    project = Path(os.path.abspath(str(project_root)))
    _safe_directory(project)
    locator_path = project.joinpath(*PurePosixPath(ACTIVE_LOCATOR_LOGICAL).parts)
    transition_path = _locator_transition_path(locator_path)
    try:
        selected_locator = (
            locator_path if os.path.lexists(locator_path) else transition_path
        )
        untrusted = _parse_json(_read_regular(selected_locator))
        recovery_ref = untrusted.get("recovery_ref")
        if (
            type(recovery_ref) is not str
            or _RECOVERY_REF_RE.fullmatch(recovery_ref) is None
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
    except LegacyProjectUpdateRecoveryError:
        raise
    except BaseException:
        raise _fail(
            "project_update_legacy_recovery_authentication_invalid"
        ) from None
    def consume(key: memoryview) -> ResolvedActiveRecovery:
        with LegacyRecoveryStore(project, recovery_ref, key) as store:
            locator = store.read_locator()
            transition = _locator_transition_path(store.paths.locator_path)
            selected_locator = (
                store.paths.locator_path
                if os.path.lexists(store.paths.locator_path)
                else transition
            )
            locator_raw = _read_regular(selected_locator)
            if verify_authenticated_document(
                _parse_json(locator_raw), store._key
            ) != locator:
                raise _fail("project_update_legacy_recovery_state_changed")
            locator_sha256 = sha256_bytes(locator_raw)
            if (
                selected_locator == store.paths.locator_path
                and os.path.lexists(transition)
            ):
                transition_raw = _read_regular(transition)
                verify_authenticated_document(
                    _parse_json(transition_raw), store._key
                )
                if locator.get("previous_locator_sha256") != sha256_bytes(
                    transition_raw
                ):
                    raise _fail(
                        "project_update_legacy_recovery_state_ambiguous"
                    )
                _delete_exact_regular_bytes(
                    store.paths.project_root,
                    transition,
                    transition_raw,
                )
            if locator.get("state") == "allocating":
                nested = locator.get("allocating_intent")
                if not isinstance(nested, Mapping):
                    raise _fail(
                        "project_update_legacy_recovery_state_changed"
                    )
                allocating_intent = verify_authenticated_document(
                    nested, store._key
                )
                intent_raw = _canonical(dict(nested))
                if (
                    allocating_intent.get("recovery_ref")
                    != store.paths.recovery_ref
                    or sha256_bytes(intent_raw)
                    != locator.get("intent_sha256")
                ):
                    raise _fail(
                        "project_update_legacy_recovery_state_changed"
                    )
                if not os.path.lexists(store.paths.recovery_root):
                    # The authenticated seed is created before the allocating
                    # locator.  Missing it is not an allocation state that may
                    # be guessed or silently reconstructed.
                    raise _fail(
                        "project_update_legacy_recovery_state_changed"
                    )
                _safe_directory(store.paths.recovery_root)
                try:
                    with os.scandir(store.paths.recovery_root) as iterator:
                        if not {entry.name for entry in iterator}.issubset(
                            {"fresh-approval-seed.json", "intent.json"}
                        ):
                            raise _fail(
                                "project_update_legacy_recovery_state_changed"
                            )
                except LegacyProjectUpdateRecoveryError:
                    raise
                except OSError:
                    raise _fail(
                        "project_update_legacy_recovery_path_unsafe"
                    ) from None
                _write_new(
                    store.paths.recovery_root / "intent.json",
                    intent_raw,
                )
                locator_sha256 = store.publish_locator(
                    state="intent_sealed",
                    intent_sha256=str(locator["intent_sha256"]),
                    journal_head_sha256=None,
                    previous_locator_sha256=locator_sha256,
                )
                locator = store.read_locator()
                if locator.get("state") != "intent_sealed":
                    raise _fail(
                        "project_update_legacy_recovery_state_changed"
                    )
            intent, intent_sha256 = store.read_intent()
            if locator.get("intent_sha256") != intent_sha256:
                raise _fail("project_update_legacy_recovery_state_changed")
            fresh_approval_seed = store.read_fresh_approval_seed()
            fresh_approval_seed_path = (
                store.paths.recovery_root / "fresh-approval-seed.json"
            )
            fresh_approval_seed_document_sha256 = sha256_bytes(
                _read_regular(fresh_approval_seed_path)
            )
            if (
                intent.get("fresh_approval_seed_document_sha256")
                != fresh_approval_seed_document_sha256
                or fresh_approval_seed.get("old_transaction_ref")
                != intent.get("old_transaction_ref")
                or fresh_approval_seed.get("old_transaction_sha256")
                != intent.get("old_transaction_sha256")
                or fresh_approval_seed.get("archive_identity_sha256")
                != intent.get("archive_identity_sha256")
                or fresh_approval_seed.get("project_identity_sha256")
                != intent.get("project_identity_sha256")
            ):
                raise _fail("project_update_legacy_recovery_state_changed")
            chain = store._read_checkpoint_chain(intent_sha256=intent_sha256)
            journal_head = chain[-1][1] if chain else None
            chain_state = _checkpoint_chain_state(
                tuple(payload for payload, _digest in chain)
            )
            locator_journal_head = locator.get("journal_head_sha256")
            pending_checkpoint: Mapping[str, Any] | None = None
            if (
                locator_journal_head == journal_head
                and locator.get("state") != "terminal_completed"
                and locator.get("state") != chain_state
            ):
                raise _fail("project_update_legacy_recovery_state_changed")
            if locator_journal_head != journal_head:
                locator_index = -1
                if locator_journal_head is not None:
                    locator_index = next(
                        (
                            index
                            for index, (_payload_value, digest) in enumerate(chain)
                            if digest == locator_journal_head
                        ),
                        -2,
                    )
                if locator_index != len(chain) - 2 or not chain:
                    raise _fail("project_update_legacy_recovery_state_changed")
                forward, forward_digest = chain[-1]
                if (
                    forward.get("previous_checkpoint_sha256")
                    != locator_journal_head
                    or str(locator.get("state"))
                    != _checkpoint_chain_state(
                        tuple(
                            payload for payload, _digest in chain[:-1]
                        )
                    )
                    or _CHECKPOINT_LOCATOR_STATE.get(str(forward.get("phase")))
                    is None
                    or (
                        str(locator.get("state")),
                        str(forward.get("phase")),
                    )
                    not in _ALLOWED_LOCATOR_FORWARD_TRANSITIONS
                    or locator.get("state") == "terminal_completed"
                ):
                    raise _fail("project_update_legacy_recovery_state_changed")
                pending_checkpoint = dict(forward)
                locator_sha256 = store.publish_locator(
                    state=_CHECKPOINT_LOCATOR_STATE[str(forward["phase"])],
                    intent_sha256=intent_sha256,
                    journal_head_sha256=forward_digest,
                    previous_locator_sha256=locator_sha256,
                )
                locator = store.read_locator()
                if locator.get("journal_head_sha256") != journal_head:
                    raise _fail("project_update_legacy_recovery_state_changed")
            pre_ref_snapshot_path = (
                store.paths.recovery_root / "pre-fetch-ref-snapshot.json"
            )
            post_ref_snapshot_path = (
                store.paths.recovery_root / "post-fetch-ref-snapshot.json"
            )
            allocation_path = (
                store.paths.recovery_root / "fresh-allocation.json"
            )
            reservation_path = (
                store.paths.recovery_root / "fresh-reservation.json"
            )
            inventory_root = (
                store.paths.recovery_root / "fresh-transaction-inventory"
            )
            inventory_prepared_root = (
                store.paths.recovery_root
                / "fresh-transaction-inventory.prepared"
            )
            plan_path = store.paths.recovery_root / "prospective-plan.json"
            cancellation_result_path = (
                store.paths.recovery_root / "cancellation-result.json"
            )
            cancellation_plan_path = (
                store.paths.recovery_root / "cancellation-plan.json"
            )
            cancellation_stage_evidence_path = (
                store.paths.recovery_root / "cancellation-stage-evidence.json"
            )
            cancellation_cleanup_evidence_path = (
                store.paths.recovery_root / "cancellation-cleanup-evidence.json"
            )
            cancellation_restore_evidence_path = (
                store.paths.recovery_root / "cancellation-restore-evidence.json"
            )
            terminal_receipt_path = (
                store.paths.recovery_root / "terminal-receipt.json"
            )
            pre_ref_snapshot = (
                store.read_pre_fetch_ref_snapshot()
                if os.path.lexists(pre_ref_snapshot_path)
                else None
            )
            post_ref_snapshot = (
                store.read_post_fetch_ref_snapshot()
                if os.path.lexists(post_ref_snapshot_path)
                else None
            )
            fresh_allocation = (
                store.read_fresh_allocation()
                if os.path.lexists(allocation_path)
                else None
            )
            fresh_reservation = (
                store.read_fresh_reservation()
                if os.path.lexists(reservation_path)
                else None
            )
            inventory_exists = os.path.lexists(inventory_root)
            inventory_prepared_exists = os.path.lexists(
                inventory_prepared_root
            )
            if inventory_exists and inventory_prepared_exists:
                raise _fail("project_update_legacy_recovery_state_ambiguous")
            if inventory_prepared_exists:
                _safe_directory(inventory_prepared_root)
                if chain_state != "fresh_reservation_bound":
                    raise _fail(
                        "project_update_legacy_recovery_state_changed"
                    )
            stored_inventory = (
                store.read_fresh_transaction_inventory()
                if inventory_exists
                else None
            )
            prospective_plan = (
                store.read_prospective_plan()
                if os.path.lexists(plan_path)
                else None
            )
            cancellation_result_record = (
                store.read_cancellation_result()
                if os.path.lexists(cancellation_result_path)
                else None
            )
            cancellation_plan = (
                store.read_cancellation_plan()
                if os.path.lexists(cancellation_plan_path)
                else None
            )
            cancellation_stage_evidence = (
                store.read_cancellation_stage_evidence()
                if os.path.lexists(cancellation_stage_evidence_path)
                else None
            )
            cancellation_cleanup_evidence = (
                store.read_cancellation_cleanup_evidence()
                if os.path.lexists(cancellation_cleanup_evidence_path)
                else None
            )
            cancellation_restore_evidence = (
                store.read_cancellation_restore_evidence()
                if os.path.lexists(cancellation_restore_evidence_path)
                else None
            )
            terminal_receipt = (
                store.read_terminal_receipt()
                if os.path.lexists(terminal_receipt_path)
                else None
            )
            fresh_allocation_document_sha256 = (
                sha256_bytes(_read_regular(allocation_path))
                if fresh_allocation is not None
                else None
            )
            fresh_reservation_document_sha256 = (
                sha256_bytes(_read_regular(reservation_path))
                if fresh_reservation is not None
                else None
            )
            prospective_plan_document_sha256 = (
                sha256_bytes(_read_regular(plan_path))
                if prospective_plan is not None
                else None
            )
            cancellation_result_document_sha256 = (
                cancellation_result_record[
                    "cancellation_result_document_sha256"
                ]
                if cancellation_result_record is not None
                else None
            )
            cancellation_result_sha256 = (
                cancellation_result_record["cancellation_result_sha256"]
                if cancellation_result_record is not None
                else None
            )
            cancellation_plan_document_sha256 = (
                sha256_bytes(_read_regular(cancellation_plan_path))
                if cancellation_plan is not None
                else None
            )
            cancellation_stage_evidence_document_sha256 = (
                sha256_bytes(_read_regular(cancellation_stage_evidence_path))
                if cancellation_stage_evidence is not None
                else None
            )
            cancellation_cleanup_evidence_document_sha256 = (
                sha256_bytes(_read_regular(cancellation_cleanup_evidence_path))
                if cancellation_cleanup_evidence is not None
                else None
            )
            cancellation_restore_evidence_document_sha256 = (
                sha256_bytes(_read_regular(cancellation_restore_evidence_path))
                if cancellation_restore_evidence is not None
                else None
            )
            terminal_receipt_document_sha256 = (
                sha256_bytes(_read_regular(terminal_receipt_path))
                if terminal_receipt is not None
                else None
            )
            checkpoint_by_phase = {
                str(payload.get("phase")): payload
                for payload, _digest in chain
            }
            for phase, document_sha256 in (
                (
                    "fresh_transaction_allocated",
                    fresh_allocation_document_sha256,
                ),
                (
                    "fresh_reservation_bound",
                    fresh_reservation_document_sha256,
                ),
                ("fresh_plan_sealed", prospective_plan_document_sha256),
                (
                    "cancelled_fresh_staged",
                    cancellation_stage_evidence_document_sha256,
                ),
                (
                    "cancelled_fresh_cleaned",
                    cancellation_cleanup_evidence_document_sha256,
                ),
                (
                    "unapproved_restored",
                    cancellation_restore_evidence_document_sha256,
                ),
            ):
                checkpoint = checkpoint_by_phase.get(phase)
                if checkpoint is not None and (
                    document_sha256 is None
                    or checkpoint.get("evidence_sha256") != document_sha256
                ):
                    raise _fail("project_update_legacy_recovery_state_changed")
            eligibility_checkpoint = checkpoint_by_phase.get(
                "legacy_eligibility_verified"
            )
            if fresh_allocation is not None and (
                eligibility_checkpoint is None
                or fresh_allocation.get("old_abandonment_sha256")
                != eligibility_checkpoint.get("evidence_sha256")
                or pre_ref_snapshot is None
                or fresh_allocation.get(
                    "pre_ref_snapshot_document_sha256"
                )
                != pre_ref_snapshot[
                    "pre_ref_snapshot_document_sha256"
                ]
                or fresh_allocation.get("pre_ref_snapshot_sha256")
                != pre_ref_snapshot["pre_ref_snapshot_sha256"]
                or fresh_allocation.get("project_identity_sha256")
                != intent.get("project_identity_sha256")
                or fresh_allocation.get("project_identity_sha256")
                != fresh_approval_seed.get("project_identity_sha256")
                or fresh_allocation.get("requested_target_tag")
                != fresh_approval_seed.get("requested_target_tag")
            ):
                raise _fail("project_update_legacy_recovery_state_changed")
            if pre_ref_snapshot is not None and fresh_allocation is None:
                # The pre-fetch snapshot is allowed immediately before its
                # allocation write; every later resolver state requires the
                # authenticated allocation to exist.
                if chain_state != "old_transaction_staged":
                    raise _fail(
                        "project_update_legacy_recovery_state_changed"
                    )
            if post_ref_snapshot is not None and (
                fresh_allocation is None
                or post_ref_snapshot[
                    "pre_ref_snapshot_document_sha256"
                ]
                != fresh_allocation[
                    "pre_ref_snapshot_document_sha256"
                ]
                or post_ref_snapshot["pre_ref_snapshot_sha256"]
                != fresh_allocation["pre_ref_snapshot_sha256"]
                or post_ref_snapshot["requested_target_tag"]
                != fresh_allocation["requested_target_tag"]
                or post_ref_snapshot["transport_cache_policy"]
                != fresh_allocation["transport_cache_policy"]
            ):
                raise _fail("project_update_legacy_recovery_state_changed")
            after_old_staged = {
                "old_transaction_staged",
                "fresh_transaction_allocated",
                "fresh_reservation_bound",
                "fresh_plan_sealed",
                "fresh_lock_backlinked",
                "fresh_transaction_completed",
                "cancelled_fresh_staged",
                "cancelled_fresh_cleaned",
                "unapproved_restored",
            }
            after_allocation = after_old_staged - {"old_transaction_staged"}
            after_reservation = after_allocation - {
                "fresh_transaction_allocated"
            }
            if (
                (pre_ref_snapshot is not None or fresh_allocation is not None)
                and chain_state not in after_old_staged
            ) or (
                fresh_reservation is not None
                and chain_state not in after_allocation
            ) or (
                (
                    stored_inventory is not None
                    or post_ref_snapshot is not None
                    or prospective_plan is not None
                )
                and chain_state not in after_reservation
            ):
                raise _fail("project_update_legacy_recovery_state_changed")
            allocation_ref = (
                str(fresh_allocation["fresh_transaction_ref"])
                if fresh_allocation is not None
                else None
            )
            reservation_ref = (
                str(fresh_reservation["fresh_transaction_ref"])
                if fresh_reservation is not None
                else None
            )
            plan_ref = (
                str(prospective_plan["fresh_transaction_ref"])
                if prospective_plan is not None
                else None
            )
            inventory_ref = (
                str(stored_inventory["fresh_transaction_ref"])
                if stored_inventory is not None
                else None
            )
            if fresh_reservation is not None and fresh_allocation is None:
                raise _fail("project_update_legacy_recovery_state_changed")
            if stored_inventory is not None and fresh_reservation is None:
                raise _fail("project_update_legacy_recovery_state_changed")
            if (
                allocation_ref is not None
                and reservation_ref is not None
                and allocation_ref != reservation_ref
            ):
                raise _fail("project_update_legacy_recovery_state_changed")
            if (
                reservation_ref is not None
                and plan_ref is not None
                and reservation_ref != plan_ref
            ):
                raise _fail("project_update_legacy_recovery_state_changed")
            if (
                inventory_ref is not None
                and reservation_ref is not None
                and inventory_ref != reservation_ref
            ):
                raise _fail("project_update_legacy_recovery_state_changed")
            if prospective_plan is not None and (
                fresh_allocation is None
                or prospective_plan.get(
                    "fresh_allocation_document_sha256"
                )
                != fresh_allocation_document_sha256
                or post_ref_snapshot is None
                or prospective_plan.get(
                    "post_ref_snapshot_document_sha256"
                )
                != post_ref_snapshot[
                    "post_ref_snapshot_document_sha256"
                ]
                or prospective_plan.get("post_ref_snapshot_sha256")
                != post_ref_snapshot["post_ref_snapshot_sha256"]
                or stored_inventory is None
                or prospective_plan.get(
                    "fresh_transaction_inventory_document_sha256"
                )
                != stored_inventory[
                    "fresh_transaction_inventory_document_sha256"
                ]
                or prospective_plan.get(
                    "fresh_transaction_inventory_sha256"
                )
                != stored_inventory["fresh_transaction_inventory_sha256"]
            ):
                raise _fail("project_update_legacy_recovery_state_changed")
            if (
                fresh_allocation is not None
                and fresh_reservation is not None
                and (
                    fresh_allocation.get("old_abandonment_sha256")
                    != fresh_reservation.get("old_abandonment_sha256")
                    or fresh_reservation.get(
                        "fresh_allocation_document_sha256"
                    )
                    != fresh_allocation_document_sha256
                    or fresh_reservation.get("fresh_reservation_sha256")
                    != fresh_allocation.get(
                        "prepared_reservation_document_sha256"
                    )
                )
            ):
                raise _fail("project_update_legacy_recovery_state_changed")
            if (
                fresh_reservation is not None
                and prospective_plan is not None
                and fresh_reservation.get("old_abandonment_sha256")
                != prospective_plan.get("old_abandonment_sha256")
            ):
                raise _fail("project_update_legacy_recovery_state_changed")
            cancellation_documents_present = any(
                value is not None
                for value in (
                    cancellation_result_record,
                    cancellation_plan,
                    cancellation_stage_evidence,
                    cancellation_cleanup_evidence,
                    cancellation_restore_evidence,
                )
            )
            cancellation_states = {
                "fresh_plan_sealed",
                "cancelled_fresh_staged",
                "cancelled_fresh_cleaned",
                "unapproved_restored",
            }
            if cancellation_documents_present and chain_state not in cancellation_states:
                raise _fail("project_update_legacy_recovery_state_changed")
            if cancellation_stage_evidence is not None and chain_state not in {
                "fresh_plan_sealed",
                "cancelled_fresh_staged",
                "cancelled_fresh_cleaned",
                "unapproved_restored",
            }:
                raise _fail("project_update_legacy_recovery_state_changed")
            if cancellation_cleanup_evidence is not None and chain_state not in {
                "cancelled_fresh_staged",
                "cancelled_fresh_cleaned",
                "unapproved_restored",
            }:
                raise _fail("project_update_legacy_recovery_state_changed")
            if cancellation_restore_evidence is not None and chain_state not in {
                "cancelled_fresh_cleaned",
                "unapproved_restored",
            }:
                raise _fail("project_update_legacy_recovery_state_changed")
            # One create-only result may precede its plan.  From there every
            # side-effect evidence document is a strict prefix: plan -> stage
            # -> cleanup -> restore.  No skipped or cross-branch document is
            # accepted.
            if (
                cancellation_plan is not None
                and cancellation_result_record is None
            ) or (
                cancellation_stage_evidence is not None
                and cancellation_plan is None
            ) or (
                cancellation_cleanup_evidence is not None
                and cancellation_stage_evidence is None
            ) or (
                cancellation_restore_evidence is not None
                and cancellation_cleanup_evidence is None
            ):
                raise _fail("project_update_legacy_recovery_state_changed")
            required_by_state = {
                "cancelled_fresh_staged": (
                    cancellation_result_record,
                    cancellation_plan,
                    cancellation_stage_evidence,
                ),
                "cancelled_fresh_cleaned": (
                    cancellation_result_record,
                    cancellation_plan,
                    cancellation_stage_evidence,
                    cancellation_cleanup_evidence,
                ),
                "unapproved_restored": (
                    cancellation_result_record,
                    cancellation_plan,
                    cancellation_stage_evidence,
                    cancellation_cleanup_evidence,
                    cancellation_restore_evidence,
                ),
            }
            if any(
                item is None
                for item in required_by_state.get(chain_state, ())
            ):
                raise _fail("project_update_legacy_recovery_state_changed")
            terminal_ref = (
                str(terminal_receipt["fresh_transaction_ref"])
                if terminal_receipt is not None
                else None
            )
            established_ref = (
                plan_ref or inventory_ref or reservation_ref or allocation_ref
            )
            if cancellation_plan is not None and (
                prospective_plan is None
                or stored_inventory is None
                or cancellation_result_record is None
                or cancellation_plan.get("intent_sha256") != intent_sha256
                or cancellation_plan.get("fresh_transaction_ref")
                != established_ref
                or cancellation_plan.get("prospective_plan_document_sha256")
                != prospective_plan_document_sha256
                or cancellation_plan.get("fresh_approval_plan_sha256")
                != prospective_plan.get("fresh_approval_plan_sha256")
                or cancellation_plan.get("fresh_approval_context_sha256")
                != prospective_plan.get("fresh_approval_context_sha256")
                or cancellation_plan.get("old_abandonment_sha256")
                != prospective_plan.get("old_abandonment_sha256")
                or cancellation_plan.get("old_transaction_ref")
                != intent.get("old_transaction_ref")
                or cancellation_plan.get("old_transaction_sha256")
                != intent.get("old_transaction_sha256")
                or cancellation_plan.get("old_lock_sha256")
                != intent.get("old_lock_sha256")
                or cancellation_plan.get(
                    "fresh_transaction_inventory_document_sha256"
                )
                != stored_inventory[
                    "fresh_transaction_inventory_document_sha256"
                ]
                or cancellation_plan.get(
                    "fresh_transaction_inventory_sha256"
                )
                != stored_inventory["fresh_transaction_inventory_sha256"]
                or cancellation_plan.get(
                    "cancellation_result_document_sha256"
                )
                != cancellation_result_document_sha256
                or cancellation_plan.get("cancellation_result_sha256")
                != cancellation_result_sha256
            ):
                raise _fail("project_update_legacy_recovery_state_changed")
            if cancellation_stage_evidence is not None and (
                cancellation_plan is None
                or stored_inventory is None
                or cancellation_stage_evidence.get("intent_sha256")
                != intent_sha256
                or cancellation_stage_evidence.get("fresh_transaction_ref")
                != established_ref
                or cancellation_stage_evidence.get(
                    "cancellation_plan_document_sha256"
                )
                != cancellation_plan_document_sha256
                or cancellation_stage_evidence.get(
                    "claim_absence_evidence_sha256"
                )
                != cancellation_plan.get("claim_absence_evidence_sha256")
                or cancellation_stage_evidence.get(
                    "fresh_transaction_inventory_document_sha256"
                )
                != stored_inventory[
                    "fresh_transaction_inventory_document_sha256"
                ]
                or cancellation_stage_evidence.get(
                    "fresh_transaction_inventory_sha256"
                )
                != stored_inventory["fresh_transaction_inventory_sha256"]
            ):
                raise _fail("project_update_legacy_recovery_state_changed")
            if cancellation_cleanup_evidence is not None and (
                cancellation_plan is None
                or cancellation_stage_evidence is None
                or stored_inventory is None
                or cancellation_cleanup_evidence.get("intent_sha256")
                != intent_sha256
                or cancellation_cleanup_evidence.get("fresh_transaction_ref")
                != established_ref
                or cancellation_cleanup_evidence.get(
                    "cancellation_plan_document_sha256"
                )
                != cancellation_plan_document_sha256
                or cancellation_cleanup_evidence.get(
                    "cancellation_stage_evidence_document_sha256"
                )
                != cancellation_stage_evidence_document_sha256
                or cancellation_cleanup_evidence.get(
                    "fresh_transaction_inventory_document_sha256"
                )
                != stored_inventory[
                    "fresh_transaction_inventory_document_sha256"
                ]
                or cancellation_cleanup_evidence.get(
                    "fresh_transaction_inventory_sha256"
                )
                != stored_inventory["fresh_transaction_inventory_sha256"]
            ):
                raise _fail("project_update_legacy_recovery_state_changed")
            if cancellation_restore_evidence is not None and (
                cancellation_plan is None
                or cancellation_cleanup_evidence is None
                or cancellation_restore_evidence.get("intent_sha256")
                != intent_sha256
                or cancellation_restore_evidence.get("fresh_transaction_ref")
                != established_ref
                or cancellation_restore_evidence.get(
                    "cancellation_plan_document_sha256"
                )
                != cancellation_plan_document_sha256
                or cancellation_restore_evidence.get(
                    "cancellation_cleanup_evidence_document_sha256"
                )
                != cancellation_cleanup_evidence_document_sha256
                or cancellation_restore_evidence.get("old_transaction_ref")
                != intent.get("old_transaction_ref")
                or cancellation_restore_evidence.get(
                    "old_transaction_sha256"
                )
                != intent.get("old_transaction_sha256")
                or cancellation_restore_evidence.get("old_lock_sha256")
                != intent.get("old_lock_sha256")
            ):
                raise _fail("project_update_legacy_recovery_state_changed")
            if (
                terminal_ref is not None
                and established_ref is not None
                and terminal_ref != established_ref
            ):
                raise _fail("project_update_legacy_recovery_state_changed")
            locator_terminal = locator.get("state") == "terminal_completed"
            if locator_terminal != (
                locator.get("terminal_receipt_sha256") is not None
            ):
                raise _fail("project_update_legacy_recovery_state_changed")
            if terminal_receipt is not None:
                terminal_raw = _read_regular(terminal_receipt_path)
                terminal_digest = sha256_bytes(terminal_raw)
                if (
                    terminal_receipt.get("intent_sha256") != intent_sha256
                    or terminal_receipt.get("journal_head_sha256")
                    != journal_head
                    or terminal_receipt.get(
                        "old_transaction_inventory_sha256"
                    )
                    != intent.get("old_transaction_sha256")
                    or (
                        terminal_receipt.get("outcome") == "success"
                        and chain_state != "fresh_transaction_completed"
                    )
                    or (
                        terminal_receipt.get("outcome")
                        == "unapproved_restored"
                        and chain_state != "unapproved_restored"
                    )
                    or (
                        terminal_receipt.get("outcome")
                        == "unapproved_restored"
                        and (
                            stored_inventory is None
                            or cancellation_plan is None
                            or cancellation_result_record is None
                            or cancellation_stage_evidence is None
                            or cancellation_cleanup_evidence is None
                            or cancellation_restore_evidence is None
                            or terminal_receipt.get(
                                "cancellation_plan_document_sha256"
                            )
                            != cancellation_plan_document_sha256
                            or terminal_receipt.get(
                                "cancellation_result_document_sha256"
                            )
                            != cancellation_result_document_sha256
                            or terminal_receipt.get(
                                "cancellation_result_sha256"
                            )
                            != cancellation_result_sha256
                            or terminal_receipt.get(
                                "claim_absence_evidence_sha256"
                            )
                            != cancellation_plan.get(
                                "claim_absence_evidence_sha256"
                            )
                            or terminal_receipt.get(
                                "cancelled_fresh_staging_document_sha256"
                            )
                            != cancellation_stage_evidence_document_sha256
                            or terminal_receipt.get(
                                "cancelled_fresh_staging_sha256"
                            )
                            != _transaction_semantic_sha256(
                                cancellation_stage_evidence
                            )
                            or terminal_receipt.get(
                                "cancelled_fresh_cleanup_evidence_document_sha256"
                            )
                            != cancellation_cleanup_evidence_document_sha256
                            or terminal_receipt.get(
                                "cancelled_fresh_cleanup_evidence_sha256"
                            )
                            != _transaction_semantic_sha256(
                                cancellation_cleanup_evidence
                            )
                            or terminal_receipt.get(
                                "restored_evidence_document_sha256"
                            )
                            != cancellation_restore_evidence_document_sha256
                            or terminal_receipt.get(
                                "restored_evidence_sha256"
                            )
                            != _transaction_semantic_sha256(
                                cancellation_restore_evidence
                            )
                            or terminal_receipt.get(
                                "restored_old_transaction_sha256"
                            )
                            != intent.get("old_transaction_sha256")
                            or terminal_receipt.get("preserved_old_lock_sha256")
                            != intent.get("old_lock_sha256")
                            or terminal_receipt.get(
                                "cancelled_fresh_transaction_inventory_document_sha256"
                            )
                            != stored_inventory[
                                "fresh_transaction_inventory_document_sha256"
                            ]
                            or terminal_receipt.get(
                                "cancelled_fresh_transaction_inventory_sha256"
                            )
                            != stored_inventory[
                                "fresh_transaction_inventory_sha256"
                            ]
                        )
                    )
                    or (
                        locator_terminal
                        and locator.get("terminal_receipt_sha256")
                        != terminal_digest
                    )
                ):
                    raise _fail("project_update_legacy_recovery_state_changed")
            elif locator_terminal:
                raise _fail("project_update_legacy_recovery_state_changed")
            pending_cancellation_terminal = (
                _resolve_pending_cancellation_terminal(
                    paths=store.paths,
                    key=store._key,
                    locator=locator,
                    locator_sha256=locator_sha256,
                    intent=intent,
                    intent_sha256=intent_sha256,
                    journal_head_sha256=journal_head,
                    terminal_receipt=terminal_receipt,
                    terminal_receipt_document_sha256=(
                        terminal_receipt_document_sha256
                    ),
                    cancellation_result_document_sha256=(
                        cancellation_result_document_sha256
                    ),
                    cancellation_result_sha256=cancellation_result_sha256,
                )
            )
            return ResolvedActiveRecovery(
                paths=store.paths,
                locator=dict(locator),
                intent=dict(intent),
                fresh_approval_seed=dict(fresh_approval_seed),
                checkpoints=tuple(
                    dict(payload) for payload, _digest in chain
                ),
                pre_fetch_ref_snapshot=(
                    dict(pre_ref_snapshot["pre_ref_snapshot"])
                    if pre_ref_snapshot is not None
                    else None
                ),
                fresh_allocation=(
                    dict(fresh_allocation)
                    if fresh_allocation is not None
                    else None
                ),
                fresh_reservation=(
                    dict(fresh_reservation)
                    if fresh_reservation is not None
                    else None
                ),
                fresh_transaction_inventory=(
                    dict(stored_inventory["fresh_transaction_inventory"])
                    if stored_inventory is not None
                    else None
                ),
                post_fetch_ref_snapshot=(
                    dict(post_ref_snapshot["post_ref_snapshot"])
                    if post_ref_snapshot is not None
                    else None
                ),
                prospective_plan=(
                    dict(prospective_plan)
                    if prospective_plan is not None
                    else None
                ),
                cancellation_result=(
                    dict(
                        cancellation_result_record["cancellation_result"]
                    )
                    if cancellation_result_record is not None
                    else None
                ),
                cancellation_plan=(
                    dict(cancellation_plan)
                    if cancellation_plan is not None
                    else None
                ),
                cancellation_stage_evidence=(
                    dict(cancellation_stage_evidence)
                    if cancellation_stage_evidence is not None
                    else None
                ),
                cancellation_cleanup_evidence=(
                    dict(cancellation_cleanup_evidence)
                    if cancellation_cleanup_evidence is not None
                    else None
                ),
                cancellation_restore_evidence=(
                    dict(cancellation_restore_evidence)
                    if cancellation_restore_evidence is not None
                    else None
                ),
                terminal_receipt=(
                    dict(terminal_receipt)
                    if terminal_receipt is not None
                    else None
                ),
                intent_sha256=intent_sha256,
                fresh_approval_seed_document_sha256=(
                    fresh_approval_seed_document_sha256
                ),
                journal_head_sha256=journal_head,
                locator_sha256=locator_sha256,
                locator_journal_head_sha256=locator_journal_head,
                pending_checkpoint=pending_checkpoint,
                pre_fetch_ref_snapshot_document_sha256=(
                    pre_ref_snapshot[
                        "pre_ref_snapshot_document_sha256"
                    ]
                    if pre_ref_snapshot is not None
                    else None
                ),
                pre_fetch_ref_snapshot_sha256=(
                    pre_ref_snapshot["pre_ref_snapshot_sha256"]
                    if pre_ref_snapshot is not None
                    else None
                ),
                fresh_allocation_document_sha256=(
                    fresh_allocation_document_sha256
                ),
                fresh_reservation_document_sha256=(
                    fresh_reservation_document_sha256
                ),
                fresh_transaction_inventory_document_sha256=(
                    stored_inventory[
                        "fresh_transaction_inventory_document_sha256"
                    ]
                    if stored_inventory is not None
                    else None
                ),
                fresh_transaction_inventory_sha256=(
                    stored_inventory["fresh_transaction_inventory_sha256"]
                    if stored_inventory is not None
                    else None
                ),
                post_fetch_ref_snapshot_document_sha256=(
                    post_ref_snapshot[
                        "post_ref_snapshot_document_sha256"
                    ]
                    if post_ref_snapshot is not None
                    else None
                ),
                post_fetch_ref_snapshot_sha256=(
                    post_ref_snapshot["post_ref_snapshot_sha256"]
                    if post_ref_snapshot is not None
                    else None
                ),
                prospective_plan_document_sha256=(
                    prospective_plan_document_sha256
                ),
                cancellation_result_document_sha256=(
                    cancellation_result_document_sha256
                ),
                cancellation_result_sha256=cancellation_result_sha256,
                cancellation_plan_document_sha256=(
                    cancellation_plan_document_sha256
                ),
                cancellation_stage_evidence_document_sha256=(
                    cancellation_stage_evidence_document_sha256
                ),
                cancellation_cleanup_evidence_document_sha256=(
                    cancellation_cleanup_evidence_document_sha256
                ),
                cancellation_restore_evidence_document_sha256=(
                    cancellation_restore_evidence_document_sha256
                ),
                terminal_receipt_document_sha256=(
                    terminal_receipt_document_sha256
                ),
                fresh_transaction_ref=terminal_ref or established_ref,
                pending_cancellation_terminal=(
                    pending_cancellation_terminal
                ),
            )

    try:
        return key_provider.use_key(
            archive_root,
            consume,
            create_if_missing=False,
        )
    except LegacyProjectUpdateRecoveryError:
        raise
    except BaseException:
        raise _fail(
            "project_update_legacy_recovery_authentication_invalid"
        ) from None


def resolve_terminal_recovery(
    project_root: Path | str,
    archive_root: Path | str,
    recovery_ref: str,
    key_provider: Any,
    *,
    create_if_missing: bool = False,
) -> ResolvedTerminalRecovery:
    """Reauthenticate one retired, unapproved recovery after restart.

    The caller-provided reference selects a private recovery directory but is
    not authority.  Authority comes only from the existing archive key and
    the authenticated terminal locator, complete checkpoint chain, immutable
    evidence documents, and terminal receipt below it.
    """

    if (
        type(recovery_ref) is not str
        or _RECOVERY_REF_RE.fullmatch(recovery_ref) is None
        or type(create_if_missing) is not bool
        or create_if_missing
        or not callable(getattr(key_provider, "use_key", None))
    ):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    project = Path(os.path.abspath(str(project_root)))
    RecoveryPaths.build(project, recovery_ref)

    def consume(key: memoryview) -> ResolvedTerminalRecovery:
        with LegacyRecoveryStore(project, recovery_ref, key) as store:
            terminal_path = store.paths.recovery_root / "terminal-locator.json"
            transition_path = _locator_transition_path(
                store.paths.locator_path
            )
            if os.path.lexists(store.paths.locator_path) or os.path.lexists(
                transition_path
            ):
                raise _fail(
                    "project_update_legacy_recovery_state_ambiguous"
                )
            _safe_directory(store.paths.recovery_root)
            if not os.path.lexists(terminal_path):
                raise _fail("project_update_legacy_recovery_state_changed")
            terminal_raw = _read_regular(terminal_path)
            terminal = verify_authenticated_document(
                _parse_json(terminal_raw), store._key
            )
            terminal_keys = {
                "intent_sha256",
                "journal_head_sha256",
                "previous_locator_sha256",
                "recovery_ref",
                "schema",
                "state",
                "terminal_receipt_sha256",
            }
            if (
                set(terminal) != terminal_keys
                or terminal.get("schema") != ACTIVE_LOCATOR_SCHEMA
                or terminal.get("recovery_ref") != recovery_ref
                or terminal.get("state") != "terminal_completed"
                or any(
                    type(terminal.get(name)) is not str
                    or _SHA_RE.fullmatch(str(terminal.get(name))) is None
                    for name in (
                        "intent_sha256",
                        "journal_head_sha256",
                        "previous_locator_sha256",
                        "terminal_receipt_sha256",
                    )
                )
            ):
                raise _fail(
                    "project_update_legacy_recovery_binding_invalid"
                )
            terminal_locator_sha256 = sha256_bytes(terminal_raw)
            preterminal_locator_sha256 = str(
                terminal["previous_locator_sha256"]
            )
            history_root = store.paths.recovery_root / "locator-history"
            preterminal_path = (
                history_root
                / (
                    preterminal_locator_sha256.removeprefix("sha256:")
                    + ".json"
                )
            )
            with _retained_parent_chains(
                store.paths.project_root,
                store.paths.recovery_root,
                history_root,
            ):
                if not os.path.lexists(preterminal_path):
                    raise _fail(
                        "project_update_legacy_recovery_state_changed"
                    )
                preterminal_raw = _read_regular(preterminal_path)
            preterminal = verify_authenticated_document(
                _parse_json(preterminal_raw), store._key
            )
            ordinary_locator_keys = {
                "intent_sha256",
                "journal_head_sha256",
                "previous_locator_sha256",
                "recovery_ref",
                "schema",
                "state",
            }
            if (
                sha256_bytes(preterminal_raw)
                != preterminal_locator_sha256
                or set(preterminal) != ordinary_locator_keys
                or preterminal.get("schema") != ACTIVE_LOCATOR_SCHEMA
                or preterminal.get("recovery_ref") != recovery_ref
                or preterminal.get("state") != "unapproved_restored"
                or preterminal.get("intent_sha256")
                != terminal["intent_sha256"]
                or preterminal.get("journal_head_sha256")
                != terminal["journal_head_sha256"]
                or _SHA_RE.fullmatch(
                    str(preterminal.get("previous_locator_sha256"))
                )
                is None
            ):
                raise _fail("project_update_legacy_recovery_state_changed")

            intent, intent_sha256 = store.read_intent()
            if terminal["intent_sha256"] != intent_sha256:
                raise _fail("project_update_legacy_recovery_state_changed")
            try:
                exact_intent = recovery_intent_document(
                    recovery_ref=str(intent["recovery_ref"]),
                    old_transaction_ref=str(intent["old_transaction_ref"]),
                    old_transaction_sha256=str(
                        intent["old_transaction_sha256"]
                    ),
                    old_claim_sha256=str(intent["old_claim_sha256"]),
                    old_lock_sha256=str(intent["old_lock_sha256"]),
                    old_live_components_sha256=str(
                        intent["old_live_components_sha256"]
                    ),
                    archive_identity_sha256=str(
                        intent["archive_identity_sha256"]
                    ),
                    project_identity_sha256=str(
                        intent["project_identity_sha256"]
                    ),
                    fresh_approval_seed_document_sha256=str(
                        intent["fresh_approval_seed_document_sha256"]
                    ),
                )
            except (KeyError, TypeError):
                raise _fail(
                    "project_update_legacy_recovery_binding_invalid"
                ) from None
            if exact_intent != intent:
                raise _fail(
                    "project_update_legacy_recovery_binding_invalid"
                )

            # The seed is authenticated and cross-bound but never returned;
            # its raw reviewer remains confined to this private stack frame.
            seed_path = (
                store.paths.recovery_root / "fresh-approval-seed.json"
            )
            seed = store.read_fresh_approval_seed()
            seed_document_sha256 = sha256_bytes(_read_regular(seed_path))
            if (
                intent["fresh_approval_seed_document_sha256"]
                != seed_document_sha256
                or seed["old_transaction_ref"]
                != intent["old_transaction_ref"]
                or seed["old_transaction_sha256"]
                != intent["old_transaction_sha256"]
                or seed["archive_identity_sha256"]
                != intent["archive_identity_sha256"]
                or seed["project_identity_sha256"]
                != intent["project_identity_sha256"]
            ):
                raise _fail("project_update_legacy_recovery_state_changed")

            chain = store._read_checkpoint_chain(
                intent_sha256=intent_sha256
            )
            expected_phases = (
                "legacy_eligibility_verified",
                "old_transaction_staged",
                "fresh_transaction_allocated",
                "fresh_reservation_bound",
                "fresh_plan_sealed",
                "cancelled_fresh_staged",
                "cancelled_fresh_cleaned",
                "unapproved_restored",
            )
            if (
                tuple(
                    str(checkpoint.get("phase"))
                    for checkpoint, _digest in chain
                )
                != expected_phases
                or _checkpoint_chain_state(
                    tuple(checkpoint for checkpoint, _digest in chain)
                )
                != "unapproved_restored"
                or not chain
                or terminal["journal_head_sha256"] != chain[-1][1]
            ):
                raise _fail("project_update_legacy_recovery_state_changed")
            checkpoint_by_phase = {
                str(checkpoint["phase"]): checkpoint
                for checkpoint, _digest in chain
            }
            journal_head_sha256 = chain[-1][1]

            control_paths = {
                "pre": store.paths.recovery_root
                / "pre-fetch-ref-snapshot.json",
                "allocation": store.paths.recovery_root
                / "fresh-allocation.json",
                "reservation": store.paths.recovery_root
                / "fresh-reservation.json",
                "inventory": store.paths.recovery_root
                / "fresh-transaction-inventory",
                "post": store.paths.recovery_root
                / "post-fetch-ref-snapshot.json",
                "prospective": store.paths.recovery_root
                / "prospective-plan.json",
                "result": store.paths.recovery_root
                / "cancellation-result.json",
                "plan": store.paths.recovery_root / "cancellation-plan.json",
                "stage": store.paths.recovery_root
                / "cancellation-stage-evidence.json",
                "cleanup": store.paths.recovery_root
                / "cancellation-cleanup-evidence.json",
                "restore": store.paths.recovery_root
                / "cancellation-restore-evidence.json",
                "receipt": store.paths.recovery_root
                / "terminal-receipt.json",
            }
            if any(
                not os.path.lexists(path) for path in control_paths.values()
            ) or os.path.lexists(
                store.paths.recovery_root
                / "fresh-transaction-inventory.prepared"
            ):
                raise _fail("project_update_legacy_recovery_state_changed")

            pre_snapshot = store.read_pre_fetch_ref_snapshot()
            allocation = store.read_fresh_allocation()
            reservation = store.read_fresh_reservation()
            inventory = store.read_fresh_transaction_inventory()
            post_snapshot = store.read_post_fetch_ref_snapshot()
            prospective = store.read_prospective_plan()
            cancellation_result = store.read_cancellation_result()
            cancellation_plan = store.read_cancellation_plan()
            stage_evidence = store.read_cancellation_stage_evidence()
            cleanup_evidence = store.read_cancellation_cleanup_evidence()
            restore_evidence = store.read_cancellation_restore_evidence()
            receipt = store.read_terminal_receipt()

            document_digests = {
                name: sha256_bytes(_read_regular(path))
                for name, path in control_paths.items()
                if name != "inventory"
            }
            document_digests["inventory"] = inventory[
                "fresh_transaction_inventory_document_sha256"
            ]

            try:
                prepared = _prepared_reservation_from_allocation(allocation)
                exact_allocation = fresh_allocation_document(
                    recovery_ref=recovery_ref,
                    prepared_reservation_document=prepared.document(),
                    old_abandonment_sha256=str(
                        allocation["old_abandonment_sha256"]
                    ),
                    pre_ref_snapshot_document_sha256=str(
                        allocation[
                            "pre_ref_snapshot_document_sha256"
                        ]
                    ),
                    pre_ref_snapshot_sha256=str(
                        allocation["pre_ref_snapshot_sha256"]
                    ),
                    transport_cache_policy=str(
                        allocation["transport_cache_policy"]
                    ),
                )
                exact_reservation = fresh_reservation_document(
                    recovery_ref=recovery_ref,
                    fresh_transaction_ref=str(
                        reservation["fresh_transaction_ref"]
                    ),
                    fresh_reservation_sha256=str(
                        reservation["fresh_reservation_sha256"]
                    ),
                    fresh_allocation_document_sha256=str(
                        reservation[
                            "fresh_allocation_document_sha256"
                        ]
                    ),
                    old_abandonment_sha256=str(
                        reservation["old_abandonment_sha256"]
                    ),
                )
                exact_prospective = prospective_plan_document(
                    recovery_ref=recovery_ref,
                    fresh_allocation_document_sha256=str(
                        prospective[
                            "fresh_allocation_document_sha256"
                        ]
                    ),
                    fresh_transaction_ref=str(
                        prospective["fresh_transaction_ref"]
                    ),
                    fresh_intent_sha256=str(
                        prospective["fresh_intent_sha256"]
                    ),
                    fresh_transaction_inventory_sha256=str(
                        prospective[
                            "fresh_transaction_inventory_sha256"
                        ]
                    ),
                    fresh_transaction_inventory_document_sha256=str(
                        prospective[
                            "fresh_transaction_inventory_document_sha256"
                        ]
                    ),
                    fresh_approval_plan_sha256=str(
                        prospective["fresh_approval_plan_sha256"]
                    ),
                    fresh_approval_target_binding_sha256=str(
                        prospective[
                            "fresh_approval_target_binding_sha256"
                        ]
                    ),
                    fresh_approval_context_sha256=str(
                        prospective["fresh_approval_context_sha256"]
                    ),
                    fresh_recovery_binding_sha256=str(
                        prospective["fresh_recovery_binding_sha256"]
                    ),
                    post_ref_snapshot_document_sha256=str(
                        prospective[
                            "post_ref_snapshot_document_sha256"
                        ]
                    ),
                    post_ref_snapshot_sha256=str(
                        prospective["post_ref_snapshot_sha256"]
                    ),
                    old_abandonment_sha256=str(
                        prospective["old_abandonment_sha256"]
                    ),
                )
                exact_plan = cancellation_plan_document(
                    recovery_ref=recovery_ref,
                    intent_sha256=str(cancellation_plan["intent_sha256"]),
                    fresh_transaction_ref=str(
                        cancellation_plan["fresh_transaction_ref"]
                    ),
                    prospective_plan_document_sha256=str(
                        cancellation_plan[
                            "prospective_plan_document_sha256"
                        ]
                    ),
                    fresh_approval_plan_sha256=str(
                        cancellation_plan["fresh_approval_plan_sha256"]
                    ),
                    fresh_approval_context_sha256=str(
                        cancellation_plan[
                            "fresh_approval_context_sha256"
                        ]
                    ),
                    claim_absence_evidence_sha256=str(
                        cancellation_plan[
                            "claim_absence_evidence_sha256"
                        ]
                    ),
                    old_transaction_ref=str(
                        cancellation_plan["old_transaction_ref"]
                    ),
                    old_transaction_sha256=str(
                        cancellation_plan["old_transaction_sha256"]
                    ),
                    old_lock_sha256=str(
                        cancellation_plan["old_lock_sha256"]
                    ),
                    old_abandonment_sha256=str(
                        cancellation_plan["old_abandonment_sha256"]
                    ),
                    fresh_transaction_inventory_sha256=str(
                        cancellation_plan[
                            "fresh_transaction_inventory_sha256"
                        ]
                    ),
                    fresh_transaction_inventory_document_sha256=str(
                        cancellation_plan[
                            "fresh_transaction_inventory_document_sha256"
                        ]
                    ),
                    cancellation_result_sha256=str(
                        cancellation_plan["cancellation_result_sha256"]
                    ),
                    cancellation_result_document_sha256=str(
                        cancellation_plan[
                            "cancellation_result_document_sha256"
                        ]
                    ),
                )
                exact_stage = cancellation_stage_evidence_document(
                    recovery_ref=recovery_ref,
                    intent_sha256=str(stage_evidence["intent_sha256"]),
                    fresh_transaction_ref=str(
                        stage_evidence["fresh_transaction_ref"]
                    ),
                    cancellation_plan_document_sha256=str(
                        stage_evidence[
                            "cancellation_plan_document_sha256"
                        ]
                    ),
                    claim_absence_evidence_sha256=str(
                        stage_evidence[
                            "claim_absence_evidence_sha256"
                        ]
                    ),
                    fresh_transaction_inventory_sha256=str(
                        stage_evidence[
                            "fresh_transaction_inventory_sha256"
                        ]
                    ),
                    fresh_transaction_inventory_document_sha256=str(
                        stage_evidence[
                            "fresh_transaction_inventory_document_sha256"
                        ]
                    ),
                    stage_state=str(stage_evidence["stage_state"]),
                )
                exact_cleanup = cancellation_cleanup_evidence_document(
                    recovery_ref=recovery_ref,
                    intent_sha256=str(cleanup_evidence["intent_sha256"]),
                    fresh_transaction_ref=str(
                        cleanup_evidence["fresh_transaction_ref"]
                    ),
                    cancellation_plan_document_sha256=str(
                        cleanup_evidence[
                            "cancellation_plan_document_sha256"
                        ]
                    ),
                    cancellation_stage_evidence_document_sha256=str(
                        cleanup_evidence[
                            "cancellation_stage_evidence_document_sha256"
                        ]
                    ),
                    fresh_transaction_inventory_sha256=str(
                        cleanup_evidence[
                            "fresh_transaction_inventory_sha256"
                        ]
                    ),
                    fresh_transaction_inventory_document_sha256=str(
                        cleanup_evidence[
                            "fresh_transaction_inventory_document_sha256"
                        ]
                    ),
                    cleanup_state=str(cleanup_evidence["cleanup_state"]),
                )
                exact_restore = cancellation_restore_evidence_document(
                    recovery_ref=recovery_ref,
                    intent_sha256=str(restore_evidence["intent_sha256"]),
                    fresh_transaction_ref=str(
                        restore_evidence["fresh_transaction_ref"]
                    ),
                    cancellation_plan_document_sha256=str(
                        restore_evidence[
                            "cancellation_plan_document_sha256"
                        ]
                    ),
                    cancellation_cleanup_evidence_document_sha256=str(
                        restore_evidence[
                            "cancellation_cleanup_evidence_document_sha256"
                        ]
                    ),
                    old_transaction_ref=str(
                        restore_evidence["old_transaction_ref"]
                    ),
                    old_transaction_sha256=str(
                        restore_evidence["old_transaction_sha256"]
                    ),
                    old_lock_sha256=str(
                        restore_evidence["old_lock_sha256"]
                    ),
                    restore_state=str(restore_evidence["restore_state"]),
                )
                exact_receipt = terminal_receipt_document(
                    recovery_ref=recovery_ref,
                    outcome="unapproved_restored",
                    intent_sha256=str(receipt["intent_sha256"]),
                    journal_head_sha256=str(receipt["journal_head_sha256"]),
                    fresh_transaction_ref=str(
                        receipt["fresh_transaction_ref"]
                    ),
                    old_transaction_inventory_sha256=str(
                        receipt["old_transaction_inventory_sha256"]
                    ),
                    claim_absence_evidence_sha256=str(
                        receipt["claim_absence_evidence_sha256"]
                    ),
                    cancelled_fresh_staging_sha256=str(
                        receipt["cancelled_fresh_staging_sha256"]
                    ),
                    cancelled_fresh_transaction_inventory_sha256=str(
                        receipt[
                            "cancelled_fresh_transaction_inventory_sha256"
                        ]
                    ),
                    cancelled_fresh_transaction_inventory_document_sha256=str(
                        receipt[
                            "cancelled_fresh_transaction_inventory_document_sha256"
                        ]
                    ),
                    cancelled_fresh_cleanup_evidence_sha256=str(
                        receipt[
                            "cancelled_fresh_cleanup_evidence_sha256"
                        ]
                    ),
                    restored_old_transaction_sha256=str(
                        receipt["restored_old_transaction_sha256"]
                    ),
                    preserved_old_lock_sha256=str(
                        receipt["preserved_old_lock_sha256"]
                    ),
                    cancellation_plan_document_sha256=str(
                        receipt["cancellation_plan_document_sha256"]
                    ),
                    cancellation_result_document_sha256=str(
                        receipt["cancellation_result_document_sha256"]
                    ),
                    cancellation_result_sha256=str(
                        receipt["cancellation_result_sha256"]
                    ),
                    cancelled_fresh_staging_document_sha256=str(
                        receipt[
                            "cancelled_fresh_staging_document_sha256"
                        ]
                    ),
                    cancelled_fresh_cleanup_evidence_document_sha256=str(
                        receipt[
                            "cancelled_fresh_cleanup_evidence_document_sha256"
                        ]
                    ),
                    restored_evidence_sha256=str(
                        receipt["restored_evidence_sha256"]
                    ),
                    restored_evidence_document_sha256=str(
                        receipt["restored_evidence_document_sha256"]
                    ),
                )
            except (KeyError, TypeError):
                raise _fail(
                    "project_update_legacy_recovery_binding_invalid"
                ) from None

            if (
                allocation != exact_allocation
                or reservation != exact_reservation
                or prospective != exact_prospective
                or cancellation_plan != exact_plan
                or stage_evidence != exact_stage
                or cleanup_evidence != exact_cleanup
                or restore_evidence != exact_restore
                or receipt != exact_receipt
                or cancellation_result["cancellation_result"]
                != cancellation_result_document()
                or receipt["outcome"] != "unapproved_restored"
            ):
                raise _fail(
                    "project_update_legacy_recovery_binding_invalid"
                )

            fresh_transaction_ref = str(
                allocation["fresh_transaction_ref"]
            )
            phase_evidence = {
                "fresh_transaction_allocated": document_digests[
                    "allocation"
                ],
                "fresh_reservation_bound": document_digests[
                    "reservation"
                ],
                "fresh_plan_sealed": document_digests["prospective"],
                "cancelled_fresh_staged": document_digests["stage"],
                "cancelled_fresh_cleaned": document_digests["cleanup"],
                "unapproved_restored": document_digests["restore"],
            }
            if any(
                checkpoint_by_phase[phase]["evidence_sha256"] != digest
                for phase, digest in phase_evidence.items()
            ):
                raise _fail("project_update_legacy_recovery_state_changed")

            old_abandonment_sha256 = checkpoint_by_phase[
                "legacy_eligibility_verified"
            ]["evidence_sha256"]
            allowed_old_stage_evidence = {
                sha256_document(
                    {
                        "old_transaction_sha256": intent[
                            "old_transaction_sha256"
                        ],
                        "schema": (
                            "wom-kit/project-update-legacy-stage-evidence/"
                            "v0.4.19"
                        ),
                        "state": state,
                    }
                )
                for state in ("staged", "already_staged")
            }
            stage_semantic_sha256 = _transaction_semantic_sha256(
                stage_evidence
            )
            cleanup_semantic_sha256 = _transaction_semantic_sha256(
                cleanup_evidence
            )
            restore_semantic_sha256 = _transaction_semantic_sha256(
                restore_evidence
            )
            if (
                checkpoint_by_phase["old_transaction_staged"][
                    "evidence_sha256"
                ]
                not in allowed_old_stage_evidence
                or allocation["old_abandonment_sha256"]
                != old_abandonment_sha256
                or allocation["project_identity_sha256"]
                != intent["project_identity_sha256"]
                or allocation["project_identity_sha256"]
                != seed["project_identity_sha256"]
                or allocation["requested_target_tag"]
                != seed["requested_target_tag"]
                or allocation["pre_ref_snapshot_document_sha256"]
                != pre_snapshot["pre_ref_snapshot_document_sha256"]
                or allocation["pre_ref_snapshot_sha256"]
                != pre_snapshot["pre_ref_snapshot_sha256"]
                or reservation["fresh_transaction_ref"]
                != fresh_transaction_ref
                or reservation["fresh_allocation_document_sha256"]
                != document_digests["allocation"]
                or reservation["fresh_reservation_sha256"]
                != allocation["prepared_reservation_document_sha256"]
                or reservation["old_abandonment_sha256"]
                != old_abandonment_sha256
                or inventory["fresh_transaction_ref"]
                != fresh_transaction_ref
                or post_snapshot["pre_ref_snapshot_document_sha256"]
                != pre_snapshot["pre_ref_snapshot_document_sha256"]
                or post_snapshot["pre_ref_snapshot_sha256"]
                != pre_snapshot["pre_ref_snapshot_sha256"]
                or post_snapshot["requested_target_tag"]
                != allocation["requested_target_tag"]
                or post_snapshot["transport_cache_policy"]
                != allocation["transport_cache_policy"]
                or prospective["fresh_transaction_ref"]
                != fresh_transaction_ref
                or prospective["fresh_allocation_document_sha256"]
                != document_digests["allocation"]
                or prospective[
                    "fresh_transaction_inventory_document_sha256"
                ]
                != document_digests["inventory"]
                or prospective["fresh_transaction_inventory_sha256"]
                != inventory["fresh_transaction_inventory_sha256"]
                or prospective["post_ref_snapshot_document_sha256"]
                != post_snapshot["post_ref_snapshot_document_sha256"]
                or prospective["post_ref_snapshot_sha256"]
                != post_snapshot["post_ref_snapshot_sha256"]
                or prospective["old_abandonment_sha256"]
                != old_abandonment_sha256
                or cancellation_plan["intent_sha256"] != intent_sha256
                or cancellation_plan["fresh_transaction_ref"]
                != fresh_transaction_ref
                or cancellation_plan["prospective_plan_document_sha256"]
                != document_digests["prospective"]
                or cancellation_plan["fresh_approval_plan_sha256"]
                != prospective["fresh_approval_plan_sha256"]
                or cancellation_plan["fresh_approval_context_sha256"]
                != prospective["fresh_approval_context_sha256"]
                or cancellation_plan["old_abandonment_sha256"]
                != old_abandonment_sha256
                or cancellation_plan["old_transaction_ref"]
                != intent["old_transaction_ref"]
                or cancellation_plan["old_transaction_sha256"]
                != intent["old_transaction_sha256"]
                or cancellation_plan["old_lock_sha256"]
                != intent["old_lock_sha256"]
                or cancellation_plan[
                    "fresh_transaction_inventory_document_sha256"
                ]
                != document_digests["inventory"]
                or cancellation_plan[
                    "fresh_transaction_inventory_sha256"
                ]
                != inventory["fresh_transaction_inventory_sha256"]
                or cancellation_plan[
                    "cancellation_result_document_sha256"
                ]
                != cancellation_result[
                    "cancellation_result_document_sha256"
                ]
                or document_digests["result"]
                != cancellation_result[
                    "cancellation_result_document_sha256"
                ]
                or cancellation_plan["cancellation_result_sha256"]
                != cancellation_result["cancellation_result_sha256"]
                or stage_evidence["intent_sha256"] != intent_sha256
                or stage_evidence["fresh_transaction_ref"]
                != fresh_transaction_ref
                or stage_evidence["cancellation_plan_document_sha256"]
                != document_digests["plan"]
                or stage_evidence["claim_absence_evidence_sha256"]
                != cancellation_plan["claim_absence_evidence_sha256"]
                or stage_evidence[
                    "fresh_transaction_inventory_document_sha256"
                ]
                != document_digests["inventory"]
                or stage_evidence["fresh_transaction_inventory_sha256"]
                != inventory["fresh_transaction_inventory_sha256"]
                or cleanup_evidence["intent_sha256"] != intent_sha256
                or cleanup_evidence["fresh_transaction_ref"]
                != fresh_transaction_ref
                or cleanup_evidence["cancellation_plan_document_sha256"]
                != document_digests["plan"]
                or cleanup_evidence[
                    "cancellation_stage_evidence_document_sha256"
                ]
                != document_digests["stage"]
                or cleanup_evidence[
                    "fresh_transaction_inventory_document_sha256"
                ]
                != document_digests["inventory"]
                or cleanup_evidence[
                    "fresh_transaction_inventory_sha256"
                ]
                != inventory["fresh_transaction_inventory_sha256"]
                or restore_evidence["intent_sha256"] != intent_sha256
                or restore_evidence["fresh_transaction_ref"]
                != fresh_transaction_ref
                or restore_evidence["cancellation_plan_document_sha256"]
                != document_digests["plan"]
                or restore_evidence[
                    "cancellation_cleanup_evidence_document_sha256"
                ]
                != document_digests["cleanup"]
                or restore_evidence["old_transaction_ref"]
                != intent["old_transaction_ref"]
                or restore_evidence["old_transaction_sha256"]
                != intent["old_transaction_sha256"]
                or restore_evidence["old_lock_sha256"]
                != intent["old_lock_sha256"]
                or receipt["intent_sha256"] != intent_sha256
                or receipt["journal_head_sha256"]
                != journal_head_sha256
                or receipt["fresh_transaction_ref"]
                != fresh_transaction_ref
                or receipt["old_transaction_inventory_sha256"]
                != intent["old_transaction_sha256"]
                or receipt["claim_absence_evidence_sha256"]
                != cancellation_plan["claim_absence_evidence_sha256"]
                or receipt[
                    "cancelled_fresh_transaction_inventory_document_sha256"
                ]
                != document_digests["inventory"]
                or receipt[
                    "cancelled_fresh_transaction_inventory_sha256"
                ]
                != inventory["fresh_transaction_inventory_sha256"]
                or receipt["cancellation_plan_document_sha256"]
                != document_digests["plan"]
                or receipt["cancellation_result_document_sha256"]
                != cancellation_result[
                    "cancellation_result_document_sha256"
                ]
                or receipt["cancellation_result_sha256"]
                != cancellation_result["cancellation_result_sha256"]
                or receipt["cancelled_fresh_staging_document_sha256"]
                != document_digests["stage"]
                or receipt["cancelled_fresh_staging_sha256"]
                != stage_semantic_sha256
                or receipt[
                    "cancelled_fresh_cleanup_evidence_document_sha256"
                ]
                != document_digests["cleanup"]
                or receipt["cancelled_fresh_cleanup_evidence_sha256"]
                != cleanup_semantic_sha256
                or receipt["restored_evidence_document_sha256"]
                != document_digests["restore"]
                or receipt["restored_evidence_sha256"]
                != restore_semantic_sha256
                or receipt["restored_old_transaction_sha256"]
                != intent["old_transaction_sha256"]
                or receipt["preserved_old_lock_sha256"]
                != intent["old_lock_sha256"]
                or terminal["terminal_receipt_sha256"]
                != document_digests["receipt"]
            ):
                raise _fail("project_update_legacy_recovery_state_changed")

            # Detect a competing active recovery or replacement of any bound
            # terminal control document before returning the snapshot.
            if (
                os.path.lexists(store.paths.locator_path)
                or os.path.lexists(transition_path)
                or not hmac.compare_digest(
                    _read_regular(terminal_path), terminal_raw
                )
                or any(
                    sha256_bytes(_read_regular(path))
                    != document_digests[name]
                    for name, path in control_paths.items()
                    if name != "inventory"
                )
            ):
                raise _fail(
                    "project_update_legacy_recovery_state_ambiguous"
                )
            with _retained_parent_chains(
                store.paths.project_root,
                store.paths.recovery_root,
                history_root,
            ):
                if not hmac.compare_digest(
                    _read_regular(preterminal_path), preterminal_raw
                ):
                    raise _fail(
                        "project_update_legacy_recovery_state_ambiguous"
                    )

            return ResolvedTerminalRecovery(
                recovery_ref=recovery_ref,
                outcome="unapproved_restored",
                archive_identity_sha256=str(
                    intent["archive_identity_sha256"]
                ),
                project_identity_sha256=str(
                    intent["project_identity_sha256"]
                ),
                intent_sha256=intent_sha256,
                journal_head_sha256=journal_head_sha256,
                fresh_transaction_ref=fresh_transaction_ref,
                terminal_locator_sha256=terminal_locator_sha256,
                terminal_receipt_document_sha256=document_digests[
                    "receipt"
                ],
                cancellation_result_document_sha256=str(
                    cancellation_result[
                        "cancellation_result_document_sha256"
                    ]
                ),
                cancellation_result_sha256=str(
                    cancellation_result["cancellation_result_sha256"]
                ),
                cancellation_plan_document_sha256=document_digests["plan"],
                cancellation_stage_evidence_document_sha256=(
                    document_digests["stage"]
                ),
                cancellation_stage_evidence_sha256=stage_semantic_sha256,
                cancellation_cleanup_evidence_document_sha256=(
                    document_digests["cleanup"]
                ),
                cancellation_cleanup_evidence_sha256=(
                    cleanup_semantic_sha256
                ),
                cancellation_restore_evidence_document_sha256=(
                    document_digests["restore"]
                ),
                cancellation_restore_evidence_sha256=(
                    restore_semantic_sha256
                ),
            )

    try:
        return key_provider.use_key(
            archive_root,
            consume,
            create_if_missing=False,
        )
    except LegacyProjectUpdateRecoveryError:
        raise
    except BaseException:
        raise _fail(
            "project_update_legacy_recovery_authentication_invalid"
        ) from None


def move_directory_no_replace(source: Path, destination: Path) -> None:
    """Move one retained real directory without replacing another name."""

    source = Path(os.path.abspath(str(source)))
    destination = Path(os.path.abspath(str(destination)))
    source_info = _safe_directory(source)
    if os.path.lexists(destination):
        raise _fail("project_update_legacy_recovery_state_changed")
    _safe_directory(destination.parent)
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        from . import legacy_cleanup_bound_delete, private_metadata_win32

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_file = kernel32.CreateFileW
        create_file.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        create_file.restype = wintypes.HANDLE
        set_information = kernel32.SetFileInformationByHandle
        set_information.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        set_information.restype = wintypes.BOOL
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL
        invalid_handle = wintypes.HANDLE(-1).value
        project_root = _control_project_root(source)
        raw_handle: int | None = None
        try:
            with _retained_parent_chains(
                project_root,
                source.parent,
                destination.parent,
            ):
                handle = create_file(
                    str(source),
                    0x00010000 | 0x00000001 | 0x00000080,
                    0x00000001 | 0x00000002,
                    None,
                    3,
                    0x02000000 | 0x00200000,
                    None,
                )
                value = (
                    handle
                    if isinstance(handle, int)
                    else getattr(handle, "value", None)
                )
                if value in {None, invalid_handle}:
                    raise OSError("directory_open_failed")
                raw_handle = int(value)
                held = _safe_directory(source)
                if (int(held.st_dev), int(held.st_ino)) != (
                    int(source_info.st_dev),
                    int(source_info.st_ino),
                ):
                    raise OSError("directory_identity_changed")
                legacy_cleanup_bound_delete._reject_windows_alternate_streams(
                    raw_handle,
                    directory=True,
                )
                rename = private_metadata_win32.file_rename_info_buffer(
                    destination,
                    replace_if_exists=False,
                )
                if not set_information(
                    raw_handle, 3, rename.backing, rename.api_buffer_size
                ):
                    raise OSError("directory_rename_failed")
                moved = _safe_directory(destination)
                if (
                    os.path.lexists(source)
                    or (int(moved.st_dev), int(moved.st_ino))
                    != (int(source_info.st_dev), int(source_info.st_ino))
                ):
                    raise OSError("directory_move_unproved")
                _fsync_directory(source.parent)
                if destination.parent != source.parent:
                    _fsync_directory(destination.parent)
            return
        except LegacyProjectUpdateRecoveryError:
            raise
        except BaseException:
            raise _fail("project_update_legacy_recovery_state_changed") from None
        finally:
            if raw_handle is not None and not close_handle(raw_handle):
                raise _fail(
                    "project_update_legacy_recovery_state_ambiguous"
                ) from None
    try:
        os.rename(source, destination)
    except OSError:
        raise _fail("project_update_legacy_recovery_commit_failed") from None
    moved = _safe_directory(destination)
    if (source_info.st_dev, source_info.st_ino) != (moved.st_dev, moved.st_ino):
        raise _fail("project_update_legacy_recovery_state_changed")
    if os.path.lexists(source):
        raise _fail("project_update_legacy_recovery_state_ambiguous")
    _fsync_directory(source.parent)
    if destination.parent != source.parent:
        _fsync_directory(destination.parent)


def _locator_transition_path(locator_path: Path) -> Path:
    return locator_path.with_name(locator_path.name + ".transition")


def _delete_exact_regular_bytes(
    project_root: Path,
    path: Path,
    expected_raw: bytes,
) -> None:
    """Delete only the retained single-link file whose full bytes were bound."""

    if type(expected_raw) is not bytes:
        raise _fail("project_update_legacy_recovery_binding_invalid")
    if not os.path.lexists(path):
        return
    info = _safe_regular(path, maximum=max(len(expected_raw), 1))
    observed = _read_regular(path, maximum=max(len(expected_raw), 1))
    if not hmac.compare_digest(observed, expected_raw):
        raise _fail("project_update_legacy_recovery_state_changed")
    try:
        from . import legacy_cleanup_bound_delete

        legacy_cleanup_bound_delete._delete_exact_approved_file(
            project_root,
            path,
            {
                "identity": {
                    "device": int(info.st_dev),
                    "inode": int(info.st_ino),
                },
                "mtime_ns": int(info.st_mtime_ns),
                "sha256": hashlib.sha256(expected_raw).hexdigest(),
                "size": len(expected_raw),
                "type": "file",
            },
        )
        _fsync_directory(path.parent)
    except BaseException:
        if not os.path.lexists(path):
            return
        raise _fail("project_update_legacy_recovery_state_changed") from None


def _move_exact_regular_no_replace(
    project_root: Path,
    source: Path,
    destination: Path,
    expected_raw: bytes,
) -> None:
    """Rename one exact retained Windows file without replacing any name."""

    if type(expected_raw) is not bytes:
        raise _fail("project_update_legacy_recovery_path_unsafe")
    if os.name != "nt":
        raise _fail("project_update_legacy_recovery_platform_unsupported")
    source = Path(os.path.abspath(str(source)))
    destination = Path(os.path.abspath(str(destination)))
    if source == destination or os.path.lexists(destination):
        raise _fail("project_update_legacy_recovery_state_changed")
    before = _safe_regular(source, maximum=max(len(expected_raw), 1))
    if int(before.st_size) != len(expected_raw):
        raise _fail("project_update_legacy_recovery_state_changed")
    import ctypes
    import msvcrt
    from ctypes import wintypes
    from . import private_metadata_win32

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    set_information = kernel32.SetFileInformationByHandle
    set_information.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    set_information.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    invalid_handle = wintypes.HANDLE(-1).value
    descriptor: int | None = None
    raw_handle: int | None = None
    try:
        with _retained_parent_chains(
            project_root,
            source.parent,
            destination.parent,
        ):
            handle = create_file(
                str(source),
                0x80000000 | 0x00010000 | 0x00000080,
                0x00000001,
                None,
                3,
                0x00200000,
                None,
            )
            value = (
                handle
                if isinstance(handle, int)
                else getattr(handle, "value", None)
            )
            if value in {None, invalid_handle}:
                raise OSError("bound_open_failed")
            raw_handle = int(value)
            descriptor = msvcrt.open_osfhandle(
                raw_handle,
                os.O_RDONLY | getattr(os, "O_BINARY", 0),
            )
            raw_handle = msvcrt.get_osfhandle(descriptor)
            opened = os.fstat(descriptor)
            if (
                not stat.S_ISREG(opened.st_mode)
                or stat.S_ISLNK(opened.st_mode)
                or int(opened.st_nlink) != 1
                or (int(opened.st_dev), int(opened.st_ino))
                != (int(before.st_dev), int(before.st_ino))
                or int(opened.st_size) != len(expected_raw)
            ):
                raise OSError("bound_identity_changed")
            os.lseek(descriptor, 0, os.SEEK_SET)
            observed = bytearray()
            while len(observed) < len(expected_raw):
                chunk = os.read(
                    descriptor,
                    min(1024 * 1024, len(expected_raw) - len(observed)),
                )
                if not chunk:
                    raise OSError("bound_read_incomplete")
                observed.extend(chunk)
            if os.read(descriptor, 1) or not hmac.compare_digest(
                bytes(observed), expected_raw
            ):
                raise OSError("bound_bytes_changed")
            from . import legacy_cleanup_bound_delete

            legacy_cleanup_bound_delete._reject_windows_alternate_streams(
                raw_handle,
                directory=False,
            )
            named = _safe_regular(source, maximum=max(len(expected_raw), 1))
            if (int(named.st_dev), int(named.st_ino)) != (
                int(opened.st_dev),
                int(opened.st_ino),
            ):
                raise OSError("bound_name_changed")
            rename = private_metadata_win32.file_rename_info_buffer(
                destination,
                replace_if_exists=False,
            )
            if not set_information(
                raw_handle,
                3,
                rename.backing,
                rename.api_buffer_size,
            ):
                raise OSError("bound_rename_failed")
            moved = _safe_regular(
                destination,
                maximum=max(len(expected_raw), 1),
            )
            if (
                os.path.lexists(source)
                or (int(moved.st_dev), int(moved.st_ino))
                != (int(opened.st_dev), int(opened.st_ino))
            ):
                raise OSError("bound_move_unproved")
            _fsync_directory(source.parent)
            if destination.parent != source.parent:
                _fsync_directory(destination.parent)
    except LegacyProjectUpdateRecoveryError:
        raise
    except BaseException:
        raise _fail("project_update_legacy_recovery_state_changed") from None
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                raise _fail(
                    "project_update_legacy_recovery_state_ambiguous"
                ) from None
        elif raw_handle is not None:
            if not close_handle(raw_handle):
                raise _fail(
                    "project_update_legacy_recovery_state_ambiguous"
                ) from None


def vault_old_lock_backup(
    paths: RecoveryPaths,
    backup_path: Path,
    *,
    expected_old_lock_bytes: bytes,
) -> dict[str, str]:
    """Move the exact retained old-lock backup into its recovery vault."""

    if (
        not isinstance(paths, RecoveryPaths)
        or type(expected_old_lock_bytes) is not bytes
        or not expected_old_lock_bytes
    ):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    source = Path(os.path.abspath(str(backup_path)))
    try:
        source.relative_to(paths.project_root)
    except ValueError:
        raise _fail("project_update_legacy_recovery_path_unsafe") from None
    destination = paths.recovery_root / "old-lock-backup"
    source_exists = os.path.lexists(source)
    destination_exists = os.path.lexists(destination)
    if source_exists and destination_exists:
        raise _fail("project_update_legacy_recovery_state_ambiguous")
    if source_exists:
        if not hmac.compare_digest(
            _read_regular(source, maximum=len(expected_old_lock_bytes)),
            expected_old_lock_bytes,
        ):
            raise _fail("project_update_legacy_recovery_state_changed")
        _move_exact_regular_no_replace(
            paths.project_root,
            source,
            destination,
            expected_old_lock_bytes,
        )
        state = "vaulted"
    elif destination_exists:
        state = "already_vaulted"
    else:
        raise _fail("project_update_legacy_recovery_state_ambiguous")
    observed = _read_regular(
        destination,
        maximum=len(expected_old_lock_bytes),
    )
    info = _safe_regular(destination, maximum=len(expected_old_lock_bytes))
    if not hmac.compare_digest(observed, expected_old_lock_bytes):
        raise _fail("project_update_legacy_recovery_state_changed")
    identity_sha256 = sha256_document(
        {
            "device": int(info.st_dev),
            "inode": int(info.st_ino),
            "modified_ns": int(info.st_mtime_ns),
            "size": int(info.st_size),
        }
    )
    return {
        "old_lock_backup_identity_sha256": identity_sha256,
        "old_lock_backup_sha256": sha256_bytes(observed),
        "state": state,
    }


def _write_exact_placeholder(path: Path) -> tuple[int, int]:
    _write_new(path, b"")
    info = _safe_regular(path, maximum=0)
    return int(info.st_dev), int(info.st_ino)


def _validated_tree_inventory(
    inventory: Mapping[str, Any],
) -> tuple[dict[str, Mapping[str, Any]], tuple[int, int], int]:
    if (
        not isinstance(inventory, Mapping)
        or inventory.get("schema")
        != "wom-kit/project-update-legacy-tree/v0.4.19"
        or type(inventory.get("records")) is not list
        or type(inventory.get("root_identity")) is not list
        or len(inventory["root_identity"]) != 2
        or any(type(value) is not int for value in inventory["root_identity"])
        or type(inventory.get("entry_count")) is not int
        or type(inventory.get("total_bytes")) is not int
    ):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    expected: dict[str, Mapping[str, Any]] = {}
    total_bytes = 0
    for raw in inventory["records"]:
        if not isinstance(raw, Mapping) or type(raw.get("logical")) is not str:
            raise _fail("project_update_legacy_recovery_binding_invalid")
        logical = str(raw["logical"])
        pure = PurePosixPath(logical)
        if (
            not logical
            or pure.is_absolute()
            or any(part in {"", ".", ".."} for part in pure.parts)
            or (os.name == "nt" and any(":" in part for part in pure.parts))
            or logical in expected
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        kind = raw.get("kind")
        common = {"device", "inode", "kind", "logical"}
        if (
            type(raw.get("device")) is not int
            or type(raw.get("inode")) is not int
            or int(raw["inode"]) <= 0
        ):
            raise _fail("project_update_legacy_recovery_binding_invalid")
        if kind == "directory":
            if set(raw) != common:
                raise _fail("project_update_legacy_recovery_binding_invalid")
        elif kind == "file":
            if (
                set(raw)
                != common
                | {"content_sha256", "modified_ns", "size"}
                or type(raw.get("modified_ns")) is not int
                or type(raw.get("size")) is not int
                or int(raw["size"]) < 0
                or _SHA_RE.fullmatch(str(raw.get("content_sha256"))) is None
            ):
                raise _fail("project_update_legacy_recovery_binding_invalid")
            total_bytes += int(raw["size"])
        else:
            raise _fail("project_update_legacy_recovery_binding_invalid")
        expected[logical] = raw
    if (
        len(expected) != inventory["entry_count"]
        or total_bytes != inventory["total_bytes"]
        or len(expected) > _MAX_TREE_ENTRIES
        or total_bytes > _MAX_TREE_BYTES
    ):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    for logical in expected:
        parent = PurePosixPath(logical).parent.as_posix()
        if parent != "." and expected.get(parent, {}).get("kind") != "directory":
            raise _fail("project_update_legacy_recovery_binding_invalid")
    return (
        expected,
        (int(inventory["root_identity"][0]), int(inventory["root_identity"][1])),
        total_bytes,
    )


def directory_tree_inventory(
    path: Path,
    *,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Bind one bounded real tree with depth-bounded retained handles."""

    if progress_callback is not None and not callable(progress_callback):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    root = Path(os.path.abspath(str(path)))
    records: list[dict[str, Any]] = []
    total_bytes = 0

    def progress() -> None:
        if progress_callback is not None:
            try:
                progress_callback(len(records), total_bytes)
            except Exception:
                pass

    def visit(
        current: Path,
        logical: str,
        depth: int,
        expected_identity: tuple[int, int] | None,
    ) -> tuple[int, int]:
        nonlocal total_bytes
        if depth > _MAX_TREE_DEPTH:
            raise _fail("project_update_legacy_recovery_path_unsafe")
        with _retained_directory(
            current,
            expected_identity=expected_identity,
        ) as held:
            identity = (int(held.st_dev), int(held.st_ino))
            try:
                with os.scandir(current) as iterator:
                    entries = sorted(iterator, key=lambda item: item.name)
            except OSError:
                raise _fail(
                    "project_update_legacy_recovery_path_unsafe"
                ) from None
            entry_bindings: dict[str, tuple[int, int]] = {}
            for entry in entries:
                if len(records) >= _MAX_TREE_ENTRIES:
                    raise _fail("project_update_legacy_recovery_path_unsafe")
                relative = f"{logical}/{entry.name}" if logical else entry.name
                try:
                    info = os.lstat(entry.path)
                except OSError:
                    raise _fail(
                        "project_update_legacy_recovery_path_unsafe"
                    ) from None
                if stat.S_ISLNK(info.st_mode) or _is_reparse(info):
                    raise _fail("project_update_legacy_recovery_path_unsafe")
                entry_identity = (int(info.st_dev), int(info.st_ino))
                entry_bindings[entry.name] = entry_identity
                if stat.S_ISDIR(info.st_mode):
                    records.append(
                        {
                            "device": entry_identity[0],
                            "inode": entry_identity[1],
                            "kind": "directory",
                            "logical": relative,
                        }
                    )
                    progress()
                    visit(
                        Path(entry.path),
                        relative,
                        depth + 1,
                        entry_identity,
                    )
                    continue
                if not stat.S_ISREG(info.st_mode) or int(info.st_nlink) != 1:
                    raise _fail("project_update_legacy_recovery_path_unsafe")
                content_sha256, size, file_identity, modified_ns = _hash_regular(
                    Path(entry.path), maximum=_MAX_TREE_BYTES
                )
                total_bytes += size
                if total_bytes > _MAX_TREE_BYTES:
                    raise _fail("project_update_legacy_recovery_path_unsafe")
                records.append(
                    {
                        "content_sha256": content_sha256,
                        "device": file_identity[0],
                        "inode": file_identity[1],
                        "kind": "file",
                        "logical": relative,
                        "modified_ns": modified_ns,
                        "size": size,
                    }
                )
                progress()
            try:
                with os.scandir(current) as iterator:
                    after_entries = list(iterator)
                after_bindings = {
                    item.name: (
                        int(os.lstat(item.path).st_dev),
                        int(os.lstat(item.path).st_ino),
                    )
                    for item in after_entries
                }
            except OSError:
                raise _fail(
                    "project_update_legacy_recovery_path_unsafe"
                ) from None
            if after_bindings != entry_bindings:
                raise _fail("project_update_legacy_recovery_state_changed")
            return identity

    root_identity = visit(root, "", 0, None)
    records.sort(key=lambda item: str(item["logical"]))
    return {
        "entry_count": len(records),
        "records": records,
        "root_identity": list(root_identity),
        "schema": "wom-kit/project-update-legacy-tree/v0.4.19",
        "total_bytes": total_bytes,
    }


def directory_tree_sha256(
    path: Path,
    *,
    progress_callback: Callable[[int, int], None] | None = None,
) -> str:
    """Hash one bounded real tree without returning names or contents."""

    return sha256_document(
        directory_tree_inventory(path, progress_callback=progress_callback)
    )


def directory_tree_matches_inventory(
    path: Path,
    inventory: Mapping[str, Any],
    *,
    retained_guard_logical: str | None = None,
) -> bool:
    """Revalidate an exact tree while one inventory file may be locked.

    On Windows an exclusive append-guard handle intentionally prevents a
    second read handle.  The caller has already hashed the complete tree
    immediately before acquiring that exact guard.  While the handle remains
    held, this verifier binds the guard by identity/size/mtime and re-hashes
    every other file, so the self-owned lock is not mistaken for an unsafe
    path.
    """

    if retained_guard_logical is not None and type(retained_guard_logical) is not str:
        raise _fail("project_update_legacy_recovery_binding_invalid")
    expected, root_identity, expected_total = _validated_tree_inventory(inventory)
    if retained_guard_logical is not None and retained_guard_logical not in expected:
        raise _fail("project_update_legacy_recovery_binding_invalid")
    root = Path(os.path.abspath(str(path)))
    observed: set[str] = set()
    total_bytes = 0

    def visit(
        current: Path,
        prefix: str,
        depth: int,
        expected_identity: tuple[int, int],
    ) -> bool:
        nonlocal total_bytes
        if depth > _MAX_TREE_DEPTH:
            raise _fail("project_update_legacy_recovery_path_unsafe")
        with _retained_directory(current, expected_identity=expected_identity):
            try:
                with os.scandir(current) as iterator:
                    entries = list(iterator)
            except OSError:
                raise _fail(
                    "project_update_legacy_recovery_path_unsafe"
                ) from None
            first_names = {entry.name for entry in entries}
            for entry in entries:
                logical = f"{prefix}/{entry.name}" if prefix else entry.name
                record = expected.get(logical)
                if record is None:
                    return False
                observed.add(logical)
                try:
                    info = os.lstat(entry.path)
                except OSError:
                    raise _fail(
                        "project_update_legacy_recovery_path_unsafe"
                    ) from None
                if stat.S_ISLNK(info.st_mode) or _is_reparse(info):
                    raise _fail("project_update_legacy_recovery_path_unsafe")
                identity = (int(info.st_dev), int(info.st_ino))
                expected_identity_value = (
                    int(record["device"]),
                    int(record["inode"]),
                )
                if record["kind"] == "directory":
                    if not stat.S_ISDIR(info.st_mode) or identity != expected_identity_value:
                        return False
                    if not visit(
                        Path(entry.path),
                        logical,
                        depth + 1,
                        expected_identity_value,
                    ):
                        return False
                    continue
                if logical == retained_guard_logical:
                    if (
                        not stat.S_ISREG(info.st_mode)
                        or int(info.st_nlink) != 1
                        or int(info.st_size) != record["size"]
                        or identity != expected_identity_value
                        or int(info.st_mtime_ns) != record["modified_ns"]
                    ):
                        return False
                    total_bytes += int(info.st_size)
                    continue
                digest, size, file_identity, modified_ns = _hash_regular(
                    Path(entry.path), maximum=_MAX_TREE_BYTES
                )
                if (
                    digest != record["content_sha256"]
                    or size != record["size"]
                    or file_identity != expected_identity_value
                    or modified_ns != record["modified_ns"]
                ):
                    return False
                total_bytes += size
            try:
                with os.scandir(current) as iterator:
                    if {entry.name for entry in iterator} != first_names:
                        return False
            except OSError:
                raise _fail(
                    "project_update_legacy_recovery_path_unsafe"
                ) from None
        return True

    return bool(
        visit(root, "", 0, root_identity)
        and observed == set(expected)
        and total_bytes == expected_total
    )


def delete_exact_inventory_tree(
    path: Path,
    inventory: Mapping[str, Any],
) -> str:
    """Delete only remaining entries from an exact recovery-owned tree.

    Missing entries are allowed so a power-cut cleanup can resume.  Every
    present file must still have the captured identity, mtime, size, digest,
    and single-link status.  Any unlisted/changed entry stops cleanup and
    preserves the tree for review.
    """

    by_logical, root_identity, _total = _validated_tree_inventory(inventory)
    if not os.path.lexists(path):
        return "already_absent"
    if os.name != "nt":
        # A descriptor-relative unlink still cannot compare-and-delete the
        # exact inode. Preserve every entry until the bound primitive exists.
        raise _fail("project_update_legacy_recovery_platform_unsupported")
    path = Path(os.path.abspath(str(path)))
    root_info = _safe_directory(path)
    if (int(root_info.st_dev), int(root_info.st_ino)) != root_identity:
        raise _fail("project_update_legacy_recovery_state_changed")
    observed: set[str] = set()

    def scan_present(
        current: Path,
        prefix: str,
        depth: int,
        identity: tuple[int, int],
    ) -> None:
        if depth > _MAX_TREE_DEPTH:
            raise _fail("project_update_legacy_recovery_path_unsafe")
        with _retained_directory(current, expected_identity=identity):
            try:
                with os.scandir(current) as iterator:
                    entries = list(iterator)
            except OSError:
                raise _fail(
                    "project_update_legacy_recovery_path_unsafe"
                ) from None
            names = {entry.name for entry in entries}
            for entry in entries:
                logical = f"{prefix}/{entry.name}" if prefix else entry.name
                expected = by_logical.get(logical)
                if expected is None:
                    raise _fail("project_update_legacy_recovery_state_changed")
                observed.add(logical)
                try:
                    info = os.lstat(entry.path)
                except OSError:
                    raise _fail(
                        "project_update_legacy_recovery_path_unsafe"
                    ) from None
                if stat.S_ISLNK(info.st_mode) or _is_reparse(info):
                    raise _fail("project_update_legacy_recovery_path_unsafe")
                exact_identity = (int(expected["device"]), int(expected["inode"]))
                if expected["kind"] == "directory":
                    if (
                        not stat.S_ISDIR(info.st_mode)
                        or (int(info.st_dev), int(info.st_ino)) != exact_identity
                    ):
                        raise _fail("project_update_legacy_recovery_state_changed")
                    scan_present(
                        Path(entry.path), logical, depth + 1, exact_identity
                    )
                else:
                    digest, size, file_identity, modified_ns = _hash_regular(
                        Path(entry.path), maximum=_MAX_TREE_BYTES
                    )
                    if (
                        digest != expected["content_sha256"]
                        or size != expected["size"]
                        or file_identity != exact_identity
                        or modified_ns != expected["modified_ns"]
                    ):
                        raise _fail(
                            "project_update_legacy_recovery_state_changed"
                        )
            try:
                with os.scandir(current) as iterator:
                    if {entry.name for entry in iterator} != names:
                        raise _fail(
                            "project_update_legacy_recovery_state_changed"
                        )
            except OSError:
                raise _fail(
                    "project_update_legacy_recovery_path_unsafe"
                ) from None

    scan_present(path, "", 0, root_identity)
    from . import legacy_cleanup_bound_delete

    for logical in sorted(
        observed,
        key=lambda value: (value.count("/"), value),
        reverse=True,
    ):
        expected = by_logical[logical]
        target = path.joinpath(*PurePosixPath(logical).parts)
        if not os.path.lexists(target):
            continue
        try:
            if expected["kind"] == "file":
                legacy_cleanup_bound_delete._delete_exact_approved_file(
                    path,
                    target,
                    {
                        "identity": {
                            "device": int(expected["device"]),
                            "inode": int(expected["inode"]),
                        },
                        "mtime_ns": int(expected["modified_ns"]),
                        "sha256": str(expected["content_sha256"]).removeprefix(
                            "sha256:"
                        ),
                        "size": int(expected["size"]),
                        "type": "file",
                    },
                )
            else:
                legacy_cleanup_bound_delete._delete_exact_approved_empty_directory(
                    path,
                    target,
                    {
                        "identity": {
                            "birthtime_ns": None,
                            "device": int(expected["device"]),
                            "inode": int(expected["inode"]),
                        },
                        "type": "directory",
                    },
                )
        except BaseException:
            if not os.path.lexists(target):
                continue
            raise _fail("project_update_legacy_recovery_state_changed") from None
        _fsync_directory(target.parent)
    try:
        legacy_cleanup_bound_delete._delete_exact_approved_empty_directory(
            path.parent,
            path,
            {
                "identity": {
                    "birthtime_ns": None,
                    "device": root_identity[0],
                    "inode": root_identity[1],
                },
                "type": "directory",
            },
        )
    except BaseException:
        if not os.path.lexists(path):
            return "deleted_exact"
        raise _fail("project_update_legacy_recovery_state_changed") from None
    _fsync_directory(path.parent)
    if os.path.lexists(path):
        raise _fail("project_update_legacy_recovery_state_ambiguous")
    return "deleted_exact"


def stage_old_transaction(
    paths: RecoveryPaths,
    *,
    old_transaction_ref: str,
    expected_tree_sha256: str,
) -> str:
    """Reversibly hide the old transaction so old clients fail closed."""

    if (
        _TRANSACTION_REF_RE.fullmatch(old_transaction_ref) is None
        or _SHA_RE.fullmatch(expected_tree_sha256) is None
    ):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    source = paths.project_root.joinpath(
        *PurePosixPath(TRANSACTION_ROOT_LOGICAL).parts,
        old_transaction_ref,
    )
    destination = paths.old_transaction_vault
    source_exists = os.path.lexists(source)
    destination_exists = os.path.lexists(destination)
    if source_exists == destination_exists:
        raise _fail("project_update_legacy_recovery_state_ambiguous")
    selected = source if source_exists else destination
    if directory_tree_sha256(selected) != expected_tree_sha256:
        raise _fail("project_update_legacy_recovery_state_changed")
    if source_exists:
        move_directory_no_replace(source, destination)
        if directory_tree_sha256(destination) != expected_tree_sha256:
            raise _fail("project_update_legacy_recovery_state_changed")
        return "staged"
    return "already_staged"


def restore_old_transaction(
    paths: RecoveryPaths,
    *,
    old_transaction_ref: str,
    expected_tree_sha256: str,
) -> str:
    """Restore the exact old namespace after a claimless denial."""

    if (
        _TRANSACTION_REF_RE.fullmatch(old_transaction_ref) is None
        or _SHA_RE.fullmatch(expected_tree_sha256) is None
    ):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    destination = paths.project_root.joinpath(
        *PurePosixPath(TRANSACTION_ROOT_LOGICAL).parts,
        old_transaction_ref,
    )
    source = paths.old_transaction_vault
    source_exists = os.path.lexists(source)
    destination_exists = os.path.lexists(destination)
    if source_exists and destination_exists:
        raise _fail("project_update_legacy_recovery_state_ambiguous")
    if destination_exists:
        if directory_tree_sha256(destination) != expected_tree_sha256:
            raise _fail("project_update_legacy_recovery_state_changed")
        return "already_restored"
    if not source_exists or directory_tree_sha256(source) != expected_tree_sha256:
        raise _fail("project_update_legacy_recovery_state_changed")
    move_directory_no_replace(source, destination)
    if directory_tree_sha256(destination) != expected_tree_sha256:
        raise _fail("project_update_legacy_recovery_state_changed")
    return "restored"


def stage_cancelled_fresh_transaction(
    paths: RecoveryPaths,
    *,
    fresh_transaction_ref: str,
    fresh_transaction_inventory: Mapping[str, Any],
) -> str:
    """No-replace stage the exact unapproved fresh tree before cleanup."""

    if (
        not isinstance(paths, RecoveryPaths)
        or _TRANSACTION_REF_RE.fullmatch(fresh_transaction_ref) is None
    ):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    _validated_tree_inventory(fresh_transaction_inventory)
    source = paths.project_root.joinpath(
        *PurePosixPath(TRANSACTION_ROOT_LOGICAL).parts,
        fresh_transaction_ref,
    )
    destination = paths.cancelled_fresh_transaction_vault
    source_exists = os.path.lexists(source)
    destination_exists = os.path.lexists(destination)
    if source_exists == destination_exists:
        raise _fail("project_update_legacy_recovery_state_ambiguous")
    selected = source if source_exists else destination
    if not directory_tree_matches_inventory(selected, fresh_transaction_inventory):
        raise _fail("project_update_legacy_recovery_state_changed")
    if source_exists:
        move_directory_no_replace(source, destination)
        if not directory_tree_matches_inventory(
            destination,
            fresh_transaction_inventory,
        ):
            raise _fail("project_update_legacy_recovery_state_changed")
        return "staged"
    return "already_staged"


def delete_cancelled_fresh_transaction(
    paths: RecoveryPaths,
    *,
    fresh_transaction_inventory: Mapping[str, Any],
) -> str:
    """Delete only the previously staged exact cancelled-fresh tree."""

    if not isinstance(paths, RecoveryPaths):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    _validated_tree_inventory(fresh_transaction_inventory)
    if not os.path.lexists(paths.cancelled_fresh_transaction_vault):
        return "already_absent"
    return delete_exact_inventory_tree(
        paths.cancelled_fresh_transaction_vault,
        fresh_transaction_inventory,
    )


def restore_claimless_preapproval_state(
    paths: RecoveryPaths,
    *,
    old_transaction_ref: str,
    old_transaction_tree_sha256: str,
    fresh_transaction_ref: str,
    fresh_transaction_inventory: Mapping[str, Any],
    expected_old_lock_bytes: bytes,
    confirm_new_context_claim_absent: Any,
    cleanup_fresh_candidate: Callable[[], bool],
) -> dict[str, str]:
    """Restore the predecessor after denial/UI/key failure with no new claim.

    A fully sealed candidate is first retired by its owning runtime subsystem;
    the remaining recovery-owned scaffold is then deleted only through its
    exact file/inode inventory.  An incomplete or changed candidate is kept
    for review instead of being widened into generic recursive deletion.
    """

    if (
        _TRANSACTION_REF_RE.fullmatch(fresh_transaction_ref) is None
        or not isinstance(fresh_transaction_inventory, Mapping)
        or type(expected_old_lock_bytes) is not bytes
        or not expected_old_lock_bytes
        or not callable(confirm_new_context_claim_absent)
        or not callable(cleanup_fresh_candidate)
    ):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    try:
        absent = confirm_new_context_claim_absent()
    except BaseException:
        raise _fail("project_update_legacy_recovery_state_ambiguous") from None
    if type(absent) is not bool or not absent:
        raise _fail("project_update_legacy_recovery_state_ambiguous")

    fresh = paths.project_root.joinpath(
        *PurePosixPath(TRANSACTION_ROOT_LOGICAL).parts,
        fresh_transaction_ref,
    )
    if os.path.lexists(fresh):
        try:
            candidate_removed = cleanup_fresh_candidate()
        except BaseException:
            raise _fail("project_update_legacy_recovery_state_ambiguous") from None
        if type(candidate_removed) is not bool or not candidate_removed:
            raise _fail("project_update_legacy_recovery_state_ambiguous")
        stage_cancelled_fresh_transaction(
            paths,
            fresh_transaction_ref=fresh_transaction_ref,
            fresh_transaction_inventory=fresh_transaction_inventory,
        )
        fresh_scaffold = delete_cancelled_fresh_transaction(
            paths,
            fresh_transaction_inventory=fresh_transaction_inventory,
        )
    elif os.path.lexists(paths.cancelled_fresh_transaction_vault):
        fresh_scaffold = delete_cancelled_fresh_transaction(
            paths,
            fresh_transaction_inventory=fresh_transaction_inventory,
        )
    else:
        # A completed prior cleanup is represented by absence plus the signed
        # recovery journal; an unexplained alternate vault is never inferred.
        fresh_scaffold = "already_absent"

    restored = restore_old_transaction(
        paths,
        old_transaction_ref=old_transaction_ref,
        expected_tree_sha256=old_transaction_tree_sha256,
    )
    live_lock = paths.project_root.joinpath(*PurePosixPath(LOCK_LOGICAL).parts)
    if not hmac.compare_digest(_read_regular(live_lock), expected_old_lock_bytes):
        raise _fail("project_update_legacy_recovery_state_changed")
    return {
        "fresh_scaffold": fresh_scaffold,
        "new_context_claim": "absent_authenticated",
        "old_lock": "preserved_exact",
        "old_transaction": restored,
    }


def active_locator_presence_read_only(project_root: Path | str) -> str:
    """Classify only the fixed locator leaf without creating or parsing it."""

    project = Path(os.path.abspath(str(project_root)))
    path = project.joinpath(*PurePosixPath(ACTIVE_LOCATOR_LOGICAL).parts)
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        transition = _locator_transition_path(path)
        try:
            info = os.lstat(transition)
        except FileNotFoundError:
            return "absent"
        except OSError:
            return "unavailable"
    except OSError:
        return "unavailable"
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or _is_reparse(info)
        or int(info.st_nlink) != 1
        or int(info.st_size) > _MAX_DOCUMENT_BYTES
    ):
        return "unsafe"
    return "present_unverified"


def _exact_regular_identity_allowing_links(
    path: Path,
    expected: bytes,
    *,
    allowed_links: frozenset[int],
) -> tuple[int, int, int]:
    """Bind exact bytes and identity while permitting one owned hard-link."""

    if type(expected) is not bytes or not allowed_links:
        raise _fail("project_update_legacy_recovery_binding_invalid")
    candidate = Path(os.path.abspath(str(path)))
    try:
        before = os.lstat(candidate)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or _is_reparse(before)
            or int(before.st_nlink) not in allowed_links
            or int(before.st_size) != len(expected)
        ):
            raise _fail("project_update_legacy_recovery_state_changed")
        descriptor = os.open(
            candidate,
            os.O_RDONLY
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            opened = os.fstat(descriptor)
            if (
                (int(opened.st_dev), int(opened.st_ino))
                != (int(before.st_dev), int(before.st_ino))
                or int(opened.st_nlink) not in allowed_links
                or int(opened.st_size) != len(expected)
            ):
                raise _fail("project_update_legacy_recovery_state_changed")
            observed = bytearray()
            while len(observed) < len(expected):
                chunk = os.read(descriptor, len(expected) - len(observed))
                if not chunk:
                    raise _fail(
                        "project_update_legacy_recovery_state_changed"
                    )
                observed.extend(chunk)
            if os.read(descriptor, 1) or not hmac.compare_digest(
                bytes(observed), expected
            ):
                raise _fail("project_update_legacy_recovery_state_changed")
            if os.name == "nt":
                import msvcrt
                from . import legacy_cleanup_bound_delete

                legacy_cleanup_bound_delete._reject_windows_alternate_streams(
                    msvcrt.get_osfhandle(descriptor),
                    directory=False,
                )
            after = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        named = os.lstat(candidate)
        if (
            (int(opened.st_dev), int(opened.st_ino), int(opened.st_nlink))
            != (int(after.st_dev), int(after.st_ino), int(after.st_nlink))
            or (int(after.st_dev), int(after.st_ino), int(after.st_nlink))
            != (int(named.st_dev), int(named.st_ino), int(named.st_nlink))
        ):
            raise _fail("project_update_legacy_recovery_state_changed")
        return int(after.st_dev), int(after.st_ino), int(after.st_nlink)
    except LegacyProjectUpdateRecoveryError:
        raise
    except BaseException:
        raise _fail("project_update_legacy_recovery_path_unsafe") from None


def _classify_lock_handoff_unretained(
    paths: RecoveryPaths,
    expected_old_lock_bytes: bytes,
    expected_fresh_lock_bytes: bytes,
) -> str:
    """Classify only exact, resumable lock-handoff namespace states."""

    if (
        not isinstance(paths, RecoveryPaths)
        or type(expected_old_lock_bytes) is not bytes
        or type(expected_fresh_lock_bytes) is not bytes
        or not expected_old_lock_bytes
        or not expected_fresh_lock_bytes
        or hmac.compare_digest(
            expected_old_lock_bytes, expected_fresh_lock_bytes
        )
    ):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    lock = paths.project_root.joinpath(*PurePosixPath(LOCK_LOGICAL).parts)
    suffix = paths.recovery_ref.removeprefix("recovery_")
    replacement = lock.parent / f".legacy-recovery-{suffix}.fresh-lock"
    backup = lock.parent / f".legacy-recovery-{suffix}.old-lock"
    vaulted = paths.recovery_root / "old-lock-backup"
    try:
        lock_exists = os.path.lexists(lock)
        replacement_exists = os.path.lexists(replacement)
        backup_exists = os.path.lexists(backup)
        vaulted_exists = os.path.lexists(vaulted)
        if lock_exists and replacement_exists and not vaulted_exists:
            if not backup_exists:
                _exact_regular_identity_allowing_links(
                    lock,
                    expected_old_lock_bytes,
                    allowed_links=frozenset({1}),
                )
                _exact_regular_identity_allowing_links(
                    replacement,
                    expected_fresh_lock_bytes,
                    allowed_links=frozenset({1}),
                )
                return "old"
            old_identity = _exact_regular_identity_allowing_links(
                lock,
                expected_old_lock_bytes,
                allowed_links=frozenset({2}),
            )
            backup_identity = _exact_regular_identity_allowing_links(
                backup,
                expected_old_lock_bytes,
                allowed_links=frozenset({2}),
            )
            _exact_regular_identity_allowing_links(
                replacement,
                expected_fresh_lock_bytes,
                allowed_links=frozenset({1}),
            )
            return (
                "backup_linked"
                if old_identity[:2] == backup_identity[:2]
                else "ambiguous"
            )
        if lock_exists and not replacement_exists:
            _exact_regular_identity_allowing_links(
                lock,
                expected_fresh_lock_bytes,
                allowed_links=frozenset({1}),
            )
            old_names = [name for name in (backup, vaulted) if os.path.lexists(name)]
            if len(old_names) != 1:
                return "ambiguous"
            _exact_regular_identity_allowing_links(
                old_names[0],
                expected_old_lock_bytes,
                allowed_links=frozenset({1}),
            )
            return "fresh"
        if not lock_exists and replacement_exists and backup_exists and not vaulted_exists:
            _exact_regular_identity_allowing_links(
                replacement,
                expected_fresh_lock_bytes,
                allowed_links=frozenset({1}),
            )
            _exact_regular_identity_allowing_links(
                backup,
                expected_old_lock_bytes,
                allowed_links=frozenset({1}),
            )
            return "legacy_gap"
    except LegacyProjectUpdateRecoveryError:
        return "ambiguous"
    return "ambiguous"


def classify_lock_handoff(
    paths: RecoveryPaths,
    expected_old_lock_bytes: bytes,
    expected_fresh_lock_bytes: bytes,
) -> str:
    """Classify a handoff while retaining both namespace parent chains."""

    if (
        not isinstance(paths, RecoveryPaths)
        or type(expected_old_lock_bytes) is not bytes
        or type(expected_fresh_lock_bytes) is not bytes
        or not expected_old_lock_bytes
        or not expected_fresh_lock_bytes
    ):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    lock_parent = paths.project_root / ".zettel-kasten"
    try:
        with _retained_parent_chains(
            paths.project_root,
            lock_parent,
            paths.recovery_root,
        ):
            return _classify_lock_handoff_unretained(
                paths,
                expected_old_lock_bytes,
                expected_fresh_lock_bytes,
            )
    except LegacyProjectUpdateRecoveryError as exc:
        if exc.code == "project_update_legacy_recovery_binding_invalid":
            raise
        return "ambiguous"


def prepare_lock_handoff_files(
    paths: RecoveryPaths,
    *,
    fresh_lock_bytes: bytes,
) -> tuple[Path, Path]:
    """Create-or-verify fresh lock bytes without interpreting backup state.

    The former zero-byte placeholder had no durable identity token and could
    be replaced between preparation and handoff.  Retained no-replace moves
    leave any existing backup name to the retained atomic classifier; that
    name may be the valid hard-link checkpoint of an interrupted handoff.
    """

    if type(fresh_lock_bytes) is not bytes or not fresh_lock_bytes:
        raise _fail("project_update_legacy_recovery_binding_invalid")
    lock_parent = paths.project_root / ".zettel-kasten"
    _safe_directory(lock_parent)
    suffix = paths.recovery_ref.removeprefix("recovery_")
    replacement = lock_parent / f".legacy-recovery-{suffix}.fresh-lock"
    backup = lock_parent / f".legacy-recovery-{suffix}.old-lock"
    if os.path.lexists(replacement):
        if not hmac.compare_digest(_read_regular(replacement), fresh_lock_bytes):
            raise _fail("project_update_legacy_recovery_state_changed")
    else:
        _write_new(replacement, fresh_lock_bytes)
    # An existing name is not accepted here and is not removed here.  It may
    # be the exact hard-link checkpoint left by a crash immediately before
    # the atomic replacement.  The retained-handle handoff classifier binds
    # that identity to the live old lock, or fails closed if it is unrelated.
    return replacement, backup


def atomic_replace_lock_with_backup_windows(
    lock_path: Path,
    replacement_path: Path,
    backup_path: Path,
    *,
    expected_old_bytes: bytes,
    expected_fresh_bytes: bytes,
    _failpoint: Callable[[str], None] | None = None,
) -> str:
    """Resume-safe, no-gap exact lock handoff without ``ReplaceFileW``.

    The old public lock first receives a no-replace recovery-owned hard-link.
    A retained fresh handle then uses ``FileRenameInfoEx`` with replace and
    POSIX semantics to exchange the *name* in one kernel operation.  Thus a
    predecessor client can never observe an absent public lock: before the
    atomic point it sees old bytes, afterwards it sees fresh bytes, while the
    durable hard-link always preserves the old bytes for rollback.

    The protocol serializes cooperating WOM processes through the caller's
    terminal-control lease and recovery guard, and requires the already
    approved external-writer-quiescence assertion.  An arbitrary same-user
    process that deliberately ignores those locks is outside that guarantee;
    nevertheless all three names are rebound immediately before the syscall
    and any replacement observed at that seam is preserved and fails closed.
    """

    if os.name != "nt":
        raise _fail("project_update_legacy_recovery_lock_replace_unavailable")
    if (
        type(expected_old_bytes) is not bytes
        or type(expected_fresh_bytes) is not bytes
        or not expected_old_bytes
        or not expected_fresh_bytes
        or (_failpoint is not None and not callable(_failpoint))
        or len({os.path.normcase(os.path.abspath(item)) for item in (lock_path, replacement_path, backup_path)}) != 3
        or lock_path.parent != replacement_path.parent
        or lock_path.parent != backup_path.parent
    ):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    if hmac.compare_digest(expected_old_bytes, expected_fresh_bytes):
        raise _fail("project_update_legacy_recovery_binding_invalid")
    project_root = _control_project_root(lock_path)

    def exact_final() -> bool:
        try:
            return bool(
                not os.path.lexists(replacement_path)
                and hmac.compare_digest(
                    _read_regular(
                        lock_path,
                        maximum=len(expected_fresh_bytes),
                    ),
                    expected_fresh_bytes,
                )
                and hmac.compare_digest(
                    _read_regular(
                        backup_path,
                        maximum=len(expected_old_bytes),
                    ),
                    expected_old_bytes,
                )
            )
        except LegacyProjectUpdateRecoveryError:
            return False

    if exact_final():
        return "already_replaced"

    import ctypes
    import msvcrt
    from ctypes import wintypes
    from . import legacy_cleanup_bound_delete, private_metadata_win32

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    create_hard_link = kernel32.CreateHardLinkW
    create_hard_link.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPVOID,
    ]
    create_hard_link.restype = wintypes.BOOL
    set_information = kernel32.SetFileInformationByHandle
    set_information.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    set_information.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    invalid_handle = wintypes.HANDLE(-1).value
    old_descriptor: int | None = None
    fresh_descriptor: int | None = None
    old_raw_handle: int | None = None
    fresh_raw_handle: int | None = None

    def open_exact(
        path: Path,
        expected: bytes,
        *,
        allow_two_links: bool,
        share_delete: bool,
    ) -> tuple[int, int, tuple[int, int]]:
        share = 0x00000001 | (0x00000004 if share_delete else 0)
        handle = create_file(
            str(path),
            0x80000000 | 0x00010000 | 0x00000080,
            share,
            None,
            3,
            0x00200000 | 0x08000000,
            None,
        )
        value = handle if isinstance(handle, int) else getattr(handle, "value", None)
        if value in {None, invalid_handle}:
            raise OSError("lock_exact_open_failed")
        raw_handle = int(value)
        try:
            descriptor = msvcrt.open_osfhandle(
                raw_handle,
                os.O_RDONLY | getattr(os, "O_BINARY", 0),
            )
        except BaseException:
            close_handle(raw_handle)
            raise
        raw_handle = msvcrt.get_osfhandle(descriptor)
        opened = os.fstat(descriptor)
        named = os.lstat(path)
        allowed_links = {1, 2} if allow_two_links else {1}
        identity = (int(opened.st_dev), int(opened.st_ino))
        if (
            not stat.S_ISREG(opened.st_mode)
            or stat.S_ISLNK(opened.st_mode)
            or _is_reparse(opened)
            or int(opened.st_nlink) not in allowed_links
            or int(opened.st_size) != len(expected)
            or (int(named.st_dev), int(named.st_ino)) != identity
        ):
            os.close(descriptor)
            raise OSError("lock_exact_binding_failed")
        os.lseek(descriptor, 0, os.SEEK_SET)
        observed = bytearray()
        while len(observed) < len(expected):
            chunk = os.read(descriptor, len(expected) - len(observed))
            if not chunk:
                os.close(descriptor)
                raise OSError("lock_exact_read_failed")
            observed.extend(chunk)
        if os.read(descriptor, 1) or not hmac.compare_digest(
            bytes(observed), expected
        ):
            os.close(descriptor)
            raise OSError("lock_exact_bytes_changed")
        try:
            legacy_cleanup_bound_delete._reject_windows_alternate_streams(
                raw_handle,
                directory=False,
            )
        except BaseException:
            os.close(descriptor)
            raise
        return descriptor, raw_handle, identity

    try:
        with _retained_parent_chains(project_root, lock_path.parent):
            # A pre-release two-move attempt may have left this exact midpoint.
            # It is recoverable, but new executions never create such a gap.
            if not os.path.lexists(lock_path):
                if (
                    not hmac.compare_digest(
                        _read_regular(
                            backup_path,
                            maximum=len(expected_old_bytes),
                        ),
                        expected_old_bytes,
                    )
                    or not hmac.compare_digest(
                        _read_regular(
                            replacement_path,
                            maximum=len(expected_fresh_bytes),
                        ),
                        expected_fresh_bytes,
                    )
                ):
                    raise OSError("legacy_midpoint_changed")
                _move_exact_regular_no_replace(
                    project_root,
                    replacement_path,
                    lock_path,
                    expected_fresh_bytes,
                )
                if not exact_final():
                    raise OSError("legacy_midpoint_unproved")
                return "replaced"

            old_descriptor, old_raw_handle, old_identity = open_exact(
                lock_path,
                expected_old_bytes,
                allow_two_links=True,
                share_delete=True,
            )
            if os.path.lexists(backup_path):
                backup_info = os.lstat(backup_path)
                if (
                    not stat.S_ISREG(backup_info.st_mode)
                    or stat.S_ISLNK(backup_info.st_mode)
                    or _is_reparse(backup_info)
                    or (int(backup_info.st_dev), int(backup_info.st_ino))
                    != old_identity
                    or int(os.fstat(old_descriptor).st_nlink) != 2
                ):
                    raise OSError("old_backup_changed")
            else:
                if int(os.fstat(old_descriptor).st_nlink) != 1:
                    raise OSError("old_lock_link_count_changed")
                if not create_hard_link(
                    str(backup_path),
                    str(lock_path),
                    None,
                ):
                    raise OSError("old_backup_link_failed")
                backup_info = os.lstat(backup_path)
                named_old = os.lstat(lock_path)
                if (
                    (int(backup_info.st_dev), int(backup_info.st_ino))
                    != old_identity
                    or (int(named_old.st_dev), int(named_old.st_ino))
                    != old_identity
                    or int(os.fstat(old_descriptor).st_nlink) != 2
                ):
                    raise OSError("old_backup_link_unproved")
                _fsync_directory(lock_path.parent)
            if _failpoint is not None:
                _failpoint("old_backup_durable_before_atomic_replace")
            if not os.path.lexists(lock_path):
                raise OSError("public_lock_name_missing")

            fresh_descriptor, fresh_raw_handle, fresh_identity = open_exact(
                replacement_path,
                expected_fresh_bytes,
                allow_two_links=False,
                share_delete=False,
            )
            if (
                (int(os.lstat(lock_path).st_dev), int(os.lstat(lock_path).st_ino))
                != old_identity
                or (
                    int(os.lstat(replacement_path).st_dev),
                    int(os.lstat(replacement_path).st_ino),
                )
                != fresh_identity
            ):
                raise OSError("lock_names_changed")
            if _failpoint is not None:
                _failpoint("lock_names_bound_before_atomic_replace")
            rebound_public = os.lstat(lock_path)
            rebound_backup = os.lstat(backup_path)
            rebound_fresh = os.lstat(replacement_path)
            if (
                (int(rebound_public.st_dev), int(rebound_public.st_ino))
                != old_identity
                or (int(rebound_backup.st_dev), int(rebound_backup.st_ino))
                != old_identity
                or (int(rebound_fresh.st_dev), int(rebound_fresh.st_ino))
                != fresh_identity
                or int(os.fstat(old_descriptor).st_nlink) != 2
                or int(os.fstat(fresh_descriptor).st_nlink) != 1
            ):
                raise OSError("lock_names_changed_before_atomic_replace")
            rename = private_metadata_win32.file_rename_info_buffer(
                lock_path,
                replace_if_exists=True,
            )
            # FileRenameInfo (class 3) cannot replace a named file whose old
            # inode is retained, even when every handle grants share-delete.
            # FileRenameInfoEx (class 22) with POSIX semantics is the Windows
            # no-gap primitive: DWORD Flags overlays the legacy BOOLEAN field.
            ctypes.c_uint32.from_buffer(rename.backing, 0).value = 0x00000001 | 0x00000002
            if not set_information(
                fresh_raw_handle,
                22,
                rename.backing,
                rename.api_buffer_size,
            ):
                raise OSError("lock_replace_failed")
            if _failpoint is not None:
                _failpoint("public_lock_atomically_replaced")
            public_info = os.lstat(lock_path)
            backup_info = os.lstat(backup_path)
            if (
                os.path.lexists(replacement_path)
                or (int(public_info.st_dev), int(public_info.st_ino))
                != fresh_identity
                or (int(backup_info.st_dev), int(backup_info.st_ino))
                != old_identity
                or int(os.fstat(old_descriptor).st_nlink) != 1
                or int(os.fstat(fresh_descriptor).st_nlink) != 1
            ):
                raise OSError("lock_replace_unproved")
            _fsync_directory(lock_path.parent)
    except LegacyProjectUpdateRecoveryError:
        raise
    except BaseException:
        if exact_final():
            return "already_replaced"
        raise _fail(
            "project_update_legacy_recovery_lock_replace_ambiguous"
        ) from None
    finally:
        close_failed = False
        for descriptor in (fresh_descriptor, old_descriptor):
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    close_failed = True
        if close_failed:
            raise _fail(
                "project_update_legacy_recovery_lock_replace_ambiguous"
            ) from None
    if not exact_final():
        raise _fail("project_update_legacy_recovery_lock_replace_ambiguous")
    return "replaced"
