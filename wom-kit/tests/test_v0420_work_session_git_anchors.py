"""Immutable real Git proofs do not depend on the later HEAD or dirty tree."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import test_git_backup_writer as fixtures
from wom_kit import exact_operation_manifest as exact
from wom_kit import git_backup_plan as planning
from wom_kit import git_backup_writer as writer
from wom_kit import work_session_git_anchors as anchors


class OriginalGitAnchorTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.GitBackupWriterTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.prepared = self.fixture.plan_and_prepare(group_count=2)
        self.oids = []
        # Create genuine ordered commits with the original exact messages and
        # file selection. This is fixture setup, not the read-only observer.
        with writer._pinned_git_runtime(self.prepared):
            backend = writer._GitBackupBackend(self.prepared)
            for group in self.prepared.groups:
                self.fixture.git(self.fixture.root, "-c", "core.autocrlf=false",
                                 "-c", "core.safecrlf=false", "add", "--", *group.paths)
                committed = backend._git_raw(
                    ["commit", "--no-verify", "--cleanup=verbatim", "--file", "-"],
                    input_bytes=group.commit_message,
                )
                self.assertIsNotNone(committed)
                self.assertEqual(committed[0], 0)
                self.oids.append(backend._head())
        self.oids = tuple(self.oids)
        self.fixture.git(self.fixture.root, "push", str(self.fixture.remote),
                         self.oids[-1] + ":refs/heads/main")

    def observe(self, *, oids=None, remote=None):
        if oids is None:
            oids = self.oids
        callback = remote or (lambda prepared: self.fixture.remote_observer(
            prepared.root, prepared.remote_name, prepared.target_ref,
        ))
        with exact.ExactOperationWriterLock(self.prepared.root) as held, patch.object(
            writer, "_query_exact_remote_ref_with_stored_credentials", side_effect=callback,
        ), patch.object(planning, "git_backup_plan", side_effect=AssertionError("No replanning")), patch.object(
            writer._GitBackupBackend, "_refresh", side_effect=AssertionError("No dirty-tree refresh"),
        ):
            return anchors._observe_original_git_anchors_held(
                self.prepared, held=held, commit_oids=oids,
            )

    def test_exact_objects_remote_and_later_unrelated_work_remain_separate(self):
        first = self.observe().document()
        self.assertEqual(first["status"], "verified")
        self.assertEqual(first["current_head_relation"], "terminal")
        self.assertTrue(first["commit_anchors_verified"])
        self.assertTrue(first["remote_ref_independently_verified"])
        self.assertFalse(first["approval_authenticated"])
        self.assertFalse(first["backup_completion_verified"])
        self.assertFalse(first["git_mutation_performed"])
        (self.fixture.root / "later.txt").write_bytes(b"SYNTHETIC_LATER_WORK\n")
        self.fixture.git(self.fixture.root, "add", "later.txt")
        self.fixture.git(self.fixture.root, "commit", "-m", "Later independent work")
        (self.fixture.root / "tracked.txt").write_bytes(b"Later changed original file\n")
        before = self.fixture.git(self.fixture.root, "status", "--porcelain=v1", "--ignored", "-z").stdout
        current_head = self.fixture.git(self.fixture.root, "rev-parse", "HEAD").stdout
        result = self.observe().document()
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["current_head_relation"], "different")
        self.assertEqual(self.fixture.git(self.fixture.root, "rev-parse", "HEAD").stdout, current_head)
        self.assertEqual(self.fixture.git(self.fixture.root, "status", "--porcelain=v1", "--ignored", "-z").stdout, before)
        raw = json.dumps(result)
        for private in (str(self.fixture.root), self.prepared.remote_url, self.prepared.target_ref,
                        "tracked.txt", "SYNTHETIC_LATER_WORK", *self.oids):
            self.assertNotIn(private, raw)

    def test_incomplete_invalid_or_duplicate_assertions_never_query_remote(self):
        for oids in ((), self.oids[:1], list(self.oids), (self.oids[0],) * 2,
                     (self.oids[0], "SYNTHETIC_PRIVATE_OID")):
            with self.subTest(shape=type(oids).__name__), patch.object(
                writer, "_query_exact_remote_ref_with_stored_credentials",
            ) as query, exact.ExactOperationWriterLock(self.prepared.root) as held:
                with self.assertRaises(anchors.GitAnchorObservationError) as caught:
                    anchors._observe_original_git_anchors_held(self.prepared, held=held, commit_oids=oids)
                query.assert_not_called()
                self.assertIsNone(caught.exception.__context__)
                self.assertIsNone(caught.exception.__cause__)
                self.assertNotIn("SYNTHETIC_PRIVATE", str(caught.exception))
        with self.assertRaises(anchors.GitAnchorObservationError):
            anchors._observe_original_git_anchors_held(self.prepared, held=None, commit_oids=self.oids)

    def test_order_or_commit_content_mismatch_stops_before_remote_query(self):
        query_calls = []
        def remote(prepared):
            query_calls.append(prepared)
            return "present", self.oids[-1]
        for oids in (tuple(reversed(self.oids)), (self.oids[0], "f" * 40)):
            self.assertEqual(self.observe(oids=oids, remote=remote).status, "commit_mismatch")
        self.assertEqual(query_calls, [])
        for helper, value in (("_commit_paths", ("SYNTHETIC_OTHER_PATH",)),
                              ("_tree_matches_group", False),
                              ("_commit_object", (self.prepared.initial_head_oid, b"Different message"))):
            with patch.object(writer._GitBackupBackend, helper, return_value=value):
                self.assertEqual(self.observe(remote=remote).status, "commit_mismatch")
        self.assertEqual(query_calls, [])

    def test_remote_states_do_not_overclaim_absence_or_preservation(self):
        for remote_state, remote_oid, expected in (
            ("target_ref_missing", None, "remote_absent"),
            ("unavailable", None, "remote_unavailable"),
            ("invalid_response", None, "remote_unavailable"),
            ("present", self.prepared.initial_head_oid, "remote_mismatch"),
        ):
            with self.subTest(state=remote_state):
                result = self.observe(remote=lambda p: (remote_state, remote_oid)).document()
                self.assertEqual(result["status"], expected)
                self.assertTrue(result["commit_anchors_verified"])
                self.assertFalse(result["remote_ref_independently_verified"])

    def test_runtime_config_or_metadata_change_is_not_silently_accepted(self):
        with patch.object(writer._GitBackupBackend, "_runtime_binding_matches", side_effect=[True, False]):
            self.assertEqual(self.observe().status, "observation_changed")
        with patch.object(planning, "_git_metadata_is_local_real", return_value=False):
            self.assertEqual(self.observe().status, "runtime_unavailable")
        def private_failure(prepared):
            raise OSError("SYNTHETIC_PRIVATE_REMOTE_FAILURE")
        result = self.observe(remote=private_failure).document()
        self.assertEqual(result["status"], "runtime_unavailable")
        self.assertNotIn("SYNTHETIC_PRIVATE", json.dumps(result))

    def test_head_moved_during_remote_query_is_reported_without_erasing_original_proof(self):
        def remote(prepared):
            (self.fixture.root / "concurrent.txt").write_bytes(b"Later ordinary Git work\n")
            self.fixture.git(self.fixture.root, "add", "concurrent.txt")
            self.fixture.git(self.fixture.root, "commit", "-m", "Concurrent independent commit")
            return self.fixture.remote_observer(prepared.root, prepared.remote_name, prepared.target_ref)
        result = self.observe(remote=remote).document()
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["current_head_relation"], "different")
        self.assertTrue(result["commit_anchors_verified"])
        self.assertTrue(result["remote_ref_independently_verified"])


if __name__ == "__main__":
    unittest.main()
