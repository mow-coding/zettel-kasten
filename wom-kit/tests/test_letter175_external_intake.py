"""Official external intake; synthetic files only."""
import json
import hashlib
import unittest
from unittest.mock import patch

from wom_kit import source_intake_batch_exact as intake, source_intake_external as external
from wom_kit import objet_capture_batch_exact as capture, archive_services as services
from . import test_v0410_source_intake_batch_exact as fixture
from . import test_v0420_source_intake_session_public_workflow as scoped_fixture


class ExternalIntakeTests(unittest.TestCase):
    setUp = fixture.SourceIntakeBatchExactTests.setUp
    tearDown = fixture.SourceIntakeBatchExactTests.tearDown

    def request(self):
        original = self.workspace / "original synthetic attachment.txt"
        original.write_bytes(b"synthetic source body\n")
        self.request_path.write_text(json.dumps({"schema": intake.REQUEST_SCHEMA, "batch_id": "external-test",
            "items": [{"item_id": "attachment", "local_path": str(original), "source_role": "primary_source"}]}), encoding="utf-8")
        return original

    def test_external_copy_and_authenticated_capture_preserve_original(self):
        original = self.request()
        before = (original.read_bytes(), original.stat().st_mtime_ns)
        self.assertFalse(intake.plan_source_intake_batch(self.root, self.request_path).approveable)
        plan = intake.plan_source_intake_batch(self.root, self.request_path, stage_external=True)
        self.assertTrue(plan.approveable, plan.public_document())
        self.assertEqual(plan.manifest.operation_evidence.schema, external.SCHEMA)
        self.assertFalse((self.root / plan.items[0].capture_staged_path).exists())
        native, key = fixture._Native(), fixture._KeyProvider()
        workflow = fixture.SourceIntakeBatchExactTests._workflow(native, key)
        with patch.object(intake, "_execute_exact_human_approved_write", side_effect=workflow):
            result = intake.execute_source_intake_batch(plan, reviewer_claim=fixture.REVIEWER)
        self.assertTrue(result["ok"], result)
        self.assertEqual((original.read_bytes(), original.stat().st_mtime_ns), before)
        self.assertEqual((self.root / plan.items[0].capture_staged_path).read_bytes(), before[0])
        services.index_archive(self.root)
        captured = capture.plan_objet_capture_batch(self.root,
            intake_execution_sha256=result["execution_sha256"], claim_key_provider=key)
        self.assertTrue(captured.approveable, captured.public_document())
        from wom_kit import exact_human_approval_workflow as broker
        with patch.object(capture, "_execute_exact_human_approved_write", side_effect=workflow), \
                patch.object(broker, "_production_key_provider", return_value=key):
            written = capture.execute_objet_capture_batch(captured, reviewer_claim=fixture.REVIEWER)
        self.assertTrue(written["ok"], written)
        oid = "sha256:" + hashlib.sha256(before[0]).hexdigest()
        self.assertTrue(any(row.get("object_id") == oid for row in services.load_manifest_records(self.root)))
        self.assertEqual((original.read_bytes(), original.stat().st_mtime_ns), before)

    def test_partial_copy_resumes_matching_prefix_and_rejects_foreign_residue(self):
        original = self.request()
        plan = intake.plan_source_intake_batch(self.root, self.request_path, stage_external=True)
        item = plan.items[0]
        target = self.root / item.capture_staged_path
        target.parent.mkdir(parents=True)
        partial = target.with_suffix(".copying")
        partial.write_bytes(b"foreign")
        with self.assertRaises(intake.SourceIntakeBatchExactError):
            external.copy_approved(plan, item, heartbeat=lambda: None)
        self.assertEqual(partial.read_bytes(), b"foreign")
        partial.write_bytes(original.read_bytes()[:7])
        external.copy_approved(plan, item, heartbeat=lambda: None)
        self.assertEqual(target.read_bytes(), original.read_bytes())
        self.assertFalse(partial.exists())


class ScopedExternalIntakeTests(unittest.TestCase):
    setUp = scoped_fixture.PublicSessionSourceIntakeJourneyTests.setUp
    call = scoped_fixture.PublicSessionSourceIntakeJourneyTests.call
    session_command = scoped_fixture.PublicSessionSourceIntakeJourneyTests.session_command

    def test_public_scoped_external_copy_and_original_resume(self):
        source = self.fixture.workspace / "external-original.txt"
        source.write_bytes(b"synthetic external scoped body")
        self.request.write_text(json.dumps({"schema": intake.REQUEST_SCHEMA, "batch_id": "scoped-external",
            "items": [{"item_id": "source", "local_path": str(source), "source_role": "primary_source"}]}), encoding="utf-8")
        before = (source.read_bytes(), source.stat().st_mtime_ns)
        common = (*self.refs, "--work-session-ref", self.session)
        preview = self.call("source-intake-batch", *common, "--manifest", str(self.request), "--stage-external", "--dry-run")
        self.assertTrue(preview["ok"])
        written = self.call("source-intake-batch", *common, "--manifest", str(self.request), "--stage-external",
                            "--approve", "--reviewed-by", "person:synthetic-intake-reviewer")
        self.assertTrue(written["ok"])
        resumed = self.call("source-intake-batch", *common, "--resume")
        self.assertTrue(resumed["ok"])
        self.assertEqual((source.read_bytes(), source.stat().st_mtime_ns), before)
