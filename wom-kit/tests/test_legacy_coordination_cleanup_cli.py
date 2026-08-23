from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import archive_cli  # noqa: E402


class LegacyCoordinationCleanupCliTests(unittest.TestCase):
    def run_cli(self, args: list[str]) -> tuple[int, str]:
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            code = archive_cli.main(args)
        return code, output.getvalue()

    @staticmethod
    def plan_result(
        *, ok: bool = True, status: str = "dry_run_ready"
    ) -> dict[str, object]:
        return {
            "ok": ok,
            "status": status,
            "dry_run": True,
            "action": "legacy_coordination_cleanup",
            "plan_sha256": "a" * 64,
            "summary": {
                "file_count": 2,
                "directory_count": 1,
                "total_bytes": 17,
            },
            "blockers": [] if ok else ["legacy_coordination_cleanup_blocked"],
            "warnings": [],
        }

    @staticmethod
    def apply_result(*, ok: bool = True, status: str = "cleanup_completed") -> dict[str, object]:
        return {
            "ok": ok,
            "status": status,
            "dry_run": False,
            "approved": ok,
            "action": "legacy_coordination_cleanup",
            "plan_sha256": "b" * 64,
            "summary": {
                "file_count": 2,
                "directory_count": 1,
                "total_bytes": 17,
            },
            "blockers": [] if ok else ["legacy_coordination_cleanup_partial"],
            "warnings": [],
        }

    def test_parser_requires_exactly_one_mode_and_exposes_no_broad_path_option(self) -> None:
        parser = archive_cli.build_parser()
        subcommands = archive_cli.subparser_action(parser)
        self.assertIsNotNone(subcommands)
        assert subcommands is not None
        command = subcommands.choices["legacy-coordination-cleanup"]
        option_strings = {
            option
            for action in command._actions
            for option in action.option_strings
        }
        self.assertNotIn("--target", option_strings)
        self.assertNotIn("--path", option_strings)
        self.assertNotIn("--recursive", option_strings)
        parsed = parser.parse_args(
            ["legacy-coordination-cleanup", "workspace", "--dry-run"]
        )
        self.assertEqual(
            parsed.max_files,
            archive_cli.legacy_cleanup.DEFAULT_LEGACY_COORDINATION_CLEANUP_MAX_FILES,
        )
        self.assertEqual(
            parsed.max_bytes,
            archive_cli.legacy_cleanup.DEFAULT_LEGACY_COORDINATION_CLEANUP_MAX_BYTES,
        )
        approve_action = next(
            action
            for action in command._actions
            if "--approve" in action.option_strings
        )
        self.assertIn("unavailable in v0.4.3", approve_action.help.lower())
        self.assertIn("dry-run, plan, or audit", approve_action.help.lower())

        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["legacy-coordination-cleanup", "workspace"])
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "legacy-coordination-cleanup",
                    "workspace",
                    "--dry-run",
                    "--approve",
                ]
            )

    def test_dry_run_calls_core_with_explicit_limits_and_returns_core_json(self) -> None:
        result = self.plan_result()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            archive_cli.legacy_cleanup,
            "legacy_coordination_cleanup",
            return_value=result,
        ) as apply, mock.patch.object(
            archive_cli.legacy_cleanup,
            "legacy_coordination_cleanup_plan",
        ) as plan:
            workspace_root = Path(tmp) / "generated-workspace"
            code, output = self.run_cli(
                [
                    "legacy-coordination-cleanup",
                    str(workspace_root),
                    "--dry-run",
                    "--max-files",
                    "12",
                    "--max-bytes",
                    "3456",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(code, 0, output)
        self.assertEqual(json.loads(output), result)
        apply.assert_called_once_with(
            workspace_root,
            dry_run=True,
            approve=False,
            expected_plan_sha256=None,
            reviewed_by=None,
            affirm_workspace_owner_authorized=False,
            affirm_external_writers_quiescent=False,
            affirm_retired_state_disposable=False,
            affirm_backups_and_receipts_disposable=False,
            max_files=12,
            max_bytes=3456,
        )
        plan.assert_not_called()

    def test_approve_fails_closed_before_cleanup_service(self) -> None:
        expected_plan_sha256 = "b" * 64
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            archive_cli.legacy_cleanup,
            "legacy_coordination_cleanup_plan",
        ) as plan, mock.patch.object(
            archive_cli.legacy_cleanup,
            "legacy_coordination_cleanup",
            return_value=self.apply_result(),
        ) as apply:
            workspace_root = Path(tmp) / "generated-workspace"
            code, output = self.run_cli(
                [
                    "legacy-coordination-cleanup",
                    str(workspace_root),
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                    "--expected-plan-sha256",
                    expected_plan_sha256,
                    "--affirm-workspace-owner-authorized",
                    "--affirm-external-writers-quiescent",
                    "--affirm-retired-state-disposable",
                    "--affirm-backups-and-receipts-disposable",
                    "--max-files",
                    "24",
                    "--max-bytes",
                    "7890",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(code, 1, output)
        self.assertEqual(
            json.loads(output),
            {
                "schema": "wom-kit/cli-error/v0.1",
                "ok": False,
                "state": "blocked",
                "command": "legacy-coordination-cleanup",
                "error_class": "policy",
                "status_class": "blocked",
                "effects_state": "none",
                "exit_code": 1,
                "lifecycle_action": "legacy_coordination_cleanup",
                "reason_codes": [
                    "compound_exact_human_approval_binding_required"
                ],
                "files_written": [],
                "private_values_echoed": False,
            },
        )
        apply.assert_not_called()
        plan.assert_not_called()

    def test_blocked_and_partial_results_exit_nonzero(self) -> None:
        blocked = self.plan_result(ok=False, status="blocked")
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            archive_cli.legacy_cleanup,
            "legacy_coordination_cleanup",
            return_value=blocked,
        ):
            workspace_root = Path(tmp) / "generated-workspace"
            blocked_code, blocked_output = self.run_cli(
                [
                    "legacy-coordination-cleanup",
                    str(workspace_root),
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            partial_code, partial_output = self.run_cli(
                [
                    "legacy-coordination-cleanup",
                    str(workspace_root),
                    "--approve",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(blocked_code, 1, blocked_output)
        self.assertEqual(partial_code, 1, partial_output)
        self.assertEqual(json.loads(blocked_output)["status"], "blocked")
        self.assertEqual(json.loads(partial_output)["state"], "blocked")
        self.assertEqual(
            json.loads(partial_output)["reason_codes"],
            ["compound_exact_human_approval_binding_required"],
        )

    def test_text_output_is_count_only_and_does_not_echo_private_paths(self) -> None:
        private_sentinel = "C:/PRIVATE/never-echo/secret-mailbox.json"
        result = self.plan_result()
        result["private_debug"] = {
            "workspace_root": private_sentinel,
            "relative_names": ["secret-mailbox.json"],
        }
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            archive_cli.legacy_cleanup,
            "legacy_coordination_cleanup",
            return_value=result,
        ):
            workspace_root = Path(tmp) / "generated-workspace"
            code, output = self.run_cli(
                [
                    "legacy-coordination-cleanup",
                    str(workspace_root),
                    "--dry-run",
                    "--format",
                    "text",
                ]
            )

        self.assertEqual(code, 0, output)
        self.assertIn("Legacy coordination cleanup: dry_run_ready", output)
        self.assertIn("- files: 2", output)
        self.assertIn("- directories: 1", output)
        self.assertIn("- bytes: 17", output)
        self.assertIn(f"- plan sha256: {'a' * 64}", output)
        self.assertNotIn(str(workspace_root), output)
        self.assertNotIn(private_sentinel, output)
        self.assertNotIn("secret-mailbox.json", output)

    def test_capabilities_exposes_preview_only_boundary_without_broad_path(self) -> None:
        code, output = self.run_cli(["capabilities", "--machine"])
        self.assertEqual(code, 0, output)
        result = json.loads(output)
        command = next(
            item
            for item in result["data"]["commands"]
            if item["name"] == "legacy-coordination-cleanup"
        )
        self.assertEqual(command["aliases"], [])
        self.assertEqual(command["required_positionals"], ["workspace_root"])
        expected_options = {
            "--dry-run",
            "--approve",
            "--reviewed-by",
            "--expected-plan-sha256",
            "--affirm-workspace-owner-authorized",
            "--affirm-external-writers-quiescent",
            "--affirm-retired-state-disposable",
            "--affirm-backups-and-receipts-disposable",
            "--max-files",
            "--max-bytes",
            "--format",
        }
        self.assertTrue(expected_options.issubset(set(command["options"])))
        self.assertNotIn("--target", command["options"])
        self.assertNotIn("--path", command["options"])
        self.assertIn("unavailable in v0.4.3", command["help"].lower())
        self.assertIn("collab/ is never traversed or changed", command["help"].lower())

    @unittest.skipUnless(os.name == "nt", "approved apply is Windows-only")
    def test_real_generated_workspace_dry_run_and_approve_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "generated-workspace"
            archive = workspace / "archive"
            archive.mkdir(parents=True)
            (archive / "archive.yml").write_text(
                "archive_id: archive:personal:cli-test\n"
                "name: CLI Test\n"
                "type: personal\n",
                encoding="utf-8",
            )
            (archive / "archive-identity.yml").write_text(
                "identity:\n"
                "  archive_id: archive:personal:cli-test\n"
                "  identity_id: identity:archive:personal:cli-test\n",
                encoding="utf-8",
            )
            target_file = workspace / ".mow-harness" / "source" / "private.bin"
            target_file.parent.mkdir(parents=True)
            target_file.write_bytes(b"generated-private-state")
            collab_file = workspace / "collab" / "STATE.md"
            collab_file.parent.mkdir()
            collab_file.write_bytes(b"outside-collab-sentinel")
            outside_file = workspace / "ordinary.txt"
            outside_file.write_bytes(b"outside-sentinel")

            dry_code, dry_output = self.run_cli(
                [
                    "legacy-coordination-cleanup",
                    str(workspace),
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(dry_code, 0, dry_output)
            dry_result = json.loads(dry_output)
            self.assertEqual(dry_result["status"], "dry_run_ready")
            self.assertNotIn(str(workspace), dry_output)
            self.assertNotIn("private.bin", dry_output)
            self.assertNotIn("generated-private-state", dry_output)

            apply_code, apply_output = self.run_cli(
                [
                    "legacy-coordination-cleanup",
                    str(workspace),
                    "--approve",
                    "--reviewed-by",
                    "person:cli-test-owner",
                    "--expected-plan-sha256",
                    dry_result["plan_sha256"],
                    "--affirm-workspace-owner-authorized",
                    "--affirm-external-writers-quiescent",
                    "--affirm-retired-state-disposable",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(apply_code, 1, apply_output)
            apply_result = json.loads(apply_output)
            self.assertEqual(apply_result["state"], "blocked")
            self.assertEqual(
                apply_result["reason_codes"],
                ["compound_exact_human_approval_binding_required"],
            )
            self.assertTrue((workspace / ".mow-harness").exists())
            self.assertEqual(collab_file.read_bytes(), b"outside-collab-sentinel")
            self.assertEqual(outside_file.read_bytes(), b"outside-sentinel")
            residues = [
                child.name
                for child in workspace.iterdir()
                if "legacy-coordination-cleanup" in child.name
            ]
            self.assertEqual(residues, [])

    def test_real_dry_run_rejects_apply_only_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "generated-workspace"
            archive = workspace / "archive"
            archive.mkdir(parents=True)
            (archive / "archive.yml").write_text(
                "archive_id: archive:personal:cli-gate\n",
                encoding="utf-8",
            )
            (archive / "archive-identity.yml").write_text(
                "identity:\n  archive_id: archive:personal:cli-gate\n",
                encoding="utf-8",
            )
            (workspace / ".mow-harness").mkdir()

            code, output = self.run_cli(
                [
                    "legacy-coordination-cleanup",
                    str(workspace),
                    "--dry-run",
                    "--reviewed-by",
                    "person:should-not-be-accepted",
                    "--format",
                    "json",
                ]
            )

            self.assertEqual(code, 1, output)
            result = json.loads(output)
            self.assertEqual(result["status"], "blocked")
            self.assertIn(
                "approval_fields_only_valid_for_apply",
                result["blockers"],
            )
            self.assertTrue((workspace / ".mow-harness").exists())


if __name__ == "__main__":
    unittest.main()
