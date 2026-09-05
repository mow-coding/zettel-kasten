"""Actual archive locks, cancellation and process-death recovery; no TTL theft."""

import errno
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_wait as waiting


class WorkSessionWaitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wom-session-wait-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "archive"
        self.root.mkdir()

    def test_pre_cancel_does_not_create_control_files(self):
        with self.assertRaisesRegex(waiting.WorkSessionWaitError, "work_session_wait_cancelled"):
            with waiting.wait_for_archive_writer(self.root, cancel_requested=lambda: True, progress=lambda row: None):
                self.fail("cancelled waiter entered")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_wait_cancel_preserves_actual_holder_and_other_reads(self):
        events = []
        cancel = threading.Event()
        with exact.ExactOperationWriterLock(self.root) as owner:
            timer = threading.Timer(0.25, cancel.set)
            timer.start()
            self.addCleanup(timer.join)
            started = time.monotonic()
            with self.assertRaisesRegex(waiting.WorkSessionWaitError, "work_session_wait_cancelled"):
                with waiting.wait_for_archive_writer(self.root, cancel_requested=cancel.is_set, progress=events.append):
                    self.fail("second writer entered")
            self.assertLess(time.monotonic() - started, 2)
            owner.verify_held()
            self.assertEqual(events[0]["stage"], "waiting_for_writer")
            self.assertTrue(list(self.root.iterdir()))  # Ordinary metadata reads remain available.
            with self.assertRaisesRegex(exact.ExactOperationManifestError, "exact_operation_writer_busy"):
                with exact.ExactOperationWriterLock(self.root, timeout_seconds=0):
                    self.fail("waiter stole owner lock")

    def test_actual_release_revalidates_before_caller_runs(self):
        acquired = threading.Event()
        release = threading.Event()
        errors = []

        def owner():
            try:
                with exact.ExactOperationWriterLock(self.root):
                    acquired.set()
                    release.wait(5)
            except BaseException as error:
                errors.append(error)

        thread = threading.Thread(target=owner)
        thread.start()
        self.addCleanup(thread.join, 6)
        self.addCleanup(release.set)
        self.assertTrue(acquired.wait(3))
        timer = threading.Timer(0.25, release.set)
        timer.start()
        self.addCleanup(timer.join)
        events = []
        with waiting.wait_for_archive_writer(self.root, cancel_requested=lambda: False, progress=events.append) as held:
            held.verify_held()
            self.assertTrue(release.is_set())
            self.assertEqual(events[-1]["stage"], "writer_acquired_revalidation_required")
        thread.join(3)
        self.assertEqual(errors, [])

    def test_progress_failure_after_acquisition_releases_own_lock(self):
        def progress(row):
            if row["stage"] == "writer_acquired_revalidation_required":
                raise RuntimeError("synthetic display unavailable")

        with self.assertRaises(RuntimeError):
            with waiting.wait_for_archive_writer(self.root, cancel_requested=lambda: False, progress=progress):
                self.fail("failed callback entered")
        with exact.ExactOperationWriterLock(self.root, timeout_seconds=0) as held:
            held.verify_held()

    def test_cancel_from_acquired_progress_never_yields_and_releases_real_lock(self):
        cancelled = threading.Event()
        events = []

        def progress(row):
            events.append(dict(row))
            if row["stage"] == "writer_acquired_revalidation_required":
                cancelled.set()

        with self.assertRaisesRegex(waiting.WorkSessionWaitError, "^work_session_wait_cancelled$"):
            with waiting.wait_for_archive_writer(
                self.root, cancel_requested=cancelled.is_set, progress=progress,
            ):
                self.fail("cancelled acquired notification entered caller")
        self.assertTrue(cancelled.is_set())
        self.assertEqual(events[-1]["stage"], "writer_acquired_revalidation_required")
        path = self.root / exact.EXACT_OPERATION_LOCAL_ROOT / ".writer.lock"
        before = os.lstat(path)
        with exact.ExactOperationWriterLock(self.root, timeout_seconds=0) as held:
            held.verify_held()
            after = os.lstat(path)
            self.assertEqual((before.st_dev, before.st_ino), (after.st_dev, after.st_ino))

    def test_root_replacement_from_acquired_progress_never_yields(self):
        moved = self.root.parent / "private-displaced-root"
        replacement_succeeded = []

        def progress(row):
            if row["stage"] != "writer_acquired_revalidation_required":
                return
            try:
                self.root.rename(moved)
            except OSError:
                # Some Windows filesystems retain this ancestor while its
                # byte-lock is open. Such a host blocks the race itself.
                return
            self.root.mkdir()
            replacement_succeeded.append(True)

        try:
            with waiting.wait_for_archive_writer(
                self.root, cancel_requested=lambda: False, progress=progress,
            ) as held:
                self.assertFalse(replacement_succeeded, "replaced archive root entered caller")
                held.verify_held()
        except waiting.WorkSessionWaitError as error:
            self.assertEqual(str(error), "work_session_wait_root_changed")
            self.assertTrue(replacement_succeeded)
            self.assertEqual(list(self.root.iterdir()), [])
        else:
            self.assertFalse(replacement_succeeded)
        surviving_root = moved if replacement_succeeded else self.root
        with exact.ExactOperationWriterLock(surviving_root, timeout_seconds=0) as held:
            held.verify_held()

    def test_post_acquire_identity_probe_error_closes_real_descriptor(self):
        original = waiting._root_identity
        calls = []

        def fail_after_acquire(root):
            calls.append(root)
            if len(calls) == 3:
                raise waiting.WorkSessionWaitError("work_session_wait_root_changed")
            return original(root)

        with mock.patch.object(waiting, "_root_identity", side_effect=fail_after_acquire):
            with self.assertRaisesRegex(waiting.WorkSessionWaitError, "^work_session_wait_root_changed$"):
                with waiting.wait_for_archive_writer(
                    self.root, cancel_requested=lambda: False, progress=lambda row: None,
                ):
                    self.fail("unavailable post-acquire identity entered caller")
        self.assertEqual(len(calls), 3)
        with exact.ExactOperationWriterLock(self.root, timeout_seconds=0) as held:
            held.verify_held()

    def test_unavailable_lock_is_not_infinite_contention(self):
        lock = exact.ExactOperationWriterLock(self.root, timeout_seconds=0)
        with mock.patch.object(lock, "_try_os_lock", side_effect=OSError(errno.EBADF, "private synthetic error")):
            with self.assertRaisesRegex(exact.ExactOperationManifestError, "^exact_operation_writer_lock_invalid$"):
                lock.__enter__()
        self.assertIsNone(lock._handle)
        with mock.patch.object(exact.ExactOperationWriterLock, "_try_os_lock", side_effect=OSError(errno.EBADF, "private synthetic error")):
            with self.assertRaisesRegex(exact.ExactOperationManifestError, "^exact_operation_writer_lock_invalid$"):
                with waiting.wait_for_archive_writer(self.root, cancel_requested=lambda: False, progress=lambda row: None):
                    self.fail("unavailable lock entered")

    def test_busy_callback_failure_closes_attempt_descriptor(self):
        with exact.ExactOperationWriterLock(self.root) as owner:
            def broken_progress():
                raise RuntimeError("synthetic cancellation")
            attempt = exact.ExactOperationWriterLock(self.root, heartbeat=broken_progress)
            with self.assertRaises(RuntimeError):
                attempt.__enter__()
            self.assertIsNone(attempt._handle)
            owner.verify_held()

    def test_killed_process_releases_same_os_lock_without_removing_file(self):
        script = (
            "import sys\nfrom wom_kit.exact_operation_manifest import ExactOperationWriterLock\n"
            "with ExactOperationWriterLock(sys.argv[1]):\n"
            " print('held', flush=True)\n sys.stdin.read()\n"
        )
        process = subprocess.Popen(
            [sys.executable, "-c", script, str(self.root)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            signal = queue.Queue()
            reader = threading.Thread(target=lambda: signal.put(process.stdout.readline()), daemon=True)
            reader.start()
            self.assertEqual(signal.get(timeout=10).strip(), "held")
            path = self.root / exact.EXACT_OPERATION_LOCAL_ROOT / ".writer.lock"
            info = os.lstat(path)
            with self.assertRaisesRegex(exact.ExactOperationManifestError, "exact_operation_writer_busy"):
                with exact.ExactOperationWriterLock(self.root, timeout_seconds=0):
                    self.fail("other process lock acquired")
            process.kill()
            process.communicate(timeout=10)
            with waiting.wait_for_archive_writer(self.root, cancel_requested=lambda: False, progress=lambda row: None) as held:
                held.verify_held()
                after = os.lstat(path)
                self.assertEqual((after.st_dev, after.st_ino), (info.st_dev, info.st_ino))
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=10)

    def test_real_contention_reports_immediately_and_within_ten_seconds(self):
        release = threading.Event()
        acquired = threading.Event()

        def owner():
            with exact.ExactOperationWriterLock(self.root):
                acquired.set()
                release.wait(10)

        thread = threading.Thread(target=owner)
        thread.start()
        self.addCleanup(thread.join, 11)
        self.addCleanup(release.set)
        self.assertTrue(acquired.wait(3))
        timer = threading.Timer(5.3, release.set)
        timer.start()
        self.addCleanup(timer.join)
        observed = []
        started = time.monotonic()
        with waiting.wait_for_archive_writer(self.root, cancel_requested=lambda: False,
                                            progress=lambda row: observed.append((time.monotonic(), row))) as held:
            held.verify_held()
        self.assertGreaterEqual(len(observed), 3)
        self.assertLess(observed[0][0] - started, 2)
        self.assertLess(max(right[0] - left[0] for left, right in zip(observed, observed[1:])), 10)
        self.assertEqual({key for _, row in observed for key in row}, {"stage", "elapsed_seconds"})


if __name__ == "__main__":
    unittest.main()
