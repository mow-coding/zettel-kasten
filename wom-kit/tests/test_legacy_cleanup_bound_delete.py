from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wom_kit import legacy_cleanup_bound_delete as bound_delete
from wom_kit.legacy_cleanup_bound_delete import (
    LegacyCleanupBoundDeleteError,
    delete_exact_approved_empty_directory,
    delete_exact_approved_file,
)


class LegacyCleanupBoundDeleteTests(unittest.TestCase):
    def make_root(self, temporary: str) -> Path:
        root = Path(temporary) / "workspace"
        root.mkdir()
        return root

    def file_record(self, path: Path) -> dict[str, object]:
        information = os.lstat(path)
        raw = path.read_bytes()
        return {
            "type": "file",
            "identity": {
                "device": int(information.st_dev),
                "inode": int(information.st_ino),
            },
            "size": len(raw),
            "mtime_ns": int(information.st_mtime_ns),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    def directory_record(self, path: Path) -> dict[str, object]:
        information = os.lstat(path)
        return {
            "type": "directory",
            "identity": {
                "device": int(information.st_dev),
                "inode": int(information.st_ino),
            },
        }

    def test_exact_file_and_empty_directory_are_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_root(temporary)
            target_file = root / "approved.bin"
            target_file.write_bytes(b"approved bytes")
            file_record = self.file_record(target_file)
            target_directory = root / "approved-empty-directory"
            target_directory.mkdir()
            directory_record = self.directory_record(target_directory)
            outside = root / "outside.bin"
            outside.write_bytes(b"outside must survive")

            if os.name != "nt":
                with self.assertRaises(LegacyCleanupBoundDeleteError) as file_error:
                    delete_exact_approved_file(root, target_file, file_record)
                with self.assertRaises(
                    LegacyCleanupBoundDeleteError
                ) as directory_error:
                    delete_exact_approved_empty_directory(
                        root,
                        target_directory,
                        directory_record,
                    )
                self.assertEqual(
                    file_error.exception.code,
                    "legacy_cleanup_bound_apply_platform_unsupported",
                )
                self.assertEqual(
                    directory_error.exception.code,
                    "legacy_cleanup_bound_apply_platform_unsupported",
                )
                self.assertTrue(target_file.is_file())
                self.assertTrue(target_directory.is_dir())
                self.assertEqual(outside.read_bytes(), b"outside must survive")
                return

            delete_exact_approved_file(root, target_file, file_record)
            delete_exact_approved_empty_directory(
                root,
                target_directory,
                directory_record,
            )

            self.assertFalse(target_file.exists())
            self.assertFalse(target_directory.exists())
            self.assertEqual(outside.read_bytes(), b"outside must survive")

    def test_wrong_digest_and_nonempty_directory_fail_without_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_root(temporary)
            target_file = root / "private-name.bin"
            target_file.write_bytes(b"private-content")
            file_record = self.file_record(target_file)
            file_record["sha256"] = "0" * 64
            directory = root / "not-empty"
            directory.mkdir()
            child = directory / "child.bin"
            child.write_bytes(b"child")
            directory_record = self.directory_record(directory)

            with self.assertRaises(LegacyCleanupBoundDeleteError) as file_error:
                delete_exact_approved_file(root, target_file, file_record)
            with self.assertRaises(LegacyCleanupBoundDeleteError) as directory_error:
                delete_exact_approved_empty_directory(
                    root,
                    directory,
                    directory_record,
                )

            self.assertEqual(target_file.read_bytes(), b"private-content")
            self.assertEqual(child.read_bytes(), b"child")
            rendered = f"{file_error.exception} {directory_error.exception}"
            self.assertNotIn("private-name.bin", rendered)
            self.assertNotIn("private-content", rendered)
            self.assertNotIn(str(root), rendered)

    def test_hardlinked_file_is_rejected_and_other_link_survives(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_root(temporary)
            target = root / "approved.bin"
            target.write_bytes(b"single approved content")
            record = self.file_record(target)
            outside_link = root / "outside-link.bin"
            os.link(target, outside_link)

            with self.assertRaises(LegacyCleanupBoundDeleteError):
                delete_exact_approved_file(root, target, record)

            self.assertEqual(target.read_bytes(), b"single approved content")
            self.assertEqual(outside_link.read_bytes(), b"single approved content")

    def test_pre_epoch_mtime_is_valid_approved_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_root(temporary)
            target = root / "approved.bin"
            target.write_bytes(b"pre-epoch-approved")
            try:
                os.utime(target, ns=(-100, -100))
            except OSError as exc:
                self.skipTest(f"pre-epoch timestamps unavailable: {exc}")
            record = self.file_record(target)
            if int(record["mtime_ns"]) >= 0:
                self.skipTest("filesystem normalized the pre-epoch timestamp")

            if os.name == "nt":
                delete_exact_approved_file(root, target, record)
                self.assertFalse(target.exists())
            else:
                with self.assertRaises(LegacyCleanupBoundDeleteError) as captured:
                    delete_exact_approved_file(root, target, record)
                self.assertEqual(
                    captured.exception.code,
                    "legacy_cleanup_bound_apply_platform_unsupported",
                )
                self.assertEqual(target.read_bytes(), b"pre-epoch-approved")

    def test_outside_root_and_stream_syntax_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = self.make_root(temporary)
            outside = parent / "outside.bin"
            outside.write_bytes(b"outside")
            record = self.file_record(outside)
            with self.assertRaises(LegacyCleanupBoundDeleteError) as captured:
                delete_exact_approved_file(root, outside, record)
            self.assertEqual(
                captured.exception.code,
                "legacy_cleanup_bound_path_outside_root",
            )
            self.assertEqual(outside.read_bytes(), b"outside")

            if os.name == "nt":
                inside = root / "inside.bin"
                inside.write_bytes(b"inside")
                inside_record = self.file_record(inside)
                streamed = Path(str(inside) + ":stream")
                with self.assertRaises(LegacyCleanupBoundDeleteError) as stream_error:
                    delete_exact_approved_file(root, streamed, inside_record)
                self.assertEqual(
                    stream_error.exception.code,
                    "legacy_cleanup_bound_path_stream_syntax",
                )
                self.assertEqual(inside.read_bytes(), b"inside")

    @unittest.skipUnless(os.name == "nt", "Windows retained-handle behavior")
    def test_windows_alternate_data_stream_blocks_file_and_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_root(temporary)
            target_file = root / "with-stream.bin"
            target_file.write_bytes(b"default")
            file_stream = Path(str(target_file) + ":private")
            target_directory = root / "directory-with-stream"
            target_directory.mkdir()
            directory_stream = Path(str(target_directory) + ":private")
            try:
                file_stream.write_bytes(b"hidden")
                directory_stream.write_bytes(b"hidden-directory")
            except OSError as exc:
                self.skipTest(f"alternate streams unavailable: {exc}")

            with self.assertRaises(LegacyCleanupBoundDeleteError) as file_error:
                delete_exact_approved_file(
                    root,
                    target_file,
                    self.file_record(target_file),
                )
            with self.assertRaises(LegacyCleanupBoundDeleteError) as directory_error:
                delete_exact_approved_empty_directory(
                    root,
                    target_directory,
                    self.directory_record(target_directory),
                )

            self.assertEqual(
                file_error.exception.code,
                "legacy_cleanup_bound_alternate_data_stream",
            )
            self.assertEqual(
                directory_error.exception.code,
                "legacy_cleanup_bound_alternate_data_stream",
            )
            self.assertEqual(target_file.read_bytes(), b"default")
            self.assertEqual(file_stream.read_bytes(), b"hidden")
            self.assertTrue(target_directory.is_dir())
            self.assertEqual(directory_stream.read_bytes(), b"hidden-directory")

    @unittest.skipUnless(os.name == "nt", "Windows retained-handle behavior")
    def test_windows_retained_handle_denies_writer_during_disposition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_root(temporary)
            target = root / "approved.bin"
            target.write_bytes(b"approved")
            record = self.file_record(target)
            api = bound_delete._windows_api()
            original = api.set_disposition
            writer_blocked = False

            def observe_writer(handle: int, delete: bool) -> None:
                nonlocal writer_blocked
                if delete:
                    try:
                        with target.open("r+b") as writer:
                            writer.write(b"changed")
                    except OSError:
                        writer_blocked = True
                    else:
                        self.fail("retained cleanup handle allowed a writer")
                original(handle, delete)

            with patch.object(api, "set_disposition", side_effect=observe_writer):
                delete_exact_approved_file(root, target, record)

            self.assertTrue(writer_blocked)
            self.assertFalse(target.exists())

    @unittest.skipUnless(os.name == "nt", "Windows retained-handle behavior")
    def test_windows_post_disposition_failure_cancels_and_preserves_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_root(temporary)
            target = root / "approved.bin"
            target.write_bytes(b"approved")
            record = self.file_record(target)
            original = bound_delete._windows_digest_handle
            pending_check_seen = False

            def fail_pending_check(
                handle: int,
                approved: object,
                *,
                expected_link_count: int,
            ) -> str:
                nonlocal pending_check_seen
                if expected_link_count == 0 and not pending_check_seen:
                    pending_check_seen = True
                    raise LegacyCleanupBoundDeleteError(
                        "injected_post_disposition_failure"
                    )
                return original(
                    handle,
                    approved,
                    expected_link_count=expected_link_count,
                )

            with patch.object(
                bound_delete,
                "_windows_digest_handle",
                side_effect=fail_pending_check,
            ), self.assertRaises(LegacyCleanupBoundDeleteError) as captured:
                delete_exact_approved_file(root, target, record)

            self.assertTrue(pending_check_seen)
            self.assertEqual(
                captured.exception.code,
                "injected_post_disposition_failure",
            )
            self.assertEqual(target.read_bytes(), b"approved")

    @unittest.skipIf(os.name == "nt", "POSIX apply refusal")
    def test_posix_file_apply_refuses_before_any_unlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_root(temporary)
            target = root / "approved.bin"
            target.write_bytes(b"approved")
            record = self.file_record(target)
            with patch.object(
                bound_delete.os,
                "unlink",
                side_effect=AssertionError("POSIX unlink must not run"),
            ), self.assertRaises(LegacyCleanupBoundDeleteError) as captured:
                delete_exact_approved_file(root, target, record)

            self.assertEqual(
                captured.exception.code,
                "legacy_cleanup_bound_apply_platform_unsupported",
            )
            self.assertEqual(target.read_bytes(), b"approved")

    @unittest.skipIf(os.name == "nt", "POSIX apply refusal")
    def test_posix_replacement_entry_is_never_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_root(temporary)
            target = root / "approved.bin"
            target.write_bytes(b"approved")
            record = self.file_record(target)
            replacement = root / "replacement.bin"
            replacement.write_bytes(b"replacement")
            with self.assertRaises(LegacyCleanupBoundDeleteError) as captured:
                delete_exact_approved_file(root, target, record)

            self.assertEqual(
                captured.exception.code,
                "legacy_cleanup_bound_apply_platform_unsupported",
            )
            self.assertEqual(target.read_bytes(), b"approved")
            self.assertEqual(replacement.read_bytes(), b"replacement")

    @unittest.skipIf(os.name == "nt", "POSIX apply refusal")
    def test_posix_directory_apply_refuses_before_any_rmdir(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_root(temporary)
            target = root / "approved-empty"
            target.mkdir()
            record = self.directory_record(target)
            with patch.object(
                bound_delete.os,
                "rmdir",
                side_effect=AssertionError("POSIX rmdir must not run"),
            ), self.assertRaises(LegacyCleanupBoundDeleteError) as captured:
                delete_exact_approved_empty_directory(root, target, record)

            self.assertEqual(
                captured.exception.code,
                "legacy_cleanup_bound_apply_platform_unsupported",
            )
            self.assertTrue(target.is_dir())


if __name__ == "__main__":
    unittest.main()
