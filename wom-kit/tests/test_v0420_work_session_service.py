"""Public SDK flow: actual guards/locks/runners; only native/key input is fake."""

from contextlib import contextmanager
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as workflow
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_actor as actor
from wom_kit import work_session_operation as operation
from wom_kit import work_session_registration as registration
from wom_kit import work_session_registry as registry
from wom_kit import work_session_registry_intent as intents
from wom_kit import work_session_service as subject
import test_v0420_work_session_execution as fixture


LABEL = "Synthetic private service label"


class WorkSessionServiceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="wom-session-service-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        self.root.mkdir()
        archive_id = "archive:personal:synthetic-session-service"
        (self.root / "archive.yml").write_text("archive_id: " + archive_id + "\n", encoding="utf-8")
        self.store = registry.WorkSessionRegistryStore(
            self.root, approval.exact_human_approval_archive_identity_sha256(archive_id))
        self.native, self.key = fixture.SessionNative(), fixture._Key()
        # Use the original public facade defaults, not public/native/key args.
        native_patch = patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native)
        self.native_factory = native_patch.start()
        self.addCleanup(native_patch.stop)
        key_patch = patch.object(workflow, "_production_key_provider", return_value=self.key)
        self.key_factory = key_patch.start()
        self.addCleanup(key_patch.stop)
        self.route = actor.new_task_route_ref()

    def files(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file() and path.name != ".writer.lock"}

    def register(self):
        selected = subject.preview_registration(self.root, label=LABEL)
        result = subject.apply_or_resume_registration(self.root, selection=selected, label=LABEL)
        self.app = result["client_app_ref"]
        return selected, result

    def create(self, **changes):
        arguments = dict(client_app_ref=self.app, task_route_ref=self.route, label=LABEL,
                         reviewer_claim="person:synthetic-service-reviewer")
        arguments.update(changes)
        return subject.create_task(self.root, **arguments)

    def resume(self):
        return subject.resume_task_create(self.root, client_app_ref=self.app, task_route_ref=self.route)

    def rereview(self):
        return subject.review_original_task_create(self.root, client_app_ref=self.app, task_route_ref=self.route)

    def claim(self, session):
        return subject.apply_or_resume_task_claim(
            self.root, client_app_ref=self.app, task_route_ref=self.route, work_session_ref=session)

    def reject(self, call, code=None, *, committed=False):
        with self.assertRaises(subject.WorkSessionServiceError) as caught:
            call()
        error = caught.exception
        if code is not None:
            self.assertEqual(error.code, code)
        self.assertEqual(error.original_commit_verified, committed)
        self.assertIsNone(error.__context__)
        self.assertIsNone(error.__cause__)
        for marker in (LABEL, str(self.root), "private_error_marker"):
            self.assertNotIn(marker, repr(error))

    def test_public_signatures_exclude_authority_and_unsupported_actions(self):
        expected = {"preview_registration", "initialize_task_request", "apply_or_resume_registration", "create_task", "resume_task_create",
                    "review_original_task_create", "apply_or_resume_task_claim", "transition_task_state"}
        self.assertEqual(set(subject.__all__), expected | {"WorkSessionServiceError"})
        forbidden = {"native", "key_provider", "context", "approval_id", "claim_ref", "manifest_sha256",
                     "running_version", "running_module_path", "running_archive_cli_module_path", "dry_run"}
        for name in expected:
            with self.subTest(name=name):
                signature = inspect.signature(getattr(subject, name))
                self.assertFalse(forbidden & set(signature.parameters))
                self.assertFalse(any(p.kind == p.VAR_KEYWORD for p in signature.parameters.values()))

    def test_read_only_preview_and_real_full_registration_create_claim_flow(self):
        before = self.files()
        with patch.object(subject, "wait_for_archive_writer", side_effect=AssertionError("preview locked")), \
                patch.object(subject.project_runtime, "project_write_guard", side_effect=AssertionError("preview guarded")):
            selected = subject.preview_registration(self.root, label=LABEL)
        self.assertEqual(self.files(), before)
        self.assertFalse((self.root / "profiles").exists())
        waits = []
        original_wait = subject.wait_for_archive_writer
        original_guard = subject.project_runtime.project_write_guard

        @contextmanager
        def counted_wait(*args, **kwargs):
            with original_wait(*args, **kwargs) as held:
                waits.append(held)
                yield held

        def observed_guard(*args, **kwargs):
            self.assertIsNone(waits[-1].verify_held())
            self.assertEqual(kwargs["running_module_path"], Path(subject.__file__))
            self.assertIsNone(kwargs["running_archive_cli_module_path"])
            return original_guard(*args, **kwargs)

        with patch.object(subject, "wait_for_archive_writer", new=counted_wait), \
                patch.object(subject.project_runtime, "project_write_guard", new=observed_guard):
            registered = subject.apply_or_resume_registration(self.root, selection=selected, label=LABEL)
            self.app = registered["client_app_ref"]
            before = self.files()
            replayed_registration = subject.apply_or_resume_registration(self.root, selection=selected, label=LABEL)
            self.assertEqual(self.files(), before)
            created = self.create()
            before = self.files()
            continued = self.resume()
            self.assertEqual(self.files(), before)
            self.assertEqual(continued["receipt_sha256"], created["receipt_sha256"])
            session = created["work_session_binding"]["work_session_ref"]
            claimed = self.claim(session)
            before = self.files()
            continued_claim = self.claim(session)
            self.assertEqual(self.files(), before)
        self.assertEqual(len(waits), 6)
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.store.read().revision, 3)
        self.assertTrue(registered["ok"] and registered["identity_level"] == "self_declared")
        self.assertFalse(registered["routing_is_write_authority"])
        self.assertTrue(created["independent_post_verification"] and created["claim_required"])
        self.assertTrue(claimed["current_claim_authority_evaluated"])
        self.assertEqual(continued_claim["plan_sha256"], claimed["plan_sha256"])
        public = json.dumps([selected, registered, replayed_registration, created, continued, claimed, continued_claim])
        for marker in (LABEL, str(self.root), "person:synthetic-service-reviewer"):
            self.assertNotIn(marker, public)
        private = actor.WorkSessionActorStore(self.store, client_app_ref=self.app, task_route_ref=self.route).read().document()
        self.assertNotIn(private["claim_ref"], public)

    def test_invalid_inputs_are_refused_before_wait_without_private_errors(self):
        self.register()
        before = self.files()
        cases = [lambda: self.create(client_app_ref=None), lambda: self.create(task_route_ref=True),
                 lambda: self.create(label={"private_error_marker": LABEL}),
                 lambda: self.create(reviewer_claim="private_error_marker"),
                 lambda: self.claim(None), lambda: self.claim("private_error_marker"),
                 lambda: subject.apply_or_resume_registration(self.root, selection={"native": LABEL}, label=LABEL)]
        with patch.object(subject, "wait_for_archive_writer", side_effect=AssertionError("invalid input waited")) as waiting:
            for call in cases:
                with self.subTest(case=cases.index(call)):
                    self.reject(call)
            waiting.assert_not_called()
        self.assertEqual(self.files(), before)
        self.assertEqual(self.native.calls, 0)

    def test_state_modes_reject_invalid_authority_inputs_before_lock_or_writer(self):
        arguments = dict(action="pause", original_resume=False, client_app_ref="client_app:" + "a" * 32,
                         task_route_ref="task_route:" + "b" * 32, work_session_ref="work_session:" + "c" * 32)
        before = self.files()
        with patch.object(subject, "wait_for_archive_writer", side_effect=AssertionError("invalid input waited")) as waiting:
            for changes in ({"action": "handoff"}, {"action": True}, {"original_resume": 1},
                            {"client_app_ref": None}, {"task_route_ref": []}, {"work_session_ref": None}):
                with self.subTest(changes=tuple(changes)):
                    self.reject(lambda: subject.transition_task_state(self.root, **{**arguments, **changes}))
            waiting.assert_not_called()
        self.assertEqual(self.files(), before)

    def test_all_state_modes_keep_runtime_and_cancellation_guards_before_facade(self):
        self.register()
        session = self.create()["work_session_binding"]["work_session_ref"]
        self.claim(session)
        before = self.files()
        selected = dict(client_app_ref=self.app, task_route_ref=self.route, work_session_ref=session)
        with patch.object(subject.session_state, "_transition_task_held", side_effect=AssertionError("blocked facade")) as facade:
            for action in ("pause", "resume", "complete"):
                for original_resume in (False, True):
                    with self.subTest(action=action, original_resume=original_resume):
                        arguments = dict(action=action, original_resume=original_resume, **selected)
                        self.reject(lambda: subject.transition_task_state(self.root, **arguments,
                            cancel_requested=lambda: True), "work_session_wait_cancelled")
                        with patch.object(subject.project_runtime, "project_write_guard", return_value={
                                "blocked": True, "reason_code": "project_runtime_mismatch"}):
                            self.reject(lambda: subject.transition_task_state(self.root, **arguments), "project_runtime_mismatch")
            facade.assert_not_called()
        self.assertEqual(self.files(), before)
        self.assertEqual(self.native.calls, 1)

    def test_runtime_pin_created_during_wait_blocks_before_any_writer_or_native(self):
        self.register()
        before = self.files()

        def progress(event):
            if event["stage"] == "writer_acquired_revalidation_required":
                metadata = self.root.parent / ".zettel-kasten"
                metadata.mkdir()
                (metadata / "installed-version.txt").write_text("v9.9.9\n", encoding="utf-8")

        with patch.object(operation, "prepare_session_decision", side_effect=AssertionError("blocked plan")) as planner:
            self.reject(lambda: self.create(progress=progress), "project_runtime_mismatch")
            planner.assert_not_called()
        self.assertEqual(self.files(), before)
        self.assertEqual(self.native.calls, 0)
        self.key_factory.assert_not_called()

    def test_guard_unavailable_or_malformed_never_authorizes_write_and_never_echoes(self):
        selected = subject.preview_registration(self.root, label=LABEL)
        before = self.files()
        cases = [{"blocked": True, "reason_code": "project_runtime_unavailable"},
                 {"blocked": True, "reason_code": "private_error_marker"}, {"blocked": 0}, {},
                 {"blocked": False, "reason_code": "private_error_marker"},
                 {"blocked": False, "reason_code": []},
                 {"blocked": False, "reason_code": "project_runtime_version_aligned", "runtime_inspection_state": "unavailable"},
                 {"blocked": False, "reason_code": "project_runtime_version_aligned", "runtime_inspection_state": []}]
        for guard in cases:
            with self.subTest(guard=cases.index(guard)), \
                    patch.object(subject.project_runtime, "project_write_guard", return_value=guard), \
                    patch.object(intents, "save_registry_intent", side_effect=AssertionError("blocked intent")) as save:
                self.reject(lambda: subject.apply_or_resume_registration(self.root, selection=selected, label=LABEL),
                            "project_runtime_unavailable")
                save.assert_not_called()
        with patch.object(subject.project_runtime, "project_write_guard", side_effect=OSError("private_error_marker")):
            self.reject(lambda: subject.apply_or_resume_registration(self.root, selection=selected, label=LABEL),
                        "work_session_service_unavailable")
        self.assertEqual(self.files(), before)

    def test_selection_is_detached_before_wait_progress_can_change_original_dict(self):
        selected = subject.preview_registration(self.root, label=LABEL)
        original_app = selected["client_app_ref"]

        def progress(_event):
            selected["client_app_ref"] = registry._new_ref("client_app")
            selected["private_error_marker"] = LABEL

        result = subject.apply_or_resume_registration(self.root, selection=selected, label=LABEL, progress=progress)
        self.assertEqual(result["client_app_ref"], original_app)
        self.assertEqual(set(self.store.read()._document["apps"]), {original_app})

    def test_cancellation_and_callback_exception_never_create_registration(self):
        selected = subject.preview_registration(self.root, label=LABEL)
        before = self.files()
        self.reject(lambda: subject.apply_or_resume_registration(self.root, selection=selected, label=LABEL,
                    cancel_requested=lambda: True), "work_session_wait_cancelled")

        def broken(_event):
            raise OSError("private_error_marker")

        self.reject(lambda: subject.apply_or_resume_registration(self.root, selection=selected, label=LABEL,
                    progress=broken), "work_session_service_unavailable")
        self.assertEqual(self.files(), before)
        self.assertEqual(self.store.read().revision, 0)

    def test_started_original_resume_and_present_rereview_never_open_new_native(self):
        self.register()
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=OSError("private_error_marker")):
            self.reject(self.create)
        routing = actor.WorkSessionActorStore(self.store, client_app_ref=self.app, task_route_ref=self.route)
        selected = routing.read().document()
        self.assertIsNotNone(selected["pending_manifest_sha256"])
        self.assertEqual(self.native.calls, 1)
        with patch.object(windows, "_CtypesTaskDialogNative", side_effect=AssertionError("resume opened native")):
            result = self.resume()
            before = self.files()
            replay = self.rereview()
        self.assertTrue(result["ok"] and replay["ok"])
        self.assertFalse(replay["native_approval_redisplayed"])
        self.assertEqual(self.files(), before)
        self.assertEqual(self.store.read().revision, 2)

    def test_preclaim_cut_cancel_and_explicit_original_rereview_use_one_original(self):
        self.register()
        original_save = actor.WorkSessionActorStore.save

        def cut(store, **kwargs):
            result = original_save(store, **kwargs)
            if kwargs.get("pending_manifest_sha256") is not None:
                raise OSError("private_error_marker")
            return result

        with patch.object(actor.WorkSessionActorStore, "save", new=cut):
            self.reject(self.create)
        before = self.files()
        self.assertEqual(self.store.read().revision, 1)
        self.native.approve = False
        self.reject(self.rereview, "exact_human_approval_cancelled")
        self.assertEqual(self.files(), before)
        self.native.approve = True
        with patch.object(registry, "_new_ref", side_effect=AssertionError("rereview regenerated")):
            result = self.rereview()
        self.assertTrue(result["ok"] and result["native_approval_redisplayed"])
        self.assertEqual(self.native.calls, 3)
        before = self.files()
        self.assertEqual(self.resume()["receipt_sha256"], result["receipt_sha256"])
        self.assertEqual(self.files(), before)

    def test_claim_commit_output_loss_resumes_same_claim_and_pause_reports_lost_ownership(self):
        self.register()
        session = self.create()["work_session_binding"]["work_session_ref"]
        original_save = actor.WorkSessionActorStore.save

        def cut(store, **kwargs):
            pointer = kwargs.get("last_completed_operation")
            if pointer is not None and pointer.document()["kind"] == "registry_transition":
                raise OSError("private_error_marker")
            return original_save(store, **kwargs)

        with patch.object(actor.WorkSessionActorStore, "save", new=cut):
            self.reject(lambda: self.claim(session))
        self.assertEqual(self.store.read().revision, 3)
        original_claim = self.store.read()._document["sessions"][session]["claim_ref"]
        with patch.object(registry, "_new_ref", side_effect=AssertionError("claim replay regenerated")):
            result = self.claim(session)
        self.assertEqual(self.store.read()._document["sessions"][session]["claim_ref"], original_claim)
        self.assertTrue(result["current_claim_authority_evaluated"])
        pause = registry.plan_transition(self.store.read(), action="pause", client_app_ref=self.app,
                                          work_session_ref=session, claim_ref=original_claim)
        with exact.ExactOperationWriterLock(self.root) as held:
            self.store.commit(pause, held_lock=held)
        before = self.files()
        with patch.object(registry.WorkSessionRegistryStore, "commit", side_effect=AssertionError("reclaimed")):
            self.reject(lambda: self.claim(session), "work_session_claim_ownership_unavailable", committed=True)
        self.assertEqual(self.files(), before)

    def test_registration_held_seam_requires_original_same_archive_lock(self):
        selected = subject.preview_registration(self.root, label=LABEL)
        before = self.files()
        with self.assertRaises(registration.WorkSessionRegistrationError):
            registration._apply_or_resume_registration_held(self.root, held=None, selection=selected, label=LABEL)
        other = self.root.parent / "other"
        other.mkdir()
        with exact.ExactOperationWriterLock(other) as held:
            with self.assertRaises(registration.WorkSessionRegistrationError):
                registration._apply_or_resume_registration_held(self.root, held=held, selection=selected, label=LABEL)
        self.assertEqual(self.files(), before)


if __name__ == "__main__":
    unittest.main()
