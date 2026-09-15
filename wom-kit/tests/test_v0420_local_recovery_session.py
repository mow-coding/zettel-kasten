"""Actual scoped document recovery, with synthetic native intent/key only."""

from dataclasses import replace
import unittest
from unittest.mock import patch

import test_local_recovery_execution as recovery_fixture
import test_v0420_source_intake_record_workflow as session_fixture
from wom_kit import archive_services
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import exact_operation_manifest as exact
from wom_kit import local_recovery_execution as recovery
from wom_kit import local_recovery_session as subject
from wom_kit import work_session_actor as actor
from wom_kit import work_session_registry as registry


class SessionLocalRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.f = session_fixture.SessionSourceIntakeRecordWorkflowTests("runTest")
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.root = self.f.root
        archive_services.index_archive(self.root)
        helper = recovery_fixture.LocalRecoveryExecutionTests()
        self.factory = lambda: helper.title_plan(self.root)

    def options(self, held):
        return dict(held=held, client_app_ref=self.f.app, task_route_ref=self.f.route,
                    work_session_ref=self.f.session, reviewer_claim="person:synthetic-recovery-reviewer",
                    key_provider=self.f.key)

    def execute(self, held, **extra):
        return subject._execute_session_local_recovery_held(self.root, self.factory,
            **self.options(held), native=self.f.native, **extra)

    def resume(self, held):
        return subject._resume_session_local_recovery_held(self.root, held=held,
            client_app_ref=self.f.app, task_route_ref=self.f.route, key_provider=self.f.key)

    def retained(self):
        selected = self.f.routing._read(current=False)
        pointer = (selected.pending_operation().document() if selected.pending_operation() is not None
                   else selected.document()["last_completed_operation"])
        self.assertEqual(pointer["kind"], "local_recovery")
        return recovery.load_local_recovery_plan(self.root, manifest_sha256=pointer["manifest_sha256"])

    def test_prepare_round_trip_rejects_rehashed_payload_or_context_replacement(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            before = self.f.files()
            plan = subject._prepare_local_recovery_session_held(self.root, self.factory, **self.options(held))
            self.assertEqual(self.f.files(), before)
            self.assertEqual(self.f.native.calls, 0)
            self.assertEqual(plan.manifest.work_session_binding, self.f.binding)
            recovery.persist_local_recovery_control(plan)
            loaded = recovery.load_local_recovery_plan(self.root, manifest_sha256=plan.manifest.manifest_sha256)
            self.assertEqual(loaded.session_context, plan.session_context)
            self.assertEqual(subject._view(loaded).context, subject._view(plan).context)
            for change in (dict(public_summary={"substituted": True}),
                           dict(warning_codes=("substituted",))):
                with self.subTest(change=change):
                    with self.assertRaises(recovery.LocalRecoveryError):
                        replace(loaded, **change)
            # A relabelled historical binding alone remains no write authority.
            stripped = replace(loaded, session_context=None)
            with self.assertRaises(recovery.LocalRecoveryError):
                recovery._run_with_store(stripped, None,
                    exact.FileExactOperationCheckpointStore(self.root, writer_lock=held),
                    mode="apply", resume=False, progress_hook=None)

    def test_real_title_write_cut_unrelated_app_resume_and_completed_replay(self):
        write = recovery._Writer.write_field

        def cut(writer, **kwargs):
            write(writer, **kwargs)
            raise RuntimeError("synthetic interruption after title write")

        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(recovery._Writer, "write_field", new=cut):
                interrupted = self.execute(held)
            self.assertFalse(interrupted["ok"], interrupted)
            self.assertEqual(interrupted["applied_field_count"], 1)
            original = self.retained()
            original_control = recovery._control_document(original)
            pending = self.f.routing._read(current=False)._raw
            registered = registry.plan_transition(self.f.store.read(), action="register-app",
                label="Synthetic unrelated recovery app")
            self.f.store.commit(registered, held_lock=held)
            self.assertEqual(self.f.routing._read(current=False)._raw, pending)
            with patch.object(subject, "_prepare_local_recovery_session_held", side_effect=AssertionError("replan")), \
                 patch.object(self.f.native, "show", side_effect=AssertionError("native redisplay")), \
                 patch.object(recovery._Writer, "write_field", side_effect=AssertionError("duplicate title write")):
                resumed = self.resume(held)
                self.assertTrue(resumed["ok"], resumed)
                self.assertTrue(resumed["original_completion_verified"])
                self.assertTrue(resumed["current_claim_ownership_verified"])
                self.assertFalse(resumed["whole_document_ownership_verified"])
                self.assertEqual(recovery._control_document(self.retained()), original_control)
                before = self.f.files()
                with patch.object(actor.WorkSessionActorStore, "save", side_effect=AssertionError("actor replay")), \
                     patch.object(recovery, "_execute_core", side_effect=AssertionError("domain replay")), \
                     patch.object(broker, "_claim_exact_human_approval_core", side_effect=AssertionError("approval replay")):
                    replay = self.resume(held)
                self.assertTrue(replay["original_operation_already_completed"])
                self.assertFalse(replay["actor_completion_published"])
                self.assertEqual(self.f.files(), before)
            self.assertEqual(self.f.native.calls, 1)

    def test_actual_pause_before_first_domain_write_blocks_original_resume(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(recovery, "_execute_core", side_effect=OSError("synthetic prewriter cut")):
                with self.assertRaises(recovery.LocalRecoveryError):
                    self.execute(held)
            original = self.retained()
            self.assertTrue(recovery.verify_local_recovery_state(original, state="pre")["all_match"])
            paused = registry.plan_transition(self.f.store.read(), action="pause",
                client_app_ref=self.f.app, work_session_ref=self.f.session, claim_ref=self.f.claim_ref)
            self.f.store.commit(paused, held_lock=held)
            before = self.f.files()
            with patch.object(recovery._Writer, "write_field", side_effect=AssertionError("paused writer")):
                with self.assertRaises(recovery.LocalRecoveryError):
                    self.resume(held)
            self.assertEqual(self.f.files(), before)

    def test_field_final_before_index_completion_resumes_index_without_rewriting_title(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(recovery.ZettelIndexBatchLifecycle, "finalize",
                              side_effect=OSError("synthetic index finalization cut")):
                interrupted = self.execute(held)
            self.assertFalse(interrupted["ok"], interrupted)
            self.assertTrue(interrupted["index_rebuild_required"])
            original = self.retained()
            self.assertTrue(recovery.verify_local_recovery_state(original, state="post")["all_match"])
            self.assertIsNotNone(self.f.routing._read(current=False).pending_operation())
            with patch.object(recovery._Writer, "write_field", side_effect=AssertionError("duplicate title")), \
                 patch.object(recovery, "_execute_core", side_effect=AssertionError("exact final already exists")):
                resumed = self.resume(held)
            self.assertTrue(resumed["ok"], resumed)
            self.assertEqual(resumed["started_resume_state"], "common_final_present")
            self.assertTrue(resumed["index_current"])
            self.assertFalse(resumed["index_rebuild_required"])
            self.assertTrue(archive_services.require_current_zettel_index(self.root)["ok"])
            self.assertIsNone(self.f.routing._read(current=False).pending_operation())
            self.assertEqual(self.f.native.calls, 1)

    def test_changed_control_in_progress_callback_stops_before_title_or_index_write(self):
        before_title = (self.root / "zettels" / (recovery_fixture.ZETTEL_ID + ".md")).read_bytes()
        changed = []

        def progress(event):
            if event.stage == "preflight" and not changed:
                original = self.retained()
                path = self.root / recovery._control_relative(original.manifest.manifest_sha256)
                path.write_bytes(path.read_bytes() + b" ")
                changed.append(True)

        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(recovery._Writer, "write_field", side_effect=AssertionError("changed original")):
                with self.assertRaises(recovery.LocalRecoveryError):
                    self.execute(held, progress_hook=progress)
            self.assertEqual(changed, [True])
            self.assertEqual((self.root / "zettels" / (recovery_fixture.ZETTEL_ID + ".md")).read_bytes(), before_title)
            self.assertTrue(archive_services.require_current_zettel_index(self.root)["ok"])
            self.assertIsNotNone(self.f.routing._read(current=False).pending_operation())

    def test_legacy_entry_points_cannot_reapprove_or_resume_a_scoped_plan(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            plan = subject._prepare_local_recovery_session_held(self.root, self.factory, **self.options(held))
            recovery.persist_local_recovery_control(plan)
            loaded = recovery.load_local_recovery_plan(self.root, manifest_sha256=plan.manifest.manifest_sha256)
            before = self.f.files()
            with patch.object(recovery, "_execute_exact_human_approved_write", side_effect=AssertionError("legacy approval")), \
                 patch.object(recovery, "_resume_exact_human_approved_write_core", side_effect=AssertionError("legacy resume")):
                for candidate in (loaded, replace(loaded, session_context=None)):
                    with self.assertRaises(recovery.LocalRecoveryError):
                        recovery.execute_local_recovery(candidate, reviewer_claim=subject._view(loaded).context.reviewer_claim)
                    with self.assertRaises(recovery.LocalRecoveryError):
                        recovery.resume_local_recovery(candidate, key_provider=self.f.key)
            self.assertEqual(self.f.files(), before)

    def test_native_approval_shows_count_first_target_preview_and_legacy_facade_still_works(self):
        from test_v0420_work_session_execution import SessionNative
        from wom_kit.target_collection_preview import TARGET_COLLECTION_PAGE_SIZE
        paged = SessionNative()
        plan = self.factory()
        self.assertIsNotNone(recovery.local_recovery_target_collection(plan))
        self.assertEqual(recovery.local_recovery_target_collection(plan).count, 1)
        observe = recovery.local_recovery_observe_target_binding(plan, mode="apply")
        self.assertEqual(observe(), recovery._binding(plan, mode="apply").target_binding_sha256)
        with exact.ExactOperationWriterLock(self.root) as held:
            result = subject._execute_session_local_recovery_held(self.root, self.factory,
                **self.options(held), native=paged)
            self.assertTrue(result["ok"], result)
        self.assertEqual(paged.calls, 1)
        self.assertEqual(paged.main, ["대상 1개"])
        page = paged.pages[0]
        frontmatter = archive_services.require_readable_zettel_text(
            archive_services.decode_utf8_with_universal_newlines(
                (self.root / "zettels" / (recovery_fixture.ZETTEL_ID + ".md")).read_bytes()))[0]
        self.assertNotIn(frontmatter["title"], page)  # the post title is not the current label
        self.assertIn("1. Fake thought while eating alone", page)  # the pre title labels the page
        self.assertNotIn("zettels/", page)  # no path is shown
        self.assertEqual(TARGET_COLLECTION_PAGE_SIZE, 20)
        # The legacy show-only facade used by other fixtures still approves.
        self.assertEqual(self.f.native.calls, 0)
        with self.assertRaises(recovery.LocalRecoveryError):
            observe()  # the pre state no longer holds after the recovery

    def test_legacy_title_apply_and_revert_pass_the_real_boundary_with_the_preview(self):
        from test_local_recovery_execution import _ApproveNative, _StableKeyProvider
        from wom_kit.exact_human_approval_workflow import _execute_exact_human_approved_write_core
        native, keys = _ApproveNative(), _StableKeyProvider()

        def approved_workflow(archive_root, context, writer, **preview):
            return _execute_exact_human_approved_write_core(archive_root, context, writer,
                native=native, key_provider=keys, **preview)

        plan = self.factory()
        with patch.object(recovery, "_execute_exact_human_approved_write", new=approved_workflow):
            applied = recovery.execute_local_recovery(plan, reviewer_claim="person:legacy")
            self.assertTrue(applied["ok"], applied)
            loaded = recovery.load_local_recovery_plan(self.root, manifest_sha256=plan.manifest.manifest_sha256)
            self.assertTrue(recovery.verify_local_recovery_state(loaded, state="post")["all_match"])
            # The revert observer must accept the post state the revert starts from.
            observe = recovery.local_recovery_observe_target_binding(loaded, mode="revert")
            self.assertEqual(observe(), recovery._binding(loaded, mode="revert").target_binding_sha256)
            reverted = recovery.execute_local_recovery(loaded, mode="revert", reviewer_claim="person:legacy")
            self.assertTrue(reverted["ok"], reverted)
            self.assertTrue(recovery.verify_local_recovery_state(loaded, state="pre")["all_match"])
        self.assertEqual(native.calls, 2)


    def test_review_options_keep_the_plain_dialog_for_plans_without_zettel_targets(self):
        from wom_kit.target_collection_preview import TargetCollectionPreview
        plan = self.factory()
        options = recovery.local_recovery_review_options(plan, mode="apply")
        self.assertEqual(sorted(options), ["observe_target_binding", "target_collection"])
        self.assertIs(type(options["target_collection"]), TargetCollectionPreview)
        self.assertEqual(options["observe_target_binding"](),
                         recovery._binding(plan, mode="apply").target_binding_sha256)
        # A caller-supplied observer wraps the plan's own instead of being replaced.
        sentinel = lambda: "sentinel"
        self.assertIs(recovery.local_recovery_review_options(plan, mode="apply",
                      observe_target_binding=sentinel)["observe_target_binding"], sentinel)
        # Ledger and locator plans have no canonical zettel targets: no preview, no
        # observer, so the approval core shows the plain dialog instead of refusing
        # an observer without a collection (the v0.4.20 installed-wheel gate caught
        # the locator apply failing with exact_human_approval_operation_failed).
        with patch.object(recovery, "local_recovery_target_collection", return_value=None):
            self.assertEqual(recovery.local_recovery_review_options(plan, mode="apply"), {})
        with self.assertRaises(recovery.LocalRecoveryError):
            recovery.local_recovery_review_options(plan, mode="preview")


if __name__ == "__main__":
    unittest.main()
