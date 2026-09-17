"""v0.4.22 hotfix for beta letters 161/162: a project-version-update that fails
after the human claim now says which fixed gate stopped it, the operation
journal names the post-verify stages, operation-control finds the parent
project's journal from the archive root, a started claim can be abandoned
after human review, and a budget-exhausted git probe is never reported as a
misconfigured origin.

Synthetic archives only; keys and dialogs are injected.
"""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from wom_kit import archive_cli
from wom_kit import archive_services
from wom_kit import exact_human_approval_workflow as workflow
from wom_kit import operation_control
from wom_kit.exact_human_approval import (
    CLAIMS_RELATIVE_ROOT,
    _claim_exact_human_approval_core,
    exact_human_approval_archive_identity_sha256,
)
from wom_kit.exact_human_approval_windows import (
    ExactHumanApprovalContext,
    ExactHumanApprovalOperation,
    _ExactHumanApprovalDecision,
)

KIT_ROOT = Path(__file__).resolve().parents[1]
AUTH_KEY = bytes(range(32))
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64


class _MemoryKey:
    def use_key(self, _root, consumer, *, create_if_missing=False):
        key = bytearray(AUTH_KEY)
        try:
            return consumer(memoryview(key))
        finally:
            key[:] = b"\0" * len(key)


class _ReadyClaim:
    def assert_ready_for_context(self, _context):
        return {"ok": True}

    def close(self):
        return None


def _context() -> ExactHumanApprovalContext:
    return ExactHumanApprovalContext(
        operation=ExactHumanApprovalOperation.project_version_update,
        archive_identity_sha256=exact_human_approval_archive_identity_sha256("archive:personal:fake-life"),
        plan_sha256=SHA_B,
        target_binding_sha256=SHA_C,
        reviewer_claim="person:synthetic-operator",
        review_binding_codes=("forward_only",),
        warning_codes=(),
    )


class CausePropagationTests(unittest.TestCase):
    def test_writer_failure_carries_the_fixed_inner_code_into_the_cli_projection(self) -> None:
        def writer(_claim):
            raise archive_services.ArchiveServiceError("project_version_update_approved_snapshot_unavailable")

        with self.assertRaises(workflow.ExactHumanApprovalWorkflowError) as raised:
            workflow._run_started_claim_writer(object(), writer, _ReadyClaim())
        error = raised.exception
        self.assertEqual(error.code, "exact_human_approval_state_unknown")
        self.assertEqual(error.cause_code, "project_version_update_approved_snapshot_unavailable")
        self.assertEqual(error.cause_stage, "domain_writer")
        self.assertIsNone(error.__cause__)  # still `from None`: no text travels
        self.assertEqual(
            archive_cli._project_version_update_content_free_cause(error),
            {"cause_code": "project_version_update_approved_snapshot_unavailable", "cause_stage": "domain_writer"},
        )

    def test_free_text_and_unknown_families_never_become_a_cause(self) -> None:
        def writer(_claim):
            raise archive_services.ArchiveServiceError("C:\\Users\\<user>\\private path leaked")

        with self.assertRaises(workflow.ExactHumanApprovalWorkflowError) as raised:
            workflow._run_started_claim_writer(object(), writer, _ReadyClaim())
        self.assertIsNone(raised.exception.cause_code)
        foreign = workflow.ExactHumanApprovalWorkflowError(
            "exact_human_approval_state_unknown", cause_code="some_other_family_code", cause_stage="domain_writer"
        )
        self.assertIsNone(archive_cli._project_version_update_content_free_cause(foreign))


class JournalStageTests(unittest.TestCase):
    def test_candidate_substages_and_post_claim_stages_are_named(self) -> None:
        class Journal:
            command = "project-version-update"

        safe = operation_control.OperationRunJournal._safe_stage
        self.assertEqual(safe(Journal(), "project-runtime-candidate-venv"), "materialize-runtime-candidate")
        self.assertEqual(safe(Journal(), "project-runtime-candidate-installed-payload-verify"), "materialize-runtime-candidate")
        for stage in ("native-approval", "post-claim-revalidate", "approval-bound", "durable-write"):
            self.assertEqual(safe(Journal(), stage), stage)
        self.assertEqual(safe(Journal(), "not-a-stage"), "unknown")


class OperationControlRootTests(unittest.TestCase):
    def test_recovery_plan_retries_with_the_parent_project_root(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-v0422-opctl-")
        self.addCleanup(temporary.cleanup)
        project = Path(temporary.name) / "project"
        (project / ".zettel-kasten").mkdir(parents=True)
        archive = project / "archive"
        archive.mkdir()
        (archive / "archive.yml").write_text("archive_id: archive:personal:fake\n", encoding="utf-8")
        seen: list[Path] = []

        def fake_recovery_plan(root, operation_ref):
            seen.append(Path(root))
            if Path(root).resolve() == archive.resolve():
                return {"ok": False, "state": "recovery_required", "blockers": ["operation_not_found"], "privacy_guards": {}}
            return {"ok": False, "state": "completed_failure_artifact_available", "blockers": [], "privacy_guards": {}}

        out = io.StringIO()
        with patch.object(operation_control, "recovery_plan", side_effect=fake_recovery_plan), redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = archive_cli.main([
                "operation-control", str(archive), "--operation-ref", "op:sha256:" + "a" * 64,
                "--action", "recovery-plan", "--dry-run", "--format", "json",
            ])
        result = json.loads(out.getvalue())
        self.assertEqual([p.resolve() for p in seen], [archive.resolve(), project.resolve()])
        self.assertEqual(result["state"], "completed_failure_artifact_available")
        self.assertTrue(result["inspection_root_resolved_to_parent_project"])
        self.assertNotIn(str(temporary.name), out.getvalue())


class AbandonStartedClaimTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-v0422-abandon-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", self.root)
        self.context = _context()
        self.decision = _ExactHumanApprovalDecision(
            approved=True, synthetic_acknowledged=False, reason_code="exact_human_approval_approved",
            plan_sha256=SHA_B, target_binding_sha256=SHA_C,
        )

    def make_claim(self, suffix: str):
        return _claim_exact_human_approval_core(
            self.root, self.context, self.decision, bytearray(AUTH_KEY),
            clock=lambda: datetime(2026, 9, 17, 5, 25, 56, tzinfo=timezone.utc),
            random_hex=lambda _size: suffix * 32,
        )

    def claim_document(self, suffix: str) -> dict:
        path = self.root.joinpath(*Path(CLAIMS_RELATIVE_ROOT).parts) / f"approval_{suffix * 32}.json"
        document = json.loads(path.read_bytes())
        return {key: document.get(key) for key in ("status", "finished_at", "failure_code")}

    def abandon(self, guard):
        return workflow._abandon_started_exact_human_approved_claims_core(
            self.root, self.context, guard,
            key_provider=_MemoryKey(),
            resume_boundary=lambda: archive_cli._project_version_update_resume_boundary(self.root),
        )

    def test_started_claim_is_closed_as_failed_without_a_dialog(self) -> None:
        claim = self.make_claim("a")
        claim.close()
        self.assertEqual(self.claim_document("a")["status"], "started")
        result = self.abandon(lambda _claim: True)
        self.assertEqual(result["abandoned_started_claim_count"], 1)
        self.assertEqual(result["failure_code"], workflow.ABANDONED_STARTED_CLAIM_FAILURE_CODE)
        self.assertFalse(result["native_approval_redisplayed"])
        document = self.claim_document("a")
        self.assertEqual(document["status"], "failed")
        self.assertEqual(document["failure_code"], "operator_abandoned_before_domain_write")
        self.assertIsNotNone(document["finished_at"])
        # a second abandon finds nothing to do; the failed claim is not a candidate
        self.assertEqual(self.abandon(lambda _claim: True)["abandoned_started_claim_count"], 0)

    def test_abandoned_claim_is_absence_for_resume_discovery(self) -> None:
        # The ordinary discovery refuses a failed claim of the same context
        # (it must never be read as absence) except the operator-abandoned one,
        # which is exactly what lets the claimless cancellation run afterwards.
        self.make_claim("e").close()
        self.abandon(lambda _claim: True)
        with archive_cli._project_version_update_resume_boundary(self.root) as boundary:
            candidates = workflow._authenticated_resume_candidates_with_key_core(
                self.root, self.context, lambda _c: True, lambda _c: True,
                key=memoryview(bytearray(AUTH_KEY)), filesystem_boundary=boundary,
            )
        self.assertEqual(candidates, ())
        # a claim failed for any other reason still blocks discovery
        other = self.make_claim("f")
        other.finalize_failed("synthetic_other_failure")
        other.close()
        with archive_cli._project_version_update_resume_boundary(self.root) as boundary:
            with self.assertRaises(workflow.ExactHumanApprovalWorkflowError) as raised:
                workflow._authenticated_resume_candidates_with_key_core(
                    self.root, self.context, lambda _c: True, lambda _c: True,
                    key=memoryview(bytearray(AUTH_KEY)), filesystem_boundary=boundary,
                )
        self.assertEqual(raised.exception.code, "exact_human_approval_resume_claim_invalid")

    def test_guard_rejected_claims_are_left_started(self) -> None:
        self.make_claim("b").close()
        result = self.abandon(lambda _claim: False)
        self.assertEqual(result["abandoned_started_claim_count"], 0)
        self.assertEqual(self.claim_document("b")["status"], "started")

    def test_a_succeeded_claim_for_the_context_refuses_the_abandon(self) -> None:
        claim = self.make_claim("c")
        claim.finalize_succeeded()
        claim.close()
        self.make_claim("d").close()
        with self.assertRaises(workflow.ExactHumanApprovalWorkflowError) as raised:
            self.abandon(lambda _claim: True)
        self.assertEqual(raised.exception.code, "exact_human_approval_resume_claim_invalid")
        self.assertEqual(self.claim_document("d")["status"], "started")


class VersionProbeBudgetTests(unittest.TestCase):
    def test_budget_summary_is_content_free_and_reports_exhaustion(self) -> None:
        self.assertIsNone(archive_services._wom_kit_git_probe_budget_summary())
        with archive_services._wom_kit_git_probe_budget(0.05) as state:
            state["exhausted"] = True
            state["git_calls_skipped"] = 3
            summary = archive_services._wom_kit_git_probe_budget_summary()
        self.assertEqual(summary["budget_exhausted"], True)
        self.assertEqual(summary["git_calls_skipped"], 3)
        self.assertEqual(set(summary), {"budget_seconds", "git_calls_started", "git_calls_skipped", "budget_exhausted"})
        self.assertGreaterEqual(archive_services.WOM_KIT_VERSION_GIT_PROBE_BUDGET_SECONDS, 45.0)


class UpgradeCheckNoticeTests(unittest.TestCase):
    def test_upgrade_check_without_progress_announces_its_scope(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-v0422-upgrade-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", root)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            archive_cli.main(["upgrade-check", str(root), "--dry-run", "--format", "json"])
        self.assertIn("[upgrade-check] running the full deep Doctor scan", err.getvalue())
        self.assertIn("not required before project-version-update", err.getvalue())
        self.assertNotIn(str(root), err.getvalue())


if __name__ == "__main__":
    unittest.main()
