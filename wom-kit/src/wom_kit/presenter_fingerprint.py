"""Content-free presenter fingerprint for session-grant claims (v0.4.34).

Beta letter 165 [A]: a second conversation of the same desktop app wrote
under a limited mode granted in another conversation, and nothing in the
claims said so. The presenter token (``work_session_permission``) is the
binding; this module supplies the *evidence* next to it: which process
presented the grant, without naming the process, the user or a path.

``observe()`` walks the ancestor chain of the current process and returns
the first ancestor whose image basename is not a shell or launcher — on the
Claude desktop app that is the conversation's runtime, stable inside one
conversation and distinct across conversations. The observation is hashed
with the archive receipt key inside the approval broker before it is
recorded; the raw basis (basename, pid, creation time) never leaves the
process and is never written. Any failure resolves to ``None``: the
fingerprint is evidence, never authority, and its absence is recorded as
``fingerprint_state: unavailable`` rather than refusing the write.
"""

from __future__ import annotations

import os
import sys
from typing import Any

FINGERPRINT_SCHEMA = "wom-kit/presenter-fingerprint/v0.1"
FINGERPRINT_DOMAIN = b"wom-kit/presenter-fingerprint/v0.1\x00"
# Shells and launchers are skipped so the fingerprint names the conversation
# runtime, not the wrapper that invoked ``wom``. Fixed and content-free.
LAUNCHER_BASENAMES = frozenset({
    "wom.exe", "wom", "archive.exe", "archive", "python.exe", "python", "python3", "python3.12",
    "pythonw.exe", "py.exe", "uv.exe", "uv", "uvx.exe", "uvx", "bash.exe", "bash", "sh.exe", "sh",
    "dash", "zsh", "fish", "powershell.exe", "pwsh.exe", "pwsh", "cmd.exe", "conhost.exe",
    "node.exe", "node", "npx.cmd", "npx", "cli.js",
})
MAX_ANCESTOR_DEPTH = 16


def _windows_process_table() -> dict[int, tuple[int, str]]:
    """{pid: (parent_pid, image_basename)} from one Toolhelp snapshot."""

    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)), ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    snapshot = kernel32.CreateToolhelp32Snapshot(wintypes.DWORD(0x2), wintypes.DWORD(0))
    invalid = ctypes.c_void_p(-1).value
    if snapshot in (0, None, invalid):
        raise OSError("snapshot")
    table: dict[int, tuple[int, str]] = {}
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        if not kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            raise OSError("first")
        while True:
            table[int(entry.th32ProcessID)] = (int(entry.th32ParentProcessID), str(entry.szExeFile))
            if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                break
    finally:
        kernel32.CloseHandle(snapshot)
    return table


def _windows_creation_time(pid: int) -> int:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(wintypes.DWORD(0x1000), False, wintypes.DWORD(pid))
    if not handle:
        raise OSError("open")
    try:
        creation, exit_time, kernel, user = (wintypes.FILETIME(), wintypes.FILETIME(),
                                             wintypes.FILETIME(), wintypes.FILETIME())
        if not kernel32.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exit_time),
                                        ctypes.byref(kernel), ctypes.byref(user)):
            raise OSError("times")
        return (int(creation.dwHighDateTime) << 32) | int(creation.dwLowDateTime)
    finally:
        kernel32.CloseHandle(handle)


def _windows_observation() -> dict[str, Any] | None:
    table = _windows_process_table()
    pid = os.getpid()
    for _depth in range(MAX_ANCESTOR_DEPTH):
        parent = table.get(pid)
        if parent is None:
            return None
        parent_pid, basename = parent
        if parent_pid in (0, pid) or parent_pid not in table:
            return None
        parent_basename = table[parent_pid][1]
        if parent_basename.casefold() not in LAUNCHER_BASENAMES:
            return {"image_basename": parent_basename.casefold(), "pid": parent_pid,
                    "creation_time": _windows_creation_time(parent_pid)}
        pid = parent_pid
    return None


def _linux_stat(pid: int) -> tuple[str, int, int]:
    """(comm, ppid, starttime) from /proc/<pid>/stat."""

    with open(f"/proc/{pid}/stat", "rb") as handle:
        raw = handle.read(65536)
    start = raw.index(b"(") + 1
    end = raw.rindex(b")")
    comm = raw[start:end].decode("utf-8", "replace")
    fields = raw[end + 2:].split()
    return comm, int(fields[1]), int(fields[19])


def _linux_observation() -> dict[str, Any] | None:
    pid = os.getpid()
    for _depth in range(MAX_ANCESTOR_DEPTH):
        _comm, parent_pid, _start = _linux_stat(pid)
        if parent_pid in (0, 1, pid):
            return None
        comm, _grand, start = _linux_stat(parent_pid)
        if comm.casefold() not in LAUNCHER_BASENAMES:
            return {"image_basename": comm.casefold(), "pid": parent_pid, "creation_time": start}
        pid = parent_pid
    return None


def observe() -> dict[str, Any] | None:
    """The presenter process basis, or None when it cannot be observed.

    Never raises. The returned dict is private: callers hash it with the
    archive key and discard it; it is never written or echoed.
    """

    try:
        if sys.platform.startswith("win"):
            observed = _windows_observation()
        elif sys.platform.startswith("linux"):
            observed = _linux_observation()
        else:
            return None
    except Exception:  # noqa: BLE001 - evidence only; absence is recorded, not raised
        return None
    if (type(observed) is not dict or type(observed.get("image_basename")) is not str
            or type(observed.get("pid")) is not int or type(observed.get("creation_time")) is not int):
        return None
    return {"schema": FINGERPRINT_SCHEMA, **observed}


__all__ = ["FINGERPRINT_DOMAIN", "FINGERPRINT_SCHEMA", "LAUNCHER_BASENAMES", "observe"]
