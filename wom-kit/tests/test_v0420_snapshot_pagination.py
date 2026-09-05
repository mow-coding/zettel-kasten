from __future__ import annotations

import base64
import json
import unittest

from wom_kit.snapshot_pagination import (
    SnapshotPager, SnapshotPaginationError, content_sha256,
)


class SnapshotPaginationTests(unittest.TestCase):
    def pager(self, items=None, *, generation="generation", query="query"):
        return SnapshotPager.build(
            items if items is not None else [{"ordinal": i} for i in range(5)],
            generation_sha256=content_sha256(generation), query_sha256=content_sha256(query),
        )

    def test_immutable_projection_visits_all_6773_items_without_global_limit(self):
        source = [{"ordinal": i, "state": "recorded" if i % 2 else "review"} for i in range(6773)]
        pager = self.pager(source)
        source[-1]["ordinal"] = -1
        cursor = None
        seen = []
        snapshots = set()
        while True:
            result = pager.page(page_size=127, cursor=cursor)
            page = result["pagination"]
            self.assertEqual(page["total_count"], 6773)
            self.assertEqual(page["offset"], len(seen))
            self.assertEqual(page["remaining_count"], 6773 - len(seen) - len(result["items"]))
            self.assertFalse(page["cursor_is_authority"])
            self.assertFalse(page["prior_pages_read_proven"])
            snapshots.add(page["snapshot_sha256"])
            seen.extend(item["ordinal"] for item in result["items"])
            if page["next_cursor"] is None:
                self.assertFalse(page["has_more"])
                self.assertFalse(page["complete_listing"])
                break
            cursor = page["next_cursor"]
        self.assertEqual(seen, list(range(6773)))
        self.assertEqual(len(snapshots), 1)
        result["items"][0]["ordinal"] = -2
        self.assertEqual(pager.page(page_size=6773)["items"][-1]["ordinal"], 6772)

    def test_cursor_rejects_query_generation_page_size_and_projection_changes(self):
        pager = self.pager()
        cursor = pager.page(page_size=2)["pagination"]["next_cursor"]
        for other, size, reason in (
            (self.pager(query="other"), 2, "query_changed"),
            (self.pager(generation="other"), 2, "generation_changed"),
            (self.pager([{ "ordinal": i } for i in range(6)]), 2, "generation_changed"),
            (pager, 3, "query_changed"),
        ):
            with self.subTest(reason=reason):
                with self.assertRaisesRegex(SnapshotPaginationError, "^snapshot_pagination_" + reason + "$"):
                    other.page(page_size=size, cursor=cursor)

    def test_cursor_is_strict_and_never_echoes_private_input(self):
        pager = self.pager()
        cursor = pager.page(page_size=2)["pagination"]["next_cursor"]
        decoded = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        private = "private_lowercase_marker"
        variants = [None, "", cursor + "=", private, True, 1, {"private": private}]
        variants.remove(None)  # None is the legitimate first-page request.
        for field, value in (("offset", True), ("offset", 1), ("offset", 4), ("page_size", 0), ("schema", private), (private, private)):
            tampered = dict(decoded)
            tampered[field] = value
            variants.append(base64.urlsafe_b64encode(json.dumps(tampered, sort_keys=True, separators=(",", ":")).encode()).decode().rstrip("="))
        for value in variants:
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(SnapshotPaginationError) as raised:
                    pager.page(page_size=2, cursor=value)
                self.assertEqual(str(raised.exception), "snapshot_pagination_cursor_invalid")
                self.assertNotIn(private, str(raised.exception))

    def test_empty_one_page_and_invalid_page_sizes(self):
        empty = self.pager([]).page(page_size=1)
        self.assertEqual(empty["items"], [])
        self.assertEqual(empty["pagination"]["remaining_count"], 0)
        self.assertTrue(empty["pagination"]["complete_listing"])
        self.assertIsNone(empty["pagination"]["next_cursor"])
        for value in (True, 0, -1, 1.5, "2", 2**63):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaisesRegex(SnapshotPaginationError, "^snapshot_pagination_input_invalid$"):
                    self.pager().page(page_size=value)


if __name__ == "__main__":
    unittest.main()
