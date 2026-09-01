from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
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
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_BINARY", 0),
            0o600,
        )
        try:
            os.write(descriptor, raw)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _state_document() -> dict[str, object]:
        return {
            "schema": archive_services._PROJECT_UPDATE_TERMINAL_HANDOFF_SCHEMA,
            "state": "claim_succeeded_pre_unlock",
            "pending": {"status": "succeeded"},
        }

    def _write_unbound_active(self) -> tuple[Path, bytes]:
        handoff, _guard = archive_services._project_update_terminal_handoff_paths(
            self.project
        )
        handoff.parent.mkdir(parents=True)
        raw = archive_services._project_update_canonical_bytes(
            self._state_document()
        )
        self._write_private_stage(handoff, raw)
        return handoff, raw

    @staticmethod
    def _create_directory_reparse(link: Path, target: Path) -> None:
        link.parent.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(
            [
                "cmd.exe",
                "/d",
                "/c",
                "mklink",
                "/J",
                str(link),
                str(target),
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if completed.returncode != 0:
            raise OSError("Windows junction creation failed")

    def _reserve_locked_update(self):
        reserved = (
            project_update_transaction.ProjectUpdateTransaction.reserve(
                self.project,
                project_identity_sha256=(
                    project_update_transaction.sha256_bytes(
                        b"terminal-cleanup-classifier-project"
                    )
                ),
                requested_target_tag="v0.4.17",
                transaction_ref="update_0123456789abcdef0123456789abcdef",
                ownership_nonce="abcdef0123456789abcdef0123456789",
                created_at="2026-09-01T00:00:00Z",
            )
        )
        reserved.acquire_lock()
        return reserved

    def _assert_live_resume_stops_at_cleanup_unknown(self) -> None:
        with patch.object(
            archive_services,
            "_project_update_resume_preapproval_transaction",
            side_effect=AssertionError(
                "mixed cleanup state entered preapproval recovery"
            ),
        ) as preapproval_recovery, patch.object(
            archive_services,
            "_project_update_durable_writer",
            side_effect=AssertionError(
                "mixed cleanup state entered the domain writer"
            ),
        ) as domain_writer:
            result = (
                archive_services
                ._wom_kit_project_version_update_resume_live_transaction(
                    self.project,
                    target=None,
                    reviewed_by=None,
                    transaction_ref=None,
                    approval_executor=lambda *_args, **_kwargs: {},
                    _expected_approval_root=self.project,
                    _expected_archive_id="archive:test-only",
                )
            )
        self.assertEqual(
            result["status"],
            "terminal_cleanup_outcome_unknown",
        )
        self.assertFalse(result["domain_writer_entered"])
        self.assertEqual(result["project_domain_files_written"], [])
        preapproval_recovery.assert_not_called()
        domain_writer.assert_not_called()

    def _assert_invalid_terminal_resume_stops_at_cleanup_unknown(
        self,
        *,
        private_values: tuple[str, ...] = (),
    ) -> dict[str, object]:
        with (
            patch.object(
                archive_services,
                "_project_update_resume_preapproval_transaction",
                side_effect=AssertionError(
                    "unsafe terminal document entered preapproval recovery"
                ),
            ) as preapproval_recovery,
            patch.object(
                archive_services,
                "_project_update_durable_writer",
                side_effect=AssertionError(
                    "unsafe terminal document entered the domain writer"
                ),
            ) as domain_writer,
            patch.object(
                archive_services,
                "_project_update_replay_ready_terminal_handoff",
                side_effect=AssertionError(
                    "unsafe terminal document entered terminal replay"
                ),
            ) as terminal_replay,
            patch.object(
                archive_services,
                "_project_update_reauthenticate_consumed_terminal_delivery",
                side_effect=AssertionError(
                    "unsafe terminal document entered terminal delivery"
                ),
            ) as terminal_delivery,
            patch.object(
                archive_services,
                "_project_update_acknowledge_terminal_result_delivery",
                side_effect=AssertionError(
                    "unsafe terminal document acknowledged delivery"
                ),
            ) as delivery_acknowledgement,
        ):
            result = (
                archive_services
                ._wom_kit_project_version_update_resume_live_transaction(
                    self.project,
                    target=None,
                    reviewed_by=None,
                    transaction_ref=None,
                    approval_executor=lambda *_args, **_kwargs: self.fail(
                        "unsafe terminal document entered native approval"
                    ),
                    _expected_approval_root=self.project,
                    _expected_archive_id="archive:test-only",
                )
            )

        self.assertFalse(result["ok"])
        self.assertEqual(
            result["status"],
            "terminal_cleanup_outcome_unknown",
        )
        self.assertEqual(
            result["reason_code"],
            "project_version_update_terminal_cleanup_outcome_unknown",
        )
        self.assertFalse(result["domain_writer_entered"])
        self.assertFalse(result["client_archive_domain_content_accessed"])
        self.assertEqual(result["project_domain_files_written"], [])
        self.assertEqual(result["files_written"], [])
        preapproval_recovery.assert_not_called()
        domain_writer.assert_not_called()
        terminal_replay.assert_not_called()
        terminal_delivery.assert_not_called()
        delivery_acknowledgement.assert_not_called()
        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn(str(self.project), serialized)
        for private_value in private_values:
            self.assertNotIn(private_value, serialized)
        return result

    def test_unbound_reader_missing_terminal_document_is_none(self) -> None:
        self.assertIsNone(
            archive_services._project_update_terminal_handoff_state_read_only(
                self.project
            )
        )

    @unittest.skipUnless(os.name == "nt", "Windows exact unbound reader")
    def test_unbound_reader_accepts_single_link_active_document(self) -> None:
        handoff, raw = self._write_unbound_active()

        self.assertEqual(
            archive_services._project_update_terminal_handoff_state_read_only(
                self.project
            ),
            "claim_succeeded_pre_unlock",
        )
        observed = archive_services._project_update_read_terminal_document(
            self.project,
            handoff,
        )
        self.assertIsNotNone(observed)
        self.assertEqual(observed[1], raw)
        self.assertEqual(os.lstat(handoff).st_nlink, 1)

    @unittest.skipUnless(os.name == "nt", "Windows held parent authority")
    def test_unbound_reader_holds_parent_against_root_swap(self) -> None:
        handoff, raw = self._write_unbound_active()
        moved = handoff.parent.with_name("version-update-terminal-moved")
        foreign_root = self.project / "foreign-terminal-root"
        foreign_root.mkdir()
        foreign_active = foreign_root / handoff.name
        foreign_raw = b"PRIVATE-FOREIGN-TERMINAL-BYTES"
        foreign_active.write_bytes(foreign_raw)
        real_bound_reader = (
            archive_services._project_update_read_terminal_document_bound
        )
        swap_blocked: list[bool] = []

        def attempt_parent_swap(project_root, binding, path):
            with self.assertRaises(OSError):
                os.replace(handoff.parent, moved)
            swap_blocked.append(True)
            return real_bound_reader(project_root, binding, path)

        with patch.object(
            archive_services,
            "_project_update_read_terminal_document_bound",
            side_effect=attempt_parent_swap,
        ):
            observed = archive_services._project_update_read_terminal_document(
                self.project,
                handoff,
            )

        self.assertEqual(swap_blocked, [True])
        self.assertIsNotNone(observed)
        self.assertEqual(observed[1], raw)
        self.assertTrue(handoff.parent.is_dir())
        self.assertFalse(moved.exists())
        self.assertEqual(foreign_active.read_bytes(), foreign_raw)

    @unittest.skipUnless(os.name == "nt", "Windows single-link authority")
    def test_unbound_reader_rejects_active_hardlink(self) -> None:
        handoff, raw = self._write_unbound_active()
        alias = self.project / "outside-terminal-active-reader-alias.json"
        os.link(handoff, alias)

        with self.assertRaisesRegex(
            archive_services.ArchiveServiceError,
            "project_version_update_terminal_handoff_invalid",
        ):
            archive_services._project_update_terminal_handoff_state_read_only(
                self.project
            )

        self.assertEqual(handoff.read_bytes(), raw)
        self.assertEqual(alias.read_bytes(), raw)
        self.assertEqual(os.lstat(handoff).st_nlink, 2)
        self._assert_invalid_terminal_resume_stops_at_cleanup_unknown(
            private_values=(alias.name,),
        )
        self.assertEqual(handoff.read_bytes(), raw)
        self.assertEqual(alias.read_bytes(), raw)

    @unittest.skipUnless(os.name == "nt", "Windows default-stream authority")
    def test_unbound_reader_rejects_active_named_stream(self) -> None:
        handoff, raw = self._write_unbound_active()
        named_stream = Path(str(handoff) + ":foreign")
        try:
            named_stream.write_bytes(b"foreign-terminal-reader-stream")
        except OSError:
            self.skipTest("filesystem does not support named data streams")

        with self.assertRaisesRegex(
            archive_services.ArchiveServiceError,
            "project_version_update_terminal_handoff_invalid",
        ):
            archive_services._project_update_terminal_handoff_state_read_only(
                self.project
            )

        self.assertEqual(handoff.read_bytes(), raw)
        self.assertEqual(
            named_stream.read_bytes(),
            b"foreign-terminal-reader-stream",
        )
        self._assert_invalid_terminal_resume_stops_at_cleanup_unknown(
            private_values=("foreign-terminal-reader-stream",),
        )
        self.assertEqual(handoff.read_bytes(), raw)
        self.assertEqual(
            named_stream.read_bytes(),
            b"foreign-terminal-reader-stream",
        )

    @unittest.skipUnless(os.name == "nt", "Windows reparse parent authority")
    def test_unbound_reader_rejects_reparse_parent_without_following_it(
        self,
    ) -> None:
        handoff, _guard = archive_services._project_update_terminal_handoff_paths(
            self.project
        )
        foreign_root = self.project / "foreign-terminal-reparse-target"
        foreign_root.mkdir()
        foreign_active = foreign_root / handoff.name
        foreign_raw = b"PRIVATE-FOREIGN-REPARSE-ACTIVE"
        foreign_active.write_bytes(foreign_raw)
        try:
            try:
                self._create_directory_reparse(handoff.parent, foreign_root)
            except OSError as failure:
                self.skipTest(str(failure))

            with self.assertRaisesRegex(
                archive_services.ArchiveServiceError,
                "project_version_update_terminal_handoff_invalid",
            ):
                archive_services._project_update_terminal_handoff_state_read_only(
                    self.project
                )
            self._assert_invalid_terminal_resume_stops_at_cleanup_unknown(
                private_values=(
                    foreign_root.name,
                    foreign_raw.decode("ascii"),
                ),
            )
            self.assertEqual(foreign_active.read_bytes(), foreign_raw)
            self.assertTrue(handoff.parent.exists())
        finally:
            if os.path.lexists(handoff.parent):
                os.rmdir(handoff.parent)
        self.assertTrue(foreign_root.is_dir())
        self.assertEqual(foreign_active.read_bytes(), foreign_raw)

    @unittest.skipUnless(os.name == "nt", "Windows reparse file authority")
    def test_unbound_reader_rejects_reparse_file_attribute(self) -> None:
        handoff, raw = self._write_unbound_active()
        real_lstat = os.lstat

        def report_active_as_reparse(path):
            observed = real_lstat(path)
            if Path(path).name != handoff.name:
                return observed
            return SimpleNamespace(
                st_mode=observed.st_mode,
                st_file_attributes=(
                    getattr(observed, "st_file_attributes", 0) | 0x400
                ),
                st_dev=observed.st_dev,
                st_ino=observed.st_ino,
                st_nlink=observed.st_nlink,
                st_size=observed.st_size,
                st_mtime_ns=observed.st_mtime_ns,
                st_ctime_ns=observed.st_ctime_ns,
            )

        with patch.object(
            archive_services.os,
            "lstat",
            side_effect=report_active_as_reparse,
        ):
            with self.assertRaisesRegex(
                archive_services.ArchiveServiceError,
                "project_version_update_terminal_handoff_invalid",
            ):
                archive_services._project_update_terminal_handoff_state_read_only(
                    self.project
                )
            self._assert_invalid_terminal_resume_stops_at_cleanup_unknown()

        self.assertEqual(handoff.read_bytes(), raw)

    def test_terminal_handoff_invalid_is_the_only_structured_unknown_allowlist(
        self,
    ) -> None:
        sentinel = "project_version_update_terminal_handoff_conflict"
        with (
            patch.object(
                archive_services,
                "_project_update_terminal_handoff_state_read_only",
                side_effect=archive_services.ArchiveServiceError(sentinel),
            ),
            patch.object(
                archive_services,
                "_project_update_resume_preapproval_transaction",
                side_effect=AssertionError(
                    "non-allowlisted terminal failure entered recovery"
                ),
            ) as preapproval_recovery,
            patch.object(
                archive_services,
                "_project_update_durable_writer",
                side_effect=AssertionError(
                    "non-allowlisted terminal failure entered writer"
                ),
            ) as domain_writer,
        ):
            with self.assertRaisesRegex(
                archive_services.ArchiveServiceError,
                sentinel,
            ):
                archive_services._wom_kit_project_version_update_resume_live_transaction(
                    self.project,
                    target=None,
                    reviewed_by=None,
                    transaction_ref=None,
                    approval_executor=lambda *_args, **_kwargs: self.fail(
                        "non-allowlisted terminal failure entered approval"
                    ),
                    _expected_approval_root=self.project,
                    _expected_archive_id="archive:test-only",
                )

        preapproval_recovery.assert_not_called()
        domain_writer.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "Windows exact-name race")
    def test_unbound_reader_never_accepts_swapped_foreign_bytes(self) -> None:
        handoff, raw = self._write_unbound_active()
        preserved = self.project / "preserved-terminal-active.json"
        foreign_raw = archive_services._project_update_canonical_bytes(
            {
                "schema": (
                    archive_services._PROJECT_UPDATE_TERMINAL_HANDOFF_SCHEMA
                ),
                "state": "claim_succeeded_pre_unlock",
                "pending": {"status": "foreign"},
            }
        )
        real_reader = (
            archive_services
            ._project_update_terminal_windows_move_exact_no_replace
        )
        swapped = False

        def swap_before_exact_open(source, destination, **kwargs):
            nonlocal swapped
            if (
                source.name == handoff.name
                and destination is None
                and not swapped
            ):
                os.replace(handoff, preserved)
                handoff.write_bytes(foreign_raw)
                swapped = True
            return real_reader(source, destination, **kwargs)

        with patch.object(
            archive_services,
            "_project_update_terminal_windows_move_exact_no_replace",
            side_effect=swap_before_exact_open,
        ):
            with self.assertRaisesRegex(
                archive_services.ArchiveServiceError,
                "project_version_update_terminal_handoff_invalid",
            ):
                archive_services._project_update_terminal_handoff_state_read_only(
                    self.project
                )

        self.assertTrue(swapped)
        self.assertEqual(preserved.read_bytes(), raw)
        self.assertEqual(handoff.read_bytes(), foreign_raw)

    @unittest.skipIf(os.name == "nt", "POSIX private read-only contract")
    def test_posix_unbound_reader_requires_private_single_link_active(self) -> None:
        handoff, raw = self._write_unbound_active()
        self.assertEqual(
            archive_services._project_update_terminal_handoff_state_read_only(
                self.project
            ),
            "claim_succeeded_pre_unlock",
        )

        handoff.chmod(0o644)
        with self.assertRaisesRegex(
            archive_services.ArchiveServiceError,
            "project_version_update_terminal_handoff_invalid",
        ):
            archive_services._project_update_terminal_handoff_state_read_only(
                self.project
            )
        handoff.chmod(0o600)

        alias = self.project / "outside-terminal-active-reader-alias.json"
        os.link(handoff, alias)
        with self.assertRaisesRegex(
            archive_services.ArchiveServiceError,
            "project_version_update_terminal_handoff_invalid",
        ):
            archive_services._project_update_terminal_handoff_state_read_only(
                self.project
            )
        self.assertEqual(handoff.read_bytes(), raw)
        self.assertEqual(alias.read_bytes(), raw)

    def test_exact_locked_preapproval_is_explicitly_resumable(self) -> None:
        reserved = self._reserve_locked_update()

        self.assertEqual(
            project_update_transaction.inspect_prelock_orphans(
                self.project
            )[0].classification,
            "reserved_locked_unsealed",
        )
        self.assertEqual(
            archive_services
            ._project_update_terminal_cleanup_artifact_classification_read_only(
                self.project
            ),
            ("resume_required_exact", 1),
        )
        self.assertIsNone(
            archive_services
            ._project_update_terminal_cleanup_unknown_gate_read_only(
                self.project,
                operator_resume_identifiers_supplied=False,
            )
        )
        self.assertTrue(reserved.transaction_root.is_dir())

    def test_active_plus_malformed_tombstone_stops_before_recovery(self) -> None:
        reserved = self._reserve_locked_update()
        malformed = reserved.transaction_root.parent / (
            ".cleanup_update_11111111111111111111111111111111"
        )
        malformed.mkdir()
        (malformed / "foreign.bin").write_bytes(b"foreign cleanup bytes")

        self.assertEqual(
            archive_services
            ._project_update_terminal_cleanup_artifact_classification_read_only(
                self.project
            ),
            ("unresolved", 0),
        )
        self._assert_live_resume_stops_at_cleanup_unknown()

    def test_active_plus_unknown_namespace_name_stops_before_recovery(
        self,
    ) -> None:
        reserved = self._reserve_locked_update()
        (reserved.transaction_root.parent / "foreign.bin").write_bytes(
            b"unknown transaction namespace entry"
        )

        self.assertEqual(
            archive_services
            ._project_update_terminal_cleanup_artifact_classification_read_only(
                self.project
            ),
            ("unresolved", 0),
        )
        self._assert_live_resume_stops_at_cleanup_unknown()

    def test_active_plus_unsafe_transaction_entry_stops_before_recovery(
        self,
    ) -> None:
        reserved = self._reserve_locked_update()
        unsafe = reserved.transaction_root.parent / (
            "update_22222222222222222222222222222222"
        )
        unsafe.write_bytes(
            b"regular file where a transaction directory was expected"
        )

        self.assertEqual(
            archive_services
            ._project_update_terminal_cleanup_artifact_classification_read_only(
                self.project
            ),
            ("unresolved", 0),
        )
        self._assert_live_resume_stops_at_cleanup_unknown()

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
