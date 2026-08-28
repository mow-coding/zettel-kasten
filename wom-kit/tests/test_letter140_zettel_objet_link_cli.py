from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Callable
from unittest import mock

from jsonschema import Draft202012Validator

from wom_kit import archive_cli, archive_services
from wom_kit.exact_human_approval import CLAIMS_RELATIVE_ROOT
from wom_kit.exact_human_approval_windows import APPROVE_BUTTON_ID
from wom_kit.exact_human_approval_workflow import (
    ExactHumanApprovalWorkflowError,
    _execute_exact_human_approved_write_core,
)


KIT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = KIT_ROOT / "examples" / "fake-life-archive"
ZETTEL_ID = "zet_20240504_fake_lunch_thought"
OBJECT_ID = (
    "sha256:"
    "9dabf9b965a3f789b1b36100f3f70515ce8dfd81b411b1503e1e2c3304303647"
)
ROLE = "evidence"
REVIEWER = "person:letter140-cli-test"


class _ApproveNative:
    def show(self, **_kwargs: str) -> tuple[int, bool]:
        return APPROVE_BUTTON_ID, True


class _EphemeralKeyProvider:
    def use_key(
        self,
        _root: Path | str,
        consumer: Callable[[memoryview], Any],
        *,
        create_if_missing: bool = False,
    ) -> Any:
        if create_if_missing is not True:
            raise AssertionError("the live workflow must request a usable key")
        key = bytearray(range(32))
        try:
            return consumer(memoryview(key))
        finally:
            key[:] = b"\0" * len(key)


class Letter140ZettelObjetLinkCliTests(unittest.TestCase):
    @staticmethod
    def prepare_index(root: Path) -> None:
        indexed = archive_services.index_archive(root)
        if indexed.get("ok") is not True:
            raise AssertionError(indexed)

    @staticmethod
    def run_cli(values: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = archive_cli.main(values)
        return int(code), stdout.getvalue(), stderr.getvalue()

    @staticmethod
    def approved_workflow(
        root,
        context,
        writer,
    ):
        return _execute_exact_human_approved_write_core(
            root,
            context,
            writer,
            native=_ApproveNative(),
            key_provider=_EphemeralKeyProvider(),
            post_decision_boundary=lambda: (
                archive_cli._zettel_objet_link_post_decision_boundary(root)
            ),
        )

    @staticmethod
    def post_write_failure_workflow(
        root,
        context,
        writer,
    ):
        def _write_then_fail(claim):
            result = writer(claim)
            if result.get("ok") is not True:
                return result
            raise OSError("PRIVATE_LETTER140_POST_WRITE_FAILURE")

        return _execute_exact_human_approved_write_core(
            root,
            context,
            _write_then_fail,
            native=_ApproveNative(),
            key_provider=_EphemeralKeyProvider(),
            post_decision_boundary=lambda: (
                archive_cli._zettel_objet_link_post_decision_boundary(root)
            ),
        )

    def test_cli_dry_run_to_exact_approval_writes_and_reads_v02_receipt(self) -> None:
        private_label = "private Letter 140 label"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "archive"
            shutil.copytree(FIXTURE, root)
            self.prepare_index(root)
            zettel_path = root / "zettels" / f"{ZETTEL_ID}.md"
            before = zettel_path.read_bytes()
            common = [
                "zettel-objet-link",
                str(root),
                "--zettel-id",
                ZETTEL_ID,
                "--object-id",
                OBJECT_ID,
                "--role",
                ROLE,
                "--label",
                private_label,
                "--format",
                "json",
            ]

            preview_code, preview_stdout, preview_stderr = self.run_cli(
                [*common, "--dry-run"]
            )
            self.assertEqual(preview_code, 0, preview_stdout)
            self.assertEqual(preview_stderr, "")
            self.assertNotIn(private_label, preview_stdout)
            preview = json.loads(preview_stdout)
            self.assertTrue(preview["ok"], preview)
            expected_plan = preview["summary"]["plan_sha256"]

            with mock.patch.object(
                archive_cli,
                "_execute_zettel_objet_link_exact_human_approved_write",
                side_effect=self.approved_workflow,
            ):
                apply_code, apply_stdout, apply_stderr = self.run_cli(
                    [
                        *common,
                        "--approve",
                        "--expected-plan-sha256",
                        expected_plan,
                        "--reviewed-by",
                        REVIEWER,
                    ]
                )

            self.assertEqual(apply_code, 0, apply_stdout)
            self.assertEqual(apply_stderr, "")
            self.assertNotIn(private_label, apply_stdout)
            applied = json.loads(apply_stdout)
            self.assertTrue(applied["ok"], applied)
            self.assertEqual(applied["state"], "written")
            self.assertEqual(
                applied["exact_human_approval"]["status"], "succeeded"
            )
            self.assertNotEqual(zettel_path.read_bytes(), before)
            self.assertIn(private_label, zettel_path.read_text(encoding="utf-8"))

            receipt_relative = applied["summary"]["receipt_path"]
            receipt_path = root.joinpath(*receipt_relative.split("/"))
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(
                receipt["schema"], "wom-kit/zettel-objet-link-receipt/v0.2"
            )
            self.assertEqual(
                receipt["exact_human_approval"]["operation"],
                "zettel_objet_link",
            )
            claim_paths = list((root / CLAIMS_RELATIVE_ROOT).glob("*.json"))
            self.assertEqual(len(claim_paths), 1)
            self.assertEqual(
                json.loads(claim_paths[0].read_text(encoding="utf-8"))["status"],
                "succeeded",
            )

            lookup_code, lookup_stdout, lookup_stderr = self.run_cli(
                [
                    "zettel-objet-link-receipts",
                    str(root),
                    "--zettel-id",
                    ZETTEL_ID,
                    "--object-id",
                    OBJECT_ID,
                    "--role",
                    ROLE,
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(lookup_code, 0, lookup_stdout)
            self.assertEqual(lookup_stderr, "")
            self.assertNotIn(private_label, lookup_stdout)
            lookup = json.loads(lookup_stdout)
            self.assertTrue(lookup["ok"], lookup)
            self.assertEqual(lookup["summary"]["validated_receipt_count"], 1)
            self.assertEqual(
                lookup["data"]["receipts"][0]["receipt_path"],
                receipt_relative,
            )

    def test_cancelled_workflow_reports_precondition_with_no_effects(self) -> None:
        private_label = "private Letter 140 cancelled label"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "archive"
            shutil.copytree(FIXTURE, root)
            self.prepare_index(root)
            zettel_path = root / "zettels" / f"{ZETTEL_ID}.md"
            before = zettel_path.read_bytes()
            common = [
                "zettel-objet-link",
                str(root),
                "--zettel-id",
                ZETTEL_ID,
                "--object-id",
                OBJECT_ID,
                "--role",
                ROLE,
                "--label",
                private_label,
            ]
            preview_code, preview_stdout, preview_stderr = self.run_cli(
                [*common, "--dry-run", "--format", "json"]
            )
            self.assertEqual(preview_code, 0, preview_stdout)
            self.assertEqual(preview_stderr, "")
            expected_plan = json.loads(preview_stdout)["summary"]["plan_sha256"]

            with mock.patch.object(
                archive_cli,
                "_execute_zettel_objet_link_exact_human_approved_write",
                side_effect=ExactHumanApprovalWorkflowError(
                    "exact_human_approval_cancelled"
                ),
            ):
                code, stdout, stderr = self.run_cli(
                    [
                        *common,
                        "--approve",
                        "--expected-plan-sha256",
                        expected_plan,
                        "--reviewed-by",
                        REVIEWER,
                        "--format",
                        "json",
                    ]
                )

            self.assertEqual(code, 1)
            self.assertEqual(stderr, "")
            self.assertNotIn(private_label, stdout)
            self.assertNotIn(str(root), stdout)
            payload = json.loads(stdout)
            self.assertEqual(payload["state"], "blocked")
            self.assertEqual(payload["status_class"], "blocked")
            self.assertEqual(payload["error_class"], "precondition")
            self.assertEqual(
                payload["reason_codes"],
                ["zettel_objet_link_workflow_precondition_failed"],
            )
            self.assertEqual(payload["effects_state"], "none")
            self.assertEqual(payload["files_written"], [])
            self.assertEqual(zettel_path.read_bytes(), before)

    def test_deep_manifest_fails_closed_in_content_free_cli_json_envelope(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "archive"
            shutil.copytree(FIXTURE, root)
            self.prepare_index(root)
            manifest = root / "objects" / "manifests" / "files.jsonl"
            digest = OBJECT_ID.removeprefix("sha256:")
            deep_value = "[" * 2_000 + "0" + "]" * 2_000
            manifest.write_text(
                (
                    '{"object_id":"'
                    + OBJECT_ID
                    + '","sha256":"'
                    + digest
                    + '","logical_key":"objects/safe/deep.bin",'
                    '"locations":[{"provider":"local"}],'
                    '"provenance":{"nested":'
                    + deep_value
                    + "}}\n"
                ),
                encoding="utf-8",
            )

            code, stdout, stderr = self.run_cli(
                [
                    "zettel-objet-link",
                    str(root),
                    "--zettel-id",
                    ZETTEL_ID,
                    "--object-id",
                    OBJECT_ID,
                    "--role",
                    ROLE,
                    "--approve",
                    "--expected-plan-sha256",
                    "0" * 64,
                    "--reviewed-by",
                    REVIEWER,
                    "--format",
                    "json",
                ]
            )

            self.assertEqual(code, 1)
            self.assertEqual(stderr, "")
            payload = json.loads(stdout)
            schema = json.loads(
                (KIT_ROOT / "schemas" / "cli-error-v0.1.schema.json").read_text(
                    encoding="utf-8"
                )
            )
            Draft202012Validator(schema).validate(payload)
            self.assertEqual(payload["schema"], "wom-kit/cli-error/v0.1")
            self.assertEqual(payload["error_class"], "precondition")
            self.assertEqual(
                payload["reason_codes"],
                ["zettel_objet_link_preflight_blocked"],
            )
            self.assertEqual(payload["effects_state"], "none")
            self.assertEqual(payload["files_written"], [])
            self.assertIs(payload["private_values_echoed"], False)
            self.assertNotIn(str(root), stdout)
            self.assertNotIn(ZETTEL_ID, stdout)

    def test_post_write_failure_reports_unknown_effects_in_json_and_text(self) -> None:
        private_label = "private Letter 140 post-write label"
        for output_format in ("json", "text"):
            with self.subTest(output_format=output_format):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary) / "archive"
                    shutil.copytree(FIXTURE, root)
                    self.prepare_index(root)
                    zettel_path = root / "zettels" / f"{ZETTEL_ID}.md"
                    before = zettel_path.read_bytes()
                    common = [
                        "zettel-objet-link",
                        str(root),
                        "--zettel-id",
                        ZETTEL_ID,
                        "--object-id",
                        OBJECT_ID,
                        "--role",
                        ROLE,
                        "--label",
                        private_label,
                    ]
                    preview_code, preview_stdout, preview_stderr = self.run_cli(
                        [*common, "--dry-run", "--format", "json"]
                    )
                    self.assertEqual(preview_code, 0, preview_stdout)
                    self.assertEqual(preview_stderr, "")
                    expected_plan = json.loads(preview_stdout)["summary"][
                        "plan_sha256"
                    ]

                    with mock.patch.object(
                        archive_cli,
                        "_execute_zettel_objet_link_exact_human_approved_write",
                        side_effect=self.post_write_failure_workflow,
                    ):
                        code, stdout, stderr = self.run_cli(
                            [
                                *common,
                                "--approve",
                                "--expected-plan-sha256",
                                expected_plan,
                                "--reviewed-by",
                                REVIEWER,
                                "--format",
                                output_format,
                            ]
                        )

                    self.assertEqual(code, 1)
                    self.assertNotEqual(zettel_path.read_bytes(), before)
                    self.assertIn(
                        private_label,
                        zettel_path.read_text(encoding="utf-8"),
                    )
                    claim_paths = list(
                        (root / CLAIMS_RELATIVE_ROOT).glob("*.json")
                    )
                    self.assertEqual(len(claim_paths), 1)
                    self.assertEqual(
                        json.loads(
                            claim_paths[0].read_text(encoding="utf-8")
                        )["status"],
                        "started",
                    )
                    combined = stdout + stderr
                    self.assertNotIn(private_label, combined)
                    self.assertNotIn(str(root), combined)
                    self.assertNotIn(
                        "PRIVATE_LETTER140_POST_WRITE_FAILURE",
                        combined,
                    )
                    if output_format == "json":
                        self.assertEqual(stderr, "")
                        payload = json.loads(stdout)
                        self.assertEqual(payload["state"], "state_unknown")
                        self.assertEqual(
                            payload["status_class"],
                            "reconciliation_required",
                        )
                        self.assertEqual(payload["error_class"], "execution")
                        self.assertEqual(
                            payload["reason_codes"],
                            ["zettel_objet_link_execution_state_unknown"],
                        )
                        self.assertEqual(payload["effects_state"], "unknown")
                        self.assertIsNone(payload["files_written"])
                        self.assertIs(
                            payload["reconciliation_required"], True
                        )
                        self.assertIs(
                            payload["automatic_retry_allowed"], False
                        )
                    else:
                        self.assertEqual(stdout, "")
                        self.assertIn(
                            "execution state is unknown; archive files may "
                            "have been written",
                            stderr,
                        )
                        self.assertIn("do not retry automatically", stderr)
                        self.assertNotIn(
                            "no archive files were written",
                            stderr,
                        )


if __name__ == "__main__":
    unittest.main()
