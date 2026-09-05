from __future__ import annotations

import argparse
import copy
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import unittest
from unittest import mock

from wom_kit import archive_cli, archive_services, command_status, mcp_server


class V0419CapabilityAvailabilityTests(unittest.TestCase):
    def test_shared_gate_preserves_public_action_names_without_handler_inspection(self) -> None:
        expected = {
            "add-source": "add_source_binding",
            "discard-draft": "discard_draft_apply",
            "credential-lifecycle": "authenticated_credential_lifecycle_decision",
            "github-repo": "approve_github_repository_setup_plan",
            "import-external": "import_external_archive",
            "migrate": "migrate_archive",
            "parcel": "pack_work_context",
            "notion-page-recovery": "authenticated_notion_page_recovery_execute",
            "objet-capture-selection": "objet_capture_selection_record",
            "prehashed-objet-ledger": "prehashed_objet_ledger_register",
            "transfer-ownership": "transfer_archive_ownership",
            "revert-batch": "zettel_edge_batch_revert",
            "mint-zet-batch": "mint_zet_batch",
        }
        args = argparse.Namespace(func=mock.Mock(), from_manifest=None)
        for path, action in expected.items():
            with self.subTest(path=path):
                self.assertEqual(archive_cli._unavailable_writer_lifecycle_action(path, args), action)
        args.func.assert_not_called()
        for value, action in (
            (None, "derived_text_capture_apply"),
            ("PRIVATE_MANIFEST_MUST_NOT_BE_ECHOED", "derived_text_capture_manifest_apply"),
        ):
            args.from_manifest = value
            self.assertEqual(
                archive_cli._unavailable_writer_lifecycle_action("derive-text capture", args), action
            )

    def test_fixed_closed_command_preserves_parser_json_default(self) -> None:
        output, errors = io.StringIO(), io.StringIO()
        argv = ["principal-register", "synthetic-root-must-not-be-read", "--principal-id", "team:synthetic",
                "--kind", "team", "--display-name", "Synthetic app", "--expected-plan-sha256",
                "sha256:" + "a" * 64, "--approve", "--reviewed-by", "person:synthetic"]
        with mock.patch.object(archive_cli, "command_principal_register") as handler:
            with redirect_stdout(output), redirect_stderr(errors):
                code = archive_cli.main(argv)
        handler.assert_not_called()
        result = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(errors.getvalue(), "")
        self.assertEqual(result["capability_state"], "writer_unavailable")
        self.assertEqual(result["effects_state"], "none")
        self.assertNotIn("synthetic-root", output.getvalue())

    def inventory(self) -> dict[str, object]:
        parser = archive_cli.build_parser()
        return archive_cli._parser_capability_inventory(parser)

    def test_audited_history_is_shared_without_claiming_success(self) -> None:
        parser = archive_cli.build_parser()
        inventory = archive_cli._parser_capability_inventory(parser)
        expected_commands = {
            "discard-draft", "discard-draft-restore", "mint-zet-batch",
            "retire-draft-batch", "zettel-edge-batch", "zet-revision-write",
            "zet-revision-restore-write", "remint-reconcile", "retire-draft-reconcile",
        }
        self.assertEqual(
            command_status.AUDITED_PREVIOUSLY_EXPOSED_APPROVAL_COMMANDS,
            expected_commands,
        )
        expected_history = {
            "state": "previously_exposed_now_restricted",
            "exposed_at_tag": "v0.3.320",
            "restricted_at_tag": "v0.4.0",
            "evidence_basis": "public_tag_parser_and_dispatch",
            "successful_use_verified": False,
        }
        by_path = {row["canonical_path"]: row for row in inventory["commands"]}
        self.assertEqual({
            path for path, row in by_path.items()
            if row["approval_exposure_history"]["state"]
            == "previously_exposed_now_restricted"
        }, expected_commands)
        leaves = command_status._subparser_actions(parser)[0].choices
        for path in sorted(expected_commands):
            with self.subTest(command=path):
                row = by_path[path]
                self.assertEqual(row["approval_exposure_history"], expected_history)
                for invocation_path in (path, *row["alias_paths"]):
                    for mode in ("dry_run", "approve"):
                        availability = command_status.resolve_capability_availability(
                            inventory, invocation_path, requested_mode=mode
                        )
                        self.assertEqual(
                            availability["approval_exposure_history"], expected_history
                        )
                help_text = " ".join(leaves[path].format_help().split())
                self.assertIn("exposed approval at v0.3.320", help_text)
                self.assertIn("restricted this path at v0.4.0", help_text)
                self.assertIn("Successful execution at those versions is not verified", help_text)
                self.assertIn("earlier-version bypass is not supported", help_text)
        for path in ("object-storage-upload", "create-draft"):
            self.assertEqual(by_path[path]["approval_exposure_history"], {
                "state": "history_not_audited", "successful_use_verified": False,
            })
            self.assertNotIn("exposed approval at v0.3.320", leaves[path].format_help())
        self.assertNotIn("not implemented yet", leaves["discard-draft"].format_help())
        self.assertNotIn("last_working_version", json.dumps(inventory))

    def test_history_never_labels_reopened_surface_currently_restricted(self) -> None:
        for status in (command_status.APPROVAL_AVAILABLE, command_status.APPROVAL_NOT_EXPOSED):
            self.assertEqual(command_status.approval_exposure_history("discard-draft", status), {
                "state": "history_not_audited", "successful_use_verified": False,
            })

    def test_untrusted_history_is_rejected_without_echoing_private_values(self) -> None:
        inventory = self.inventory()
        known = next(
            row for row in inventory["commands"]
            if row["canonical_path"] == "discard-draft"
        )
        history = known["approval_exposure_history"]
        invalid_histories = [
            {**history, "exposed_at_tag": "PRIVATE-HISTORY-MARKER"},
            {**history, "successful_use_verified": True},
            {**history, "successful_use_verified": 0},
            {**history, "last_working_version": "v0.3.320"},
            {"state": "never_implemented", "successful_use_verified": False},
            None,
        ]
        for invalid in invalid_histories:
            with self.subTest(history=invalid):
                tampered = copy.deepcopy(inventory)
                tampered_row = next(
                    row for row in tampered["commands"]
                    if row["canonical_path"] == "discard-draft"
                )
                tampered_row["approval_exposure_history"] = invalid
                with self.assertRaisesRegex(ValueError, "^command_status_inventory_invalid$"):
                    command_status.resolve_capability_availability(
                        tampered, "discard-draft", requested_mode="approve"
                    )
        tampered = copy.deepcopy(inventory)
        unaudited_row = next(
            row for row in tampered["commands"]
            if row["canonical_path"] == "object-storage-upload"
        )
        unaudited_row["approval_exposure_history"] = history
        with self.assertRaisesRegex(ValueError, "^command_status_inventory_invalid$"):
            command_status.resolve_capability_availability(
                tampered, "object-storage-upload", requested_mode="approve"
            )

    def test_create_draft_scope_uses_same_provenance_for_parsed_modes(self) -> None:
        parser = archive_cli.build_parser()
        inventory = archive_cli._parser_capability_inventory(parser)
        cases = [
            ([], False),
            (["--creation-mode=human_written"], False),
            (["--creation-mode=imported"], False),
            (["--creation-mode=derived"], False),
            (["--creation-mode=ai_assisted"], True),
            (["--creation-mode", "ai_generated"], True),
            (["--created-by=ai:synthetic"], True),
            (["--created-by", "ai_runtime:synthetic"], True),
            (["--created-by=mcp:zettel-kasten-archive-mcp"], True),
            (["--created-by=person:synthetic"], False),
            (["--assisted-by=ai:synthetic"], True),
            (["--assisted-by=ai:one", "--assisted-by=ai:two"], True),
            (["--local-ai-session=session:synthetic"], True),
            (["--local-ai-session="], False),
            (["--creation-mode=ai_assisted", "--creation-mode=human_written"], False),
            (["--creation-mode=human_written", "--creation-mode=ai_assisted"], True),
            (["--created-by=ai:synthetic", "--created-by=person:synthetic"], False),
            (["--created-by=person:synthetic", "--created-by=ai:synthetic"], True),
            (["--creation-mode=human_written", "--assisted-by=ai:synthetic"], True),
        ]
        for extra, expected in cases:
            with self.subTest(arguments=extra):
                argv = ["create-draft", "synthetic-archive", *extra, "--approve"]
                namespace = parser.parse_args(argv)
                self.assertEqual(
                    archive_cli._create_draft_ai_provenance_scope(namespace), expected
                )
                actual = command_status.resolve_namespace_capability_availability(
                    parser, inventory, namespace
                )
                suggested = command_status.resolve_suggested_command_mode(
                    inventory,
                    "archive " + " ".join(argv),
                    trusted_parser=parser,
                )
                self.assertEqual(actual["available"], expected)
                self.assertEqual(suggested["capability_availability"], actual)
                self.assertNotIn("ai:synthetic", json.dumps(actual))
                self.assertNotIn("session:synthetic", json.dumps(suggested))
        unspecified = command_status.resolve_capability_availability(
            inventory, "create-draft", requested_mode="approve"
        )
        self.assertEqual(unspecified["state"], "writer_unavailable")
        self.assertFalse(unspecified["available"])

    def test_create_draft_non_ai_writer_is_blocked_before_handler(self) -> None:
        stdout = io.StringIO()
        with mock.patch.object(
            archive_cli, "command_create_draft",
            side_effect=AssertionError("non-AI writer must not dispatch"),
        ) as handler, redirect_stdout(stdout):
            result = archive_cli.main([
                "create-draft", "PRIVATE-SCOPE-MARKER",
                "--creation-mode=human_written", "--approve", "--format=json",
            ])
        self.assertEqual(result, 1)
        handler.assert_not_called()
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["capability_state"], "writer_unavailable")
        self.assertNotIn("PRIVATE-SCOPE-MARKER", stdout.getvalue())

    def test_create_draft_scope_requires_trusted_boolean_predicate(self) -> None:
        parser = archive_cli.build_parser()
        inventory = archive_cli._parser_capability_inventory(parser)
        namespace = parser.parse_args([
            "create-draft", "synthetic-archive", "--creation-mode=ai_assisted", "--approve"
        ])
        _, leaf = command_status._selected_canonical_parser_path(parser, namespace)
        for predicate in (None, lambda unused: "private-non-boolean"):
            with self.subTest(predicate_callable=callable(predicate)):
                setattr(leaf, command_status._APPROVAL_SCOPE_PREDICATE_ATTRIBUTE, predicate)
                with self.assertRaisesRegex(ValueError, "^command_approval_scope_invalid$"):
                    command_status.resolve_namespace_capability_availability(
                        parser, inventory, namespace
                    )

    def test_create_draft_preview_separates_valid_input_from_write_readiness(self) -> None:
        for state in ("failed", "unavailable"):
            for output_format in ("text", "json"):
                with self.subTest(state=state, format=output_format):
                    preview = {
                        "ok": True, "dry_run": True,
                        "frontmatter_preview": {"id": "zet_synthetic"},
                        "proposed_path": "inbox/zet_synthetic.md",
                        "blockers": [], "warnings": [],
                        "write_preflight": {"state": state},
                        "approval_handoff": {"ready": False},
                        "next_safe_actions": [archive_services.INDEX_REBUILD_NEXT_SAFE_ACTIONS[1]],
                    }
                    stdout = io.StringIO()
                    with mock.patch.object(
                        archive_services, "create_draft_zettel", return_value=preview
                    ), redirect_stdout(stdout):
                        result = archive_cli.main([
                            "create-draft", "synthetic-archive",
                            "--creation-mode=ai_assisted", "--title=Synthetic",
                            "--body=Synthetic", "--dry-run", "--format", output_format,
                        ])
                    self.assertEqual(result, 0)
                    if output_format == "text":
                        self.assertIn("input is valid, but approval is blocked", stdout.getvalue())
                        self.assertNotIn("Draft dry-run passed", stdout.getvalue())
                        self.assertIn("archive index-health", stdout.getvalue())
                    else:
                        payload = json.loads(stdout.getvalue())
                        self.assertEqual(payload["write_preflight"]["state"], state)
                        self.assertFalse(payload["approval_handoff"]["ready"])

    def test_create_draft_index_approval_failure_keeps_safe_reason_before_broker(self) -> None:
        for state, reason in (
            ("failed", archive_services.INDEX_REBUILD_REQUIRED),
            ("unavailable", "archive_index_observation_unavailable"),
        ):
            for output_format in ("text", "json"):
                with self.subTest(state=state, format=output_format):
                    preview = {
                        "ok": False, "dry_run": True,
                        "write_preflight": {"state": state, "reason_code": reason},
                        "next_safe_actions": ["PRIVATE-UNTRUSTED-PREVIEW-MARKER"],
                    }
                    stdout, stderr = io.StringIO(), io.StringIO()
                    with mock.patch.object(
                        archive_cli, "_project_write_runtime_guard", return_value=None
                    ), mock.patch.object(
                        archive_services, "create_draft_zettel", return_value=preview
                    ), mock.patch.object(
                        archive_cli, "_exact_human_approval_context",
                        side_effect=AssertionError("index failure must precede broker context"),
                    ) as context, redirect_stdout(stdout), redirect_stderr(stderr):
                        result = archive_cli.main([
                            "create-draft", "synthetic-archive",
                            "--creation-mode=ai_assisted", "--title=Synthetic",
                            "--body=Synthetic", "--draft-id=zet_synthetic",
                            "--created-at=2026-09-05T00:00:00+00:00",
                            "--draft-approved-by=person:synthetic",
                            "--expected-body-sha256=" + "a" * 64,
                            "--expected-source-fidelity-plan-sha256=" + "b" * 64,
                            "--approve", "--format", output_format,
                        ])
                    self.assertEqual(result, 1)
                    context.assert_not_called()
                    combined = stdout.getvalue() + stderr.getvalue()
                    self.assertNotIn("PRIVATE-UNTRUSTED-PREVIEW-MARKER", combined)
                    self.assertIn("archive index-health", combined)
                    if state == "unavailable":
                        self.assertNotIn("archive index <", combined)
                    if output_format == "json":
                        payload = json.loads(stdout.getvalue())
                        self.assertEqual(payload["reason_codes"], [reason])
                        self.assertEqual(payload["files_written"], [])
                    else:
                        self.assertIn("no approval window was opened", combined)

    def test_reconcile_dry_runs_do_not_offer_unavailable_approval(self) -> None:
        for command, service_name in (
            ("remint-reconcile", "remint_reconcile_plan"),
            ("retire-draft-reconcile", "retire_draft_reconcile_plan"),
        ):
            for drift in ("clean", "format_drift", "content_change"):
                original = {
                    "ok": True, "dry_run": True, "zettel_id": "zet_synthetic",
                    "drift_class": drift, "blockers": [], "warnings": [],
                    "content_change_ack_required": drift == "content_change",
                    "approval_would_write": drift != "clean",
                    "body_changed": drift == "content_change",
                    "current_canonical_text": "PRIVATE-BODY-MARKER",
                    "next_safe_actions": ["Review the evidence.", "Rerun --approve."],
                    "human_review_plan": {
                        "required": drift == "content_change",
                        "commands": {"approve_if_intentional": "archive ignored --approve"},
                        "decision_options": [{
                            "decision": "intentional_change",
                            "next_action": "approve_only_after_named_human_review",
                            "command": "archive ignored --approve",
                        }],
                    },
                }
                saved = copy.deepcopy(original)
                formats = [("json", False), ("text", False)]
                if command == "remint-reconcile":
                    formats.append(("json", True))
                for output_format, diagnostic in formats:
                    with self.subTest(command=command, drift=drift, format=output_format, diagnostic=diagnostic):
                        stdout = io.StringIO()
                        argv = [
                            command, "synthetic-archive", "--zettel-id", "zet_synthetic",
                            "--dry-run", "--format", output_format,
                        ]
                        if diagnostic:
                            argv.append("--diagnostic-only")
                        with mock.patch.object(
                            archive_services, service_name, return_value=original
                        ), redirect_stdout(stdout):
                            result = archive_cli.main(argv)
                        self.assertEqual(result, 0)
                        self.assertEqual(original, saved)
                        self.assertNotIn("--approve", stdout.getvalue())
                        self.assertIn("writer_unavailable", stdout.getvalue())
                        if output_format == "json":
                            payload = json.loads(stdout.getvalue())
                            self.assertEqual(payload["drift_class"], drift)
                            self.assertFalse(payload["approval_would_write"])
                            self.assertFalse(payload["approved_write_implemented"])
                            self.assertFalse(payload["validation_digest_is_approval_authority"])
                        if diagnostic:
                            self.assertNotIn("PRIVATE-BODY-MARKER", stdout.getvalue())

    def test_fixed_closed_and_available_modes_use_one_normalized_truth(self) -> None:
        inventory = self.inventory()

        dry_run = command_status.resolve_capability_availability(
            inventory,
            "remint-reconcile",
            requested_mode="dry_run",
        )
        approve = command_status.resolve_capability_availability(
            inventory,
            "remint-reconcile",
            requested_mode="approve",
        )
        available_writer = command_status.resolve_capability_availability(
            inventory,
            "project-version-update",
            requested_mode="approve",
        )

        self.assertEqual(dry_run["state"], command_status.CAPABILITY_AVAILABLE)
        self.assertTrue(dry_run["available"])
        self.assertEqual(
            approve["state"],
            command_status.CAPABILITY_WRITER_UNAVAILABLE,
        )
        self.assertFalse(approve["available"])
        self.assertEqual(
            approve["reason_code"],
            command_status.WRITER_UNAVAILABLE_REASON_CODE,
        )
        self.assertEqual(
            approve["detail_reason_code"],
            command_status.COMPOUND_APPROVAL_REASON_CODE,
        )
        self.assertEqual(
            available_writer["state"],
            command_status.CAPABILITY_AVAILABLE,
        )
        self.assertFalse(approve["prerequisites_evaluated"])

    def test_conditional_writer_is_resolved_from_exact_arguments(self) -> None:
        parser = archive_cli.build_parser()
        inventory = archive_cli._parser_capability_inventory(parser)
        allowed = parser.parse_args(
            [
                "migrate",
                "synthetic-archive",
                "--target",
                "notion-source-properties",
                "--approve",
            ]
        )
        closed = parser.parse_args(
            [
                "migrate",
                "synthetic-archive",
                "--target",
                "frontmatter-v0.3",
                "--approve",
            ]
        )

        allowed_status = (
            command_status.resolve_namespace_capability_availability(
                parser,
                inventory,
                allowed,
            )
        )
        closed_status = (
            command_status.resolve_namespace_capability_availability(
                parser,
                inventory,
                closed,
            )
        )

        self.assertEqual(
            allowed_status["state"],
            command_status.CAPABILITY_AVAILABLE,
        )
        self.assertEqual(
            closed_status["state"],
            command_status.CAPABILITY_WRITER_UNAVAILABLE,
        )
        self.assertFalse(closed_status["private_values_echoed"])

    def test_value_taking_conditional_scope_matches_suggestion_and_dispatch(
        self,
    ) -> None:
        parser = archive_cli.build_parser()
        inventory = archive_cli._parser_capability_inventory(parser)
        cases = (
            (
                "zet-title-remap-write",
                [
                    "zet-title-remap-write",
                    "synthetic-archive",
                    "--source-mirror",
                    "private-mirror-placeholder",
                    "--approve",
                ],
                (
                    "archive zet-title-remap-write <archive-root> "
                    "--source-mirror <mirror> --approve"
                ),
            ),
            (
                "external-locator-record",
                [
                    "external-locator-record",
                    "synthetic-archive",
                    "--source-mirror",
                    "private-mirror-placeholder",
                    "--approve",
                ],
                (
                    "archive external-locator-record <archive-root> "
                    "--source-mirror <mirror> --approve"
                ),
            ),
            (
                "external-locator-record",
                [
                    "external-locator-record",
                    "synthetic-archive",
                    "--markup-receipt",
                    "private-receipt-placeholder",
                    "--approve",
                ],
                (
                    "archive external-locator-record <archive-root> "
                    "--markup-receipt <receipt> --approve"
                ),
            ),
        )

        for command, argv, suggested in cases:
            with self.subTest(command=command, selector=argv[2]):
                namespace = parser.parse_args(argv)
                dispatch = (
                    command_status.resolve_namespace_capability_availability(
                        parser,
                        inventory,
                        namespace,
                    )
                )
                suggestion = command_status.resolve_suggested_command_mode(
                    inventory,
                    suggested,
                    trusted_parser=parser,
                )["capability_availability"]

                self.assertEqual(
                    dispatch["state"],
                    command_status.CAPABILITY_AVAILABLE,
                )
                self.assertEqual(dispatch["state"], suggestion["state"])
                self.assertFalse(dispatch["private_values_echoed"])
                self.assertNotIn(argv[3], repr(dispatch))

    def test_suggestion_scope_uses_argparse_equals_and_last_value_semantics(
        self,
    ) -> None:
        parser = archive_cli.build_parser()
        inventory = archive_cli._parser_capability_inventory(parser)
        closed_target = "frontmatter-v0.3"
        cases = (
            (
                [
                    "migrate",
                    "synthetic-archive",
                    "--target=notion-source-properties",
                    "--approve",
                ],
                (
                    "archive migrate <archive-root> "
                    "--target=notion-source-properties --approve"
                ),
                command_status.CAPABILITY_AVAILABLE,
            ),
            (
                [
                    "migrate",
                    "synthetic-archive",
                    "--target",
                    closed_target,
                    "--target",
                    "notion-source-properties",
                    "--approve",
                ],
                (
                    "archive migrate <archive-root> "
                    f"--target {closed_target} "
                    "--target notion-source-properties --approve"
                ),
                command_status.CAPABILITY_AVAILABLE,
            ),
            (
                [
                    "migrate",
                    "synthetic-archive",
                    "--target",
                    "notion-source-properties",
                    "--target",
                    closed_target,
                    "--approve",
                ],
                (
                    "archive migrate <archive-root> "
                    "--target notion-source-properties "
                    f"--target {closed_target} --approve"
                ),
                command_status.CAPABILITY_WRITER_UNAVAILABLE,
            ),
        )

        for argv, suggested, expected_state in cases:
            with self.subTest(expected_state=expected_state, argv=argv):
                namespace = parser.parse_args(argv)
                dispatch = (
                    command_status.resolve_namespace_capability_availability(
                        parser,
                        inventory,
                        namespace,
                    )
                )
                suggestion = command_status.resolve_suggested_command_mode(
                    inventory,
                    suggested,
                    trusted_parser=parser,
                )["capability_availability"]

                self.assertEqual(dispatch["state"], expected_state)
                self.assertEqual(suggestion["state"], expected_state)
                self.assertEqual(dispatch["available"], suggestion["available"])
                self.assertNotIn(closed_target, repr(dispatch))
                self.assertNotIn(closed_target, repr(suggestion))

    def test_delegated_coverage_audit_dry_run_is_in_shared_inventory(self) -> None:
        parser = archive_cli.build_parser()
        inventory = archive_cli._parser_capability_inventory(parser)
        row = next(
            item
            for item in inventory["commands"]
            if item["canonical_path"] == "source-reference-coverage-audit"
        )

        self.assertTrue(row["dry_run_exposed"])
        self.assertEqual(row["approval_status"], command_status.APPROVAL_NOT_EXPOSED)
        status = command_status.resolve_suggested_command_mode(
            inventory,
            (
                "archive source-reference-coverage-audit <archive-root> "
                "--dry-run --format json"
            ),
            trusted_parser=parser,
        )
        self.assertEqual(status["resolution_state"], "resolved")
        self.assertEqual(status["requested_mode"], "dry_run")
        self.assertTrue(status["requested_mode_available"])
        self.assertEqual(
            status["capability_availability"]["state"],
            command_status.CAPABILITY_AVAILABLE,
        )
        self.assertFalse(status["private_values_echoed"])

    def test_delegated_parser_rejects_invalid_suggestion_and_dispatch_before_handler(
        self,
    ) -> None:
        private_marker = "PRIVATE-DELEGATED-ARGUMENT-MARKER"
        parser = archive_cli.build_parser()
        inventory = archive_cli._parser_capability_inventory(parser)
        invocation = (
            "archive source-reference-coverage-audit "
            f"{private_marker} --dry-run --bogus --format json"
        )

        suggestion = command_status.resolve_suggested_command_mode(
            inventory,
            invocation,
            trusted_parser=parser,
        )
        namespace = parser.parse_args(
            [
                "source-reference-coverage-audit",
                private_marker,
                "--dry-run",
                "--bogus",
                "--format",
                "json",
            ]
        )
        dispatch = command_status.resolve_namespace_capability_availability(
            parser,
            inventory,
            namespace,
        )

        self.assertEqual(suggestion["resolution_state"], "unresolved")
        self.assertTrue(suggestion["argument_syntax_evaluated"])
        self.assertFalse(suggestion["argument_syntax_valid"])
        self.assertFalse(suggestion["requested_mode_available"])
        self.assertEqual(suggestion["capability_availability"], dispatch)
        self.assertEqual(
            dispatch["reason_code"],
            "capability_argument_syntax_invalid",
        )
        self.assertNotIn(private_marker, repr(suggestion))
        self.assertNotIn(private_marker, repr(dispatch))

        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch(
            "wom_kit.source_reference_coverage_audit."
            "command_source_reference_coverage_audit_argv",
            side_effect=AssertionError("invalid delegated handler must not run"),
        ) as handler, redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = archive_cli.main(
                [
                    "source-reference-coverage-audit",
                    private_marker,
                    "--dry-run",
                    "--bogus",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(exit_code, 1)
        handler.assert_not_called()
        actual = json.loads(stdout.getvalue())
        self.assertEqual(
            actual["reason_codes"],
            ["capability_argument_syntax_invalid"],
        )
        self.assertEqual(actual["capability_availability"], dispatch)
        self.assertNotIn(private_marker, stdout.getvalue() + stderr.getvalue())

    def test_both_raw_delegates_pass_the_shared_gate_before_dispatch(self) -> None:
        cases = (
            (
                (
                    "wom_kit.source_reference_coverage_audit."
                    "command_source_reference_coverage_audit_argv"
                ),
                [
                    "source-reference-coverage-audit",
                    "synthetic-archive",
                    "--dry-run",
                    "--format",
                    "json",
                ],
            ),
            (
                "wom_kit.private_objet_finder.command_find_objet_argv",
                ["find-objet", "--help"],
            ),
        )
        for handler_name, argv in cases:
            with self.subTest(command=argv[0]):
                stdout = io.StringIO()
                stderr = io.StringIO()
                with mock.patch(
                    handler_name,
                    return_value=73,
                ) as handler, redirect_stdout(stdout), redirect_stderr(stderr):
                    exit_code = archive_cli.main(argv)

                self.assertEqual(exit_code, 73)
                handler.assert_called_once()

    def test_find_objet_invalid_remainder_is_blocked_before_private_handler(
        self,
    ) -> None:
        private_marker = "PRIVATE-FINDER-ARCHIVE-MARKER"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch(
            "wom_kit.private_objet_finder.command_find_objet_argv",
            side_effect=AssertionError("invalid private handler must not run"),
        ) as handler, redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = archive_cli.main(
                ["find-objet", private_marker, "--bogus"]
            )

        self.assertEqual(exit_code, 1)
        handler.assert_not_called()
        self.assertNotIn(private_marker, stdout.getvalue() + stderr.getvalue())
        self.assertIn("requested command mode is unavailable", stderr.getvalue())

    def test_doctor_suggestion_carries_the_same_capability_record(self) -> None:
        parser = archive_cli.build_parser()
        inventory = archive_cli._parser_capability_inventory(parser)

        status = command_status.resolve_suggested_command_mode(
            inventory,
            (
                "archive remint-reconcile <archive-root> "
                "--zettel-id <id> --approve"
            ),
            trusted_parser=parser,
        )

        availability = status["capability_availability"]
        self.assertFalse(status["requested_mode_available"])
        self.assertEqual(
            availability["state"],
            command_status.CAPABILITY_WRITER_UNAVAILABLE,
        )
        self.assertEqual(
            availability["reason_code"],
            command_status.WRITER_UNAVAILABLE_REASON_CODE,
        )

    def test_actual_dispatch_refuses_unavailable_writer_before_handler(self) -> None:
        private_marker = "PRIVATE-SYNTHETIC-ARCHIVE-MARKER"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.object(
            archive_cli,
            "command_remint_reconcile",
            side_effect=AssertionError("unavailable handler must not run"),
        ) as handler, redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = archive_cli.main(
                [
                    "remint-reconcile",
                    private_marker,
                    "--zettel-id",
                    "zet_synthetic",
                    "--approve",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(exit_code, 1)
        handler.assert_not_called()
        self.assertEqual(stderr.getvalue(), "")
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["capability_state"], "writer_unavailable")
        self.assertEqual(
            payload["capability_reason_codes"][0],
            "writer_unavailable",
        )
        self.assertEqual(payload["effects_state"], "none")
        self.assertEqual(payload["files_written"], [])
        self.assertNotIn(private_marker, stdout.getvalue())

    def test_actual_dry_run_dispatch_receives_available_capability(self) -> None:
        observed: dict[str, object] = {}

        def handler(args: argparse.Namespace) -> int:
            observed.update(args._wom_capability_availability)
            return 0

        with mock.patch.object(
            archive_cli,
            "command_remint_reconcile",
            side_effect=handler,
        ) as patched:
            exit_code = archive_cli.main(
                [
                    "remint-reconcile",
                    "synthetic-archive",
                    "--zettel-id",
                    "zet_synthetic",
                    "--dry-run",
                ]
            )

        self.assertEqual(exit_code, 0)
        patched.assert_called_once()
        self.assertEqual(observed["state"], command_status.CAPABILITY_AVAILABLE)
        self.assertTrue(observed["available"])

    def test_actual_dispatch_refuses_conflicting_modes_before_handler(self) -> None:
        private_marker = "PRIVATE-CONFLICTING-MODE-MARKER"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.object(
            archive_cli,
            "command_operator_feedback_record",
            side_effect=AssertionError("conflicting modes must not dispatch"),
        ) as handler, redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = archive_cli.main(
                [
                    "operator-feedback-record",
                    private_marker,
                    "--feedback-id",
                    "feedback_synthetic",
                    "--feedback-ref",
                    "feedback:synthetic",
                    "--status",
                    "draft",
                    "--dry-run",
                    "--approve",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(exit_code, 1)
        handler.assert_not_called()
        self.assertEqual(stderr.getvalue(), "")
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["capability_state"], "mode_unavailable")
        self.assertEqual(
            payload["reason_codes"],
            ["capability_mode_conflicting"],
        )
        self.assertEqual(payload["effects_state"], "none")
        self.assertEqual(payload["files_written"], [])
        self.assertNotIn(private_marker, stdout.getvalue())

    def test_approval_dispatch_fails_closed_if_availability_cannot_resolve(
        self,
    ) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.object(
            command_status,
            "resolve_namespace_capability_availability",
            side_effect=ValueError("synthetic resolution failure"),
        ), mock.patch.object(
            archive_cli,
            "command_remint_reconcile",
            side_effect=AssertionError("unresolved approval must not dispatch"),
        ) as handler, redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = archive_cli.main(
                [
                    "remint-reconcile",
                    "synthetic-archive",
                    "--zettel-id",
                    "zet_synthetic",
                    "--approve",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(exit_code, 1)
        handler.assert_not_called()
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["capability_state"], "writer_unavailable")
        self.assertEqual(
            payload["reason_codes"],
            ["capability_availability_unresolved"],
        )
        self.assertEqual(stderr.getvalue(), "")

    def test_capabilities_projection_and_no_commands_remain_honest(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = archive_cli.main(["capabilities", "--machine"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        rows = {
            row["canonical_path"]: row
            for row in payload["data"]["capability_availability"]["rows"]
        }
        self.assertEqual(
            rows["remint-reconcile"]["approve_without_arguments"]["state"],
            command_status.CAPABILITY_WRITER_UNAVAILABLE,
        )
        self.assertEqual(
            rows["project-version-update"]["approve_without_arguments"][
                "state"
            ],
            command_status.CAPABILITY_AVAILABLE,
        )

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = archive_cli.main(
                ["capabilities", "--machine", "--no-commands"]
            )
        self.assertEqual(exit_code, 0)
        hidden = json.loads(stdout.getvalue())
        self.assertEqual(
            hidden["data"]["capability_availability"]["rows"],
            [],
        )

    def test_command_manifest_recurses_to_executable_parser_leaves(self) -> None:
        parser = archive_cli.build_parser()
        commands = archive_cli.parser_command_manifest(parser)
        inventory = archive_cli._parser_capability_inventory(parser)
        by_path = {row["canonical_path"]: row for row in commands}

        self.assertEqual(
            len(commands),
            inventory["counts"]["canonical_executable_command_count"],
        )
        self.assertNotIn("derive-text", by_path)
        self.assertIn("derive-text capture", by_path)
        capture = by_path["derive-text capture"]
        self.assertEqual(capture["name"], "derive-text capture")
        self.assertEqual(capture["required_positionals"], ["archive_root"])
        self.assertIn("--from-manifest", capture["options"])
        self.assertIn("--approve", capture["options"])
        self.assertEqual(capture["nested_subcommands"], [])

    def test_runtime_context_keeps_status_and_filters_bare_unsafe_suggestion(
        self,
    ) -> None:
        parser = archive_cli.build_parser()
        inventory = archive_cli._parser_capability_inventory(parser)
        available_command = (
            "archive remint-reconcile <archive-root> "
            "--zettel-id <id> --dry-run"
        )
        unavailable_command = (
            "archive remint-reconcile <archive-root> "
            "--zettel-id <id> --approve"
        )
        available_status = command_status.resolve_suggested_command_mode(
            inventory,
            available_command,
            trusted_parser=parser,
        )
        unavailable_status = command_status.resolve_suggested_command_mode(
            inventory,
            unavailable_command,
            trusted_parser=parser,
        )
        findings = archive_services.runtime_context_doctor_findings(
            [
                {
                    "severity": "WARN",
                    "code": "available",
                    "message": "available",
                    "suggested_command": available_command,
                    "suggested_command_status": available_status,
                },
                {
                    "severity": "WARN",
                    "code": "unavailable",
                    "message": "unavailable",
                    "suggested_command": unavailable_command,
                    "suggested_command_status": unavailable_status,
                },
                {
                    "severity": "WARN",
                    "code": "legacy_unknown",
                    "message": "legacy unknown",
                    "suggested_command": "archive unknown --dry-run",
                },
            ],
            root=Path("synthetic-archive"),
            redact_local_paths=True,
        )

        self.assertEqual(findings["suggested_commands"], [available_command])
        self.assertTrue(findings["suggested_command_entries_authoritative"])
        entries = {
            row["suggested_command"]: row
            for row in findings["suggested_command_entries"]
        }
        self.assertTrue(entries[available_command]["bare_execution_candidate"])
        self.assertFalse(
            entries[unavailable_command]["bare_execution_candidate"]
        )
        self.assertFalse(
            entries["archive unknown --dry-run"]["bare_execution_candidate"]
        )
        self.assertEqual(
            findings["items"][1]["suggested_command_status"],
            unavailable_status,
        )

    def test_mcp_capabilities_is_the_same_shared_parser_truth(self) -> None:
        definitions = {
            row["name"]: row for row in mcp_server.TOOL_DEFINITIONS
        }
        self.assertIn("archive_capabilities", definitions)
        mcp_result = mcp_server.handle_tools_call(
            {"name": "archive_capabilities", "arguments": {}}
        )["structuredContent"]
        cli_result = archive_cli.capabilities_result()

        self.assertEqual(mcp_result["summary"], cli_result["summary"])
        self.assertEqual(mcp_result["data"], cli_result["data"])
        self.assertFalse(mcp_result["privacy_guards"]["network_checked"])
        self.assertFalse(mcp_result["privacy_guards"]["writes"])


if __name__ == "__main__":
    unittest.main()
