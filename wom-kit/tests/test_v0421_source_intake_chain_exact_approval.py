"""v0.4.21 LR-01e: the objet intake chain (source-intake-record →
objet-capture-selection → objet-capture) under ONE exact human approval
(beta letter 160 ⑦: three dialogs per objet, 42 popups for three drafts).

Synthetic archive only; the native dialog and archive key are injected. The
result documents never echo the staged file's private name or body, the
operator path, or the reviewer id.
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
from wom_kit import command_status
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import objet_capture_selection_exact
from wom_kit import source_intake_chain_exact as chain
from wom_kit import source_intake_record_exact
from wom_kit.exact_human_approval_windows import APPROVE_BUTTON_ID, IDCANCEL

KIT_ROOT = Path(__file__).resolve().parents[1]
REVIEWER = "person:synthetic-chain-reviewer"
PRIVATE_NAME = "PRIVATE_STAGED_NAME_SYNTHETIC.txt"
PRIVATE_BODY = "PRIVATE_STAGED_BODY_SYNTHETIC line\n"
STAGED_RELATIVE = f"staging/incoming/{PRIVATE_NAME}"


class _Native:
    def __init__(self) -> None:
        self.approve = True
        self.calls = 0
        self.contexts: list[dict[str, object]] = []

    def show(self, **kwargs: object) -> tuple[int, bool]:
        self.calls += 1
        self.contexts.append(dict(kwargs))
        return (APPROVE_BUTTON_ID if self.approve else IDCANCEL), True


class _KeyProvider:
    def use_key(self, _root, consumer, *, create_if_missing=False):
        key = bytearray(range(32))
        try:
            return consumer(memoryview(key))
        finally:
            key[:] = b"\0" * len(key)


class SourceIntakeChainExactApprovalTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-v0421-chain-")
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name)
        self.root = self.workspace / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", self.root)
        indexed = archive_services.index_archive(self.root)
        self.assertEqual(indexed.get("index_state"), "current", indexed)
        staged = self.root / Path(STAGED_RELATIVE)
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_bytes(PRIVATE_BODY.encode("utf-8"))
        document = archive_services.source_intake_plan(
            self.root, local_path=staged, redact_local_paths=True
        )
        self.assertTrue(document["ok"], document)
        self.plan_path = self.workspace / "source-intake-plan.json"
        self.plan_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        self.native = _Native()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
        stack.enter_context(patch.object(broker, "_production_key_provider", return_value=_KeyProvider()))
        self.outputs: list[str] = []

    # -- helpers -----------------------------------------------------------

    def run_cli(self, *args: str) -> tuple[int, dict]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = archive_cli.main([*args, "--no-progress", "--format", "json"])
        self.outputs.extend((out.getvalue(), err.getvalue()))
        self.assertEqual(err.getvalue(), "")
        return code, json.loads(out.getvalue())

    def chain_args(self) -> list[str]:
        return [
            "source-intake-chain", str(self.root),
            "--source-intake-plan", str(self.plan_path),
            "--staged-path", STAGED_RELATIVE,
        ]

    def snapshot(self) -> dict[str, bytes]:
        return {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in sorted(self.root.rglob("*"))
            if path.is_file()
        }

    def assert_private_free(self) -> None:
        rendered = "".join(self.outputs) + json.dumps(self.native.contexts, ensure_ascii=False)
        for marker in (PRIVATE_NAME, PRIVATE_BODY.strip(), str(self.root), str(self.workspace)):
            self.assertNotIn(marker, rendered)
        self.assertNotIn(REVIEWER, "".join(self.outputs))

    # -- tests -------------------------------------------------------------

    def test_dry_run_plans_three_steps_from_projected_bytes_without_writing(self) -> None:
        before = self.snapshot()
        code, preview = self.run_cli(*self.chain_args(), "--dry-run")
        self.assertEqual(code, 0, preview)
        self.assertEqual(preview["state"], "ready_for_exact_human_approval")
        self.assertEqual(preview["write_status"], "would_write")
        self.assertEqual([step["step"] for step in preview["steps"]], list(chain.STEP_NAMES))
        self.assertTrue(all(step["state"] == "ready" for step in preview["steps"]))
        self.assertEqual(preview["approval_count"], 1)
        self.assertEqual(preview["single_step_approval_count"], 3)
        self.assertTrue(preview["chain_id"].startswith("source-intake-chain:"))
        self.assertTrue(preview["receipt_path"].startswith(chain.CHAIN_RECEIPTS_DIR + "/"))
        self.assertTrue(preview["steps"][0]["output_path"].startswith("receipts/sources/"))
        self.assertTrue(preview["steps"][1]["output_path"].startswith("receipts/objet-capture-selections/"))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.native.calls, 0)
        # the same plan digest is produced again from the unchanged tree
        code, again = self.run_cli(*self.chain_args(), "--dry-run")
        self.assertEqual(again["plan_sha256"], preview["plan_sha256"])
        self.assertEqual(again["target_binding_sha256"], preview["target_binding_sha256"])
        self.assert_private_free()

    def test_one_dialog_writes_record_selection_and_capture(self) -> None:
        code, preview = self.run_cli(*self.chain_args(), "--dry-run")
        self.assertEqual(code, 0, preview)
        code, result = self.run_cli(
            *self.chain_args(), "--approve", "--reviewed-by", REVIEWER,
            "--expected-plan-sha256", preview["plan_sha256"],
        )
        self.assertEqual(code, 0, result)
        self.assertEqual(result["state"], "completed")
        self.assertTrue(result["ok"])
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(result["approval_count"], 1)
        self.assertEqual(result["steps_written"], 3)
        self.assertEqual([step["state"] for step in result["steps"]], ["written"] * 3)
        self.assertEqual(result["plan_sha256"], preview["plan_sha256"])
        self.assertTrue(result["general_intake_chain_complete"])
        self.assertEqual(result["exact_human_approval"]["status"], "succeeded")
        # every written artifact exists and the record/selection bytes are the projected ones
        record_path = self.root / result["steps"][0]["output_path"]
        selection_path = self.root / result["steps"][1]["output_path"]
        capture_receipt = self.root / result["steps"][2]["output_path"]
        chain_receipt = self.root / result["receipt_path"]
        for path in (record_path, selection_path, capture_receipt, chain_receipt):
            self.assertTrue(path.is_file(), path)
        self.assertEqual(result["steps"][0]["output_path"], preview["steps"][0]["output_path"])
        self.assertEqual(result["steps"][1]["output_path"], preview["steps"][1]["output_path"])
        self.assertIn(result["receipt_path"], result["files_written"])
        for path in (result["steps"][0]["output_path"], result["steps"][1]["output_path"]):
            self.assertIn(path, result["files_written"])
        # the captured bytes are content-addressed under objects/
        capture_step = result["steps"][2]
        self.assertEqual(capture_step["summary"]["captured"], 1)
        object_relative = f"objects/sha256/{preview['staged_bytes_sha256'][7:9]}/{preview['staged_bytes_sha256'][7:]}"
        self.assertEqual((self.root / object_relative).read_bytes(), PRIVATE_BODY.encode("utf-8"))
        # the chain receipt records the one approval and each step's binding
        receipt = json.loads(chain_receipt.read_text(encoding="utf-8"))
        self.assertEqual(receipt["schema_version"], chain.RECEIPT_SCHEMA)
        self.assertEqual(receipt["state"], "completed")
        self.assertEqual(receipt["exact_human_approval"]["operation"], "source_intake_chain")
        self.assertEqual([step["step"] for step in receipt["steps"]], list(chain.STEP_NAMES))
        self.assertTrue(all(step["approval_plan_sha256"] for step in receipt["steps"]))
        # the exact-operation final receipts bind the chain claim's approval id
        approval_id = result["exact_human_approval"]["approval_id"]
        capture_document = json.loads(capture_receipt.read_text(encoding="utf-8"))
        capture_approval = capture_document["exact_human_approval"]
        self.assertEqual(capture_approval["operation"], "source_intake_chain")
        self.assertEqual(capture_approval["exact_human_approval"]["approval_id"], approval_id)
        self.assertEqual(capture_approval["batch_item_binding"]["match"], "exact")
        self.assertEqual(receipt["exact_human_approval"]["exact_human_approval"]["approval_id"], approval_id)
        # the same chain cannot be replayed: the record now exists
        code, replay = self.run_cli(*self.chain_args(), "--dry-run")
        self.assertEqual(code, 1, replay)
        self.assertEqual(replay["state"], "blocked")
        self.assertEqual(replay["steps"][0]["state"], "blocked")
        self.assertEqual(self.native.calls, 1)
        self.assert_private_free()

    def test_cancel_and_missing_reviewer_write_nothing(self) -> None:
        before = self.snapshot()
        self.native.approve = False
        code, cancelled = self.run_cli(*self.chain_args(), "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1, cancelled)
        self.assertEqual(cancelled["blockers"], ["exact_human_approval_cancelled"])
        self.assertFalse(cancelled["writes_performed"])
        self.assertEqual(self.native.calls, 1)
        code, missing = self.run_cli(*self.chain_args(), "--approve")
        self.assertEqual(code, 1, missing)
        self.assertEqual(missing["blockers"], ["source_intake_chain_approval_required"])
        code, conflict = self.run_cli(*self.chain_args(), "--dry-run", "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1, conflict)
        self.assertIn("capability_mode_conflicting", conflict["reason_codes"])
        code, dry_reviewer = self.run_cli(*self.chain_args(), "--dry-run", "--reviewed-by", REVIEWER)
        self.assertEqual(dry_reviewer["blockers"], ["source_intake_chain_request_invalid"])
        code, mismatch = self.run_cli(
            *self.chain_args(), "--approve", "--reviewed-by", REVIEWER,
            "--expected-plan-sha256", "sha256:" + "0" * 64,
        )
        self.assertEqual(mismatch["blockers"], ["source_intake_chain_plan_digest_mismatch"])
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.snapshot(), before)
        self.assert_private_free()

    def test_chain_plan_blocks_before_any_write_when_a_later_step_cannot_run(self) -> None:
        # A stale archive index blocks the capture apply; the chain must say so
        # in the dry-run instead of writing the record and selection first.
        (self.root / "zettels" / "zet-synthetic-stale-index.md").write_text(
            "---\nid: zet-synthetic-stale-index\ntitle: stale\n---\n\nbody\n", encoding="utf-8"
        )
        with patch.object(
            archive_services, "require_archive_manifest_index_mutation_authority",
            side_effect=archive_services.ArchiveServiceError(archive_services.INDEX_REBUILD_REQUIRED),
        ):
            before = self.snapshot()
            code, preview = self.run_cli(*self.chain_args(), "--dry-run")
            self.assertEqual(code, 1, preview)
            self.assertEqual(preview["blockers"], ["source_intake_chain_plan_blocked"])
            self.assertEqual(preview["steps"][0]["state"], "ready")
            self.assertEqual(preview["steps"][1]["state"], "ready")
            self.assertEqual(preview["steps"][2]["state"], "blocked")
            self.assertEqual(preview["steps"][2]["blockers"], [archive_services.INDEX_REBUILD_REQUIRED])
            self.assertIsNone(preview["plan_sha256"])
            code, approve = self.run_cli(*self.chain_args(), "--approve", "--reviewed-by", REVIEWER)
            self.assertEqual(code, 1, approve)
            self.assertEqual(approve["blockers"], ["source_intake_chain_plan_blocked"])
            self.assertEqual(self.native.calls, 0)
            self.assertEqual(self.snapshot(), before)
        self.assert_private_free()

    def test_step_failure_after_earlier_writes_is_reported_partial(self) -> None:
        original = archive_services.objet_capture_apply

        def failing_capture(*args, **kwargs):
            raise archive_services.ArchiveServiceError("synthetic_capture_failure")

        with patch.object(archive_services, "objet_capture_apply", side_effect=failing_capture):
            code, result = self.run_cli(*self.chain_args(), "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1, result)
        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "partial")
        self.assertEqual([step["state"] for step in result["steps"]], ["written", "written", "failed"])
        self.assertEqual(result["steps_written"], 2)
        self.assertTrue((self.root / result["steps"][0]["output_path"]).is_file())
        self.assertTrue((self.root / result["steps"][1]["output_path"]).is_file())
        self.assertTrue(result["next_safe_actions"])
        self.assertIn(result["steps"][1]["output_path"], result["next_safe_actions"][0])
        self.assertEqual(result["exact_human_approval_reconciliation"]["required"], True)
        receipt = json.loads((self.root / result["receipt_path"]).read_text(encoding="utf-8"))
        self.assertEqual(receipt["state"], "partial")
        # the written selection is a valid standalone input for the single-step capture
        preview = archive_services.objet_capture_exact_dry_run(
            self.root, Path(result["steps"][1]["output_path"])
        )
        self.assertTrue(preview["ok"], preview)
        self.assertIs(archive_services.objet_capture_apply, original)
        self.assert_private_free()

    def test_capture_durable_writes_are_listed_when_the_capture_reports_failure(self) -> None:
        # The capture writer publishes the object bytes and its always-written
        # receipt before the manifest append; when that append fails it reports
        # ok:false, and the chain must still list those durable writes.
        with patch.object(archive_services, "_append_jsonl_records_outcome_aware", return_value="not_written"):
            code, result = self.run_cli(*self.chain_args(), "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1, result)
        self.assertEqual(result["state"], "partial")
        self.assertEqual([step["state"] for step in result["steps"]], ["written", "written", "failed"])
        capture = result["steps"][2]
        self.assertIn("manifest_append_failed", capture["reason_codes"])
        self.assertTrue(capture["receipt_path"].startswith("receipts/objet-capture/"))
        self.assertEqual(capture["output_path"], capture["receipt_path"])
        self.assertIn(capture["receipt_path"], result["files_written"])
        object_relative = (
            f"objects/sha256/{result['staged_bytes_sha256'][7:9]}/{result['staged_bytes_sha256'][7:]}"
        )
        self.assertIn(object_relative, capture["files_written"])
        self.assertIn(object_relative, result["files_written"])
        self.assertTrue((self.root / object_relative).is_file())
        self.assertTrue(result["receipt_written"])
        receipt = json.loads((self.root / result["receipt_path"]).read_text(encoding="utf-8"))
        self.assertEqual(receipt["steps"][2]["receipt_path"], capture["receipt_path"])
        self.assertIn(object_relative, receipt["steps"][2]["files_written"])
        self.assert_private_free()

    def test_first_step_failure_writes_nothing_and_no_chain_receipt(self) -> None:
        before = self.snapshot()
        with patch.object(
            source_intake_record_exact, "execute_source_intake_record_in_chain",
            side_effect=source_intake_record_exact.SourceIntakeRecordExactError("source_intake_record_write_failed"),
        ):
            code, result = self.run_cli(*self.chain_args(), "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1, result)
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["steps_written"], 0)
        self.assertEqual(result["files_written"], [])
        self.assertIsNone(result["receipt_path"])
        self.assertFalse(result["receipt_written"])
        self.assertFalse(result["writes_performed"])
        self.assertIn("Nothing was written", result["next_safe_actions"][0])
        # only the approval broker's own private claim ledger changed; no
        # receipt, selection, object or chain receipt was written
        after = self.snapshot()
        ledger = "profiles/local/exact-human-approvals/"
        self.assertEqual({k: v for k, v in after.items() if not k.startswith(ledger)},
                         {k: v for k, v in before.items() if not k.startswith(ledger)})
        self.assertEqual(self.native.calls, 1)
        self.assert_private_free()

    def test_step_writers_refuse_a_foreign_or_missing_chain_authority(self) -> None:
        plan = chain.plan_source_intake_chain(self.root, self.plan_path, staged_path=STAGED_RELATIVE)
        self.assertTrue(plan.approveable)
        with self.assertRaises(source_intake_record_exact.SourceIntakeRecordExactError) as record_error:
            source_intake_record_exact.execute_source_intake_record_in_chain(
                plan.record, claim=object(), chain_authority=object()
            )
        self.assertEqual(record_error.exception.code, "source_intake_record_approval_required")
        with self.assertRaises(
            objet_capture_selection_exact.ExistingIntakeCaptureSelectionError
        ) as selection_error:
            objet_capture_selection_exact.execute_existing_intake_capture_selection_in_chain(
                plan.selection, claim=object(), chain_authority=object()
            )
        self.assertEqual(
            selection_error.exception.code,
            "existing_intake_capture_selection_approval_required",
        )
        blocked = archive_services.objet_capture_apply(
            self.root, Path("receipts/objet-capture-selections/missing.selection.json"),
            reviewed_by=REVIEWER, batch_authority=object(),
        )
        self.assertFalse(blocked["ok"])
        self.assertEqual(self.native.calls, 0)
        self.assertFalse((self.root / str(plan.record.receipt_relative_path)).exists())

    def test_inventory_reports_the_chain_available_and_help_names_one_approval(self) -> None:
        rows = {row["canonical_path"]: row for row in archive_cli._parser_capability_inventory(
            archive_cli.build_parser())["commands"]}
        self.assertEqual(rows["source-intake-chain"]["approval_status"], command_status.APPROVAL_AVAILABLE)
        out = io.StringIO()
        with redirect_stdout(out):
            try:
                code = archive_cli.main(["source-intake-chain", "--help"])
            except SystemExit as exit_request:
                code = exit_request.code
        self.assertEqual(code, 0)
        self.assertIn("one native exact human approval", out.getvalue())
        self.assertIn(
            windows.ExactHumanApprovalOperation.source_intake_chain,
            windows._OPERATION_APPROVE_BUTTONS,
        )


if __name__ == "__main__":
    unittest.main()
