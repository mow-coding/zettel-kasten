"""A recovery must not reacquire or release the caller's exact OS lock."""

from pathlib import Path
import tempfile
import unittest
from unittest import mock

import test_local_recovery_execution as fixture
from wom_kit import local_recovery_execution as recovery
from wom_kit.exact_human_approval_workflow import _execute_exact_human_approved_write_core
from wom_kit.exact_operation_manifest import ExactOperationWriterLock


class LocalRecoveryHeldTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="wom-recovery-held-")
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        helper = fixture.LocalRecoveryExecutionTests()
        self.root = helper.archive(self.parent)
        self.plan = helper.title_plan(self.root)

    def test_approved_interruption_and_same_claim_resume_retain_caller_lock(self):
        native, keys = fixture._ApproveNative(), fixture._StableKeyProvider()
        context = recovery.local_recovery_context(self.plan, mode="apply")
        write = recovery._Writer.write_field

        def cut_after_field(writer, **kwargs):
            write(writer, **kwargs)
            raise RuntimeError("synthetic interruption after canonical write")

        with ExactOperationWriterLock(self.root) as held:
            with mock.patch.object(recovery, "exact_operation_writer_lock",
                                   side_effect=AssertionError("must use caller lock")):
                with mock.patch.object(recovery._Writer, "write_field", new=cut_after_field):
                    interrupted = _execute_exact_human_approved_write_core(
                        self.root, context,
                        lambda claim: recovery._execute_core(
                            self.plan, claim, context, mode="apply", resume=False,
                            progress_hook=None, writer_lock=held),
                        native=native, key_provider=keys,
                    )
                self.assertFalse(interrupted["ok"], interrupted)
                self.assertEqual(interrupted["applied_field_count"], 1)
                self.assertTrue(interrupted["resume_supported"])
                held.verify_held()
                loaded = recovery.load_local_recovery_plan(
                    self.root, manifest_sha256=self.plan.manifest.manifest_sha256)
                with mock.patch.object(recovery._Writer, "write_field",
                                       side_effect=AssertionError("field already written")):
                    resumed = recovery.resume_local_recovery(
                        loaded, key_provider=keys, _writer_lock=held)
                self.assertTrue(resumed["ok"], resumed)
                self.assertEqual(resumed["resumed_field_count"], 1)
                self.assertFalse(resumed["native_approval_redisplayed"])
                held.verify_held()
                self.assertTrue(recovery.verify_local_recovery_state(loaded, state="post")["all_match"])
        self.assertFalse(held.held)
        self.assertEqual(native.calls, 1)
        self.assertEqual(keys.create_if_missing, [True, False])

    def test_wrong_archive_lock_is_rejected_before_resume_key_or_control_write(self):
        helper = fixture.LocalRecoveryExecutionTests()
        other = helper.archive(self.parent / "other")
        recovery.persist_local_recovery_control(self.plan)
        loaded = recovery.load_local_recovery_plan(
            self.root, manifest_sha256=self.plan.manifest.manifest_sha256)
        keys = fixture._StableKeyProvider()
        before = {p.relative_to(self.root): p.read_bytes()
                  for p in self.root.rglob("*") if p.is_file()}
        with ExactOperationWriterLock(other) as wrong:
            with self.assertRaisesRegex(recovery.LocalRecoveryError, "^local_recovery_lock_required$") as caught:
                recovery.resume_local_recovery(loaded, key_provider=keys, _writer_lock=wrong)
            self.assertIsNone(caught.exception.__context__)
            self.assertIsNone(caught.exception.__cause__)
            wrong.verify_held()
        self.assertEqual(keys.create_if_missing, [])
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes()
                                  for p in self.root.rglob("*") if p.is_file()})

    def test_released_and_spoofed_locks_never_enter_the_recovery_boundary(self):
        with ExactOperationWriterLock(self.root) as released:
            pass
        spoofed = mock.Mock(held=True, archive_root=self.root)
        for candidate in (released, spoofed):
            with self.subTest(released=candidate is released):
                entered = False
                with self.assertRaisesRegex(recovery.LocalRecoveryError, "^local_recovery_lock_required$"):
                    with recovery._local_recovery_writer_lock(self.plan, candidate):
                        entered = True
                self.assertFalse(entered)
        spoofed.verify_held.assert_not_called()

    def test_identity_change_during_held_boundary_is_rejected_without_unlocking(self):
        archive_file = self.root / "archive.yml"
        original = archive_file.read_bytes()
        with ExactOperationWriterLock(self.root) as held:
            try:
                with self.assertRaisesRegex(recovery.LocalRecoveryError, "^local_recovery_lock_required$"):
                    with recovery._local_recovery_writer_lock(self.plan, held):
                        archive_file.write_text("archive_id: archive:personal:synthetic-replaced\n", encoding="utf-8")
                held.verify_held()
            finally:
                archive_file.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
