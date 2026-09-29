"""Synthetic lifecycle tests; no customer archive or native approval window."""
import copy
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from wom_kit import draft_disposition as module


class Claim:
    def assert_ready_for_context(self, context):
        return {"schema": "synthetic-approval", "context": context}


class DraftDispositionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="wom-draft-disposition-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        shutil.copytree(Path(__file__).parents[1] / "examples/fake-life-archive", self.root)
        self.path = self.root / "inbox/zet_20260928_synthetic_hold.md"
        self.path.write_text("---\nid: zet_20260928_synthetic_hold\nstatus: draft\ntitle: Synthetic hold\n---\nUnpublished synthetic body.\n", encoding="utf-8")
        self.request = {"schema": module.REQUEST_SCHEMA, "action": "hold", "zettel_id": "zet_20260928_synthetic_hold",
            "reason": "Wait for the source comparison.", "intended_next_action": "discard",
            "conditions": [{"condition_id": "source_checked", "description": "Compare the preserved source.", "state": "unmet"}]}
        self.addCleanup(patch.stopall)
        patch.object(module, "_ClaimedExactHumanApproval", Claim).start()
        # Test domain CAS/append/replay independently from the existing broker.
        patch.object(module, "_context", side_effect=lambda value, reviewer: module._sha(module._canonical(value))).start()

    def apply(self, request=None):
        value = request or self.request
        plan = module.plan(self.root, value)
        return module.apply(self.root, value, expected_plan_sha256=plan["plan_sha256"],
                            reviewer_claim="person:synthetic-reviewer", approval_claim=Claim())

    def test_plan_and_inspection_never_create_files_or_modify_draft(self):
        before = {str(path.relative_to(self.root)) for path in self.root.rglob("*")}
        self.assertEqual(module.inspect(self.root, zettel_id=self.request["zettel_id"])["state"], "unrecorded")
        self.assertEqual(module.plan(self.root, self.request)["condition_count"], 1)
        self.assertEqual(before, {str(path.relative_to(self.root)) for path in self.root.rglob("*")})

    def test_invalid_request_types_are_fixed_domain_errors(self):
        for field in ("action", "intended_next_action", "zettel_id", "expected_previous_event_sha256"):
            value = copy.deepcopy(self.request)
            value[field] = ["synthetic-private-value"]
            with self.subTest(field=field), self.assertRaises(module.services.ArchiveServiceError) as caught:
                module.plan(self.root, value)
            self.assertNotIn("synthetic-private-value", str(caught.exception))
        for field in ("condition_id", "state"):
            value = copy.deepcopy(self.request)
            value["conditions"][0][field] = ["synthetic-private-value"]
            with self.subTest(field=field), self.assertRaisesRegex(module.services.ArchiveServiceError, "^draft_disposition_conditions_invalid$"):
                module.plan(self.root, value)

    def test_workflow_guidance_is_lightweight_without_history_and_uses_official_selectors(self):
        before = {str(path.relative_to(self.root)) for path in self.root.rglob("*")}
        with patch.object(module, "_target", side_effect=AssertionError("unrecorded helper read draft bytes")):
            result = module.workflow_guidance(self.root, zettel_id=self.request["zettel_id"])
        self.assertEqual(result["disposition"]["state"], "unrecorded")
        self.assertEqual(before, {str(path.relative_to(self.root)) for path in self.root.rglob("*")})
        actions = {item["action"]: item for item in result["next_actions"]}
        self.assertEqual(actions["revise_plan"]["selector_argument"], "--draft")
        self.assertEqual(actions["quality_check"]["selector_argument"], "--zettel-id")
        self.assertEqual(actions["publish_plan"]["command"], "mint-zet")
        self.assertIn("--reason", actions["discard_plan"]["required_arguments"])
        self.assertIn("--history", actions["hold_history"]["required_arguments"])
        self.assertFalse(result["conditions_are_publish_authority"])
        self.assertFalse(result["conditions_are_delete_authority"])

    def test_workflow_guidance_preserves_history_and_reports_corruption_without_throwing(self):
        self.apply()
        self.path.unlink()
        result = module.workflow_guidance(self.root, zettel_id=self.request["zettel_id"])
        self.assertEqual(result["disposition"]["state"], "draft_not_currently_resolved_history_retained")
        self.assertFalse(result["disposition"]["final_disposition_inferred"])
        event = module._folder(self.root, self.request["zettel_id"]) / "00000001.json"
        event.write_text("{synthetic-private-corruption", encoding="utf-8")
        result = module.workflow_guidance(self.root, zettel_id=self.request["zettel_id"])
        self.assertFalse(result["ok"])
        self.assertEqual(result["disposition"]["state"], "status_unavailable")
        self.assertTrue(result["workflow_result_is_unchanged"])
        self.assertNotIn("synthetic-private-corruption", str(result))

    def test_hold_review_release_append_without_deletion(self):
        original = self.path.read_bytes()
        held = self.apply()
        review = copy.deepcopy(self.request)
        review["action"] = "review"
        review["conditions"][0].update(state="met", evidence_ref="receipt:synthetic-source-comparison")
        review["expected_previous_event_sha256"] = held["event_sha256"]
        self.assertEqual(self.apply(review)["state"], "ready_for_review")
        release = copy.deepcopy(review)
        release.pop("expected_previous_event_sha256")
        release["action"] = "release"
        self.assertEqual(self.apply(release)["state"], "released")
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(module.inspect(self.root, zettel_id=self.request["zettel_id"])["event_count"], 3)

    def test_resumed_completed_event_is_not_appended_twice(self):
        original_context = module.approval_context(self.root, self.request, reviewer_claim="person:synthetic-reviewer")
        result = self.apply()
        self.assertEqual(module.approval_context(self.root, self.request,
            reviewer_claim="person:synthetic-reviewer", expected_plan_sha256=result["plan_sha256"], resume=True), original_context)
        again = module.apply(self.root, self.request, expected_plan_sha256=result["plan_sha256"],
                             reviewer_claim="person:synthetic-reviewer", approval_claim=Claim(), resume=True)
        self.assertTrue(again["resumed"])
        self.assertEqual(again["event_sha256"], result["event_sha256"])
        self.assertEqual(module.inspect(self.root, zettel_id=self.request["zettel_id"])["event_count"], 1)

    def test_changed_draft_rejects_old_plan_and_exposes_review_required(self):
        self.apply()
        request = {**self.request, "action": "review"}
        plan = module.plan(self.root, request)
        self.path.write_bytes(self.path.read_bytes() + b"Changed body.\n")
        with self.assertRaisesRegex(Exception, "draft_disposition_plan_changed"):
            module.apply(self.root, request, expected_plan_sha256=plan["plan_sha256"],
                         reviewer_claim="person:synthetic-reviewer", approval_claim=Claim())
        self.assertEqual(module.inspect(self.root, zettel_id=self.request["zettel_id"])["state"], "review_required_draft_changed")

    def test_met_condition_needs_evidence_and_unknown_fields_rejected(self):
        value = copy.deepcopy(self.request)
        value["conditions"][0]["state"] = "met"
        with self.assertRaisesRegex(Exception, "draft_disposition_met_condition_evidence_required"):
            module.plan(self.root, value)
        with self.assertRaisesRegex(Exception, "draft_disposition_request_invalid"):
            module.plan(self.root, {**self.request, "delete_when_met": True})

    def test_unbound_writer_rejected_before_write(self):
        with self.assertRaisesRegex(Exception, "draft_disposition_exact_approval_required"):
            module.apply(self.root, self.request, expected_plan_sha256="invalid", reviewer_claim="synthetic", approval_claim=None)


    def test_history_survives_separate_mint_and_completed_resume_is_noop(self):
        event = self.apply()
        destination = self.root / "zettels" / self.path.name
        self.path.rename(destination)
        detail = module.history(self.root, zettel_id=self.request["zettel_id"])
        self.assertEqual(detail["event_count"], 1)
        status = module.inspect(self.root, zettel_id=self.request["zettel_id"])
        self.assertEqual(status["state"], "draft_not_currently_resolved_history_retained")
        self.assertFalse(status["final_disposition_inferred"])
        resumed = module.apply(self.root, self.request, expected_plan_sha256=event["plan_sha256"],
            reviewer_claim="person:synthetic-reviewer", approval_claim=Claim(), resume=True)
        self.assertTrue(resumed["resumed"])
        self.assertTrue(destination.exists())


if __name__ == "__main__":
    unittest.main()
