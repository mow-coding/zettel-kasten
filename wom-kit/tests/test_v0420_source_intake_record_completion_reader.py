"""Real original single-record history; no actor, source, or approval shortcuts."""

from contextlib import ExitStack
from dataclasses import replace
import inspect
import json
import os
import shutil
import unittest
from unittest.mock import patch

import test_v0420_source_intake_record_workflow as fixture
from wom_kit import archive_services
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import exact_operation_manifest as exact
from wom_kit import source_intake_record_exact as record
from wom_kit import work_session_actor as actor
from wom_kit import work_session_source_intake_bundle as batch_bundle
from wom_kit import work_session_source_intake_completion as subject
from wom_kit import work_session_source_intake_record_bundle as bundle
from wom_kit import work_session_source_intake_record_execution as domain
from wom_kit.exact_human_approval_windows import ExactHumanApprovalOperation, _ExactHumanApprovalDecision


class SourceIntakeRecordCompletionReaderTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.SessionSourceIntakeRecordWorkflowTests("runTest")
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
        self.checkpoint_path = self.root / exact.EXACT_OPERATION_LOCAL_ROOT / "checkpoints" / (self.execution[7:] + ".jsonl")
        final = exact.load_exact_operation_final_receipt_read_only(self.root, self.execution)
        self.reference = final["result"]["completion_authentication"]["approval_reference"]
        self.claim_path = self.root / approval.CLAIMS_RELATIVE_ROOT / (self.reference["approval_id"] + ".json")

    def read(self, **changes):
        return subject._read_completed_session_source_intake_record_held(self.root,
            **{**self.values, "key_provider": self.fixture.key, **changes})

    def image(self, **changes):
        return subject._read_session_source_intake_record_completion_image_held(self.root,
            **{**self.values, "execution_sha256": self.execution, **changes})

    def verify(self, claim, **changes):
        return subject._verify_completed_session_source_intake_record_with_claim_held(self.root,
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
        self.fixture.assert_private_safe(repr(caught.exception))
        self.assertEqual(self.fixture.files(), before)

    def test_source_and_input_free_read_has_distinct_types_exact_two_outputs_and_cached_views(self):
        self.fixture.plan_path.unlink()
        self.fixture.fixture.selected.unlink()
        before, key_start = self.fixture.files(), len(self.fixture.key.create_if_missing_calls)
        observed_decodes = []
        original_decode, original_read = bundle._decode_prepared, domain._Verifier.read_field
        with patch.object(bundle, "_decode_prepared", wraps=original_decode) as decodes:
            def read_field(verifier, **kwargs):
                observed_decodes.append(decodes.call_count)
                return original_read(verifier, **kwargs)

            with patch.object(record, "plan_source_intake_record", side_effect=AssertionError("replan")), \
                 patch.object(record, "_resolve_plan_path", side_effect=AssertionError("caller JSON")), \
                 patch.object(archive_services, "source_intake_plan", side_effect=AssertionError("source")), \
                 patch.object(domain, "_run_session_source_intake_record_exact_operation", side_effect=AssertionError("writer")), \
                 patch.object(actor.WorkSessionActorStore, "_read", side_effect=AssertionError("current actor")), \
                 patch.object(approval._ClaimedExactHumanApproval, "exact_terminal_record_mac", side_effect=AssertionError("sign")), \
                 patch.object(broker, "_production_key_provider", side_effect=AssertionError("default provider")), \
                 patch.object(domain._Verifier, "read_field", new=read_field), \
                 patch.object(domain, "_verify_source_intake_record_completion_with_claim_held",
                              wraps=domain._verify_source_intake_record_completion_with_claim_held) as own_gate:
                verified = self.read()
            self.assertEqual(own_gate.call_count, 1)
            cached = decodes.call_count
            for _ in range(20):
                self.assertIs(verified.plan, verified.plan)
                self.assertIs(verified.scope, verified.scope)
                verified.approved_output_map()
            self.assertEqual(decodes.call_count, cached)
        self.assertGreaterEqual(len(observed_decodes), 3)
        self.assertEqual(len(set(observed_decodes)), 1, "retained decode count cannot grow per output read")
        image = self.image()
        self.assertIs(type(verified), subject._VerifiedSessionSourceIntakeRecordCompletion)
        self.assertIs(type(image), subject._SessionSourceIntakeRecordCompletionImage)
        self.assertIsNot(type(verified), subject._VerifiedSessionSourceIntakeCompletion)
        self.assertIsNot(type(image), subject._SessionSourceIntakeCompletionImage)
        self.assertEqual(verified.proof_document(), image.proof_document())
        self.assertEqual(verified.image_sha256, image.image_sha256)
        self.assertEqual(self.fixture.key.create_if_missing_calls[key_start:], [False])
        outputs = verified.approved_output_map()
        self.assertEqual(set(outputs), {self.plan.receipt_relative_path,
            self.final_path.relative_to(self.root).as_posix()})
        self.assertEqual({row["output_kind"] for row in outputs.values()},
                         {"source_intake_receipt", "common_completion_receipt"})
        receipt = outputs[self.plan.receipt_relative_path]
        self.assertEqual(receipt["output_identity_sha256"], self.plan.source_intake_plan_sha256)
        self.assertEqual((receipt["target_kind"], receipt["field_ref"]), (record.TARGET_KIND, record.FIELD_REF))
        common = outputs[self.final_path.relative_to(self.root).as_posix()]
        self.assertEqual(common["output_identity_sha256"], self.execution)
        self.assertNotEqual(common["sha256"], verified.proof_document()["common_final_receipt_sha256"])
        for path, row in outputs.items():
            raw = (self.root / path).read_bytes()
            self.assertEqual((row["sha256"], row["size_bytes"]), (subject.intake._sha_bytes(raw), len(raw)))
        self.assertEqual(verified.common_final_receipt_raw, self.final_path.read_bytes())
        outputs.clear()
        proof = verified.proof_document()
        proof["work_session_binding"].clear()
        self.assertEqual(len(verified.approved_output_map()), 2)
        self.assertEqual(verified.proof_document()["work_session_binding"], self.plan.manifest.work_session_binding.document())
        self.assertEqual(self.fixture.files(), before)
        self.fixture.assert_private_safe(repr(verified) + repr(image))

    def test_active_git_and_capture_claims_verify_without_own_context_gate_or_nested_provider(self):
        expected = self.read().proof_document()
        for operation in (ExactHumanApprovalOperation.git_backup, ExactHumanApprovalOperation.objet_capture_batch):
            context = replace(self.context, operation=operation, plan_sha256="sha256:" + "a" * 64)
            claim = self.claim(context)
            before = self.fixture.files()
            with patch.object(self.fixture.key, "use_key", side_effect=AssertionError("nested key")), \
                 patch.object(broker, "_production_key_provider", side_effect=AssertionError("nested provider")), \
                 patch.object(approval._ClaimedExactHumanApproval, "exact_terminal_record_mac", side_effect=AssertionError("sign")):
                with patch.object(domain, "_verify_source_intake_record_completion_with_claim_held",
                                  side_effect=AssertionError("foreign claim is not record own authority")):
                    self.assertEqual(self.verify(claim).proof_document(), expected)
                with self.assertRaises(domain.WorkSessionSourceIntakeRecordExecutionError):
                    domain._verify_source_intake_record_completion_with_claim_held(self.plan,
                        context=self.context, claim=claim, writer_lock=self.held)
            self.assertEqual(claim.status, "started")
            self.assertEqual(self.fixture.files(), before)

    def test_missing_started_corrupt_or_additional_unverified_exact_claim_is_not_completion(self):
        original = self.claim_path.read_bytes()
        self.claim_path.unlink()
        self.refuse(self.read)
        document = json.loads(original)
        started = {**document, "status": "started", "finished_at": None, "failure_code": None}
        self.claim_path.write_bytes(approval._canonical_bytes(approval._authenticated(started, bytes(range(32)))))
        self.refuse(self.read, "work_session_intake_completion_authentication_invalid")
        self.claim_path.write_bytes(b"private malformed original claim")
        self.refuse(self.read, "work_session_intake_completion_authentication_invalid")
        self.claim_path.write_bytes(original)
        self.assertIs(type(self.read()), subject._VerifiedSessionSourceIntakeRecordCompletion)
        # An authenticated status alone is not authenticated domain completion:
        # this second real claim has no original checkpoint/final and must block.
        additional = self.claim(self.context)
        additional.finalize_succeeded()
        self.refuse(self.read)

    def test_output_bytes_hardlinks_and_post_read_callback_drift_refuse(self):
        claim = self.claim()
        target = self.root / self.plan.receipt_relative_path
        original = target.read_bytes()
        target.write_bytes(original[:-1] + b" ")
        self.refuse(lambda: self.verify(claim))
        self.refuse(self.image)
        target.write_bytes(original)
        alias = self.fixture.fixture.workspace / "historical-record-alias"
        os.link(target, alias)
        try:
            self.assertEqual(os.lstat(target).st_nlink, 2)
            self.assertEqual(target.read_bytes(), original)
            self.refuse(self.read)
            self.refuse(self.image)
            self.refuse(lambda: self.verify(claim))
        finally:
            alias.unlink()
        self.assertIs(type(self.verify(claim)), subject._VerifiedSessionSourceIntakeRecordCompletion)
        original_read, changed = domain._Verifier.read_field, []
        def read_field(verifier, **kwargs):
            value = original_read(verifier, **kwargs)
            if not changed:
                changed.append(True)
                self.claim_path.write_bytes(b"private post-observation claim drift")
            return value
        with patch.object(domain._Verifier, "read_field", new=read_field):
            with self.assertRaises(subject.WorkSessionIntakeCompletionError):
                self.verify(claim)
        self.assertEqual(changed, [True])

    def test_original_mac_establishment_checkpoint_and_reference_context_are_bound(self):
        claim = self.claim()
        raw = self.final_path.read_bytes()
        final = json.loads(raw)
        final["result"]["completion_authentication"]["terminal_mac"] = "hmac-sha256:" + "0" * 64
        final["result"]["result_sha256"] = subject.intake._sha_document(
            {key: value for key, value in final["result"].items() if key != "result_sha256"})
        final["receipt_sha256"] = subject.intake._sha_document(
            {key: value for key, value in final.items() if key != "receipt_sha256"})
        self.final_path.write_bytes(subject.bundle._canonical(final) + b"\n")
        self.assertIsNotNone(exact.load_exact_operation_final_receipt_read_only(self.root, self.execution))
        self.assertIs(type(self.image()), subject._SessionSourceIntakeRecordCompletionImage)
        self.refuse(lambda: self.verify(claim), "work_session_intake_completion_authentication_invalid")
        self.refuse(self.read, "work_session_intake_completion_authentication_invalid")
        self.final_path.write_bytes(raw)
        origin_path = self.root / exact.EXACT_OPERATION_RECEIPTS_ROOT / (
            self.prepared.scope.document()["establishment_execution_sha256"][7:] + ".json")
        for path in (origin_path, self.checkpoint_path):
            original = path.read_bytes()
            path.write_bytes(original[:-1] + b" ")
            self.refuse(lambda: self.verify(claim))
            path.write_bytes(original)
        for change in ({"context_sha256": "sha256:" + "f" * 64},
                       {"execution_sha256": "sha256:" + "f" * 64}):
            self.refuse(lambda: self.verify(claim, **change))
        self.assertIs(type(self.verify(claim)), subject._VerifiedSessionSourceIntakeRecordCompletion)

    def test_provider_entry_and_exit_evidence_and_claim_generation_changes_refuse(self):
        target = self.root / self.plan.receipt_relative_path
        raw = target.read_bytes()
        events = []
        def mutate(create_if_missing):
            self.assertFalse(create_if_missing)
            target.write_bytes(raw[:-1] + b" ")
            events.append(True)
        self.fixture.key.before_consumer = mutate
        with self.assertRaises(subject.WorkSessionIntakeCompletionError):
            self.read()
        self.assertEqual(events, [True])
        self.assertEqual(target.read_bytes(), raw[:-1] + b" ")
        self.fixture.key.before_consumer = None
        target.write_bytes(raw)
        original_use = self.fixture.key.use_key
        for timing in ("entry", "exit"):
            created = []
            def use_key(root, consumer, *, create_if_missing):
                self.assertFalse(create_if_missing)
                if timing == "entry":
                    created.append(self.claim())
                result = original_use(root, consumer, create_if_missing=create_if_missing)
                if timing == "exit":
                    created.append(self.claim())
                return result
            with patch.object(self.fixture.key, "use_key", side_effect=use_key):
                with self.assertRaises(subject.WorkSessionIntakeCompletionError) as caught:
                    self.read()
            self.assertEqual(caught.exception.code, "work_session_intake_completion_changed")
            self.assertEqual(len(created), 1)
            self.assertTrue(created[0]._path.exists())

    def test_family_routes_are_closed_and_cannot_load_record_bytes_as_batch(self):
        with patch.object(self.fixture.key, "use_key", side_effect=AssertionError("wrong family key")):
            self.refuse(lambda: subject._read_completed_session_source_intake_held(self.root,
                **self.values, key_provider=self.fixture.key), "work_session_intake_completion_missing")
        batch_path = self.root.joinpath(*batch_bundle.PRIVATE_ROOT) / (self.plan.manifest.manifest_sha256[7:] + ".json")
        batch_path.parent.mkdir(parents=True, exist_ok=True)
        batch_path.write_bytes(self.bound._raw)
        with patch.object(self.fixture.key, "use_key", side_effect=AssertionError("wrong family key")):
            self.refuse(lambda: subject._read_completed_session_source_intake_held(self.root,
                **self.values, key_provider=self.fixture.key))
        for entry in (subject._read_completed_session_source_intake_record_held,
                      subject._verify_completed_session_source_intake_record_with_claim_held,
                      subject._read_session_source_intake_record_completion_image_held):
            self.assertNotIn("family", inspect.signature(entry).parameters)
            self.assertNotIn("backend", inspect.signature(entry).parameters)
            self.assertNotIn("verifier", inspect.signature(entry).parameters)
        with self.assertRaises(subject.WorkSessionIntakeCompletionError):
            subject._original(self.root, self.held, self.values["manifest_sha256"],
                              self.values["context_sha256"], family="source_intake_record")
        self.assertIs(type(self.read()), subject._VerifiedSessionSourceIntakeRecordCompletion)

    def test_foreign_claim_missing_released_other_root_locks_and_private_failures_refuse(self):
        claim = self.claim()
        copied = self.fixture.fixture.workspace / "foreign-copy"
        shutil.copytree(self.root, copied, ignore=shutil.ignore_patterns(".writer.lock"))
        foreign = self.claim(root=copied)
        self.refuse(lambda: self.verify(foreign))
        for held in (None, exact.ExactOperationWriterLock(self.root)):
            self.refuse(lambda: self.read(held=held), "work_session_intake_completion_lock_required")
        with exact.ExactOperationWriterLock(copied) as other:
            self.refuse(lambda: self.read(held=other), "work_session_intake_completion_lock_required")
        with patch.object(subject.os.path, "samefile", side_effect=OSError(str(self.root / "private-path"))):
            self.refuse(lambda: self.verify(claim))
        self.held.__exit__(None, None, None)
        self.refuse(self.read, "work_session_intake_completion_lock_required")


if __name__ == "__main__":
    unittest.main()
