from __future__ import annotations

import io
import json
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Callable
from unittest import mock

from wom_kit import (
    archive_cli,
    archive_services,
    command_status,
    objet_capture_selection_exact,
)
from wom_kit.exact_human_approval_windows import APPROVE_BUTTON_ID
from wom_kit.exact_human_approval_workflow import (
    _execute_exact_human_approved_write_core,
)


ARCHIVE_ID = "archive:test:v048-existing-intake-selection"
REVIEWER = "person:v048-selection-reviewer"


class _Native:
    def __init__(self, *, approved: bool) -> None:
        self.approved = approved
        self.calls = 0

    def show(self, **_kwargs: str) -> tuple[int, bool]:
        self.calls += 1
        return (
            (APPROVE_BUTTON_ID, True)
            if self.approved
            else (2, False)
        )


class _KeyProvider:
    def __init__(self) -> None:
        self.calls = 0

    def use_key(
        self,
        _root: Path | str,
        consumer: Callable[[memoryview], Any],
        *,
        create_if_missing: bool = False,
    ) -> Any:
        if create_if_missing is not True:
            raise AssertionError("exact approval must request one usable key")
        self.calls += 1
        key = bytearray(range(32))
        try:
            return consumer(memoryview(key))
        finally:
            key[:] = b"\0" * len(key)


class ExistingIntakeCaptureSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "archive"
        self.root.mkdir()
        (self.root / "archive.yml").write_text(
            f"archive_id: {ARCHIVE_ID}\n",
            encoding="utf-8",
        )
        self.private_name = "private-existing-intake-source.txt"
        self.staged_relative = f"staging/incoming/{self.private_name}"
        staged = self.root / Path(self.staged_relative)
        staged.parent.mkdir(parents=True)
        staged.write_bytes(b"private staged bytes\n")
        self.receipt_relative = self._write_existing_source_intake_receipt()
        manifest = self.root / "objects" / "manifests" / "files.jsonl"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_bytes(b"")
        indexed = archive_services.index_archive(self.root)
        self.assertTrue(indexed["ok"], indexed)
        self.assertEqual(indexed["index_state"], "current", indexed)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_existing_source_intake_receipt(self) -> str:
        document = {
            "ok": True,
            "dry_run": True,
            "lifecycle_action": "source_intake_plan",
            "archive_id": ARCHIVE_ID,
            "blockers": [],
            "content_access": dict(
                archive_services.SOURCE_INTAKE_CONTENT_ACCESS_EXPECTATIONS
            ),
            "source_refs_for_draft": [],
        }
        digest = archive_services.sha256_json_value(document)
        relative = archive_services.source_intake_record_path(digest)
        path = self.root / Path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return relative

    def _plan(self):
        return objet_capture_selection_exact.plan_existing_intake_capture_selection(
            self.root,
            staged_path=self.staged_relative,
            source_intake_receipt=self.receipt_relative,
        )

    @staticmethod
    def _snapshot(root: Path) -> dict[str, bytes]:
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    @staticmethod
    def _run_cli(values: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = archive_cli.main(values)
        return int(code), stdout.getvalue(), stderr.getvalue()

    @staticmethod
    def _workflow(native: _Native, key_provider: _KeyProvider):
        def execute(root, context, writer):
            return _execute_exact_human_approved_write_core(
                root,
                context,
                writer,
                native=native,
                key_provider=key_provider,
            )

        return execute

    def test_plan_is_stable_content_free_and_dry_run_writes_nothing(self) -> None:
        before = self._snapshot(self.root)
        first = self._plan()
        second = self._plan()

        self.assertTrue(first.approveable, first.public_document())
        self.assertEqual(
            first.manifest.manifest_sha256,
            second.manifest.manifest_sha256,
        )
        self.assertEqual(first.selection_bytes, second.selection_bytes)
        self.assertEqual(self._snapshot(self.root), before)
        public = first.public_document()
        self.assertEqual(public["capability_scope"], "preexisting_artifact_only")
        self.assertFalse(public["general_intake_chain_complete"])
        self.assertEqual(public["selected_item_count"], 1)
        self.assertEqual(public["source_intake_receipt_count"], 1)
        self.assertEqual(
            first.manifest.operation,
            "objet_capture_selection_record",
        )
        serialized = json.dumps(public, sort_keys=True)
        for forbidden in (
            str(self.root),
            self.staged_relative,
            self.receipt_relative,
            self.private_name,
            "private staged bytes",
        ):
            self.assertNotIn(forbidden, serialized)

        cli_values = [
            "objet-capture-selection",
            str(self.root),
            "--staged-path",
            self.staged_relative,
            "--source-intake-receipt",
            self.receipt_relative,
            "--exact-existing-intake",
            "--dry-run",
            "--format",
            "json",
        ]
        first_code, first_output, first_error = self._run_cli(cli_values)
        second_code, second_output, second_error = self._run_cli(cli_values)
        self.assertEqual((first_code, second_code), (0, 0), first_error + second_error)
        first_cli = json.loads(first_output)
        second_cli = json.loads(second_output)
        self.assertEqual(first_cli["plan_sha256"], second_cli["plan_sha256"])
        self.assertEqual(first_cli["plan_sha256"], first.manifest.manifest_sha256)
        for forbidden in (
            str(self.root),
            self.staged_relative,
            self.receipt_relative,
            self.private_name,
        ):
            self.assertNotIn(forbidden, first_output)
        self.assertEqual(self._snapshot(self.root), before)

    def test_only_canonical_existing_source_intake_record_is_accepted(self) -> None:
        copied = "receipts/sources/arbitrary.source-intake-plan.json"
        (self.root / Path(copied)).write_bytes(
            (self.root / Path(self.receipt_relative)).read_bytes()
        )
        plan = objet_capture_selection_exact.plan_existing_intake_capture_selection(
            self.root,
            staged_path=self.staged_relative,
            source_intake_receipt=copied,
        )
        self.assertFalse(plan.approveable)
        self.assertEqual(
            plan.blockers,
            ("existing_intake_capture_selection_source_intake_invalid",),
        )

    def test_cli_uses_one_native_approval_and_writes_checkpointed_selection(self) -> None:
        plan = self._plan()
        native = _Native(approved=True)
        key_provider = _KeyProvider()
        legacy_approve_values: list[bool] = []
        original_preview = archive_services.objet_capture_selection_manifest

        def guarded_preview(*args, **kwargs):
            legacy_approve_values.append(bool(kwargs.get("approve")))
            if kwargs.get("approve"):
                raise AssertionError("the old approval gate must not be called")
            return original_preview(*args, **kwargs)

        with (
            mock.patch.object(
                objet_capture_selection_exact,
                "_execute_exact_human_approved_write",
                side_effect=self._workflow(native, key_provider),
            ),
            mock.patch.object(
                archive_services,
                "objet_capture_selection_manifest",
                side_effect=guarded_preview,
            ),
        ):
            code, stdout, stderr = self._run_cli(
                [
                    "objet-capture-selection",
                    str(self.root),
                    "--staged-path",
                    self.staged_relative,
                    "--source-intake-receipt",
                    self.receipt_relative,
                    "--exact-existing-intake",
                    "--approve",
                    "--reviewed-by",
                    REVIEWER,
                    "--format",
                    "json",
                ]
            )
        self.assertEqual(code, 0, stderr)
        result = json.loads(stdout)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["state"], "selection_recorded")
        self.assertEqual(native.calls, 1)
        self.assertEqual(key_provider.calls, 1)
        self.assertTrue(legacy_approve_values)
        self.assertNotIn(True, legacy_approve_values)
        selection_path = self.root / Path(plan.selection_relative_path)
        self.assertTrue(selection_path.is_file())
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
        self.assertIsNone(selection["created_at"])
        self.assertIsNone(selection["created_by"])
        capture_plan = archive_services.objet_capture_exact_dry_run(
            self.root,
            plan.selection_relative_path,
        )
        self.assertTrue(capture_plan["ok"], capture_plan)

        # The exact selection is not a private one-off format: the already
        # shipped capture command must be able to consume it all the way
        # through its own, separate native approval and lossless write.
        with mock.patch.object(
            archive_cli,
            "_execute_exact_human_approved_write",
            side_effect=self._workflow(native, key_provider),
        ):
            capture_code, capture_stdout, capture_stderr = self._run_cli(
                [
                    "objet-capture",
                    str(self.root),
                    "--selection",
                    plan.selection_relative_path,
                    "--exact-local",
                    "--approve",
                    "--reviewed-by",
                    REVIEWER,
                    "--format",
                    "json",
                ]
            )
        self.assertEqual(capture_code, 0, capture_stderr)
        captured = json.loads(capture_stdout)
        self.assertTrue(captured["ok"], captured)
        self.assertEqual(captured["summary"]["captured"], 1)
        self.assertEqual(native.calls, 2)
        self.assertEqual(key_provider.calls, 2)
        object_digest = plan.staged_bytes_sha256.removeprefix("sha256:")
        object_path = (
            self.root
            / "objects"
            / "sha256"
            / object_digest[:2]
            / object_digest
        )
        self.assertEqual(object_path.read_bytes(), b"private staged bytes\n")
        capture_receipt = json.loads(
            (self.root / Path(captured["receipt_path"])).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            capture_receipt["exact_human_approval"]["operation"],
            "objet_capture",
        )
        self.assertTrue(
            list(
                (self.root / "profiles" / "local" / "exact-operations" / "checkpoints")
                .glob("*.jsonl")
            )
        )
        self.assertTrue(
            list(
                (self.root / "receipts" / "ops" / "exact-operations")
                .glob("*.json")
            )
        )
        serialized = json.dumps(result, sort_keys=True)
        for forbidden in (
            str(self.root),
            self.staged_relative,
            self.receipt_relative,
            self.private_name,
        ):
            self.assertNotIn(forbidden, serialized)

    def test_progress_starts_before_slow_hash_and_heartbeats_without_private_values(
        self,
    ) -> None:
        original_reporter = archive_cli.CommandProgressReporter
        original_preview = archive_services.objet_capture_selection_manifest
        stdout = io.StringIO()
        stderr = io.StringIO()
        preview_observed_start = False

        def fast_reporter(enabled, **kwargs):
            kwargs["heartbeat_interval_seconds"] = 0.01
            return original_reporter(enabled, **kwargs)

        def slow_preview(*args, **kwargs):
            nonlocal preview_observed_start
            preview_observed_start = "selection-plan: start" in stderr.getvalue()
            deadline = time.monotonic() + 1.0
            while (
                "selection-plan: heartbeat" not in stderr.getvalue()
                and time.monotonic() < deadline
            ):
                time.sleep(0.005)
            return original_preview(*args, **kwargs)

        with (
            mock.patch.object(
                archive_cli,
                "CommandProgressReporter",
                side_effect=fast_reporter,
            ),
            mock.patch.object(
                archive_services,
                "objet_capture_selection_manifest",
                side_effect=slow_preview,
            ),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = archive_cli.main(
                [
                    "objet-capture-selection",
                    str(self.root),
                    "--staged-path",
                    self.staged_relative,
                    "--source-intake-receipt",
                    self.receipt_relative,
                    "--exact-existing-intake",
                    "--dry-run",
                    "--progress",
                    "--format",
                    "json",
                ]
            )

        progress = stderr.getvalue()
        self.assertEqual(code, 0, progress)
        self.assertTrue(preview_observed_start, progress)
        self.assertIn("selection-plan: start", progress)
        self.assertIn("selection-plan: heartbeat", progress)
        self.assertLess(
            progress.index("selection-plan: start"),
            progress.index("selection-plan: heartbeat"),
        )
        for forbidden in (
            str(self.root),
            self.staged_relative,
            self.receipt_relative,
            self.private_name,
            self._plan().manifest.manifest_sha256,
        ):
            self.assertNotIn(forbidden, progress)

    def test_success_text_reports_write_and_exact_execution_emits_progress(self) -> None:
        native = _Native(approved=True)
        key_provider = _KeyProvider()
        exact_events = []
        original_apply = objet_capture_selection_exact.apply_exact_operation

        def observed_apply(*args, **kwargs):
            hook = kwargs.get("progress_hook")
            self.assertTrue(callable(hook))

            def capture(event):
                exact_events.append(event.public_document())
                hook(event)

            kwargs["progress_hook"] = capture
            return original_apply(*args, **kwargs)

        with (
            mock.patch.object(
                objet_capture_selection_exact,
                "_execute_exact_human_approved_write",
                side_effect=self._workflow(native, key_provider),
            ),
            mock.patch.object(
                objet_capture_selection_exact,
                "apply_exact_operation",
                side_effect=observed_apply,
            ),
        ):
            code, stdout, stderr = self._run_cli(
                [
                    "objet-capture-selection",
                    str(self.root),
                    "--staged-path",
                    self.staged_relative,
                    "--source-intake-receipt",
                    self.receipt_relative,
                    "--exact-existing-intake",
                    "--approve",
                    "--reviewed-by",
                    REVIEWER,
                    "--progress",
                    "--format",
                    "text",
                ]
            )

        self.assertEqual(code, 0, stderr)
        self.assertIn("- selection recorded: yes", stdout)
        self.assertTrue(exact_events)
        self.assertIn("exact-operation-", stderr)
        for forbidden in (
            str(self.root),
            self.staged_relative,
            self.receipt_relative,
            self.private_name,
        ):
            self.assertNotIn(forbidden, stderr)

    def test_legacy_general_selection_approval_remains_fixed_closed(self) -> None:
        before = self._snapshot(self.root)
        code, stdout, stderr = self._run_cli(
            [
                "objet-capture-selection",
                str(self.root),
                "--staged-path",
                self.staged_relative,
                "--source-intake-receipt",
                self.receipt_relative,
                "--approve",
                "--reviewed-by",
                REVIEWER,
                "--format",
                "json",
            ]
        )
        self.assertEqual(code, 1, stderr)
        result = json.loads(stdout)
        self.assertFalse(result["ok"], result)
        self.assertEqual(
            result["reason_codes"],
            ["compound_exact_human_approval_binding_required"],
        )
        self.assertEqual(self._snapshot(self.root), before)
        for forbidden in (
            str(self.root),
            self.staged_relative,
            self.receipt_relative,
            self.private_name,
        ):
            self.assertNotIn(forbidden, stdout)

    def test_cancel_has_zero_filesystem_effects(self) -> None:
        plan = self._plan()
        before = self._snapshot(self.root)
        native = _Native(approved=False)
        key_provider = _KeyProvider()
        with mock.patch.object(
            objet_capture_selection_exact,
            "_execute_exact_human_approved_write",
            side_effect=self._workflow(native, key_provider),
        ):
            code, stdout, _stderr = self._run_cli(
                [
                    "objet-capture-selection",
                    str(self.root),
                    "--staged-path",
                    self.staged_relative,
                    "--source-intake-receipt",
                    self.receipt_relative,
                    "--exact-existing-intake",
                    "--approve",
                    "--reviewed-by",
                    REVIEWER,
                    "--format",
                    "json",
                ]
            )
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(stdout)["ok"])
        self.assertEqual(native.calls, 1)
        self.assertEqual(key_provider.calls, 0)
        self.assertEqual(self._snapshot(self.root), before)

    def test_expected_digest_and_source_drift_fail_before_selection_write(self) -> None:
        plan = self._plan()
        native = _Native(approved=True)
        key_provider = _KeyProvider()
        (self.root / Path(self.staged_relative)).write_bytes(b"changed after plan\n")
        with mock.patch.object(
            objet_capture_selection_exact,
            "_execute_exact_human_approved_write",
            side_effect=self._workflow(native, key_provider),
        ):
            code, stdout, _stderr = self._run_cli(
                [
                    "objet-capture-selection",
                    str(self.root),
                    "--staged-path",
                    self.staged_relative,
                    "--source-intake-receipt",
                    self.receipt_relative,
                    "--exact-existing-intake",
                    "--approve",
                    "--expected-plan-sha256",
                    plan.manifest.manifest_sha256,
                    "--reviewed-by",
                    REVIEWER,
                    "--format",
                    "json",
                ]
            )
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(stdout)["ok"])
        self.assertEqual(native.calls, 0)
        self.assertEqual(key_provider.calls, 0)
        self.assertFalse((self.root / Path(plan.selection_relative_path)).exists())

    def test_create_only_collision_and_exact_postimage_are_distinguished(self) -> None:
        original = self._plan()
        target = self.root / Path(original.selection_relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"unrelated collision bytes\n")

        collision = self._plan()
        self.assertFalse(collision.approveable)
        self.assertEqual(collision.state, "target_collision")
        self.assertEqual(
            collision.blockers,
            ("existing_intake_capture_selection_target_collision",),
        )
        self.assertEqual(target.read_bytes(), b"unrelated collision bytes\n")

        target.write_bytes(original.selection_bytes)
        reconciled = self._plan()
        self.assertFalse(reconciled.approveable)
        self.assertEqual(reconciled.state, "exact_target_present")
        self.assertEqual(
            reconciled.blockers,
            ("existing_intake_capture_selection_exact_target_present",),
        )
        public = json.dumps(reconciled.public_document(), sort_keys=True)
        self.assertNotIn(self.staged_relative, public)
        self.assertNotIn(self.receipt_relative, public)

    def test_parser_exposes_only_the_bounded_exact_branch(self) -> None:
        inventory = command_status.build_command_status_inventory(
            archive_cli.build_parser(),
            archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS,
        )
        row = next(
            item
            for item in inventory["commands"]
            if item["canonical_path"] == "objet-capture-selection"
        )
        self.assertEqual(row["approval_status"], "approval_available")
        self.assertEqual(
            row["approval_scope"],
            {
                "kind": "argument_flag_any_allowlist",
                "allowed_flags": ["--exact-existing-intake"],
                "outside_scope_status": "approval_fixed_closed",
                "outside_scope_reason_code": (
                    "compound_exact_human_approval_binding_required"
                ),
            },
        )


if __name__ == "__main__":
    unittest.main()
