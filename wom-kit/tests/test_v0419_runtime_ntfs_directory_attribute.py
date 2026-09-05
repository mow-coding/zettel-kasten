"""Model CPython #126253's 0x10 / 0x10000010 directory observations.

These portable synthetic stat observations are not a native reproduction or a
claim about this machine's filesystem. No undocumented attribute is written.
"""

import hashlib
import os
import stat
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import test_v0419_runtime_directory_archive_attribute as archive_tests


runtime = archive_tests.runtime
DIRECTORY = 0x10
ARCHIVE = 0x20
NTFS_DIRECTORY = 0x10000000
REPARSE = 0x400


@contextmanager
def _directory_transition(target, before, after, *, boundary, changed_fields=None):
    """Change only synthetic observations after enumeration or descriptor open."""
    native_lstat = Path.lstat
    native_scandir = os.scandir
    native_fstat = os.fstat
    changed = False
    calls = [0, 0]

    def observe(path, *args, **kwargs):
        observed = native_lstat(path, *args, **kwargs)
        if path != target:
            return observed
        calls[int(changed)] += 1
        fields = changed_fields(observed) if changed and changed_fields else {}
        return archive_tests._with_stat_fields(
            observed, st_file_attributes=after if changed else before, **fields,
        )

    @contextmanager
    def enumerate_directory(path):
        nonlocal changed
        with native_scandir(path) as entries:
            yield entries
        if boundary == "tree" and Path(path) == target:
            changed = True

    def observe_descriptor(descriptor):
        nonlocal changed
        observed = native_fstat(descriptor)
        if boundary == "ancestor":
            changed = True
        return observed

    with mock.patch.object(Path, "lstat", observe), mock.patch.object(
        os, "scandir", enumerate_directory,
    ), mock.patch.object(os, "fstat", observe_descriptor):
        yield calls


class RuntimeNtfsDirectoryAttributeTests(unittest.TestCase):
    def test_all_32_attribute_bits_have_only_the_two_exact_directory_exceptions(self):
        for mode in (stat.S_IFDIR, stat.S_IFREG, stat.S_IFLNK):
            for attributes in (0, DIRECTORY, NTFS_DIRECTORY, DIRECTORY | NTFS_DIRECTORY):
                baseline = SimpleNamespace(
                    st_dev=7, st_ino=11, st_mode=mode, st_size=8,
                    st_mtime_ns=12345, st_file_attributes=attributes,
                )
                for index in range(32):
                    bit = 1 << index
                    with self.subTest(mode=mode, attributes=attributes, bit=bit):
                        changed = archive_tests._with_stat_fields(
                            baseline, st_file_attributes=attributes ^ bit,
                        )
                        ignored = mode == stat.S_IFDIR and (
                            bit == ARCHIVE
                            or bit == NTFS_DIRECTORY and bool(attributes & DIRECTORY)
                        )
                        left = runtime._stat_identity(baseline)
                        right = runtime._stat_identity(changed)
                        self.assertEqual(left == right, ignored)
                        self.assertEqual(left[:-1], right[:-1])
                        if not ignored:
                            self.assertNotEqual(left[-1], right[-1])

    def test_exact_ntfs_pairs_keep_tree_and_ancestor_reads_stable_in_both_directions(self):
        for boundary in ("tree", "ancestor"):
            for level in ("root", "intermediate"):
                for before, after in (
                    (DIRECTORY, DIRECTORY | NTFS_DIRECTORY),
                    (DIRECTORY | NTFS_DIRECTORY, DIRECTORY),
                    (DIRECTORY | ARCHIVE, DIRECTORY | NTFS_DIRECTORY),
                    (DIRECTORY | NTFS_DIRECTORY, DIRECTORY | ARCHIVE),
                ):
                    with self.subTest(boundary=boundary, level=level, before=before, after=after):
                        with tempfile.TemporaryDirectory() as temporary:
                            root, item = archive_tests._tree(temporary)
                            target = root if level == "root" else item.parent
                            baseline = runtime._runtime_payload_observation(root)
                            with _directory_transition(target, before, after, boundary=boundary) as calls:
                                if boundary == "tree":
                                    self.assertEqual(runtime._runtime_payload_observation(root), baseline)
                                else:
                                    self.assertEqual(
                                        runtime._stable_regular_file_observation(
                                            item, limit=1024, ancestor_root=root, collect_bytes=True,
                                        ),
                                        (b"original", hashlib.sha256(b"original").hexdigest(), 8),
                                    )
                            self.assertGreater(calls[0], 0)
                            self.assertGreater(calls[1], 0)

    def test_ntfs_toggle_cannot_hide_unknown_bits_reparse_or_cleared_directory(self):
        for boundary in ("tree", "ancestor"):
            for level in ("root", "intermediate"):
                for name, before, after in (
                    ("unknown27", DIRECTORY, DIRECTORY | NTFS_DIRECTORY | (1 << 27)),
                    ("unknown31", DIRECTORY, DIRECTORY | NTFS_DIRECTORY | (1 << 31)),
                    ("reparse", DIRECTORY, DIRECTORY | NTFS_DIRECTORY | REPARSE),
                    ("directory_cleared", DIRECTORY | NTFS_DIRECTORY, NTFS_DIRECTORY),
                    ("directory_missing", 0, NTFS_DIRECTORY),
                ):
                    for reverse in (False, True):
                        with self.subTest(boundary=boundary, level=level, case=name, reverse=reverse):
                            with tempfile.TemporaryDirectory() as temporary:
                                root, item = archive_tests._tree(temporary)
                                target = root if level == "root" else item.parent
                                first, last = (after, before) if reverse else (before, after)
                                with _directory_transition(target, first, last, boundary=boundary):
                                    self._assert_rejected(boundary, root, item)

    def test_ntfs_toggle_cannot_hide_other_directory_identity_changes(self):
        changes = (
            ("device", lambda value: {"st_dev": value.st_dev + 1}),
            ("inode", lambda value: {"st_ino": value.st_ino + 1}),
            ("type", lambda value: {"st_mode": stat.S_IFREG}),
            ("mtime", lambda value: {"st_mtime_ns": value.st_mtime_ns + 1}),
        )
        for boundary in ("tree", "ancestor"):
            for level in ("root", "intermediate"):
                for name, changed_fields in changes:
                    for before, after in (
                        (DIRECTORY, DIRECTORY | NTFS_DIRECTORY),
                        (DIRECTORY | NTFS_DIRECTORY, DIRECTORY),
                    ):
                        with self.subTest(boundary=boundary, level=level, field=name, before=before):
                            with tempfile.TemporaryDirectory() as temporary:
                                root, item = archive_tests._tree(temporary)
                                target = root if level == "root" else item.parent
                                with _directory_transition(
                                    target, before, after, boundary=boundary, changed_fields=changed_fields,
                                ) as calls:
                                    self._assert_rejected(boundary, root, item)
                                self.assertGreater(calls[0], 0)
                                self.assertGreater(calls[1], 0)

    def test_regular_file_ntfs_bit_remains_bound_even_with_contradictory_directory_attribute(self):
        for attributes in (0, DIRECTORY):
            for reverse in (False, True):
                with self.subTest(attributes=attributes, reverse=reverse):
                    with tempfile.TemporaryDirectory() as temporary:
                        root, item = archive_tests._tree(temporary)
                        native_lstat = Path.lstat
                        native_fstat = os.fstat
                        calls = 0
                        before, after = attributes, attributes | NTFS_DIRECTORY
                        if reverse:
                            before, after = after, before

                        def observe_path(path, *args, **kwargs):
                            observed = native_lstat(path, *args, **kwargs)
                            if path == item:
                                return archive_tests._with_stat_fields(
                                    observed, st_file_attributes=after if calls >= 2 else before,
                                )
                            return observed

                        def observe_descriptor(descriptor):
                            nonlocal calls
                            observed = native_fstat(descriptor)
                            calls += 1
                            return archive_tests._with_stat_fields(
                                observed, st_file_attributes=after if calls >= 2 else before,
                            )

                        with mock.patch.object(Path, "lstat", observe_path), mock.patch.object(
                            os, "fstat", observe_descriptor,
                        ):
                            self.assertIsNone(runtime._stable_regular_file_observation(
                                item, limit=1024, ancestor_root=root, collect_bytes=True,
                            ))
                        self.assertEqual(calls, 2)

    def test_member_changes_with_restored_mtime_still_fail_with_ntfs_toggle(self):
        for mutation in ("add", "remove", "rename"):
            for before, after in (
                (DIRECTORY, DIRECTORY | NTFS_DIRECTORY),
                (DIRECTORY | NTFS_DIRECTORY, DIRECTORY),
            ):
                with self.subTest(mutation=mutation, before=before):
                    with tempfile.TemporaryDirectory() as temporary:
                        root, item = archive_tests._tree(temporary)
                        directory_stat = item.parent.lstat()
                        native_hash = runtime._sha256_file
                        native_lstat = Path.lstat
                        changed = False

                        def change_members(path, **kwargs):
                            nonlocal changed
                            result = native_hash(path, **kwargs)
                            if mutation == "add":
                                (item.parent / "added.py").write_bytes(b"added")
                            elif mutation == "remove":
                                item.unlink()
                            else:
                                item.rename(item.parent / "renamed.py")
                            os.utime(item.parent, ns=(directory_stat.st_atime_ns, directory_stat.st_mtime_ns))
                            changed = True
                            return result

                        def observe(path, *args, **kwargs):
                            observed = native_lstat(path, *args, **kwargs)
                            if path == item.parent:
                                return archive_tests._with_stat_fields(
                                    observed, st_file_attributes=after if changed else before,
                                )
                            return observed

                        with mock.patch.object(runtime, "_sha256_file", change_members), mock.patch.object(
                            Path, "lstat", observe,
                        ):
                            with self.assertRaisesRegex(runtime.ProjectRuntimeError, "project_runtime_tree_changed"):
                                runtime._runtime_payload_observation(root)
                        self.assertTrue(changed)
                        self.assertEqual(item.parent.lstat().st_mtime_ns, directory_stat.st_mtime_ns)

    def test_same_size_byte_drift_with_restored_mtime_changes_digest(self):
        for before, after in (
            (DIRECTORY, DIRECTORY | NTFS_DIRECTORY),
            (DIRECTORY | NTFS_DIRECTORY, DIRECTORY),
        ):
            with self.subTest(before=before), tempfile.TemporaryDirectory() as temporary:
                root, item = archive_tests._tree(temporary)
                baseline = runtime._runtime_payload_observation(root)
                original_stat = item.lstat()
                item.write_bytes(b"modified")
                os.utime(item, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
                with _directory_transition(item.parent, before, after, boundary="tree"):
                    changed = runtime._runtime_payload_observation(root)
                self.assertNotEqual(changed[0], baseline[0])
                self.assertEqual(changed[1], (("package/payload.py", 8, hashlib.sha256(b"modified").hexdigest()),))
                self.assertEqual(item.lstat().st_size, original_stat.st_size)
                self.assertEqual(item.lstat().st_mtime_ns, original_stat.st_mtime_ns)

    def _assert_rejected(self, boundary, root, item):
        if boundary == "tree":
            with self.assertRaisesRegex(runtime.ProjectRuntimeError, "project_runtime_tree_(changed|unsafe)"):
                runtime._runtime_payload_observation(root)
        else:
            self.assertIsNone(runtime._stable_regular_file_observation(
                item, limit=1024, ancestor_root=root, collect_bytes=True,
            ))


if __name__ == "__main__":
    unittest.main()
