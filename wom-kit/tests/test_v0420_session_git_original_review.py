"""Explicit original Git re-review, with real temporary Git/claim evidence."""

from contextlib import contextmanager
import inspect
import unittest
from unittest.mock import patch

import test_v0420_work_session_git_workflow as fixtures
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import exact_operation_manifest as exact
from wom_kit import git_backup_writer as writer
from wom_kit import work_session_actor as actor
from wom_kit import work_session_git_bundle as bundle
from wom_kit import work_session_git_terminal as terminal
from wom_kit import work_session_git_workflow as subject
from wom_kit import work_session_registry as registry


class OriginalGitReviewTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.SessionGitWorkflowTests(methodName="runTest")
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def cut(self, held):
        with patch.object(broker, "_claim_exact_human_approval_core", side_effect=RuntimeError("synthetic cut")):
            with self.assertRaises(subject.WorkSessionGitWorkflowError):
                self.f.execute(held)
        return self.f.original_git(held), self.f.routing._read(current=False)

    def review(self, held, **changes):
        options = dict(native=self.f.native, key_provider=self.f.key)
        options.update(changes)
        return subject._review_original_session_git_backup_held(self.f.root, held=held,
            client_app_ref=self.f.app, task_route_ref=self.f.route, **options)

    def test_missing_claim_reviews_identical_context_then_real_git_and_completed_replay(self):
        f = self.f
        self.assertEqual(set(inspect.signature(subject._review_original_session_git_backup_held).parameters),
            {"root", "held", "client_app_ref", "task_route_ref", "work_session_ref", "native", "key_provider", "progress_hook"})
        with exact.ExactOperationWriterLock(f.root) as held:
            original, pending = self.cut(held)
            context_sha = approval.exact_human_approval_context_sha256(original.context)
            immutable_bundle = writer._canonical(writer._bundle_document(original.prepared))
            execute = writer._run_git_backup_exact_operation
            observed = []

            def check(prepared, **kwargs):
                self.assertEqual(f.routing._read(current=False)._raw, pending._raw)
                self.assertEqual(writer._canonical(writer._bundle_document(prepared)), immutable_bundle)
                self.assertEqual(approval.exact_human_approval_context_sha256(kwargs["context"]), context_sha)
                observed.append(kwargs["claim"].public_reference())
                return execute(prepared, **kwargs)

            with patch.object(writer.planning, "git_backup_plan", side_effect=AssertionError("new plan")), \
                 patch.object(bundle, "_save_original_git_context_held", side_effect=AssertionError("context rewritten")), \
                 patch.object(writer, "_run_git_backup_exact_operation", side_effect=check), \
                 patch.object(f.routing.__class__, "save", autospec=True, side_effect=f.routing.__class__.save) as save:
                result = self.review(held)
            self.assertTrue(result["original_commit_verified"])
            self.assertTrue(result["native_approval_redisplayed"])
            self.assertTrue(result["original_context_preserved"])
            self.assertEqual(f.native.calls, 2)
            self.assertEqual(len(observed), 1)
            self.assertEqual(save.call_count, 1)
            self.assertIsNone(save.call_args.kwargs["pending_operation"])
            self.assertEqual(save.call_args.kwargs["expected_sha256"], pending.sha256)
            self.assertNotEqual(f.git("rev-parse", "HEAD").stdout.strip(), f.fixture.initial_head)
            f.fixture.assert_remote_matches_head()
            evidence = f.evidence()
            with patch.object(broker, "_request_exact_human_approval_core", side_effect=AssertionError("new native")), \
                 patch.object(writer, "_run_git_backup_exact_operation", side_effect=AssertionError("writer repeated")), \
                 patch.object(terminal, "_build_git_terminal_record", side_effect=AssertionError("signed again")), \
                 patch.object(actor.WorkSessionActorStore, "save", side_effect=AssertionError("actor rewritten")):
                replay = self.review(held)
            self.assertFalse(replay["native_approval_redisplayed"])
            self.assertTrue(replay["original_operation_already_completed"])
            self.assertEqual(f.evidence(), evidence)

    def test_cancel_and_after_click_excluded_source_drift_preserve_original_pending(self):
        f = self.f

        class CancelNative:
            def show(self, **_kwargs):
                return 2, False

        with exact.ExactOperationWriterLock(f.root) as held:
            _original, pending = self.cut(held)
            before = f.evidence()
            f.key.create_if_missing.clear()
            with self.assertRaises(subject.WorkSessionGitWorkflowError) as caught:
                self.review(held, native=CancelNative())
            self.assertEqual(caught.exception.code, "exact_human_approval_cancelled")
            self.assertIsNone(caught.exception.__context__)
            self.assertNotIn(True, f.key.create_if_missing)
            self.assertEqual(f.evidence(), before)
            f.native.callback = lambda: (f.root / "new-private.txt").write_text("synthetic postclick drift\n")
            with patch.object(writer, "_run_git_backup_exact_operation", side_effect=AssertionError("Git effects")):
                with self.assertRaises(subject.WorkSessionGitWorkflowError) as changed:
                    self.review(held)
            self.assertEqual(changed.exception.code, "work_session_git_changed")
            self.assertIsNone(changed.exception.__context__)
            self.assertNotIn(True, f.key.create_if_missing)
            self.assertEqual(f.evidence(), before)
            self.assertEqual(f.routing._read(current=False)._raw, pending._raw)
            self.assertEqual(f.git("rev-parse", "HEAD").stdout.strip(), f.fixture.initial_head)

    def test_repeated_preclaim_cut_then_started_claim_uses_original_resume_without_third_review(self):
        f = self.f
        with exact.ExactOperationWriterLock(f.root) as held:
            _original, pending = self.cut(held)
            before = f.evidence()
            with patch.object(broker, "_claim_exact_human_approval_core", side_effect=RuntimeError("second cut")):
                with self.assertRaises(subject.WorkSessionGitWorkflowError):
                    self.review(held)
            self.assertEqual(f.evidence(), before)
            self.assertEqual(f.routing._read(current=False)._raw, pending._raw)
            with patch.object(writer, "_run_git_backup_exact_operation", side_effect=RuntimeError("started cut")):
                with self.assertRaises(subject.WorkSessionGitWorkflowError):
                    self.review(held)
            self.assertEqual(f.native.calls, 3)
            with patch.object(broker, "_request_exact_human_approval_core", side_effect=AssertionError("new review")), \
                 patch.object(writer.planning, "git_backup_plan", side_effect=AssertionError("fresh plan")), \
                 patch.object(bundle, "_save_original_git_context_held", side_effect=AssertionError("context rewritten")):
                result = self.review(held)
            self.assertTrue(result["original_commit_verified"])
            self.assertFalse(result["native_approval_redisplayed"])
            self.assertEqual(result["started_resume_state"], "authenticated_before_first_checkpoint")
            self.assertEqual(f.native.calls, 3)

    def test_key_provider_entry_inserts_real_claim_and_cannot_publish_a_second_one(self):
        f = self.f
        with exact.ExactOperationWriterLock(f.root) as held:
            original, pending = self.cut(held)
            directory = f.root / approval.CLAIMS_RELATIVE_ROOT
            names_before = set(p.name for p in directory.glob("*.json"))
            request, use_key = broker._request_exact_human_approval_core, f.key.use_key
            original_boundary = writer._git_backup_post_decision_boundary
            decisions, inserted = [], []
            publication_ready = [False]

            @contextmanager
            def boundary(*args, **kwargs):
                with original_boundary(*args, **kwargs) as value:
                    publication_ready[0] = True
                    try:
                        yield value
                    finally:
                        publication_ready[0] = False

            def record(*args, **kwargs):
                decision = request(*args, **kwargs)
                decisions.append(decision)
                return decision

            def provider(root, consumer, *, create_if_missing=False):
                def enter(key):
                    if publication_ready[0]:
                        self.assertFalse(create_if_missing)
                        with fixtures.execution._claim_boundary(f.store, held, create=False) as (bound_root, parent):
                            claim = broker._claim_exact_human_approval_core(root, original.context, decisions[-1], key,
                                bound_archive_root=bound_root, claim_parent_binding=parent)
                            inserted.append(claim.public_reference())
                            claim.close()
                    return consumer(key)
                return use_key(root, enter, create_if_missing=create_if_missing)

            with patch.object(broker, "_request_exact_human_approval_core", side_effect=record), \
                 patch.object(f.key, "use_key", side_effect=provider), \
                 patch.object(writer, "_git_backup_post_decision_boundary", side_effect=boundary), \
                 patch.object(writer, "_run_git_backup_exact_operation", side_effect=AssertionError("Git effect")):
                with self.assertRaises(subject.WorkSessionGitWorkflowError) as caught:
                    self.review(held)
            self.assertIsNone(caught.exception.__context__)
            self.assertEqual(len(inserted), 1)
            self.assertEqual(set(p.name for p in directory.glob("*.json")) - names_before,
                             {inserted[0]["approval_id"] + ".json"})
            self.assertEqual(f.routing._read(current=False)._raw, pending._raw)
            self.assertEqual(f.git("rev-parse", "HEAD").stdout.strip(), f.fixture.initial_head)

    def test_wrong_session_current_owner_and_original_proof_drift_refuse_before_native(self):
        f = self.f
        with exact.ExactOperationWriterLock(f.root) as held:
            original, pending = self.cut(held)
            count, before = f.native.calls, f.evidence()
            with self.assertRaises(subject.WorkSessionGitWorkflowError):
                self.review(held, work_session_ref="work_session:wrong")
            with patch.object(registry.WorkSessionRegistryStore, "require_claimed_binding",
                              side_effect=registry.WorkSessionRegistryError("work_session_claim_conflict")):
                with self.assertRaises(subject.WorkSessionGitWorkflowError):
                    self.review(held)
            proof = original.prepared.session_scope.document()["establishment_proof"]
            path = f.root / "receipts" / "ops" / "exact-operations" / (proof["execution_sha256"][7:] + ".json")
            path.write_bytes(path.read_bytes() + b" ")
            changed = f.evidence()
            with self.assertRaises(subject.WorkSessionGitWorkflowError) as caught:
                self.review(held)
            self.assertIsNone(caught.exception.__context__)
            self.assertEqual(f.native.calls, count)
            self.assertEqual(f.evidence(), changed)
            self.assertEqual(f.routing._read(current=False)._raw, pending._raw)
            self.assertNotEqual(changed, before)
            self.assertEqual(f.git("rev-parse", "HEAD").stdout.strip(), f.fixture.initial_head)

    def test_unrelated_registry_transition_then_actual_pause_refuses_original_review(self):
        f = self.f
        with exact.ExactOperationWriterLock(f.root) as held:
            original, pending = self.cut(held)
            before_registry = f.store.read()
            registration = registry.plan_transition(before_registry, action="register-app",
                label="Synthetic unrelated Git app")
            f.store.commit(registration, held_lock=held)
            self.assertNotEqual(f.store.read().sha256, before_registry.sha256)
            self.assertEqual(f.store.read().binding(f.session), before_registry.binding(f.session))
            subject._current_scope(original.prepared, f.store, f.routing, pending, held)
            paused = registry.plan_transition(f.store.read(), action="pause",
                client_app_ref=f.app, work_session_ref=f.session, claim_ref=f.claim_ref)
            f.store.commit(paused, held_lock=held)
            before, calls = f.evidence(), f.native.calls
            with patch.object(broker, "_request_exact_human_approval_core", side_effect=AssertionError("new review")), \
                 patch.object(writer, "_run_git_backup_exact_operation", side_effect=AssertionError("Git effects")):
                with self.assertRaises(subject.WorkSessionGitWorkflowError):
                    self.review(held)
            self.assertEqual(f.evidence(), before)
            self.assertEqual(f.native.calls, calls)
            self.assertEqual(f.routing._read(current=False)._raw, pending._raw)
            self.assertEqual(f.git("rev-parse", "HEAD").stdout.strip(), f.fixture.initial_head)


if __name__ == "__main__":
    unittest.main()
