"""Beta letter 180 (v0.4.59): the manifest projection rewrites only changed rows.

Each child step of a cleanup item rewrites one manifest row; the projection
used to delete and re-insert every row. The tables must still end exactly as
a full rewrite leaves them. Synthetic in-memory rows only.
"""
import hashlib
import json
import sqlite3
import unittest

from wom_kit import archive_services as services

SCHEMA = """
CREATE TABLE objects (object_id TEXT PRIMARY KEY, logical_key TEXT, mime TEXT, manifest_json TEXT);
CREATE TABLE objet_manifest_projection (record_ordinal INTEGER PRIMARY KEY, object_id TEXT NOT NULL,
  record_sha256 TEXT NOT NULL, record_json TEXT NOT NULL);
"""


def _records(rows):
    out = []
    for ordinal, record in enumerate(rows, start=1):
        record_json = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        out.append({"record_ordinal": ordinal, "record": record, "record_json": record_json,
                    "record_sha256": "sha256:" + hashlib.sha256((record_json + "\n").encode()).hexdigest()})
    return out


def _full_rewrite(records):
    """The pre-v0.4.59 behaviour, kept here as the reference."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    for projected in records:
        record = projected["record"]
        conn.execute("INSERT OR REPLACE INTO objects VALUES (?, ?, ?, ?)", (record.get("object_id"),
                     record.get("logical_key"), record.get("mime"), json.dumps(record, ensure_ascii=False, default=str)))
        conn.execute("INSERT INTO objet_manifest_projection VALUES (?, ?, ?, ?)", (projected["record_ordinal"],
                     record["object_id"], projected["record_sha256"], projected["record_json"]))
    return conn


def _tables(conn):
    return (sorted(conn.execute("SELECT * FROM objects")),
            sorted(conn.execute("SELECT * FROM objet_manifest_projection")))


def _row(number, **extra):
    return {"object_id": f"sha256:{number:064x}", "logical_key": f"objets/{number}", "mime": "text/plain", **extra}


class IncrementalProjectionTests(unittest.TestCase):
    def check(self, before, after):
        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA)
        services._write_manifest_projection_rows(conn, _records(before))
        self.assertEqual(_tables(conn), _tables(_full_rewrite(_records(before))))
        services._write_manifest_projection_rows(conn, _records(after))
        self.assertEqual(_tables(conn), _tables(_full_rewrite(_records(after))))

    def test_one_row_rewritten_in_place(self):
        before = [_row(n) for n in range(50)]
        after = list(before)
        after[17] = _row(17, local_location={"state": "offloaded"})
        self.check(before, after)

    def test_appended_and_removed_rows(self):
        before = [_row(n) for n in range(10)]
        self.check(before, before + [_row(10), _row(11)])
        self.check(before, before[:6])

    def test_duplicate_object_rows_keep_the_last_record(self):
        before = [_row(1), _row(2), _row(1, note="second")]
        self.check(before, [_row(1), _row(2), _row(1, note="changed")])
        self.check(before, [_row(1, note="first"), _row(2), _row(3)])

    def test_key_order_only_change_matches_the_full_rewrite(self):
        record = _row(5)
        reordered = {"mime": record["mime"], "logical_key": record["logical_key"], "object_id": record["object_id"]}
        self.check([record], [reordered])

    def test_inconsistent_stored_tables_are_corrected(self):
        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA)
        conn.execute("INSERT INTO objects VALUES ('sha256:stale', NULL, NULL, '{}')")
        conn.execute("INSERT INTO objet_manifest_projection VALUES (99, 'sha256:stale', 'x', '{}')")
        rows = [_row(n) for n in range(3)]
        services._write_manifest_projection_rows(conn, _records(rows))
        self.assertEqual(_tables(conn), _tables(_full_rewrite(_records(rows))))


if __name__ == "__main__":
    unittest.main()
