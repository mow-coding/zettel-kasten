"""Synthetic real intake claims/bytes; no provider, actor or source authority shortcuts."""

from contextlib import ExitStack
from dataclasses import replace
import json
import shutil
import unittest
from unittest.mock import patch

import test_v0420_work_session_source_intake_workflow as fixture
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import exact_operation_manifest as exact
from wom_kit import source_intake_batch_exact as intake
from wom_kit import work_session_actor as actor
from wom_kit import work_session_source_intake_bundle as bundle
from wom_kit import work_session_source_intake_completion as subject
from wom_kit.exact_human_approval_windows import ExactHumanApprovalOperation, _ExactHumanApprovalDecision


class SourceIntakeCompletionReaderTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.SessionSourceIntakeWorkflowTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = self.fixture.root
        self.held = self.stack.enter_context(exact.ExactOperationWriterLock(self.root))
        self.result = self.fixture.execute(self.held)
        self.bound = self.fixture.retained(self.held)
        self.prepared, self.context = self.bound.prepared, self.bound.context
        self.plan = self.prepared.plan
        self.values = dict(held=self.held, manifest_sha256=self.plan.manifest.manifest_sha256,
            context_sha256=approval.exact_human_approval_context_sha256(self.context))
        self.execution = self.result["execution_sha256"]
        self.final_path = self.root / exact.EXACT_OPERATION_RECEIPTS_ROOT / (self.execution[7:] + ".json")
        final = exact.load_exact_operation_final_receipt_read_only(self.root, self.execution)
        self.reference = final["result"]["completion_authentication"]["approval_reference"]
        self.claim_path = self.root / approval.CLAIMS_RELATIVE_ROOT / (self.reference["approval_id"] + ".json")

    def read(self, **changes):
        values = {**self.values, "key_provider": self.fixture.key, **changes}
        return subject._read_completed_session_source_intake_held(self.root, **values)

    def image(self, **changes):
        return subject._read_session_source_intake_completion_image_held(self.root,
            **{**self.values, "execution_sha256": self.execution, **changes})

    def verify(self, claim, **changes):
        return subject._verify_completed_session_source_intake_with_claim_held(self.root,
            **{**self.values, "execution_sha256": self.execution, "claim": claim, **changes})

    def claim(self, context=None, root=None):
        context = context or replace(self.context, operation=ExactHumanApprovalOperation.git_backup,
            plan_sha256="sha256:" + "c" * 64, target_binding_sha256="sha256:" + "d" * 64)
        decision = _ExactHumanApprovalDecision(approved=True, synthetic_acknowledged=False,
            reason_code="exact_human_approval_approved", plan_sha256=context.plan_sha256,
            target_binding_sha256=context.target_binding_sha256)
        claim = approval._claim_exact_human_approval_core(root or self.root, context, decision, bytes(range(32)))
        self.addCleanup(claim.close)
        return claim

    def refuse(self, call, code=None):
        before = self.fixture.files()
        with self.assertRaises(subject.WorkSessionIntakeCompletionError) as caught:
            call()
        if code is not None:
            self.assertEqual(caught.exception.code, code)
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)
        self.assertNotIn(str(self.root), repr(caught.exception))
        self.assertEqual(self.fixture.files(), before)

    def test_source_free_read_is_noncreating_detached_and_includes_actual_common_file_bytes(self):
        self.fixture.request.unlink()
        for source in self.fixture.sources:
            source.unlink()
        before, key_start = self.fixture.files(), len(self.fixture.key.create_if_missing_calls)
        with patch.object(intake, "plan_source_intake_batch", side_effect=AssertionError("replan")), \
             patch.object(intake, "_stable_source_digest", side_effect=AssertionError("source")), \
             patch.object(intake, "_stable_request_bytes", side_effect=AssertionError("caller request")), \
             patch.object(intake._Writer, "write_field", side_effect=AssertionError("writer")), \
             patch.object(actor.WorkSessionActorStore, "_read", side_effect=AssertionError("current actor")), \
             patch.object(approval._ClaimedExactHumanApproval, "exact_terminal_record_mac", side_effect=AssertionError("sign")):
            verified = self.read()
            image = self.image()
        self.assertIs(type(verified), subject._VerifiedSessionSourceIntakeCompletion)
        self.assertIs(type(image), subject._SessionSourceIntakeCompletionImage)
        self.assertEqual(verified.image_sha256, image.image_sha256)
        self.assertEqual(self.fixture.files(), before)
        self.assertEqual(self.fixture.key.create_if_missing_calls[key_start:], [False])
        outputs = verified.approved_output_map()
        self.assertEqual(len(outputs), len(self.plan.items) + 2)
        for path, row in outputs.items():
            raw = (self.root / path).read_bytes()
            self.assertEqual(row["sha256"], intake._sha_bytes(raw))
            self.assertEqual(row["size_bytes"], len(raw))
        common = outputs[self.final_path.relative_to(self.root).as_posix()]
        self.assertEqual(common["output_kind"], "common_completion_receipt")
        self.assertEqual(common["output_identity_sha256"], self.execution)
        self.assertEqual(verified.common_final_receipt_raw, self.final_path.read_bytes())
        self.assertNotEqual(common["sha256"], verified.proof_document()["common_final_receipt_sha256"])
        outputs.clear()
        proof = verified.proof_document()
        proof["work_session_binding"].clear()
        self.assertTrue(verified.approved_output_map())
        self.assertEqual(verified.proof_document()["work_session_binding"], self.plan.manifest.work_session_binding.document())
        self.assertNotIn(str(self.root), repr(verified) + repr(image))

    def test_active_git_and_capture_claims_audit_without_nested_key_or_weakening_intake_wrapper(self):
        expected = self.read().proof_document()
        for operation in (ExactHumanApprovalOperation.git_backup, ExactHumanApprovalOperation.objet_capture_batch):
            context = replace(self.context, operation=operation, plan_sha256="sha256:" + "a" * 64)
            claim = self.claim(context)
            before = self.fixture.files()
            with patch.object(broker, "_production_key_provider", side_effect=AssertionError("nested provider")), \
                 patch.object(self.fixture.key, "use_key", side_effect=AssertionError("nested key")), \
                 patch.object(approval._ClaimedExactHumanApproval, "exact_terminal_record_mac", side_effect=AssertionError("sign")):
                self.assertEqual(self.verify(claim).proof_document(), expected)
                with self.assertRaises(intake.SourceIntakeBatchExactError):
                    intake._verify_source_intake_batch_completion_with_claim_held(self.plan,
                        context=self.context, claim=claim, writer_lock=self.held)
            self.assertEqual(claim.status, "started")
            self.assertEqual(self.fixture.files(), before)

    def test_provider_entry_evidence_change_refuses_without_repair(self):
        target = self.root / self.plan.items[0].receipt_relative_path
        raw, original_claim = target.read_bytes(), self.claim_path.read_bytes()
        changed = []
        def mutate(create_if_missing):
            self.assertFalse(create_if_missing)
            changed.append(True)
            target.write_bytes(raw[:-1] + b" ")
        self.fixture.key.before_consumer = mutate
        with self.assertRaises(subject.WorkSessionIntakeCompletionError):
            self.read()
        self.assertEqual(changed, [True])
        self.assertEqual(target.read_bytes(), raw[:-1] + b" ")
        self.assertEqual(self.claim_path.read_bytes(), original_claim)

    def test_provider_entry_and_exit_extra_claims_refuse_generation_change(self):
        original_use = self.fixture.key.use_key
        for timing in ("entry", "exit", "exit_same_context"):
            created = []
            def use_key(root, consumer, *, create_if_missing):
                self.assertFalse(create_if_missing)
                if timing == "entry":
                    created.append(self.claim())
                result = original_use(root, consumer, create_if_missing=create_if_missing)
                if timing.startswith("exit"):
                    created.append(self.claim(self.context if timing == "exit_same_context" else None))
                return result
            with patch.object(self.fixture.key, "use_key", side_effect=use_key):
                with self.assertRaises(subject.WorkSessionIntakeCompletionError) as caught:
                    self.read()
            self.assertEqual(caught.exception.code, "work_session_intake_completion_changed")
            self.assertEqual(len(created), 1)
            self.assertTrue(created[0]._path.exists())

    def test_missing_started_corrupt_and_wrong_exact_selectors_refuse(self):
        original = self.claim_path.read_bytes()
        self.claim_path.unlink()
        self.refuse(self.read)
        self.claim_path.write_bytes(original)
        document = json.loads(original)
        started = {**document, "status": "started", "finished_at": None, "failure_code": None}
        self.claim_path.write_bytes(approval._canonical_bytes(approval._authenticated(started, bytes(range(32)))))
        self.refuse(self.read, "work_session_intake_completion_authentication_invalid")
        self.claim_path.write_bytes(b"private malformed claim")
        self.refuse(self.read, "work_session_intake_completion_authentication_invalid")
        self.claim_path.write_bytes(original)
        self.refuse(lambda: self.read(context_sha256="sha256:" + "f" * 64))
        self.refuse(lambda: self.image(execution_sha256="sha256:" + "f" * 64))
        claim = self.claim()
        self.refuse(lambda: self.verify(claim, execution_sha256="sha256:" + "f" * 64))

    def test_two_actual_succeeded_exact_claims_are_ambiguous_not_selected_by_execution_hint(self):
        for item in self.plan.items:
            (self.root / item.receipt_relative_path).unlink()
        (self.root / self.plan.prepared_capture_request.relative_path).unlink()
        second = self.claim(self.context)
        authority = intake._authority(self.plan, second, self.context, allow_resume=True)
        store = exact.FileExactOperationCheckpointStore(self.root, writer_lock=self.held)
        result = exact.apply_exact_operation(self.plan.manifest, payloads=intake._Payloads(self.plan),
            writer=intake._Writer(self.plan, request_items=self.prepared.request_items()), verifier=intake._Verifier(self.plan),
            checkpoint_store=store, approval_authority=authority,
            completion_authenticator=intake._completion_authenticator(second))
        self.assertEqual(result["status"], "completed")
        second.finalize_succeeded()
        self.refuse(self.read, "work_session_intake_completion_ambiguous")

    def test_same_size_targets_invalid_mac_origin_and_callback_drift_refuse(self):
        claim = self.claim()
        targets = [self.root / self.plan.items[0].receipt_relative_path,
                   self.root / self.plan.prepared_capture_request.relative_path, self.final_path]
        for path in targets:
            raw = path.read_bytes()
            path.write_bytes(raw[:-1] + b" ")
            self.refuse(lambda: self.verify(claim))
            path.write_bytes(raw)
        raw = self.final_path.read_bytes()
        final = json.loads(raw)
        final["result"]["completion_authentication"]["terminal_mac"] = "hmac-sha256:" + "0" * 64
        final["result"]["result_sha256"] = self.fixture.fixture._exact_document_sha256(
            {key: value for key, value in final["result"].items() if key != "result_sha256"})
        final["receipt_sha256"] = self.fixture.fixture._exact_document_sha256(
            {key: value for key, value in final.items() if key != "receipt_sha256"})
        self.final_path.write_bytes(self.fixture.fixture._canonical_exact_bytes(final) + b"\n")
        self.assertIsNotNone(exact.load_exact_operation_final_receipt_read_only(self.root, self.execution))
        self.assertIs(type(self.image()), subject._SessionSourceIntakeCompletionImage)
        self.refuse(lambda: self.verify(claim), "work_session_intake_completion_authentication_invalid")
        self.refuse(self.read, "work_session_intake_completion_authentication_invalid")
        self.final_path.write_bytes(raw)
        origin_path = self.root / exact.EXACT_OPERATION_RECEIPTS_ROOT / (
            self.prepared.scope.document()["establishment_execution_sha256"][7:] + ".json")
        origin_raw = origin_path.read_bytes()
        origin_path.write_bytes(origin_raw[:-1] + b" ")
        self.refuse(lambda: self.verify(claim))
        origin_path.write_bytes(origin_raw)
        original_read = intake._Verifier.read_field
        changed = []
        def read_field(verifier, **kwargs):
            value = original_read(verifier, **kwargs)
            if not changed:
                changed.append(True)
                self.claim_path.write_bytes(b"changed after original output observation")
            return value
        with patch.object(intake._Verifier, "read_field", new=read_field):
            with self.assertRaises(subject.WorkSessionIntakeCompletionError):
                self.verify(claim)
        self.assertEqual(changed, [True])

    def test_foreign_archive_wrong_lock_private_errors_and_decode_count_are_bounded(self):
        claim = self.claim()
        copy = self.fixture.fixture.workspace / "foreign-copy"
        shutil.copytree(self.root, copy, ignore=shutil.ignore_patterns(".writer.lock"))
        foreign = self.claim(root=copy)
        self.refuse(lambda: self.verify(foreign))
        for held in (None, exact.ExactOperationWriterLock(self.root)):
            self.refuse(lambda: self.read(held=held), "work_session_intake_completion_lock_required")
        with patch.object(subject.os.path, "samefile", side_effect=OSError(str(self.root / "private-path"))):
            self.refuse(lambda: self.verify(claim))
        count, observations = [], []
        original_decode, original_read = bundle._decode_prepared, intake._Verifier.read_field
        def decode(*args, **kwargs):
            count.append(True)
            return original_decode(*args, **kwargs)
        def read_field(verifier, **kwargs):
            observations.append(len(count))
            return original_read(verifier, **kwargs)
        with patch.object(bundle, "_decode_prepared", side_effect=decode), \
             patch.object(intake._Verifier, "read_field", new=read_field):
            verified = self.verify(claim)
            captured = len(count)
            for _ in range(20):
                self.assertIs(verified.plan, verified.plan)
                self.assertIs(verified.scope, verified.scope)
                verified.approved_output_map()
            self.assertEqual(len(count), captured)
        self.assertGreaterEqual(len(observations), 2 * len(self.plan.manifest.items))
        self.assertEqual(len(set(observations)), 1, "full retained decodes cannot happen per output")

    def test_unknown_claim_leaf_is_only_generation_data_and_inventory_limit_is_noncreating(self):
        pending = self.claim_path.parent / ".pending_fixture"
        pending.write_bytes(b"unrecognized private data, not a claim")
        before = self.fixture.files()
        self.assertIs(type(self.read()), subject._VerifiedSessionSourceIntakeCompletion)
        self.assertEqual(self.fixture.files(), before)
        calls = self.fixture.key.calls
        with patch.object(subject, "_MAX_CLAIM_IMAGE_BYTES", 1):
            self.refuse(self.read, "work_session_intake_completion_authentication_invalid")
        self.assertEqual(self.fixture.key.calls, calls)
        original_use = self.fixture.key.use_key
        def use_key(root, consumer, *, create_if_missing):
            result = original_use(root, consumer, create_if_missing=create_if_missing)
            pending.write_bytes(b"changed unrecognized image")
            return result
        with patch.object(self.fixture.key, "use_key", side_effect=use_key):
            with self.assertRaises(subject.WorkSessionIntakeCompletionError) as caught:
                self.read()
        self.assertEqual(caught.exception.code, "work_session_intake_completion_changed")
        self.assertEqual(pending.read_bytes(), b"changed unrecognized image")


if __name__ == "__main__":
    unittest.main()
