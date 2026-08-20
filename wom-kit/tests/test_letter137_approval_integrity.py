from __future__ import annotations

import json
import hashlib
import inspect
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from jsonschema import Draft202012Validator

from wom_kit import approval_integrity
from wom_kit.exact_human_approval import (
    CLAIMS_RELATIVE_ROOT,
    _claim_exact_human_approval_core as claim_exact_human_approval,
    exact_human_approval_archive_identity_sha256,
)
from wom_kit.exact_human_approval_windows import (
    ExactHumanApprovalContext,
    _ExactHumanApprovalDecision as ExactHumanApprovalDecision,
    ExactHumanApprovalOperation,
)


AUTH_KEY = bytes(range(32))
ARCHIVE_ID = "archive:test-approval-integrity"
PRIVATE_TITLE = "PRIVATE TITLE MUST NEVER ECHO"
PRIVATE_PATH = "inbox/PRIVATE-person-name.md"
PRIVATE_REVIEWER = "person:PRIVATE-reviewer-name"


def _json_digest_hex(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


class ApprovalIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "archive"
        self.root.mkdir()
        (self.root / "archive.yml").write_text(
            f"archive_id: {ARCHIVE_ID}\n", encoding="utf-8"
        )
        self.clock_value = datetime(2026, 8, 20, 9, 30, tzinfo=timezone.utc)
        self.clock = lambda: self.clock_value
        self.claim_counter = 0

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_json(self, relative: str, document: dict) -> Path:
        path = self.root.joinpath(*relative.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    def _mint_receipt(
        self,
        zettel_id: str,
        *,
        reviewed_by: str | None = PRIVATE_REVIEWER,
        affirmations: list[dict] | None = None,
        approval_binding: dict | None = None,
        source_fidelity: dict | None = None,
    ) -> tuple[str, Path]:
        relative = f"receipts/mint/{zettel_id}.mint.json"
        document: dict = {
            "receipt_id": f"receipt:mint:{zettel_id}",
            "receipt_path": relative,
            "action": "mint_zettel",
            "dry_run": False,
            "timestamp": "2026-08-20T09:00:00Z",
            "archive_id": ARCHIVE_ID,
            "authority_mode": "basic",
            "source": {
                "path": PRIVATE_PATH,
                "status": "draft",
                "sha256": "1" * 64,
            },
            "target": {
                "path": f"zettel-kasten/{PRIVATE_TITLE}.md",
                "status": "canonical",
                "sha256": "2" * 64,
            },
            "snapshot": {"path": PRIVATE_PATH, "sha256": "1" * 64},
            "zettel": {"id": zettel_id, "title": PRIVATE_TITLE},
            "checklist": [],
            "near_duplicates": [],
            "warnings": [],
            "result": {"created_paths": [PRIVATE_PATH]},
        }
        if reviewed_by is not None:
            document["reviewed_by"] = reviewed_by
        if affirmations is not None:
            document["affirmations"] = affirmations
        if approval_binding is not None:
            document["exact_human_approval"] = approval_binding
        if source_fidelity is not None:
            document["source_fidelity"] = source_fidelity
        return relative, self._write_json(relative, document)

    def _edge_receipt(
        self,
        edge_id: str = "edge:" + "3" * 64,
        *,
        reviewed_by: str | None = PRIVATE_REVIEWER,
        approval_binding: dict | None = None,
    ) -> tuple[str, Path]:
        relative = "receipts/edges/private-source.related." + "3" * 16 + ".zettel-edge.json"
        document = {
            "schema_version": "wom-kit/zettel-edge-receipt/v0.1",
            "lifecycle_action": "zettel_edge_write",
            "receipt_kind": "zettel_edge_write",
            "created_at": "2026-08-20T09:00:00Z",
            "archive_id": ARCHIVE_ID,
            "edge_id": edge_id,
            "edge_type": "related",
            "source_zettel_id": "zet_private_source",
            "source_zettel_path": PRIVATE_PATH,
            "target_ref": "zet:PRIVATE-target",
            "target_kind": "zettel",
            "visibility": "private",
            "result": {
                "edge_written": True,
                "zettel_frontmatter_updated": True,
                "receipt_written": True,
            },
        }
        if reviewed_by is not None:
            document["reviewed_by"] = reviewed_by
        if approval_binding is not None:
            document["exact_human_approval"] = approval_binding
        return relative, self._write_json(relative, document)

    def _retired_receipt(
        self,
        zettel_id: str = "zet_private_retired",
        *,
        reviewed_by: str | None = None,
        approval_binding: dict | None = None,
    ) -> tuple[str, Path]:
        relative = f"receipts/mint/retired-drafts/{zettel_id}.retire-draft.json"
        document = {
            "receipt_id": f"receipt:mint-retired-draft:{zettel_id}",
            "receipt_path": relative,
            "action": "retire_minted_draft",
            "dry_run": False,
            "timestamp": "2026-08-20T09:00:00Z",
            "archive_id": ARCHIVE_ID,
            "authority_mode": "basic",
            "source": {"path": PRIVATE_PATH, "sha256": "1" * 64},
            "target": {"path": PRIVATE_PATH, "sha256": "2" * 64},
            "mint_receipt": {"path": PRIVATE_PATH, "sha256": "3" * 64},
            "snapshot": {"path": PRIVATE_PATH, "sha256": "1" * 64},
            "zettel": {"id": zettel_id},
            "result": {"removed_paths": [PRIVATE_PATH]},
        }
        if reviewed_by is not None:
            document["reviewed_by"] = reviewed_by
        if approval_binding is not None:
            document["exact_human_approval"] = approval_binding
        return relative, self._write_json(relative, document)

    def _fidelity_receipt(
        self,
        zettel_id: str,
        *,
        independent: bool,
        source_role: str,
    ) -> tuple[str, dict]:
        raw_sha = "e" * 64
        body_sha = "a" * 64
        source = {
            "authority_kind": "manifested_object",
            "object_id": "sha256:" + raw_sha,
            "raw_sha256": raw_sha,
            "raw_size_bytes": 128,
            "normalized_sha256": body_sha,
            "normalized_size_bytes": 128,
            "comparison_basis": "utf8_newlines_lf",
            "newline_transformation_applied": False,
            "source_text_stored": False,
            "source_locator_stored": False,
            "provenance": {
                "binding_state": "legacy_unbound",
                "captured_at": "2026-08-20T07:00:00Z",
                "source_role": source_role,
                "input_kind": None,
                "source_intake_plan_sha256": None,
                "staged_source_class": "archive_ai_scratch",
                "independent_external_provenance": independent,
                "raw_source_locator_stored": False,
                "raw_source_locator_echoed": False,
            },
        }
        mode = "faithful_summary"
        audience = "private_self"
        region = None
        fidelity = {
            "schema": "wom-kit/source-fidelity/v0.2",
            "mode": mode,
            "audience": audience,
            "comparison_basis": "utf8_newlines_lf",
            "source": source,
            "region": region,
            "byte_exact": False,
            "mechanically_verified": False,
            "semantic_fidelity_machine_verified": False,
            "human_review_required": True,
            "source_changed": False,
            "share_performed": False,
            "source_text_stored": False,
            "source_locator_stored": False,
            "evidence_id": "source-fidelity-evidence:"
            + _json_digest_hex(
                {
                    "source": source,
                    "region": region,
                    "mode": mode,
                    "audience": audience,
                    "comparison_basis": "utf8_newlines_lf",
                }
            )[:24],
        }
        candidate_created_at = "2026-08-20T08:00:00Z"
        frontmatter_sha = "b" * 64
        plan_sha = _json_digest_hex(
            {
                "schema": "wom-kit/source-fidelity/v0.2",
                "archive_id": ARCHIVE_ID,
                "archive_type": "personal",
                "draft_id": zettel_id,
                "draft_path": PRIVATE_PATH,
                "created_at": candidate_created_at,
                "creation_mode": "ai_generated",
                "source_fidelity": fidelity,
                "final_body_sha256": body_sha,
                "region": region,
                "frontmatter_authority_sha256": frontmatter_sha,
            }
        )
        fidelity["creation_plan_sha256"] = plan_sha
        review_binding_sha = _json_digest_hex(
            {
                "schema": "wom-kit/source-fidelity-review-binding/v0.1",
                "archive_id": ARCHIVE_ID,
                "draft_id": zettel_id,
                "draft_path": PRIVATE_PATH,
                "body_sha256": body_sha,
                "source_fidelity_plan_sha256": plan_sha,
                "reviewed_by": PRIVATE_REVIEWER,
            }
        )
        receipt = {
            "schema": "wom-kit/source-fidelity-draft-receipt/v0.2",
            "action": "create_source_fidelity_draft",
            "archive_id": ARCHIVE_ID,
            "archive_type": "personal",
            "draft_id": zettel_id,
            "draft_path": PRIVATE_PATH,
            "body_sha256": body_sha,
            "creation_mode": "ai_generated",
            "frontmatter_authority_sha256": frontmatter_sha,
            "source_fidelity_plan_sha256": plan_sha,
            "reviewed_by": PRIVATE_REVIEWER,
            "review_binding_sha256": review_binding_sha,
            "candidate_created_at": candidate_created_at,
            "source_fidelity": fidelity,
            "content_contract": {
                "source_text_stored": False,
                "source_locator_stored": False,
                "source_path_stored": False,
            },
            "result": {
                "draft_written_create_only": True,
                "receipt_written_create_only": True,
                "source_changed": False,
                "share_performed": False,
            },
        }
        return plan_sha, receipt

    def _context(
        self,
        *,
        operation: ExactHumanApprovalOperation,
        plan_sha256: str,
        target_binding_sha256: str,
        review_codes: tuple[str, ...],
        warning_codes: tuple[str, ...],
    ) -> ExactHumanApprovalContext:
        return ExactHumanApprovalContext(
            operation=operation,
            archive_identity_sha256=exact_human_approval_archive_identity_sha256(
                ARCHIVE_ID
            ),
            plan_sha256=plan_sha256,
            target_binding_sha256=target_binding_sha256,
            reviewer_claim="person:local-operator",
            review_binding_codes=review_codes,
            warning_codes=warning_codes,
        )

    def _claim(self, context: ExactHumanApprovalContext):
        self.claim_counter += 1
        decision = ExactHumanApprovalDecision(
            approved=True,
            synthetic_acknowledged=False,
            reason_code="exact_human_approval_approved",
            plan_sha256=context.plan_sha256,
            target_binding_sha256=context.target_binding_sha256,
        )
        suffix = format(self.claim_counter, "032x")
        return claim_exact_human_approval(
            self.root,
            context,
            decision,
            AUTH_KEY,
            clock=self.clock,
            random_hex=lambda _size: suffix,
        )

    def _overlay_plan(
        self,
        relative: str,
        inspection: dict,
        state: str,
        *,
        expected_current: str | None = None,
    ) -> dict:
        return approval_integrity.plan_approval_integrity_overlay(
            self.root,
            operation_receipt=relative,
            expected_operation_receipt_sha256=inspection[
                "operation_receipt_sha256"
            ],
            affected_kind=inspection["affected_kind"],
            affected_id_sha256=inspection["affected_id_sha256"],
            state=state,
            expected_current_overlay_digest=expected_current,
            receipt_authentication_key=AUTH_KEY,
        )

    def _claim_for_overlay(self, plan: dict):
        context = self._context(
            operation=ExactHumanApprovalOperation.integrity_repair,
            plan_sha256=plan["plan_sha256"],
            target_binding_sha256=plan["target_binding_sha256"],
            review_codes=tuple(plan["review_binding_codes"]),
            warning_codes=tuple(plan["warning_codes"]),
        )
        return context, self._claim(context)

    def _create_overlay(
        self,
        relative: str,
        inspection: dict,
        plan: dict,
        context: ExactHumanApprovalContext,
        claim,
        *,
        finalize: bool = True,
    ) -> dict:
        result = approval_integrity.create_approval_integrity_overlay(
            self.root,
            operation_receipt=relative,
            expected_operation_receipt_sha256=inspection[
                "operation_receipt_sha256"
            ],
            affected_kind=inspection["affected_kind"],
            affected_id_sha256=inspection["affected_id_sha256"],
            state=plan["state"],
            expected_current_overlay_digest=plan["prior_overlay_digest"],
            expected_plan_sha256=plan["plan_sha256"],
            approval_claim=claim,
            approval_context=context,
            clock=self.clock,
            random_hex=lambda _size: "a" * 16,
        )
        self.assertEqual(result["claim_status_at_return"], "started")
        self.assertTrue(result["claim_finalization_required"])
        if finalize:
            claim.finalize_succeeded()
        return result

    def test_bounded_audit_classifies_legacy_affirmation_and_unknown_privately(self) -> None:
        self._mint_receipt(
            "zet_private_mint",
            affirmations=[
                {
                    "item_id": "PRIVATE affirmation label",
                    "affirmed_by": PRIVATE_REVIEWER,
                    "affirmed_at": "2026-08-20T09:00:00Z",
                }
            ],
        )
        self._edge_receipt()
        self._retired_receipt()

        result = approval_integrity.audit_approval_integrity(self.root)
        classes = {
            item["affected_kind"]: item["classification"]
            for item in result["results"]
        }
        self.assertEqual(classes["canonical_mint"], "unsupported_affirmation")
        self.assertEqual(classes["zettel_edge"], "legacy_unbound_approval")
        self.assertEqual(classes["retired_draft"], "unknown")
        self.assertFalse(result["operation_receipts_authenticated"])
        rendered = json.dumps(result, ensure_ascii=False)
        for private_value in (
            PRIVATE_TITLE,
            PRIVATE_PATH,
            PRIVATE_REVIEWER,
            "PRIVATE affirmation label",
            "zet_private_mint",
            "private-source",
        ):
            self.assertNotIn(private_value, rendered)

    def test_exact_v0400_requires_authenticated_succeeded_claim(self) -> None:
        zettel_id = "zet_exact_v0400"
        operation_plan_sha = "sha256:" + "4" * 64
        operation_target_sha = "sha256:" + "9" * 64
        context = self._context(
            operation=ExactHumanApprovalOperation.mint_zet,
            plan_sha256=operation_plan_sha,
            target_binding_sha256=operation_target_sha,
            review_codes=("body_digest", "frontmatter_digest"),
            warning_codes=(),
        )
        claim = self._claim(context)
        relative, _path = self._mint_receipt(
            zettel_id,
            approval_binding={
                "schema_version": approval_integrity.OPERATION_APPROVAL_SCHEMA_VERSION,
                "operation": "mint_zet",
                "plan_sha256": operation_plan_sha,
                "target_binding_sha256": operation_target_sha,
                "exact_human_approval": claim.public_reference(),
            },
        )
        uncertain = approval_integrity.inspect_approval_integrity_operation_receipt(
            self.root,
            relative,
            receipt_authentication_key=AUTH_KEY,
        )
        self.assertEqual(uncertain["classification"], "unknown")
        self.assertFalse(uncertain["exact_human_approval_claim_verified"])
        claim.finalize_succeeded()
        try:
            verified = approval_integrity.inspect_approval_integrity_operation_receipt(
                self.root,
                relative,
                receipt_authentication_key=AUTH_KEY,
            )
            unverified = approval_integrity.inspect_approval_integrity_operation_receipt(
                self.root, relative
            )
            self.assertEqual(verified["classification"], "exact_v0400")
            self.assertTrue(verified["exact_human_approval_claim_verified"])
            self.assertFalse(
                verified["operation_receipt_mac_or_signature_verified"]
            )
            self.assertEqual(unverified["classification"], "unknown")
            self.assertFalse(unverified["exact_human_approval_claim_verified"])
        finally:
            claim.close()

    def test_tampered_exact_claim_is_receipt_invalid_not_legacy(self) -> None:
        zettel_id = "zet_tampered_claim"
        operation_plan_sha = "sha256:" + "5" * 64
        operation_target_sha = "sha256:" + "8" * 64
        context = self._context(
            operation=ExactHumanApprovalOperation.mint_zet,
            plan_sha256=operation_plan_sha,
            target_binding_sha256=operation_target_sha,
            review_codes=("body_digest",),
            warning_codes=(),
        )
        claim = self._claim(context)
        relative, _path = self._mint_receipt(
            zettel_id,
            approval_binding={
                "schema_version": approval_integrity.OPERATION_APPROVAL_SCHEMA_VERSION,
                "operation": "mint_zet",
                "plan_sha256": operation_plan_sha,
                "target_binding_sha256": operation_target_sha,
                "exact_human_approval": claim.public_reference(),
            },
        )
        claim.finalize_succeeded()
        claim_path = self.root / CLAIMS_RELATIVE_ROOT / f"{claim.approval_id}.json"
        document = json.loads(claim_path.read_text(encoding="utf-8"))
        document["context"]["plan_sha256"] = "sha256:" + "6" * 64
        claim_path.write_text(json.dumps(document), encoding="utf-8")
        try:
            result = approval_integrity.inspect_approval_integrity_operation_receipt(
                self.root, relative, receipt_authentication_key=AUTH_KEY
            )
            self.assertEqual(result["classification"], "receipt_invalid")
            self.assertNotIn("6" * 64, json.dumps(result))
        finally:
            claim.close()

    def test_edge_and_retire_exact_receipts_use_writer_target_bindings(self) -> None:
        cases = (
            (
                "zettel_edge",
                ExactHumanApprovalOperation.zettel_edge,
                self._edge_receipt,
            ),
            (
                "retire_draft",
                ExactHumanApprovalOperation.retire_draft,
                self._retired_receipt,
            ),
        )
        claims = []
        try:
            for index, (operation, operation_enum, writer) in enumerate(
                cases, start=10
            ):
                plan_sha = "sha256:" + format(index, "x") * 64
                target_sha = "sha256:" + format(index + 2, "x") * 64
                context = self._context(
                    operation=operation_enum,
                    plan_sha256=plan_sha,
                    target_binding_sha256=target_sha,
                    review_codes=("operation_target_digest",),
                    warning_codes=(),
                )
                claim = self._claim(context)
                claims.append(claim)
                binding = {
                    "schema_version": approval_integrity.OPERATION_APPROVAL_SCHEMA_VERSION,
                    "operation": operation,
                    "plan_sha256": plan_sha,
                    "target_binding_sha256": target_sha,
                    "exact_human_approval": claim.public_reference(),
                }
                relative, _path = writer(approval_binding=binding)
                claim.finalize_succeeded()
                result = approval_integrity.inspect_approval_integrity_operation_receipt(
                    self.root,
                    relative,
                    receipt_authentication_key=AUTH_KEY,
                )
                self.assertEqual(result["classification"], "exact_v0400")
                self.assertTrue(result["exact_human_approval_claim_verified"])
        finally:
            for claim in claims:
                claim.close()

    def test_circular_requires_hash_equality_and_positive_provenance(self) -> None:
        positive_id = "zet_circular_positive"
        negative_id = "zet_circular_unknown"
        for zettel_id, independent, source_role in (
            (positive_id, False, "derived_context"),
            (negative_id, True, "primary_source"),
        ):
            plan_sha, fidelity = self._fidelity_receipt(
                zettel_id,
                independent=independent,
                source_role=source_role,
            )
            projection = {
                "schema": "wom-kit/source-fidelity/v0.2",
                "creation_plan_sha256": plan_sha,
            }
            self._mint_receipt(zettel_id, source_fidelity=projection)
            self._write_json(
                f"receipts/source-fidelity/drafts/{plan_sha}.json", fidelity
            )

        result = approval_integrity.audit_approval_integrity(self.root)
        classes = sorted(item["classification"] for item in result["results"])
        self.assertEqual(
            classes, ["circular_self_source", "legacy_unbound_approval"]
        )
        circular = next(
            item
            for item in result["results"]
            if item["classification"] == "circular_self_source"
        )
        self.assertTrue(circular["mechanical_equality_proven"])
        self.assertTrue(circular["provenance_facts_proven"])
        self.assertTrue(circular["related_fidelity_receipt_valid"])

    def test_v01_fidelity_without_positive_provenance_remains_legacy(self) -> None:
        self._mint_receipt(
            "zet_legacy_fidelity",
            source_fidelity={
                "schema": "wom-kit/source-fidelity/v0.1",
                "creation_plan_sha256": "d" * 64,
            },
        )
        result = approval_integrity.audit_approval_integrity(self.root)
        self.assertEqual(
            result["results"][0]["classification"],
            "legacy_unbound_approval",
        )
        self.assertFalse(result["results"][0]["provenance_facts_proven"])

    def test_fidelity_digest_tamper_cannot_create_circular_classification(self) -> None:
        zettel_id = "zet_fidelity_tampered"
        plan_sha, fidelity = self._fidelity_receipt(
            zettel_id,
            independent=False,
            source_role="derived_context",
        )
        self._mint_receipt(
            zettel_id,
            source_fidelity={
                "schema": "wom-kit/source-fidelity/v0.2",
                "creation_plan_sha256": plan_sha,
            },
        )
        fidelity["source_fidelity"]["source"]["provenance"][
            "staged_source_class"
        ] = "PRIVATE-tampered-class"
        self._write_json(
            f"receipts/source-fidelity/drafts/{plan_sha}.json", fidelity
        )
        result = approval_integrity.audit_approval_integrity(self.root)
        self.assertEqual(result["results"][0]["classification"], "receipt_invalid")
        self.assertFalse(result["results"][0]["provenance_facts_proven"])
        self.assertNotIn("PRIVATE-tampered-class", json.dumps(result))

    def test_receipt_scan_limit_is_enforced_and_reported_incomplete(self) -> None:
        self._mint_receipt("zet_limit_one")
        self._mint_receipt("zet_limit_two")
        self._edge_receipt()
        result = approval_integrity.audit_approval_integrity(
            self.root, max_receipts=1
        )
        self.assertEqual(result["receipt_count"], 1)
        self.assertFalse(result["ok"])
        self.assertFalse(result["complete"])
        self.assertIn(
            "approval_integrity_receipt_limit_exceeded",
            result["blocker_codes"],
        )

    def test_malformed_and_duplicate_key_receipts_are_content_free_invalid(self) -> None:
        directory = self.root / "receipts" / "edges"
        directory.mkdir(parents=True)
        private_text = "PRIVATE MALFORMED BODY"
        (directory / "private.zettel-edge.json").write_text(
            '{"archive_id":"archive:test", "archive_id":"'
            + private_text
            + '"}',
            encoding="utf-8",
        )
        result = approval_integrity.audit_approval_integrity(self.root)
        self.assertEqual(result["results"][0]["classification"], "receipt_invalid")
        self.assertNotIn(private_text, json.dumps(result))

    def test_overlay_append_blocks_guard_and_followup_repair_unblocks(self) -> None:
        relative, _path = self._edge_receipt()
        inspection = approval_integrity.inspect_approval_integrity_operation_receipt(
            self.root, relative, receipt_authentication_key=AUTH_KEY
        )
        first_plan = self._overlay_plan(relative, inspection, "review_required")
        first_context, first_claim = self._claim_for_overlay(first_plan)
        try:
            first = self._create_overlay(
                relative, inspection, first_plan, first_context, first_claim
            )
            self.assertEqual(first_claim.status, "succeeded")
            guard = approval_integrity.approval_integrity_guard(
                self.root,
                affected_kind=inspection["affected_kind"],
                affected_id_sha256=inspection["affected_id_sha256"],
                receipt_authentication_key=AUTH_KEY,
            )
            self.assertTrue(guard["ok"])
            self.assertTrue(guard["blocked"])
            self.assertFalse(guard["allowed"])
            self.assertEqual(guard["current_state"], "review_required")

            self.clock_value += timedelta(minutes=1)
            second_plan = self._overlay_plan(
                relative,
                inspection,
                "repair_planned",
                expected_current=first["current_overlay_digest"],
            )
            second_context, second_claim = self._claim_for_overlay(second_plan)
            try:
                second = self._create_overlay(
                    relative,
                    inspection,
                    second_plan,
                    second_context,
                    second_claim,
                )
                repaired_guard = approval_integrity.approval_integrity_guard(
                    self.root,
                    affected_kind=inspection["affected_kind"],
                    affected_id_sha256=inspection["affected_id_sha256"],
                    receipt_authentication_key=AUTH_KEY,
                )
                self.assertTrue(repaired_guard["ok"])
                self.assertTrue(repaired_guard["allowed"])
                self.assertFalse(repaired_guard["blocked"])
                self.assertEqual(repaired_guard["current_state"], "repair_planned")
                self.assertEqual(repaired_guard["entry_count"], 2)
                self.assertEqual(
                    second["prior_overlay_digest"], first["current_overlay_digest"]
                )
            finally:
                second_claim.close()
        finally:
            first_claim.close()

    def test_stale_expected_current_closes_replay_and_concurrency(self) -> None:
        relative, _path = self._edge_receipt()
        inspection = approval_integrity.inspect_approval_integrity_operation_receipt(
            self.root, relative, receipt_authentication_key=AUTH_KEY
        )
        plan = self._overlay_plan(relative, inspection, "review_required")
        context_one, claim_one = self._claim_for_overlay(plan)
        context_two, claim_two = self._claim_for_overlay(plan)
        try:
            self._create_overlay(relative, inspection, plan, context_one, claim_one)
            with self.assertRaises(approval_integrity.ApprovalIntegrityError) as stale:
                self._create_overlay(
                    relative, inspection, plan, context_two, claim_two
                )
            self.assertEqual(
                stale.exception.code,
                "approval_integrity_overlay_expected_current_mismatch",
            )
            self.assertEqual(claim_two.status, "started")
            guard = approval_integrity.approval_integrity_guard(
                self.root,
                affected_kind=inspection["affected_kind"],
                affected_id_sha256=inspection["affected_id_sha256"],
                receipt_authentication_key=AUTH_KEY,
            )
            self.assertEqual(guard["entry_count"], 1)
        finally:
            claim_one.close()
            claim_two.close()

    def test_overlay_writer_uses_claim_capability_reasserts_then_never_finalizes(self) -> None:
        self.assertNotIn(
            "receipt_authentication_key",
            inspect.signature(
                approval_integrity.create_approval_integrity_overlay
            ).parameters,
        )
        relative, _path = self._edge_receipt()
        inspection = approval_integrity.inspect_approval_integrity_operation_receipt(
            self.root, relative, receipt_authentication_key=AUTH_KEY
        )
        plan = self._overlay_plan(relative, inspection, "review_required")
        context, claim = self._claim_for_overlay(plan)
        events: list[str] = []
        original_assert = claim.assert_ready_for_context
        original_mac = claim.approval_integrity_mac
        original_publish = approval_integrity._publish_overlay_create_only

        def assert_context(value):
            events.append("assert_context")
            return original_assert(value)

        def mac_payload(value):
            events.append("mac")
            return original_mac(value)

        def publish(*args, **kwargs):
            events.append("append")
            return original_publish(*args, **kwargs)

        try:
            with mock.patch.object(
                claim, "assert_ready_for_context", side_effect=assert_context
            ), mock.patch.object(
                claim, "approval_integrity_mac", side_effect=mac_payload
            ), mock.patch.object(
                approval_integrity,
                "_publish_overlay_create_only",
                side_effect=publish,
            ):
                self._create_overlay(
                    relative,
                    inspection,
                    plan,
                    context,
                    claim,
                    finalize=False,
                )
            self.assertGreaterEqual(events.count("assert_context"), 2)
            self.assertLess(
                max(
                    index
                    for index, event in enumerate(events)
                    if event == "assert_context"
                ),
                events.index("mac"),
            )
            self.assertLess(events.index("mac"), events.index("append"))
            self.assertEqual(claim.status, "started")
        finally:
            claim.close()

    def test_overlay_tamper_fails_closed_without_echo(self) -> None:
        relative, _path = self._edge_receipt()
        inspection = approval_integrity.inspect_approval_integrity_operation_receipt(
            self.root, relative, receipt_authentication_key=AUTH_KEY
        )
        plan = self._overlay_plan(relative, inspection, "withdrawn")
        context, claim = self._claim_for_overlay(plan)
        try:
            self._create_overlay(relative, inspection, plan, context, claim)
            overlay_directory = (
                self.root
                / "receipts"
                / "approval-integrity"
                / "overlays"
                / inspection["affected_id_sha256"].removeprefix("sha256:")
            )
            overlay = next(overlay_directory.glob("*.approval-integrity.json"))
            document = json.loads(overlay.read_text(encoding="utf-8"))
            document["PRIVATE_TITLE"] = PRIVATE_TITLE
            overlay.write_text(json.dumps(document), encoding="utf-8")
            guard = approval_integrity.approval_integrity_guard(
                self.root,
                affected_kind=inspection["affected_kind"],
                affected_id_sha256=inspection["affected_id_sha256"],
                receipt_authentication_key=AUTH_KEY,
            )
            self.assertFalse(guard["ok"])
            self.assertTrue(guard["blocked"])
            self.assertFalse(guard["allowed"])
            self.assertNotIn(PRIVATE_TITLE, json.dumps(guard))
        finally:
            claim.close()

    def test_precommit_crash_writes_no_overlay_and_leaves_claim_uncertain(self) -> None:
        relative, _path = self._edge_receipt()
        inspection = approval_integrity.inspect_approval_integrity_operation_receipt(
            self.root, relative, receipt_authentication_key=AUTH_KEY
        )
        plan = self._overlay_plan(relative, inspection, "review_required")
        context, claim = self._claim_for_overlay(plan)
        try:
            with mock.patch.object(
                approval_integrity,
                "_publish_overlay_create_only",
                side_effect=approval_integrity.ApprovalIntegrityError(
                    "approval_integrity_overlay_commit_failed"
                ),
            ):
                with self.assertRaises(approval_integrity.ApprovalIntegrityError):
                    self._create_overlay(relative, inspection, plan, context, claim)
            self.assertEqual(claim.status, "started")
            guard = approval_integrity.approval_integrity_guard(
                self.root,
                affected_kind=inspection["affected_kind"],
                affected_id_sha256=inspection["affected_id_sha256"],
                receipt_authentication_key=AUTH_KEY,
            )
            self.assertTrue(guard["ok"])
            self.assertTrue(guard["allowed"])
            self.assertEqual(guard["entry_count"], 0)
        finally:
            claim.close()

    def test_postcommit_claim_finalization_uncertainty_fails_guard_closed(self) -> None:
        relative, _path = self._edge_receipt()
        inspection = approval_integrity.inspect_approval_integrity_operation_receipt(
            self.root, relative, receipt_authentication_key=AUTH_KEY
        )
        plan = self._overlay_plan(relative, inspection, "repair_planned")
        context, claim = self._claim_for_overlay(plan)
        try:
            self._create_overlay(
                relative,
                inspection,
                plan,
                context,
                claim,
                finalize=False,
            )
            with mock.patch.object(
                claim,
                "finalize_succeeded",
                side_effect=RuntimeError("PRIVATE crash detail"),
            ):
                with self.assertRaises(RuntimeError):
                    claim.finalize_succeeded()
            guard = approval_integrity.approval_integrity_guard(
                self.root,
                affected_kind=inspection["affected_kind"],
                affected_id_sha256=inspection["affected_id_sha256"],
                receipt_authentication_key=AUTH_KEY,
            )
            self.assertFalse(guard["ok"])
            self.assertTrue(guard["blocked"])
            self.assertNotIn("PRIVATE crash detail", json.dumps(guard))
        finally:
            claim.close()

    def test_orphaned_crash_temp_file_fails_guard_closed(self) -> None:
        relative, _path = self._edge_receipt()
        inspection = approval_integrity.inspect_approval_integrity_operation_receipt(
            self.root, relative, receipt_authentication_key=AUTH_KEY
        )
        directory = (
            self.root
            / "receipts"
            / "approval-integrity"
            / "overlays"
            / inspection["affected_id_sha256"].removeprefix("sha256:")
        )
        directory.mkdir(parents=True)
        private_crash_text = "PRIVATE partial overlay bytes"
        (directory / ".orphan.tmp-0000000000000000").write_text(
            private_crash_text, encoding="utf-8"
        )
        guard = approval_integrity.approval_integrity_guard(
            self.root,
            affected_kind=inspection["affected_kind"],
            affected_id_sha256=inspection["affected_id_sha256"],
            receipt_authentication_key=AUTH_KEY,
        )
        self.assertFalse(guard["ok"])
        self.assertTrue(guard["blocked"])
        self.assertFalse(guard["allowed"])
        self.assertNotIn(private_crash_text, json.dumps(guard))

    def test_wrong_context_operation_and_operation_sha_never_write(self) -> None:
        relative, _path = self._edge_receipt()
        inspection = approval_integrity.inspect_approval_integrity_operation_receipt(
            self.root, relative, receipt_authentication_key=AUTH_KEY
        )
        with self.assertRaises(approval_integrity.ApprovalIntegrityError) as digest:
            approval_integrity.plan_approval_integrity_overlay(
                self.root,
                operation_receipt=relative,
                expected_operation_receipt_sha256="sha256:" + "f" * 64,
                affected_kind=inspection["affected_kind"],
                affected_id_sha256=inspection["affected_id_sha256"],
                state="review_required",
                receipt_authentication_key=AUTH_KEY,
            )
        self.assertEqual(
            digest.exception.code,
            "approval_integrity_operation_receipt_sha256_mismatch",
        )

        plan = self._overlay_plan(relative, inspection, "review_required")
        wrong_context = self._context(
            operation=ExactHumanApprovalOperation.zettel_edge,
            plan_sha256=plan["plan_sha256"],
            target_binding_sha256=plan["target_binding_sha256"],
            review_codes=tuple(plan["review_binding_codes"]),
            warning_codes=tuple(plan["warning_codes"]),
        )
        wrong_claim = self._claim(wrong_context)
        try:
            with self.assertRaises(approval_integrity.ApprovalIntegrityError) as wrong:
                self._create_overlay(
                    relative,
                    inspection,
                    plan,
                    wrong_context,
                    wrong_claim,
                )
            self.assertEqual(
                wrong.exception.code,
                "approval_integrity_approval_context_invalid",
            )
            self.assertEqual(wrong_claim.status, "started")
        finally:
            wrong_claim.close()

    def test_published_schemas_validate_audit_envelope_and_overlay_entry(self) -> None:
        schemas = Path(__file__).resolve().parents[1] / "schemas"
        audit_schema = json.loads(
            (schemas / "approval-integrity-audit-result-v0.1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        overlay_schema = json.loads(
            (
                schemas / "approval-integrity-overlay-entry-v0.1.schema.json"
            ).read_text(encoding="utf-8")
        )
        operation_schema = json.loads(
            (
                schemas / "operation-exact-human-approval-v0.1.schema.json"
            ).read_text(encoding="utf-8")
        )
        for schema in (audit_schema, overlay_schema, operation_schema):
            Draft202012Validator.check_schema(schema)

        relative, _path = self._edge_receipt()
        audit = approval_integrity.audit_approval_integrity(self.root)
        Draft202012Validator(audit_schema).validate(audit)
        inspection = approval_integrity.inspect_approval_integrity_operation_receipt(
            self.root, relative, receipt_authentication_key=AUTH_KEY
        )
        plan = self._overlay_plan(relative, inspection, "review_required")
        context, claim = self._claim_for_overlay(plan)
        try:
            result = self._create_overlay(
                relative, inspection, plan, context, claim
            )
            directory = (
                self.root
                / "receipts"
                / "approval-integrity"
                / "overlays"
                / inspection["affected_id_sha256"].removeprefix("sha256:")
            )
            entry = json.loads(
                next(directory.glob("*.approval-integrity.json")).read_text(
                    encoding="utf-8"
                )
            )
            Draft202012Validator(overlay_schema).validate(entry)
            self.assertEqual(result["current_overlay_digest"], entry["entry_digest"])
        finally:
            claim.close()


if __name__ == "__main__":
    unittest.main()
