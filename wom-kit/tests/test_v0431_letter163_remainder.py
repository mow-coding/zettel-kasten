"""v0.4.31 (beta letter 163 remainder): create-draft argument hints (⑦), the
gating edge-target warnings (item 11), warning explanations inside
quality_check (⑪), project-version-update failures that always name a cause
and dry-runs that describe the existing transaction (②), and the index fact
announced by edge / revert-edge / intake-chain dry-runs (⑧).

Synthetic archives only; the dialog and keys are never opened.
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
from jsonschema import Draft202012Validator
from wom_kit import approval_handoff, archive_cli, archive_services

KIT_ROOT = Path(__file__).resolve().parents[1]
REVIEWER = "person:synthetic-operator"
DRAFT_A = "zet_20260519_draft_ai_lunch_note"
HANDOFF_SCHEMA = json.loads((KIT_ROOT / "schemas" / "approval-handoff-v0.1.schema.json").read_text(encoding="utf-8"))


def _run_cli_split(*args: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = archive_cli.main(list(args))
    return code, out.getvalue(), err.getvalue()


class CreateDraftHintTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = gate_tests.Letter163MintGateTests("setUp")
        self.gate.setUp()
        self.addCleanup(self.gate.doCleanups)
        self.root = self.gate.root
        self.fixture = self.gate.fixture

    def test_runtime_identification_blocker_names_the_options(self) -> None:
        object_id = self.fixture.manifested_source(b"Exact source bytes for the hint test.")
        kwargs = self.fixture.ai_kwargs(object_id, draft_id="zet_20260919_201_letter163", body="A faithful summary long enough to stand on its own as a first note.", mode="faithful_summary")
        kwargs["assisted_by"] = []
        kwargs["created_by"] = "ai_runtime:test"
        preview = archive_services.create_draft_zettel(self.root, dry_run=True, approved=False, **kwargs)
        self.assertFalse(preview["ok"])
        self.assertIn("ai_draft_assisted_by_required", preview["blockers"])
        self.assertTrue(any("assisting AI runtime" in item for item in preview["blockers"]))
        hints = [item for item in preview["next_safe_actions"] if "--assisted-by" in item and "--supervised-by" in item]
        self.assertEqual(len(hints), 1)
        self.assertNotIn("ai_runtime:test", " ".join(preview["next_safe_actions"]))
        self.assertTrue(any("approval_replay values are null" in item for item in preview["next_safe_actions"]))
        self.assertTrue(all(value is None for value in preview["approval_replay"].values()))

    def test_handoff_marks_omit_when_null_and_validates(self) -> None:
        object_id = self.fixture.manifested_source(b"Exact source bytes for the handoff test.")
        kwargs = self.fixture.ai_kwargs(object_id, draft_id="zet_20260919_202_letter163", body="A faithful summary long enough to stand on its own as a first note.", mode="faithful_summary")
        preview = archive_services.create_draft_zettel(self.root, dry_run=True, approved=False, **kwargs)
        self.assertTrue(preview["ok"], preview)
        handoff = preview["approval_handoff"]
        Draft202012Validator(HANDOFF_SCHEMA).validate(handoff)
        by_option = {item["option"]: item for item in handoff["arguments"]}
        self.assertTrue(by_option["--profile-id"]["omit_when_null"])
        self.assertFalse(by_option["--profile-id"]["required"])
        self.assertIsNone(by_option["--profile-id"]["value"])
        self.assertTrue(by_option["--expected-type"]["omit_when_null"])
        self.assertFalse(by_option["--draft-approved-by"]["omit_when_null"])
        # the mint handoff shares the builder and keeps the default
        self.assertFalse(approval_handoff.argument("--x", required=True, value_source="operator_input")["omit_when_null"])

    def test_literal_none_replay_value_is_refused_before_any_archive_read(self) -> None:
        with patch.object(archive_services, "require_existing_archive_root") as root_read:
            code, out, err = _run_cli_split(
                "create-draft", str(self.root), "--title", "x", "--body", "y", "--creation-mode", "ai_assisted",
                "--assisted-by", "ai_runtime:test", "--approve", "--draft-approved-by", REVIEWER,
                "--draft-id", "zet_20260919_203_letter163", "--created-at", "2026-09-19T10:00:00+09:00",
                "--expected-body-sha256", "0" * 64, "--profile-id", "None", "--format", "json",
            )
        self.assertEqual(code, 1, out + err)
        self.assertEqual(json.loads(out)["reason_codes"], ["create_draft_replay_value_null_literal"])
        root_read.assert_not_called()


class WarningExplanationTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", self.root)
        self.cli = test_cli.ArchiveCliTests("setUp")

    def test_status_contradiction_explanation_names_lines_not_words(self) -> None:
        body = "First line of the note.\n\nThe migration was completed.\n\nThe follow-up is still pending and the review is in progress.\n"
        path = self.cli.make_fake_lunch_draft_promotion_ready(self.root, replacement_body=body)
        preview = archive_services.mint_zettel_dry_run(self.root, zettel_id=DRAFT_A)
        self.assertIn("internal_status_consistency_review_required", preview["warnings"])
        explanations = {item["code"]: item for item in preview["quality_check"]["warning_explanations"]}
        status = explanations["internal_status_consistency_review_required"]
        self.assertEqual(status["completed_marker_count"], 1)
        self.assertEqual(status["completed_marker_body_lines"], [3])
        self.assertEqual(status["pending_marker_count"], 2)
        self.assertEqual(status["pending_marker_body_lines"], [5])
        self.assertFalse(status["matched_text_echoed"])
        self.assertFalse(preview["quality_check"]["privacy_guards"]["matched_status_markers_echoed"])
        rendered = json.dumps(preview["quality_check"])
        for word in ("completed", "pending", "in progress"):
            self.assertNotIn(word, rendered.replace("internal_status_consistency_review_required", "").replace("any_completed_marker_and_any_pending_marker_anywhere_in_body", "").replace("completed_marker", "").replace("pending_marker", ""))
        # the text renderer prints counts and lines only
        code, out, err = _run_cli_split("mint-zet", str(self.root), "--zettel-id", DRAFT_A, "--dry-run")
        self.assertIn("completed-status markers: 1 at body lines 3", out)
        self.assertIn("pending-status markers: 2 at body lines 5", out)
        self.assertNotIn("migration", out)
        clean = self.cli.make_fake_lunch_draft_promotion_ready(self.root, replacement_body="A calm note with no status wording at all.\n")
        again = archive_services.mint_zettel_dry_run(self.root, zettel_id=DRAFT_A)
        self.assertEqual(again["quality_check"]["warning_explanations"], [])
        self.assertNotIn("internal_status_consistency_review_required", again["warnings"])
        self.assertTrue(path.is_file() and clean.is_file())


class PreflightCauseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cli = test_cli.ArchiveCliTests("setUp")

    def test_family_cause_is_class_identity_only(self) -> None:
        cause = archive_cli._project_version_update_family_cause(OSError(2, "secret path C:/x"), journal_stage="project-preflight")
        self.assertEqual(cause["cause_code"], "project_version_update_failure_family_os_error")
        self.assertEqual(cause["cause_stage"], "project-preflight")
        self.assertEqual(cause["cause_code_source"], "exception_family")
        self.assertEqual(archive_cli._project_version_update_family_cause(ValueError("x"))["cause_stage"], "unknown")
        self.assertEqual(
            archive_cli._project_version_update_family_cause(archive_services.ArchiveServiceError("free text with C:/Users/x"))["cause_code"],
            "project_version_update_failure_family_archive_service_error",
        )
        self.assertEqual(archive_cli._project_version_update_family_cause(RuntimeError("x"))["cause_code"], "project_version_update_failure_family_other_error")

    def test_direct_failure_without_a_token_still_records_a_cause(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            output_relative = ".zettel-kasten/diagnostics/project-version-update-family.json"
            with patch.object(archive_services, "wom_kit_project_version_update", side_effect=OSError(13, "permission denied on C:/private/secret.json")):
                code, out, err = _run_cli_split(
                    "project-version-update", str(project_root), "--target", "v0.4.30", "--dry-run", "--output", output_relative, "--format", "json",
                )
            self.assertEqual(code, 1)
            self.assertIn("inner reason (fixed code): project_version_update_failure_family_os_error", err)
            self.assertNotIn("secret.json", out + err)
            saved = json.loads((project_root / output_relative).read_text(encoding="utf-8"))
            error_payload = saved["cli_execution"]["error"]
            self.assertEqual(error_payload["cause_code"], "project_version_update_failure_family_os_error")
            self.assertEqual(error_payload["cause_code_source"], "exception_family")
            self.assertFalse(error_payload["raw_message_stored"])
            self.assertNotIn("secret.json", json.dumps(saved))

    def test_existing_transaction_projection_is_fail_quiet_and_content_free(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            block = archive_services.project_update_existing_transaction_read_only(project_root)
            self.assertEqual(block["schema"], archive_services.PROJECT_UPDATE_EXISTING_TRANSACTION_SCHEMA)
            self.assertIn(block["status"], {"absent", "unknown"})
            self.assertEqual(block["abandon_applicability_basis"], "journal_shape_only_live_components_unchecked")
            self.assertFalse(block["private_identifiers_echoed"])
            self.assertNotIn(str(project_root), json.dumps(block))
            # the terminal-cleanup gate carries the block
            error = archive_services.ArchiveServiceError("project_version_update_terminal_cleanup_required")
            output_relative = ".zettel-kasten/diagnostics/project-version-update-existing.json"
            with patch.object(archive_services, "wom_kit_project_version_update", side_effect=error):
                code, out, err = _run_cli_split(
                    "project-version-update", str(project_root), "--target", "v0.4.30", "--dry-run", "--output", output_relative, "--format", "json",
                )
            self.assertEqual(code, 1, err)
            result = json.loads(out)
            self.assertEqual(result["status"], "terminal_cleanup_required")
            self.assertEqual(result["existing_transaction"]["schema"], archive_services.PROJECT_UPDATE_EXISTING_TRANSACTION_SCHEMA)
            self.assertIn("applicable_recovery", result["existing_transaction"])


class IndexPrecheckTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", self.root)

    def test_precheck_states_and_edge_previews_announce_them(self) -> None:
        missing = archive_services.archive_index_precheck(self.root)
        self.assertEqual(missing["state"], "stale")
        self.assertEqual(missing["reason_codes"], ["archive_index_missing"])
        self.assertEqual(missing["next_safe_actions"], list(archive_services.INDEX_REBUILD_NEXT_SAFE_ACTIONS))
        archive_services.index_archive(self.root)
        current = archive_services.archive_index_precheck(self.root)
        self.assertEqual(current["state"], "current")
        self.assertEqual(current["next_safe_actions"], [])
        self.assertEqual(current["live_zettel_count"], current["indexed_zettel_count"])
        preview = archive_services.zettel_edge_write(
            self.root, from_zettel="zet_20240504_fake_lunch_thought", target_ref="zet_20240505_fake_company_onboarding_insight",
            edge_type="semantic", visibility="private", dry_run=True,
        )
        self.assertTrue(preview["ok"], preview)
        self.assertEqual(preview["index_precheck"]["state"], "current")
        source = self.root / "zettels" / "zet_20240504_fake_lunch_thought.md"
        source.write_text(source.read_text(encoding="utf-8") + "\nedited after the index\n", encoding="utf-8")
        stale = archive_services.zettel_edge_write(
            self.root, from_zettel="zet_20240504_fake_lunch_thought", target_ref="zet_20240505_fake_company_onboarding_insight",
            edge_type="semantic", visibility="private", dry_run=True,
        )
        self.assertFalse(stale["ok"])
        self.assertIn(archive_services.INDEX_REBUILD_REQUIRED, stale["blockers"])
        self.assertEqual(stale["index_precheck"]["state"], "stale")
        self.assertTrue(stale["index_precheck"]["reason_codes"])
        self.assertEqual(stale["next_safe_actions"][:2], list(archive_services.INDEX_REBUILD_NEXT_SAFE_ACTIONS))
        self.assertNotIn(str(self.root), json.dumps(stale["index_precheck"]))
        with patch.object(archive_services, "require_current_zettel_index", side_effect=OSError("C:/Users/private/db")):
            broken = archive_services.archive_index_precheck(self.root)
        self.assertEqual(broken["state"], "stale")
        self.assertEqual(broken["reason_codes"], [archive_services.INDEX_REBUILD_REQUIRED])


if __name__ == "__main__":
    unittest.main()
