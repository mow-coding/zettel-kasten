from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


KIT_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_SENTINELS = (
    "LETTER148_PRIVATE_TITLE_DO_NOT_ECHO",
    "LETTER148_PRIVATE_BODY_DO_NOT_ECHO",
    "letter148-private-path-do-not-echo.md",
)


class DoctorLetter148ScaleBenchmarkTests(unittest.TestCase):
    def test_reduced_fixture_exercises_operational_and_deep_contracts(self) -> None:
        benchmark_path = (
            KIT_ROOT / "tools" / "benchmark_doctor_letter148_scale.py"
        )
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                str(benchmark_path),
                "--reduced",
                "--format",
                "json",
            ],
            cwd=KIT_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        for sentinel in PRIVATE_SENTINELS:
            self.assertNotIn(sentinel, completed.stdout)
            self.assertNotIn(sentinel, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertTrue(result["ok"])
        self.assertEqual(result["profile"], "normal-suite-reduced")
        self.assertEqual(
            result["fixture"],
            {
                "fixture_generation_excluded_from_doctor_timing": True,
                "fixture_generation_seconds": result["fixture"][
                    "fixture_generation_seconds"
                ],
                "mint_receipts": 5,
                "object_manifest_rows": 31,
                "profile": "normal-suite-reduced",
                "retired_receipts": 6,
                "unique_objets": 31,
                "zettels": 20,
            },
        )

        operational = result["operational_doctor"]
        self.assertTrue(operational["ok"])
        self.assertTrue(all(operational["checks"].values()))
        self.assertEqual(
            operational["instrumentation"]["object_stable_hash_calls"],
            0,
        )
        self.assertEqual(
            operational["instrumentation"][
                "object_manifest_parse_passes"
            ],
            1,
        )
        self.assertLessEqual(
            operational["timing_seconds"]["first_status"],
            2.0,
        )
        self.assertLessEqual(
            operational["timing_seconds"]["maximum_status_gap"],
            10.0,
        )
        self.assertFalse(any(operational["privacy"].values()))

        deep = result["deep_full_doctor"]
        self.assertTrue(deep["ok"])
        self.assertTrue(all(deep["checks"].values()))
        self.assertLessEqual(
            deep["timing_seconds"]["doctor_deep_full"],
            180.0,
        )
        self.assertLessEqual(
            deep["timing_seconds"]["first_status"],
            2.0,
        )
        self.assertLessEqual(
            deep["timing_seconds"]["maximum_status_gap"],
            10.0,
        )
        self.assertEqual(deep["stable_hash_calls"], 31)
        self.assertEqual(deep["unique_paths_hashed"], 31)
        self.assertEqual(deep["maximum_hashes_for_one_path"], 1)
        self.assertEqual(
            deep["instrumentation"]["object_manifest_parse_passes"],
            1,
        )
        self.assertFalse(any(deep["privacy"].values()))


if __name__ == "__main__":
    unittest.main()
