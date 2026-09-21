"""Synthetic classification and aggregate-result regression cases."""
import importlib.util
from pathlib import Path
import unittest
import subprocess
import tempfile

spec = importlib.util.spec_from_file_location("ci_change_policy", Path(__file__).resolve().parents[1] / "tools" / "ci_change_policy.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class CIChangePolicyTests(unittest.TestCase):
    def test_only_explicit_development_docs_are_light(self):
        paths = ["CONTRIBUTING.md", "wom-kit/docs/development/README.md", "meeting-minutes/synthetic-evidence.md"]
        self.assertEqual(policy.classify(paths, event="pull_request"), "docs")
        for path in ["README.md", "wom-kit/templates/runtime/AGENTS.md", ".github/workflows/ci.yml", "wom-kit/src/wom_kit/archive_cli.py", "unknown.md", "wom-kit/docs/development/tool.py", "wom-kit/docs/development/../releases/test.md"]:
            self.assertEqual(policy.classify(paths + [path], event="pull_request"), "full", path)

    def test_empty_unknown_or_manual_requests_are_full(self):
        for event in ["pull_request", "workflow_dispatch", "unknown"]:
            self.assertEqual(policy.classify([], event=event), "full")
        self.assertEqual(policy.classify(["CLAUDE.md"], event="workflow_dispatch"), "full")

    def test_documentation_skips_are_exact_not_blanket_success(self):
        results = {name: {"result": "skipped"} for name in policy.HEAVY_JOBS}
        results.update({"classify": {"result": "success"}, "gate": {"result": "success"}})
        self.assertEqual(policy.check_results("docs", results), [])
        for name in results:
            for state in ["failure", "cancelled", None]:
                changed = {**results, name: {"result": state}}
                self.assertIn(name, policy.check_results("docs", changed))
            missing = dict(results); del missing[name]
            self.assertIn(name, policy.check_results("docs", missing))
        self.assertEqual(set(policy.check_results("full", results)), set(policy.HEAVY_JOBS))

    def test_full_requires_every_job_and_rejects_unknown_lane(self):
        results = {name: {"result": "success"} for name in ["classify", "gate", *policy.HEAVY_JOBS]}
        self.assertEqual(policy.check_results("full", results), [])
        self.assertEqual(policy.check_results("", results), ["invalid_lane"])
        self.assertTrue(policy.check_results("full", {}))
        self.assertIn("new_unclassified_job", policy.check_results("full", {**results, "new_unclassified_job": {"result": "failure"}}))

    def test_real_git_rename_cannot_hide_deleted_product_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            def git(*args):
                return subprocess.check_output(["git", *args], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
            git("init", "-q")
            git("config", "user.name", "synthetic-test")
            git("config", "user.email", "synthetic@example.invalid")
            source = root / "product.py"
            source.write_text("print('synthetic')\n", encoding="utf-8")
            git("add", "--", "product.py")
            git("commit", "-qm", "synthetic source")
            base = git("rev-parse", "HEAD")
            source.rename(root / "CONTRIBUTING.md")
            git("add", "--", "product.py", "CONTRIBUTING.md")
            git("commit", "-qm", "synthetic rename")
            paths = policy.changed_paths(base, git("rev-parse", "HEAD"), cwd=root)
            self.assertEqual(paths, ["CONTRIBUTING.md", "product.py"])
            self.assertEqual(policy.classify(paths, event="pull_request"), "full")


if __name__ == "__main__":
    unittest.main()
