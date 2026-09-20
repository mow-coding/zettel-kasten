"""v0.4.30 (beta letter 163 ⑥): started exact-approval claims can be listed,
reviewed and closed, and the approval-integrity audit pages per kind.

Synthetic archives only; keys, clocks and the dialog are injected.
"""

from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from wom_kit import approval_integrity
from wom_kit import archive_cli
from wom_kit import exact_approval_claims as claims
from wom_kit import exact_human_approval_workflow as workflow
from wom_kit import work_session_permission
from wom_kit.exact_human_approval import (
    CLAIMS_RELATIVE_ROOT,
    _claim_exact_human_approval_core,
    exact_human_approval_archive_identity_sha256,
)
from wom_kit.exact_human_approval_windows import (
    ExactHumanApprovalContext,
    ExactHumanApprovalOperation,
    _ExactHumanApprovalDecision,
    CURRENT_INTERACTIVE_INTENT_MECHANISM,
    _OPERATION_LABELS,
    _OPERATION_QUESTIONS,
)
from jsonschema import Draft202012Validator

KIT_ROOT = Path(__file__).resolve().parents[1]
AUTH_KEY = bytes(range(32))
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64
REVIEWER = "person:synthetic-operator"
NOW = datetime(2026, 9, 19, 12, 0, 0, tzinfo=timezone.utc)


class _MemoryKey:
    def use_key(self, _root, consumer, *, create_if_missing=False):
        key = bytearray(AUTH_KEY)
        try:
            return consumer(memoryview(key))
        finally:
            key[:] = b"\0" * len(key)


class _StubFinalizeClaim:
    def public_reference(self):
        return {
            "schema_version": "wom-kit/exact-human-approval-reference/v0.1",
            "approval_id": "approval_" + "f" * 32,
            "context_sha256": SHA_B,
            "approval_authority_sha256": SHA_C,
            "one_use": True,
        }


def _context(operation: ExactHumanApprovalOperation, *, plan: str = SHA_B) -> ExactHumanApprovalContext:
    return ExactHumanApprovalContext(
        operation=operation,
        archive_identity_sha256=exact_human_approval_archive_identity_sha256("archive:personal:fake-life"),
        plan_sha256=plan,
        target_binding_sha256=SHA_C,
        reviewer_claim=REVIEWER,
        review_binding_codes=("forward_only",),
        warning_codes=(),
    )


class _ClaimStoreCase(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", self.root)
        self.counter = 0

    def make_claim(self, operation: ExactHumanApprovalOperation, *, age: timedelta = timedelta(hours=2), finalize: str | None = None) -> str:
        self.counter += 1
        suffix = format(self.counter, "032x")
        plan = "sha256:" + format(self.counter, "064x")
        context = _context(operation, plan=plan)
        decision = _ExactHumanApprovalDecision(
            approved=True, synthetic_acknowledged=False, reason_code="exact_human_approval_approved",
            plan_sha256=plan, target_binding_sha256=SHA_C,
        )
        claim = _claim_exact_human_approval_core(
            self.root, context, decision, bytearray(AUTH_KEY),
            clock=lambda: NOW - age, random_hex=lambda _size: suffix,
        )
        try:
            if finalize == "succeeded":
                claim.finalize_succeeded()
            elif finalize == "failed":
                claim.finalize_failed("operator_abandoned_before_domain_write")
        finally:
            claim.close()
        return f"approval_{suffix}"

    def document(self, approval_id: str) -> dict:
        path = self.root.joinpath(*Path(CLAIMS_RELATIVE_ROOT).parts) / f"{approval_id}.json"
        return json.loads(path.read_bytes())

    def boundary(self):
        return archive_cli._project_version_update_resume_boundary(self.root)

    def listing(self, **kwargs):
        return claims.list_exact_human_approval_claims(
            self.root, key_provider=_MemoryKey(), claims_boundary=self.boundary,
            clock=lambda: NOW, **kwargs,
        )

    def plan(self, **kwargs):
        return claims.plan_exact_human_approval_claim_finalize(
            self.root, key_provider=_MemoryKey(), claims_boundary=self.boundary,
            clock=lambda: NOW, **kwargs,
        )

    def finalize(self, *, expected_plan_sha256: str, **kwargs):
        return claims.finalize_exact_human_approval_claims(
            self.root, key_provider=_MemoryKey(), claims_boundary=self.boundary,
            clock=lambda: NOW, expected_plan_sha256=expected_plan_sha256,
            exact_human_approval_claim=_StubFinalizeClaim(), **kwargs,
        )

    def write_receipt_referencing(self, approval_id: str) -> None:
        directory = self.root / "receipts" / "mint"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "zet_synthetic.mint.json").write_text(
            json.dumps({"exact_human_approval": {"exact_human_approval": {"approval_id": approval_id}}}),
            encoding="utf-8",
        )


class ListingTests(_ClaimStoreCase):
    def test_listing_projects_fixed_fields_and_counts_only_started_by_default(self) -> None:
        mint = [self.make_claim(ExactHumanApprovalOperation.mint_zet) for _ in range(3)]
        link = self.make_claim(ExactHumanApprovalOperation.zettel_objet_link)
        update = self.make_claim(ExactHumanApprovalOperation.project_version_update)
        self.make_claim(ExactHumanApprovalOperation.mint_zet, finalize="succeeded")
        self.make_claim(ExactHumanApprovalOperation.retire_draft, finalize="failed")
        result = self.listing()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["schema_version"], claims.LISTING_SCHEMA_VERSION)
        self.assertEqual(result["status_counts"], {"started": 5, "succeeded": 1, "failed": 1})
        self.assertEqual(result["started_operation_counts"], {"mint_zet": 3, "project_version_update": 1, "zettel_objet_link": 1})
        self.assertEqual(result["claim_count"], 5)
        self.assertEqual({row["approval_id"] for row in result["claims"]}, set(mint) | {link, update})
        self.assertEqual(
            set(result["claims"][0]),
            {"approval_id", "operation", "status", "started_at", "finished_at", "failure_code",
             "age_minutes", "approval_mechanism", "context_sha256", "review_binding_codes", "warning_codes",
             # v0.4.34 (letter 165 [A]): presenter evidence of a session-grant claim.
             "presenter_recorded", "session_presenter"},
        )
        self.assertEqual(result["claims"][0]["age_minutes"], 120)
        self.assertEqual(result["claims"][0]["approval_mechanism"], CURRENT_INTERACTIVE_INTENT_MECHANISM)
        rendered = json.dumps(result)
        self.assertNotIn(REVIEWER, rendered)
        self.assertNotIn("archive:personal:fake-life", rendered)
        self.assertNotIn(str(self.root), rendered)
        self.assertTrue(any("exact-approval-claim-finalize" in action for action in result["next_safe_actions"]))
        self.assertTrue(any("abandon-started-approval" in action for action in result["next_safe_actions"]))
        # filters
        self.assertEqual(self.listing(status="all")["claim_count"], 7)
        self.assertEqual(self.listing(status="failed")["claims"][0]["failure_code"], "operator_abandoned_before_domain_write")
        self.assertEqual(self.listing(operation="mint_zet")["claim_count"], 3)
        limited = self.listing(max_claims=2)
        self.assertFalse(limited["complete"])
        self.assertIn("exact_approval_claim_limit_exceeded", limited["blocker_codes"])

    def test_tampered_claim_is_counted_invalid_not_projected(self) -> None:
        good = self.make_claim(ExactHumanApprovalOperation.mint_zet)
        bad = self.make_claim(ExactHumanApprovalOperation.mint_zet)
        path = self.root.joinpath(*Path(CLAIMS_RELATIVE_ROOT).parts) / f"{bad}.json"
        path.write_bytes(path.read_bytes().replace(b'"started"', b'"failed" '))
        result = self.listing()
        self.assertFalse(result["ok"])
        self.assertEqual(result["invalid_claim_count"], 1)
        self.assertIn("exact_approval_claim_listing_entry_invalid", result["blocker_codes"])
        self.assertEqual([row["approval_id"] for row in result["claims"]], [good])

    def test_argument_validation_is_fixed_code(self) -> None:
        with self.assertRaises(claims.ExactApprovalClaimsError) as caught:
            self.listing(status="pending")
        self.assertEqual(caught.exception.code, "exact_approval_claim_argument_invalid")


class FinalizePlanTests(_ClaimStoreCase):
    def test_plan_selects_reviewed_started_claims_and_refuses_the_unsafe_ones(self) -> None:
        old_mint = self.make_claim(ExactHumanApprovalOperation.mint_zet)
        young_mint = self.make_claim(ExactHumanApprovalOperation.mint_zet, age=timedelta(minutes=5))
        update = self.make_claim(ExactHumanApprovalOperation.project_version_update)
        capture = self.make_claim(ExactHumanApprovalOperation.objet_capture)
        done = self.make_claim(ExactHumanApprovalOperation.mint_zet, finalize="succeeded")
        plan = self.plan(all_started=True)
        self.assertTrue(plan["ok"], plan)
        self.assertEqual([item["approval_id"] for item in plan["selected"]], [old_mint, capture])
        self.assertEqual(plan["skipped_too_recent_count"], 1)
        self.assertEqual(plan["excluded_project_version_update_count"], 1)
        self.assertEqual(plan["warnings"], ["exact_approval_claim_write_evidence_receipts_only"])
        self.assertEqual(plan["write_evidence"]["kind"], "receipts_only")
        self.assertTrue(plan["write_evidence"]["complete"])
        self.assertEqual(plan["failure_code"], claims.FINALIZE_FAILURE_CODE)
        self.assertTrue(plan["plan_sha256"].startswith("sha256:"))
        self.assertEqual(plan["plan_sha256"], self.plan(all_started=True)["plan_sha256"])
        # explicit selection: too recent, not started and project update are blockers
        blocked = self.plan(approval_ids=(young_mint, update, done))
        self.assertFalse(blocked["ok"])
        self.assertEqual(
            blocked["blockers"],
            sorted({"exact_approval_claim_too_recent", "exact_approval_claim_finalize_use_project_version_update_abandon", "exact_approval_claim_not_started"}),
        )
        self.assertIsNone(blocked["plan_sha256"])
        unknown = self.plan(approval_ids=("approval_" + "9" * 32,))
        self.assertEqual(unknown["blockers"], ["exact_approval_claim_not_found"])
        # a different set is a different digest; min-age override is a bound warning
        overridden = self.plan(all_started=True, min_age_minutes=0)
        self.assertEqual([item["approval_id"] for item in overridden["selected"]], [old_mint, capture, young_mint])
        self.assertIn("exact_approval_claim_min_age_overridden", overridden["warnings"])
        self.assertNotEqual(overridden["plan_sha256"], plan["plan_sha256"])
        rendered = json.dumps(plan)
        self.assertNotIn(REVIEWER, rendered)
        self.assertNotIn(str(self.root), rendered)

    def test_receipt_referencing_a_selected_claim_blocks_the_plan(self) -> None:
        referenced = self.make_claim(ExactHumanApprovalOperation.mint_zet)
        self.make_claim(ExactHumanApprovalOperation.mint_zet)
        self.write_receipt_referencing(referenced)
        plan = self.plan(all_started=True)
        self.assertFalse(plan["ok"])
        self.assertIn("exact_approval_claim_referenced_by_receipt", plan["blockers"])
        self.assertEqual(plan["write_evidence"]["referenced_count"], 1)
        self.assertEqual([item["receipt_reference_count"] for item in plan["selected"]], [1, 0])
        self.assertTrue(any("approval-integrity-audit" in action for action in plan["next_safe_actions"]))

    def test_receipts_are_scanned_as_byte_streams_and_only_real_failures_block(self) -> None:
        # v0.4.32 (letter 164 ②): a malformed or oversized receipt is still
        # searched for the id; only an I/O failure or a file above the
        # ceiling makes the scan incomplete, and that file is named.
        approval_id = self.make_claim(ExactHumanApprovalOperation.mint_zet)
        directory = self.root / "receipts" / "mint"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "broken.mint.json").write_bytes(b"{not json")
        big = directory / "big.mint.json"
        big.write_bytes(b"{" + b" " * (3 * 1024 * 1024) + b"}")
        plan = self.plan(all_started=True)
        self.assertTrue(plan["ok"], plan)
        self.assertEqual(plan["write_evidence"]["scan_method"], "byte_stream_search")
        self.assertEqual(plan["write_evidence"]["unreadable_file_count"], 0)
        self.assertEqual(plan["write_evidence"]["oversize_skipped_count"], 0)
        # an id inside a malformed or oversized file still counts as a reference
        big.write_bytes(b"{" + b" " * (3 * 1024 * 1024) + approval_id.encode() + b"}")
        referenced = self.plan(all_started=True)
        self.assertIn("exact_approval_claim_referenced_by_receipt", referenced["blockers"])
        big.unlink()
        with patch.object(claims, "_MAX_EVIDENCE_FILE_BYTES", 4):
            skipped = self.plan(all_started=True)
        self.assertFalse(skipped["ok"])
        self.assertIn("exact_approval_claim_evidence_scan_incomplete", skipped["blockers"])
        self.assertGreaterEqual(skipped["write_evidence"]["oversize_skipped_count"], 1)
        self.assertIn("receipts/mint/broken.mint.json", skipped["write_evidence"]["oversize_skipped_receipt_paths"])
        self.assertTrue(skipped["paths_echoed"])
        self.assertTrue(any("incomplete" in action for action in skipped["next_safe_actions"]))
        with patch.object(claims, "_scan_file_for_approval_ids", side_effect=OSError("PRIVATE-IO-CANARY")):
            unreadable = self.plan(all_started=True)
        self.assertGreaterEqual(unreadable["write_evidence"]["unreadable_file_count"], 1)
        self.assertIn("receipts/mint/broken.mint.json", unreadable["write_evidence"]["unreadable_receipt_paths"])
        self.assertNotIn("PRIVATE-IO-CANARY", json.dumps(unreadable))

    def test_nothing_selected_is_a_blocker(self) -> None:
        plan = self.plan(all_started=True)
        self.assertEqual(plan["blockers"], ["exact_approval_claim_finalize_nothing_selected"])


class FinalizeWriterTests(_ClaimStoreCase):
    def test_finalize_closes_each_claim_writes_a_receipt_and_leaves_no_started_claim(self) -> None:
        ids = [self.make_claim(ExactHumanApprovalOperation.mint_zet) for _ in range(3)]
        plan = self.plan(all_started=True)
        result = self.finalize(all_started=True, expected_plan_sha256=plan["plan_sha256"])
        self.assertTrue(result["ok"])
        self.assertEqual(result["finalized_count"], 3)
        self.assertEqual(result["backfilled_count"], 0)
        schema = json.loads((KIT_ROOT / "schemas" / "exact-human-approval-claim-finalize-receipt-v0.1.schema.json").read_text(encoding="utf-8"))
        for approval_id in ids:
            document = self.document(approval_id)
            self.assertEqual(document["status"], "failed")
            self.assertEqual(document["failure_code"], claims.FINALIZE_FAILURE_CODE)
            self.assertGreaterEqual(document["finished_at"], document["started_at"])
            receipt_path = self.root / "receipts" / "exact-human-approvals" / "claim-finalize" / f"{approval_id}.claim-finalize.json"
            receipt = json.loads(receipt_path.read_bytes())
            Draft202012Validator(schema).validate(receipt)
            self.assertEqual(receipt["target_approval_id"], approval_id)
            self.assertFalse(receipt["backfilled"])
            self.assertTrue(receipt["write_evidence"]["operation_receipted_on_success"])
            self.assertEqual(receipt["finalize_approval"]["approval_id"], "approval_" + "f" * 32)
        self.assertEqual(self.listing()["claim_count"], 0)
        self.assertEqual(self.listing(status="failed")["claim_count"], 3)
        # the closed claim is not absence for ordinary resume discovery
        self.assertNotEqual(claims.FINALIZE_FAILURE_CODE, workflow.ABANDONED_STARTED_CLAIM_FAILURE_CODE)
        rendered = json.dumps(result)
        self.assertNotIn(REVIEWER, rendered)
        self.assertNotIn(str(self.root), rendered)

    def test_plan_digest_mismatch_and_blocked_plan_refuse_before_any_swap(self) -> None:
        approval_id = self.make_claim(ExactHumanApprovalOperation.mint_zet)
        from wom_kit.archive_services import ArchiveServiceError

        with self.assertRaises(ArchiveServiceError) as caught:
            self.finalize(all_started=True, expected_plan_sha256="sha256:" + "0" * 64)
        self.assertEqual(str(caught.exception), "exact_approval_claim_finalize_plan_mismatch")
        self.assertEqual(self.document(approval_id)["status"], "started")
        self.write_receipt_referencing(approval_id)
        with self.assertRaises(ArchiveServiceError) as caught:
            self.finalize(all_started=True, expected_plan_sha256="sha256:" + "0" * 64)
        self.assertEqual(str(caught.exception), "exact_approval_claim_finalize_plan_blocked")
        self.assertEqual(self.document(approval_id)["status"], "started")

    def test_partial_failure_keeps_earlier_closings_and_the_next_plan_shrinks(self) -> None:
        ids = [self.make_claim(ExactHumanApprovalOperation.mint_zet) for _ in range(3)]
        plan = self.plan(all_started=True)
        original = claims._rehydrate_started_claim_without_context
        calls = {"n": 0}

        def _flaky(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                raise claims.ExactApprovalClaimsError("exact_approval_claim_finalize_state_unknown")
            return original(*args, **kwargs)

        from wom_kit.archive_services import ArchiveServiceError

        with patch.object(claims, "_rehydrate_started_claim_without_context", _flaky):
            with self.assertRaises(ArchiveServiceError) as caught:
                self.finalize(all_started=True, expected_plan_sha256=plan["plan_sha256"])
        self.assertEqual(str(caught.exception), "exact_approval_claim_finalize_state_unknown")
        self.assertEqual(self.document(ids[0])["status"], "failed")
        self.assertEqual(self.document(ids[1])["status"], "started")
        self.assertEqual(self.document(ids[2])["status"], "started")
        again = self.plan(all_started=True)
        self.assertEqual([item["approval_id"] for item in again["selected"]], ids[1:])
        self.assertNotEqual(again["plan_sha256"], plan["plan_sha256"])

    def test_closed_claim_without_receipt_is_backfilled_on_the_next_run(self) -> None:
        approval_id = self.make_claim(ExactHumanApprovalOperation.mint_zet)
        plan = self.plan(all_started=True)
        self.finalize(all_started=True, expected_plan_sha256=plan["plan_sha256"])
        receipt_path = self.root / "receipts" / "exact-human-approvals" / "claim-finalize" / f"{approval_id}.claim-finalize.json"
        receipt_path.unlink()
        again = self.plan(all_started=True)
        self.assertTrue(again["ok"], again)
        self.assertEqual(again["backfill_count"], 1)
        self.assertTrue(again["selected"][0]["backfill"])
        result = self.finalize(all_started=True, expected_plan_sha256=again["plan_sha256"])
        self.assertEqual(result["backfilled_count"], 1)
        self.assertTrue(json.loads(receipt_path.read_bytes())["backfilled"])
        self.assertEqual(self.plan(all_started=True)["blockers"], ["exact_approval_claim_finalize_nothing_selected"])


class OperationKindTests(unittest.TestCase):
    def test_finalize_is_grantable_since_v0436_with_korean_copy(self) -> None:
        kind = ExactHumanApprovalOperation.exact_approval_claim_finalize
        self.assertNotIn(kind, work_session_permission.ALWAYS_DIALOG_OPERATIONS)  # v0.4.36: grantable
        self.assertIn(kind, work_session_permission.GRANTABLE_OPERATIONS)
        self.assertTrue(_OPERATION_QUESTIONS[kind].endswith("까요?"))
        self.assertIn("클레임", _OPERATION_LABELS[kind])


class CliTests(_ClaimStoreCase):
    def run_cli(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with patch.object(workflow, "_production_key_provider", lambda: _MemoryKey()):
            with redirect_stdout(out), redirect_stderr(err):
                code = archive_cli.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_listing_command_is_read_only_and_content_free(self) -> None:
        approval_id = self.make_claim(ExactHumanApprovalOperation.mint_zet, age=timedelta(days=3))
        code, out, err = self.run_cli("exact-approval-claims", str(self.root), "--format", "json")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(err, "")
        document = json.loads(out)
        self.assertEqual(document["claim_count"], 1)
        self.assertEqual(document["claims"][0]["approval_id"], approval_id)
        self.assertNotIn(REVIEWER, out)
        self.assertNotIn(str(self.root), out)
        code, out, err = self.run_cli("approval-claims", str(self.root))
        self.assertEqual(code, 0, out + err)
        self.assertIn(approval_id, out)
        self.assertNotIn(REVIEWER, out)

    def test_finalize_command_dry_run_then_approve_through_the_broker(self) -> None:
        ids = [self.make_claim(ExactHumanApprovalOperation.mint_zet, age=timedelta(days=3)) for _ in range(2)]
        code, out, err = self.run_cli(
            "exact-approval-claim-finalize", str(self.root), "--all-started", "--dry-run", "--format", "json"
        )
        self.assertEqual(code, 0, out + err)
        plan = json.loads(out)
        self.assertEqual(plan["lifecycle_action"], "exact_approval_claim_finalize_plan")
        self.assertEqual([item["approval_id"] for item in plan["selected"]], ids)
        seen: dict = {}

        def _fake_execute(archive_root, context, writer, **_kwargs):
            seen["operation"] = context.operation
            seen["plan"] = context.plan_sha256
            seen["warnings"] = context.warning_codes
            result = dict(writer(_StubFinalizeClaim()))
            result["exact_human_approval"] = {"status": "succeeded"}
            return result

        with patch.object(archive_cli, "_execute_exact_human_approved_write", _fake_execute):
            code, out, err = self.run_cli(
                "exact-approval-claim-finalize", str(self.root), "--all-started", "--approve",
                "--reviewed-by", REVIEWER, "--expected-plan-sha256", plan["plan_sha256"], "--format", "json",
            )
        self.assertEqual(code, 0, out + err)
        self.assertEqual(seen["operation"], ExactHumanApprovalOperation.exact_approval_claim_finalize)
        self.assertEqual(seen["plan"], plan["plan_sha256"])
        result = json.loads(out)
        self.assertEqual(result["finalized_count"], 2)
        for approval_id in ids:
            self.assertEqual(self.document(approval_id)["status"], "failed")
        self.assertNotIn(REVIEWER, out)

    def test_finalize_command_refusals_are_fixed_codes(self) -> None:
        approval_id = self.make_claim(ExactHumanApprovalOperation.mint_zet, age=timedelta(days=3))
        code, out, err = self.run_cli("exact-approval-claim-finalize", str(self.root), "--all-started", "--format", "json")
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)["reason_codes"], ["exact_approval_claim_finalize_execution_mode_invalid"])
        code, out, err = self.run_cli("exact-approval-claim-finalize", str(self.root), "--all-started", "--approve", "--format", "json")
        self.assertEqual(json.loads(out)["reason_codes"], ["exact_approval_claim_finalize_approval_evidence_required"])
        code, out, err = self.run_cli(
            "exact-approval-claim-finalize", str(self.root), "--all-started", "--approve",
            "--reviewed-by", REVIEWER, "--expected-plan-sha256", "sha256:" + "0" * 64, "--format", "json",
        )
        self.assertEqual(json.loads(out)["reason_codes"], ["exact_approval_claim_finalize_plan_mismatch"])
        self.assertEqual(self.document(approval_id)["status"], "started")
        self.write_receipt_referencing(approval_id)
        code, out, err = self.run_cli(
            "exact-approval-claim-finalize", str(self.root), "--all-started", "--approve",
            "--reviewed-by", REVIEWER, "--expected-plan-sha256", "sha256:" + "0" * 64, "--format", "json",
        )
        self.assertEqual(json.loads(out)["reason_codes"], ["exact_approval_claim_finalize_plan_blocked"])
        self.assertEqual(err, "")

    def test_command_status_inventory_classifies_both_commands(self) -> None:
        from wom_kit import command_status

        inventory = command_status.build_command_status_inventory(archive_cli.build_parser(), set())
        by_path = {row["canonical_path"]: row for row in inventory["commands"]}
        self.assertEqual(by_path["exact-approval-claims"]["approval_status"], "approval_not_exposed")
        self.assertEqual(by_path["exact-approval-claim-finalize"]["approval_status"], "approval_available")


class AuditPagingTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", self.root)
        mint = self.root / "receipts" / "mint"
        mint.mkdir(parents=True, exist_ok=True)
        for index in range(12):
            (mint / f"zet_{index:02d}.mint.json").write_text(json.dumps({"receipt_id": f"receipt:mint:zet_{index:02d}"}), encoding="utf-8")
        edges = self.root / "receipts" / "edges"
        edges.mkdir(parents=True, exist_ok=True)
        (edges / "edge_a.zettel-edge.json").write_text(json.dumps({"receipt_kind": "zettel_edge_write"}), encoding="utf-8")

    def test_pages_are_name_ordered_and_the_unpaged_result_is_unchanged(self) -> None:
        schema_v2 = json.loads((KIT_ROOT / "schemas" / "approval-integrity-audit-result-v0.2.schema.json").read_text(encoding="utf-8"))
        schema_v1 = json.loads((KIT_ROOT / "schemas" / "approval-integrity-audit-result-v0.1.schema.json").read_text(encoding="utf-8"))
        pages = [
            approval_integrity.audit_approval_integrity(self.root, max_receipts=5, kind="canonical_mint", offset=offset)
            for offset in (0, 5, 10)
        ]
        self.assertEqual([page["receipt_count"] for page in pages], [5, 5, 2])
        self.assertEqual([page["page"]["next_offset"] for page in pages], [5, 10, None])
        self.assertEqual([page["page"]["exhausted"] for page in pages], [False, False, True])
        self.assertEqual(pages[0]["page"]["total_in_kind"], 12)
        for page in pages:
            self.assertEqual(page["schema_version"], approval_integrity.AUDIT_PAGED_SCHEMA_VERSION)
            Draft202012Validator(schema_v2).validate(page)
            self.assertNotIn("approval_integrity_receipt_limit_exceeded", page["blocker_codes"])
            self.assertTrue(all(row["affected_kind"] == "canonical_mint" for row in page["results"]))
        beyond = approval_integrity.audit_approval_integrity(self.root, max_receipts=5, kind="canonical_mint", offset=40)
        self.assertEqual(beyond["receipt_count"], 0)
        self.assertTrue(beyond["page"]["exhausted"])
        # unpaged: v0.1 document, single global cap, limit blocker preserved
        default = approval_integrity.audit_approval_integrity(self.root, max_receipts=4096)
        self.assertEqual(default["schema_version"], approval_integrity.AUDIT_SCHEMA_VERSION)
        self.assertNotIn("page", default)
        Draft202012Validator(schema_v1).validate(default)
        self.assertEqual(default["receipt_count"], 13)
        capped = approval_integrity.audit_approval_integrity(self.root, max_receipts=1)
        self.assertEqual(capped["receipt_count"], 1)
        self.assertIn("approval_integrity_receipt_limit_exceeded", capped["blocker_codes"])
        for bad in ({"kind": "mint"}, {"offset": -1}, {"offset": 3}):
            with self.assertRaises(approval_integrity.ApprovalIntegrityError) as caught:
                approval_integrity.audit_approval_integrity(self.root, max_receipts=5, **bad)
            self.assertEqual(caught.exception.code, "approval_integrity_argument_invalid")


if __name__ == "__main__":
    unittest.main()
