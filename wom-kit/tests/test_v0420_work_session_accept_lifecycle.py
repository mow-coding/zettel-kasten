"""Accepted successor starts use real original approval and a new actor route."""

import json
import unittest
from unittest.mock import patch

from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_actor as actor
from wom_kit import work_session_claim as claim
from wom_kit import work_session_execution as execution
from wom_kit import work_session_lifecycle as subject
from wom_kit import work_session_operation as operation
from wom_kit import work_session_registry as registry
import test_v0420_work_session_execution as fixture


class AcceptLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.case = fixture.SessionExecutionTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.root, self.store = self.case.root, self.case.store
        self.app, self.route = self.case.app, actor.new_task_route_ref()
        self.create_route = actor.new_task_route_ref()
        created = subject._create_task_core(self.root, client_app_ref=self.app, task_route_ref=self.create_route,
            label="Synthetic origin task", reviewer_claim="person:synthetic-reviewer",
            native=self.case.native, key_provider=self.case.key)
        self.predecessor = created["work_session_binding"]["work_session_ref"]
        with exact.ExactOperationWriterLock(self.root) as held:
            claim._claim_task_held(self.root, held=held, client_app_ref=self.app,
                task_route_ref=self.create_route, work_session_ref=self.predecessor, key_provider=self.case.key)
            registration = registry.plan_transition(self.store.read(), action="register-app", label="Synthetic receiving app")
            self.store.commit(registration, held_lock=held)
            self.receiving = registration.result_refs[0]
            execution._execute_session_decision_held(self.root, held=held, action="handoff",
                client_app_ref=self.app, task_route_ref=self.create_route, work_session_ref=self.predecessor,
                claim_ref=self.store.read()._document["sessions"][self.predecessor]["claim_ref"],
                target_app_ref=self.receiving, reviewer_claim="person:synthetic-reviewer",
                native=self.case.native, key_provider=self.case.key)
        self.routing = actor.WorkSessionActorStore(self.store, client_app_ref=self.receiving, task_route_ref=self.route)

    def files(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file() and path.name != ".writer.lock"}

    def accept(self, **changes):
        arguments = dict(action="accept", client_app_ref=self.receiving, task_route_ref=self.route,
            predecessor_work_session_ref=self.predecessor, reviewer_claim="person:synthetic-reviewer",
            native=self.case.native, key_provider=self.case.key)
        arguments.update(changes)
        with exact.ExactOperationWriterLock(self.root) as held:
            return subject._establish_task_held(self.root, held=held, **arguments)

    def resume(self, **changes):
        arguments = dict(action="accept", client_app_ref=self.receiving, task_route_ref=self.route,
                         key_provider=self.case.key)
        arguments.update(changes)
        with exact.ExactOperationWriterLock(self.root) as held:
            return subject._resume_task_establishment_held(self.root, held=held, **arguments)

    def reject(self, call):
        with self.assertRaises(subject.WorkSessionLifecycleError) as caught:
            call()
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)
        for private in (str(self.root), self.app, self.route, "Synthetic"):
            self.assertNotIn(private, repr(caught.exception))

    def test_accept_establishes_successor_not_claim_and_completed_replay_changes_no_bytes(self):
        result = self.accept()
        selected = self.routing.read().document()
        successor = result["work_session_binding"]["work_session_ref"]
        self.assertNotEqual(successor, self.predecessor)
        self.assertTrue(result["claim_required"])
        self.assertIsNone(selected["claim_ref"])
        self.assertEqual(selected["established_origin"]["action"], "accept")
        self.assertEqual(selected["established_origin"]["manifest_sha256"],
                         selected["last_completed_operation"]["manifest_sha256"])
        sessions = self.store.read()._document["sessions"]
        self.assertEqual(sessions[successor]["predecessor_ref"], self.predecessor)
        self.assertEqual(sessions[successor]["workstream_ref"], sessions[self.predecessor]["workstream_ref"])
        self.assertEqual(sessions[self.predecessor]["state"], "handed_off")
        self.assertEqual(self.case.native.calls, 3)
        before = self.files()
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=AssertionError("completed reentered")):
            resumed = self.resume()
        self.assertTrue(resumed["original_task_operation_already_completed"])
        self.assertEqual(resumed["receipt_sha256"], result["receipt_sha256"])
        self.assertEqual(self.files(), before)
        self.reject(lambda: self.resume(action="create"))
        self.reject(self.accept)
        self.assertEqual(self.files(), before)
        for marker in ("Synthetic", str(self.root)):
            self.assertNotIn(marker, json.dumps(result) + json.dumps(resumed))

    def test_started_accept_resumes_same_approval_without_new_successor_or_input(self):
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=OSError("Synthetic cut")):
            self.reject(self.accept)
        pending = self.routing.read().document()
        self.assertIsNotNone(pending["pending_manifest_sha256"])
        self.assertNotIn("established_origin", pending)
        claims = set(self.case.claims())
        before = self.files()
        self.reject(lambda: self.resume(action="create"))
        self.assertEqual(self.files(), before)
        result = self.resume()
        self.assertTrue(result["independent_post_verification"])
        self.assertEqual(set(self.case.claims()), claims)
        self.assertEqual(self.case.native.calls, 3)
        self.assertEqual(len(self.store.read()._document["sessions"]), 2)
        self.assertEqual(self.routing.read().document()["established_origin"]["action"], "accept")

    def test_loss_before_actor_terminal_save_resumes_original_completed_receipt(self):
        original = actor.WorkSessionActorStore.save

        def cut(store, **arguments):
            if arguments.get("established_origin") is not None:
                raise OSError("Synthetic terminal publication cut")
            return original(store, **arguments)

        with patch.object(actor.WorkSessionActorStore, "save", new=cut):
            self.reject(self.accept)
        claims = self.case.claims()
        generation = self.store.read().sha256
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=AssertionError("completed republished")):
            result = self.resume()
        self.assertTrue(result["ok"])
        self.assertEqual(self.store.read().sha256, generation)
        self.assertEqual(self.case.claims(), claims)
        self.assertEqual(self.case.native.calls, 3)
        self.assertIsNone(self.routing.read().document()["pending_manifest_sha256"])

    def test_cancel_wrong_app_and_copied_other_route_do_not_accept(self):
        before = self.files()
        self.reject(lambda: self.accept(client_app_ref=self.app))
        self.assertEqual(self.files(), before)
        self.case.native.approve = False
        self.reject(self.accept)
        self.assertEqual(self.files(), before)
        self.case.native.approve = True
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=OSError("Synthetic cut")):
            self.reject(self.accept)
        pending = self.routing.read().document()
        other_route = actor.new_task_route_ref()
        other = actor.WorkSessionActorStore(self.store, client_app_ref=self.receiving, task_route_ref=other_route)
        with exact.ExactOperationWriterLock(self.root) as held:
            other.save(expected_sha256=None, held_lock=held,
                pending_manifest_sha256=pending["pending_manifest_sha256"],
                pending_context_sha256=pending["pending_context_sha256"])
        before = self.files()
        self.reject(lambda: self.resume(task_route_ref=other_route))
        self.assertEqual(self.files(), before)
        self.assertTrue(self.resume()["ok"])


class LegacyCreateLifecycleTests(unittest.TestCase):
    def test_completed_legacy_create_is_not_migrated_when_read_only_resumed(self):
        case = fixture.SessionExecutionTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        route = actor.new_task_route_ref()
        original_save = actor.WorkSessionActorStore.save

        def legacy_save(store, **arguments):
            # Produce the historical shape at its initial publication, not by
            # deleting a pointer from an existing authenticated actor history.
            arguments.pop("established_origin", None)
            return original_save(store, **arguments)

        with patch.object(actor.WorkSessionActorStore, "save", new=legacy_save):
            original = subject._create_task_core(case.root, client_app_ref=case.app, task_route_ref=route,
                label="Synthetic legacy task", reviewer_claim="person:synthetic-reviewer",
                native=case.native, key_provider=case.key)
        routing = actor.WorkSessionActorStore(case.store, client_app_ref=case.app, task_route_ref=route)
        selected = routing.read()
        self.assertNotIn("established_origin", selected.document())
        before = {path.relative_to(case.root).as_posix(): path.read_bytes()
                  for path in case.root.rglob("*") if path.is_file() and path.name != ".writer.lock"}
        result = subject._resume_task_create_core(case.root, client_app_ref=case.app,
            task_route_ref=route, key_provider=case.key)
        self.assertEqual(result["receipt_sha256"], original["receipt_sha256"])
        self.assertEqual(routing.read().sha256, selected.sha256)
        self.assertEqual({path.relative_to(case.root).as_posix(): path.read_bytes()
                          for path in case.root.rglob("*") if path.is_file() and path.name != ".writer.lock"}, before)


if __name__ == "__main__":
    unittest.main()
