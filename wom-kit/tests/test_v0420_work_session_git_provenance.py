"""Receipt-only producer, real Git snapshots and real authenticated completion.

Only native human input, the secure-key boundary and remote transport observation
are synthetic. All Git writes in these fixtures are confined to temporary test
repositories. Classification itself must not write or repair any domain evidence.
"""

from contextlib import ExitStack
import inspect
import json
import unittest
from unittest.mock import patch

from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as workflow
from wom_kit import exact_operation_manifest as exact
from wom_kit import git_backup_writer as writer
from wom_kit import work_session_actor as actor
from wom_kit import work_session_execution as execution
from wom_kit import work_session_git_provenance as provenance
from wom_kit import work_session_operation as operation
from wom_kit import work_session_registry as registry
from wom_kit.work_session_binding import WorkSessionBinding
import test_git_backup_writer as git_fixture
from test_v0420_work_session_execution import SessionNative


class _ReadGuardKey(git_fixture._KeyProvider):
    def __init__(self):
        super().__init__()
        self.in_consumer = False
        self.read_only = False

    def use_key(self, root, consumer, *, create_if_missing=False):
        if self.in_consumer or (self.read_only and create_if_missing):
            raise AssertionError("nested or mutating credential consumer")
        self.in_consumer = True
        try:
            return super().use_key(root, consumer, create_if_missing=create_if_missing)
        finally:
            self.in_consumer = False


class ReceiptProvenanceBoundaryTests(unittest.TestCase):
    def test_fixed_error_grammar_never_hashes_or_echoes_rejected_values(self):
        class RejectedString(str):
            def __hash__(self):
                raise AssertionError("private rejected string was hashed")

        for value in ([], {}, None, True, "synthetic private rejected path",
                      RejectedString("work_session_git_snapshot_changed")):
            with self.subTest(input_type=type(value).__name__):
                failure = provenance.WorkSessionGitProvenanceError(value)
                self.assertEqual(str(failure), "work_session_git_provenance_invalid")
                self.assertIsNone(failure.__context__)
                self.assertIsNone(failure.__cause__)
        self.assertEqual(provenance.WorkSessionGitProvenanceError(
            "work_session_git_snapshot_changed").code, "work_session_git_snapshot_changed")


class ReceiptGitProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = git_fixture.GitBackupWriterTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.root = self.fixture.root
        self.git = lambda *args: self.fixture.git(self.root, *args)
        self.git("config", "core.autocrlf", "false")
        self.store, _archive_id = execution._store(self.root)
        transition = registry.plan_transition(self.store.read(), action="register-app", label="Synthetic private app")
        with exact.ExactOperationWriterLock(self.root) as held:
            self.store.commit(transition, held_lock=held)
        self.app = transition.result_refs[0]
        self.native, self.key = SessionNative(), _ReadGuardKey()
        self.owner_result = self.create_session("Synthetic private owner")
        self.owner = WorkSessionBinding.from_document(self.owner_result["work_session_binding"])
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(self.fixture.patches()[0])
        self.stack.enter_context(self.fixture.patches()[1])
        self.stack.enter_context(patch.object(workflow, "_production_key_provider", return_value=self.key))

    def create_session(self, label):
        return execution._execute_session_decision_core(
            self.root, action="create", client_app_ref=self.app, label=label,
            reviewer_claim="person:synthetic-receipt-reviewer", native=self.native, key_provider=self.key,
        )

    def receipt_path(self, result=None):
        result = self.owner_result if result is None else result
        return self.root / exact.EXACT_OPERATION_RECEIPTS_ROOT / (result["execution_sha256"][7:] + ".json")

    def evidence_bytes(self):
        return {str(path.relative_to(self.root)): path.read_bytes()
                for top in (self.root / "profiles" / "local", self.root / "receipts")
                for path in top.rglob("*") if path.is_file() and path.suffix in {".json", ".jsonl"}}

    def classify(self, *, binding=None):
        self.key.read_only = True
        with exact.ExactOperationWriterLock(self.root) as held:
            snapshot = provenance._capture_git_snapshot_held(self.root, held=held)
            result = provenance._select_receipt_changes_held(
                self.root, held=held, snapshot=snapshot,
                selected_binding=self.owner if binding is None else binding,
            )
            return snapshot, result

    def assert_partition(self, snapshot, selection):
        data = selection._private_document()
        partition = data["selection"]
        selected = [ref for group in partition["selected_groups"] for ref in group["change_refs"]]
        excluded = [row["change_ref"] for row in partition["excluded_changes"]]
        all_refs = [row["change_ref"] for row in snapshot._document()["capture"]["public_changes"]]
        self.assertEqual(sorted(selected + excluded), sorted(all_refs))
        self.assertEqual(len(selected + excluded), len(set(selected + excluded)))
        self.assertEqual(partition["expected_plan_sha256"], snapshot._document()["plan_sha256"])
        if selected:
            writer._selection_partition(partition, expected_plan_sha256=partition["expected_plan_sha256"],
                                        observed_change_refs=all_refs)
        self.assertTrue(selection.public_summary()["snapshot_partition_complete"])
        self.assertFalse(selection.public_summary()["artifact_backup_complete"])
        self.assertFalse(selection.public_summary()["backup_performed"])
        return partition

    def test_two_authenticated_sessions_unknown_documents_and_original_binding_after_later_revision(self):
        other_result = self.create_session("Synthetic private other")
        with exact.ExactOperationWriterLock(self.root) as held:
            claim = registry.plan_transition(self.store.read(), action="claim", client_app_ref=self.app,
                                             work_session_ref=self.owner.work_session_ref)
            self.store.commit(claim, held_lock=held)
        current = self.store.read().binding(self.owner.work_session_ref)
        self.assertGreater(current.revision, self.owner.revision)
        before = self.evidence_bytes()
        native_calls = self.native.calls
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=AssertionError("writer called")), \
             patch.object(actor.WorkSessionActorStore, "save", side_effect=AssertionError("actor written")), \
             patch.object(exact.FileExactOperationCheckpointStore, "append", side_effect=AssertionError("checkpoint written")), \
             patch.object(exact.FileExactOperationCheckpointStore, "finalize", side_effect=AssertionError("receipt written")), \
             patch.object(approval, "_claim_exact_human_approval_core", side_effect=AssertionError("claim published")):
            snapshot, selection = self.classify(binding=current)
        partition = self.assert_partition(snapshot, selection)
        self.assertEqual(selection.public_summary()["selected_receipt_count"], 1)
        self.assertEqual(selection.public_summary()["other_session_receipt_count"], 1)
        captured_rows = snapshot._document()["capture"]["private_changes"]
        self.assertEqual(selection.public_summary()["ownership_unverified_count"], len(captured_rows) - 2)
        by_path = {row["path"]: row["public_observation"]["change_ref"] for row in captured_rows}
        unknown_refs = {row["change_ref"] for row in partition["excluded_changes"] if row["scope"] == "unknown"}
        self.assertTrue({by_path["tracked.txt"], by_path["new-private.txt"]}.issubset(unknown_refs))
        self.assertEqual(self.native.calls, native_calls)
        self.assertEqual(self.evidence_bytes(), before)
        proof = next(row for row in selection._private_document()["proofs"]
                     if row["execution_sha256"] == self.owner_result["execution_sha256"])
        self.assertEqual(proof["original_work_session_binding"], self.owner.document())
        self.assertNotEqual(proof["original_work_session_binding"], current.document())
        self.assertEqual(len(selection._private_document()["proofs"]), 2)
        self.assertFalse(selection.public_summary()["current_claim_authority_evaluated"])
        for marker in (str(self.root), "Synthetic private", "tracked.txt", "new-private.txt",
                       self.app, other_result["work_session_binding"]["work_session_ref"]):
            self.assertNotIn(marker, json.dumps(selection.public_summary()) + repr(selection) + repr(snapshot))
        # Frozen values do not retain document aliases returned to internal callers.
        partition["selected_groups"].clear()
        self.assertEqual(selection.public_summary()["selected_receipt_count"], 1)

    def test_index_same_canonical_bytes_is_eligible(self):
        self.git("add", "--", self.receipt_path().relative_to(self.root).as_posix())
        snapshot, selection = self.classify()
        self.assert_partition(snapshot, selection)
        self.assertEqual(selection.public_summary()["selected_receipt_count"], 1)

    def test_explicit_private_provider_is_used_when_default_provider_is_forbidden(self):
        before, native_calls = self.evidence_bytes(), self.native.calls
        self.key.read_only = True
        self.key.create_if_missing.clear()
        with exact.ExactOperationWriterLock(self.root) as held, \
             patch.object(workflow, "_production_key_provider",
                          side_effect=AssertionError("default provider entered")) as default:
            snapshot = provenance._capture_git_snapshot_held(self.root, held=held)
            selection = provenance._select_receipt_changes_held(
                self.root, held=held, snapshot=snapshot, selected_binding=self.owner,
                key_provider=self.key,
            )
            default.assert_not_called()
            held.verify_held()
        self.assert_partition(snapshot, selection)
        self.assertEqual(selection.public_summary()["selected_receipt_count"], 1)
        self.assertEqual(selection.public_summary()["unverified_receipt_candidate_count"], 0)
        self.assertEqual(self.key.create_if_missing, [False])
        self.assertFalse(self.key.in_consumer)
        self.assertEqual(self.native.calls, native_calls)
        self.assertEqual(self.evidence_bytes(), before)

    def test_index_different_bytes_is_unknown_and_preserved(self):
        path = self.receipt_path()
        original = path.read_bytes()
        path.write_bytes(b"synthetic staged bytes\n")
        self.git("add", "--", path.relative_to(self.root).as_posix())
        path.write_bytes(original)
        old_index = self.git("show", ":" + path.relative_to(self.root).as_posix()).stdout
        snapshot, selection = self.classify()
        self.assert_partition(snapshot, selection)
        self.assertEqual(selection.public_summary()["selected_receipt_count"], 0)
        self.assertEqual(selection.public_summary()["unverified_receipt_candidate_count"], 1)
        self.assertEqual(self.git("show", ":" + path.relative_to(self.root).as_posix()).stdout, old_index)
        self.assertEqual(path.read_bytes(), original)

    def test_head_existing_even_if_worktree_has_authentic_receipt_is_unknown(self):
        path = self.receipt_path()
        original = path.read_bytes()
        path.write_bytes(b"historical unrelated bytes\n")
        relative = path.relative_to(self.root).as_posix()
        self.git("add", "--", relative)
        self.git("commit", "--only", "-m", "synthetic historical receipt path", "--", relative)
        self.git("push", str(self.fixture.remote), "HEAD:refs/heads/main")
        path.write_bytes(original)
        snapshot, selection = self.classify()
        self.assert_partition(snapshot, selection)
        self.assertEqual(selection.public_summary()["selected_receipt_count"], 0)
        self.assertEqual(selection.public_summary()["unverified_receipt_candidate_count"], 1)

    def test_forged_corrupt_mutated_and_noncanonical_receipts_remain_unknown(self):
        path = self.receipt_path()
        original = path.read_bytes()
        mutated = json.loads(original)
        mutated["result"]["completion_authentication"]["terminal_mac"] = "hmac-sha256:" + "0" * 64
        # Even recomputing every unkeyed envelope digest grants no authority.
        result_basis = dict(mutated["result"])
        result_basis.pop("result_sha256")
        mutated["result"]["result_sha256"] = exact._digest_document(result_basis)
        receipt_basis = dict(mutated)
        receipt_basis.pop("receipt_sha256")
        mutated["receipt_sha256"] = exact._digest_document(receipt_basis)
        variants = {
            "corrupt": b"{\n", "forged": b'{"schema":"forged","result":{}}\n',
            "mutated_mac": exact._canonical_json_bytes(mutated) + b"\n",
            "noncanonical_whitespace": b" " + original,
        }
        for name, raw in variants.items():
            with self.subTest(name=name):
                path.write_bytes(raw)
                before = self.evidence_bytes()
                snapshot, selection = self.classify()
                self.assert_partition(snapshot, selection)
                self.assertEqual(selection.public_summary()["selected_receipt_count"], 0)
                self.assertEqual(selection.public_summary()["unverified_receipt_candidate_count"], 1)
                self.assertEqual(selection.public_summary()["status"], "no_eligible_receipts")
                self.assertEqual(self.evidence_bytes(), before)

    def test_corrupt_original_claim_excluded_without_new_claim_or_receipt(self):
        claims = list((self.root / approval.CLAIMS_RELATIVE_ROOT).glob("*.json"))
        self.assertEqual(len(claims), 1)
        claims[0].write_bytes(b"{\n")
        before = self.evidence_bytes()
        snapshot, selection = self.classify()
        self.assert_partition(snapshot, selection)
        self.assertEqual(selection.public_summary()["selected_receipt_count"], 0)
        self.assertEqual(selection.public_summary()["unverified_receipt_candidate_count"], 1)
        self.assertEqual(self.evidence_bytes(), before)

    def test_started_original_claim_cannot_publish_or_repair_evidence(self):
        # A valid completed receipt paired with an authenticated started claim
        # is not completed authority; restore the original started claim captured
        # at the real pre-writer boundary of a second decision.
        started_claims = {}
        original_apply = operation.apply_session_decision_with_claim

        def capture_started(*args, **kwargs):
            started_claims.update({path: path.read_bytes()
                                  for path in (self.root / approval.CLAIMS_RELATIVE_ROOT).glob("*.json")})
            return original_apply(*args, **kwargs)

        with patch.object(operation, "apply_session_decision_with_claim", side_effect=capture_started):
            second = self.create_session("Synthetic private started evidence")
        second_binding = WorkSessionBinding.from_document(second["work_session_binding"])
        for path, raw in started_claims.items():
            path.write_bytes(raw)
        before = self.evidence_bytes()
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=AssertionError("writer entered")):
            snapshot, selection = self.classify(binding=second_binding)
        self.assert_partition(snapshot, selection)
        self.assertEqual(selection.public_summary()["selected_receipt_count"], 0)
        self.assertGreaterEqual(selection.public_summary()["unverified_receipt_candidate_count"], 1)
        self.assertEqual(self.evidence_bytes(), before)

    def test_ignored_receipt_not_force_added_and_not_complete_backup(self):
        with (self.root / ".gitignore").open("a", encoding="utf-8") as stream:
            stream.write("receipts/ops/exact-operations/\n")
        before = self.evidence_bytes()
        snapshot, selection = self.classify()
        self.assert_partition(snapshot, selection)
        self.assertEqual(selection.public_summary()["selected_receipt_count"], 0)
        self.assertEqual(selection.public_summary()["unverified_receipt_candidate_count"], 0)
        self.assertFalse(selection.public_summary()["artifact_backup_complete"])
        self.assertTrue(self.receipt_path().exists())
        self.assertEqual(self.evidence_bytes(), before)
        self.assertNotIn(self.receipt_path().relative_to(self.root).as_posix(),
                         [row["path"] for row in snapshot._document()["capture"]["private_changes"]])

    def test_snapshot_drift_before_and_during_classification_fails_closed(self):
        self.key.read_only = True
        with exact.ExactOperationWriterLock(self.root) as held:
            snapshot = provenance._capture_git_snapshot_held(self.root, held=held)
            path = self.root / "new-private.txt"
            path.write_text("synthetic drift before\n", encoding="utf-8")
            with self.assertRaises(provenance.WorkSessionGitProvenanceError) as caught:
                provenance._select_receipt_changes_held(self.root, held=held, snapshot=snapshot, selected_binding=self.owner)
            self.assertEqual(caught.exception.code, "work_session_git_snapshot_changed")
            self.assertIsNone(caught.exception.__context__)
            snapshot = provenance._capture_git_snapshot_held(self.root, held=held)
            original = provenance._authenticated_receipt

            def drift(*args, **kwargs):
                proof = original(*args, **kwargs)
                path.write_text("synthetic drift during\n", encoding="utf-8")
                return proof

            with patch.object(provenance, "_authenticated_receipt", side_effect=drift):
                with self.assertRaises(provenance.WorkSessionGitProvenanceError) as caught:
                    provenance._select_receipt_changes_held(self.root, held=held, snapshot=snapshot, selected_binding=self.owner)
            self.assertEqual(caught.exception.code, "work_session_git_snapshot_changed")
            self.assertIsNone(caught.exception.__context__)

    def test_lock_and_typed_data_not_public_approval_or_raw_key_seams(self):
        with self.assertRaises(provenance.WorkSessionGitProvenanceError) as caught:
            provenance._capture_git_snapshot_held(self.root, held=object())
        self.assertIsNone(caught.exception.__context__)
        with exact.ExactOperationWriterLock(self.root) as held:
            with self.assertRaises(provenance.WorkSessionGitProvenanceError):
                provenance._select_receipt_changes_held(self.root, held=held, snapshot={}, selected_binding=self.owner)
        for function in (provenance._capture_git_snapshot_held, provenance._select_receipt_changes_held):
            params = inspect.signature(function).parameters
            self.assertTrue({"key", "native", "approve", "claim_ref", "context"}.isdisjoint(params))
        self.assertNotIn("key_provider", inspect.signature(provenance._capture_git_snapshot_held).parameters)
        self.assertIsNone(inspect.signature(provenance._select_receipt_changes_held).parameters["key_provider"].default)


if __name__ == "__main__":
    unittest.main()
