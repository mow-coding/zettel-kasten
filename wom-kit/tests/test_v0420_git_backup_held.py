"""The existing exact Git writer composes under one caller-owned archive lock."""

from __future__ import annotations

import inspect
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import test_git_backup_writer as fixtures
import test_v0420_git_selection as selection_fixtures
from wom_kit import exact_operation_manifest as exact
from wom_kit import git_backup_writer as writer
from wom_kit.exact_human_approval_workflow import ExactHumanApprovalWorkflowError


class HeldGitBackupPrivacyTests(unittest.TestCase):
    def test_lock_observation_failures_do_not_retain_private_exception_chains(self):
        private = OSError("SYNTHETIC_PRIVATE_LOCK_PATH")
        nested = exact.ExactOperationManifestError("exact_operation_writer_lock_invalid")
        nested.__context__ = private
        nested.__cause__ = private
        prepared = SimpleNamespace(root=Path("SYNTHETIC_PRIVATE_ARCHIVE"))
        held = object.__new__(exact.ExactOperationWriterLock)
        held.archive_root = prepared.root
        for label, verify_error, samefile_error, samefile in (
            ("verify_os", private, None, True),
            ("verify_nested", nested, None, True),
            ("samefile_os", None, private, True),
            ("foreign_root", None, None, False),
        ):
            with self.subTest(boundary=label), patch.object(
                held, "verify_held", side_effect=verify_error,
            ), patch.object(
                writer.os.path, "samefile", side_effect=samefile_error, return_value=samefile,
            ):
                with self.assertRaises(writer.GitBackupWriterError) as caught:
                    writer._require_git_backup_held_lock(prepared, held)
            self.assertEqual(caught.exception.code, "git_backup_git_state_drifted")
            self.assertIsNone(caught.exception.__context__)
            self.assertIsNone(caught.exception.__cause__)
            self.assertNotIn("SYNTHETIC_PRIVATE", str(caught.exception))
            self.assertNotIn("SYNTHETIC_PRIVATE", repr(caught.exception))


class HeldGitBackupTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.GitBackupWriterTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.root = self.fixture.root

    def execute(self, prepared, held, *, native=None):
        with self.fixture.patches()[2], self.fixture.patches()[3]:
            return writer._execute_git_backup_held(
                prepared, held=held,
                selection_manifest_path=self.fixture.selection_path,
                reviewer_claim="person:local-operator",
                native=native or fixtures._Native(),
                key_provider=fixtures._KeyProvider(),
            )

    def assert_second_session_blocked(self):
        with self.assertRaises(exact.ExactOperationManifestError) as caught:
            with exact.ExactOperationWriterLock(self.root, timeout_seconds=0):
                self.fail("A second session acquired the caller's archive lock")
        self.assertEqual(caught.exception.code, "exact_operation_writer_busy")

    def assert_git_unchanged(self):
        self.assertEqual(
            self.fixture.git(self.root, "rev-parse", "HEAD").stdout.strip(),
            self.fixture.initial_head,
        )
        self.assertEqual(self.fixture.assert_remote_matches_head(), self.fixture.initial_head)
        self.assertFalse(self.fixture.transport_commands)

    def test_real_git_write_reuses_same_lock_and_blocks_another_session_until_caller_releases(self):
        prepared = self.fixture.plan_and_prepare()
        before_bundle = writer._canonical(writer._bundle_document(prepared))
        before_manifest = prepared.manifest.document()
        applied_locks = []
        original_apply = writer._apply_prepared_with_claim

        with exact.ExactOperationWriterLock(self.root) as held:
            self.assert_second_session_blocked()

            def native_review():
                held.verify_held()
                self.assert_second_session_blocked()

            def apply_with_original_lock(*args, **kwargs):
                self.assertIs(kwargs["writer_lock"], held)
                held.verify_held()
                self.assert_second_session_blocked()
                applied_locks.append(kwargs["writer_lock"])
                return original_apply(*args, **kwargs)

            native = fixtures._Native(native_review)
            with patch.object(
                writer, "exact_operation_writer_lock",
                side_effect=AssertionError("The held route must not enter a nested lock"),
            ), patch.object(writer, "_apply_prepared_with_claim", side_effect=apply_with_original_lock):
                result = self.execute(prepared, held, native=native)
            held.verify_held()
            self.assert_second_session_blocked()
            self.assertEqual(applied_locks, [held])
            self.assertTrue(result["ok"])
            self.assertEqual(native.calls, 1)
            self.assertTrue(result["remote_ref_independently_requeried"])
            terminal = self.fixture.assert_remote_matches_head()
            self.assertNotEqual(terminal, self.fixture.initial_head)

        with exact.ExactOperationWriterLock(self.root, timeout_seconds=0) as next_session:
            next_session.verify_held()
        self.assertEqual(prepared.manifest.document(), before_manifest)
        loaded = writer.load_private_git_backup_bundle(
            self.root, manifest_sha256=prepared.manifest.manifest_sha256,
        )
        self.assertEqual(writer._canonical(writer._bundle_document(loaded)), before_bundle)
        self.assertEqual(len(self.fixture.transport_commands), 1)
        self.assertNotIn("--force", self.fixture.transport_commands[0])
        self.assertNotIn("--force-with-lease", self.fixture.transport_commands[0])
        self.assertNotIn("work_session_binding", result)
        self.assertNotIn("_execute_git_backup_held", writer.__all__)

    def test_missing_unheld_released_and_other_archive_locks_fail_before_native_or_claim(self):
        prepared = self.fixture.plan_and_prepare()
        with exact.ExactOperationWriterLock(self.root) as released:
            released.verify_held()
        with tempfile.TemporaryDirectory(prefix="wom-git-held-foreign-") as temporary:
            foreign = Path(temporary)
            with exact.ExactOperationWriterLock(foreign) as foreign_held:
                candidates = (None, object(), exact.ExactOperationWriterLock(self.root), released, foreign_held)
                for candidate in candidates:
                    with self.subTest(lock_type=type(candidate).__name__):
                        native = fixtures._Native()
                        key = fixtures._KeyProvider()
                        with patch.object(
                            writer, "exact_operation_writer_lock",
                            side_effect=AssertionError("Invalid held locks cannot acquire a replacement"),
                        ), patch.object(
                            writer, "_apply_prepared_with_claim",
                            side_effect=AssertionError("Invalid held lock reached the Git writer"),
                        ):
                            with self.assertRaises(writer.GitBackupWriterError) as caught:
                                writer._execute_git_backup_held(
                                    prepared, held=candidate,
                                    selection_manifest_path=self.fixture.selection_path,
                                    reviewer_claim="person:local-operator",
                                    native=native, key_provider=key,
                                )
                        self.assertEqual(caught.exception.code, "git_backup_git_state_drifted")
                        self.assertEqual(native.calls, 0)
                        self.assertEqual(key.create_if_missing, [])
                        foreign_held.verify_held()
        self.assert_git_unchanged()
        self.assertFalse((self.root / "profiles/local/exact-human-approvals").exists())
        self.assertFalse((self.root / "receipts").exists())

    def test_lock_released_during_native_review_is_not_replaced_or_used_for_claims(self):
        prepared = self.fixture.plan_and_prepare()
        held = exact.ExactOperationWriterLock(self.root)
        held.__enter__()
        native = fixtures._Native(lambda: held.__exit__(None, None, None))
        key = fixtures._KeyProvider()
        try:
            with patch.object(
                writer, "exact_operation_writer_lock",
                side_effect=AssertionError("Released caller lock cannot be reacquired"),
            ), patch.object(
                writer, "_apply_prepared_with_claim",
                side_effect=AssertionError("Released caller lock reached Git"),
            ):
                with self.assertRaises(ExactHumanApprovalWorkflowError):
                    writer._execute_git_backup_held(
                        prepared, held=held,
                        selection_manifest_path=self.fixture.selection_path,
                        reviewer_claim="person:local-operator", native=native, key_provider=key,
                    )
        finally:
            held.__exit__(None, None, None)
        self.assertEqual(native.calls, 1)
        self.assertEqual(key.create_if_missing, [])
        self.assert_git_unchanged()
        self.assertFalse((self.root / "profiles/local/exact-human-approvals").exists())
        with exact.ExactOperationWriterLock(self.root, timeout_seconds=0) as next_session:
            next_session.verify_held()

    def test_selection_drift_is_rejected_without_git_writes_or_releasing_caller_lock(self):
        prepared = self.fixture.plan_and_prepare()

        def selection_drift():
            self.fixture.selection_path.write_text("{}\n", encoding="utf-8")

        native = fixtures._Native(selection_drift)
        with exact.ExactOperationWriterLock(self.root) as held, patch.object(
            writer, "exact_operation_writer_lock",
            side_effect=AssertionError("The held route must not enter a nested lock"),
        ), patch.object(writer, "_apply_prepared_with_claim") as apply:
            with self.assertRaises(ExactHumanApprovalWorkflowError) as caught:
                self.execute(prepared, held, native=native)
            self.assertEqual(caught.exception.code, "exact_human_approval_state_unknown")
            apply.assert_not_called()
            held.verify_held()
            self.assert_second_session_blocked()
        self.assertEqual(native.calls, 1)
        self.assert_git_unchanged()

    def test_prepared_nested_drift_during_review_still_fails_before_claim_publication(self):
        prepared = self.fixture.plan_and_prepare()

        def prepared_drift():
            observation = prepared.groups[0].private_changes[0]["public_observation"]
            observation["worktree"]["sha256"] = "sha256:" + "f" * 64

        native = fixtures._Native(prepared_drift)
        with exact.ExactOperationWriterLock(self.root) as held, patch.object(
            writer, "exact_operation_writer_lock",
            side_effect=AssertionError("The held route must not enter a nested lock"),
        ):
            with self.assertRaises(ExactHumanApprovalWorkflowError):
                self.execute(prepared, held, native=native)
            held.verify_held()
        self.assertEqual(native.calls, 1)
        self.assert_git_unchanged()
        self.assertFalse((self.root / "profiles/local/exact-human-approvals").exists())

    def test_original_public_executor_keeps_native_before_default_lock(self):
        prepared = self.fixture.plan_and_prepare()
        events = []
        original_factory = writer.exact_operation_writer_lock

        def native_review():
            events.append("native")
            with exact.ExactOperationWriterLock(self.root, timeout_seconds=0) as observer:
                observer.verify_held()

        def acquire_after_native(*args, **kwargs):
            self.assertEqual(events, ["native"])
            events.append("post_decision_lock")
            return original_factory(*args, **kwargs)

        with self.fixture.patches()[2], self.fixture.patches()[3], patch.object(
            writer, "exact_operation_writer_lock", side_effect=acquire_after_native,
        ):
            result = writer.execute_git_backup(
                prepared, selection_manifest_path=self.fixture.selection_path,
                reviewer_claim="person:local-operator", native=fixtures._Native(native_review),
                key_provider=fixtures._KeyProvider(),
            )
        self.assertTrue(result["ok"])
        self.assertEqual(events, ["native", "post_decision_lock"])
        self.assertEqual(
            tuple(inspect.signature(writer.execute_git_backup).parameters),
            ("prepared", "selection_manifest_path", "reviewer_claim", "progress_hook", "native", "key_provider"),
        )
        self.fixture.assert_remote_matches_head()
        with exact.ExactOperationWriterLock(self.root, timeout_seconds=0) as next_session:
            next_session.verify_held()

    def test_held_v2_preserves_excluded_index_bytes_and_original_binding(self):
        v2 = selection_fixtures.GitSelectionV2RealTests(methodName="runTest")
        v2.fixture, v2.root, v2.git = self.fixture, self.root, self.fixture.git
        self.fixture.git(self.root, "add", "--", "new-private.txt")
        (self.root / "new-private.txt").write_bytes(b"other session unstaged bytes\n")
        binding = selection_fixtures.archive_binding(revision=7)
        prepared = v2.prepare(work_session_binding=binding)
        before_excluded = v2.excluded_snapshot(prepared)
        before_bundle = writer._canonical(writer._bundle_document(prepared))
        with exact.ExactOperationWriterLock(self.root) as held, patch.object(
            writer, "exact_operation_writer_lock",
            side_effect=AssertionError("The held route must not enter a nested lock"),
        ):
            result = self.execute(prepared, held)
            held.verify_held()
        self.assertTrue(result["ok"])
        self.assertEqual(result["work_session_binding"], binding.document())
        self.assertEqual(result["selected_change_count"], 1)
        self.assertEqual(result["excluded_change_count"], 1)
        self.assertEqual(v2.excluded_snapshot(prepared), before_excluded)
        terminal = self.fixture.assert_remote_matches_head()
        committed = self.fixture.git(
            self.root, "diff", "--name-only", self.fixture.initial_head, terminal,
        ).stdout.splitlines()
        self.assertEqual(committed, ["tracked.txt"])
        loaded = writer.load_private_git_backup_bundle(
            self.root, manifest_sha256=prepared.manifest.manifest_sha256,
        )
        self.assertEqual(writer._canonical(writer._bundle_document(loaded)), before_bundle)
        receipts = list((self.root / "receipts/ops/git-backups").glob("*.json"))
        self.assertEqual(len(receipts), 1)
        receipt = json.loads(receipts[0].read_text(encoding="ascii"))
        self.assertEqual(receipt["work_session_binding"], binding.document())
        self.assertTrue(receipt["exact_remote_ref_requeried"])
        self.assertFalse(receipt["force_push_used"])


if __name__ == "__main__":
    unittest.main()
