from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from wom_kit import archive_cli, archive_services, command_status


FIXED_CLOSED_PATHS = (
    "derive-text capture",
    "zet-revision-restore-proposal-from-snapshot",
)


class V0412FixedCloseSurfaceTruthTests(unittest.TestCase):
    def inventory(self) -> dict[str, object]:
        return command_status.build_command_status_inventory(
            archive_cli.build_parser(),
            archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS,
        )

    def help_text(self, argv: list[str]) -> str:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with self.assertRaises(SystemExit) as raised:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                archive_cli.build_parser().parse_args([*argv, "--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(stderr.getvalue(), "")
        return stdout.getvalue()

    def test_parser_inventory_and_nested_help_share_fixed_close_truth(self) -> None:
        inventory = self.inventory()
        commands = {
            item["canonical_path"]: item
            for item in inventory["commands"]
        }
        self.assertEqual(
            inventory["counts"]["unmatched_fixed_closed_command_count"],
            0,
        )
        for path in FIXED_CLOSED_PATHS:
            with self.subTest(path=path):
                command = commands[path]
                self.assertEqual(
                    command["approval_status"],
                    command_status.APPROVAL_FIXED_CLOSED,
                )
                self.assertEqual(
                    command["approval_reason_code"],
                    command_status.COMPOUND_APPROVAL_REASON_CODE,
                )

        for argv in (
            ["derive-text", "capture"],
            ["zet-revision-restore-proposal-from-snapshot"],
        ):
            with self.subTest(argv=argv):
                help_text = self.help_text(argv)
                self.assertIn(
                    f"Unavailable in v{archive_cli.__version__}",
                    help_text,
                )
                self.assertIn(
                    "specific exact compound human-approval binding",
                    help_text,
                )

    def test_runtime_refusal_happens_before_archive_or_source_reads(self) -> None:
        missing_root = Path("private-client-root-must-not-be-read")
        derived = archive_services.derived_text_capture_apply(
            missing_root,
            text_file=Path("private-source-must-not-be-read.txt"),
            source_object_id="sha256:" + "a" * 64,
            derivation_kind="ocr",
            tool_name="fixture",
            tool_version="1",
            review_status="human_reviewed",
            reviewed_by="person:fixture",
        )
        restored = (
            archive_services.zet_revision_restore_proposal_from_snapshot(
                missing_root,
                receipt_path="private-receipt-must-not-be-read.json",
                expected_receipt_sha256="sha256:" + "b" * 64,
                dry_run=False,
                approve=True,
            )
        )
        for result in (derived, restored):
            with self.subTest(action=result.get("lifecycle_action")):
                self.assertFalse(result["ok"])
                self.assertEqual(
                    result["blockers"],
                    [command_status.COMPOUND_APPROVAL_REASON_CODE],
                )
                self.assertEqual(result["files_written"], [])
                self.assertFalse(result["private_values_echoed"])


if __name__ == "__main__":
    unittest.main()
