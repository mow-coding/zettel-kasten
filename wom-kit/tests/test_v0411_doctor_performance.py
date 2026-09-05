from __future__ import annotations

from concurrent.futures import CancelledError, ThreadPoolExecutor, TimeoutError
from contextlib import redirect_stderr, redirect_stdout
import ctypes
import hashlib
import io
import json
import os
from pathlib import Path
import queue
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from wom_kit import (
    archive_cli,
    archive_doctor,
    archive_services,
    schema_validator,
    target_sha_evolution,
)
from wom_kit.paths import ArchivePathError


class DoctorObjectByteModeTests(unittest.TestCase):
    @staticmethod
    def _write_manifest(
        root: Path,
        *,
        body: bytes,
        repeated_location_count: int = 1,
        declared_digest: str | None = None,
    ) -> Path:
        digest = declared_digest or hashlib.sha256(body).hexdigest()
        relative = "objects/sha256/" + digest[:2] + "/" + digest
        object_path = root.joinpath(*relative.split("/"))
        object_path.parent.mkdir(parents=True)
        object_path.write_bytes(body)
        record = {
            "object_id": "sha256:" + digest,
            "sha256": digest,
            "logical_key": relative,
            "size_bytes": len(body),
            "locations": [
                {
                    "provider": "local",
                    "path": relative,
                    "availability": "available",
                }
                for _index in range(repeated_location_count)
            ],
            "provenance": {"source": "synthetic-doctor-test"},
        }
        manifest = root / "objects" / "manifests" / "files.jsonl"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        return object_path

    @staticmethod
    def _object_only_stages(
        doctor: archive_cli.Doctor,
    ) -> list[tuple[str, object]]:
        return [("object-manifest", doctor._check_object_manifest)]

    @staticmethod
    def _run_cli(arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = archive_cli.main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_operational_mode_never_claims_or_reads_current_object_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            body = b"current-object-bytes"
            object_path = self._write_manifest(root, body=body)
            object_path.write_bytes(b"x" * len(body))
            self.assertEqual(object_path.stat().st_size, len(body))
            doctor = archive_cli.Doctor(
                root,
                object_byte_verification_mode="operational",
            )

            with (
                mock.patch.object(
                    archive_cli.Doctor,
                    "_full_stages",
                    autospec=True,
                    side_effect=self._object_only_stages,
                ),
                mock.patch.object(
                    archive_cli,
                    "sha256_file",
                    side_effect=AssertionError("operational_mode_hashed_bytes"),
                ),
            ):
                diagnostics = doctor.run()

            codes = {item.code for item in diagnostics}
            self.assertIn("local_object_bytes_unverified", codes)
            self.assertNotIn("local_object_sha_mismatch", codes)
            self.assertFalse(doctor.read_observations()["objet_bytes_read"])
            summary = doctor.object_byte_verification_summary().as_dict()
            self.assertEqual(summary["result_state"], "bytes_unverified")
            self.assertFalse(summary["byte_integrity_verified"])
            self.assertEqual(
                summary["completion_revalidation"]["state"],
                "not_run",
            )
            self.assertEqual(
                summary["states"],
                {
                    "rehashed_now": 0,
                    "attested_unchanged": 0,
                    "bytes_unverified": 1,
                },
            )
            self.assertFalse(summary["all_unique_local_files_rehashed_this_run"])
            self.assertFalse(summary["attestation_reuse_supported"])
            self.assertFalse(summary["size_or_timestamp_treated_as_byte_proof"])

    def test_deep_mode_hashes_each_unique_local_path_once_at_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            self._write_manifest(
                root,
                body=b"same-path-many-references",
                repeated_location_count=1000,
            )
            doctor = archive_cli.Doctor(
                root,
                object_byte_verification_mode="deep",
            )
            real_stable_hash = archive_doctor.observe_stable_regular_file_sha256

            with (
                mock.patch.object(
                    archive_cli.Doctor,
                    "_full_stages",
                    autospec=True,
                    side_effect=self._object_only_stages,
                ),
                mock.patch.object(
                    archive_doctor,
                    "observe_stable_regular_file_sha256",
                    wraps=real_stable_hash,
                ) as stable_hash,
            ):
                diagnostics = doctor.run()

            self.assertEqual(stable_hash.call_count, 1)
            self.assertNotIn(
                "local_object_sha_mismatch",
                {item.code for item in diagnostics},
            )
            summary = doctor.object_byte_verification_summary().as_dict()
            self.assertEqual(summary["local_reference_count"], 1000)
            self.assertEqual(summary["unique_local_file_count"], 1)
            self.assertEqual(summary["states"]["rehashed_now"], 1)
            self.assertEqual(summary["states"]["bytes_unverified"], 0)
            self.assertTrue(summary["all_unique_local_files_rehashed_this_run"])
            self.assertTrue(summary["byte_integrity_verified"])
            self.assertEqual(
                summary["completion_revalidation"],
                {
                    "state": "current",
                    "revalidated_unique_local_file_count": 1,
                },
            )
            self.assertTrue(doctor.read_observations()["objet_bytes_read"])

    def test_deep_mode_preserves_existing_sha_mismatch_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            body = b"declared-original"
            object_path = self._write_manifest(root, body=body)
            object_path.write_bytes(b"x" * len(body))
            doctor = archive_cli.Doctor(
                root,
                object_byte_verification_mode="deep",
            )

            with mock.patch.object(
                archive_cli.Doctor,
                "_full_stages",
                autospec=True,
                side_effect=self._object_only_stages,
            ):
                diagnostics = doctor.run()

            mismatch = [
                item
                for item in diagnostics
                if item.code == "local_object_sha_mismatch"
            ]
            self.assertEqual(len(mismatch), 1)
            self.assertEqual(mismatch[0].severity, "ERROR")
            summary = doctor.object_byte_verification_summary().as_dict()
            self.assertEqual(summary["result_state"], "rehashed_now")
            self.assertEqual(summary["states"]["rehashed_now"], 1)

    def test_deep_mode_cannot_vacuously_verify_a_missing_local_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            object_path = self._write_manifest(
                root,
                body=b"manifested-but-missing-objet",
            )
            object_path.unlink()
            doctor = archive_cli.Doctor(
                root,
                object_byte_verification_mode="deep",
            )

            with mock.patch.object(
                archive_cli.Doctor,
                "_full_stages",
                autospec=True,
                side_effect=self._object_only_stages,
            ):
                diagnostics = doctor.run()

            self.assertIn(
                "local_object_missing",
                {item.code for item in diagnostics},
            )
            summary = doctor.object_byte_verification_summary().as_dict()
            self.assertEqual(summary["local_reference_count"], 1)
            self.assertEqual(summary["unresolved_local_reference_count"], 1)
            self.assertEqual(summary["unique_local_file_count"], 0)
            self.assertEqual(summary["result_state"], "bytes_unverified")
            self.assertFalse(summary["byte_integrity_verified"])

            with mock.patch.object(
                archive_cli.Doctor,
                "_full_stages",
                autospec=True,
                side_effect=self._object_only_stages,
            ):
                code, stdout, stderr = self._run_cli(
                    [
                        "doctor",
                        str(root),
                        "--summary",
                        "--format",
                        "json",
                        "--no-progress",
                    ]
                )

            result = json.loads(stdout)
            self.assertEqual(code, 1)
            self.assertEqual(stderr, "")
            self.assertFalse(result["ok"])
            self.assertFalse(result["byte_integrity_verified"])
            self.assertFalse(result["full_integrity_ok"])

    def test_cli_defaults_deep_and_operational_is_explicitly_unverified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            body = b"declared-original"
            object_path = self._write_manifest(root, body=body)
            object_path.write_bytes(b"x" * len(body))
            self.assertEqual(object_path.stat().st_size, len(body))

            with mock.patch.object(
                archive_cli.Doctor,
                "_full_stages",
                autospec=True,
                side_effect=self._object_only_stages,
            ):
                deep_code, deep_stdout, deep_stderr = (
                    self._run_cli(
                        [
                            "doctor",
                            str(root),
                            "--summary",
                            "--format",
                            "json",
                            "--no-progress",
                        ]
                    )
                )
                operational_code, operational_stdout, operational_stderr = self._run_cli(
                    [
                        "doctor",
                        str(root),
                        "--summary",
                        "--format",
                        "json",
                        "--object-byte-verification",
                        "operational",
                        "--no-progress",
                    ]
                )

            operational = json.loads(operational_stdout)
            deep = json.loads(deep_stdout)
            self.assertEqual(deep_code, 1)
            self.assertEqual(deep_stderr, "")
            self.assertEqual(
                deep["object_byte_verification"]["result_state"],
                "rehashed_now",
            )
            self.assertFalse(deep["ok"])
            self.assertTrue(deep["byte_integrity_verified"])
            self.assertFalse(deep["full_integrity_ok"])
            self.assertEqual(operational_code, 0)
            self.assertEqual(operational_stderr, "")
            self.assertEqual(
                operational["object_byte_verification"]["result_state"],
                "bytes_unverified",
            )
            self.assertFalse(operational["byte_integrity_verified"])
            self.assertIsNone(operational["full_integrity_ok"])

    def test_strict_rejects_operational_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            self._write_manifest(root, body=b"current-bytes")
            code, stdout, stderr = self._run_cli(
                [
                    "doctor",
                    str(root),
                    "--strict",
                    "--object-byte-verification",
                    "operational",
                    "--no-progress",
                ]
            )
            self.assertEqual(code, 2)
            self.assertEqual(stdout, "")
            self.assertIn("--strict requires", stderr)

    def test_deep_completion_hashes_current_objet_and_reports_manifest_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            body = b"initial-objet-bytes"
            object_path = self._write_manifest(root, body=body)
            doctor = archive_cli.Doctor(
                root,
                object_byte_verification_mode="deep",
            )

            def object_then_mutate() -> None:
                doctor._check_object_manifest()
                object_path.write_bytes(b"x" * len(body))

            with mock.patch.object(
                archive_cli.Doctor,
                "_full_stages",
                return_value=[("object-manifest", object_then_mutate)],
            ):
                diagnostics = doctor.run()

            self.assertIn(
                "local_object_sha_mismatch",
                {item.code for item in diagnostics},
            )
            summary = doctor.object_byte_verification_summary().as_dict()
            self.assertTrue(summary["byte_integrity_verified"])
            self.assertEqual(
                summary["completion_revalidation"]["state"],
                "current",
            )

    def test_deep_fails_unverified_when_stable_objet_read_cannot_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            self._write_manifest(root, body=b"current-objet-bytes")
            doctor = archive_cli.Doctor(
                root,
                object_byte_verification_mode="deep",
            )
            with (
                mock.patch.object(
                    archive_cli.Doctor,
                    "_full_stages",
                    autospec=True,
                    side_effect=self._object_only_stages,
                ),
                mock.patch.object(
                    archive_doctor,
                    "observe_stable_regular_file_sha256",
                    return_value=archive_doctor.DoctorStableFileHash(
                        "changed",
                        len(b"current-objet-bytes"),
                        None,
                    ),
                ),
            ):
                diagnostics = doctor.run()

            self.assertIn(
                "doctor_objet_byte_input_unverified",
                {item.code for item in diagnostics},
            )
            summary = doctor.object_byte_verification_summary().as_dict()
            self.assertFalse(summary["byte_integrity_verified"])
            self.assertEqual(
                summary["completion_revalidation"]["state"],
                "unverified",
            )


class DoctorReadCacheTests(unittest.TestCase):
    @staticmethod
    def _windows_directory_generation_record(
        name: str,
        *,
        file_id: bytes = bytes(range(1, 17)),
        attributes: int = 0x20,
        creation_time: int = 11,
        last_write_time: int = 13,
        change_time: int = 17,
        size: int = 19,
        reparse_tag: int = 0,
        next_offset: int = 0,
    ) -> bytes:
        encoded_name = name.encode("utf-16-le")
        header = struct.pack(
            "<IIqqqqqqIIII16s",
            next_offset,
            0,
            creation_time,
            0,
            last_write_time,
            change_time,
            size,
            size,
            attributes,
            len(encoded_name),
            0,
            reparse_tag,
            file_id,
        )
        record = header + encoded_name
        if next_offset:
            if next_offset < len(record):
                raise ValueError("test_directory_record_offset_too_small")
            record += b"\0" * (next_offset - len(record))
        return record

    def test_windows_directory_generation_parser_binds_exact_utf16_fields(
        self,
    ) -> None:
        first_name = "정확한-이름.json"
        first_unpadded = self._windows_directory_generation_record(first_name)
        first_offset = (len(first_unpadded) + 7) // 8 * 8
        raw = self._windows_directory_generation_record(
            first_name,
            change_time=101,
            reparse_tag=0xA000000C,
            next_offset=first_offset,
        ) + self._windows_directory_generation_record(
            "second.bin",
            file_id=bytes(range(17, 33)),
            change_time=202,
            size=23,
        )

        parsed = (
            archive_cli._doctor_parse_windows_directory_generation_buffer(
                raw
            )
        )

        self.assertEqual(set(parsed), {first_name, "second.bin"})
        self.assertEqual(parsed[first_name][5], 101)
        self.assertEqual(parsed[first_name][6], 19)
        # ReparsePointTag is undefined for a non-reparse entry and therefore
        # must not create false drift or a false unsafe classification.
        self.assertEqual(parsed[first_name][7], 0)
        self.assertEqual(parsed["second.bin"][5], 202)
        self.assertEqual(parsed["second.bin"][6], 23)

    def test_windows_directory_generation_parser_rejects_malformed_batches(
        self,
    ) -> None:
        duplicate_name = "same.json"
        first_unpadded = self._windows_directory_generation_record(
            duplicate_name
        )
        first_offset = (len(first_unpadded) + 7) // 8 * 8
        malformed = {
            "short_header": b"\0" * 87,
            "misaligned_next_offset": (
                self._windows_directory_generation_record(
                    "one.json",
                    next_offset=105,
                )
            ),
            "zero_file_id": self._windows_directory_generation_record(
                "zero.json",
                file_id=b"\0" * 16,
            ),
            "separator_in_name": self._windows_directory_generation_record(
                "bad/name.json"
            ),
            "duplicate_name": (
                self._windows_directory_generation_record(
                    duplicate_name,
                    next_offset=first_offset,
                )
                + self._windows_directory_generation_record(
                    duplicate_name,
                    file_id=bytes(range(17, 33)),
                )
            ),
        }
        odd_name_length = bytearray(
            self._windows_directory_generation_record("odd.json")
        )
        struct.pack_into("<I", odd_name_length, 60, 3)
        malformed["odd_name_bytes"] = bytes(odd_name_length)
        overlapping_name = "offset-inside-name.json".encode("utf-16-le")
        overlapping_header = struct.pack(
            "<IIqqqqqqIIII16s",
            96,  # aligned and forward, but inside the filename payload
            0,
            11,
            0,
            13,
            17,
            19,
            19,
            0x20,
            len(overlapping_name),
            0,
            0,
            bytes(range(1, 17)),
        )
        malformed["aligned_next_offset_inside_name"] = (
            overlapping_header + overlapping_name
        )

        for label, raw in malformed.items():
            with self.subTest(label=label), self.assertRaises(OSError):
                archive_cli._doctor_parse_windows_directory_generation_buffer(
                    raw
                )

    @unittest.skipUnless(os.name == "nt", "Windows generation observation")
    def test_windows_directory_generation_observation_marks_links_and_duplicates(
        self,
    ) -> None:
        observed = mock.Mock(
            st_mode=stat.S_IFREG | 0o600,
            st_size=19,
            st_file_attributes=0x20,
            st_nlink=1,
            st_dev=1,
            st_ino=2,
            st_mtime_ns=3,
            st_ctime_ns=4,
        )
        token = (
            "windows_directory_generation_observation_v1",
            101,
            bytes(range(1, 17)).hex(),
            0x20,
            11,
            13,
            17,
            19,
            0,
            True,
        )
        self.assertEqual(
            archive_cli.Doctor._file_generation_token_from_directory_observation(
                observed,
                token,
            ),
            token,
        )
        linked = mock.Mock(
            st_mode=observed.st_mode,
            st_size=observed.st_size,
            st_file_attributes=observed.st_file_attributes,
            st_nlink=2,
            st_dev=observed.st_dev,
            st_ino=observed.st_ino,
            st_mtime_ns=observed.st_mtime_ns,
            st_ctime_ns=observed.st_ctime_ns,
        )
        self.assertEqual(
            archive_cli.Doctor._file_generation_token_from_directory_observation(
                linked,
                token,
            ),
            token,
        )
        duplicate_token = (*token[:-1], False)
        self.assertEqual(
            archive_cli.Doctor._file_generation_token_from_directory_observation(
                observed,
                duplicate_token,
            ),
            duplicate_token,
        )

    @unittest.skipUnless(os.name == "nt", "Windows hardlink fallback")
    def test_hardlink_generation_uses_descriptor_hash_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "archive"
            path = root / "nested" / "cached.json"
            outside_link = base / "outside.json"
            path.parent.mkdir(parents=True)
            path.write_text('{"value":"first"}\n', encoding="utf-8")
            try:
                os.link(path, outside_link)
            except OSError as exc:
                self.skipTest(f"hardlink unavailable: {exc}")
            doctor = archive_cli.Doctor(root)
            doctor._run_stage(
                "symlink-boundaries",
                doctor._check_symlink_boundaries,
            )
            self.assertTrue(doctor._archive_tree_inventory_complete)
            doctor._load_json_file(path)
            relative = doctor._lexical_archive_relative(path)
            self.assertIsNotNone(relative)
            snapshot_key = doctor._archive_tree_key(relative or ".")
            self.assertIn(
                snapshot_key,
                doctor._archive_tree_file_generation_hash_required,
            )
            real_sha256_file = archive_cli.sha256_file

            with mock.patch.object(
                archive_cli,
                "sha256_file",
                wraps=real_sha256_file,
            ) as hash_file:
                doctor._finalize_run_file_generation_snapshots()

            self.assertEqual(hash_file.call_count, 2)
            self.assertIn(
                "doctor_cache_snapshot_current",
                {item.code for item in doctor.diagnostics},
            )

    def test_lexical_projection_caches_positive_and_negative_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "archive"
            root.mkdir()
            inside = root / "nested" / "data.json"
            outside = base / "outside.json"
            doctor = archive_cli.Doctor(root)

            self.assertEqual(
                doctor._lexical_archive_relative(inside),
                "nested/data.json",
            )
            self.assertIsNone(doctor._lexical_archive_relative(outside))

            with mock.patch.object(
                type(inside),
                "relative_to",
                side_effect=AssertionError("lexical_projection_recomputed"),
            ):
                self.assertEqual(
                    doctor._lexical_archive_relative(inside),
                    "nested/data.json",
                )
                self.assertIsNone(
                    doctor._lexical_archive_relative(outside)
                )

    def test_live_file_cache_identity_uses_one_file_and_one_root_lstat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            path = root / "nested" / "data.json"
            path.parent.mkdir(parents=True)
            path.write_text('{"value":"first"}\n', encoding="utf-8")
            doctor = archive_cli.Doctor(root)
            doctor._check_symlink_boundaries()
            expected = doctor._stat_identity(os.lstat(path))
            original_lstat = os.lstat
            observed_paths: list[Path] = []

            def counted_lstat(candidate: object) -> os.stat_result:
                observed_paths.append(Path(candidate))
                return original_lstat(candidate)

            with mock.patch.object(
                archive_cli.os,
                "lstat",
                side_effect=counted_lstat,
            ):
                observed = doctor._file_cache_identity(path)

            self.assertEqual(observed, expected)
            self.assertEqual(len(observed_paths), 2)
            canonical_path = doctor.archive_root / "nested" / "data.json"
            self.assertEqual(observed_paths.count(canonical_path), 1)
            self.assertEqual(observed_paths.count(doctor.archive_root), 1)

            path.write_text(
                '{"value":"a-different-generation"}\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                OSError,
                "doctor_archive_cache_boundary_changed",
            ):
                doctor._file_cache_identity(path)

    def test_stage_reuses_root_observation_but_keeps_boundary_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            path = root / "nested" / "data.json"
            path.parent.mkdir(parents=True)
            path.write_text('{"value":"first"}\n', encoding="utf-8")
            doctor = archive_cli.Doctor(root)
            doctor._run_stage(
                "symlink-boundaries",
                doctor._check_symlink_boundaries,
            )
            original_lstat = os.lstat
            observed_paths: list[Path] = []

            def counted_lstat(candidate: object) -> os.stat_result:
                observed_paths.append(Path(candidate))
                return original_lstat(candidate)

            with mock.patch.object(
                archive_cli.os,
                "lstat",
                side_effect=counted_lstat,
            ):
                doctor._run_stage(
                    "identity",
                    lambda: doctor._file_cache_identity(path),
                )

            # Stage entry and exit still observe the root.  The cache identity
            # itself performs only the exact file lstat inside that bracket.
            self.assertEqual(observed_paths.count(doctor.archive_root), 2)
            canonical_path = doctor.archive_root / "nested" / "data.json"
            self.assertEqual(observed_paths.count(canonical_path), 1)

    def test_resolved_reference_is_revalidated_at_run_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            path = root / "nested" / "data.json"
            path.parent.mkdir(parents=True)
            path.write_text('{"value":"first"}\n', encoding="utf-8")
            doctor = archive_cli.Doctor(root)
            doctor._run_stage(
                "symlink-boundaries",
                doctor._check_symlink_boundaries,
            )

            resolved = doctor._resolve_archive_relative_path(
                "nested/data.json"
            )
            self.assertTrue(os.path.samefile(resolved, path))
            self.assertTrue(doctor._run_file_generation_snapshots)

            path.write_text(
                '{"value":"changed-generation"}\n',
                encoding="utf-8",
            )
            doctor._finalize_run_file_generation_snapshots()

            stale = next(
                item
                for item in doctor.diagnostics
                if item.code == "doctor_cache_snapshot_stale"
            )
            self.assertEqual(stale.details["changed_file_count"], 1)

    def test_file_created_after_inventory_is_not_adopted_mid_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            parent = root / "nested"
            parent.mkdir(parents=True)
            doctor = archive_cli.Doctor(root)
            doctor._run_stage(
                "symlink-boundaries",
                doctor._check_symlink_boundaries,
            )

            (parent / "created.json").write_text(
                "{}\n",
                encoding="utf-8",
            )

            # Even if a platform's directory metadata were made to look
            # unchanged, the newly present final entry is not adopted into
            # the frozen generation.
            with (
                mock.patch.object(
                    doctor,
                    "_inventory_ancestor_chain_matches",
                    return_value=True,
                ),
                mock.patch.object(
                    doctor,
                    "_inventory_identity_matches",
                    return_value=True,
                ),
                self.assertRaisesRegex(
                    ArchivePathError,
                    "appeared after",
                ),
            ):
                doctor._resolve_archive_relative_path("nested/created.json")

    def test_final_entry_still_missing_after_inventory_stays_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            (root / "nested").mkdir(parents=True)
            doctor = archive_cli.Doctor(root)
            doctor._run_stage(
                "symlink-boundaries",
                doctor._check_symlink_boundaries,
            )

            resolved = doctor._resolve_archive_relative_path(
                "nested/missing.json"
            )

            self.assertFalse(resolved.exists())
            self.assertEqual(
                doctor._lexical_archive_relative(resolved),
                "nested/missing.json",
            )

    def test_inventory_stage_revalidation_detects_concurrent_tree_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            parent = root / "nested"
            parent.mkdir(parents=True)
            (parent / "existing.json").write_text(
                "{}\n",
                encoding="utf-8",
            )
            doctor = archive_cli.Doctor(root)

            def inventory_then_change() -> None:
                doctor._check_symlink_boundaries()
                (parent / "created-during-stage.json").write_text(
                    "{}\n",
                    encoding="utf-8",
                )

            doctor._run_stage(
                "symlink-boundaries",
                inventory_then_change,
            )

            self.assertIn(
                "archive_stage_directory_boundary_changed",
                {item.code for item in doctor.diagnostics},
            )
            self.assertFalse(doctor._archive_tree_inventory_complete)
            self.assertFalse(doctor._run_cache_snapshot_active)

            secret = parent / "created-after-invalid-inventory.json"
            secret.write_text(
                json.dumps({"value": "token=" + "B" * 24}) + "\n",
                encoding="utf-8",
            )
            with mock.patch.object(
                doctor,
                "_check_local_profile_and_secret_safety_from_inventory",
                side_effect=AssertionError("invalid_inventory_was_reused"),
            ):
                doctor._check_local_profile_and_secret_safety()
            self.assertIn(
                "secret_value_detected",
                {item.code for item in doctor.diagnostics},
            )

    def test_parallel_tree_inventory_captures_each_file_generation_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            files = root / "many"
            files.mkdir(parents=True)
            expected_paths = []
            for index in range(64):
                path = files / f"item-{index:03d}.json"
                path.write_text("{}\n", encoding="utf-8")
                expected_paths.append(path)
            doctor = archive_cli.Doctor(root)
            original_lstat = os.lstat
            counts: dict[Path, int] = {}
            counts_lock = threading.Lock()

            def counted_lstat(candidate: object) -> os.stat_result:
                path = Path(candidate)
                with counts_lock:
                    counts[path] = counts.get(path, 0) + 1
                return original_lstat(candidate)

            with mock.patch.object(
                archive_cli.os,
                "lstat",
                side_effect=counted_lstat,
            ):
                doctor._check_symlink_boundaries()

            self.assertTrue(doctor._archive_tree_inventory_complete)
            self.assertEqual(
                len(doctor._archive_tree_file_identities),
                len(expected_paths),
            )
            canonical_paths = [
                doctor.archive_root / "many" / path.name
                for path in expected_paths
            ]
            self.assertTrue(
                all(counts.get(path) == 1 for path in canonical_paths)
            )

    def test_inventory_lstat_unavailable_is_nonclean_and_secret_scan_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            files = root / "many"
            files.mkdir(parents=True)
            target = files / "target.json"
            target.write_text(
                json.dumps({"value": "token=" + "A" * 24}) + "\n",
                encoding="utf-8",
            )
            for index in range(63):
                (files / f"item-{index:03d}.json").write_text(
                    "{}\n",
                    encoding="utf-8",
                )
            doctor = archive_cli.Doctor(root)
            canonical_target = doctor.archive_root / "many" / "target.json"
            original_lstat = os.lstat
            failed_once = False
            failure_lock = threading.Lock()

            def transient_lstat(candidate: object) -> os.stat_result:
                nonlocal failed_once
                path = Path(candidate)
                with failure_lock:
                    should_fail = path == canonical_target and not failed_once
                    if should_fail:
                        failed_once = True
                if should_fail:
                    raise PermissionError("synthetic_inventory_unavailable")
                return original_lstat(candidate)

            with (
                mock.patch.object(
                    doctor,
                    "_full_stages",
                    return_value=[
                        (
                            "symlink-boundaries",
                            doctor._check_symlink_boundaries,
                        ),
                        (
                            "local-profile-secret-safety",
                            doctor._check_local_profile_and_secret_safety,
                        ),
                    ],
                ),
                mock.patch.object(
                    archive_cli.os,
                    "lstat",
                    side_effect=transient_lstat,
                ),
            ):
                diagnostics = doctor.run()

            self.assertFalse(doctor._archive_tree_inventory_complete)
            unavailable = next(
                item
                for item in diagnostics
                if item.code == "doctor_archive_inventory_unavailable"
            )
            self.assertEqual(unavailable.severity, "ERROR")
            self.assertIsNone(unavailable.path)
            self.assertFalse(unavailable.details["paths_echoed"])
            self.assertIn(
                "secret_value_detected",
                {item.code for item in diagnostics},
            )

    @unittest.skipUnless(os.name == "nt", "Windows junction regression")
    def test_queued_inventory_directory_junction_swap_is_never_enumerated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "archive"
            queued = root / "queued-private-child"
            queued.mkdir(parents=True)
            (queued / "ordinary.json").write_text("{}\n", encoding="utf-8")
            outside = base / "outside-private-root"
            outside.mkdir()
            external_basename = "HIGHLY-PRIVATE-EXTERNAL-BASENAME.env"
            (outside / external_basename).write_text(
                "token=" + "C" * 24 + "\n",
                encoding="utf-8",
            )
            saved = root / "queued-original"
            doctor = archive_cli.Doctor(root)
            canonical_queued = doctor.archive_root / queued.name
            original_lstat = os.lstat
            queued_observations = 0
            swapped = False

            def swap_before_scandir(candidate: object) -> os.stat_result:
                nonlocal queued_observations, swapped
                path = Path(candidate)
                if path == canonical_queued:
                    queued_observations += 1
                    if queued_observations == 2:
                        canonical_queued.rename(saved)
                        created = subprocess.run(
                            [
                                "cmd",
                                "/c",
                                "mklink",
                                "/J",
                                str(canonical_queued),
                                str(outside),
                            ],
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        if created.returncode != 0:
                            saved.rename(canonical_queued)
                            self.skipTest(
                                "Windows directory junction creation unavailable"
                            )
                        swapped = True
                return original_lstat(candidate)

            try:
                with mock.patch.object(
                    archive_cli.os,
                    "lstat",
                    side_effect=swap_before_scandir,
                ):
                    doctor._run_stage(
                        "symlink-boundaries",
                        doctor._check_symlink_boundaries,
                    )

                # An incomplete inventory forces the live secret-scan path.
                # It may report the lexical in-archive junction but must not
                # enumerate or echo the external directory's member names.
                doctor._check_local_profile_and_secret_safety()

                self.assertTrue(swapped)
                self.assertFalse(doctor._archive_tree_inventory_complete)
                self.assertFalse(doctor._run_cache_snapshot_active)
                boundary = next(
                    item
                    for item in doctor.diagnostics
                    if item.code
                    == "doctor_archive_inventory_boundary_changed"
                )
                self.assertEqual(boundary.severity, "ERROR")
                self.assertIsNone(boundary.path)
                self.assertFalse(boundary.details["paths_echoed"])
                serialized = json.dumps(
                    [item.as_dict() for item in doctor.diagnostics],
                    sort_keys=True,
                )
                self.assertNotIn(external_basename, serialized)
                self.assertNotIn(str(outside), serialized)
            finally:
                if swapped and canonical_queued.exists():
                    canonical_queued.rmdir()
                if saved.exists():
                    saved.rename(canonical_queued)

    @unittest.skipUnless(os.name == "nt", "Windows retained handle regression")
    def test_retained_directory_handle_blocks_junction_swap_during_scandir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "archive"
            queued = root / "queued-child"
            queued.mkdir(parents=True)
            (queued / "inside.json").write_text("{}\n", encoding="utf-8")
            outside = base / "outside-private-root"
            outside.mkdir()
            external_basename = "PRIVATE-SCAN-TARGET.env"
            (outside / external_basename).write_text(
                "token=" + "D" * 24 + "\n",
                encoding="utf-8",
            )
            saved = root / "queued-saved"
            doctor = archive_cli.Doctor(root)
            canonical_queued = doctor.archive_root / queued.name
            original_scandir = os.scandir
            attempted = False
            rename_blocked = False
            unexpected_swap = False

            def attempt_swap_during_scan(path: object) -> object:
                nonlocal attempted, rename_blocked, unexpected_swap
                candidate = Path(path)
                if candidate == canonical_queued and not attempted:
                    attempted = True
                    try:
                        canonical_queued.rename(saved)
                    except OSError:
                        rename_blocked = True
                    else:
                        unexpected_swap = True
                        subprocess.run(
                            [
                                "cmd",
                                "/c",
                                "mklink",
                                "/J",
                                str(canonical_queued),
                                str(outside),
                            ],
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        raise OSError("retained_directory_handle_failed")
                return original_scandir(path)

            try:
                with mock.patch.object(
                    archive_cli.os,
                    "scandir",
                    side_effect=attempt_swap_during_scan,
                ):
                    doctor._run_stage(
                        "symlink-boundaries",
                        doctor._check_symlink_boundaries,
                    )

                self.assertTrue(attempted)
                self.assertTrue(rename_blocked)
                self.assertFalse(unexpected_swap)
                self.assertTrue(doctor._archive_tree_inventory_complete)
                inventoried_keys = set(doctor._archive_tree_file_identities)
                self.assertFalse(
                    any(external_basename.casefold() in key.casefold() for key in inventoried_keys)
                )
            finally:
                if unexpected_swap and canonical_queued.exists():
                    canonical_queued.rmdir()
                if saved.exists():
                    saved.rename(canonical_queued)

    def test_archive_inventory_capacity_fails_closed_without_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            root.mkdir()
            for index in range(8):
                (root / f"item-{index}.json").write_text(
                    "{}\n",
                    encoding="utf-8",
                )
            doctor = archive_cli.Doctor(root)

            with mock.patch.object(
                archive_cli,
                "DOCTOR_ARCHIVE_TREE_INVENTORY_MAX_ENTRIES",
                4,
            ):
                doctor._run_stage(
                    "symlink-boundaries",
                    doctor._check_symlink_boundaries,
                )

            self.assertFalse(doctor._archive_tree_inventory_complete)
            self.assertFalse(doctor._run_cache_snapshot_active)
            capacity = next(
                item
                for item in doctor.diagnostics
                if item.code == "doctor_archive_inventory_capacity_exceeded"
            )
            self.assertIsNone(capacity.path)
            self.assertFalse(capacity.details["paths_echoed"])

    def test_run_cache_snapshot_capacity_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            root.mkdir()
            paths = []
            for index in range(4):
                path = root / f"item-{index}.json"
                path.write_text("{}\n", encoding="utf-8")
                paths.append(path)
            doctor = archive_cli.Doctor(root)
            doctor._run_stage(
                "symlink-boundaries",
                doctor._check_symlink_boundaries,
            )

            with mock.patch.object(
                archive_cli,
                "DOCTOR_RUN_CACHE_SNAPSHOT_MAX_ENTRIES",
                2,
            ):
                for path in paths:
                    doctor._load_json_file(path)

            self.assertFalse(doctor._run_cache_snapshot_active)
            self.assertEqual(doctor._run_file_generation_snapshots, {})
            capacity = [
                item
                for item in doctor.diagnostics
                if item.code == "doctor_cache_snapshot_capacity_exceeded"
            ]
            self.assertEqual(len(capacity), 1)
            self.assertIsNone(capacity[0].path)
            self.assertFalse(capacity[0].details["paths_echoed"])

    def test_clean_directory_projection_replaces_duplicate_file_barriers(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            path = root / "nested" / "cached.json"
            path.parent.mkdir(parents=True)
            path.write_text('{"value":"first"}\n', encoding="utf-8")
            doctor = archive_cli.Doctor(root)
            doctor._run_stage(
                "symlink-boundaries",
                doctor._check_symlink_boundaries,
            )
            doctor._load_json_file(path)
            canonical_path = doctor.archive_root / "nested" / "cached.json"
            original_lstat = os.lstat
            target_observations = 0

            def counted_lstat(candidate: object) -> os.stat_result:
                nonlocal target_observations
                if Path(candidate) == canonical_path:
                    target_observations += 1
                return original_lstat(candidate)

            with mock.patch.object(
                archive_cli.os,
                "lstat",
                side_effect=counted_lstat,
            ):
                doctor._finalize_run_file_generation_snapshots()

            # Windows pass 1 compares the exact native directory digest.  The
            # child receives one lstat in the full pass 2; a separate pair of
            # file lstat calls would duplicate that clean projection.
            self.assertEqual(
                target_observations,
                1 if os.name == "nt" else 2,
            )
            self.assertIn(
                "doctor_cache_snapshot_current",
                {item.code for item in doctor.diagnostics},
            )

    @unittest.skipUnless(os.name == "nt", "Windows ChangeTime regression")
    def test_fast_projection_detects_same_inode_write_with_mtime_restored(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            path = root / "nested" / "cached.json"
            path.parent.mkdir(parents=True)
            original = b'{"value":"first"}\n'
            changed = b'{"value":"other"}\n'
            self.assertEqual(len(original), len(changed))
            path.write_bytes(original)
            doctor = archive_cli.Doctor(root)
            doctor._run_stage(
                "symlink-boundaries",
                doctor._check_symlink_boundaries,
            )
            doctor._load_json_file(path)
            before = os.lstat(path)
            relative = doctor._lexical_archive_relative(path)
            self.assertIsNotNone(relative)
            snapshot_key = doctor._archive_tree_key(relative or ".")
            self.assertIn(
                snapshot_key,
                doctor._archive_tree_file_generation_tokens,
            )
            frozen_token = doctor._archive_tree_file_generation_tokens[
                snapshot_key
            ]
            self.assertEqual(
                frozen_token[0],
                "windows_directory_generation_observation_v1",
            )
            self.assertIsInstance(frozen_token[1], int)
            self.assertEqual(len(frozen_token), 10)

            time.sleep(0.02)
            with path.open("r+b") as stream:
                stream.write(changed)
                stream.flush()
                os.fsync(stream.fileno())
            os.utime(
                path,
                ns=(int(before.st_atime_ns), int(before.st_mtime_ns)),
            )
            after = os.lstat(path)
            self.assertEqual(before.st_ino, after.st_ino)
            self.assertEqual(
                doctor._stat_identity(before),
                doctor._stat_identity(after),
            )

            doctor._finalize_run_file_generation_snapshots()

            stale = next(
                item
                for item in doctor.diagnostics
                if item.code == "doctor_cache_snapshot_stale"
            )
            self.assertGreaterEqual(stale.details["changed_directory_count"], 1)
            self.assertEqual(stale.details["changed_file_count"], 1)
            self.assertIsNone(stale.path)
            self.assertFalse(stale.details["paths_echoed"])
            self.assertFalse(stale.details["private_values_echoed"])

    @unittest.skipUnless(os.name == "nt", "Windows ChangeTime regression")
    def test_file_fallback_detects_same_inode_write_with_mtime_restored(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            path = root / "nested" / "cached.json"
            path.parent.mkdir(parents=True)
            original = b'{"value":"first"}\n'
            changed = b'{"value":"other"}\n'
            path.write_bytes(original)
            doctor = archive_cli.Doctor(root)
            doctor._run_stage(
                "symlink-boundaries",
                doctor._check_symlink_boundaries,
            )
            doctor._load_json_file(path)
            relative = doctor._lexical_archive_relative(path)
            self.assertIsNotNone(relative)
            snapshot_key = doctor._archive_tree_key(relative or ".")
            self.assertIn(
                snapshot_key,
                doctor._archive_tree_file_generation_tokens,
            )
            # Remove only the stat projection so completion must exercise the
            # historical file-pass fallback while retaining its frozen native
            # generation token.
            doctor._archive_tree_file_identities.pop(snapshot_key)
            before = os.lstat(path)

            time.sleep(0.02)
            with path.open("r+b") as stream:
                stream.write(changed)
                stream.flush()
                os.fsync(stream.fileno())
            os.utime(
                path,
                ns=(int(before.st_atime_ns), int(before.st_mtime_ns)),
            )
            after = os.lstat(path)
            self.assertEqual(before.st_ino, after.st_ino)
            self.assertEqual(
                doctor._stat_identity(before),
                doctor._stat_identity(after),
            )

            doctor._finalize_run_file_generation_snapshots()

            stale = next(
                item
                for item in doctor.diagnostics
                if item.code == "doctor_cache_snapshot_stale"
            )
            self.assertEqual(stale.details["changed_file_count"], 1)
            self.assertNotIn(
                "doctor_cache_snapshot_current",
                {item.code for item in doctor.diagnostics},
            )

    @unittest.skipUnless(os.name == "nt", "Windows ChangeTime regression")
    def test_native_generation_unavailable_never_reports_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            path = root / "nested" / "cached.json"
            path.parent.mkdir(parents=True)
            path.write_text('{"value":"first"}\n', encoding="utf-8")
            doctor = archive_cli.Doctor(root)
            doctor._run_stage(
                "symlink-boundaries",
                doctor._check_symlink_boundaries,
            )
            doctor._load_json_file(path)

            with mock.patch.object(
                archive_cli.Doctor,
                "_retained_windows_directory_generations",
                return_value=None,
            ):
                doctor._finalize_run_file_generation_snapshots()

            codes = {item.code for item in doctor.diagnostics}
            self.assertIn("doctor_cache_snapshot_stale", codes)
            self.assertNotIn("doctor_cache_snapshot_current", codes)
            stale = next(
                item
                for item in doctor.diagnostics
                if item.code == "doctor_cache_snapshot_stale"
            )
            self.assertIsNone(stale.path)
            self.assertFalse(stale.details["paths_echoed"])
            self.assertFalse(stale.details["private_values_echoed"])

    def test_directory_projection_binds_full_file_generation_shape(self) -> None:
        def observed_stat(
            *,
            mode: int = stat.S_IFREG | 0o600,
            inode: int = 11,
            size: int = 5,
            modified: int = 13,
            changed: int = 17,
            attributes: int = 0,
            links: int = 1,
        ) -> mock.Mock:
            return mock.Mock(
                st_dev=7,
                st_ino=inode,
                st_mode=mode,
                st_size=size,
                st_mtime_ns=modified,
                st_ctime_ns=changed,
                st_file_attributes=attributes,
                st_nlink=links,
            )

        regular = observed_stat()
        self.assertEqual(
            archive_cli.Doctor._inventory_stat_identity(regular),
            archive_cli.Doctor._stat_identity(regular),
        )
        variants = (
            regular,
            observed_stat(inode=12),
            observed_stat(size=6),
            observed_stat(modified=14),
            observed_stat(changed=18),
            observed_stat(links=2),
            observed_stat(mode=stat.S_IFLNK | 0o600),
            observed_stat(attributes=0x00000400),
        )
        digests = {
            archive_cli.Doctor._inventory_directory_entry_digest(
                [(Path("entry"), value)]
            )
            for value in variants
        }
        self.assertEqual(len(digests), len(variants))

    def test_same_size_mtime_restored_replacement_uses_file_fallback(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            path = root / "nested" / "cached.json"
            path.parent.mkdir(parents=True)
            path.write_text('{"value":"first"}\n', encoding="utf-8")
            doctor = archive_cli.Doctor(root)
            doctor._run_stage(
                "symlink-boundaries",
                doctor._check_symlink_boundaries,
            )
            doctor._load_json_file(path)
            before = os.lstat(path)
            time.sleep(0.01)
            replacement = path.with_name("replacement.json")
            replacement.write_text(
                '{"value":"other"}\n',
                encoding="utf-8",
            )
            os.utime(
                replacement,
                ns=(int(before.st_atime_ns), int(before.st_mtime_ns)),
            )
            os.replace(replacement, path)

            doctor._finalize_run_file_generation_snapshots()

            stale = next(
                item
                for item in doctor.diagnostics
                if item.code == "doctor_cache_snapshot_stale"
            )
            self.assertEqual(stale.details["changed_file_count"], 1)
            self.assertGreaterEqual(
                stale.details["changed_directory_count"],
                1,
            )

    def test_missing_parent_projection_keeps_file_and_final_directory_barriers(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            path = root / "nested" / "cached.json"
            path.parent.mkdir(parents=True)
            path.write_text('{"value":"first"}\n', encoding="utf-8")
            doctor = archive_cli.Doctor(root)
            doctor._run_stage(
                "symlink-boundaries",
                doctor._check_symlink_boundaries,
            )
            doctor._load_json_file(path)
            parent_relative = doctor._lexical_archive_relative(path.parent)
            self.assertIsNotNone(parent_relative)
            parent_key = doctor._archive_tree_key(parent_relative or ".")
            doctor._archive_tree_directory_entry_digests.pop(parent_key)
            canonical_path = doctor.archive_root / "nested" / "cached.json"
            original_lstat = os.lstat
            target_observations = 0
            directory_passes: list[int] = []

            def counted_lstat(candidate: object) -> os.stat_result:
                nonlocal target_observations
                if Path(candidate) == canonical_path:
                    target_observations += 1
                return original_lstat(candidate)

            def record_progress(
                stage: str,
                message: str,
                _current: int | None,
                _total: int | None,
            ) -> None:
                if (
                    stage == "doctor-cache-snapshot-revalidation"
                    and message.startswith("directory membership barrier pass ")
                    and not message.endswith(" done")
                ):
                    pass_number = int(message.rsplit(" ", 1)[1])
                    if not directory_passes or directory_passes[-1] != pass_number:
                        directory_passes.append(pass_number)

            doctor.progress_callback = record_progress
            with mock.patch.object(
                archive_cli.os,
                "lstat",
                side_effect=counted_lstat,
            ):
                doctor._finalize_run_file_generation_snapshots()

            self.assertEqual(target_observations, 2)
            self.assertEqual(
                directory_passes,
                [2, 3] if os.name == "nt" else [1, 2, 3],
            )
            self.assertIn(
                "doctor_cache_snapshot_stale",
                {item.code for item in doctor.diagnostics},
            )

    def test_fallback_file_read_is_followed_by_final_directory_barrier(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            path = root / "nested" / "cached.json"
            late_parent = root / "late-parent"
            path.parent.mkdir(parents=True)
            late_parent.mkdir()
            path.write_text('{"value":"first"}\n', encoding="utf-8")
            doctor = archive_cli.Doctor(root)
            doctor._run_stage(
                "symlink-boundaries",
                doctor._check_symlink_boundaries,
            )
            doctor._load_json_file(path)
            canonical_path = doctor.archive_root / "nested" / "cached.json"

            # Make only this file ineligible for projection reuse.  Its parent
            # digest remains complete and current, so the first two directory
            # passes are clean and the historical file fallback is exercised.
            relative = doctor._lexical_archive_relative(path)
            self.assertIsNotNone(relative)
            doctor._archive_tree_file_identities.pop(
                doctor._archive_tree_key(relative or ".")
            )
            original_lstat = os.lstat
            target_observations = 0

            def mutate_after_second_file_barrier(
                candidate: object,
            ) -> os.stat_result:
                nonlocal target_observations
                observed = original_lstat(candidate)
                if Path(candidate) == canonical_path:
                    target_observations += 1
                    # On Windows native pass 1 does not lstat the child.  Full
                    # pass 2 observes it first and fallback file pass 1/2 are
                    # observations 2/3.  Change a different inventoried parent
                    # after the final file read, where omitting pass 3 misses it.
                    mutation_observation = 3 if os.name == "nt" else 4
                    if target_observations == mutation_observation:
                        (late_parent / "late.json").write_text(
                            "{}\n",
                            encoding="utf-8",
                        )
                return observed

            with mock.patch.object(
                archive_cli.os,
                "lstat",
                side_effect=mutate_after_second_file_barrier,
            ):
                doctor._finalize_run_file_generation_snapshots()

            stale = next(
                item
                for item in doctor.diagnostics
                if item.code == "doctor_cache_snapshot_stale"
            )
            # The last observation is the target entry in the required full
            # directory barrier after the file fallback described above.
            self.assertEqual(
                target_observations,
                4 if os.name == "nt" else 5,
            )
            self.assertEqual(stale.details["changed_file_count"], 0)
            self.assertGreaterEqual(
                stale.details["changed_directory_count"],
                1,
            )

    def test_file_identity_detects_hardlink_count_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "archive"
            outside = base / "outside"
            path = root / "nested" / "data.json"
            path.parent.mkdir(parents=True)
            outside.mkdir()
            path.write_text('{"value":"first"}\n', encoding="utf-8")
            doctor = archive_cli.Doctor(root)
            doctor._run_stage(
                "symlink-boundaries",
                doctor._check_symlink_boundaries,
            )
            doctor._load_json_file(path)
            before = os.lstat(path)
            link = outside / "linked.json"
            try:
                os.link(path, link)
            except OSError as exc:
                self.skipTest(f"hardlink unavailable: {exc}")
            self.assertGreater(os.lstat(path).st_nlink, before.st_nlink)

            doctor._finalize_run_file_generation_snapshots()

            stale = next(
                item
                for item in doctor.diagnostics
                if item.code == "doctor_cache_snapshot_stale"
            )
            self.assertEqual(stale.details["changed_file_count"], 1)

    def test_second_revalidation_barrier_detects_post_worker_byte_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            files = root / "many"
            files.mkdir(parents=True)
            paths = []
            for index in range(64):
                path = files / f"item-{index:03d}.json"
                path.write_text('{"v":1}\n', encoding="utf-8")
                paths.append(path)
            doctor = archive_cli.Doctor(root)
            doctor._run_stage(
                "symlink-boundaries",
                doctor._check_symlink_boundaries,
            )
            for path in paths:
                doctor._load_json_file(path)
            target = doctor.archive_root / "many" / paths[0].name
            original_lstat = os.lstat
            target_observations = 0
            observation_lock = threading.Lock()

            def mutate_after_first_observation(
                candidate: object,
            ) -> os.stat_result:
                nonlocal target_observations
                path = Path(candidate)
                observed = original_lstat(candidate)
                if path == target:
                    with observation_lock:
                        target_observations += 1
                        mutate = target_observations == 1
                    if mutate:
                        target.write_text('{"v":2}\n', encoding="utf-8")
                return observed

            with mock.patch.object(
                archive_cli.os,
                "lstat",
                side_effect=mutate_after_first_observation,
            ):
                doctor._finalize_run_file_generation_snapshots()

            self.assertGreaterEqual(target_observations, 2)
            stale = next(
                item
                for item in doctor.diagnostics
                if item.code == "doctor_cache_snapshot_stale"
            )
            self.assertEqual(stale.details["changed_file_count"], 1)

    def test_cache_clean_claim_runs_after_late_command_status_finalizer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            path = root / "nested" / "data.json"
            path.parent.mkdir(parents=True)
            path.write_text('{"v":1}\n', encoding="utf-8")
            doctor = archive_cli.Doctor(root)

            def load_cached_input() -> None:
                self.assertEqual(doctor._load_json_file(path), {"v": 1})

            def late_command_status_read_and_mutation() -> None:
                path.write_text('{"v":2}\n', encoding="utf-8")

            with (
                mock.patch.object(
                    doctor,
                    "_full_stages",
                    return_value=[
                        (
                            "symlink-boundaries",
                            doctor._check_symlink_boundaries,
                        ),
                        ("cached-input", load_cached_input),
                    ],
                ),
                mock.patch.object(
                    doctor,
                    "_attach_suggested_command_statuses",
                    side_effect=late_command_status_read_and_mutation,
                ),
            ):
                diagnostics = doctor.run()

            codes = [item.code for item in diagnostics]
            self.assertIn("doctor_cache_snapshot_stale", codes)
            self.assertNotIn("doctor_cache_snapshot_current", codes)

    def test_late_new_member_in_uncached_directory_makes_snapshot_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            empty = root / "initially-empty"
            empty.mkdir(parents=True)
            stable = root / "stable.json"
            stable.write_text("{}\n", encoding="utf-8")
            doctor = archive_cli.Doctor(root)
            private_basename = "PRIVATE-LATE-SECRET.env"
            private_value = "token=" + "Z" * 24
            empty_before = os.stat(empty)

            def load_cached_input() -> None:
                self.assertEqual(doctor._load_json_file(stable), {})

            def create_after_inventory() -> None:
                (empty / private_basename).write_text(
                    private_value + "\n",
                    encoding="utf-8",
                )
                os.utime(
                    empty,
                    ns=(empty_before.st_atime_ns, empty_before.st_mtime_ns),
                )

            with mock.patch.object(
                doctor,
                "_full_stages",
                return_value=[
                    (
                        "symlink-boundaries",
                        doctor._check_symlink_boundaries,
                    ),
                    ("cached-input", load_cached_input),
                    ("late-member", create_after_inventory),
                    (
                        "local-profile-secret-safety",
                        doctor._check_local_profile_and_secret_safety,
                    ),
                ],
            ):
                diagnostics = doctor.run()

            codes = [item.code for item in diagnostics]
            self.assertIn("doctor_cache_snapshot_stale", codes)
            self.assertNotIn("doctor_cache_snapshot_current", codes)
            stale = next(
                item
                for item in diagnostics
                if item.code == "doctor_cache_snapshot_stale"
            )
            self.assertGreaterEqual(stale.details["changed_directory_count"], 1)
            serialized = json.dumps(
                [item.as_dict() for item in diagnostics],
                sort_keys=True,
            )
            self.assertNotIn(private_basename, serialized)
            self.assertNotIn(private_value, serialized)

    def test_stage_interrupt_never_starts_queued_deep_hash_finalizer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            objects = root / "objects"
            objects.mkdir(parents=True)
            doctor = archive_cli.Doctor(
                root,
                object_byte_verification_mode="deep",
            )

            def queue_then_interrupt() -> None:
                for index in range(32):
                    path = objects / f"queued-{index:02d}.bin"
                    path.write_bytes(b"queued")
                    doctor._object_byte_observations_by_path[str(path)] = (
                        path,
                        len(b"queued"),
                        hashlib.sha256(b"queued").hexdigest(),
                    )
                raise KeyboardInterrupt()

            with (
                mock.patch.object(
                    doctor,
                    "_full_stages",
                    return_value=[("interrupted-stage", queue_then_interrupt)],
                ),
                mock.patch.object(
                    archive_doctor,
                    "observe_stable_regular_file_sha256",
                    side_effect=AssertionError("deep_hash_started_after_interrupt"),
                ) as stable_hash,
                mock.patch.object(
                    doctor,
                    "_finalize_stage_directory_generations",
                    side_effect=AssertionError("stage_finalizer_started_after_interrupt"),
                ) as stage_finalizer,
                self.assertRaises(KeyboardInterrupt),
            ):
                doctor.run()

            stable_hash.assert_not_called()
            stage_finalizer.assert_not_called()
            self.assertFalse(doctor._run_cache_snapshot_active)
            self.assertEqual(
                doctor._object_byte_completion_revalidation_state,
                "not_run",
            )

    def test_stage_runtime_failure_never_starts_completion_finalizers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            root.mkdir()
            doctor = archive_cli.Doctor(
                root,
                object_byte_verification_mode="deep",
            )

            def fail_stage() -> None:
                raise RuntimeError("synthetic_stage_failure")

            with (
                mock.patch.object(
                    doctor,
                    "_full_stages",
                    return_value=[("failed-stage", fail_stage)],
                ),
                mock.patch.object(
                    doctor,
                    "_finalize_object_byte_observations",
                    side_effect=AssertionError("object_finalizer_started"),
                ) as object_finalizer,
                mock.patch.object(
                    doctor,
                    "_finalize_object_manifest_snapshot",
                    side_effect=AssertionError("manifest_finalizer_started"),
                ) as manifest_finalizer,
                mock.patch.object(
                    doctor,
                    "_attach_suggested_command_statuses",
                    side_effect=AssertionError("command_status_finalizer_started"),
                ) as status_finalizer,
                mock.patch.object(
                    doctor,
                    "_finalize_run_file_generation_snapshots",
                    side_effect=AssertionError("cache_finalizer_started"),
                ) as cache_finalizer,
                self.assertRaisesRegex(
                    RuntimeError,
                    "synthetic_stage_failure",
                ),
            ):
                doctor.run()

            object_finalizer.assert_not_called()
            manifest_finalizer.assert_not_called()
            status_finalizer.assert_not_called()
            cache_finalizer.assert_not_called()

    def test_parallel_map_interrupt_cancels_pending_io_and_keeps_heartbeat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            root.mkdir()
            reporter = archive_cli.CommandProgressReporter(
                True,
                label="doctor-test",
                heartbeat_interval_seconds=0.01,
            )
            doctor = archive_cli.Doctor(
                root,
                progress_callback=reporter.progress,
            )
            shutdown_calls: list[tuple[bool, bool]] = []

            class InterruptingExecutor:
                def __init__(self, **_kwargs: object) -> None:
                    pass

                def submit(
                    self,
                    _function: object,
                    _value: object,
                ) -> object:
                    class InterruptingFuture:
                        def result(self) -> object:
                            time.sleep(0.06)
                            raise KeyboardInterrupt()

                    return InterruptingFuture()

                def shutdown(
                    self,
                    *,
                    wait: bool,
                    cancel_futures: bool,
                ) -> None:
                    shutdown_calls.append((wait, cancel_futures))

            stderr = io.StringIO()
            started = time.monotonic()
            try:
                with (
                    redirect_stderr(stderr),
                    mock.patch.object(
                        archive_cli,
                        "_DoctorBoundedDaemonExecutor",
                        InterruptingExecutor,
                    ),
                    self.assertRaises(KeyboardInterrupt),
                    doctor._bounded_parallel_map(
                        lambda value: value,
                        range(64),
                        max_workers=16,
                        thread_name_prefix="synthetic-interrupt",
                    ) as observations,
                ):
                    reporter.progress(
                        "doctor-cache-snapshot-revalidation",
                        "start",
                        0,
                        64,
                    )
                    tuple(observations)
            finally:
                reporter.close()
            elapsed = time.monotonic() - started

            self.assertLess(elapsed, 0.5)
            self.assertEqual(shutdown_calls, [(False, True)])
            self.assertIn("heartbeat", stderr.getvalue())

    def test_parallel_map_executor_failure_cancels_and_propagates(self) -> None:
        shutdown_calls: list[tuple[bool, bool]] = []

        class FailingExecutor:
            def __init__(self, **_kwargs: object) -> None:
                pass

            def submit(
                self,
                _function: object,
                _value: object,
            ) -> object:
                class FailingFuture:
                    def result(self) -> object:
                        raise RuntimeError("synthetic_executor_failure")

                return FailingFuture()

            def shutdown(
                self,
                *,
                wait: bool,
                cancel_futures: bool,
            ) -> None:
                shutdown_calls.append((wait, cancel_futures))

        with (
            mock.patch.object(
                archive_cli,
                "_DoctorBoundedDaemonExecutor",
                FailingExecutor,
            ),
            self.assertRaisesRegex(
                RuntimeError,
                "synthetic_executor_failure",
            ),
            archive_cli.Doctor._bounded_parallel_map(
                lambda value: value,
                range(64),
                max_workers=16,
                thread_name_prefix="synthetic-failure",
            ) as observations,
        ):
            tuple(observations)

        self.assertEqual(shutdown_calls, [(False, True)])

    def test_parallel_map_keeps_submission_window_bounded(self) -> None:
        instances: list[object] = []

        class CountingExecutor:
            def __init__(self, **_kwargs: object) -> None:
                self.outstanding = 0
                self.peak = 0
                self.submitted = 0
                self.shutdown_calls: list[tuple[bool, bool]] = []
                instances.append(self)

            def submit(
                self,
                function: object,
                value: object,
            ) -> object:
                self.outstanding += 1
                self.submitted += 1
                self.peak = max(self.peak, self.outstanding)
                owner = self

                class CountingFuture:
                    def result(self) -> object:
                        try:
                            return function(value)
                        finally:
                            owner.outstanding -= 1

                return CountingFuture()

            def shutdown(
                self,
                *,
                wait: bool,
                cancel_futures: bool,
            ) -> None:
                self.shutdown_calls.append((wait, cancel_futures))

        with (
            mock.patch.object(
                archive_cli,
                "_DoctorBoundedDaemonExecutor",
                CountingExecutor,
            ),
            archive_cli.Doctor._bounded_parallel_map(
                lambda value: value * 2,
                range(10_000),
                max_workers=16,
                thread_name_prefix="synthetic-bounded",
            ) as observations,
        ):
            results = tuple(observations)

        self.assertEqual(results[0], 0)
        self.assertEqual(results[-1], 19_998)
        executor = instances[0]
        self.assertEqual(executor.submitted, 10_000)
        self.assertLessEqual(executor.peak, 32)
        self.assertEqual(executor.shutdown_calls, [(True, False)])

    def test_shutdown_cancels_dequeued_not_started_observation(self) -> None:
        """Cancellation linearizes before a dequeued worker calls user code."""

        real_queue_type = queue.Queue

        class ControlledQueue:
            def __init__(self) -> None:
                self._queue = real_queue_type()
                self._get_count = 0
                self.second_dequeued = threading.Event()
                self.allow_second_get_to_return = threading.Event()

            def put(self, value: object) -> None:
                self._queue.put(value)

            def get(self) -> object:
                value = self._queue.get()
                self._get_count += 1
                if self._get_count == 2:
                    self.second_dequeued.set()
                    self.allow_second_get_to_return.wait(timeout=5.0)
                return value

            def get_nowait(self) -> object:
                return self._queue.get_nowait()

        first_release = threading.Event()
        second_called = threading.Event()

        def observe(value: int) -> int:
            if value == 0:
                first_release.wait(timeout=5.0)
            else:
                second_called.set()
            return value

        with mock.patch.object(
            archive_cli.queue,
            "SimpleQueue",
            ControlledQueue,
        ):
            executor = archive_cli._DoctorBoundedDaemonExecutor(
                max_workers=1,
                thread_name_prefix="synthetic-start-gate",
            )
            first = executor.submit(observe, 0)
            second = executor.submit(observe, 1)
            first_release.set()
            self.assertTrue(executor._tasks.second_dequeued.wait(timeout=5.0))

            executor.shutdown(wait=False, cancel_futures=True)
            executor._tasks.allow_second_get_to_return.set()

            self.assertEqual(first.result(timeout=5.0), 0)
            with self.assertRaises(CancelledError):
                second.result(timeout=5.0)
            self.assertTrue(second.cancelled())
            self.assertFalse(second_called.wait(timeout=0.1))

    def test_interrupt_with_blocked_worker_does_not_hold_process_exit(self) -> None:
        source_root = Path(archive_cli.__file__).resolve().parents[1]
        environment = os.environ.copy()
        previous_pythonpath = environment.get("PYTHONPATH", "")
        environment["PYTHONPATH"] = os.pathsep.join(
            value
            for value in (str(source_root), previous_pythonpath)
            if value
        )
        script = "\n".join(
            [
                "import time",
                "import sys",
                "from wom_kit.archive_cli import Doctor",
                "print('doctor-ready', flush=True)",
                "sys.stdin.readline()",
                "def blocked(value):",
                "    if value == 0:",
                "        time.sleep(0.1)",
                "        raise KeyboardInterrupt()",
                "    time.sleep(30)",
                "try:",
                "    with Doctor._bounded_parallel_map(",
                "        blocked, range(32), max_workers=16,",
                "        thread_name_prefix='blocked-doctor-test',",
                "    ) as observations:",
                "        tuple(observations)",
                "except KeyboardInterrupt:",
                "    print('interrupt-returned', flush=True)",
            ]
        )
        # Import readiness and interrupted-worker exit are separate contracts.
        # A slow cold import must not spend the worker's unchanged exit budget.
        completed = subprocess.Popen(
            [sys.executable, "-c", script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=environment,
        )
        assert completed.stdout is not None
        ready: queue.Queue[str] = queue.Queue()
        reader = threading.Thread(
            target=lambda: ready.put(completed.stdout.readline()), daemon=True
        )
        reader.start()
        try:
            self.assertEqual(ready.get(timeout=30), "doctor-ready\n")
            reader.join(timeout=1)
            started = time.monotonic()
            stdout, stderr = completed.communicate(input="continue\n", timeout=5)
            elapsed = time.monotonic() - started
        finally:
            if completed.poll() is None:
                completed.kill()
                completed.communicate(timeout=5)
            reader.join(timeout=1)

        self.assertEqual(completed.returncode, 0, stderr)
        self.assertIn("interrupt-returned", stdout)
        self.assertLess(elapsed, 3.0)

    def test_managed_run_reuses_prefetched_secret_observation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            path = root / "receipts" / "prefetched.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {"value": "token=" + "A" * 24},
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            doctor = archive_cli.Doctor(root)

            stages = [
                ("symlink-boundaries", doctor._check_symlink_boundaries),
                ("prefetch-json", lambda: doctor._load_json_file(path)),
                (
                    "local-profile-secret-safety",
                    doctor._check_local_profile_and_secret_safety,
                ),
            ]
            with (
                mock.patch.object(doctor, "_full_stages", return_value=stages),
                mock.patch.object(
                    doctor,
                    "_file_contains_secret_value",
                    side_effect=AssertionError(
                        "managed_run_rescanned_prefetched_secret_input"
                    ),
                ) as scan_again,
            ):
                diagnostics = doctor.run()

            scan_again.assert_not_called()
            codes = {item.code for item in diagnostics}
            self.assertIn("secret_value_detected", codes)
            self.assertIn("doctor_cache_snapshot_current", codes)

    def test_completion_revalidation_detects_cached_file_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            path = root / "nested" / "cached.json"
            path.parent.mkdir(parents=True)
            path.write_text('{"value":"first"}\n', encoding="utf-8")
            doctor = archive_cli.Doctor(root)
            doctor._run_stage(
                "symlink-boundaries",
                doctor._check_symlink_boundaries,
            )
            doctor._run_stage(
                "prefetch-json",
                lambda: doctor._load_json_file(path),
            )
            self.assertTrue(doctor._run_file_generation_snapshots)

            path.write_text(
                '{"value":"changed-generation"}\n',
                encoding="utf-8",
            )
            doctor._finalize_run_file_generation_snapshots()

            stale = next(
                item
                for item in doctor.diagnostics
                if item.code == "doctor_cache_snapshot_stale"
            )
            self.assertEqual(stale.details["changed_file_count"], 1)

    def test_completion_revalidation_detects_cached_parent_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            parent = root / "nested"
            path = parent / "cached.json"
            parent.mkdir(parents=True)
            path.write_text('{"value":"stable"}\n', encoding="utf-8")
            doctor = archive_cli.Doctor(root)
            doctor._run_stage(
                "symlink-boundaries",
                doctor._check_symlink_boundaries,
            )
            doctor._run_stage(
                "prefetch-json",
                lambda: doctor._load_json_file(path),
            )
            expected_file = doctor._stat_identity(os.lstat(path))

            parent_stat = os.lstat(parent)
            os.utime(
                parent,
                ns=(
                    int(parent_stat.st_atime_ns),
                    int(parent_stat.st_mtime_ns) + 1_000_000_000,
                ),
            )
            self.assertEqual(doctor._stat_identity(os.lstat(path)), expected_file)
            doctor._finalize_run_file_generation_snapshots()

            stale = next(
                item
                for item in doctor.diagnostics
                if item.code == "doctor_cache_snapshot_stale"
            )
            self.assertEqual(stale.details["changed_file_count"], 0)
            self.assertGreaterEqual(
                stale.details["changed_directory_count"],
                1,
            )

    def test_parallel_zettel_prefetch_reports_each_invalid_utf8_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            zettels = root / "zettels"
            zettels.mkdir(parents=True)
            for index in range(16):
                (zettels / f"zet_{index:02d}.md").write_bytes(b"\xff")
            doctor = archive_cli.Doctor(root)

            doctor._check_zettels()

            invalid_utf8 = [
                item
                for item in doctor.diagnostics
                if item.code == "doctor_zet_utf8_invalid"
            ]
            self.assertEqual(len(invalid_utf8), 16)

    def test_retired_receipt_prefetch_never_runs_validation_in_workers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            receipt_root = (
                root / archive_services.MINT_RETIRED_DRAFT_RECEIPTS_DIR
            )
            receipt_root.mkdir(parents=True)
            expected = []
            for index in range(16):
                name = f"r{index:02d}.retire-draft.json"
                expected.append(name)
                (receipt_root / name).write_text("{}\n", encoding="utf-8")
            doctor = archive_cli.Doctor(root)
            main_thread = threading.get_ident()
            prefetch_threads: set[int] = set()
            prefetch_lock = threading.Lock()
            validation: list[tuple[str, int]] = []

            def observe(
                _path: Path,
                *,
                encoding: str,
            ) -> None:
                self.assertEqual(encoding, "utf-8-sig")
                with prefetch_lock:
                    prefetch_threads.add(threading.get_ident())
                return None

            def validate(path: Path) -> None:
                validation.append((path.name, threading.get_ident()))

            with (
                mock.patch.object(
                    doctor,
                    "_observe_stable_text_for_prefetch",
                    side_effect=observe,
                ),
                mock.patch.object(
                    doctor,
                    "_check_one_retired_draft_receipt",
                    side_effect=validate,
                ),
            ):
                doctor._check_retired_draft_receipts()

            self.assertTrue(prefetch_threads)
            self.assertNotIn(main_thread, prefetch_threads)
            self.assertEqual(
                validation,
                [(name, main_thread) for name in expected],
            )

    def test_zettel_and_mint_prefetch_never_validate_in_workers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            zettel_root = root / "zettels"
            mint_root = root / "receipts" / "mint"
            zettel_root.mkdir(parents=True)
            mint_root.mkdir(parents=True)
            expected_zettels = []
            for index in range(16):
                zettel = zettel_root / f"zet-{index:03d}.md"
                receipt = mint_root / f"zet-{index:03d}.mint.json"
                zettel.write_text("body\n", encoding="utf-8")
                receipt.write_text("{}\n", encoding="utf-8")
                expected_zettels.append(zettel.name)
            doctor = archive_cli.Doctor(root)
            main_thread = threading.get_ident()
            prefetch_threads: set[int] = set()
            prefetch_lock = threading.Lock()
            validation: list[tuple[str, int]] = []

            def observe(
                _path: Path,
                *,
                encoding: str,
            ) -> None:
                self.assertIn(encoding, {"utf-8", "utf-8-sig"})
                with prefetch_lock:
                    prefetch_threads.add(threading.get_ident())
                return None

            def validate(path: Path, _status: str) -> None:
                validation.append((path.name, threading.get_ident()))

            with (
                mock.patch.object(
                    doctor,
                    "_observe_stable_text_for_prefetch",
                    side_effect=observe,
                ),
                mock.patch.object(
                    doctor,
                    "_check_zettel_file",
                    side_effect=validate,
                ),
            ):
                doctor._check_zettels()

            self.assertTrue(prefetch_threads)
            self.assertNotIn(main_thread, prefetch_threads)
            self.assertEqual(
                validation,
                [(name, main_thread) for name in expected_zettels],
            )

    def test_direct_transition_index_is_not_observed_half_initialized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            target = root / "zettels" / "zet_test.md"
            target.parent.mkdir(parents=True)
            target.write_text("body\n", encoding="utf-8")
            doctor = archive_cli.Doctor(root)
            expected_sha = "a" * 64
            actual_sha = "b" * 64
            receipt = {
                "action": "mint_zettel",
                "archive_id": "archive:test",
                "timestamp": "2026-08-27T00:00:00Z",
                "zettel": {"id": "zet_test"},
                "target": {
                    "path": "zettels/zet_test.md",
                    "sha256": expected_sha,
                },
            }
            build_started = threading.Event()
            release_build = threading.Event()

            class ProvenIndex:
                def assess(self, **_kwargs: object) -> dict[str, object]:
                    return {
                        "proven": True,
                        "state": (
                            target_sha_evolution
                            .EXACT_BYTE_TRANSITION_INTERNAL_EVIDENCE
                        ),
                        "evidence": {
                            "evidence_kind": "exact_transition_chain",
                            "transition_count": 1,
                            "transition_kinds": ["zettel_objet_link"],
                            "cryptographic_authentication": False,
                        },
                    }

            def build(_root: Path) -> ProvenIndex:
                build_started.set()
                self.assertTrue(release_build.wait(timeout=2.0))
                return ProvenIndex()

            def assess() -> dict[str, object] | None:
                return doctor._target_sha_evolved_by_direct_objet_receipts(
                    receipt,
                    root / "receipts" / "mint.json",
                    target,
                    expected_sha,
                    actual_sha,
                )

            with mock.patch.object(
                target_sha_evolution,
                "build_zettel_objet_target_sha_evolution_index",
                side_effect=build,
            ) as builder:
                with ThreadPoolExecutor(max_workers=2) as executor:
                    first = executor.submit(assess)
                    self.assertTrue(build_started.wait(timeout=1.0))
                    second = executor.submit(assess)
                    try:
                        with self.assertRaises(TimeoutError):
                            second.result(timeout=0.1)
                    finally:
                        release_build.set()
                    first_result = first.result(timeout=2.0)
                    second_result = second.result(timeout=2.0)

            self.assertIsNotNone(first_result)
            self.assertIsNotNone(second_result)
            self.assertEqual(builder.call_count, 1)

    def test_packaged_schema_is_parsed_once_per_process(self) -> None:
        schema_name = "archive.schema.json"
        schema_path = (schema_validator.SCHEMAS_ROOT / schema_name).resolve()
        original_read_text = Path.read_text
        reads = 0

        def observed_read_text(
            path: Path,
            *args: object,
            **kwargs: object,
        ) -> str:
            nonlocal reads
            if Path(path).resolve() == schema_path:
                reads += 1
            return original_read_text(path, *args, **kwargs)

        schema_validator.load_schema.cache_clear()
        try:
            with mock.patch.object(Path, "read_text", new=observed_read_text):
                schema_validator.validate_schema({}, schema_name)
                schema_validator.validate_schema({}, schema_name)
            self.assertEqual(reads, 1)
        finally:
            schema_validator.load_schema.cache_clear()

    def test_duplicate_suggested_commands_are_resolved_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            doctor = archive_cli.Doctor(Path(tmp))
            command = "archive doctor <archive-root> --strict --summary"
            doctor.warn("first", "first", suggested_command=command)
            doctor.warn("second", "second", suggested_command=command)
            status = {
                "requested_mode": "dry_run",
                "requested_mode_available": True,
            }

            with (
                mock.patch.object(archive_cli, "build_parser", return_value=object()),
                mock.patch.object(
                    archive_cli.command_status,
                    "build_command_status_inventory",
                    return_value={},
                ),
                mock.patch.object(
                    archive_cli.command_status,
                    "resolve_suggested_command_mode",
                    return_value=status,
                ) as resolve,
            ):
                doctor._attach_suggested_command_statuses()

            self.assertEqual(resolve.call_count, 1)
            self.assertEqual(doctor.diagnostics[0].suggested_command_status, status)
            self.assertEqual(doctor.diagnostics[1].suggested_command_status, status)

    def test_zettel_text_is_read_once_across_text_and_frontmatter_consumers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            path = root / "zettels" / "zet_test.md"
            path.parent.mkdir(parents=True)
            path.write_text(
                "---\nid: zet_test\ntitle: Test\n---\n\nBody.\n",
                encoding="utf-8",
            )
            doctor = archive_cli.Doctor(root)
            stable_reader = archive_doctor._stable_regular_file_bytes

            with mock.patch.object(
                archive_doctor,
                "_stable_regular_file_bytes",
                wraps=stable_reader,
            ) as read_stable:
                text = doctor._load_zettel_text_cached(path)
                frontmatter = doctor._load_zettel_frontmatter_cached(path)

            self.assertIn("Body.", text)
            self.assertEqual(frontmatter, {"id": "zet_test", "title": "Test"})
            self.assertEqual(read_stable.call_count, 1)

    def test_changed_hash_input_is_not_cached_as_the_new_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            path = root / "zettels" / "zet_test.md"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"first-generation")
            doctor = archive_cli.Doctor(root)
            generation_a = (1, 1, 0o100644, 16, 1, 0, 0)
            generation_b = (1, 2, 0o100644, 17, 2, 0, 0)
            digest_b = hashlib.sha256(b"second-generation").hexdigest()

            with (
                mock.patch.object(
                    doctor,
                    "_file_cache_identity",
                    side_effect=[
                        generation_a,
                        generation_b,
                        generation_b,
                        generation_b,
                    ],
                ),
                mock.patch.object(
                    archive_cli,
                    "sha256_file",
                    return_value=digest_b,
                ) as hasher,
            ):
                first = doctor._sha256_file_cached(path)
                second = doctor._sha256_file_cached(path)

            self.assertEqual(first, "")
            self.assertEqual(second, digest_b)
            self.assertEqual(hasher.call_count, 2)
            self.assertEqual(doctor._file_sha256_cache_hits, 0)
            self.assertIn(
                "doctor_file_changed_while_hashing",
                {item.code for item in doctor.diagnostics},
            )

    def test_repeatedly_changed_zettel_text_is_discarded_not_cached(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            path = root / "zettels" / "zet_test.md"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"first")
            doctor = archive_cli.Doctor(root)
            generation_a = (1, 1, 0o100644, 5, 1, 0, 0)
            generation_b = (1, 2, 0o100644, 6, 2, 0, 0)

            with (
                mock.patch.object(
                    doctor,
                    "_file_cache_identity",
                    side_effect=[generation_a, generation_b],
                ),
                mock.patch.object(
                    archive_doctor,
                    "_stable_regular_file_bytes",
                    return_value=(b"second", None),
                ) as reader,
            ):
                text = doctor._load_zettel_text_cached(path)

            self.assertEqual(text, "")
            self.assertEqual(reader.call_count, 1)
            self.assertEqual(doctor._zettel_text_cache, {})
            self.assertIn(
                "doctor_zet_changed_while_reading",
                {item.code for item in doctor.diagnostics},
            )

    def test_frontmatter_parsed_from_old_text_is_not_cached_as_new_generation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            path = root / "zettels" / "zet_test.md"
            path.parent.mkdir(parents=True)
            old_text = "---\nid: zet_old\ntitle: Old\n---\n\nOld body.\n"
            new_text = "---\nid: zet_new\ntitle: New\n---\n\nNew body.\n"
            path.write_text(old_text, encoding="utf-8")
            doctor = archive_cli.Doctor(root)

            def mutate_after_old_parse(
                _frontmatter: str,
                _path: Path,
            ) -> dict[str, str]:
                path.write_text(new_text, encoding="utf-8")
                return {"id": "zet_old", "title": "Old"}

            with mock.patch.object(
                doctor,
                "_load_yaml_text",
                side_effect=mutate_after_old_parse,
            ):
                stale = doctor._load_zettel_frontmatter_cached(path)

            self.assertIsNone(stale)
            self.assertEqual(doctor._zettel_frontmatter_cache, {})
            self.assertIn(
                "doctor_zet_changed_while_parsing",
                {item.code for item in doctor.diagnostics},
            )
            current = doctor._load_zettel_frontmatter_cached(path)
            self.assertEqual(current, {"id": "zet_new", "title": "New"})

    def test_secret_scan_reads_current_text_instead_of_cached_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            path = root / "zettels" / "zet_test.md"
            path.parent.mkdir(parents=True)
            path.write_text(
                "---\nid: zet_test\ntitle: Test\n---\n\nOrdinary body.\n",
                encoding="utf-8",
            )
            doctor = archive_cli.Doctor(root)
            doctor._load_zettel_text_cached(path)
            path.write_text(
                "token=ghp_" + "A" * 24,
                encoding="utf-8",
            )

            contains_secret = doctor._file_contains_secret_value(
                path,
                stage="local-profile-secret-safety",
                progress_label="zettels/zet_test.md",
            )

            self.assertTrue(contains_secret)

    def test_secret_scan_discards_result_when_boundary_changes_before_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            path = root / "zettels" / "zet_test.md"
            path.parent.mkdir(parents=True)
            path.write_text("ordinary text", encoding="utf-8")
            doctor = archive_cli.Doctor(root)

            with mock.patch.object(
                doctor,
                "_archive_cache_boundary_current",
                side_effect=[True, False],
            ):
                contains_secret = doctor._file_contains_secret_value(
                    path,
                    stage="local-profile-secret-safety",
                    progress_label="zettels/zet_test.md",
                )

            self.assertFalse(contains_secret)
            self.assertEqual(doctor._secret_value_observation_cache, {})
            self.assertIn(
                "doctor_secret_scan_input_changed",
                {item.code for item in doctor.diagnostics},
            )

    def test_edge_evolution_reads_current_target_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            path = root / "zettels" / "zet_test.md"
            path.parent.mkdir(parents=True)
            current_text = (
                "---\n"
                "id: zet_test\n"
                "status: canonical\n"
                "edges: []\n"
                "---\n\nBody.\n"
            )
            path.write_bytes(current_text.replace("\n", "\r\n").encode("utf-8"))

            with mock.patch.object(
                archive_services,
                "require_readable_zettel_text",
                wraps=archive_services.require_readable_zettel_text,
            ) as parse:
                result = archive_services.target_sha_evolved_by_edge_receipts(
                    root,
                    {"timestamp": "2026-08-27T00:00:00Z"},
                    path,
                    "a" * 64,
                    edge_receipts=[],
                )

            self.assertFalse(result)
            self.assertEqual(parse.call_args.args[0], current_text)


class DoctorSqliteIndexBoundaryTests(unittest.TestCase):
    @staticmethod
    def _write_index_inputs(root: Path) -> tuple[Path, Path]:
        zettel = root / "zettels" / "zet_test.md"
        zettel.parent.mkdir(parents=True)
        zettel.write_text(
            "---\nid: zet_test\ntitle: Test\n---\n\nBody.\n",
            encoding="utf-8",
        )
        db_path = root / archive_services.INDEX_RELATIVE_PATH
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.write_bytes(b"synthetic-index-placeholder")
        return zettel, db_path

    def test_false_pre_query_boundary_blocks_sqlite_connection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            zettel, _db_path = self._write_index_inputs(root)
            doctor = archive_cli.Doctor(
                root,
                use_zettel_index_cache=True,
            )
            canonical_db_path = (
                doctor.archive_root / archive_services.INDEX_RELATIVE_PATH
            )

            with (
                mock.patch.object(
                    doctor,
                    "_archive_cache_boundary_current",
                    return_value=False,
                ) as boundary_current,
                mock.patch.object(
                    archive_services,
                    "connect_archive_index",
                ) as connect,
            ):
                cached = doctor._indexed_zettel_cache_for_path(zettel)

            self.assertIsNone(cached)
            boundary_current.assert_called_once_with(canonical_db_path)
            connect.assert_not_called()

    def test_false_post_query_boundary_discards_sqlite_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            zettel, _db_path = self._write_index_inputs(root)
            doctor = archive_cli.Doctor(
                root,
                use_zettel_index_cache=True,
            )
            canonical_db_path = (
                doctor.archive_root / archive_services.INDEX_RELATIVE_PATH
            )
            zettel_identity = doctor._file_cache_identity(zettel)
            connection = mock.MagicMock()
            connection.execute.return_value.fetchone.return_value = {
                "frontmatter_json": json.dumps(
                    {"id": "zet_test", "title": "Test"},
                    sort_keys=True,
                ),
                "file_size": zettel_identity[3],
                "file_mtime_ns": zettel_identity[4],
                "body_sha256": "a" * 64,
                "approved_body_sha256": "b" * 64,
                "forbidden_location_reference_found": 0,
            }

            with (
                mock.patch.object(
                    doctor,
                    "_archive_cache_boundary_current",
                    side_effect=[True, False],
                ) as boundary_current,
                mock.patch.object(
                    archive_services,
                    "connect_archive_index",
                    return_value=connection,
                ) as connect,
            ):
                cached = doctor._indexed_zettel_cache_for_path(zettel)

            self.assertIsNone(cached)
            self.assertEqual(boundary_current.call_count, 2)
            connect.assert_called_once_with(
                canonical_db_path,
                row_factory=True,
            )
            connection.execute.assert_called_once()
            connection.close.assert_called_once_with()
            self.assertEqual(doctor._zettel_index_cache, {})
            self.assertIsNone(doctor._zettel_index_cache_db_identity)


class DoctorStableFileHashTests(unittest.TestCase):
    def test_stable_bytes_discards_result_when_root_changes_at_final_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            path = root / "objects" / "one.bin"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"stable-until-final-boundary")
            boundary = archive_doctor.capture_doctor_archive_root_boundary(
                root
            )
            self.assertIsNotNone(boundary)

            with mock.patch.object(
                archive_doctor,
                "doctor_archive_root_boundary_is_current",
                side_effect=[True, False],
            ) as root_current:
                raw, reason = archive_doctor._stable_regular_file_bytes(
                    path,
                    maximum_bytes=1024,
                    required_root=boundary,
                )

            self.assertIsNone(raw)
            self.assertEqual(reason, "changed")
            self.assertEqual(root_current.call_count, 2)

    def test_stable_hash_discards_result_when_root_changes_at_final_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            path = root / "objects" / "one.bin"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"stable-until-final-boundary")
            boundary = archive_doctor.capture_doctor_archive_root_boundary(
                root
            )
            self.assertIsNotNone(boundary)

            with mock.patch.object(
                archive_doctor,
                "doctor_archive_root_boundary_is_current",
                side_effect=[True, False],
            ) as root_current:
                result = archive_doctor.observe_stable_regular_file_sha256(
                    path,
                    required_root=boundary,
                )

            self.assertEqual(result.state, "changed")
            self.assertIsNone(result.sha256)
            self.assertEqual(root_current.call_count, 2)

    def test_descriptor_bound_hash_rejects_handle_outside_required_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            archive_root = base / "archive"
            archive_root.mkdir()
            outside = base / "outside.bin"
            outside.write_bytes(b"outside")
            boundary = archive_doctor.capture_doctor_archive_root_boundary(
                archive_root
            )
            self.assertIsNotNone(boundary)

            result = archive_doctor.observe_stable_regular_file_sha256(
                outside,
                required_root=boundary,
            )

            self.assertEqual(result.state, "unsafe")
            self.assertIsNone(result.sha256)

    @unittest.skipUnless(os.name == "nt", "Windows junction regression")
    def test_inventory_and_handle_reject_parent_junction_hardlink_swap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            archive_root = base / "archive"
            logical_parent = archive_root / "objects"
            logical_parent.mkdir(parents=True)
            logical = logical_parent / "same.bin"
            logical.write_bytes(b"same-inode-bytes")
            outside = base / "outside"
            outside.mkdir()
            external = outside / "same.bin"
            os.link(logical, external)
            doctor = archive_cli.Doctor(archive_root)
            doctor._check_symlink_boundaries()

            logical.unlink()
            logical_parent.rmdir()
            created = subprocess.run(
                [
                    "cmd",
                    "/c",
                    "mklink",
                    "/J",
                    str(logical_parent),
                    str(outside),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if created.returncode != 0:
                self.skipTest("Windows directory junction creation unavailable")
            try:
                with self.assertRaises(ArchivePathError):
                    doctor._resolve_archive_relative_path(
                        "objects/same.bin"
                    )
                result = archive_doctor.observe_stable_regular_file_sha256(
                    logical_parent / "same.bin",
                    required_root=doctor._archive_root_boundary,
                )
                self.assertEqual(result.state, "unsafe")
                self.assertIsNone(result.sha256)
            finally:
                logical_parent.rmdir()

    @unittest.skipUnless(os.name == "nt", "Windows root junction regression")
    def test_queued_hash_rejects_archive_root_replaced_by_junction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            archive_root = base / "archive"
            original_file = archive_root / "objects" / "queued.bin"
            original_file.parent.mkdir(parents=True)
            original_file.write_bytes(b"original-root-bytes")
            outside = base / "outside"
            outside_file = outside / "objects" / "queued.bin"
            outside_file.parent.mkdir(parents=True)
            os.link(original_file, outside_file)

            doctor = archive_cli.Doctor(archive_root)
            doctor._check_symlink_boundaries()
            queued = doctor._resolve_archive_relative_path(
                "objects/queued.bin"
            )
            cached_digest = doctor._sha256_file_cached(queued)
            self.assertEqual(
                cached_digest,
                hashlib.sha256(b"original-root-bytes").hexdigest(),
            )
            saved_root = base / "saved-archive-root"
            archive_root.rename(saved_root)
            created = subprocess.run(
                [
                    "cmd",
                    "/c",
                    "mklink",
                    "/J",
                    str(archive_root),
                    str(outside),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if created.returncode != 0:
                saved_root.rename(archive_root)
                self.skipTest("Windows directory junction creation unavailable")
            try:
                with self.assertRaises(ArchivePathError):
                    doctor._resolve_archive_relative_path(
                        "objects/queued.bin"
                    )
                result = archive_doctor.observe_stable_regular_file_sha256(
                    queued,
                    expected_size=len(b"original-root-bytes"),
                    required_root=doctor._archive_root_boundary,
                )
                self.assertEqual(result.state, "unsafe")
                self.assertIsNone(result.sha256)
                self.assertFalse(result.as_dict()["descriptor_bound"])
                self.assertEqual(doctor._sha256_file_cached(queued), "")
                self.assertTrue(
                    any(
                        item.code == "doctor_file_input_unverified"
                        for item in doctor.diagnostics
                    )
                )
            finally:
                archive_root.rmdir()
                saved_root.rename(archive_root)

    @unittest.skipUnless(os.name == "nt", "Windows root alias regression")
    def test_real_83_root_alias_cache_is_unverified_after_root_swap(self) -> None:
        from ctypes import wintypes

        with tempfile.TemporaryDirectory(
            prefix="doctor-long-root-parent-name-"
        ) as tmp:
            base = Path(tmp)
            archive_root = base / "archive-root-with-long-name"
            original_file = archive_root / "objects" / "queued.bin"
            original_file.parent.mkdir(parents=True)
            original_file.write_bytes(b"original-root-bytes")

            get_short_path = ctypes.WinDLL(
                "kernel32",
                use_last_error=True,
            ).GetShortPathNameW
            get_short_path.argtypes = (
                wintypes.LPCWSTR,
                wintypes.LPWSTR,
                wintypes.DWORD,
            )
            get_short_path.restype = wintypes.DWORD
            required = int(get_short_path(str(archive_root), None, 0))
            if required <= 0:
                self.skipTest("Windows 8.3 path aliases are unavailable")
            buffer = ctypes.create_unicode_buffer(required + 1)
            written = int(
                get_short_path(str(archive_root), buffer, len(buffer))
            )
            if written <= 0 or written >= len(buffer):
                self.skipTest("Windows 8.3 path alias could not be read")
            short_root = Path(buffer.value)
            if os.path.normcase(str(short_root)) == os.path.normcase(
                str(archive_root)
            ):
                self.skipTest("The test volume did not assign an 8.3 alias")

            doctor = archive_cli.Doctor(short_root)
            self.assertNotEqual(
                os.path.normcase(str(doctor._archive_root_input_absolute)),
                os.path.normcase(str(doctor.archive_root)),
            )
            doctor._run_stage(
                "symlink-boundaries",
                doctor._check_symlink_boundaries,
            )
            short_file = (
                doctor._archive_root_input_absolute / "objects" / "queued.bin"
            )
            expected_digest = hashlib.sha256(
                b"original-root-bytes"
            ).hexdigest()
            self.assertEqual(
                doctor._sha256_file_cached(short_file),
                expected_digest,
            )

            outside = base / "outside-root"
            outside_file = outside / "objects" / "queued.bin"
            outside_file.parent.mkdir(parents=True)
            os.link(original_file, outside_file)
            saved_root = base / "saved-original-root"
            doctor.archive_root.rename(saved_root)
            created = subprocess.run(
                [
                    "cmd",
                    "/c",
                    "mklink",
                    "/J",
                    str(doctor.archive_root),
                    str(outside.resolve()),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if created.returncode != 0:
                saved_root.rename(doctor.archive_root)
                self.skipTest("Windows directory junction creation unavailable")
            try:
                # The alias spelling still selects only the already-proven
                # in-memory generation; completion rejects the replaced root.
                self.assertEqual(
                    doctor._sha256_file_cached(short_file),
                    expected_digest,
                )
                doctor._finalize_run_file_generation_snapshots()
                self.assertIn(
                    "doctor_cache_snapshot_unverified",
                    {item.code for item in doctor.diagnostics},
                )
                self.assertNotIn(
                    "doctor_cache_snapshot_current",
                    {item.code for item in doctor.diagnostics},
                )
            finally:
                doctor.archive_root.rmdir()
                saved_root.rename(doctor.archive_root)

    @unittest.skipUnless(os.name == "nt", "Windows root alias regression")
    def test_third_root_spelling_cache_hit_is_unverified_after_root_swap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            archive_root = base / "archive"
            original_file = archive_root / "objects" / "queued.bin"
            original_file.parent.mkdir(parents=True)
            original_file.write_bytes(b"original-root-bytes")
            outside = base / "outside"
            outside_file = outside / "objects" / "queued.bin"
            outside_file.parent.mkdir(parents=True)
            os.link(original_file, outside_file)
            doctor = archive_cli.Doctor(archive_root)
            doctor._run_stage(
                "symlink-boundaries",
                doctor._check_symlink_boundaries,
            )
            input_spelling = (
                doctor._archive_root_input_absolute
                / "objects"
                / "queued.bin"
            )
            canonical_spelling = (
                doctor.archive_root / "objects" / "queued.bin"
            )
            third_spelling = Path(
                str(doctor.archive_root).upper()
            ) / "OBJECTS" / "QUEUED.BIN"
            expected_digest = hashlib.sha256(
                b"original-root-bytes"
            ).hexdigest()
            real_sha256_file = archive_cli.sha256_file
            with mock.patch.object(
                archive_cli,
                "sha256_file",
                wraps=real_sha256_file,
            ) as hash_file:
                self.assertEqual(
                    doctor._sha256_file_cached(input_spelling),
                    expected_digest,
                )
                self.assertEqual(
                    doctor._sha256_file_cached(canonical_spelling),
                    expected_digest,
                )
                self.assertEqual(
                    doctor._sha256_file_cached(third_spelling),
                    expected_digest,
                )
                self.assertEqual(hash_file.call_count, 1)

                saved_root = doctor.archive_root.with_name(
                    "saved-archive-root"
                )
                doctor.archive_root.rename(saved_root)
                created = subprocess.run(
                    [
                        "cmd",
                        "/c",
                        "mklink",
                        "/J",
                        str(doctor.archive_root),
                        str(outside.resolve()),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if created.returncode != 0:
                    saved_root.rename(doctor.archive_root)
                    self.skipTest(
                        "Windows directory junction creation unavailable"
                    )
                try:
                    # Returning already-proven cached bytes does not read the
                    # replacement.  Completion still rejects the whole result.
                    self.assertEqual(
                        doctor._sha256_file_cached(third_spelling),
                        expected_digest,
                    )
                    self.assertEqual(hash_file.call_count, 1)
                    doctor._finalize_run_file_generation_snapshots()
                    self.assertIn(
                        "doctor_cache_snapshot_unverified",
                        {item.code for item in doctor.diagnostics},
                    )
                finally:
                    doctor.archive_root.rmdir()
                    saved_root.rename(doctor.archive_root)

    @unittest.skipUnless(os.name == "nt", "Windows replacement regression")
    def test_inventory_rejects_same_path_directory_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            archive_root = base / "archive"
            objects = archive_root / "objects"
            logical = objects / "same.bin"
            objects.mkdir(parents=True)
            logical.write_bytes(b"same-file-identity")
            doctor = archive_cli.Doctor(archive_root)
            doctor._check_symlink_boundaries()

            saved_objects = archive_root / "objects-original"
            objects.rename(saved_objects)
            objects.mkdir()
            os.link(saved_objects / "same.bin", logical)

            with self.assertRaises(ArchivePathError):
                doctor._resolve_archive_relative_path("objects/same.bin")
            self.assertFalse(doctor._archive_cache_boundary_current(logical))

    @unittest.skipUnless(os.name == "nt", "Windows internal junction regression")
    def test_cache_rejects_internal_ancestor_junction_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            archive_root = base / "archive"
            slot = archive_root / "branch-a" / "parent" / "slot"
            logical = slot / "same.bin"
            logical.parent.mkdir(parents=True)
            logical.write_bytes(b"branch-a")
            target = archive_root / "branch-b" / "target"
            target.mkdir(parents=True)
            (target / "same.bin").write_bytes(b"branch-b")
            doctor = archive_cli.Doctor(archive_root)
            doctor._check_symlink_boundaries()

            saved_slot = slot.with_name("slot-original")
            slot.rename(saved_slot)
            created = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(slot), str(target)],
                capture_output=True,
                text=True,
                check=False,
            )
            if created.returncode != 0:
                saved_slot.rename(slot)
                self.skipTest("Windows directory junction creation unavailable")
            try:
                self.assertFalse(
                    doctor._archive_cache_boundary_current(logical)
                )
                with self.assertRaises(ArchivePathError):
                    doctor._resolve_archive_relative_path(
                        "branch-a/parent/slot/same.bin"
                    )
            finally:
                slot.rmdir()
                saved_slot.rename(slot)

    def test_descriptor_bound_hash_returns_current_digest_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "objet.bin"
            body = b"one-stable-objet-read"
            path.write_bytes(body)

            result = archive_doctor.observe_stable_regular_file_sha256(
                path,
                expected_size=len(body),
            )

            self.assertEqual(result.state, "verified")
            self.assertEqual(result.size_bytes, len(body))
            self.assertEqual(result.sha256, hashlib.sha256(body).hexdigest())
            self.assertTrue(result.as_dict()["descriptor_bound"])

    def test_descriptor_bound_hash_rejects_identity_change_during_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "objet.bin"
            body = b"changing-objet-read"
            path.write_bytes(body)

            with mock.patch.object(
                archive_doctor,
                "_identity_changed",
                side_effect=[False, True],
            ):
                result = archive_doctor.observe_stable_regular_file_sha256(
                    path,
                    expected_size=len(body),
                )

            self.assertEqual(result.state, "changed")
            self.assertIsNone(result.sha256)
            self.assertFalse(result.as_dict()["descriptor_bound"])

    def test_identity_change_detects_file_type_and_reparse_transitions(self) -> None:
        regular = mock.Mock(
            st_dev=1,
            st_ino=2,
            st_mode=stat.S_IFREG | 0o600,
            st_size=10,
            st_mtime_ns=20,
            st_file_attributes=0,
        )
        symlink = mock.Mock(
            st_dev=1,
            st_ino=2,
            st_mode=stat.S_IFLNK | 0o600,
            st_size=10,
            st_mtime_ns=20,
            st_file_attributes=0,
        )
        reparse = mock.Mock(
            st_dev=1,
            st_ino=2,
            st_mode=stat.S_IFREG | 0o600,
            st_size=10,
            st_mtime_ns=20,
            st_file_attributes=int(
                getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            ),
        )

        self.assertTrue(archive_doctor._identity_changed(regular, symlink))
        self.assertTrue(archive_doctor._identity_changed(regular, reparse))


class DoctorRootCompletionBoundaryTests(unittest.TestCase):
    def test_run_reports_root_replaced_by_normal_directory_in_last_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "archive"
            root.mkdir()
            saved = base / "archive-original"
            doctor = archive_cli.Doctor(root)

            def replace_root() -> None:
                root.rename(saved)
                root.mkdir()

            with mock.patch.object(
                doctor,
                "_full_stages",
                return_value=[("replace-root", replace_root)],
            ):
                try:
                    diagnostics = doctor.run()
                finally:
                    root.rmdir()
                    saved.rename(root)

            self.assertIn(
                "archive_root_boundary_changed",
                {item.code for item in diagnostics},
            )


class DoctorObjectByteSummaryContractTests(unittest.TestCase):
    def test_partition_rejects_false_verification_counts(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "doctor_object_byte_verification_partition_invalid",
        ):
            archive_doctor.DoctorObjectByteVerification(
                mode="operational",
                local_reference_count=1,
                unique_local_file_count=1,
                rehashed_now=0,
                attested_unchanged=0,
                bytes_unverified=0,
            )

    def test_attested_unchanged_cannot_be_claimed_without_contract(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "doctor_object_byte_verification_attestation_unsupported",
        ):
            archive_doctor.DoctorObjectByteVerification(
                mode="operational",
                local_reference_count=1,
                unique_local_file_count=1,
                rehashed_now=0,
                attested_unchanged=1,
                bytes_unverified=0,
            )


if __name__ == "__main__":
    unittest.main()
