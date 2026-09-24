"""2026-09-24 reopen (58-writer triage, group 6): project-bytecode-repair.

Letter 129 hit update collisions; this writer deletes only the untracked
.pyc/.pyo files and empty __pycache__ folders an update left behind. The
approval is recorded in the project's archive and binds the repair plan
digest; the legacy engine re-derives the plan and refuses drift. Synthetic
project only; the native dialog and archive key are injected so no real
window opens.
"""
from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wom_kit import archive_cli, command_status, completion_workflows, work_session_permission
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker

import test_completion_workflows as fixtures
import test_v0421_lifecycle_batches_exact_approval as lifecycle

REVIEWER = "person:synthetic-bytecode-reviewer"


class ProjectBytecodeRepairExactTests(unittest.TestCase):
    def setUp(self) -> None:
        case = fixtures.CompletionWorkflowTests("runTest")
        case.setUp()
        self.addCleanup(case.doCleanups)
        temporary = tempfile.TemporaryDirectory(prefix="wom-group6-bytecode-")
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name) / "project"
        _mirror, self.bytecode, _source = case.project_mirror_fixture(self.project)
        archive = self.project / "archive"
        archive.mkdir()
        (archive / "archive.yml").write_text("archive_id: synthetic-bytecode-project\n", encoding="utf-8")
        self.native = lifecycle._PagedNative()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
        stack.enter_context(patch.object(broker, "_production_key_provider", return_value=lifecycle._KeyProvider()))

    def run_cli(self, *args: str) -> tuple[int, dict]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = archive_cli.main([*args, "--format", "json"])
        return code, json.loads(out.getvalue())

    def _plan_sha(self) -> str:
        plan = completion_workflows.project_bytecode_repair_plan(self.project, max_files=100)
        self.assertTrue(plan["ok"], plan)
        return plan["summary"]["plan_sha256"]

    def _args(self, *extra: str) -> list[str]:
        return ["project-bytecode-repair", str(self.project), "--max-files", "100",
                "--expected-plan-sha256", self._plan_sha(), "--reviewed-by", REVIEWER, "--approve", *extra]

    def test_repairs_under_one_dialog(self) -> None:
        code, error = self.run_cli(*self._args())
        self.assertEqual(error["reason_codes"], ["project_bytecode_repair_quiescence_required"])
        self.assertEqual(self.native.calls, 0)
        code, result = self.run_cli(*self._args("--affirm-external-writers-quiescent"))
        self.assertEqual(code, 0, result)
        self.assertEqual(self.native.calls, 1)
        self.assertFalse(self.bytecode.exists())

    def test_a_declined_dialog_deletes_nothing(self) -> None:
        self.native.approve = False
        original = self.bytecode.read_bytes()
        code, _result = self.run_cli(*self._args("--affirm-external-writers-quiescent"))
        self.assertEqual(code, 1)
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.bytecode.read_bytes(), original)

    def test_the_service_stays_blocked_without_a_claim(self) -> None:
        result = completion_workflows.project_bytecode_repair(
            self.project, max_files=100, expected_plan_sha256=self._plan_sha(), reviewed_by=REVIEWER,
            affirm_external_writers_quiescent=True,
        )
        self.assertEqual(result["blockers"], [command_status.COMPOUND_APPROVAL_REASON_CODE])
        self.assertTrue(self.bytecode.exists())

    def test_inventory_is_open_and_grantable(self) -> None:
        self.assertNotIn("project-bytecode-repair", command_status.COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS)
        self.assertIn("project-bytecode-repair", command_status.EXACT_APPROVAL_REOPENED_WRITERS)
        self.assertIn(windows.ExactHumanApprovalOperation.project_bytecode_repair,
                      work_session_permission.GRANTABLE_OPERATIONS)


if __name__ == "__main__":
    unittest.main()
