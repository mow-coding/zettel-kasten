"""v0.4.21 LR-01: zettel-edge-batch reopened under one exact human approval
(beta letters 157-160, issue I40: one dialog per edge became 21 dialogs).

Synthetic archive only; the native dialog and archive key are injected.
"""

from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wom_kit import archive_cli
from wom_kit import archive_services
from wom_kit import command_status
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import operation_approval_binding as binding_module
from wom_kit.exact_human_approval_windows import APPROVE_BUTTON_ID, IDCANCEL

KIT_ROOT = Path(__file__).resolve().parents[1]
REVIEWER = "person:synthetic-batch-reviewer"
SOURCE_A = "zet_20240504_fake_lunch_thought"
SOURCE_B = "zet_20240505_fake_company_onboarding_insight"
TARGET = "zet_20260519_fake_family_memory"


class _PagedNative:
    """Legacy ``show`` plus the v0.4.20 count-first ``show_collection``."""

    def __init__(self) -> None:
        self.approve = True
        self.calls = 0
        self.main: list[str] = []
        self.pages: list[str] = []
        self.plain_calls = 0

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
    def __init__(self) -> None:
        self.calls = 0

    def use_key(self, _root, consumer, *, create_if_missing=False):
        self.calls += 1
        key = bytearray(range(32))
        try:
            return consumer(memoryview(key))
        finally:
            key[:] = b"\0" * len(key)


def _plan_document(edges: list[dict]) -> dict:
    return {
        "schema": "wom-kit/zettel-edge-batch/v0.1",
        "policy": {
            "policy_id": "policy:fixture-high-confidence-material",
            "policy_label": "Fixture high confidence material",
            "auto_write_edge_types": ["material"],
            "minimum_confidence": "high",
            "ambiguous_edges_to_review_queue": True,
        },
        "edges": edges,
    }


class ZettelEdgeBatchExactApprovalTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-v0421-edge-batch-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", self.root)
        indexed = archive_services.index_archive(self.root)
        self.assertTrue(indexed["ok"], indexed)
        self.native = _PagedNative()
        self.key = _KeyProvider()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
        stack.enter_context(patch.object(broker, "_production_key_provider", return_value=self.key))
        self.plan_path = Path(temporary.name) / "edge-batch.plan.json"
        self.plan_path.write_text(json.dumps(_plan_document([
            {"candidate_id": "candidate:a", "from_zettel": SOURCE_A, "target": TARGET,
             "edge_type": "material", "visibility": "private", "confidence": "high",
             "review_status": "policy_candidate", "evidence_ref": "fixture:row-a"},
            {"candidate_id": "candidate:b", "from_zettel": SOURCE_B, "target": TARGET,
             "edge_type": "material", "visibility": "private", "confidence": "high",
             "review_status": "policy_candidate", "evidence_ref": "fixture:row-b"},
            {"candidate_id": "candidate:low", "from_zettel": SOURCE_A, "target": SOURCE_B,
             "edge_type": "material", "visibility": "private", "confidence": "low",
             "review_status": "policy_candidate", "evidence_ref": "fixture:row-low"},
        ]), indent=2), encoding="utf-8")
        self.outputs: list[str] = []

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

    def dry_run(self) -> dict:
        code, plan = self.run_cli("zettel-edge-batch", str(self.root), "--plan", str(self.plan_path), "--dry-run")
        self.assertEqual(code, 0, plan)
        return plan

    def test_dry_run_carries_item_bindings_and_capability_truth(self) -> None:
        plan = self.dry_run()
        self.assertEqual(plan["write_status"], "would_write")
        self.assertEqual(plan["summary"]["policy_writable_edge_count"], 2)
        self.assertEqual(plan["summary"]["review_queue_count"], 1)
        for item in plan["policy_writable_edges"]:
            self.assertRegex(item["approval_plan_sha256"], r"^sha256:[0-9a-f]{64}$")
            self.assertRegex(item["approval_target_binding_sha256"], r"^sha256:[0-9a-f]{64}$")
        capability = plan["current_capability"]
        self.assertTrue(capability["one_exact_human_approval_per_batch"])
        self.assertFalse(capability["compound_exact_human_approval_binding_required"])
        binding = binding_module.zettel_edge_batch_approval_binding(plan)
        self.assertIs(binding.operation, windows.ExactHumanApprovalOperation.zettel_edge_batch)
        public = json.dumps(binding.public_document())
        for private in (SOURCE_A, SOURCE_B, TARGET, plan["batch_id"], plan["receipt_path"]):
            self.assertNotIn(private, public)

    def test_one_dialog_writes_every_policy_edge_and_embeds_the_batch_approval(self) -> None:
        plan = self.dry_run()
        before = self.files()
        code, result = self.run_cli("zettel-edge-batch", str(self.root), "--plan", str(self.plan_path),
                                    "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, result)
        self.assertTrue(result["ok"])
        self.assertEqual(result["write_status"], "written")
        self.assertEqual(result["summary"]["written_edge_count"], 2)
        self.assertEqual(result["summary"]["review_queue_count"], 1)
        # exactly one native decision, shown count-first with both source zets
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.native.plain_calls, 0)
        self.assertEqual(self.native.main, ["대상 2개"])
        self.assertIn(SOURCE_A + ".md", self.native.pages[0])
        self.assertIn(SOURCE_B + ".md", self.native.pages[0])
        self.assertEqual(self.key.calls, 1)
        after = self.files()
        batch_receipt = json.loads(after[plan["receipt_path"]].decode("utf-8"))
        self.assertEqual(batch_receipt["exact_human_approval"]["operation"], "zettel_edge_batch")
        self.assertEqual(batch_receipt["written_edge_count"], 2)
        for item in result["policy_writable_edges"]:
            edge_receipt = json.loads(after[item["receipt_path"]].decode("utf-8"))
            approval = edge_receipt["exact_human_approval"]
            self.assertEqual(approval["operation"], "zettel_edge_batch")
            self.assertEqual(approval["exact_human_approval"]["approval_id"],
                             batch_receipt["exact_human_approval"]["exact_human_approval"]["approval_id"])
            self.assertEqual(approval["batch_item_binding"]["plan_sha256"], item["approval_plan_sha256"])
        for source in (SOURCE_A, SOURCE_B):
            text = after[f"zettels/{source}.md"].decode("utf-8")
            self.assertIn(TARGET, text)
        self.assertNotIn(str(self.root), "".join(self.outputs))
        # the low-confidence row stayed in the review queue and changed nothing
        changed = {k for k in after if after.get(k) != before.get(k)}
        self.assertTrue(changed.issuperset({f"zettels/{SOURCE_A}.md", f"zettels/{SOURCE_B}.md", plan["receipt_path"]}))

    def test_cancel_and_changed_source_write_nothing(self) -> None:
        plan = self.dry_run()
        before = self.files()
        self.native.approve = False
        code, error = self.run_cli("zettel-edge-batch", str(self.root), "--plan", str(self.plan_path),
                                   "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1)
        self.assertEqual(error["reason_codes"], ["zettel_edge_batch_workflow_precondition_failed"])
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.files(), before)
        # a source zet edited between the dialog and the write is refused by
        # the fresh item binding; nothing is written and nothing is echoed
        self.native.approve = True
        original_write = archive_services.zettel_edge_batch_write

        def edit_source_then_write(*args, **kwargs):
            if kwargs.get("approve"):
                path = self.root / "zettels" / f"{SOURCE_A}.md"
                path.write_bytes(path.read_bytes() + b"\nedited after the dialog\n")
                archive_services.index_archive(self.root)
            return original_write(*args, **kwargs)

        with patch.object(archive_services, "zettel_edge_batch_write", side_effect=edit_source_then_write):
            code, error = self.run_cli("zettel-edge-batch", str(self.root), "--plan", str(self.plan_path),
                                       "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1)
        # the writer refused after the decision, so the boundary reports the
        # honest unknown-state code; the batch rolled its snapshots back
        self.assertEqual(error["reason_codes"], ["exact_human_approval_state_unknown"])
        self.assertFalse((self.root / plan["receipt_path"]).exists())
        self.assertNotIn(TARGET, (self.root / "zettels" / f"{SOURCE_B}.md").read_text(encoding="utf-8"))
        for item in plan["policy_writable_edges"]:
            self.assertFalse((self.root / item["receipt_path"]).exists())
        self.assertNotIn(str(self.root), "".join(self.outputs))

    def _two_edges_from_one_source_plan(self) -> Path:
        plan_path = self.plan_path.parent / "edge-batch-same-source.plan.json"
        plan_path.write_text(json.dumps(_plan_document([
            {"candidate_id": "candidate:a1", "from_zettel": SOURCE_A, "target": TARGET,
             "edge_type": "material", "visibility": "private", "confidence": "high",
             "review_status": "policy_candidate", "evidence_ref": "fixture:row-a1"},
            {"candidate_id": "candidate:a2", "from_zettel": SOURCE_A, "target": SOURCE_B,
             "edge_type": "material", "visibility": "private", "confidence": "high",
             "review_status": "policy_candidate", "evidence_ref": "fixture:row-a2"},
        ]), indent=2), encoding="utf-8")
        return plan_path

    def test_second_edge_from_one_source_is_approved_only_after_the_batch_own_write(self) -> None:
        # Two edges from the same source zet: the second item's fresh binding
        # differs from the dialog's (the batch itself changed the source), so it
        # is written under the identity rule, and only because the writer proved
        # the bytes it read are exactly the bytes the batch wrote.
        plan_path = self._two_edges_from_one_source_plan()
        code, plan = self.run_cli("zettel-edge-batch", str(self.root), "--plan", str(plan_path), "--dry-run")
        self.assertEqual(code, 0, plan)
        code, result = self.run_cli("zettel-edge-batch", str(self.root), "--plan", str(plan_path),
                                    "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["summary"]["written_edge_count"], 2)
        self.assertEqual(self.native.calls, 1)
        after = self.files()
        matches = []
        for item in result["policy_writable_edges"]:
            receipt = json.loads(after[item["receipt_path"]].decode("utf-8"))
            matches.append(receipt["exact_human_approval"]["batch_item_binding"]["match"])
        self.assertEqual(matches, ["exact", "identity_after_own_write"])
        source_text = after[f"zettels/{SOURCE_A}.md"].decode("utf-8")
        self.assertIn(TARGET, source_text)
        self.assertIn(SOURCE_B, source_text)

    def test_foreign_edit_after_the_batch_own_write_is_refused(self) -> None:
        # The invariant "the only change since the dialog was the batch's own
        # write" must hold at the moment the item writer reads the source, not
        # only when the batch loop looked: a foreign edit landing after the
        # first write and before the second item's fresh read is refused.
        plan_path = self._two_edges_from_one_source_plan()
        code, plan = self.run_cli("zettel-edge-batch", str(self.root), "--plan", str(plan_path), "--dry-run")
        self.assertEqual(code, 0, plan)
        before = self.files()
        original_write = archive_services.zettel_edge_write
        calls = {"approve": 0}

        def foreign_edit_before_second_item(*args, **kwargs):
            if kwargs.get("approve"):
                calls["approve"] += 1
                if calls["approve"] == 2:
                    path = self.root / "zettels" / f"{SOURCE_A}.md"
                    path.write_bytes(path.read_bytes() + b"\nforeign edit between the batch items\n")
            return original_write(*args, **kwargs)

        with patch.object(archive_services, "zettel_edge_write", side_effect=foreign_edit_before_second_item):
            code, error = self.run_cli("zettel-edge-batch", str(self.root), "--plan", str(plan_path),
                                       "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1, error)
        self.assertEqual(calls["approve"], 2)
        self.assertEqual(error["reason_codes"], ["exact_human_approval_state_unknown"])
        self.assertEqual(self.native.calls, 1)
        # the batch rolled its snapshots back: no receipts, no edge, and the
        # foreign paragraph is not reported as the batch's own work
        self.assertFalse((self.root / plan["receipt_path"]).exists())
        for item in plan["policy_writable_edges"]:
            self.assertFalse((self.root / item["receipt_path"]).exists())
        self.assertEqual(self.files()[f"zettels/{SOURCE_A}.md"], before[f"zettels/{SOURCE_A}.md"])
        self.assertNotIn(str(self.root), "".join(self.outputs))

    def test_item_authority_identity_rule_needs_the_exact_own_write_digest(self) -> None:
        authority = archive_services._ExactBatchAuthority(
            context=None, plan_sha256="sha256:" + "a" * 64, target_binding_sha256="sha256:" + "b" * 64,
            item_bindings=frozenset(), item_identities=frozenset({"sha256:" + "c" * 64}),
            receipt={"operation": "zettel_edge_batch"},
        )
        with self.assertRaises(archive_services.ArchiveServiceError) as bad_digest:
            authority.for_item("sha256:" + "c" * 64, own_write_source_sha256="not-a-digest")
        self.assertEqual(str(bad_digest.exception), "exact_batch_authority_invalid")
        item = authority.for_item("sha256:" + "c" * 64, own_write_source_sha256="sha256:" + "d" * 64)
        binding = SimpleNamespace(plan_sha256="sha256:" + "e" * 64, target_binding_sha256="sha256:" + "f" * 64)
        claim = broker._ClaimedExactHumanApproval.__new__(broker._ClaimedExactHumanApproval)
        for fresh in (None, "sha256:" + "0" * 64):
            with self.assertRaises(archive_services.ArchiveServiceError) as refused:
                item.item_approval(binding, claim=claim, item_identity_sha256="sha256:" + "c" * 64,
                                   fresh_source_sha256=fresh)
            self.assertEqual(str(refused.exception), "exact_batch_item_not_approved")

    def test_unbound_service_calls_fail_before_any_archive_read(self) -> None:
        before = self.files()
        with patch.object(archive_services, "require_existing_archive_root",
                          side_effect=AssertionError("archive read before approval inputs")):
            with self.assertRaises(archive_services.ArchiveServiceError) as caught:
                archive_services.zettel_edge_batch_write(
                    self.root, plan_path=self.plan_path, dry_run=False, approve=True, reviewed_by=REVIEWER)
        self.assertEqual(str(caught.exception), "exact_human_approval_required")
        # a forged batch authority is refused before any read as well
        with self.assertRaises(archive_services.ArchiveServiceError) as forged:
            archive_services.zettel_edge_write(
                self.root, from_zettel=SOURCE_A, target_ref=TARGET, edge_type="material",
                approve=True, reviewed_by=REVIEWER, batch_authority=object())
        self.assertEqual(str(forged.exception), "exact_batch_authority_invalid")
        self.assertEqual(self.files(), before)

    def test_reviewer_and_mode_errors_open_no_dialog(self) -> None:
        code, error = self.run_cli("zettel-edge-batch", str(self.root), "--plan", str(self.plan_path), "--approve")
        self.assertEqual(error["reason_codes"], ["zettel_edge_batch_reviewer_required"])
        code, error = self.run_cli("zettel-edge-batch", str(self.root), "--plan", str(self.plan_path),
                                   "--approve", "--dry-run", "--reviewed-by", REVIEWER)
        self.assertEqual(error["reason_codes"], ["capability_mode_conflicting"])  # shared parser gate
        self.assertEqual(self.native.calls, 0)
        rows = {row["canonical_path"]: row for row in archive_cli._parser_capability_inventory(
            archive_cli.build_parser())["commands"]}
        self.assertEqual(rows["zettel-edge-batch"]["approval_status"], command_status.APPROVAL_AVAILABLE)


if __name__ == "__main__":
    unittest.main()
