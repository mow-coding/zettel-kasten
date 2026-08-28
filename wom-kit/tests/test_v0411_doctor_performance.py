from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import threading
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
