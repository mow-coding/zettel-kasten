"""Small contracts for the existing candidate fixture's failure-only observer."""

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import test_cli


class CliCandidateObservationTests(unittest.TestCase):
    def test_source_fixture_enters_and_restores_same_component_observer(self):
        services = test_cli.archive_services
        original = services._project_update_live_component_sha256
        original_walk = test_cli.project_runtime._walk_regular_files
        raised_error = RuntimeError("SYNTHETIC_PRIVATE_TOKEN")
        with self.assertRaises(RuntimeError) as raised:
            with test_cli._observe_project_update_fixture_boundaries():
                self.assertIsNot(services._project_update_live_component_sha256, original)
                self.assertIsNot(test_cli.project_runtime._walk_regular_files, original_walk)
                raise raised_error
        self.assertIs(raised.exception, raised_error)
        self.assertIs(services._project_update_live_component_sha256, original)
        self.assertIs(test_cli.project_runtime._walk_regular_files, original_walk)

    def test_source_fixture_preserves_real_inner_tree_refusal_and_bounded_runtime_evidence(self):
        runtime = test_cli.project_runtime
        original_hash = runtime._sha256_file
        calls = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "SYNTHETIC_PRIVATE_FILE").write_bytes(b"synthetic bytes")

            def wrong_size(*args, **kwargs):
                result = original_hash(*args, **kwargs)
                calls.append(True)
                return result[0], result[1] + 1

            def prepare():
                return runtime._runtime_payload_sha256(root)

            with mock.patch.object(runtime, "_sha256_file", new=wrong_size), \
                 mock.patch.object(runtime, "prepare_runtime_candidate", new=prepare):
                with self.assertRaises(runtime.ProjectRuntimeError) as raised:
                    with test_cli._observe_project_update_fixture_boundaries() as observation:
                        runtime.prepare_runtime_candidate()
            self.assertEqual(raised.exception.args, ("project_runtime_tree_changed",))
            self.assertEqual(calls, [True])
            payload = observation.failure_payload(native_observed=False, cli_code=1)
            source = payload["failures"]["runtime_prepare"][0]["source"]
            self.assertEqual(source, {"file": "wom-kit/src/wom_kit/project_runtime.py",
                                      "function": "_walk_regular_files", "line": 3402})
            events = payload["runtime_observation"]["events"]
            self.assertIn("file_size", {row["comparison_site"] for row in events})
            self.assertFalse(any(row["changed_identity_fields"] for row in events))
            self.assertNotIn("SYNTHETIC_PRIVATE", json.dumps(payload))
            self.assertNotIn(str(root), json.dumps(payload))

    def test_original_calls_results_and_argument_identity_are_preserved(self):
        runtime, cli = test_cli.project_runtime, test_cli.archive_cli
        supplied, result, projected = object(), object(), object()
        error = ValueError("SYNTHETIC_PRIVATE_TOKEN")
        calls = []

        def prepare(value, *, selected):
            calls.append(("prepare", value, selected))
            return result

        def broker(value, *, selected):
            calls.append(("broker", value, selected))
            return result

        def projector(value):
            calls.append(("projector", value))
            return projected

        profile, trace = sys.getprofile(), sys.gettrace()
        with mock.patch.object(runtime, "prepare_runtime_candidate", new=prepare), \
             mock.patch.object(cli, "_execute_project_version_update_exact_human_approved_write", new=broker), \
             mock.patch.object(cli, "_project_version_update_privacy_safe_failure_result", new=projector):
            with test_cli._observe_project_update_fixture_boundaries() as observation:
                self.assertIs(runtime.prepare_runtime_candidate(supplied, selected=supplied), result)
                self.assertIs(cli._execute_project_version_update_exact_human_approved_write(
                    supplied, selected=supplied), result)
                self.assertIs(cli._project_version_update_privacy_safe_failure_result(error), projected)
            self.assertIs(runtime.prepare_runtime_candidate, prepare)
            self.assertIs(cli._execute_project_version_update_exact_human_approved_write, broker)
            self.assertIs(cli._project_version_update_privacy_safe_failure_result, projector)
        self.assertEqual(calls, [("prepare", supplied, supplied), ("broker", supplied, supplied),
                                 ("projector", error)])
        self.assertEqual(observation.boundaries, {
            "runtime_prepare": {"entered": True, "returned": True},
            "approval_broker": {"entered": True, "returned": True},
        })
        self.assertIs(sys.getprofile(), profile)
        self.assertIs(sys.gettrace(), trace)

    def test_original_exception_and_fixed_failure_evidence_survive_without_retry(self):
        runtime, cli = test_cli.project_runtime, test_cli.archive_cli
        error = OSError("Q:/synthetic/SYNTHETIC_PRIVATE_TOKEN/key")
        original_broker = cli._execute_project_version_update_exact_human_approved_write
        original_projector = cli._project_version_update_privacy_safe_failure_result
        calls = []

        def prepare(*args, **kwargs):
            calls.append((args, kwargs))
            raise error

        with mock.patch.object(runtime, "prepare_runtime_candidate", new=prepare):
            with self.assertRaises(OSError) as raised:
                with test_cli._observe_project_update_fixture_boundaries() as observation:
                    runtime.prepare_runtime_candidate("SYNTHETIC_PRIVATE_TOKEN")
            self.assertIs(raised.exception, error)
            self.assertIs(runtime.prepare_runtime_candidate, prepare)
        self.assertIs(cli._execute_project_version_update_exact_human_approved_write, original_broker)
        self.assertIs(cli._project_version_update_privacy_safe_failure_result, original_projector)
        self.assertEqual(len(calls), 1)
        payload = observation.failure_payload(native_observed=False, cli_code=1)
        self.assertEqual(payload["scope"], "synthetic_harness_only")
        self.assertFalse(payload["product_recovery_evidence"])
        self.assertFalse(payload["native_observed"])
        self.assertEqual(payload["cli"]["return_code"], 1)
        self.assertEqual(payload["boundaries"]["runtime_prepare"], {"entered": True, "returned": False})
        self.assertEqual(payload["boundaries"]["approval_broker"], {"entered": False, "returned": False})
        self.assertEqual(payload["failures"]["runtime_prepare"][0], {
            "kind": "os_error", "code": "unclassified_failure", "source": None,
        })
        serialized = json.dumps(payload)
        self.assertLess(len(serialized.encode("utf-8")), 32768)
        self.assertNotIn("SYNTHETIC_PRIVATE_TOKEN", serialized)
        self.assertNotIn("Q:/", serialized)

    def test_existing_synthetic_broker_is_not_reported_as_native_ui(self):
        cli = test_cli.archive_cli
        result = {"ok": True}
        with mock.patch.object(cli, "_execute_project_version_update_exact_human_approved_write",
                               return_value=result) as synthetic:
            with test_cli._observe_project_update_fixture_boundaries() as observation:
                self.assertIs(cli._execute_project_version_update_exact_human_approved_write(), result)
            synthetic.assert_called_once_with()
        payload = observation.failure_payload(native_observed=False, cli_code=1)
        self.assertTrue(payload["boundaries"]["approval_broker"]["returned"])
        self.assertFalse(payload["native_observed"])
        self.assertEqual(payload["failures"], {})


if __name__ == "__main__":
    unittest.main()
