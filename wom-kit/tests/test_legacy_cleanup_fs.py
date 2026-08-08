from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wom_kit import _legacy_cleanup_fs as cleanup_fs
from wom_kit._legacy_cleanup_fs import (
    LegacyCleanupFilesystemError,
    MountToken,
    bind_directory,
    bind_regular_file,
    bind_workspace_root,
    open_exclusive_at_root,
    parse_linux_fdinfo_mount_id,
    rename_at_root,
    require_same_mount,
    rmdir_in_directory,
    scan_directory,
    scan_root,
    stat_identity,
    unlink_at_root,
    unlink_in_directory,
)


class LegacyCleanupFilesystemTests(unittest.TestCase):
    def assert_boundary_code(self, expected: str, action: object) -> None:
        if not callable(action):
            self.fail("action must be callable")
        with self.assertRaises(LegacyCleanupFilesystemError) as raised:
            action()
        self.assertEqual(raised.exception.code, expected)

    @unittest.skipUnless(os.name == "nt", "approved mutation is Windows-only")
    def test_root_relative_lock_rename_scan_and_close_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temporary_root = Path(tmp).resolve()
            workspace = temporary_root / "workspace"
            workspace.mkdir()
            target = workspace / ".mow-harness"
            target.mkdir()
            target_identity = stat_identity(os.lstat(target))

            with bind_workspace_root(workspace) as bound:
                if os.name == "nt":
                    self.assertIsNone(bound.descriptor)
                    self.assertGreater(len(bound.windows_handles), 1)
                    moved_while_bound = temporary_root / "must-not-move-while-bound"
                    with self.assertRaises(OSError):
                        os.rename(workspace, moved_while_bound)
                else:
                    self.assertIsInstance(bound.descriptor, int)
                    self.assertEqual(bound.windows_handles, ())

                names = [name for name, _info in scan_root(bound, max_entries=10)]
                self.assertEqual(names, [".mow-harness"])

                lock_descriptor = open_exclusive_at_root(bound, ".cleanup.lock")
                try:
                    self.assertEqual(os.write(lock_descriptor, b"bound-lock"), 10)
                    os.fsync(lock_descriptor)
                    lock_identity = stat_identity(os.fstat(lock_descriptor))
                finally:
                    os.close(lock_descriptor)

                rename_at_root(
                    bound,
                    ".mow-harness",
                    ".cleanup-tombstone",
                    expected_source_identity=target_identity,
                )
                unlink_at_root(
                    bound,
                    ".cleanup.lock",
                    expected_identity=lock_identity,
                )
                names = [name for name, _info in scan_root(bound, max_entries=10)]
                self.assertEqual(names, [".cleanup-tombstone"])

            self.assertFalse(target.exists())
            self.assertTrue((workspace / ".cleanup-tombstone").is_dir())
            self.assertFalse((workspace / ".cleanup.lock").exists())

            # The root context owns every ancestor handle.  Once it exits,
            # those handles are closed in reverse order and the root is movable.
            moved_after_close = temporary_root / "moved-after-close"
            os.rename(workspace, moved_after_close)
            os.rename(moved_after_close, workspace)

    def test_bound_directory_and_regular_file_stay_inside_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp).resolve() / "workspace"
            nested = workspace / ".mow-harness" / "source" / "nested"
            nested.mkdir(parents=True)
            payload = nested / "state.bin"
            payload.write_bytes(b"legacy-state")
            outside = workspace / "outside.bin"
            outside.write_bytes(b"outside-must-survive")

            with bind_workspace_root(workspace) as root:
                with bind_directory(
                    root,
                    ".mow-harness/source/nested",
                ) as directory:
                    entries = scan_directory(directory, max_entries=10)
                    self.assertEqual([name for name, _info in entries], ["state.bin"])
                    expected_identity = stat_identity(os.lstat(payload))
                    with bind_regular_file(directory, "state.bin") as bound_file:
                        self.assertEqual(os.read(bound_file.descriptor, 100), b"legacy-state")
                        self.assertEqual(bound_file.identity, expected_identity)
                        self.assertEqual(bound_file.mount_token, root.mount_token)
                    if os.name == "nt":
                        unlink_in_directory(
                            directory,
                            "state.bin",
                            expected_identity=expected_identity,
                        )
                    else:
                        self.assert_boundary_code(
                            "legacy_cleanup_apply_platform_unsupported",
                            lambda: unlink_in_directory(
                                directory,
                                "state.bin",
                                expected_identity=expected_identity,
                            ),
                        )

                self.assert_boundary_code(
                    "legacy_cleanup_relative_directory_invalid",
                    lambda: bind_directory(root, ".mow-harness/../outside").__enter__(),
                )
                self.assert_boundary_code(
                    "legacy_cleanup_entry_name_invalid",
                    lambda: open_exclusive_at_root(root, "../escape"),
                )

            self.assertEqual(payload.exists(), os.name != "nt")
            self.assertEqual(outside.read_bytes(), b"outside-must-survive")

    @unittest.skipIf(os.name == "nt", "POSIX mutation refusal")
    def test_posix_mutation_helpers_refuse_before_any_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp).resolve() / "workspace"
            target = workspace / ".mow-harness"
            empty = target / "empty"
            empty.mkdir(parents=True)
            child = target / "state.bin"
            child.write_bytes(b"must-remain")
            direct = workspace / "direct.bin"
            direct.write_bytes(b"direct-must-remain")

            with bind_workspace_root(workspace) as root:
                for action in (
                    lambda: open_exclusive_at_root(root, ".cleanup.lock"),
                    lambda: rename_at_root(
                        root,
                        ".mow-harness",
                        ".cleanup-tombstone",
                    ),
                    lambda: unlink_at_root(root, "direct.bin"),
                ):
                    self.assert_boundary_code(
                        "legacy_cleanup_apply_platform_unsupported",
                        action,
                    )
                with bind_directory(root, ".mow-harness") as directory:
                    self.assert_boundary_code(
                        "legacy_cleanup_apply_platform_unsupported",
                        lambda: unlink_in_directory(directory, "state.bin"),
                    )
                    self.assert_boundary_code(
                        "legacy_cleanup_apply_platform_unsupported",
                        lambda: rmdir_in_directory(directory, "empty"),
                    )

            self.assertFalse((workspace / ".cleanup.lock").exists())
            self.assertFalse((workspace / ".cleanup-tombstone").exists())
            self.assertEqual(child.read_bytes(), b"must-remain")
            self.assertTrue(empty.is_dir())
            self.assertEqual(direct.read_bytes(), b"direct-must-remain")

    def test_ancestor_link_or_junction_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            real_parent = root / "real-parent"
            workspace = real_parent / "workspace"
            workspace.mkdir(parents=True)
            alias = root / "alias-parent"
            try:
                os.symlink(real_parent, alias, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                if os.name != "nt":
                    self.skipTest(f"symlink creation unavailable: {exc}")
                junction = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(alias), str(real_parent)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                if junction.returncode != 0:
                    self.skipTest(f"junction creation unavailable: {exc}")

            with self.assertRaises(OSError):
                with bind_workspace_root(alias / "workspace"):
                    self.fail("a linked ancestor must never be accepted")
            self.assertTrue(workspace.is_dir())

    @unittest.skipIf(os.name == "nt", "POSIX dirfd replacement test")
    def test_root_replacement_cannot_redirect_root_relative_rename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp).resolve()
            workspace = parent / "workspace"
            original_target = workspace / ".mow-harness"
            original_target.mkdir(parents=True)
            (original_target / "original.bin").write_bytes(b"approved-original")
            moved = parent / "moved-approved-workspace"

            with self.assertRaises(OSError):
                with bind_workspace_root(workspace) as bound:
                    os.rename(workspace, moved)
                    replacement_target = workspace / ".mow-harness"
                    replacement_target.mkdir(parents=True)
                    replacement = replacement_target / "replacement.bin"
                    replacement.write_bytes(b"must-not-be-touched")

                    with bind_directory(bound, ".mow-harness") as original:
                        original_names = [
                            name
                            for name, _info in scan_directory(
                                original,
                                max_entries=10,
                            )
                        ]
                    self.assertEqual(original_names, ["original.bin"])
                    self.assertEqual(replacement.read_bytes(), b"must-not-be-touched")

            self.assertEqual(
                (workspace / ".mow-harness" / "replacement.bin").read_bytes(),
                b"must-not-be-touched",
            )
            self.assertEqual(
                (moved / ".mow-harness" / "original.bin").read_bytes(),
                b"approved-original",
            )

    def test_linux_fdinfo_mount_id_parser_is_strict_and_fail_closed(self) -> None:
        self.assertEqual(
            parse_linux_fdinfo_mount_id(
                "pos:\t0\nflags:\t02100000\nmnt_id:\t314\nino:\t7\n"
            ),
            314,
        )
        for malformed in (
            "pos:\t0\n",
            "mnt_id:\tnot-a-number\n",
            "mnt_id:\t1\nmnt_id:\t2\n",
            "mnt_id:\t-1\n",
        ):
            with self.subTest(raw=malformed):
                self.assert_boundary_code(
                    "mount_identity_unavailable",
                    lambda malformed=malformed: parse_linux_fdinfo_mount_id(
                        malformed
                    ),
                )

    def test_mount_mismatch_uses_stable_content_free_blocker(self) -> None:
        self.assert_boundary_code(
            "mount_boundary_entry",
            lambda: require_same_mount(
                MountToken("linux-mount-id", 10),
                MountToken("linux-mount-id", 11),
            ),
        )

    @unittest.skipIf(os.name == "nt", "POSIX mount token injection test")
    def test_directory_mount_token_mismatch_blocks_before_scan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp).resolve() / "workspace"
            target = workspace / ".mow-harness"
            target.mkdir(parents=True)
            with bind_workspace_root(workspace) as root:
                mismatched = MountToken(root.mount_token.kind, root.mount_token.value + 1)
                with patch.object(
                    cleanup_fs,
                    "mount_token_for_open_fd",
                    return_value=mismatched,
                ):
                    self.assert_boundary_code(
                        "mount_boundary_entry",
                        lambda: bind_directory(root, ".mow-harness").__enter__(),
                    )
            self.assertTrue(target.is_dir())

    def test_filesystem_anchor_is_rejected_before_binding(self) -> None:
        anchor = Path(Path.cwd().anchor)
        self.assert_boundary_code(
            "workspace_root_broad_or_protected",
            lambda: bind_workspace_root(anchor).__enter__(),
        )

    @unittest.skipUnless(os.name == "nt", "Windows alternate-stream syntax")
    def test_windows_root_alternate_stream_syntax_is_rejected_lexically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp).resolve() / "workspace"
            workspace.mkdir()
            stream_spelling = Path(f"{workspace}:private")
            self.assert_boundary_code(
                "workspace_root_alternate_stream_syntax",
                lambda: bind_workspace_root(stream_spelling).__enter__(),
            )

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux fdinfo only")
    def test_linux_bound_root_and_child_use_same_kernel_mount_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp).resolve() / "workspace"
            child = workspace / ".mow-harness"
            child.mkdir(parents=True)
            with bind_workspace_root(workspace) as root:
                self.assertEqual(root.mount_token.kind, "linux-mount-id")
                with bind_directory(root, ".mow-harness") as directory:
                    self.assertEqual(directory.mount_token, root.mount_token)


if __name__ == "__main__":
    unittest.main()
