"""Actual temporary intake originals/claims; no public or timing acceptance."""

from contextlib import ExitStack, contextmanager
import inspect
import os
import unittest
from unittest.mock import patch

import test_v0420_work_session_source_intake_workflow as batch_fixture
import test_v0420_source_intake_record_workflow as record_fixture
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import exact_operation_manifest as exact
from wom_kit import source_intake_batch_exact as batch
from wom_kit import source_intake_record_exact as record
from wom_kit import work_session_actor as actor
from wom_kit import work_session_execution as execution
from wom_kit import work_session_registry as registry
from wom_kit import work_session_source_intake_bundle as batch_bundle
from wom_kit import work_session_source_intake_record_bundle as record_bundle
from wom_kit import work_session_source_intake_record_execution as record_execution
from wom_kit import work_session_source_intake_workflow as batch_workflow
from wom_kit import work_session_source_intake_record_workflow as record_workflow
from wom_kit import work_session_source_intake_rereview as subject


class OriginalIntakeReviewTests(unittest.TestCase):
    def fixture(self, family):
        factory = (batch_fixture.SessionSourceIntakeWorkflowTests if family == "batch"
                   else record_fixture.SessionSourceIntakeRecordWorkflowTests)
        value = factory("runTest")
        value.setUp()
        self.addCleanup(value.doCleanups)
        return value

    def review(self, family, fixture, held, **changes):
        function = (batch_workflow._review_original_session_source_intake_batch_held if family == "batch"
                    else record_workflow._review_original_session_source_intake_record_held)
        values = dict(held=held, client_app_ref=fixture.app, task_route_ref=fixture.route,
                      native=fixture.native, key_provider=fixture.key)
        values.update(changes)
        return function(fixture.root, **values)

    @staticmethod
    def runner(family):
        return ((batch, "_run_session_source_intake_batch_exact_operation") if family == "batch"
                else (record_execution, "_run_session_source_intake_record_exact_operation"))

    @staticmethod
    def claims(fixture):
        return {p.name: p.read_bytes() for p in (fixture.root / approval.CLAIMS_RELATIVE_ROOT).glob("*.json")}

    def cut(self, fixture, held):
        before = self.claims(fixture)
        with patch.object(broker, "_claim_exact_human_approval_core", side_effect=OSError("private preclaim cut")) as claim:
            fixture.refuse(lambda: fixture.execute(held))
        self.assertEqual(claim.call_count, 1)
        self.assertEqual(self.claims(fixture), before)
        pending = fixture.routing._read(current=False)
        self.assertIsNotNone(pending.pending_operation())
        fixture.key.create_if_missing_calls.clear()
        return fixture.retained(held), pending

    @staticmethod
    def targets(family, original):
        plan = original.prepared.plan
        if family == "record":
            return [(plan.receipt_relative_path, plan.receipt_bytes)]
        return ([(item.receipt_relative_path, item.receipt_bytes) for item in plan.items]
                + [(plan.prepared_capture_request.relative_path, plan.prepared_capture_request.request_bytes)])

    def forbid_reconstruction(self, family, stack):
        module, planner, bundle, save = ((batch, "plan_source_intake_batch", batch_bundle,
            "_save_original_source_intake_context_held") if family == "batch" else
            (record, "plan_source_intake_record", record_bundle,
             "_save_original_source_intake_record_context_held"))
        for owner, name in ((module, planner), (bundle, save)):
            stack.enter_context(patch.object(owner, name, side_effect=AssertionError("original reconstructed")))

    def test_both_families_review_exact_original_then_source_free_completed_replay(self):
        for family in ("batch", "record"):
            with self.subTest(family=family):
                f = self.fixture(family)
                with exact.ExactOperationWriterLock(f.root) as held:
                    original, pending = self.cut(f, held)
                    f.refuse(lambda: f.resume(held), "work_session_intake_original_approval_missing")
                    (f.request if family == "batch" else f.plan_path).unlink()
                    if family == "record":
                        f.fixture.selected.unlink()  # Redacted metadata, not source custody.
                    owner, name = self.runner(family)
                    runner = getattr(owner, name)
                    observed = []

                    def apply(prepared, **kwargs):
                        self.assertEqual(f.routing._read(current=False)._raw, pending._raw)
                        self.assertEqual(prepared._raw, original.prepared._raw)
                        self.assertEqual(kwargs["context"], original.context)
                        observed.append(kwargs["claim"].public_reference())
                        return runner(prepared, **kwargs)

                    request = broker._request_exact_human_approval_core

                    def native(*args, **kwargs):
                        self.assertEqual(args[0], original.context)
                        self.assertEqual(f.routing._read(current=False)._raw, pending._raw)
                        return request(*args, **kwargs)

                    with ExitStack() as stack:
                        self.forbid_reconstruction(family, stack)
                        stack.enter_context(patch.object(owner, name, side_effect=apply))
                        stack.enter_context(patch.object(broker, "_request_exact_human_approval_core", side_effect=native))
                        save = stack.enter_context(patch.object(actor.WorkSessionActorStore, "save",
                            autospec=True, side_effect=actor.WorkSessionActorStore.save))
                        result = self.review(family, f, held)
                    self.assertTrue(result["ok"] and result["original_completion_verified"])
                    self.assertTrue(result["current_claim_ownership_verified"] and result["actor_completion_published"])
                    self.assertTrue(result["native_approval_redisplayed"] and result["original_context_preserved"])
                    self.assertEqual(f.native.calls, 2)
                    self.assertEqual(len(observed), 1)
                    self.assertEqual(save.call_count, 1)
                    self.assertEqual(save.call_args.kwargs["expected_sha256"], pending.sha256)
                    self.assertIsNone(save.call_args.kwargs["pending_operation"])
                    self.assertNotIn(True, f.key.create_if_missing_calls)
                    for relative, raw in self.targets(family, original):
                        self.assertEqual((f.root / relative).read_bytes(), raw)
                    if family == "batch":
                        for source in f.sources:
                            source.unlink()
                    before = f.files()
                    with ExitStack() as stack:
                        self.forbid_reconstruction(family, stack)
                        for target, method in ((owner, name), (broker, "_request_exact_human_approval_core"),
                                (approval._ClaimedExactHumanApproval, "finalize_succeeded"),
                                (broker, "_claim_exact_human_approval_core"),
                                (actor.WorkSessionActorStore, "save")):
                            stack.enter_context(patch.object(target, method, side_effect=AssertionError("completed mutation")))
                        replay = self.review(family, f, held)
                    self.assertTrue(replay["original_completion_verified"] and replay["original_operation_already_completed"])
                    self.assertFalse(replay["native_approval_redisplayed"] or replay["writes_performed"])
                    self.assertEqual(f.files(), before)
                    with patch.object(registry.WorkSessionRegistryStore, "require_claimed_binding",
                            side_effect=registry.WorkSessionRegistryError("work_session_claim_conflict")):
                        f.refuse(lambda: self.review(family, f, held),
                            "work_session_intake_ownership_unavailable", completed=True)
                    self.assertEqual(f.files(), before)
                    # A completed pointer is not permission to recreate its
                    # missing claim, even when the complete output is present.
                    claim_path = f.root / approval.CLAIMS_RELATIVE_ROOT / (observed[0]["approval_id"] + ".json")
                    claim_path.unlink()
                    missing = f.files()
                    f.refuse(lambda: self.review(family, f, held), "work_session_intake_original_evidence_invalid")
                    self.assertEqual(f.files(), missing)
                    self.assertEqual(f.native.calls, 2)

    def test_cancel_repeated_preclaim_cut_then_started_delegates_without_new_review(self):
        class Cancel:
            def show(self, **_kwargs):
                return 2, False

        for family in ("batch", "record"):
            with self.subTest(family=family):
                f = self.fixture(family)
                with exact.ExactOperationWriterLock(f.root) as held:
                    _original, pending = self.cut(f, held)
                    before = f.files()
                    f.refuse(lambda: self.review(family, f, held, native=Cancel()), "exact_human_approval_cancelled")
                    self.assertEqual(f.files(), before)
                    with patch.object(broker, "_claim_exact_human_approval_core", side_effect=OSError("repeat cut")):
                        f.refuse(lambda: self.review(family, f, held))
                    self.assertEqual(f.files(), before)
                    owner, name = self.runner(family)
                    with patch.object(owner, name, side_effect=OSError("started before checkpoint")):
                        f.refuse(lambda: self.review(family, f, held), "exact_human_approval_state_unknown")
                    self.assertEqual(f.routing._read(current=False)._raw, pending._raw)
                    calls = f.native.calls
                    with patch.object(broker, "_request_exact_human_approval_core", side_effect=AssertionError("duplicate review")):
                        result = self.review(family, f, held)
                    self.assertTrue(result["original_completion_verified"])
                    self.assertFalse(result["native_approval_redisplayed"])
                    self.assertEqual(f.native.calls, calls)
                    self.assertNotIn(True, f.key.create_if_missing_calls)

    def test_exact_copied_output_never_becomes_absent_preimage(self):
        for family in ("batch", "record"):
            with self.subTest(family=family):
                f = self.fixture(family)
                with exact.ExactOperationWriterLock(f.root) as held:
                    original, pending = self.cut(f, held)
                    for relative, raw in self.targets(family, original):
                        path = f.root / relative
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(raw)
                        before, calls = f.files(), f.native.calls
                        f.refuse(lambda: self.review(family, f, held))
                        self.assertEqual(f.files(), before)
                        self.assertEqual(f.native.calls, calls)
                        self.assertEqual(f.routing._read(current=False)._raw, pending._raw)
                        path.unlink()

    def test_batch_source_drift_before_native_and_after_native_is_rejected(self):
        f = self.fixture("batch")
        with exact.ExactOperationWriterLock(f.root) as held:
            _original, pending = self.cut(f, held)
            source, raw = f.sources[0], f.sources[0].read_bytes()
            source_stat = source.stat()
            source.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
            os.utime(source, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
            count = f.native.calls
            f.refuse(lambda: self.review("batch", f, held))
            self.assertEqual(f.native.calls, count)
            source.write_bytes(raw)
            os.utime(source, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
            native = f.native.show

            def change(**kwargs):
                result = native(**kwargs)
                source.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
                os.utime(source, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
                return result

            before = self.claims(f)
            with patch.object(f.native, "show", side_effect=change):
                f.refuse(lambda: self.review("batch", f, held), "work_session_intake_changed")
            self.assertEqual(f.native.calls, count + 1)
            self.assertEqual(self.claims(f), before)
            self.assertEqual(f.routing._read(current=False)._raw, pending._raw)

    def test_provider_entry_insertion_cannot_create_a_second_claim(self):
        for family in ("batch", "record"):
            with self.subTest(family=family):
                f = self.fixture(family)
                with exact.ExactOperationWriterLock(f.root) as held:
                    original, pending = self.cut(f, held)
                    before = set(self.claims(f))
                    request, use_key, boundary = (broker._request_exact_human_approval_core,
                                                 f.key.use_key, execution._claim_boundary)
                    ready, decisions, inserted = [False], [], []

                    @contextmanager
                    def lease(*args, **kwargs):
                        with boundary(*args, **kwargs) as value:
                            old = ready[0]
                            ready[0] = kwargs.get("create") is True or old
                            try:
                                yield value
                            finally:
                                ready[0] = old

                    def decision(*args, **kwargs):
                        result = request(*args, **kwargs)
                        decisions.append(result)
                        return result

                    def provider(root, consumer, *, create_if_missing=False):
                        def enter(key):
                            if ready[0]:
                                self.assertFalse(create_if_missing)
                                with boundary(f.store, held, create=False) as (bound_root, parent):
                                    claim = broker._claim_exact_human_approval_core(root, original.context,
                                        decisions[-1], key, bound_archive_root=bound_root, claim_parent_binding=parent)
                                    inserted.append(claim.public_reference())
                                    claim.close()
                            return consumer(key)
                        return use_key(root, enter, create_if_missing=create_if_missing)

                    owner, name = self.runner(family)
                    with patch.object(execution, "_claim_boundary", side_effect=lease), \
                         patch.object(broker, "_request_exact_human_approval_core", side_effect=decision), \
                         patch.object(f.key, "use_key", side_effect=provider), \
                         patch.object(owner, name, side_effect=AssertionError("domain effect")):
                        f.refuse(lambda: self.review(family, f, held))
                    self.assertEqual(len(inserted), 1)
                    self.assertEqual(set(self.claims(f)) - before, {inserted[0]["approval_id"] + ".json"})
                    self.assertEqual(f.routing._read(current=False)._raw, pending._raw)
                    for relative, _raw in self.targets(family, original):
                        self.assertFalse((f.root / relative).exists())

    def test_corrupt_ambiguous_failed_and_missing_key_are_not_absence(self):
        for family in ("batch", "record"):
            with self.subTest(family=family):
                f = self.fixture(family)
                with exact.ExactOperationWriterLock(f.root) as held:
                    original, pending = self.cut(f, held)
                    count = f.native.calls
                    with patch.object(f.key, "use_key", side_effect=FileNotFoundError("private key path")):
                        f.refuse(lambda: self.review(family, f, held), "work_session_intake_original_evidence_invalid")
                    refs = []
                    # Real test-only claims made through the existing broker,
                    # never unsigned guessed claim dictionaries.
                    for _index in range(2):
                        decision = broker._request_exact_human_approval_core(original.context,
                            intent=broker.ExactHumanApprovalIntent.live_write, native=f.native)

                        def create(key):
                            with execution._claim_boundary(f.store, held, create=False) as (root, parent):
                                claim = broker._claim_exact_human_approval_core(f.root, original.context, decision, key,
                                    bound_archive_root=root, claim_parent_binding=parent)
                                refs.append(claim.public_reference())
                                claim.close()
                        f.key.use_key(f.root, create, create_if_missing=False)
                    count = f.native.calls
                    before = f.files()
                    f.refuse(lambda: self.review(family, f, held), "work_session_intake_original_evidence_invalid")
                    self.assertEqual(f.files(), before)
                    second = f.root / approval.CLAIMS_RELATIVE_ROOT / (refs[1]["approval_id"] + ".json")
                    second.unlink()
                    first = f.root / approval.CLAIMS_RELATIVE_ROOT / (refs[0]["approval_id"] + ".json")
                    original_claim = first.read_bytes()
                    first.write_bytes(original_claim + b"private malformed")
                    before = f.files()
                    f.refuse(lambda: self.review(family, f, held), "work_session_intake_original_evidence_invalid")
                    self.assertEqual(f.files(), before)
                    first.write_bytes(original_claim)

                    def fail(claim):
                        claim.finalize_failed("synthetic_failure")
                        return {"ok": False}
                    broker._resume_exact_human_approved_transaction_auto_core(f.root, original.context,
                        lambda _claim: True, fail, lambda _claim: True, lambda _claim: None, key_provider=f.key,
                        resume_boundary=lambda: execution._claim_boundary(f.store, held, create=False))
                    before = f.files()
                    f.refuse(lambda: self.review(family, f, held), "work_session_intake_original_evidence_invalid")
                    self.assertEqual(f.files(), before)
                    self.assertEqual(f.native.calls, count)
                    self.assertEqual(f.routing._read(current=False)._raw, pending._raw)

    def test_scope_origin_and_provider_entry_evidence_drift_preserve_pending(self):
        for family in ("batch", "record"):
            with self.subTest(family=family):
                f = self.fixture(family)
                with exact.ExactOperationWriterLock(f.root) as held:
                    original, pending = self.cut(f, held)
                    calls = f.native.calls
                    f.refuse(lambda: self.review(family, f, held, work_session_ref="work_session:wrong"))
                    with patch.object(registry.WorkSessionRegistryStore, "require_claimed_binding",
                            side_effect=registry.WorkSessionRegistryError("work_session_claim_conflict")):
                        f.refuse(lambda: self.review(family, f, held))
                    scope = original.prepared.scope.document()
                    path = f.root / "receipts/ops/exact-operations" / (scope["establishment_execution_sha256"][7:] + ".json")
                    raw = path.read_bytes()
                    entered = []

                    def change(_create):
                        if not entered:
                            entered.append(True)
                            path.write_bytes(raw + b" ")
                    f.key.before_consumer = change
                    f.refuse(lambda: self.review(family, f, held))
                    self.assertEqual(entered, [True])
                    self.assertEqual(f.native.calls, calls)
                    self.assertEqual(path.read_bytes(), raw + b" ")
                    self.assertEqual(f.routing._read(current=False)._raw, pending._raw)

    def test_closed_wrapper_signatures_and_family_are_not_caller_plugins(self):
        for function in (batch_workflow._review_original_session_source_intake_batch_held,
                         record_workflow._review_original_session_source_intake_record_held):
            self.assertEqual(set(inspect.signature(function).parameters),
                {"root", "held", "client_app_ref", "task_route_ref", "work_session_ref", "native", "key_provider", "progress_hook"})
        for invalid in ("batch", "record", None, object(), batch_workflow):
            with self.assertRaises(batch_workflow.WorkSessionIntakeWorkflowError):
                subject._workflow(invalid)


if __name__ == "__main__":
    unittest.main()
