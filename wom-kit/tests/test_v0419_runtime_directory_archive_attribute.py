"""Directory ARCHIVE bookkeeping is not runtime content or path identity."""

import hashlib
import os
import stat
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import project_runtime as runtime


ARCHIVE = 0x20


def _with_stat_fields(observed, **changes):
    fields = {
        name: getattr(observed, name)
        for name in dir(observed)
        if name.startswith("st_")
    }
    return SimpleNamespace(**{**fields, **changes})


def _tree(temporary):
    root = Path(temporary) / "runtime"
    item = root / "package" / "payload.py"
    item.parent.mkdir(parents=True)
    item.write_bytes(b"original")
    return root, item


def _set_native_attributes(path, attributes):
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    set_attributes = kernel32.SetFileAttributesW
    set_attributes.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
    set_attributes.restype = wintypes.BOOL
    if not set_attributes(str(path), attributes):
        raise ctypes.WinError(ctypes.get_last_error())


class RuntimeDirectoryArchiveAttributeTests(unittest.TestCase):
    def test_only_directory_archive_bit_is_normalized(self):
        for mode in (stat.S_IFDIR, stat.S_IFREG):
            baseline = SimpleNamespace(
                st_dev=7, st_ino=11, st_mode=mode, st_size=8,
                st_mtime_ns=12345, st_file_attributes=0,
            )
            for bit in (1 << index for index in range(32)):
                with self.subTest(mode=mode, bit=bit):
                    changed = _with_stat_fields(baseline, st_file_attributes=bit)
                    self.assertEqual(
                        runtime._stat_identity(baseline) == runtime._stat_identity(changed),
                        mode == stat.S_IFDIR and bit == ARCHIVE,
                    )

    def test_portable_archive_toggle_keeps_tree_and_ancestor_reads_stable(self):
        for level in ("root", "intermediate"):
            with self.subTest(level=level), tempfile.TemporaryDirectory() as temporary:
                root, item = _tree(temporary)
                target = root if level == "root" else item.parent
                baseline = runtime._runtime_payload_observation(root)
                native_lstat = Path.lstat
                calls = 0

                def toggle_archive(path, *args, **kwargs):
                    nonlocal calls
                    observed = native_lstat(path, *args, **kwargs)
                    if path == target:
                        calls += 1
                        attributes = getattr(observed, "st_file_attributes", 0)
                        return _with_stat_fields(
                            observed,
                            st_file_attributes=attributes ^ (ARCHIVE if calls % 2 else 0),
                        )
                    return observed

                with mock.patch.object(Path, "lstat", toggle_archive):
                    self.assertEqual(runtime._runtime_payload_observation(root), baseline)
                    observed = runtime._stable_regular_file_observation(
                        item, limit=1024, ancestor_root=root, collect_bytes=True,
                    )
                self.assertEqual(observed, (b"original", hashlib.sha256(b"original").hexdigest(), 8))
                self.assertGreater(calls, 1)

    @unittest.skipUnless(os.name == "nt", "Requires native Windows attributes")
    def test_native_archive_toggle_during_directory_enumeration_is_accepted(self):
        for level in ("root", "intermediate"):
            with self.subTest(level=level), tempfile.TemporaryDirectory() as temporary:
                root, item = _tree(temporary)
                target = root if level == "root" else item.parent
                baseline = runtime._runtime_payload_observation(root)
                original_attributes = target.lstat().st_file_attributes
                native_scandir = os.scandir
                changes = []

                @contextmanager
                def toggle_after_enumeration(path):
                    with native_scandir(path) as entries:
                        yield entries
                    if Path(path) == target and not changes:
                        before = target.lstat()
                        _set_native_attributes(target, before.st_file_attributes ^ ARCHIVE)
                        after = target.lstat()
                        changes.append((before, after))

                try:
                    with mock.patch.object(os, "scandir", toggle_after_enumeration):
                        self.assertEqual(runtime._runtime_payload_observation(root), baseline)
                    self._assert_native_archive_only(changes)
                    self.assertEqual(item.read_bytes(), b"original")
                finally:
                    _set_native_attributes(target, original_attributes)

    @unittest.skipUnless(os.name == "nt", "Requires native Windows attributes")
    def test_native_archive_toggle_during_ancestor_bound_read_is_accepted(self):
        for level in ("root", "intermediate"):
            with self.subTest(level=level), tempfile.TemporaryDirectory() as temporary:
                root, item = _tree(temporary)
                target = root if level == "root" else item.parent
                original_attributes = target.lstat().st_file_attributes
                native_fstat = os.fstat
                changes = []

                def toggle_after_open(descriptor):
                    observed = native_fstat(descriptor)
                    if not changes:
                        before = target.lstat()
                        _set_native_attributes(target, before.st_file_attributes ^ ARCHIVE)
                        changes.append((before, target.lstat()))
                    return observed

                try:
                    with mock.patch.object(os, "fstat", toggle_after_open):
                        observed = runtime._stable_regular_file_observation(
                            item, limit=1024, ancestor_root=root, collect_bytes=True,
                        )
                    self._assert_native_archive_only(changes)
                    self.assertEqual(observed, (b"original", hashlib.sha256(b"original").hexdigest(), 8))
                finally:
                    _set_native_attributes(target, original_attributes)

    def _assert_native_archive_only(self, changes):
        self.assertEqual(len(changes), 1)
        before, after = changes[0]
        self.assertEqual(before.st_file_attributes ^ after.st_file_attributes, ARCHIVE)
        for name in ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns"):
            self.assertEqual(getattr(before, name), getattr(after, name), name)
        self.assertEqual(runtime._stat_identity(before), runtime._stat_identity(after))

    def test_archive_toggle_cannot_hide_other_directory_identity_changes(self):
        changes = (
            ("device", lambda value: {"st_dev": value.st_dev + 1}),
            ("inode", lambda value: {"st_ino": value.st_ino + 1}),
            ("type", lambda value: {"st_mode": stat.S_IFREG}),
            ("mtime", lambda value: {"st_mtime_ns": value.st_mtime_ns + 1}),
        )
        for level in ("root", "intermediate"):
            for field, changed_fields in changes:
                with self.subTest(level=level, field=field), tempfile.TemporaryDirectory() as temporary:
                    root, item = _tree(temporary)
                    target = root if level == "root" else item.parent
                    native_lstat = Path.lstat
                    calls = 0

                    def change_after_first(path, *args, **kwargs):
                        nonlocal calls
                        observed = native_lstat(path, *args, **kwargs)
                        if path == target:
                            calls += 1
                            if calls >= 3:
                                return _with_stat_fields(
                                    observed,
                                    st_file_attributes=getattr(observed, "st_file_attributes", 0) ^ ARCHIVE,
                                    **changed_fields(observed),
                                )
                        return observed

                    with mock.patch.object(Path, "lstat", change_after_first):
                        with self.assertRaisesRegex(runtime.ProjectRuntimeError, "project_runtime_tree_(changed|unsafe)"):
                            runtime._runtime_payload_observation(root)

    def test_archive_toggle_cannot_hide_other_directory_attribute_changes(self):
        for bit in (1 << index for index in range(32) if (1 << index) != ARCHIVE):
            with self.subTest(bit=bit), tempfile.TemporaryDirectory() as temporary:
                root, _item = _tree(temporary)
                baseline_stat = root.lstat()
                redundant_ntfs_bit = (
                    bit == 0x10000000 and stat.S_ISDIR(baseline_stat.st_mode)
                    and bool(getattr(baseline_stat, "st_file_attributes", 0) & 0x10)
                )
                native_lstat = Path.lstat
                calls = 0

                def change_after_first(path, *args, **kwargs):
                    nonlocal calls
                    observed = native_lstat(path, *args, **kwargs)
                    if path == root:
                        calls += 1
                        if calls >= 3:
                            return _with_stat_fields(
                                observed,
                                st_file_attributes=getattr(observed, "st_file_attributes", 0) ^ ARCHIVE ^ bit,
                            )
                    return observed

                with mock.patch.object(Path, "lstat", change_after_first):
                    if redundant_ntfs_bit:
                        runtime._runtime_payload_observation(root)
                    else:
                        with self.assertRaisesRegex(runtime.ProjectRuntimeError, "project_runtime_tree_(changed|unsafe)"):
                            runtime._runtime_payload_observation(root)

    def test_member_changes_with_restored_mtime_still_fail_with_archive_toggle(self):
        for mutation in ("add", "remove", "rename"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                root, item = _tree(temporary)
                before_directory = item.parent.lstat()
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
                    os.utime(item.parent, ns=(before_directory.st_atime_ns, before_directory.st_mtime_ns))
                    changed = True
                    return result

                def toggle_archive(path, *args, **kwargs):
                    observed = native_lstat(path, *args, **kwargs)
                    if path == item.parent and changed:
                        return _with_stat_fields(
                            observed, st_file_attributes=getattr(observed, "st_file_attributes", 0) ^ ARCHIVE,
                        )
                    return observed

                with mock.patch.object(runtime, "_sha256_file", change_members), mock.patch.object(Path, "lstat", toggle_archive):
                    with self.assertRaisesRegex(runtime.ProjectRuntimeError, "project_runtime_tree_changed"):
                        runtime._runtime_payload_observation(root)

    def test_same_size_byte_drift_with_restored_mtime_changes_digest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, item = _tree(temporary)
            baseline = runtime._runtime_payload_observation(root)
            original_stat = item.lstat()
            item.write_bytes(b"modified")
            os.utime(item, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
            native_lstat = Path.lstat

            def toggle_archive(path, *args, **kwargs):
                observed = native_lstat(path, *args, **kwargs)
                if stat.S_ISDIR(observed.st_mode):
                    return _with_stat_fields(
                        observed, st_file_attributes=getattr(observed, "st_file_attributes", 0) ^ ARCHIVE,
                    )
                return observed

            with mock.patch.object(Path, "lstat", toggle_archive):
                self.assertNotEqual(runtime._runtime_payload_observation(root), baseline)
            self.assertEqual(item.lstat().st_size, original_stat.st_size)
            self.assertEqual(item.lstat().st_mtime_ns, original_stat.st_mtime_ns)


if __name__ == "__main__":
    unittest.main()
