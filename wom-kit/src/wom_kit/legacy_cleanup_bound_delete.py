"""Retained-handle deletion primitives for legacy coordination cleanup.

These helpers remove one already-approved regular file or one already-approved
empty directory.  They deliberately do not discover targets, recurse, interpret
approval, or print paths.  Callers remain responsible for the higher-level
cleanup plan and for turning any exception into a non-success result.

The important invariant is that an approved mutation either proves the exact
object or does not run:

* Windows keeps a non-reparse ``CreateFileW`` handle with delete access, marks
  that exact handle with ``FileDispositionInfo``, revalidates its bytes and
  delete-pending link count, and only then closes it.
* POSIX fails before mutation because its standard name-based deletion APIs
  cannot atomically require an expected inode.

No exception created here contains a local path, filename, or file content.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .archive_services import _activity_group_bound_directory_chain


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REPARSE_FLAG = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
_CHUNK_SIZE = 1024 * 1024


class LegacyCleanupBoundDeleteError(OSError):
    """Content-free failure from an exact-object deletion primitive."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class _ApprovedFile:
    device: int
    inode: int
    size: int
    mtime_ns: int
    sha256: str


@dataclass(frozen=True)
class _ApprovedDirectory:
    device: int
    inode: int


def _fail(code: str) -> LegacyCleanupBoundDeleteError:
    return LegacyCleanupBoundDeleteError(code)


def _is_reparse(info: os.stat_result) -> bool:
    return bool(
        stat.S_ISLNK(info.st_mode)
        or (
            REPARSE_FLAG
            and getattr(info, "st_file_attributes", 0) & REPARSE_FLAG
        )
    )


def _identity(info: os.stat_result) -> tuple[int, int]:
    return int(info.st_dev), int(info.st_ino)


def _required_int(value: Any, code: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise _fail(code)
    return int(value)


def _approved_identity(expected: Mapping[str, Any]) -> tuple[int, int]:
    identity = expected.get("identity")
    if not isinstance(identity, Mapping):
        raise _fail("legacy_cleanup_expected_identity_invalid")
    device = _required_int(
        identity.get("device"),
        "legacy_cleanup_expected_identity_invalid",
    )
    inode = _required_int(
        identity.get("inode"),
        "legacy_cleanup_expected_identity_invalid",
        minimum=1,
    )
    return device, inode


def _approved_file(expected: Mapping[str, Any]) -> _ApprovedFile:
    if not isinstance(expected, Mapping) or expected.get("type") != "file":
        raise _fail("legacy_cleanup_expected_file_invalid")
    device, inode = _approved_identity(expected)
    size = _required_int(
        expected.get("size"),
        "legacy_cleanup_expected_file_size_invalid",
    )
    raw_mtime_ns = expected.get("mtime_ns")
    if isinstance(raw_mtime_ns, bool) or not isinstance(raw_mtime_ns, int):
        raise _fail("legacy_cleanup_expected_file_mtime_invalid")
    # Filesystems can represent timestamps before the Unix epoch.  A negative
    # nanosecond value is valid state, not an unsafe approval record.
    mtime_ns = int(raw_mtime_ns)
    digest = expected.get("sha256")
    if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
        raise _fail("legacy_cleanup_expected_file_sha256_invalid")
    return _ApprovedFile(
        device=device,
        inode=inode,
        size=size,
        mtime_ns=mtime_ns,
        sha256=digest,
    )


def _approved_directory(expected: Mapping[str, Any]) -> _ApprovedDirectory:
    if not isinstance(expected, Mapping) or expected.get("type") != "directory":
        raise _fail("legacy_cleanup_expected_directory_invalid")
    device, inode = _approved_identity(expected)
    return _ApprovedDirectory(device=device, inode=inode)


def _validated_paths(
    workspace_root: Path | str,
    path: Path | str,
) -> tuple[Path, Path]:
    supplied_root = Path(workspace_root)
    supplied_path = Path(path)
    if not supplied_root.is_absolute() or not supplied_path.is_absolute():
        raise _fail("legacy_cleanup_bound_path_not_absolute")

    lexical_root = Path(os.path.abspath(str(supplied_root)))
    lexical_path = Path(os.path.abspath(str(supplied_path)))
    try:
        relative = lexical_path.relative_to(lexical_root)
    except ValueError as exc:
        raise _fail("legacy_cleanup_bound_path_outside_root") from exc
    if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise _fail("legacy_cleanup_bound_path_invalid")
    if os.name == "nt" and any(":" in part for part in relative.parts):
        # A colon in a descendant component can address an NTFS alternate data
        # stream instead of the reviewed directory entry.
        raise _fail("legacy_cleanup_bound_path_stream_syntax")

    try:
        root_stat = os.lstat(lexical_root)
        if _is_reparse(root_stat) or not stat.S_ISDIR(root_stat.st_mode):
            raise _fail("legacy_cleanup_bound_root_unsafe")
        canonical_root = lexical_root.resolve(strict=True)
    except LegacyCleanupBoundDeleteError:
        raise
    except OSError as exc:
        raise _fail("legacy_cleanup_bound_root_unreadable") from exc
    candidate = canonical_root.joinpath(*relative.parts)
    return canonical_root, candidate


def _path_is_absent_no_follow(path: Path) -> bool:
    try:
        os.lstat(path)
    except FileNotFoundError:
        return True
    except OSError as exc:
        raise _fail("legacy_cleanup_bound_name_absence_uncertain") from exc
    return False


def _delete_posix_file(
    workspace_root: Path,
    path: Path,
    approved: _ApprovedFile,
) -> None:
    del workspace_root, path, approved
    # POSIX unlinkat accepts a directory descriptor and a name, but it has no
    # compare-and-delete operation for an expected inode.  A concurrent name
    # swap could therefore remove an unapproved replacement.  Until a stronger
    # primitive is available, apply is Windows-only and POSIX never mutates.
    raise _fail("legacy_cleanup_bound_apply_platform_unsupported")


def _delete_posix_directory(
    workspace_root: Path,
    path: Path,
    approved: _ApprovedDirectory,
) -> None:
    del workspace_root, path, approved
    raise _fail("legacy_cleanup_bound_apply_platform_unsupported")


def _windows_extended_path(path: Path) -> str:
    value = os.path.abspath(str(path))
    if value.startswith("\\\\?\\"):
        return value
    if value.startswith("\\\\"):
        return "\\\\?\\UNC\\" + value[2:]
    return "\\\\?\\" + value


@dataclass(frozen=True)
class _WindowsInformation:
    attributes: int
    volume_serial: int
    file_index: int
    link_count: int
    size: int
    mtime_ns: int


class _Win32Api:
    GENERIC_READ = 0x80000000
    DELETE = 0x00010000
    FILE_LIST_DIRECTORY = 0x00000001
    FILE_READ_ATTRIBUTES = 0x00000080
    FILE_SHARE_READ = 0x00000001
    OPEN_EXISTING = 3
    FILE_ATTRIBUTE_DIRECTORY = 0x00000010
    FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
    FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    FILE_DISPOSITION_INFO_CLASS = 4
    FILE_STREAM_INFO_CLASS = 7
    ERROR_HANDLE_EOF = 38
    ERROR_INSUFFICIENT_BUFFER = 122
    ERROR_MORE_DATA = 234
    WINDOWS_EPOCH_TICKS = 116_444_736_000_000_000

    def __init__(self) -> None:
        if os.name != "nt":
            raise _fail("legacy_cleanup_bound_win32_unavailable")
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

        class FileDispositionInformation(ctypes.Structure):
            _fields_ = [("DeleteFile", ctypes.c_ubyte)]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.create_file = kernel32.CreateFileW
        self.create_file.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        self.create_file.restype = wintypes.HANDLE
        self.get_information = kernel32.GetFileInformationByHandle
        self.get_information.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(ByHandleFileInformation),
        ]
        self.get_information.restype = wintypes.BOOL
        self.get_information_ex = kernel32.GetFileInformationByHandleEx
        self.get_information_ex.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        self.get_information_ex.restype = wintypes.BOOL
        self.set_pointer = kernel32.SetFilePointerEx
        self.set_pointer.argtypes = [
            wintypes.HANDLE,
            ctypes.c_longlong,
            ctypes.POINTER(ctypes.c_longlong),
            wintypes.DWORD,
        ]
        self.set_pointer.restype = wintypes.BOOL
        self.read_file = kernel32.ReadFile
        self.read_file.argtypes = [
            wintypes.HANDLE,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ]
        self.read_file.restype = wintypes.BOOL
        self.set_information = kernel32.SetFileInformationByHandle
        self.set_information.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        self.set_information.restype = wintypes.BOOL
        self.close_handle = kernel32.CloseHandle
        self.close_handle.argtypes = [wintypes.HANDLE]
        self.close_handle.restype = wintypes.BOOL
        self.ByHandleFileInformation = ByHandleFileInformation
        self.FileDispositionInformation = FileDispositionInformation
        self.DWORD = wintypes.DWORD
        self.invalid_handle = ctypes.c_void_p(-1).value

    def query(self, handle: int) -> _WindowsInformation:
        raw = self.ByHandleFileInformation()
        if not self.get_information(handle, ctypes.byref(raw)):
            raise _fail("legacy_cleanup_bound_win32_information_uncertain")
        ticks = (
            int(raw.ftLastWriteTime.dwHighDateTime) << 32
        ) | int(raw.ftLastWriteTime.dwLowDateTime)
        return _WindowsInformation(
            attributes=int(raw.dwFileAttributes),
            volume_serial=int(raw.dwVolumeSerialNumber),
            file_index=(int(raw.nFileIndexHigh) << 32) | int(raw.nFileIndexLow),
            link_count=int(raw.nNumberOfLinks),
            size=(int(raw.nFileSizeHigh) << 32) | int(raw.nFileSizeLow),
            mtime_ns=(ticks - self.WINDOWS_EPOCH_TICKS) * 100,
        )

    def set_disposition(self, handle: int, delete: bool) -> None:
        disposition = self.FileDispositionInformation(1 if delete else 0)
        if not self.set_information(
            handle,
            self.FILE_DISPOSITION_INFO_CLASS,
            ctypes.byref(disposition),
            ctypes.sizeof(disposition),
        ):
            raise _fail(
                "legacy_cleanup_bound_win32_disposition_uncertain"
                if delete
                else "legacy_cleanup_bound_win32_cancellation_uncertain"
            )


_WIN32_API: _Win32Api | None = None


def _windows_api() -> _Win32Api:
    global _WIN32_API
    if _WIN32_API is None:
        _WIN32_API = _Win32Api()
    return _WIN32_API


def _windows_open(path: Path, *, directory: bool) -> int:
    api = _windows_api()
    desired_access = api.DELETE | api.FILE_READ_ATTRIBUTES
    flags = api.FILE_FLAG_OPEN_REPARSE_POINT
    if directory:
        desired_access |= api.FILE_LIST_DIRECTORY
        flags |= api.FILE_FLAG_BACKUP_SEMANTICS
    else:
        desired_access |= api.GENERIC_READ
    handle = api.create_file(
        _windows_extended_path(path),
        desired_access,
        api.FILE_SHARE_READ,
        None,
        api.OPEN_EXISTING,
        flags,
        None,
    )
    value = handle if isinstance(handle, int) else getattr(handle, "value", None)
    if value in {None, api.invalid_handle}:
        raise _fail("legacy_cleanup_bound_win32_open_uncertain")
    return int(value)


def _windows_close(handle: int) -> None:
    if not _windows_api().close_handle(handle):
        raise _fail("legacy_cleanup_bound_win32_close_uncertain")


def _windows_stream_names(handle: int, *, directory: bool) -> tuple[str, ...]:
    api = _windows_api()
    capacity = 4096
    raw_bytes: bytes | None = None
    while capacity <= 1024 * 1024:
        buffer = ctypes.create_string_buffer(capacity)
        ctypes.set_last_error(0)
        if api.get_information_ex(
            handle,
            api.FILE_STREAM_INFO_CLASS,
            buffer,
            capacity,
        ):
            raw_bytes = bytes(buffer)
            break
        error = ctypes.get_last_error()
        if directory and error == api.ERROR_HANDLE_EOF:
            return ()
        if error not in {api.ERROR_INSUFFICIENT_BUFFER, api.ERROR_MORE_DATA}:
            raise _fail("legacy_cleanup_bound_win32_stream_inventory_uncertain")
        capacity *= 2
    if raw_bytes is None:
        raise _fail("legacy_cleanup_bound_win32_stream_inventory_too_large")

    names: list[str] = []
    offset = 0
    header_size = 24
    while True:
        if offset + header_size > len(raw_bytes):
            raise _fail("legacy_cleanup_bound_win32_stream_inventory_malformed")
        next_offset = int.from_bytes(raw_bytes[offset : offset + 4], "little")
        name_bytes = int.from_bytes(raw_bytes[offset + 4 : offset + 8], "little")
        if name_bytes <= 0 or name_bytes % 2:
            raise _fail("legacy_cleanup_bound_win32_stream_inventory_malformed")
        end = offset + header_size + name_bytes
        if end > len(raw_bytes):
            raise _fail("legacy_cleanup_bound_win32_stream_inventory_malformed")
        try:
            name = raw_bytes[offset + header_size : end].decode("utf-16-le")
        except UnicodeDecodeError as exc:
            raise _fail(
                "legacy_cleanup_bound_win32_stream_inventory_malformed"
            ) from exc
        names.append(name)
        if next_offset == 0:
            break
        if next_offset < header_size + name_bytes or next_offset % 8:
            raise _fail("legacy_cleanup_bound_win32_stream_inventory_malformed")
        offset += next_offset
    return tuple(names)


def _reject_windows_alternate_streams(handle: int, *, directory: bool) -> None:
    names = _windows_stream_names(handle, directory=directory)
    if directory:
        if names:
            raise _fail("legacy_cleanup_bound_alternate_data_stream")
        return
    if names != ("::$DATA",):
        raise _fail("legacy_cleanup_bound_alternate_data_stream")


def _validate_windows_file_information(
    information: _WindowsInformation,
    approved: _ApprovedFile,
    *,
    expected_link_count: int,
) -> None:
    api = _windows_api()
    if (
        information.attributes
        & (api.FILE_ATTRIBUTE_DIRECTORY | api.FILE_ATTRIBUTE_REPARSE_POINT)
        or information.file_index != approved.inode
        or information.file_index == 0
        or information.link_count != expected_link_count
        or information.size != approved.size
        or information.mtime_ns != approved.mtime_ns
    ):
        raise _fail("legacy_cleanup_bound_win32_file_state_drift")


def _windows_digest_handle(
    handle: int,
    approved: _ApprovedFile,
    *,
    expected_link_count: int,
) -> str:
    api = _windows_api()
    before = api.query(handle)
    _validate_windows_file_information(
        before,
        approved,
        expected_link_count=expected_link_count,
    )
    position = ctypes.c_longlong()
    if not api.set_pointer(handle, 0, ctypes.byref(position), 0):
        raise _fail("legacy_cleanup_bound_win32_read_uncertain")
    digest = hashlib.sha256()
    remaining = approved.size
    while remaining:
        request = min(_CHUNK_SIZE, remaining)
        buffer = ctypes.create_string_buffer(request)
        read_count = api.DWORD()
        if not api.read_file(
            handle,
            buffer,
            request,
            ctypes.byref(read_count),
            None,
        ):
            raise _fail("legacy_cleanup_bound_win32_read_uncertain")
        progressed = int(read_count.value)
        if progressed <= 0 or progressed > request:
            raise _fail("legacy_cleanup_bound_win32_read_uncertain")
        digest.update(buffer.raw[:progressed])
        remaining -= progressed

    probe = ctypes.create_string_buffer(1)
    probe_count = api.DWORD()
    if not api.read_file(
        handle,
        probe,
        1,
        ctypes.byref(probe_count),
        None,
    ) or int(probe_count.value) != 0:
        raise _fail("legacy_cleanup_bound_win32_file_size_drift")
    after = api.query(handle)
    _validate_windows_file_information(
        after,
        approved,
        expected_link_count=expected_link_count,
    )
    if after != before or digest.hexdigest() != approved.sha256:
        raise _fail("legacy_cleanup_bound_win32_file_bytes_drift")
    return digest.hexdigest()


def _validate_windows_named_file(path: Path, approved: _ApprovedFile) -> None:
    try:
        named = os.lstat(path)
    except OSError as exc:
        raise _fail("legacy_cleanup_bound_win32_file_name_uncertain") from exc
    if (
        _is_reparse(named)
        or not stat.S_ISREG(named.st_mode)
        or _identity(named) != (approved.device, approved.inode)
        or int(named.st_nlink) != 1
        or int(named.st_size) != approved.size
        or int(named.st_mtime_ns) != approved.mtime_ns
    ):
        raise _fail("legacy_cleanup_bound_win32_file_name_drift")


def _cancel_windows_file_disposition(
    handle: int,
    path: Path,
    approved: _ApprovedFile,
) -> None:
    api = _windows_api()
    try:
        api.set_disposition(handle, False)
        _windows_digest_handle(handle, approved, expected_link_count=1)
        _reject_windows_alternate_streams(handle, directory=False)
        _validate_windows_named_file(path, approved)
    except BaseException as exc:
        if isinstance(exc, LegacyCleanupBoundDeleteError) and exc.code == (
            "legacy_cleanup_bound_win32_cancellation_uncertain"
        ):
            raise
        raise _fail("legacy_cleanup_bound_win32_cancellation_uncertain") from exc


def _delete_windows_file(
    workspace_root: Path,
    path: Path,
    approved: _ApprovedFile,
) -> None:
    with _activity_group_bound_directory_chain(
        workspace_root,
        path.parent,
    ):
        handle = _windows_open(path, directory=False)
        failure: BaseException | None = None
        delete_marked = False
        committed = False
        try:
            _validate_windows_named_file(path, approved)
            _reject_windows_alternate_streams(handle, directory=False)
            _windows_digest_handle(handle, approved, expected_link_count=1)
            _windows_api().set_disposition(handle, True)
            delete_marked = True
            _windows_digest_handle(handle, approved, expected_link_count=0)
            _reject_windows_alternate_streams(handle, directory=False)
            committed = True
        except BaseException as exc:
            failure = exc
            if delete_marked and not committed:
                try:
                    _cancel_windows_file_disposition(handle, path, approved)
                    delete_marked = False
                except BaseException as cancel_exc:
                    failure = cancel_exc

        try:
            _windows_close(handle)
        except LegacyCleanupBoundDeleteError as close_exc:
            failure = close_exc
        if failure is not None:
            if isinstance(failure, LegacyCleanupBoundDeleteError):
                raise failure
            raise _fail("legacy_cleanup_bound_win32_file_delete_uncertain") from failure
        if not committed or not _path_is_absent_no_follow(path):
            raise _fail("legacy_cleanup_bound_win32_file_delete_unproved")


def _validate_windows_directory_information(
    information: _WindowsInformation,
    approved: _ApprovedDirectory,
    *,
    expected_link_count: int | None,
) -> None:
    api = _windows_api()
    if (
        not information.attributes & api.FILE_ATTRIBUTE_DIRECTORY
        or information.attributes & api.FILE_ATTRIBUTE_REPARSE_POINT
        or information.file_index != approved.inode
        or information.file_index == 0
        or (
            expected_link_count is not None
            and information.link_count != expected_link_count
        )
    ):
        raise _fail("legacy_cleanup_bound_win32_directory_state_drift")


def _validate_windows_named_directory(
    path: Path,
    approved: _ApprovedDirectory,
) -> None:
    try:
        named = os.lstat(path)
    except OSError as exc:
        raise _fail("legacy_cleanup_bound_win32_directory_name_uncertain") from exc
    if (
        _is_reparse(named)
        or not stat.S_ISDIR(named.st_mode)
        or _identity(named) != (approved.device, approved.inode)
    ):
        raise _fail("legacy_cleanup_bound_win32_directory_name_drift")


def _cancel_windows_directory_disposition(
    handle: int,
    path: Path,
    approved: _ApprovedDirectory,
    original_link_count: int,
) -> None:
    try:
        _windows_api().set_disposition(handle, False)
        information = _windows_api().query(handle)
        _validate_windows_directory_information(
            information,
            approved,
            expected_link_count=original_link_count,
        )
        _reject_windows_alternate_streams(handle, directory=True)
        _validate_windows_named_directory(path, approved)
    except BaseException as exc:
        if isinstance(exc, LegacyCleanupBoundDeleteError) and exc.code == (
            "legacy_cleanup_bound_win32_cancellation_uncertain"
        ):
            raise
        raise _fail("legacy_cleanup_bound_win32_cancellation_uncertain") from exc


def _delete_windows_directory(
    workspace_root: Path,
    path: Path,
    approved: _ApprovedDirectory,
) -> None:
    with _activity_group_bound_directory_chain(
        workspace_root,
        path.parent,
    ):
        handle = _windows_open(path, directory=True)
        failure: BaseException | None = None
        delete_marked = False
        committed = False
        original_link_count = 0
        try:
            _validate_windows_named_directory(path, approved)
            information = _windows_api().query(handle)
            original_link_count = information.link_count
            if original_link_count <= 0:
                raise _fail("legacy_cleanup_bound_win32_directory_link_uncertain")
            _validate_windows_directory_information(
                information,
                approved,
                expected_link_count=original_link_count,
            )
            _reject_windows_alternate_streams(handle, directory=True)
            _windows_api().set_disposition(handle, True)
            delete_marked = True
            pending = _windows_api().query(handle)
            _validate_windows_directory_information(
                pending,
                approved,
                expected_link_count=0,
            )
            _reject_windows_alternate_streams(handle, directory=True)
            committed = True
        except BaseException as exc:
            failure = exc
            if delete_marked and not committed:
                try:
                    _cancel_windows_directory_disposition(
                        handle,
                        path,
                        approved,
                        original_link_count,
                    )
                    delete_marked = False
                except BaseException as cancel_exc:
                    failure = cancel_exc

        try:
            _windows_close(handle)
        except LegacyCleanupBoundDeleteError as close_exc:
            failure = close_exc
        if failure is not None:
            if isinstance(failure, LegacyCleanupBoundDeleteError):
                raise failure
            raise _fail(
                "legacy_cleanup_bound_win32_directory_delete_uncertain"
            ) from failure
        if not committed or not _path_is_absent_no_follow(path):
            raise _fail("legacy_cleanup_bound_win32_directory_delete_unproved")


def _delete_exact_approved_file(
    workspace_root: Path | str,
    path: Path | str,
    expected: Mapping[str, Any],
) -> None:
    """Delete one exact approved regular file or raise content-free failure."""

    approved = _approved_file(expected)
    root, candidate = _validated_paths(workspace_root, path)
    try:
        if os.name == "nt":
            _delete_windows_file(root, candidate, approved)
        else:
            _delete_posix_file(root, candidate, approved)
    except LegacyCleanupBoundDeleteError:
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        raise _fail("legacy_cleanup_bound_file_delete_uncertain") from exc


def _delete_exact_approved_empty_directory(
    workspace_root: Path | str,
    path: Path | str,
    expected: Mapping[str, Any],
) -> None:
    """Delete one exact approved empty directory or fail without recursion."""

    approved = _approved_directory(expected)
    root, candidate = _validated_paths(workspace_root, path)
    try:
        if os.name == "nt":
            _delete_windows_directory(root, candidate, approved)
        else:
            _delete_posix_directory(root, candidate, approved)
    except LegacyCleanupBoundDeleteError:
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        raise _fail("legacy_cleanup_bound_directory_delete_uncertain") from exc


__all__ = [
    "LegacyCleanupBoundDeleteError",
]
