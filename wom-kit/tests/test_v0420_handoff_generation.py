"""Complete read-only handoff summaries never recreate legacy approval."""

import copy
import io
import json
import tempfile
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from wom_kit import archive_cli, archive_services as services
import test_v0420_ai_artifact_pagination as artifact_fixtures


class HandoffGenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wom-handoff-generation-")
        self.addCleanup(self.temp.cleanup)
        self.fixture = artifact_fixtures.AiArtifactPaginationTests(methodName="runTest")
        self.root = self.fixture.archive(Path(self.temp.name))

    def context(self):
        stack = ExitStack()
        stack.enter_context(patch.object(services, "runtime_context_operational_context", return_value={"status": "present", "ok": True}))
        stack.enter_context(patch.object(services, "session_handoff_operational_context_evidence", return_value={
            "status": "receipt_verified", "record_sha256": "sha256:" + "a" * 64,
            "matching_receipt_ref": "receipts/operational-context/synthetic.operational-context.json",
            "receipt_hash_basis": "exact_utf8_bytes", "record_body_read": True,
        }))
        return stack

    def add_artifacts(self, count):
        for index in range(count):
            (self.root / ".wom-scratch/nested" / f"private-note-{index:05d}.txt").write_bytes(b"private ordinary body")

    def record_fates(self, count):
        receipt = self.fixture.receipt(self.root, ".wom-scratch/nested/private-note-00000.txt")
        data = json.loads(receipt.read_text(encoding="utf-8"))
        data["source_refs_for_draft"] = [
            {"type": "ai_artifact", "value": services.ai_artifact_ref_for_relative_path(f".wom-scratch/nested/private-note-{index:05d}.txt")}
            for index in range(count)
        ]
        receipt.write_text(json.dumps(data), encoding="utf-8")

    def test_original_v1_projection_and_canonical_bytes_are_unchanged(self):
        legacy = {
            "total_candidate_count": 1, "item_count": 1, "truncated": False,
            "skipped_non_plain_file_count": 0,
            "fate_counts": {"source_intake_recorded": 1},
            "artifact_kind_counts": {"ai_working_note": 1},
            "items": [{"artifact_ref": "ai-artifact:" + "a" * 24, "artifact_kind": "ai_working_note",
                       "fate_state": "source_intake_recorded", "bytes": 12, "modified_at": "2026-09-05T12:34:56+09:00"}],
        }
        before = json.dumps(legacy, sort_keys=True, separators=(",", ":")).encode()
        projected = services.session_handoff_inventory_snapshot(copy.deepcopy(legacy))
        self.assertEqual(json.dumps(projected, sort_keys=True, separators=(",", ":")).encode(), before)
        self.assertNotIn("schema", projected)
        self.assertNotIn("work_session_binding", projected)

    def test_ai_timestamp_keeps_original_same_host_local_offset_precision(self):
        self.add_artifacts(1)
        path = self.root / ".wom-scratch/nested/private-note-00000.txt"
        expected = datetime.fromtimestamp(path.stat().st_mtime).astimezone().replace(microsecond=0).isoformat()
        result = services.ai_artifact_inventory(self.root)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["items"][0]["modified_at"], expected)

    def test_full_projection_digest_is_independent_of_display_page(self):
        self.add_artifacts(5)
        first = services.ai_artifact_inventory(self.root, max_items=2)
        second = services.ai_artifact_inventory(self.root, max_items=2, cursor=first["pagination"]["next_cursor"])
        larger = services.ai_artifact_inventory(self.root, max_items=5)
        summaries = [services.session_handoff_inventory_snapshot(value, complete_generation=True) for value in (first, second, larger)]
        self.assertTrue(all(value["complete"] for value in summaries))
        self.assertEqual(len({services.sha256_json_value(value) for value in summaries}), 1)
        self.assertNotEqual(first["items"], second["items"])
        self.assertNotIn("items", summaries[0])
        self.assertEqual(summaries[0]["total_candidate_count"], 5)

    def test_single_collection_counts_last_unreviewed_artifact_beyond_1000(self):
        self.add_artifacts(1201)
        self.record_fates(1200)
        with self.context(), patch.object(services, "ai_artifact_inventory", wraps=services.ai_artifact_inventory) as inventory:
            result = services.session_handoff_checkpoint(self.root, dry_run=True, confirm_chat_reviewed=True)
        inventory.assert_called_once()
        evidence = result["ai_artifact_generation_diagnostic"]
        self.assertTrue(result["ok"], result)
        self.assertTrue(evidence["complete"])
        self.assertEqual(evidence["total_candidate_count"], 1201)
        self.assertEqual(evidence["unreviewed_count"], 1)
        self.assertEqual(evidence["rows_returned"], 1000)
        self.assertTrue(evidence["display_rows_truncated"])
        self.assertFalse(evidence["checkpoint_approval_uses_this_generation"])
        self.assertTrue(result["ai_artifact_inventory_evidence"]["truncated"])
        self.assertTrue(any("inventory is truncated" in gap for gap in result["durable_gaps"]))
        self.assertFalse(result["ready_for_context_reset"])
        self.assertRegex(result["state_digest"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(result["files_written"], [])

    def test_all_recorded_large_generation_is_diagnostic_not_new_approval(self):
        self.add_artifacts(1001)
        self.record_fates(1001)
        with self.context():
            result = services.session_handoff_checkpoint(self.root, dry_run=True, confirm_chat_reviewed=True)
        self.assertEqual(result["status"], "needs_durable_capture")
        self.assertTrue(any("inventory is truncated" in gap for gap in result["durable_gaps"]))
        self.assertNotIn("capability_state", result)
        self.assertFalse(result["ready_for_context_reset"])
        self.assertIsNone(result["expected_state_digest"])
        evidence = result["ai_artifact_generation_diagnostic"]
        self.assertTrue(evidence["complete"])
        self.assertEqual(evidence["total_candidate_count"], 1001)
        self.assertEqual(evidence["unreviewed_count"], 0)
        self.assertEqual(evidence["rows_returned"], 1000)
        self.assertTrue(evidence["diagnostic_only"])
        self.assertFalse(evidence["approval_authority"])
        self.assertEqual(evidence["complete_generation_writer_integration"], "pending_work_session_handoff")
        self.assertRegex(result["diagnostic_state_digest"], r"^sha256:[0-9a-f]{64}$")
        self.assertFalse(result["diagnostic_digest_is_authority"])
        self.assertFalse((self.root / "receipts/session-handoffs").exists())

    def test_incomplete_and_unknown_counts_never_turn_into_zero_or_ready(self):
        inventory = services.ai_artifact_inventory(self.root)
        mutations = (
            {"ok": False}, {"counts_complete": False}, {"total_candidate_count": None},
            {"fate_counts": None}, {"fate_counts": {"unreviewed_ai_artifact": True}},
            {"artifact_kind_counts": {"ai_working_note": -1}}, {"pagination": {}},
            {"pagination": {**inventory["pagination"], "total_count": False}},
            {"pagination": {**inventory["pagination"], "observed_count": False}},
            {"pagination": ["invalid"]},
        )
        for fields in mutations:
            with self.subTest(fields=tuple(fields)):
                incomplete = {**inventory, **fields}
                summary = services.session_handoff_inventory_snapshot(incomplete, complete_generation=True)
                self.assertFalse(summary["complete"])
                self.assertIsNone(summary["total_candidate_count"])
                with self.context(), patch.object(services, "ai_artifact_inventory", return_value=incomplete):
                    result = services.session_handoff_checkpoint(self.root, dry_run=True, confirm_chat_reviewed=True)
                self.assertFalse(result["ready_for_context_reset"])
                self.assertTrue(any("generation is incomplete" in gap for gap in result["durable_gaps"]))
                self.assertIsNone(result["ai_artifact_inventory_evidence"]["unreviewed_count"])
                evidence = result["ai_artifact_generation_diagnostic"]
                self.assertFalse(evidence["complete"])
                self.assertIsNone(evidence["unreviewed_count"])
                self.assertIsNone(evidence["fate_counts"])
                self.assertEqual(result["files_written"], [])

    def test_actual_legacy_receipt_is_only_legacy_scoped_proof_and_bytes_survive(self):
        self.add_artifacts(1)
        self.record_fates(1)
        old_inventory = services.session_handoff_inventory_snapshot(services.ai_artifact_inventory(self.root))
        old_inventory_digest = services.sha256_json_value(old_inventory)
        context_sha = "sha256:" + "a" * 64
        context_ref = "receipts/operational-context/synthetic.operational-context.json"
        old_state_digest = services.sha256_json_value({
            "operational_context_sha256": context_sha, "operational_context_receipt_ref": context_ref,
            "ai_artifact_inventory_digest": old_inventory_digest,
            "ai_artifact_total_candidate_count": old_inventory["total_candidate_count"],
            "ai_artifact_fate_counts": old_inventory["fate_counts"],
            "ai_artifact_inventory_truncated": old_inventory["truncated"],
        })
        receipt = {
            "schema": services.SESSION_HANDOFF_CHECKPOINT_SCHEMA,
            "lifecycle_action": "session_handoff_checkpoint_write", "archive_id": "archive:test",
            "state_digest": old_state_digest, "operational_context_sha256": context_sha,
            "operational_context_receipt_ref": context_ref, "ai_artifact_inventory_digest": old_inventory_digest,
            "confirmation": {"conversation_review_completed": True, "important_context_has_durable_home": True},
            "reviewed_by": "person:test-reviewer", "ready_for_context_reset": True,
        }
        path = self.root / "receipts/session-handoffs/historical.session-handoff.json"
        path.parent.mkdir(parents=True)
        original = json.dumps(receipt, sort_keys=True).encode()
        path.write_bytes(original)
        with self.context():
            result = services.session_handoff_checkpoint(self.root, dry_run=True)
        self.assertEqual(result["state_digest"], old_state_digest)
        self.assertTrue(result["checkpoint_evidence"]["current_verified"], result)
        self.assertEqual(result["checkpoint_evidence"]["verification_scope"], "legacy_v1_checkpoint_projection")
        self.assertFalse(result["checkpoint_evidence"]["complete_generation_approval_inferred"])
        self.assertTrue(result["ready_for_context_reset"])
        self.assertEqual(path.read_bytes(), original)
        self.assertNotIn("work_session_binding", json.dumps(result))

    def test_default_public_preflight_never_suggests_approving_new_digest(self):
        output, errors = io.StringIO(), io.StringIO()
        with self.context(), redirect_stdout(output), redirect_stderr(errors):
            code = archive_cli.main(["session-handoff-checkpoint", str(self.root), "--dry-run", "--confirm-chat-reviewed", "--format", "json"])
        self.assertEqual(code, 0, output.getvalue() + errors.getvalue())
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "would_write")
        self.assertNotIn("capability_state", result)
        self.assertNotEqual(result["state_digest"], result["diagnostic_state_digest"])
        self.assertFalse(result["diagnostic_digest_is_authority"])
        self.assertIn("Approve only the exact state_digest", " ".join(result["next_safe_actions"]))
        output, errors = io.StringIO(), io.StringIO()
        with self.context(), redirect_stdout(output), redirect_stderr(errors):
            code = archive_cli.main(["session-handoff-checkpoint", str(self.root), "--approve", "--reviewed-by", "person:test-reviewer", "--confirm-chat-reviewed", "--expected-state-digest", result["diagnostic_state_digest"], "--format", "json"])
        self.assertEqual(code, 1)
        rejected = json.loads(output.getvalue())
        self.assertTrue(any("stale session handoff plan" in item for item in rejected["blockers"]))
        self.assertEqual(rejected["files_written"], [])
        self.assertFalse((self.root / "receipts/session-handoffs").exists())
        output, errors = io.StringIO(), io.StringIO()
        with self.context(), redirect_stdout(output), redirect_stderr(errors):
            code = archive_cli.main(["session-handoff-checkpoint", str(self.root), "--approve", "--reviewed-by", "person:test-reviewer", "--confirm-chat-reviewed", "--expected-state-digest", result["state_digest"], "--format", "json"])
        self.assertEqual(code, 0, output.getvalue() + errors.getvalue())
        written = json.loads(output.getvalue())
        self.assertEqual(written["status"], "written")
        self.assertTrue(written["ready_for_context_reset"])
        receipt_path = self.root / written["files_written"][0]
        receipt_bytes = receipt_path.read_bytes()
        receipt = json.loads(receipt_bytes)
        self.assertEqual(receipt["state_digest"], result["state_digest"])
        self.assertNotIn("diagnostic_state_digest", receipt)
        self.assertNotIn("ai_artifact_generation_diagnostic", receipt)
        self.assertNotIn("work_session_binding", receipt)
        with self.context():
            repeated = services.session_handoff_checkpoint(self.root, approve=True, reviewed_by="person:test-reviewer", confirm_chat_reviewed=True, expected_state_digest=result["state_digest"])
        self.assertEqual(repeated["status"], "no_change")
        self.assertEqual(repeated["files_written"], [])
        self.assertEqual(receipt_path.read_bytes(), receipt_bytes)


if __name__ == "__main__":
    unittest.main()
