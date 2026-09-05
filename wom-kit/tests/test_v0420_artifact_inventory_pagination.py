from __future__ import annotations

import json
import io
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from wom_kit import artifact_lifecycle_inventory as inventory
from wom_kit import archive_cli


class ArtifactInventoryPaginationTests(unittest.TestCase):
    def test_public_cli_cursor_traverses_and_rejects_changed_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp), count=5)

            def run(cursor=None, output_format="json"):
                argv = ["artifact-lifecycle-inventory", str(root), "--dry-run", "--max-items", "2", "--format", output_format]
                if cursor is not None:
                    argv.extend(["--cursor", cursor])
                stdout, stderr = io.StringIO(), io.StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = archive_cli.main(argv)
                self.assertEqual(stderr.getvalue(), "")
                return code, json.loads(stdout.getvalue()) if output_format == "json" else stdout.getvalue()

            code, first = run()
            self.assertEqual(code, 0)
            cursor = first["pagination"]["next_cursor"]
            code, second = run(cursor)
            self.assertEqual(code, 0)
            self.assertEqual(second["pagination"]["offset"], 2)
            self.assertEqual(first["pagination"]["snapshot_sha256"], second["pagination"]["snapshot_sha256"])
            self.assertFalse({item["artifact_ref"] for item in first["items"]} & {item["artifact_ref"] for item in second["items"]})
            code, text = run(output_format="text")
            self.assertEqual(code, 0)
            self.assertIn("Next cursor: ", text)
            (root / "tmp" / "private-artifact-00004.txt").write_bytes(b"changed")
            code, rejected = run(cursor)
            self.assertEqual(code, 1)
            self.assertIn("snapshot_pagination_generation_changed", rejected["blockers"])
            self.assertEqual(rejected["items"], [])

    def make_archive(self, base: Path, *, count=0):
        root = base / "archive"
        root.mkdir()
        (root / "archive.yml").write_text("archive_id: archive:test\nname: Synthetic\ntype: personal\n", encoding="utf-8")
        if count:
            folder = root / "tmp"
            folder.mkdir()
            for index in range(count):
                (folder / f"private-artifact-{index:05d}.txt").write_bytes(b"synthetic private body")
        return root.resolve(strict=True)

    def test_real_metadata_inventory_traverses_all_6773_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp), count=6773)
            seen = []
            snapshots = set()
            cursor = None
            while True:
                result = inventory.artifact_lifecycle_inventory(root, max_items=2000, cursor=cursor)
                self.assertTrue(result["ok"], result["blockers"])
                page = result["pagination"]
                self.assertEqual(result["review_candidate_count"], 6773)
                self.assertEqual(page["total_count"], 6773)
                self.assertEqual(page["offset"], len(seen))
                snapshots.add(page["snapshot_sha256"])
                seen.extend(item["artifact_ref"] for item in result["items"])
                output = json.dumps(result)
                self.assertNotIn("private-artifact", output)
                self.assertNotIn("synthetic private body", output)
                self.assertNotIn(str(root), output)
                self.assertFalse(result["closed_actions"]["ordinary_artifact_bodies_read"])
                self.assertFalse(result["closed_actions"]["files_written"])
                cursor = page["next_cursor"]
                if cursor is None:
                    self.assertEqual(page["remaining_count"], 0)
                    break
            self.assertEqual(len(seen), 6773)
            self.assertEqual(len(set(seen)), 6773)
            self.assertEqual(len(snapshots), 1)

    def test_unseen_file_change_and_query_change_reject_old_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp), count=5)
            first = inventory.artifact_lifecycle_inventory(root, max_items=2)
            cursor = first["pagination"]["next_cursor"]
            changed_query = inventory.artifact_lifecycle_inventory(root, max_items=2, cursor=cursor, show_relative_paths=True)
            self.assertIn("snapshot_pagination_query_changed", changed_query["blockers"])
            self.assertEqual(changed_query["items"], [])
            (root / "tmp" / "private-artifact-00004.txt").write_bytes(b"changed unseen artifact")
            changed = inventory.artifact_lifecycle_inventory(root, max_items=2, cursor=cursor)
            self.assertFalse(changed["ok"])
            self.assertIn("snapshot_pagination_generation_changed", changed["blockers"])
            self.assertEqual(changed["items"], [])
            self.assertIsNone(changed["pagination"]["next_cursor"])
            self.assertIsNone(changed["pagination"]["remaining_count"])

    def test_directory_size_only_change_does_not_invalidate_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp), count=4)
            first = inventory.artifact_lifecycle_inventory(root, max_items=2)
            original = os.lstat

            def changed_directory_size(path):
                info = original(path)
                if not inventory.stat_module.S_ISDIR(info.st_mode):
                    return info
                attributes = {name: getattr(info, name) for name in dir(info) if name.startswith("st_")}
                attributes["st_size"] = int(info.st_size) + 4096
                return SimpleNamespace(**attributes)

            proxy = SimpleNamespace(**(vars(os) | {"lstat": changed_directory_size}))
            with patch.object(inventory, "os", proxy):
                second = inventory.artifact_lifecycle_inventory(root, max_items=2, cursor=first["pagination"]["next_cursor"])
            self.assertTrue(second["ok"], second["blockers"])
            self.assertEqual(first["pagination"]["snapshot_sha256"], second["pagination"]["snapshot_sha256"])
            self.assertEqual(second["pagination"]["remaining_count"], 0)

    def test_ordinary_artifact_bytes_are_never_opened_by_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp), count=4)
            original = os.open

            def forbid_artifact_open(path, *args, **kwargs):
                if Path(path).parent == root / "tmp":
                    self.fail("ordinary artifact bytes were opened")
                return original(path, *args, **kwargs)

            proxy = SimpleNamespace(**(vars(os) | {"open": forbid_artifact_open}))
            with patch.object(inventory, "os", proxy):
                result = inventory.artifact_lifecycle_inventory(root, max_items=2)
            self.assertTrue(result["ok"], result["blockers"])
            self.assertEqual(result["pagination"]["total_count"], 4)

    def test_invalid_page_request_never_issues_continuation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp), count=4)
            for value in (True, 0, 2001):
                with self.subTest(value=value):
                    result = inventory.artifact_lifecycle_inventory(root, max_items=value)
                    self.assertFalse(result["ok"])
                    self.assertIsNone(result["pagination"]["next_cursor"])
                    self.assertFalse(result["pagination"]["complete_listing"])

    def test_initial_metadata_failure_never_echoes_private_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp))
            with patch.object(
                inventory._MetadataGeneration, "observe",
                side_effect=OSError("private_lowercase_marker"),
            ):
                with self.assertRaisesRegex(
                    Exception, "^artifact_lifecycle_inventory_archive_metadata_unavailable$",
                ) as raised:
                    inventory.artifact_lifecycle_inventory(root)
            self.assertNotIn("private_lowercase_marker", str(raised.exception))

    def test_control_payload_hash_detects_same_summary_same_size_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp), count=5)
            manifest = root / "objects" / "manifests" / "files.jsonl"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({"object_id": "sha256:" + "a" * 64}) + "\n", encoding="utf-8")
            first = inventory.artifact_lifecycle_inventory(root, max_items=2)
            before = manifest.stat()
            manifest.write_text(json.dumps({"object_id": "sha256:" + "b" * 64}) + "\n", encoding="utf-8")
            os.utime(manifest, ns=(before.st_atime_ns, before.st_mtime_ns))
            changed = inventory.artifact_lifecycle_inventory(root, max_items=2, cursor=first["pagination"]["next_cursor"])
            self.assertEqual(first["object_manifest"], changed["object_manifest"])
            self.assertIn("snapshot_pagination_generation_changed", changed["blockers"])
            self.assertEqual(changed["items"], [])

    def test_change_after_earlier_scope_scan_invalidates_whole_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp), count=4)
            original = inventory._scan_never_touch_presence

            def mutate_after_prior_scope(*args, **kwargs):
                (root / "tmp" / "private-artifact-00003.txt").write_bytes(b"changed after its own recheck")
                return original(*args, **kwargs)

            with patch.object(inventory, "_scan_never_touch_presence", side_effect=mutate_after_prior_scope):
                result = inventory.artifact_lifecycle_inventory(root, max_items=2)
            self.assertFalse(result["ok"])
            self.assertFalse(result["coverage"]["complete"])
            self.assertIn("inventory_generation_changed_during_scan", result["blockers"])
            self.assertEqual(result["items"], [])
            self.assertEqual(result["pagination"]["observed_count"], 4)
            self.assertIsNone(result["pagination"]["total_count"])
            self.assertIsNone(result["pagination"]["next_cursor"])

    def test_incomplete_scan_never_claims_exact_end_or_total(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp), count=5)
            result = inventory.artifact_lifecycle_inventory(root, max_entries_per_root=2, max_items=1)
            self.assertFalse(result["ok"])
            page = result["pagination"]
            self.assertEqual(page["state"], "incomplete_generation")
            self.assertEqual(page["observed_count"], 2)
            self.assertEqual(page["returned_count"], 1)
            self.assertIsNone(page["remaining_count"])
            self.assertIsNone(page["total_count"])
            self.assertIsNone(page["has_more"])
            self.assertIsNone(page["next_cursor"])
            self.assertFalse(page["complete_listing"])

    def test_intermediate_reparse_parent_is_not_enumerated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp))
            parent = root / "workbench"
            child = parent / "ai-scratch"
            child.mkdir(parents=True)
            (child / "private-outside.txt").write_bytes(b"must not enumerate")
            original = os.lstat
            inspected = []

            def reparse_parent(path):
                inspected.append(Path(path))
                info = original(path)
                if Path(path) != parent:
                    return info
                attributes = {name: getattr(info, name) for name in dir(info) if name.startswith("st_")}
                attributes["st_file_attributes"] = 0x400
                return SimpleNamespace(**attributes)

            proxy = SimpleNamespace(**(vars(os) | {"lstat": reparse_parent}))
            with patch.object(inventory, "os", proxy):
                result = inventory.artifact_lifecycle_inventory(root)
            self.assertFalse(result["ok"])
            self.assertIn("ai_workbench_scratch_parent_link_or_reparse", result["blockers"])
            self.assertNotIn(child, inspected)
            self.assertNotIn("private-outside", json.dumps(result))
            self.assertIsNone(result["pagination"]["next_cursor"])


if __name__ == "__main__":
    unittest.main()
