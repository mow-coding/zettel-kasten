"""Synthetic title census: complete pages, explicit unknowns, private locators."""
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from wom_kit import title_diagnostics as module


class TitleDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="wom-title-diagnostics-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "archive"
        shutil.copytree(Path(__file__).parents[1] / "examples/fake-life-archive", self.root)

    def zet(self, number, title="Ordinary synthetic title", status="canonical"):
        path = self.root / "zettels" / f"zet_20260928_diag_{number}.md"
        path.write_text(f"---\nid: zet_20260928_diag_{number}\nstatus: {status}\ntitle: '{title}'\nkind: note\n---\nSynthetic body.\n", encoding="utf-8")
        return path

    def test_more_than_old_limit_paginate_without_live_scan_or_generation_churn(self):
        for n in range(601):
            self.zet(n, f"{n:032x}")
        first = module.publish(self.root)
        snapshot = first["snapshot_ref"]
        seen, cursor = set(), None
        with patch.object(module.services, "zet_catalog_entries", side_effect=AssertionError("live scan during page query")):
            while True:
                result = module.query(self.root, snapshot_ref=snapshot, page_size=79, cursor=cursor, state="attention")
                for row in result["items"]:
                    self.assertNotIn(row["item_ref"], seen)
                    seen.add(row["item_ref"])
                cursor = result["pagination"]["next_cursor"]
                if not cursor:
                    break
        self.assertGreaterEqual(len(seen), 601)
        self.zet("new", "d" * 32)
        second = module.publish(self.root)
        self.assertNotEqual(snapshot, second["snapshot_ref"])
        self.assertEqual(module.query(self.root, snapshot_ref=snapshot)["counts"], first["counts"])

    def test_unjudged_items_have_opaque_identity_reason_and_private_locator(self):
        self.zet("empty", "")
        redacted = self.zet("redacted", "Hidden synthetic title", "redacted")
        bad = self.root / "zettels/zet_20260928_diag_bad.md"
        bad.write_text("---\nid: [\n---\nUnparseable synthetic frontmatter.\n", encoding="utf-8")
        module.publish(self.root)
        result = module.query(self.root, state="not_judged")
        reasons = {reason for row in result["items"] for reason in row["reason_codes"]}
        self.assertIn("title_missing_or_empty", reasons)
        self.assertIn("frontmatter_unreadable", reasons)
        self.assertIn("redacted_not_judged", reasons)
        rendered = str(result)
        self.assertNotIn("Hidden synthetic title", rendered)
        self.assertNotIn(str(self.root), rendered)
        details = module.private_report(self.root)["items"]
        self.assertEqual(len(details), result["counts"].get("not_judged", 0) + result["counts"].get("readable", 0) + result["counts"].get("attention", 0))
        self.assertTrue(any(row["relative_path"].endswith(redacted.name) and row["title"] is None for row in details.values()))

    def test_marker_rule_is_advisory_and_never_changes_normal_title(self):
        path = self.zet("marker", "WORKITEM: comparison pending")
        ordinary = self.zet("ordinary", "How work items affect attention")
        before = (path.read_bytes(), ordinary.read_bytes())
        module.publish(self.root, rules=[{"rule_id": "workitem", "match": "prefix", "value": "WORKITEM:"}])
        rows = module.query(self.root, state="attention")["items"]
        self.assertEqual(sum("configured_marker:workitem" in row["signals"] for row in rows), 1)
        self.assertEqual(before, (path.read_bytes(), ordinary.read_bytes()))

    def test_malformed_rule_is_fixed_domain_error(self):
        for key in ("rule_id", "match", "value"):
            rule = {"rule_id": "synthetic", "match": "prefix", "value": "Synthetic"}
            rule[key] = ["synthetic-private-value"]
            with self.subTest(field=key), self.assertRaisesRegex(module.services.ArchiveServiceError, "^title_diagnostics_rules_invalid$"):
                module._rules([rule])

    def test_no_generation_is_explicit_and_read_has_no_side_effect(self):
        before = set(self.root.rglob("*"))
        with self.assertRaisesRegex(Exception, "generation_missing_run_index"):
            module.query(self.root)
        self.assertEqual(before, set(self.root.rglob("*")))


    def test_index_snapshot_includes_quarantine_without_second_filesystem_census(self):
        from wom_kit import archive_services as services, search_snapshots
        self.zet("empty", "")
        self.zet("redacted", "Never disclosed", "redacted")
        broken = self.root / "zettels/zet_20260928_diag_broken.md"
        broken.write_text("---\nid: [\n---\nBroken synthetic frontmatter.\n", encoding="utf-8")
        services.index_archive(self.root)
        source = search_snapshots.publish(self.root)
        self.assertFalse(source["ok"], source)  # quarantine cannot become search authority
        connection = services.connect_archive_index(self.root / services.INDEX_RELATIVE_PATH, row_factory=True)
        try:
            rows = [dict(row) for row in connection.execute("SELECT path,title,status,frontmatter_json FROM zettels WHERE path LIKE 'zettels/%' ORDER BY path")]
        finally:
            connection.close()
        with patch.object(module.services, "zet_catalog_entries", side_effect=AssertionError("second filesystem census")):
            generated = module.publish(self.root, index_rows=rows,
                index_diagnostics=[{"path": "zettels/zet_20260928_diag_broken.md", "code": "frontmatter_yaml_error"}])
            again = module.publish(self.root, index_rows=rows,
                index_diagnostics=[{"path": "zettels/zet_20260928_diag_broken.md", "code": "frontmatter_yaml_error"}])
        self.assertEqual(generated["snapshot_ref"], again["snapshot_ref"])
        report = module.query(self.root, snapshot_ref=generated["snapshot_ref"], state="not_judged")
        reasons = {reason for row in report["items"] for reason in row["reason_codes"]}
        self.assertTrue({"frontmatter_unreadable", "redacted_not_judged", "title_missing_or_empty"} <= reasons)
        self.assertNotIn("Never disclosed", str(report))


if __name__ == "__main__":
    unittest.main()
