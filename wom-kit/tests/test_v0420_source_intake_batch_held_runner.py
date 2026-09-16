"""The held extraction preserves legacy authority and does not open sessions."""

import inspect
import shutil
import unittest
from dataclasses import replace
from unittest import mock

import test_v0410_source_intake_batch_exact as legacy
from test_v0420_work_session_binding import binding_fixture
from wom_kit import exact_human_approval as approval
from wom_kit import exact_operation_manifest as exact
from wom_kit import source_intake_batch_exact as subject
from wom_kit.exact_human_approval_windows import _ExactHumanApprovalDecision


class SourceIntakeBatchHeldRunnerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = legacy.SourceIntakeBatchExactTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.fixture._write_request(1)
        self.root = self.fixture.root
        self.plan = subject.plan_source_intake_batch(self.root, self.fixture.request_path)
        self.context = subject.approval_context(self.plan, reviewer_claim=legacy.REVIEWER)

    def claim(self, context=None):
        context = context or self.context
        decision = _ExactHumanApprovalDecision(
            approved=True, synthetic_acknowledged=False, reason_code="exact_human_approval_approved",
            plan_sha256=context.plan_sha256, target_binding_sha256=context.target_binding_sha256,
        )
        claim = approval._claim_exact_human_approval_core(self.root, context, decision, bytes(range(32)))
        self.addCleanup(claim.close)
        return claim

    def snapshot(self):
        # Windows byte-range locking intentionally forbids a second reader of
        # the held lock byte. All claim/checkpoint/receipt/source bytes remain
        # included; the real lock verifies its own identity independently.
        lock_path = self.root / exact.EXACT_OPERATION_LOCAL_ROOT / ".writer.lock"
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path != lock_path and path.is_file()}

    def run_held(self, held, claim, **changes):
        values = dict(context=self.context, claim=claim, writer_lock=held, resume=False, progress_hook=None)
        values.update(changes)
        return subject._run_source_intake_batch_exact_operation(self.plan, **values)

    def assert_fixed_error(self, code, call):
        with self.assertRaises(subject.SourceIntakeBatchExactError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)
        self.assertNotIn(str(self.root), repr(caught.exception))

    def test_held_success_keeps_legacy_bytes_and_authenticated_common_receipt_without_nested_lock(self):
        original_manifest = self.plan.manifest.document()
        original_context = approval.exact_human_approval_context_sha256(self.context)
        claim = self.claim()
        with exact.exact_operation_writer_lock(self.root) as held, \
             mock.patch.object(subject, "exact_operation_writer_lock", side_effect=AssertionError("nested lock")), \
             mock.patch.object(subject, "_production_key_provider", side_effect=AssertionError("nested key")):
            result = self.run_held(held, claim)
            held.verify_held()
            claim.assert_ready_for_context(self.context)  # Runner does not finalize the broker's claim.
        self.assertTrue(result["ok"])
        self.assertEqual(self.plan.manifest.document(), original_manifest)
        self.assertEqual(approval.exact_human_approval_context_sha256(self.context), original_context)
        self.assertNotIn("work_session_binding", original_manifest)
        self.assertNotIn("extension_sha256", original_manifest)
        for item in self.plan.items:
            self.assertEqual((self.root / item.receipt_relative_path).read_bytes(), item.receipt_bytes)
        artifact = self.plan.prepared_capture_request
        self.assertEqual((self.root / artifact.relative_path).read_bytes(), artifact.request_bytes)
        final = exact.load_exact_operation_final_receipt_read_only(self.root, result["execution_sha256"])
        self.assertEqual(final["result"]["manifest_sha256"], self.plan.manifest.manifest_sha256)
        self.assertIn("completion_authentication", final["result"])
        self.assertNotIn("work_session_binding_sha256", final["result"])
        self.assertNotIn("extension_sha256", final["result"])
        claim.finalize_succeeded()
        reconciled = subject.reconcile_source_intake_batch(
            self.plan, execution_sha256=result["execution_sha256"], key_provider=legacy._KeyProvider(),
        )
        self.assertTrue(reconciled["ok"] and reconciled["completion_authentication_verified"])

    def test_legacy_execute_delegates_once_and_keeps_one_request_read(self):
        native, keys = legacy._Native(), legacy._KeyProvider()
        with mock.patch.object(subject, "_execute_exact_human_approved_write",
                               side_effect=self.fixture._workflow(native, keys)), \
             mock.patch.object(subject, "_run_source_intake_batch_exact_operation",
                               wraps=subject._run_source_intake_batch_exact_operation) as runner, \
             mock.patch.object(subject, "_stable_request_bytes", wraps=subject._stable_request_bytes) as reads:
            result = subject.execute_source_intake_batch(self.plan, reviewer_claim=legacy.REVIEWER)
        self.assertTrue(result["ok"])
        self.assertEqual(native.calls, 1)
        self.assertEqual(runner.call_count, 1)
        self.assertEqual(reads.call_count, 1)
        self.assertIs(runner.call_args.args[0], self.plan)
        self.assertIs(type(runner.call_args.kwargs["writer_lock"]), exact.ExactOperationWriterLock)
        self.assertFalse(runner.call_args.kwargs["resume"])

    def test_real_wrong_archive_and_unheld_locks_refuse_without_writes(self):
        claim = self.claim()
        other = self.fixture.workspace / "other-archive"
        shutil.copytree(self.root, other)
        unheld = exact.exact_operation_writer_lock(self.root)
        with exact.exact_operation_writer_lock(other) as foreign:
            for held in (foreign, unheld):
                before = self.snapshot()
                self.assert_fixed_error("source_intake_batch_lock_required", lambda: self.run_held(held, claim))
                self.assertEqual(self.snapshot(), before)
        with exact.exact_operation_writer_lock(self.root) as released:
            pass
        before = self.snapshot()
        self.assert_fixed_error("source_intake_batch_lock_required", lambda: self.run_held(released, claim))
        self.assertEqual(self.snapshot(), before)

    def test_legacy_invalid_claim_refuses_before_lock_and_blocked_plan_keeps_original_errors(self):
        other_context = replace(self.context, reviewer_claim="person:other-synthetic-reviewer")
        wrong_claim = self.claim(other_context)
        before = self.snapshot()
        with mock.patch.object(subject, "exact_operation_writer_lock") as lock:
            with self.assertRaises(subject.SourceIntakeBatchExactError) as caught:
                subject._execute_core(self.plan, wrong_claim, self.context, progress_hook=None)
            self.assertEqual(caught.exception.code, "source_intake_batch_approval_required")
            lock.assert_not_called()
        blocked = replace(self.plan, manifest=None, state="blocked")
        with mock.patch.object(subject, "_execute_exact_human_approved_write") as broker:
            self.assert_fixed_error("source_intake_batch_plan_blocked",
                lambda: subject.execute_source_intake_batch(blocked, reviewer_claim=legacy.REVIEWER))
            self.assert_fixed_error("source_intake_batch_plan_digest_mismatch",
                lambda: subject.execute_source_intake_batch(blocked, reviewer_claim=legacy.REVIEWER,
                    expected_plan_sha256="sha256:" + "a" * 64))
            broker.assert_not_called()
        self.assertEqual(self.snapshot(), before)

    def test_held_resume_reuses_original_claim_and_checkpoint_without_new_approval(self):
        claim = self.claim()
        original_reference = claim.public_reference()
        original_write = subject._Writer.write_field
        calls = 0

        def interrupt(writer, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("synthetic-interruption")
            return original_write(writer, **kwargs)

        with exact.exact_operation_writer_lock(self.root) as held, \
             mock.patch.object(subject._Writer, "write_field", new=interrupt):
            with self.assertRaises(exact.ExactOperationManifestError):
                self.run_held(held, claim)
        receipt = self.root / self.plan.items[0].receipt_relative_path
        original_receipt = receipt.read_bytes()
        resumed = subject.plan_source_intake_batch(self.root, self.fixture.request_path)
        self.assertEqual(resumed.manifest.document(), self.plan.manifest.document())
        self.assertTrue(resumed.resume_candidate)
        with exact.exact_operation_writer_lock(self.root) as held, \
             mock.patch.object(subject, "exact_operation_writer_lock", side_effect=AssertionError("nested lock")), \
             mock.patch.object(subject, "_production_key_provider", side_effect=AssertionError("nested key")), \
             mock.patch.object(subject, "_execute_exact_human_approved_write", side_effect=AssertionError("new approval")):
            result = subject._run_source_intake_batch_exact_operation(resumed, context=self.context,
                claim=claim, writer_lock=held, resume=True, progress_hook=None)
        self.assertTrue(result["ok"])
        self.assertEqual(receipt.read_bytes(), original_receipt)
        self.assertEqual(claim.public_reference(), original_reference)
        claim.assert_ready_for_context(self.context)
        claim.finalize_succeeded()
        reconciled = subject.reconcile_source_intake_batch(resumed,
            execution_sha256=result["execution_sha256"], key_provider=legacy._KeyProvider())
        self.assertTrue(reconciled["completion_authentication_verified"])

    def test_original_context_and_real_claim_mismatch_refuse_before_metadata_or_receipt_write(self):
        claim = self.claim()
        other_context = replace(self.context, reviewer_claim="person:other-synthetic-reviewer")
        other_claim = self.claim(other_context)
        with exact.exact_operation_writer_lock(self.root) as held:
            for changes in ({"context": other_context}, {"claim": other_claim}):
                before = self.snapshot()
                self.assert_fixed_error("source_intake_batch_approval_required",
                    lambda: self.run_held(held, changes.get("claim", claim),
                                          context=changes.get("context", self.context)))
                self.assertEqual(self.snapshot(), before)

    def test_post_approval_request_drift_refuses_before_checkpoint_or_domain_receipt(self):
        claim = self.claim()
        self.fixture.request_path.write_bytes(self.fixture.request_path.read_bytes() + b"\n")
        with exact.exact_operation_writer_lock(self.root) as held:
            before = self.snapshot()
            self.assert_fixed_error("source_intake_batch_state_drifted", lambda: self.run_held(held, claim))
            self.assertEqual(self.snapshot(), before)

    def test_bound_and_new_scope_plans_refuse_public_and_held_and_legacy_apply_routes(self):
        manifest = self.plan.manifest
        binding = binding_fixture(manifest.archive_identity_sha256)
        evidence = manifest.operation_evidence.document()
        evidence["digests"]["session_scope_sha256"] = "sha256:" + "d" * 64
        changed = (
            exact.ExactOperationManifest.build(operation=manifest.operation,
                archive_identity_sha256=manifest.archive_identity_sha256, items=manifest.items,
                operation_evidence=manifest.operation_evidence, work_session_binding=binding),
            exact.ExactOperationManifest.build(operation=manifest.operation,
                archive_identity_sha256=manifest.archive_identity_sha256, items=manifest.items,
                operation_evidence=evidence),
        )
        for modified in changed:
            plan = replace(self.plan, manifest=modified)
            before = self.snapshot()
            with mock.patch.object(subject, "_execute_exact_human_approved_write") as broker, \
                 mock.patch.object(subject, "apply_exact_operation") as apply:
                self.assert_fixed_error("source_intake_batch_scope_context_required",
                    lambda: subject.execute_source_intake_batch(plan, reviewer_claim=legacy.REVIEWER))
                self.assert_fixed_error("source_intake_batch_scope_context_required",
                    lambda: subject._run_source_intake_batch_exact_operation(plan, context=self.context,
                        claim=None, writer_lock=None, resume=True, progress_hook=None))
                self.assert_fixed_error("source_intake_batch_scope_context_required",
                    lambda: subject._apply_with_store(plan, None, None, request_items={}, resume=True,
                        progress_hook=None, completion_authenticator=None))
                broker.assert_not_called()
                apply.assert_not_called()
            self.assertEqual(self.snapshot(), before)

    def test_subclass_capabilities_and_non_boolean_resume_are_not_authority(self):
        claim = self.claim()
        with exact.exact_operation_writer_lock(self.root) as held:
            for name, base in (("context", type(self.context)), ("claim", type(claim)),
                               ("writer_lock", type(held))):
                subclass = type("UntrustedSubclass", (base,), {})
                value = object.__new__(subclass)
                values = dict(context=self.context, claim=claim, writer_lock=held, resume=False, progress_hook=None)
                values[name] = value
                before = self.snapshot()
                code = "source_intake_batch_lock_required" if name == "writer_lock" else "source_intake_batch_approval_required"
                self.assert_fixed_error(code, lambda: subject._run_source_intake_batch_exact_operation(self.plan, **values))
                self.assertEqual(self.snapshot(), before)
            self.assert_fixed_error("source_intake_batch_approval_required", lambda: self.run_held(held, claim, resume=1))
            for base, field in ((type(self.plan), None), (type(self.plan.manifest), "manifest")):
                subclass = type("UntrustedPlanSubclass", (base,), {})
                value = object.__new__(subclass)
                plan = replace(self.plan, manifest=value) if field else value
                self.assert_fixed_error("source_intake_batch_plan_blocked",
                    lambda: subject._run_source_intake_batch_exact_operation(plan, context=self.context,
                        claim=claim, writer_lock=held, resume=False, progress_hook=None))

    def test_internal_signature_has_no_approval_or_key_injection(self):
        parameters = inspect.signature(subject._run_source_intake_batch_exact_operation).parameters
        self.assertEqual(set(parameters), {"plan", "context", "claim", "writer_lock", "resume", "progress_hook"})
        self.assertTrue(all(value.kind is inspect.Parameter.KEYWORD_ONLY
                            for name, value in parameters.items() if name != "plan"))


if __name__ == "__main__":
    unittest.main()
