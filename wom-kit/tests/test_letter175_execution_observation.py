import multiprocessing
from pathlib import Path
import tempfile
import unittest

from wom_kit import operation_observation as observation
from wom_kit.operation_target_leases import TargetLeases


def _running(root, ready, release):
    with TargetLeases(root, [("object", "synthetic-target")], session_ref="synthetic-session-a"):
        ready.set()
        release.wait(20)


class ExecutionObservationTests(unittest.TestCase):
    def test_real_process_is_live_only_in_its_session_and_crash_is_not_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = list(root.rglob("*"))
            self.assertEqual(observation.inspect(root, "synthetic-session-a")["state"], "not_observed")
            self.assertEqual(before, list(root.rglob("*")))
            ctx = multiprocessing.get_context("spawn")
            ready, release = ctx.Event(), ctx.Event()
            process = ctx.Process(target=_running, args=(root, ready, release))
            process.start()
            try:
                self.assertTrue(ready.wait(12))
                before = {p: p.read_bytes() for p in root.rglob("*.live")}
                result = observation.inspect(root, "synthetic-session-a")
                self.assertEqual(result["state"], "running", result)
                self.assertEqual(result["observed_operation_count"], 1)
                self.assertFalse(result["observation_grants_permission"])
                self.assertEqual(observation.inspect(root, "synthetic-session-b")["state"], "not_observed")
                self.assertEqual(before, {p: p.read_bytes() for p in root.rglob("*.live")})
                # Synthetic worker owns no user data; kill before finally to
                # leave stale evidence and prove OS lifetime, not file/PID trust.
                process.terminate()
                process.join(10)
                self.assertTrue(list(root.rglob("*.live")))
                self.assertEqual(observation.inspect(root, "synthetic-session-a")["state"], "not_observed")
            finally:
                # A forcibly terminated multiprocessing waiter may retain the
                # Event's internal semaphore. Do not touch that orphaned IPC.
                if process.is_alive():
                    process.terminate()
                process.join(10)

    def test_normal_completion_removes_own_marker_and_same_process_inspection_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            with observation.observe(tmp, "synthetic-session-a"):
                self.assertEqual(observation.inspect(tmp, "synthetic-session-a")["state"], "running")
            self.assertEqual(list(Path(tmp).rglob("*.live")), [])
            self.assertEqual(observation.inspect(tmp, "synthetic-session-a")["state"], "not_observed")

    def test_marker_alone_never_proves_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = observation._session_directory(tmp, "synthetic-session-a", create=True)
            (directory / ("a" * 32 + ".live")).write_bytes(b"wom-execution-observation-v1\n")
            self.assertEqual(observation.inspect(tmp, "synthetic-session-a")["state"], "not_observed")
