"""Re-review a real preclaim cut; never replace stored approval or old refs."""

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_v0420_work_session_lifecycle as fixture
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as workflow
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_actor as actor
from wom_kit import work_session_bundle as bundle
from wom_kit import work_session_operation as operation
from wom_kit import work_session_registry as registry
from wom_kit import work_session_rereview as subject


class GuardedKey:
    def __init__(self, delegate):
        self.delegate, self.active, self.requests, self.before_create = delegate, False, [], None

    def use_key(self, root, consumer, *, create_if_missing=False):
        if self.active:
            raise AssertionError("nested key consumer")
        self.active = True
        self.requests.append(create_if_missing)
        try:
            if create_if_missing and self.before_create is not None:
                self.before_create()
            return self.delegate.use_key(root, consumer, create_if_missing=create_if_missing)
        finally:
            self.active = False


class OriginalRereviewTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.TaskLifecycleTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.key = GuardedKey(self.fixture.key)
        self.fixture.key = self.key
        show = self.fixture.native.show_collection

        def outside_key(**kwargs):
            self.assertFalse(self.key.active)
            return show(**kwargs)

        self.fixture.native.show_collection = outside_key

    def cut_before_claim(self):
        t = self.fixture
        original = actor.WorkSessionActorStore.save

        def cut(store, **kwargs):
            result = original(store, **kwargs)
            if kwargs.get("pending_manifest_sha256") is not None:
                raise OSError("Synthetic output loss before claim publication")
            return result

        with patch.object(actor.WorkSessionActorStore, "save", new=cut):
            t.reject(t.create)
        self.assertEqual(t.store.read().revision, 1)
        self.assertEqual(t.claims(), {})
        self.assertIsNotNone(t.routing.read().document()["pending_manifest_sha256"])
        return t.routing.read().document()

    def review(self, **changes):
        t = self.fixture
        arguments = dict(client_app_ref=t.app, task_route_ref=t.route, native=t.native, key_provider=self.key)
        arguments.update(changes)
        with exact.ExactOperationWriterLock(t.root) as held:
            return subject._review_original_session_decision_held(t.root, held=held, **arguments)

    def reject(self, call, code=None):
        with self.assertRaises(subject.WorkSessionRereviewError) as caught:
            call()
        if code is not None:
            self.assertEqual(caught.exception.code, code)
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)
        for private in (str(self.fixture.root), "Synthetic private", "private_error_marker"):
            self.assertNotIn(private, repr(caught.exception))

    def test_preclaim_cut_rereviews_once_with_original_context_refs_and_no_nested_broker(self):
        t = self.fixture
        selected = self.cut_before_claim()
        plan = t.root.joinpath(*bundle.PRIVATE_ROOT) / (selected["pending_manifest_sha256"][7:] + ".json")
        original_raw = plan.read_bytes()
        original = bundle.load_context_bound_session_decision(t.store, manifest_sha256=selected["pending_manifest_sha256"])
        contexts = []
        execute = workflow._execute_exact_human_approved_write_core

        def observe(root, context, writer, **kwargs):
            contexts.append(context)
            return execute(root, context, writer, **kwargs)

        with patch.object(workflow, "_execute_exact_human_approved_write_core", new=observe), \
                patch.object(registry, "_new_ref", side_effect=AssertionError("re-review regenerated ref")), \
                patch.object(bundle, "save_context_bound_session_decision", side_effect=AssertionError("re-review replaced original")):
            result = self.review()
        self.assertTrue(result["ok"] and result["native_approval_redisplayed"])
        self.assertEqual(contexts, [original.context])
        self.assertEqual(result["work_session_binding"], original.prepared.manifest.work_session_binding.document())
        self.assertEqual(plan.read_bytes(), original_raw)
        self.assertEqual(t.native.calls, 2)
        self.assertEqual(t.store.read().revision, 2)
        self.assertEqual(len(t.claims()), 1)
        self.assertEqual(self.key.requests[-3:], [False, False, True])

    def test_cancel_preserves_original_pending_and_domain_bytes_without_creating_key(self):
        t = self.fixture
        self.cut_before_claim()
        before, calls = t.domain_files(), len(self.key.requests)
        t.native.approve = False
        self.reject(self.review, "exact_human_approval_cancelled")
        self.assertEqual(t.domain_files(), before)
        self.assertNotIn(True, self.key.requests[calls:])
        self.assertEqual(t.claims(), {})
        self.assertEqual(t.native.calls, 2)

    def test_real_started_and_succeeded_use_original_resume_without_new_native(self):
        t = self.fixture
        t.cut_before_writer()
        original_claims = set(t.claims())
        with patch.object(t.native, "show_collection", side_effect=AssertionError("stored approval re-reviewed")):
            resumed = self.review()
        self.assertTrue(resumed["ok"])
        self.assertIs(resumed["native_approval_redisplayed"], False)
        self.assertEqual(set(t.claims()), original_claims)
        before = t.domain_files()
        with patch.object(t.native, "show_collection", side_effect=AssertionError("success re-reviewed")), \
                patch.object(operation, "apply_session_decision_with_claim", side_effect=AssertionError("success wrote again")):
            done = self.review()
        self.assertEqual(done["receipt_sha256"], resumed["receipt_sha256"])
        self.assertIs(done["native_approval_redisplayed"], False)
        self.assertEqual(t.domain_files(), before)

    def test_corrupt_claim_is_not_absence_and_never_shows_native(self):
        t = self.fixture
        t.cut_before_writer()
        claim_path = next(t.root.joinpath(*Path(approval.CLAIMS_RELATIVE_ROOT).parts).glob("*.json"))
        claim_path.write_bytes(b"invalid private_error_marker claim")
        before = t.domain_files()
        with patch.object(t.native, "show_collection", side_effect=AssertionError("corrupt claim re-reviewed")):
            self.reject(self.review, "exact_human_approval_resume_claim_invalid")
        self.assertEqual(t.domain_files(), before)

    def test_authenticated_failed_claim_is_not_absence_or_new_approval(self):
        t = self.fixture
        selected = self.cut_before_claim()
        original = bundle.load_context_bound_session_decision(t.store, manifest_sha256=selected["pending_manifest_sha256"])

        def fail_with_original_mac(claim):
            claim.finalize_failed("synthetic_operation_failed")
            raise OSError("Synthetic terminal failure")

        with exact.ExactOperationWriterLock(t.root):
            with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
                workflow._execute_exact_human_approved_write_core(
                    t.root, original.context, fail_with_original_mac, native=t.native, key_provider=self.key,
                )
        self.assertEqual(len(t.claims()), 1)
        before = t.domain_files()
        with patch.object(t.native, "show_collection", side_effect=AssertionError("failed claim re-reviewed")):
            self.reject(self.review, "exact_human_approval_resume_claim_invalid")
        self.assertEqual(t.domain_files(), before)

    def test_missing_or_foreign_held_lock_cannot_start_discovery_or_native(self):
        t = self.fixture
        self.cut_before_claim()
        foreign = t.root.parent / "other-archive"
        foreign.mkdir()
        (foreign / "archive.yml").write_text("archive_id: archive:synthetic:other-rereview\n", encoding="utf-8")
        before = t.domain_files()
        with patch.object(t.native, "show_collection", side_effect=AssertionError("unlocked native")), \
                patch.object(self.key, "use_key", side_effect=AssertionError("unlocked key access")):
            self.reject(lambda: subject._review_original_session_decision_held(
                t.root, held=None, client_app_ref=t.app, task_route_ref=t.route, native=t.native, key_provider=self.key,
            ), "work_session_lock_required")
            with exact.ExactOperationWriterLock(foreign) as held:
                self.reject(lambda: subject._review_original_session_decision_held(
                    t.root, held=held, client_app_ref=t.app, task_route_ref=t.route, native=t.native, key_provider=self.key,
                ), "work_session_lock_required")
        self.assertEqual(t.domain_files(), before)

    def test_two_real_authenticated_claims_are_ambiguous_not_permission_to_rereview(self):
        t = self.fixture
        selected = self.cut_before_claim()
        original = bundle.load_context_bound_session_decision(t.store, manifest_sha256=selected["pending_manifest_sha256"])
        with exact.ExactOperationWriterLock(t.root):
            for _ in range(2):
                with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
                    workflow._execute_exact_human_approved_write_core(
                        t.root, original.context, lambda _claim: (_ for _ in ()).throw(OSError("Synthetic no writer")),
                        native=t.native, key_provider=self.key,
                    )
        self.assertEqual(len(t.claims()), 2)
        before = t.domain_files()
        with patch.object(t.native, "show_collection", side_effect=AssertionError("ambiguous claim re-reviewed")):
            self.reject(self.review, "exact_human_approval_resume_candidate_ambiguous")
        self.assertEqual(t.domain_files(), before)

    def test_bundle_drift_during_dialog_refuses_before_new_claim(self):
        t = self.fixture
        selected = self.cut_before_claim()
        plan_path = t.root.joinpath(*bundle.PRIVATE_ROOT) / (selected["pending_manifest_sha256"][7:] + ".json")
        original_raw = plan_path.read_bytes()
        t.native.before_click = lambda: plan_path.write_bytes(b"private_error_marker changed bundle")
        before_revision = t.store.read().revision
        try:
            self.reject(self.review)
            self.assertEqual(t.claims(), {})
            self.assertEqual(t.store.read().revision, before_revision)
        finally:
            plan_path.write_bytes(original_raw)
            t.native.before_click = None

    def test_claim_appearing_during_dialog_is_detected_before_new_write_key(self):
        t = self.fixture
        selected = self.cut_before_claim()
        original = bundle.load_context_bound_session_decision(t.store, manifest_sha256=selected["pending_manifest_sha256"])
        from test_v0420_work_session_operation import _Native, _Key

        def concurrent_claim():
            with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
                workflow._execute_exact_human_approved_write_core(
                    t.root, original.context, lambda _claim: (_ for _ in ()).throw(OSError("Synthetic interrupted writer")),
                    native=_Native(), key_provider=_Key(),
                )

        t.native.before_click = concurrent_claim
        calls = len(self.key.requests)
        self.reject(self.review, "work_session_original_operation_changed")
        self.assertNotIn(True, self.key.requests[calls:])
        self.assertEqual(len(t.claims()), 1)
        self.assertEqual(t.store.read().revision, 1)

    def test_actor_drift_inside_write_key_stops_publication_without_nested_discovery(self):
        t = self.fixture
        self.cut_before_claim()
        with exact.ExactOperationWriterLock(t.root) as held:
            selected = t.routing.read()

            def change_actor():
                t.routing.save(expected_sha256=selected.sha256, held_lock=held)

            self.key.before_create = change_actor
            self.reject(lambda: subject._review_original_session_decision_held(
                t.root, held=held, client_app_ref=t.app, task_route_ref=t.route, native=t.native, key_provider=self.key,
            ), "work_session_original_operation_changed")
        self.assertEqual(t.claims(), {})
        self.assertEqual(t.store.read().revision, 1)

    def test_changed_predecessor_or_wrong_route_does_not_offer_new_review(self):
        t = self.fixture
        self.cut_before_claim()
        self.reject(lambda: self.review(task_route_ref=actor.new_task_route_ref()), "work_session_original_operation_missing")
        other = registry.plan_transition(t.store.read(), action="register-app", label="Synthetic other app")
        with exact.ExactOperationWriterLock(t.root) as held:
            t.store.commit(other, held_lock=held)
        before = t.domain_files()
        with patch.object(t.native, "show_collection", side_effect=AssertionError("drift opened native")):
            self.reject(self.review)
        self.assertEqual(t.domain_files(), before)

    def test_actual_preclaim_cut_then_rereview_output_loss_resumes_original_claim_in_new_process(self):
        child = r'''
import json, os, sys
from pathlib import Path
from wom_kit import work_session_actor as actor, work_session_lifecycle as lifecycle
from wom_kit import work_session_operation as operation, work_session_rereview as subject
from wom_kit import exact_operation_manifest as exact
from test_v0420_work_session_execution import SessionNative
from test_v0420_work_session_operation import _Key
root, app, route, mode = sys.argv[1:]
if mode == 'preclaim':
    original = actor.WorkSessionActorStore.save
    def save(*args, **kwargs):
        result = original(*args, **kwargs)
        if kwargs.get('pending_manifest_sha256') is not None: os._exit(71)
        return result
    actor.WorkSessionActorStore.save = save
    lifecycle._create_task_core(Path(root), client_app_ref=app, task_route_ref=route,
        label='Synthetic private task', reviewer_claim='person:synthetic-original-rereview', native=SessionNative(), key_provider=_Key())
elif mode == 'rereview_cut':
    def cut(*args, **kwargs): os._exit(72)
    operation.apply_session_decision_with_claim = cut
    with exact.ExactOperationWriterLock(Path(root)) as held:
        subject._review_original_session_decision_held(Path(root), held=held, client_app_ref=app,
            task_route_ref=route, native=SessionNative(), key_provider=_Key())
else:
    result = lifecycle._resume_task_create_core(Path(root), client_app_ref=app, task_route_ref=route, key_provider=_Key())
    print(json.dumps({'ok':result['ok'], 'receipt_sha256':result['receipt_sha256'],
                      'native_approval_redisplayed':result['native_approval_redisplayed']}))
'''
        t = self.fixture
        kit = Path(__file__).resolve().parents[1]
        environment = dict(os.environ)
        environment["PYTHONPATH"] = os.pathsep.join((str(kit / "src"), str(kit / "tests")))
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        command = [sys.executable, "-B", "-c", child, str(t.root), t.app, t.route]
        first = subprocess.run([*command, "preclaim"], env=environment, capture_output=True, text=True,
                               encoding="utf-8", timeout=90, **options)
        self.assertEqual((first.returncode, first.stdout, first.stderr), (71, "", ""))
        self.assertEqual(t.claims(), {})
        selected = t.routing.read().document()
        path = t.root.joinpath(*bundle.PRIVATE_ROOT) / (selected["pending_manifest_sha256"][7:] + ".json")
        original = path.read_bytes()
        second = subprocess.run([*command, "rereview_cut"], env=environment, capture_output=True, text=True,
                                encoding="utf-8", timeout=90, **options)
        self.assertEqual((second.returncode, second.stdout, second.stderr), (72, "", ""))
        claims = set(t.claims())
        self.assertEqual(len(claims), 1)
        resumed = subprocess.run([*command, "resume"], env=environment, capture_output=True, text=True,
                                 encoding="utf-8", timeout=90, **options)
        self.assertEqual((resumed.returncode, resumed.stderr), (0, ""))
        result = json.loads(resumed.stdout)
        self.assertTrue(result["ok"])
        self.assertIs(result["native_approval_redisplayed"], False)
        self.assertEqual(set(t.claims()), claims)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(t.store.read().revision, 2)


if __name__ == "__main__":
    unittest.main()
