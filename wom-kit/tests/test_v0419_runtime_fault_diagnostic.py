"""Unexpected candidate preflight failures remain failing and traceable."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.append(str(TESTS))

from test_project_runtime_candidate import _expect_exact_runtime_fault, project_runtime


class RuntimeFaultDiagnosticTests(unittest.TestCase):
    def test_only_exact_expected_fault_is_accepted(self):
        with _expect_exact_runtime_fault("project_runtime_repair_promotion_rolled_back"):
            raise project_runtime.ProjectRuntimeError("project_runtime_repair_promotion_rolled_back")
        with self.assertRaises(AssertionError):
            with _expect_exact_runtime_fault("project_runtime_repair_promotion_rolled_back"):
                pass

    def test_unexpected_fault_preserves_original_exception_and_frame(self):
        original = project_runtime.ProjectRuntimeError("project_runtime_tree_changed")

        def actual_preflight_failure():
            raise original

        try:
            with _expect_exact_runtime_fault("project_runtime_repair_promotion_rolled_back"):
                actual_preflight_failure()
        except project_runtime.ProjectRuntimeError as caught:
            self.assertIs(caught, original)
            frames = []
            traceback = caught.__traceback__
            while traceback is not None:
                frames.append(traceback.tb_frame.f_code.co_name)
                traceback = traceback.tb_next
            self.assertIn("actual_preflight_failure", frames)
        else:
            self.fail("An unexpected runtime failure was hidden.")


if __name__ == "__main__":
    unittest.main()
