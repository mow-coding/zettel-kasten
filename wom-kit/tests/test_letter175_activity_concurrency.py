"""A remains inside remote PUT while B searches, captures and links another objet."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import threading
import unittest
from unittest.mock import patch

from wom_kit import archive_services as services, search_snapshots
from wom_kit import source_intake_batch_exact as intake, objet_capture_batch_exact as capture
from wom_kit import completion_workflows as links, operation_approval_binding as bindings
from wom_kit.exact_human_approval import _claim_exact_human_approval_core
from wom_kit.exact_human_approval_windows import _ExactHumanApprovalDecision
from . import test_activity_cleanup as activity_fixture
from . import test_v0410_source_intake_batch_exact as intake_fixture


@unittest.skipUnless(os.name == "nt", "native activity cleanup")
class ActivityConcurrencyTests(unittest.TestCase):
    setUp = activity_fixture.ActivityCleanupTests.setUp

    def test_other_work_finishes_inside_activity_remote_transfer(self):
        entered, completed = threading.Event(), threading.Event()
        findings = {}
        source_b = self.base / "other-session-source.txt"
        source_b.write_bytes(b"synthetic B source unrelated to activity A")
        before = source_b.read_bytes(), source_b.stat().st_mtime_ns
        request_b = self.base / "other-intake.json"
        request_b.write_text(json.dumps({"schema": intake.REQUEST_SCHEMA, "batch_id": "other-session",
            "items": [{"item_id": "other", "local_path": str(source_b), "source_role": "primary_source"}]}), encoding="utf-8")

        def independent_work():
            self.assertTrue(entered.is_set())
            findings["search"] = search_snapshots.search(self.root, "fake", limit=100)
            plan = intake.plan_source_intake_batch(self.root, request_b, stage_external=True)
            workflow = intake_fixture.SourceIntakeBatchExactTests._workflow(intake_fixture._Native(), self.key)
            with patch.object(intake, "_execute_exact_human_approved_write", side_effect=workflow):
                findings["intake"] = intake.execute_source_intake_batch(plan, reviewer_claim="person:synthetic")
            self.assertTrue(findings["intake"]["ok"], findings["intake"])
            capture_plan = capture.plan_objet_capture_batch(self.root,
                intake_execution_sha256=findings["intake"]["execution_sha256"], claim_key_provider=self.key)
            with patch.object(capture, "_execute_exact_human_approved_write", side_effect=workflow):
                findings["capture"] = capture.execute_objet_capture_batch(capture_plan, reviewer_claim="person:synthetic")
            self.assertTrue(findings["capture"]["ok"], findings["capture"])
            oid = "sha256:" + hashlib.sha256(before[0]).hexdigest()
            link_args = dict(zettel_id="zet_20240504_fake_lunch_thought", object_id=oid, role="evidence")
            plan = links.zettel_objet_link_plan(self.root, **link_args)
            self.assertTrue(plan["ok"], plan)
            binding = bindings.zettel_objet_link_approval_binding(plan)
            context = binding.context(archive_id=services.read_archive_id(self.root), reviewer_claim="person:synthetic")
            claim = _claim_exact_human_approval_core(self.root, context,
                _ExactHumanApprovalDecision(approved=True, synthetic_acknowledged=False,
                    reason_code="exact_human_approval_approved", plan_sha256=context.plan_sha256,
                    target_binding_sha256=context.target_binding_sha256), bytearray(range(32)))
            try:
                findings["link"] = links.zettel_objet_link_apply(self.root, **link_args,
                    expected_plan_sha256=plan["summary"]["plan_sha256"], reviewed_by="person:synthetic",
                    expected_exact_approval_plan_sha256=binding.plan_sha256,
                    expected_exact_approval_target_binding_sha256=binding.target_binding_sha256,
                    exact_human_approval_claim=claim)
                self.assertTrue(findings["link"]["ok"], findings["link"])
                claim.finalize_succeeded()
            finally:
                claim.close()
            self.assertEqual((source_b.read_bytes(), source_b.stat().st_mtime_ns), before)
            completed.set()

        def paused_remote_transfer():
            entered.set()
            with ThreadPoolExecutor(max_workers=1) as worker:
                worker.submit(independent_work).result(timeout=25)
            self.assertTrue(completed.is_set(), "B must finish before A's PUT returns")

        self.during_first_put = paused_remote_transfer
        activity_fixture.ActivityCleanupTests.test_official_intake_upload_offload_external_cleanup_pipeline(self)
        self.assertTrue(completed.is_set())
