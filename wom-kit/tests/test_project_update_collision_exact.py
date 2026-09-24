"""2026-09-24 reopen (58-writer triage, group 6): update collision relocation.

Letter 129 hit update collisions. `project-version-update-collision
--action preserve-relocate --approve` moves one reviewed collision aside
(never deletes it) so the update can run again. The approval is recorded in
the project's archive and bound to the failed update's materialization plan
digest, the entry ref and the action. The fixture's sealed test seam runs the
real claim path without a window. Windows-only, like the relocation engine.
"""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wom_kit import archive_cli, archive_services, command_status, work_session_permission
from wom_kit import exact_human_approval_windows as windows

import test_cli as _test_cli

REVIEWER = "human:synthetic-collision-reviewer"


@unittest.skipUnless(os.name == "nt", "Windows preserve-relocate contract")
class ProjectUpdateCollisionExactTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture_case = _test_cli.ArchiveCliTests("runTest")
        self.fixture_case.setUp()
        self.addCleanup(self.fixture_case.doCleanups)
        # The fixture project pins a different runtime than this checkout;
        # the CLI's runtime pin guard is not what these tests exercise.
        guard = patch.object(
            archive_cli.project_runtime, "project_write_guard", return_value={"blocked": False},
        )
        guard.start()
        self.addCleanup(guard.stop)
        temporary = tempfile.TemporaryDirectory(prefix="wom-group6-collision-")
        self.addCleanup(temporary.cleanup)
        fixture = self.fixture_case.create_project_version_update_fixture(
            Path(temporary.name), ignored_checkout_collision=True,
        )
        self.fixture = fixture
        self.collision = fixture["mirror"] / fixture["collision_name"]
        self.private_bytes = b"PRIVATE COLLISION BYTES MUST BE PRESERVED\n"
        self.collision.write_bytes(self.private_bytes)
        failed = archive_services._wom_kit_project_version_update_legacy_core(
            fixture["project_root"], target=fixture["target_tag"], approve=True,
            reviewed_by="human:letter-127-test", affirm_external_writers_quiescent=True,
        )
        self.assertEqual(failed["status"], "blocked")
        preflight = failed["materialization_preflight"]
        self.entry_ref = preflight["conflicts"][0]["entry_ref"]
        self.plan_sha256 = preflight["materialization_plan_sha256"]

    def run_cli(self, *extra: str) -> tuple[int, dict]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = archive_cli.main([
                "project-version-update-collision", str(self.fixture["project_root"]),
                "--target", self.fixture["target_tag"], "--entry-ref", self.entry_ref,
                "--action", "preserve-relocate", "--expected-plan-sha256", self.plan_sha256,
                "--reviewed-by", REVIEWER, *extra, "--format", "json",
            ])
        return code, json.loads(out.getvalue())

    def test_preserve_relocate_moves_the_collision_aside_after_approval(self) -> None:
        code, error = self.run_cli("--approve")
        self.assertEqual(error["reason_codes"], ["project_version_update_collision_quiescence_required"])
        self.assertTrue(self.collision.exists())

        def decline(*_args, **_kwargs):
            raise archive_cli.ExactHumanApprovalWorkflowError("exact_human_approval_cancelled")

        with patch.object(archive_cli, "_execute_exact_human_approved_write", side_effect=decline):
            code, error = self.run_cli("--approve", "--affirm-external-writers-quiescent")
        self.assertEqual(code, 1)
        self.assertEqual(error["reason_codes"], ["project_version_update_collision_workflow_precondition_failed"])
        self.assertEqual(self.collision.read_bytes(), self.private_bytes)

        code, result = self.run_cli("--approve", "--affirm-external-writers-quiescent")
        self.assertEqual(code, 0, result)
        self.assertFalse(self.collision.exists())
        self.assertNotIn(str(self.fixture["collision_name"]), json.dumps(result))

    def test_the_service_stays_blocked_without_a_claim(self) -> None:
        result = archive_services.wom_kit_project_version_update_collision(
            self.fixture["project_root"], target=self.fixture["target_tag"], entry_ref=self.entry_ref,
            action="preserve-relocate", approve=True, expected_plan_sha256=self.plan_sha256,
            reviewed_by=REVIEWER, affirm_external_writers_quiescent=True,
        )
        self.assertEqual(result["blockers"], [command_status.COMPOUND_APPROVAL_REASON_CODE])
        self.assertTrue(self.collision.exists())


class ProjectUpdateCollisionInventoryTests(unittest.TestCase):
    def test_inventory_is_open_and_grantable(self) -> None:
        name = "project-version-update-collision"
        self.assertNotIn(name, command_status.COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS)
        self.assertIn(name, command_status.EXACT_APPROVAL_REOPENED_WRITERS)
        self.assertIn(windows.ExactHumanApprovalOperation.project_version_update_collision,
                      work_session_permission.GRANTABLE_OPERATIONS)


if __name__ == "__main__":
    unittest.main()
