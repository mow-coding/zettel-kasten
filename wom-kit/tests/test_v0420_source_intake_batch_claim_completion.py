"""Read-only succeeded intake proof inside the original broker key consumer."""

from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
import json
import shutil
import unittest
from unittest import mock

import test_v0410_source_intake_batch_exact as legacy
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as workflow
from wom_kit import exact_operation_manifest as exact
from wom_kit import source_intake_batch_exact as subject
from wom_kit.exact_human_approval_windows import _ExactHumanApprovalDecision


class SourceIntakeBatchClaimCompletionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = legacy.SourceIntakeBatchExactTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.sources = self.fixture._write_request(1)
        self.root = self.fixture.root
        self.plan = subject.plan_source_intake_batch(self.root, self.fixture.request_path)
        self.context = subject.approval_context(self.plan, reviewer_claim=legacy.REVIEWER)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.held = self.stack.enter_context(exact.exact_operation_writer_lock(self.root))

    def claim(self, context=None, root=None):
        context = context or self.context
        decision = _ExactHumanApprovalDecision(
            approved=True, synthetic_acknowledged=False, reason_code="exact_human_approval_approved",
            plan_sha256=context.plan_sha256, target_binding_sha256=context.target_binding_sha256,
        )
        claim = approval._claim_exact_human_approval_core(root or self.root, context, decision, bytes(range(32)))
        self.addCleanup(claim.close)
        return claim

    def complete(self, *, finalize=True):
        claim = self.claim()
        result = subject._run_source_intake_batch_exact_operation(
            self.plan, context=self.context, claim=claim, writer_lock=self.held,
            resume=False, progress_hook=None,
        )
        if finalize:
            claim.finalize_succeeded()
        return claim, result

    def verify(self, claim, **changes):
        values = dict(context=self.context, claim=claim, writer_lock=self.held)
        values.update(changes)
        return subject._verify_source_intake_batch_completion_with_claim_held(self.plan, **values)

    def snapshot(self):
        lock_path = self.root / exact.EXACT_OPERATION_LOCAL_ROOT / ".writer.lock"
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path != lock_path and path.is_file()}

    def assert_refused_read_only(self, claim, *, code=None, **changes):
        before = self.snapshot()
        with self.assertRaises(subject.SourceIntakeBatchExactError) as caught:
            self.verify(claim, **changes)
        if code is not None:
            self.assertEqual(caught.exception.code, code)
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)
        self.assertNotIn(str(self.root), repr(caught.exception))
        self.assertEqual(self.snapshot(), before)

    def test_actual_broker_succeeded_finalizer_reuses_active_key_and_held_lock_without_writes(self):
        observations = []
        keys = legacy._KeyProvider()
        active = False
        original_use_key = keys.use_key

        def use_key(root, consumer, *, create_if_missing=False):
            nonlocal active
            self.assertFalse(active, "nested key consumer")
            active = True
            try:
                return original_use_key(root, consumer, create_if_missing=create_if_missing)
            finally:
                active = False

        def finalizer(claim):
            self.assertTrue(active)
            self.assertEqual(claim.status, "succeeded")
            before = self.snapshot()
            with mock.patch.object(subject, "_production_key_provider", side_effect=AssertionError("nested key")), \
                 mock.patch.object(subject, "audit_exact_human_approval_succeeded_terminal_record_read_only",
                                   side_effect=AssertionError("nested audit key")), \
                 mock.patch.object(subject, "exact_operation_writer_lock", side_effect=AssertionError("nested lock")), \
                 mock.patch.object(approval._ClaimedExactHumanApproval, "exact_terminal_record_mac",
                                   side_effect=AssertionError("signing is not verification")):
                observations.append(self.verify(claim))
            self.assertEqual(self.snapshot(), before)
            self.held.verify_held()

        with mock.patch.object(keys, "use_key", side_effect=use_key):
            result = workflow._execute_exact_human_approved_write_core(
                self.root, self.context,
                lambda claim: subject._run_source_intake_batch_exact_operation(
                    self.plan, context=self.context, claim=claim, writer_lock=self.held,
                    resume=False, progress_hook=None),
                native=legacy._Native(), key_provider=keys, claim_succeeded_finalizer=finalizer,
            )
        self.assertTrue(result["ok"])
        self.assertEqual(keys.calls, 1)
        verified = observations[0]
        self.assertTrue(verified["ok"] and verified["completion_authentication_verified"])
        self.assertTrue(verified["independent_verification"] and verified["prepared_capture_request_verified"])
        self.assertFalse(verified["writes_performed"] or verified["source_bytes_reverified"])
        self.assertEqual(verified["execution_sha256"], result["execution_sha256"])
        final = exact.load_exact_operation_final_receipt_read_only(self.root, result["execution_sha256"])
        self.assertEqual(verified["common_final_receipt_sha256"], final["receipt_sha256"])
        self.assertEqual(verified["context_sha256"], approval.exact_human_approval_context_sha256(self.context))

    def test_started_with_complete_outputs_and_succeeded_without_final_both_refuse(self):
        claim, result = self.complete(finalize=False)
        self.assert_refused_read_only(claim)
        claim.finalize_succeeded()
        final_path = self.fixture._final_receipt_path(result["execution_sha256"])
        final_path.unlink()
        self.assert_refused_read_only(claim, code="source_intake_batch_completion_evidence_required")

    def test_wrong_claim_context_closed_claim_and_copied_archive_refuse(self):
        claim, _ = self.complete()
        other_context = replace(self.context, reviewer_claim="person:other-synthetic-reviewer")
        for supplied in (None, object(), self.claim(other_context)):
            self.assert_refused_read_only(supplied)
        self.assert_refused_read_only(claim, context=other_context)
        other = self.fixture.workspace / "copied-archive"
        shutil.copytree(self.root, other, ignore=shutil.ignore_patterns(".writer.lock"))
        other_claim = self.claim(root=other)
        other_claim.finalize_succeeded()
        self.assert_refused_read_only(other_claim, code="source_intake_batch_approval_required")
        claim.close()
        self.assert_refused_read_only(claim)

    def test_missing_released_foreign_and_privacy_bearing_lock_failures_refuse(self):
        claim, _ = self.complete()
        other = self.fixture.workspace / "other-archive"
        shutil.copytree(self.root, other, ignore=shutil.ignore_patterns(".writer.lock"))
        with exact.exact_operation_writer_lock(other) as foreign:
            for lock in (None, object(), foreign, exact.exact_operation_writer_lock(self.root)):
                self.assert_refused_read_only(claim, writer_lock=lock, code="source_intake_batch_lock_required")
        self.assert_refused_read_only(claim, writer_lock=foreign, code="source_intake_batch_lock_required")
        with mock.patch.object(subject.os.path, "samefile", side_effect=OSError(str(self.root / "private"))):
            self.assert_refused_read_only(claim, code="source_intake_batch_lock_required")

    def test_whole_receipt_and_capture_request_same_size_changes_refuse(self):
        claim, _ = self.complete()
        targets = [self.root / self.plan.items[0].receipt_relative_path,
                   self.root / self.plan.prepared_capture_request.relative_path]
        for target in targets:
            with self.subTest(target_kind=target.parent.name):
                raw = target.read_bytes()
                target.write_bytes(raw[:-1] + (b" " if raw[-1:] != b" " else b"\n"))
                self.assert_refused_read_only(claim, code="source_intake_batch_state_drifted")
                target.write_bytes(raw)
        self.assertTrue(self.verify(claim)["ok"])

    def test_common_receipt_mac_cannot_be_repaired_with_only_public_hashes(self):
        claim, result = self.complete()
        path = self.fixture._final_receipt_path(result["execution_sha256"])
        final = json.loads(path.read_bytes())
        final["result"]["completion_authentication"]["terminal_mac"] = "hmac-sha256:" + "0" * 64
        basis = dict(final["result"])
        basis.pop("result_sha256")
        final["result"]["result_sha256"] = self.fixture._exact_document_sha256(basis)
        basis = dict(final)
        basis.pop("receipt_sha256")
        final["receipt_sha256"] = self.fixture._exact_document_sha256(basis)
        path.write_bytes(self.fixture._canonical_exact_bytes(final) + b"\n")
        self.assertIsNotNone(exact.load_exact_operation_final_receipt_read_only(self.root, result["execution_sha256"]))
        self.assert_refused_read_only(claim, code="source_intake_batch_completion_evidence_required")

    def test_exact_result_and_reference_guard_matrix(self):
        claim, result = self.complete()
        final = exact.load_exact_operation_final_receipt_read_only(self.root, result["execution_sha256"])
        wrong = "sha256:" + "f" * 64
        mutations = [
            ("status", "pending"), ("mode", "revert"), ("manifest_sha256", wrong),
            ("execution_sha256", wrong), ("approval_binding_sha256", wrong),
            ("item_count", 99), ("field_count", 99), ("operation_evidence", None),
            ("work_session_binding_sha256", wrong), ("extension_sha256", wrong),
        ]
        for name, value in mutations:
            with self.subTest(result_field=name):
                altered = deepcopy(final)
                altered["result"][name] = value
                with mock.patch.object(subject, "load_exact_operation_final_receipt_read_only", return_value=altered):
                    self.assert_refused_read_only(claim)
        for name, value in (("operation", "other_operation"), ("target_binding_sha256", wrong),
                            ("approval_reference", {**claim.public_reference(), "context_sha256": wrong})):
            with self.subTest(authentication_field=name):
                altered = deepcopy(final)
                altered["result"]["completion_authentication"][name] = value
                with mock.patch.object(subject, "load_exact_operation_final_receipt_read_only", return_value=altered):
                    self.assert_refused_read_only(claim)

    def test_completion_claim_and_checkpoint_are_reaudited_after_actual_output_observation(self):
        claim, result = self.complete()
        paths = [self.fixture._final_receipt_path(result["execution_sha256"]), claim._path,
                 self.fixture._checkpoint_path(result["execution_sha256"])]
        original_verify = subject.verify_exact_operation
        for path in paths:
            with self.subTest(evidence_kind=path.parent.name):
                raw = path.read_bytes()

                def change_after_observation(*args, **kwargs):
                    verified = original_verify(*args, **kwargs)
                    self.assertTrue(verified["all_match"])
                    path.write_bytes(b"untrusted replacement")
                    return verified

                with mock.patch.object(subject, "verify_exact_operation", side_effect=change_after_observation):
                    with self.assertRaises(subject.SourceIntakeBatchExactError) as caught:
                        self.verify(claim)
                self.assertIsNone(caught.exception.__context__)
                self.assertEqual(path.read_bytes(), b"untrusted replacement")
                path.write_bytes(raw)
        self.assertTrue(self.verify(claim)["ok"])

    def test_retained_completion_needs_no_request_or_current_source_and_does_not_replan(self):
        claim, _ = self.complete()
        self.fixture.request_path.unlink()
        for source in self.sources:
            source.unlink()
        before = self.snapshot()
        with mock.patch.object(subject, "plan_source_intake_batch", side_effect=AssertionError("replan")), \
             mock.patch.object(subject, "_request_items", side_effect=AssertionError("request reread")):
            verified = self.verify(claim)
        self.assertTrue(verified["ok"])
        self.assertFalse(verified["source_bytes_reverified"])
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
