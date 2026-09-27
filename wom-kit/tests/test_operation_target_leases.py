import multiprocessing
from pathlib import Path
import tempfile
import time
import unittest

from wom_kit.exact_operation_manifest import ExactOperationManifestError, FileExactOperationCheckpointStore, exact_operation_writer_lock
from wom_kit.operation_target_leases import TargetLease, TargetLeases, ExecutionCheckpointStore


def _hold(root, ready, release):
    with TargetLeases(root, [("object", "synthetic-object")]):
        ready.set()
        release.wait(15)


class TargetLeaseTests(unittest.TestCase):
    def test_real_process_contention_is_target_only_bounded_and_cancelable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            context = multiprocessing.get_context("spawn")
            ready, release = context.Event(), context.Event()
            process = context.Process(target=_hold, args=(root, ready, release))
            process.start()
            try:
                self.assertTrue(ready.wait(10))
                with TargetLeases(root, [("object", "unrelated-object")]), exact_operation_writer_lock(root):
                    self.assertTrue(process.is_alive())
                started = time.monotonic()
                with self.assertRaisesRegex(ExactOperationManifestError, "exact_operation_writer_busy"):
                    with TargetLeases(root, [("object", "synthetic-object")], timeout_seconds=.1):
                        self.fail("must contend")
                self.assertLess(time.monotonic() - started, 2)
                def cancel():
                    raise InterruptedError("synthetic cancellation")
                with self.assertRaises(InterruptedError):
                    with TargetLeases(root, [("object", "synthetic-object")], heartbeat=cancel):
                        self.fail("must cancel")
            finally:
                release.set()
                process.join(10)
                if process.is_alive():
                    process.terminate()
                    process.join()
            self.assertEqual(process.exitcode, 0)
            with TargetLeases(root, [("object", "synthetic-object")]):
                pass

    def test_scoped_checkpoints_cannot_write_another_execution_or_act_as_global_lock(self):
        execution = "sha256:" + "a" * 64
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with TargetLease(root, kind="execution", reference=execution) as lease:
                with self.assertRaises(ExactOperationManifestError):
                    FileExactOperationCheckpointStore(root, writer_lock=lease)
                store = ExecutionCheckpointStore(root, execution_sha256=execution, lease=lease)
                self.assertEqual(store.load(execution, heartbeat=lambda: None), [])
                with self.assertRaises(ExactOperationManifestError):
                    store.load("sha256:" + "b" * 64, heartbeat=lambda: None)
                with self.assertRaises(ExactOperationManifestError):
                    ExecutionCheckpointStore(root, execution_sha256="sha256:" + "b" * 64, lease=lease)
            with self.assertRaises(ExactOperationManifestError):
                store.load(execution, heartbeat=lambda: None)
