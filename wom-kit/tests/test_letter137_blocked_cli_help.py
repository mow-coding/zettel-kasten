from __future__ import annotations

import argparse
import subprocess
import sys
import unittest

from wom_kit import archive_cli, command_status


class Letter137BlockedCliHelpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = archive_cli.build_parser()
        cls.subcommands = next(
            action
            for action in cls.parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )

    @staticmethod
    def _approval_action(parser: argparse.ArgumentParser) -> argparse.Action:
        matches = [
            action
            for action in parser._actions
            if "--approve" in action.option_strings
        ]
        if len(matches) != 1:
            raise AssertionError("expected exactly one --approve action")
        return matches[0]

    def _command_parser(self, command_path: str) -> argparse.ArgumentParser:
        parser = self.parser
        for segment in command_path.split():
            subcommands = next(
                action
                for action in parser._actions
                if isinstance(action, argparse._SubParsersAction)
            )
            parser = subcommands.choices[segment]
        return parser

    def test_every_fixed_closed_command_has_honest_approval_help(self) -> None:
        expected_additional_public_commands = {
            "credential-keepassxc-write",
            "github-repo",
            "imap-mailbox-adapter-manifest-write",
            "imap-mailbox-header-metadata-scan",
            "notion-objet-manifest-locator-label",
            "onboard",
            "repair-gitignore",
            "restore-drill",
            "runtime-skill-install",
            "runtime-skill-uninstall",
            "scan-source",
            "tiro-lossless-recovery-capture",
            "tiro-lossless-recovery-fetch-run",
            "zet-catalog-pass-cleanup",
        }
        self.assertEqual(
            len(archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS),
            67,
        )
        for exact_batch_command in (
            "source-intake-batch",
            "objet-capture-batch",
        ):
            self.assertNotIn(
                exact_batch_command,
                archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS,
            )
        self.assertNotIn(
            "migrate",
            archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS,
        )
        self.assertNotIn(
            "zettel-objet-link",
            archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS,
        )
        self.assertNotIn(
            "project-version-update",
            archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS,
        )
        self.assertNotIn(
            "object-storage-adopt-existing",
            archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS,
        )
        self.assertNotIn(
            "object-storage",
            archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS,
        )
        self.assertNotIn(
            "objet-capture",
            archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS,
        )
        self.assertNotIn(
            "objet-capture-selection",
            archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS,
        )
        self.assertNotIn(
            "revert-edge",
            archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS,
        )
        self.assertIn(
            "zettel-objet-link-revert",
            archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS,
        )
        self.assertTrue(
            expected_additional_public_commands.issubset(
                archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS
            )
        )
        for command_name in sorted(
            archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS
        ):
            with self.subTest(command=command_name):
                command_parser = self._command_parser(command_name)
                action = self._approval_action(command_parser)
                self.assertEqual(
                    action.help,
                    archive_cli.COMPOUND_APPROVAL_BLOCKED_HELP,
                )
                rendered = " ".join(command_parser.format_help().split())
                self.assertIn(
                    f"Unavailable in v{archive_cli.__version__}",
                    rendered,
                )
                self.assertIn(
                    "dry-run, plan, or audit mode",
                    rendered,
                )

    def test_exact_single_write_flows_keep_their_specific_help(self) -> None:
        exact_commands = {
            "approval-integrity-overlay",
            "create-draft",
            "duplicate-object-reconcile",
            "human-artifact-register-root",
            "human-artifact-transition",
            "mint-zet",
            "promote",
            "project-version-update",
            "object-storage-adopt-existing",
            "object-storage",
            "objet-capture",
            "objet-capture-selection",
            "revert-edge",
            "retire-draft",
            "source-fidelity-session-evidence",
            "migrate",
            "zettel-edge",
            "zettel-objet-link",
        }
        self.assertTrue(
            exact_commands.isdisjoint(
                archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS
            )
        )
        for command_name in sorted(exact_commands):
            with self.subTest(command=command_name):
                command_parser = self.subcommands.choices[command_name]
                action = self._approval_action(command_parser)
                self.assertNotEqual(
                    action.help,
                    archive_cli.COMPOUND_APPROVAL_BLOCKED_HELP,
                )
                self.assertNotIn(
                    "exact compound human-approval binding",
                    str(action.help),
                )
        migrate_help = self._approval_action(
            self.subcommands.choices["migrate"]
        ).help
        self.assertIn("notion-source-properties", str(migrate_help))
        self.assertIn("Every other migration target", str(migrate_help))

    def test_fixed_closed_registry_and_revision_plan_help_share_one_truth(self) -> None:
        self.assertIs(
            archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS,
            command_status.COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS,
        )
        plan_contract = (
            command_status.compound_approval_fixed_closed_plan_contract(
                "zet-revision-plan"
            )
        )
        self.assertEqual(plan_contract["approval_status"], "approval_fixed_closed")
        self.assertFalse(plan_contract["approved_write_implemented"])
        self.assertFalse(plan_contract["actionable_handoff_available"])
        self.assertFalse(plan_contract["validation_digest_is_approval_authority"])

        rendered = " ".join(
            self.subcommands.choices["zet-revision-plan"].format_help().split()
        )
        self.assertIn("approval_fixed_closed", rendered)
        self.assertIn(command_status.COMPOUND_APPROVAL_REASON_CODE, rendered)
        self.assertIn("No actionable approval handoff", rendered)

    def test_installed_module_help_keeps_plan_and_writer_closure_visible(self) -> None:
        for command_name, expected in (
            ("zet-revision-plan", "approval_fixed_closed"),
            ("zet-revision-write", f"Unavailable in v{archive_cli.__version__}"),
            ("discard-draft", f"Unavailable in v{archive_cli.__version__}"),
        ):
            with self.subTest(command=command_name):
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "wom_kit.archive_cli",
                        command_name,
                        "--help",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )
                self.assertEqual(
                    completed.returncode,
                    0,
                    completed.stdout + completed.stderr,
                )
                self.assertIn(
                    expected,
                    completed.stdout + completed.stderr,
                )


if __name__ == "__main__":
    unittest.main()
