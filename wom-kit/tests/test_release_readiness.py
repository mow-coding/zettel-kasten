from __future__ import annotations

import importlib.util
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace


KIT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = KIT_ROOT.parent
CHECKER_PATH = KIT_ROOT / "tools" / "check_release_readiness.py"

spec = importlib.util.spec_from_file_location("check_release_readiness", CHECKER_PATH)
assert spec is not None and spec.loader is not None
check_release_readiness = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = check_release_readiness
spec.loader.exec_module(check_release_readiness)


class ReleaseReadinessTests(unittest.TestCase):
    def test_release_gate_uses_expected_checker_paths(self) -> None:
        self.assertEqual(
            [check.script_path for check in check_release_readiness.RELEASE_CHECKS],
            [
                "wom-kit/tools/check_public_links.py",
                "wom-kit/tools/check_korean_product_language.py",
                "wom-kit/tools/check_public_privacy.py",
                "wom-kit/tools/check_runtime_skill.py",
            ],
        )

    def test_success_returns_zero_when_all_child_checks_pass(self) -> None:
        calls: list[list[str]] = []

        def fake_runner(command, **kwargs):
            calls.append(command)
            return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

        results = check_release_readiness.run_release_checks(REPO_ROOT, runner=fake_runner)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = check_release_readiness.summarize_results(results)

        self.assertEqual(exit_code, 0)
        self.assertIn("PASS: public link hygiene", buffer.getvalue())
        self.assertEqual(len(calls), 4)
        self.assertTrue(all(command[0] == sys.executable for command in calls))

    def test_failure_returns_nonzero_and_identifies_failing_checker(self) -> None:
        failing_script = "wom-kit/tools/check_korean_product_language.py"

        def fake_runner(command, **kwargs):
            script = Path(command[1]).as_posix()
            if script.endswith(failing_script):
                return SimpleNamespace(returncode=1, stdout="language drift\n", stderr="details\n")
            return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

        results = check_release_readiness.run_release_checks(REPO_ROOT, runner=fake_runner)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = check_release_readiness.summarize_results(results)

        output = buffer.getvalue()
        self.assertEqual(exit_code, 1)
        self.assertIn("FAIL: Korean product-language hygiene", output)
        self.assertIn("language drift", output)
        self.assertIn("details", output)

    def test_current_repository_passes_release_gate(self) -> None:
        results = check_release_readiness.run_release_checks(REPO_ROOT)
        self.assertEqual(
            [(result.check.name, result.returncode) for result in results],
            [(result.check.name, 0) for result in results],
        )

    def test_source_has_no_network_or_release_edit_behavior(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        banned = (
            "req" + "uests",
            "urllib" + ".request",
            "http" + ".client",
            "url" + "open",
            "gh " + "release",
            "provider" + "_api",
            "add" + "_parser",
            "mcp" + "_server",
        )
        for needle in banned:
            with self.subTest(needle=needle):
                self.assertNotIn(needle, source)


if __name__ == "__main__":
    unittest.main()
