"""A narrow retry must never hide a changed input or an unrelated failure."""
import copy
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
with patch.object(sys, 'path', [str(TOOLS), *sys.path]):
    spec = importlib.util.spec_from_file_location('incremental_ci', TOOLS / 'incremental_ci.py')
    ci = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ci)

SAMPLE = '''import unittest
class Example(unittest.TestCase):
    def setUp(self): self.value = "observed"
    def test_message(self):
        self.assertTrue(any("old expected message" in x for x in [self.value]))
'''


class IncrementalCITests(unittest.TestCase):
    def test_only_assertion_literals_change(self):
        new = SAMPLE.replace('old expected message', 'new expected message')
        self.assertEqual(ci.assertion_changes(SAMPLE, new, 'test_example'),
                         ['test_example.Example.test_message'])
        for altered in (new.replace('observed', 'changed fixture'),
                        new.replace('assertTrue', 'assertFalse'),
                        new.replace('any(', 'all('),
                        new.replace('def test_message', 'def test_renamed'),
                        new.replace('import unittest', 'import unittest\nimport os'),
                        new.replace('self.assertTrue', 'return # self.assertTrue')):
            with self.subTest(altered=altered), self.assertRaises((ValueError, SyntaxError)):
                ci.assertion_changes(SAMPLE, altered, 'test_example')

    def test_failure_log_requires_complete_accounted_results(self):
        log = ('FAIL: test_message (wom-kit.tests.test_example.Example.test_message)\n'
               'Ran 1470 tests in 123.456s\nFAILED (failures=1, skipped=2)\n')
        self.assertEqual(ci.failed_tests(log), {'test_example.Example.test_message'})
        self.assertEqual(ci.failed_tests(log.replace('.test_message)', ')')),
                         {'test_example.Example.test_message'})
        for changed in (log.replace('failures=1', 'failures=2'),
                        log.replace('failures=1', 'failures=1, errors=1'),
                        log.replace('Ran 1470 tests in 123.456s', 'runner timed out'),
                        log + 'ERROR: test_other (other.Example)\n', log + log):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                ci.failed_tests(changed)

    def test_completed_passes_and_only_changed_failures_can_be_combined(self):
        names = ['Release readiness gate', 'Classify exact change', ci.INSTALLED_JOB,
                 *ci.SCALE_JOBS, *ci.TEST_JOBS]
        jobs = [{'id': i, 'name': n, 'status': 'completed', 'conclusion': 'success',
                 'steps': []} for i, n in enumerate(names)]
        self.assertEqual(len(ci.validate_jobs(jobs, [], lambda _: '')), len(names))
        bad = copy.deepcopy(jobs)
        bad[-1].update(conclusion='failure', steps=[{'name': 'WOM-kit unittest suite', 'conclusion': 'failure'}])
        log = 'FAIL: test_message (test_example.Example)\nRan 9 tests in 1.0s\nFAILED (failures=1)\n'
        report = ci.validate_jobs(bad, ['test_example.Example.test_message'], lambda _: log)
        self.assertEqual(report[bad[-1]['name']]['result'], 'requires_focused_revalidation')
        with self.assertRaises(ValueError):
            ci.validate_jobs(bad, [], lambda _: log)
        for state in ('cancelled', 'timed_out', 'skipped'):
            changed = copy.deepcopy(jobs); changed[-1]['conclusion'] = state
            with self.assertRaises(ValueError): ci.validate_jobs(changed, [], lambda _: '')
        with self.assertRaises(ValueError): ci.validate_jobs(jobs[:-1], [], lambda _: '')
        with self.assertRaises(ValueError): ci.validate_jobs(jobs + jobs[:1], [], lambda _: '')
        with self.assertRaises(ValueError):
            ci.validate_jobs(jobs + [dict(jobs[0], name='Unknown extra check')], [], lambda _: '')
        bad[-1]['steps'][0]['name'] = 'Install dependencies'
        with self.assertRaises(ValueError): ci.validate_jobs(bad, [], lambda _: log)

    def test_exact_git_inputs_detect_runtime_fixture_and_global_workflow_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.DEVNULL).decode().strip()
            git('init', '-q'); git('config', 'user.name', 'Synthetic CI')
            git('config', 'user.email', 'synthetic@example.invalid')
            test = root / 'wom-kit/tests/test_example.py'; test.parent.mkdir(parents=True)
            test.write_text(SAMPLE, encoding='utf-8')
            runtime = root / 'product.py'; runtime.write_text('VALUE = 1\n', encoding='utf-8')
            workflow = root / '.github/workflows/ci.yml'; workflow.parent.mkdir(parents=True)
            original = 'name: CI\nenv:\n  MODE: real\njobs:\n' + ''.join(
                f'  {job}:\n    run: check-{job}\n' for job in ci.PROTECTED_JOBS)
            workflow.write_text(original, encoding='utf-8')
            git('add', '--', 'wom-kit/tests/test_example.py', 'product.py', '.github/workflows/ci.yml')
            git('commit', '-qm', 'synthetic baseline'); base = git('rev-parse', 'HEAD')
            test.write_text(SAMPLE.replace('old expected message', 'new message'), encoding='utf-8')
            git('add', '--', 'wom-kit/tests/test_example.py'); git('commit', '-qm', 'assertion update')
            real_run = subprocess.run
            with patch.object(ci, 'git', lambda *a: subprocess.check_output(['git', *a], cwd=root)), \
                 patch.object(ci.subprocess, 'run', wraps=subprocess.run) as called:
                # merge-base is the sole run() call; bind it to the synthetic repo.
                called.side_effect = lambda args, **kwargs: real_run(args, **({'cwd': root} | kwargs))
                self.assertEqual(ci.compare_inputs(base, git('rev-parse', 'HEAD'))['targets'],
                                 ['test_example.Example.test_message'])
                for path, content in ((runtime, 'VALUE = 2\n'),
                                      (workflow, original.replace('MODE: real', 'MODE: fake'))):
                    previous = path.read_bytes(); path.write_text(content, encoding='utf-8')
                    git('add', '--', path.relative_to(root).as_posix()); git('commit', '-qm', 'changed input')
                    with self.assertRaises(ValueError): ci.compare_inputs(base, git('rev-parse', 'HEAD'))
                    path.write_bytes(previous); git('add', '--', path.relative_to(root).as_posix())
                    git('commit', '-qm', 'restore synthetic input')


if __name__ == '__main__': unittest.main()
