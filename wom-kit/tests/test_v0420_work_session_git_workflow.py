"""Real temporary Git, registry and claims; no provider or private archive."""

from contextlib import ExitStack, nullcontext
import _thread
import inspect
import json
from pathlib import Path
import signal
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_git_backup_writer as git_fixture
from test_v0420_work_session_execution import SessionNative
from test_v0420_work_session_git_provenance import _ReadGuardKey
import test_v0420_git_backup_session_scope as scope_fixtures
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import exact_operation_manifest as exact
from wom_kit import git_backup_session_scope as scope
from wom_kit import git_backup_writer as writer
from wom_kit import work_session_actor as actor
from wom_kit import work_session_establishment as establishment
from wom_kit import work_session_execution as execution
from wom_kit import work_session_git_bundle as bundle
from wom_kit import work_session_git_terminal as terminal
from wom_kit import work_session_git_workflow as subject
from wom_kit import work_session_registry as registry


class ScopeEstablishmentTests(unittest.TestCase):
    def test_optional_origin_preserves_legacy_bytes_and_strictly_binds_new_proof(self):
        fixture = scope_fixtures.SessionScopeTests()
        fixture.setUp()
        original = fixture.scope
        value = original.document()
        self.assertNotIn("establishment_proof", value)
        self.assertEqual(scope._GitBackupSessionScope.from_document(value)._raw, original._raw)
        proof = {key: "sha256:" + str(index) * 64 for index, key in enumerate(sorted(scope._ESTABLISHMENT_KEYS))}
        updated = {**value, "establishment_proof": proof}
        updated["scope_sha256"] = scope._sha({key: field for key, field in updated.items() if key != "scope_sha256"})
        extended = scope._GitBackupSessionScope.from_document(updated)
        self.assertNotEqual(extended.scope_sha256, original.scope_sha256)
        self.assertEqual(extended.document()["establishment_proof"], proof)
        for malformed in (None, {}, [], True, {**proof, "label": "PRIVATE"},
                          {**proof, "execution_sha256": "PRIVATE"}):
            changed = {**updated, "establishment_proof": malformed}
            changed["scope_sha256"] = scope._sha({key: field for key, field in changed.items() if key != "scope_sha256"})
            with self.subTest(kind=type(malformed).__name__), self.assertRaises(scope.GitBackupSessionScopeError) as caught:
                scope._GitBackupSessionScope.from_document(changed)
            self.assertIsNone(caught.exception.__context__)
            self.assertIsNone(caught.exception.__cause__)

    def test_private_resume_has_no_new_reviewer_approval_hash_or_native_parameters(self):
        parameters = inspect.signature(subject._resume_session_git_backup_held).parameters
        self.assertEqual(set(parameters), {"root", "held", "client_app_ref", "task_route_ref",
                                          "work_session_ref", "key_provider", "progress_hook"})
        self.assertIsNone(parameters["work_session_ref"].default)
        for value in ([], {}, None, True, "PRIVATE"):
            error = subject.WorkSessionGitWorkflowError(value)
            self.assertEqual(error.code, "work_session_git_invalid")
            self.assertIsNone(error.__context__)

    def test_verified_git_fact_survives_private_actor_tail_errors_without_exception_chains(self):
        digest = "sha256:" + "a" * 64
        prepared = SimpleNamespace(manifest=SimpleNamespace(
            manifest_sha256=digest, work_session_binding=SimpleNamespace(work_session_ref="work_session:synthetic")))
        selected = SimpleNamespace(sha256=digest, document=lambda: {"claim_ref": "claim:synthetic"})
        routing = SimpleNamespace(save=lambda **_kwargs: selected)
        for boundary in ("selection", "ownership", "save", "readback"):
            with self.subTest(boundary=boundary), ExitStack() as stack:
                stack.enter_context(patch.object(subject, "_verified_terminal", return_value=({}, None)))
                selected_scope = stack.enter_context(patch.object(subject, "_selected_scope",
                    return_value=(prepared, object(), routing, selected, None)))
                ownership = stack.enter_context(patch.object(subject, "_current_scope"))
                readback = stack.enter_context(patch.object(subject, "_assert_actor"))
                stack.enter_context(patch.object(approval, "exact_human_approval_context_sha256", return_value=digest))
                failure = OSError("SYNTHETIC_PRIVATE_PATH")
                if boundary == "selection":
                    selected_scope.side_effect = failure
                elif boundary == "ownership":
                    ownership.side_effect = failure
                elif boundary == "save":
                    stack.enter_context(patch.object(routing, "save", side_effect=failure))
                else:
                    readback.side_effect = failure
                with self.assertRaises(subject.WorkSessionGitWorkflowError) as caught:
                    subject._finish(prepared, None, None, None, completed=False)
                self.assertTrue(caught.exception.original_commit_verified)
                self.assertIsNone(caught.exception.__context__)
                self.assertIsNone(caught.exception.__cause__)
                self.assertNotIn("SYNTHETIC_PRIVATE_PATH", repr(caught.exception))


class ScopedWorkerSettlementTests(unittest.TestCase):
    def test_thread_creation_failure_does_not_wait_for_nonexistent_worker(self):
        numbers = (signal.SIGINT,) + ((signal.SIGBREAK,) if hasattr(signal, "SIGBREAK") else ())
        originals = tuple(signal.getsignal(number) for number in numbers)
        for failure in (RuntimeError("synthetic thread exhaustion"), KeyboardInterrupt()):
            effects = []
            with self.subTest(kind=type(failure).__name__), \
                 patch.object(threading.Thread, "start", side_effect=failure):
                with self.assertRaises(subject.WorkSessionGitWorkflowError) as caught:
                    subject._settled_git_call(lambda: effects.append(True))
            self.assertEqual(effects, [])
            self.assertIsNone(caught.exception.__context__)
            self.assertEqual(tuple(signal.getsignal(number) for number in numbers), originals)

    def test_startup_signal_setter_failure_restores_exact_handlers_without_launch(self):
        numbers = (signal.SIGINT,) + ((signal.SIGBREAK,) if hasattr(signal, "SIGBREAK") else ())
        originals = {number: object() for number in numbers}
        current, attempts, effects = dict(originals), [], []
        def setter(number, handler):
            current[number] = handler
            attempts.append((number, handler))
            if len(attempts) == 1:
                raise KeyboardInterrupt()
        with patch.object(signal, "getsignal", side_effect=lambda number: current[number]), \
             patch.object(signal, "signal", side_effect=setter):
            with self.assertRaises(subject.WorkSessionGitWorkflowError):
                with subject._deferred_git_worker_signals():
                    effects.append(True)
        self.assertEqual(effects, [])
        self.assertEqual(current, originals)

    def test_permanent_restore_failure_is_bounded_after_worker_done_and_cancellation_flag_is_bounded(self):
        numbers = (signal.SIGINT,) + ((signal.SIGBREAK,) if hasattr(signal, "SIGBREAK") else ())
        originals = {number: object() for number in numbers}
        current, attempts, effects = dict(originals), [], []
        def setter(number, handler):
            attempts.append((number, handler))
            if handler is originals[number]:
                raise OSError("SYNTHETIC_PRIVATE_RESTORE_FAILURE")
            current[number] = handler
        with patch.object(signal, "getsignal", side_effect=lambda number: current[number]), \
             patch.object(signal, "signal", side_effect=setter):
            with self.assertRaises(subject.WorkSessionGitWorkflowError) as caught:
                subject._settled_git_call(lambda: effects.append("done"))
        self.assertEqual(effects, ["done"])
        self.assertEqual(caught.exception.code, "work_session_git_signal_restore_failed")
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)
        self.assertEqual(len(attempts), len(numbers) * 4)
        with subject._deferred_git_worker_signals() as cancelled:
            for _index in range(1000):
                signal.getsignal(signal.SIGINT)(signal.SIGINT, None)
            self.assertEqual(cancelled, [True])

    def test_interruption_cannot_release_real_archive_lock_before_worker_settles(self):
        self._assert_interrupted_worker_settlement("console")

    def test_exception_after_real_start_cannot_escape_before_worker_settles(self):
        self._assert_interrupted_worker_settlement("after_start")

    def _assert_interrupted_worker_settlement(self, mode):
        entered, release, joined, finished = (threading.Event() for _index in range(4))
        observations, errors = [], []
        original_join = threading.Thread.join
        original_start = threading.Thread.start

        def interrupted_start(worker):
            original_start(worker)
            raise KeyboardInterrupt()

        def mutation():
            entered.set()
            if not release.wait(10):
                raise AssertionError("worker was never released")
            finished.set()

        def observed_join(worker, *args, **kwargs):
            joined.set()
            return original_join(worker, *args, **kwargs)

        with tempfile.TemporaryDirectory(prefix="wom-git-settlement-") as temporary:
            root = Path(temporary)

            def interrupt_and_probe():
                try:
                    if not entered.wait(10):
                        raise AssertionError("worker did not start")
                    if mode == "console":
                        _thread.interrupt_main()
                    if not joined.wait(10):
                        raise AssertionError("interruption did not enter settlement")
                    try:
                        with exact.ExactOperationWriterLock(root, timeout_seconds=0):
                            observations.append("wrongly_acquired")
                    except exact.ExactOperationManifestError:
                        observations.append("still_locked")
                except BaseException as error:
                    errors.append(error)
                finally:
                    release.set()

            controller = threading.Thread(target=interrupt_and_probe)
            controller.start()
            with exact.ExactOperationWriterLock(root) as held, \
                 patch.object(threading.Thread, "join", observed_join), \
                 (patch.object(threading.Thread, "start", interrupted_start) if mode == "after_start" else nullcontext()):
                with self.assertRaises(subject.WorkSessionGitWorkflowError) as caught:
                    subject._settled_git_call(mutation)
                self.assertEqual(caught.exception.code, "exact_human_approval_state_unknown")
                self.assertIsNone(caught.exception.__context__)
                self.assertTrue(finished.is_set())
                held.verify_held()
            controller.join(10)
            self.assertFalse(controller.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(observations, ["still_locked"])
            with exact.ExactOperationWriterLock(root, timeout_seconds=0):
                pass

    def test_mutation_has_no_concurrent_progress_callback_and_rechecks_after_initial_callback(self):
        entered, release = threading.Event(), threading.Event()
        pulses, effects, observations = [], [], []
        owner = [True]

        def guard(*_args, **_kwargs):
            if not owner[0]:
                raise subject.WorkSessionGitWorkflowError("work_session_git_ownership_unavailable")

        def mutate(*_args):
            entered.set()
            if not release.wait(10):
                raise AssertionError("release missing")
            effects.append(owner[0])

        backend = SimpleNamespace(prepared=object(), write=mutate)
        adapter = subject._SessionGitBackupWriter(backend, None, None, None)
        def pulse():
            pulses.append("progress")
            if entered.is_set() and not release.is_set():
                owner[0] = False

        def observe():
            try:
                if not entered.wait(10):
                    raise AssertionError("mutation did not start")
                observations.append(len(pulses))
            finally:
                release.set()

        controller = threading.Thread(target=observe)
        controller.start()
        with patch.object(subject, "_require_pending_scope_held", side_effect=guard):
            adapter.write_field(target_kind="synthetic", target_ref="synthetic", field_ref="synthetic",
                                value=b"x", heartbeat=pulse)
            self.assertEqual(effects, [True])
            self.assertEqual(observations, [1])
            self.assertEqual(len(pulses), 2)
            def drift():
                owner[0] = False
            with self.assertRaises(subject.WorkSessionGitWorkflowError):
                adapter.write_field(target_kind="synthetic", target_ref="synthetic", field_ref="synthetic",
                                    value=b"x", heartbeat=drift)
            self.assertEqual(effects, [True])
        controller.join(10)
        self.assertFalse(controller.is_alive())


class SessionGitWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.fixture = git_fixture.GitBackupWriterTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.root = self.fixture.root
        self.git = lambda *args, **kwargs: self.fixture.git(self.root, *args, **kwargs)
        self.git("config", "core.autocrlf", "false")
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for item in self.fixture.patches():
            self.stack.enter_context(item)
        self.key = _ReadGuardKey()
        self.stack.enter_context(patch.object(broker, "_production_key_provider", return_value=self.key))
        self.store, _archive = execution._store(self.root)
        self.route = actor.new_task_route_ref()
        with exact.ExactOperationWriterLock(self.root) as held:
            registered = registry.plan_transition(self.store.read(), action="register-app", label="Synthetic app")
            self.store.commit(registered, held_lock=held)
            self.app = registered.result_refs[0]
            self.original = execution._execute_session_decision_held(
                self.root, held=held, action="create", client_app_ref=self.app,
                task_route_ref=self.route, label="Synthetic task", reviewer_claim="person:fixture",
                native=SessionNative(), key_provider=self.key)
            self.session = self.original["work_session_binding"]["work_session_ref"]
            claimed = registry.plan_transition(self.store.read(), action="claim", client_app_ref=self.app,
                                               work_session_ref=self.session)
            self.store.commit(claimed, held_lock=held)
            self.binding = self.store.read().binding(self.session)
            self.claim_ref = self.store.read()._document["sessions"][self.session]["claim_ref"]
            self.routing = actor.WorkSessionActorStore(self.store, client_app_ref=self.app, task_route_ref=self.route)
            origin = establishment.EstablishmentSelector.from_document({
                "action": "create", "manifest_sha256": self.original["manifest_sha256"],
                "context_sha256": self.original["exact_human_approval_reference"]["context_sha256"]})
            self.selected = self.routing.save(expected_sha256=None, held_lock=held,
                work_session_ref=self.session, claim_ref=self.claim_ref, observed_binding=self.binding,
                established_origin=origin)
        self.native = git_fixture._Native()

    def execute(self, held):
        return subject._execute_session_git_backup_held(self.root, held=held,
            client_app_ref=self.app, task_route_ref=self.route, work_session_ref=self.session,
            reviewer_claim="person:git-reviewer", native=self.native, key_provider=self.key)

    def resume(self, held, **changes):
        return subject._resume_session_git_backup_held(self.root, held=held,
            client_app_ref=self.app, task_route_ref=self.route, key_provider=self.key, **changes)

    def evidence(self):
        return {str(path.relative_to(self.root)): path.read_bytes()
                for top in (self.root / "profiles" / "local", self.root / "receipts")
                for path in top.rglob("*") if path.is_file() and path.suffix in {".json", ".jsonl"}}

    def original_git(self, held):
        pending = self.routing._read(current=False).pending_operation()
        return bundle._load_original_git_context_held(self.root, held=held,
                                                     manifest_sha256=pending.document()["manifest_sha256"])

    def test_preview_is_read_only_then_real_scoped_write_and_original_output_lost_tail(self):
        before, registry_sha = self.evidence(), self.store.read().sha256
        with exact.ExactOperationWriterLock(self.root) as held:
            self.key.read_only = True
            preview = subject._preview_session_git_backup_held(self.root, held=held,
                client_app_ref=self.app, task_route_ref=self.route, work_session_ref=self.session,
                key_provider=self.key)
            self.assertEqual(self.evidence(), before)
            self.assertEqual(preview["selected_receipt_count"], 1)
            self.assertTrue(preview["current_claim_ownership_verified"])
            self.assertFalse(preview["backup_performed"])
            self.key.read_only = False
            result = self.execute(held)
            held.verify_held()
            self.assertEqual(self.store.read().sha256, registry_sha)
            self.assertTrue(result["original_commit_verified"])
            self.assertFalse(result["artifact_backup_complete"])
            self.assertEqual(self.native.calls, 1)
            self.assertIsNone(self.routing.read().pending_operation())
            self.assertEqual(self.routing.read().document()["last_completed_operation"]["kind"], "git_backup")
            self.assertEqual(self.routing.read().document()["established_origin"], self.selected.document()["established_origin"])
            self.assertEqual((self.root / "tracked.txt").read_text(), "after\n")
            self.assertEqual((self.root / "new-private.txt").read_text(), "new bytes\n")
            written = self.evidence()
            with patch.object(writer, "_run_git_backup_exact_operation", side_effect=AssertionError("writer reentered")), \
                 patch.object(writer.planning, "git_backup_plan", side_effect=AssertionError("fresh plan")), \
                 patch.object(terminal, "_build_git_terminal_record", side_effect=AssertionError("signed again")), \
                 patch.object(actor.WorkSessionActorStore, "save", side_effect=AssertionError("actor rewritten")):
                resumed = self.resume(held)
            self.assertTrue(resumed["original_operation_already_completed"])
            self.assertFalse(resumed["domain_writer_reentered"])
            self.assertEqual(self.evidence(), written)

    def test_post_click_actor_or_source_change_never_publishes_git_claim_or_context(self):
        before = self.evidence()
        self.native.callback = lambda: (self.root / "new-private.txt").write_text("changed after click\n")
        self.key.create_if_missing.clear()
        with exact.ExactOperationWriterLock(self.root) as held:
            with self.assertRaises(subject.WorkSessionGitWorkflowError) as caught:
                self.execute(held)
            self.assertEqual(caught.exception.code, "work_session_git_changed")
            self.assertIsNone(caught.exception.__context__)
            self.assertEqual(self.evidence(), before)
            self.assertNotIn(True, self.key.create_if_missing)
            self.assertEqual(self.git("rev-parse", "HEAD").stdout.strip(), self.fixture.initial_head)

    def test_pending_without_authenticated_claim_is_preserved_and_never_reapproved(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(broker, "_claim_exact_human_approval_core", side_effect=RuntimeError("synthetic crash")):
                with self.assertRaises(subject.WorkSessionGitWorkflowError):
                    self.execute(held)
            pending = self.routing._read(current=False)
            self.assertEqual(pending.pending_operation().document()["kind"], "git_backup")
            before = self.evidence()
            with patch.object(writer, "_run_git_backup_exact_operation", side_effect=AssertionError("writer entered")), \
                 patch.object(broker, "_request_exact_human_approval_core", side_effect=AssertionError("new review")):
                with self.assertRaises(subject.WorkSessionGitWorkflowError) as caught:
                    self.resume(held)
            self.assertEqual(caught.exception.code, "work_session_git_original_approval_missing")
            self.assertEqual(self.evidence(), before)

    def test_started_before_first_checkpoint_resumes_exact_original_without_planner(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(writer, "_run_git_backup_exact_operation", side_effect=RuntimeError("synthetic crash")):
                with self.assertRaises(subject.WorkSessionGitWorkflowError):
                    self.execute(held)
            original = self.original_git(held)
            self.assertEqual(self.routing._read(current=False).document()["previous_sha256"],
                             original.prepared.session_scope.document()["actor_sha256"])
            with patch.object(writer.planning, "git_backup_plan", side_effect=AssertionError("fresh plan")):
                result = self.resume(held)
            self.assertEqual(result["started_resume_state"], "authenticated_before_first_checkpoint")
            self.assertTrue(result["original_commit_verified"])
            self.assertFalse(result["resume_discovery"]["checkpoint_chain_validated_read_only"])
            self.assertEqual(self.native.calls, 1)

    def test_common_final_cut_builds_only_terminal_without_reentering_dirty_tree_writer(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(terminal, "_build_git_terminal_record", side_effect=RuntimeError("synthetic crash")):
                with self.assertRaises(subject.WorkSessionGitWorkflowError):
                    self.execute(held)
            count = len(self.fixture.transport_commands)
            with patch.object(writer, "_run_git_backup_exact_operation", side_effect=AssertionError("Git reentered")), \
                 patch.object(writer.planning, "git_backup_plan", side_effect=AssertionError("fresh plan")):
                result = self.resume(held)
            self.assertEqual(result["started_resume_state"], "common_final_present")
            self.assertTrue(result["common_final_tail_only"])
            self.assertEqual(len(self.fixture.transport_commands), count)

    def test_succeeded_cut_proves_old_anchors_after_unrelated_later_head_without_resigning(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(subject, "_finish", side_effect=RuntimeError("synthetic actor cut")):
                with self.assertRaises(subject.WorkSessionGitWorkflowError):
                    self.execute(held)
            (self.root / "later.txt").write_text("synthetic later local work\n")
            self.git("add", "--", "later.txt")
            self.git("commit", "--only", "-m", "synthetic later commit", "--", "later.txt")
            with patch.object(writer, "_run_git_backup_exact_operation", side_effect=AssertionError("Git reentered")), \
                 patch.object(writer.planning, "git_backup_plan", side_effect=AssertionError("fresh plan")), \
                 patch.object(terminal, "_build_git_terminal_record", side_effect=AssertionError("signed again")):
                result = self.resume(held)
            self.assertFalse(result["domain_writer_reentered"])
            self.assertTrue(result["original_commit_verified"])
            self.assertEqual(result["original_git_anchors"]["current_head_relation"], "different")

    def test_no_eligible_receipts_is_honest_noop_without_native_or_metadata_writes(self):
        receipt = "receipts/ops/exact-operations/" + self.original["execution_sha256"][7:] + ".json"
        self.git("add", "--", receipt)
        self.git("commit", "--only", "-m", "synthetic prior receipt backup", "--", receipt)
        self.git("push", str(self.fixture.remote), "HEAD:refs/heads/main")
        before = self.evidence()
        self.key.read_only = True
        with exact.ExactOperationWriterLock(self.root) as held:
            result = self.execute(held)
            self.assertEqual(result["status"], "no_eligible_receipts")
            self.assertFalse(result["backup_performed"])
            self.assertFalse(result["artifact_backup_complete"])
            self.assertFalse(result["ready_for_write"])
            self.assertEqual(self.native.calls, 0)
            self.assertEqual(self.evidence(), before)

    def test_missing_released_lock_and_wrong_explicit_route_fail_before_key_or_native(self):
        with exact.ExactOperationWriterLock(self.root) as released:
            released.verify_held()
        with patch.object(self.key, "use_key", side_effect=AssertionError("key before ownership")):
            for held in (None, released):
                with self.subTest(lock=type(held).__name__), self.assertRaises(subject.WorkSessionGitWorkflowError):
                    self.execute(held)
            with exact.ExactOperationWriterLock(self.root) as held:
                with self.assertRaises(subject.WorkSessionGitWorkflowError):
                    subject._execute_session_git_backup_held(self.root, held=held,
                        client_app_ref=self.app, task_route_ref=actor.new_task_route_ref(),
                        work_session_ref=self.session, reviewer_claim="person:synthetic",
                        native=self.native, key_provider=self.key)
        self.assertEqual(self.native.calls, 0)

    def test_partial_commit_cut_resumes_without_second_commit_or_new_review(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(writer._GitBackupBackend, "_push", side_effect=RuntimeError("synthetic push cut")):
                with self.assertRaises(subject.WorkSessionGitWorkflowError):
                    self.execute(held)
            committed = self.git("rev-parse", "HEAD").stdout.strip()
            self.assertNotEqual(committed, self.fixture.initial_head)
            with patch.object(writer._GitBackupBackend, "_commit_group", side_effect=AssertionError("second commit")), \
                 patch.object(writer.planning, "git_backup_plan", side_effect=AssertionError("fresh plan")):
                result = self.resume(held)
            self.assertEqual(result["started_resume_state"], "checkpoint_present")
            self.assertEqual(self.git("rev-parse", "HEAD").stdout.strip(), committed)
            self.assertEqual(self.native.calls, 1)

    def test_started_signed_terminal_cut_reuses_existing_record_without_signing(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(approval._ClaimedExactHumanApproval, "finalize_succeeded",
                              side_effect=RuntimeError("synthetic succeeded cut")):
                with self.assertRaises(subject.WorkSessionGitWorkflowError):
                    self.execute(held)
            with patch.object(writer, "_run_git_backup_exact_operation", side_effect=AssertionError("Git reentered")), \
                 patch.object(terminal, "_build_git_terminal_record", side_effect=AssertionError("signed again")):
                result = self.resume(held)
            self.assertEqual(result["started_resume_state"], "signed_terminal_present")
            self.assertTrue(result["signed_terminal_tail_only"])

    def test_underlying_writer_refuses_changed_pending_selector_before_git_effect(self):
        original_runner = writer._run_git_backup_exact_operation
        with exact.ExactOperationWriterLock(self.root) as held:
            def altered(prepared, **kwargs):
                selected = self.routing._read(current=False)
                wrong = selected.pending_operation().document()
                wrong["context_sha256"] = "sha256:" + "a" * 64
                self.routing.save(expected_sha256=selected.sha256, held_lock=held,
                    work_session_ref=self.session, claim_ref=self.claim_ref, observed_binding=self.binding,
                    pending_operation=actor.PendingOperationSelector.from_document(wrong))
                return original_runner(prepared, **kwargs)
            with patch.object(writer, "_run_git_backup_exact_operation", side_effect=altered), \
                 patch.object(writer._GitBackupBackend, "_exact_add", side_effect=AssertionError("Git effect")):
                with self.assertRaises(subject.WorkSessionGitWorkflowError):
                    self.execute(held)
            self.assertEqual(self.git("rev-parse", "HEAD").stdout.strip(), self.fixture.initial_head)

    def test_underlying_writer_reauthenticates_exact_original_establishment_receipt(self):
        original_runner = writer._run_git_backup_exact_operation
        origin_path = self.root / "receipts" / "ops" / "exact-operations" / (self.original["execution_sha256"][7:] + ".json")
        with exact.ExactOperationWriterLock(self.root) as held:
            def altered(prepared, **kwargs):
                raw = json.loads(origin_path.read_bytes())
                raw["result"]["completion_authentication"]["terminal_mac"] = "hmac-sha256:" + "0" * 64
                raw["result"]["result_sha256"] = exact._digest_document(
                    {key: value for key, value in raw["result"].items() if key != "result_sha256"})
                raw["receipt_sha256"] = exact._digest_document(
                    {key: value for key, value in raw.items() if key != "receipt_sha256"})
                origin_path.write_bytes(exact._canonical_json_bytes(raw) + b"\n")
                return original_runner(prepared, **kwargs)
            with patch.object(writer, "_run_git_backup_exact_operation", side_effect=altered), \
                 patch.object(writer._GitBackupBackend, "_exact_add", side_effect=AssertionError("Git effect")):
                with self.assertRaises(subject.WorkSessionGitWorkflowError):
                    self.execute(held)
            self.assertEqual(self.git("rev-parse", "HEAD").stdout.strip(), self.fixture.initial_head)

    def test_proven_git_completion_survives_later_ownership_loss_without_actor_cas(self):
        original_finish = subject._finish
        with exact.ExactOperationWriterLock(self.root) as held:
            def lose_ownership(*args, **kwargs):
                paused = registry.plan_transition(self.store.read(), action="pause",
                    client_app_ref=self.app, work_session_ref=self.session, claim_ref=self.claim_ref)
                self.store.commit(paused, held_lock=held)
                return original_finish(*args, **kwargs)
            with patch.object(subject, "_finish", side_effect=lose_ownership):
                with self.assertRaises(subject.WorkSessionGitWorkflowError) as caught:
                    self.execute(held)
            self.assertTrue(caught.exception.original_commit_verified)
            self.assertIsNone(caught.exception.__context__)
            self.assertIsNotNone(self.routing._read(current=False).pending_operation())
            before = self.evidence()
            with patch.object(writer, "_run_git_backup_exact_operation", side_effect=AssertionError("Git reentered")), \
                 patch.object(actor.WorkSessionActorStore, "save", side_effect=AssertionError("actor rewritten")):
                with self.assertRaises(subject.WorkSessionGitWorkflowError) as again:
                    self.resume(held)
            self.assertTrue(again.exception.original_commit_verified)
            self.assertEqual(self.evidence(), before)

    def test_key_provider_boundary_rechecks_actual_ownership_before_context_or_pending(self):
        original_key = self.key.use_key
        before = self.evidence()
        def changed_provider(root, consumer, *, create_if_missing=False):
            if create_if_missing:
                with patch.object(registry.WorkSessionRegistryStore, "require_claimed_binding",
                                  side_effect=registry.WorkSessionRegistryError("work_session_claim_conflict")):
                    return original_key(root, consumer, create_if_missing=create_if_missing)
            return original_key(root, consumer, create_if_missing=create_if_missing)
        with exact.ExactOperationWriterLock(self.root) as held, \
             patch.object(self.key, "use_key", side_effect=changed_provider), \
             patch.object(bundle, "_save_original_git_context_held") as context_save, \
             patch.object(actor.WorkSessionActorStore, "save") as pending_save:
            with self.assertRaises(subject.WorkSessionGitWorkflowError):
                self.execute(held)
            context_save.assert_not_called()
            pending_save.assert_not_called()
            self.assertEqual(self.evidence(), before)

    def test_two_real_sessions_commit_only_owned_receipt_and_preserve_other_receipt(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            other = execution._execute_session_decision_held(self.root, held=held, action="create",
                client_app_ref=self.app, task_route_ref=actor.new_task_route_ref(), label="Synthetic other task",
                reviewer_claim="person:other-reviewer", native=SessionNative(), key_provider=self.key)
            other_path = "receipts/ops/exact-operations/" + other["execution_sha256"][7:] + ".json"
            other_raw = (self.root / other_path).read_bytes()
            result = self.execute(held)
            self.assertEqual(result["selected_receipt_count"], 1)
            self.assertEqual((self.root / other_path).read_bytes(), other_raw)
            self.assertNotEqual(self.git("ls-files", "--error-unmatch", "--", other_path, check=False).returncode, 0)
            committed = self.git("show", "--format=", "--name-only", "HEAD").stdout.splitlines()
            self.assertEqual([line for line in committed if line], [
                "receipts/ops/exact-operations/" + self.original["execution_sha256"][7:] + ".json"])

    def test_supplied_read_only_key_provider_never_falls_back_to_production(self):
        self.key.read_only = True
        with exact.ExactOperationWriterLock(self.root) as held, \
             patch.object(broker, "_production_key_provider", side_effect=AssertionError("default key selected")):
            result = subject._preview_session_git_backup_held(self.root, held=held,
                client_app_ref=self.app, task_route_ref=self.route, work_session_ref=self.session,
                key_provider=self.key)
            self.assertEqual(result["selected_receipt_count"], 1)

    def test_terminal_change_during_anchor_observation_blocks_completed_actor_publication(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(subject, "_finish", side_effect=RuntimeError("synthetic actor cut")):
                with self.assertRaises(subject.WorkSessionGitWorkflowError):
                    self.execute(held)
            terminal_path = next((self.root / "receipts" / "ops" / "git-backups").glob("*.json"))
            original_observer = subject.anchors._observe_original_git_anchors_held
            def replace_after_observation(*args, **kwargs):
                observation = original_observer(*args, **kwargs)
                terminal_path.write_bytes(b"{synthetic changed terminal\n")
                return observation
            with patch.object(subject.anchors, "_observe_original_git_anchors_held", side_effect=replace_after_observation), \
                 patch.object(actor.WorkSessionActorStore, "save", side_effect=AssertionError("actor completed")), \
                 patch.object(terminal, "_build_git_terminal_record", side_effect=AssertionError("evidence repaired")):
                with self.assertRaises(subject.WorkSessionGitWorkflowError):
                    self.resume(held)
            self.assertIsNotNone(self.routing._read(current=False).pending_operation())
            self.assertEqual(terminal_path.read_bytes(), b"{synthetic changed terminal\n")


if __name__ == "__main__":
    unittest.main()
