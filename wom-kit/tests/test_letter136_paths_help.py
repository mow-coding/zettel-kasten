from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wom_kit import archive_cli, archive_services
from wom_kit import operator_feedback_body


class Letter136PathsAndHelpTests(unittest.TestCase):
    def run_cli(self, argv: list[str]) -> tuple[int, str]:
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = archive_cli.main(argv)
        return code, stdout.getvalue() + stderr.getvalue()

    def make_archive(self, parent: Path) -> Path:
        root = parent / "archive"
        root.mkdir()
        (root / "archive.yml").write_text(
            "archive_id: archive:personal:letter136-fixture\n",
            encoding="utf-8",
        )
        return root

    def test_project_scratch_is_visible_but_never_an_inventory_or_gc_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = base / "project"
            project.mkdir()
            archive = self.make_archive(project)
            managed = archive / ".wom-scratch" / "managed-note.md"
            unmanaged = project / ".wom-scratch" / "unmanaged-note.md"
            managed.parent.mkdir(parents=True)
            unmanaged.parent.mkdir(parents=True)
            managed.write_text("MANAGED BODY MUST NOT ECHO", encoding="utf-8")
            unmanaged.write_text("UNMANAGED BODY MUST NOT ECHO", encoding="utf-8")

            result = archive_services.ai_artifact_inventory(
                archive,
                project_root=project,
                dry_run=True,
            )
            rendered = json.dumps(result, ensure_ascii=False)

            self.assertTrue(result["ok"], result)
            self.assertEqual(result["total_candidate_count"], 1)
            self.assertTrue(result["scan_policy"]["archive_root_only"])
            self.assertFalse(
                result["scan_policy"]["external_project_roots_inventory_eligible"]
            )
            external = result["unmanaged_project_scratch"]
            self.assertTrue(external["inspected"])
            self.assertTrue(external["present"])
            self.assertEqual(external["plain_file_count"], 1)
            self.assertFalse(external["managed_by_inventory"])
            self.assertFalse(external["managed_by_gc"])
            self.assertIn("never be deleted", "\n".join(result["warnings"]))
            self.assertIn(
                "explicit reviewed root-registration contract",
                "\n".join(external["next_safe_actions"]),
            )
            self.assertIn(
                "human-artifact or source-intake",
                "\n".join(result["next_safe_actions"]),
            )
            self.assertIn(
                "Do not close the operation",
                "\n".join(result["next_safe_actions"]),
            )
            self.assertNotIn(str(project), rendered)
            self.assertNotIn("managed-note.md", rendered)
            self.assertNotIn("unmanaged-note.md", rendered)
            self.assertNotIn("MANAGED BODY MUST NOT ECHO", rendered)
            self.assertNotIn("UNMANAGED BODY MUST NOT ECHO", rendered)

            unbound = base / "unbound-private-project"
            unbound_scratch = unbound / ".wom-scratch"
            unbound_scratch.mkdir(parents=True)
            (unbound_scratch / "PRIVATE-unbound-note.md").write_text(
                "PRIVATE UNBOUND BODY MUST NOT ECHO",
                encoding="utf-8",
            )
            unbound_result = archive_services.ai_artifact_inventory(
                archive,
                project_root=unbound,
                dry_run=True,
            )
            unbound_summary = unbound_result["unmanaged_project_scratch"]
            unbound_rendered = json.dumps(unbound_result, ensure_ascii=False)

            self.assertEqual(
                unbound_summary["reason_codes"],
                ["unmanaged_project_root_not_bound"],
            )
            self.assertFalse(unbound_summary["coverage_complete"])
            self.assertFalse(unbound_summary["present"])
            self.assertEqual(unbound_summary["entries_seen"], 0)
            self.assertEqual(unbound_summary["plain_file_count"], 0)
            self.assertNotIn(str(unbound), unbound_rendered)
            self.assertNotIn("PRIVATE-unbound-note.md", unbound_rendered)
            self.assertNotIn("PRIVATE UNBOUND BODY MUST NOT ECHO", unbound_rendered)

            parser = archive_cli.build_parser()
            help_stdout = StringIO()
            with self.assertRaises(SystemExit), redirect_stdout(help_stdout):
                parser.parse_args(["ai-artifact-inventory", "--help"])
            normalized_help = " ".join(help_stdout.getvalue().split())
            self.assertIn(
                "Optional exact direct parent of the archive root",
                normalized_help,
            )
            self.assertIn(
                "any other root is rejected without scanning",
                normalized_help,
            )

    def test_scratch_gc_approve_cannot_cross_into_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = base / "project"
            project.mkdir()
            archive = self.make_archive(project)
            managed = archive / ".wom-scratch" / "session" / "same-name.md"
            external = project / ".wom-scratch" / "session" / "same-name.md"
            managed.parent.mkdir(parents=True)
            external.parent.mkdir(parents=True)
            managed.write_text("archive-owned scratch", encoding="utf-8")
            external.write_text("project-owned scratch", encoding="utf-8")
            draft = archive / "inbox" / "zet_letter136_scratch_gc.md"
            draft.parent.mkdir()
            draft.write_text(
                "---\n"
                "id: zet_letter136_scratch_gc\n"
                "status: draft\n"
                "source_refs:\n"
                "  - type: ai_scratch\n"
                "    value: .wom-scratch/session/same-name.md\n"
                "---\n\n"
                "Durable reviewed summary.\n",
                encoding="utf-8",
            )

            preview = archive_services.ai_scratch_gc_for_zettel(
                archive,
                relative_path="inbox/zet_letter136_scratch_gc.md",
                dry_run=True,
            )
            self.assertTrue(preview["ok"], preview)
            self.assertEqual(
                [item["path"] for item in preview["cleanup_plan"]["candidates"]],
                [".wom-scratch/session/same-name.md"],
            )

            result = archive_services.ai_scratch_gc_for_zettel(
                archive,
                relative_path="inbox/zet_letter136_scratch_gc.md",
                dry_run=False,
                approve=True,
                reviewed_by="person:letter136-reviewer",
            )

            self.assertFalse(result["ok"], result)
            self.assertEqual(
                result["reason_codes"],
                ["compound_exact_human_approval_binding_required"],
            )
            self.assertEqual(result["files_written"], [])
            self.assertFalse(result["private_values_echoed"])
            self.assertTrue(managed.is_file())
            self.assertTrue(external.is_file())

            with patch.object(
                archive_services,
                "ai_scratch_gc_for_zettel",
                side_effect=AssertionError("approval reached scratch service"),
            ) as service:
                code, output = self.run_cli(
                    [
                        "ai-scratch-gc",
                        str(archive),
                        "--path",
                        "inbox/zet_letter136_scratch_gc.md",
                        "--approve",
                        "--reviewed-by",
                        "person:letter136-reviewer",
                        "--format",
                        "json",
                    ]
                )
            self.assertEqual(code, 1)
            payload = json.loads(output)
            self.assertEqual(
                payload["reason_codes"],
                ["compound_exact_human_approval_binding_required"],
            )
            self.assertEqual(payload["files_written"], [])
            self.assertFalse(payload["private_values_echoed"])
            service.assert_not_called()
            self.assertTrue(managed.is_file())
            self.assertTrue(external.is_file())

    def test_compose_reports_exact_request_shape_and_root_resolution_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            wrong_root = base / "project-not-archive"
            request = (
                wrong_root
                / "profiles"
                / "local"
                / "operator-feedback"
                / "requests"
                / "PRIVATE-letter136.json"
            )
            request.parent.mkdir(parents=True)
            (wrong_root / ".gitignore").write_text(
                "profiles/local/\n",
                encoding="utf-8",
            )
            request.write_text("PRIVATE REQUEST VALUE", encoding="utf-8")

            code, output = self.run_cli(
                [
                    "operator-feedback-compose",
                    str(wrong_root),
                    "--request",
                    "profiles/local/operator-feedback/requests/PRIVATE-letter136.json",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            result = json.loads(output)

            self.assertEqual(code, 1, output)
            self.assertEqual(
                result["blockers"],
                ["feedback_body_archive_root_invalid"],
            )
            self.assertEqual(
                result["requirements"]["request_path_pattern"],
                operator_feedback_body.REQUEST_PATH_PATTERN,
            )
            self.assertNotIn(str(wrong_root), output)
            self.assertNotIn("PRIVATE-letter136.json", output)
            self.assertNotIn("PRIVATE REQUEST VALUE", output)

            parser = archive_cli.build_parser()
            stdout = StringIO()
            with self.assertRaises(SystemExit), redirect_stdout(stdout):
                parser.parse_args(["operator-feedback-compose", "--help"])
            self.assertIn(
                operator_feedback_body.REQUEST_PATH_PATTERN,
                stdout.getvalue(),
            )

    def test_compose_wrong_request_directory_returns_shape_without_echo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            archive = self.make_archive(base)
            (archive / ".gitignore").write_text("profiles/local/\n", encoding="utf-8")
            outside = base / "PRIVATE-outside-request.json"
            outside.write_text("PRIVATE OUTSIDE VALUE", encoding="utf-8")

            result = operator_feedback_body.plan_operator_feedback_body(
                archive,
                outside,
                require_archive_marker=True,
            )
            rendered = json.dumps(result, ensure_ascii=False)

            self.assertEqual(
                result["blockers"],
                ["feedback_body_request_path_invalid"],
            )
            self.assertEqual(
                result["requirements"]["request_path_pattern"],
                operator_feedback_body.REQUEST_PATH_PATTERN,
            )
            self.assertNotIn(str(outside), rendered)
            self.assertNotIn("PRIVATE OUTSIDE VALUE", rendered)

    def test_mint_rebuild_blocker_carries_exact_content_free_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = self.make_archive(Path(tmp))
            duplicate_check: dict[str, object] = {}

            duplicates = archive_services.find_promotion_duplicates(
                archive,
                archive / "inbox" / "candidate.md",
                {"id": "zet_letter136_mint", "title": "Letter 136 mint"},
                "Distinct reviewed body.\n",
                "zettels/candidate.md",
                duplicate_check=duplicate_check,
            )

            self.assertEqual(
                [item["reason"] for item in duplicates],
                [archive_services.INDEX_REBUILD_REQUIRED],
            )
            self.assertEqual(
                duplicate_check["next_safe_actions"],
                list(archive_services.INDEX_REBUILD_NEXT_SAFE_ACTIONS),
            )
            self.assertNotIn(str(archive), json.dumps(duplicate_check))

    def test_recognized_subcommand_argument_error_uses_only_its_usage(self) -> None:
        code, output = self.run_cli(
            ["index", ".", "--not-a-real-letter136-option"]
        )

        self.assertEqual(code, 2)
        self.assertTrue(output.startswith("usage: archive index "), output)
        self.assertIn("unrecognized arguments: --not-a-real-letter136-option", output)
        self.assertNotIn("{find-objet,source-reference-coverage-audit", output)
        self.assertLess(len(output), 1_000)

        nested_code, nested_output = self.run_cli(
            ["derive-text", "capture", ".", "--not-a-real-letter136-option"]
        )
        self.assertEqual(nested_code, 2)
        self.assertTrue(
            nested_output.startswith("usage: archive derive-text capture "),
            nested_output,
        )
        self.assertNotIn("{find-objet,source-reference-coverage-audit", nested_output)

        collision_code, collision_output = self.run_cli(
            ["derive-text", "index", "capture"]
        )
        self.assertEqual(collision_code, 2)
        self.assertTrue(
            collision_output.startswith("usage: archive derive-text "),
            collision_output,
        )
        self.assertFalse(
            collision_output.startswith("usage: archive derive-text capture "),
            collision_output,
        )

        synthetic = argparse.ArgumentParser(prog="synthetic")
        synthetic_commands = synthetic.add_subparsers(dest="command", required=True)
        outer = synthetic_commands.add_parser("outer")
        outer.add_argument("--label")
        nested_commands = outer.add_subparsers(dest="nested", required=True)
        nested_commands.add_parser("capture")

        selected = archive_cli._selected_cli_argument_parser(
            synthetic,
            ["outer", "--label", "capture"],
        )
        self.assertIs(selected, outer)


if __name__ == "__main__":
    unittest.main()
