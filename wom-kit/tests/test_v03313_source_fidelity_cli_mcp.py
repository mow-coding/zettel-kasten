from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from wom_kit import archive_cli, archive_services, mcp_server


SOURCE_OBJECT_ID = "sha256:" + "a" * 64
BODY_SHA256 = "b" * 64
PLAN_SHA256 = "c" * 64
DRAFT_ID = "zet_20260820_letter136"
CREATED_AT = "2026-08-20T12:00:00+09:00"


class SourceFidelityCliTests(unittest.TestCase):
    def run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = archive_cli.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_create_draft_help_exposes_closed_source_fidelity_contract(self) -> None:
        code, stdout, stderr = self.run_cli(["create-draft", "--help"])

        self.assertEqual(code, 0, stderr)
        self.assertIn("--source-fidelity", stdout)
        self.assertIn("{faithful_summary,sanitized_derivative,verbatim}", stdout)
        self.assertIn("--fidelity-audience", stdout)
        self.assertIn("--fidelity-source-object-id", stdout)
        self.assertIn("--expected-source-fidelity-plan-sha256", stdout)
        self.assertIn("--approve", stdout)

    def test_create_draft_dry_run_passes_fidelity_inputs_and_preserves_replay(self) -> None:
        replay = {"expected_source_fidelity_plan_sha256": PLAN_SHA256}
        service_result = {
            "ok": True,
            "dry_run": True,
            "approval_replay": replay,
            "source_fidelity": {
                "mode": "faithful_summary",
                "audience": "private_self",
                "plan_sha256": PLAN_SHA256,
            },
        }
        with mock.patch.object(
            archive_services,
            "create_draft_zettel",
            return_value=service_result,
        ) as create_draft:
            code, stdout, stderr = self.run_cli(
                [
                    "create-draft",
                    "C:/private/archive",
                    "--title",
                    "Private title",
                    "--body",
                    "Private body",
                    "--creation-mode",
                    "ai_assisted",
                    "--source-fidelity",
                    "faithful_summary",
                    "--fidelity-audience",
                    "private_self",
                    "--fidelity-source-object-id",
                    SOURCE_OBJECT_ID,
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(code, 0, stderr)
        self.assertEqual(json.loads(stdout)["approval_replay"], replay)
        kwargs = create_draft.call_args.kwargs
        self.assertTrue(kwargs["dry_run"])
        self.assertFalse(kwargs["approved"])
        self.assertEqual(kwargs["source_fidelity_mode"], "faithful_summary")
        self.assertEqual(kwargs["source_fidelity_audience"], "private_self")
        self.assertEqual(kwargs["fidelity_source_object_id"], SOURCE_OBJECT_ID)
        self.assertIsNone(kwargs["expected_source_fidelity_plan_sha256"])

    def test_create_draft_verbatim_can_omit_body(self) -> None:
        with mock.patch.object(
            archive_services,
            "create_draft_zettel",
            return_value={"ok": True, "dry_run": True},
        ) as create_draft:
            code, _stdout, stderr = self.run_cli(
                [
                    "create-draft",
                    "C:/private/archive",
                    "--title",
                    "Private verbatim",
                    "--creation-mode",
                    "ai_generated",
                    "--source-fidelity",
                    "verbatim",
                    "--fidelity-audience",
                    "private_self",
                    "--fidelity-source-object-id",
                    SOURCE_OBJECT_ID,
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(code, 0, stderr)
        self.assertEqual(create_draft.call_args.kwargs["body"], "")

    def test_ai_approve_requires_all_review_evidence_without_service_call(self) -> None:
        private_body = "RAW PRIVATE BODY 010-0000-0000"
        with mock.patch.object(archive_services, "create_draft_zettel") as create_draft:
            code, stdout, stderr = self.run_cli(
                [
                    "create-draft",
                    "C:/private/archive",
                    "--title",
                    "Private title",
                    "--body",
                    private_body,
                    "--creation-mode",
                    "ai_assisted",
                    "--approve",
                    "--draft-id",
                    DRAFT_ID,
                    "--created-at",
                    CREATED_AT,
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(code, 1, stderr)
        create_draft.assert_not_called()
        result = json.loads(stdout)
        self.assertEqual(
            result["reason_codes"],
            ["create_draft_ai_approval_evidence_required"],
        )
        self.assertEqual(
            result["missing_required_options"],
            [
                "--draft-approved-by",
                "--expected-body-sha256",
                "--expected-source-fidelity-plan-sha256",
            ],
        )
        self.assertFalse(result["private_values_echoed"])
        self.assertNotIn(private_body, stdout + stderr)

    def test_ai_approve_reports_all_five_missing_prerequisites_once(self) -> None:
        private_body = "RAW PRIVATE BODY ALL PREREQUISITES"
        with mock.patch.object(archive_services, "create_draft_zettel") as create_draft:
            code, stdout, stderr = self.run_cli(
                [
                    "create-draft",
                    "C:/private/archive",
                    "--title",
                    "Private title",
                    "--body",
                    private_body,
                    "--creation-mode",
                    "ai_assisted",
                    "--approve",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(code, 1, stderr)
        create_draft.assert_not_called()
        result = json.loads(stdout)
        self.assertEqual(
            result["reason_codes"],
            [
                "create_draft_ai_replay_identity_required",
                "create_draft_ai_approval_evidence_required",
            ],
        )
        self.assertEqual(
            result["missing_required_options"],
            [
                "--draft-id",
                "--created-at",
                "--draft-approved-by",
                "--expected-body-sha256",
                "--expected-source-fidelity-plan-sha256",
            ],
        )
        self.assertFalse(result["private_values_echoed"])
        self.assertNotIn(private_body, stdout + stderr)

    def test_ai_create_draft_requires_exactly_one_execution_mode(self) -> None:
        cases = (
            ([], ["compound_exact_human_approval_binding_required"]),
            (
                ["--dry-run", "--approve"],
                ["create_draft_ai_execution_mode_invalid"],
            ),
        )
        for switches, expected_reason_codes in cases:
            with self.subTest(switches=switches):
                with mock.patch.object(
                    archive_services,
                    "create_draft_zettel",
                ) as create_draft:
                    code, stdout, stderr = self.run_cli(
                        [
                            "create-draft",
                            "C:/private/archive",
                            "--title",
                            "Private title",
                            "--body",
                            "Private body",
                            "--creation-mode",
                            "ai_assisted",
                            *switches,
                            "--format",
                            "json",
                        ]
                    )

                self.assertEqual(code, 1, stderr)
                create_draft.assert_not_called()
                self.assertEqual(
                    json.loads(stdout)["reason_codes"],
                    expected_reason_codes,
                )

    def test_ai_approve_passes_exact_review_evidence(self) -> None:
        preview = {
            "ok": True,
            "dry_run": True,
            "proposed_path": f"inbox/{DRAFT_ID}.md",
            "source_fidelity_plan_sha256": PLAN_SHA256,
            "body_sha256": BODY_SHA256,
            "warnings": [],
        }

        def execute(_root, _context, writer):
            return writer(mock.sentinel.approval_claim)

        with (
            mock.patch.object(
                archive_services,
                "create_draft_zettel",
                side_effect=[preview, {"ok": True, "dry_run": False}],
            ) as create_draft,
            mock.patch.object(
                archive_cli,
                "_exact_human_approval_context",
                return_value=mock.sentinel.approval_context,
            ) as approval_context,
            mock.patch.object(
                archive_cli,
                "_execute_exact_human_approved_write",
                side_effect=execute,
            ),
        ):
            code, _stdout, stderr = self.run_cli(
                [
                    "create-draft",
                    "C:/private/archive",
                    "--title",
                    "Reviewed title",
                    "--body",
                    "Reviewed body",
                    "--creation-mode",
                    "ai_generated",
                    "--approve",
                    "--draft-id",
                    DRAFT_ID,
                    "--created-at",
                    CREATED_AT,
                    "--draft-approved-by",
                    "person:reviewer",
                    "--expected-body-sha256",
                    BODY_SHA256,
                    "--expected-source-fidelity-plan-sha256",
                    PLAN_SHA256,
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(code, 0, stderr)
        target_preview = approval_context.call_args.kwargs["target_preview"]
        self.assertEqual(target_preview.kind, "draft")
        self.assertEqual(target_preview.primary, f"{DRAFT_ID}.md")
        self.assertEqual(target_preview.secondary, "Reviewed title")
        self.assertEqual(create_draft.call_count, 2)
        kwargs = create_draft.call_args_list[-1].kwargs
        self.assertTrue(kwargs["approved"])
        self.assertFalse(kwargs["dry_run"])
        self.assertIs(
            kwargs["exact_human_approval_claim"],
            mock.sentinel.approval_claim,
        )
        self.assertEqual(kwargs["draft_id"], DRAFT_ID)
        self.assertEqual(kwargs["created_at"], CREATED_AT)
        self.assertEqual(kwargs["draft_approved_by"], "person:reviewer")
        self.assertEqual(kwargs["expected_body_sha256"], BODY_SHA256)
        self.assertEqual(
            kwargs["expected_source_fidelity_plan_sha256"],
            PLAN_SHA256,
        )

    def test_human_legacy_create_draft_is_fixed_closed_without_service_call(self) -> None:
        with mock.patch.object(
            archive_services,
            "create_draft_zettel",
            return_value={"ok": True, "dry_run": False},
        ) as create_draft:
            code, stdout, stderr = self.run_cli(
                [
                    "create-draft",
                    "C:/private/archive",
                    "--title",
                    "Human title",
                    "--body",
                    "Human body",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(code, 1, stderr)
        create_draft.assert_not_called()
        result = json.loads(stdout)
        self.assertEqual(
            result["reason_codes"],
            ["compound_exact_human_approval_binding_required"],
        )
        self.assertFalse(result["private_values_echoed"])

    def test_create_draft_parser_error_never_echoes_private_arguments(self) -> None:
        private_archive = "C:/SECRET_ARCHIVE_PATH"
        private_title = "SECRET PRIVATE TITLE"
        private_body = "SECRET PRIVATE BODY 010-1234-5678"
        code, stdout, stderr = self.run_cli(
            [
                "create-draft",
                private_archive,
                "--title",
                private_title,
                "--body",
                private_body,
                "--source-fidelity",
                "not-a-mode",
                "--format",
                "json",
            ]
        )

        self.assertEqual(code, 2)
        result = json.loads(stdout)
        self.assertEqual(result["reason_codes"], ["cli_arguments_invalid"])
        self.assertFalse(result["private_values_echoed"])
        combined = stdout + stderr
        for private_value in (private_archive, private_title, private_body, "not-a-mode"):
            self.assertNotIn(private_value, combined)

    def test_mint_approve_passes_expected_fidelity_plan(self) -> None:
        binding = mock.Mock(
            plan_sha256="sha256:" + "d" * 64,
            target_binding_sha256="sha256:" + "e" * 64,
        )
        binding.context.return_value = mock.sentinel.approval_context

        def execute(_root, _context, writer):
            return writer(mock.sentinel.approval_claim)

        with (
            mock.patch.object(
                archive_services,
                "mint_zettel_dry_run",
                return_value={"ok": True, "dry_run": True},
            ),
            mock.patch.object(
                archive_cli.operation_approval_binding,
                "mint_zet_approval_binding",
                return_value=binding,
            ),
            mock.patch.object(
                archive_services,
                "read_archive_id",
                return_value="archive:personal:test",
            ),
            mock.patch.object(
                archive_cli,
                "_execute_exact_human_approved_write",
                side_effect=execute,
            ),
            mock.patch.object(
                archive_services,
                "mint_zettel",
                return_value={"ok": True, "warnings": []},
            ) as mint,
        ):
            code, _stdout, stderr = self.run_cli(
                [
                    "mint-zet",
                    "C:/private/archive",
                    "--path",
                    "inbox/private.md",
                    "--approve",
                    "--reviewed-by",
                    "person:reviewer",
                    "--expected-source-fidelity-plan-sha256",
                    PLAN_SHA256,
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(code, 0, stderr)
        self.assertEqual(
            mint.call_args.kwargs["expected_source_fidelity_plan_sha256"],
            PLAN_SHA256,
        )
        self.assertIs(
            mint.call_args.kwargs["exact_human_approval_claim"],
            mock.sentinel.approval_claim,
        )

    def test_mint_dry_run_preserves_current_fidelity_plan_in_json(self) -> None:
        service_result = {
            "ok": True,
            "dry_run": True,
            "current_source_fidelity_plan_sha256": PLAN_SHA256,
            "source_fidelity": {"mode": "verbatim", "private_values_echoed": False},
        }
        with mock.patch.object(
            archive_services,
            "mint_zettel_dry_run",
            return_value=service_result,
        ):
            code, stdout, stderr = self.run_cli(
                [
                    "mint-zet",
                    "C:/private/archive",
                    "--path",
                    "inbox/private.md",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(code, 0, stderr)
        self.assertEqual(
            json.loads(stdout)["current_source_fidelity_plan_sha256"],
            PLAN_SHA256,
        )


class SourceFidelityMcpTests(unittest.TestCase):
    def create_tool_schema(self) -> dict[str, object]:
        return next(
            item["inputSchema"]
            for item in mcp_server.TOOL_DEFINITIONS
            if item["name"] == "create_draft_zettel"
        )

    def test_create_tool_schema_is_ai_only_dry_run_by_default(self) -> None:
        schema = self.create_tool_schema()
        properties = schema["properties"]

        self.assertEqual(properties["dry_run"]["default"], True)
        self.assertEqual(properties["approved"]["default"], False)
        self.assertEqual(properties["creation_mode"]["default"], "ai_assisted")
        self.assertEqual(
            properties["creation_mode"]["enum"],
            ["ai_assisted", "ai_generated"],
        )
        self.assertEqual(
            properties["assisted_by"]["default"],
            ["ai_runtime:mcp"],
        )
        self.assertEqual(
            properties["source_fidelity_mode"]["enum"],
            sorted(archive_services.SOURCE_FIDELITY_MODES),
        )
        self.assertEqual(
            properties["source_fidelity_audience"]["enum"],
            sorted(archive_services.ZET_QUALITY_AUDIENCES),
        )
        self.assertEqual(
            properties["expected_source_fidelity_plan_sha256"]["pattern"],
            "^[0-9a-f]{64}$",
        )
        self.assertEqual(
            properties["fidelity_session_evidence_id"]["pattern"],
            "^source-fidelity-session-evidence:[0-9a-f]{64}$",
        )
        self.assertNotIn("body", schema["required"])
        self.assertTrue(
            {
                "archive_root",
                "title",
                "abstract",
                "facets",
                "source_fidelity_mode",
                "source_fidelity_audience",
            }.issubset(set(schema["required"]))
        )
        self.assertNotIn("fidelity_source_object_id", schema["required"])
        self.assertEqual(
            schema["oneOf"],
            [
                {
                    "required": ["fidelity_source_object_id"],
                    "not": {"required": ["fidelity_session_evidence_id"]},
                },
                {
                    "required": ["fidelity_session_evidence_id"],
                    "not": {"required": ["fidelity_source_object_id"]},
                },
            ],
        )

    def test_create_tool_defaults_to_ai_assisted_dry_run(self) -> None:
        service_result = {
            "ok": True,
            "dry_run": True,
            "approval_replay": {
                "expected_source_fidelity_plan_sha256": PLAN_SHA256,
            },
        }
        with mock.patch.object(
            mcp_server,
            "call_service",
            return_value=service_result,
        ) as call_service:
            result = mcp_server.tool_create_draft_zettel(
                {
                    "archive_root": "C:/private/archive",
                    "title": "Private title",
                    "body": "Private body",
                    "fidelity_source_object_id": SOURCE_OBJECT_ID,
                }
            )

        kwargs = call_service.call_args.kwargs
        self.assertEqual(kwargs["creation_mode"], "ai_assisted")
        self.assertEqual(kwargs["assisted_by"], ["ai_runtime:mcp"])
        self.assertTrue(kwargs["dry_run"])
        self.assertFalse(kwargs["approved"])
        self.assertEqual(result["structuredContent"], service_result)
        summary = result["content"][0]["text"]
        self.assertNotIn("Private title", summary)
        self.assertNotIn("Private body", summary)

    def test_create_tool_rejects_human_written_spoof_before_service(self) -> None:
        with mock.patch.object(mcp_server, "call_service") as call_service:
            with self.assertRaises(mcp_server.ToolError):
                mcp_server.tool_create_draft_zettel(
                    {
                        "archive_root": "C:/private/archive",
                        "title": "Private title",
                        "body": "Private body",
                        "creation_mode": "human_written",
                    }
                )
        call_service.assert_not_called()

    def test_create_tool_rejects_caller_assisted_identity_spoof(self) -> None:
        with mock.patch.object(mcp_server, "call_service") as call_service:
            with self.assertRaises(mcp_server.ToolError):
                mcp_server.tool_create_draft_zettel(
                    {
                        "archive_root": "C:/private/archive",
                        "title": "Private title",
                        "body": "Private body",
                        "assisted_by": ["ai_runtime:spoofed"],
                    }
                )
        call_service.assert_not_called()

    def test_create_tool_rejects_live_write_without_approval(self) -> None:
        with mock.patch.object(mcp_server, "call_service") as call_service:
            with self.assertRaises(mcp_server.ToolError):
                mcp_server.tool_create_draft_zettel(
                    {
                        "archive_root": "C:/private/archive",
                        "title": "Private title",
                        "body": "Private body",
                        "dry_run": False,
                    }
                )
        call_service.assert_not_called()

    def test_create_tool_rejects_dry_run_and_approval_together(self) -> None:
        with mock.patch.object(mcp_server, "call_service") as call_service:
            with self.assertRaises(mcp_server.ToolError):
                mcp_server.tool_create_draft_zettel(
                    {
                        "archive_root": "C:/private/archive",
                        "title": "Private title",
                        "body": "Private body",
                        "dry_run": True,
                        "approved": True,
                    }
                )
        call_service.assert_not_called()

    def test_create_tool_approve_requires_local_ui_without_service_call(self) -> None:
        with mock.patch.object(
            mcp_server,
            "call_service",
            return_value={"ok": True, "dry_run": False},
        ) as call_service:
            result = mcp_server.tool_create_draft_zettel(
                {
                    "archive_root": "C:/private/archive",
                    "title": "Private title",
                    "body": "Private body",
                    "creation_mode": "ai_generated",
                    "dry_run": False,
                    "approved": True,
                    "draft_id": DRAFT_ID,
                    "created_at": CREATED_AT,
                    "draft_approved_by": "person:reviewer",
                    "expected_body_sha256": BODY_SHA256,
                    "source_fidelity_mode": "sanitized_derivative",
                    "source_fidelity_audience": "client_report",
                    "fidelity_source_object_id": SOURCE_OBJECT_ID,
                    "expected_source_fidelity_plan_sha256": PLAN_SHA256,
                }
            )

        call_service.assert_not_called()
        payload = result["structuredContent"]
        self.assertFalse(payload["ok"])
        self.assertEqual(
            payload["reason_codes"],
            ["exact_human_approval_cli_required"],
        )
        self.assertFalse(payload["private_values_echoed"])
        summary = result["content"][0]["text"]
        for private_value in (
            "Private title",
            "Private body",
            SOURCE_OBJECT_ID,
            "C:/private/archive",
        ):
            self.assertNotIn(private_value, summary)

    def test_create_tool_verbatim_can_omit_body(self) -> None:
        with mock.patch.object(
            mcp_server,
            "call_service",
            return_value={"ok": True, "dry_run": True},
        ) as call_service:
            mcp_server.tool_create_draft_zettel(
                {
                    "archive_root": "C:/private/archive",
                    "title": "Private title",
                    "source_fidelity_mode": "verbatim",
                    "source_fidelity_audience": "private_self",
                    "fidelity_source_object_id": SOURCE_OBJECT_ID,
                }
            )

        self.assertEqual(call_service.call_args.kwargs["body"], "")

    def test_tool_error_response_is_content_free(self) -> None:
        private_values = (
            "C:/SECRET_ARCHIVE_PATH",
            "SECRET TITLE",
            "SECRET BODY 010-1234-5678",
            SOURCE_OBJECT_ID,
        )
        response = mcp_server.JsonRpcMcpServer().handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "create_draft_zettel",
                    "arguments": {
                        "archive_root": private_values[0],
                        "title": private_values[1],
                        "body": private_values[2],
                        "creation_mode": "human_written",
                        "fidelity_source_object_id": private_values[3],
                    },
                },
            }
        )

        serialized = json.dumps(response, ensure_ascii=False)
        self.assertTrue(response["result"]["isError"])
        for private_value in private_values:
            self.assertNotIn(private_value, serialized)

    def test_mint_check_passes_fidelity_evidence_without_source_text(self) -> None:
        service_result = {
            "ok": True,
            "current_source_fidelity_plan_sha256": PLAN_SHA256,
            "source_fidelity": {
                "mode": "verbatim",
                "source_text_stored": False,
                "source_text_echoed": False,
            },
        }
        with mock.patch.object(
            mcp_server,
            "call_service",
            return_value=service_result,
        ):
            result = mcp_server.tool_mint_zettel_check(
                {
                    "archive_root": "C:/private/archive",
                    "path": "inbox/private.md",
                }
            )

        self.assertEqual(result["structuredContent"], service_result)
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("source_text\": \"", serialized)


if __name__ == "__main__":
    unittest.main()
