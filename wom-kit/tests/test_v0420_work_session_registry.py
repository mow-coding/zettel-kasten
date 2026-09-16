"""Synthetic private state, real OS lock and durable generation tests."""

from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_registry as registry


ARCHIVE = "sha256:" + "a" * 64


class SessionRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wom-session-registry-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "archive"
        self.root.mkdir()
        self.store = registry.WorkSessionRegistryStore(self.root, ARCHIVE)

    def commit(self, plan, *, approve=False):
        with exact.ExactOperationWriterLock(self.root) as held:
            return self.store.commit(plan, held_lock=held,
                                     verify_human_authority=(lambda digest: digest == plan.plan_sha256) if approve else None)

    def register(self, label="Synthetic app"):
        plan = registry.plan_transition(self.store.read(), action="register-app", label=label)
        self.commit(plan)
        return plan.result_refs[0]

    def create(self, app):
        plan = registry.plan_transition(self.store.read(), action="create", client_app_ref=app, label="Synthetic task")
        self.commit(plan, approve=True)
        return plan.result_refs[-1]

    def claim(self, app, session):
        plan = registry.plan_transition(self.store.read(), action="claim", client_app_ref=app, work_session_ref=session)
        after = self.commit(plan)
        return after._document["sessions"][session]["claim_ref"]

    def test_empty_read_has_no_filesystem_effect(self):
        self.assertEqual(self.store.read().revision, 0)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_malformed_unhashable_values_have_fixed_errors(self):
        for value in ([], {}, {"PRIVATE_SYNTHETIC_VALUE"}, None, True):
            with self.subTest(kind=type(value).__name__):
                with self.assertRaisesRegex(registry.WorkSessionRegistryError, "^work_session_transition_invalid$"):
                    registry.plan_transition(self.store.read(), action=value)
                with self.assertRaisesRegex(registry.WorkSessionRegistryError, "^work_session_registry_invalid$"):
                    self.store.read().binding(value)
        app = self.register()
        session = self.create(app)
        for group, ref, field in (
            ("apps", app, "identity_level"),
            ("sessions", session, "state"),
            ("sessions", session, "client_app_ref"),
            ("sessions", session, "workstream_ref"),
            ("sessions", session, "predecessor_ref"),
        ):
            invalid = deepcopy(self.store.read()._document)
            invalid[group][ref][field] = []
            with self.subTest(field=field):
                with self.assertRaisesRegex(registry.WorkSessionRegistryError, "^work_session_registry_invalid$"):
                    registry.RegistrySnapshot(invalid)

    @unittest.skipUnless(os.name == "nt", "native retained Windows parent")
    def test_pending_write_retains_windows_parent_against_replacement(self):
        plan = registry.plan_transition(self.store.read(), action="register-app", label="Synthetic private label")
        original = registry.durable._write_new
        attempts = []

        def attempt_swap(path, raw, *, within):
            moved = path.parent.with_name("moved-generations")
            with self.assertRaises(OSError):
                path.parent.rename(moved)
            attempts.append(True)
            return original(path, raw, within=within)

        with mock.patch.object(registry.durable, "_write_new", side_effect=attempt_swap):
            after = self.commit(plan)
        self.assertEqual(attempts, [True])
        self.assertEqual(after.sha256, plan.after.sha256)
        self.assertFalse(self.store.path.with_name("moved-generations").exists())

    @unittest.skipIf(os.name == "nt", "descriptor-relative POSIX create")
    def test_pending_write_uses_retained_posix_directory_not_replacement(self):
        self.register()
        plan = registry.plan_transition(self.store.read(), action="register-app", label="Synthetic private label")
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        original = os.open
        swapped = []

        def swap_before_open(path, flags, *args, **kwargs):
            if isinstance(path, str) and path.startswith(".pending_") and not swapped:
                moved = self.store.path.with_name("retained-generations")
                self.store.path.rename(moved)
                self.store.path.symlink_to(outside, target_is_directory=True)
                swapped.append(moved)
            return original(path, flags, *args, **kwargs)

        with mock.patch.object(registry.os, "open", side_effect=swap_before_open):
            with self.assertRaisesRegex(registry.WorkSessionRegistryError, "durability_unknown"):
                self.commit(plan)
        self.assertEqual(len(swapped), 1)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertEqual(len(list(swapped[0].glob(".pending_*"))), 1)
        self.assertFalse((swapped[0] / "000000000002.json").exists())

    def test_two_apps_handoff_preserves_workstream_and_predecessor(self):
        first, second = self.register("Synthetic first"), self.register("Synthetic second")
        session = self.create(first)
        claim = self.claim(first, session)
        before = self.store.read().binding(session)
        handoff = registry.plan_transition(self.store.read(), action="handoff", client_app_ref=first,
                                          work_session_ref=session, claim_ref=claim, target_app_ref=second)
        self.commit(handoff, approve=True)
        with self.assertRaisesRegex(registry.WorkSessionRegistryError, "claim_conflict"):
            registry.plan_transition(self.store.read(), action="pause", client_app_ref=first,
                                     work_session_ref=session, claim_ref=claim)
        accept = registry.plan_transition(self.store.read(), action="accept", client_app_ref=second, work_session_ref=session)
        after = self.commit(accept, approve=True)
        next_session = accept.result_refs[0]
        self.assertEqual(after.binding(next_session).workstream_ref, before.workstream_ref)
        self.assertEqual(after._document["sessions"][next_session]["predecessor_ref"], session)
        self.assertEqual(after._document["sessions"][session]["state"], "handed_off")
        self.assertEqual(before.revision, 2)
        self.assertNotEqual(before.binding_sha256, after.binding(session).binding_sha256)

    def test_duplicate_claim_cas_does_not_replace_first_owner(self):
        app = self.register()
        session = self.create(app)
        initial = self.store.read()
        first = registry.plan_transition(initial, action="claim", client_app_ref=app, work_session_ref=session)
        second = registry.plan_transition(initial, action="claim", client_app_ref=app, work_session_ref=session)
        claimed = self.commit(first)
        with self.assertRaisesRegex(registry.WorkSessionRegistryError, "registry_changed"):
            self.commit(second)
        self.assertEqual(self.store.read().sha256, claimed.sha256)

    def test_start_requires_exact_human_callback(self):
        app = self.register()
        plan = registry.plan_transition(self.store.read(), action="create", client_app_ref=app, label="Synthetic task")
        with self.assertRaisesRegex(registry.WorkSessionRegistryError, "human_authority_required"):
            self.commit(plan)
        self.assertEqual(self.store.read().public_summary()["session_count"], 0)

    def test_pause_resume_and_complete_require_current_claim(self):
        app = self.register()
        session = self.create(app)
        first_claim = self.claim(app, session)
        pause = registry.plan_transition(self.store.read(), action="pause", client_app_ref=app,
                                         work_session_ref=session, claim_ref=first_claim)
        self.commit(pause)
        resume = registry.plan_transition(self.store.read(), action="resume", client_app_ref=app, work_session_ref=session)
        resumed = self.commit(resume)
        with self.assertRaisesRegex(registry.WorkSessionRegistryError, "claim_conflict"):
            registry.plan_transition(resumed, action="complete", client_app_ref=app,
                                     work_session_ref=session, claim_ref=first_claim)
        complete = registry.plan_transition(resumed, action="complete", client_app_ref=app, work_session_ref=session,
                                            claim_ref=resumed._document["sessions"][session]["claim_ref"])
        after = self.commit(complete)
        self.assertEqual(after._document["sessions"][session]["state"], "completed")
        self.assertIsNone(after._document["workstreams"][after.binding(session).workstream_ref]["active_session_ref"])

    def test_recover_never_steals_claim_without_human_decision(self):
        app = self.register()
        session = self.create(app)
        old_claim = self.claim(app, session)
        plan = registry.plan_transition(self.store.read(), action="recover", client_app_ref=app, work_session_ref=session)
        with self.assertRaisesRegex(registry.WorkSessionRegistryError, "human_authority_required"):
            self.commit(plan)
        recovered = self.commit(plan, approve=True)
        self.assertNotEqual(recovered._document["sessions"][session]["claim_ref"], old_claim)

    def test_forged_postimage_cannot_smuggle_human_confirmation(self):
        plan = registry.plan_transition(self.store.read(), action="register-app", label="Synthetic app")
        altered = deepcopy(plan.after._document)
        altered["apps"][plan.result_refs[0]]["identity_level"] = "human_confirmed"
        forged = replace(plan, after=registry.RegistrySnapshot(altered))
        forged = replace(forged, plan_sha256=registry._digest(forged._basis()))
        with self.assertRaisesRegex(registry.WorkSessionRegistryError, "transition_invalid"):
            self.commit(forged)
        self.assertEqual(self.store.read().revision, 0)

    def test_published_generation_after_lost_result_is_readable_not_reapplied(self):
        plan = registry.plan_transition(self.store.read(), action="register-app", label="Synthetic app")
        original = registry.durable._atomic_move_file_no_replace

        def lose_result(*args):
            original(*args)
            raise OSError("synthetic lost result")

        with mock.patch.object(registry.durable, "_atomic_move_file_no_replace", side_effect=lose_result):
            with self.assertRaisesRegex(registry.WorkSessionRegistryError, "durability_unknown"):
                self.commit(plan)
        self.assertEqual(self.store.read().sha256, plan.after.sha256)
        with self.assertRaisesRegex(registry.WorkSessionRegistryError, "registry_changed"):
            self.commit(plan)

    def test_pending_image_is_preserved_and_previous_snapshot_remains_current(self):
        app = self.register()
        before = self.store.read()
        plan = registry.plan_transition(before, action="create", client_app_ref=app, label="Synthetic task")
        with mock.patch.object(registry.durable, "_atomic_move_file_no_replace", side_effect=OSError("synthetic cut")):
            with self.assertRaisesRegex(registry.WorkSessionRegistryError, "durability_unknown"):
                self.commit(plan, approve=True)
        self.assertEqual(self.store.read().sha256, before.sha256)
        self.assertEqual(len(list(self.store.path.glob(".pending_*"))), 1)
        # The identical transition can resume; it does not choose a new session.
        after = self.commit(plan, approve=True)
        self.assertEqual(after.sha256, plan.after.sha256)

    def test_symlink_directory_is_refused_without_following(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        try:
            os.symlink(outside, self.root / "profiles", target_is_directory=True)
        except OSError:
            self.skipTest("symlink creation unavailable on host")
        with self.assertRaisesRegex(registry.WorkSessionRegistryError, "path_unsafe"):
            self.store.read()
        self.assertEqual(list(outside.iterdir()), [])

    def test_cross_archive_and_unheld_locks_are_refused(self):
        plan = registry.plan_transition(self.store.read(), action="register-app", label="Synthetic app")
        lock = exact.ExactOperationWriterLock(self.root)
        with self.assertRaisesRegex(registry.WorkSessionRegistryError, "lock_required"):
            self.store.commit(plan, held_lock=lock)
        other = Path(self.temp.name) / "other"
        other.mkdir()
        with exact.ExactOperationWriterLock(other) as held:
            with self.assertRaisesRegex(registry.WorkSessionRegistryError, "lock_required"):
                self.store.commit(plan, held_lock=held)

    def test_private_names_are_absent_from_repr_and_public_summary(self):
        private = "Synthetic confidential app label"
        self.register(private)
        observed = self.store.read()
        self.assertNotIn(private, repr(observed))
        self.assertNotIn(private, json.dumps(observed.public_summary()))
        self.assertNotIn(str(self.root), repr(self.store))


if __name__ == "__main__":
    unittest.main()
