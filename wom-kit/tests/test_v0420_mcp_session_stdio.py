"""Real new-process stdio, archive OS lock, runtime guard and registration.

No writer, runtime preparation, lock or native approval is mocked. Registration
does not require native UI. These are source-entry tests, not installed-wheel
or host-application progress-display evidence. Cold start has a separate gate.
"""

import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from wom_kit import mcp_server
from wom_kit import work_session_registration as registration


KIT_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_LABEL = "SYNTHETIC_PRIVATE_STDIO_APP"
COLD_START_SECONDS = 30


def _options():
    if os.name != "nt":
        return {}
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    return {"startupinfo": startup}


class Peer:
    def __init__(self, root):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(KIT_ROOT / "src")
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment[mcp_server.MCP_ALLOWED_ROOTS_ENV] = str(root)
        self.process = subprocess.Popen([sys.executable, "-B", "-m", "wom_kit.mcp_server"],
            cwd=KIT_ROOT, env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", **_options())
        self.rows = queue.Queue()
        self.history = []
        self.errors = []
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.error_reader = threading.Thread(target=self._errors, daemon=True)
        self.reader.start()
        self.error_reader.start()

    def _read(self):
        for line in self.process.stdout:
            self.rows.put((time.monotonic(), line))
        self.rows.put((time.monotonic(), None))

    def _errors(self):
        for line in self.process.stderr:
            self.errors.append(line)

    def send(self, value):
        self.process.stdin.write(json.dumps(value, ensure_ascii=True, allow_nan=False) + "\n")
        self.process.stdin.flush()

    def request(self, request_id, method, params=None):
        self.send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})

    def next(self, timeout):
        observed, raw = self.rows.get(timeout=timeout)
        if raw is None:
            raise AssertionError("stdio ended before expected protocol message")
        value = json.loads(raw)
        if value.get("jsonrpc") != "2.0":
            raise AssertionError("stdout contained a non-protocol message")
        self.history.append((observed, value))
        return observed, value

    def until(self, predicate, timeout=5):
        deadline = time.monotonic() + timeout
        while True:
            observed, value = self.next(max(0.001, deadline - time.monotonic()))
            if predicate(value):
                return observed, value

    def result(self, request_id, timeout=5):
        return self.until(lambda value: value.get("id") == request_id, timeout)[1]

    def initialize(self):
        self.request(0, "initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                                      "clientInfo": {"name": "synthetic-stdio", "version": "1"}})
        result = self.result(0, COLD_START_SECONDS)
        if result["result"]["protocolVersion"] != "2025-11-25":
            raise AssertionError("unexpected negotiated protocol version")
        self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def close(self):
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()  # synthetic test cleanup only, never product cancellation
            self.process.wait(timeout=5)
        self.reader.join(timeout=2)
        self.error_reader.join(timeout=2)
        self.process.stdout.close()
        self.process.stderr.close()


class McpSessionStdioTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="wom-mcp-session-stdio-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        self.root.mkdir()
        (self.root / "archive.yml").write_text("archive_id: archive:personal:synthetic-stdio-session\n", encoding="utf-8")
        self.original_archive = (self.root / "archive.yml").read_bytes()

    def peer(self):
        result = Peer(self.root)
        self.addCleanup(result.close)
        result.initialize()
        return result

    def hold_archive(self):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(KIT_ROOT / "src")
        script = (
            "import sys\nfrom pathlib import Path\n"
            "from wom_kit.exact_operation_manifest import ExactOperationWriterLock\n"
            "with ExactOperationWriterLock(Path(sys.argv[1]), timeout_seconds=0):\n"
            " print('held', flush=True)\n sys.stdin.readline()\n"
        )
        process = subprocess.Popen([sys.executable, "-B", "-c", script, str(self.root)],
            cwd=KIT_ROOT, env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", **_options())
        def release():
            if not process.stdin.closed:
                process.stdin.close()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            process.stdout.close()
            process.stderr.close()
        self.addCleanup(release)
        ready = queue.Queue()
        reader = threading.Thread(target=lambda: ready.put(process.stdout.readline()), daemon=True)
        reader.start()
        self.assertEqual(ready.get(timeout=COLD_START_SECONDS), "held\n")
        reader.join(timeout=2)
        return process, release

    def manage(self, peer, request_id, arguments, token=None):
        params = {"name": "archive_work_session_manage", "arguments": {"archive_root": str(self.root), **arguments}}
        if token is not None:
            params["_meta"] = {"progressToken": token}
        peer.request(request_id, "tools/call", params)

    def preview(self, peer):
        self.manage(peer, 1, {"action": "register-app", "dry_run": True, "request": {"label": PRIVATE_LABEL}})
        result = peer.result(1)["result"]["structuredContent"]
        self.assertTrue(result["ok"])
        return {"selection": result["result"], "label": PRIVATE_LABEL}

    def private_files(self):
        return {path.relative_to(self.root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in self.root.rglob("*") if path.is_file() and path.name != ".writer.lock"}

    def test_actual_wait_progress_queries_cancel_and_fresh_process_original_registration_resume(self):
        peer = self.peer()
        original = self.preview(peer)
        held, release = self.hold_archive()
        before = self.private_files()
        started = time.monotonic()
        self.manage(peer, 20, {"action": "register-app", "apply": True, "request": original}, "wait-token")
        first, row = peer.until(lambda row: row.get("method") == "notifications/progress", 2)
        self.assertLessEqual(first - started, 2)
        self.assertEqual(row["params"], {"progressToken": "wait-token", "progress": 1})
        peer.request(21, "ping")
        self.assertEqual(peer.result(21)["result"], {})
        peer.request(22, "tools/list")
        self.assertIn("tools", peer.result(22)["result"])
        peer.request(23, "tools/call", {"name": "archive_work_session", "arguments": {
            "archive_root": str(self.root), "kind": "app"}})
        self.assertTrue(peer.result(23)["result"]["structuredContent"]["ok"])
        queued_started = time.monotonic()
        self.manage(peer, 26, {"action": "register-app", "apply": True, "request": original}, "queued-token")
        queued_first, row = peer.until(lambda row: row.get("params", {}).get("progressToken") == "queued-token", 2)
        self.assertLessEqual(queued_first - queued_started, 2)
        queued_second, row = peer.until(lambda row: row.get("params", {}).get("progressToken") == "queued-token", 10)
        self.assertLessEqual(queued_second - queued_first, 10)
        self.assertEqual(row["params"]["progress"], 2)
        if not any(observed - first >= 4.5 and row.get("params", {}).get("progressToken") == "wait-token"
                   for observed, row in peer.history):
            peer.until(lambda row: row.get("params", {}).get("progressToken") == "wait-token", 10)
        peer.send({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 26}})
        waits = [(observed, row["params"]["progress"]) for observed, row in peer.history
                 if row.get("params", {}).get("progressToken") == "wait-token"]
        self.assertGreaterEqual(len(waits), 2)
        self.assertGreaterEqual(waits[-1][0] - first, 4.5)
        self.assertTrue(all(right[1] > left[1] and right[0] - left[0] <= 10 for left, right in zip(waits, waits[1:])))
        self.assertIsNone(held.poll())
        peer.send({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {
            "requestId": 20, "reason": "PRIVATE_CANCEL_REASON"}})
        # This preview uses the serial lane, so its response proves the cancelled
        # call has ended, not merely that the reader accepted another ping.
        self.manage(peer, 24, {"action": "register-app", "dry_run": True, "request": {"label": PRIVATE_LABEL}})
        self.assertTrue(peer.result(24)["result"]["structuredContent"]["ok"])
        self.assertEqual(self.private_files(), before)
        self.assertNotIn(20, [row.get("id") for _time, row in peer.history])
        self.assertNotIn(26, [row.get("id") for _time, row in peer.history])
        release()
        self.assertEqual(held.returncode, 0)
        self.manage(peer, 25, {"action": "register-app", "resume": True, "request": original}, "wait-token")
        registered = peer.result(25)["result"]["structuredContent"]
        self.assertTrue(registered["ok"], registered)
        self.assertEqual(registered["result"]["client_app_ref"], original["selection"]["client_app_ref"])
        self.assertEqual((self.root / "archive.yml").read_bytes(), self.original_archive)
        committed = self.private_files()
        peer.close()
        self.assertEqual(peer.process.returncode, 0)
        self.assertEqual(peer.errors, [])
        fresh = self.peer()
        self.manage(fresh, 30, {"action": "register-app", "resume": True, "request": original})
        resumed = fresh.result(30)["result"]["structuredContent"]
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(resumed["result"]["client_app_ref"], registered["result"]["client_app_ref"])
        self.assertEqual(self.private_files(), committed)
        # Independent retained generation reader, not the transport response.
        snapshot = registration._store(self.root).read()
        self.assertEqual(snapshot.public_summary()["app_count"], 1)
        fresh.close()
        self.assertEqual(fresh.process.returncode, 0)
        self.assertEqual(fresh.errors, [])
        output = json.dumps([row for _time, row in peer.history + fresh.history])
        for value in (PRIVATE_LABEL, "PRIVATE_CANCEL_REASON", str(self.root)):
            self.assertNotIn(value, output)
        print("STDIO_WAIT_TIMING first_status_seconds={:.3f} largest_wait_gap_seconds={:.3f} queued_first_seconds={:.3f} queued_heartbeat_seconds={:.3f}".format(
            first - started, max(right[0] - left[0] for left, right in zip(waits, waits[1:])),
            queued_first - queued_started, queued_second - queued_first))

    def test_eof_cancels_actual_lock_wait_and_never_starts_queued_registration(self):
        peer = self.peer()
        original = self.preview(peer)
        held, _release = self.hold_archive()
        before = self.private_files()
        self.manage(peer, 20, {"action": "register-app", "apply": True, "request": original}, 1)
        peer.until(lambda row: row.get("method") == "notifications/progress", 2)
        self.manage(peer, 21, {"action": "register-app", "apply": True, "request": original}, 2)
        peer.process.stdin.close()
        peer.process.wait(timeout=5)
        self.assertEqual(peer.process.returncode, 0)
        self.assertIsNone(held.poll())
        self.assertEqual(self.private_files(), before)
        peer.reader.join(timeout=2)
        while not peer.rows.empty():
            _observed, raw = peer.rows.get_nowait()
            if raw is not None:
                self.assertEqual(json.loads(raw).get("method"), "notifications/progress")
        self.assertEqual(peer.errors, [])


if __name__ == "__main__":
    unittest.main()
