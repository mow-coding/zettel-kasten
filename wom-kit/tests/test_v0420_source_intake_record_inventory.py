"""Fixed single-record hints reuse the bounded reader, never authenticate."""

import os
import unittest
from unittest.mock import patch

import test_v0420_work_session_source_intake_inventory as fixtures
import test_v0420_source_intake_record_bundle as record_fixture
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_source_intake_inventory as subject
from wom_kit import work_session_source_intake_record_bundle as record


class SourceIntakeRecordInventoryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.SourceIntakeContextInventoryTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.batch_directory = self.fixture.directory
        self.fixture.directory = self.root.joinpath(*record.PRIVATE_ROOT)

    def capture(self, held):
        return subject._capture_source_intake_record_context_inventory_held(self.root, held=held)

    def unchanged(self, inventory, held):
        return subject._require_source_intake_record_context_inventory_unchanged_held(
            self.root, inventory=inventory, held=held)

    def test_fixed_directories_are_separate_and_cross_family_inventory_is_rejected(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            before = self.fixture.files()
            absent = self.capture(held)
            self.assertEqual(absent.state, "absent")
            self.assertIsNone(self.unchanged(absent, held))
            self.assertEqual(self.fixture.files(), before)
            self.fixture.leaf("a", b"record opaque hint")
            self.batch_directory.mkdir(parents=True)
            (self.batch_directory / ("a" * 64 + ".json")).write_bytes(b"batch opaque hint")
            single = self.capture(held)
            batch = subject._capture_source_intake_context_inventory_held(self.root, held=held)
            self.assertEqual(single.hints()[0].raw, b"record opaque hint")
            self.assertEqual(batch.hints()[0].raw, b"batch opaque hint")
            self.fixture.refuse(lambda: self.unchanged(batch, held), "work_session_intake_inventory_invalid")
            self.fixture.refuse(lambda: subject._require_source_intake_context_inventory_unchanged_held(
                self.root, inventory=single, held=held), "work_session_intake_inventory_invalid")
            self.fixture.refuse(lambda: self.unchanged(absent, held), "work_session_intake_inventory_changed")
            self.assertIsNone(self.unchanged(single, held))

    def test_retained_original_hint_survives_missing_input_without_semantic_parse(self):
        fixture = record_fixture.SourceIntakeRecordBundleTests("runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        with exact.ExactOperationWriterLock(fixture.root) as held:
            original = fixture.save(held)
            fixture.fixture.plan_path.unlink()
            fixture.fixture.selected.unlink()
            def files():
                # A Windows byte-range writer lock cannot be read by this
                # unrelated assertion handle while held; it is not payload.
                return {path.relative_to(fixture.root).as_posix(): path.read_bytes()
                        for path in fixture.root.rglob("*")
                        if path.is_file() and path != held.path}
            before = files()
            with patch.object(record, "_decode_context", side_effect=AssertionError("parse")), \
                 patch.object(record, "_decode_prepared", side_effect=AssertionError("prepare")):
                observed = subject._capture_source_intake_record_context_inventory_held(fixture.root, held=held)
            self.assertEqual(len(observed.hints()), 1)
            self.assertEqual(observed.hints()[0].raw, original._raw)
            self.assertEqual(observed.hints()[0].manifest_sha256, fixture.context.plan_sha256)
            self.assertFalse(observed.public_summary()["completion_authenticated"])
            self.assertEqual(files(), before)

    def test_record_directory_preserves_pending_generation_link_and_read_budget_guards(self):
        leaf = self.fixture.leaf(raw=b"aaaa")
        pending = leaf.parent / (".pending_" + "b" * 32)
        pending.write_bytes(b"bb")
        with exact.ExactOperationWriterLock(self.root) as held:
            original = self.capture(held)
            self.assertEqual(original.public_summary()["entry_count"], 2)
            self.assertEqual(len(original.hints()), 1)
            with patch.object(subject, "MAX_CONTEXT_INVENTORY_BYTES", 5), \
                 patch.object(subject.controls, "_read_control", side_effect=AssertionError("body read")):
                self.fixture.refuse(lambda: self.capture(held), "work_session_intake_inventory_limit")
            with patch.object(record, "MAX_BUNDLE_BYTES", 3):
                self.fixture.refuse(lambda: self.capture(held), "work_session_intake_inventory_limit")
            pending.write_bytes(b"cc")
            self.fixture.refuse(lambda: self.unchanged(original, held), "work_session_intake_inventory_changed")
            alias = self.root / "single-record-alias"
            os.link(leaf, alias)
            try:
                self.assertEqual(os.lstat(leaf).st_nlink, 2)
                self.fixture.refuse(lambda: self.capture(held), "work_session_intake_inventory_unavailable")
                self.assertEqual(alias.read_bytes(), b"aaaa")
            finally:
                alias.unlink()
            self.assertEqual(self.capture(held).hints()[0].raw, b"aaaa")

    def test_record_fixed_directory_permission_and_lock_errors_do_not_become_absence(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(record, "_directory", side_effect=PermissionError(str(self.root))):
                self.fixture.refuse(lambda: self.capture(held), "work_session_intake_inventory_unavailable")
            self.fixture.refuse(lambda: self.capture(object()), "work_session_intake_inventory_lock_required")
            for invalid in ([], {}, "other", "../record"):
                with self.subTest(invalid=type(invalid).__name__):
                    self.fixture.refuse(lambda: subject._capture(self.root, held, family=invalid),
                                        "work_session_intake_inventory_invalid")
        self.fixture.refuse(lambda: self.capture(held), "work_session_intake_inventory_lock_required")


if __name__ == "__main__":
    unittest.main()
