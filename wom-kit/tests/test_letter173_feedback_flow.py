"""Request E with letter 173 (2026-09-24): one deliverable letter, two user states.

Synthetic archives only. A new letter needs no hand-picked number, the compose
approval is the one human decision, and the ledger shows "before delivery" /
"delivered" with developer receipt kept separate.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_v0434_letter165 as _compose_fixture
from wom_kit import archive_services
from wom_kit import operator_feedback_body as body_module


class NextFeedbackIdTests(unittest.TestCase):
    def test_next_number_follows_bodies_and_records_and_ignores_other_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            letters = root / body_module.BODY_PREFIX
            letters.mkdir(parents=True)
            (letters / "wom-feedback-20260920-166.md").write_text("x\n", encoding="utf-8")
            (letters / "camp-close-session-followup-20260921.md").write_text("x\n", encoding="utf-8")
            (root / body_module.RECORD_PREFIX / "wom-feedback-20260922-172.yml").write_text("x\n", encoding="utf-8")
            with patch.object(body_module, "_local_date_stamp", return_value="20260924"):
                self.assertEqual(body_module.next_feedback_id(root), "wom-feedback-20260924-173")
            empty = root / "empty"
            empty.mkdir()
            with patch.object(body_module, "_local_date_stamp", return_value="20260924"):
                self.assertEqual(body_module.next_feedback_id(empty), "wom-feedback-20260924-001")


class OneLetterFlowTests(unittest.TestCase):
    for _name, _value in vars(_compose_fixture.FeedbackComposeExactApprovalTests).items():
        if not _name.startswith("test") and _name not in {"__module__", "__qualname__", "__doc__", "__dict__", "__weakref__"}:
            locals()[_name] = _value
    del _name, _value

    def test_new_letter_without_id_is_numbered_created_and_ledgered_before_delivery(self) -> None:
        del self.request["feedback_id"]
        self.request_path.write_text(json.dumps(self.request, ensure_ascii=False) + "\n", encoding="utf-8")
        with patch.object(body_module, "_local_date_stamp", return_value="20260924"):
            preview = self.compose("--dry-run")
            self.assertTrue(preview["feedback_id_assigned_automatically"])
            self.assertRegex(preview["feedback_id"], r"^wom-feedback-20260924-\d{3}$")
            created = self.compose("--approve", "--expected-plan-sha256", preview["plan_sha256"],
                                   "--reviewed-by", _compose_fixture.REVIEWER)
        self.assertEqual(created["feedback_id"], preview["feedback_id"])
        self.assertTrue(created["draft_record"]["record_created"], created["draft_record"])
        self.assertEqual(created["user_status_label"], "전달 전")
        self.assertFalse(created["separate_review_copy_needed"])
        ledger = archive_services.operator_feedback_ledger(self.root, dry_run=True)
        self.assertEqual(ledger["user_view"]["labels"], {"before_delivery": "전달 전", "delivered": "전달 완료"})
        self.assertEqual(ledger["user_view"]["before_delivery_count"], 1)
        self.assertEqual(ledger["user_view"]["delivered_count"], 0)
        number = int(created["feedback_id"].rsplit("-", 1)[1])
        self.assertTrue(ledger["user_view"]["next_feedback_id"].endswith(f"-{number + 1:03d}"))

    def test_explicit_id_and_revise_still_require_their_exact_inputs(self) -> None:
        preview = self.compose("--dry-run")
        self.assertFalse(preview["feedback_id_assigned_automatically"])
        self.assertEqual(preview["feedback_id"], self.request["feedback_id"])
        del self.request["feedback_id"]
        self.request_path.write_text(json.dumps(self.request, ensure_ascii=False) + "\n", encoding="utf-8")
        revise = self.compose("--dry-run", "--intent", "revise", "--expected-body-sha256", "0" * 64, ok=False)
        self.assertFalse(revise["ok"])


if __name__ == "__main__":
    unittest.main()
