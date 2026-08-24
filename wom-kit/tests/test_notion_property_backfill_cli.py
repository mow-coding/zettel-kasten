from __future__ import annotations

import io
import hashlib
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import yaml

from wom_kit import archive_cli


def _json_bytes(document) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


class NotionPropertyBackfillCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        temporary = Path(self.temporary.name)
        self.root = temporary / "archive"
        self.root.mkdir()
        (self.root / "archive.yml").write_text(
            "archive_id: archive:test:notion-cli\n",
            encoding="utf-8",
        )
        (self.root / ".gitignore").write_text(
            "profiles/local/\n",
            encoding="utf-8",
            newline="\n",
        )
        (self.root / "zettels").mkdir()
        self.page_id = "synthetic-private-page-id"
        self.mirror = temporary / "PRIVATE-MIRROR-PATH"
        self.mirror.mkdir()
        (self.mirror / f"{self.page_id}.json").write_bytes(
            _json_bytes(
                {
                    "page_id": self.page_id,
                    "object_record": {
                        "object": "page",
                        "id": self.page_id,
                        "properties": {
                            "Email": {
                                "id": "email-id",
                                "type": "email",
                                "email": "private-cli@example.test",
                            }
                        },
                    },
                    "blocks": [],
                }
            )
        )
        target = {
            "id": "zet:synthetic-cli",
            "title": "Synthetic CLI",
            "archive_id": "archive:test:notion-cli",
            "status": "canonical",
            "facets": {"source_page_id": self.page_id},
        }
        (self.root / "zettels" / "synthetic.md").write_text(
            "---\n"
            + yaml.safe_dump(target, sort_keys=False, allow_unicode=True)
            + "---\nSynthetic body.\n",
            encoding="utf-8",
            newline="\n",
        )
        self.acceptance = temporary / "PRIVATE-ACCEPTANCE-PATH.json"
        acceptance_candidate = (
            archive_cli.notion_property_backfill.plan_notion_property_backfill(
                self.root,
                self.mirror,
            )["acceptance_candidate"]
        )
        self.acceptance.write_bytes(
            _json_bytes(acceptance_candidate) + b"\n"
        )
        self.acceptance_output = (
            "profiles/local/notion-property-backfill/"
            "synthetic-acceptance.json"
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_cli(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = archive_cli.main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def base_arguments(self) -> list[str]:
        return [
            "migrate",
            str(self.root),
            "--target",
            "notion-source-properties",
            "--source-mirror",
            str(self.mirror),
            "--acceptance-file",
            str(self.acceptance),
            "--format",
            "json",
        ]

    def assert_private_canaries_absent(self, *outputs: str) -> None:
        serialized = "\n".join(outputs)
        for canary in (
            str(self.root),
            str(self.mirror),
            str(self.acceptance),
            "PRIVATE-MIRROR-PATH",
            "PRIVATE-ACCEPTANCE-PATH",
            "synthetic-acceptance.json",
            self.page_id,
            "private-cli@example.test",
        ):
            self.assertNotIn(canary, serialized)

    def test_migrate_help_exposes_only_target_scoped_backfill_options(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            code = archive_cli.main(["migrate", "--help"])
        self.assertEqual(code, 0)
        text = output.getvalue()
        self.assertIn("notion-source-properties", text)
        self.assertIn("--source-mirror", text)
        self.assertIn("--acceptance-file", text)
        self.assertIn("--acceptance-bootstrap", text)
        self.assertIn("--acceptance-output", text)
        self.assertIn("--resume", text)
        self.assertIn("--approval-id", text)
        self.assertIn("--execution-sha256", text)
        self.assertIn(
            "Every other migration target remains fixed closed",
            " ".join(text.split()),
        )

    def test_parser_error_does_not_echo_private_migration_paths(self) -> None:
        private_unknown_value = "C:\\PRIVATE\\client-secret-acceptance.json"
        code, stdout, stderr = self.run_cli(
            [
                "migrate",
                str(self.root),
                "--target",
                "notion-source-properties",
                "--source-mirror",
                str(self.mirror),
                "--acceptance-fiel",
                private_unknown_value,
                "--dry-run",
            ]
        )

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("private argument values were not echoed", stderr)
        self.assertNotIn(private_unknown_value, stderr)
        self.assert_private_canaries_absent(stdout, stderr)

    def test_bootstrap_stages_exact_private_candidate_create_only(self) -> None:
        arguments = [
            "migrate",
            str(self.root),
            "--target",
            "notion-source-properties",
            "--source-mirror",
            str(self.mirror),
            "--acceptance-bootstrap",
            "--acceptance-output",
            self.acceptance_output,
            "--dry-run",
            "--format",
            "json",
        ]
        code, stdout, stderr = self.run_cli(arguments)

        self.assertEqual(code, 0, stderr)
        result = json.loads(stdout)
        output = self.root.joinpath(*self.acceptance_output.split("/"))
        raw = output.read_bytes()
        self.assertTrue(result["private_output_created"])
        self.assertTrue(result["create_only"])
        self.assertTrue(result["recovery_evidence_staging_write"])
        self.assertTrue(result["namespace_durability_confirmed"])
        self.assertTrue(result["writes_performed"])
        self.assertFalse(result["canonical_zettel_writes_performed"])
        self.assertEqual(
            result["acceptance_document_sha256"],
            "sha256:" + hashlib.sha256(raw).hexdigest(),
        )
        backfill = archive_cli.notion_property_backfill
        loaded = backfill.load_notion_property_backfill_acceptance(output)
        self.assertEqual(loaded["mirror_page_count"], 1)
        before = raw

        code, stdout, stderr = self.run_cli(arguments)
        self.assertEqual(code, 1)
        blocked = json.loads(stdout)
        self.assertEqual(
            blocked["reason_codes"],
            ["notion_property_backfill_acceptance_output_exists"],
        )
        self.assertEqual(output.read_bytes(), before)
        self.assert_private_canaries_absent(stdout, stderr)

    def test_dry_run_streams_content_free_progress_and_plan(self) -> None:
        code, stdout, stderr = self.run_cli(self.base_arguments() + ["--dry-run"])

        self.assertEqual(code, 0, stderr)
        result = json.loads(stdout)
        self.assertTrue(result["ok"])
        self.assertEqual(result["category_counts"]["mapped"], 1)
        progress_lines = [
            line.removeprefix("WOM-PROGRESS ")
            for line in stderr.splitlines()
            if line.startswith("WOM-PROGRESS ")
        ]
        self.assertTrue(progress_lines)
        first = json.loads(progress_lines[0])
        self.assertEqual(first["stage"], "starting")
        self.assertEqual(first["processed"], 0)
        self.assertFalse(first["private_values_echoed"])
        self.assertFalse(first["paths_echoed"])
        self.assert_private_canaries_absent(stdout, stderr)

    def test_missing_or_cross_target_options_fail_closed_without_private_echo(self) -> None:
        code, stdout, stderr = self.run_cli(
            [
                "migrate",
                str(self.root),
                "--target",
                "notion-source-properties",
                "--dry-run",
                "--source-mirror",
                str(self.mirror),
            ]
        )
        self.assertEqual(code, 1)
        self.assertIn(
            "requires --acceptance-file after the reviewed bootstrap step",
            stderr,
        )
        self.assert_private_canaries_absent(stdout, stderr)

        code, _stdout, stderr = self.run_cli(
            [
                "migrate",
                str(self.root),
                "--target",
                "frontmatter-v0.3",
                "--dry-run",
                "--source-mirror",
                str(self.mirror),
            ]
        )
        self.assertEqual(code, 1)
        self.assertIn("require --target notion-source-properties", stderr)
        self.assertNotIn(str(self.mirror), stderr)

        code, stdout, stderr = self.run_cli(
            [
                "migrate",
                str(self.root),
                "--target",
                "notion-source-properties",
                "--source-mirror",
                str(self.mirror),
                "--acceptance-bootstrap",
                "--dry-run",
                "--format",
                "json",
            ]
        )
        self.assertEqual(code, 1)
        self.assertIn("requires --acceptance-output", stderr)
        self.assert_private_canaries_absent(stdout, stderr)

    def test_current_inventory_is_target_conditional_not_globally_open(self) -> None:
        inventory = archive_cli.command_status.build_command_status_inventory(
            archive_cli.build_parser(),
            archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS,
        )
        by_path = {
            row["canonical_path"]: row for row in inventory["commands"]
        }
        self.assertEqual(
            by_path["migrate"]["approval_status"],
            "approval_available",
        )
        self.assertEqual(
            by_path["migrate"]["approval_scope"],
            {
                "kind": "argument_value_allowlist",
                "argument": "--target",
                "allowed_values": ["notion-source-properties"],
                "outside_scope_status": "approval_fixed_closed",
                "outside_scope_reason_code": (
                    "compound_exact_human_approval_binding_required"
                ),
            },
        )
        self.assertEqual(
            inventory["counts"]["approval_available_command_count"],
            39,
        )
        self.assertEqual(
            inventory["counts"]["approval_fixed_closed_command_count"],
            75,
        )
        self.assertEqual(
            inventory["counts"]["conditional_approval_command_count"],
            2,
        )

        code, stdout, stderr = self.run_cli(
            [
                "migrate",
                str(self.root),
                "--target",
                "frontmatter-v0.3",
                "--approve",
                "--format",
                "json",
            ]
        )
        self.assertEqual(code, 1)
        blocked = json.loads(stdout)
        self.assertEqual(
            blocked["reason_codes"],
            ["compound_exact_human_approval_binding_required"],
        )
        self.assert_private_canaries_absent(stdout, stderr)

    def test_fresh_resume_and_revert_route_only_to_fixed_domain_wrappers(self) -> None:
        safe_result = {
            "ok": True,
            "reason_code": "synthetic_wrapper_succeeded",
            "writes_performed": False,
            "private_values_echoed": False,
        }
        with mock.patch.object(
            archive_cli.notion_property_backfill,
            "execute_notion_property_backfill",
            return_value=safe_result,
        ) as fresh:
            code, stdout, stderr = self.run_cli(
                self.base_arguments()
                + ["--approve", "--reviewed-by", "person:test-reviewer"]
            )
        self.assertEqual(code, 0, stderr)
        self.assertTrue(fresh.called)
        self.assertTrue(callable(fresh.call_args.kwargs["progress_hook"]))
        self.assertTrue(callable(fresh.call_args.kwargs["planning_progress"]))
        self.assertTrue(
            callable(fresh.call_args.kwargs["execution_locator_hook"])
        )
        self.assertEqual(json.loads(stdout)["reason_code"], "synthetic_wrapper_succeeded")

        with mock.patch.object(
            archive_cli.notion_property_backfill,
            "resume_notion_property_backfill",
            return_value=safe_result,
        ) as resumed:
            code, stdout, stderr = self.run_cli(
                self.base_arguments()
                + [
                    "--approve",
                    "--reviewed-by",
                    "person:test-reviewer",
                    "--resume",
                    "--approval-id",
                    "approval_" + "a" * 32,
                    "--execution-sha256",
                    "sha256:" + "b" * 64,
                ]
            )
        self.assertEqual(code, 0, stderr)
        self.assertTrue(resumed.called)
        self.assertEqual(json.loads(stdout)["reason_code"], "synthetic_wrapper_succeeded")

        with mock.patch.object(
            archive_cli.notion_property_backfill,
            "execute_notion_property_backfill_revert",
            return_value=safe_result,
        ) as reverted:
            code, stdout, stderr = self.run_cli(
                self.base_arguments()
                + [
                    "--approve",
                    "--reviewed-by",
                    "person:test-reviewer",
                    "--revert",
                ]
            )
        self.assertEqual(code, 0, stderr)
        self.assertTrue(reverted.called)
        self.assertEqual(json.loads(stdout)["reason_code"], "synthetic_wrapper_succeeded")
        self.assert_private_canaries_absent(stdout, stderr)

    def test_execution_progress_is_throttled_and_locator_is_content_free(self) -> None:
        progress = archive_cli._NotionPropertyBackfillCliProgress()
        stderr = io.StringIO()
        manifest_sha256 = "sha256:" + "a" * 64
        execution_sha256 = "sha256:" + "b" * 64
        locator = {
            "schema_version": (
                "wom-kit/notion-property-backfill-execution-locator/v0.1"
            ),
            "mode": "apply",
            "approval_id": "approval_" + "c" * 32,
            "execution_sha256": execution_sha256,
            "manifest_sha256": manifest_sha256,
            "checkpoint_required_for_resume": True,
            "private_values_echoed": False,
            "paths_echoed": False,
            "source_page_ids_echoed": False,
            "property_values_echoed": False,
        }
        with redirect_stderr(stderr):
            progress.execution(
                archive_cli.ExactOperationProgress(
                    manifest_sha256,
                    None,
                    "apply",
                    "preflight",
                    0,
                    8_566,
                    0,
                    8_566,
                )
            )
            progress.execution(
                archive_cli.ExactOperationProgress(
                    manifest_sha256,
                    execution_sha256,
                    "apply",
                    "preflight",
                    0,
                    8_566,
                    0,
                    8_566,
                )
            )
            for ordinal in range(100):
                progress.execution(
                    archive_cli.ExactOperationProgress(
                        manifest_sha256,
                        execution_sha256,
                        "apply",
                        "field_verified",
                        ordinal,
                        8_566,
                        ordinal,
                        8_566,
                        ordinal,
                    )
                )
            progress.locator(locator)

        lines = stderr.getvalue().splitlines()
        progress_lines = [
            line for line in lines if line.startswith("WOM-PROGRESS ")
        ]
        self.assertEqual(len(progress_lines), 2)
        self.assertTrue(
            any(line.startswith("WOM-RESUME ") for line in lines)
        )
        self.assertEqual(progress.resume_locator, locator)
        self.assert_private_canaries_absent(stderr.getvalue())

    def test_state_unknown_json_requires_reconciliation_and_returns_locator(self) -> None:
        locator = {
            "schema_version": (
                "wom-kit/notion-property-backfill-execution-locator/v0.1"
            ),
            "mode": "apply",
            "approval_id": "approval_" + "d" * 32,
            "execution_sha256": "sha256:" + "e" * 64,
            "manifest_sha256": "sha256:" + "f" * 64,
            "checkpoint_required_for_resume": True,
            "private_values_echoed": False,
            "paths_echoed": False,
            "source_page_ids_echoed": False,
            "property_values_echoed": False,
        }

        def fail_after_writer_entry(_plan, **kwargs):
            kwargs["execution_locator_hook"](locator)
            raise archive_cli.ExactHumanApprovalWorkflowError(
                "exact_human_approval_state_unknown"
            )

        with mock.patch.object(
            archive_cli.notion_property_backfill,
            "execute_notion_property_backfill",
            side_effect=fail_after_writer_entry,
        ):
            code, stdout, stderr = self.run_cli(
                self.base_arguments()
                + ["--approve", "--reviewed-by", "person:test-reviewer"]
            )

        self.assertEqual(code, 1)
        result = json.loads(stdout)
        self.assertEqual(result["schema"], "wom-kit/cli-error/v0.1")
        self.assertEqual(result["effects_state"], "unknown")
        self.assertEqual(result["status_class"], "reconciliation_required")
        self.assertTrue(result["reconciliation_required"])
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertEqual(result["resume_locator"], locator)
        self.assertIn("WOM-RESUME ", stderr)
        self.assert_private_canaries_absent(stdout, stderr)

    def test_bootstrap_hidden_temp_cleanup_failure_is_state_unknown(self) -> None:
        original_unlink = Path.unlink

        def fail_hidden_temporary(path, *args, **kwargs):
            if path.name.endswith(".tmp"):
                raise OSError("synthetic hidden temporary cleanup failure")
            return original_unlink(path, *args, **kwargs)

        arguments = [
            "migrate",
            str(self.root),
            "--target",
            "notion-source-properties",
            "--source-mirror",
            str(self.mirror),
            "--acceptance-bootstrap",
            "--acceptance-output",
            self.acceptance_output,
            "--dry-run",
            "--format",
            "json",
        ]
        with mock.patch.object(
            archive_cli.notion_property_backfill,
            "_publish_acceptance_final_no_replace",
            side_effect=OSError("synthetic link failure"),
        ), mock.patch.object(Path, "unlink", new=fail_hidden_temporary):
            code, stdout, stderr = self.run_cli(arguments)

        self.assertEqual(code, 1)
        result = json.loads(stdout)
        self.assertEqual(result["effects_state"], "unknown")
        self.assertEqual(result["files_written"], None)
        self.assertTrue(result["reconciliation_required"])
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertEqual(
            result["reason_codes"],
            [
                "notion_property_backfill_acceptance_output_outcome_unknown"
            ],
        )
        self.assert_private_canaries_absent(stdout, stderr)

    def test_bootstrap_post_publish_cleanup_failure_is_state_unknown(self) -> None:
        original_unlink = Path.unlink

        def publish_hard_link(temporary, output):
            archive_cli.notion_property_backfill.os.link(temporary, output)
            return False, False

        def fail_hidden_temporary(path, *args, **kwargs):
            if path.name.endswith(".tmp"):
                raise OSError("synthetic post-publish cleanup failure")
            return original_unlink(path, *args, **kwargs)

        arguments = [
            "migrate",
            str(self.root),
            "--target",
            "notion-source-properties",
            "--source-mirror",
            str(self.mirror),
            "--acceptance-bootstrap",
            "--acceptance-output",
            self.acceptance_output,
            "--dry-run",
            "--format",
            "json",
        ]
        with mock.patch.object(
            archive_cli.notion_property_backfill,
            "_publish_acceptance_final_no_replace",
            side_effect=publish_hard_link,
        ), mock.patch.object(Path, "unlink", new=fail_hidden_temporary):
            code, stdout, stderr = self.run_cli(arguments)

        self.assertEqual(code, 1)
        result = json.loads(stdout)
        self.assertEqual(result["effects_state"], "unknown")
        self.assertEqual(result["files_written"], None)
        self.assertTrue(result["reconciliation_required"])
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertEqual(
            result["reason_codes"],
            [
                "notion_property_backfill_acceptance_output_outcome_unknown"
            ],
        )
        output = self.root.joinpath(*self.acceptance_output.split("/"))
        self.assertTrue(output.exists())
        self.assertGreater(os.lstat(output).st_nlink, 1)
        with self.assertRaises(
            archive_cli.notion_property_backfill.NotionPropertyBackfillError
        ):
            archive_cli.notion_property_backfill.load_notion_property_backfill_acceptance(
                output
            )
        self.assert_private_canaries_absent(stdout, stderr)

    def test_resume_requires_every_authenticated_checkpoint_locator(self) -> None:
        code, stdout, stderr = self.run_cli(
            self.base_arguments()
            + [
                "--approve",
                "--reviewed-by",
                "person:test-reviewer",
                "--resume",
            ]
        )
        self.assertEqual(code, 1)
        self.assertIn(
            "--resume requires --approve, --approval-id, and --execution-sha256",
            stderr,
        )
        self.assert_private_canaries_absent(stdout, stderr)


if __name__ == "__main__":
    unittest.main()
