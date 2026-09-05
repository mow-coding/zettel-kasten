"""Bounded stdio scheduling for session management, never write authority.

Legacy-only connections keep synchronous dispatch. A managed mutation opens
one serial worker lane; only the explicitly audited queries bypass that lane.
Cancellation is cooperative at the existing queue/writer-wait boundary, not
thread termination, approval revocation or a promise to undo committed work.
The existing line reader is unchanged: these limits bound retained queue
payloads, not the memory needed to parse an oversized individual input line.
"""

from collections import deque
from contextvars import ContextVar
import json
import threading
import time

from .work_session_command_modes import resolve_work_session_mode


MAX_PENDING_REQUESTS = 16
MAX_QUEUED_MESSAGE_BYTES = 65536
QUEUE_HEARTBEAT_SECONDS = 5
_SESSION_REQUEST = ContextVar("wom_mcp_session_request", default=None)


def current_session_request():
    return _SESSION_REQUEST.get()


def _key(value):
    return (type(value), value) if type(value) in (str, int) else None


def _request_key(value):
    # Legacy JSON-RPC accepts finite floats and null. Keep that synchronous
    # ABI, but never let numeric 1.0 alias an active MCP integer request 1.
    if type(value) in (int, float):
        return (int, value)
    return (type(value), value)


def is_management_request(message):
    return (type(message) is dict and message.get("method") == "tools/call"
            and type(message.get("params")) is dict
            and message["params"].get("name") == "archive_work_session_manage")


def management_metadata(params):
    """Return (valid, optional token); private metadata is never reflected."""
    if "_meta" not in params:
        return True, None
    meta = params["_meta"]
    if type(meta) is not dict:
        return False, None
    if "progressToken" not in meta:
        return True, None
    token = meta["progressToken"]
    return (_key(token) is not None, token if _key(token) is not None else None)


def _managed_mutation(message):
    arguments = message["params"].get("arguments")
    if type(arguments) is not dict:
        return False
    mode = resolve_work_session_mode(action=arguments.get("action"), **{
        key: arguments.get(key, False)
        for key in ("dry_run", "approve", "apply", "resume", "review_original")
    })
    return mode["available"] and mode["potential_write"]


def _reader_safe(message):
    if message.get("method") in {"ping", "tools/list"}:
        return True
    return (message.get("method") == "tools/call"
            and type(message.get("params")) is dict
            and message["params"].get("name") == "archive_work_session")


def _error(request_id, code, message):
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


class SessionRequest:
    """Ephemeral callbacks. Repr and progress never include domain inputs."""

    def __init__(self, token, send):
        self._token = token
        self._send = send
        self._lock = threading.RLock()
        self._cancel = False
        self._observed_cancel = False
        self._terminal = False
        self._sequence = 0
        self._queued = True
        self._last_queue_progress = None

    def __repr__(self):
        return "<McpSessionRequest>"

    def cancel(self):
        with self._lock:
            if not self._terminal:
                self._cancel = True

    def cancel_requested(self):
        with self._lock:
            if not self._terminal and self._cancel:
                self._observed_cancel = True
                return True
            return False

    def progress(self, event):
        # Only original wait events are supported. No labels, elapsed values,
        # supplied message, total, ownership or guessed domain progress escape.
        if type(event) is not dict or type(event.get("stage")) is not str or event["stage"] not in {
                "waiting_for_writer", "writer_acquired_revalidation_required"}:
            return
        with self._lock:
            if self._terminal or self._cancel or self._token is None:
                return
            self._emit_progress()

    def _emit_progress(self):
        self._sequence += 1
        self._send({"jsonrpc": "2.0", "method": "notifications/progress", "params": {
            "progressToken": self._token, "progress": self._sequence,
        }})

    def queued_progress(self):
        with self._lock:
            if self._terminal or self._cancel or not self._queued or self._token is None:
                return
            now = time.monotonic()
            if self._last_queue_progress is not None and now - self._last_queue_progress < QUEUE_HEARTBEAT_SECONDS:
                return
            self._last_queue_progress = now
            self._emit_progress()

    def enter_execution(self):
        with self._lock:
            self._queued = False

    def finish(self, response, *, retire=lambda: None):
        with self._lock:
            if self._terminal:
                return
            self._terminal = True
            result = response.get("result") if type(response) is dict else None
            content = result.get("structuredContent") if type(result) is dict else None
            accepted = (self._observed_cancel and type(content) is dict
                        and content.get("schema") == "wom-kit/work-session-management/v1"
                        and content.get("ok") is False
                        and content.get("reason_code") == "work_session_wait_cancelled")
            # Release this exact routing entry before a client can observe the
            # terminal response and reuse its now-completed progress token.
            retire()
            # An event set after the last cooperative check does not cancel a
            # success or suppress its original evidence, even during shutdown.
            if response is not None and not accepted:
                self._send(response)


class SessionStdioTransport:
    def __init__(self, handle, write, valid_id):
        self._handle, self._write, self._valid_id = handle, write, valid_id
        self._condition = threading.Condition()
        self._output_lock = threading.Lock()
        self._pending = deque()
        self._active = {}
        self._tokens = set()
        self._worker = None
        self._heartbeat = None
        self._closed = False
        self._output_failed = False

    @property
    def stopped(self):
        with self._condition:
            return self._closed

    def send(self, response):
        with self._output_lock:
            if self._output_failed:
                return False
            try:
                succeeded = self._write(response)
            except Exception:
                # A broken/misbehaving output sink must not create an uncaught
                # worker traceback containing transport or tool inputs.
                succeeded = False
            if not succeeded:
                self._output_failed = True
        if not succeeded:
            self.close(wait=False)
        return succeeded

    def _notify(self, message):
        if message.get("method") != "notifications/cancelled":
            return
        params = message.get("params")
        key = _key(params.get("requestId")) if type(params) is dict else None
        if key is None:
            return
        with self._condition:
            entry = self._active.get(key)
            queued = entry is not None and any(item[1] == key for item in self._pending)
            if queued and entry[0] is not None:
                self._pending = deque(item for item in self._pending if item[1] != key)
                self._active.pop(key)
                if entry[1] is not None:
                    self._tokens.discard(entry[1])
                self._condition.notify_all()
        # The optional reason is neither retained nor read. Unknown, finished,
        # legacy and initialize requests have no cancellable session context.
        if entry is not None and entry[0] is not None:
            entry[0].cancel()
            if queued:
                entry[0].finish(None)

    def dispatch(self, message):
        if self.stopped:
            return
        valid = (type(message) is dict and message.get("jsonrpc") == "2.0"
                 and type(message.get("method")) is str
                 and ("id" not in message or self._valid_id(message["id"])))
        if not valid:
            self._respond_inline(message)
            return
        if "id" not in message:
            self._notify(message)
            return
        key = _request_key(message["id"])
        managed = is_management_request(message)
        token = None
        if managed:
            if _key(message["id"]) is None:
                self.send(_error(None, -32600, "Invalid Request"))
                return
        with self._condition:
            id_collision = key in self._active
        if id_collision:
            self.send(_error(None, -32600, "Invalid Request"))
            return
        if managed:
            metadata_valid, token = management_metadata(message["params"])
            if not metadata_valid:
                self.send(_error(message["id"], -32602, "Invalid params"))
                return
        token_key = _key(token)
        with self._condition:
            token_collision = token_key is not None and token_key in self._tokens
        if token_collision:
            self.send(_error(message["id"], -32600, "Invalid Request"))
            return
        # Preserve old synchronous dispatch and finite-input/EOF behavior until
        # a real managed mutation needs asynchronous waiting. After activation,
        # unaudited tools never execute concurrently with the serial lane.
        if _reader_safe(message) or (self._worker is None and not (managed and _managed_mutation(message))):
            self._respond_inline(message)
            return
        within_limit = False
        try:
            within_limit = len(json.dumps(message, ensure_ascii=True, allow_nan=False).encode("utf-8")) <= MAX_QUEUED_MESSAGE_BYTES
        except Exception:
            pass
        if not within_limit:
            self.send(_error(message["id"], -32602, "Invalid params"))
            return
        context = SessionRequest(token, self.send) if managed else None
        with self._condition:
            if self._closed:
                return
            full = len(self._pending) >= MAX_PENDING_REQUESTS
            if not full:
                entry = (context, token_key)
                if key is not None:
                    self._active[key] = entry
                if token_key is not None:
                    self._tokens.add(token_key)
                self._pending.append((message, key, context, entry))
                if self._worker is None:
                    self._worker = threading.Thread(target=self._run, name="wom-mcp-serial")
                    self._heartbeat = threading.Thread(target=self._queue_heartbeat, name="wom-mcp-queue-progress")
                    self._worker.start()
                    self._heartbeat.start()
                self._condition.notify_all()
        if full:
            self.send(_error(message["id"], -32000, "Server busy"))
        elif context is not None:
            context.queued_progress()

    def _respond_inline(self, message):
        response = self._handle(message)
        if response is not None:
            self.send(response)

    def _remove(self, key, expected_entry):
        with self._condition:
            if self._active.get(key) is expected_entry:
                self._active.pop(key)
                if expected_entry[1] is not None:
                    self._tokens.discard(expected_entry[1])

    def _run(self):
        while True:
            with self._condition:
                while not self._pending and not self._closed:
                    self._condition.wait()
                if self._closed:
                    return
                message, key, context, entry = self._pending.popleft()
            try:
                if context is not None:
                    context.enter_execution()
                if context is not None and context.cancel_requested():
                    context.finish(None)
                    continue
                marker = _SESSION_REQUEST.set(context)
                try:
                    response = self._handle(message)
                except Exception:
                    response = _error(message.get("id"), -32603, "Internal error")
                finally:
                    _SESSION_REQUEST.reset(marker)
                if context is not None:
                    context.finish(response, retire=lambda: self._remove(key, entry))
                elif response is not None:
                    self._remove(key, entry)
                    self.send(response)
            finally:
                self._remove(key, entry)

    def _queue_heartbeat(self):
        # One queued-only scheduler, not one thread per request. It never emits
        # after a job enters a native dialog/writer, nor invents domain progress.
        while True:
            with self._condition:
                if self._closed:
                    return
                contexts = [item[2] for item in self._pending if item[2] is not None]
                self._condition.wait(timeout=1 if contexts else None)
                if self._closed:
                    return
                contexts = [item[2] for item in self._pending if item[2] is not None]
            for context in contexts:
                context.queued_progress()

    def close(self, *, wait=True):
        with self._condition:
            self._closed = True
            contexts = [entry[0] for entry in self._active.values() if entry[0] is not None]
            abandoned = list(self._pending)
            self._pending.clear()
            self._condition.notify_all()
        for context in contexts:
            context.cancel()
        for _message, key, context, entry in abandoned:
            if context is not None:
                context.finish(None)
            self._remove(key, entry)
        worker = self._worker
        if wait and worker is not None and worker is not threading.current_thread():
            # No forced termination of an approval dialog or entered writer.
            worker.join()
        heartbeat = self._heartbeat
        if wait and heartbeat is not None and heartbeat is not threading.current_thread():
            heartbeat.join()
