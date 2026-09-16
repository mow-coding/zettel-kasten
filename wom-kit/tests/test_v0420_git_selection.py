from __future__ import annotations

import copy
import json
import subprocess
import unittest
from dataclasses import replace
from unittest.mock import patch

import test_git_backup_writer as fixtures
from wom_kit import git_backup_plan as planning
from wom_kit import git_backup_writer as writer
from wom_kit.exact_human_approval_workflow import ExactHumanApprovalWorkflowError
from test_v0420_work_session_binding import binding_fixture


def archive_binding(*, revision=1, archive_id="archive:personal:git-writer-fixture"):
    return binding_fixture(
        writer.exact_human_approval_archive_identity_sha256(archive_id), revision=revision
    )


class SelectionPartitionTests(unittest.TestCase):
    plan_sha256 = "sha256:" + "a" * 64
    refs = ("change:000001", "change:000002", "change:000003")

    def document(self):
        return {
            "schema": writer.GIT_BACKUP_SELECTION_V2_SCHEMA,
            "expected_plan_sha256": self.plan_sha256,
            "selected_groups": [{
                "group_id": "group:selected",
                "change_refs": [self.refs[0]],
                "commit_subject": "Back up selected changes",
            }],
            "excluded_changes": [
                {"change_ref": self.refs[1], "scope": "mixed", "reason": "mixed_session_change"},
                {"change_ref": self.refs[2], "scope": "unknown", "reason": "ownership_unverified"},
            ],
        }

    def parse(self, document):
        return writer._selection_partition(
            document, expected_plan_sha256=self.plan_sha256, observed_change_refs=self.refs
        )

    def test_complete_disjoint_partition_binds_entire_document(self):
        document = self.document()
        groups, digest, exclusions = self.parse(document)
        self.assertEqual(groups[0].change_refs, self.refs[:1])
        self.assertEqual(digest, writer._sha256_json(document))
        self.assertEqual(exclusions, tuple(document["excluded_changes"]))
        changed = copy.deepcopy(document)
        changed["excluded_changes"][0].update(scope="other_session", reason="other_session_change")
        self.assertNotEqual(self.parse(changed)[1], digest)

    def test_incomplete_overlap_unknown_duplicate_and_untrusted_reason_rejected(self):
        mutations = {
            "missing": lambda d: d["excluded_changes"].pop(),
            "overlap": lambda d: d["selected_groups"][0]["change_refs"].append(self.refs[1]),
            "unknown": lambda d: d["excluded_changes"][1].update(change_ref="change:999999"),
            "duplicate": lambda d: d["excluded_changes"][1].update(change_ref=self.refs[1]),
            "invalid_scope": lambda d: d["excluded_changes"][0].update(scope="inferred_from_filename"),
            "private_reason": lambda d: d["excluded_changes"][0].update(reason="private_marker"),
            "mismatched_reason": lambda d: d["excluded_changes"][0].update(reason="other_session_change"),
            "extra_field": lambda d: d["excluded_changes"][0].update(owner="private_marker"),
            "wrong_plan": lambda d: d.update(expected_plan_sha256="sha256:" + "b" * 64),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                document = self.document()
                mutate(document)
                with self.assertRaises(writer.GitBackupWriterError) as failure:
                    self.parse(document)
                self.assertNotIn("private_marker", str(failure.exception))

    def test_v1_remains_exact_all_selected_and_same_hash(self):
        document = {
            "schema": writer.GIT_BACKUP_SELECTION_SCHEMA,
            "expected_plan_sha256": self.plan_sha256,
            "groups": [{
                "group_id": "group:all", "change_refs": list(self.refs),
                "commit_subject": "Back up all reviewed changes",
            }],
        }
        old = writer._selection_groups(
            document, expected_plan_sha256=self.plan_sha256, observed_change_refs=self.refs
        )
        self.assertEqual(self.parse(document), (*old, ()))
        document["groups"][0]["change_refs"].pop()
        with self.assertRaises(writer.GitBackupWriterError) as failure:
            self.parse(document)
        self.assertEqual(failure.exception.code, "git_backup_selection_incomplete")

    def test_all_excluded_is_explicit_no_selected_changes_not_empty_commit(self):
        document = self.document()
        document["selected_groups"] = []
        document["excluded_changes"].insert(0, {
            "change_ref": self.refs[0], "scope": "legacy_unattributed",
            "reason": "legacy_unattributed_change",
        })
        with self.assertRaises(writer.GitBackupWriterError) as failure:
            self.parse(document)
        self.assertEqual(failure.exception.code, "git_backup_no_selected_changes")

    def test_unbound_commit_message_keeps_exact_historical_bytes(self):
        self.assertEqual(
            writer._commit_message("Reviewed changes", self.plan_sha256, 0, "sha256:" + "b" * 64),
            ("Reviewed changes\n\n"
             + f"WOM-Git-Backup-Selection: {self.plan_sha256}\n"
             + "WOM-Git-Backup-Group: 000001\n"
             + "WOM-Git-Backup-Source: sha256:" + "b" * 64 + "\n").encode("utf-8"),
        )

    def test_binding_validation_rejects_cross_archive_tamper_and_display_data(self):
        correct = archive_binding()
        self.assertEqual(
            writer._validated_work_session_binding(correct.document(), "archive:personal:git-writer-fixture"),
            correct,
        )
        tampered = correct.document()
        tampered["revision"] = 2
        with_label = correct.document()
        with_label["app_name"] = "private_marker"
        for candidate in (
            archive_binding(archive_id="archive:personal:other-fixture"),
            tampered, with_label, {"schema": ["private_marker"]},
        ):
            with self.subTest(candidate_type=type(candidate).__name__):
                with self.assertRaises(writer.GitBackupWriterError) as failure:
                    writer._validated_work_session_binding(candidate, "archive:personal:git-writer-fixture")
                self.assertEqual(failure.exception.code, "git_backup_work_session_binding_invalid")
                self.assertNotIn("private_marker", str(failure.exception))


class GitSelectionV2RealTests(unittest.TestCase):
    """Compose the real Git/native broker fixture without inheriting its tests."""

    def setUp(self):
        self.fixture = fixtures.GitBackupWriterTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.root = self.fixture.root
        self.git = self.fixture.git

    def prepare(self, *, selected_paths=None, groups=1, work_session_binding=None):
        capture = {}
        with self.fixture.patches()[0], self.fixture.patches()[1]:
            plan = planning.git_backup_plan(
                self.root, credential_mode="stored", _private_capture=capture
            )
        self.assertTrue(plan["ok"], plan)
        if selected_paths is None:
            selected_paths = {"tracked.txt"}
        selected_refs = sorted(
            row["public_observation"]["change_ref"]
            for row in capture["private_changes"] if row["path"] in selected_paths
        )
        reasons = tuple(writer.GIT_BACKUP_EXCLUSION_REASONS.items())
        excluded = []
        for row in capture["private_changes"]:
            ref = row["public_observation"]["change_ref"]
            if ref not in selected_refs:
                scope, reason = reasons[len(excluded) % len(reasons)]
                excluded.append({"change_ref": ref, "scope": scope, "reason": reason})
        selected_groups = [
            {"group_id": f"group:selected-{i}", "change_refs": selected_refs[i::groups],
             "commit_subject": f"Back up reviewed work group {i + 1}"}
            for i in range(groups)
        ] if selected_refs else []
        selection = {
            "schema": writer.GIT_BACKUP_SELECTION_V2_SCHEMA,
            "expected_plan_sha256": plan["plan_sha256"],
            "selected_groups": selected_groups,
            "excluded_changes": excluded,
        }
        self.fixture.selection_path.write_text(json.dumps(selection, sort_keys=True), encoding="utf-8")
        with self.fixture.patches()[0], self.fixture.patches()[1]:
            prepared = writer.prepare_git_backup(
                self.root, expected_plan_sha256=plan["plan_sha256"],
                selection_manifest_path=self.fixture.selection_path, credential_mode="stored",
                work_session_binding=work_session_binding,
            )
        return prepared

    def execute(self, prepared, *, native=None):
        with self.fixture.patches()[2], self.fixture.patches()[3]:
            return writer.execute_git_backup(
                prepared, selection_manifest_path=self.fixture.selection_path,
                reviewer_claim="person:local-operator", native=native or fixtures._Native(),
                key_provider=fixtures._KeyProvider(),
            )

    def excluded_snapshot(self, prepared):
        paths = sorted({
            path for row in prepared.excluded_changes
            for path in writer._change_paths(row["private_change"])
        })
        index = subprocess.run(
            ["git", "-C", str(self.root), "ls-files", "--stage", "-z", "--", *paths],
            check=True, capture_output=True,
        ).stdout
        return index, {path: (self.root / path).read_bytes() for path in paths}

    def test_sixty_two_changes_preserve_excluded_staging_and_bytes_and_push_only_selected(self):
        paths = [f"cohort-{i:03d}.txt" for i in range(60)]
        for path in paths:
            (self.root / path).write_bytes(b"baseline\n")
        self.git(self.root, "add", "--", *paths)
        self.git(self.root, "commit", "--only", "-m", "Fixture cohort", "--", *paths)
        initial_head = self.git(self.root, "rev-parse", "HEAD").stdout.strip()
        self.git(self.root, "push", str(self.fixture.remote), "HEAD:refs/heads/main")
        for path in paths:
            (self.root / path).write_bytes(b"staged version\n")
        self.git(self.root, "add", "--", *paths)
        for path in paths[::2]:
            (self.root / path).write_bytes(b"unstaged version after staging\n")
        selected_paths = {"tracked.txt", "new-private.txt", *paths[:18]}
        prepared = self.prepare(selected_paths=selected_paths, groups=2)
        public = prepared.public_plan()
        self.assertEqual(public["classified_change_count"], 62)
        self.assertEqual(public["selected_change_count"], 20)
        self.assertEqual(public["excluded_change_count"], 42)
        self.assertEqual(sum(public["exclusion_scope_counts"].values()), 42)
        self.assertTrue(any(
            row["private_change"]["public_observation"]["staging_state"] == "staged_and_unstaged"
            for row in prepared.excluded_changes
        ))
        before = self.excluded_snapshot(prepared)
        result = self.execute(prepared)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["selected_change_count"], 20)
        self.assertEqual(result["excluded_change_count"], 42)
        self.assertTrue(result["excluded_index_and_worktree_observations_verified"])
        self.assertEqual(self.excluded_snapshot(prepared), before)
        head = self.fixture.assert_remote_matches_head()
        committed_paths = set(self.git(self.root, "diff", "--name-only", initial_head, head).stdout.splitlines())
        self.assertEqual(committed_paths, selected_paths)
        self.assertEqual(self.git(self.root, "rev-list", "--count", f"{initial_head}..{head}").stdout.strip(), "2")
        self.assertEqual(len(self.fixture.transport_commands), 1)
        for command in self.fixture.transport_commands:
            self.assertNotIn("--force", command)
            self.assertNotIn("--force-with-lease", command)
        loaded = writer.load_private_git_backup_bundle(
            self.root, manifest_sha256=prepared.manifest.manifest_sha256
        )
        self.assertEqual(loaded.manifest.document(), prepared.manifest.document())
        self.assertEqual(writer._bundle_document(loaded), writer._bundle_document(prepared))
        serialized = json.dumps({"plan": public, "result": result})
        self.assertNotIn("cohort-", serialized)
        self.assertNotIn("staged version", serialized)
        self.assertNotIn("private/repository.git", serialized)

    def test_interrupted_add_resume_keeps_exclusions_and_reuses_exact_claim(self):
        # A real excluded file has a staged blob different from its worktree.
        self.git(self.root, "add", "--", "new-private.txt")
        (self.root / "new-private.txt").write_bytes(b"excluded unstaged bytes\n")
        prepared = self.prepare()
        before = self.excluded_snapshot(prepared)
        original = writer._GitBackupBackend._git_raw
        failed_once = False
        native = fixtures._Native()

        def fail_first_commit(backend, args, **kwargs):
            nonlocal failed_once
            if not failed_once and "commit" in args and "--only" in args:
                failed_once = True
                return 1, b""
            return original(backend, args, **kwargs)

        with patch.object(writer._GitBackupBackend, "_git_raw", new=fail_first_commit):
            with self.assertRaises(ExactHumanApprovalWorkflowError):
                self.execute(prepared, native=native)
        self.assertTrue(failed_once)
        self.assertEqual(self.excluded_snapshot(prepared), before)
        self.assertEqual(self.git(self.root, "rev-parse", "HEAD").stdout.strip(), self.fixture.initial_head)
        loaded = writer.load_private_git_backup_bundle(
            self.root, manifest_sha256=prepared.manifest.manifest_sha256
        )
        with self.fixture.patches()[2], self.fixture.patches()[3]:
            result = writer.resume_git_backup(
                loaded, reviewer_claim="person:local-operator", approval_id=self.fixture.only_claim_id(),
                key_provider=fixtures._KeyProvider(),
            )
        self.assertTrue(result["ok"], result)
        self.assertEqual(native.calls, 1)
        self.assertEqual(self.excluded_snapshot(prepared), before)
        self.fixture.assert_remote_matches_head()

    def test_excluded_worktree_drift_before_approval_blocks_without_overwrite(self):
        prepared = self.prepare()
        changed = b"other session changed these bytes\n"
        native = fixtures._Native(lambda: (self.root / "new-private.txt").write_bytes(changed))
        with self.assertRaises(ExactHumanApprovalWorkflowError):
            self.execute(prepared, native=native)
        self.assertEqual((self.root / "new-private.txt").read_bytes(), changed)
        self.assertEqual(self.git(self.root, "rev-parse", "HEAD").stdout.strip(), self.fixture.initial_head)
        self.assertFalse(self.fixture.transport_commands)

    def test_excluded_index_only_drift_before_commit_blocks_and_preserves_new_staging(self):
        prepared = self.prepare()
        original = writer._GitBackupBackend._git_raw
        changed = False

        def stage_excluded_after_selected_add(backend, args, **kwargs):
            nonlocal changed
            result = original(backend, args, **kwargs)
            if not changed and "add" in args and "--" in args:
                changed = True
                self.git(self.root, "add", "--", "new-private.txt")
            return result

        with patch.object(writer._GitBackupBackend, "_git_raw", new=stage_excluded_after_selected_add):
            with self.assertRaises(ExactHumanApprovalWorkflowError):
                self.execute(prepared)
        self.assertTrue(changed)
        self.assertIn("new-private.txt", self.git(self.root, "diff", "--cached", "--name-only").stdout)
        self.assertEqual(self.git(self.root, "rev-parse", "HEAD").stdout.strip(), self.fixture.initial_head)
        self.assertFalse(self.fixture.transport_commands)

    def test_excluded_drift_at_push_boundary_does_not_advance_remote(self):
        prepared = self.prepare()
        original = writer._GitBackupBackend._push
        changed = b"other work changed at transport boundary\n"

        def change_before_push(backend):
            (self.root / "new-private.txt").write_bytes(changed)
            return original(backend)

        with patch.object(writer._GitBackupBackend, "_push", new=change_before_push):
            with self.assertRaises(ExactHumanApprovalWorkflowError):
                self.execute(prepared)
        self.assertEqual((self.root / "new-private.txt").read_bytes(), changed)
        head = self.git(self.root, "rev-parse", "HEAD").stdout.strip()
        self.assertNotEqual(head, self.fixture.initial_head)
        self.assertEqual(
            self.fixture.remote_observer(self.root, "origin", "refs/heads/main"),
            ("present", self.fixture.initial_head),
        )
        self.assertFalse(self.fixture.transport_commands)

    def test_crash_after_commit_resume_verifies_existing_commit_without_repetition(self):
        prepared = self.prepare()
        before = self.excluded_snapshot(prepared)
        original = writer._GitBackupWriter.write_field
        crashed = False
        native = fixtures._Native()

        def crash_after_commit(adapter, **kwargs):
            nonlocal crashed
            original(adapter, **kwargs)
            if kwargs.get("target_kind") == "git_commit_group" and not crashed:
                crashed = True
                raise RuntimeError("synthetic_process_loss")

        with patch.object(writer._GitBackupWriter, "write_field", new=crash_after_commit):
            with self.assertRaises(ExactHumanApprovalWorkflowError):
                self.execute(prepared, native=native)
        self.assertTrue(crashed)
        committed_head = self.git(self.root, "rev-parse", "HEAD").stdout.strip()
        self.assertNotEqual(committed_head, self.fixture.initial_head)
        loaded = writer.load_private_git_backup_bundle(
            self.root, manifest_sha256=prepared.manifest.manifest_sha256
        )
        with self.fixture.patches()[2], self.fixture.patches()[3]:
            result = writer.resume_git_backup(
                loaded, reviewer_claim="person:local-operator", approval_id=self.fixture.only_claim_id(),
                key_provider=fixtures._KeyProvider(),
            )
        self.assertTrue(result["ok"], result)
        self.assertEqual(native.calls, 1)
        self.assertEqual(self.fixture.assert_remote_matches_head(), committed_head)
        self.assertEqual(self.excluded_snapshot(prepared), before)

    def test_all_excluded_does_not_prepare_approval_commit_or_push(self):
        before = self.git(self.root, "status", "--porcelain=v1", "-z").stdout
        with self.assertRaises(writer.GitBackupWriterError) as failure:
            self.prepare(selected_paths=set())
        self.assertEqual(failure.exception.code, "git_backup_no_selected_changes")
        self.assertEqual(self.git(self.root, "status", "--porcelain=v1", "-z").stdout, before)
        self.assertEqual(self.git(self.root, "rev-parse", "HEAD").stdout.strip(), self.fixture.initial_head)
        self.assertFalse((self.root / "profiles" / "local" / "exact-human-approvals").exists())
        self.assertFalse(self.fixture.transport_commands)

    def test_private_bundle_exclusion_tamper_cannot_reuse_approved_manifest(self):
        prepared = self.prepare()
        directory = writer._private_bundle_root(self.root, create=True)
        path = directory / (prepared.manifest.manifest_sha256.removeprefix("sha256:") + ".json")
        original = writer._bundle_document(prepared)
        path.write_bytes(writer._canonical(original) + b"\n")
        loaded = writer.load_private_git_backup_bundle(
            self.root, manifest_sha256=prepared.manifest.manifest_sha256
        )
        self.assertEqual(loaded.manifest.document(), prepared.manifest.document())
        for mode in ("scope", "observed_bytes", "path_overlap"):
            with self.subTest(mode=mode):
                document = copy.deepcopy(original)
                exclusion = document["excluded_changes"][0]
                if mode == "scope":
                    exclusion.update(scope="unknown", reason="ownership_unverified")
                elif mode == "observed_bytes":
                    exclusion["private_change"]["public_observation"]["worktree"]["sha256"] = "sha256:" + "f" * 64
                else:
                    exclusion["private_change"]["path"] = "tracked.txt"
                document["push_source"]["excluded_changes"] = copy.deepcopy(document["excluded_changes"])
                document["push_target_identity_sha256"] = writer._sha256_json({
                    "schema": "wom-kit/git-backup-push-target/v1",
                    "push_source_sha256": writer._sha256_bytes(writer._canonical(document["push_source"])),
                })
                document.pop("bundle_sha256")
                document["bundle_sha256"] = writer._sha256_json(document)
                path.write_bytes(writer._canonical(document) + b"\n")
                with self.assertRaises(writer.GitBackupWriterError) as failure:
                    writer.load_private_git_backup_bundle(
                        self.root, manifest_sha256=prepared.manifest.manifest_sha256
                    )
                self.assertEqual(failure.exception.code, "git_backup_manifest_drifted")

    def test_exclusion_view_mutation_cannot_replace_bound_source_observation(self):
        prepared = self.prepare()
        prepared.excluded_changes[0]["private_change"]["path"] = "private_marker.txt"
        with self.fixture.patches()[3], writer._pinned_git_runtime(prepared):
            backend = writer._GitBackupBackend(prepared)
            self.assertFalse(backend._refresh()["classification_complete"])
        self.assertFalse(self.fixture.transport_commands)

    def test_selected_observation_mutation_after_approval_never_commits_or_pushes(self):
        for version in (1, 2):
            for change_disk in (False, True):
                with self.subTest(version=version, change_disk=change_disk):
                    prepared = (self.fixture.plan_and_prepare() if version == 1
                                else self.prepare(work_session_binding=archive_binding()))
                    before_source = prepared.groups[0].source_payload
                    selected = next(row for row in prepared.groups[0].private_changes if row["path"] == "tracked.txt")
                    target = self.root / "tracked.txt"
                    before_bytes = target.read_bytes()
                    before_index = self.git(self.root, "ls-files", "--stage", "-z").stdout
                    changed_bytes = b"Synthetic bytes changed after approval\n"

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
                        with self.assertRaises(ExactHumanApprovalWorkflowError):
                            self.execute(prepared, native=native)
                        self.assertEqual(native.calls, 1)
                        self.assertEqual(prepared.groups[0].source_payload, before_source)
                        self.assertEqual(self.git(self.root, "rev-parse", "HEAD").stdout.strip(), self.fixture.initial_head)
                        self.assertEqual(self.fixture.assert_remote_matches_head(), self.fixture.initial_head)
                        self.assertEqual(self.git(self.root, "ls-files", "--stage", "-z").stdout, before_index)
                        self.assertEqual(target.read_bytes(), changed_bytes if change_disk else before_bytes)
                        self.assertFalse(self.fixture.transport_commands)
                        self.assertFalse((self.root / "profiles" / "local" / "exact-human-approvals").exists())
                        self.assertFalse((self.root / "receipts").exists())
                    finally:
                        target.write_bytes(before_bytes)

    def test_validated_prepared_is_deeply_detached_with_identical_serialization(self):
        for version in (1, 2):
            with self.subTest(version=version):
                prepared = (self.fixture.plan_and_prepare() if version == 1
                            else self.prepare(work_session_binding=archive_binding()))
                before = writer._canonical(writer._bundle_document(prepared))
                frozen = writer._freeze_validated_prepared(prepared)
                self.assertEqual(writer._canonical(writer._bundle_document(frozen)), before)
                self.assertIsNot(frozen.groups[0].private_changes[0], prepared.groups[0].private_changes[0])
                self.assertIsNot(frozen.groups[0].private_changes[0]["public_observation"],
                                 prepared.groups[0].private_changes[0]["public_observation"])
                prepared.groups[0].private_changes[0]["public_observation"]["worktree"]["sha256"] = "sha256:" + "f" * 64
                self.assertEqual(writer._canonical(writer._bundle_document(frozen)), before)
                self.assertEqual(writer._freeze_validated_prepared(frozen), frozen)
                with self.assertRaisesRegex(writer.GitBackupWriterError, "^git_backup_manifest_drifted$"):
                    writer._freeze_validated_prepared(prepared)

    def test_v1_prepared_bundle_and_public_plan_have_no_new_fields(self):
        prepared = self.fixture.plan_and_prepare()
        self.assertEqual(prepared.selection_schema, writer.GIT_BACKUP_SELECTION_SCHEMA)
        self.assertEqual(prepared.excluded_changes, ())
        self.assertNotIn("excluded_change_count", prepared.public_plan())
        self.assertNotIn("selection_schema", prepared.public_plan())
        bundle = writer._bundle_document(prepared)
        self.assertEqual(bundle["schema"], "wom-kit/git-backup-private-execution-bundle/v1")
        self.assertNotIn("excluded_changes", bundle)
        self.assertEqual(bundle["push_source"]["schema"], "wom-kit/git-backup-push-source/v1")
        self.assertNotIn("excluded_changes", bundle["push_source"])
        self.assertNotIn("work_session_binding", bundle)
        self.assertNotIn("work_session_binding", bundle["push_source"])
        self.assertNotIn("work_session_binding", prepared.manifest.document())
        with self.fixture.patches()[0], self.fixture.patches()[1]:
            with self.assertRaises(writer.GitBackupWriterError) as failure:
                writer.prepare_git_backup(
                    self.root, expected_plan_sha256=prepared.expected_plan_sha256,
                    selection_manifest_path=self.fixture.selection_path, credential_mode="stored",
                    work_session_binding=archive_binding(),
                )
        self.assertEqual(failure.exception.code, "git_backup_work_session_binding_invalid")
        directory = writer._private_bundle_root(self.root, create=True)
        path = directory / (prepared.manifest.manifest_sha256.removeprefix("sha256:") + ".json")
        raw = writer._canonical(bundle) + b"\n"
        path.write_bytes(raw)
        # Unbound replay does not consult or invent a work-session binding.
        with patch("wom_kit.work_session_binding.WorkSessionBinding.from_document", side_effect=AssertionError("legacy replay read current binding")):
            loaded = writer.load_private_git_backup_bundle(
                self.root, manifest_sha256=prepared.manifest.manifest_sha256
            )
        self.assertIsNone(loaded.manifest.work_session_binding)
        self.assertEqual(writer._canonical(writer._bundle_document(loaded)) + b"\n", raw)
        self.assertEqual(loaded.manifest.document(), prepared.manifest.document())
        self.assertEqual(loaded.groups[0].commit_message, prepared.groups[0].commit_message)

    def test_bound_v2_commit_resume_and_remote_receipt_share_frozen_binding(self):
        binding = archive_binding(revision=7)
        prepared = self.prepare(work_session_binding=binding.document())
        before = self.excluded_snapshot(prepared)
        self.assertEqual(prepared.manifest.work_session_binding, binding)
        self.assertEqual(prepared.public_plan()["work_session_binding"], binding.document())
        self.assertEqual(json.loads(prepared.push_source_payload)["work_session_binding"], binding.document())
        for group in prepared.groups:
            self.assertEqual(json.loads(group.source_payload)["work_session_binding"], binding.document())
        original = writer._GitBackupWriter.write_field
        crashed = False
        native = fixtures._Native()

        def crash_after_commit(adapter, **kwargs):
            nonlocal crashed
            original(adapter, **kwargs)
            if kwargs.get("target_kind") == "git_commit_group" and not crashed:
                crashed = True
                raise RuntimeError("synthetic_bound_process_loss")

        with patch.object(writer._GitBackupWriter, "write_field", new=crash_after_commit):
            with self.assertRaises(ExactHumanApprovalWorkflowError):
                self.execute(prepared, native=native)
        self.assertTrue(crashed)
        head = self.git(self.root, "rev-parse", "HEAD").stdout.strip()
        message = self.git(self.root, "show", "-s", "--format=%B", head).stdout
        for value in (binding.client_app_ref, binding.workstream_ref, binding.work_session_ref, binding.binding_sha256):
            self.assertIn(value, message)
        self.assertIn("WOM-Work-Session-Revision: 7", message)
        self.assertNotIn("worktree", message)
        loaded = writer.load_private_git_backup_bundle(
            self.root, manifest_sha256=prepared.manifest.manifest_sha256
        )
        self.assertEqual(loaded.manifest.work_session_binding, binding)
        self.assertEqual(writer._bundle_document(loaded), writer._bundle_document(prepared))
        with self.fixture.patches()[2], self.fixture.patches()[3]:
            result = writer.resume_git_backup(
                loaded, reviewer_claim="person:local-operator", approval_id=self.fixture.only_claim_id(),
                key_provider=fixtures._KeyProvider(),
            )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["work_session_binding"], binding.document())
        self.assertEqual(self.fixture.assert_remote_matches_head(), head)
        self.assertEqual(self.excluded_snapshot(prepared), before)
        self.assertEqual(native.calls, 1)
        receipts = list((self.root / "receipts" / "ops" / "git-backups").glob("*.json"))
        self.assertEqual(len(receipts), 1)
        self.assertEqual(json.loads(receipts[0].read_text(encoding="utf-8"))["work_session_binding"], binding.document())

    def test_binding_revision_changes_source_and_manifest_not_the_observed_plan(self):
        first = self.prepare(work_session_binding=archive_binding(revision=1))
        second = self.prepare(work_session_binding=archive_binding(revision=2))
        self.assertEqual(first.expected_plan_sha256, second.expected_plan_sha256)
        self.assertEqual(first.selection_sha256, second.selection_sha256)
        self.assertNotEqual(first.groups[0].source_sha256, second.groups[0].source_sha256)
        self.assertNotEqual(first.groups[0].commit_message, second.groups[0].commit_message)
        self.assertNotEqual(first.manifest.manifest_sha256, second.manifest.manifest_sha256)
        self.assertNotEqual(first.manifest.extension_sha256, second.manifest.extension_sha256)
        self.assertNotEqual(first.push_source_payload, second.push_source_payload)

    def test_bound_bundle_cannot_replace_or_drop_its_historical_binding(self):
        binding = archive_binding()
        prepared = self.prepare(work_session_binding=binding)
        original = writer._bundle_document(prepared)
        directory = writer._private_bundle_root(self.root, create=True)
        path = directory / (prepared.manifest.manifest_sha256.removeprefix("sha256:") + ".json")
        for change in (None, archive_binding(revision=2).document(), archive_binding(archive_id="archive:personal:other-fixture").document()):
            with self.subTest(binding_present=change is not None):
                document = copy.deepcopy(original)
                document["work_session_binding"] = change
                document.pop("bundle_sha256")
                document["bundle_sha256"] = writer._sha256_json(document)
                path.write_bytes(writer._canonical(document) + b"\n")
                with self.assertRaises(writer.GitBackupWriterError) as failure:
                    writer.load_private_git_backup_bundle(self.root, manifest_sha256=prepared.manifest.manifest_sha256)
                self.assertEqual(failure.exception.code, "git_backup_manifest_drifted")
        forged_manifest = writer._build_exact_manifest(
            archive_id=prepared.archive_id, groups=prepared.groups,
            push_source_payload=prepared.push_source_payload,
            push_target_identity_sha256=prepared.push_target_identity_sha256,
            work_session_binding=archive_binding(revision=2),
        )
        forged = replace(prepared, manifest=forged_manifest)
        with writer._pinned_git_runtime(forged):
            self.assertFalse(writer._GitBackupBackend(forged)._refresh()["classification_complete"])
        self.assertEqual(self.git(self.root, "rev-parse", "HEAD").stdout.strip(), self.fixture.initial_head)

    def test_cross_archive_binding_cannot_prepare_a_git_write(self):
        before = self.git(self.root, "status", "--porcelain=v1", "-z").stdout
        with patch.object(planning, "git_backup_plan", side_effect=AssertionError("cross-archive planner entered")) as planner:
            with self.assertRaises(writer.GitBackupWriterError) as failure:
                writer.prepare_git_backup(
                    self.root, expected_plan_sha256="sha256:" + "a" * 64,
                    selection_manifest_path=self.fixture.selection_path, credential_mode="stored",
                    work_session_binding=archive_binding(archive_id="archive:personal:other-fixture"),
                )
        planner.assert_not_called()
        self.assertEqual(failure.exception.code, "git_backup_work_session_binding_invalid")
        self.assertEqual(self.git(self.root, "status", "--porcelain=v1", "-z").stdout, before)
        self.assertFalse(self.fixture.transport_commands)

    def test_supplied_binding_is_frozen_before_planner_callbacks(self):
        unbound = self.prepare()
        original_binding = archive_binding(revision=1)
        supplied = original_binding.document()
        original_plan = planning.git_backup_plan

        def mutate_supplied_after_plan(*args, **kwargs):
            result = original_plan(*args, **kwargs)
            supplied.clear()
            supplied.update(archive_binding(revision=2).document())
            return result

        with (
            self.fixture.patches()[0], self.fixture.patches()[1],
            patch.object(planning, "git_backup_plan", side_effect=mutate_supplied_after_plan),
        ):
            prepared = writer.prepare_git_backup(
                self.root, expected_plan_sha256=unbound.expected_plan_sha256,
                selection_manifest_path=self.fixture.selection_path, credential_mode="stored",
                work_session_binding=supplied,
            )
        self.assertEqual(supplied["revision"], 2)
        self.assertEqual(prepared.manifest.work_session_binding, original_binding)
        self.assertEqual(json.loads(prepared.groups[0].source_payload)["work_session_binding"], original_binding.document())


if __name__ == "__main__":
    unittest.main()
