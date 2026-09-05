"""Real human recovery and original continuation over synthetic archives."""

import inspect
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
from wom_kit import work_session_actor_execution as actor_guard
from wom_kit import work_session_bundle as bundle
from wom_kit import work_session_claim as claim
from wom_kit import work_session_execution as execution
from wom_kit import work_session_lifecycle as lifecycle
from wom_kit import work_session_operation as operation
from wom_kit import work_session_recovery as subject
from wom_kit import work_session_registry as registry
from wom_kit import work_session_state as state
from wom_kit.process_launch import noninteractive_creationflags
import test_v0420_work_session_handoff as fixture
from test_v0420_work_session_rereview import GuardedKey
from test_v0420_work_session_operation import _Native, _Key


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.case = fixture.HandoffTests("runTest")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.t = self.case.task
        self.app, self.route, self.session = self.t.app, self.t.route, self.case.session
        self.routing = self.t.routing
        self.key = GuardedKey(self.t.key)
        self.t.key = self.key
        provider = patch.object(workflow, "_production_key_provider", return_value=self.key)
        provider.start()
        self.addCleanup(provider.stop)
        show = self.t.native.show_collection

        def non_nested(**kwargs):
            self.assertFalse(self.key.active, "native inside key consumer")
            return show(**kwargs)
        self.t.native.show_collection = non_nested

    def recover(self, original=False, **changes):
        values = dict(client_app_ref=self.app, task_route_ref=self.route, work_session_ref=self.session,
                      original_resume=original, reviewer_claim=None if original else "person:synthetic-recovery")
        values.update(changes)
        with exact.ExactOperationWriterLock(self.t.root) as held:
            return subject._recover_task_held(self.t.root, held=held, **values)

    def review(self, **changes):
        values = dict(client_app_ref=self.app, task_route_ref=self.route, work_session_ref=self.session)
        values.update(changes)
        with exact.ExactOperationWriterLock(self.t.root) as held:
            return subject._review_original_recovery_held(self.t.root, held=held, **values)

    def transition(self, action):
        with exact.ExactOperationWriterLock(self.t.root) as held:
            return state._transition_task_held(self.t.root, held=held, action=action, original_resume=False,
                client_app_ref=self.app, task_route_ref=self.route, work_session_ref=self.session)

    def reject(self, call, code=None, committed=False):
        with self.assertRaises(subject.WorkSessionRecoveryError) as caught:
            call()
        error = caught.exception
        if code is not None:
            self.assertEqual(error.code, code)
        self.assertEqual(error.original_commit_verified, committed)
        self.assertIsNone(error.__context__)
        self.assertIsNone(error.__cause__)
        for private in (str(self.t.root), self.app, self.route, "PRIVATE_FAILURE"):
            self.assertNotIn(private, repr(error))

    def cut_preclaim(self):
        original = actor.WorkSessionActorStore.save
        claims = self.t.claims()
        def save_then_cut(store, **kwargs):
            saved = original(store, **kwargs)
            if kwargs.get("pending_manifest_sha256") is not None:
                raise OSError("PRIVATE_FAILURE preclaim")
            return saved
        with patch.object(actor.WorkSessionActorStore, "save", new=save_then_cut):
            self.reject(self.recover)
        self.assertEqual(self.t.claims(), claims)
        selected = self.routing._read(current=False).document()
        return bundle.load_context_bound_session_decision(self.t.store,
            manifest_sha256=selected["pending_manifest_sha256"])

    def accepted(self):
        self.case.run_handoff()
        self.app, self.route = self.case.target, actor.new_task_route_ref()
        with exact.ExactOperationWriterLock(self.t.root) as held:
            result = lifecycle._establish_task_held(self.t.root, held=held, action="accept",
                client_app_ref=self.app, task_route_ref=self.route, predecessor_work_session_ref=self.session,
                reviewer_claim="person:synthetic-receiver")
            self.session = result["work_session_binding"]["work_session_ref"]
            claim._claim_task_held(self.t.root, held=held, client_app_ref=self.app,
                task_route_ref=self.route, work_session_ref=self.session)
        self.routing = actor.WorkSessionActorStore(self.t.store, client_app_ref=self.app, task_route_ref=self.route)

    def assert_journey(self, expected_origin):
        t = self.t
        old = self.routing.read().document()
        self.assertEqual(old["established_origin"]["action"], expected_origin)
        original_files = t.domain_files()
        native = t.native.calls
        result = self.recover()
        current = self.routing.read().document()
        self.assertNotEqual(current["claim_ref"], old["claim_ref"])
        self.assertEqual(current["work_session_ref"], old["work_session_ref"])
        self.assertEqual(current["established_origin"], old["established_origin"])
        self.assertTrue(result["current_claim_ownership_verified"])
        self.assertFalse(result["ownership_transferred"])
        for name, raw in original_files.items():
            self.assertEqual((t.root / name).read_bytes(), raw)
        before = t.domain_files()
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=AssertionError("completed writer")), \
             patch.object(actor.WorkSessionActorStore, "save", side_effect=AssertionError("completed actor")), \
             patch.object(t.native, "show_collection", side_effect=AssertionError("completed native")):
            replay = self.recover(True)
            reread = self.review()
        self.assertEqual(replay["receipt_sha256"], result["receipt_sha256"])
        self.assertFalse(reread["native_approval_redisplayed"])
        self.assertEqual(t.domain_files(), before)
        for action in ("pause", "resume", "complete"):
            self.assertEqual(self.transition(action)["state"], {"pause":"paused", "resume":"claimed", "complete":"completed"}[action])
            self.assertEqual(self.routing.read().document()["established_origin"], old["established_origin"])
        self.assertEqual(t.native.calls, native + 1)
        for private in (old["claim_ref"], current["claim_ref"], str(t.root), "person:synthetic-recovery", "Synthetic private"):
            self.assertNotIn(private, json.dumps([result, replay, reread]))

    def test_create_recovery_then_original_resume_and_pause_resume_complete(self):
        self.assert_journey("create")

    def test_accepted_successor_recovery_preserves_exact_accept_origin(self):
        self.accepted()
        self.assert_journey("accept")

    def test_stale_actor_claim_is_not_authority_but_new_human_recovery_can_replace_it(self):
        old = self.routing.read().document()
        with exact.ExactOperationWriterLock(self.t.root) as held:
            execution._execute_session_decision_held(self.t.root, held=held, action="recover",
                client_app_ref=self.app, task_route_ref=self.route, work_session_ref=self.session,
                reviewer_claim="person:synthetic-first-recovery")
            with self.assertRaises(actor_guard.WorkSessionTaskSelectionError):
                actor_guard._require_actor_selection_for_write_held(self.t.root, held=held,
                    client_app_ref=self.app, task_route_ref=self.route, work_session_ref=self.session)
        stale = self.routing._read(current=False)
        previous = self.t.store.read()._document["sessions"][self.session]["claim_ref"]
        self.assertEqual(stale.document(), old)
        result = self.recover()
        current = self.routing.read().document()
        self.assertNotIn(current["claim_ref"], (old["claim_ref"], previous))
        self.assertEqual(current["established_origin"], old["established_origin"])
        self.assertTrue(result["current_claim_ownership_verified"])
        self.assertEqual(self.t.native.calls, 3)

    def test_preclaim_cancel_then_explicit_review_reuses_original_context_and_refs(self):
        bound = self.cut_preclaim()
        before, claims = self.t.domain_files(), self.t.claims()
        self.reject(lambda: self.recover(True))
        self.reject(self.recover, "work_session_original_operation_pending")
        self.assertEqual(self.t.domain_files(), before)
        self.t.native.approve = False
        self.reject(self.review, "exact_human_approval_cancelled")
        self.assertEqual(self.t.domain_files(), before)
        self.assertEqual(self.t.claims(), claims)
        self.t.native.approve = True
        contexts, original = [], workflow._execute_exact_human_approved_write_core
        def observe(root, context, writer, **kwargs):
            contexts.append(context)
            return original(root, context, writer, **kwargs)
        with patch.object(workflow, "_execute_exact_human_approved_write_core", new=observe), \
             patch.object(registry, "_new_ref", side_effect=AssertionError("new refs")), \
             patch.object(bundle, "save_context_bound_session_decision", side_effect=AssertionError("rewritten bundle")):
            result = self.review()
        self.assertEqual(contexts, [bound.context])
        self.assertEqual(result["manifest_sha256"], bound.prepared.manifest.manifest_sha256)
        self.assertTrue(result["native_approval_redisplayed"])

    def test_started_claim_resumes_without_native_or_new_claim(self):
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=OSError("PRIVATE_FAILURE")):
            self.reject(self.recover)
        names = set(self.t.claims())
        with patch.object(self.t.native, "show_collection", side_effect=AssertionError("started native")):
            result = self.review()
        self.assertFalse(result["native_approval_redisplayed"])
        self.assertEqual(set(self.t.claims()), names)
        self.assertEqual(self.t.native.calls, 2)

    def test_completed_before_actor_publication_and_after_terminal_output_loss(self):
        with patch.object(subject, "_finish", side_effect=subject.WorkSessionRecoveryError(
                "work_session_task_context_changed", original_commit_verified=True)):
            self.reject(self.recover, committed=True)
        self.assertIsNotNone(self.routing._read(current=False).document()["pending_manifest_sha256"])
        original = actor.WorkSessionActorStore.save
        def saved_then_lost(store, **kwargs):
            saved = original(store, **kwargs)
            if kwargs.get("last_completed_operation") is not None:
                raise OSError("PRIVATE_FAILURE terminal")
            return saved
        with patch.object(actor.WorkSessionActorStore, "save", new=saved_then_lost):
            self.reject(lambda: self.recover(True), "work_session_task_context_changed", committed=True)
        before = self.t.domain_files()
        with patch.object(actor.WorkSessionActorStore, "save", side_effect=AssertionError("terminal duplicate")):
            self.assertTrue(self.recover(True)["original_operation_already_completed"])
        self.assertEqual(self.t.domain_files(), before)
        self.assertEqual(self.t.native.calls, 2)

    def test_later_state_keeps_original_commit_true_without_actor_or_registry_rewrite(self):
        self.recover()
        selected = self.routing.read().document()
        with exact.ExactOperationWriterLock(self.t.root) as held:
            planned = registry.plan_transition(self.t.store.read(), action="pause", client_app_ref=self.app,
                work_session_ref=self.session, claim_ref=selected["claim_ref"])
            self.t.store.commit(planned, held_lock=held)
        before = self.t.domain_files()
        with patch.object(self.t.native, "show_collection", side_effect=AssertionError("old success native")):
            for call in (lambda: self.recover(True), self.review):
                self.reject(call, "work_session_recovery_current_unavailable", committed=True)
        self.assertEqual(self.t.domain_files(), before)

    def test_wrong_route_session_action_origin_and_missing_lock_are_not_recovery(self):
        before = self.t.domain_files()
        for changes in ({"task_route_ref": actor.new_task_route_ref()}, {"client_app_ref": self.case.target},
                        {"work_session_ref": registry._new_ref("work_session")}, {"work_session_ref": None},
                        {"original_resume": 1}, {"reviewer_claim": None}):
            self.reject(lambda: self.recover(**changes))
        self.reject(lambda: self.recover(True))
        self.reject(self.review)
        with patch.object(self.key, "use_key", side_effect=OSError("PRIVATE_FAILURE missing MAC")):
            self.reject(self.recover)
        self.reject(lambda: subject._recover_task_held(self.t.root, held=None, client_app_ref=self.app,
            task_route_ref=self.route, work_session_ref=self.session, original_resume=False, reviewer_claim="person:synthetic"),
            "work_session_lock_required")
        self.assertEqual(self.t.domain_files(), before)
        self.assertEqual(self.t.native.calls, 1)
        for name in ("_recover_task_held", "_review_original_recovery_held"):
            parameters = inspect.signature(getattr(subject, name)).parameters
            self.assertFalse({"native", "key_provider", "claim_ref", "context", "approval_id", "target_app_ref"} & set(parameters))

    def test_cancel_and_whole_registry_drift_during_native_cannot_publish_claim(self):
        before = self.t.domain_files()
        self.t.native.approve = False
        self.reject(self.recover, "exact_human_approval_cancelled")
        self.assertEqual(self.t.domain_files(), before)
        self.t.native.approve = True
        names = self.t.claims()
        def changed_registry():
            plan = registry.plan_transition(self.t.store.read(), action="register-app", label="Synthetic concurrent generation")
            self.t.store.commit(plan, held_lock=held)
        with exact.ExactOperationWriterLock(self.t.root) as held:
            self.t.native.before_click = changed_registry
            self.reject(lambda: subject._recover_task_held(self.t.root, held=held, client_app_ref=self.app,
                task_route_ref=self.route, work_session_ref=self.session, original_resume=False,
                reviewer_claim="person:synthetic-recovery"))
        self.assertEqual(self.t.claims(), names)
        self.assertIsNone(self.routing.read().document()["pending_manifest_sha256"])

    def test_two_authenticated_original_claims_are_ambiguous_not_absent(self):
        bound = self.cut_preclaim()
        for _ in range(2):
            with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
                workflow._execute_exact_human_approved_write_core(self.t.root, bound.context,
                    lambda _claim: (_ for _ in ()).throw(OSError("Synthetic interrupted original")),
                    native=_Native(), key_provider=_Key())
        before = self.t.domain_files()
        self.reject(self.review, "exact_human_approval_resume_candidate_ambiguous")
        self.assertEqual(self.t.domain_files(), before)
        self.assertEqual(self.t.native.calls, 2)

    def test_actor_sha_drift_during_native_cannot_publish_recovery_claim(self):
        names = self.t.claims()
        registry_before = self.t.store.read()
        claim_before = registry_before._document["sessions"][self.session]["claim_ref"]
        def changed_actor():
            values = self.routing.read().document()
            values["pending_manifest_sha256"] = "sha256:" + "e" * 64
            values["pending_context_sha256"] = "sha256:" + "f" * 64
            basis = {key:value for key,value in values.items() if key != "actor_sha256"}
            changed = actor.ActorContext(registry._canonical({**basis,
                "actor_sha256":actor._sha(registry._canonical(basis))}))
            path = self.t.root.joinpath(*self.routing._parts, f"{values['revision']:012d}.json")
            path.write_bytes(changed._raw)
        self.t.native.before_click = changed_actor
        self.reject(self.recover)
        self.assertEqual(self.t.claims(), names)
        registry_after = self.t.store.read()
        self.assertEqual(registry_after.sha256, registry_before.sha256)
        self.assertEqual(registry_after._document["sessions"][self.session]["claim_ref"], claim_before)
        self.assertEqual(registry_after._document["sessions"][self.session]["state"], "claimed")

    def test_failed_and_corrupt_original_claim_never_open_native(self):
        bound = self.cut_preclaim()
        original_names = set(self.t.claims())
        def failed(claim):
            claim.finalize_failed("synthetic_recovery_failed")
            raise OSError("Synthetic failed")
        with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
            workflow._execute_exact_human_approved_write_core(self.t.root, bound.context, failed,
                native=_Native(), key_provider=_Key())
        name = (set(self.t.claims()) - original_names).pop()
        path = next(self.t.root.rglob(name))
        cases = (("authenticated_failed", path.read_bytes(), "exact_human_approval_resume_claim_invalid"),
                 # Malformed bytes cannot even be routed away from the original
                 # establishment MAC scan. Its existing fixed unavailable result
                 # must not be reclassified as an absent recovery approval.
                 ("malformed", b"PRIVATE_FAILURE invalid claim", "work_session_recovery_unavailable"))
        for phase, raw, code in cases:
            with self.subTest(phase=phase):
                path.write_bytes(raw)
                before = self.t.domain_files()
                self.reject(self.review, code)
                self.assertEqual(self.t.domain_files(), before)
        self.assertEqual(self.t.native.calls, 2)

    def test_actual_preclaim_exit_then_fresh_review_and_terminal_replay(self):
        child = r'''
import json, os, sys
from pathlib import Path
from unittest.mock import patch
from wom_kit import exact_human_approval_workflow as workflow
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_actor as actor
from wom_kit import work_session_recovery as recovery
from test_v0420_work_session_execution import SessionNative, _Key
root, app, route, session, mode = sys.argv[1:]
native, key = SessionNative(), _Key()
original = actor.WorkSessionActorStore.save
def cut(store, **kwargs):
    value = original(store, **kwargs)
    if kwargs.get('pending_manifest_sha256') is not None: os._exit(73)
    return value
with patch.object(workflow, '_production_key_provider', return_value=key), patch.object(windows, '_CtypesTaskDialogNative', return_value=native):
    with exact.ExactOperationWriterLock(Path(root)) as held:
        args = dict(held=held, client_app_ref=app, task_route_ref=route, work_session_ref=session)
        if mode == 'cut':
            with patch.object(actor.WorkSessionActorStore, 'save', new=cut):
                recovery._recover_task_held(Path(root), original_resume=False, reviewer_claim='person:synthetic-process', **args)
        elif mode == 'review':
            result = recovery._review_original_recovery_held(Path(root), **args)
            print(json.dumps({'ok':result['ok'], 'native_calls':native.calls, 'redisplayed':result['native_approval_redisplayed']}))
        else:
            result = recovery._recover_task_held(Path(root), original_resume=True, **args)
            print(json.dumps({'ok':result['ok'], 'native_calls':native.calls, 'completed':result['original_operation_already_completed']}))
'''
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join((str(Path(__file__).resolve().parents[1] / "src"), str(Path(__file__).resolve().parent)))
        base = [sys.executable, "-B", "-c", child, str(self.t.root), self.app, self.route, self.session]
        options = dict(env=env, text=True, capture_output=True, timeout=90, creationflags=noninteractive_creationflags())
        names = self.t.claims()
        cut = subprocess.run([*base, "cut"], **options)
        self.assertEqual(cut.returncode, 73, "synthetic preclaim exit missing")
        self.assertEqual(self.t.claims(), names)
        pointer = self.routing._read(current=False).document()
        original = self.t.root.joinpath(*bundle.PRIVATE_ROOT, pointer["pending_manifest_sha256"][7:] + ".json").read_bytes()
        reviewed = subprocess.run([*base, "review"], **options)
        self.assertEqual(reviewed.returncode, 0, "synthetic fresh review failed")
        self.assertEqual(json.loads(reviewed.stdout), {"ok":True, "native_calls":1, "redisplayed":True})
        before = self.t.domain_files()
        replayed = subprocess.run([*base, "resume"], **options)
        self.assertEqual(replayed.returncode, 0, "synthetic fresh terminal resume failed")
        self.assertEqual(json.loads(replayed.stdout), {"ok":True, "native_calls":0, "completed":True})
        self.assertEqual(self.t.domain_files(), before)
        self.assertEqual(self.t.root.joinpath(*bundle.PRIVATE_ROOT, pointer["pending_manifest_sha256"][7:] + ".json").read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
