"""2026-09-24 reclassification (58-writer triage): the two title-remap
recovery executors move from Retire to Reopen.

No newer command adopts a legacy interrupted title-remap journal or lock, so
these executors are the only way to finish or roll back such a case. They now
run under exact approval like the other reopened writers: one dialog, or none
under a valid session grant. The CLI round trip (declined writes nothing,
approved recovers once) is in test_cli's title-remap recovery tests.
"""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wom_kit import archive_services, command_status, work_session_permission
from wom_kit import exact_human_approval_windows as windows

KIT_ROOT = Path(__file__).resolve().parents[1]
NAMES = ("zet-title-remap-recover", "zet-title-remap-revert-recover")


class TitleRemapRecoverExactTests(unittest.TestCase):
    def test_inventory_is_open_and_grantable(self) -> None:
        for name in NAMES:
            self.assertNotIn(name, command_status.COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS)
            self.assertIn(name, command_status.EXACT_APPROVAL_REOPENED_WRITERS)
            operation = windows.ExactHumanApprovalOperation(name.replace("-", "_"))
            self.assertIn(operation, work_session_permission.GRANTABLE_OPERATIONS)
            for table in (
                windows._OPERATION_LABELS,
                windows._OPERATION_QUESTIONS,
                windows._OPERATION_SUMMARIES,
                windows._OPERATION_APPROVE_BUTTONS,
            ):
                self.assertTrue(table[operation].strip())

    def test_the_service_stays_blocked_without_a_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", root)
            for service, action in (
                (archive_services.zet_title_remap_recover, "zet_title_remap_recover"),
                (archive_services.zet_title_remap_revert_recover, "zet_title_remap_revert_recover"),
            ):
                with self.subTest(action=action):
                    result = service(
                        root,
                        case_sha256="sha256:" + "a" * 64,
                        expected_plan_digest="sha256:" + "b" * 64,
                        expected_action="rollback",
                        dry_run=False,
                        approve=True,
                        reviewed_by="person:synthetic-title-reviewer",
                        affirm_recovery_reviewed=True,
                        affirm_archive_quiescent=True,
                    )
                    self.assertFalse(result["ok"])
                    self.assertEqual(result["blockers"], [command_status.COMPOUND_APPROVAL_REASON_CODE])


if __name__ == "__main__":
    unittest.main()
