"""Cross-platform launch flags for invisible noninteractive child processes.

WOM uses native UI for the decisions that require a human.  Those approval
windows must stay visible.  Git, Docker, Python runtime probes, and other
captured or discarded child processes are different: on Windows, launching a
console executable without an explicit flag can flash a black console window.

Callers opt in by passing :func:`noninteractive_creationflags` to
``subprocess.run`` or ``subprocess.Popen``.  Keeping the opt-in explicit makes
it difficult to accidentally hide an interactive approval or credential UI.
"""

from __future__ import annotations

import os
from pathlib import Path
import multiprocessing
import multiprocessing.spawn as multiprocessing_spawn
import stat
import subprocess
import sys
import threading
from typing import Protocol


# CPython exposes subprocess.CREATE_NO_WINDOW on Windows.  Keep the documented
# Win32 value as a fallback so an alternate compatible runtime cannot silently
# regress to a visible console.
WINDOWS_CREATE_NO_WINDOW = int(
    getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
)
_IS_WINDOWS = os.name == "nt"
_SPAWN_EXECUTABLE_LOCK = threading.RLock()


class _StartableProcess(Protocol):
    def start(self) -> None: ...


class ProcessLaunchError(RuntimeError):
    """A child could not be launched under the declared visibility policy."""


def _windows_pythonw_executable() -> str:
    """Return the sibling GUI interpreter used by Windows spawn children.

    ``multiprocessing`` hard-codes creation flags to zero on Windows.  Pointing
    its one spawn at the standard sibling ``pythonw.exe`` prevents a transient
    console from being created while still allowing the child to create native
    approval or credential windows.
    """

    try:
        current = Path(sys.executable).resolve(strict=True)
        candidate = current.with_name("pythonw.exe")
        observed = os.lstat(candidate)
    except (OSError, RuntimeError) as exc:
        raise ProcessLaunchError("windows_pythonw_unavailable") from exc
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if not stat.S_ISREG(observed.st_mode) or (
        reparse_flag
        and getattr(observed, "st_file_attributes", 0) & reparse_flag
    ):
        raise ProcessLaunchError("windows_pythonw_unsafe")
    return os.fspath(candidate)


def noninteractive_creationflags(existing: int = 0) -> int:
    """Return launch flags that never create a console for background work.

    ``existing`` lets containment-sensitive callers preserve flags such as
    ``CREATE_NEW_PROCESS_GROUP`` or ``CREATE_SUSPENDED``.  On non-Windows
    systems the value is unchanged; ordinary callers pass zero, which is the
    only portable value accepted by :mod:`subprocess`.

    This helper is intentionally *not* a default subprocess wrapper.  Native
    approval and secure-input UI stay visible because only explicitly
    noninteractive call sites opt in.
    """

    if isinstance(existing, bool) or not isinstance(existing, int) or existing < 0:
        raise ValueError("noninteractive_creationflags_invalid")
    if not _IS_WINDOWS:
        return existing
    return existing | WINDOWS_CREATE_NO_WINDOW


def start_multiprocessing_process_no_console(process: _StartableProcess) -> None:
    """Start one spawn process without creating a Windows console.

    ``multiprocessing.set_executable`` is process-global.  Every production
    multiprocessing child uses this helper, so a lock can cover the brief
    executable substitution from immediately before ``start`` until CPython
    has captured its spawn executable.  The prior executable is restored even
    when ``start`` raises.  Other platforms use the ordinary start path.
    """

    if not _IS_WINDOWS:
        process.start()
        return
    hidden_executable = _windows_pythonw_executable()
    with _SPAWN_EXECUTABLE_LOCK:
        previous_executable = multiprocessing_spawn.get_executable()
        try:
            multiprocessing.set_executable(hidden_executable)
            process.start()
        finally:
            multiprocessing.set_executable(previous_executable)
