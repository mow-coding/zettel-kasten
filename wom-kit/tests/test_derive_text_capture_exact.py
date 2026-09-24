"""2026-09-24 reopen (58-writer triage, group 6): `derive-text capture`.

Letters 033-036 attached OCR/extraction text to existing objets (3,746
links); the writer was fixed closed in v0.4.0 and only new captures could
carry a derived-text half. Approve now binds the dry-run plan digest of the
exact text, source objet, metadata and planned action: one dialog, or none
under a valid session grant. Synthetic archives only; the native dialog and
archive key are injected so no real window opens.
"""
from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wom_kit import archive_cli, archive_services, command_status, work_session_permission
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker

import test_v0421_lifecycle_batches_exact_approval as lifecycle

REVIEWER = "person:synthetic-derived-text-reviewer"


class DeriveTextCaptureExactTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-group6-")
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.root = self.tmp / "archive"
        shutil.copytree(lifecycle.KIT_ROOT / "examples" / "fake-life-archive", self.root)
        self.native = lifecycle._PagedNative()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
        stack.enter_context(patch.object(broker, "_production_key_provider", return_value=lifecycle._KeyProvider()))

    def _source(self, data: bytes) -> str:
        digest = hashlib.sha256(data).hexdigest()
        record = {
            "object_id": f"sha256:{digest}",
            "sha256": digest,
            "logical_key": f"objects/sha256/{digest[:2]}/{digest}",
            "mime": "application/pdf",
            "size_bytes": len(data),
            "locations": [],
            "provenance": {"source": "test"},
        }
        manifest = self.root / "objects" / "manifests" / "files.jsonl"
        with manifest.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")
        return record["object_id"]

    def _text(self, name: str, body: str) -> Path:
        path = self.tmp / name
        path.write_text(body, encoding="utf-8")
        return path

    def run_cli(self, *args: str) -> tuple[int, dict]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = archive_cli.main([*args, "--format", "json"])
        return code, json.loads(out.getvalue())

    def _single(self, source: str, text: Path) -> list[str]:
        return ["derive-text", "capture", str(self.root), "--text-file", str(text), "--source-object-id", source,
                "--derivation-kind", "ocr", "--tool-name", "fake-ocr", "--tool-version", "1.0",
                "--review-status", "unreviewed"]

    def _derived_lines(self) -> list[dict]:
        path = self.root / archive_services.DERIVED_TEXT_MANIFEST_RELATIVE_PATH
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def test_single_capture_writes_under_one_dialog_then_rerun_needs_none(self) -> None:
        source = self._source(b"synthetic scanned page")
        text = self._text("page.txt", "Synthetic OCR marker 20260924\n")
        before = len(self._derived_lines())
        code, preview = self.run_cli(*self._single(source, text), "--dry-run")
        self.assertEqual(code, 0, preview)
        self.assertRegex(preview["plan_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(self.native.calls, 0)

        code, result = self.run_cli(*self._single(source, text), "--approve", "--reviewed-by", REVIEWER,
                                    "--expected-plan-sha256", preview["plan_sha256"])
        self.assertEqual(code, 0, result)
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(result["action"], "captured")
        self.assertTrue(result["stored_sha256_verified"])
        self.assertTrue((self.root / result["text_logical_key"]).is_file())
        self.assertEqual(len(self._derived_lines()), before + 1)

        code, again = self.run_cli(*self._single(source, text), "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, again)
        self.assertEqual(again["write_status"], "nothing_to_write")
        self.assertEqual(self.native.calls, 1)

    def test_manifest_capture_is_one_dialog_for_all_rows(self) -> None:
        rows = []
        for index in range(3):
            source = self._source(f"synthetic source {index}".encode())
            self._text(f"t{index}.txt", f"Synthetic batch text {index}\n")
            rows.append({"item_id": f"row-{index}", "source_object_id": source, "text_file": f"t{index}.txt",
                         "derivation_kind": "parser", "tool_name": "fake-parser", "tool_version": "1.0",
                         "review_status": "unreviewed"})
        manifest = self.tmp / "ledger.jsonl"
        manifest.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        before = len(self._derived_lines())
        code, result = self.run_cli("derive-text", "capture", str(self.root), "--from-manifest", str(manifest),
                                    "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, result)
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(len(self._derived_lines()), before + 3)

    def test_a_changed_text_after_review_is_refused_before_the_dialog(self) -> None:
        source = self._source(b"synthetic page two")
        text = self._text("page.txt", "Reviewed text\n")
        code, preview = self.run_cli(*self._single(source, text), "--dry-run")
        self.assertEqual(code, 0, preview)
        text.write_text("Edited after review\n", encoding="utf-8")
        before = len(self._derived_lines())
        code, error = self.run_cli(*self._single(source, text), "--approve", "--reviewed-by", REVIEWER,
                                   "--expected-plan-sha256", preview["plan_sha256"])
        self.assertEqual(code, 1)
        self.assertEqual(error["reason_codes"], ["derived_text_capture_apply_plan_changed"])
        self.assertEqual(self.native.calls, 0)
        self.assertEqual(len(self._derived_lines()), before)

    def test_a_declined_dialog_writes_nothing(self) -> None:
        self.native.approve = False
        source = self._source(b"synthetic page three")
        text = self._text("page.txt", "Declined text\n")
        before = len(self._derived_lines())
        code, error = self.run_cli(*self._single(source, text), "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1)
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(len(self._derived_lines()), before)

    def test_the_service_stays_blocked_without_a_claim(self) -> None:
        source = self._source(b"synthetic page four")
        text = self._text("page.txt", "No claim\n")
        result = archive_services.derived_text_capture_apply(
            self.root, text_file=text, source_object_id=source, derivation_kind="ocr",
            tool_name="fake-ocr", tool_version="1.0", review_status="unreviewed", reviewed_by=REVIEWER,
        )
        self.assertEqual(result["blockers"], [command_status.COMPOUND_APPROVAL_REASON_CODE])

    def test_inventory_is_open_and_grantable(self) -> None:
        self.assertNotIn("derive-text capture", command_status.COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS)
        self.assertIn("derive-text capture", command_status.EXACT_APPROVAL_REOPENED_WRITERS)
        self.assertIn(windows.ExactHumanApprovalOperation.derived_text_capture,
                      work_session_permission.GRANTABLE_OPERATIONS)


if __name__ == "__main__":
    unittest.main()
