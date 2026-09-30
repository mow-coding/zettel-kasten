"""v0.4.54 (owner decision 2026-09-30): delivered feedback letters are deleted, not moved.

"정리" of delivered or resolved letters means deleting them from the PC. The
v0.4.36 move (operator-feedback-archive) is retired; operator-feedback-delete
removes the letter, its body receipts and any copy the move left outside the
archive, and keeps only a one-line deleted record.

Synthetic archive, fake dialog; no client data.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from wom_kit import archive_cli, archive_services
from wom_kit import work_session_permission as permission
from wom_kit.exact_human_approval_windows import ExactHumanApprovalOperation

import test_v0433_object_storage_upload as _upload_fixture

REVIEWER = _upload_fixture.REVIEWER
TITLE = "synthetic letter title"


class FeedbackDeleteTests(unittest.TestCase):
    """Borrows the v0.4.33 CLI fixture (fake dialog, key provider, memory transport) without its tests."""

    for _name, _value in vars(_upload_fixture.UploadCliTests).items():
        if not _name.startswith("test") and _name not in {"__module__", "__qualname__", "__doc__", "__dict__", "__weakref__"}:
            locals()[_name] = _value
    del _name, _value

    def _letter(self, feedback_id: str, status: str, *, body: bool = True, receipt: bool = True) -> bytes:
        root = self.archive.root
        raw = (
            f"# {feedback_id}\n\n<!-- wom-kit/operator-feedback-body/v0.1 -->\n\nFeedback ID: `{feedback_id}`\n\n## 1. body\n\nsynthetic\n"
        ).encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        (root / "ops" / "feedback" / "letters").mkdir(parents=True, exist_ok=True)
        if body:
            (root / "ops" / "feedback" / "letters" / f"{feedback_id}.md").write_bytes(raw)
        record = {"feedback_id": feedback_id, "feedback_ref": f"feedback-body-sha256:{digest}", "status": status,
                  "title": TITLE, "delivered_at": "2026-09-20T00:00:00Z", "updated_at": "2026-09-20T00:00:00Z"}
        self._write_record(feedback_id, record)
        if receipt and body:
            receipt_dir = root / "receipts" / "operator-feedback" / "body"
            receipt_dir.mkdir(parents=True, exist_ok=True)
            (receipt_dir / f"{feedback_id}.{digest[:16]}.json").write_text(
                json.dumps({"schema": "wom-kit/operator-feedback-body-receipt/v0.1", "feedback_id": feedback_id}), encoding="utf-8")
            (receipt_dir / "revisions" / feedback_id).mkdir(parents=True, exist_ok=True)
            (receipt_dir / "revisions" / feedback_id / "old.md").write_bytes(b"older body\n")
        return raw

    def _write_record(self, feedback_id: str, record: dict) -> None:
        path = self.archive.root / "ops" / "feedback" / f"{feedback_id}.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(archive_services.dump_yaml(record), encoding="utf-8")

    def _record(self, feedback_id: str) -> dict:
        path = self.archive.root / "ops" / "feedback" / f"{feedback_id}.yml"
        return archive_services.load_yaml(path.read_text(encoding="utf-8"))

    def _moved_by_v0436(self, folder: Path, feedback_id: str) -> bytes:
        """The layout the retired operator-feedback-archive left: a stub inside, the bytes outside."""

        raw = f"# {feedback_id}\n\nmoved letter\n".encode("utf-8")
        copy = folder / feedback_id
        (copy / "receipts").mkdir(parents=True)
        (copy / f"{feedback_id}.md").write_bytes(raw)
        (copy / "receipts" / f"{feedback_id}.0123456789abcdef.json").write_text("{}", encoding="utf-8")
        (copy / "receipts" / f"revisions__{feedback_id}__old.md").write_bytes(b"older\n")
        self._write_record(feedback_id, {
            "feedback_id": feedback_id, "status": "archived", "title": TITLE,
            "feedback_ref": "feedback-body-sha256:" + hashlib.sha256(raw).hexdigest(),
            "archived_at": "2026-09-22T00:00:00Z", "archived_from_status": "delivered",
            "body_sha256": hashlib.sha256(raw).hexdigest(), "body_utf8_bytes": len(raw), "receipt_count": 2,
            "destination_sha256": "0" * 64, "archived_body_relative": f"{feedback_id}/{feedback_id}.md",
            "updated_at": "2026-09-22T00:00:00Z",
        })
        return raw

    def _run(self, *args: str) -> tuple[int, dict]:
        return self.run_cli("operator-feedback-delete", str(self.archive.root), *args)

    def _approve(self, plan: dict, *extra: str) -> tuple[int, dict]:
        return self._run(*extra, "--approve", "--reviewed-by", REVIEWER, "--expected-plan-sha256", plan["plan_sha256"])

    def test_delivered_letters_are_deleted_and_only_a_one_line_record_stays(self) -> None:
        root = self.archive.root
        raw_a = self._letter("wom-feedback-20260901-101", "delivered")
        raw_b = self._letter("wom-feedback-20260902-102", "resolved")
        self._letter("wom-feedback-20260903-103", "draft")
        self._letter("wom-feedback-20260904-104", "acknowledged", body=False)
        code, plan = self._run("--dry-run")
        self.assertEqual(code, 0, plan)
        self.assertEqual(plan["state"], "ready_for_exact_human_approval")
        self.assertEqual(plan["feedback_ids"], ["wom-feedback-20260901-101", "wom-feedback-20260902-102",
                                                "wom-feedback-20260904-104"])
        self.assertEqual(plan["receipt_count_total"], 4)
        self.assertEqual(plan["skipped"]["other_status"], 1)
        self.assertFalse(plan["recoverable"])
        self.assertGreaterEqual(plan["bytes_freed_total"], len(raw_a) + len(raw_b))
        self.assertEqual(self.native.calls, 0)
        code, result = self._approve(plan)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["state"], "deleted")
        self.assertEqual(result["deleted_count"], 3)
        self.assertEqual(result["receipts_deleted"], 4)
        self.assertEqual(result["bytes_freed"], plan["bytes_freed_total"])
        self.assertEqual(self.native.calls, 1)
        context = self.native.contexts[0]
        self.assertIn("편지 삭제", str(context.get("approve_button_text")) + str(context.get("main_instruction")))
        # the letters and receipts are gone; nothing was copied anywhere
        letters = root / "ops" / "feedback" / "letters"
        self.assertEqual(sorted(p.name for p in letters.iterdir()), ["wom-feedback-20260903-103.md"])
        body_receipts = root / "receipts" / "operator-feedback" / "body"
        self.assertEqual(sorted(p.name for p in body_receipts.glob("*.json")), ["wom-feedback-20260903-103." +
                         hashlib.sha256((letters / "wom-feedback-20260903-103.md").read_bytes()).hexdigest()[:16] + ".json"])
        self.assertFalse((body_receipts / "revisions" / "wom-feedback-20260901-101").exists())
        # the record says only "letter N deleted": no title, no body reference
        record = self._record("wom-feedback-20260901-101")
        self.assertEqual(set(record), {"feedback_id", "status", "deleted_at", "deleted_from_status", "updated_at"})
        self.assertEqual(record["status"], "deleted")
        self.assertEqual(record["deleted_from_status"], "delivered")
        self.assertEqual(self._record("wom-feedback-20260903-103")["status"], "draft")
        receipt = json.loads((root / result["receipt_relative_path"]).read_text(encoding="utf-8"))
        self.assertEqual(receipt["deleted_feedback_ids"], result["deleted_feedback_ids"])
        self.assertEqual(receipt["exact_human_approval"]["approval_id"], result["exact_human_approval"]["approval_id"])
        rendered = "".join(self.outputs) + json.dumps(self.native.contexts, ensure_ascii=False)
        self.assertNotIn(TITLE, rendered)
        self.assertNotIn(str(root), rendered)
        # the ledger counts them, the body check recognises them, numbering continues
        code, ledger = self.run_cli("operator-feedback-ledger", str(root), "--dry-run")
        self.assertEqual(code, 0, ledger)
        self.assertEqual(ledger["counts"]["deleted"], 3)
        self.assertEqual(ledger["counts"]["unknown_status"], 0)
        self.assertEqual(ledger["user_view"]["deleted_count"], 3)
        self.assertEqual(ledger["user_view"]["delivered_count"], 3)
        self.assertNotEqual(ledger["user_view"]["next_feedback_id"][-3:], "102")
        code, check = self.run_cli("operator-feedback-body-check", str(root), "--feedback-id", "wom-feedback-20260901-101", "--dry-run")
        self.assertEqual(code, 0, check)
        self.assertEqual(check["state"], "deleted_record")
        self.assertIsNone(check["feedback_ref"])
        # a second plan finds nothing left
        code, again = self._run("--dry-run")
        self.assertEqual(code, 1, again)
        self.assertEqual(again["blockers"], ["feedback_delete_nothing_to_delete"])
        self.assertEqual(again["skipped"]["already_deleted"], 3)

    def test_letters_moved_out_by_v0436_are_deleted_when_their_folder_is_named(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "ops-feedback-archive"
            self._moved_by_v0436(folder, "wom-feedback-20260901-101")
            self._moved_by_v0436(folder, "wom-feedback-20260902-102")
            # without the folder the moved letters are named, not silently kept
            code, plan = self._run("--dry-run")
            self.assertEqual(code, 1, plan)
            self.assertEqual(plan["blockers"], ["feedback_delete_nothing_to_delete"])
            self.assertEqual(plan["skipped"]["moved_letter_needs_moved_folder"], 2)
            self.assertTrue(any("--moved-folder" in line for line in plan["next_safe_actions"]))
            code, plan = self._run("--moved-folder", str(folder), "--dry-run")
            self.assertEqual(code, 0, plan)
            self.assertEqual(plan["status_counts"]["archived"], 2)
            self.assertEqual(plan["moved_copy_count"], 2)
            self.assertEqual(plan["moved_file_count"], 6)
            self.assertNotIn(str(folder), "".join(self.outputs))
            code, result = self._approve(plan, "--moved-folder", str(folder))
            self.assertEqual(code, 0, result)
            self.assertEqual(result["moved_files_deleted"], 6)
            self.assertFalse(folder.exists())
            record = self._record("wom-feedback-20260901-101")
            self.assertEqual(record["status"], "deleted")
            self.assertEqual(record["deleted_from_status"], "archived")
            self.assertNotIn("body_sha256", record)

    def test_a_changed_moved_copy_and_unknown_files_are_left_alone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "moved"
            self._moved_by_v0436(folder, "wom-feedback-20260901-101")
            self._moved_by_v0436(folder, "wom-feedback-20260902-102")
            (folder / "wom-feedback-20260901-101" / "wom-feedback-20260901-101.md").write_bytes(b"edited by hand\n")
            (folder / "wom-feedback-20260902-102" / "notes.txt").write_bytes(b"operator notes\n")
            code, plan = self._run("--moved-folder", str(folder), "--dry-run")
            self.assertEqual(code, 0, plan)
            self.assertEqual(plan["feedback_ids"], ["wom-feedback-20260902-102"])
            self.assertEqual(plan["skipped"]["moved_copy_changed"], 1)
            code, result = self._approve(plan, "--moved-folder", str(folder))
            self.assertEqual(code, 0, result)
            self.assertEqual((folder / "wom-feedback-20260901-101" / "wom-feedback-20260901-101.md").read_bytes(), b"edited by hand\n")
            self.assertEqual((folder / "wom-feedback-20260902-102" / "notes.txt").read_bytes(), b"operator notes\n")
            self.assertFalse((folder / "wom-feedback-20260902-102" / "wom-feedback-20260902-102.md").exists())
            self.assertEqual(self._record("wom-feedback-20260901-101")["status"], "archived")

    def test_bad_folders_and_a_changed_plan_are_refused_before_the_dialog(self) -> None:
        self._letter("wom-feedback-20260901-101", "delivered")
        code, inside = self._run("--moved-folder", str(self.archive.root / "ops"), "--dry-run")
        self.assertEqual(code, 1, inside)
        self.assertEqual(inside["blockers"], ["feedback_delete_moved_folder_inside_archive"])
        code, relative = self._run("--moved-folder", "relative/folder", "--dry-run")
        self.assertEqual(relative["blockers"], ["feedback_delete_moved_folder_invalid"])
        with tempfile.TemporaryDirectory() as tmp:
            code, missing = self._run("--moved-folder", str(Path(tmp) / "absent"), "--dry-run")
            self.assertEqual(missing["blockers"], ["feedback_delete_moved_folder_missing"])
        code, plan = self._run("--dry-run")
        self.assertEqual(code, 0, plan)
        code, refused = self._run("--approve", "--reviewed-by", REVIEWER, "--expected-plan-sha256", "0" * 64)
        self.assertEqual(code, 1, refused)
        self.assertEqual(refused["reason_codes"], ["feedback_delete_plan_changed"])
        self._letter("wom-feedback-20260902-102", "delivered")
        code, refused = self._approve(plan)
        self.assertEqual(code, 1, refused)
        self.assertEqual(refused["reason_codes"], ["feedback_delete_plan_changed"])
        self.assertEqual(self.native.calls, 0)
        self.assertTrue((self.archive.root / "ops" / "feedback" / "letters" / "wom-feedback-20260901-101.md").exists())

    def test_files_left_by_an_interrupted_run_are_finished(self) -> None:
        self._letter("wom-feedback-20260901-101", "delivered")
        self._write_record("wom-feedback-20260901-101", {
            "feedback_id": "wom-feedback-20260901-101", "status": "deleted", "deleted_at": "2026-09-30T00:00:00Z",
            "deleted_from_status": "delivered", "updated_at": "2026-09-30T00:00:00Z",
        })
        code, plan = self._run("--dry-run")
        self.assertEqual(code, 0, plan)
        self.assertEqual(plan["feedback_ids"], ["wom-feedback-20260901-101"])
        code, result = self._approve(plan)
        self.assertEqual(code, 0, result)
        self.assertFalse((self.archive.root / "ops" / "feedback" / "letters" / "wom-feedback-20260901-101.md").exists())
        self.assertEqual(self._record("wom-feedback-20260901-101")["deleted_from_status"], "delivered")

    def test_the_move_command_is_retired_and_the_delete_kind_is_grantable(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            code = archive_cli.main(["operator-feedback-archive", str(self.archive.root), "--destination", "x", "--dry-run"])
        self.assertEqual(code, 2)
        from wom_kit import exact_human_approval_windows as windows
        kind = ExactHumanApprovalOperation.operator_feedback_delete
        self.assertIn(kind, permission.GRANTABLE_OPERATIONS)
        for table in (windows._OPERATION_LABELS, windows._OPERATION_QUESTIONS, windows._OPERATION_SUMMARIES,
                      windows._OPERATION_APPROVE_BUTTONS):
            self.assertIn(kind, table)
        self.assertTrue(windows._OPERATION_QUESTIONS[kind].endswith("까요?"))
        self.assertIn("삭제", windows._OPERATION_QUESTIONS[kind])


if __name__ == "__main__":
    unittest.main()
