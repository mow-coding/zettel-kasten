"""Real tree predicates with bounded synthetic faults, never a wheel build.

Stat-only faults demonstrate the diagnostic contract, not the cause of a CI
failure. No production guard, runtime payload or private client data is changed.
"""

from contextlib import contextmanager
from copy import deepcopy
import inspect
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from types import CodeType, SimpleNamespace
import unittest
from unittest import mock

import test_v0419_installed_runtime_failure_observation as existing
import test_v0419_runtime_noop as fixture
from wom_kit import archive_cli, project_runtime as runtime


driver, checker = existing.driver, existing.checker
_STAT_NAMES = ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_mtime_ns', 'st_file_attributes')


class RuntimeBoundaryObservationTests(unittest.TestCase):
    @contextmanager
    def stat_change(self, target, field, *, xor=None):
        original = Path.lstat
        observed = {'count': 0}
        def changed(path, *args, **kwargs):
            value = original(path, *args, **kwargs)
            if path == target:
                observed['count'] += 1
                if observed['count'] == 3:
                    fields = {name: getattr(value, name, 0) for name in _STAT_NAMES}
                    fields[field] = fields[field] + 1 if xor is None else fields[field] ^ xor
                    return SimpleNamespace(**fields)
            return value
        with mock.patch.object(Path, 'lstat', new=changed):
            yield observed

    def envelope(self, observer):
        return {'ok': False, 'schema': driver.SCHEMA,
                'reason_code': 'repair_resume_failed' if observer.stage == 'repair_fresh_resume' else 'public_update_failed',
                'failure_observation': observer.failure_payload(native_observed=False, cli_code=1)}

    def test_exact_comparison_registration_and_fixture_semantics_are_pinned(self):
        observation = driver.RuntimeBoundaryObservation(runtime)
        prior = fixture._RuntimeObservationDiagnostics()
        self.assertIs(observation.shape_code, prior.shape_code)
        self.assertIs(type(observation.shape_code), CodeType)
        self.assertEqual(driver.RUNTIME_DIRECTORY_COMPARISON_LINE, fixture._DIRECTORY_IDENTITY_COMPARISON_LINE)
        self.assertEqual(driver.RUNTIME_IDENTITY_FIELDS, fixture._DIRECTORY_IDENTITY_FIELDS)
        self.assertEqual(driver.RUNTIME_BOUNDARY_REASONS, prior._REASONS)
        source, first = inspect.getsourcelines(runtime._walk_regular_files)
        self.assertEqual(source[driver.RUNTIME_DIRECTORY_COMPARISON_LINE - first].strip(),
                         'if _stat_identity(directory_before) != _stat_identity(directory_after):')
        for line, comparison in driver.RUNTIME_COMPARISON_RAISES.items():
            with self.subTest(site=comparison):
                self.assertEqual(source[line - first].strip(),
                                 'raise ProjectRuntimeError("project_runtime_tree_changed")')

    def test_real_root_and_intermediate_comparisons_match_fixture_fields_without_values(self):
        for level in ('root', 'intermediate'):
            for field, expected in (('st_dev', 'device'), ('st_ino', 'inode'),
                                    ('st_mtime_ns', 'mtime_ns'), ('st_file_attributes', 'attributes')):
                with self.subTest(level=level, field=expected), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    nested = root / 'SYNTHETIC_PRIVATE_DIRECTORY'
                    nested.mkdir()
                    (nested / 'SYNTHETIC_PRIVATE_FILE').write_bytes(b'synthetic bytes')
                    target = root if level == 'root' else nested
                    original_identity = runtime._stat_identity
                    profile, trace = sys.getprofile(), sys.gettrace()
                    snapshots = []
                    for observer in (fixture._RuntimeObservationDiagnostics(), driver.RuntimeBoundaryObservation(runtime)):
                        with self.stat_change(target, field) as count, observer:
                            with self.assertRaises(runtime.ProjectRuntimeError) as caught:
                                runtime._runtime_payload_sha256(root)
                        self.assertEqual(caught.exception.args, ('project_runtime_tree_changed',))
                        self.assertEqual(count['count'], 3)
                        events = observer.snapshot()['events']
                        snapshots.append([row['changed_identity_fields'] for row in events
                                          if row.get('changed_identity_fields')])
                        self.assertIsNone(observer.identity_pair)
                        self.assertNotIn(str(root), json.dumps(events))
                        self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(events))
                    self.assertEqual(snapshots, [[[expected]], [[expected]]])
                    self.assertIs(runtime._stat_identity, original_identity)
                    self.assertIs(sys.getprofile(), profile)
                    self.assertIs(sys.gettrace(), trace)

    def test_both_harness_stages_keep_actual_nested_raise_coordinate_and_field(self):
        for stage in driver.FAILURE_OBSERVATION_STAGES:
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / 'SYNTHETIC_PRIVATE_FILE').write_bytes(b'synthetic')
                argv, calls = ['SYNTHETIC_PRIVATE_ARG'], []
                def cli(values):
                    self.assertIs(values, argv)
                    calls.append(True)
                    runtime._runtime_payload_sha256(root)
                with self.stat_change(root, 'st_mtime_ns'):
                    with self.assertRaises(driver.InitialUpdateCheckError) as caught:
                        driver._observed_runtime_call(archive_cli, runtime, cli, argv,
                                                      SimpleNamespace(called=False), stage=stage)
                self.assertEqual(calls, [True])
                value = {'ok': False, 'schema': driver.SCHEMA,
                         'reason_code': 'repair_resume_failed' if stage == 'repair_fresh_resume' else 'public_update_failed',
                         'failure_observation': caught.exception.observation}
                parsed = checker._parse_runtime_failure_output(json.dumps(value))
                failure = parsed['failure_observation']['failures']['first_cli_call'][0]
                self.assertEqual(failure['code'], 'project_runtime_tree_changed')
                self.assertEqual(failure['source'], {'file': 'wom-kit/src/wom_kit/project_runtime.py',
                                 'line': 3346, 'function': '_walk_regular_files'})
                events = parsed['failure_observation']['runtime_observation']['events']
                self.assertEqual(events[0]['changed_identity_fields'], ['mtime_ns'])
                self.assertFalse(parsed['failure_observation']['boundaries']['approval_broker']['entered'])
                self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(parsed))
                self.assertNotIn(str(root), json.dumps(parsed))

    def test_attribute_changes_keep_only_fixed_bit_names_from_original_comparison(self):
        names = dict(driver.RUNTIME_ATTRIBUTE_FLAGS)
        for position in range(32):
            bit, name = 1 << position, names.get(1 << position)
            with self.subTest(flag=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / 'SYNTHETIC_PRIVATE_FILE').write_bytes(b'synthetic')
                before_attributes = runtime._stat_identity(root.lstat())[-1]
                normalized = name == 'archive' or position == 28 and bool(before_attributes & 0x10)
                observer = driver.FirstUpdateObservation()
                with self.stat_change(root, 'st_file_attributes', xor=bit) as count, observer.runtime_boundaries():
                    if normalized:
                        # Product normalization makes this administrative bit
                        # invisible to content identity; diagnostics do not
                        # invent an attribute failure for a successful read.
                        runtime._runtime_payload_sha256(root)
                    else:
                        with self.assertRaises(runtime.ProjectRuntimeError) as caught:
                            runtime._runtime_payload_sha256(root)
                        observer.record('first_cli_call', caught.exception)
                if normalized:
                    self.assertIsNone(observer.runtime_observation)
                    self.assertNotIn('runtime_observation', observer.failure_payload(native_observed=False))
                    continue
                parsed = checker._parse_runtime_failure_output(json.dumps(self.envelope(observer)))
                row = parsed['failure_observation']['runtime_observation']['events'][0]
                self.assertEqual(count['count'], 3)
                self.assertEqual(row['changed_identity_fields'], ['attributes'])
                self.assertEqual(row['changed_attribute_flags'], [] if name is None else [name])
                self.assertIs(row['unknown_attribute_bits_changed'], name is None)
                label = 'bit_' + str(position).zfill(2)
                self.assertEqual(row['attribute_bits_set'], [] if before_attributes & bit else [label])
                self.assertEqual(row['attribute_bits_cleared'], [label] if before_attributes & bit else [])
                self.assertNotIn(str(root), json.dumps(parsed))
                self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(parsed))
                self.assertNotIn('attribute_values', row)

    def test_complete_attribute_positions_validate_directions_and_legacy_compatibility(self):
        observation = driver.RuntimeBoundaryObservation(runtime)
        observation._record('directory_identity', 'identity_changed', reason='project_runtime_tree_changed',
                            operation='before_after_directory_comparison', site='directory_identity', fields=('attributes',),
                            attribute_change={'changed_attribute_flags': ['hidden'], 'unknown_attribute_bits_changed': True,
                                              'attribute_bits_set': ['bit_01', 'bit_21'],
                                              'attribute_bits_cleared': ['bit_31']})
        observer = driver.FirstUpdateObservation()
        observer.runtime_observation = observation.snapshot()
        original = self.envelope(observer)
        self.assertEqual(checker._parse_runtime_failure_output(json.dumps(original)), original)
        for key, value in (
                ('attribute_bits_set', ['SYNTHETIC_PRIVATE']), ('attribute_bits_set', ['bit_32']),
                ('attribute_bits_set', ['bit_1']), ('attribute_bits_set', ['bit_01', 'bit_01', 'bit_21']),
                ('attribute_bits_set', ['bit_21', 'bit_01']), ('attribute_bits_set', 'bit_01'),
                ('attribute_bits_set', [1]), ('attribute_bits_set', ['bit_01', 'bit_21', 'bit_31']),
                ('attribute_bits_set', []), ('attribute_bits_cleared', None),
                ('unknown_attribute_bits_changed', False), ('changed_attribute_flags', ['hidden', 'system'])):
            with self.subTest(key=key, value=value):
                changed = deepcopy(original)
                changed['failure_observation']['runtime_observation']['events'][0][key] = value
                with self.assertRaises(checker.WheelCheckError):
                    checker._parse_runtime_failure_output(json.dumps(changed))
        for key in ('attribute_bits_set', 'attribute_bits_cleared', 'changed_attribute_flags', 'unknown_attribute_bits_changed'):
            changed = deepcopy(original)
            del changed['failure_observation']['runtime_observation']['events'][0][key]
            with self.assertRaises(checker.WheelCheckError):
                checker._parse_runtime_failure_output(json.dumps(changed))
        empty = deepcopy(original)
        row = empty['failure_observation']['runtime_observation']['events'][0]
        row.update(attribute_bits_set=[], attribute_bits_cleared=[], changed_attribute_flags=[],
                   unknown_attribute_bits_changed=False)
        with self.assertRaises(checker.WheelCheckError):
            checker._parse_runtime_failure_output(json.dumps(empty))
        # Previous fixed-name and field-only payloads remain readable; readers
        # must not fabricate a bit position or direction from the old boolean.
        row = original['failure_observation']['runtime_observation']['events'][0]
        del row['attribute_bits_set'], row['attribute_bits_cleared']
        self.assertEqual(checker._parse_runtime_failure_output(json.dumps(original)), original)

    def test_attribute_extension_rejects_unknown_labels_types_and_inconsistent_rows(self):
        observer = driver.FirstUpdateObservation()
        observation = driver.RuntimeBoundaryObservation(runtime)
        observation._record('directory_identity', 'identity_changed', reason='project_runtime_tree_changed',
                            operation='before_after_directory_comparison', site='directory_identity', fields=('attributes',),
                            attribute_change={'changed_attribute_flags': ['archive'], 'unknown_attribute_bits_changed': False})
        observer.runtime_observation = observation.snapshot()
        original = self.envelope(observer)
        self.assertEqual(checker._parse_runtime_failure_output(json.dumps(original)), original)

        for key, value in (('changed_attribute_flags', ['SYNTHETIC_PRIVATE']),
                           ('changed_attribute_flags', ['archive', 'archive']),
                           ('changed_attribute_flags', ['archive', 'hidden']),
                           ('changed_attribute_flags', []), ('changed_attribute_flags', 32),
                           ('unknown_attribute_bits_changed', 1), ('unknown_attribute_bits_changed', None),
                           ('changed_identity_fields', ['inode']), ('attribute_mask', 32)):
            with self.subTest(key=key, value=value):
                changed = deepcopy(original)
                changed['failure_observation']['runtime_observation']['events'][0][key] = value
                with self.assertRaises(checker.WheelCheckError):
                    checker._parse_runtime_failure_output(json.dumps(changed))
        for key in ('changed_attribute_flags', 'unknown_attribute_bits_changed'):
            changed = deepcopy(original)
            del changed['failure_observation']['runtime_observation']['events'][0][key]
            with self.assertRaises(checker.WheelCheckError):
                checker._parse_runtime_failure_output(json.dumps(changed))
        # Older field-only observations remain valid, with no bit inference.
        row = original['failure_observation']['runtime_observation']['events'][0]
        del row['changed_attribute_flags'], row['unknown_attribute_bits_changed']
        self.assertEqual(checker._parse_runtime_failure_output(json.dumps(original)), original)

    def test_source_diagnostic_retains_same_validated_failure_observations(self):
        observer = driver.FirstUpdateObservation()
        observation = driver.RuntimeBoundaryObservation(runtime)
        observation._record('directory_identity', 'identity_changed', reason='project_runtime_tree_changed',
                            operation='before_after_directory_comparison', site='directory_identity', fields=('attributes',),
                            attribute_change={'changed_attribute_flags': ['hidden'], 'unknown_attribute_bits_changed': False})
        observer.runtime_observation = observation.snapshot()
        cli_result = {'status': 'blocked', 'reason_codes': ['SYNTHETIC_PRIVATE'],
                      'project_runtime': {'preparation_revalidation': {'state': 'failed'}},
                      'private': 'SYNTHETIC_PRIVATE'}
        payload = json.loads(observer.diagnostic(native_observed=False, cli_code=1, cli_result=cli_result))
        self.assertEqual(payload, observer.failure_payload(native_observed=False, cli_code=1, cli_result=cli_result))
        self.assertEqual(payload['runtime_observation']['events'][0]['changed_attribute_flags'], ['hidden'])
        self.assertEqual(payload['cli']['status'], 'blocked')
        self.assertEqual(payload['cli']['preparation_revalidation_state'], 'failed')
        self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(payload))

    def test_other_real_tree_refusals_identify_site_without_guessing_directory_fields(self):
        for site in ('file_size', 'tree_generation'):
            with self.subTest(site=site), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                path = root / 'SYNTHETIC_PRIVATE_FILE'
                path.write_bytes(b'original bytes')
                before = path.read_bytes()
                original = runtime._sha256_file
                calls = []
                def fault(*args, **kwargs):
                    result = original(*args, **kwargs)
                    calls.append(True)
                    if site == 'file_size':
                        # Deliberate result-only fault at the existing predicate;
                        # the actual original hash/read still ran exactly once.
                        return result[0], result[1] + 1
                    info = root.stat()
                    os.utime(root, ns=(info.st_atime_ns, info.st_mtime_ns + 2_000_000_000))
                    return result
                observer = driver.FirstUpdateObservation()
                with mock.patch.object(runtime, '_sha256_file', new=fault), observer.runtime_boundaries():
                    with self.assertRaises(runtime.ProjectRuntimeError) as caught:
                        runtime._runtime_payload_sha256(root)
                    observer.record('first_cli_call', caught.exception)
                parsed = checker._parse_runtime_failure_output(json.dumps(self.envelope(observer)))
                events = parsed['failure_observation']['runtime_observation']['events']
                self.assertIn(site, {row['comparison_site'] for row in events})
                self.assertFalse(any(row['changed_identity_fields'] for row in events))
                self.assertEqual(calls, [True])
                self.assertEqual(path.read_bytes(), before)
                self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(parsed))

    def test_directory_allocation_size_stays_normalized_and_success_has_no_optional_payload(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'synthetic').write_bytes(b'bytes')
            original = runtime._runtime_payload_sha256(root)
            observer = driver.FirstUpdateObservation()
            with self.stat_change(root, 'st_size'), observer.runtime_boundaries():
                self.assertEqual(runtime._runtime_payload_sha256(root), original)
            self.assertIsNone(observer.runtime_observation)
            self.assertNotIn('runtime_observation', observer.failure_payload(native_observed=False))

    def test_original_returns_exceptions_restoration_and_other_thread_remain_unchanged(self):
        observation = driver.RuntimeBoundaryObservation(runtime)
        observation.owner_thread = threading.get_ident()
        result, argument, calls = object(), object(), []
        def original(*args, **kwargs):
            calls.append((args, kwargs))
            return result
        self.assertIs(observation._wrap(original, 'file_hash')(argument, marker=argument), result)
        self.assertEqual(calls, [((argument,), {'marker': argument})])
        error = OSError(5, 'SYNTHETIC_PRIVATE_EXCEPTION', 'SYNTHETIC_PRIVATE_PATH')
        error.winerror = 32
        def failing():
            raise error
        with self.assertRaises(OSError) as caught:
            observation._wrap(failing, 'file_hash')()
        self.assertIs(caught.exception, error)
        self.assertEqual(observation.snapshot()['events'][0]['winerror'], 32)
        # Instrumentation failure cannot replace the original error/result.
        with mock.patch.object(observation, '_record', side_effect=ValueError('SYNTHETIC_PRIVATE_DIAGNOSTIC')):
            with self.assertRaises(OSError) as caught:
                observation._wrap(failing, 'file_hash')()
        self.assertIs(caught.exception, error)
        before, seen = observation.snapshot(), []
        def other():
            try:
                observation._wrap(failing, 'file_hash')()
            except OSError as caught:
                seen.append(caught)
        worker = threading.Thread(target=other)
        worker.start()
        worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(seen, [error])
        self.assertEqual(observation.snapshot(), before)
        self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(before))
        functions = tuple(getattr(runtime, name) for name, _boundary in driver.RUNTIME_BOUNDARY_TARGETS)
        os_functions = (Path.lstat, os.open, os.fstat, runtime._stat_identity)
        with self.assertRaises(OSError) as caught:
            with driver.RuntimeBoundaryObservation(runtime):
                raise error
        self.assertIs(caught.exception, error)
        self.assertEqual(functions, tuple(getattr(runtime, name) for name, _boundary in driver.RUNTIME_BOUNDARY_TARGETS))
        self.assertEqual(os_functions, (Path.lstat, os.open, os.fstat, runtime._stat_identity))

    def test_decisive_lane_survives_incidental_saturation_and_snapshot_is_detached(self):
        observation = driver.RuntimeBoundaryObservation(runtime)
        for _ in range(40):
            observation._record('regular_file_read', 'read_not_confirmed')
        observation._record('directory_identity', 'identity_changed', reason='project_runtime_tree_changed',
                            operation='before_after_directory_comparison', site='directory_identity', fields=('inode',))
        snapshot = observation.snapshot()
        self.assertTrue(snapshot['truncated'])
        self.assertLessEqual(len(snapshot['events']), 32)
        self.assertEqual(snapshot['events'][0]['changed_identity_fields'], ['inode'])
        snapshot['events'][0]['changed_identity_fields'].append('SYNTHETIC_PRIVATE_TOKEN')
        self.assertEqual(observation.snapshot()['events'][0]['changed_identity_fields'], ['inode'])

    def test_parent_rejects_unknown_private_or_inconsistent_runtime_grammar(self):
        observer = driver.FirstUpdateObservation()
        observation = driver.RuntimeBoundaryObservation(runtime)
        observation._record('directory_identity', 'identity_changed', reason='project_runtime_tree_changed',
                            operation='before_after_directory_comparison', site='directory_identity', fields=('device',))
        observer.runtime_observation = observation.snapshot()
        original = self.envelope(observer)
        self.assertEqual(checker._parse_runtime_failure_output(json.dumps(original)), original)
        cases = []
        for key, value in (('boundary', 'SYNTHETIC_PRIVATE_TOKEN'), ('outcome', 'passed'),
                           ('reason_code', 'SYNTHETIC_PRIVATE_TOKEN'), ('operation', 'os_open'),
                           ('cause_depth', True), ('errno', 5), ('winerror', 65536),
                           ('comparison_site', 'file_size'), ('changed_identity_fields', ['device', 'device']),
                           ('path', 'SYNTHETIC_PRIVATE_TOKEN')):
            changed = deepcopy(original)
            changed['failure_observation']['runtime_observation']['events'][0][key] = value
            cases.append(changed)
        for key, value in (('schema', 'SYNTHETIC_PRIVATE_TOKEN'), ('truncated', 1), ('private', False),
                           ('events', []), ('events', observation.snapshot()['events'] * 33)):
            changed = deepcopy(original)
            changed['failure_observation']['runtime_observation'][key] = value
            cases.append(changed)
        for changed in cases:
            with self.assertRaises(checker.WheelCheckError) as caught:
                checker._parse_runtime_failure_output(json.dumps(changed))
            self.assertNotIn('SYNTHETIC_PRIVATE', repr(caught.exception))
            self.assertIsNone(caught.exception.__context__)


if __name__ == '__main__':
    unittest.main()
