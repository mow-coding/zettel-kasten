"""Synthetic mixed search, update-during-pagination and cache integrity."""
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from wom_kit import archive_cli, archive_services as services, search_snapshots as snapshots


class SearchSnapshotTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        shutil.copytree(Path(__file__).resolve().parents[1] / "examples/fake-life-archive", self.root)
        self.query = "synthetic-pagination-needle"
        template = (self.root / "zettels/zet_20240504_fake_lunch_thought.md").read_text(encoding="utf-8")
        for index in range(100):
            raw = template.replace("zet_20240504_fake_lunch_thought", f"zet_20260927_page_{index:04d}")
            (self.root / f"zettels/zet_20260927_page_{index:04d}.md").write_text(raw + "\n" + self.query, encoding="utf-8")
        manifest = self.root / "objects/manifests/files.jsonl"
        sample = json.loads(manifest.read_text(encoding="utf-8").splitlines()[0])
        with manifest.open("a", encoding="utf-8") as stream:
            for index in range(100):
                payload = f"{self.query}-{index}".encode()
                digest = hashlib.sha256(payload).hexdigest()
                key = f"objects/sample/{self.query}-{index:04d}.txt"
                (self.root / key).write_bytes(payload)
                stream.write(json.dumps({**sample, "object_id": "sha256:" + digest, "sha256": digest,
                    "logical_key": key, "size_bytes": len(payload),
                    "locations": [{"provider": "local", "path": key, "availability": "available"}]}) + "\n")
        source_map = self.root / "source-maps/local_fake_sample_objects.jsonl"
        sample = json.loads(source_map.read_text(encoding="utf-8").splitlines()[0])
        with source_map.open("a", encoding="utf-8") as stream:
            for index in range(111):
                stream.write(json.dumps({**sample, "item_id": f"sourceitem:synthetic:{index:04d}",
                    "title": self.query, "relative_path": f"{self.query}-{index:04d}.txt"}) + "\n")
        indexed = services.index_archive(self.root)
        self.assertTrue(indexed["ok"], indexed)
        self.assertTrue(indexed["search_snapshot"]["ok"], indexed["search_snapshot"])

    def test_311_mixed_results_continue_from_same_generation_after_real_index_update(self):
        first = snapshots.search(self.root, self.query)
        self.assertEqual(first["total_matches"], 311)
        self.assertEqual(first["returned"], 100)
        self.assertEqual(first["matches_by_type"], dict(zettel=100, object=100, source_map=111))
        # B changes and rebuilds the real index after A has received page one.
        path = self.root / "zettels/zet_20260927_page_0000.md"
        path.write_text(path.read_text(encoding="utf-8").replace(self.query, "unrelated replacement"), encoding="utf-8")
        self.assertTrue(services.index_archive(self.root)["ok"])
        self.assertEqual(snapshots.search(self.root, self.query)["total_matches"], 310)
        page, rows, lengths = first, [], []
        while True:
            self.assertEqual(page["snapshot"], first["snapshot"])
            self.assertEqual(page["total_matches"], 311)
            rows.extend((row["type"], row["id"]) for row in page["results"])
            lengths.append(page["returned"])
            if page["next_cursor"] is None:
                break
            page = snapshots.search(self.root, self.query, cursor=page["next_cursor"])
        self.assertEqual(lengths, [100, 100, 100, 11])
        self.assertEqual(len(set(rows)), 311)
        self.assertTrue(page["page_sequence_complete"])
        self.assertFalse(page["complete"])  # last page alone is not all results
        self.assertFalse(page["remote_preservation_proven"])

    def test_dirty_live_index_keeps_old_search_and_filters_and_cursor_binding(self):
        first = snapshots.search(self.root, self.query, types=["source_map"], limit=60)
        self.assertEqual(first["total_matches"], 111)
        path = self.root / "zettels/zet_20260927_page_0000.md"
        path.write_text(path.read_text(encoding="utf-8") + "\nchanged", encoding="utf-8")
        historical = snapshots.search(self.root, self.query)
        self.assertTrue(historical["ok"])
        self.assertFalse(historical["refresh"]["live_source_freshness_checked"])
        self.assertEqual(historical["index_evidence"]["evidence_scope"], "captured_generation")
        self.assertEqual(historical["total_matches"], 311)
        second = snapshots.search(self.root, self.query, types=["source_map"], limit=60, cursor=first["next_cursor"])
        self.assertEqual(second["returned"], 51)
        for changes in ({"query": "another"}, {"types": ["object"]}, {"limit": 100}):
            options = dict(root=self.root, query=self.query, types=["source_map"], limit=60, cursor=first["next_cursor"])
            with self.assertRaisesRegex(services.ArchiveServiceError, "search_cursor_invalid"):
                snapshots.search(**{**options, **changes})

    def test_changed_snapshot_is_rejected_and_cli_returns_real_next_page(self):
        output = io.StringIO()
        with redirect_stdout(output):
            code = archive_cli.main(["search", str(self.root), self.query, "--type", "source_map", "--format", "json"])
        self.assertEqual(code, 0)
        first = json.loads(output.getvalue())
        output = io.StringIO()
        with redirect_stdout(output):
            code = archive_cli.main(["search", str(self.root), self.query, "--type", "source_map",
                "--cursor", first["next_cursor"], "--format", "json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["returned"], 11)
        path = self.root / "db/search-snapshots" / (first["snapshot"]["sha256"][7:] + ".sqlite")
        with path.open("ab") as stream:
            stream.write(b"synthetic corruption")
        with self.assertRaisesRegex(services.ArchiveServiceError, "search_snapshot_changed"):
            snapshots.search(self.root, self.query, types=["source_map"], cursor=first["next_cursor"])
