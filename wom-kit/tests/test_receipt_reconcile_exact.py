"""2026-09-24 reopen (58-writer triage, group 1): receipt reconcile under exact approval.

Letters 147/148/156 reported thousands of mint and retired-draft receipt
mismatches, mostly an ``assets`` field added after mint, while the only repair
writer was closed. One reviewed list is now written under one exact approval
(native dialog here; a valid session grant in real use) and every item
re-derives its evidence digest before its own write.

Synthetic archive only; the native dialog and archive key are injected.
"""

from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wom_kit import archive_cli
from wom_kit import archive_services
from wom_kit import command_status
from wom_kit import exact_human_approval_windows as windows
from wom_kit import work_session_permission

import test_v0421_lifecycle_batches_exact_approval as lifecycle

ALPHA, BETA, REVIEWER = lifecycle.ALPHA, lifecycle.BETA, lifecycle.REVIEWER


class ReceiptReconcileExactTests(unittest.TestCase):
    setUp = lifecycle.LifecycleBatchesExactApprovalTests.setUp
    make_batch_ready_draft = lifecycle.LifecycleBatchesExactApprovalTests.make_batch_ready_draft
    run_cli = lifecycle.LifecycleBatchesExactApprovalTests.run_cli
    write_plan = lifecycle.LifecycleBatchesExactApprovalTests.write_plan
    mint_plan = lifecycle.LifecycleBatchesExactApprovalTests.mint_plan
    mint_both = lifecycle.LifecycleBatchesExactApprovalTests.mint_both

    def canonical(self, zettel_id: str) -> Path:
        return self.root / "zettels" / f"{zettel_id}.md"

    def add_assets_after_mint(self, zettel_id: str) -> None:
        path = self.canonical(zettel_id)
        text = path.read_text(encoding="utf-8")
        match = archive_cli.FRONTMATTER_RE.match(text)
        frontmatter = archive_cli.load_yaml(match.group(1))
        frontmatter["assets"] = ["asset:sha256:" + "a" * 64]
        path.write_text("---\n" + archive_cli.dump_yaml(frontmatter) + "---\n" + text[match.end():], encoding="utf-8")

    def crlf(self, zettel_id: str) -> None:
        path = self.canonical(zettel_id)
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))

    def drift_both(self) -> None:
        self.mint_both()
        self.crlf(ALPHA)
        self.add_assets_after_mint(BETA)

    def receipt(self, relative: str) -> dict:
        return json.loads((self.root / relative).read_text(encoding="utf-8"))

    def test_batch_lists_both_classes_and_one_approval_reconciles_them(self) -> None:
        self.drift_both()
        code, dry = self.run_cli("remint-reconcile-batch", str(self.root), "--dry-run")
        self.assertEqual(code, 0, dry)
        self.assertEqual(dry["write_status"], "would_write")
        self.assertEqual(dry["summary"]["format_drift_count"], 1)
        self.assertEqual(dry["summary"]["content_change_count"], 1)
        self.assertEqual(dry["summary"]["changed_field_counts"], {"assets": 1})
        self.assertEqual({item["zettel_id"]: item["drift_class"] for item in dry["items"]},
                         {ALPHA: "format_drift", BETA: "content_change"})
        self.assertNotIn("Batch alpha body", json.dumps(dry, ensure_ascii=False))
        code, result = self.run_cli("remint-reconcile-batch", str(self.root), "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["write_status"], "written")
        self.assertEqual(result["reconciled_count"], 2)
        self.assertEqual(self.native.calls, 2)  # one mint dialog, one reconcile dialog
        approval = self.receipt(result["batch_receipt_path"])["exact_human_approval"]
        self.assertEqual(approval["operation"], "remint_reconcile")
        self.assertEqual(result["exact_human_approval"]["approval_id"], approval["exact_human_approval"]["approval_id"])
        approval_id = approval["exact_human_approval"]["approval_id"]
        for zettel_id in (ALPHA, BETA):
            mint = self.receipt(f"receipts/mint/{zettel_id}.mint.json")
            self.assertEqual(mint["target"]["sha256"], archive_services.sha256_path(self.canonical(zettel_id)))
            self.assertEqual(mint["reconcile"]["exact_human_approval_id"], approval_id)
        for item in result["items"]:
            audit = self.receipt(item["reconcile_receipt_path"])
            self.assertEqual(audit["exact_human_approval"]["exact_human_approval"]["approval_id"], approval_id)
            self.assertEqual(audit["approval_item_sha256"], item["approval_item_sha256"])
        batch = self.receipt(result["batch_receipt_path"])
        self.assertEqual(batch["reconciled_count"], 2)
        self.assertEqual(batch["exact_human_approval"]["operation"], "remint_reconcile")
        code, again = self.run_cli("remint-reconcile-batch", str(self.root), "--dry-run")
        self.assertEqual(again["summary"]["item_count"], 0)
        self.assertEqual(again["write_status"], "nothing_to_write")

    def test_retired_draft_receipts_follow_the_mint_repair(self) -> None:
        self.mint_both()
        self.assertTrue(archive_services.index_archive(self.root)["index_complete"])
        plan = "workbench/retire.plan.json"
        self.write_plan("retire.plan.json", {
            "schema": "wom-kit/retire-draft-batch/v0.1",
            "policy": {"policy_id": "policy:fixture-batch-retire"},
            "items": [{"zettel_id": ALPHA}, {"zettel_id": BETA}],
        })
        code, retired = self.run_cli("retire-draft-batch", str(self.root), "--plan", plan, "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, retired)
        self.add_assets_after_mint(ALPHA)
        code, mint_fix = self.run_cli("remint-reconcile-batch", str(self.root), "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, mint_fix)
        self.assertTrue(any("retire-draft-reconcile-batch" in action for action in mint_fix["next_safe_actions"]))
        code, dry = self.run_cli("retire-draft-reconcile-batch", str(self.root), "--dry-run")
        self.assertEqual(code, 0, dry)
        self.assertEqual([item["zettel_id"] for item in dry["items"]], [ALPHA])
        self.assertIn("mint_receipt", dry["items"][0]["changed_refs"])
        code, result = self.run_cli("retire-draft-reconcile-batch", str(self.root), "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, result)
        self.assertEqual(self.receipt(result["batch_receipt_path"])["exact_human_approval"]["operation"],
                         "retire_draft_reconcile")
        retire = self.receipt(f"receipts/mint/retired-drafts/{ALPHA}.retire-draft.json")
        self.assertEqual(retire["mint_receipt"]["sha256"],
                         archive_services.sha256_path(self.root / f"receipts/mint/{ALPHA}.mint.json"))
        code, again = self.run_cli("retire-draft-reconcile-batch", str(self.root), "--dry-run")
        self.assertEqual(again["summary"]["item_count"], 0)

    def test_single_command_approve_keeps_the_content_change_contract(self) -> None:
        self.drift_both()
        code, error = self.run_cli("remint-reconcile", str(self.root), "--zettel-id", BETA, "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1)
        self.assertEqual(error["reason_codes"], ["remint_reconcile_content_changed_ack_required"])
        self.assertEqual(self.native.calls, 1)  # only the mint dialog
        code, dry = self.run_cli("remint-reconcile", str(self.root), "--zettel-id", BETA, "--dry-run")
        self.assertEqual(dry["drift_class"], "content_change")
        self.assertEqual(dry.get("approval_status"), None)  # no longer projected as closed
        code, result = self.run_cli(
            "remint-reconcile", str(self.root), "--zettel-id", BETA, "--approve", "--reviewed-by", REVIEWER,
            "--content-changed-ack", "--reviewed-plan-sha256", dry["review_plan_sha256"],
        )
        self.assertEqual(code, 0, result)
        self.assertEqual([item["zettel_id"] for item in result["items"]], [BETA])
        self.assertEqual(self.native.calls, 2)
        code, result = self.run_cli("remint-reconcile", str(self.root), "--path", f"zettels/{ALPHA}.md",
                                    "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, result)
        self.assertEqual([item["zettel_id"] for item in result["items"]], [ALPHA])

    def test_cancel_writes_nothing_and_item_drift_after_approval_is_refused(self) -> None:
        self.drift_both()
        watched = sorted((self.root / "receipts" / "mint").rglob("*.json"))
        before = {path: path.read_bytes() for path in watched}
        self.native.approve = False
        code, error = self.run_cli("remint-reconcile-batch", str(self.root), "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1)
        self.assertEqual(error["reason_codes"], ["remint_reconcile_batch_workflow_precondition_failed"])
        self.assertEqual({path: path.read_bytes() for path in watched}, before)
        self.assertFalse((self.root / "receipts" / "mint" / "reconciles").exists())
        # The apply writers refuse without the private token the batch builds.
        blocked = archive_services.remint_reconcile_apply(self.root, zettel_id=ALPHA, reviewed_by=REVIEWER)
        self.assertEqual(blocked["blockers"], [command_status.COMPOUND_APPROVAL_REASON_CODE])
        # A canonical that changes after the list was approved is not laundered.
        self.native.approve = True
        real = archive_services._receipt_reconcile_require_item

        def drift_then_check(root, kind, plan, approval, *, strip_bom):
            if plan.get("zettel_id") == ALPHA:
                self.canonical(ALPHA).write_bytes(self.canonical(ALPHA).read_bytes() + b"late\r\n")
                plan = archive_services.remint_reconcile_plan(root, zettel_id=ALPHA)
            return real(root, kind, plan, approval, strip_bom=strip_bom)

        with patch.object(archive_services, "_receipt_reconcile_require_item", side_effect=drift_then_check):
            code, result = self.run_cli("remint-reconcile-batch", str(self.root), "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1, result)
        self.assertEqual(result["write_status"], "partial")
        failed = [item for item in result["items"] if item["write_status"] == "failed"]
        self.assertEqual([item["zettel_id"] for item in failed], [ALPHA])
        self.assertEqual(failed[0]["blockers"], ["receipt_reconcile_item_changed_after_approval"])

    def test_unbound_service_call_reads_nothing_and_inventory_is_open(self) -> None:
        with patch.object(archive_services, "require_existing_archive_root",
                          side_effect=AssertionError("archive read before approval inputs")):
            with self.assertRaises(archive_services.ArchiveServiceError) as caught:
                archive_services.receipt_reconcile_batch(self.root, kind="mint", dry_run=False, approve=True,
                                                         reviewed_by=REVIEWER)
        self.assertEqual(str(caught.exception), "exact_human_approval_required")
        for name in ("remint-reconcile", "retire-draft-reconcile", "remint-reconcile-batch", "retire-draft-reconcile-batch"):
            self.assertNotIn(name, command_status.COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS)
            self.assertIn(name, command_status.EXACT_APPROVAL_REOPENED_WRITERS)
        # A limited/allow_all session grant covers them like every other kind (2026-09-17).
        for operation in (windows.ExactHumanApprovalOperation.remint_reconcile,
                          windows.ExactHumanApprovalOperation.retire_draft_reconcile):
            self.assertIn(operation, work_session_permission.GRANTABLE_OPERATIONS)


if __name__ == "__main__":
    unittest.main()
