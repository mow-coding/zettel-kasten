"""Test-only original-call diagnostics; no runtime construction or retries."""

import ast
import inspect
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_project_runtime_candidate as fixture


runtime = fixture.project_runtime


class CandidateReuseObservationTests(unittest.TestCase):
    def candidate(self, reusable=False, repair=False):
        return SimpleNamespace(existing_runtime_reusable=reusable,
                               existing_runtime_repair_required=repair)

    def test_allowlist_is_exactly_the_original_return_contract(self):
        tree = ast.parse(inspect.getsource(runtime._existing_runtime_candidate_observation))
        reasons = {node.value for node in ast.walk(tree)
                   if isinstance(node, ast.Constant) and type(node.value) is str
                   and node.value.startswith("project_runtime_existing_")}
        self.assertEqual(fixture._CANDIDATE_REUSE_REASONS, reasons)

    def test_one_original_call_identical_arguments_result_and_no_output_or_extra_io(self):
        calls, args, kwargs = [], (object(), object()), {"private_kw": object()}
        result = {"state": "failed", "reason_code": "project_runtime_existing_payload_mismatch",
                  "matches": False, "private_extra": "PRIVATE_TEST_MARKER"}
        def original(*actual_args, **actual_kwargs):
            calls.append((actual_args, actual_kwargs))
            return result
        output, error = io.StringIO(), io.StringIO()
        profile, trace = sys.getprofile(), sys.gettrace()
        with patch.object(runtime, "_existing_runtime_candidate_observation", original):
            with redirect_stdout(output), redirect_stderr(error), fixture._CandidateReuseObservation() as observed:
                # The loader has already run. The comparison and observation
                # must introduce no filesystem observation of their own.
                with patch.object(Path, "lstat", side_effect=AssertionError("extra lstat")), \
                     patch.object(runtime.os, "open", side_effect=AssertionError("extra open")), \
                     patch.object(runtime.os, "fstat", side_effect=AssertionError("extra fstat")):
                    actual = runtime._existing_runtime_candidate_observation(*args, **kwargs)
                self.assertIs(actual, result)
            self.assertIs(runtime._existing_runtime_candidate_observation, original)
        self.assertEqual(calls, [(args, kwargs)])
        payload = json.loads(observed.failure_message(self.candidate()))
        self.assertEqual(payload["observation"], {key: result[key] for key in ("state", "reason_code", "matches")})
        self.assertEqual(payload["runtime_observation"]["events"], [])
        self.assertNotIn("PRIVATE_TEST_MARKER", json.dumps(payload))
        self.assertEqual((output.getvalue(), error.getvalue()), ("", ""))
        self.assertIs(sys.getprofile(), profile)
        self.assertIs(sys.gettrace(), trace)

    def test_original_exception_identity_boundary_snapshot_and_functions_restored(self):
        error = runtime.ProjectRuntimeError("PRIVATE_TEST_MARKER")
        calls = []
        def hashing(*args, **kwargs):
            raise error
        def original(*args, **kwargs):
            calls.append(True)
            return runtime._sha256_file("PRIVATE_TEST_MARKER")
        real_stat = runtime._stat_identity
        with patch.object(runtime, "_existing_runtime_candidate_observation", original), \
             patch.object(runtime, "_sha256_file", hashing):
            with self.assertRaises(runtime.ProjectRuntimeError) as caught:
                with fixture._CandidateReuseObservation() as observed:
                    runtime._existing_runtime_candidate_observation(object(), object())
            self.assertIs(runtime._existing_runtime_candidate_observation, original)
            self.assertIs(runtime._sha256_file, hashing)
        self.assertIs(caught.exception, error)
        self.assertEqual(calls, [True])
        self.assertIs(runtime._stat_identity, real_stat)
        rendered = observed.failure_message(self.candidate())
        self.assertNotIn("PRIVATE_TEST_MARKER", rendered)
        events = json.loads(rendered)["runtime_observation"]["events"]
        self.assertEqual(events[0]["boundary"], "file_hash")
        self.assertIsNone(events[0]["reason_code"])

    def test_unknown_values_are_unclassified_not_stringified_or_truth_coerced(self):
        class PrivateValue:
            def __str__(self):
                raise AssertionError("private value was rendered")
            def __bool__(self):
                raise AssertionError("private value was coerced")
        private = PrivateValue()
        for result in ({"state": private, "reason_code": private, "matches": 1},
                       {"state": "PRIVATE_TEST_MARKER", "reason_code": "PRIVATE_TEST_MARKER", "matches": private},
                       private):
            with self.subTest(kind=type(result).__name__), \
                 patch.object(runtime, "_existing_runtime_candidate_observation", return_value=result) as original:
                with fixture._CandidateReuseObservation() as observed:
                    self.assertIs(runtime._existing_runtime_candidate_observation(object(), object()), result)
                original.assert_called_once()
                payload = json.loads(observed.failure_message(self.candidate(private, 1)))
                self.assertEqual(payload["observation"], {"state": "unclassified", "reason_code": "unclassified", "matches": None})
                self.assertIsNone(payload["existing_runtime_reusable"])
                self.assertIsNone(payload["existing_runtime_repair_required"])
                self.assertNotIn("PRIVATE_TEST_MARKER", json.dumps(payload))

    def test_other_thread_is_forwarded_but_not_observed(self):
        returned, calls = [], []
        result = {"state": "passed", "reason_code": "project_runtime_existing_verified", "matches": True}
        def original(*args, **kwargs):
            calls.append(True)
            return result
        with patch.object(runtime, "_existing_runtime_candidate_observation", original):
            with fixture._CandidateReuseObservation() as observed:
                thread = threading.Thread(target=lambda: returned.append(runtime._existing_runtime_candidate_observation(1, 2)))
                thread.start()
                thread.join(timeout=5)
                self.assertFalse(thread.is_alive())
        self.assertEqual(calls, [True])
        self.assertIs(returned[0], result)
        self.assertIsNone(observed.runtime_observation)
        self.assertEqual(observed.observation["state"], "unclassified")

    def test_only_last_return_and_bounded_runtime_events_survive(self):
        error = runtime.ProjectRuntimeError("PRIVATE_TEST_MARKER")
        results = iter([{"state": "passed", "reason_code": "project_runtime_existing_verified", "matches": True},
                        {"state": "unavailable", "reason_code": "project_runtime_existing_observation_unavailable", "matches": False}])
        calls = []
        def original(*args, **kwargs):
            calls.append(True)
            for _ in range(40):
                try:
                    runtime._sha256_file("PRIVATE_TEST_MARKER")
                except runtime.ProjectRuntimeError:
                    pass
            return next(results)
        with patch.object(runtime, "_existing_runtime_candidate_observation", original), \
             patch.object(runtime, "_sha256_file", side_effect=error):
            with fixture._CandidateReuseObservation() as observed:
                runtime._existing_runtime_candidate_observation(1, 2)
                runtime._existing_runtime_candidate_observation(1, 2)
        payload = json.loads(observed.failure_message(self.candidate(False, True)))
        self.assertEqual(len(calls), 2)
        self.assertEqual(payload["observation"]["state"], "unavailable")
        self.assertIs(payload["existing_runtime_reusable"], False)
        self.assertIs(payload["existing_runtime_repair_required"], True)
        self.assertLessEqual(len(payload["runtime_observation"]["events"]), 32)
        self.assertIs(payload["runtime_observation"]["truncated"], True)
        self.assertNotIn("PRIVATE_TEST_MARKER", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
