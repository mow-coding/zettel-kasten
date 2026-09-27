import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from wom_kit.manifest_lookup import ManifestLookup
from wom_kit import archive_services as services


class ManifestLookupTests(unittest.TestCase):
    def test_generation_reuse_append_and_same_timestamp_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "objects/manifests/files.jsonl"
            path.parent.mkdir(parents=True)
            rows = [{"object_id": "sha256:" + format(i, "064x"), "synthetic": "before"} for i in range(23000)]
            path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            target = rows[-1]["object_id"]
            started = time.monotonic()
            for _ in range(8):
                expected = [row for row in services.load_manifest_records(root) if row.get("object_id") == target]
            before = time.monotonic() - started
            lookup = ManifestLookup(root)
            started = time.monotonic()
            for _ in range(8):
                self.assertEqual(list(lookup.rows(target)), expected)
            after = time.monotonic() - started
            self.assertEqual(lookup.observations()["parsed_rows"], 23000)
            self.assertEqual(lookup.observations()["unchanged_generation_reuses"], 7)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"object_id": target, "synthetic": "append"}) + "\n")
            self.assertEqual(len(lookup.rows(target)), 2)
            self.assertEqual(lookup.observations()["parsed_rows"], 23001)
            stamp = path.stat()
            path.write_bytes(path.read_bytes().replace(b'"before"', b'"edited"'))
            os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            self.assertEqual(lookup.rows(target)[0]["synthetic"], "edited")
            self.assertEqual(lookup.observations()["full_lookup_rebuilds"], 2)
            print(json.dumps({"synthetic_rows": 23000, "lookups": 8,
                "before_seconds": before, "after_seconds": after,
                "before_rows_parsed": 184000, "after_rows_parsed": 23000,
                "exact_bytes_checked_each_lookup": True}), flush=True)
