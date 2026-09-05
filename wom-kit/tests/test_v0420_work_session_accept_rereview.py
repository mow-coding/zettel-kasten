"""An accept cut before authenticated publication needs original native review."""

import unittest
from unittest.mock import patch

from wom_kit import exact_human_approval_workflow as workflow
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_actor as actor
from wom_kit import work_session_bundle as bundle
from wom_kit import work_session_operation as operation
from wom_kit import work_session_registry as registry
from wom_kit import work_session_rereview as subject
import test_v0420_work_session_accept_lifecycle as fixture
from test_v0420_work_session_rereview import GuardedKey


class AcceptRereviewTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.AcceptLifecycleTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.key = GuardedKey(self.fixture.case.key)
        self.fixture.case.key = self.key
        show = self.fixture.case.native.show_collection

        def outside_key(**kwargs):
            self.assertFalse(self.key.active)
            return show(**kwargs)

        self.fixture.case.native.show_collection = outside_key

    def review(self, **changes):
        t = self.fixture
        arguments = dict(action="accept", client_app_ref=t.receiving, task_route_ref=t.route,
                         native=t.case.native, key_provider=self.key)
        arguments.update(changes)
        with exact.ExactOperationWriterLock(t.root) as held:
            return subject._review_original_session_decision_held(t.root, held=held, **arguments)

    def reject(self, call):
        with self.assertRaises(subject.WorkSessionRereviewError) as caught:
            call()
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)

    def cut_before_claim(self):
        t = self.fixture
        previous_claims = t.case.claims()
        original = actor.WorkSessionActorStore.save

        def cut(store, **arguments):
            result = original(store, **arguments)
            if arguments.get("pending_manifest_sha256") is not None:
                raise OSError("Synthetic preclaim cut")
            return result

        with patch.object(actor.WorkSessionActorStore, "save", new=cut):
            t.reject(t.accept)
        self.assertEqual(t.case.claims(), previous_claims)
        self.assertEqual(len(t.store.read()._document["sessions"]), 1)
        return t.routing.read().document()

    def test_accept_preclaim_reuses_original_context_and_successor_without_new_plan(self):
        t = self.fixture
        selected = self.cut_before_claim()
        path = t.root.joinpath(*bundle.PRIVATE_ROOT) / (selected["pending_manifest_sha256"][7:] + ".json")
        raw = path.read_bytes()
        original = bundle.load_context_bound_session_decision(t.store,
            manifest_sha256=selected["pending_manifest_sha256"])
        contexts = []
        execute = workflow._execute_exact_human_approved_write_core

        def observe(root, context, writer, **kwargs):
            contexts.append(context)
            return execute(root, context, writer, **kwargs)

        with patch.object(workflow, "_execute_exact_human_approved_write_core", new=observe), \
                patch.object(registry, "_new_ref", side_effect=AssertionError("regenerated successor")), \
                patch.object(bundle, "save_context_bound_session_decision", side_effect=AssertionError("replaced bundle")):
            result = self.review()
        self.assertTrue(result["ok"] and result["native_approval_redisplayed"])
        self.assertEqual(contexts, [original.context])
        self.assertEqual(result["work_session_binding"], original.prepared.manifest.work_session_binding.document())
        self.assertEqual(path.read_bytes(), raw)
        self.assertEqual(t.routing.read().document()["established_origin"]["action"], "accept")
        self.assertEqual(t.case.native.calls, 4)
        self.assertEqual(len(t.store.read()._document["sessions"]), 2)

    def test_wrong_action_cancel_and_target_drift_preserve_pending_without_claim(self):
        t = self.fixture
        selected = self.cut_before_claim()
        before = t.files()
        with patch.object(t.case.native, "show_collection", side_effect=AssertionError("wrong action prompted")):
            self.reject(lambda: self.review(action="create"))
        self.assertEqual(t.files(), before)
        t.case.native.approve = False
        self.reject(self.review)
        self.assertEqual(t.files(), before)
        t.case.native.approve = True
        path = t.root.joinpath(*bundle.PRIVATE_ROOT) / (selected["pending_manifest_sha256"][7:] + ".json")
        raw, claims = path.read_bytes(), t.case.claims()
        t.case.native.before_click = lambda: path.write_bytes(b"Synthetic changed original")
        try:
            self.reject(self.review)
            self.assertEqual(t.case.claims(), claims)
            self.assertEqual(len(t.store.read()._document["sessions"]), 1)
        finally:
            path.write_bytes(raw)
            t.case.native.before_click = None
        self.assertEqual(t.files(), before)

    def test_started_and_completed_accept_do_not_redisplay_native(self):
        t = self.fixture
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=OSError("Synthetic started cut")):
            t.reject(t.accept)
        old_names = set(t.case.claims())
        with patch.object(t.case.native, "show_collection", side_effect=AssertionError("started re-reviewed")):
            result = self.review()
        self.assertFalse(result["native_approval_redisplayed"])
        self.assertEqual(set(t.case.claims()), old_names)
        before = t.files()
        with patch.object(t.case.native, "show_collection", side_effect=AssertionError("completed re-reviewed")), \
                patch.object(operation, "apply_session_decision_with_claim", side_effect=AssertionError("completed wrote")):
            completed = self.review()
        self.assertFalse(completed["native_approval_redisplayed"])
        self.assertEqual(completed["receipt_sha256"], result["receipt_sha256"])
        self.assertEqual(t.files(), before)


if __name__ == "__main__":
    unittest.main()
