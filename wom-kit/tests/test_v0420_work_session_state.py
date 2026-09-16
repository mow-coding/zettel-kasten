"""Actual actor/registry/CAS transitions with original human MAC verification."""

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from wom_kit import exact_human_approval_workflow as workflow
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_actor as actor
from wom_kit import work_session_claim as claim
from wom_kit import work_session_registry as registry
from wom_kit import work_session_registry_intent as intents
from wom_kit import work_session_state as subject
import test_v0420_work_session_lifecycle as fixture


class WorkSessionStateTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.TaskLifecycleTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        t = self.fixture
        created = t.create()
        self.session = created["work_session_binding"]["work_session_ref"]
        claim._claim_task_core(t.root, client_app_ref=t.app, task_route_ref=t.route,
                               work_session_ref=self.session, key_provider=t.key)
        # Existing production key seam only: no new public secret/authority arg.
        key_patch = patch.object(workflow, "_production_key_provider", return_value=t.key)
        key_patch.start()
        self.addCleanup(key_patch.stop)

    def run_state(self, action="pause", original_resume=False, **changes):
        t = self.fixture
        arguments = dict(action=action, original_resume=original_resume,
                         client_app_ref=t.app, task_route_ref=t.route, work_session_ref=self.session)
        arguments.update(changes)
        with exact.ExactOperationWriterLock(t.root) as held:
            return subject._transition_task_held(t.root, held=held, **arguments)

    def reject(self, call, code=None, committed=False):
        with self.assertRaises(subject.WorkSessionStateError) as caught:
            call()
        error = caught.exception
        if code is not None:
            self.assertEqual(error.code, code)
        self.assertEqual(error.original_commit_verified, committed)
        self.assertIsNone(error.__context__)
        self.assertIsNone(error.__cause__)
        for value in (str(self.fixture.root), self.fixture.app, self.fixture.route, "Synthetic private", "PRIVATE_FAILURE"):
            self.assertNotIn(value, repr(error))

    def test_real_pause_resume_keep_original_human_evidence_and_have_readonly_original_replays(self):
        t = self.fixture
        receipts = t.claims()
        first_claim = t.routing.read().document()["claim_ref"]
        paused = self.run_state()
        self.assertEqual(paused["state"], "paused")
        self.assertFalse(paused["current_claim_ownership_verified"])
        self.assertIsNone(t.routing.read().document()["claim_ref"])
        self.assertEqual(t.store.read().revision, 4)
        for action, result in (("pause", paused), ("resume", None)):
            with self.subTest(action=action):
                if result is None:
                    result = self.run_state(action)
                before = t.domain_files()
                with patch.object(intents, "prepare_registry_intent", side_effect=AssertionError("replay replanned")), \
                     patch.object(intents, "observe_or_apply_registry_intent", side_effect=AssertionError("terminal executed")), \
                     patch.object(actor.WorkSessionActorStore, "save", side_effect=AssertionError("terminal rewrote actor")):
                    replayed = self.run_state(action, original_resume=True)
                self.assertTrue(replayed["original_operation_already_completed"])
                self.assertEqual(replayed["plan_sha256"], result["plan_sha256"])
                self.assertEqual(t.domain_files(), before)
                self.assertTrue(result["original_commit_verified"] and result["independent_post_verification"])
                self.assertFalse(result["human_approval_granted"])
        last = t.routing.read().document()
        self.assertNotEqual(first_claim, last["claim_ref"])
        self.assertEqual(t.store.read().revision, 5)
        self.assertEqual(t.claims(), receipts)
        self.assertEqual(t.native.calls, 1)
        for value in (first_claim, last["claim_ref"], str(t.root), "Synthetic private"):
            self.assertNotIn(value, json.dumps([paused, result, replayed]))

    def test_fresh_and_original_resume_modes_cannot_be_substituted_or_repeat_claim_creation(self):
        t = self.fixture
        before = t.domain_files()
        self.reject(lambda: self.run_state("resume"), "work_session_state_current_unavailable")
        self.reject(lambda: self.run_state("pause", True), "work_session_state_action_mismatch")
        self.assertEqual(t.domain_files(), before)
        self.run_state()
        before = t.domain_files()
        self.reject(lambda: self.run_state("pause"))
        self.reject(lambda: self.run_state("resume", True), "work_session_state_action_mismatch")
        self.assertEqual(t.domain_files(), before)
        self.run_state("resume")
        before = t.domain_files()
        self.reject(lambda: self.run_state("resume"), "work_session_state_current_unavailable")
        self.reject(lambda: self.run_state("pause", True), "work_session_state_action_mismatch")
        self.assertEqual(t.domain_files(), before)

    def cut(self, action, boundary):
        original_save = intents.save_registry_intent
        original_actor = actor.WorkSessionActorStore.save
        original_commit = registry.WorkSessionRegistryStore.commit
        def intent_save(*args, **kwargs):
            result = original_save(*args, **kwargs)
            if boundary == "intent":
                raise OSError("PRIVATE_FAILURE after intent")
            return result
        def actor_save(store, **kwargs):
            pending = kwargs.get("pending_registry_intent_plan_sha256") is not None
            completed = kwargs.get("last_completed_operation") is not None
            if boundary == "before_terminal" and completed:
                raise OSError("PRIVATE_FAILURE before terminal")
            result = original_actor(store, **kwargs)
            if (boundary == "pending" and pending) or (boundary == "terminal" and completed):
                raise OSError("PRIVATE_FAILURE after actor")
            return result
        def commit(store, plan, **kwargs):
            result = original_commit(store, plan, **kwargs)
            if boundary == "registry" and plan.action == action:
                raise OSError("PRIVATE_FAILURE after registry")
            return result
        with patch.object(intents, "save_registry_intent", new=intent_save), \
             patch.object(actor.WorkSessionActorStore, "save", new=actor_save), \
             patch.object(registry.WorkSessionRegistryStore, "commit", new=commit):
            self.reject(lambda: self.run_state(action), committed=boundary in {"before_terminal", "terminal"})

    def test_pending_original_pause_resumes_without_preparation_or_second_human_approval(self):
        t = self.fixture
        self.cut("pause", "pending")
        pending = t.routing.read().document()["pending_registry_intent_plan_sha256"]
        before = t.domain_files()
        self.reject(lambda: self.run_state("pause"), "work_session_original_operation_pending")
        self.reject(lambda: self.run_state("resume", True), "work_session_state_action_mismatch")
        self.assertEqual(t.domain_files(), before)
        with patch.object(intents, "prepare_registry_intent", side_effect=AssertionError("new intent")), \
             patch.object(intents, "save_registry_intent", side_effect=AssertionError("replaced intent")):
            result = self.run_state("pause", True)
        self.assertEqual(result["plan_sha256"], pending)
        self.assertEqual(result["state"], "paused")
        self.assertEqual(t.native.calls, 1)

    def test_unselected_orphan_resume_intent_does_not_authorize_another_claim(self):
        t = self.fixture
        self.run_state()
        self.cut("resume", "intent")
        self.assertIsNone(t.routing.read().document()["pending_registry_intent_plan_sha256"])
        before = t.domain_files()
        with patch.object(intents, "prepare_registry_intent", side_effect=AssertionError("orphan replanned")), \
             patch.object(registry.WorkSessionRegistryStore, "commit", side_effect=AssertionError("orphan committed")):
            self.reject(lambda: self.run_state("resume", True), "work_session_state_action_mismatch")
        self.assertEqual(t.domain_files(), before)
        self.assertEqual(t.store.read()._document["sessions"][self.session]["state"], "paused")

    def test_committed_resume_and_terminal_output_loss_keep_exact_original_claim(self):
        for boundary in ("registry", "before_terminal", "terminal"):
            with self.subTest(boundary=boundary):
                self.run_state("pause")
                self.cut("resume", boundary)
                t = self.fixture
                claim_ref = t.store.read()._document["sessions"][self.session]["claim_ref"]
                with patch.object(registry.WorkSessionRegistryStore, "commit", side_effect=AssertionError("duplicate commit")), \
                     patch.object(intents, "prepare_registry_intent", side_effect=AssertionError("replanned resume")):
                    result = self.run_state("resume", True)
                self.assertEqual(result["state"], "claimed")
                self.assertEqual(t.routing.read().document()["claim_ref"], claim_ref)
                self.assertEqual(t.native.calls, 1)

    def test_old_pause_outcome_does_not_forge_current_paused_state(self):
        t = self.fixture
        self.run_state()
        with exact.ExactOperationWriterLock(t.root) as held:
            transition = registry.plan_transition(t.store.read(), action="resume", client_app_ref=t.app,
                                                   work_session_ref=self.session)
            t.store.commit(transition, held_lock=held)
        before = t.domain_files()
        self.reject(lambda: self.run_state("pause", True), "work_session_state_current_unavailable", committed=True)
        self.assertEqual(t.domain_files(), before)

    def test_wrong_scope_lock_modes_and_failed_original_mac_are_zero_effects(self):
        t = self.fixture
        before = t.domain_files()
        for changes in ({"work_session_ref": None}, {"work_session_ref": registry._new_ref("work_session")},
                        {"task_route_ref": actor.new_task_route_ref()}, {"client_app_ref": registry._new_ref("client_app")},
                        {"action": "handoff"}, {"original_resume": 1}):
            with self.subTest(changes=tuple(changes)):
                self.reject(lambda: self.run_state(**changes))
        self.reject(lambda: subject._transition_task_held(t.root, held=None, action="pause", original_resume=False,
            client_app_ref=t.app, task_route_ref=t.route, work_session_ref=self.session), "work_session_lock_required")
        with patch.object(t.key, "use_key", side_effect=OSError("PRIVATE_FAILURE from secret seam")):
            self.reject(lambda: self.run_state())
        self.assertEqual(t.domain_files(), before)

    def test_copied_same_app_route_is_not_original_create_scope(self):
        t = self.fixture
        old = t.routing.read().document()
        route = actor.new_task_route_ref()
        copied = actor.WorkSessionActorStore(t.store, client_app_ref=t.app, task_route_ref=route)
        with exact.ExactOperationWriterLock(t.root) as held:
            copied.save(expected_sha256=None, held_lock=held, work_session_ref=self.session,
                observed_binding=t.store.read().binding(self.session), claim_ref=old["claim_ref"],
                last_completed_operation=actor.CompletedOperationSelector.from_document(old["last_completed_operation"]))
        before = t.domain_files()
        self.reject(lambda: self.run_state(task_route_ref=route), "work_session_original_operation_changed")
        self.assertEqual(t.domain_files(), before)

    def test_actor_cas_drift_after_intent_preserves_changed_pointer_without_registry_mutation(self):
        t = self.fixture
        before_revision = t.store.read().revision
        original = intents.save_registry_intent
        changed = {}
        def save(store, intent, *, held_lock):
            original(store, intent, held_lock=held_lock)
            selected = t.routing.read()
            document = selected.document()
            replacement = t.routing.save(expected_sha256=selected.sha256, held_lock=held_lock,
                work_session_ref=self.session, observed_binding=t.store.read().binding(self.session),
                claim_ref=document["claim_ref"], pending_registry_intent_plan_sha256="sha256:" + "f" * 64)
            changed["sha"] = replacement.sha256
        with patch.object(intents, "save_registry_intent", new=save):
            self.reject(lambda: self.run_state(), "work_session_task_context_changed")
        self.assertEqual(t.store.read().revision, before_revision)
        self.assertEqual(t.routing.read().sha256, changed["sha"])

    def test_pending_actor_source_mismatch_is_not_permission_to_publish_original_transition(self):
        t = self.fixture
        self.cut("pause", "pending")
        selected = t.routing.read()
        document = selected.document()
        with exact.ExactOperationWriterLock(t.root) as held:
            t.routing.save(expected_sha256=selected.sha256, held_lock=held, work_session_ref=self.session,
                observed_binding=t.store.read().binding(self.session), claim_ref=registry._new_ref("claim"),
                pending_registry_intent_plan_sha256=document["pending_registry_intent_plan_sha256"])
        before = t.domain_files()
        self.reject(lambda: self.run_state("pause", True), "work_session_original_operation_changed")
        self.assertEqual(t.domain_files(), before)

    def test_real_child_termination_after_pending_and_after_resume_commit_reuses_original_selector(self):
        child = r'''
import os, sys
from pathlib import Path
from wom_kit import exact_operation_manifest as exact
from wom_kit import exact_human_approval_workflow as workflow
from wom_kit import work_session_state as state, work_session_registry as registry, work_session_actor as actor
from test_v0420_work_session_operation import _Key
root, app, route, session, action, boundary = sys.argv[1:]
workflow._production_key_provider = lambda *args, **kwargs: _Key()
if boundary == "pending":
    original = actor.WorkSessionActorStore.save
    def save(store, **kwargs):
        result = original(store, **kwargs)
        if kwargs.get("pending_registry_intent_plan_sha256") is not None:
            os._exit(71)
        return result
    actor.WorkSessionActorStore.save = save
else:
    original = registry.WorkSessionRegistryStore.commit
    def commit(store, plan, **kwargs):
        result = original(store, plan, **kwargs)
        if plan.action == action:
            os._exit(72)
        return result
    registry.WorkSessionRegistryStore.commit = commit
with exact.ExactOperationWriterLock(Path(root)) as held:
    state._transition_task_held(Path(root), held=held, action=action, original_resume=False,
        client_app_ref=app, task_route_ref=route, work_session_ref=session)
raise AssertionError("synthetic cut not reached")
'''
        t = self.fixture
        environment = os.environ.copy()
        environment["PYTHONPATH"] = os.pathsep.join([str(Path(__file__).resolve().parents[1] / "src"), str(Path(__file__).parent)])
        for action, boundary, code in (("pause", "pending", 71), ("resume", "registry", 72)):
            with self.subTest(action=action):
                result = subprocess.run([sys.executable, "-B", "-c", child, str(t.root), t.app, t.route,
                    self.session, action, boundary], env=environment, capture_output=True, text=True,
                    timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                self.assertEqual(result.returncode, code, "synthetic state cut not reached")
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "")
                original_plan = t.routing.read().document()["pending_registry_intent_plan_sha256"]
                with patch.object(intents, "prepare_registry_intent", side_effect=AssertionError("child cut replanned")):
                    resumed = self.run_state(action, True)
                self.assertEqual(resumed["plan_sha256"], original_plan)
                self.assertEqual(resumed["state"], "paused" if action == "pause" else "claimed")
        self.assertEqual(t.native.calls, 1)


if __name__ == "__main__":
    unittest.main()
