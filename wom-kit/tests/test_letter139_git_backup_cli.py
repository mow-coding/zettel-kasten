from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import archive_cli


PLAN_SHA256 = "sha256:" + "1" * 64
HIDDEN_EFFECT_SET_SHA256 = "sha256:" + "2" * 64
LOCAL_HEAD_OID = "3" * 40
REMOTE_OID = "4" * 40


class Letter139GitBackupCliTests(unittest.TestCase):
    @staticmethod
    def run_cli(values: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = archive_cli.main(values)
        return int(code), stdout.getvalue(), stderr.getvalue()

    @staticmethod
    def selected_parser(command: str):
        parser = archive_cli.build_parser()
        subparsers = next(
            action
            for action in parser._actions
            if isinstance(action, archive_cli.argparse._SubParsersAction)
        )
        return subparsers.choices[command]

    def test_plan_is_json_only_has_no_approve_and_uses_bounded_defaults(self) -> None:
        parser = self.selected_parser("git-backup-plan")
        option_strings = {
            option
            for action in parser._actions
            for option in action.option_strings
        }
        self.assertNotIn("--approve", option_strings)
        self.assertIn("--dry-run", option_strings)

        args = parser.parse_args(["PRIVATE_ROOT", "--dry-run"])
        self.assertEqual(args.format, "json")
        self.assertEqual(args.remote, "origin")
        self.assertIsNone(args.branch)
        self.assertEqual(
            args.max_changes,
            archive_cli.git_backup_planning.GIT_BACKUP_PLAN_DEFAULT_MAX_CHANGES,
        )
        self.assertEqual(
            args.max_changed_bytes,
            archive_cli.git_backup_planning.GIT_BACKUP_PLAN_DEFAULT_MAX_CHANGED_BYTES,
        )

        format_action = next(
            action for action in parser._actions if "--format" in action.option_strings
        )
        self.assertEqual(format_action.choices, ["json"])
        help_text = parser.format_help().lower()
        self.assertIn("no writer is available", help_text)
        self.assertNotIn("commit and push", help_text)

    def test_plan_forwards_only_read_only_arguments_and_prints_result(self) -> None:
        private_root = "C:/PRIVATE_ARCHIVE_LETTER139"
        observed: dict[str, object] = {}
        result = {
            "schema": "wom-kit/git-backup-plan/v0.1",
            "ok": True,
            "dry_run": True,
            "ready_for_write": False,
            "writer_available": False,
            "would_change": [],
        }

        def fake_plan(root: Path, **kwargs: object) -> dict[str, object]:
            observed["root"] = root
            observed.update(kwargs)
            return result

        with mock.patch.object(
            archive_cli.git_backup_planning,
            "git_backup_plan",
            side_effect=fake_plan,
            create=True,
        ):
            code, stdout, stderr = self.run_cli(
                [
                    "git-backup-plan",
                    private_root,
                    "--remote",
                    "backup",
                    "--branch",
                    "main",
                    "--max-changes",
                    "37",
                    "--max-changed-bytes",
                    "4096",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(code, 0, stdout)
        self.assertEqual(stderr, "")
        self.assertEqual(json.loads(stdout), result)
        self.assertNotIn(private_root, stdout)
        self.assertEqual(
            observed,
            {
                "root": Path(private_root),
                "remote_name": "backup",
                "branch": "main",
                "max_changes": 37,
                "max_changed_bytes": 4096,
                "dry_run": True,
            },
        )

    def test_reconcile_requires_and_forwards_all_review_bindings(self) -> None:
        private_root = "C:/PRIVATE_RECONCILE_ARCHIVE"
        observed: dict[str, object] = {}
        result = {
            "schema": "wom-kit/git-backup-reconcile-plan/v0.1",
            "ok": True,
            "dry_run": True,
            "ready_for_write": False,
            "writer_available": False,
            "would_change": [],
        }

        def fake_reconcile(root: Path, **kwargs: object) -> dict[str, object]:
            observed["root"] = root
            observed.update(kwargs)
            return result

        with mock.patch.object(
            archive_cli.git_backup_planning,
            "git_backup_reconcile_plan",
            side_effect=fake_reconcile,
            create=True,
        ):
            code, stdout, stderr = self.run_cli(
                [
                    "git-backup-reconcile-plan",
                    private_root,
                    "--expected-plan-sha256",
                    PLAN_SHA256,
                    "--expected-hidden-effect-set-sha256",
                    HIDDEN_EFFECT_SET_SHA256,
                    "--expected-local-head-oid",
                    LOCAL_HEAD_OID,
                    "--expected-remote-oid",
                    REMOTE_OID,
                    "--remote",
                    "mirror",
                    "--branch",
                    "release",
                    "--max-changes",
                    "41",
                    "--max-changed-bytes",
                    "8192",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(code, 0, stdout)
        self.assertEqual(stderr, "")
        self.assertEqual(json.loads(stdout), result)
        self.assertNotIn(private_root, stdout)
        self.assertEqual(
            observed,
            {
                "root": Path(private_root),
                "expected_plan_sha256": PLAN_SHA256,
                "expected_hidden_effect_set_sha256": HIDDEN_EFFECT_SET_SHA256,
                "expected_local_head_oid": LOCAL_HEAD_OID,
                "expected_remote_oid": REMOTE_OID,
                "remote_name": "mirror",
                "branch": "release",
                "max_changes": 41,
                "max_changed_bytes": 8192,
                "dry_run": True,
            },
        )

    def test_missing_dry_run_fails_closed_without_calling_core(self) -> None:
        private_root = "C:/PRIVATE_DRY_RUN_REQUIRED"
        cases = (
            (
                "git-backup-plan",
                ["git-backup-plan", private_root, "--format", "json"],
                "git_backup_plan",
                "git_backup_plan_dry_run_required",
            ),
            (
                "git-backup-reconcile-plan",
                [
                    "git-backup-reconcile-plan",
                    private_root,
                    "--expected-plan-sha256",
                    PLAN_SHA256,
                    "--format",
                    "json",
                ],
                "git_backup_reconcile_plan",
                "git_backup_reconcile_plan_dry_run_required",
            ),
        )
        for command, argv, api_name, reason_code in cases:
            with self.subTest(command=command):
                core = mock.Mock()
                with mock.patch.object(
                    archive_cli.git_backup_planning,
                    api_name,
                    core,
                    create=True,
                ):
                    code, stdout, stderr = self.run_cli(argv)
                self.assertEqual(code, 1)
                self.assertEqual(stderr, "")
                core.assert_not_called()
                self.assertNotIn(private_root, stdout)
                payload = json.loads(stdout)
                self.assertFalse(payload["dry_run"])
                self.assertEqual(payload["reason_codes"], [reason_code])
                self.assertEqual(payload["effects_state"], "none")
                self.assertEqual(payload["would_change"], [])
                self.assertEqual(payload["files_written"], [])
                self.assertFalse(payload["private_values_echoed"])

    def test_core_exception_is_sanitized_without_path_or_secret_echo(self) -> None:
        private_root = "C:/PRIVATE_EXCEPTION_ARCHIVE"
        private_secret = "LETTER139_PRIVATE_CANARY_VALUE"
        with mock.patch.object(
            archive_cli.git_backup_planning,
            "git_backup_plan",
            side_effect=OSError(f"{private_root}/{private_secret}"),
            create=True,
        ):
            code, stdout, stderr = self.run_cli(
                [
                    "git-backup-plan",
                    private_root,
                    "--remote",
                    private_secret,
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        self.assertNotIn(private_root, stdout)
        self.assertNotIn(private_secret, stdout)
        payload = json.loads(stdout)
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["error_class"], "inspection")
        self.assertEqual(
            payload["reason_codes"],
            ["git_backup_plan_inspection_unavailable"],
        )
        self.assertFalse(payload["private_values_echoed"])

    def test_reconcile_missing_plan_and_unknown_approve_are_privacy_safe(self) -> None:
        private_root = "C:/PRIVATE_ARGUMENT_ARCHIVE"
        private_remote = "PRIVATE_REMOTE_CANARY"
        cases = (
            [
                "git-backup-reconcile-plan",
                private_root,
                "--remote",
                private_remote,
                "--dry-run",
                "--format",
                "json",
            ],
            [
                "git-backup-plan",
                private_root,
                "--remote",
                private_remote,
                "--approve",
                "--format",
                "json",
            ],
        )
        for argv in cases:
            with self.subTest(command=argv[0]):
                code, stdout, stderr = self.run_cli(argv)
                self.assertEqual(code, 2)
                self.assertEqual(stderr, "")
                self.assertNotIn(private_root, stdout)
                self.assertNotIn(private_remote, stdout)
                payload = json.loads(stdout)
                self.assertEqual(payload["schema"], "wom-kit/cli-error/v0.1")
                self.assertEqual(payload["effects_state"], "none")
                self.assertEqual(payload["files_written"], [])
                self.assertFalse(payload["private_values_echoed"])

    def test_blocked_core_result_is_preserved_and_exits_nonzero(self) -> None:
        result = {
            "schema": "wom-kit/git-backup-plan/v0.1",
            "ok": False,
            "state": "blocked",
            "reason_codes": ["active_git_operation_detected"],
            "ready_for_write": False,
            "writer_available": False,
            "would_change": [],
        }
        with mock.patch.object(
            archive_cli.git_backup_planning,
            "git_backup_plan",
            return_value=result,
            create=True,
        ):
            code, stdout, stderr = self.run_cli(
                ["git-backup-plan", "PRIVATE_ROOT", "--dry-run"]
            )

        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        self.assertEqual(json.loads(stdout), result)

    def test_existing_reconcile_family_routes_exact_approve_without_new_command(self) -> None:
        parser = archive_cli.build_parser()
        subparsers = next(
            action
            for action in parser._actions
            if isinstance(action, archive_cli.argparse._SubParsersAction)
        )
        self.assertNotIn("git-backup-apply", subparsers.choices)
        reconcile = subparsers.choices["git-backup-reconcile-plan"]
        options = {
            option
            for action in reconcile._actions
            for option in action.option_strings
        }
        self.assertTrue(
            {
                "--selection-manifest",
                "--approve",
                "--reviewed-by",
                "--resume-approval-id",
                "--expected-manifest-sha256",
                "--progress",
            }.issubset(options)
        )

        private_root = "C:/PRIVATE_WRITER_ROOT"
        private_selection = "C:/PRIVATE_SELECTION.json"
        prepared = object()
        result = {
            "schema": "wom-kit/exact-operation-result/v1",
            "ok": True,
            "lifecycle_action": "git_backup_exact_apply",
            "private_values_echoed": False,
        }
        with (
            mock.patch.object(
                archive_cli.git_backup_writer,
                "prepare_git_backup",
                return_value=prepared,
            ) as prepare,
            mock.patch.object(
                archive_cli.git_backup_writer,
                "execute_git_backup",
                return_value=result,
            ) as execute,
        ):
            code, stdout, stderr = self.run_cli(
                [
                    "git-backup-reconcile-plan",
                    private_root,
                    "--expected-plan-sha256",
                    PLAN_SHA256,
                    "--selection-manifest",
                    private_selection,
                    "--credential-mode",
                    "stored",
                    "--approve",
                    "--reviewed-by",
                    "person:operator",
                ]
            )
        self.assertEqual(code, 0, stdout)
        self.assertEqual(stderr, "")
        self.assertEqual(json.loads(stdout), result)
        self.assertNotIn(private_root, stdout)
        self.assertNotIn(private_selection, stdout)
        prepare.assert_called_once_with(
            Path(private_root),
            expected_plan_sha256=PLAN_SHA256,
            selection_manifest_path=Path(private_selection),
            remote_name="origin",
            branch=None,
            credential_mode="stored",
            max_changes=(
                archive_cli.git_backup_planning.GIT_BACKUP_PLAN_DEFAULT_MAX_CHANGES
            ),
            max_changed_bytes=(
                archive_cli.git_backup_planning.GIT_BACKUP_PLAN_DEFAULT_MAX_CHANGED_BYTES
            ),
            progress_hook=None,
        )
        execute.assert_called_once_with(
            prepared,
            selection_manifest_path=Path(private_selection),
            reviewer_claim="person:operator",
            progress_hook=None,
        )

    def test_reconcile_resume_loads_exact_private_bundle_and_reuses_started_claim(self) -> None:
        manifest_sha256 = "sha256:" + "8" * 64

        class Prepared:
            expected_plan_sha256 = PLAN_SHA256

        prepared = Prepared()
        result = {
            "ok": True,
            "lifecycle_action": "git_backup_exact_apply",
            "private_values_echoed": False,
        }
        with (
            mock.patch.object(
                archive_cli.git_backup_writer,
                "load_private_git_backup_bundle",
                return_value=prepared,
            ) as load,
            mock.patch.object(
                archive_cli.git_backup_writer,
                "resume_git_backup",
                return_value=result,
            ) as resume,
        ):
            code, stdout, stderr = self.run_cli(
                [
                    "git-backup-reconcile-plan",
                    "C:/PRIVATE_RESUME_ROOT",
                    "--expected-plan-sha256",
                    PLAN_SHA256,
                    "--expected-manifest-sha256",
                    manifest_sha256,
                    "--resume-approval-id",
                    "approval_" + "a" * 32,
                    "--reviewed-by",
                    "person:operator",
                ]
            )
        self.assertEqual(code, 0, stdout)
        self.assertEqual(stderr, "")
        self.assertEqual(json.loads(stdout), result)
        load.assert_called_once_with(
            Path("C:/PRIVATE_RESUME_ROOT"),
            manifest_sha256=manifest_sha256,
        )
        resume.assert_called_once_with(
            prepared,
            reviewer_claim="person:operator",
            approval_id="approval_" + "a" * 32,
            progress_hook=None,
        )

    def test_writer_exception_is_private_and_reports_unknown_effects(self) -> None:
        prepared = object()
        private_canary = "C:/PRIVATE_WRITE_CANARY/secret-token"
        with (
            mock.patch.object(
                archive_cli.git_backup_writer,
                "prepare_git_backup",
                return_value=prepared,
            ),
            mock.patch.object(
                archive_cli.git_backup_writer,
                "execute_git_backup",
                side_effect=RuntimeError(private_canary),
            ),
        ):
            code, stdout, stderr = self.run_cli(
                [
                    "git-backup-reconcile-plan",
                    "C:/PRIVATE_ROOT",
                    "--expected-plan-sha256",
                    PLAN_SHA256,
                    "--selection-manifest",
                    "C:/PRIVATE_SELECTION.json",
                    "--credential-mode",
                    "stored",
                    "--approve",
                    "--reviewed-by",
                    "person:operator",
                ]
            )
        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        self.assertNotIn(private_canary, stdout)
        payload = json.loads(stdout)
        self.assertEqual(payload["error_class"], "execution")
        self.assertEqual(payload["effects_state"], "unknown")
        self.assertEqual(payload["files_written"], [])
        self.assertFalse(payload["private_values_echoed"])


if __name__ == "__main__":
    unittest.main()
