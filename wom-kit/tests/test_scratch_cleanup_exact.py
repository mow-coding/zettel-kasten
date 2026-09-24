"""2026-09-24 reopen (58-writer triage, group 2): scratch cleanup under exact approval.

`ai-scratch-gc` deletes the AI scratch files one zet explicitly references and
`zet-catalog-pass-cleanup` deletes one SHA-bound catalog-pass artifact. Both
run under one exact approval (native dialog here; a valid session grant in
real use) and re-derive what they approved immediately before deleting.

Synthetic archive only; the native dialog and archive key are injected.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wom_kit import archive_cli
from wom_kit import archive_services
from wom_kit import command_status
from wom_kit import exact_human_approval_windows as windows
from wom_kit import work_session_permission

import test_v0421_lifecycle_batches_exact_approval as lifecycle

ALPHA, REVIEWER = lifecycle.ALPHA, lifecycle.REVIEWER
SCRATCH = (".wom-scratch/ai/note-a.md", ".wom-scratch/ai/note-b.md")


class ScratchCleanupExactTests(unittest.TestCase):
    setUp = lifecycle.LifecycleBatchesExactApprovalTests.setUp
    make_batch_ready_draft = lifecycle.LifecycleBatchesExactApprovalTests.make_batch_ready_draft
    run_cli = lifecycle.LifecycleBatchesExactApprovalTests.run_cli

    def reference_scratch(self) -> None:
        for index, relative in enumerate(SCRATCH):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"temporary AI note {index}\n", encoding="utf-8")
        draft = self.root / "inbox" / f"{ALPHA}.md"
        draft.write_text(
            draft.read_text(encoding="utf-8") + "\nWorking notes: " + " and ".join(SCRATCH) + "\n",
            encoding="utf-8",
        )

    def test_one_approval_deletes_only_the_referenced_scratch(self) -> None:
        self.reference_scratch()
        unrelated = self.root / ".wom-scratch" / "ai" / "unrelated.md"
        unrelated.write_text("keep me\n", encoding="utf-8")
        code, dry = self.run_cli("ai-scratch-gc", str(self.root), "--zettel-id", ALPHA, "--dry-run")
        self.assertEqual(code, 0, dry)
        self.assertEqual(dry["cleanup_plan"]["candidate_count"], 2)
        code, result = self.run_cli("ai-scratch-gc", str(self.root), "--zettel-id", ALPHA, "--approve",
                                    "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, result)
        self.assertEqual(self.native.calls, 1)
        for relative in SCRATCH:
            self.assertFalse((self.root / relative).exists())
        self.assertTrue(unrelated.exists())
        receipt = json.loads((self.root / result["receipt_path"]).read_text(encoding="utf-8"))
        self.assertEqual(receipt["exact_human_approval"]["operation"], "ai_scratch_gc")
        self.assertEqual(result["exact_human_approval"]["approval_id"],
                         receipt["exact_human_approval"]["exact_human_approval"]["approval_id"])
        self.assertTrue((self.root / "inbox" / f"{ALPHA}.md").exists())

    def test_cancel_or_a_changed_file_deletes_nothing(self) -> None:
        self.reference_scratch()
        before = {relative: (self.root / relative).read_bytes() for relative in SCRATCH}
        self.native.approve = False
        code, error = self.run_cli("ai-scratch-gc", str(self.root), "--zettel-id", ALPHA, "--approve",
                                   "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1)
        self.assertEqual(error["reason_codes"], ["ai_scratch_gc_workflow_precondition_failed"])
        self.assertEqual({relative: (self.root / relative).read_bytes() for relative in SCRATCH}, before)
        self.native.approve = True
        real = archive_services._require_exact_human_operation_approval

        def change_then_approve(*args, **kwargs):
            (self.root / SCRATCH[0]).write_text("edited after review\n", encoding="utf-8")
            return real(*args, **kwargs)

        with patch.object(archive_services, "_require_exact_human_operation_approval", side_effect=change_then_approve):
            code, result = self.run_cli("ai-scratch-gc", str(self.root), "--zettel-id", ALPHA, "--approve",
                                        "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1, result)
        self.assertEqual(result["blockers"], [archive_services.AI_SCRATCH_GC_APPROVAL_BINDING_CHANGED])
        for relative in SCRATCH:
            self.assertTrue((self.root / relative).exists())
        self.assertFalse((self.root / "receipts" / "scratch-gc").exists())

    def test_no_referenced_scratch_opens_no_dialog(self) -> None:
        code, result = self.run_cli("ai-scratch-gc", str(self.root), "--zettel-id", ALPHA, "--approve",
                                    "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["write_status"], "nothing_to_write")
        self.assertEqual(self.native.calls, 0)

    def catalog_pass(self) -> tuple[str, str]:
        output_relative = ".wom-scratch/diagnostics/catalog-pass-cleanup.jsonl"
        code, created = self.run_cli("zet-catalog-pass", str(self.root), "--projection", "reading",
                                     "--page-size", "1", "--output", output_relative, "--dry-run")
        self.assertEqual(code, 0, created)
        return output_relative, created["output"]["sha256"]

    def test_catalog_pass_artifact_is_deleted_under_one_approval(self) -> None:
        relative, sha256 = self.catalog_pass()
        base = ("zet-catalog-pass-cleanup", str(self.root), "--input", relative, "--expected-sha256", sha256)
        self.native.approve = False
        code, error = self.run_cli(*base, "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1)
        self.assertEqual(error["reason_codes"], ["zet_catalog_pass_cleanup_workflow_precondition_failed"])
        self.assertTrue((self.root / relative).exists())
        self.native.approve = True
        code, result = self.run_cli(*base, "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "deleted")
        self.assertEqual(result["approval"]["exact_human_approval_operation"], "zet_catalog_pass_cleanup")
        self.assertFalse((self.root / relative).exists())
        self.assertEqual(self.native.calls, 2)

    def test_unbound_calls_are_refused_and_inventory_is_open(self) -> None:
        relative, sha256 = self.catalog_pass()
        refused = archive_cli._cleanup_zet_catalog_pass_output_file_legacy_core(
            relative, self.root, expected_sha256=sha256, approve=True, reviewed_by=REVIEWER,
        )
        self.assertEqual(refused["blockers"], ["exact_human_approval_required"])
        self.assertTrue((self.root / relative).exists())
        with patch.object(archive_services, "require_existing_archive_root",
                          side_effect=AssertionError("archive read before approval inputs")):
            with self.assertRaises(archive_services.ArchiveServiceError) as caught:
                archive_services.ai_scratch_gc_for_zettel(self.root, zettel_id=ALPHA, dry_run=False,
                                                          approve=True, reviewed_by=REVIEWER)
        self.assertEqual(str(caught.exception), "exact_human_approval_required")
        for name in ("ai-scratch-gc", "zet-catalog-pass-cleanup"):
            self.assertNotIn(name, command_status.COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS)
            self.assertIn(name, command_status.EXACT_APPROVAL_REOPENED_WRITERS)
        for operation in (windows.ExactHumanApprovalOperation.ai_scratch_gc,
                          windows.ExactHumanApprovalOperation.zet_catalog_pass_cleanup):
            self.assertIn(operation, work_session_permission.GRANTABLE_OPERATIONS)


if __name__ == "__main__":
    unittest.main()
