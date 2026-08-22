"""Read-only, content-free Git backup planning for one WOM archive.

This module deliberately has no commit, push, fetch, checkout, reset, merge,
rebase, clean, delete, lock-creation, or receipt-writing primitive.  It may ask
the configured Git transport for one exact ref with ``ls-remote`` and otherwise
uses local interrogator commands only.
"""

from __future__ import annotations

import ctypes
import contextvars
import hashlib
import json
import os
import re
import signal
import shutil
import stat
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlsplit

from . import archive_services


GIT_BACKUP_PLAN_SCHEMA = "wom-kit/git-backup-plan/v0.1"
GIT_BACKUP_RECONCILE_PLAN_SCHEMA = "wom-kit/git-backup-reconcile-plan/v0.1"
GIT_BACKUP_PLAN_DEFAULT_MAX_CHANGES = 20_000
GIT_BACKUP_PLAN_MAX_CHANGES = 100_000
GIT_BACKUP_PLAN_DEFAULT_MAX_CHANGED_BYTES = 512 * 1024 * 1024
GIT_BACKUP_PLAN_MAX_CHANGED_BYTES = 2 * 1024 * 1024 * 1024
GIT_BACKUP_PLAN_MAX_FILE_BYTES = 64 * 1024 * 1024
GIT_BACKUP_PLAN_MAX_GIT_OUTPUT_BYTES = 64 * 1024 * 1024
GIT_BACKUP_PLAN_MAX_TRACKED_PATHS = 200_000
GIT_BACKUP_PLAN_MAX_RECEIPTS = 100_000
GIT_BACKUP_PLAN_MAX_RECEIPT_BYTES = 4 * 1024 * 1024
GIT_BACKUP_PLAN_MAX_RECEIPT_TOTAL_BYTES = 256 * 1024 * 1024
GIT_BACKUP_PLAN_MAX_PREFLIGHT_ENTRIES = 500_000
GIT_BACKUP_PLAN_MAX_GIT_EXECUTABLE_BYTES = 128 * 1024 * 1024
GIT_BACKUP_PLAN_MAX_BLOB_BATCH_BYTES = 64 * 1024 * 1024
GIT_BACKUP_REMOTE_TIMEOUT_SECONDS = 30
GIT_BACKUP_LOCAL_TIMEOUT_SECONDS = 60
GIT_BACKUP_REMOTE_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
GIT_BACKUP_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}")
GIT_BACKUP_OPERATION_MARKERS = (
    "MERGE_HEAD",
    "AUTO_MERGE",
    "MERGE_AUTOSTASH",
    "CHERRY_PICK_HEAD",
    "REVERT_HEAD",
    "REBASE_HEAD",
    "BISECT_START",
    "BISECT_LOG",
    "rebase-apply",
    "rebase-merge",
    "sequencer",
    "index.lock",
)
GIT_BACKUP_TRANSPORT_PROTOCOLS = ("https",)
GIT_BACKUP_CREDENTIAL_MODES = ("anonymous", "stored")


@dataclass(frozen=True)
class _StatusRecord:
    record_kind: str
    xy: str
    path: str
    original_path: str | None = None
    directory_summary: bool = False


@dataclass(frozen=True)
class _FileObservation:
    state: str
    size: int | None = None
    sha256: str | None = None
    identity: tuple[int, int, int, int, int] | None = None


@dataclass(frozen=True)
class _ReceiptInventory:
    state: str
    file_count: int
    total_bytes: int
    inventory_sha256: str | None
    stability_sha256: str | None


@dataclass(frozen=True)
class _ReceiptInventoryCache:
    state: str
    # Private relative paths never cross the public result boundary. Directory
    # identities detect additions/removals; file identities detect body or
    # metadata drift without reopening every historical receipt body.
    entries: tuple[tuple[str, str, tuple[int, int, int, int, int, int]], ...]


@dataclass(frozen=True)
class _PinnedGitExecutable:
    path: str
    sha256: str
    identity: tuple[int, int, int, int, int]


_PINNED_GIT_EXECUTABLE: contextvars.ContextVar[_PinnedGitExecutable | None] = (
    contextvars.ContextVar("wom_git_backup_pinned_git", default=None)
)


class _GitBackupPlanProgress:
    """Publish content-free planner stages and bounded heartbeats.

    Progress is deliberately outside the deterministic plan document.  A
    broken observer must not change a read-only inspection result, so callback
    failures are counted and suppressed.
    """

    def __init__(
        self,
        hook: Callable[[Mapping[str, Any]], None] | None,
        *,
        operation: str,
    ) -> None:
        self.hook = hook
        self.operation = operation
        self.started = time.monotonic()
        self.stage = "starting"
        self.sequence = 0
        self.failure_count = 0
        self._lock = threading.Lock()

    def _publish(self, event_kind: str, stage: str) -> None:
        with self._lock:
            self.stage = stage
            self.sequence += 1
            document = {
                "schema": "wom-kit/git-backup-progress/v1",
                "operation": self.operation,
                "event": event_kind,
                "stage": stage,
                "sequence": self.sequence,
                "elapsed_seconds": round(max(0.0, time.monotonic() - self.started), 3),
                "private_values_echoed": False,
            }
            if self.hook is None:
                return
            try:
                self.hook(document)
            except Exception:  # noqa: BLE001 - observability cannot alter the plan.
                self.failure_count += 1

    def status(self, stage: str) -> None:
        self._publish("status", stage)

    def heartbeat(self) -> None:
        self._publish("heartbeat", self.stage)


def _run_plan_with_heartbeats(
    progress: _GitBackupPlanProgress,
    operation: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    """Run one planner call while emitting at least one event every 5 seconds."""

    if progress.hook is None:
        return operation()
    context = contextvars.copy_context()
    completed = threading.Event()
    result_box: list[dict[str, Any]] = []
    failure_box: list[BaseException] = []

    def run() -> None:
        try:
            result_box.append(context.run(operation))
        except BaseException as exc:  # preserve the original in-process failure
            failure_box.append(exc)
        finally:
            completed.set()

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    while not completed.wait(timeout=5.0):
        progress.heartbeat()
    worker.join()
    if failure_box:
        raise failure_box[0]
    if not result_box:
        raise RuntimeError("git_backup_progress_worker_failed")
    return result_box[0]


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return _sha256_bytes(encoded)


def _external_path_components_are_real(path: Path) -> bool:
    try:
        absolute = path.resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    anchor = Path(absolute.anchor)
    current = anchor
    for part in absolute.parts[1:]:
        current = current / part
        try:
            item_stat = os.lstat(current)
        except OSError:
            return False
        if (
            stat.S_ISLNK(item_stat.st_mode)
            or (
                reparse_flag
                and getattr(item_stat, "st_file_attributes", 0) & reparse_flag
            )
        ):
            return False
    return True


def _pin_git_at(path: Path) -> _PinnedGitExecutable | None:
    try:
        absolute = path.resolve(strict=True)
        before = os.lstat(absolute)
    except (OSError, RuntimeError, ValueError):
        return None
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if (
        not absolute.is_absolute()
        or not stat.S_ISREG(before.st_mode)
        or stat.S_ISLNK(before.st_mode)
        or (reparse_flag and getattr(before, "st_file_attributes", 0) & reparse_flag)
        or not _external_path_components_are_real(absolute)
        or before.st_size < 0
        or before.st_size > GIT_BACKUP_PLAN_MAX_GIT_EXECUTABLE_BYTES
    ):
        return None
    descriptor: int | None = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(absolute, flags)
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_size != before.st_size
            or (before.st_ino and opened.st_ino and before.st_ino != opened.st_ino)
            or (before.st_dev and opened.st_dev and before.st_dev != opened.st_dev)
        ):
            return None
        digest = hashlib.sha256()
        total = 0
        while total <= GIT_BACKUP_PLAN_MAX_GIT_EXECUTABLE_BYTES:
            chunk = os.read(
                descriptor,
                min(
                    64 * 1024,
                    GIT_BACKUP_PLAN_MAX_GIT_EXECUTABLE_BYTES + 1 - total,
                ),
            )
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
        after = os.fstat(descriptor)
        if (
            total != opened.st_size
            or after.st_size != opened.st_size
            or after.st_mtime_ns != opened.st_mtime_ns
            or after.st_ctime_ns != opened.st_ctime_ns
            or (opened.st_ino and after.st_ino and opened.st_ino != after.st_ino)
            or (opened.st_dev and after.st_dev and opened.st_dev != after.st_dev)
        ):
            return None
        return _PinnedGitExecutable(
            path=str(absolute),
            sha256="sha256:" + digest.hexdigest(),
            identity=(
                int(after.st_dev),
                int(after.st_ino),
                int(after.st_size),
                int(after.st_mtime_ns),
                int(after.st_ctime_ns),
            ),
        )
    except (OSError, OverflowError, ValueError):
        return None
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _pin_git_executable() -> _PinnedGitExecutable | None:
    candidate = shutil.which("git")
    if not candidate:
        return None
    return _pin_git_at(Path(candidate))


def _git_command(root: Path | None, args: list[str]) -> list[str]:
    pinned = _PINNED_GIT_EXECUTABLE.get()
    if pinned is None:
        raise RuntimeError("git_executable_not_pinned")
    git_null_path = "/dev/null" if os.name == "nt" else os.devnull
    command = [
        pinned.path,
        "--no-optional-locks",
        "--no-replace-objects",
        "-c",
        "core.fsmonitor=false",
        "-c",
        f"core.hooksPath={git_null_path}",
        "-c",
        f"core.attributesFile={git_null_path}",
        "-c",
        f"core.excludesFile={git_null_path}",
    ]
    if root is not None:
        command.extend(["-C", str(root)])
    command.extend(args)
    return command


def _local_git_environment() -> dict[str, str]:
    environment = archive_services.wom_kit_project_update_git_environment()
    environment["GIT_ATTR_NOSYSTEM"] = "1"
    return environment


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _close_windows_handle(handle: Any | None) -> bool:
    if os.name != "nt" or handle is None:
        return True
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    return bool(close_handle(handle))


def _assign_windows_kill_on_close_job(
    process: subprocess.Popen[bytes],
) -> Any | None:
    """Assign a suspended Git transport and descendants to one kill-on-close job."""

    if os.name != "nt":
        return None
    from ctypes import wintypes

    class JobObjectBasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IoCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class JobObjectExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JobObjectBasicLimitInformation),
            ("IoInfo", IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_job = kernel32.CreateJobObjectW
    create_job.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    create_job.restype = wintypes.HANDLE
    set_job_information = kernel32.SetInformationJobObject
    set_job_information.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    set_job_information.restype = wintypes.BOOL
    assign_process = kernel32.AssignProcessToJobObject
    assign_process.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    assign_process.restype = wintypes.BOOL

    job = create_job(None, None)
    if not job:
        return None
    information = JobObjectExtendedLimitInformation()
    information.BasicLimitInformation.LimitFlags = 0x00002000
    if not set_job_information(
        job,
        9,
        ctypes.byref(information),
        ctypes.sizeof(information),
    ):
        _close_windows_handle(job)
        return None
    process_handle = wintypes.HANDLE(int(process._handle))  # type: ignore[attr-defined]
    if not assign_process(job, process_handle):
        _close_windows_handle(job)
        return None
    return job


def _resume_windows_process(process: subprocess.Popen[bytes]) -> bool:
    if os.name != "nt":
        return True
    from ctypes import wintypes

    class ThreadEntry32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ThreadID", wintypes.DWORD),
            ("th32OwnerProcessID", wintypes.DWORD),
            ("tpBasePri", wintypes.LONG),
            ("tpDeltaPri", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_snapshot = kernel32.CreateToolhelp32Snapshot
    create_snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    create_snapshot.restype = wintypes.HANDLE
    thread_first = kernel32.Thread32First
    thread_first.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry32)]
    thread_first.restype = wintypes.BOOL
    thread_next = kernel32.Thread32Next
    thread_next.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry32)]
    thread_next.restype = wintypes.BOOL
    open_thread = kernel32.OpenThread
    open_thread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    open_thread.restype = wintypes.HANDLE
    resume_thread = kernel32.ResumeThread
    resume_thread.argtypes = [wintypes.HANDLE]
    resume_thread.restype = wintypes.DWORD

    snapshot = create_snapshot(0x00000004, 0)
    if snapshot == wintypes.HANDLE(-1).value:
        return False
    try:
        entry = ThreadEntry32()
        entry.dwSize = ctypes.sizeof(entry)
        found = bool(thread_first(snapshot, ctypes.byref(entry)))
        while found:
            if int(entry.th32OwnerProcessID) == process.pid:
                thread = open_thread(0x0002, False, entry.th32ThreadID)
                if not thread:
                    return False
                try:
                    return resume_thread(thread) != 0xFFFFFFFF
                finally:
                    _close_windows_handle(thread)
            found = bool(thread_next(snapshot, ctypes.byref(entry)))
    finally:
        _close_windows_handle(snapshot)
    return False


def _terminate_windows_job(job: Any | None) -> bool:
    if os.name != "nt" or job is None:
        return True
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    terminate_job = kernel32.TerminateJobObject
    terminate_job.argtypes = [wintypes.HANDLE, wintypes.UINT]
    terminate_job.restype = wintypes.BOOL
    wait_for_single_object = kernel32.WaitForSingleObject
    wait_for_single_object.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    wait_for_single_object.restype = wintypes.DWORD
    terminated = bool(terminate_job(job, 1))
    wait_result = wait_for_single_object(job, 5_000) if terminated else 0xFFFFFFFF
    closed = _close_windows_handle(job)
    return terminated and wait_result == 0 and closed


def _kill_process_tree(
    process: subprocess.Popen[bytes],
    windows_job: Any | None,
) -> bool:
    if os.name == "nt":
        job_closed = _terminate_windows_job(windows_job)
        if windows_job is None:
            try:
                process.kill()
            except OSError:
                pass
        return job_closed
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (OSError, ProcessLookupError):
        pass
    try:
        process.kill()
    except OSError:
        pass
    return True


def _run_transport_capped(
    command: list[str],
    *,
    environment: dict[str, str],
    timeout_seconds: int,
    max_output_bytes: int,
) -> tuple[int, bytes] | None:
    """Run one transport query with bounded output and descendant containment."""

    if timeout_seconds <= 0 or max_output_bytes < 0:
        return None
    process_options: dict[str, Any] = {}
    if os.name == "nt":
        process_options["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000004
        )
    else:
        process_options["start_new_session"] = True
    try:
        process = subprocess.Popen(
            command,
            cwd=Path(tempfile.gettempdir()).resolve(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=environment,
            **process_options,
        )
    except (OSError, ValueError):
        return None
    windows_job = _assign_windows_kill_on_close_job(process)
    if os.name == "nt" and (
        windows_job is None or not _resume_windows_process(process)
    ):
        _kill_process_tree(process, windows_job)
        try:
            process.wait(timeout=1)
        except (OSError, subprocess.SubprocessError):
            pass
        if process.stdout is not None:
            process.stdout.close()
        return None
    if process.stdout is None:
        _kill_process_tree(process, windows_job)
        process.wait()
        return None

    output_box: list[bytes] = []
    read_failed = threading.Event()
    overflow = threading.Event()

    def read_capped() -> None:
        chunks: list[bytes] = []
        total = 0
        try:
            while total <= max_output_bytes:
                chunk = os.read(
                    process.stdout.fileno(),
                    min(64 * 1024, max_output_bytes + 1 - total),
                )
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
            if total > max_output_bytes:
                overflow.set()
            output_box.append(b"".join(chunks))
        except (OSError, ValueError):
            read_failed.set()

    reader = threading.Thread(target=read_capped, daemon=True)
    reader.start()
    timed_out = False
    containment_failed = False
    try:
        return_code = process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_process_tree(process, windows_job)
        windows_job = None
        try:
            return_code = process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            return_code = -1
    else:
        # The direct Git parent may exit while a credential/proxy helper keeps
        # the inherited stdout handle and continues running.  Tear down the
        # containment boundary immediately, before waiting for the reader, so
        # no descendant receives a post-parent execution window.
        if os.name == "nt":
            containment_failed = not _terminate_windows_job(windows_job)
            windows_job = None
        else:
            containment_failed = not _kill_process_tree(process, None)
    reader.join(timeout=2)
    if reader.is_alive() or overflow.is_set() or read_failed.is_set():
        _kill_process_tree(process, windows_job)
        windows_job = None
    try:
        process.stdout.close()
    except OSError:
        pass
    if (
        timed_out
        or containment_failed
        or reader.is_alive()
        or overflow.is_set()
        or read_failed.is_set()
    ):
        return None
    return return_code, output_box[0] if output_box else b""


def _local_git_raw(
    root: Path,
    args: list[str],
    *,
    max_output_bytes: int = GIT_BACKUP_PLAN_MAX_GIT_OUTPUT_BYTES,
    timeout_seconds: int = GIT_BACKUP_LOCAL_TIMEOUT_SECONDS,
) -> tuple[int, bytes] | None:
    return archive_services._wom_kit_project_update_run_capped(
        _git_command(root, args),
        environment=_local_git_environment(),
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
    )


def _local_git_text(
    root: Path,
    args: list[str],
    *,
    max_output_bytes: int = 64 * 1024,
) -> tuple[int, str] | None:
    result = _local_git_raw(root, args, max_output_bytes=max_output_bytes)
    if result is None:
        return None
    return_code, raw = result
    try:
        text = raw.decode("utf-8", errors="strict").rstrip("\r\n")
    except UnicodeError:
        return None
    return return_code, text


def _safe_remote_url(value: str) -> bool:
    if (
        not value
        or len(value.encode("utf-8", errors="surrogatepass")) > 4096
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
        or value.startswith("-")
    ):
        return False
    parsed = urlsplit(value)
    if parsed.scheme in GIT_BACKUP_TRANSPORT_PROTOCOLS:
        try:
            port = parsed.port
        except ValueError:
            return False
        return bool(
            parsed.hostname
            and parsed.password is None
            and not parsed.query
            and not parsed.fragment
            and (port is None or 0 < port < 65_536)
            and parsed.username is None
        )
    return False


def _configured_remote_url(root: Path, remote_name: str) -> str | None:
    result = _local_git_text(
        root,
        ["remote", "get-url", "--all", remote_name],
        max_output_bytes=16 * 1024,
    )
    if result is None or result[0] != 0:
        return None
    values = result[1].splitlines()
    if len(values) != 1 or not _safe_remote_url(values[0]):
        return None
    return values[0]


def _query_remote_ref(url: str, full_ref: str) -> tuple[str, str | None]:
    pinned = _PINNED_GIT_EXECUTABLE.get()
    if pinned is None:
        return "unavailable", None
    git_null_path = "/dev/null" if os.name == "nt" else os.devnull
    command = [
        pinned.path,
        "--no-optional-locks",
        "--no-replace-objects",
        "-c",
        "core.fsmonitor=false",
        "-c",
        f"core.hooksPath={git_null_path}",
        "-c",
        "protocol.allow=never",
        "-c",
        "protocol.https.allow=always",
        "-c",
        "credential.interactive=never",
        "-c",
        "credential.helper=",
        "-c",
        "core.askPass=",
        "-c",
        "http.proxy=",
        "ls-remote",
        "--quiet",
        "--refs",
        "--exit-code",
        url,
        full_ref,
    ]
    environment = _local_git_environment()
    for key in list(environment):
        upper_key = key.upper()
        if upper_key.endswith("_PROXY") or upper_key in {
            "NO_PROXY",
            "SSH_ASKPASS",
            "SSH_ASKPASS_REQUIRE",
            "SSLKEYLOGFILE",
        }:
            environment.pop(key, None)
    neutral_root = Path(tempfile.gettempdir()).resolve()
    try:
        if os.path.lexists(neutral_root / ".git"):
            return "unavailable", None
    except OSError:
        return "unavailable", None
    neutral_home = neutral_root / (
        f".wom-git-backup-no-home-{os.getpid()}-{time.monotonic_ns()}"
    )
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": git_null_path,
            "GIT_CEILING_DIRECTORIES": str(neutral_root),
            "HOME": str(neutral_home),
            "USERPROFILE": str(neutral_home),
            "XDG_CONFIG_HOME": str(neutral_home),
            "GCM_INTERACTIVE": "never",
        }
    )
    result = _run_transport_capped(
        command,
        # Inherited GIT_ASKPASS/GIT_PROXY_COMMAND/GIT_SSH* values can execute
        # arbitrary helpers.  The read-only planner deliberately strips every
        # inherited GIT_* override and fails closed when non-interactive auth is
        # unavailable.  Normal SSH agent variables are not Git overrides.
        environment=environment,
        timeout_seconds=GIT_BACKUP_REMOTE_TIMEOUT_SECONDS,
        max_output_bytes=64 * 1024,
    )
    if result is None:
        return "unavailable", None
    return_code, raw = result
    if return_code == 2 and raw == b"":
        return "target_ref_missing", None
    if return_code != 0:
        return "unavailable", None
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeError:
        return "invalid_response", None
    rows = [row for row in text.splitlines() if row]
    if len(rows) != 1:
        return "invalid_response", None
    fields = rows[0].split("\t")
    if (
        len(fields) != 2
        or fields[1] != full_ref
        or re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", fields[0]) is None
    ):
        return "invalid_response", None
    return "present", fields[0].lower()


def _query_remote_ref_with_stored_credentials(
    root: Path,
    remote_name: str,
    full_ref: str,
) -> tuple[str, str | None]:
    """Query one exact HTTPS ref through already configured local credentials.

    The remote name and ref are validated before this boundary.  Interactive
    prompts remain disabled, stdout is bounded, stderr is discarded, and no
    configured URL or credential value crosses the result boundary.  Unlike
    the anonymous observer, this route intentionally permits the user's
    existing global credential helper so private repositories remain usable.
    """

    pinned = _PINNED_GIT_EXECUTABLE.get()
    if pinned is None:
        return "unavailable", None
    command = _git_command(
        root,
        [
            "-c",
            "protocol.allow=never",
            "-c",
            "protocol.https.allow=always",
            "-c",
            "credential.interactive=never",
            "ls-remote",
            "--quiet",
            "--refs",
            "--exit-code",
            remote_name,
            full_ref,
        ],
    )
    environment = _local_git_environment()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment["GCM_INTERACTIVE"] = "never"
    result = _run_transport_capped(
        command,
        environment=environment,
        timeout_seconds=GIT_BACKUP_REMOTE_TIMEOUT_SECONDS,
        max_output_bytes=64 * 1024,
    )
    if result is None:
        return "unavailable", None
    return_code, raw = result
    if return_code == 2 and raw == b"":
        return "target_ref_missing", None
    if return_code != 0:
        return "unavailable", None
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeError:
        return "invalid_response", None
    rows = [row for row in text.splitlines() if row]
    if len(rows) != 1:
        return "invalid_response", None
    fields = rows[0].split("\t")
    if (
        len(fields) != 2
        or fields[1] != full_ref
        or re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", fields[0]) is None
    ):
        return "invalid_response", None
    return "present", fields[0].lower()


def _decode_git_path(raw: bytes, *, directory_summary: bool = False) -> str | None:
    try:
        value = raw.decode("utf-8", errors="strict")
    except UnicodeError:
        return None
    if directory_summary and value.endswith("/"):
        value = value[:-1]
    if (
        not value
        or "\x00" in value
        or len(value.encode("utf-8")) > 4096
    ):
        return None
    pure = PurePosixPath(value)
    if (
        pure.is_absolute()
        or pure.as_posix() != value
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        return None
    return value


def _parse_status(raw: bytes) -> list[_StatusRecord] | None:
    if raw == b"":
        return []
    if not raw.endswith(b"\x00"):
        return None
    fields = raw[:-1].split(b"\x00")
    if any(field == b"" for field in fields):
        return None
    result: list[_StatusRecord] = []
    index = 0
    while index < len(fields):
        record = fields[index]
        index += 1
        if record.startswith(b"1 "):
            parts = record.split(b" ", 8)
            if len(parts) != 9 or len(parts[1]) != 2:
                return None
            path = _decode_git_path(parts[8])
            if path is None:
                return None
            try:
                xy = parts[1].decode("ascii", errors="strict")
            except UnicodeError:
                return None
            result.append(
                _StatusRecord(record_kind="ordinary", xy=xy, path=path)
            )
            continue
        if record.startswith(b"2 "):
            parts = record.split(b" ", 9)
            if len(parts) != 10 or len(parts[1]) != 2 or index >= len(fields):
                return None
            path = _decode_git_path(parts[9])
            original_path = _decode_git_path(fields[index])
            index += 1
            if path is None or original_path is None or path == original_path:
                return None
            try:
                xy = parts[1].decode("ascii", errors="strict")
            except UnicodeError:
                return None
            result.append(
                _StatusRecord(
                    record_kind="rename_or_copy",
                    xy=xy,
                    path=path,
                    original_path=original_path,
                )
            )
            continue
        if record.startswith(b"u "):
            parts = record.split(b" ", 10)
            if len(parts) != 11 or len(parts[1]) != 2:
                return None
            path = _decode_git_path(parts[10])
            if path is None:
                return None
            try:
                xy = parts[1].decode("ascii", errors="strict")
            except UnicodeError:
                return None
            result.append(
                _StatusRecord(record_kind="unmerged", xy=xy, path=path)
            )
            continue
        if record.startswith((b"? ", b"! ")):
            ignored = record.startswith(b"! ")
            raw_path = record[2:]
            directory_summary = raw_path.endswith(b"/")
            path = _decode_git_path(
                raw_path,
                directory_summary=directory_summary,
            )
            if path is None:
                return None
            result.append(
                _StatusRecord(
                    record_kind="ignored" if ignored else "untracked",
                    xy="!!" if ignored else "??",
                    path=path,
                    directory_summary=directory_summary,
                )
            )
            continue
        return None
    return result


def _parse_tree(
    raw: bytes,
) -> tuple[dict[str, tuple[str, str]], int, int] | None:
    if raw == b"":
        return {}, 0, 0
    if not raw.endswith(b"\x00"):
        return None
    entries: dict[str, tuple[str, str]] = {}
    symlink_count = 0
    gitlink_count = 0
    for record in raw[:-1].split(b"\x00"):
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode, object_type, raw_oid = metadata.split(b" ", 2)
            mode_text = mode.decode("ascii")
            object_type_text = object_type.decode("ascii")
            oid = raw_oid.decode("ascii").lower()
        except (UnicodeError, ValueError):
            return None
        path = _decode_git_path(raw_path)
        if (
            path is None
            or path in entries
            or len(entries) >= GIT_BACKUP_PLAN_MAX_TRACKED_PATHS
            or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", oid) is None
        ):
            return None
        if mode_text in {"100644", "100755"} and object_type_text == "blob":
            pass
        elif mode_text == "120000" and object_type_text == "blob":
            symlink_count += 1
        elif mode_text == "160000" and object_type_text == "commit":
            gitlink_count += 1
        else:
            return None
        entries[path] = (mode_text, oid)
    return entries, symlink_count, gitlink_count


def _parse_index(
    raw: bytes,
) -> tuple[dict[str, list[tuple[str, str, int]]], int] | None:
    if raw == b"":
        return {}, 0
    if not raw.endswith(b"\x00"):
        return None
    entries: dict[str, list[tuple[str, str, int]]] = {}
    gitlink_count = 0
    count = 0
    for record in raw[:-1].split(b"\x00"):
        try:
            metadata, raw_path = record.split(b"\t", 1)
            raw_mode, raw_oid, raw_stage = metadata.split(b" ", 2)
            mode = raw_mode.decode("ascii")
            oid = raw_oid.decode("ascii").lower()
            stage = int(raw_stage.decode("ascii"))
        except (UnicodeError, ValueError):
            return None
        path = _decode_git_path(raw_path)
        if (
            path is None
            or count >= GIT_BACKUP_PLAN_MAX_TRACKED_PATHS * 4
            or stage not in {0, 1, 2, 3}
            or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", oid) is None
            or mode not in {"100644", "100755", "120000", "160000"}
        ):
            return None
        if mode == "160000":
            gitlink_count += 1
        entries.setdefault(path, []).append((mode, oid, stage))
        count += 1
    if any(
        len(rows) != len(set(rows))
        for rows in entries.values()
    ):
        return None
    return entries, gitlink_count


def _parse_flags(raw: bytes) -> dict[str, str] | None:
    if raw == b"":
        return {}
    if not raw.endswith(b"\x00"):
        return None
    result: dict[str, str] = {}
    for record in raw[:-1].split(b"\x00"):
        if len(record) < 3 or record[1:2] != b" ":
            return None
        try:
            flag = record[:1].decode("ascii")
        except UnicodeError:
            return None
        path = _decode_git_path(record[2:])
        if path is None or path in result:
            return None
        result[path] = flag
    return result


def _changed_path_attributes_are_inert(
    root: Path,
    relative_paths: Iterable[str],
) -> bool | None:
    """Return whether changed paths avoid executable/encoding attributes.

    ``check-attr`` only parses attributes; it does not run clean/smudge/process
    filters.  The same hardened Git command boundary disables global attribute
    files, fsmonitor, hooks, and optional locks.
    """

    paths = sorted(set(relative_paths))
    if not paths:
        return True
    encoded_paths: list[bytes] = []
    for relative_path in paths:
        try:
            encoded = relative_path.encode("utf-8", errors="strict")
        except UnicodeError:
            return None
        encoded_paths.append(encoded)
    request = b"\x00".join(encoded_paths) + b"\x00"
    if len(request) > 1024 * 1024:
        return None
    completed = archive_services._wom_kit_project_update_run_capped(
        _git_command(
            root,
            [
                "check-attr",
                "-z",
                "--stdin",
                "filter",
                "working-tree-encoding",
            ],
        ),
        environment=_local_git_environment(),
        timeout_seconds=GIT_BACKUP_LOCAL_TIMEOUT_SECONDS,
        max_output_bytes=min(
            GIT_BACKUP_PLAN_MAX_GIT_OUTPUT_BYTES,
            len(request) * 8 + 1024,
        ),
        input_bytes=request,
    )
    if completed is None or completed[0] != 0:
        return None
    raw = completed[1]
    if not raw.endswith(b"\x00"):
        return None
    fields = raw[:-1].split(b"\x00")
    if len(fields) != len(paths) * 6:
        return None
    observed: dict[tuple[str, str], str] = {}
    for offset in range(0, len(fields), 3):
        try:
            path = fields[offset].decode("utf-8", errors="strict")
            attribute = fields[offset + 1].decode("ascii", errors="strict")
            value = fields[offset + 2].decode("utf-8", errors="strict")
        except UnicodeError:
            return None
        key = (path, attribute)
        if (
            path not in paths
            or attribute not in {"filter", "working-tree-encoding"}
            or key in observed
        ):
            return None
        observed[key] = value
    expected_keys = {
        (path, attribute)
        for path in paths
        for attribute in ("filter", "working-tree-encoding")
    }
    if set(observed) != expected_keys:
        return None
    return all(value in {"unspecified", "unset"} for value in observed.values())


def _config_value_state(root: Path, key: str, *, boolean: bool = False) -> str:
    args = ["config", "--local"]
    if boolean:
        args.append("--type=bool")
    args.extend(["--get", key])
    result = _local_git_text(root, args, max_output_bytes=8 * 1024)
    if result is None:
        return "invalid"
    return_code, value = result
    if return_code == 1 and value == "":
        return "absent"
    if return_code != 0:
        return "invalid"
    if boolean:
        normalized = value.strip().casefold()
        return normalized if normalized in {"true", "false"} else "invalid"
    return "present"


def _promisor_config_state(root: Path) -> str:
    result = _local_git_text(
        root,
        ["config", "--local", "--get-regexp", r"^remote\..*\.promisor$"],
        max_output_bytes=64 * 1024,
    )
    if result is None:
        return "invalid"
    if result[0] == 1 and result[1] == "":
        return "absent"
    return "present" if result[0] == 0 else "invalid"


def _validate_full_branch_ref(value: str) -> bool:
    return bool(
        value.startswith("refs/heads/")
        and len(value.encode("utf-8")) <= 1024
        and not any(character in value for character in "*?[")
        and not any(ord(character) < 32 or ord(character) == 127 for character in value)
    )


def _resolve_target_ref(root: Path, branch: str | None) -> tuple[str | None, str]:
    symbolic = _local_git_text(
        root,
        ["symbolic-ref", "--quiet", "HEAD"],
        max_output_bytes=8 * 1024,
    )
    if symbolic is None:
        return None, "invalid"
    if symbolic[0] == 1 and symbolic[1] == "":
        return None, "detached"
    if symbolic[0] != 0 or not _validate_full_branch_ref(symbolic[1]):
        return None, "invalid"
    current_ref = symbolic[1]
    if branch is None:
        return current_ref, "symbolic_head"
    if (
        not branch
        or branch.startswith("-")
        or branch.startswith("refs/")
        or len(branch.encode("utf-8")) > 1000
    ):
        return None, "invalid"
    checked = _local_git_text(
        root,
        ["check-ref-format", "--branch", branch],
        max_output_bytes=8 * 1024,
    )
    if checked is None or checked[0] != 0 or checked[1] != branch:
        return None, "invalid"
    return f"refs/heads/{branch}", (
        "symbolic_head" if f"refs/heads/{branch}" == current_ref else "explicit_other_branch"
    )


def _archive_attribute_preflight(root: Path) -> list[str]:
    """Detect relevant attribute files without walking the whole archive.

    The former implementation recursively ``scandir``/``lstat``-ed every
    ignored object and scratch artifact, twice per plan.  On real archives
    that turned a sub-second Git projection into a multi-minute preflight.
    ``git ls-files`` can inventory the exact tracked, untracked, and ignored
    attribute filename set without invoking content filters or reading file
    bodies, so the safety check remains fail-closed and bounded by Git's one
    index/worktree projection.
    """

    git_dir = root / ".git"
    try:
        git_stat = os.lstat(git_dir)
    except OSError:
        return ["git_metadata_boundary_not_local_or_real"]
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if (
        not stat.S_ISDIR(git_stat.st_mode)
        or stat.S_ISLNK(git_stat.st_mode)
        or (reparse_flag and getattr(git_stat, "st_file_attributes", 0) & reparse_flag)
    ):
        return ["git_metadata_boundary_not_local_or_real"]
    try:
        if os.path.lexists(git_dir / "info" / "attributes"):
            return ["git_info_attributes_not_supported"]
    except OSError:
        return ["git_info_attributes_state_unavailable"]
    pathspecs = [".gitattributes", ":(glob)**/.gitattributes"]
    projections = (
        (
            ["ls-files", "--cached", "-z", "--", *pathspecs],
            "tracked_repository_attributes_not_supported",
        ),
        (
            ["ls-files", "--others", "--exclude-standard", "-z", "--", *pathspecs],
            "repository_attributes_not_supported",
        ),
        (
            ["ls-files", "--others", "--ignored", "--exclude-standard", "-z", "--", *pathspecs],
            "repository_attributes_not_supported",
        ),
    )
    for args, blocker in projections:
        result = _local_git_raw(
            root,
            args,
            max_output_bytes=GIT_BACKUP_PLAN_MAX_GIT_OUTPUT_BYTES,
        )
        if result is None or result[0] != 0:
            return ["archive_attribute_preflight_scan_failed"]
        if result[1]:
            return [blocker]
    return []


def _tracked_attribute_preflight(root: Path) -> list[str]:
    # Consolidated into `_archive_attribute_preflight` so one projection
    # covers tracked, untracked, ignored, and .git/info attribute sources.
    return []


def _git_metadata_is_local_real(root: Path) -> bool:
    git_dir = root / ".git"
    required_kinds = {
        git_dir: "directory",
        git_dir / "HEAD": "file",
        git_dir / "config": "file",
        git_dir / "objects": "directory",
        git_dir / "refs": "directory",
    }
    if any(
        archive_services.wom_kit_real_path_kind(root, path) != expected_kind
        for path, expected_kind in required_kinds.items()
    ):
        return False
    for overlay in (
        git_dir / "objects" / "info" / "alternates",
        git_dir / "info" / "grafts",
        git_dir / "refs" / "replace",
    ):
        if archive_services.wom_kit_real_path_kind(root, overlay) != "missing":
            return False
    packed_refs = git_dir / "packed-refs"
    packed_kind = archive_services.wom_kit_real_path_kind(root, packed_refs)
    if packed_kind == "file":
        packed = archive_services._wom_kit_read_bounded_real_bytes(
            root,
            packed_refs,
            max_bytes=4 * 1024 * 1024,
        )
        if packed is None or b"refs/replace/" in packed:
            return False
    elif packed_kind != "missing":
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    stack = [git_dir]
    seen = 0
    try:
        while stack:
            directory = stack.pop()
            with os.scandir(directory) as scanner:
                for child in scanner:
                    seen += 1
                    if seen > GIT_BACKUP_PLAN_MAX_PREFLIGHT_ENTRIES:
                        return False
                    child_stat = child.stat(follow_symlinks=False)
                    if (
                        child.is_symlink()
                        or (
                            reparse_flag
                            and getattr(child_stat, "st_file_attributes", 0)
                            & reparse_flag
                        )
                    ):
                        return False
                    if stat.S_ISDIR(child_stat.st_mode):
                        stack.append(Path(child.path))
                    elif not stat.S_ISREG(child_stat.st_mode):
                        return False
    except OSError:
        return False
    return True


def _git_lock_inventory(root: Path) -> tuple[dict[str, Any] | None, list[str]]:
    """Inventory every regular ``*.lock`` below the real local Git dir."""

    git_dir = root / ".git"
    if archive_services.wom_kit_real_path_kind(root, git_dir) != "directory":
        return None, ["git_lock_inventory_boundary_invalid"]
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    stack = [git_dir]
    lock_tokens: list[str] = []
    seen = 0
    try:
        while stack:
            directory = stack.pop()
            with os.scandir(directory) as scanner:
                for child in scanner:
                    seen += 1
                    if seen > GIT_BACKUP_PLAN_MAX_PREFLIGHT_ENTRIES:
                        return None, ["git_lock_inventory_entry_limit_exceeded"]
                    child_stat = child.stat(follow_symlinks=False)
                    if (
                        child.is_symlink()
                        or (
                            reparse_flag
                            and getattr(child_stat, "st_file_attributes", 0)
                            & reparse_flag
                        )
                    ):
                        return None, ["git_lock_inventory_non_plain_entry"]
                    child_path = Path(child.path)
                    if stat.S_ISDIR(child_stat.st_mode):
                        stack.append(child_path)
                        continue
                    if not stat.S_ISREG(child_stat.st_mode):
                        return None, ["git_lock_inventory_non_plain_entry"]
                    if child.name.casefold().endswith(".lock"):
                        lock_tokens.append(_private_path_token(root, child_path))
    except OSError:
        return None, ["git_lock_inventory_scan_failed"]
    lock_tokens.sort()
    return {
        "count": len(lock_tokens),
        "private_inventory_sha256": _sha256_json(lock_tokens),
    }, []


def _safe_git_preflight(
    root: Path,
) -> tuple[dict[str, Any] | None, list[str]]:
    if not _git_metadata_is_local_real(root):
        return None, ["git_metadata_boundary_not_local_or_real"]
    locks, lock_blockers = _git_lock_inventory(root)
    if locks is None:
        return None, lock_blockers
    if locks["count"]:
        return locks, ["git_lock_files_present"]
    git_dir = root / ".git"
    if any(
        archive_services.wom_kit_real_path_kind(root, git_dir / marker)
        != "missing"
        for marker in GIT_BACKUP_OPERATION_MARKERS
    ):
        return locks, ["git_operation_or_lock_in_progress"]
    if (
        archive_services.wom_kit_real_path_kind(
            root,
            root / ".zettel-kasten" / "git-backup.lock",
        )
        != "missing"
    ):
        return locks, ["archive_git_backup_lock_present"]
    # Only after the local metadata boundary and operation markers are proven
    # safe may Git inspect the bounded attribute pathspec.  This preserves the
    # fail-fast rule: a malformed repository or active writer never starts a
    # status/index subprocess.
    attribute_blockers = _archive_attribute_preflight(root)
    if attribute_blockers:
        return locks, attribute_blockers
    return locks, []


def _git_config_trust_digest(root: Path) -> str | None:
    """Hash effective config through the pinned executable without exposing it."""

    environment = _local_git_environment()
    config_process: subprocess.Popen[bytes] | None = None
    digest_process: subprocess.Popen[bytes] | None = None
    try:
        config_process = subprocess.Popen(
            _git_command(
                root,
                ["config", "--includes", "--null", "--list", "--show-origin"],
            ),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=environment,
        )
        if config_process.stdout is None:
            raise OSError("git_config_stdout_unavailable")
        digest_process = subprocess.Popen(
            _git_command(root, ["hash-object", "--stdin"]),
            stdin=config_process.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=environment,
        )
        config_process.stdout.close()
        digest_stdout, _ = digest_process.communicate(timeout=15)
        config_return_code = config_process.wait(timeout=5)
    except (OSError, ValueError, subprocess.SubprocessError):
        for process in (digest_process, config_process):
            if process is None:
                continue
            try:
                process.kill()
            except OSError:
                pass
            try:
                process.wait(timeout=5)
            except (OSError, subprocess.SubprocessError):
                pass
        return None
    if (
        config_return_code != 0
        or digest_process.returncode != 0
        or re.fullmatch(rb"[0-9a-fA-F]{40,64}\r?\n?", digest_stdout) is None
    ):
        return None
    return _sha256_bytes(digest_stdout.strip().lower())


def _structural_snapshot(
    root: Path,
    *,
    branch: str | None,
    preflight_verified: bool = False,
    max_status_records: int = GIT_BACKUP_PLAN_MAX_CHANGES,
) -> tuple[dict[str, Any] | None, list[str]]:
    blockers: list[str] = []

    if not preflight_verified:
        _, preflight_blockers = _safe_git_preflight(root)
        if preflight_blockers:
            return None, preflight_blockers
    repository_shape_queries = {
        "top_level": ["rev-parse", "--show-toplevel"],
        "inside_worktree": ["rev-parse", "--is-inside-work-tree"],
        "bare": ["rev-parse", "--is-bare-repository"],
        "shallow": ["rev-parse", "--is-shallow-repository"],
        "git_dir": ["rev-parse", "--absolute-git-dir"],
        "common_dir": ["rev-parse", "--path-format=absolute", "--git-common-dir"],
    }
    shape: dict[str, str] = {}
    for name, args in repository_shape_queries.items():
        result = _local_git_text(root, args, max_output_bytes=16 * 1024)
        if result is None or result[0] != 0:
            return None, [f"git_{name}_query_failed"]
        shape[name] = result[1]
    try:
        root_resolved = root.resolve(strict=True)
        top_level_matches = Path(shape["top_level"]).resolve(strict=True) == root_resolved
        expected_git_dir = (root / ".git").resolve(strict=True)
        git_dir_matches = Path(shape["git_dir"]).resolve(strict=True) == expected_git_dir
        common_dir_matches = Path(shape["common_dir"]).resolve(strict=True) == expected_git_dir
    except (OSError, RuntimeError, ValueError):
        return None, ["git_repository_shape_invalid"]
    if not top_level_matches:
        blockers.append("archive_root_not_git_top_level")
    if shape["inside_worktree"] != "true" or shape["bare"] != "false":
        blockers.append("git_worktree_shape_not_supported")
    if shape["shallow"] != "false":
        blockers.append("shallow_repository_not_supported")
    if not git_dir_matches or not common_dir_matches:
        blockers.append("linked_or_external_git_metadata_not_supported")

    target_ref, target_ref_source = _resolve_target_ref(root, branch)
    if target_ref is None:
        blockers.append(
            "detached_head_not_supported"
            if target_ref_source == "detached"
            else "target_branch_ref_invalid"
        )
        return None, blockers
    if target_ref_source == "explicit_other_branch":
        blockers.append("target_branch_not_checked_out")

    head_result = _local_git_text(
        root,
        ["rev-parse", "--verify", "HEAD^{commit}"],
        max_output_bytes=8 * 1024,
    )
    if head_result is None:
        return None, ["local_head_query_failed"]
    local_head: str | None
    if head_result[0] == 0 and re.fullmatch(
        r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}",
        head_result[1],
    ):
        local_head = head_result[1].lower()
    elif head_result[0] != 0 and head_result[1] == "":
        local_head = None
        blockers.append("unborn_head_not_supported")
    else:
        return None, ["local_head_query_failed"]
    if local_head is not None:
        target_commit_result = _local_git_text(
            root,
            ["rev-parse", "--verify", f"{target_ref}^{{commit}}"],
            max_output_bytes=8 * 1024,
        )
        if (
            target_commit_result is None
            or target_commit_result[0] != 0
            or target_commit_result[1].lower() != local_head
        ):
            blockers.append("target_ref_and_head_commit_mismatch")

    object_format_result = _local_git_text(
        root,
        ["rev-parse", "--show-object-format=storage"],
        max_output_bytes=64,
    )
    if (
        object_format_result is None
        or object_format_result[0] != 0
        or object_format_result[1] not in {"sha1", "sha256"}
    ):
        return None, ["git_object_format_unavailable"]
    object_format = object_format_result[1]
    expected_oid_length = 40 if object_format == "sha1" else 64
    if local_head is not None and len(local_head) != expected_oid_length:
        return None, ["git_object_format_oid_mismatch"]

    commands = {
        "status": [
            "status",
            "--porcelain=v2",
            "-z",
            "--untracked-files=all",
            "--ignore-submodules=all",
        ],
        "ignored": [
            "status",
            "--porcelain=v2",
            "-z",
            "--untracked-files=normal",
            "--ignored=matching",
            "--ignore-submodules=all",
        ],
        "index": ["ls-files", "--stage", "-z"],
        "flags": ["ls-files", "-v", "-z"],
    }
    raw_values: dict[str, bytes] = {}
    for name, args in commands.items():
        result = _local_git_raw(root, args)
        if result is None or result[0] != 0:
            return None, [f"git_{name}_snapshot_failed"]
        raw_values[name] = result[1]
    if local_head is None:
        raw_values["tree"] = b""
    else:
        tree_result = _local_git_raw(root, ["ls-tree", "-r", "-z", "HEAD"])
        if tree_result is None or tree_result[0] != 0:
            return None, ["git_tree_snapshot_failed"]
        raw_values["tree"] = tree_result[1]

    status = _parse_status(raw_values["status"])
    ignored_status = _parse_status(raw_values["ignored"])
    tree = _parse_tree(raw_values["tree"])
    index = _parse_index(raw_values["index"])
    flags = _parse_flags(raw_values["flags"])
    if status is None or ignored_status is None or tree is None or index is None or flags is None:
        return None, ["git_machine_output_invalid_or_unsafe"]
    if len(status) > max_status_records:
        return None, ["requested_changed_item_limit_exceeded"]
    if any(record.record_kind == "ignored" for record in status):
        return None, ["git_status_candidate_inventory_invalid"]
    ignored_items = [
        record for record in ignored_status if record.record_kind == "ignored"
    ]
    if len(status) > GIT_BACKUP_PLAN_MAX_CHANGES:
        blockers.append("changed_item_limit_exceeded")
    if len(ignored_items) > GIT_BACKUP_PLAN_MAX_TRACKED_PATHS:
        blockers.append("ignored_item_limit_exceeded")

    tree_entries, tree_symlinks, tree_gitlinks = tree
    index_entries, index_gitlinks = index
    candidate_paths = {
        path
        for record in status
        for path in (record.path, record.original_path)
        if path is not None
    }
    inert_attributes = _changed_path_attributes_are_inert(root, candidate_paths)
    if inert_attributes is None:
        blockers.append("changed_path_attribute_state_unavailable")
    elif not inert_attributes:
        blockers.append("changed_path_filter_or_encoding_attribute_not_supported")
    if candidate_paths and not archive_services.wom_kit_project_update_safe_worktree_paths(
        sorted(candidate_paths)
    ):
        blockers.append("changed_path_set_not_cross_platform_safe")
    if tree_entries and not archive_services.wom_kit_project_update_safe_worktree_paths(
        sorted(tree_entries)
    ):
        blockers.append("tracked_tree_path_set_not_cross_platform_safe")
    if index_entries and not archive_services.wom_kit_project_update_safe_worktree_paths(
        sorted(index_entries)
    ):
        blockers.append("index_path_set_not_cross_platform_safe")
    if tree_symlinks:
        blockers.append("tracked_symlink_present")
    if tree_gitlinks or index_gitlinks:
        blockers.append("git_submodule_or_gitlink_present")
    if any(value != "H" for value in flags.values()):
        blockers.append("git_index_path_flags_not_plain")

    trust_digest = _git_config_trust_digest(root)
    if trust_digest is None:
        blockers.append("git_config_trust_digest_unavailable")
    split_index = _local_git_text(
        root,
        ["rev-parse", "--shared-index-path"],
        max_output_bytes=8 * 1024,
    )
    if split_index is None or split_index[0] != 0:
        blockers.append("git_split_index_state_unavailable")
    elif split_index[1]:
        blockers.append("git_split_index_not_supported")
    sparse_state = _config_value_state(root, "core.sparseCheckout", boolean=True)
    partial_state = _config_value_state(root, "extensions.partialClone")
    promisor_state = _promisor_config_state(root)
    if sparse_state == "invalid":
        blockers.append("git_sparse_checkout_state_invalid")
    elif sparse_state == "true":
        blockers.append("git_sparse_checkout_not_supported")
    if partial_state == "invalid" or promisor_state == "invalid":
        blockers.append("git_partial_clone_state_invalid")
    elif partial_state == "present" or promisor_state == "present":
        blockers.append("git_partial_clone_not_supported")

    git_dir = root / ".git"
    active_markers = 0
    for marker in GIT_BACKUP_OPERATION_MARKERS:
        kind = archive_services.wom_kit_real_path_kind(root, git_dir / marker)
        if kind != "missing":
            active_markers += 1
    if active_markers:
        blockers.append("git_operation_or_lock_in_progress")
    backup_lock_kind = archive_services.wom_kit_real_path_kind(
        root,
        root / ".zettel-kasten" / "git-backup.lock",
    )
    if backup_lock_kind != "missing":
        blockers.append("archive_git_backup_lock_present")

    target_ref_after, target_source_after = _resolve_target_ref(root, branch)
    if target_ref_after != target_ref or target_source_after != target_ref_source:
        blockers.append("symbolic_head_or_target_ref_drifted")

    return {
        "target_ref": target_ref,
        "target_ref_source": target_ref_source,
        "local_head": local_head,
        "object_format": object_format,
        "status": status,
        "ignored_status": ignored_items,
        "tree_entries": tree_entries,
        "index_entries": index_entries,
        "flags": flags,
        "tree_symlink_count": tree_symlinks,
        "tree_gitlink_count": tree_gitlinks,
        "index_gitlink_count": index_gitlinks,
        "tracked_path_count": len(tree_entries),
        "git_config_trust_sha256": (
            trust_digest if trust_digest is not None else None
        ),
        "status_sha256": _sha256_bytes(raw_values["status"]),
        "ignored_status_sha256": _sha256_bytes(raw_values["ignored"]),
        "index_sha256": _sha256_bytes(raw_values["index"]),
        "flags_sha256": _sha256_bytes(raw_values["flags"]),
        "tree_sha256": _sha256_bytes(raw_values["tree"]),
    }, blockers


def _hash_stable_plain_file(
    root: Path,
    path: Path,
    *,
    max_bytes: int,
) -> _FileObservation:
    """Hash one real, single-link file without following a final symlink."""

    try:
        path.relative_to(root)
        before = os.lstat(path)
    except FileNotFoundError:
        return _FileObservation("missing")
    except (OSError, ValueError):
        return _FileObservation("unsafe")
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if (
        not stat.S_ISREG(before.st_mode)
        or stat.S_ISLNK(before.st_mode)
        or (reparse_flag and getattr(before, "st_file_attributes", 0) & reparse_flag)
        or not archive_services.wom_kit_path_components_are_real(root, path)
    ):
        return _FileObservation("unsafe")
    if before.st_nlink != 1:
        return _FileObservation("hardlinked")
    if before.st_size < 0 or before.st_size > max_bytes:
        return _FileObservation("too_large", size=max(0, before.st_size))

    descriptor: int | None = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or opened.st_size != before.st_size
            or (before.st_ino and opened.st_ino and before.st_ino != opened.st_ino)
            or (before.st_dev and opened.st_dev and before.st_dev != opened.st_dev)
        ):
            return _FileObservation("unstable")
        digest = hashlib.sha256()
        total = 0
        while total <= max_bytes:
            chunk = os.read(
                descriptor,
                min(64 * 1024, max_bytes + 1 - total),
            )
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
        after = os.fstat(descriptor)
        if (
            total != opened.st_size
            or after.st_size != opened.st_size
            or after.st_mtime_ns != opened.st_mtime_ns
            or after.st_ctime_ns != opened.st_ctime_ns
            or after.st_nlink != 1
            or (opened.st_ino and after.st_ino and opened.st_ino != after.st_ino)
            or (opened.st_dev and after.st_dev and opened.st_dev != after.st_dev)
        ):
            return _FileObservation("unstable")
        identity = (
            int(after.st_dev),
            int(after.st_ino),
            int(after.st_size),
            int(after.st_mtime_ns),
            int(after.st_ctime_ns),
        )
        return _FileObservation(
            "regular_file",
            size=total,
            sha256="sha256:" + digest.hexdigest(),
            identity=identity,
        )
    except (OSError, OverflowError, ValueError):
        return _FileObservation("unstable")
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _private_path_token(root: Path, path: Path) -> str:
    relative = path.relative_to(root).as_posix()
    return relative.encode("utf-8", errors="surrogatepass").hex()


def _receipt_stat_identity(info: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        int(info.st_dev),
        int(info.st_ino),
        int(info.st_mode),
        int(info.st_size),
        int(info.st_mtime_ns),
        int(info.st_ctime_ns),
    )


def _receipt_inventory(
    root: Path,
) -> tuple[_ReceiptInventory, _ReceiptInventoryCache | None, list[str]]:
    """Inventory receipt metadata once, without reading historical bodies.

    Changed receipt bodies are already exact Git status candidates and are
    hashed by `_observe_changed_files`.  Opening every unchanged historical
    receipt could not establish provenance for an arbitrary changed file and
    made an 8k-receipt archive take minutes.  This inventory therefore binds
    private path tokens, sizes, and stable filesystem identities only.
    """

    receipt_root = root / "receipts"
    kind = archive_services.wom_kit_real_path_kind(root, receipt_root)
    if kind == "missing":
        empty_digest = _sha256_json([])
        return (
            _ReceiptInventory("absent", 0, 0, empty_digest, empty_digest),
            _ReceiptInventoryCache("absent", ()),
            [],
        )
    if kind != "directory":
        return (
            _ReceiptInventory("unsafe", 0, 0, None, None),
            None,
            ["receipt_inventory_root_not_real_directory"],
        )

    entries: list[tuple[str, str, tuple[int, int, int, int, int, int]]] = []
    file_metadata: list[tuple[str, int]] = []
    stack = [receipt_root]
    directory_count = 0
    total_bytes = 0
    blockers: list[str] = []
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    scanned_entry_count = 0
    try:
        root_info = os.lstat(receipt_root)
    except OSError:
        return (
            _ReceiptInventory("blocked", 0, 0, None, None),
            None,
            ["receipt_inventory_scan_failed"],
        )
    entries.append(("receipts", "directory", _receipt_stat_identity(root_info)))
    while stack and not blockers:
        directory = stack.pop()
        directory_count += 1
        if directory_count > GIT_BACKUP_PLAN_MAX_RECEIPTS * 4:
            blockers.append("receipt_directory_limit_exceeded")
            break
        try:
            with os.scandir(directory) as scanner:
                children = []
                for child in scanner:
                    scanned_entry_count += 1
                    if scanned_entry_count > GIT_BACKUP_PLAN_MAX_RECEIPTS * 4:
                        blockers.append("receipt_inventory_entry_limit_exceeded")
                        break
                    children.append(child)
                children.sort(key=lambda item: item.name)
        except OSError:
            blockers.append("receipt_inventory_scan_failed")
            break
        if blockers:
            break
        for child in children:
            try:
                child_stat = child.stat(follow_symlinks=False)
            except OSError:
                blockers.append("receipt_inventory_scan_failed")
                break
            if (
                child.is_symlink()
                or (
                    reparse_flag
                    and getattr(child_stat, "st_file_attributes", 0) & reparse_flag
                )
            ):
                blockers.append("receipt_inventory_non_plain_entry")
                break
            child_path = Path(child.path)
            if stat.S_ISDIR(child_stat.st_mode):
                try:
                    directory_stat = (
                        os.lstat(child_path) if os.name == "nt" else child_stat
                    )
                except OSError:
                    blockers.append("receipt_inventory_scan_failed")
                    break
                if (
                    not stat.S_ISDIR(directory_stat.st_mode)
                    or stat.S_ISLNK(directory_stat.st_mode)
                    or (
                        reparse_flag
                        and getattr(directory_stat, "st_file_attributes", 0)
                        & reparse_flag
                    )
                ):
                    blockers.append("receipt_inventory_non_plain_entry")
                    break
                relative = child_path.relative_to(root).as_posix()
                entries.append(
                    (relative, "directory", _receipt_stat_identity(directory_stat))
                )
                stack.append(child_path)
                continue
            if not stat.S_ISREG(child_stat.st_mode):
                blockers.append("receipt_inventory_non_plain_entry")
                break
            # CPython's Windows DirEntry cache reports st_nlink=0.  One
            # metadata-only lstat obtains the actual link count without
            # opening or reading the receipt body.
            try:
                file_stat = os.lstat(child_path) if os.name == "nt" else child_stat
            except OSError:
                blockers.append("receipt_inventory_scan_failed")
                break
            if (
                not stat.S_ISREG(file_stat.st_mode)
                or stat.S_ISLNK(file_stat.st_mode)
                or (
                    reparse_flag
                    and getattr(file_stat, "st_file_attributes", 0) & reparse_flag
                )
            ):
                blockers.append("receipt_inventory_non_plain_entry")
                break
            if len(file_metadata) >= GIT_BACKUP_PLAN_MAX_RECEIPTS:
                blockers.append("receipt_file_limit_exceeded")
                break
            if file_stat.st_nlink != 1:
                blockers.append("receipt_inventory_non_plain_or_unstable_file")
                break
            if file_stat.st_size < 0 or file_stat.st_size > GIT_BACKUP_PLAN_MAX_RECEIPT_BYTES:
                blockers.append("receipt_file_too_large")
                break
            total_bytes += file_stat.st_size
            if total_bytes > GIT_BACKUP_PLAN_MAX_RECEIPT_TOTAL_BYTES:
                blockers.append("receipt_total_bytes_limit_exceeded")
                break
            relative = child_path.relative_to(root).as_posix()
            token = _private_path_token(root, child_path)
            entries.append(
                (relative, "file", _receipt_stat_identity(file_stat))
            )
            file_metadata.append((token, int(file_stat.st_size)))
    if blockers:
        return (
            _ReceiptInventory(
                "blocked", len(file_metadata), total_bytes, None, None
            ),
            None,
            blockers,
        )
    entries.sort(key=lambda item: (item[0], item[1]))
    file_metadata.sort(key=lambda item: item[0])
    content_basis = [
        {"path": path, "bytes": size, "basis": "metadata_only"}
        for path, size in file_metadata
    ]
    stability_basis = [
        {
            "path": _private_path_token(
                root,
                root.joinpath(*PurePosixPath(path).parts),
            ),
            "kind": entry_kind,
            "identity": list(identity),
        }
        for path, entry_kind, identity in entries
    ]
    return (
        _ReceiptInventory(
            "observed",
            len(file_metadata),
            total_bytes,
            _sha256_json(content_basis),
            _sha256_json(stability_basis),
        ),
        _ReceiptInventoryCache("observed", tuple(entries)),
        [],
    )


def _receipt_inventory_recheck(
    root: Path,
    cache: _ReceiptInventoryCache,
) -> list[str]:
    """CAS-check the one-pass inventory with lstat only; never reopen bodies."""

    if cache.state == "absent":
        return (
            []
            if archive_services.wom_kit_real_path_kind(root, root / "receipts")
            == "missing"
            else ["receipt_inventory_drifted"]
        )
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    for relative, entry_kind, expected_identity in cache.entries:
        path = root.joinpath(*PurePosixPath(relative).parts)
        try:
            current = os.lstat(path)
        except OSError:
            return ["receipt_inventory_drifted"]
        if (
            stat.S_ISLNK(current.st_mode)
            or (
                reparse_flag
                and getattr(current, "st_file_attributes", 0) & reparse_flag
            )
            or (entry_kind == "directory" and not stat.S_ISDIR(current.st_mode))
            or (entry_kind == "file" and not stat.S_ISREG(current.st_mode))
            or (entry_kind == "file" and current.st_nlink != 1)
            or _receipt_stat_identity(current) != expected_identity
        ):
            return ["receipt_inventory_drifted"]
    return []


def _handoff_observation(root: Path) -> dict[str, Any] | None:
    """Return the fixed handoff boundary relevant to Git backup safety.

    A session-handoff scan inventories AI scratch material and operational
    context; it neither proves file provenance nor changes whether an exact Git
    change may be committed.  Running that independent workflow here caused a
    second broad scratch traversal.  Git backup therefore records that the
    context workflow was intentionally not evaluated and relies on its own
    complete Git change classification.
    """

    del root
    return {
        "state_digest": _sha256_json(
            {
                "schema": "wom-kit/git-backup-handoff-scope/v1",
                "status": "not_required_for_git_backup",
                "file_provenance_authority": False,
            }
        ),
        "status": "not_required_for_git_backup",
        "ready_for_context_reset": False,
    }


def _snapshot_comparison_basis(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        key: snapshot.get(key)
        for key in (
            "target_ref",
            "target_ref_source",
            "local_head",
            "object_format",
            "tracked_path_count",
            "tree_symlink_count",
            "tree_gitlink_count",
            "index_gitlink_count",
            "git_config_trust_sha256",
            "status_sha256",
            "ignored_status_sha256",
            "index_sha256",
            "flags_sha256",
            "tree_sha256",
        )
    }


def _status_records_are_supported(records: list[_StatusRecord]) -> bool:
    valid_xy = re.compile(r"[.MADRCU]{2}")
    seen_paths: set[str] = set()
    for record in records:
        if record.path in seen_paths:
            return False
        seen_paths.add(record.path)
        if record.original_path is not None:
            if record.original_path in seen_paths:
                return False
            seen_paths.add(record.original_path)
        if record.record_kind == "untracked":
            if record.xy != "??":
                return False
        elif record.record_kind in {"ordinary", "rename_or_copy", "unmerged"}:
            if valid_xy.fullmatch(record.xy) is None:
                return False
        else:
            return False
    return True


def _observe_changed_files(
    root: Path,
    records: list[_StatusRecord],
    *,
    max_total_bytes: int,
) -> tuple[dict[str, _FileObservation], int, list[str]]:
    paths = {
        path
        for record in records
        for path in (record.path, record.original_path)
        if path is not None
    }
    observations: dict[str, _FileObservation] = {}
    total_bytes = 0
    blockers: list[str] = []
    for relative_path in sorted(paths):
        remaining = max_total_bytes - total_bytes
        if remaining < 0:
            blockers.append("requested_changed_bytes_limit_exceeded")
            break
        observation = _hash_stable_plain_file(
            root,
            root.joinpath(*PurePosixPath(relative_path).parts),
            max_bytes=min(GIT_BACKUP_PLAN_MAX_FILE_BYTES, remaining),
        )
        observations[relative_path] = observation
        if observation.state == "regular_file":
            assert observation.size is not None
            total_bytes += observation.size
        elif observation.state == "missing":
            continue
        elif observation.state == "too_large":
            blockers.append(
                "changed_file_size_limit_exceeded"
                if (observation.size or 0) > GIT_BACKUP_PLAN_MAX_FILE_BYTES
                else "requested_changed_bytes_limit_exceeded"
            )
            break
        elif observation.state == "hardlinked":
            blockers.append("changed_file_hardlink_not_supported")
            break
        else:
            blockers.append("changed_path_not_plain_or_stable_file")
            break
    return observations, total_bytes, _unique(blockers)


def _git_blob_inventory(
    root: Path,
    snapshot: dict[str, Any],
    *,
    max_total_bytes: int,
) -> tuple[dict[str, tuple[int, str]], int, list[str]]:
    records: list[_StatusRecord] = snapshot["status"]
    tree_entries: dict[str, tuple[str, str]] = snapshot["tree_entries"]
    index_entries: dict[str, list[tuple[str, str, int]]] = snapshot["index_entries"]
    paths = {
        path
        for record in records
        for path in (record.path, record.original_path)
        if path is not None
    }
    oid_path_counts: dict[str, int] = {}
    blockers: list[str] = []
    expected_oid_length = 40 if snapshot["object_format"] == "sha1" else 64
    for relative_path in sorted(paths):
        tree_entry = tree_entries.get(relative_path)
        if tree_entry is not None:
            mode, oid = tree_entry
            if mode not in {"100644", "100755"} or len(oid) != expected_oid_length:
                blockers.append("changed_head_blob_binding_invalid")
            else:
                oid_path_counts[oid] = oid_path_counts.get(oid, 0) + 1
        index_rows = index_entries.get(relative_path, [])
        stage_zero = [row for row in index_rows if row[2] == 0]
        nonzero = [row for row in index_rows if row[2] != 0]
        if nonzero:
            blockers.append("unmerged_index_entries_present")
        if len(stage_zero) > 1:
            blockers.append("changed_index_blob_binding_invalid")
        elif stage_zero:
            mode, oid, _ = stage_zero[0]
            if mode not in {"100644", "100755"} or len(oid) != expected_oid_length:
                blockers.append("changed_index_blob_binding_invalid")
            else:
                oid_path_counts[oid] = oid_path_counts.get(oid, 0) + 1
    if blockers:
        return {}, 0, _unique(blockers)
    if not oid_path_counts:
        return {}, 0, []
    if len(oid_path_counts) > archive_services.WOM_KIT_PROJECT_UPDATE_MAX_TRACKED_FILES:
        return {}, 0, ["changed_git_blob_count_limit_exceeded"]

    object_ids = list(oid_path_counts)
    request = b"".join(oid.encode("ascii") + b"\n" for oid in object_ids)
    size_check = archive_services._wom_kit_project_update_run_batch_capped(
        _git_command(
            root,
            ["cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)"],
        ),
        environment=_local_git_environment(),
        timeout_seconds=archive_services.WOM_KIT_PROJECT_UPDATE_BATCH_TIMEOUT_SECONDS,
        max_output_bytes=len(object_ids) * 160,
        input_bytes=request,
    )
    if size_check is None or size_check[0] != 0:
        return {}, 0, ["changed_git_blob_size_preflight_failed"]
    size_rows = size_check[1].splitlines()
    if len(size_rows) != len(object_ids):
        return {}, 0, ["changed_git_blob_size_preflight_failed"]
    sizes: dict[str, int] = {}
    logical_total_bytes = 0
    unique_total_bytes = 0
    for expected_oid, row in zip(object_ids, size_rows, strict=True):
        match = re.fullmatch(
            rb"([0-9a-fA-F]{40}|[0-9a-fA-F]{64}) blob (0|[1-9][0-9]*)",
            row,
        )
        if match is None or match.group(1).decode("ascii").lower() != expected_oid:
            return {}, 0, ["changed_git_blob_size_preflight_failed"]
        size = int(match.group(2))
        if size > GIT_BACKUP_PLAN_MAX_FILE_BYTES:
            return {}, 0, ["changed_git_blob_file_size_limit_exceeded"]
        logical_total_bytes += size * oid_path_counts[expected_oid]
        unique_total_bytes += size
        if logical_total_bytes > max_total_bytes:
            return {}, 0, ["requested_changed_bytes_limit_exceeded"]
        sizes[expected_oid] = size
    if unique_total_bytes > GIT_BACKUP_PLAN_MAX_BLOB_BATCH_BYTES:
        return {}, 0, ["changed_git_blob_physical_read_limit_exceeded"]

    framing_cap = len(object_ids) * 129
    completed = archive_services._wom_kit_project_update_run_batch_capped(
        _git_command(root, ["cat-file", "--batch"]),
        environment=_local_git_environment(),
        timeout_seconds=archive_services.WOM_KIT_PROJECT_UPDATE_BATCH_TIMEOUT_SECONDS,
        max_output_bytes=unique_total_bytes + framing_cap,
        input_bytes=request,
    )
    if completed is None or completed[0] != 0:
        return {}, 0, ["changed_git_blob_inventory_failed"]
    output = completed[1]
    cursor = 0
    inventory: dict[str, tuple[int, str]] = {}
    for oid in object_ids:
        header_end = output.find(b"\n", cursor, min(len(output), cursor + 129))
        if header_end < 0:
            return {}, 0, ["changed_git_blob_inventory_failed"]
        header = output[cursor:header_end]
        expected_header = f"{oid} blob {sizes[oid]}".encode("ascii")
        if header.lower() != expected_header:
            return {}, 0, ["changed_git_blob_inventory_failed"]
        blob_start = header_end + 1
        blob_end = blob_start + sizes[oid]
        if blob_end >= len(output) or output[blob_end : blob_end + 1] != b"\n":
            return {}, 0, ["changed_git_blob_inventory_failed"]
        blob = output[blob_start:blob_end]
        object_hasher = hashlib.sha1() if len(oid) == 40 else hashlib.sha256()
        object_hasher.update(f"blob {len(blob)}\0".encode("ascii"))
        object_hasher.update(blob)
        if object_hasher.hexdigest() != oid:
            return {}, 0, ["changed_git_blob_inventory_failed"]
        inventory[oid] = (len(blob), _sha256_bytes(blob))
        cursor = blob_end + 1
    if cursor != len(output):
        return {}, 0, ["changed_git_blob_inventory_failed"]
    return inventory, logical_total_bytes, []


def _mode_label(mode: str) -> str:
    return {
        "100644": "regular_file",
        "100755": "executable_file",
        "120000": "symlink",
        "160000": "gitlink",
    }.get(mode, "unsupported")


def _staging_label(record: _StatusRecord) -> str:
    if record.record_kind == "untracked":
        return "untracked"
    if record.record_kind == "unmerged":
        return "conflicted"
    staged = record.xy[0] != "."
    unstaged = record.xy[1] != "."
    if staged and unstaged:
        return "staged_and_unstaged"
    if staged:
        return "staged_only"
    if unstaged:
        return "unstaged_only"
    return "unchanged"


def _operation_label(record: _StatusRecord) -> str:
    if record.record_kind == "untracked":
        return "added_untracked"
    if record.record_kind == "unmerged" or "U" in record.xy:
        return "conflicted"
    if record.record_kind == "rename_or_copy":
        return "copied" if "C" in record.xy else "renamed"
    for code, label in (
        ("D", "deleted"),
        ("A", "added"),
        ("T", "type_changed"),
        ("R", "renamed"),
        ("C", "copied"),
        ("M", "modified"),
    ):
        if code in record.xy:
            return label
    return "unknown"


def _worktree_public_observation(observation: _FileObservation) -> dict[str, Any]:
    return {
        "state": observation.state,
        "bytes": observation.size,
        "sha256": observation.sha256,
    }


def _git_entry_public_observation(
    entry: tuple[str, str] | None,
    blobs: dict[str, tuple[int, str]],
) -> dict[str, Any]:
    if entry is None:
        return {"state": "absent", "mode": None, "bytes": None, "sha256": None}
    mode, oid = entry
    blob = blobs.get(oid)
    if blob is None:
        return {"state": "unavailable", "mode": _mode_label(mode), "bytes": None, "sha256": None}
    return {
        "state": "blob",
        "mode": _mode_label(mode),
        "bytes": blob[0],
        "sha256": blob[1],
    }


def _change_inventory(
    snapshot: dict[str, Any],
    file_observations: dict[str, _FileObservation],
    blobs: dict[str, tuple[int, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    records: list[_StatusRecord] = sorted(
        snapshot["status"],
        key=lambda item: (
            item.path,
            item.original_path or "",
            item.record_kind,
            item.xy,
        ),
    )
    tree_entries: dict[str, tuple[str, str]] = snapshot["tree_entries"]
    index_entries: dict[str, list[tuple[str, str, int]]] = snapshot["index_entries"]
    public_items: list[dict[str, Any]] = []
    private_items: list[dict[str, Any]] = []
    blockers: list[str] = []
    for ordinal, record in enumerate(records, start=1):
        reference = f"change:{ordinal:06d}"
        index_rows = index_entries.get(record.path, [])
        stage_zero = [row for row in index_rows if row[2] == 0]
        index_entry = (stage_zero[0][0], stage_zero[0][1]) if len(stage_zero) == 1 else None
        head_entry = tree_entries.get(record.path)
        source_head_entry = (
            tree_entries.get(record.original_path)
            if record.original_path is not None
            else None
        )
        operation = _operation_label(record)
        if operation in {"conflicted", "type_changed", "unknown"}:
            blockers.append("changed_item_requires_unsupported_git_semantics")
        public_item = {
            "change_ref": reference,
            "record_kind": record.record_kind,
            "operation": operation,
            "staging_state": _staging_label(record),
            "worktree": _worktree_public_observation(
                file_observations[record.path]
            ),
            "head": _git_entry_public_observation(head_entry, blobs),
            "index": _git_entry_public_observation(index_entry, blobs),
            "source_head": (
                _git_entry_public_observation(source_head_entry, blobs)
                if record.original_path is not None
                else None
            ),
            "review_state": "human_review_required",
            "provenance_state": "unknown_provenance",
            "receipt_binding": "not_attempted_without_command_specific_adapter",
        }
        public_items.append(public_item)
        private_items.append(
            {
                "path": record.path,
                "original_path": record.original_path,
                "xy": record.xy,
                "record_kind": record.record_kind,
                "public_observation": public_item,
                "worktree_identity": (
                    list(file_observations[record.path].identity)
                    if file_observations[record.path].identity is not None
                    else None
                ),
                "original_worktree": (
                    _worktree_public_observation(
                        file_observations[record.original_path]
                    )
                    if record.original_path is not None
                    else None
                ),
                "original_worktree_identity": (
                    list(file_observations[record.original_path].identity)
                    if (
                        record.original_path is not None
                        and file_observations[record.original_path].identity is not None
                    )
                    else None
                ),
            }
        )
    return public_items, private_items, _unique(blockers)


def _repository_relation(
    root: Path,
    *,
    local_oid: str | None,
    remote_state: str,
    remote_oid: str | None,
    relation_allowed: bool,
) -> tuple[dict[str, Any], list[str]]:
    unavailable = {
        "state": "not_computed",
        "local_only_commit_count": None,
        "remote_only_commit_count": None,
    }
    if not relation_allowed or local_oid is None:
        return unavailable, []
    if remote_state == "target_ref_missing":
        return {
            "state": "remote_branch_missing",
            "local_only_commit_count": None,
            "remote_only_commit_count": 0,
        }, []
    if remote_state != "present" or remote_oid is None:
        return unavailable, ["remote_relation_unavailable"]
    if local_oid == remote_oid:
        return {
            "state": "equal",
            "local_only_commit_count": 0,
            "remote_only_commit_count": 0,
        }, []
    commit_check = _local_git_text(
        root,
        ["cat-file", "-e", f"{remote_oid}^{{commit}}"],
        max_output_bytes=64,
    )
    if commit_check is None or commit_check[0] != 0:
        return {
            "state": "remote_oid_not_available_locally",
            "local_only_commit_count": None,
            "remote_only_commit_count": None,
        }, ["remote_commit_graph_not_available_without_fetch"]
    counts = _local_git_text(
        root,
        ["rev-list", "--left-right", "--count", f"{local_oid}...{remote_oid}"],
        max_output_bytes=256,
    )
    if counts is None or counts[0] != 0:
        return unavailable, ["git_commit_relation_query_failed"]
    match = re.fullmatch(r"([0-9]+)\s+([0-9]+)", counts[1])
    if match is None:
        return unavailable, ["git_commit_relation_response_invalid"]
    local_only = int(match.group(1))
    remote_only = int(match.group(2))
    if local_only and remote_only:
        state = "diverged"
    elif local_only:
        state = "local_ahead"
    elif remote_only:
        state = "remote_ahead"
    else:
        state = "equal"
    return {
        "state": state,
        "local_only_commit_count": local_only,
        "remote_only_commit_count": remote_only,
    }, []


def _empty_plan_result(*, blockers: Iterable[str]) -> dict[str, Any]:
    blocker_list = _unique(blockers)
    return {
        "schema": GIT_BACKUP_PLAN_SCHEMA,
        "ok": False,
        "dry_run": True,
        "lifecycle_action": "git_backup_plan",
        "status": "blocked",
        "inspection_complete": False,
        "git_executable": {"sha256": None, "stability_verified": False},
        "git_lock_evidence": {"count": None, "inventory_sha256": None},
        "plan_sha256": None,
        "hidden_effect_set_sha256": None,
        "ready_for_write": False,
        "writer_available": False,
        "would_change": [],
        "files_written": [],
        "repository": {
            "local_head_oid": None,
            "remote_oid": None,
            "relation": {
                "state": "not_computed",
                "local_only_commit_count": None,
                "remote_only_commit_count": None,
            },
        },
        "remote_observation": {
            "state": "not_attempted",
            "git_transport_confirmed_ref": False,
            "provider_confirmed": False,
        },
        "change_summary": {
            "count": 0,
            "worktree_bytes_observed": 0,
            "git_blob_bytes_observed": 0,
            "human_review_required_count": 0,
        },
        "changes": [],
        "ignored_inventory": {
            "count": 0,
            "inventory_sha256": None,
            "classified_as_rebuildable": False,
        },
        "receipt_context": {
            "state": "not_observed",
            "file_count": 0,
            "total_bytes": 0,
            "inventory_sha256": None,
            "generic_provenance_matching_performed": False,
        },
        "session_handoff_context": {
            "state": "not_observed",
            "ready_for_context_reset": False,
            "context_only_not_file_provenance": True,
        },
        "next_safe_actions": [
            "Resolve every blocker and rerun this read-only plan.",
        ],
        "closed_actions": {
            "git_commit_called": False,
            "git_push_called": False,
            "git_fetch_called": False,
            "git_pull_merge_rebase_reset_clean_called": False,
            "lock_created": False,
            "receipt_written": False,
            "provider_api_called": False,
            "network_checked": False,
            "credential_resolution_called": False,
            "secret_classification_performed": False,
        },
        "blockers": blocker_list,
        "warnings": [],
    }


def _valid_limit(value: Any, *, minimum: int, maximum: int) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _git_backup_plan_with_pinned_git(
    archive_root: Path | str,
    *,
    remote_name: str = "origin",
    branch: str | None = None,
    credential_mode: str = "anonymous",
    max_changes: int = GIT_BACKUP_PLAN_DEFAULT_MAX_CHANGES,
    max_changed_bytes: int = GIT_BACKUP_PLAN_DEFAULT_MAX_CHANGED_BYTES,
    dry_run: bool = True,
    _private_capture: dict[str, Any] | None = None,
    _progress: _GitBackupPlanProgress | None = None,
) -> dict[str, Any]:
    """Return a deterministic, read-only Git backup review plan.

    Private paths, the archive identity, and the configured remote URL are used
    only inside cryptographic commitments.  They are never returned.
    """

    progress = _progress or _GitBackupPlanProgress(
        None,
        operation="git_backup_plan",
    )
    progress.status("validating_parameters")
    parameter_blockers: list[str] = []
    if type(dry_run) is not bool or not dry_run:
        parameter_blockers.append("read_only_command_requires_dry_run")
    if (
        not isinstance(remote_name, str)
        or GIT_BACKUP_REMOTE_NAME_RE.fullmatch(remote_name) is None
    ):
        parameter_blockers.append("remote_name_invalid")
    if branch is not None and not isinstance(branch, str):
        parameter_blockers.append("branch_invalid")
    if credential_mode not in GIT_BACKUP_CREDENTIAL_MODES:
        parameter_blockers.append("credential_mode_invalid")
    if not _valid_limit(
        max_changes,
        minimum=1,
        maximum=GIT_BACKUP_PLAN_MAX_CHANGES,
    ):
        parameter_blockers.append("max_changes_invalid")
    if not _valid_limit(
        max_changed_bytes,
        minimum=1,
        maximum=GIT_BACKUP_PLAN_MAX_CHANGED_BYTES,
    ):
        parameter_blockers.append("max_changed_bytes_invalid")
    if parameter_blockers:
        return _empty_plan_result(blockers=parameter_blockers)

    progress.status("resolving_archive")
    try:
        supplied_root = Path(archive_root)
        supplied_absolute = Path(os.path.abspath(str(supplied_root)))
        supplied_stat = os.lstat(supplied_absolute)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if (
            stat.S_ISLNK(supplied_stat.st_mode)
            or (
                reparse_flag
                and getattr(supplied_stat, "st_file_attributes", 0) & reparse_flag
            )
        ):
            return _empty_plan_result(blockers=["archive_root_link_not_supported"])
        root = archive_services.require_existing_archive_root(supplied_absolute)
        archive_id = archive_services.read_archive_id(root)
    except (
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        archive_services.ArchiveServiceError,
    ):
        return _empty_plan_result(blockers=["archive_root_or_identity_invalid"])
    pinned_git = _PINNED_GIT_EXECUTABLE.get()
    if pinned_git is None:
        return _empty_plan_result(blockers=["git_executable_not_pinned"])
    progress.status("preflight_initial")
    locks_before, preflight_blockers = _safe_git_preflight(root)
    if locks_before is None:
        return _empty_plan_result(blockers=preflight_blockers)
    public_lock_inventory_sha256 = _sha256_json(
        {
            "archive_root": str(root),
            "archive_id": archive_id,
            "git_executable_sha256": pinned_git.sha256,
            "lock_inventory_sha256": locks_before["private_inventory_sha256"],
        }
    )
    if preflight_blockers:
        blocked = _empty_plan_result(blockers=preflight_blockers)
        blocked["git_lock_evidence"] = {
            "count": locks_before["count"],
            "inventory_sha256": public_lock_inventory_sha256,
        }
        return blocked

    progress.status("git_projection_initial")
    snapshot_before, blockers = _structural_snapshot(
        root,
        branch=branch,
        preflight_verified=True,
        max_status_records=max_changes,
    )
    if snapshot_before is None:
        return _empty_plan_result(blockers=blockers)
    if len(snapshot_before["status"]) > max_changes:
        return _empty_plan_result(
            blockers=[*blockers, "requested_changed_item_limit_exceeded"]
        )
    if not _status_records_are_supported(snapshot_before["status"]):
        blockers.append("changed_status_semantics_invalid_or_ambiguous")

    progress.status("remote_ref_initial")
    remote_url = _configured_remote_url(root, remote_name)
    remote_before: tuple[str, str | None]
    if remote_url is None:
        remote_before = ("not_configured_or_unsafe", None)
        blockers.append("configured_remote_unavailable_or_unsafe")
    else:
        remote_before = (
            _query_remote_ref_with_stored_credentials(
                root,
                remote_name,
                snapshot_before["target_ref"],
            )
            if credential_mode == "stored"
            else _query_remote_ref(
                remote_url,
                snapshot_before["target_ref"],
            )
        )
        if remote_before[0] not in {"present", "target_ref_missing"}:
            blockers.append("git_transport_ref_observation_unavailable")
        elif remote_before[0] == "target_ref_missing":
            blockers.append("remote_target_ref_missing")
        if (
            remote_before[1] is not None
            and len(remote_before[1]) != (40 if snapshot_before["object_format"] == "sha1" else 64)
        ):
            blockers.append("remote_oid_object_format_mismatch")

    progress.status("receipt_inventory_initial")
    receipts_before, receipt_cache, receipt_blockers = _receipt_inventory(root)
    blockers.extend(receipt_blockers)
    progress.status("handoff_scope_initial")
    handoff_before = _handoff_observation(root)
    if handoff_before is None:
        blockers.append("session_handoff_context_unavailable")

    progress.status("changed_content_observation")
    files_before, worktree_bytes, file_blockers = _observe_changed_files(
        root,
        snapshot_before["status"],
        max_total_bytes=max_changed_bytes,
    )
    blockers.extend(file_blockers)
    if file_blockers:
        return _empty_plan_result(blockers=blockers)
    progress.status("git_blob_observation")
    blobs, git_blob_bytes, blob_blockers = _git_blob_inventory(
        root,
        snapshot_before,
        max_total_bytes=max_changed_bytes - worktree_bytes,
    )
    blockers.extend(blob_blockers)
    if blob_blockers:
        return _empty_plan_result(blockers=blockers)

    progress.status("building_change_inventory")
    public_changes, private_changes, change_blockers = _change_inventory(
        snapshot_before,
        files_before,
        blobs,
    )
    blockers.extend(change_blockers)

    # Observe the same evidence a second time after hashing every changed file.
    # No lock is created: drift is reported, never papered over.
    progress.status("drift_reobservation")
    files_after, worktree_bytes_after, file_after_blockers = _observe_changed_files(
        root,
        snapshot_before["status"],
        max_total_bytes=max_changed_bytes,
    )
    blockers.extend(file_after_blockers)
    progress.status("receipt_inventory_cas_recheck")
    receipts_after = receipts_before
    if receipt_cache is None:
        blockers.append("receipt_inventory_recheck_unavailable")
    else:
        blockers.extend(_receipt_inventory_recheck(root, receipt_cache))
    progress.status("handoff_scope_final")
    handoff_after = handoff_before
    if handoff_after is None:
        blockers.append("session_handoff_context_unavailable")
    progress.status("preflight_final")
    locks_after, preflight_after_blockers = _safe_git_preflight(root)
    blockers.extend(preflight_after_blockers)
    if locks_after is None:
        blockers.append("git_lock_inventory_unavailable")
    if locks_after != locks_before:
        blockers.append("git_lock_inventory_drifted")
    public_lock_inventory_after_sha256 = (
        _sha256_json(
            {
                "archive_root": str(root),
                "archive_id": archive_id,
                "git_executable_sha256": pinned_git.sha256,
                "lock_inventory_sha256": locks_after[
                    "private_inventory_sha256"
                ],
            }
        )
        if locks_after is not None
        else None
    )
    if preflight_after_blockers:
        snapshot_after = None
    else:
        progress.status("git_projection_final")
        snapshot_after, snapshot_after_blockers = _structural_snapshot(
            root,
            branch=branch,
            preflight_verified=True,
            max_status_records=max_changes,
        )
        blockers.extend(snapshot_after_blockers)
    progress.status("remote_ref_final")
    remote_url_after = _configured_remote_url(root, remote_name)
    if remote_url_after != remote_url:
        blockers.append("configuration_drifted")
        remote_after = ("configuration_drifted", None)
    elif remote_url_after is None:
        remote_after = remote_before
    else:
        remote_after = (
            _query_remote_ref_with_stored_credentials(
                root,
                remote_name,
                snapshot_before["target_ref"],
            )
            if credential_mode == "stored"
            else _query_remote_ref(
                remote_url_after,
                snapshot_before["target_ref"],
            )
        )

    if files_before != files_after or worktree_bytes != worktree_bytes_after:
        blockers.append("changed_file_observation_drifted")
    if receipts_before != receipts_after:
        blockers.append("receipt_inventory_drifted")
    if (
        snapshot_after is None
        or _snapshot_comparison_basis(snapshot_before)
        != _snapshot_comparison_basis(snapshot_after)
    ):
        blockers.append("git_structural_snapshot_drifted")
    if remote_before != remote_after:
        blockers.append("remote_ref_observation_drifted")
    if remote_after[0] not in {
        "present",
        "target_ref_missing",
        "configuration_drifted",
    }:
        blockers.append("git_transport_ref_observation_unavailable")
    elif remote_after[0] == "target_ref_missing":
        blockers.append("remote_target_ref_missing")

    relation_allowed = bool(
        snapshot_before["local_head"] is not None
        and snapshot_before["target_ref_source"] != "explicit_other_branch"
        and "unborn_head_not_supported" not in blockers
    )
    progress.status("repository_relation")
    relation, relation_blockers = _repository_relation(
        root,
        local_oid=snapshot_before["local_head"],
        remote_state=remote_after[0],
        remote_oid=remote_after[1],
        relation_allowed=relation_allowed,
    )
    blockers.extend(relation_blockers)

    warnings: list[str] = []
    if public_changes:
        warnings.append("every_changed_item_requires_exact_human_review")
        warnings.append("generic_receipt_fields_do_not_prove_file_provenance")
    if (
        handoff_after is not None
        and handoff_after.get("status") != "not_required_for_git_backup"
        and not handoff_after["ready_for_context_reset"]
    ):
        warnings.append("session_handoff_context_is_not_reset_ready")
    blockers = _unique(blockers)
    warnings = _unique(warnings)

    privacy_context = {
        "archive_root": str(root),
        "archive_id": archive_id,
        "remote_name": remote_name,
        "remote_url": remote_url,
        "remote_url_after": remote_url_after,
        "target_ref": snapshot_before["target_ref"],
        "git_executable_path": pinned_git.path,
        "git_executable_sha256": pinned_git.sha256,
        "git_executable_identity": list(pinned_git.identity),
        "credential_mode": credential_mode,
    }
    hidden_effect_set_sha256 = _sha256_json(
        {
            "privacy_context": privacy_context,
            "changes": private_changes,
        }
    )
    ignored_inventory_sha256 = _sha256_json(
        {
            "privacy_context": privacy_context,
            "ignored_status_sha256": snapshot_before["ignored_status_sha256"],
        }
    )
    receipt_inventory_sha256 = (
        _sha256_json(
            {
                "privacy_context": privacy_context,
                "receipt_inventory_sha256": receipts_after.inventory_sha256,
            }
        )
        if receipts_after.inventory_sha256 is not None
        else None
    )
    progress.status("finalizing_plan")
    plan_sha256 = _sha256_json(
        {
            "schema": GIT_BACKUP_PLAN_SCHEMA,
            "privacy_context": privacy_context,
            "parameters": {
                "max_changes": max_changes,
                "max_changed_bytes": max_changed_bytes,
                "dry_run": True,
                "credential_mode": credential_mode,
            },
            "snapshot": _snapshot_comparison_basis(snapshot_before),
            "remote_before": remote_before,
            "remote_after": remote_after,
            "receipts": receipts_after.__dict__,
            "handoff": handoff_after,
            "git_locks_before": locks_before,
            "git_locks_after": locks_after,
            "hidden_effect_set_sha256": hidden_effect_set_sha256,
            "relation": relation,
            "blockers": blockers,
            "warnings": warnings,
        }
    )

    ignored_count = len(snapshot_before["ignored_status"])
    result = {
        "schema": GIT_BACKUP_PLAN_SCHEMA,
        "ok": not blockers,
        "dry_run": True,
        "lifecycle_action": "git_backup_plan",
        "status": "plan_ready" if not blockers else "blocked",
        "inspection_complete": True,
        "git_executable": {
            "sha256": pinned_git.sha256,
            "stability_verified": False,
        },
        "git_lock_evidence": {
            "count": locks_after["count"] if locks_after is not None else None,
            "inventory_sha256": public_lock_inventory_after_sha256,
        },
        "plan_sha256": plan_sha256,
        "hidden_effect_set_sha256": hidden_effect_set_sha256,
        "ready_for_write": False,
        "writer_available": False,
        "would_change": [],
        "files_written": [],
        "repository": {
            "local_head_oid": snapshot_before["local_head"],
            "remote_oid": remote_after[1],
            "relation": relation,
        },
        "remote_observation": {
            "state": remote_after[0],
            "git_transport_confirmed_ref": remote_after[0] == "present",
            "provider_confirmed": False,
        },
        "change_summary": {
            "count": len(public_changes),
            "worktree_bytes_observed": worktree_bytes,
            "git_blob_bytes_observed": git_blob_bytes,
            "human_review_required_count": len(public_changes),
        },
        "changes": public_changes,
        "ignored_inventory": {
            "count": ignored_count,
            "inventory_sha256": ignored_inventory_sha256,
            "classified_as_rebuildable": False,
        },
        "receipt_context": {
            "state": receipts_after.state,
            "file_count": receipts_after.file_count,
            "total_bytes": receipts_after.total_bytes,
            "inventory_sha256": receipt_inventory_sha256,
            "inventory_basis": "path_size_and_filesystem_identity_metadata",
            "historical_receipt_bodies_read": False,
            "generic_provenance_matching_performed": False,
        },
        "session_handoff_context": {
            "state": handoff_after["status"] if handoff_after is not None else "unavailable",
            "ready_for_context_reset": bool(
                handoff_after and handoff_after["ready_for_context_reset"]
            ),
            "state_digest": handoff_after["state_digest"] if handoff_after else None,
            "context_only_not_file_provenance": True,
        },
        "next_safe_actions": (
            ["Resolve every blocker and rerun this read-only plan."]
            if blockers
            else [
                "Review each ordinal change against local private evidence.",
                "Keep all writers paused; v0.4.2 intentionally has no Git writer.",
                "Rerun reconcile against the exact plan commitments before any future approved writer.",
            ]
        ),
        "closed_actions": {
            "git_commit_called": False,
            "git_push_called": False,
            "git_fetch_called": False,
            "git_pull_merge_rebase_reset_clean_called": False,
            "lock_created": False,
            "receipt_written": False,
            "provider_api_called": False,
            "network_checked": remote_url is not None,
            "changed_file_bodies_read_for_hashing": bool(public_changes),
            "receipt_file_bodies_read_for_hashing": False,
            "session_handoff_context_artifacts_read": bool(
                handoff_after
                and handoff_after.get("status") != "not_required_for_git_backup"
            ),
            "credential_resolution_called": credential_mode == "stored",
            "secret_classification_performed": False,
        },
        "blockers": blockers,
        "warnings": warnings,
    }
    if _private_capture is not None and not blockers:
        # This is an in-process handoff to the exact Git writer.  It is never
        # serialized or returned by the public planner.  Keeping the ordinal
        # change-to-path map here means the writer reuses the planner's exact
        # observation instead of reconstructing a weaker parallel inventory.
        _private_capture.clear()
        _private_capture.update(
            {
                "root": root,
                "archive_id": archive_id,
                "remote_name": remote_name,
                "credential_mode": credential_mode,
                "remote_url": remote_url_after,
                "target_ref": snapshot_before["target_ref"],
                "local_head_oid": snapshot_before["local_head"],
                "remote_state": remote_after[0],
                "remote_oid": remote_after[1],
                "private_changes": private_changes,
                "public_changes": public_changes,
                "git_executable_sha256": pinned_git.sha256,
                "git_executable_identity": list(pinned_git.identity),
                "git_config_trust_sha256": snapshot_before[
                    "git_config_trust_sha256"
                ],
            }
        )
    # A final serialization check is part of the public contract.  It also
    # prevents accidental leakage through a non-JSON Python object repr.
    try:
        json.dumps(result, ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError):
        return _empty_plan_result(blockers=["plan_serialization_failed"])
    return result


def git_backup_plan(
    archive_root: Path | str,
    *,
    remote_name: str = "origin",
    branch: str | None = None,
    credential_mode: str = "anonymous",
    max_changes: int = GIT_BACKUP_PLAN_DEFAULT_MAX_CHANGES,
    max_changed_bytes: int = GIT_BACKUP_PLAN_DEFAULT_MAX_CHANGED_BYTES,
    dry_run: bool = True,
    _private_capture: dict[str, Any] | None = None,
    progress_hook: Callable[[Mapping[str, Any]], None] | None = None,
    _progress_operation: str = "git_backup_plan",
) -> dict[str, Any]:
    """Pin one Git executable, run the planner, then verify the same bytes."""

    progress = _GitBackupPlanProgress(
        progress_hook,
        operation=_progress_operation,
    )
    # This synchronous first event precedes executable hashing, filesystem
    # inspection, Git subprocesses, network access, and archive body reads.
    progress.status("starting")

    def inspect() -> dict[str, Any]:
        progress.status("pinning_git")
        pinned = _pin_git_executable()
        if pinned is None:
            return _empty_plan_result(
                blockers=["git_executable_unavailable_or_unsafe"]
            )
        token = _PINNED_GIT_EXECUTABLE.set(pinned)
        try:
            result = _git_backup_plan_with_pinned_git(
                archive_root,
                remote_name=remote_name,
                branch=branch,
                credential_mode=credential_mode,
                max_changes=max_changes,
                max_changed_bytes=max_changed_bytes,
                dry_run=dry_run,
                _private_capture=_private_capture,
                _progress=progress,
            )
            progress.status("verifying_git_pin")
            final_observation = _pin_git_at(Path(pinned.path))
            if final_observation != pinned:
                if _private_capture is not None:
                    _private_capture.clear()
                return _empty_plan_result(blockers=["git_executable_drifted"])
            executable_evidence = result.get("git_executable")
            if isinstance(executable_evidence, dict):
                executable_evidence["sha256"] = pinned.sha256
                executable_evidence["stability_verified"] = True
            return result
        finally:
            _PINNED_GIT_EXECUTABLE.reset(token)

    result = _run_plan_with_heartbeats(progress, inspect)
    progress.status("completed")
    return result


def _empty_reconcile_result(*, blockers: Iterable[str]) -> dict[str, Any]:
    return {
        "schema": GIT_BACKUP_RECONCILE_PLAN_SCHEMA,
        "ok": False,
        "dry_run": True,
        "lifecycle_action": "git_backup_reconcile_plan",
        "status": "blocked",
        "inspection_complete": False,
        "current_plan_sha256": None,
        "current_hidden_effect_set_sha256": None,
        "expected_bindings": {
            "plan_sha256_matches": False,
            "hidden_effect_set_sha256_matches": None,
            "local_head_oid_matches": None,
            "remote_oid_matches": None,
        },
        "repository": {
            "local_head_oid": None,
            "remote_oid": None,
            "relation": {
                "state": "not_computed",
                "local_only_commit_count": None,
                "remote_only_commit_count": None,
            },
        },
        "remote_observation": {
            "state": "not_attempted",
            "git_transport_confirmed_ref": False,
            "provider_confirmed": False,
        },
        "ready_for_write": False,
        "writer_available": False,
        "would_change": [],
        "files_written": [],
        "next_safe_actions": [
            "Correct the reconcile bindings or resolve blockers, then rerun the read-only plan.",
        ],
        "closed_actions": {
            "git_commit_called": False,
            "git_push_called": False,
            "git_fetch_called": False,
            "git_pull_merge_rebase_reset_clean_called": False,
            "lock_created": False,
            "receipt_written": False,
            "provider_api_called": False,
            "network_checked": False,
            "credential_resolution_called": False,
            "secret_classification_performed": False,
        },
        "blockers": _unique(blockers),
        "warnings": [],
    }


def _valid_oid(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(
        r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}",
        value,
    ) is not None


def git_backup_reconcile_plan(
    archive_root: Path | str,
    *,
    expected_plan_sha256: str,
    expected_hidden_effect_set_sha256: str | None = None,
    expected_local_head_oid: str | None = None,
    expected_remote_oid: str | None = None,
    remote_name: str = "origin",
    branch: str | None = None,
    credential_mode: str = "anonymous",
    max_changes: int = GIT_BACKUP_PLAN_DEFAULT_MAX_CHANGES,
    max_changed_bytes: int = GIT_BACKUP_PLAN_DEFAULT_MAX_CHANGED_BYTES,
    dry_run: bool = True,
    progress_hook: Callable[[Mapping[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Re-observe a plan and compare only explicit cryptographic bindings."""

    parameter_blockers: list[str] = []
    if (
        not isinstance(expected_plan_sha256, str)
        or GIT_BACKUP_SHA256_RE.fullmatch(expected_plan_sha256) is None
    ):
        parameter_blockers.append("expected_plan_sha256_invalid")
    if (
        expected_hidden_effect_set_sha256 is not None
        and (
            not isinstance(expected_hidden_effect_set_sha256, str)
            or GIT_BACKUP_SHA256_RE.fullmatch(expected_hidden_effect_set_sha256) is None
        )
    ):
        parameter_blockers.append("expected_hidden_effect_set_sha256_invalid")
    if expected_local_head_oid is not None and not _valid_oid(expected_local_head_oid):
        parameter_blockers.append("expected_local_head_oid_invalid")
    if expected_remote_oid is not None and not _valid_oid(expected_remote_oid):
        parameter_blockers.append("expected_remote_oid_invalid")
    if parameter_blockers:
        return _empty_reconcile_result(blockers=parameter_blockers)

    current = git_backup_plan(
        archive_root,
        remote_name=remote_name,
        branch=branch,
        credential_mode=credential_mode,
        max_changes=max_changes,
        max_changed_bytes=max_changed_bytes,
        dry_run=dry_run,
        progress_hook=progress_hook,
        _progress_operation="git_backup_reconcile_plan",
    )
    current_plan = current.get("plan_sha256")
    current_effects = current.get("hidden_effect_set_sha256")
    repository = current.get("repository")
    if not isinstance(repository, dict):
        repository = {
            "local_head_oid": None,
            "remote_oid": None,
            "relation": {
                "state": "not_computed",
                "local_only_commit_count": None,
                "remote_only_commit_count": None,
            },
        }
    local_oid = repository.get("local_head_oid")
    remote_oid = repository.get("remote_oid")
    bindings = {
        "plan_sha256_matches": current_plan == expected_plan_sha256,
        "hidden_effect_set_sha256_matches": (
            current_effects == expected_hidden_effect_set_sha256
            if expected_hidden_effect_set_sha256 is not None
            else None
        ),
        "local_head_oid_matches": (
            isinstance(local_oid, str)
            and local_oid.lower() == expected_local_head_oid.lower()
            if expected_local_head_oid is not None
            else None
        ),
        "remote_oid_matches": (
            isinstance(remote_oid, str)
            and remote_oid.lower() == expected_remote_oid.lower()
            if expected_remote_oid is not None
            else None
        ),
    }
    blockers = list(current.get("blockers") or [])
    if not bindings["plan_sha256_matches"]:
        blockers.append("expected_plan_sha256_mismatch")
    if bindings["hidden_effect_set_sha256_matches"] is False:
        blockers.append("expected_hidden_effect_set_sha256_mismatch")
    if bindings["local_head_oid_matches"] is False:
        blockers.append("expected_local_head_oid_mismatch")
    if bindings["remote_oid_matches"] is False:
        blockers.append("expected_remote_oid_mismatch")
    blockers = _unique(blockers)
    remote_observation = current.get("remote_observation")
    if not isinstance(remote_observation, dict):
        remote_observation = {
            "state": "not_attempted",
            "git_transport_confirmed_ref": False,
            "provider_confirmed": False,
        }
    closed_actions = dict(current.get("closed_actions") or {})
    closed_actions.setdefault("credential_resolution_called", False)
    closed_actions.setdefault("secret_classification_performed", False)
    result = {
        "schema": GIT_BACKUP_RECONCILE_PLAN_SCHEMA,
        "ok": not blockers,
        "dry_run": True,
        "lifecycle_action": "git_backup_reconcile_plan",
        "status": "reconciled" if not blockers else "drift_or_blocked",
        "inspection_complete": bool(current.get("inspection_complete")),
        "current_plan_sha256": current_plan,
        "current_hidden_effect_set_sha256": current_effects,
        "expected_bindings": bindings,
        "repository": repository,
        "remote_observation": remote_observation,
        "ready_for_write": False,
        "writer_available": False,
        "would_change": [],
        "files_written": [],
        "next_safe_actions": (
            ["All requested bindings match this read-only observation; a writer is still unavailable in v0.4.2."]
            if not blockers
            else ["Treat the plan as stale or blocked and perform no Git write."]
        ),
        "closed_actions": closed_actions,
        "blockers": blockers,
        "warnings": list(current.get("warnings") or []),
    }
    try:
        json.dumps(result, ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError):
        return _empty_reconcile_result(blockers=["reconcile_serialization_failed"])
    return result
