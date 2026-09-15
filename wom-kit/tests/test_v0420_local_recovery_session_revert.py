"""Session-scoped compensation of a completed title recovery.

The compensation is a new bound apply plan over exactly the fields that still
hold the approved post value; it is natively approved like any apply, keeps
later unrelated changes, records the compensated manifest in its evidence and
never rewrites the original control, receipt, claim or checkpoint.
"""

import unittest
from unittest.mock import patch

import test_local_recovery_execution as recovery_fixture
import test_v0420_local_recovery_session as session_tests
from wom_kit import archive_services
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import exact_operation_manifest as exact
from wom_kit import local_recovery_execution as recovery
from wom_kit import local_recovery_session as subject


class SessionSubsetRevertTests(unittest.TestCase):
    def setUp(self):
        self.case = session_tests.SessionLocalRecoveryTests("runTest")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.f, self.root = self.case.f, self.case.root
        self.path = self.root / "zettels" / (recovery_fixture.ZETTEL_ID + ".md")
        for seam in (patch.object(windows, "_CtypesTaskDialogNative", return_value=self.f.native),
                     patch.object(broker, "_production_key_provider", return_value=self.f.key)):
            seam.start()
            self.addCleanup(seam.stop)

    def revert(self, held, **extra):
        return subject._dispatch_session_local_recovery(self.root, mode="revert", client_app_ref=self.f.app,
            task_route_ref=self.f.route, work_session_ref=self.f.session, allowed_domains={"synthetic_title"},
            reviewer_claim="person:synthetic-revert-reviewer", **extra)

    def test_completed_recovery_is_compensated_as_a_bound_apply_and_unrelated_edits_survive(self):
        original_bytes = self.path.read_bytes()
        with exact.ExactOperationWriterLock(self.root) as held:
            applied = self.case.execute(held)
            self.assertTrue(applied["ok"], applied)
            original = self.case.retained()
            original_control = recovery._control_document(original)
            recovered = self.path.read_bytes()
            self.assertNotEqual(recovered, original_bytes)
        # An unrelated later body edit must survive the compensation.
        self.path.write_bytes(recovered + b"\nUnrelated later body line.\n")
        archive_services.index_archive(self.root)
        files_before = self.f.files()
        with patch.object(subject, "_review_original_session_local_recovery_held",
                          side_effect=AssertionError("review path used")), \
             patch.object(recovery, "resume_local_recovery", side_effect=AssertionError("legacy resume")):
            result = self.revert(None)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["state"], "applied")
        self.assertEqual(result["mode"], "revert")
        self.assertEqual(result["field_count"], 1)
        self.assertTrue(result["original_completion_verified"])
        self.assertTrue(result["whole_document_transition_verified"])
        self.assertNotEqual(result["manifest_sha256"], original.manifest.manifest_sha256)
        after = self.path.read_bytes()
        frontmatter, _body = archive_services.require_readable_zettel_content(self.path)
        original_frontmatter, _ = archive_services.require_readable_zettel_text(
            archive_services.decode_utf8_with_universal_newlines(original_bytes))
        self.assertEqual(frontmatter["title"], original_frontmatter["title"])
        self.assertTrue(after.endswith(b"\nUnrelated later body line.\n"))
        # The compensation is its own bound control naming the compensated
        # manifest; the original control is untouched.
        compensation = self.case.retained()
        self.assertNotEqual(compensation.manifest.manifest_sha256, original.manifest.manifest_sha256)
        self.assertEqual(compensation.manifest.operation_evidence.schema, subject.SESSION_SUBSET_REVERT_EVIDENCE_SCHEMA)
        self.assertEqual(dict(compensation.manifest.operation_evidence.digests)["compensated_manifest_sha256"],
                         original.manifest.manifest_sha256)
        self.assertEqual(compensation.manifest.work_session_binding, self.f.binding)
        reloaded = recovery.load_local_recovery_plan(self.root, manifest_sha256=original.manifest.manifest_sha256)
        self.assertEqual(recovery._control_document(reloaded), original_control)
        self.assertTrue(recovery.verify_local_recovery_state(reloaded, state="pre")["all_match"])
        self.assertEqual(self.f.native.calls, 2)
        # A second compensation finds nothing left at the post value.
        files_after = self.f.files()
        again = self.revert(None)
        self.assertTrue(again["ok"], again)
        self.assertEqual(again["state"], "already_reverted")
        self.assertEqual(again["effects_state"], "none")
        self.assertEqual(again["already_pre_field_count"], 1)
        self.assertEqual(self.f.files(), files_after)
        self.assertEqual(self.f.native.calls, 2)
        self.assertNotEqual(files_before, files_after)

    def test_pending_original_and_divergent_field_are_refused_without_effects(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(recovery, "_execute_core", side_effect=OSError("synthetic prewriter cut")):
                with self.assertRaises(recovery.LocalRecoveryError):
                    self.case.execute(held)
        before = self.f.files()
        blocked = self.revert(None)
        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["reason_codes"], ["local_recovery_resume_invalid"])
        self.assertEqual(blocked["effects_state"], "none")
        self.assertEqual(self.f.files(), before)
        self.assertEqual(self.f.native.calls, 1)
        # Finish the original, then make the recovered field diverge: the
        # compensation refuses rather than guessing.
        resumed = subject._dispatch_session_local_recovery(self.root, mode="resume", client_app_ref=self.f.app,
            task_route_ref=self.f.route, allowed_domains={"synthetic_title"})
        self.assertTrue(resumed["ok"], resumed)
        raw = self.path.read_bytes()
        self.path.write_bytes(raw.replace(b"Recovered exact title", b"Manually retitled afterwards", 1))
        archive_services.index_archive(self.root)
        before = self.f.files()
        divergent = self.revert(None)
        self.assertFalse(divergent["ok"])
        self.assertEqual(divergent["reason_codes"], ["local_recovery_partial_revert_blocked"])
        self.assertEqual(self.f.files(), before)

    def test_revert_mode_rejects_a_planner_and_requires_a_reviewer(self):
        for kwargs in ({"plan_factory": self.case.factory}, {"reviewer_claim": None}):
            result = subject._dispatch_session_local_recovery(self.root, mode="revert", client_app_ref=self.f.app,
                task_route_ref=self.f.route, work_session_ref=self.f.session, allowed_domains={"synthetic_title"},
                **{"reviewer_claim": "person:x", **kwargs})
            self.assertFalse(result["ok"])
            self.assertEqual(result["reason_codes"], ["local_recovery_session_context_invalid"])
            self.assertEqual(result["effects_state"], "none")


if __name__ == "__main__":
    unittest.main()
