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
    saved_view_workflows,
)


COMPOUND_APPROVAL_BLOCKER = (
    "compound_exact_human_approval_binding_required"
)
PRIVATE_ROOT_NAME = "PRIVATE-CANONICAL-AUTHORITY-ROOT-SECRET"
PRIVATE_RECEIPT = "receipts/PRIVATE-AUTHORITY-RECEIPT-SECRET.json"
PRIVATE_JOURNAL = "receipts/PRIVATE-AUTHORITY-JOURNAL-SECRET.json"
PRIVATE_MANIFEST = ".wom-scratch/private/PRIVATE-AUTHORITY-MANIFEST-SECRET.json"
PRIVATE_SELECTION = ".wom-scratch/private/PRIVATE-AUTHORITY-SELECTION-SECRET.json"
PRIVATE_STAGED = "inbox/PRIVATE-AUTHORITY-STAGED-SECRET.bin"
PRIVATE_EXPORT = "PRIVATE-AUTHORITY-EXPORT-SECRET"
PRIVATE_REVIEWER = "person:PRIVATE-AUTHORITY-REVIEWER-SECRET"
PRIVATE_DIGEST = "PRIVATE-AUTHORITY-DIGEST-SECRET"
PRIVATE_PRINCIPAL = "person:PRIVATE-AUTHORITY-PRINCIPAL-SECRET"
PRIVATE_DISPLAY_NAME = "PRIVATE AUTHORITY DISPLAY NAME SECRET"
PRIVATE_SOURCE_ID = "local:PRIVATE-AUTHORITY-SOURCE-SECRET"
PRIVATE_NEW_OWNER = "person:PRIVATE-AUTHORITY-NEW-OWNER-SECRET"


def _snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


PRIVATE_VALUES = (
    PRIVATE_ROOT_NAME,
    PRIVATE_RECEIPT,
    PRIVATE_JOURNAL,
    PRIVATE_MANIFEST,
    PRIVATE_SELECTION,
    PRIVATE_STAGED,
    PRIVATE_EXPORT,
    PRIVATE_REVIEWER,
    PRIVATE_DIGEST,
    PRIVATE_PRINCIPAL,
    PRIVATE_DISPLAY_NAME,
    PRIVATE_SOURCE_ID,
    PRIVATE_NEW_OWNER,
)


class _CanonicalAuthorityAssertions(unittest.TestCase):
    def _root(self, parent: Path) -> Path:
        root = parent / PRIVATE_ROOT_NAME
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
        for private in (str(root), *PRIVATE_VALUES):
            self.assertNotIn(private, rendered)


class Letter137CanonicalAuthorityServiceBoundaryTests(
    _CanonicalAuthorityAssertions
):
    def test_migration_apply_and_revert_block_before_target_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(Path(tmp))
            with (
                mock.patch.object(
                    archive_services,
                    "migrate_frontmatter_v03",
                    side_effect=AssertionError("migration apply entered"),
                ) as apply,
                mock.patch.object(
                    archive_services,
                    "migrate_frontmatter_v03_revert",
                    side_effect=AssertionError("migration revert entered"),
                ) as revert,
            ):
                for is_revert in (False, True):
                    with self.subTest(revert=is_revert):
                        self._assert_fixed_service_block(
                            root=root,
                            lifecycle_action="migrate_archive",
                            invoke=lambda is_revert=is_revert: (
                                archive_services.migrate_archive(
                                    root,
                                    target=archive_services.FRONTMATTER_V03_TARGET,
                                    dry_run=False,
                                    approve=True,
                                    revert=is_revert,
                                    reviewed_by=PRIVATE_REVIEWER,
                                )
                            ),
                        )
            apply.assert_not_called()
            revert.assert_not_called()

    def test_public_migration_services_block_before_archive_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(Path(tmp))
            calls = (
                (
                    archive_services.sync_base_link_types,
                    archive_services.BASE_LINK_TYPES_TARGET,
                ),
                (
                    archive_services.sync_base_link_types_revert,
                    archive_services.BASE_LINK_TYPES_TARGET,
                ),
                (
                    archive_services.migrate_link_types_v03,
                    archive_services.LINK_TYPES_V03_TARGET,
                ),
                (
                    archive_services.migrate_link_types_v03_revert,
                    archive_services.LINK_TYPES_V03_TARGET,
                ),
                (
                    archive_services.migrate_frontmatter_v03,
                    archive_services.FRONTMATTER_V03_TARGET,
                ),
                (
                    archive_services.migrate_frontmatter_v03_revert,
                    archive_services.FRONTMATTER_V03_TARGET,
                ),
            )
            with mock.patch.object(
                archive_services,
                "require_existing_archive_root",
                side_effect=AssertionError("migration archive read entered"),
            ) as archive_read:
                for service, target in calls:
                    with self.subTest(service=service.__name__):
                        self._assert_fixed_service_block(
                            root=root,
                            lifecycle_action="migrate_archive",
                            invoke=lambda service=service, target=target: service(
                                root,
                                target=target,
                                dry_run=False,
                                approve=True,
                            ),
                        )
            archive_read.assert_not_called()

    def test_saved_view_and_completion_writes_block_before_private_plans(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(Path(tmp))
            cases = (
                (
                    saved_view_workflows,
                    "_revert_plan_core",
                    "saved_view_revert",
                    lambda: saved_view_workflows.saved_view_revert(
                        root,
                        receipt_path=PRIVATE_RECEIPT,
                        expected_plan_sha256=PRIVATE_DIGEST,
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                ),
                (
                    completion_workflows,
                    "_batch_plan_core",
                    "objet_capture_batch",
                    lambda: completion_workflows.objet_capture_batch_apply(
                        root,
                        manifest_path=PRIVATE_MANIFEST,
                        expected_plan_sha256=PRIVATE_DIGEST,
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                ),
                (
                    completion_workflows,
                    "_markup_plan_core",
                    "markup_normalization",
                    lambda: completion_workflows.markup_normalization_apply(
                        root,
                        policy="normalize",
                        max_items=10,
                        max_changes=10,
                        expected_plan_sha256=PRIVATE_DIGEST,
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                ),
                (
                    completion_workflows,
                    "_markup_revert_plan_core",
                    "markup_normalization_revert",
                    lambda: completion_workflows.markup_normalization_revert(
                        root,
                        receipt=PRIVATE_RECEIPT,
                        expected_plan_sha256=PRIVATE_DIGEST,
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                ),
                (
                    completion_workflows,
                    "_markup_recovery_plan_core",
                    "markup_normalization_recovery",
                    lambda: completion_workflows.markup_normalization_recover(
                        root,
                        journal=PRIVATE_JOURNAL,
                        mode="rollback",
                        expected_plan_sha256=PRIVATE_DIGEST,
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                ),
                (
                    completion_workflows,
                    "_principal_registration_plan_core",
                    "principal_register",
                    lambda: completion_workflows.principal_register(
                        root,
                        principal_id=PRIVATE_PRINCIPAL,
                        kind="person",
                        display_name=PRIVATE_DISPLAY_NAME,
                        expected_plan_sha256=PRIVATE_DIGEST,
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                ),
                (
                    completion_workflows,
                    "_principal_unregistration_plan_core",
                    "principal_unregister",
                    lambda: completion_workflows.principal_unregister(
                        root,
                        principal_id=PRIVATE_PRINCIPAL,
                        expected_plan_sha256=PRIVATE_DIGEST,
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                ),
            )
            for module, private_plan, action, invoke in cases:
                with self.subTest(action=action), mock.patch.object(
                    module,
                    private_plan,
                    side_effect=AssertionError("private plan entered"),
                ) as plan:
                    self._assert_fixed_service_block(
                        root=root,
                        lifecycle_action=action,
                        invoke=invoke,
                    )
                plan.assert_not_called()

    def test_archive_authority_writes_block_before_archive_or_input_reads(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(Path(tmp))
            cases = (
                (
                    "objet_capture_enable",
                    lambda: archive_services.objet_capture_enable(
                        root,
                        dry_run=False,
                        approve=True,
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                ),
                (
                    "objet_capture_enable",
                    lambda: archive_services.objet_capture_enable(
                        root,
                        dry_run=False,
                        approve=True,
                        reviewed_by=PRIVATE_REVIEWER,
                        revoke=True,
                    ),
                ),
                (
                    "objet_capture_enable",
                    lambda: archive_services.objet_capture_enable(
                        root,
                        dry_run=False,
                        approve=True,
                        reviewed_by=PRIVATE_REVIEWER,
                        reenable=True,
                    ),
                ),
                (
                    "objet_capture_selection_record",
                    lambda: archive_services.objet_capture_selection_manifest(
                        root,
                        staged_path=PRIVATE_STAGED,
                        source_intake_receipt=PRIVATE_RECEIPT,
                        dry_run=False,
                        approve=True,
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                ),
                (
                    "import_external_archive",
                    lambda: archive_services.import_external_archive(
                        root,
                        PRIVATE_EXPORT,
                        source_system="notion",
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                ),
                (
                    "add_source_binding",
                    lambda: archive_services.add_source_binding(
                        root,
                        source_id=PRIVATE_SOURCE_ID,
                        source_type="local_folder",
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                ),
                (
                    "transfer_archive_ownership",
                    lambda: archive_services.transfer_archive_ownership(
                        root,
                        new_owner=PRIVATE_NEW_OWNER,
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                ),
            )
            with mock.patch.object(
                archive_services,
                "require_existing_archive_root",
                side_effect=AssertionError("archive read entered"),
            ) as archive_read:
                for action, invoke in cases:
                    with self.subTest(action=action):
                        self._assert_fixed_service_block(
                            root=root,
                            lifecycle_action=action,
                            invoke=invoke,
                        )
            archive_read.assert_not_called()

    def test_single_objet_capture_blocks_before_capture_runner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(Path(tmp))
            with mock.patch.object(
                archive_services,
                "_objet_capture_run",
                side_effect=AssertionError("capture runner entered"),
            ) as runner:
                self._assert_fixed_service_block(
                    root=root,
                    lifecycle_action="objet_capture",
                    invoke=lambda: archive_services.objet_capture_apply(
                        root,
                        PRIVATE_SELECTION,
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                )
            runner.assert_not_called()


class Letter137CanonicalAuthorityCliBoundaryTests(
    _CanonicalAuthorityAssertions
):
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
                side_effect=AssertionError("approved service entered"),
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
        for private in (arguments[1], *PRIVATE_VALUES):
            self.assertNotIn(private, rendered)

    def test_all_canonical_authority_cli_approvals_block_before_service(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root_path = self._root(Path(tmp))
            root = str(root_path)
            calls = (
                (
                    [
                        "objet-capture-enable",
                        root,
                        "--approve",
                        "--reviewed-by",
                        PRIVATE_REVIEWER,
                        "--format",
                        "json",
                    ],
                    archive_services,
                    "objet_capture_enable",
                    "objet_capture_enable",
                ),
                (
                    [
                        "objet-capture-enable",
                        root,
                        "--approve",
                        "--reviewed-by",
                        PRIVATE_REVIEWER,
                        "--revoke",
                        "--format",
                        "json",
                    ],
                    archive_services,
                    "objet_capture_enable",
                    "objet_capture_enable",
                ),
                (
                    [
                        "objet-capture-enable",
                        root,
                        "--approve",
                        "--reviewed-by",
                        PRIVATE_REVIEWER,
                        "--reenable",
                        "--format",
                        "json",
                    ],
                    archive_services,
                    "objet_capture_enable",
                    "objet_capture_enable",
                ),
                (
                    [
                        "migrate",
                        root,
                        "--target",
                        archive_services.FRONTMATTER_V03_TARGET,
                        "--approve",
                        "--format",
                        "json",
                    ],
                    archive_services,
                    "migrate_archive",
                    "migrate_archive",
                ),
                (
                    [
                        "migrate",
                        root,
                        "--target",
                        archive_services.FRONTMATTER_V03_TARGET,
                        "--approve",
                        "--revert",
                        "--format",
                        "json",
                    ],
                    archive_services,
                    "migrate_archive",
                    "migrate_archive",
                ),
                (
                    [
                        "saved-view-revert",
                        root,
                        "--receipt",
                        PRIVATE_RECEIPT,
                        "--approve",
                        "--expected-plan-sha256",
                        PRIVATE_DIGEST,
                        "--reviewed-by",
                        PRIVATE_REVIEWER,
                        "--format",
                        "json",
                    ],
                    saved_view_workflows,
                    "saved_view_revert",
                    "saved_view_revert",
                ),
                (
                    [
                        "objet-capture-batch",
                        root,
                        "--manifest",
                        PRIVATE_MANIFEST,
                        "--approve",
                        "--expected-plan-sha256",
                        PRIVATE_DIGEST,
                        "--reviewed-by",
                        PRIVATE_REVIEWER,
                        "--format",
                        "json",
                    ],
                    completion_workflows,
                    "objet_capture_batch_apply",
                    "objet_capture_batch",
                ),
                (
                    [
                        "markup-normalization",
                        root,
                        "--expected-plan-sha256",
                        PRIVATE_DIGEST,
                        "--approve",
                        "--reviewed-by",
                        PRIVATE_REVIEWER,
                        "--format",
                        "json",
                    ],
                    completion_workflows,
                    "markup_normalization_apply",
                    "markup_normalization",
                ),
                (
                    [
                        "markup-normalization-revert",
                        root,
                        "--receipt",
                        PRIVATE_RECEIPT,
                        "--approve",
                        "--expected-plan-sha256",
                        PRIVATE_DIGEST,
                        "--reviewed-by",
                        PRIVATE_REVIEWER,
                        "--format",
                        "json",
                    ],
                    completion_workflows,
                    "markup_normalization_revert",
                    "markup_normalization_revert",
                ),
                (
                    [
                        "markup-normalization-recovery",
                        root,
                        "--journal",
                        PRIVATE_JOURNAL,
                        "--mode",
                        "rollback",
                        "--approve",
                        "--expected-plan-sha256",
                        PRIVATE_DIGEST,
                        "--reviewed-by",
                        PRIVATE_REVIEWER,
                        "--format",
                        "json",
                    ],
                    completion_workflows,
                    "markup_normalization_recover",
                    "markup_normalization_recovery",
                ),
                (
                    [
                        "principal-register",
                        root,
                        "--principal-id",
                        PRIVATE_PRINCIPAL,
                        "--kind",
                        "person",
                        "--display-name",
                        PRIVATE_DISPLAY_NAME,
                        "--expected-plan-sha256",
                        PRIVATE_DIGEST,
                        "--approve",
                        "--reviewed-by",
                        PRIVATE_REVIEWER,
                        "--format",
                        "json",
                    ],
                    completion_workflows,
                    "principal_register",
                    "principal_register",
                ),
                (
                    [
                        "principal-unregister",
                        root,
                        "--principal-id",
                        PRIVATE_PRINCIPAL,
                        "--expected-plan-sha256",
                        PRIVATE_DIGEST,
                        "--approve",
                        "--reviewed-by",
                        PRIVATE_REVIEWER,
                        "--format",
                        "json",
                    ],
                    completion_workflows,
                    "principal_unregister",
                    "principal_unregister",
                ),
                (
                    [
                        "objet-capture-selection",
                        root,
                        "--staged-path",
                        PRIVATE_STAGED,
                        "--source-intake-receipt",
                        PRIVATE_RECEIPT,
                        "--approve",
                        "--reviewed-by",
                        PRIVATE_REVIEWER,
                        "--format",
                        "json",
                    ],
                    archive_services,
                    "objet_capture_selection_manifest",
                    "objet_capture_selection_record",
                ),
                (
                    [
                        "objet-capture",
                        root,
                        "--selection",
                        PRIVATE_SELECTION,
                        "--approve",
                        "--reviewed-by",
                        PRIVATE_REVIEWER,
                        "--format",
                        "json",
                    ],
                    archive_services,
                    "objet_capture_apply",
                    "objet_capture",
                ),
                (
                    [
                        "import-external",
                        root,
                        "--source",
                        "notion",
                        "--export",
                        PRIVATE_EXPORT,
                        "--approve",
                        "--reviewed-by",
                        PRIVATE_REVIEWER,
                        "--format",
                        "json",
                    ],
                    archive_services,
                    "import_external_archive",
                    "import_external_archive",
                ),
                (
                    [
                        "add-source",
                        root,
                        "--source-id",
                        PRIVATE_SOURCE_ID,
                        "--type",
                        "local_folder",
                        "--approve",
                        "--reviewed-by",
                        PRIVATE_REVIEWER,
                        "--format",
                        "json",
                    ],
                    archive_services,
                    "add_source_binding",
                    "add_source_binding",
                ),
                (
                    [
                        "transfer-ownership",
                        root,
                        "--new-owner",
                        PRIVATE_NEW_OWNER,
                        "--approve",
                        "--reviewed-by",
                        PRIVATE_REVIEWER,
                        "--format",
                        "json",
                    ],
                    archive_services,
                    "transfer_archive_ownership",
                    "transfer_archive_ownership",
                ),
            )
            before = _snapshot(root_path)
            for arguments, module, service, action in calls:
                with self.subTest(action=action, command=arguments[0]):
                    self._assert_cli_block(
                        arguments=arguments,
                        service_module=module,
                        service_name=service,
                        lifecycle_action=action,
                    )
            self.assertEqual(_snapshot(root_path), before)

    def test_text_blocker_says_binding_is_unimplemented_and_write_did_not_start(
        self,
    ) -> None:
        args = self.parser.parse_args(
            [
                "migrate",
                PRIVATE_ROOT_NAME,
                "--target",
                archive_services.FRONTMATTER_V03_TARGET,
                "--approve",
            ]
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            mock.patch.object(
                archive_services,
                "migrate_archive",
                side_effect=AssertionError("migration service entered"),
            ) as service,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = args.func(args)

        self.assertEqual(code, 1)
        service.assert_not_called()
        self.assertEqual(stdout.getvalue(), "")
        message = stderr.getvalue()
        self.assertIn("binding is not implemented", message)
        self.assertIn("write did not start", message)
        self.assertIn("dry-run or plan mode only", message)
        self.assertNotIn(PRIVATE_ROOT_NAME, message)

    def test_read_only_plans_and_dry_runs_still_dispatch(self) -> None:
        safe_result = {
            "ok": True,
            "state": "ready",
            "status": "ready",
            "dry_run": True,
            "blockers": [],
            "warnings": [],
            "would_change": [],
            "files_written": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root_path = self._root(Path(tmp))
            root = str(root_path)
            calls = (
                (
                    [
                        "objet-capture-enable",
                        root,
                        "--dry-run",
                        "--format",
                        "json",
                    ],
                    archive_services,
                    "objet_capture_enable",
                ),
                (
                    [
                        "objet-capture-enable",
                        root,
                        "--dry-run",
                        "--revoke",
                        "--format",
                        "json",
                    ],
                    archive_services,
                    "objet_capture_enable",
                ),
                (
                    [
                        "migrate",
                        root,
                        "--target",
                        archive_services.FRONTMATTER_V03_TARGET,
                        "--dry-run",
                        "--format",
                        "json",
                    ],
                    archive_services,
                    "migrate_archive",
                ),
                (
                    [
                        "saved-view-revert",
                        root,
                        "--receipt",
                        PRIVATE_RECEIPT,
                        "--dry-run",
                        "--format",
                        "json",
                    ],
                    saved_view_workflows,
                    "saved_view_revert_plan",
                ),
                (
                    [
                        "objet-capture-batch",
                        root,
                        "--manifest",
                        PRIVATE_MANIFEST,
                        "--dry-run",
                        "--format",
                        "json",
                    ],
                    completion_workflows,
                    "objet_capture_batch_plan",
                ),
                (
                    [
                        "markup-normalization-plan",
                        root,
                        "--dry-run",
                        "--format",
                        "json",
                    ],
                    completion_workflows,
                    "markup_normalization_plan",
                ),
                (
                    [
                        "markup-normalization-revert",
                        root,
                        "--receipt",
                        PRIVATE_RECEIPT,
                        "--dry-run",
                        "--format",
                        "json",
                    ],
                    completion_workflows,
                    "markup_normalization_revert_plan",
                ),
                (
                    [
                        "markup-normalization-recovery",
                        root,
                        "--journal",
                        PRIVATE_JOURNAL,
                        "--mode",
                        "rollback",
                        "--dry-run",
                        "--format",
                        "json",
                    ],
                    completion_workflows,
                    "markup_normalization_recovery_plan",
                ),
                (
                    [
                        "principal-register-plan",
                        root,
                        "--principal-id",
                        PRIVATE_PRINCIPAL,
                        "--kind",
                        "person",
                        "--display-name",
                        PRIVATE_DISPLAY_NAME,
                        "--dry-run",
                        "--format",
                        "json",
                    ],
                    completion_workflows,
                    "principal_registration_plan",
                ),
                (
                    [
                        "principal-unregister-plan",
                        root,
                        "--principal-id",
                        PRIVATE_PRINCIPAL,
                        "--dry-run",
                        "--format",
                        "json",
                    ],
                    completion_workflows,
                    "principal_unregistration_plan",
                ),
                (
                    [
                        "objet-capture-selection",
                        root,
                        "--staged-path",
                        PRIVATE_STAGED,
                        "--source-intake-receipt",
                        PRIVATE_RECEIPT,
                        "--dry-run",
                        "--format",
                        "json",
                    ],
                    archive_services,
                    "objet_capture_selection_manifest",
                ),
                (
                    [
                        "objet-capture",
                        root,
                        "--selection",
                        PRIVATE_SELECTION,
                        "--dry-run",
                        "--format",
                        "json",
                    ],
                    archive_services,
                    "objet_capture_dry_run",
                ),
                (
                    [
                        "import-external",
                        root,
                        "--source",
                        "notion",
                        "--export",
                        PRIVATE_EXPORT,
                        "--dry-run",
                        "--format",
                        "json",
                    ],
                    archive_services,
                    "external_import_dry_run",
                ),
                (
                    [
                        "add-source",
                        root,
                        "--source-id",
                        PRIVATE_SOURCE_ID,
                        "--type",
                        "local_folder",
                        "--dry-run",
                        "--format",
                        "json",
                    ],
                    archive_services,
                    "add_source_dry_run",
                ),
                (
                    [
                        "transfer-ownership",
                        root,
                        "--new-owner",
                        PRIVATE_NEW_OWNER,
                        "--dry-run",
                        "--format",
                        "json",
                    ],
                    archive_services,
                    "ownership_transfer_dry_run",
                ),
            )
            before = _snapshot(root_path)
            for arguments, module, service_name in calls:
                with self.subTest(command=arguments[0]), mock.patch.object(
                    module,
                    service_name,
                    return_value=dict(safe_result),
                ) as service:
                    args = self.parser.parse_args(arguments)
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        code = args.func(args)
                    self.assertEqual(code, 0, stderr.getvalue())
                service.assert_called_once()
            self.assertEqual(_snapshot(root_path), before)


if __name__ == "__main__":
    unittest.main()
