"""Argument/real-held-runtime routing tests; private domain runners are mocked.

These prove no intake execution, native UI, installed wheel or client journey.
"""

from contextlib import redirect_stderr, redirect_stdout
import inspect
import io
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

import wom_kit
from wom_kit import archive_cli as cli
from wom_kit import cli_entry, command_status
from wom_kit import exact_operation_manifest as exact
from wom_kit import source_intake_session_command as command


APP = "client_app_" + "a" * 32
ROUTE = "task_route_" + "b" * 32
SESSION = "work_session_" + "c" * 32
PRIVATE = "SYNTHETIC_PRIVATE_INPUT"
DIGEST = "sha256:" + "d" * 64


def result(mode):
    if mode == "preview":
        return {"ok": True, "ready_for_write": True, "manifest_sha256": DIGEST,
                "item_count": 1, "writes_performed": False}
    return {"ok": True, "state": "completed", "original_completion_verified": True,
            "completion_authentication_verified": True, "independent_verification": True,
            "execution_sha256": DIGEST, "common_final_receipt_sha256": DIGEST,
            "item_count": 1, "completed_item_count": 1, "artifact_capture_performed": False}


class SourceIntakeSessionCliTests(unittest.TestCase):
    def call(self, flags):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = cli.main(["source-intake-batch", PRIVATE, "--format", "json", *flags])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_fresh_routes_keep_request_but_do_not_accept_copied_plan_digest(self):
        for flag, mode in (("--dry-run", "preview"), ("--approve", "apply")):
            flags = ["--client-app-ref", APP, "--task-route-ref", ROUTE, "--work-session-ref", SESSION,
                     "--manifest", PRIVATE, flag]
            if mode == "apply":
                flags += ["--reviewed-by", "person:synthetic-reviewer"]
            with self.subTest(mode=mode), patch.object(command, "dispatch_session_source_intake",
                                                       return_value=result(mode)) as dispatch:
                code, stdout, stderr = self.call(flags)
                self.assertEqual(code, 0, stdout)
                values = dispatch.call_args.kwargs
                self.assertEqual(values["mode"], mode)
                self.assertEqual(values["request_path"], PRIVATE)
                self.assertEqual(values["client_app_ref"], APP)
                self.assertEqual(values["task_route_ref"], ROUTE)
                self.assertEqual(values["work_session_ref"], SESSION)
                self.assertTrue(callable(values["progress"]))
                self.assertNotIn("expected_plan_sha256", values)
                self.assertNotIn(PRIVATE, stdout + stderr)

    def test_any_explicit_reference_selects_new_route_including_assignment_syntax(self):
        for flag, value in (("--client-app-ref", APP), ("--task-route-ref", ROUTE), ("--work-session-ref", SESSION)):
            with self.subTest(flag=flag), patch.object(command, "dispatch_session_source_intake",
                                                       return_value=result("resume")) as dispatch:
                code, stdout, _stderr = self.call([flag + "=" + value, "--resume", "--no-progress"])
                self.assertEqual(code, 0, stdout)
                self.assertEqual(dispatch.call_args.kwargs[flag[2:].replace("-", "_")], value)
                self.assertEqual(dispatch.call_args.kwargs["mode"], "resume")

    def test_original_resume_forwards_only_retained_route_and_optional_session_assertion(self):
        for additional in ([], ["--work-session-ref", SESSION]):
            with self.subTest(assertion=bool(additional)), patch.object(command, "dispatch_session_source_intake",
                                                                       return_value=result("resume")) as dispatch:
                code, stdout, stderr = self.call(["--client-app-ref", APP, "--task-route-ref", ROUTE,
                                                 "--resume", "--no-progress", *additional])
                self.assertEqual(code, 0, stdout)
                values = dispatch.call_args.kwargs
                self.assertIsNone(values["request_path"])
                self.assertIsNone(values["reviewer_claim"])
                self.assertEqual(values["work_session_ref"], SESSION if additional else None)
                self.assertNotIn(PRIVATE, stdout + stderr)

    def test_replacement_and_contradictory_flags_refuse_before_dispatch(self):
        route = ["--client-app-ref", APP, "--task-route-ref", ROUTE, "--resume"]
        bad = [["--manifest", PRIVATE], ["--reviewed-by", PRIVATE], ["--expected-plan-sha256", PRIVATE],
               ["--resume-approval-id", PRIVATE], ["--execution-sha256", PRIVATE], ["--reconcile"],
               ["--approve"], ["--dry-run"], ["--review-original"]]
        for extra in bad:
            with self.subTest(extra=extra), patch.object(command, "dispatch_session_source_intake") as dispatch:
                code, stdout, stderr = self.call(route + extra)
                self.assertNotEqual(code, 0)
                dispatch.assert_not_called()
                self.assertNotIn(PRIVATE, stdout + stderr)
        for flag in ("--dry-run", "--approve"):
            with patch.object(command, "dispatch_session_source_intake") as dispatch:
                code, stdout, stderr = self.call(["--client-app-ref", APP, "--manifest", PRIVATE,
                    flag, "--expected-plan-sha256", PRIVATE])
                self.assertNotEqual(code, 0)
                dispatch.assert_not_called()
                self.assertNotIn(PRIVATE, stdout + stderr)

    def test_missing_manifest_keeps_legacy_rc2_schema_and_fresh_requirement(self):
        for flags in (["--dry-run"], ["--resume"], ["--client-app-ref", APP, "--dry-run"],
                      ["--client-app-ref", APP, "--approve"]):
            with self.subTest(flags=flags), patch.object(command, "dispatch_session_source_intake") as dispatch:
                code, stdout, stderr = self.call(flags)
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(stdout), {
                    "schema": "wom-kit/cli-error/v0.1", "ok": False, "state": "blocked", "status_class": "blocked",
                    "lifecycle_action": "cli_argument_validation", "command": "source-intake-batch", "error_class": "usage",
                    "reason_codes": ["cli_required_arguments_missing"], "exit_code": 2, "effects_state": "none",
                    "files_written": [], "missing_arguments": ["--manifest"], "private_values_echoed": False})
                self.assertEqual(stderr, "")
                dispatch.assert_not_called()

    def test_no_ref_legacy_resume_and_approval_error_order_are_unchanged(self):
        from wom_kit import source_intake_batch_exact as legacy
        marker = object()
        with patch.object(command, "dispatch_session_source_intake") as dispatch, \
             patch.object(legacy, "plan_source_intake_batch", return_value=marker) as planner, \
             patch.object(legacy, "resume_source_intake_batch_auto", return_value={"ok": True}) as resume:
            code, stdout, stderr = self.call(["--manifest", PRIVATE, "--resume", "--reviewed-by",
                                              "person:synthetic-reviewer", "--no-progress"])
            self.assertEqual(code, 0, stdout)
            self.assertEqual(stderr, "")
            dispatch.assert_not_called()
            planner.assert_called_once()
            self.assertIs(resume.call_args.args[0], marker)
        with patch.object(legacy, "plan_source_intake_batch") as planner:
            code, stdout, _stderr = self.call(["--manifest", PRIVATE, "--approve", "--no-progress"])
            self.assertEqual(code, 1)
            self.assertIn("source_intake_batch_approval_required", stdout)
            planner.assert_not_called()

    def test_startup_defaults_and_capability_remain_available_without_review_original(self):
        parser = cli.build_parser()
        inventory = cli._parser_capability_inventory(parser)
        for mode in ("--dry-run", "--approve", "--resume"):
            flags = ["source-intake-batch", PRIVATE, "--client-app-ref", APP, mode]
            self.assertTrue(cli_entry.startup_progress_requested(flags))
            self.assertFalse(cli_entry.startup_progress_requested(flags + ["--no-progress"]))
            self.assertFalse(cli_entry.startup_progress_requested(flags + ["--help"]))
            args = parser.parse_args(flags)
            available = command_status.resolve_namespace_capability_availability(parser, inventory, args)
            if mode == "--resume":
                self.assertEqual(available["state"], "not_requested")
                self.assertIsNone(available["available"])
            else:
                self.assertTrue(available["available"], available)
            self.assertEqual(available["approval_status"], "approval_available")
            self.assertTrue(args._wom_project_runtime_resume_effect)
        self.assertTrue(cli_entry.startup_progress_requested(["source-intake-batch", "--resume"]))

    def test_reporter_uses_five_seconds_and_only_closed_projected_events(self):
        exact_event = exact.ExactOperationProgress(PRIVATE, PRIVATE, "apply", "field_verified", 1, 2, 1, 2)
        def dispatch(*args, progress, **kwargs):
            progress({"phase": "intake_preflight", "label": PRIVATE})
            progress(exact_event)
            progress({"phase": PRIVATE})
            return result("resume")
        with patch.object(command, "dispatch_session_source_intake", side_effect=dispatch), \
             patch.object(cli, "CommandProgressReporter") as reporter:
            code, stdout, stderr = self.call(["--client-app-ref", APP, "--resume"])
        self.assertEqual(code, 0)
        self.assertEqual(reporter.call_args.kwargs["heartbeat_interval_seconds"], 5.0)
        self.assertEqual(reporter.return_value.progress.call_count, 3)
        self.assertNotIn(PRIVATE, repr(reporter.return_value.progress.call_args_list))
        reporter.return_value.close.assert_called_once()
        self.assertNotIn(PRIVATE, stdout + stderr)

    def test_scoped_text_usage_error_is_private_and_does_not_advertise_original_review(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr), \
             patch.object(command, "dispatch_session_source_intake") as dispatch:
            code = cli.main(["source-intake-batch", PRIVATE, "--client-app-ref", APP,
                             "--resume", "--review-original", PRIVATE, "--format", "text"])
        self.assertEqual(code, 2)
        dispatch.assert_not_called()
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("private argument values were not echoed", stderr.getvalue())
        self.assertNotIn(PRIVATE, stderr.getvalue())

    def test_scoped_text_distinguishes_preview_completion_and_blocked(self):
        for mode, okay, expected in (("preview", True, "ready_for_write"), ("apply", True, "completed"),
                                      ("preview", False, "blocked")):
            with self.subTest(mode=mode, okay=okay), patch.object(command, "dispatch_session_source_intake",
                    return_value=result(mode) if okay else command._failure("work_session_intake_plan_blocked", mode=mode)):
                flags = ["--client-app-ref", APP, "--manifest", PRIVATE, "--no-progress", "--format", "text",
                         "--dry-run" if mode == "preview" else "--approve"]
                if mode == "apply":
                    flags += ["--reviewed-by", "person:synthetic-reviewer"]
                code, stdout, stderr = self.call(flags)
                self.assertEqual(code == 0, okay)
                self.assertEqual(stdout, "Session source intake: " + expected + "\n")
                self.assertEqual(stderr, "")

    def test_reporter_interrupt_does_not_erase_verified_original_completion(self):
        for boundary in ("construct", "close"):
            with self.subTest(boundary=boundary), patch.object(cli, "CommandProgressReporter") as reporter, \
                 patch.object(command, "dispatch_session_source_intake", return_value=result("resume")) as dispatch:
                if boundary == "construct":
                    reporter.side_effect = KeyboardInterrupt(PRIVATE)
                else:
                    reporter.return_value.close.side_effect = KeyboardInterrupt(PRIVATE)
                code, stdout, stderr = self.call(["--client-app-ref", APP, "--resume"])
                public = json.loads(stdout)
                self.assertEqual(code, 1)
                self.assertEqual(public["reason_code"], "work_session_wait_cancelled")
                self.assertEqual(public["original_completion_verified"], boundary == "close")
                self.assertEqual(dispatch.call_count, int(boundary == "close"))
                self.assertNotIn(PRIVATE, stdout + stderr)


class SourceIntakeSessionBoundaryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="wom-session-intake-command-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "archive.yml").write_text("archive_id: archive:personal:synthetic-intake-command\n", encoding="utf-8")
        self.calls, self.held_locks = [], []
        fake = ModuleType("wom_kit.work_session_source_intake_workflow")
        fake._ERRORS = frozenset({"work_session_intake_ownership_unavailable"})
        class WorkflowError(RuntimeError):
            code = "work_session_intake_ownership_unavailable"
            original_completion_verified = True
        fake.WorkSessionIntakeWorkflowError = WorkflowError
        for mode, name in (("preview", "_preview_session_source_intake_batch_held"),
                           ("apply", "_execute_session_source_intake_batch_held"),
                           ("resume", "_resume_session_source_intake_batch_held")):
            def run(root, *request, held, _mode=mode, **values):
                self.assertIs(type(held), exact.ExactOperationWriterLock)
                held.verify_held()
                self.held_locks.append(held)
                self.calls.append((_mode, request, values))
                return result(_mode)
            setattr(fake, name, run)
        self.fake = fake
        for item in (patch.dict(sys.modules, {fake.__name__: fake}),
                     patch.object(wom_kit, "work_session_source_intake_workflow", fake, create=True)):
            item.start()
            self.addCleanup(item.stop)

    def call(self, mode="preview", **options):
        values = dict(client_app_ref=APP, task_route_ref=ROUTE, work_session_ref=SESSION)
        if mode != "resume":
            values["request_path"] = PRIVATE
        if mode == "apply":
            values["reviewer_claim"] = "person:synthetic-reviewer"
        values.update(options)
        return command.dispatch_session_source_intake(self.root, mode=mode, **values)

    def test_all_modes_reuse_real_held_lock_and_runtime_guard_then_release(self):
        original = command.sessions._runtime_guard
        original_enter = exact.ExactOperationWriterLock.__enter__
        guards, entries = [], []
        def guard(root):
            guards.append(root)
            return original(root)
        def enter(held):
            entries.append(held)
            return original_enter(held)
        with patch.object(command.sessions, "_runtime_guard", side_effect=guard), \
             patch.object(exact.ExactOperationWriterLock, "__enter__", new=enter):
            for mode in ("preview", "apply", "resume"):
                self.assertTrue(self.call(mode)["ok"])
        self.assertEqual(len(guards), 3)
        self.assertEqual(entries, self.held_locks)
        self.assertEqual([row[0] for row in self.calls], ["preview", "apply", "resume"])
        self.assertEqual(self.calls[-1][1], ())
        for held in self.held_locks:
            with self.assertRaises(exact.ExactOperationManifestError):
                held.verify_held()
        for name in ("native", "key_provider", "approval_id", "execution_sha256", "expected_plan_sha256"):
            self.assertNotIn(name, inspect.signature(command.dispatch_session_source_intake).parameters)

    def test_runtime_refusal_and_cancel_stop_before_domain(self):
        with patch.object(command.sessions, "_runtime_guard",
                          side_effect=command.sessions.WorkSessionServiceError("project_runtime_mismatch")):
            refused = self.call()
        self.assertEqual(refused["reason_code"], "project_runtime_mismatch")
        self.assertEqual(refused["effects_state"], "none")
        cancelled = self.call(cancel_requested=lambda: True)
        self.assertEqual(cancelled["reason_code"], "work_session_wait_cancelled")
        self.assertEqual(cancelled["effects_state"], "none")
        self.assertEqual(self.calls, [])

    def test_invalid_reference_or_replacement_request_never_enters_domain(self):
        for mode, changes in (("preview", {"request_path": None}), ("apply", {"reviewer_claim": None}),
                              ("resume", {"request_path": PRIVATE}), ("resume", {"reviewer_claim": PRIVATE}),
                              ("resume", {"work_session_ref": PRIVATE}), ("preview", {"client_app_ref": None}),
                              ("preview", {"task_route_ref": PRIVATE})):
            with self.subTest(mode=mode, changes=changes):
                self.assertFalse(self.call(mode, **changes)["ok"])
        self.assertEqual(self.calls, [])

    def test_callback_cannot_forge_completion_but_actual_workflow_error_preserves_it(self):
        def fail(*args, **kwargs):
            raise self.fake.WorkSessionIntakeWorkflowError(PRIVATE)
        self.fake._resume_session_source_intake_batch_held = fail
        verified = self.call("resume")
        self.assertTrue(verified["original_completion_verified"])
        self.assertFalse(verified["completion_verified"])
        def pulse(root, *args, progress_hook, **kwargs):
            progress_hook({"phase": "intake_preflight"})
        self.fake._preview_session_source_intake_batch_held = pulse
        forged = self.call(progress=fail)
        self.assertFalse(forged["original_completion_verified"])
        self.assertEqual(forged["reason_code"], "work_session_intake_command_unavailable")
        self.assertNotIn(PRIVATE, json.dumps([verified, forged]))

    def test_keyboard_interrupt_and_private_os_error_are_fixed_before_and_after_entry(self):
        def interrupt(*args, **kwargs):
            raise KeyboardInterrupt(PRIVATE)
        before = self.call(cancel_requested=interrupt)
        self.fake._preview_session_source_intake_batch_held = interrupt
        after = self.call()
        self.assertEqual(before["effects_state"], "none")
        self.assertEqual(after["effects_state"], "none")
        self.assertEqual(after["reason_code"], "work_session_wait_cancelled")
        self.fake._execute_session_source_intake_batch_held = interrupt
        apply_interrupted = self.call("apply")
        self.assertEqual(apply_interrupted["effects_state"], "unknown")
        def failed(*args, **kwargs):
            raise OSError(PRIVATE)
        self.fake._preview_session_source_intake_batch_held = failed
        self.assertNotIn(PRIVATE, json.dumps([before, after, self.call()]))

    def test_public_result_and_progress_never_call_private_objects_or_leak_nested_data(self):
        class Private:
            def public_document(self):
                raise AssertionError("arbitrary callback")
            def __repr__(self):
                raise AssertionError("arbitrary repr")
        private = Private()
        projected = command._public_result({**result("preview"), "private": private,
            "operation_evidence": {"private_path": PRIVATE}, "reviewer": PRIVATE}, mode="preview")
        self.assertNotIn(PRIVATE, json.dumps(projected))
        self.assertNotIn("operation_evidence", projected)
        self.assertIsNone(command._project_progress(private))
        self.assertIsNone(command._project_progress({"phase": private}))
        self.assertEqual(command._project_progress({"phase": "intake_revalidation", "private": private}),
                         ("source-intake-session-intake_revalidation", None, None))
        for count in (True, -1, float("inf"), 1 << 80, PRIVATE):
            event = exact.ExactOperationProgress(PRIVATE, PRIVATE, "apply", "preflight", count, 2, 0, 2)
            self.assertIsNone(command._project_progress(event))
        event = exact.ExactOperationProgress(PRIVATE, PRIVATE, "apply", "item_verified", 1, 2, 0, 2)
        with patch.object(exact.ExactOperationProgress, "public_document", side_effect=AssertionError("callback")):
            self.assertEqual(command._project_progress(event), ("exact-operation-item_verified", 1, 2))
        class DerivedProgress(exact.ExactOperationProgress):
            pass
        self.assertIsNone(command._project_progress(DerivedProgress(PRIVATE, PRIVATE, "apply", "preflight", 0, 1, 0, 1)))


if __name__ == "__main__":
    unittest.main()
