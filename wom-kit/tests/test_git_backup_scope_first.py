"""Synthetic Git repositories only: select owned paths before body limits."""
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_letter139_git_backup_plan as plan_fixtures
import test_v0420_work_session_git_workflow as workflow_fixtures
from wom_kit import git_backup_plan as planner
from wom_kit import git_backup_writer as writer
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_git_workflow as workflow


class ScopeFirstPlanTests(unittest.TestCase):
    def test_11132_unrelated_changes_and_large_file_are_not_body_inspected(self):
        fixture = plan_fixtures.Letter139GitBackupPlanTests()
        with tempfile.TemporaryDirectory() as temp:
            root = fixture.create_repository(Path(temp))
            owned = root / "owned.txt"
            owned.write_bytes(b"authenticated output\n")
            outside = root / "unrelated"
            outside.mkdir()
            for ordinal in range(11131):
                (outside / f"file-{ordinal:05d}.txt").write_bytes(b"x")
            large = outside / "large.bin"
            with large.open("wb") as stream:
                stream.truncate(planner.GIT_BACKUP_PLAN_MAX_FILE_BYTES + 1)
            observed = []
            original = planner._observe_changed_files
            def observe(root, records, **kwargs):
                observed.extend(row.path for row in records)
                return original(root, records, **kwargs)
            with ExitStack() as stack:
                for item in fixture.plan_patches(root):
                    stack.enter_context(item)
                stack.enter_context(patch.object(planner, "_observe_changed_files", side_effect=observe))
                plan = planner.git_backup_plan(root, _inspection_paths=("owned.txt",), max_changes=1)
            self.assertTrue(plan["ok"], plan["blockers"])
            self.assertEqual(set(observed), {"owned.txt"})
            self.assertEqual(plan["change_summary"]["count"], 1)
            self.assertEqual(plan["inspection_scope"]["uninspected_change_count"], 11132)
            self.assertFalse(plan["inspection_scope"]["uninspected_contents_read"])
            self.assertNotIn("owned.txt", json.dumps(plan))
            self.assertEqual(large.stat().st_size, planner.GIT_BACKUP_PLAN_MAX_FILE_BYTES + 1)

    def test_owned_oversized_file_still_blocks_and_legacy_plan_still_checks_all(self):
        fixture = plan_fixtures.Letter139GitBackupPlanTests()
        with tempfile.TemporaryDirectory() as temp:
            root = fixture.create_repository(Path(temp))
            with (root / "owned.bin").open("wb") as stream:
                stream.truncate(planner.GIT_BACKUP_PLAN_MAX_FILE_BYTES + 1)
            with ExitStack() as stack:
                for item in fixture.plan_patches(root):
                    stack.enter_context(item)
                scoped = planner.git_backup_plan(root, _inspection_paths=("owned.bin",))
                legacy = planner.git_backup_plan(root)
            for result in (scoped, legacy):
                self.assertFalse(result["ok"])
                self.assertIn("changed_file_size_limit_exceeded", result["blockers"])
                # Letter 176: a blocked plan never reads as "no changes", and the
                # blocking item is classified by role and size only.
                self.assertIsNone(result["change_summary"]["count"])
                self.assertEqual(result["change_summary"]["state"], "not_observed")
                observation = result["change_observation"]
                self.assertEqual(observation["state"], "stopped")
                self.assertEqual(observation["blocking_role"], "archive_root_file")
                self.assertEqual(observation["blocking_size_bucket"], "up_to_4x_file_limit")
                self.assertEqual(observation["file_limit_bytes"], planner.GIT_BACKUP_PLAN_MAX_FILE_BYTES)
                self.assertNotIn("owned.bin", json.dumps(result))


class ScopeFirstWorkflowTests(unittest.TestCase):
    def test_real_approved_writer_and_resume_ignore_unrelated_large_body(self):
        fixture = workflow_fixtures.SessionGitWorkflowTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        root = fixture.root
        large = root / "unrelated-large.bin"
        with large.open("wb") as stream:
            stream.truncate(planner.GIT_BACKUP_PLAN_MAX_FILE_BYTES + 1)
        touched = []
        original = planner._hash_stable_plain_file
        def hashed(root, path, **kwargs):
            touched.append(path)
            return original(root, path, **kwargs)
        with patch.object(planner, "_hash_stable_plain_file", side_effect=hashed):
            with exact.ExactOperationWriterLock(root) as held:
                preview = workflow._preview_session_git_backup_held(
                    root, held=held, client_app_ref=fixture.app, task_route_ref=fixture.route,
                    work_session_ref=fixture.session, key_provider=fixture.key)
                self.assertEqual(preview["selected_receipt_count"], 1)
                self.assertGreaterEqual(preview["uninspected_change_count"], 1)
                result = fixture.execute(held)
                self.assertTrue(result["original_commit_verified"])
                with patch.object(planner, "git_backup_plan", side_effect=AssertionError("replanned")), \
                     patch.object(writer, "_run_git_backup_exact_operation", side_effect=AssertionError("rewritten")):
                    resumed = fixture.resume(held)
                self.assertTrue(resumed["original_operation_already_completed"])
        self.assertNotIn(large, touched)
        self.assertIn("unrelated-large.bin", fixture.git("status", "--porcelain").stdout)


if __name__ == "__main__":
    unittest.main()
