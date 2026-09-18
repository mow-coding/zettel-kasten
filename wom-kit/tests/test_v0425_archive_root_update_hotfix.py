"""v0.4.25 hotfix: archive-root project updates and resume failure causes.

Beta letter 161 and the 2026-09-18 v0.4.24 resume report: an update started
from the archive root (``archive project-version-update <archive-root>``)
failed after the native approval with ``approved_snapshot_changed`` and its
transaction could not be reopened by ``--resume``
(``directory_stability_unavailable``), with no cause in diagnostics.  The
preflight records mirror, pin and receipt locations relative to the
inspection root with a ``parent_of_archive`` label; six consumers joined that
label literally onto the project root.  These tests pin the resolver, the
consumers that must use it, and the direct-cause projection.  The end to end
reproduction (v0.4.18 and v0.4.21 wheels from the archive root, then the
hotfix build's ``--resume --abandon-started-approval`` and a fresh approve) is
recorded in the release minutes, not run here.
"""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import inspect
import io
import json
from pathlib import PurePosixPath
import shutil
import tempfile
import unittest
from pathlib import Path

from wom_kit import archive_cli
from wom_kit import archive_services
from wom_kit import operation_control
from wom_kit import project_runtime
from wom_kit import project_update_git_runner
from wom_kit import project_update_transaction
from wom_kit.exact_human_approval import ExactHumanApprovalError
from wom_kit.exact_human_approval_workflow import ExactHumanApprovalWorkflowError


resolve = archive_services.wom_kit_project_update_logical_relative_to_project_root


class LogicalLocationResolverTests(unittest.TestCase):
    def test_archive_root_label_maps_onto_the_project_root(self) -> None:
        self.assertEqual(
            resolve("parent_of_archive/.zettel-kasten/source"),
            PurePosixPath(".zettel-kasten/source"),
        )
        self.assertEqual(
            resolve("parent_of_archive/.zettel-kasten/installed-version.txt"),
            PurePosixPath(".zettel-kasten/installed-version.txt"),
        )
        self.assertEqual(
            resolve("parent_of_archive/installed-version.txt"),
            PurePosixPath("installed-version.txt"),
        )
        self.assertEqual(
            resolve("parent_of_archive/.zettel-kasten/receipts/version-updates/update_x.json"),
            PurePosixPath(".zettel-kasten/receipts/version-updates/update_x.json"),
        )

    def test_project_root_locations_are_unchanged(self) -> None:
        for logical in (
            ".zettel-kasten/source",
            ".zettel-kasten/installed-version.txt",
            "installed-version.txt",
            ".zettel-kasten/runtimes/v0.4.25",
            ".zettel-kasten/bin/archive.cmd",
        ):
            with self.subTest(logical=logical):
                self.assertEqual(resolve(logical), PurePosixPath(logical))

    def test_labels_produced_by_preflight_round_trip(self) -> None:
        for label in ("inspection_root", "parent_of_archive"):
            with self.subTest(label=label):
                mirror = archive_services.wom_kit_project_source_mirror_location(label)
                self.assertEqual(resolve(mirror), PurePosixPath(".zettel-kasten/source"))
                pin = archive_services.wom_kit_version_pin_location(
                    label, ".zettel-kasten/installed-version.txt"
                )
                self.assertEqual(resolve(pin), PurePosixPath(".zettel-kasten/installed-version.txt"))

    def test_unsafe_or_empty_locations_resolve_to_none(self) -> None:
        for logical in ("", "parent_of_archive", "../x", "/abs", "a/../b", "a/./b/..", None, 7, b"x"):
            with self.subTest(logical=logical):
                self.assertIsNone(resolve(logical))


class ConsumersUseTheResolverTests(unittest.TestCase):
    """Every site that joins a recorded location onto the project root."""

    CONSUMERS = (
        "_project_update_reopen_durable_state",
        "_project_update_assert_approved_snapshot_unchanged",
        "_project_update_terminal_original_postimage_superseded_read_only",
    )

    def test_named_consumers_resolve_through_the_helper(self) -> None:
        for name in self.CONSUMERS:
            with self.subTest(function=name):
                source = inspect.getsource(getattr(archive_services, name))
                self.assertIn("wom_kit_project_update_logical_relative_to_project_root", source)

    def test_no_literal_join_of_a_recorded_location_remains(self) -> None:
        source = inspect.getsource(archive_services)
        for stale in (
            'project_root.joinpath(\n            *PurePosixPath(str(private_plan["mirror_logical"])).parts',
            "mirror_logical = PurePosixPath(str(basis.get(\"mirror_logical\") or \"\"))",
            "logical = PurePosixPath(component[\"logical_target\"])",
            "logical = PurePosixPath(component.logical_target)",
            "*PurePosixPath(pin.logical_target).parts",
            "logical = PurePosixPath(logical_value)",
        ):
            with self.subTest(stale=stale[:48]):
                self.assertNotIn(stale, source)


class DirectCauseProjectionTests(unittest.TestCase):
    def test_service_failures_carry_their_fixed_code_and_journal_stage(self) -> None:
        cases = (
            archive_services.ArchiveServiceError("project_version_update_directory_stability_unavailable"),
            archive_services.ArchiveServiceError("project_version_update_resume_binding_mismatch"),
            project_update_transaction.ProjectUpdateTransactionError("project_update_transaction_not_found"),
            project_runtime.ProjectRuntimeError("project_runtime_candidate_invalid"),
            project_update_git_runner.ProjectUpdateGitRunnerError("project_update_git_runner_drift"),
            operation_control.OperationControlError("operation_result_unavailable"),
            ExactHumanApprovalError("exact_human_approval_resume_claim_invalid"),
        )
        for error in cases:
            with self.subTest(error=type(error).__name__):
                projected = archive_cli._project_version_update_content_free_cause(
                    error, journal_stage="project-preflight"
                )
                self.assertEqual(projected["cause_stage"], "project-preflight")
                self.assertRegex(projected["cause_code"], r"^[a-z][a-z0-9_]{0,95}$")
                self.assertEqual(
                    projected["cause_code"],
                    getattr(error, "code", None) or error.args[0],
                )

    def test_unknown_stage_and_missing_journal_are_named_unknown(self) -> None:
        error = archive_services.ArchiveServiceError("project_version_update_resume_target_mismatch")
        self.assertEqual(
            archive_cli._project_version_update_content_free_cause(error, journal_stage=None),
            {"cause_code": "project_version_update_resume_target_mismatch", "cause_stage": "unknown"},
        )
        self.assertEqual(
            archive_cli._project_version_update_content_free_cause(error, journal_stage="PRIVATE stage")[
                "cause_stage"
            ],
            "unknown",
        )

    def test_free_text_and_foreign_families_never_cross(self) -> None:
        for error in (
            archive_services.ArchiveServiceError("C:\\Users\\<user>\\private path"),
            archive_services.ArchiveServiceError("project_version_update_", "two", "args"),
            archive_services.ArchiveServiceError("credential_registry_local_profile_not_ignored"),
            ValueError("project version update target required"),  # free text, not a token
            ValueError("credential_registry_local_profile_not_ignored"),  # foreign family
            OSError("project_version_update_x"),
            RuntimeError("project_update_transaction_invalid"),
        ):
            with self.subTest(error=repr(error)[:60]):
                self.assertIsNone(
                    archive_cli._project_version_update_content_free_cause(
                        error, journal_stage="project-preflight"
                    )
                )

    def test_broker_wrapper_projection_is_unchanged(self) -> None:
        wrapped = ExactHumanApprovalWorkflowError(
            "exact_human_approval_state_unknown",
            cause_code="project_version_update_approved_snapshot_changed",
            cause_stage="domain_writer",
        )
        self.assertEqual(
            archive_cli._project_version_update_content_free_cause(wrapped, journal_stage="native-approval"),
            {"cause_code": "project_version_update_approved_snapshot_changed", "cause_stage": "domain_writer"},
        )
        bare = ExactHumanApprovalWorkflowError("exact_human_approval_state_unknown")
        self.assertIsNone(archive_cli._project_version_update_content_free_cause(bare, journal_stage="native-approval"))


class JournalStageAndDiagnosticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="wom-v0425-journal-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def test_current_stage_follows_reported_progress(self) -> None:
        relative = ".zettel-kasten/diagnostics/project-version-update-" + "b" * 32 + ".json"
        (self.root / ".zettel-kasten").mkdir(parents=True)
        journal = operation_control.OperationRunJournal.prepare(
            self.root, output_relative=relative, command="project-version-update", run_id="a" * 32
        )
        try:
            self.assertEqual(journal.current_stage, "starting")
            journal.progress("project-preflight", "resume-start", None, None)
            self.assertEqual(journal.current_stage, "project-preflight")
            journal.progress("PRIVATE_STAGE_DO_NOT_ECHO", "start", None, None)
            self.assertEqual(journal.current_stage, "unknown")
        finally:
            journal.close()

    def test_diagnostics_store_the_direct_cause_with_a_hyphenated_stage(self) -> None:
        (self.root / ".zettel-kasten").mkdir(parents=True)
        capture = archive_cli._CommandRunResultCapture.prepare(
            ".zettel-kasten/diagnostics/project-version-update-" + "c" * 32 + ".json",
            self.root,
            command="project-version-update",
            required_prefix=".zettel-kasten/diagnostics/",
            require_archive_root=False,
        )
        error = archive_services.ArchiveServiceError("project_version_update_directory_stability_unavailable")
        metadata = capture.write_completed(
            exit_code=1,
            error=error,
            cause=archive_cli._project_version_update_content_free_cause(error, journal_stage="project-preflight"),
        )
        self.assertTrue(metadata["result_artifact_written"])
        stored = json.loads(capture.output_path.read_text(encoding="utf-8"))
        for document in (stored,):
            execution_error = document["cli_execution"]["error"]
            self.assertEqual(execution_error["type"], "ArchiveServiceError")
            self.assertEqual(execution_error["code"], "project_version_update_command_failed")
            self.assertEqual(execution_error["cause_code"], "project_version_update_directory_stability_unavailable")
            self.assertEqual(execution_error["cause_stage"], "project-preflight")
            self.assertEqual(execution_error["cause_code_source"], "fixed_literal_allowlist")
            self.assertFalse(execution_error["raw_message_stored"])
        self.assertNotIn("Users", capture.output_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
