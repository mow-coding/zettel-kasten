"""v0.4.41 (letter 141): import-external --approve runs again.

Until v0.4.40 the write was fixed closed; the customer had used it for 437
notes before. Now the dry-run prints a plan digest over the exact items and
`--approve` creates the inbox drafts and the import receipt after one exact
approval bound to it. The native dialog and archive key are injected.
"""
from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wom_kit import archive_cli, archive_services, command_status
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker

import test_v0421_lifecycle_batches_exact_approval as lifecycle

REVIEWER = "person:synthetic-import-reviewer"


class ImportExternalExactTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-import-")
        self.addCleanup(temporary.cleanup)
        tmp = Path(temporary.name)
        self.root = tmp / "archive"
        shutil.copytree(lifecycle.KIT_ROOT / "examples" / "fake-life-archive", self.root)
        self.export = tmp / "export"
        self.export.mkdir()
        (self.export / "first.md").write_text("# First synthetic note\n\nA plain body.\n", encoding="utf-8")
        (self.export / "second.md").write_text("# Second synthetic note\n\nAnother body.\n", encoding="utf-8")
        self.native = lifecycle._PagedNative()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
        stack.enter_context(patch.object(broker, "_production_key_provider", return_value=lifecycle._KeyProvider()))

    def run_cli(self, *args: str) -> tuple[int, dict]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = archive_cli.main(["import-external", str(self.root), "--source", "google_drive",
                                     "--export", str(self.export), *args, "--format", "json"])
        return code, json.loads(out.getvalue())

    def test_approve_creates_the_reviewed_drafts_after_one_dialog(self) -> None:
        code, plan = self.run_cli("--dry-run")
        self.assertEqual(code, 0, plan)
        self.assertRegex(plan["plan_sha256"], r"^sha256:[0-9a-f]{64}$")
        code, result = self.run_cli("--approve", "--reviewed-by", REVIEWER,
                                    "--expected-plan-sha256", plan["plan_sha256"])
        self.assertEqual(code, 0, result)
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(result["imported_count"], 2)
        for relative in result["created_paths"]:
            self.assertTrue((self.root / relative).is_file(), relative)

    def test_a_changed_export_is_refused_before_the_dialog(self) -> None:
        _code, plan = self.run_cli("--dry-run")
        (self.export / "third.md").write_text("# Third\n\nLate addition.\n", encoding="utf-8")
        code, error = self.run_cli("--approve", "--reviewed-by", REVIEWER,
                                   "--expected-plan-sha256", plan["plan_sha256"])
        self.assertEqual(code, 1)
        self.assertEqual(error["reason_codes"], ["import_external_archive_plan_changed"])
        self.assertEqual(self.native.calls, 0)

    def test_a_declined_dialog_writes_nothing(self) -> None:
        before = sorted(path.name for path in (self.root / "inbox").iterdir())
        self.native.approve = False
        code, _error = self.run_cli("--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1)
        self.assertEqual(sorted(path.name for path in (self.root / "inbox").iterdir()), before)

    def test_the_service_stays_blocked_without_a_claim(self) -> None:
        result = archive_services.import_external_archive(
            self.root, self.export, source_system="google_drive", reviewed_by=REVIEWER,
        )
        self.assertEqual(result["reason_codes"], [command_status.COMPOUND_APPROVAL_REASON_CODE])

    def test_inventory_is_open(self) -> None:
        self.assertNotIn("import-external", command_status.COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS)


if __name__ == "__main__":
    unittest.main()
