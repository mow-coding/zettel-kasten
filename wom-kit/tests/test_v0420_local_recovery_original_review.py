"""Original local recovery review uses real claims and synthetic archive data."""

import unittest
from unittest.mock import patch

import test_v0420_local_recovery_session as fixture
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import exact_operation_manifest as exact
from wom_kit import local_recovery_execution as recovery
from wom_kit import local_recovery_session as subject
from wom_kit import work_session_actor as actor
from wom_kit import work_session_registry as registry


class OriginalLocalRecoveryReviewTests(unittest.TestCase):
    def setUp(self):
        self.case = fixture.SessionLocalRecoveryTests("runTest")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.f, self.root = self.case.f, self.case.root

    def review(self, held, **changes):
        options = dict(held=held, client_app_ref=self.f.app, task_route_ref=self.f.route,
            native=self.f.native, key_provider=self.f.key)
        options.update(changes)
        return subject._review_original_session_local_recovery_held(self.root, **options)

    def cut(self, held):
        claims = self.f.claims()
        with patch.object(broker, "_claim_exact_human_approval_core", side_effect=OSError("synthetic preclaim cut")):
            with self.assertRaises(recovery.LocalRecoveryError):
                self.case.execute(held)
        self.assertEqual(self.f.claims(), claims)
        self.f.key.create_if_missing_calls.clear()
        plan = self.case.retained()
        self.assertTrue(recovery.verify_local_recovery_state(plan, state="pre")["all_match"])
        return plan, self.f.routing._read(current=False)

    def test_original_review_after_unrelated_app_and_completed_replay(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            plan, pending = self.cut(held)
            view = subject._view(plan)
            with self.assertRaises(recovery.LocalRecoveryError):
                self.case.resume(held)
            registered = registry.plan_transition(self.f.store.read(), action="register-app",
                label="Synthetic unrelated original review app")
            self.f.store.commit(registered, held_lock=held)
            request = broker._request_exact_human_approval_core

            def native(context, **kwargs):
                self.assertEqual(context, view.context)
                self.assertEqual(self.f.routing._read(current=False)._raw, pending._raw)
                return request(context, **kwargs)

            with patch.object(broker, "_request_exact_human_approval_core", side_effect=native), \
                 patch.object(subject, "_prepare_local_recovery_session_held", side_effect=AssertionError("replan")), \
                 patch.object(recovery, "persist_local_recovery_control", side_effect=AssertionError("replace original")):
                result = self.review(held)
            self.assertTrue(result["ok"], result)
            self.assertTrue(result["original_context_preserved"])
            self.assertTrue(result["native_approval_redisplayed"])
            self.assertEqual(subject._view(self.case.retained()).control_bytes, view.control_bytes)
            before = self.f.files()
            with patch.object(self.f.native, "show", side_effect=AssertionError("duplicate review")), \
                 patch.object(recovery, "_execute_core", side_effect=AssertionError("duplicate domain")), \
                 patch.object(actor.WorkSessionActorStore, "save", side_effect=AssertionError("duplicate actor")):
                replay = self.review(held)
            self.assertTrue(replay["original_operation_already_completed"])
            self.assertFalse(replay["native_approval_redisplayed"])
            self.assertEqual(self.f.files(), before)
            self.assertNotIn(True, self.f.key.create_if_missing_calls)

    def test_cancel_repeated_cut_and_started_claim_delegation(self):
        class Cancel:
            def show(self, **kwargs):
                return 2, False

        with exact.ExactOperationWriterLock(self.root) as held:
            _plan, pending = self.cut(held)
            before = self.f.files()
            with self.assertRaises(recovery.LocalRecoveryError):
                self.review(held, native=Cancel())
            self.assertEqual(self.f.files(), before)
            with patch.object(broker, "_claim_exact_human_approval_core", side_effect=OSError("repeat cut")):
                with self.assertRaises(recovery.LocalRecoveryError):
                    self.review(held)
            self.assertEqual(self.f.files(), before)
            with patch.object(recovery, "_execute_core", side_effect=OSError("started before checkpoint")):
                with self.assertRaises(recovery.LocalRecoveryError):
                    self.review(held)
            self.assertEqual(self.f.routing._read(current=False)._raw, pending._raw)
            calls = self.f.native.calls
            with patch.object(self.f.native, "show", side_effect=AssertionError("new review")):
                result = self.review(held)
            self.assertTrue(result["ok"], result)
            self.assertFalse(result["native_approval_redisplayed"])
            self.assertEqual(self.f.native.calls, calls)

    def test_after_click_control_and_claim_image_changes_are_rejected(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            plan, _pending = self.cut(held)
            control = self.root / recovery._control_relative(plan.manifest.manifest_sha256)
            original = control.read_bytes()
            before_claims = self.f.claims()

            class Mutate:
                def show(inner, **kwargs):
                    control.write_bytes(original + b" ")
                    return self.f.native.show(**kwargs)

            with patch.object(recovery._Writer, "write_field", side_effect=AssertionError("changed evidence write")):
                with self.assertRaises(recovery.LocalRecoveryError):
                    self.review(held, native=Mutate())
            self.assertEqual(self.f.claims(), before_claims)
            self.assertTrue(recovery.verify_local_recovery_state(plan, state="pre")["all_match"])
            control.write_bytes(original)  # Only this synthetic fixture is restored.
            origin_claim = next((self.root / approval.CLAIMS_RELATIVE_ROOT).glob("*.json"))
            origin_bytes = origin_claim.read_bytes()

            class CopyClaim:
                def show(inner, **kwargs):
                    (origin_claim.parent / "synthetic-identical-copy.json").write_bytes(origin_bytes)
                    return self.f.native.show(**kwargs)

            with self.assertRaises(recovery.LocalRecoveryError):
                self.review(held, native=CopyClaim())
            self.assertTrue(recovery.verify_local_recovery_state(plan, state="pre")["all_match"])
            self.assertEqual(len(self.f.claims()), len(before_claims) + 1)


if __name__ == "__main__":
    unittest.main()
