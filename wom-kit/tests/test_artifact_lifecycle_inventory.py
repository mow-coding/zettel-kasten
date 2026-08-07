from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from jsonschema import Draft202012Validator, FormatChecker

from wom_kit import archive_cli
from wom_kit import artifact_lifecycle_inventory as inventory


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "wom-kit" / "schemas" / "artifact-lifecycle-inventory.schema.json"


class ArtifactLifecycleInventoryTests(unittest.TestCase):
    def make_archive(self, parent: Path, *, name: str = "archive") -> Path:
        root = parent / name
        root.mkdir()
        (root / "archive.yml").write_text(
            "archive_id: archive:personal:artifact-test\n"
            "name: Artifact Test\n"
            "type: personal\n",
            encoding="utf-8",
        )
        return root

    def run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = archive_cli.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def validate_schema(self, result: dict[str, object]) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        errors = list(
            Draft202012Validator(
                schema,
                format_checker=FormatChecker(),
            ).iter_errors(result)
        )
        self.assertEqual(errors, [], [error.message for error in errors])

    def test_empty_archive_is_complete_clear_and_schema_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp))
            result = inventory.artifact_lifecycle_inventory(
                root,
                _now=datetime(2026, 8, 7, tzinfo=timezone.utc),
            )

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["inventory_state"], "clear")
        self.assertTrue(result["coverage"]["complete"])
        self.assertEqual(result["coverage"]["scope_count"], 12)
        self.assertEqual(result["review_candidate_count"], 0)
        self.assertEqual(result["items"], [])
        self.assertEqual(result["would_change"], [])
        self.validate_schema(result)

    def test_default_output_is_content_free_and_path_opt_in_preserves_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp))
            private_name = "client-secret-plan-김민수.md"
            private_body = "PRIVATE ARTIFACT BODY MUST NEVER ECHO"
            path = root / ".wom-scratch" / "session" / private_name
            path.parent.mkdir(parents=True)
            path.write_text(private_body, encoding="utf-8")
            hidden = inventory.artifact_lifecycle_inventory(root)
            shown = inventory.artifact_lifecycle_inventory(
                root,
                show_relative_paths=True,
            )

        hidden_text = json.dumps(hidden, ensure_ascii=False)
        shown_text = json.dumps(shown, ensure_ascii=False)
        self.assertNotIn(private_name, hidden_text)
        self.assertNotIn(private_body, hidden_text)
        self.assertNotIn(str(root), hidden_text)
        self.assertIn(private_name, shown_text)
        self.assertNotIn(private_body, shown_text)
        self.assertEqual(hidden["inventory_digest"], shown["inventory_digest"])
        self.assertFalse(hidden["privacy_guards"]["relative_paths_echoed"])
        self.assertTrue(shown["privacy_guards"]["relative_paths_echoed"])
        self.assertEqual(len({item["artifact_ref"] for item in hidden["items"]}), 1)

    def test_object_manifest_reconciliation_uses_names_not_object_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp))
            manifested_digest = "a" * 64
            candidate_digest = "b" * 64
            manifest = root / "objects" / "manifests" / "files.jsonl"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                json.dumps({"object_id": f"sha256:{manifested_digest}"}) + "\n",
                encoding="utf-8",
            )
            manifested = root / "objects" / "sha256" / "aa" / manifested_digest
            candidate = root / "objects" / "sha256" / "bb" / candidate_digest
            manifested.parent.mkdir(parents=True)
            candidate.parent.mkdir(parents=True)
            manifested.write_bytes(b"PRIVATE MANIFESTED OBJECT BYTES")
            candidate.write_bytes(b"PRIVATE UNMANIFESTED OBJECT BYTES")
            result = inventory.artifact_lifecycle_inventory(root)

        output = json.dumps(result)
        reconciliation = result["local_object_reconciliation"]
        self.assertTrue(result["ok"], result)
        self.assertTrue(reconciliation["complete"])
        self.assertEqual(reconciliation["valid_layout_file_count"], 2)
        self.assertEqual(reconciliation["unmanifested_local_object_candidate_count"], 1)
        self.assertFalse(reconciliation["object_bytes_hashed"])
        self.assertFalse(reconciliation["orphan_claimed"])
        self.assertNotIn(manifested_digest, output)
        self.assertNotIn(candidate_digest, output)
        self.assertNotIn("PRIVATE", output)
        candidate_rows = [
            item
            for item in result["items"]
            if item["review_state"] == "unmanifested_local_object_candidate"
        ]
        self.assertEqual(len(candidate_rows), 1)

    def test_invalid_manifest_blocks_without_false_orphan_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp))
            digest = "c" * 64
            manifest = root / "objects" / "manifests" / "files.jsonl"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                '{"object_id":"sha256:' + digest + '","object_id":"sha256:' + digest + '"}\n',
                encoding="utf-8",
            )
            object_path = root / "objects" / "sha256" / "cc" / digest
            object_path.parent.mkdir(parents=True)
            object_path.write_bytes(b"DO NOT READ")
            result = inventory.artifact_lifecycle_inventory(root)

        self.assertFalse(result["ok"])
        self.assertEqual(result["inventory_state"], "blocked")
        self.assertIn("object_manifest_record_invalid", result["blockers"])
        self.assertFalse(result["local_object_reconciliation"]["complete"])
        self.assertIsNone(
            result["local_object_reconciliation"][
                "unmanifested_local_object_candidate_count"
            ]
        )

    def test_duplicate_manifest_object_id_blocks_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp))
            digest = "d" * 64
            manifest = root / "objects" / "manifests" / "files.jsonl"
            manifest.parent.mkdir(parents=True)
            row = json.dumps({"object_id": f"sha256:{digest}"}) + "\n"
            manifest.write_text(row + row, encoding="utf-8")
            object_path = root / "objects" / "sha256" / "dd" / digest
            object_path.parent.mkdir(parents=True)
            object_path.write_bytes(b"DO NOT READ")
            result = inventory.artifact_lifecycle_inventory(root)

        self.assertFalse(result["ok"])
        self.assertEqual(result["object_manifest"]["duplicate_object_id_count"], 1)
        self.assertIn("object_manifest_duplicate_object_id", result["blockers"])
        self.assertFalse(result["local_object_reconciliation"]["complete"])
        self.assertIsNone(
            result["local_object_reconciliation"][
                "unmanifested_local_object_candidate_count"
            ]
        )

    def test_invalid_local_object_layout_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp))
            manifest = root / "objects" / "manifests" / "files.jsonl"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("", encoding="utf-8")
            invalid = root / "objects" / "sha256" / "zz" / "private-filename.bin"
            invalid.parent.mkdir(parents=True)
            invalid.write_bytes(b"PRIVATE")
            result = inventory.artifact_lifecycle_inventory(root)

        self.assertFalse(result["ok"])
        self.assertIn("local_object_store_layout_invalid", result["blockers"])
        self.assertEqual(
            result["local_object_reconciliation"]["invalid_layout_file_count"],
            1,
        )
        self.assertNotIn("private-filename.bin", json.dumps(result))

    def test_per_root_limit_blocks_and_preserves_other_root_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp))
            scratch = root / "tmp"
            inbox = root / "inbox"
            scratch.mkdir()
            inbox.mkdir()
            for index in range(4):
                (scratch / f"secret-{index}.txt").write_text("private", encoding="utf-8")
            (inbox / "one.md").write_text("private", encoding="utf-8")
            result = inventory.artifact_lifecycle_inventory(
                root,
                max_entries_per_root=2,
            )

        scopes = {row["root_id"]: row for row in result["coverage"]["scopes"]}
        self.assertFalse(result["ok"])
        self.assertTrue(scopes["temporary_files"]["truncated"])
        self.assertFalse(scopes["temporary_files"]["coverage_complete"])
        self.assertTrue(scopes["draft_inbox"]["coverage_complete"])
        self.assertIn("temporary_files_entry_limit_reached", result["blockers"])
        self.assertIn("declared_lifecycle_coverage_incomplete", result["blockers"])

    def test_never_touch_objets_reports_presence_without_enumeration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp))
            child = root / "objets" / "client-private-original.mov"
            child.parent.mkdir()
            child.write_bytes(b"PRIVATE ORIGINAL BYTES")
            result = inventory.artifact_lifecycle_inventory(root)

        output = json.dumps(result)
        scope = next(
            row
            for row in result["coverage"]["scopes"]
            if row["root_id"] == "noncanonical_in_root_objets"
        )
        self.assertEqual(scope["scan_mode"], "root_presence_only_never_touch")
        self.assertEqual(scope["file_count"], 0)
        self.assertEqual(scope["entries_seen"], 0)
        self.assertEqual(scope["directory_count"], 1)
        self.assertNotIn("client-private-original.mov", output)
        self.assertNotIn("PRIVATE ORIGINAL", output)
        rows = [
            item
            for item in result["items"]
            if item["root_id"] == "noncanonical_in_root_objets"
        ]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["entry_kind"], "directory")
        self.assertEqual(rows[0]["review_state"], "manual_migration_hold")

    def test_workpack_expiry_is_review_state_not_cleanup_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp))
            expired = root / "workpacks" / "private-expired" / "package.yml"
            active = root / "workpacks" / "private-active" / "package.yml"
            expired.parent.mkdir(parents=True)
            active.parent.mkdir(parents=True)
            expired.write_text(
                "package_id: private-expired\nexpires_at: 2020-01-01T00:00:00Z\n",
                encoding="utf-8",
            )
            active.write_text(
                "package_id: private-active\nexpires_at: 2999-01-01T00:00:00Z\n",
                encoding="utf-8",
            )
            result = inventory.artifact_lifecycle_inventory(
                root,
                _now=datetime(2026, 8, 7, tzinfo=timezone.utc),
            )

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["workpacks"]["expired_count"], 1)
        self.assertEqual(result["workpacks"]["active_count"], 1)
        states = {item["review_state"] for item in result["items"]}
        self.assertIn("workpack_expired_review_required", states)
        self.assertIn("workpack_active", states)
        self.assertEqual(result["would_change"], [])
        self.assertFalse(result["closed_actions"]["files_deleted"])
        self.assertIn(
            "expiry alone is not deletion approval",
            " ".join(result["next_safe_actions"]),
        )

    def test_missing_and_duplicate_workpack_metadata_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp))
            (root / "workpacks" / "missing").mkdir(parents=True)
            duplicate = root / "workpacks" / "duplicate" / "package.yml"
            duplicate.parent.mkdir(parents=True)
            duplicate.write_text(
                "expires_at: 2020-01-01T00:00:00Z\n"
                "expires_at: 2999-01-01T00:00:00Z\n",
                encoding="utf-8",
            )
            result = inventory.artifact_lifecycle_inventory(root)

        self.assertFalse(result["ok"])
        self.assertIn("workpack_package_metadata_missing", result["blockers"])
        self.assertIn("workpack_package_metadata_invalid", result["blockers"])
        self.assertEqual(result["workpacks"]["missing_package_metadata_count"], 1)
        self.assertEqual(result["workpacks"]["invalid_package_metadata_count"], 1)

    def test_workpack_yaml_alias_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp))
            package = root / "workpacks" / "alias" / "package.yml"
            package.parent.mkdir(parents=True)
            package.write_text(
                "package_id: &private private-value\n"
                "copied_id: *private\n"
                "expires_at: 2999-01-01T00:00:00Z\n",
                encoding="utf-8",
            )
            result = inventory.artifact_lifecycle_inventory(root)

        self.assertFalse(result["ok"])
        self.assertIn("workpack_package_metadata_invalid", result["blockers"])
        self.assertEqual(result["workpacks"]["invalid_package_metadata_count"], 1)

    def test_changed_entry_blocks_snapshot_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp))
            target = root / "tmp" / "volatile.txt"
            target.parent.mkdir()
            target.write_text("private", encoding="utf-8")
            real_lstat = os.lstat
            target_calls = 0

            def changing_lstat(path: os.PathLike[str] | str) -> object:
                nonlocal target_calls
                result = real_lstat(path)
                candidate = Path(path)
                if candidate.name != target.name or candidate.parent.name != target.parent.name:
                    return result
                target_calls += 1
                if target_calls < 2:
                    return result
                return SimpleNamespace(
                    st_mode=result.st_mode,
                    st_ino=result.st_ino,
                    st_dev=result.st_dev,
                    st_nlink=result.st_nlink,
                    st_uid=result.st_uid,
                    st_gid=result.st_gid,
                    st_size=result.st_size,
                    st_atime=result.st_atime,
                    st_mtime=result.st_mtime,
                    st_mtime_ns=result.st_mtime_ns + 1,
                    st_ctime=result.st_ctime,
                    st_file_attributes=getattr(result, "st_file_attributes", 0),
                )

            with mock.patch.object(inventory.os, "lstat", side_effect=changing_lstat):
                result = inventory.artifact_lifecycle_inventory(root)

        self.assertFalse(result["ok"])
        self.assertIn("temporary_files_changed_during_scan", result["blockers"])
        scope = next(
            row
            for row in result["coverage"]["scopes"]
            if row["root_id"] == "temporary_files"
        )
        self.assertEqual(scope["changed_during_scan_count"], 1)
        self.assertEqual(scope["file_count"], 0)
        self.assertEqual(scope["byte_count"], 0)
        self.assertFalse(
            any(item["root_id"] == "temporary_files" for item in result["items"])
        )

    def test_manifest_descriptor_change_blocks_without_parsed_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp))
            manifest = root / "objects" / "manifests" / "files.jsonl"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                json.dumps({"object_id": "sha256:" + ("e" * 64)}) + "\n",
                encoding="utf-8",
            )
            real_fstat = os.fstat
            call_count = 0

            def changing_fstat(descriptor: int) -> object:
                nonlocal call_count
                result = real_fstat(descriptor)
                call_count += 1
                if call_count < 2:
                    return result
                return SimpleNamespace(
                    st_mode=result.st_mode,
                    st_ino=result.st_ino,
                    st_dev=result.st_dev,
                    st_size=result.st_size,
                    st_mtime_ns=result.st_mtime_ns + 1,
                    st_ctime_ns=result.st_ctime_ns,
                    st_ctime=result.st_ctime,
                    st_file_attributes=getattr(result, "st_file_attributes", 0),
                )

            with mock.patch.object(inventory.os, "fstat", side_effect=changing_fstat):
                result = inventory.artifact_lifecycle_inventory(root)

        self.assertFalse(result["ok"])
        self.assertIn("object_manifest_changed_during_read", result["blockers"])
        self.assertTrue(result["object_manifest"]["changed_during_read"])
        self.assertEqual(result["object_manifest"]["record_count"], 0)
        self.assertEqual(result["object_manifest"]["bytes_read"], 0)

    def test_symlink_is_not_followed_when_environment_allows_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = self.make_archive(base)
            outside = base / "outside-secret.txt"
            outside.write_text("PRIVATE OUTSIDE BODY", encoding="utf-8")
            link = root / "tmp" / "linked-secret.txt"
            link.parent.mkdir()
            try:
                link.symlink_to(outside)
            except OSError:
                self.skipTest("symlink creation not permitted in this environment")
            result = inventory.artifact_lifecycle_inventory(root)

        output = json.dumps(result)
        self.assertFalse(result["ok"])
        self.assertIn("temporary_files_link_or_reparse_skipped", result["blockers"])
        self.assertNotIn("outside-secret.txt", output)
        self.assertNotIn("PRIVATE OUTSIDE BODY", output)

    def test_cli_requires_dry_run_and_json_stays_content_free(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp))
            private = root / "tmp" / "client-private.txt"
            private.parent.mkdir()
            private.write_text("PRIVATE BODY", encoding="utf-8")
            blocked_code, blocked_stdout, blocked_stderr = self.run_cli(
                ["artifact-lifecycle-inventory", str(root), "--format", "json"]
            )
            code, stdout, stderr = self.run_cli(
                [
                    "artifact-lifecycle-inventory",
                    str(root),
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(blocked_code, 1)
        self.assertEqual(blocked_stdout, "")
        self.assertIn("requires --dry-run", blocked_stderr)
        self.assertEqual(code, 0, stderr)
        result = json.loads(stdout)
        self.assertNotIn("client-private.txt", stdout)
        self.assertNotIn("PRIVATE BODY", stdout)
        self.assertNotIn(str(root), stdout)
        self.validate_schema(result)


if __name__ == "__main__":
    unittest.main()
