"""Real task-scoped create/continuation; fake native input and synthetic key only."""

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_actor as actor
from wom_kit import work_session_lifecycle as subject
from wom_kit import work_session_operation as operation
import test_v0420_work_session_execution as fixture


class TaskLifecycleTests(unittest.TestCase):
    claims = fixture.SessionExecutionTests.claims

    def setUp(self):
        fixture.SessionExecutionTests.setUp(self)
        self.route = actor.new_task_route_ref()
        self.routing = actor.WorkSessionActorStore(self.store, client_app_ref=self.app, task_route_ref=self.route)

    def create(self, **changes):
        arguments = dict(client_app_ref=self.app, task_route_ref=self.route,
                         label="Synthetic private task", reviewer_claim="person:synthetic-task-reviewer",
                         native=self.native, key_provider=self.key)
        arguments.update(changes)
        return subject._create_task_core(self.root, **arguments)

    def resume(self, **changes):
        arguments = dict(client_app_ref=self.app, task_route_ref=self.route, key_provider=self.key)
        arguments.update(changes)
        return subject._resume_task_create_core(self.root, **arguments)

    def domain_files(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file() and path.name != ".writer.lock"}

    def reject(self, call, code=None):
        with self.assertRaises(subject.WorkSessionLifecycleError) as caught:
            call()
        if code is not None:
            self.assertEqual(caught.exception.code, code)
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)
        for private in (str(self.root), self.app, self.route, "Synthetic private"):
            self.assertNotIn(private, repr(caught.exception))

    def cut_before_writer(self):
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=OSError("private simulated loss")):
            self.reject(self.create)
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.store.read().revision, 1)
        self.assertIsNotNone(self.routing.read().document()["pending_manifest_sha256"])

    def test_create_publishes_one_completed_route_and_original_resume_is_read_only(self):
        result = self.create()
        selected = self.routing.read().document()
        self.assertTrue(result["ok"])
        self.assertTrue(result["claim_required"])
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.store.read().revision, 2)
        self.assertEqual(selected["work_session_ref"], result["work_session_binding"]["work_session_ref"])
        self.assertIsNone(selected["claim_ref"])
        self.assertIsNone(selected["pending_manifest_sha256"])
        self.assertEqual(selected["last_completed_operation"]["kind"], "human_session_decision")
        before = self.domain_files()
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=AssertionError("completed cannot write")):
            resumed = self.resume()
        self.assertTrue(resumed["original_task_operation_already_completed"])
        self.assertEqual(resumed["receipt_sha256"], result["receipt_sha256"])
        self.assertEqual(self.domain_files(), before)
        self.assertEqual(self.native.calls, 1)
        for marker in ("Synthetic private", str(self.root)):
            self.assertNotIn(marker, json.dumps(result) + json.dumps(resumed))

    def test_cancel_does_not_save_actor_bundle_claim_or_create_another_session(self):
        before = self.domain_files()
        self.native.approve = False
        self.reject(self.create, "exact_human_approval_cancelled")
        self.assertIsNone(self.routing.read())
        self.assertEqual(self.domain_files(), before)

    def test_started_original_operation_resumes_without_manifest_or_reviewer_input(self):
        self.cut_before_writer()
        old_claim_names = set(self.claims())
        resumed = self.resume()
        self.assertTrue(resumed["ok"])
        self.assertTrue(resumed["independent_post_verification"])
        self.assertEqual(self.store.read().revision, 2)
        self.assertEqual(set(self.claims()), old_claim_names)
        self.assertEqual(self.native.calls, 1)
        self.assertIsNone(self.routing.read().document()["pending_manifest_sha256"])

    def test_loss_before_terminal_actor_save_recovers_same_completed_receipt(self):
        original_save = actor.WorkSessionActorStore.save

        def lose_terminal(store, **kwargs):
            if kwargs.get("last_completed_operation") is not None:
                raise OSError("private output loss before routing acknowledgement")
            return original_save(store, **kwargs)

        with patch.object(actor.WorkSessionActorStore, "save", new=lose_terminal):
            self.reject(self.create)
        old_claims = self.claims()
        self.assertEqual(self.store.read().revision, 2)
        self.assertIsNotNone(self.routing.read().document()["pending_manifest_sha256"])
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=AssertionError("already completed")):
            result = self.resume()
        self.assertTrue(result["ok"])
        self.assertEqual(self.claims(), old_claims)
        self.assertEqual(self.store.read().revision, 2)
        self.assertIsNone(self.routing.read().document()["pending_manifest_sha256"])

    def test_completed_selector_cannot_upgrade_started_claim_into_completion_or_execution(self):
        self.cut_before_writer()
        pending = self.routing.read()
        document = pending.document()
        forged = actor.CompletedOperationSelector.from_document({
            "kind": "human_session_decision", "manifest_sha256": document["pending_manifest_sha256"],
            "context_sha256": document["pending_context_sha256"],
        })
        with exact.ExactOperationWriterLock(self.root) as held:
            self.routing.save(expected_sha256=pending.sha256, held_lock=held,
                              last_completed_operation=forged)
        before = self.domain_files()
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=AssertionError("forged completed selector")):
            self.reject(self.resume)
        self.assertEqual(self.domain_files(), before)

    def test_explicit_task_routes_do_not_default_or_replace_an_existing_selection(self):
        result = self.create()
        before = self.domain_files()
        self.reject(self.create, "work_session_task_already_selected")
        self.reject(lambda: self.create(task_route_ref=None), "work_session_task_context_required")
        self.reject(lambda: self.resume(task_route_ref=actor.new_task_route_ref()),
                    "work_session_original_operation_missing")
        self.assertEqual(self.domain_files(), before)
        other_route = actor.new_task_route_ref()
        other = self.create(task_route_ref=other_route)
        self.assertNotEqual(other["work_session_binding"]["work_session_ref"], result["work_session_binding"]["work_session_ref"])
        self.assertEqual(self.resume()["receipt_sha256"], result["receipt_sha256"])

    def test_actor_change_during_native_decision_prevents_claim_and_writer(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            self.native.before_click = lambda: self.routing.save(expected_sha256=None, held_lock=held)
            self.reject(lambda: subject._create_task_held(
                self.root, held=held, client_app_ref=self.app, task_route_ref=self.route,
                label="Synthetic private task", reviewer_claim="person:synthetic-task-reviewer",
                native=self.native, key_provider=self.key,
            ))
        self.assertEqual(self.store.read().revision, 1)
        self.assertEqual(self.claims(), {})
        self.assertEqual(self.routing.read().document()["revision"], 1)
        self.assertIsNone(self.routing.read().document()["pending_manifest_sha256"])
        self.assertEqual(self.native.calls, 1)

    def test_original_pending_approval_cannot_be_copied_to_blank_other_task_route(self):
        self.cut_before_writer()
        original = self.routing.read().document()
        other_route = actor.new_task_route_ref()
        other = actor.WorkSessionActorStore(self.store, client_app_ref=self.app, task_route_ref=other_route)
        with exact.ExactOperationWriterLock(self.root) as held:
            other.save(expected_sha256=None, held_lock=held,
                pending_manifest_sha256=original["pending_manifest_sha256"],
                pending_context_sha256=original["pending_context_sha256"])
        before = self.domain_files()
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=AssertionError("other task route")):
            self.reject(lambda: self.resume(task_route_ref=other_route),
                        "work_session_original_operation_changed")
        self.assertEqual(self.domain_files(), before)
        self.assertTrue(self.resume()["ok"])

    def test_pending_registry_transition_never_falls_back_to_older_completed_create(self):
        self.create()
        selected = self.routing.read()
        document = selected.document()
        from wom_kit.work_session_binding import WorkSessionBinding
        with exact.ExactOperationWriterLock(self.root) as held:
            self.routing.save(expected_sha256=selected.sha256, held_lock=held,
                work_session_ref=document["work_session_ref"],
                observed_binding=WorkSessionBinding.from_document(document["observed_binding"]),
                pending_registry_intent_plan_sha256="sha256:" + "a" * 64)
        before = self.domain_files()
        self.reject(self.resume, "work_session_original_operation_pending")
        self.assertEqual(self.domain_files(), before)

    def test_real_child_exit_after_final_actor_save_then_new_process_read_only_resume(self):
        child = r'''
import json, os, sys
from pathlib import Path
from wom_kit import work_session_actor as actor, work_session_lifecycle as subject
from test_v0420_work_session_execution import SessionNative
from test_v0420_work_session_operation import _Key
root, app, route, mode = sys.argv[1:]
if mode == 'cut':
    original = actor.WorkSessionActorStore.save
    def save(store, **kwargs):
        result = original(store, **kwargs)
        if kwargs.get('last_completed_operation') is not None:
            os._exit(73)
        return result
    actor.WorkSessionActorStore.save = save
    subject._create_task_core(Path(root), client_app_ref=app, task_route_ref=route,
        label='Synthetic private task', reviewer_claim='person:synthetic-task-reviewer',
        native=SessionNative(), key_provider=_Key())
else:
    result = subject._resume_task_create_core(Path(root), client_app_ref=app, task_route_ref=route, key_provider=_Key())
    print(json.dumps({'ok': result['ok'], 'already_completed': result['original_task_operation_already_completed'],
                      'receipt_sha256': result['receipt_sha256']}))
'''
        environment = dict(os.environ)
        kit = Path(__file__).resolve().parents[1]
        environment["PYTHONPATH"] = os.pathsep.join((str(kit / "src"), str(kit / "tests")))
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        command = [sys.executable, "-B", "-c", child, str(self.root), self.app, self.route]
        cut = subprocess.run([*command, "cut"], env=environment, capture_output=True, text=True,
                             encoding="utf-8", timeout=90, **options)
        self.assertEqual((cut.returncode, cut.stdout, cut.stderr), (73, "", ""))
        before = self.domain_files()
        resumed = subprocess.run([*command, "resume"], env=environment, capture_output=True, text=True,
                                 encoding="utf-8", timeout=90, **options)
        self.assertEqual((resumed.returncode, resumed.stderr), (0, ""))
        result = json.loads(resumed.stdout)
        self.assertTrue(result["ok"] and result["already_completed"])
        self.assertEqual(self.domain_files(), before)
        self.assertEqual(self.store.read().revision, 2)
        self.assertEqual(len(self.claims()), 1)


if __name__ == "__main__":
    unittest.main()
