"""Canonical note writers cannot race a remote disposal intent (synthetic)."""
import hashlib
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

import test_object_storage_cleanup_open as fixture
from wom_kit import archive_services as services, object_storage_cleanup as cleanup
from wom_kit.exact_operation_manifest import current_writer_lock, exact_operation_writer_lock
from wom_kit.operation_target_leases import TargetLeases


class ReferenceFenceTests(unittest.TestCase):
    def setUp(self):
        self.case = fixture.CleanupOpenTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.root = self.case.root
        self.note = self.root / "inbox/synthetic.md"
        self.note.parent.mkdir(exist_ok=True)

    def test_pending_disposal_blocks_all_common_note_writers(self):
        attempted = []
        raw = ("source: " + fixture.OID).encode()
        def during_delete(stage, _entry):
            if stage != "pending_published":
                return
            for writer, value in [(services.write_text_atomic, raw.decode()),
                (services.write_bytes_atomic, raw), (services._atomic_write, raw),
                (services._atomic_write_text, raw.decode()), (services._write_bytes_create_if_absent, raw)]:
                with self.subTest(writer=writer.__name__):
                    with self.assertRaisesRegex(cleanup.ObjectStorageCleanupError, "disposed_or_pending"):
                        writer(self.note, value)
                    self.assertFalse(self.note.exists())
                    attempted.append(writer.__name__)
        self.assertTrue(self.case.run_cleanup(fault_hook=during_delete)["ok"])
        self.assertEqual(len(attempted), 5)

    def test_compare_and_swap_cannot_add_pending_reference(self):
        before = b"---\nid: zet_synthetic_fence\ntitle: Synthetic\nstatus: draft\n---\nUnrelated note"
        self.note.write_bytes(before)
        after = fixture.OID.encode()
        def during_delete(stage, _entry):
            if stage != "pending_published":
                return
            with self.assertRaisesRegex(cleanup.ObjectStorageCleanupError, "disposed_or_pending"):
                services._replace_regular_file_bytes_compare_and_swap(self.root, self.note,
                    expected_bytes=before, replacement_bytes=after,
                    transaction_sha256="sha256:" + hashlib.sha256(after).hexdigest(),
                    swap_suffix=".test.swap", max_bytes=1024, error_prefix="synthetic")
            self.assertEqual(self.note.read_bytes(), before)
        self.assertTrue(self.case.run_cleanup(fault_hook=during_delete)["ok"])

    def test_unrelated_note_finishes_during_remote_delete(self):
        def during_delete(stage, _entry):
            if stage == "pending_published":
                services.write_text_atomic(self.note, text="Unrelated synthetic note")
        self.assertTrue(self.case.run_cleanup(fault_hook=during_delete)["ok"])
        self.assertEqual(self.note.read_text(), "Unrelated synthetic note")

    def test_existing_writer_lock_reused_without_reacquiring(self):
        target = self.root / cleanup.ROOT / "targets"
        target.mkdir(parents=True, exist_ok=True)
        with exact_operation_writer_lock(self.root) as held:
            self.assertIs(current_writer_lock(self.root), held)
            with patch.object(cleanup, "assert_referenceable") as checked:
                services.write_bytes_atomic(self.note, value=fixture.OID.encode())
                checked.assert_called_once()
            other = []
            thread = threading.Thread(target=lambda: other.append(current_writer_lock(self.root)))
            thread.start(); thread.join()
            self.assertEqual(other, [None])
        self.assertIsNone(current_writer_lock(self.root))

    def test_object_lease_is_not_an_archive_publication_lock(self):
        with TargetLeases(self.root, [("object", fixture.OID)]):
            self.assertIsNone(current_writer_lock(self.root))
            with exact_operation_writer_lock(self.root) as held:
                self.assertIs(current_writer_lock(self.root), held)


if __name__ == "__main__":
    unittest.main()
