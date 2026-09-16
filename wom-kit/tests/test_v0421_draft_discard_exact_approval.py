"""v0.4.21 LR-01: discard-draft and discard-draft-restore reopened through
operation-specific exact human approval (beta letters 157-160, issue I14).

Synthetic archive only. The native dialog and the archive key are injected at
the same seams the other public approval tests use; no real dialog opens.
"""

from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator

from wom_kit import archive_cli
from wom_kit import archive_services
from wom_kit import command_status
from wom_kit import completion_workflows
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import operation_approval_binding as binding_module
from wom_kit.exact_human_approval_windows import APPROVE_BUTTON_ID, IDCANCEL

KIT_ROOT = Path(__file__).resolve().parents[1]
DRAFT_RELATIVE = "inbox/zet_20260519_draft_ai_lunch_note.md"
REASON = "SYNTHETIC_PRIVATE_REASON human decided not to publish this note"
REVIEWER = "person:synthetic-discard-reviewer"


class _Native:
    def __init__(self, approve: bool = True) -> None:
        self.calls = 0
        self.approve = approve
        self.contexts: list[dict[str, object]] = []

    def show(self, **kwargs: object) -> tuple[int, bool]:
        self.calls += 1
        self.contexts.append(dict(kwargs))
        return (APPROVE_BUTTON_ID if self.approve else IDCANCEL), True


class _KeyProvider:
    def __init__(self) -> None:
        self.calls = 0

    def use_key(self, _root, consumer, *, create_if_missing=False):
        self.calls += 1
        key = bytearray(range(32))
        try:
            return consumer(memoryview(key))
        finally:
            key[:] = b"\0" * len(key)


class DraftDiscardExactApprovalTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-v0421-discard-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", self.root)
        self.native = _Native()
        self.key = _KeyProvider()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
        stack.enter_context(patch.object(broker, "_production_key_provider", return_value=self.key))
        self.outputs: list[str] = []

    # -- helpers -----------------------------------------------------------
    def run_cli(self, *args: str) -> tuple[int, dict]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = archive_cli.main([*args, "--format", "json"])
        self.outputs.extend((out.getvalue(), err.getvalue()))
        self.assertEqual(err.getvalue(), "")
        return code, json.loads(out.getvalue())

    def files(self) -> dict[str, bytes]:
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob("*") if p.is_file()}

    def schema(self, name: str) -> Draft202012Validator:
        return Draft202012Validator(json.loads((KIT_ROOT / "schemas" / name).read_text(encoding="utf-8")))

    def discard_plan(self) -> dict:
        code, plan = self.run_cli("discard-draft", str(self.root), "--path", DRAFT_RELATIVE,
                                  "--reason", REASON, "--dry-run")
        self.assertEqual(code, 0, plan)
        return plan

    # -- tests -------------------------------------------------------------
    def test_plan_reports_exact_approval_available_without_authority_in_the_digest(self) -> None:
        plan = self.discard_plan()
        self.assertTrue(plan["ok"], plan)
        self.assertEqual(plan["state"], "ready")
        self.assertEqual(plan["validation_status"], "ready")
        self.assertEqual(plan["approval_status"], command_status.APPROVAL_AVAILABLE)
        contract = plan["approval_contract"]
        self.assertTrue(contract["approved_write_implemented"])
        self.assertFalse(contract["validation_digest_is_approval_authority"])
        self.assertIsNone(contract["approval_reason_code"])
        self.assertFalse(plan["summary"]["plan_sha256_is_approval_authority"])
        self.assertFalse(plan["summary"]["plan_sha256_validation_only"])
        self.assertTrue(plan["summary"]["exact_byte_restore_approval_available"])
        self.assertNotIn(REASON, json.dumps(plan))
        self.assertEqual(self.native.calls, 0)

    def test_discard_then_restore_through_the_native_boundary(self) -> None:
        before = self.files()
        draft_bytes = before[DRAFT_RELATIVE]
        plan = self.discard_plan()

        code, result = self.run_cli(
            "discard-draft", str(self.root), "--path", DRAFT_RELATIVE, "--reason", REASON,
            "--expected-plan-sha256", plan["summary"]["plan_sha256"], "--approve",
            "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["state"], "discarded")
        self.assertTrue(result["approved"])
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.key.calls, 1)
        self.assertFalse((self.root / DRAFT_RELATIVE).exists())
        snapshot = self.root / plan["summary"]["snapshot_path"]
        self.assertEqual(snapshot.read_bytes(), draft_bytes)
        receipt = json.loads((self.root / plan["summary"]["receipt_path"]).read_text(encoding="utf-8"))
        self.schema("draft-discard-receipt.schema.json").validate(receipt)
        self.assertEqual(receipt["exact_human_approval"]["operation"], "draft_discard")
        self.assertEqual(receipt["reason"], REASON)  # private receipt keeps the reason
        self.assertEqual(receipt["reviewed_by"], REVIEWER)
        # the dialog showed the draft identity, never the reason
        self.assertNotIn(REASON, json.dumps(self.native.contexts, ensure_ascii=False))
        self.assertNotIn(REASON, "".join(self.outputs))
        self.assertNotIn(str(self.root), "".join(self.outputs))

        after_discard = self.files()
        added = set(after_discard) - set(before)
        self.assertIn(plan["summary"]["snapshot_path"], added)
        self.assertIn(plan["summary"]["receipt_path"], added)
        # only the snapshot, the receipt, the approval claim and the lock marker
        self.assertFalse({k for k in added if not (k.startswith("receipts/discarded-drafts/")
                                                   or "exact-human-approvals" in k)}, added)
        self.assertEqual(set(before) - set(after_discard), {DRAFT_RELATIVE})

        code, restore_plan = self.run_cli("discard-draft-restore", str(self.root),
                                          "--receipt", plan["summary"]["receipt_path"], "--dry-run")
        self.assertEqual(code, 0, restore_plan)
        self.assertEqual(restore_plan["state"], "ready")
        code, restored = self.run_cli(
            "discard-draft-restore", str(self.root), "--receipt", plan["summary"]["receipt_path"],
            "--expected-plan-sha256", restore_plan["summary"]["plan_sha256"], "--approve",
            "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, restored)
        self.assertEqual(restored["state"], "restored")
        self.assertEqual(self.native.calls, 2)
        self.assertEqual((self.root / DRAFT_RELATIVE).read_bytes(), draft_bytes)
        restore_receipt = json.loads(
            (self.root / restore_plan["summary"]["restore_receipt_path"]).read_text(encoding="utf-8"))
        self.schema("draft-discard-restore-receipt.schema.json").validate(restore_receipt)
        self.assertEqual(restore_receipt["exact_human_approval"]["operation"], "draft_discard_restore")
        # a second restore of the same receipt is refused without a dialog
        code, again = self.run_cli("discard-draft-restore", str(self.root),
                                   "--receipt", plan["summary"]["receipt_path"], "--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("discard_draft_restore_target_exists", again["blockers"])
        self.assertEqual(self.native.calls, 2)

    def test_cancel_stale_digest_and_missing_reviewer_write_nothing(self) -> None:
        plan = self.discard_plan()
        before = self.files()
        self.native.approve = False
        code, error = self.run_cli(
            "discard-draft", str(self.root), "--path", DRAFT_RELATIVE, "--reason", REASON,
            "--expected-plan-sha256", plan["summary"]["plan_sha256"], "--approve",
            "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1)
        self.assertEqual(error["reason_codes"], ["discard_draft_apply_workflow_precondition_failed"])
        self.assertEqual(error["effects_state"], "none")
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.files(), before)

        self.native.approve = True
        code, error = self.run_cli(
            "discard-draft", str(self.root), "--path", DRAFT_RELATIVE, "--reason", REASON,
            "--expected-plan-sha256", "0" * 64, "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1)
        self.assertEqual(error["reason_codes"], ["discard_draft_apply_plan_changed"])
        self.assertEqual(self.native.calls, 1)  # no dialog for a stale digest
        code, error = self.run_cli(
            "discard-draft", str(self.root), "--path", DRAFT_RELATIVE, "--reason", REASON,
            "--expected-plan-sha256", plan["summary"]["plan_sha256"], "--approve")
        self.assertEqual(error["reason_codes"], ["discard_draft_apply_reviewer_required"])
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.files(), before)
        self.assertNotIn(REASON, "".join(self.outputs))

    def test_unbound_workflow_calls_fail_before_any_archive_read(self) -> None:
        before = self.files()
        plan = completion_workflows.draft_discard_plan(self.root, relative_path=DRAFT_RELATIVE, reason=REASON)
        with patch.object(archive_services, "require_existing_archive_root",
                          side_effect=AssertionError("archive read before approval inputs")):
            with self.assertRaises(archive_services.ArchiveServiceError) as caught:
                completion_workflows.draft_discard_apply(
                    self.root, relative_path=DRAFT_RELATIVE, reason=REASON,
                    expected_plan_sha256=plan["summary"]["plan_sha256"], reviewed_by=REVIEWER)
            self.assertEqual(str(caught.exception), "exact_human_approval_required")
            with self.assertRaises(archive_services.ArchiveServiceError):
                completion_workflows.draft_discard_restore(
                    self.root, receipt="receipts/discarded-drafts/none.discard.json",
                    expected_plan_sha256="0" * 64, reviewed_by=REVIEWER)
        self.assertEqual(self.files(), before)

    def test_binding_hides_paths_and_rejects_blocked_plans(self) -> None:
        plan = self.discard_plan()
        binding = binding_module.draft_discard_approval_binding(plan)
        self.assertIs(binding.operation, windows.ExactHumanApprovalOperation.draft_discard)
        public = json.dumps(binding.public_document())
        for private in (DRAFT_RELATIVE, plan["summary"]["zettel_id"], plan["summary"]["receipt_path"]):
            self.assertNotIn(private, public)
        self.assertEqual(binding.target_preview.primary, DRAFT_RELATIVE.rsplit("/", 1)[-1])
        blocked = dict(plan, ok=False, blockers=["discard_draft_source_invalid"], validation_status="blocked")
        with self.assertRaises(binding_module.OperationApprovalBindingError):
            binding_module.draft_discard_approval_binding(blocked)
        tampered = json.loads(json.dumps(plan))
        tampered["summary"]["mint_receipt_present"] = True
        with self.assertRaises(binding_module.OperationApprovalBindingError):
            binding_module.draft_discard_approval_binding(tampered)

    def test_capability_inventory_reports_both_writers_as_available(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(archive_cli.main(["capabilities", "--machine"]), 0)
        inventory = json.loads(out.getvalue())["data"]["approval_status_inventory"]
        rows = {row["canonical_path"]: row for row in inventory["commands"]}
        for name in ("discard-draft", "discard-draft-restore"):
            self.assertEqual(rows[name]["approval_status"], command_status.APPROVAL_AVAILABLE, rows[name])
            self.assertEqual(rows[name]["approval_exposure_history"]["state"], "history_not_audited")
        self.assertNotIn("discard-draft", command_status.COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS)
        self.assertNotIn("discard-draft-restore", command_status.COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS)


if __name__ == "__main__":
    unittest.main()
