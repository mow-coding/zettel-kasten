from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest import mock


KIT_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_PATH = KIT_ROOT / "tools" / "benchmark_doctor_letter148_scale.py"


class DoctorPayloadFixtureContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.benchmark = runpy.run_path(str(BENCHMARK_PATH))

    def test_historical_count_fixture_remains_tiny_and_reports_that_fact(self) -> None:
        benchmark = self.benchmark
        with tempfile.TemporaryDirectory(prefix="wom-count-fixture-contract-") as tmp:
            root = Path(tmp) / "archive"
            fixture = benchmark["build_fixture"](
                root, benchmark["REDUCED_PROFILE"]
            )
            payload = benchmark["describe_fixture_payload"](root)
        self.assertEqual(fixture["unique_objets"], 31)
        self.assertEqual(payload["object_total_bytes"], 31 * 30)
        self.assertEqual(
            payload["object_size_distribution"], [{"bytes": 30, "count": 31}]
        )
        self.assertEqual(payload["independent_mint_source_count"], 2)
        self.assertEqual(payload["independent_mint_snapshot_count"], 2)
        self.assertEqual(payload["canonical_file_count"], 19)
        self.assertEqual(payload["inbox_file_count"], 1)
        self.assertIn("not a reproduction", payload["claim_boundary"])

    def test_mixed_fixture_has_deterministic_bytes_and_independent_evidence(self) -> None:
        benchmark = self.benchmark
        profile = benchmark["mixed_payload_profile"](benchmark["REDUCED_PROFILE"])
        with tempfile.TemporaryDirectory(prefix="wom-mixed-fixture-contract-") as tmp:
            first = Path(tmp) / "first"
            second = Path(tmp) / "second"
            for root in (first, second):
                fixture = benchmark["build_fixture"](root, profile)
                self.assertEqual(fixture["zettels"], profile.zettels)
            payload = benchmark["describe_fixture_payload"](first)
            self.assertEqual(payload, benchmark["describe_fixture_payload"](second))
            self.assertEqual(
                payload["independent_mint_source_count"], profile.mint_receipts
            )
            self.assertEqual(
                payload["independent_mint_snapshot_count"], profile.mint_receipts
            )
            self.assertEqual(payload["object_total_bytes"], 500_736)
            self.assertEqual(payload["canonical_file_count"], 15)
            self.assertEqual(payload["inbox_file_count"], 5)
            self.assertEqual(
                payload["canonical_file_count"] + payload["inbox_file_count"],
                profile.zettels,
            )
            self.assertGreaterEqual(payload["canonical_max_bytes"], 16_384)
            self.assertGreater(
                payload["canonical_max_bytes"], payload["canonical_min_bytes"]
            )
            for path in (first / "objects" / "sha256").glob("*/*"):
                raw = path.read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), path.name)
                self.assertEqual(raw, (second / path.relative_to(first)).read_bytes())
            for path in (first / "receipts" / "mint").glob("*.mint.json"):
                receipt = json.loads(path.read_text(encoding="utf-8"))
                snapshot = first / receipt["snapshot"]["path"]
                source = first / receipt["source"]["path"]
                snapshot_frontmatter, _ = benchmark["archive_services"].require_readable_zettel_content(
                    snapshot
                )
                target_frontmatter, _ = benchmark["archive_services"].require_readable_zettel_content(
                    first / receipt["target"]["path"]
                )
                self.assertEqual(snapshot_frontmatter["id"], receipt["zettel"]["id"])
                self.assertEqual(target_frontmatter["id"], receipt["zettel"]["id"])
                if source.exists():
                    self.assertEqual(source.read_bytes(), snapshot.read_bytes())
                self.assertEqual(
                    hashlib.sha256(snapshot.read_bytes()).hexdigest(),
                    receipt["source"]["sha256"],
                )

    def test_full_mixed_profile_keeps_historical_cardinalities(self) -> None:
        full = self.benchmark["FULL_PROFILE"]
        mixed = self.benchmark["mixed_payload_profile"](full)
        self.assertEqual(
            (
                mixed.unique_objets,
                mixed.zettels,
                mixed.mint_receipts,
                mixed.retired_receipts,
            ),
            (22_441, 8_612, 3_345, 3_346),
        )
        self.assertEqual(
            replace(
                mixed,
                name=full.name,
                object_sizes=full.object_sizes,
                body_sizes=full.body_sizes,
                independent_mint_sources=False,
            ),
            full,
        )

    def test_real_mixed_doctor_reports_byte_work_and_preserves_operational_budget(self) -> None:
        benchmark = self.benchmark
        profile = benchmark["mixed_payload_profile"](benchmark["REDUCED_PROFILE"])
        report = benchmark["run_benchmark"](
            profile, deep_regression_budget_seconds=0.000001
        )
        self.assertFalse(report["ok"])
        self.assertTrue(report["operational_doctor"]["ok"])
        self.assertEqual(report["operational_doctor"]["error_code_counts"], {})
        self.assertFalse(
            report["deep_full_doctor"]["checks"][
                "completed_within_configured_regression_budget"
            ]
        )
        self.assertEqual(report["budgets"]["operational_seconds"], 180.0)
        self.assertFalse(report["budgets"]["deep_budget_is_client_archive_sla"])
        deep = report["deep_full_doctor"]
        self.assertEqual(deep["byte_throughput"]["object_total_bytes"], 500_736)
        self.assertTrue(deep["byte_throughput"]["complete_verified_pass"])
        self.assertGreater(
            deep["byte_throughput"]["object_bytes_per_whole_doctor_second"], 0
        )
        self.assertEqual(deep["stable_hash_calls"], profile.unique_objets)
        self.assertEqual(deep["progress"]["timing_basis"], "observed_stderr_delivery")
        for sentinel in benchmark["PRIVATE_SENTINELS"]:
            self.assertNotIn(sentinel, json.dumps(report))

    def test_corrupt_payload_cannot_report_complete_verified_throughput(self) -> None:
        benchmark = self.benchmark
        with tempfile.TemporaryDirectory(prefix="wom-corrupt-byte-fixture-") as tmp:
            root = Path(tmp) / "archive"
            benchmark["build_fixture"](root, benchmark["REDUCED_PROFILE"])
            path = next((root / "objects" / "sha256").glob("*/*"))
            path.write_bytes(b"x" * path.stat().st_size)
            deep = benchmark["run_deep_full_doctor"](
                root, expected_objets=31, expected_object_bytes=31 * 30
            )
        self.assertFalse(deep["ok"])
        self.assertEqual(deep["error_code_counts"], {"local_object_sha_mismatch": 1})
        self.assertFalse(deep["byte_throughput"]["complete_verified_pass"])
        self.assertIsNone(
            deep["byte_throughput"]["object_bytes_per_whole_doctor_second"]
        )

    def test_progress_delivery_detects_delayed_self_reported_zero(self) -> None:
        capture_class = self.benchmark["_TimedProgressCapture"]
        forwarded = io.StringIO()
        capture = capture_class(100.0, forwarded)
        with mock.patch.object(
            self.benchmark["time"], "perf_counter", side_effect=[103.0, 115.0]
        ):
            capture.write("[doctor] elapsed=0.0s stage=start\n")
            capture.write("[doctor] elapsed=1.0s stage=read\n")
        self.assertEqual(capture.status_times, [3.0, 15.0])
        self.assertEqual(forwarded.getvalue(), capture.getvalue())
        self.assertEqual(
            self.benchmark["_maximum_status_gap"](
                capture.status_times, 116.0 - 100.0
            ),
            12.0,
        )

    def test_fixture_heartbeat_is_closed_before_measured_doctor_dispatch(self) -> None:
        benchmark = self.benchmark
        reporters = []

        class FakeReporter:
            def __init__(self, *_args, **_kwargs):
                self.active = True
                reporters.append(self)

            def progress(self, *_args):
                pass

            def close(self):
                self.active = False

        def measured_doctor(*_args, **_kwargs):
            self.assertFalse(any(reporter.active for reporter in reporters))
            return {"ok": True}

        with (
            mock.patch.object(
                benchmark["archive_cli"], "CommandProgressReporter", FakeReporter
            ),
            mock.patch.dict(
                benchmark["run_benchmark"].__globals__,
                {
                    "build_fixture": lambda *_args, **_kwargs: {},
                    "describe_fixture_payload": lambda _root: {"object_total_bytes": 0},
                    "run_operational_doctor": measured_doctor,
                    "run_deep_full_doctor": measured_doctor,
                },
            ),
        ):
            report = benchmark["run_benchmark"](
                benchmark["REDUCED_PROFILE"], progress_output=io.StringIO()
            )
        self.assertTrue(report["ok"])
        self.assertEqual(len(reporters), 2)
        self.assertFalse(any(reporter.active for reporter in reporters))

    def test_cli_rejects_invalid_deep_budgets(self) -> None:
        for value in ("0", "-1", "nan", "inf"):
            with (
                self.subTest(value=value),
                redirect_stderr(io.StringIO()),
                redirect_stdout(io.StringIO()),
            ):
                with self.assertRaises(SystemExit) as raised:
                    self.benchmark["main"](
                        ["--reduced", "--deep-regression-budget-seconds", value]
                    )
                self.assertEqual(raised.exception.code, 2)

    def test_unexpected_failure_reports_coordinates_not_exception_values(self) -> None:
        benchmark = self.benchmark
        stdout = io.StringIO()
        private_text = " ".join(benchmark["PRIVATE_SENTINELS"])

        def fail(*_args, **_kwargs):
            private_local = private_text
            raise IndexError(private_local)

        with (
            mock.patch.dict(benchmark["main"].__globals__, {"run_benchmark": fail}),
            redirect_stdout(stdout),
            redirect_stderr(io.StringIO()),
        ):
            status = benchmark["main"](["--reduced", "--format", "json"])
        result = json.loads(stdout.getvalue())
        self.assertEqual(status, 1)
        self.assertEqual(result["reason_code"], "benchmark_internal_error")
        diagnostic = result["exception_diagnostics"]
        self.assertEqual(diagnostic["exception_type"], "IndexError")
        self.assertTrue(diagnostic["known_source_frames"])
        for frame in diagnostic["known_source_frames"]:
            self.assertEqual(frame["source"], "tools/benchmark_doctor_letter148_scale.py")
            self.assertEqual(frame["function"], "main")
            self.assertIsInstance(frame["line"], int)
        for sentinel in benchmark["PRIVATE_SENTINELS"]:
            self.assertNotIn(sentinel, stdout.getvalue())
        self.assertNotIn(str(BENCHMARK_PATH), stdout.getvalue())
        self.assertFalse(diagnostic["exception_text_emitted"])
        self.assertFalse(diagnostic["locals_emitted"])
        self.assertFalse(diagnostic["absolute_paths_emitted"])


if __name__ == "__main__":
    unittest.main()
