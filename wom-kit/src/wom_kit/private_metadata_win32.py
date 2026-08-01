"""Retained-handle Win32 primitives for the v0.3.296 private writer.

This module deliberately contains no writer state machine.  It supplies the
small, auditable Windows/NTFS boundary used by that state machine:

* retained non-reparse directory guards;
* persistent, identity-bound ``LockFileEx`` coordination locks;
* the directive's exact file-handle access/share profiles;
* allow-listed ``CREATE_NEW`` temp materialization;
* create-if-absent directory and hard-link publication;
* source-handle ``FileRenameInfo`` replacement; and
* retained-handle ``FileDispositionInfo`` cleanup.

Mutation helpers fail closed on non-Windows platforms.  Read-only callers can
import this module everywhere and inspect :func:`approval_support_status`
without creating a file or directory.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Iterator


WINDOWS_NTFS_MUTATION_PROFILE = (
    "windows_ntfs_win32_process_interruption/v0.1"
)
APPROVAL_PLATFORM_NOT_SUPPORTED = (
    "private_metadata_approval_platform_not_supported"
)
REQUIRED_PRIMITIVE_UNAVAILABLE = (
    "private_metadata_required_win32_primitive_unavailable"
)
AUTHORITY_PATH_UNSAFE = "private_metadata_authority_path_unsafe"
MUTATION_GUARD_IDENTITY_CHANGED = (
    "private_metadata_mutation_guard_identity_changed"
)
LOCK_PATH_UNSAFE = "private_metadata_lock_path_unsafe"
LOCK_IDENTITY_CHANGED = "private_metadata_lock_identity_changed"
RECEIPT_DIRECTORY_BOOTSTRAP_FAILED = (
    "private_metadata_receipt_directory_bootstrap_failed"
)
OBJECT_MANIFEST_DIRECTORY_BOOTSTRAP_FAILED = (
    "private_metadata_object_manifest_directory_bootstrap_failed"
)
OWNED_TEMP_SUBSTITUTED = "private_metadata_owned_temp_substituted"
UNEXPECTED_HARDLINK = "private_metadata_unexpected_hardlink"
OWNED_TEMP_MATERIALIZATION_FAILED = (
    "private_metadata_owned_temp_materialization_failed"
)
HARDLINK_PUBLICATION_FAILED = (
    "private_metadata_hardlink_publication_failed"
)
MANIFEST_REPLACEMENT_FAILED = (
    "private_metadata_manifest_replacement_failed"
)
RESIDUE_DISPOSITION_FAILED = (
    "private_metadata_residue_disposition_failed"
)
FINAL_VERIFICATION_FAILED = "private_metadata_final_verification_failed"

OBJECT_MANIFEST_LOCK_RELATIVE_PATH = (
    "objects/manifests/.files.jsonl.lock"
)
PRIVATE_METADATA_LOCK_RELATIVE_PATH = (
    "objects/manifests/.private-source-metadata.jsonl.lock"
)
PRIVATE_JOURNAL_RELATIVE_PATH = (
    "objects/manifests/.private-source-metadata-write.journal.json"
)
PRIVATE_MANIFEST_RELATIVE_PATH = (
    "objects/manifests/private-source-metadata.jsonl"
)
PRIVATE_RECEIPT_DIRECTORY_RELATIVE_PATH = (
    "receipts/objects/private-source-metadata"
)

_AUTHORITY_KEY_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_WINDOWS_AVAILABLE = os.name == "nt" and sys.platform == "win32"
# The original exact-minimal profile was disabled after the 2026-08-01 NTFS
# probe proved an out-of-bounds NUL scan.  The corrected two-byte readable NUL
# guard and the complete approval executor received two independent CLEAR
# verdicts before this production gate was opened.
_MINIMAL_RENAME_PROFILE_APPROVAL_ENABLED = True


# Win32 constants are written out rather than imported from pywin32 so the
# package keeps its dependency-light contract.
_DELETE = 0x00010000
_FILE_LIST_DIRECTORY = 0x00000001
_FILE_READ_ATTRIBUTES = 0x00000080
_GENERIC_READ = 0x80000000
_GENERIC_WRITE = 0x40000000

_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_FILE_SHARE_DELETE = 0x00000004

_CREATE_NEW = 1
_OPEN_EXISTING = 3

_FILE_ATTRIBUTE_DIRECTORY = 0x00000010
_FILE_ATTRIBUTE_NORMAL = 0x00000080
_FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000

_FILE_TYPE_DISK = 0x0001
_LOCKFILE_EXCLUSIVE_LOCK = 0x00000002
_LOCKFILE_FAIL_IMMEDIATELY = 0x00000001

_FILE_RENAME_INFO_CLASS = 3
_FILE_DISPOSITION_INFO_CLASS = 4

_DRIVE_REMOVABLE = 2
_DRIVE_FIXED = 3
_DRIVE_RAMDISK = 6
_LOCAL_DRIVE_TYPES = {
    _DRIVE_REMOVABLE,
    _DRIVE_FIXED,
    _DRIVE_RAMDISK,
}

_ERROR_ACCESS_DENIED = 5
_ERROR_FILE_NOT_FOUND = 2
_ERROR_PATH_NOT_FOUND = 3
_ERROR_INVALID_HANDLE = 6
_ERROR_SHARING_VIOLATION = 32
_ERROR_FILE_EXISTS = 80
_ERROR_ALREADY_EXISTS = 183
_ABSENT_WINERRORS = {_ERROR_FILE_NOT_FOUND, _ERROR_PATH_NOT_FOUND}


class Win32SafetyError(RuntimeError):
    """A content-free refusal from the retained-handle boundary.

    ``str(exc)`` is intentionally only the closed WOM reason code.  Paths and
    operating-system exception text are not reflected into CLI output.  The
    numeric Win32 error and a closed operation label remain available for
    deterministic internal classification and tests.
    """

    def __init__(
        self,
        reason: str,
        *,
        operation: str,
        winerror: int | None = None,
    ) -> None:
        self.reason = reason
        self.operation = operation
        self.winerror = winerror
        super().__init__(reason)


class MutationEffect(Enum):
    NO_CHANGE_PROVED = "no_change_proved"
    STATE_CHANGE_PROVED = "state_change_proved"
    STATE_CHANGE_POSSIBLE = "state_change_possible"


class MutationCheckpoint(Enum):
    OWNED_TEMP_CREATE = "owned_temp_create"
    OWNED_TEMP_WRITE = "owned_temp_write"
    OWNED_TEMP_FLUSH = "owned_temp_flush"
    OWNED_TEMP_VERIFY = "owned_temp_verify"
    HARDLINK_PRECONDITION = "hardlink_precondition"
    HARDLINK_API = "hardlink_api"
    HARDLINK_POSTCHECK = "hardlink_postcheck"
    MANIFEST_PRECONDITION = "manifest_precondition"
    MANIFEST_RENAME_API = "manifest_rename_api"
    MANIFEST_POSTCHECK = "manifest_postcheck"
    RESIDUE_PRECONDITION = "residue_precondition"
    RESIDUE_API = "residue_api"
    RESIDUE_POSTCHECK = "residue_postcheck"
    HANDOFF = "handoff"


@dataclass
class RetainedAuthorityTransfer:
    role: str
    bound: Any
    name_state: str
    terminal_release_first: bool = False
    expected_link_count_after_terminal_release: int | None = None


class Win32MutationFailure(Win32SafetyError):
    """Mutation failure that transfers every still-live authority upward."""

    def __init__(
        self,
        reason: str,
        *,
        operation: str,
        checkpoint: MutationCheckpoint,
        effect: MutationEffect,
        authorities: Iterable[RetainedAuthorityTransfer] = (),
        winerror: int | None = None,
        terminal_release_required: bool = False,
    ) -> None:
        super().__init__(
            reason,
            operation=operation,
            winerror=winerror,
        )
        self.checkpoint = checkpoint
        self.effect = effect
        self._authorities = list(authorities)
        self._taken = False
        self.terminal_release_required = terminal_release_required

    def take_authorities(self) -> tuple[RetainedAuthorityTransfer, ...]:
        if self._taken:
            raise RuntimeError(
                "private_metadata_failure_authorities_already_taken"
            )
        self._taken = True
        authorities = tuple(self._authorities)
        self._authorities.clear()
        return authorities


@dataclass(frozen=True)
class ApprovalSupportStatus:
    supported: bool
    reason: str | None
    mutation_platform_profile: str
    filesystem_name: str | None
    local_volume: bool | None


@dataclass(frozen=True, order=True)
class Win32FileIdentity:
    volume_serial: int
    file_index: int


@dataclass(frozen=True)
class Win32FileInformation:
    identity: Win32FileIdentity
    attributes: int
    link_count: int
    byte_count: int
    file_type: int

    @property
    def is_directory(self) -> bool:
        return bool(self.attributes & _FILE_ATTRIBUTE_DIRECTORY)

    @property
    def is_reparse_point(self) -> bool:
        return bool(self.attributes & _FILE_ATTRIBUTE_REPARSE_POINT)

    @property
    def is_regular_file(self) -> bool:
        return (
            self.file_type == _FILE_TYPE_DISK
            and not self.is_directory
            and not self.is_reparse_point
        )


@dataclass(frozen=True)
class FileRenameInfoBuffer:
    """Exact logical FILE_RENAME_INFO plus its two-byte backing guard."""

    backing: Any
    file_name_offset: int
    file_name_length: int
    logical_size: int
    backing_size: int
    api_buffer_size: int


class FileHandleProfile(Enum):
    """The six exact file handle profiles from directive section 8.1."""

    AUTHORITY_READ = (
        _GENERIC_READ | _FILE_READ_ATTRIBUTES,
        _FILE_SHARE_READ,
    )
    COORDINATION_LOCK = (
        _GENERIC_READ | _GENERIC_WRITE | _FILE_READ_ATTRIBUTES,
        _FILE_SHARE_READ | _FILE_SHARE_WRITE,
    )
    MUTATION_SOURCE = (
        _GENERIC_READ
        | _GENERIC_WRITE
        | _DELETE
        | _FILE_READ_ATTRIBUTES,
        _FILE_SHARE_READ,
    )
    NARROW_READ = (
        _GENERIC_READ | _FILE_READ_ATTRIBUTES,
        _FILE_SHARE_READ,
    )
    TRANSITIONAL_READ = (
        _GENERIC_READ | _FILE_READ_ATTRIBUTES,
        _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
    )
    RESIDUE_DISPOSITION = (
        _GENERIC_READ | _DELETE | _FILE_READ_ATTRIBUTES,
        _FILE_SHARE_READ,
    )

    @property
    def desired_access(self) -> int:
        return int(self.value[0])

    @property
    def share_mode(self) -> int:
        return int(self.value[1])


class CoordinationLockKind(Enum):
    OBJECT_MANIFEST = OBJECT_MANIFEST_LOCK_RELATIVE_PATH
    PRIVATE_METADATA = PRIVATE_METADATA_LOCK_RELATIVE_PATH


class OwnedTempKind(Enum):
    JOURNAL = "journal"
    MANIFEST = "manifest"
    RECEIPT = "receipt"


def owned_temp_relative_path(
    kind: OwnedTempKind,
    authority_key_hex: str,
) -> str:
    """Return one of the three and only three v0.3.296 owned temp paths."""

    if not _AUTHORITY_KEY_HEX_RE.fullmatch(authority_key_hex):
        raise ValueError("private_metadata_authority_key_invalid")
    if kind is OwnedTempKind.JOURNAL:
        return (
            "objects/manifests/"
            f".private-source-metadata-write.{authority_key_hex}.journal.tmp"
        )
    if kind is OwnedTempKind.MANIFEST:
        return (
            "objects/manifests/"
            f".private-source-metadata-write.{authority_key_hex}.manifest.tmp"
        )
    if kind is OwnedTempKind.RECEIPT:
        return (
            "receipts/objects/private-source-metadata/"
            f".{authority_key_hex}.receipt.tmp"
        )
    raise AssertionError("unreachable owned temp kind")


def receipt_relative_path(authority_key_hex: str) -> str:
    if not _AUTHORITY_KEY_HEX_RE.fullmatch(authority_key_hex):
        raise ValueError("private_metadata_authority_key_invalid")
    return (
        "receipts/objects/private-source-metadata/"
        f"{authority_key_hex}.json"
    )


def _closed_error(
    reason: str,
    operation: str,
    *,
    winerror: int | None = None,
) -> Win32SafetyError:
    return Win32SafetyError(
        reason,
        operation=operation,
        winerror=winerror,
    )


def _last_error(reason: str, operation: str) -> Win32SafetyError:
    return _closed_error(
        reason,
        operation,
        winerror=ctypes.get_last_error(),
    )


def _handle_value(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    raw = getattr(value, "value", None)
    return int(raw) if raw is not None else None


def _require_windows(operation: str) -> None:
    if not _WINDOWS_AVAILABLE:
        raise _closed_error(
            APPROVAL_PLATFORM_NOT_SUPPORTED,
            operation,
        )


def _absolute_lexical_path(path: Path | str) -> Path:
    raw = os.fspath(path)
    if "\x00" in raw:
        raise _closed_error(
            AUTHORITY_PATH_UNSAFE,
            "normalize_path",
        )
    absolute = Path(os.path.abspath(raw))
    anchor = absolute.anchor
    if not anchor:
        raise _closed_error(
            AUTHORITY_PATH_UNSAFE,
            "normalize_path",
        )
    # Alternate data streams are outside the v0.3.296 path contract.
    if ":" in str(absolute)[len(anchor) :]:
        raise _closed_error(
            AUTHORITY_PATH_UNSAFE,
            "normalize_path",
        )
    return absolute


def _path_key(path: Path | str) -> str:
    return os.path.normcase(str(_absolute_lexical_path(path)))


def _extended_path(path: Path | str) -> str:
    """Return an exact extended-length absolute Win32 path."""

    value = str(_absolute_lexical_path(path))
    if value.startswith("\\\\?\\"):
        return value
    if value.startswith("\\\\"):
        return "\\\\?\\UNC\\" + value[2:]
    return "\\\\?\\" + value


def _contains_path(root: Path, candidate: Path) -> bool:
    try:
        common = os.path.commonpath(
            (os.path.normcase(str(root)), os.path.normcase(str(candidate)))
        )
    except ValueError:
        return False
    return common == os.path.normcase(str(root))


def _archive_path(root: Path, relative_path: str) -> Path:
    if not relative_path or "\x00" in relative_path:
        raise _closed_error(
            AUTHORITY_PATH_UNSAFE,
            "archive_relative_path",
        )
    normalized_separators = relative_path.replace("/", os.sep)
    candidate_relative = Path(normalized_separators)
    if candidate_relative.is_absolute() or any(
        part in {"", ".", ".."} for part in candidate_relative.parts
    ):
        raise _closed_error(
            AUTHORITY_PATH_UNSAFE,
            "archive_relative_path",
        )
    candidate = _absolute_lexical_path(root / candidate_relative)
    if not _contains_path(root, candidate):
        raise _closed_error(
            AUTHORITY_PATH_UNSAFE,
            "archive_relative_path",
        )
    return candidate


class _Win32Api:
    """ctypes bindings loaded only on Windows."""

    def __init__(self) -> None:
        _require_windows("load_win32_primitives")
        try:
            from ctypes import wintypes

            ulong_ptr = (
                ctypes.c_ulonglong
                if ctypes.sizeof(ctypes.c_void_p) == 8
                else ctypes.c_ulong
            )

            class _ByHandleFileInformation(ctypes.Structure):
                _fields_ = [
                    ("file_attributes", wintypes.DWORD),
                    ("creation_time", wintypes.FILETIME),
                    ("last_access_time", wintypes.FILETIME),
                    ("last_write_time", wintypes.FILETIME),
                    ("volume_serial_number", wintypes.DWORD),
                    ("file_size_high", wintypes.DWORD),
                    ("file_size_low", wintypes.DWORD),
                    ("number_of_links", wintypes.DWORD),
                    ("file_index_high", wintypes.DWORD),
                    ("file_index_low", wintypes.DWORD),
                ]

            class _Overlapped(ctypes.Structure):
                _fields_ = [
                    ("internal", ulong_ptr),
                    ("internal_high", ulong_ptr),
                    ("offset", wintypes.DWORD),
                    ("offset_high", wintypes.DWORD),
                    ("event", wintypes.HANDLE),
                ]

            class _FileRenameInfoLayout(ctypes.Structure):
                _fields_ = [
                    ("replace_if_exists", wintypes.BOOLEAN),
                    ("root_directory", wintypes.HANDLE),
                    ("file_name_length", wintypes.DWORD),
                    ("file_name", wintypes.WCHAR * 1),
                ]

            class _FileDispositionInfo(ctypes.Structure):
                _fields_ = [("delete_file", wintypes.BOOL)]

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

            self.create_file = kernel32.CreateFileW
            self.create_file.argtypes = [
                wintypes.LPCWSTR,
                wintypes.DWORD,
                wintypes.DWORD,
                ctypes.c_void_p,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.HANDLE,
            ]
            self.create_file.restype = wintypes.HANDLE

            self.close_handle = kernel32.CloseHandle
            self.close_handle.argtypes = [wintypes.HANDLE]
            self.close_handle.restype = wintypes.BOOL

            self.get_handle_information = kernel32.GetHandleInformation
            self.get_handle_information.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(wintypes.DWORD),
            ]
            self.get_handle_information.restype = wintypes.BOOL

            self.get_file_information = (
                kernel32.GetFileInformationByHandle
            )
            self.get_file_information.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(_ByHandleFileInformation),
            ]
            self.get_file_information.restype = wintypes.BOOL

            self.get_file_type = kernel32.GetFileType
            self.get_file_type.argtypes = [wintypes.HANDLE]
            self.get_file_type.restype = wintypes.DWORD

            self.set_file_pointer = kernel32.SetFilePointerEx
            self.set_file_pointer.argtypes = [
                wintypes.HANDLE,
                ctypes.c_longlong,
                ctypes.POINTER(ctypes.c_longlong),
                wintypes.DWORD,
            ]
            self.set_file_pointer.restype = wintypes.BOOL

            self.read_file = kernel32.ReadFile
            self.read_file.argtypes = [
                wintypes.HANDLE,
                ctypes.c_void_p,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
                ctypes.c_void_p,
            ]
            self.read_file.restype = wintypes.BOOL

            self.write_file = kernel32.WriteFile
            self.write_file.argtypes = [
                wintypes.HANDLE,
                ctypes.c_void_p,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
                ctypes.c_void_p,
            ]
            self.write_file.restype = wintypes.BOOL

            self.flush_file_buffers = kernel32.FlushFileBuffers
            self.flush_file_buffers.argtypes = [wintypes.HANDLE]
            self.flush_file_buffers.restype = wintypes.BOOL

            self.create_directory = kernel32.CreateDirectoryW
            self.create_directory.argtypes = [
                wintypes.LPCWSTR,
                ctypes.c_void_p,
            ]
            self.create_directory.restype = wintypes.BOOL

            self.create_hard_link = kernel32.CreateHardLinkW
            self.create_hard_link.argtypes = [
                wintypes.LPCWSTR,
                wintypes.LPCWSTR,
                ctypes.c_void_p,
            ]
            self.create_hard_link.restype = wintypes.BOOL

            self.set_file_information = (
                kernel32.SetFileInformationByHandle
            )
            self.set_file_information.argtypes = [
                wintypes.HANDLE,
                ctypes.c_int,
                ctypes.c_void_p,
                wintypes.DWORD,
            ]
            self.set_file_information.restype = wintypes.BOOL

            self.lock_file = kernel32.LockFileEx
            self.lock_file.argtypes = [
                wintypes.HANDLE,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.DWORD,
                ctypes.POINTER(_Overlapped),
            ]
            self.lock_file.restype = wintypes.BOOL

            self.unlock_file = kernel32.UnlockFileEx
            self.unlock_file.argtypes = [
                wintypes.HANDLE,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.DWORD,
                ctypes.POINTER(_Overlapped),
            ]
            self.unlock_file.restype = wintypes.BOOL

            self.get_volume_information_by_handle = (
                kernel32.GetVolumeInformationByHandleW
            )
            self.get_volume_information_by_handle.argtypes = [
                wintypes.HANDLE,
                wintypes.LPWSTR,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
                ctypes.POINTER(wintypes.DWORD),
                ctypes.POINTER(wintypes.DWORD),
                wintypes.LPWSTR,
                wintypes.DWORD,
            ]
            self.get_volume_information_by_handle.restype = wintypes.BOOL

            self.get_volume_path_name = kernel32.GetVolumePathNameW
            self.get_volume_path_name.argtypes = [
                wintypes.LPCWSTR,
                wintypes.LPWSTR,
                wintypes.DWORD,
            ]
            self.get_volume_path_name.restype = wintypes.BOOL

            self.get_drive_type = kernel32.GetDriveTypeW
            self.get_drive_type.argtypes = [wintypes.LPCWSTR]
            self.get_drive_type.restype = wintypes.UINT

            self._wintypes = wintypes
            self.ByHandleFileInformation = _ByHandleFileInformation
            self.Overlapped = _Overlapped
            self.FileRenameInfoLayout = _FileRenameInfoLayout
            self.FileDispositionInfo = _FileDispositionInfo
            self.invalid_handle_value = ctypes.c_void_p(-1).value
        except (AttributeError, ImportError, OSError) as exc:
            raise _closed_error(
                REQUIRED_PRIMITIVE_UNAVAILABLE,
                "load_win32_primitives",
            ) from exc


_API: _Win32Api | None = None


def _api() -> _Win32Api:
    global _API
    if _API is None:
        _API = _Win32Api()
    return _API


def _query_information(handle: int) -> Win32FileInformation:
    api = _api()
    raw = api.ByHandleFileInformation()
    if not api.get_file_information(handle, ctypes.byref(raw)):
        raise _last_error(
            FINAL_VERIFICATION_FAILED,
            "get_file_information",
        )
    file_type = int(api.get_file_type(handle))
    if file_type == 0:
        last_error = ctypes.get_last_error()
        if last_error:
            raise _closed_error(
                FINAL_VERIFICATION_FAILED,
                "get_file_type",
                winerror=last_error,
            )
    return Win32FileInformation(
        identity=Win32FileIdentity(
            volume_serial=int(raw.volume_serial_number),
            file_index=(
                int(raw.file_index_high) << 32
            )
            | int(raw.file_index_low),
        ),
        attributes=int(raw.file_attributes),
        link_count=int(raw.number_of_links),
        byte_count=(
            int(raw.file_size_high) << 32
        )
        | int(raw.file_size_low),
        file_type=file_type,
    )


def _close_raw_handle(
    handle: int,
    *,
    reason: str,
    operation: str,
) -> None:
    if not _api().close_handle(handle):
        raise _last_error(reason, operation)


def _release_raw_handle_until_closed(
    handle: int,
    *,
    reason: str,
    operation: str,
) -> None:
    """Release one raw authority without path access or finalizer reliance."""

    del reason, operation
    api = _api()
    for _cycle in range(3):
        if _api().close_handle(handle):
            return
        flags = api._wintypes.DWORD()
        ctypes.set_last_error(0)
        if not api.get_handle_information(
            handle,
            ctypes.byref(flags),
        ) and ctypes.get_last_error() == _ERROR_INVALID_HANDLE:
            return
        # Proved-live and indeterminate queries both permit only the next
        # same-raw-value terminal cycle.
    os._exit(74)


def _close_raw_handle_with_terminal_fallback(
    handle: int,
    *,
    reason: str,
    operation: str,
) -> None:
    """Surface the first close fault after bounded same-handle release."""

    try:
        _close_raw_handle(
            handle,
            reason=reason,
            operation=operation,
        )
    except Win32SafetyError:
        _release_raw_handle_until_closed(
            handle,
            reason=reason,
            operation=f"{operation}_terminal_release",
        )
        raise


def release_terminal_bound_authority(
    bound: Win32BoundFile,
    *,
    reason: str = RESIDUE_DISPOSITION_FAILED,
    operation: str = "residue_terminal_authority_release",
) -> None:
    """Release the exact retained residue before any other authority."""

    if bound.closed:
        return
    handle = bound.raw_handle
    _release_raw_handle_until_closed(
        handle,
        reason=reason,
        operation=operation,
    )
    bound._handle = None


def _open_raw(
    path: Path,
    *,
    desired_access: int,
    share_mode: int,
    creation_disposition: int,
    flags: int,
    reason: str,
    operation: str,
) -> int:
    raw = _api().create_file(
        _extended_path(path),
        desired_access,
        share_mode,
        None,
        creation_disposition,
        flags,
        None,
    )
    value = _handle_value(raw)
    if value in {None, _api().invalid_handle_value}:
        raise _last_error(reason, operation)
    return int(value)


def _validate_regular_information(
    information: Win32FileInformation,
    *,
    reason: str,
    operation: str,
    expected_link_count: int | None,
    expected_volume_serial: int | None,
) -> None:
    if not information.is_regular_file or information.identity.file_index == 0:
        raise _closed_error(reason, operation)
    if (
        expected_link_count is not None
        and information.link_count != expected_link_count
    ):
        raise _closed_error(
            UNEXPECTED_HARDLINK,
            operation,
        )
    if (
        expected_volume_serial is not None
        and information.identity.volume_serial != expected_volume_serial
    ):
        raise _closed_error(reason, operation)


def _validate_directory_information(
    information: Win32FileInformation,
    *,
    reason: str,
    operation: str,
    expected_volume_serial: int | None,
) -> None:
    if (
        information.file_type != _FILE_TYPE_DISK
        or not information.is_directory
        or information.is_reparse_point
        or information.identity.file_index == 0
    ):
        raise _closed_error(reason, operation)
    if (
        expected_volume_serial is not None
        and information.identity.volume_serial != expected_volume_serial
    ):
        raise _closed_error(reason, operation)


def _open_directory_raw(
    path: Path,
    *,
    reason: str,
    operation: str,
    expected_volume_serial: int | None = None,
) -> tuple[int, Win32FileInformation]:
    handle = _open_raw(
        path,
        desired_access=_FILE_LIST_DIRECTORY | _FILE_READ_ATTRIBUTES,
        share_mode=_FILE_SHARE_READ | _FILE_SHARE_WRITE,
        creation_disposition=_OPEN_EXISTING,
        flags=(
            _FILE_FLAG_BACKUP_SEMANTICS
            | _FILE_FLAG_OPEN_REPARSE_POINT
        ),
        reason=reason,
        operation=operation,
    )
    try:
        information = _query_information(handle)
        _validate_directory_information(
            information,
            reason=reason,
            operation=operation,
            expected_volume_serial=expected_volume_serial,
        )
    except BaseException:
        try:
            _close_raw_handle_with_terminal_fallback(
                handle,
                reason=reason,
                operation=f"{operation}_close_after_refusal",
            )
        except Win32SafetyError:
            pass
        raise
    return handle, information


def _filesystem_name(handle: int) -> str:
    api = _api()
    filesystem_name = ctypes.create_unicode_buffer(64)
    serial = api._wintypes.DWORD()
    maximum_component = api._wintypes.DWORD()
    flags = api._wintypes.DWORD()
    if not api.get_volume_information_by_handle(
        handle,
        None,
        0,
        ctypes.byref(serial),
        ctypes.byref(maximum_component),
        ctypes.byref(flags),
        filesystem_name,
        len(filesystem_name),
    ):
        raise _last_error(
            REQUIRED_PRIMITIVE_UNAVAILABLE,
            "get_volume_information",
        )
    return str(filesystem_name.value)


def _is_local_volume(path: Path) -> bool:
    api = _api()
    volume_path = ctypes.create_unicode_buffer(32768)
    if not api.get_volume_path_name(
        str(path),
        volume_path,
        len(volume_path),
    ):
        raise _last_error(
            REQUIRED_PRIMITIVE_UNAVAILABLE,
            "get_volume_path_name",
        )
    return int(api.get_drive_type(volume_path.value)) in _LOCAL_DRIVE_TYPES


def _approval_environment_status(
    archive_root: Path | str,
) -> ApprovalSupportStatus:
    if not _WINDOWS_AVAILABLE:
        return ApprovalSupportStatus(
            supported=False,
            reason=APPROVAL_PLATFORM_NOT_SUPPORTED,
            mutation_platform_profile=WINDOWS_NTFS_MUTATION_PROFILE,
            filesystem_name=None,
            local_volume=None,
        )
    try:
        version = sys.getwindowsversion()
    except AttributeError:
        return ApprovalSupportStatus(
            supported=False,
            reason=APPROVAL_PLATFORM_NOT_SUPPORTED,
            mutation_platform_profile=WINDOWS_NTFS_MUTATION_PROFILE,
            filesystem_name=None,
            local_volume=None,
        )
    if (version.major, version.minor, version.build) < (10, 0, 14393):
        return ApprovalSupportStatus(
            supported=False,
            reason=APPROVAL_PLATFORM_NOT_SUPPORTED,
            mutation_platform_profile=WINDOWS_NTFS_MUTATION_PROFILE,
            filesystem_name=None,
            local_volume=None,
        )

    try:
        root = _absolute_lexical_path(archive_root)
        handle, _ = _open_directory_raw(
            root,
            reason=REQUIRED_PRIMITIVE_UNAVAILABLE,
            operation="approval_platform_root_open",
        )
        try:
            filesystem_name = _filesystem_name(handle)
            local_volume = _is_local_volume(root)
        finally:
            _close_raw_handle_with_terminal_fallback(
                handle,
                reason=REQUIRED_PRIMITIVE_UNAVAILABLE,
                operation="approval_platform_root_close",
            )
    except Win32SafetyError:
        return ApprovalSupportStatus(
            supported=False,
            reason=REQUIRED_PRIMITIVE_UNAVAILABLE,
            mutation_platform_profile=WINDOWS_NTFS_MUTATION_PROFILE,
            filesystem_name=None,
            local_volume=None,
        )

    supported = filesystem_name.upper() == "NTFS" and local_volume
    return ApprovalSupportStatus(
        supported=supported,
        reason=None if supported else APPROVAL_PLATFORM_NOT_SUPPORTED,
        mutation_platform_profile=WINDOWS_NTFS_MUTATION_PROFILE,
        filesystem_name=filesystem_name,
        local_volume=local_volume,
    )


def approval_support_status(
    archive_root: Path | str,
) -> ApprovalSupportStatus:
    """Return the v0.3.296 approval-platform decision.

    On non-Windows platforms this function returns before touching
    ``archive_root``.  Windows must be version 10.0.14393 or newer and the
    supplied existing root must live on a local NTFS volume.  The result also
    remains fail-closed while any directive-required mutation primitive has a
    confirmed unsafe profile.
    """

    environment = _approval_environment_status(archive_root)
    if not environment.supported:
        return environment
    if not _MINIMAL_RENAME_PROFILE_APPROVAL_ENABLED:
        return ApprovalSupportStatus(
            supported=False,
            reason=REQUIRED_PRIMITIVE_UNAVAILABLE,
            mutation_platform_profile=WINDOWS_NTFS_MUTATION_PROFILE,
            filesystem_name=environment.filesystem_name,
            local_volume=environment.local_volume,
        )
    return environment


class Win32UnverifiedCreatedFile:
    """Exact CREATE_NEW handle retained when post-create proof fails."""

    def __init__(self, *, path: Path, handle: int) -> None:
        self.path = path
        self.profile = FileHandleProfile.MUTATION_SOURCE
        self.expected_link_count = 1
        self._handle: int | None = handle

    @property
    def raw_handle(self) -> int:
        if self._handle is None:
            raise _closed_error(
                FINAL_VERIFICATION_FAILED,
                "closed_created_handle",
            )
        return self._handle

    @property
    def closed(self) -> bool:
        return self._handle is None

    def detach(self) -> int:
        handle = self.raw_handle
        self._handle = None
        return handle

    def close(
        self,
        *,
        reason: str = FINAL_VERIFICATION_FAILED,
        operation: str = "created_handle_close",
    ) -> None:
        if self._handle is None:
            return
        handle = self._handle
        _close_raw_handle(
            handle,
            reason=reason,
            operation=operation,
        )
        self._handle = None

    def __del__(self) -> None:
        if self._handle is not None and _WINDOWS_AVAILABLE:
            try:
                _api().close_handle(self._handle)
            except BaseException:
                pass
            self._handle = None


class Win32BoundFile:
    """One retained file handle bound to an immutable file identity."""

    def __init__(
        self,
        *,
        path: Path,
        handle: int,
        profile: FileHandleProfile,
        information: Win32FileInformation,
        expected_link_count: int | None,
        expected_byte_count: int | None = None,
        expected_sha256: str | None = None,
    ) -> None:
        self.path = path
        self.profile = profile
        self.identity = information.identity
        self.initial_information = information
        self.expected_link_count = expected_link_count
        self.expected_byte_count = expected_byte_count
        self.expected_sha256 = expected_sha256
        self._handle: int | None = handle

    def bind_proved_content(
        self,
        *,
        expected_byte_count: int,
        expected_sha256: str,
        reason: str = FINAL_VERIFICATION_FAILED,
    ) -> None:
        """Bind an already-proved planned byte authority exactly once."""

        if expected_byte_count < 0:
            raise _closed_error(reason, "bound_content_size_invalid")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", expected_sha256):
            raise _closed_error(reason, "bound_content_digest_invalid")
        if (
            self.expected_byte_count is not None
            and self.expected_byte_count != expected_byte_count
        ) or (
            self.expected_sha256 is not None
            and self.expected_sha256 != expected_sha256
        ):
            raise _closed_error(reason, "bound_content_authority_changed")
        self.expected_byte_count = expected_byte_count
        self.expected_sha256 = expected_sha256

    def inherit_proved_content(
        self,
        source: "Win32BoundFile",
        *,
        reason: str,
    ) -> None:
        if (
            source.expected_byte_count is None
            or source.expected_sha256 is None
        ):
            return
        self.bind_proved_content(
            expected_byte_count=source.expected_byte_count,
            expected_sha256=source.expected_sha256,
            reason=reason,
        )

    @property
    def raw_handle(self) -> int:
        if self._handle is None:
            raise _closed_error(
                FINAL_VERIFICATION_FAILED,
                "closed_bound_handle",
            )
        return self._handle

    @property
    def closed(self) -> bool:
        return self._handle is None

    def information(
        self,
        *,
        reason: str = FINAL_VERIFICATION_FAILED,
        operation: str = "bound_handle_information",
    ) -> Win32FileInformation:
        return self._information_for_expected_link_count(
            expected_link_count=self.expected_link_count,
            reason=reason,
            operation=operation,
        )

    def _information_for_expected_link_count(
        self,
        *,
        expected_link_count: int | None,
        reason: str,
        operation: str,
    ) -> Win32FileInformation:
        information = _query_information(self.raw_handle)
        _validate_regular_information(
            information,
            reason=reason,
            operation=operation,
            expected_link_count=expected_link_count,
            expected_volume_serial=self.identity.volume_serial,
        )
        if information.identity != self.identity:
            raise _closed_error(reason, operation)
        return information

    def iter_chunks(
        self,
        *,
        max_bytes: int,
        reason: str = FINAL_VERIFICATION_FAILED,
        chunk_size: int = 1024 * 1024,
    ) -> Iterator[bytes]:
        """Stream the exact retained bytes and revalidate at EOF."""

        yield from self._iter_chunks_for_expected_link_count(
            max_bytes=max_bytes,
            expected_link_count=self.expected_link_count,
            reason=reason,
            chunk_size=chunk_size,
        )

    def _iter_chunks_for_expected_link_count(
        self,
        *,
        max_bytes: int,
        expected_link_count: int | None,
        reason: str,
        chunk_size: int = 1024 * 1024,
    ) -> Iterator[bytes]:
        """Read only this handle under one explicit link-count authority."""

        if chunk_size <= 0 or chunk_size > 16 * 1024 * 1024:
            raise ValueError("private_metadata_chunk_size_invalid")
        information = self._information_for_expected_link_count(
            expected_link_count=expected_link_count,
            reason=reason,
            operation="bound_read_precheck",
        )
        if information.byte_count > max_bytes:
            raise _closed_error(reason, "bound_read_size_limit")
        api = _api()
        new_position = ctypes.c_longlong()
        if not api.set_file_pointer(
            self.raw_handle,
            0,
            ctypes.byref(new_position),
            0,
        ):
            raise _last_error(reason, "bound_read_seek")
        remaining = information.byte_count
        while remaining:
            requested = min(remaining, chunk_size)
            buffer = ctypes.create_string_buffer(requested)
            read_count = api._wintypes.DWORD()
            if not api.read_file(
                self.raw_handle,
                buffer,
                requested,
                ctypes.byref(read_count),
                None,
            ):
                raise _last_error(reason, "bound_read")
            progressed = int(read_count.value)
            if progressed <= 0 or progressed > requested:
                raise _closed_error(reason, "bound_read_zero_progress")
            yield buffer.raw[:progressed]
            remaining -= progressed
        after = self._information_for_expected_link_count(
            expected_link_count=expected_link_count,
            reason=reason,
            operation="bound_read_postcheck",
        )
        if after.byte_count != information.byte_count:
            raise _closed_error(reason, "bound_read_size_changed")

    def read_all(
        self,
        *,
        max_bytes: int,
        reason: str = FINAL_VERIFICATION_FAILED,
    ) -> bytes:
        return b"".join(
            self.iter_chunks(
                max_bytes=max_bytes,
                reason=reason,
            )
        )

    def sha256(
        self,
        *,
        max_bytes: int,
        reason: str = FINAL_VERIFICATION_FAILED,
    ) -> str:
        digest = hashlib.sha256()
        for chunk in self.iter_chunks(
            max_bytes=max_bytes,
            reason=reason,
        ):
            digest.update(chunk)
        return "sha256:" + digest.hexdigest()

    def _sha256_for_expected_link_count(
        self,
        *,
        max_bytes: int,
        expected_link_count: int | None,
        reason: str,
    ) -> str:
        digest = hashlib.sha256()
        for chunk in self._iter_chunks_for_expected_link_count(
            max_bytes=max_bytes,
            expected_link_count=expected_link_count,
            reason=reason,
        ):
            digest.update(chunk)
        return "sha256:" + digest.hexdigest()

    def write_chunks(
        self,
        chunks: Iterable[bytes],
        *,
        expected_byte_count: int,
        expected_sha256: str,
        reason: str = OWNED_TEMP_MATERIALIZATION_FAILED,
    ) -> tuple[int, str]:
        if self.profile is not FileHandleProfile.MUTATION_SOURCE:
            raise _closed_error(reason, "bound_write_wrong_profile")
        if expected_byte_count < 0:
            raise ValueError("private_metadata_expected_byte_count_invalid")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", expected_sha256):
            raise ValueError("private_metadata_expected_sha256_invalid")
        api = _api()
        new_position = ctypes.c_longlong()
        if not api.set_file_pointer(
            self.raw_handle,
            0,
            ctypes.byref(new_position),
            0,
        ):
            raise _last_error(reason, "bound_write_seek")
        digest = hashlib.sha256()
        total = 0
        for supplied in chunks:
            if not isinstance(supplied, (bytes, bytearray, memoryview)):
                raise _closed_error(reason, "bound_write_chunk_type")
            view = memoryview(supplied).cast("B")
            chunk_offset = 0
            while chunk_offset < len(view):
                chunk = bytes(
                    view[chunk_offset : chunk_offset + 1024 * 1024]
                )
                if total + len(chunk) > expected_byte_count:
                    raise _closed_error(
                        reason,
                        "bound_write_expected_size_exceeded",
                    )
                buffer = ctypes.create_string_buffer(chunk, len(chunk))
                written = api._wintypes.DWORD()
                if not api.write_file(
                    self.raw_handle,
                    buffer,
                    len(chunk),
                    ctypes.byref(written),
                    None,
                ):
                    raise _last_error(reason, "bound_write")
                progressed = int(written.value)
                if progressed <= 0 or progressed > len(chunk):
                    raise _closed_error(
                        reason,
                        "bound_write_zero_progress",
                    )
                digest.update(chunk[:progressed])
                chunk_offset += progressed
                total += progressed
        actual_sha256 = "sha256:" + digest.hexdigest()
        if total != expected_byte_count:
            raise _closed_error(reason, "bound_write_expected_size_mismatch")
        if actual_sha256 != expected_sha256:
            raise _closed_error(reason, "bound_write_expected_digest_mismatch")
        information = self.information(
            reason=reason,
            operation="bound_write_postcheck",
        )
        if information.byte_count != expected_byte_count:
            raise _closed_error(reason, "bound_write_size_mismatch")
        return total, actual_sha256

    def write_all(
        self,
        data: bytes,
        *,
        reason: str = OWNED_TEMP_MATERIALIZATION_FAILED,
    ) -> None:
        self.write_chunks(
            (data,),
            expected_byte_count=len(data),
            expected_sha256=(
                "sha256:" + hashlib.sha256(data).hexdigest()
            ),
            reason=reason,
        )

    def flush(
        self,
        *,
        reason: str = OWNED_TEMP_MATERIALIZATION_FAILED,
    ) -> None:
        if self.profile is not FileHandleProfile.MUTATION_SOURCE:
            raise _closed_error(reason, "flush_wrong_profile")
        if not _api().flush_file_buffers(self.raw_handle):
            raise _last_error(reason, "flush_file_buffers")

    def close(
        self,
        *,
        reason: str = FINAL_VERIFICATION_FAILED,
        operation: str = "bound_handle_close",
    ) -> None:
        if self._handle is None:
            return
        handle = self._handle
        _close_raw_handle(
            handle,
            reason=reason,
            operation=operation,
        )
        self._handle = None

    def __enter__(self) -> "Win32BoundFile":
        return self

    def __exit__(self, *exc_info: object) -> bool:
        self.close()
        return False

    def __del__(self) -> None:
        if self._handle is not None and _WINDOWS_AVAILABLE:
            try:
                _api().close_handle(self._handle)
            except BaseException:
                pass
            self._handle = None


class PrivateMetadataMutationGuard:
    """Retain exact non-reparse directory identities for one approval."""

    def __init__(self, archive_root: Path | str) -> None:
        self._initialize(
            archive_root,
            require_complete_approval_profile=False,
        )

    @classmethod
    def _for_low_level_ntfs_probe(
        cls,
        archive_root: Path | str,
    ) -> "PrivateMetadataMutationGuard":
        """Construct a guard without applying the full support decision."""

        instance = cls.__new__(cls)
        instance._initialize(
            archive_root,
            require_complete_approval_profile=False,
        )
        return instance

    def _initialize(
        self,
        archive_root: Path | str,
        *,
        require_complete_approval_profile: bool,
    ) -> None:
        self._handles: dict[str, int] = {}
        self._paths: dict[str, Path] = {}
        self._identities: dict[str, Win32FileIdentity] = {}
        self._order: list[str] = []
        self._volume_serial: int | None = None
        self._active_lock_kinds: set[CoordinationLockKind] = set()
        self._closed = True
        _require_windows("mutation_guard_init")
        self.archive_root = _absolute_lexical_path(archive_root)
        support = (
            approval_support_status(self.archive_root)
            if require_complete_approval_profile
            else _approval_environment_status(self.archive_root)
        )
        if not support.supported:
            raise _closed_error(
                support.reason or APPROVAL_PLATFORM_NOT_SUPPORTED,
                "mutation_guard_platform",
            )
        self._closed = False
        self.hold_directory(self.archive_root)

    @property
    def volume_serial(self) -> int:
        if self._volume_serial is None:
            raise _closed_error(
                MUTATION_GUARD_IDENTITY_CHANGED,
                "mutation_guard_volume_missing",
            )
        return self._volume_serial

    @property
    def held_paths(self) -> tuple[Path, ...]:
        return tuple(self._paths[key] for key in self._order)

    def _require_open(self) -> None:
        if self._closed:
            raise _closed_error(
                MUTATION_GUARD_IDENTITY_CHANGED,
                "mutation_guard_closed",
            )

    def contains(self, path: Path | str) -> bool:
        candidate = _absolute_lexical_path(path)
        return _contains_path(self.archive_root, candidate)

    def is_held(self, path: Path | str) -> bool:
        return _path_key(path) in self._handles

    def require_parent_held(self, path: Path | str) -> Path:
        candidate = _absolute_lexical_path(path)
        if not self.contains(candidate):
            raise _closed_error(
                MUTATION_GUARD_IDENTITY_CHANGED,
                "mutation_guard_path_escape",
            )
        if not self.is_held(candidate.parent):
            raise _closed_error(
                MUTATION_GUARD_IDENTITY_CHANGED,
                "mutation_guard_parent_not_held",
            )
        return candidate

    def hold_directory(self, path: Path | str) -> Win32FileIdentity:
        self._require_open()
        candidate = _absolute_lexical_path(path)
        if not self.contains(candidate):
            raise _closed_error(
                MUTATION_GUARD_IDENTITY_CHANGED,
                "mutation_guard_path_escape",
            )
        key = _path_key(candidate)
        if key in self._handles:
            self.validate_directory(candidate)
            return self._identities[key]
        if candidate != self.archive_root and not self.is_held(
            candidate.parent
        ):
            raise _closed_error(
                MUTATION_GUARD_IDENTITY_CHANGED,
                "mutation_guard_parent_not_held",
            )

        handle, information = _open_directory_raw(
            candidate,
            reason=MUTATION_GUARD_IDENTITY_CHANGED,
            operation="mutation_guard_hold",
            expected_volume_serial=self._volume_serial,
        )
        try:
            if self._volume_serial is None:
                self._volume_serial = information.identity.volume_serial
            verification_handle, verification = _open_directory_raw(
                candidate,
                reason=MUTATION_GUARD_IDENTITY_CHANGED,
                operation="mutation_guard_hold_verify",
                expected_volume_serial=self._volume_serial,
            )
            try:
                if verification.identity != information.identity:
                    raise _closed_error(
                        MUTATION_GUARD_IDENTITY_CHANGED,
                        "mutation_guard_hold_identity_mismatch",
                    )
            finally:
                _close_raw_handle_with_terminal_fallback(
                    verification_handle,
                    reason=MUTATION_GUARD_IDENTITY_CHANGED,
                    operation="mutation_guard_hold_verify_close",
                )
        except BaseException:
            try:
                _close_raw_handle_with_terminal_fallback(
                    handle,
                    reason=MUTATION_GUARD_IDENTITY_CHANGED,
                    operation="mutation_guard_hold_refusal_close",
                )
            except Win32SafetyError:
                pass
            raise

        self._handles[key] = handle
        self._paths[key] = candidate
        self._identities[key] = information.identity
        self._order.append(key)
        if candidate != self.archive_root:
            self.validate_directory(candidate.parent)
        return information.identity

    def hold_chain(self, directory: Path | str) -> tuple[Path, ...]:
        self._require_open()
        target = _absolute_lexical_path(directory)
        if not self.contains(target):
            raise _closed_error(
                MUTATION_GUARD_IDENTITY_CHANGED,
                "mutation_guard_chain_escape",
            )
        relative = target.relative_to(self.archive_root)
        current = self.archive_root
        for part in relative.parts:
            current = current / part
            self.hold_directory(current)
        self.validate_all()
        return self.held_paths

    def validate_directory(
        self,
        path: Path | str,
    ) -> Win32FileIdentity:
        self._require_open()
        candidate = _absolute_lexical_path(path)
        key = _path_key(candidate)
        handle = self._handles.get(key)
        expected = self._identities.get(key)
        if handle is None or expected is None:
            raise _closed_error(
                MUTATION_GUARD_IDENTITY_CHANGED,
                "mutation_guard_directory_not_held",
            )
        held = _query_information(handle)
        _validate_directory_information(
            held,
            reason=MUTATION_GUARD_IDENTITY_CHANGED,
            operation="mutation_guard_held_validate",
            expected_volume_serial=self.volume_serial,
        )
        verification_handle, verification = _open_directory_raw(
            candidate,
            reason=MUTATION_GUARD_IDENTITY_CHANGED,
            operation="mutation_guard_path_reopen",
            expected_volume_serial=self.volume_serial,
        )
        try:
            if held.identity != expected or verification.identity != expected:
                raise _closed_error(
                    MUTATION_GUARD_IDENTITY_CHANGED,
                    "mutation_guard_identity_mismatch",
                )
        finally:
            _close_raw_handle_with_terminal_fallback(
                verification_handle,
                reason=MUTATION_GUARD_IDENTITY_CHANGED,
                operation="mutation_guard_path_reopen_close",
            )
        return expected

    def validate_all(self) -> None:
        self._require_open()
        for key in tuple(self._order):
            self.validate_directory(self._paths[key])

    def _register_lock(self, kind: CoordinationLockKind) -> None:
        if kind in self._active_lock_kinds:
            raise _closed_error(
                LOCK_IDENTITY_CHANGED,
                "coordination_lock_registration_duplicate",
            )
        self._active_lock_kinds.add(kind)

    def _unregister_lock(self, kind: CoordinationLockKind) -> None:
        if kind not in self._active_lock_kinds:
            raise _closed_error(
                LOCK_IDENTITY_CHANGED,
                "coordination_lock_registration_missing",
            )
        self._active_lock_kinds.remove(kind)

    def require_lock_pair(self) -> None:
        if self._active_lock_kinds != {
            CoordinationLockKind.OBJECT_MANIFEST,
            CoordinationLockKind.PRIVATE_METADATA,
        }:
            raise _closed_error(
                LOCK_IDENTITY_CHANGED,
                "private_metadata_lock_pair_required",
            )

    def close(self) -> None:
        if self._closed:
            return
        if self._active_lock_kinds:
            raise _closed_error(
                LOCK_IDENTITY_CHANGED,
                "mutation_guard_close_with_live_lock",
            )
        for key in reversed(tuple(self._order)):
            handle = self._handles.get(key)
            if handle is None:
                continue
            try:
                _close_raw_handle(
                    handle,
                    reason=MUTATION_GUARD_IDENTITY_CHANGED,
                    operation="mutation_guard_close",
                )
            except Win32SafetyError:
                # CloseHandle failure does not prove that the handle closed.
                # Retain the exact map entry and keep the guard open so the
                # caller can retry without losing authority over that handle.
                raise
            del self._handles[key]
            self._paths.pop(key, None)
            self._identities.pop(key, None)
            self._order.remove(key)
        self._closed = True

    def terminal_release_after_failure(self) -> None:
        """Bounded no-path unwind after an ordinary guard close failed."""

        for key in reversed(tuple(self._order)):
            handle = self._handles.get(key)
            if handle is None:
                continue
            _release_raw_handle_until_closed(
                handle,
                reason=MUTATION_GUARD_IDENTITY_CHANGED,
                operation="mutation_guard_terminal_release",
            )
            del self._handles[key]
            self._paths.pop(key, None)
            self._identities.pop(key, None)
            self._order.remove(key)
        self._closed = True

    def __enter__(self) -> "PrivateMetadataMutationGuard":
        return self

    def __exit__(self, *exc_info: object) -> bool:
        self.close()
        return False

    def __del__(self) -> None:
        if not self._closed and _WINDOWS_AVAILABLE:
            for handle in self._handles.values():
                try:
                    _api().close_handle(handle)
                except BaseException:
                    pass
            self._closed = True


def _open_bound_file_absolute(
    guard: PrivateMetadataMutationGuard,
    path: Path,
    *,
    profile: FileHandleProfile,
    creation_disposition: int,
    expected_link_count: int | None,
    reason: str,
    operation: str,
) -> Win32BoundFile:
    candidate = guard.require_parent_held(path)
    guard.validate_all()
    handle = _open_raw(
        candidate,
        desired_access=profile.desired_access,
        share_mode=profile.share_mode,
        creation_disposition=creation_disposition,
        flags=_FILE_FLAG_OPEN_REPARSE_POINT | _FILE_ATTRIBUTE_NORMAL,
        reason=reason,
        operation=operation,
    )
    try:
        information = _query_information(handle)
        _validate_regular_information(
            information,
            reason=reason,
            operation=operation,
            expected_link_count=expected_link_count,
            expected_volume_serial=guard.volume_serial,
        )
        guard.validate_all()
    except BaseException:
        try:
            _close_raw_handle_with_terminal_fallback(
                handle,
                reason=reason,
                operation=f"{operation}_close_after_refusal",
            )
        except Win32SafetyError:
            pass
        raise
    return Win32BoundFile(
        path=candidate,
        handle=handle,
        profile=profile,
        information=information,
        expected_link_count=expected_link_count,
    )


def open_bound_file(
    guard: PrivateMetadataMutationGuard,
    relative_path: str,
    *,
    profile: FileHandleProfile = FileHandleProfile.AUTHORITY_READ,
    expected_link_count: int | None = 1,
    reason: str = AUTHORITY_PATH_UNSAFE,
) -> Win32BoundFile:
    """Open one existing archive-relative regular file through the guard."""

    path = _archive_path(guard.archive_root, relative_path)
    return _open_bound_file_absolute(
        guard,
        path,
        profile=profile,
        creation_disposition=_OPEN_EXISTING,
        expected_link_count=expected_link_count,
        reason=reason,
        operation="open_bound_file",
    )


def _reopen_and_compare(
    guard: PrivateMetadataMutationGuard,
    bound: Win32BoundFile,
    *,
    profile: FileHandleProfile,
    expected_link_count: int | None,
    reason: str,
    operation: str,
) -> Win32BoundFile:
    current = bound.information(
        reason=reason,
        operation=f"{operation}_held",
    )
    verification = _open_bound_file_absolute(
        guard,
        bound.path,
        profile=profile,
        creation_disposition=_OPEN_EXISTING,
        expected_link_count=expected_link_count,
        reason=reason,
        operation=f"{operation}_reopen",
    )
    try:
        observed = verification.information(
            reason=reason,
            operation=f"{operation}_reopen_information",
        )
        if current.identity != observed.identity:
            raise _closed_error(reason, f"{operation}_identity_mismatch")
        verification.inherit_proved_content(
            bound,
            reason=reason,
        )
    except BaseException:
        try:
            verification.close(
                reason=reason,
                operation=f"{operation}_reopen_refusal_close",
            )
        except Win32SafetyError:
            release_terminal_bound_authority(
                verification,
                reason=reason,
                operation=f"{operation}_reopen_refusal_terminal",
            )
        raise
    return verification


def validate_bound_path(
    guard: PrivateMetadataMutationGuard,
    bound: Win32BoundFile,
    *,
    expected_link_count: int | None = None,
    reason: str = FINAL_VERIFICATION_FAILED,
) -> Win32FileInformation:
    """Prove that ``bound.path`` still names the retained handle identity."""

    expected = (
        bound.expected_link_count
        if expected_link_count is None
        else expected_link_count
    )
    verification = _reopen_and_compare(
        guard,
        bound,
        profile=FileHandleProfile.TRANSITIONAL_READ,
        expected_link_count=expected,
        reason=reason,
        operation="validate_bound_path",
    )
    try:
        return bound.information(
            reason=reason,
            operation="validate_bound_path_final",
        )
    finally:
        try:
            verification.close(
                reason=reason,
                operation="validate_bound_path_verifier_close",
            )
        except Win32SafetyError:
            release_terminal_bound_authority(
                verification,
                reason=reason,
                operation="validate_bound_path_verifier_terminal",
            )
            raise


def _prove_exact_bound_name(
    guard: PrivateMetadataMutationGuard,
    bound: Win32BoundFile,
    *,
    reason: str,
    operation_prefix: str,
) -> None:
    """Prove one exact name->identity edge without full guard validation."""

    candidate = guard.require_parent_held(bound.path)
    verification_handle = _open_raw(
        candidate,
        desired_access=FileHandleProfile.TRANSITIONAL_READ.desired_access,
        share_mode=FileHandleProfile.TRANSITIONAL_READ.share_mode,
        creation_disposition=_OPEN_EXISTING,
        flags=_FILE_FLAG_OPEN_REPARSE_POINT | _FILE_ATTRIBUTE_NORMAL,
        reason=reason,
        operation=f"{operation_prefix}_open",
    )
    try:
        observed = _query_information(verification_handle)
        _validate_regular_information(
            observed,
            reason=reason,
            operation=f"{operation_prefix}_information",
            expected_link_count=1,
            expected_volume_serial=bound.identity.volume_serial,
        )
        if observed.identity != bound.identity:
            raise _closed_error(
                reason,
                f"{operation_prefix}_identity_changed",
            )
    finally:
        _release_raw_handle_until_closed(
            verification_handle,
            reason=reason,
            operation=f"{operation_prefix}_close",
        )


def _prove_exact_bound_name_after_cancellation(
    guard: PrivateMetadataMutationGuard,
    bound: Win32BoundFile,
    *,
    reason: str,
) -> None:
    """Compatibility wrapper for the compensation post-proof."""

    _prove_exact_bound_name(
        guard,
        bound,
        reason=reason,
        operation_prefix="residue_disposition_restore_name",
    )


def _prove_failed_disposition_same_handle_no_change(
    bound: Win32BoundFile,
    *,
    reason: str,
) -> None:
    """Prove the exact retained handle is still the planned link-one file."""

    if (
        bound.expected_link_count != 1
        or bound.expected_byte_count is None
        or bound.expected_sha256 is None
    ):
        raise _closed_error(
            reason,
            "residue_disposition_failed_no_change_content_unbound",
        )
    information = bound._information_for_expected_link_count(
        expected_link_count=1,
        reason=reason,
        operation="residue_disposition_failed_no_change_handle",
    )
    if information.byte_count != bound.expected_byte_count:
        raise _closed_error(
            reason,
            "residue_disposition_failed_no_change_size_changed",
        )
    if (
        bound._sha256_for_expected_link_count(
            max_bytes=bound.expected_byte_count,
            expected_link_count=1,
            reason=reason,
        )
        != bound.expected_sha256
    ):
        raise _closed_error(
            reason,
            "residue_disposition_failed_no_change_bytes_changed",
        )


def _prove_failed_disposition_name_guard_locks(
    guard: PrivateMetadataMutationGuard,
    bound: Win32BoundFile,
    *,
    locks: Any,
    reason: str,
) -> None:
    """Finish failed-TRUE no-change proof after link-one is established."""

    # The same-handle link-one/content proof must complete before this function
    # allocates a verifier or performs any path operation.  Once link-one is
    # exact, the retained handle is proved non-delete-pending, so failures in
    # this name/guard/lock phase use ordinary terminal release.
    _prove_exact_bound_name(
        guard,
        bound,
        reason=reason,
        operation_prefix="residue_disposition_failed_no_change_name",
    )
    guard.validate_all()
    locks.validate()


def path_is_absent(
    guard: PrivateMetadataMutationGuard,
    path: Path | str,
    *,
    reason: str,
    operation: str,
) -> bool:
    candidate = guard.require_parent_held(path)
    guard.validate_all()
    try:
        handle = _open_raw(
            candidate,
            desired_access=_FILE_READ_ATTRIBUTES,
            share_mode=(
                _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE
            ),
            creation_disposition=_OPEN_EXISTING,
            flags=(
                _FILE_FLAG_BACKUP_SEMANTICS
                | _FILE_FLAG_OPEN_REPARSE_POINT
            ),
            reason=reason,
            operation=operation,
        )
    except Win32SafetyError as exc:
        if exc.winerror in _ABSENT_WINERRORS:
            guard.validate_all()
            return True
        raise
    _close_raw_handle_with_terminal_fallback(
        handle,
        reason=reason,
        operation=f"{operation}_existing_close",
    )
    guard.validate_all()
    return False


def create_guarded_directory(
    guard: PrivateMetadataMutationGuard,
    path: Path | str,
) -> Win32FileIdentity:
    """Create one expected missing child and immediately extend the guard."""

    guard.require_lock_pair()
    candidate = guard.require_parent_held(path)
    if not path_is_absent(
        guard,
        candidate,
        reason=RECEIPT_DIRECTORY_BOOTSTRAP_FAILED,
        operation="receipt_directory_absence_precheck",
    ):
        raise _closed_error(
            RECEIPT_DIRECTORY_BOOTSTRAP_FAILED,
            "receipt_directory_not_absent",
        )
    guard.validate_all()
    if not _api().create_directory(_extended_path(candidate), None):
        raise _last_error(
            RECEIPT_DIRECTORY_BOOTSTRAP_FAILED,
            "create_directory",
        )
    try:
        identity = guard.hold_directory(candidate)
        # The new child must be empty at the immediate post-create boundary.
        with os.scandir(candidate) as scanner:
            if next(scanner, None) is not None:
                raise _closed_error(
                    RECEIPT_DIRECTORY_BOOTSTRAP_FAILED,
                    "created_directory_not_empty",
                )
        guard.validate_all()
    except BaseException as exc:
        if isinstance(exc, Win32SafetyError):
            raise
        raise _closed_error(
            RECEIPT_DIRECTORY_BOOTSTRAP_FAILED,
            "created_directory_enumeration",
        ) from exc
    return identity


def bootstrap_object_manifest_lock_directories(
    guard: PrivateMetadataMutationGuard,
) -> tuple[Win32FileIdentity, Win32FileIdentity]:
    """Bind or safely create the object-manifest lock's exact parent chain.

    This deliberately narrow bootstrap exists because the persistent object
    lock cannot be acquired until ``objects/manifests`` exists, while the
    general approval directory creator correctly requires both coordination
    locks.  The only children this helper can touch are ``objects`` followed by
    ``objects/manifests``.  Every existing or concurrently created child is
    opened with ``OPEN_REPARSE_POINT`` and retained by ``guard`` before the
    next child is considered.
    """

    identities: list[Win32FileIdentity] = []
    for relative_path in ("objects", "objects/manifests"):
        candidate = _archive_path(guard.archive_root, relative_path)
        guard.require_parent_held(candidate)
        guard.validate_all()
        try:
            identity = guard.hold_directory(candidate)
        except Win32SafetyError as exc:
            if exc.winerror not in _ABSENT_WINERRORS:
                raise
            guard.validate_all()
            if not _api().create_directory(_extended_path(candidate), None):
                winerror = ctypes.get_last_error()
                if winerror != _ERROR_ALREADY_EXISTS:
                    raise _closed_error(
                        OBJECT_MANIFEST_DIRECTORY_BOOTSTRAP_FAILED,
                        "object_manifest_directory_create",
                        winerror=winerror,
                    )
            # A successful CreateDirectoryW or an ERROR_ALREADY_EXISTS race is
            # accepted only after the exact child is reopened twice, proven to
            # be a same-volume non-reparse directory, and retained by guard.
            identity = guard.hold_directory(candidate)
            guard.validate_all()
        identities.append(identity)
    return identities[0], identities[1]


def _owned_temp_checkpoint(operation: str) -> MutationCheckpoint:
    if "flush" in operation:
        return MutationCheckpoint.OWNED_TEMP_FLUSH
    if "write" in operation:
        return MutationCheckpoint.OWNED_TEMP_WRITE
    if "create" in operation:
        return MutationCheckpoint.OWNED_TEMP_CREATE
    return MutationCheckpoint.OWNED_TEMP_VERIFY


def _create_owned_temp_authority(
    guard: PrivateMetadataMutationGuard,
    *,
    path: Path,
    role: str,
) -> Win32BoundFile:
    """CREATE_NEW while preserving the exact raw handle on later refusal."""

    try:
        candidate = guard.require_parent_held(path)
        guard.validate_all()
        handle = _open_raw(
            candidate,
            desired_access=FileHandleProfile.MUTATION_SOURCE.desired_access,
            share_mode=FileHandleProfile.MUTATION_SOURCE.share_mode,
            creation_disposition=_CREATE_NEW,
            flags=_FILE_FLAG_OPEN_REPARSE_POINT | _FILE_ATTRIBUTE_NORMAL,
            reason=OWNED_TEMP_MATERIALIZATION_FAILED,
            operation="owned_temp_create_new",
        )
    except Win32SafetyError as exc:
        raise Win32MutationFailure(
            (
                exc.reason
                if exc.reason in {
                    OWNED_TEMP_SUBSTITUTED,
                    UNEXPECTED_HARDLINK,
                }
                else OWNED_TEMP_MATERIALIZATION_FAILED
            ),
            operation=exc.operation,
            checkpoint=MutationCheckpoint.OWNED_TEMP_CREATE,
            effect=MutationEffect.NO_CHANGE_PROVED,
            winerror=exc.winerror,
        ) from exc

    created = Win32UnverifiedCreatedFile(
        path=candidate,
        handle=handle,
    )
    try:
        information = _query_information(created.raw_handle)
        _validate_regular_information(
            information,
            reason=OWNED_TEMP_MATERIALIZATION_FAILED,
            operation="owned_temp_create_new",
            expected_link_count=1,
            expected_volume_serial=guard.volume_serial,
        )
        guard.validate_all()
    except Win32SafetyError as exc:
        raise Win32MutationFailure(
            (
                exc.reason
                if exc.reason in {
                    OWNED_TEMP_SUBSTITUTED,
                    UNEXPECTED_HARDLINK,
                }
                else OWNED_TEMP_MATERIALIZATION_FAILED
            ),
            operation=exc.operation,
            checkpoint=MutationCheckpoint.OWNED_TEMP_CREATE,
            effect=MutationEffect.STATE_CHANGE_PROVED,
            authorities=(
                RetainedAuthorityTransfer(
                    role=role,
                    bound=created,
                    name_state="owned_present",
                ),
            ),
            winerror=exc.winerror,
        ) from exc
    return Win32BoundFile(
        path=candidate,
        handle=created.detach(),
        profile=FileHandleProfile.MUTATION_SOURCE,
        information=information,
        expected_link_count=1,
    )


def materialize_owned_temp(
    guard: PrivateMetadataMutationGuard,
    *,
    kind: OwnedTempKind,
    authority_key_hex: str,
    data: bytes | Iterable[bytes],
    expected_byte_count: int | None = None,
    expected_sha256: str | None = None,
) -> Win32BoundFile:
    """Exclusive-create, stream, flush, and verify one allow-listed temp.

    A bytes input derives its expected length and digest directly.  A streaming
    input must provide both values from the accepted plan/journal, allowing a
    256 MiB manifest to be copied and appended without a second in-memory
    representation.
    """

    guard.require_lock_pair()
    if isinstance(data, bytes):
        derived_count = len(data)
        derived_sha256 = "sha256:" + hashlib.sha256(data).hexdigest()
        if (
            expected_byte_count is not None
            and expected_byte_count != derived_count
        ):
            raise ValueError("private_metadata_expected_byte_count_mismatch")
        if (
            expected_sha256 is not None
            and expected_sha256 != derived_sha256
        ):
            raise ValueError("private_metadata_expected_sha256_mismatch")
        expected_byte_count = derived_count
        expected_sha256 = derived_sha256
        chunks: Iterable[bytes] = (data,)
    else:
        if expected_byte_count is None or expected_sha256 is None:
            raise ValueError(
                "private_metadata_stream_expectations_required"
            )
        chunks = data
    relative_path = owned_temp_relative_path(kind, authority_key_hex)
    path = _archive_path(guard.archive_root, relative_path)
    bound = _create_owned_temp_authority(
        guard,
        path=path,
        role=f"{kind.value}_temp",
    )
    try:
        if bound.initial_information.byte_count != 0:
            raise _closed_error(
                OWNED_TEMP_MATERIALIZATION_FAILED,
                "owned_temp_not_initially_empty",
            )
        bound.write_chunks(
            chunks,
            expected_byte_count=expected_byte_count,
            expected_sha256=expected_sha256,
        )
        bound.flush()
        observed = validate_bound_path(
            guard,
            bound,
            expected_link_count=1,
            reason=OWNED_TEMP_SUBSTITUTED,
        )
        if observed.byte_count != expected_byte_count:
            raise _closed_error(
                OWNED_TEMP_MATERIALIZATION_FAILED,
                "owned_temp_final_size_mismatch",
            )
        if bound.sha256(
            max_bytes=expected_byte_count,
            reason=OWNED_TEMP_MATERIALIZATION_FAILED,
        ) != expected_sha256:
            raise _closed_error(
                OWNED_TEMP_MATERIALIZATION_FAILED,
                "owned_temp_final_digest_mismatch",
            )
        bound.bind_proved_content(
            expected_byte_count=expected_byte_count,
            expected_sha256=expected_sha256,
            reason=OWNED_TEMP_MATERIALIZATION_FAILED,
        )
    except Win32MutationFailure:
        raise
    except Win32SafetyError as exc:
        raise Win32MutationFailure(
            exc.reason,
            operation=exc.operation,
            checkpoint=_owned_temp_checkpoint(exc.operation),
            effect=MutationEffect.STATE_CHANGE_PROVED,
            authorities=(
                RetainedAuthorityTransfer(
                    role=f"{kind.value}_temp",
                    bound=bound,
                    name_state="owned_present",
                ),
            ),
            winerror=exc.winerror,
        ) from exc
    return bound


def _lock_create_or_open(
    guard: PrivateMetadataMutationGuard,
    kind: CoordinationLockKind,
) -> tuple[Win32BoundFile, bool]:
    path = _archive_path(guard.archive_root, kind.value)
    try:
        return (
            _open_bound_file_absolute(
                guard,
                path,
                profile=FileHandleProfile.COORDINATION_LOCK,
                creation_disposition=_OPEN_EXISTING,
                expected_link_count=1,
                reason=LOCK_PATH_UNSAFE,
                operation="coordination_lock_open_existing",
            ),
            False,
        )
    except Win32SafetyError as exc:
        if exc.winerror not in _ABSENT_WINERRORS:
            raise
    try:
        return (
            _open_bound_file_absolute(
                guard,
                path,
                profile=FileHandleProfile.COORDINATION_LOCK,
                creation_disposition=_CREATE_NEW,
                expected_link_count=1,
                reason=LOCK_PATH_UNSAFE,
                operation="coordination_lock_create_new",
            ),
            True,
        )
    except Win32SafetyError as exc:
        if exc.winerror not in {
            _ERROR_FILE_EXISTS,
            _ERROR_ALREADY_EXISTS,
        }:
            raise
    # A cooperating winner may have created the exact persistent lock between
    # our absence observation and CREATE_NEW.  Open once and bind that identity.
    return (
        _open_bound_file_absolute(
            guard,
            path,
            profile=FileHandleProfile.COORDINATION_LOCK,
            creation_disposition=_OPEN_EXISTING,
            expected_link_count=1,
            reason=LOCK_PATH_UNSAFE,
            operation="coordination_lock_open_race_winner",
        ),
        False,
    )


class PersistentCoordinationLock:
    """One zero-byte, identity-bound persistent ``LockFileEx`` lock."""

    def __init__(
        self,
        guard: PrivateMetadataMutationGuard,
        kind: CoordinationLockKind,
        *,
        fail_immediately: bool = False,
    ) -> None:
        self.guard = guard
        self.kind = kind
        self.fail_immediately = fail_immediately
        self.bound: Win32BoundFile | None = None
        self.created = False
        self._overlapped: Any = None
        self._locked = False

    @property
    def identity(self) -> Win32FileIdentity:
        if self.bound is None:
            raise _closed_error(
                LOCK_IDENTITY_CHANGED,
                "coordination_lock_not_open",
            )
        return self.bound.identity

    def acquire(self) -> "PersistentCoordinationLock":
        if self.bound is not None:
            raise _closed_error(
                LOCK_IDENTITY_CHANGED,
                "coordination_lock_double_acquire",
            )
        self.guard.validate_all()
        bound, created = _lock_create_or_open(self.guard, self.kind)
        try:
            information = bound.information(
                reason=LOCK_PATH_UNSAFE,
                operation="coordination_lock_initial_information",
            )
            if information.byte_count != 0:
                raise _closed_error(
                    LOCK_PATH_UNSAFE,
                    "coordination_lock_nonzero",
                )
            validate_bound_path(
                self.guard,
                bound,
                expected_link_count=1,
                reason=LOCK_IDENTITY_CHANGED,
            )
            overlapped = _api().Overlapped()
            flags = _LOCKFILE_EXCLUSIVE_LOCK
            if self.fail_immediately:
                flags |= _LOCKFILE_FAIL_IMMEDIATELY
            if not _api().lock_file(
                bound.raw_handle,
                flags,
                0,
                1,
                0,
                ctypes.byref(overlapped),
            ):
                raise _last_error(
                    LOCK_IDENTITY_CHANGED,
                    "lock_file_ex",
                )
            self.bound = bound
            self.created = created
            self._overlapped = overlapped
            self._locked = True
            self.validate()
            self.guard._register_lock(self.kind)
        except BaseException:
            if self._locked and self._overlapped is not None:
                _api().unlock_file(
                    bound.raw_handle,
                    0,
                    1,
                    0,
                    ctypes.byref(self._overlapped),
                )
            try:
                bound.close(
                    reason=LOCK_IDENTITY_CHANGED,
                    operation="coordination_lock_failed_acquire_close",
                )
            except Win32SafetyError:
                release_terminal_bound_authority(
                    bound,
                    reason=LOCK_IDENTITY_CHANGED,
                    operation="coordination_lock_failed_acquire_terminal",
                )
            self.bound = None
            self._overlapped = None
            self._locked = False
            raise
        return self

    def validate(self) -> Win32FileIdentity:
        if self.bound is None or not self._locked:
            raise _closed_error(
                LOCK_IDENTITY_CHANGED,
                "coordination_lock_not_acquired",
            )
        self.guard.validate_all()
        information = validate_bound_path(
            self.guard,
            self.bound,
            expected_link_count=1,
            reason=LOCK_IDENTITY_CHANGED,
        )
        if information.byte_count != 0:
            raise _closed_error(
                LOCK_IDENTITY_CHANGED,
                "coordination_lock_changed_bytes",
            )
        self.guard.validate_all()
        return information.identity

    def release(self) -> None:
        if self.bound is None:
            return
        bound = self.bound
        if self._locked:
            self.validate()
            if not _api().unlock_file(
                bound.raw_handle,
                0,
                1,
                0,
                ctypes.byref(self._overlapped),
            ):
                raise _last_error(
                    LOCK_IDENTITY_CHANGED,
                    "unlock_file_ex",
                )
            self._locked = False
        else:
            self.guard.validate_all()
        validate_bound_path(
            self.guard,
            bound,
            expected_link_count=1,
            reason=LOCK_IDENTITY_CHANGED,
        )
        bound.close(
            reason=LOCK_IDENTITY_CHANGED,
            operation="coordination_lock_close",
        )
        self.guard._unregister_lock(self.kind)
        self.bound = None
        self._overlapped = None

    def terminal_release_after_failure(self) -> None:
        """Close the exact lock handle; raw close releases its byte lock."""

        bound = self.bound
        if bound is not None:
            release_terminal_bound_authority(
                bound,
                reason=LOCK_IDENTITY_CHANGED,
                operation="coordination_lock_terminal_release",
            )
        # Terminal unwind has already released the exact raw lock handle.
        # Bookkeeping must not turn that completed release into another
        # fallible step.
        self.guard._active_lock_kinds.discard(self.kind)
        self.bound = None
        self._overlapped = None
        self._locked = False

    def __enter__(self) -> "PersistentCoordinationLock":
        return self.acquire()

    def __exit__(self, *exc_info: object) -> bool:
        self.release()
        return False


class PrivateMetadataLockPair:
    """Acquire object-manifest then private-manifest locks, release reverse."""

    def __init__(
        self,
        guard: PrivateMetadataMutationGuard,
        *,
        fail_immediately: bool = False,
    ) -> None:
        self.guard = guard
        self.object_manifest = PersistentCoordinationLock(
            guard,
            CoordinationLockKind.OBJECT_MANIFEST,
            fail_immediately=fail_immediately,
        )
        self.private_metadata = PersistentCoordinationLock(
            guard,
            CoordinationLockKind.PRIVATE_METADATA,
            fail_immediately=fail_immediately,
        )
        self._acquired = False

    def acquire(self) -> "PrivateMetadataLockPair":
        if self._acquired:
            raise _closed_error(
                LOCK_IDENTITY_CHANGED,
                "coordination_lock_pair_double_acquire",
            )
        self.object_manifest.acquire()
        try:
            self.object_manifest.validate()
            self.private_metadata.acquire()
            self.object_manifest.validate()
            self.private_metadata.validate()
        except BaseException:
            # A failure after the inner/private lock was acquired must unwind
            # both locks in reverse order even though the pair-level
            # ``_acquired`` bit has not yet been committed.  Pair.release()
            # intentionally does nothing in that state, so release the
            # individual authorities explicitly and terminalize any failed
            # unlock/close before touching the outer lock.
            for lock in (self.private_metadata, self.object_manifest):
                try:
                    lock.release()
                except Win32SafetyError:
                    lock.terminal_release_after_failure()
            self._acquired = False
            raise
        self._acquired = True
        return self

    def validate(self) -> tuple[Win32FileIdentity, Win32FileIdentity]:
        if not self._acquired:
            raise _closed_error(
                LOCK_IDENTITY_CHANGED,
                "coordination_lock_pair_not_acquired",
            )
        return (
            self.object_manifest.validate(),
            self.private_metadata.validate(),
        )

    def release(self) -> None:
        if not self._acquired:
            return
        try:
            self.private_metadata.release()
        except Win32SafetyError as exc:
            # Do not release the outer/object lock after the inner lock's
            # identity, unlock, or close became unprovable.
            raise exc
        try:
            self.object_manifest.release()
        except Win32SafetyError as exc:
            raise exc
        self._acquired = False

    def terminal_release_after_failure(self) -> None:
        """Unwind inner then outer lock without further path validation."""

        self.private_metadata.terminal_release_after_failure()
        self.object_manifest.terminal_release_after_failure()
        self._acquired = False

    def __enter__(self) -> "PrivateMetadataLockPair":
        return self.acquire()

    def __exit__(self, *exc_info: object) -> bool:
        self.release()
        return False


def _set_disposition(
    bound: Win32BoundFile,
    *,
    reason: str,
    operation: str,
) -> None:
    if bound.profile not in {
        FileHandleProfile.MUTATION_SOURCE,
        FileHandleProfile.RESIDUE_DISPOSITION,
    }:
        raise _closed_error(reason, f"{operation}_wrong_profile")
    disposition = _api().FileDispositionInfo(1)
    if not _api().set_file_information(
        bound.raw_handle,
        _FILE_DISPOSITION_INFO_CLASS,
        ctypes.byref(disposition),
        ctypes.sizeof(disposition),
    ):
        raise _last_error(reason, operation)


def _clear_disposition(
    bound: Win32BoundFile,
    *,
    reason: str,
    operation: str,
) -> None:
    """Cancel delete-pending while the exact disposition handle is retained."""

    if bound.profile is not FileHandleProfile.RESIDUE_DISPOSITION:
        raise _closed_error(reason, f"{operation}_wrong_profile")
    disposition = _api().FileDispositionInfo(0)
    if not _api().set_file_information(
        bound.raw_handle,
        _FILE_DISPOSITION_INFO_CLASS,
        ctypes.byref(disposition),
        ctypes.sizeof(disposition),
    ):
        raise _last_error(reason, operation)


def _authority_role_for_path(
    guard: PrivateMetadataMutationGuard,
    path: Path,
) -> str:
    try:
        relative = path.relative_to(guard.archive_root).as_posix()
    except ValueError:
        return "unclassified"
    if relative == PRIVATE_JOURNAL_RELATIVE_PATH:
        return "fixed_journal"
    if relative == PRIVATE_MANIFEST_RELATIVE_PATH:
        return "private_manifest"
    if re.fullmatch(
        r"objects/manifests/"
        r"\.private-source-metadata-write\.[0-9a-f]{64}\.journal\.tmp",
        relative,
    ):
        return "journal_temp"
    if re.fullmatch(
        r"objects/manifests/"
        r"\.private-source-metadata-write\.[0-9a-f]{64}\.manifest\.tmp",
        relative,
    ):
        return "manifest_temp"
    if re.fullmatch(
        r"receipts/objects/private-source-metadata/"
        r"\.[0-9a-f]{64}\.receipt\.tmp",
        relative,
    ):
        return "receipt_temp"
    if re.fullmatch(
        r"receipts/objects/private-source-metadata/[0-9a-f]{64}\.json",
        relative,
    ):
        return "final_receipt"
    return "unclassified"


def handoff_to_residue_authority(
    guard: PrivateMetadataMutationGuard,
    current: Win32BoundFile,
    *,
    reason: str = FINAL_VERIFICATION_FAILED,
) -> Win32BoundFile:
    """Bridge narrow/transitional authority to DELETE/share-read authority."""

    transitional: Win32BoundFile | None = None
    residue: Win32BoundFile | None = None
    role = _authority_role_for_path(guard, current.path)
    try:
        guard.require_lock_pair()
        transitional = _reopen_and_compare(
            guard,
            current,
            profile=FileHandleProfile.TRANSITIONAL_READ,
            expected_link_count=current.expected_link_count,
            reason=reason,
            operation="residue_handoff_transitional",
        )
        try:
            current.close(
                reason=reason,
                operation="residue_handoff_current_close",
            )
        except Win32SafetyError as close_exc:
            raise Win32MutationFailure(
                close_exc.reason,
                operation=close_exc.operation,
                checkpoint=MutationCheckpoint.HANDOFF,
                effect=MutationEffect.NO_CHANGE_PROVED,
                authorities=(
                    RetainedAuthorityTransfer(
                        role=role,
                        bound=current,
                        name_state="owned_present",
                        terminal_release_first=True,
                    ),
                    RetainedAuthorityTransfer(
                        role=role,
                        bound=transitional,
                        name_state="owned_present",
                    ),
                ),
                winerror=close_exc.winerror,
                terminal_release_required=True,
            ) from close_exc
        residue = _reopen_and_compare(
            guard,
            transitional,
            profile=FileHandleProfile.RESIDUE_DISPOSITION,
            expected_link_count=transitional.expected_link_count,
            reason=reason,
            operation="residue_handoff_open",
        )
        try:
            transitional.close(
                reason=reason,
                operation="residue_handoff_transitional_close",
            )
        except Win32SafetyError as close_exc:
            raise Win32MutationFailure(
                close_exc.reason,
                operation=close_exc.operation,
                checkpoint=MutationCheckpoint.HANDOFF,
                effect=MutationEffect.NO_CHANGE_PROVED,
                authorities=(
                    RetainedAuthorityTransfer(
                        role=role,
                        bound=transitional,
                        name_state="owned_present",
                        terminal_release_first=True,
                    ),
                    RetainedAuthorityTransfer(
                        role=role,
                        bound=residue,
                        name_state="owned_present",
                    ),
                ),
                winerror=close_exc.winerror,
                terminal_release_required=True,
            ) from close_exc
    except Win32MutationFailure:
        raise
    except Win32SafetyError as exc:
        authorities: list[RetainedAuthorityTransfer] = []
        retained: list[Win32BoundFile] = []
        for candidate in (current, transitional, residue):
            if (
                candidate is not None
                and not candidate.closed
                and all(existing is not candidate for existing in retained)
            ):
                retained.append(candidate)
        for candidate in retained:
            authorities.append(
                RetainedAuthorityTransfer(
                    role=role,
                    bound=candidate,
                    name_state="owned_present",
                )
            )
        raise Win32MutationFailure(
            exc.reason,
            operation=exc.operation,
            checkpoint=MutationCheckpoint.HANDOFF,
            effect=MutationEffect.NO_CHANGE_PROVED,
            authorities=authorities,
            winerror=exc.winerror,
        ) from exc
    assert residue is not None
    return residue


def handoff_to_narrow_authority(
    guard: PrivateMetadataMutationGuard,
    transitional: Win32BoundFile,
    *,
    reason: str = FINAL_VERIFICATION_FAILED,
) -> Win32BoundFile:
    narrow: Win32BoundFile | None = None
    role = _authority_role_for_path(guard, transitional.path)
    try:
        guard.require_lock_pair()
        if transitional.profile is not FileHandleProfile.TRANSITIONAL_READ:
            raise _closed_error(reason, "narrow_handoff_wrong_profile")
        narrow = _reopen_and_compare(
            guard,
            transitional,
            profile=FileHandleProfile.NARROW_READ,
            expected_link_count=transitional.expected_link_count,
            reason=reason,
            operation="narrow_handoff_open",
        )
        try:
            transitional.close(
                reason=reason,
                operation="narrow_handoff_transitional_close",
            )
        except Win32SafetyError as close_exc:
            raise Win32MutationFailure(
                close_exc.reason,
                operation=close_exc.operation,
                checkpoint=MutationCheckpoint.HANDOFF,
                effect=MutationEffect.NO_CHANGE_PROVED,
                authorities=(
                    RetainedAuthorityTransfer(
                        role=role,
                        bound=transitional,
                        name_state="owned_present",
                        terminal_release_first=True,
                    ),
                    RetainedAuthorityTransfer(
                        role=role,
                        bound=narrow,
                        name_state="owned_present",
                    ),
                ),
                winerror=close_exc.winerror,
                terminal_release_required=True,
            ) from close_exc
    except Win32MutationFailure:
        raise
    except Win32SafetyError as exc:
        retained = [
            candidate
            for candidate in (transitional, narrow)
            if candidate is not None and not candidate.closed
        ]
        raise Win32MutationFailure(
            exc.reason,
            operation=exc.operation,
            checkpoint=MutationCheckpoint.HANDOFF,
            effect=MutationEffect.NO_CHANGE_PROVED,
            authorities=tuple(
                RetainedAuthorityTransfer(
                    role=role,
                    bound=candidate,
                    name_state="owned_present",
                )
                for candidate in retained
            ),
            winerror=exc.winerror,
        ) from exc
    assert narrow is not None
    return narrow


def handoff_same_identity_twin_to_residue(
    guard: PrivateMetadataMutationGuard,
    survivor: Win32BoundFile,
    residue_name: Win32BoundFile,
    *,
    expected_bytes: bytes,
    reason: str = FINAL_VERIFICATION_FAILED,
) -> tuple[Win32BoundFile, Win32BoundFile]:
    """Bridge two narrow link-count-two names to survivor+DELETE authority."""

    transitional: Win32BoundFile | None = None
    residue: Win32BoundFile | None = None
    survivor_role = _authority_role_for_path(guard, survivor.path)
    residue_role = _authority_role_for_path(guard, residue_name.path)
    try:
        guard.require_lock_pair()
        if (
            survivor.identity != residue_name.identity
            or survivor.expected_link_count != 2
            or residue_name.expected_link_count != 2
        ):
            raise _closed_error(
                UNEXPECTED_HARDLINK,
                "twin_handoff_identity_mismatch",
            )
        for bound in (survivor, residue_name):
            validate_bound_path(
                guard,
                bound,
                expected_link_count=2,
                reason=UNEXPECTED_HARDLINK,
            )
            if bound.read_all(
                max_bytes=len(expected_bytes),
                reason=reason,
            ) != expected_bytes:
                raise _closed_error(
                    UNEXPECTED_HARDLINK,
                    "twin_handoff_bytes_mismatch",
                )
        transitional = _reopen_and_compare(
            guard,
            survivor,
            profile=FileHandleProfile.TRANSITIONAL_READ,
            expected_link_count=2,
            reason=reason,
            operation="twin_survivor_transitional",
        )
        try:
            survivor.close(
                reason=reason,
                operation="twin_survivor_narrow_close",
            )
        except Win32SafetyError as close_exc:
            raise Win32MutationFailure(
                close_exc.reason,
                operation=close_exc.operation,
                checkpoint=MutationCheckpoint.HANDOFF,
                effect=MutationEffect.NO_CHANGE_PROVED,
                authorities=(
                    RetainedAuthorityTransfer(
                        role=survivor_role,
                        bound=survivor,
                        name_state="twin_published",
                        terminal_release_first=True,
                    ),
                    RetainedAuthorityTransfer(
                        role=survivor_role,
                        bound=transitional,
                        name_state="twin_published",
                    ),
                    RetainedAuthorityTransfer(
                        role=residue_role,
                        bound=residue_name,
                        name_state="twin_published",
                    ),
                ),
                winerror=close_exc.winerror,
                terminal_release_required=True,
            ) from close_exc
        residue_path = residue_name.path
        try:
            residue_name.close(
                reason=reason,
                operation="twin_residue_narrow_close",
            )
        except Win32SafetyError as close_exc:
            raise Win32MutationFailure(
                close_exc.reason,
                operation=close_exc.operation,
                checkpoint=MutationCheckpoint.HANDOFF,
                effect=MutationEffect.NO_CHANGE_PROVED,
                authorities=(
                    RetainedAuthorityTransfer(
                        role=residue_role,
                        bound=residue_name,
                        name_state="twin_published",
                        terminal_release_first=True,
                    ),
                    RetainedAuthorityTransfer(
                        role=survivor_role,
                        bound=transitional,
                        name_state="twin_published",
                    ),
                ),
                winerror=close_exc.winerror,
                terminal_release_required=True,
            ) from close_exc
        residue = _open_bound_file_absolute(
            guard,
            residue_path,
            profile=FileHandleProfile.RESIDUE_DISPOSITION,
            creation_disposition=_OPEN_EXISTING,
            expected_link_count=2,
            reason=reason,
            operation="twin_residue_disposition_open",
        )
        if residue.identity != transitional.identity:
            raise _closed_error(
                UNEXPECTED_HARDLINK,
                "twin_residue_disposition_identity_mismatch",
            )
        residue.inherit_proved_content(
            residue_name,
            reason=reason,
        )
        guard.validate_all()
    except Win32MutationFailure:
        raise
    except Win32SafetyError as exc:
        authorities: list[RetainedAuthorityTransfer] = []
        survivor_bounds = [
            candidate
            for candidate in (survivor, transitional)
            if candidate is not None and not candidate.closed
        ]
        residue_bounds = [
            candidate
            for candidate in (residue_name, residue)
            if candidate is not None and not candidate.closed
        ]
        for survivor_bound in survivor_bounds:
            authorities.append(
                RetainedAuthorityTransfer(
                    role=survivor_role,
                    bound=survivor_bound,
                    name_state="twin_published",
                )
            )
        for residue_bound in residue_bounds:
            authorities.append(
                RetainedAuthorityTransfer(
                    role=residue_role,
                    bound=residue_bound,
                    name_state="twin_published",
                )
            )
        raise Win32MutationFailure(
            exc.reason,
            operation=exc.operation,
            checkpoint=MutationCheckpoint.HANDOFF,
            effect=MutationEffect.NO_CHANGE_PROVED,
            authorities=authorities,
            winerror=exc.winerror,
        ) from exc
    assert transitional is not None and residue is not None
    return transitional, residue


def dispose_bound_residue(
    guard: PrivateMetadataMutationGuard,
    residue: Win32BoundFile,
    *,
    locks: Any,
) -> None:
    """Delete exactly the retained residue identity, never a path snapshot."""

    disposition_set = False
    closed = False
    role = _authority_role_for_path(guard, residue.path)
    path = residue.path
    try:
        guard.require_lock_pair()
        if residue.profile is not FileHandleProfile.RESIDUE_DISPOSITION:
            raise _closed_error(
                RESIDUE_DISPOSITION_FAILED,
                "residue_disposition_wrong_profile",
            )
        validate_bound_path(
            guard,
            residue,
            expected_link_count=residue.expected_link_count,
            reason=RESIDUE_DISPOSITION_FAILED,
        )
        guard.validate_all()
        locks.validate()
        try:
            _set_disposition(
                residue,
                reason=RESIDUE_DISPOSITION_FAILED,
                operation="file_disposition_info",
            )
        except Win32SafetyError as api_exc:
            try:
                _prove_failed_disposition_same_handle_no_change(
                    residue,
                    reason=RESIDUE_DISPOSITION_FAILED,
                )
            except Win32SafetyError as same_handle_exc:
                raise Win32MutationFailure(
                    api_exc.reason,
                    operation=api_exc.operation,
                    checkpoint=MutationCheckpoint.RESIDUE_API,
                    effect=MutationEffect.STATE_CHANGE_POSSIBLE,
                    authorities=(
                        RetainedAuthorityTransfer(
                            role=role,
                            bound=residue,
                            name_state="state_unknown",
                        ),
                    ),
                    winerror=api_exc.winerror,
                    terminal_release_required=True,
                ) from same_handle_exc
            try:
                _prove_failed_disposition_name_guard_locks(
                    guard,
                    residue,
                    locks=locks,
                    reason=RESIDUE_DISPOSITION_FAILED,
                )
            except Win32SafetyError as authority_exc:
                raise Win32MutationFailure(
                    api_exc.reason,
                    operation=api_exc.operation,
                    checkpoint=MutationCheckpoint.RESIDUE_API,
                    effect=MutationEffect.STATE_CHANGE_POSSIBLE,
                    authorities=(
                        RetainedAuthorityTransfer(
                            role=role,
                            bound=residue,
                            name_state="state_unknown",
                        ),
                    ),
                    winerror=api_exc.winerror,
                    terminal_release_required=True,
                ) from authority_exc
            raise Win32MutationFailure(
                api_exc.reason,
                operation=api_exc.operation,
                checkpoint=MutationCheckpoint.RESIDUE_API,
                effect=MutationEffect.NO_CHANGE_PROVED,
                authorities=(
                    RetainedAuthorityTransfer(
                        role=role,
                        bound=residue,
                        name_state="owned_present",
                    ),
                ),
                winerror=api_exc.winerror,
                terminal_release_required=True,
            ) from api_exc
        disposition_set = True
        residue.close(
            reason=RESIDUE_DISPOSITION_FAILED,
            operation="residue_disposition_source_close",
        )
        closed = True
        if not path_is_absent(
            guard,
            path,
            reason=FINAL_VERIFICATION_FAILED,
            operation="residue_disposition_absence",
        ):
            raise _closed_error(
                FINAL_VERIFICATION_FAILED,
                "residue_disposition_name_survived",
            )
        guard.validate_all()
        locks.validate()
    except Win32MutationFailure:
        raise
    except Win32SafetyError as exc:
        if disposition_set and not closed and not residue.closed:
            clear_succeeded = False
            compensation_complete = False
            try:
                if residue.expected_link_count != 1:
                    raise _closed_error(
                        RESIDUE_DISPOSITION_FAILED,
                        "residue_disposition_restore_link_count_not_one",
                    )
                if (
                    residue.expected_byte_count is None
                    or residue.expected_sha256 is None
                ):
                    raise _closed_error(
                        RESIDUE_DISPOSITION_FAILED,
                        "residue_disposition_restore_content_unbound",
                    )

                # No path, open, create, handle allocation, guard, or lock call
                # may intervene here.  NTFS reports link_count=0 on the exact
                # retained delete-pending handle.
                before_clear = (
                    residue._information_for_expected_link_count(
                        expected_link_count=0,
                        reason=RESIDUE_DISPOSITION_FAILED,
                        operation="residue_disposition_restore_precheck",
                    )
                )
                before_clear_sha256 = (
                    residue._sha256_for_expected_link_count(
                        max_bytes=before_clear.byte_count,
                        expected_link_count=0,
                        reason=RESIDUE_DISPOSITION_FAILED,
                    )
                )
                if (
                    before_clear.byte_count
                    != residue.expected_byte_count
                    or before_clear_sha256 != residue.expected_sha256
                ):
                    raise _closed_error(
                        RESIDUE_DISPOSITION_FAILED,
                        "residue_disposition_restore_precheck_bytes_changed",
                    )
                _clear_disposition(
                    residue,
                    reason=RESIDUE_DISPOSITION_FAILED,
                    operation="residue_disposition_restore",
                )
                clear_succeeded = True

                # Post-cancellation order is deliberate: same handle first,
                # exact name second, full guard third, both locks last.
                after_clear = (
                    residue._information_for_expected_link_count(
                        expected_link_count=1,
                        reason=RESIDUE_DISPOSITION_FAILED,
                        operation="residue_disposition_restore_postcheck",
                    )
                )
                if (
                    after_clear.identity != before_clear.identity
                    or after_clear.byte_count
                    != residue.expected_byte_count
                ):
                    raise _closed_error(
                        RESIDUE_DISPOSITION_FAILED,
                        "residue_disposition_restore_identity_changed",
                    )
                after_clear_sha256 = (
                    residue._sha256_for_expected_link_count(
                        max_bytes=residue.expected_byte_count,
                        expected_link_count=1,
                        reason=RESIDUE_DISPOSITION_FAILED,
                    )
                )
                if after_clear_sha256 != residue.expected_sha256:
                    raise _closed_error(
                        RESIDUE_DISPOSITION_FAILED,
                        "residue_disposition_restore_bytes_changed",
                    )
                _prove_exact_bound_name_after_cancellation(
                    guard,
                    residue,
                    reason=RESIDUE_DISPOSITION_FAILED,
                )
                guard.validate_all()
                locks.validate()
                compensation_complete = True
            except Win32SafetyError as restore_exc:
                raise Win32MutationFailure(
                    exc.reason,
                    operation=exc.operation,
                    checkpoint=MutationCheckpoint.RESIDUE_API,
                    effect=MutationEffect.STATE_CHANGE_POSSIBLE,
                    authorities=(
                        RetainedAuthorityTransfer(
                            role=role,
                            bound=residue,
                            name_state=(
                                "state_unknown"
                                if clear_succeeded
                                else "delete_pending"
                            ),
                        ),
                    ),
                    winerror=exc.winerror,
                    terminal_release_required=True,
                ) from restore_exc
            assert compensation_complete
            raise Win32MutationFailure(
                exc.reason,
                operation=exc.operation,
                checkpoint=MutationCheckpoint.RESIDUE_API,
                effect=MutationEffect.NO_CHANGE_PROVED,
                authorities=(
                    RetainedAuthorityTransfer(
                        role=role,
                        bound=residue,
                        name_state="owned_present",
                    ),
                ),
                winerror=exc.winerror,
                terminal_release_required=True,
            ) from exc
        raise Win32MutationFailure(
            exc.reason,
            operation=exc.operation,
            checkpoint=(
                MutationCheckpoint.RESIDUE_POSTCHECK
                if closed
                else MutationCheckpoint.RESIDUE_API
                if disposition_set
                else MutationCheckpoint.RESIDUE_PRECONDITION
            ),
            effect=(
                MutationEffect.STATE_CHANGE_POSSIBLE
                if closed
                else MutationEffect.STATE_CHANGE_PROVED
                if disposition_set
                else MutationEffect.NO_CHANGE_PROVED
            ),
            authorities=(
                (
                    RetainedAuthorityTransfer(
                        role=role,
                        bound=residue,
                        name_state=(
                            "delete_pending"
                            if disposition_set
                            else "owned_present"
                        ),
                    ),
                )
                if not residue.closed
                else ()
            ),
            winerror=exc.winerror,
        ) from exc


def complete_delete_pending_residue(
    guard: PrivateMetadataMutationGuard,
    residue: Win32BoundFile,
) -> None:
    """Close an exact retained handle already marked delete-pending."""

    closed = False
    role = _authority_role_for_path(guard, residue.path)
    try:
        guard.require_lock_pair()
        if residue.profile is not FileHandleProfile.RESIDUE_DISPOSITION:
            raise _closed_error(
                RESIDUE_DISPOSITION_FAILED,
                "delete_pending_wrong_profile",
            )
        residue.expected_link_count = 0
        residue.information(
            reason=RESIDUE_DISPOSITION_FAILED,
            operation="delete_pending_information",
        )
        try:
            residue.close(
                reason=RESIDUE_DISPOSITION_FAILED,
                operation="delete_pending_source_close",
            )
        except Win32SafetyError as close_exc:
            raise Win32MutationFailure(
                close_exc.reason,
                operation=close_exc.operation,
                checkpoint=MutationCheckpoint.RESIDUE_API,
                effect=MutationEffect.STATE_CHANGE_PROVED,
                authorities=(
                    RetainedAuthorityTransfer(
                        role=role,
                        bound=residue,
                        name_state="delete_pending",
                        terminal_release_first=True,
                    ),
                ),
                winerror=close_exc.winerror,
                terminal_release_required=True,
            ) from close_exc
        closed = True
        if not path_is_absent(
            guard,
            residue.path,
            reason=FINAL_VERIFICATION_FAILED,
            operation="delete_pending_absence",
        ):
            raise _closed_error(
                FINAL_VERIFICATION_FAILED,
                "delete_pending_name_survived",
            )
        guard.validate_all()
    except Win32MutationFailure:
        raise
    except Win32SafetyError as exc:
        raise Win32MutationFailure(
            exc.reason,
            operation=exc.operation,
            checkpoint=(
                MutationCheckpoint.RESIDUE_POSTCHECK
                if closed
                else MutationCheckpoint.RESIDUE_API
            ),
            effect=(
                MutationEffect.STATE_CHANGE_POSSIBLE
                if closed
                else MutationEffect.STATE_CHANGE_PROVED
            ),
            authorities=(
                (
                    RetainedAuthorityTransfer(
                        role=role,
                        bound=residue,
                        name_state="delete_pending",
                    ),
                )
                if not residue.closed
                else ()
            ),
            winerror=exc.winerror,
        ) from exc


def dispose_unverified_created_file(
    guard: PrivateMetadataMutationGuard,
    created: Win32UnverifiedCreatedFile,
) -> None:
    """Dispose only the exact CREATE_NEW handle after proof failure."""

    disposition_set = False
    closed = False
    role = _authority_role_for_path(guard, created.path)
    try:
        guard.require_lock_pair()
        guard.require_parent_held(created.path)
        guard.validate_all()
        _set_disposition(
            created,
            reason=RESIDUE_DISPOSITION_FAILED,
            operation="unverified_created_file_disposition",
        )
        disposition_set = True
        try:
            created.close(
                reason=RESIDUE_DISPOSITION_FAILED,
                operation="unverified_created_file_close",
            )
        except Win32SafetyError as close_exc:
            raise Win32MutationFailure(
                close_exc.reason,
                operation=close_exc.operation,
                checkpoint=MutationCheckpoint.RESIDUE_API,
                effect=MutationEffect.STATE_CHANGE_PROVED,
                authorities=(
                    RetainedAuthorityTransfer(
                        role=role,
                        bound=created,
                        name_state="delete_pending",
                        terminal_release_first=True,
                    ),
                ),
                winerror=close_exc.winerror,
                terminal_release_required=True,
            ) from close_exc
        closed = True
        if not path_is_absent(
            guard,
            created.path,
            reason=FINAL_VERIFICATION_FAILED,
            operation="unverified_created_file_absence",
        ):
            raise _closed_error(
                FINAL_VERIFICATION_FAILED,
                "unverified_created_file_name_survived",
            )
        guard.validate_all()
    except Win32MutationFailure:
        raise
    except Win32SafetyError as exc:
        raise Win32MutationFailure(
            exc.reason,
            operation=exc.operation,
            checkpoint=(
                MutationCheckpoint.RESIDUE_POSTCHECK
                if closed
                else MutationCheckpoint.RESIDUE_API
                if disposition_set
                else MutationCheckpoint.RESIDUE_PRECONDITION
            ),
            effect=(
                MutationEffect.STATE_CHANGE_POSSIBLE
                if closed
                else MutationEffect.STATE_CHANGE_PROVED
                if disposition_set
                else MutationEffect.NO_CHANGE_PROVED
            ),
            authorities=(
                (
                    RetainedAuthorityTransfer(
                        role=role,
                        bound=created,
                        name_state=(
                            "delete_pending"
                            if disposition_set
                            else "owned_present"
                        ),
                    ),
                )
                if not created.closed
                else ()
            ),
            winerror=exc.winerror,
        ) from exc


def _assert_hardlink_family(
    guard: PrivateMetadataMutationGuard,
    source: Win32BoundFile,
    destination: Path,
) -> None:
    root = guard.archive_root
    source_relative = source.path.relative_to(root).as_posix()
    destination_relative = destination.relative_to(root).as_posix()
    journal_match = re.fullmatch(
        r"objects/manifests/"
        r"\.private-source-metadata-write\.([0-9a-f]{64})\.journal\.tmp",
        source_relative,
    )
    if (
        journal_match is not None
        and destination_relative == PRIVATE_JOURNAL_RELATIVE_PATH
    ):
        return
    receipt_match = re.fullmatch(
        r"receipts/objects/private-source-metadata/"
        r"\.([0-9a-f]{64})\.receipt\.tmp",
        source_relative,
    )
    if (
        receipt_match is not None
        and destination_relative
        == receipt_relative_path(receipt_match.group(1))
    ):
        return
    raise _closed_error(
        HARDLINK_PUBLICATION_FAILED,
        "hardlink_family_not_allowed",
    )


def publish_hard_link(
    guard: PrivateMetadataMutationGuard,
    source: Win32BoundFile,
    *,
    destination_relative_path: str,
    survivor_profile: FileHandleProfile,
    expected_bytes: bytes,
) -> Win32BoundFile:
    """Publish a fixed journal or final receipt with exact ``1 -> 2 -> 1``."""

    published = False
    transitional: Win32BoundFile | None = None
    survivor: Win32BoundFile | None = None
    source_role = (
        "journal_temp"
        if destination_relative_path == PRIVATE_JOURNAL_RELATIVE_PATH
        else "receipt_temp"
    )
    try:
        guard.require_lock_pair()
        if source.profile is not FileHandleProfile.MUTATION_SOURCE:
            raise _closed_error(
                HARDLINK_PUBLICATION_FAILED,
                "hardlink_source_wrong_profile",
            )
        if survivor_profile not in {
            FileHandleProfile.NARROW_READ,
            FileHandleProfile.RESIDUE_DISPOSITION,
        }:
            raise _closed_error(
                HARDLINK_PUBLICATION_FAILED,
                "hardlink_survivor_profile_invalid",
            )
        destination = _archive_path(
            guard.archive_root,
            destination_relative_path,
        )
        guard.require_parent_held(destination)
        _assert_hardlink_family(guard, source, destination)
        source.expected_link_count = 1
        validate_bound_path(
            guard,
            source,
            expected_link_count=1,
            reason=OWNED_TEMP_SUBSTITUTED,
        )
        if source.read_all(
            max_bytes=len(expected_bytes),
            reason=HARDLINK_PUBLICATION_FAILED,
        ) != expected_bytes:
            raise _closed_error(
                HARDLINK_PUBLICATION_FAILED,
                "hardlink_source_bytes_mismatch",
            )
        if not path_is_absent(
            guard,
            destination,
            reason=HARDLINK_PUBLICATION_FAILED,
            operation="hardlink_destination_absence_precheck",
        ):
            raise _closed_error(
                HARDLINK_PUBLICATION_FAILED,
                "hardlink_destination_not_absent",
            )
        guard.validate_all()
        if not _api().create_hard_link(
            _extended_path(destination),
            _extended_path(source.path),
            None,
        ):
            api_error = _last_error(
                HARDLINK_PUBLICATION_FAILED,
                "create_hard_link",
            )
            absence_proved = False
            try:
                absence_proved = path_is_absent(
                    guard,
                    destination,
                    reason=HARDLINK_PUBLICATION_FAILED,
                    operation="hardlink_failed_destination_absence",
                )
            except Win32SafetyError:
                pass
            raise Win32MutationFailure(
                api_error.reason,
                operation=api_error.operation,
                checkpoint=MutationCheckpoint.HARDLINK_API,
                effect=(
                    MutationEffect.NO_CHANGE_PROVED
                    if absence_proved
                    else MutationEffect.STATE_CHANGE_POSSIBLE
                ),
                authorities=(
                    RetainedAuthorityTransfer(
                        role=source_role,
                        bound=source,
                        name_state="owned_present",
                    ),
                ),
                winerror=api_error.winerror,
            )

        published = True
        source.expected_link_count = 2
        transitional = _open_bound_file_absolute(
            guard,
            destination,
            profile=FileHandleProfile.TRANSITIONAL_READ,
            creation_disposition=_OPEN_EXISTING,
            expected_link_count=2,
            reason=FINAL_VERIFICATION_FAILED,
            operation="hardlink_transitional_open",
        )
        if transitional.identity != source.identity:
            raise _closed_error(
                FINAL_VERIFICATION_FAILED,
                "hardlink_identity_mismatch",
            )
        if transitional.read_all(
            max_bytes=len(expected_bytes),
            reason=FINAL_VERIFICATION_FAILED,
        ) != expected_bytes:
            raise _closed_error(
                FINAL_VERIFICATION_FAILED,
                "hardlink_bytes_mismatch",
            )
        _set_disposition(
            source,
            reason=RESIDUE_DISPOSITION_FAILED,
            operation="hardlink_source_disposition",
        )
        source_path = source.path
        try:
            source.close(
                reason=RESIDUE_DISPOSITION_FAILED,
                operation="hardlink_source_close",
            )
        except Win32SafetyError as close_exc:
            # The source is already delete-pending.  Its exact raw handle must
            # terminalize before the coexisting transitional survivor (or any
            # other tracked authority) is closed.  The survivor becomes a
            # single-link authority only after that terminal release.
            raise Win32MutationFailure(
                close_exc.reason,
                operation=close_exc.operation,
                checkpoint=MutationCheckpoint.HARDLINK_POSTCHECK,
                effect=MutationEffect.STATE_CHANGE_PROVED,
                authorities=(
                    RetainedAuthorityTransfer(
                        role=source_role,
                        bound=source,
                        name_state="delete_pending",
                        terminal_release_first=True,
                    ),
                    RetainedAuthorityTransfer(
                        role=(
                            "fixed_journal"
                            if source_role == "journal_temp"
                            else "final_receipt"
                        ),
                        bound=transitional,
                        name_state="owned_present",
                        expected_link_count_after_terminal_release=1,
                    ),
                ),
                winerror=close_exc.winerror,
                terminal_release_required=True,
            ) from close_exc
        if not path_is_absent(
            guard,
            source_path,
            reason=FINAL_VERIFICATION_FAILED,
            operation="hardlink_source_absence",
        ):
            raise _closed_error(
                FINAL_VERIFICATION_FAILED,
                "hardlink_source_name_survived",
            )
        transitional.expected_link_count = 1
        after = transitional.information(
            reason=FINAL_VERIFICATION_FAILED,
            operation="hardlink_transitional_after_disposition",
        )
        if after.identity != source.identity:
            raise _closed_error(
                FINAL_VERIFICATION_FAILED,
                "hardlink_survivor_identity_changed",
            )
        survivor = _reopen_and_compare(
            guard,
            transitional,
            profile=survivor_profile,
            expected_link_count=1,
            reason=FINAL_VERIFICATION_FAILED,
            operation="hardlink_survivor_handoff",
        )
        try:
            transitional.close(
                reason=FINAL_VERIFICATION_FAILED,
                operation="hardlink_transitional_close",
            )
        except Win32SafetyError as close_exc:
            survivor_role = (
                "fixed_journal"
                if source_role == "journal_temp"
                else "final_receipt"
            )
            raise Win32MutationFailure(
                close_exc.reason,
                operation=close_exc.operation,
                checkpoint=MutationCheckpoint.HARDLINK_POSTCHECK,
                effect=MutationEffect.STATE_CHANGE_PROVED,
                authorities=(
                    RetainedAuthorityTransfer(
                        role=survivor_role,
                        bound=transitional,
                        name_state="owned_present",
                        terminal_release_first=True,
                    ),
                    RetainedAuthorityTransfer(
                        role=survivor_role,
                        bound=survivor,
                        name_state="owned_present",
                    ),
                ),
                winerror=close_exc.winerror,
                terminal_release_required=True,
            ) from close_exc
        guard.validate_all()
    except Win32MutationFailure:
        raise
    except Win32SafetyError as exc:
        authorities: list[RetainedAuthorityTransfer] = []
        if not source.closed:
            authorities.append(
                RetainedAuthorityTransfer(
                    role=source_role,
                    bound=source,
                    name_state=(
                        "twin_published" if published else "owned_present"
                    ),
                )
            )
        if transitional is not None and not transitional.closed:
            authorities.append(
                RetainedAuthorityTransfer(
                    role=(
                        "fixed_journal"
                        if source_role == "journal_temp"
                        else "final_receipt"
                    ),
                    bound=transitional,
                    name_state="twin_published",
                )
            )
        if survivor is not None and not survivor.closed:
            authorities.append(
                RetainedAuthorityTransfer(
                    role=(
                        "fixed_journal"
                        if source_role == "journal_temp"
                        else "final_receipt"
                    ),
                    bound=survivor,
                    name_state="owned_present",
                )
            )
        raise Win32MutationFailure(
            exc.reason,
            operation=exc.operation,
            checkpoint=(
                MutationCheckpoint.HARDLINK_POSTCHECK
                if published
                else MutationCheckpoint.HARDLINK_PRECONDITION
            ),
            effect=(
                MutationEffect.STATE_CHANGE_PROVED
                if published
                else MutationEffect.NO_CHANGE_PROVED
            ),
            authorities=authorities,
            winerror=exc.winerror,
        ) from exc
    assert transitional is not None and survivor is not None
    return survivor


def file_rename_info_buffer(
    destination: Path | str,
    *,
    replace_if_exists: bool,
) -> FileRenameInfoBuffer:
    """Build exact logical rename bytes plus one readable UTF-16 NUL guard."""

    _require_windows("file_rename_info_buffer")
    destination_utf16 = _extended_path(destination).encode("utf-16-le")
    layout = _api().FileRenameInfoLayout
    file_name_offset = int(layout.file_name.offset)
    file_name_length = len(destination_utf16)
    logical_size = file_name_offset + file_name_length
    backing_size = logical_size + ctypes.sizeof(ctypes.c_wchar)
    if ctypes.sizeof(ctypes.c_wchar) != 2:
        raise _closed_error(
            REQUIRED_PRIMITIVE_UNAVAILABLE,
            "file_rename_info_wchar_size",
        )
    buffer = ctypes.create_string_buffer(backing_size)
    ctypes.c_ubyte.from_buffer(
        buffer,
        int(layout.replace_if_exists.offset),
    ).value = 1 if replace_if_exists else 0
    ctypes.c_void_p.from_buffer(
        buffer,
        int(layout.root_directory.offset),
    ).value = None
    ctypes.c_uint32.from_buffer(
        buffer,
        int(layout.file_name_length.offset),
    ).value = file_name_length
    ctypes.memmove(
        ctypes.addressof(buffer) + file_name_offset,
        destination_utf16,
        file_name_length,
    )
    if bytes(buffer[logical_size:backing_size]) != b"\x00\x00":
        raise _closed_error(
            REQUIRED_PRIMITIVE_UNAVAILABLE,
            "file_rename_info_nul_guard_missing",
        )
    return FileRenameInfoBuffer(
        backing=buffer,
        file_name_offset=file_name_offset,
        file_name_length=file_name_length,
        logical_size=logical_size,
        backing_size=backing_size,
        api_buffer_size=logical_size,
    )


def _assert_private_manifest_destination(
    guard: PrivateMetadataMutationGuard,
    destination: Path,
) -> None:
    expected = _archive_path(
        guard.archive_root,
        PRIVATE_MANIFEST_RELATIVE_PATH,
    )
    if _path_key(destination) != _path_key(expected):
        raise _closed_error(
            MANIFEST_REPLACEMENT_FAILED,
            "manifest_destination_not_canonical",
        )


def replace_private_manifest(
    guard: PrivateMetadataMutationGuard,
    source: Win32BoundFile,
    *,
    authority_key_hex: str,
    replace_if_exists: bool,
    before_authority: Win32BoundFile | None,
    expected_bytes: bytes,
) -> Win32BoundFile:
    """Rename the retained manifest temp to the exact canonical target."""

    renamed = False
    transitional: Win32BoundFile | None = None
    narrow: Win32BoundFile | None = None
    restored_before: Win32BoundFile | None = None
    try:
        if not _MINIMAL_RENAME_PROFILE_APPROVAL_ENABLED:
            raise _closed_error(
                REQUIRED_PRIMITIVE_UNAVAILABLE,
                "file_rename_info_minimal_buffer_hazard",
            )
        guard.require_lock_pair()
        if source.profile is not FileHandleProfile.MUTATION_SOURCE:
            raise _closed_error(
                MANIFEST_REPLACEMENT_FAILED,
                "manifest_source_wrong_profile",
            )
        expected_source = _archive_path(
            guard.archive_root,
            owned_temp_relative_path(
                OwnedTempKind.MANIFEST,
                authority_key_hex,
            ),
        )
        if str(source.path) != str(expected_source):
            raise _closed_error(
                OWNED_TEMP_SUBSTITUTED,
                "manifest_source_not_canonical_owned_temp",
            )
        destination = _archive_path(
            guard.archive_root,
            PRIVATE_MANIFEST_RELATIVE_PATH,
        )
        _assert_private_manifest_destination(guard, destination)
        source.expected_link_count = 1
        validate_bound_path(
            guard,
            source,
            expected_link_count=1,
            reason=OWNED_TEMP_SUBSTITUTED,
        )
        if source.read_all(
            max_bytes=len(expected_bytes),
            reason=MANIFEST_REPLACEMENT_FAILED,
        ) != expected_bytes:
            raise _closed_error(
                MANIFEST_REPLACEMENT_FAILED,
                "manifest_source_bytes_mismatch",
            )

        if replace_if_exists:
            if before_authority is None:
                raise _closed_error(
                    MANIFEST_REPLACEMENT_FAILED,
                    "manifest_before_authority_required",
                )
            if before_authority.path != destination:
                raise _closed_error(
                    MANIFEST_REPLACEMENT_FAILED,
                    "manifest_before_path_mismatch",
                )
            validate_bound_path(
                guard,
                before_authority,
                expected_link_count=1,
                reason=MANIFEST_REPLACEMENT_FAILED,
            )
            # Ordinary FileRenameInfo cannot replace while the old target
            # verifier remains open. Close only at this single boundary.
            try:
                before_authority.close(
                    reason=MANIFEST_REPLACEMENT_FAILED,
                    operation="manifest_old_target_boundary_close",
                )
            except Win32SafetyError as close_exc:
                raise Win32MutationFailure(
                    close_exc.reason,
                    operation=close_exc.operation,
                    checkpoint=MutationCheckpoint.MANIFEST_PRECONDITION,
                    effect=MutationEffect.NO_CHANGE_PROVED,
                    authorities=(
                        RetainedAuthorityTransfer(
                            role="private_manifest",
                            bound=before_authority,
                            name_state="owned_present",
                            terminal_release_first=True,
                        ),
                        RetainedAuthorityTransfer(
                            role="manifest_temp",
                            bound=source,
                            name_state="owned_present",
                        ),
                    ),
                    winerror=close_exc.winerror,
                    terminal_release_required=True,
                ) from close_exc
        else:
            if before_authority is not None:
                raise _closed_error(
                    MANIFEST_REPLACEMENT_FAILED,
                    "manifest_before_authority_for_absent_target",
                )
            if not path_is_absent(
                guard,
                destination,
                reason=MANIFEST_REPLACEMENT_FAILED,
                operation="manifest_absent_target_precheck",
            ):
                raise _closed_error(
                    MANIFEST_REPLACEMENT_FAILED,
                    "manifest_absent_target_raced_in",
                    winerror=_ERROR_ALREADY_EXISTS,
                )

        guard.validate_all()
        validate_bound_path(
            guard,
            source,
            expected_link_count=1,
            reason=OWNED_TEMP_SUBSTITUTED,
        )
        rename_information = file_rename_info_buffer(
            destination,
            replace_if_exists=replace_if_exists,
        )
        if not _api().set_file_information(
            source.raw_handle,
            _FILE_RENAME_INFO_CLASS,
            rename_information.backing,
            rename_information.api_buffer_size,
        ):
            api_error = _last_error(
                MANIFEST_REPLACEMENT_FAILED,
                "file_rename_info",
            )
            no_change_proved = False
            try:
                validate_bound_path(
                    guard,
                    source,
                    expected_link_count=1,
                    reason=MANIFEST_REPLACEMENT_FAILED,
                )
                if replace_if_exists:
                    assert before_authority is not None
                    restored_before = _open_bound_file_absolute(
                        guard,
                        destination,
                        profile=FileHandleProfile.NARROW_READ,
                        creation_disposition=_OPEN_EXISTING,
                        expected_link_count=1,
                        reason=MANIFEST_REPLACEMENT_FAILED,
                        operation="manifest_failed_before_restore",
                    )
                    no_change_proved = (
                        restored_before.identity
                        == before_authority.identity
                    )
                else:
                    no_change_proved = path_is_absent(
                        guard,
                        destination,
                        reason=MANIFEST_REPLACEMENT_FAILED,
                        operation="manifest_failed_target_absence",
                    )
            except Win32SafetyError:
                no_change_proved = False
            authorities = [
                RetainedAuthorityTransfer(
                    role=(
                        "manifest_temp"
                        if no_change_proved
                        else "private_manifest_unknown"
                    ),
                    bound=source,
                    name_state=(
                        "owned_present"
                        if no_change_proved
                        else "preserved_unverified"
                    ),
                )
            ]
            if restored_before is not None:
                authorities.append(
                    RetainedAuthorityTransfer(
                        role="private_manifest",
                        bound=restored_before,
                        name_state="owned_present",
                    )
                )
            raise Win32MutationFailure(
                api_error.reason,
                operation=api_error.operation,
                checkpoint=MutationCheckpoint.MANIFEST_RENAME_API,
                effect=(
                    MutationEffect.NO_CHANGE_PROVED
                    if no_change_proved
                    else MutationEffect.STATE_CHANGE_POSSIBLE
                ),
                authorities=authorities,
                winerror=api_error.winerror,
            )

        renamed = True
        source_path = source.path
        transitional = _open_bound_file_absolute(
            guard,
            destination,
            profile=FileHandleProfile.TRANSITIONAL_READ,
            creation_disposition=_OPEN_EXISTING,
            expected_link_count=1,
            reason=FINAL_VERIFICATION_FAILED,
            operation="manifest_transitional_open",
        )
        if transitional.identity != source.identity:
            raise _closed_error(
                FINAL_VERIFICATION_FAILED,
                "manifest_replacement_identity_mismatch",
            )
        if transitional.read_all(
            max_bytes=len(expected_bytes),
            reason=FINAL_VERIFICATION_FAILED,
        ) != expected_bytes:
            raise _closed_error(
                FINAL_VERIFICATION_FAILED,
                "manifest_replacement_bytes_mismatch",
            )
        if not path_is_absent(
            guard,
            source_path,
            reason=FINAL_VERIFICATION_FAILED,
            operation="manifest_temp_absence",
        ):
            raise _closed_error(
                FINAL_VERIFICATION_FAILED,
                "manifest_temp_name_survived",
            )
        try:
            source.close(
                reason=FINAL_VERIFICATION_FAILED,
                operation="manifest_renamed_source_close",
            )
        except Win32SafetyError as close_exc:
            raise Win32MutationFailure(
                close_exc.reason,
                operation=close_exc.operation,
                checkpoint=MutationCheckpoint.MANIFEST_POSTCHECK,
                effect=MutationEffect.STATE_CHANGE_PROVED,
                authorities=(
                    RetainedAuthorityTransfer(
                        role="private_manifest",
                        bound=source,
                        name_state="renamed_final",
                        terminal_release_first=True,
                    ),
                    RetainedAuthorityTransfer(
                        role="private_manifest",
                        bound=transitional,
                        name_state="renamed_final",
                    ),
                ),
                winerror=close_exc.winerror,
                terminal_release_required=True,
            ) from close_exc
        narrow = _reopen_and_compare(
            guard,
            transitional,
            profile=FileHandleProfile.NARROW_READ,
            expected_link_count=1,
            reason=FINAL_VERIFICATION_FAILED,
            operation="manifest_narrow_handoff",
        )
        try:
            transitional.close(
                reason=FINAL_VERIFICATION_FAILED,
                operation="manifest_transitional_close",
            )
        except Win32SafetyError as close_exc:
            raise Win32MutationFailure(
                close_exc.reason,
                operation=close_exc.operation,
                checkpoint=MutationCheckpoint.MANIFEST_POSTCHECK,
                effect=MutationEffect.STATE_CHANGE_PROVED,
                authorities=(
                    RetainedAuthorityTransfer(
                        role="private_manifest",
                        bound=transitional,
                        name_state="renamed_final",
                        terminal_release_first=True,
                    ),
                    RetainedAuthorityTransfer(
                        role="private_manifest",
                        bound=narrow,
                        name_state="renamed_final",
                    ),
                ),
                winerror=close_exc.winerror,
                terminal_release_required=True,
            ) from close_exc
        guard.validate_all()
    except Win32MutationFailure:
        raise
    except Win32SafetyError as exc:
        authorities: list[RetainedAuthorityTransfer] = []
        if renamed:
            retained_after: list[Win32BoundFile] = []
            for candidate in (source, transitional, narrow):
                if (
                    candidate is not None
                    and not candidate.closed
                    and all(
                        existing is not candidate
                        for existing in retained_after
                    )
                ):
                    retained_after.append(candidate)
            for candidate in retained_after:
                authorities.append(
                    RetainedAuthorityTransfer(
                        role="private_manifest",
                        bound=candidate,
                        name_state="renamed_final",
                    )
                )
        else:
            if not source.closed:
                authorities.append(
                    RetainedAuthorityTransfer(
                        role="manifest_temp",
                        bound=source,
                        name_state="owned_present",
                    )
                )
            if (
                before_authority is not None
                and not before_authority.closed
            ):
                authorities.append(
                    RetainedAuthorityTransfer(
                        role="private_manifest",
                        bound=before_authority,
                        name_state="owned_present",
                    )
                )
        raise Win32MutationFailure(
            exc.reason,
            operation=exc.operation,
            checkpoint=(
                MutationCheckpoint.MANIFEST_POSTCHECK
                if renamed
                else MutationCheckpoint.MANIFEST_PRECONDITION
            ),
            effect=(
                MutationEffect.STATE_CHANGE_PROVED
                if renamed
                else MutationEffect.NO_CHANGE_PROVED
            ),
            authorities=authorities,
            winerror=exc.winerror,
        ) from exc
    assert narrow is not None
    return narrow


def win32_error_constants() -> dict[str, int]:
    """Expose exact values for synthetic cross-platform contract tests."""

    return {
        "ERROR_ACCESS_DENIED": _ERROR_ACCESS_DENIED,
        "ERROR_SHARING_VIOLATION": _ERROR_SHARING_VIOLATION,
        "ERROR_ALREADY_EXISTS": _ERROR_ALREADY_EXISTS,
    }


__all__ = [
    "APPROVAL_PLATFORM_NOT_SUPPORTED",
    "ApprovalSupportStatus",
    "CoordinationLockKind",
    "FileHandleProfile",
    "FileRenameInfoBuffer",
    "HARDLINK_PUBLICATION_FAILED",
    "LOCK_IDENTITY_CHANGED",
    "MutationCheckpoint",
    "MutationEffect",
    "OBJECT_MANIFEST_DIRECTORY_BOOTSTRAP_FAILED",
    "OBJECT_MANIFEST_LOCK_RELATIVE_PATH",
    "OWNED_TEMP_MATERIALIZATION_FAILED",
    "OwnedTempKind",
    "PRIVATE_JOURNAL_RELATIVE_PATH",
    "PRIVATE_MANIFEST_RELATIVE_PATH",
    "PRIVATE_METADATA_LOCK_RELATIVE_PATH",
    "PRIVATE_RECEIPT_DIRECTORY_RELATIVE_PATH",
    "PrivateMetadataLockPair",
    "PrivateMetadataMutationGuard",
    "PersistentCoordinationLock",
    "REQUIRED_PRIMITIVE_UNAVAILABLE",
    "RetainedAuthorityTransfer",
    "WINDOWS_NTFS_MUTATION_PROFILE",
    "Win32BoundFile",
    "Win32FileIdentity",
    "Win32FileInformation",
    "Win32SafetyError",
    "Win32MutationFailure",
    "Win32UnverifiedCreatedFile",
    "approval_support_status",
    "bootstrap_object_manifest_lock_directories",
    "complete_delete_pending_residue",
    "create_guarded_directory",
    "dispose_bound_residue",
    "dispose_unverified_created_file",
    "file_rename_info_buffer",
    "handoff_to_narrow_authority",
    "handoff_to_residue_authority",
    "handoff_same_identity_twin_to_residue",
    "materialize_owned_temp",
    "open_bound_file",
    "owned_temp_relative_path",
    "path_is_absent",
    "publish_hard_link",
    "receipt_relative_path",
    "release_terminal_bound_authority",
    "replace_private_manifest",
    "validate_bound_path",
    "win32_error_constants",
]
