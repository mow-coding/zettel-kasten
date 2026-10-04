"""Beta letter 181 (A): legacy cleanup intents and the session-closeout evidence.

An activity-cleanup request written by an older WOM has no alternate_streams
field on its items. The closeout accepted such an item only with an EMPTY
recorded stream inventory, so the customer's finished request counted 2 of
1,070: the items the original run deleted had no inventory at all, and items
whose streams were preserved with them were rejected outright. Since v0.4.61
the closeout names how each item's stream state is proven:

- bound_delete_guard_no_streams: deleted by the bound delete under this exact
  intent, which refuses any file carrying an alternate data stream;
- recorded_inventory_empty / recorded_inventory_with_stream_backup;
- unknown items (e.g. absent after the delete intent) are counted, never
  assumed empty.

Synthetic files and a mocked preservation backend only.
"""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from wom_kit import activity_cleanup as cleanup
from wom_kit import activity_closeout as closeout

from . import test_activity_cleanup as fixture


@unittest.skipUnless(os.name == "nt", "Windows alternate data streams and native deletion")
class LegacyCloseoutStreamEvidenceTests(unittest.TestCase):
    setUp = fixture.ActivityCleanupTests.setUp
    plan = fixture.ActivityCleanupTests.plan
    execute = fixture.ActivityCleanupTests.execute

    def legacy_candidate(self, names, ads=()):
        for name in names:
            (self.external / name).write_bytes(b"synthetic " + name.encode())
        for name in ads:
            Path(str(self.external / name) + ":Zone.Identifier:$DATA").write_bytes(b"[ZoneTransfer]\r\nZoneId=3\r\n")
        self.source.unlink()
        self.document["items"] = [{"path": str(self.external / name), "role": "source", "reason": "synthetic",
                                   "disposition": "preserve"} for name in names]
        self.document["remove_empty_directories"] = []
        self.request.write_text(json.dumps(self.document), encoding="utf-8")
        candidate = self.plan()
        # The intent shape written by v0.4.38-v0.4.46: no alternate_streams field.
        for item in candidate["material"]["items"]:
            item.pop("alternate_streams")
        candidate["material"]["schema"] = "wom-kit/activity-cleanup-intent/v1"
        candidate["public"] = cleanup.public_plan(candidate["material"])
        return candidate

    def preserve(self, fail=()):
        def record(item, journal):
            if str(item["number"]) in fail:
                raise cleanup.ActivityCleanupError("synthetic_transient_failure")
            journal.write("item-" + str(item["number"]) + "-preserved", {"object_id": item["object_id"],
                "size": item["state"]["size"], "state": "remote_verified", "source_link_preserved": True})
            rows = item.get("alternate_streams")
            if rows:
                child = {"number": str(item["number"]) + "-streams", "path": "x", "root": "x", "role": "evidence",
                         "disposition": "preserve", "state": {"size": 7}, "object_id": "sha256:" + "c" * 64}
                journal.write("item-" + str(item["number"]) + "-streams",
                              {"parent_object_id": item["object_id"], "streams": rows, "item": child})
                record(child, journal)
        self.backend.preserve.side_effect = record

    def closeout(self):
        original = cleanup.plan
        with patch.object(cleanup, "plan", side_effect=lambda *a, **k: original(*a, **{**k, "key_provider": self.key})):
            return closeout.evidence(self.root, [str(self.request)])

    def test_guarded_deletes_recorded_inventories_and_stream_backups_all_qualify(self) -> None:
        candidate = self.legacy_candidate(["A.txt", "B.txt", "C.txt", "D.txt"], ads=["C.txt"])
        self.preserve(fail={"1"})
        first = self.execute(candidate)
        self.assertEqual([row["state"] for row in first["items"]], ["deleted", "retained", "retained", "deleted"])
        self.preserve()
        second = self.execute(cleanup.reconcile_plan(self.plan(resume=True)))
        self.assertTrue(second["ok"], second)
        evidence = self.closeout()
        backup = evidence["requests"][0]["recorded_backup"]
        self.assertEqual(evidence["state"], "complete", backup)
        self.assertEqual(backup["verified_preservation_receipts"], 4)
        self.assertEqual(backup["verified_by_basis"], {"bound_delete_guard_no_streams": 2,
                                                       "recorded_inventory_empty": 1,
                                                       "recorded_inventory_with_stream_backup": 1})
        self.assertEqual(backup["legacy_stream_state_unknown_count"], 0)
        # The official restore of a guarded legacy item is no longer refused as unknown.
        (self.base / "restored").mkdir()
        restore = cleanup.restore_plan(self.plan(resume=True), number=0,
                                       destination=str(self.base / "restored" / "A.txt"))
        self.assertTrue(restore["restore_public"]["ok"])

    def test_deletes_without_a_signed_attempt_stay_unknown(self) -> None:
        """An interrupted run writes no attempt record, and an item found absent after its
        delete intent proves nothing: both are counted as unknown, never assumed empty."""
        candidate = self.legacy_candidate(["A.txt", "B.txt"])
        self.preserve()
        original_write = candidate["journal"].write

        def interrupt(name, document):
            if name == "item-1-deleted":
                raise KeyboardInterrupt()
            return original_write(name, document)
        with patch.object(candidate["journal"], "write", side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.execute(candidate)
        resumed = self.execute(self.plan(resume=True))
        self.assertEqual(resumed["items"][1]["state"], "already_absent_after_intent")
        evidence = self.closeout()
        backup = evidence["requests"][0]["recorded_backup"]
        self.assertEqual(evidence["state"], "partial")
        self.assertEqual(backup["verified_by_basis"], {})
        self.assertEqual(backup["legacy_stream_state_unknown_count"], 2)
        self.assertEqual(backup["legacy_stream_state_unknown_items"], [0, 1])
        self.assertIn("cannot be determined now", backup["plain_summary"])


    def test_handoff_accepts_the_legacy_stream_boundary_only_when_asked(self) -> None:
        from wom_kit import archive_services as services

        candidate = self.legacy_candidate(["A.txt", "B.txt"])
        self.preserve()
        original_write = candidate["journal"].write

        def interrupt(name, document):
            if name == "item-1-deleted":
                raise KeyboardInterrupt()
            return original_write(name, document)
        with patch.object(candidate["journal"], "write", side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.execute(candidate)
        self.execute(self.plan(resume=True))
        original = cleanup.plan

        def handoff(**flags):
            with patch.object(cleanup, "plan", side_effect=lambda *a, **k: original(*a, **{**k, "key_provider": self.key})):
                return services.session_handoff_checkpoint(self.root, dry_run=True,
                                                           cleanup_requests=[str(self.request)], **flags)
        plain = handoff()
        self.assertEqual(plain["activity_closeout"]["state"], "partial")
        self.assertTrue(any("--accept-legacy-stream-boundary" in gap for gap in plain["durable_gaps"]), plain["durable_gaps"])
        accepted = handoff(accept_legacy_stream_boundary=True)
        self.assertEqual(accepted["activity_closeout"]["state"], "complete_with_accepted_legacy_stream_boundary")
        self.assertEqual(accepted["activity_closeout"]["accepted_legacy_stream_boundary"]["unknown_item_count"], 2)
        self.assertFalse(any("cleanup/backup evidence" in gap for gap in accepted["durable_gaps"]))
        self.assertNotEqual(plain["state_digest"], accepted["state_digest"])


if __name__ == "__main__":
    unittest.main()
