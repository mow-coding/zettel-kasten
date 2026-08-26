from __future__ import annotations

import argparse
from copy import deepcopy
import json
import unittest

from wom_kit import command_status


def _handler(_: argparse.Namespace) -> int:
    raise AssertionError("resolver_must_not_execute_handler")


class SuggestedCommandStatusHardeningTests(unittest.TestCase):
    @staticmethod
    def parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="archive")
        commands = parser.add_subparsers(dest="command", required=True)

        repair = commands.add_parser("repair", aliases=["fix"])
        repair.add_argument("archive_root")
        repair.add_argument("--target", required=True, type=lambda _value: 1 / 0)
        repair.add_argument("--dry-run", action="store_true")
        repair.add_argument("--approve", action="store_true")
        repair.set_defaults(
            func=_handler,
            _wom_approval_scope={
                "kind": "argument_value_allowlist",
                "argument": "--target",
                "allowed_values": ["safe-target"],
                "outside_scope_status": command_status.APPROVAL_FIXED_CLOSED,
                "outside_scope_reason_code": (
                    command_status.COMPOUND_APPROVAL_REASON_CODE
                ),
            },
        )

        inspect = commands.add_parser("inspect")
        inspect.add_argument("archive_root")
        inspect.add_argument("--dry-run", action="store_true")
        inspect.set_defaults(func=_handler)
        return parser

    def inventory(self) -> dict[str, object]:
        return command_status.build_command_status_inventory(
            self.parser(),
            frozenset(),
        )

    def test_resolution_explicitly_stops_short_of_full_executability(self) -> None:
        status = command_status.resolve_suggested_command_mode(
            self.inventory(),
            "archive repair <archive-root> --target safe-target --dry-run",
        )

        self.assertEqual(status["resolution_state"], "resolved")
        self.assertEqual(
            status["resolution_scope"],
            "inventory_path_and_requested_mode_only",
        )
        self.assertTrue(status["requested_mode_available"])
        self.assertFalse(status["argument_syntax_evaluated"])
        self.assertIsNone(status["argument_syntax_valid"])
        self.assertEqual(
            status["argument_syntax_reason_code"],
            "suggested_command_trusted_parser_not_supplied",
        )
        self.assertFalse(status["shell_syntax_evaluated"])
        self.assertFalse(status["portable_template_substitution_evaluated"])
        self.assertTrue(status["portable_template_placeholders_present"])
        self.assertFalse(status["prerequisites_evaluated"])
        self.assertFalse(status["full_command_executability_evaluated"])
        self.assertIsNone(status["full_command_executable"])

    def test_trusted_parser_checks_arity_without_types_actions_or_handler(self) -> None:
        parser = self.parser()
        inventory = command_status.build_command_status_inventory(
            parser,
            frozenset(),
        )
        status = command_status.resolve_suggested_command_mode(
            inventory,
            "archive fix <archive-root> --target safe-target --approve",
            trusted_parser=parser,
        )

        self.assertEqual(status["resolution_state"], "resolved")
        self.assertTrue(status["argument_syntax_evaluated"])
        self.assertTrue(status["argument_syntax_valid"])
        self.assertIsNone(status["argument_syntax_reason_code"])
        self.assertTrue(status["requested_mode_available"])
        self.assertFalse(status["external_effects_performed"])

    def test_trusted_parser_rejects_missing_required_argument_content_free(self) -> None:
        parser = self.parser()
        inventory = command_status.build_command_status_inventory(
            parser,
            frozenset(),
        )
        private_marker = "PRIVATE_MISSING_TARGET_VALUE"
        status = command_status.resolve_suggested_command_mode(
            inventory,
            f"archive repair <archive-root> {private_marker} --dry-run",
            trusted_parser=parser,
        )

        self.assertEqual(status["resolution_state"], "unresolved")
        self.assertEqual(
            status["resolution_reason_code"],
            "suggested_command_argument_syntax_invalid",
        )
        self.assertTrue(status["argument_syntax_evaluated"])
        self.assertFalse(status["argument_syntax_valid"])
        self.assertNotIn(private_marker, json.dumps(status, sort_keys=True))

    def test_shell_control_expansion_and_unsafe_templates_are_unresolved(self) -> None:
        inventory = self.inventory()
        unsafe_invocations = (
            "archive inspect <archive-root> --dry-run\nGet-ChildItem",
            "archive inspect <archive-root> --dry-run\u2028Get-ChildItem",
            "archive inspect <archive-root> --dry-run; if ($true) { whoami }",
            "archive inspect <archive-root> --dry-run | Out-File secret.txt",
            "archive inspect <archive-root> --dry-run && whoami",
            "archive inspect $(Get-Content secret.txt) --dry-run",
            "archive inspect ${env:USERPROFILE} --dry-run",
            "archive inspect %USERPROFILE% --dry-run",
            "archive inspect `<archive-root`> --dry-run",
            "archive inspect --% <archive-root> --dry-run",
            "archive inspect <archive-root --dry-run",
            "archive inspect #private --dry-run",
        )

        for invocation in unsafe_invocations:
            with self.subTest(invocation=invocation):
                status = command_status.resolve_suggested_command_mode(
                    inventory,
                    invocation,
                )
                self.assertEqual(status["resolution_state"], "unresolved")
                self.assertFalse(status["portable_invocation_syntax_safe"])
                self.assertFalse(status["shell_syntax_evaluated"])
                self.assertFalse(status["full_command_executability_evaluated"])

    def test_untrusted_inventory_cannot_reflect_private_reason_or_scope(self) -> None:
        private_marker = "PRIVATE_INVENTORY_MARKER"

        private_reason = deepcopy(self.inventory())
        private_reason["commands"][0]["approval_status"] = (
            command_status.APPROVAL_FIXED_CLOSED
        )
        private_reason["commands"][0]["approval_reason_code"] = private_marker
        private_reason["commands"][0]["approval_scope"] = None
        with self.assertRaisesRegex(
            ValueError,
            "^command_status_inventory_invalid$",
        ) as reason_error:
            command_status.resolve_suggested_command_mode(
                private_reason,
                "archive inspect <archive-root> --dry-run",
            )
        self.assertNotIn(private_marker, str(reason_error.exception))

        private_scope = deepcopy(self.inventory())
        repair = next(
            row
            for row in private_scope["commands"]
            if row["canonical_path"] == "repair"
        )
        repair["approval_scope"]["allowed_values"] = [private_marker]
        with self.assertRaisesRegex(
            ValueError,
            "^command_status_inventory_invalid$",
        ) as scope_error:
            command_status.resolve_suggested_command_mode(
                private_scope,
                "archive repair <archive-root> --target safe-target --dry-run",
            )
        self.assertNotIn(private_marker, str(scope_error.exception))

        safe_looking_private_marker = "privateinventorymarker"
        private_scope = deepcopy(self.inventory())
        repair = next(
            row
            for row in private_scope["commands"]
            if row["canonical_path"] == "repair"
        )
        repair["approval_scope"]["allowed_values"] = [
            safe_looking_private_marker
        ]
        status = command_status.resolve_suggested_command_mode(
            private_scope,
            (
                "archive repair <archive-root> --target "
                f"{safe_looking_private_marker} --dry-run"
            ),
        )
        self.assertNotIn(
            safe_looking_private_marker,
            json.dumps(status, sort_keys=True),
        )
        self.assertEqual(
            status["approval_scope"],
            {
                "kind": "argument_value_allowlist",
                "allowlisted_entry_count": 1,
                "values_disclosed": False,
            },
        )

    def test_dry_run_and_same_argument_approval_remain_separate(self) -> None:
        parser = self.parser()
        inventory = command_status.build_command_status_inventory(
            parser,
            frozenset(),
        )
        status = command_status.resolve_suggested_command_mode(
            inventory,
            "archive repair <archive-root> --target unsafe-target --dry-run",
            trusted_parser=parser,
        )

        self.assertTrue(status["requested_mode_available"])
        self.assertFalse(status["approval_mode_available_for_arguments"])
        self.assertEqual(
            status["approval_mode_reason_code_for_arguments"],
            command_status.COMPOUND_APPROVAL_REASON_CODE,
        )


if __name__ == "__main__":
    unittest.main()
