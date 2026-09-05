"""Real byte reads with independently perturbed directory metadata."""

import hashlib
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import project_runtime


def _with_stat_fields(observed, **changes):
    fields = {name: getattr(observed, name) for name in dir(observed) if name.startswith("st_")}
    return SimpleNamespace(**{**fields, **changes})


class RuntimeDirectoryIdentityTests(unittest.TestCase):
    def test_directory_allocation_size_is_not_identity_but_file_size_is(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            item = root / "item"
            item.write_bytes(b"unchanged")
            for target, equal in ((root, True), (item, False)):
                observed = target.lstat()
                first = project_runtime._stat_identity(_with_stat_fields(observed, st_size=0))
                second = project_runtime._stat_identity(_with_stat_fields(observed, st_size=4096))
                self.assertEqual(first == second, equal)

    def test_runtime_and_source_tree_hashes_ignore_only_directory_size(self):
        for tree_name in ("runtime", "source_mirror"):
            for changed_level in ("root", "intermediate", "all"):
                with self.subTest(tree=tree_name, changed_level=changed_level):
                    with tempfile.TemporaryDirectory() as temporary:
                        root = Path(temporary) / tree_name
                        item = root / "package" / "nested" / "payload.py"
                        item.parent.mkdir(parents=True)
                        item.write_bytes(b"unchanged original bytes\n")
                        baseline = project_runtime._runtime_payload_observation(root)
                        native_lstat = Path.lstat
                        calls = {}

                        def cold_then_allocated(path, *args, **kwargs):
                            observed = native_lstat(path, *args, **kwargs)
                            selected = path == root if changed_level == "root" else path == item.parent if changed_level == "intermediate" else True
                            if selected and stat.S_ISDIR(observed.st_mode):
                                calls[path] = calls.get(path, 0) + 1
                                return _with_stat_fields(observed, st_size=0 if calls[path] % 2 else 4096)
                            return observed

                        with mock.patch.object(Path, "lstat", cold_then_allocated):
                            actual = project_runtime._runtime_payload_observation(root)
                            direct = project_runtime._stable_regular_file_observation(item, limit=1024, ancestor_root=root, collect_bytes=True)
                        self.assertEqual(actual, baseline)
                        self.assertEqual(direct, (item.read_bytes(), hashlib.sha256(item.read_bytes()).hexdigest(), len(item.read_bytes())))
                        self.assertTrue(any(count > 1 for count in calls.values()))

    def test_members_changed_during_real_read_are_rejected_even_with_restored_mtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            item = root / "nested" / "payload.py"
            item.parent.mkdir()
            item.write_bytes(b"original")
            before = item.parent.stat()
            native_hash = project_runtime._sha256_file

            def add_member(path, **kwargs):
                value = native_hash(path, **kwargs)
                (item.parent / "added.py").write_bytes(b"unapproved")
                os.utime(item.parent, ns=(before.st_atime_ns, before.st_mtime_ns))
                return value

            with mock.patch.object(project_runtime, "_sha256_file", side_effect=add_member):
                with self.assertRaisesRegex(project_runtime.ProjectRuntimeError, "project_runtime_tree_changed"):
                    project_runtime._runtime_payload_observation(root)

    def test_directory_replacement_or_reparse_during_read_remains_rejected(self):
        for mutation in ("inode", "reparse"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                item = root / "nested" / "payload.py"
                item.parent.mkdir()
                item.write_bytes(b"original")
                native_hash = project_runtime._sha256_file
                native_lstat = Path.lstat
                read_done = False

                def read_bytes(path, **kwargs):
                    nonlocal read_done
                    value = native_hash(path, **kwargs)
                    read_done = True
                    return value

                def replace_directory(path, *args, **kwargs):
                    observed = native_lstat(path, *args, **kwargs)
                    if path == item.parent and read_done:
                        return _with_stat_fields(observed, **({"st_ino": observed.st_ino + 1} if mutation == "inode" else {"st_file_attributes": getattr(observed, "st_file_attributes", 0) | 0x400}))
                    return observed

                with mock.patch.object(project_runtime, "_sha256_file", side_effect=read_bytes), mock.patch.object(Path, "lstat", replace_directory):
                    with self.assertRaisesRegex(project_runtime.ProjectRuntimeError, "project_runtime_tree_(changed|unsafe)"):
                        project_runtime._runtime_payload_observation(root)

    def test_file_byte_drift_is_not_hidden_by_directory_normalization(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            item = root / "payload.py"
            item.write_bytes(b"original")
            before = project_runtime._runtime_payload_observation(root)
            original_stat = item.stat()
            item.write_bytes(b"modified")
            os.utime(item, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
            self.assertNotEqual(project_runtime._runtime_payload_observation(root), before)


if __name__ == "__main__":
    unittest.main()
