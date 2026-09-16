"""Current writer ownership is a prerequisite, never human approval.

Synthetic registry setup uses an explicit test authority callback only to
construct lifecycle states. The checked guard performs no approval or write;
all lock checks use the real archive-wide OS lock and real private snapshots.
"""

from dataclasses import FrozenInstanceError, replace
import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from wom_kit import exact_human_approval as approval
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_registry as registry
from wom_kit.work_session_binding import WorkSessionBinding


ARCHIVE_ID = "archive:personal:synthetic-current-scope"


class CurrentSessionScopeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="wom-current-session-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        self.root.mkdir()
        (self.root / "archive.yml").write_text("archive_id: " + ARCHIVE_ID + "\n", encoding="utf-8")
        self.store = registry.WorkSessionRegistryStore(
            self.root, approval.exact_human_approval_archive_identity_sha256(ARCHIVE_ID))
        self.app = self.commit(action="register-app", label="Synthetic private app").result_refs[0]
        self.other_app = self.commit(action="register-app", label="Synthetic other app").result_refs[0]
        started = self.commit(action="create", client_app_ref=self.app, label="Synthetic private workstream")
        self.session = started.result_refs[-1]
        self.commit(action="claim", client_app_ref=self.app, work_session_ref=self.session)
        self.claim = self.store.read()._document["sessions"][self.session]["claim_ref"]
        self.expected = self.store.read().binding(self.session)

    def commit(self, **request):
        planned = registry.plan_transition(self.store.read(), **request)
        with exact.ExactOperationWriterLock(self.root) as held:
            self.store.commit(planned, held_lock=held,
                              verify_human_authority=lambda digest: digest == planned.plan_sha256)
        return planned

    def files(self):
        result = {}
        lock_path = self.root / exact.EXACT_OPERATION_LOCAL_ROOT / ".writer.lock"
        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            if path == lock_path:
                # Windows' real byte-range lock correctly denies an unrelated
                # descriptor read. Record its exact identity here; the guard's
                # verify_held reads bytes through the actual lock descriptor.
                info = path.stat()
                value = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
            else:
                value = path.read_bytes()
            result[path.relative_to(self.root).as_posix()] = value
        return result

    def check(self, held, **overrides):
        options = dict(client_app_ref=self.app, work_session_ref=self.session, claim_ref=self.claim,
                       held_lock=held, expected_binding=self.expected)
        options.update(overrides)
        return self.store.require_claimed_binding(**options)

    def assert_rejected_without_writes(self, call, code=None):
        before = self.files()
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            with self.assertRaises(registry.WorkSessionRegistryError) as caught:
                call()
        error = caught.exception
        self.assertIn(str(error), registry._ERRORS)
        if code is not None:
            self.assertEqual(str(error), code)
        self.assertIsNone(error.__context__)
        self.assertIsNone(error.__cause__)
        for private in ("Synthetic", self.app, self.session, self.claim, str(self.root)):
            self.assertNotIn(private, repr(error))
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(self.files(), before)

    def test_current_owner_returns_detached_immutable_binding_without_writes(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            before = self.files()
            for expected in (None, self.expected):
                with self.subTest(expected=expected is not None):
                    binding = self.check(held, expected_binding=expected)
                    self.assertIs(type(binding), WorkSessionBinding)
                    self.assertEqual(binding, self.expected)
                    self.assertIsNot(binding, self.expected)
                    with self.assertRaises(FrozenInstanceError):
                        binding.revision = 99
            held.verify_held()
            self.assertEqual(self.files(), before)
        self.assertFalse((self.root / "receipts").exists())
        self.assertFalse((self.root / "profiles/local/exact-human-approvals").exists())

    def test_wrong_type_unheld_released_and_foreign_os_lock_are_refused(self):
        unheld = exact.ExactOperationWriterLock(self.root)
        with exact.ExactOperationWriterLock(self.root) as released:
            released.verify_held()
        for invalid in (None, True, object(), unheld, released):
            with self.subTest(kind=type(invalid).__name__):
                self.assert_rejected_without_writes(lambda: self.check(invalid), "work_session_lock_required")
        other = self.root.parent / "other-archive"
        other.mkdir()
        (other / "archive.yml").write_text("archive_id: archive:personal:synthetic-other\n", encoding="utf-8")
        with exact.ExactOperationWriterLock(other) as foreign:
            self.assert_rejected_without_writes(lambda: self.check(foreign), "work_session_lock_required")

    def test_wrong_app_claim_and_absent_session_do_not_admit_a_writer(self):
        cases = ({"client_app_ref": self.other_app}, {"claim_ref": "claim_" + "0" * 32},
                 {"work_session_ref": "work_session_" + "0" * 32})
        with exact.ExactOperationWriterLock(self.root) as held:
            for case in cases:
                with self.subTest(field=next(iter(case))):
                    self.assert_rejected_without_writes(lambda: self.check(held, **case))

    def test_malformed_refs_and_binding_fail_without_private_error_values(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            for field in ("client_app_ref", "work_session_ref", "claim_ref"):
                for invalid in (None, True, [], "Synthetic private value", str(self.root)):
                    with self.subTest(field=field, kind=type(invalid).__name__):
                        self.assert_rejected_without_writes(lambda: self.check(held, **{field: invalid}),
                                                            "work_session_registry_invalid")
            for expected in ({}, self.expected.document(), True):
                self.assert_rejected_without_writes(lambda: self.check(held, expected_binding=expected),
                                                    "work_session_registry_invalid")
            forged = replace(self.expected)
            object.__setattr__(forged, "revision", forged.revision + 1)
            self.assert_rejected_without_writes(lambda: self.check(held, expected_binding=forged),
                                                "work_session_registry_invalid")

    def test_created_paused_completed_and_handoff_states_cannot_write(self):
        # Give every state its own legal lifecycle without rewriting history.
        for state in ("created", "paused", "completed", "handoff_pending", "handed_off"):
            with self.subTest(state=state):
                planned = self.commit(action="create", client_app_ref=self.app, label="Synthetic separate workstream")
                session = planned.result_refs[-1]
                claim = "claim_" + "1" * 32
                if state != "created":
                    self.commit(action="claim", client_app_ref=self.app, work_session_ref=session)
                    claim = self.store.read()._document["sessions"][session]["claim_ref"]
                    action = {"paused": "pause", "completed": "complete",
                              "handoff_pending": "handoff", "handed_off": "handoff"}[state]
                    request = dict(action=action, client_app_ref=self.app, work_session_ref=session, claim_ref=claim)
                    if action == "handoff":
                        request["target_app_ref"] = self.other_app
                    self.commit(**request)
                    if state == "handed_off":
                        self.commit(action="accept", client_app_ref=self.other_app, work_session_ref=session)
                with exact.ExactOperationWriterLock(self.root) as held:
                    self.assert_rejected_without_writes(lambda: self.check(
                        held, work_session_ref=session, claim_ref=claim, expected_binding=None),
                        "work_session_claim_conflict")

    def test_pause_resume_rotates_claim_and_invalidates_old_session_revision(self):
        self.commit(action="pause", client_app_ref=self.app, work_session_ref=self.session, claim_ref=self.claim)
        self.commit(action="resume", client_app_ref=self.app, work_session_ref=self.session)
        new_claim = self.store.read()._document["sessions"][self.session]["claim_ref"]
        self.assertNotEqual(new_claim, self.claim)
        with exact.ExactOperationWriterLock(self.root) as held:
            self.assert_rejected_without_writes(lambda: self.check(held), "work_session_claim_conflict")
            self.assert_rejected_without_writes(lambda: self.check(held, claim_ref=new_claim),
                                                "work_session_registry_changed")
            current = self.check(held, claim_ref=new_claim, expected_binding=None)
            self.assertGreater(current.revision, self.expected.revision)

    def test_recover_rotates_claim_even_when_app_and_workstream_are_same(self):
        self.commit(action="recover", client_app_ref=self.app, work_session_ref=self.session)
        new_claim = self.store.read()._document["sessions"][self.session]["claim_ref"]
        with exact.ExactOperationWriterLock(self.root) as held:
            self.assert_rejected_without_writes(lambda: self.check(held), "work_session_claim_conflict")
            self.assert_rejected_without_writes(lambda: self.check(held, claim_ref=new_claim),
                                                "work_session_registry_changed")

    def test_unrelated_registry_generation_preserves_scope_binding(self):
        before_revision = self.store.read().revision
        self.commit(action="register-app", label="Synthetic unrelated installation")
        other = self.commit(action="create", client_app_ref=self.other_app, label="Synthetic unrelated workstream")
        self.commit(action="claim", client_app_ref=self.other_app, work_session_ref=other.result_refs[-1])
        self.assertGreater(self.store.read().revision, before_revision)
        with exact.ExactOperationWriterLock(self.root) as held:
            self.assertEqual(self.check(held), self.expected)

    def test_archive_marker_drift_or_lying_store_digest_is_refused(self):
        marker = self.root / "archive.yml"
        marker.write_text("archive_id: archive:personal:synthetic-changed\n", encoding="utf-8")
        with exact.ExactOperationWriterLock(self.root) as held:
            self.assert_rejected_without_writes(lambda: self.check(held), "work_session_registry_changed")
        marker.write_text("archive_id: " + ARCHIVE_ID + "\n", encoding="utf-8")
        self.store.archive_identity_sha256 = "sha256:" + "0" * 64
        with exact.ExactOperationWriterLock(self.root) as held:
            self.assert_rejected_without_writes(lambda: self.check(held), "work_session_registry_changed")

    def test_expected_binding_covers_archive_session_revision_and_both_labels(self):
        basis = self.expected.document()
        basis.pop("schema")
        basis.pop("binding_sha256")
        for field in ("archive_identity_sha256", "client_app_label_sha256", "workstream_label_sha256", "revision"):
            with self.subTest(field=field):
                changed = dict(basis)
                changed[field] = self.expected.revision + 1 if field == "revision" else "sha256:" + "f" * 64
                expected = WorkSessionBinding.build(**changed)
                with exact.ExactOperationWriterLock(self.root) as held:
                    self.assert_rejected_without_writes(lambda: self.check(held, expected_binding=expected),
                                                        "work_session_registry_changed")

    def test_native_wait_scope_drift_is_detected_by_rechecking_expected_binding(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            observed = self.check(held)
            transition = registry.plan_transition(self.store.read(), action="pause", client_app_ref=self.app,
                                                  work_session_ref=self.session, claim_ref=self.claim)
            self.store.commit(transition, held_lock=held)
            self.assert_rejected_without_writes(lambda: self.check(held, expected_binding=observed),
                                                "work_session_claim_conflict")

    def test_final_observation_rejects_changed_claim_but_allows_unrelated_generation(self):
        original_read = self.store.read
        for unrelated in (True, False):
            with self.subTest(unrelated=unrelated), exact.ExactOperationWriterLock(self.root) as held:
                injected = []

                def read_then_change():
                    snapshot = original_read()
                    if not injected:
                        injected.append(True)
                        if unrelated:
                            transition = registry.plan_transition(snapshot, action="register-app", label="Synthetic racing app")
                        else:
                            transition = registry.plan_transition(snapshot, action="pause", client_app_ref=self.app,
                                                                  work_session_ref=self.session, claim_ref=self.claim)
                        self.store.commit(transition, held_lock=held)
                    return snapshot

                with mock.patch.object(self.store, "read", side_effect=read_then_change):
                    if unrelated:
                        self.assertEqual(self.check(held), self.expected)
                    else:
                        with self.assertRaisesRegex(registry.WorkSessionRegistryError, "^work_session_claim_conflict$"):
                            self.check(held)
                self.assertEqual(injected, [True])

    def test_sensitive_lower_reader_error_is_not_retained_or_printed(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            for failure in (OSError("Synthetic private path " + str(self.root)),
                            ValueError("Synthetic private claim " + self.claim)):
                with mock.patch.object(self.store, "read", side_effect=failure):
                    self.assert_rejected_without_writes(lambda: self.check(held))

    def test_expected_binding_is_detached_before_reader_observation(self):
        original = self.expected
        supplied = replace(original)
        real_read = self.store.read

        def read_and_change_caller_view():
            snapshot = real_read()
            object.__setattr__(supplied, "revision", original.revision + 1)
            return snapshot

        with exact.ExactOperationWriterLock(self.root) as held:
            before = self.files()
            with mock.patch.object(self.store, "read", side_effect=read_and_change_caller_view):
                self.assertEqual(self.check(held, expected_binding=supplied), original)
            self.assertEqual(self.files(), before)

    def test_archive_marker_changed_during_observation_is_refused_at_final_barrier(self):
        real_read = self.store.read
        injected = []
        marker = self.root / "archive.yml"
        changed_marker = b"archive_id: archive:personal:synthetic-racing-marker\n"

        def read_and_change_marker():
            snapshot = real_read()
            if not injected:
                injected.append(True)
                marker.write_bytes(changed_marker)
            return snapshot

        with exact.ExactOperationWriterLock(self.root) as held:
            before = self.files()
            with mock.patch.object(self.store, "read", side_effect=read_and_change_marker):
                with self.assertRaisesRegex(registry.WorkSessionRegistryError, "^work_session_registry_changed$") as caught:
                    self.check(held)
            self.assertIsNone(caught.exception.__context__)
            self.assertEqual(self.files(), {**before, "archive.yml": changed_marker})
            self.assertEqual(injected, [True])

    def test_redirected_private_path_is_rejected_before_snapshot_read(self):
        original = self.store.path
        self.store.path = self.root.parent / "synthetic-outside"
        try:
            with exact.ExactOperationWriterLock(self.root) as held, mock.patch.object(
                self.store, "read", side_effect=AssertionError("redirected path read")):
                self.assert_rejected_without_writes(lambda: self.check(held), "work_session_path_unsafe")
        finally:
            self.store.path = original

    def test_historical_binding_and_read_do_not_require_current_claim(self):
        original = self.expected.document()
        self.commit(action="pause", client_app_ref=self.app, work_session_ref=self.session, claim_ref=self.claim)
        before = self.files()
        snapshot = self.store.read()
        self.assertEqual(snapshot._document["sessions"][self.session]["state"], "paused")
        historical_projection = snapshot.binding(self.session)
        self.assertEqual(historical_projection.work_session_ref, self.expected.work_session_ref)
        self.assertEqual(self.expected.document(), original)
        self.assertEqual(self.files(), before)


if __name__ == "__main__":
    unittest.main()
