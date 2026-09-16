"""Routing preparation uses actual read-only registry state, never authority."""

from contextlib import redirect_stderr, redirect_stdout
import inspect
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_actor as actor
from wom_kit import work_session_registration as registration
from wom_kit import work_session_registry as registry
from wom_kit import work_session_service as subject


LABEL = "SYNTHETIC_PRIVATE_REQUEST_APP"


class TaskRequestInitializationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="wom-task-request-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "archive"
        self.root.mkdir()
        (self.root / "archive.yml").write_text(
            "archive_id: archive:personal:synthetic-task-request\n", encoding="utf-8")
        self.store = registration._store(self.root)
        self.app = self.register()

    def register(self):
        transition = registry.plan_transition(self.store.read(), action="register-app", label=LABEL)
        with exact.ExactOperationWriterLock(self.root) as held:
            self.store.commit(transition, held_lock=held)
        return transition.result_refs[0]

    def snapshot(self, root=None):
        root = self.root if root is None else root
        return {
            path.relative_to(root).as_posix(): (
                "directory" if path.is_dir() else path.read_bytes(), path.stat().st_mtime_ns,
            )
            for path in root.rglob("*")
        }

    def reject(self, call, *, code="work_session_service_invalid"):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            with self.assertRaises(subject.WorkSessionServiceError) as caught:
                call()
        self.assertEqual(caught.exception.code, code)
        self.assertIsNone(caught.exception.__cause__)
        self.assertIsNone(caught.exception.__context__)
        for private in (LABEL, self.app, str(self.root)):
            self.assertNotIn(private, repr(caught.exception))
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")
        self.assertFalse(caught.exception.original_commit_verified)

    def test_registered_explicit_app_gets_only_a_route_without_writes_or_approval(self):
        before, generation = self.snapshot(), self.store.read().sha256
        with mock.patch.object(subject, "wait_for_archive_writer", side_effect=AssertionError("no_lock")), \
             mock.patch.object(subject, "_runtime_guard", side_effect=AssertionError("no_writer_guard")), \
             mock.patch.object(registry.WorkSessionRegistryStore, "commit", side_effect=AssertionError("no_commit")), \
             mock.patch.object(registry, "_write_private_pending", side_effect=AssertionError("no_pending")), \
             mock.patch.object(exact, "_ensure_private_directory", side_effect=AssertionError("no_directory")):
            result = subject.initialize_task_request(self.root, client_app_ref=self.app)
        self.assertTrue(registry._ref(result["task_route_ref"], "task_route"))
        self.assertEqual(result, {
            "schema": "wom-kit/work-session-task-request/v1", "ok": True,
            "client_app_ref": self.app, "task_route_ref": result["task_route_ref"],
            "read_only": True, "routing_is_write_authority": False,
            "native_approval_required": False, "archive_changed": False,
        })
        self.assertNotIn(LABEL, json.dumps(result))
        self.assertNotIn(str(self.root), json.dumps(result))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.store.read().sha256, generation)
        self.assertFalse(self.root.joinpath(*actor.PRIVATE_ROOT).exists())
        self.assertEqual(self.store.read()._document["sessions"], {})

    def test_each_explicit_new_request_gets_a_fresh_route_but_no_session(self):
        before = self.snapshot()
        first = subject.initialize_task_request(self.root, client_app_ref=self.app)
        second = subject.initialize_task_request(self.root, client_app_ref=self.app)
        self.assertNotEqual(first["task_route_ref"], second["task_route_ref"])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.store.read()._document["sessions"], {})

    def test_invalid_app_is_blocked_before_root_lookup_or_route_generation(self):
        with mock.patch.object(subject, "_root", side_effect=AssertionError("no_root_read")), \
             mock.patch.object(actor, "new_task_route_ref", side_effect=AssertionError("no_route")):
            for value in (None, False, 1, [], {}, LABEL, "client_app_" + "A" * 32):
                with self.subTest(kind=type(value).__name__):
                    self.reject(lambda: subject.initialize_task_request(self.root, client_app_ref=value))

    def test_unregistered_app_and_other_archive_app_never_infer_a_registered_app(self):
        before = self.snapshot()
        with mock.patch.object(actor, "new_task_route_ref", side_effect=AssertionError("no_route")):
            self.reject(lambda: subject.initialize_task_request(
                self.root, client_app_ref=registry._new_ref("client_app")))
            other = self.base / "other"
            other.mkdir()
            (other / "archive.yml").write_text(
                "archive_id: archive:personal:synthetic-other-request\n", encoding="utf-8")
            other_before = self.snapshot(other)
            self.reject(lambda: subject.initialize_task_request(other, client_app_ref=self.app))
            self.assertEqual(self.snapshot(other), other_before)
            self.assertFalse((other / "profiles").exists())
        self.assertEqual(self.snapshot(), before)

    def test_generation_drift_is_not_reported_as_success_and_adds_no_service_writes(self):
        observed = {}
        original = actor.new_task_route_ref

        def drift():
            self.register()  # An independent writer changes the generation.
            observed["files"] = self.snapshot()
            return original()

        with mock.patch.object(actor, "new_task_route_ref", side_effect=drift):
            self.reject(lambda: subject.initialize_task_request(self.root, client_app_ref=self.app),
                        code="work_session_registration_changed")
        self.assertEqual(self.snapshot(), observed["files"])

    def test_archive_identity_drift_is_not_reported_as_success(self):
        observed = {}
        original = actor.new_task_route_ref

        def drift():
            (self.root / "archive.yml").write_text(
                "archive_id: archive:personal:synthetic-changed-request\n", encoding="utf-8")
            observed["files"] = self.snapshot()
            return original()

        with mock.patch.object(actor, "new_task_route_ref", side_effect=drift):
            self.reject(lambda: subject.initialize_task_request(self.root, client_app_ref=self.app),
                        code="work_session_registration_changed")
        self.assertEqual(self.snapshot(), observed["files"])

    def test_malformed_registry_and_generation_failure_keep_private_details_hidden(self):
        generation = self.store.path / "000000000001.json"
        generation.write_text(LABEL, encoding="utf-8")
        before = self.snapshot()
        with mock.patch.object(actor, "new_task_route_ref", side_effect=AssertionError("no_route")):
            self.reject(lambda: subject.initialize_task_request(self.root, client_app_ref=self.app))
        self.assertEqual(self.snapshot(), before)

    def test_route_generation_failure_is_fixed_and_has_no_side_effect(self):
        before = self.snapshot()
        for value in (None, LABEL):
            with mock.patch.object(actor, "new_task_route_ref", return_value=value):
                self.reject(lambda: subject.initialize_task_request(self.root, client_app_ref=self.app),
                            code="work_session_service_unavailable")
        with mock.patch.object(actor, "new_task_route_ref", side_effect=OSError(LABEL)):
            self.reject(lambda: subject.initialize_task_request(self.root, client_app_ref=self.app),
                        code="work_session_service_unavailable")
        self.assertEqual(self.snapshot(), before)

    def test_signature_has_no_implicit_route_or_authority_injection(self):
        signature = inspect.signature(subject.initialize_task_request)
        self.assertEqual(tuple(signature.parameters), ("root", "client_app_ref"))
        selected = signature.parameters["client_app_ref"]
        self.assertEqual(selected.kind, selected.KEYWORD_ONLY)
        self.assertEqual(selected.default, selected.empty)


if __name__ == "__main__":
    unittest.main()
