from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[1]


class LocalProfileSecretSafetyBenchmarkTests(unittest.TestCase):
    def test_synthetic_secret_safety_benchmark_preserves_scan_contract(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(KIT_ROOT / "tools" / "benchmark_local_profile_secret_safety.py"),
                "--file-count",
                "50",
                "--files-per-directory",
                "10",
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
        self.assertEqual(result["fixture"]["safe_json_file_count"], 50)
        self.assertEqual(result["fixture"]["expected_checked_file_count"], 51)
        self.assertFalse(result["fixture"]["real_archive_read"])
        self.assertEqual(result["result"]["error_count"], 0)
        self.assertEqual(result["result"]["warning_count"], 0)
        self.assertTrue(result["result"]["archive_text_scanned_for_secret_patterns"])
        self.assertFalse(result["safety"]["persistent_files_written"])
        self.assertTrue(result["safety"]["temporary_fixture_files_written"])


if __name__ == "__main__":
    unittest.main()
