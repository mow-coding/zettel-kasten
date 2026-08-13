from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from typing import Any


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import archive_cli, archive_services, operation_control


class StagedCleanupOutputTests(unittest.TestCase):
    maxDiff = None

    def _copy_sandbox_archive(self, temporary_root: Path) -> Path:
        archive_root = temporary_root / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", archive_root)
        (archive_root / ".wom-sandbox").write_text("sandbox\n", encoding="utf-8")
        (archive_root / "staging" / "incoming").mkdir(parents=True, exist_ok=True)
        return archive_root

    def _source_intake_plan(self, archive_root: Path) -> tuple[str, str]:
        plan = {
            "ok": True,
            "dry_run": True,
            "lifecycle_action": "source_intake_plan",
            "blockers": [],
            "content_access": dict(
                archive_services.SOURCE_INTAKE_CONTENT_ACCESS_EXPECTATIONS
            ),
            "source_refs_for_draft": [],
        }
        relative = "receipts/sources/letter130-output.source-intake-plan.json"
        path = archive_root.joinpath(*relative.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(plan, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return relative, archive_services.sha256_json_value(plan)

    def _capture_private_ordinary_fixture(
        self,
        temporary_root: Path,
    ) -> tuple[Path, set[str]]:
        archive_root = self._copy_sandbox_archive(temporary_root)
        filename = "PRIVATE_LETTER130_CAPTURED_FILENAME_9917.txt"
        body = b"PRIVATE_LETTER130_CAPTURED_BODY_9917"
        staged_relative = f"staging/incoming/{filename}"
        archive_root.joinpath(*staged_relative.split("/")).write_bytes(body)
        digest = hashlib.sha256(body).hexdigest()
        object_id = f"sha256:{digest}"
        plan_path, plan_sha256 = self._source_intake_plan(archive_root)
        archive_id = archive_services.read_archive_id(archive_root)
        selection = {
            "manifest_id": "approved:local-objet-capture:letter130-output",
            "schema": "wom-kit/b4-selection/v0.2",
            "action": "local_objet_capture_approved",
            "archive_id": archive_id,
            "items": [
                {
                    "item_id": "letter130-private-ordinary",
                    "approved": True,
                    "input_kind": "local_path",
                    "staged_path": staged_relative,
                    "approved_object_id": object_id,
                    "source_intake_receipt_path": plan_path,
                    "source_intake_plan_sha256": plan_sha256,
                }
            ],
            "privacy_guards": {
                key: True
                for key in archive_services.OBJET_CAPTURE_REQUIRED_PRIVACY_GUARDS
            },
        }
        selection_path = temporary_root / "PRIVATE_LETTER130_SELECTION_9917.json"
        selection_path.write_text(
            json.dumps(selection, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        applied = archive_services.objet_capture_apply(
            archive_root,
            selection_path,
            reviewed_by="person:letter130-output-test",
        )
        self.assertTrue(applied["ok"], applied)
        self.assertIsInstance(applied.get("receipt_path"), str)

        private_tokens = {
            str(archive_root),
            archive_root.as_posix(),
            str(selection_path),
            selection_path.as_posix(),
            filename,
            staged_relative,
            body.decode("utf-8"),
            digest,
            object_id,
            plan_path,
            str(applied["receipt_path"]),
        }
        return archive_root, private_tokens

    def _add_uncaptured_private_fixture(self, archive_root: Path) -> set[str]:
        filename = "PRIVATE_LETTER130_UNCAPTURED_FILENAME_7731.txt"
        body = b"PRIVATE_LETTER130_UNCAPTURED_BODY_7731"
        staged_relative = f"staging/incoming/{filename}"
        archive_root.joinpath(*staged_relative.split("/")).write_bytes(body)
        digest = hashlib.sha256(body).hexdigest()
        return {
            filename,
            staged_relative,
            body.decode("utf-8"),
            digest,
            f"sha256:{digest}",
        }

    def _run_cli_split(self, args: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = archive_cli.main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def _command_args(
        self,
        archive_root: Path,
        *,
        output: str | None = None,
        progress: bool = False,
    ) -> list[str]:
        args = [
            "staged-cleanup-check",
            str(archive_root),
            "--staged",
            "staging/incoming",
            "--dry-run",
            "--format",
            "json",
        ]
        if progress:
            args.append("--progress")
        if output is not None:
            args.extend(["--output", output])
        return args

    def _assert_content_free(
        self,
        value: Any,
        private_tokens: set[str],
        *,
        saved_or_public_result: bool = True,
    ) -> None:
        rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
        for token in sorted(private_tokens):
            if token:
                self.assertNotIn(token, rendered, f"private token leaked: {token!r}")
        if saved_or_public_result:
            for forbidden_key in (
                "archive_id",
                "files",
                "object_id",
                "receipt_path",
                "staged_folder",
            ):
                self.assertNotIn(f'"{forbidden_key}"', rendered)

    def _assert_completed_operation(
        self,
        archive_root: Path,
        saved: dict[str, Any],
        *,
        expected_safe: bool,
        expected_exit_code: int,
        expected_state: str,
    ) -> dict[str, Any]:
        operation = saved["cli_output_artifact"]["operation"]
        status = operation_control.inspect_operation(
            archive_root,
            operation["operation_ref"],
        )
        self.assertTrue(status["ok"], status)
        self.assertEqual(status["state"], "completed_result_available")
        self.assertTrue(status["terminal"])
        self.assertTrue(status["result"]["available"])
        self.assertTrue(status["result"]["binding_verified"])
        self.assertEqual(status["result"]["exit_code"], expected_exit_code)
        self.assertIs(status["result"]["ok"], expected_safe)
        domain = status["result"]["domain"]
        self.assertEqual(domain["state"], expected_state)
        self.assertIs(domain["safe_to_cleanup"], expected_safe)
        return status

    def test_parser_registers_one_canonical_command_and_one_output_option(self) -> None:
        parser = archive_cli.build_parser()
        subcommands = next(
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        command_parser = subcommands.choices["staged-cleanup-check"]
        names_for_same_parser = [
            name
            for name, candidate in subcommands.choices.items()
            if candidate is command_parser
        ]
        self.assertEqual(names_for_same_parser, ["staged-cleanup-check"])
        output_actions = [
            action
            for action in command_parser._actions
            if "--output" in action.option_strings
        ]
        self.assertEqual(len(output_actions), 1)
        self.assertEqual(output_actions[0].dest, "output")
        parsed = parser.parse_args(
            [
                "staged-cleanup-check",
                "archive-root",
                "--staged",
                "staging/incoming",
                "--dry-run",
                "--output",
                ".wom-scratch/diagnostics/result.json",
            ]
        )
        self.assertEqual(parsed.output, ".wom-scratch/diagnostics/result.json")

    def test_saved_safe_and_unsafe_results_are_content_free_and_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temporary_root = Path(tmp)
            archive_root, private_tokens = self._capture_private_ordinary_fixture(
                temporary_root
            )
            private_output_name = "reviewed-private-page-title"
            safe_relative = (
                ".wom-scratch/diagnostics/"
                f"{private_output_name}.json"
            )

            safe_code, safe_stdout, safe_stderr = self._run_cli_split(
                self._command_args(archive_root, output=safe_relative)
            )

            self.assertEqual(safe_code, 0, safe_stdout + safe_stderr)
            safe_terminal = json.loads(safe_stdout)
            self.assertEqual(
                safe_terminal["lifecycle_action"],
                "staged_cleanup_check_output_summary",
            )
            self.assertEqual(safe_terminal["state"], "safe_to_cleanup")
            self.assertTrue(safe_terminal["safe_to_cleanup"])
            self.assertNotIn("entries", safe_terminal)
            self.assertNotIn("files", safe_terminal)
            self.assertTrue(safe_terminal["output"]["written"])
            self.assertRegex(
                safe_terminal["output"]["output_ref"],
                r"\Acommand-result:[0-9a-f]{32}\Z",
            )
            self.assertFalse(safe_terminal["output"]["path_echoed"])
            self.assertNotIn("path", safe_terminal["output"])
            self.assertNotIn(private_output_name, safe_stdout)
            self.assertNotIn(private_output_name, safe_stderr)
            self._assert_content_free(
                safe_terminal,
                private_tokens,
                saved_or_public_result=False,
            )

            safe_path = archive_root.joinpath(*safe_relative.split("/"))
            self.assertTrue(safe_path.is_file())
            self.assertTrue(safe_path.is_relative_to(archive_root / ".wom-scratch" / "diagnostics"))
            safe_saved_text = safe_path.read_text(encoding="utf-8")
            safe_saved = json.loads(safe_saved_text)
            self.assertEqual(safe_saved["state"], "safe_to_cleanup")
            self.assertTrue(safe_saved["safe_to_cleanup"])
            self.assertEqual(safe_saved["summary"]["preserved"], 1)
            self.assertEqual(safe_saved["summary"]["not_preserved"], 0)
            self.assertEqual(safe_saved["cli_execution"]["status"], "completed")
            self.assertEqual(safe_saved["cli_execution"]["exit_code"], 0)
            self.assertEqual(
                safe_saved["cli_execution"]["exit_code_scope"],
                "command_result_before_terminal_transport",
            )
            self.assertIsNone(safe_saved["cli_execution"]["error"])
            self._assert_content_free(safe_saved, private_tokens)
            self._assert_completed_operation(
                archive_root,
                safe_saved,
                expected_safe=True,
                expected_exit_code=0,
                expected_state="safe_to_cleanup",
            )

            private_tokens |= self._add_uncaptured_private_fixture(archive_root)
            unsafe_relative = ".wom-scratch/diagnostics/letter130-unsafe.json"
            unsafe_code, unsafe_stdout, unsafe_stderr = self._run_cli_split(
                self._command_args(archive_root, output=unsafe_relative)
            )

            self.assertEqual(unsafe_code, 1, unsafe_stdout + unsafe_stderr)
            unsafe_terminal = json.loads(unsafe_stdout)
            self.assertEqual(unsafe_terminal["state"], "not_safe_to_cleanup")
            self.assertFalse(unsafe_terminal["safe_to_cleanup"])
            self.assertIn("staged_entry_not_preserved", unsafe_terminal["reason_codes"])
            self.assertNotIn("entries", unsafe_terminal)
            self.assertNotIn("files", unsafe_terminal)
            self._assert_content_free(
                unsafe_terminal,
                private_tokens,
                saved_or_public_result=False,
            )

            unsafe_path = archive_root.joinpath(*unsafe_relative.split("/"))
            unsafe_saved = json.loads(unsafe_path.read_text(encoding="utf-8"))
            self.assertEqual(unsafe_saved["state"], "not_safe_to_cleanup")
            self.assertFalse(unsafe_saved["safe_to_cleanup"])
            self.assertIn("staged_entry_not_preserved", unsafe_saved["reason_codes"])
            self.assertEqual(unsafe_saved["summary"]["preserved"], 1)
            self.assertEqual(unsafe_saved["summary"]["not_preserved"], 1)
            self.assertEqual(unsafe_saved["cli_execution"]["status"], "completed")
            self.assertEqual(unsafe_saved["cli_execution"]["exit_code"], 1)
            self.assertIsNone(unsafe_saved["cli_execution"]["error"])
            self._assert_content_free(unsafe_saved, private_tokens)
            unsafe_status = self._assert_completed_operation(
                archive_root,
                unsafe_saved,
                expected_safe=False,
                expected_exit_code=1,
                expected_state="not_safe_to_cleanup",
            )
            self.assertIn(
                "staged_entry_not_preserved",
                unsafe_status["result"]["domain"]["reason_codes"],
            )

    def test_no_output_json_keeps_entries_but_never_private_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temporary_root = Path(tmp)
            archive_root, private_tokens = self._capture_private_ordinary_fixture(
                temporary_root
            )
            private_tokens |= self._add_uncaptured_private_fixture(archive_root)

            code, stdout, stderr = self._run_cli_split(
                self._command_args(archive_root)
            )

            self.assertEqual(code, 1, stdout + stderr)
            result = json.loads(stdout)
            self.assertEqual(result["state"], "not_safe_to_cleanup")
            self.assertFalse(result["safe_to_cleanup"])
            self.assertIn("staged_entry_not_preserved", result["reason_codes"])
            self.assertEqual(len(result["entries"]), 2)
            self.assertEqual(
                {entry["status"] for entry in result["entries"]},
                {"preserved", "not_preserved"},
            )
            self.assertNotIn("cli_execution", result)
            self.assertNotIn("cli_output_artifact", result)
            self._assert_content_free(result, private_tokens)
            self.assertFalse((archive_root / ".wom-scratch").exists())

    def test_output_refusals_happen_before_cleanup_service(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temporary_root = Path(tmp)
            archive_root, _private_tokens = self._capture_private_ordinary_fixture(
                temporary_root
            )
            existing_relative = ".wom-scratch/diagnostics/existing.json"
            existing_path = archive_root.joinpath(*existing_relative.split("/"))
            existing_path.parent.mkdir(parents=True, exist_ok=True)
            original_existing_bytes = b"do-not-overwrite\n"
            existing_path.write_bytes(original_existing_bytes)
            cases = (
                ("wrong-prefix", "diagnostics/result.json"),
                (
                    "traversal",
                    ".wom-scratch/diagnostics/../escaped.json",
                ),
                ("no-overwrite", existing_relative),
            )

            for label, output_relative in cases:
                with self.subTest(label=label):
                    with patch.object(
                        archive_cli.archive_services,
                        "staged_cleanup_check",
                    ) as cleanup_service:
                        code, _stdout, _stderr = self._run_cli_split(
                            self._command_args(
                                archive_root,
                                output=output_relative,
                            )
                        )
                    self.assertEqual(code, 1)
                    cleanup_service.assert_not_called()

            self.assertEqual(existing_path.read_bytes(), original_existing_bytes)
            self.assertFalse(
                (archive_root / ".wom-scratch" / "escaped.json").exists()
            )
            self.assertFalse((archive_root / "diagnostics" / "result.json").exists())

    def test_broken_stderr_does_not_change_saved_completion(self) -> None:
        class BrokenTerminal:
            def write(self, _value: str) -> int:
                raise BrokenPipeError("simulated closed stderr")

            def flush(self) -> None:
                raise BrokenPipeError("simulated closed stderr")

        with tempfile.TemporaryDirectory() as tmp:
            temporary_root = Path(tmp)
            archive_root, private_tokens = self._capture_private_ordinary_fixture(
                temporary_root
            )
            output_relative = ".wom-scratch/diagnostics/broken-stderr.json"
            stdout = io.StringIO()
            with (
                redirect_stdout(stdout),
                patch.object(archive_cli.sys, "stderr", BrokenTerminal()),
            ):
                code = archive_cli.main(
                    self._command_args(
                        archive_root,
                        output=output_relative,
                        progress=True,
                    )
                )

            self.assertEqual(code, 0)
            terminal = json.loads(stdout.getvalue())
            self.assertEqual(terminal["state"], "safe_to_cleanup")
            self.assertNotIn("entries", terminal)
            saved = json.loads(
                archive_root.joinpath(*output_relative.split("/")).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(saved["state"], "safe_to_cleanup")
            self.assertTrue(saved["safe_to_cleanup"])
            self.assertEqual(saved["cli_execution"]["status"], "completed")
            self.assertEqual(saved["cli_execution"]["exit_code"], 0)
            self.assertEqual(
                saved["cli_execution"]["terminal_output_delivery"],
                "best_effort_not_observed",
            )
            self._assert_content_free(saved, private_tokens)
            self._assert_completed_operation(
                archive_root,
                saved,
                expected_safe=True,
                expected_exit_code=0,
                expected_state="safe_to_cleanup",
            )


if __name__ == "__main__":
    unittest.main()
