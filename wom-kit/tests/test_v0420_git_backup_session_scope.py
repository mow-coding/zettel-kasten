"""Session Git scope binds facts; these synthetic proofs are NOT authenticated.

Only the existing local Git fixture is used. No approval, current ownership,
receipt MAC or backup completion is established by constructing a scope.
"""

from dataclasses import FrozenInstanceError, replace
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_git_backup_writer as fixtures
import test_v0420_git_selection as selection_fixtures
from test_v0420_work_session_binding import binding_fixture
from wom_kit import exact_human_approval as approval
from wom_kit import exact_operation_manifest as exact
from wom_kit import git_backup_plan as planning
from wom_kit import git_backup_writer as writer
from wom_kit import git_backup_session_scope as scopes
from wom_kit import work_session_git_bundle as bundles


def proof_fixture(binding, *, change_ref="change:000001", execution="e", raw=b"synthetic receipt"):
    return {
        "change_ref": change_ref, "producer": "authenticated_work_session_completion_receipt",
        "whole_file_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(), "whole_file_bytes": len(raw),
        "execution_sha256": "sha256:" + execution * 64,
        "receipt_sha256": "sha256:" + "1" * 64, "manifest_sha256": "sha256:" + "2" * 64,
        "context_sha256": "sha256:" + "3" * 64, "registry_generation_sha256": "sha256:" + "4" * 64,
        "original_work_session_binding": binding.document(),
    }


def scope_for_selection(document, binding, proofs, **changes):
    fields = {
        "task_route_ref": "task_route_" + "5" * 32, "actor_sha256": "sha256:" + "6" * 64,
        "registry_preimage_sha256": "sha256:" + "7" * 64, "claim_ref": "claim_" + "8" * 32,
        "work_session_binding": binding, "selection_sha256": writer._sha256_json(document),
        "selected_change_count": sum(len(group["change_refs"]) for group in document["selected_groups"]),
        "excluded_change_count": len(document["excluded_changes"]), "producer_proofs": proofs,
    }
    return scopes._GitBackupSessionScope.build(**(fields | changes))


def prepare_scoped_fixture(fixture):
    """Shared positive codec fixture only; never an authenticated proof producer."""
    binding = selection_fixtures.archive_binding(revision=7)
    original = selection_fixtures.archive_binding(revision=6)
    other = binding_fixture(binding.archive_identity_sha256, work_session_ref="work_session_" + "9" * 32)
    proof_by_path = {}
    for execution, producer_binding in (("e", original), ("f", other)):
        raw = b"Synthetic whole receipt; deliberately unauthenticated " + execution.encode("ascii")
        proof = proof_fixture(producer_binding, execution=execution, raw=raw)
        path = "receipts/ops/exact-operations/" + execution * 64 + ".json"
        target = fixture.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        proof_by_path[path] = proof
    capture = {}
    with fixture.patches()[0], fixture.patches()[1]:
        plan = planning.git_backup_plan(fixture.root, credential_mode="stored", _private_capture=capture)
    fixture.assertTrue(plan["ok"], plan)
    selected, exclusions, proofs = [], [], []
    for row in capture["private_changes"]:
        ref = row["public_observation"]["change_ref"]
        proof = proof_by_path.get(row["path"])
        if proof is not None:
            proof = {**proof, "change_ref": ref}
            proofs.append(proof)
            if proof["original_work_session_binding"]["work_session_ref"] == binding.work_session_ref:
                selected.append(ref)
                continue
        scope = "other_session" if proof is not None else "unknown"
        exclusions.append({"change_ref": ref, "scope": scope, "reason": writer.GIT_BACKUP_EXCLUSION_REASONS[scope]})
    document = {
        "schema": writer.GIT_BACKUP_SELECTION_V2_SCHEMA, "expected_plan_sha256": plan["plan_sha256"],
        "selected_groups": [{"group_id": "group:session-receipts-000001", "change_refs": sorted(selected),
                             "commit_subject": "Back up authenticated session receipts"}],
        "excluded_changes": sorted(exclusions, key=lambda row: row["change_ref"]),
    }
    scope = scope_for_selection(document, binding, sorted(proofs, key=lambda row: row["change_ref"]))
    with fixture.patches()[0], fixture.patches()[1]:
        prepared = writer._prepare_git_backup_from_selection(
            fixture.root, expected_plan_sha256=plan["plan_sha256"],
            selection=writer._GitBackupSelectionV2(writer._canonical(document)),
            credential_mode="stored", work_session_binding=binding, session_scope=scope,
        )
    return prepared, document


def rehash_scope(document):
    document["scope_sha256"] = writer._sha256_json({k: v for k, v in document.items() if k != "scope_sha256"})
    return document


class SessionScopeTests(unittest.TestCase):
    def setUp(self):
        self.binding = selection_fixtures.archive_binding()
        self.selection = selection_fixtures.SelectionPartitionTests().document()
        self.proof = proof_fixture(self.binding)
        self.scope = scope_for_selection(self.selection, self.binding, [self.proof])

    def assert_private(self, error):
        self.assertEqual(str(error), "git_backup_session_scope_invalid")
        self.assertIsNone(error.__context__)
        self.assertIsNone(error.__cause__)
        self.assertNotIn("SYNTHETIC_PRIVATE", repr(error))

    def test_private_immutable_canonical_scope_and_content_free_evidence(self):
        self.proof["context_sha256"] = "sha256:" + "a" * 64
        self.assertEqual(self.scope.document()["producer_proofs"][0]["context_sha256"], "sha256:" + "3" * 64)
        view = self.scope.document()
        view["claim_ref"] = "claim_" + "9" * 32
        self.assertNotEqual(view, self.scope.document())
        with self.assertRaises(FrozenInstanceError):
            self.scope._raw = b"{}"
        self.assertFalse(hasattr(self.scope, "__dict__"))
        self.assertNotIn("claim_", repr(self.scope))
        evidence = self.scope.operation_evidence()
        self.assertEqual(exact.ExactOperationEvidence.from_document(evidence.document()), evidence)
        self.assertEqual(dict(evidence.counts), {"selected_change_count": 1, "excluded_change_count": 2,
                                               "producer_proof_count": 1})
        encoded = json.dumps(evidence.document())
        for marker in ("task_route_", "claim_", "client_app_", "workstream_", "change:000001",
                       "original_work_session_binding", "authenticated_work_session_completion_receipt"):
            self.assertNotIn(marker, encoded)
        self.scope.validate_selection(self.binding, self.selection)

    def test_malformed_rehashed_structure_and_noncanonical_raw_fail_privately(self):
        mutations = (
            lambda d: d.update(extra="SYNTHETIC_PRIVATE"),
            lambda d: d.update(task_route_ref="SYNTHETIC_PRIVATE"),
            lambda d: d.update(actor_sha256="SYNTHETIC_PRIVATE"),
            lambda d: d.update(registry_preimage_sha256=None),
            lambda d: d.update(claim_ref="SYNTHETIC_PRIVATE"),
            lambda d: d.update(selected_change_count=True),
            lambda d: d.update(excluded_change_count=-1),
            lambda d: d.update(producer_proofs=[]),
            lambda d: d["producer_proofs"].append(copy.deepcopy(d["producer_proofs"][0])),
            lambda d: d["producer_proofs"][0].update(producer="SYNTHETIC_PRIVATE"),
            lambda d: d["producer_proofs"][0].update(whole_file_bytes=True),
            lambda d: d["producer_proofs"][0].update(context_sha256="SYNTHETIC_PRIVATE"),
            lambda d: d["producer_proofs"][0].update(path="SYNTHETIC_PRIVATE"),
            lambda d: d["producer_proofs"][0].update(original_work_session_binding=
                selection_fixtures.archive_binding(archive_id="archive:personal:foreign").document()),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(case=index):
                document = self.scope.document()
                mutation(document)
                with self.assertRaises(scopes.GitBackupSessionScopeError) as caught:
                    scopes._GitBackupSessionScope.from_document(rehash_scope(document))
                self.assert_private(caught.exception)
        for raw in (b"{}", b" " + self.scope._raw, bytearray(self.scope._raw),
                    self.scope._raw[:-1] + b',"schema":"SYNTHETIC_PRIVATE"}'):
            with self.assertRaises(scopes.GitBackupSessionScopeError) as caught:
                scopes._GitBackupSessionScope(raw)
            self.assert_private(caught.exception)

    def test_selection_and_session_partition_are_binding_not_claim_attestation(self):
        other = binding_fixture(self.binding.archive_identity_sha256, work_session_ref="work_session_" + "a" * 32)
        changed_selection = copy.deepcopy(self.selection)
        changed_selection["selected_groups"][0]["commit_subject"] = "Other reviewed subject"
        for binding, selection in ((other, self.selection), (self.binding.document(), self.selection),
                                   (self.binding, changed_selection)):
            with self.assertRaises(scopes.GitBackupSessionScopeError):
                self.scope.validate_selection(binding, selection)
        wrong_proof = scope_for_selection(self.selection, self.binding, [proof_fixture(other)])
        with self.assertRaises(scopes.GitBackupSessionScopeError):
            wrong_proof.validate_selection(self.binding, self.selection)
        missing = scope_for_selection(self.selection, self.binding,
                                      [proof_fixture(other, change_ref="change:000002")])
        with self.assertRaises(scopes.GitBackupSessionScopeError):
            missing.validate_selection(self.binding, self.selection)

    def test_large_excluded_selection_keeps_existing_input_budget_separate_from_private_scope(self):
        selection = copy.deepcopy(self.selection)
        selection["excluded_changes"] = [
            {"change_ref": "change:" + str(index).zfill(6), "scope": "unknown", "reason": "ownership_unverified"}
            for index in range(2, 8002)
        ]
        self.assertGreater(len(writer._canonical(selection)), scopes._MAX_BYTES)
        writer._GitBackupSelectionV2(writer._canonical(selection))
        scope = scope_for_selection(selection, self.binding, [self.proof])
        scope.validate_selection(self.binding, selection)
        self.assertLess(len(scope._raw), scopes._MAX_BYTES)

    def test_source_binding_checks_whole_new_receipt_path_head_index_hash_and_bytes(self):
        proof = self.scope.document()["producer_proofs"][0]
        row = {
            "path": "receipts/ops/exact-operations/" + "e" * 64 + ".json", "original_path": None,
            "public_observation": {"change_ref": proof["change_ref"], "operation": "added_untracked",
                "head": {"state": "absent"}, "index": {"state": "absent"},
                "worktree": {"state": "regular_file", "sha256": proof["whole_file_sha256"],
                             "bytes": proof["whole_file_bytes"]}},
        }
        self.scope.validate_sources([row])
        mutations = (
            lambda d: d.update(path="SYNTHETIC_PRIVATE.json"),
            lambda d: d.update(original_path="prior.json"),
            lambda d: d["public_observation"].update(operation="modified"),
            lambda d: d["public_observation"]["head"].update(state="blob"),
            lambda d: d["public_observation"]["worktree"].update(sha256="sha256:" + "a" * 64),
            lambda d: d["public_observation"]["worktree"].update(bytes=1),
            lambda d: d["public_observation"].update(index={"state": "blob", "mode": "regular_file",
                "sha256": "sha256:" + "a" * 64, "bytes": proof["whole_file_bytes"]}),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(case=index):
                changed = copy.deepcopy(row)
                mutate(changed)
                with self.assertRaises(scopes.GitBackupSessionScopeError) as caught:
                    self.scope.validate_sources([changed])
                self.assert_private(caught.exception)


class SessionScopeRealGitTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.GitBackupWriterTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.prepared, self.selection = prepare_scoped_fixture(self.fixture)
        self.root = self.fixture.root

    def test_optional_none_legacy_bytes_and_scoped_exact_manifest_reconstruct(self):
        prepared = self.prepared
        with self.fixture.patches()[0], self.fixture.patches()[1]:
            legacy = writer._prepare_git_backup_from_selection(
                self.root, expected_plan_sha256=prepared.expected_plan_sha256,
                selection=writer._GitBackupSelectionV2(writer._canonical(self.selection)),
                credential_mode="stored", work_session_binding=prepared.manifest.work_session_binding,
                session_scope=None,
            )
        self.assertIsNone(legacy.session_scope)
        self.assertIsNone(legacy.manifest.operation_evidence)
        self.assertNotIn("session_scope", writer._bundle_document(legacy))
        self.assertNotIn("operation_evidence", legacy.manifest.document())
        self.assertEqual(legacy.groups, prepared.groups)
        self.assertEqual(legacy.push_source_payload, prepared.push_source_payload)
        self.assertEqual(legacy.manifest.source_set_sha256, prepared.manifest.source_set_sha256)
        self.assertNotEqual(legacy.manifest.manifest_sha256, prepared.manifest.manifest_sha256)
        stripped = replace(prepared, session_scope=None, manifest=legacy.manifest)
        self.assertEqual(writer._canonical(writer._bundle_document(stripped)),
                         writer._canonical(writer._bundle_document(legacy)))
        decoded = writer._decode_private_git_backup_bundle(
            prepared.root, writer._bundle_document(prepared), manifest_sha256=prepared.manifest.manifest_sha256,
        )
        self.assertEqual(decoded, prepared)
        self.assertEqual(writer._freeze_validated_prepared(prepared), prepared)
        self.assertEqual(prepared.manifest.operation_evidence, prepared.session_scope.operation_evidence())
        public = prepared.public_plan()
        self.assertFalse(public["ready_for_write"])
        self.assertFalse(public["writer_available"])
        self.assertEqual(public["operation_evidence"], prepared.manifest.operation_evidence.document())

    def test_changed_scope_and_rehashed_outer_bundle_cannot_retain_original_manifest(self):
        baseline = writer._bundle_document(self.prepared)
        changes = (
            lambda d: d.update(task_route_ref="task_route_" + "a" * 32),
            lambda d: d.update(actor_sha256="sha256:" + "a" * 64),
            lambda d: d.update(registry_preimage_sha256="sha256:" + "a" * 64),
            lambda d: d.update(claim_ref="claim_" + "a" * 32),
            lambda d: d.update(selection_sha256="sha256:" + "a" * 64),
            lambda d: d["producer_proofs"][0].update(receipt_sha256="sha256:" + "a" * 64),
            lambda d: d["producer_proofs"][0].update(context_sha256="sha256:" + "a" * 64),
            lambda d: d["producer_proofs"][0].update(whole_file_sha256="sha256:" + "a" * 64),
        )
        for index, mutate in enumerate(changes):
            with self.subTest(field=index):
                changed = copy.deepcopy(baseline)
                mutate(changed["session_scope"])
                rehash_scope(changed["session_scope"])
                changed["bundle_sha256"] = writer._sha256_json({k: v for k, v in changed.items() if k != "bundle_sha256"})
                with self.assertRaises(writer.GitBackupWriterError):
                    writer._decode_private_git_backup_bundle(
                        self.root, changed, manifest_sha256=self.prepared.manifest.manifest_sha256,
                    )
                replacement = scopes._GitBackupSessionScope.from_document(changed["session_scope"])
                with self.assertRaises(writer.GitBackupWriterError) as caught:
                    writer._freeze_validated_prepared(replace(self.prepared, session_scope=replacement))
                self.assertEqual(caught.exception.code, "git_backup_manifest_drifted")
                self.assertIsNone(caught.exception.__context__)
                self.assertIsNone(caught.exception.__cause__)
        for key in ("session_scope", "work_session_binding"):
            changed = copy.deepcopy(baseline)
            del changed[key]
            changed["bundle_sha256"] = writer._sha256_json({k: v for k, v in changed.items() if k != "bundle_sha256"})
            with self.assertRaises(writer.GitBackupWriterError):
                writer._decode_private_git_backup_bundle(
                    self.root, changed, manifest_sha256=self.prepared.manifest.manifest_sha256,
                )

    def test_prepare_rejects_scope_binding_selection_and_source_proof_mismatches(self):
        scope = self.prepared.session_scope
        binding = self.prepared.manifest.work_session_binding
        selected = writer._GitBackupSelectionV2(writer._canonical(self.selection))
        other = binding_fixture(binding.archive_identity_sha256, work_session_ref="work_session_" + "a" * 32)
        for invalid_scope, invalid_binding in ((scope.document(), binding), (scope, None), (scope, other)):
            with patch.object(planning, "git_backup_plan") as planner:
                with self.assertRaises(writer.GitBackupWriterError) as caught:
                    writer._prepare_git_backup_from_selection(
                        self.root, expected_plan_sha256=self.prepared.expected_plan_sha256, selection=selected,
                        credential_mode="stored", work_session_binding=invalid_binding, session_scope=invalid_scope,
                    )
                planner.assert_not_called()
                self.assertEqual(caught.exception.code, "git_backup_session_scope_invalid")
                self.assertIsNone(caught.exception.__context__)
        bad_source = scope.document()
        bad_source["producer_proofs"][0]["whole_file_sha256"] = "sha256:" + "a" * 64
        bad_source = scopes._GitBackupSessionScope.from_document(rehash_scope(bad_source))
        with self.fixture.patches()[0], self.fixture.patches()[1]:
            with self.assertRaises(writer.GitBackupWriterError) as caught:
                writer._prepare_git_backup_from_selection(
                    self.root, expected_plan_sha256=self.prepared.expected_plan_sha256, selection=selected,
                    credential_mode="stored", work_session_binding=binding, session_scope=bad_source,
                )
        self.assertEqual(caught.exception.code, "git_backup_session_scope_invalid")

    def test_original_context_wrapper_preserves_scope_without_authenticating_it(self):
        context = writer._git_backup_approval_context(self.prepared, reviewer_claim="person:synthetic-reviewer")
        expected = writer._canonical(writer._bundle_document(self.prepared))
        with exact.ExactOperationWriterLock(self.root) as held, patch.object(
            planning, "git_backup_plan", side_effect=AssertionError("No replan"),
        ), patch.object(approval, "_claim_exact_human_approval_core", side_effect=AssertionError("No claim")):
            saved = bundles._save_original_git_context_held(self.prepared, context=context, held=held)
            loaded = bundles._load_original_git_context_held(
                self.root, held=held, manifest_sha256=self.prepared.manifest.manifest_sha256,
            )
            self.assertEqual(saved._raw, loaded._raw)
            self.assertEqual(writer._canonical(writer._bundle_document(loaded.prepared)), expected)
            self.assertEqual(loaded.context, context)
            self.assertEqual(loaded.prepared.session_scope, self.prepared.session_scope)
            held.verify_held()
        self.assertFalse(self.fixture.transport_commands)

    def test_all_existing_execution_routes_refuse_scope_before_native_key_or_git(self):
        native, key = fixtures._Native(), fixtures._KeyProvider()
        prepared = self.prepared
        context = writer._git_backup_approval_context(prepared, reviewer_claim="person:synthetic-reviewer")
        common = dict(selection_manifest_path=self.fixture.selection_path, reviewer_claim=context.reviewer_claim,
                      native=native, key_provider=key)
        calls = (
            lambda: writer.execute_git_backup(prepared, **common),
            lambda: writer._execute_git_backup_held(prepared, held=object(), **common),
            lambda: writer._execute_git_backup_core(prepared, held=None, progress_hook=None, **common),
            lambda: writer.resume_git_backup(prepared, reviewer_claim=context.reviewer_claim,
                approval_id="approval_" + "a" * 32, key_provider=key),
            lambda: writer._apply_prepared_with_claim(prepared, context=context, claim=object(),
                writer_lock=object(), resume=False, progress_hook=None),
        )
        with patch.object(writer, "_freeze_validated_prepared", side_effect=AssertionError("Read before refusal")), \
             patch.object(writer, "_pinned_git_runtime", side_effect=AssertionError("Git before refusal")):
            for index, call in enumerate(calls):
                with self.subTest(route=index):
                    with self.assertRaises(writer.GitBackupWriterError) as caught:
                        call()
                    self.assertEqual(caught.exception.code, "git_backup_scope_context_required")
                    self.assertIsNone(caught.exception.__context__)
                    self.assertIsNone(caught.exception.__cause__)
        self.assertEqual(native.calls, 0)
        self.assertEqual(key.create_if_missing, [])
        self.assertFalse(self.fixture.transport_commands)
        self.assertFalse((self.root / "profiles").exists())
        self.assertEqual(self.fixture.git(self.root, "rev-parse", "HEAD").stdout.strip(), self.fixture.initial_head)

    def test_malformed_scoped_subclass_and_stripped_scope_cannot_reach_any_legacy_native_route(self):
        class DerivedPrepared(writer.PreparedGitBackup):
            pass
        derived = DerivedPrepared(**vars(self.prepared))
        stripped = replace(self.prepared, session_scope=None)
        native, key = fixtures._Native(), fixtures._KeyProvider()
        context = writer._git_backup_approval_context(self.prepared, reviewer_claim="person:synthetic-reviewer")
        for prepared in (derived, stripped):
            common = dict(selection_manifest_path=self.fixture.selection_path, reviewer_claim=context.reviewer_claim,
                          native=native, key_provider=key)
            calls = (
                lambda: writer.execute_git_backup(prepared, **common),
                lambda: writer._execute_git_backup_held(prepared, held=object(), **common),
                lambda: writer._execute_git_backup_core(prepared, held=None, progress_hook=None, **common),
                lambda: writer.resume_git_backup(prepared, reviewer_claim=context.reviewer_claim,
                    approval_id="approval_" + "a" * 32, key_provider=key),
                lambda: writer._apply_prepared_with_claim(prepared, context=context, claim=object(),
                    writer_lock=object(), resume=False, progress_hook=None),
            )
            with patch.object(writer, "_pinned_git_runtime", side_effect=AssertionError("Git before refusal")):
                for index, call in enumerate(calls):
                    with self.subTest(prepared_type=type(prepared).__name__, route=index):
                        with self.assertRaises(writer.GitBackupWriterError) as caught:
                            call()
                        self.assertEqual(caught.exception.code, "git_backup_manifest_drifted")
                        self.assertIsNone(caught.exception.__context__)
                        self.assertIsNone(caught.exception.__cause__)
        self.assertEqual(native.calls, 0)
        self.assertEqual(key.create_if_missing, [])
        self.assertFalse(self.fixture.transport_commands)
        self.assertFalse((self.root / "profiles").exists())


if __name__ == "__main__":
    unittest.main()
