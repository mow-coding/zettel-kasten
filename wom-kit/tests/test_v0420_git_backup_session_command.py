"""Public argument/one-lock routing; domain real-Git journeys are separate."""

from contextlib import contextmanager, nullcontext, redirect_stderr, redirect_stdout
import inspect
import io
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

import wom_kit
from wom_kit import archive_cli as cli
from wom_kit import cli_entry
from wom_kit import exact_operation_manifest as exact
from wom_kit import git_backup_session_command as command
from wom_kit import work_session_git_progress as progress_observer


APP = "client_app_" + "a" * 32
ROUTE = "task_route_" + "b" * 32
SESSION = "work_session_" + "c" * 32
PRIVATE = "SYNTHETIC_PRIVATE_COMMAND_VALUE"


class SessionGitCliRoutingTests(unittest.TestCase):
    def test_scoped_startup_is_visible_without_changing_legacy_progress_default(self):
        command_name = "git-backup-reconcile-plan"
        for flag in ("--client-app-ref", "--task-route-ref", "--work-session-ref", "--resume"):
            for option in (flag, flag + "=" + PRIVATE):
                with self.subTest(option=option):
                    self.assertTrue(cli_entry.startup_progress_requested([command_name, option]))
                    self.assertFalse(cli_entry.startup_progress_requested([command_name, option, "--help"]))
                    self.assertFalse(cli_entry.startup_progress_requested([command_name, "--", option]))
        self.assertFalse(cli_entry.startup_progress_requested([command_name, "--dry-run"]))
        self.assertTrue(cli_entry.startup_progress_requested([command_name, "--progress"]))

    def call(self, extra):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = cli.main(["git-backup-reconcile-plan", PRIVATE, "--format", "json", *extra])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_preview_and_approve_compute_selection_without_ids_or_json_input(self):
        for flag, mode in (("--dry-run", "preview"), ("--approve", "apply")):
            arguments = ["--client-app-ref", APP, "--task-route-ref", ROUTE,
                         "--work-session-ref", SESSION, "--credential-mode", "stored", flag]
            if mode == "apply":
                arguments += ["--reviewed-by", "person:synthetic-reviewer"]
            with self.subTest(mode=mode), patch.object(command, "dispatch_session_git_backup",
                                                       return_value={"ok": True, "receipt_only": True}) as dispatch:
                code, stdout, _stderr = self.call(arguments)
                self.assertEqual(code, 0, stdout)
                values = dispatch.call_args.kwargs
                self.assertEqual(values["mode"], mode)
                self.assertEqual(values["client_app_ref"], APP)
                self.assertEqual(values["task_route_ref"], ROUTE)
                self.assertEqual(values["work_session_ref"], SESSION)
                self.assertEqual(values["options"]["credential_mode"], "stored")
                self.assertTrue(callable(values["progress"]))
                presentation = json.loads(stdout)["progress_observation"]
                self.assertEqual(presentation["mode"], "synchronous")
                self.assertFalse(presentation["live_heartbeat_used"])
                self.assertTrue(presentation["observer_closed"])
                self.assertNotIn(PRIVATE, stdout)
                self.assertFalse(set(values) & {"approval_id", "expected_plan_sha256", "selection_manifest"})

    def test_original_resume_forwards_only_the_retained_route(self):
        with patch.object(command, "dispatch_session_git_backup", return_value={"ok": True}) as dispatch:
            code, stdout, _stderr = self.call(["--client-app-ref", APP, "--task-route-ref", ROUTE, "--resume"])
        self.assertEqual(code, 0, stdout)
        values = dispatch.call_args.kwargs
        self.assertEqual(values["mode"], "resume")
        self.assertIsNone(values["work_session_ref"])
        self.assertIsNone(values["reviewer_claim"])
        self.assertIsNone(values["options"])

    def test_new_original_cannot_be_replaced_by_legacy_inputs_or_a_fresh_mode(self):
        base = ["--client-app-ref", APP, "--task-route-ref", ROUTE, "--resume"]
        for extra in (["--reviewed-by", PRIVATE], ["--expected-plan-sha256", PRIVATE],
                      ["--selection-manifest", PRIVATE], ["--resume-approval-id", PRIVATE],
                      ["--expected-manifest-sha256", PRIVATE], ["--branch", PRIVATE],
                      ["--credential-mode", "stored"], ["--approve"], ["--dry-run"]):
            with self.subTest(flag=extra[0]), patch.object(command, "dispatch_session_git_backup") as dispatch:
                code, stdout, stderr = self.call([*base, *extra])
                self.assertNotEqual(code, 0)
                dispatch.assert_not_called()
                self.assertNotIn(PRIVATE, stdout + stderr)
                self.assertEqual(json.loads(stdout)["effects_state"], "none")

    def test_unavailable_live_observer_stops_before_dispatch_without_private_error(self):
        unavailable = SimpleNamespace(status=lambda: {"mode": "unavailable"})
        with patch.object(progress_observer, "_git_command_progress_observer",
                          return_value=nullcontext(unavailable)), \
             patch.object(command, "dispatch_session_git_backup") as dispatch:
            code, stdout, stderr = self.call([
                "--client-app-ref", APP, "--task-route-ref", ROUTE, "--resume",
            ])
        self.assertNotEqual(code, 0)
        self.assertEqual(json.loads(stdout)["reason_codes"], ["work_session_git_progress_unavailable"])
        self.assertEqual(json.loads(stdout)["effects_state"], "none")
        dispatch.assert_not_called()
        self.assertNotIn(PRIVATE, stdout + stderr)

    def test_observer_lifecycle_interrupts_keep_fixed_errors_and_original_proof(self):
        original = {"ok": True, "original_commit_verified": True}
        observer = SimpleNamespace(status=lambda: {"mode": "synchronous", "heartbeat_available": False})

        @contextmanager
        def interrupted_close():
            yield observer
            raise KeyboardInterrupt(PRIVATE)

        for boundary in ("construction", "closure"):
            replacement = {"side_effect": KeyboardInterrupt(PRIVATE)} if boundary == "construction" else {
                "side_effect": interrupted_close,
            }
            with self.subTest(boundary=boundary), \
                 patch.object(progress_observer, "_git_command_progress_observer", **replacement), \
                 patch.object(command, "dispatch_session_git_backup", return_value=original) as dispatch:
                code, stdout, stderr = self.call([
                    "--client-app-ref", APP, "--task-route-ref", ROUTE, "--resume",
                ])
                result = json.loads(stdout)
                self.assertNotEqual(code, 0)
                self.assertEqual(result["reason_code"], "work_session_wait_cancelled")
                self.assertEqual(result["effects_state"], "none" if boundary == "construction" else "unknown")
                self.assertEqual(result["original_commit_verified"], boundary == "closure")
                self.assertEqual(dispatch.call_count, int(boundary == "closure"))
                self.assertNotIn(PRIVATE, stdout + stderr)


class SessionGitCommandBoundaryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="wom-session-git-command-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "archive.yml").write_text("archive_id: archive:personal:synthetic-git-command\n", encoding="utf-8")
        self.calls = []
        fake = ModuleType("wom_kit.work_session_git_workflow")
        fake._ERRORS = frozenset({"work_session_git_original_approval_missing"})
        class WorkSessionGitWorkflowError(RuntimeError):
            code = "work_session_git_original_approval_missing"
            original_commit_verified = True
        fake.WorkSessionGitWorkflowError = WorkSessionGitWorkflowError
        for mode, name in (("preview", "_preview_session_git_backup_held"),
                           ("apply", "_execute_session_git_backup_held"),
                           ("resume", "_resume_session_git_backup_held")):
            def run(root, *, held, _mode=mode, **values):
                self.assertIs(type(held), exact.ExactOperationWriterLock)
                held.verify_held()
                self.calls.append((_mode, values))
                return {"ok": True, "mode": _mode}
            setattr(fake, name, run)
        self.fake = fake
        modules = patch.dict(sys.modules, {fake.__name__: fake})
        parent = patch.object(wom_kit, "work_session_git_workflow", fake, create=True)
        modules.start()
        parent.start()
        self.addCleanup(modules.stop)
        self.addCleanup(parent.stop)

    def call(self, mode="preview", **options):
        values = dict(client_app_ref=APP, task_route_ref=ROUTE, work_session_ref=SESSION)
        values.update(options)
        return command.dispatch_session_git_backup(self.root, mode=mode, **values)

    def test_all_modes_use_real_shared_lock_and_loaded_runtime_guard(self):
        for mode in ("preview", "apply", "resume"):
            values = {"reviewer_claim": "person:synthetic-reviewer"} if mode == "apply" else {}
            result = self.call(mode, **values)
            self.assertTrue(result["ok"], result)
            self.assertEqual(self.calls[-1][0], mode)
        for name in ("native", "key_provider", "approval_id", "manifest_sha256", "allow_scope"):
            self.assertNotIn(name, inspect.signature(command.dispatch_session_git_backup).parameters)

    def test_invalid_or_original_replacement_input_stops_before_domain_runner(self):
        for mode, changes in (("resume", {"reviewer_claim": PRIVATE}), ("resume", {"options": {"branch": PRIVATE}}),
                              ("preview", {"options": {"native": PRIVATE}}), ("apply", {}),
                              ("preview", {"client_app_ref": None}), ("preview", {"task_route_ref": PRIVATE})):
            self.assertFalse(self.call(mode, **changes)["ok"])
        self.assertEqual(self.calls, [])

    def test_cancel_and_private_errors_are_truthful_and_content_free(self):
        cancelled = self.call(cancel_requested=lambda: True)
        self.assertFalse(cancelled["ok"])
        self.assertEqual(cancelled["effects_state"], "none")
        self.assertEqual(self.calls, [])
        def fail(*args, **kwargs):
            raise OSError(PRIVATE)
        self.fake._preview_session_git_backup_held = fail
        failed = self.call()
        self.assertEqual(failed["effects_state"], "unknown")
        self.assertFalse(failed["backup_completion_verified"])
        self.assertNotIn("backup_performed", failed)
        self.assertNotIn(PRIVATE, json.dumps(failed))

    def test_only_actual_domain_completion_flag_is_preserved_not_callback_impersonation(self):
        def completed_then_refused(*args, **kwargs):
            raise self.fake.WorkSessionGitWorkflowError()
        self.fake._resume_session_git_backup_held = completed_then_refused
        result = self.call("resume")
        self.assertTrue(result["original_commit_verified"])
        self.assertFalse(result["backup_completion_verified"])
        def callback_raises(*args):
            raise self.fake.WorkSessionGitWorkflowError()
        def domain_calls_progress(root, *, progress_hook, **kwargs):
            progress_hook({"stage": "synthetic"})
        self.fake._preview_session_git_backup_held = domain_calls_progress
        forged = self.call(progress=callback_raises)
        self.assertFalse(forged["original_commit_verified"])
        self.assertEqual(forged["reason_code"], "work_session_git_command_unavailable")

    def test_keyboard_interrupt_before_and_after_entry_uses_fixed_private_cancellation(self):
        def interrupt(*args, **kwargs):
            raise KeyboardInterrupt(PRIVATE)
        before = self.call(cancel_requested=interrupt)
        self.assertEqual(before["reason_code"], "work_session_wait_cancelled")
        self.assertEqual(before["effects_state"], "none")
        self.fake._preview_session_git_backup_held = interrupt
        after = self.call()
        self.assertEqual(after["reason_code"], "work_session_wait_cancelled")
        self.assertEqual(after["effects_state"], "unknown")
        self.assertNotIn(PRIVATE, json.dumps([before, after]))


if __name__ == "__main__":
    unittest.main()
