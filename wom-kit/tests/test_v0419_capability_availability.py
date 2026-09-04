from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import unittest
from unittest import mock

from wom_kit import archive_cli, command_status


class V0419CapabilityAvailabilityTests(unittest.TestCase):
    def inventory(self) -> dict[str, object]:
        parser = archive_cli.build_parser()
        return archive_cli._parser_capability_inventory(parser)

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


if __name__ == "__main__":
    unittest.main()
