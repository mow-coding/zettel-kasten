"""Directory allocation is not content evidence; real generation drift still is."""

from collections import Counter
from pathlib import Path
import os
import runpy
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from wom_kit import archive_cli, archive_doctor


def changed_stat(value, **changes):
    fields = {name: getattr(value, name) for name in dir(value) if name.startswith("st_")}
    return SimpleNamespace(**(fields | changes))


class DoctorDirectoryIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.benchmark = runpy.run_path(str(
            Path(__file__).resolve().parents[1] / "tools" / "benchmark_doctor_letter148_scale.py"
        ))

    def diagnose_size_transition(self, mutation=None):
        with tempfile.TemporaryDirectory(prefix="wom-doctor-directory-identity-") as tmp:
            root = Path(tmp) / "archive"
            self.benchmark["build_fixture"](root, self.benchmark["REDUCED_PROFILE"])
            changed = False
            real_lstat = os.lstat

            class AllocationTransitionDoctor(archive_cli.Doctor):
                def _run_stage(self, name, function):
                    nonlocal changed
                    result = super()._run_stage(name, function)
                    if name == "symlink-boundaries":
                        changed = True
                        if mutation is not None:
                            mutation(root)
                    return result

            def observe(path, *args, **kwargs):
                value = real_lstat(path, *args, **kwargs)
                if changed and stat.S_ISDIR(value.st_mode):
                    return changed_stat(value, st_size=value.st_size + 4096)
                return value

            doctor = AllocationTransitionDoctor(root)
            with mock.patch.object(os, "lstat", side_effect=observe):
                diagnostics = doctor.run()
            self.assertTrue(changed)
            return diagnostics

    def test_full_small_doctor_accepts_directory_size_only_transition(self) -> None:
        diagnostics = self.diagnose_size_transition()
        self.assertEqual(Counter(item.code for item in diagnostics if item.severity == "ERROR"), {})
        self.assertTrue(any(item.code == "doctor_cache_snapshot_current" for item in diagnostics))

    def test_size_transition_does_not_hide_file_or_member_change(self) -> None:
        for kind in ("file_bytes", "new_member"):
            with self.subTest(kind=kind):
                def mutate(root):
                    directory = root / "zettels"
                    before = directory.stat()
                    if kind == "file_bytes":
                        path = next(directory.glob("*.md"))
                        path.write_bytes(path.read_bytes() + b"changed body\n")
                    else:
                        (directory / "synthetic-added.md").write_bytes(b"new member\n")
                    # Member drift must survive restored parent timestamps too.
                    os.utime(directory, ns=(before.st_atime_ns, before.st_mtime_ns))

                diagnostics = self.diagnose_size_transition(mutate)
                self.assertTrue(any(item.severity == "ERROR" for item in diagnostics))
                self.assertFalse(any(item.code == "doctor_cache_snapshot_current" for item in diagnostics))

    def test_directory_identity_ignores_only_allocation_size(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wom-doctor-directory-token-") as tmp:
            value = os.lstat(tmp)
        allocated = changed_stat(value, st_size=value.st_size + 4096)
        self.assertFalse(archive_doctor._identity_changed(value, allocated))
        self.assertEqual(
            archive_cli.Doctor._inventory_stat_identity(value),
            archive_cli.Doctor._inventory_stat_identity(allocated),
        )
        for field, changed in (
            ("st_ino", value.st_ino + 1),
            ("st_dev", value.st_dev + 1),
            ("st_mode", stat.S_IFREG | 0o600),
            ("st_mtime_ns", value.st_mtime_ns + 1),
        ):
            with self.subTest(field=field):
                altered = changed_stat(value, **{field: changed})
                self.assertTrue(archive_doctor._identity_changed(value, altered))
                self.assertNotEqual(
                    archive_cli.Doctor._inventory_stat_identity(value),
                    archive_cli.Doctor._inventory_stat_identity(altered),
                )

    def test_regular_file_size_remains_content_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wom-doctor-file-token-") as tmp:
            path = Path(tmp) / "source.md"
            path.write_bytes(b"synthetic source\n")
            value = path.stat()
        altered = changed_stat(value, st_size=value.st_size + 1)
        self.assertTrue(archive_doctor._identity_changed(value, altered))
        self.assertNotEqual(
            archive_cli.Doctor._inventory_stat_identity(value),
            archive_cli.Doctor._inventory_stat_identity(altered),
        )

    def test_posix_inventory_does_not_read_windows_only_generation_flag(self) -> None:
        # Select Doctor's POSIX branch without changing pathlib's host platform.
        # This remains a real POSIX run on Linux CI, and catches tuple-contract
        # mistakes on Windows before they reach the Linux matrix.
        posix_observer = SimpleNamespace(**(vars(os) | {"name": "posix"}))
        with tempfile.TemporaryDirectory(prefix="wom-doctor-posix-generation-") as tmp:
            root = Path(tmp) / "archive"
            self.benchmark["build_fixture"](root, self.benchmark["REDUCED_PROFILE"])
            doctor = archive_cli.Doctor(root)
            with mock.patch.object(archive_cli, "os", posix_observer):
                diagnostics = doctor.run()
            self.assertTrue(doctor._archive_tree_inventory_complete)
            self.assertEqual(Counter(item.code for item in diagnostics if item.severity == "ERROR"), {})
            self.assertTrue(any(item.code == "doctor_cache_snapshot_current" for item in diagnostics))
            self.assertTrue(doctor._archive_tree_file_generation_tokens)
            for token in doctor._archive_tree_file_generation_tokens.values():
                self.assertEqual(token[0], "posix_file_generation_v1")
                self.assertEqual(len(token), 9)

    def test_posix_hardlink_keeps_descriptor_hash_fallback(self) -> None:
        posix_observer = SimpleNamespace(**(vars(os) | {"name": "posix"}))
        with tempfile.TemporaryDirectory(prefix="wom-doctor-posix-hardlink-") as tmp:
            base = Path(tmp)
            root = base / "archive"
            path = root / "nested" / "source.json"
            path.parent.mkdir(parents=True)
            path.write_bytes(b'{"synthetic":true}\n')
            try:
                os.link(path, base / "second-link.json")
            except OSError:
                self.skipTest("Host filesystem does not provide hardlinks")
            doctor = archive_cli.Doctor(root)
            with mock.patch.object(archive_cli, "os", posix_observer):
                doctor._run_stage("symlink-boundaries", doctor._check_symlink_boundaries)
                doctor._load_json_file(path)
                with mock.patch.object(archive_cli, "sha256_file", wraps=archive_cli.sha256_file) as hashed:
                    doctor._finalize_run_file_generation_snapshots()
            self.assertEqual(hashed.call_count, 2)
            self.assertIn(
                doctor._archive_tree_key("nested/source.json"),
                doctor._archive_tree_file_generation_hash_required,
            )
            self.assertTrue(any(item.code == "doctor_cache_snapshot_current" for item in doctor.diagnostics))


if __name__ == "__main__":
    unittest.main()
