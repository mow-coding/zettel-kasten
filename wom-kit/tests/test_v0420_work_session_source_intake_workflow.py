"""Real temporary intake bytes/session claims; synthetic native/key only."""

from contextlib import ExitStack
import inspect
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import test_v0410_source_intake_batch_exact as intake_fixture
from test_v0420_work_session_execution import SessionNative
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import exact_operation_manifest as exact
from wom_kit import source_intake_batch_exact as intake
from wom_kit import work_session_actor as actor
from wom_kit import work_session_establishment as establishment
from wom_kit import work_session_execution as execution
from wom_kit import work_session_registry as registry
from wom_kit import work_session_source_intake_bundle as bundle
from wom_kit import work_session_source_intake_workflow as subject


class _ActiveKey(intake_fixture._KeyProvider):
    def __init__(self):
        super().__init__()
        self.active = False
        self.before_consumer = None

    def use_key(self, root, consumer, *, create_if_missing=False):
        if self.active:
            raise AssertionError("nested key consumer")
        self.active = True
        try:
            if self.before_consumer is not None:
                self.before_consumer(create_if_missing)
            return super().use_key(root, consumer, create_if_missing=create_if_missing)
        finally:
            self.active = False


class SessionSourceIntakeWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.fixture = intake_fixture.SourceIntakeBatchExactTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.root = self.fixture.root
        self.sources = self.fixture._write_request(2)
        self.request = self.fixture.request_path
        self.key, self.native = _ActiveKey(), intake_fixture._Native()
        self.store, _archive = execution._store(self.root)
        self.route = actor.new_task_route_ref()
        with exact.ExactOperationWriterLock(self.root) as held:
            registered = registry.plan_transition(self.store.read(), action="register-app", label="Synthetic app")
            self.store.commit(registered, held_lock=held)
            self.app = registered.result_refs[0]
            original = execution._execute_session_decision_held(self.root, held=held, action="create",
                client_app_ref=self.app, task_route_ref=self.route, label="Synthetic task",
                reviewer_claim="person:fixture", native=SessionNative(), key_provider=self.key)
            self.session = original["work_session_binding"]["work_session_ref"]
            claimed = registry.plan_transition(self.store.read(), action="claim", client_app_ref=self.app,
                                               work_session_ref=self.session)
            self.store.commit(claimed, held_lock=held)
            self.binding = self.store.read().binding(self.session)
            self.claim_ref = self.store.read()._document["sessions"][self.session]["claim_ref"]
            self.routing = actor.WorkSessionActorStore(self.store, client_app_ref=self.app, task_route_ref=self.route)
            origin = establishment.EstablishmentSelector.from_document({"action": "create",
                "manifest_sha256": original["manifest_sha256"],
                "context_sha256": original["exact_human_approval_reference"]["context_sha256"]})
            self.selected = self.routing.save(expected_sha256=None, held_lock=held,
                work_session_ref=self.session, claim_ref=self.claim_ref, observed_binding=self.binding,
                established_origin=origin)

    def files(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file() and path.name != ".writer.lock"}

    def execute(self, held, **changes):
        values = dict(held=held, client_app_ref=self.app, task_route_ref=self.route,
            work_session_ref=self.session, reviewer_claim="person:intake-reviewer",
            native=self.native, key_provider=self.key)
        values.update(changes)
        return subject._execute_session_source_intake_batch_held(self.root, self.request, **values)

    def resume(self, held, **changes):
        values = dict(held=held, client_app_ref=self.app, task_route_ref=self.route, key_provider=self.key)
        values.update(changes)
        return subject._resume_session_source_intake_batch_held(self.root, **values)

    def refuse(self, call, code=None, completed=False):
        with self.assertRaises(subject.WorkSessionIntakeWorkflowError) as caught:
            call()
        if code is not None:
            self.assertEqual(caught.exception.code, code)
        self.assertEqual(caught.exception.original_completion_verified, completed)
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)
        self.assertNotIn(str(self.root), repr(caught.exception))

    def retained(self, held):
        selected = self.routing._read(current=False)
        pointer = (selected.pending_operation().document() if selected.pending_operation() is not None
                   else selected.document()["last_completed_operation"])
        return bundle._load_original_source_intake_context_held(self.root,
            manifest_sha256=pointer["manifest_sha256"], held=held)

    def cut_before_runner(self, held):
        with patch.object(intake, "_run_session_source_intake_batch_exact_operation",
                          side_effect=OSError("private synthetic crash")):
            self.refuse(lambda: self.execute(held), "exact_human_approval_state_unknown")
        self.assertIsNotNone(self.routing._read(current=False).pending_operation())

    def test_fresh_preview_apply_and_completed_original_replay_without_source_or_request(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            before = self.files()
            preview = subject._preview_session_source_intake_batch_held(self.root, self.request,
                held=held, client_app_ref=self.app, task_route_ref=self.route,
                work_session_ref=self.session, key_provider=self.key)
            self.assertTrue(preview["ready_for_write"])
            self.assertFalse(preview["original_completion_verified"])
            self.assertEqual(self.files(), before)
            registry_before = self.store.read().sha256
            result = self.execute(held)
            self.assertTrue(result["ok"] and result["original_completion_verified"])
            self.assertTrue(result["current_claim_ownership_verified"] and result["actor_completion_published"])
            self.assertEqual(self.native.calls, 1)
            bound = self.retained(held)
            for item in bound.prepared.plan.items:
                self.assertEqual((self.root / item.receipt_relative_path).read_bytes(), item.receipt_bytes)
            artifact = bound.prepared.plan.prepared_capture_request
            self.assertEqual((self.root / artifact.relative_path).read_bytes(), artifact.request_bytes)
            self.assertEqual(self.store.read().sha256, registry_before)
            self.request.unlink()
            for path in self.sources:
                path.unlink()
            before = self.files()
            with patch.object(intake, "plan_source_intake_batch", side_effect=AssertionError("replan")), \
                 patch.object(intake, "_run_session_source_intake_batch_exact_operation", side_effect=AssertionError("writer")), \
                 patch.object(approval._ClaimedExactHumanApproval, "exact_terminal_record_mac", side_effect=AssertionError("sign")), \
                 patch.object(actor.WorkSessionActorStore, "save", side_effect=AssertionError("actor rewrite")):
                resumed = self.resume(held)
            self.assertTrue(resumed["original_completion_verified"] and resumed["original_operation_already_completed"])
            self.assertFalse(resumed["writes_performed"] or resumed["actor_completion_published"])
            self.assertEqual(self.files(), before)
            for marker in (str(self.root), self.claim_ref, self.app, self.route, self.session,
                           "batch-2", "source-1", "source-2"):
                self.assertNotIn(marker, json.dumps(result) + json.dumps(resumed) + json.dumps(preview))

    def test_precheckpoint_resume_uses_same_context_claim_and_retained_request(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            self.cut_before_runner(held)
            bound = self.retained(held)
            original_raw = bound._raw
            claim_names = set(self.root.joinpath(approval.CLAIMS_RELATIVE_ROOT).glob("*.json"))
            self.request.unlink()
            with patch.object(intake, "plan_source_intake_batch", side_effect=AssertionError("replan")), \
                 patch.object(bundle, "_save_original_source_intake_context_held", side_effect=AssertionError("context rewrite")):
                result = self.resume(held)
            self.assertTrue(result["ok"])
            self.assertEqual(result["started_resume_state"], "authenticated_before_first_checkpoint")
            self.assertEqual(self.retained(held)._raw, original_raw)
            self.assertEqual(set(self.root.joinpath(approval.CLAIMS_RELATIVE_ROOT).glob("*.json")), claim_names)
            self.assertEqual(self.native.calls, 1)

    def test_partial_receipts_resume_without_rewriting_original_receipt(self):
        calls = []
        original = intake._Writer.write_field
        def cut(writer, **kwargs):
            calls.append(kwargs["target_ref"])
            if len(calls) == 2:
                raise OSError("private cut between receipts")
            return original(writer, **kwargs)
        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(intake._Writer, "write_field", new=cut):
                self.refuse(lambda: self.execute(held), "exact_human_approval_state_unknown")
            first = self.root / calls[0]
            raw = first.read_bytes()
            self.request.unlink()
            with patch.object(intake, "plan_source_intake_batch", side_effect=AssertionError("replan")):
                result = self.resume(held)
            self.assertTrue(result["ok"])
            self.assertEqual(result["started_resume_state"], "checkpoint_present")
            self.assertEqual(first.read_bytes(), raw)
            self.assertEqual(self.native.calls, 1)

    def test_started_common_final_tail_and_succeeded_actor_tail_are_read_only_domain_replays(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(approval._ClaimedExactHumanApproval, "finalize_succeeded", side_effect=OSError("cut after final")):
                self.refuse(lambda: self.execute(held), "exact_human_approval_state_unknown")
            before = self.files()
            with patch.object(intake, "_run_session_source_intake_batch_exact_operation", side_effect=AssertionError("domain writer")), \
                 patch.object(approval._ClaimedExactHumanApproval, "exact_terminal_record_mac", side_effect=AssertionError("resign")):
                result = self.resume(held)
            self.assertTrue(result["ok"])
            self.assertEqual(result["started_resume_state"], "common_final_present")
            self.assertEqual(self.native.calls, 1)
            for path, raw in before.items():
                if not path.startswith(approval.CLAIMS_RELATIVE_ROOT):
                    self.assertEqual(self.files()[path], raw)

    def test_after_click_source_drift_refuses_before_context_pending_or_claim(self):
        original_show = self.native.show
        def click(**kwargs):
            result = original_show(**kwargs)
            self.sources[0].write_bytes(b"changed")
            return result
        with exact.ExactOperationWriterLock(self.root) as held, patch.object(self.native, "show", side_effect=click):
            old_actor = self.routing._read(current=False)._raw
            claims = list(self.root.joinpath(approval.CLAIMS_RELATIVE_ROOT).glob("*.json"))
            with patch.object(bundle, "_save_original_source_intake_context_held") as save:
                self.refuse(lambda: self.execute(held), "work_session_intake_changed")
            save.assert_not_called()
            self.assertEqual(self.routing._read(current=False)._raw, old_actor)
            self.assertEqual(list(self.root.joinpath(approval.CLAIMS_RELATIVE_ROOT).glob("*.json")), claims)

    def test_concrete_guard_refuses_actor_drift_at_real_publication_boundary(self):
        original_write = intake.archive_services._write_activity_group_bytes_new_file_bound
        changed = []
        def write(binding, path, raw, **kwargs):
            if not path.name.endswith(".source-intake-plan.json"):
                return original_write(binding, path, raw, **kwargs)
            self.assertTrue(path.parent.samefile(self.root / "receipts" / "sources"))
            if not changed:
                changed.append(path)
                selected = self.routing._read(current=False)
                self.routing.save(expected_sha256=selected.sha256, held_lock=held,
                    work_session_ref=self.session, observed_binding=self.binding, claim_ref=self.claim_ref,
                    pending_operation=actor.PendingOperationSelector.from_document({
                        **selected.pending_operation().document(), "context_sha256": "sha256:" + "f" * 64}))
            return original_write(binding, path, raw, **kwargs)
        with exact.ExactOperationWriterLock(self.root) as held, \
             patch.object(intake.archive_services, "_write_activity_group_bytes_new_file_bound", side_effect=write):
            self.refuse(lambda: self.execute(held), "exact_human_approval_state_unknown")
            self.assertTrue(changed)
            self.assertFalse(changed[0].exists())

    def test_provider_entry_source_drift_refuses_before_context_or_pending_publication(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            old_actor = self.routing._read(current=False)._raw
            entered = []
            def change(create_if_missing):
                if create_if_missing:
                    entered.append(True)
                    self.sources[0].write_bytes(b"private changed source")
            self.key.before_consumer = change
            with patch.object(bundle, "_save_original_source_intake_context_held") as save:
                self.refuse(lambda: self.execute(held))
            self.assertEqual(entered, [True])
            save.assert_not_called()
            self.assertEqual(self.routing._read(current=False)._raw, old_actor)

    def test_source_mutating_callback_cannot_run_during_publication_but_notifications_resume(self):
        original_write = intake.archive_services._write_activity_group_bytes_new_file_bound
        inside, published, attacks, notifications = [False], [], [], []
        original_source = self.sources[0].read_bytes()
        def write(binding, path, raw, **kwargs):
            if not path.name.endswith(".source-intake-plan.json"):
                return original_write(binding, path, raw, **kwargs)
            self.assertTrue(path.parent.samefile(self.root / "receipts" / "sources"))
            inside[0] = True
            try:
                result = original_write(binding, path, raw, **kwargs)
                published.append(path)
                return result
            finally:
                inside[0] = False
        def progress(event):
            if type(event) is exact.ExactOperationProgress:
                if inside[0] and not attacks:
                    attacks.append(True)
                    self.sources[0].write_bytes(b"mutated after the final source hash")
                elif published and not inside[0]:
                    notifications.append(event.stage)
        with exact.ExactOperationWriterLock(self.root) as held, \
             patch.object(intake.archive_services, "_write_activity_group_bytes_new_file_bound", side_effect=write), \
             patch.object(exact, "HEARTBEAT_INTERVAL_SECONDS", 0):
            result = self.execute(held, progress_hook=progress)
            self.assertTrue(result["original_completion_verified"])
            self.assertEqual(attacks, [])
            self.assertTrue(notifications, "progress must resume at the safe field boundary")
            self.assertEqual(self.sources[0].read_bytes(), original_source)

    def test_final_source_eof_callback_cannot_change_previously_hashed_bytes(self):
        original_digest = intake._stable_source_digest
        at_eof, observed_eof, attacks = [False], [], []
        original_source = self.sources[0].read_bytes()
        def digest(path, **kwargs):
            callback = kwargs.get("heartbeat")
            selected = self.routing._read(current=False)
            if not path.samefile(self.sources[0]) or selected.pending_operation() is None:
                return original_digest(path, **kwargs)
            calls = [0]
            def heartbeat():
                calls[0] += 1
                at_eof[0] = calls[0] == 2  # One small data chunk, then the real EOF read.
                if at_eof[0]:
                    observed_eof.append(True)
                try:
                    callback()
                finally:
                    at_eof[0] = False
            return original_digest(path, **{**kwargs, "heartbeat": heartbeat})
        def progress(event):
            if type(event) is exact.ExactOperationProgress and at_eof[0] and not attacks:
                attacks.append(True)
                info = self.sources[0].stat()
                self.sources[0].write_bytes(b"x" * len(original_source))
                os.utime(self.sources[0], ns=(info.st_atime_ns, info.st_mtime_ns))
        with exact.ExactOperationWriterLock(self.root) as held, \
             patch.object(intake, "_stable_source_digest", side_effect=digest), \
             patch.object(exact, "HEARTBEAT_INTERVAL_SECONDS", 0):
            self.assertTrue(self.execute(held, progress_hook=progress)["ok"])
            self.assertTrue(observed_eof)
            self.assertEqual(attacks, [])
            self.assertEqual(self.sources[0].read_bytes(), original_source)

    def test_source_drift_in_pre_entry_callback_is_rejected_not_silently_ignored(self):
        changed = []
        def progress(event):
            if type(event) is exact.ExactOperationProgress and event.stage == "item_started" and not changed:
                changed.append(True)
                self.sources[0].write_bytes(b"changed before protected source read")
        with exact.ExactOperationWriterLock(self.root) as held:
            self.refuse(lambda: self.execute(held, progress_hook=progress), "exact_human_approval_state_unknown")
            self.assertEqual(changed, [True])
            self.assertFalse((self.root / self.retained(held).prepared.plan.items[0].receipt_relative_path).exists())

    def test_safe_post_field_callback_cancellation_preserves_lock_and_original_resume(self):
        original_write = intake.archive_services._write_activity_group_bytes_new_file_bound
        published, inside, cancelled = [], [False], []
        def write(binding, path, raw, **kwargs):
            if not path.name.endswith(".source-intake-plan.json"):
                return original_write(binding, path, raw, **kwargs)
            self.assertTrue(path.parent.samefile(self.root / "receipts" / "sources"))
            inside[0] = True
            try:
                result = original_write(binding, path, raw, **kwargs)
                published.append(path)
                return result
            finally:
                inside[0] = False
        def progress(event):
            if type(event) is exact.ExactOperationProgress and published and not inside[0] and not cancelled:
                cancelled.append(True)
                raise KeyboardInterrupt()
        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(intake.archive_services, "_write_activity_group_bytes_new_file_bound", side_effect=write), \
                 patch.object(exact, "HEARTBEAT_INTERVAL_SECONDS", 0):
                self.refuse(lambda: self.execute(held, progress_hook=progress), "exact_human_approval_state_unknown")
            held.verify_held()
            self.assertEqual(cancelled, [True])
            first = published[0]
            raw = first.read_bytes()
            self.assertTrue(self.resume(held)["ok"])
            self.assertEqual(first.read_bytes(), raw)
            self.assertEqual(self.native.calls, 1)

    def test_missing_original_claim_stays_pending_without_native_or_key_creation(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(broker, "_claim_exact_human_approval_core", side_effect=OSError("before approval claim")):
                self.refuse(lambda: self.execute(held))
            pending = self.routing._read(current=False)._raw
            before = self.files()
            key_start = len(self.key.create_if_missing_calls)
            self.refuse(lambda: self.resume(held), "work_session_intake_original_approval_missing")
            self.assertEqual(self.files(), before)
            self.assertEqual(self.routing._read(current=False)._raw, pending)
            self.assertEqual(self.native.calls, 1)
            self.assertNotIn(True, self.key.create_if_missing_calls[key_start:])

    def test_completed_output_fact_survives_current_owner_loss_without_actor_repair(self):
        original_save = actor.WorkSessionActorStore.save
        def cut(store, **kwargs):
            completed = kwargs.get("last_completed_operation")
            if completed is not None and completed.document()["kind"] == "source_intake_batch":
                raise OSError("private lost actor acknowledgement")
            return original_save(store, **kwargs)
        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(actor.WorkSessionActorStore, "save", new=cut):
                self.refuse(lambda: self.execute(held), completed=True)
            pending = self.routing._read(current=False)._raw
            with patch.object(self.store.__class__, "require_claimed_binding", side_effect=OSError("owner unavailable")), \
                 patch.object(intake, "_run_session_source_intake_batch_exact_operation", side_effect=AssertionError("write")):
                self.refuse(lambda: self.resume(held), "work_session_intake_ownership_unavailable", completed=True)
            self.assertEqual(self.routing._read(current=False)._raw, pending)
            self.assertTrue(self.resume(held)["original_completion_verified"])

    def test_legacy_admission_stays_closed_and_pending_runner_decode_cost_is_not_per_field(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            self.cut_before_runner(held)
            bound = self.retained(held)
            with self.assertRaises(intake.SourceIntakeBatchExactError) as caught:
                intake._require_legacy_unbound_plan(bound.prepared.plan)
            self.assertEqual(caught.exception.code, "source_intake_batch_scope_context_required")
            decode_counts = []
            original_writer = intake._Writer.write_field
            with patch.object(bundle, "_decode_prepared", wraps=bundle._decode_prepared) as decode:
                def observe(writer, **kwargs):
                    before = decode.call_count
                    for _index in range(3):
                        kwargs["heartbeat"]()
                    result = original_writer(writer, **kwargs)
                    decode_counts.append(decode.call_count - before)
                    return result
                with patch.object(intake._Writer, "write_field", new=observe):
                    self.assertTrue(self.resume(held)["ok"])
            self.assertEqual(decode_counts, [0, 0, 0])

    def test_resume_accepts_no_request_reviewer_manifest_approval_or_native_selector(self):
        names = set(inspect.signature(subject._resume_session_source_intake_batch_held).parameters)
        self.assertEqual(names, {"root", "held", "client_app_ref", "task_route_ref", "work_session_ref", "key_provider", "progress_hook"})


if __name__ == "__main__":
    unittest.main()
