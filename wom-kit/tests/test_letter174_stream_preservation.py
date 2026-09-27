"""Native synthetic ADS preservation, mutation exclusion, and full restoration."""
import os
from pathlib import Path
import tempfile
import unittest

from wom_kit import activity_cleanup as cleanup, activity_cleanup_streams as streams
from . import test_activity_cleanup as fixture


@unittest.skipUnless(os.name == "nt", "Windows alternate data streams")
class StreamPreservationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.original = self.root / "original.txt"
        self.original.write_bytes(b"synthetic immutable body")
        self.extra = {":Zone.Identifier:$DATA": b"[ZoneTransfer]\r\nZoneId=3\r\n", ":synthetic-note:$DATA": "합성 부가 자료".encode()}
        for name, value in self.extra.items():
            Path(str(self.original) + name).write_bytes(value)
        self.state = cleanup.file_state(self.original)

    def test_native_stream_bundle_roundtrip_keeps_original_and_exact_named_bytes(self):
        rows = streams.inventory(self.original, self.state)
        self.assertEqual(len(rows), 2)
        bundle = streams.build_bundle(self.original, self.state, rows, self.root / "bundle.zip")
        destination = self.root / "restored.txt"
        result = streams.restore_new(self.original, bundle, destination, self.state, rows)
        self.assertTrue(result["ok"])
        self.assertEqual(destination.read_bytes(), self.original.read_bytes())
        for name, expected in self.extra.items():
            self.assertEqual(Path(str(destination) + name).read_bytes(), expected)
            self.assertEqual(Path(str(self.original) + name).read_bytes(), expected)
        self.assertEqual(cleanup.file_state(self.original), self.state)
        with self.assertRaisesRegex(cleanup.ActivityCleanupError, "destination_exists"):
            streams.restore_new(self.original, bundle, destination, self.state, rows)

    def test_held_streams_prevent_replacement_writes_and_new_stream_creation(self):
        with streams.hold(self.original, self.state) as (rows, _handles, verify):
            for name in (*self.extra, ":new-unapproved:$DATA"):
                with self.assertRaises(OSError):
                    Path(str(self.original) + name).write_bytes(b"unapproved")
            with self.assertRaises(OSError):
                self.original.write_bytes(b"changed body")
            verify()
        self.assertEqual(len(rows), 2)

    def test_changed_stream_or_bundle_cannot_become_preservation_proof(self):
        rows = streams.inventory(self.original, self.state)
        bundle = streams.build_bundle(self.original, self.state, rows, self.root / "bundle.zip")
        corrupt = [{**row, "sha256": "0" * 64} for row in rows]
        with self.assertRaises(cleanup.ActivityCleanupError):
            streams.verify_bundle(bundle, self.state, corrupt)
        Path(str(self.original) + ":synthetic-note:$DATA").write_bytes(b"changed")
        with self.assertRaises(Exception):
            streams.build_bundle(self.original, self.state, rows, self.root / "another.zip")

    def test_native_delete_requires_exact_stream_inventory_and_bytes(self):
        from wom_kit.legacy_cleanup_bound_delete import _delete_exact_approved_file, LegacyCleanupBoundDeleteError
        rows = streams.inventory(self.original, self.state)
        with self.assertRaises(LegacyCleanupBoundDeleteError):
            _delete_exact_approved_file(self.root, self.original, self.state)
        self.assertTrue(self.original.exists())
        with self.assertRaises(Exception):
            _delete_exact_approved_file(self.root, self.original, self.state, expected_streams=[])
        self.assertTrue(self.original.exists())
        _delete_exact_approved_file(self.root, self.original, self.state, expected_streams=rows)
        self.assertFalse(self.original.exists())


@unittest.skipUnless(os.name == "nt", "Windows full ADS preservation pipeline")
class OfficialStreamPipelineTests(unittest.TestCase):
    setUp = fixture.ActivityCleanupTests.setUp

    def test_started_child_without_first_checkpoint_resumes_original_claim(self):
        self.interrupt_before_upload_checkpoint = True
        fixture.ActivityCleanupTests.test_official_intake_upload_offload_external_cleanup_pipeline(self)

    def test_missing_child_control_reconstructs_only_original_authenticated_plan(self):
        self.interrupt_before_upload_checkpoint = True
        self.remove_original_upload_control = True
        fixture.ActivityCleanupTests.test_official_intake_upload_offload_external_cleanup_pipeline(self)

    def test_official_intake_upload_offload_delete_and_remote_bytes_restore(self):
        self.preserve_ads = True
        Path(str(self.source) + ":Zone.Identifier:$DATA").write_bytes(b"synthetic zone data")
        fixture.ActivityCleanupTests.test_official_intake_upload_offload_external_cleanup_pipeline(self)

    def test_restored_body_and_ads_survive_cut_before_final_receipt_and_resume_without_download(self):
        self.preserve_ads = True
        self.interrupt_restore_publication = True
        Path(str(self.source) + ":Zone.Identifier:$DATA").write_bytes(b"synthetic zone data")
        fixture.ActivityCleanupTests.test_official_intake_upload_offload_external_cleanup_pipeline(self)

    def test_reconcile_legacy_1017_completed_and_53_pending_only(self):
        import copy
        from unittest.mock import patch
        candidate = cleanup.plan(self.root, self.request, key_provider=self.key)
        original = candidate["material"]
        prototype = original["items"][0]
        original["schema"] = "wom-kit/activity-cleanup-intent/v1"
        original["items"] = []
        for number in range(1070):
            item = copy.deepcopy(prototype)
            item.pop("alternate_streams")
            item["number"] = number
            path = self.external / f"synthetic-{number:04d}.txt"
            item["path"] = str(path)
            if number >= 1017:
                path.write_bytes(f"synthetic remaining item {number}".encode())
                if number >= 1019:
                    Path(str(path) + ":Zone.Identifier:$DATA").write_bytes(b"synthetic zone data")
                item["state"] = cleanup.file_state(path)
                item["object_id"] = "sha256:" + item["state"]["sha256"]
            original["items"].append(item)
        original["directories"] = []
        journal = candidate["journal"]
        journal.write("intent", original)
        for number in range(1017):
            journal.write(f"item-{number}-deleted", {"number": number, "state": "absent_after_bound_delete_intent"})
        original_bytes = (self.root / journal.relative("intent")).read_bytes()
        with patch.object(cleanup, "file_state", wraps=cleanup.file_state) as probe:
            recovery = cleanup.reconcile_plan(candidate)
        self.assertEqual(probe.call_count, 53)
        self.assertEqual(recovery["public"]["completed_items_not_reprocessed"], 1017)
        self.assertEqual(recovery["public"]["pending_recovery_count"], 53)
        self.assertEqual(recovery["public"]["alternate_stream_count"], 51)
        result = fixture.ActivityCleanupTests.execute(self, recovery)
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.backend.preserve.call_count, 53)
        self.assertEqual(sum(row["state"] == "already_deleted" for row in result["items"]), 1017)
        self.assertEqual(sum(row["state"] == "deleted" for row in result["items"]), 53)
        self.assertEqual((self.root / journal.relative("intent")).read_bytes(), original_bytes)
        self.assertTrue(self.source.exists(), "unselected file must remain")
        with patch.object(cleanup, "file_state", wraps=cleanup.file_state) as probe:
            repeated = cleanup.reconcile_plan(candidate)
        self.assertEqual(probe.call_count, 0)
        self.assertEqual(repeated["public"]["pending_recovery_count"], 0)
