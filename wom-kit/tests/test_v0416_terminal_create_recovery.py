from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import archive_services
from wom_kit import project_update_transaction


class V0416TerminalCreateRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name) / "project"
        self.project.mkdir()

    @staticmethod
    def _document() -> dict[str, object]:
        return {
            "schema": archive_services._PROJECT_UPDATE_TERMINAL_HANDOFF_SCHEMA,
            "state": "claim_succeeded_pre_unlock",
            "record": {"status": "succeeded"},
        }

    def _prepared_paths(self) -> tuple[Path, Path, bytes]:
        archive_services._project_update_terminal_control_scaffold(
            self.project
        )
        handoff, _guard = (
            archive_services._project_update_terminal_handoff_paths(
                self.project
            )
        )
        raw = archive_services._project_update_canonical_bytes(
            self._document()
        )
        stage = archive_services._project_update_terminal_create_stage_path(
            handoff,
            raw,
        )
        return handoff, stage, raw

    def _publish_with_failpoint(self, callback) -> tuple[Path, Path, bytes]:
        handoff, stage, raw = self._prepared_paths()
        with archive_services._project_update_terminal_control_boundary(
            self.project
        ) as (scaffold, binding):
            archive_services._project_update_publish_terminal_bytes_no_replace(
                scaffold.project_root,
                scaffold.terminal_root,
                scaffold.terminal_root / handoff.name,
                raw,
                binding=binding,
                _failpoint=callback,
            )
        return handoff, stage, raw

    @staticmethod
    def _write_private_stage(path: Path, raw: bytes) -> None:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        try:
            os.write(descriptor, raw)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @unittest.skipUnless(os.name == "nt", "Windows named-stage recovery")
    def test_exact_content_bound_stage_resumes_after_hard_exit(self) -> None:
        handoff, stage, raw = self._prepared_paths()
        self._write_private_stage(stage, raw)
        project_update_transaction._require_directory_durable(stage.parent)

        written_sha256 = (
            archive_services._project_update_write_terminal_document_exact(
                self.project,
                handoff,
                self._document(),
                expected_previous_value=None,
            )
        )

        self.assertEqual(handoff.read_bytes(), raw)
        self.assertFalse(stage.exists())
        self.assertEqual(
            written_sha256,
            project_update_transaction.sha256_bytes(raw),
        )

    @unittest.skipUnless(os.name == "nt", "Windows named-stage recovery")
    def test_partial_stage_is_preserved_then_initial_write_resumes(self) -> None:
        handoff, stage, raw = self._prepared_paths()
        partial = raw[: max(1, len(raw) // 3)]
        self._write_private_stage(stage, partial)
        residue = (
            archive_services._project_update_terminal_create_residue_path(
                stage
            )
        )

        archive_services._project_update_write_terminal_document_exact(
            self.project,
            handoff,
            self._document(),
            expected_previous_value=None,
        )

        self.assertEqual(handoff.read_bytes(), raw)
        self.assertFalse(stage.exists())
        self.assertEqual(residue.read_bytes(), partial)

    @unittest.skipUnless(os.name == "nt", "Windows named-stage recovery")
    def test_existing_partial_residue_is_never_replaced(self) -> None:
        handoff, stage, raw = self._prepared_paths()
        partial = raw[: max(1, len(raw) // 4)]
        self._write_private_stage(stage, partial)
        residue = (
            archive_services._project_update_terminal_create_residue_path(
                stage
            )
        )
        foreign = b"foreign-residue-must-survive"
        residue.write_bytes(foreign)

        with self.assertRaisesRegex(
            archive_services.ArchiveServiceError,
            "project_version_update_terminal_handoff_conflict",
        ):
            archive_services._project_update_write_terminal_document_exact(
                self.project,
                handoff,
                self._document(),
                expected_previous_value=None,
            )

        self.assertEqual(stage.read_bytes(), partial)
        self.assertEqual(residue.read_bytes(), foreign)
        self.assertFalse(handoff.exists())

    @unittest.skipUnless(os.name == "nt", "Windows bounded-residue inventory")
    def test_unsafe_fixed_residue_blocks_without_publication(self) -> None:
        handoff, stage, raw = self._prepared_paths()
        residue = (
            archive_services._project_update_terminal_create_residue_path(
                stage
            )
        )
        residue.mkdir()

        with self.assertRaisesRegex(
            archive_services.ArchiveServiceError,
            "project_version_update_terminal_handoff_conflict",
        ):
            archive_services._project_update_write_terminal_document_exact(
                self.project,
                handoff,
                self._document(),
                expected_previous_value=None,
            )

        self.assertTrue(residue.is_dir())
        self.assertFalse(handoff.exists())
        self.assertFalse(stage.exists())

    @unittest.skipUnless(os.name == "nt", "Windows named-stage recovery")
    def test_repeated_partial_hard_exits_keep_one_bounded_residue(
        self,
    ) -> None:
        handoff, stage, raw = self._prepared_paths()
        first_partial = raw[: max(1, len(raw) // 5)]
        second_partial = raw[: max(2, len(raw) // 2)]
        self._write_private_stage(stage, first_partial)
        residue = (
            archive_services._project_update_terminal_create_residue_path(
                stage
            )
        )
        real_move = (
            archive_services
            ._project_update_terminal_windows_move_exact_no_replace
        )

        def stop_after_residue(source, destination, **kwargs):
            moved = real_move(source, destination, **kwargs)
            if destination is not None and destination.name == residue.name:
                raise SystemExit("synthetic hard exit after bounded residue")
            return moved

        with patch.object(
            archive_services,
            "_project_update_terminal_windows_move_exact_no_replace",
            side_effect=stop_after_residue,
        ):
            with self.assertRaises(SystemExit):
                archive_services._project_update_write_terminal_document_exact(
                    self.project,
                    handoff,
                    self._document(),
                    expected_previous_value=None,
                )

        self.assertEqual(residue.read_bytes(), first_partial)
        self.assertFalse(stage.exists())
        self._write_private_stage(stage, second_partial)

        with self.assertRaisesRegex(
            archive_services.ArchiveServiceError,
            "project_version_update_terminal_handoff_conflict",
        ):
            archive_services._project_update_write_terminal_document_exact(
                self.project,
                handoff,
                self._document(),
                expected_previous_value=None,
            )

        self.assertEqual(residue.read_bytes(), first_partial)
        self.assertEqual(stage.read_bytes(), second_partial)
        self.assertFalse(handoff.exists())

    @unittest.skipUnless(os.name == "nt", "Windows held-handle recovery")
    def test_full_stage_before_flush_is_reflushed_then_published(self) -> None:
        def hard_exit(phase: str) -> None:
            if phase == "windows_stage_fully_written_before_flush":
                raise SystemExit("synthetic hard exit before file flush")

        with self.assertRaises(SystemExit):
            handoff, stage, raw = self._publish_with_failpoint(hard_exit)

        handoff, stage, raw = self._prepared_paths()
        self.assertEqual(stage.read_bytes(), raw)
        self.assertFalse(handoff.exists())
        archive_services._project_update_write_terminal_document_exact(
            self.project,
            handoff,
            self._document(),
            expected_previous_value=None,
        )
        self.assertEqual(handoff.read_bytes(), raw)
        self.assertFalse(stage.exists())

    @unittest.skipUnless(os.name == "nt", "Windows held-handle recovery")
    def test_renamed_before_parent_flush_is_idempotently_recovered(self) -> None:
        def hard_exit(phase: str) -> None:
            if phase == "windows_exact_handle_renamed_before_parent_flush":
                raise SystemExit("synthetic hard exit before parent flush")

        with self.assertRaises(SystemExit):
            self._publish_with_failpoint(hard_exit)

        handoff, stage, raw = self._prepared_paths()
        self.assertEqual(handoff.read_bytes(), raw)
        self.assertFalse(stage.exists())
        archive_services._project_update_write_terminal_document_exact(
            self.project,
            handoff,
            self._document(),
            expected_previous_value=None,
        )
        self.assertEqual(handoff.read_bytes(), raw)

    @unittest.skipUnless(os.name == "nt", "Windows held-handle race")
    def test_source_name_cannot_be_swapped_after_exact_handle_binding(
        self,
    ) -> None:
        handoff, stage, raw = self._prepared_paths()
        self._write_private_stage(stage, raw)
        foreign = stage.with_name("foreign-stage.json")
        foreign_raw = b"foreign-stage-must-never-enter-active"
        foreign.write_bytes(foreign_raw)
        swap_blocked = []

        def race(phase: str) -> None:
            if phase == "windows_exact_handle_verified_before_rename":
                with self.assertRaises(OSError):
                    os.replace(foreign, stage)
                swap_blocked.append(True)

        with archive_services._project_update_terminal_control_boundary(
            self.project
        ) as (scaffold, binding):
            archive_services._project_update_publish_terminal_bytes_no_replace(
                scaffold.project_root,
                scaffold.terminal_root,
                scaffold.terminal_root / handoff.name,
                raw,
                binding=binding,
                _failpoint=race,
            )

        self.assertGreaterEqual(len(swap_blocked), 1)
        self.assertEqual(handoff.read_bytes(), raw)
        self.assertEqual(foreign.read_bytes(), foreign_raw)

    @unittest.skipUnless(os.name == "nt", "Windows held-handle race")
    def test_destination_race_never_replaces_or_accepts_foreign_bytes(
        self,
    ) -> None:
        handoff, _stage, raw = self._prepared_paths()
        foreign_raw = b"foreign-destination-must-survive"

        def race(phase: str) -> None:
            if phase == "windows_exact_handle_verified_before_rename":
                handoff.write_bytes(foreign_raw)

        with archive_services._project_update_terminal_control_boundary(
            self.project
        ) as (scaffold, binding):
            with self.assertRaises(OSError):
                archive_services._project_update_publish_terminal_bytes_no_replace(
                    scaffold.project_root,
                    scaffold.terminal_root,
                    scaffold.terminal_root / handoff.name,
                    raw,
                    binding=binding,
                    _failpoint=race,
                )

        self.assertEqual(handoff.read_bytes(), foreign_raw)
        stage = archive_services._project_update_terminal_create_stage_path(
            handoff,
            raw,
        )
        self.assertEqual(stage.read_bytes(), raw)

    @unittest.skipUnless(os.name == "nt", "Windows directory handles")
    def test_terminal_root_cannot_be_swapped_while_boundary_is_held(
        self,
    ) -> None:
        handoff, _stage, _raw = self._prepared_paths()
        moved = handoff.parent.with_name("version-update-terminal-moved")
        with archive_services._project_update_terminal_control_boundary(
            self.project
        ):
            with self.assertRaises(OSError):
                os.replace(handoff.parent, moved)
        self.assertTrue(handoff.parent.is_dir())
        self.assertFalse(moved.exists())

    @unittest.skipUnless(os.name == "nt", "Windows fixed-guard recovery")
    def test_zero_byte_guard_hard_exit_is_completed_on_exact_handle(
        self,
    ) -> None:
        handoff, guard = archive_services._project_update_terminal_handoff_paths(
            self.project
        )
        raw = archive_services._project_update_canonical_bytes(self._document())
        real_move = (
            archive_services
            ._project_update_terminal_windows_move_exact_no_replace
        )

        def stop_after_guard_create(source, destination, **kwargs):
            if (
                destination is None
                and source.name == guard.name
                and kwargs.get("create_raw") == b"\x00"
            ):
                def hard_exit(phase: str) -> None:
                    if phase == "windows_file_created_before_write":
                        raise SystemExit(
                            "synthetic hard exit after fixed guard create"
                        )

                kwargs["_failpoint"] = hard_exit
            return real_move(source, destination, **kwargs)

        with patch.object(
            archive_services,
            "_project_update_terminal_windows_move_exact_no_replace",
            side_effect=stop_after_guard_create,
        ):
            with self.assertRaises(SystemExit):
                archive_services._project_update_write_terminal_document_exact(
                    self.project,
                    handoff,
                    self._document(),
                    expected_previous_value=None,
                )

        self.assertTrue(guard.is_file())
        self.assertEqual(guard.read_bytes(), b"")
        self.assertFalse(handoff.exists())
        archive_services._project_update_write_terminal_document_exact(
            self.project,
            handoff,
            self._document(),
            expected_previous_value=None,
        )
        self.assertEqual(guard.read_bytes(), b"\x00")
        self.assertEqual(handoff.read_bytes(), raw)

    @unittest.skipUnless(os.name == "nt", "Windows fixed-guard recovery")
    def test_zero_byte_guard_hardlink_is_rejected_without_mutation(self) -> None:
        handoff, _stage, _raw = self._prepared_paths()
        _ignored_handoff, guard = (
            archive_services._project_update_terminal_handoff_paths(
                self.project
            )
        )
        alias = self.project / "outside-terminal-guard-alias"
        os.link(guard, alias)

        with self.assertRaisesRegex(
            archive_services.ArchiveServiceError,
            "project_version_update_terminal_handoff_conflict",
        ):
            archive_services._project_update_write_terminal_document_exact(
                self.project,
                handoff,
                self._document(),
                expected_previous_value=None,
            )

        self.assertEqual(guard.read_bytes(), b"\x00")
        self.assertEqual(alias.read_bytes(), b"\x00")
        self.assertEqual(os.lstat(guard).st_nlink, 2)
        self.assertFalse(handoff.exists())

    @unittest.skipUnless(os.name == "nt", "Windows fixed-guard recovery")
    def test_zero_byte_guard_named_stream_is_rejected_without_mutation(
        self,
    ) -> None:
        handoff, _stage, _raw = self._prepared_paths()
        _ignored_handoff, guard = (
            archive_services._project_update_terminal_handoff_paths(
                self.project
            )
        )
        named_stream = Path(str(guard) + ":foreign")
        try:
            named_stream.write_bytes(b"foreign-guard-stream-must-survive")
        except OSError:
            self.skipTest("filesystem does not support named data streams")

        with self.assertRaisesRegex(
            archive_services.ArchiveServiceError,
            "project_version_update_terminal_handoff_conflict",
        ):
            archive_services._project_update_write_terminal_document_exact(
                self.project,
                handoff,
                self._document(),
                expected_previous_value=None,
            )

        self.assertEqual(guard.read_bytes(), b"\x00")
        self.assertEqual(
            named_stream.read_bytes(),
            b"foreign-guard-stream-must-survive",
        )
        self.assertFalse(handoff.exists())

    @unittest.skipUnless(os.name == "nt", "Windows fixed-guard recovery")
    def test_guard_swap_before_recovery_handle_open_is_rejected(self) -> None:
        handoff, _stage, _raw = self._prepared_paths()
        _ignored_handoff, guard = (
            archive_services._project_update_terminal_handoff_paths(
                self.project
            )
        )
        preserved = guard.with_name("preserved-original-guard")
        foreign_raw = b"foreign-guard-must-never-authorize"
        real_move = (
            archive_services
            ._project_update_terminal_windows_move_exact_no_replace
        )
        swapped = False

        def swap_before_recovery_open(source, destination, **kwargs):
            nonlocal swapped
            if (
                source.name == guard.name
                and destination is None
                and kwargs.get("complete_empty_with") == b"\x00"
                and not swapped
            ):
                os.replace(guard, preserved)
                guard.write_bytes(foreign_raw)
                swapped = True
            return real_move(source, destination, **kwargs)

        with patch.object(
            archive_services,
            "_project_update_terminal_windows_move_exact_no_replace",
            side_effect=swap_before_recovery_open,
        ):
            with self.assertRaisesRegex(
                archive_services.ArchiveServiceError,
                "project_version_update_terminal_handoff_conflict",
            ):
                archive_services._project_update_write_terminal_document_exact(
                    self.project,
                    handoff,
                    self._document(),
                    expected_previous_value=None,
                )

        self.assertTrue(swapped)
        self.assertEqual(preserved.read_bytes(), b"\x00")
        self.assertEqual(guard.read_bytes(), foreign_raw)
        self.assertFalse(handoff.exists())

    @unittest.skipUnless(os.name == "nt", "Windows single-link contract")
    def test_existing_active_hardlink_is_rejected_without_mutation(self) -> None:
        handoff, _stage, raw = self._prepared_paths()
        handoff.write_bytes(raw)
        alias = self.project / "outside-terminal-active-alias.json"
        os.link(handoff, alias)

        with self.assertRaisesRegex(
            archive_services.ArchiveServiceError,
            "project_version_update_terminal_handoff_invalid",
        ):
            archive_services._project_update_write_terminal_document_exact(
                self.project,
                handoff,
                self._document(),
                expected_previous_value=None,
            )

        self.assertEqual(handoff.read_bytes(), raw)
        self.assertEqual(alias.read_bytes(), raw)
        self.assertEqual(os.lstat(handoff).st_nlink, 2)

    @unittest.skipUnless(os.name == "nt", "Windows default-stream contract")
    def test_existing_active_named_stream_is_rejected_without_mutation(
        self,
    ) -> None:
        handoff, _stage, raw = self._prepared_paths()
        handoff.write_bytes(raw)
        named_stream = Path(str(handoff) + ":foreign")
        try:
            named_stream.write_bytes(b"foreign-stream-must-survive")
        except OSError:
            self.skipTest("filesystem does not support named data streams")

        with self.assertRaisesRegex(
            archive_services.ArchiveServiceError,
            "project_version_update_terminal_handoff_invalid",
        ):
            archive_services._project_update_write_terminal_document_exact(
                self.project,
                handoff,
                self._document(),
                expected_previous_value=None,
            )

        self.assertEqual(handoff.read_bytes(), raw)
        self.assertEqual(
            named_stream.read_bytes(),
            b"foreign-stream-must-survive",
        )

    @unittest.skipUnless(os.name == "nt", "Windows pre-handle race")
    def test_partial_stage_swap_before_handle_open_never_reaches_active(
        self,
    ) -> None:
        handoff, stage, raw = self._prepared_paths()
        partial = raw[: max(1, len(raw) // 3)]
        self._write_private_stage(stage, partial)
        preserved = stage.with_name("observed-partial-stage.json")
        foreign_raw = b"foreign-stage-before-exact-handle-open"
        residue = archive_services._project_update_terminal_create_residue_path(
            stage
        )
        real_move = (
            archive_services
            ._project_update_terminal_windows_move_exact_no_replace
        )
        swapped = False

        def swap_before_open(source, destination, **kwargs):
            nonlocal swapped
            if (
                source.name == stage.name
                and destination is not None
                and destination.name == residue.name
                and not swapped
            ):
                os.replace(stage, preserved)
                stage.write_bytes(foreign_raw)
                swapped = True
            return real_move(source, destination, **kwargs)

        with patch.object(
            archive_services,
            "_project_update_terminal_windows_move_exact_no_replace",
            side_effect=swap_before_open,
        ):
            with self.assertRaisesRegex(
                archive_services.ArchiveServiceError,
                "project_version_update_terminal_handoff_conflict",
            ):
                archive_services._project_update_write_terminal_document_exact(
                    self.project,
                    handoff,
                    self._document(),
                    expected_previous_value=None,
                )

        self.assertTrue(swapped)
        self.assertFalse(handoff.exists())
        self.assertEqual(preserved.read_bytes(), partial)
        self.assertEqual(residue.read_bytes(), foreign_raw)

    @unittest.skipIf(os.name == "nt", "POSIX zero-write contract")
    def test_posix_terminal_writer_fails_before_control_root_creation(
        self,
    ) -> None:
        handoff, _guard = (
            archive_services._project_update_terminal_handoff_paths(
                self.project
            )
        )
        control_root = handoff.parent

        with self.assertRaisesRegex(
            archive_services.ArchiveServiceError,
            "project_version_update_terminal_handoff_platform_unsupported",
        ):
            archive_services._project_update_write_terminal_document_exact(
                self.project,
                handoff,
                self._document(),
                expected_previous_value=None,
            )

        self.assertFalse(control_root.exists())
        self.assertFalse((self.project / ".zettel-kasten").exists())

    @unittest.skipIf(os.name == "nt", "POSIX zero-write contract")
    def test_posix_private_terminal_primitives_preserve_foreign_state(
        self,
    ) -> None:
        handoff, guard = (
            archive_services._project_update_terminal_handoff_paths(
                self.project
            )
        )
        handoff.parent.mkdir(parents=True)
        foreign_handoff = b"foreign-terminal-document"
        foreign_guard = b"foreign-terminal-guard"
        handoff.write_bytes(foreign_handoff)
        guard.write_bytes(foreign_guard)
        before_names = tuple(sorted(item.name for item in handoff.parent.iterdir()))
        before_root_mtime = handoff.parent.stat().st_mtime_ns
        binding = {"path": handoff.parent, "descriptor": None}

        with self.assertRaisesRegex(
            OSError,
            "project_update_terminal_control_platform_unsupported",
        ):
            archive_services._project_update_publish_terminal_bytes_no_replace(
                self.project,
                handoff.parent,
                handoff,
                b"replacement-must-not-be-written",
                binding=binding,
            )
        with self.assertRaisesRegex(
            OSError,
            "project_update_terminal_control_platform_unsupported",
        ):
            archive_services._project_update_terminal_posix_publish_unnamed_no_replace(
                binding,
                handoff,
                b"replacement-must-not-be-written",
            )
        with self.assertRaisesRegex(
            OSError,
            "project_update_terminal_control_platform_unsupported",
        ):
            with archive_services._project_update_terminal_control_boundary(
                self.project
            ):
                self.fail("unsupported control boundary must not yield")

        self.assertEqual(handoff.read_bytes(), foreign_handoff)
        self.assertEqual(guard.read_bytes(), foreign_guard)
        self.assertEqual(
            tuple(sorted(item.name for item in handoff.parent.iterdir())),
            before_names,
        )
        self.assertEqual(handoff.parent.stat().st_mtime_ns, before_root_mtime)



if __name__ == "__main__":
    unittest.main()
