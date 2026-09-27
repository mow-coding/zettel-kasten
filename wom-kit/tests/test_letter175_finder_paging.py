"""Exact private-name results stay on their verified generation across pages."""
from contextlib import closing, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from urllib.parse import urljoin

from wom_kit import archive_cli, private_objet_finder as finder
from . import test_v03298_private_objet_finder as fixture


class FinderPagingTests(unittest.TestCase):
    def test_private_alias_results_continue_after_live_projection_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = fixture._prepare_archive(Path(temporary), nonempty=False)
            rows, expected = [], set()
            for number in range(3):
                sha = hashlib.sha256(f"synthetic alias object {number}".encode()).hexdigest()
                oid = "sha256:" + sha
                expected.add(oid)
                rows.append({"object_id": oid, "sha256": sha, "logical_key": f"objects/sha256/{sha[:2]}/{sha}",
                    "locations": [{"provider": "synthetic"}], "provenance": {"source": "synthetic"}})
            (root / "objects/manifests/files.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            private = root / fixture.contract.PRIVATE_MANIFEST_PATH
            for row in rows:
                previous = private.read_bytes() if private.exists() else b""
                with patch.object(fixture, "OBJECT_ID", row["object_id"]), patch.object(fixture, "OBJECT_HEX", row["sha256"]), \
                        patch.object(fixture, "OBSERVATION", "sha256:" + hashlib.sha256(row["object_id"].encode()).hexdigest()):
                    fixture._install_private_authority(root)
                private.write_bytes(previous + private.read_bytes())
            authority = fixture.capture_private_objet_index_authority(root, fixture.ARCHIVE_ID)
            projection = fixture.generated_index._compile_private_objet_index_projection(authority.compiler_input)
            db = root / "db/archive-index.sqlite"
            db.parent.mkdir()
            with closing(sqlite3.connect(db)) as connection:
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("BEGIN IMMEDIATE")
                fixture.generated_index.install_private_objet_index_projection(connection, projection)
                connection.commit()

            def query(cursor=None, text="private-canary.hwpx"):
                args = fixture._finder_argv(root, text) + ["--limit", "1"]
                if cursor:
                    args += ["--cursor", cursor]
                output = io.StringIO()
                with redirect_stdout(output):
                    code = archive_cli.main(args)
                return code, json.loads(output.getvalue())

            code, first = query()
            self.assertEqual(code, 0, first)
            self.assertEqual(first["returned"], 1, first)
            self.assertEqual(first["distinct_object_count"], 3)
            self.assertTrue(finder.validate_private_objet_finder_result(first))
            schema = json.loads((Path(__file__).parents[1] / "schemas/private-objet-finder-result-v0.2.schema.json").read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            projection = json.loads((Path(__file__).parents[1] / "schemas/objet-safe-label-projection-v0.1.schema.json").read_text(encoding="utf-8"))
            registry = Registry().with_resources((key, Resource.from_contents(projection)) for key in ("objet-safe-label-projection-v0.1.schema.json", urljoin(schema["$id"], "objet-safe-label-projection-v0.1.schema.json"), projection["$id"]))
            validator = Draft202012Validator(schema, registry=registry)
            validator.validate(first)
            cursor = first["pagination"]["next_cursor"]
            # Change the live generated index; old cursor must not reclassify
            # healthy historical evidence as a current-source assertion.
            with closing(sqlite3.connect(db)) as connection:
                connection.execute("DELETE FROM objet_name_aliases")
                connection.commit()
            pages = [first]
            while cursor:
                code, page = query(cursor)
                self.assertEqual(code, 0, page)
                self.assertEqual(page["pagination"]["snapshot"], first["pagination"]["snapshot"])
                self.assertTrue(finder.validate_private_objet_finder_result(page))
                validator.validate(page)
                pages.append(page)
                cursor = page["pagination"]["next_cursor"]
            ids = [item["object_id"] for page in pages for item in page["results"]]
            self.assertEqual([page["returned"] for page in pages], [1, 1, 1])
            self.assertEqual(len(set(ids)), 3)
            self.assertEqual(set(ids), expected)
            code, rejected = query(first["pagination"]["next_cursor"], text="different.hwpx")
            self.assertEqual(code, 2)
            self.assertNotIn("different.hwpx", json.dumps(rejected))
            snapshot = root / "db/finder-snapshots" / (first["pagination"]["snapshot"] + ".sqlite")
            with snapshot.open("ab") as stream:
                stream.write(b"changed")
            self.assertEqual(query(first["pagination"]["next_cursor"])[0], 2)
