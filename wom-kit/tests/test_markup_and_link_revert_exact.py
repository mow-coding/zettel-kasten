"""2026-09-24 reopen (58-writer triage, group 3): markup normalization writers and
zettel-objet-link-revert under an exact approval bound to each plan digest.

Letters 115-117 applied 1,994 normalizations before v0.4.0 closed the writer;
136 used objet-link revert and 159 was blocked without it. Synthetic archive
only; the native dialog and archive key are injected.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wom_kit import command_status
from wom_kit import completion_workflows
from wom_kit import exact_human_approval_windows as windows
from wom_kit import work_session_permission

import test_v0421_lifecycle_batches_exact_approval as lifecycle

REVIEWER = lifecycle.REVIEWER
LINK_ZET = "zet_20240504_fake_lunch_thought"
OBJECT_ID = "sha256:9dabf9b965a3f789b1b36100f3f70515ce8dfd81b411b1503e1e2c3304303647"
MARKUP_ZET = "zet_20260924_markup_reopen"


class MarkupAndLinkRevertExactTests(unittest.TestCase):
    setUp = lifecycle.LifecycleBatchesExactApprovalTests.setUp
    make_batch_ready_draft = lifecycle.LifecycleBatchesExactApprovalTests.make_batch_ready_draft
    run_cli = lifecycle.LifecycleBatchesExactApprovalTests.run_cli

    def markup_zet(self) -> Path:
        path = self.root / "zettels" / f"{MARKUP_ZET}.md"
        path.write_text(
            "---\n"
            f"id: {MARKUP_ZET}\n"
            "title: Synthetic markup reopen\n"
            "status: canonical\n"
            "kind: note\n"
            "---\n"
            "Before\n"
            "<empty-block/>\n"
            "<div><span class=\"migration\">Visible text</span></div>\n",
            encoding="utf-8",
        )
        return path

    def test_markup_applies_and_reverts_under_one_dialog_each(self) -> None:
        target = self.markup_zet()
        before = target.read_bytes()
        code, plan = self.run_cli("markup-normalization-plan", str(self.root), "--dry-run")
        self.assertEqual(code, 0, plan)
        code, applied = self.run_cli("markup-normalization", str(self.root), "--approve", "--reviewed-by", REVIEWER,
                                     "--expected-plan-sha256", plan["summary"]["plan_sha256"])
        self.assertEqual(code, 0, applied)
        self.assertEqual(self.native.calls, 1)
        self.assertNotIn("<span", target.read_text(encoding="utf-8"))
        receipt_path = applied["summary"]["receipt_path"]
        receipt = json.loads((self.root / receipt_path).read_text(encoding="utf-8"))
        self.assertEqual(receipt["exact_human_approval"]["operation"], "markup_normalization")
        code, reverted = self.run_cli("markup-normalization-revert", str(self.root), "--receipt", receipt_path,
                                      "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, reverted)
        self.assertEqual(self.native.calls, 2)
        self.assertEqual(target.read_bytes(), before)
        revert_receipt = json.loads((self.root / reverted["summary"]["receipt_path"]).read_text(encoding="utf-8"))
        self.assertEqual(revert_receipt["exact_human_approval"]["operation"], "markup_normalization_revert")

    def test_stale_digest_nothing_to_do_and_unbound_calls_open_no_dialog(self) -> None:
        code, plan = self.run_cli("markup-normalization-plan", str(self.root), "--dry-run")
        code, result = self.run_cli("markup-normalization", str(self.root), "--approve", "--reviewed-by", REVIEWER,
                                    "--expected-plan-sha256", plan["summary"]["plan_sha256"])
        self.assertEqual(code, 0, result)  # an honest no-op: nothing ready, no dialog
        self.assertEqual(result["write_status"], "nothing_to_write")
        target = self.markup_zet()
        before = target.read_bytes()
        code, error = self.run_cli("markup-normalization", str(self.root), "--approve", "--reviewed-by", REVIEWER,
                                   "--expected-plan-sha256", "0" * 64)
        self.assertEqual(error["reason_codes"], ["markup_normalization_plan_changed"])
        code, error = self.run_cli("markup-normalization-recovery", str(self.root), "--journal",
                                   ".wom-scratch/markup-normalization/transactions/missing/journal.json",
                                   "--mode", "rollback", "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1, error)
        self.assertEqual(self.native.calls, 0)
        self.assertEqual(target.read_bytes(), before)
        plan = completion_workflows.markup_normalization_plan(self.root)
        blocked = completion_workflows.markup_normalization_apply(
            self.root, policy="normalize", max_items=1000, max_changes=1000,
            expected_plan_sha256=plan["summary"]["plan_sha256"], reviewed_by=REVIEWER,
        )
        self.assertFalse(blocked["ok"])
        self.assertEqual(target.read_bytes(), before)

    def test_objet_link_is_reverted_to_exact_bytes(self) -> None:
        zettel = self.root / "zettels" / f"{LINK_ZET}.md"
        before = zettel.read_bytes()
        common = ["zettel-objet-link", str(self.root), "--zettel-id", LINK_ZET, "--object-id", OBJECT_ID,
                  "--role", "evidence"]
        code, preview = self.run_cli(*common, "--dry-run")
        self.assertEqual(code, 0, preview)
        code, linked = self.run_cli(*common, "--approve", "--reviewed-by", REVIEWER,
                                    "--expected-plan-sha256", preview["summary"]["plan_sha256"])
        self.assertEqual(code, 0, linked)
        self.assertNotEqual(zettel.read_bytes(), before)
        receipt = linked["summary"]["receipt_path"]
        code, dry = self.run_cli("zettel-objet-link-revert", str(self.root), "--receipt", receipt, "--dry-run")
        self.assertEqual(code, 0, dry)
        calls = self.native.calls
        code, reverted = self.run_cli("zettel-objet-link-revert", str(self.root), "--receipt", receipt,
                                      "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, reverted)
        self.assertEqual(self.native.calls, calls + 1)
        self.assertEqual(zettel.read_bytes(), before)
        revert_receipt = json.loads((self.root / reverted["summary"]["revert_receipt_path"]).read_text(encoding="utf-8"))
        self.assertEqual(revert_receipt["exact_human_approval"]["operation"], "zettel_objet_link_revert")

    def test_inventory_is_open_and_grantable(self) -> None:
        for name in ("markup-normalization", "markup-normalization-recovery", "markup-normalization-revert",
                     "zettel-objet-link-revert"):
            self.assertNotIn(name, command_status.COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS)
            self.assertIn(name, command_status.EXACT_APPROVAL_REOPENED_WRITERS)
        for operation in ("markup_normalization", "markup_normalization_revert", "markup_normalization_recovery",
                          "zettel_objet_link_revert"):
            self.assertIn(windows.ExactHumanApprovalOperation(operation), work_session_permission.GRANTABLE_OPERATIONS)


if __name__ == "__main__":
    unittest.main()
