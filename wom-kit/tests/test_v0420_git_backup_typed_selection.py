"""Private selection bytes feed the unchanged exact Git preparation codec."""

from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError
import inspect
import json
import unittest
from unittest.mock import patch

import test_git_backup_writer as fixtures
import test_v0420_git_selection as selection_fixtures
from wom_kit import exact_operation_manifest as exact
from wom_kit import git_backup_plan as planning
from wom_kit import git_backup_writer as writer


class TypedSelectionInputTests(unittest.TestCase):
    def document(self):
        return selection_fixtures.SelectionPartitionTests().document()

    def test_exact_bytes_are_immutable_private_and_not_public_api(self):
        document = self.document()
        document["selected_groups"][0]["commit_subject"] = "SYNTHETIC_PRIVATE_SUBJECT"
        raw = json.dumps(document, indent=2).encode("utf-8")
        selected = writer._GitBackupSelectionV2(raw)
        self.assertEqual(selected.raw_json, raw)
        self.assertEqual(repr(selected), "_GitBackupSelectionV2(<private>)")
        self.assertNotIn("SYNTHETIC_PRIVATE", str(selected))
        self.assertFalse(hasattr(selected, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            selected.raw_json = b"{}"
        self.assertNotIn("_GitBackupSelectionV2", writer.__all__)
        self.assertNotIn("_prepare_git_backup_from_selection", writer.__all__)
        self.assertEqual(
            tuple(inspect.signature(writer.prepare_git_backup).parameters),
            ("archive_root", "expected_plan_sha256", "selection_manifest_path", "remote_name",
             "branch", "credential_mode", "max_changes", "max_changed_bytes", "progress_hook",
             "work_session_binding"),
        )

    def test_bad_bytes_json_v1_and_partition_fail_without_private_exception_chain(self):
        document = self.document()
        raw = writer._canonical(document)
        malformed = [None, raw.decode("ascii"), bytearray(raw), memoryview(raw), b"", b"{}",
                     b"[]", b"\xff", b'{"SYNTHETIC_PRIVATE":',
                     b'{"SYNTHETIC_PRIVATE":1,"SYNTHETIC_PRIVATE":2}']
        mutations = (
            lambda d: d.update(schema=writer.GIT_BACKUP_SELECTION_SCHEMA),
            lambda d: d.update(expected_plan_sha256="SYNTHETIC_PRIVATE"),
            lambda d: d.update(selected_groups="SYNTHETIC_PRIVATE"),
            lambda d: d.update(excluded_changes="SYNTHETIC_PRIVATE"),
            lambda d: d["selected_groups"][0]["change_refs"].append("change:000002"),
            lambda d: d["excluded_changes"][1].update(change_ref="change:000002"),
            lambda d: d["excluded_changes"][0].update(reason="SYNTHETIC_PRIVATE"),
            lambda d: d["selected_groups"][0].update(commit_subject="bad\nSYNTHETIC_PRIVATE"),
        )
        for mutate in mutations:
            changed = copy.deepcopy(document)
            mutate(changed)
            malformed.append(writer._canonical(changed))
        for ordinal, candidate in enumerate(malformed):
            with self.subTest(candidate=ordinal):
                with self.assertRaises(writer.GitBackupWriterError) as caught:
                    writer._GitBackupSelectionV2(candidate)
                self.assertIsNone(caught.exception.__context__)
                self.assertIsNone(caught.exception.__cause__)
                self.assertNotIn("SYNTHETIC_PRIVATE", str(caught.exception))
                self.assertNotIn("SYNTHETIC_PRIVATE", repr(caught.exception))
        with patch.object(writer, "GIT_BACKUP_MAX_SELECTION_BYTES", len(raw) - 1):
            with self.assertRaises(writer.GitBackupWriterError):
                writer._GitBackupSelectionV2(raw)

    def test_wrong_type_or_forged_bytes_fail_before_planner(self):
        valid = writer._GitBackupSelectionV2(writer._canonical(self.document()))
        forged = writer._GitBackupSelectionV2(valid.raw_json)
        object.__setattr__(forged, "raw_json", b'{"SYNTHETIC_PRIVATE":')
        class DerivedSelection(writer._GitBackupSelectionV2):
            pass
        missing = object.__new__(writer._GitBackupSelectionV2)
        for candidate in (None, valid.raw_json, self.document(), forged, missing, DerivedSelection(valid.raw_json)):
            with self.subTest(candidate_type=type(candidate).__name__), patch.object(
                planning, "git_backup_plan",
            ) as planner:
                with self.assertRaises(writer.GitBackupWriterError) as caught:
                    writer._prepare_git_backup_from_selection(
                        "SYNTHETIC_PRIVATE_ARCHIVE", expected_plan_sha256="sha256:" + "a" * 64,
                        selection=candidate, credential_mode="stored",
                    )
                planner.assert_not_called()
                self.assertIsNone(caught.exception.__context__)
                self.assertIsNone(caught.exception.__cause__)


class TypedSelectionRealGitTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.GitBackupWriterTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.root = self.fixture.root

    def plan_document(self, *, select_all=False):
        capture = {}
        with self.fixture.patches()[0], self.fixture.patches()[1]:
            plan = planning.git_backup_plan(self.root, credential_mode="stored", _private_capture=capture)
        self.assertTrue(plan["ok"], plan)
        selected, excluded = [], []
        for row in capture["private_changes"]:
            reference = row["public_observation"]["change_ref"]
            if select_all or row["path"] == "tracked.txt":
                selected.append(reference)
            else:
                excluded.append({"change_ref": reference, "scope": "other_session",
                                 "reason": "other_session_change"})
        return {
            "schema": writer.GIT_BACKUP_SELECTION_V2_SCHEMA,
            "expected_plan_sha256": plan["plan_sha256"],
            "selected_groups": [{"group_id": "group:reviewed", "change_refs": sorted(selected),
                                 "commit_subject": "Back up reviewed work"}],
            "excluded_changes": excluded,
        }

    def prepare(self, document, *, selection=None, **options):
        if selection is None:
            selection = writer._GitBackupSelectionV2(writer._canonical(document))
        with self.fixture.patches()[0], self.fixture.patches()[1]:
            return writer._prepare_git_backup_from_selection(
                self.root, expected_plan_sha256=document["expected_plan_sha256"],
                selection=selection, credential_mode="stored", **options,
            )

    def test_typed_and_path_preparations_have_identical_exact_bundle_and_context_bytes(self):
        for select_all, binding in ((False, selection_fixtures.archive_binding(revision=7)), (True, None)):
            with self.subTest(select_all=select_all):
                document = self.plan_document(select_all=select_all)
                raw = json.dumps(document, indent=2, sort_keys=False).encode("utf-8")
                self.fixture.selection_path.write_bytes(raw)
                with self.fixture.patches()[0], self.fixture.patches()[1]:
                    from_path = writer.prepare_git_backup(
                        self.root, expected_plan_sha256=document["expected_plan_sha256"],
                        selection_manifest_path=self.fixture.selection_path, credential_mode="stored",
                        work_session_binding=binding,
                    )
                from_memory = self.prepare(document, selection=writer._GitBackupSelectionV2(raw),
                                           work_session_binding=binding)
                self.assertEqual(writer._canonical(writer._bundle_document(from_memory)),
                                 writer._canonical(writer._bundle_document(from_path)))
                self.assertEqual(from_memory.manifest.document(), from_path.manifest.document())
                self.assertEqual(from_memory.selection_sha256, writer._sha256_json(document))
                self.assertEqual(from_memory.public_plan(), from_path.public_plan())
                self.assertEqual(writer._freeze_validated_prepared(from_memory), from_memory)
                self.assertEqual(
                    writer._git_backup_approval_context(from_memory, reviewer_claim="person:local-operator"),
                    writer._git_backup_approval_context(from_path, reviewer_claim="person:local-operator"),
                )

    def test_no_selection_file_or_ignored_inventory_change_and_input_detaches_before_planning(self):
        document = self.plan_document()
        raw = writer._canonical(document)
        selected = writer._GitBackupSelectionV2(raw)
        before = self.fixture.git(self.root, "status", "--porcelain=v1", "--ignored", "-z").stdout
        original = planning.git_backup_plan

        def plan_then_mutate(*args, **kwargs):
            result = original(*args, **kwargs)
            object.__setattr__(selected, "raw_json", b"{}")
            return result

        with patch.object(planning, "git_backup_plan", side_effect=plan_then_mutate) as planner, patch.object(
            writer, "_read_stable_plain_file", side_effect=AssertionError("No selection file may be read"),
        ):
            prepared = self.prepare(document, selection=selected)
        self.assertEqual(planner.call_count, 1)
        self.assertEqual(prepared.selection_sha256, writer._sha256_json(document))
        self.assertFalse(self.fixture.selection_path.exists())
        self.assertFalse((self.root / "profiles").exists())
        self.assertEqual(self.fixture.git(self.root, "status", "--porcelain=v1", "--ignored", "-z").stdout,
                         before)
        self.assertEqual(self.plan_document()["expected_plan_sha256"], document["expected_plan_sha256"])

    def test_source_drift_still_rejects_the_original_plan(self):
        document = self.plan_document()
        # Same length as the fixture's original changed bytes.
        (self.root / "tracked.txt").write_bytes(b"other\n")
        with self.assertRaises(writer.GitBackupWriterError) as caught:
            self.prepare(document)
        self.assertEqual(caught.exception.code, "git_backup_selection_plan_mismatch")
        self.assertFalse(self.fixture.transport_commands)

    def test_real_remote_ref_drift_still_rejects_the_original_plan(self):
        document = self.plan_document()
        tree = self.fixture.git(self.root, "rev-parse", "HEAD^{tree}").stdout.strip()
        advanced = self.fixture.git(self.root, "commit-tree", tree, "-p", self.fixture.initial_head,
                                    "-m", "Synthetic remote advance").stdout.strip()
        self.fixture.git(self.root, "push", str(self.fixture.remote), advanced + ":refs/heads/main")
        with self.assertRaises(writer.GitBackupWriterError) as caught:
            self.prepare(document)
        self.assertIn(caught.exception.code, {"git_backup_exact_plan_blocked", "git_backup_selection_plan_mismatch",
                                              "git_backup_repository_relation_unsafe"})
        self.assertEqual(self.fixture.git(self.root, "rev-parse", "HEAD").stdout.strip(), self.fixture.initial_head)
        self.assertFalse(self.fixture.transport_commands)

    def test_declared_partition_is_checked_again_against_the_real_plan(self):
        original = self.plan_document()
        for label in ("missing", "unknown"):
            document = copy.deepcopy(original)
            if label == "missing":
                document["excluded_changes"] = []
            else:
                document["excluded_changes"][0]["change_ref"] = "change:999999"
            # Structurally valid input is not evidence that these refs exist.
            selected = writer._GitBackupSelectionV2(writer._canonical(document))
            with self.subTest(partition=label):
                with self.assertRaises(writer.GitBackupWriterError) as caught:
                    self.prepare(document, selection=selected)
                self.assertEqual(caught.exception.code, "git_backup_selection_incomplete")

    def test_typed_prepared_bundle_remains_compatible_with_existing_held_execution(self):
        document = self.plan_document()
        binding = selection_fixtures.archive_binding(revision=9)
        prepared = self.prepare(document, work_session_binding=binding)
        # The existing executor still takes its original private file argument.
        # This fixture lives outside the archive; no new execution route is implied.
        self.fixture.selection_path.write_bytes(writer._canonical(document))
        excluded_before = (self.root / "new-private.txt").read_bytes()
        with exact.ExactOperationWriterLock(self.root) as held, self.fixture.patches()[2], self.fixture.patches()[3]:
            native = fixtures._Native(held.verify_held)
            with patch.object(writer, "exact_operation_writer_lock",
                              side_effect=AssertionError("No nested archive lock")):
                result = writer._execute_git_backup_held(
                    prepared, held=held, selection_manifest_path=self.fixture.selection_path,
                    reviewer_claim="person:local-operator", native=native, key_provider=fixtures._KeyProvider(),
                )
            held.verify_held()
        self.assertTrue(result["ok"])
        self.assertEqual(native.calls, 1)
        self.assertEqual(result["work_session_binding"], binding.document())
        self.assertEqual((self.root / "new-private.txt").read_bytes(), excluded_before)
        terminal = self.fixture.assert_remote_matches_head()
        self.assertEqual(self.fixture.git(self.root, "diff", "--name-only", self.fixture.initial_head, terminal)
                         .stdout.splitlines(), ["tracked.txt"])
        self.assertEqual(len(self.fixture.transport_commands), 1)


if __name__ == "__main__":
    unittest.main()
