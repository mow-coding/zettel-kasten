from __future__ import annotations

import io
import json
import sys
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import archive_cli, archive_services


class V03312CliContractTests(unittest.TestCase):
    def run_cli_split(self, args: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = archive_cli.main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    @staticmethod
    def jsonl_rows(raw: str) -> list[dict[str, object]]:
        return [json.loads(line) for line in raw.splitlines() if line.strip()]

    def test_mint_json_progress_is_content_free_jsonl_and_stdout_is_final_result(self) -> None:
        private_stage = "PRIVATE_PATH_C_USERS_ARCHIVE"
        private_message = "PRIVATE_BODY_AND_TITLE"
        callback_seen = False

        def fake_dry_run(_root: Path, **kwargs: object) -> dict[str, object]:
            nonlocal callback_seen
            callback = kwargs.get("progress_callback")
            self.assertTrue(callable(callback))
            callback_seen = True
            assert callable(callback)
            for stage in archive_cli.MINT_PUBLIC_PROGRESS_STAGES:
                callback(stage, "start", 0, 5)
                if stage == "duplicate_title":
                    callback(private_stage, private_message, 1, 5)
                callback(stage, "done", 1, 5)
            return {"ok": True, "dry_run": True, "blockers": [], "warnings": []}

        with patch.object(archive_services, "mint_zettel_dry_run", side_effect=fake_dry_run):
            code, stdout, stderr = self.run_cli_split(
                [
                    "mint-zet",
                    "C:/PRIVATE_ARCHIVE_ROOT",
                    "--path",
                    "inbox/PRIVATE_REQUEST.md",
                    "--dry-run",
                    "--progress",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(code, 0, stdout)
        self.assertTrue(callback_seen)
        final_result = json.loads(stdout)
        self.assertTrue(final_result["ok"])
        progress_summary = final_result["progress_summary"]
        summary_rows = progress_summary["stages"]
        self.assertEqual(
            [row["stage"] for row in summary_rows],
            list(archive_cli.MINT_PUBLIC_PROGRESS_STAGES),
        )
        self.assertTrue(all(
            set(row).issubset({"stage", "status", "elapsed_ms", "current", "total"})
            for row in summary_rows
        ))
        self.assertTrue(all(row["status"] == "completed" for row in summary_rows))
        quality_summary = next(row for row in summary_rows if row["stage"] == "quality")
        self.assertEqual(quality_summary["status"], "completed")
        self.assertEqual((quality_summary["current"], quality_summary["total"]), (1, 5))
        rows = self.jsonl_rows(stderr)
        self.assertGreaterEqual(len(rows), 4)
        self.assertEqual(rows[0]["stage"], "target")
        self.assertEqual(rows[0]["event"], "start")
        required_keys = {
            "stage",
            "event",
            "current",
            "total",
            "elapsed_ms",
            "last_completed_stage",
        }
        for row in rows:
            self.assertEqual(set(row), required_keys)
            self.assertIn(row["stage"], {*archive_cli.MINT_PROGRESS_STAGES, "unknown"})
            self.assertIn(row["event"], archive_cli.MINT_PROGRESS_EVENTS)
        combined = stdout + stderr
        self.assertNotIn(private_stage, combined)
        self.assertNotIn(private_message, combined)
        self.assertNotIn("PRIVATE_REQUEST", stderr)
        self.assertNotIn("PRIVATE_ARCHIVE_ROOT", stderr)

    def test_mint_approve_passes_progress_callback(self) -> None:
        observed: dict[str, object] = {}
        approval_claim = object()
        binding = SimpleNamespace(
            plan_sha256="sha256:" + "a" * 64,
            target_binding_sha256="sha256:" + "b" * 64,
            context=lambda **_kwargs: object(),
        )

        def fake_mint(_root: Path, **kwargs: object) -> dict[str, object]:
            observed.update(kwargs)
            callback = kwargs.get("progress_callback")
            assert callable(callback)
            callback("receipt_plan", "start", None, None)
            callback("receipt_plan", "done", None, None)
            return {"ok": True, "dry_run": False}

        def execute(_root: Path, _context: object, writer):
            return writer(approval_claim)

        with (
            patch.object(
                archive_services,
                "mint_zettel_dry_run",
                return_value={"ok": True, "dry_run": True},
            ),
            patch.object(
                archive_cli.operation_approval_binding,
                "mint_zet_approval_binding",
                return_value=binding,
            ),
            patch.object(
                archive_services,
                "read_archive_id",
                return_value="archive:personal:test",
            ),
            patch.object(
                archive_cli,
                "_execute_exact_human_approved_write",
                side_effect=execute,
            ),
            patch.object(
                archive_services,
                "mint_zettel",
                side_effect=fake_mint,
            ),
        ):
            code, stdout, stderr = self.run_cli_split(
                [
                    "mint-zet",
                    "C:/archive",
                    "--path",
                    "inbox/example.md",
                    "--approve",
                    "--reviewed-by",
                    "person:reviewer",
                    "--progress",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(code, 0, stdout)
        self.assertTrue(json.loads(stdout)["ok"])
        self.assertTrue(callable(observed.get("progress_callback")))
        self.assertIs(observed["exact_human_approval_claim"], approval_claim)
        self.assertEqual(self.jsonl_rows(stderr)[-1]["event"], "done")

    def test_mint_without_progress_preserves_result_shape_and_passes_no_callback(self) -> None:
        observed: dict[str, object] = {}

        def fake_dry_run(_root: Path, **kwargs: object) -> dict[str, object]:
            observed.update(kwargs)
            return {"ok": True, "dry_run": True, "blockers": [], "warnings": []}

        with patch.object(archive_services, "mint_zettel_dry_run", side_effect=fake_dry_run):
            code, stdout, stderr = self.run_cli_split(
                [
                    "mint-zet",
                    "C:/archive",
                    "--path",
                    "inbox/example.md",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
        result = json.loads(stdout)
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIsNone(observed["progress_callback"])
        self.assertNotIn("progress_summary", result)

    def test_mint_json_progress_service_error_is_sanitized_and_keeps_summary(self) -> None:
        private_error = "PRIVATE_PATH_BODY_EXCEPTION"

        def fail(_root: Path, **kwargs: object) -> dict[str, object]:
            callback = kwargs.get("progress_callback")
            assert callable(callback)
            callback("quality", "start", 0, 1)
            raise archive_services.ArchiveServiceError(private_error)

        with patch.object(archive_services, "mint_zettel_dry_run", side_effect=fail):
            code, stdout, stderr = self.run_cli_split(
                [
                    "mint-zet",
                    "C:/archive",
                    "--path",
                    "inbox/example.md",
                    "--dry-run",
                    "--progress",
                    "--format",
                    "json",
                ]
            )
        result = json.loads(stdout)
        self.assertEqual(code, 1)
        self.assertFalse(result["ok"])
        self.assertIn("progress_summary", result)
        self.assertNotIn(private_error, stdout + stderr)
        for row in self.jsonl_rows(stderr):
            self.assertEqual(
                set(row),
                {"stage", "event", "current", "total", "elapsed_ms", "last_completed_stage"},
            )

    def test_mint_reporter_heartbeat_is_bounded_and_json_schema_is_exact(self) -> None:
        stderr = io.StringIO()
        reporter = archive_cli.MintProgressReporter(
            True,
            json_lines=True,
            heartbeat_interval_seconds=0.02,
        )
        with redirect_stderr(stderr):
            reporter.start()
            time.sleep(0.07)
            reporter.close()

        rows = self.jsonl_rows(stderr.getvalue())
        self.assertLessEqual(reporter._interval, 2.0)
        self.assertTrue(any(row["event"] == "heartbeat" for row in rows))
        self.assertTrue(all(isinstance(row["elapsed_ms"], int) for row in rows))

    def test_mint_progress_failure_does_not_change_result(self) -> None:
        class BrokenStderr:
            def write(self, _value: str) -> int:
                raise OSError("closed progress transport")

            def flush(self) -> None:
                raise OSError("closed progress transport")

        args = SimpleNamespace(
            affirm=[],
            reviewed_by=None,
            dry_run=True,
            approve=False,
            archive_root="C:/archive",
            zettel_id=None,
            path="inbox/example.md",
            allow_warnings=False,
            progress=True,
            format="json",
        )
        stdout = io.StringIO()
        with patch.object(
            archive_services,
            "mint_zettel_dry_run",
            return_value={"ok": True, "dry_run": True, "blockers": [], "warnings": []},
        ), patch.object(sys, "stderr", BrokenStderr()), redirect_stdout(stdout):
            code = archive_cli.command_mint_zettel(args)
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(stdout.getvalue())["ok"])

    def test_view_zets_maps_public_filter_vocabulary_to_service_kwargs(self) -> None:
        observed: dict[str, object] = {}

        def fake_view(_root: Path, **kwargs: object) -> dict[str, object]:
            observed.update(kwargs)
            return {"ok": True, "count": 0, "zettels": [], "blockers": [], "warnings": []}

        with patch.object(archive_services, "view_zets", side_effect=fake_view):
            code, stdout, _stderr = self.run_cli_split(
                [
                    "view-zets",
                    "C:/archive",
                    "--facet",
                    "topic=testing",
                    "--status",
                    "canonical",
                    "--origin",
                    "wom_native",
                    "--minted-after",
                    "2026-08-08T00:00:00+09:00",
                    "--minted-before",
                    "2026-08-11T00:00:00+09:00",
                    "--sort",
                    "minted_at:desc",
                    "--dedupe-by",
                    "id",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(code, 0, stdout)
        self.assertEqual(observed["status"], "canonical")
        self.assertEqual(observed["origin"], "wom_native")
        self.assertEqual(observed["minted_after"], "2026-08-08T00:00:00+09:00")
        self.assertEqual(observed["minted_before"], "2026-08-11T00:00:00+09:00")
        self.assertEqual(observed["sort"], "minted_at_desc")
        self.assertEqual(observed["dedupe_by"], "zettel_id")

    def test_view_zets_accepts_structured_filters_without_saved_view_or_facet(self) -> None:
        observed: dict[str, object] = {}

        def fake_view(_root: Path, **kwargs: object) -> dict[str, object]:
            observed.update(kwargs)
            return {"ok": True, "count": 0, "zettels": [], "blockers": [], "warnings": []}

        with patch.object(archive_services, "view_zets", side_effect=fake_view):
            code, stdout, stderr = self.run_cli_split(
                [
                    "view-zets",
                    "C:/archive",
                    "--status",
                    "canonical",
                    "--origin",
                    "wom_native",
                    "--sort",
                    "minted_at:desc",
                    "--dedupe-by",
                    "id",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(code, 0, stdout + stderr)
        self.assertIsNone(observed["view_id"])
        self.assertIsNone(observed["facets"])
        self.assertEqual(observed["status"], "canonical")
        self.assertEqual(observed["origin"], "wom_native")

    def test_view_and_search_return_exit_one_for_stale_safe_results(self) -> None:
        view_result = {
            "ok": False,
            "count": 0,
            "zettels": [],
            "blockers": ["archive_index_rebuild_required"],
            "warnings": [],
        }
        search_result = {
            "ok": False,
            "index_evidence": {"state": "stale"},
            "blockers": ["archive_index_rebuild_required"],
            "warnings": [],
            "results": [],
        }
        with patch.object(archive_services, "view_zets", return_value=view_result):
            view_code, view_stdout, _ = self.run_cli_split(
                ["view-zets", "C:/archive", "--facet", "topic=x", "--format", "json"]
            )
        with patch.object(archive_services, "search_archive", return_value=search_result):
            search_code, search_stdout, _ = self.run_cli_split(
                ["search", "C:/archive", "needle", "--format", "json"]
            )
        self.assertEqual(view_code, 1)
        self.assertEqual(search_code, 1)
        self.assertFalse(json.loads(view_stdout)["ok"])
        self.assertEqual(json.loads(search_stdout), search_result)

    def test_operator_feedback_compose_and_check_dispatch_public_api(self) -> None:
        calls: list[tuple[object, ...]] = []

        def plan(root: Path, request: str) -> dict[str, object]:
            calls.append(("plan", root, request))
            return {"ok": True, "state": "planned"}

        def approve(root: Path, request: str, **kwargs: object) -> dict[str, object]:
            calls.append(("approve", root, request, kwargs))
            return {"ok": True, "state": "approved"}

        def check(root: Path, feedback_id: str) -> dict[str, object]:
            calls.append(("check", root, feedback_id))
            return {"ok": True, "state": "valid"}

        api = SimpleNamespace(
            plan_operator_feedback_body=plan,
            approve_operator_feedback_body=approve,
            check_operator_feedback_body=check,
        )
        with patch.object(archive_cli, "_operator_feedback_body_api", return_value=api):
            plan_code, _, _ = self.run_cli_split(
                [
                    "operator-feedback-compose",
                    "C:/archive",
                    "--request",
                    ".wom-scratch/private/feedback/request.json",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            approve_code, _, _ = self.run_cli_split(
                [
                    "operator-feedback-compose",
                    "C:/archive",
                    "--request",
                    ".wom-scratch/private/feedback/request.json",
                    "--approve",
                    "--expected-plan-sha256",
                    "a" * 64,
                    "--reviewed-by",
                    "person:reviewer",
                    "--format",
                    "json",
                ]
            )
            check_code, _, _ = self.run_cli_split(
                [
                    "operator-feedback-body-check",
                    "C:/archive",
                    "--feedback-id",
                    "feedback:example",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual((plan_code, approve_code, check_code), (0, 0, 0))
        self.assertEqual(calls[0][0], "plan")
        self.assertEqual(calls[1][0], "approve")
        self.assertEqual(calls[1][3]["expected_plan_sha256"], "a" * 64)
        self.assertEqual(calls[1][3]["reviewed_by"], "person:reviewer")
        self.assertEqual(calls[2][0], "check")

    def test_operator_feedback_late_import_resolves_public_api(self) -> None:
        api = archive_cli._operator_feedback_body_api()
        self.assertTrue(callable(api.plan_operator_feedback_body))
        self.assertTrue(callable(api.approve_operator_feedback_body))
        self.assertTrue(callable(api.check_operator_feedback_body))

    def test_operator_feedback_private_parser_and_service_errors_do_not_echo_values(self) -> None:
        private_value = "PRIVATE_REQUEST_PATH_AND_BODY_MARKER"
        code, stdout, stderr = self.run_cli_split(
            [
                "operator-feedback-compose",
                "C:/archive",
                "--request",
                private_value,
                "--dry-run",
                "--approve",
            ]
        )
        self.assertEqual(code, 2)
        self.assertNotIn(private_value, stdout + stderr)
        self.assertIn("private argument values were not echoed", stderr)

        json_code, json_stdout, json_stderr = self.run_cli_split(
            [
                "operator-feedback-body-check",
                "C:/archive",
                "--feedback-id",
                private_value,
                "--format",
                "json",
            ]
        )
        self.assertEqual(json_code, 1)
        self.assertEqual(json_stderr, "")
        self.assertNotIn(private_value, json_stdout)
        self.assertFalse(json.loads(json_stdout)["private_values_echoed"])

        failing_api = SimpleNamespace(
            plan_operator_feedback_body=lambda *_args: (_ for _ in ()).throw(RuntimeError(private_value))
        )
        with patch.object(archive_cli, "_operator_feedback_body_api", return_value=failing_api):
            code, stdout, stderr = self.run_cli_split(
                [
                    "operator-feedback-compose",
                    "C:/archive",
                    "--request",
                    private_value,
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
        self.assertEqual(code, 1)
        self.assertNotIn(private_value, stdout + stderr)
        failure = json.loads(stdout)
        self.assertFalse(failure["ok"])
        self.assertFalse(failure["private_values_echoed"])

    def test_operator_feedback_approve_requires_digest_and_reviewer(self) -> None:
        code, stdout, stderr = self.run_cli_split(
            [
                "operator-feedback-compose",
                "C:/archive",
                "--request",
                "PRIVATE_REQUEST",
                "--approve",
                "--format",
                "json",
            ]
        )
        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        self.assertEqual(
            json.loads(stdout)["reason_codes"],
            ["feedback_compose_expected_plan_sha256_required"],
        )


if __name__ == "__main__":
    unittest.main()
