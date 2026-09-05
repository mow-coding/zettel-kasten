"""Fixed observer tests use actual isolated children, never Git or an archive."""

from contextlib import redirect_stderr
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from unittest.mock import Mock, patch

from wom_kit import cli_entry
from wom_kit import work_session_git_progress as subject
from wom_kit.exact_operation_manifest import ExactOperationProgress
from wom_kit.process_launch import noninteractive_creationflags
import test_v0419_cli_startup as startup_fixture


SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"


class _FdStream(io.StringIO):
    def fileno(self):
        return 2


class GitProgressContractTests(unittest.TestCase):
    def test_projection_preserves_only_closed_stage_and_bounded_numeric_data(self):
        event = ExactOperationProgress("PRIVATE_MANIFEST", "PRIVATE_EXECUTION", "apply", "field_verified", 1, 2, 3, 4, 2)
        self.assertEqual(subject._project(event), {"stage": "field_verified", "completed_items": 1,
            "total_items": 2, "completed_fields": 3, "total_fields": 4, "item_ordinal": 2})
        self.assertEqual(subject._project({"phase": "git_receipt_snapshot", "total_bytes": 65536,
            "processed_bytes": 1024, "elapsed_seconds": 1.25, "label": "PRIVATE", "path": "PRIVATE"}),
            {"stage": "git_receipt_snapshot", "total_bytes": 65536, "processed_bytes": 1024, "elapsed_seconds": 1.25})
        class Callback:
            def public_document(self):
                raise AssertionError("caller method must not execute")
        self.assertIsNone(subject._project(Callback()))
        for value in (True, -1, float("nan"), float("inf"), 1 << 10000, [], "PRIVATE"):
            with self.subTest(kind=type(value).__name__):
                self.assertIsNone(subject._project({"stage": "preflight", "total_bytes": value}))
        self.assertIsNone(subject._project({"stage": "PRIVATE", "total_items": 2}))

    def test_signal_install_change_then_raise_restores_handlers_without_launch(self):
        numbers = (subject.signal.SIGINT,) + ((subject.signal.SIGBREAK,)
                   if hasattr(subject.signal, "SIGBREAK") else ())
        originals = {number: object() for number in numbers}
        current, attempts = dict(originals), []

        def setter(number, handler):
            current[number] = handler
            attempts.append((number, handler))
            if len(attempts) == 1:
                raise KeyboardInterrupt("PRIVATE_SIGNAL_INSTALL")

        with redirect_stderr(_FdStream()), \
             patch.object(subject.signal, "getsignal", side_effect=lambda number: current[number]), \
             patch.object(subject.signal, "signal", side_effect=setter), \
             patch.object(subject.subprocess, "Popen") as popen:
            observer = subject._git_command_progress_observer()
            self.assertEqual(observer.status()["mode"], "unavailable")
            self.assertTrue(observer.status()["closed"])
            popen.assert_not_called()
        self.assertEqual(current, originals)
        self.assertEqual(len(attempts), 2 + 2 * len(numbers))  # Failed launch lease, then cleanup lease.

    def test_synchronous_stream_is_explicitly_non_live_and_contains_no_private_fields(self):
        stream = io.StringIO()
        with redirect_stderr(stream), patch.object(subject.subprocess, "Popen") as popen:
            with subject._git_command_progress_observer() as observer:
                observer({"stage": "waiting_for_writer", "elapsed_seconds": 2.5, "label": "PRIVATE"})
                self.assertEqual(observer.status()["mode"], "synchronous")
                self.assertFalse(observer.status()["heartbeat_available"])
                self.assertNotIn("PRIVATE", repr(observer))
            observer({"stage": "completed"})
            self.assertTrue(observer.status()["closed"])
            popen.assert_not_called()
        rows = [json.loads(line) for line in stream.getvalue().splitlines()]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["elapsed_seconds"], 2.5)
        self.assertTrue(all(row["observer_mode"] == "synchronous" and not row["heartbeat_available"]
                            and not row["completion_verified"] for row in rows))
        self.assertNotIn("PRIVATE", stream.getvalue())

    def test_child_launch_is_fixed_hidden_and_ready_before_live_then_reaped_once(self):
        process = Mock()
        read_fd, write_fd = os.pipe()
        self.addCleanup(os.close, read_fd)
        ended = threading.Event()
        class ReadyPipe(io.BytesIO):
            def readline(self, limit):
                if self.tell() == 0:
                    return super().readline(limit)
                ended.wait(5)
                return b""
        process.stdin = os.fdopen(write_fd, "wb", buffering=0)
        process.stdout = ReadyPipe(subject._READY)
        process.poll.return_value = None
        def waited(**_kwargs):
            process.poll.return_value = 0
            ended.set()
            return 0
        process.wait.side_effect = waited
        stream, startup = _FdStream(), Mock()
        cli_entry._active_watchdog = startup
        with redirect_stderr(stream), patch.dict(os.environ, {"PRIVATE_SECRET": "PRIVATE"}), \
             patch.object(subject.subprocess, "Popen", return_value=process) as popen:
            observer = subject._git_command_progress_observer()
            self.assertEqual(observer.status()["mode"], "live")
            observer({"stage": "preflight", "total_fields": 3, "archive_root": "PRIVATE"})
            observer.close()
            observer.close()
            self.assertTrue(observer.status()["closed"])
            self.assertEqual(json.loads(os.read(read_fd, 2048)), {"stage": "preflight", "total_fields": 3})
        startup.close.assert_called_once()
        self.assertIsNone(cli_entry._active_watchdog)
        args, kwargs = popen.call_args
        self.assertEqual(args[0], [sys.executable, "-I", "-B", "-c", subject._PROGRAM])
        self.assertLessEqual(set(kwargs["env"]), {"SystemRoot", "WINDIR"})
        self.assertEqual(kwargs["creationflags"], noninteractive_creationflags())
        self.assertTrue(kwargs["close_fds"])
        self.assertEqual(kwargs["bufsize"], 0)
        self.assertEqual(kwargs["stdout"], subprocess.PIPE)  # Private ready handshake, not user stdout.
        self.assertNotIn("shell", kwargs)
        self.assertNotIn("PRIVATE", repr(args) + repr(kwargs["env"]))
        process.wait.assert_called_once_with(timeout=2.0)
        self.assertEqual(stream.getvalue(), "")  # Child is the only live stderr writer.

    def test_launch_bad_ready_and_sink_failures_are_explicit_unavailable_without_exception_details(self):
        for failure in ("launch", "ready"):
            stream = _FdStream()
            process = Mock()
            process.stdin, process.stdout = io.BytesIO(), io.BytesIO(b"PRIVATE_INVALID_READY\n")
            process.poll.return_value, process.wait.return_value = None, 0
            def waited(**_kwargs):
                process.poll.return_value = 0
                return 0
            process.wait.side_effect = waited
            options = {"side_effect": OSError("PRIVATE_PATH")} if failure == "launch" else {"return_value": process}
            with self.subTest(failure=failure), redirect_stderr(stream), \
                 patch.object(subject.subprocess, "Popen", **options):
                with subject._git_command_progress_observer() as observer:
                    self.assertEqual(observer.status()["mode"], "unavailable")
                    self.assertFalse(observer.status()["heartbeat_available"])
            # The fd may be stalled: fixed unavailability travels through status,
            # never an unbounded parent fallback write to the same failed sink.
            self.assertEqual(stream.getvalue(), "")
        class BrokenStream(io.StringIO):
            def write(self, _text):
                raise OSError("PRIVATE_SINK")
        with redirect_stderr(BrokenStream()), subject._git_command_progress_observer() as observer:
            self.assertEqual(observer.status()["mode"], "unavailable")


class GitProgressProcessTests(unittest.TestCase):
    def setUp(self):
        self.helper = startup_fixture.CliStartupProcessTests()
        self.addCleanup(self.helper.doCleanups)

    def program(self, body):
        return ("import json, sys, time\n"
                f"sys.path.insert(0, {str(SOURCE_ROOT)!r})\n"
                "from wom_kit import work_session_git_progress as p\n" + body)

    def test_actual_child_heartbeats_during_silent_parent_with_complete_json_lines_and_counts(self):
        program = self.program('''with p._git_command_progress_observer() as observer:
    assert observer.status()["mode"] == "live"
    child = observer._watchdog.process
    observer({"stage": "item_started", "completed_fields": 2, "total_fields": 5,
              "processed_bytes": 12, "total_bytes": 90, "label": "PRIVATE_LABEL"})
    time.sleep(11.2)
    for ordinal in range(64):
        observer({"stage": "field_verified", "completed_fields": ordinal, "total_fields": 64})
print(json.dumps({"child_reaped": child.poll() is not None}))
''')
        process, events, _ = self.helper.spawn(program)
        observed = self.helper.collect(process, events, timeout=25)
        self.assertEqual(process.returncode, 0)
        rows = [(at, json.loads(line)) for label, at, line in observed if label == "stderr" and line is not None]
        heartbeats = [(at, row) for at, row in rows if row["event"] == "heartbeat"]
        self.assertGreaterEqual(len(heartbeats), 2)
        self.assertLessEqual(rows[0][0], 5)
        self.assertTrue(all(after[0] - before[0] <= 10 for before, after in zip(rows, rows[1:])))
        self.assertTrue(all(row["completed_fields"] == 2 and row["processed_bytes"] == 12 for _, row in heartbeats))
        self.assertTrue(all(not row["completion_verified"] and not row["private_values_echoed"] for _, row in rows))
        self.assertEqual(sum(row["event"] == "progress" for _, row in rows), 65)
        output = "".join(line for label, _, line in observed if label == "stdout" and line is not None)
        self.assertEqual(json.loads(output), {"child_reaped": True})
        self.assertNotIn("PRIVATE_LABEL", "".join(line for _, _, line in observed if line is not None))

    def test_parent_death_closes_child_stderr_without_orphan_ticks(self):
        process, events, _ = self.helper.spawn(self.program('''with p._git_command_progress_observer() as observer:
    print(json.dumps(observer.status()), flush=True)
    time.sleep(60)
'''))
        while True:
            label, _at, line = events.get(timeout=10)
            if label == "stdout" and line is not None:
                self.assertEqual(json.loads(line)["mode"], "live")
                break
        process.terminate()
        observed = self.helper.collect(process, events, timeout=8)
        self.assertTrue(any(label == "stderr" and line is None for label, _, line in observed))

    def test_context_error_reaps_child_and_invalid_wire_reports_fixed_unavailable(self):
        process, events, _ = self.helper.spawn(self.program('''try:
    with p._git_command_progress_observer() as observer:
        child = observer._watchdog.process
        child.stdin.write(b'{"stage":"preflight","label":"PRIVATE_WIRE"}\\n')
        child.stdin.flush()
        child.wait(timeout=5)
        status = observer.status()
        raise RuntimeError("PRIVATE_EXCEPTION")
except RuntimeError:
    print(json.dumps({"status": status, "child_reaped": child.poll() is not None}))
'''))
        observed = self.helper.collect(process, events, timeout=15)
        self.assertEqual(process.returncode, 0)
        rows = [json.loads(line) for label, _, line in observed if label == "stderr" and line is not None]
        self.assertTrue(any(row["event"] == "observation_unavailable" for row in rows))
        output = json.loads("".join(line for label, _, line in observed if label == "stdout" and line is not None))
        self.assertEqual(output["status"]["mode"], "unavailable")
        self.assertFalse(output["status"]["heartbeat_available"])
        self.assertTrue(output["child_reaped"])
        self.assertNotIn("PRIVATE", "".join(line for _, _, line in observed if line is not None))

    def test_child_independently_rejects_non_protocol_types_duplicates_and_oversized_frames(self):
        process, events, _ = self.helper.spawn(self.program('''results = []
payloads = [b'{"stage":[]}\\n', b'{"stage":"preflight","total_fields":true}\\n',
            b'{"stage":"preflight","elapsed_seconds":NaN}\\n',
            b'{"stage":"preflight","stage":"PRIVATE_DUPLICATE"}\\n', b'X' * (p._MAX_LINE + 1)]
for raw in payloads:
    with p._git_command_progress_observer() as observer:
        child = observer._watchdog.process
        child.stdin.write(raw)
        child.stdin.flush()
        child.wait(timeout=5)
        results.append(observer.status()["mode"])
print(json.dumps(results))
'''))
        observed = self.helper.collect(process, events, timeout=15)
        self.assertEqual(process.returncode, 0)
        for label, _, line in observed:
            if label == "stderr" and line is not None:
                self.assertFalse(json.loads(line)["completion_verified"])
        output = json.loads("".join(line for label, _, line in observed if label == "stdout" and line is not None))
        self.assertEqual(output, ["unavailable"] * 5)
        self.assertNotIn("PRIVATE", "".join(line for _, _, line in observed if line is not None))

    def test_actual_broken_stderr_sink_is_unavailable_without_startup_or_shutdown_traceback(self):
        process, events, _ = self.helper.spawn(self.program('''import os
from contextlib import redirect_stderr
read_fd, write_fd = os.pipe()
os.close(read_fd)
class BrokenSink:
    def fileno(self): return write_fd
    def write(self, value): return os.write(write_fd, value.encode("ascii"))
    def flush(self): pass
try:
    with redirect_stderr(BrokenSink()), p._git_command_progress_observer() as observer:
        status = observer.status()
finally:
    os.close(write_fd)
print(json.dumps(status))
'''))
        observed = self.helper.collect(process, events, timeout=15)
        self.assertEqual(process.returncode, 0)
        output = json.loads("".join(line for label, _, line in observed if label == "stdout" and line is not None))
        self.assertEqual(output["mode"], "unavailable")
        self.assertFalse(output["heartbeat_available"])
        self.assertEqual("".join(line for label, _, line in observed if label == "stderr" and line is not None), "")

    def test_open_undrained_sink_never_blocks_callbacks_or_close_and_never_gets_parent_fallback(self):
        process, events, _ = self.helper.spawn(self.program('''import os
from contextlib import redirect_stderr
read_fd, write_fd = os.pipe()
parent_writes = []
class StalledSink:
    def fileno(self): return write_fd
    def write(self, value): parent_writes.append(True); raise AssertionError("parent fallback")
    def flush(self): pass
with redirect_stderr(StalledSink()), p._git_command_progress_observer() as observer:
    assert observer.status()["mode"] == "live"
    child = observer._watchdog.process
    started = time.monotonic()
    for ordinal in range(20000):
        observer({"stage": "field_verified", "completed_fields": ordinal, "total_fields": 20000})
    callback_elapsed = time.monotonic() - started
    status = observer.status()
    started = time.monotonic()
    observer.close()
    close_elapsed = time.monotonic() - started
os.close(read_fd)
os.close(write_fd)
print(json.dumps({"callback_elapsed": callback_elapsed, "close_elapsed": close_elapsed,
                  "mode": status["mode"], "parent_writes": parent_writes,
                  "closed": observer.status()["closed"], "child_reaped": child.poll() is not None}))
'''))
        observed = self.helper.collect(process, events, timeout=15)
        self.assertEqual(process.returncode, 0)
        output = json.loads("".join(line for label, _, line in observed if label == "stdout" and line is not None))
        self.assertLess(output["callback_elapsed"], 2.0)
        self.assertLess(output["close_elapsed"], 6.0)
        self.assertEqual(output["mode"], "unavailable")
        self.assertEqual(output["parent_writes"], [])
        self.assertTrue(output["closed"] and output["child_reaped"])

    def test_ready_and_close_interrupts_and_cleanup_start_failure_reap_without_traceback(self):
        process, events, _ = self.helper.spawn(self.program('''import threading
from unittest.mock import patch
results = []
original_popen = p.subprocess.Popen
original_wait = threading.Event.wait
original_start = threading.Thread.start
original_watchdog = p._StartupWatchdog
for failure in ("ready", "ownership", "close", "cleanup_start"):
    children = []
    fired = [False]
    def captured(*args, **kwargs):
        child = original_popen(*args, **kwargs)
        children.append(child)
        return child
    def interrupted_wait(event, *args, **kwargs):
        caller = sys._getframe(1).f_code.co_name
        if failure == "ready" and caller == "__init__" and not fired[0]:
            fired[0] = True
            raise KeyboardInterrupt("PRIVATE_READY")
        if failure == "close" and caller == "_close_owned" and not fired[0]:
            fired[0] = True
            raise KeyboardInterrupt("PRIVATE_CLOSE")
        return original_wait(event, *args, **kwargs)
    def interrupted_owner(child):
        if failure == "ownership" and not fired[0]:
            fired[0] = True
            raise KeyboardInterrupt("PRIVATE_OWNERSHIP")
        return original_watchdog(child)
    def failed_start(worker):
        if failure == "cleanup_start" and getattr(worker._target, "__name__", "") == "_cleanup":
            fired[0] = True
            raise RuntimeError("PRIVATE_THREAD_START")
        return original_start(worker)
    with patch.object(p.subprocess, "Popen", side_effect=captured), \\
         patch.object(threading.Event, "wait", interrupted_wait), \\
         patch.object(threading.Thread, "start", failed_start), \\
         patch.object(p, "_StartupWatchdog", side_effect=interrupted_owner):
        observer = p._git_command_progress_observer()
        observer.close()
        observer.close()
    results.append({"fired": fired[0], "mode": observer.status()["mode"],
                    "closed": observer.status()["closed"], "reaped": all(c.poll() is not None for c in children)})
print(json.dumps(results))
'''))
        observed = self.helper.collect(process, events, timeout=20)
        self.assertEqual(process.returncode, 0)
        output = json.loads("".join(line for label, _, line in observed if label == "stdout" and line is not None))
        self.assertEqual(len(output), 4)
        self.assertTrue(all(row["fired"] and row["mode"] == "unavailable" and row["closed"] and row["reaped"] for row in output))
        self.assertNotIn("PRIVATE", "".join(line for _, _, line in observed if line is not None))

    def test_real_launch_signals_before_handle_return_are_deferred_then_reaped_and_handlers_restored(self):
        process, events, _ = self.helper.spawn(self.program('''import signal
from unittest.mock import patch
original_popen = p.subprocess.Popen
numbers = (signal.SIGINT,) + ((signal.SIGBREAK,) if hasattr(signal, "SIGBREAK") else ())
originals = tuple(signal.getsignal(number) for number in numbers)
results = []
for number in numbers:
    children, returned = [], []
    def captured(*args, **kwargs):
        child = original_popen(*args, **kwargs)
        children.append(child)
        # Actual Python signal dispatch at the vulnerable boundary: the caller
        # has not received/stored Popen's result. This wrapper still honors the
        # Popen ownership contract by returning the real child after dispatch.
        signal.raise_signal(number)
        returned.append(True)
        return child
    with patch.object(p.subprocess, "Popen", side_effect=captured):
        observer = p._git_command_progress_observer()
    observer.close()
    results.append({"returned": returned == [True], "mode": observer.status()["mode"],
                    "closed": observer.status()["closed"], "reaped": all(c.poll() is not None for c in children),
                    "restored": tuple(signal.getsignal(value) for value in numbers) == originals})
print(json.dumps(results))
'''))
        observed = self.helper.collect(process, events, timeout=12)
        self.assertEqual(process.returncode, 0)
        output = json.loads("".join(line for label, _, line in observed if label == "stdout" and line is not None))
        self.assertTrue(output)
        self.assertTrue(all(row == {"returned": True, "mode": "unavailable", "closed": True,
                                   "reaped": True, "restored": True} for row in output))
        for label, _, line in observed:
            if label == "stderr" and line is not None:
                self.assertFalse(json.loads(line)["completion_verified"])

    def test_real_close_signal_during_cleanup_construction_settles_once_without_traceback(self):
        process, events, _ = self.helper.spawn(self.program('''import signal, threading
from unittest.mock import patch
numbers = (signal.SIGINT,) + ((signal.SIGBREAK,) if hasattr(signal, "SIGBREAK") else ())
originals = tuple(signal.getsignal(number) for number in numbers)
original_thread = threading.Thread
results = []
for number in numbers:
    observer = p._git_command_progress_observer()
    child = observer._watchdog.process
    fired = []
    def captured(*args, **kwargs):
        worker = original_thread(*args, **kwargs)
        if getattr(kwargs.get("target"), "__name__", "") == "_cleanup":
            signal.raise_signal(number)
            fired.append(True)
        return worker
    with patch.object(threading, "Thread", side_effect=captured):
        observer.close()
    results.append({"fired": fired == [True], "mode": observer.status()["mode"],
                    "closed": observer.status()["closed"], "reaped": child.poll() is not None,
                    "restored": tuple(signal.getsignal(value) for value in numbers) == originals})
print(json.dumps(results))
'''))
        observed = self.helper.collect(process, events, timeout=12)
        self.assertEqual(process.returncode, 0)
        output = json.loads("".join(line for label, _, line in observed if label == "stdout" and line is not None))
        self.assertTrue(output)
        self.assertTrue(all(row == {"fired": True, "mode": "unavailable", "closed": True,
                                   "reaped": True, "restored": True} for row in output))
        for label, _, line in observed:
            if label == "stderr" and line is not None:
                self.assertFalse(json.loads(line)["completion_verified"])

    def test_post_ready_output_failure_exits_without_needing_another_parent_callback(self):
        process, events, _ = self.helper.spawn(self.program('''import os
from contextlib import redirect_stderr
read_fd, write_fd = os.pipe()
class Sink:
    def fileno(self): return write_fd
    def write(self, value): raise AssertionError("parent fallback")
    def flush(self): pass
with redirect_stderr(Sink()), p._git_command_progress_observer() as observer:
    assert observer.status()["mode"] == "live"
    child = observer._watchdog.process
    os.close(read_fd)
    child.wait(timeout=7)
    status = observer.status()
os.close(write_fd)
print(json.dumps({"mode": status["mode"], "heartbeat_available": status["heartbeat_available"],
                  "closed": observer.status()["closed"], "child_reaped": child.poll() is not None}))
'''))
        observed = self.helper.collect(process, events, timeout=12)
        self.assertEqual(process.returncode, 0)
        output = json.loads("".join(line for label, _, line in observed if label == "stdout" and line is not None))
        self.assertEqual(output, {"mode": "unavailable", "heartbeat_available": False, "closed": True, "child_reaped": True})
        self.assertEqual("".join(line for label, _, line in observed if label == "stderr" and line is not None), "")


if __name__ == "__main__":
    unittest.main()
