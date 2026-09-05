"""Cheap contracts for the first-update diagnostic, without creating a venv."""

import json
import sys
import unittest
from unittest import mock

from wom_kit import archive_services, exact_human_approval_workflow
from test_v0419_update_noop_journey import _FirstUpdateObservation


class FirstUpdateObservationTests(unittest.TestCase):
    def test_boundary_forwards_original_arguments_and_result_once_without_profiling(self):
        observer = _FirstUpdateObservation()
        private_argument, result = object(), object()
        calls = []
        profile, trace = sys.getprofile(), sys.gettrace()

        def original(value, *, selected):
            calls.append((value, selected))
            return result

        wrapped = observer.boundary("runtime_prepare", original)
        self.assertIs(wrapped(private_argument, selected=private_argument), result)
        self.assertEqual(calls, [(private_argument, private_argument)])
        self.assertEqual(observer.boundaries["runtime_prepare"], {"entered": True, "returned": True})
        self.assertIs(sys.getprofile(), profile)
        self.assertIs(sys.gettrace(), trace)

    def test_original_exception_identity_is_preserved_and_private_details_are_absent(self):
        for error in (TypeError("PRIVATE_TOKEN"), IndexError("PRIVATE_TOKEN"),
                      OSError("Q:/synthetic/PRIVATE_TOKEN/key")):
            with self.subTest(kind=type(error).__name__):
                observer = _FirstUpdateObservation()

                def original():
                    raise error

                with self.assertRaises(type(error)) as captured:
                    observer.boundary("runtime_prepare", original)()
                self.assertIs(captured.exception, error)
                result = observer.diagnostic(native_observed=False)
                self.assertNotIn("PRIVATE_TOKEN", result)
                self.assertNotIn("Q:/", result)
                self.assertNotIn("test_v0419_update_noop_observation", result)
                self.assertIsNone(observer.failures["runtime_prepare"][0]["source"])
                self.assertFalse(observer.boundaries["runtime_prepare"]["returned"])

    def test_projector_keeps_result_and_exception_unchanged_and_restores_patch(self):
        observer = _FirstUpdateObservation()
        error = ValueError("PRIVATE_TOKEN")
        result, calls = object(), []

        def original(value):
            calls.append(value)
            return result

        holder = mock.Mock()
        holder.project = original
        with mock.patch.object(holder, "project", new=observer.failure_projector(original)):
            self.assertIs(holder.project(error), result)
        self.assertIs(holder.project, original)
        self.assertEqual(calls, [error])
        self.assertEqual(observer.failures["cli_failure_projection"][0]["kind"], "value_error")
        self.assertNotIn("PRIVATE_TOKEN", observer.diagnostic(native_observed=False))

    def test_actual_known_repository_frame_is_relative_and_bounded(self):
        observer = _FirstUpdateObservation()
        # Genuine production validation throws before any filesystem/provider
        # access. Its exact code object, not a path-shaped string, is allowed.
        with self.assertRaises(archive_services.ArchiveServiceError):
            observer.boundary("approval_broker",
                archive_services._wom_kit_project_version_update_live_approval_transaction)(
                    None, target="", reviewed_by="", affirm_external_writers_quiescent=False,
                    approval_executor=None)
        error = observer.failures["approval_broker"][0]
        self.assertEqual(error["code"], "project_version_update_live_approval_executor_required")
        self.assertEqual(error["source"]["file"], "wom-kit/src/wom_kit/archive_services.py")
        self.assertEqual(error["source"]["function"],
                         "_wom_kit_project_version_update_live_approval_transaction")
        self.assertIs(type(error["source"]["line"]), int)
        self.assertGreater(error["source"]["line"], 0)
        self.assertNotIn(str(archive_services.__file__), observer.diagnostic(native_observed=False))

    def test_spoofed_filename_and_function_are_not_known_code_objects(self):
        observer = _FirstUpdateObservation()
        namespace = {}
        exec(compile("def _wom_kit_project_version_update_live_approval_transaction():\n"
                     "    raise IndexError('PRIVATE_TOKEN')\n", archive_services.__file__, "exec"), namespace)
        with self.assertRaises(IndexError):
            observer.boundary("approval_broker",
                namespace["_wom_kit_project_version_update_live_approval_transaction"])()
        error = observer.failures["approval_broker"][0]
        self.assertEqual(error["kind"], "index_error")
        self.assertIsNone(error["source"])
        self.assertNotIn("PRIVATE_TOKEN", observer.diagnostic(native_observed=False))

    def test_wrapped_hidden_context_has_only_fixed_codes_and_cycle_bound(self):
        observer = _FirstUpdateObservation()
        original = TypeError("PRIVATE_TOKEN")
        wrapped = exact_human_approval_workflow.ExactHumanApprovalWorkflowError(
            "exact_human_approval_state_unknown")
        wrapped.__context__ = original
        wrapped.__suppress_context__ = True
        original.__context__ = wrapped
        observer.record("cli_failure_projection", wrapped)
        chain = observer.failures["cli_failure_projection"]
        self.assertEqual(len(chain), 2)
        self.assertEqual(chain[0]["code"], "exact_human_approval_state_unknown")
        self.assertEqual(chain[1]["kind"], "type_error")
        self.assertNotIn("PRIVATE_TOKEN", observer.diagnostic(native_observed=False))
        wrapped.code = "PRIVATE_TOKEN"
        observer.record("first_cli_call", wrapped)
        self.assertEqual(observer.failures["first_cli_call"][0]["code"], "unclassified_failure")
        self.assertNotIn("PRIVATE_TOKEN", json.dumps(observer.failures))

    def test_unknown_stage_is_rejected_without_echoing_it(self):
        observer = _FirstUpdateObservation()
        with self.assertRaisesRegex(ValueError, "^unknown_observation_stage$"):
            observer.record("PRIVATE_STAGE", ValueError("PRIVATE_TOKEN"))
        self.assertEqual(observer.failures, {})
