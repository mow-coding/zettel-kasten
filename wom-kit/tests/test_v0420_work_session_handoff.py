"""Real original handoff authority, actor publication and strict continuation."""

import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from wom_kit import exact_human_approval_workflow as workflow
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_actor as actor
from wom_kit import work_session_claim as claim
from wom_kit import work_session_execution as execution
from wom_kit import work_session_handoff as subject
from wom_kit import work_session_operation as operation
from wom_kit import work_session_registry as registry
from wom_kit.process_launch import noninteractive_creationflags
import test_v0420_work_session_lifecycle as fixture


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.task = fixture.TaskLifecycleTests("runTest")
        self.task.setUp()
        self.addCleanup(self.task.doCleanups)
        t = self.task
        self.session = t.create()["work_session_binding"]["work_session_ref"]
        claim._claim_task_core(t.root, client_app_ref=t.app, task_route_ref=t.route,
                              work_session_ref=self.session, key_provider=t.key)
        target = registry.plan_transition(t.store.read(), action="register-app", label="Synthetic receiving app")
        with exact.ExactOperationWriterLock(t.root) as held:
            t.store.commit(target, held_lock=held)
        self.target = target.result_refs[0]
        for owner, name, value in ((workflow, "_production_key_provider", t.key),
                                   (windows, "_CtypesTaskDialogNative", t.native)):
            replacement = patch.object(owner, name, return_value=value)
            replacement.start()
            self.addCleanup(replacement.stop)

    def run_handoff(self, original_resume=False, **changes):
        t = self.task
        arguments = dict(client_app_ref=t.app, task_route_ref=t.route, work_session_ref=self.session,
                         target_app_ref=self.target, original_resume=original_resume,
                         reviewer_claim=None if original_resume else "person:synthetic-handoff-reviewer")
        arguments.update(changes)
        with exact.ExactOperationWriterLock(t.root) as held:
            return subject._handoff_task_held(t.root, held=held, **arguments)

    def reject(self, call, code=None, committed=False):
        with self.assertRaises(subject.WorkSessionHandoffError) as caught:
            call()
        error = caught.exception
        if code is not None:
            self.assertEqual(error.code, code)
        self.assertEqual(error.original_commit_verified, committed)
        self.assertIsNone(error.__context__)
        self.assertIsNone(error.__cause__)
        for private in (str(self.task.root), self.task.app, self.task.route, "PRIVATE_FAILURE"):
            self.assertNotIn(private, repr(error))

    def test_actual_handoff_consumes_claim_preserves_origin_and_transfers_no_artifacts(self):
        t = self.task
        (t.root / "synthetic-preserved.bin").write_bytes(b"synthetic canonical object")
        before = t.domain_files()
        original = t.routing.read().document()
        old_claim = original["claim_ref"]
        native_calls = t.native.calls
        key_use = t.key.use_key
        consuming = False

        def non_nested(*args, **kwargs):
            nonlocal consuming
            self.assertFalse(consuming, "nested key consumer")
            consuming = True
            try:
                return key_use(*args, **kwargs)
            finally:
                consuming = False

        with patch.object(t.key, "use_key", new=non_nested):
            result = self.run_handoff()
        current = t.store.read()
        session = current._document["sessions"][self.session]
        self.assertEqual(session["state"], "handoff_pending")
        self.assertEqual(session["handoff_app_ref"], self.target)
        self.assertIsNone(session["claim_ref"])
        self.assertEqual(current._document["workstreams"][session["workstream_ref"]]["active_session_ref"], self.session)
        selected = t.routing.read().document()
        self.assertEqual(selected["established_origin"], original["established_origin"])
        self.assertEqual(selected["observed_binding"], current.binding(self.session).document())
        self.assertIsNone(selected["claim_ref"])
        self.assertIsNone(selected["pending_manifest_sha256"])
        self.assertEqual(selected["last_completed_operation"]["kind"], "human_session_decision")
        self.assertEqual(t.native.calls, native_calls + 1)
        for name, value in before.items():
            self.assertEqual((t.root / name).read_bytes(), value)
        self.assertFalse(result["ownership_transferred"])
        self.assertFalse(result["artifact_responsibility_transferred"])
        self.assertFalse(result["current_claim_ownership_verified"])
        for private in (old_claim, str(t.root), "Synthetic receiving app", "Synthetic private"):
            self.assertNotIn(private, json.dumps(result))

    def test_terminal_resume_is_load_only_and_exact_target_and_action_are_required(self):
        t = self.task
        first = self.run_handoff()
        before = t.domain_files()
        with patch.object(execution, "_execute_session_decision_held", side_effect=AssertionError("new approval")), \
             patch.object(operation, "apply_session_decision_with_claim", side_effect=AssertionError("new writer")), \
             patch.object(actor.WorkSessionActorStore, "save", side_effect=AssertionError("new actor image")):
            result = self.run_handoff(True)
            self.reject(lambda: self.run_handoff(True, target_app_ref=t.app))
            self.reject(lambda: self.run_handoff(True, reviewer_claim="person:synthetic-replacement"))
            self.reject(self.run_handoff)
        self.assertTrue(result["original_operation_already_completed"])
        self.assertEqual(result["receipt_sha256"], first["receipt_sha256"])
        self.assertEqual(t.domain_files(), before)
        self.assertEqual(t.native.calls, 2)

    def test_started_precheckpoint_resumes_original_with_no_second_native(self):
        t = self.task
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=OSError("PRIVATE_FAILURE")):
            self.reject(self.run_handoff)
        self.assertEqual(t.store.read()._document["sessions"][self.session]["state"], "claimed")
        pending = t.routing._read(current=False).document()
        self.assertIsNotNone(pending["pending_manifest_sha256"])
        claims = set(t.claims())
        result = self.run_handoff(True)
        self.assertEqual(result["state"], "handoff_pending")
        self.assertEqual(set(t.claims()), claims)
        self.assertEqual(t.native.calls, 2)

    def test_completed_registry_with_stale_pending_actor_uses_historical_reader(self):
        t = self.task
        with patch.object(subject, "_finish", side_effect=subject.WorkSessionHandoffError(
                "work_session_task_context_changed", original_commit_verified=True)):
            self.reject(self.run_handoff, committed=True)
        self.assertEqual(t.store.read()._document["sessions"][self.session]["state"], "handoff_pending")
        selected = t.routing._read(current=False).document()
        self.assertIsNotNone(selected["claim_ref"])
        self.assertIsNotNone(selected["pending_manifest_sha256"])
        with patch.object(actor.WorkSessionActorStore, "read", side_effect=AssertionError("stale live actor read")):
            result = self.run_handoff(True)
        self.assertTrue(result["current_state_verified"])
        self.assertIsNone(t.routing.read().document()["claim_ref"])
        self.assertEqual(t.native.calls, 2)

    def test_output_loss_after_terminal_actor_save_retains_original_discovery(self):
        t = self.task
        original_save = actor.WorkSessionActorStore.save

        def saved_then_lost(store, **kwargs):
            result = original_save(store, **kwargs)
            if kwargs.get("last_completed_operation") is not None:
                raise OSError("PRIVATE_FAILURE")
            return result

        with patch.object(actor.WorkSessionActorStore, "save", new=saved_then_lost):
            self.reject(self.run_handoff, "work_session_task_context_changed", committed=True)
        before = t.domain_files()
        with patch.object(actor.WorkSessionActorStore, "save", side_effect=AssertionError("terminal rewritten")):
            result = self.run_handoff(True)
        self.assertTrue(result["original_operation_already_completed"])
        self.assertEqual(t.domain_files(), before)
        self.assertEqual(t.native.calls, 2)

    def test_preclaim_pending_without_mac_never_auto_approves_or_falls_back_to_origin(self):
        t = self.task
        original_save = actor.WorkSessionActorStore.save
        before_claims = t.claims()

        def lost_before_claim(store, **kwargs):
            result = original_save(store, **kwargs)
            if kwargs.get("pending_manifest_sha256") is not None:
                raise OSError("PRIVATE_FAILURE")
            return result

        with patch.object(actor.WorkSessionActorStore, "save", new=lost_before_claim):
            self.reject(self.run_handoff)
        self.assertEqual(t.claims(), before_claims)
        before = t.domain_files()
        with patch.object(execution, "_execute_session_decision_held", side_effect=AssertionError("implicit approval")), \
             patch.object(operation, "apply_session_decision_with_claim", side_effect=AssertionError("unapproved writer")):
            self.reject(lambda: self.run_handoff(True))
            self.reject(self.run_handoff, "work_session_original_operation_pending")
        self.assertEqual(t.domain_files(), before)
        self.assertEqual(t.native.calls, 2)

    def test_wrong_route_session_origin_mac_and_missing_lock_cannot_request_handoff(self):
        t = self.task
        before = t.domain_files()
        for changes in ({"task_route_ref": actor.new_task_route_ref()},
                        {"work_session_ref": registry._new_ref("work_session")},
                        {"target_app_ref": None}, {"target_app_ref": t.app},
                        {"target_app_ref": registry._new_ref("client_app")}):
            with self.subTest(fields=tuple(changes)):
                self.reject(lambda: self.run_handoff(**changes))
        self.reject(lambda: self.run_handoff(True))
        with patch.object(t.key, "use_key", side_effect=OSError("PRIVATE_FAILURE")):
            self.reject(self.run_handoff)
        self.reject(lambda: subject._handoff_task_held(t.root, held=None,
            client_app_ref=t.app, task_route_ref=t.route, work_session_ref=self.session,
            target_app_ref=self.target, original_resume=False, reviewer_claim="person:synthetic"))
        self.assertEqual(t.domain_files(), before)
        self.assertEqual(t.native.calls, 1)
        parameters = inspect.signature(subject._handoff_task_held).parameters
        for forbidden in ("native", "key_provider", "claim_ref", "context", "approval_id"):
            self.assertNotIn(forbidden, parameters)

    def test_cancel_and_actor_change_during_native_leave_no_handoff_claim(self):
        t = self.task
        before = t.domain_files()
        t.native.approve = False
        self.reject(self.run_handoff, "exact_human_approval_cancelled")
        self.assertEqual(t.domain_files(), before)
        t.native.approve = True
        old_claims = t.claims()

        def mutate_actor():
            values = t.routing.read().document()
            # Deliberately forge a self-consistent image during the synthetic
            # dialog. The expected actor SHA must detect the untrusted change.
            values["pending_manifest_sha256"] = "sha256:" + "e" * 64
            values["pending_context_sha256"] = "sha256:" + "f" * 64
            values["actor_sha256"] = actor._sha(registry._canonical({key: value for key, value in values.items()
                                                                   if key != "actor_sha256"}))
            altered = actor.ActorContext(registry._canonical(values))
            image = t.root.joinpath(*actor.PRIVATE_ROOT, t.app, t.route, f"{values['revision']:012d}.json")
            image.write_bytes(altered._raw)

        t.native.before_click = mutate_actor
        self.reject(self.run_handoff)
        self.assertEqual(t.claims(), old_claims)
        self.assertEqual(t.store.read()._document["sessions"][self.session]["state"], "claimed")

    def test_later_accept_is_not_reported_as_current_pending_handoff(self):
        t = self.task
        self.run_handoff()
        with exact.ExactOperationWriterLock(t.root) as held:
            accepted = execution._execute_session_decision_held(t.root, held=held, action="accept",
                client_app_ref=self.target, task_route_ref=actor.new_task_route_ref(), work_session_ref=self.session,
                reviewer_claim="person:synthetic-receiver", native=t.native, key_provider=t.key)
        self.assertNotEqual(accepted["work_session_binding"]["work_session_ref"], self.session)
        before = t.domain_files()
        self.reject(lambda: self.run_handoff(True), "work_session_handoff_current_unavailable", committed=True)
        self.assertEqual(t.domain_files(), before)

    def test_legacy_actor_origin_is_added_only_to_new_approved_pending_image(self):
        legacy = fixture.TaskLifecycleTests("runTest")
        legacy.setUp()
        self.addCleanup(legacy.doCleanups)
        original_save = actor.WorkSessionActorStore.save

        def old_actor_save(store, **kwargs):
            # Emulate an older caller's already supported actor image shape;
            # the actual create approval, writer and claim remain unchanged.
            kwargs.pop("established_origin", None)
            return original_save(store, **kwargs)

        with patch.object(actor.WorkSessionActorStore, "save", new=old_actor_save):
            session = legacy.create()["work_session_binding"]["work_session_ref"]
            claim._claim_task_core(legacy.root, client_app_ref=legacy.app, task_route_ref=legacy.route,
                                  work_session_ref=session, key_provider=legacy.key)
        self.assertNotIn("established_origin", legacy.routing.read().document())
        target = registry.plan_transition(legacy.store.read(), action="register-app", label="Synthetic legacy target")
        with exact.ExactOperationWriterLock(legacy.root) as held:
            legacy.store.commit(target, held_lock=held)
        before = legacy.domain_files()
        additions = []

        def observe_attachment(store, **kwargs):
            if kwargs.get("established_origin") is not None:
                self.assertIsNotNone(kwargs.get("pending_manifest_sha256"))
                self.assertEqual(legacy.native.calls, 2)
                additions.append(kwargs["established_origin"])
            return original_save(store, **kwargs)

        with patch.object(workflow, "_production_key_provider", return_value=legacy.key), \
             patch.object(windows, "_CtypesTaskDialogNative", return_value=legacy.native), \
             patch.object(actor.WorkSessionActorStore, "save", new=observe_attachment):
            with exact.ExactOperationWriterLock(legacy.root) as held:
                result = subject._handoff_task_held(legacy.root, held=held, client_app_ref=legacy.app,
                    task_route_ref=legacy.route, work_session_ref=session, target_app_ref=target.result_refs[0],
                    original_resume=False, reviewer_claim="person:synthetic-legacy-handoff")
        self.assertEqual(result["state"], "handoff_pending")
        self.assertEqual(len(additions), 1)
        self.assertEqual(legacy.routing.read().document()["established_origin"], additions[0].document())
        for name, value in before.items():
            self.assertEqual((legacy.root / name).read_bytes(), value)

    def test_real_process_loss_after_original_completion_fresh_process_resumes_same_actor(self):
        t = self.task
        child = r'''
import json, os, sys
from pathlib import Path
from unittest.mock import patch
from wom_kit import exact_human_approval_workflow as workflow
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_handoff as handoff
from wom_kit import work_session_operation as operation
from test_v0420_work_session_execution import SessionNative, _Key
root, app, route, session, target, mode = sys.argv[1:]
native, key = SessionNative(), _Key()
def cut(*args, **kwargs): os._exit(73)
with patch.object(workflow, '_production_key_provider', return_value=key), patch.object(windows, '_CtypesTaskDialogNative', return_value=native):
    with exact.ExactOperationWriterLock(Path(root)) as held:
        args = dict(held=held, client_app_ref=app, task_route_ref=route, work_session_ref=session, target_app_ref=target,
                    original_resume=mode=='resume', reviewer_claim=None if mode=='resume' else 'person:synthetic-handoff-reviewer')
        if mode == 'cut':
            with patch.object(handoff, '_finish', new=cut): handoff._handoff_task_held(Path(root), **args)
        else:
            with patch.object(operation, 'apply_session_decision_with_claim', side_effect=AssertionError('duplicate writer')):
                result = handoff._handoff_task_held(Path(root), **args)
            print(json.dumps({'ok': result['ok'], 'state': result['state'], 'native_calls': native.calls,
                              'current': result['current_state_verified']}))
'''
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join((str(Path(__file__).resolve().parents[1] / "src"),
                                            str(Path(__file__).resolve().parent)))
        base = [sys.executable, "-B", "-c", child, str(t.root), t.app, t.route, self.session, self.target]
        options = dict(env=env, capture_output=True, text=True, timeout=90,
                       creationflags=noninteractive_creationflags())
        cut = subprocess.run([*base, "cut"], **options)
        self.assertEqual(cut.returncode, 73, "synthetic cut did not occur")
        original = t.routing._read(current=False).document()
        claims = t.claims()
        self.assertIsNotNone(original["pending_manifest_sha256"])
        resumed = subprocess.run([*base, "resume"], **options)
        self.assertEqual(resumed.returncode, 0, "synthetic original resume failed")
        self.assertEqual(json.loads(resumed.stdout), {"ok": True, "state": "handoff_pending", "native_calls": 0, "current": True})
        self.assertEqual(t.claims(), claims)
        terminal = t.routing.read().document()["last_completed_operation"]
        self.assertEqual(terminal["manifest_sha256"], original["pending_manifest_sha256"])


if __name__ == "__main__":
    unittest.main()
