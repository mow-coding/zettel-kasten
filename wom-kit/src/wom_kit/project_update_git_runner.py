"""Approval-bound Git executable authority for project version updates.

The updater resolves ``git`` once before native approval.  This module keeps
that exact regular file open, binds its private absolute locator and bytes,
and produces only absolute argv values afterwards.  Closing the transport
boundary permanently disables network-capable Git subcommands while retaining
the executable handle through the domain write and approval finalizer.
"""

from __future__ import annotations

import ctypes
import hashlib
import hmac
import json
import os
import re
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


PRIVATE_SCHEMA = "wom-kit/project-update-trusted-git-runner-private/v0.4.3"
PUBLIC_SCHEMA = "wom-kit/project-update-trusted-git-runner/v0.4.3"
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
MAX_EXECUTABLE_BYTES = 256 * 1024 * 1024
_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

_TRANSPORT_SUBCOMMANDS = frozenset(
    {
        "clone",
        "fetch",
        "http-fetch",
        "http-push",
        "ls-remote",
        "pull",
        "push",
        "send-pack",
        "submodule",
        "upload-archive",
        "upload-pack",
    }
)
_PREAPPROVAL_TRANSPORT_SUBCOMMANDS = frozenset({"fetch", "ls-remote"})
_LOCAL_ONLY_SUBCOMMANDS = frozenset(
    {
        "--version",
        "cat-file",
        "check-attr",
        "check-ignore",
        "check-ref-format",
        "config",
        "hash-object",
        "ls-files",
        "ls-tree",
        "merge-base",
        "read-tree",
        "rev-parse",
        "show-ref",
        "symbolic-ref",
        "update-ref",
    }
)


class ProjectUpdateGitRunnerError(RuntimeError):
    _CODES = frozenset(
        {
            "project_update_git_runner_unavailable",
            "project_update_git_runner_unsafe",
            "project_update_git_runner_binding_invalid",
            "project_update_git_runner_drift",
            "project_update_git_runner_phase_invalid",
            "project_update_git_runner_command_invalid",
            "project_update_git_runner_closed",
            "project_update_git_runner_close_unverified",
            "project_update_git_runner_resolved_more_than_once",
            "project_update_git_runner_handoff_invalid",
        }
    )

    def __init__(self, code: str) -> None:
        self.code = (
            code
            if code in self._CODES
            else "project_update_git_runner_binding_invalid"
        )
        super().__init__(self.code)


def _fail(code: str) -> ProjectUpdateGitRunnerError:
    return ProjectUpdateGitRunnerError(code)


class _DuplicateKey(ValueError):
    pass


def _object_without_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey(key)
        result[key] = value
    return result


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise _fail("project_update_git_runner_binding_invalid") from None


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _absolute(path: Path | str) -> Path:
    try:
        return Path(os.path.abspath(str(Path(path).expanduser())))
    except (OSError, RuntimeError, ValueError):
        raise _fail("project_update_git_runner_unsafe") from None


def _validate_path_chain(path: Path) -> os.stat_result:
    if not path.is_absolute() or path.name.casefold() not in {"git", "git.exe"}:
        raise _fail("project_update_git_runner_unsafe")
    anchor = Path(path.anchor)
    current = anchor
    try:
        relative_parts = path.relative_to(anchor).parts
    except ValueError:
        raise _fail("project_update_git_runner_unsafe") from None
    if not relative_parts:
        raise _fail("project_update_git_runner_unsafe")
    try:
        for index, part in enumerate(relative_parts):
            current = current / part
            information = os.lstat(current)
            if stat.S_ISLNK(information.st_mode) or bool(
                getattr(information, "st_file_attributes", 0) & _REPARSE
            ):
                raise _fail("project_update_git_runner_unsafe")
            if index < len(relative_parts) - 1:
                if not stat.S_ISDIR(information.st_mode):
                    raise _fail("project_update_git_runner_unsafe")
            elif (
                not stat.S_ISREG(information.st_mode)
                or not (1 <= int(information.st_nlink) <= 64)
                or int(information.st_size) <= 0
                or int(information.st_size) > MAX_EXECUTABLE_BYTES
            ):
                raise _fail("project_update_git_runner_unsafe")
    except ProjectUpdateGitRunnerError:
        raise
    except OSError:
        raise _fail("project_update_git_runner_unsafe") from None
    return information


@dataclass(frozen=True)
class TrustedGitPrivateBinding:
    executable_locator: str
    executable_sha256: str
    size_bytes: int
    volume_identity: int
    file_identity: int
    link_count: int

    def __post_init__(self) -> None:
        path = _absolute(self.executable_locator)
        if str(path) != self.executable_locator:
            raise _fail("project_update_git_runner_binding_invalid")
        if (
            SHA256_RE.fullmatch(self.executable_sha256) is None
            or type(self.size_bytes) is not int
            or not (1 <= self.size_bytes <= MAX_EXECUTABLE_BYTES)
            or type(self.volume_identity) is not int
            or self.volume_identity < 0
            or type(self.file_identity) is not int
            or self.file_identity <= 0
            or type(self.link_count) is not int
            or not (1 <= self.link_count <= 64)
        ):
            raise _fail("project_update_git_runner_binding_invalid")

    def document(self) -> dict[str, Any]:
        return {
            "executable_locator": self.executable_locator,
            "executable_sha256": self.executable_sha256,
            "file_identity": self.file_identity,
            "link_count": self.link_count,
            "schema": PRIVATE_SCHEMA,
            "size_bytes": self.size_bytes,
            "volume_identity": self.volume_identity,
        }

    @property
    def sha256(self) -> str:
        return _sha256(_canonical(self.document()))

    @classmethod
    def from_document(cls, value: Any) -> "TrustedGitPrivateBinding":
        expected = {
            "executable_locator",
            "executable_sha256",
            "file_identity",
            "link_count",
            "schema",
            "size_bytes",
            "volume_identity",
        }
        if (
            type(value) is not dict
            or set(value) != expected
            or value.get("schema") != PRIVATE_SCHEMA
        ):
            raise _fail("project_update_git_runner_binding_invalid")
        return cls(
            executable_locator=value["executable_locator"],
            executable_sha256=value["executable_sha256"],
            size_bytes=value["size_bytes"],
            volume_identity=value["volume_identity"],
            file_identity=value["file_identity"],
            link_count=value["link_count"],
        )


def load_private_binding_bytes(raw: bytes) -> TrustedGitPrivateBinding:
    try:
        value = json.loads(
            raw.decode("ascii", errors="strict"),
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()),
        )
    except (UnicodeError, ValueError, TypeError):
        raise _fail("project_update_git_runner_binding_invalid") from None
    binding = TrustedGitPrivateBinding.from_document(value)
    if raw not in {_canonical(binding.document()), _canonical(binding.document()) + b"\n"}:
        raise _fail("project_update_git_runner_binding_invalid")
    return binding


def _extract_subcommand(arguments: Sequence[str]) -> str:
    if (
        isinstance(arguments, (str, bytes))
        or not arguments
        or any(type(item) is not str or not item or "\0" in item for item in arguments)
    ):
        raise _fail("project_update_git_runner_command_invalid")
    index = 0
    pair_options = {"-c", "-C", "--git-dir", "--work-tree", "--namespace"}
    while index < len(arguments):
        item = arguments[index]
        if item in pair_options:
            if index + 1 >= len(arguments):
                raise _fail("project_update_git_runner_command_invalid")
            index += 2
            continue
        if item.startswith(("--git-dir=", "--work-tree=", "--namespace=")):
            index += 1
            continue
        if item in {"--no-pager", "--literal-pathspecs", "--no-optional-locks"}:
            index += 1
            continue
        if item in {"--version", "--help"}:
            return item
        if item.startswith("-"):
            raise _fail("project_update_git_runner_command_invalid")
        return item.casefold()
    raise _fail("project_update_git_runner_command_invalid")


def _validate_fixed_project_prologue(arguments: Sequence[str]) -> None:
    if tuple(arguments) == ("--version",):
        return
    if len(arguments) < 12:
        raise _fail("project_update_git_runner_command_invalid")
    expected = (
        "--no-optional-locks",
        "-c",
        "core.fsmonitor=false",
        "-c",
        f"core.hooksPath={os.devnull}",
        "-c",
        f"core.attributesFile={os.devnull}",
        "-c",
        f"core.excludesFile={os.devnull}",
        "-C",
    )
    if tuple(arguments[:10]) != expected:
        raise _fail("project_update_git_runner_command_invalid")
    working_root = Path(arguments[10])
    try:
        if (
            not working_root.is_absolute()
            or str(working_root) != str(_absolute(working_root))
            or not working_root.is_dir()
            or working_root.is_symlink()
        ):
            raise _fail("project_update_git_runner_command_invalid")
    except OSError:
        raise _fail("project_update_git_runner_command_invalid") from None


def _validate_local_only_command(
    arguments: Sequence[str], subcommand: str
) -> None:
    """Admit only the local plumbing used by the sealed updater.

    Blocking a short list of transport verbs is not sufficient: commands such
    as ``remote update`` or ``archive --remote`` can also cross the network,
    and checkout-like commands can invoke repository-defined filters.  Keep
    the post-resolution runner on the exact local plumbing surface instead.
    """

    if subcommand not in _LOCAL_ONLY_SUBCOMMANDS:
        raise _fail("project_update_git_runner_command_invalid")
    lowered = tuple(item.casefold() for item in arguments)
    if any(
        item in {
            "--ext-diff",
            "--filters",
            "--recurse-submodules",
            "--remote",
            "--textconv",
        }
        or item.startswith("--remote=")
        for item in lowered
    ):
        raise _fail("project_update_git_runner_command_invalid")
    subcommand_index = lowered.index(subcommand)
    tail = lowered[subcommand_index + 1 :]
    if subcommand == "config":
        safe_config_queries = {
            ("--includes", "--null", "--list", "--show-origin"),
            ("--type=bool", "--get", "core.autocrlf"),
            (
                "--local",
                "--no-includes",
                "--name-only",
                "--get-regexp",
                r"^remote\.origin\.url$",
            ),
        }
        if tail not in safe_config_queries:
            raise _fail("project_update_git_runner_command_invalid")
    if subcommand == "hash-object":
        worktree_hash = bool(
            len(tail) == 3
            and tail[:2] == ("--no-filters", "--")
            and not tail[2].startswith("/")
            and "\\" not in tail[2]
            and not re.match(r"^[a-z]:", tail[2], flags=re.IGNORECASE)
            and all(
                part not in {"", ".", ".."}
                for part in tail[2].split("/")
            )
            and PurePosixPath(tail[2]).as_posix() == tail[2]
        )
        if tail != ("--stdin",) and not worktree_hash:
            raise _fail("project_update_git_runner_command_invalid")
    if subcommand == "read-tree" and any(item in {"-u", "--empty"} for item in tail):
        raise _fail("project_update_git_runner_command_invalid")


class TrustedProjectUpdateGitRunner:
    """One held executable binding with a one-way transport phase."""

    def __init__(
        self,
        binding: TrustedGitPrivateBinding,
        *,
        handle: int,
        windows_handle: bool,
    ) -> None:
        self.binding = binding
        self._path = Path(binding.executable_locator)
        self._handle = handle
        self._windows_handle = windows_handle
        self._phase = "transport_open"
        self._closed = False

    @classmethod
    def resolve_preapproval(
        cls,
        executable: Path | str | None = None,
    ) -> "TrustedProjectUpdateGitRunner":
        candidate = executable
        if candidate is None:
            candidate = shutil.which("git")
        if candidate is None:
            raise _fail("project_update_git_runner_unavailable")
        path = _absolute(candidate)
        _validate_path_chain(path)
        if os.name == "nt":
            handle, identity, size, digest, link_count = _open_windows(path)
            return cls(
                TrustedGitPrivateBinding(
                    executable_locator=str(path),
                    executable_sha256=digest,
                    size_bytes=size,
                    volume_identity=identity[0],
                    file_identity=identity[1],
                    link_count=link_count,
                ),
                handle=handle,
                windows_handle=True,
            )
        handle, identity, size, digest, link_count = _open_posix(path)
        return cls(
            TrustedGitPrivateBinding(
                executable_locator=str(path),
                executable_sha256=digest,
                size_bytes=size,
                volume_identity=identity[0],
                file_identity=identity[1],
                link_count=link_count,
            ),
            handle=handle,
            windows_handle=False,
        )

    @classmethod
    def reopen_private(
        cls,
        binding: TrustedGitPrivateBinding | Mapping[str, Any],
    ) -> "TrustedProjectUpdateGitRunner":
        expected = (
            binding
            if isinstance(binding, TrustedGitPrivateBinding)
            else TrustedGitPrivateBinding.from_document(dict(binding))
        )
        runner = cls.resolve_preapproval(expected.executable_locator)
        if not hmac.compare_digest(
            _canonical(runner.binding.document()),
            _canonical(expected.document()),
        ):
            runner.close()
            raise _fail("project_update_git_runner_drift")
        return runner

    @property
    def phase(self) -> str:
        return self._phase

    def private_binding_bytes(self) -> bytes:
        return _canonical(self.binding.document()) + b"\n"

    def public_summary(self) -> dict[str, Any]:
        return {
            "schema": PUBLIC_SCHEMA,
            "runner_sha256": self.binding.sha256,
            "executable_sha256": self.binding.executable_sha256,
            "size_bytes": self.binding.size_bytes,
            "phase": self._phase,
            "absolute_path_echoed": False,
            "path_lookup_after_resolution": False,
            "executable_handle_held": not self._closed,
            "postapproval_transport_allowed": False,
        }

    def assert_unchanged(self) -> None:
        if self._closed:
            raise _fail("project_update_git_runner_closed")
        try:
            current = _validate_path_chain(self._path)
            if self._windows_handle:
                identity, size, digest, link_count = _inspect_windows_handle(
                    self._handle
                )
            else:
                identity, size, digest, link_count = _inspect_posix_handle(
                    self._handle
                )
            path_identity = (int(current.st_dev), int(current.st_ino))
            if (
                size != self.binding.size_bytes
                or identity
                != (self.binding.volume_identity, self.binding.file_identity)
                or (current.st_size != size)
                or int(current.st_nlink) != self.binding.link_count
                or link_count != self.binding.link_count
                or (
                    os.name != "nt"
                    and path_identity[0]
                    and self.binding.volume_identity
                    and path_identity[0] != self.binding.volume_identity
                )
                or (
                    path_identity[1]
                    and path_identity[1] != self.binding.file_identity
                )
                or not hmac.compare_digest(digest, self.binding.executable_sha256)
            ):
                raise _fail("project_update_git_runner_drift")
        except ProjectUpdateGitRunnerError:
            raise
        except OSError:
            raise _fail("project_update_git_runner_drift") from None

    def close_transport_boundary(self) -> None:
        if self._phase != "transport_open" or self._closed:
            raise _fail("project_update_git_runner_phase_invalid")
        self.assert_unchanged()
        self._phase = "local_only"

    def command(
        self,
        arguments: Sequence[str],
        *,
        transport: bool = False,
    ) -> list[str]:
        _validate_fixed_project_prologue(arguments)
        subcommand = _extract_subcommand(arguments)
        if transport:
            if (
                self._phase != "transport_open"
                or subcommand not in _PREAPPROVAL_TRANSPORT_SUBCOMMANDS
            ):
                raise _fail("project_update_git_runner_phase_invalid")
        elif subcommand in _TRANSPORT_SUBCOMMANDS:
            raise _fail("project_update_git_runner_command_invalid")
        else:
            _validate_local_only_command(arguments, subcommand)
        self.assert_unchanged()
        return [str(self._path), *arguments]

    def close(self) -> None:
        if self._closed:
            return
        ok = True
        if self._windows_handle:
            ok = _close_windows_handle(self._handle)
        else:
            try:
                os.close(self._handle)
            except OSError:
                ok = False
        self._closed = True
        self._handle = -1
        if not ok:
            raise _fail("project_update_git_runner_close_unverified")

    def __enter__(self) -> "TrustedProjectUpdateGitRunner":
        return self

    def __exit__(self, _type: Any, _value: Any, _traceback: Any) -> None:
        self.close()

    def __del__(self) -> None:
        if not getattr(self, "_closed", True):
            try:
                self.close()
            except BaseException:
                pass


def _open_posix(
    path: Path,
) -> tuple[int, tuple[int, int], int, str, int]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        os.set_inheritable(descriptor, False)
        identity, size, digest, link_count = _inspect_posix_handle(
            descriptor
        )
        return descriptor, identity, size, digest, link_count
    except BaseException:
        try:
            os.close(descriptor)
        except (OSError, UnboundLocalError):
            pass
        raise _fail("project_update_git_runner_unavailable") from None


def _inspect_posix_handle(
    descriptor: int,
) -> tuple[tuple[int, int], int, str, int]:
    before = os.fstat(descriptor)
    if (
        not stat.S_ISREG(before.st_mode)
        or not (1 <= before.st_nlink <= 64)
        or not (1 <= before.st_size <= MAX_EXECUTABLE_BYTES)
    ):
        raise _fail("project_update_git_runner_unsafe")
    digest = hashlib.sha256()
    offset = 0
    while offset < before.st_size:
        block = os.pread(descriptor, min(1024 * 1024, before.st_size - offset), offset)
        if not block:
            raise _fail("project_update_git_runner_drift")
        digest.update(block)
        offset += len(block)
    after = os.fstat(descriptor)
    if (
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    ):
        raise _fail("project_update_git_runner_drift")
    return (
        (int(after.st_dev), int(after.st_ino)),
        int(after.st_size),
        "sha256:" + digest.hexdigest(),
        int(after.st_nlink),
    )


def _windows_api() -> tuple[Any, Any]:
    from ctypes import wintypes

    class ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("attributes", wintypes.DWORD),
            ("creation_time", wintypes.FILETIME),
            ("access_time", wintypes.FILETIME),
            ("write_time", wintypes.FILETIME),
            ("volume_serial", wintypes.DWORD),
            ("size_high", wintypes.DWORD),
            ("size_low", wintypes.DWORD),
            ("link_count", wintypes.DWORD),
            ("file_index_high", wintypes.DWORD),
            ("file_index_low", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.GetFileInformationByHandle.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ByHandleFileInformation),
    ]
    kernel32.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel32.SetFilePointerEx.argtypes = [
        wintypes.HANDLE,
        ctypes.c_longlong,
        ctypes.POINTER(ctypes.c_longlong),
        wintypes.DWORD,
    ]
    kernel32.SetFilePointerEx.restype = wintypes.BOOL
    kernel32.ReadFile.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    kernel32.ReadFile.restype = wintypes.BOOL
    kernel32.SetHandleInformation.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    kernel32.SetHandleInformation.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32, ByHandleFileInformation


def _windows_handle_value(handle: Any) -> int | None:
    value = handle if isinstance(handle, int) else getattr(handle, "value", None)
    return None if value in {None, ctypes.c_void_p(-1).value} else int(value)


def _open_windows(
    path: Path,
) -> tuple[int, tuple[int, int], int, str, int]:
    kernel32, _information_type = _windows_api()
    handle = kernel32.CreateFileW(
        str(path),
        0x80000000 | 0x00000080,  # GENERIC_READ | FILE_READ_ATTRIBUTES
        0x00000001,  # FILE_SHARE_READ only; deny write/delete sharing
        None,
        3,  # OPEN_EXISTING
        0x00200000 | 0x08000000,  # OPEN_REPARSE_POINT | SEQUENTIAL_SCAN
        None,
    )
    value = _windows_handle_value(handle)
    if value is None:
        raise _fail("project_update_git_runner_unavailable")
    try:
        if not kernel32.SetHandleInformation(handle, 0x00000001, 0):
            raise _fail("project_update_git_runner_unavailable")
        identity, size, digest, link_count = _inspect_windows_handle(value)
        return value, identity, size, digest, link_count
    except BaseException:
        kernel32.CloseHandle(handle)
        raise


def _inspect_windows_handle(
    handle: int,
) -> tuple[tuple[int, int], int, str, int]:
    from ctypes import wintypes

    kernel32, information_type = _windows_api()
    before = information_type()
    if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(before)):
        raise _fail("project_update_git_runner_drift")
    size = (int(before.size_high) << 32) | int(before.size_low)
    file_identity = (int(before.file_index_high) << 32) | int(before.file_index_low)
    if (
        before.attributes & (0x00000010 | 0x00000400)
        or not (1 <= int(before.link_count) <= 64)
        or file_identity <= 0
        or not (1 <= size <= MAX_EXECUTABLE_BYTES)
    ):
        raise _fail("project_update_git_runner_unsafe")
    if not kernel32.SetFilePointerEx(handle, 0, None, 0):
        raise _fail("project_update_git_runner_drift")
    digest = hashlib.sha256()
    remaining = size
    while remaining:
        requested = min(1024 * 1024, remaining)
        buffer = ctypes.create_string_buffer(requested)
        count = wintypes.DWORD(0)
        if not kernel32.ReadFile(
            handle, buffer, requested, ctypes.byref(count), None
        ):
            raise _fail("project_update_git_runner_drift")
        actual = int(count.value)
        if actual <= 0 or actual > requested:
            raise _fail("project_update_git_runner_drift")
        digest.update(buffer.raw[:actual])
        remaining -= actual
    after = information_type()
    if (
        not kernel32.GetFileInformationByHandle(handle, ctypes.byref(after))
        or int(after.volume_serial) != int(before.volume_serial)
        or int(after.file_index_high) != int(before.file_index_high)
        or int(after.file_index_low) != int(before.file_index_low)
        or int(after.size_high) != int(before.size_high)
        or int(after.size_low) != int(before.size_low)
        or int(after.link_count) != int(before.link_count)
    ):
        raise _fail("project_update_git_runner_drift")
    return (
        (int(after.volume_serial), file_identity),
        size,
        "sha256:" + digest.hexdigest(),
        int(after.link_count),
    )


def _close_windows_handle(handle: int) -> bool:
    kernel32, _information_type = _windows_api()
    return bool(kernel32.CloseHandle(handle))


__all__ = [
    "ProjectUpdateGitRunnerError",
    "TrustedGitPrivateBinding",
    "TrustedProjectUpdateGitRunner",
    "load_private_binding_bytes",
]
