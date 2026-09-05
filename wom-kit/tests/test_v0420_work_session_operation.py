"""Real session generation, authenticated claim and checkpoint integration.

Only native human input and the secure-key boundary are synthetic. The writer,
filesystem lock, claim HMAC, completion evidence and independent read are real.
Public command/discovery and installed-wheel tests remain separate gates.
"""

from dataclasses import replace
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as workflow
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_registry as registry
from wom_kit import work_session_operation as operation
from wom_kit.exact_human_approval_windows import APPROVE_BUTTON_ID, IDCANCEL


ARCHIVE_ID = "archive:personal:synthetic-session-operation"


class _Native:
    def __init__(self, approve=True):
        self.calls = 0
        self.approve = approve

    def show(self, **_kwargs):
        self.calls += 1
        return (APPROVE_BUTTON_ID if self.approve else IDCANCEL), True


class _Key:
    def use_key(self, _root, consumer, *, create_if_missing=False):
        secret = bytearray(range(32))
        try:
            return consumer(memoryview(secret))
        finally:
            secret[:] = b"\0" * len(secret)


class SessionOperationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wom-session-operation-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "archive"
        self.root.mkdir()
        (self.root / "archive.yml").write_text("archive_id: " + ARCHIVE_ID + "\n", encoding="utf-8")
        self.store = registry.WorkSessionRegistryStore(
            self.root, approval.exact_human_approval_archive_identity_sha256(ARCHIVE_ID)
        )
        app = registry.plan_transition(self.store.read(), action="register-app", label="Synthetic app")
        with exact.ExactOperationWriterLock(self.root) as held:
            self.store.commit(app, held_lock=held)
        self.app = app.result_refs[0]
        self.transition = registry.plan_transition(self.store.read(), action="create",
                                                  client_app_ref=self.app, label="Synthetic private task")
        self.prepared = operation.prepare_session_decision(self.transition)
        self.context = self.prepared.context(archive_id=ARCHIVE_ID, reviewer_claim="person:synthetic")
        self.native, self.key = _Native(), _Key()

    def execute(self):
        # The archive lock is acquired before the broker opens, not afterwards.
        with exact.ExactOperationWriterLock(self.root) as held:
            return workflow._execute_exact_human_approved_write_core(
                self.root, self.context,
                lambda claim: operation.apply_session_decision_with_claim(
                    self.store, self.prepared, context=self.context, claim=claim, held_lock=held,
                ), native=self.native, key_provider=self.key,
            )

    def test_authenticated_claim_publishes_generation_and_signed_exact_receipt(self):
        result = self.execute()
        self.assertTrue(result["ok"])
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.store.read().sha256, self.transition.after.sha256)
        self.assertEqual(result["work_session_binding"], self.prepared.manifest.work_session_binding.document())
        receipt = exact.load_exact_operation_final_receipt_read_only(self.root, result["execution_sha256"])
        self.assertIn("completion_authentication", receipt["result"])
        authentication = receipt["result"]["completion_authentication"]
        payload = exact.exact_operation_completion_authentication_payload(receipt["result"])
        audit = dict(
            expected_operation=self.context.operation,
            expected_plan_sha256=self.prepared.manifest.manifest_sha256,
            expected_target_binding_sha256=self.prepared.manifest.target_set_sha256,
            payload=payload, key_provider=self.key,
        )
        self.assertTrue(approval.audit_exact_human_approval_succeeded_terminal_record_read_only(
            self.root, authentication["approval_reference"],
            expected_mac=authentication["terminal_mac"], **audit,
        ))
        self.assertFalse(approval.audit_exact_human_approval_succeeded_terminal_record_read_only(
            self.root, authentication["approval_reference"],
            expected_mac="hmac-sha256:" + "0" * 64, **audit,
        ))
        for public in (result, self.prepared.manifest.document(), receipt):
            text = json.dumps(public)
            self.assertNotIn("Synthetic private task", text)
            self.assertNotIn("Synthetic app", text)
            self.assertNotIn(str(self.root), text)

    def test_cancel_keeps_registry_and_domain_receipts_unchanged(self):
        before = self.store.read().sha256
        self.native.approve = False
        with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
            self.execute()
        self.assertEqual(before, self.store.read().sha256)
        self.assertFalse((self.root / "receipts").exists())

    def test_changed_factory_review_codes_cannot_authorize_generation(self):
        self.context = replace(self.context, review_binding_codes=("synthetic_other_review",))
        before = self.store.read().sha256
        with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
            self.execute()
        self.assertEqual(self.store.read().sha256, before)
        self.assertFalse((self.store.path / "000000000002.json").exists())

    def test_rehashed_forged_transition_is_rejected_without_registry_mutation(self):
        document = deepcopy(self.transition.after._document)
        document["apps"][self.app]["label"] = "Synthetic altered app"
        forged = replace(self.transition, after=registry.RegistrySnapshot(document))
        forged = replace(forged, plan_sha256=registry._digest(forged._basis()))
        self.prepared = operation.prepare_session_decision(forged)
        self.context = self.prepared.context(archive_id=ARCHIVE_ID, reviewer_claim="person:synthetic")
        before = self.store.read().sha256
        with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
            self.execute()
        self.assertEqual(self.store.read().sha256, before)
        self.assertFalse((self.store.path / "000000000002.json").exists())

    def test_older_target_tamper_detected_beyond_latest_two_generations(self):
        result = self.execute()
        saved = exact.load_exact_operation_final_receipt_read_only(self.root, result["execution_sha256"])
        for index in range(3):
            plan = registry.plan_transition(self.store.read(), action="register-app",
                                            label=f"Synthetic later app {index}")
            with exact.ExactOperationWriterLock(self.root) as held:
                self.store.commit(plan, held_lock=held)
        old_target = self.store.path / "000000000002.json"
        document = json.loads(old_target.read_bytes())
        document["apps"][self.app]["label"] = "Synthetic historical alteration"
        old_target.write_bytes(registry._canonical(document))
        # Current snapshot admission inspects generations four/five, so this
        # assertion ensures it is the target-specific verifier that catches two.
        self.assertEqual(self.store.read().revision, 5)
        verification = exact.verify_exact_operation(
            self.prepared.manifest, verifier=operation._Verifier(self.store, self.prepared), state="post",
        )
        self.assertFalse(verification["all_match"])
        self.assertEqual(exact.load_exact_operation_final_receipt_read_only(self.root, result["execution_sha256"]), saved)

    def test_boolean_or_wrong_action_is_not_authenticated_authority(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            with self.assertRaises(registry.WorkSessionRegistryError):
                operation.apply_session_decision_with_claim(
                    self.store, self.prepared, context=self.context, claim=True, held_lock=held,
                )
        wrong = replace(self.context, warning_codes=("work_session_handoff",))
        with exact.ExactOperationWriterLock(self.root) as held:
            with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
                workflow._execute_exact_human_approved_write_core(
                    self.root, wrong, lambda claim: operation.apply_session_decision_with_claim(
                        self.store, self.prepared, context=wrong, claim=claim, held_lock=held,
                    ), native=self.native, key_provider=self.key,
                )
        self.assertEqual(self.store.read().revision, 1)

    def test_later_session_change_does_not_rewrite_historical_generation_evidence(self):
        result = self.execute()
        saved = exact.load_exact_operation_final_receipt_read_only(self.root, result["execution_sha256"])
        unrelated = registry.plan_transition(self.store.read(), action="register-app", label="Synthetic other app")
        with exact.ExactOperationWriterLock(self.root) as held:
            self.store.commit(unrelated, held_lock=held)
        verification = exact.verify_exact_operation(
            self.prepared.manifest, verifier=operation._Verifier(self.store, self.prepared), state="post",
        )
        self.assertTrue(verification["all_match"])
        self.assertEqual(exact.load_exact_operation_final_receipt_read_only(self.root, result["execution_sha256"]), saved)

    def test_cut_after_registry_publish_resumes_same_claim_without_new_native_intent(self):
        original = self.store.commit
        approval_ids = []

        def cut(*args, **kwargs):
            original(*args, **kwargs)
            raise OSError("synthetic power cut")

        with mock.patch.object(self.store, "commit", side_effect=cut):
            with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
                self.execute()
        for path in (self.root / "profiles/local/exact-human-approvals/claims").glob("*.json"):
            record = json.loads(path.read_text(encoding="utf-8"))
            if record["status"] == "started":
                approval_ids.append(record["approval_id"])
        self.assertEqual(len(approval_ids), 1)
        with exact.ExactOperationWriterLock(self.root) as held:
            def guard(claim):
                authority = exact.ExactOperationApprovalAuthority.from_reference(claim.assert_ready_for_context(self.context))
                execution = exact.exact_operation_execution_sha256(self.prepared.manifest, approval_authority=authority)
                store = exact.FileExactOperationCheckpointStore(self.root, writer_lock=held)
                return bool(tuple(store.load(execution, heartbeat=lambda: None)))

            with mock.patch.object(self.store, "commit", side_effect=AssertionError("must not republish")):
                result = workflow._resume_exact_human_approved_write_core(
                    self.root, self.context, approval_ids[0], guard,
                    lambda claim: operation.apply_session_decision_with_claim(
                        self.store, self.prepared, context=self.context, claim=claim, held_lock=held, resume=True,
                    ), key_provider=self.key,
                )
        self.assertTrue(result["ok"])
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.store.read().sha256, self.transition.after.sha256)


if __name__ == "__main__":
    unittest.main()
