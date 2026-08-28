"""Pure doctor input-snapshot and completion-revalidation helpers.

The legacy :mod:`wom_kit.archive_cli` Doctor currently owns traversal and
diagnostic production.  This module deliberately does not import that CLI.
It supplies the small, independently testable contract needed to bind object
manifest findings to the exact bytes that were parsed and to decide whether a
completed doctor result must fail because that input changed.

Only content-free metadata is returned by ``as_dict()``.  The captured bytes
are returned separately so callers can parse those exact bytes without a
second filesystem read.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import os
from pathlib import Path, PurePosixPath
import stat
import sys
from typing import Any, Callable


DOCTOR_OBJECT_MANIFEST_RELATIVE_PATH = "objects/manifests/files.jsonl"
DOCTOR_OBJECT_MANIFEST_MAX_BYTES = 64 * 1024 * 1024
DOCTOR_INPUT_SNAPSHOT_SCHEMA = "wom-kit/doctor-input-snapshot/v0.1"
DOCTOR_INPUT_REVALIDATION_SCHEMA = "wom-kit/doctor-input-revalidation/v0.1"
DOCTOR_INPUT_SNAPSHOT_BASIS = (
    "sha256_exact_bytes_parsed_by_object_manifest_stage"
)
DOCTOR_OBJECT_BYTE_VERIFICATION_SCHEMA = (
    "wom-kit/doctor-object-byte-verification/v0.2"
)
DOCTOR_OBJECT_BYTE_VERIFICATION_MODES = frozenset({"operational", "deep"})
DOCTOR_OBJECT_BYTE_VERIFICATION_STATES = (
    "rehashed_now",
    "attested_unchanged",
    "bytes_unverified",
)
DOCTOR_OBJECT_BYTE_COMPLETION_REVALIDATION_STATES = frozenset(
    {"not_run", "current", "stale", "unverified"}
)

_SNAPSHOT_STATES = frozenset({"present", "absent", "unavailable"})
_REVALIDATION_STATES = frozenset({"current", "stale", "unverified"})


@dataclass(frozen=True)
class DoctorObjectByteVerification:
    """Content-free truth statement for local object-byte verification.

    ``attested_unchanged`` is part of the stable result vocabulary, but a
    caller must not increment it until WOM has a durable, independently
    revalidated deep-byte attestation contract.  The current Doctor therefore
    reports zero for that state instead of treating size or timestamps as a
    byte-integrity proof.
    """

    mode: str
    local_reference_count: int
    unique_local_file_count: int
    rehashed_now: int
    attested_unchanged: int
    bytes_unverified: int
    unresolved_local_reference_count: int = 0
    completion_revalidation_state: str = "not_run"
    completion_revalidated_unique_local_file_count: int = 0

    def __post_init__(self) -> None:
        if self.mode not in DOCTOR_OBJECT_BYTE_VERIFICATION_MODES:
            raise ValueError("doctor_object_byte_verification_mode_invalid")
        counts = (
            self.local_reference_count,
            self.unique_local_file_count,
            self.rehashed_now,
            self.attested_unchanged,
            self.bytes_unverified,
            self.unresolved_local_reference_count,
        )
        if any(type(value) is not int or value < 0 for value in counts):
            raise ValueError("doctor_object_byte_verification_count_invalid")
        if (
            self.completion_revalidation_state
            not in DOCTOR_OBJECT_BYTE_COMPLETION_REVALIDATION_STATES
        ):
            raise ValueError(
                "doctor_object_byte_completion_revalidation_state_invalid"
            )
        if (
            type(self.completion_revalidated_unique_local_file_count) is not int
            or self.completion_revalidated_unique_local_file_count < 0
            or self.completion_revalidated_unique_local_file_count
            > self.unique_local_file_count
        ):
            raise ValueError(
                "doctor_object_byte_completion_revalidation_count_invalid"
            )
        if self.local_reference_count < self.unique_local_file_count:
            raise ValueError(
                "doctor_object_byte_verification_reference_count_invalid"
            )
        if self.unresolved_local_reference_count > self.local_reference_count:
            raise ValueError(
                "doctor_object_byte_unresolved_reference_count_invalid"
            )
        if self.attested_unchanged != 0:
            raise ValueError(
                "doctor_object_byte_verification_attestation_unsupported"
            )
        if (
            self.rehashed_now
            + self.attested_unchanged
            + self.bytes_unverified
            != self.unique_local_file_count
        ):
            raise ValueError("doctor_object_byte_verification_partition_invalid")

    @property
    def result_state(self) -> str:
        if self.bytes_unverified or self.unresolved_local_reference_count:
            return "bytes_unverified"
        if self.attested_unchanged:
            return "attested_unchanged"
        if self.rehashed_now:
            return "rehashed_now"
        return "not_applicable"

    @property
    def byte_integrity_verified(self) -> bool:
        return bool(
            self.mode == "deep"
            and self.unresolved_local_reference_count == 0
            and self.bytes_unverified == 0
            and self.rehashed_now == self.unique_local_file_count
            and self.completion_revalidation_state == "current"
            and self.completion_revalidated_unique_local_file_count
            == self.unique_local_file_count
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": DOCTOR_OBJECT_BYTE_VERIFICATION_SCHEMA,
            "mode": self.mode,
            "result_state": self.result_state,
            "local_reference_count": self.local_reference_count,
            "unresolved_local_reference_count": (
                self.unresolved_local_reference_count
            ),
            "unique_local_file_count": self.unique_local_file_count,
            "states": {
                "rehashed_now": self.rehashed_now,
                "attested_unchanged": self.attested_unchanged,
                "bytes_unverified": self.bytes_unverified,
            },
            "completion_revalidation": {
                "state": self.completion_revalidation_state,
                "revalidated_unique_local_file_count": (
                    self.completion_revalidated_unique_local_file_count
                ),
            },
            "byte_integrity_verified": self.byte_integrity_verified,
            "all_unique_local_files_rehashed_this_run": bool(
                self.unique_local_file_count > 0
                and self.rehashed_now == self.unique_local_file_count
            ),
            "attestation_reuse_supported": False,
            "size_or_timestamp_treated_as_byte_proof": False,
        }


def _utc_timestamp(value: str | None = None) -> str:
    if value is None:
        return (
            datetime.now(timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
    if type(value) is not str or not value.strip():
        raise ValueError("doctor_snapshot_timestamp_invalid")
    normalized = value.strip()
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("doctor_snapshot_timestamp_invalid") from None
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("doctor_snapshot_timestamp_not_utc")
    return normalized


def _maximum_bytes(value: int) -> int:
    if type(value) is not int or value < 1:
        raise ValueError("doctor_snapshot_maximum_bytes_invalid")
    return value


def _safe_relative_path(value: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError("doctor_snapshot_relative_path_invalid")
    normalized = value.strip().replace("\\", "/")
    candidate = PurePosixPath(normalized)
    if (
        candidate.is_absolute()
        or normalized.startswith("//")
        or not candidate.parts
        or candidate.parts[0].endswith(":")
        or any(part in {"", ".", ".."} for part in candidate.parts)
    ):
        raise ValueError("doctor_snapshot_relative_path_invalid")
    return candidate.as_posix()


def _is_reparse_point(value: os.stat_result) -> bool:
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0) or 0)
    return bool(
        reparse_flag
        and int(getattr(value, "st_file_attributes", 0) or 0) & reparse_flag
    )


def _identity_changed(before: os.stat_result, after: os.stat_result) -> bool:
    before_inode = int(getattr(before, "st_ino", 0) or 0)
    after_inode = int(getattr(after, "st_ino", 0) or 0)
    inode_changed = (
        before_inode != 0
        and after_inode != 0
        and before_inode != after_inode
    )
    return bool(
        int(before.st_dev) != int(after.st_dev)
        or inode_changed
        or stat.S_IFMT(int(before.st_mode)) != stat.S_IFMT(int(after.st_mode))
        or _is_reparse_point(before) != _is_reparse_point(after)
        or int(before.st_size) != int(after.st_size)
        or int(getattr(before, "st_mtime_ns", 0) or 0)
        != int(getattr(after, "st_mtime_ns", 0) or 0)
    )


@dataclass(frozen=True)
class DoctorArchiveRootBoundary:
    """One immutable canonical archive-root observation for a Doctor run.

    Stable file readers must not resolve a mutable root path after work has
    been queued.  Otherwise a renamed root replaced by a junction can make the
    replacement look like the newly trusted boundary.  This value captures
    the canonical spelling and identity once; every descriptor check compares
    against that original observation.
    """

    canonical_path: Path
    observed_identity: os.stat_result


def capture_doctor_archive_root_boundary(
    root: Path,
) -> DoctorArchiveRootBoundary | None:
    """Capture one existing, non-reparse directory root without a race."""

    candidate = Path(root)
    try:
        before = os.lstat(candidate)
        if (
            not stat.S_ISDIR(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or _is_reparse_point(before)
        ):
            return None
        canonical = candidate.resolve(strict=True)
        canonical_observed = os.lstat(canonical)
        after = os.lstat(candidate)
    except (OSError, RuntimeError, ValueError):
        return None
    if (
        not stat.S_ISDIR(canonical_observed.st_mode)
        or stat.S_ISLNK(canonical_observed.st_mode)
        or _is_reparse_point(canonical_observed)
        or _identity_changed(before, after)
        or _identity_changed(before, canonical_observed)
    ):
        return None
    return DoctorArchiveRootBoundary(
        canonical_path=canonical,
        observed_identity=canonical_observed,
    )


def doctor_archive_root_boundary_is_current(
    boundary: DoctorArchiveRootBoundary,
) -> bool:
    """Revalidate the captured root identity without resolving it again."""

    if not isinstance(boundary, DoctorArchiveRootBoundary):
        return False
    try:
        current = os.lstat(boundary.canonical_path)
    except OSError:
        return False
    return bool(
        stat.S_ISDIR(current.st_mode)
        and not stat.S_ISLNK(current.st_mode)
        and not _is_reparse_point(current)
        and not _identity_changed(boundary.observed_identity, current)
    )


def _normalized_path_stays_within_root(path: Path, root: Path) -> bool:
    try:
        normalized_path = os.path.normcase(os.path.abspath(os.fspath(path)))
        # ``root`` is the immutable canonical spelling captured before the
        # operation.  Never resolve it here: the path can be replaced between
        # inventory and a queued descriptor read.
        normalized_root = os.path.normcase(os.path.abspath(os.fspath(root)))
        return os.path.commonpath(
            [normalized_path, normalized_root]
        ) == normalized_root
    except (OSError, RuntimeError, ValueError):
        return False


@lru_cache(maxsize=1)
def _windows_final_path_api() -> tuple[Any, Any, Any]:
    """Load the immutable Win32 descriptor-path API once per process."""

    import ctypes
    from ctypes import wintypes
    import msvcrt

    get_final_path = ctypes.WinDLL(
        "kernel32",
        use_last_error=True,
    ).GetFinalPathNameByHandleW
    get_final_path.argtypes = (
        wintypes.HANDLE,
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
    )
    get_final_path.restype = wintypes.DWORD
    return get_final_path, wintypes.HANDLE, msvcrt


def _windows_descriptor_final_path(descriptor: int) -> Path | None:
    try:
        import ctypes

        get_final_path, handle_type, msvcrt = _windows_final_path_api()
        handle = handle_type(msvcrt.get_osfhandle(descriptor))
        # Ordinary archive paths are short.  Starting with Windows' maximum
        # legacy path buffer allocated tens of KiB twice per tiny file.  The API
        # returns the required length, so grow only for an actually long path.
        size = 512
        buffer = ctypes.create_unicode_buffer(size)
        written = int(get_final_path(handle, buffer, size, 0))
        if written <= 0:
            return None
        if written >= size:
            size = written + 1
            buffer = ctypes.create_unicode_buffer(size)
            written = int(get_final_path(handle, buffer, size, 0))
            if written <= 0 or written >= size:
                return None
        value = buffer.value
        if value.startswith("\\\\?\\UNC\\"):
            value = "\\\\" + value[8:]
        elif value.startswith("\\\\?\\"):
            value = value[4:]
        return Path(value)
    except (ImportError, OSError, RuntimeError, ValueError):
        return None


def _darwin_descriptor_final_path(descriptor: int) -> Path | None:
    """Return the path bound to an open macOS descriptor via ``F_GETPATH``."""

    try:
        import fcntl

        # Darwin's F_GETPATH writes a NUL-terminated MAXPATHLEN buffer.  Python
        # fcntl accepts and returns a bytes buffer for this command.
        raw = fcntl.fcntl(descriptor, 50, b"\0" * 1024)
        if not isinstance(raw, bytes):
            return None
        value = raw.split(b"\0", 1)[0]
        if not value:
            return None
        return Path(os.fsdecode(value))
    except (ImportError, OSError, RuntimeError, TypeError, ValueError):
        return None


def descriptor_path_stays_within_root(
    descriptor: int,
    *,
    required_root: DoctorArchiveRootBoundary,
) -> bool:
    """Bind the opened handle itself to one canonical archive root.

    Final-entry ``O_NOFOLLOW`` does not reject a junction in an ancestor.
    Windows therefore asks the opened handle for its final normalized path;
    Linux uses ``/proc/self/fd``.  Unsupported/ambiguous platforms fail closed.
    """

    if not doctor_archive_root_boundary_is_current(required_root):
        return False
    if os.name == "nt":
        final_path = _windows_descriptor_final_path(descriptor)
    elif sys.platform == "darwin":
        final_path = _darwin_descriptor_final_path(descriptor)
    else:
        descriptor_link = Path("/proc/self/fd") / str(descriptor)
        try:
            final_path = descriptor_link.resolve(strict=True)
        except (OSError, RuntimeError, ValueError):
            final_path = None
    # Callers perform this descriptor proof both before and after consuming the
    # file.  Rechecking the root a second time *inside* each proof doubles an
    # expensive Windows ``lstat`` without closing a race (no finite sequence of
    # path checks can do that).  The post-read descriptor proof and Doctor's
    # stage/final root checks still bind the complete result to the captured
    # root generation.
    return bool(
        final_path is not None
        and _normalized_path_stays_within_root(
            final_path,
            required_root.canonical_path,
        )
    )


@dataclass(frozen=True)
class DoctorStableFileHash:
    """Content-free result of one descriptor-bound stable SHA-256 read."""

    state: str
    size_bytes: int | None
    sha256: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "size_bytes": self.size_bytes,
            "sha256_computed": self.sha256 is not None,
            "descriptor_bound": self.state == "verified",
            "path_echoed": False,
        }


def observe_stable_regular_file_sha256(
    path: Path,
    *,
    expected_size: int | None = None,
    progress_callback: Callable[[int], None] | None = None,
    required_root: DoctorArchiveRootBoundary | None = None,
) -> DoctorStableFileHash:
    """Hash a regular file once while proving its path and descriptor stayed stable."""

    try:
        path_before = os.lstat(path)
    except FileNotFoundError:
        return DoctorStableFileHash("missing", None, None)
    except OSError:
        return DoctorStableFileHash("unreadable", None, None)
    size_bytes = int(path_before.st_size)
    if (
        stat.S_ISLNK(path_before.st_mode)
        or _is_reparse_point(path_before)
        or not stat.S_ISREG(path_before.st_mode)
    ):
        return DoctorStableFileHash("unsafe", size_bytes, None)
    if expected_size is not None and size_bytes != expected_size:
        return DoctorStableFileHash("size_mismatch", size_bytes, None)
    flags = (
        os.O_RDONLY
        | int(getattr(os, "O_BINARY", 0) or 0)
        | int(getattr(os, "O_NOFOLLOW", 0) or 0)
    )
    try:
        descriptor = os.open(str(path), flags)
    except OSError:
        return DoctorStableFileHash("unreadable", size_bytes, None)
    try:
        opened_before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened_before.st_mode)
            or _is_reparse_point(opened_before)
            or _identity_changed(path_before, opened_before)
            or (
                required_root is not None
                and not descriptor_path_stays_within_root(
                    descriptor,
                    required_root=required_root,
                )
            )
        ):
            return DoctorStableFileHash("unsafe", size_bytes, None)
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            digest.update(chunk)
            if progress_callback is not None:
                progress_callback(total)
        opened_after = os.fstat(descriptor)
        try:
            path_after = os.lstat(path)
        except OSError:
            return DoctorStableFileHash("changed", size_bytes, None)
        if (
            not stat.S_ISREG(opened_after.st_mode)
            or _is_reparse_point(opened_after)
            or not stat.S_ISREG(path_after.st_mode)
            or stat.S_ISLNK(path_after.st_mode)
            or _is_reparse_point(path_after)
            or _identity_changed(opened_before, opened_after)
            or _identity_changed(opened_after, path_after)
            or (
                required_root is not None
                and not doctor_archive_root_boundary_is_current(required_root)
            )
            or total != size_bytes
        ):
            return DoctorStableFileHash("changed", size_bytes, None)
        return DoctorStableFileHash("verified", total, digest.hexdigest())
    except OSError:
        return DoctorStableFileHash("unreadable", size_bytes, None)
    finally:
        os.close(descriptor)


def _stable_regular_file_bytes(
    path: Path,
    *,
    maximum_bytes: int,
    required_root: DoctorArchiveRootBoundary | None = None,
) -> tuple[bytes | None, str | None]:
    """Return one bounded stable regular-file read and an internal reason.

    The opened descriptor is matched to the pre-open path identity, then both
    descriptor and path identities are checked after the read.  This rejects
    symlinks, Windows reparse points, replacements, growth, truncation, and
    same-size writes observable through mtime.
    """

    try:
        path_before = os.lstat(path)
    except FileNotFoundError:
        return None, "missing"
    except OSError:
        return None, "unreadable"
    if stat.S_ISLNK(path_before.st_mode):
        return None, "symlink"
    if _is_reparse_point(path_before):
        return None, "reparse"
    if not stat.S_ISREG(path_before.st_mode):
        return None, "special"
    if int(path_before.st_size) > maximum_bytes:
        return None, "too_large"

    flags = (
        os.O_RDONLY
        | int(getattr(os, "O_BINARY", 0) or 0)
        | int(getattr(os, "O_NOFOLLOW", 0) or 0)
    )
    try:
        descriptor = os.open(str(path), flags)
    except OSError:
        return None, "unreadable"
    try:
        opened_before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened_before.st_mode)
            or _is_reparse_point(opened_before)
            or _identity_changed(path_before, opened_before)
            or (
                required_root is not None
                and not descriptor_path_stays_within_root(
                    descriptor,
                    required_root=required_root,
                )
            )
        ):
            return None, "outside_root"
        chunks: list[bytes] = []
        total = 0
        while True:
            remaining = maximum_bytes + 1 - total
            if remaining <= 0:
                return None, "too_large"
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            total += len(chunk)
            if total > maximum_bytes:
                return None, "too_large"
            chunks.append(chunk)
        opened_after = os.fstat(descriptor)
        try:
            path_after = os.lstat(path)
        except OSError:
            return None, "changed"
        if (
            not stat.S_ISREG(path_after.st_mode)
            or stat.S_ISLNK(path_after.st_mode)
            or _is_reparse_point(path_after)
            or _identity_changed(opened_before, opened_after)
            or _identity_changed(opened_after, path_after)
            or (
                required_root is not None
                and not doctor_archive_root_boundary_is_current(required_root)
            )
            or total != int(opened_after.st_size)
        ):
            return None, "changed"
        return b"".join(chunks), None
    except OSError:
        return None, "unreadable"
    finally:
        os.close(descriptor)


def _manifest_path_state(
    archive_root: Path,
) -> tuple[Path, str | None, tuple[tuple[Path, os.stat_result], ...]]:
    root = Path(archive_root)
    manifest_path = root.joinpath(*DOCTOR_OBJECT_MANIFEST_RELATIVE_PATH.split("/"))
    try:
        root_stat = os.lstat(root)
    except FileNotFoundError:
        return manifest_path, "archive_root_missing", ()
    except OSError:
        return manifest_path, "archive_root_unreadable", ()
    if (
        not stat.S_ISDIR(root_stat.st_mode)
        or stat.S_ISLNK(root_stat.st_mode)
        or _is_reparse_point(root_stat)
    ):
        return manifest_path, "archive_root_unsafe", ()

    current = root
    parents: list[tuple[Path, os.stat_result]] = [(root, root_stat)]
    for segment in ("objects", "manifests"):
        current = current / segment
        try:
            current_stat = os.lstat(current)
        except FileNotFoundError:
            return manifest_path, None, tuple(parents)
        except OSError:
            return manifest_path, "parent_unreadable", tuple(parents)
        if (
            not stat.S_ISDIR(current_stat.st_mode)
            or stat.S_ISLNK(current_stat.st_mode)
            or _is_reparse_point(current_stat)
        ):
            return manifest_path, "parent_unsafe", tuple(parents)
        parents.append((current, current_stat))
    return manifest_path, None, tuple(parents)


def _manifest_parents_changed(
    before: tuple[tuple[Path, os.stat_result], ...],
    after: tuple[tuple[Path, os.stat_result], ...],
) -> bool:
    if len(before) != len(after):
        return True

    def directory_identity_changed(
        before_stat: os.stat_result,
        after_stat: os.stat_result,
    ) -> bool:
        before_inode = int(getattr(before_stat, "st_ino", 0) or 0)
        after_inode = int(getattr(after_stat, "st_ino", 0) or 0)
        return bool(
            int(before_stat.st_dev) != int(after_stat.st_dev)
            or (
                before_inode != 0
                and after_inode != 0
                and before_inode != after_inode
            )
            or stat.S_IFMT(before_stat.st_mode) != stat.S_IFMT(after_stat.st_mode)
            or _is_reparse_point(before_stat) != _is_reparse_point(after_stat)
        )

    return any(
        before_path != after_path
        or directory_identity_changed(before_stat, after_stat)
        for (before_path, before_stat), (after_path, after_stat) in zip(
            before,
            after,
        )
    )


@dataclass(frozen=True)
class DoctorInputSnapshot:
    relative_path: str
    observed_at: str
    state: str
    identity: str | None
    size_bytes: int | None
    maximum_bytes: int
    reason_code: str | None = None

    def __post_init__(self) -> None:
        _safe_relative_path(self.relative_path)
        _utc_timestamp(self.observed_at)
        _maximum_bytes(self.maximum_bytes)
        if self.state not in _SNAPSHOT_STATES:
            raise ValueError("doctor_snapshot_state_invalid")
        if self.state == "present":
            if (
                type(self.identity) is not str
                or len(self.identity) != 71
                or not self.identity.startswith("sha256:")
                or any(character not in "0123456789abcdef" for character in self.identity[7:])
                or type(self.size_bytes) is not int
                or self.size_bytes < 0
                or self.reason_code is not None
            ):
                raise ValueError("doctor_snapshot_present_invalid")
        elif self.identity is not None or self.size_bytes is not None:
            raise ValueError("doctor_snapshot_nonpresent_identity_invalid")
        if self.state == "absent" and self.reason_code is not None:
            raise ValueError("doctor_snapshot_absent_reason_invalid")
        if self.state == "unavailable" and (
            type(self.reason_code) is not str or not self.reason_code
        ):
            raise ValueError("doctor_snapshot_unavailable_reason_missing")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": DOCTOR_INPUT_SNAPSHOT_SCHEMA,
            "relative_path": self.relative_path,
            "observed_at": self.observed_at,
            "state": self.state,
            "identity": self.identity,
            "size_bytes": self.size_bytes,
            "maximum_bytes": self.maximum_bytes,
            "reason_code": self.reason_code,
            "basis": DOCTOR_INPUT_SNAPSHOT_BASIS,
            "exact_bytes_returned_separately": self.state == "present",
            "absolute_path_echoed": False,
            "private_values_echoed": False,
            "external_effects_performed": False,
        }


@dataclass(frozen=True)
class DoctorInputRevalidation:
    observed: DoctorInputSnapshot
    revalidated: DoctorInputSnapshot
    state: str
    reason_codes: tuple[str, ...]
    requires_nonzero_exit: bool

    def __post_init__(self) -> None:
        if self.state not in _REVALIDATION_STATES:
            raise ValueError("doctor_revalidation_state_invalid")
        if type(self.reason_codes) is not tuple:
            raise ValueError("doctor_revalidation_reasons_invalid")
        if type(self.requires_nonzero_exit) is not bool:
            raise ValueError("doctor_revalidation_exit_flag_invalid")
        if self.observed.relative_path != self.revalidated.relative_path:
            raise ValueError("doctor_revalidation_path_mismatch")
        if any(type(reason) is not str or not reason for reason in self.reason_codes):
            raise ValueError("doctor_revalidation_reason_invalid")
        if self.state == "current" and (
            self.reason_codes or self.requires_nonzero_exit
        ):
            raise ValueError("doctor_revalidation_current_invalid")
        if self.state != "current" and (
            not self.reason_codes or not self.requires_nonzero_exit
        ):
            raise ValueError("doctor_revalidation_failure_invalid")

    @property
    def result_current(self) -> bool:
        return self.state == "current"

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": DOCTOR_INPUT_REVALIDATION_SCHEMA,
            "scope": self.observed.relative_path,
            "basis": DOCTOR_INPUT_SNAPSHOT_BASIS,
            "observed_at": self.observed.observed_at,
            "observed_state": self.observed.state,
            "observed_identity": self.observed.identity,
            "observed_size_bytes": self.observed.size_bytes,
            "observed_reason_code": self.observed.reason_code,
            "revalidated_at": self.revalidated.observed_at,
            "revalidated_state": self.revalidated.state,
            "revalidated_identity": self.revalidated.identity,
            "revalidated_size_bytes": self.revalidated.size_bytes,
            "revalidated_reason_code": self.revalidated.reason_code,
            "state": self.state,
            "reason_codes": list(self.reason_codes),
            "result_current": self.result_current,
            "requires_nonzero_exit": self.requires_nonzero_exit,
            "freshness_scope": "declared_input_only",
            "full_archive_atomic_snapshot": False,
            "absolute_path_echoed": False,
            "private_values_echoed": False,
            "external_effects_performed": False,
        }


_READ_REASON_CODES = {
    "unreadable": "object_manifest_snapshot_unreadable",
    "symlink": "object_manifest_snapshot_symlink",
    "reparse": "object_manifest_snapshot_reparse",
    "special": "object_manifest_snapshot_special_file",
    "too_large": "object_manifest_snapshot_too_large",
    "changed": "object_manifest_snapshot_changed_during_read",
    "outside_root": "object_manifest_snapshot_outside_archive_root",
    "parent_changed": "object_manifest_snapshot_parent_changed_during_read",
}


def capture_doctor_object_manifest_snapshot(
    archive_root: Path,
    *,
    maximum_bytes: int = DOCTOR_OBJECT_MANIFEST_MAX_BYTES,
    observed_at: str | None = None,
    root_boundary: DoctorArchiveRootBoundary | None = None,
) -> tuple[bytes | None, DoctorInputSnapshot]:
    """Capture the exact object-manifest bytes one Doctor stage must parse."""

    cap = _maximum_bytes(maximum_bytes)
    supplied_timestamp = (
        _utc_timestamp(observed_at) if observed_at is not None else None
    )
    requested_root = Path(archive_root)
    if root_boundary is None:
        manifest_path, path_reason, _initial_parents = _manifest_path_state(
            requested_root
        )
        if path_reason is not None:
            return None, DoctorInputSnapshot(
                relative_path=DOCTOR_OBJECT_MANIFEST_RELATIVE_PATH,
                observed_at=supplied_timestamp or _utc_timestamp(),
                state="unavailable",
                identity=None,
                size_bytes=None,
                maximum_bytes=cap,
                reason_code=f"object_manifest_snapshot_{path_reason}",
            )
        root_boundary = capture_doctor_archive_root_boundary(requested_root)
    elif (
        os.path.normcase(os.path.abspath(os.fspath(requested_root)))
        != os.path.normcase(
            os.path.abspath(os.fspath(root_boundary.canonical_path))
        )
        or not doctor_archive_root_boundary_is_current(root_boundary)
    ):
        root_boundary = None
    if root_boundary is None:
        return None, DoctorInputSnapshot(
            relative_path=DOCTOR_OBJECT_MANIFEST_RELATIVE_PATH,
            observed_at=supplied_timestamp or _utc_timestamp(),
            state="unavailable",
            identity=None,
            size_bytes=None,
            maximum_bytes=cap,
            reason_code="object_manifest_snapshot_archive_root_unverified",
        )
    canonical_root = root_boundary.canonical_path
    manifest_path, path_reason, parents_before = _manifest_path_state(
        canonical_root
    )
    if path_reason is not None:
        return None, DoctorInputSnapshot(
            relative_path=DOCTOR_OBJECT_MANIFEST_RELATIVE_PATH,
            observed_at=supplied_timestamp or _utc_timestamp(),
            state="unavailable",
            identity=None,
            size_bytes=None,
            maximum_bytes=cap,
            reason_code=f"object_manifest_snapshot_{path_reason}",
        )

    raw, read_reason = _stable_regular_file_bytes(
        manifest_path,
        maximum_bytes=cap,
        required_root=root_boundary,
    )
    _post_path, post_reason, parents_after = _manifest_path_state(
        canonical_root
    )
    if post_reason is not None or _manifest_parents_changed(
        parents_before,
        parents_after,
    ):
        raw = None
        read_reason = "parent_changed"
    if read_reason == "missing":
        return None, DoctorInputSnapshot(
            relative_path=DOCTOR_OBJECT_MANIFEST_RELATIVE_PATH,
            observed_at=supplied_timestamp or _utc_timestamp(),
            state="absent",
            identity=None,
            size_bytes=None,
            maximum_bytes=cap,
        )
    if read_reason is not None or raw is None:
        return None, DoctorInputSnapshot(
            relative_path=DOCTOR_OBJECT_MANIFEST_RELATIVE_PATH,
            observed_at=supplied_timestamp or _utc_timestamp(),
            state="unavailable",
            identity=None,
            size_bytes=None,
            maximum_bytes=cap,
            reason_code=_READ_REASON_CODES.get(
                str(read_reason),
                "object_manifest_snapshot_unavailable",
            ),
        )
    identity = "sha256:" + hashlib.sha256(raw).hexdigest()
    return raw, DoctorInputSnapshot(
        relative_path=DOCTOR_OBJECT_MANIFEST_RELATIVE_PATH,
        observed_at=supplied_timestamp or _utc_timestamp(),
        state="present",
        identity=identity,
        size_bytes=len(raw),
        maximum_bytes=cap,
    )


def revalidate_doctor_object_manifest_snapshot(
    archive_root: Path,
    observed: DoctorInputSnapshot,
    *,
    revalidated_at: str | None = None,
    root_boundary: DoctorArchiveRootBoundary | None = None,
) -> DoctorInputRevalidation:
    """Re-read the manifest and classify completion freshness fail-closed."""

    if observed.relative_path != DOCTOR_OBJECT_MANIFEST_RELATIVE_PATH:
        raise ValueError("doctor_object_manifest_snapshot_path_invalid")
    _raw, current = capture_doctor_object_manifest_snapshot(
        archive_root,
        maximum_bytes=observed.maximum_bytes,
        observed_at=revalidated_at,
        root_boundary=root_boundary,
    )
    if observed.state == "unavailable" or current.state == "unavailable":
        return DoctorInputRevalidation(
            observed=observed,
            revalidated=current,
            state="unverified",
            reason_codes=("object_manifest_snapshot_unverified",),
            requires_nonzero_exit=True,
        )
    if observed.state == current.state and observed.identity == current.identity:
        return DoctorInputRevalidation(
            observed=observed,
            revalidated=current,
            state="current",
            reason_codes=(),
            requires_nonzero_exit=False,
        )
    return DoctorInputRevalidation(
        observed=observed,
        revalidated=current,
        state="stale",
        reason_codes=("object_manifest_changed_during_doctor",),
        requires_nonzero_exit=True,
    )


def doctor_exit_code_with_snapshot(
    base_exit_code: int,
    revalidation: DoctorInputRevalidation,
) -> int:
    """Preserve an existing failure, otherwise fail when freshness is unsafe."""

    if type(base_exit_code) is not int or not 0 <= base_exit_code <= 255:
        raise ValueError("doctor_base_exit_code_invalid")
    if not isinstance(revalidation, DoctorInputRevalidation):
        raise TypeError("doctor_revalidation_invalid")
    if base_exit_code != 0:
        return base_exit_code
    return 1 if revalidation.requires_nonzero_exit else 0
