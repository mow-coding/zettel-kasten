from __future__ import annotations

import argparse
import unittest

from wom_kit import archive_cli


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
            79,
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
                command_parser = self.subcommands.choices[command_name]
                action = self._approval_action(command_parser)
                self.assertEqual(
                    action.help,
                    archive_cli.COMPOUND_APPROVAL_BLOCKED_HELP,
                )
                rendered = " ".join(command_parser.format_help().split())
                self.assertIn("Unavailable in v0.4.0", rendered)
                self.assertIn("dry-run, plan, or audit mode only", rendered)

    def test_exact_single_write_flows_keep_their_specific_help(self) -> None:
        exact_commands = {
            "approval-integrity-overlay",
            "create-draft",
            "duplicate-object-reconcile",
            "human-artifact-register-root",
            "human-artifact-transition",
            "mint-zet",
            "promote",
            "retire-draft",
            "source-fidelity-session-evidence",
            "zettel-edge",
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


if __name__ == "__main__":
    unittest.main()
