from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[1]


class ZetCatalogBenchmarkTests(unittest.TestCase):
    def test_synthetic_benchmark_completes_without_duplicate_or_persisted_fixture(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(KIT_ROOT / "tools" / "benchmark_zet_catalog.py"),
                "--zet-count",
                "120",
                "--page-size",
                "25",
                "--abstract-chars",
                "80",
                "--max-estimated-tokens",
                "2000",
                "--projection",
                "reading",
                "--coverage-mode",
                "strict",
                "--format",
                "json",
            ],
            cwd=KIT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["ok"])
        self.assertTrue(report["coverage"]["complete"])
        self.assertEqual(report["coverage"]["collected_count"], 120)
        self.assertEqual(report["coverage"]["unique_count"], 120)
        self.assertTrue(report["coverage"]["archive_wide_coverage_claim_ready"])
        self.assertEqual(report["fixture"]["projection"], "reading")
        self.assertEqual(report["fixture"]["coverage_mode"], "strict")
        self.assertEqual(report["scan"]["frontmatter_files_scanned_across_pass"], 120)
        self.assertEqual(report["scan"]["path_metadata_checked_across_pass"], 240)
        self.assertEqual(report["scan"]["completion_revalidation_pages"], 1)
        self.assertGreater(report["scan"]["materialized_snapshot_pages"], 0)
        self.assertEqual(report["scan"]["cache_mode"], "process_local_ephemeral")
        self.assertFalse(report["scan"]["cache_persisted"])
        self.assertFalse(report["safety"]["real_archive_read"])
        self.assertFalse(report["safety"]["zet_bodies_read"])
        self.assertGreater(report["workload_estimate"]["scope"]["estimated_items_json_tokens"], 0)
        self.assertLessEqual(report["page_budget_observation"]["max_page_estimated_items_json_tokens"], 2000)
        self.assertEqual(report["page_budget_observation"]["pages_over_requested_token_budget"], 0)


if __name__ == "__main__":
    unittest.main()
