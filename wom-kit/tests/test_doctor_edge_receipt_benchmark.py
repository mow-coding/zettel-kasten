from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[1]


class DoctorEdgeReceiptBenchmarkTests(unittest.TestCase):
    def test_synthetic_benchmark_indexes_all_names_but_opens_only_target_receipt(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(KIT_ROOT / "tools" / "benchmark_doctor_edge_receipt_index.py"),
                "--receipt-count",
                "25",
                "--target-index",
                "8",
                "--format",
                "json",
            ],
            cwd=KIT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertTrue(result["ok"])
        self.assertEqual(result["fixture"]["edge_receipt_count"], 25)
        self.assertEqual(result["fixture"]["source_group_count"], 25)
        self.assertEqual(result["result"]["targeted_receipt_documents_opened"], 1)
        self.assertEqual(result["result"]["doctor_index_build_count"], 1)
        self.assertEqual(result["result"]["doctor_target_load_count"], 1)
        self.assertTrue(result["result"]["second_lookup_used_cache"])
        self.assertFalse(result["result"]["full_receipt_corpus_opened"])
        self.assertFalse(result["safety"]["real_archive_read"])
        self.assertFalse(result["safety"]["files_persisted"])


if __name__ == "__main__":
    unittest.main()
