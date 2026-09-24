"""2026-09-24 reopen (58-writer triage, group 5a): restore drill, .gitignore
repair and archive identity reconcile under exact approval.

A closed restore drill left `preflight --require-restore-drill` unsatisfiable;
repair-gitignore and identity-reconcile were used successfully before v0.4.0.
Synthetic archive only; the native dialog and archive key are injected.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wom_kit import archive_services, command_status
from wom_kit import exact_human_approval_windows as windows
from wom_kit import work_session_permission

import test_v0421_lifecycle_batches_exact_approval as lifecycle

REVIEWER = lifecycle.REVIEWER


class Group5ExactTests(unittest.TestCase):
    setUp = lifecycle.LifecycleBatchesExactApprovalTests.setUp
    make_batch_ready_draft = lifecycle.LifecycleBatchesExactApprovalTests.make_batch_ready_draft
    run_cli = lifecycle.LifecycleBatchesExactApprovalTests.run_cli

    def test_restore_drill_runs_under_one_dialog(self) -> None:
        target = self.tmp / "restore-drill-target"
        code, dry = self.run_cli("restore-drill", str(self.root), "--target", str(target), "--dry-run")
        self.assertEqual(code, 0, dry)
        self.assertFalse(target.exists())
        code, result = self.run_cli("restore-drill", str(self.root), "--target", str(target),
                                    "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(self.native.calls, 1)
        self.assertTrue(target.is_dir(), result)
        self.assertTrue((self.root / result["receipt_path"]).is_file(), result)
        receipt = json.loads((self.root / result["receipt_path"]).read_text(encoding="utf-8"))
        self.assertEqual(receipt["reviewed_by"], REVIEWER)

    def test_gitignore_repair_adds_only_missing_patterns(self) -> None:
        gitignore = self.root / ".gitignore"
        original = gitignore.read_text(encoding="utf-8")
        code, result = self.run_cli("repair-gitignore", str(self.root), "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["write_status"], "nothing_to_write")
        self.assertEqual(self.native.calls, 0)
        gitignore.write_text(original.replace("secrets/\n", ""), encoding="utf-8")
        code, result = self.run_cli("repair-gitignore", str(self.root), "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, result)
        self.assertEqual(self.native.calls, 1)
        self.assertIn("secrets/", gitignore.read_text(encoding="utf-8").splitlines())

    def test_identity_reconcile_refuses_before_any_dialog(self) -> None:
        code, error = self.run_cli("identity-reconcile", str(self.root), "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1)
        self.assertEqual(error["reason_codes"], ["archive_identity_reconcile_review_affirmation_required"])
        code, error = self.run_cli("identity-reconcile", str(self.root), "--approve", "--reviewed-by", REVIEWER,
                                   "--affirm-principal-metadata-reviewed")
        self.assertEqual(code, 1)
        self.assertEqual(error["reason_codes"], ["archive_identity_reconcile_preflight_blocked"])
        self.assertEqual(self.native.calls, 0)
        blocked = archive_services.reconcile_archive_identity(
            self.root, reviewed_by=REVIEWER, expected_archive_sha256="0" * 64,
            expected_identity_sha256="0" * 64, expected_proposed_identity_sha256="0" * 64,
            affirm_principal_metadata_reviewed=True,
        )
        self.assertEqual(blocked["blockers"], [command_status.COMPOUND_APPROVAL_REASON_CODE])

    def test_inventory_is_open_and_grantable(self) -> None:
        for name, operation in (("restore-drill", "restore_drill"), ("repair-gitignore", "repair_gitignore"),
                                ("identity-reconcile", "archive_identity_reconcile")):
            self.assertNotIn(name, command_status.COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS)
            self.assertIn(name, command_status.EXACT_APPROVAL_REOPENED_WRITERS)
            self.assertIn(windows.ExactHumanApprovalOperation(operation), work_session_permission.GRANTABLE_OPERATIONS)


if __name__ == "__main__":
    unittest.main()
