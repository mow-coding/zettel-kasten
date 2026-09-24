"""2026-09-24 reopen (58-writer triage, group 6): external-locator-deactivate.

Letter 116 used it to retire duplicate external locators (R-B4b-12). The
dormant writer re-derived its plan under the per-zet locator lock and refused
drift; v0.4.0 only switched it off. Approve now binds that plan digest: one
dialog, or none under a valid session grant. Synthetic archive only; the
native dialog and archive key are injected so no real window opens.
"""
from __future__ import annotations

from contextlib import ExitStack
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wom_kit import command_status, completion_workflows, work_session_permission
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker

import test_completion_workflows as fixtures
import test_v0421_lifecycle_batches_exact_approval as lifecycle

ZETTEL = "zet_20110228_fake_school_record"


class ExternalLocatorDeactivateExactTests(fixtures.CompletionWorkflowTests):
    def setUp(self) -> None:
        super().setUp()
        temporary = tempfile.TemporaryDirectory(prefix="wom-group6-locator-")
        self.addCleanup(temporary.cleanup)
        self.root = self.fake_archive(Path(temporary.name) / "archive")
        self.target = self.locator_fixture_row("a")
        self.keeper = self.locator_fixture_row("b", account_ref="reviewed-account@example.test")
        self.record = self.write_locator_record_fixture(self.root, ZETTEL, [self.target, self.keeper])
        self.native = lifecycle._PagedNative()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
        stack.enter_context(patch.object(broker, "_production_key_provider", return_value=lifecycle._KeyProvider()))

    def _args(self) -> list[str]:
        plan = completion_workflows.external_locator_deactivate_plan(
            self.root, zettel_id=ZETTEL, locator_id=str(self.target["locator_id"]),
            keep_locator_id=str(self.keeper["locator_id"]),
        )
        return ["external-locator-deactivate", str(self.root), "--zettel-id", ZETTEL,
                "--expected-plan-sha256", plan["summary"]["plan_sha256"],
                "--locator-id", str(self.target["locator_id"]),
                "--keep-locator-id", str(self.keeper["locator_id"]),
                "--reviewed-by", "person:synthetic-locator-reviewer", "--approve", "--format", "json"]

    def test_deactivates_the_reviewed_duplicate_under_one_dialog(self) -> None:
        code, output = self.run_cli(self._args())
        self.assertEqual(code, 0, output)
        self.assertEqual(self.native.calls, 1)
        stored = json.loads(self.record.read_text(encoding="utf-8"))
        self.assertEqual(stored["locators"], [{**self.target, "status": "inactive"}, self.keeper])
        self.assertNotIn(str(self.target["locator_ref"]), output)

    def test_a_declined_dialog_writes_nothing(self) -> None:
        self.native.approve = False
        before = self.record.read_bytes()
        code, _output = self.run_cli(self._args())
        self.assertEqual(code, 1)
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.record.read_bytes(), before)

    def test_the_service_stays_blocked_without_a_claim(self) -> None:
        plan = completion_workflows.external_locator_deactivate_plan(
            self.root, zettel_id=ZETTEL, locator_id=str(self.target["locator_id"]),
            keep_locator_id=str(self.keeper["locator_id"]),
        )
        result = completion_workflows.external_locator_deactivate(
            self.root, zettel_id=ZETTEL, locator_id=str(self.target["locator_id"]),
            keep_locator_id=str(self.keeper["locator_id"]),
            expected_plan_sha256=plan["summary"]["plan_sha256"], reviewed_by="person:synthetic-locator-reviewer",
        )
        self.assertEqual(result["blockers"], [command_status.COMPOUND_APPROVAL_REASON_CODE])

    def test_inventory_is_open_and_grantable(self) -> None:
        self.assertNotIn("external-locator-deactivate", command_status.COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS)
        self.assertIn("external-locator-deactivate", command_status.EXACT_APPROVAL_REOPENED_WRITERS)
        self.assertIn(windows.ExactHumanApprovalOperation.external_locator_deactivate,
                      work_session_permission.GRANTABLE_OPERATIONS)


def load_tests(loader, tests, pattern):  # only this module's tests, not the inherited suite
    return loader.loadTestsFromNames(
        [f"{__name__}.ExternalLocatorDeactivateExactTests.{name}" for name in (
            "test_deactivates_the_reviewed_duplicate_under_one_dialog",
            "test_a_declined_dialog_writes_nothing",
            "test_the_service_stays_blocked_without_a_claim",
            "test_inventory_is_open_and_grantable",
        )]
    )


if __name__ == "__main__":
    unittest.main()
