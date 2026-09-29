"""Synthetic registration recovery through the real approval and capture paths."""
import io
import json
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest import mock

import test_v0410_objet_capture_batch_exact as fixtures
from wom_kit import archive_services as services
from wom_kit import objet_capture_batch_exact as batch
from wom_kit import objet_capture_recovery as recovery
from wom_kit import source_intake_batch_exact as intake
from wom_kit import exact_human_approval, exact_human_approval_workflow as workflow
from wom_kit import exact_human_approval_windows as windows
from wom_kit import archive_cli
from wom_kit.operation_cancellation import OperationCancelled

_Native, _KeyProvider, _ReadKeyProvider, REVIEWER = (
    fixtures._Native, fixtures._KeyProvider, fixtures._ReadKeyProvider, fixtures.REVIEWER)


class CaptureRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ObjetCaptureBatchExactTests()
        self.fixture.setUp()
        self.root = self.fixture.root
        self.native = _Native(approved=True)
        self.keys = _KeyProvider()

    def tearDown(self):
        self.fixture.tearDown()

    def plan(self, count=3, name="synthetic-recovery"):
        request, execution = self.fixture._request(count, batch_id=name)
        return self.fixture._plan(request, execution)

    def execute(self, plan):
        with mock.patch.object(batch, "_execute_exact_human_approved_write",
                               side_effect=self.fixture._workflow(self.native, self.keys)):
            return batch.execute_objet_capture_batch(plan, reviewer_claim=REVIEWER,
                                                     expected_plan_sha256=plan.batch_plan_sha256)

    def resume(self, result, **kwargs):
        return batch.resume_objet_capture_batch(self.root, reviewer_claim=REVIEWER,
            approval_id=result["recovery"]["approval_id"], execution_sha256=result["execution_sha256"],
            key_provider=_ReadKeyProvider(), **kwargs)

    def interrupted(self, plan):
        original = services._objet_capture_process_item
        calls = 0
        def stop(root, item, **kwargs):
            nonlocal calls
            if kwargs["approve"]:
                calls += 1
                if calls == 2:
                    raise recovery.CaptureRecoveryError("synthetic_capture_interrupted")
            return original(root, item, **kwargs)
        with mock.patch.object(services, "_objet_capture_process_item", side_effect=stop):
            result = self.execute(plan)
        self.assertFalse(result["ok"], result)
        self.assertTrue(result["same_claim_resume_supported"], result)
        self.assertEqual(result["exact_human_approval"]["status"], "started")
        return result

    def assert_once(self, plan):
        records = services.load_manifest_records(self.root)
        for item in plan.selection_document["items"]:
            self.assertEqual(sum(row.get("object_id") == item["approved_object_id"] for row in records), 1)

    def test_partial_bytes_resume_same_claim_without_second_dialog(self):
        plan = self.plan()
        first = self.interrupted(plan)
        self.assertEqual(first["cause_code"], "synthetic_capture_interrupted")
        result = self.resume(first)
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["recovery"]["resumed"])
        self.assertEqual(result["execution_sha256"], first["execution_sha256"])
        self.assertEqual(result["exact_human_approval"]["approval_id"], first["exact_human_approval"]["approval_id"])
        self.assertEqual(result["exact_human_approval"]["status"], "succeeded")
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(result["items"][0]["action"], "repair_appended")
        self.assert_once(plan)

    def test_twenty_one_prepared_items_resume_only_unfinished_registration(self):
        plan = self.plan(count=21, name="synthetic-twenty-one")
        self.assertEqual(len(plan.selection_document["items"]), 21)
        first = self.interrupted(plan)
        self.assertEqual(first["cause_code"], "synthetic_capture_interrupted")
        self.assertTrue(first["same_claim_resume_supported"])

        resumed = self.resume(first)
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(len(resumed["items"]), 21)
        self.assertEqual(resumed["execution_sha256"], first["execution_sha256"])
        self.assertEqual(resumed["exact_human_approval"]["approval_id"],
                         first["exact_human_approval"]["approval_id"])
        self.assertEqual(self.native.calls, 1)
        self.assert_once(plan)

    def test_twenty_one_external_sources_copy_then_resume_registration(self):
        originals = []
        items = []
        for index in range(21):
            original = self.fixture.workspace / f"external-original-{index:02d}.txt"
            original.write_bytes(f"synthetic external source {index}".encode())
            originals.append((original, original.read_bytes(), original.stat().st_mtime_ns))
            items.append({"item_id": f"external-{index:02d}", "local_path": str(original),
                          "source_role": "primary_source"})
        request = self.fixture.workspace / "external-twenty-one.json"
        request.write_text(json.dumps({"schema": intake.REQUEST_SCHEMA,
            "batch_id": "synthetic-external-twenty-one", "items": items}), encoding="utf-8")
        parser = archive_cli.build_parser()
        def invoke(command, arguments):
            args = parser.parse_args([command, str(self.root),
                "--format", "json", "--no-progress", *arguments])
            with redirect_stdout(output := io.StringIO()), redirect_stderr(io.StringIO()):
                code = args.func(args)
            return code, json.loads(output.getvalue())
        intake_args = ["--manifest", str(request), "--stage-external"]
        preview_code, preview = invoke("source-intake-batch", [*intake_args, "--dry-run"])
        self.assertEqual(preview_code, 0, preview)
        self.assertEqual(preview["item_count"], 21)
        intake_native = _Native(approved=True)
        with mock.patch.object(intake, "_execute_exact_human_approved_write",
                               side_effect=self.fixture._workflow(intake_native, self.keys)):
            prepared_code, prepared = invoke("source-intake-batch", [*intake_args,
                "--approve", "--reviewed-by", REVIEWER,
                "--expected-plan-sha256", preview["plan_sha256"]])
        self.assertEqual(prepared_code, 0, prepared)
        self.assertTrue(prepared["ok"], prepared)
        plan = batch.plan_objet_capture_batch(self.root,
            intake_execution_sha256=prepared["execution_sha256"],
            claim_key_provider=_ReadKeyProvider())
        self.assertTrue(plan.approveable, plan.public_document())
        self.assertEqual(len(plan.selection_document["items"]), 21)

        original = services._objet_capture_process_item
        calls = 0
        def stop(root, item, **kwargs):
            nonlocal calls
            if kwargs["approve"]:
                calls += 1
                if calls == 2:
                    raise recovery.CaptureRecoveryError("synthetic_capture_interrupted")
            return original(root, item, **kwargs)
        with (mock.patch.object(workflow, "_production_key_provider", return_value=_ReadKeyProvider()),
              mock.patch.object(batch, "_execute_exact_human_approved_write",
                                side_effect=self.fixture._workflow(self.native, self.keys))):
            with mock.patch.object(services, "_objet_capture_process_item", side_effect=stop):
                first_code, first = invoke("objet-capture-batch", ["--approve", "--reviewed-by", REVIEWER,
                    "--source-intake-execution-sha256", prepared["execution_sha256"],
                    "--expected-plan-sha256", plan.batch_plan_sha256])
            self.assertEqual(first_code, 1, first)
            self.assertEqual(first["cause_code"], "synthetic_capture_interrupted")
            self.assertEqual(first["recovery"]["origin_operation_ref"], first["operation_ref"])
            resumed_code, resumed = invoke("objet-capture-batch", ["--approve", "--resume", "--reviewed-by", REVIEWER,
                "--approval-id", first["recovery"]["approval_id"],
                "--execution-sha256", first["execution_sha256"]])
        self.assertEqual(resumed_code, 0, resumed)
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(resumed["recovery"]["origin_operation_ref"], first["operation_ref"])
        self.assertNotEqual(resumed["operation_ref"], first["operation_ref"])
        self.assertEqual(len(resumed["items"]), 21)
        self.assertEqual(intake_native.calls, 1)
        self.assertEqual(self.native.calls, 1)
        self.assert_once(plan)
        for original, before, mtime in originals:
            self.assertEqual((original.read_bytes(), original.stat().st_mtime_ns), (before, mtime))

        object_id = plan.selection_document["items"][0]["approved_object_id"]
        zettel = self.root / "zettels/zet_20240504_fake_lunch_thought.md"
        original_zettel = zettel.read_bytes()
        link_args = ["zettel-objet-link", str(self.root), "--path",
            zettel.relative_to(self.root).as_posix(), "--object-id", object_id,
            "--role", "source_document", "--format", "json"]
        def invoke_link(arguments):
            args = parser.parse_args([*link_args, *arguments])
            with redirect_stdout(output := io.StringIO()), redirect_stderr(io.StringIO()):
                code = args.func(args)
            return code, json.loads(output.getvalue())
        link_code, link_plan = invoke_link(["--dry-run"])
        self.assertEqual(link_code, 0, link_plan)
        with (mock.patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native),
              mock.patch.object(workflow, "_production_key_provider", return_value=self.keys)):
            link_code, linked = invoke_link(["--approve", "--reviewed-by", REVIEWER,
                "--expected-plan-sha256", link_plan["summary"]["plan_sha256"]])
        self.assertEqual(link_code, 0, linked)
        self.assertNotEqual(zettel.read_bytes(), original_zettel)
        self.assertIn(object_id.encode(), zettel.read_bytes())

        indexed = services.index_archive(self.root)
        self.assertTrue(indexed["ok"], indexed)
        with redirect_stdout(output := io.StringIO()), redirect_stderr(io.StringIO()):
            found_code = archive_cli.main(["search", str(self.root),
                object_id, "--type", "object", "--format", "json"])
        found = json.loads(output.getvalue())
        self.assertEqual(found_code, 0, found)
        self.assertIn(object_id, [item["id"] for item in found["results"]], found)

    def test_cancellation_after_first_item_preserves_receipt_and_resumes_remaining(self):
        plan = self.plan()
        completed = False
        original = services._objet_capture_process_item
        def processed(root, item, **kwargs):
            nonlocal completed
            result = original(root, item, **kwargs)
            if kwargs["approve"]:
                completed = True
            return result
        def checkpoint():
            if completed:
                raise OperationCancelled()
        with (mock.patch("wom_kit.operation_cancellation.checkpoint", side_effect=checkpoint),
              mock.patch.object(services, "_objet_capture_process_item", side_effect=processed)):
            first = self.execute(plan)
        self.assertFalse(first["ok"], first)
        self.assertIn("operation_cancelled_at_checkpoint", first["blockers"])
        self.assertEqual(first["cause_code"], "operation_cancelled_at_checkpoint")
        receipts = {path: path.read_bytes() for path in (self.root / "receipts/objet-capture").glob("*.json")}
        result = self.resume(first)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["items"][0]["action"], "skip_already_present")
        self.assertTrue(all(path.read_bytes() == raw for path, raw in receipts.items()))
        self.assert_once(plan)

    def test_prepared_request_drift_blocks_resume_before_writes(self):
        plan = self.plan()
        first = self.interrupted(plan)
        original = plan.request_path.read_bytes()
        document = json.loads(original)
        document["batch_id"] = "changed-scope"
        plan.request_path.write_text(json.dumps(document), encoding="utf-8")
        before = self.fixture._snapshot(self.root)
        with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
            self.resume(first)
        self.assertEqual(self.fixture._snapshot(self.root), before)
        plan.request_path.write_bytes(original)
        self.assertTrue(self.resume(first)["ok"])

    def test_changed_staged_bytes_never_register_under_old_approval(self):
        plan = self.plan()
        first = self.interrupted(plan)
        source = self.root / plan.selection_document["items"][1]["staged_path"]
        original = source.read_bytes()
        source.write_bytes(b"synthetic changed bytes")
        before = self.fixture._snapshot(self.root)
        with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
            self.resume(first)
        self.assertEqual(self.fixture._snapshot(self.root), before)
        source.write_bytes(original)
        self.assertTrue(self.resume(first)["ok"])

    def test_control_tampering_rejected_even_when_plan_still_valid(self):
        plan = self.plan()
        first = self.interrupted(plan)
        path = recovery._path(self.root, first["execution_sha256"])
        raw = path.read_bytes()
        value = json.loads(raw)
        value["document"]["origin_operation_ref"] = "tampered"
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
            self.resume(first)
        path.write_bytes(raw)
        self.assertTrue(self.resume(first)["ok"])

    def test_completed_claim_cannot_be_reused(self):
        result = self.execute(self.plan(1))
        self.assertTrue(result["ok"], result)
        with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
            self.resume(result)
        self.assertEqual(self.native.calls, 1)

    def test_registered_objects_reconciled_after_result_delivery_failure(self):
        plan = self.plan()
        save = recovery._save
        def stop(root, execution, document, claim, suffix="control"):
            if suffix == "result":
                raise recovery.CaptureRecoveryError("synthetic_result_not_recorded")
            return save(root, execution, document, claim, suffix)
        with mock.patch.object(recovery, "_save", side_effect=stop):
            first = self.execute(plan)
        self.assertFalse(first["ok"])
        self.assertEqual(first["state"], "evidence_incomplete")
        self.assertTrue(first["same_claim_resume_supported"])
        self.assert_once(plan)
        result = self.resume(first)
        self.assertTrue(result["ok"], result)
        self.assertTrue(all(item["action"] == "skip_already_present" for item in result["items"]))
        self.assert_once(plan)

    def test_signed_result_reconciles_checkpoint_failure_without_recapture(self):
        plan = self.plan()
        append = recovery.ExecutionCheckpointStore.append
        def stop(store, execution, checkpoint, **kwargs):
            if checkpoint["stage"] == "field_verified":
                raise recovery.CaptureRecoveryError("synthetic_checkpoint_write_failed")
            return append(store, execution, checkpoint, **kwargs)
        with mock.patch.object(recovery.ExecutionCheckpointStore, "append", stop):
            first = self.execute(plan)
        self.assertFalse(first["ok"])
        with mock.patch.object(services, "objet_capture_apply", side_effect=AssertionError("must reuse completion")):
            result = self.resume(first)
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["registration_completion_reused"])
        self.assertFalse(result["writes_performed"])
        self.assertEqual(result["files_written"], [])
        self.assert_once(plan)

    def test_checkpoint_tampering_rejected(self):
        plan = self.plan()
        first = self.interrupted(plan)
        execution = first["execution_sha256"][7:]
        candidates = list((self.root / "profiles/local").rglob(execution + "*.jsonl"))
        self.assertEqual(len(candidates), 1)
        candidates[0].write_bytes(candidates[0].read_bytes().replace(b'"stage":"started"', b'"stage":"item_verified"'))
        with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
            self.resume(first)

    def test_resume_rechecks_current_grant_for_session_authority(self):
        plan = self.plan()
        first = self.interrupted(plan)
        original = exact_human_approval._ClaimedExactHumanApproval.public_summary
        from wom_kit.exact_human_approval_windows import PERMISSION_INTERACTIVE_INTENT_MECHANISM
        def session(claim):
            value = original(claim)
            value["approval_mechanism"] = PERMISSION_INTERACTIVE_INTENT_MECHANISM
            return value
        with (mock.patch.object(exact_human_approval._ClaimedExactHumanApproval, "public_summary", session),
              mock.patch("wom_kit.work_session_permission.resolve_grant_outcome_from_environment",
                         return_value=(None, "work_session_grant_expired"))):
            before = self.fixture._snapshot(self.root)
            with self.assertRaises(workflow.ExactHumanApprovalWorkflowError) as raised:
                self.resume(first)
            self.assertEqual(raised.exception.cause_code, "work_session_grant_expired")
            self.assertEqual(self.fixture._snapshot(self.root), before)
        self.assertTrue(self.resume(first)["ok"])

    def test_public_cli_resume_links_new_journal_to_original_execution(self):
        plan = self.plan()
        parser = archive_cli.build_parser()
        def invoke(arguments):
            args = parser.parse_args(["objet-capture-batch", str(self.root), "--format", "json", "--no-progress", *arguments])
            with redirect_stdout(output := io.StringIO()), redirect_stderr(io.StringIO()):
                code = args.func(args)
            return code, json.loads(output.getvalue())
        with (mock.patch.object(workflow, "_production_key_provider", return_value=_ReadKeyProvider()),
              mock.patch.object(batch, "_execute_exact_human_approved_write",
                                side_effect=self.fixture._workflow(self.native, self.keys))):
            with mock.patch.object(services, "objet_capture_apply", side_effect=recovery.CaptureRecoveryError("synthetic_capture_interrupted")):
                code, first = invoke(["--approve", "--reviewed-by", REVIEWER,
                    "--source-intake-execution-sha256", plan.intake_execution_sha256,
                    "--expected-plan-sha256", plan.batch_plan_sha256])
            self.assertEqual(code, 1, first)
            self.assertEqual(first["recovery"]["origin_operation_ref"], first["operation_ref"])
            code, resumed = invoke(["--approve", "--resume", "--reviewed-by", REVIEWER,
                "--approval-id", first["recovery"]["approval_id"], "--execution-sha256", first["execution_sha256"]])
        self.assertEqual(code, 0, resumed)
        self.assertNotEqual(resumed["operation_ref"], first["operation_ref"])
        self.assertEqual(resumed["recovery"]["origin_operation_ref"], first["operation_ref"])
        self.assertEqual(resumed["recovery"]["current_operation_ref"], resumed["operation_ref"])
        self.assertEqual(resumed["execution_sha256"], first["execution_sha256"])
        self.assertEqual(self.native.calls, 1)
        self.assert_once(plan)

    def test_resume_finishes_claim_after_exact_final_receipt_was_written(self):
        plan = self.plan(1)
        with mock.patch.object(exact_human_approval._ClaimedExactHumanApproval, "finalize_succeeded",
                               side_effect=OSError("synthetic claim publication interruption")):
            first = self.execute(plan)
        self.assertFalse(first["ok"], first)
        self.assertTrue(first["recovery"]["requires_claim_state_validation"])
        with mock.patch.object(services, "objet_capture_apply", side_effect=AssertionError("completed effects must be reused")):
            result = self.resume(first)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["exact_human_approval"]["status"], "succeeded")
        self.assert_once(plan)


if __name__ == "__main__":
    unittest.main()
