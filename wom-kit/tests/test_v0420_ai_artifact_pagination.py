"""Real read-only AI fate inventory generations, not a larger listing cap."""

from __future__ import annotations

import copy
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from wom_kit import archive_cli, archive_services as services
from wom_kit import artifact_lifecycle_inventory as metadata


class AiArtifactPaginationTests(unittest.TestCase):
    def archive(self, base: Path, count: int = 0) -> Path:
        root = base / "archive"
        root.mkdir()
        (root / "archive.yml").write_text(
            "archive_id: archive:test\nname: Synthetic\ntype: personal\n", encoding="utf-8",
        )
        folder = root / ".wom-scratch" / "nested"
        folder.mkdir(parents=True)
        for index in range(count):
            (folder / f"private-note-{index:05d}.txt").write_bytes(b"ordinary private artifact body")
        return root.resolve()

    def receipt(self, root: Path, relative: str, *, name="one", **extra) -> Path:
        path = root / "receipts" / "sources" / f"{name}.source-intake-plan.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "archive_id": "archive:test", "ok": True, "dry_run": True,
            "lifecycle_action": "source_intake_plan", "blockers": [],
            "content_access": dict(services.SOURCE_INTAKE_CONTENT_ACCESS_EXPECTATIONS),
            "source_kind": "ai_artifact",
            "source_refs_for_draft": [{"type": "ai_artifact", "value": services.ai_artifact_ref_for_relative_path(relative)}],
            **extra,
        }
        problems = []
        services.prepare_source_intake_plan_for_draft(data, problems)
        self.assertEqual(problems, [])
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def assert_incomplete(self, result):
        self.assertFalse(result["ok"], result)
        self.assertFalse(result["counts_complete"])
        self.assertIsNone(result["total_candidate_count"])
        self.assertIsNone(result["fate_counts"])
        self.assertIsNone(result["artifact_kind_counts"])
        self.assertEqual(result["items"], [])
        self.assertTrue(result["truncated"])
        page = result["pagination"]
        for key in ("total_count", "remaining_count", "next_cursor", "has_more"):
            self.assertIsNone(page[key])
        self.assertFalse(page["complete_listing"])
        self.assertNotIn("No AI artifact candidates", " ".join(result["next_safe_actions"]))

    def test_6773_files_all_pages_and_global_fates_include_unseen_recorded_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp), 6773)
            self.receipt(root, ".wom-scratch/nested/private-note-06772.txt")
            cursor = None
            seen, snapshots = [], set()
            while True:
                result = services.ai_artifact_inventory(root, max_items=1000, cursor=cursor)
                self.assertTrue(result["ok"], result["blockers"])
                self.assertEqual(result["total_candidate_count"], 6773)
                self.assertEqual(result["fate_counts"], {"unreviewed_ai_artifact": 6772, "source_intake_recorded": 1})
                self.assertEqual(sum(result["artifact_kind_counts"].values()), 6773)
                page = result["pagination"]
                self.assertEqual(page["offset"], len(seen))
                self.assertLessEqual(len(result["items"]), 1000)
                seen.extend(item["artifact_ref"] for item in result["items"])
                snapshots.add(page["snapshot_sha256"])
                output = json.dumps(result)
                for value in ("private-note", "ordinary private artifact body", str(root)):
                    self.assertNotIn(value, output)
                self.assertFalse(result["closed_actions"]["files_written"])
                self.assertFalse(result["closed_actions"]["file_bodies_read"])
                cursor = page["next_cursor"]
                if cursor is None:
                    self.assertEqual(page["remaining_count"], 0)
                    break
            self.assertEqual(len(seen), 6773)
            self.assertEqual(len(set(seen)), 6773)
            self.assertEqual(len(snapshots), 1)

    def test_overlapping_roots_are_deduplicated_without_private_root_echo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp), 5)
            result = services.ai_artifact_inventory(root, include_roots=[".wom-scratch/nested", ".wom-scratch", ".wom-scratch/nested"])
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["total_candidate_count"], 5)
            self.assertEqual(result["scan_policy"]["roots"], [".wom-scratch/"])
            narrowed = services.ai_artifact_inventory(root, include_roots=[".wom-scratch/nested"])
            self.assertTrue(narrowed["ok"])
            self.assertNotIn("nested", json.dumps(narrowed))
            shown = services.ai_artifact_inventory(root, include_roots=[".wom-scratch/nested"], show_relative_paths=True)
            self.assertIn("nested", json.dumps(shown))

    def test_unseen_artifact_and_query_drift_reject_old_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp), 5)
            first = services.ai_artifact_inventory(root, max_items=2)
            cursor = first["pagination"]["next_cursor"]
            for arguments in ({"show_relative_paths": True}, {"include_roots": [".wom-scratch/nested"]}, {"project_root": root.parent}):
                with self.subTest(arguments=tuple(arguments)):
                    rejected = services.ai_artifact_inventory(root, max_items=2, cursor=cursor, **arguments)
                    self.assert_incomplete(rejected)
                    self.assertIn("snapshot_pagination_query_changed", rejected["blockers"])
            (root / ".wom-scratch/nested/private-note-00004.txt").write_bytes(b"changed unseen bytes")
            changed = services.ai_artifact_inventory(root, max_items=2, cursor=cursor)
            self.assert_incomplete(changed)
            self.assertIn("snapshot_pagination_generation_changed", changed["blockers"])

    def test_receipt_payload_change_same_summary_size_and_time_rejects_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp), 5)
            receipt = self.receipt(root, ".wom-scratch/nested/private-note-00004.txt", note="private_marker_A")
            first = services.ai_artifact_inventory(root, max_items=2)
            before = receipt.stat()
            receipt.write_bytes(receipt.read_bytes().replace(b"private_marker_A", b"private_marker_B"))
            os.utime(receipt, ns=(before.st_atime_ns, before.st_mtime_ns))
            changed = services.ai_artifact_inventory(root, max_items=2, cursor=first["pagination"]["next_cursor"])
            self.assert_incomplete(changed)
            self.assertEqual(first["fate_counts"], changed["observed_fate_counts"])
            self.assertIn("snapshot_pagination_generation_changed", changed["blockers"])
            self.assertNotIn("private_marker", json.dumps(changed))

    def test_new_receipt_and_unrelated_receipt_metadata_are_generation_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp), 5)
            first = services.ai_artifact_inventory(root, max_items=2)
            self.receipt(root, ".wom-scratch/nested/private-note-00004.txt")
            changed = services.ai_artifact_inventory(root, max_items=2, cursor=first["pagination"]["next_cursor"])
            self.assert_incomplete(changed)
            self.assertEqual(changed["observed_fate_counts"]["source_intake_recorded"], 1)
            fresh = services.ai_artifact_inventory(root, max_items=2)
            (root / "receipts/sources/not-a-plan.bin").write_bytes(b"do not read this ordinary body")
            changed = services.ai_artifact_inventory(root, max_items=2, cursor=fresh["pagination"]["next_cursor"])
            self.assert_incomplete(changed)

    def test_control_change_after_collection_is_rechecked_before_publication(self):
        for target in ("archive", "receipt"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp:
                root = self.archive(Path(tmp), 5)
                receipt = self.receipt(root, ".wom-scratch/nested/private-note-00004.txt", note="private_marker_A")
                original = services.ai_artifact_unmanaged_project_scratch_summary

                def mutate_after_collection(*args):
                    path = root / "archive.yml" if target == "archive" else receipt
                    before = path.stat()
                    old, new = ((b"Synthetic", b"Changed__") if target == "archive" else (b"private_marker_A", b"private_marker_B"))
                    path.write_bytes(path.read_bytes().replace(old, new))
                    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
                    return original(*args)

                with patch.object(services, "ai_artifact_unmanaged_project_scratch_summary", side_effect=mutate_after_collection):
                    result = services.ai_artifact_inventory(root, max_items=2)
                self.assert_incomplete(result)
                self.assertIn("ai_artifact_inventory_generation_changed_or_unavailable", result["blockers"])

    def test_malformed_receipts_never_disappear_as_unreviewed_or_zero(self):
        for content in (b"{", b"[]", b'{"source_kind":"ai_artifact","source_kind":"other"}', b'{"value":NaN}', b'{"archive_id":"different"}'):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as tmp:
                root = self.archive(Path(tmp))
                receipt = self.receipt(root, ".wom-scratch/nested/missing.txt")
                receipt.write_bytes(content)
                result = services.ai_artifact_inventory(root)
                self.assert_incomplete(result)
                self.assertIn("ai_artifact_inventory_intake_receipt_invalid_or_unavailable", result["blockers"])

    def test_receipt_control_size_limit_and_read_error_are_fixed_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp), 3)
            receipt = self.receipt(root, ".wom-scratch/nested/private-note-00002.txt")
            original = metadata._read_verified_control_bytes

            def unavailable(path, *args, **kwargs):
                if path == receipt:
                    raise OSError("private_lowercase_marker")
                return original(path, *args, **kwargs)

            with patch.object(metadata, "_read_verified_control_bytes", side_effect=unavailable):
                result = services.ai_artifact_inventory(root)
            self.assert_incomplete(result)
            self.assertNotIn("private_lowercase_marker", json.dumps(result))
            receipt.write_bytes(b"x" * (metadata.MAX_CONTROL_FILE_BYTES + 1))
            result = services.ai_artifact_inventory(root)
            self.assert_incomplete(result)

    def test_scan_limit_or_late_iterator_error_never_claims_complete_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp), 5)
            with patch.object(metadata, "MAX_ENTRIES_PER_ROOT", 2):
                result = services.ai_artifact_inventory(root)
            self.assert_incomplete(result)
            self.assertGreater(result["observed_candidate_count"], 0)
            original = metadata._scan_recursive_scope

            def failed(root, spec, **kwargs):
                if spec.root_id.startswith("ai_artifacts"):
                    raise OSError("private_path_secret_error")
                return original(root, spec, **kwargs)

            with patch.object(metadata, "_scan_recursive_scope", side_effect=failed):
                result = services.ai_artifact_inventory(root)
            self.assert_incomplete(result)
            self.assertNotIn("private_path_secret_error", json.dumps(result))

    def test_reparse_parent_is_never_enumerated_and_body_files_never_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp), 5)
            original_stat, original_open = metadata.os.lstat, metadata.os.open
            inspected = []

            def reparse(path):
                inspected.append(Path(path))
                info = original_stat(path)
                if Path(path) == root / ".wom-scratch":
                    values = {name: getattr(info, name) for name in dir(info) if name.startswith("st_")}
                    return SimpleNamespace(**(values | {"st_file_attributes": 0x400}))
                return info

            def forbid_body_open(path, *args, **kwargs):
                if Path(path).name != "archive.yml":
                    self.fail("ordinary artifact or unapproved control body opened")
                return original_open(path, *args, **kwargs)

            proxy = SimpleNamespace(**(vars(os) | {"lstat": reparse, "open": forbid_body_open}))
            with patch.object(metadata, "os", proxy):
                blocked = services.ai_artifact_inventory(root)
            self.assert_incomplete(blocked)
            self.assertNotIn(root / ".wom-scratch/nested", inspected)
            proxy = SimpleNamespace(**(vars(os) | {"open": forbid_body_open}))
            with patch.object(metadata, "os", proxy):
                valid = services.ai_artifact_inventory(root)
            self.assertTrue(valid["ok"], valid)
            self.assertFalse(valid["closed_actions"]["content_hashes_calculated"])

    def test_archive_metadata_failure_and_unsafe_root_never_echo_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            with patch.object(metadata._MetadataGeneration, "observe", side_effect=OSError("private_lowercase_marker")):
                with self.assertRaisesRegex(services.ArchiveServiceError, "^ai_artifact_inventory_archive_metadata_unavailable$"):
                    services.ai_artifact_inventory(root)
            result = services.ai_artifact_inventory(root, include_roots=["../private_marker"])
            self.assert_incomplete(result)
            self.assertNotIn("private_marker", json.dumps(result))

    def test_invalid_page_or_cursor_and_exact_empty_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            empty = services.ai_artifact_inventory(root)
            self.assertTrue(empty["ok"], empty)
            self.assertEqual(empty["total_candidate_count"], 0)
            self.assertTrue(empty["pagination"]["complete_listing"])
            for kwargs in ({"max_items": True}, {"max_items": 0}, {"cursor": "private_invalid_cursor"}):
                with self.subTest(kwargs=tuple(kwargs)):
                    self.assert_incomplete(services.ai_artifact_inventory(root, **kwargs))

    def test_public_cli_preserves_json_and_forwards_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp), 5)

            def run(cursor=None):
                args = ["ai-artifact-inventory", str(root), "--dry-run", "--max-items", "2", "--format", "json"]
                if cursor is not None:
                    args.extend(["--cursor", cursor])
                output, errors = io.StringIO(), io.StringIO()
                with redirect_stdout(output), redirect_stderr(errors):
                    code = archive_cli.main(args)
                self.assertEqual(errors.getvalue(), "")
                return code, json.loads(output.getvalue())

            code, first = run()
            self.assertEqual(code, 0)
            code, second = run(first["pagination"]["next_cursor"])
            self.assertEqual(code, 0)
            self.assertEqual(second["pagination"]["offset"], 2)
            self.assertEqual(first["pagination"]["snapshot_sha256"], second["pagination"]["snapshot_sha256"])


if __name__ == "__main__":
    unittest.main()
