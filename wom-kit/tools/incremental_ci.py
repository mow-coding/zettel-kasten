"""Reuse completed full CI only across proven assertion/documentation changes.

No previous failure becomes success: changed assertions run again on every
supported platform, including pytest steps not reached by failed baseline jobs.
Other edits, incomplete jobs, unknown failures and changed execution contracts
fall back to a full run. No customer data or raw logs enter the public plan.
"""
from __future__ import annotations

import argparse
import ast
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import quote

import ci_change_policy as policy

PROTECTED_JOBS = ('gate', 'tests', 'doctor_scale', 'link_index_scale', 'installed_wheel')
SUPPORT_TESTS = ('test_ci_change_policy', 'test_incremental_ci', 'test_release_artifact_reuse')
SUPPORT_FILES = frozenset({
    'wom-kit/tools/ci_change_policy.py', 'wom-kit/tools/incremental_ci.py',
    'wom-kit/tools/run_focused_tests.py', 'wom-kit/tools/verify_release_artifact.py',
    *('wom-kit/tests/' + name + '.py' for name in SUPPORT_TESTS),
})
INSTALLED_JOB = 'Installed public entrypoints and workflow gate (Windows py3.12)'
SCALE_JOBS = ('Doctor count scale gate (Ubuntu py3.12)',
              'Doctor mixed-payload scale gate (Ubuntu py3.12)',
              'Link-index regression scale gate (Windows py3.12)')
TEST_JOBS = tuple(f'Tests {os_name} py{version} shard {index}/{count}'
                  for os_name, version, count in [('ubuntu-latest', '3.10', 2),
                                                   ('ubuntu-latest', '3.12', 2),
                                                   ('windows-latest', '3.12', 4)]
                  for index in range(1, count + 1))


def git(*args: str) -> bytes:
    return subprocess.check_output(['git', *args], stderr=subprocess.DEVNULL)


def text_at(commit: str, path: str) -> str:
    return git('show', f'{commit}:{path}').decode('utf-8')


def inventory(commit: str) -> dict[str, str]:
    rows = git('ls-tree', '-rz', commit).split(b'\0')
    return {row.split(b'\t', 1)[1].decode(): row.split(b'\t', 1)[0].decode()
            for row in rows if row}


def workflow_job(source: str, name: str) -> str:
    match = re.search(r'^  ' + re.escape(name) + r':\n(.*?)(?=^  [a-z_]+:|\Z)',
                      source, re.M | re.S)
    if not match:
        raise ValueError('missing_execution_contract')
    return match.group(0).rstrip()


def assertion_changes(before: str, after: str, module: str) -> list[str]:
    """Only string literals inside existing self.assert* calls may differ.

    Fixtures, imports, decorators, control flow, calls and assertion operators
    must be identical. Replacing/removing an assertion cannot qualify.
    """
    old, new = ast.parse(before), ast.parse(after)
    def methods(tree):
        result = {}
        for cls in tree.body:
            if isinstance(cls, ast.ClassDef):
                for method in cls.body:
                    if isinstance(method, ast.FunctionDef) and method.name.startswith('test_'):
                        key = f'{module}.{cls.name}.{method.name}'
                        if key in result:
                            raise ValueError('duplicate_test_method')
                        result[key] = method
        return result
    left, right = methods(old), methods(new)
    if left.keys() != right.keys():
        raise ValueError('test_inventory_changed')
    changed = []
    def scrub(method):
        result = copy.deepcopy(method)
        for call in ast.walk(result):
            if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name) and call.func.value.id == 'self'
                    and call.func.attr.startswith('assert')):
                for node in call.args:
                    if isinstance(node, ast.Constant) and isinstance(node.value, str):
                        node.value = '<assertion string>'
                for node in ast.walk(call):
                    if (isinstance(node, ast.Compare) and len(node.ops) == 1
                            and isinstance(node.ops[0], (ast.In, ast.NotIn))
                            and isinstance(node.left, ast.Constant) and isinstance(node.left.value, str)):
                        node.left.value = '<assertion string>'
        return ast.dump(result, include_attributes=False)
    for name in left:
        a, b = left[name], right[name]
        if ast.dump(a) == ast.dump(b):
            continue
        if scrub(a) != scrub(b):
            raise ValueError('non_assertion_edit')
        changed.append(name)
        # Remove only matched method bodies from the full module comparison.
        a.body = b.body = [ast.Pass()]
    if ast.dump(old) != ast.dump(new):
        raise ValueError('shared_test_input_changed')
    return changed


def compare_inputs(base: str, head: str) -> dict:
    if subprocess.run(['git', 'merge-base', '--is-ancestor', base, head],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        raise ValueError('baseline_not_ancestor')
    before, after = inventory(base), inventory(head)
    changed = [p for p in before.keys() | after.keys() if before.get(p) != after.get(p)]
    targets = []
    for path in sorted(changed):
        if policy.documentation_path(path):
            continue
        if path == '.github/workflows/ci.yml':
            old, new = text_at(base, path), text_at(head, path)
            # Global environment, triggers and cancellation semantics are inputs
            # too. The read-only Actions permission is needed to fetch evidence.
            header = lambda value: value.split('\njobs:\n', 1)[0].replace('\n  actions: read', '')
            if header(old) != header(new):
                raise ValueError('global_execution_contract_changed')
            for job in PROTECTED_JOBS:
                if workflow_job(old, job) != workflow_job(new, job):
                    raise ValueError('execution_contract_changed')
            continue
        if path in SUPPORT_FILES:
            # CI selection/reuse code has its own mandatory cross-platform
            # tests. This never exempts a runtime, build or full-suite runner.
            if path not in after:
                raise ValueError('ci_support_deleted')
            continue
        if (path.startswith('wom-kit/tests/test_') and path.endswith('.py')
                and '/' not in path[len('wom-kit/tests/'):]
                and path in before and path in after):
            targets += assertion_changes(text_at(base, path), text_at(head, path), Path(path).stem)
            continue
        raise ValueError('product_or_shared_input_changed')
    if not changed:
        raise ValueError('no_incremental_change')
    # Unchanged inventory is the execution-input proof, not a filename guess.
    same = {p: oid for p, oid in after.items() if p not in changed}
    digest = hashlib.sha256(json.dumps(same, sort_keys=True).encode()).hexdigest()
    return {'targets': sorted(targets), 'support_modules': list(SUPPORT_TESTS),
            'unchanged_inventory_sha256': digest,
            'changed_paths_sha256': hashlib.sha256(json.dumps(sorted(changed)).encode()).hexdigest()}


def failed_tests(log: str) -> set[str]:
    # Remove only GitHub's timestamp, not test content or error records.
    clean = re.sub(r'^\d{4}-\d\d-\d\dT\S+Z ', '', log, flags=re.M)
    summary = re.findall(r'^FAILED \(failures=(\d+)(?:, skipped=\d+)?\)\s*$', clean, re.M)
    failures = re.findall(r'^FAIL: (test_\w+) \(([^\r\n()]+)\)\s*$', clean, re.M)
    if (len(summary) != 1 or len(failures) != int(summary[0]) or not failures
            or re.search(r'^ERROR:|^Unexpected success:', clean, re.M)
            or not re.search(r'^Ran \d+ tests? in [\d.]+s\s*$', clean, re.M)):
        raise ValueError('unaccounted_baseline_failure')
    result = set()
    for method, identity in failures:
        identity = identity.removeprefix('wom-kit.tests.')
        if not identity.endswith('.' + method):
            identity += '.' + method
        result.add(identity)
    if len(result) != len(failures):
        raise ValueError('duplicate_failure_identity')
    return result


def validate_jobs(jobs: list[dict], targets: list[str], load_log) -> dict:
    by_name = {j['name']: j for j in jobs}
    required = {'Release readiness gate', 'Classify exact change', INSTALLED_JOB, *SCALE_JOBS, *TEST_JOBS}
    if (len(by_name) != len(jobs) or not required.issubset(by_name)
            or set(by_name) - required - {'Required CI'}):
        raise ValueError('incomplete_full_baseline')
    observed = {}
    for name in required:
        job = by_name[name]
        if job['status'] != 'completed':
            raise ValueError('baseline_still_running')
        result = job['conclusion']
        if result == 'success':
            observed[name] = {'result': 'reused_success', 'job_id': job['id']}
            continue
        if name not in TEST_JOBS or result != 'failure':
            raise ValueError('non_test_baseline_failure')
        steps = job['steps']
        failed = [s['name'] for s in steps if s['conclusion'] == 'failure']
        if failed != ['WOM-kit unittest suite'] or any(s['conclusion'] in {'cancelled', 'timed_out'} for s in steps):
            raise ValueError('non_unittest_baseline_failure')
        log = load_log(job['id'])
        failures = failed_tests(log)
        if not failures.issubset(targets):
            raise ValueError('unchanged_test_failed')
        observed[name] = {'result': 'requires_focused_revalidation', 'job_id': job['id'],
                          'failed_tests': sorted(failures),
                          'log_sha256': hashlib.sha256(log.encode()).hexdigest()}
    return observed


def api(repo: str, endpoint: str, *, raw=False):
    command = ['gh', 'api', f'repos/{repo}/{endpoint}']
    response = subprocess.run(command, capture_output=True)
    if (raw and response.returncode
            and b'pass --allow-escape-sequences' in response.stderr):
        # Newer gh refuses ANSI-bearing job logs, even when stdout is piped.
        # Keep raw bytes for the evidence hash; never render them as commands.
        response = subprocess.run([*command, '--allow-escape-sequences'], capture_output=True)
    response.check_returncode()
    value = response.stdout
    return value.decode('utf-8') if raw else json.loads(value)


def baseline_plan(repo: str, run_id: int, head: str, pr_number: int) -> dict:
    run = api(repo, f'actions/runs/{run_id}')
    if (run['event'] != 'pull_request' or run['status'] != 'completed'
            or run['conclusion'] not in {'success', 'failure'}
            or not any(p['number'] == pr_number for p in run['pull_requests'])):
        raise ValueError('not_completed_same_pr_baseline')
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(run['created_at'].replace('Z', '+00:00'))).total_seconds()
    if not 0 <= age <= 86400:
        raise ValueError('baseline_outside_current_validation_window')
    delta = compare_inputs(run['head_sha'], head)
    jobs = api(repo, f'actions/runs/{run_id}/attempts/{run["run_attempt"]}/jobs?per_page=100')['jobs']
    observed = validate_jobs(jobs, delta['targets'], lambda job: api(repo, f'actions/jobs/{job}/logs', raw=True))
    tree = git('rev-parse', run['head_sha'] + '^{tree}').decode().strip()
    artifact = f'installed-wheel-{run_id}-{run["run_attempt"]}'
    with tempfile.TemporaryDirectory(prefix='wom-ci-evidence-') as temp:
        subprocess.run(['gh', 'run', 'download', str(run_id), '--repo', repo,
                        '--name', artifact, '--dir', temp], check=True, stdout=subprocess.DEVNULL)
        proof_raw = (Path(temp) / 'source-proof.json').read_bytes()
        proof = json.loads(proof_raw)
        if (proof.get('source_tree') != tree or proof.get('candidate_commit') != run['head_sha']
                or proof.get('run_id') != str(run_id) or proof.get('attempt') != str(run['run_attempt'])
                or proof.get('platform') != 'Windows' or not proof.get('python', '').startswith('3.12.')):
            raise ValueError('baseline_checkout_or_platform_mismatch')
    return {'schema': 'wom-kit/incremental-ci-plan/v1', 'head': head,
            'baseline_head': run['head_sha'], 'baseline_run': run_id,
            'baseline_tree': tree, 'installed_artifact': artifact,
            'source_proof_sha256': hashlib.sha256(proof_raw).hexdigest(),
            'baseline_attempt': run['run_attempt'], 'pull_request': pr_number,
            **delta, 'jobs': observed, 'full_baseline_conclusion': run['conclusion']}


def find_plan(repo: str, head: str, pr_number: int) -> dict | None:
    pr = api(repo, f'pulls/{pr_number}')
    runs = api(repo, 'actions/workflows/ci.yml/runs?event=pull_request&per_page=30&branch='
               + quote(pr['head']['ref'], safe=''))['workflow_runs']
    for run in runs:
        if run['head_sha'] == head or run['status'] != 'completed':
            continue
        try:
            return baseline_plan(repo, run['id'], head, pr_number)
        except (ValueError, SyntaxError, subprocess.CalledProcessError, KeyError):
            continue
    return None


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--head', required=True)
    parser.add_argument('--pr', type=int, required=True)
    parser.add_argument('--baseline', type=int)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    plan = (baseline_plan(args.repo, args.baseline, args.head, args.pr) if args.baseline
            else find_plan(args.repo, args.head, args.pr))
    args.output.write_text(json.dumps(plan, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(plan))
