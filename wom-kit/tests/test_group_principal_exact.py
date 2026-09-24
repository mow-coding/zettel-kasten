"""2026-09-24 reopen (58-writer triage, group 4): third-party Principals and
activity-group memberships under exact approval.

Letters 102/104/112 asked for event groups and non-owner Principals; both were
implemented and never usable. Synthetic archives only; the native dialog and
archive key are injected so no real window opens.
"""
from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wom_kit import archive_cli, archive_services, command_status, completion_workflows
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import work_session_permission

import test_activity_group_membership_removal_write as removal
import test_v0421_lifecycle_batches_exact_approval as lifecycle

REVIEWER = "person:synthetic-group-reviewer"
NAMES = (
    "principal-register", "principal-unregister", "activity-group-membership-write",
    "activity-group-membership-removal-write", "activity-group-membership-recover",
    "activity-group-membership-removal-recover",
)


class GroupAndPrincipalExactTests(unittest.TestCase):
    _init_archive = removal.ActivityGroupMembershipRemovalWriteTests._init_archive
    _create_canonical = removal.ActivityGroupMembershipRemovalWriteTests._create_canonical
    _fixture = removal.ActivityGroupMembershipRemovalWriteTests._fixture

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-group4-")
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.native = lifecycle._PagedNative()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
        stack.enter_context(patch.object(broker, "_production_key_provider", return_value=lifecycle._KeyProvider()))

    def run_cli(self, *args: str) -> tuple[int, dict]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = archive_cli.main([*args, "--format", "json"])
        self.assertEqual(err.getvalue(), "")
        return code, json.loads(out.getvalue())

    def test_membership_removal_writes_under_one_dialog(self) -> None:
        fixture = self._fixture(self.tmp / "archive", suffix="g4", mode="one_ready")
        root, plan = fixture["root"], fixture["plan"]
        member = fixture["member_paths"][0]
        before = member.read_bytes()
        base = ["activity-group-membership-removal-write", str(root), "--request", fixture["request_relative"],
                "--expected-request-sha256", plan["request"]["sha256"],
                "--expected-review-plan-sha256", plan["review_plan_sha256"]]
        code, error = self.run_cli(*base, "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(error["reason_codes"], ["activity_group_membership_removal_write_review_affirmation_required"])
        self.assertEqual(self.native.calls, 0)
        code, result = self.run_cli(*base, "--approve", "--reviewed-by", REVIEWER, "--affirm-removals-reviewed")
        self.assertEqual(code, 0, result)
        self.assertEqual(self.native.calls, 1)
        self.assertNotEqual(member.read_bytes(), before)
        self.assertNotIn(fixture["anchor_id"], member.read_text(encoding="utf-8"))

    def test_a_wrong_digest_is_refused_before_the_dialog(self) -> None:
        fixture = self._fixture(self.tmp / "archive", suffix="g5", mode="one_ready")
        root, plan = fixture["root"], fixture["plan"]
        code, error = self.run_cli(
            "activity-group-membership-removal-write", str(root), "--request", fixture["request_relative"],
            "--expected-request-sha256", plan["request"]["sha256"],
            "--expected-review-plan-sha256", "sha256:" + "0" * 64,
            "--approve", "--reviewed-by", REVIEWER, "--affirm-removals-reviewed")
        self.assertEqual(code, 1)
        self.assertEqual(error["reason_codes"], ["activity_group_membership_removal_write_preflight_blocked"])
        self.assertEqual(self.native.calls, 0)
        blocked = archive_services.activity_group_membership_removal_write(
            root, request_path=fixture["request_relative"],
            expected_request_sha256=plan["request"]["sha256"],
            expected_review_plan_sha256=plan["review_plan_sha256"],
            approve=True, reviewed_by=REVIEWER, affirm_removals_reviewed=True,
        )
        self.assertEqual(blocked["blockers"], [command_status.COMPOUND_APPROVAL_REASON_CODE])

    def test_principal_register_and_unregister(self) -> None:
        root = self.tmp / "archive"
        import shutil
        shutil.copytree(lifecycle.KIT_ROOT / "examples" / "fake-life-archive", root)
        fields = ["--principal-id", "team:synthetic-lab", "--kind", "team", "--display-name", "Synthetic Lab"]
        plan = completion_workflows.principal_registration_plan(
            root, principal_id="team:synthetic-lab", kind="team", display_name="Synthetic Lab")
        self.assertTrue(plan["ok"], plan)
        digest = plan.get("plan_sha256") or plan["summary"]["plan_sha256"]
        code, result = self.run_cli("principal-register", str(root), *fields, "--expected-plan-sha256", digest,
                                    "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, result)
        self.assertEqual(self.native.calls, 1)
        receipts = sorted((root / "receipts").rglob("*.json"))
        approved = [json.loads(path.read_text(encoding="utf-8")) for path in receipts]
        self.assertTrue(any((row.get("exact_human_approval") or {}).get("operation") == "principal_register"
                            for row in approved))
        unplan = completion_workflows.principal_unregistration_plan(root, principal_id="team:synthetic-lab")
        self.assertTrue(unplan["ok"], unplan)
        code, result = self.run_cli("principal-unregister", str(root), "--principal-id", "team:synthetic-lab",
                                    "--expected-plan-sha256", unplan.get("plan_sha256") or unplan["summary"]["plan_sha256"],
                                    "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, result)
        self.assertEqual(self.native.calls, 2)

    def test_inventory_is_open_and_grantable(self) -> None:
        for name in NAMES:
            self.assertNotIn(name, command_status.COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS)
            self.assertIn(name, command_status.EXACT_APPROVAL_REOPENED_WRITERS)
            operation = windows.ExactHumanApprovalOperation(name.replace("-", "_"))
            self.assertIn(operation, work_session_permission.GRANTABLE_OPERATIONS)


if __name__ == "__main__":
    unittest.main()
