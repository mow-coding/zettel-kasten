"""Run the exact changed assertions, CI self-tests and pending pytest coverage."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from incremental_ci import compare_inputs

ROOT = Path(__file__).resolve().parents[2]
CROSS_PYTEST = (
    'test_saved_view_workflows.py', 'test_v03297_private_objet_metadata_index_authority.py',
    'test_v03297_private_objet_metadata_index_rebuild.py', 'test_v03298_private_objet_finder.py',
    'test_v03314_index_private_projection_recovery.py',
)
WINDOWS_PYTEST = ('test_v03296_private_metadata_win32.py', 'test_v03296_private_metadata_writer_authority.py')


def run(plan: dict, output: Path) -> int:
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], text=True).strip()
    expected = subprocess.check_output(['git', 'rev-parse', plan['head'] + '^{tree}'], text=True).strip()
    if head != expected:
        raise ValueError('focused_checkout_tree_mismatch')
    delta = compare_inputs(plan['baseline_head'], plan['head'])
    if any(plan.get(key) != value for key, value in delta.items()):
        raise ValueError('focused_plan_input_mismatch')
    sys.path.insert(0, str(ROOT / 'wom-kit/src'))
    sys.path.insert(0, str(ROOT))
    loader = unittest.TestLoader()
    names = ['wom-kit.tests.' + name for name in plan['targets'] + plan['support_modules']]
    suite = loader.loadTestsFromNames(names)
    if loader.errors or suite.countTestCases() < len(plan['targets']) + len(plan['support_modules']):
        raise ValueError('focused_tests_missing')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    # A failed baseline unittest step did not reach these separate pytest suites.
    # Run them on each supported platform; never infer they passed from a log.
    pytest_files = [*CROSS_PYTEST, *(WINDOWS_PYTEST if os.name == 'nt' else ())]
    pytest_exit = subprocess.run([sys.executable, '-B', '-m', 'pytest', '-q',
                                *('wom-kit/tests/' + name for name in pytest_files)], cwd=ROOT).returncode
    clean = not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT).strip()
    ok = result.wasSuccessful() and not result.skipped and pytest_exit == 0 and clean
    report = {'schema': 'wom-kit/focused-ci-result/v1', 'ok': ok, 'head': plan['head'],
              'baseline_run': plan['baseline_run'], 'baseline_attempt': plan['baseline_attempt'],
              'targets': plan['targets'], 'tests_run': result.testsRun,
              'pytest_exit': pytest_exit, 'worktree_clean': clean,
              'platform': sys.platform, 'python': list(sys.version_info[:2])}
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return 0 if ok else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(json.loads(args.plan.read_text(encoding='utf-8')), args.output))
