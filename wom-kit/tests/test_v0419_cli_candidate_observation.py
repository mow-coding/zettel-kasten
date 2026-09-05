"""Small contracts for the existing candidate fixture's failure-only observer."""

import json
import sys
import unittest
from unittest import mock

import test_cli


class CliCandidateObservationTests(unittest.TestCase):
    def test_source_fixture_enters_and_restores_same_component_observer(self):
        services = test_cli.archive_services
        original = services._project_update_live_component_sha256
        raised_error = RuntimeError("SYNTHETIC_PRIVATE_TOKEN")
        with self.assertRaises(RuntimeError) as raised:
            with test_cli._observe_project_update_fixture_boundaries():
                self.assertIsNot(services._project_update_live_component_sha256, original)
                raise raised_error
        self.assertIs(raised.exception, raised_error)
        self.assertIs(services._project_update_live_component_sha256, original)

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
