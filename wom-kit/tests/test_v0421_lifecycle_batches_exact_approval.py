"""v0.4.21 LR-01: mint-zet-batch, retire-draft-batch and revert-batch reopened
under one exact human approval each (beta letters 157-160).

Synthetic archive only; the native dialog and archive key are injected. Each
batch is one count-first native decision; every item write re-verifies the
same claim against the batch context and proves its own binding is in the
approved set.
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

from wom_kit import archive_cli
from wom_kit import archive_services
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import operation_approval_binding as binding_module
from wom_kit.exact_human_approval_windows import APPROVE_BUTTON_ID, IDCANCEL

KIT_ROOT = Path(__file__).resolve().parents[1]
REVIEWER = "person:synthetic-lifecycle-reviewer"
PROMOTION_CHECKLIST_IDS = [
    "one_clear_purpose", "understandable_title", "future_self_contained", "source_clarity",
    "object_id_only", "stable_facets", "allowed_edges", "explicit_visibility",
    "provenance_present", "sensitive_content_reviewed",
]
ALPHA = "zet_20260620_batch_alpha"
BETA = "zet_20260620_batch_beta"
TARGET = "zet_20240505_fake_company_onboarding_insight"


class _PagedNative:
    def __init__(self) -> None:
        self.approve = True
        self.calls = 0
        self.plain_calls = 0
        self.main: list[str] = []
        self.pages: list[str] = []

    def show(self, **_kwargs: object) -> tuple[int, bool]:
        self.plain_calls += 1
        self.calls += 1
        return (APPROVE_BUTTON_ID if self.approve else IDCANCEL), True

    def show_collection(self, *, session, **_kwargs: object) -> tuple[int, bool]:
        self.calls += 1
        self.main.append(session.preview.native_main_text())
        self.pages.append(session.preview.native_page_text(0))
        button = APPROVE_BUTTON_ID if self.approve else IDCANCEL
        assert session.button_clicked(button) == "close"
        return button, True


class _KeyProvider:
    def use_key(self, _root, consumer, *, create_if_missing=False):
        key = bytearray(range(32))
        try:
            return consumer(memoryview(key))
        finally:
            key[:] = b"\0" * len(key)


class LifecycleBatchesExactApprovalTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-v0421-lifecycle-")
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.root = self.tmp / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", self.root)
        self.native = _PagedNative()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
        stack.enter_context(patch.object(broker, "_production_key_provider", return_value=_KeyProvider()))
        self.outputs: list[str] = []
        for zettel_id, title, body in (
            (ALPHA, "Batch alpha", "Batch alpha body with enough distinct material for the fixture.\n"),
            (BETA, "Batch beta", "Batch beta body with a separate thought and enough distinct content.\n"),
        ):
            self.make_batch_ready_draft(zettel_id, title, body)

    def make_batch_ready_draft(self, zettel_id: str, title: str, body: str) -> Path:
        template = (self.root / "inbox" / "zet_20260519_draft_ai_lunch_note.md").read_text(encoding="utf-8")
        match = archive_cli.FRONTMATTER_RE.match(template)
        frontmatter = archive_cli.load_yaml(match.group(1))
        frontmatter["provenance"]["created_by"] = "person:test-fixture"
        frontmatter["provenance"]["creation_mode"] = "human_written"
        frontmatter["id"] = zettel_id
        frontmatter["title"] = title
        frontmatter["kind"] = "permanent_note"
        frontmatter["promotion"] = {
            "stage": "promotion_candidate", "ready_for_promotion": True,
            "checklist": {item: True for item in PROMOTION_CHECKLIST_IDS},
        }
        path = self.root / "inbox" / f"{zettel_id}.md"
        path.write_text("---\n" + archive_cli.dump_yaml(frontmatter) + "---\n\n" + body, encoding="utf-8")
        indexed = archive_services.index_archive(self.root)
        self.assertTrue(indexed["index_complete"], indexed)
        return path

    def run_cli(self, *args: str) -> tuple[int, dict]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = archive_cli.main([*args, "--format", "json"])
        self.outputs.extend((out.getvalue(), err.getvalue()))
        self.assertEqual(err.getvalue(), "")
        return code, json.loads(out.getvalue())

    def write_plan(self, name: str, document: dict) -> Path:
        path = self.root / "workbench" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, indent=2), encoding="utf-8")
        return path

    def mint_plan(self) -> str:
        self.write_plan("mint.plan.json", {
            "schema": "wom-kit/mint-zet-batch/v0.1",
            "policy": {"policy_id": "policy:fixture-batch-mint"},
            "items": [{"item_id": "item:alpha", "zettel_id": ALPHA}, {"item_id": "item:beta", "path": f"inbox/{BETA}.md"}],
        })
        return "workbench/mint.plan.json"

    def mint_both(self) -> dict:
        plan = self.mint_plan()
        code, dry = self.run_cli("mint-zet-batch", str(self.root), "--plan", plan, "--dry-run")
        self.assertEqual(code, 0, dry)
        self.assertEqual(dry["summary"]["would_write_count"], 2)
        for item in dry["items"]:
            self.assertRegex(item["approval_plan_sha256"], r"^sha256:[0-9a-f]{64}$")
        code, result = self.run_cli("mint-zet-batch", str(self.root), "--plan", plan, "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, result)
        return result

    def test_mint_batch_mints_two_drafts_under_one_count_first_dialog(self) -> None:
        result = self.mint_both()
        self.assertEqual(result["write_status"], "written")
        self.assertEqual(result["summary"]["written_item_count"], 2)
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.native.plain_calls, 0)
        self.assertEqual(self.native.main, ["대상 2개"])
        self.assertIn(ALPHA + ".md", self.native.pages[0])
        self.assertIn(BETA + ".md", self.native.pages[0])
        for zettel_id in (ALPHA, BETA):
            self.assertTrue((self.root / "zettels" / f"{zettel_id}.md").exists())
        batch_receipt = json.loads((self.root / result["receipt_path"]).read_text(encoding="utf-8"))
        self.assertEqual(batch_receipt["exact_human_approval"]["operation"], "mint_zet_batch")
        approval_id = batch_receipt["exact_human_approval"]["exact_human_approval"]["approval_id"]
        for item in result["items"]:
            mint_receipt = json.loads((self.root / item["mint_receipt_path"]).read_text(encoding="utf-8"))
            self.assertEqual(mint_receipt["exact_human_approval"]["operation"], "mint_zet_batch")
            self.assertEqual(mint_receipt["exact_human_approval"]["exact_human_approval"]["approval_id"], approval_id)
            item_binding = mint_receipt["exact_human_approval"]["batch_item_binding"]
            self.assertEqual(item_binding["target_binding_sha256"], item["approval_target_binding_sha256"])
            self.assertEqual(item_binding["item_identity_sha256"], item["approval_item_identity_sha256"])
            # the second draft's review context (duplicate scan) legitimately
            # changed after the first mint; its exact bytes and destination did not
            self.assertIn(item_binding["match"], {"exact", "target"})
        self.assertNotIn(str(self.root), "".join(self.outputs))
        self.assertNotIn("Batch alpha body", "".join(self.outputs))

    def test_retire_batch_retires_minted_drafts_under_one_dialog(self) -> None:
        self.mint_both()
        self.assertTrue(archive_services.index_archive(self.root)["index_complete"])
        plan = "workbench/retire.plan.json"
        self.write_plan("retire.plan.json", {
            "schema": "wom-kit/retire-draft-batch/v0.1",
            "policy": {"policy_id": "policy:fixture-batch-retire"},
            "items": [{"zettel_id": ALPHA}, {"zettel_id": BETA}],
        })
        code, dry = self.run_cli("retire-draft-batch", str(self.root), "--plan", plan, "--dry-run")
        self.assertEqual(code, 0, dry)
        self.assertEqual(dry["summary"]["would_write_count"], 2)
        binding = binding_module.retire_draft_batch_approval_binding(dict(dry, receipt_path=dry["receipt_path"]))
        self.assertIs(binding.operation, windows.ExactHumanApprovalOperation.retire_draft_batch)
        code, result = self.run_cli("retire-draft-batch", str(self.root), "--plan", plan, "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["summary"]["written_item_count"], 2)
        self.assertEqual(self.native.calls, 2)  # one mint dialog, one retire dialog
        self.assertEqual(self.native.main[-1], "대상 2개")
        for zettel_id in (ALPHA, BETA):
            self.assertFalse((self.root / "inbox" / f"{zettel_id}.md").exists())
            self.assertTrue((self.root / "zettels" / f"{zettel_id}.md").exists())
        batch_receipt = json.loads((self.root / result["receipt_path"]).read_text(encoding="utf-8"))
        self.assertEqual(batch_receipt["exact_human_approval"]["operation"], "retire_draft_batch")
        for item in result["items"]:
            retire_receipt = json.loads((self.root / item["retire_receipt_path"]).read_text(encoding="utf-8"))
            self.assertEqual(retire_receipt["exact_human_approval"]["operation"], "retire_draft_batch")

    def test_revert_batch_removes_a_written_edge_batch_under_one_dialog(self) -> None:
        self.assertTrue(archive_services.index_archive(self.root)["index_complete"])
        plan = self.write_plan("edges.plan.json", {
            "schema": "wom-kit/zettel-edge-batch/v0.1",
            "policy": {"policy_id": "policy:fixture", "policy_label": "Fixture", "auto_write_edge_types": ["material"],
                       "minimum_confidence": "high", "ambiguous_edges_to_review_queue": True},
            "edges": [
                {"candidate_id": "candidate:a", "from_zettel": "zet_20240504_fake_lunch_thought", "target": TARGET,
                 "edge_type": "material", "visibility": "private", "confidence": "high",
                 "review_status": "policy_candidate", "evidence_ref": "fixture:a"},
                {"candidate_id": "candidate:b", "from_zettel": "zet_20260519_fake_family_memory", "target": TARGET,
                 "edge_type": "material", "visibility": "private", "confidence": "high",
                 "review_status": "policy_candidate", "evidence_ref": "fixture:b"},
            ],
        })
        code, written = self.run_cli("zettel-edge-batch", str(self.root), "--plan", str(plan), "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, written)
        self.assertEqual(written["summary"]["written_edge_count"], 2)
        code, dry = self.run_cli("revert-batch", str(self.root), "--receipt", written["receipt_path"], "--dry-run")
        self.assertEqual(code, 0, dry)
        self.assertEqual(dry["write_status"], "would_revert")
        for item in dry["edge_reverts"]:
            self.assertRegex(item["approval_plan_sha256"], r"^sha256:[0-9a-f]{64}$")
        code, reverted = self.run_cli("revert-batch", str(self.root), "--receipt", written["receipt_path"], "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, reverted)
        self.assertEqual(reverted["write_status"], "reverted")
        self.assertEqual(reverted["summary"]["edge_revert_count"], 2)
        self.assertEqual(self.native.calls, 2)
        self.assertEqual(self.native.main, ["대상 2개", "대상 2개"])
        for source in ("zet_20240504_fake_lunch_thought", "zet_20260519_fake_family_memory"):
            self.assertNotIn(TARGET, (self.root / "zettels" / f"{source}.md").read_text(encoding="utf-8"))
        batch_revert = json.loads((self.root / reverted["batch_revert_receipt_path"]).read_text(encoding="utf-8"))
        self.assertEqual(batch_revert["exact_human_approval"]["operation"], "zettel_edge_batch_revert")
        self.assertTrue((self.root / written["receipt_path"]).exists())

    def test_cancel_and_unbound_calls_write_nothing(self) -> None:
        plan = self.mint_plan()
        before = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.native.approve = False
        code, error = self.run_cli("mint-zet-batch", str(self.root), "--plan", plan, "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1)
        self.assertEqual(error["reason_codes"], ["mint_zet_batch_workflow_precondition_failed"])
        self.assertEqual(self.native.calls, 1)
        after = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual({k for k in after if not k.startswith("profiles/local/exact-human-approvals")},
                         {k for k in before if not k.startswith("profiles/local/exact-human-approvals")})
        with patch.object(archive_services, "require_existing_archive_root",
                          side_effect=AssertionError("archive read before approval inputs")):
            for invoke in (
                lambda: archive_services.mint_zet_batch(self.root, plan_path=plan, approve=True, reviewed_by=REVIEWER),
                lambda: archive_services.retire_draft_batch(self.root, plan_path=plan, approve=True, reviewed_by=REVIEWER),
                lambda: archive_services.zettel_edge_batch_revert(self.root, receipt="receipts/x.json", approve=True, reviewed_by=REVIEWER),
            ):
                with self.assertRaises(archive_services.ArchiveServiceError) as caught:
                    invoke()
                self.assertEqual(str(caught.exception), "exact_human_approval_required")
        code, error = self.run_cli("retire-draft-batch", str(self.root), "--plan", plan, "--approve")
        self.assertEqual(error["reason_codes"], ["retire_draft_batch_reviewer_required"])
        self.assertEqual(self.native.calls, 1)


if __name__ == "__main__":
    unittest.main()
