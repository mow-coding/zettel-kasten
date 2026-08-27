from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from wom_kit import archive_cli, archive_doctor, archive_services, schema_validator


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

    def test_deep_mode_hashes_each_unique_local_path_once_per_run(self) -> None:
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
            real_sha256_file = archive_cli.sha256_file

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
                    wraps=real_sha256_file,
                ) as sha256_file,
            ):
                diagnostics = doctor.run()

            self.assertEqual(sha256_file.call_count, 1)
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

    def test_cli_defaults_operational_and_deep_is_explicit(self) -> None:
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
                operational_code, operational_stdout, operational_stderr = (
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
                deep_code, deep_stdout, deep_stderr = self._run_cli(
                    [
                        "doctor",
                        str(root),
                        "--summary",
                        "--format",
                        "json",
                        "--object-byte-verification",
                        "deep",
                        "--no-progress",
                    ]
                )

            operational = json.loads(operational_stdout)
            deep = json.loads(deep_stdout)
            self.assertEqual(operational_code, 0)
            self.assertEqual(operational_stderr, "")
            self.assertEqual(
                operational["object_byte_verification"]["result_state"],
                "bytes_unverified",
            )
            self.assertEqual(deep_code, 1)
            self.assertEqual(deep_stderr, "")
            self.assertEqual(
                deep["object_byte_verification"]["result_state"],
                "rehashed_now",
            )
            self.assertFalse(deep["ok"])


class DoctorReadCacheTests(unittest.TestCase):
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
            original_read_text = Path.read_text
            reads = 0

            def observed_read_text(
                candidate: Path,
                *args: object,
                **kwargs: object,
            ) -> str:
                nonlocal reads
                if Path(candidate).resolve() == path.resolve():
                    reads += 1
                return original_read_text(candidate, *args, **kwargs)

            with mock.patch.object(Path, "read_text", new=observed_read_text):
                text = doctor._load_zettel_text_cached(path)
                frontmatter = doctor._load_zettel_frontmatter_cached(path)

            self.assertIn("Body.", text)
            self.assertEqual(frontmatter, {"id": "zet_test", "title": "Test"})
            self.assertEqual(reads, 1)

    def test_secret_scan_reuses_zettel_text_without_second_file_open(self) -> None:
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

            with mock.patch.object(
                Path,
                "open",
                side_effect=AssertionError("cached_zettel_was_reopened"),
            ):
                contains_secret = doctor._file_contains_secret_value(
                    path,
                    stage="local-profile-secret-safety",
                    progress_label="zettels/zet_test.md",
                )

            self.assertFalse(contains_secret)

    def test_edge_evolution_accepts_cached_target_text_without_reread(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            path = root / "zettels" / "zet_test.md"
            path.parent.mkdir(parents=True)
            path.write_text("disk text must not be reread", encoding="utf-8")
            cached_text = (
                "---\n"
                "id: zet_test\n"
                "status: canonical\n"
                "edges: []\n"
                "---\n\nBody.\n"
            )

            with mock.patch.object(
                Path,
                "read_text",
                side_effect=AssertionError("target_text_reread"),
            ):
                result = archive_services.target_sha_evolved_by_edge_receipts(
                    root,
                    {"timestamp": "2026-08-27T00:00:00Z"},
                    path,
                    "a" * 64,
                    edge_receipts=[],
                    target_text=cached_text,
                )

            self.assertFalse(result)


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
