from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from wom_kit import archive_cli, archive_services, completion_workflows, mcp_server


COMPOUND_APPROVAL_BLOCKER = (
    "compound_exact_human_approval_binding_required"
)
PLAN_SHA256 = "a" * 64
BODY_SHA256 = "b" * 64
SOURCE_OBJECT_ID = "sha256:" + "c" * 64
CANDIDATE_ID = "candidate:" + "d" * 64


def _archive_snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class Letter137McpApprovalBoundaryTests(unittest.TestCase):
    def test_mcp_approved_create_requires_local_ui_without_service_call(
        self,
    ) -> None:
        definition = next(
            item
            for item in mcp_server.TOOL_DEFINITIONS
            if item.get("name") == "create_draft_zettel"
        )
        approved_schema = definition["inputSchema"]["properties"]["approved"]
        self.assertIs(approved_schema["const"], False)
        self.assertIn(
            "local Windows exact-human approval dialog",
            definition["description"],
        )

        with mock.patch.object(mcp_server, "call_service") as call_service:
            result = mcp_server.tool_create_draft_zettel(
                {
                    "archive_root": "C:/private/archive",
                    "title": "PRIVATE TITLE MUST NOT LEAK",
                    "body": "PRIVATE BODY MUST NOT LEAK",
                    "creation_mode": "ai_generated",
                    "dry_run": False,
                    "approved": True,
                }
            )

        call_service.assert_not_called()
        payload = result["structuredContent"]
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["state"], "blocked")
        self.assertEqual(
            payload["reason_codes"],
            ["exact_human_approval_cli_required"],
        )
        self.assertIs(payload["private_values_echoed"], False)
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("PRIVATE TITLE MUST NOT LEAK", serialized)
        self.assertNotIn("PRIVATE BODY MUST NOT LEAK", serialized)


class Letter137CompoundApprovalCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = archive_cli.build_parser()

    def _run(self, values: list[str]) -> tuple[int, str, str]:
        args = self.parser.parse_args(values)
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = args.func(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def _assert_compound_approve_is_blocked_before_service(
        self,
        values: list[str],
        service_owner: object,
        service_name: str,
    ) -> None:
        with mock.patch.object(
            service_owner,
            service_name,
            return_value={"ok": True, "files_written": ["unexpected"]},
        ) as service:
            code, stdout, stderr = self._run(values)

        self.assertEqual(code, 1, stderr)
        service.assert_not_called()
        payload = json.loads(stdout)
        self.assertEqual(payload["state"], "blocked")
        self.assertEqual(
            payload["reason_codes"],
            [COMPOUND_APPROVAL_BLOCKER],
        )
        self.assertIs(payload["private_values_echoed"], False)

    def test_mint_batch_approve_is_blocked_before_service(self) -> None:
        self._assert_compound_approve_is_blocked_before_service(
            [
                "mint-zet-batch",
                "C:/private/archive",
                "--plan",
                "workbench/private-mint-plan.json",
                "--approve",
                "--reviewed-by",
                "person:reviewer",
                "--format",
                "json",
            ],
            archive_cli.archive_services,
            "mint_zet_batch",
        )

    def test_retire_batch_approve_is_blocked_before_service(self) -> None:
        self._assert_compound_approve_is_blocked_before_service(
            [
                "retire-draft-batch",
                "C:/private/archive",
                "--plan",
                "workbench/private-retire-plan.json",
                "--approve",
                "--reviewed-by",
                "person:reviewer",
                "--format",
                "json",
            ],
            archive_cli.archive_services,
            "retire_draft_batch",
        )

    def test_zettel_edge_batch_approve_is_blocked_before_service(self) -> None:
        self._assert_compound_approve_is_blocked_before_service(
            [
                "zettel-edge-batch",
                "C:/private/archive",
                "--plan",
                "workbench/private-edge-plan.json",
                "--approve",
                "--reviewed-by",
                "person:reviewer",
                "--format",
                "json",
            ],
            archive_cli.archive_services,
            "zettel_edge_batch_write",
        )

    def test_notion_objet_link_convert_approve_is_blocked_before_service(
        self,
    ) -> None:
        self._assert_compound_approve_is_blocked_before_service(
            [
                "notion-objet-link-convert",
                "C:/private/archive",
                "--path",
                "zettels/private.md",
                "--locator-fingerprint",
                "sha256:" + "e" * 64,
                "--object-id",
                "sha256:" + "f" * 64,
                "--target-mode",
                "embed_edge",
                "--expected-occurrence-count",
                "1",
                "--approve",
                "--reviewed-by",
                "person:reviewer",
                "--format",
                "json",
            ],
            archive_cli.archive_services,
            "notion_objet_link_convert",
        )

    def test_relation_candidate_accept_is_blocked_before_service(self) -> None:
        self._assert_compound_approve_is_blocked_before_service(
            [
                "relation-candidate-decide",
                "C:/private/archive",
                "--from-zettel",
                "zet_source",
                "--candidate-id",
                CANDIDATE_ID,
                "--decision",
                "accept",
                "--edge-type",
                "related",
                "--visibility",
                "private",
                "--reason",
                "reviewed relation",
                "--confidence",
                "high",
                "--expected-plan-sha256",
                PLAN_SHA256,
                "--approve",
                "--reviewed-by",
                "person:reviewer",
                "--format",
                "json",
            ],
            archive_cli.completion_workflows,
            "relation_candidate_decide",
        )

    def test_non_ai_create_approve_is_rejected_before_service(self) -> None:
        with mock.patch.object(
            archive_cli.archive_services,
            "create_draft_zettel",
            return_value={"ok": True, "dry_run": False},
        ) as service:
            code, stdout, stderr = self._run(
                [
                    "create-draft",
                    "C:/private/archive",
                    "--title",
                    "PRIVATE TITLE MUST NOT LEAK",
                    "--body",
                    "PRIVATE BODY MUST NOT LEAK",
                    "--creation-mode",
                    "human_written",
                    "--approve",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(code, 1, stderr)
        service.assert_not_called()
        payload = json.loads(stdout)
        self.assertEqual(payload["reason_codes"], [COMPOUND_APPROVAL_BLOCKER])
        self.assertEqual(payload["files_written"], [])
        self.assertIs(payload["private_values_echoed"], False)
        serialized = stdout + stderr
        self.assertNotIn("PRIVATE TITLE MUST NOT LEAK", serialized)
        self.assertNotIn("PRIVATE BODY MUST NOT LEAK", serialized)

    def test_cli_uses_service_ai_classification_for_approval_routing(
        self,
    ) -> None:
        vectors = (
            ("created_by", ["--created-by", "ai_runtime:test"]),
            ("assisted_by", ["--assisted-by", "ai_runtime:test"]),
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            root.mkdir()
            (root / "archive.yml").write_text(
                "archive_id: archive:personal:classification-test\n",
                encoding="utf-8",
            )
            for label, provenance_args in vectors:
                with self.subTest(label=label):
                    preview = {
                        "ok": True,
                        "dry_run": True,
                        "source_fidelity_plan_sha256": PLAN_SHA256,
                        "body_sha256": BODY_SHA256,
                        "warnings": [],
                    }
                    approved = {
                        "ok": True,
                        "dry_run": False,
                        "zettel_id": "zet_20260820_classification_test",
                        "path": "inbox/zet_20260820_classification_test.md",
                        "warnings": [],
                    }
                    with (
                        mock.patch.object(
                            archive_cli.archive_services,
                            "create_draft_zettel",
                            return_value=preview,
                        ) as service,
                        mock.patch.object(
                            archive_cli,
                            "_execute_exact_human_approved_write",
                            return_value=approved,
                        ) as approval_workflow,
                    ):
                        code, _stdout, stderr = self._run(
                            [
                                "create-draft",
                                str(root),
                                "--title",
                                "Private title",
                                "--body",
                                "Private body",
                                "--abstract",
                                "Reviewed abstract",
                                "--facet",
                                "topic=test",
                                *provenance_args,
                                "--draft-id",
                                "zet_20260820_classification_test",
                                "--created-at",
                                "2026-08-20T09:00:00+09:00",
                                "--expected-body-sha256",
                                BODY_SHA256,
                                "--draft-approved-by",
                                "person:reviewer",
                                "--source-fidelity",
                                "faithful_summary",
                                "--fidelity-audience",
                                "private_self",
                                "--fidelity-source-object-id",
                                SOURCE_OBJECT_ID,
                                "--expected-source-fidelity-plan-sha256",
                                PLAN_SHA256,
                                "--approve",
                                "--format",
                                "json",
                            ]
                        )

                    self.assertEqual(code, 0, stderr)
                    approval_workflow.assert_called_once()
                    service.assert_called_once()
                    self.assertIs(service.call_args.kwargs["dry_run"], True)


class Letter137CompoundApprovalServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "archive"
        self.root.mkdir()
        (self.root / "archive.yml").write_text(
            "archive_id: archive:personal:compound-gate-test\n",
            encoding="utf-8",
        )

    def _assert_blocked_without_changes(self, result: dict, before: dict) -> None:
        self.assertFalse(result["ok"], result)
        self.assertIn(COMPOUND_APPROVAL_BLOCKER, result["blockers"])
        self.assertEqual(result.get("files_written"), [])
        self.assertEqual(_archive_snapshot(self.root), before)

    def test_mint_batch_service_has_explicit_compound_gate(self) -> None:
        before = _archive_snapshot(self.root)
        with mock.patch.object(archive_services, "mint_zettel") as writer:
            result = archive_services.mint_zet_batch(
                self.root,
                plan_path="workbench/private-mint-plan.json",
                approve=True,
                reviewed_by="person:reviewer",
            )
        writer.assert_not_called()
        self._assert_blocked_without_changes(result, before)

    def test_retire_batch_service_has_explicit_compound_gate(self) -> None:
        before = _archive_snapshot(self.root)
        with mock.patch.object(
            archive_services,
            "write_retired_draft_from_plan",
        ) as writer:
            result = archive_services.retire_draft_batch(
                self.root,
                plan_path="workbench/private-retire-plan.json",
                approve=True,
                reviewed_by="person:reviewer",
            )
        writer.assert_not_called()
        self._assert_blocked_without_changes(result, before)

    def test_zettel_edge_batch_service_has_explicit_compound_gate(self) -> None:
        before = _archive_snapshot(self.root)
        with mock.patch.object(archive_services, "zettel_edge_write") as writer:
            result = archive_services.zettel_edge_batch_write(
                self.root,
                plan_path="workbench/private-edge-plan.json",
                approve=True,
                reviewed_by="person:reviewer",
            )
        writer.assert_not_called()
        self._assert_blocked_without_changes(result, before)

    def test_notion_convert_service_has_explicit_compound_gate(self) -> None:
        before = _archive_snapshot(self.root)
        blocked_plan = {
            "ok": False,
            "zettel": {"path": None, "redacted": False},
            "blockers": ["synthetic_review_plan_unavailable"],
            "warnings": [],
        }
        with (
            mock.patch.object(
                archive_services,
                "notion_objet_link_rewrite_plan",
                return_value=blocked_plan,
            ),
            mock.patch.object(archive_services, "zettel_edge_write") as writer,
        ):
            result = archive_services.notion_objet_link_convert(
                self.root,
                relative_path="zettels/private.md",
                locator_fingerprint="sha256:" + "e" * 64,
                object_id="sha256:" + "f" * 64,
                target_mode="embed_edge",
                expected_occurrence_count=1,
                approve=True,
                reviewed_by="person:reviewer",
            )
        writer.assert_not_called()
        self._assert_blocked_without_changes(result, before)

    def test_relation_accept_service_has_explicit_compound_gate(self) -> None:
        before = _archive_snapshot(self.root)
        blocked_plan = {
            "ok": False,
            "state": "blocked",
            "blockers": ["synthetic_review_plan_unavailable"],
        }
        private = {
            "root": self.root,
            "candidates": {},
            "plan_sha256": PLAN_SHA256,
        }
        with (
            mock.patch.object(
                completion_workflows,
                "_relation_candidate_plan_core",
                return_value=(blocked_plan, private),
            ),
            mock.patch.object(archive_services, "zettel_edge_write") as writer,
        ):
            result = completion_workflows.relation_candidate_decide(
                self.root,
                from_zettel="zet_source",
                candidate_id=CANDIDATE_ID,
                decision="accept",
                edge_type="related",
                visibility="private",
                reason="reviewed relation",
                confidence="high",
                expected_plan_sha256=PLAN_SHA256,
                reviewed_by="person:reviewer",
            )
        writer.assert_not_called()
        self._assert_blocked_without_changes(result, before)

    def test_non_ai_service_approve_is_rejected_without_changes(self) -> None:
        before = _archive_snapshot(self.root)
        with mock.patch.object(
            archive_services,
            "require_yaml",
            side_effect=AssertionError("fixed-close must precede YAML access"),
        ) as yaml_reader, mock.patch.object(
            archive_services,
            "require_existing_archive_root",
            side_effect=AssertionError("fixed-close must precede archive reads"),
        ) as root_reader:
            result = archive_services.create_draft_zettel(
                self.root,
                title="Non-AI draft",
                body="Human-written body.",
                creation_mode="human_written",
                approved=True,
                draft_id="zet_20260820_non_ai_approve",
                created_at="2026-08-20T09:00:00+09:00",
            )
        yaml_reader.assert_not_called()
        root_reader.assert_not_called()
        self._assert_blocked_without_changes(result, before)


if __name__ == "__main__":
    unittest.main()
