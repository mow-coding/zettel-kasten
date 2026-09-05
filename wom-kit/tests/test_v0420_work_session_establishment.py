"""Typed origins are selectors; only the original completed MAC proves them."""

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as workflow
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_actor as actor
from wom_kit import work_session_bundle as bundle
from wom_kit import work_session_establishment as subject
from wom_kit import work_session_execution as execution
from wom_kit import work_session_operation as operation
from wom_kit import work_session_registry as registry
from wom_kit import work_session_registry_intent as intents
import test_v0420_work_session_execution as fixture


class EstablishmentSelectorTests(unittest.TestCase):
    def test_strict_typed_union_detaches_and_does_not_attest_authority(self):
        for action in ("create", "accept"):
            row = {"action": action, "manifest_sha256": "sha256:" + "1" * 64,
                   "context_sha256": "sha256:" + "2" * 64}
            selected = subject.EstablishmentSelector.from_document(row)
            row["action"] = "recover"
            detached = selected.document()
            detached["action"] = "handoff"
            self.assertEqual(selected.action, action)
            self.assertFalse(selected.public_summary()["human_approval_verified"])
            self.assertFalse(selected.public_summary()["current_claim_authority_evaluated"])
            self.assertNotIn(selected.manifest_sha256, repr(selected) + json.dumps(selected.public_summary()))
        legacy = {"manifest_sha256": "sha256:" + "1" * 64, "context_sha256": "sha256:" + "2" * 64}
        before = dict(legacy)
        selected = subject.EstablishmentSelector.from_original_create(legacy)
        self.assertEqual(selected.document(), {"action": "create", **legacy})
        self.assertEqual(legacy, before)

    def test_malformed_actions_types_and_mixed_shapes_are_fixed_errors(self):
        class PrivateString(str):
            pass

        class PrivateDict(dict):
            pass

        good = {"action": "create", "manifest_sha256": "sha256:" + "1" * 64,
                "context_sha256": "sha256:" + "2" * 64}
        bad = [None, [], PrivateDict(good), {**good, "reviewer": "PRIVATE_MARKER"}]
        for field in good:
            missing = dict(good)
            del missing[field]
            bad.append(missing)
            for value in (None, True, [], {}, 1, "PRIVATE_MARKER", PrivateString(good[field])):
                bad.append({**good, field: value})
        bad.extend({**good, "action": action} for action in ("handoff", "recover", "claim", "CREATE"))
        for row in bad:
            with self.subTest(kind=type(row).__name__):
                with self.assertRaises(subject.WorkSessionEstablishmentError) as caught:
                    subject.EstablishmentSelector.from_document(row)
                self.assertEqual(str(caught.exception), "work_session_establishment_invalid")
                self.assertIsNone(caught.exception.__context__)
                self.assertIsNone(caught.exception.__cause__)
        with self.assertRaises(subject.WorkSessionEstablishmentError):
            subject.EstablishmentSelector.from_original_create(good)


class OriginalEstablishmentTests(unittest.TestCase):
    def setUp(self):
        self.case = fixture.SessionExecutionTests("runTest")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.root, self.store = self.case.root, self.case.store
        self.app = self.case.app
        self.route = actor.new_task_route_ref()

    def files(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file() and path.name != ".writer.lock"}

    def decision(self, action="create", *, app=None, route=None, **changes):
        arguments = dict(action=action, client_app_ref=app or self.app,
                         task_route_ref=route or self.route,
                         reviewer_claim="person:synthetic-establishment",
                         native=self.case.native, key_provider=self.case.key)
        if action == "create":
            arguments["label"] = "Synthetic private establishment"
        arguments.update(changes)
        with exact.ExactOperationWriterLock(self.root) as held:
            result = execution._execute_session_decision_held(self.root, held=held, **arguments)
        binding = result["work_session_binding"]
        path = self.root.joinpath(*bundle.PRIVATE_ROOT)
        for candidate in path.glob("*.json"):
            bound = bundle.load_context_bound_session_decision(self.store, manifest_sha256="sha256:" + candidate.stem)
            if bound.prepared.manifest.work_session_binding.document() == binding:
                return self.selector(bound), binding["work_session_ref"], bound
        self.fail("exact original bundle missing")

    def selector(self, bound):
        return subject.EstablishmentSelector.from_document({
            "action": bound.prepared.transition.action,
            "manifest_sha256": bound.prepared.manifest.manifest_sha256,
            "context_sha256": approval.exact_human_approval_context_sha256(bound.context),
        })

    def verify(self, selected, session, **changes):
        arguments = dict(selector=selected, client_app_ref=self.app, task_route_ref=self.route,
                         work_session_ref=session, key_provider=self.case.key)
        arguments.update(changes)
        with exact.ExactOperationWriterLock(self.root) as held:
            return subject.verify_original_establishment_held(self.root, self.store, held=held, **arguments)

    def reject(self, call):
        with self.assertRaises(subject.WorkSessionEstablishmentError) as caught:
            call()
        self.assertIn(caught.exception.code, subject._ERRORS)
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)
        for private in (str(self.root), self.app, self.route, "PRIVATE_MARKER"):
            self.assertNotIn(private, repr(caught.exception))

    def commit_nonhuman(self, action, app, **changes):
        transition = registry.plan_transition(self.store.read(), action=action, client_app_ref=app, **changes)
        with exact.ExactOperationWriterLock(self.root) as held:
            self.store.commit(transition, held_lock=held)
        return transition

    def test_completed_create_and_legacy_normalization_preserve_all_original_bytes(self):
        selected, session, bound = self.decision()
        legacy = {key: selected.document()[key] for key in ("manifest_sha256", "context_sha256")}
        normalized = subject.EstablishmentSelector.from_original_create(legacy)
        self.commit_nonhuman("claim", self.app, work_session_ref=session)
        before = self.files()
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=AssertionError("completed wrote")):
            restored = self.verify(normalized, session)
        self.assertEqual(restored, bound)
        self.assertEqual(self.files(), before)
        self.assertEqual(self.case.native.calls, 1)
        self.assertNotEqual(self.store.read().binding(session), restored.prepared.manifest.work_session_binding)

    def test_accept_successor_uses_its_own_completed_approval_and_typed_claim_intent(self):
        created, predecessor, _created_bound = self.decision()
        original_claim = self.commit_nonhuman("claim", self.app, work_session_ref=predecessor)._generated_refs[0]
        second = self.commit_nonhuman("register-app", None, label="Synthetic receiving app").result_refs[0]
        # Handoff is a human operation, but not an establishment selector.
        with exact.ExactOperationWriterLock(self.root) as held:
            execution._execute_session_decision_held(self.root, held=held, action="handoff",
                client_app_ref=self.app, task_route_ref=self.route, work_session_ref=predecessor,
                claim_ref=original_claim, target_app_ref=second,
                reviewer_claim="person:synthetic-establishment", native=self.case.native, key_provider=self.case.key)
        successor_route = actor.new_task_route_ref()
        accepted, successor, bound = self.decision("accept", app=second, route=successor_route,
                                                  work_session_ref=predecessor)
        self.assertNotEqual(predecessor, successor)
        self.assertEqual(self.store.read()._document["sessions"][successor]["state"], "created")
        self.assertEqual(self.verify(accepted, successor, client_app_ref=second, task_route_ref=successor_route), bound)
        before = self.files()
        self.reject(lambda: self.verify(created, successor, client_app_ref=second, task_route_ref=successor_route))
        self.reject(lambda: self.verify(replace(accepted, action="create"), successor,
                                       client_app_ref=second, task_route_ref=successor_route))
        self.assertEqual(self.files(), before)
        claim = registry.plan_transition(self.store.read(), action="claim", client_app_ref=second,
                                         work_session_ref=successor)
        with exact.ExactOperationWriterLock(self.root) as held:
            with self.assertRaises(intents.WorkSessionRegistryIntentError):
                intents.prepare_registry_intent(self.store, claim, held_lock=held,
                    original_create_selector={"manifest_sha256": accepted.manifest_sha256,
                                              "context_sha256": accepted.context_sha256})
            intent = intents.prepare_registry_intent(self.store, claim, held_lock=held,
                                                     original_establishment_selector=accepted)
            intents.save_registry_intent(self.store, intent, held_lock=held)
            outcome = intents.observe_or_apply_registry_intent(self.store, plan_sha256=intent.plan_sha256, held_lock=held)
        self.assertEqual(outcome.transition, claim)
        self.assertEqual(intent.original_establishment_selector, accepted)
        self.assertIsNone(intent.original_create_selector)
        before = self.files()
        self.assertEqual(self.verify(accepted, successor, client_app_ref=second, task_route_ref=successor_route), bound)
        self.assertEqual(self.files(), before)
        self.assertEqual(self.case.native.calls, 3)

    def test_started_original_is_readable_but_never_completed_by_verification(self):
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=OSError("PRIVATE_MARKER")):
            with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
                self.decision()
        path = next(self.root.joinpath(*bundle.PRIVATE_ROOT).glob("*.json"))
        bound = bundle.load_context_bound_session_decision(self.store, manifest_sha256="sha256:" + path.stem)
        selected, session = self.selector(bound), bound.prepared.manifest.work_session_binding.work_session_ref
        self.assertEqual(subject.load_original_establishment(self.store, selector=selected,
            client_app_ref=self.app, task_route_ref=self.route, work_session_ref=session), bound)
        before = self.files()
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=AssertionError("started wrote")) as writer:
            self.reject(lambda: self.verify(selected, session))
        writer.assert_not_called()
        self.assertEqual(self.files(), before)
        self.assertEqual(self.case.native.calls, 1)

    def test_wrong_scope_and_foreign_or_missing_lock_fail_before_key_access(self):
        selected, session, _bound = self.decision()
        before = self.files()
        with patch.object(self.case.key, "use_key", side_effect=AssertionError("wrong scope accessed key")) as key:
            for changes in ({"client_app_ref": registry._new_ref("client_app")},
                            {"task_route_ref": actor.new_task_route_ref()},
                            {"work_session_ref": registry._new_ref("work_session")},
                            {"selector": replace(selected, context_sha256="sha256:" + "f" * 64)}):
                self.reject(lambda: self.verify(selected, session, **changes))
            arguments = dict(selector=selected, client_app_ref=self.app, task_route_ref=self.route,
                             work_session_ref=session, key_provider=self.case.key)
            self.reject(lambda: subject.verify_original_establishment_held(
                self.root, self.store, held=None, **arguments))
            with tempfile.TemporaryDirectory(prefix="wom-foreign-origin-") as directory:
                other = Path(directory)
                (other / "archive.yml").write_bytes((self.root / "archive.yml").read_bytes())
                with exact.ExactOperationWriterLock(self.root) as held:
                    self.reject(lambda: subject.verify_original_establishment_held(
                        other, self.store, held=held, **arguments))
        key.assert_not_called()
        self.assertEqual(self.files(), before)

    def test_post_verification_drift_and_changed_claim_mac_do_not_attest_establishment(self):
        selected, session, _bound = self.decision()
        path = self.root.joinpath(*bundle.PRIVATE_ROOT, selected.manifest_sha256[7:] + ".json")
        original_raw = path.read_bytes()
        original_resume = execution._resume_session_decision_held

        def drift(*args, **kwargs):
            result = original_resume(*args, **kwargs)
            self.assertTrue(kwargs["completed_only"])
            path.write_bytes(b"PRIVATE_MARKER")
            return result

        try:
            with patch.object(execution, "_resume_session_decision_held", new=drift):
                self.reject(lambda: self.verify(selected, session))
        finally:
            path.write_bytes(original_raw)
        claim_path = next(self.root.joinpath(*Path(approval.CLAIMS_RELATIVE_ROOT).parts).glob("*.json"))
        claim_raw = claim_path.read_bytes()
        changed = json.loads(claim_raw)
        changed["unexpected"] = "PRIVATE_MARKER"
        claim_path.write_text(json.dumps(changed), encoding="utf-8")
        before = self.files()
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=AssertionError("forged MAC wrote")):
            self.reject(lambda: self.verify(selected, session))
        self.assertEqual(self.files(), before)
        self.assertEqual(self.case.native.calls, 1)


if __name__ == "__main__":
    unittest.main()
