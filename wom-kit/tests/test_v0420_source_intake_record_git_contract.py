"""Closed producer DATA contracts; synthetic views are not MAC acceptance."""

from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_v0420_git_backup_intake_scope import canonical, digest, intake_proof, selection, source_row
from test_v0420_git_backup_session_scope import proof_fixture, scope_for_selection
from test_v0420_git_selection import archive_binding
from wom_kit import exact_human_approval as approval
from wom_kit import exact_operation_manifest as exact
from wom_kit import git_backup_session_scope as scope
from wom_kit import work_session_git_provenance as git_provenance
from wom_kit import work_session_git_workflow as git_workflow
from wom_kit import work_session_intake_git_provenance as subject
from wom_kit import work_session_source_intake_bundle as batch_bundle
from wom_kit import work_session_source_intake_record_bundle as record_bundle
from wom_kit import work_session_source_intake_completion as completion
from wom_kit import work_session_source_intake_inventory as inventory


RECORD = "authenticated_source_intake_record_output"
BATCH = "authenticated_source_intake_batch_output"


def record_proof(binding, ordinal=1, kind="source_intake_receipt"):
    return {**intake_proof(binding, ordinal, kind), "producer": RECORD}


class RecordGitScopeTests(unittest.TestCase):
    def test_record_v2_is_distinct_and_has_exactly_two_metadata_output_kinds(self):
        binding = archive_binding()
        proofs = [record_proof(binding, 1), record_proof(binding, 2, "common_completion_receipt")]
        selected = selection(proofs)
        value = scope_for_selection(selected, binding, proofs)
        self.assertEqual(value.document()["schema"], scope._SCHEMA_V2)
        self.assertEqual(value.document()["producer_proofs"], proofs)
        paths = ["receipts/sources/source-intake-" + proofs[0]["output_identity_sha256"][7:23] + ".source-intake-plan.json",
                 "receipts/ops/exact-operations/" + proofs[1]["execution_sha256"][7:] + ".json"]
        self.assertEqual([scope._proof_output_path(row) for row in proofs], paths)
        value.validate_selection(binding, selected)
        value.validate_sources([source_row(row) for row in proofs])
        self.assertEqual(scope._GitBackupSessionScope.from_document(value.document())._raw, value._raw)

    def test_existing_human_v1_and_batch_v2_canonical_bytes_and_evidence_are_unchanged(self):
        binding = archive_binding()
        for proof, schema, evidence_schema in (
            (proof_fixture(binding), scope._SCHEMA, scope._EVIDENCE_SCHEMA),
            (intake_proof(binding), scope._SCHEMA_V2, scope._EVIDENCE_SCHEMA_V2),
        ):
            picked = selection([proof])
            basis = {"schema": schema, "task_route_ref": "task_route_" + "5" * 32,
                "actor_sha256": "sha256:" + "6" * 64, "registry_preimage_sha256": "sha256:" + "7" * 64,
                "claim_ref": "claim_" + "8" * 32, "work_session_binding": binding.document(),
                "selection_sha256": "sha256:" + hashlib.sha256(canonical(picked)).hexdigest(),
                "selected_change_count": 1, "excluded_change_count": 0, "producer_proofs": [proof]}
            expected = {**basis, "scope_sha256": "sha256:" + hashlib.sha256(canonical(basis)).hexdigest()}
            value = scope_for_selection(picked, binding, [proof])
            self.assertEqual(value._raw, canonical(expected))
            self.assertEqual(value.operation_evidence().document(), {
                "schema": evidence_schema, "private_values_echoed": False,
                "counts": {"selected_change_count": 1, "excluded_change_count": 0, "producer_proof_count": 1},
                "digests": {"session_scope_sha256": expected["scope_sha256"], "selection_sha256": basis["selection_sha256"],
                    "producer_proofs_sha256": "sha256:" + hashlib.sha256(canonical([proof])).hexdigest()}})

    def test_record_cannot_claim_capture_unknown_family_or_v1_even_after_rehash(self):
        binding = archive_binding()
        proof = record_proof(binding)
        original = scope_for_selection(selection([proof]), binding, [proof])
        for key, value in (("output_kind", "prepared_capture_request"), ("output_kind", []),
                           ("producer", "SYNTHETIC_PRIVATE_FAMILY"), ("producer", [])):
            document = original.document()
            document["producer_proofs"][0][key] = value
            document["scope_sha256"] = "sha256:" + hashlib.sha256(canonical(
                {k: v for k, v in document.items() if k != "scope_sha256"})).hexdigest()
            with self.assertRaises(scope.GitBackupSessionScopeError):
                scope._GitBackupSessionScope.from_document(document)
            with self.assertRaises(subject.WorkSessionIntakeGitProvenanceError):
                subject._stored(document["producer_proofs"], [source_row(proof)])
        legacy = original.document()
        legacy["schema"] = scope._SCHEMA
        legacy["scope_sha256"] = "sha256:" + hashlib.sha256(canonical(
            {k: v for k, v in legacy.items() if k != "scope_sha256"})).hexdigest()
        with self.assertRaises(scope.GitBackupSessionScopeError):
            scope._GitBackupSessionScope.from_document(legacy)

    def test_git_dispatch_and_summary_count_single_receipts_without_inventing_capture(self):
        binding = archive_binding()
        proofs = [record_proof(binding, 1), record_proof(binding, 2, "common_completion_receipt")]
        prepared = SimpleNamespace(session_scope=SimpleNamespace(document=lambda: {"producer_proofs": proofs}))
        self.assertEqual(git_workflow._partition_producer_proofs(prepared), ([], proofs))
        result = git_provenance._ReceiptSelection(git_provenance._canonical({
            "selection": selection(proofs), "proofs": proofs, "unverified_receipt_candidates": 0})).public_summary()
        self.assertEqual(result["selected_output_count"], 2)
        self.assertEqual(result["selected_receipt_count"], 2)
        self.assertEqual(result["selected_intake_output_count"], 2)
        self.assertTrue(result["receipt_only"])
        self.assertFalse(result["source_bytes_backed_up"] or result["artifact_capture_performed"]
                         or result["artifact_backup_complete"] or result["current_claim_authority_evaluated"])


class RecordGitAdapterContractTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.archive_id = "archive:personal:record-git-data"
        (self.root / "archive.yml").write_text("archive_id: " + self.archive_id + "\n", encoding="utf-8")
        self.binding = archive_binding(archive_id=self.archive_id)

    def facts(self, manifest=None):
        return {"manifest_sha256": manifest or digest("manifest"), "context_sha256": digest("context"),
            "execution_sha256": digest("execution"), "common_final_receipt_sha256": digest("final"),
            "common_result_sha256": digest("result"), "approval_binding_sha256": digest("approval"),
            "session_scope_sha256": digest("scope"), "work_session_binding": self.binding.document()}

    def outputs(self):
        identity = digest("output")
        return {"receipts/sources/source-intake-" + identity[7:23] + ".source-intake-plan.json": {
            "output_kind": "source_intake_receipt", "target_kind": "source_intake_record", "field_ref": "receipt_bytes",
            "sha256": digest("bytes"), "size_bytes": 12, "output_identity_sha256": identity}}

    def view(self, stack, kind, facts, outputs):
        # Deliberately synthetic exact view; only dispatch/data contracts here.
        value = object.__new__(kind)
        stack.enter_context(patch.object(kind, "proof_document", return_value=facts))
        stack.enter_context(patch.object(kind, "approved_output_map", return_value=outputs))
        stack.enter_context(patch.object(kind, "image_sha256", new=property(lambda _: digest("image"))))
        return value

    def snapshot(self, rows):
        return git_provenance._GitChangeSnapshot(subject._canonical({"plan_sha256": digest("gitplan"),
            "capture": {"root": str(self.root), "archive_id": self.archive_id, "private_changes": rows,
                        "public_changes": [row["public_observation"] for row in rows]}}))

    def test_closed_reader_types_do_not_confuse_record_subclasses_with_batch_or_data_with_auth(self):
        pairs = ((BATCH, completion._VerifiedSessionSourceIntakeCompletion, completion._SessionSourceIntakeCompletionImage),
                 (RECORD, completion._VerifiedSessionSourceIntakeRecordCompletion, completion._SessionSourceIntakeRecordCompletionImage))
        for producer, authenticated, image in pairs:
            self.assertIs(subject._reader_api(producer, "key")[1], authenticated)
            self.assertIs(subject._reader_api(producer, "claim")[1], authenticated)
            self.assertIs(subject._reader_api(producer, "image")[1], image)
            other = pairs[1 if producer == BATCH else 0][1]
            for value in (object.__new__(image), object.__new__(other), {}, True):
                with self.assertRaises(subject.WorkSessionIntakeGitProvenanceError):
                    subject._origin(value, authenticated, producer=producer)
        for producer in ([], {}, True, "unknown"):
            with self.assertRaises(subject.WorkSessionIntakeGitProvenanceError):
                subject._reader_api(producer, "key")

    def test_stored_record_proofs_use_only_original_reader_once_and_never_inventory(self):
        facts, outputs = self.facts(), self.outputs()
        path, output = next(iter(outputs.items()))
        proof = subject._proof(facts, output, "change:000001", producer=RECORD)
        rows = [{**source_row(proof), "path": path}]
        with exact.ExactOperationWriterLock(self.root) as held, ExitStack() as stack:
            for name in ("_capture_source_intake_context_inventory_held", "_capture_source_intake_record_context_inventory_held"):
                stack.enter_context(patch.object(inventory, name, side_effect=AssertionError("rediscovery")))
            for mode, api, kind in (
                ("key", "_read_completed_session_source_intake_record_held", completion._VerifiedSessionSourceIntakeRecordCompletion),
                ("claim", "_verify_completed_session_source_intake_record_with_claim_held", completion._VerifiedSessionSourceIntakeRecordCompletion),
                ("image", "_read_session_source_intake_record_completion_image_held", completion._SessionSourceIntakeRecordCompletionImage),
            ):
                with ExitStack() as local:
                    view = self.view(local, kind, facts, outputs)
                    read = local.enter_context(patch.object(completion, api, return_value=view))
                    kwargs = {"claim": object()} if mode == "claim" else {"key_provider": object()} if mode == "key" else {}
                    result = subject._revalidate(self.root, held, [proof], rows, mode, **kwargs)
                    read.assert_called_once()
                    self.assertEqual(read.call_args.kwargs["manifest_sha256"], facts["manifest_sha256"])
                    self.assertEqual("key_provider" in read.call_args.kwargs, mode == "key")
                    self.assertEqual("claim" in read.call_args.kwargs, mode == "claim")
                    self.assertEqual(result, ((facts["manifest_sha256"], facts["context_sha256"], facts["execution_sha256"], digest("image")),)
                                     if mode == "image" else [proof])
                    forged = {**proof, "intake_scope_sha256": digest("forged")}
                    with self.assertRaises(subject.WorkSessionIntakeGitProvenanceError):
                        subject._revalidate(self.root, held, [forged], rows, mode, **kwargs)

    def test_wrong_inventory_family_refuses_and_corrupt_record_hint_stays_unknown(self):
        row = {"path": "generic.md", "original_path": None, "public_observation": {
            "change_ref": "change:000001", "operation": "added_untracked", "head": {"state": "absent"},
            "index": {"state": "absent"}, "worktree": {"state": "regular_file", "sha256": digest("generic"), "bytes": 12}}}
        with exact.ExactOperationWriterLock(self.root) as held:
            batch = inventory._capture_source_intake_context_inventory_held(self.root, held=held)
            with patch.object(inventory, "_capture_source_intake_record_context_inventory_held", return_value=batch):
                with self.assertRaises(subject.WorkSessionIntakeGitProvenanceError):
                    subject._select_intake_output_changes_held(self.root, held=held, snapshot=self.snapshot([row]), selected_binding=self.binding)
            directory = self.root.joinpath(*record_bundle.PRIVATE_ROOT)
            directory.mkdir(parents=True)
            (directory / ("a" * 64 + ".json")).write_bytes(b"not a context")
            result = subject._select_intake_output_changes_held(self.root, held=held,
                snapshot=self.snapshot([row]), selected_binding=self.binding).public_summary()
            self.assertEqual(result["hint_inventory_state"], "present")
            self.assertEqual(result["context_hint_count"], 1)
            self.assertEqual(result["unverified_context_hint_count"], 1)
            self.assertEqual(result["authenticated_original_count"], 0)
            self.assertEqual(result["ownership_unverified_count"], 1)
            self.assertFalse(result["artifact_backup_complete"])

    def test_conflicting_authenticated_output_paths_across_families_refuse_whole_partition(self):
        with exact.ExactOperationWriterLock(self.root) as held, ExitStack() as stack:
            for module, letter in ((batch_bundle, "a"), (record_bundle, "b")):
                directory = self.root.joinpath(*module.PRIVATE_ROOT)
                directory.mkdir(parents=True)
                (directory / (letter * 64 + ".json")).write_bytes(b"synthetic opaque hint")
                stack.enter_context(patch.object(module, "_decode_context", return_value=(None, object())))
            stack.enter_context(patch.object(approval, "exact_human_approval_context_sha256", return_value=digest("context")))
            for letter, kind, api in (("a", completion._VerifiedSessionSourceIntakeCompletion, "_read_completed_session_source_intake_held"),
                                      ("b", completion._VerifiedSessionSourceIntakeRecordCompletion, "_read_completed_session_source_intake_record_held")):
                view = self.view(stack, kind, self.facts("sha256:" + letter * 64), self.outputs())
                stack.enter_context(patch.object(completion, api, return_value=view))
            with self.assertRaises(subject.WorkSessionIntakeGitProvenanceError) as caught:
                subject._select_intake_output_changes_held(self.root, held=held, snapshot=self.snapshot([]), selected_binding=self.binding)
            self.assertEqual(caught.exception.code, "work_session_intake_git_proof_ambiguous")


if __name__ == "__main__":
    unittest.main()
