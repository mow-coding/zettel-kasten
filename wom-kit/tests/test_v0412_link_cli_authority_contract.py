from __future__ import annotations

import copy
import io
import json
import shutil
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from wom_kit import (
    archive_cli,
    archive_services,
    completion_workflows,
    operation_approval_binding,
)
from wom_kit.exact_human_approval import CLAIMS_RELATIVE_ROOT


KIT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = KIT_ROOT / "examples" / "fake-life-archive"
ZETTEL_ID = "zet_20240504_fake_lunch_thought"
OBJECT_ID = (
    "sha256:"
    "9dabf9b965a3f789b1b36100f3f70515ce8dfd81b411b1503e1e2c3304303647"
)
ROLE = "evidence"


class V0412LinkCliAuthorityContractTests(unittest.TestCase):
    @staticmethod
    def archive(parent: Path) -> Path:
        root = parent / "archive"
        shutil.copytree(FIXTURE, root)
        return root

    @staticmethod
    def run_cli(values: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = archive_cli.main(values)
        return int(code), stdout.getvalue(), stderr.getvalue()

    @staticmethod
    def seed_existing_link(root: Path) -> Path:
        path = root / "zettels" / f"{ZETTEL_ID}.md"
        text = path.read_text(encoding="utf-8")
        replacement = (
            "assets:\n"
            f"  - object_id: {OBJECT_ID}\n"
            f"    role: {ROLE}"
        )
        if text.count("assets: []") != 1:
            raise AssertionError("fixture assets boundary changed")
        path.write_text(text.replace("assets: []", replacement), encoding="utf-8")
        return path

    def test_approval_binding_requires_and_binds_index_and_manifest_generations(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.archive(Path(temporary))
            indexed = archive_services.index_archive(root)
            self.assertTrue(indexed["ok"], indexed)
            plan = completion_workflows.zettel_objet_link_plan(
                root,
                zettel_id=ZETTEL_ID,
                object_id=OBJECT_ID,
                role=ROLE,
            )
            self.assertTrue(plan["ok"], plan)

        original = operation_approval_binding.zettel_objet_link_approval_binding(
            plan
        )
        self.assertIn("authority_projection", original.review_binding_codes)
        self.assertEqual(
            original.review_binding_codes,
            tuple(sorted(original.review_binding_codes)),
        )
        for key, replacement in (
            ("index_generation", "gen:" + "f" * 32),
            ("manifest_sha256", "sha256:" + "e" * 64),
        ):
            with self.subTest(binding_key=key):
                changed = copy.deepcopy(plan)
                changed["summary"][key] = replacement
                rebound = (
                    operation_approval_binding.zettel_objet_link_approval_binding(
                        changed
                    )
                )
                self.assertNotEqual(
                    rebound.target_binding_sha256,
                    original.target_binding_sha256,
                )

        invalid_cases = (
            ("index_generation", None),
            ("index_generation", "gen:" + "a" * 31),
            ("manifest_sha256", "a" * 64),
            ("manifest_sha256", "sha256:" + "A" * 64),
        )
        for key, value in invalid_cases:
            with self.subTest(invalid_key=key, value=value):
                invalid = copy.deepcopy(plan)
                if value is None:
                    invalid["summary"].pop(key, None)
                else:
                    invalid["summary"][key] = value
                with self.assertRaises(
                    operation_approval_binding.OperationApprovalBindingError
                ):
                    operation_approval_binding.zettel_objet_link_approval_binding(
                        invalid
                    )

    def test_already_present_dry_run_and_approve_skip_human_and_support_writes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.archive(Path(temporary))
            zettel_path = self.seed_existing_link(root)
            indexed = archive_services.index_archive(root)
            self.assertTrue(indexed["ok"], indexed)
            before_zettel = zettel_path.read_bytes()
            before_receipts = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in (root / "receipts").rglob("*")
                if path.is_file()
            }
            common = [
                "zettel-objet-link",
                str(root),
                "--zettel-id",
                ZETTEL_ID,
                "--object-id",
                OBJECT_ID,
                "--role",
                ROLE,
                "--format",
                "json",
            ]

            with (
                mock.patch.object(
                    archive_cli,
                    "_execute_zettel_objet_link_exact_human_approved_write",
                    side_effect=AssertionError("native approval must not run"),
                ) as native_approval,
                mock.patch.object(
                    operation_approval_binding,
                    "zettel_objet_link_approval_binding",
                    side_effect=AssertionError("approval binding must not run"),
                ) as approval_binding,
                mock.patch.object(
                    completion_workflows,
                    "zettel_objet_link_apply",
                    side_effect=AssertionError("writer must not run"),
                ) as writer,
            ):
                dry_code, dry_stdout, dry_stderr = self.run_cli(
                    [*common, "--dry-run"]
                )
                approve_code, approve_stdout, approve_stderr = self.run_cli(
                    [*common, "--approve"]
                )

            self.assertEqual(dry_code, 0, dry_stdout)
            self.assertEqual(approve_code, 0, approve_stdout)
            self.assertEqual(dry_stderr, "")
            self.assertEqual(approve_stderr, "")
            dry_result = json.loads(dry_stdout)
            approve_result = json.loads(approve_stdout)
            self.assertEqual(dry_result["state"], "already_present")
            self.assertIs(dry_result["dry_run"], True)
            self.assertEqual(approve_result["state"], "already_present")
            self.assertIs(approve_result["dry_run"], False)
            self.assertIs(approve_result["approved"], False)
            self.assertEqual(approve_result["files_written"], [])
            native_approval.assert_not_called()
            approval_binding.assert_not_called()
            writer.assert_not_called()
            self.assertEqual(zettel_path.read_bytes(), before_zettel)
            after_receipts = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in (root / "receipts").rglob("*")
                if path.is_file()
            }
            self.assertEqual(after_receipts, before_receipts)
            self.assertFalse((root / CLAIMS_RELATIVE_ROOT).exists())

    def test_single_plan_progress_starts_before_slow_work_and_heartbeats(
        self,
    ) -> None:
        original_reporter = archive_cli.CommandProgressReporter
        stdout = io.StringIO()
        stderr = io.StringIO()
        planner_observed_start = False
        private_marker = "PRIVATE_V0412_PROGRESS_MUST_NOT_ESCAPE"
        configured_interval = 0.0

        def fast_reporter(enabled, **kwargs):
            nonlocal configured_interval
            configured_interval = float(
                kwargs.get("heartbeat_interval_seconds", 10.0)
            )
            kwargs["heartbeat_interval_seconds"] = 0.01
            return original_reporter(enabled, **kwargs)

        def slow_plan(*_args, **_kwargs):
            nonlocal planner_observed_start
            current = stderr.getvalue()
            planner_observed_start = (
                "zettel-objet-link-plan" in current and "start" in current
            )
            deadline = time.monotonic() + 1.0
            while "heartbeat" not in stderr.getvalue() and time.monotonic() < deadline:
                time.sleep(0.005)
            return {
                "ok": True,
                "state": "ready",
                "dry_run": True,
                "lifecycle_action": "zettel_objet_link_plan",
                "summary": {"plan_sha256": "a" * 64},
                "data": {},
                "blockers": [],
                "warnings": [],
                "would_change": [],
            }

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / private_marker
            with (
                mock.patch.object(
                    archive_cli,
                    "CommandProgressReporter",
                    side_effect=fast_reporter,
                ),
                mock.patch.object(
                    completion_workflows,
                    "zettel_objet_link_plan",
                    side_effect=slow_plan,
                ),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                code = archive_cli.main(
                    [
                        "zettel-objet-link",
                        str(root),
                        "--zettel-id",
                        ZETTEL_ID,
                        "--object-id",
                        OBJECT_ID,
                        "--role",
                        ROLE,
                        "--label",
                        private_marker,
                        "--dry-run",
                        "--progress",
                        "--format",
                        "json",
                    ]
                )

        progress = stderr.getvalue()
        self.assertEqual(code, 0, stdout.getvalue())
        self.assertTrue(planner_observed_start, progress)
        self.assertLessEqual(configured_interval, 10.0)
        self.assertIn("zettel-objet-link-plan", progress)
        self.assertIn("start", progress)
        self.assertIn("heartbeat", progress)
        for forbidden in (private_marker, str(root), ZETTEL_ID, OBJECT_ID):
            self.assertNotIn(forbidden, progress)

    def test_single_apply_progress_starts_before_slow_writer_and_heartbeats(
        self,
    ) -> None:
        original_reporter = archive_cli.CommandProgressReporter
        stdout = io.StringIO()
        stderr = io.StringIO()
        writer_observed_start = False
        private_marker = "PRIVATE_V0412_APPLY_PROGRESS_MUST_NOT_ESCAPE"

        def fast_reporter(enabled, **kwargs):
            kwargs["heartbeat_interval_seconds"] = 0.01
            return original_reporter(enabled, **kwargs)

        def direct_workflow(_root, _context, writer):
            return writer(object())

        def slow_apply(*_args, **_kwargs):
            nonlocal writer_observed_start
            current = stderr.getvalue()
            writer_observed_start = (
                "zettel-objet-link-apply" in current and "start" in current
            )
            deadline = time.monotonic() + 1.0
            while "heartbeat" not in stderr.getvalue() and time.monotonic() < deadline:
                time.sleep(0.005)
            return {
                "ok": True,
                "state": "written",
                "dry_run": False,
                "lifecycle_action": "zettel_objet_link_apply",
                "summary": {},
                "data": {},
                "blockers": [],
                "warnings": [],
                "would_change": [],
                "files_written": [],
            }

        with tempfile.TemporaryDirectory() as temporary:
            root = self.archive(Path(temporary))
            indexed = archive_services.index_archive(root)
            self.assertTrue(indexed["ok"], indexed)
            plan = completion_workflows.zettel_objet_link_plan(
                root,
                zettel_id=ZETTEL_ID,
                object_id=OBJECT_ID,
                role=ROLE,
                label=private_marker,
            )
            self.assertTrue(plan["ok"], plan)
            expected_plan = str(plan["summary"]["plan_sha256"])
            with (
                mock.patch.object(
                    archive_cli,
                    "CommandProgressReporter",
                    side_effect=fast_reporter,
                ),
                mock.patch.object(
                    archive_cli,
                    "_execute_zettel_objet_link_exact_human_approved_write",
                    side_effect=direct_workflow,
                ),
                mock.patch.object(
                    completion_workflows,
                    "zettel_objet_link_apply",
                    side_effect=slow_apply,
                ),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                code = archive_cli.main(
                    [
                        "zettel-objet-link",
                        str(root),
                        "--zettel-id",
                        ZETTEL_ID,
                        "--object-id",
                        OBJECT_ID,
                        "--role",
                        ROLE,
                        "--label",
                        private_marker,
                        "--approve",
                        "--expected-plan-sha256",
                        expected_plan,
                        "--reviewed-by",
                        "person:v0412-progress-test",
                        "--progress",
                        "--format",
                        "json",
                    ]
                )

        progress = stderr.getvalue()
        self.assertEqual(code, 0, stdout.getvalue())
        self.assertTrue(writer_observed_start, progress)
        self.assertIn("zettel-objet-link-apply", progress)
        self.assertIn("heartbeat", progress)
        for forbidden in (private_marker, str(root), ZETTEL_ID, OBJECT_ID):
            self.assertNotIn(forbidden, progress)


if __name__ == "__main__":
    unittest.main()
