"""Whole-document Git ownership for completed session title recoveries.

The actual tests use a real Git repository over the synthetic archive, a
local bare remote, the real session lifecycle, a real approved title
recovery and the real session Git backup. Native approval and the key are
synthetic. Ownership requires all of: HEAD holds the approved preimage, the
worktree the approved postimage, the index equals one of them, the original
recovery authenticates, and the current bytes still match the postimage.
"""

from contextlib import ExitStack
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import test_git_backup_writer as git_fixture
import test_local_recovery_execution as recovery_fixture
from test_v0420_work_session_execution import SessionNative
from test_v0420_work_session_git_provenance import _ReadGuardKey
from wom_kit import archive_services
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import exact_operation_manifest as exact
from wom_kit import git_backup_session_scope as scope_codec
from wom_kit import local_recovery_completion as completion
from wom_kit import local_recovery_execution as recovery
from wom_kit import local_recovery_session as sessions
from wom_kit import work_session_actor as actor
from wom_kit import work_session_establishment as establishment
from wom_kit import work_session_execution as execution
from wom_kit import work_session_git_provenance as snapshots
from wom_kit import work_session_git_workflow as git_workflow
from wom_kit import work_session_local_recovery_git_provenance as subject
from wom_kit import work_session_registry as registry
from wom_kit.work_session_binding import WorkSessionBinding


ZETTEL_RELATIVE = "zettels/" + recovery_fixture.ZETTEL_ID + ".md"


def _sha(letter):
    return "sha256:" + letter * 64


def _row(index, path, *, head, index_entry, worktree, operation="modified", original_path=None):
    def entry(value):
        if value is None:
            return {"state": "absent", "mode": None, "bytes": None, "sha256": None}
        return {"state": "blob", "mode": "regular_file", "bytes": value[1], "sha256": value[0]}
    return {"path": path, "original_path": original_path, "public_observation": {
        "change_ref": "change:" + str(index).zfill(6), "operation": operation,
        "head": entry(head), "index": entry(index_entry),
        "worktree": {"state": "regular_file", "sha256": worktree[0], "bytes": worktree[1]}}}


def title_plan(root, after):
    """The fixture title plan with a chosen post value."""
    archive_id = archive_services.read_archive_id(root)
    path = root.joinpath(*ZETTEL_RELATIVE.split("/"))
    frontmatter, _body = archive_services.require_readable_zettel_content(path)
    before = frontmatter["title"].encode("utf-8")
    identity = recovery.local_recovery_zettel_identity_sha256(archive_id, recovery_fixture.ZETTEL_ID, ZETTEL_RELATIVE)
    source = b'{"source":"synthetic"}'
    item = exact.ExactOperationItem(ordinal=0, item_id="item:000000", target_kind="zettel", target_ref=identity,
        target_identity_sha256=identity, fields=(exact.ExactFieldEffect(field_ref="frontmatter.title",
            pre_sha256=exact.hash_field_value(before), post_sha256=exact.hash_field_value(after),
            source_sha256=exact.hash_field_value(source)),))
    manifest = exact.ExactOperationManifest.build(operation=recovery.APPLY_OPERATION,
        archive_identity_sha256=approval.exact_human_approval_archive_identity_sha256(archive_id), items=(item,))
    spec = recovery.LocalRecoveryFieldSpec(item_id=item.item_id, target_kind="zettel", target_ref=identity,
        target_identity_sha256=identity, field_ref="frontmatter.title", target_relative=ZETTEL_RELATIVE,
        zettel_id=recovery_fixture.ZETTEL_ID, pre_value=before, post_value=after, source_value=source)
    return recovery.build_local_recovery_plan(root, domain="synthetic_title", manifest=manifest, specs=(spec,))


class DocumentGitProvenanceDataTests(unittest.TestCase):
    def test_modified_document_predicate_needs_head_preimage_worktree_postimage_and_index_on_one_side(self):
        output = {"output_kind": "canonical_zettel_document", "output_identity_sha256": _sha("1"),
                  "head_sha256": _sha("a"), "head_bytes": 10, "sha256": _sha("b"), "size_bytes": 12}
        unstaged = _row(1, "zettels/private.md", head=(_sha("a"), 10), index_entry=(_sha("a"), 10), worktree=(_sha("b"), 12))
        staged = _row(1, "zettels/private.md", head=(_sha("a"), 10), index_entry=(_sha("b"), 12), worktree=(_sha("b"), 12))
        self.assertTrue(subject._matches(unstaged, output))
        self.assertTrue(subject._matches(staged, output))
        for changed in (
            _row(1, "z.md", head=(_sha("a"), 10), index_entry=(_sha("c"), 3), worktree=(_sha("b"), 12)),  # index neither
            _row(1, "z.md", head=(_sha("c"), 10), index_entry=(_sha("c"), 10), worktree=(_sha("b"), 12)),  # head differs
            _row(1, "z.md", head=(_sha("a"), 10), index_entry=(_sha("a"), 10), worktree=(_sha("b"), 13)),  # size differs
            _row(1, "z.md", head=None, index_entry=None, worktree=(_sha("b"), 12), operation="added_untracked"),
            _row(1, "z.md", head=(_sha("a"), 10), index_entry=(_sha("a"), 10), worktree=(_sha("b"), 12), operation="renamed", original_path="old.md"),
        ):
            self.assertFalse(subject._matches(changed, output))
        receipt = {"output_kind": "common_completion_receipt", "output_identity_sha256": _sha("e"),
                   "head_sha256": None, "head_bytes": None, "sha256": _sha("d"), "size_bytes": 7}
        self.assertTrue(subject._matches(_row(2, "receipts/ops/exact-operations/x.json", head=None, index_entry=None,
                                              worktree=(_sha("d"), 7), operation="added_untracked"), receipt))
        self.assertFalse(subject._matches(unstaged, receipt))

    def test_scope_codec_v3_binds_document_proofs_and_keeps_v2_bytes(self):
        binding = WorkSessionBinding.build(archive_identity_sha256=_sha("a"), client_app_ref="client_app_" + "1" * 32,
            workstream_ref="workstream_" + "2" * 32, work_session_ref="work_session_" + "3" * 32, revision=1,
            client_app_label_sha256=_sha("b"), workstream_label_sha256=_sha("c"))
        facts = {"manifest_sha256": _sha("1"), "context_sha256": _sha("2"), "execution_sha256": _sha("3"),
                 "common_final_receipt_sha256": _sha("4"), "recovery_scope_sha256": _sha("5"),
                 "work_session_binding": binding.document()}
        document = subject._proof(facts, {"output_kind": "canonical_zettel_document", "output_identity_sha256": _sha("6"),
            "head_sha256": _sha("7"), "head_bytes": 10, "sha256": _sha("8"), "size_bytes": 11}, "zettels/private.md", "change:000001")
        receipt = subject._proof(facts, {"output_kind": "common_completion_receipt", "output_identity_sha256": _sha("3"),
            "head_sha256": None, "head_bytes": None, "sha256": _sha("9"), "size_bytes": 5},
            "receipts/ops/exact-operations/" + "3" * 64 + ".json", "change:000002")
        built = scope_codec._GitBackupSessionScope.build(task_route_ref="task_route_" + "4" * 32, actor_sha256=_sha("a"),
            registry_preimage_sha256=_sha("b"), claim_ref="claim_" + "5" * 32, work_session_binding=binding,
            selection_sha256=_sha("c"), selected_change_count=2, excluded_change_count=0,
            producer_proofs=[document, receipt])
        self.assertEqual(built.document()["schema"], scope_codec._SCHEMA_V3)
        self.assertEqual(built.operation_evidence().schema, scope_codec._EVIDENCE_SCHEMA_V3)
        self.assertNotIn("private.md", json.dumps(built.document()))
        for broken in (
            {**document, "head_file_sha256": None},
            {**receipt, "head_file_sha256": _sha("7"), "head_file_bytes": 10},
            {**receipt, "output_identity_sha256": _sha("f")},
            {**document, "output_kind": "prepared_capture_request"},
        ):
            with self.assertRaises(scope_codec.GitBackupSessionScopeError):
                scope_codec._GitBackupSessionScope.build(task_route_ref="task_route_" + "4" * 32, actor_sha256=_sha("a"),
                    registry_preimage_sha256=_sha("b"), claim_ref="claim_" + "5" * 32, work_session_binding=binding,
                    selection_sha256=_sha("c"), selected_change_count=1, excluded_change_count=0, producer_proofs=[broken])
        rows = [_row(1, "zettels/private.md", head=(_sha("7"), 10), index_entry=(_sha("7"), 10), worktree=(_sha("8"), 11)),
                _row(2, "receipts/ops/exact-operations/" + "3" * 64 + ".json", head=None, index_entry=None,
                     worktree=(_sha("9"), 5), operation="added_untracked")]
        built.validate_sources(rows)
        rows[0]["public_observation"]["index"] = {"state": "blob", "mode": "regular_file", "bytes": 3, "sha256": _sha("d")}
        with self.assertRaises(scope_codec.GitBackupSessionScopeError):
            built.validate_sources(rows)
        rows[0]["public_observation"]["index"] = {"state": "blob", "mode": "regular_file", "bytes": 10, "sha256": _sha("7")}
        rows[0]["path"] = "zettels/other.md"  # the path digest is bound, not derivable from digests
        with self.assertRaises(scope_codec.GitBackupSessionScopeError):
            built.validate_sources(rows)
        # A v2 intake scope is untouched by the new level.
        self.assertEqual(scope_codec._LEVELS[scope_codec._SCHEMA_V2], 2)

    def test_fixed_errors_and_stored_inputs_are_closed_before_any_reader(self):
        for value in ([], {}, None, "private/path"):
            self.assertEqual(str(subject.WorkSessionDocumentGitProvenanceError(value)), "work_session_document_git_invalid")
        with patch.object(subject, "_reader_api", side_effect=AssertionError("reader called")):
            for proofs in (None, [], [True], [{}] * 8193):
                with self.assertRaises(subject.WorkSessionDocumentGitProvenanceError):
                    subject._revalidate_document_proofs_held("private", held=None, proofs=proofs, private_changes=[])


class DocumentGitProvenanceActualTests(unittest.TestCase):
    def setUp(self):
        if shutil.which("git") is None:
            self.skipTest("git is required")
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        parent = Path(self.temporary.name)
        self.root = parent / "archive"
        shutil.copytree(recovery_fixture.FIXTURE, self.root)
        self.root = self.root.resolve()
        self.remote = parent / "remote.git"
        subprocess.run(["git", "init", "--bare", str(self.remote)], check=True, capture_output=True, text=True)
        self.fixture = git_fixture.GitBackupWriterTests("runTest")
        self.fixture.root, self.fixture.remote, self.fixture.transport_commands = self.root, self.remote, []
        self.git = lambda *args, **kwargs: self.fixture.git(self.root, *args, **kwargs)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "document-test")
        self.git("config", "user.email", "document-test@example.invalid")
        self.git("config", "core.autocrlf", "false")
        self.git("add", "-A")
        self.git("commit", "-m", "synthetic archive baseline")
        self.git("remote", "add", "origin", "https://example.invalid/private/repository.git")
        self.git("push", str(self.remote), "HEAD:refs/heads/main")
        self.baseline = self.git("rev-parse", "HEAD").stdout.strip()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for item in self.fixture.patches():
            self.stack.enter_context(item)
        self.key = _ReadGuardKey()
        self.stack.enter_context(patch.object(broker, "_production_key_provider", return_value=self.key))
        self.store, _archive = execution._store(self.root)
        self.route = actor.new_task_route_ref()
        with exact.ExactOperationWriterLock(self.root) as held:
            registered = registry.plan_transition(self.store.read(), action="register-app", label="Synthetic app")
            self.store.commit(registered, held_lock=held)
            self.app = registered.result_refs[0]
            self.original = execution._execute_session_decision_held(self.root, held=held, action="create",
                client_app_ref=self.app, task_route_ref=self.route, label="Synthetic task",
                reviewer_claim="person:fixture", native=SessionNative(), key_provider=self.key)
            self.session = self.original["work_session_binding"]["work_session_ref"]
            claimed = registry.plan_transition(self.store.read(), action="claim", client_app_ref=self.app,
                                               work_session_ref=self.session)
            self.store.commit(claimed, held_lock=held)
            self.binding = self.store.read().binding(self.session)
            self.claim_ref = self.store.read()._document["sessions"][self.session]["claim_ref"]
            self.routing = actor.WorkSessionActorStore(self.store, client_app_ref=self.app, task_route_ref=self.route)
            origin = establishment.EstablishmentSelector.from_document({"action": "create",
                "manifest_sha256": self.original["manifest_sha256"],
                "context_sha256": self.original["exact_human_approval_reference"]["context_sha256"]})
            self.routing.save(expected_sha256=None, held_lock=held, work_session_ref=self.session,
                claim_ref=self.claim_ref, observed_binding=self.binding, established_origin=origin)
        archive_services.index_archive(self.root)
        self.zettel = self.root / ZETTEL_RELATIVE
        self.establishment_receipt = "receipts/ops/exact-operations/" + self.original["execution_sha256"][7:] + ".json"

    def recover(self, held, after=b"Recovered exact title"):
        result = sessions._execute_session_local_recovery_held(self.root, lambda: title_plan(self.root, after),
            held=held, client_app_ref=self.app, task_route_ref=self.route, work_session_ref=self.session,
            reviewer_claim="person:synthetic-recovery-reviewer", native=git_fixture._Native(), key_provider=self.key)
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["whole_document_transition_verified"])
        self.assertFalse(result["whole_document_ownership_verified"])
        return "receipts/ops/exact-operations/" + result["execution_sha256"][7:] + ".json"

    def preview(self, held):
        return git_workflow._preview_session_git_backup_held(self.root, held=held, client_app_ref=self.app,
            task_route_ref=self.route, work_session_ref=self.session, key_provider=self.key)

    def show_bytes(self, spec):
        return subprocess.run(["git", "-C", str(self.root), "show", spec], check=True, capture_output=True).stdout

    def committed_paths(self):
        return sorted(line for line in self.git("show", "--format=", "--name-only", "HEAD").stdout.splitlines() if line)

    def test_completed_title_recovery_document_is_owned_committed_and_pushed_once(self):
        pre = self.zettel.read_bytes()
        with exact.ExactOperationWriterLock(self.root) as held:
            recovery_receipt = self.recover(held)
            post = self.zettel.read_bytes()
            self.assertNotEqual(post, pre)
            preview = self.preview(held)
            self.assertEqual(preview["selected_document_count"], 1)
            self.assertEqual(preview["selected_output_count"], 3)  # zettel + recovery receipt + establishment receipt
            self.assertTrue(preview["document_provenance_evaluated"])
            self.assertFalse(preview["whole_document_ownership_verified"])
            self.assertEqual(preview["authenticated_recovery_count"], 1)
            self.assertEqual(preview["unverified_document_control_count"], 0)
            self.assertFalse(preview["backup_performed"])
            self.assertNotIn(ZETTEL_RELATIVE, json.dumps(preview))
            result = git_workflow._execute_session_git_backup_held(self.root, held=held, client_app_ref=self.app,
                task_route_ref=self.route, work_session_ref=self.session, reviewer_claim="person:git-reviewer",
                native=git_fixture._Native(), key_provider=self.key)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["status"], "session_documents_backed_up")
            self.assertTrue(result["whole_document_ownership_verified"])
            self.assertTrue(result["document_provenance_evaluated"])
            self.assertEqual(result["selected_document_count"], 1)
            self.assertEqual(result["selected_receipt_count"], 2)
            self.assertTrue(result["original_commit_verified"])
            self.assertEqual(self.committed_paths(), sorted([ZETTEL_RELATIVE, recovery_receipt, self.establishment_receipt]))
            head = self.git("rev-parse", "HEAD").stdout.strip()
            self.assertNotEqual(head, self.baseline)
            self.assertEqual(self.show_bytes("HEAD:" + ZETTEL_RELATIVE), post)
            self.assertEqual(self.show_bytes(self.baseline + ":" + ZETTEL_RELATIVE), pre)
            self.assertEqual(self.fixture.remote_observer(self.root, "origin", "refs/heads/main"), ("present", head))
            self.assertEqual(self.zettel.read_bytes(), post)
            # Completed replay reauthenticates the document proof without a second commit.
            with patch.object(git_workflow.writer, "_run_git_backup_exact_operation", side_effect=AssertionError("writer reentered")):
                resumed = git_workflow._resume_session_git_backup_held(self.root, held=held, client_app_ref=self.app,
                    task_route_ref=self.route, key_provider=self.key)
            self.assertTrue(resumed["original_operation_already_completed"])
            self.assertTrue(resumed["whole_document_ownership_verified"])
            self.assertEqual(self.git("rev-parse", "HEAD").stdout.strip(), head)
            self.assertEqual(self.git("rev-list", "--count", "HEAD").stdout.strip(), "2")

    def test_later_body_edit_or_foreign_index_leaves_document_unverified_and_uncommitted(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            recovery_receipt = self.recover(held)
            post = self.zettel.read_bytes()
            # Index holds bytes that are neither the preimage nor the postimage.
            self.zettel.write_bytes(post + b"\nSynthetic staged experiment.\n")
            self.git("add", "--", ZETTEL_RELATIVE)
            self.zettel.write_bytes(post)
            preview = self.preview(held)
            self.assertEqual(preview["authenticated_recovery_count"], 1)
            self.assertEqual(preview["selected_document_count"], 0)
            self.assertEqual(preview["unverified_document_control_count"], 0)
            self.git("reset", "-q", "--", ZETTEL_RELATIVE)
            # A later unrelated body edit: the recovery no longer matches its
            # approved postimage, so the whole document stays unverified and
            # the recovery's own receipt is not claimed by this producer.
            self.zettel.write_bytes(post + b"\nSynthetic later body edit.\n")
            preview = self.preview(held)
            self.assertEqual(preview["selected_document_count"], 0)
            self.assertEqual(preview["unverified_document_control_count"], 1)
            self.assertEqual(preview["authenticated_recovery_count"], 0)
            self.assertEqual(preview["selected_receipt_count"], 1)
            result = git_workflow._execute_session_git_backup_held(self.root, held=held, client_app_ref=self.app,
                task_route_ref=self.route, work_session_ref=self.session, reviewer_claim="person:git-reviewer",
                native=git_fixture._Native(), key_provider=self.key)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["status"], "session_receipts_backed_up")
            self.assertFalse(result.get("whole_document_ownership_verified", False))
            self.assertEqual(self.committed_paths(), [self.establishment_receipt])
            self.assertNotEqual(self.git("ls-files", "--error-unmatch", "--", recovery_receipt, check=False).returncode, 0)
            self.assertEqual(self.zettel.read_bytes(), post + b"\nSynthetic later body edit.\n")

    def test_second_recovery_on_one_document_supersedes_the_first_without_chain_evidence(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            first = self.recover(held, after=b"Recovered exact title")
            second = self.recover(held, after=b"Recovered exact title again")
            preview = self.preview(held)
            # The first recovery's approved postimage no longer matches the
            # file, so it is unverified; the second matches the file but HEAD
            # still holds the original preimage, not its own preimage. Without
            # consecutive chain evidence the document stays unverified.
            self.assertEqual(preview["authenticated_recovery_count"], 1)
            self.assertEqual(preview["unverified_document_control_count"], 1)
            self.assertEqual(preview["overlapping_document_count"], 0)
            self.assertEqual(preview["selected_document_count"], 0)
            self.assertEqual(preview["selected_receipt_count"], 2)  # second recovery + establishment
            result = git_workflow._execute_session_git_backup_held(self.root, held=held, client_app_ref=self.app,
                task_route_ref=self.route, work_session_ref=self.session, reviewer_claim="person:git-reviewer",
                native=git_fixture._Native(), key_provider=self.key)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["status"], "session_outputs_backed_up")
            self.assertEqual(self.committed_paths(), sorted([second, self.establishment_receipt]))
            self.assertNotEqual(self.git("ls-files", "--error-unmatch", "--", first, check=False).returncode, 0)
            self.assertEqual(self.show_bytes("HEAD:" + ZETTEL_RELATIVE), self.show_bytes(self.baseline + ":" + ZETTEL_RELATIVE))

    def test_readers_agree_and_reject_a_changed_control_without_repair(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            self.recover(held)
            snapshot = snapshots._capture_git_snapshot_held(self.root, held=held)
            selection = subject._select_document_changes_held(self.root, held=held, snapshot=snapshot,
                selected_binding=self.binding, key_provider=self.key)
            data = selection._private_document()
            self.assertEqual(len(data["proofs"]), 2)
            rows = snapshot._document()["capture"]["private_changes"]
            values = dict(held=held, proofs=data["proofs"], private_changes=rows)
            self.assertEqual(subject._revalidate_document_proofs_held(self.root, key_provider=self.key, **values), data["proofs"])
            images = subject._original_document_proof_images_held(self.root, **values)
            self.assertEqual(len(images), 1)
            manifest_sha = data["proofs"][0]["manifest_sha256"]
            control = self.root / recovery._control_relative(manifest_sha)
            before = control.read_bytes()
            control.write_bytes(before + b" ")
            with self.assertRaises(subject.WorkSessionDocumentGitProvenanceError):
                subject._original_document_proof_images_held(self.root, **values)
            self.assertEqual(control.read_bytes(), before + b" ")
            control.write_bytes(before)
            self.assertEqual(subject._original_document_proof_images_held(self.root, **values), images)


if __name__ == "__main__":
    unittest.main()
