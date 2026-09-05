"""Human create to original claim intent, actor CAS and fresh ownership proof."""

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_v0420_work_session_lifecycle as fixture
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_actor as actor
from wom_kit import work_session_claim as subject
from wom_kit import work_session_registry as registry
from wom_kit import work_session_registry_intent as intents


class TaskClaimTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.TaskLifecycleTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.created = self.fixture.create()
        self.session = self.created["work_session_binding"]["work_session_ref"]

    def claim(self, **changes):
        t = self.fixture
        arguments = dict(client_app_ref=t.app, task_route_ref=t.route, work_session_ref=self.session, key_provider=t.key)
        arguments.update(changes)
        return subject._claim_task_core(t.root, **arguments)

    def reject(self, call, code=None, committed=False):
        with self.assertRaises(subject.WorkSessionClaimError) as caught:
            call()
        if code is not None:
            self.assertEqual(caught.exception.code, code)
        self.assertEqual(caught.exception.original_commit_verified, committed)
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)
        for private in (str(self.fixture.root), "Synthetic private", "private_error_marker"):
            self.assertNotIn(private, repr(caught.exception))

    def cut_before_claim_commit(self):
        original = registry.WorkSessionRegistryStore.commit

        def cut(store, plan, **kwargs):
            if plan.action == "claim":
                raise OSError("private_error_marker before original claim commit")
            return original(store, plan, **kwargs)

        with patch.object(registry.WorkSessionRegistryStore, "commit", new=cut):
            self.reject(self.claim)
        selected = self.fixture.routing.read().document()
        self.assertIsNotNone(selected["pending_registry_intent_plan_sha256"])
        self.assertEqual(self.fixture.store.read()._document["sessions"][self.session]["state"], "created")
        return selected

    def test_actual_claim_then_completed_readonly_resume_has_same_original_claim_and_receipt(self):
        t = self.fixture
        original_human_receipts = t.claims()
        result = self.claim()
        selected = t.routing.read().document()
        original_claim = selected["claim_ref"]
        self.assertTrue(result["ok"] and result["original_commit_verified"] and result["current_claim_ownership_verified"])
        self.assertIs(result["current_claim_authority_evaluated"], True)
        self.assertIs(result["human_approval_granted"], False)
        self.assertIsNone(selected["pending_registry_intent_plan_sha256"])
        self.assertEqual(selected["last_completed_operation"]["kind"], "registry_transition")
        self.assertEqual(t.store.read().revision, 3)
        self.assertEqual(t.claims(), original_human_receipts)
        self.assertEqual(t.native.calls, 1)
        before = t.domain_files()
        with patch.object(registry.WorkSessionRegistryStore, "commit", side_effect=AssertionError("completed wrote")), \
                patch.object(intents, "observe_or_apply_registry_intent", side_effect=AssertionError("completed executed intent")):
            resumed = self.claim()
        self.assertTrue(resumed["original_operation_already_completed"])
        self.assertEqual(resumed["intent_sha256"], result["intent_sha256"])
        self.assertEqual(t.routing.read().document()["claim_ref"], original_claim)
        self.assertEqual(t.domain_files(), before)
        for private in (original_claim, str(t.root), "Synthetic private"):
            self.assertNotIn(private, json.dumps(result) + json.dumps(resumed))

    def test_pending_original_resumes_without_new_reference_or_plan(self):
        t = self.fixture
        selected = self.cut_before_claim_commit()
        pending_plan = selected["pending_registry_intent_plan_sha256"]
        with exact.ExactOperationWriterLock(t.root) as held:
            original = intents.load_registry_intent(t.store, plan_sha256=pending_plan, held_lock=held)
        claim_ref = intents._strict_document(original._raw)["generated_refs"][0]
        with patch.object(intents, "prepare_registry_intent", side_effect=AssertionError("replanned pending claim")), \
                patch.object(intents, "save_registry_intent", side_effect=AssertionError("replaced pending intent")):
            result = self.claim()
        self.assertTrue(result["ok"])
        self.assertEqual(result["plan_sha256"], pending_plan)
        self.assertEqual(t.routing.read().document()["claim_ref"], claim_ref)
        self.assertEqual(t.native.calls, 1)

    def test_completed_pointer_to_pending_intent_is_readonly_refusal_not_claim_authority(self):
        t = self.fixture
        pending = self.cut_before_claim_commit()
        selected = t.routing.read()
        with exact.ExactOperationWriterLock(t.root) as held:
            t.routing.save(expected_sha256=selected.sha256, held_lock=held, work_session_ref=self.session,
                           observed_binding=t.store.read().binding(self.session),
                           pending_registry_intent_plan_sha256=None,
                           last_completed_operation=actor.CompletedOperationSelector.from_document({
                               "kind": "registry_transition", "plan_sha256": pending["pending_registry_intent_plan_sha256"],
                           }))
        before = t.domain_files()
        with patch.object(registry.WorkSessionRegistryStore, "commit", side_effect=AssertionError("forged completed wrote")) as writer:
            self.reject(self.claim, "work_session_original_operation_changed")
        writer.assert_not_called()
        self.assertEqual(t.domain_files(), before)

    def test_readonly_committed_intent_refuses_pending_then_observes_actual_same_commit(self):
        t = self.fixture
        pending = self.cut_before_claim_commit()
        plan = pending["pending_registry_intent_plan_sha256"]
        before = t.domain_files()
        with exact.ExactOperationWriterLock(t.root) as held:
            with patch.object(registry.WorkSessionRegistryStore, "commit", side_effect=AssertionError("read-only wrote")) as writer:
                with self.assertRaises(intents.WorkSessionRegistryIntentError):
                    intents.observe_committed_registry_intent(t.store, plan_sha256=plan, held_lock=held)
                writer.assert_not_called()
        self.assertEqual(t.domain_files(), before)
        result = self.claim()
        before = t.domain_files()
        with exact.ExactOperationWriterLock(t.root) as held:
            with patch.object(registry.WorkSessionRegistryStore, "commit", side_effect=AssertionError("read-only committed")):
                observed = intents.observe_committed_registry_intent(t.store, plan_sha256=plan, held_lock=held)
        self.assertEqual(observed.status, "already_committed")
        self.assertEqual(observed.intent.public_summary()["intent_sha256"], result["intent_sha256"])
        self.assertEqual(t.domain_files(), before)

    def test_original_success_after_pause_is_not_current_ownership(self):
        t = self.fixture
        result = self.claim()
        selected = t.routing.read().document()
        pause = registry.plan_transition(t.store.read(), action="pause", client_app_ref=t.app,
                                          work_session_ref=self.session, claim_ref=selected["claim_ref"])
        with exact.ExactOperationWriterLock(t.root) as held:
            t.store.commit(pause, held_lock=held)
        before = t.domain_files()
        with patch.object(registry.WorkSessionRegistryStore, "commit", side_effect=AssertionError("old claim reacquired")):
            self.reject(self.claim, "work_session_claim_ownership_unavailable", committed=True)
        self.assertEqual(t.domain_files(), before)
        with exact.ExactOperationWriterLock(t.root) as held:
            old = intents.observe_committed_registry_intent(t.store, plan_sha256=result["plan_sha256"], held_lock=held)
        self.assertEqual(old.status, "already_committed")

    def test_own_route_explicit_session_and_other_app_mismatch_are_zero_effects(self):
        t = self.fixture
        before = t.domain_files()
        for changes in ({"work_session_ref": None}, {"work_session_ref": registry._new_ref("work_session")},
                        {"task_route_ref": actor.new_task_route_ref()}, {"client_app_ref": registry._new_ref("client_app")}):
            with self.subTest(keys=tuple(changes)):
                self.reject(lambda changes=changes: self.claim(**changes))
        self.assertEqual(t.domain_files(), before)

    def test_failed_human_origin_cannot_claim(self):
        t = self.fixture
        before = t.domain_files()
        with patch.object(t.key, "use_key", side_effect=OSError("private_error_marker")), \
                patch.object(intents, "save_registry_intent", side_effect=AssertionError("unverified create saved intent")), \
                patch.object(registry.WorkSessionRegistryStore, "commit", side_effect=AssertionError("unverified create claimed")):
            self.reject(self.claim)
        self.assertEqual(t.domain_files(), before)

    def test_completed_claim_copied_to_blank_same_app_route_is_not_original_route(self):
        t = self.fixture
        result = self.claim()
        old = t.routing.read().document()
        route = actor.new_task_route_ref()
        other = actor.WorkSessionActorStore(t.store, client_app_ref=t.app, task_route_ref=route)
        with exact.ExactOperationWriterLock(t.root) as held:
            other.save(expected_sha256=None, held_lock=held, work_session_ref=self.session,
                       observed_binding=t.store.read().binding(self.session), claim_ref=old["claim_ref"],
                       last_completed_operation=actor.CompletedOperationSelector.from_document(old["last_completed_operation"]))
        before = t.domain_files()
        with patch.object(registry.WorkSessionRegistryStore, "commit", side_effect=AssertionError("copied route wrote")) as writer:
            self.reject(lambda: self.claim(task_route_ref=route), "work_session_original_operation_changed")
        writer.assert_not_called()
        self.assertEqual(t.domain_files(), before)
        self.assertEqual(self.claim()["intent_sha256"], result["intent_sha256"])

    def test_origin_selector_missing_or_tampered_cannot_upgrade_old_claim(self):
        t = self.fixture
        result = self.claim()
        path = t.root.joinpath(*intents.PRIVATE_ROOT) / (result["plan_sha256"][7:] + ".json")
        original = path.read_bytes()
        row = json.loads(original)
        origin = row["original_create_selector"]
        variants = [None, {**origin, "context_sha256": "sha256:" + "a" * 64},
                    {**origin, "manifest_sha256": "sha256:" + "a" * 64},
                    {**origin, "private_extra": "private_error_marker"}]
        for variant in ["missing", *variants]:
            with self.subTest(kind="missing" if variant == "missing" else type(variant).__name__):
                changed = json.loads(original)
                if variant == "missing":
                    del changed["original_create_selector"]
                else:
                    changed["original_create_selector"] = variant
                changed["intent_sha256"] = intents._sha(intents._canonical({k: v for k, v in changed.items() if k != "intent_sha256"}))
                path.write_bytes(intents._canonical(changed))
                before = t.domain_files()
                try:
                    with patch.object(registry.WorkSessionRegistryStore, "commit", side_effect=AssertionError("tampered origin wrote")) as writer:
                        self.reject(self.claim)
                    writer.assert_not_called()
                    self.assertEqual(t.domain_files(), before)
                finally:
                    path.write_bytes(original)
        self.assertTrue(self.claim()["current_claim_ownership_verified"])

    def test_old_none_intent_bytes_and_low_level_observation_are_not_rebound(self):
        t = self.fixture
        transition = registry.plan_transition(t.store.read(), action="claim", client_app_ref=t.app, work_session_ref=self.session)
        with exact.ExactOperationWriterLock(t.root) as held:
            original = intents.prepare_registry_intent(t.store, transition, held_lock=held)
            explicit_none = intents.prepare_registry_intent(t.store, transition, held_lock=held, original_create_selector=None)
            basis = {"schema": intents.INTENT_SCHEMA, "archive_identity_sha256": t.store.archive_identity_sha256,
                     "before_revision": transition.after.revision - 1, "before_sha256": transition.before_sha256,
                     "request": transition._request, "generated_refs": list(transition._generated_refs),
                     "after_sha256": transition.after.sha256, "plan_sha256": transition.plan_sha256}
            expected = intents._canonical({**basis, "intent_sha256": intents._sha(intents._canonical(basis))})
            self.assertEqual(original._raw, expected)
            self.assertEqual(original._raw, explicit_none._raw)
            self.assertIsNone(original.original_create_selector)
            intents.save_registry_intent(t.store, original, held_lock=held)
            outcome = intents.observe_or_apply_registry_intent(t.store, plan_sha256=original.plan_sha256, held_lock=held)
            old = t.routing._read(current=False)
            t.routing.save(expected_sha256=old.sha256, held_lock=held, work_session_ref=self.session,
                           observed_binding=outcome.transition.after.binding(self.session), claim_ref=transition._generated_refs[0],
                           last_completed_operation=actor.CompletedOperationSelector.from_document({
                               "kind": "registry_transition", "plan_sha256": original.plan_sha256,
                           }))
        before = t.domain_files()
        self.reject(self.claim, "work_session_original_operation_changed")
        self.assertEqual(t.domain_files(), before)
        with exact.ExactOperationWriterLock(t.root) as held:
            observed = intents.observe_committed_registry_intent(t.store, plan_sha256=original.plan_sha256, held_lock=held)
        self.assertEqual(observed.intent._raw, expected)

    def test_cancellation_before_lock_and_missing_held_lock_do_not_mutate(self):
        t = self.fixture
        before = t.domain_files()
        self.reject(lambda: self.claim(cancel_requested=lambda: True), "work_session_claim_cancelled")
        self.reject(lambda: subject._claim_task_held(t.root, held=None, client_app_ref=t.app,
                                                    task_route_ref=t.route, work_session_ref=self.session, key_provider=t.key),
                    "work_session_lock_required")
        self.assertEqual(t.domain_files(), before)

    def test_output_loss_before_terminal_actor_cas_resumes_original_commit(self):
        t = self.fixture
        original = actor.WorkSessionActorStore.save

        def cut(store, **kwargs):
            completed = kwargs.get("last_completed_operation")
            if completed is not None and completed.document()["kind"] == "registry_transition":
                raise OSError("private_error_marker before terminal actor CAS")
            return original(store, **kwargs)

        with patch.object(actor.WorkSessionActorStore, "save", new=cut):
            self.reject(self.claim)
        document = t.routing.read().document()
        self.assertIsNotNone(document["pending_registry_intent_plan_sha256"])
        original_claim = t.store.read()._document["sessions"][self.session]["claim_ref"]
        with patch.object(registry.WorkSessionRegistryStore, "commit", side_effect=AssertionError("original commit repeated")):
            result = self.claim()
        self.assertTrue(result["ok"])
        self.assertEqual(t.routing.read().document()["claim_ref"], original_claim)
        self.assertEqual(t.store.read().revision, 3)

    def test_real_child_exit_matrix_uses_original_pending_or_terminal_claim(self):
        child = r'''
import json, os, sys
from pathlib import Path
from wom_kit import work_session_claim as subject, work_session_actor as actor
from wom_kit import work_session_registry as registry, work_session_registry_intent as intents
from test_v0420_work_session_operation import _Key
root, app, route, session, mode = sys.argv[1:]
if mode == 'after_intent':
    original = intents.save_registry_intent
    def save(*args, **kwargs):
        value = original(*args, **kwargs)
        os._exit(71)
    intents.save_registry_intent = save
elif mode in {'after_pending', 'after_actor_completed'}:
    original = actor.WorkSessionActorStore.save
    def save(*args, **kwargs):
        value = original(*args, **kwargs)
        if mode == 'after_pending' and kwargs.get('pending_registry_intent_plan_sha256') is not None:
            os._exit(72)
        completed = kwargs.get('last_completed_operation')
        if mode == 'after_actor_completed' and completed is not None and completed.document()['kind'] == 'registry_transition':
            os._exit(74)
        return value
    actor.WorkSessionActorStore.save = save
elif mode == 'after_commit':
    original = registry.WorkSessionRegistryStore.commit
    def commit(store, plan, **kwargs):
        value = original(store, plan, **kwargs)
        if plan.action == 'claim':
            os._exit(73)
        return value
    registry.WorkSessionRegistryStore.commit = commit
result = subject._claim_task_core(Path(root), client_app_ref=app, task_route_ref=route,
                                 work_session_ref=session, key_provider=_Key())
print(json.dumps(result, sort_keys=True))
'''
        environment = dict(os.environ)
        kit = Path(__file__).resolve().parents[1]
        environment["PYTHONPATH"] = os.pathsep.join((str(kit / "src"), str(kit / "tests")))
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        for mode, code in (("after_intent", 71), ("after_pending", 72), ("after_commit", 73), ("after_actor_completed", 74)):
            with self.subTest(stage=mode):
                t = fixture.TaskLifecycleTests("runTest")
                t.setUp()
                try:
                    created = t.create()
                    session = created["work_session_binding"]["work_session_ref"]
                    command = [sys.executable, "-B", "-c", child, str(t.root), t.app, t.route, session]
                    cut = subprocess.run([*command, mode], env=environment, capture_output=True, text=True,
                                         encoding="utf-8", timeout=90, **options)
                    self.assertEqual((cut.returncode, cut.stdout, cut.stderr), (code, "", ""))
                    before = t.routing.read().document()
                    stored_claim = t.store.read()._document["sessions"][session]["claim_ref"]
                    if mode == "after_intent":
                        self.assertIsNone(before["pending_registry_intent_plan_sha256"])
                        self.assertIsNone(stored_claim)
                        self.assertEqual(before["last_completed_operation"]["kind"], "human_session_decision")
                    else:
                        plan = (before["pending_registry_intent_plan_sha256"] or before["last_completed_operation"]["plan_sha256"])
                        with exact.ExactOperationWriterLock(t.root) as held:
                            original_intent = intents.load_registry_intent(t.store, plan_sha256=plan, held_lock=held)
                        original_claim = intents._strict_document(original_intent._raw)["generated_refs"][0]
                    if mode in {"after_intent", "after_pending"}:
                        self.assertIsNone(stored_claim)
                        self.assertEqual(t.store.read().revision, 2)
                    else:
                        self.assertEqual(stored_claim, original_claim)
                    resumed = subprocess.run([*command, "resume"], env=environment, capture_output=True, text=True,
                                             encoding="utf-8", timeout=90, **options)
                    self.assertEqual((resumed.returncode, resumed.stderr), (0, ""))
                    result = json.loads(resumed.stdout)
                    self.assertTrue(result["ok"] and result["current_claim_ownership_verified"])
                    current = t.routing.read().document()
                    if mode != "after_intent":
                        self.assertEqual(current["claim_ref"], original_claim)
                        self.assertEqual(result["plan_sha256"], plan)
                    else:
                        self.assertEqual(len(list(t.root.joinpath(*intents.PRIVATE_ROOT).glob("*.json"))), 2)
                    self.assertEqual(t.store.read().revision, 3)
                    self.assertIsNone(current["pending_registry_intent_plan_sha256"])
                    self.assertNotIn(current["claim_ref"], resumed.stdout)
                    self.assertEqual(len(t.claims()), 1)
                finally:
                    t.doCleanups()


if __name__ == "__main__":
    unittest.main()
