"""No-download runtime reuse exercised against actual Windows venv bytes."""

import hashlib
import json
import os
import platform
import shutil
import sys
import tempfile
import threading
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


TESTS_ROOT = Path(__file__).resolve().parent
SRC_ROOT = TESTS_ROOT.parent / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(TESTS_ROOT) not in sys.path:
    sys.path.append(str(TESTS_ROOT))

from wom_kit import project_runtime
from test_project_runtime import _supply_for_dependency, _write_dependency_wheel, _write_minimal_wheel


WINDOWS_RUNTIME = os.name == "nt" and sys.version_info[:2] == (3, 12) and platform.machine().casefold() in {"amd64", "x86_64"}


class _RuntimeObservationDiagnostics:
    """Test-only failure observations, without retries, reads or global tracing.

    Each named wrapper calls the original exactly once and preserves its result
    or exception. Only fixed boundary/state codes and bounded OS error numbers
    survive; arguments, paths, bytes and exception text are never retained. A
    refused read alone does not identify which identity field changed.
    """

    _TARGETS = (
        ("inspect_runtime", "installed_inspection"),
        ("_real_component_snapshot_observation", "component_chain"),
        ("_stable_regular_file_observation", "regular_file_read"),
        ("_sha256_file", "file_hash"),
        ("_runtime_payload_observation", "payload_inventory"),
    )
    _STATES = frozenset({"passed", "failed", "unavailable", "not_reached"})
    _REASONS = frozenset({
        "path_outside_root", "path_observation_unavailable", "path_component_missing",
        "path_component_reparse", "path_component_not_directory", "path_target_kind_invalid",
        "project_runtime_static_receipt_invalid", "project_runtime_live_payload_verified",
        "project_runtime_live_payload_mismatch", "project_runtime_live_payload_unavailable",
        "project_runtime_required_python_missing", "project_runtime_required_python_unsafe",
        "project_runtime_tree_unsafe", "project_runtime_tree_case_collision",
        "project_runtime_tree_too_large",
        "project_runtime_file_unreadable_or_changed", "project_runtime_tree_unreadable",
        "project_runtime_tree_changed",
    })

    def __init__(self, module=project_runtime):
        self.module = module
        self.events = []
        self.truncated = False
        self.stack = ExitStack()
        self.owner_thread = None
        self.active_boundaries = []

    @staticmethod
    def _error_number(value):
        return value if type(value) is int and 0 <= value <= 65535 else None

    def _record(self, boundary, outcome, *, reason="unclassified", error=None, operation=None, cause_depth=0):
        if len(self.events) >= 32:
            self.truncated = True
            return
        self.events.append({
            "boundary": boundary,
            "outcome": outcome,
            "reason_code": reason if type(reason) is str and reason in self._REASONS else "unclassified",
            "errno": self._error_number(getattr(error, "errno", None)) if isinstance(error, OSError) else None,
            "winerror": self._error_number(getattr(error, "winerror", None)) if isinstance(error, OSError) else None,
            "identity_cause": "unknown",
            "operation": operation,
            "cause_depth": cause_depth,
        })

    def _record_exception(self, boundary, error):
        # Follow only explicit causes, not arbitrary exception text/context.
        # The three-step cap also bounds a malformed cyclic cause chain.
        for depth in range(3):
            reason = (
                error.args[0]
                if isinstance(error, project_runtime.ProjectRuntimeError) and len(error.args) == 1
                else "unclassified"
            )
            self._record(
                boundary, "os_error" if isinstance(error, OSError) else "exception",
                reason=reason, error=error, cause_depth=depth,
            )
            error = error.__cause__
            if error is None:
                break

    def _wrap_os_exception(self, original, operation):
        def observed(*args, **kwargs):
            try:
                return original(*args, **kwargs)
            except OSError as error:
                if threading.get_ident() == self.owner_thread and self.active_boundaries:
                    self._record(self.active_boundaries[-1], "os_error", error=error, operation=operation)
                raise
        return observed

    def _wrap(self, original, boundary):
        def observed(*args, **kwargs):
            if threading.get_ident() != self.owner_thread:
                return original(*args, **kwargs)
            self.active_boundaries.append(boundary)
            try:
                result = original(*args, **kwargs)
            except Exception as error:
                self._record_exception(boundary, error)
                raise
            finally:
                self.active_boundaries.pop()
            if boundary == "regular_file_read":
                if result is None:
                    self._record(boundary, "read_not_confirmed")
            elif boundary in {"installed_inspection", "component_chain"} and isinstance(result, dict):
                state_key = "live_payload_state" if boundary == "installed_inspection" else "state"
                reason_key = "live_payload_reason_code" if boundary == "installed_inspection" else "reason_code"
                state = result.get(state_key)
                if state != "passed":
                    outcome = state if type(state) is str and state in self._STATES else "unknown"
                    self._record(boundary, outcome, reason=result.get(reason_key))
            return result
        return observed

    def __enter__(self):
        self.owner_thread = threading.get_ident()
        try:
            for name, boundary in self._TARGETS:
                original = getattr(self.module, name)
                self.stack.enter_context(mock.patch.object(self.module, name, self._wrap(original, boundary)))
            for target, name, operation in (
                (Path, "lstat", "path_lstat"),
                (os, "open", "os_open"),
                (os, "fstat", "os_fstat"),
            ):
                original = getattr(target, name)
                self.stack.enter_context(mock.patch.object(target, name, self._wrap_os_exception(original, operation)))
        except BaseException:
            self.stack.close()
            raise
        return self

    def __exit__(self, *exception_info):
        return self.stack.__exit__(*exception_info)

    def snapshot(self):
        return {
            "schema": "runtime-noop-observation/v0.1",
            "scope": "synthetic_test_only",
            "events": [dict(event) for event in self.events],
            "truncated": self.truncated,
        }


class RuntimeObservationDiagnosticTests(unittest.TestCase):
    def subject(self, function):
        return SimpleNamespace(**{name: function for name, _boundary in _RuntimeObservationDiagnostics._TARGETS})

    def test_named_wrappers_forward_once_and_leave_trace_and_profile_unchanged(self):
        calls = []
        result = {"state": "passed", "live_payload_state": "passed"}
        argument = object()

        def original(*args, **kwargs):
            calls.append((args, kwargs))
            return result

        subject = self.subject(original)
        prior_trace, prior_profile = sys.gettrace(), sys.getprofile()
        os_functions = (Path.lstat, os.open, os.fstat)
        with _RuntimeObservationDiagnostics(subject) as diagnostic:
            for name, _boundary in diagnostic._TARGETS:
                self.assertIs(getattr(subject, name)(argument, marker=argument), result)
            self.assertEqual(diagnostic.snapshot()["events"], [])
        self.assertEqual(len(calls), len(_RuntimeObservationDiagnostics._TARGETS))
        for args, kwargs in calls:
            self.assertIs(args[0], argument)
            self.assertIs(kwargs["marker"], argument)
        for name, _boundary in diagnostic._TARGETS:
            self.assertIs(getattr(subject, name), original)
        self.assertIs(sys.gettrace(), prior_trace)
        self.assertIs(sys.getprofile(), prior_profile)
        self.assertEqual((Path.lstat, os.open, os.fstat), os_functions)
        self.assertEqual(diagnostic.active_boundaries, [])

    def test_original_os_error_is_rethrown_without_private_text(self):
        error = OSError(5, "private_diagnostic_marker", "private_path_marker")
        error.winerror = 32
        calls = []

        def original():
            calls.append(True)
            raise error

        subject = self.subject(original)
        with self.assertRaises(OSError) as caught:
            with _RuntimeObservationDiagnostics(subject) as diagnostic:
                subject._stable_regular_file_observation()
        self.assertIs(caught.exception, error)
        self.assertEqual(calls, [True])
        self.assertIs(subject._stable_regular_file_observation, original)
        event = diagnostic.snapshot()["events"][0]
        self.assertEqual((event["boundary"], event["outcome"], event["errno"], event["winerror"]),
                         ("regular_file_read", "os_error", 5, 32))
        self.assertNotIn("private", json.dumps(diagnostic.snapshot()))

    def test_refused_result_is_unchanged_and_unknown_details_are_not_copied(self):
        result = {
            "state": "unavailable", "reason_code": "private_diagnostic_marker",
            "snapshot": ["private_path_marker"], "live_payload_state": "private_state_marker",
            "live_payload_reason_code": "private_reason_marker",
        }
        subject = self.subject(lambda: result)
        with _RuntimeObservationDiagnostics(subject) as diagnostic:
            self.assertIs(subject._real_component_snapshot_observation(), result)
            self.assertIs(subject.inspect_runtime(), result)
        events = diagnostic.snapshot()["events"]
        self.assertEqual([event["outcome"] for event in events], ["unavailable", "unknown"])
        self.assertTrue(all(event["reason_code"] == "unclassified" for event in events))
        self.assertTrue(all(event["identity_cause"] == "unknown" for event in events))
        self.assertNotIn("private", json.dumps(diagnostic.snapshot()))

    def test_records_are_bounded_and_snapshot_is_detached(self):
        subject = self.subject(lambda: None)
        with _RuntimeObservationDiagnostics(subject) as diagnostic:
            for _index in range(40):
                self.assertIsNone(subject._stable_regular_file_observation())
        snapshot = diagnostic.snapshot()
        self.assertEqual(len(snapshot["events"]), 32)
        self.assertTrue(snapshot["truncated"])
        snapshot["events"][0]["boundary"] = "private_mutation_marker"
        self.assertNotIn("private", json.dumps(diagnostic.snapshot()))

    def test_body_exception_and_partial_entry_restore_originals(self):
        original = lambda: None
        subject = self.subject(original)
        error = RuntimeError("private_body_marker")
        os_functions = (Path.lstat, os.open, os.fstat)
        with self.assertRaises(RuntimeError) as caught:
            with _RuntimeObservationDiagnostics(subject):
                raise error
        self.assertIs(caught.exception, error)
        for name, _boundary in _RuntimeObservationDiagnostics._TARGETS:
            self.assertIs(getattr(subject, name), original)
        self.assertEqual((Path.lstat, os.open, os.fstat), os_functions)
        del subject._stable_regular_file_observation
        with self.assertRaises(AttributeError):
            with _RuntimeObservationDiagnostics(subject):
                self.fail("incomplete subject must not enter")
        self.assertIs(subject.inspect_runtime, original)
        self.assertIs(subject._real_component_snapshot_observation, original)

    def test_error_number_bounds_do_not_accept_bool_or_private_values(self):
        for value in (True, -1, 65536, "private_number_marker", object()):
            with self.subTest(value_type=type(value).__name__):
                self.assertIsNone(_RuntimeObservationDiagnostics._error_number(value))
        self.assertEqual(_RuntimeObservationDiagnostics._error_number(0), 0)
        self.assertEqual(_RuntimeObservationDiagnostics._error_number(65535), 65535)

    def test_real_reader_caught_lstat_error_has_only_fixed_os_evidence(self):
        with tempfile.TemporaryDirectory(prefix="wom-observation-contract-") as temporary:
            target = Path(temporary) / "fixture.bin"
            target.write_bytes(b"synthetic bytes")
            original_lstat = Path.lstat

            def unavailable(path, *args, **kwargs):
                if path == target:
                    raise PermissionError(13, "private_read_marker", "private_path_marker")
                return original_lstat(path, *args, **kwargs)

            with mock.patch.object(Path, "lstat", unavailable), _RuntimeObservationDiagnostics() as diagnostic:
                result = project_runtime._stable_regular_file_observation(
                    target, limit=64, ancestor_root=target.parent, collect_bytes=False,
                )
            self.assertIsNone(result)
            events = diagnostic.snapshot()["events"]
            self.assertEqual(events[0]["operation"], "path_lstat")
            self.assertEqual(events[0]["outcome"], "os_error")
            self.assertEqual(events[0]["errno"], 13)
            self.assertIsNone(events[0]["winerror"])
            self.assertEqual(events[-1]["outcome"], "read_not_confirmed")
            self.assertTrue(all(event["identity_cause"] == "unknown" for event in events))
            self.assertNotIn("private", json.dumps(diagnostic.snapshot()))

    def test_real_reader_open_and_fstat_errors_are_observed_before_original_catch(self):
        with tempfile.TemporaryDirectory(prefix="wom-observation-contract-") as temporary:
            target = Path(temporary) / "fixture.bin"
            target.write_bytes(b"synthetic bytes")
            for name in ("open", "fstat"):
                with self.subTest(operation=name):
                    original = getattr(os, name)
                    error = OSError(13, "private_os_marker", "private_path_marker")
                    error.winerror = 32
                    with mock.patch.object(os, name, side_effect=error) as fault:
                        with _RuntimeObservationDiagnostics() as diagnostic:
                            result = project_runtime._stable_regular_file_observation(
                                target, limit=64, ancestor_root=target.parent, collect_bytes=False,
                            )
                        fault.assert_called_once()
                    self.assertIs(getattr(os, name), original)
                    self.assertIsNone(result)
                    event = diagnostic.snapshot()["events"][0]
                    self.assertEqual(event["operation"], "os_" + name)
                    self.assertEqual((event["errno"], event["winerror"]), (13, 32))
                    self.assertEqual(diagnostic.snapshot()["events"][-1]["outcome"], "read_not_confirmed")
                    self.assertNotIn("private", json.dumps(diagnostic.snapshot()))

    def test_os_success_returns_same_value_without_retaining_or_recording_it(self):
        value = object()
        subject = self.subject(lambda: os.fstat(123))
        with mock.patch.object(os, "fstat", return_value=value) as original:
            with _RuntimeObservationDiagnostics(subject) as diagnostic:
                self.assertIs(subject._stable_regular_file_observation(), value)
            original.assert_called_once_with(123)
        self.assertEqual(diagnostic.snapshot()["events"], [])

    def test_os_errors_outside_named_boundary_and_other_thread_are_not_recorded(self):
        error = OSError(5, "private_thread_marker")
        caught = []
        subject = self.subject(lambda: os.fstat(123))

        def call_from_other_thread():
            try:
                subject._stable_regular_file_observation()
            except OSError as observed:
                caught.append(observed)

        with mock.patch.object(os, "fstat", side_effect=error) as original:
            with _RuntimeObservationDiagnostics(subject) as diagnostic:
                with self.assertRaises(OSError) as outside:
                    os.fstat(123)
                self.assertIs(outside.exception, error)
                worker = threading.Thread(target=call_from_other_thread)
                worker.start()
                worker.join(timeout=5)
                self.assertFalse(worker.is_alive())
                self.assertEqual(diagnostic.snapshot()["events"], [])
            self.assertEqual(original.call_count, 2)
        self.assertEqual(caught, [error])
        self.assertEqual(diagnostic.active_boundaries, [])

    def test_fixed_project_error_causes_are_bounded_and_private_text_is_not_copied(self):
        os_error = OSError(13, "private_cause_marker", "private_path_marker")
        os_error.winerror = 32
        error = project_runtime.ProjectRuntimeError("project_runtime_tree_unreadable")
        error.__cause__ = os_error
        os_error.__cause__ = RuntimeError("private_nested_marker")
        os_error.__cause__.__cause__ = RuntimeError("private_fourth_marker")

        def original():
            raise error

        subject = self.subject(original)
        with self.assertRaises(project_runtime.ProjectRuntimeError) as caught:
            with _RuntimeObservationDiagnostics(subject) as diagnostic:
                subject._runtime_payload_observation()
        self.assertIs(caught.exception, error)
        events = diagnostic.snapshot()["events"]
        self.assertEqual(len(events), 3)
        self.assertEqual([event["cause_depth"] for event in events], [0, 1, 2])
        self.assertEqual(events[0]["reason_code"], "project_runtime_tree_unreadable")
        self.assertEqual((events[1]["errno"], events[1]["winerror"]), (13, 32))
        self.assertNotIn("private", json.dumps(diagnostic.snapshot()))


@unittest.skipUnless(WINDOWS_RUNTIME, "Real Windows CPython 3.12 runtime")
class ExistingRuntimeNoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="wom-noop-fixture-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.project = cls.root / "project"
        cls.runtime = project_runtime.runtime_path(cls.project, "0.4.3")
        artifacts = cls.runtime / project_runtime.PROJECT_RUNTIME_ARTIFACTS_NAME
        artifacts.mkdir(parents=True)
        wheel = _write_minimal_wheel(artifacts, "0.4.3")
        dependency = _write_dependency_wheel(artifacts)
        cls.supply = _supply_for_dependency(dependency)
        cls.bootstrap = project_runtime.BootstrapWheel(
            version="0.4.3", tag="v0.4.3", url="https://invalid.example/never-used",
            sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(), file_name=wheel.name,
        )
        (artifacts / project_runtime.PROJECT_RUNTIME_RETAINED_LOCK_NAME).write_bytes(cls.supply.raw_bytes)
        verification, packages, python_version = project_runtime._initialize_runtime_payload(
            cls.runtime, wheelhouse=artifacts, wheel_paths=[wheel, dependency],
            bootstrap=cls.bootstrap, supply=cls.supply,
            stage_prefix="synthetic-noop-fixture", progress_callback=None,
        )
        inventory = [
            project_runtime._artifact_inventory_entry(
                role="runtime", distribution="wom-kit", version="0.4.3", file_name=wheel.name,
                size_bytes=wheel.stat().st_size, sha256=cls.bootstrap.sha256,
            ),
            *[
                project_runtime._artifact_inventory_entry(
                    role=item.role, distribution=item.distribution, version=item.version,
                    file_name=item.file_name, size_bytes=item.size_bytes, sha256=item.sha256,
                ) for item in cls.supply.artifacts
            ],
        ]
        receipt = {
            "schema": project_runtime.PROJECT_RUNTIME_RECEIPT_SCHEMA,
            "status": "verified", "created_at": "2026-09-05T00:00:00Z",
            "target_tag": "v0.4.3", "target_version": "0.4.3", "target_commit": "b" * 40,
            "wheel_file_name": wheel.name, "wheel_sha256": "sha256:" + cls.bootstrap.sha256,
            "supply_lock_sha256": "sha256:" + cls.supply.sha256,
            "artifact_inventory": sorted(inventory, key=lambda item: item["file_name"].casefold()),
            "installed_payload_sha256": "sha256:" + project_runtime._runtime_payload_sha256(cls.runtime),
            "python_version": python_version, "installer_running_version": "0.4.3",
            "installed_distributions": packages, "verification": verification,
            "global_path_mutation": False, "previous_runtime_deleted": False, "absolute_paths_echoed": False,
        }
        cls.receipt_path = cls.runtime / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME
        cls.receipt_bytes = (json.dumps(receipt, indent=2) + "\n").encode()
        cls.receipt_path.write_bytes(cls.receipt_bytes)
        project_runtime._candidate_receipt_document(cls.receipt_bytes)

    def observe(self):
        with _RuntimeObservationDiagnostics() as diagnostic:
            try:
                return project_runtime.verify_existing_runtime_for_noop(
                    self.project, target="v0.4.3", target_commit="b" * 40,
                    bootstrap=self.bootstrap, supply=self.supply,
                )
            finally:
                self.observation_diagnostics = diagnostic.snapshot()

    def observation_failure_details(self, observed):
        # unittest formats this only when an assertion fails; nothing is printed
        # by the observer or added to the production result/receipt.
        return {"observed": observed, "test_observation": self.observation_diagnostics}

    def refresh_forged_receipt_hash(self):
        receipt = json.loads(self.receipt_bytes)
        receipt["installed_payload_sha256"] = "sha256:" + project_runtime._runtime_payload_sha256(self.runtime)
        self.receipt_path.write_bytes((json.dumps(receipt, indent=2) + "\n").encode())

    def test_valid_runtime_runs_real_checks_without_download_install_or_file_changes(self):
        before = project_runtime._candidate_inventory_snapshot(self.runtime)
        native_run = project_runtime._run_bounded
        with mock.patch.object(project_runtime, "_run_bounded", wraps=native_run) as runs, mock.patch.object(project_runtime, "_download_exact_artifact", side_effect=AssertionError("no network permitted")), mock.patch.object(project_runtime, "_initialize_runtime_payload", side_effect=AssertionError("no candidate permitted")):
            observed = self.observe()
        self.assertEqual(observed["state"], "passed", self.observation_failure_details(observed))
        self.assertTrue(observed["reusable"])
        self.assertFalse(observed["repair_required"])
        self.assertEqual(project_runtime._candidate_inventory_snapshot(self.runtime), before)
        self.assertEqual(self.receipt_path.read_bytes(), self.receipt_bytes)
        stages = {call.kwargs["stage"] for call in runs.call_args_list}
        self.assertTrue({"project-runtime-noop-pip-check", "project-runtime-noop-version", "project-runtime-noop-resources", "project-runtime-noop-new-process"} <= stages)
        for call in runs.call_args_list:
            self.assertIn("-I", call.args[0])
            self.assertIn("-B", call.args[0])
        self.assertNotIn(str(self.project), json.dumps(observed))

    def test_forged_receipt_cannot_authorize_tampered_startup_or_package(self):
        relative_paths = ("Scripts/python.exe", "pyvenv.cfg", "Lib/site-packages/wom_kit/__init__.py", "unapproved.dll")
        for relative in relative_paths:
            with self.subTest(relative=relative):
                target = self.runtime / relative
                original = target.read_bytes() if target.exists() else None
                try:
                    target.write_bytes(b"forged-untrusted-startup\n")
                    self.refresh_forged_receipt_hash()
                    with mock.patch.object(project_runtime, "_run_bounded", side_effect=AssertionError("untrusted process must not run")):
                        observed = self.observe()
                    self.assertEqual(observed["state"], "failed", self.observation_failure_details(observed))
                    self.assertFalse(observed["reusable"])
                    self.assertTrue(observed["repair_required"])
                finally:
                    if original is None:
                        target.unlink()
                    else:
                        target.write_bytes(original)
                    self.receipt_path.write_bytes(self.receipt_bytes)

    def test_missing_retained_wheel_is_repair_required_before_process_execution(self):
        wheel = self.runtime / project_runtime.PROJECT_RUNTIME_ARTIFACTS_NAME / self.bootstrap.file_name
        original = wheel.read_bytes()
        try:
            wheel.unlink()
            with mock.patch.object(project_runtime, "_run_bounded", side_effect=AssertionError("untrusted process must not run")):
                observed = self.observe()
            self.assertEqual(observed["state"], "failed", self.observation_failure_details(observed))
            self.assertTrue(observed["repair_required"])
        finally:
            wheel.write_bytes(original)

    def test_runtime_access_failure_is_not_repair_authority(self):
        native_lstat = Path.lstat

        def unavailable(path, *args, **kwargs):
            if path == self.runtime:
                raise PermissionError("synthetic unavailable")
            return native_lstat(path, *args, **kwargs)

        with mock.patch.object(Path, "lstat", unavailable):
            observed = self.observe()
        self.assertEqual(observed["state"], "unavailable", self.observation_failure_details(observed))
        self.assertFalse(observed["repair_required"])

    def test_fresh_probe_timeout_or_launch_failure_is_not_repair_authority(self):
        for error in (
            project_runtime.ProjectRuntimeError("project-runtime-noop-pip-check_timeout"),
            project_runtime.ProjectRuntimeError("project-runtime-noop-pip-check_failed"),
            OSError("synthetic child launch unavailable"),
        ):
            with self.subTest(error_type=type(error).__name__, reason=str(error)):
                # Static package/startup verification is real; only the first
                # subprocess boundary fails to return usable evidence.
                with mock.patch.object(project_runtime, "_run_bounded", side_effect=error):
                    observed = self.observe()
                self.assertEqual(observed["state"], "unavailable", self.observation_failure_details(observed))
                self.assertFalse(observed["repair_required"])
                self.assertFalse(observed["reusable"])

    def test_new_process_drift_invalidates_noop_proof(self):
        native_run = project_runtime._run_bounded
        unexpected = self.runtime / "unexpected"

        def drift_after_execution(*args, **kwargs):
            result = native_run(*args, **kwargs)
            if kwargs.get("stage") == "project-runtime-noop-python-version":
                unexpected.write_bytes(b"changed during verification")
            return result

        try:
            with mock.patch.object(project_runtime, "_run_bounded", side_effect=drift_after_execution):
                observed = self.observe()
            self.assertEqual(observed["state"], "failed", self.observation_failure_details(observed))
            self.assertEqual(observed["reason_code"], "project_runtime_existing_payload_changed")
            self.assertFalse(observed["repair_required"])
            self.assertFalse(observed["reusable"])
        finally:
            unexpected.unlink(missing_ok=True)

    def test_observed_generation_change_is_not_repair_authority(self):
        for reason in (
            "project_runtime_existing_receipt_changed",
            "project_runtime_existing_payload_changed",
            "project_runtime_tree_changed",
            "project_runtime_candidate_concurrent_drift",
        ):
            with self.subTest(reason=reason), mock.patch.object(
                project_runtime, "_candidate_inventory_snapshot",
                side_effect=project_runtime.ProjectRuntimeError(reason),
            ), mock.patch.object(project_runtime, "_run_bounded") as process:
                observed = self.observe()
            self.assertEqual(observed["state"], "failed")
            self.assertEqual(observed["reason_code"], reason)
            self.assertFalse(observed["repair_required"])
            self.assertFalse(observed["reusable"])
            process.assert_not_called()

    def test_retained_wheel_mutation_during_static_verification_cannot_authorize_repair(self):
        wheel = self.runtime / project_runtime.PROJECT_RUNTIME_ARTIFACTS_NAME / self.bootstrap.file_name
        original = wheel.read_bytes()
        verify = project_runtime._verify_retained_artifacts

        def change_after_captured_inventory(*args, **kwargs):
            wheel.write_bytes(original + b"synthetic concurrent artifact mutation")
            return verify(*args, **kwargs)

        try:
            with mock.patch.object(
                project_runtime, "_verify_retained_artifacts", side_effect=change_after_captured_inventory,
            ), mock.patch.object(project_runtime, "_run_bounded") as process:
                observed = self.observe()
            self.assertEqual(observed["state"], "failed")
            self.assertEqual(observed["reason_code"], "project_runtime_existing_payload_changed")
            self.assertFalse(observed["repair_required"])
            process.assert_not_called()
        finally:
            wheel.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
