"""Actual create/accept MACs drive claim/state; legacy intent bytes survive."""

import json
import unittest
from unittest.mock import patch

from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as workflow
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_actor as actor
from wom_kit import work_session_bundle as bundle
from wom_kit import work_session_claim as claim
from wom_kit import work_session_establishment as establishment
from wom_kit import work_session_execution as execution
from wom_kit import work_session_lifecycle as lifecycle
from wom_kit import work_session_registry as registry
from wom_kit import work_session_registry_intent as intents
from wom_kit import work_session_state as state
import test_v0420_work_session_establishment as fixture


class EstablishedClaimStateTests(unittest.TestCase):
    def setUp(self):
        self.t = fixture.OriginalEstablishmentTests("runTest")
        self.t.setUp()
        self.addCleanup(self.t.doCleanups)
        self.root, self.store = self.t.root, self.t.store
        key_patch = patch.object(workflow, "_production_key_provider", return_value=self.t.case.key)
        key_patch.start()
        self.addCleanup(key_patch.stop)

    def accepted(self):
        created, predecessor, _bound = self.t.decision()
        old_claim = self.t.commit_nonhuman("claim", self.t.app, work_session_ref=predecessor)._generated_refs[0]
        self.app = self.t.commit_nonhuman("register-app", None, label="Synthetic receiving app").result_refs[0]
        with exact.ExactOperationWriterLock(self.root) as held:
            execution._execute_session_decision_held(self.root, held=held, action="handoff",
                client_app_ref=self.t.app, task_route_ref=self.t.route, work_session_ref=predecessor,
                claim_ref=old_claim, target_app_ref=self.app, reviewer_claim="person:synthetic-establishment",
                native=self.t.case.native, key_provider=self.t.case.key)
        self.route = actor.new_task_route_ref()
        with exact.ExactOperationWriterLock(self.root) as held:
            result = lifecycle._establish_task_held(self.root, held=held, action="accept",
                client_app_ref=self.app, task_route_ref=self.route, predecessor_work_session_ref=predecessor,
                reviewer_claim="person:synthetic-establishment", native=self.t.case.native, key_provider=self.t.case.key)
        self.session = result["work_session_binding"]["work_session_ref"]
        self.routing = actor.WorkSessionActorStore(self.store, client_app_ref=self.app, task_route_ref=self.route)
        self.origin = establishment.EstablishmentSelector.from_document(self.routing.read().document()["established_origin"])
        return created

    def run_claim(self):
        return claim._claim_task_core(self.root, client_app_ref=self.app, task_route_ref=self.route,
                                     work_session_ref=self.session, key_provider=self.t.case.key)

    def run_state(self, action, original=False):
        with exact.ExactOperationWriterLock(self.root) as held:
            return state._transition_task_held(self.root, held=held, action=action, original_resume=original,
                client_app_ref=self.app, task_route_ref=self.route, work_session_ref=self.session)

    def reject(self, call, cls=claim.WorkSessionClaimError):
        with self.assertRaises(cls) as caught:
            call()
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)
        for private in (str(self.root), self.app, self.route, "Synthetic", "PRIVATE_FAILURE"):
            self.assertNotIn(private, repr(caught.exception))

    def test_accepted_successor_claim_pause_resume_complete_preserves_original_accept(self):
        self.accepted()
        self.assertEqual(self.origin.action, "accept")
        receipts = self.t.case.claims()
        claimed = self.run_claim()
        for action in ("pause", "resume", "complete"):
            result = self.run_state(action)
            self.assertEqual(result["state"], {"pause": "paused", "resume": "claimed", "complete": "completed"}[action])
            self.assertEqual(self.routing.read().document()["established_origin"], self.origin.document())
            with exact.ExactOperationWriterLock(self.root) as held:
                saved = intents.load_registry_intent(self.store, plan_sha256=result["plan_sha256"], held_lock=held)
            self.assertEqual(saved.original_establishment_selector, self.origin)
            self.assertIsNone(saved.original_create_selector)
        self.assertTrue(claimed["current_claim_ownership_verified"])
        self.assertEqual(self.t.case.claims(), receipts)
        self.assertEqual(self.t.case.native.calls, 3)

    def test_accepted_pending_claim_and_state_use_original_commit_without_new_prepare(self):
        self.accepted()
        original = registry.WorkSessionRegistryStore.commit
        def cut(store, plan, **kwargs):
            result = original(store, plan, **kwargs)
            if plan.action in {"claim", "pause"}:
                raise OSError("PRIVATE_FAILURE after actual registry commit")
            return result
        for action in ("claim", "pause"):
            with self.subTest(action=action):
                with patch.object(registry.WorkSessionRegistryStore, "commit", new=cut):
                    self.reject(self.run_claim if action == "claim" else lambda: self.run_state("pause"),
                                claim.WorkSessionClaimError if action == "claim" else state.WorkSessionStateError)
                pending = self.routing.read().document()["pending_registry_intent_plan_sha256"]
                path = self.root.joinpath(*intents.PRIVATE_ROOT, pending[7:] + ".json")
                raw = path.read_bytes()
                with patch.object(intents, "prepare_registry_intent", side_effect=AssertionError("new intent")), \
                     patch.object(registry.WorkSessionRegistryStore, "commit", side_effect=AssertionError("duplicate commit")):
                    result = self.run_claim() if action == "claim" else self.run_state("pause", True)
                self.assertEqual(result["plan_sha256"], pending)
                self.assertEqual(path.read_bytes(), raw)
                self.assertEqual(self.routing.read().document()["established_origin"], self.origin.document())
        self.assertEqual(self.t.case.native.calls, 3)

    def test_false_accept_action_context_or_original_actor_binding_cannot_claim(self):
        created = self.accepted()
        original = self.routing.read()
        path = self.root.joinpath(*self.routing._parts, f"{original.document()['revision']:012d}.json")
        # At the first establishment CAS the predecessor has no origin. These
        # schema-valid private pointer faults must still fail real MAC/source
        # verification, not be accepted as actor authority.
        for fault in ("action", "context", "predecessor", "observed_binding"):
            with self.subTest(fault=fault):
                changed = original.document()
                if fault == "action":
                    changed["established_origin"]["action"] = "create"
                elif fault == "context":
                    changed["established_origin"]["context_sha256"] = "sha256:" + "f" * 64
                elif fault == "predecessor":
                    changed["established_origin"] = created.document()
                else:
                    changed["observed_binding"]["revision"] += 1
                    from wom_kit.work_session_binding import WorkSessionBinding
                    prior = changed["observed_binding"]
                    changed["observed_binding"] = WorkSessionBinding.build(**{
                        key: value for key, value in prior.items() if key not in {"schema", "binding_sha256"}
                    }).document()
                basis = {key: value for key, value in changed.items() if key != "actor_sha256"}
                path.write_bytes(registry._canonical({**basis, "actor_sha256": actor._sha(registry._canonical(basis))}))
                before = self.t.files()
                self.reject(self.run_claim)
                self.assertEqual(self.t.files(), before)
        path.write_bytes(original._raw)

    def test_immutable_origin_survives_real_recovery_last_operation_for_later_state(self):
        self.accepted()
        self.run_claim()
        selected = self.routing.read()
        with exact.ExactOperationWriterLock(self.root) as held:
            result = execution._execute_session_decision_held(self.root, held=held, action="recover",
                client_app_ref=self.app, task_route_ref=self.route, work_session_ref=self.session,
                reviewer_claim="person:synthetic-establishment", native=self.t.case.native, key_provider=self.t.case.key)
            bound = bundle.load_context_bound_session_decision(self.store, manifest_sha256=result["manifest_sha256"])
            current = self.store.read()
            self.routing.save(expected_sha256=selected.sha256, held_lock=held, work_session_ref=self.session,
                observed_binding=current.binding(self.session), claim_ref=current._document["sessions"][self.session]["claim_ref"],
                last_completed_operation=actor.CompletedOperationSelector.from_document({
                    "kind": "human_session_decision", "manifest_sha256": result["manifest_sha256"],
                    "context_sha256": approval.exact_human_approval_context_sha256(bound.context),
                }))
        self.assertEqual(self.run_state("pause")["state"], "paused")
        self.assertEqual(self.routing.read().document()["established_origin"], self.origin.document())
        self.assertEqual(self.t.case.native.calls, 4)

    def test_legacy_create_claim_and_pause_intents_resume_without_rewriting_old_bytes(self):
        self.origin, self.session, bound = self.t.decision()
        self.app, self.route = self.t.app, self.t.route
        self.routing = actor.WorkSessionActorStore(self.store, client_app_ref=self.app, task_route_ref=self.route)
        pair = {key: self.origin.document()[key] for key in ("manifest_sha256", "context_sha256")}
        with exact.ExactOperationWriterLock(self.root) as held:
            self.routing.save(expected_sha256=None, held_lock=held, work_session_ref=self.session,
                observed_binding=bound.prepared.manifest.work_session_binding,
                last_completed_operation=actor.CompletedOperationSelector.from_document({"kind": "human_session_decision", **pair}))
        receipts = self.t.case.claims()
        for action in ("claim", "pause"):
            selected = self.routing.read()
            document = selected.document()
            with exact.ExactOperationWriterLock(self.root) as held:
                planned = registry.plan_transition(self.store.read(), action=action, client_app_ref=self.app,
                    work_session_ref=self.session, claim_ref=document["claim_ref"] if action == "pause" else None)
                old = intents.prepare_registry_intent(self.store, planned, held_lock=held, original_create_selector=pair)
                intents.save_registry_intent(self.store, old, held_lock=held)
                self.routing.save(expected_sha256=selected.sha256, held_lock=held, work_session_ref=self.session,
                    observed_binding=self.store.read().binding(self.session), claim_ref=document["claim_ref"],
                    pending_registry_intent_plan_sha256=old.plan_sha256)
            self.assertIn("original_create_selector", json.loads(old._raw))
            self.assertNotIn("original_establishment_selector", json.loads(old._raw))
            with patch.object(intents, "prepare_registry_intent", side_effect=AssertionError("legacy rewritten")), \
                 patch.object(intents, "save_registry_intent", side_effect=AssertionError("legacy saved again")):
                result = self.run_claim() if action == "claim" else self.run_state("pause", True)
            self.assertEqual(result["plan_sha256"], old.plan_sha256)
            self.assertEqual(self.root.joinpath(*intents.PRIVATE_ROOT, old.plan_sha256[7:] + ".json").read_bytes(), old._raw)
            self.assertNotIn("established_origin", self.routing.read().document())
        self.assertEqual(self.t.case.claims(), receipts)
        with exact.ExactOperationWriterLock(self.root) as held:
            self.assertIsNone(claim._verify_original_create(self.root, self.store, self.routing,
                self.routing._read(current=False), held=held, client_app_ref=self.app, task_route_ref=self.route,
                work_session_ref=self.session, key_provider=self.t.case.key, original_create_selector=pair))

    def test_actor_cas_change_during_real_key_verification_cannot_claim(self):
        self.origin, self.session, bound = self.t.decision()
        self.app, self.route = self.t.app, self.t.route
        self.routing = actor.WorkSessionActorStore(self.store, client_app_ref=self.app, task_route_ref=self.route)
        original_key = self.t.case.key.use_key
        injected = {}
        before_registry = self.store.read().sha256
        with exact.ExactOperationWriterLock(self.root) as held:
            self.routing.save(expected_sha256=None, held_lock=held, work_session_ref=self.session,
                observed_binding=bound.prepared.manifest.work_session_binding, established_origin=self.origin)
            def key(*args, **kwargs):
                result = original_key(*args, **kwargs)
                if not injected:
                    old = self.routing.read()
                    changed = self.routing.save(expected_sha256=old.sha256, held_lock=held,
                        work_session_ref=self.session, observed_binding=self.store.read().binding(self.session),
                        pending_registry_intent_plan_sha256="sha256:" + "f" * 64)
                    injected["sha"] = changed.sha256
                return result
            with patch.object(self.t.case.key, "use_key", new=key):
                self.reject(lambda: claim._claim_task_held(self.root, held=held, client_app_ref=self.app,
                    task_route_ref=self.route, work_session_ref=self.session, key_provider=self.t.case.key))
        self.assertEqual(self.store.read().sha256, before_registry)
        self.assertEqual(self.routing.read().sha256, injected["sha"])


if __name__ == "__main__":
    unittest.main()
