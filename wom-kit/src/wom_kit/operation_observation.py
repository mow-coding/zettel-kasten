"""Ephemeral OS liveness diagnostics, never permission or completion evidence.

Windows uses a non-inherited manual-reset event held only while executing.
Unix uses a private advisory lock. Stale files and reused process IDs cannot
turn a stopped operation into a running one. Inspection creates no files.
"""
from contextlib import contextmanager
from pathlib import Path
import errno
import hashlib
import os
import re
import stat
import uuid

from .exact_operation_manifest import EXACT_OPERATION_LOCAL_ROOT, _ensure_private_directory


def _session_directory(root, session_ref, *, create=False):
    if type(session_ref) is not str or not session_ref:
        raise ValueError("operation_observation_invalid")
    root = Path(root).resolve(strict=True)
    digest = hashlib.sha256(session_ref.encode("utf-8")).hexdigest()
    parts = (*Path(EXACT_OPERATION_LOCAL_ROOT).parts, "execution-observations", digest)
    if create:
        return _ensure_private_directory(root, parts)
    current = root
    for part in parts:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            return None
        if (not stat.S_ISDIR(info.st_mode) or current.is_symlink()
                or getattr(info, "st_file_attributes", 0) & 0x400):
            raise OSError("operation_observation_path_unsafe")
    return current


def _event_name(path):
    identity = os.path.normcase(str(path.parent.resolve())).encode("utf-8")
    return "Local\\WOMExecution-" + hashlib.sha256(identity).hexdigest() + "-" + path.stem


def _kernel():
    import ctypes
    from ctypes import wintypes as w
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    for name, args, result in (
        ("CreateEventW", [w.LPVOID, w.BOOL, w.BOOL, w.LPCWSTR], w.HANDLE),
        ("OpenEventW", [w.DWORD, w.BOOL, w.LPCWSTR], w.HANDLE),
        ("WaitForSingleObject", [w.HANDLE, w.DWORD], w.DWORD),
        ("ResetEvent", [w.HANDLE], w.BOOL),
        ("CloseHandle", [w.HANDLE], w.BOOL),
    ):
        fn = getattr(kernel, name)
        fn.argtypes, fn.restype = args, result
    return kernel


@contextmanager
def observe(root, session_ref):
    """Optional diagnosis must not add approval or prevent authorized work."""
    path = handle = stream = kernel = None
    try:
        directory = _session_directory(root, session_ref, create=True)
        path = directory / (uuid.uuid4().hex + ".live")
        if os.name == "nt":
            import ctypes
            kernel = _kernel()
            handle = kernel.CreateEventW(None, True, True, _event_name(path))
            if not handle or ctypes.get_last_error() == 183:
                if handle:
                    kernel.CloseHandle(handle)
                    handle = None
                raise OSError("operation_observation_unavailable")
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        stream = os.fdopen(descriptor, "w+b")
        if os.name != "nt":
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        stream.write(b"wom-execution-observation-v1\n")
        stream.flush()
    except (OSError, ValueError):
        # Missing diagnostic evidence is reported as unobserved, not stopped.
        pass
    try:
        yield
    finally:
        if handle:
            kernel.ResetEvent(handle)
            kernel.CloseHandle(handle)
        if stream:
            stream.close()
            # Only this invocation's exclusively-created marker belongs to us.
            try:
                path.unlink()
            except OSError:
                pass


def _live(path):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or path.is_symlink()
            or getattr(info, "st_file_attributes", 0) & 0x400):
        raise OSError("operation_observation_path_unsafe")
    if os.name == "nt":
        import ctypes
        kernel = _kernel()
        handle = kernel.OpenEventW(0x00100000, False, _event_name(path))
        if not handle:
            if ctypes.get_last_error() == 2:
                return False
            raise OSError("operation_observation_unavailable")
        try:
            state = kernel.WaitForSingleObject(handle, 0)
            if state not in (0, 258):
                raise OSError("operation_observation_unavailable")
            return state == 0
        finally:
            kernel.CloseHandle(handle)
    import fcntl
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except OSError as error:
            if error.errno in (errno.EACCES, errno.EAGAIN):
                return True
            raise
        fcntl.flock(stream, fcntl.LOCK_UN)
        return False


def inspect(root, session_ref):
    count, complete = 0, True
    try:
        directory = _session_directory(root, session_ref)
        if directory is not None:
            for index, path in enumerate(directory.iterdir()):
                if index >= 1024:
                    complete = False
                    break
                if re.fullmatch(r"[0-9a-f]{32}\.live", path.name):
                    try:
                        count += int(_live(path))
                    except FileNotFoundError:
                        pass  # Operation finished between listing and probing.
    except (OSError, ValueError):
        complete = False
    return {"state": "running" if count else "not_observed" if complete else "unavailable",
        "observed_operation_count": count, "observation_complete": complete,
        "observation_scope": "instrumented_target_operations_at_inspection_time",
        "absence_is_proof_of_idle": False, "session_claim_is_execution_proof": False,
        "host_process_lookup_is_wom_execution_proof": False, "observation_grants_permission": False}
