"""CI reuse must bind an exact tree, latest run and successful aggregate."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("delivery_source_proof", Path(__file__).resolve().parents[1] / "tools/delivery_source_proof.py")
proof = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proof)


class DeliverySourceProofTests(unittest.TestCase):
    def fixture(self, *, tree="c" * 40, conclusion="success", job="success", merged=True):
        return [
            {"tree": {"sha": "c" * 40}},
            [{"merged_at": "2026-01-01" if merged else None, "merge_commit_sha": "a" * 40,
              "base": {"ref": "main"}, "head": {"sha": "b" * 40, "repo": {"full_name": "example/project"}}, "number": 1}],
            {"tree": {"sha": tree}},
            {"workflow_runs": [{"id": 2, "run_attempt": 3, "conclusion": conclusion, "html_url": "https://example.invalid/ci"},
                               {"id": 1, "conclusion": "success"}]},
            {"jobs": [{"name": "Required CI", "conclusion": job}]},
        ]

    def test_exact_tree_and_latest_attempt(self):
        with patch.object(proof, "gh_json", side_effect=self.fixture()):
            result = proof.verify("example/project", "a" * 40)
        self.assertEqual((result["ci_run"], result["ci_attempt"]), (2, 3))

    def test_mismatch_old_green_cancelled_or_missing_merge_never_reused(self):
        for changes in [{"tree": "d" * 40}, {"conclusion": "failure"},
                        {"conclusion": None}, {"job": "cancelled"}, {"merged": False}]:
            with self.subTest(changes=changes), patch.object(proof, "gh_json", side_effect=self.fixture(**changes)):
                with self.assertRaisesRegex(ValueError, "no_successful_exact_tree"):
                    proof.verify("example/project", "a" * 40)


if __name__ == "__main__":
    unittest.main()
