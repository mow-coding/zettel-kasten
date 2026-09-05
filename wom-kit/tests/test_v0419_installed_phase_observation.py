"""Harness-only phase protocol tests; no WOM runtime/venv or provider setup."""
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

from test_wheel_install import check_wheel_install as checker


def load_driver():
    spec = importlib.util.spec_from_file_location("runtime_phase_driver", checker.RUNTIME_JOURNEY_TOOL)
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    return driver


def line(sequence, stage, event, elapsed_ms, **extra):
    item = {"schema": checker.RUNTIME_PHASE_SCHEMA, "sequence": sequence,
            "stage": stage, "event": event, "elapsed_ms": elapsed_ms, **extra}
    return checker.RUNTIME_PHASE_PREFIX + json.dumps(item, separators=(",", ":")).encode("ascii") + b"\n"


def valid_prefix(observer):
    observer.feed(line(1, "bootstrap_import", "begin", 0)
                  + line(2, "bootstrap_import", "passed", 20))


class RuntimePhaseProtocolTests(unittest.TestCase):
    def test_reporter_contract_all_stages_and_original_stderr_are_separate_from_cli(self):
        driver = load_driver()
        self.assertEqual(driver.PHASES, checker.RUNTIME_PHASES)
        self.assertEqual(driver.PHASE_SCHEMA, checker.RUNTIME_PHASE_SCHEMA)
        self.assertEqual(driver.PHASE_PREFIX.encode("ascii"), checker.RUNTIME_PHASE_PREFIX)
        output, cli_output = io.StringIO(), io.StringIO()
        ticks = iter(range(37))
        with redirect_stderr(output):
            reporter = driver.PhaseReporter(clock=lambda: next(ticks))
        with redirect_stderr(cli_output):
            for stage in driver.PHASES:
                reporter.begin(stage)
                reporter.passed()
        self.assertEqual(cli_output.getvalue(), "")
        observer = checker.RuntimePhaseObservation()
        payload = output.getvalue().encode("ascii")
        for start in range(0, len(payload), 7):
            observer.feed(payload[start:start + 7])
        observer.end_stream()
        observer.require_complete()
        observer.finish(success=True)
        result = observer.public_payload()
        self.assertEqual(result["validated_event_count"], 36)
        self.assertEqual(result["observation_status"], "complete")
        self.assertFalse(result["product_recovery_evidence"])
        self.assertEqual(result["scope"], "synthetic_harness_only")
        self.assertTrue(all(row["state"] == "passed" and row["duration_ms"] == 1000 for row in result["stages"]))

    def test_driver_failure_preserves_fixed_phase_and_original_final_json_contract(self):
        driver = load_driver()
        original_error = RuntimeError("private_lowercase_token_marker")

        def actual_failure(*_args, phases):
            phases.begin("bootstrap_import")
            raise original_error

        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(driver.sys, "argv", ["tool", "wheel", "source", "shim", "fixture", "0.4.19"]), mock.patch.object(
            driver, "run_journey", side_effect=actual_failure,
        ), redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(driver.main(), 1)
        self.assertEqual(json.loads(stdout.getvalue()), {"ok": False, "schema": driver.SCHEMA,
                         "reason_code": "installed_runtime_journey_failed"})
        self.assertNotIn("private_lowercase_token_marker", stdout.getvalue() + stderr.getvalue())
        observer = checker.RuntimePhaseObservation()
        observer.feed(stderr.getvalue().encode("ascii"))
        observer.end_stream()
        observer.finish(success=False)
        result = observer.public_payload()
        self.assertEqual(result["stages"][0]["state"], "failed")
        self.assertIsNotNone(result["stages"][0]["duration_ms"])
        self.assertTrue(all(row["state"] == "not_reached" for row in result["stages"][1:]))

    def test_timeout_keeps_completed_prefix_and_unknown_active_completion(self):
        observer = checker.RuntimePhaseObservation()
        valid_prefix(observer)
        observer.feed(line(3, "synthetic_project", "begin", 25))
        observer.mark_timeout()
        observer.finish(success=False)
        result = observer.public_payload()
        self.assertEqual(result["reason_code"], "harness_timeout")
        self.assertTrue(result["product_completion_unknown"])
        self.assertEqual(result["last_completed_stage"], "bootstrap_import")
        self.assertEqual(result["unfinished_stage"], "synthetic_project")
        self.assertEqual(result["stages"][1], {"stage": "synthetic_project", "state": "failed",
                         "started_at_ms": 25, "completed_at_ms": None, "duration_ms": None})
        self.assertFalse(result["protocol_invalid"])
        observer.feed(b"late private text after containment closed")
        self.assertEqual(observer.public_payload(), result)

    def test_strict_types_sequence_time_privacy_and_bounds_preserve_validated_prefix(self):
        good = line(3, "synthetic_project", "begin", 20)
        cases = [
            b"private_path_or_token\n", good.replace(b'"sequence":3', b'"sequence":true'),
            good.replace(b'"sequence":3', b'"sequence":4'), good.replace(b'"elapsed_ms":20', b'"elapsed_ms":false'),
            good.replace(b'"elapsed_ms":20', b'"elapsed_ms":NaN'),
            good.replace(b'"elapsed_ms":20', b'"elapsed_ms":Infinity'),
            good.replace(b'"elapsed_ms":20', b'"elapsed_ms":19'),
            good.replace(b'"elapsed_ms":20', b'"elapsed_ms":1200001'),
            good.replace(b'"sequence":3', b'"sequence":3,"sequence":3'),
            line(3, "private_stage", "begin", 20), line(3, "synthetic_project", "private_event", 20),
            line(3, "synthetic_project", "passed", 20),
            line(3, "synthetic_project", "begin", 20, private_key="private_value"),
            b"x" * (checker.RUNTIME_PHASE_LINE_BYTES + 1),
            b"x" * (checker.RUNTIME_PHASE_STREAM_BYTES + 1),
            checker.RUNTIME_PHASE_PREFIX + b"[1,2,3]\n", b"\xff\n",
        ]
        for payload in cases:
            with self.subTest(case=cases.index(payload)):
                observer = checker.RuntimePhaseObservation()
                valid_prefix(observer)
                with self.assertRaises(checker.WheelCheckError) as caught:
                    observer.feed(payload)
                self.assertNotIn("private", str(caught.exception))
                observer.finish(success=False)
                result = observer.public_payload()
                self.assertEqual(result["validated_event_count"], 2)
                self.assertEqual(result["stages"][0]["state"], "passed")
                self.assertTrue(result["protocol_invalid"])
                self.assertEqual(result["reason_code"], "protocol_invalid")
                self.assertNotIn("private_", json.dumps(result))

    def test_deadline_tail_and_missing_newline_do_not_discard_valid_prefix(self):
        for tail in (line(4, "synthetic_project", "passed", 1200001), b"partial"):
            observer = checker.RuntimePhaseObservation()
            valid_prefix(observer)
            observer.feed(line(3, "synthetic_project", "begin", 1199999))
            try:
                observer.feed(tail)
            except checker.WheelCheckError:
                pass
            observer.mark_timeout()
            observer.finish(success=False)
            result = observer.public_payload()
            self.assertEqual(result["validated_event_count"], 3)
            self.assertTrue(result["protocol_invalid"])
            self.assertEqual(result["reason_code"], "harness_timeout")
            self.assertEqual(result["stages"][0]["duration_ms"], 20)
            self.assertIsNone(result["stages"][1]["duration_ms"])

    def test_failure_or_empty_stream_never_becomes_complete_and_payload_is_detached(self):
        observer = checker.RuntimePhaseObservation()
        observer.feed(line(1, "bootstrap_import", "begin", 0)
                      + line(2, "bootstrap_import", "failed", 1))
        with self.assertRaises(checker.WheelCheckError):
            observer.feed(line(3, "synthetic_project", "begin", 2))
        with self.assertRaises(checker.WheelCheckError):
            observer.require_complete()
        observer.finish(success=True)
        holder = checker.WheelPartialEvidence()
        holder.record_phases(observer)
        result = holder.public_payload()
        result["installed_runtime_harness_observation"]["stages"][0]["state"] = "passed"
        self.assertEqual(holder.public_payload()["installed_runtime_harness_observation"]["stages"][0]["state"], "failed")
        with self.assertRaises(checker.WheelCheckError):
            holder.record_phases({"private": "material"})
        empty = checker.RuntimePhaseObservation()
        with self.assertRaises(checker.WheelCheckError):
            empty.require_complete()

    def test_outer_hook_failure_retains_observations_without_full_runtime_proof(self):
        holder = checker.WheelPartialEvidence()
        root = Path(tempfile.gettempdir())

        def timeout(*_args, stderr_observer, **_kwargs):
            valid_prefix(stderr_observer)
            stderr_observer.feed(line(3, "synthetic_project", "begin", 30))
            stderr_observer.mark_timeout()
            raise checker.WheelCheckError("installed runtime journey exceeded the execution timeout.")

        with mock.patch.object(checker.os, "name", "nt"), mock.patch.object(checker.sys, "version_info", (3, 12)), mock.patch.object(
            checker, "_run_installed_entrypoint", side_effect=timeout,
        ), redirect_stderr(io.StringIO()), self.assertRaises(checker.WheelCheckError):
            checker._check_installed_v0419_runtime_journey(root / "python", root / "wheel", root / "source",
                root / "fixture", cwd=root, expected_package_version="0.4.19", partial_evidence=holder)
        evidence = holder.public_payload()
        self.assertEqual(set(evidence), {"installed_runtime_harness_observation"})
        self.assertEqual(evidence["installed_runtime_harness_observation"]["unfinished_stage"], "synthetic_project")

        def failed_check(_wheel_output_dir, *, partial_evidence):
            return checker._check_installed_v0419_runtime_journey(root / "python", root / "wheel", root / "source",
                root / "fixture", cwd=root, expected_package_version="0.4.19", partial_evidence=partial_evidence)

        output = io.StringIO()
        with mock.patch.object(checker.os, "name", "nt"), mock.patch.object(checker.sys, "version_info", (3, 12)), mock.patch.object(
            checker, "_run_installed_entrypoint", side_effect=timeout,
        ), mock.patch.object(checker, "check_wheel", side_effect=failed_check), mock.patch.object(
            checker.sys, "argv", ["checker", "--format", "json"],
        ), redirect_stderr(io.StringIO()), redirect_stdout(output):
            self.assertEqual(checker.main(), 1)
        final = json.loads(output.getvalue())
        self.assertFalse(final["ok"])
        self.assertEqual(final["partial_evidence"], evidence)
        self.assertNotIn("installed_v0419_runtime_journey", final["partial_evidence"])

    def test_all_passed_prefix_plus_invalid_tail_is_not_promoted_to_success(self):
        observer = checker.RuntimePhaseObservation()
        for index, stage in enumerate(checker.RUNTIME_PHASES):
            observer.feed(line(index * 2 + 1, stage, "begin", index * 2)
                          + line(index * 2 + 2, stage, "passed", index * 2 + 1))
        with self.assertRaises(checker.WheelCheckError):
            observer.feed(b"unknown_private_material\n")
        with self.assertRaises(checker.WheelCheckError):
            observer.require_complete()
        observer.finish(success=True)
        result = observer.public_payload()
        self.assertEqual(result["validated_event_count"], 36)
        self.assertTrue(all(row["state"] == "passed" for row in result["stages"]))
        self.assertEqual(result["observation_status"], "incomplete")
        self.assertTrue(result["protocol_invalid"])
        self.assertTrue(result["product_completion_unknown"])

    def test_outer_main_never_echoes_launch_or_wheel_read_private_exception(self):
        root = Path(tempfile.gettempdir())
        private = "private_marker_in_os_error"

        def failed_check(_wheel_output_dir, *, partial_evidence):
            return checker._check_installed_v0419_runtime_journey(root / "python", root / "wheel", root / "source",
                root / "fixture", cwd=root, expected_package_version="0.4.19", partial_evidence=partial_evidence)

        def completed_child(*_args, stderr_observer, **_kwargs):
            valid_prefix(stderr_observer)
            return "{}"

        cases = (
            (mock.patch.object(checker.subprocess, "Popen", side_effect=OSError(private)),
             mock.patch.object(checker.sys, "version_info", (3, 12))),
            (mock.patch.object(checker, "_run_installed_entrypoint", side_effect=completed_child),
             mock.patch.object(Path, "read_bytes", side_effect=OSError(private))),
        )
        for patches in cases:
            with self.subTest(case=cases.index(patches)):
                output = io.StringIO()
                with patches[0], patches[1], mock.patch.object(checker.os, "name", "nt"), mock.patch.object(
                    checker.sys, "version_info", (3, 12),
                ), mock.patch.object(checker.subprocess, "CREATE_NEW_PROCESS_GROUP", 512, create=True), mock.patch.object(
                    checker, "check_wheel", side_effect=failed_check,
                ), mock.patch.object(
                    checker.sys, "argv", ["checker", "--format", "json"],
                ), redirect_stderr(io.StringIO()), redirect_stdout(output):
                    self.assertEqual(checker.main(), 1)
                self.assertNotIn(private, output.getvalue())
                result = json.loads(output.getvalue())
                self.assertFalse(result["ok"])
                self.assertIn("partial_evidence", result)
                self.assertIn(result["error"], {
                    "Installed runtime journey process could not start.",
                    "Installed runtime journey wheel evidence could not be read.",
                })


class RuntimePhaseRealPipeTests(unittest.TestCase):
    def test_actual_timeout_parses_short_stderr_before_eof_and_keeps_stdout_private(self):
        observer = checker.RuntimePhaseObservation()
        payload = (line(1, "bootstrap_import", "begin", 0) + line(2, "bootstrap_import", "passed", 1)
                   + line(3, "synthetic_project", "begin", 2))
        script = "import sys,time;sys.stderr.buffer.write(" + repr(payload) + ");sys.stderr.flush();time.sleep(30)"
        started = time.monotonic()
        with self.assertRaisesRegex(checker.WheelCheckError, "execution timeout"):
            checker._run_installed_entrypoint([sys.executable, "-I", "-B", "-c", script],
                cwd=Path(tempfile.gettempdir()), label="phase pipe", timeout_seconds=2, stderr_observer=observer)
        observer.finish(success=False)
        self.assertLess(time.monotonic() - started, 8)
        self.assertEqual(observer.public_payload()["validated_event_count"], 3)
        self.assertEqual(observer.public_payload()["unfinished_stage"], "synthetic_project")
        self.assertEqual(observer.public_payload()["reason_code"], "harness_timeout")

    def test_actual_unknown_stderr_is_rejected_without_echoing_and_preserves_prefix(self):
        observer = checker.RuntimePhaseObservation()
        payload = line(1, "bootstrap_import", "begin", 0) + line(2, "bootstrap_import", "passed", 1)
        script = "import sys;sys.stderr.buffer.write(" + repr(payload + b"private_marker_secret\n") + ");sys.stderr.flush()"
        with self.assertRaises(checker.WheelCheckError) as caught:
            checker._run_installed_entrypoint([sys.executable, "-I", "-B", "-c", script],
                cwd=Path(tempfile.gettempdir()), label="phase pipe", timeout_seconds=4, stderr_observer=observer)
        self.assertNotIn("private_marker_secret", str(caught.exception))
        observer.finish(success=False)
        self.assertEqual(observer.public_payload()["validated_event_count"], 2)
        self.assertTrue(observer.public_payload()["protocol_invalid"])

    def test_actual_phase_stream_does_not_change_final_stdout_json(self):
        observer = checker.RuntimePhaseObservation()
        payload = b"".join(line(index * 2 + offset, stage, event, index * 2 + offset)
                           for index, stage in enumerate(checker.RUNTIME_PHASES)
                           for offset, event in ((1, "begin"), (2, "passed")))
        script = "import sys;sys.stderr.buffer.write(" + repr(payload) + ");sys.stderr.flush();print('{\"ok\":true}')"
        result = checker._run_installed_entrypoint([sys.executable, "-I", "-B", "-c", script],
            cwd=Path(tempfile.gettempdir()), label="phase pipe", timeout_seconds=4, stderr_observer=observer)
        self.assertEqual(json.loads(result), {"ok": True})
        observer.require_complete()
        observer.finish(success=True)
        self.assertEqual(observer.public_payload()["observation_status"], "complete")
