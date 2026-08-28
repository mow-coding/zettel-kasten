from __future__ import annotations

import ast
from collections import Counter
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "wom-kit" / "tools" / "run_unittest_shard.py"
SPEC = importlib.util.spec_from_file_location("run_unittest_shard", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CiUnittestShardingTests(unittest.TestCase):
    def _make_modules(self, root: Path, sizes: list[int]):
        tests_dir = root / "tests"
        tests_dir.mkdir()
        for index, size in enumerate(sizes):
            (tests_dir / f"test_{index:02d}.py").write_bytes(b"x" * size)
        return MODULE.discover_test_modules(tests_dir)

    def test_assignment_is_complete_unique_balanced_and_deterministic(self):
        with tempfile.TemporaryDirectory() as raw:
            modules = self._make_modules(Path(raw), [100, 90, 80, 70, 60, 50, 40, 30])
            first = MODULE.assign_test_shards(modules, 3)
            second = MODULE.assign_test_shards(tuple(reversed(modules)), 3)

        first_paths = [
            module.relative_path for shard in first for module in shard
        ]
        expected = [module.relative_path for module in modules]
        self.assertEqual(sorted(first_paths), sorted(expected))
        self.assertEqual(len(first_paths), len(set(first_paths)))
        self.assertEqual(
            [[item.relative_path for item in shard] for shard in first],
            [[item.relative_path for item in shard] for shard in second],
        )
        weights = [sum(item.byte_length for item in shard) for shard in first]
        self.assertLessEqual(
            max(weights) - min(weights),
            max(item.byte_length for item in modules),
        )

    def test_manifest_proves_exact_assignment(self):
        with tempfile.TemporaryDirectory() as raw:
            modules = self._make_modules(Path(raw), [5, 10, 15, 20])
            manifest = MODULE.shard_manifest(modules, 2)

        self.assertTrue(manifest["complete"])
        self.assertEqual(manifest["duplicate_assignment_count"], 0)
        self.assertEqual(manifest["unassigned_count"], 0)
        self.assertEqual(manifest["test_module_count"], 4)
        self.assertEqual(
            sum(shard["module_count"] for shard in manifest["shards"]),
            4,
        )

    def test_invalid_shard_contracts_fail_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            modules = self._make_modules(Path(raw), [1, 2])
            with self.assertRaisesRegex(ValueError, "shard_count_must_be_positive"):
                MODULE.assign_test_shards(modules, 0)
            with self.assertRaisesRegex(ValueError, "shard_count_exceeds_module_count"):
                MODULE.assign_test_shards(modules, 3)

    def test_repository_manifest_is_complete_for_two_and_four_shards(self):
        for shard_count in (2, 4):
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(SCRIPT),
                    "--tests-dir",
                    str(ROOT / "wom-kit" / "tests"),
                    "--shard-count",
                    str(shard_count),
                    "--manifest-only",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            manifest = json.loads(completed.stdout)
            self.assertTrue(manifest["complete"])
            self.assertEqual(manifest["duplicate_assignment_count"], 0)
            self.assertEqual(manifest["unassigned_count"], 0)
            self.assertEqual(
                manifest["test_module_count"],
                len(list((ROOT / "wom-kit" / "tests").glob("test_*.py"))),
            )

    def test_cli_runs_selected_shard_with_explicit_no_bytecode_subprocess(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            tests_dir = Path(raw) / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_pass.py").write_text(
                "import unittest\n"
                "class PassTest(unittest.TestCase):\n"
                "    def test_pass(self):\n"
                "        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(SCRIPT),
                    "--tests-dir",
                    str(tests_dir),
                    "--shard-count",
                    "1",
                    "--shard-index",
                    "0",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        selection = json.loads(completed.stdout.splitlines()[0])
        self.assertEqual(selection["module_count"], 1)
        self.assertEqual(selection["shard_count"], 1)
        self.assertEqual(selection["shard_index"], 0)

    def test_ci_runs_pytest_native_suite_once_and_uses_explicit_zero_based_indices(self):
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertEqual(
            workflow.count(
                "if: runner.os == 'Windows' && matrix.shard_index_zero == 0"
            ),
            1,
        )
        self.assertIn(
            "--shard-index ${{ matrix.shard_index_zero }}",
            workflow,
        )
        self.assertNotIn("matrix.shard_index - 1", workflow)
        self.assertEqual(workflow.count("shard_index_zero:"), 8)
        matrix_rows = []
        current = None
        for raw_line in workflow.splitlines():
            line = raw_line.strip()
            if current is not None and line == "steps:":
                matrix_rows.append(current)
                current = None
                break
            if line.startswith("- os:"):
                if current is not None:
                    matrix_rows.append(current)
                current = {"os": line.split(":", 1)[1].strip()}
            elif current is not None and ":" in line:
                key, value = line.split(":", 1)
                if key in {
                    "python-version",
                    "shard_index_zero",
                    "timeout-minutes",
                }:
                    current[key] = value.strip().strip("'")
        if current is not None:
            matrix_rows.append(current)
        self.assertEqual(len(matrix_rows), 8)
        for row in matrix_rows:
            expected_timeout = (
                "75"
                if row["shard_index_zero"] == "0"
                or (
                    row["os"] == "windows-latest"
                    and row["shard_index_zero"] == "1"
                )
                else "45"
            )
            self.assertEqual(
                row["timeout-minutes"],
                expected_timeout,
                row,
            )

    def test_ci_explicitly_runs_every_top_level_pytest_module(self):
        tests_root = ROOT / "wom-kit" / "tests"
        pytest_native_modules = set()
        for path in sorted(tests_root.glob("test_*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            has_top_level_test = any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name.startswith("test_")
                for node in tree.body
            )
            has_plain_pytest_class = any(
                isinstance(node, ast.ClassDef)
                and node.name.startswith("Test")
                and not any(
                    (
                        isinstance(base, ast.Name)
                        and base.id == "TestCase"
                    )
                    or (
                        isinstance(base, ast.Attribute)
                        and base.attr == "TestCase"
                    )
                    for base in node.bases
                )
                and any(
                    isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and member.name.startswith("test_")
                    for member in node.body
                )
                for node in tree.body
            )
            if has_top_level_test or has_plain_pytest_class:
                pytest_native_modules.add(path.name)

        workflow = yaml.safe_load(
            (ROOT / ".github" / "workflows" / "ci.yml").read_text(
                encoding="utf-8"
            )
        )
        pytest_run_blocks = [
            str(step["run"])
            for job in workflow["jobs"].values()
            for step in job.get("steps", [])
            if isinstance(step, dict)
            and isinstance(step.get("run"), str)
            and re.search(r"(?:^|\s)-m\s+pytest\b", step["run"])
        ]
        explicit_pytest_modules = Counter(
            re.findall(
                r"wom-kit/tests/(test_[A-Za-z0-9_]+\.py)",
                "\n".join(pytest_run_blocks),
            )
        )
        self.assertEqual(
            set(explicit_pytest_modules),
            pytest_native_modules,
            "Every pytest-native module must appear in an actual workflow pytest run block.",
        )
        self.assertEqual(
            explicit_pytest_modules,
            Counter({name: 1 for name in pytest_native_modules}),
            "Every pytest-native module must appear exactly once across actual pytest commands.",
        )

    def test_current_branch_protection_docs_match_required_ci_state(self):
        readiness = (
            ROOT / "wom-kit" / "docs" / "main-branch-protection-readiness.md"
        ).read_text(encoding="utf-8")
        matrix = (
            ROOT / "wom-kit" / "docs" / "capability-matrix.md"
        ).read_text(encoding="utf-8")

        for phrase in (
            "main-required-ci",
            "enforcement is active",
            "Required CI",
            "branch deletion",
            "non-fast-forward",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readiness)
        self.assertIn("| Continuous integration workflow | `implemented required CI` |", matrix)
        self.assertIn("| Main branch protection | `implemented remote ruleset` |", matrix)
        self.assertNotIn("| Continuous integration workflow | `implemented non-required CI` |", matrix)


if __name__ == "__main__":
    unittest.main()
