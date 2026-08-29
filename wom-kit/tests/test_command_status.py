from __future__ import annotations

import argparse
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from jsonschema import Draft202012Validator

from wom_kit import archive_cli, command_status


def _handler(_: argparse.Namespace) -> int:
    return 0


class CommandStatusSyntheticParserTests(unittest.TestCase):
    @staticmethod
    def _parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="synthetic")
        commands = parser.add_subparsers(dest="command", required=True)

        inspect_parser = commands.add_parser("inspect", aliases=["i"])
        inspect_parser.add_argument("--dry-run", action="store_true")
        inspect_parser.set_defaults(func=_handler)

        write_parser = commands.add_parser("write", aliases=["w"])
        write_parser.add_argument("--approve", action="store_true")
        write_parser.add_argument("--dry-run", action="store_true")
        write_parser.add_argument("--target")
        write_parser.add_argument(
            "--private-input",
            default="not_projected_private_default",
            help="not_projected_private_help",
        )
        write_parser.set_defaults(func=_handler)

        fixed_parser = commands.add_parser("fixed", aliases=["f"])
        fixed_parser.add_argument("--approve", action="store_true")
        fixed_parser.set_defaults(func=_handler)

        plain_parser = commands.add_parser("plain")
        plain_parser.set_defaults(func=_handler)

        derive_parser = commands.add_parser("derive", aliases=["d"])
        derive_commands = derive_parser.add_subparsers(
            dest="derive_command",
            required=True,
        )
        capture_parser = derive_commands.add_parser(
            "capture",
            aliases=["c"],
        )
        capture_parser.add_argument("--approve", action="store_true")
        capture_parser.add_argument("--dry-run", action="store_true")
        capture_parser.set_defaults(func=_handler)

        status_parser = derive_commands.add_parser("status", aliases=["s"])
        status_parser.add_argument("--dry-run", action="store_true")
        status_parser.set_defaults(func=_handler)
        return parser

    def test_inventory_classifies_only_exposed_parser_facts(self) -> None:
        inventory = command_status.build_command_status_inventory(
            self._parser(),
            frozenset({"fixed", "derive", "plain", "w"}),
        )
        commands = {
            command["canonical_path"]: command
            for command in inventory["commands"]
        }

        self.assertEqual(
            sorted(commands),
            [
                "derive capture",
                "derive status",
                "fixed",
                "inspect",
                "plain",
                "write",
            ],
        )
        self.assertNotIn("derive", commands)
        self.assertEqual(
            commands["write"]["approval_status"],
            command_status.APPROVAL_AVAILABLE,
        )
        self.assertEqual(
            commands["fixed"]["approval_status"],
            command_status.APPROVAL_FIXED_CLOSED,
        )
        self.assertEqual(
            commands["fixed"]["approval_reason_code"],
            command_status.COMPOUND_APPROVAL_REASON_CODE,
        )
        self.assertEqual(
            commands["derive capture"]["approval_status"],
            command_status.APPROVAL_FIXED_CLOSED,
        )
        self.assertEqual(
            commands["inspect"]["approval_status"],
            command_status.APPROVAL_NOT_EXPOSED,
        )
        self.assertEqual(
            commands["plain"]["approval_status"],
            command_status.APPROVAL_NOT_EXPOSED,
        )
        self.assertIsNone(commands["plain"]["approval_reason_code"])
        self.assertTrue(
            all(command["approval_scope"] is None for command in commands.values())
        )
        self.assertTrue(commands["inspect"]["dry_run_exposed"])
        self.assertFalse(commands["plain"]["dry_run_exposed"])
        self.assertTrue(
            all(
                command["invocation_surface_available"]
                for command in commands.values()
            )
        )

    def test_nested_aliases_cover_every_invocation_path(self) -> None:
        inventory = command_status.build_command_status_inventory(
            self._parser(),
            frozenset(),
        )
        commands = {
            command["canonical_path"]: command
            for command in inventory["commands"]
        }
        self.assertEqual(
            commands["derive capture"]["alias_paths"],
            ["d c", "d capture", "derive c"],
        )
        self.assertEqual(
            commands["derive status"]["alias_paths"],
            ["d s", "d status", "derive s"],
        )
        self.assertEqual(commands["write"]["alias_paths"], ["w"])

    def test_parser_declared_approval_scope_is_bounded_and_content_free(self) -> None:
        parser = self._parser()
        write_parser = command_status._subparser_actions(parser)[0].choices[
            "write"
        ]
        write_parser.set_defaults(
            _wom_approval_scope={
                "kind": "argument_value_allowlist",
                "argument": "--target",
                "allowed_values": ["safe-target"],
                "outside_scope_status": "approval_fixed_closed",
                "outside_scope_reason_code": (
                    command_status.COMPOUND_APPROVAL_REASON_CODE
                ),
            }
        )
        inventory = command_status.build_command_status_inventory(
            parser,
            frozenset(),
        )
        commands = {
            row["canonical_path"]: row for row in inventory["commands"]
        }
        self.assertEqual(
            commands["write"]["approval_scope"]["allowed_values"],
            ["safe-target"],
        )
        self.assertEqual(
            inventory["counts"]["conditional_approval_command_count"],
            1,
        )

        write_parser.set_defaults(
            _wom_approval_scope={
                "kind": "argument_value_allowlist",
                "argument": "--target",
                "allowed_values": ["C:/PRIVATE/not-a-safe-code"],
                "outside_scope_status": "approval_fixed_closed",
                "outside_scope_reason_code": (
                    command_status.COMPOUND_APPROVAL_REASON_CODE
                ),
            }
        )
        with self.assertRaisesRegex(
            ValueError,
            "command_approval_scope_invalid",
        ):
            command_status.build_command_status_inventory(
                parser,
                frozenset(),
            )

    def test_parser_declared_exactly_one_flag_scope_is_bounded(self) -> None:
        parser = self._parser()
        write_parser = command_status._subparser_actions(parser)[0].choices[
            "write"
        ]
        write_parser.set_defaults(
            _wom_approval_scope={
                "kind": "argument_flag_exactly_one_allowlist",
                "allowed_flags": ["--approve", "--dry-run"],
                "outside_scope_status": "approval_fixed_closed",
                "outside_scope_reason_code": (
                    command_status.COMPOUND_APPROVAL_REASON_CODE
                ),
            }
        )
        inventory = command_status.build_command_status_inventory(
            parser,
            frozenset(),
        )
        row = next(
            item for item in inventory["commands"]
            if item["canonical_path"] == "write"
        )
        self.assertEqual(
            row["approval_scope"],
            {
                "kind": "argument_flag_exactly_one_allowlist",
                "allowed_flags": ["--approve", "--dry-run"],
                "outside_scope_status": "approval_fixed_closed",
                "outside_scope_reason_code": (
                    command_status.COMPOUND_APPROVAL_REASON_CODE
                ),
            },
        )

    def test_parser_declared_any_flag_scope_is_bounded(self) -> None:
        parser = self._parser()
        write_parser = command_status._subparser_actions(parser)[0].choices[
            "write"
        ]
        write_parser.set_defaults(
            _wom_approval_scope={
                "kind": "argument_flag_any_allowlist",
                "allowed_flags": ["--approve", "--dry-run"],
                "outside_scope_status": "approval_fixed_closed",
                "outside_scope_reason_code": (
                    command_status.COMPOUND_APPROVAL_REASON_CODE
                ),
            }
        )
        inventory = command_status.build_command_status_inventory(
            parser,
            frozenset(),
        )
        row = next(
            item for item in inventory["commands"]
            if item["canonical_path"] == "write"
        )
        self.assertEqual(
            row["approval_scope"],
            {
                "kind": "argument_flag_any_allowlist",
                "allowed_flags": ["--approve", "--dry-run"],
                "outside_scope_status": "approval_fixed_closed",
                "outside_scope_reason_code": (
                    command_status.COMPOUND_APPROVAL_REASON_CODE
                ),
            },
        )

    def test_counts_are_complete_and_output_is_deterministic_json(self) -> None:
        first = command_status.build_command_status_inventory(
            self._parser(),
            frozenset({"fixed", "derive capture", "plain"}),
        )
        second = command_status.build_command_status_inventory(
            self._parser(),
            frozenset({"plain", "derive capture", "fixed"}),
        )
        self.assertEqual(first, second)
        rendered = json.dumps(first, sort_keys=True)
        self.assertNotIn("not_projected_private_default", rendered)
        self.assertNotIn("not_projected_private_help", rendered)
        self.assertNotIn("read_only", rendered)

        counts = first["counts"]
        status_counts = counts["approval_status_counts"]
        self.assertEqual(counts["total_command_count"], 6)
        self.assertEqual(counts["canonical_executable_command_count"], 6)
        self.assertEqual(sum(status_counts.values()), 6)
        self.assertEqual(
            status_counts,
            {
                command_status.APPROVAL_AVAILABLE: 1,
                command_status.APPROVAL_FIXED_CLOSED: 2,
                command_status.APPROVAL_NOT_EXPOSED: 3,
            },
        )
        self.assertEqual(counts["approval_available_command_count"], 1)
        self.assertEqual(counts["approval_fixed_closed_command_count"], 2)
        self.assertEqual(counts["approval_not_exposed_command_count"], 3)
        self.assertEqual(counts["conditional_approval_command_count"], 0)
        self.assertEqual(
            counts["approval_available_command_count"]
            + counts["approval_fixed_closed_command_count"]
            + counts["approval_not_exposed_command_count"],
            counts["total_command_count"],
        )
        self.assertEqual(counts["dry_run_exposed_command_count"], 4)
        self.assertEqual(counts["alias_invocation_path_count"], 9)
        self.assertEqual(counts["invocation_path_count"], 15)
        self.assertEqual(counts["matched_fixed_closed_command_count"], 2)
        self.assertEqual(counts["unmatched_fixed_closed_command_count"], 1)
        canonical_paths = [
            command["canonical_path"] for command in first["commands"]
        ]
        self.assertEqual(canonical_paths, sorted(canonical_paths))
        self.assertFalse(first["prerequisites_evaluated"])
        self.assertFalse(first["external_effects_performed"])


class CommandStatusArchiveParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inventory = command_status.build_command_status_inventory(
            archive_cli.build_parser(),
            archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS,
        )

    def test_every_current_fixed_closed_command_is_classified(self) -> None:
        commands = {
            command["canonical_path"]: command
            for command in self.inventory["commands"]
        }
        self.assertEqual(
            self.inventory["counts"][
                "matched_fixed_closed_command_count"
            ],
            len(archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS),
        )
        self.assertEqual(
            self.inventory["counts"][
                "unmatched_fixed_closed_command_count"
            ],
            0,
        )
        for command_name in archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS:
            with self.subTest(command=command_name):
                self.assertEqual(
                    commands[command_name]["approval_status"],
                    command_status.APPROVAL_FIXED_CLOSED,
                )
                self.assertEqual(
                    commands[command_name]["approval_reason_code"],
                    command_status.COMPOUND_APPROVAL_REASON_CODE,
                )

    def test_archive_inventory_has_complete_stable_coverage(self) -> None:
        commands = self.inventory["commands"]
        counts = self.inventory["counts"]
        canonical_paths = [command["canonical_path"] for command in commands]
        status_counts = counts["approval_status_counts"]

        self.assertEqual(len(commands), len(set(canonical_paths)))
        self.assertEqual(canonical_paths, sorted(canonical_paths))
        self.assertEqual(
            counts["canonical_executable_command_count"],
            len(commands),
        )
        self.assertEqual(sum(status_counts.values()), len(commands))
        self.assertEqual(
            counts["approval_available_command_count"]
            + counts["approval_fixed_closed_command_count"]
            + counts["approval_not_exposed_command_count"],
            counts["total_command_count"],
        )
        self.assertTrue(
            all(
                command["invocation_surface_available"]
                for command in commands
            )
        )
        self.assertIn("derive-text capture", canonical_paths)
        self.assertNotIn("derive-text", canonical_paths)
        self.assertFalse(self.inventory["prerequisites_evaluated"])
        self.assertFalse(self.inventory["external_effects_performed"])

    def test_archive_inventory_validates_against_public_schema(self) -> None:
        schema_path = (
            Path(__file__).resolve().parents[1]
            / "schemas"
            / "command-approval-status-inventory-v0.2.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        errors = sorted(
            Draft202012Validator(schema).iter_errors(self.inventory),
            key=lambda error: list(error.absolute_path),
        )
        self.assertEqual(errors, [])

    def test_capabilities_machine_exposes_complete_approval_inventory(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = archive_cli.main(["capabilities", "--machine"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        exposed = payload["data"]["approval_status_inventory"]
        self.assertEqual(exposed, self.inventory)
        by_path = {
            command["canonical_path"]: command
            for command in exposed["commands"]
        }
        self.assertEqual(
            by_path["zettel-objet-link"]["approval_status"],
            command_status.APPROVAL_AVAILABLE,
        )
        self.assertEqual(
            by_path["project-version-update"]["approval_status"],
            command_status.APPROVAL_AVAILABLE,
        )
        self.assertEqual(
            by_path["object-storage"]["approval_status"],
            command_status.APPROVAL_AVAILABLE,
        )
        self.assertEqual(
            by_path["git-backup-reconcile-plan"]["approval_status"],
            command_status.APPROVAL_AVAILABLE,
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
            by_path["object-storage-adopt-existing"]["approval_scope"],
            {
                "kind": "argument_flag_exactly_one_allowlist",
                "allowed_flags": ["--formal-adoption", "--preserve-local-only"],
                "outside_scope_status": "approval_fixed_closed",
                "outside_scope_reason_code": (
                    "compound_exact_human_approval_binding_required"
                ),
            },
        )
        self.assertEqual(
            by_path["relation-candidate-decide"]["approval_scope"],
            {
                "kind": "argument_value_allowlist",
                "argument": "--decision",
                "allowed_values": ["reject"],
                "outside_scope_status": "approval_fixed_closed",
                "outside_scope_reason_code": (
                    "compound_exact_human_approval_binding_required"
                ),
            },
        )
        expected_local_recovery_scopes = {
            "objet-capture": ["--exact-local"],
            "objet-capture-selection": ["--exact-existing-intake"],
            "revert-edge": ["--exact-local"],
            "external-locator-record": [
                "--all-markup-receipts",
                "--markup-receipt",
                "--resume-recovery",
                "--revert-recovery",
                "--source-mirror",
            ],
            "zet-title-remap-write": [
                "--resume-recovery",
                "--revert-recovery",
                "--source-mirror",
            ],
            "zet-title-remap-revert": [
                "--field-local",
                "--resume-recovery",
                "--revert-recovery",
            ],
        }
        for command, allowed_flags in expected_local_recovery_scopes.items():
            with self.subTest(command=command):
                self.assertEqual(
                    by_path[command]["approval_scope"],
                    {
                        "kind": "argument_flag_any_allowlist",
                        "allowed_flags": allowed_flags,
                        "outside_scope_status": "approval_fixed_closed",
                        "outside_scope_reason_code": (
                            "compound_exact_human_approval_binding_required"
                        ),
                    },
                )
        self.assertEqual(
            exposed["counts"]["conditional_approval_command_count"],
            9,
        )


if __name__ == "__main__":
    unittest.main()
