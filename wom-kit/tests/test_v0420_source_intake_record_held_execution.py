"""Real common-exact record MAC/bytes, with synthetic native/key boundaries.

These focused completion fixtures create NEW signed exact operations. They do
not upgrade unsigned legacy receipts or substitute current ownership in the
session runner. The separately composed workflow tests exercise owned writes.
"""

from contextlib import ExitStack
from dataclasses import replace
import json
import os
import unittest
from unittest.mock import patch

import test_v049_source_intake_record_exact as fixture_module
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import exact_operation_manifest as exact
from wom_kit import source_intake_batch_exact as batch
from wom_kit import source_intake_record_exact as record
from wom_kit import work_session_source_intake_record_execution as subject
from wom_kit.exact_human_approval_windows import _ExactHumanApprovalDecision


class RecordHeldBoundaryTests(unittest.TestCase):
    def test_fixed_errors_cannot_hash_subclasses_or_retain_private_chains(self):
        class Hostile(str):
            def __hash__(self):
                raise AssertionError("untrusted hash")
        for code in ([], {}, None, True, "private/source.json", Hostile("source_intake_record_lock_required")):
            self.assertEqual(str(subject.WorkSessionSourceIntakeRecordExecutionError(code)),
                             "source_intake_record_write_failed")
        def fail():
            raise OSError("private/source.json")
        with self.assertRaises(subject.WorkSessionSourceIntakeRecordExecutionError) as caught:
            subject._safe_call(fail)
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)

    def test_scoped_runner_rejects_duck_subclass_and_resume_nonbool_before_domain(self):
        from wom_kit.work_session_source_intake_record_bundle import PreparedSessionSourceIntakeRecord
        class Subclass(PreparedSessionSourceIntakeRecord):
            pass
        values = (None, {}, True, object.__new__(Subclass))
        with patch.object(exact, "apply_exact_operation", side_effect=AssertionError("domain writer")) as apply:
            for prepared in values:
                with self.assertRaises(subject.WorkSessionSourceIntakeRecordExecutionError):
                    subject._run_session_source_intake_record_exact_operation(prepared,
                        context=None, claim=None, writer_lock=None, resume=False)
            with self.assertRaises(subject.WorkSessionSourceIntakeRecordExecutionError) as caught:
                subject._run_session_source_intake_record_exact_operation(object.__new__(PreparedSessionSourceIntakeRecord),
                    context=None, claim=None, writer_lock=None, resume=0)
            self.assertEqual(caught.exception.code, "source_intake_record_scope_context_required")
            apply.assert_not_called()


class RecordHeldCompletionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.SourceIntakeRecordExactTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.root = self.fixture.root.resolve()
        self.plan = record.plan_source_intake_record(self.root, self.fixture.plan_path)
        self.context = record.approval_context(self.plan, reviewer_claim="person:synthetic-record-reviewer")
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.held = self.stack.enter_context(exact.ExactOperationWriterLock(self.root))
        self.claims = []
        self.addCleanup(lambda: [claim.close() for claim in self.claims])

    def claim(self, context=None, root=None):
        context = self.context if context is None else context
        decision = _ExactHumanApprovalDecision(approved=True, synthetic_acknowledged=False,
            reason_code="exact_human_approval_approved", plan_sha256=context.plan_sha256,
            target_binding_sha256=context.target_binding_sha256)
        claim = approval._claim_exact_human_approval_core(root or self.root, context, decision, bytes(range(32)))
        self.claims.append(claim)
        return claim

    def complete(self):
        # A new original claim, no existing unsigned result is adopted. The
        # common exact engine owns the same real checkpoint/receipt algorithm.
        claim = self.claim()
        authority = record._authority(self.plan, claim, self.context)
        result = exact.apply_exact_operation(self.plan.manifest, payloads=record._Payloads(self.plan),
            writer=record._Writer(self.plan), verifier=record._Verifier(self.plan),
            checkpoint_store=exact.FileExactOperationCheckpointStore(self.root, writer_lock=self.held),
            approval_authority=authority, completion_authenticator=batch._completion_authenticator(claim))
        self.assertEqual(result["status"], "completed")
        claim.finalize_succeeded()
        return claim, result

    def files(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*") if path.is_file() and path.name != ".writer.lock"}

    def verify(self, claim, **changes):
        values = dict(context=self.context, claim=claim, writer_lock=self.held)
        values.update(changes)
        return subject._verify_source_intake_record_completion_with_claim_held(self.plan, **values)

    def refuse(self, call):
        before = self.files()
        with self.assertRaises(subject.WorkSessionSourceIntakeRecordExecutionError) as caught:
            call()
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)
        self.assertNotIn(str(self.root), repr(caught.exception))
        self.assertEqual(self.files(), before)

    def test_real_succeeded_proof_is_source_free_readonly_and_exact(self):
        claim, result = self.complete()
        self.fixture.plan_path.unlink()
        self.fixture.selected.unlink()
        before = self.files()
        with patch.object(record, "plan_source_intake_record", side_effect=AssertionError("replan")), \
             patch.object(record, "_stable_regular_bytes", side_effect=AssertionError("source JSON")), \
             patch.object(record._Writer, "write_field", side_effect=AssertionError("writer")), \
             patch.object(approval._ClaimedExactHumanApproval, "exact_terminal_record_mac", side_effect=AssertionError("sign")), \
             patch.object(broker, "_production_key_provider", side_effect=AssertionError("nested provider")):
            verified = self.verify(claim)
        self.assertTrue(verified["completion_authentication_verified"])
        self.assertTrue(verified["independent_verification"])
        self.assertEqual(verified["item_count"], 1)
        self.assertEqual(verified["completed_item_count"], 1)
        self.assertFalse(verified["writes_performed"] or verified["current_claim_authority_evaluated"])
        self.assertEqual(verified["execution_sha256"], result["execution_sha256"])
        self.assertEqual(verified["common_final_receipt_sha256"], result["final_receipt_sha256"])
        self.assertEqual((self.root / self.plan.receipt_relative_path).read_bytes(), self.plan.receipt_bytes)
        self.assertEqual(self.files(), before)
        for secret in (str(self.root), str(self.fixture.plan_path), fixture_module.PRIVATE_NAME, fixture_module.PRIVATE_BODY):
            self.assertNotIn(secret, json.dumps(verified))

    def test_started_wrong_context_wrong_archive_and_untyped_claim_are_not_completion(self):
        started = self.claim()
        self.refuse(lambda: self.verify(started))
        claim, _result = self.complete()
        changed = replace(self.context, plan_sha256="sha256:" + "f" * 64)
        self.refuse(lambda: self.verify(claim, context=changed))
        self.refuse(lambda: self.verify(object()))
        other_root = self.root.parent / "other-archive"
        other_root.mkdir()
        (other_root / "archive.yml").write_bytes((self.root / "archive.yml").read_bytes())
        foreign = self.claim(root=other_root)
        foreign.finalize_succeeded()
        self.refuse(lambda: self.verify(foreign))

    def test_real_lock_type_archive_and_closed_lock_required_without_evidence_writes(self):
        subject._require_source_intake_record_held_lock(self.plan, self.held)
        for lock in (None, True, object()):
            self.refuse(lambda: subject._require_source_intake_record_held_lock(self.plan, lock))
        other_root = self.root.parent / "other-archive"
        other_root.mkdir()
        (other_root / "archive.yml").write_bytes((self.root / "archive.yml").read_bytes())
        with exact.ExactOperationWriterLock(other_root) as other:
            self.refuse(lambda: subject._require_source_intake_record_held_lock(self.plan, other))
        self.refuse(lambda: subject._require_source_intake_record_held_lock(self.plan, other))

    def test_mac_checkpoint_and_same_size_output_drift_refuse_without_repair(self):
        claim, result = self.complete()
        execution = result["execution_sha256"]
        final_path = self.root / exact.EXACT_OPERATION_RECEIPTS_ROOT / (execution[7:] + ".json")
        checkpoint = self.root / exact.EXACT_OPERATION_LOCAL_ROOT / "checkpoints" / (execution[7:] + ".jsonl")
        receipt = self.root / self.plan.receipt_relative_path
        for target in (receipt, checkpoint):
            raw = target.read_bytes()
            target.write_bytes(raw[:-1] + b" ")
            self.refuse(lambda: self.verify(claim))
            target.write_bytes(raw)
        raw = final_path.read_bytes()
        value = json.loads(raw)
        value["result"]["completion_authentication"]["terminal_mac"] = "hmac-sha256:" + "f" * 64
        value["result"]["result_sha256"] = exact._digest_document({k: v for k, v in value["result"].items() if k != "result_sha256"})
        value["receipt_sha256"] = exact._digest_document({k: v for k, v in value.items() if k != "receipt_sha256"})
        final_path.write_bytes(exact._canonical_json_bytes(value) + b"\n")
        self.assertEqual(exact.load_exact_operation_final_receipt_read_only(self.root, execution), value)
        self.refuse(lambda: self.verify(claim))
        final_path.write_bytes(raw)
        self.assertTrue(self.verify(claim)["completion_authentication_verified"])

    def test_hardlinked_exact_output_is_not_scoped_completion_or_resumable_postimage(self):
        claim, _result = self.complete()
        receipt = self.root / self.plan.receipt_relative_path
        alias = self.root / "staging" / "single-record-hardlink.json"
        os.link(receipt, alias)
        self.assertEqual(receipt.stat().st_nlink, 2)
        # This is the actual old-reader gap, not a stubbed link observation.
        self.assertTrue(exact.verify_exact_operation(self.plan.manifest,
            verifier=record._Verifier(self.plan), state="post")["all_match"])
        self.refuse(lambda: self.verify(claim))
        with self.assertRaises(exact.ExactOperationManifestError):
            exact.verify_exact_operation(self.plan.manifest, verifier=subject._Verifier(self.plan), state="post")
        alias.unlink()
        self.assertTrue(self.verify(claim)["completion_authentication_verified"])

    def test_inroot_resolved_link_is_not_scoped_completion_or_resumable_postimage(self):
        claim, _result = self.complete()
        receipt = self.root / self.plan.receipt_relative_path
        original = receipt.read_bytes()
        actual = self.root / "staging" / "single-record-link-target.json"
        actual.write_bytes(original)
        receipt.unlink()
        try:
            os.symlink(actual, receipt)
        except OSError as error:
            receipt.write_bytes(original)
            if os.name == "nt" and getattr(error, "winerror", None) == 1314:
                self.skipTest("Windows host lacks file-symlink creation privilege")
            raise
        self.assertTrue(receipt.is_symlink())
        self.assertEqual(receipt.resolve(), actual.resolve())
        self.assertTrue(exact.verify_exact_operation(self.plan.manifest,
            verifier=record._Verifier(self.plan), state="post")["all_match"])
        self.refuse(lambda: self.verify(claim))
        with self.assertRaises(exact.ExactOperationManifestError):
            exact.verify_exact_operation(self.plan.manifest, verifier=subject._Verifier(self.plan), state="post")
        receipt.unlink()
        receipt.write_bytes(original)
        self.assertTrue(self.verify(claim)["completion_authentication_verified"])

    def test_pure_completion_shape_cannot_grant_authority_and_binds_scope_context(self):
        claim, result = self.complete()
        final = exact.load_exact_operation_final_receipt_read_only(self.root, result["execution_sha256"])
        values = dict(context=self.context, reference=claim.public_reference(),
                      execution=result["execution_sha256"], final=final)
        _authority, auth, payload = subject._source_intake_record_completion_evidence_view(self.plan, **values)
        self.assertIsInstance(payload, bytes)
        self.assertEqual(auth, final["result"]["completion_authentication"])
        for changed in ({"context": replace(self.context, plan_sha256="sha256:" + "f" * 64)},
                        {"execution": "sha256:" + "f" * 64},
                        {"final": {**final, "result": {**final["result"], "operation_evidence": None}}}):
            self.refuse(lambda: subject._source_intake_record_completion_evidence_view(self.plan, **{**values, **changed}))
        # A forged MAC is structural data here and never authentication.
        forged = {**final, "result": {**final["result"], "completion_authentication": {**auth,
                  "terminal_mac": "hmac-sha256:" + "f" * 64}}}
        _authority, row, _payload = subject._source_intake_record_completion_evidence_view(self.plan, **{**values, "final": forged})
        self.assertEqual(row["terminal_mac"], "hmac-sha256:" + "f" * 64)


if __name__ == "__main__":
    unittest.main()
