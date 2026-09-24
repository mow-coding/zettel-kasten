"""2026-09-24 reopen (58-writer triage, group 6): saved views.

Letter 147 listed `saved-view-write` among the commands it needed. The
writer and its revert already re-derived their plan under a lock and refused
drift; v0.4.0 only switched them off. They now run under exact approval bound
to that plan digest: one dialog, or none under a valid session grant.
Synthetic archives only; the native dialog and archive key are injected so no
real window opens.
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

from wom_kit import archive_cli, archive_services, command_status, saved_view_workflows, work_session_permission
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker

import test_v0421_lifecycle_batches_exact_approval as lifecycle

REVIEWER = "person:synthetic-view-reviewer"
PRIVATE_NAME = "Synthetic Private View Name"
PRIVATE_VALUE = "synthetic-private-domain"
KIT_ROOT = Path(__file__).resolve().parents[1]


def _archive(root: Path) -> Path:
    shutil.copytree(KIT_ROOT / "templates" / "personal", root)
    shutil.copytree(KIT_ROOT / "zettel-kasten", root / "zettel-kasten")
    (root / "views").mkdir(exist_ok=True)
    (root / "zettels").mkdir(exist_ok=True)
    frontmatter = {
        "id": "zet_20260924_saved_view",
        "title": "Synthetic title",
        "status": "canonical",
        "kind": "note",
        "facets": {"domain": PRIVATE_VALUE, "record_type": "memory"},
    }
    (root / "zettels" / "zet_20260924_saved_view.md").write_text(
        "---\n" + archive_services.dump_yaml(frontmatter) + "---\n\nSynthetic body.\n", encoding="utf-8",
    )
    assert archive_services.index_archive(root)["ok"] is True
    return root


def _request(root: Path) -> str:
    relative = ".wom-scratch/private/saved-views/synthetic.json"
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema": saved_view_workflows.SAVED_VIEW_WRITE_REQUEST_SCHEMA,
        "view_id": "view.ai.synthetic",
        "name": PRIVATE_NAME,
        "filters": {"facets.domain": PRIVATE_VALUE},
    }), encoding="utf-8")
    return relative


class SavedViewExactTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-group6-view-")
        self.addCleanup(temporary.cleanup)
        self.root = _archive(Path(temporary.name) / "archive")
        self.request = _request(self.root)
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

    def test_write_then_revert_each_under_one_dialog(self) -> None:
        base = ["saved-view-write", str(self.root), "--request", self.request]
        code, error = self.run_cli(*base, "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(error["reason_codes"], ["saved_view_write_review_affirmation_required"])
        self.assertEqual(self.native.calls, 0)

        code, result = self.run_cli(*base, "--approve", "--reviewed-by", REVIEWER, "--affirm-view-reviewed")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["state"], "created")
        self.assertEqual(self.native.calls, 1)
        target, receipt = result["files_written"]
        self.assertIn(PRIVATE_NAME, (self.root / target).read_text(encoding="utf-8"))
        self.assertNotIn(PRIVATE_VALUE, json.dumps(result))

        code, again = self.run_cli(*base, "--approve", "--reviewed-by", REVIEWER, "--affirm-view-reviewed")
        self.assertEqual(code, 0, again)
        self.assertEqual(again["write_status"], "nothing_to_write")
        self.assertEqual(self.native.calls, 1)

        code, reverted = self.run_cli("saved-view-revert", str(self.root), "--receipt", receipt,
                                      "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, reverted)
        self.assertEqual(reverted["state"], "reverted")
        self.assertEqual(self.native.calls, 2)
        self.assertFalse((self.root / target).exists())

    def test_a_declined_dialog_writes_nothing(self) -> None:
        self.native.approve = False
        before = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_file())
        code, error = self.run_cli("saved-view-write", str(self.root), "--request", self.request,
                                   "--approve", "--reviewed-by", REVIEWER, "--affirm-view-reviewed")
        self.assertEqual(code, 1)
        self.assertEqual(self.native.calls, 1)
        after = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_file())
        self.assertEqual(after, before)

    def test_the_services_stay_blocked_without_a_claim(self) -> None:
        plan = saved_view_workflows.saved_view_write_plan(self.root, request_path=self.request)
        result = saved_view_workflows.saved_view_write(
            self.root, request_path=self.request, expected_plan_sha256=plan["summary"]["plan_sha256"],
            reviewed_by=REVIEWER, affirm_view_reviewed=True,
        )
        self.assertEqual(result["blockers"], [command_status.COMPOUND_APPROVAL_REASON_CODE])

    def test_inventory_is_open_and_grantable(self) -> None:
        for name in ("saved-view-write", "saved-view-revert"):
            self.assertNotIn(name, command_status.COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS)
            self.assertIn(name, command_status.EXACT_APPROVAL_REOPENED_WRITERS)
            self.assertIn(windows.ExactHumanApprovalOperation(name.replace("-", "_")),
                          work_session_permission.GRANTABLE_OPERATIONS)


if __name__ == "__main__":
    unittest.main()
