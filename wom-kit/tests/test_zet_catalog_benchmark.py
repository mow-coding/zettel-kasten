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
                "5000",
                "--response-envelope-reserve-tokens",
                "2500",
                "--projection",
                "routed_reading",
                "--coverage-mode",
                "strict",
                "--order",
                "seeded_connection_walk",
                "--seed-index",
                "100",
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
        self.assertTrue(report["coverage"]["archive_wide_abstract_reading_claim_ready"])
        self.assertTrue(report["coverage"]["archive_wide_followup_resolution_ready"])
        self.assertTrue(report["abstract_coverage"]["all_required_first_reads_available"])
        self.assertTrue(report["identity_coverage"]["all_entries_uniquely_addressable"])
        self.assertEqual(report["fixture"]["projection"], "routed_reading")
        self.assertEqual(report["fixture"]["coverage_mode"], "strict")
        self.assertEqual(report["fixture"]["order_mode"], "seeded_connection_walk")
        self.assertEqual(report["order_evidence"]["seed_connected_prefix_count"], 120)
        self.assertEqual(report["order_evidence"]["fallback_component_count"], 0)
        self.assertTrue(report["order_evidence"]["item_route_evidence_in_routed_reading_projection"])
        self.assertEqual(report["order_evidence"]["item_route_evidence_count"], 120)
        self.assertTrue(report["order_evidence"]["all_nodes_preserved"])
        self.assertTrue(report["continuation_contract"]["duplicate_ids_distinguished_in_chain"])
        self.assertEqual(report["scan"]["frontmatter_files_scanned_across_pass"], 120)
        self.assertEqual(report["scan"]["path_metadata_checked_across_pass"], 240)
        self.assertEqual(report["scan"]["completion_revalidation_pages"], 1)
        self.assertGreater(report["scan"]["materialized_snapshot_pages"], 0)
        self.assertEqual(report["scan"]["cache_mode"], "process_local_ephemeral")
        self.assertFalse(report["scan"]["cache_persisted"])
        self.assertFalse(report["safety"]["real_archive_read"])
        self.assertFalse(report["safety"]["zet_bodies_read"])
        self.assertGreater(report["workload_estimate"]["scope"]["estimated_items_json_tokens"], 0)
        self.assertEqual(report["page_budget_observation"]["effective_items_token_budget"], 2500)
        self.assertLessEqual(report["page_budget_observation"]["max_page_estimated_items_json_tokens"], 2500)
        self.assertEqual(report["page_budget_observation"]["pages_over_requested_token_budget"], 0)
        self.assertLessEqual(report["page_budget_observation"]["max_page_estimated_service_result_tokens"], 5000)
        self.assertEqual(report["page_budget_observation"]["pages_over_requested_response_budget"], 0)
        self.assertEqual(report["page_budget_observation"]["pages_with_insufficient_envelope_reserve"], 0)
        self.assertEqual(
            report["workload_estimate"]["response"]["basis"],
            "compact_sorted_service_result_json_excluding_this_measurement",
        )


if __name__ == "__main__":
    unittest.main()
