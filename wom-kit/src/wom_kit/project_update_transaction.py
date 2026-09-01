"""Crash-durable, privacy-safe transaction evidence for project updates.

The primitive in this module never chooses a version, displays approval UI,
downloads bytes, or writes project-domain files.  It binds immutable intent,
private exact preimages and runtime supply, a live O_EXCL lock, and a monotonic
checkpoint state machine.  Recovery is classification only: mixed or unknown
live state never authorizes an automatic action.
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
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterator, Literal, Mapping, Sequence


INTENT_SCHEMA = "wom-kit/project-update-transaction-intent/v0.4.3"
MARKER_SCHEMA = "wom-kit/project-update-transaction-reservation/v0.4.3"
INTENT_SEAL_SCHEMA = "wom-kit/project-update-transaction-intent-seal/v0.4.3"
LOCK_SCHEMA = "wom-kit/project-update-transaction-lock/v0.4.3"
RESERVATION_LOCK_BACKLINK_SCHEMA = (
    "wom-kit/project-update-transaction-reservation-lock-backlink/v0.4.3"
)
RESERVATION_ABORT_INTENT_SCHEMA = (
    "wom-kit/project-update-reservation-abort-intent/v0.4.3"
)
RESERVATION_ABORT_RECEIPT_SCHEMA = (
    "wom-kit/project-update-reservation-abort-receipt/v0.4.3"
)
RESERVATION_ABORT_PLAN_SCHEMA = (
    "wom-kit/project-update-reservation-abort-plan/v0.4.3"
)
RESERVATION_ABORT_CLEANUP_PLAN_SCHEMA = (
    "wom-kit/project-update-reservation-abort-cleanup-plan/v0.4.17"
)
RESERVATION_ABORT_CLEANUP_RESULT_SCHEMA = (
    "wom-kit/project-update-reservation-abort-cleanup-result/v0.4.17"
)
LOCK_BACKLINK_SCHEMA = "wom-kit/project-update-transaction-lock-backlink/v0.4.3"
CHECKPOINT_SCHEMA = "wom-kit/project-update-transaction-checkpoint/v0.4.3"
PUBLIC_SUMMARY_SCHEMA = "wom-kit/project-update-transaction-public-summary/v0.4.3"
RESERVATION_PUBLIC_SUMMARY_SCHEMA = (
    "wom-kit/project-update-reservation-public-summary/v0.4.3"
)
INSPECTION_SCHEMA = "wom-kit/project-update-transaction-inspection/v0.4.3"
LEGACY_CLEANUP_PLAN_SCHEMA = (
    "wom-kit/project-update-transaction-cleanup-plan/v0.4.3"
)
CLEANUP_PLAN_SCHEMA = (
    "wom-kit/project-update-transaction-cleanup-plan/v0.4.16"
)
LEGACY_CLEANUP_PLAN_NAME = "cleanup-plan.json"
CLEANUP_PLAN_NAME = "cleanup-plan-v0416.json"
ORPHAN_SUMMARY_SCHEMA = "wom-kit/project-update-orphan-summary/v0.4.3"
RUNTIME_BUNDLE_INVENTORY_SCHEMA = "wom-kit/project-update-runtime-bundle-inventory/v0.4.3"
RUNTIME_CANDIDATE_BINDING_SCHEMA = (
    "wom-kit/project-update-runtime-candidate-binding/v0.4.3"
)
RUNTIME_CANDIDATE_TREE_SCHEMA = (
    "wom-kit/project-update-runtime-candidate-tree/v0.4.3"
)
PROJECT_RUNTIME_CANDIDATE_SCHEMA = "wom-kit/project-runtime-candidate/v0.1"
LOCK_OBSERVATION_SCHEMA = "wom-kit/project-update-live-lock-observation/v0.4.3"
CANDIDATE_ABSENCE_SCHEMA = (
    "wom-kit/project-update-runtime-candidate-absence/v0.4.3"
)
CANDIDATE_CLEANUP_PLAN_SCHEMA = (
    "wom-kit/project-update-runtime-candidate-cleanup-plan/v0.4.3"
)
CANDIDATE_CLEANUP_RECEIPT_SCHEMA = (
    "wom-kit/project-update-runtime-candidate-cleanup-receipt/v0.4.3"
)
RUNTIME_PARENT_RESTORATION_SCHEMA = (
    "wom-kit/project-update-runtime-parent-restoration/v0.4.3"
)
RUNTIME_PATH_IDENTITIES_SCHEMA = (
    "wom-kit/project-update-runtime-path-identities/v0.4.3"
)

TRANSACTION_ROOT_LOGICAL = ".zettel-kasten/private/version-updates"
PROJECT_UPDATE_LOCK_LOGICAL = ".zettel-kasten/version-update.lock"
TRANSACTION_REF_RE = re.compile(r"^update_[0-9a-f]{32}$")
OWNERSHIP_NONCE_RE = re.compile(r"^[0-9a-f]{32}$")
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+-]{0,127}$")
TARGET_TAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
PREIMAGE_KEY_RE = re.compile(r"^[a-z][a-z0-9._:-]{0,127}$")

MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
MAX_JOURNAL_BYTES = 64 * 1024 * 1024
MAX_PRIVATE_BLOB_BYTES = 512 * 1024 * 1024
MAX_PRIVATE_BLOBS = 256
MAX_COMPONENTS = 256
MAX_CLAIM_EVIDENCE_ITEMS = 16
MAX_RUNTIME_CANDIDATE_ENTRIES = 500_000
MAX_RUNTIME_CANDIDATE_FILE_BYTES = 2 * 1024 * 1024 * 1024
MAX_TERMINAL_CLEANUP_SCAN_ENTRIES = 256
MAX_TRANSACTION_DESCENDANT_SCAN_ENTRIES = (
    MAX_RUNTIME_CANDIDATE_ENTRIES
    + MAX_PRIVATE_BLOBS
    + (MAX_COMPONENTS * 3)
    + 1024
)

RUNTIME_CANDIDATE_NAME = "runtime-candidate"
RUNTIME_CANDIDATE_SEAL_NAME = "runtime-candidate-seal.json"
RUNTIME_REPAIR_PREIMAGE_NAME = "runtime-repair-preimage"
RUNTIME_CANDIDATE_RECEIPT_NAME = "runtime-receipt.json"
RUNTIME_PARENT_LOGICAL = ".zettel-kasten/runtimes"
PRIVATE_BINDINGS_NAME = "private-bindings"
RESERVATION_LOCK_BACKLINK_NAME = "reservation-lock-backlink.json"
RESERVATION_ABORT_INTENT_NAME = "reservation-abort-intent.json"
RESERVATION_ABORT_RECEIPT_NAME = "reservation-abort-receipt.json"
RESERVATION_ABORT_CLEANUP_PLAN_NAME = (
    "reservation-abort-cleanup-plan-v0417.json"
)
SEALED_LOCK_BACKLINK_NAME = "lock-backlink.json"

ABSENT_COMPONENT_SHA256 = "sha256:" + hashlib.sha256(
    b"wom-kit/project-update-component-absent/v0.4.3\n"
).hexdigest()
CHECKPOINT_CHAIN_START_SHA256 = "sha256:" + hashlib.sha256(
    b"wom-kit/project-update-checkpoint-chain-start/v0.4.3\n"
).hexdigest()

PRIVACY_FLAGS = {
    "absolute_paths_forbidden": True,
    "credentials_forbidden": True,
    "old_runtime_and_pin_preservation_default": True,
    "private_bytes_in_private_subtrees_only": True,
    "public_paths_are_logical": True,
    "public_payloads_are_content_free": True,
    "urls_forbidden": True,
}

COMPONENT_ROLES = (
    "source",
    "runtime",
    "launcher",
    "non_active_pin",
    "receipt",
    "active_pin",
)
CONTROL_PHASES = (
    "lock_backlinked",
    "preapproval_cancel_requested",
    "preapproval_cancelled",
    "approval_bound",
    "domain_committed",
    "rollback_authorized",
    "rollback_effect",
    "rollback_verified",
    "claim_succeeded",
    "ready_to_unlock",
    "lock_released",
    "completed",
)
ALLOWED_CHECKPOINT_PHASES = frozenset((*COMPONENT_ROLES, *CONTROL_PHASES))

CheckpointStage = Literal["intent", "verified"]
ComponentOverallState = Literal[
    "prewrite_exact", "mixed_exact", "complete_exact", "unknown"
]
JournalState = Literal["exact", "tail_torn", "corrupt"]
TerminalCleanupArtifactState = Literal[
    "absent",
    "observed_or_scan_incomplete",
    "active_lock_changed",
]


class ProjectUpdateTransactionError(RuntimeError):
    """Fixed path-free failure codes; exception text never leaks local data."""

    _CODES = frozenset(
        {
            "project_update_transaction_invalid",
            "project_update_transaction_exists",
            "project_update_transaction_not_found",
            "project_update_transaction_path_unsafe",
            "project_update_transaction_intent_invalid",
            "project_update_transaction_lock_invalid",
            "project_update_transaction_checkpoint_invalid",
            "project_update_transaction_checkpoint_write_failed",
            "project_update_transaction_state_transition_invalid",
            "project_update_transaction_journal_degraded",
            "project_update_transaction_durability_unverified",
            "project_update_transaction_cleanup_refused",
            "project_update_transaction_not_sealed",
            "project_update_transaction_candidate_invalid",
            "project_update_transaction_scan_incomplete",
        }
    )

    def __init__(self, code: str) -> None:
        self.code = code if code in self._CODES else "project_update_transaction_invalid"
        super().__init__(self.code)


def _fail(code: str) -> ProjectUpdateTransactionError:
    return ProjectUpdateTransactionError(code)


class _DuplicateKey(ValueError):
    pass


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey(key)
        result[key] = value
    return result


def canonical_json_bytes(value: Any) -> bytes:
    try:
        raw = json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise _fail("project_update_transaction_invalid") from None
    if len(raw) > MAX_DOCUMENT_BYTES:
        raise _fail("project_update_transaction_invalid")
    return raw


def _document_bytes(value: Any) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def sha256_bytes(value: bytes) -> str:
    if type(value) is not bytes:
        raise _fail("project_update_transaction_invalid")
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_document(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def digest_component(value: bytes | None) -> str:
    return ABSENT_COMPONENT_SHA256 if value is None else sha256_bytes(value)


def _digest(value: Any, *, code: str) -> str:
    if type(value) is not str or SHA256_RE.fullmatch(value) is None:
        raise _fail(code)
    return value


def _token(value: Any, *, code: str) -> str:
    if type(value) is not str or SAFE_TOKEN_RE.fullmatch(value) is None:
        raise _fail(code)
    lowered = value.lower()
    if (
        "://" in lowered
        or lowered.startswith(("file:", "http:", "https:"))
        or any(word in lowered for word in ("credential", "password", "secret="))
    ):
        raise _fail(code)
    return value


def _transaction_ref(value: Any) -> str:
    if type(value) is not str or TRANSACTION_REF_RE.fullmatch(value) is None:
        raise _fail("project_update_transaction_path_unsafe")
    return value


def _target_tag(value: Any) -> str:
    if type(value) is not str or TARGET_TAG_RE.fullmatch(value) is None:
        raise _fail("project_update_transaction_intent_invalid")
    return value


def _transaction_logical_ref(value: str) -> str:
    return f"{TRANSACTION_ROOT_LOGICAL}/{_transaction_ref(value)}"


def _logical_path(value: Any) -> str:
    if type(value) is not str or not value or "\\" in value:
        raise _fail("project_update_transaction_intent_invalid")
    try:
        encoded = value.encode("utf-8", errors="strict")
    except UnicodeError:
        raise _fail("project_update_transaction_intent_invalid") from None
    candidate = PurePosixPath(value)
    if (
        len(encoded) > 512
        or candidate.is_absolute()
        or value != candidate.as_posix()
        or any(part in {"", ".", ".."} for part in candidate.parts)
        or re.match(r"^[A-Za-z]:", value) is not None
        or "://" in value.lower()
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise _fail("project_update_transaction_intent_invalid")
    return value


def _private_key(value: Any) -> str:
    if type(value) is not str or PREIMAGE_KEY_RE.fullmatch(value) is None:
        raise _fail("project_update_transaction_intent_invalid")
    if any(word in value.lower() for word in ("credential", "password", "secret")):
        raise _fail("project_update_transaction_intent_invalid")
    return value


def _parse_json(raw: bytes, *, code: str) -> Any:
    try:
        return json.loads(
            raw.decode("ascii", errors="strict"),
            object_pairs_hook=_no_duplicate_keys,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()),
        )
    except (UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        raise _fail(code) from None


def _parse_document(raw: bytes, *, code: str) -> dict[str, Any]:
    if (
        type(raw) is not bytes
        or len(raw) > MAX_DOCUMENT_BYTES + 1
        or not raw.endswith(b"\n")
        or raw.endswith(b"\n\n")
    ):
        raise _fail(code)
    body = raw[:-1]
    value = _parse_json(body, code=code)
    if type(value) is not dict:
        raise _fail(code)
    try:
        expected = canonical_json_bytes(value)
    except ProjectUpdateTransactionError:
        raise _fail(code) from None
    if not hmac.compare_digest(body, expected):
        raise _fail(code)
    return value


def _is_reparse(info: os.stat_result) -> bool:
    return bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _absolute(path: Path | str) -> Path:
    try:
        return Path(os.path.abspath(os.fspath(path)))
    except (TypeError, ValueError, OSError):
        raise _fail("project_update_transaction_path_unsafe") from None


def _within(path: Path, root: Path) -> None:
    try:
        common = os.path.commonpath(
            (os.path.normcase(str(path)), os.path.normcase(str(root)))
        )
    except (ValueError, OSError):
        raise _fail("project_update_transaction_path_unsafe") from None
    if os.path.normcase(common) != os.path.normcase(str(root)):
        raise _fail("project_update_transaction_path_unsafe")


def _chain(path: Path) -> list[Path]:
    absolute = _absolute(path)
    current = Path(absolute.anchor)
    result = [current]
    for part in absolute.parts[1:]:
        current = current / part
        result.append(current)
    return result


def _safe_existing_chain(path: Path, *, directory: bool) -> None:
    members = _chain(path)
    for index, member in enumerate(members):
        try:
            info = member.lstat()
        except OSError:
            raise _fail("project_update_transaction_path_unsafe") from None
        if stat.S_ISLNK(info.st_mode) or _is_reparse(info):
            raise _fail("project_update_transaction_path_unsafe")
        if index < len(members) - 1 and not stat.S_ISDIR(info.st_mode):
            raise _fail("project_update_transaction_path_unsafe")
    if directory and not stat.S_ISDIR(members[-1].lstat().st_mode):
        raise _fail("project_update_transaction_path_unsafe")


def _safe_directory(path: Path, *, within: Path) -> os.stat_result:
    _within(path, within)
    try:
        info = path.lstat()
    except OSError:
        raise _fail("project_update_transaction_path_unsafe") from None
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or _is_reparse(info):
        raise _fail("project_update_transaction_path_unsafe")
    return info


def _safe_regular(path: Path, *, within: Path) -> os.stat_result:
    _within(path, within)
    try:
        info = path.lstat()
    except OSError:
        raise _fail("project_update_transaction_path_unsafe") from None
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or _is_reparse(info)
        or info.st_nlink != 1
    ):
        raise _fail("project_update_transaction_path_unsafe")
    return info


def _mkdirs(project: Path, logical: str) -> Path:
    current = project
    for part in PurePosixPath(logical).parts:
        candidate = current / part
        _within(candidate, project)
        created = False
        try:
            candidate.mkdir(mode=0o700)
            created = True
        except FileExistsError:
            pass
        except OSError:
            raise _fail("project_update_transaction_path_unsafe") from None
        _safe_directory(candidate, within=project)
        if created:
            _require_directory_durable(current)
        current = candidate
    return current


def _flags(value: int) -> int:
    return value | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)


def _write_all(descriptor: int, value: bytes) -> None:
    view = memoryview(value)
    position = 0
    while position < len(view):
        count = os.write(descriptor, view[position:])
        if count <= 0:
            raise OSError("short write")
        position += count


def _read_regular_with_info(
    path: Path,
    *,
    within: Path,
    maximum: int = MAX_PRIVATE_BLOB_BYTES,
) -> tuple[bytes, os.stat_result]:
    named = _safe_regular(path, within=within)
    if named.st_size > maximum:
        raise _fail("project_update_transaction_invalid")
    try:
        descriptor = os.open(path, _flags(os.O_RDONLY))
    except OSError:
        raise _fail("project_update_transaction_path_unsafe") from None
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or (
                named.st_ino
                and opened.st_ino
                and (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino)
            )
        ):
            raise _fail("project_update_transaction_path_unsafe")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, maximum + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum:
                raise _fail("project_update_transaction_invalid")
        value = b"".join(chunks)
        opened_after = os.fstat(descriptor)
        after = _safe_regular(path, within=within)
        if (
            (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
            != (
                opened_after.st_dev,
                opened_after.st_ino,
                opened_after.st_size,
                opened_after.st_mtime_ns,
            )
            or (opened_after.st_dev, opened_after.st_ino)
            != (after.st_dev, after.st_ino)
            or opened_after.st_size != after.st_size
            or opened_after.st_mtime_ns != after.st_mtime_ns
        ):
            raise _fail("project_update_transaction_path_unsafe")
        return value, opened_after
    finally:
        os.close(descriptor)


def _read_regular(
    path: Path,
    *,
    within: Path,
    maximum: int = MAX_PRIVATE_BLOB_BYTES,
) -> bytes:
    return _read_regular_with_info(path, within=within, maximum=maximum)[0]


def _hash_regular_with_info(
    path: Path,
    *,
    within: Path,
    maximum: int = MAX_RUNTIME_CANDIDATE_FILE_BYTES,
) -> tuple[str, int, os.stat_result]:
    """Hash one exact regular file without retaining its private bytes."""

    named = _safe_regular(path, within=within)
    if named.st_size > maximum:
        raise _fail("project_update_transaction_candidate_invalid")
    try:
        descriptor = os.open(path, _flags(os.O_RDONLY))
    except OSError:
        raise _fail("project_update_transaction_path_unsafe") from None
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or (
                named.st_ino
                and opened.st_ino
                and (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino)
            )
        ):
            raise _fail("project_update_transaction_path_unsafe")
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > maximum:
                raise _fail("project_update_transaction_candidate_invalid")
            digest.update(chunk)
        opened_after = os.fstat(descriptor)
        after = _safe_regular(path, within=within)
        if (
            (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
            != (
                opened_after.st_dev,
                opened_after.st_ino,
                opened_after.st_size,
                opened_after.st_mtime_ns,
            )
            or (opened_after.st_dev, opened_after.st_ino)
            != (after.st_dev, after.st_ino)
            or total != opened_after.st_size
        ):
            raise _fail("project_update_transaction_path_unsafe")
        return "sha256:" + digest.hexdigest(), total, opened_after
    finally:
        os.close(descriptor)


def _write_new(path: Path, value: bytes, *, within: Path) -> None:
    _within(path, within)
    try:
        descriptor = os.open(path, _flags(os.O_WRONLY | os.O_CREAT | os.O_EXCL), 0o600)
    except FileExistsError:
        raise _fail("project_update_transaction_exists") from None
    except OSError:
        raise _fail("project_update_transaction_path_unsafe") from None
    try:
        _write_all(descriptor, value)
        os.fsync(descriptor)
    except OSError:
        raise _fail("project_update_transaction_durability_unverified") from None
    finally:
        os.close(descriptor)
    if not hmac.compare_digest(_read_regular(path, within=within), value):
        raise _fail("project_update_transaction_invalid")


@dataclass(frozen=True)
class DirectoryDurability:
    attempted: bool
    durable: bool
    mechanism: str
    result_code: str

    def public_document(self) -> dict[str, Any]:
        return {
            "attempted": self.attempted,
            "durable": self.durable,
            "mechanism": self.mechanism,
            "result_code": self.result_code,
        }


def _fsync_directory(path: Path) -> DirectoryDurability:
    if os.name != "nt":
        try:
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except OSError:
            return DirectoryDurability(True, False, "posix_fsync", "directory_fsync_failed")
        return DirectoryDurability(True, True, "posix_fsync", "directory_fsync_succeeded")

    try:
        import ctypes
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
        flush = kernel32.FlushFileBuffers
        flush.argtypes = [wintypes.HANDLE]
        flush.restype = wintypes.BOOL
        close = kernel32.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close.restype = wintypes.BOOL
        generic_write = 0x40000000
        share_all = 0x00000001 | 0x00000002 | 0x00000004
        open_existing = 3
        backup_semantics = 0x02000000
        open_reparse = 0x00200000
        invalid = wintypes.HANDLE(-1).value
        handle = create_file(
            str(path),
            generic_write,
            share_all,
            None,
            open_existing,
            backup_semantics | open_reparse,
            None,
        )
        if handle == invalid:
            return DirectoryDurability(
                True,
                False,
                "windows_FlushFileBuffers",
                "directory_open_failed",
            )
        try:
            succeeded = bool(flush(handle))
        finally:
            close(handle)
        return DirectoryDurability(
            True,
            succeeded,
            "windows_FlushFileBuffers",
            "directory_flush_succeeded" if succeeded else "directory_flush_failed",
        )
    except (ImportError, AttributeError, OSError):
        return DirectoryDurability(
            True,
            False,
            "windows_FlushFileBuffers",
            "directory_flush_unavailable",
        )


def _require_directory_durable(path: Path) -> DirectoryDurability:
    result = _fsync_directory(path)
    if not result.durable:
        raise _fail("project_update_transaction_durability_unverified")
    return result


@dataclass(frozen=True)
class ProjectUpdateBindings:
    preflight_sha256: str
    source_sha256: str
    config_sha256: str
    ref_sha256: str
    pin_sha256: str
    launcher_sha256: str
    runtime_sha256: str
    receipt_sha256: str
    bundle_sha256: str

    def __post_init__(self) -> None:
        for value in self.document().values():
            _digest(value, code="project_update_transaction_intent_invalid")

    def document(self) -> dict[str, str]:
        return {name: getattr(self, name) for name in sorted(self.__dataclass_fields__)}

    @classmethod
    def from_document(cls, value: Any) -> "ProjectUpdateBindings":
        expected = set(cls.__dataclass_fields__)
        if type(value) is not dict or set(value) != expected:
            raise _fail("project_update_transaction_intent_invalid")
        return cls(**{name: value[name] for name in expected})


@dataclass(frozen=True)
class PrivateBlobRecord:
    logical_key: str
    relative_path: str
    size: int
    sha256: str

    def __post_init__(self) -> None:
        _private_key(self.logical_key)
        _logical_path(self.relative_path)
        if type(self.size) is not int or not 0 <= self.size <= MAX_PRIVATE_BLOB_BYTES:
            raise _fail("project_update_transaction_intent_invalid")
        _digest(self.sha256, code="project_update_transaction_intent_invalid")

    def document(self) -> dict[str, Any]:
        return {
            "logical_key": self.logical_key,
            "relative_path": self.relative_path,
            "sha256": self.sha256,
            "size": self.size,
        }


@dataclass(frozen=True)
class ProjectUpdateComponent:
    component_ref: str
    role: str
    sequence: int
    logical_target: str
    pre_sha256: str
    post_sha256: str
    preimage_key: str | None
    preserve_old_value: bool = True

    def __post_init__(self) -> None:
        _token(self.component_ref, code="project_update_transaction_intent_invalid")
        if (
            self.role not in COMPONENT_ROLES
            or type(self.sequence) is not int
            or self.sequence <= 0
        ):
            raise _fail("project_update_transaction_intent_invalid")
        _logical_path(self.logical_target)
        _digest(self.pre_sha256, code="project_update_transaction_intent_invalid")
        _digest(self.post_sha256, code="project_update_transaction_intent_invalid")
        if self.preimage_key is not None:
            _private_key(self.preimage_key)
        if self.preserve_old_value is not True:
            raise _fail("project_update_transaction_intent_invalid")

    def document(self) -> dict[str, Any]:
        return {
            "component_ref": self.component_ref,
            "logical_target": self.logical_target,
            "post_sha256": self.post_sha256,
            "pre_sha256": self.pre_sha256,
            "preimage_key": self.preimage_key,
            "preserve_old_value": self.preserve_old_value,
            "role": self.role,
            "sequence": self.sequence,
        }


def _blob_record(key: str, value: bytes, *, root_name: str) -> PrivateBlobRecord:
    validated = _private_key(key)
    relative = f"{root_name}/{hashlib.sha256(validated.encode('ascii')).hexdigest()}.bin"
    return PrivateBlobRecord(validated, relative, len(value), sha256_bytes(value))


def _records_from_document(value: Any, *, root_name: str) -> tuple[PrivateBlobRecord, ...]:
    if type(value) is not list:
        raise _fail("project_update_transaction_intent_invalid")
    records: list[PrivateBlobRecord] = []
    expected_keys = {"logical_key", "relative_path", "sha256", "size"}
    for item in value:
        if type(item) is not dict or set(item) != expected_keys:
            raise _fail("project_update_transaction_intent_invalid")
        record = PrivateBlobRecord(**item)
        expected_path = _blob_record(record.logical_key, b"", root_name=root_name).relative_path
        if record.relative_path != expected_path:
            raise _fail("project_update_transaction_intent_invalid")
        records.append(record)
    if tuple(sorted(record.logical_key for record in records)) != tuple(
        record.logical_key for record in records
    ) or len({record.logical_key for record in records}) != len(records):
        raise _fail("project_update_transaction_intent_invalid")
    return tuple(records)


def runtime_bundle_inventory_sha256(runtime_bundle: Mapping[str, bytes]) -> str:
    if (
        not isinstance(runtime_bundle, Mapping)
        or not runtime_bundle
        or len(runtime_bundle) > MAX_PRIVATE_BLOBS
    ):
        raise _fail("project_update_transaction_intent_invalid")
    records = []
    for key in sorted(runtime_bundle):
        value = runtime_bundle[key]
        if type(value) is not bytes or len(value) > MAX_PRIVATE_BLOB_BYTES:
            raise _fail("project_update_transaction_intent_invalid")
        records.append(_blob_record(key, value, root_name="runtime-bundle").document())
    return sha256_document({"artifacts": records, "schema": RUNTIME_BUNDLE_INVENTORY_SCHEMA})


@dataclass(frozen=True)
class ProjectUpdateReservation:
    transaction_ref: str
    transaction_logical_ref: str
    project_identity_sha256: str
    requested_target_tag: str
    ownership_nonce: str
    runtime_candidate_logical_ref: str
    runtime_candidate_seal_logical_ref: str
    created_at: str

    def __post_init__(self) -> None:
        _transaction_ref(self.transaction_ref)
        expected_logical = _transaction_logical_ref(self.transaction_ref)
        if (
            self.transaction_logical_ref != expected_logical
            or self.runtime_candidate_logical_ref
            != f"{expected_logical}/{RUNTIME_CANDIDATE_NAME}"
            or self.runtime_candidate_seal_logical_ref
            != f"{expected_logical}/{RUNTIME_CANDIDATE_SEAL_NAME}"
        ):
            raise _fail("project_update_transaction_intent_invalid")
        _digest(self.project_identity_sha256, code="project_update_transaction_intent_invalid")
        _target_tag(self.requested_target_tag)
        _token(self.created_at, code="project_update_transaction_intent_invalid")
        if (
            type(self.ownership_nonce) is not str
            or OWNERSHIP_NONCE_RE.fullmatch(self.ownership_nonce) is None
        ):
            raise _fail("project_update_transaction_intent_invalid")

    def document(self) -> dict[str, Any]:
        return {
            "created_at": self.created_at,
            "ownership_nonce": self.ownership_nonce,
            "privacy_flags": dict(PRIVACY_FLAGS),
            "project_identity_sha256": self.project_identity_sha256,
            "requested_target_tag": self.requested_target_tag,
            "runtime_candidate_logical_ref": self.runtime_candidate_logical_ref,
            "runtime_candidate_seal_logical_ref": self.runtime_candidate_seal_logical_ref,
            "schema": MARKER_SCHEMA,
            "state": "reserved",
            "transaction_logical_ref": self.transaction_logical_ref,
            "transaction_ref": self.transaction_ref,
        }

    @property
    def sha256(self) -> str:
        return sha256_document(self.document())

    @classmethod
    def from_document(cls, value: Any) -> "ProjectUpdateReservation":
        expected = {
            "created_at",
            "ownership_nonce",
            "privacy_flags",
            "project_identity_sha256",
            "requested_target_tag",
            "runtime_candidate_logical_ref",
            "runtime_candidate_seal_logical_ref",
            "schema",
            "state",
            "transaction_logical_ref",
            "transaction_ref",
        }
        if (
            type(value) is not dict
            or set(value) != expected
            or value.get("schema") != MARKER_SCHEMA
            or value.get("state") != "reserved"
            or value.get("privacy_flags") != PRIVACY_FLAGS
        ):
            raise _fail("project_update_transaction_intent_invalid")
        return cls(
            transaction_ref=value["transaction_ref"],
            transaction_logical_ref=value["transaction_logical_ref"],
            project_identity_sha256=value["project_identity_sha256"],
            requested_target_tag=value["requested_target_tag"],
            ownership_nonce=value["ownership_nonce"],
            runtime_candidate_logical_ref=value["runtime_candidate_logical_ref"],
            runtime_candidate_seal_logical_ref=value[
                "runtime_candidate_seal_logical_ref"
            ],
            created_at=value["created_at"],
        )


@dataclass(frozen=True)
class RuntimeCandidateTreeInventory:
    recursive_tree_sha256: str
    inventory_count: int
    file_count: int
    total_bytes: int

    def __post_init__(self) -> None:
        _digest(
            self.recursive_tree_sha256,
            code="project_update_transaction_candidate_invalid",
        )
        if (
            type(self.inventory_count) is not int
            or type(self.file_count) is not int
            or type(self.total_bytes) is not int
            or not 0 < self.file_count <= self.inventory_count <= MAX_RUNTIME_CANDIDATE_ENTRIES
            or self.total_bytes < 0
        ):
            raise _fail("project_update_transaction_candidate_invalid")


def _runtime_candidate_tree_inventory(root: Path, *, transaction_root: Path) -> RuntimeCandidateTreeInventory:
    _safe_directory(root, within=transaction_root)
    rows: list[dict[str, Any]] = []
    seen_folded: set[str] = set()
    total_bytes = 0
    file_count = 0

    def visit(directory: Path, prefix: PurePosixPath) -> None:
        nonlocal total_bytes, file_count
        _safe_directory(directory, within=transaction_root)
        try:
            entries = sorted(os.scandir(directory), key=lambda item: (item.name.casefold(), item.name))
        except OSError:
            raise _fail("project_update_transaction_candidate_invalid") from None
        for entry in entries:
            if len(rows) >= MAX_RUNTIME_CANDIDATE_ENTRIES:
                raise _fail("project_update_transaction_candidate_invalid")
            path = Path(entry.path)
            _within(path, root)
            try:
                info = path.lstat()
            except OSError:
                raise _fail("project_update_transaction_candidate_invalid") from None
            if stat.S_ISLNK(info.st_mode) or _is_reparse(info):
                raise _fail("project_update_transaction_path_unsafe")
            relative = (prefix / entry.name).as_posix()
            _logical_path(relative)
            folded = relative.casefold()
            if folded in seen_folded:
                raise _fail("project_update_transaction_candidate_invalid")
            seen_folded.add(folded)
            if stat.S_ISDIR(info.st_mode):
                rows.append({"entry_type": "directory", "relative_path": relative})
                visit(path, prefix / entry.name)
            elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                digest, size, _after = _hash_regular_with_info(
                    path, within=root, maximum=MAX_RUNTIME_CANDIDATE_FILE_BYTES
                )
                rows.append(
                    {
                        "entry_type": "file",
                        "relative_path": relative,
                        "sha256": digest,
                        "size": size,
                    }
                )
                file_count += 1
                total_bytes += size
            else:
                raise _fail("project_update_transaction_path_unsafe")

    visit(root, PurePosixPath())
    binding = {
        "entries": rows,
        "schema": RUNTIME_CANDIDATE_TREE_SCHEMA,
    }
    return RuntimeCandidateTreeInventory(
        recursive_tree_sha256=sha256_document(binding),
        inventory_count=len(rows),
        file_count=file_count,
        total_bytes=total_bytes,
    )


def _runtime_repair_preimage_inventory(
    root: Path,
    *,
    transaction_root: Path,
) -> tuple[str, int, int, set[str], set[str]]:
    """Recompute the provider seal digest for one moved repair preimage."""

    _safe_directory(root, within=transaction_root)
    rows: list[dict[str, Any]] = []
    files: set[str] = set()
    directories: set[str] = {RUNTIME_REPAIR_PREIMAGE_NAME}
    seen_folded: set[str] = set()
    total_bytes = 0

    def visit(directory: Path, prefix: PurePosixPath) -> None:
        nonlocal total_bytes
        _safe_directory(directory, within=transaction_root)
        try:
            entries = sorted(
                os.scandir(directory),
                key=lambda item: (item.name.casefold(), item.name),
            )
        except OSError:
            raise _fail("project_update_transaction_candidate_invalid") from None
        for entry in entries:
            if len(rows) >= MAX_RUNTIME_CANDIDATE_ENTRIES:
                raise _fail("project_update_transaction_candidate_invalid")
            path = Path(entry.path)
            _within(path, root)
            try:
                info = path.lstat()
            except OSError:
                raise _fail("project_update_transaction_candidate_invalid") from None
            if stat.S_ISLNK(info.st_mode) or _is_reparse(info):
                raise _fail("project_update_transaction_path_unsafe")
            relative = (prefix / entry.name).as_posix()
            _logical_path(relative)
            folded = relative.casefold()
            if folded in seen_folded:
                raise _fail("project_update_transaction_candidate_invalid")
            seen_folded.add(folded)
            transaction_relative = f"{RUNTIME_REPAIR_PREIMAGE_NAME}/{relative}"
            if stat.S_ISDIR(info.st_mode):
                rows.append(
                    {
                        "nlink": int(info.st_nlink),
                        "path": relative,
                        "sha256": None,
                        "size_bytes": 0,
                        "type": "directory",
                    }
                )
                directories.add(transaction_relative)
                visit(path, prefix / entry.name)
            elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                digest, size, _after = _hash_regular_with_info(
                    path,
                    within=root,
                    maximum=MAX_RUNTIME_CANDIDATE_FILE_BYTES,
                )
                rows.append(
                    {
                        "nlink": 1,
                        "path": relative,
                        "sha256": digest,
                        "size_bytes": size,
                        "type": "file",
                    }
                )
                files.add(transaction_relative)
                total_bytes += size
            else:
                raise _fail("project_update_transaction_path_unsafe")

    visit(root, PurePosixPath())
    return (
        sha256_bytes(canonical_json_bytes(rows) + b"\n"),
        len(rows),
        total_bytes,
        files,
        directories,
    )


@dataclass(frozen=True)
class RuntimeCandidateBinding:
    logical_ref: str
    seal_logical_ref: str
    recursive_tree_sha256: str
    inventory_count: int
    file_count: int
    inventory_bytes: int
    provider_inventory_sha256: str
    provider_candidate_sha256: str
    seal_sha256: str
    path_identities_sha256: str
    receipt_relative_path: str
    receipt_sha256: str
    postimage_sha256: str
    existing_runtime_reusable: bool
    existing_runtime_repair_required: bool
    existing_runtime_inventory_sha256: str | None
    existing_runtime_inventory_count: int
    existing_runtime_inventory_bytes: int
    runtime_parent_existed_before: bool
    recursive_directory_durability_verified: bool
    seal_parent_durability_required: bool
    marker_free_final_postimage: bool
    # v0.4.15 sealed this same schema before repair-only fields existed.
    # Preserve that exact document shape when reopening so its intent hash and
    # authenticated approval binding remain byte-for-byte authoritative.
    legacy_document_shape: bool = field(
        default=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        _logical_path(self.logical_ref)
        _logical_path(self.seal_logical_ref)
        _logical_path(self.receipt_relative_path)
        for value in (
            self.recursive_tree_sha256,
            self.provider_inventory_sha256,
            self.provider_candidate_sha256,
            self.seal_sha256,
            self.path_identities_sha256,
            self.receipt_sha256,
            self.postimage_sha256,
        ):
            _digest(value, code="project_update_transaction_candidate_invalid")
        if (
            type(self.inventory_count) is not int
            or type(self.file_count) is not int
            or type(self.inventory_bytes) is not int
            or not 0 < self.file_count <= self.inventory_count <= MAX_RUNTIME_CANDIDATE_ENTRIES
            or self.inventory_bytes < 0
            or type(self.existing_runtime_reusable) is not bool
            or type(self.existing_runtime_repair_required) is not bool
            or type(self.legacy_document_shape) is not bool
            or (
                self.legacy_document_shape
                and self.existing_runtime_repair_required
            )
            or (
                self.existing_runtime_reusable
                and self.existing_runtime_repair_required
            )
            or type(self.existing_runtime_inventory_count) is not int
            or self.existing_runtime_inventory_count < 0
            or type(self.existing_runtime_inventory_bytes) is not int
            or self.existing_runtime_inventory_bytes < 0
            or (
                self.existing_runtime_repair_required
                and self.existing_runtime_inventory_sha256 is None
            )
            or (
                not self.existing_runtime_repair_required
                and (
                    self.existing_runtime_inventory_sha256 is not None
                    or self.existing_runtime_inventory_count != 0
                    or self.existing_runtime_inventory_bytes != 0
                )
            )
            or type(self.runtime_parent_existed_before) is not bool
            or self.recursive_directory_durability_verified is not True
            or self.seal_parent_durability_required is not True
            or self.marker_free_final_postimage is not True
        ):
            raise _fail("project_update_transaction_candidate_invalid")
        if self.existing_runtime_inventory_sha256 is not None:
            _digest(
                self.existing_runtime_inventory_sha256,
                code="project_update_transaction_candidate_invalid",
            )

    def document(self) -> dict[str, Any]:
        document = {
            "existing_runtime_reusable": self.existing_runtime_reusable,
            "file_count": self.file_count,
            "inventory_bytes": self.inventory_bytes,
            "inventory_count": self.inventory_count,
            "logical_ref": self.logical_ref,
            "marker_free_final_postimage": self.marker_free_final_postimage,
            "postimage_sha256": self.postimage_sha256,
            "path_identities_sha256": self.path_identities_sha256,
            "provider_candidate_sha256": self.provider_candidate_sha256,
            "provider_inventory_sha256": self.provider_inventory_sha256,
            "receipt_relative_path": self.receipt_relative_path,
            "receipt_sha256": self.receipt_sha256,
            "recursive_tree_sha256": self.recursive_tree_sha256,
            "recursive_directory_durability_verified": (
                self.recursive_directory_durability_verified
            ),
            "runtime_parent_existed_before": self.runtime_parent_existed_before,
            "schema": RUNTIME_CANDIDATE_BINDING_SCHEMA,
            "seal_logical_ref": self.seal_logical_ref,
            "seal_sha256": self.seal_sha256,
            "seal_parent_durability_required": self.seal_parent_durability_required,
        }
        if not self.legacy_document_shape:
            document.update(
                {
                    "existing_runtime_repair_required": (
                        self.existing_runtime_repair_required
                    ),
                    "existing_runtime_inventory_sha256": (
                        self.existing_runtime_inventory_sha256
                    ),
                    "existing_runtime_inventory_count": (
                        self.existing_runtime_inventory_count
                    ),
                    "existing_runtime_inventory_bytes": (
                        self.existing_runtime_inventory_bytes
                    ),
                }
            )
        return document

    @classmethod
    def from_document(cls, value: Any) -> "RuntimeCandidateBinding":
        legacy_expected = {
            "existing_runtime_reusable",
            "file_count",
            "inventory_bytes",
            "inventory_count",
            "logical_ref",
            "marker_free_final_postimage",
            "postimage_sha256",
            "path_identities_sha256",
            "provider_candidate_sha256",
            "provider_inventory_sha256",
            "receipt_relative_path",
            "receipt_sha256",
            "recursive_tree_sha256",
            "recursive_directory_durability_verified",
            "runtime_parent_existed_before",
            "schema",
            "seal_logical_ref",
            "seal_sha256",
            "seal_parent_durability_required",
        }
        current_expected = legacy_expected | {
            "existing_runtime_repair_required",
            "existing_runtime_inventory_sha256",
            "existing_runtime_inventory_count",
            "existing_runtime_inventory_bytes",
        }
        if (
            type(value) is not dict
            or set(value) not in {frozenset(legacy_expected), frozenset(current_expected)}
            or value.get("schema") != RUNTIME_CANDIDATE_BINDING_SCHEMA
        ):
            raise _fail("project_update_transaction_candidate_invalid")
        fields = dict(value)
        fields.pop("schema")
        legacy = set(value) == legacy_expected
        if legacy:
            fields.update(
                {
                    "existing_runtime_repair_required": False,
                    "existing_runtime_inventory_sha256": None,
                    "existing_runtime_inventory_count": 0,
                    "existing_runtime_inventory_bytes": 0,
                    "legacy_document_shape": True,
                }
            )
        return cls(**fields)


@dataclass(frozen=True)
class ProjectUpdateIntent:
    transaction_ref: str
    transaction_logical_ref: str
    project_identity_sha256: str
    requested_target_tag: str
    bindings: ProjectUpdateBindings
    components: tuple[ProjectUpdateComponent, ...]
    logical_targets: tuple[str, ...]
    preimages: tuple[PrivateBlobRecord, ...]
    private_bindings: tuple[PrivateBlobRecord, ...]
    runtime_candidate: RuntimeCandidateBinding
    ownership_nonce: str
    reservation_sha256: str
    created_at: str
    static_receipt_domain_plan_sha256: str
    static_receipt_domain_target_binding_sha256: str

    def __post_init__(self) -> None:
        _transaction_ref(self.transaction_ref)
        if self.transaction_logical_ref != _transaction_logical_ref(self.transaction_ref):
            raise _fail("project_update_transaction_intent_invalid")
        _digest(self.project_identity_sha256, code="project_update_transaction_intent_invalid")
        _digest(self.reservation_sha256, code="project_update_transaction_intent_invalid")
        _digest(
            self.static_receipt_domain_plan_sha256,
            code="project_update_transaction_intent_invalid",
        )
        _digest(
            self.static_receipt_domain_target_binding_sha256,
            code="project_update_transaction_intent_invalid",
        )
        _target_tag(self.requested_target_tag)
        _token(self.created_at, code="project_update_transaction_intent_invalid")
        if (
            type(self.ownership_nonce) is not str
            or OWNERSHIP_NONCE_RE.fullmatch(self.ownership_nonce) is None
        ):
            raise _fail("project_update_transaction_intent_invalid")
        if not self.components or len(self.components) > MAX_COMPONENTS:
            raise _fail("project_update_transaction_intent_invalid")
        if tuple(component.sequence for component in self.components) != tuple(
            range(1, len(self.components) + 1)
        ):
            raise _fail("project_update_transaction_intent_invalid")
        if len({component.component_ref for component in self.components}) != len(self.components):
            raise _fail("project_update_transaction_intent_invalid")
        role_positions = [COMPONENT_ROLES.index(component.role) for component in self.components]
        if role_positions != sorted(role_positions):
            raise _fail("project_update_transaction_intent_invalid")
        required_single = {"source", "runtime", "launcher", "receipt", "active_pin"}
        for role in required_single:
            if sum(component.role == role for component in self.components) != 1:
                raise _fail("project_update_transaction_intent_invalid")
        if self.components[-1].role != "active_pin":
            raise _fail("project_update_transaction_intent_invalid")
        expected_targets = tuple(sorted(component.logical_target for component in self.components))
        if self.logical_targets != expected_targets or len(set(expected_targets)) != len(expected_targets):
            raise _fail("project_update_transaction_intent_invalid")
        preimage_by_key = {record.logical_key: record for record in self.preimages}
        expected_preimage_keys: set[str] = set()
        runtime_tree_preimages = 0
        for component in self.components:
            if component.pre_sha256 == ABSENT_COMPONENT_SHA256:
                if component.preimage_key is not None:
                    raise _fail("project_update_transaction_intent_invalid")
            else:
                runtime_tree_preimage = (
                    component.role == "runtime"
                    and self.runtime_candidate.existing_runtime_repair_required
                    and not self.runtime_candidate.existing_runtime_reusable
                    and component.logical_target
                    == f"{RUNTIME_PARENT_LOGICAL}/{self.requested_target_tag}"
                    and component.pre_sha256
                    == self.runtime_candidate.existing_runtime_inventory_sha256
                    and component.preserve_old_value is True
                    and component.preimage_key is None
                )
                if runtime_tree_preimage:
                    runtime_tree_preimages += 1
                    continue
                if component.preimage_key is None:
                    raise _fail("project_update_transaction_intent_invalid")
                expected_preimage_keys.add(component.preimage_key)
                record = preimage_by_key.get(component.preimage_key)
                if record is None or record.sha256 != component.pre_sha256:
                    raise _fail("project_update_transaction_intent_invalid")
        if runtime_tree_preimages != int(
            self.runtime_candidate.existing_runtime_repair_required
        ):
            raise _fail("project_update_transaction_intent_invalid")
        if set(preimage_by_key) != expected_preimage_keys:
            raise _fail("project_update_transaction_intent_invalid")
        private_keys = tuple(record.logical_key for record in self.private_bindings)
        if (
            not private_keys
            or private_keys != tuple(sorted(set(private_keys)))
            or "git-runner-binding" not in private_keys
            or "static-receipt-postimage" not in private_keys
            or "runtime-candidate-path-identities" not in private_keys
        ):
            raise _fail("project_update_transaction_intent_invalid")
        static_receipt_records = [
            record
            for record in self.private_bindings
            if record.logical_key == "static-receipt-postimage"
        ]
        receipt_components = [
            component for component in self.components if component.role == "receipt"
        ]
        runtime_components = [
            component for component in self.components if component.role == "runtime"
        ]
        if (
            len(static_receipt_records) != 1
            or len(receipt_components) != 1
            or static_receipt_records[0].sha256 != receipt_components[0].post_sha256
            or len(runtime_components) != 1
            or self.runtime_candidate.postimage_sha256
            != runtime_components[0].post_sha256
        ):
            raise _fail("project_update_transaction_intent_invalid")
        if (
            self.runtime_candidate.logical_ref
            != f"{self.transaction_logical_ref}/{RUNTIME_CANDIDATE_NAME}"
            or self.runtime_candidate.seal_logical_ref
            != f"{self.transaction_logical_ref}/{RUNTIME_CANDIDATE_SEAL_NAME}"
        ):
            raise _fail("project_update_transaction_candidate_invalid")

    def document(self) -> dict[str, Any]:
        return {
            "binding_digests": self.bindings.document(),
            "components": [component.document() for component in self.components],
            "created_at": self.created_at,
            "logical_targets": list(self.logical_targets),
            "ownership_nonce": self.ownership_nonce,
            "preimages": [record.document() for record in self.preimages],
            "privacy_flags": dict(PRIVACY_FLAGS),
            "private_bindings": [record.document() for record in self.private_bindings],
            "project_identity_sha256": self.project_identity_sha256,
            "requested_target_tag": self.requested_target_tag,
            "reservation_sha256": self.reservation_sha256,
            "runtime_candidate": self.runtime_candidate.document(),
            "schema": INTENT_SCHEMA,
            "static_receipt_domain_plan_sha256": (
                self.static_receipt_domain_plan_sha256
            ),
            "static_receipt_domain_target_binding_sha256": (
                self.static_receipt_domain_target_binding_sha256
            ),
            "transaction_logical_ref": self.transaction_logical_ref,
            "transaction_ref": self.transaction_ref,
        }

    @property
    def sha256(self) -> str:
        return sha256_document(self.document())

    @classmethod
    def from_document(cls, value: Any) -> "ProjectUpdateIntent":
        expected = {
            "binding_digests",
            "components",
            "created_at",
            "logical_targets",
            "ownership_nonce",
            "preimages",
            "privacy_flags",
            "private_bindings",
            "project_identity_sha256",
            "requested_target_tag",
            "reservation_sha256",
            "runtime_candidate",
            "schema",
            "static_receipt_domain_plan_sha256",
            "static_receipt_domain_target_binding_sha256",
            "transaction_logical_ref",
            "transaction_ref",
        }
        if (
            type(value) is not dict
            or set(value) != expected
            or value.get("schema") != INTENT_SCHEMA
            or value.get("privacy_flags") != PRIVACY_FLAGS
            or type(value.get("components")) is not list
            or type(value.get("logical_targets")) is not list
        ):
            raise _fail("project_update_transaction_intent_invalid")
        component_keys = {
            "component_ref",
            "logical_target",
            "post_sha256",
            "pre_sha256",
            "preimage_key",
            "preserve_old_value",
            "role",
            "sequence",
        }
        components: list[ProjectUpdateComponent] = []
        for item in value["components"]:
            if type(item) is not dict or set(item) != component_keys:
                raise _fail("project_update_transaction_intent_invalid")
            components.append(ProjectUpdateComponent(**item))
        return cls(
            transaction_ref=value["transaction_ref"],
            transaction_logical_ref=value["transaction_logical_ref"],
            project_identity_sha256=value["project_identity_sha256"],
            requested_target_tag=value["requested_target_tag"],
            bindings=ProjectUpdateBindings.from_document(value["binding_digests"]),
            components=tuple(components),
            logical_targets=tuple(value["logical_targets"]),
            preimages=_records_from_document(value["preimages"], root_name="preimages"),
            private_bindings=_records_from_document(
                value["private_bindings"], root_name=PRIVATE_BINDINGS_NAME
            ),
            runtime_candidate=RuntimeCandidateBinding.from_document(
                value["runtime_candidate"]
            ),
            ownership_nonce=value["ownership_nonce"],
            reservation_sha256=value["reservation_sha256"],
            created_at=value["created_at"],
            static_receipt_domain_plan_sha256=value[
                "static_receipt_domain_plan_sha256"
            ],
            static_receipt_domain_target_binding_sha256=value[
                "static_receipt_domain_target_binding_sha256"
            ],
        )


@dataclass(frozen=True)
class LockObservation:
    pid: int | None = None
    process_start: str | None = None

    def document(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if self.pid is not None:
            if type(self.pid) is not int or self.pid <= 0:
                raise _fail("project_update_transaction_lock_invalid")
            result["pid"] = self.pid
        if self.process_start is not None:
            result["process_start"] = _token(
                self.process_start, code="project_update_transaction_lock_invalid"
            )
        return result


def _reservation_from_intent(intent: ProjectUpdateIntent) -> ProjectUpdateReservation:
    reservation = ProjectUpdateReservation(
        transaction_ref=intent.transaction_ref,
        transaction_logical_ref=intent.transaction_logical_ref,
        project_identity_sha256=intent.project_identity_sha256,
        requested_target_tag=intent.requested_target_tag,
        ownership_nonce=intent.ownership_nonce,
        runtime_candidate_logical_ref=intent.runtime_candidate.logical_ref,
        runtime_candidate_seal_logical_ref=intent.runtime_candidate.seal_logical_ref,
        created_at=intent.created_at,
    )
    if reservation.sha256 != intent.reservation_sha256:
        raise _fail("project_update_transaction_intent_invalid")
    return reservation


def build_lock_document(
    subject: ProjectUpdateReservation | ProjectUpdateIntent,
    *,
    observation: LockObservation | None = None,
) -> dict[str, Any]:
    reservation = (
        _reservation_from_intent(subject)
        if isinstance(subject, ProjectUpdateIntent)
        else subject
    )
    if not isinstance(reservation, ProjectUpdateReservation):
        raise _fail("project_update_transaction_lock_invalid")
    result: dict[str, Any] = {
        "ownership_nonce": reservation.ownership_nonce,
        "project_identity_sha256": reservation.project_identity_sha256,
        "reservation_sha256": reservation.sha256,
        "schema": LOCK_SCHEMA,
        "transaction_logical_ref": reservation.transaction_logical_ref,
        "transaction_ref": reservation.transaction_ref,
    }
    if observation is not None and observation.document():
        result["observations"] = observation.document()
    return result


def _validate_lock_document(
    value: Any,
    *,
    reservation: ProjectUpdateReservation | None = None,
    intent: ProjectUpdateIntent | None = None,
) -> dict[str, Any]:
    required = {
        "ownership_nonce",
        "project_identity_sha256",
        "reservation_sha256",
        "schema",
        "transaction_logical_ref",
        "transaction_ref",
    }
    if (
        type(value) is not dict
        or set(value) not in (required, required | {"observations"})
        or value.get("schema") != LOCK_SCHEMA
    ):
        raise _fail("project_update_transaction_lock_invalid")
    _transaction_ref(value.get("transaction_ref"))
    _digest(value.get("reservation_sha256"), code="project_update_transaction_lock_invalid")
    _digest(
        value.get("project_identity_sha256"),
        code="project_update_transaction_lock_invalid",
    )
    if (
        value.get("transaction_logical_ref")
        != _transaction_logical_ref(value["transaction_ref"])
        or type(value.get("ownership_nonce")) is not str
        or OWNERSHIP_NONCE_RE.fullmatch(value["ownership_nonce"]) is None
    ):
        raise _fail("project_update_transaction_lock_invalid")
    observations = value.get("observations")
    observation: LockObservation | None = None
    if observations is not None:
        if (
            type(observations) is not dict
            or not observations
            or not set(observations).issubset({"pid", "process_start"})
        ):
            raise _fail("project_update_transaction_lock_invalid")
        observation = LockObservation(
            pid=observations.get("pid"),
            process_start=observations.get("process_start"),
        )
        observation.document()
    if intent is not None:
        if reservation is not None:
            raise _fail("project_update_transaction_lock_invalid")
        reservation = _reservation_from_intent(intent)
    if reservation is not None:
        expected = build_lock_document(reservation, observation=observation)
        if not hmac.compare_digest(canonical_json_bytes(value), canonical_json_bytes(expected)):
            raise _fail("project_update_transaction_lock_invalid")
    return value


def lock_document_bytes(value: Mapping[str, Any]) -> bytes:
    return _document_bytes(_validate_lock_document(dict(value)))


def _parse_lock_bytes(
    raw: bytes,
    *,
    reservation: ProjectUpdateReservation | None = None,
    intent: ProjectUpdateIntent | None = None,
) -> dict[str, Any]:
    return _validate_lock_document(
        _parse_document(raw, code="project_update_transaction_lock_invalid"),
        reservation=reservation,
        intent=intent,
    )


def active_transaction_ref_from_lock_read_only(
    project_root: Path | str,
) -> str:
    """Read the sole live lock's opaque transaction ref without creating state.

    This is only a locator for the subsequent fully authenticated transaction
    reopen.  The lock schema, canonical bytes, real path chain, and bounded
    regular-file read are all verified here; the pointed transaction then
    revalidates its reservation, sealed intent, backlink, journal, and live
    components before any resume authority exists.
    """

    project = _absolute(project_root)
    _safe_existing_chain(project, directory=True)
    lock_path = project / PurePosixPath(PROJECT_UPDATE_LOCK_LOGICAL)
    _within(lock_path, project)
    raw = _read_regular(
        lock_path,
        within=project,
        maximum=MAX_DOCUMENT_BYTES + 1,
    )
    document = _parse_lock_bytes(raw)
    return _transaction_ref(document["transaction_ref"])


def active_transaction_ref_for_resume_read_only(
    project_root: Path | str,
) -> str:
    """Locate the sole exact resumable transaction without operator input.

    A present lock is always authoritative and is parsed by the stricter lock
    reader above.  The fallback exists only for a process loss after the exact
    lock unlink: it accepts one sealed, backlinked, exact-journal transaction
    whose verified state has already reached the unlock tail.  It never
    creates state and never guesses among multiple candidates.
    """

    project = _absolute(project_root)
    _safe_existing_chain(project, directory=True)
    lock_path = project / PurePosixPath(PROJECT_UPDATE_LOCK_LOGICAL)
    _within(lock_path, project)
    if os.path.lexists(lock_path):
        return active_transaction_ref_from_lock_read_only(project)

    candidates: list[str] = []
    for orphan in inspect_prelock_orphans(project):
        if orphan.classification == "reserved_abort_receipt_pending":
            candidates.append(orphan.transaction_ref)
            continue
        if orphan.classification != "not_prelock_orphan":
            continue
        try:
            transaction = ProjectUpdateTransaction.open(
                project,
                orphan.transaction_ref,
                verify_candidate_content=False,
            )
            inspection = transaction.inspect(
                verify_candidate_content=False
            )
        except ProjectUpdateTransactionError:
            continue
        prefix = inspection.journal.verified_prefix
        last_phase = prefix[-1].phase if prefix else None
        if (
            inspection.lock_backlinked
            and inspection.journal.state == "exact"
            and last_phase in {"ready_to_unlock", "lock_released", "completed"}
        ):
            candidates.append(orphan.transaction_ref)

    # The lock was absent at the scan's linearization start, but a new
    # transaction may have acquired it while the bounded transaction-root
    # inspection was in flight.  A live lock is always authoritative: parse it
    # again after the scan instead of returning a now-stale lockless tail.
    if os.path.lexists(lock_path):
        return active_transaction_ref_from_lock_read_only(project)

    if not candidates:
        raise _fail("project_update_transaction_not_found")
    if len(candidates) != 1:
        raise _fail("project_update_transaction_invalid")
    return candidates[0]


def inspect_terminal_cleanup_artifacts_for_resume_read_only(
    project_root: Path | str,
) -> TerminalCleanupArtifactState:
    """Detect untrusted terminal-cleanup residue without opening its content.

    This is deliberately not an outcome or cleanup-authority inspector.  It
    only distinguishes ordinary locator absence from a cleanup-shaped name,
    an unsafe/incomplete bounded scan, or a live lock published while that
    scan was in flight.  A caller may use ``observed_or_scan_incomplete`` only
    to report that the terminal outcome is unknown; it authorizes no retry,
    cleanup, approval, or domain write.

    Every entry counts toward a fixed cap and is consumed with streaming
    ``scandir`` iteration.  Any name beginning with either cleanup prefix is
    enough to produce the conservative state, regardless of suffix, file
    type, target, bytes, or cardinality.  Thus malformed names, symlinks,
    reparse points, and other special entries are never trusted as evidence.
    """

    project = _absolute(project_root)
    _safe_existing_chain(project, directory=True)
    lock_path = project / PurePosixPath(PROJECT_UPDATE_LOCK_LOGICAL)
    _within(lock_path, project)

    def live_lock_changed() -> bool:
        if not os.path.lexists(lock_path):
            return False
        # Parse the newly observed lock strictly, while deliberately
        # discarding its private transaction reference.
        active_transaction_ref_from_lock_read_only(project)
        return True

    if live_lock_changed():
        return "active_lock_changed"

    parent = project / PurePosixPath(TRANSACTION_ROOT_LOGICAL)
    _within(parent, project)
    state: TerminalCleanupArtifactState = "absent"
    if os.path.lexists(parent):
        try:
            _safe_existing_chain(parent, directory=True)
            seen = 0
            with os.scandir(parent) as entries:
                for entry in entries:
                    seen += 1
                    if seen > MAX_TERMINAL_CLEANUP_SCAN_ENTRIES:
                        state = "observed_or_scan_incomplete"
                        break
                    name = entry.name
                    if name.startswith(".cleanup_") or name.startswith(
                        ".cleanup-proof_"
                    ):
                        state = "observed_or_scan_incomplete"
                        break
        except (OSError, ProjectUpdateTransactionError):
            # Failure to finish a safe bounded scan cannot prove absence.
            state = "observed_or_scan_incomplete"

    # A lock published during the scan is authoritative.  Never return a
    # stale cleanup-unknown or ordinary-absence classification for it.
    if live_lock_changed():
        return "active_lock_changed"
    return state


def _identity_document(info: os.stat_result) -> dict[str, int]:
    return {
        "device": int(info.st_dev),
        "inode": int(info.st_ino),
        "modified_ns": int(info.st_mtime_ns),
        "size": int(info.st_size),
    }


def _stable_path_identity(info: os.stat_result) -> tuple[int, int, int, int]:
    """Return the bounded identity fields used across a read-only scan."""

    return (
        int(info.st_dev),
        int(info.st_ino),
        int(info.st_mtime_ns),
        int(info.st_size),
    )


def _cleanup_directory_identity(
    info: os.stat_result,
) -> tuple[int, int, int | None]:
    """Bind a directory generation, not only a potentially reusable inode."""

    raw_birthtime = getattr(info, "st_birthtime_ns", None)
    birthtime_ns = (
        int(raw_birthtime)
        if type(raw_birthtime) is int and raw_birthtime > 0
        else None
    )
    return int(info.st_dev), int(info.st_ino), birthtime_ns


@dataclass(frozen=True)
class _BoundDirectoryForMove:
    """One exact directory kept stable across a namespace mutation."""

    path: Path
    identity: tuple[int, int]
    descriptor: int | None


@dataclass(frozen=True)
class _CleanupFileSnapshot:
    size: int
    sha256: str
    device: int
    inode: int
    mtime_ns: int


@dataclass(frozen=True)
class _CleanupDirectorySnapshot:
    device: int
    inode: int
    birthtime_ns: int | None


def _cleanup_plan_name_for_document(value: Mapping[str, Any]) -> str:
    """Return the sole canonical filename for one supported plan schema."""

    schema = value.get("schema")
    if schema == CLEANUP_PLAN_SCHEMA:
        return CLEANUP_PLAN_NAME
    if schema == LEGACY_CLEANUP_PLAN_SCHEMA:
        return LEGACY_CLEANUP_PLAN_NAME
    raise _fail("project_update_transaction_cleanup_refused")


def _existing_cleanup_plan_path(root: Path) -> Path | None:
    """Prefer the identity-bound v0.4.16 plan over a retained legacy plan."""

    current = root / CLEANUP_PLAN_NAME
    legacy = root / LEGACY_CLEANUP_PLAN_NAME
    if os.path.lexists(current):
        return current
    if os.path.lexists(legacy):
        return legacy
    return None


@contextmanager
def _bound_directory_for_move(path: Path) -> Iterator[_BoundDirectoryForMove]:
    """Bind a complete directory chain without following a racing replacement."""

    absolute = _absolute(path)
    expected = _safe_directory(absolute, within=absolute)
    expected_identity = (int(expected.st_dev), int(expected.st_ino))
    if os.name != "nt":
        flags = os.O_RDONLY
        flags |= getattr(os, "O_DIRECTORY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptors: list[int] = []
        try:
            anchor = Path(absolute.anchor)
            descriptor = os.open(anchor, flags)
            descriptors.append(descriptor)
            opened = os.fstat(descriptor)
            if not stat.S_ISDIR(opened.st_mode):
                raise OSError("project update move parent unsafe")
            current = anchor
            for part in absolute.parts[1:]:
                named = os.stat(
                    part,
                    dir_fd=descriptor,
                    follow_symlinks=False,
                )
                if stat.S_ISLNK(named.st_mode) or not stat.S_ISDIR(named.st_mode):
                    raise OSError("project update move parent unsafe")
                child = os.open(part, flags, dir_fd=descriptor)
                child_info = os.fstat(child)
                if (
                    not stat.S_ISDIR(child_info.st_mode)
                    or (int(child_info.st_dev), int(child_info.st_ino))
                    != (int(named.st_dev), int(named.st_ino))
                ):
                    os.close(child)
                    raise OSError("project update move parent changed")
                descriptors.append(child)
                descriptor = child
                current = current / part
            final = os.fstat(descriptor)
            if (
                current != absolute
                or (int(final.st_dev), int(final.st_ino))
                != expected_identity
            ):
                raise OSError("project update move parent changed")
            yield _BoundDirectoryForMove(
                path=absolute,
                identity=expected_identity,
                descriptor=descriptor,
            )
            final_after = os.fstat(descriptor)
            if (int(final_after.st_dev), int(final_after.st_ino)) != expected_identity:
                raise OSError("project update move parent changed")
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)
        return

    import ctypes
    from ctypes import wintypes

    class ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", wintypes.FILETIME),
            ("ftLastAccessTime", wintypes.FILETIME),
            ("ftLastWriteTime", wintypes.FILETIME),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

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
    get_information = kernel32.GetFileInformationByHandle
    get_information.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ByHandleFileInformation),
    ]
    get_information.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    file_list_directory = 0x00000001
    file_share_read = 0x00000001
    file_share_write = 0x00000002
    open_existing = 3
    file_flag_open_reparse_point = 0x00200000
    file_flag_backup_semantics = 0x02000000
    file_attribute_directory = 0x00000010
    file_attribute_reparse_point = 0x00000400
    invalid_handle = wintypes.HANDLE(-1).value
    handles: list[Any] = []

    def query(handle: Any) -> ByHandleFileInformation:
        information = ByHandleFileInformation()
        if not get_information(handle, ctypes.byref(information)):
            raise ctypes.WinError(ctypes.get_last_error())
        return information

    try:
        for member in _chain(absolute):
            named = os.lstat(member)
            if (
                stat.S_ISLNK(named.st_mode)
                or _is_reparse(named)
                or not stat.S_ISDIR(named.st_mode)
            ):
                raise OSError("project update move parent unsafe")
            handle = create_file(
                str(member),
                file_list_directory,
                file_share_read | file_share_write,
                None,
                open_existing,
                file_flag_open_reparse_point | file_flag_backup_semantics,
                None,
            )
            if handle == invalid_handle:
                raise ctypes.WinError(ctypes.get_last_error())
            handles.append(handle)
            information = query(handle)
            file_index = (
                int(information.nFileIndexHigh) << 32
            ) | int(information.nFileIndexLow)
            if (
                not information.dwFileAttributes & file_attribute_directory
                or information.dwFileAttributes & file_attribute_reparse_point
                or (int(named.st_ino) and file_index != int(named.st_ino))
            ):
                raise OSError("project update move parent changed")
        final_information = query(handles[-1])
        final_index = (
            int(final_information.nFileIndexHigh) << 32
        ) | int(final_information.nFileIndexLow)
        if int(expected.st_ino) and final_index != int(expected.st_ino):
            raise OSError("project update move parent changed")
        yield _BoundDirectoryForMove(
            path=absolute,
            identity=expected_identity,
            descriptor=None,
        )
        after = query(handles[-1])
        after_index = (int(after.nFileIndexHigh) << 32) | int(after.nFileIndexLow)
        if int(expected.st_ino) and after_index != int(expected.st_ino):
            raise OSError("project update move parent changed")
    finally:
        close_error: OSError | None = None
        for handle in reversed(handles):
            if not close_handle(handle) and close_error is None:
                close_error = ctypes.WinError(ctypes.get_last_error())
        if close_error is not None:
            raise close_error


def _atomic_move_entry_no_replace(source: Path, destination: Path) -> None:
    """Move one entry no-replace while both complete parent chains stay bound."""

    import ctypes

    source = _absolute(source)
    destination = _absolute(destination)
    if (
        source == source.parent
        or destination == destination.parent
        or source.name in {"", ".", ".."}
        or destination.name in {"", ".", ".."}
    ):
        raise _fail("project_update_transaction_path_unsafe")
    source_parent_before = _safe_directory(source.parent, within=source.parent)
    destination_parent_before = _safe_directory(
        destination.parent,
        within=destination.parent,
    )
    same_parent = os.path.normcase(str(source.parent)) == os.path.normcase(
        str(destination.parent)
    )
    with ExitStack() as stack:
        source_binding = stack.enter_context(
            _bound_directory_for_move(source.parent)
        )
        destination_binding = (
            source_binding
            if same_parent
            else stack.enter_context(
                _bound_directory_for_move(destination.parent)
            )
        )
        if (
            source_binding.identity
            != (int(source_parent_before.st_dev), int(source_parent_before.st_ino))
            or destination_binding.identity
            != (
                int(destination_parent_before.st_dev),
                int(destination_parent_before.st_ino),
            )
            or source_binding.identity[0] != destination_binding.identity[0]
        ):
            raise _fail("project_update_transaction_path_unsafe")
        if os.name == "nt":
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            move = kernel32.MoveFileExW
            move.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
            move.restype = ctypes.c_int
            # MOVEFILE_WRITE_THROUGH only. REPLACE_EXISTING and COPY_ALLOWED
            # are deliberately omitted: a concurrent destination is refusal.
            if not move(str(source), str(destination), 0x00000008):
                raise OSError(
                    ctypes.get_last_error(),
                    "atomic no-replace move failed",
                )
            if not _fsync_directory(destination.parent).durable:
                raise OSError("atomic no-replace destination flush failed")
            if (
                not same_parent
                and not _fsync_directory(source.parent).durable
            ):
                raise OSError("atomic no-replace source flush failed")
            return
        source_descriptor = source_binding.descriptor
        destination_descriptor = destination_binding.descriptor
        if not isinstance(source_descriptor, int) or not isinstance(
            destination_descriptor, int
        ):
            raise OSError("atomic no-replace parent binding missing")
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = getattr(libc, "renameat2", None)
        if renameat2 is None:
            raise OSError("atomic no-replace entry move unsupported")
        renameat2.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameat2.restype = ctypes.c_int
        if renameat2(
            source_descriptor,
            os.fsencode(source.name),
            destination_descriptor,
            os.fsencode(destination.name),
            1,  # RENAME_NOREPLACE
        ) != 0:
            error_number = ctypes.get_errno()
            raise OSError(
                error_number,
                "atomic no-replace move failed",
            )
        os.fsync(destination_descriptor)
        if not same_parent:
            os.fsync(source_descriptor)


def _atomic_move_directory_no_replace(source: Path, destination: Path) -> None:
    """Atomically move one directory while preserving the historical seam."""

    if source.parent != destination.parent:
        raise _fail("project_update_transaction_path_unsafe")
    _atomic_move_entry_no_replace(source, destination)


def _atomic_move_file_no_replace(source: Path, destination: Path) -> None:
    """Atomically move one file only while the destination is absent."""

    _atomic_move_entry_no_replace(source, destination)


def _cleanup_bound_directory_context(project: Path, path: Path) -> Any:
    """Load the existing full-chain binding lazily to avoid an import cycle."""

    from .archive_services import _activity_group_bound_directory_chain

    project = _absolute(project)
    path = _absolute(path)
    try:
        relative = path.relative_to(project)
    except ValueError:
        raise _fail("project_update_transaction_path_unsafe") from None
    canonical_project = project.resolve()
    canonical_path = canonical_project.joinpath(*relative.parts)
    return _activity_group_bound_directory_chain(
        canonical_project,
        canonical_path,
    )


def _read_cleanup_linked_regular(
    project: Path,
    path: Path,
    *,
    maximum: int,
) -> tuple[bytes, os.stat_result]:
    """Read one one-or-two-link cleanup file through a fully bound parent."""

    from .archive_services import _hold_activity_group_evidence_file

    project = _absolute(project)
    path = _absolute(path)
    try:
        relative = path.relative_to(project)
    except ValueError:
        raise _fail("project_update_transaction_cleanup_refused") from None
    canonical_project = project.resolve()
    canonical_path = canonical_project.joinpath(*relative.parts)
    with _hold_activity_group_evidence_file(
        canonical_project,
        canonical_path,
        max_bytes=maximum,
    ) as held:
        raw = held.get("raw")
        identity = held.get("identity")
        if not isinstance(raw, bytes) or not isinstance(identity, tuple):
            raise _fail("project_update_transaction_cleanup_refused")
        if os.name == "nt":
            windows_handle = held.get("windows_handle")
            if windows_handle is None:
                raise _fail("project_update_transaction_cleanup_refused")
            from .archive_services import (
                _windows_assert_default_backup_stream_only,
            )

            try:
                _windows_assert_default_backup_stream_only(
                    windows_handle,
                    expected_size=len(raw),
                    error_prefix="project_update_transaction_cleanup",
                )
            except OSError:
                raise _fail(
                    "project_update_transaction_cleanup_refused"
                ) from None
        try:
            named = os.lstat(canonical_path)
        except OSError:
            raise _fail("project_update_transaction_cleanup_refused") from None
        if (
            stat.S_ISLNK(named.st_mode)
            or _is_reparse(named)
            or not stat.S_ISREG(named.st_mode)
            or int(named.st_nlink) not in {1, 2}
            or (int(named.st_dev), int(named.st_ino))
            != (int(identity[0]), int(identity[1]))
            or int(named.st_size) != len(raw)
        ):
            raise _fail("project_update_transaction_cleanup_refused")
        return raw, named


def _delete_exact_cleanup_file(
    project: Path,
    path: Path,
    snapshot: _CleanupFileSnapshot,
) -> None:
    """Delete one transiently identity-bound file through the hardened primitive."""

    from .legacy_cleanup_bound_delete import _delete_exact_approved_file

    _delete_exact_approved_file(
        project,
        path,
        {
            "type": "file",
            "identity": {
                "device": snapshot.device,
                "inode": snapshot.inode,
            },
            "size": snapshot.size,
            "mtime_ns": snapshot.mtime_ns,
            "sha256": snapshot.sha256.removeprefix("sha256:"),
        },
    )


def _delete_exact_cleanup_directory(
    project: Path,
    path: Path,
    snapshot: _CleanupDirectorySnapshot,
) -> None:
    """Delete one exact empty directory without a pathname-only rmdir race."""

    current = _safe_directory(path, within=project)
    if _cleanup_directory_identity(current) != (
        snapshot.device,
        snapshot.inode,
        snapshot.birthtime_ns,
    ):
        raise _fail("project_update_transaction_cleanup_refused")

    from .legacy_cleanup_bound_delete import (
        _delete_exact_approved_empty_directory,
    )

    _delete_exact_approved_empty_directory(
        project,
        path,
        {
            "type": "directory",
            "identity": {
                "birthtime_ns": snapshot.birthtime_ns,
                "device": snapshot.device,
                "inode": snapshot.inode,
            },
        },
    )


def _unlink_exact_cleanup_plan_duplicate_windows(
    project: Path,
    source: Path,
    proof: Path,
    *,
    expected_raw: bytes,
    expected_identity: tuple[int, int],
) -> None:
    """Remove only the source hardlink from a proven rename-crash duplicate."""

    if os.name != "nt":
        raise OSError("exact cleanup duplicate unlink unsupported")
    from .archive_services import _windows_mark_handle_posix_delete
    from .legacy_cleanup_bound_delete import (
        _ApprovedFile,
        _reject_windows_alternate_streams,
        _windows_close,
        _windows_digest_handle,
        _windows_open,
    )

    try:
        source_info = os.lstat(source)
        proof_info = os.lstat(proof)
    except OSError:
        raise OSError("exact cleanup duplicate changed") from None
    expected_digest = hashlib.sha256(expected_raw).hexdigest()
    if (
        stat.S_ISLNK(source_info.st_mode)
        or stat.S_ISLNK(proof_info.st_mode)
        or _is_reparse(source_info)
        or _is_reparse(proof_info)
        or not stat.S_ISREG(source_info.st_mode)
        or not stat.S_ISREG(proof_info.st_mode)
        or int(source_info.st_nlink) != 2
        or int(proof_info.st_nlink) != 2
        or (int(source_info.st_dev), int(source_info.st_ino))
        != expected_identity
        or (int(proof_info.st_dev), int(proof_info.st_ino))
        != expected_identity
        or int(source_info.st_size) != len(expected_raw)
        or int(proof_info.st_size) != len(expected_raw)
    ):
        raise OSError("exact cleanup duplicate changed")
    approved = _ApprovedFile(
        device=int(source_info.st_dev),
        inode=int(source_info.st_ino),
        size=len(expected_raw),
        mtime_ns=int(source_info.st_mtime_ns),
        sha256=expected_digest,
    )
    handle = _windows_open(source, directory=False)
    failure: BaseException | None = None
    committed = False
    try:
        _reject_windows_alternate_streams(handle, directory=False)
        _windows_digest_handle(handle, approved, expected_link_count=2)
        current_proof_raw, current_proof_info = _read_cleanup_linked_regular(
            project,
            proof,
            maximum=MAX_DOCUMENT_BYTES + 1,
        )
        if (
            not hmac.compare_digest(current_proof_raw, expected_raw)
            or (int(current_proof_info.st_dev), int(current_proof_info.st_ino))
            != expected_identity
            or int(current_proof_info.st_nlink) != 2
        ):
            raise OSError("exact cleanup duplicate changed")
        _windows_mark_handle_posix_delete(
            handle,
            error_prefix="project_update_cleanup",
        )
        _windows_digest_handle(handle, approved, expected_link_count=1)
        _reject_windows_alternate_streams(handle, directory=False)
        final_proof_raw, final_proof_info = _read_cleanup_linked_regular(
            project,
            proof,
            maximum=MAX_DOCUMENT_BYTES + 1,
        )
        if (
            not hmac.compare_digest(final_proof_raw, expected_raw)
            or (int(final_proof_info.st_dev), int(final_proof_info.st_ino))
            != expected_identity
            or int(final_proof_info.st_nlink) != 1
        ):
            raise OSError("exact cleanup duplicate unlink unproved")
        committed = True
    except BaseException as error:
        failure = error
    try:
        _windows_close(handle)
    except BaseException as error:
        failure = error
    if failure is not None:
        raise OSError("exact cleanup duplicate unlink failed") from failure
    if not committed:
        raise OSError("exact cleanup duplicate unlink unproved")
    # FileDispositionInfoEx removes the namespace entry only after the held
    # source handle closes on some supported Windows filesystems.  Attribute
    # the reconciliation only after that close and one fresh exact proof read.
    final_proof_raw, final_proof_info = _read_cleanup_linked_regular(
        project,
        proof,
        maximum=MAX_DOCUMENT_BYTES + 1,
    )
    if (
        os.path.lexists(source)
        or not hmac.compare_digest(final_proof_raw, expected_raw)
        or (int(final_proof_info.st_dev), int(final_proof_info.st_ino))
        != expected_identity
        or int(final_proof_info.st_nlink) != 1
    ):
        raise OSError("exact cleanup duplicate unlink unproved")


@dataclass(frozen=True)
class CleanupTombstoneInspection:
    """Private capability for one exact, still-complete cleanup tombstone."""

    transaction_ref: str
    cleanup_authority_sha256: str
    cleanup_plan_sha256: str
    intent_sha256: str
    terminal_checkpoint_sha256: str
    transaction_parent_identity: tuple[int, int, int, int]
    tombstone_identity: tuple[int, int, int, int]


@dataclass(frozen=True)
class ReservationAbortCleanupInspection:
    """One exact abort history that still needs compaction or resume."""

    transaction_ref: str
    state: Literal[
        "terminal_original",
        "planned_original",
        "cleanup_tombstone",
    ]
    cleanup_authority_sha256: str | None
    entry_identity: tuple[int, int, int, int]


@dataclass(frozen=True)
class ComponentExpectation:
    component_ref: str
    pre_sha256: str
    post_sha256: str

    def __post_init__(self) -> None:
        _token(self.component_ref, code="project_update_transaction_invalid")
        _digest(self.pre_sha256, code="project_update_transaction_invalid")
        _digest(self.post_sha256, code="project_update_transaction_invalid")


@dataclass(frozen=True)
class ComponentClassification:
    overall: ComponentOverallState
    component_states: tuple[tuple[str, str], ...]
    observed_state_sha256: str


def classify_components(
    expectations: Sequence[ComponentExpectation], live_sha256: Mapping[str, str]
) -> ComponentClassification:
    if (
        not expectations
        or len({item.component_ref for item in expectations}) != len(expectations)
        or set(live_sha256) != {item.component_ref for item in expectations}
    ):
        raise _fail("project_update_transaction_invalid")
    states: list[tuple[str, str]] = []
    vector: list[dict[str, str]] = []
    all_pre = True
    all_post = True
    unknown = False
    for item in sorted(expectations, key=lambda candidate: candidate.component_ref):
        live = _digest(live_sha256[item.component_ref], code="project_update_transaction_invalid")
        is_pre = hmac.compare_digest(live, item.pre_sha256)
        is_post = hmac.compare_digest(live, item.post_sha256)
        all_pre = all_pre and is_pre
        all_post = all_post and is_post
        if is_pre and is_post:
            state = "pre_and_post_exact"
        elif is_pre:
            state = "pre_exact"
        elif is_post:
            state = "post_exact"
        else:
            state = "unknown"
            unknown = True
        states.append((item.component_ref, state))
        vector.append({"component_ref": item.component_ref, "live_sha256": live})
    if unknown:
        overall: ComponentOverallState = "unknown"
    elif all_pre:
        overall = "prewrite_exact"
    elif all_post:
        overall = "complete_exact"
    else:
        overall = "mixed_exact"
    return ComponentClassification(
        overall=overall,
        component_states=tuple(states),
        observed_state_sha256=sha256_document(vector),
    )


@dataclass(frozen=True)
class ProjectUpdateCheckpoint:
    seq: int
    phase: str
    stage: CheckpointStage
    previous_checkpoint_sha256: str
    observed_state_sha256: str
    live_lock_observation_sha256: str
    checkpoint_sha256: str
    component_ref: str | None = None
    approval_reference_sha256: str | None = None
    approval_mac_sha256: str | None = None
    claim_receipt_sha256: str | None = None
    claim_mac_sha256: str | None = None
    claim_evidence_digests: tuple[tuple[str, str], ...] = ()
    cancellation_plan_sha256: str | None = None
    runtime_candidate_binding_sha256: str | None = None
    candidate_cleanup_receipt_sha256: str | None = None
    candidate_absence_observation_sha256: str | None = None


def _validate_static_receipt_postimage(
    raw: bytes, *, reservation: ProjectUpdateReservation
) -> tuple[str, str]:
    """Validate pre-intent domain plan/target digests, never approval context.

    Native approval authority is created only after the transaction is sealed
    and is independently bound by ``approval_bound`` and claim checkpoints.
    Treating either receipt digest as that later authority would be circular.
    """

    value = _parse_document(
        raw, code="project_update_transaction_intent_invalid"
    )
    required = {
        "plan_sha256",
        "schema",
        "target_binding_sha256",
        "timestamp",
        "transaction_ref",
    }
    if (
        not required.issubset(value)
        or value.get("transaction_ref") != reservation.transaction_ref
        or value.get("timestamp") != reservation.created_at
        or type(value.get("schema")) is not str
        or not value["schema"]
        or len(value["schema"]) > 160
    ):
        raise _fail("project_update_transaction_intent_invalid")

    forbidden = {
        "approval_id",
        "approval_reference",
        "approval_reference_sha256",
        "authority",
        "claim_mac",
        "claim_receipt",
        "claimed_at",
    }

    def inspect(item: Any) -> None:
        if type(item) is dict:
            for key, nested in item.items():
                if type(key) is not str or key.lower() in forbidden:
                    raise _fail("project_update_transaction_intent_invalid")
                inspect(nested)
        elif type(item) is list:
            for nested in item:
                inspect(nested)

    inspect(value)
    return (
        _digest(
            value.get("plan_sha256"),
            code="project_update_transaction_intent_invalid",
        ),
        _digest(
            value.get("target_binding_sha256"),
            code="project_update_transaction_intent_invalid",
        ),
    )


def _static_receipt_sha256(intent: ProjectUpdateIntent) -> str:
    matches = [
        record.sha256
        for record in intent.private_bindings
        if record.logical_key == "static-receipt-postimage"
    ]
    if len(matches) != 1:
        raise _fail("project_update_transaction_intent_invalid")
    return matches[0]


def _runtime_candidate_binding_sha256(intent: ProjectUpdateIntent) -> str:
    return sha256_document(intent.runtime_candidate.document())


def _candidate_absence_observation(
    transaction_root: Path,
    *,
    transaction_ref: str,
    reservation_sha256: str,
    intent_sha256: str | None,
    runtime_candidate_binding_sha256: str | None,
) -> str:
    """Durably bind exact absence without exposing a physical path."""

    _transaction_ref(transaction_ref)
    _digest(
        reservation_sha256,
        code="project_update_transaction_candidate_invalid",
    )
    if intent_sha256 is not None:
        _digest(
            intent_sha256,
            code="project_update_transaction_candidate_invalid",
        )
    if runtime_candidate_binding_sha256 is not None:
        _digest(
            runtime_candidate_binding_sha256,
            code="project_update_transaction_candidate_invalid",
        )
    candidate = transaction_root / RUNTIME_CANDIDATE_NAME
    seal = transaction_root / RUNTIME_CANDIDATE_SEAL_NAME
    _within(candidate, transaction_root)
    _within(seal, transaction_root)
    if os.path.lexists(candidate) or os.path.lexists(seal):
        raise _fail("project_update_transaction_candidate_invalid")
    root_info = _safe_directory(transaction_root, within=transaction_root)
    durability = _require_directory_durable(transaction_root)
    return sha256_document(
        {
            "candidate_logical_ref": (
                f"{_transaction_logical_ref(transaction_ref)}/{RUNTIME_CANDIDATE_NAME}"
            ),
            "directory_durability": durability.public_document(),
            "intent_sha256": intent_sha256,
            "reservation_sha256": reservation_sha256,
            "runtime_candidate_binding_sha256": (
                runtime_candidate_binding_sha256
            ),
            "schema": CANDIDATE_ABSENCE_SCHEMA,
            "seal_logical_ref": (
                f"{_transaction_logical_ref(transaction_ref)}/{RUNTIME_CANDIDATE_SEAL_NAME}"
            ),
            "state": "absent",
            "transaction_ref": transaction_ref,
            "transaction_root_identity": {
                "device": int(root_info.st_dev),
                "inode": int(root_info.st_ino),
            },
        }
    )


def _claim_evidence_digests(
    value: Mapping[str, str] | None,
    *,
    intent: ProjectUpdateIntent,
    approval_reference_sha256: str | None,
    claim_receipt_sha256: str | None,
    claim_mac_sha256: str | None,
) -> tuple[tuple[str, str], ...]:
    if (
        not isinstance(value, Mapping)
        or not value
        or len(value) > MAX_CLAIM_EVIDENCE_ITEMS
    ):
        raise _fail("project_update_transaction_state_transition_invalid")
    normalized: list[tuple[str, str]] = []
    for key in sorted(value):
        validated_key = _private_key(key)
        normalized.append(
            (
                validated_key,
                _digest(
                    value[key],
                    code="project_update_transaction_state_transition_invalid",
                ),
            )
        )
    if len({key for key, _digest_value in normalized}) != len(normalized):
        raise _fail("project_update_transaction_state_transition_invalid")
    document = dict(normalized)
    required = {
        "approval_reference_sha256": approval_reference_sha256,
        "claim_mac_sha256": claim_mac_sha256,
        "claim_receipt_sha256": claim_receipt_sha256,
        "static_receipt_sha256": _static_receipt_sha256(intent),
    }
    if any(value is None for value in required.values()) or any(
        document.get(key) != expected for key, expected in required.items()
    ):
        raise _fail("project_update_transaction_state_transition_invalid")
    return tuple(normalized)


@dataclass(frozen=True)
class JournalInspection:
    state: JournalState
    verified_prefix: tuple[ProjectUpdateCheckpoint, ...]
    unverified_tail_sha256: str | None
    unverified_tail_size: int
    reason_code: str | None

    @property
    def head_sha256(self) -> str:
        return (
            self.verified_prefix[-1].checkpoint_sha256
            if self.verified_prefix
            else CHECKPOINT_CHAIN_START_SHA256
        )


@dataclass(frozen=True)
class ProjectUpdateInspection:
    schema: str
    transaction_ref: str
    transaction_logical_ref: str
    intent_sha256: str
    project_identity_sha256: str
    requested_target_tag: str
    lock_backlinked: bool
    journal: JournalInspection
    terminal: bool


@dataclass(frozen=True)
class OrphanInspection:
    schema: str
    transaction_ref: str
    transaction_logical_ref: str
    classification: str
    evidence_sha256: str

    def public_document(self) -> dict[str, str]:
        return {
            "classification": self.classification,
            "evidence_sha256": self.evidence_sha256,
            "schema": self.schema,
            "transaction_logical_ref": self.transaction_logical_ref,
            "transaction_ref": self.transaction_ref,
        }


@dataclass(frozen=True)
class LockReleaseResult:
    released: bool
    absence_observation_sha256: str
    directory_durability: DirectoryDurability


@dataclass(frozen=True)
class _Event:
    phase: str
    stage: CheckpointStage
    component_ref: str | None
    authority: str


def _forward_events(intent: ProjectUpdateIntent) -> list[_Event]:
    result = [
        _Event("lock_backlinked", "verified", None, "none"),
        _Event("approval_bound", "verified", None, "main_new"),
    ]
    for component in intent.components:
        result.extend(
            (
                _Event(component.role, "intent", component.component_ref, "main"),
                _Event(component.role, "verified", component.component_ref, "main"),
            )
        )
    result.append(_Event("domain_committed", "verified", None, "main"))
    return result


def _rollback_events(intent: ProjectUpdateIntent) -> list[_Event]:
    result = [_Event("rollback_authorized", "verified", None, "rollback_new")]
    for component in reversed(intent.components):
        result.extend(
            (
                _Event("rollback_effect", "intent", component.component_ref, "rollback"),
                _Event("rollback_effect", "verified", component.component_ref, "rollback"),
            )
        )
    result.append(_Event("rollback_verified", "verified", None, "rollback"))
    return result


def _final_events(authority: str) -> list[_Event]:
    return [
        _Event("claim_succeeded", "verified", None, f"claim_{authority}"),
        _Event("ready_to_unlock", "verified", None, f"final_{authority}"),
        _Event("lock_released", "verified", None, f"final_{authority}"),
        _Event("completed", "verified", None, f"final_{authority}"),
    ]


def _preapproval_cancel_events() -> list[_Event]:
    return [
        _Event("preapproval_cancel_requested", "intent", None, "cancel_intent"),
        _Event("preapproval_cancelled", "verified", None, "cancel_verified"),
        _Event("ready_to_unlock", "verified", None, "none"),
        _Event("lock_released", "verified", None, "none"),
        _Event("completed", "verified", None, "none"),
    ]


def _candidate_sequences(intent: ProjectUpdateIntent) -> tuple[tuple[_Event, ...], ...]:
    forward = _forward_events(intent)
    cancel = _preapproval_cancel_events()
    candidates: list[tuple[_Event, ...]] = [
        tuple(forward + _final_events("main")),
        tuple(cancel),
        tuple([forward[0], *cancel]),
    ]
    # Rollback may be explicitly authorized after main approval and before the
    # claim is finalized.  Every candidate still rolls all components back in
    # reverse order; already-pre components become verified no-op effects.
    for branch_at in range(2, len(forward) + 1):
        candidates.append(
            tuple(
                forward[:branch_at]
                + _rollback_events(intent)
                + _final_events("rollback")
            )
        )
    return tuple(candidates)


def _authority_values(
    checkpoints: Sequence[ProjectUpdateCheckpoint], authority_name: str
) -> tuple[str, str] | None:
    phase = "approval_bound" if authority_name == "main" else "rollback_authorized"
    for checkpoint in reversed(checkpoints):
        if checkpoint.phase == phase:
            if (
                checkpoint.approval_reference_sha256 is None
                or checkpoint.approval_mac_sha256 is None
            ):
                return None
            return checkpoint.approval_reference_sha256, checkpoint.approval_mac_sha256
    return None


def _claim_values(
    checkpoints: Sequence[ProjectUpdateCheckpoint], authority_name: str
) -> tuple[str, str] | None:
    for checkpoint in reversed(checkpoints):
        if checkpoint.phase == "claim_succeeded":
            active = _authority_values(checkpoints, authority_name)
            if (
                active is not None
                and checkpoint.approval_reference_sha256 == active[0]
                and checkpoint.approval_mac_sha256 == active[1]
                and checkpoint.claim_receipt_sha256 is not None
                and checkpoint.claim_mac_sha256 is not None
            ):
                return checkpoint.claim_receipt_sha256, checkpoint.claim_mac_sha256
    return None


def _checkpoint_matches_event(
    checkpoint: ProjectUpdateCheckpoint,
    event: _Event,
    prefix: Sequence[ProjectUpdateCheckpoint],
) -> bool:
    if (
        checkpoint.phase != event.phase
        or checkpoint.stage != event.stage
        or checkpoint.component_ref != event.component_ref
    ):
        return False
    cancellation_values = (
        checkpoint.cancellation_plan_sha256,
        checkpoint.runtime_candidate_binding_sha256,
        checkpoint.candidate_cleanup_receipt_sha256,
        checkpoint.candidate_absence_observation_sha256,
    )
    authority = event.authority
    if authority not in {"cancel_intent", "cancel_verified"} and any(
        value is not None for value in cancellation_values
    ):
        return False
    if authority == "none":
        return all(
            value is None
            for value in (
                checkpoint.approval_reference_sha256,
                checkpoint.approval_mac_sha256,
                checkpoint.claim_receipt_sha256,
                checkpoint.claim_mac_sha256,
                *cancellation_values,
            )
        ) and not checkpoint.claim_evidence_digests
    if authority == "cancel_intent":
        return (
            checkpoint.cancellation_plan_sha256 is not None
            and checkpoint.runtime_candidate_binding_sha256 is not None
            and checkpoint.candidate_cleanup_receipt_sha256 is None
            and checkpoint.candidate_absence_observation_sha256 is None
            and all(
                value is None
                for value in (
                    checkpoint.approval_reference_sha256,
                    checkpoint.approval_mac_sha256,
                    checkpoint.claim_receipt_sha256,
                    checkpoint.claim_mac_sha256,
                )
            )
            and not checkpoint.claim_evidence_digests
        )
    if authority == "cancel_verified":
        requested = next(
            (
                item
                for item in reversed(prefix)
                if item.phase == "preapproval_cancel_requested"
            ),
            None,
        )
        return (
            requested is not None
            and checkpoint.cancellation_plan_sha256
            == requested.cancellation_plan_sha256
            and checkpoint.runtime_candidate_binding_sha256
            == requested.runtime_candidate_binding_sha256
            and checkpoint.candidate_cleanup_receipt_sha256 is not None
            and checkpoint.candidate_absence_observation_sha256 is not None
            and all(
                value is None
                for value in (
                    checkpoint.approval_reference_sha256,
                    checkpoint.approval_mac_sha256,
                    checkpoint.claim_receipt_sha256,
                    checkpoint.claim_mac_sha256,
                )
            )
            and not checkpoint.claim_evidence_digests
        )
    if authority in {"main_new", "rollback_new"}:
        if checkpoint.approval_reference_sha256 is None or checkpoint.approval_mac_sha256 is None:
            return False
        if authority == "rollback_new":
            main = _authority_values(prefix, "main")
            if main is None or (
                checkpoint.approval_reference_sha256,
                checkpoint.approval_mac_sha256,
            ) == main:
                return False
        return (
            checkpoint.claim_receipt_sha256 is None
            and checkpoint.claim_mac_sha256 is None
            and not checkpoint.claim_evidence_digests
        )
    authority_name = "rollback" if "rollback" in authority else "main"
    expected = _authority_values(prefix, authority_name)
    if expected is None or (
        checkpoint.approval_reference_sha256,
        checkpoint.approval_mac_sha256,
    ) != expected:
        return False
    if authority.startswith("claim_"):
        return (
            checkpoint.claim_receipt_sha256 is not None
            and checkpoint.claim_mac_sha256 is not None
            and bool(checkpoint.claim_evidence_digests)
        )
    if authority.startswith("final_"):
        claim = _claim_values(prefix, authority_name)
        return claim is not None and not checkpoint.claim_evidence_digests and (
            checkpoint.claim_receipt_sha256,
            checkpoint.claim_mac_sha256,
        ) == claim
    return (
        checkpoint.claim_receipt_sha256 is None
        and checkpoint.claim_mac_sha256 is None
        and not checkpoint.claim_evidence_digests
    )


def _matching_candidates(
    checkpoints: Sequence[ProjectUpdateCheckpoint], intent: ProjectUpdateIntent
) -> tuple[tuple[_Event, ...], ...]:
    result: list[tuple[_Event, ...]] = []
    for candidate in _candidate_sequences(intent):
        if len(checkpoints) > len(candidate):
            continue
        if all(
            _checkpoint_matches_event(checkpoint, candidate[index], checkpoints[:index])
            for index, checkpoint in enumerate(checkpoints)
        ):
            result.append(candidate)
    return tuple(result)


def _next_events(
    checkpoints: Sequence[ProjectUpdateCheckpoint], intent: ProjectUpdateIntent
) -> tuple[_Event, ...]:
    candidates = _matching_candidates(checkpoints, intent)
    if not candidates:
        raise _fail("project_update_transaction_state_transition_invalid")
    unique: dict[tuple[str, str, str | None, str], _Event] = {}
    for candidate in candidates:
        if len(checkpoints) < len(candidate):
            event = candidate[len(checkpoints)]
            unique[(event.phase, event.stage, event.component_ref, event.authority)] = event
    return tuple(unique.values())


@contextmanager
def _exclusive_guard(path: Path, *, within: Path) -> Iterator[None]:
    try:
        guard_bytes = _read_regular(path, within=within, maximum=1)
    except (OSError, ProjectUpdateTransactionError):
        raise _fail("project_update_transaction_checkpoint_write_failed") from None
    if guard_bytes != b"\x00":
        raise _fail("project_update_transaction_checkpoint_write_failed")
    named = _safe_regular(path, within=within)
    try:
        descriptor = os.open(path, _flags(os.O_RDWR))
    except OSError:
        raise _fail("project_update_transaction_checkpoint_write_failed") from None
    locked = False
    try:
        opened = os.fstat(descriptor)
        if (
            (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino)
            or opened.st_size != 1
        ):
            raise _fail("project_update_transaction_checkpoint_write_failed")
        if os.name == "nt":
            import msvcrt

            os.lseek(descriptor, 0, os.SEEK_SET)
            try:
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            except OSError:
                raise _fail("project_update_transaction_checkpoint_write_failed") from None
            locked = True
        else:
            import fcntl

            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise _fail("project_update_transaction_checkpoint_write_failed") from None
            locked = True
        locked_info = os.fstat(descriptor)
        named_after_lock = _safe_regular(path, within=within)
        if (
            locked_info.st_size != 1
            or (locked_info.st_dev, locked_info.st_ino)
            != (opened.st_dev, opened.st_ino)
            or (named_after_lock.st_dev, named_after_lock.st_ino)
            != (opened.st_dev, opened.st_ino)
        ):
            raise _fail("project_update_transaction_checkpoint_write_failed")
        yield
    finally:
        if locked:
            try:
                if os.name == "nt":
                    import msvcrt

                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(descriptor, fcntl.LOCK_UN)
            except OSError:
                pass
        os.close(descriptor)


class ReservedProjectUpdateTransaction:
    """Durable reservation whose candidate and final intent are not sealed yet."""

    def __init__(
        self,
        project: Path,
        root: Path,
        reservation: ProjectUpdateReservation,
    ) -> None:
        self._project_root = project
        self._transaction_root = root
        self.reservation = reservation

    @property
    def transaction_ref(self) -> str:
        return self.reservation.transaction_ref

    @property
    def transaction_logical_ref(self) -> str:
        return self.reservation.transaction_logical_ref

    @property
    def created_at(self) -> str:
        return self.reservation.created_at

    @property
    def transaction_root(self) -> Path:
        return self._transaction_root

    @property
    def runtime_candidate_path(self) -> Path:
        path = self._transaction_root / RUNTIME_CANDIDATE_NAME
        _within(path, self._transaction_root)
        return path

    @property
    def runtime_candidate_seal_path(self) -> Path:
        path = self._transaction_root / RUNTIME_CANDIDATE_SEAL_NAME
        _within(path, self._transaction_root)
        return path

    @property
    def _lock_path(self) -> Path:
        path = self._project_root / PurePosixPath(PROJECT_UPDATE_LOCK_LOGICAL)
        _within(path, self._project_root)
        return path

    @classmethod
    def reserve(
        cls,
        project_root: Path | str,
        *,
        project_identity_sha256: str,
        requested_target_tag: str,
        transaction_ref: str | None = None,
        ownership_nonce: str | None = None,
        created_at: str = "1970-01-01T00:00:00Z",
    ) -> "ReservedProjectUpdateTransaction":
        project = _absolute(project_root)
        _safe_existing_chain(project, directory=True)
        ref = _transaction_ref(transaction_ref or f"update_{secrets.token_hex(16)}")
        nonce = ownership_nonce or secrets.token_hex(16)
        logical = _transaction_logical_ref(ref)
        reservation = ProjectUpdateReservation(
            transaction_ref=ref,
            transaction_logical_ref=logical,
            project_identity_sha256=project_identity_sha256,
            requested_target_tag=requested_target_tag,
            ownership_nonce=nonce,
            runtime_candidate_logical_ref=f"{logical}/{RUNTIME_CANDIDATE_NAME}",
            runtime_candidate_seal_logical_ref=(
                f"{logical}/{RUNTIME_CANDIDATE_SEAL_NAME}"
            ),
            created_at=created_at,
        )
        parent = _mkdirs(project, TRANSACTION_ROOT_LOGICAL)
        root = parent / ref
        tombstone = parent / f".cleanup_{ref}"
        proof = parent / f".cleanup-proof_{ref}.json"
        if os.path.lexists(tombstone) or os.path.lexists(proof):
            raise _fail("project_update_transaction_exists")
        _within(root, project)
        try:
            root.mkdir(mode=0o700)
        except FileExistsError:
            raise _fail("project_update_transaction_exists") from None
        except OSError:
            raise _fail("project_update_transaction_path_unsafe") from None
        _safe_directory(root, within=project)
        _write_new(root / "marker.json", _document_bytes(reservation.document()), within=root)
        _write_new(root / "append.guard", b"\x00", within=root)
        _require_directory_durable(root)
        _require_directory_durable(parent)
        return cls.open(project, ref)

    @classmethod
    def open(
        cls, project_root: Path | str, transaction_ref: str
    ) -> "ReservedProjectUpdateTransaction":
        project = _absolute(project_root)
        _safe_existing_chain(project, directory=True)
        ref = _transaction_ref(transaction_ref)
        root = project / PurePosixPath(TRANSACTION_ROOT_LOGICAL) / ref
        _within(root, project)
        if not os.path.lexists(root):
            raise _fail("project_update_transaction_not_found")
        _safe_existing_chain(root, directory=True)
        marker = _parse_document(
            _read_regular(root / "marker.json", within=root, maximum=MAX_DOCUMENT_BYTES + 1),
            code="project_update_transaction_intent_invalid",
        )
        reservation = ProjectUpdateReservation.from_document(marker)
        if reservation.transaction_ref != ref:
            raise _fail("project_update_transaction_intent_invalid")
        if _read_regular(root / "append.guard", within=root) != b"\x00":
            raise _fail("project_update_transaction_intent_invalid")
        return cls(project, root, reservation)

    def lock_document(
        self, *, observation: LockObservation | None = None
    ) -> dict[str, Any]:
        return build_lock_document(self.reservation, observation=observation)

    def lock_bytes(self, *, observation: LockObservation | None = None) -> bytes:
        return lock_document_bytes(self.lock_document(observation=observation))

    def public_summary(self) -> dict[str, Any]:
        try:
            abort = self.inspect_abort_receipt()
            abort_state = None
        except ProjectUpdateTransactionError:
            abort = None
            abort_state = "manual_review_abort_incomplete_or_invalid"
        if abort is not None:
            return {
                "created_at": self.created_at,
                "intent_sealed": False,
                "lock_state": "released_exact",
                "runtime_candidate_logical_ref": (
                    self.reservation.runtime_candidate_logical_ref
                ),
                "schema": RESERVATION_PUBLIC_SUMMARY_SCHEMA,
                "state": "aborted_before_intent_seal",
                "transaction_logical_ref": self.transaction_logical_ref,
                "transaction_ref": self.transaction_ref,
            }
        lock_state = "absent"
        if os.path.lexists(self._lock_path):
            try:
                self._present_lock()
                lock_state = "reservation_exact"
            except ProjectUpdateTransactionError:
                lock_state = "manual_review"
        result = {
            "created_at": self.created_at,
            "intent_sealed": os.path.lexists(self._transaction_root / "intent-seal.json"),
            "lock_state": lock_state,
            "runtime_candidate_logical_ref": (
                self.reservation.runtime_candidate_logical_ref
            ),
            "schema": RESERVATION_PUBLIC_SUMMARY_SCHEMA,
            "transaction_logical_ref": self.transaction_logical_ref,
            "transaction_ref": self.transaction_ref,
        }
        if abort_state is not None:
            result["state"] = abort_state
        return result

    def _present_lock(
        self, expected_lock_bytes: bytes | None = None
    ) -> tuple[str, bytes, dict[str, int]]:
        raw, info = _read_regular_with_info(
            self._lock_path,
            within=self._project_root,
            maximum=MAX_DOCUMENT_BYTES + 1,
        )
        _parse_lock_bytes(raw, reservation=self.reservation)
        if expected_lock_bytes is not None and not hmac.compare_digest(
            raw, expected_lock_bytes
        ):
            raise _fail("project_update_transaction_lock_invalid")
        identity = _identity_document(info)
        observation = {
            "lock_identity": identity,
            "lock_logical_ref": PROJECT_UPDATE_LOCK_LOGICAL,
            "lock_sha256": sha256_bytes(raw),
            "schema": LOCK_OBSERVATION_SCHEMA,
            "state": "present",
            "transaction_ref": self.transaction_ref,
        }
        return sha256_document(observation), raw, identity

    def acquire_lock(self, *, observation: LockObservation | None = None) -> bytes:
        """Acquire or exactly resume this reservation's immutable O_EXCL lock."""

        if os.path.lexists(
            self._transaction_root / RESERVATION_ABORT_INTENT_NAME
        ) or os.path.lexists(
            self._transaction_root / RESERVATION_ABORT_RECEIPT_NAME
        ):
            raise _fail("project_update_transaction_state_transition_invalid")
        expected = self.lock_bytes(observation=observation)
        parent = self._lock_path.parent
        _safe_existing_chain(parent, directory=True)
        if not os.path.lexists(self._lock_path):
            _write_new(self._lock_path, expected, within=self._project_root)
            _require_directory_durable(parent)
        observed_sha, actual, identity = self._present_lock(expected)
        backlink = {
            "live_lock_observation_sha256": observed_sha,
            "lock_identity": identity,
            "lock_sha256": sha256_bytes(actual),
            "ownership_nonce": self.reservation.ownership_nonce,
            "project_identity_sha256": self.reservation.project_identity_sha256,
            "reservation_sha256": self.reservation.sha256,
            "schema": RESERVATION_LOCK_BACKLINK_SCHEMA,
            "transaction_logical_ref": self.transaction_logical_ref,
            "transaction_ref": self.transaction_ref,
        }
        path = self._transaction_root / RESERVATION_LOCK_BACKLINK_NAME
        encoded = _document_bytes(backlink)
        if os.path.lexists(path):
            if not hmac.compare_digest(
                _read_regular(path, within=self._transaction_root), encoded
            ):
                raise _fail("project_update_transaction_lock_invalid")
        else:
            _write_new(path, encoded, within=self._transaction_root)
            _require_directory_durable(self._transaction_root)
        self._verify_reservation_backlink(expected)
        return actual

    def existing_lock_bytes_read_only(self) -> bytes:
        """Read the exact existing reservation lock without recreating it."""

        _observed, actual, _identity = self._present_lock(
            self.lock_bytes()
        )
        self._verify_reservation_backlink(actual)
        return actual

    def _verify_reservation_backlink(
        self, expected_lock_bytes: bytes | None = None
    ) -> dict[str, Any]:
        value = self._read_reservation_backlink()
        observed_sha, actual, actual_identity = self._present_lock(expected_lock_bytes)
        if (
            value.get("lock_sha256") != sha256_bytes(actual)
            or value.get("lock_identity") != actual_identity
            or value.get("live_lock_observation_sha256") != observed_sha
        ):
            raise _fail("project_update_transaction_lock_invalid")
        return value

    def _read_reservation_backlink(self) -> dict[str, Any]:
        value = _parse_document(
            _read_regular(
                self._transaction_root / RESERVATION_LOCK_BACKLINK_NAME,
                within=self._transaction_root,
                maximum=MAX_DOCUMENT_BYTES + 1,
            ),
            code="project_update_transaction_lock_invalid",
        )
        expected_keys = {
            "live_lock_observation_sha256",
            "lock_identity",
            "lock_sha256",
            "ownership_nonce",
            "project_identity_sha256",
            "reservation_sha256",
            "schema",
            "transaction_logical_ref",
            "transaction_ref",
        }
        identity = value.get("lock_identity")
        if (
            set(value) != expected_keys
            or value.get("schema") != RESERVATION_LOCK_BACKLINK_SCHEMA
            or value.get("reservation_sha256") != self.reservation.sha256
            or value.get("ownership_nonce") != self.reservation.ownership_nonce
            or value.get("project_identity_sha256")
            != self.reservation.project_identity_sha256
            or value.get("transaction_logical_ref") != self.transaction_logical_ref
            or value.get("transaction_ref") != self.transaction_ref
            or type(identity) is not dict
            or set(identity) != {"device", "inode", "modified_ns", "size"}
            or any(type(item) is not int for item in identity.values())
        ):
            raise _fail("project_update_transaction_lock_invalid")
        _digest(
            value.get("lock_sha256"),
            code="project_update_transaction_lock_invalid",
        )
        return value

    def _absent_lock_observation(self, backlink: Mapping[str, Any]) -> str:
        parent = self._lock_path.parent
        _safe_existing_chain(parent, directory=True)
        if os.path.lexists(self._lock_path):
            raise _fail("project_update_transaction_lock_invalid")
        parent_info = _safe_directory(parent, within=self._project_root)
        return sha256_document(
            {
                "lock_logical_ref": PROJECT_UPDATE_LOCK_LOGICAL,
                "prior_lock_sha256": backlink["lock_sha256"],
                "schema": LOCK_OBSERVATION_SCHEMA,
                "state": "absent",
                "transaction_ref": self.transaction_ref,
                "verified_parent_identity": {
                    "device": int(parent_info.st_dev),
                    "inode": int(parent_info.st_ino),
                },
            }
        )

    def reservation_abort_plan_sha256(self) -> str:
        """Reproduce the only plan allowed for an empty reserved transaction."""

        backlink = self._read_reservation_backlink()
        candidate_absence = _candidate_absence_observation(
            self._transaction_root,
            transaction_ref=self.transaction_ref,
            reservation_sha256=self.reservation.sha256,
            intent_sha256=None,
            runtime_candidate_binding_sha256=None,
        )
        return sha256_document(
            {
                "candidate_absence_observation_sha256": candidate_absence,
                "lock_sha256": backlink["lock_sha256"],
                "operation": "abort_empty_reservation",
                "reservation_sha256": self.reservation.sha256,
                "schema": RESERVATION_ABORT_PLAN_SCHEMA,
                "transaction_ref": self.transaction_ref,
            }
        )

    def _validated_abort_intent_after_lock_release(
        self,
    ) -> tuple[dict[str, Any], dict[str, Any], str, str, str]:
        """Validate the sole receipt-pending empty-reservation abort state."""

        if os.path.lexists(self._lock_path):
            raise _fail("project_update_transaction_lock_invalid")
        files, directories = ProjectUpdateTransaction._descendant_names(
            self._transaction_root
        )
        expected_files = {
            "append.guard",
            "marker.json",
            RESERVATION_LOCK_BACKLINK_NAME,
            RESERVATION_ABORT_INTENT_NAME,
        }
        if directories or files != expected_files:
            raise _fail("project_update_transaction_candidate_invalid")

        backlink = self._read_reservation_backlink()
        intent_path = self._transaction_root / RESERVATION_ABORT_INTENT_NAME
        abort_intent = _parse_document(
            _read_regular(intent_path, within=self._transaction_root),
            code="project_update_transaction_state_transition_invalid",
        )
        expected_intent_keys = {
            "candidate_absence_observation_sha256",
            "candidate_cleanup_evidence_sha256",
            "lock_sha256",
            "reservation_lock_backlink_sha256",
            "reservation_sha256",
            "schema",
            "transaction_logical_ref",
            "transaction_ref",
        }
        cleanup_evidence = _digest(
            abort_intent.get("candidate_cleanup_evidence_sha256"),
            code="project_update_transaction_state_transition_invalid",
        )
        candidate_absence = _candidate_absence_observation(
            self._transaction_root,
            transaction_ref=self.transaction_ref,
            reservation_sha256=self.reservation.sha256,
            intent_sha256=None,
            runtime_candidate_binding_sha256=None,
        )
        if (
            set(abort_intent) != expected_intent_keys
            or abort_intent.get("schema") != RESERVATION_ABORT_INTENT_SCHEMA
            or abort_intent.get("transaction_ref") != self.transaction_ref
            or abort_intent.get("transaction_logical_ref")
            != self.transaction_logical_ref
            or abort_intent.get("reservation_sha256")
            != self.reservation.sha256
            or abort_intent.get("reservation_lock_backlink_sha256")
            != sha256_document(backlink)
            or abort_intent.get("lock_sha256") != backlink["lock_sha256"]
            or abort_intent.get("candidate_absence_observation_sha256")
            != candidate_absence
            or cleanup_evidence != self.reservation_abort_plan_sha256()
        ):
            raise _fail("project_update_transaction_state_transition_invalid")
        lock_absence = self._absent_lock_observation(backlink)
        return (
            backlink,
            abort_intent,
            candidate_absence,
            cleanup_evidence,
            lock_absence,
        )

    def inspect_abort_receipt_pending_read_only(self) -> dict[str, Any] | None:
        """Classify an exact post-unlink/pre-receipt abort without writing."""

        intent_path = self._transaction_root / RESERVATION_ABORT_INTENT_NAME
        receipt_path = self._transaction_root / RESERVATION_ABORT_RECEIPT_NAME
        if not os.path.lexists(intent_path) and not os.path.lexists(receipt_path):
            return None
        if not os.path.lexists(intent_path) or os.path.lexists(receipt_path):
            raise _fail("project_update_transaction_state_transition_invalid")
        (
            _backlink,
            abort_intent,
            _candidate_absence,
            cleanup_evidence,
            _lock_absence,
        ) = self._validated_abort_intent_after_lock_release()
        return {
            "abort_intent_sha256": sha256_document(abort_intent),
            "candidate_cleanup_evidence_sha256": cleanup_evidence,
            "schema": RESERVATION_ABORT_INTENT_SCHEMA,
            "state": "abort_receipt_pending_after_lock_release",
            "transaction_logical_ref": self.transaction_logical_ref,
            "transaction_ref": self.transaction_ref,
        }

    def resume_abort_after_lock_release(self) -> dict[str, Any]:
        """Complete the exact receipt after process loss following lock unlink."""

        (
            backlink,
            abort_intent,
            candidate_absence,
            cleanup_evidence,
            _prior_lock_absence,
        ) = self._validated_abort_intent_after_lock_release()
        lock_parent_durability = _require_directory_durable(
            self._lock_path.parent
        )
        # Recheck after the durability call so a newly acquired live lock is
        # never covered by a stale absence observation.
        lock_absence = self._absent_lock_observation(backlink)
        receipt = {
            "abort_intent_sha256": sha256_document(abort_intent),
            "candidate_absence_observation_sha256": candidate_absence,
            "candidate_cleanup_evidence_sha256": cleanup_evidence,
            "lock_absence_observation_sha256": lock_absence,
            "lock_parent_durability": lock_parent_durability.public_document(),
            "reservation_sha256": self.reservation.sha256,
            "schema": RESERVATION_ABORT_RECEIPT_SCHEMA,
            "state": "aborted_before_intent_seal",
            "transaction_logical_ref": self.transaction_logical_ref,
            "transaction_ref": self.transaction_ref,
        }
        receipt_path = self._transaction_root / RESERVATION_ABORT_RECEIPT_NAME
        _write_new(
            receipt_path,
            _document_bytes(receipt),
            within=self._transaction_root,
        )
        _require_directory_durable(self._transaction_root)
        terminal = self.inspect_abort_receipt()
        if terminal is None:
            raise _fail("project_update_transaction_state_transition_invalid")
        return terminal

    def abort_before_intent_seal(
        self,
        *,
        expected_lock_bytes: bytes,
        candidate_cleanup_evidence_sha256: str | None = None,
    ) -> dict[str, Any]:
        """Exactly release an unchanged reservation after candidate absence.

        Unknown or partial candidate trees are never touched.  The caller's
        cleanup/no-candidate evidence is content-bound and the durable abort
        intent is written before the live reservation lock is removed.
        """

        _parse_lock_bytes(expected_lock_bytes, reservation=self.reservation)
        backlink = self._read_reservation_backlink()
        if backlink["lock_sha256"] != sha256_bytes(expected_lock_bytes):
            raise _fail("project_update_transaction_lock_invalid")
        files, directories = ProjectUpdateTransaction._descendant_names(
            self._transaction_root
        )
        allowed_files = {
            "append.guard",
            "marker.json",
            RESERVATION_LOCK_BACKLINK_NAME,
            RESERVATION_ABORT_INTENT_NAME,
            RESERVATION_ABORT_RECEIPT_NAME,
        }
        if directories or not files.issubset(allowed_files) or not {
            "append.guard",
            "marker.json",
            RESERVATION_LOCK_BACKLINK_NAME,
        }.issubset(files):
            raise _fail("project_update_transaction_candidate_invalid")
        candidate_absence = _candidate_absence_observation(
            self._transaction_root,
            transaction_ref=self.transaction_ref,
            reservation_sha256=self.reservation.sha256,
            intent_sha256=None,
            runtime_candidate_binding_sha256=None,
        )
        exact_cleanup_evidence = self.reservation_abort_plan_sha256()
        if candidate_cleanup_evidence_sha256 is None:
            cleanup_evidence = exact_cleanup_evidence
        else:
            cleanup_evidence = _digest(
                candidate_cleanup_evidence_sha256,
                code="project_update_transaction_candidate_invalid",
            )
            if cleanup_evidence != exact_cleanup_evidence:
                raise _fail("project_update_transaction_candidate_invalid")
        abort_intent = {
            "candidate_absence_observation_sha256": candidate_absence,
            "candidate_cleanup_evidence_sha256": cleanup_evidence,
            "lock_sha256": backlink["lock_sha256"],
            "reservation_lock_backlink_sha256": sha256_document(backlink),
            "reservation_sha256": self.reservation.sha256,
            "schema": RESERVATION_ABORT_INTENT_SCHEMA,
            "transaction_logical_ref": self.transaction_logical_ref,
            "transaction_ref": self.transaction_ref,
        }
        intent_path = self._transaction_root / RESERVATION_ABORT_INTENT_NAME
        intent_bytes = _document_bytes(abort_intent)
        if os.path.lexists(intent_path):
            if not hmac.compare_digest(
                _read_regular(intent_path, within=self._transaction_root),
                intent_bytes,
            ):
                raise _fail("project_update_transaction_state_transition_invalid")
        else:
            _write_new(intent_path, intent_bytes, within=self._transaction_root)
            _require_directory_durable(self._transaction_root)

        if os.path.lexists(self._lock_path):
            self._verify_reservation_backlink(expected_lock_bytes)
            try:
                self._lock_path.unlink()
            except OSError:
                raise _fail("project_update_transaction_lock_invalid") from None
        lock_parent_durability = _require_directory_durable(self._lock_path.parent)
        lock_absence = self._absent_lock_observation(backlink)
        receipt = {
            "abort_intent_sha256": sha256_document(abort_intent),
            "candidate_absence_observation_sha256": candidate_absence,
            "candidate_cleanup_evidence_sha256": cleanup_evidence,
            "lock_absence_observation_sha256": lock_absence,
            "lock_parent_durability": lock_parent_durability.public_document(),
            "reservation_sha256": self.reservation.sha256,
            "schema": RESERVATION_ABORT_RECEIPT_SCHEMA,
            "state": "aborted_before_intent_seal",
            "transaction_logical_ref": self.transaction_logical_ref,
            "transaction_ref": self.transaction_ref,
        }
        receipt_path = self._transaction_root / RESERVATION_ABORT_RECEIPT_NAME
        receipt_bytes = _document_bytes(receipt)
        if os.path.lexists(receipt_path):
            if not hmac.compare_digest(
                _read_regular(receipt_path, within=self._transaction_root),
                receipt_bytes,
            ):
                raise _fail("project_update_transaction_state_transition_invalid")
        else:
            _write_new(receipt_path, receipt_bytes, within=self._transaction_root)
            _require_directory_durable(self._transaction_root)
        return {
            "candidate_cleanup_evidence_sha256": cleanup_evidence,
            "receipt_sha256": sha256_document(receipt),
            "schema": RESERVATION_ABORT_RECEIPT_SCHEMA,
            "state": "aborted_before_intent_seal",
            "transaction_logical_ref": self.transaction_logical_ref,
            "transaction_ref": self.transaction_ref,
        }

    def inspect_abort_receipt(self) -> dict[str, Any] | None:
        """Validate an already-terminal reservation abort without mutating it."""

        intent_path = self._transaction_root / RESERVATION_ABORT_INTENT_NAME
        receipt_path = self._transaction_root / RESERVATION_ABORT_RECEIPT_NAME
        if not os.path.lexists(intent_path) and not os.path.lexists(receipt_path):
            return None
        if not os.path.lexists(intent_path) or not os.path.lexists(receipt_path):
            raise _fail("project_update_transaction_state_transition_invalid")
        backlink = self._read_reservation_backlink()
        abort_intent = _parse_document(
            _read_regular(intent_path, within=self._transaction_root),
            code="project_update_transaction_state_transition_invalid",
        )
        expected_intent_keys = {
            "candidate_absence_observation_sha256",
            "candidate_cleanup_evidence_sha256",
            "lock_sha256",
            "reservation_lock_backlink_sha256",
            "reservation_sha256",
            "schema",
            "transaction_logical_ref",
            "transaction_ref",
        }
        if (
            set(abort_intent) != expected_intent_keys
            or abort_intent.get("schema") != RESERVATION_ABORT_INTENT_SCHEMA
            or abort_intent.get("transaction_ref") != self.transaction_ref
            or abort_intent.get("transaction_logical_ref")
            != self.transaction_logical_ref
            or abort_intent.get("reservation_sha256") != self.reservation.sha256
            or abort_intent.get("reservation_lock_backlink_sha256")
            != sha256_document(backlink)
            or abort_intent.get("lock_sha256") != backlink["lock_sha256"]
        ):
            raise _fail("project_update_transaction_state_transition_invalid")
        cleanup_evidence = _digest(
            abort_intent.get("candidate_cleanup_evidence_sha256"),
            code="project_update_transaction_state_transition_invalid",
        )
        candidate_absence = _candidate_absence_observation(
            self._transaction_root,
            transaction_ref=self.transaction_ref,
            reservation_sha256=self.reservation.sha256,
            intent_sha256=None,
            runtime_candidate_binding_sha256=None,
        )
        if (
            abort_intent.get("candidate_absence_observation_sha256")
            != candidate_absence
        ):
            raise _fail("project_update_transaction_candidate_invalid")
        lock_absence = self._absent_lock_observation(backlink)
        lock_parent_durability = _require_directory_durable(self._lock_path.parent)
        receipt = _parse_document(
            _read_regular(receipt_path, within=self._transaction_root),
            code="project_update_transaction_state_transition_invalid",
        )
        expected_receipt = {
            "abort_intent_sha256": sha256_document(abort_intent),
            "candidate_absence_observation_sha256": candidate_absence,
            "candidate_cleanup_evidence_sha256": cleanup_evidence,
            "lock_absence_observation_sha256": lock_absence,
            "lock_parent_durability": lock_parent_durability.public_document(),
            "reservation_sha256": self.reservation.sha256,
            "schema": RESERVATION_ABORT_RECEIPT_SCHEMA,
            "state": "aborted_before_intent_seal",
            "transaction_logical_ref": self.transaction_logical_ref,
            "transaction_ref": self.transaction_ref,
        }
        if not hmac.compare_digest(
            canonical_json_bytes(receipt), canonical_json_bytes(expected_receipt)
        ):
            raise _fail("project_update_transaction_state_transition_invalid")
        return {
            "candidate_cleanup_evidence_sha256": cleanup_evidence,
            "receipt_sha256": sha256_document(receipt),
            "schema": RESERVATION_ABORT_RECEIPT_SCHEMA,
            "state": "aborted_before_intent_seal",
            "transaction_logical_ref": self.transaction_logical_ref,
            "transaction_ref": self.transaction_ref,
        }

    @staticmethod
    def _abort_cleanup_paths(
        parent: Path, transaction_ref: str
    ) -> tuple[Path, Path]:
        _transaction_ref(transaction_ref)
        return (
            parent / f".cleanup_{transaction_ref}",
            parent / f".cleanup-proof_{transaction_ref}.json",
        )

    @staticmethod
    def _abort_cleanup_expected_files() -> tuple[str, ...]:
        return (
            "append.guard",
            "marker.json",
            RESERVATION_ABORT_INTENT_NAME,
            RESERVATION_ABORT_RECEIPT_NAME,
            RESERVATION_LOCK_BACKLINK_NAME,
        )

    @staticmethod
    def _abort_cleanup_root_identity(
        plan: Mapping[str, Any],
    ) -> tuple[int, int, int | None]:
        identity = plan["transaction_root_identity"]
        return (
            int(identity["device"]),
            int(identity["inode"]),
            identity["birthtime_ns"],
        )

    @staticmethod
    def _abort_cleanup_file_snapshots(
        plan: Mapping[str, Any],
    ) -> dict[str, _CleanupFileSnapshot]:
        snapshots: dict[str, _CleanupFileSnapshot] = {}
        for item in plan["files"]:
            identity = item["identity"]
            snapshots[item["relative_path"]] = _CleanupFileSnapshot(
                size=item["size"],
                sha256=item["sha256"],
                device=identity["device"],
                inode=identity["inode"],
                mtime_ns=identity["mtime_ns"],
            )
        return snapshots

    @classmethod
    def _validate_abort_cleanup_plan_document(
        cls,
        value: Any,
        transaction_ref: str,
        authority: str,
    ) -> dict[str, Any]:
        """Validate the canonical, content-free proof for one aborted reserve."""

        expected_keys = {
            "abort_receipt_sha256",
            "candidate_cleanup_evidence_sha256",
            "cleanup_authority_sha256",
            "directories",
            "files",
            "operation",
            "reservation_sha256",
            "schema",
            "terminal_state",
            "transaction_logical_ref",
            "transaction_ref",
            "transaction_root_identity",
        }
        if (
            type(value) is not dict
            or set(value) != expected_keys
            or value.get("schema") != RESERVATION_ABORT_CLEANUP_PLAN_SCHEMA
            or value.get("operation") != "compact_terminal_reservation_abort"
            or value.get("terminal_state") != "aborted_before_intent_seal"
            or value.get("transaction_ref") != transaction_ref
            or value.get("transaction_logical_ref")
            != _transaction_logical_ref(transaction_ref)
            or value.get("cleanup_authority_sha256") != authority
            or value.get("directories") != []
            or type(value.get("files")) is not list
        ):
            raise _fail("project_update_transaction_cleanup_refused")
        _digest(
            value.get("abort_receipt_sha256"),
            code="project_update_transaction_cleanup_refused",
        )
        _digest(
            value.get("candidate_cleanup_evidence_sha256"),
            code="project_update_transaction_cleanup_refused",
        )
        _digest(
            value.get("cleanup_authority_sha256"),
            code="project_update_transaction_cleanup_refused",
        )
        _digest(
            value.get("reservation_sha256"),
            code="project_update_transaction_cleanup_refused",
        )
        root_identity = value.get("transaction_root_identity")
        birthtime_ns = (
            root_identity.get("birthtime_ns")
            if type(root_identity) is dict
            else None
        )
        if (
            type(root_identity) is not dict
            or set(root_identity) != {"birthtime_ns", "device", "inode"}
            or type(root_identity.get("device")) is not int
            or root_identity["device"] < 0
            or type(root_identity.get("inode")) is not int
            or root_identity["inode"] <= 0
            or (
                os.name == "nt"
                and (type(birthtime_ns) is not int or birthtime_ns <= 0)
            )
            or (os.name != "nt" and birthtime_ns is not None)
        ):
            raise _fail("project_update_transaction_cleanup_refused")

        expected_files = cls._abort_cleanup_expected_files()
        observed_files: list[str] = []
        for item in value["files"]:
            identity = item.get("identity") if type(item) is dict else None
            if (
                type(item) is not dict
                or set(item) != {"identity", "relative_path", "sha256", "size"}
                or type(item.get("relative_path")) is not str
                or type(item.get("size")) is not int
                or item["size"] < 0
                or item["size"] > MAX_DOCUMENT_BYTES + 1
                or type(identity) is not dict
                or set(identity) != {"device", "inode", "mtime_ns"}
                or type(identity.get("device")) is not int
                or identity["device"] < 0
                or type(identity.get("inode")) is not int
                or identity["inode"] <= 0
                or type(identity.get("mtime_ns")) is not int
                or identity["mtime_ns"] < 0
            ):
                raise _fail("project_update_transaction_cleanup_refused")
            _digest(
                item.get("sha256"),
                code="project_update_transaction_cleanup_refused",
            )
            observed_files.append(item["relative_path"])
        if tuple(observed_files) != expected_files:
            raise _fail("project_update_transaction_cleanup_refused")
        return value

    def _build_abort_cleanup_plan(
        self,
        authority: str,
        *,
        transaction_root_identity: tuple[int, int, int | None],
    ) -> dict[str, Any]:
        """Bind the exact five-file terminal history and its file identities."""

        if os.path.lexists(self._lock_path):
            raise _fail("project_update_transaction_cleanup_refused")
        terminal = self.inspect_abort_receipt()
        if terminal is None:
            raise _fail("project_update_transaction_cleanup_refused")
        files, directories = ProjectUpdateTransaction._cleanup_descendant_snapshot(
            self._transaction_root,
            exclude={RESERVATION_ABORT_CLEANUP_PLAN_NAME},
        )
        if directories or tuple(sorted(files)) != self._abort_cleanup_expected_files():
            raise _fail("project_update_transaction_cleanup_refused")
        if os.path.lexists(self._lock_path):
            raise _fail("project_update_transaction_cleanup_refused")
        plan = {
            "abort_receipt_sha256": terminal["receipt_sha256"],
            "candidate_cleanup_evidence_sha256": terminal[
                "candidate_cleanup_evidence_sha256"
            ],
            "cleanup_authority_sha256": authority,
            "directories": [],
            "files": [
                {
                    "identity": {
                        "device": snapshot.device,
                        "inode": snapshot.inode,
                        "mtime_ns": snapshot.mtime_ns,
                    },
                    "relative_path": relative,
                    "sha256": snapshot.sha256,
                    "size": snapshot.size,
                }
                for relative, snapshot in sorted(files.items())
            ],
            "operation": "compact_terminal_reservation_abort",
            "reservation_sha256": self.reservation.sha256,
            "schema": RESERVATION_ABORT_CLEANUP_PLAN_SCHEMA,
            "terminal_state": "aborted_before_intent_seal",
            "transaction_logical_ref": self.transaction_logical_ref,
            "transaction_ref": self.transaction_ref,
            "transaction_root_identity": {
                "birthtime_ns": transaction_root_identity[2],
                "device": transaction_root_identity[0],
                "inode": transaction_root_identity[1],
            },
        }
        return self._validate_abort_cleanup_plan_document(
            plan,
            self.transaction_ref,
            authority,
        )

    def exact_cleanup(self, *, cleanup_authority_sha256: str) -> bool:
        """Compact one exact pre-intent abort while retaining canonical proof."""

        # The exact compare-and-delete primitive is intentionally Windows-only.
        # Refuse before publishing a cleanup plan or moving the transaction
        # directory so POSIX resume remains genuinely read-only and fail-closed.
        if os.name != "nt":
            return False
        try:
            authority = _digest(
                cleanup_authority_sha256,
                code="project_update_transaction_cleanup_refused",
            )
            parent = self._transaction_root.parent
            _safe_existing_chain(parent, directory=True)
            tombstone, proof = self._abort_cleanup_paths(
                parent,
                self.transaction_ref,
            )
            if not os.path.lexists(self._transaction_root):
                if os.path.lexists(tombstone) or os.path.lexists(proof):
                    return self._resume_abort_cleanup_paths(
                        self._project_root,
                        self.transaction_ref,
                        authority,
                    )
                return False
            if (
                os.path.lexists(self._lock_path)
                or os.path.lexists(tombstone)
                or os.path.lexists(proof)
            ):
                return False
            root_before = _safe_directory(self._transaction_root, within=parent)
            root_identity = _cleanup_directory_identity(root_before)
            plan = self._build_abort_cleanup_plan(
                authority,
                transaction_root_identity=root_identity,
            )
            plan_bytes = _document_bytes(plan)
            plan_path = (
                self._transaction_root / RESERVATION_ABORT_CLEANUP_PLAN_NAME
            )
            if os.path.lexists(plan_path):
                existing, _existing_info = _read_cleanup_linked_regular(
                    self._project_root,
                    plan_path,
                    maximum=MAX_DOCUMENT_BYTES + 1,
                )
                if not hmac.compare_digest(existing, plan_bytes):
                    return False
            else:
                _write_new(plan_path, plan_bytes, within=self._transaction_root)
            _require_directory_durable(self._transaction_root)
            rebuilt = self._build_abort_cleanup_plan(
                authority,
                transaction_root_identity=root_identity,
            )
            root_after = _safe_directory(self._transaction_root, within=parent)
            if (
                _cleanup_directory_identity(root_after) != root_identity
                or os.path.lexists(self._lock_path)
                or not hmac.compare_digest(_document_bytes(rebuilt), plan_bytes)
                or not hmac.compare_digest(
                    _read_cleanup_linked_regular(
                        self._project_root,
                        plan_path,
                        maximum=MAX_DOCUMENT_BYTES + 1,
                    )[0],
                    plan_bytes,
                )
            ):
                return False
            try:
                _atomic_move_directory_no_replace(self._transaction_root, tombstone)
            except OSError:
                return False
            moved = _safe_directory(tombstone, within=parent)
            if (
                _cleanup_directory_identity(moved) != root_identity
                or os.path.lexists(self._lock_path)
                or not _fsync_directory(parent).durable
            ):
                return False
            return self._resume_abort_cleanup_paths(
                self._project_root,
                self.transaction_ref,
                authority,
            )
        except (OSError, ProjectUpdateTransactionError, KeyError, TypeError):
            return False

    @classmethod
    def resume_cleanup(
        cls,
        project_root: Path | str,
        transaction_ref: str,
        *,
        cleanup_authority_sha256: str,
    ) -> bool:
        """Resume only this primitive's identity-bound abort-history cleanup."""

        if os.name != "nt":
            return False
        try:
            project = _absolute(project_root)
            _safe_existing_chain(project, directory=True)
            ref = _transaction_ref(transaction_ref)
            authority = _digest(
                cleanup_authority_sha256,
                code="project_update_transaction_cleanup_refused",
            )
            return cls._resume_abort_cleanup_paths(project, ref, authority)
        except (OSError, ProjectUpdateTransactionError, KeyError, TypeError):
            return False

    @classmethod
    def _resume_abort_cleanup_paths(
        cls,
        project: Path,
        transaction_ref: str,
        authority: str,
    ) -> bool:
        parent = project / PurePosixPath(TRANSACTION_ROOT_LOGICAL)
        _safe_existing_chain(parent, directory=True)
        original = parent / transaction_ref
        tombstone, proof = cls._abort_cleanup_paths(parent, transaction_ref)
        lock_path = project / PurePosixPath(PROJECT_UPDATE_LOCK_LOGICAL)
        if os.path.lexists(lock_path) or os.path.lexists(original):
            return False

        if os.path.lexists(proof):
            proof_raw, proof_info = _read_cleanup_linked_regular(
                project,
                proof,
                maximum=MAX_DOCUMENT_BYTES + 1,
            )
            proof_identity = (int(proof_info.st_dev), int(proof_info.st_ino))
            plan = cls._validate_abort_cleanup_plan_document(
                _parse_document(
                    proof_raw,
                    code="project_update_transaction_cleanup_refused",
                ),
                transaction_ref,
                authority,
            )
            if os.path.lexists(tombstone):
                tombstone_info = _safe_directory(tombstone, within=parent)
                tombstone_generation = _cleanup_directory_identity(tombstone_info)
                if tombstone_generation != cls._abort_cleanup_root_identity(plan):
                    return False
                tombstone_snapshot = _CleanupDirectorySnapshot(
                    device=tombstone_generation[0],
                    inode=tombstone_generation[1],
                    birthtime_ns=tombstone_generation[2],
                )
                with _cleanup_bound_directory_context(project, tombstone):
                    bound = _safe_directory(tombstone, within=parent)
                    if (
                        _cleanup_directory_identity(bound) != tombstone_generation
                        or os.path.lexists(lock_path)
                    ):
                        return False
                    with os.scandir(tombstone) as entries:
                        names = tuple(sorted(entry.name for entry in entries))
                    if names:
                        if names != (RESERVATION_ABORT_CLEANUP_PLAN_NAME,):
                            return False
                        duplicate = (
                            tombstone / RESERVATION_ABORT_CLEANUP_PLAN_NAME
                        )
                        duplicate_raw, duplicate_info = (
                            _read_cleanup_linked_regular(
                                project,
                                duplicate,
                                maximum=MAX_DOCUMENT_BYTES + 1,
                            )
                        )
                        if (
                            not hmac.compare_digest(duplicate_raw, proof_raw)
                            or int(proof_info.st_nlink) != 2
                            or int(duplicate_info.st_nlink) != 2
                            or (
                                int(duplicate_info.st_dev),
                                int(duplicate_info.st_ino),
                            )
                            != proof_identity
                        ):
                            return False
                        _unlink_exact_cleanup_plan_duplicate_windows(
                            project,
                            duplicate,
                            proof,
                            expected_raw=proof_raw,
                            expected_identity=proof_identity,
                        )
                        if (
                            not _fsync_directory(parent).durable
                            or not _fsync_directory(tombstone).durable
                        ):
                            return False
                    elif int(proof_info.st_nlink) != 1:
                        return False
                    if os.path.lexists(lock_path):
                        return False
                _delete_exact_cleanup_directory(
                    project,
                    tombstone,
                    tombstone_snapshot,
                )
                if not _fsync_directory(parent).durable:
                    return False
            elif int(proof_info.st_nlink) != 1:
                return False
            if os.path.lexists(lock_path):
                return False
            final_raw, final_info = _read_cleanup_linked_regular(
                project,
                proof,
                maximum=MAX_DOCUMENT_BYTES + 1,
            )
            return (
                not os.path.lexists(original)
                and not os.path.lexists(tombstone)
                and hmac.compare_digest(final_raw, proof_raw)
                and int(final_info.st_nlink) == 1
                and (int(final_info.st_dev), int(final_info.st_ino))
                == proof_identity
            )

        if not os.path.lexists(tombstone):
            return False
        tombstone_info = _safe_directory(tombstone, within=parent)
        tombstone_generation = _cleanup_directory_identity(tombstone_info)
        tombstone_snapshot = _CleanupDirectorySnapshot(
            device=tombstone_generation[0],
            inode=tombstone_generation[1],
            birthtime_ns=tombstone_generation[2],
        )
        plan_path = tombstone / RESERVATION_ABORT_CLEANUP_PLAN_NAME
        with _cleanup_bound_directory_context(project, tombstone):
            bound = _safe_directory(tombstone, within=parent)
            if (
                _cleanup_directory_identity(bound) != tombstone_generation
                or os.path.lexists(lock_path)
                or not os.path.lexists(plan_path)
            ):
                return False
            plan_raw, plan_info = _read_cleanup_linked_regular(
                project,
                plan_path,
                maximum=MAX_DOCUMENT_BYTES + 1,
            )
            plan_identity = (int(plan_info.st_dev), int(plan_info.st_ino))
            plan = cls._validate_abort_cleanup_plan_document(
                _parse_document(
                    plan_raw,
                    code="project_update_transaction_cleanup_refused",
                ),
                transaction_ref,
                authority,
            )
            if cls._abort_cleanup_root_identity(plan) != tombstone_generation:
                return False
            expected_files = cls._abort_cleanup_file_snapshots(plan)
            actual_files, actual_directories = (
                ProjectUpdateTransaction._cleanup_descendant_snapshot(
                    tombstone,
                    exclude={RESERVATION_ABORT_CLEANUP_PLAN_NAME},
                )
            )
            if actual_directories or not set(actual_files).issubset(expected_files):
                return False
            if any(
                actual_files[relative] != expected_files[relative]
                for relative in actual_files
            ):
                return False
            for relative in sorted(actual_files):
                if os.path.lexists(lock_path):
                    return False
                _delete_exact_cleanup_file(
                    project,
                    tombstone / PurePosixPath(relative),
                    expected_files[relative],
                )
            remaining_files, remaining_directories = (
                ProjectUpdateTransaction._cleanup_descendant_snapshot(
                    tombstone,
                    exclude={RESERVATION_ABORT_CLEANUP_PLAN_NAME},
                )
            )
            if (
                remaining_files
                or remaining_directories
                or os.path.lexists(lock_path)
                or _cleanup_directory_identity(
                    _safe_directory(tombstone, within=parent)
                )
                != tombstone_generation
            ):
                return False
            try:
                _atomic_move_file_no_replace(plan_path, proof)
            except OSError:
                return False
            moved_raw, moved_info = _read_cleanup_linked_regular(
                project,
                proof,
                maximum=MAX_DOCUMENT_BYTES + 1,
            )
            if (
                not hmac.compare_digest(moved_raw, plan_raw)
                or int(moved_info.st_nlink) != 1
                or (int(moved_info.st_dev), int(moved_info.st_ino))
                != plan_identity
                or not _fsync_directory(parent).durable
                or not _fsync_directory(tombstone).durable
                or os.path.lexists(lock_path)
            ):
                return False
            if _cleanup_directory_identity(
                _safe_directory(tombstone, within=parent)
            ) != tombstone_generation:
                return False
            with os.scandir(tombstone) as entries:
                if next(entries, None) is not None:
                    return False
        _delete_exact_cleanup_directory(project, tombstone, tombstone_snapshot)
        if not _fsync_directory(parent).durable or os.path.lexists(lock_path):
            return False
        final_raw, final_info = _read_cleanup_linked_regular(
            project,
            proof,
            maximum=MAX_DOCUMENT_BYTES + 1,
        )
        return (
            not os.path.lexists(original)
            and not os.path.lexists(tombstone)
            and hmac.compare_digest(final_raw, plan_raw)
            and int(final_info.st_nlink) == 1
            and (int(final_info.st_dev), int(final_info.st_ino))
            == plan_identity
        )

    @staticmethod
    def _candidate_seal(
        raw: bytes,
        *,
        reservation: ProjectUpdateReservation,
        provider_inventory_sha256: str,
        tree: RuntimeCandidateTreeInventory,
    ) -> dict[str, Any]:
        value = _parse_document(raw, code="project_update_transaction_candidate_invalid")
        legacy_expected_keys = {
            "absolute_paths_echoed",
            "candidate_locator",
            "candidate_sha256",
            "existing_runtime_reusable",
            "inventory_bytes",
            "inventory_count",
            "inventory_sha256",
            "marker_free_final_postimage",
            "path_identities",
            "post_approval_child_process_allowed",
            "post_approval_copy_allowed",
            "post_approval_network_allowed",
            "receipt_sha256",
            "recursive_directory_durability_verified",
            "runtime_parent_existed_before",
            "same_volume_verified",
            "seal_parent_durability_required",
            "schema",
            "status",
            "supply_lock_sha256",
            "target_commit",
            "target_tag",
            "transaction_ref",
            "wheel_file_name",
            "wheel_sha256",
        }
        current_expected_keys = legacy_expected_keys | {
            "existing_runtime_repair_required",
            "existing_runtime_inventory_sha256",
            "existing_runtime_inventory_count",
            "existing_runtime_inventory_bytes",
        }
        legacy_shape = set(value) == legacy_expected_keys
        if (
            not legacy_shape
            and set(value) != current_expected_keys
        ) or (
            value.get("schema") != PROJECT_RUNTIME_CANDIDATE_SCHEMA
            or value.get("status") != "sealed"
            or value.get("target_tag") != reservation.requested_target_tag
            or value.get("transaction_ref") != reservation.transaction_ref
            or value.get("candidate_locator")
            != reservation.runtime_candidate_logical_ref
            or value.get("inventory_sha256") != provider_inventory_sha256
            or value.get("inventory_count") != tree.inventory_count
            or value.get("inventory_bytes") != tree.total_bytes
            or value.get("same_volume_verified") is not True
            or type(value.get("existing_runtime_reusable")) is not bool
            or (
                not legacy_shape
                and (
                    type(value.get("existing_runtime_repair_required"))
                    is not bool
                    or type(value.get("existing_runtime_inventory_count"))
                    is not int
                    or value.get("existing_runtime_inventory_count") < 0
                    or type(value.get("existing_runtime_inventory_bytes"))
                    is not int
                    or value.get("existing_runtime_inventory_bytes") < 0
                )
            )
            or type(value.get("runtime_parent_existed_before")) is not bool
            or value.get("recursive_directory_durability_verified") is not True
            or value.get("seal_parent_durability_required") is not True
            or value.get("marker_free_final_postimage") is not True
            or value.get("post_approval_child_process_allowed") is not False
            or value.get("post_approval_copy_allowed") is not False
            or value.get("post_approval_network_allowed") is not False
            or value.get("absolute_paths_echoed") is not False
            or type(value.get("target_commit")) is not str
            or re.fullmatch(r"[0-9a-f]{40,64}", value["target_commit"]) is None
            or type(value.get("wheel_file_name")) is not str
            or "/" in value["wheel_file_name"]
            or "\\" in value["wheel_file_name"]
        ):
            raise _fail("project_update_transaction_candidate_invalid")
        for field in (
            "candidate_sha256",
            "inventory_sha256",
            "receipt_sha256",
            "supply_lock_sha256",
            "wheel_sha256",
        ):
            _digest(value.get(field), code="project_update_transaction_candidate_invalid")
        repair_required = bool(
            False
            if legacy_shape
            else value["existing_runtime_repair_required"]
        )
        repair_inventory_sha256 = value.get(
            "existing_runtime_inventory_sha256"
        )
        if repair_required:
            _digest(
                repair_inventory_sha256,
                code="project_update_transaction_candidate_invalid",
            )
        elif (
            repair_inventory_sha256 is not None
            or (
                not legacy_shape
                and (
                    value["existing_runtime_inventory_count"] != 0
                    or value["existing_runtime_inventory_bytes"] != 0
                )
            )
        ):
            raise _fail("project_update_transaction_candidate_invalid")
        identities = value.get("path_identities")
        legacy_identity_keys = {
            "candidate_root",
            "project_root",
            "runtime_parent",
            "runtime_parent_created",
            "transaction_root",
        }
        identity_keys = (
            legacy_identity_keys
            if legacy_shape
            else legacy_identity_keys | {"existing_runtime_root"}
        )
        if type(identities) is not dict or set(identities) != identity_keys:
            raise _fail("project_update_transaction_candidate_invalid")

        def sealed_identity(item: Any) -> tuple[int, int] | None:
            if item is None:
                return None
            if (
                type(item) is not list
                or len(item) != 2
                or any(type(part) is not int or part < 0 for part in item)
            ):
                raise _fail("project_update_transaction_candidate_invalid")
            return int(item[0]), int(item[1])

        for key in identity_keys:
            sealed_identity(identities[key])
        if (
            identities["project_root"] is None
            or identities["transaction_root"] is None
            or identities["candidate_root"] is None
            or identities["runtime_parent"] is None
            or (
                not legacy_shape
                and repair_required
                != (identities["existing_runtime_root"] is not None)
            )
            or (
                value["runtime_parent_existed_before"]
                and identities["runtime_parent_created"] is not None
            )
            or (
                not value["runtime_parent_existed_before"]
                and identities["runtime_parent_created"]
                != identities["runtime_parent"]
            )
        ):
            raise _fail("project_update_transaction_candidate_invalid")
        return value

    def seal_intent(
        self,
        *,
        bindings: ProjectUpdateBindings,
        components: Sequence[ProjectUpdateComponent],
        preimages: Mapping[str, bytes],
        private_binding_blobs: Mapping[str, bytes],
        static_receipt_postimage: bytes,
        runtime_candidate_inventory_sha256: str,
        runtime_candidate_postimage_sha256: str,
        runtime_candidate_receipt_relative_path: str = RUNTIME_CANDIDATE_RECEIPT_NAME,
    ) -> "ProjectUpdateTransaction":
        """Seal exact bindings after the reserved candidate was built in place."""

        self._verify_reservation_backlink()
        provider_inventory = _digest(
            runtime_candidate_inventory_sha256,
            code="project_update_transaction_candidate_invalid",
        )
        postimage = _digest(
            runtime_candidate_postimage_sha256,
            code="project_update_transaction_candidate_invalid",
        )
        receipt_relative = _logical_path(runtime_candidate_receipt_relative_path)
        if (
            not isinstance(preimages, Mapping)
            or len(preimages) > MAX_PRIVATE_BLOBS
            or not isinstance(private_binding_blobs, Mapping)
            or not private_binding_blobs
            or len(private_binding_blobs) > MAX_PRIVATE_BLOBS
            or "git-runner-binding" not in private_binding_blobs
            or "static-receipt-postimage" in private_binding_blobs
            or "runtime-candidate-path-identities" in private_binding_blobs
            or type(static_receipt_postimage) is not bytes
            or len(static_receipt_postimage) > MAX_PRIVATE_BLOB_BYTES
        ):
            raise _fail("project_update_transaction_intent_invalid")
        for reserved_name in (
            "intent.json",
            "intent-seal.json",
            "preimages",
            PRIVATE_BINDINGS_NAME,
            SEALED_LOCK_BACKLINK_NAME,
            RESERVATION_ABORT_INTENT_NAME,
            RESERVATION_ABORT_RECEIPT_NAME,
        ):
            if os.path.lexists(self._transaction_root / reserved_name):
                raise _fail("project_update_transaction_exists")
        candidate = self.runtime_candidate_path
        seal_path = self.runtime_candidate_seal_path
        candidate_info = _safe_directory(candidate, within=self._transaction_root)
        transaction_info = _safe_directory(
            self._transaction_root, within=self._project_root
        )
        project_info = _safe_directory(
            self._project_root, within=self._project_root
        )
        if not (
            int(candidate_info.st_dev)
            == int(transaction_info.st_dev)
            == int(project_info.st_dev)
        ):
            raise _fail("project_update_transaction_candidate_invalid")
        tree = _runtime_candidate_tree_inventory(
            candidate, transaction_root=self._transaction_root
        )
        seal_raw = _read_regular(
            seal_path, within=self._transaction_root, maximum=MAX_DOCUMENT_BYTES + 1
        )
        seal = self._candidate_seal(
            seal_raw,
            reservation=self.reservation,
            provider_inventory_sha256=provider_inventory,
            tree=tree,
        )
        runtime_parent = self._project_root / PurePosixPath(RUNTIME_PARENT_LOGICAL)
        runtime_parent_info = _safe_directory(
            runtime_parent, within=self._project_root
        )
        actual_identities = {
            "candidate_root": [
                int(candidate_info.st_dev),
                int(candidate_info.st_ino),
            ],
            "project_root": [
                int(project_info.st_dev),
                int(project_info.st_ino),
            ],
            "runtime_parent": [
                int(runtime_parent_info.st_dev),
                int(runtime_parent_info.st_ino),
            ],
            "transaction_root": [
                int(transaction_info.st_dev),
                int(transaction_info.st_ino),
            ],
        }
        sealed_identities = seal["path_identities"]
        if any(
            sealed_identities[key] != expected
            for key, expected in actual_identities.items()
        ):
            raise _fail("project_update_transaction_candidate_invalid")
        receipt_path = candidate / PurePosixPath(receipt_relative)
        receipt_digest, _receipt_size, _receipt_info = _hash_regular_with_info(
            receipt_path, within=candidate
        )
        if receipt_digest != seal["receipt_sha256"]:
            raise _fail("project_update_transaction_candidate_invalid")

        private_values: dict[str, bytes] = {}
        preimage_records: list[PrivateBlobRecord] = []
        for key in sorted(preimages):
            value = preimages[key]
            if type(value) is not bytes or len(value) > MAX_PRIVATE_BLOB_BYTES:
                raise _fail("project_update_transaction_intent_invalid")
            record = _blob_record(key, value, root_name="preimages")
            preimage_records.append(record)
            private_values[record.relative_path] = value
        component_tuple = tuple(components)
        static_receipt_domain_plan_sha256, static_receipt_domain_target_binding_sha256 = (
            _validate_static_receipt_postimage(
                static_receipt_postimage, reservation=self.reservation
            )
        )
        receipt_components = [
            component for component in component_tuple if component.role == "receipt"
        ]
        runtime_components = [
            component for component in component_tuple if component.role == "runtime"
        ]
        if (
            len(receipt_components) != 1
            or sha256_bytes(static_receipt_postimage)
            != receipt_components[0].post_sha256
            or len(runtime_components) != 1
            or postimage != runtime_components[0].post_sha256
        ):
            raise _fail("project_update_transaction_intent_invalid")
        complete_private_bindings = dict(private_binding_blobs)
        complete_private_bindings["static-receipt-postimage"] = (
            static_receipt_postimage
        )
        complete_private_bindings["runtime-candidate-path-identities"] = (
            _document_bytes(
                {
                    "path_identities": sealed_identities,
                    "schema": RUNTIME_PATH_IDENTITIES_SCHEMA,
                }
            )
        )
        binding_records: list[PrivateBlobRecord] = []
        for key in sorted(complete_private_bindings):
            value = complete_private_bindings[key]
            if type(value) is not bytes or len(value) > MAX_PRIVATE_BLOB_BYTES:
                raise _fail("project_update_transaction_intent_invalid")
            record = _blob_record(key, value, root_name=PRIVATE_BINDINGS_NAME)
            binding_records.append(record)
            private_values[record.relative_path] = value
        candidate_binding = RuntimeCandidateBinding(
            logical_ref=self.reservation.runtime_candidate_logical_ref,
            seal_logical_ref=self.reservation.runtime_candidate_seal_logical_ref,
            recursive_tree_sha256=tree.recursive_tree_sha256,
            inventory_count=tree.inventory_count,
            file_count=tree.file_count,
            inventory_bytes=tree.total_bytes,
            provider_inventory_sha256=provider_inventory,
            provider_candidate_sha256=seal["candidate_sha256"],
            seal_sha256=sha256_bytes(seal_raw),
            path_identities_sha256=sha256_document(sealed_identities),
            receipt_relative_path=receipt_relative,
            receipt_sha256=receipt_digest,
            postimage_sha256=postimage,
            existing_runtime_reusable=seal["existing_runtime_reusable"],
            existing_runtime_repair_required=seal[
                "existing_runtime_repair_required"
            ],
            existing_runtime_inventory_sha256=seal[
                "existing_runtime_inventory_sha256"
            ],
            existing_runtime_inventory_count=seal[
                "existing_runtime_inventory_count"
            ],
            existing_runtime_inventory_bytes=seal[
                "existing_runtime_inventory_bytes"
            ],
            runtime_parent_existed_before=seal[
                "runtime_parent_existed_before"
            ],
            recursive_directory_durability_verified=True,
            seal_parent_durability_required=True,
            marker_free_final_postimage=True,
        )
        intent = ProjectUpdateIntent(
            transaction_ref=self.transaction_ref,
            transaction_logical_ref=self.transaction_logical_ref,
            project_identity_sha256=self.reservation.project_identity_sha256,
            requested_target_tag=self.reservation.requested_target_tag,
            bindings=bindings,
            components=component_tuple,
            logical_targets=tuple(
                sorted(component.logical_target for component in component_tuple)
            ),
            preimages=tuple(preimage_records),
            private_bindings=tuple(binding_records),
            runtime_candidate=candidate_binding,
            ownership_nonce=self.reservation.ownership_nonce,
            reservation_sha256=self.reservation.sha256,
            created_at=self.reservation.created_at,
            static_receipt_domain_plan_sha256=(
                static_receipt_domain_plan_sha256
            ),
            static_receipt_domain_target_binding_sha256=(
                static_receipt_domain_target_binding_sha256
            ),
        )
        for name in ("preimages", PRIVATE_BINDINGS_NAME):
            try:
                (self._transaction_root / name).mkdir(mode=0o700)
            except OSError:
                raise _fail("project_update_transaction_path_unsafe") from None
            _safe_directory(self._transaction_root / name, within=self._transaction_root)
        for relative, value in sorted(private_values.items()):
            _write_new(
                self._transaction_root / PurePosixPath(relative),
                value,
                within=self._transaction_root,
            )
        _write_new(
            self._transaction_root / "intent.json",
            _document_bytes(intent.document()),
            within=self._transaction_root,
        )
        # Detect candidate drift across all private/control writes before the
        # immutable final seal marker is created.
        tree_after = _runtime_candidate_tree_inventory(
            candidate, transaction_root=self._transaction_root
        )
        seal_after = _read_regular(
            seal_path, within=self._transaction_root, maximum=MAX_DOCUMENT_BYTES + 1
        )
        if tree_after != tree or not hmac.compare_digest(seal_after, seal_raw):
            raise _fail("project_update_transaction_candidate_invalid")
        intent_seal = {
            "intent_sha256": intent.sha256,
            "preimages_inventory_sha256": sha256_document(
                {"records": [record.document() for record in preimage_records]}
            ),
            "private_bindings_inventory_sha256": sha256_document(
                {"records": [record.document() for record in binding_records]}
            ),
            "reservation_sha256": self.reservation.sha256,
            "runtime_candidate_provider_inventory_sha256": provider_inventory,
            "runtime_candidate_provider_candidate_sha256": (
                candidate_binding.provider_candidate_sha256
            ),
            "runtime_candidate_path_identities_sha256": (
                candidate_binding.path_identities_sha256
            ),
            "runtime_candidate_recursive_tree_sha256": tree.recursive_tree_sha256,
            "runtime_candidate_seal_sha256": sha256_bytes(seal_raw),
            "schema": INTENT_SEAL_SCHEMA,
            "transaction_ref": self.transaction_ref,
        }
        _require_directory_durable(self._transaction_root / "preimages")
        _require_directory_durable(self._transaction_root / PRIVATE_BINDINGS_NAME)
        _write_new(
            self._transaction_root / "intent-seal.json",
            _document_bytes(intent_seal),
            within=self._transaction_root,
        )
        _require_directory_durable(self._transaction_root)
        return ProjectUpdateTransaction.open(self._project_root, self.transaction_ref)


class ProjectUpdateTransaction:
    """Immutable intent and a monotonic, live-lock-bound checkpoint chain."""

    def __init__(
        self,
        project: Path,
        root: Path,
        reservation: ProjectUpdateReservation,
        intent: ProjectUpdateIntent,
    ) -> None:
        self._project_root = project
        self._transaction_root = root
        self.reservation = reservation
        self.intent = intent
        self._cleanup_completed = False

    @property
    def transaction_ref(self) -> str:
        return self.intent.transaction_ref

    @property
    def transaction_logical_ref(self) -> str:
        return self.intent.transaction_logical_ref

    @property
    def _lock_path(self) -> Path:
        path = self._project_root / PurePosixPath(PROJECT_UPDATE_LOCK_LOGICAL)
        _within(path, self._project_root)
        return path

    @property
    def transaction_root(self) -> Path:
        return self._transaction_root

    @property
    def runtime_candidate_path(self) -> Path:
        path = self._transaction_root / RUNTIME_CANDIDATE_NAME
        _within(path, self._transaction_root)
        return path

    @classmethod
    def reserve(
        cls,
        project_root: Path | str,
        *,
        project_identity_sha256: str,
        requested_target_tag: str,
        transaction_ref: str | None = None,
        ownership_nonce: str | None = None,
        created_at: str = "1970-01-01T00:00:00Z",
    ) -> ReservedProjectUpdateTransaction:
        return ReservedProjectUpdateTransaction.reserve(
            project_root,
            project_identity_sha256=project_identity_sha256,
            requested_target_tag=requested_target_tag,
            transaction_ref=transaction_ref,
            ownership_nonce=ownership_nonce,
            created_at=created_at,
        )

    @classmethod
    def create(
        cls,
        project_root: Path | str,
        *,
        project_identity_sha256: str,
        requested_target_tag: str,
        bindings: ProjectUpdateBindings,
        components: Sequence[ProjectUpdateComponent],
        preimages: Mapping[str, bytes],
        runtime_bundle: Mapping[str, bytes],
        static_receipt_postimage: bytes,
        transaction_ref: str | None = None,
        ownership_nonce: str | None = None,
        lock_observation: LockObservation | None = None,
        created_at: str = "1970-01-01T00:00:00Z",
    ) -> "ProjectUpdateTransaction":
        """Test/small-input convenience wrapper around reserve/build/seal."""

        component_tuple = tuple(components)
        if (
            not component_tuple
            or len(component_tuple) > MAX_COMPONENTS
            or tuple(component.sequence for component in component_tuple)
            != tuple(range(1, len(component_tuple) + 1))
            or len({component.component_ref for component in component_tuple})
            != len(component_tuple)
            or [COMPONENT_ROLES.index(component.role) for component in component_tuple]
            != sorted(COMPONENT_ROLES.index(component.role) for component in component_tuple)
            or component_tuple[-1].role != "active_pin"
        ):
            raise _fail("project_update_transaction_intent_invalid")
        for role in {"source", "runtime", "launcher", "receipt", "active_pin"}:
            if sum(component.role == role for component in component_tuple) != 1:
                raise _fail("project_update_transaction_intent_invalid")
        if (
            not isinstance(preimages, Mapping)
            or len(preimages) > MAX_PRIVATE_BLOBS
            or not isinstance(runtime_bundle, Mapping)
            or not runtime_bundle
            or len(runtime_bundle) > MAX_PRIVATE_BLOBS
        ):
            raise _fail("project_update_transaction_intent_invalid")
        for key in sorted(preimages):
            value = preimages[key]
            _private_key(key)
            if (
                type(value) is not bytes
                or len(value) > MAX_PRIVATE_BLOB_BYTES
                or not any(
                    component.preimage_key == key
                    and component.pre_sha256 == sha256_bytes(value)
                    for component in component_tuple
                )
            ):
                raise _fail("project_update_transaction_intent_invalid")
        for key in sorted(runtime_bundle):
            value = runtime_bundle[key]
            _private_key(key)
            if type(value) is not bytes or len(value) > MAX_PRIVATE_BLOB_BYTES:
                raise _fail("project_update_transaction_intent_invalid")
        if type(static_receipt_postimage) is not bytes:
            raise _fail("project_update_transaction_intent_invalid")
        expected_preimages = {
            component.preimage_key
            for component in component_tuple
            if component.preimage_key is not None
        }
        if set(preimages) != expected_preimages:
            raise _fail("project_update_transaction_intent_invalid")

        reserved = cls.reserve(
            project_root,
            project_identity_sha256=project_identity_sha256,
            requested_target_tag=requested_target_tag,
            transaction_ref=transaction_ref,
            ownership_nonce=ownership_nonce,
            created_at=created_at,
        )
        lock_bytes = reserved.acquire_lock(observation=lock_observation)
        runtime_parent = reserved._project_root / PurePosixPath(
            RUNTIME_PARENT_LOGICAL
        )
        runtime_parent_existed_before = os.path.lexists(runtime_parent)
        _mkdirs(reserved._project_root, RUNTIME_PARENT_LOGICAL)
        candidate = reserved.runtime_candidate_path
        try:
            candidate.mkdir(mode=0o700)
            (candidate / "artifacts").mkdir(mode=0o700)
        except OSError:
            raise _fail("project_update_transaction_path_unsafe") from None
        for key in sorted(runtime_bundle):
            name = hashlib.sha256(key.encode("ascii")).hexdigest() + ".bin"
            _write_new(
                candidate / "artifacts" / name,
                runtime_bundle[key],
                within=candidate,
            )
        runtime_component = next(
            component for component in component_tuple if component.role == "runtime"
        )
        receipt = {
            "installed_payload_sha256": runtime_component.post_sha256,
            "schema": "wom-kit/project-update-synthetic-runtime-receipt/v0.4.3",
            "transaction_ref": reserved.transaction_ref,
        }
        receipt_bytes = _document_bytes(receipt)
        _write_new(
            candidate / RUNTIME_CANDIDATE_RECEIPT_NAME,
            receipt_bytes,
            within=candidate,
        )
        _require_directory_durable(candidate / "artifacts")
        _require_directory_durable(candidate)
        tree = _runtime_candidate_tree_inventory(
            candidate, transaction_root=reserved.transaction_root
        )
        first_bundle = runtime_bundle[sorted(runtime_bundle)[0]]
        provider_inventory = tree.recursive_tree_sha256
        candidate_sha256 = sha256_document(
            {
                "inventory_sha256": provider_inventory,
                "runtime_postimage_sha256": runtime_component.post_sha256,
                "schema": "wom-kit/project-update-synthetic-candidate-binding/v0.4.3",
            }
        )
        project_info = _safe_directory(
            reserved._project_root, within=reserved._project_root
        )
        transaction_info = _safe_directory(
            reserved.transaction_root, within=reserved._project_root
        )
        candidate_info = _safe_directory(
            candidate, within=reserved.transaction_root
        )
        runtime_parent_info = _safe_directory(
            runtime_parent, within=reserved._project_root
        )
        runtime_parent_identity = [
            int(runtime_parent_info.st_dev),
            int(runtime_parent_info.st_ino),
        ]
        candidate_seal = {
            "absolute_paths_echoed": False,
            "candidate_locator": reserved.reservation.runtime_candidate_logical_ref,
            "candidate_sha256": candidate_sha256,
            "existing_runtime_reusable": False,
            "existing_runtime_repair_required": False,
            "existing_runtime_inventory_sha256": None,
            "existing_runtime_inventory_count": 0,
            "existing_runtime_inventory_bytes": 0,
            "inventory_bytes": tree.total_bytes,
            "inventory_count": tree.inventory_count,
            "inventory_sha256": provider_inventory,
            "marker_free_final_postimage": True,
            "path_identities": {
                "candidate_root": [
                    int(candidate_info.st_dev),
                    int(candidate_info.st_ino),
                ],
                "project_root": [
                    int(project_info.st_dev),
                    int(project_info.st_ino),
                ],
                "runtime_parent": runtime_parent_identity,
                "runtime_parent_created": (
                    None
                    if runtime_parent_existed_before
                    else runtime_parent_identity
                ),
                "transaction_root": [
                    int(transaction_info.st_dev),
                    int(transaction_info.st_ino),
                ],
                "existing_runtime_root": None,
            },
            "post_approval_child_process_allowed": False,
            "post_approval_copy_allowed": False,
            "post_approval_network_allowed": False,
            "receipt_sha256": sha256_bytes(receipt_bytes),
            "recursive_directory_durability_verified": True,
            "runtime_parent_existed_before": runtime_parent_existed_before,
            "same_volume_verified": True,
            "seal_parent_durability_required": True,
            "schema": "wom-kit/project-runtime-candidate/v0.1",
            "status": "sealed",
            "supply_lock_sha256": bindings.bundle_sha256,
            "target_commit": "0" * 40,
            "target_tag": requested_target_tag,
            "transaction_ref": reserved.transaction_ref,
            "wheel_file_name": "synthetic-runtime.whl",
            "wheel_sha256": sha256_bytes(first_bundle),
        }
        _write_new(
            reserved.runtime_candidate_seal_path,
            _document_bytes(candidate_seal),
            within=reserved.transaction_root,
        )
        _require_directory_durable(reserved.transaction_root)
        sealed = reserved.seal_intent(
            bindings=bindings,
            components=component_tuple,
            preimages=preimages,
            private_binding_blobs={
                "git-runner-binding": _document_bytes(
                    {
                        "binding_sha256": bindings.bundle_sha256,
                        "schema": "wom-kit/project-update-synthetic-git-runner-binding/v0.4.3",
                    }
                )
            },
            static_receipt_postimage=static_receipt_postimage,
            runtime_candidate_inventory_sha256=provider_inventory,
            runtime_candidate_postimage_sha256=runtime_component.post_sha256,
        )
        sealed.bind_sealed_intent_to_lock(lock_bytes)
        return sealed

    @classmethod
    def open(
        cls,
        project_root: Path | str,
        transaction_ref: str,
        *,
        verify_candidate_content: bool = True,
    ) -> "ProjectUpdateTransaction":
        if type(verify_candidate_content) is not bool:
            raise _fail("project_update_transaction_invalid")
        project = _absolute(project_root)
        _safe_existing_chain(project, directory=True)
        ref = _transaction_ref(transaction_ref)
        root = project / PurePosixPath(TRANSACTION_ROOT_LOGICAL) / ref
        _within(root, project)
        if not os.path.lexists(root):
            raise _fail("project_update_transaction_not_found")
        _safe_existing_chain(root, directory=True)
        temporary = cls.__new__(cls)
        temporary._project_root = project
        temporary._transaction_root = root
        temporary._cleanup_completed = False
        reservation = ReservedProjectUpdateTransaction.open(project, ref).reservation
        temporary.reservation = reservation
        intent, _journal, _backlink, _cleanup = temporary._load_exact_state(
            verify_candidate_content=verify_candidate_content
        )
        temporary.intent = intent
        return temporary

    def lock_document(self, *, observation: LockObservation | None = None) -> dict[str, Any]:
        return build_lock_document(self.intent, observation=observation)

    def lock_bytes(self, *, observation: LockObservation | None = None) -> bytes:
        return lock_document_bytes(self.lock_document(observation=observation))

    def runtime_bundle_path(self, logical_key: str) -> Path:
        """Compatibility locator for the create() wrapper's synthetic artifacts."""

        validated = _private_key(logical_key)
        path = (
            self.runtime_candidate_path
            / "artifacts"
            / (hashlib.sha256(validated.encode("ascii")).hexdigest() + ".bin")
        )
        if not os.path.lexists(path):
            raise _fail("project_update_transaction_intent_invalid")
        _safe_regular(path, within=self.runtime_candidate_path)
        return path

    def private_binding_bytes(self, logical_key: str) -> bytes:
        """Read one intent-bound private integration blob exactly."""

        validated = _private_key(logical_key)
        intent, journal, _backlink, cleanup = self._load_exact_state()
        cleanup_is_exact_terminal = (
            cleanup is not None
            and journal.state == "exact"
            and bool(journal.verified_prefix)
            and journal.verified_prefix[-1].phase == "completed"
            and not _next_events(journal.verified_prefix, intent)
        )
        if journal.state != "exact" or (
            cleanup is not None and not cleanup_is_exact_terminal
        ):
            raise _fail("project_update_transaction_intent_invalid")
        matches = [
            record
            for record in intent.private_bindings
            if record.logical_key == validated
        ]
        if len(matches) != 1:
            raise _fail("project_update_transaction_intent_invalid")
        record = matches[0]
        value = _read_regular(
            self._transaction_root / PurePosixPath(record.relative_path),
            within=self._transaction_root,
            maximum=MAX_PRIVATE_BLOB_BYTES,
        )
        if len(value) != record.size or sha256_bytes(value) != record.sha256:
            raise _fail("project_update_transaction_intent_invalid")
        return value

    def candidate_cleanup_plan_sha256(self) -> str:
        """Return the deterministic operation plan bound before cleanup."""

        return sha256_document(
            {
                "intent_sha256": self.intent.sha256,
                "operation": "remove_sealed_runtime_candidate",
                "reservation_sha256": self.intent.reservation_sha256,
                "runtime_candidate_binding_sha256": (
                    _runtime_candidate_binding_sha256(self.intent)
                ),
                "runtime_parent_existed_before": (
                    self.intent.runtime_candidate.runtime_parent_existed_before
                ),
                "schema": CANDIDATE_CLEANUP_PLAN_SCHEMA,
                "transaction_ref": self.intent.transaction_ref,
            }
        )

    def _runtime_parent_restoration_observation_sha256(self) -> str:
        raw = self.private_binding_bytes("runtime-candidate-path-identities")
        value = _parse_document(
            raw, code="project_update_transaction_candidate_invalid"
        )
        identities = value.get("path_identities")
        if (
            set(value) != {"path_identities", "schema"}
            or value.get("schema") != RUNTIME_PATH_IDENTITIES_SCHEMA
            or type(identities) is not dict
            or sha256_document(identities)
            != self.intent.runtime_candidate.path_identities_sha256
        ):
            raise _fail("project_update_transaction_candidate_invalid")
        runtime_parent = self._project_root / PurePosixPath(RUNTIME_PARENT_LOGICAL)
        expected_identity = identities.get("runtime_parent")
        if self.intent.runtime_candidate.runtime_parent_existed_before:
            info = _safe_directory(runtime_parent, within=self._project_root)
            actual_identity = [int(info.st_dev), int(info.st_ino)]
            if actual_identity != expected_identity:
                raise _fail("project_update_transaction_candidate_invalid")
            state = "preserved_exact"
            identity_sha256: str | None = sha256_document(expected_identity)
        else:
            if os.path.lexists(runtime_parent):
                raise _fail("project_update_transaction_candidate_invalid")
            state = "restored_absent"
            identity_sha256 = None
        return sha256_document(
            {
                "runtime_parent_identity_sha256": identity_sha256,
                "runtime_parent_logical_ref": RUNTIME_PARENT_LOGICAL,
                "schema": RUNTIME_PARENT_RESTORATION_SCHEMA,
                "state": state,
                "transaction_ref": self.intent.transaction_ref,
            }
        )

    def candidate_cleanup_receipt_sha256(self) -> str:
        """Reproduce exact cleanup evidence from live post-cleanup state."""

        binding = _runtime_candidate_binding_sha256(self.intent)
        absence = _candidate_absence_observation(
            self._transaction_root,
            transaction_ref=self.intent.transaction_ref,
            reservation_sha256=self.intent.reservation_sha256,
            intent_sha256=self.intent.sha256,
            runtime_candidate_binding_sha256=binding,
        )
        restoration = self._runtime_parent_restoration_observation_sha256()
        return sha256_document(
            {
                "candidate_absence_observation_sha256": absence,
                "cleanup_plan_sha256": self.candidate_cleanup_plan_sha256(),
                "runtime_parent_restoration_observation_sha256": restoration,
                "schema": CANDIDATE_CLEANUP_RECEIPT_SCHEMA,
                "transaction_ref": self.intent.transaction_ref,
            }
        )

    def _present_lock_observation(
        self, backlink: Mapping[str, Any] | None = None
    ) -> tuple[str, bytes, dict[str, int]]:
        parent = self._lock_path.parent
        _safe_existing_chain(parent, directory=True)
        raw, lock_info = _read_regular_with_info(
            self._lock_path,
            within=self._project_root,
            maximum=MAX_DOCUMENT_BYTES + 1,
        )
        _parse_lock_bytes(raw, intent=self.intent)
        identity = _identity_document(lock_info)
        if backlink is not None and (
            backlink.get("lock_sha256") != sha256_bytes(raw)
            or backlink.get("lock_identity") != identity
        ):
            raise _fail("project_update_transaction_lock_invalid")
        observation = {
            "lock_identity": identity,
            "lock_logical_ref": PROJECT_UPDATE_LOCK_LOGICAL,
            "lock_sha256": sha256_bytes(raw),
            "schema": LOCK_OBSERVATION_SCHEMA,
            "state": "present",
            "transaction_ref": self.intent.transaction_ref,
        }
        observation_sha256 = sha256_document(observation)
        if (
            backlink is not None
            and backlink.get("live_lock_observation_sha256")
            != observation_sha256
        ):
            raise _fail("project_update_transaction_lock_invalid")
        return observation_sha256, raw, identity

    def _absent_lock_observation(self, backlink: Mapping[str, Any]) -> str:
        parent = self._lock_path.parent
        _safe_existing_chain(parent, directory=True)
        if os.path.lexists(self._lock_path):
            raise _fail("project_update_transaction_lock_invalid")
        parent_info = _safe_directory(parent, within=self._project_root)
        observation = {
            "lock_logical_ref": PROJECT_UPDATE_LOCK_LOGICAL,
            "prior_lock_sha256": backlink["lock_sha256"],
            "schema": LOCK_OBSERVATION_SCHEMA,
            "state": "absent",
            "transaction_ref": self.intent.transaction_ref,
            "verified_parent_identity": {
                "device": int(parent_info.st_dev),
                "inode": int(parent_info.st_ino),
            },
        }
        return sha256_document(observation)

    def bind_sealed_intent_to_lock(self, expected_lock_bytes: bytes) -> None:
        _parse_lock_bytes(expected_lock_bytes, intent=self.intent)
        reserved = ReservedProjectUpdateTransaction(
            self._project_root, self._transaction_root, self.reservation
        )
        reservation_backlink = reserved._verify_reservation_backlink(
            expected_lock_bytes
        )
        observed_sha, actual, identity = self._present_lock_observation()
        if not hmac.compare_digest(actual, expected_lock_bytes):
            raise _fail("project_update_transaction_lock_invalid")
        backlink = {
            "intent_sha256": self.intent.sha256,
            "live_lock_observation_sha256": observed_sha,
            "lock_identity": identity,
            "lock_sha256": sha256_bytes(actual),
            "ownership_nonce": self.intent.ownership_nonce,
            "project_identity_sha256": self.intent.project_identity_sha256,
            "reservation_lock_backlink_sha256": sha256_document(
                reservation_backlink
            ),
            "reservation_sha256": self.intent.reservation_sha256,
            "schema": LOCK_BACKLINK_SCHEMA,
            "transaction_logical_ref": self.intent.transaction_logical_ref,
            "transaction_ref": self.intent.transaction_ref,
        }
        path = self._transaction_root / SEALED_LOCK_BACKLINK_NAME
        expected = _document_bytes(backlink)
        if os.path.lexists(path):
            if hmac.compare_digest(_read_regular(path, within=self._transaction_root), expected):
                return
            raise _fail("project_update_transaction_lock_invalid")
        _write_new(path, expected, within=self._transaction_root)
        _require_directory_durable(self._transaction_root)
        self._load_exact_state()

    bind_lock_backlink = bind_sealed_intent_to_lock

    def classify_live_components(self, live_sha256: Mapping[str, str]) -> ComponentClassification:
        expectations = tuple(
            ComponentExpectation(
                component.component_ref,
                component.pre_sha256,
                component.post_sha256,
            )
            for component in self.intent.components
        )
        return classify_components(expectations, live_sha256)

    @staticmethod
    def _state_map(classification: ComponentClassification) -> dict[str, str]:
        return dict(classification.component_states)

    def _validate_live_for_event(
        self,
        event: _Event,
        checkpoints: Sequence[ProjectUpdateCheckpoint],
        classification: ComponentClassification,
    ) -> None:
        states = self._state_map(classification)
        if classification.overall == "unknown":
            raise _fail("project_update_transaction_state_transition_invalid")

        def exact(component: ProjectUpdateComponent, side: str) -> bool:
            state = states[component.component_ref]
            return state == "pre_and_post_exact" or state == f"{side}_exact"

        rollback_active = any(item.phase == "rollback_authorized" for item in checkpoints)
        cancellation_active = event.phase.startswith("preapproval_cancel") or any(
            item.phase.startswith("preapproval_cancel") for item in checkpoints
        )
        if cancellation_active:
            if not all(exact(component, "pre") for component in self.intent.components):
                raise _fail("project_update_transaction_state_transition_invalid")
            return
        if event.phase == "rollback_authorized":
            return
        if rollback_active or event.phase in {"rollback_effect", "rollback_verified"}:
            processed = {
                item.component_ref
                for item in checkpoints
                if item.phase == "rollback_effect" and item.stage == "verified"
            }
            if event.phase == "rollback_effect" and event.component_ref is not None:
                component = next(
                    item
                    for item in self.intent.components
                    if item.component_ref == event.component_ref
                )
                if event.stage == "verified" and not exact(component, "pre"):
                    raise _fail("project_update_transaction_state_transition_invalid")
                processed.add(component.component_ref if event.stage == "verified" else "")
            for component in self.intent.components:
                if component.component_ref in processed and not exact(component, "pre"):
                    raise _fail("project_update_transaction_state_transition_invalid")
            if event.phase in {
                "rollback_verified",
                "claim_succeeded",
                "ready_to_unlock",
                "lock_released",
                "completed",
            }:
                if not all(exact(component, "pre") for component in self.intent.components):
                    raise _fail("project_update_transaction_state_transition_invalid")
            return

        if event.phase in {"lock_backlinked", "approval_bound"}:
            if not all(exact(component, "pre") for component in self.intent.components):
                raise _fail("project_update_transaction_state_transition_invalid")
            return
        if event.phase in COMPONENT_ROLES and event.component_ref is not None:
            target = next(
                item
                for item in self.intent.components
                if item.component_ref == event.component_ref
            )
            for component in self.intent.components:
                if component.sequence < target.sequence:
                    required = "post"
                elif component.sequence > target.sequence:
                    required = "pre"
                else:
                    required = "pre" if event.stage == "intent" else "post"
                if not exact(component, required):
                    raise _fail("project_update_transaction_state_transition_invalid")
            return
        if event.phase in {
            "domain_committed",
            "claim_succeeded",
            "ready_to_unlock",
            "lock_released",
            "completed",
        }:
            if not all(exact(component, "post") for component in self.intent.components):
                raise _fail("project_update_transaction_state_transition_invalid")

    def _authority_for_append(
        self,
        event: _Event,
        checkpoints: Sequence[ProjectUpdateCheckpoint],
        approval_reference_sha256: str | None,
        approval_mac_sha256: str | None,
        claim_receipt_sha256: str | None,
        claim_mac_sha256: str | None,
    ) -> tuple[str | None, str | None, str | None, str | None]:
        authority = event.authority
        if authority in {"cancel_intent", "cancel_verified"}:
            if any(
                value is not None
                for value in (
                    approval_reference_sha256,
                    approval_mac_sha256,
                    claim_receipt_sha256,
                    claim_mac_sha256,
                )
            ):
                raise _fail("project_update_transaction_state_transition_invalid")
            return None, None, None, None
        if authority == "none":
            if any(
                value is not None
                for value in (
                    approval_reference_sha256,
                    approval_mac_sha256,
                    claim_receipt_sha256,
                    claim_mac_sha256,
                )
            ):
                raise _fail("project_update_transaction_state_transition_invalid")
            return None, None, None, None
        if authority in {"main_new", "rollback_new"}:
            approval_ref = _digest(
                approval_reference_sha256,
                code="project_update_transaction_state_transition_invalid",
            )
            approval_mac = _digest(
                approval_mac_sha256,
                code="project_update_transaction_state_transition_invalid",
            )
            if authority == "rollback_new":
                main = _authority_values(checkpoints, "main")
                if main is None or (approval_ref, approval_mac) == main:
                    raise _fail("project_update_transaction_state_transition_invalid")
            if claim_receipt_sha256 is not None or claim_mac_sha256 is not None:
                raise _fail("project_update_transaction_state_transition_invalid")
            return approval_ref, approval_mac, None, None
        authority_name = "rollback" if "rollback" in authority else "main"
        active = _authority_values(checkpoints, authority_name)
        if active is None:
            raise _fail("project_update_transaction_state_transition_invalid")
        if approval_reference_sha256 is not None and approval_reference_sha256 != active[0]:
            raise _fail("project_update_transaction_state_transition_invalid")
        if approval_mac_sha256 is not None and approval_mac_sha256 != active[1]:
            raise _fail("project_update_transaction_state_transition_invalid")
        if authority.startswith("claim_"):
            claim_receipt = _digest(
                claim_receipt_sha256,
                code="project_update_transaction_state_transition_invalid",
            )
            claim_mac = _digest(
                claim_mac_sha256,
                code="project_update_transaction_state_transition_invalid",
            )
            return active[0], active[1], claim_receipt, claim_mac
        if authority.startswith("final_"):
            claim = _claim_values(checkpoints, authority_name)
            if claim is None:
                raise _fail("project_update_transaction_state_transition_invalid")
            if claim_receipt_sha256 is not None and claim_receipt_sha256 != claim[0]:
                raise _fail("project_update_transaction_state_transition_invalid")
            if claim_mac_sha256 is not None and claim_mac_sha256 != claim[1]:
                raise _fail("project_update_transaction_state_transition_invalid")
            return active[0], active[1], claim[0], claim[1]
        if claim_receipt_sha256 is not None or claim_mac_sha256 is not None:
            raise _fail("project_update_transaction_state_transition_invalid")
        return active[0], active[1], None, None

    def _append_guard_held(
        self,
        *,
        phase: str,
        stage: CheckpointStage,
        live_component_sha256: Mapping[str, str],
        component_ref: str | None = None,
        approval_reference_sha256: str | None = None,
        approval_mac_sha256: str | None = None,
        claim_receipt_sha256: str | None = None,
        claim_mac_sha256: str | None = None,
        claim_evidence: Mapping[str, str] | None = None,
        cancellation_plan_sha256: str | None = None,
        candidate_cleanup_receipt_sha256: str | None = None,
        candidate_absence_observation_sha256: str | None = None,
        lock_release_result: LockReleaseResult | None = None,
    ) -> ProjectUpdateCheckpoint:
        if phase not in ALLOWED_CHECKPOINT_PHASES or stage not in {"intent", "verified"}:
            raise _fail("project_update_transaction_checkpoint_invalid")

        def perform() -> ProjectUpdateCheckpoint:
            intent, journal, backlink, cleanup = self._load_exact_state(
                guard_locked=True,
                verify_candidate_content=(
                    (phase == "runtime" and stage == "intent")
                    or phase == "preapproval_cancel_requested"
                ),
            )
            if cleanup is not None:
                raise _fail("project_update_transaction_cleanup_refused")
            if backlink is None:
                raise _fail("project_update_transaction_lock_invalid")
            if journal.state != "exact":
                raise _fail("project_update_transaction_journal_degraded")
            checkpoints = journal.verified_prefix
            events = _next_events(checkpoints, intent)
            matches = [
                event
                for event in events
                if (event.phase, event.stage, event.component_ref)
                == (phase, stage, component_ref)
            ]
            if len(matches) != 1:
                raise _fail("project_update_transaction_state_transition_invalid")
            event = matches[0]
            classification = self.classify_live_components(live_component_sha256)
            self._validate_live_for_event(event, checkpoints, classification)
            approval_ref, approval_mac, claim_receipt, claim_mac = self._authority_for_append(
                event,
                checkpoints,
                approval_reference_sha256,
                approval_mac_sha256,
                claim_receipt_sha256,
                claim_mac_sha256,
            )
            if phase == "claim_succeeded":
                evidence = _claim_evidence_digests(
                    claim_evidence,
                    intent=intent,
                    approval_reference_sha256=approval_ref,
                    claim_receipt_sha256=claim_receipt,
                    claim_mac_sha256=claim_mac,
                )
            else:
                if claim_evidence is not None:
                    raise _fail("project_update_transaction_state_transition_invalid")
                evidence = ()
            cancel_plan: str | None = None
            candidate_binding: str | None = None
            cleanup_receipt: str | None = None
            candidate_absence: str | None = None
            if event.authority == "cancel_intent":
                cancel_plan = _digest(
                    cancellation_plan_sha256,
                    code="project_update_transaction_state_transition_invalid",
                )
                if (
                    candidate_cleanup_receipt_sha256 is not None
                    or candidate_absence_observation_sha256 is not None
                ):
                    raise _fail("project_update_transaction_state_transition_invalid")
                candidate_binding = _runtime_candidate_binding_sha256(intent)
            elif event.authority == "cancel_verified":
                cancel_plan = _digest(
                    cancellation_plan_sha256,
                    code="project_update_transaction_state_transition_invalid",
                )
                requested = checkpoints[-1] if checkpoints else None
                if (
                    requested is None
                    or requested.phase != "preapproval_cancel_requested"
                    or requested.cancellation_plan_sha256 != cancel_plan
                    or requested.runtime_candidate_binding_sha256
                    != _runtime_candidate_binding_sha256(intent)
                ):
                    raise _fail("project_update_transaction_state_transition_invalid")
                candidate_binding = requested.runtime_candidate_binding_sha256
                cleanup_receipt = _digest(
                    candidate_cleanup_receipt_sha256,
                    code="project_update_transaction_state_transition_invalid",
                )
                candidate_absence = _digest(
                    candidate_absence_observation_sha256,
                    code="project_update_transaction_state_transition_invalid",
                )
                exact_absence = _candidate_absence_observation(
                    self._transaction_root,
                    transaction_ref=intent.transaction_ref,
                    reservation_sha256=intent.reservation_sha256,
                    intent_sha256=intent.sha256,
                    runtime_candidate_binding_sha256=candidate_binding,
                )
                if candidate_absence != exact_absence:
                    raise _fail("project_update_transaction_candidate_invalid")
            elif any(
                value is not None
                for value in (
                    cancellation_plan_sha256,
                    candidate_cleanup_receipt_sha256,
                    candidate_absence_observation_sha256,
                )
            ):
                raise _fail("project_update_transaction_state_transition_invalid")
            if phase in {"lock_released", "completed"}:
                lock_observation = self._absent_lock_observation(backlink)
                if phase == "lock_released":
                    if (
                        lock_release_result is None
                        or not lock_release_result.released
                        or not lock_release_result.directory_durability.durable
                        or lock_release_result.absence_observation_sha256 != lock_observation
                    ):
                        raise _fail("project_update_transaction_durability_unverified")
            else:
                lock_observation, _raw, _identity = self._present_lock_observation(backlink)
            previous = journal.head_sha256
            row: dict[str, Any] = {
                "intent_sha256": intent.sha256,
                "live_lock_observation_sha256": lock_observation,
                "observed_state_sha256": classification.observed_state_sha256,
                "phase": phase,
                "previous_checkpoint_sha256": previous,
                "schema": CHECKPOINT_SCHEMA,
                "seq": len(checkpoints) + 1,
                "stage": stage,
                "transaction_ref": intent.transaction_ref,
            }
            if component_ref is not None:
                row["component_ref"] = component_ref
            if approval_ref is not None:
                row["approval_reference_sha256"] = approval_ref
                row["approval_mac_sha256"] = approval_mac
            if claim_receipt is not None:
                row["claim_receipt_sha256"] = claim_receipt
                row["claim_mac_sha256"] = claim_mac
            if evidence:
                row["claim_evidence_digests"] = dict(evidence)
            if cancel_plan is not None:
                row["cancellation_plan_sha256"] = cancel_plan
                row["runtime_candidate_binding_sha256"] = candidate_binding
            if cleanup_receipt is not None:
                row["candidate_cleanup_receipt_sha256"] = cleanup_receipt
                row["candidate_absence_observation_sha256"] = candidate_absence
            line = canonical_json_bytes(row) + b"\n"
            path = self._transaction_root / "checkpoints.jsonl"
            try:
                if os.path.lexists(path):
                    named = _safe_regular(path, within=self._transaction_root)
                    flags = _flags(os.O_WRONLY | os.O_APPEND)
                else:
                    named = None
                    flags = _flags(os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND)
                descriptor = os.open(path, flags, 0o600)
                try:
                    opened = os.fstat(descriptor)
                    if (
                        not stat.S_ISREG(opened.st_mode)
                        or opened.st_nlink != 1
                        or (
                            named is not None
                            and (named.st_dev, named.st_ino)
                            != (opened.st_dev, opened.st_ino)
                        )
                    ):
                        raise OSError("checkpoint identity drift")
                    _write_all(descriptor, line)
                    os.fsync(descriptor)
                    opened_after = os.fstat(descriptor)
                finally:
                    os.close(descriptor)
                named_after = _safe_regular(path, within=self._transaction_root)
                if (opened_after.st_dev, opened_after.st_ino) != (
                    named_after.st_dev,
                    named_after.st_ino,
                ):
                    raise OSError("checkpoint path changed")
            except OSError:
                raise _fail("project_update_transaction_checkpoint_write_failed") from None
            _require_directory_durable(self._transaction_root)
            _intent, verified_journal, _backlink, _cleanup = self._load_exact_state(
                guard_locked=True,
                verify_candidate_content=False,
            )
            if verified_journal.state != "exact" or not verified_journal.verified_prefix:
                raise _fail("project_update_transaction_checkpoint_write_failed")
            return verified_journal.verified_prefix[-1]

        return perform()

    @contextmanager
    def append_guard_nonblocking(self) -> Iterator[None]:
        """Hold the transaction's identity-bound append guard without waiting."""

        guard = self._transaction_root / "append.guard"
        with _exclusive_guard(guard, within=self._transaction_root):
            yield

    def validate_claim_publication_boundary_guard_held(
        self,
        *,
        expected_lock_bytes: bytes,
        live_component_sha256: Mapping[str, str],
    ) -> ProjectUpdateCheckpoint:
        """Re-prove the exact prewrite state while ``append.guard`` is held.

        The caller must already hold :meth:`append_guard_nonblocking`.  This
        split lets the approval workflow publish only its claim inside the
        same guard, while all domain writing remains outside it.
        """

        _parse_lock_bytes(expected_lock_bytes, intent=self.intent)
        _intent, journal, backlink, cleanup = self._load_exact_state(
            guard_locked=True,
            verify_candidate_content=True,
        )
        checkpoints = journal.verified_prefix
        if (
            journal.state != "exact"
            or cleanup is not None
            or backlink is None
            or len(checkpoints) != 1
            or checkpoints[0].phase != "lock_backlinked"
            or checkpoints[0].stage != "verified"
            or checkpoints[-1].phase != "lock_backlinked"
            or any(
                item.phase.startswith("preapproval_cancel")
                for item in checkpoints
            )
        ):
            raise _fail("project_update_transaction_state_transition_invalid")
        classification = self.classify_live_components(
            live_component_sha256
        )
        if classification.overall != "prewrite_exact":
            raise _fail("project_update_transaction_state_transition_invalid")
        _observation, actual, _identity = self._present_lock_observation(
            backlink
        )
        if not hmac.compare_digest(actual, expected_lock_bytes):
            raise _fail("project_update_transaction_lock_invalid")
        return checkpoints[-1]

    def append(
        self,
        *,
        phase: str,
        stage: CheckpointStage,
        live_component_sha256: Mapping[str, str],
        component_ref: str | None = None,
        approval_reference_sha256: str | None = None,
        approval_mac_sha256: str | None = None,
        claim_receipt_sha256: str | None = None,
        claim_mac_sha256: str | None = None,
        claim_evidence: Mapping[str, str] | None = None,
        cancellation_plan_sha256: str | None = None,
        candidate_cleanup_receipt_sha256: str | None = None,
        candidate_absence_observation_sha256: str | None = None,
        lock_release_result: LockReleaseResult | None = None,
    ) -> ProjectUpdateCheckpoint:
        with self.append_guard_nonblocking():
            return self._append_guard_held(
                phase=phase,
                stage=stage,
                live_component_sha256=live_component_sha256,
                component_ref=component_ref,
                approval_reference_sha256=approval_reference_sha256,
                approval_mac_sha256=approval_mac_sha256,
                claim_receipt_sha256=claim_receipt_sha256,
                claim_mac_sha256=claim_mac_sha256,
                claim_evidence=claim_evidence,
                cancellation_plan_sha256=cancellation_plan_sha256,
                candidate_cleanup_receipt_sha256=(
                    candidate_cleanup_receipt_sha256
                ),
                candidate_absence_observation_sha256=(
                    candidate_absence_observation_sha256
                ),
                lock_release_result=lock_release_result,
            )

    append_checkpoint = append

    def begin_cancel_before_approval(
        self,
        *,
        expected_lock_bytes: bytes,
        live_component_sha256: Mapping[str, str],
        candidate_cleanup_plan_sha256: str | None = None,
    ) -> ProjectUpdateCheckpoint:
        """Durably authorize only cleanup of the sealed runtime candidate."""

        _parse_lock_bytes(expected_lock_bytes, intent=self.intent)
        exact_plan = self.candidate_cleanup_plan_sha256()
        if candidate_cleanup_plan_sha256 is None:
            plan = exact_plan
        else:
            plan = _digest(
                candidate_cleanup_plan_sha256,
                code="project_update_transaction_state_transition_invalid",
            )
            if plan != exact_plan:
                raise _fail("project_update_transaction_state_transition_invalid")

        def existing() -> ProjectUpdateCheckpoint | None:
            intent, journal, backlink, cleanup = self._load_exact_state(
                verify_candidate_content=True
            )
            if journal.state != "exact":
                raise _fail("project_update_transaction_journal_degraded")
            if (
                cleanup is not None
                or backlink is None
            ):
                raise _fail("project_update_transaction_state_transition_invalid")
            classification = self.classify_live_components(live_component_sha256)
            if classification.overall != "prewrite_exact":
                raise _fail("project_update_transaction_state_transition_invalid")
            observed, actual, _identity = self._present_lock_observation(backlink)
            if (
                not observed
                or not hmac.compare_digest(actual, expected_lock_bytes)
            ):
                raise _fail("project_update_transaction_lock_invalid")
            if not journal.verified_prefix:
                return None
            tail = journal.verified_prefix[-1]
            if tail.phase == "lock_backlinked":
                return None
            if (
                tail.phase == "preapproval_cancel_requested"
                and tail.cancellation_plan_sha256 == plan
                and tail.runtime_candidate_binding_sha256
                == _runtime_candidate_binding_sha256(intent)
            ):
                return tail
            raise _fail("project_update_transaction_state_transition_invalid")

        prior = existing()
        if prior is not None:
            return prior
        try:
            return self.append(
                phase="preapproval_cancel_requested",
                stage="intent",
                live_component_sha256=live_component_sha256,
                cancellation_plan_sha256=plan,
            )
        except ProjectUpdateTransactionError as error:
            if error.code != "project_update_transaction_state_transition_invalid":
                raise
            prior = existing()
            if prior is None:
                raise
            return prior

    def begin_claimless_cancel_before_approval(
        self,
        *,
        expected_lock_bytes: bytes,
        live_component_sha256: Mapping[str, str],
        confirm_claim_store_empty: Callable[[], bool],
        candidate_cleanup_plan_sha256: str | None = None,
    ) -> ProjectUpdateCheckpoint:
        """Atomically select claimless cancellation under ``append.guard``.

        The callback performs the caller's final claim-store absence check.
        It runs while the same nonblocking guard used by checkpoint append is
        held, and the cancellation-intent row is durably appended before that
        guard is released.  A false/non-boolean result or callback exception
        leaves the checkpoint journal unchanged.
        """

        if not callable(confirm_claim_store_empty):
            raise _fail("project_update_transaction_state_transition_invalid")
        _parse_lock_bytes(expected_lock_bytes, intent=self.intent)
        exact_plan = self.candidate_cleanup_plan_sha256()
        if candidate_cleanup_plan_sha256 is None:
            plan = exact_plan
        else:
            plan = _digest(
                candidate_cleanup_plan_sha256,
                code="project_update_transaction_state_transition_invalid",
            )
            if plan != exact_plan:
                raise _fail("project_update_transaction_state_transition_invalid")

        with self.append_guard_nonblocking():
            intent, journal, backlink, cleanup = self._load_exact_state(
                guard_locked=True,
                verify_candidate_content=True,
            )
            if journal.state != "exact":
                raise _fail("project_update_transaction_journal_degraded")
            if cleanup is not None or backlink is None:
                raise _fail("project_update_transaction_state_transition_invalid")
            classification = self.classify_live_components(
                live_component_sha256
            )
            if classification.overall != "prewrite_exact":
                raise _fail("project_update_transaction_state_transition_invalid")
            _observed, actual, _identity = self._present_lock_observation(
                backlink
            )
            if not hmac.compare_digest(actual, expected_lock_bytes):
                raise _fail("project_update_transaction_lock_invalid")
            if not journal.verified_prefix:
                raise _fail("project_update_transaction_state_transition_invalid")
            tail = journal.verified_prefix[-1]
            if (
                tail.phase == "preapproval_cancel_requested"
                and tail.cancellation_plan_sha256 == plan
                and tail.runtime_candidate_binding_sha256
                == _runtime_candidate_binding_sha256(intent)
            ):
                return tail
            if tail.phase != "lock_backlinked":
                raise _fail("project_update_transaction_state_transition_invalid")

            confirmed = confirm_claim_store_empty()
            if type(confirmed) is not bool or not confirmed:
                raise _fail("project_update_transaction_state_transition_invalid")
            return self._append_guard_held(
                phase="preapproval_cancel_requested",
                stage="intent",
                live_component_sha256=live_component_sha256,
                cancellation_plan_sha256=plan,
            )

    def cancel_before_approval(
        self,
        *,
        expected_lock_bytes: bytes,
        live_component_sha256: Mapping[str, str],
        candidate_cleanup_plan_sha256: str | None = None,
        candidate_cleanup_receipt_sha256: str | None = None,
    ) -> ProjectUpdateCheckpoint:
        """Idempotently finish a begun preapproval cancellation.

        The runtime-candidate cleanup is performed by its owning runtime
        subsystem.  This finalizer accepts only its exact plan/receipt digests,
        proves candidate and seal absence durably, and never accepts approval
        or claim evidence.
        """

        _parse_lock_bytes(expected_lock_bytes, intent=self.intent)
        exact_plan = self.candidate_cleanup_plan_sha256()
        if candidate_cleanup_plan_sha256 is None:
            plan = exact_plan
        else:
            plan = _digest(
                candidate_cleanup_plan_sha256,
                code="project_update_transaction_state_transition_invalid",
            )
            if plan != exact_plan:
                raise _fail("project_update_transaction_state_transition_invalid")
        supplied_cleanup_receipt = (
            None
            if candidate_cleanup_receipt_sha256 is None
            else _digest(
                candidate_cleanup_receipt_sha256,
                code="project_update_transaction_state_transition_invalid",
            )
        )
        for _attempt in range(8):
            intent, journal, backlink, cleanup = self._load_exact_state()
            if journal.state != "exact":
                raise _fail("project_update_transaction_journal_degraded")
            if (
                cleanup is not None
                or backlink is None
                or not journal.verified_prefix
            ):
                raise _fail("project_update_transaction_state_transition_invalid")
            classification = self.classify_live_components(live_component_sha256)
            if classification.overall != "prewrite_exact":
                raise _fail("project_update_transaction_state_transition_invalid")
            if any(
                item.phase in {
                    "approval_bound",
                    "domain_committed",
                    "rollback_authorized",
                    "claim_succeeded",
                }
                or item.phase in COMPONENT_ROLES
                for item in journal.verified_prefix
            ):
                raise _fail("project_update_transaction_state_transition_invalid")
            requested = next(
                (
                    item
                    for item in journal.verified_prefix
                    if item.phase == "preapproval_cancel_requested"
                ),
                None,
            )
            if (
                requested is None
                or requested.cancellation_plan_sha256 != plan
                or requested.runtime_candidate_binding_sha256
                != _runtime_candidate_binding_sha256(intent)
            ):
                raise _fail("project_update_transaction_state_transition_invalid")
            cleanup_receipt = self.candidate_cleanup_receipt_sha256()
            if (
                supplied_cleanup_receipt is not None
                and supplied_cleanup_receipt != cleanup_receipt
            ):
                raise _fail("project_update_transaction_state_transition_invalid")
            verified = next(
                (
                    item
                    for item in journal.verified_prefix
                    if item.phase == "preapproval_cancelled"
                ),
                None,
            )
            if verified is not None and (
                verified.cancellation_plan_sha256 != plan
                or verified.runtime_candidate_binding_sha256
                != requested.runtime_candidate_binding_sha256
                or verified.candidate_cleanup_receipt_sha256 != cleanup_receipt
            ):
                raise _fail("project_update_transaction_state_transition_invalid")
            tail = journal.verified_prefix[-1]
            if tail.phase == "completed":
                self._absent_lock_observation(backlink)
                return tail
            if tail.phase == "preapproval_cancel_requested":
                absence = _candidate_absence_observation(
                    self._transaction_root,
                    transaction_ref=intent.transaction_ref,
                    reservation_sha256=intent.reservation_sha256,
                    intent_sha256=intent.sha256,
                    runtime_candidate_binding_sha256=(
                        requested.runtime_candidate_binding_sha256
                    ),
                )
                if os.path.lexists(self._lock_path):
                    _observed, actual, _identity = self._present_lock_observation(
                        backlink
                    )
                    if not hmac.compare_digest(actual, expected_lock_bytes):
                        raise _fail("project_update_transaction_lock_invalid")
                self.append(
                    phase="preapproval_cancelled",
                    stage="verified",
                    live_component_sha256=live_component_sha256,
                    cancellation_plan_sha256=plan,
                    candidate_cleanup_receipt_sha256=cleanup_receipt,
                    candidate_absence_observation_sha256=absence,
                )
                continue
            if tail.phase == "preapproval_cancelled":
                self.append(
                    phase="ready_to_unlock",
                    stage="verified",
                    live_component_sha256=live_component_sha256,
                )
                continue
            if tail.phase == "ready_to_unlock":
                if os.path.lexists(self._lock_path):
                    release = self.release_lock_exact(
                        expected_lock_bytes=expected_lock_bytes,
                        live_component_sha256=live_component_sha256,
                    )
                else:
                    release = self.confirm_lock_absence_durable(
                        live_component_sha256=live_component_sha256
                    )
                self.append(
                    phase="lock_released",
                    stage="verified",
                    live_component_sha256=live_component_sha256,
                    lock_release_result=release,
                )
                continue
            if tail.phase == "lock_released":
                self.append(
                    phase="completed",
                    stage="verified",
                    live_component_sha256=live_component_sha256,
                )
                continue
            raise _fail("project_update_transaction_state_transition_invalid")
        raise _fail("project_update_transaction_state_transition_invalid")

    def finalize_succeeded_claim(
        self,
        *,
        checkpoint_guard_sha256: str,
        live_component_sha256: Mapping[str, str],
        claim_receipt_sha256: str,
        claim_mac_sha256: str,
        claim_evidence: Mapping[str, str],
    ) -> ProjectUpdateCheckpoint:
        """Idempotently bind one already-succeeded native claim to the journal.

        The guard may name the exact ``domain_committed`` head used by an
        immediate claim, or the exact ``claim_succeeded`` head recovered after
        process loss.  No earlier/later checkpoint authorizes this finalizer.
        """

        guard = _digest(
            checkpoint_guard_sha256,
            code="project_update_transaction_state_transition_invalid",
        )

        def exact_existing() -> ProjectUpdateCheckpoint | None:
            intent, journal, backlink, cleanup = self._load_exact_state()
            if (
                cleanup is not None
                or backlink is None
                or journal.state != "exact"
                or not journal.verified_prefix
            ):
                raise _fail("project_update_transaction_state_transition_invalid")
            tail = journal.verified_prefix[-1]
            if tail.phase == "domain_committed":
                if guard != tail.checkpoint_sha256:
                    raise _fail("project_update_transaction_state_transition_invalid")
                return None
            if tail.phase != "claim_succeeded" or guard not in {
                tail.previous_checkpoint_sha256,
                tail.checkpoint_sha256,
            }:
                raise _fail("project_update_transaction_state_transition_invalid")
            classification = self.classify_live_components(live_component_sha256)
            if classification.overall != "complete_exact":
                raise _fail("project_update_transaction_state_transition_invalid")
            self._present_lock_observation(backlink)
            expected_evidence = _claim_evidence_digests(
                claim_evidence,
                intent=intent,
                approval_reference_sha256=tail.approval_reference_sha256,
                claim_receipt_sha256=claim_receipt_sha256,
                claim_mac_sha256=claim_mac_sha256,
            )
            if (
                tail.claim_receipt_sha256 != claim_receipt_sha256
                or tail.claim_mac_sha256 != claim_mac_sha256
                or tail.claim_evidence_digests != expected_evidence
            ):
                raise _fail("project_update_transaction_state_transition_invalid")
            return tail

        existing = exact_existing()
        if existing is not None:
            return existing
        try:
            return self.append(
                phase="claim_succeeded",
                stage="verified",
                live_component_sha256=live_component_sha256,
                claim_receipt_sha256=claim_receipt_sha256,
                claim_mac_sha256=claim_mac_sha256,
                claim_evidence=claim_evidence,
            )
        except ProjectUpdateTransactionError as error:
            if error.code != "project_update_transaction_state_transition_invalid":
                raise
            # A competing identical finalizer may have appended the one exact
            # claim checkpoint after our guard read.  Re-read and accept only
            # that exact idempotent result; any later tail remains refused.
            existing = exact_existing()
            if existing is None:
                raise
            return existing

    append_succeeded_claim = finalize_succeeded_claim

    def release_lock_exact(
        self,
        *,
        expected_lock_bytes: bytes,
        live_component_sha256: Mapping[str, str],
    ) -> LockReleaseResult:
        _parse_lock_bytes(expected_lock_bytes, intent=self.intent)
        guard = self._transaction_root / "append.guard"
        with _exclusive_guard(guard, within=self._transaction_root):
            _intent, journal, backlink, cleanup = self._load_exact_state(
                guard_locked=True
            )
            if cleanup is not None or backlink is None or journal.state != "exact":
                raise _fail("project_update_transaction_lock_invalid")
            next_events = _next_events(journal.verified_prefix, self.intent)
            if len(next_events) != 1 or next_events[0].phase != "lock_released":
                raise _fail("project_update_transaction_state_transition_invalid")
            classification = self.classify_live_components(live_component_sha256)
            self._validate_live_for_event(
                next_events[0], journal.verified_prefix, classification
            )
            _observation, actual, _identity = self._present_lock_observation(backlink)
            if not hmac.compare_digest(actual, expected_lock_bytes):
                raise _fail("project_update_transaction_lock_invalid")
            try:
                self._lock_path.unlink()
            except OSError:
                raise _fail("project_update_transaction_lock_invalid") from None
            durability = _fsync_directory(self._lock_path.parent)
            absence = self._absent_lock_observation(backlink)
            return LockReleaseResult(True, absence, durability)

    def confirm_lock_absence_durable(
        self, *, live_component_sha256: Mapping[str, str]
    ) -> LockReleaseResult:
        _intent, journal, backlink, cleanup = self._load_exact_state()
        if cleanup is not None or backlink is None or journal.state != "exact":
            raise _fail("project_update_transaction_lock_invalid")
        next_events = _next_events(journal.verified_prefix, self.intent)
        if len(next_events) != 1 or next_events[0].phase != "lock_released":
            raise _fail("project_update_transaction_state_transition_invalid")
        classification = self.classify_live_components(live_component_sha256)
        self._validate_live_for_event(
            next_events[0], journal.verified_prefix, classification
        )
        absence = self._absent_lock_observation(backlink)
        durability = _fsync_directory(self._lock_path.parent)
        return LockReleaseResult(True, absence, durability)

    def inspect(
        self,
        *,
        verify_candidate_content: bool = True,
    ) -> ProjectUpdateInspection:
        if type(verify_candidate_content) is not bool:
            raise _fail("project_update_transaction_invalid")
        intent, journal, backlink, _cleanup = self._load_exact_state(
            verify_candidate_content=verify_candidate_content
        )
        terminal = (
            journal.state == "exact"
            and bool(journal.verified_prefix)
            and journal.verified_prefix[-1].phase == "completed"
            and not _next_events(journal.verified_prefix, intent)
        )
        return ProjectUpdateInspection(
            schema=INSPECTION_SCHEMA,
            transaction_ref=intent.transaction_ref,
            transaction_logical_ref=intent.transaction_logical_ref,
            intent_sha256=intent.sha256,
            project_identity_sha256=intent.project_identity_sha256,
            requested_target_tag=intent.requested_target_tag,
            lock_backlinked=backlink is not None,
            journal=journal,
            terminal=terminal,
        )

    def public_summary(self) -> dict[str, Any]:
        inspection = self.inspect()
        if not inspection.lock_backlinked:
            lifecycle = "orphan_before_lock"
        elif inspection.journal.state != "exact":
            lifecycle = "manual_review_journal_degraded"
        elif inspection.terminal:
            lifecycle = "terminal"
        else:
            lifecycle = "active"
        if inspection.journal.state != "exact":
            state_machine_state = "manual_review"
        elif inspection.journal.verified_prefix:
            last = inspection.journal.verified_prefix[-1]
            state_machine_state = f"{last.phase}:{last.stage}"
        else:
            state_machine_state = "intent_reserved"
        return {
            "checkpoint_count": len(inspection.journal.verified_prefix),
            "checkpoint_head_sha256": inspection.journal.head_sha256,
            "directory_fsync_required": True,
            "fetched_refs_may_change": True,
            "intent_sha256": inspection.intent_sha256,
            "journal_reason_code": inspection.journal.reason_code,
            "journal_state": inspection.journal.state,
            "journal_unverified_tail_sha256": inspection.journal.unverified_tail_sha256,
            "journal_unverified_tail_size": inspection.journal.unverified_tail_size,
            "lifecycle": lifecycle,
            "lock_backlinked": inspection.lock_backlinked,
            "preapproval_control_writes_completed": True,
            "preapproval_domain_writes_completed": False,
            "project_identity_sha256": inspection.project_identity_sha256,
            "requested_target_tag": inspection.requested_target_tag,
            "schema": PUBLIC_SUMMARY_SCHEMA,
            "state_machine_state": state_machine_state,
            "terminal": inspection.terminal,
            "transaction_logical_ref": inspection.transaction_logical_ref,
            "transaction_ref": inspection.transaction_ref,
        }

    def exact_cleanup(self, *, cleanup_authority_sha256: str) -> bool:
        """Move terminal evidence to a resumable tombstone, then erase exactly."""

        try:
            authority = _digest(
                cleanup_authority_sha256,
                code="project_update_transaction_cleanup_refused",
            )
            parent = self._transaction_root.parent
            tombstone, proof = self._cleanup_paths(
                parent,
                self.intent.transaction_ref,
            )
            if not os.path.lexists(self._transaction_root):
                if os.path.lexists(tombstone) or os.path.lexists(proof):
                    completed = self._resume_cleanup_paths(
                        self._project_root,
                        self.intent.transaction_ref,
                        authority,
                    )
                    self._cleanup_completed = completed
                    return completed
                return self._cleanup_completed
            transaction_root_before = _safe_directory(
                self._transaction_root,
                within=parent,
            )
            transaction_root_identity = _cleanup_directory_identity(
                transaction_root_before
            )
            intent, journal, backlink, existing_plan = self._load_exact_state(
                verify_candidate_content=True
            )
            if (
                backlink is None
                or journal.state != "exact"
                or not journal.verified_prefix
                or journal.verified_prefix[-1].phase != "completed"
                or _next_events(journal.verified_prefix, intent)
            ):
                return False
            self._absent_lock_observation(backlink)
            if os.path.lexists(tombstone) or os.path.lexists(proof):
                return False
            plan = self._build_cleanup_plan(
                intent,
                journal,
                authority,
                transaction_root_identity=transaction_root_identity,
            )
            plan_bytes = _document_bytes(plan)
            plan_path = self._transaction_root / CLEANUP_PLAN_NAME
            if not os.path.lexists(plan_path):
                _write_new(plan_path, plan_bytes, within=self._transaction_root)
                _require_directory_durable(self._transaction_root)
            elif (
                existing_plan is None
                or existing_plan.get("schema") != CLEANUP_PLAN_SCHEMA
                or not hmac.compare_digest(
                    _document_bytes(existing_plan),
                    plan_bytes,
                )
            ):
                return False
            # Reflush even on resume: a process may have stopped after the
            # complete sidecar became visible but before its directory entry
            # was durably committed.
            _require_directory_durable(self._transaction_root)
            transaction_root_after = _safe_directory(
                self._transaction_root,
                within=parent,
            )
            if (
                _cleanup_directory_identity(transaction_root_after)
                != transaction_root_identity
            ):
                return False
            try:
                _atomic_move_directory_no_replace(
                    self._transaction_root, tombstone
                )
            except OSError:
                return False
            moved_tombstone = _safe_directory(tombstone, within=parent)
            if (
                _cleanup_directory_identity(moved_tombstone)
                != transaction_root_identity
            ):
                return False
            durability = _fsync_directory(parent)
            if not durability.durable:
                return False
            completed = self._resume_cleanup_paths(
                self._project_root, self.intent.transaction_ref, authority
            )
            self._cleanup_completed = completed
            return completed
        except (OSError, ProjectUpdateTransactionError, KeyError, TypeError):
            return False

    @classmethod
    def discover_complete_cleanup_tombstone_for_resume_read_only(
        cls, project_root: Path | str
    ) -> CleanupTombstoneInspection | None:
        """Find one byte-complete legacy tombstone without trusting its claim.

        Canonical cleanup-proof-shaped files are inert history. Exact abort
        originals and abort-cleanup tombstones are independently validated and
        excluded so one ordinary tombstone can still be recovered from a mixed
        crash state. Any other live transaction, malformed name or artifact,
        unsafe entry, concurrent drift, live global lock, or more than one
        ordinary tombstone refuses discovery. A returned value authorizes only
        atomic restoration of these exact private bytes so the ordinary
        transaction and claim validators can run; it does not itself attribute
        past success.
        """

        project = _absolute(project_root)
        _safe_existing_chain(project, directory=True)
        lock_path = project / PurePosixPath(PROJECT_UPDATE_LOCK_LOGICAL)
        _within(lock_path, project)
        if os.path.lexists(lock_path):
            raise _fail("project_update_transaction_cleanup_refused")

        parent = project / PurePosixPath(TRANSACTION_ROOT_LOGICAL)
        _within(parent, project)
        if not os.path.lexists(parent):
            return None
        _safe_existing_chain(parent, directory=True)
        abort_inspections = discover_exact_reservation_abort_cleanup_read_only(
            project
        )
        abort_originals = {
            item.transaction_ref: item
            for item in abort_inspections
            if item.state != "cleanup_tombstone"
        }
        abort_tombstones = {
            item.transaction_ref: item
            for item in abort_inspections
            if item.state == "cleanup_tombstone"
        }
        parent_before = _stable_path_identity(
            _safe_directory(parent, within=project)
        )

        tombstones: list[tuple[str, Path]] = []
        proof_refs: set[str] = set()
        seen = 0
        try:
            with os.scandir(parent) as entries:
                for entry in entries:
                    seen += 1
                    if seen > MAX_TERMINAL_CLEANUP_SCAN_ENTRIES:
                        raise _fail("project_update_transaction_scan_incomplete")
                    path = Path(entry.path)
                    _within(path, parent)
                    info = path.lstat()
                    if stat.S_ISLNK(info.st_mode) or _is_reparse(info):
                        raise _fail("project_update_transaction_path_unsafe")
                    name = entry.name
                    abort_original = abort_originals.get(name)
                    if abort_original is not None:
                        if (
                            not stat.S_ISDIR(info.st_mode)
                            or _stable_path_identity(info)
                            != abort_original.entry_identity
                        ):
                            raise _fail(
                                "project_update_transaction_cleanup_refused"
                            )
                        continue
                    tombstone_match = re.fullmatch(
                        r"\.cleanup_(update_[0-9a-f]{32})", name
                    )
                    proof_match = re.fullmatch(
                        r"\.cleanup-proof_(update_[0-9a-f]{32})\.json", name
                    )
                    if tombstone_match is not None:
                        ref = tombstone_match.group(1)
                        abort_tombstone = abort_tombstones.get(ref)
                        if abort_tombstone is not None:
                            if (
                                not stat.S_ISDIR(info.st_mode)
                                or _stable_path_identity(info)
                                != abort_tombstone.entry_identity
                            ):
                                raise _fail(
                                    "project_update_transaction_cleanup_refused"
                                )
                            continue
                        if not stat.S_ISDIR(info.st_mode):
                            raise _fail("project_update_transaction_cleanup_refused")
                        tombstones.append((ref, path))
                        continue
                    if proof_match is not None:
                        if proof_match.group(1) in abort_tombstones:
                            if not stat.S_ISREG(info.st_mode):
                                raise _fail(
                                    "project_update_transaction_cleanup_refused"
                                )
                            # The paired abort discovery validated proof bytes,
                            # link cardinality, and tombstone identity. Its
                            # second pass below closes this scan's race window.
                            continue
                        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                            raise _fail("project_update_transaction_cleanup_refused")
                        ref = proof_match.group(1)
                        raw = _read_regular(
                            path, within=parent, maximum=MAX_DOCUMENT_BYTES + 1
                        )
                        value = _parse_document(
                            raw, code="project_update_transaction_cleanup_refused"
                        )
                        if not hmac.compare_digest(raw, _document_bytes(value)):
                            raise _fail("project_update_transaction_cleanup_refused")
                        authority = (
                            value.get("cleanup_authority_sha256")
                            if type(value) is dict
                            else None
                        )
                        if type(authority) is not str:
                            raise _fail("project_update_transaction_cleanup_refused")
                        cls._validate_cleanup_plan_document(value, ref, authority)
                        proof_refs.add(ref)
                        continue
                    # The recovery namespace is intentionally closed. An
                    # ordinary update directory or any unknown entry must be
                    # handled by the live/orphan classifier, never skipped.
                    raise _fail("project_update_transaction_cleanup_refused")
        except OSError:
            raise _fail("project_update_transaction_path_unsafe") from None

        parent_after_scan = _stable_path_identity(
            _safe_directory(parent, within=project)
        )
        if (
            parent_after_scan != parent_before
            or os.path.lexists(lock_path)
            or discover_exact_reservation_abort_cleanup_read_only(project)
            != abort_inspections
        ):
            raise _fail("project_update_transaction_cleanup_refused")
        if not tombstones:
            return None
        if len(tombstones) != 1:
            raise _fail("project_update_transaction_cleanup_refused")

        transaction_ref, tombstone = tombstones[0]
        if transaction_ref in proof_refs:
            raise _fail("project_update_transaction_cleanup_refused")
        tombstone_before_info = _safe_directory(tombstone, within=parent)
        tombstone_before = _stable_path_identity(tombstone_before_info)
        tombstone_generation = _cleanup_directory_identity(
            tombstone_before_info
        )
        plan_path = _existing_cleanup_plan_path(tombstone)
        if plan_path is None:
            raise _fail("project_update_transaction_cleanup_refused")
        plan_raw = _read_regular(
            plan_path, within=tombstone, maximum=MAX_DOCUMENT_BYTES + 1
        )
        plan_value = _parse_document(
            plan_raw, code="project_update_transaction_cleanup_refused"
        )
        if not hmac.compare_digest(plan_raw, _document_bytes(plan_value)):
            raise _fail("project_update_transaction_cleanup_refused")
        authority = (
            plan_value.get("cleanup_authority_sha256")
            if type(plan_value) is dict
            else None
        )
        if type(authority) is not str:
            raise _fail("project_update_transaction_cleanup_refused")
        plan = cls._validate_cleanup_plan_document(
            plan_value, transaction_ref, authority
        )
        root_identity = plan.get("transaction_root_identity")
        if (
            plan.get("schema") == CLEANUP_PLAN_SCHEMA
            and (
                not isinstance(root_identity, dict)
                or (
                    int(root_identity["device"]),
                    int(root_identity["inode"]),
                    root_identity["birthtime_ns"],
                )
                != tombstone_generation
            )
        ):
            raise _fail("project_update_transaction_cleanup_refused")
        expected_files = {
            item["relative_path"]: (item["size"], item["sha256"])
            for item in plan["files"]
        }
        expected_directories = set(plan["directories"])
        actual_files, actual_directories = cls._descendant_snapshot(
            tombstone,
            exclude={plan_path.name},
        )
        if actual_files != expected_files or actual_directories != expected_directories:
            raise _fail("project_update_transaction_cleanup_refused")
        tombstone_after_info = _safe_directory(tombstone, within=parent)
        tombstone_after = _stable_path_identity(tombstone_after_info)
        parent_after_content = _stable_path_identity(
            _safe_directory(parent, within=project)
        )
        if (
            tombstone_after != tombstone_before
            or _cleanup_directory_identity(tombstone_after_info)
            != tombstone_generation
            or parent_after_content != parent_before
            or os.path.lexists(lock_path)
            or discover_exact_reservation_abort_cleanup_read_only(project)
            != abort_inspections
        ):
            raise _fail("project_update_transaction_cleanup_refused")
        return CleanupTombstoneInspection(
            transaction_ref=transaction_ref,
            cleanup_authority_sha256=authority,
            cleanup_plan_sha256=sha256_bytes(plan_raw),
            intent_sha256=plan["intent_sha256"],
            terminal_checkpoint_sha256=plan["terminal_checkpoint_sha256"],
            transaction_parent_identity=parent_before,
            tombstone_identity=tombstone_before,
        )

    @classmethod
    def restore_complete_cleanup_tombstone_for_resume(
        cls,
        project_root: Path | str,
        inspection: CleanupTombstoneInspection,
    ) -> "ProjectUpdateTransaction":
        """Atomically restore one previously inspected complete tombstone."""

        if not isinstance(inspection, CleanupTombstoneInspection):
            raise _fail("project_update_transaction_cleanup_refused")
        project = _absolute(project_root)
        latest = cls.discover_complete_cleanup_tombstone_for_resume_read_only(
            project
        )
        if latest is None or latest != inspection:
            raise _fail("project_update_transaction_cleanup_refused")
        parent = project / PurePosixPath(TRANSACTION_ROOT_LOGICAL)
        original = parent / inspection.transaction_ref
        tombstone, proof = cls._cleanup_paths(parent, inspection.transaction_ref)
        lock_path = project / PurePosixPath(PROJECT_UPDATE_LOCK_LOGICAL)
        if (
            _stable_path_identity(_safe_directory(parent, within=project))
            != inspection.transaction_parent_identity
            or os.path.lexists(lock_path)
            or os.path.lexists(original)
            or os.path.lexists(proof)
        ):
            raise _fail("project_update_transaction_cleanup_refused")
        if (
            _stable_path_identity(_safe_directory(tombstone, within=parent))
            != inspection.tombstone_identity
        ):
            raise _fail("project_update_transaction_cleanup_refused")
        try:
            _atomic_move_directory_no_replace(tombstone, original)
        except OSError:
            raise _fail("project_update_transaction_cleanup_refused") from None
        if not _fsync_directory(parent).durable:
            raise _fail("project_update_transaction_durability_unverified")
        if os.path.lexists(tombstone) or not os.path.lexists(original):
            raise _fail("project_update_transaction_cleanup_refused")
        if os.path.lexists(lock_path):
            raise _fail("project_update_transaction_cleanup_refused")
        if (
            _stable_path_identity(_safe_directory(original, within=parent))
            != inspection.tombstone_identity
        ):
            raise _fail("project_update_transaction_cleanup_refused")

        # From this point the ordinary sealed-transaction validators are
        # authoritative. A failure leaves the original directory present so a
        # fresh writer remains fail-closed; it is never silently moved back.
        transaction = cls.open(
            project, inspection.transaction_ref, verify_candidate_content=True
        )
        state = transaction.inspect(verify_candidate_content=True)
        if (
            os.path.lexists(lock_path)
            or
            not state.terminal
            or state.intent_sha256 != inspection.intent_sha256
            or state.journal.head_sha256 != inspection.terminal_checkpoint_sha256
            or transaction.cleanup_authority_sha256_read_only()
            != inspection.cleanup_authority_sha256
        ):
            raise _fail("project_update_transaction_cleanup_refused")
        cls._validate_restored_cleanup_namespace_read_only(
            project, inspection
        )
        return transaction

    @classmethod
    def _validate_restored_cleanup_namespace_read_only(
        cls,
        project: Path,
        inspection: CleanupTombstoneInspection,
    ) -> None:
        """Recheck the closed namespace and exact plan after restoration."""

        parent = project / PurePosixPath(TRANSACTION_ROOT_LOGICAL)
        original = parent / inspection.transaction_ref
        lock_path = project / PurePosixPath(PROJECT_UPDATE_LOCK_LOGICAL)
        if os.path.lexists(lock_path):
            raise _fail("project_update_transaction_cleanup_refused")
        before = _stable_path_identity(_safe_directory(parent, within=project))
        original_seen = False
        seen = 0
        try:
            with os.scandir(parent) as entries:
                for entry in entries:
                    seen += 1
                    if seen > MAX_TERMINAL_CLEANUP_SCAN_ENTRIES:
                        raise _fail("project_update_transaction_scan_incomplete")
                    path = Path(entry.path)
                    _within(path, parent)
                    info = path.lstat()
                    if stat.S_ISLNK(info.st_mode) or _is_reparse(info):
                        raise _fail("project_update_transaction_path_unsafe")
                    if entry.name == inspection.transaction_ref:
                        if (
                            original_seen
                            or not stat.S_ISDIR(info.st_mode)
                            or _stable_path_identity(info)
                            != inspection.tombstone_identity
                        ):
                            raise _fail(
                                "project_update_transaction_cleanup_refused"
                            )
                        original_seen = True
                        continue
                    proof_match = re.fullmatch(
                        r"\.cleanup-proof_(update_[0-9a-f]{32})\.json",
                        entry.name,
                    )
                    if (
                        proof_match is None
                        or not stat.S_ISREG(info.st_mode)
                        or info.st_nlink != 1
                    ):
                        raise _fail("project_update_transaction_cleanup_refused")
                    proof_raw = _read_regular(
                        path, within=parent, maximum=MAX_DOCUMENT_BYTES + 1
                    )
                    proof_value = _parse_document(
                        proof_raw,
                        code="project_update_transaction_cleanup_refused",
                    )
                    if not hmac.compare_digest(
                        proof_raw, _document_bytes(proof_value)
                    ):
                        raise _fail("project_update_transaction_cleanup_refused")
                    proof_authority = (
                        proof_value.get("cleanup_authority_sha256")
                        if type(proof_value) is dict
                        else None
                    )
                    if type(proof_authority) is not str:
                        raise _fail("project_update_transaction_cleanup_refused")
                    cls._validate_cleanup_plan_document(
                        proof_value,
                        proof_match.group(1),
                        proof_authority,
                    )
        except OSError:
            raise _fail("project_update_transaction_path_unsafe") from None
        if not original_seen:
            raise _fail("project_update_transaction_cleanup_refused")

        plan_path = _existing_cleanup_plan_path(original)
        if plan_path is None:
            raise _fail("project_update_transaction_cleanup_refused")
        plan_raw = _read_regular(
            plan_path, within=original, maximum=MAX_DOCUMENT_BYTES + 1
        )
        if not hmac.compare_digest(
            sha256_bytes(plan_raw), inspection.cleanup_plan_sha256
        ):
            raise _fail("project_update_transaction_cleanup_refused")
        plan_value = _parse_document(
            plan_raw, code="project_update_transaction_cleanup_refused"
        )
        plan = cls._validate_cleanup_plan_document(
            plan_value,
            inspection.transaction_ref,
            inspection.cleanup_authority_sha256,
        )
        original_identity = _safe_directory(original, within=parent)
        root_identity = plan.get("transaction_root_identity")
        if (
            plan.get("schema") == CLEANUP_PLAN_SCHEMA
            and (
                not isinstance(root_identity, dict)
                or (
                    int(root_identity["device"]),
                    int(root_identity["inode"]),
                    root_identity["birthtime_ns"],
                )
                != _cleanup_directory_identity(original_identity)
            )
        ):
            raise _fail("project_update_transaction_cleanup_refused")
        actual_files, actual_directories = cls._descendant_snapshot(
            original,
            exclude={plan_path.name},
        )
        expected_files = {
            item["relative_path"]: (item["size"], item["sha256"])
            for item in plan["files"]
        }
        if (
            actual_files != expected_files
            or actual_directories != set(plan["directories"])
            or _stable_path_identity(_safe_directory(parent, within=project))
            != before
            or os.path.lexists(lock_path)
        ):
            raise _fail("project_update_transaction_cleanup_refused")

    def cleanup_authority_sha256_read_only(self) -> str | None:
        """Return an exact existing cleanup-plan authority, never inferred."""

        _intent, journal, _backlink, cleanup = self._load_exact_state(
            verify_candidate_content=True
        )
        if cleanup is None:
            return None
        if journal.state != "exact":
            raise _fail("project_update_transaction_cleanup_refused")
        return _digest(
            cleanup.get("cleanup_authority_sha256"),
            code="project_update_transaction_cleanup_refused",
        )

    @classmethod
    def resume_cleanup(
        cls,
        project_root: Path | str,
        transaction_ref: str,
        *,
        cleanup_authority_sha256: str,
    ) -> bool:
        try:
            project = _absolute(project_root)
            _safe_existing_chain(project, directory=True)
            ref = _transaction_ref(transaction_ref)
            authority = _digest(
                cleanup_authority_sha256,
                code="project_update_transaction_cleanup_refused",
            )
            return cls._resume_cleanup_paths(project, ref, authority)
        except (OSError, ProjectUpdateTransactionError, KeyError, TypeError):
            return False

    @staticmethod
    def _cleanup_paths(parent: Path, transaction_ref: str) -> tuple[Path, Path]:
        _transaction_ref(transaction_ref)
        return (
            parent / f".cleanup_{transaction_ref}",
            parent / f".cleanup-proof_{transaction_ref}.json",
        )

    def _build_cleanup_plan(
        self,
        intent: ProjectUpdateIntent,
        journal: JournalInspection,
        authority: str,
        *,
        transaction_root_identity: tuple[int, int, int | None],
    ) -> dict[str, Any]:
        files, directories = self._descendant_snapshot(
            self._transaction_root,
            exclude={CLEANUP_PLAN_NAME},
        )
        return {
            "cleanup_authority_sha256": authority,
            "directories": sorted(directories),
            "files": [
                {
                    "relative_path": relative,
                    "sha256": digest,
                    "size": size,
                }
                for relative, (size, digest) in sorted(files.items())
            ],
            "intent_sha256": intent.sha256,
            "schema": CLEANUP_PLAN_SCHEMA,
            "terminal_checkpoint_sha256": journal.head_sha256,
            "transaction_root_identity": {
                "birthtime_ns": transaction_root_identity[2],
                "device": int(transaction_root_identity[0]),
                "inode": int(transaction_root_identity[1]),
            },
            "transaction_logical_ref": intent.transaction_logical_ref,
            "transaction_ref": intent.transaction_ref,
        }

    @classmethod
    def _resume_cleanup_paths(
        cls, project: Path, transaction_ref: str, authority: str
    ) -> bool:
        parent = project / PurePosixPath(TRANSACTION_ROOT_LOGICAL)
        _safe_existing_chain(parent, directory=True)
        original = parent / transaction_ref
        tombstone, proof = cls._cleanup_paths(parent, transaction_ref)
        if os.path.lexists(original):
            return False
        if os.path.lexists(proof):
            proof_raw, proof_info = _read_cleanup_linked_regular(
                project,
                proof,
                maximum=MAX_DOCUMENT_BYTES + 1,
            )
            proof_identity = (int(proof_info.st_dev), int(proof_info.st_ino))
            plan = cls._validate_cleanup_plan_document(
                _parse_document(
                    proof_raw, code="project_update_transaction_cleanup_refused"
                ),
                transaction_ref,
                authority,
            )
            plan_name = _cleanup_plan_name_for_document(plan)
            if os.path.lexists(tombstone):
                if plan.get("schema") != CLEANUP_PLAN_SCHEMA:
                    return False
                tombstone_info = _safe_directory(tombstone, within=parent)
                tombstone_generation = _cleanup_directory_identity(
                    tombstone_info
                )
                tombstone_snapshot = _CleanupDirectorySnapshot(
                    device=tombstone_generation[0],
                    inode=tombstone_generation[1],
                    birthtime_ns=tombstone_generation[2],
                )
                root_identity = plan["transaction_root_identity"]
                if (
                    int(root_identity["device"]),
                    int(root_identity["inode"]),
                    root_identity["birthtime_ns"],
                ) != (
                    tombstone_snapshot.device,
                    tombstone_snapshot.inode,
                    tombstone_snapshot.birthtime_ns,
                ):
                    return False
                with _cleanup_bound_directory_context(
                    project,
                    tombstone,
                ):
                    bound_info = _safe_directory(tombstone, within=parent)
                    if _cleanup_directory_identity(bound_info) != (
                        tombstone_snapshot.device,
                        tombstone_snapshot.inode,
                        tombstone_snapshot.birthtime_ns,
                    ):
                        return False
                    with os.scandir(tombstone) as entries:
                        names = tuple(entry.name for entry in entries)
                    if names:
                        if names != (plan_name,):
                            return False
                        duplicate_path = tombstone / plan_name
                        duplicate_raw, duplicate_info = (
                            _read_cleanup_linked_regular(
                                project,
                                duplicate_path,
                                maximum=MAX_DOCUMENT_BYTES + 1,
                            )
                        )
                        expected_identity = (
                            int(proof_info.st_dev),
                            int(proof_info.st_ino),
                        )
                        if (
                            not hmac.compare_digest(duplicate_raw, proof_raw)
                            or int(proof_info.st_nlink) != 2
                            or int(duplicate_info.st_nlink) != 2
                            or (
                                int(duplicate_info.st_dev),
                                int(duplicate_info.st_ino),
                            )
                            != expected_identity
                        ):
                            return False
                        _unlink_exact_cleanup_plan_duplicate_windows(
                            project,
                            duplicate_path,
                            proof,
                            expected_raw=proof_raw,
                            expected_identity=expected_identity,
                        )
                        if not _fsync_directory(parent).durable:
                            return False
                        if not _fsync_directory(tombstone).durable:
                            return False
                    elif int(proof_info.st_nlink) != 1:
                        return False
                _delete_exact_cleanup_directory(
                    project,
                    tombstone,
                    tombstone_snapshot,
                )
                if not _fsync_directory(parent).durable:
                    return False
            elif int(proof_info.st_nlink) != 1:
                return False
            # Keep the compact, content-free proof as the durable receipt that
            # distinguishes successful cleanup from unexplained disappearance.
            durability = _fsync_directory(parent)
            final_proof_raw, final_proof_info = _read_cleanup_linked_regular(
                project,
                proof,
                maximum=MAX_DOCUMENT_BYTES + 1,
            )
            return (
                durability.durable
                and not os.path.lexists(original)
                and not os.path.lexists(tombstone)
                and os.path.lexists(proof)
                and hmac.compare_digest(final_proof_raw, proof_raw)
                and int(final_proof_info.st_nlink) == 1
                and (
                    int(final_proof_info.st_dev),
                    int(final_proof_info.st_ino),
                )
                == proof_identity
            )
        if not os.path.lexists(tombstone):
            return False
        tombstone_info = _safe_directory(tombstone, within=parent)
        tombstone_generation = _cleanup_directory_identity(tombstone_info)
        tombstone_snapshot = _CleanupDirectorySnapshot(
            device=tombstone_generation[0],
            inode=tombstone_generation[1],
            birthtime_ns=tombstone_generation[2],
        )
        with _cleanup_bound_directory_context(project, tombstone):
            bound_info = _safe_directory(tombstone, within=parent)
            if _cleanup_directory_identity(bound_info) != (
                tombstone_snapshot.device,
                tombstone_snapshot.inode,
                tombstone_snapshot.birthtime_ns,
            ):
                return False
            plan_path = _existing_cleanup_plan_path(tombstone)
            if plan_path is None:
                return False
            plan_raw, plan_info = _read_regular_with_info(
                plan_path, within=tombstone, maximum=MAX_DOCUMENT_BYTES + 1
            )
            plan_identity = (int(plan_info.st_dev), int(plan_info.st_ino))
            plan = cls._validate_cleanup_plan_document(
                _parse_document(
                    plan_raw, code="project_update_transaction_cleanup_refused"
                ),
                transaction_ref,
                authority,
            )
            if plan.get("schema") != CLEANUP_PLAN_SCHEMA:
                # A v0.4.15 tombstone is recovery evidence only. Restore it to
                # the original transaction name, then write the durable
                # identity-bound v0.4.16 sidecar before any deletion.
                return False
            root_identity = plan["transaction_root_identity"]
            if (
                int(root_identity["device"]),
                int(root_identity["inode"]),
                root_identity["birthtime_ns"],
            ) != (
                tombstone_snapshot.device,
                tombstone_snapshot.inode,
                tombstone_snapshot.birthtime_ns,
            ):
                return False
            expected_files = {
                item["relative_path"]: (item["size"], item["sha256"])
                for item in plan["files"]
            }
            expected_directories = set(plan["directories"])
            actual_files, actual_directories = (
                cls._cleanup_descendant_snapshot(
                    tombstone,
                    exclude={plan_path.name},
                )
            )
            if not set(actual_files).issubset(expected_files) or not set(
                actual_directories
            ).issubset(expected_directories):
                return False
            for relative, actual in actual_files.items():
                size, digest = expected_files[relative]
                if actual.size != size or actual.sha256 != digest:
                    return False
            for relative in sorted(
                actual_files,
                key=lambda item: len(PurePosixPath(item).parts),
                reverse=True,
            ):
                _delete_exact_cleanup_file(
                    project,
                    tombstone / PurePosixPath(relative),
                    actual_files[relative],
                )
            for relative in sorted(
                actual_directories,
                key=lambda item: len(PurePosixPath(item).parts),
                reverse=True,
            ):
                _delete_exact_cleanup_directory(
                    project,
                    tombstone / PurePosixPath(relative),
                    actual_directories[relative],
                )
            remaining_files, remaining_directories = (
                cls._cleanup_descendant_snapshot(
                    tombstone,
                    exclude={plan_path.name},
                )
            )
            if remaining_files or remaining_directories:
                return False
            try:
                _atomic_move_file_no_replace(plan_path, proof)
            except OSError:
                return False
            moved_proof_raw, moved_proof_info = _read_cleanup_linked_regular(
                project,
                proof,
                maximum=MAX_DOCUMENT_BYTES + 1,
            )
            if (
                not hmac.compare_digest(moved_proof_raw, plan_raw)
                or int(moved_proof_info.st_nlink) != 1
                or (
                    int(moved_proof_info.st_dev),
                    int(moved_proof_info.st_ino),
                )
                != plan_identity
            ):
                return False
            if not _fsync_directory(parent).durable:
                return False
            if not _fsync_directory(tombstone).durable:
                return False
            after_move = _safe_directory(tombstone, within=parent)
            if _cleanup_directory_identity(after_move) != (
                tombstone_snapshot.device,
                tombstone_snapshot.inode,
                tombstone_snapshot.birthtime_ns,
            ):
                return False
            with os.scandir(tombstone) as entries:
                if next(entries, None) is not None:
                    return False
        _delete_exact_cleanup_directory(
            project,
            tombstone,
            tombstone_snapshot,
        )
        if not _fsync_directory(parent).durable:
            return False
        # The proof is the plan itself and remains as a small durable receipt.
        # A hard exit at any earlier step is recoverable by the branches above.
        final_proof_raw, final_proof_info = _read_cleanup_linked_regular(
            project,
            proof,
            maximum=MAX_DOCUMENT_BYTES + 1,
        )
        return (
            not os.path.lexists(original)
            and not os.path.lexists(tombstone)
            and os.path.lexists(proof)
            and hmac.compare_digest(final_proof_raw, plan_raw)
            and int(final_proof_info.st_nlink) == 1
            and (
                int(final_proof_info.st_dev),
                int(final_proof_info.st_ino),
            )
            == plan_identity
        )

    @staticmethod
    def _validate_cleanup_plan_document(
        value: Any, transaction_ref: str, authority: str
    ) -> dict[str, Any]:
        if (
            type(value) is dict
            and value.get("schema") == RESERVATION_ABORT_CLEANUP_PLAN_SCHEMA
        ):
            return ReservedProjectUpdateTransaction._validate_abort_cleanup_plan_document(
                value,
                transaction_ref,
                authority,
            )
        legacy_expected = {
            "cleanup_authority_sha256",
            "directories",
            "files",
            "intent_sha256",
            "schema",
            "terminal_checkpoint_sha256",
            "transaction_logical_ref",
            "transaction_ref",
        }
        current_expected = legacy_expected | {"transaction_root_identity"}
        is_legacy = bool(
            type(value) is dict
            and value.get("schema") == LEGACY_CLEANUP_PLAN_SCHEMA
            and set(value) == legacy_expected
        )
        is_current = bool(
            type(value) is dict
            and value.get("schema") == CLEANUP_PLAN_SCHEMA
            and set(value) == current_expected
        )
        if (
            type(value) is not dict
            or not (is_legacy or is_current)
            or value.get("transaction_ref") != transaction_ref
            or value.get("transaction_logical_ref")
            != _transaction_logical_ref(transaction_ref)
            or value.get("cleanup_authority_sha256") != authority
            or type(value.get("files")) is not list
            or type(value.get("directories")) is not list
        ):
            raise _fail("project_update_transaction_cleanup_refused")
        if is_current:
            root_identity = value.get("transaction_root_identity")
            birthtime_ns = (
                root_identity.get("birthtime_ns")
                if type(root_identity) is dict
                else None
            )
            if (
                type(root_identity) is not dict
                or set(root_identity)
                != {"birthtime_ns", "device", "inode"}
                or type(root_identity.get("device")) is not int
                or root_identity["device"] < 0
                or type(root_identity.get("inode")) is not int
                or root_identity["inode"] <= 0
                or (
                    os.name == "nt"
                    and (
                        type(birthtime_ns) is not int
                        or birthtime_ns <= 0
                    )
                )
                or (os.name != "nt" and birthtime_ns is not None)
            ):
                raise _fail("project_update_transaction_cleanup_refused")
        _digest(value.get("intent_sha256"), code="project_update_transaction_cleanup_refused")
        _digest(
            value.get("terminal_checkpoint_sha256"),
            code="project_update_transaction_cleanup_refused",
        )
        seen: set[str] = set()
        ordered_paths: list[str] = []
        for item in value["files"]:
            if (
                type(item) is not dict
                or set(item) != {"relative_path", "sha256", "size"}
                or type(item.get("size")) is not int
                or item["size"] < 0
                or item["size"] > MAX_RUNTIME_CANDIDATE_FILE_BYTES
            ):
                raise _fail("project_update_transaction_cleanup_refused")
            relative = _logical_path(item["relative_path"])
            self_name = (
                CLEANUP_PLAN_NAME if is_current else LEGACY_CLEANUP_PLAN_NAME
            )
            if relative in seen or relative == self_name:
                raise _fail("project_update_transaction_cleanup_refused")
            seen.add(relative)
            ordered_paths.append(relative)
            _digest(item["sha256"], code="project_update_transaction_cleanup_refused")
        if ordered_paths != sorted(ordered_paths):
            raise _fail("project_update_transaction_cleanup_refused")
        directories = tuple(value["directories"])
        if tuple(sorted(set(directories))) != directories:
            raise _fail("project_update_transaction_cleanup_refused")
        for relative in directories:
            _logical_path(relative)
        return value

    @staticmethod
    def _descendant_names(root: Path) -> tuple[set[str], set[str]]:
        files: set[str] = set()
        directories: set[str] = set()
        stack = [root]
        seen = 0
        while stack:
            directory = stack.pop()
            _safe_directory(directory, within=root)
            try:
                scanner = os.scandir(directory)
            except OSError:
                raise _fail("project_update_transaction_path_unsafe") from None
            try:
                with scanner:
                    for entry in scanner:
                        seen += 1
                        if seen > MAX_TRANSACTION_DESCENDANT_SCAN_ENTRIES:
                            raise _fail(
                                "project_update_transaction_scan_incomplete"
                            )
                        path = Path(entry.path)
                        _within(path, root)
                        try:
                            info = path.lstat()
                        except OSError:
                            raise _fail(
                                "project_update_transaction_path_unsafe"
                            ) from None
                        if stat.S_ISLNK(info.st_mode) or _is_reparse(info):
                            raise _fail(
                                "project_update_transaction_path_unsafe"
                            )
                        relative = path.relative_to(root).as_posix()
                        if stat.S_ISDIR(info.st_mode):
                            directories.add(relative)
                            stack.append(path)
                        elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                            files.add(relative)
                        else:
                            raise _fail(
                                "project_update_transaction_path_unsafe"
                            )
            except OSError:
                raise _fail("project_update_transaction_path_unsafe") from None
        return files, directories

    @staticmethod
    def _descendant_snapshot(
        root: Path, *, exclude: set[str]
    ) -> tuple[dict[str, tuple[int, str]], set[str]]:
        files: dict[str, tuple[int, str]] = {}
        directories: set[str] = set()
        seen = 0

        def walk(directory: Path) -> None:
            nonlocal seen
            _safe_directory(directory, within=root)
            try:
                entries = list(os.scandir(directory))
            except OSError:
                raise _fail("project_update_transaction_path_unsafe") from None
            for entry in entries:
                seen += 1
                if seen > MAX_TRANSACTION_DESCENDANT_SCAN_ENTRIES:
                    raise _fail("project_update_transaction_scan_incomplete")
                path = Path(entry.path)
                _within(path, root)
                try:
                    info = path.lstat()
                except OSError:
                    raise _fail("project_update_transaction_path_unsafe") from None
                if stat.S_ISLNK(info.st_mode) or _is_reparse(info):
                    raise _fail("project_update_transaction_path_unsafe")
                relative = path.relative_to(root).as_posix()
                if stat.S_ISDIR(info.st_mode):
                    directories.add(relative)
                    walk(path)
                elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                    if relative not in exclude:
                        digest, size, _after = _hash_regular_with_info(
                            path,
                            within=root,
                            maximum=MAX_RUNTIME_CANDIDATE_FILE_BYTES,
                        )
                        files[relative] = (size, digest)
                else:
                    raise _fail("project_update_transaction_path_unsafe")

        walk(root)
        return files, directories

    @staticmethod
    def _cleanup_descendant_snapshot(
        root: Path,
        *,
        exclude: set[str],
    ) -> tuple[
        dict[str, _CleanupFileSnapshot],
        dict[str, _CleanupDirectorySnapshot],
    ]:
        """Capture the transient identities later bound to exact deletion."""

        files: dict[str, _CleanupFileSnapshot] = {}
        directories: dict[str, _CleanupDirectorySnapshot] = {}
        seen = 0

        def walk(directory: Path) -> None:
            nonlocal seen
            directory_before = _safe_directory(directory, within=root)
            directory_identity = _cleanup_directory_identity(
                directory_before
            )
            try:
                entries = list(os.scandir(directory))
            except OSError:
                raise _fail("project_update_transaction_path_unsafe") from None
            for entry in entries:
                seen += 1
                if seen > MAX_TRANSACTION_DESCENDANT_SCAN_ENTRIES:
                    raise _fail("project_update_transaction_scan_incomplete")
                path = Path(entry.path)
                _within(path, root)
                try:
                    info = path.lstat()
                except OSError:
                    raise _fail("project_update_transaction_path_unsafe") from None
                if stat.S_ISLNK(info.st_mode) or _is_reparse(info):
                    raise _fail("project_update_transaction_path_unsafe")
                relative = path.relative_to(root).as_posix()
                if stat.S_ISDIR(info.st_mode):
                    child_generation = _cleanup_directory_identity(info)
                    directories[relative] = _CleanupDirectorySnapshot(
                        device=child_generation[0],
                        inode=child_generation[1],
                        birthtime_ns=child_generation[2],
                    )
                    walk(path)
                    after = _safe_directory(path, within=root)
                    if (
                        _cleanup_directory_identity(after)
                        != child_generation
                    ):
                        raise _fail("project_update_transaction_path_unsafe")
                elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                    if relative not in exclude:
                        digest, size, after = _hash_regular_with_info(
                            path,
                            within=root,
                            maximum=MAX_RUNTIME_CANDIDATE_FILE_BYTES,
                        )
                        files[relative] = _CleanupFileSnapshot(
                            size=size,
                            sha256=digest,
                            device=int(after.st_dev),
                            inode=int(after.st_ino),
                            mtime_ns=int(after.st_mtime_ns),
                        )
                else:
                    raise _fail("project_update_transaction_path_unsafe")
            directory_after = _safe_directory(directory, within=root)
            if (
                _cleanup_directory_identity(directory_after)
                != directory_identity
            ):
                raise _fail("project_update_transaction_path_unsafe")

        walk(root)
        return files, directories

    def _load_exact_state(
        self,
        *,
        guard_locked: bool = False,
        verify_candidate_content: bool = False,
    ) -> tuple[
        ProjectUpdateIntent,
        JournalInspection,
        dict[str, Any] | None,
        dict[str, Any] | None,
    ]:
        _safe_existing_chain(self._transaction_root, directory=True)
        reservation_document = _parse_document(
            _read_regular(
                self._transaction_root / "marker.json",
                within=self._transaction_root,
                maximum=MAX_DOCUMENT_BYTES + 1,
            ),
            code="project_update_transaction_intent_invalid",
        )
        reservation = ProjectUpdateReservation.from_document(reservation_document)
        if (
            reservation.transaction_ref != self._transaction_root.name
            or (
                hasattr(self, "reservation")
                and reservation != self.reservation
            )
        ):
            raise _fail("project_update_transaction_intent_invalid")
        self.reservation = reservation
        intent_document = _parse_document(
            _read_regular(
                self._transaction_root / "intent.json",
                within=self._transaction_root,
                maximum=MAX_DOCUMENT_BYTES + 1,
            ),
            code="project_update_transaction_intent_invalid",
        )
        intent = ProjectUpdateIntent.from_document(intent_document)
        if (
            intent.transaction_ref != self._transaction_root.name
            or intent.reservation_sha256 != reservation.sha256
            or _reservation_from_intent(intent) != reservation
        ):
            raise _fail("project_update_transaction_intent_invalid")
        intent_seal = _parse_document(
            _read_regular(
                self._transaction_root / "intent-seal.json",
                within=self._transaction_root,
                maximum=MAX_DOCUMENT_BYTES + 1,
            ),
            code="project_update_transaction_intent_invalid",
        )
        expected_intent_seal = {
            "intent_sha256": intent.sha256,
            "preimages_inventory_sha256": sha256_document(
                {"records": [record.document() for record in intent.preimages]}
            ),
            "private_bindings_inventory_sha256": sha256_document(
                {"records": [record.document() for record in intent.private_bindings]}
            ),
            "reservation_sha256": reservation.sha256,
            "runtime_candidate_provider_inventory_sha256": (
                intent.runtime_candidate.provider_inventory_sha256
            ),
            "runtime_candidate_provider_candidate_sha256": (
                intent.runtime_candidate.provider_candidate_sha256
            ),
            "runtime_candidate_path_identities_sha256": (
                intent.runtime_candidate.path_identities_sha256
            ),
            "runtime_candidate_recursive_tree_sha256": (
                intent.runtime_candidate.recursive_tree_sha256
            ),
            "runtime_candidate_seal_sha256": intent.runtime_candidate.seal_sha256,
            "schema": INTENT_SEAL_SCHEMA,
            "transaction_ref": intent.transaction_ref,
        }
        if not hmac.compare_digest(
            canonical_json_bytes(intent_seal),
            canonical_json_bytes(expected_intent_seal),
        ):
            raise _fail("project_update_transaction_intent_invalid")
        for root_name, records in (
            ("preimages", intent.preimages),
            (PRIVATE_BINDINGS_NAME, intent.private_bindings),
        ):
            _safe_directory(self._transaction_root / root_name, within=self._transaction_root)
            for record in records:
                value = _read_regular(
                    self._transaction_root / PurePosixPath(record.relative_path),
                    within=self._transaction_root,
                )
                if len(value) != record.size or sha256_bytes(value) != record.sha256:
                    raise _fail("project_update_transaction_intent_invalid")
        static_record = next(
            record
            for record in intent.private_bindings
            if record.logical_key == "static-receipt-postimage"
        )
        static_receipt_bytes = _read_regular(
            self._transaction_root / PurePosixPath(static_record.relative_path),
            within=self._transaction_root,
        )
        plan_digest, target_binding_digest = _validate_static_receipt_postimage(
            static_receipt_bytes, reservation=reservation
        )
        if (
            plan_digest != intent.static_receipt_domain_plan_sha256
            or target_binding_digest
            != intent.static_receipt_domain_target_binding_sha256
        ):
            raise _fail("project_update_transaction_intent_invalid")
        path_identity_record = next(
            record
            for record in intent.private_bindings
            if record.logical_key == "runtime-candidate-path-identities"
        )
        path_identity_document = _parse_document(
            _read_regular(
                self._transaction_root
                / PurePosixPath(path_identity_record.relative_path),
                within=self._transaction_root,
            ),
            code="project_update_transaction_candidate_invalid",
        )
        if (
            set(path_identity_document) != {"path_identities", "schema"}
            or path_identity_document.get("schema")
            != RUNTIME_PATH_IDENTITIES_SCHEMA
            or sha256_document(path_identity_document.get("path_identities"))
            != intent.runtime_candidate.path_identities_sha256
        ):
            raise _fail("project_update_transaction_candidate_invalid")
        guard_path = self._transaction_root / "append.guard"
        if guard_locked:
            guard_info = _safe_regular(guard_path, within=self._transaction_root)
            if guard_info.st_size != 1:
                raise _fail("project_update_transaction_intent_invalid")
        elif _read_regular(guard_path, within=self._transaction_root) != b"\x00":
            raise _fail("project_update_transaction_intent_invalid")
        journal_exists = os.path.lexists(self._transaction_root / "checkpoints.jsonl")
        journal = self._read_journal(intent)
        runtime_intent_recorded = any(
            item.phase == "runtime" and item.stage == "intent"
            for item in journal.verified_prefix
        )
        preapproval_cancel_requested = any(
            item.phase == "preapproval_cancel_requested"
            and item.stage == "intent"
            for item in journal.verified_prefix
        )
        candidate_removal_authorized = (
            runtime_intent_recorded or preapproval_cancel_requested
        )
        candidate_path = self._transaction_root / RUNTIME_CANDIDATE_NAME
        candidate_seal_path = self._transaction_root / RUNTIME_CANDIDATE_SEAL_NAME
        candidate_present = os.path.lexists(candidate_path)
        candidate_seal_present = os.path.lexists(candidate_seal_path)
        candidate_files: set[str] = set()
        candidate_directories: set[str] = set()
        if candidate_present:
            binding = intent.runtime_candidate
            if not candidate_seal_present:
                raise _fail("project_update_transaction_candidate_invalid")
            if verify_candidate_content:
                tree = _runtime_candidate_tree_inventory(
                    candidate_path, transaction_root=self._transaction_root
                )
                if (
                    tree.recursive_tree_sha256 != binding.recursive_tree_sha256
                    or tree.inventory_count != binding.inventory_count
                    or tree.file_count != binding.file_count
                    or tree.total_bytes != binding.inventory_bytes
                ):
                    raise _fail("project_update_transaction_candidate_invalid")
            nested_files, nested_directories = self._descendant_names(candidate_path)
            if (
                len(nested_files) + len(nested_directories)
                != binding.inventory_count
            ):
                raise _fail("project_update_transaction_candidate_invalid")
            candidate_directories.add(RUNTIME_CANDIDATE_NAME)
            candidate_files.update(
                f"{RUNTIME_CANDIDATE_NAME}/{item}" for item in nested_files
            )
            candidate_directories.update(
                f"{RUNTIME_CANDIDATE_NAME}/{item}" for item in nested_directories
            )
        elif not candidate_removal_authorized:
            raise _fail("project_update_transaction_candidate_invalid")
        if candidate_seal_present:
            seal_raw = _read_regular(
                candidate_seal_path,
                within=self._transaction_root,
                maximum=MAX_DOCUMENT_BYTES + 1,
            )
            if sha256_bytes(seal_raw) != intent.runtime_candidate.seal_sha256:
                raise _fail("project_update_transaction_candidate_invalid")
            bound_tree = RuntimeCandidateTreeInventory(
                recursive_tree_sha256=intent.runtime_candidate.recursive_tree_sha256,
                inventory_count=intent.runtime_candidate.inventory_count,
                file_count=intent.runtime_candidate.file_count,
                total_bytes=intent.runtime_candidate.inventory_bytes,
            )
            parsed_seal = ReservedProjectUpdateTransaction._candidate_seal(
                seal_raw,
                reservation=reservation,
                provider_inventory_sha256=(
                    intent.runtime_candidate.provider_inventory_sha256
                ),
                tree=bound_tree,
            )
            if (
                parsed_seal["candidate_sha256"]
                != intent.runtime_candidate.provider_candidate_sha256
                or sha256_document(parsed_seal["path_identities"])
                != intent.runtime_candidate.path_identities_sha256
                or parsed_seal["runtime_parent_existed_before"]
                is not intent.runtime_candidate.runtime_parent_existed_before
                or parsed_seal["recursive_directory_durability_verified"]
                is not intent.runtime_candidate.recursive_directory_durability_verified
                or parsed_seal["seal_parent_durability_required"]
                is not intent.runtime_candidate.seal_parent_durability_required
            ):
                raise _fail("project_update_transaction_candidate_invalid")
        elif not candidate_removal_authorized:
            raise _fail("project_update_transaction_candidate_invalid")
        cancelled_checkpoint = next(
            (
                item
                for item in journal.verified_prefix
                if item.phase == "preapproval_cancelled"
            ),
            None,
        )
        if cancelled_checkpoint is not None:
            if candidate_present or candidate_seal_present:
                raise _fail("project_update_transaction_candidate_invalid")
            exact_candidate_absence = _candidate_absence_observation(
                self._transaction_root,
                transaction_ref=intent.transaction_ref,
                reservation_sha256=intent.reservation_sha256,
                intent_sha256=intent.sha256,
                runtime_candidate_binding_sha256=(
                    _runtime_candidate_binding_sha256(intent)
                ),
            )
            if (
                cancelled_checkpoint.candidate_absence_observation_sha256
                != exact_candidate_absence
            ):
                raise _fail("project_update_transaction_candidate_invalid")
        repair_preimage_path = (
            self._transaction_root / RUNTIME_REPAIR_PREIMAGE_NAME
        )
        repair_preimage_present = os.path.lexists(repair_preimage_path)
        repair_files: set[str] = set()
        repair_directories: set[str] = set()
        repair_binding = intent.runtime_candidate
        if repair_preimage_present:
            if (
                not runtime_intent_recorded
                or not repair_binding.existing_runtime_repair_required
                or repair_binding.existing_runtime_inventory_sha256 is None
            ):
                raise _fail("project_update_transaction_candidate_invalid")
            (
                repair_sha256,
                repair_count,
                repair_bytes,
                repair_files,
                repair_directories,
            ) = _runtime_repair_preimage_inventory(
                repair_preimage_path,
                transaction_root=self._transaction_root,
            )
            if (
                repair_sha256
                != repair_binding.existing_runtime_inventory_sha256
                or repair_count
                != repair_binding.existing_runtime_inventory_count
                or repair_bytes
                != repair_binding.existing_runtime_inventory_bytes
            ):
                raise _fail("project_update_transaction_candidate_invalid")
        elif (
            repair_binding.existing_runtime_repair_required
            and runtime_intent_recorded
            and not candidate_present
        ):
            # Once the candidate has left the transaction, the exact old
            # runtime must remain here until authenticated terminal cleanup.
            raise _fail("project_update_transaction_candidate_invalid")
        reservation_backlink = self._read_reservation_backlink(intent)
        backlink = self._read_backlink(intent)
        cleanup = self._read_cleanup_plan(intent, journal)
        expected_directories = {"preimages", PRIVATE_BINDINGS_NAME}
        expected_directories.update(candidate_directories)
        expected_directories.update(repair_directories)
        expected_files = {
            "marker.json",
            "intent.json",
            "intent-seal.json",
            "append.guard",
            RESERVATION_LOCK_BACKLINK_NAME,
        }
        expected_files.update(record.relative_path for record in intent.preimages)
        expected_files.update(record.relative_path for record in intent.private_bindings)
        expected_files.update(candidate_files)
        expected_files.update(repair_files)
        if candidate_seal_present:
            expected_files.add(RUNTIME_CANDIDATE_SEAL_NAME)
        if journal_exists:
            expected_files.add("checkpoints.jsonl")
        if backlink is not None:
            expected_files.add(SEALED_LOCK_BACKLINK_NAME)
        if cleanup is not None:
            expected_files.add(_cleanup_plan_name_for_document(cleanup))
            if (
                cleanup.get("schema") == CLEANUP_PLAN_SCHEMA
                and os.path.lexists(
                    self._transaction_root / LEGACY_CLEANUP_PLAN_NAME
                )
            ):
                expected_files.add(LEGACY_CLEANUP_PLAN_NAME)
        actual_files, actual_directories = self._descendant_names(
            self._transaction_root
        )
        if actual_files != expected_files or actual_directories != expected_directories:
            raise _fail("project_update_transaction_invalid")
        if backlink is not None and backlink.get(
            "reservation_lock_backlink_sha256"
        ) != sha256_document(reservation_backlink):
            raise _fail("project_update_transaction_lock_invalid")
        return intent, journal, backlink, cleanup

    def _read_reservation_backlink(
        self, intent: ProjectUpdateIntent
    ) -> dict[str, Any]:
        path = self._transaction_root / RESERVATION_LOCK_BACKLINK_NAME
        value = _parse_document(
            _read_regular(path, within=self._transaction_root, maximum=MAX_DOCUMENT_BYTES + 1),
            code="project_update_transaction_lock_invalid",
        )
        expected = {
            "live_lock_observation_sha256",
            "lock_identity",
            "lock_sha256",
            "ownership_nonce",
            "project_identity_sha256",
            "reservation_sha256",
            "schema",
            "transaction_logical_ref",
            "transaction_ref",
        }
        identity = value.get("lock_identity")
        if (
            set(value) != expected
            or value.get("schema") != RESERVATION_LOCK_BACKLINK_SCHEMA
            or value.get("reservation_sha256") != intent.reservation_sha256
            or value.get("ownership_nonce") != intent.ownership_nonce
            or value.get("project_identity_sha256") != intent.project_identity_sha256
            or value.get("transaction_logical_ref") != intent.transaction_logical_ref
            or value.get("transaction_ref") != intent.transaction_ref
            or type(identity) is not dict
            or set(identity) != {"device", "inode", "modified_ns", "size"}
            or any(type(item) is not int for item in identity.values())
        ):
            raise _fail("project_update_transaction_lock_invalid")
        _digest(value.get("lock_sha256"), code="project_update_transaction_lock_invalid")
        expected_observation = {
            "lock_identity": identity,
            "lock_logical_ref": PROJECT_UPDATE_LOCK_LOGICAL,
            "lock_sha256": value["lock_sha256"],
            "schema": LOCK_OBSERVATION_SCHEMA,
            "state": "present",
            "transaction_ref": intent.transaction_ref,
        }
        if value.get("live_lock_observation_sha256") != sha256_document(
            expected_observation
        ):
            raise _fail("project_update_transaction_lock_invalid")
        return value

    def _read_backlink(self, intent: ProjectUpdateIntent) -> dict[str, Any] | None:
        path = self._transaction_root / SEALED_LOCK_BACKLINK_NAME
        if not os.path.lexists(path):
            return None
        value = _parse_document(
            _read_regular(path, within=self._transaction_root, maximum=MAX_DOCUMENT_BYTES + 1),
            code="project_update_transaction_lock_invalid",
        )
        expected = {
            "intent_sha256",
            "live_lock_observation_sha256",
            "lock_identity",
            "lock_sha256",
            "ownership_nonce",
            "project_identity_sha256",
            "reservation_lock_backlink_sha256",
            "reservation_sha256",
            "schema",
            "transaction_logical_ref",
            "transaction_ref",
        }
        identity = value.get("lock_identity")
        if (
            set(value) != expected
            or value.get("schema") != LOCK_BACKLINK_SCHEMA
            or value.get("intent_sha256") != intent.sha256
            or value.get("ownership_nonce") != intent.ownership_nonce
            or value.get("project_identity_sha256") != intent.project_identity_sha256
            or value.get("reservation_sha256") != intent.reservation_sha256
            or value.get("transaction_logical_ref") != intent.transaction_logical_ref
            or value.get("transaction_ref") != intent.transaction_ref
            or type(identity) is not dict
            or set(identity) != {"device", "inode", "modified_ns", "size"}
            or any(type(item) is not int for item in identity.values())
        ):
            raise _fail("project_update_transaction_lock_invalid")
        _digest(value.get("lock_sha256"), code="project_update_transaction_lock_invalid")
        _digest(
            value.get("reservation_lock_backlink_sha256"),
            code="project_update_transaction_lock_invalid",
        )
        _digest(
            value.get("live_lock_observation_sha256"),
            code="project_update_transaction_lock_invalid",
        )
        expected_observation = {
            "lock_identity": identity,
            "lock_logical_ref": PROJECT_UPDATE_LOCK_LOGICAL,
            "lock_sha256": value["lock_sha256"],
            "schema": LOCK_OBSERVATION_SCHEMA,
            "state": "present",
            "transaction_ref": intent.transaction_ref,
        }
        if value["live_lock_observation_sha256"] != sha256_document(
            expected_observation
        ):
            raise _fail("project_update_transaction_lock_invalid")
        return value

    def _read_cleanup_plan(
        self, intent: ProjectUpdateIntent, journal: JournalInspection
    ) -> dict[str, Any] | None:
        path = _existing_cleanup_plan_path(self._transaction_root)
        if path is None:
            return None
        value = _parse_document(
            _read_regular(path, within=self._transaction_root, maximum=MAX_DOCUMENT_BYTES + 1),
            code="project_update_transaction_cleanup_refused",
        )
        authority = value.get("cleanup_authority_sha256") if type(value) is dict else None
        if type(authority) is not str:
            raise _fail("project_update_transaction_cleanup_refused")
        self._validate_cleanup_plan_document(value, intent.transaction_ref, authority)
        if (
            value.get("intent_sha256") != intent.sha256
            or journal.state != "exact"
            or value.get("terminal_checkpoint_sha256") != journal.head_sha256
            or not journal.verified_prefix
            or journal.verified_prefix[-1].phase != "completed"
        ):
            raise _fail("project_update_transaction_cleanup_refused")
        return value

    def _read_journal(self, intent: ProjectUpdateIntent) -> JournalInspection:
        path = self._transaction_root / "checkpoints.jsonl"
        if not os.path.lexists(path):
            return JournalInspection("exact", (), None, 0, None)
        raw = _read_regular(path, within=self._transaction_root, maximum=MAX_JOURNAL_BYTES)
        if not raw:
            return JournalInspection(
                "corrupt", (), sha256_bytes(raw), 0, "journal_empty"
            )
        checkpoints: list[ProjectUpdateCheckpoint] = []
        offset = 0
        for physical in raw.splitlines(keepends=True):
            if not physical.endswith(b"\n"):
                tail = raw[offset:]
                return JournalInspection(
                    "tail_torn",
                    tuple(checkpoints),
                    sha256_bytes(tail),
                    len(tail),
                    "journal_tail_torn",
                )
            line = physical[:-1]
            try:
                checkpoint = self._checkpoint_from_line(
                    line, intent, checkpoints
                )
                if not _matching_candidates((*checkpoints, checkpoint), intent):
                    raise _fail("project_update_transaction_state_transition_invalid")
            except ProjectUpdateTransactionError:
                tail = raw[offset:]
                return JournalInspection(
                    "corrupt",
                    tuple(checkpoints),
                    sha256_bytes(tail),
                    len(tail),
                    "journal_record_or_chain_invalid",
                )
            checkpoints.append(checkpoint)
            offset += len(physical)
        return JournalInspection("exact", tuple(checkpoints), None, 0, None)

    def _checkpoint_from_line(
        self,
        line: bytes,
        intent: ProjectUpdateIntent,
        prefix: Sequence[ProjectUpdateCheckpoint],
    ) -> ProjectUpdateCheckpoint:
        value = _parse_json(line, code="project_update_transaction_checkpoint_invalid")
        if type(value) is not dict or not hmac.compare_digest(
            line, canonical_json_bytes(value)
        ):
            raise _fail("project_update_transaction_checkpoint_invalid")
        required = {
            "intent_sha256",
            "live_lock_observation_sha256",
            "observed_state_sha256",
            "phase",
            "previous_checkpoint_sha256",
            "schema",
            "seq",
            "stage",
            "transaction_ref",
        }
        optional = {
            "approval_mac_sha256",
            "approval_reference_sha256",
            "candidate_absence_observation_sha256",
            "candidate_cleanup_receipt_sha256",
            "cancellation_plan_sha256",
            "claim_mac_sha256",
            "claim_evidence_digests",
            "claim_receipt_sha256",
            "component_ref",
            "runtime_candidate_binding_sha256",
        }
        expected_previous = (
            prefix[-1].checkpoint_sha256
            if prefix
            else CHECKPOINT_CHAIN_START_SHA256
        )
        if (
            not required.issubset(value)
            or not set(value).issubset(required | optional)
            or value.get("schema") != CHECKPOINT_SCHEMA
            or type(value.get("seq")) is not int
            or value["seq"] != len(prefix) + 1
            or value.get("phase") not in ALLOWED_CHECKPOINT_PHASES
            or value.get("stage") not in {"intent", "verified"}
            or value.get("transaction_ref") != intent.transaction_ref
            or value.get("intent_sha256") != intent.sha256
            or value.get("previous_checkpoint_sha256") != expected_previous
        ):
            raise _fail("project_update_transaction_checkpoint_invalid")
        for name in (
            "live_lock_observation_sha256",
            "observed_state_sha256",
            *(
                key
                for key in (
                    "approval_mac_sha256",
                    "approval_reference_sha256",
                    "candidate_absence_observation_sha256",
                    "candidate_cleanup_receipt_sha256",
                    "cancellation_plan_sha256",
                    "claim_mac_sha256",
                    "claim_receipt_sha256",
                    "runtime_candidate_binding_sha256",
                )
                if key in value
            ),
        ):
            _digest(value[name], code="project_update_transaction_checkpoint_invalid")
        component_ref = value.get("component_ref")
        if component_ref is not None:
            _token(component_ref, code="project_update_transaction_checkpoint_invalid")
        claim_evidence_value = value.get("claim_evidence_digests")
        if value.get("phase") == "claim_succeeded":
            try:
                claim_evidence = _claim_evidence_digests(
                    claim_evidence_value,
                    intent=intent,
                    approval_reference_sha256=value.get("approval_reference_sha256"),
                    claim_receipt_sha256=value.get("claim_receipt_sha256"),
                    claim_mac_sha256=value.get("claim_mac_sha256"),
                )
            except ProjectUpdateTransactionError:
                raise _fail("project_update_transaction_checkpoint_invalid") from None
        else:
            if claim_evidence_value is not None:
                raise _fail("project_update_transaction_checkpoint_invalid")
            claim_evidence = ()
        cancellation_plan = value.get("cancellation_plan_sha256")
        candidate_binding = value.get("runtime_candidate_binding_sha256")
        cleanup_receipt = value.get("candidate_cleanup_receipt_sha256")
        candidate_absence = value.get("candidate_absence_observation_sha256")
        if value.get("phase") == "preapproval_cancel_requested":
            if (
                cancellation_plan is None
                or candidate_binding != _runtime_candidate_binding_sha256(intent)
                or cleanup_receipt is not None
                or candidate_absence is not None
            ):
                raise _fail("project_update_transaction_checkpoint_invalid")
        elif value.get("phase") == "preapproval_cancelled":
            requested = prefix[-1] if prefix else None
            if (
                requested is None
                or requested.phase != "preapproval_cancel_requested"
                or cancellation_plan != requested.cancellation_plan_sha256
                or candidate_binding != requested.runtime_candidate_binding_sha256
                or cleanup_receipt is None
                or candidate_absence is None
            ):
                raise _fail("project_update_transaction_checkpoint_invalid")
        elif any(
            item is not None
            for item in (
                cancellation_plan,
                candidate_binding,
                cleanup_receipt,
                candidate_absence,
            )
        ):
            raise _fail("project_update_transaction_checkpoint_invalid")
        return ProjectUpdateCheckpoint(
            seq=value["seq"],
            phase=value["phase"],
            stage=value["stage"],
            previous_checkpoint_sha256=expected_previous,
            observed_state_sha256=value["observed_state_sha256"],
            live_lock_observation_sha256=value["live_lock_observation_sha256"],
            checkpoint_sha256=sha256_bytes(line),
            component_ref=component_ref,
            approval_reference_sha256=value.get("approval_reference_sha256"),
            approval_mac_sha256=value.get("approval_mac_sha256"),
            claim_receipt_sha256=value.get("claim_receipt_sha256"),
            claim_mac_sha256=value.get("claim_mac_sha256"),
            claim_evidence_digests=claim_evidence,
            cancellation_plan_sha256=cancellation_plan,
            runtime_candidate_binding_sha256=candidate_binding,
            candidate_cleanup_receipt_sha256=cleanup_receipt,
            candidate_absence_observation_sha256=candidate_absence,
        )


def inspect_prelock_orphans(project_root: Path | str) -> tuple[OrphanInspection, ...]:
    """Content-free classification of reserved, sealed, and damaged update roots."""

    project = _absolute(project_root)
    _safe_existing_chain(project, directory=True)
    parent = project / PurePosixPath(TRANSACTION_ROOT_LOGICAL)
    if not os.path.lexists(parent):
        return ()
    _safe_existing_chain(parent, directory=True)
    result: list[OrphanInspection] = []
    try:
        entries: list[tuple[str, str]] = []
        seen = 0
        with os.scandir(parent) as scanner:
            for entry in scanner:
                seen += 1
                if seen > MAX_TERMINAL_CLEANUP_SCAN_ENTRIES:
                    raise _fail(
                        "project_update_transaction_scan_incomplete"
                    )
                if TRANSACTION_REF_RE.fullmatch(entry.name) is not None:
                    entries.append((entry.name, entry.path))
    except OSError:
        raise _fail("project_update_transaction_path_unsafe") from None
    entries.sort(key=lambda item: item[0])
    for ref, entry_path in entries:
        logical = _transaction_logical_ref(ref)
        try:
            info = Path(entry_path).lstat()
            if (
                not stat.S_ISDIR(info.st_mode)
                or stat.S_ISLNK(info.st_mode)
                or _is_reparse(info)
            ):
                raise _fail("project_update_transaction_path_unsafe")
            transaction = ProjectUpdateTransaction.open(
                project,
                ref,
                verify_candidate_content=False,
            )
            inspection = transaction.inspect(
                verify_candidate_content=False
            )
            if (
                not inspection.lock_backlinked
                and inspection.journal.state == "exact"
                and not inspection.journal.verified_prefix
            ):
                classification = "intent_sealed_lock_binding_incomplete"
            elif inspection.journal.state != "exact":
                classification = "manual_review_journal_degraded"
            else:
                classification = "not_prelock_orphan"
            evidence = inspection.intent_sha256
        except ProjectUpdateTransactionError as transaction_failure:
            if (
                transaction_failure.code
                == "project_update_transaction_scan_incomplete"
            ):
                raise
            try:
                reserved = ReservedProjectUpdateTransaction.open(project, ref)
                files, directories = ProjectUpdateTransaction._descendant_names(
                    Path(entry_path)
                )
                candidate_present = RUNTIME_CANDIDATE_NAME in directories
                candidate_seal_present = RUNTIME_CANDIDATE_SEAL_NAME in files
                intent_present = "intent.json" in files or "intent-seal.json" in files
                intent_material_present = (
                    intent_present
                    or "preimages" in directories
                    or PRIVATE_BINDINGS_NAME in directories
                    or any(item.startswith("preimages/") for item in files)
                    or any(
                        item.startswith(f"{PRIVATE_BINDINGS_NAME}/")
                        for item in files
                    )
                )
                reservation_backlink_present = (
                    RESERVATION_LOCK_BACKLINK_NAME in files
                )
                lock_state = "absent"
                if os.path.lexists(reserved._lock_path):
                    try:
                        reserved._present_lock()
                        lock_state = "exact"
                    except ProjectUpdateTransactionError:
                        lock_state = "conflict_or_unsafe"
                backlink_exact = False
                if reservation_backlink_present and lock_state == "exact":
                    try:
                        reserved._verify_reservation_backlink()
                        backlink_exact = True
                    except ProjectUpdateTransactionError:
                        backlink_exact = False
                allowed_files = {
                    "append.guard",
                    "marker.json",
                    RESERVATION_LOCK_BACKLINK_NAME,
                    RESERVATION_ABORT_INTENT_NAME,
                    RESERVATION_ABORT_RECEIPT_NAME,
                    RUNTIME_CANDIDATE_SEAL_NAME,
                    "intent.json",
                    "intent-seal.json",
                    SEALED_LOCK_BACKLINK_NAME,
                }
                allowed_directories = {
                    "preimages",
                    PRIVATE_BINDINGS_NAME,
                    RUNTIME_CANDIDATE_NAME,
                }
                unexpected = any(
                    item not in allowed_files
                    and not item.startswith(f"{RUNTIME_CANDIDATE_NAME}/")
                    and not item.startswith("preimages/")
                    and not item.startswith(f"{PRIVATE_BINDINGS_NAME}/")
                    for item in files
                ) or any(
                    item not in allowed_directories
                    and not item.startswith(f"{RUNTIME_CANDIDATE_NAME}/")
                    for item in directories
                )
                abort_receipt = None
                abort_receipt_pending = False
                if (
                    RESERVATION_ABORT_INTENT_NAME in files
                    or RESERVATION_ABORT_RECEIPT_NAME in files
                ):
                    try:
                        abort_receipt = reserved.inspect_abort_receipt()
                    except ProjectUpdateTransactionError:
                        abort_receipt = None
                        if (
                            lock_state == "absent"
                            and RESERVATION_ABORT_INTENT_NAME in files
                            and RESERVATION_ABORT_RECEIPT_NAME not in files
                        ):
                            try:
                                abort_receipt_pending = (
                                    reserved.inspect_abort_receipt_pending_read_only()
                                    is not None
                                )
                            except ProjectUpdateTransactionError:
                                abort_receipt_pending = False
                        if not abort_receipt_pending:
                            unexpected = True
                if abort_receipt is not None:
                    classification = "reserved_aborted_before_intent_seal"
                elif abort_receipt_pending:
                    classification = "reserved_abort_receipt_pending"
                elif unexpected or lock_state == "conflict_or_unsafe":
                    classification = "manual_review_incomplete_or_unsafe"
                elif intent_material_present:
                    classification = "manual_review_intent_seal_incomplete_or_invalid"
                elif candidate_present and not candidate_seal_present:
                    classification = "manual_review_candidate_partial"
                elif candidate_seal_present and not candidate_present:
                    classification = "manual_review_candidate_seal_without_tree"
                elif candidate_present and candidate_seal_present:
                    classification = "candidate_sealed_intent_unsealed"
                elif lock_state == "exact" and backlink_exact:
                    classification = "reserved_locked_unsealed"
                elif lock_state == "exact":
                    classification = "reserved_locked_unbacklinked"
                elif reservation_backlink_present:
                    classification = "manual_review_backlink_without_live_lock"
                else:
                    classification = "reserved_lock_absent"
                evidence_basis = {
                    "candidate_present": candidate_present,
                    "candidate_seal_present": candidate_seal_present,
                    "classification": classification,
                    "descendant_count": len(files) + len(directories),
                    "lock_state": lock_state,
                    "reservation_backlink_exact": backlink_exact,
                    "reservation_sha256": reserved.reservation.sha256,
                    "schema": ORPHAN_SUMMARY_SCHEMA,
                    "transaction_ref": ref,
                }
            except ProjectUpdateTransactionError as reservation_failure:
                if (
                    reservation_failure.code
                    == "project_update_transaction_scan_incomplete"
                ):
                    raise
                classification = "manual_review_incomplete_or_unsafe"
                evidence_basis = {
                    "classification": classification,
                    "schema": ORPHAN_SUMMARY_SCHEMA,
                    "transaction_ref": ref,
                    "unsafe_descendant_preserved": True,
                }
            evidence = sha256_document(evidence_basis)
        result.append(
            OrphanInspection(
                schema=ORPHAN_SUMMARY_SCHEMA,
                transaction_ref=ref,
                transaction_logical_ref=logical,
                classification=classification,
                evidence_sha256=evidence,
            )
        )
    return tuple(result)


def discover_exact_reservation_abort_cleanup_read_only(
    project_root: Path | str,
) -> tuple[ReservationAbortCleanupInspection, ...]:
    """Find every exact abort history that still needs cleanup or resume.

    Completed proof-only history is deliberately excluded.  A live lock,
    unsafe namespace entry, mixed ref state, partial abort evidence, or drift
    during the bounded scan refuses discovery rather than returning a subset.
    """

    project = _absolute(project_root)
    _safe_existing_chain(project, directory=True)
    lock_path = project / PurePosixPath(PROJECT_UPDATE_LOCK_LOGICAL)
    _within(lock_path, project)
    if os.path.lexists(lock_path):
        raise _fail("project_update_transaction_cleanup_refused")
    parent = project / PurePosixPath(TRANSACTION_ROOT_LOGICAL)
    _within(parent, project)
    if not os.path.lexists(parent):
        return ()
    _safe_existing_chain(parent, directory=True)
    parent_before = _stable_path_identity(_safe_directory(parent, within=project))

    originals: dict[str, tuple[Path, os.stat_result]] = {}
    tombstones: dict[str, tuple[Path, os.stat_result]] = {}
    proofs: dict[
        str,
        tuple[bytes, os.stat_result, dict[str, Any]],
    ] = {}
    seen = 0
    try:
        with os.scandir(parent) as entries:
            for entry in entries:
                seen += 1
                if seen > MAX_TERMINAL_CLEANUP_SCAN_ENTRIES:
                    raise _fail("project_update_transaction_scan_incomplete")
                path = Path(entry.path)
                _within(path, parent)
                info = path.lstat()
                if stat.S_ISLNK(info.st_mode) or _is_reparse(info):
                    raise _fail("project_update_transaction_path_unsafe")
                original_match = TRANSACTION_REF_RE.fullmatch(entry.name)
                tombstone_match = re.fullmatch(
                    r"\.cleanup_(update_[0-9a-f]{32})",
                    entry.name,
                )
                proof_match = re.fullmatch(
                    r"\.cleanup-proof_(update_[0-9a-f]{32})\.json",
                    entry.name,
                )
                if original_match is not None:
                    if not stat.S_ISDIR(info.st_mode):
                        raise _fail("project_update_transaction_cleanup_refused")
                    originals[entry.name] = (path, info)
                    continue
                if tombstone_match is not None:
                    if not stat.S_ISDIR(info.st_mode):
                        raise _fail("project_update_transaction_cleanup_refused")
                    ref = tombstone_match.group(1)
                    if ref in tombstones:
                        raise _fail("project_update_transaction_cleanup_refused")
                    tombstones[ref] = (path, info)
                    continue
                if proof_match is None or not stat.S_ISREG(info.st_mode):
                    raise _fail("project_update_transaction_cleanup_refused")
                ref = proof_match.group(1)
                raw, proof_info = _read_cleanup_linked_regular(
                    project,
                    path,
                    maximum=MAX_DOCUMENT_BYTES + 1,
                )
                value = _parse_document(
                    raw,
                    code="project_update_transaction_cleanup_refused",
                )
                authority = _digest(
                    value.get("cleanup_authority_sha256"),
                    code="project_update_transaction_cleanup_refused",
                )
                ProjectUpdateTransaction._validate_cleanup_plan_document(
                    value,
                    ref,
                    authority,
                )
                proofs[ref] = (raw, proof_info, value)
    except OSError:
        raise _fail("project_update_transaction_path_unsafe") from None

    if set(originals) & (set(tombstones) | set(proofs)):
        raise _fail("project_update_transaction_cleanup_refused")
    candidates: list[ReservationAbortCleanupInspection] = []

    for ref in sorted(originals):
        root, root_scan_info = originals[ref]
        root_before = _stable_path_identity(
            _safe_directory(root, within=parent)
        )
        if root_before != _stable_path_identity(root_scan_info):
            raise _fail("project_update_transaction_cleanup_refused")
        reserved = ReservedProjectUpdateTransaction.open(project, ref)
        abort_intent_present = os.path.lexists(
            root / RESERVATION_ABORT_INTENT_NAME
        )
        abort_receipt_present = os.path.lexists(
            root / RESERVATION_ABORT_RECEIPT_NAME
        )
        abort_plan_present = os.path.lexists(
            root / RESERVATION_ABORT_CLEANUP_PLAN_NAME
        )
        if not abort_intent_present and not abort_receipt_present:
            if abort_plan_present:
                raise _fail("project_update_transaction_cleanup_refused")
            continue
        if not abort_intent_present or not abort_receipt_present:
            raise _fail("project_update_transaction_cleanup_refused")
        files, directories = ProjectUpdateTransaction._descendant_names(root)
        terminal = reserved.inspect_abort_receipt()
        if terminal is None:
            raise _fail("project_update_transaction_cleanup_refused")
        expected_files = set(reserved._abort_cleanup_expected_files())
        plan_present = RESERVATION_ABORT_CLEANUP_PLAN_NAME in files
        if plan_present:
            expected_files.add(RESERVATION_ABORT_CLEANUP_PLAN_NAME)
        if directories or files != expected_files:
            raise _fail("project_update_transaction_cleanup_refused")
        authority: str | None = None
        state: Literal["terminal_original", "planned_original"] = (
            "terminal_original"
        )
        if plan_present:
            plan_path = root / RESERVATION_ABORT_CLEANUP_PLAN_NAME
            plan_raw, _plan_info = _read_cleanup_linked_regular(
                project,
                plan_path,
                maximum=MAX_DOCUMENT_BYTES + 1,
            )
            plan_value = _parse_document(
                plan_raw,
                code="project_update_transaction_cleanup_refused",
            )
            authority = _digest(
                plan_value.get("cleanup_authority_sha256"),
                code="project_update_transaction_cleanup_refused",
            )
            plan = reserved._validate_abort_cleanup_plan_document(
                plan_value,
                ref,
                authority,
            )
            if (
                reserved._abort_cleanup_root_identity(plan)
                != _cleanup_directory_identity(
                    _safe_directory(root, within=parent)
                )
                or plan["reservation_sha256"] != reserved.reservation.sha256
                or plan["abort_receipt_sha256"] != terminal["receipt_sha256"]
                or plan["candidate_cleanup_evidence_sha256"]
                != terminal["candidate_cleanup_evidence_sha256"]
            ):
                raise _fail("project_update_transaction_cleanup_refused")
            actual, actual_directories = (
                ProjectUpdateTransaction._cleanup_descendant_snapshot(
                    root,
                    exclude={RESERVATION_ABORT_CLEANUP_PLAN_NAME},
                )
            )
            if (
                actual_directories
                or actual != reserved._abort_cleanup_file_snapshots(plan)
            ):
                raise _fail("project_update_transaction_cleanup_refused")
            state = "planned_original"
        root_after = _stable_path_identity(
            _safe_directory(root, within=parent)
        )
        if root_after != root_before or os.path.lexists(lock_path):
            raise _fail("project_update_transaction_cleanup_refused")
        candidates.append(
            ReservationAbortCleanupInspection(
                transaction_ref=ref,
                state=state,
                cleanup_authority_sha256=authority,
                entry_identity=root_after,
            )
        )

    for ref in sorted(tombstones):
        tombstone, tombstone_scan_info = tombstones[ref]
        tombstone_before = _stable_path_identity(
            _safe_directory(tombstone, within=parent)
        )
        if tombstone_before != _stable_path_identity(tombstone_scan_info):
            raise _fail("project_update_transaction_cleanup_refused")
        proof_entry = proofs.get(ref)
        with os.scandir(tombstone) as entries:
            names = tuple(sorted(entry.name for entry in entries))
        if proof_entry is not None:
            proof_raw, proof_info, proof_value = proof_entry
            if proof_value.get("schema") != RESERVATION_ABORT_CLEANUP_PLAN_SCHEMA:
                # A generic completed-transaction tombstone is outside this
                # primitive and remains for the ordinary cleanup resumer.
                continue
            authority = _digest(
                proof_value.get("cleanup_authority_sha256"),
                code="project_update_transaction_cleanup_refused",
            )
            plan = ReservedProjectUpdateTransaction._validate_abort_cleanup_plan_document(
                proof_value,
                ref,
                authority,
            )
            if (
                ReservedProjectUpdateTransaction._abort_cleanup_root_identity(plan)
                != _cleanup_directory_identity(
                    _safe_directory(tombstone, within=parent)
                )
            ):
                raise _fail("project_update_transaction_cleanup_refused")
            if names:
                if names != (RESERVATION_ABORT_CLEANUP_PLAN_NAME,):
                    raise _fail("project_update_transaction_cleanup_refused")
                duplicate_raw, duplicate_info = _read_cleanup_linked_regular(
                    project,
                    tombstone / RESERVATION_ABORT_CLEANUP_PLAN_NAME,
                    maximum=MAX_DOCUMENT_BYTES + 1,
                )
                if (
                    not hmac.compare_digest(duplicate_raw, proof_raw)
                    or int(proof_info.st_nlink) != 2
                    or int(duplicate_info.st_nlink) != 2
                    or (int(proof_info.st_dev), int(proof_info.st_ino))
                    != (int(duplicate_info.st_dev), int(duplicate_info.st_ino))
                ):
                    raise _fail("project_update_transaction_cleanup_refused")
            elif int(proof_info.st_nlink) != 1:
                raise _fail("project_update_transaction_cleanup_refused")
            authority_for_candidate = authority
        else:
            if RESERVATION_ABORT_CLEANUP_PLAN_NAME not in names:
                # A canonical complete-transaction tombstone is deliberately
                # left to ProjectUpdateTransaction.resume_cleanup.
                if set(names) & {CLEANUP_PLAN_NAME, LEGACY_CLEANUP_PLAN_NAME}:
                    continue
                raise _fail("project_update_transaction_cleanup_refused")
            plan_path = tombstone / RESERVATION_ABORT_CLEANUP_PLAN_NAME
            plan_raw, _plan_info = _read_cleanup_linked_regular(
                project,
                plan_path,
                maximum=MAX_DOCUMENT_BYTES + 1,
            )
            plan_value = _parse_document(
                plan_raw,
                code="project_update_transaction_cleanup_refused",
            )
            authority_for_candidate = _digest(
                plan_value.get("cleanup_authority_sha256"),
                code="project_update_transaction_cleanup_refused",
            )
            plan = ReservedProjectUpdateTransaction._validate_abort_cleanup_plan_document(
                plan_value,
                ref,
                authority_for_candidate,
            )
            if (
                ReservedProjectUpdateTransaction._abort_cleanup_root_identity(plan)
                != _cleanup_directory_identity(
                    _safe_directory(tombstone, within=parent)
                )
            ):
                raise _fail("project_update_transaction_cleanup_refused")
            expected = (
                ReservedProjectUpdateTransaction._abort_cleanup_file_snapshots(
                    plan
                )
            )
            actual, actual_directories = (
                ProjectUpdateTransaction._cleanup_descendant_snapshot(
                    tombstone,
                    exclude={RESERVATION_ABORT_CLEANUP_PLAN_NAME},
                )
            )
            if (
                actual_directories
                or not set(actual).issubset(expected)
                or any(actual[item] != expected[item] for item in actual)
            ):
                raise _fail("project_update_transaction_cleanup_refused")
        tombstone_after = _stable_path_identity(
            _safe_directory(tombstone, within=parent)
        )
        if tombstone_after != tombstone_before or os.path.lexists(lock_path):
            raise _fail("project_update_transaction_cleanup_refused")
        candidates.append(
            ReservationAbortCleanupInspection(
                transaction_ref=ref,
                state="cleanup_tombstone",
                cleanup_authority_sha256=authority_for_candidate,
                entry_identity=tombstone_after,
            )
        )

    for ref, (_raw, proof_info, _value) in proofs.items():
        if ref not in tombstones and int(proof_info.st_nlink) != 1:
            raise _fail("project_update_transaction_cleanup_refused")
    parent_after = _stable_path_identity(_safe_directory(parent, within=project))
    if parent_after != parent_before or os.path.lexists(lock_path):
        raise _fail("project_update_transaction_cleanup_refused")
    return tuple(sorted(candidates, key=lambda item: item.transaction_ref))


def compact_exact_reservation_abort_history(
    project_root: Path | str,
    transaction_ref: str,
    *,
    cleanup_authority_sha256: str | None,
) -> bool:
    """Compact or resume one discovered exact abort history idempotently."""

    try:
        project = _absolute(project_root)
        ref = _transaction_ref(transaction_ref)
        supplied = (
            None
            if cleanup_authority_sha256 is None
            else _digest(
                cleanup_authority_sha256,
                code="project_update_transaction_cleanup_refused",
            )
        )
        candidates = discover_exact_reservation_abort_cleanup_read_only(project)
        inspection = next(
            (item for item in candidates if item.transaction_ref == ref),
            None,
        )
        if inspection is None:
            if supplied is None:
                return False
            return ReservedProjectUpdateTransaction.resume_cleanup(
                project,
                ref,
                cleanup_authority_sha256=supplied,
            )
        persisted = inspection.cleanup_authority_sha256
        if persisted is not None and supplied not in {None, persisted}:
            return False
        authority = persisted or supplied
        if authority is None:
            return False
        if inspection.state == "cleanup_tombstone":
            return ReservedProjectUpdateTransaction.resume_cleanup(
                project,
                ref,
                cleanup_authority_sha256=authority,
            )
        transaction = ReservedProjectUpdateTransaction.open(project, ref)
        return transaction.exact_cleanup(
            cleanup_authority_sha256=authority,
        )
    except (OSError, ProjectUpdateTransactionError, KeyError, TypeError):
        return False


def compact_exact_reservation_abort_histories(
    project_root: Path | str,
    *,
    cleanup_authority_sha256: str,
) -> dict[str, Any]:
    """Compact all exact abort histories, stopping at the first refusal."""

    project = _absolute(project_root)
    authority = _digest(
        cleanup_authority_sha256,
        code="project_update_transaction_cleanup_refused",
    )
    inspections = discover_exact_reservation_abort_cleanup_read_only(project)
    completed: list[str] = []
    failed_ref: str | None = None
    for inspection in inspections:
        item_authority = inspection.cleanup_authority_sha256 or authority
        if not compact_exact_reservation_abort_history(
            project,
            inspection.transaction_ref,
            cleanup_authority_sha256=item_authority,
        ):
            failed_ref = inspection.transaction_ref
            break
        completed.append(inspection.transaction_ref)
    remaining = discover_exact_reservation_abort_cleanup_read_only(project)
    remaining_refs = [item.transaction_ref for item in remaining]
    return {
        "completed_count": len(completed),
        "completed_refs": completed,
        "discovered_count": len(inspections),
        "failed_ref": failed_ref,
        "ok": failed_ref is None and not remaining_refs,
        "remaining_refs": remaining_refs,
        "schema": RESERVATION_ABORT_CLEANUP_RESULT_SCHEMA,
    }


__all__ = [
    "ABSENT_COMPONENT_SHA256",
    "ALLOWED_CHECKPOINT_PHASES",
    "CHECKPOINT_CHAIN_START_SHA256",
    "CleanupTombstoneInspection",
    "ComponentClassification",
    "ComponentExpectation",
    "DirectoryDurability",
    "JournalInspection",
    "LockObservation",
    "LockReleaseResult",
    "MAX_TERMINAL_CLEANUP_SCAN_ENTRIES",
    "OrphanInspection",
    "PrivateBlobRecord",
    "ProjectUpdateBindings",
    "ProjectUpdateCheckpoint",
    "ProjectUpdateComponent",
    "ProjectUpdateInspection",
    "ProjectUpdateIntent",
    "ProjectUpdateReservation",
    "ProjectUpdateTransaction",
    "ProjectUpdateTransactionError",
    "RESERVATION_ABORT_CLEANUP_PLAN_SCHEMA",
    "RESERVATION_ABORT_CLEANUP_RESULT_SCHEMA",
    "ReservationAbortCleanupInspection",
    "ReservedProjectUpdateTransaction",
    "RuntimeCandidateBinding",
    "RuntimeCandidateTreeInventory",
    "TerminalCleanupArtifactState",
    "build_lock_document",
    "active_transaction_ref_for_resume_read_only",
    "active_transaction_ref_from_lock_read_only",
    "canonical_json_bytes",
    "classify_components",
    "compact_exact_reservation_abort_histories",
    "compact_exact_reservation_abort_history",
    "digest_component",
    "discover_exact_reservation_abort_cleanup_read_only",
    "inspect_prelock_orphans",
    "inspect_terminal_cleanup_artifacts_for_resume_read_only",
    "lock_document_bytes",
    "runtime_bundle_inventory_sha256",
    "sha256_bytes",
    "sha256_document",
]
