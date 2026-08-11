from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wom_kit import archive_cli, operation_control


TARGET = "v0.3.316"
MATERIALIZATION_PLAN = "sha256:" + "a" * 64
REPAIR_PLAN = "b" * 64


def batch_result(*, private_marker: str) -> dict[str, object]:
    return {
        "ok": True,
        "status": "inspected",
        "action": "inspect-all",
        "plan": {
            "materialization_plan_sha256": MATERIALIZATION_PLAN,
            "matches_expected": True,
        },
        "entries": [
            {
                "entry_ref": "update-entry:0001",
                "private_path": private_marker,
            }
        ],
        "summary": {
            "requested_entry_count": 25,
            "inspected_entry_count": 25,
            "entry_kind_counts": {
                "plain_directory": 1,
                "regular_file": 24,
            },
            "runtime_shadow_kind_counts": {
                "bytecode_cache_directory": 1,
                "derived_bytecode_file": 24,
            },
            "remediation_counts": {"project_bytecode_repair": 25},
            "private_summary": private_marker,
        },
        "project_bytecode_repair_route_eligible": True,
        "remediation_available": True,
        "remediation": {
            "route": "project_bytecode_repair",
            "route_eligible": True,
            "exact_collision_set_covered": True,
            "all_requested_entries_supported": True,
            "route_set_counts_complete": True,
            "collision_entry_count": 25,
            "derived_bytecode_file_count": 24,
            "bytecode_cache_directory_count": 1,
            "unsupported_entry_count": 0,
        },
        "blocker_codes": [],
        "blockers": [private_marker],
        "next_safe_actions": [private_marker],
    }


class Letter129CollisionCliTests(unittest.TestCase):
    @staticmethod
    def run_cli(argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = archive_cli.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    @staticmethod
    def inspect_all_argv(root: Path, *, output_format: str) -> list[str]:
        return [
            "project-version-update-collision",
            str(root),
            "--target",
            TARGET,
            "--expected-plan-sha256",
            MATERIALIZATION_PLAN,
            "--action",
            "inspect-all",
            "--dry-run",
            "--format",
            output_format,
        ]

    def test_parser_keeps_one_alias_free_command_and_optional_entry_ref(
        self,
    ) -> None:
        parser = archive_cli.build_parser()
        command = next(
            item
            for item in archive_cli.parser_command_manifest(parser)
            if item["name"] == "project-version-update-collision"
        )
        parsed = parser.parse_args(
            [
                "project-version-update-collision",
                ".",
                "--target",
                TARGET,
                "--expected-plan-sha256",
                MATERIALIZATION_PLAN,
                "--action",
                "inspect-all",
                "--dry-run",
            ]
        )

        self.assertEqual(command["aliases"], [])
        self.assertEqual(parsed.action, "inspect-all")
        self.assertIsNone(parsed.entry_ref)

    def test_json_calls_public_batch_once_derives_refs_and_projects_privacy(
        self,
    ) -> None:
        private_marker = "PRIVATE_LETTER129_LOCAL_FILENAME.pyc"
        captured: dict[str, object] = {}

        def fake_service(root: Path, **kwargs: object) -> dict[str, object]:
            captured["root"] = root
            captured.update(kwargs)
            return batch_result(private_marker=private_marker)

        with tempfile.TemporaryDirectory() as tmp, patch.object(
            archive_cli.archive_services,
            "wom_kit_project_version_update_collision_inspect_batch",
            side_effect=fake_service,
        ) as service:
            root = Path(tmp) / "PRIVATE_LETTER129_PROJECT_ROOT"
            root.mkdir()
            code, stdout, stderr = self.run_cli(
                self.inspect_all_argv(root, output_format="json")
            )

        result = json.loads(stdout)
        rendered = stdout + stderr
        self.assertEqual(code, 0, rendered)
        self.assertEqual(service.call_count, 1)
        self.assertEqual(captured["target"], TARGET)
        self.assertEqual(
            captured["expected_plan_sha256"], MATERIALIZATION_PLAN
        )
        self.assertNotIn("entry_refs", captured)
        self.assertNotIn("entries", result)
        self.assertNotIn(private_marker, rendered)
        self.assertNotIn(str(root), rendered)
        self.assertEqual(
            result["summary"]["entry_kind_counts"],
            {"plain_directory": 1, "regular_file": 24},
        )
        self.assertEqual(
            result["summary"]["runtime_shadow_kind_counts"],
            {
                "bytecode_cache_directory": 1,
                "derived_bytecode_file": 24,
            },
        )
        self.assertEqual(
            result["remediation"]["route"],
            "project_bytecode_repair",
        )
        self.assertFalse(
            result["remediation"]["automatic_update_retry"]
        )

    def test_route_emits_three_separate_exact_command_templates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            archive_cli.archive_services,
            "wom_kit_project_version_update_collision_inspect_batch",
            return_value=batch_result(private_marker="PRIVATE_COMMAND_DECOY"),
        ):
            root = Path(tmp) / "project"
            root.mkdir()
            code, stdout, _ = self.run_cli(
                self.inspect_all_argv(root, output_format="json")
            )

        result = json.loads(stdout)
        commands = result["remediation"]["commands"]
        self.assertEqual(code, 0, stdout)
        self.assertEqual(
            [item["kind"] for item in commands],
            ["repair_plan", "repair_approval", "fresh_update_preview"],
        )
        self.assertEqual(
            commands[0]["command"],
            "archive project-bytecode-repair-plan . "
            f"--target {TARGET} "
            "--expected-materialization-plan-sha256 "
            f"{MATERIALIZATION_PLAN} --dry-run --format json",
        )
        self.assertIn(
            "--expected-plan-sha256 <repair-plan-sha256>",
            commands[1]["command"],
        )
        self.assertIn(
            "--reviewed-by <reviewer-id>", commands[1]["command"]
        )
        self.assertIn(
            "--affirm-external-writers-quiescent",
            commands[1]["command"],
        )
        self.assertIn(
            "--expected-materialization-plan-sha256 "
            + MATERIALIZATION_PLAN,
            commands[1]["command"],
        )
        self.assertEqual(
            commands[2]["command"],
            "archive project-version-update . "
            f"--target {TARGET} --dry-run --format json",
        )
        self.assertTrue(
            result["remediation"]["commands_must_run_separately"]
        )

    def test_text_reveals_counts_kinds_route_and_commands_not_private_data(
        self,
    ) -> None:
        private_marker = "PRIVATE_LETTER129_TEXT_DECOY.pyc"
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            archive_cli.archive_services,
            "wom_kit_project_version_update_collision_inspect_batch",
            return_value=batch_result(private_marker=private_marker),
        ):
            root = Path(tmp) / "PRIVATE_TEXT_ROOT"
            root.mkdir()
            code, stdout, stderr = self.run_cli(
                self.inspect_all_argv(root, output_format="text")
            )

        rendered = stdout + stderr
        self.assertEqual(code, 0, rendered)
        self.assertIn("Inspected entries: 25", stdout)
        self.assertIn("plain_directory=1", stdout)
        self.assertIn("derived_bytecode_file=24", stdout)
        self.assertIn(
            "Remediation route: project_bytecode_repair", stdout
        )
        self.assertIn("STEP 1 repair_plan:", stdout)
        self.assertIn("STEP 2 repair_approval:", stdout)
        self.assertIn("STEP 3 fresh_update_preview:", stdout)
        self.assertIn("never automatically retry", stdout)
        self.assertNotIn(private_marker, rendered)
        self.assertNotIn(str(root), rendered)

    def test_inspect_all_refuses_caller_entry_refs_before_service_call(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            archive_cli.archive_services,
            "wom_kit_project_version_update_collision_inspect_batch",
        ) as service:
            root = Path(tmp) / "project"
            root.mkdir()
            argv = self.inspect_all_argv(root, output_format="json")
            argv.extend(["--entry-ref", "update-entry:0001"])
            code, stdout, _ = self.run_cli(argv)

        result = json.loads(stdout)
        self.assertEqual(code, 1)
        service.assert_not_called()
        self.assertIn(
            "project_update_collision_inspect_all_derives_entry_refs",
            result["blocker_codes"],
        )
        self.assertFalse(result["write_boundary"]["writes"])

    def test_multiple_operation_collisions_route_to_one_inspect_all(self) -> None:
        actions = operation_control._project_update_completed_next_actions(
            {
                "command": "project-version-update",
                "completion_ok": False,
                "target_tag": TARGET,
                "collision_refs": [
                    "update-entry:0001",
                    "update-entry:0002",
                    "update-entry:0025",
                ],
                "materialization_plan_sha256": MATERIALIZATION_PLAN,
            }
        )

        self.assertIsNotNone(actions)
        self.assertEqual(len(actions or []), 1)
        command = (actions or [""])[0]
        self.assertIn("--action inspect-all", command)
        self.assertNotIn("--entry-ref", command)
        self.assertIn(MATERIALIZATION_PLAN, command)
        self.assertNotIn("separately", command)

    def test_bytecode_text_reports_binding_directories_and_partial_guidance(
        self,
    ) -> None:
        with patch.object(
            archive_cli.completion_workflows,
            "project_bytecode_repair_plan",
            return_value={
                "ok": True,
                "state": "ready",
                "summary": {
                    "bytecode_file_count": 24,
                    "bytecode_total_bytes": 240,
                    "pycache_directory_count": 1,
                    "collision_binding_verified": True,
                    "plan_sha256": REPAIR_PLAN,
                },
                "blockers": [],
            },
        ):
            plan_code, plan_stdout, _ = self.run_cli(
                [
                    "project-bytecode-repair-plan",
                    ".",
                    "--target",
                    TARGET,
                    "--expected-materialization-plan-sha256",
                    MATERIALIZATION_PLAN,
                    "--dry-run",
                    "--format",
                    "text",
                ]
            )
        self.assertEqual(plan_code, 0, plan_stdout)
        self.assertIn("cache directories: 1", plan_stdout)
        self.assertIn("collision binding verified: True", plan_stdout)

        with patch.object(
            archive_cli.completion_workflows,
            "project_bytecode_repair",
            return_value={
                "ok": False,
                "state": "partial",
                "summary": {
                    "removed_count": 12,
                    "removed_empty_pycache_directory_count": 0,
                    "source_files_modified": False,
                    "receipt_path": None,
                },
                "writes_may_have_occurred": True,
                "blockers": ["project_bytecode_removal_failed"],
                "next_safe_actions": [
                    "Run a fresh project-bytecode-repair-plan."
                ],
            },
        ):
            repair_code, repair_stdout, _ = self.run_cli(
                [
                    "project-bytecode-repair",
                    ".",
                    "--expected-plan-sha256",
                    REPAIR_PLAN,
                    "--target",
                    TARGET,
                    "--expected-materialization-plan-sha256",
                    MATERIALIZATION_PLAN,
                    "--approve",
                    "--reviewed-by",
                    "person:letter129-reviewer",
                    "--affirm-external-writers-quiescent",
                    "--format",
                    "text",
                ]
            )
        self.assertEqual(repair_code, 1)
        self.assertIn("Project bytecode repair: partial", repair_stdout)
        self.assertIn("removed cache directories: 0", repair_stdout)
        self.assertIn("writes may have occurred: True", repair_stdout)
        self.assertIn("NEXT: Run a fresh", repair_stdout)

    def test_approved_repair_exception_reports_unverified_outcome(self) -> None:
        private_error = "PRIVATE_LETTER129_EXCEPTION_PATH"
        with patch.object(
            archive_cli.completion_workflows,
            "project_bytecode_repair",
            side_effect=RuntimeError(private_error),
        ):
            code, stdout, stderr = self.run_cli(
                [
                    "project-bytecode-repair",
                    ".",
                    "--expected-plan-sha256",
                    REPAIR_PLAN,
                    "--target",
                    TARGET,
                    "--expected-materialization-plan-sha256",
                    MATERIALIZATION_PLAN,
                    "--approve",
                    "--reviewed-by",
                    "person:letter129-reviewer",
                    "--affirm-external-writers-quiescent",
                    "--format",
                    "json",
                ]
            )

        result = json.loads(stdout)
        self.assertEqual(code, 1)
        self.assertEqual(result["state"], "recovery_required")
        self.assertFalse(result["outcome_verified"])
        self.assertTrue(result["writes_may_have_occurred"])
        self.assertIsNone(result["privacy_guards"]["writes"])
        self.assertNotIn(private_error, stdout + stderr)


if __name__ == "__main__":
    unittest.main()
