from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import archive_cli, operation_control


class OperationControlTests(unittest.TestCase):
    def start_journal(
        self,
        root: Path,
        *,
        command: str = "index",
        relative: str = ".wom-scratch/diagnostics/result.json",
    ) -> tuple[operation_control.OperationRunJournal, Path]:
        root.mkdir(parents=True, exist_ok=True)
        journal = operation_control.OperationRunJournal.prepare(
            root,
            output_relative=relative,
            command=command,
            run_id="a" * 32,
        )
        return journal, root.joinpath(*relative.split("/"))

    def write_result(
        self,
        journal: operation_control.OperationRunJournal,
        output_path: Path,
        *,
        ok: bool = True,
        exit_code: int = 0,
    ) -> None:
        payload = {
            "ok": ok,
            "cli_execution": {
                "status": "completed",
                "run_id": journal.run_id,
                "command": journal.command,
                "exit_code": exit_code,
            },
            "cli_output_artifact": {
                "command": journal.command,
                "operation": journal.metadata(),
            },
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def test_terminal_status_revalidates_complete_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            journal, output = self.start_journal(root)
            self.write_result(journal, output)
            self.assertTrue(
                journal.complete(
                    exit_code=0,
                    result_available=True,
                    result_ok=True,
                    result_path=output,
                )
            )

            result = operation_control.inspect_operation(
                root, journal.operation_ref
            )

            self.assertTrue(result["ok"], result)
            self.assertEqual(result["state"], "completed_result_available")
            self.assertTrue(result["terminal"])
            self.assertTrue(result["result"]["available"])
            self.assertTrue(result["result"]["binding_verified"])
            self.assertFalse(result["result"]["domain_truth_verified"])
            rendered = json.dumps(result)
            self.assertNotIn(str(root), rendered)
            self.assertNotIn("result_sha256", rendered)

    def test_missing_or_tampered_result_fails_closed(self) -> None:
        for mutation in ("missing", "tampered"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "archive"
                journal, output = self.start_journal(root)
                self.write_result(journal, output)
                self.assertTrue(
                    journal.complete(
                        exit_code=0,
                        result_available=True,
                        result_ok=True,
                        result_path=output,
                    )
                )
                if mutation == "missing":
                    output.unlink()
                else:
                    output.write_text("{}\n", encoding="utf-8")

                result = operation_control.inspect_operation(
                    root, journal.operation_ref
                )

                self.assertFalse(result["ok"], result)
                self.assertEqual(result["state"], "recovery_required")
                self.assertTrue(result["control"]["recovery_required"])
                self.assertIn(
                    "operation_result_missing_or_unverifiable",
                    result["blockers"],
                )

    def test_stale_nonterminal_reconciles_only_matching_complete_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            journal, output = self.start_journal(root)
            self.write_result(journal, output)
            journal.close()

            with patch.object(operation_control, "HEARTBEAT_STALE_SECONDS", -1):
                result = operation_control.inspect_operation(
                    root, journal.operation_ref
                )

            self.assertTrue(result["ok"], result)
            self.assertTrue(result["terminal"])
            self.assertEqual(
                result["terminal_source"], "complete_output_reconciliation"
            )
            self.assertTrue(result["result"]["binding_verified"])

    def test_stale_without_output_is_not_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            journal, _output = self.start_journal(root)
            journal.close()

            with patch.object(operation_control, "HEARTBEAT_STALE_SECONDS", -1):
                result = operation_control.inspect_operation(
                    root, journal.operation_ref
                )

            self.assertFalse(result["ok"], result)
            self.assertEqual(result["blockers"], ["operation_observation_stale"])

    def test_torn_tampered_and_future_journals_fail_closed(self) -> None:
        for mutation in ("torn", "tampered", "future"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "archive"
                journal, _output = self.start_journal(root)
                journal.close()
                raw = journal.journal_path.read_bytes()
                if mutation == "torn":
                    journal.journal_path.write_bytes(raw + b"{")
                    expected = "operation_journal_torn"
                else:
                    record = json.loads(raw.decode("ascii"))
                    if mutation == "tampered":
                        record["stage"] = "unknown"
                        expected = "operation_journal_invalid"
                    else:
                        record["observed_at"] = "2999-01-01T00:00:00Z"
                        record["record_sha256"] = operation_control._record_digest(record)
                        expected = "operation_journal_future_timestamp"
                    journal.journal_path.write_text(
                        json.dumps(record, sort_keys=True, separators=(",", ":"))
                        + "\n",
                        encoding="ascii",
                    )

                result = operation_control.inspect_operation(
                    root, journal.operation_ref
                )

                self.assertFalse(result["ok"], result)
                self.assertEqual(result["blockers"], [expected])

    def test_copied_journal_is_bound_to_original_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            target = Path(tmp) / "target"
            journal, _output = self.start_journal(source)
            journal.close()
            copied = (
                target
                / ".wom-scratch"
                / "diagnostics"
                / ".operations"
                / journal.journal_path.name
            )
            copied.parent.mkdir(parents=True)
            shutil.copy2(journal.journal_path, copied)

            result = operation_control.inspect_operation(
                target, journal.operation_ref
            )

            self.assertFalse(result["ok"], result)
            self.assertEqual(result["blockers"], ["operation_root_mismatch"])

    def test_wait_deadline_is_not_cancel_or_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            journal, _output = self.start_journal(root)
            clock = [0.0]

            def advance(seconds: float) -> None:
                clock[0] += seconds

            result = operation_control.wait_operation(
                root,
                journal.operation_ref,
                1,
                _clock=lambda: clock[0],
                _sleep=advance,
            )
            journal.close()

            self.assertTrue(result["ok"], result)
            self.assertEqual(result["wait"]["outcome"], "deadline_reached")
            self.assertFalse(result["wait"]["cancel_requested"])
            self.assertFalse(result["control"]["cancel_requested"])

    def test_append_during_read_uses_complete_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            journal, _output = self.start_journal(root)
            journal.close()
            original_fstat = operation_control.os.fstat
            injected = [False]

            def append_before_first_fstat(descriptor: int):
                if not injected[0]:
                    injected[0] = True
                    with journal._lock:
                        journal._append("heartbeat", terminal=False)
                return original_fstat(descriptor)

            with patch.object(
                operation_control.os, "fstat", side_effect=append_before_first_fstat
            ):
                result = operation_control.inspect_operation(
                    root, journal.operation_ref
                )

            self.assertTrue(result["ok"], result)
            self.assertEqual(result["state"], "running_observed")

    def test_result_scan_is_bounded_before_unbounded_directory_loading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            journal, output = self.start_journal(root)
            journal.close()
            for index in range(operation_control.MAX_RESULT_SCAN_ENTRIES):
                output.with_name(f"noise-{index:05d}.txt").write_bytes(b"x")

            with patch.object(operation_control, "HEARTBEAT_STALE_SECONDS", -1):
                result = operation_control.inspect_operation(
                    root, journal.operation_ref
                )

            self.assertFalse(result["ok"], result)
            self.assertEqual(
                result["blockers"], ["operation_result_verification_bounded"]
            )

    def test_wrong_path_self_claim_and_ambiguous_matches_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            journal, expected_output = self.start_journal(root)
            self.write_result(journal, expected_output)
            wrong_output = expected_output.with_name("wrong.json")
            shutil.copy2(expected_output, wrong_output)
            expected_output.unlink()
            journal.close()

            with patch.object(operation_control, "HEARTBEAT_STALE_SECONDS", -1):
                wrong_path_result = operation_control.inspect_operation(
                    root, journal.operation_ref
                )

            self.assertFalse(wrong_path_result["ok"], wrong_path_result)
            self.assertEqual(
                wrong_path_result["blockers"], ["operation_observation_stale"]
            )

            shutil.copy2(wrong_output, expected_output)
            with (
                patch.object(operation_control, "HEARTBEAT_STALE_SECONDS", -1),
                patch.object(
                    operation_control,
                    "_output_ref",
                    return_value=journal.output_ref,
                ),
            ):
                ambiguous_result = operation_control.inspect_operation(
                    root, journal.operation_ref
                )

            self.assertFalse(ambiguous_result["ok"], ambiguous_result)
            self.assertEqual(
                ambiguous_result["blockers"],
                ["operation_result_artifact_ambiguous"],
            )

    def test_cancel_is_fixed_unsupported_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            journal, _output = self.start_journal(root)
            before = journal.journal_path.read_bytes()

            result = operation_control.unsupported_cancel(
                root,
                journal.operation_ref,
                approve=True,
                reviewed_by="person:test",
                expected_control_digest=journal.control_digest,
            )
            after = journal.journal_path.read_bytes()
            journal.close()

            self.assertFalse(result["ok"])
            self.assertEqual(result["blockers"], ["operation_cancel_not_supported"])
            self.assertFalse(result["control"]["cancel_supported"])
            self.assertFalse(result["control"]["cancel_requested"])
            self.assertFalse(result["control"]["resume_supported"])
            self.assertFalse(result["privacy_guards"]["writes"])
            self.assertEqual(before, after)

    def test_invalid_operation_ref_is_not_echoed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            secret_like = "C:/private/secret-token"

            result = operation_control.inspect_operation(root, secret_like)

            self.assertIsNone(result["operation_ref"])
            self.assertNotIn(secret_like, json.dumps(result))

    def test_cli_has_one_canonical_surface_and_status_json(self) -> None:
        parser = archive_cli.build_parser()
        subparsers = next(
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        operation_parser = subparsers.choices["operation-control"]
        self.assertEqual(
            sum(value is operation_parser for value in subparsers.choices.values()),
            1,
        )
        project_parser = subparsers.choices["project-version-update"]
        self.assertTrue(
            any("--output" in action.option_strings for action in project_parser._actions)
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            journal, _output = self.start_journal(root)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = archive_cli.main(
                    [
                        "operation-control",
                        str(root),
                        "--operation-ref",
                        journal.operation_ref,
                        "--action",
                        "status",
                        "--dry-run",
                        "--format",
                        "json",
                    ]
                )
            journal.close()

            self.assertEqual(exit_code, 0)
            self.assertEqual(json.loads(stdout.getvalue())["state"], "running_observed")

    def test_index_and_project_update_output_embed_roundtrip_operation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            archive_root.mkdir()

            def fake_index(_root: Path, *, progress_callback=None):
                if progress_callback is not None:
                    progress_callback("index-lock-and-schema", "start", None, None)
                    progress_callback("index-commit", "done", None, None)
                return {
                    "ok": True,
                    "state": "rebuilt",
                    "index_rebuilt": True,
                    "index_complete": True,
                    "warnings": [],
                }

            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                patch.object(
                    archive_cli.archive_services,
                    "require_existing_archive_root",
                    return_value=archive_root,
                ),
                patch.object(
                    archive_cli.archive_services,
                    "index_archive",
                    side_effect=fake_index,
                ),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                index_exit = archive_cli.main(
                    [
                        "index",
                        str(archive_root),
                        "--output",
                        ".wom-scratch/diagnostics/index-result.json",
                        "--format",
                        "json",
                    ]
                )
            self.assertEqual(index_exit, 0, stderr.getvalue())
            index_payload = json.loads(
                (
                    archive_root
                    / ".wom-scratch"
                    / "diagnostics"
                    / "index-result.json"
                ).read_text(encoding="utf-8")
            )
            index_operation = index_payload["cli_output_artifact"]["operation"]
            self.assertEqual(
                operation_control.inspect_operation(
                    archive_root, index_operation["operation_ref"]
                )["state"],
                "completed_result_available",
            )

            project_root = Path(tmp) / "project"
            project_root.mkdir()

            def fake_update(
                _root: Path,
                *,
                progress_callback=None,
                **_kwargs,
            ):
                if progress_callback is not None:
                    progress_callback("project-preflight", "start", None, None)
                    progress_callback("project-preflight", "done", None, None)
                return {
                    "ok": True,
                    "status": "dry_run_ready",
                    "target": {},
                    "source_mirror": {},
                    "runtime": {},
                    "blockers": [],
                    "next_safe_actions": [],
                }

            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                patch.object(
                    archive_cli.archive_services,
                    "wom_kit_project_version_update",
                    side_effect=fake_update,
                ),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                update_exit = archive_cli.main(
                    [
                        "project-version-update",
                        str(project_root),
                        "--target",
                        "v0.3.313",
                        "--dry-run",
                        "--output",
                        ".zettel-kasten/diagnostics/update-result.json",
                        "--format",
                        "json",
                    ]
                )
            self.assertEqual(update_exit, 0, stderr.getvalue())
            project_payload = json.loads(
                (
                    project_root
                    / ".zettel-kasten"
                    / "diagnostics"
                    / "update-result.json"
                ).read_text(encoding="utf-8")
            )
            project_operation = project_payload["cli_output_artifact"]["operation"]
            project_status = operation_control.inspect_operation(
                project_root, project_operation["operation_ref"]
            )
            self.assertTrue(project_status["ok"], project_status)
            self.assertEqual(project_status["state"], "completed_result_available")


if __name__ == "__main__":
    unittest.main()
