"""Approved whole preimages augment field recovery without retrofitting history."""

from dataclasses import replace
import unittest
from unittest.mock import patch

import test_v0420_local_recovery_session as fixture
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import exact_operation_manifest as exact
from wom_kit import local_recovery_execution as recovery
from wom_kit import local_recovery_session as subject


class SessionDocumentImagesTests(unittest.TestCase):
    def setUp(self):
        self.case = fixture.SessionLocalRecoveryTests("runTest")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.f, self.root = self.case.f, self.case.root
        self.path = self.root / self.case.factory().specs[0].target_relative

    def test_actual_approved_write_records_transition_but_does_not_claim_git_ownership(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            before = self.path.read_bytes()
            result = self.case.execute(held)
            self.assertTrue(result["ok"], result)
            self.assertTrue(result["whole_document_transition_verified"])
            self.assertFalse(result["whole_document_ownership_verified"])
            plan = self.case.retained()
            images = subject._document_images(plan)
            self.assertEqual(images[0]["pre_sha256"], recovery._sha(before))
            self.assertEqual(images[0]["post_sha256"], recovery._sha(self.path.read_bytes()))
            raw = plan.session_context
            document = subject.controls._strict_document(raw)
            document["document_images"][0]["pre_sha256"] = "sha256:" + "0" * 64
            with self.assertRaises(recovery.LocalRecoveryError):
                replace(plan, session_context=recovery._canonical_bytes(document))
            with patch.object(self.f.native, "show", side_effect=AssertionError("completed approval")):
                replay = self.case.resume(held)
            self.assertTrue(replay["whole_document_transition_verified"])
            self.assertEqual(self.case.retained().session_context, raw)

    def test_body_change_after_native_decision_does_not_create_domain_claim(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            claims = self.f.claims()
            old = self.path.read_bytes()
            show = self.f.native.show

            def change(**kwargs):
                result = show(**kwargs)
                self.path.write_bytes(old + b"\nSynthetic concurrent body edit.\n")
                return result

            with patch.object(self.f.native, "show", side_effect=change):
                with self.assertRaises(recovery.LocalRecoveryError):
                    self.case.execute(held)
            self.assertEqual(self.f.claims(), claims)
            self.assertIsNone(self.f.routing._read(current=False).pending_operation())
            self.assertEqual(self.path.read_bytes(), old + b"\nSynthetic concurrent body edit.\n")

    def test_missing_claim_original_review_refuses_changed_whole_preimage(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(broker, "_claim_exact_human_approval_core", side_effect=OSError("preclaim cut")):
                with self.assertRaises(recovery.LocalRecoveryError):
                    self.case.execute(held)
            plan = self.case.retained()
            self.path.write_bytes(self.path.read_bytes() + b"\nSynthetic later body.\n")
            self.assertTrue(recovery.verify_local_recovery_state(plan, state="pre")["all_match"])
            before = self.f.files()
            with patch.object(self.f.native, "show", side_effect=AssertionError("review changed original")):
                with self.assertRaises(recovery.LocalRecoveryError):
                    subject._review_original_session_local_recovery_held(self.root, held=held,
                        client_app_ref=self.f.app, task_route_ref=self.f.route,
                        native=self.f.native, key_provider=self.f.key)
            self.assertEqual(self.f.files(), before)

    def test_callback_body_change_is_refused_at_actual_cas_without_overwrite(self):
        changed = []
        original = self.path.read_bytes()

        def progress(event):
            if event.stage == "preflight" and not changed:
                self.path.write_bytes(original + b"\nSynthetic concurrent body preserved.\n")
                changed.append(True)

        with exact.ExactOperationWriterLock(self.root) as held:
            result = self.case.execute(held, progress_hook=progress)
            self.assertFalse(result["ok"], result)
            self.assertEqual(changed, [True])
            self.assertEqual(self.path.read_bytes(), original + b"\nSynthetic concurrent body preserved.\n")
            self.assertTrue(recovery.verify_local_recovery_state(self.case.retained(), state="pre")["all_match"])

    def test_original_without_images_retains_historical_control_and_executes_without_new_proof(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            fresh = subject._prepare_local_recovery_session_held(self.root, self.case.factory, **self.case.options(held))
            document = subject.controls._strict_document(fresh.session_context)
            del document["document_images"]
            scope = document["scope"]
            del scope["document_images_sha256"]
            scope["scope_sha256"] = subject._sha({key: value for key, value in scope.items() if key != "scope_sha256"})
            unbound = exact.ExactOperationManifest.from_document(document["unbound_manifest"])
            legacy = replace(fresh, manifest=subject._manifest(unbound, scope), session_context=None)
            context = recovery.local_recovery_context(legacy, mode="apply", reviewer_claim=subject._view(fresh).context.reviewer_claim)
            document["context"] = subject.controls._context_document(context)
            legacy = replace(legacy, session_context=recovery._canonical_bytes(document))
            expected = recovery._canonical_line(recovery._control_document(legacy))
            # The retained old-shape plan still passes actual session/native
            # admission. No synthetic claim or completion is pre-seeded.
            with patch.object(subject, "_prepare_local_recovery_session_held", return_value=legacy):
                result = self.case.execute(held)
            self.assertTrue(result["ok"], result)
            self.assertFalse(result["whole_document_transition_verified"])
            self.assertFalse(result["whole_document_ownership_verified"])
            self.assertEqual(subject._view(self.case.retained()).control_bytes, expected)
            self.assertIsNone(subject._document_images(self.case.retained()))


if __name__ == "__main__":
    unittest.main()
