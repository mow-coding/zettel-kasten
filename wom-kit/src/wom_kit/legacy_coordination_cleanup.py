"""Fail-closed cleanup for one retired workspace-local coordination root.

The public results are deliberately content-free.  Exact paths, names, file
identities, and content hashes exist only in the private canonical plan whose
SHA-256 is presented for human approval.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from ._legacy_cleanup_fs import (
    BoundCleanupRoot,
    LegacyCleanupFilesystemError,
    bind_directory,
    bind_regular_file,
    bind_workspace_root,
    lstat_in_directory,
    open_exclusive_at_root,
    scan_directory,
    scan_root,
    stat_identity,
)
from .archive_services import (
    _compound_exact_human_approval_blocked,
    _activity_group_bound_directory_chain,
    safe_foreign_quarantine_actor_id,
)
from .legacy_cleanup_bound_delete import (
    _delete_exact_approved_empty_directory,
    _delete_exact_approved_file,
)
from .process_launch import noninteractive_creationflags


DEFAULT_LEGACY_COORDINATION_CLEANUP_MAX_FILES = 10_000
DEFAULT_LEGACY_COORDINATION_CLEANUP_MAX_BYTES = 1024 * 1024 * 1024

PLAN_SCHEMA = "wom-kit/legacy-coordination-cleanup-plan/v0.1"
RESULT_SCHEMA = "wom-kit/legacy-coordination-cleanup-result/v0.1"
TARGET_NAME = ".mow-harness"
LOCK_NAME = ".wom-legacy-coordination-cleanup.lock"
TOMBSTONE_PREFIX = ".wom-legacy-coordination-cleanup-tombstone-"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REPARSE_FLAG = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
MAX_WORKSPACE_ROOT_ENTRIES = 100_000
LEGACY_COORDINATION_CLEANUP_APPLY_SUPPORTED = os.name == "nt"

KNOWN_TOP_LEVEL_DIRECTORIES = {
    "source",
    "updates",
    "backups",
    "receipts",
    "tmp",
}
KNOWN_TOP_LEVEL_FILES = {
    "installed-version.txt",
    "source-url.txt",
    "update.log",
    "update.lock",
}
EVIDENCE_CATEGORIES = {"backups", "receipts"}


class _HardlinkEntryError(OSError):
    pass


class _DirectoryEntryLimitError(OSError):
    pass


class _AlternateDataStreamError(OSError):
    pass


class _FileSizeLimitError(OSError):
    pass


class _MountBoundaryError(OSError):
    pass


def _translate_mount_boundary_error(
    error: LegacyCleanupFilesystemError,
) -> None:
    if error.code in {
        "mount_boundary_entry",
        "mount_identity_unavailable",
        "workspace_root_mount_boundary",
    }:
        raise _MountBoundaryError(error.code) from error
    raise error


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _path_identifier(path: Path) -> str:
    normalized = os.path.normcase(os.path.abspath(str(path)))
    return _sha256_bytes(normalized.encode("utf-8", errors="surrogatepass"))


def _identity(info: os.stat_result) -> dict[str, int]:
    return {
        "device": int(info.st_dev),
        "inode": int(info.st_ino),
    }


def _is_reparse(info: os.stat_result) -> bool:
    return bool(
        stat.S_ISLNK(info.st_mode)
        or (
            REPARSE_FLAG
            and getattr(info, "st_file_attributes", 0) & REPARSE_FLAG
        )
    )


def _has_alternate_data_stream(
    path: Path,
    *,
    expected_identity: dict[str, int] | None = None,
) -> bool:
    """Return whether a Windows file or directory has a named NTFS stream."""

    if os.name != "nt":
        return False

    before = os.lstat(path)
    if (
        _is_reparse(before)
        or (
            expected_identity is not None
            and _identity(before) != expected_identity
        )
    ):
        raise OSError("legacy_cleanup_stream_entry_unsafe")

    import ctypes
    from ctypes import wintypes

    class Win32FindStreamData(ctypes.Structure):
        _fields_ = [
            ("stream_size", ctypes.c_longlong),
            ("stream_name", wintypes.WCHAR * (260 + 36)),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    find_first_stream = kernel32.FindFirstStreamW
    find_first_stream.argtypes = [
        wintypes.LPCWSTR,
        wintypes.INT,
        ctypes.POINTER(Win32FindStreamData),
        wintypes.DWORD,
    ]
    find_first_stream.restype = wintypes.HANDLE
    find_next_stream = kernel32.FindNextStreamW
    find_next_stream.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(Win32FindStreamData),
    ]
    find_next_stream.restype = wintypes.BOOL
    find_close = kernel32.FindClose
    find_close.argtypes = [wintypes.HANDLE]
    find_close.restype = wintypes.BOOL

    invalid_handle = wintypes.HANDLE(-1).value
    error_handle_eof = 38
    error_no_more_files = 18
    data = Win32FindStreamData()
    handle = find_first_stream(str(path), 0, ctypes.byref(data), 0)
    if handle == invalid_handle:
        error = ctypes.get_last_error()
        if error == error_handle_eof:
            after = os.lstat(path)
            if _is_reparse(after) or _identity(after) != _identity(before):
                raise OSError("legacy_cleanup_stream_entry_changed")
            return False
        raise ctypes.WinError(error)
    result = False
    try:
        while True:
            if str(data.stream_name) != "::$DATA":
                result = True
                break
            if not find_next_stream(handle, ctypes.byref(data)):
                error = ctypes.get_last_error()
                if error in {error_handle_eof, error_no_more_files}:
                    break
                raise ctypes.WinError(error)
    finally:
        find_close(handle)
    after = os.lstat(path)
    if _is_reparse(after) or _identity(after) != _identity(before):
        raise OSError("legacy_cleanup_stream_entry_changed")
    return result


def _path_exists_no_follow(path: Path) -> bool:
    try:
        os.lstat(path)
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return True


def _normalized_path_key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(str(path))))


def _account_profile_roots() -> tuple[set[str], bool]:
    """Return canonical profile roots, including one OS-account authority."""

    candidates: set[str] = set()
    authoritative_available = False
    if os.name == "nt":
        try:
            import ctypes
            import uuid
            from ctypes import wintypes

            class Guid(ctypes.Structure):
                _fields_ = [
                    ("data1", wintypes.DWORD),
                    ("data2", wintypes.WORD),
                    ("data3", wintypes.WORD),
                    ("data4", ctypes.c_ubyte * 8),
                ]

            raw = uuid.UUID("5e6c858f-0e22-4760-9afe-ea3317b67173").bytes_le
            profile_guid = Guid(
                int.from_bytes(raw[0:4], "little"),
                int.from_bytes(raw[4:6], "little"),
                int.from_bytes(raw[6:8], "little"),
                (ctypes.c_ubyte * 8)(*raw[8:16]),
            )
            value = ctypes.c_wchar_p()
            shell32 = ctypes.WinDLL("shell32", use_last_error=True)
            get_known_folder = shell32.SHGetKnownFolderPath
            get_known_folder.argtypes = [
                ctypes.POINTER(Guid),
                wintypes.DWORD,
                wintypes.HANDLE,
                ctypes.POINTER(ctypes.c_wchar_p),
            ]
            get_known_folder.restype = ctypes.c_long
            result = get_known_folder(
                ctypes.byref(profile_guid),
                0,
                None,
                ctypes.byref(value),
            )
            if result != 0 or not value.value:
                raise OSError("known profile lookup failed")
            try:
                candidates.add(
                    _normalized_path_key(Path(value.value).resolve(strict=True))
                )
                authoritative_available = True
            finally:
                ole32 = ctypes.WinDLL("ole32", use_last_error=True)
                ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
                ole32.CoTaskMemFree(value)
        except (OSError, RuntimeError, TypeError, ValueError):
            authoritative_available = False
    else:
        try:
            import pwd

            account_home = Path(pwd.getpwuid(os.getuid()).pw_dir)
            candidates.add(
                _normalized_path_key(account_home.resolve(strict=True))
            )
            authoritative_available = True
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            authoritative_available = False

    try:
        candidates.add(_normalized_path_key(Path.home().resolve(strict=True)))
    except (OSError, RuntimeError):
        pass
    return candidates, authoritative_available


def _validate_workspace_root_path(
    supplied_root: Path,
) -> tuple[Path, dict[str, Any], list[str]]:
    """Validate every lexical component before resolving a workspace root."""

    blockers: list[str] = []
    if not supplied_root.is_absolute():
        return supplied_root, {}, ["workspace_root_must_be_absolute"]
    if ".." in supplied_root.parts:
        return supplied_root, {}, ["workspace_root_ambiguous_component"]
    if supplied_root.name.casefold() == TARGET_NAME.casefold():
        return supplied_root, {}, ["workspace_root_cannot_be_legacy_target"]
    if os.name == "nt":
        supplied_text = str(supplied_root)
        drive = supplied_root.drive
        remainder = supplied_text[len(drive) :]
        if (
            drive.startswith("\\\\")
            or supplied_text.startswith(("\\\\?\\", "\\\\.\\"))
            or ":" in remainder
        ):
            return supplied_root, {}, ["workspace_root_namespace_unsafe"]

    normalized_root = Path(os.path.abspath(str(supplied_root)))
    observed_chain: list[tuple[Path, dict[str, int]]] = []
    try:
        parts = normalized_root.parts
        if not parts:
            raise OSError("workspace root has no absolute components")
        current = Path(parts[0])
        for part in parts[1:]:
            current = current / part
            info = os.lstat(current)
            if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
                raise OSError("workspace root path component is unsafe")
            observed_chain.append((current, _identity(info)))
        root_stat = os.lstat(normalized_root)
        if _is_reparse(root_stat) or not stat.S_ISDIR(root_stat.st_mode):
            raise OSError("workspace root is not a real directory")

        canonical_root = normalized_root.resolve(strict=True)
        canonical_stat = os.lstat(canonical_root)
        if (
            _is_reparse(canonical_stat)
            or not stat.S_ISDIR(canonical_stat.st_mode)
            or _identity(canonical_stat) != _identity(root_stat)
        ):
            raise OSError("workspace root resolution changed identity")

        for component, expected_identity in observed_chain:
            current_stat = os.lstat(component)
            if (
                _is_reparse(current_stat)
                or not stat.S_ISDIR(current_stat.st_mode)
                or _identity(current_stat) != expected_identity
            ):
                raise OSError("workspace root path component changed")

        canonical_key = _normalized_path_key(canonical_root)
        anchor_key = _normalized_path_key(Path(canonical_root.anchor))
        home_keys, account_home_known = _account_profile_roots()
        if not account_home_known:
            blockers.append("workspace_account_profile_unavailable")
        if canonical_key == anchor_key or canonical_key in home_keys:
            blockers.append("workspace_root_broad_or_protected")

        root_identity = {
            **_identity(canonical_stat),
            "mode": int(stat.S_IFMT(canonical_stat.st_mode)),
            "supplied_absolute_path": _normalized_path_key(normalized_root),
            "canonical_absolute_path": canonical_key,
        }
        return canonical_root, root_identity, blockers
    except OSError:
        return normalized_root, {}, ["workspace_root_path_component_unsafe"]


def _unique_codes(values: list[str]) -> list[str]:
    return sorted(set(values))


def _stream_regular_file_bound(
    workspace_root: Path,
    path: Path,
    *,
    max_bytes: int,
    capture_bytes: bool,
) -> tuple[bytes | None, os.stat_result, int, str]:
    """Stream one stable regular, single-link file without following links."""

    def consume(
        file_descriptor: int,
        before: os.stat_result,
        read_name_state: Any,
    ) -> tuple[bytes | None, os.stat_result, int, str]:
        opened = os.fstat(file_descriptor)
        if int(before.st_nlink) > 1:
            raise _HardlinkEntryError("legacy_cleanup_hardlink_entry")
        if int(opened.st_size) > max_bytes:
            raise _FileSizeLimitError("legacy_cleanup_file_size_limit")
        if (
            _is_reparse(before)
            or not stat.S_ISREG(before.st_mode)
            or not stat.S_ISREG(opened.st_mode)
            or _identity(before) != _identity(opened)
            # CPython's Windows descriptor stat can report zero links even
            # when the name-based Win32 stat correctly reports one.  The
            # bound, no-follow directory entry is the link-count authority.
            or int(before.st_nlink) not in {0, 1}
        ):
            raise OSError("legacy_cleanup_file_unsafe")
        chunks: list[bytes] | None = [] if capture_bytes else None
        digest = hashlib.sha256()
        total = 0
        remaining = max_bytes + 1
        while remaining:
            chunk = os.read(file_descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            digest.update(chunk)
            if chunks is not None:
                chunks.append(chunk)
            total += len(chunk)
            remaining -= len(chunk)
        if total > max_bytes:
            raise _FileSizeLimitError("legacy_cleanup_file_size_limit")
        if total != int(opened.st_size):
            raise OSError("legacy_cleanup_file_size_changed")
        after_open = os.fstat(file_descriptor)
        after_name = read_name_state()
        if (
            _identity(after_open) != _identity(opened)
            or _identity(after_name) != _identity(opened)
            or int(after_open.st_size) != int(opened.st_size)
            or int(after_name.st_size) != int(opened.st_size)
            or int(after_name.st_nlink) not in {0, 1}
            or int(after_open.st_mtime_ns) != int(opened.st_mtime_ns)
            or int(after_name.st_mtime_ns) != int(opened.st_mtime_ns)
            or _is_reparse(after_name)
        ):
            raise OSError("legacy_cleanup_file_changed_while_reading")
        return (
            b"".join(chunks) if chunks is not None else None,
            opened,
            total,
            digest.hexdigest(),
        )

    if os.name != "nt":
        try:
            relative_parent = path.parent.relative_to(workspace_root)
            if not relative_parent.parts:
                raise OSError("legacy_cleanup_root_file_unsupported")
            with bind_workspace_root(workspace_root) as root_binding:
                with bind_directory(
                    root_binding,
                    PurePosixPath(relative_parent.as_posix()),
                ) as directory_binding:
                    before = lstat_in_directory(directory_binding, path.name)
                    with bind_regular_file(
                        directory_binding,
                        path.name,
                    ) as file_binding:
                        return consume(
                            file_binding.descriptor,
                            before,
                            lambda: lstat_in_directory(
                                directory_binding,
                                path.name,
                            ),
                        )
        except LegacyCleanupFilesystemError as exc:
            _translate_mount_boundary_error(exc)

    with _activity_group_bound_directory_chain(
        workspace_root,
        path.parent,
    ) as binding:
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        before = os.lstat(path)
        file_descriptor = os.open(path, flags)
        try:
            return consume(
                file_descriptor,
                before,
                lambda: os.lstat(path),
            )
        finally:
            os.close(file_descriptor)


def _read_regular_file_bound(
    workspace_root: Path,
    path: Path,
    *,
    max_bytes: int,
) -> tuple[bytes, os.stat_result]:
    raw, info, _size, _sha256 = _stream_regular_file_bound(
        workspace_root,
        path,
        max_bytes=max_bytes,
        capture_bytes=True,
    )
    if raw is None:
        raise OSError("legacy_cleanup_file_capture_failed")
    return raw, info


def _list_directory_bound(
    workspace_root: Path,
    directory: Path,
    *,
    max_entries: int | None = None,
    reject_alternate_streams: bool = False,
) -> tuple[os.stat_result, list[tuple[str, os.stat_result]]]:
    if os.name != "nt":
        try:
            relative = directory.relative_to(workspace_root)
            with bind_workspace_root(workspace_root) as root_binding:
                if relative.parts:
                    with bind_directory(
                        root_binding,
                        PurePosixPath(relative.as_posix()),
                    ) as directory_binding:
                        observed = scan_directory(
                            directory_binding,
                            max_entries=(
                                max_entries
                                if max_entries is not None
                                else MAX_WORKSPACE_ROOT_ENTRIES
                            ),
                        )
                        info = os.fstat(directory_binding.descriptor)
                else:
                    observed = scan_root(
                        root_binding,
                        max_entries=(
                            max_entries
                            if max_entries is not None
                            else MAX_WORKSPACE_ROOT_ENTRIES
                        ),
                    )
                    info = os.fstat(root_binding.descriptor)
                return info, observed
        except LegacyCleanupFilesystemError as exc:
            if exc.code == "legacy_cleanup_directory_entry_limit_exceeded":
                raise _DirectoryEntryLimitError(exc.code) from exc
            _translate_mount_boundary_error(exc)

    with _activity_group_bound_directory_chain(
        workspace_root,
        directory,
    ) as binding:
        descriptor = binding.get("descriptor")
        before = os.lstat(directory)
        if _is_reparse(before) or not stat.S_ISDIR(before.st_mode):
            raise OSError("legacy_cleanup_directory_unsafe")
        if reject_alternate_streams and _has_alternate_data_stream(
            directory,
            expected_identity=_identity(before),
        ):
            raise _AlternateDataStreamError(
                "legacy_cleanup_alternate_data_stream_entry"
            )
        scan_target: int | Path = (
            descriptor if isinstance(descriptor, int) else directory
        )
        observed: list[tuple[str, os.stat_result]] = []
        with os.scandir(scan_target) as entries:
            for entry in entries:
                if max_entries is not None and len(observed) >= max_entries:
                    raise _DirectoryEntryLimitError(
                        "legacy_cleanup_directory_entry_limit_exceeded"
                    )
                observed.append(
                    (entry.name, entry.stat(follow_symlinks=False))
                )
        after = os.lstat(directory)
        if (
            _identity(before) != _identity(after)
            or _is_reparse(after)
            or not stat.S_ISDIR(after.st_mode)
        ):
            raise OSError("legacy_cleanup_directory_changed")
        observed.sort(key=lambda item: (item[0].casefold(), item[0]))
        return after, observed


def _category_for(logical_relative: str) -> str:
    parts = PurePosixPath(logical_relative).parts
    if len(parts) < 2:
        return "target"
    first = parts[1]
    if first in KNOWN_TOP_LEVEL_DIRECTORIES:
        return first
    if first in KNOWN_TOP_LEVEL_FILES:
        return "metadata"
    return "unknown"


def _scan_target_tree(
    workspace_root: Path,
    target: Path,
    *,
    max_files: int,
    max_bytes: int,
) -> dict[str, Any]:
    blockers: list[str] = []
    records: list[dict[str, Any]] = []
    expected_children: dict[str, list[dict[str, Any]]] = {}
    directory_paths: dict[str, Path] = {}
    pending: list[tuple[Path, str]] = [(target, TARGET_NAME)]
    entry_count = 0
    file_count = 0
    directory_count = 0
    total_bytes = 0
    category_counts: dict[str, int] = {}
    category_bytes: dict[str, int] = {}
    evidence_present = False

    while pending and not any(
        code in blockers
        for code in ("max_files_exceeded", "max_bytes_exceeded")
    ):
        directory, logical_relative = pending.pop()
        try:
            directory_stat, children = _list_directory_bound(
                workspace_root,
                directory,
                max_entries=max_files - entry_count,
                reject_alternate_streams=True,
            )
        except _AlternateDataStreamError:
            blockers.append("alternate_data_stream_entry")
            continue
        except _MountBoundaryError:
            blockers.append("cross_mount_entry")
            continue
        except _DirectoryEntryLimitError:
            blockers.append("max_files_exceeded")
            break
        except (OSError, RuntimeError, ValueError):
            blockers.append("unsafe_or_unreadable_directory")
            continue

        directory_count += 1
        directory_paths[logical_relative] = directory
        child_set: list[dict[str, Any]] = []
        for name, child_stat in children:
            entry_count += 1
            if entry_count > max_files:
                blockers.append("max_files_exceeded")
                break
            child_relative = (
                PurePosixPath(logical_relative) / name
            ).as_posix()
            protected_collab = name.casefold() == "collab"
            nested_git_marker = name.casefold() == ".git"
            stop_at_entry = protected_collab or nested_git_marker
            if protected_collab:
                blockers.append("collab_present_in_target")
            if nested_git_marker:
                # A repository nested anywhere inside the retired tree has its
                # own index and may contain tracked user data.  Treat only the
                # marker's name/type as evidence; never traverse or read it.
                blockers.append("nested_git_repository_present")
            if logical_relative == TARGET_NAME and not protected_collab:
                exact_known = (
                    name in KNOWN_TOP_LEVEL_DIRECTORIES
                    or name in KNOWN_TOP_LEVEL_FILES
                )
                casefold_known = name.casefold() in {
                    item.casefold()
                    for item in (
                        KNOWN_TOP_LEVEL_DIRECTORIES
                        | KNOWN_TOP_LEVEL_FILES
                    )
                }
                if not exact_known:
                    blockers.append(
                        "top_level_name_case_mismatch"
                        if casefold_known
                        else "unknown_top_level_entry"
                    )
                    stop_at_entry = True

            if _is_reparse(child_stat):
                blockers.append("symlink_or_reparse_entry")
                child_kind = "reparse"
            elif stat.S_ISDIR(child_stat.st_mode):
                child_kind = "directory"
            elif stat.S_ISREG(child_stat.st_mode):
                child_kind = "file"
            else:
                blockers.append("special_entry")
                child_kind = "special"
            child_set.append(
                {
                    "name": name,
                    "type": child_kind,
                    "identity": _identity(child_stat),
                }
            )

            category = _category_for(child_relative)
            if logical_relative == TARGET_NAME:
                if name in KNOWN_TOP_LEVEL_DIRECTORIES and child_kind != "directory":
                    blockers.append("known_entry_type_mismatch")
                    stop_at_entry = True
                if name in KNOWN_TOP_LEVEL_FILES and child_kind != "file":
                    blockers.append("known_entry_type_mismatch")
                    stop_at_entry = True
                if name in EVIDENCE_CATEGORIES:
                    evidence_present = True

            # Protected collaboration history and unrecognized/mismatched
            # top-level entries are boundary evidence only.  Record their
            # direct name/type/identity so the plan fails closed, but never
            # descend into them or open their contents.
            if stop_at_entry:
                continue

            # Never ask a path-based stream API about a link/reparse/special
            # entry; doing so could follow it outside the reviewed tree.
            if child_kind not in {"directory", "file"}:
                continue

            try:
                if _has_alternate_data_stream(
                    directory / name,
                    expected_identity=(
                        _identity(child_stat)
                        if int(child_stat.st_ino) != 0
                        else None
                    ),
                ):
                    blockers.append("alternate_data_stream_entry")
                    continue
            except OSError:
                blockers.append("unsafe_modified_or_unreadable_entry")
                continue

            if child_kind == "directory":
                pending.append((directory / name, child_relative))
                continue
            if child_kind != "file":
                continue
            # os.scandir(directory_fd) reports st_nlink=0 for ordinary files
            # on Windows.  Zero means "not reported" here; the subsequent
            # bound name-based read is authoritative and rejects >1.
            if int(child_stat.st_nlink) > 1:
                blockers.append("hardlink_entry")
                continue
            file_size = int(child_stat.st_size)
            if total_bytes + file_size > max_bytes:
                blockers.append("max_bytes_exceeded")
                break
            try:
                _raw, stable_stat, stable_size, stable_sha256 = (
                    _stream_regular_file_bound(
                        workspace_root,
                        directory / name,
                        max_bytes=max_bytes - total_bytes,
                        capture_bytes=False,
                    )
                )
            except _HardlinkEntryError:
                blockers.append("hardlink_entry")
                continue
            except _FileSizeLimitError:
                blockers.append("max_bytes_exceeded")
                break
            except _MountBoundaryError:
                blockers.append("cross_mount_entry")
                continue
            except (OSError, RuntimeError, ValueError):
                blockers.append("unsafe_modified_or_unreadable_file")
                continue
            scanned_identity = _identity(child_stat)
            if (
                scanned_identity["inode"] != 0
                and _identity(stable_stat) != scanned_identity
            ):
                blockers.append("file_identity_drift")
                continue
            total_bytes += stable_size
            file_count += 1
            category_counts[category] = category_counts.get(category, 0) + 1
            category_bytes[category] = (
                category_bytes.get(category, 0) + stable_size
            )
            records.append(
                {
                    "relative_path": child_relative,
                    "type": "file",
                    "size": stable_size,
                    "sha256": stable_sha256,
                    "identity": _identity(stable_stat),
                    "mtime_ns": int(stable_stat.st_mtime_ns),
                    "category": category,
                }
            )
        expected_children[logical_relative] = child_set

    for logical_relative, directory in sorted(directory_paths.items()):
        try:
            directory_stat, current_children = _list_directory_bound(
                workspace_root,
                directory,
                max_entries=len(expected_children.get(logical_relative, [])),
                reject_alternate_streams=True,
            )
        except _AlternateDataStreamError:
            blockers.append("alternate_data_stream_entry")
            continue
        except _DirectoryEntryLimitError:
            blockers.append("directory_child_set_drift")
            continue
        except (OSError, RuntimeError, ValueError):
            blockers.append("directory_drift")
            continue
        current_child_set = []
        for name, info in current_children:
            kind = (
                "reparse"
                if _is_reparse(info)
                else "directory"
                if stat.S_ISDIR(info.st_mode)
                else "file"
                if stat.S_ISREG(info.st_mode)
                else "special"
            )
            current_child_set.append(
                {"name": name, "type": kind, "identity": _identity(info)}
            )
        expected = expected_children.get(logical_relative, [])
        if current_child_set != expected:
            blockers.append("directory_child_set_drift")
        child_set_sha256 = _sha256_bytes(_canonical_bytes(expected))
        records.append(
            {
                "relative_path": logical_relative,
                "type": "directory",
                "size": 0,
                "sha256": child_set_sha256,
                "identity": _identity(directory_stat),
                "mtime_ns": int(directory_stat.st_mtime_ns),
                "category": _category_for(logical_relative),
                "child_set_sha256": child_set_sha256,
            }
        )

    records.sort(key=lambda item: item["relative_path"])
    return {
        "records": records,
        "blockers": _unique_codes(blockers),
        "summary": {
            "file_count": file_count,
            "directory_count": directory_count,
            "total_bytes": total_bytes,
            "category_counts": dict(sorted(category_counts.items())),
            "category_bytes": dict(sorted(category_bytes.items())),
            "backups_or_receipts_present": evidence_present,
        },
    }


def _workspace_target_name_state(
    workspace_root: Path,
    *,
    owned_lock_record: dict[str, Any] | None,
) -> tuple[Path, list[str], bool]:
    target = workspace_root / TARGET_NAME
    blockers: list[str] = []
    try:
        _root_stat, entries = _list_directory_bound(
            workspace_root,
            workspace_root,
            max_entries=MAX_WORKSPACE_ROOT_ENTRIES,
        )
    except _DirectoryEntryLimitError:
        return target, ["workspace_root_entry_limit_exceeded"], False
    except (OSError, RuntimeError, ValueError):
        return target, ["workspace_root_unreadable"], False
    for name, info in entries:
        folded = name.casefold()
        if folded == LOCK_NAME.casefold():
            observed_lock_identity = _identity(info)
            owned_lock_shape = (
                owned_lock_record is not None
                and name == LOCK_NAME
                and stat.S_ISREG(info.st_mode)
                and not _is_reparse(info)
                and (
                    observed_lock_identity == owned_lock_record.get("identity")
                    or (
                        os.name == "nt"
                        and observed_lock_identity["inode"] == 0
                    )
                )
                and int(info.st_size) == owned_lock_record.get("size")
                and int(info.st_mtime_ns) == owned_lock_record.get("mtime_ns")
                and int(info.st_nlink) in (
                    {0, 1} if os.name == "nt" else {1}
                )
            )
            if owned_lock_shape:
                try:
                    owned_lock_shape = not _has_alternate_data_stream(
                        workspace_root / name,
                        expected_identity=owned_lock_record.get("identity"),
                    )
                except OSError:
                    owned_lock_shape = False
            if not owned_lock_shape:
                blockers.append("cleanup_lock_present")
        if folded.startswith(TOMBSTONE_PREFIX.casefold()):
            blockers.append("prior_cleanup_tombstone_present")
    matches = [name for name, _info in entries if name.casefold() == TARGET_NAME]
    exact = [name for name in matches if name == TARGET_NAME]
    if len(matches) > 1:
        blockers.append("target_name_collision")
    elif matches and not exact:
        blockers.append("target_name_case_mismatch")
    return target, blockers, bool(exact)


def _git_tracking_blockers(workspace_root: Path, target_present: bool) -> list[str]:
    if not target_present:
        return []
    repository_selector_names = {
        "GIT_COMMON_DIR",
        "GIT_DIR",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_WORK_TREE",
    }
    if any(name in os.environ for name in repository_selector_names):
        return ["git_tracking_environment_unsafe"]
    repository_roots: list[Path] = []
    current = workspace_root
    while True:
        marker = current / ".git"
        if _path_exists_no_follow(marker):
            try:
                marker_info = os.lstat(marker)
            except OSError:
                return ["git_tracking_check_failed"]
            if (
                _is_reparse(marker_info)
                or not (
                    stat.S_ISDIR(marker_info.st_mode)
                    or stat.S_ISREG(marker_info.st_mode)
                )
            ):
                return ["git_tracking_check_failed"]
            repository_roots.append(current)
        if current.parent == current:
            break
        current = current.parent
    if not repository_roots:
        return []
    # Repository-selection variables inherited from the caller must not be
    # allowed to redirect this destructive safety check to another index.
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    target = workspace_root / TARGET_NAME
    for repository_root in repository_roots:
        try:
            inside = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repository_root),
                    "rev-parse",
                    "--is-inside-work-tree",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=environment,
                timeout=10,
                check=False,
                creationflags=noninteractive_creationflags(),
            )
            top_level = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repository_root),
                    "rev-parse",
                    "--show-toplevel",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=environment,
                timeout=10,
                check=False,
                creationflags=noninteractive_creationflags(),
            )
        except (OSError, subprocess.SubprocessError):
            return ["git_tracking_check_failed"]
        if (
            inside.returncode != 0
            or inside.stdout.strip() != b"true"
            or top_level.returncode != 0
        ):
            return ["git_tracking_check_failed"]
        try:
            rendered_top = os.fsdecode(top_level.stdout).rstrip("\r\n")
            if not rendered_top or "\n" in rendered_top or "\r" in rendered_top:
                raise ValueError("ambiguous Git top-level output")
            observed_top = Path(rendered_top).resolve(strict=True)
            expected_top = repository_root.resolve(strict=True)
            if _normalized_path_key(observed_top) != _normalized_path_key(
                expected_top
            ):
                raise ValueError("Git worktree root mismatch")
            pathspec = target.relative_to(expected_top).as_posix()
        except (OSError, RuntimeError, ValueError):
            return ["git_tracking_check_failed"]
        try:
            tracked = subprocess.run(
                [
                    "git",
                    "-C",
                    str(expected_top),
                    "--literal-pathspecs",
                    "ls-files",
                    "-z",
                    "--",
                    pathspec,
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=environment,
                timeout=10,
                check=False,
                creationflags=noninteractive_creationflags(),
            )
        except (OSError, subprocess.SubprocessError):
            return ["git_tracking_check_failed"]
        if tracked.returncode != 0:
            return ["git_tracking_check_failed"]
        if tracked.stdout:
            return ["git_tracked_target"]
    return []


def _host_identity(
    workspace_root: Path,
) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    archive_root = workspace_root / "archive"
    archive_config = archive_root / "archive.yml"
    archive_identity = archive_root / "archive-identity.yml"
    try:
        archive_stat = os.lstat(archive_root)
        if _is_reparse(archive_stat) or not stat.S_ISDIR(archive_stat.st_mode):
            raise OSError("unsafe archive root")
        config_raw, _config_stat = _read_regular_file_bound(
            workspace_root,
            archive_config,
            max_bytes=4 * 1024 * 1024,
        )
        identity_raw, _identity_stat = _read_regular_file_bound(
            workspace_root,
            archive_identity,
            max_bytes=4 * 1024 * 1024,
        )
        config_doc = yaml.safe_load(config_raw.decode("utf-8"))
        identity_doc = yaml.safe_load(identity_raw.decode("utf-8"))
        archive_id = config_doc.get("archive_id") if isinstance(config_doc, dict) else None
        identity_section = (
            identity_doc.get("identity")
            if isinstance(identity_doc, dict)
            else None
        )
        identity_archive_id = (
            identity_section.get("archive_id")
            if isinstance(identity_section, dict)
            else None
        )
        if (
            not isinstance(archive_id, str)
            or not archive_id.strip()
            or identity_archive_id != archive_id
        ):
            blockers.append("workspace_host_identity_invalid")
        return {
            "archive_config_sha256": _sha256_bytes(config_raw),
            "archive_identity_sha256": _sha256_bytes(identity_raw),
            "archive_id_sha256": _sha256_bytes(
                str(archive_id or "").encode("utf-8")
            ),
        }, blockers
    except (
        OSError,
        UnicodeError,
        yaml.YAMLError,
        AttributeError,
        TypeError,
        ValueError,
    ):
        return {}, ["workspace_host_identity_missing_or_unreadable"]


def _build_private_plan(
    workspace_root: Path | str,
    *,
    max_files: int,
    max_bytes: int,
    owned_lock_record: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    supplied_root = Path(workspace_root)
    target_for_hash = supplied_root / TARGET_NAME
    blockers: list[str] = []
    root_identity: dict[str, Any] = {}
    host_identity: dict[str, Any] = {}
    target_present = False
    tree = {
        "records": [],
        "summary": {
            "file_count": 0,
            "directory_count": 0,
            "total_bytes": 0,
            "category_counts": {},
            "category_bytes": {},
            "backups_or_receipts_present": False,
        },
        "blockers": [],
    }

    if not isinstance(max_files, int) or isinstance(max_files, bool) or max_files < 1:
        blockers.append("max_files_invalid")
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes < 0:
        blockers.append("max_bytes_invalid")
    normalized_root, root_identity, root_blockers = _validate_workspace_root_path(
        supplied_root
    )
    blockers.extend(root_blockers)
    if supplied_root.is_absolute():
        target_for_hash = Path(os.path.abspath(str(supplied_root))) / TARGET_NAME

    if not blockers:
        host_identity, host_blockers = _host_identity(normalized_root)
        blockers.extend(host_blockers)
    if not blockers:
        target, name_blockers, target_present = _workspace_target_name_state(
            normalized_root,
            owned_lock_record=owned_lock_record,
        )
        blockers.extend(name_blockers)
        if target_present and not name_blockers:
            tree = _scan_target_tree(
                normalized_root,
                target,
                max_files=max_files,
                max_bytes=max_bytes,
            )
            blockers.extend(tree["blockers"])
            blockers.extend(_git_tracking_blockers(normalized_root, True))

    private_plan = {
        "schema": PLAN_SCHEMA,
        "policy_version": 1,
        "workspace_root_identity": root_identity,
        "host_identity": host_identity,
        "target_relative_path": TARGET_NAME,
        "target_present": target_present,
        "target_records": tree["records"],
        "summary": tree["summary"],
        "limits": {
            "max_files": max_files,
            "max_bytes": max_bytes,
            "max_workspace_root_entries": MAX_WORKSPACE_ROOT_ENTRIES,
        },
        "blockers": _unique_codes(blockers),
    }
    plan_sha256 = hashlib.sha256(_canonical_bytes(private_plan)).hexdigest()
    root_identity_sha256 = _sha256_bytes(
        _canonical_bytes(
            {
                "workspace_root_identity": root_identity,
                "host_identity": host_identity,
            }
        )
    )
    public = {
        "schema": PLAN_SCHEMA,
        "ok": not private_plan["blockers"],
        "action": "legacy_coordination_cleanup_plan",
        "status": (
            "blocked"
            if private_plan["blockers"]
            else "ready"
            if target_present
            else "target_absent"
        ),
        "dry_run": True,
        "approval_platform_supported": (
            LEGACY_COORDINATION_CLEANUP_APPLY_SUPPORTED
        ),
        "approval_supported_platforms": ["windows"],
        "safe_to_cleanup": bool(
            LEGACY_COORDINATION_CLEANUP_APPLY_SUPPORTED
            and target_present
            and not private_plan["blockers"]
        ),
        "target_present": target_present,
        "plan_sha256": plan_sha256,
        "target_path_sha256": _path_identifier(target_for_hash),
        "root_identity_sha256": root_identity_sha256,
        "summary": tree["summary"],
        "blockers": private_plan["blockers"],
        "privacy": {
            "absolute_paths_echoed": False,
            "filenames_echoed": False,
            "file_contents_echoed": False,
        },
    }
    return private_plan, public


def legacy_coordination_cleanup_plan(
    workspace_root: Path | str,
    *,
    max_files: int,
    max_bytes: int,
) -> dict[str, Any]:
    """Return a privacy-safe, digest-bound preview for one exact target."""

    _private, public = _build_private_plan(
        workspace_root,
        max_files=max_files,
        max_bytes=max_bytes,
    )
    return public


def _result_from_plan(
    plan: dict[str, Any],
    *,
    dry_run: bool,
    status: str,
    blockers: list[str],
    changed: bool,
    remaining_tombstone_id: str | None = None,
    residue: dict[str, bool] | None = None,
) -> dict[str, Any]:
    return {
        **plan,
        "schema": RESULT_SCHEMA,
        "ok": not blockers and status in {
            "dry_run_ready",
            "target_absent",
            "cleanup_completed",
        },
        "action": "legacy_coordination_cleanup",
        "status": status,
        "dry_run": dry_run,
        "safe_to_cleanup": bool(
            plan.get("approval_platform_supported")
            and plan.get("target_present")
            and not blockers
            and dry_run
        ),
        "blockers": _unique_codes(blockers),
        "changed": changed,
        "remaining_tombstone_id": remaining_tombstone_id,
        "residue": residue
        or {
            "target_present": bool(plan.get("target_present")),
            "tombstone_present": False,
            "lock_present": False,
        },
    }


def _acquire_lock(
    workspace: BoundCleanupRoot,
    lock_path: Path,
) -> tuple[int, dict[str, Any]]:
    descriptor = open_exclusive_at_root(workspace, LOCK_NAME, mode=0o600)
    token = secrets.token_bytes(32)
    try:
        if os.write(descriptor, token) != len(token):
            raise OSError("legacy_cleanup_lock_short_write")
        os.fsync(descriptor)
        info = os.fstat(descriptor)
        named = os.lstat(lock_path)
        if (
            not stat.S_ISREG(info.st_mode)
            or not stat.S_ISREG(named.st_mode)
            or _is_reparse(named)
            or _identity(info) != _identity(named)
            or int(info.st_size) != len(token)
            or int(named.st_size) != len(token)
            or int(named.st_nlink) != 1
            or int(info.st_mtime_ns) != int(named.st_mtime_ns)
            or _has_alternate_data_stream(
                lock_path,
                expected_identity=_identity(info),
            )
        ):
            raise OSError("legacy_cleanup_lock_unsafe")
        return descriptor, {
            "type": "file",
            "identity": _identity(info),
            "size": len(token),
            "mtime_ns": int(info.st_mtime_ns),
            "sha256": _sha256_bytes(token),
        }
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        # A failed acquisition deliberately leaves the entry in place.  Once
        # the retained descriptor is gone, a path-based cleanup attempt could
        # remove a foreign replacement.  Residue is safer than deleting an
        # entry whose ownership can no longer be proved.
        raise


def _release_lock(
    workspace_root: Path,
    lock_path: Path,
    descriptor: int | None,
    expected_record: dict[str, Any] | None,
) -> bool:
    # A caller that did not acquire the lock has no authority to touch it.
    if descriptor is None or expected_record is None:
        return True
    try:
        os.close(descriptor)
    except OSError:
        return False
    try:
        _delete_exact_approved_file(
            workspace_root,
            lock_path,
            expected_record,
        )
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _cleanup_residue_state(
    workspace_root: BoundCleanupRoot,
) -> tuple[dict[str, bool], bool]:
    try:
        entries = scan_root(
            workspace_root,
            max_entries=MAX_WORKSPACE_ROOT_ENTRIES,
        )
    except (OSError, RuntimeError, ValueError):
        return {
            "target_present": True,
            "tombstone_present": True,
            "lock_present": True,
        }, False
    folded_names = [name.casefold() for name, _info in entries]
    return {
        "target_present": TARGET_NAME.casefold() in folded_names,
        "tombstone_present": any(
            name.startswith(TOMBSTONE_PREFIX.casefold())
            for name in folded_names
        ),
        "lock_present": LOCK_NAME.casefold() in folded_names,
    }, True


def _target_path_for_relative(target: Path, relative_path: str) -> Path:
    parts = PurePosixPath(relative_path).parts
    if not parts or parts[0] != TARGET_NAME:
        raise OSError("legacy_cleanup_relative_path_invalid")
    return target.joinpath(*parts[1:])


def _unlink_verified_file(
    workspace_root: Path,
    path: Path,
    expected: dict[str, Any],
) -> None:
    _delete_exact_approved_file(workspace_root, path, expected)


def _remove_verified_empty_directory(
    workspace_root: Path,
    path: Path,
    expected: dict[str, Any],
) -> None:
    _delete_exact_approved_empty_directory(workspace_root, path, expected)


def legacy_coordination_cleanup(
    workspace_root: Path | str,
    *,
    dry_run: bool = False,
    approve: bool = False,
    reviewed_by: str | None,
    expected_plan_sha256: str | None,
    affirm_workspace_owner_authorized: bool,
    affirm_external_writers_quiescent: bool,
    affirm_retired_state_disposable: bool,
    affirm_backups_and_receipts_disposable: bool,
    max_files: int,
    max_bytes: int,
) -> dict[str, Any]:
    """Preview or remove exactly one fully reviewed retired-state directory."""

    if type(dry_run) is not bool or type(approve) is not bool or approve:
        return _compound_exact_human_approval_blocked(
            lifecycle_action="legacy_coordination_cleanup",
        )

    return _legacy_coordination_cleanup_legacy_core(
        workspace_root,
        dry_run=dry_run,
        approve=approve,
        reviewed_by=reviewed_by,
        expected_plan_sha256=expected_plan_sha256,
        affirm_workspace_owner_authorized=affirm_workspace_owner_authorized,
        affirm_external_writers_quiescent=affirm_external_writers_quiescent,
        affirm_retired_state_disposable=affirm_retired_state_disposable,
        affirm_backups_and_receipts_disposable=(
            affirm_backups_and_receipts_disposable
        ),
        max_files=max_files,
        max_bytes=max_bytes,
    )


def _legacy_coordination_cleanup_legacy_core(
    workspace_root: Path | str,
    *,
    dry_run: bool = False,
    approve: bool = False,
    reviewed_by: str | None,
    expected_plan_sha256: str | None,
    affirm_workspace_owner_authorized: bool,
    affirm_external_writers_quiescent: bool,
    affirm_retired_state_disposable: bool,
    affirm_backups_and_receipts_disposable: bool,
    max_files: int,
    max_bytes: int,
) -> dict[str, Any]:
    """Exercise the pre-v0.4 cleanup in bounded historical tests only."""

    private_plan, public_plan = _build_private_plan(
        workspace_root,
        max_files=max_files,
        max_bytes=max_bytes,
    )
    blockers = list(public_plan["blockers"])

    approval_values_present = bool(
        approve
        or reviewed_by
        or expected_plan_sha256
        or affirm_workspace_owner_authorized
        or affirm_external_writers_quiescent
        or affirm_retired_state_disposable
        or affirm_backups_and_receipts_disposable
    )
    if dry_run:
        if approval_values_present:
            blockers.append("approval_fields_only_valid_for_apply")
        status = (
            "blocked"
            if blockers
            else "dry_run_ready"
            if public_plan["target_present"]
            else "target_absent"
        )
        return _result_from_plan(
            public_plan,
            dry_run=True,
            status=status,
            blockers=blockers,
            changed=False,
        )

    if not public_plan["target_present"] and not blockers:
        return _result_from_plan(
            public_plan,
            dry_run=False,
            status="target_absent",
            blockers=[],
            changed=False,
            residue={
                "target_present": False,
                "tombstone_present": False,
                "lock_present": False,
            },
        )
    if not approve:
        blockers.append("approve_required")
    if safe_foreign_quarantine_actor_id(reviewed_by) is None:
        blockers.append("safe_reviewer_required")
    if not isinstance(expected_plan_sha256, str) or not SHA256_RE.fullmatch(
        expected_plan_sha256
    ):
        blockers.append("expected_plan_sha256_invalid")
    elif expected_plan_sha256 != public_plan["plan_sha256"]:
        blockers.append("expected_plan_sha256_mismatch")
    if not affirm_workspace_owner_authorized:
        blockers.append("workspace_owner_authorization_required")
    if not affirm_external_writers_quiescent:
        blockers.append("external_writers_quiescence_required")
    if not affirm_retired_state_disposable:
        blockers.append("retired_state_disposable_affirmation_required")
    if (
        public_plan["summary"]["backups_or_receipts_present"]
        and not affirm_backups_and_receipts_disposable
    ):
        blockers.append("backups_and_receipts_disposable_affirmation_required")
    if not LEGACY_COORDINATION_CLEANUP_APPLY_SUPPORTED:
        blockers.append("cleanup_apply_platform_unsupported")
    if blockers:
        return _result_from_plan(
            public_plan,
            dry_run=False,
            status="blocked",
            blockers=blockers,
            changed=False,
        )

    root, root_identity, root_validation_blockers = _validate_workspace_root_path(
        Path(workspace_root)
    )
    if root_validation_blockers:
        return _result_from_plan(
            public_plan,
            dry_run=False,
            status="blocked",
            blockers=["workspace_root_changed_after_approval"],
            changed=False,
        )
    target = root / TARGET_NAME
    lock_path = root / LOCK_NAME
    lock_descriptor: int | None = None
    lock_record: dict[str, Any] | None = None
    changed = False
    execution_blockers: list[str] = []
    residue = {
        "target_present": True,
        "tombstone_present": True,
        "lock_present": True,
    }
    residue_known = False
    try:
        with bind_workspace_root(root) as bound_root:
            expected_root_identity = (
                int(root_identity["device"]),
                int(root_identity["inode"]),
            )
            if (
                bound_root.identity != expected_root_identity
                or stat_identity(os.lstat(root)) != expected_root_identity
            ):
                execution_blockers.append("workspace_root_changed_after_approval")
            else:
                try:
                    lock_descriptor, lock_record = _acquire_lock(
                        bound_root,
                        lock_path,
                    )
                except OSError:
                    execution_blockers.append("cleanup_lock_occupied_or_unsafe")
                else:
                    try:
                        locked_private, locked_public = _build_private_plan(
                            workspace_root,
                            max_files=max_files,
                            max_bytes=max_bytes,
                            owned_lock_record=lock_record,
                        )
                        if (
                            locked_public["plan_sha256"]
                            != public_plan["plan_sha256"]
                            or _canonical_bytes(locked_private)
                            != _canonical_bytes(private_plan)
                            or locked_public["blockers"]
                        ):
                            execution_blockers.append("full_replan_drift")
                        else:
                            pre_delete_git_blockers = _git_tracking_blockers(
                                root,
                                True,
                            )
                            if pre_delete_git_blockers:
                                execution_blockers.extend(pre_delete_git_blockers)
                                raise OSError("legacy_cleanup_git_state_changed")

                            final_scan = _scan_target_tree(
                                root,
                                target,
                                max_files=max_files,
                                max_bytes=max_bytes,
                            )
                            if (
                                final_scan["blockers"]
                                or _canonical_bytes(final_scan["records"])
                                != _canonical_bytes(
                                    private_plan["target_records"]
                                )
                            ):
                                raise OSError("legacy_cleanup_final_tree_drift")

                            file_records = sorted(
                                (
                                    record
                                    for record in private_plan["target_records"]
                                    if record.get("type") == "file"
                                ),
                                key=lambda item: item["relative_path"],
                            )
                            for record in file_records:
                                # A retained-handle helper can fail after the OS
                                # accepted a delete disposition.  From this
                                # point onward report possible mutation
                                # conservatively even if the helper raises.
                                changed = True
                                _unlink_verified_file(
                                    root,
                                    _target_path_for_relative(
                                        target,
                                        record["relative_path"],
                                    ),
                                    record,
                                )
                            directory_records = sorted(
                                (
                                    record
                                    for record in private_plan["target_records"]
                                    if record.get("type") == "directory"
                                ),
                                key=lambda item: (
                                    -len(
                                        PurePosixPath(
                                            item["relative_path"]
                                        ).parts
                                    ),
                                    item["relative_path"],
                                ),
                            )
                            for record in directory_records:
                                changed = True
                                _remove_verified_empty_directory(
                                    root,
                                    _target_path_for_relative(
                                        target,
                                        record["relative_path"],
                                    ),
                                    record,
                                )
                            post_delete_git_blockers = _git_tracking_blockers(
                                root,
                                True,
                            )
                            if post_delete_git_blockers:
                                execution_blockers.extend(
                                    post_delete_git_blockers
                                )
                                raise OSError("legacy_cleanup_git_state_changed")
                    except KeyboardInterrupt:
                        # Once exact-entry deletion starts, Ctrl+C must not
                        # bypass the partial-change result.  Finish owned-lock
                        # release and residue inspection, then report the
                        # interruption without echoing private path details.
                        execution_blockers.append("cleanup_execution_interrupted")
                    except (MemoryError, OSError, RuntimeError, ValueError):
                        execution_blockers.append("cleanup_execution_failed")
                    finally:
                        lock_released = _release_lock(
                            root,
                            lock_path,
                            lock_descriptor,
                            lock_record,
                        )
                        lock_descriptor = None
                        if not lock_released:
                            execution_blockers.append(
                                "cleanup_lock_release_failed"
                            )

            residue, residue_known = _cleanup_residue_state(bound_root)
    except KeyboardInterrupt:
        execution_blockers.append("cleanup_execution_interrupted")
    except (MemoryError, OSError, RuntimeError, ValueError):
        execution_blockers.extend(
            [
                "workspace_root_binding_or_state_changed",
                "cleanup_execution_failed",
            ]
        )

    if not residue_known:
        execution_blockers.append("cleanup_residue_scan_failed")
    if execution_blockers or any(residue.values()):
        if any(residue.values()) and not execution_blockers:
            execution_blockers.append("cleanup_residue_present")
        return _result_from_plan(
            public_plan,
            dry_run=False,
            status="partial_cleanup_pending" if changed else "blocked",
            blockers=execution_blockers,
            changed=changed,
            remaining_tombstone_id=None,
            residue=residue,
        )
    return _result_from_plan(
        public_plan,
        dry_run=False,
        status="cleanup_completed",
        blockers=[],
        changed=changed,
        remaining_tombstone_id=None,
        residue=residue,
    )
