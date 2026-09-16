"""Real broker/claim/registry/receipt paths; only native input and key are fake."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as workflow
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_bundle as bundle
from wom_kit import work_session_execution as execution
from wom_kit import work_session_operation as operation
from wom_kit import work_session_registry as registry
from wom_kit import exact_human_approval_windows as native_approval
from test_v0420_work_session_operation import _Key, _Native, ARCHIVE_ID


class SessionNative(_Native):
    def __init__(self):
        super().__init__()
        self.pages, self.main = [], []
        self.before_click = None

    def show_collection(self, *, session, **kwargs):
        self.calls += 1
        self.main.append(session.preview.native_main_text())
        self.pages.append(session.preview.native_page_text(0))
        if self.before_click is not None:
            self.before_click()
        button = native_approval.APPROVE_BUTTON_ID if self.approve else native_approval.IDCANCEL
        assert session.button_clicked(button) == "close"
        return button, True


class SessionExecutionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="wom-session-execution-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        self.root.mkdir()
        (self.root / "archive.yml").write_text("archive_id: " + ARCHIVE_ID + "\n", encoding="utf-8")
        self.store = registry.WorkSessionRegistryStore(
            self.root, approval.exact_human_approval_archive_identity_sha256(ARCHIVE_ID),
        )
        transition = registry.plan_transition(self.store.read(), action="register-app", label="Synthetic private app")
        with exact.ExactOperationWriterLock(self.root) as held:
            self.store.commit(transition, held_lock=held)
        self.app = transition.result_refs[0]
        self.native, self.key = SessionNative(), _Key()

    def execute(self):
        return execution._execute_session_decision_core(
            self.root, action="create", client_app_ref=self.app,
            label="Synthetic private workstream", reviewer_claim="person:synthetic-session-reviewer",
            native=self.native, key_provider=self.key,
        )

    def manifest_sha(self):
        files = list(self.root.joinpath(*bundle.PRIVATE_ROOT).glob("*.json"))
        self.assertEqual(len(files), 1)
        return "sha256:" + files[0].stem

    def resume(self):
        return execution._resume_session_decision_core(
            self.root, manifest_sha256=self.manifest_sha(), key_provider=self.key,
        )

    def claims(self):
        return {path.name: path.read_bytes()
                for path in self.root.joinpath(*Path(approval.CLAIMS_RELATIVE_ROOT).parts).glob("*.json")}

    def cut_before_checkpoint(self):
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=OSError("synthetic process loss")):
            with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
                self.execute()
        self.assertEqual(self.store.read().revision, 1)

    def test_one_native_decision_has_authenticated_receipt_and_independent_verification(self):
        result = self.execute()
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["independent_post_verification"])
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.native.main, ["대상 2개"])
        self.assertIn("Synthetic private app", self.native.pages[0])
        self.assertIn("Synthetic private workstream", self.native.pages[0])
        self.assertEqual(self.store.read().revision, 2)
        restored = bundle.load_context_bound_session_decision(self.store, manifest_sha256=self.manifest_sha())
        self.assertEqual(restored.context.reviewer_claim, "person:synthetic-session-reviewer")
        self.assertEqual(restored.prepared.manifest.work_session_binding.document(), result["work_session_binding"])
        for marker in ("Synthetic private app", "Synthetic private workstream", str(self.root)):
            self.assertNotIn(marker, json.dumps(result))

    def test_cancel_creates_no_plan_claim_key_or_registry_generation(self):
        self.native.approve = False
        with patch.object(self.key, "use_key", side_effect=AssertionError("cancel accessed secure key")):
            with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
                self.execute()
        self.assertEqual(self.store.read().revision, 1)
        self.assertFalse(self.root.joinpath(*bundle.PRIVATE_ROOT).exists())
        self.assertFalse(self.root.joinpath(*Path(approval.CLAIMS_RELATIVE_ROOT).parts).exists())
        self.assertFalse((self.root / "receipts").exists())

    def test_native_target_change_stops_before_claim_or_payload(self):
        path = self.store.path / "000000000001.json"

        def drift():
            document = json.loads(path.read_bytes())
            document["apps"][self.app]["label"] = "Synthetic changed app"
            path.write_bytes(registry._canonical(document))

        self.native.before_click = drift
        with patch.object(self.key, "use_key", side_effect=AssertionError("drift accessed secure key")):
            with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
                self.execute()
        self.assertEqual(self.store.read().revision, 1)
        self.assertFalse(self.root.joinpath(*bundle.PRIVATE_ROOT).exists())
        self.assertEqual(self.claims(), {})

    def test_sensitive_preview_is_omitted_without_changing_exact_identity(self):
        path = self.store.path / "000000000001.json"
        document = json.loads(path.read_bytes())
        document["apps"][self.app]["label"] = "https://private.invalid/synthetic"
        path.write_bytes(registry._canonical(document))
        result = self.execute()
        self.assertTrue(result["ok"])
        self.assertEqual(result["work_session_binding"]["client_app_ref"], self.app)
        self.assertIn("미리보기 생략", self.native.pages[0])
        self.assertNotIn("private.invalid", self.native.pages[0] + json.dumps(result))

    def test_started_claim_before_first_checkpoint_begins_original_runner_without_second_approval(self):
        self.cut_before_checkpoint()
        old_claims = self.claims()
        self.assertEqual(len(old_claims), 1)
        # The common lock directory legitimately exists; no exact checkpoint
        # or final receipt was created before the interrupted writer entry.
        self.assertFalse((self.root / exact.EXACT_OPERATION_LOCAL_ROOT / "checkpoints").exists())
        self.assertFalse((self.root / exact.EXACT_OPERATION_RECEIPTS_ROOT).exists())
        result = self.resume()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["started_resume_state"], "authenticated_before_first_checkpoint")
        self.assertFalse(result["native_approval_redisplayed"])
        self.assertFalse(result["resume_discovery"]["checkpoint_chain_validated_read_only"])
        self.assertTrue(result["resume_discovery"]["authenticated_precheckpoint_preimage_verified"])
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.claims().keys(), old_claims.keys())
        self.assertEqual(self.store.read().revision, 2)

    def test_real_publish_then_cut_resumes_original_checkpoint_without_republishing(self):
        original = registry.WorkSessionRegistryStore.commit

        def cut(store, transition, **kwargs):
            original(store, transition, **kwargs)
            raise OSError("synthetic process loss after registry publication")

        with patch.object(registry.WorkSessionRegistryStore, "commit", side_effect=cut, autospec=True):
            with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
                self.execute()
        old_claims = self.claims()
        self.assertEqual(self.store.read().revision, 2)
        with patch.object(registry.WorkSessionRegistryStore, "commit", side_effect=AssertionError("republished old generation")):
            result = self.resume()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["started_resume_state"], "checkpoint_present")
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.claims().keys(), old_claims.keys())

    def test_succeeded_output_loss_rechecks_receipt_without_entering_domain_writer(self):
        original = self.execute()
        claims, generation = self.claims(), self.store.read().sha256
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=AssertionError("succeeded writer reentered")):
            result = self.resume()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["exact_human_approval_resume_branch"], "succeeded_tail")
        self.assertFalse(result["domain_writer_reentered"])
        self.assertFalse(result["native_approval_redisplayed"])
        self.assertEqual(result["receipt_sha256"], original["receipt_sha256"])
        self.assertEqual(self.claims(), claims)
        self.assertEqual(self.store.read().sha256, generation)

    def test_later_unrelated_generation_does_not_rebind_completed_context(self):
        result = self.execute()
        for index in range(3):
            transition = registry.plan_transition(self.store.read(), action="register-app", label=f"Synthetic other app {index}")
            with exact.ExactOperationWriterLock(self.root) as held:
                self.store.commit(transition, held_lock=held)
        resumed = self.resume()
        self.assertEqual(resumed["work_session_binding"], result["work_session_binding"])
        self.assertEqual(self.store.read().revision, 5)

    def test_rehashed_terminal_mac_tamper_is_not_repaired_or_promoted(self):
        result = self.execute()
        path = self.root / exact.EXACT_OPERATION_RECEIPTS_ROOT / (result["execution_sha256"][7:] + ".json")
        document = json.loads(path.read_bytes())
        document["result"]["completion_authentication"]["terminal_mac"] = "hmac-sha256:" + "0" * 64
        document["result"].pop("result_sha256")
        document["result"]["result_sha256"] = exact._digest_document(document["result"])
        document.pop("receipt_sha256")
        document["receipt_sha256"] = exact._digest_document(document)
        path.write_bytes(exact._canonical_json_bytes(document) + b"\n")
        before = path.read_bytes(), self.claims(), self.store.read().sha256
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=AssertionError("tampered receipt wrote")):
            with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
                self.resume()
        self.assertEqual((path.read_bytes(), self.claims(), self.store.read().sha256), before)

    def test_precheckpoint_requires_exact_current_predecessor(self):
        self.cut_before_checkpoint()
        transition = registry.plan_transition(self.store.read(), action="register-app", label="Synthetic intervening app")
        with exact.ExactOperationWriterLock(self.root) as held:
            self.store.commit(transition, held_lock=held)
        before = self.claims(), self.store.read().sha256
        with self.assertRaises(bundle.WorkSessionBundleError):
            self.resume()
        self.assertEqual((self.claims(), self.store.read().sha256), before)

    def test_private_payload_without_authenticated_claim_cannot_resume(self):
        with patch.object(workflow, "_claim_exact_human_approval_core", side_effect=approval.ExactHumanApprovalError("exact_human_approval_claim_failed")):
            with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
                self.execute()
        self.assertEqual(self.claims(), {})
        with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
            self.resume()
        self.assertEqual(self.store.read().revision, 1)
        self.assertEqual(self.claims(), {})

    def test_rehashed_reviewer_payload_cannot_substitute_for_original_human_claim(self):
        self.cut_before_checkpoint()
        manifest_sha = self.manifest_sha()
        restored = bundle.load_context_bound_session_decision(self.store, manifest_sha256=manifest_sha)
        replacement = restored.prepared.context(archive_id=ARCHIVE_ID, reviewer_claim="person:different-reviewer")
        path = self.root.joinpath(*bundle.PRIVATE_ROOT) / (manifest_sha[7:] + ".json")
        document = json.loads(path.read_bytes())
        document["context"]["reviewer_claim"] = replacement.reviewer_claim
        document["context_sha256"] = approval.exact_human_approval_context_sha256(replacement)
        document.pop("bundle_sha256")
        document["bundle_sha256"] = bundle._sha(bundle._canonical(document))
        path.write_bytes(bundle._canonical(document))
        before = path.read_bytes(), self.claims(), self.store.read().sha256
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=AssertionError("different reviewer wrote")):
            with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
                self.resume()
        self.assertEqual((path.read_bytes(), self.claims(), self.store.read().sha256), before)

    def test_two_authenticated_claims_are_ambiguous_not_latest_wins(self):
        self.cut_before_checkpoint()
        restored = bundle.load_context_bound_session_decision(self.store, manifest_sha256=self.manifest_sha())

        def cut(_claim):
            raise OSError("synthetic second started claim")

        with exact.ExactOperationWriterLock(self.root):
            with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
                workflow._execute_exact_human_approved_write_core(
                    self.root, restored.context, cut, native=_Native(), key_provider=self.key,
                )
        before = self.claims(), self.store.read().sha256
        self.assertEqual(len(before[0]), 2)
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=AssertionError("ambiguous claim wrote")):
            with self.assertRaisesRegex(workflow.ExactHumanApprovalWorkflowError, "candidate_ambiguous"):
                self.resume()
        self.assertEqual((self.claims(), self.store.read().sha256), before)


if __name__ == "__main__":
    unittest.main()
