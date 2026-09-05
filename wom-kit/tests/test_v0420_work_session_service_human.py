"""Public handoff/accept routes retain the real lock, broker and exact writer.

Only the existing native/key input seams are synthetic. Cuts wrap real durable
publication, and continuation is observed through public services, not private
approval identifiers or a caller-supplied claim.
"""

from contextlib import contextmanager, ExitStack
import inspect
import json
import unittest
from unittest.mock import patch

from wom_kit import exact_human_approval as approval
from wom_kit import work_session_actor as actor
from wom_kit import work_session_bundle as bundle
from wom_kit import work_session_execution as execution
from wom_kit import work_session_operation as operation
from wom_kit import work_session_registry as registry
from wom_kit import work_session_service as subject
import test_v0420_work_session_service as fixture


class HumanSessionServiceTests(unittest.TestCase):
    def setUp(self):
        self.task = fixture.WorkSessionServiceTests("runTest")
        self.task.setUp()
        self.addCleanup(self.task.doCleanups)
        t = self.task
        t.register()
        self.session = t.create()["work_session_binding"]["work_session_ref"]
        t.claim(self.session)
        selection = subject.preview_registration(t.root, label="Synthetic receiving service app")
        self.target = subject.apply_or_resume_registration(
            t.root, selection=selection, label="Synthetic receiving service app")["client_app_ref"]
        self.route = subject.initialize_task_request(t.root, client_app_ref=self.target)["task_route_ref"]

    def handoff(self, *, original_resume=False, **changes):
        t = self.task
        arguments = dict(client_app_ref=t.app, task_route_ref=t.route,
                         work_session_ref=self.session, target_app_ref=self.target,
                         original_resume=original_resume,
                         reviewer_claim=None if original_resume else "person:synthetic-service-handoff")
        arguments.update(changes)
        return subject.handoff_task(t.root, **arguments)

    def review_handoff(self, **changes):
        t = self.task
        arguments = dict(client_app_ref=t.app, task_route_ref=t.route,
                         work_session_ref=self.session, target_app_ref=self.target)
        arguments.update(changes)
        return subject.review_original_task_handoff(t.root, **arguments)

    def accept(self, **changes):
        arguments = dict(client_app_ref=self.target, task_route_ref=self.route,
                         predecessor_work_session_ref=self.session,
                         reviewer_claim="person:synthetic-service-accept")
        arguments.update(changes)
        return subject.accept_task(self.task.root, **arguments)

    def resume_accept(self, **changes):
        return subject.resume_task_accept(self.task.root, **{
            "client_app_ref": self.target, "task_route_ref": self.route, **changes})

    def review_accept(self, **changes):
        return subject.review_original_task_accept(self.task.root, **{
            "client_app_ref": self.target, "task_route_ref": self.route, **changes})

    def test_actual_handoff_accept_and_original_observation_use_one_lock_each(self):
        t = self.task
        old_claim = t.store.read()._document["sessions"][self.session]["claim_ref"]
        stream = t.store.read()._document["sessions"][self.session]["workstream_ref"]
        original_wait, original_guard = subject.wait_for_archive_writer, subject.project_runtime.project_write_guard
        waits, guards, progress = [], [], []

        @contextmanager
        def counted_wait(*args, **kwargs):
            with original_wait(*args, **kwargs) as held:
                waits.append(held)
                yield held

        def guarded(*args, **kwargs):
            waits[-1].verify_held()
            guards.append(True)
            return original_guard(*args, **kwargs)

        with patch.object(subject, "wait_for_archive_writer", new=counted_wait), \
                patch.object(subject.project_runtime, "project_write_guard", new=guarded):
            outgoing = self.handoff(progress=progress.append)
            before = t.files()
            continued = self.handoff(original_resume=True, progress=progress.append)
            reviewed = self.review_handoff(progress=progress.append)
            self.assertEqual(t.files(), before)
            accepted = self.accept(progress=progress.append)
            before = t.files()
            original = self.resume_accept(progress=progress.append)
            reread = self.review_accept(progress=progress.append)
            self.assertEqual(t.files(), before)
        self.assertEqual(len(waits), 6)
        self.assertEqual(len(guards), 6)
        self.assertTrue(progress)
        self.assertEqual(t.native.calls, 3)
        self.assertFalse(outgoing["ownership_transferred"])
        self.assertFalse(outgoing["artifact_responsibility_transferred"])
        self.assertEqual(continued["receipt_sha256"], outgoing["receipt_sha256"])
        self.assertFalse(reviewed["native_approval_redisplayed"])
        self.assertTrue(accepted["claim_required"])
        self.assertEqual(original["receipt_sha256"], accepted["receipt_sha256"])
        self.assertFalse(reread["native_approval_redisplayed"])
        successor = accepted["work_session_binding"]["work_session_ref"]
        self.assertNotEqual(successor, self.session)
        current = t.store.read()._document
        self.assertEqual(current["sessions"][successor]["state"], "created")
        self.assertIsNone(current["sessions"][successor]["claim_ref"])
        self.assertEqual(current["sessions"][successor]["workstream_ref"], stream)
        self.assertEqual(current["sessions"][successor]["predecessor_ref"], self.session)
        self.assertEqual(current["workstreams"][stream]["active_session_ref"], successor)
        before = t.files()
        t.reject(lambda: self.handoff(original_resume=True), "work_session_handoff_current_unavailable", committed=True)
        self.assertEqual(t.files(), before)
        public = json.dumps([outgoing, continued, reviewed, accepted, original, reread, progress])
        for private in (old_claim, fixture.LABEL, str(t.root), "person:synthetic-service-accept",
                        "Synthetic receiving service app"):
            self.assertNotIn(private, public)

    def test_all_new_routes_stop_at_real_runtime_pin_or_cancellation_before_facades(self):
        t = self.task
        calls = [self.handoff, lambda **kw: self.handoff(original_resume=True, **kw), self.review_handoff,
                 self.accept, self.resume_accept, self.review_accept]
        before = t.files()
        with ExitStack() as stack:
            blocked = [stack.enter_context(patch.object(owner, name, side_effect=AssertionError("blocked facade")))
                       for owner, name in ((subject.lifecycle, "_establish_task_held"),
                                           (subject.lifecycle, "_resume_task_establishment_held"),
                                           (subject.rereview, "_review_original_session_decision_held"),
                                           (subject.handoff, "_handoff_task_held"),
                                           (subject.handoff, "_review_original_handoff_held"))]
            for index, call in enumerate(calls):
                with self.subTest(mode=index):
                    t.reject(lambda: call(cancel_requested=lambda: True), "work_session_wait_cancelled")
            metadata = t.root.parent / ".zettel-kasten"
            metadata.mkdir()
            (metadata / "installed-version.txt").write_text("v9.9.9\n", encoding="utf-8")
            for index, call in enumerate(calls):
                with self.subTest(mode=index):
                    t.reject(call, "project_runtime_mismatch")
            for dependency in blocked:
                dependency.assert_not_called()
        self.assertEqual(t.files(), before)
        self.assertEqual(t.native.calls, 1)

    def test_invalid_selectors_modes_and_replacement_reviewers_never_wait(self):
        t = self.task
        before = t.files()
        calls = [lambda: self.handoff(original_resume=1), lambda: self.handoff(original_resume=[]),
                 lambda: self.handoff(original_resume=True, reviewer_claim="person:replacement"),
                 lambda: self.handoff(reviewer_claim=None), lambda: self.handoff(target_app_ref=None),
                 lambda: self.handoff(work_session_ref=[]), lambda: self.handoff(client_app_ref=None),
                 lambda: self.accept(predecessor_work_session_ref=None),
                 lambda: self.accept(reviewer_claim="private_error_marker"),
                 lambda: self.accept(task_route_ref=True), lambda: self.resume_accept(client_app_ref=None),
                 lambda: self.review_accept(task_route_ref=[]), lambda: self.review_handoff(target_app_ref=[])]
        with patch.object(subject, "wait_for_archive_writer", side_effect=AssertionError("invalid input waited")) as waiting:
            for index, call in enumerate(calls):
                with self.subTest(mode=index):
                    t.reject(call)
            waiting.assert_not_called()
        self.assertEqual(t.files(), before)

    def test_accept_requires_blank_route_and_resume_never_substitutes_create(self):
        t = self.task
        before = t.files()
        t.reject(lambda: self.resume_accept(client_app_ref=t.app, task_route_ref=t.route))
        t.reject(lambda: self.review_accept(client_app_ref=t.app, task_route_ref=t.route))
        self.assertEqual(t.files(), before)
        self.handoff()
        before = t.files()
        t.reject(lambda: self.accept(client_app_ref=t.app, task_route_ref=t.route), "work_session_task_already_selected")
        self.assertEqual(t.files(), before)
        first = self.accept()
        before = t.files()
        t.reject(self.accept, "work_session_task_already_selected")
        self.assertEqual(t.files(), before)
        self.assertTrue(first["ok"])
        self.assertEqual(t.native.calls, 3)

    def test_accept_preclaim_cut_only_explicit_original_rereview_can_approve(self):
        t = self.task
        self.handoff()
        original_save = actor.WorkSessionActorStore.save

        def cut(store, **kwargs):
            saved = original_save(store, **kwargs)
            if kwargs.get("pending_manifest_sha256") is not None:
                raise OSError("private_error_marker")
            return saved

        with patch.object(actor.WorkSessionActorStore, "save", new=cut):
            t.reject(self.accept)
        before = t.files()
        t.reject(self.resume_accept)
        self.assertEqual(t.files(), before)
        self.assertEqual(t.native.calls, 3)
        t.native.approve = False
        t.reject(self.review_accept, "exact_human_approval_cancelled")
        self.assertEqual(t.files(), before)
        t.native.approve = True
        with patch.object(registry, "_new_ref", side_effect=AssertionError("new original")):
            result = self.review_accept()
        self.assertTrue(result["native_approval_redisplayed"])
        self.assertEqual(t.native.calls, 5)
        before = t.files()
        self.assertEqual(self.resume_accept()["receipt_sha256"], result["receipt_sha256"])
        self.assertEqual(t.files(), before)

    def test_handoff_preclaim_cut_rereview_retains_original_target_and_receipt(self):
        t = self.task
        original_save = actor.WorkSessionActorStore.save

        def cut(store, **kwargs):
            saved = original_save(store, **kwargs)
            if kwargs.get("pending_manifest_sha256") is not None:
                raise OSError("private_error_marker")
            return saved

        with patch.object(actor.WorkSessionActorStore, "save", new=cut):
            t.reject(self.handoff)
        before = t.files()
        t.reject(lambda: self.handoff(original_resume=True))
        t.reject(lambda: self.review_handoff(target_app_ref=t.app))
        self.assertEqual(t.files(), before)
        self.assertEqual(t.native.calls, 2)
        t.native.approve = False
        t.reject(self.review_handoff, "exact_human_approval_cancelled")
        self.assertEqual(t.files(), before)
        t.native.approve = True
        with patch.object(registry, "_new_ref", side_effect=AssertionError("new original")):
            result = self.review_handoff()
        self.assertTrue(result["native_approval_redisplayed"])
        self.assertEqual(t.native.calls, 4)
        before = t.files()
        self.assertEqual(self.handoff(original_resume=True)["receipt_sha256"], result["receipt_sha256"])
        self.assertEqual(t.files(), before)

    def test_started_accept_resumes_original_without_second_native_or_new_plan(self):
        t = self.task
        self.handoff()
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=OSError("private_error_marker")):
            t.reject(self.accept)
        routing = actor.WorkSessionActorStore(t.store, client_app_ref=self.target, task_route_ref=self.route)
        pending = routing._read(current=False).document()
        self.assertIsNotNone(pending["pending_manifest_sha256"])
        self.assertEqual(t.native.calls, 3)
        claims_root = t.root / approval.CLAIMS_RELATIVE_ROOT
        original_claim_names = {path.name for path in claims_root.glob("*.json")}
        plans_root = t.root.joinpath(*bundle.PRIVATE_ROOT)
        original_plans = {path.name: path.read_bytes() for path in plans_root.glob("*.json")}
        # Original bundle decoding must reconstruct its frozen transition with
        # saved refs. Do not disable that verifier's shared pure preparation.
        with patch.object(execution, "_execute_session_decision_held", side_effect=AssertionError("new approval")), \
                patch.object(registry, "_new_ref", side_effect=AssertionError("new original refs")):
            result = self.resume_accept()
        self.assertTrue(result["ok"])
        self.assertEqual({path.name for path in claims_root.glob("*.json")}, original_claim_names)
        self.assertEqual({path.name: path.read_bytes() for path in plans_root.glob("*.json")}, original_plans)
        self.assertEqual(t.native.calls, 3)
        before = t.files()
        self.assertFalse(self.review_accept()["native_approval_redisplayed"])
        self.assertEqual(t.files(), before)

    def test_public_signatures_never_accept_private_approval_or_replacement_resume_context(self):
        for name in ("accept_task", "resume_task_accept", "review_original_task_accept",
                     "handoff_task", "review_original_task_handoff"):
            with self.subTest(name=name):
                parameters = inspect.signature(getattr(subject, name)).parameters
                self.assertFalse({"native", "key_provider", "claim_ref", "context", "approval_id",
                                  "manifest_sha256", "running_version", "label"} & set(parameters))
                self.assertFalse(any(p.kind == p.VAR_KEYWORD for p in parameters.values()))
                if name not in {"accept_task", "handoff_task"}:
                    self.assertNotIn("reviewer_claim", parameters)
                if name in {"resume_task_accept", "review_original_task_accept"}:
                    self.assertNotIn("predecessor_work_session_ref", parameters)


if __name__ == "__main__":
    unittest.main()
