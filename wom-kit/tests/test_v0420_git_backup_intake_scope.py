"""Pure v2 proof binding, NOT authenticated provenance or backup authority."""

import hashlib
import json
import unittest
from unittest.mock import patch

from test_v0420_git_backup_session_scope import proof_fixture, scope_for_selection
from test_v0420_git_selection import archive_binding
from wom_kit import git_backup_session_scope as subject


def digest(value):
    return "sha256:" + hashlib.sha256(str(value).encode("ascii")).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("ascii")


def intake_proof(binding, ordinal=1, kind="source_intake_receipt"):
    proof = proof_fixture(binding, change_ref=f"change:{ordinal:06d}")
    proof.pop("registry_generation_sha256")
    proof.update(producer="authenticated_source_intake_batch_output", output_kind=kind,
                 output_identity_sha256=digest(ordinal), intake_scope_sha256=digest("scope"))
    if kind == "common_completion_receipt":
        proof["output_identity_sha256"] = proof["execution_sha256"]
    return proof


def selection(proofs):
    return {"schema": "wom-kit/git-backup-selection/v2", "expected_plan_sha256": digest("plan"),
            "selected_groups": [{"group_id": "group:synthetic-intake", "commit_subject": "Back up intake evidence",
                                 "change_refs": [proof["change_ref"] for proof in proofs]}], "excluded_changes": []}


def source_row(proof):
    return {"path": subject._proof_output_path(proof), "original_path": None,
            "public_observation": {"change_ref": proof["change_ref"], "operation": "added_untracked",
                "head": {"state": "absent"}, "index": {"state": "absent"},
                "worktree": {"state": "regular_file", "sha256": proof["whole_file_sha256"],
                             "bytes": proof["whole_file_bytes"]}}}


class IntakeGitScopeContractTests(unittest.TestCase):
    def setUp(self):
        self.binding = archive_binding()
        self.proof = intake_proof(self.binding)
        self.selection = selection([self.proof])
        self.scope = scope_for_selection(self.selection, self.binding, [self.proof])

    def test_legacy_v1_raw_hash_and_evidence_stay_exact(self):
        old_proof = proof_fixture(self.binding)
        old_selection = selection([old_proof])
        old = scope_for_selection(old_selection, self.binding, [old_proof])
        basis = {"schema": "wom-kit/git-backup-session-scope/v1", "task_route_ref": "task_route_" + "5" * 32,
                 "actor_sha256": "sha256:" + "6" * 64, "registry_preimage_sha256": "sha256:" + "7" * 64,
                 "claim_ref": "claim_" + "8" * 32, "work_session_binding": self.binding.document(),
                 "selection_sha256": "sha256:" + hashlib.sha256(canonical(old_selection)).hexdigest(),
                 "selected_change_count": 1, "excluded_change_count": 0, "producer_proofs": [old_proof]}
        expected = {**basis, "scope_sha256": "sha256:" + hashlib.sha256(canonical(basis)).hexdigest()}
        self.assertEqual(old._raw, canonical(expected))
        evidence = old.operation_evidence().document()
        self.assertEqual(evidence["schema"], "wom-kit/git-backup-session-scope-evidence/v1")
        self.assertEqual(evidence["digests"]["producer_proofs_sha256"],
                         "sha256:" + hashlib.sha256(canonical([old_proof])).hexdigest())
        self.assertEqual(subject._GitBackupSessionScope.from_document(expected)._raw, old._raw)

    def test_v2_closed_union_preserves_original_bindings_and_all_target_spellings(self):
        proofs = [intake_proof(self.binding, index, kind) for index, kind in enumerate((
            "source_intake_receipt", "prepared_capture_request", "common_completion_receipt"), 1)]
        proofs.append(proof_fixture(self.binding, change_ref="change:000004", execution="f"))
        picked = selection(proofs)
        scope = scope_for_selection(picked, self.binding, proofs)
        self.assertEqual(scope.document()["schema"], "wom-kit/git-backup-session-scope/v2")
        self.assertEqual(scope.operation_evidence().document()["schema"],
                         "wom-kit/git-backup-session-scope-evidence/v2")
        scope.validate_selection(self.binding, picked)
        # Literal domain spellings form an independent oracle; do not obtain
        # the expected path from the helper that is being verified.
        paths = ["receipts/sources/source-intake-" + proofs[0]["output_identity_sha256"][7:23]
                 + ".source-intake-plan.json",
                 "receipts/ops/source-intake-batches/capture-requests/"
                 + proofs[1]["output_identity_sha256"][7:] + ".objet-capture-request.json",
                 "receipts/ops/exact-operations/" + "e" * 64 + ".json",
                 "receipts/ops/exact-operations/" + "f" * 64 + ".json"]
        self.assertEqual([subject._proof_output_path(proof) for proof in proofs], paths)
        scope.validate_sources([{**source_row(proof), "path": path} for proof, path in zip(proofs, paths)])
        self.assertEqual(scope.document()["producer_proofs"], proofs)
        self.assertNotIn("registry_generation_sha256", scope.document()["producer_proofs"][0])
        proofs[0]["intake_scope_sha256"] = digest("replaced")
        self.assertNotEqual(scope.document()["producer_proofs"][0], proofs[0])

    def test_one_thousand_intake_items_bind_all_one_thousand_two_outputs(self):
        proofs = [intake_proof(self.binding, index) for index in range(1, 1001)]
        proofs.extend([intake_proof(self.binding, 1001, "prepared_capture_request"),
                       intake_proof(self.binding, 1002, "common_completion_receipt")])
        picked = selection(proofs)
        scope = scope_for_selection(picked, self.binding, proofs)
        self.assertGreater(len(scope._raw), subject._MAX_BYTES)
        self.assertLess(len(scope._raw), subject._MAX_V2_BYTES)
        self.assertEqual(scope.document()["selected_change_count"], 1002)
        self.assertEqual(scope.operation_evidence().document()["counts"]["producer_proof_count"], 1002)
        scope.validate_selection(self.binding, picked)
        scope.validate_sources([source_row(proof) for proof in proofs])
        self.assertEqual(subject._GitBackupSessionScope.from_document(scope.document())._raw, scope._raw)

    def test_false_or_cross_version_shapes_refuse_even_after_full_rehash(self):
        mutations = (
            lambda value: value.update(schema=subject._SCHEMA),
            lambda value: value["producer_proofs"][0].update(producer="SYNTHETIC_PRIVATE"),
            lambda value: value["producer_proofs"][0].update(output_kind="inferred_from_filename"),
            lambda value: value["producer_proofs"][0].update(path="SYNTHETIC_PRIVATE"),
            lambda value: value["producer_proofs"][0].update(registry_generation_sha256=digest("not a generation")),
            lambda value: value["producer_proofs"][0].update(output_identity_sha256="SYNTHETIC_PRIVATE"),
            lambda value: value["producer_proofs"][0].update(whole_file_bytes=True),
            lambda value: value["producer_proofs"][0].update(output_kind="common_completion_receipt"),
            lambda value: value["producer_proofs"][0]["original_work_session_binding"].update(
                archive_identity_sha256=digest("foreign archive")),
        )
        for change in mutations:
            value = self.scope.document()
            change(value)
            value["scope_sha256"] = "sha256:" + hashlib.sha256(canonical(
                {key: item for key, item in value.items() if key != "scope_sha256"})).hexdigest()
            with self.subTest(change=change), self.assertRaises(subject.GitBackupSessionScopeError) as caught:
                subject._GitBackupSessionScope.from_document(value)
            self.assertEqual(str(caught.exception), "git_backup_session_scope_invalid")
            self.assertIsNone(caught.exception.__context__)
            self.assertIsNone(caught.exception.__cause__)

    def test_v2_does_not_silently_upgrade_legacy_only_original(self):
        proof = proof_fixture(self.binding)
        old = scope_for_selection(selection([proof]), self.binding, [proof]).document()
        old["schema"] = subject._SCHEMA_V2
        old["scope_sha256"] = "sha256:" + hashlib.sha256(canonical(
            {key: value for key, value in old.items() if key != "scope_sha256"})).hexdigest()
        with self.assertRaises(subject.GitBackupSessionScopeError):
            subject._GitBackupSessionScope.from_document(old)

    def test_whole_new_output_rules_remain_strict(self):
        for change in (
            lambda row: row.update(path="SYNTHETIC_PRIVATE"),
            lambda row: row.update(original_path="old-name"),
            lambda row: row["public_observation"].update(operation="modified"),
            lambda row: row["public_observation"]["head"].update(state="blob"),
            lambda row: row["public_observation"]["worktree"].update(state="symlink"),
            lambda row: row["public_observation"]["worktree"].update(sha256=digest("changed")),
            lambda row: row["public_observation"]["index"].update(state="blob", mode="regular_file",
                                                                  sha256=digest("other staged bytes"), bytes=1),
        ):
            row = source_row(self.proof)
            change(row)
            with self.subTest(change=change), self.assertRaises(subject.GitBackupSessionScopeError):
                self.scope.validate_sources([row])
        same = source_row(self.proof)
        same["public_observation"]["index"] = {"state": "blob", "mode": "regular_file",
            "sha256": self.proof["whole_file_sha256"], "bytes": self.proof["whole_file_bytes"]}
        self.scope.validate_sources([same])

    def test_explicit_v2_budgets_refuse_whole_scope_not_truncate(self):
        with patch.object(subject, "_MAX_V2_PROOFS", 0):
            with self.assertRaises(subject.GitBackupSessionScopeError):
                subject._GitBackupSessionScope.from_document(self.scope.document())
        value = self.scope.document()
        with patch.object(subject, "_MAX_V2_BYTES", len(self.scope._raw) - 1):
            with self.assertRaises(subject.GitBackupSessionScopeError):
                subject._GitBackupSessionScope.from_document(value)


if __name__ == "__main__":
    unittest.main()
