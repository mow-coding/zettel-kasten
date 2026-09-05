"""Real legacy Git guard against mutable execution views after approval."""

import copy
import unittest

import test_git_backup_writer as fixtures
from wom_kit import git_backup_writer as writer
from wom_kit.exact_human_approval_workflow import ExactHumanApprovalWorkflowError


class GitBackupSourceBindingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.GitBackupWriterTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def test_postapproval_view_change_alone_or_matching_disk_never_commits(self):
        fixture = self.fixture
        for change_disk in (False, True):
            with self.subTest(change_disk=change_disk):
                prepared = fixture.plan_and_prepare()
                original_source = prepared.groups[0].source_payload
                selected = next(row for row in prepared.groups[0].private_changes if row["path"] == "tracked.txt")
                target = fixture.root / "tracked.txt"
                original_bytes = target.read_bytes()
                initial_index = fixture.git(fixture.root, "ls-files", "--stage", "-z").stdout
                changed_bytes = b"Synthetic postapproval changed bytes\n"

                def mutate():
                    if change_disk:
                        target.write_bytes(changed_bytes)
                        with writer._pinned_git_runtime(prepared):
                            rows = writer._GitBackupBackend(prepared)._current_private_changes()
                        replacement = next(row for row in rows if row["path"] == "tracked.txt")
                        selected.clear()
                        selected.update(copy.deepcopy(replacement))
                    else:
                        selected["public_observation"]["worktree"]["sha256"] = "sha256:" + "f" * 64

                native = fixtures._Native(mutate)
                try:
                    with fixture.execution_patches()[0], fixture.execution_patches()[1]:
                        with self.assertRaises(ExactHumanApprovalWorkflowError):
                            writer.execute_git_backup(
                                prepared, selection_manifest_path=fixture.selection_path,
                                reviewer_claim="person:local-operator", native=native,
                                key_provider=fixtures._KeyProvider(),
                            )
                    self.assertEqual(native.calls, 1)
                    self.assertEqual(prepared.groups[0].source_payload, original_source)
                    self.assertEqual(fixture.git(fixture.root, "rev-parse", "HEAD").stdout.strip(), fixture.initial_head)
                    self.assertEqual(fixture.assert_remote_matches_head(), fixture.initial_head)
                    self.assertEqual(fixture.git(fixture.root, "ls-files", "--stage", "-z").stdout, initial_index)
                    self.assertEqual(target.read_bytes(), changed_bytes if change_disk else original_bytes)
                    self.assertFalse(fixture.transport_commands)
                    self.assertFalse((fixture.root / "profiles" / "local" / "exact-human-approvals").exists())
                    self.assertFalse((fixture.root / "receipts").exists())
                finally:
                    target.write_bytes(original_bytes)

    def test_validated_clone_preserves_v1_bytes_without_nested_aliases(self):
        prepared = self.fixture.plan_and_prepare()
        raw = writer._canonical(writer._bundle_document(prepared))
        frozen = writer._freeze_validated_prepared(prepared)
        self.assertEqual(writer._canonical(writer._bundle_document(frozen)), raw)
        self.assertEqual(frozen.manifest.document(), prepared.manifest.document())
        self.assertEqual(frozen.groups[0].commit_message, prepared.groups[0].commit_message)
        nested = prepared.groups[0].private_changes[0]["public_observation"]["worktree"]
        self.assertIsNot(nested, frozen.groups[0].private_changes[0]["public_observation"]["worktree"])
        nested["sha256"] = "sha256:" + "f" * 64
        self.assertEqual(writer._canonical(writer._bundle_document(frozen)), raw)
        self.assertEqual(writer._freeze_validated_prepared(frozen), frozen)
        with self.assertRaisesRegex(writer.GitBackupWriterError, "^git_backup_manifest_drifted$"):
            writer._freeze_validated_prepared(prepared)


if __name__ == "__main__":
    unittest.main()
