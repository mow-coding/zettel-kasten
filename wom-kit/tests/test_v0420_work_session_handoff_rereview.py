"""One shared native protocol for exact preclaim handoff recovery."""

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
from wom_kit import work_session_bundle as bundle
from wom_kit import work_session_execution as execution
from wom_kit import work_session_handoff as subject
from wom_kit import work_session_operation as operation
from wom_kit import work_session_registry as registry
from wom_kit.work_session_binding import WorkSessionBinding
from wom_kit.process_launch import noninteractive_creationflags
import test_v0420_work_session_handoff as fixture
from test_v0420_work_session_rereview import GuardedKey
from test_v0420_work_session_operation import _Native, _Key


class HandoffRereviewTests(unittest.TestCase):
    def setUp(self):
        self.case = fixture.HandoffTests("runTest")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.task = self.case.task
        self.key = GuardedKey(self.task.key)
        self.task.key = self.key
        provider = patch.object(workflow, "_production_key_provider", return_value=self.key)
        provider.start()
        self.addCleanup(provider.stop)
        show = self.task.native.show_collection

        def outside_consumer(**kwargs):
            self.assertFalse(self.key.active, "native inside key consumer")
            return show(**kwargs)

        self.task.native.show_collection = outside_consumer

    def cut(self):
        original = actor.WorkSessionActorStore.save
        claims = self.task.claims()

        def save_then_cut(store, **kwargs):
            result = original(store, **kwargs)
            if kwargs.get("pending_manifest_sha256") is not None:
                raise OSError("PRIVATE_FAILURE preclaim")
            return result

        with patch.object(actor.WorkSessionActorStore, "save", new=save_then_cut):
            self.case.reject(self.case.run_handoff)
        self.assertEqual(self.task.claims(), claims)
        selected = self.task.routing._read(current=False).document()
        self.assertIsNotNone(selected["pending_manifest_sha256"])
        bound = bundle.load_context_bound_session_decision(self.task.store,
            manifest_sha256=selected["pending_manifest_sha256"])
        return selected, bound

    def review(self, **changes):
        t = self.task
        values = dict(client_app_ref=t.app, task_route_ref=t.route,
                      work_session_ref=self.case.session, target_app_ref=self.case.target)
        values.update(changes)
        with exact.ExactOperationWriterLock(t.root) as held:
            return subject._review_original_handoff_held(t.root, held=held, **values)

    def test_original_context_targets_reviewer_and_origin_are_unchanged_without_nested_key(self):
        t = self.task
        selected, bound = self.cut()
        path = t.root.joinpath(*bundle.PRIVATE_ROOT, selected["pending_manifest_sha256"][7:] + ".json")
        raw = path.read_bytes()
        contexts = []
        original = workflow._execute_exact_human_approved_write_core

        def observe(root, context, writer, **kwargs):
            contexts.append(context)
            return original(root, context, writer, **kwargs)

        with patch.object(workflow, "_execute_exact_human_approved_write_core", new=observe), \
             patch.object(registry, "_new_ref", side_effect=AssertionError("new reference")), \
             patch.object(bundle, "save_context_bound_session_decision", side_effect=AssertionError("rewrote original")):
            result = self.review()
        self.assertEqual(contexts, [bound.context])
        self.assertEqual(result["work_session_binding"], bound.prepared.manifest.work_session_binding.document())
        self.assertTrue(result["native_approval_redisplayed"])
        self.assertEqual(t.native.calls, 3)
        self.assertEqual(path.read_bytes(), raw)
        self.assertEqual(t.routing.read().document()["established_origin"], selected["established_origin"])
        self.assertEqual(result["target_app_ref"], self.case.target)
        self.assertEqual(self.key.requests[-3:], [False, False, True])
        self.assertFalse(result["ownership_transferred"])
        for private in (str(t.root), selected["claim_ref"], "Synthetic private", bound.context.reviewer_claim):
            self.assertNotIn(private, json.dumps(result))

    def test_cancel_preserves_pending_and_has_no_write_key_or_new_claim(self):
        t = self.task
        self.cut()
        before, claims, index = t.domain_files(), t.claims(), len(self.key.requests)
        t.native.approve = False
        self.case.reject(self.review, "exact_human_approval_cancelled")
        self.assertEqual(t.domain_files(), before)
        self.assertEqual(t.claims(), claims)
        self.assertNotIn(True, self.key.requests[index:])

    def test_existing_started_and_completed_claims_use_only_original_resume(self):
        t = self.task
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=OSError("PRIVATE_FAILURE")):
            self.case.reject(self.case.run_handoff)
        original_claims = set(t.claims())
        with patch.object(t.native, "show_collection", side_effect=AssertionError("existing approval re-reviewed")):
            result = self.review()
        self.assertFalse(result["native_approval_redisplayed"])
        before = t.domain_files()
        with patch.object(t.native, "show_collection", side_effect=AssertionError("completed re-reviewed")), \
             patch.object(operation, "apply_session_decision_with_claim", side_effect=AssertionError("completed wrote")), \
             patch.object(actor.WorkSessionActorStore, "save", side_effect=AssertionError("completed actor wrote")):
            replay = self.review()
        self.assertFalse(replay["native_approval_redisplayed"])
        self.assertTrue(replay["original_operation_already_completed"])
        self.assertEqual(replay["receipt_sha256"], result["receipt_sha256"])
        self.assertEqual(set(t.claims()), original_claims)
        self.assertEqual(t.domain_files(), before)

    def test_claim_appearing_during_native_cannot_trigger_a_second_write_key(self):
        t = self.task
        _selected, bound = self.cut()
        count = len(t.claims())

        def appeared():
            with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
                workflow._execute_exact_human_approved_write_core(t.root, bound.context,
                    lambda _claim: (_ for _ in ()).throw(OSError("Synthetic interrupted original")),
                    native=_Native(), key_provider=_Key())

        t.native.before_click = appeared
        index = len(self.key.requests)
        self.case.reject(self.review, "work_session_original_operation_changed")
        self.assertNotIn(True, self.key.requests[index:])
        self.assertEqual(len(t.claims()), count + 1)
        self.assertEqual(t.store.read()._document["sessions"][self.case.session]["state"], "claimed")

    def test_failed_corrupt_and_ambiguous_claims_are_never_treated_as_absence(self):
        t = self.task
        _selected, bound = self.cut()
        baseline = t.claims()

        def failed(claim):
            claim.finalize_failed("synthetic_handoff_failed")
            raise OSError("Synthetic authenticated failure")

        with exact.ExactOperationWriterLock(t.root):
            with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
                workflow._execute_exact_human_approved_write_core(t.root, bound.context, failed,
                                                                 native=_Native(), key_provider=_Key())
        new_names = set(t.claims()) - set(baseline)
        self.assertEqual(len(new_names), 1)
        claim_name = next(iter(new_names))
        claim_path = next(path for path in t.root.rglob(claim_name) if path.is_file())
        failed_raw = claim_path.read_bytes()
        for raw in (failed_raw, b"PRIVATE_FAILURE invalid claim"):
            claim_path.write_bytes(raw)
            before = t.domain_files()
            with patch.object(t.native, "show_collection", side_effect=AssertionError("invalid claim re-reviewed")):
                self.case.reject(self.review)
            self.assertEqual(t.domain_files(), before)
        claim_path.write_bytes(failed_raw)
        # Two authenticated records, including failed, must still be refused;
        # never delete the first record to manufacture an absent candidate.
        with exact.ExactOperationWriterLock(t.root):
            with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
                workflow._execute_exact_human_approved_write_core(t.root, bound.context,
                    lambda _claim: (_ for _ in ()).throw(OSError("Synthetic second original")),
                    native=_Native(), key_provider=_Key())
        before = t.domain_files()
        with patch.object(t.native, "show_collection", side_effect=AssertionError("ambiguous re-reviewed")):
            self.case.reject(self.review)
        self.assertEqual(t.domain_files(), before)

    def test_wrong_route_target_session_and_missing_lock_never_reopen_native(self):
        t = self.task
        self.cut()
        before = t.domain_files()
        with patch.object(t.native, "show_collection", side_effect=AssertionError("wrong context native")):
            for changes in ({"task_route_ref": actor.new_task_route_ref()},
                            {"work_session_ref": registry._new_ref("work_session")},
                            {"target_app_ref": t.app}, {"target_app_ref": None}):
                self.case.reject(lambda: self.review(**changes))
            self.case.reject(lambda: subject._review_original_handoff_held(t.root, held=None,
                client_app_ref=t.app, task_route_ref=t.route, work_session_ref=self.case.session,
                target_app_ref=self.case.target))
        self.assertEqual(t.domain_files(), before)
        parameters = inspect.signature(subject._review_original_handoff_held).parameters
        for forbidden in ("native", "key_provider", "claim_ref", "reviewer_claim", "context", "resume_original"):
            self.assertNotIn(forbidden, parameters)

    def test_actor_drift_in_publication_key_preserves_pending_without_nested_discovery(self):
        t = self.task
        selected, _bound = self.cut()
        claims = t.claims()
        with exact.ExactOperationWriterLock(t.root) as held:
            def drift():
                t.routing.save(expected_sha256=t.routing._read(current=False).sha256, held_lock=held,
                    work_session_ref=self.case.session, observed_binding=WorkSessionBinding.from_document(selected["observed_binding"]),
                    claim_ref=selected["claim_ref"], pending_manifest_sha256=selected["pending_manifest_sha256"],
                    pending_context_sha256="sha256:" + "f" * 64)
            self.key.before_create = drift
            self.case.reject(lambda: subject._review_original_handoff_held(t.root, held=held,
                client_app_ref=t.app, task_route_ref=t.route, work_session_ref=self.case.session,
                target_app_ref=self.case.target), "work_session_original_operation_changed")
        self.assertEqual(t.claims(), claims)
        self.assertEqual(t.store.read()._document["sessions"][self.case.session]["state"], "claimed")

    def test_later_accepted_state_keeps_original_commit_evidence_without_rewriting_actor(self):
        t = self.task
        self.case.run_handoff()
        with exact.ExactOperationWriterLock(t.root) as held:
            execution._execute_session_decision_held(t.root, held=held, action="accept", client_app_ref=self.case.target,
                task_route_ref=actor.new_task_route_ref(), work_session_ref=self.case.session,
                reviewer_claim="person:synthetic-receiver", native=t.native, key_provider=self.key)
        before = t.domain_files()
        with patch.object(t.native, "show_collection", side_effect=AssertionError("old success re-approved")):
            self.case.reject(self.review, "work_session_handoff_current_unavailable", committed=True)
        self.assertEqual(t.domain_files(), before)

    def test_actual_preclaim_process_cut_then_fresh_original_native_rereview(self):
        t = self.task
        child = r'''
import json, os, sys
from pathlib import Path
from unittest.mock import patch
from wom_kit import exact_human_approval_workflow as workflow
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_actor as actor
from wom_kit import work_session_bundle as bundle
from wom_kit import work_session_handoff as handoff
from test_v0420_work_session_execution import SessionNative, _Key
root, app, route, session, target, mode = sys.argv[1:]
native, key = SessionNative(), _Key()
original = actor.WorkSessionActorStore.save
def cut(store, **kwargs):
    result = original(store, **kwargs)
    if kwargs.get('pending_manifest_sha256') is not None: os._exit(73)
    return result
with patch.object(workflow, '_production_key_provider', return_value=key), patch.object(windows, '_CtypesTaskDialogNative', return_value=native):
    with exact.ExactOperationWriterLock(Path(root)) as held:
        args = dict(held=held, client_app_ref=app, task_route_ref=route, work_session_ref=session, target_app_ref=target)
        if mode == 'cut':
            with patch.object(actor.WorkSessionActorStore, 'save', new=cut):
                handoff._handoff_task_held(Path(root), original_resume=False, reviewer_claim='person:synthetic-process-reviewer', **args)
        else:
            with patch.object(bundle, 'save_context_bound_session_decision', side_effect=AssertionError('original rewritten')):
                result = handoff._review_original_handoff_held(Path(root), **args)
            print(json.dumps({'ok':result['ok'],'native_calls':native.calls,'redisplayed':result['native_approval_redisplayed']}))
'''
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join((str(Path(__file__).resolve().parents[1] / "src"),
                                            str(Path(__file__).resolve().parent)))
        base = [sys.executable, "-B", "-c", child, str(t.root), t.app, t.route, self.case.session, self.case.target]
        options = dict(env=env, text=True, capture_output=True, timeout=90, creationflags=noninteractive_creationflags())
        claims = t.claims()
        cut = subprocess.run([*base, "cut"], **options)
        self.assertEqual(cut.returncode, 73, "synthetic preclaim cut missing")
        self.assertEqual(t.claims(), claims)
        selected = t.routing._read(current=False).document()
        path = t.root.joinpath(*bundle.PRIVATE_ROOT, selected["pending_manifest_sha256"][7:] + ".json")
        raw = path.read_bytes()
        reviewed = subprocess.run([*base, "review"], **options)
        self.assertEqual(reviewed.returncode, 0, "synthetic original review failed")
        self.assertEqual(json.loads(reviewed.stdout), {"ok": True, "native_calls": 1, "redisplayed": True})
        self.assertEqual(path.read_bytes(), raw)
        self.assertEqual(t.routing.read().document()["last_completed_operation"]["manifest_sha256"],
                         selected["pending_manifest_sha256"])


if __name__ == "__main__":
    unittest.main()
