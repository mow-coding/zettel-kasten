"""Reject misleading performance evidence without running the large benchmark."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from types import SimpleNamespace


_SPEC = importlib.util.spec_from_file_location(
    "benchmark_installed_feedback", Path(__file__).parents[1] / "tools/benchmark_installed_feedback.py"
)
benchmark = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(benchmark)


def rows():
    return [
        {"label": label, "case": case, "sample": sample,
         "seconds": (8.0 if label == "baseline" else 3.0) + sample / 100,
         "exit_code": 0, "ok": True, "claims_count_correct": True, "expected_result": True,
         "official_launcher": True, "instrumented": False, "new_process": True}
        for case in benchmark.CASES for label in ("baseline", "candidate") for sample in range(11)
    ]


class InstalledBenchmarkEvidenceTests(unittest.TestCase):
    def test_claims_fixture_reuse_cannot_measure_index_dependent_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = benchmark.owned_root(Path(temporary) / "owned")
            for label in ("baseline", "candidate-claims-native"):
                (root / label).mkdir()
                (root / label / "preparation.json").write_text(json.dumps({
                    "supported_cases": ["exact-approval-claims"]}), encoding="utf-8")
            args = SimpleNamespace(work_dir=root, candidate_label="candidate-claims-native",
                                   case="zettel-edge", measurement_id="claims-native", repeat=10)
            with self.assertRaisesRegex(RuntimeError, "fixture_reuse_scope_invalid"):
                benchmark.measure(args)
            self.assertFalse((root / "claims-native-official-launcher-measurements.jsonl").exists())

    def test_focused_retest_does_not_claim_other_commands_or_accept_missing_samples(self):
        selected = [row for row in rows() if row["case"] == "exact-approval-claims"]
        result = benchmark.summarize(selected, cases=("exact-approval-claims",))
        self.assertEqual(set(result), {"exact-approval-claims"})
        with self.assertRaisesRegex(ValueError, "failed_or_samples_missing"):
            benchmark.summarize(selected)
        with self.assertRaisesRegex(ValueError, "failed_or_samples_missing"):
            benchmark.summarize(selected[:-1], cases=("exact-approval-claims",))

    def test_official_fresh_samples_and_explicit_first_observation(self):
        observed = list(reversed(rows()))
        result = benchmark.summarize(observed)
        for case in benchmark.CASES:
            self.assertEqual(result[case]["candidate"]["first_process_seconds"], 3.0)
            self.assertEqual(result[case]["candidate"]["repeat_new_process_p95_seconds"], 3.1)
            self.assertTrue(all(result[case]["goals"].values()))

    def test_missing_duplicate_failed_or_instrumented_sample_cannot_pass(self):
        defects = [
            lambda data: data.pop(),
            lambda data: data[1].update(sample=0),
            lambda data: data[1].update(exit_code=1),
            lambda data: data[1].update(ok=False),
            lambda data: data[1].update(expected_result=False),
            lambda data: data[1].update(official_launcher=False),
            lambda data: data[1].update(instrumented=True),
            lambda data: data[1].update(new_process=False),
            lambda data: data[1].update(seconds=float("nan")),
            lambda data: data[1].update(seconds=0),
            lambda data: data[-1].pop("claims_count_correct"),
            lambda data: data[-1].update(claims_count_correct=False),
        ]
        for defect in defects:
            with self.subTest(defect=defect):
                data = copy.deepcopy(rows())
                defect(data)
                with self.assertRaisesRegex(ValueError, "failed_or_samples_missing"):
                    benchmark.summarize(data)

    def test_regression_remains_a_failed_goal(self):
        data = rows()
        for row in data:
            if row["label"] == "candidate":
                row["seconds"] = 12.0
        result = benchmark.summarize(data)
        self.assertFalse(result[benchmark.CASES[0]]["goals"]["repeat_p95_at_most_5_seconds"])
        self.assertFalse(result[benchmark.CASES[0]]["goals"]["at_least_50_percent_reduction"])

    def test_claims_must_be_real_result_array_and_content_is_not_in_summary(self):
        for stdout in (b"[]", b'{"ok":true,"claims":1000}', b'{"ok":true,"claims":[]}'):
            observed = benchmark.observe(subprocess.CompletedProcess([], 0, stdout, b""), 1.0,
                                         label="candidate", case="exact-approval-claims", sample=0)
            self.assertFalse(observed["claims_count_correct"])
        content = {"ok": True, "claims": [{"synthetic_secret_marker": "private"}] * 1000}
        observed = benchmark.observe(subprocess.CompletedProcess([], 0, json.dumps(content).encode(), b""), 1.0,
                                     label="candidate", case="exact-approval-claims", sample=0)
        self.assertTrue(observed["claims_count_correct"])
        self.assertNotIn("synthetic_secret_marker", json.dumps(observed))

    def test_fast_blocked_or_noop_plan_is_not_a_successful_performance_sample(self):
        for result in ({"ok": True, "dry_run": True, "blockers": ["blocked"], "would_change": ["synthetic"]},
                       {"ok": True, "dry_run": True, "blockers": [], "would_change": [], "state": "ready"}):
            completed = subprocess.CompletedProcess([], 0, json.dumps(result).encode(), b"")
            observed = benchmark.observe(completed, .01, label="candidate", case="zettel-objet-link", sample=0)
            self.assertFalse(observed["expected_result"])

    def test_workspace_must_be_owned_and_paths_cannot_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "unrelated.txt").write_text("preserve")
            with self.assertRaisesRegex(RuntimeError, "not_empty_or_owned"):
                benchmark.owned_root(root)
            own = benchmark.owned_root(root / "task")
            self.assertEqual(benchmark.inside(own, own / "nested"), own / "nested")
            for forbidden in (root, own, own / "../sibling"):
                with self.assertRaisesRegex(RuntimeError, "outside_owned_workspace"):
                    benchmark.inside(own, forbidden)

    def test_fixture_fingerprint_detects_zet_claim_and_manifest_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "zettels").mkdir()
            claims = root / "profiles/local/exact-human-approvals/claims"
            claims.mkdir(parents=True)
            manifest = root / "objects/manifests/files.jsonl"
            manifest.parent.mkdir(parents=True)
            manifest.write_bytes(b'{"object_id":"synthetic"}\n')
            (root / "archive.yml").write_text("archive_id: synthetic")
            (root / ".gitignore").write_text("profiles/local/\n")
            zet = root / "zettels/synthetic.md"
            claim = claims / "synthetic.json"
            zet.write_text("synthetic original")
            claim.write_text("{}")
            counts = {"zettels": 1, "claims": 1, "objects": 1, "manifest_bytes": manifest.stat().st_size}
            initial = benchmark.fixture_fingerprint(root, expected_counts=counts)
            zet.write_text("synthetic revised")
            changed = benchmark.fixture_fingerprint(root, expected_counts=counts)
            self.assertNotEqual(initial["sha256"], changed["sha256"])
            claim.write_text('{"state":"changed"}')
            self.assertNotEqual(changed["sha256"], benchmark.fixture_fingerprint(root, expected_counts=counts)["sha256"])
            manifest.write_bytes(b"")
            with self.assertRaisesRegex(RuntimeError, "counts_mismatch"):
                benchmark.fixture_fingerprint(root, expected_counts=counts)


if __name__ == "__main__":
    unittest.main()
