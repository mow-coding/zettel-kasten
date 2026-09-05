"""Real retained-parent reads; POSIX replacement races run in Linux CI."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import test_v0420_work_session_operation as operation_fixtures
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_operation as operation
from wom_kit import work_session_registry as registry


class SessionReadBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = operation_fixtures.SessionOperationTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root, self.store = self.fixture.root, self.fixture.store

    def historical_verifier(self):
        self.fixture.execute()
        for index in range(3):
            plan = registry.plan_transition(self.store.read(), action="register-app", label=f"Synthetic later {index}")
            with exact.ExactOperationWriterLock(self.root) as held:
                self.store.commit(plan, held_lock=held)
        verifier = operation._Verifier(self.store, self.fixture.prepared)
        item = self.fixture.prepared.manifest.items[0]
        return lambda: verifier.read_field(target_kind=item.target_kind, target_ref=item.target_ref,
                                          field_ref=item.fields[0].field_ref, heartbeat=lambda: None)

    def test_missing_registry_is_readonly_but_unavailable_is_not_empty(self):
        with tempfile.TemporaryDirectory(prefix="wom-session-absent-") as folder:
            root = Path(folder)
            store = registry.WorkSessionRegistryStore(root, self.store.archive_identity_sha256)
            self.assertEqual(store.read().revision, 0)
            self.assertIsNone(store._read_generation_bytes(1, heartbeat=lambda: None))
            self.assertEqual(list(root.iterdir()), [])
            with mock.patch.object(registry, "_relative_stat", side_effect=PermissionError("Synthetic private unavailable")):
                for read in (store.read, lambda: store._read_generation_bytes(1, heartbeat=lambda: None)):
                    with self.subTest(reader=read.__name__):
                        with self.assertRaisesRegex(registry.WorkSessionRegistryError, "^work_session_path_unsafe$"):
                            read()
            self.assertEqual(list(root.iterdir()), [])

    def test_leaf_read_failure_does_not_become_absence(self):
        with mock.patch.object(registry, "_read_bound_generation", side_effect=OSError("Synthetic private unreadable")):
            for read in (self.store.read, lambda: self.store._read_generation_bytes(1, heartbeat=lambda: None)):
                with self.subTest(reader=read.__name__):
                    with self.assertRaises(registry.WorkSessionRegistryError) as caught:
                        read()
                    self.assertNotIn("Synthetic", str(caught.exception))
        moved = self.store.path.with_name("released-after-error")
        self.store.path.rename(moved)
        moved.rename(self.store.path)
        self.assertEqual(self.store.read().revision, 1)

    def test_pending_entries_also_count_toward_directory_scan_budget(self):
        for index in range(2):
            (self.store.path / (".pending_" + f"{index:032x}")).write_bytes(b"pending")
        with mock.patch.object(registry, "MAX_ENTITIES", 2):
            with self.assertRaisesRegex(registry.WorkSessionRegistryError, "registry_invalid"):
                self.store.read()

    def test_empty_directory_creation_drift_is_not_empty_success(self):
        with tempfile.TemporaryDirectory(prefix="wom-session-new-generation-") as folder:
            root = Path(folder)
            store = registry.WorkSessionRegistryStore(root, self.store.archive_identity_sha256)
            store.path.mkdir(parents=True)
            original = registry._bound_generation_names
            observations = []

            def create_after_observation(parent):
                names = original(parent)
                if not observations:
                    observations.append(True)
                    (store.path / "000000000001.json").write_bytes(b"Synthetic unverified new generation")
                return names

            with mock.patch.object(registry, "_bound_generation_names", side_effect=create_after_observation):
                with self.assertRaisesRegex(registry.WorkSessionRegistryError, "registry_changed"):
                    store.read()

    @unittest.skipUnless(os.name == "nt", "real Windows retained ancestor handles")
    def test_windows_current_read_retains_ancestors_and_releases_handles(self):
        original = exact._read_plain_file
        attempts = []

        def try_rename(path, **kwargs):
            if path.parent == self.store.path:
                for parent in (self.store.path, self.store.path.parent, self.root):
                    with self.assertRaises(OSError):
                        parent.rename(parent.with_name(parent.name + "-moved"))
                    attempts.append(parent.name)
            return original(path, **kwargs)

        with mock.patch.object(exact, "_read_plain_file", side_effect=try_rename):
            self.assertEqual(self.store.read().revision, 1)
        self.assertEqual(len(attempts), 3)
        moved = self.store.path.with_name("released-generations")
        self.store.path.rename(moved)
        moved.rename(self.store.path)
        self.assertEqual(self.store.read().revision, 1)

    @unittest.skipUnless(os.name == "nt", "real Windows retained historical target")
    def test_windows_historical_verifier_uses_retained_read(self):
        read = self.historical_verifier()
        original = exact._read_plain_file
        attempts = []

        def try_rename(path, **kwargs):
            if path.name == "000000000002.json":
                with self.assertRaises(OSError):
                    self.store.path.parent.rename(self.store.path.parent.with_name("moved-work-sessions"))
                attempts.append(True)
            return original(path, **kwargs)

        with mock.patch.object(exact, "_read_plain_file", side_effect=try_rename):
            raw = read()
        self.assertEqual(attempts, [True])
        self.assertEqual(raw, registry._canonical(self.fixture.prepared.transition.after._document))

    def assert_posix_replacement_safe(self, read, name):
        original_raw = (self.store.path / name).read_bytes()
        outside = self.root.parent / "outside-registry"
        outside.mkdir()
        external = outside / name
        external.write_bytes(b"Synthetic private external bytes must not be read")
        external_inode = external.stat().st_ino
        original_open = os.open
        observed = []

        def replace_before_leaf_open(path, flags, *args, **kwargs):
            if path == name and not observed:
                moved = self.store.path.with_name("retained-generations")
                self.store.path.rename(moved)
                self.store.path.symlink_to(outside, target_is_directory=True)
                self.assertIsInstance(kwargs.get("dir_fd"), int)
                descriptor = original_open(path, flags, *args, **kwargs)
                self.assertNotEqual(os.fstat(descriptor).st_ino, external_inode)
                observed.append(os.pread(descriptor, len(original_raw) + 1, 0))
                return descriptor
            return original_open(path, flags, *args, **kwargs)

        with mock.patch.object(registry.os, "open", side_effect=replace_before_leaf_open):
            with self.assertRaises(registry.WorkSessionRegistryError):
                read()
        self.assertEqual(observed, [original_raw])
        self.assertEqual(external.read_bytes(), b"Synthetic private external bytes must not be read")

    @unittest.skipIf(os.name == "nt", "descriptor-relative POSIX registry read")
    def test_posix_current_read_cannot_follow_replaced_ancestor(self):
        self.assert_posix_replacement_safe(self.store.read, "000000000001.json")

    @unittest.skipIf(os.name == "nt", "descriptor-relative POSIX historical read")
    def test_posix_historical_verifier_cannot_follow_replaced_ancestor(self):
        self.assert_posix_replacement_safe(self.historical_verifier(), "000000000002.json")


if __name__ == "__main__":
    unittest.main()
