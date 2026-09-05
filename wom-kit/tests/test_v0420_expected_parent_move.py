"""Optional original-parent binding, without changing legacy move callers."""

from contextlib import contextmanager
import ctypes
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from wom_kit import project_update_transaction as durable


class ExpectedParentMoveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="wom-parent-move-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.parent = self.root / "original"
        self.parent.mkdir()
        self.source = self.parent / "pending.bin"
        self.destination = self.parent / "final.bin"
        self.source.write_bytes(b"synthetic original pending")
        info = os.lstat(self.parent)
        self.identity = (info.st_dev, info.st_ino)

    def move(self, identity=None):
        return durable._atomic_move_file_no_replace(
            self.source, self.destination, expected_parent_identity=self.identity if identity is None else identity,
        )

    def test_legacy_two_argument_call_is_forwarded_unchanged(self):
        with mock.patch.object(durable, "_atomic_move_entry_no_replace") as original:
            durable._atomic_move_file_no_replace(self.source, self.destination)
        original.assert_called_once_with(self.source, self.destination)
        self.assertEqual(self.source.read_bytes(), b"synthetic original pending")

    def test_default_and_expected_parent_moves_keep_existing_no_overwrite(self):
        self.destination.write_bytes(b"synthetic preserved destination")
        for expected in (False, True):
            with self.subTest(expected=expected):
                with self.assertRaises((OSError, durable.ProjectUpdateTransactionError)):
                    if expected:
                        self.move()
                    else:
                        durable._atomic_move_file_no_replace(self.source, self.destination)
                self.assertEqual(self.source.read_bytes(), b"synthetic original pending")
                self.assertEqual(self.destination.read_bytes(), b"synthetic preserved destination")

    def test_expected_parent_is_checked_against_actual_binding_before_mutation(self):
        with self.assertRaises(durable.ProjectUpdateTransactionError):
            self.move((self.identity[0], self.identity[1] + 1))
        self.assertEqual(self.source.read_bytes(), b"synthetic original pending")
        self.assertFalse(self.destination.exists())

    def test_exact_expected_parent_success_keeps_original_bytes(self):
        self.move()
        self.assertFalse(self.source.exists())
        self.assertEqual(self.destination.read_bytes(), b"synthetic original pending")

    def test_default_actual_move_still_succeeds(self):
        durable._atomic_move_file_no_replace(self.source, self.destination)
        self.assertFalse(self.source.exists())
        self.assertEqual(self.destination.read_bytes(), b"synthetic original pending")

    def test_malformed_identity_and_distinct_parent_are_refused(self):
        for invalid in (True, [], (True, 2), (-1, 2), (1,), (1, 2, 3)):
            with self.subTest(kind=type(invalid).__name__):
                with self.assertRaises(durable.ProjectUpdateTransactionError):
                    self.move(invalid)
        other = self.root / "other"
        other.mkdir()
        with self.assertRaises(durable.ProjectUpdateTransactionError):
            durable._atomic_move_file_no_replace(self.source, other / "final.bin", expected_parent_identity=self.identity)
        self.assertEqual(self.source.read_bytes(), b"synthetic original pending")
        self.assertEqual(list(other.iterdir()), [])

    def test_parent_replaced_before_binding_does_not_promote_replacement_bytes(self):
        moved = self.root / "retained-original"
        self.parent.rename(moved)
        self.parent.mkdir()
        self.source.write_bytes(b"synthetic replacement pending")
        with self.assertRaises(durable.ProjectUpdateTransactionError):
            self.move()
        self.assertEqual(self.source.read_bytes(), b"synthetic replacement pending")
        self.assertEqual((moved / self.source.name).read_bytes(), b"synthetic original pending")
        self.assertFalse(self.destination.exists())
        self.assertFalse((moved / self.destination.name).exists())

    @unittest.skipUnless(os.name == "nt", "native Windows retained handle")
    def test_windows_parent_rename_is_refused_after_actual_binding(self):
        original = durable._bound_directory_for_move
        attempts = []

        @contextmanager
        def retained(path):
            with original(path) as bound:
                with self.assertRaises(OSError):
                    path.rename(self.root / "unexpected-renamed-parent")
                attempts.append(bound.identity)
                yield bound

        with mock.patch.object(durable, "_bound_directory_for_move", retained):
            self.move()
        self.assertEqual(attempts, [self.identity])
        self.assertEqual(self.destination.read_bytes(), b"synthetic original pending")

    @unittest.skipUnless(sys.platform.startswith("linux"), "native Linux retained directory descriptor")
    def test_linux_rename_after_binding_refuses_before_publication(self):
        original = durable._bound_directory_for_move
        moved = self.root / "retained-original"

        @contextmanager
        def retained(path):
            with original(path) as bound:
                path.rename(moved)
                path.mkdir()
                self.source.write_bytes(b"synthetic replacement pending")
                yield bound

        with mock.patch.object(durable, "_bound_directory_for_move", retained):
            with self.assertRaises(durable.ProjectUpdateTransactionError):
                self.move()
        self.assertEqual(self.source.read_bytes(), b"synthetic replacement pending")
        self.assertEqual((moved / self.source.name).read_bytes(), b"synthetic original pending")
        self.assertFalse(self.destination.exists())
        self.assertFalse((moved / self.destination.name).exists())

    @unittest.skipUnless(sys.platform.startswith("linux"), "native Linux renameat2 through retained descriptors")
    def test_linux_rename_at_syscall_never_mutates_replacement_directory(self):
        original_cdll = ctypes.CDLL
        moved = self.root / "retained-original"
        called = []

        class RenameObserved:
            def __init__(self, function):
                object.__setattr__(self, "function", function)

            def __setattr__(self, name, value):
                setattr(self.function, name, value)

            def __call__(proxy, *args):
                self.parent.rename(moved)
                self.parent.mkdir()
                self.source.write_bytes(b"synthetic replacement pending")
                called.append(True)
                return proxy.function(*args)

        class LibraryObserved:
            def __init__(self, library):
                self.library = library
                self.renameat2 = RenameObserved(library.renameat2)

            def __getattr__(self, name):
                return getattr(self.library, name)

        with mock.patch.object(ctypes, "CDLL", side_effect=lambda *args, **kwargs: LibraryObserved(original_cdll(*args, **kwargs))):
            with self.assertRaises(durable.ProjectUpdateTransactionError):
                self.move()
        self.assertEqual(called, [True])
        self.assertEqual(self.source.read_bytes(), b"synthetic replacement pending")
        self.assertFalse(self.destination.exists())
        self.assertEqual((moved / self.destination.name).read_bytes(), b"synthetic original pending")


if __name__ == "__main__":
    unittest.main()
