"""v0.4.30 (beta letter 163): inbox attention on write results (⑫), edges on
inbox drafts and session-mode revert-edge (③c, [G]), discard-draft inbound
edge count (④c), the mint edge-target check (11) and the create-draft
truncated objet reference blocker (⑩).

Synthetic archives only; keys and the dialog are injected.
"""

from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import test_cli
import test_v0430_letter163 as gate_tests
from wom_kit import archive_cli, archive_services, completion_workflows
from wom_kit import work_session_command
from wom_kit.exact_human_approval import (
    _claim_exact_human_approval_core as claim_exact_human_approval,
)
from wom_kit.exact_human_approval_windows import (
    ExactHumanApprovalOperation,
    _ExactHumanApprovalDecision as ExactHumanApprovalDecision,
)
from wom_kit.operation_approval_binding import (
    zettel_edge_approval_binding,
    zettel_edge_revert_approval_binding,
)

KIT_ROOT = Path(__file__).resolve().parents[1]
REVIEWER = "person:synthetic-operator"
DRAFT_A = "zet_20260519_draft_ai_lunch_note"
INBOX_ATTENTION_KEYS = {
    "status", "complete", "unpublished_draft_count", "possible_out_of_pipeline_draft_count",
    "mint_readiness_gap_count", "oldest_draft_age_days", "review_recommended", "human_summary",
    "next_command", "audit_schema", "audit_digest", "body_text_read", "paths_titles_or_body_echoed",
}


def _run_cli(*args: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = archive_cli.main(list(args))
    return code, out.getvalue(), err.getvalue()


class _GateFixtureCase(unittest.TestCase):
    """Composes the mint-gate fixture: a fidelity draft, a fake dialog, a memory key."""

    def setUp(self) -> None:
        self.gate = gate_tests.Letter163MintGateTests("setUp")
        self.gate.setUp()
        self.addCleanup(self.gate.doCleanups)
        self.root = self.gate.root
        self.fixture = self.gate.fixture

    def run_cli(self, *args: str) -> tuple[int, dict]:
        return self.gate.run_cli(*args)

    def mint_args(self, path: Path) -> list[str]:
        return self.gate.mint_args(path)

    def fidelity_draft(self, **kwargs) -> Path:
        return self.gate.fidelity_draft(**kwargs)


class InboxAttentionTests(_GateFixtureCase):
    def test_approved_writes_carry_the_inbox_attention_block(self):
        path = self.fidelity_draft()
        code, preview = self.run_cli(*self.mint_args(path), "--dry-run")
        self.assertEqual(code, 0, preview)
        self.assertNotIn("inbox_attention", preview)
        before = archive_services.ai_start_here_inbox_attention(self.root)["unpublished_draft_count"]
        code, minted = self.run_cli(
            *self.mint_args(path), "--approve",
            "--expected-source-fidelity-plan-sha256", preview["current_source_fidelity_plan_sha256"],
        )
        self.assertEqual(code, 0, minted)
        attention = minted["inbox_attention"]
        self.assertEqual(set(attention), INBOX_ATTENTION_KEYS)
        self.assertFalse(attention["paths_titles_or_body_echoed"])
        self.assertFalse(attention["body_text_read"])
        self.assertEqual(attention["unpublished_draft_count"], before)
        zettel_id = minted["zettel_id"]
        code, retire_preview = self.run_cli("retire-draft", str(self.root), "--zettel-id", zettel_id, "--dry-run")
        self.assertEqual(code, 0, retire_preview)
        self.assertNotIn("inbox_attention", retire_preview)
        code, retired = self.run_cli(
            "retire-draft", str(self.root), "--zettel-id", zettel_id, "--approve", "--reviewed-by", REVIEWER,
        )
        self.assertEqual(code, 0, retired)
        self.assertEqual(retired["inbox_attention"]["unpublished_draft_count"], before - 1)
        rendered = json.dumps(minted) + json.dumps(retired)
        self.assertNotIn(str(self.root), rendered)

    def test_a_counting_failure_never_fails_the_write(self):
        path = self.fidelity_draft(draft_id="zet_20260919_102_letter163")
        code, preview = self.run_cli(*self.mint_args(path), "--dry-run")
        self.assertEqual(code, 0, preview)

        def _boom(*_args, **_kwargs):
            raise OSError("synthetic inbox failure")

        with patch.object(archive_services, "inbox_pipeline_audit", _boom):
            code, minted = self.run_cli(
                *self.mint_args(path), "--approve",
                "--expected-source-fidelity-plan-sha256", preview["current_source_fidelity_plan_sha256"],
            )
        self.assertEqual(code, 0, minted)
        self.assertTrue(minted["ok"])
        self.assertEqual(minted["inbox_attention"]["status"], "unavailable")
        self.assertEqual(set(minted["inbox_attention"]), INBOX_ATTENTION_KEYS)
        self.assertTrue(minted["inbox_attention"]["review_recommended"])

    def test_create_draft_approve_result_and_text_line(self):
        object_id = self.fixture.manifested_source(b"Exact source bytes for the create-draft attention test.")
        kwargs = self.fixture.ai_kwargs(
            object_id, draft_id="zet_20260919_103_letter163", title="Attention on create",
            body="A faithful summary long enough to stand alone as a first self-contained note about attention.",
            mode="faithful_summary",
        )
        result = self.fixture.create_approved(kwargs)
        self.assertTrue(result["ok"], result)
        # the service result is untouched; the CLI attaches the block
        self.assertNotIn("inbox_attention", result)
        attached = archive_services.attach_inbox_attention(result, self.root)
        self.assertEqual(set(attached["inbox_attention"]), INBOX_ATTENTION_KEYS)
        self.assertIn(attached["inbox_attention"]["status"], {"attention", "clear", "incomplete"})

    def test_work_session_create_and_claim_envelopes_carry_the_block(self):
        from wom_kit import work_session_service

        with patch.object(work_session_service, "create_task", return_value={"ok": True, "schema": "x"}):
            envelope = work_session_command.dispatch_work_session_management(
                self.root, action="create", approve=True, client_app_ref="app:x", task_route_ref="route:y",
                request={"label": "synthetic", "reviewer_claim": REVIEWER},
            )
        self.assertTrue(envelope["ok"], envelope)
        self.assertEqual(set(envelope["inbox_attention"]), INBOX_ATTENTION_KEYS)
        with patch.object(work_session_service, "apply_or_resume_task_claim", return_value={"ok": True}):
            claimed = work_session_command.dispatch_work_session_management(
                self.root, action="claim", apply=True, client_app_ref="app:x", task_route_ref="route:y",
                work_session_ref="session:z",
            )
        self.assertEqual(claimed["mode"], "claim_apply")
        self.assertIn("inbox_attention", claimed)
        with patch.object(work_session_service, "initialize_task_request", return_value={"ok": True}):
            init = work_session_command.dispatch_work_session_management(
                self.root, action="request-init", dry_run=True, client_app_ref="app:x",
            )
        self.assertNotIn("inbox_attention", init)
        with patch.object(work_session_service, "create_task", return_value={"ok": False, "reason_code": "x"}):
            failed = work_session_command.dispatch_work_session_management(
                self.root, action="create", approve=True, client_app_ref="app:x", task_route_ref="route:y",
                request={"label": "synthetic", "reviewer_claim": REVIEWER},
            )
        self.assertNotIn("inbox_attention", failed)


class CreateDraftTruncatedReferenceTests(_GateFixtureCase):
    def test_truncated_objet_reference_blocks_create_draft_before_approval(self):
        object_id = self.fixture.manifested_source(b"Exact source bytes for the truncated reference test.")
        kwargs = self.fixture.ai_kwargs(
            object_id, draft_id="zet_20260919_104_letter163", title="Truncated reference",
            body="See objet:sha256:deadbeef1234 for the table; the summary stands alone otherwise.",
            mode="faithful_summary",
        )
        preview = archive_services.create_draft_zettel(self.root, dry_run=True, approved=False, **kwargs)
        self.assertFalse(preview["ok"])
        self.assertIn("draft_body_truncated_objet_reference", preview["blockers"])
        self.assertNotIn("deadbeef1234", json.dumps(preview))
        self.assertFalse((self.root / "inbox" / "zet_20260919_104_letter163.md").exists())


class EdgeTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", self.root)
        self.cli = test_cli.ArchiveCliTests("setUp")

    def bound_writer(self, binding, writer):
        context = binding.context(archive_id=archive_services.read_archive_id(self.root), reviewer_claim=REVIEWER)
        claim = claim_exact_human_approval(
            self.root, context,
            ExactHumanApprovalDecision(
                approved=True, synthetic_acknowledged=False, reason_code="exact_human_approval_approved",
                plan_sha256=context.plan_sha256, target_binding_sha256=context.target_binding_sha256,
            ),
            bytearray(b"e" * 32),
        )
        try:
            result = writer(claim, binding)
            if result.get("ok") is True:
                claim.finalize_succeeded()
            else:
                claim.finalize_failed("operation_blocked")
            return result
        finally:
            claim.close()

    def second_draft(self, zettel_id: str) -> Path:
        return self.cli.make_batch_ready_draft(self.root, zettel_id, "Second draft", "Body of the second draft.\n")

    def write_edge(self, from_zettel: str, target: str) -> dict:
        preview = archive_services.zettel_edge_write(
            self.root, from_zettel=from_zettel, target_ref=target, edge_type="semantic", visibility="private", dry_run=True,
        )
        self.assertTrue(preview["ok"], preview)
        binding = zettel_edge_approval_binding(preview)
        return self.bound_writer(
            binding,
            lambda claim, bound: archive_services.zettel_edge_write(
                self.root, from_zettel=from_zettel, target_ref=target, edge_type="semantic", visibility="private",
                approve=True, reviewed_by=REVIEWER,
                expected_exact_approval_plan_sha256=bound.plan_sha256,
                expected_exact_approval_target_binding_sha256=bound.target_binding_sha256,
                exact_human_approval_claim=claim,
            ),
        )

    def test_edges_on_inbox_drafts_can_be_reverted_and_follow_a_minted_source(self):
        draft_b = "zet_20260519_draft_second"
        self.second_draft(draft_b)
        archive_services.index_archive(self.root)
        written = self.write_edge(draft_b, DRAFT_A)
        self.assertTrue(written["ok"], written)
        receipt = written["receipt_path"]
        preview = archive_services.zettel_edge_revert(self.root, receipt=receipt, dry_run=True)
        self.assertTrue(preview["ok"], preview)
        self.assertNotIn("must point under zettels/", " ".join(preview["blockers"]))
        # the source moves to zettels/ (as a mint does): the receipt still resolves by id
        source = self.root / "inbox" / f"{draft_b}.md"
        moved = self.root / "zettels" / f"{draft_b}.md"
        moved.write_bytes(source.read_bytes())
        source.unlink()
        archive_services.index_archive(self.root)
        relocated = archive_services.zettel_edge_revert(self.root, receipt=receipt, dry_run=True)
        self.assertTrue(relocated["ok"], relocated)
        self.assertEqual(relocated["source"]["path"], f"zettels/{draft_b}.md")
        binding = zettel_edge_revert_approval_binding(relocated)
        reverted = self.bound_writer(
            binding,
            lambda claim, bound: archive_services.zettel_edge_revert(
                self.root, receipt=receipt, approve=True, reviewed_by=REVIEWER,
                expected_exact_approval_plan_sha256=bound.plan_sha256,
                expected_exact_approval_target_binding_sha256=bound.target_binding_sha256,
                exact_human_approval_claim=claim,
            ),
        )
        self.assertTrue(reverted["ok"], reverted)
        frontmatter, _body = archive_services.require_readable_zettel_text(moved.read_text(encoding="utf-8"))
        self.assertFalse(frontmatter.get("edges"))
        # a source id that no longer exists anywhere is still a missing source
        moved.unlink()
        archive_services.index_archive(self.root)
        gone = archive_services.zettel_edge_revert(self.root, receipt=receipt, dry_run=True)
        self.assertIn("edge receipt source zettel is missing.", gone["blockers"])

    def test_revert_edge_approve_reaches_the_broker_without_exact_local(self):
        draft_b = "zet_20260519_draft_second"
        self.second_draft(draft_b)
        archive_services.index_archive(self.root)
        receipt = self.write_edge(draft_b, DRAFT_A)["receipt_path"]
        seen = {}

        def _fake_execute(archive_root, context, writer, **_kwargs):
            seen["operation"] = context.operation
            return {"ok": True, "write_status": "stubbed", "exact_human_approval": {"status": "succeeded"}}

        with patch.object(archive_cli, "_execute_exact_human_approved_write", _fake_execute):
            code, out, err = _run_cli(
                "revert-edge", str(self.root), "--receipt", receipt, "--approve", "--reviewed-by", REVIEWER, "--format", "json",
            )
        self.assertEqual(code, 0, out + err)
        self.assertEqual(seen["operation"], ExactHumanApprovalOperation.zettel_edge_revert)
        self.assertNotIn("compound_exact_human_approval_binding_required", out)
        # --exact-local is still accepted
        parser = archive_cli.build_parser()
        args = parser.parse_args(["revert-edge", str(self.root), "--receipt", receipt, "--dry-run", "--exact-local"])
        self.assertTrue(args.exact_local)
        self.assertIsNone(parser._subparsers._group_actions[0].choices["revert-edge"]._defaults.get("_wom_approval_scope"))

    def test_discard_plan_counts_inbound_edges_from_the_index(self):
        draft_b = "zet_20260519_draft_second"
        self.second_draft(draft_b)
        archive_services.index_archive(self.root)
        before = completion_workflows.draft_discard_plan(self.root, zettel_id=DRAFT_A, reason="synthetic")
        self.assertEqual(before["summary"]["inbound_edge_count"], 0)
        self.assertEqual(before["summary"]["inbound_edge_scan"], "index")
        self.write_edge(draft_b, DRAFT_A)
        archive_services.index_archive(self.root)
        after = completion_workflows.draft_discard_plan(self.root, zettel_id=DRAFT_A, reason="synthetic")
        self.assertEqual(after["summary"]["inbound_edge_count"], 1)
        self.assertEqual(after["warnings"], ["discard_draft_inbound_edges_present"])
        self.assertTrue(any("related-zets" in action for action in after["next_safe_actions"]))
        self.assertEqual(after["summary"]["plan_sha256"], before["summary"]["plan_sha256"])
        self.assertNotIn(draft_b, json.dumps(after))
        (self.root / archive_services.INDEX_RELATIVE_PATH).unlink()
        missing = completion_workflows.draft_discard_plan(self.root, zettel_id=DRAFT_A, reason="synthetic")
        self.assertEqual(missing["summary"]["inbound_edge_scan"], "index_missing")
        self.assertEqual(missing["warnings"], [])

    def test_mint_dry_run_reports_discarded_and_missing_edge_targets(self):
        path = self.cli.make_fake_lunch_draft_promotion_ready(self.root)
        frontmatter, body = archive_services.require_readable_zettel_text(path.read_text(encoding="utf-8"))
        frontmatter["edges"] = [
            {"type": "continues", "target": "zet_20260904_discarded_draft"},
            {"type": "continues", "target": "zet_20240505_fake_company_onboarding_insight"},
        ]
        path.write_text("---\n" + archive_cli.dump_yaml(frontmatter) + "---\n\n" + body, encoding="utf-8")
        receipts = self.root / "receipts" / "discarded-drafts"
        receipts.mkdir(parents=True, exist_ok=True)
        (receipts / "zet_20260904_discarded_draft.0123456789abcdef.discard.json").write_text("{}", encoding="utf-8")
        archive_services.index_archive(self.root)
        preview = archive_services.mint_zettel_dry_run(self.root, zettel_id=DRAFT_A)
        check = preview["edge_target_check"]
        self.assertEqual(check, {"checked": 2, "missing": 1, "discarded": 1, "index_used": True, "target_ids_echoed": False})
        self.assertTrue(any("edge_target_check" in action for action in preview["next_safe_actions"]))
        self.assertNotIn("edge_target_discarded", preview["warnings"])
        self.assertNotIn("zet_20260904_discarded_draft", json.dumps(check))


if __name__ == "__main__":
    unittest.main()
