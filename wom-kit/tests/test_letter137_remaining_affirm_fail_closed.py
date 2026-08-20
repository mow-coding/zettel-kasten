from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import ModuleType
from unittest import mock

from wom_kit import (
    archive_cli,
    archive_services,
    completion_workflows,
    legacy_coordination_cleanup,
    saved_view_workflows,
)


COMPOUND_APPROVAL_BLOCKER = "compound_exact_human_approval_binding_required"
PRIVATE_REQUEST = ".wom-scratch/private/PRIVATE-AFFIRM-REQUEST-SECRET.json"
PRIVATE_RECEIPT = "receipts/PRIVATE-AFFIRM-RECEIPT-SECRET.json"
PRIVATE_OUTPUT = (
    ".zettel-kasten/diagnostics/PRIVATE-AFFIRM-OUTPUT-SECRET.json"
)
PRIVATE_REVIEWER = "person:PRIVATE-REMAINING-AFFIRM-REVIEWER-SECRET"
PRIVATE_DIGEST = "sha256:PRIVATE-REMAINING-AFFIRM-DIGEST-SECRET"
VALID_DIGEST = "sha256:" + "a" * 64
PRIVATE_TARGET = "v0.4.0"


def _snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class _RemainingAffirmAssertions(unittest.TestCase):
    def _root(self, parent: Path) -> Path:
        root = parent / "PRIVATE-REMAINING-AFFIRM-ROOT-SECRET"
        root.mkdir()
        (root / "sentinel.bin").write_bytes(b"must remain byte exact")
        return root

    def _assert_fixed_service_block(
        self,
        *,
        root: Path,
        lifecycle_action: str,
        invoke: Callable[[], dict[str, object]],
    ) -> None:
        before = _snapshot(root)
        result = invoke()

        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["lifecycle_action"], lifecycle_action)
        self.assertEqual(result["blockers"], [COMPOUND_APPROVAL_BLOCKER])
        self.assertEqual(result["reason_codes"], [COMPOUND_APPROVAL_BLOCKER])
        self.assertEqual(result["would_change"], [])
        self.assertEqual(result["files_written"], [])
        self.assertIs(result["private_values_echoed"], False)
        self.assertEqual(_snapshot(root), before)
        rendered = json.dumps(result, ensure_ascii=False)
        for private in (
            str(root),
            PRIVATE_REQUEST,
            PRIVATE_RECEIPT,
            PRIVATE_OUTPUT,
            PRIVATE_REVIEWER,
            PRIVATE_DIGEST,
        ):
            self.assertNotIn(private, rendered)


class Letter137RemainingAffirmServiceBoundaryTests(
    _RemainingAffirmAssertions
):
    def test_legacy_cleanup_blocks_before_workspace_plan_or_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(Path(tmp))
            with mock.patch.object(
                legacy_coordination_cleanup,
                "_build_private_plan",
                side_effect=AssertionError("legacy cleanup plan entered"),
            ) as plan:
                self._assert_fixed_service_block(
                    root=root,
                    lifecycle_action="legacy_coordination_cleanup",
                    invoke=lambda: (
                        legacy_coordination_cleanup.legacy_coordination_cleanup(
                            root,
                            dry_run=False,
                            approve=True,
                            reviewed_by=PRIVATE_REVIEWER,
                            expected_plan_sha256=PRIVATE_DIGEST,
                            affirm_workspace_owner_authorized=True,
                            affirm_external_writers_quiescent=True,
                            affirm_retired_state_disposable=True,
                            affirm_backups_and_receipts_disposable=True,
                            max_files=100,
                            max_bytes=1024,
                        )
                    ),
                )
            plan.assert_not_called()

    def test_project_update_and_collision_block_before_filesystem_or_git(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(Path(tmp))
            with mock.patch.object(
                archive_services,
                "wom_kit_real_path_kind",
                side_effect=AssertionError("project filesystem read entered"),
            ) as path_kind:
                self._assert_fixed_service_block(
                    root=root,
                    lifecycle_action="project_version_update",
                    invoke=lambda: archive_services.wom_kit_project_version_update(
                        root,
                        target=PRIVATE_TARGET,
                        approve=True,
                        reviewed_by=PRIVATE_REVIEWER,
                        affirm_external_writers_quiescent=True,
                    ),
                )
                self._assert_fixed_service_block(
                    root=root,
                    lifecycle_action="project_version_update_collision",
                    invoke=lambda: (
                        archive_services.wom_kit_project_version_update_collision(
                            root,
                            target=PRIVATE_TARGET,
                            entry_ref="update-entry:0001",
                            action="preserve-relocate",
                            approve=True,
                            expected_plan_sha256=PRIVATE_DIGEST,
                            reviewed_by=PRIVATE_REVIEWER,
                            affirm_external_writers_quiescent=True,
                        )
                    ),
                )
            path_kind.assert_not_called()

    def test_saved_view_blocks_before_private_request_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(Path(tmp))
            with mock.patch.object(
                saved_view_workflows,
                "_write_plan_core",
                side_effect=AssertionError("saved-view request read entered"),
            ) as plan:
                self._assert_fixed_service_block(
                    root=root,
                    lifecycle_action="saved_view_write",
                    invoke=lambda: saved_view_workflows.saved_view_write(
                        root,
                        request_path=PRIVATE_REQUEST,
                        expected_plan_sha256=PRIVATE_DIGEST,
                        reviewed_by=PRIVATE_REVIEWER,
                        affirm_view_reviewed=True,
                    ),
                )
            plan.assert_not_called()

    def test_private_metadata_blocks_before_archive_or_intake_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(Path(tmp))
            with mock.patch.object(
                archive_services,
                "require_existing_archive_root",
                side_effect=AssertionError("private metadata archive read entered"),
            ) as archive_read:
                self._assert_fixed_service_block(
                    root=root,
                    lifecycle_action="private_objet_source_metadata_write",
                    invoke=lambda: archive_services.private_objet_source_metadata_write(
                        root,
                        intake=PRIVATE_REQUEST,
                        expected_intake_sha256=PRIVATE_DIGEST,
                        expected_plan_sha256=PRIVATE_DIGEST,
                        dry_run=False,
                        approve=True,
                        reviewed_by=PRIVATE_REVIEWER,
                        affirm_private_metadata_reviewed=True,
                        affirm_external_writers_quiescent=True,
                    ),
                )
            archive_read.assert_not_called()

    def test_bytecode_repair_blocks_before_project_scan_or_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(Path(tmp))
            with mock.patch.object(
                completion_workflows,
                "_project_bytecode_plan_core",
                side_effect=AssertionError("bytecode project scan entered"),
            ) as plan:
                self._assert_fixed_service_block(
                    root=root,
                    lifecycle_action="project_bytecode_repair",
                    invoke=lambda: completion_workflows.project_bytecode_repair(
                        root,
                        max_files=100,
                        expected_plan_sha256=PRIVATE_DIGEST,
                        reviewed_by=PRIVATE_REVIEWER,
                        affirm_external_writers_quiescent=True,
                        target=PRIVATE_TARGET,
                        expected_materialization_plan_sha256=PRIVATE_DIGEST,
                    ),
                )
            plan.assert_not_called()

    def test_identity_reconcile_blocks_before_archive_identity_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(Path(tmp))
            with mock.patch.object(
                archive_services,
                "_archive_identity_reconcile_analysis",
                side_effect=AssertionError("archive identity read entered"),
            ) as analysis:
                self._assert_fixed_service_block(
                    root=root,
                    lifecycle_action="archive_identity_reconcile",
                    invoke=lambda: archive_services.reconcile_archive_identity(
                        root,
                        reviewed_by=PRIVATE_REVIEWER,
                        expected_archive_sha256=PRIVATE_DIGEST,
                        expected_identity_sha256=PRIVATE_DIGEST,
                        expected_proposed_identity_sha256=PRIVATE_DIGEST,
                        affirm_principal_metadata_reviewed=True,
                    ),
                )
            analysis.assert_not_called()


class Letter137RemainingAffirmCliBoundaryTests(_RemainingAffirmAssertions):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = archive_cli.build_parser()

    def _assert_cli_block(
        self,
        *,
        arguments: list[str],
        service_module: ModuleType,
        service_name: str,
        lifecycle_action: str,
    ) -> None:
        args = self.parser.parse_args(arguments)
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            mock.patch.object(
                service_module,
                service_name,
                side_effect=AssertionError("affirm service entered"),
            ) as service,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = args.func(args)

        self.assertEqual(code, 1, stderr.getvalue())
        service.assert_not_called()
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["lifecycle_action"], lifecycle_action)
        self.assertEqual(result["reason_codes"], [COMPOUND_APPROVAL_BLOCKER])
        self.assertIs(result["private_values_echoed"], False)
        rendered = stdout.getvalue() + stderr.getvalue()
        for private in (
            arguments[1],
            PRIVATE_REQUEST,
            PRIVATE_RECEIPT,
            PRIVATE_OUTPUT,
            PRIVATE_REVIEWER,
            PRIVATE_DIGEST,
        ):
            self.assertNotIn(private, rendered)

    def test_all_remaining_affirm_cli_approvals_block_before_service(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = str(self._root(Path(tmp)))
            calls = (
                (
                    [
                        "legacy-coordination-cleanup",
                        root,
                        "--approve",
                        "--reviewed-by",
                        PRIVATE_REVIEWER,
                        "--expected-plan-sha256",
                        PRIVATE_DIGEST,
                        "--affirm-workspace-owner-authorized",
                        "--affirm-external-writers-quiescent",
                        "--affirm-retired-state-disposable",
                        "--affirm-backups-and-receipts-disposable",
                        "--format",
                        "json",
                    ],
                    legacy_coordination_cleanup,
                    "legacy_coordination_cleanup",
                    "legacy_coordination_cleanup",
                ),
                (
                    [
                        "project-version-update",
                        root,
                        "--target",
                        PRIVATE_TARGET,
                        "--approve",
                        "--reviewed-by",
                        PRIVATE_REVIEWER,
                        "--affirm-external-writers-quiescent",
                        "--output",
                        PRIVATE_OUTPUT,
                        "--format",
                        "json",
                    ],
                    archive_services,
                    "wom_kit_project_version_update",
                    "project_version_update",
                ),
                (
                    [
                        "project-version-update-collision",
                        root,
                        "--target",
                        PRIVATE_TARGET,
                        "--entry-ref",
                        "update-entry:0001",
                        "--action",
                        "preserve-relocate",
                        "--approve",
                        "--expected-plan-sha256",
                        PRIVATE_DIGEST,
                        "--reviewed-by",
                        PRIVATE_REVIEWER,
                        "--affirm-external-writers-quiescent",
                        "--format",
                        "json",
                    ],
                    archive_services,
                    "wom_kit_project_version_update_collision",
                    "project_version_update_collision",
                ),
                (
                    [
                        "saved-view-write",
                        root,
                        "--request",
                        PRIVATE_REQUEST,
                        "--approve",
                        "--expected-plan-sha256",
                        PRIVATE_DIGEST,
                        "--reviewed-by",
                        PRIVATE_REVIEWER,
                        "--affirm-view-reviewed",
                        "--format",
                        "json",
                    ],
                    saved_view_workflows,
                    "saved_view_write",
                    "saved_view_write",
                ),
                (
                    [
                        "objet-source-metadata-write",
                        root,
                        "--intake",
                        PRIVATE_REQUEST,
                        "--expected-intake-sha256",
                        PRIVATE_DIGEST,
                        "--expected-plan-sha256",
                        PRIVATE_DIGEST,
                        "--approve",
                        "--reviewed-by",
                        PRIVATE_REVIEWER,
                        "--affirm-private-metadata-reviewed",
                        "--affirm-external-writers-quiescent",
                        "--format",
                        "json",
                    ],
                    archive_services,
                    "private_objet_source_metadata_write",
                    "private_objet_source_metadata_write",
                ),
                (
                    [
                        "project-bytecode-repair",
                        root,
                        "--expected-plan-sha256",
                        PRIVATE_DIGEST,
                        "--target",
                        PRIVATE_TARGET,
                        "--expected-materialization-plan-sha256",
                        PRIVATE_DIGEST,
                        "--approve",
                        "--reviewed-by",
                        PRIVATE_REVIEWER,
                        "--affirm-external-writers-quiescent",
                        "--format",
                        "json",
                    ],
                    completion_workflows,
                    "project_bytecode_repair",
                    "project_bytecode_repair",
                ),
                (
                    [
                        "identity-reconcile",
                        root,
                        "--approve",
                        "--reviewed-by",
                        PRIVATE_REVIEWER,
                        "--expected-archive-sha256",
                        PRIVATE_DIGEST,
                        "--expected-identity-sha256",
                        PRIVATE_DIGEST,
                        "--expected-proposed-identity-sha256",
                        PRIVATE_DIGEST,
                        "--affirm-principal-metadata-reviewed",
                        "--format",
                        "json",
                    ],
                    archive_services,
                    "reconcile_archive_identity",
                    "archive_identity_reconcile",
                ),
            )
            before = _snapshot(Path(root))
            for arguments, module, service, action in calls:
                with self.subTest(action=action):
                    self._assert_cli_block(
                        arguments=arguments,
                        service_module=module,
                        service_name=service,
                        lifecycle_action=action,
                    )
            self.assertEqual(_snapshot(Path(root)), before)

    def test_read_only_cli_routes_still_dispatch_without_approval(self) -> None:
        safe_result = {
            "ok": True,
            "state": "ready",
            "status": "ready",
            "action": "ready",
            "dry_run": True,
            "blockers": [],
            "warnings": [],
            "would_change": [],
            "files_written": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = str(self._root(Path(tmp)))
            calls = (
                (
                    [
                        "legacy-coordination-cleanup",
                        root,
                        "--dry-run",
                        "--format",
                        "json",
                    ],
                    legacy_coordination_cleanup,
                    "legacy_coordination_cleanup",
                ),
                (
                    [
                        "project-version-update",
                        root,
                        "--target",
                        PRIVATE_TARGET,
                        "--dry-run",
                        "--format",
                        "json",
                    ],
                    archive_services,
                    "wom_kit_project_version_update",
                ),
                (
                    [
                        "project-version-update-collision",
                        root,
                        "--target",
                        PRIVATE_TARGET,
                        "--entry-ref",
                        "update-entry:0001",
                        "--action",
                        "inspect",
                        "--dry-run",
                        "--expected-plan-sha256",
                        VALID_DIGEST,
                        "--format",
                        "json",
                    ],
                    archive_services,
                    "wom_kit_project_version_update_collision",
                ),
                (
                    [
                        "saved-view-write",
                        root,
                        "--request",
                        PRIVATE_REQUEST,
                        "--dry-run",
                        "--format",
                        "json",
                    ],
                    saved_view_workflows,
                    "saved_view_write_plan",
                ),
                (
                    [
                        "objet-source-metadata-write",
                        root,
                        "--intake",
                        PRIVATE_REQUEST,
                        "--expected-intake-sha256",
                        PRIVATE_DIGEST,
                        "--dry-run",
                        "--format",
                        "json",
                    ],
                    archive_services,
                    "private_objet_source_metadata_write",
                ),
                (
                    [
                        "project-bytecode-repair-plan",
                        root,
                        "--dry-run",
                        "--format",
                        "json",
                    ],
                    completion_workflows,
                    "project_bytecode_repair_plan",
                ),
                (
                    [
                        "identity-reconcile",
                        root,
                        "--dry-run",
                        "--format",
                        "json",
                    ],
                    archive_services,
                    "archive_identity_reconcile_plan",
                ),
            )
            before = _snapshot(Path(root))
            for arguments, module, service_name in calls:
                with self.subTest(service=service_name):
                    parsed = self.parser.parse_args(arguments)
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with (
                        mock.patch.object(
                            module,
                            service_name,
                            return_value=dict(safe_result),
                        ) as service,
                        redirect_stdout(stdout),
                        redirect_stderr(stderr),
                    ):
                        code = parsed.func(parsed)
                    self.assertEqual(code, 0, stderr.getvalue())
                    service.assert_called_once()
            self.assertEqual(_snapshot(Path(root)), before)


if __name__ == "__main__":
    unittest.main()
