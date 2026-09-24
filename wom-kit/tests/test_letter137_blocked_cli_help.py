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
            "imap-mailbox-adapter-manifest-write",
            "imap-mailbox-header-metadata-scan",
            "onboard",
            "runtime-skill-install",
            "runtime-skill-uninstall",
            "tiro-lossless-recovery-fetch-run",
        }
        self.assertEqual(
            len(archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS),
            17,
        )
        for exact_batch_command in (
            "source-intake-batch",
            "objet-capture-batch",
            # 2026-09-24 reopen (58-writer triage, group 1).
            "remint-reconcile",
            "retire-draft-reconcile",
            # 2026-09-24 reopen (triage group 2).
            "ai-scratch-gc",
            "zet-catalog-pass-cleanup",
            # 2026-09-24 reopen (triage group 3).
            "markup-normalization",
            "markup-normalization-recovery",
            "markup-normalization-revert",
            "zettel-objet-link-revert",
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
        self.assertNotIn(  # reopened in v0.4.40 (triage group 3)
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
        # v0.4.21 reopened zet-revision-write; its plan contract says so while
        # the validation digest still grants no authority.
        with self.assertRaises(ValueError):
            command_status.compound_approval_fixed_closed_plan_contract(
                "zet-revision-plan"
            )
        plan_contract = command_status.exact_approval_available_plan_contract(
            "zet-revision-write"
        )
        self.assertEqual(plan_contract["approval_status"], "approval_available")
        self.assertTrue(plan_contract["approved_write_implemented"])
        self.assertFalse(plan_contract["actionable_handoff_available"])
        self.assertFalse(plan_contract["validation_digest_is_approval_authority"])

        rendered = " ".join(
            self.subcommands.choices["zet-revision-plan"].format_help().split()
        )
        self.assertIn("approval_available", rendered)
        self.assertNotIn("approval_fixed_closed", rendered)
        self.assertIn("validation evidence only", rendered)

    def test_installed_module_help_keeps_plan_and_writer_closure_visible(self) -> None:
        for command_name, expected in (
            ("zet-revision-plan", "approval_available"),
            ("zet-revision-write", "exact human approval"),
            ("zet-revision-restore-write", "exact-byte"),
            ("remint-reconcile", "exact human approval"),
            ("remint-reconcile-batch", "exact human approval"),
            ("import-external", f"Unavailable in v{archive_cli.__version__}"),
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
                    " ".join((completed.stdout + completed.stderr).split()),
                )


if __name__ == "__main__":
    unittest.main()
