"""Bounded adapter tests: supplied snapshots are data, not live Git authority.

The actual test uses two real completed intakes and real Git observations.
Native approval, credential bytes and remote observation are synthetic. Pure
partition tests below deliberately make no completion/authentication assertion.
"""

from contextlib import ExitStack
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_git_backup_writer as git_fixture
import test_v0410_source_intake_batch_exact as intake_fixture
import test_v0420_work_session_source_intake_workflow as session_fixture
from test_v0420_work_session_execution import SessionNative
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import exact_operation_manifest as exact
from wom_kit import git_backup_session_scope as scope_codec
from wom_kit import source_intake_batch_exact as intake
from wom_kit import work_session_actor as actor
from wom_kit import work_session_establishment as establishment
from wom_kit import work_session_execution as execution
from wom_kit import work_session_git_provenance as snapshots
from wom_kit import work_session_intake_git_provenance as subject
from wom_kit import work_session_registry as registry
from wom_kit import work_session_source_intake_bundle as bundle
from wom_kit import work_session_source_intake_completion as completion
from wom_kit import work_session_source_intake_inventory as inventory
from wom_kit import work_session_source_intake_workflow as workflow
from wom_kit.work_session_binding import WorkSessionBinding
from wom_kit.exact_human_approval_windows import ExactHumanApprovalOperation, _ExactHumanApprovalDecision


def _sha(letter):
    return "sha256:" + letter * 64


def _data_row(index, path, digest, size):
    return {"path": path, "original_path": None, "public_observation": {
        "change_ref": "change:" + str(index).zfill(6), "operation": "added_untracked",
        "head": {"state": "absent"}, "index": {"state": "absent"},
        "worktree": {"state": "regular_file", "sha256": digest, "bytes": size}}}


class IntakeGitProvenanceDataTests(unittest.TestCase):
    def test_fixed_errors_hide_private_values_and_chains(self):
        class Hostile(str):
            def __hash__(self):
                raise AssertionError("must not hash a string subclass")
        for value in ([], {}, None, True, "private/path", Hostile("work_session_intake_git_limit")):
            error = subject.WorkSessionIntakeGitProvenanceError(value)
            self.assertEqual(str(error), "work_session_intake_git_invalid")
        def failed():
            raise OSError("private/path secret label")
        with self.assertRaises(subject.WorkSessionIntakeGitProvenanceError) as caught:
            subject._safe_call(failed)
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)
        self.assertNotIn("private", str(caught.exception))

    def test_data_only_or_subclass_view_cannot_be_authenticated_view(self):
        image = object.__new__(completion._SessionSourceIntakeCompletionImage)
        class Subclass(completion._VerifiedSessionSourceIntakeCompletion):
            pass
        for value in (image, object.__new__(Subclass), {}, True):
            with self.assertRaises(subject.WorkSessionIntakeGitProvenanceError):
                subject._origin(value, completion._VerifiedSessionSourceIntakeCompletion)

    def test_whole_new_file_predicate_rejects_index_head_rename_or_mutated_bytes(self):
        output = {"sha256": _sha("a"), "size_bytes": 11}
        original = _data_row(1, "receipts/sources/private.json", _sha("a"), 11)
        self.assertTrue(subject._matches(original, output))
        same_index = json.loads(json.dumps(original))
        same_index["public_observation"]["index"] = {"state": "blob", "mode": "regular_file",
            "sha256": _sha("a"), "bytes": 11}
        self.assertTrue(subject._matches(same_index, output))
        cases = []
        for key, value in (("head", {"state": "blob"}),
                           ("index", {"state": "blob", "mode": "regular_file", "sha256": _sha("b"), "bytes": 11}),
                           ("operation", "modified"),
                           ("worktree", {"state": "regular_file", "sha256": _sha("b"), "bytes": 11})):
            row = json.loads(json.dumps(original))
            row["public_observation"][key] = value
            cases.append(row)
        renamed = json.loads(json.dumps(original))
        renamed["original_path"] = "private/original.json"
        cases.append(renamed)
        for row in cases:
            self.assertFalse(subject._matches(row, output))

    def test_1002_data_rows_form_complete_partition_without_authentication(self):
        # Pure bounded cardinality, not a 1,000-source completed-intake test.
        binding = WorkSessionBinding.build(archive_identity_sha256=_sha("a"),
            client_app_ref="client_app_" + "1" * 32, workstream_ref="workstream_" + "2" * 32,
            work_session_ref="work_session_" + "3" * 32, revision=7,
            client_app_label_sha256=_sha("b"), workstream_label_sha256=_sha("c"))
        rows = [_data_row(index + 1, "receipts/sources/" + str(index) + ".json", _sha("b"), 12)
                for index in range(1003)]
        proofs = [{"change_ref": row["public_observation"]["change_ref"],
                   "original_work_session_binding": binding.document()} for row in rows[:-1]]
        partition = subject._partition(_sha("c"), rows, proofs, binding)
        selected = [ref for group in partition["selected_groups"] for ref in group["change_refs"]]
        excluded = [row["change_ref"] for row in partition["excluded_changes"]]
        self.assertEqual(len(selected), 1002)
        self.assertEqual(sorted(selected + excluded), sorted(row["public_observation"]["change_ref"] for row in rows))
        self.assertEqual(len(set(selected + excluded)), len(rows))
        self.assertEqual(partition["excluded_changes"][0]["scope"], "unknown")

    def test_limits_and_stored_inputs_are_closed_before_any_reader(self):
        with self.assertRaises(subject.WorkSessionIntakeGitProvenanceError):
            subject._canonical(["private"], maximum=1)
        with patch.object(subject, "_completion", side_effect=AssertionError("reader called")) as reader:
            for proof in (None, [], [True], [{}] * 8193):
                with self.assertRaises(subject.WorkSessionIntakeGitProvenanceError):
                    subject._revalidate_intake_output_proofs_held("private", held=None,
                        proofs=proof, private_changes=[])
            reader.assert_not_called()

    def test_excluded_private_input_uses_existing_writer_budget_not_result_budget(self):
        # Scale both ceilings so this exercises admission without a large
        # allocation. Private excluded metadata is not part of the new proof.
        row = _data_row(1, "generic.md", _sha("a"), 11)
        row["private_unselected_metadata"] = "x" * 1024
        canonical = subject._canonical
        def bounded(value, maximum=512):
            return canonical(value, maximum)
        with patch.object(subject.writer, "GIT_BACKUP_MAX_PRIVATE_BUNDLE_BYTES", 4096), \
             patch.object(subject, "_canonical", side_effect=bounded):
            self.assertEqual(subject._rows([row]), [row])
            with self.assertRaises(subject.WorkSessionIntakeGitProvenanceError):
                subject._canonical([row])
            row["private_unselected_metadata"] = "x" * 4096
            with self.assertRaises(subject.WorkSessionIntakeGitProvenanceError):
                subject._rows([row])
            oversized = snapshots._GitChangeSnapshot(b"x" * 4097)
            with self.assertRaises(subject.WorkSessionIntakeGitProvenanceError) as caught:
                subject._snapshot(Path("private"), "archive:personal:fixture", oversized)
            self.assertEqual(caught.exception.code, "work_session_intake_git_limit")

    def test_real_held_archive_absent_and_empty_pending_inventory_are_distinct(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "archive"
            root.mkdir()
            root = root.resolve()
            archive_id = "archive:personal:intake-provenance-fixture"
            (root / "archive.yml").write_text("archive_id: " + archive_id + "\n", encoding="utf-8")
            binding = WorkSessionBinding.build(
                archive_identity_sha256=approval.exact_human_approval_archive_identity_sha256(archive_id),
                client_app_ref="client_app_" + "1" * 32, workstream_ref="workstream_" + "2" * 32,
                work_session_ref="work_session_" + "3" * 32, revision=1,
                client_app_label_sha256=_sha("b"), workstream_label_sha256=_sha("c"))
            row = _data_row(1, "generic-private.md", _sha("b"), 12)
            snapshot = snapshots._GitChangeSnapshot(subject._canonical({"plan_sha256": _sha("d"),
                "capture": {"root": str(root), "archive_id": archive_id,
                    "private_changes": [row], "public_changes": [row["public_observation"]]}}))
            with exact.ExactOperationWriterLock(root) as held, \
                 patch.object(completion, "_read_completed_session_source_intake_held",
                              side_effect=AssertionError("no original to authenticate")) as reader:
                values = dict(held=held, snapshot=snapshot, selected_binding=binding)
                absent = subject._select_intake_output_changes_held(root, **values)
                self.assertEqual(absent.public_summary()["hint_inventory_state"], "absent")
                self.assertEqual(absent.public_summary()["ownership_unverified_count"], 1)
                directory = root.joinpath(*bundle.PRIVATE_ROOT)
                self.assertFalse(directory.exists())
                directory.mkdir(parents=True)
                pending = directory / (".pending_" + "a" * 32)
                pending.write_bytes(b"")
                present = subject._select_intake_output_changes_held(root, **values)
                self.assertEqual(present.public_summary()["hint_inventory_state"], "present")
                self.assertEqual(present.public_summary()["context_hint_count"], 0)
                self.assertFalse(present.public_summary()["artifact_backup_complete"])
                self.assertEqual(pending.read_bytes(), b"")
                reader.assert_not_called()
                with self.assertRaises(subject.WorkSessionIntakeGitProvenanceError):
                    subject._select_intake_output_changes_held(root, **{**values, "held": object()})
                with self.assertRaises(subject.WorkSessionIntakeGitProvenanceError):
                    subject._select_intake_output_changes_held(root.parent, **values)


class IntakeGitProvenanceActualTests(unittest.TestCase):
    def setUp(self):
        self.fixture = git_fixture.GitBackupWriterTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.root = self.fixture.root
        self.git = lambda *args: self.fixture.git(self.root, *args)
        self.git("config", "core.autocrlf", "false")
        self.key = session_fixture._ActiveKey()
        self.native = intake_fixture._Native()
        self.store, _archive = execution._store(self.root)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(self.fixture.patches()[0])
        self.stack.enter_context(self.fixture.patches()[1])
        self.held = self.stack.enter_context(exact.ExactOperationWriterLock(self.root))
        registered = registry.plan_transition(self.store.read(), action="register-app", label="Synthetic private app")
        self.store.commit(registered, held_lock=self.held)
        self.app = registered.result_refs[0]

    def completed(self, label):
        route = actor.new_task_route_ref()
        origin = execution._execute_session_decision_held(self.root, held=self.held, action="create",
            client_app_ref=self.app, task_route_ref=route, label="Synthetic " + label,
            reviewer_claim="person:synthetic", native=SessionNative(), key_provider=self.key)
        session = origin["work_session_binding"]["work_session_ref"]
        claimed = registry.plan_transition(self.store.read(), action="claim", client_app_ref=self.app,
                                           work_session_ref=session)
        self.store.commit(claimed, held_lock=self.held)
        binding = self.store.read().binding(session)
        routing = actor.WorkSessionActorStore(self.store, client_app_ref=self.app, task_route_ref=route)
        routing.save(expected_sha256=None, held_lock=self.held, work_session_ref=session,
            claim_ref=self.store.read()._document["sessions"][session]["claim_ref"], observed_binding=binding,
            established_origin=establishment.EstablishmentSelector.from_document({"action": "create",
                "manifest_sha256": origin["manifest_sha256"],
                "context_sha256": origin["exact_human_approval_reference"]["context_sha256"]}))
        request = self.root.parent / (label + "-request.json")
        sources, items = [], []
        for index in range(2):
            relative = "staging/incoming/" + label + str(index) + ".bin"
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((label + " source bytes " + str(index)).encode("ascii"))
            sources.append(path)
            items.append({"item_id": label + str(index), "local_path": relative, "source_role": "primary_source"})
        request.write_text(json.dumps({"schema": "wom-kit/source-intake-batch-request/v0.1",
            "batch_id": label, "items": items}), encoding="utf-8")
        result = workflow._execute_session_source_intake_batch_held(self.root, request, held=self.held,
            client_app_ref=self.app, task_route_ref=route, work_session_ref=session,
            reviewer_claim="person:synthetic", native=self.native, key_provider=self.key)
        self.assertTrue(result["original_completion_verified"])
        pointer = routing._read(current=False).document()["last_completed_operation"]
        bound = bundle._load_original_source_intake_context_held(self.root,
            manifest_sha256=pointer["manifest_sha256"], held=self.held)
        return result, bound, binding, request, sources

    def evidence(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for top in (self.root / "receipts", self.root / "profiles" / "local")
                for path in top.rglob("*") if path.is_file() and path.name != ".writer.lock"}

    def classify(self, binding, snapshot=None):
        if snapshot is None:
            snapshot = snapshots._capture_git_snapshot_held(self.root, held=self.held)
        selection = subject._select_intake_output_changes_held(self.root, held=self.held,
            snapshot=snapshot, selected_binding=binding, key_provider=self.key)
        return snapshot, selection

    def test_two_originals_cached_common_already_committed_and_all_stored_paths(self):
        a, bound_a, binding, request_a, sources_a = self.completed("owner")
        b, bound_b, _other, request_b, sources_b = self.completed("other")
        final = self.root / exact.EXACT_OPERATION_RECEIPTS_ROOT / (a["execution_sha256"][7:] + ".json")
        self.git("add", "--", final.relative_to(self.root).as_posix())
        self.git("commit", "-m", "synthetic common final baseline")
        self.git("push", str(self.fixture.remote), "HEAD:refs/heads/main")
        # Original binding stays historical after another registry revision.
        for action in ("pause", "resume"):
            claim_ref = (self.store.read()._document["sessions"][binding.work_session_ref]["claim_ref"]
                         if action == "pause" else None)
            later = registry.plan_transition(self.store.read(), action=action,
                client_app_ref=self.app, work_session_ref=binding.work_session_ref, claim_ref=claim_ref)
            self.store.commit(later, held_lock=self.held)
        current = self.store.read().binding(binding.work_session_ref)
        self.assertGreater(current.revision, binding.revision)
        request_a.unlink()
        request_b.unlink()
        for path in sources_a + sources_b:
            path.unlink()
        before = self.evidence()
        before_keys = len(self.key.create_if_missing_calls)
        with patch.object(completion, "_read_completed_session_source_intake_held",
                          wraps=completion._read_completed_session_source_intake_held) as reads, \
             patch.object(broker, "_production_key_provider", side_effect=AssertionError("default key")), \
             patch.object(intake, "plan_source_intake_batch", side_effect=AssertionError("replan")), \
             patch.object(intake, "_stable_source_digest", side_effect=AssertionError("source read")), \
             patch.object(intake._Writer, "write_field", side_effect=AssertionError("writer")), \
             patch.object(approval._ClaimedExactHumanApproval, "exact_terminal_record_mac", side_effect=AssertionError("sign")):
            snapshot, selection = self.classify(current)
        self.assertEqual(reads.call_count, 2)
        self.assertEqual(self.key.create_if_missing_calls[before_keys:], [False, False])
        data, summary = selection._private_document(), selection.public_summary()
        self.assertEqual(summary["selected_output_count"], 3)
        self.assertEqual(summary["other_session_output_count"], 4)
        self.assertEqual(summary["authenticated_original_count"], 2)
        self.assertEqual(summary["unverified_context_hint_count"], 0)
        rows = snapshot._document()["capture"]["private_changes"]
        selected = [ref for group in data["selection"]["selected_groups"] for ref in group["change_refs"]]
        excluded = [row["change_ref"] for row in data["selection"]["excluded_changes"]]
        self.assertEqual(sorted(selected + excluded), sorted(row["public_observation"]["change_ref"] for row in rows))
        self.assertEqual(len(set(selected + excluded)), len(rows))
        self.assertEqual(summary["ownership_unverified_count"], len(rows) - 7)
        self.assertEqual(len(data["proofs"]), 7)
        self.assertTrue(all(proof["original_work_session_binding"] == binding.document()
            for proof in data["proofs"] if proof["execution_sha256"] == a["execution_sha256"]))
        self.assertEqual(self.evidence(), before)
        for marker in (str(self.root), self.app, binding.work_session_ref, "Synthetic owner", "other-request", "new-private.txt"):
            self.assertNotIn(marker, json.dumps(summary) + repr(selection))
        self.assertFalse(summary["git_snapshot_revalidated"] or summary["artifact_backup_complete"])
        values = dict(held=self.held, proofs=data["proofs"], private_changes=rows)
        with patch.object(inventory, "_capture_source_intake_context_inventory_held", side_effect=AssertionError("rediscovery")), \
             patch.object(completion, "_read_session_source_intake_completion_image_held",
                          wraps=completion._read_session_source_intake_completion_image_held) as images:
            original_images = subject._original_intake_output_proof_images_held(self.root, **values)
        self.assertEqual(images.call_count, 2)
        self.assertEqual(len(original_images), 2)
        with patch.object(inventory, "_capture_source_intake_context_inventory_held", side_effect=AssertionError("rediscovery")):
            self.assertEqual(subject._revalidate_intake_output_proofs_held(self.root,
                key_provider=self.key, **values), data["proofs"])
        # A real unrelated started Git claim supplies the same archive key. It
        # does not grant this adapter write authority or invoke another provider.
        context = replace(bound_a.context, operation=ExactHumanApprovalOperation.git_backup,
                          plan_sha256=_sha("c"), target_binding_sha256=_sha("d"))
        decision = _ExactHumanApprovalDecision(approved=True, synthetic_acknowledged=False,
            reason_code="exact_human_approval_approved", plan_sha256=context.plan_sha256,
            target_binding_sha256=context.target_binding_sha256)
        claim = approval._claim_exact_human_approval_core(self.root, context, decision, bytes(range(32)))
        self.addCleanup(claim.close)
        claimed_before = self.evidence()
        with patch.object(self.key, "use_key", side_effect=AssertionError("nested provider")), \
             patch.object(broker, "_production_key_provider", side_effect=AssertionError("nested default provider")), \
             patch.object(inventory, "_capture_source_intake_context_inventory_held", side_effect=AssertionError("rediscovery")), \
             patch.object(completion, "_verify_completed_session_source_intake_with_claim_held",
                          wraps=completion._verify_completed_session_source_intake_with_claim_held) as audits:
            self.assertEqual(subject._revalidate_intake_output_proofs_with_claim_held(self.root,
                claim=claim, **values), data["proofs"])
        self.assertEqual(audits.call_count, 2)
        self.assertEqual(claim.status, "started")
        self.assertEqual(self.evidence(), claimed_before)
        # Stored proof/request images are detached before any key callback.
        original_proofs = json.loads(json.dumps(data["proofs"]))
        def mutate_input(_create):
            data["proofs"][0]["receipt_sha256"] = _sha("f")
        self.key.before_consumer = mutate_input
        self.assertEqual(subject._revalidate_intake_output_proofs_held(self.root,
            key_provider=self.key, **values), original_proofs)
        self.key.before_consumer = None
        with self.assertRaises(subject.WorkSessionIntakeGitProvenanceError):
            subject._original_intake_output_proof_images_held(self.root, **values)
        self.assertEqual(self.evidence(), claimed_before)

    def test_incomplete_hint_and_changed_output_are_unknown_not_absence_or_repair(self):
        result, bound, binding, _request, _sources = self.completed("owner")
        target = self.root / bound.prepared.plan.items[0].receipt_relative_path
        original = target.read_bytes()
        target.write_bytes(original[:-1] + b" ")
        changed = self.evidence()
        snapshot, selection = self.classify(binding)
        summary = selection.public_summary()
        self.assertEqual(summary["selected_output_count"], 0)
        self.assertEqual(summary["authenticated_original_count"], 0)
        self.assertEqual(summary["unverified_context_hint_count"], 1)
        self.assertEqual(summary["hint_inventory_state"], "present")
        self.assertEqual(summary["ownership_unverified_count"], len(snapshot._document()["capture"]["private_changes"]))
        self.assertEqual(self.evidence(), changed)
        # Restore only this synthetic fixture so the separate corrupt-hint phase
        # has one precise cause. Product readers never repair either image.
        target.write_bytes(original)
        context_path = self.root.joinpath(*bundle.PRIVATE_ROOT, bound.prepared.plan.manifest.manifest_sha256[7:] + ".json")
        context_path.write_bytes(b"private corrupt context")
        corrupt = self.evidence()
        _, selection = self.classify(binding)
        self.assertEqual(selection.public_summary()["unverified_context_hint_count"], 1)
        self.assertEqual(selection.public_summary()["selected_output_count"], 0)
        self.assertEqual(self.evidence(), corrupt)


if __name__ == "__main__":
    unittest.main()
