"""Actual bounded private-directory reads; hints never substitute for proof."""

from contextlib import ExitStack
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_v0420_work_session_source_intake_bundle as bundle_fixture
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_source_intake_bundle as bundle
from wom_kit import work_session_source_intake_inventory as subject


class SourceIntakeContextInventoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="wom-intake-inventory-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "archive"
        self.root.mkdir()
        (self.root / "archive.yml").write_text("archive_id: archive:synthetic:intake-inventory\n", encoding="utf-8")
        self.directory = self.root.joinpath(*bundle.PRIVATE_ROOT)

    def leaf(self, digit="a", raw=b"opaque SYNTHETIC_PRIVATE context"):
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / (digit * 64 + ".json")
        path.write_bytes(raw)
        return path

    def files(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file() and path.name != ".writer.lock"}

    def capture(self, held):
        return subject._capture_source_intake_context_inventory_held(self.root, held=held)

    def unchanged(self, inventory, held):
        return subject._require_source_intake_context_inventory_unchanged_held(self.root, inventory=inventory, held=held)

    def refuse(self, call, code):
        with self.assertRaises(subject.WorkSessionIntakeInventoryError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)
        for secret in (str(self.root), "SYNTHETIC_PRIVATE", "a" * 64):
            self.assertNotIn(secret, str(caught.exception) + repr(caught.exception))

    def test_absence_is_read_only_and_distinct_from_empty_presence_and_disappearance(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            before = self.files()
            absent = self.capture(held)
            self.assertEqual(absent.state, "absent")
            self.assertEqual(absent.hints(), ())
            self.assertIsNone(self.unchanged(absent, held))
            self.assertEqual(self.files(), before)
            self.assertFalse(self.directory.exists())
            self.directory.mkdir(parents=True)
            self.refuse(lambda: self.unchanged(absent, held), "work_session_intake_inventory_changed")
            present = self.capture(held)
            self.assertEqual(present.state, "present")
            self.assertEqual(present.public_summary()["entry_count"], 0)
            self.directory.rmdir()  # This empty synthetic directory is test-owned.
            self.refuse(lambda: self.unchanged(present, held), "work_session_intake_inventory_changed")

    def test_complete_opaque_hints_pending_bytes_and_repeated_access_have_no_parse_or_write(self):
        first, second = self.leaf("a", b"NOT JSON"), self.leaf("b", b"{corrupt")
        pending = self.directory / (".pending_" + "c" * 32)
        pending.write_bytes(b"SYNTHETIC_PRIVATE pending")
        with exact.ExactOperationWriterLock(self.root) as held, ExitStack() as stack:
            before = self.files()
            for owner, name in ((bundle, "_decode_context"), (bundle, "_decode_prepared"),
                                (bundle, "_save_original_source_intake_context_held"),
                                (broker, "_production_key_provider")):
                stack.enter_context(patch.object(owner, name, side_effect=AssertionError("hint parsed or mutated")))
            reads = stack.enter_context(patch.object(subject.controls, "_read_control", wraps=subject.controls._read_control))
            inventory = self.capture(held)
            self.assertEqual(reads.call_count, 6)  # Two stable reads per leaf, including pending.
            hints = inventory.hints()
            self.assertEqual([hint.manifest_sha256 for hint in hints], ["sha256:" + "a" * 64, "sha256:" + "b" * 64])
            self.assertEqual([hint.raw for hint in hints], [first.read_bytes(), second.read_bytes()])
            for _ in range(1000):
                self.assertEqual(inventory.hints()[0].raw, b"NOT JSON")
            self.assertEqual(reads.call_count, 6)
            object.__setattr__(hints[0], "raw", b"caller replacement")
            self.assertEqual(inventory.hints()[0].raw, b"NOT JSON")
            summary = inventory.public_summary()
            self.assertEqual((summary["entry_count"], summary["context_hint_count"], summary["pending_entry_count"]), (3, 2, 1))
            self.assertEqual(summary["raw_byte_count"], sum(path.stat().st_size for path in (first, second, pending)))
            for name in ("context_bodies_validated", "completion_authenticated", "ownership_evaluated", "backup_performed"):
                self.assertFalse(summary[name])
            self.assertIsNone(self.unchanged(inventory, held))
            self.assertEqual(reads.call_count, 12)
            self.assertEqual(self.files(), before)
            for secret in ("SYNTHETIC_PRIVATE", str(self.root), "a" * 64):
                self.assertNotIn(secret, repr(inventory) + repr(hints) + json.dumps(summary))

    def test_actual_retained_context_is_a_hint_even_after_original_request_and_sources_are_removed(self):
        fixture = bundle_fixture.SourceIntakeBundleTests("runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        with exact.ExactOperationWriterLock(fixture.root) as held:
            saved = fixture.save(held)
            fixture.fixture.request_path.unlink()
            for source in fixture.sources:
                source.unlink()
            before = fixture.receipts()
            with patch.object(bundle, "_decode_context", side_effect=AssertionError("inventory parsed context")), \
                 patch.object(broker, "_production_key_provider", side_effect=AssertionError("inventory opened key")):
                inventory = subject._capture_source_intake_context_inventory_held(fixture.root, held=held)
            self.assertEqual(len(inventory.hints()), 1)
            self.assertEqual(inventory.hints()[0].raw, saved._raw)
            self.assertEqual(inventory.hints()[0].manifest_sha256, saved._manifest_sha256)
            self.assertFalse(inventory.public_summary()["completion_authenticated"])
            self.assertEqual(fixture.receipts(), before)

    def test_entry_budget_counts_pending_and_unknown_names_before_filtering(self):
        self.assertEqual(subject.MAX_CONTEXT_DIRECTORY_ENTRIES, 128)
        self.leaf("a", b"a")
        (self.directory / (".pending_" + "b" * 32)).write_bytes(b"b")
        (self.directory / "SYNTHETIC_PRIVATE_unknown").write_bytes(b"c")
        with exact.ExactOperationWriterLock(self.root) as held, \
             patch.object(subject, "MAX_CONTEXT_DIRECTORY_ENTRIES", 2), \
             patch.object(subject.controls, "_read_control", side_effect=AssertionError("over-budget body read")) as read:
            before = self.files()
            self.refuse(lambda: self.capture(held), "work_session_intake_inventory_limit")
            read.assert_not_called()
            self.assertEqual(self.files(), before)

    def test_aggregate_and_per_leaf_budgets_refuse_before_body_read_including_pending(self):
        self.assertEqual(subject.MAX_CONTEXT_INVENTORY_BYTES, 32 * 1024 * 1024)
        self.leaf("a", b"aaaa")
        pending = self.directory / (".pending_" + "b" * 32)
        pending.write_bytes(b"bb")
        with exact.ExactOperationWriterLock(self.root) as held, \
             patch.object(subject.controls, "_read_control", side_effect=AssertionError("over-budget body read")) as read:
            before = self.files()
            with patch.object(subject, "MAX_CONTEXT_INVENTORY_BYTES", 5):
                self.refuse(lambda: self.capture(held), "work_session_intake_inventory_limit")
            with patch.object(bundle, "MAX_BUNDLE_BYTES", 3):
                self.refuse(lambda: self.capture(held), "work_session_intake_inventory_limit")
            read.assert_not_called()
            self.assertEqual(self.files(), before)

    def test_unknown_name_directory_and_actual_hardlink_refuse_without_repair(self):
        path = self.leaf()
        with exact.ExactOperationWriterLock(self.root) as held:
            unknown = self.directory / "SYNTHETIC_PRIVATE_unknown"
            unknown.write_bytes(b"private")
            self.refuse(lambda: self.capture(held), "work_session_intake_inventory_unavailable")
            self.assertEqual(unknown.read_bytes(), b"private")
            unknown.unlink()
            nested = self.directory / ("b" * 64 + ".json")
            nested.mkdir()
            self.refuse(lambda: self.capture(held), "work_session_intake_inventory_unavailable")
            self.assertTrue(nested.is_dir())
            nested.rmdir()
            linked = self.root / "synthetic-hardlink"
            os.link(path, linked)
            self.refuse(lambda: self.capture(held), "work_session_intake_inventory_unavailable")
            self.assertEqual(path.read_bytes(), linked.read_bytes())
            self.assertEqual(path.stat().st_nlink, 2)

    def test_actual_symlink_is_not_an_absent_context_or_safe_leaf(self):
        target = self.root / "synthetic-target"
        target.write_bytes(b"source")
        self.directory.mkdir(parents=True)
        link = self.directory / ("a" * 64 + ".json")
        try:
            os.symlink(target, link)
        except (OSError, NotImplementedError):
            self.skipTest("native test environment cannot create a symbolic link")
        with exact.ExactOperationWriterLock(self.root) as held:
            self.refuse(lambda: self.capture(held), "work_session_intake_inventory_unavailable")
            self.assertTrue(link.is_symlink())
            self.assertEqual(target.read_bytes(), b"source")

    def test_portable_reparse_leaf_and_parent_and_permission_error_are_not_absence(self):
        path = self.leaf()
        original_lstat, original_stat = os.lstat, os.stat

        def decorated(original, name, *args, **kwargs):
            info = original(name, *args, **kwargs)
            if not isinstance(name, int) and Path(name).name == selected_name:
                fields = {field: getattr(info, field) for field in dir(info) if field.startswith("st_")}
                fields["st_file_attributes"] = int(getattr(info, "st_file_attributes", 0)) | 0x400
                return SimpleNamespace(**fields)
            return info

        with exact.ExactOperationWriterLock(self.root) as held:
            for selected_name in (path.name, self.directory.name):
                with self.subTest(target=selected_name), \
                     patch.object(os, "lstat", side_effect=lambda name, *a, **kw: decorated(original_lstat, name, *a, **kw)), \
                     patch.object(os, "stat", side_effect=lambda name, *a, **kw: decorated(original_stat, name, *a, **kw)):
                    self.refuse(lambda: self.capture(held), "work_session_intake_inventory_unavailable")
            with patch.object(bundle, "_directory", side_effect=PermissionError("SYNTHETIC_PRIVATE path denied")):
                self.refuse(lambda: self.capture(held), "work_session_intake_inventory_unavailable")

    def test_same_size_restored_mtime_edit_and_added_name_during_read_fail_generation(self):
        path = self.leaf(raw=b"before")
        reader = subject.controls._read_control
        with exact.ExactOperationWriterLock(self.root) as held:
            for mutation in ("bytes", "name"):
                calls = []

                def change_after_read(target, **kwargs):
                    raw = reader(target, **kwargs)
                    if not calls:
                        calls.append(True)
                        if mutation == "bytes":
                            info = path.stat()
                            path.write_bytes(b"after!")
                            os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
                        else:
                            self.leaf("b", b"new")
                    return raw

                with self.subTest(mutation=mutation), patch.object(subject.controls, "_read_control", side_effect=change_after_read):
                    self.refuse(lambda: self.capture(held), "work_session_intake_inventory_changed")
                self.assertTrue(calls)

    def test_pending_byte_change_is_not_hidden_by_hint_filter(self):
        self.leaf(raw=b"published")
        pending = self.directory / (".pending_" + "b" * 32)
        pending.write_bytes(b"old")
        with exact.ExactOperationWriterLock(self.root) as held:
            snapshot = self.capture(held)
            pending.write_bytes(b"new")
            self.refuse(lambda: self.unchanged(snapshot, held), "work_session_intake_inventory_changed")
            self.assertEqual(pending.read_bytes(), b"new")

    def test_zero_byte_pending_remains_present_unvalidated_inventory_not_absence(self):
        self.directory.mkdir(parents=True)
        pending = self.directory / (".pending_" + "b" * 32)
        pending.write_bytes(b"")
        with exact.ExactOperationWriterLock(self.root) as held:
            inventory = self.capture(held)
            self.assertEqual(inventory.state, "present")
            self.assertEqual(inventory.hints(), ())
            self.assertEqual(inventory.public_summary()["pending_entry_count"], 1)
            self.assertEqual(inventory.public_summary()["raw_byte_count"], 0)
            self.assertFalse(inventory.public_summary()["completion_authenticated"])
            self.assertIsNone(self.unchanged(inventory, held))
            self.assertEqual(pending.read_bytes(), b"")

    def test_final_full_chain_recheck_rejects_new_intermediate_reparse_for_present_and_absent(self):
        original_directory, original_lstat = bundle._directory, os.lstat
        with exact.ExactOperationWriterLock(self.root) as held:
            for present in (False, True):
                if present:
                    self.leaf(raw=b"safe")
                checks = []

                def directory(root):
                    checks.append(True)
                    return original_directory(root)

                def changed_ancestor(path, *args, **kwargs):
                    info = original_lstat(path, *args, **kwargs)
                    if len(checks) >= 2 and Path(path).name == "profiles":
                        fields = {field: getattr(info, field) for field in dir(info) if field.startswith("st_")}
                        fields["st_file_attributes"] = int(getattr(info, "st_file_attributes", 0)) | 0x400
                        return SimpleNamespace(**fields)
                    return info

                with self.subTest(present=present), patch.object(bundle, "_directory", side_effect=directory), \
                     patch.object(os, "lstat", side_effect=changed_ancestor):
                    self.refuse(lambda: self.capture(held), "work_session_intake_inventory_unavailable")
                self.assertGreaterEqual(len(checks), 2)

    def test_parent_identity_failure_and_growth_cannot_publish_partial_snapshot(self):
        path = self.leaf(raw=b"x")
        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(subject.durable, "_assert_named_reservation_directory_identity",
                              side_effect=OSError("SYNTHETIC_PRIVATE parent drift")):
                self.refuse(lambda: self.capture(held), "work_session_intake_inventory_unavailable")
            reader = subject.controls._read_control
            limits = []

            def grow(target, **kwargs):
                limits.append(kwargs["maximum"])
                path.write_bytes(b"now too large")
                return reader(target, **kwargs)

            with patch.object(subject.controls, "_read_control", side_effect=grow):
                self.refuse(lambda: self.capture(held), "work_session_intake_inventory_unavailable")
            self.assertEqual(limits, [1])
            self.assertEqual(path.read_bytes(), b"now too large")

    def test_exact_same_archive_live_lock_and_detached_input_are_required(self):
        self.leaf(raw=b"original")
        with exact.ExactOperationWriterLock(self.root) as held:
            inventory = self.capture(held)
            self.refuse(lambda: self.capture(object()), "work_session_intake_inventory_lock_required")
            self.refuse(lambda: self.unchanged({}, held), "work_session_intake_inventory_invalid")
            reader = subject.controls._read_control

            def mutate_caller(target, **kwargs):
                raw = reader(target, **kwargs)
                object.__setattr__(inventory, "_leaves", ())
                return raw

            with patch.object(subject.controls, "_read_control", side_effect=mutate_caller):
                self.assertIsNone(self.unchanged(inventory, held))
            self.refuse(lambda: self.unchanged(inventory, held), "work_session_intake_inventory_changed")
        self.refuse(lambda: self.capture(held), "work_session_intake_inventory_lock_required")
        other = self.root.parent / "other"
        other.mkdir()
        (other / "archive.yml").write_bytes((self.root / "archive.yml").read_bytes())
        with exact.ExactOperationWriterLock(other) as other_held:
            self.refuse(lambda: self.capture(other_held), "work_session_intake_inventory_lock_required")

    def test_fixed_error_constructor_has_no_unhashable_or_subclass_escape(self):
        class PrivateString(str):
            pass
        for value in ([], {}, PrivateString("work_session_intake_inventory_changed"), "SYNTHETIC_PRIVATE"):
            error = subject.WorkSessionIntakeInventoryError(value)
            self.assertEqual(str(error), "work_session_intake_inventory_invalid")


if __name__ == "__main__":
    unittest.main()
