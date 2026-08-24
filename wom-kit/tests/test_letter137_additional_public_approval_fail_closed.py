from __future__ import annotations

import io
import inspect
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from wom_kit import archive_cli, archive_services, mcp_server
from wom_kit.exact_human_approval import (
    _ClaimedExactHumanApproval as ClaimedExactHumanApproval,
)


BLOCKER = "compound_exact_human_approval_binding_required"
PRIVATE = "PRIVATE-LETTER137-ADDITIONAL-PUBLIC-CANARY"
SHA = "a" * 64
KIT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_ARCHIVE = KIT_ROOT / "examples" / "fake-life-archive"

NON_BOOLEAN_GUARDED_WRITERS = (
    "zet_title_remap_write",
    "zet_title_remap_revert",
    "zet_title_remap_recover",
    "zet_title_remap_revert_recover",
    "zet_revision_write",
    "zet_revision_restore_proposal_from_snapshot",
    "zet_revision_restore_write",
    "zet_abstract_backfill_write",
    "zet_abstract_backfill_revert",
    "zet_abstract_backfill_recover",
    "notion_objet_manifest_locator_label",
    "notion_objet_link_convert",
    "activity_group_membership_write",
    "activity_group_membership_removal_write",
    "activity_group_membership_recover",
    "activity_group_membership_removal_recover",
    "mint_zet_batch",
    "retire_draft_batch",
    "ai_scratch_gc_for_zettel",
    "quarantine_foreign_block",
    "record_quarantine_decision",
    "notion_ancestor_fetch_adapter_run",
    "tiro_lossless_recovery_capture",
    "tiro_lossless_recovery_fetch_run",
    "zettel_edge_batch_write",
    "zettel_edge_revert",
    "zettel_edge_batch_revert",
    "imap_mailbox_adapter_manifest_write",
    "imap_mailbox_header_metadata_scan",
    "credential_keepassxc_write",
    "prehashed_objet_ledger_register",
    "object_storage_upload_evidence_register",
    "source_intake_record",
    "wom_kit_project_version_update_collision",
    "wom_kit_project_version_update",
    "source_intake_batch",
    "object_storage_upload_run",
    "object_storage_adopt_existing_run",
    "object_storage_wom_location_reconcile_run",
    "private_objet_source_metadata_write",
    "migrate_archive",
    "migrate_link_types_v03",
    "sync_base_link_types",
    "sync_base_link_types_revert",
    "migrate_link_types_v03_revert",
    "migrate_frontmatter_v03_revert",
    "migrate_frontmatter_v03",
    "objet_capture_selection_manifest",
    "objet_capture_enable",
)

APPROVE_ONLY_NON_BOOLEAN_GUARDS = {
    "activity_group_membership_recover",
    "activity_group_membership_removal_recover",
}


class _CliAssertions(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = archive_cli.build_parser()

    def run_cli(self, values: list[str]) -> tuple[int, str, str]:
        args = self.parser.parse_args(values)
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = args.func(args)
        return int(code), stdout.getvalue(), stderr.getvalue()

    def assert_fixed_json_block(
        self,
        code: int,
        stdout: str,
        stderr: str,
        *,
        lifecycle_action: str,
        reason_code: str = BLOCKER,
    ) -> dict[str, object]:
        self.assertEqual(code, 1, stderr)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["state"], "blocked")
        self.assertEqual(payload["lifecycle_action"], lifecycle_action)
        self.assertEqual(payload["reason_codes"], [reason_code])
        self.assertEqual(payload["files_written"], [])
        self.assertIs(payload["private_values_echoed"], False)
        self.assertNotIn(PRIVATE, stdout)
        return payload


class Letter137AdditionalPublicCliBoundaryTests(_CliAssertions):
    def test_all_top_level_approve_groups_block_before_dispatch(self) -> None:
        cases = (
            (
                "approve_github_repository_setup_plan",
                "approve_github_repository_setup_plan",
                ["github-repo", PRIVATE, "--approve", "--format", "json"],
            ),
            (
                "credential_keepassxc_write",
                "credential_keepassxc_write",
                [
                    "credential-keepassxc-write",
                    PRIVATE,
                    "--credential-id",
                    "cred:test",
                    "--approval-receipt",
                    PRIVATE,
                    "--entry-label",
                    PRIVATE,
                    "--approve",
                    "--format",
                    "json",
                ],
            ),
            (
                "tiro_lossless_recovery_capture",
                "tiro_lossless_recovery_capture",
                [
                    "tiro-lossless-recovery-capture",
                    PRIVATE,
                    "--bundle",
                    PRIVATE,
                    "--approve",
                    "--format",
                    "json",
                ],
            ),
            (
                "tiro_lossless_recovery_fetch_run",
                "tiro_lossless_recovery_fetch_run",
                [
                    "tiro-lossless-recovery-fetch-run",
                    PRIVATE,
                    "--credential-ref",
                    PRIVATE,
                    "--approve",
                    "--format",
                    "json",
                ],
            ),
            (
                "notion_objet_manifest_locator_label",
                "notion_objet_manifest_locator_label",
                [
                    "notion-objet-manifest-locator-label",
                    PRIVATE,
                    "--object-id",
                    "sha256:" + SHA,
                    "--locator-fingerprint",
                    "sha256:" + SHA,
                    "--approve",
                    "--format",
                    "json",
                ],
            ),
            (
                "imap_mailbox_header_metadata_scan",
                "imap_mailbox_header_metadata_scan",
                [
                    "imap-mailbox-header-metadata-scan",
                    PRIVATE,
                    "--adapter-id",
                    PRIVATE,
                    "--source-id",
                    "imap:test",
                    "--account-ref",
                    PRIVATE,
                    "--username-ref",
                    PRIVATE,
                    "--app-password-ref",
                    PRIVATE,
                    "--approve",
                    "--format",
                    "json",
                ],
            ),
            (
                "imap_mailbox_adapter_manifest_write",
                "imap_mailbox_adapter_manifest_write",
                [
                    "imap-mailbox-adapter-manifest-write",
                    PRIVATE,
                    "--adapter-id",
                    PRIVATE,
                    "--approve",
                    "--format",
                    "json",
                ],
            ),
            (
                "scan_source",
                "scan_source",
                [
                    "scan-source",
                    PRIVATE,
                    "--source",
                    PRIVATE,
                    "--approve",
                    "--format",
                    "json",
                ],
            ),
            (
                "restore_drill_dry_run",
                "restore_drill",
                [
                    "restore-drill",
                    PRIVATE,
                    "--target",
                    PRIVATE,
                    "--approve",
                    "--format",
                    "json",
                ],
            ),
            (
                "onboarding_plan",
                "onboard",
                [
                    "onboard",
                    "--target-root",
                    PRIVATE,
                    "--type",
                    "personal",
                    "--archive-id",
                    "archive:test",
                    "--principal-id",
                    "person:test",
                    "--approve",
                    "--format",
                    "json",
                ],
            ),
        )
        for service_name, lifecycle, argv in cases:
            with self.subTest(command=argv[0]), mock.patch.object(
                archive_services,
                service_name,
                side_effect=AssertionError("dispatch must stay closed"),
            ) as service:
                code, stdout, stderr = self.run_cli(argv)
                self.assert_fixed_json_block(
                    code,
                    stdout,
                    stderr,
                    lifecycle_action=lifecycle,
                )
                service.assert_not_called()

    def test_aliases_and_help_share_the_fixed_closed_boundary(self) -> None:
        top = next(
            action
            for action in self.parser._actions
            if action.dest == "command"
        )
        alias_groups = {
            "credential-keepassxc-write": ["keepassxc-write"],
            "tiro-lossless-recovery-capture": ["tiro-recovery-capture"],
            "tiro-lossless-recovery-fetch-run": ["tiro-recovery-fetch-run"],
            "notion-objet-manifest-locator-label": ["notion-objet-locator-label"],
            "imap-mailbox-header-metadata-scan": [
                "imap-header-metadata-scan",
                "mailbox-header-metadata-scan",
            ],
            "imap-mailbox-adapter-manifest-write": [
                "mailbox-adapter-manifest-write"
            ],
            "parcel": ["pack"],
        }
        self.assertEqual(len(archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS), 76)
        self.assertNotIn(
            "migrate",
            archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS,
        )
        self.assertNotIn(
            "zettel-objet-link",
            archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS,
        )
        self.assertIn(
            "zettel-objet-link-revert",
            archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS,
        )
        for canonical, aliases in alias_groups.items():
            for alias in aliases:
                self.assertIs(top.choices[canonical], top.choices[alias])
            if canonical != "parcel":
                approve = next(
                    action
                    for action in top.choices[canonical]._actions
                    if "--approve" in action.option_strings
                )
                self.assertEqual(
                    approve.help,
                    archive_cli.COMPOUND_APPROVAL_BLOCKED_HELP,
                )

        derive = top.choices["derive-text"]
        nested = next(
            action
            for action in derive._actions
            if action.dest == "derive_text_command"
        )
        capture = nested.choices["capture"]
        approve = next(
            action
            for action in capture._actions
            if "--approve" in action.option_strings
        )
        self.assertEqual(approve.help, archive_cli.COMPOUND_APPROVAL_BLOCKED_HELP)
        parcel_help = " ".join(top.choices["parcel"].format_help().split())
        init_help = " ".join(top.choices["init"].format_help().split())
        create_help = " ".join(top.choices["create-draft"].format_help().split())
        self.assertIn("Unavailable in v0.4.5", parcel_help)
        self.assertIn("unavailable in v0.4.5", init_help)
        self.assertIn("exact reviewed AI", create_help)

    def test_nested_derive_approve_blocks_before_single_or_manifest_read(self) -> None:
        cases = (
            (
                [
                    "derive-text",
                    "capture",
                    PRIVATE,
                    "--approve",
                    "--format",
                    "json",
                ],
                "derived_text_capture_apply",
                "derived_text_capture_apply",
            ),
            (
                [
                    "derive-text",
                    "capture",
                    PRIVATE,
                    "--from-manifest",
                    PRIVATE,
                    "--approve",
                    "--format",
                    "json",
                ],
                "derived_text_capture_manifest_apply",
                "derived_text_capture_manifest_apply",
            ),
        )
        for argv, service_name, lifecycle in cases:
            with self.subTest(lifecycle=lifecycle), mock.patch.object(
                archive_services,
                service_name,
                side_effect=AssertionError("derived input must not be read"),
            ) as service:
                code, stdout, stderr = self.run_cli(argv)
                self.assert_fixed_json_block(
                    code,
                    stdout,
                    stderr,
                    lifecycle_action=lifecycle,
                )
                service.assert_not_called()

    def test_human_create_draft_blocks_before_body_file_or_service(self) -> None:
        for mode in ([], ["--approve"]):
            with self.subTest(mode=mode), mock.patch.object(
                archive_cli,
                "_read_body_arg",
                side_effect=AssertionError("private body file must not be read"),
            ) as body_reader, mock.patch.object(
                archive_services,
                "create_draft_zettel",
                side_effect=AssertionError("service must not be called"),
            ) as service:
                code, stdout, stderr = self.run_cli(
                    [
                        "create-draft",
                        PRIVATE,
                        "--title",
                        PRIVATE,
                        "--body-file",
                        PRIVATE,
                        "--format",
                        "json",
                        *mode,
                    ]
                )
                self.assert_fixed_json_block(
                    code,
                    stdout,
                    stderr,
                    lifecycle_action="create_draft",
                )
                body_reader.assert_not_called()
                service.assert_not_called()

    def test_dry_run_dispatch_remains_available(self) -> None:
        cases = (
            (
                "github_repository_setup_plan",
                ["github-repo", PRIVATE, "--dry-run", "--format", "json"],
            ),
            (
                "credential_keepassxc_write",
                [
                    "credential-keepassxc-write",
                    PRIVATE,
                    "--credential-id",
                    "cred:test",
                    "--approval-receipt",
                    "receipts/test.json",
                    "--entry-label",
                    "safe",
                    "--dry-run",
                    "--format",
                    "json",
                ],
            ),
            (
                "tiro_lossless_recovery_capture",
                [
                    "tiro-lossless-recovery-capture",
                    PRIVATE,
                    "--bundle",
                    PRIVATE,
                    "--dry-run",
                    "--format",
                    "json",
                ],
            ),
            (
                "tiro_lossless_recovery_fetch_run",
                [
                    "tiro-lossless-recovery-fetch-run",
                    PRIVATE,
                    "--dry-run",
                    "--format",
                    "json",
                ],
            ),
            (
                "notion_objet_manifest_locator_label",
                [
                    "notion-objet-manifest-locator-label",
                    PRIVATE,
                    "--object-id",
                    "sha256:" + SHA,
                    "--locator-fingerprint",
                    "sha256:" + SHA,
                    "--dry-run",
                    "--format",
                    "json",
                ],
            ),
            (
                "imap_mailbox_header_metadata_scan",
                [
                    "imap-mailbox-header-metadata-scan",
                    PRIVATE,
                    "--adapter-id",
                    "safe",
                    "--source-id",
                    "imap:test",
                    "--account-ref",
                    "safe",
                    "--username-ref",
                    "safe",
                    "--app-password-ref",
                    "safe",
                    "--dry-run",
                    "--format",
                    "json",
                ],
            ),
            (
                "imap_mailbox_adapter_manifest_write",
                [
                    "imap-mailbox-adapter-manifest-write",
                    PRIVATE,
                    "--adapter-id",
                    "safe",
                    "--dry-run",
                    "--format",
                    "json",
                ],
            ),
            (
                "source_scan_dry_run",
                [
                    "scan-source",
                    PRIVATE,
                    "--source",
                    "local:test",
                    "--dry-run",
                    "--format",
                    "json",
                ],
            ),
            (
                "restore_drill_dry_run",
                [
                    "restore-drill",
                    PRIVATE,
                    "--target",
                    PRIVATE,
                    "--dry-run",
                    "--format",
                    "json",
                ],
            ),
            (
                "onboarding_plan",
                [
                    "onboard",
                    "--target-root",
                    PRIVATE,
                    "--type",
                    "personal",
                    "--archive-id",
                    "archive:test",
                    "--principal-id",
                    "person:test",
                    "--dry-run",
                    "--format",
                    "json",
                ],
            ),
        )
        for service_name, argv in cases:
            with self.subTest(command=argv[0]), mock.patch.object(
                archive_services,
                service_name,
                return_value={"ok": True, "dry_run": True, "files_written": []},
            ) as service:
                code, stdout, stderr = self.run_cli(argv)
                self.assertEqual(code, 0, stderr)
                self.assertTrue(json.loads(stdout)["ok"])
                service.assert_called_once()


class Letter137AdditionalPublicServiceBoundaryTests(unittest.TestCase):
    def assert_service_block(
        self,
        result: dict[str, object],
        lifecycle_action: str,
    ) -> None:
        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["lifecycle_action"], lifecycle_action)
        self.assertEqual(result["reason_codes"], [BLOCKER])
        self.assertEqual(result["would_change"], [])
        self.assertEqual(result["files_written"], [])
        self.assertIs(result["private_values_echoed"], False)
        self.assertNotIn(PRIVATE, json.dumps(result, ensure_ascii=False))

    def test_public_services_block_before_private_or_provider_access(self) -> None:
        root = Path(PRIVATE)
        cases = (
            (
                "tiro_lossless_recovery_capture",
                lambda: archive_services.tiro_lossless_recovery_capture(
                    root, bundle_path=PRIVATE, approve=True
                ),
            ),
            (
                "tiro_lossless_recovery_fetch_run",
                lambda: archive_services.tiro_lossless_recovery_fetch_run(
                    root, credential_ref=PRIVATE, approve=True
                ),
            ),
            (
                "notion_objet_manifest_locator_label",
                lambda: archive_services.notion_objet_manifest_locator_label(
                    root,
                    object_id="sha256:" + SHA,
                    locator_fingerprint="sha256:" + SHA,
                    approve=True,
                ),
            ),
            (
                "derived_text_capture_apply",
                lambda: archive_services.derived_text_capture_apply(
                    root,
                    text_file=PRIVATE,
                    source_object_id="sha256:" + SHA,
                    derivation_kind="transcription",
                    tool_name="safe",
                    tool_version="1",
                    review_status="reviewed",
                    reviewed_by="person:test",
                ),
            ),
            (
                "derived_text_capture_manifest_apply",
                lambda: archive_services.derived_text_capture_manifest_apply(
                    root, PRIVATE, reviewed_by="person:test"
                ),
            ),
            (
                "derived_text_register",
                lambda: archive_services._derived_text_register(
                    root,
                    archive_id="archive:test",
                    stored_text_bytes=PRIVATE.encode(),
                    source_text_encoding="utf-8",
                    source_text_sha256=SHA,
                    text_filename=PRIVATE,
                    source_object_id="sha256:" + SHA,
                    source_record_present=True,
                    derivation_kind="transcription",
                    tool_name="safe",
                    tool_version="1",
                    review_status="reviewed",
                    approve=True,
                    reviewed_by="person:test",
                    captured_at="2026-08-20T00:00:00Z",
                ),
            ),
            (
                "copy_restore_drill_tree",
                lambda: archive_services.copy_restore_drill_tree(root, root / PRIVATE),
            ),
            (
                "approve_github_repository_setup_plan",
                lambda: archive_services.approve_github_repository_setup_plan(
                    root, reviewed_by=PRIVATE
                ),
            ),
            (
                "credential_keepassxc_write",
                lambda: archive_services.credential_keepassxc_write(
                    root,
                    credential_id="cred:test",
                    approval_receipt=PRIVATE,
                    entry_label=PRIVATE,
                    approve=True,
                    dry_run=False,
                ),
            ),
            (
                "imap_mailbox_header_metadata_scan",
                lambda: archive_services.imap_mailbox_header_metadata_scan(
                    root,
                    adapter_id=PRIVATE,
                    source_id="imap:test",
                    account_ref=PRIVATE,
                    username_ref=PRIVATE,
                    app_password_ref=PRIVATE,
                    approve=True,
                    dry_run=False,
                ),
            ),
            (
                "imap_mailbox_adapter_manifest_write",
                lambda: archive_services.imap_mailbox_adapter_manifest_write(
                    root,
                    adapter_id=PRIVATE,
                    approve=True,
                    dry_run=False,
                ),
            ),
            (
                "scan_source",
                lambda: archive_services.scan_source(
                    root,
                    source_id=PRIVATE,
                    reviewed_by=PRIVATE,
                    source_root=PRIVATE,
                ),
            ),
            (
                "pack_work_context",
                lambda: archive_services.pack_work_context(
                    root,
                    view_id=PRIVATE,
                    purpose=PRIVATE,
                ),
            ),
        )
        with mock.patch.object(
            archive_services,
            "require_existing_archive_root",
            side_effect=AssertionError("archive root must not be read"),
        ) as root_reader, mock.patch.object(
            archive_services,
            "require_yaml",
            side_effect=AssertionError("YAML runtime must not be opened"),
        ) as yaml_reader:
            for lifecycle, invoke in cases:
                with self.subTest(lifecycle=lifecycle):
                    self.assert_service_block(invoke(), lifecycle)
        root_reader.assert_not_called()
        yaml_reader.assert_not_called()

    def test_all_49_public_writers_reject_integer_zero_before_reads(self) -> None:
        class UnreadableRequiredArgument:
            def __bool__(self) -> bool:
                raise AssertionError("required argument must not be inspected")

            def __fspath__(self) -> str:
                raise AssertionError("path argument must not be inspected")

            def __iter__(self):
                raise AssertionError("iterable argument must not be inspected")

            def __str__(self) -> str:
                raise AssertionError("argument must not be rendered")

        self.assertEqual(len(NON_BOOLEAN_GUARDED_WRITERS), 49)
        blocker = archive_services.COMPOUND_EXACT_HUMAN_APPROVAL_REQUIRED
        with (
            mock.patch.object(
                archive_services,
                "require_existing_archive_root",
                side_effect=AssertionError("archive root must not be read"),
            ) as root_reader,
            mock.patch.object(
                archive_services,
                "read_archive_id",
                side_effect=AssertionError("archive identity must not be read"),
            ) as archive_id_reader,
        ):
            for function_name in NON_BOOLEAN_GUARDED_WRITERS:
                function = getattr(archive_services, function_name)
                signature = inspect.signature(function)
                args: list[object] = []
                kwargs: dict[str, object] = {}
                for parameter in signature.parameters.values():
                    if parameter.kind in {
                        inspect.Parameter.VAR_POSITIONAL,
                        inspect.Parameter.VAR_KEYWORD,
                    }:
                        continue
                    if parameter.name == "approve":
                        value: object = 0
                    elif parameter.name == "dry_run":
                        value = (
                            False
                            if function_name in APPROVE_ONLY_NON_BOOLEAN_GUARDS
                            else 0
                        )
                    elif parameter.default is not inspect.Parameter.empty:
                        continue
                    else:
                        value = UnreadableRequiredArgument()
                    if parameter.kind is inspect.Parameter.POSITIONAL_ONLY:
                        args.append(value)
                    else:
                        kwargs[parameter.name] = value

                with self.subTest(function=function_name):
                    result = function(*args, **kwargs)
                    self.assertFalse(result["ok"])
                    self.assertEqual(result["state"], "blocked")
                    self.assertEqual(result["blockers"], [blocker])
                    self.assertEqual(result["reason_codes"], [blocker])
                    self.assertEqual(result["would_change"], [])
                    self.assertEqual(result["files_written"], [])
                    self.assertIs(result["private_values_echoed"], False)

        root_reader.assert_not_called()
        archive_id_reader.assert_not_called()

    def test_create_draft_spoofs_block_before_archive_or_body_processing(self) -> None:
        claim = ClaimedExactHumanApproval(
            Path(PRIVATE),
            "archive:test",
            bytearray(b"test-key"),
            "approval:test",
            "a" * 64,
            "b" * 64,
            lambda: datetime.now(timezone.utc),
        )
        try:
            cases = (
                {
                    "approved": True,
                    "creation_mode": "human_written",
                    "exact_human_approval_claim": claim,
                },
                {
                    "approved": True,
                    "creation_mode": "ai_generated",
                    "exact_human_approval_claim": object(),
                },
                {
                    "approved": False,
                    "creation_mode": "ai_generated",
                    "exact_human_approval_claim": claim,
                },
            )
            with mock.patch.object(
                archive_services,
                "require_yaml",
                side_effect=AssertionError("must block before YAML"),
            ) as yaml_reader, mock.patch.object(
                archive_services,
                "require_existing_archive_root",
                side_effect=AssertionError("must block before archive read"),
            ) as root_reader:
                for kwargs in cases:
                    with self.subTest(kwargs=kwargs):
                        result = archive_services.create_draft_zettel(
                            Path(PRIVATE),
                            title=PRIVATE,
                            body=PRIVATE,
                            dry_run=False,
                            **kwargs,
                        )
                        self.assert_service_block(result, "create_draft")
            yaml_reader.assert_not_called()
            root_reader.assert_not_called()
        finally:
            claim.close()

    def test_restore_and_parcel_legacy_cores_are_private_and_unreachable(self) -> None:
        self.assertTrue(hasattr(archive_services, "_copy_restore_drill_tree_legacy_core"))
        self.assertTrue(hasattr(archive_services, "_pack_work_context_legacy_core"))
        self.assertNotIn(
            "_copy_restore_drill_tree_legacy_core",
            inspect.getsource(archive_services.copy_restore_drill_tree),
        )
        self.assertNotIn(
            "_pack_work_context_legacy_core",
            inspect.getsource(archive_services.pack_work_context),
        )
        self.assertNotIn(
            "archive_services.pack_work_context",
            inspect.getsource(archive_cli.command_pack),
        )


class Letter137InitParcelAndAdvisoryTests(_CliAssertions):
    def test_init_cli_and_mcp_non_dry_run_block_before_target_reads(self) -> None:
        argv = [
            "init",
            PRIVATE,
            "--type",
            "personal",
            "--archive-id",
            "archive:test",
            "--principal-id",
            "person:test",
        ]
        with mock.patch.object(
            archive_cli,
            "require_yaml",
            side_effect=AssertionError("must block before YAML"),
        ) as cli_yaml, mock.patch.object(
            archive_cli,
            "_copy_template",
            side_effect=AssertionError("must not write template"),
        ) as _copy_template:
            code, stdout, stderr = self.run_cli(argv)
        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertNotIn(PRIVATE, stderr)
        self.assertIn("not implemented", stderr)
        cli_yaml.assert_not_called()
        _copy_template.assert_not_called()

        with mock.patch.object(
            mcp_server,
            "require_path_arg",
            side_effect=AssertionError("must block before target parse"),
        ) as target_reader, mock.patch.object(
            archive_cli,
            "require_yaml",
            side_effect=AssertionError("must block before YAML"),
        ) as mcp_yaml:
            result = mcp_server.tool_archive_init(
                {
                    "archive_root": PRIVATE,
                    "archive_type": "personal",
                    "archive_id": "archive:test",
                    "principal_id": "person:test",
                    "dry_run": False,
                }
            )
        payload = result["structuredContent"]
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["reason_codes"], [BLOCKER])
        self.assertEqual(payload["files_written"], [])
        self.assertNotIn(PRIVATE, json.dumps(result, ensure_ascii=False))
        target_reader.assert_not_called()
        mcp_yaml.assert_not_called()

    def test_init_dry_run_and_mcp_default_remain_read_only(self) -> None:
        definition = next(
            item
            for item in mcp_server.TOOL_DEFINITIONS
            if item.get("name") == "archive_init"
        )
        self.assertIs(
            definition["inputSchema"]["properties"]["dry_run"]["default"],
            True,
        )
        self.assertIn("unavailable in v0.4.5", definition["description"])
        with tempfile.TemporaryDirectory() as tmp:
            cli_target = Path(tmp) / "cli-target"
            code, _stdout, stderr = self.run_cli(
                [
                    "init",
                    str(cli_target),
                    "--type",
                    "personal",
                    "--archive-id",
                    "archive:test",
                    "--principal-id",
                    "person:test",
                    "--dry-run",
                ]
            )
            self.assertEqual(code, 0, stderr)
            self.assertFalse(cli_target.exists())

            mcp_target = Path(tmp) / "mcp-target"
            result = mcp_server.tool_archive_init(
                {
                    "archive_root": str(mcp_target),
                    "archive_type": "personal",
                    "archive_id": "archive:test",
                    "principal_id": "person:test",
                }
            )
            payload = result["structuredContent"]
            self.assertTrue(payload["dry_run"])
            self.assertFalse(mcp_target.exists())

    def test_parcel_and_pack_block_before_service(self) -> None:
        for command in ("parcel", "pack"):
            with self.subTest(command=command), mock.patch.object(
                archive_services,
                "pack_work_context",
                side_effect=AssertionError("view/private bytes must not be read"),
            ) as service:
                code, stdout, stderr = self.run_cli(
                    [
                        command,
                        PRIVATE,
                        "--view",
                        PRIVATE,
                        "--purpose",
                        PRIVATE,
                        "--format",
                        "json",
                    ]
                )
                self.assert_fixed_json_block(
                    code,
                    stdout,
                    stderr,
                    lifecycle_action="pack_work_context",
                )
                service.assert_not_called()

    def test_legacy_approval_metadata_is_advisory_only(self) -> None:
        handoff = archive_services.approval_handoff_audit(
            EXAMPLE_ARCHIVE,
            handoff_record=None,
            dry_run=True,
        )
        self.assertFalse(handoff["future_operation_authorized"])
        self.assertFalse(handoff["summary"]["future_operation_authorized"])
        self.assertEqual(handoff["binding_state"], "legacy_unbound")
        self.assertEqual(handoff["authority_classification"], "advisory")

        with tempfile.TemporaryDirectory() as tmp:
            receipt_root = Path(tmp)
            receipt_relative = (
                f"{archive_services.CREDENTIAL_ACCESS_APPROVAL_RECEIPTS_DIR}/"
                "safe.credential-access-approval.json"
            )
            receipt_path = receipt_root.joinpath(*receipt_relative.split("/"))
            receipt_path.parent.mkdir(parents=True)
            receipt_path.write_text(
                json.dumps(
                    {
                        "receipt_kind": "credential_access_approval",
                        "schema_version": "wom-credential-access-approval/v0.1",
                        "archive_id": "archive:test",
                        "receipt_id": "receipt:test",
                        "decision": "approve_once",
                        "reviewed_by": "human:tester",
                        "reviewed_at": "2026-08-20T00:00:00Z",
                        "credential": {"credential_id": "cred:test"},
                        "broker_request": {
                            "action_kind": "plaintext_secret_migration",
                            "store_kind": "password_manager",
                            "consumer": "wom:adapter:keepassxc",
                        },
                        "secret_material": {"included": False},
                        "files_written": [receipt_relative],
                    }
                ),
                encoding="utf-8",
            )
            review = archive_services.credential_access_approval_receipt_review(
                receipt_root,
                receipt_relative,
                expected_archive_id="archive:test",
                expected_credential_id="cred:test",
                expected_action_kind="plaintext_secret_migration",
                expected_store_kind="password_manager",
                expected_consumer="wom:adapter:keepassxc",
                expected_decision="approve_once",
            )
        self.assertTrue(review["structural_verification_ok"])
        self.assertEqual(review["binding_state"], "legacy_unbound")
        self.assertEqual(review["authority_classification"], "advisory")
        self.assertFalse(review["future_adapter_authorized"])

        policy = archive_services.credential_policy_check(
            EXAMPLE_ARCHIVE,
            credential_id="cred:openai-api",
            credential_ref="secret:keepassxc-openai-api",
            credential_kind="openai_api_key",
            provider="openai",
            action_kind="plaintext_secret_migration",
            approval_decision="approve_once",
            store_kind="password_manager",
            adapter_kind="keepassxc_cli",
            operation="plaintext_secret_migration",
            consumer="wom:adapter:keepassxc",
            reviewed_by="human:tester",
            platform="windows",
            dry_run=True,
        )
        self.assertEqual(policy["policy_result"], "legacy_unbound")
        self.assertEqual(policy["binding_state"], "legacy_unbound")
        self.assertEqual(policy["authority_classification"], "advisory")
        self.assertFalse(
            policy["policy_evaluation"][
                "would_allow_future_adapter_after_receipt"
            ]
        )
        self.assertFalse(
            policy["policy_evaluation"]["future_adapter_has_verified_receipt"]
        )

        imap = archive_services.imap_mailbox_material_capture_approval_audit(
            EXAMPLE_ARCHIVE,
            material_selection_receipt=(
                "receipts/imap-mailbox-material-selection/missing.json"
            ),
            approval_receipt=(
                "receipts/imap-mailbox-material-capture-approvals/missing.json"
            ),
            dry_run=True,
        )
        self.assertFalse(imap["future_capture_authorized"])
        self.assertEqual(imap["binding_state"], "legacy_unbound")
        self.assertEqual(imap["authority_classification"], "advisory")
        self.assertNotEqual(
            imap["audit_state"],
            "approval_receipt_verified_for_future_material_capture",
        )


class Letter137ExactJsonProjectionTests(_CliAssertions):
    def test_missing_modes_and_reviewers_use_stdout_json_for_all_aliases(self) -> None:
        cases = (
            (["promote", PRIVATE, "--path", PRIVATE, "--format", "json"], "promote_zettel", "promote_approval_required"),
            (["promote", PRIVATE, "--path", PRIVATE, "--approve", "--format", "json"], "promote_zettel", "promote_reviewer_required"),
            (["mint-zet", PRIVATE, "--path", PRIVATE, "--format", "json"], "mint_zettel", "mint_approval_required"),
            (["mint-zettel", PRIVATE, "--path", PRIVATE, "--approve", "--format", "json"], "mint_zettel", "mint_reviewer_required"),
            (["retire-draft", PRIVATE, "--path", PRIVATE, "--format", "json"], "retire_minted_draft", "retire_execution_mode_required"),
            (["retire-minted-draft", PRIVATE, "--path", PRIVATE, "--approve", "--format", "json"], "retire_minted_draft", "retire_reviewer_required"),
        )
        for argv, lifecycle, reason in cases:
            with self.subTest(command=argv[0], reason=reason):
                code, stdout, stderr = self.run_cli(argv)
                self.assert_fixed_json_block(
                    code,
                    stdout,
                    stderr,
                    lifecycle_action=lifecycle,
                    reason_code=reason,
                )

    def test_zettel_edge_reviewer_and_preview_failures_never_start_binding(self) -> None:
        base = [
            "zettel-edge",
            PRIVATE,
            "--from-zettel",
            "zet_source",
            "--target",
            "zet_target",
            "--edge-type",
            "related",
            "--approve",
            "--format",
            "json",
        ]
        with mock.patch.object(
            archive_services,
            "zettel_edge_write",
            side_effect=AssertionError("service must not run without reviewer"),
        ) as service:
            code, stdout, stderr = self.run_cli(base)
        self.assert_fixed_json_block(
            code,
            stdout,
            stderr,
            lifecycle_action="zettel_edge_write",
            reason_code="zettel_edge_reviewed_by_required",
        )
        service.assert_not_called()

        preview = {
            "ok": False,
            "receipt_path": "receipts/edges/safe.edge.json",
            "entity_type_contract": {
                "registry_source": "archive_local",
                "source_entity_type": "Zettel",
                "target_entity_type": "Zettel",
                "from_allowed": None,
                "to_allowed": None,
                "status": "unavailable",
                "blocker_codes": ["link_type_contract_unavailable"],
                "private": PRIVATE,
            },
            "private": PRIVATE,
            "blockers": [PRIVATE],
            "files_written": [],
        }
        with mock.patch.object(
            archive_services,
            "zettel_edge_write",
            return_value=preview,
        ), mock.patch.object(
            archive_cli.operation_approval_binding,
            "zettel_edge_approval_binding",
            side_effect=AssertionError("binding must not start"),
        ) as binding:
            code, stdout, stderr = self.run_cli(
                [*base, "--reviewed-by", "person:test"]
            )
        payload = self.assert_fixed_json_block(
            code,
            stdout,
            stderr,
            lifecycle_action="zettel_edge_write",
            reason_code="zettel_edge_preflight_blocked",
        )
        self.assertEqual(
            payload["entity_type_contract"]["blocker_codes"],
            ["link_type_contract_unavailable"],
        )
        binding.assert_not_called()

    def test_preview_blockers_are_projected_without_private_values(self) -> None:
        cases = (
            (
                "promote_zettel_dry_run",
                "promote_zet_approval_binding",
                [
                    "promote",
                    PRIVATE,
                    "--path",
                    PRIVATE,
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                    "--format",
                    "json",
                ],
                "promote_zettel",
                "promote_preflight_blocked",
            ),
            (
                "mint_zettel_dry_run",
                "mint_zet_approval_binding",
                [
                    "mint-zet",
                    PRIVATE,
                    "--path",
                    PRIVATE,
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                    "--format",
                    "json",
                ],
                "mint_zettel",
                "mint_preflight_blocked",
            ),
            (
                "retire_minted_draft",
                "retire_draft_approval_binding",
                [
                    "retire-draft",
                    PRIVATE,
                    "--path",
                    PRIVATE,
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                    "--format",
                    "json",
                ],
                "retire_minted_draft",
                "retire_preflight_blocked",
            ),
        )
        for service_name, binding_name, argv, lifecycle, reason in cases:
            with self.subTest(command=argv[0]), mock.patch.object(
                archive_services,
                service_name,
                return_value={
                    "ok": False,
                    "blockers": [PRIVATE],
                    "private_path": PRIVATE,
                    "files_written": [],
                },
            ), mock.patch.object(
                archive_cli.operation_approval_binding,
                binding_name,
                side_effect=AssertionError("binding must not start"),
            ) as binding:
                code, stdout, stderr = self.run_cli(argv)
                self.assert_fixed_json_block(
                    code,
                    stdout,
                    stderr,
                    lifecycle_action=lifecycle,
                    reason_code=reason,
                )
                binding.assert_not_called()

    def test_service_exceptions_are_fixed_content_free_json(self) -> None:
        cases = (
            (
                "zettel_edge_write",
                [
                    "zettel-edge",
                    PRIVATE,
                    "--from-zettel",
                    "zet_source",
                    "--target",
                    "zet_target",
                    "--edge-type",
                    "related",
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                    "--format",
                    "json",
                ],
                "zettel_edge_write",
                "zettel_edge_failed_safely",
            ),
            (
                "promote_zettel_dry_run",
                [
                    "promote",
                    PRIVATE,
                    "--path",
                    PRIVATE,
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                    "--format",
                    "json",
                ],
                "promote_zettel",
                "promote_workflow_failed_safely",
            ),
            (
                "mint_zettel_dry_run",
                [
                    "mint-zettel",
                    PRIVATE,
                    "--path",
                    PRIVATE,
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                    "--format",
                    "json",
                ],
                "mint_zettel",
                "mint_service_failed",
            ),
            (
                "retire_minted_draft",
                [
                    "retire-minted-draft",
                    PRIVATE,
                    "--path",
                    PRIVATE,
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                    "--format",
                    "json",
                ],
                "retire_minted_draft",
                "retire_workflow_failed_safely",
            ),
        )
        for service_name, argv, lifecycle, reason in cases:
            with self.subTest(command=argv[0]), mock.patch.object(
                archive_services,
                service_name,
                side_effect=archive_services.ArchiveServiceError(PRIVATE),
            ):
                code, stdout, stderr = self.run_cli(argv)
                self.assert_fixed_json_block(
                    code,
                    stdout,
                    stderr,
                    lifecycle_action=lifecycle,
                    reason_code=reason,
                )


if __name__ == "__main__":
    unittest.main()
