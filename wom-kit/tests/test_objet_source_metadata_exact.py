"""2026-09-24 reopen (58-writer triage, group 6): objet-source-metadata-write.

Letter 105 asked to find an objet by its original filename. The private
metadata engine already bound the intake digest and its own plan digest and
re-derived both under its lock; v0.4.0 only switched approve off. Approve now
binds that plan digest: one dialog, or none under a valid session grant.
Synthetic archive only; the native dialog and archive key are injected so no
real window opens. The engine's approval path is Windows-only.
"""
from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wom_kit import archive_cli, archive_services, command_status, work_session_permission
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker

import test_v0421_lifecycle_batches_exact_approval as lifecycle
import test_v03296_private_metadata_writer_approval as engine

REVIEWER = "operator:synthetic-metadata-reviewer"


class ObjetSourceMetadataExactTests(engine.PrivateMetadataWriterApprovalTests):
    # Reuse only the synthetic archive fixture; the engine's own tests stay there.
    def setUp(self) -> None:
        super().setUp()
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

    def _base(self) -> list[str]:
        return ["objet-source-metadata-write", str(self.root), "--intake", self.intake_relative,
                "--expected-intake-sha256", self.intake_sha256]

    def test_approve_appends_once_under_one_dialog(self) -> None:
        code, error = self.run_cli(*self._base(), "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(error["reason_codes"], ["private_objet_source_metadata_write_review_affirmation_required"])
        self.assertEqual(self.native.calls, 0)
        code, error = self.run_cli(*self._base(), "--approve", "--reviewed-by", "person:bad id",
                                   "--affirm-private-metadata-reviewed", "--affirm-external-writers-quiescent")
        self.assertEqual(error["reason_codes"], ["private_objet_source_metadata_write_reviewer_required"])
        self.assertEqual(self.native.calls, 0)
        code, result = self.run_cli(*self._base(), "--approve", "--reviewed-by", REVIEWER,
                                    "--affirm-private-metadata-reviewed", "--affirm-external-writers-quiescent")
        self.assertEqual(code, 0, result)
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self._dry_run()["action"], "already_applied")
        code, again = self.run_cli(*self._base(), "--approve", "--reviewed-by", REVIEWER,
                                   "--affirm-private-metadata-reviewed", "--affirm-external-writers-quiescent")
        self.assertEqual(code, 0, again)
        self.assertEqual(again["write_status"], "nothing_to_write")
        self.assertEqual(self.native.calls, 1)

    def test_a_declined_dialog_writes_nothing(self) -> None:
        self.native.approve = False
        code, error = self.run_cli(*self._base(), "--approve", "--reviewed-by", REVIEWER,
                                   "--affirm-private-metadata-reviewed", "--affirm-external-writers-quiescent")
        self.assertEqual(code, 1)
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self._dry_run()["action"], "append")

    def test_the_service_stays_blocked_without_a_claim(self) -> None:
        result = archive_services.private_objet_source_metadata_write(
            self.root, intake=self.intake_relative, expected_intake_sha256=self.intake_sha256,
            expected_plan_sha256=self._dry_run()["plan_sha256"], dry_run=False, approve=True,
            reviewed_by=REVIEWER, affirm_private_metadata_reviewed=True, affirm_external_writers_quiescent=True,
        )
        self.assertEqual(result["blockers"], [command_status.COMPOUND_APPROVAL_REASON_CODE])

    def test_inventory_is_open_and_grantable(self) -> None:
        self.assertNotIn("objet-source-metadata-write", command_status.COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS)
        self.assertIn("objet-source-metadata-write", command_status.EXACT_APPROVAL_REOPENED_WRITERS)
        self.assertIn(windows.ExactHumanApprovalOperation.private_objet_source_metadata_write,
                      work_session_permission.GRANTABLE_OPERATIONS)


def load_tests(loader, tests, pattern):  # only this module's tests, not the inherited engine suite
    return loader.loadTestsFromNames(
        [f"{__name__}.ObjetSourceMetadataExactTests.{name}" for name in (
            "test_approve_appends_once_under_one_dialog",
            "test_a_declined_dialog_writes_nothing",
            "test_the_service_stays_blocked_without_a_claim",
            "test_inventory_is_open_and_grantable",
        )]
    )


if __name__ == "__main__":
    unittest.main()
