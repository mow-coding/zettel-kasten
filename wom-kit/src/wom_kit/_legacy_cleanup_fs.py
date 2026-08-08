"""Handle-bound filesystem primitives for retired-state cleanup.

This module is intentionally private.  It gives the legacy
coordination cleanup one narrow way to keep an approved workspace directory
bound while it scans or mutates direct entries.  Callers still own approval,
plan hashing, content validation, and public-result privacy.

Mutation helpers are intentionally Windows-only in v0.3.307.  Standard POSIX
APIs cannot atomically require that a name still denotes an expected inode at
the instant of unlink/rmdir, so POSIX remains read-only and fail-closed.

Lifetime is part of the security contract: close every bound file and child
directory, verify and remove the owned cleanup lock, and collect bound-root
residue before leaving :func:`bind_workspace_root`.  The root context then
closes held Windows handles and POSIX descriptors in reverse ancestry order.
Never fall back to the original absolute pathname after that context reports
root drift; it may now name a replacement directory.
"""

from __future__ import annotations

import ntpath
import os
import stat
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

from .archive_services import activity_group_bound_directory_chain


REPARSE_FLAG = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
_DIRECTORY_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_DIRECTORY", 0)
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_CLOEXEC", 0)
)


class LegacyCleanupFilesystemError(OSError):
    """A stable, content-free filesystem-boundary failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require_apply_platform() -> None:
    if os.name != "nt":
        raise LegacyCleanupFilesystemError(
            "legacy_cleanup_apply_platform_unsupported"
        )


@dataclass(frozen=True)
class MountToken:
    kind: str
    value: int


@dataclass(frozen=True)
class BoundCleanupRoot:
    """An approved workspace root whose OS binding is valid in its context."""

    path: Path
    descriptor: int | None
    windows_handles: tuple[Any, ...]
    identity: tuple[int, int]
    mount_token: MountToken


@dataclass(frozen=True)
class BoundCleanupDirectory:
    """One no-follow directory reached from a bound workspace root."""

    root: BoundCleanupRoot
    relative: PurePosixPath
    path: Path
    descriptor: int | None
    windows_handles: tuple[Any, ...]
    identity: tuple[int, int]
    mount_token: MountToken


@dataclass(frozen=True)
class BoundCleanupFile:
    """One stable regular-file descriptor reached from a bound directory."""

    parent: BoundCleanupDirectory
    name: str
    descriptor: int
    identity: tuple[int, int]
    mount_token: MountToken
    stat_result: os.stat_result


def stat_identity(info: os.stat_result) -> tuple[int, int]:
    return int(info.st_dev), int(info.st_ino)


def _is_reparse(info: os.stat_result) -> bool:
    return bool(
        stat.S_ISLNK(info.st_mode)
        or (
            REPARSE_FLAG
            and getattr(info, "st_file_attributes", 0) & REPARSE_FLAG
        )
    )


def _normalized_path_key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(str(path))))


def _strict_entry_name(name: str) -> str:
    if not isinstance(name, str):
        raise LegacyCleanupFilesystemError("legacy_cleanup_entry_name_invalid")
    if (
        not name
        or name in {".", ".."}
        or "\x00" in name
        or "/" in name
        or "\\" in name
        or (os.name == "nt" and ":" in name)
    ):
        raise LegacyCleanupFilesystemError("legacy_cleanup_entry_name_invalid")
    return name


def _strict_relative_directory(relative: PurePosixPath | str) -> PurePosixPath:
    raw = str(relative)
    if not raw or "\x00" in raw or "\\" in raw:
        raise LegacyCleanupFilesystemError(
            "legacy_cleanup_relative_directory_invalid"
        )
    candidate = PurePosixPath(raw)
    if (
        candidate.is_absolute()
        or not candidate.parts
        or any(part in {"", ".", ".."} for part in candidate.parts)
        or candidate.as_posix() != raw
        or any(os.name == "nt" and ":" in part for part in candidate.parts)
    ):
        raise LegacyCleanupFilesystemError(
            "legacy_cleanup_relative_directory_invalid"
        )
    return candidate


def _validate_root_syntax(root: Path) -> None:
    if not root.is_absolute() or not root.anchor:
        raise LegacyCleanupFilesystemError("workspace_root_must_be_absolute")
    if ".." in root.parts:
        raise LegacyCleanupFilesystemError("workspace_root_ambiguous_component")
    if _normalized_path_key(root) == _normalized_path_key(Path(root.anchor)):
        raise LegacyCleanupFilesystemError("workspace_root_broad_or_protected")
    if os.name != "nt":
        return
    rendered = str(root).replace("/", "\\")
    folded = rendered.casefold()
    if folded.startswith(("\\\\?\\", "\\\\.\\", "\\??\\")):
        raise LegacyCleanupFilesystemError("workspace_root_namespace_unsafe")
    drive, tail = ntpath.splitdrive(rendered)
    if drive.startswith("\\\\"):
        raise LegacyCleanupFilesystemError("workspace_root_remote_unsafe")
    if ":" in tail:
        raise LegacyCleanupFilesystemError(
            "workspace_root_alternate_stream_syntax"
        )


def parse_linux_fdinfo_mount_id(raw: str) -> int:
    """Parse the single Linux ``mnt_id`` field from one fdinfo record."""

    if not isinstance(raw, str) or len(raw) > 64 * 1024:
        raise LegacyCleanupFilesystemError("mount_identity_unavailable")
    values: list[str] = []
    for line in raw.splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip() == "mnt_id":
            values.append(value.strip())
    if len(values) != 1 or not values[0].isdecimal():
        raise LegacyCleanupFilesystemError("mount_identity_unavailable")
    return int(values[0], 10)


def linux_mount_id_for_fd(descriptor: int) -> int:
    """Return Linux's mount identity for one already-open file descriptor."""

    if not isinstance(descriptor, int) or isinstance(descriptor, bool) or descriptor < 0:
        raise LegacyCleanupFilesystemError("mount_identity_unavailable")
    try:
        with open(
            f"/proc/self/fdinfo/{descriptor}",
            "r",
            encoding="ascii",
            errors="strict",
        ) as stream:
            raw = stream.read(64 * 1024 + 1)
    except (OSError, UnicodeError):
        raise LegacyCleanupFilesystemError(
            "mount_identity_unavailable"
        ) from None
    return parse_linux_fdinfo_mount_id(raw)


def mount_token_for_open_fd(descriptor: int) -> MountToken:
    info = os.fstat(descriptor)
    if sys.platform.startswith("linux"):
        return MountToken("linux-mount-id", linux_mount_id_for_fd(descriptor))
    return MountToken("posix-device", int(info.st_dev))


def _mount_token_from_stat(info: os.stat_result) -> MountToken:
    return MountToken(
        "windows-device" if os.name == "nt" else "posix-device",
        int(info.st_dev),
    )


def require_same_mount(expected: MountToken, observed: MountToken) -> None:
    if expected != observed:
        raise LegacyCleanupFilesystemError("mount_boundary_entry")


@contextmanager
def bind_workspace_root(root: Path | str) -> Iterator[BoundCleanupRoot]:
    """Bind every component from the filesystem anchor to one workspace root.

    All descendant bindings, root-relative mutations, residue scanning, and
    owned-lock removal must finish inside this context.  On Windows the
    existing archive binding keeps the anchor and every ancestor open without
    delete sharing.  On POSIX callers use the yielded root descriptor for
    every mutation, so renaming the pathname cannot redirect the operation.
    """

    path = Path(root)
    _validate_root_syntax(path)
    anchor = Path(path.anchor)
    with activity_group_bound_directory_chain(anchor, path) as raw_binding:
        descriptor = raw_binding.get("descriptor")
        windows_handles = tuple(raw_binding.get("windows_handles") or ())
        if os.name == "nt":
            if not windows_handles:
                raise LegacyCleanupFilesystemError(
                    "workspace_root_binding_unavailable"
                )
            info = os.lstat(path)
            mount_token = _mount_token_from_stat(info)
        else:
            if not isinstance(descriptor, int):
                raise LegacyCleanupFilesystemError(
                    "workspace_root_binding_unavailable"
                )
            info = os.fstat(descriptor)
            mount_token = mount_token_for_open_fd(descriptor)
            parent_descriptor: int | None = None
            try:
                parent_descriptor = os.open(
                    "..",
                    _DIRECTORY_FLAGS,
                    dir_fd=descriptor,
                )
                parent_mount = mount_token_for_open_fd(parent_descriptor)
            finally:
                if parent_descriptor is not None:
                    os.close(parent_descriptor)
            if parent_mount != mount_token:
                raise LegacyCleanupFilesystemError(
                    "workspace_root_mount_boundary"
                )
            if not sys.platform.startswith("linux") and os.path.ismount(path):
                raise LegacyCleanupFilesystemError(
                    "workspace_root_mount_boundary"
                )
        if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
            raise LegacyCleanupFilesystemError(
                "workspace_root_path_component_unsafe"
            )
        canonical = path.resolve(strict=True)
        canonical_info = os.lstat(canonical)
        if (
            _normalized_path_key(path) != _normalized_path_key(canonical)
            or _is_reparse(canonical_info)
            or not stat.S_ISDIR(canonical_info.st_mode)
            or stat_identity(canonical_info) != stat_identity(info)
        ):
            raise LegacyCleanupFilesystemError("workspace_root_alias_unsafe")
        yield BoundCleanupRoot(
            path=path,
            descriptor=descriptor if isinstance(descriptor, int) else None,
            windows_handles=windows_handles,
            identity=stat_identity(info),
            mount_token=mount_token,
        )


@contextmanager
def bind_directory(
    root: BoundCleanupRoot,
    relative: PurePosixPath | str,
) -> Iterator[BoundCleanupDirectory]:
    """Open a no-follow directory chain relative to a held workspace root."""

    safe_relative = _strict_relative_directory(relative)
    target_path = root.path.joinpath(*safe_relative.parts)
    if root.descriptor is not None:
        current = os.dup(root.descriptor)
        try:
            final_info = os.fstat(current)
            final_mount = mount_token_for_open_fd(current)
            for part in safe_relative.parts:
                before = os.stat(
                    part,
                    dir_fd=current,
                    follow_symlinks=False,
                )
                if _is_reparse(before) or not stat.S_ISDIR(before.st_mode):
                    raise LegacyCleanupFilesystemError(
                        "legacy_cleanup_directory_unsafe"
                    )
                child = os.open(part, _DIRECTORY_FLAGS, dir_fd=current)
                try:
                    opened = os.fstat(child)
                    if (
                        _is_reparse(opened)
                        or not stat.S_ISDIR(opened.st_mode)
                        or stat_identity(opened) != stat_identity(before)
                    ):
                        raise LegacyCleanupFilesystemError(
                            "legacy_cleanup_directory_changed"
                        )
                    observed_mount = mount_token_for_open_fd(child)
                    require_same_mount(root.mount_token, observed_mount)
                except BaseException:
                    os.close(child)
                    raise
                os.close(current)
                current = child
                final_info = opened
                final_mount = observed_mount
            yield BoundCleanupDirectory(
                root=root,
                relative=safe_relative,
                path=target_path,
                descriptor=current,
                windows_handles=(),
                identity=stat_identity(final_info),
                mount_token=final_mount,
            )
        finally:
            os.close(current)
        return

    with activity_group_bound_directory_chain(root.path, target_path) as raw_binding:
        windows_handles = tuple(raw_binding.get("windows_handles") or ())
        if not windows_handles:
            raise LegacyCleanupFilesystemError(
                "legacy_cleanup_directory_binding_unavailable"
            )
        info = os.lstat(target_path)
        if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
            raise LegacyCleanupFilesystemError("legacy_cleanup_directory_unsafe")
        observed_mount = _mount_token_from_stat(info)
        require_same_mount(root.mount_token, observed_mount)
        yield BoundCleanupDirectory(
            root=root,
            relative=safe_relative,
            path=target_path,
            descriptor=None,
            windows_handles=windows_handles,
            identity=stat_identity(info),
            mount_token=observed_mount,
        )


@contextmanager
def bind_regular_file(
    directory: BoundCleanupDirectory,
    name: str,
) -> Iterator[BoundCleanupFile]:
    """Open one regular no-follow file and bind its identity and mount."""

    safe_name = _strict_entry_name(name)
    flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    if directory.descriptor is not None:
        before = os.stat(
            safe_name,
            dir_fd=directory.descriptor,
            follow_symlinks=False,
        )
        descriptor = os.open(
            safe_name,
            flags,
            dir_fd=directory.descriptor,
        )
    else:
        path = directory.path / safe_name
        before = os.lstat(path)
        descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if (
            _is_reparse(before)
            or not stat.S_ISREG(before.st_mode)
            or not stat.S_ISREG(opened.st_mode)
            or stat_identity(before) != stat_identity(opened)
        ):
            raise LegacyCleanupFilesystemError("legacy_cleanup_file_unsafe")
        observed_mount = (
            mount_token_for_open_fd(descriptor)
            if directory.descriptor is not None
            else _mount_token_from_stat(opened)
        )
        require_same_mount(directory.root.mount_token, observed_mount)
        yield BoundCleanupFile(
            parent=directory,
            name=safe_name,
            descriptor=descriptor,
            identity=stat_identity(opened),
            mount_token=observed_mount,
            stat_result=opened,
        )
    finally:
        os.close(descriptor)


def _scan(
    descriptor: int | None,
    path: Path,
    *,
    max_entries: int,
) -> list[tuple[str, os.stat_result]]:
    if (
        not isinstance(max_entries, int)
        or isinstance(max_entries, bool)
        or max_entries < 0
    ):
        raise LegacyCleanupFilesystemError(
            "legacy_cleanup_directory_entry_limit_invalid"
        )
    target: int | Path = descriptor if descriptor is not None else path
    observed: list[tuple[str, os.stat_result]] = []
    with os.scandir(target) as entries:
        for entry in entries:
            if len(observed) >= max_entries:
                raise LegacyCleanupFilesystemError(
                    "legacy_cleanup_directory_entry_limit_exceeded"
                )
            observed.append((entry.name, entry.stat(follow_symlinks=False)))
    observed.sort(key=lambda item: (item[0].casefold(), item[0]))
    return observed


def scan_root(
    root: BoundCleanupRoot,
    *,
    max_entries: int,
) -> list[tuple[str, os.stat_result]]:
    return _scan(root.descriptor, root.path, max_entries=max_entries)


def scan_directory(
    directory: BoundCleanupDirectory,
    *,
    max_entries: int,
) -> list[tuple[str, os.stat_result]]:
    return _scan(
        directory.descriptor,
        directory.path,
        max_entries=max_entries,
    )


def lstat_at_root(root: BoundCleanupRoot, name: str) -> os.stat_result:
    safe_name = _strict_entry_name(name)
    if root.descriptor is not None:
        return os.stat(
            safe_name,
            dir_fd=root.descriptor,
            follow_symlinks=False,
        )
    return os.lstat(root.path / safe_name)


def lstat_in_directory(
    directory: BoundCleanupDirectory,
    name: str,
) -> os.stat_result:
    safe_name = _strict_entry_name(name)
    if directory.descriptor is not None:
        return os.stat(
            safe_name,
            dir_fd=directory.descriptor,
            follow_symlinks=False,
        )
    return os.lstat(directory.path / safe_name)


def exists_at_root_no_follow(root: BoundCleanupRoot, name: str) -> bool:
    try:
        lstat_at_root(root, name)
    except FileNotFoundError:
        return False
    return True


def open_exclusive_at_root(
    root: BoundCleanupRoot,
    name: str,
    *,
    mode: int = 0o600,
) -> int:
    """Create one direct-child file; caller must close it before root exit."""

    safe_name = _strict_entry_name(name)
    _require_apply_platform()
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    if root.descriptor is not None:
        return os.open(safe_name, flags, mode, dir_fd=root.descriptor)
    return os.open(root.path / safe_name, flags, mode)


def rename_at_root(
    root: BoundCleanupRoot,
    source_name: str,
    destination_name: str,
    *,
    expected_source_identity: tuple[int, int] | None = None,
) -> None:
    """Rename one reviewed direct child within the held root.

    The caller must have bound and mount-checked the source during its locked
    replan.  A same-parent, unpredictable destination and writer quiescence
    remain caller policy; this primitive supplies root-fd confinement.
    """

    source = _strict_entry_name(source_name)
    destination = _strict_entry_name(destination_name)
    _require_apply_platform()
    source_info = lstat_at_root(root, source)
    if (
        _is_reparse(source_info)
        or (
            expected_source_identity is not None
            and stat_identity(source_info) != expected_source_identity
        )
    ):
        raise LegacyCleanupFilesystemError(
            "legacy_cleanup_rename_source_unsafe"
        )
    if exists_at_root_no_follow(root, destination):
        raise LegacyCleanupFilesystemError(
            "legacy_cleanup_rename_destination_present"
        )
    if root.descriptor is not None:
        os.rename(
            source,
            destination,
            src_dir_fd=root.descriptor,
            dst_dir_fd=root.descriptor,
        )
    else:
        os.rename(root.path / source, root.path / destination)


def unlink_at_root(
    root: BoundCleanupRoot,
    name: str,
    *,
    expected_identity: tuple[int, int] | None = None,
) -> None:
    """Unlink one verified regular direct child within the held root."""

    safe_name = _strict_entry_name(name)
    _require_apply_platform()
    info = lstat_at_root(root, safe_name)
    if (
        _is_reparse(info)
        or not stat.S_ISREG(info.st_mode)
        or (
            expected_identity is not None
            and stat_identity(info) != expected_identity
        )
    ):
        raise LegacyCleanupFilesystemError("legacy_cleanup_unlink_entry_unsafe")
    if root.descriptor is not None:
        os.unlink(safe_name, dir_fd=root.descriptor)
    else:
        os.unlink(root.path / safe_name)


def unlink_in_directory(
    directory: BoundCleanupDirectory,
    name: str,
    *,
    expected_identity: tuple[int, int] | None = None,
) -> None:
    safe_name = _strict_entry_name(name)
    _require_apply_platform()
    info = lstat_in_directory(directory, safe_name)
    if (
        _is_reparse(info)
        or not stat.S_ISREG(info.st_mode)
        or (
            expected_identity is not None
            and stat_identity(info) != expected_identity
        )
    ):
        raise LegacyCleanupFilesystemError("legacy_cleanup_unlink_entry_unsafe")
    if directory.descriptor is not None:
        os.unlink(safe_name, dir_fd=directory.descriptor)
    else:
        os.unlink(directory.path / safe_name)


def rmdir_in_directory(
    directory: BoundCleanupDirectory,
    name: str,
    *,
    expected_identity: tuple[int, int] | None = None,
) -> None:
    safe_name = _strict_entry_name(name)
    _require_apply_platform()
    info = lstat_in_directory(directory, safe_name)
    if (
        _is_reparse(info)
        or not stat.S_ISDIR(info.st_mode)
        or (
            expected_identity is not None
            and stat_identity(info) != expected_identity
        )
    ):
        raise LegacyCleanupFilesystemError("legacy_cleanup_rmdir_entry_unsafe")
    if directory.descriptor is not None:
        os.rmdir(safe_name, dir_fd=directory.descriptor)
    else:
        os.rmdir(directory.path / safe_name)


__all__ = [
    "BoundCleanupDirectory",
    "BoundCleanupFile",
    "BoundCleanupRoot",
    "LegacyCleanupFilesystemError",
    "MountToken",
    "bind_directory",
    "bind_regular_file",
    "bind_workspace_root",
    "exists_at_root_no_follow",
    "linux_mount_id_for_fd",
    "lstat_at_root",
    "lstat_in_directory",
    "mount_token_for_open_fd",
    "open_exclusive_at_root",
    "parse_linux_fdinfo_mount_id",
    "rename_at_root",
    "require_same_mount",
    "rmdir_in_directory",
    "scan_directory",
    "scan_root",
    "stat_identity",
    "unlink_at_root",
    "unlink_in_directory",
]
