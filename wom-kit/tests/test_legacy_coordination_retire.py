"""v0.4.41 (letters 142, 148, 156): retire the old coordination folder by
moving it, never deleting.

The delete-only cleanup refused collaboration records, nested Git
repositories, and a Git check that could not run, three times. Retirement
moves the whole `.mow-harness` folder to a reviewed destination in one step,
verifies it, and writes a receipt; the approval is one dialog (or a valid
session grant) bound to the plan digest. Synthetic workspace only; the native
dialog and archive key are injected so no real window opens.
"""
from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wom_kit import archive_cli, command_status, legacy_coordination_retire as retire, work_session_permission
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker

import test_v0421_lifecycle_batches_exact_approval as lifecycle

REVIEWER = "person:synthetic-retire-reviewer"


class LegacyCoordinationRetireTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-retire-")
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        self.workspace = base / "workspace"
        archive = self.workspace / "archive"
        archive.mkdir(parents=True)
        (archive / "archive.yml").write_text("archive_id: archive:personal:synthetic-retire\n", encoding="utf-8")
        (archive / "archive-identity.yml").write_text(
            "identity:\n  archive_id: archive:personal:synthetic-retire\n", encoding="utf-8")
        target = self.workspace / ".mow-harness"
        (target / "source" / ".git").mkdir(parents=True)
        (target / "source" / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        (target / "source" / "readme.txt").write_text("synthetic retired source\n", encoding="utf-8")
        (target / "collab").mkdir()
        (target / "collab" / "note.txt").write_text("synthetic collaboration record\n", encoding="utf-8")
        (target / "updates").mkdir()
        (target / "installed-version.txt").write_text("0.0.0\n", encoding="utf-8")
        self.destination = base / "preserved"
        self.destination.mkdir()
        self.native = lifecycle._PagedNative()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
        stack.enter_context(patch.object(broker, "_production_key_provider", return_value=lifecycle._KeyProvider()))

    def run_cli(self, *extra: str) -> tuple[int, dict]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = archive_cli.main(["legacy-coordination-cleanup", str(self.workspace),
                                     "--destination", str(self.destination), *extra, "--format", "json"])
        return code, json.loads(out.getvalue())

    def test_preview_keeps_collab_and_nested_repository_as_preserved_classes(self) -> None:
        code, preview = self.run_cli("--dry-run")
        self.assertEqual(code, 0, preview)
        self.assertEqual(preview["status"], "ready")
        self.assertTrue(preview["preserved_classes"]["preserved_collab"])
        self.assertTrue(preview["preserved_classes"]["preserved_nested_repository"])
        self.assertFalse(preview["deletes"])
        self.assertNotIn(str(self.workspace), json.dumps(preview))
        self.assertTrue((self.workspace / ".mow-harness").is_dir())

    @unittest.skipUnless(os.name == "nt", "approved apply is Windows-only")
    def test_approve_moves_everything_under_one_dialog_and_writes_a_receipt(self) -> None:
        code, result = self.run_cli("--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "retired")
        self.assertEqual(self.native.calls, 1)
        self.assertFalse((self.workspace / ".mow-harness").exists())
        moved = self.destination / result["destination_final_name"]
        self.assertEqual((moved / "collab" / "note.txt").read_text(encoding="utf-8"),
                         "synthetic collaboration record\n")
        self.assertTrue((moved / "source" / ".git" / "HEAD").is_file())
        receipt = json.loads((self.workspace / "archive" / result["receipt_path"]).read_text(encoding="utf-8"))
        self.assertFalse(receipt["deletes"])
        self.assertEqual(receipt["plan_sha256"], result["plan_sha256"])
        code, again = self.run_cli("--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(again["write_status"], "nothing_to_write")
        self.assertEqual(self.native.calls, 1)

    @unittest.skipUnless(os.name == "nt", "approved apply is Windows-only")
    def test_a_declined_dialog_moves_nothing(self) -> None:
        self.native.approve = False
        code, _error = self.run_cli("--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1)
        self.assertEqual(self.native.calls, 1)
        self.assertTrue((self.workspace / ".mow-harness" / "collab" / "note.txt").is_file())
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_destination_inside_the_workspace_is_refused_before_the_dialog(self) -> None:
        inside = self.workspace / "preserved-inside"
        inside.mkdir()
        self.destination = inside
        code, error = self.run_cli("--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1)
        self.assertEqual(error["reason_codes"], ["legacy_coordination_retire_preflight_blocked"])
        self.assertEqual(self.native.calls, 0)
        self.assertTrue((self.workspace / ".mow-harness").is_dir())

    def test_an_unsupported_platform_is_refused_before_the_dialog(self) -> None:
        with patch.object(retire.cleanup, "LEGACY_COORDINATION_CLEANUP_APPLY_SUPPORTED", False):
            code, error = self.run_cli("--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1)
        self.assertEqual(error["reason_codes"], ["legacy_coordination_retire_preflight_blocked"])
        self.assertIn("cleanup_apply_platform_unsupported", json.dumps(error))
        self.assertEqual(self.native.calls, 0)

    def test_the_writer_stays_blocked_without_a_claim(self) -> None:
        plan = retire.legacy_coordination_retire_plan(self.workspace, self.destination)
        result = retire.legacy_coordination_retire(
            self.workspace, self.destination, expected_plan_sha256=plan["plan_sha256"], reviewed_by=REVIEWER,
        )
        self.assertEqual(result["blockers"], [command_status.COMPOUND_APPROVAL_REASON_CODE])
        self.assertTrue((self.workspace / ".mow-harness").is_dir())

    def test_delete_only_approve_stays_fixed_closed(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = archive_cli.main(["legacy-coordination-cleanup", str(self.workspace), "--approve",
                                     "--reviewed-by", REVIEWER, "--format", "json"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out.getvalue())["reason_codes"], [command_status.COMPOUND_APPROVAL_REASON_CODE])
        self.assertIn(windows.ExactHumanApprovalOperation.legacy_coordination_retire,
                      work_session_permission.GRANTABLE_OPERATIONS)


if __name__ == "__main__":
    unittest.main()
