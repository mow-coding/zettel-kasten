from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[1]


class DoctorProgressVolumeBenchmarkTests(unittest.TestCase):
    def test_synthetic_progress_keeps_compact_output_bounded(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(KIT_ROOT / "tools" / "benchmark_doctor_progress_volume.py"),
                "--source-count",
                "100",
                "--index-receipt-count",
                "1000",
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
        self.assertEqual(result["results"]["direct_compact"]["line_count"], 4)
        self.assertEqual(result["results"]["shared_runtime_compact"]["line_count"], 4)
        self.assertGreater(result["results"]["direct_verbose"]["line_count"], 400)
        self.assertGreaterEqual(result["comparison"]["shared_line_reduction_fraction"], 0.99)
        self.assertGreaterEqual(result["comparison"]["shared_byte_reduction_fraction"], 0.99)
        self.assertTrue(result["results"]["shared_runtime_compact"]["final_summary_present"])
        self.assertFalse(result["fixture"]["real_archive_read"])
        self.assertFalse(result["safety"]["files_written"])


if __name__ == "__main__":
    unittest.main()
