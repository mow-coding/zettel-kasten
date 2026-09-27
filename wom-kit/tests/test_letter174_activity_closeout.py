"""Scoped completion is backed by original cleanup and preservation evidence."""
import json
import os
import unittest
from unittest.mock import patch

from wom_kit import activity_cleanup as cleanup, activity_closeout as closeout
from wom_kit import archive_services as services
from . import test_activity_cleanup as fixture


class ActivityCloseoutTests(unittest.TestCase):
    def setUp(self):
        self.case = fixture.ActivityCleanupTests("runTest")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        original = cleanup.plan
        self.patcher = patch.object(cleanup, "plan", side_effect=lambda *args, **kwargs:
            original(*args, **{**kwargs, "key_provider": self.case.key}))
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def result(self):
        return closeout.evidence(self.case.root, [self.case.request])

    def record_body(self, item, journal):
        journal.write("item-" + str(item["number"]) + "-preserved", {
            "object_id": item["object_id"], "size": item["state"]["size"],
            "state": "remote_verified", "source_link_preserved": True})

    @unittest.skipUnless(os.name == "nt", "native cleanup")
    def test_partial_then_complete_and_checkpoint_digest_tracks_evidence(self):
        candidate = self.case.plan()
        candidate["journal"].write("intent", candidate["material"])
        before = self.result()
        self.assertEqual(before["state"], "partial")
        handoff_before = services.session_handoff_checkpoint(self.case.root, dry_run=True,
            cleanup_requests=[str(self.case.request)])
        self.case.backend.preserve.side_effect = self.record_body
        self.assertTrue(self.case.execute(candidate)["ok"])
        after = self.result()
        self.assertEqual(after["state"], "complete", after)
        handoff_after = services.session_handoff_checkpoint(self.case.root, dry_run=True,
            cleanup_requests=[str(self.case.request)])
        self.assertNotEqual(handoff_before["state_digest"], handoff_after["state_digest"])
        self.assertEqual(handoff_after["activity_closeout"]["state"], "complete")
        # Other handoff prerequisites still apply; cleanup cannot waive them.
        self.assertFalse(handoff_after["ready_for_context_reset"])
        self.assertFalse(after["whole_archive_completion_claimed"])
        self.assertFalse(after["customer_acceptance_confirmed"])
        self.assertFalse(after["requests"][0]["recorded_backup"]["remote_bytes_verified_now"])
        self.assertNotIn(str(self.case.base), json.dumps(after))
        self.assertNotIn("PRIVATE_SYNTHETIC", json.dumps(after))

    def test_missing_original_evidence_is_development_wait_not_unexecuted(self):
        result = self.result()
        self.assertEqual(result["state"], "development_wait")
        self.assertFalse(result["writes_performed"])
        self.assertFalse((self.case.root / cleanup.ROOT).exists())

    @unittest.skipUnless(os.name == "nt", "native cleanup")
    def test_body_receipt_alone_does_not_complete_ads_backup(self):
        from pathlib import Path
        Path(str(self.case.source) + ":Zone.Identifier:$DATA").write_bytes(b"synthetic stream")
        candidate = self.case.plan()
        self.case.backend.preserve.side_effect = self.record_body
        self.assertTrue(self.case.execute(candidate)["ok"])
        result = self.result()
        self.assertEqual(result["requests"][0]["cleanup_counts"]["completed"], 1)
        self.assertEqual(result["state"], "partial")
        self.assertEqual(result["requests"][0]["recorded_backup"]["verified_preservation_receipts"], 0)

    @unittest.skipUnless(os.name == "nt", "native cleanup")
    def test_unselected_new_file_keeps_requested_directory_partial(self):
        candidate = self.case.plan()
        (self.case.external / "another-activity.txt").write_bytes(b"new unrelated work")
        self.case.backend.preserve.side_effect = self.record_body
        result = self.case.execute(candidate)
        self.assertFalse(result["ok"])
        observed = self.result()
        self.assertEqual(observed["state"], "partial")
        self.assertFalse(observed["requests"][0]["requested_directories_removed"])
        self.assertTrue((self.case.external / "another-activity.txt").exists())
