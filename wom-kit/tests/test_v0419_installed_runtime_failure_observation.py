"""Bounded failure diagnostics only; no wheel build, venv, or product repair."""

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import test_wheel_install


checker = test_wheel_install.check_wheel_install
spec = importlib.util.spec_from_file_location("wom_failure_driver_contract", checker.RUNTIME_JOURNEY_TOOL)
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


class InstalledRuntimeFailureObservationTests(unittest.TestCase):
    def failure(self, *, stage="first_update"):
        observer = driver.FirstUpdateObservation(stage=stage)
        observer.record("runtime_prepare", TypeError("SYNTHETIC_PRIVATE_TOKEN"))
        return {"ok": False, "schema": driver.SCHEMA,
                "reason_code": "repair_resume_failed" if stage == "repair_fresh_resume" else "public_update_failed",
                "failure_observation": observer.failure_payload(native_observed=False, cli_code=1,
                    cli_result={"status": "blocked", "effects_state": "unknown",
                                "reason_code": "project_runtime_tree_changed",
                                "project_runtime": {"preparation_revalidation": {"state": "not_reached"}},
                                "private_extension": "SYNTHETIC_PRIVATE_TOKEN"})}

    def test_cli_projection_and_parent_contract_are_fixed_and_detached(self):
        value = self.failure()
        raw = json.dumps(value)
        parsed = checker._parse_runtime_failure_output(raw)
        self.assertEqual(parsed, value)
        value["failure_observation"]["cli"]["status"] = "SYNTHETIC_PRIVATE_TOKEN"
        self.assertEqual(parsed["failure_observation"]["cli"]["status"], "blocked")
        self.assertEqual(parsed["failure_observation"]["cli"]["preparation_revalidation_state"], "not_reached")
        self.assertEqual(parsed["failure_observation"]["cli"]["reason_codes"], ["project_runtime_tree_changed"])
        self.assertNotIn("SYNTHETIC_PRIVATE_TOKEN", raw)
        self.assertFalse(parsed["failure_observation"]["product_recovery_evidence"])

    def test_exact_subprocess_stage_failure_is_visible_but_arbitrary_stage_is_not(self):
        from wom_kit import project_runtime
        observer = driver.FirstUpdateObservation()
        observer.record("runtime_prepare", project_runtime.ProjectRuntimeError("project-runtime-candidate-venv_failed"))
        self.assertEqual(observer.failure_payload(native_observed=False)["failures"]["runtime_prepare"][0]["code"],
                         "project-runtime-candidate-venv_failed")
        observer.record("first_cli_call", project_runtime.ProjectRuntimeError("private_lowercase_stage_failed"))
        value = observer.failure_payload(native_observed=False)
        self.assertEqual(value["failures"]["first_cli_call"][0]["code"], "unclassified_failure")
        self.assertNotIn("private_lowercase_stage_failed", json.dumps(value))

    def test_arbitrary_codes_keys_sources_states_and_overflow_are_rejected(self):
        original = self.failure()
        cases = []
        for change in ({"ok": True}, {"reason_code": "private_lowercase_token"},
                       {"extra": "SYNTHETIC_PRIVATE_TOKEN"}, {"schema": "wrong"}):
            cases.append(json.dumps({**original, **change}))
        for key, value in (("code", "private_lowercase_token"), ("kind", "PrivateException"),
                           ("source", {"file": "Q:/SYNTHETIC_PRIVATE_TOKEN", "line": 1, "function": "f"}),
                           ("source", {"file": "wom-kit/src/wom_kit/archive_cli.py", "line": True,
                                       "function": "_command_project_version_update_core"}),
                           ("source", {"file": "wom-kit/src/wom_kit/archive_cli.py", "line": 1,
                                       "function": "private_lowercase_token"})):
            changed = deepcopy(original)
            changed["failure_observation"]["failures"]["runtime_prepare"][0][key] = value
            cases.append(json.dumps(changed))
        changed = deepcopy(original)
        changed["failure_observation"]["cli"]["status"] = "private_lowercase_token"
        cases.extend([json.dumps(changed), '{"ok":false,"ok":false}',
                      json.dumps(original) + "SYNTHETIC_PRIVATE_TOKEN",
                      " " * (driver.FAILURE_OUTPUT_LIMIT_BYTES + 1)])
        for raw in cases:
            with self.subTest(case=len(raw)), self.assertRaises(checker.WheelCheckError) as caught:
                checker._parse_runtime_failure_output(raw)
            self.assertEqual(str(caught.exception), "Installed runtime failure observation is invalid.")
            self.assertIsNone(caught.exception.__context__)
            self.assertNotIn("SYNTHETIC_PRIVATE_TOKEN", repr(caught.exception))

    def test_actual_domain_failure_keeps_known_source_and_original_functions(self):
        from wom_kit import archive_services
        real = archive_services._wom_kit_project_version_update_live_approval_transaction
        private_argument = object()
        calls = []

        def prepare(value):
            self.assertIs(value, private_argument)
            calls.append("prepare")
            return real(None, target="", reviewed_by="", affirm_external_writers_quiescent=False,
                        approval_executor=None)

        cli_module = SimpleNamespace(
            _execute_project_version_update_exact_human_approved_write=lambda: None,
            _project_version_update_privacy_safe_failure_result=lambda error: {"status": "blocked"})
        runtime = SimpleNamespace(prepare_runtime_candidate=prepare)

        def cli(argv):
            self.assertIs(argv, private_argument)
            try:
                runtime.prepare_runtime_candidate(private_argument)
            except archive_services.ArchiveServiceError as error:
                return 1, cli_module._project_version_update_privacy_safe_failure_result(error)

        original_broker = cli_module._execute_project_version_update_exact_human_approved_write
        with self.assertRaises(driver.InitialUpdateCheckError) as caught:
            driver.observed_initial_update(cli_module, runtime, cli, private_argument, SimpleNamespace(called=False))
        self.assertIsNone(caught.exception.__context__)
        self.assertEqual(calls, ["prepare"])
        self.assertIs(runtime.prepare_runtime_candidate, prepare)
        self.assertIs(cli_module._execute_project_version_update_exact_human_approved_write, original_broker)
        item = caught.exception.observation["failures"]["runtime_prepare"][0]
        self.assertEqual(item["code"], "project_version_update_live_approval_executor_required")
        self.assertEqual(item["source"]["file"], "wom-kit/src/wom_kit/archive_services.py")
        self.assertEqual(item["source"]["function"], "_wom_kit_project_version_update_live_approval_transaction")
        self.assertGreater(item["source"]["line"], 0)

    def test_successful_real_forwarding_keeps_result_identity_without_diagnostic_success(self):
        result = {"status": "updated_restart_required"}
        prepared = object()
        effects = []
        runtime = SimpleNamespace(prepare_runtime_candidate=lambda: effects.append("prepare") or prepared)
        cli_module = SimpleNamespace(
            _execute_project_version_update_exact_human_approved_write=lambda: effects.append("broker") or result,
            _project_version_update_privacy_safe_failure_result=lambda error: None)

        def cli(_argv):
            self.assertIs(runtime.prepare_runtime_candidate(), prepared)
            return 0, cli_module._execute_project_version_update_exact_human_approved_write()

        code, actual = driver.observed_initial_update(cli_module, runtime, cli, [], SimpleNamespace(called=True))
        self.assertEqual(code, 0)
        self.assertIs(actual, result)
        self.assertEqual(effects, ["prepare", "broker"])

    def test_default_first_update_bytes_are_unchanged_and_only_two_stages_exist(self):
        self.assertEqual(json.dumps(self.failure(), sort_keys=True),
                         json.dumps(self.failure(stage="first_update"), sort_keys=True))
        for invalid in (None, True, [], "SYNTHETIC_PRIVATE_TOKEN", "repair_prepare_to_cut"):
            with self.subTest(value_type=type(invalid).__name__), self.assertRaises(driver.JourneyCheckError) as caught:
                driver.FirstUpdateObservation(stage=invalid)
            self.assertNotIn("SYNTHETIC_PRIVATE_TOKEN", repr(caught.exception))
        original = self.failure(stage="repair_fresh_resume")
        self.assertEqual(checker._parse_runtime_failure_output(json.dumps(original)), original)
        forged = deepcopy(original)
        forged["failure_observation"]["stage"] = "SYNTHETIC_PRIVATE_TOKEN"
        with self.assertRaises(checker.WheelCheckError):
            checker._parse_runtime_failure_output(json.dumps(forged))
        for wrong_stage in ({**original, "reason_code": "public_update_failed"},
                            {**self.failure(), "reason_code": "repair_resume_failed"}):
            with self.subTest(reason=wrong_stage["reason_code"]), self.assertRaises(checker.WheelCheckError):
                checker._parse_runtime_failure_output(json.dumps(wrong_stage))

    def test_real_resume_alias_runs_once_and_retains_fixed_inner_failure_without_private_values(self):
        from wom_kit import archive_cli, exact_human_approval_workflow as workflow
        from wom_kit import project_update_transaction as transaction
        real = archive_cli._resume_exact_human_approved_transaction_auto_core
        subject = object.__new__(transaction.ProjectUpdateTransaction)
        classification = transaction.ComponentClassification(
            overall="unknown", component_states=(("SYNTHETIC_PRIVATE_TOKEN", "unknown"),),
            observed_state_sha256="sha256:" + "a" * 64,
        )
        private_argument = object()
        calls, failures = [], []

        def fault_at_discovery(root, *_args, **_kwargs):
            self.assertIs(root, private_argument)
            calls.append(True)
            return subject._validate_live_for_event(None, (), classification)

        def project(error):
            failures.append(error)
            return {"status": "blocked", "private_extension": "SYNTHETIC_PRIVATE_TOKEN"}

        cli_module = SimpleNamespace(_resume_exact_human_approved_transaction_auto_core=real,
                                     _project_version_update_privacy_safe_failure_result=project)
        prepare = mock.Mock(side_effect=AssertionError("resume prepared"))
        runtime = SimpleNamespace(prepare_runtime_candidate=prepare)

        def cli(argv):
            self.assertIs(argv, private_argument)
            try:
                cli_module._resume_exact_human_approved_transaction_auto_core(
                    private_argument, None, None, None, None, None, resume_boundary=lambda: None,
                )
            except transaction.ProjectUpdateTransactionError as error:
                return 1, cli_module._project_version_update_privacy_safe_failure_result(error)

        with mock.patch.object(workflow, "_discover_exact_human_approved_transaction_resume_core",
                               side_effect=fault_at_discovery), self.assertRaises(driver.InitialUpdateCheckError) as caught:
            driver.observed_repair_resume(cli_module, runtime, cli, private_argument, SimpleNamespace(called=False))
        self.assertEqual(calls, [True])
        self.assertEqual(len(failures), 1)
        prepare.assert_not_called()
        self.assertIs(cli_module._resume_exact_human_approved_transaction_auto_core, real)
        self.assertIs(cli_module._project_version_update_privacy_safe_failure_result, project)
        self.assertIs(runtime.prepare_runtime_candidate, prepare)
        self.assertIsNone(caught.exception.__context__)
        payload = caught.exception.observation
        self.assertEqual(str(caught.exception), "repair_resume_failed")
        self.assertEqual(payload["stage"], "repair_fresh_resume")
        self.assertFalse(payload["native_observed"])
        self.assertEqual(payload["boundaries"]["approval_broker"], {"entered": True, "returned": False})
        source = payload["failures"]["approval_broker"][0]["source"]
        self.assertEqual(source["function"], "_validate_live_for_event")
        self.assertNotIn("SYNTHETIC_PRIVATE_TOKEN", json.dumps(payload))

    def test_successful_resume_alias_keeps_original_result_identity_and_does_not_prepare(self):
        result = {"status": "updated_restart_required", "private_original": object()}
        resume = mock.Mock(return_value=result)
        prepare = mock.Mock(side_effect=AssertionError("resume prepared"))
        cli_module = SimpleNamespace(_resume_exact_human_approved_transaction_auto_core=resume,
                                     _project_version_update_privacy_safe_failure_result=lambda error: None)
        runtime = SimpleNamespace(prepare_runtime_candidate=prepare)
        argument = object()
        code, actual = driver.observed_repair_resume(cli_module, runtime,
            lambda argv: (0, cli_module._resume_exact_human_approved_transaction_auto_core(argv)),
            argument, SimpleNamespace(called=False))
        self.assertEqual(code, 0)
        self.assertIs(actual, result)
        resume.assert_called_once_with(argument)
        prepare.assert_not_called()
        self.assertIs(cli_module._resume_exact_human_approved_transaction_auto_core, resume)

    def test_actual_nonzero_resume_child_forwards_only_validated_failure_to_outer_main(self):
        value = self.failure(stage="repair_fresh_resume")
        script = "import sys;print(sys.argv[1]);raise SystemExit(1)"
        with tempfile.TemporaryDirectory(prefix="wom-resume-failure-child-") as temporary:
            with self.assertRaises(driver.InitialUpdateCheckError) as caught:
                driver.command([sys.executable, "-I", "-B", "-c", script, json.dumps(value)],
                    cwd=Path(temporary), timeout=30, runtime_failure_stage="repair_fresh_resume")
        self.assertEqual(caught.exception.observation, value["failure_observation"])
        self.assertIsNone(caught.exception.__context__)
        output = io.StringIO()
        with mock.patch.object(driver.sys, "argv", ["tool", "wheel", "source", "shim", "fixture", "0.4.19"]), \
                mock.patch.object(driver, "run_journey", side_effect=caught.exception), redirect_stdout(output):
            self.assertEqual(driver.main(), 1)
        parsed = checker._parse_runtime_failure_output(output.getvalue())
        self.assertEqual(parsed, value)
        self.assertNotIn("SYNTHETIC_PRIVATE_TOKEN", output.getvalue())
        partial = checker.WheelPartialEvidence()
        partial.record_runtime_failure(parsed)
        self.assertNotIn("installed_v0419_runtime_journey", partial.public_payload())

    def test_resume_child_opt_in_rejects_wrong_stage_private_overflow_and_false_success(self):
        correct = self.failure(stage="repair_fresh_resume")
        wrong = deepcopy(correct)
        wrong["failure_observation"]["stage"] = "SYNTHETIC_PRIVATE_TOKEN"
        cases = (json.dumps(self.failure()), json.dumps(wrong), "SYNTHETIC_PRIVATE_TOKEN",
                 "x" * (driver.FAILURE_OUTPUT_LIMIT_BYTES + 1), json.dumps({**correct, "ok": True}))
        argv = ["synthetic-interpreter", "synthetic-argument"]
        for raw in cases:
            result = subprocess.CompletedProcess(argv, 1, raw, "SYNTHETIC_PRIVATE_TOKEN")
            with self.subTest(length=len(raw)), mock.patch.object(driver.subprocess, "run", return_value=result) as run, \
                    self.assertRaises(driver.JourneyCheckError) as caught:
                driver.command(argv, cwd=Path.cwd(), timeout=600, runtime_failure_stage="repair_fresh_resume")
            self.assertEqual(str(caught.exception), "synthetic_child_command_failed")
            self.assertIsNone(caught.exception.__context__)
            self.assertFalse(hasattr(caught.exception, "observation"))
            self.assertIs(run.call_args.args[0], argv)
            self.assertEqual(run.call_args.kwargs["timeout"], 600)
        with mock.patch.object(driver.subprocess, "run") as run, self.assertRaises(driver.JourneyCheckError) as caught:
            driver.command(argv, cwd=Path.cwd(), runtime_failure_stage="SYNTHETIC_PRIVATE_TOKEN")
        run.assert_not_called()
        self.assertNotIn("SYNTHETIC_PRIVATE_TOKEN", repr(caught.exception))
        with mock.patch.object(driver.subprocess, "run",
                               return_value=subprocess.CompletedProcess(argv, 1, json.dumps(correct), "")), \
                self.assertRaises(driver.JourneyCheckError) as caught:
            driver.command(argv, cwd=Path.cwd())
        self.assertEqual(str(caught.exception), "synthetic_child_command_failed")
        with mock.patch.object(driver.subprocess, "run",
                               return_value=subprocess.CompletedProcess(argv, 86, "", "")):
            self.assertEqual(driver.command(argv, cwd=Path.cwd(), expected_code=86), "")

    def test_real_unknown_component_refusal_exposes_only_fixed_method_coordinate(self):
        from wom_kit import project_update_transaction as transaction
        observer = driver.FirstUpdateObservation()
        subject = object.__new__(transaction.ProjectUpdateTransaction)
        classification = transaction.ComponentClassification(
            overall="unknown", component_states=(("SYNTHETIC_PRIVATE_TOKEN", "unknown"),),
            observed_state_sha256="sha256:" + "a" * 64,
        )
        calls, errors = [], []

        def original_call():
            calls.append(True)
            try:
                return subject._validate_live_for_event(None, (), classification)
            except transaction.ProjectUpdateTransactionError as error:
                errors.append(error)
                raise

        with self.assertRaises(transaction.ProjectUpdateTransactionError) as caught:
            observer.boundary("approval_broker", original_call)()
        self.assertEqual(calls, [True])
        self.assertIs(caught.exception, errors[0])
        value = {"ok": False, "schema": driver.SCHEMA, "reason_code": "public_update_failed",
                 "failure_observation": observer.failure_payload(native_observed=True, cli_code=1)}
        parsed = checker._parse_runtime_failure_output(json.dumps(value))
        item = parsed["failure_observation"]["failures"]["approval_broker"][0]
        self.assertEqual(item["code"], "project_update_transaction_state_transition_invalid")
        self.assertEqual(item["source"]["function"], "_validate_live_for_event")
        self.assertEqual(item["source"]["file"], "wom-kit/src/wom_kit/project_update_transaction.py")
        self.assertGreater(item["source"]["line"], 0)
        self.assertNotIn("SYNTHETIC_PRIVATE_TOKEN", json.dumps(value))
        self.assertNotIn("component_states", json.dumps(value))

    def test_real_nested_append_refusal_is_registered_without_new_io_or_replacement(self):
        import test_project_update_transaction as fixture
        helper = fixture.ProjectUpdateTransactionTests("runTest")
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        transaction = helper.create_transaction()
        helper.activate(transaction)
        observer = driver.FirstUpdateObservation()
        original = type(transaction)._append_guard_held
        before = {path.relative_to(helper.project).as_posix(): path.read_bytes()
                  for path in helper.project.rglob("*") if path.is_file()}

        with self.assertRaises(fixture.ProjectUpdateTransactionError):
            observer.boundary("approval_broker", transaction.append)(
                phase="completed", stage="verified", live_component_sha256=helper.live_pre(),
            )
        self.assertIs(type(transaction)._append_guard_held, original)
        item = observer.failure_payload(native_observed=True)["failures"]["approval_broker"][0]
        self.assertEqual(item["source"]["function"], "_append_guard_held")
        self.assertEqual(item["source"]["file"], "wom-kit/src/wom_kit/project_update_transaction.py")
        self.assertNotIn(str(helper.project), json.dumps(item))
        self.assertEqual({path.relative_to(helper.project).as_posix(): path.read_bytes()
                          for path in helper.project.rglob("*") if path.is_file()}, before)

    def test_driver_main_exports_only_validated_failure_observation(self):
        payload = self.failure()["failure_observation"]
        error = driver.InitialUpdateCheckError(payload)
        output = io.StringIO()
        with mock.patch.object(driver.sys, "argv", ["tool", "wheel", "source", "shim", "fixture", "0.4.19"]), \
                mock.patch.object(driver, "run_journey", side_effect=error), redirect_stdout(output):
            self.assertEqual(driver.main(), 1)
        self.assertEqual(driver.parse_failure_output(output.getvalue())["failure_observation"], payload)

    def test_real_nonzero_process_retains_safe_failure_but_cannot_pass(self):
        partial = checker.WheelPartialEvidence()
        captured = []

        def retain(raw):
            captured.append(True)
            partial.record_runtime_failure(checker._parse_runtime_failure_output(raw))

        with tempfile.TemporaryDirectory(prefix="wom-failure-pipe-") as temporary:
            script = "import sys;sys.stdout.write(sys.stdin.read());raise SystemExit(1)"
            with self.assertRaisesRegex(checker.WheelCheckError, "nonzero exit status"):
                checker._run_installed_entrypoint([sys.executable, "-I", "-B", "-c", script],
                    cwd=Path(temporary), label="synthetic failure observer", input_text=json.dumps(self.failure()),
                    nonzero_stdout_observer=retain)
        self.assertEqual(captured, [True])
        result = partial.public_payload()
        self.assertNotIn("installed_v0419_runtime_journey", result)
        self.assertFalse(result["installed_runtime_failure_observation"]["ok"])
        self.assertNotIn("SYNTHETIC_PRIVATE_TOKEN", json.dumps(result))

    def test_nonzero_observer_never_sees_overflow_or_invalid_utf8(self):
        scripts = ("import sys;sys.stdout.buffer.write(b'x'*512);raise SystemExit(1)",
                   "import sys;sys.stdout.buffer.write(bytes([255]));raise SystemExit(1)")
        with tempfile.TemporaryDirectory(prefix="wom-failure-bounds-") as temporary:
            for script in scripts:
                hook = mock.Mock()
                with mock.patch.object(checker, "ENTRYPOINT_OUTPUT_LIMIT_BYTES", 128), \
                        self.assertRaises(checker.WheelCheckError):
                    checker._run_installed_entrypoint([sys.executable, "-I", "-B", "-c", script],
                        cwd=Path(temporary), label="synthetic bounded failure", nonzero_stdout_observer=hook)
                hook.assert_not_called()

    def test_runtime_parent_preserves_failure_separately_and_still_raises(self):
        value = self.failure()
        partial = checker.WheelPartialEvidence()

        def child(*_args, **kwargs):
            kwargs["nonzero_stdout_observer"](json.dumps(value))
            raise checker.WheelCheckError("synthetic nonzero failure")

        with tempfile.TemporaryDirectory(prefix="wom-runtime-failure-parent-") as temporary:
            root = Path(temporary)
            with mock.patch.object(checker.os, "name", "nt"), mock.patch.object(checker.sys, "version_info", (3, 12)), \
                    mock.patch.object(checker, "_run_installed_entrypoint", side_effect=child), \
                    redirect_stderr(io.StringIO()), self.assertRaises(checker.WheelCheckError):
                checker._check_installed_v0419_runtime_journey(root / "python", root / "wheel", root / "source",
                    root / "fixture", cwd=root, expected_package_version="0.4.19", partial_evidence=partial)
        retained = partial.public_payload()
        self.assertEqual(retained["installed_runtime_failure_observation"], value)
        self.assertEqual(retained["installed_runtime_harness_observation"]["observation_status"], "incomplete")
        self.assertNotIn("installed_v0419_runtime_journey", retained)

    def test_initial_only_mode_has_distinct_schema_and_cannot_prove_full_journey(self):
        value = driver.initial_update_diagnostic("0.4.19", "a" * 64, 0.2, 50.1)
        output = io.StringIO()
        with mock.patch.object(driver.sys, "argv", ["tool", "--initial-update-only", "wheel", "source",
                                                    "shim", "fixture", "0.4.19"]), \
                mock.patch.object(driver, "run_journey", return_value=value) as journey, redirect_stdout(output):
            self.assertEqual(driver.main(), 0)
        self.assertTrue(journey.call_args.kwargs["initial_update_only"])
        self.assertEqual(json.loads(output.getvalue())["schema"], driver.INITIAL_DIAGNOSTIC_SCHEMA)
        self.assertFalse(value["full_journey_complete"])
        with self.assertRaises(checker.WheelCheckError):
            checker._validate_v0419_runtime_evidence(value, expected_version="0.4.19", expected_wheel_hash="a" * 64)
        with self.assertRaises(checker.WheelCheckError):
            checker.WheelPartialEvidence().record_runtime(value)

    def test_initial_failure_file_is_fixed_no_overwrite_strict_and_read_only(self):
        with tempfile.TemporaryDirectory(prefix="wom-safe-failure-file-") as temporary:
            root = Path(temporary)
            original = self.failure()
            driver.write_initial_failure_observation(root, driver._initial_failure_root_identity(root), original)
            files = {path.name: path.read_bytes() for path in root.iterdir()}
            self.assertEqual(set(files), {driver.INITIAL_FAILURE_FILE})
            self.assertEqual(driver.read_initial_failure_observation(root), original)
            with self.assertRaises(driver.JourneyCheckError):
                driver.write_initial_failure_observation(root, driver._initial_failure_root_identity(root), original)
            self.assertEqual({path.name: path.read_bytes() for path in root.iterdir()}, files)
            self.assertNotIn(b"SYNTHETIC_PRIVATE_TOKEN", files[driver.INITIAL_FAILURE_FILE])

    def test_failure_file_refuses_unknown_private_payload_and_wrong_root_before_write(self):
        with tempfile.TemporaryDirectory(prefix="wom-safe-failure-reject-") as temporary:
            root = Path(temporary)
            for value, identity in (({**self.failure(), "extra": "SYNTHETIC_PRIVATE_TOKEN"},
                                     driver._initial_failure_root_identity(root)),
                                    (self.failure(), (-1, -1))):
                with self.assertRaises(driver.JourneyCheckError) as caught:
                    driver.write_initial_failure_observation(root, identity, value)
                self.assertEqual(str(caught.exception), "installed_runtime_journey_failed")
                self.assertIsNone(caught.exception.__context__)
                self.assertEqual(tuple(root.iterdir()), ())

    def test_initial_main_preserves_valid_failure_before_stdout_without_full_proof(self):
        with tempfile.TemporaryDirectory(prefix="wom-safe-failure-main-") as temporary:
            root = Path(temporary)
            payload = self.failure()["failure_observation"]
            def fail(*_args, **kwargs):
                kwargs["phases"].initial_diagnostic_root = (root, driver._initial_failure_root_identity(root))
                raise driver.InitialUpdateCheckError(payload)
            output = io.StringIO()
            original_print = print
            def observed_print(*args, **kwargs):
                self.assertTrue((root / driver.INITIAL_FAILURE_FILE).is_file())
                return original_print(*args, **kwargs)
            with mock.patch.object(driver.sys, "argv", ["tool", "--initial-update-only", "wheel", "source",
                                                        "shim", str(root), "0.4.19"]), \
                    mock.patch.object(driver, "run_journey", side_effect=fail), \
                    mock.patch("builtins.print", side_effect=observed_print), redirect_stdout(output):
                self.assertEqual(driver.main(), 1)
            saved = driver.read_initial_failure_observation(root)
            self.assertEqual(saved, json.loads(output.getvalue()))
            self.assertFalse(saved["ok"])
            self.assertEqual(saved["failure_observation"], payload)

    def test_failure_file_reader_refuses_hardlink_and_oversize(self):
        import os
        with tempfile.TemporaryDirectory(prefix="wom-safe-failure-leaf-") as temporary:
            root = Path(temporary)
            file = root / driver.INITIAL_FAILURE_FILE
            file.write_bytes(b"x" * (driver.FAILURE_OUTPUT_LIMIT_BYTES + 1))
            with self.assertRaises(driver.JourneyCheckError):
                driver.read_initial_failure_observation(root)
            file.write_text(json.dumps(self.failure()), encoding="utf-8")
            try:
                os.link(file, root / "synthetic-hardlink")
            except OSError:
                self.skipTest("Host hardlink capability unavailable")
            with self.assertRaises(driver.JourneyCheckError):
                driver.read_initial_failure_observation(root)

    def test_early_initial_exit_occurs_after_real_update_checks_and_before_noop(self):
        import ast
        tree = ast.parse(checker.RUNTIME_JOURNEY_TOOL.read_text(encoding="utf-8"))
        journey = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == "run_journey")
        stop = next(item for item in ast.walk(journey) if isinstance(item, ast.If)
                    and isinstance(item.test, ast.Name) and item.test.id == "initial_update_only"
                    and any(isinstance(child, ast.Return) for child in item.body))
        update = next(item for item in ast.walk(journey) if isinstance(item, ast.Call)
                      and isinstance(item.func, ast.Name) and item.func.id == "observed_initial_update")
        noop = next(item for item in ast.walk(journey) if isinstance(item, ast.Call)
                    and any(isinstance(arg, ast.Constant) and arg.value == "healthy_noop" for arg in item.args))
        self.assertLess(update.lineno, stop.lineno)
        self.assertLess(stop.lineno, noop.lineno)
        self.assertTrue(any(isinstance(item, ast.Return) for item in stop.body))


if __name__ == "__main__":
    unittest.main()
