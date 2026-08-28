from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from wom_kit import archive_cli, archive_doctor, archive_services, command_status, mcp_server


OBSERVED_AT = "2026-08-26T13:08:49Z"
REVALIDATED_AT = "2026-08-26T13:44:00Z"


class DoctorObjectManifestSnapshotTests(unittest.TestCase):
    def test_prebound_revalidation_rejects_identical_replacement_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "archive"
            raw = b"same-manifest-bytes\n"
            self.make_archive(root, raw)
            boundary = archive_doctor.capture_doctor_archive_root_boundary(
                root
            )
            self.assertIsNotNone(boundary)
            _captured, observed = (
                archive_doctor.capture_doctor_object_manifest_snapshot(
                    root.resolve(),
                    observed_at=OBSERVED_AT,
                    root_boundary=boundary,
                )
            )

            saved = base / "archive-original"
            root.rename(saved)
            self.make_archive(root, raw)
            try:
                result = archive_doctor.revalidate_doctor_object_manifest_snapshot(
                    root.resolve(),
                    observed,
                    revalidated_at=REVALIDATED_AT,
                    root_boundary=boundary,
                )
            finally:
                replacement_manifest = (
                    root / "objects" / "manifests" / "files.jsonl"
                )
                replacement_manifest.unlink()
                replacement_manifest.parent.rmdir()
                replacement_manifest.parent.parent.rmdir()
                root.rmdir()
                saved.rename(root)

            self.assertEqual(result.state, "unverified")
            self.assertTrue(result.requires_nonzero_exit)

    def make_archive(self, root: Path, raw: bytes | None = b'{"object_id":"sha256:00"}\n') -> Path:
        manifest = root / "objects" / "manifests" / "files.jsonl"
        if raw is not None:
            manifest.parent.mkdir(parents=True)
            manifest.write_bytes(raw)
        else:
            root.mkdir(parents=True)
        return manifest

    def test_capture_returns_exact_bytes_and_content_free_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive-private-marker"
            raw = b"\xffexact-manifest-bytes\r\n"
            self.make_archive(root, raw)

            observed_raw, snapshot = (
                archive_doctor.capture_doctor_object_manifest_snapshot(
                    root,
                    observed_at=OBSERVED_AT,
                )
            )

            self.assertEqual(observed_raw, raw)
            self.assertEqual(snapshot.state, "present")
            self.assertEqual(
                snapshot.identity,
                "sha256:" + hashlib.sha256(raw).hexdigest(),
            )
            self.assertEqual(snapshot.size_bytes, len(raw))
            public = snapshot.as_dict()
            self.assertEqual(
                public["basis"],
                "sha256_exact_bytes_parsed_by_object_manifest_stage",
            )
            self.assertTrue(public["exact_bytes_returned_separately"])
            encoded = json.dumps(public, sort_keys=True)
            self.assertNotIn(str(root), encoded)
            self.assertNotIn("archive-private-marker", encoded)
            self.assertNotIn("exact-manifest-bytes", encoded)

    def test_unchanged_manifest_is_current_and_keeps_zero_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            self.make_archive(root, b"one\ntwo\n")
            _raw, observed = archive_doctor.capture_doctor_object_manifest_snapshot(
                root,
                observed_at=OBSERVED_AT,
            )

            result = archive_doctor.revalidate_doctor_object_manifest_snapshot(
                root,
                observed,
                revalidated_at=REVALIDATED_AT,
            )

            self.assertEqual(result.state, "current")
            self.assertTrue(result.result_current)
            self.assertFalse(result.requires_nonzero_exit)
            self.assertEqual(result.reason_codes, ())
            self.assertEqual(
                archive_doctor.doctor_exit_code_with_snapshot(0, result),
                0,
            )
            payload = result.as_dict()
            self.assertEqual(payload["observed_at"], OBSERVED_AT)
            self.assertEqual(payload["revalidated_at"], REVALIDATED_AT)
            self.assertEqual(
                payload["observed_identity"],
                payload["revalidated_identity"],
            )
            self.assertFalse(payload["full_archive_atomic_snapshot"])

    def test_default_timestamp_is_recorded_after_the_stable_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            self.make_archive(root, b"one\n")
            original_read = archive_doctor._stable_regular_file_bytes
            original_timestamp = archive_doctor._utc_timestamp
            stable_read_finished = False
            default_timestamp_calls: list[bool] = []

            def observed_read(*args: object, **kwargs: object) -> object:
                nonlocal stable_read_finished
                result = original_read(*args, **kwargs)
                stable_read_finished = True
                return result

            def observed_timestamp(value: str | None = None) -> str:
                if value is None:
                    default_timestamp_calls.append(stable_read_finished)
                return original_timestamp(value)

            with (
                mock.patch.object(
                    archive_doctor,
                    "_stable_regular_file_bytes",
                    side_effect=observed_read,
                ),
                mock.patch.object(
                    archive_doctor,
                    "_utc_timestamp",
                    side_effect=observed_timestamp,
                ),
            ):
                _raw, snapshot = (
                    archive_doctor.capture_doctor_object_manifest_snapshot(root)
                )

            self.assertEqual(snapshot.state, "present")
            self.assertTrue(default_timestamp_calls)
            self.assertTrue(default_timestamp_calls[0])

    def test_same_size_change_with_restored_mtime_is_stale_by_exact_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            manifest = self.make_archive(root, b"one\n")
            _raw, observed = archive_doctor.capture_doctor_object_manifest_snapshot(
                root,
                observed_at=OBSERVED_AT,
            )
            before = manifest.stat()
            manifest.write_bytes(b"two\n")
            # Exact-byte identity remains authoritative even when cheap file
            # metadata is restored to its observed timestamp.
            os.utime(
                manifest,
                ns=(before.st_atime_ns, before.st_mtime_ns),
            )

            result = archive_doctor.revalidate_doctor_object_manifest_snapshot(
                root,
                observed,
                revalidated_at=REVALIDATED_AT,
            )

            self.assertEqual(result.state, "stale")
            self.assertNotEqual(
                result.observed.identity,
                result.revalidated.identity,
            )

    def test_manifest_change_after_capture_marks_whole_result_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            manifest = self.make_archive(root, b"duplicate-row\nduplicate-row\n")
            parsed_raw, observed = archive_doctor.capture_doctor_object_manifest_snapshot(
                root,
                observed_at=OBSERVED_AT,
            )
            manifest.write_bytes(b"deduplicated-row\n")

            result = archive_doctor.revalidate_doctor_object_manifest_snapshot(
                root,
                observed,
                revalidated_at=REVALIDATED_AT,
            )

            self.assertEqual(parsed_raw, b"duplicate-row\nduplicate-row\n")
            self.assertEqual(result.state, "stale")
            self.assertFalse(result.result_current)
            self.assertTrue(result.requires_nonzero_exit)
            self.assertEqual(
                result.reason_codes,
                ("object_manifest_changed_during_doctor",),
            )
            self.assertNotEqual(
                result.observed.identity,
                result.revalidated.identity,
            )
            self.assertEqual(
                archive_doctor.doctor_exit_code_with_snapshot(0, result),
                1,
            )
            self.assertEqual(
                archive_doctor.doctor_exit_code_with_snapshot(2, result),
                2,
            )

    def test_manifest_presence_transitions_are_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            manifest = self.make_archive(root, None)
            _raw, absent = archive_doctor.capture_doctor_object_manifest_snapshot(
                root,
                observed_at=OBSERVED_AT,
            )
            self.assertEqual(absent.state, "absent")

            unchanged = archive_doctor.revalidate_doctor_object_manifest_snapshot(
                root,
                absent,
                revalidated_at=REVALIDATED_AT,
            )
            self.assertEqual(unchanged.state, "current")

            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_bytes(b"new-row\n")
            appeared = archive_doctor.revalidate_doctor_object_manifest_snapshot(
                root,
                absent,
                revalidated_at=REVALIDATED_AT,
            )
            self.assertEqual(appeared.state, "stale")

            _raw, present = archive_doctor.capture_doctor_object_manifest_snapshot(
                root,
                observed_at=OBSERVED_AT,
            )
            manifest.unlink()
            disappeared = archive_doctor.revalidate_doctor_object_manifest_snapshot(
                root,
                present,
                revalidated_at=REVALIDATED_AT,
            )
            self.assertEqual(disappeared.state, "stale")

    def test_unavailable_capture_or_revalidation_fails_unverified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            manifest = self.make_archive(root, b"oversized")
            raw, unavailable = archive_doctor.capture_doctor_object_manifest_snapshot(
                root,
                maximum_bytes=4,
                observed_at=OBSERVED_AT,
            )
            self.assertIsNone(raw)
            self.assertEqual(unavailable.state, "unavailable")
            self.assertEqual(
                unavailable.reason_code,
                "object_manifest_snapshot_too_large",
            )
            result = archive_doctor.revalidate_doctor_object_manifest_snapshot(
                root,
                unavailable,
                revalidated_at=REVALIDATED_AT,
            )
            self.assertEqual(result.state, "unverified")
            self.assertTrue(result.requires_nonzero_exit)

            manifest.write_bytes(b"ok")
            _raw, observed = archive_doctor.capture_doctor_object_manifest_snapshot(
                root,
                maximum_bytes=4,
                observed_at=OBSERVED_AT,
            )
            manifest.unlink()
            manifest.mkdir()
            revalidation_unavailable = (
                archive_doctor.revalidate_doctor_object_manifest_snapshot(
                    root,
                    observed,
                    revalidated_at=REVALIDATED_AT,
                )
            )
            self.assertEqual(revalidation_unavailable.state, "unverified")
            self.assertTrue(revalidation_unavailable.requires_nonzero_exit)
            self.assertEqual(
                revalidation_unavailable.as_dict()["revalidated_reason_code"],
                "object_manifest_snapshot_special_file",
            )

    def test_unsafe_manifest_parent_is_unavailable_without_path_echo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "private-parent-marker"
            root.mkdir()
            (root / "objects").write_text("not a directory", encoding="utf-8")

            raw, snapshot = archive_doctor.capture_doctor_object_manifest_snapshot(
                root,
                observed_at=OBSERVED_AT,
            )

            self.assertIsNone(raw)
            self.assertEqual(snapshot.state, "unavailable")
            self.assertEqual(
                snapshot.reason_code,
                "object_manifest_snapshot_parent_unsafe",
            )
            self.assertNotIn("private-parent-marker", json.dumps(snapshot.as_dict()))


class SuggestedCommandModeResolverTests(unittest.TestCase):
    @staticmethod
    def parser_inventory() -> dict[str, object]:
        parser = argparse.ArgumentParser(prog="archive")
        commands = parser.add_subparsers(dest="command", required=True)

        remint = commands.add_parser(
            "remint-reconcile",
            aliases=["remint"],
        )
        remint.add_argument("archive_root")
        remint.add_argument("--dry-run", action="store_true")
        remint.add_argument("--approve", action="store_true")
        remint.set_defaults(func=lambda _args: 0)

        derive = commands.add_parser("derive-text")
        derive_commands = derive.add_subparsers(dest="derive_command", required=True)
        capture = derive_commands.add_parser("capture", aliases=["add"])
        capture.add_argument("archive_root")
        capture.add_argument("--dry-run", action="store_true")
        capture.set_defaults(func=lambda _args: 0)

        migrate = commands.add_parser("migrate")
        migrate.add_argument("archive_root")
        migrate.add_argument("--dry-run", action="store_true")
        migrate.add_argument("--approve", action="store_true")
        migrate.add_argument("--target")
        migrate.set_defaults(
            func=lambda _args: 0,
            _wom_approval_scope={
                "kind": "argument_value_allowlist",
                "argument": "--target",
                "allowed_values": ["safe-target"],
                "outside_scope_status": command_status.APPROVAL_FIXED_CLOSED,
                "outside_scope_reason_code": command_status.COMPOUND_APPROVAL_REASON_CODE,
            },
        )

        return command_status.build_command_status_inventory(
            parser,
            {"remint-reconcile"},
        )

    def test_dry_run_is_available_while_approval_is_fixed_closed(self) -> None:
        inventory = self.parser_inventory()

        dry_run = command_status.resolve_suggested_command_mode(
            inventory,
            "archive remint-reconcile <archive-root> --dry-run --format json",
        )
        approval = command_status.resolve_suggested_command_mode(
            inventory,
            "archive remint-reconcile <archive-root> --approve",
        )

        self.assertEqual(dry_run["resolution_state"], "resolved")
        self.assertEqual(dry_run["canonical_path"], "remint-reconcile")
        self.assertEqual(dry_run["requested_mode"], "dry_run")
        self.assertTrue(dry_run["requested_mode_available"])
        self.assertEqual(
            dry_run["approval_status"],
            command_status.APPROVAL_FIXED_CLOSED,
        )
        self.assertEqual(approval["requested_mode"], "approve")
        self.assertFalse(approval["requested_mode_available"])
        self.assertEqual(
            approval["requested_mode_reason_code"],
            command_status.COMPOUND_APPROVAL_REASON_CODE,
        )
        self.assertFalse(approval["prerequisites_evaluated"])

    def test_alias_and_longest_nested_invocation_path_resolve(self) -> None:
        inventory = self.parser_inventory()

        alias = command_status.resolve_suggested_command_mode(
            inventory,
            "wom remint <archive-root> --dry-run",
        )
        nested = command_status.resolve_suggested_command_mode(
            inventory,
            "archive derive-text add <archive-root> --dry-run",
        )

        self.assertEqual(alias["canonical_path"], "remint-reconcile")
        self.assertEqual(alias["matched_invocation_path"], "remint")
        self.assertEqual(nested["canonical_path"], "derive-text capture")
        self.assertEqual(nested["matched_invocation_path"], "derive-text add")
        self.assertTrue(nested["requested_mode_available"])

    def test_conditional_approval_scope_is_evaluated_without_prerequisites(self) -> None:
        inventory = self.parser_inventory()

        allowed = command_status.resolve_suggested_command_mode(
            inventory,
            "archive migrate <archive-root> --target=safe-target --approve",
        )
        closed = command_status.resolve_suggested_command_mode(
            inventory,
            "archive migrate <archive-root> --target other-target --approve",
        )
        dry_run_outside_approval_scope = (
            command_status.resolve_suggested_command_mode(
                inventory,
                "archive migrate <archive-root> --target other-target --dry-run",
            )
        )

        self.assertTrue(allowed["requested_mode_available"])
        self.assertFalse(allowed["prerequisites_evaluated"])
        self.assertFalse(closed["requested_mode_available"])
        self.assertEqual(
            closed["requested_mode_reason_code"],
            command_status.COMPOUND_APPROVAL_REASON_CODE,
        )
        self.assertTrue(
            dry_run_outside_approval_scope["requested_mode_available"]
        )
        self.assertFalse(
            dry_run_outside_approval_scope[
                "approval_mode_available_for_arguments"
            ]
        )
        self.assertEqual(
            dry_run_outside_approval_scope[
                "approval_mode_reason_code_for_arguments"
            ],
            command_status.COMPOUND_APPROVAL_REASON_CODE,
        )

    def test_conflicting_modes_and_unresolved_input_fail_content_free(self) -> None:
        inventory = self.parser_inventory()

        conflicting = command_status.resolve_suggested_command_mode(
            inventory,
            "archive remint-reconcile <archive-root> --dry-run --approve",
        )
        after_separator = command_status.resolve_suggested_command_mode(
            inventory,
            "archive remint-reconcile <archive-root> -- --dry-run",
        )
        private_marker = "PRIVATE_SUGGESTED_COMMAND_VALUE"
        unresolved = command_status.resolve_suggested_command_mode(
            inventory,
            f"archive unknown-command {private_marker} --dry-run",
        )

        self.assertEqual(conflicting["requested_mode"], "conflicting")
        self.assertFalse(conflicting["requested_mode_available"])
        self.assertEqual(
            conflicting["requested_mode_reason_code"],
            "suggested_command_mode_conflicting",
        )
        self.assertEqual(after_separator["requested_mode"], "unspecified")
        self.assertIsNone(after_separator["requested_mode_available"])
        self.assertEqual(unresolved["resolution_state"], "unresolved")
        self.assertEqual(
            unresolved["resolution_reason_code"],
            "suggested_command_not_in_inventory",
        )
        self.assertNotIn(private_marker, json.dumps(unresolved, sort_keys=True))
        self.assertFalse(unresolved["private_values_echoed"])

    def test_real_cli_inventory_reports_remint_dry_run_separately_from_approval(self) -> None:
        from wom_kit import archive_cli

        inventory = command_status.build_command_status_inventory(
            archive_cli.build_parser(),
            archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS,
        )

        dry_run = command_status.resolve_suggested_command_mode(
            inventory,
            "archive remint-reconcile <archive-root> --zettel-id <id> --dry-run",
        )
        approval = command_status.resolve_suggested_command_mode(
            inventory,
            "archive remint-reconcile <archive-root> --zettel-id <id> --approve",
        )

        self.assertTrue(dry_run["invocation_surface_available"])
        self.assertTrue(dry_run["requested_mode_available"])
        self.assertEqual(
            dry_run["approval_status"],
            command_status.APPROVAL_FIXED_CLOSED,
        )
        self.assertFalse(dry_run["approval_mode_available_for_arguments"])
        self.assertFalse(approval["requested_mode_available"])
        self.assertEqual(
            approval["requested_mode_reason_code"],
            command_status.COMPOUND_APPROVAL_REASON_CODE,
        )

        frontmatter = command_status.resolve_suggested_command_mode(
            inventory,
            archive_cli.archive_services.FRONTMATTER_V03_MIGRATION_COMMAND,
        )
        self.assertEqual(frontmatter["requested_mode"], "dry_run")
        self.assertTrue(frontmatter["requested_mode_available"])
        self.assertEqual(
            frontmatter["approval_status"],
            command_status.APPROVAL_AVAILABLE,
        )
        self.assertFalse(
            frontmatter["approval_mode_available_for_arguments"]
        )
        self.assertEqual(
            frontmatter["approval_mode_reason_code_for_arguments"],
            command_status.COMPOUND_APPROVAL_REASON_CODE,
        )


class DoctorCliIntegrationTests(unittest.TestCase):
    @staticmethod
    def make_archive(
        root: Path,
        raw: bytes | None = b'{"object_id":"sha256:00"}\n',
    ) -> Path:
        manifest = root / "objects" / "manifests" / "files.jsonl"
        if raw is None:
            root.mkdir(parents=True)
        else:
            manifest.parent.mkdir(parents=True)
            manifest.write_bytes(raw)
        return manifest

    @staticmethod
    def object_manifest_stages(
        doctor: archive_cli.Doctor,
    ) -> list[tuple[str, object]]:
        return [("object-manifest", doctor._check_object_manifest)]

    @staticmethod
    def run_cli(args: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = archive_cli.main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_doctor_parses_only_raw_returned_by_snapshot_capture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            manifest = self.make_archive(root, b'{"disk":"must-not-be-read"}\n')
            digest = "a" * 64
            record = json.dumps(
                {
                    "object_id": f"sha256:{digest}",
                    "sha256": digest,
                    "logical_key": "synthetic",
                    "locations": [],
                },
                separators=(",", ":"),
            ).encode("utf-8")
            captured_raw = record + b"\n" + record + b"\n"
            observed = archive_doctor.DoctorInputSnapshot(
                relative_path=archive_doctor.DOCTOR_OBJECT_MANIFEST_RELATIVE_PATH,
                observed_at=OBSERVED_AT,
                state="present",
                identity="sha256:" + hashlib.sha256(captured_raw).hexdigest(),
                size_bytes=len(captured_raw),
                maximum_bytes=archive_doctor.DOCTOR_OBJECT_MANIFEST_MAX_BYTES,
            )
            revalidation = archive_doctor.DoctorInputRevalidation(
                observed=observed,
                revalidated=observed,
                state="current",
                reason_codes=(),
                requires_nonzero_exit=False,
            )
            doctor = archive_cli.Doctor(root)
            original_read_text = Path.read_text

            def guarded_read_text(path: Path, *args: object, **kwargs: object) -> str:
                if Path(path).resolve() == manifest.resolve():
                    raise AssertionError("doctor_performed_second_manifest_read")
                return original_read_text(path, *args, **kwargs)

            with (
                mock.patch.object(
                    archive_cli.Doctor,
                    "_full_stages",
                    autospec=True,
                    side_effect=self.object_manifest_stages,
                ),
                mock.patch.object(
                    archive_doctor,
                    "capture_doctor_object_manifest_snapshot",
                    return_value=(captured_raw, observed),
                ) as capture,
                mock.patch.object(
                    archive_doctor,
                    "revalidate_doctor_object_manifest_snapshot",
                    return_value=revalidation,
                ),
                mock.patch.object(
                    archive_services,
                    "load_manifest_records",
                    side_effect=AssertionError("legacy_manifest_loader_used"),
                ) as legacy_loader,
                mock.patch.object(Path, "read_text", new=guarded_read_text),
            ):
                diagnostics = doctor.run()

            self.assertEqual(capture.call_count, 1)
            legacy_loader.assert_not_called()
            self.assertIn("object_id_duplicate", {item.code for item in diagnostics})
            self.assertNotIn("doctor_performed_second_manifest_read", str(diagnostics))

    def test_manifest_change_during_cli_run_is_stale_and_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            manifest = self.make_archive(root, b"\n")
            original_revalidate = (
                archive_doctor.revalidate_doctor_object_manifest_snapshot
            )

            def mutate_then_revalidate(
                archive_root: Path,
                observed: archive_doctor.DoctorInputSnapshot,
                *,
                root_boundary: archive_doctor.DoctorArchiveRootBoundary | None = None,
            ) -> archive_doctor.DoctorInputRevalidation:
                manifest.write_bytes(b"{\"changed\":true}\n")
                return original_revalidate(
                    archive_root,
                    observed,
                    root_boundary=root_boundary,
                )

            with (
                mock.patch.object(
                    archive_cli.Doctor,
                    "_full_stages",
                    autospec=True,
                    side_effect=self.object_manifest_stages,
                ),
                mock.patch.object(
                    archive_doctor,
                    "revalidate_doctor_object_manifest_snapshot",
                    side_effect=mutate_then_revalidate,
                ),
            ):
                code, stdout, stderr = self.run_cli(
                    [
                        "doctor",
                        str(root),
                        "--summary",
                        "--format",
                        "json",
                        "--output",
                        "ops/doctor-result.json",
                        "--no-progress",
                    ]
                )

            self.assertEqual(code, 1)
            self.assertEqual(stderr, "")
            summary = json.loads(stdout)
            revalidation = summary["input_revalidation"]
            self.assertEqual(revalidation["state"], "stale")
            self.assertFalse(revalidation["result_current"])
            self.assertTrue(revalidation["requires_nonzero_exit"])
            self.assertFalse(revalidation["full_archive_atomic_snapshot"])
            self.assertEqual(
                revalidation["reason_codes"],
                ["object_manifest_changed_during_doctor"],
            )
            diagnostics = json.loads(
                (root / "ops" / "doctor-result.json").read_text(encoding="utf-8")
            )
            lifecycle = [
                item
                for item in diagnostics
                if item["code"] == "doctor_input_snapshot_stale"
            ]
            self.assertEqual(len(lifecycle), 1)
            self.assertEqual(lifecycle[0]["severity"], "ERROR")
            self.assertEqual(lifecycle[0]["details"]["state"], "stale")

    def test_manifest_change_makes_mcp_structured_ok_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            manifest = self.make_archive(root, b"\n")
            original_revalidate = (
                archive_doctor.revalidate_doctor_object_manifest_snapshot
            )

            def mutate_then_revalidate(
                archive_root: Path,
                observed: archive_doctor.DoctorInputSnapshot,
                *,
                root_boundary: archive_doctor.DoctorArchiveRootBoundary | None = None,
            ) -> archive_doctor.DoctorInputRevalidation:
                manifest.write_bytes(b"{\"changed\":true}\n")
                return original_revalidate(
                    archive_root,
                    observed,
                    root_boundary=root_boundary,
                )

            with (
                mock.patch.object(
                    archive_cli.Doctor,
                    "_full_stages",
                    autospec=True,
                    side_effect=self.object_manifest_stages,
                ),
                mock.patch.object(
                    archive_doctor,
                    "revalidate_doctor_object_manifest_snapshot",
                    side_effect=mutate_then_revalidate,
                ),
            ):
                result = mcp_server.tool_archive_doctor(
                    {"archive_root": str(root)}
                )

            self.assertFalse(result["isError"])
            structured = result["structuredContent"]
            self.assertFalse(structured["ok"])
            self.assertGreaterEqual(structured["errors"], 1)
            lifecycle = [
                item
                for item in structured["diagnostics"]
                if item["code"] == "doctor_input_snapshot_stale"
            ]
            self.assertEqual(len(lifecycle), 1)
            self.assertEqual(lifecycle[0]["details"]["state"], "stale")
            self.assertFalse(
                lifecycle[0]["details"]["full_archive_atomic_snapshot"]
            )

    def test_unavailable_snapshot_and_invalid_utf8_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unavailable_root = Path(tmp) / "unavailable"
            unavailable_root.mkdir()
            (unavailable_root / "objects").write_text(
                "not-a-directory",
                encoding="utf-8",
            )
            invalid_root = Path(tmp) / "invalid-utf8"
            self.make_archive(invalid_root, b"\xff\n")

            with mock.patch.object(
                archive_cli.Doctor,
                "_full_stages",
                autospec=True,
                side_effect=self.object_manifest_stages,
            ):
                unavailable = archive_cli.Doctor(unavailable_root).run()
                invalid = archive_cli.Doctor(invalid_root).run()

            unavailable_codes = {item.code for item in unavailable}
            self.assertIn(
                "object_manifest_snapshot_parent_unsafe",
                unavailable_codes,
            )
            self.assertIn("doctor_input_snapshot_unverified", unavailable_codes)
            invalid_codes = {item.code for item in invalid}
            self.assertIn("object_manifest_utf8_invalid", invalid_codes)
            self.assertIn("doctor_input_snapshot_current", invalid_codes)

    def test_progress_is_default_on_and_no_progress_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            self.make_archive(root, None)
            with mock.patch.object(
                archive_cli.Doctor,
                "_full_stages",
                autospec=True,
                side_effect=self.object_manifest_stages,
            ):
                default_code, default_stdout, default_stderr = self.run_cli(
                    ["doctor", str(root), "--summary", "--format", "json"]
                )
                quiet_code, quiet_stdout, quiet_stderr = self.run_cli(
                    [
                        "doctor",
                        str(root),
                        "--summary",
                        "--format",
                        "json",
                        "--no-progress",
                    ]
                )

            self.assertEqual(default_code, 0)
            self.assertEqual(quiet_code, 0)
            self.assertTrue(json.loads(default_stdout)["ok"])
            self.assertTrue(json.loads(quiet_stdout)["ok"])
            self.assertIn("[doctor] doctor-run: start", default_stderr)
            self.assertIn("[doctor] object-manifest: start", default_stderr)
            self.assertIn("[doctor] doctor-run: done", default_stderr)
            self.assertEqual(quiet_stderr, "")

    def test_protected_manifest_output_is_rejected_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            original = b"\n"
            manifest = self.make_archive(root, original)
            with mock.patch.object(
                archive_cli.Doctor,
                "_full_stages",
                autospec=True,
                side_effect=self.object_manifest_stages,
            ):
                code, stdout, stderr = self.run_cli(
                    [
                        "doctor",
                        str(root),
                        "--output",
                        archive_doctor.DOCTOR_OBJECT_MANIFEST_RELATIVE_PATH,
                        "--format",
                        "json",
                        "--no-progress",
                    ]
                )

            self.assertEqual(code, 1)
            self.assertEqual(stdout, "")
            self.assertIn(
                "--output cannot overwrite the doctor object-manifest input",
                stderr,
            )
            self.assertEqual(manifest.read_bytes(), original)

    def test_existing_archive_file_output_is_rejected_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            self.make_archive(root, b"\n")
            archive_config = root / "archive.yml"
            original = b"archive_id: exact-original\n"
            archive_config.write_bytes(original)
            with mock.patch.object(
                archive_cli.Doctor,
                "_full_stages",
                autospec=True,
                side_effect=self.object_manifest_stages,
            ):
                code, stdout, stderr = self.run_cli(
                    [
                        "doctor",
                        str(root),
                        "--output",
                        "archive.yml",
                        "--format",
                        "json",
                        "--no-progress",
                    ]
                )

            self.assertEqual(code, 1)
            self.assertEqual(stdout, "")
            self.assertIn(
                "--output must name a new archive-relative file",
                stderr,
            )
            self.assertEqual(archive_config.read_bytes(), original)

    def test_protected_manifest_hardlink_output_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            original = b"\n"
            manifest = self.make_archive(root, original)
            alias = root / "ops" / "doctor-result.json"
            alias.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(manifest, alias)
            except OSError as exc:
                self.skipTest(f"hardlink creation unavailable: {exc}")
            with mock.patch.object(
                archive_cli.Doctor,
                "_full_stages",
                autospec=True,
                side_effect=self.object_manifest_stages,
            ):
                code, stdout, stderr = self.run_cli(
                    [
                        "doctor",
                        str(root),
                        "--output",
                        "ops/doctor-result.json",
                        "--format",
                        "json",
                        "--no-progress",
                    ]
                )

            self.assertEqual(code, 1)
            self.assertEqual(stdout, "")
            self.assertIn(
                "--output cannot alias the doctor object-manifest input",
                stderr,
            )
            self.assertEqual(manifest.read_bytes(), original)

    def test_progress_log_inside_archive_is_rejected_before_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            original = b"\n"
            manifest = self.make_archive(root, original)
            with mock.patch.object(
                archive_cli.Doctor,
                "_full_stages",
                autospec=True,
                side_effect=self.object_manifest_stages,
            ):
                code, stdout, stderr = self.run_cli(
                    [
                        "doctor",
                        str(root),
                        "--progress-log",
                        str(manifest),
                        "--format",
                        "json",
                        "--no-progress",
                    ]
                )

            self.assertEqual(code, 1)
            self.assertEqual(stdout, "")
            self.assertIn(
                "--progress-log must be a new file outside the archive root",
                stderr,
            )
            self.assertEqual(manifest.read_bytes(), original)

    def test_progress_log_hardlink_outside_archive_is_never_truncated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            original = b"\n"
            manifest = self.make_archive(root, original)
            alias = Path(tmp) / "doctor-progress.jsonl"
            try:
                os.link(manifest, alias)
            except OSError as exc:
                self.skipTest(f"hardlink creation unavailable: {exc}")
            code, stdout, stderr = self.run_cli(
                [
                    "doctor",
                    str(root),
                    "--progress-log",
                    str(alias),
                    "--format",
                    "json",
                    "--no-progress",
                ]
            )

            self.assertEqual(code, 1)
            self.assertEqual(stdout, "")
            self.assertIn(
                "--progress-log must be a new file outside the archive root",
                stderr,
            )
            self.assertEqual(manifest.read_bytes(), original)

    def test_progress_log_path_replacement_after_initialization_cannot_touch_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            self.make_archive(root, b"\n")
            archive_config = root / "archive.yml"
            original = b"archive_id: exact-original\n"
            archive_config.write_bytes(original)
            log_path = Path(tmp) / "doctor-progress.jsonl"
            reporter = archive_cli.CommandProgressReporter(
                False,
                label="doctor",
                heartbeat_interval_seconds=60.0,
                progress_log_path=log_path,
            )
            try:
                try:
                    log_path.unlink()
                    os.link(archive_config, log_path)
                except OSError:
                    # Windows may deny deletion while WOM retains the handle;
                    # that denial is itself the safe outcome.
                    pass
                reporter.progress("doctor-run", "start", None, None)
            finally:
                reporter.close()

            self.assertEqual(archive_config.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
