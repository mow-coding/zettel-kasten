"""CLI-owned fixed progress output, never operation or cancellation authority.

The child owns stderr until it is reaped. Parent callbacks only send a bounded
closed projection at the workflow's existing safe points; no callback executes
inside the independent heartbeat process. Non-fd embedded streams are explicitly
synchronous and do not promise live heartbeats. No domain inputs enter the child.
"""

from __future__ import annotations

import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from contextlib import contextmanager

from .cli_entry import _StartupWatchdog, handoff_startup_progress
from .process_launch import noninteractive_creationflags


_SCHEMA = "wom-kit/work-session-git-command-progress/v1"
_MAX_LINE = 2048
_MAX_NUMBER = (1 << 53) - 1
_MAX_PENDING = 128
_READY = b"git-progress-ready\n"
_PULSE = b"pulse\n"
_STAGES = frozenset({
    "starting", "waiting_for_writer", "writer_acquired_revalidation_required",
    "git_receipt_snapshot", "git_receipt_provenance", "preflight", "heartbeat",
    "item_started", "field_verified", "item_verified", "completed",
    "validating_parameters", "resolving_archive", "preflight_initial",
    "git_projection_initial", "remote_ref_initial", "receipt_inventory_initial",
    "handoff_scope_initial", "changed_content_observation", "git_blob_observation",
    "building_change_inventory", "drift_reobservation", "receipt_inventory_cas_recheck",
    "handoff_scope_final", "preflight_final", "git_projection_final", "remote_ref_final",
    "repository_relation", "finalizing_plan", "pinning_git", "verifying_git_pin",
})
_COUNTS = frozenset({
    "completed_items", "total_items", "completed_fields", "total_fields", "item_ordinal",
    "current", "total", "bytes", "completed_bytes", "total_bytes", "processed_bytes",
    "changed_bytes", "sequence",
})
_NUMBERS = _COUNTS | {"elapsed_seconds"}


@contextmanager
def _deferred_observer_signals():
    """Protect observer ownership until launch or bounded reap has settled.

    This is the existing bounded signal-deferral pattern, local to presentation:
    no domain worker, authority callback, or process discovery is involved.
    """
    originals, cancelled = [], [False]
    failed = False

    def defer(_number, _frame):
        cancelled[0] = True

    try:
        if threading.current_thread() is threading.main_thread():
            numbers = (signal.SIGINT,) + ((signal.SIGBREAK,) if hasattr(signal, "SIGBREAK") else ())
            captured = tuple((number, signal.getsignal(number)) for number in numbers)
            for number, original in captured:
                # Record ownership before a setter that may change then raise.
                originals.append((number, original))
                signal.signal(number, defer)
                if signal.getsignal(number) is not defer:
                    raise OSError()
        yield
    finally:
        for number, original in reversed(originals):
            restored = False
            for _attempt in range(3):
                try:
                    signal.signal(number, original)
                except BaseException:
                    pass
                try:
                    if signal.getsignal(number) is original:
                        restored = True
                        break
                except BaseException:
                    pass
            failed = failed or not restored
    if cancelled[0] or failed:
        # The launch or cleanup ownership boundary has settled before refusal.
        raise OSError()


def _project(event):
    if type(event) is dict:
        document = event
    else:
        # Never invoke an arbitrary caller object's public_document callback.
        from .exact_operation_manifest import ExactOperationProgress

        if type(event) is not ExactOperationProgress:
            return None
        document = {name: getattr(event, name) for name in (
            "stage", "completed_items", "total_items", "completed_fields", "total_fields", "item_ordinal",
        )}
    stage = document.get("stage", document.get("phase"))
    if type(stage) is not str or stage not in _STAGES:
        return None
    projected = {"stage": stage}
    for name in _NUMBERS:
        value = document.get(name)
        if value is None:
            continue
        types = (int, float) if name == "elapsed_seconds" else (int,)
        if type(value) not in types or not 0 <= value <= _MAX_NUMBER:
            return None
        projected[name] = value
    return projected


def _line(document):
    return (json.dumps(document, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("ascii")


def _presentation(projected, *, event, mode):
    return {"schema": _SCHEMA, **projected, "event": event, "observer_mode": mode,
            "heartbeat_available": mode == "live", "completion_verified": False,
            "private_values_echoed": False}


# Only closed constants enter this program; neither event bodies nor domain
# arguments are interpolated. The child independently rejects any non-protocol
# key/type/value, and serializes progress and timer writes through one lock.
_PROGRAM = (
    "STAGES=" + repr(tuple(sorted(_STAGES))) + "\n"
    "COUNTS=" + repr(tuple(sorted(_COUNTS))) + "\n"
    "SCHEMA=" + repr(_SCHEMA) + "\n"
    "MAX_LINE=" + str(_MAX_LINE) + "\n"
    "MAX_NUMBER=" + str(_MAX_NUMBER) + "\n"
    "READY=" + repr(_READY) + "\n" + r'''
import json, os, queue, threading, time
stop = threading.Event()
failed = threading.Event()
writer_done = threading.Event()
pending_output = queue.Queue(maxsize=128)
state = {"stage": "starting"}
def emit(event):
    value = {"schema": SCHEMA, **state, "event": event,
             "observer_mode": "unavailable" if event == "observation_unavailable" else "live",
             "heartbeat_available": event != "observation_unavailable",
             "completion_verified": False, "private_values_echoed": False}
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")
    while raw:
        written = os.write(2, raw)
        if written <= 0:
            raise OSError()
        raw = raw[written:]
def pairs(rows):
    value = {}
    for key, field in rows:
        if key in value:
            raise ValueError()
        value[key] = field
    return value
def validate(raw):
    if len(raw) > MAX_LINE or not raw.endswith(b"\n"):
        raise ValueError()
    value = json.loads(raw, object_pairs_hook=pairs)
    if type(value) is not dict or set(value) - (set(COUNTS) | {"stage", "elapsed_seconds"}):
        raise ValueError()
    if type(value.get("stage")) is not str or value["stage"] not in STAGES:
        raise ValueError()
    for name, field in value.items():
        if name == "stage":
            continue
        types = (int, float) if name == "elapsed_seconds" else (int,)
        if type(field) not in types or not 0 <= field <= MAX_NUMBER:
            raise ValueError()
    return value
def write_output():
    global state
    try:
        emit("started")
        os.write(1, READY)
        last_output = time.monotonic()
        while True:
            if failed.is_set():
                emit("observation_unavailable")
                return
            if stop.is_set() and pending_output.empty():
                return
            try:
                state = pending_output.get(timeout=0.1)
            except queue.Empty:
                if time.monotonic() - last_output >= 5.0:
                    emit("heartbeat")
                    os.write(1, b"pulse\n")
                    last_output = time.monotonic()
            else:
                emit("progress")
                os.write(1, b"pulse\n")
                last_output = time.monotonic()
    except BaseException:
        failed.set()
        # Output death cannot leave the parent mistaking a blocked stdin reader
        # for a live heartbeat process. This child has no mutation authority.
        os._exit(1)
    finally:
        writer_done.set()
try:
    threading.Thread(target=write_output, daemon=True).start()
    pending = b""
    while not failed.is_set():
        chunk = os.read(0, MAX_LINE + 1 - len(pending))
        if not chunk:
            if pending:
                raise ValueError()
            break
        pending += chunk
        while b"\n" in pending:
            raw, pending = pending.split(b"\n", 1)
            pending_output.put_nowait(validate(raw + b"\n"))
        if len(pending) > MAX_LINE:
            raise ValueError()
except BaseException:
    failed.set()
finally:
    stop.set()
    # The reader never waits on stderr. Even an undrained inherited sink cannot
    # retain the child after parent EOF. No Python buffered IO lock is involved.
    writer_done.wait(1.0)
    os._exit(0 if not failed.is_set() else 1)
'''
)


class _GitCommandProgressObserver:
    """Private presentation object; status is not a write-admission capability."""

    def __init__(self):
        self._stream = sys.stderr
        self._mode = "unavailable"
        self._closed = False
        self._closing = False
        self._fd_backed = False
        self._watchdog = None
        self._lock = threading.RLock()
        self._last = {"stage": "starting"}
        self._pending = queue.Queue(maxsize=_MAX_PENDING)
        self._sender = None
        self._reader = None
        self._reader_done = threading.Event()
        self._last_pulse = 0.0
        self._sender_done = threading.Event()
        self._sender_stop = threading.Event()
        self._failed = threading.Event()
        self._cleanup_done = threading.Event()
        self._cleanup_thread = None
        try:
            handoff_startup_progress()
        except BaseException:
            # No owned child exists yet, and cancellation is not a traceback.
            return
        try:
            descriptor = self._stream.fileno()
        except (AttributeError, OSError, ValueError):
            self._mode = "synchronous"
            self._emit_parent("started")
            return
        except Exception:
            self._emit_parent("observation_unavailable")
            return
        if type(descriptor) is not int or descriptor < 0:
            self._emit_parent("observation_unavailable")
            return
        self._fd_backed = True
        environment = {name: value for name in ("SystemRoot", "WINDIR")
                       if (value := os.environ.get(name)) is not None}
        process = None
        try:
            with _deferred_observer_signals():
                process = subprocess.Popen(
                    [sys.executable, "-I", "-B", "-c", _PROGRAM], stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=self._stream, env=environment,
                    close_fds=True, bufsize=0, creationflags=noninteractive_creationflags(),
                )
                self._watchdog = _StartupWatchdog(process)
            ready, observed = threading.Event(), []

            def read_ready():
                try:
                    observed.append(process.stdout.readline(len(_READY) + 1))
                    if observed == [_READY]:
                        self._last_pulse = time.monotonic()
                        ready.set()
                        while process.stdout.readline(len(_PULSE) + 1) == _PULSE:
                            self._last_pulse = time.monotonic()
                    if not self._closing:
                        self._failed.set()
                except BaseException:
                    if not self._closing:
                        self._failed.set()
                finally:
                    ready.set()
                    self._reader_done.set()

            reader = threading.Thread(target=read_ready, daemon=True)
            self._reader = reader
            reader.start()
            if not ready.wait(5.0) or observed != [_READY] or process.poll() is not None:
                raise OSError()
            self._sender = threading.Thread(target=self._send, daemon=True)
            self._sender.start()
            self._mode = "live"
        except BaseException:
            self._failed.set()
            self._mode = "unavailable"
            if process is not None and self._watchdog is None:
                self._watchdog = _StartupWatchdog(process)
            self.close()

    def __repr__(self):
        return "<_GitCommandProgressObserver presentation only>"

    def _emit_parent(self, event):
        try:
            self._stream.write(_line(_presentation(self._last, event=event, mode=self._mode)).decode("ascii"))
            self._stream.flush()
        except Exception:
            self._mode = "unavailable"

    def _send(self):
        """Only this fixed worker touches the child pipe; no data callbacks."""
        try:
            descriptor = self._watchdog.process.stdin.fileno()
            while not self._sender_stop.is_set():
                try:
                    raw = self._pending.get(timeout=0.1)
                except queue.Empty:
                    continue
                if raw is None:
                    return
                while raw:
                    written = os.write(descriptor, raw)
                    if written <= 0:
                        raise OSError()
                    raw = raw[written:]
        except BaseException:
            self._failed.set()
        finally:
            self._sender_done.set()

    def _cleanup(self, watchdog):
        """Bounded observer-only reap, unaffected by the main thread's Ctrl-C."""
        process = watchdog.process
        try:
            if self._sender is not None and not self._sender_done.wait(0.25):
                # Kill before any close/flush/join on a possibly blocked sender.
                process.terminate()
            try:
                watchdog.close()
            except BaseException:
                self._failed.set()
                process.kill()
                process.wait(timeout=1.0)
            if process.poll() is None:
                process.kill()
                process.wait(timeout=1.0)
        except BaseException:
            self._failed.set()
        finally:
            self._sender_stop.set()
            for worker, done in ((self._sender, self._sender_done), (self._reader, self._reader_done)):
                if worker is not None:
                    if worker.ident is None:
                        done.set()
                    else:
                        try:
                            worker.join(timeout=1.0)
                        except BaseException:
                            self._failed.set()
            if process.poll() is not None:
                for stream in (process.stdin, process.stdout):
                    if stream is not None:
                        try:
                            stream.close()
                        except BaseException:
                            self._failed.set()
            self._cleanup_done.set()

    def __call__(self, event):
        with self._lock:
            if self._closed or self._closing:
                return
            projected = _project(event)
            if projected is None:
                return
            self._last = projected
            if self._mode == "synchronous":
                self._emit_parent("progress")
            elif self._mode == "live":
                try:
                    if self._failed.is_set() or self._watchdog.process.poll() is not None:
                        raise OSError()
                    raw = _line(projected)
                    if len(raw) > _MAX_LINE:
                        raise ValueError()
                    self._pending.put_nowait(raw)
                except Exception:
                    self._failed.set()
                    self._mode = "unavailable"

    def status(self):
        with self._lock:
            if self._failed.is_set() or (not self._closed and self._mode == "live" and (
                    self._watchdog.process.poll() is not None or time.monotonic() - self._last_pulse > 10.0)):
                self._mode = "unavailable"
            return {"mode": self._mode, "heartbeat_available": self._mode == "live" and not self._closed,
                    "closed": self._closed, "completion_verified": False, "private_values_echoed": False}

    def close(self):
        try:
            with _deferred_observer_signals():
                self._close_owned()
        except BaseException:
            self._failed.set()
            self._mode = "unavailable"
            if not self._closed:
                # A signal-handler installation failure must not skip owned
                # cleanup. One bounded fallback retains truthful closed state.
                try:
                    self._close_owned()
                except BaseException:
                    pass

    def _close_owned(self):
        with self._lock:
            if self._closed:
                return
            self._closing = True
            watchdog = self._watchdog
            if watchdog is None:
                self._closed = True
                return
            if self._cleanup_thread is None:
                try:
                    self._pending.put_nowait(None)
                except queue.Full:
                    self._sender_stop.set()
                try:
                    self._cleanup_thread = threading.Thread(target=self._cleanup, args=(watchdog,), daemon=True)
                    self._cleanup_thread.start()
                except BaseException:
                    self._failed.set()
                    self._sender_stop.set()
                    # start() may fail before launch or after launch. Killing
                    # this observer is safe in either case; retain its handle.
                    try:
                        watchdog.process.kill()
                    except BaseException:
                        pass
                    self._cleanup_thread = None
        # Do not hold the observer lock or abandon cleanup on repeated Ctrl-C.
        deadline = time.monotonic() + 8.0
        while not self._cleanup_done.is_set() and time.monotonic() < deadline:
            try:
                if (watchdog.process.poll() is not None and (self._sender is None or self._sender_done.is_set())
                        and (self._reader is None or self._reader_done.is_set())):
                    break
                self._cleanup_done.wait(timeout=0.1)
            except BaseException:
                self._failed.set()
        with self._lock:
            if (watchdog.process.poll() is not None and (self._sender is None or self._sender_done.is_set())
                    and (self._reader is None or self._reader_done.is_set())):
                for stream in (watchdog.process.stdin, watchdog.process.stdout):
                    if stream is not None:
                        try:
                            stream.close()
                        except BaseException:
                            self._failed.set()
                self._watchdog = None
                self._closed = True
            else:
                # Retain ownership for a later cleanup attempt; never say reaped.
                self._failed.set()
                if self._cleanup_done.is_set():
                    self._cleanup_thread = None
                    self._cleanup_done.clear()
            if self._failed.is_set():
                self._mode = "unavailable"

    def __enter__(self):
        return self

    def __exit__(self, *_exception):
        self.close()
        return False


def _git_command_progress_observer():
    """Own progress output until close; the command owns admission and settlement."""
    return _GitCommandProgressObserver()
