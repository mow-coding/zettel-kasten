"""v0.4.36 (beta letter 168 ① ② ⑥): the object-storage-upload writer names its cause, the two
post-dialog gates are refused before the dialog, a proven-no-effects failure closes its claim, and a
session grant covers every operation kind.

Synthetic archive, in-memory transport, fake dialog; no client data.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wom_kit import archive_cli, archive_services
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import object_storage_preservation as preservation
from wom_kit import object_storage_restore as restore
from wom_kit import object_storage_upload_exact as upload
from wom_kit import work_session_permission as permission
from wom_kit.exact_human_approval_windows import ExactHumanApprovalOperation
from wom_kit.exact_operation_manifest import ExactOperationManifestError, _fail as _runner_fail

import test_v0433_object_storage_upload as _upload_fixture
import test_v0434_letter165 as _compose_fixture
import test_v0430_exact_approval_claims as _claims_fixture

REVIEWER = _upload_fixture.REVIEWER
STORE = _upload_fixture.STORE


class UploadCauseTests(unittest.TestCase):
    """Borrows the v0.4.33 CLI fixture (fake dialog, key provider, env refs, memory transport) without its tests."""

    for _name, _value in vars(_upload_fixture.UploadCliTests).items():
        if not _name.startswith("test") and _name not in {"__module__", "__qualname__", "__doc__", "__dict__", "__weakref__"}:
            locals()[_name] = _value
    del _name, _value

    def _claims(self) -> list[dict]:
        claims_dir = self.archive.root / "profiles" / "local" / "exact-human-approvals" / "claims"
        if not claims_dir.exists():
            return []
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(claims_dir.glob("approval_*.json"))]

    def _upload_claims(self, status: str) -> list[dict]:
        return [c for c in self._claims()
                if (c.get("context") or {}).get("operation") == "object_storage_bytes_upload" and c.get("status") == status]

    def test_writer_failure_after_dialog_names_its_cause_and_closes_the_claim(self) -> None:
        _code, preview = self.run_cli(*self.base_args(), "--dry-run")
        self.assertEqual(preview["manifest_index_authority"], "current")
        self.assertTrue(preview["credential_refs_present"])
        self.assertIsNone(preview["registered_store_refs"])

        def broken_ledger(_plan):
            raise preservation.ObjectStoragePreservationError("object_storage_preservation_control_invalid")

        with patch.object(preservation, "_ManifestBoundPreservationLedger", side_effect=broken_ledger):
            code, result = self.run_cli(
                *self.base_args(), "--approve", "--reviewed-by", REVIEWER,
                "--expected-manifest-sha256", preview["plan_sha256"],
            )
        self.assertEqual(code, 1, result)
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.transport.put_calls, 0)
        # the broker knew the writer wrote nothing: the claim is closed, not left started
        self.assertEqual(result["reason_codes"], ["exact_human_approval_writer_refused"])
        self.assertEqual(result["cause_code"], "object_storage_upload_control_invalid")
        self.assertEqual(result["cause_stage"], "domain_writer")
        self.assertEqual(result["effects_state"], "refused_before_effects")
        self.assertTrue(any("closed as failed" in line for line in result["next_safe_actions"]))
        self.assertIn("progress_summary", result)
        self.assertEqual(self._upload_claims("started"), [])
        failed = self._upload_claims("failed")
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["failure_code"], "object_storage_upload_control_invalid")
        rows = self.archive.rows()
        self.assertFalse(any(l.get("availability") == "wom_uploaded" for l in rows[_upload_fixture._oid(self.raw)]["locations"]))
        rendered = "".join(self.outputs)
        self.assertNotIn(str(self.archive.root), rendered)

    def test_an_untyped_writer_exception_stays_state_unknown_without_free_text(self) -> None:
        _code, preview = self.run_cli(*self.base_args(), "--dry-run")

        def canary(_plan):
            raise ValueError("PRIVATE-FREE-TEXT-CANARY")

        with patch.object(preservation, "_ManifestBoundPreservationLedger", side_effect=canary):
            code, result = self.run_cli(
                *self.base_args(), "--approve", "--reviewed-by", REVIEWER,
                "--expected-manifest-sha256", preview["plan_sha256"],
            )
        self.assertEqual(code, 1, result)
        self.assertEqual(result["reason_codes"], ["exact_human_approval_state_unknown"])
        self.assertNotIn("cause_code", result)
        self.assertEqual(result["effects_state"], "unknown")
        self.assertTrue(any("exact-approval-claims" in line for line in result["next_safe_actions"]))
        self.assertEqual(len(self._upload_claims("started")), 1)
        self.assertNotIn("CANARY", "".join(self.outputs))

    def test_stale_index_is_refused_before_the_dialog(self) -> None:
        with patch.object(restore, "_require_manifest_index_authority_for",
                          side_effect=restore.ObjectStorageRestoreError("archive_index_rebuild_required")):
            code, preview = self.run_cli(*self.base_args(), "--dry-run")
            self.assertEqual(code, 0, preview)
            self.assertEqual(preview["manifest_index_authority"], "rebuild_required")
            self.assertTrue(any("archive index" in line for line in preview["next_safe_actions"]))
            code, refused = self.run_cli(
                *self.base_args(), "--approve", "--reviewed-by", REVIEWER,
                "--expected-manifest-sha256", preview["plan_sha256"],
            )
        self.assertEqual(code, 1, refused)
        self.assertEqual(refused["reason_codes"], ["archive_index_rebuild_required"])
        self.assertEqual(refused["cause_stage"], "upload_preflight")
        self.assertEqual(self.native.calls, 0)
        self.assertEqual(self._claims(), [])
        self.assertEqual(self.transport.put_calls, 0)

    def test_missing_credential_variable_is_refused_before_the_dialog(self) -> None:
        _code, preview = self.run_cli(*self.base_args(), "--dry-run")
        with patch.dict(os.environ, {"WOM_TEST_UPLOAD_SK": ""}):
            code, preview_missing = self.run_cli(*self.base_args(), "--dry-run")
            self.assertEqual(code, 0, preview_missing)
            self.assertFalse(preview_missing["credential_refs_present"])
            self.assertFalse(preview_missing["credential_values_read"])
            self.assertTrue(any("environment variable" in line for line in preview_missing["next_safe_actions"]))
            code, refused = self.run_cli(
                *self.base_args(), "--approve", "--reviewed-by", REVIEWER,
                "--expected-manifest-sha256", preview["plan_sha256"],
            )
        self.assertEqual(code, 1, refused)
        self.assertEqual(refused["reason_codes"], ["object_storage_upload_credential_ref_unresolved"])
        self.assertEqual(self.native.calls, 0)
        self.assertEqual(self._claims(), [])
        self.assertNotIn("AKIAEXAMPLE", "".join(self.outputs))

    def test_store_setup_missing_names_the_registered_labels(self) -> None:
        code, preview = self.run_cli(
            "object-storage-upload", "--all-sessions", str(self.archive.root), "--provider-kind", _upload_fixture.PROVIDER,
            "--store-ref", "storage:account:another-label", "--dry-run",
        )
        self.assertEqual(code, 1, preview)
        self.assertEqual(preview["state"], "writer_unavailable")
        self.assertEqual(preview["writer_unavailable_reason"], "store_setup_missing")
        self.assertEqual(preview["registered_store_refs"], [STORE])
        self.assertTrue(any("registered labels" in line.lower() for line in preview["next_safe_actions"]))

    def test_progress_log_records_the_preflight_events(self) -> None:
        _code, preview = self.run_cli(*self.base_args(), "--dry-run")
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "upload-progress.jsonl"
            code, result = self.run_cli(
                *self.base_args(), "--approve", "--reviewed-by", REVIEWER,
                "--expected-manifest-sha256", preview["plan_sha256"], "--progress-log", str(log_path),
            )
            self.assertEqual(code, 0, result)
            lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        stages = {str(row.get("stage")) for row in lines}
        self.assertIn("exact-operation-preflight", stages)
        self.assertTrue(any(str(row.get("stage")).startswith("exact-operation-") and row.get("stage") != "exact-operation-preflight" for row in lines))
        self.assertEqual(self.transport.put_calls, 1)
        rendered = json.dumps(lines)
        self.assertNotIn(str(self.archive.root), rendered)
        self.assertNotIn("AKIAEXAMPLE", rendered)


class RunnerCauseTests(unittest.TestCase):
    def test_the_runner_carries_the_adapter_code_and_the_effects_mark(self) -> None:
        inner = upload.ObjectStorageUploadError("object_storage_upload_source_drifted")
        retyped = _runner_fail("exact_operation_payload_mismatch", cause=inner)
        self.assertEqual(retyped.code, "exact_operation_payload_mismatch")
        self.assertEqual(retyped.cause_code, "object_storage_upload_source_drifted")
        self.assertIsNone(retyped.effects)
        inner.effects = "none"
        self.assertEqual(_runner_fail("exact_operation_write_failed", cause=inner).effects, "none")
        # free text never becomes a cause
        self.assertIsNone(_runner_fail("exact_operation_write_failed", cause=ValueError("PRIVATE TEXT")).cause_code)
        self.assertIsNone(_runner_fail("exact_operation_write_failed", cause=OSError(5, "no")).cause_code)
        # the broker reads the adapter code through the re-typed error
        self.assertEqual(broker._content_free_cause_code(retyped), "object_storage_upload_source_drifted")
        self.assertEqual(broker._content_free_cause_code(ExactOperationManifestError("exact_operation_writer_busy")),
                         "exact_operation_writer_busy")
        self.assertEqual(broker._content_free_cause_code(upload.ObjectStorageUploadError("archive_index_rebuild_required")),
                         "archive_index_rebuild_required")
        self.assertIsNone(broker._content_free_cause_code(ValueError("archive_index_rebuild_required")))

    def test_every_operation_kind_is_grantable_since_v0436(self) -> None:
        self.assertEqual(permission.ALWAYS_DIALOG_OPERATIONS, frozenset())
        self.assertEqual(len(permission.GRANTABLE_OPERATIONS), len(ExactHumanApprovalOperation))
        self.assertIn(ExactHumanApprovalOperation.object_storage_bytes_upload, permission.GRANTABLE_OPERATIONS)
        self.assertIn(ExactHumanApprovalOperation.project_version_update, permission.GRANTABLE_OPERATIONS)
        self.assertIn(ExactHumanApprovalOperation.exact_approval_claim_finalize, permission.GRANTABLE_OPERATIONS)
        self.assertEqual(permission.DIALOG_ONLY_ACTIONS, ("set-permission-mode",))


class ComposeDefaultRecordTests(unittest.TestCase):
    """v0.4.36 (letter 168 request 9): the draft record is created by default; the revise path names the ref."""

    for _name, _value in vars(_compose_fixture.FeedbackComposeExactApprovalTests).items():
        if not _name.startswith("test") and _name not in {"__module__", "__qualname__", "__doc__", "__dict__", "__weakref__"}:
            locals()[_name] = _value
    del _name, _value

    def test_create_makes_the_draft_record_by_default_and_names_the_body_ref(self) -> None:
        preview = self.compose("--dry-run")
        created = self.compose("--approve", "--expected-plan-sha256", preview["plan_sha256"],
                               "--reviewed-by", _compose_fixture.REVIEWER)
        self.assertTrue(created["draft_record"]["record_created"], created["draft_record"])
        self.assertTrue((self.root / created["draft_record"]["record_path"]).is_file())
        # Request E (2026-09-24): the created letter is ready to deliver; the revise
        # path is only offered when the person asks for a change.
        self.assertEqual(created["user_status_label"], "전달 전")
        self.assertTrue(created["human_review_completed_by_this_approval"])
        self.assertFalse(created["separate_review_copy_needed"])
        self.assertTrue(any("operator-feedback-mark-delivered" in line and "--only" in line
                            for line in created["next_safe_actions"]))
        step_one = next(line for line in created["revision_route_if_requested"] if line.startswith("1."))
        self.assertIn("feedback-body-sha256:<sha>", step_one)
        self.assertIn("--no-create-draft-record", step_one)
        check = self.run_cli("operator-feedback-body-check", str(self.root), "--feedback-id", self.request["feedback_id"], "--dry-run")
        self.assertTrue(check["record_binding"]["feedback_ref_bound"])
        opted_out = self.compose("--approve", "--expected-plan-sha256", preview["plan_sha256"],
                                 "--reviewed-by", _compose_fixture.REVIEWER, "--no-create-draft-record")
        self.assertEqual(opted_out["draft_record"]["skipped_reason"], "not_requested")


class PermissionPreviewKeysTests(unittest.TestCase):
    """v0.4.36 (letter 168 ④ / request 5): the dry-run accepts the approve request; a refusal names the keys."""

    def test_preview_accepts_reviewer_claim_and_a_refusal_lists_allowed_keys(self) -> None:
        from wom_kit import work_session_command as command
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            root.mkdir()
            (root / "archive.yml").write_text("archive_id: archive:test:permission-preview\n", encoding="utf-8")
            refs = dict(client_app_ref="client_app_" + "a" * 32, task_route_ref="task_route_" + "b" * 32,
                        work_session_ref="work_session_" + "c" * 32)
            accepted = command.dispatch_work_session_management(
                root, action="set-permission-mode", dry_run=True, request={
                    "reviewer_claim": "person:x", "permission_mode": "limited", "operations": ["create_draft"], "grant_hours": 12},
                **refs)
            self.assertNotEqual(accepted.get("reason_code"), "work_session_request_invalid", accepted)
            self.assertTrue(accepted["ok"], accepted)
            self.assertEqual(accepted["result"]["dialog_only_actions"], ["set-permission-mode"])
            refused = command.dispatch_work_session_management(
                root, action="set-permission-mode", dry_run=True, request={"permission_mode": "limited", "operations": [], "extra": 1},
                **refs)
            self.assertEqual(refused["reason_code"], "work_session_request_invalid")
            self.assertEqual(refused["reason_detail"]["required_keys"], ["operations", "permission_mode"])
            self.assertEqual(refused["reason_detail"]["optional_keys"], ["grant_hours", "reviewer_claim"])
            self.assertNotIn("extra", json.dumps(refused))


class FinalizeFingerprintTests(_claims_fixture._ClaimStoreCase):
    """v0.4.36 (letter 168 ③ / request 4): the approve skips the receipt re-scan when nothing changed."""

    def test_approve_skips_the_scan_when_the_receipt_inventory_is_unchanged(self) -> None:
        from wom_kit import exact_approval_claims as claims_module
        from wom_kit.exact_human_approval_windows import ExactHumanApprovalOperation as Op
        ids = [self.make_claim(Op.mint_zet) for _ in range(2)]
        original_scan = claims_module.scan_receipt_references
        calls: list[int] = []

        def counting_scan(root, approval_ids):
            calls.append(1)
            return original_scan(root, approval_ids)

        with patch.object(claims_module, "scan_receipt_references", side_effect=counting_scan):
            plan = self.plan(all_started=True)
            self.assertEqual(len(calls), 1)  # the dry-run scans once
            self.assertTrue(plan["evidence_inventory_fingerprint"].startswith("sha256:"))
            self.assertEqual(plan["approve_rescans_receipts"], "only_when_the_inventory_fingerprint_changed")
            result = self.finalize(all_started=True, expected_plan_sha256=plan["plan_sha256"])
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["finalized_count"], 2)
            self.assertEqual(len(calls), 1)  # the approve did not scan again
        receipt = json.loads((self.root / "receipts" / "exact-human-approvals" / "claim-finalize" / f"{ids[0]}.claim-finalize.json").read_bytes())
        self.assertEqual(receipt["write_evidence"]["scan_method"], "fingerprint_matched_plan")

    def test_a_receipt_written_after_the_plan_changes_the_digest_and_forces_the_scan(self) -> None:
        from wom_kit import exact_approval_claims as claims_module
        from wom_kit.exact_human_approval_windows import ExactHumanApprovalOperation as Op
        approval_id = self.make_claim(Op.mint_zet)
        plan = self.plan(all_started=True)
        self.write_receipt_referencing(approval_id)
        with self.assertRaises(archive_services.ArchiveServiceError) as caught:
            self.finalize(all_started=True, expected_plan_sha256=plan["plan_sha256"])
        # the inventory changed, so the re-plan scanned and found the reference (blocked) or the digest moved
        self.assertIn(str(caught.exception), {"exact_approval_claim_finalize_plan_blocked", "exact_approval_claim_finalize_plan_mismatch"})
        self.assertEqual(self.document(approval_id)["status"], "started")
        fresh = self.plan(all_started=True)
        self.assertIn("exact_approval_claim_referenced_by_receipt", fresh["blockers"])
        self.assertNotEqual(fresh["evidence_inventory_fingerprint"], plan["evidence_inventory_fingerprint"])


if __name__ == "__main__":
    unittest.main()
