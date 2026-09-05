from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import git_backup_plan as planning
from wom_kit import git_backup_writer as writer
from wom_kit.exact_human_approval_windows import APPROVE_BUTTON_ID
from wom_kit.exact_human_approval_workflow import ExactHumanApprovalWorkflowError


class _Native:
    def __init__(self, callback: Callable[[], None] | None = None) -> None:
        self.calls = 0
        self.callback = callback

    def show(self, **_kwargs: str) -> tuple[int, bool]:
        self.calls += 1
        if self.callback is not None:
            self.callback()
        return APPROVE_BUTTON_ID, True


class _KeyProvider:
    def __init__(self) -> None:
        self.create_if_missing: list[bool] = []

    def use_key(
        self,
        _root: Path | str,
        consumer: Callable[[memoryview], Any],
        *,
        create_if_missing: bool = False,
    ) -> Any:
        self.create_if_missing.append(create_if_missing)
        key = bytearray(range(32))
        try:
            return consumer(memoryview(key))
        finally:
            key[:] = b"\0" * len(key)


class GitBackupWriterTests(unittest.TestCase):
    maxDiff = None

    @staticmethod
    def git(repository: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(repository), *args],
            check=check,
            capture_output=True,
            text=True,
        )

    @staticmethod
    def git_dir(repository: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", f"--git-dir={repository}", *args],
            check=check,
            capture_output=True,
            text=True,
        )

    def setUp(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is required")
        self.temporary = tempfile.TemporaryDirectory()
        parent = Path(self.temporary.name)
        self.root = parent / "archive"
        self.remote = parent / "remote.git"
        self.selection_path = parent / "selection.json"
        self.root.mkdir()
        subprocess.run(
            ["git", "init", "--bare", str(self.remote)],
            check=True,
            capture_output=True,
            text=True,
        )
        self.git(self.root, "init", "-b", "main")
        self.git(self.root, "config", "user.name", "writer-test")
        self.git(self.root, "config", "user.email", "writer-test@example.invalid")
        (self.root / "archive.yml").write_text(
            "archive_id: archive:personal:git-writer-fixture\n",
            encoding="utf-8",
        )
        (self.root / ".gitignore").write_text(
            "profiles/local/\n",
            encoding="utf-8",
        )
        (self.root / "tracked.txt").write_text("before\n", encoding="utf-8")
        self.git(self.root, "add", "archive.yml", ".gitignore", "tracked.txt")
        self.git(self.root, "commit", "-m", "fixture")
        self.initial_head = self.git(self.root, "rev-parse", "HEAD").stdout.strip()
        self.git(self.root, "remote", "add", "origin", "https://example.invalid/private/repository.git")
        self.git(
            self.root,
            "push",
            str(self.remote),
            "HEAD:refs/heads/main",
        )
        (self.root / "tracked.txt").write_text("after\n", encoding="utf-8")
        (self.root / "new-private.txt").write_text("new bytes\n", encoding="utf-8")
        self.transport_commands: list[list[str]] = []

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def fixed_handoff() -> dict[str, object]:
        return {
            "state_digest": "sha256:" + "a" * 64,
            "status": "current_verified",
            "ready_for_context_reset": True,
        }

    def remote_observer(
        self,
        _root: Path,
        _remote_name: str,
        full_ref: str,
    ) -> tuple[str, str | None]:
        observed = self.git_dir(
            self.remote,
            "show-ref",
            "--verify",
            "--hash",
            full_ref,
            check=False,
        )
        if observed.returncode == 1 and not observed.stdout:
            return "target_ref_missing", None
        if observed.returncode != 0:
            return "unavailable", None
        return "present", observed.stdout.strip().lower()

    def transport_runner(
        self,
        command: list[str],
        *,
        environment: dict[str, str],
        timeout_seconds: int,
        max_output_bytes: int,
    ) -> tuple[int, bytes]:
        del environment, timeout_seconds
        self.transport_commands.append(list(command))
        self.assertIn("push", command)
        self.assertNotIn("--force", command)
        self.assertNotIn("--force-with-lease", command)
        head = self.git(self.root, "rev-parse", "HEAD").stdout.strip()
        target_ref = next(value.split(":", 1)[1] for value in command if value.startswith(head + ":"))
        pushed = self.git(
            self.root,
            "push",
            "--porcelain",
            str(self.remote),
            f"{head}:{target_ref}",
            check=False,
        )
        raw = pushed.stdout.encode("utf-8")
        return pushed.returncode, raw[:max_output_bytes]

    def patches(self):
        return (
            patch.object(
                planning,
                "_query_remote_ref_with_stored_credentials",
                side_effect=self.remote_observer,
            ),
            patch.object(
                planning,
                "_handoff_observation",
                return_value=self.fixed_handoff(),
            ),
            patch.object(
                planning,
                "_run_transport_capped",
                side_effect=self.transport_runner,
            ),
            patch.object(
                writer,
                "_query_exact_remote_ref_with_stored_credentials",
                side_effect=lambda prepared: self.remote_observer(
                    prepared.root,
                    prepared.remote_name,
                    prepared.target_ref,
                ),
            ),
        )

    def plan_and_prepare(self, *, group_count: int = 1) -> writer.PreparedGitBackup:
        with self.patches()[0], self.patches()[1]:
            plan = planning.git_backup_plan(self.root, credential_mode="stored")
        self.assertTrue(plan["ok"], plan)
        refs = [row["change_ref"] for row in plan["changes"]]
        groups: list[dict[str, object]] = []
        if group_count == 1:
            groups.append(
                {
                    "group_id": "group:all",
                    "change_refs": refs,
                    "commit_subject": "Back up reviewed archive changes",
                }
            )
        else:
            self.assertEqual(group_count, len(refs))
            for ordinal, reference in enumerate(refs, start=1):
                groups.append(
                    {
                        "group_id": f"group:part-{ordinal}",
                        "change_refs": [reference],
                        "commit_subject": f"Back up reviewed group {ordinal}",
                    }
                )
        self.selection_path.write_text(
            json.dumps(
                {
                    "schema": writer.GIT_BACKUP_SELECTION_SCHEMA,
                    "expected_plan_sha256": plan["plan_sha256"],
                    "groups": groups,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        with self.patches()[0], self.patches()[1]:
            return writer.prepare_git_backup(
                self.root,
                expected_plan_sha256=plan["plan_sha256"],
                selection_manifest_path=self.selection_path,
                credential_mode="stored",
            )

    def execution_patches(self):
        return (
            self.patches()[2],
            self.patches()[3],
        )

    def only_claim_id(self) -> str:
        claims = list(
            (
                self.root
                / "profiles"
                / "local"
                / "exact-human-approvals"
                / "claims"
            ).glob("*.json")
        )
        self.assertEqual(len(claims), 1)
        document = json.loads(claims[0].read_text(encoding="utf-8"))
        return document["approval_id"]

    def assert_remote_matches_head(self) -> str:
        head = self.git(self.root, "rev-parse", "HEAD").stdout.strip()
        self.assertEqual(
            self.remote_observer(self.root, "origin", "refs/heads/main"),
            ("present", head),
        )
        return head

    def test_exact_approved_commit_push_requery_and_content_free_receipt(self) -> None:
        prepared = self.plan_and_prepare()
        native = _Native()
        key_provider = _KeyProvider()
        git_commands: list[list[str]] = []
        original_git_raw = writer._GitBackupBackend._git_raw

        def recording_git_raw(backend, args, **kwargs):
            git_commands.append(list(args))
            return original_git_raw(backend, args, **kwargs)

        with (
            self.patches()[0],
            self.patches()[1],
            self.patches()[2],
            self.patches()[3],
            patch.object(
                writer._GitBackupBackend,
                "_git_raw",
                new=recording_git_raw,
            ),
        ):
            result = writer.execute_git_backup(
                prepared,
                selection_manifest_path=self.selection_path,
                reviewer_claim="person:local-operator",
                native=native,
                key_provider=key_provider,
            )

        self.assertTrue(result["ok"], result)
        self.assertEqual(native.calls, 1)
        self.assertEqual(key_provider.create_if_missing, [True])
        head = self.git(self.root, "rev-parse", "HEAD").stdout.strip()
        self.assertNotEqual(head, self.initial_head)
        self.assertEqual(self.remote_observer(self.root, "origin", "refs/heads/main"), ("present", head))
        changed = self.git(
            self.root,
            "diff",
            "--name-only",
            f"{self.initial_head}..{head}",
        ).stdout.splitlines()
        self.assertEqual(changed, ["new-private.txt", "tracked.txt"])
        self.assertEqual(len(self.transport_commands), 1)
        self.assertIn(prepared.remote_url, self.transport_commands[0])
        self.assertNotIn(prepared.remote_name, self.transport_commands[0])
        receipt_paths = list((self.root / "receipts" / "ops" / "git-backups").glob("*.json"))
        self.assertEqual(len(receipt_paths), 1)
        receipt = json.loads(receipt_paths[0].read_text(encoding="ascii"))
        self.assertEqual(receipt["status"], "completed")
        self.assertTrue(receipt["exact_remote_ref_requeried"])
        add_commands = [command for command in git_commands if "add" in command]
        self.assertTrue(add_commands)
        for command in add_commands:
            self.assertIn("--", command)
            self.assertNotIn("-A", command)
            self.assertNotIn("--all", command)
            delimiter = command.index("--")
            self.assertTrue(set(command[delimiter + 1 :]).issubset(set(prepared.groups[0].paths)))
        commit_commands = [
            command
            for command in git_commands
            if "commit" in command and "--only" in command
        ]
        self.assertEqual(len(commit_commands), 1)
        self.assertEqual(
            tuple(commit_commands[0][commit_commands[0].index("--") + 1 :]),
            prepared.groups[0].paths,
        )
        forbidden = {"pull", "fetch", "merge", "rebase", "reset", "clean"}
        self.assertFalse(
            [command for command in git_commands if forbidden.intersection(command)]
        )
        serialized_result = json.dumps(result, ensure_ascii=False)
        serialized_receipt = json.dumps(receipt, ensure_ascii=False)
        for private_value in (
            str(self.root),
            "new-private.txt",
            "tracked.txt",
            "https://example.invalid/private/repository.git",
            "Back up reviewed archive changes",
        ):
            self.assertNotIn(private_value, serialized_result)
            self.assertNotIn(private_value, serialized_receipt)

        loaded = writer.load_private_git_backup_bundle(
            self.root,
            manifest_sha256=prepared.manifest.manifest_sha256,
        )
        self.assertEqual(loaded.manifest.document(), prepared.manifest.document())
        push_count = len(self.transport_commands)
        with self.patches()[3]:
            with self.assertRaises(ExactHumanApprovalWorkflowError) as replay:
                writer.resume_git_backup(
                    loaded,
                    reviewer_claim="person:local-operator",
                    approval_id=result["exact_human_approval"]["approval_id"],
                    key_provider=_KeyProvider(),
                )
        self.assertEqual(
            replay.exception.code,
            "exact_human_approval_resume_claim_invalid",
        )
        self.assertEqual(len(self.transport_commands), push_count)

    def test_commit_failure_keeps_exact_stage_and_resume_finishes(self) -> None:
        prepared = self.plan_and_prepare()
        native = _Native()
        original_git_raw = writer._GitBackupBackend._git_raw
        failed_once = False

        def fail_first_commit(backend, args, **kwargs):
            nonlocal failed_once
            if not failed_once and "commit" in args and "--only" in args:
                failed_once = True
                return 1, b""
            return original_git_raw(backend, args, **kwargs)

        with (
            self.patches()[2],
            self.patches()[3],
            patch.object(
                writer._GitBackupBackend,
                "_git_raw",
                new=fail_first_commit,
            ),
        ):
            with self.assertRaises(ExactHumanApprovalWorkflowError) as failed:
                writer.execute_git_backup(
                    prepared,
                    selection_manifest_path=self.selection_path,
                    reviewer_claim="person:local-operator",
                    native=native,
                    key_provider=_KeyProvider(),
                )
        self.assertEqual(failed.exception.code, "exact_human_approval_state_unknown")
        self.assertTrue(failed_once)
        self.assertEqual(self.git(self.root, "rev-parse", "HEAD").stdout.strip(), self.initial_head)
        self.assertEqual(
            tuple(
                self.git(self.root, "diff", "--cached", "--name-only")
                .stdout.splitlines()
            ),
            prepared.groups[0].paths,
        )
        approval_id = self.only_claim_id()
        with self.patches()[2], self.patches()[3]:
            resumed = writer.resume_git_backup(
                prepared,
                reviewer_claim="person:local-operator",
                approval_id=approval_id,
                key_provider=_KeyProvider(),
            )
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(native.calls, 1)
        self.assert_remote_matches_head()

    def test_commit_after_crash_is_verified_and_resume_does_not_duplicate_it(self) -> None:
        prepared = self.plan_and_prepare()
        original_write = writer._GitBackupWriter.write_field
        crashed = False

        def crash_after_commit(adapter, **kwargs):
            nonlocal crashed
            original_write(adapter, **kwargs)
            if kwargs.get("target_kind") == "git_commit_group" and not crashed:
                crashed = True
                raise RuntimeError("simulated_process_loss")

        with (
            self.patches()[2],
            self.patches()[3],
            patch.object(
                writer._GitBackupWriter,
                "write_field",
                new=crash_after_commit,
            ),
        ):
            with self.assertRaises(ExactHumanApprovalWorkflowError):
                writer.execute_git_backup(
                    prepared,
                    selection_manifest_path=self.selection_path,
                    reviewer_claim="person:local-operator",
                    native=_Native(),
                    key_provider=_KeyProvider(),
                )
        committed_head = self.git(self.root, "rev-parse", "HEAD").stdout.strip()
        self.assertNotEqual(committed_head, self.initial_head)
        self.assertEqual(
            self.remote_observer(self.root, "origin", "refs/heads/main"),
            ("present", self.initial_head),
        )
        approval_id = self.only_claim_id()
        with self.patches()[2], self.patches()[3]:
            resumed = writer.resume_git_backup(
                prepared,
                reviewer_claim="person:local-operator",
                approval_id=approval_id,
                key_provider=_KeyProvider(),
            )
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(self.git(self.root, "rev-parse", "HEAD").stdout.strip(), committed_head)
        self.assertEqual(
            self.git(
                self.root,
                "rev-list",
                "--count",
                f"{self.initial_head}..HEAD",
            ).stdout.strip(),
            "1",
        )
        self.assert_remote_matches_head()

    def test_push_after_crash_is_requeried_and_resume_does_not_push_twice(self) -> None:
        prepared = self.plan_and_prepare()
        push_calls = 0

        def push_then_lose_result(command, **kwargs):
            nonlocal push_calls
            push_calls += 1
            result = self.transport_runner(command, **kwargs)
            self.assertEqual(result[0], 0)
            return 1, b""

        with (
            patch.object(
                planning,
                "_run_transport_capped",
                side_effect=push_then_lose_result,
            ),
            self.patches()[3],
        ):
            with self.assertRaises(ExactHumanApprovalWorkflowError):
                writer.execute_git_backup(
                    prepared,
                    selection_manifest_path=self.selection_path,
                    reviewer_claim="person:local-operator",
                    native=_Native(),
                    key_provider=_KeyProvider(),
                )
        self.assertEqual(push_calls, 1)
        pushed_head = self.assert_remote_matches_head()
        approval_id = self.only_claim_id()
        with self.patches()[2], self.patches()[3]:
            resumed = writer.resume_git_backup(
                prepared,
                reviewer_claim="person:local-operator",
                approval_id=approval_id,
                key_provider=_KeyProvider(),
            )
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(self.assert_remote_matches_head(), pushed_head)
        self.assertEqual(push_calls, 1)

    def test_selection_drift_after_native_decision_blocks_all_git_writes(self) -> None:
        prepared = self.plan_and_prepare()

        def drift() -> None:
            self.selection_path.write_text("{}\n", encoding="utf-8")

        with self.patches()[2], self.patches()[3]:
            with self.assertRaises(ExactHumanApprovalWorkflowError) as blocked:
                writer.execute_git_backup(
                    prepared,
                    selection_manifest_path=self.selection_path,
                    reviewer_claim="person:local-operator",
                    native=_Native(drift),
                    key_provider=_KeyProvider(),
                )
        self.assertEqual(blocked.exception.code, "exact_human_approval_state_unknown")
        self.assertEqual(self.git(self.root, "rev-parse", "HEAD").stdout.strip(), self.initial_head)
        self.assertEqual(
            self.remote_observer(self.root, "origin", "refs/heads/main"),
            ("present", self.initial_head),
        )

    def test_worktree_drift_after_native_decision_blocks_before_exact_add(self) -> None:
        prepared = self.plan_and_prepare()

        def drift() -> None:
            (self.root / "tracked.txt").write_text(
                "changed after approval\n",
                encoding="utf-8",
            )

        git_commands: list[list[str]] = []
        original_git_raw = writer._GitBackupBackend._git_raw

        def recording_git_raw(backend, args, **kwargs):
            git_commands.append(list(args))
            return original_git_raw(backend, args, **kwargs)

        with (
            self.patches()[2],
            self.patches()[3],
            patch.object(
                writer._GitBackupBackend,
                "_git_raw",
                new=recording_git_raw,
            ),
        ):
            with self.assertRaises(ExactHumanApprovalWorkflowError) as blocked:
                writer.execute_git_backup(
                    prepared,
                    selection_manifest_path=self.selection_path,
                    reviewer_claim="person:local-operator",
                    native=_Native(drift),
                    key_provider=_KeyProvider(),
                )
        self.assertEqual(blocked.exception.code, "exact_human_approval_state_unknown")
        self.assertFalse([command for command in git_commands if "add" in command])
        self.assertEqual(self.git(self.root, "rev-parse", "HEAD").stdout.strip(), self.initial_head)
        self.assertEqual(
            self.remote_observer(self.root, "origin", "refs/heads/main"),
            ("present", self.initial_head),
        )

    def test_new_unclassified_change_after_approval_blocks_before_exact_add(self) -> None:
        prepared = self.plan_and_prepare()

        def drift() -> None:
            (self.root / "late-unclassified.txt").write_text(
                "not in the reviewed selection\n",
                encoding="utf-8",
            )

        git_commands: list[list[str]] = []
        original_git_raw = writer._GitBackupBackend._git_raw

        def recording_git_raw(backend, args, **kwargs):
            git_commands.append(list(args))
            return original_git_raw(backend, args, **kwargs)

        with (
            self.patches()[2],
            self.patches()[3],
            patch.object(
                writer._GitBackupBackend,
                "_git_raw",
                new=recording_git_raw,
            ),
        ):
            with self.assertRaises(ExactHumanApprovalWorkflowError):
                writer.execute_git_backup(
                    prepared,
                    selection_manifest_path=self.selection_path,
                    reviewer_claim="person:local-operator",
                    native=_Native(drift),
                    key_provider=_KeyProvider(),
                )
        self.assertFalse([command for command in git_commands if "add" in command])
        self.assertEqual(self.git(self.root, "rev-parse", "HEAD").stdout.strip(), self.initial_head)
        self.assertEqual(
            self.remote_observer(self.root, "origin", "refs/heads/main"),
            ("present", self.initial_head),
        )

    def test_new_unclassified_change_after_commit_blocks_before_push(self) -> None:
        prepared = self.plan_and_prepare()
        original_commit = writer._GitBackupBackend._commit_group

        def create_late_change(backend, group):
            original_commit(backend, group)
            (self.root / "late-after-commit.txt").write_text(
                "must not ride with the reviewed backup\n",
                encoding="utf-8",
            )
            backend.invalidate()

        with (
            self.patches()[2],
            self.patches()[3],
            patch.object(
                writer._GitBackupBackend,
                "_commit_group",
                new=create_late_change,
            ),
        ):
            with self.assertRaises(ExactHumanApprovalWorkflowError):
                writer.execute_git_backup(
                    prepared,
                    selection_manifest_path=self.selection_path,
                    reviewer_claim="person:local-operator",
                    native=_Native(),
                    key_provider=_KeyProvider(),
                )
        self.assertNotEqual(self.git(self.root, "rev-parse", "HEAD").stdout.strip(), self.initial_head)
        self.assertEqual(self.transport_commands, [])
        self.assertEqual(
            self.remote_observer(self.root, "origin", "refs/heads/main"),
            ("present", self.initial_head),
        )

    def test_remote_race_blocks_before_push_without_force(self) -> None:
        prepared = self.plan_and_prepare()
        attacker = self.root.parent / "attacker"
        self.git(
            self.root.parent,
            "clone",
            "--branch",
            "main",
            str(self.remote),
            str(attacker),
        )
        self.git(attacker, "config", "user.name", "remote-racer")
        self.git(attacker, "config", "user.email", "remote-racer@example.invalid")
        observation_count = 0
        raced_oid: str | None = None

        def race_observer(selected: writer.PreparedGitBackup):
            nonlocal observation_count, raced_oid
            observation_count += 1
            if observation_count == 2:
                (attacker / "raced.txt").write_text("remote race\n", encoding="utf-8")
                self.git(attacker, "add", "--", "raced.txt")
                self.git(attacker, "commit", "-m", "advance remote")
                self.git(attacker, "push", "origin", "HEAD:refs/heads/main")
                raced_oid = self.git(attacker, "rev-parse", "HEAD").stdout.strip()
            return self.remote_observer(
                selected.root,
                selected.remote_name,
                selected.target_ref,
            )

        push_attempts: list[list[str]] = []

        def unexpected_push(command, **_kwargs):
            push_attempts.append(list(command))
            return 1, b""

        with (
            patch.object(
                writer,
                "_query_exact_remote_ref_with_stored_credentials",
                side_effect=race_observer,
            ),
            patch.object(
                planning,
                "_run_transport_capped",
                side_effect=unexpected_push,
            ),
        ):
            with self.assertRaises(ExactHumanApprovalWorkflowError):
                writer.execute_git_backup(
                    prepared,
                    selection_manifest_path=self.selection_path,
                    reviewer_claim="person:local-operator",
                    native=_Native(),
                    key_provider=_KeyProvider(),
                )
        self.assertIsNotNone(raced_oid)
        self.assertFalse(push_attempts)
        self.assertNotEqual(self.git(self.root, "rev-parse", "HEAD").stdout.strip(), self.initial_head)
        self.assertEqual(
            self.remote_observer(self.root, "origin", "refs/heads/main"),
            ("present", raced_oid),
        )

    def test_pre_staged_later_group_is_preserved_by_first_exact_commit(self) -> None:
        from wom_kit.exact_operation_manifest import ExactOperationManifestError

        self.git(self.root, "add", "--", "tracked.txt")
        prepared = self.plan_and_prepare(group_count=2)
        first_finished = False
        original_commit = writer._GitBackupBackend._commit_group
        original_apply = writer._apply_prepared_with_claim
        stage = "before_first_group"
        observed_failure: tuple[str, str] | None = None

        # The CI-only failure is not reproduced locally. Preserve a fixed-code
        # observation across the generic approval wrapper without changing the
        # real writer's call, result, exception, or retry behavior.
        def observe_failure(error: Exception) -> None:
            nonlocal observed_failure
            if observed_failure is not None:
                return
            code = "unclassified_failure"
            for error_type in (writer.GitBackupWriterError, ExactOperationManifestError):
                if type(error) is error_type:
                    candidate = error.code
                    if type(candidate) is str and candidate in error_type._CODES:
                        code = candidate
                    break
            observed_failure = (stage, code)

        def observe_apply(*args, **kwargs):
            try:
                return original_apply(*args, **kwargs)
            except Exception as error:
                observe_failure(error)
                raise

        def observe_between_groups(backend, group):
            nonlocal first_finished, stage
            stage = "first_group_commit" if group.ordinal == 0 else "later_group_commit"
            try:
                original_commit(backend, group)
            except Exception as error:
                observe_failure(error)
                raise
            if group.ordinal == 0:
                stage = "between_groups_assertion"
                first_finished = True
                staged = tuple(
                    self.git(self.root, "diff", "--cached", "--name-only")
                    .stdout.splitlines()
                )
                self.assertEqual(staged, prepared.groups[1].paths)
                stage = "after_first_group"
            else:
                stage = "after_later_group"

        with (
            self.patches()[2],
            self.patches()[3],
            patch.object(writer, "_apply_prepared_with_claim", new=observe_apply),
            patch.object(
                writer._GitBackupBackend,
                "_commit_group",
                new=observe_between_groups,
            ),
        ):
            try:
                result = writer.execute_git_backup(
                    prepared,
                    selection_manifest_path=self.selection_path,
                    reviewer_claim="person:local-operator",
                    native=_Native(),
                    key_provider=_KeyProvider(),
                )
            except ExactHumanApprovalWorkflowError:
                failure_stage, failure_code = observed_failure or (
                    "outside_observed_apply", "not_observed"
                )
                raise AssertionError(
                    "git_backup_fixture_failure: "
                    f"stage={failure_stage}; code={failure_code}"
                ) from None
        self.assertTrue(result["ok"], result)
        self.assertTrue(first_finished)
        self.assertEqual(
            self.git(
                self.root,
                "rev-list",
                "--count",
                f"{self.initial_head}..HEAD",
            ).stdout.strip(),
            "2",
        )
        self.assert_remote_matches_head()

    def test_8192_changes_split_into_bounded_explicit_complete_groups(self) -> None:
        expected_plan = "sha256:" + "1" * 64
        digest = "sha256:" + "2" * 64
        rows: list[dict[str, object]] = []
        for ordinal in range(8192):
            path = f"bulk/item-{ordinal:04d}.txt"
            rows.append(
                {
                    "path": path,
                    "worktree_identity": [1, ordinal + 1, 1, 1, 1],
                    "public_observation": {
                        "change_ref": f"change:{ordinal + 1:06d}",
                        "worktree": {
                            "state": "regular_file",
                            "bytes": 1,
                            "sha256": digest,
                        },
                    },
                }
            )

        chunks: list[list[dict[str, object]]] = []
        pending: list[dict[str, object]] = []
        for row in rows:
            candidate = [*pending, row]
            paths = [str(value["path"]) for value in candidate]
            if pending and not writer._literal_path_argv_is_bounded(paths):
                chunks.append(pending)
                pending = [row]
            else:
                pending = candidate
        chunks.append(pending)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(
            all(
                writer._literal_path_argv_is_bounded(
                    [str(row["path"]) for row in chunk]
                )
                for chunk in chunks
            )
        )
        self.assertFalse(
            writer._literal_path_argv_is_bounded(
                [str(row["path"]) for row in rows]
            )
        )
        groups = [
            {
                "group_id": f"group:bulk-{ordinal + 1}",
                "change_refs": [
                    row["public_observation"]["change_ref"]  # type: ignore[index]
                    for row in chunk
                ],
                "commit_subject": f"Back up reviewed bulk group {ordinal + 1}",
            }
            for ordinal, chunk in enumerate(chunks)
        ]
        self.selection_path.write_text(
            json.dumps(
                {
                    "schema": writer.GIT_BACKUP_SELECTION_SCHEMA,
                    "expected_plan_sha256": expected_plan,
                    "groups": groups,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        def fake_plan(_archive_root, **options):
            capture = options["_private_capture"]
            capture.update(
                {
                    "root": self.root,
                    "archive_id": "archive:personal:git-writer-fixture",
                    "remote_name": "origin",
                    "credential_mode": "stored",
                    "remote_url": "https://example.invalid/private/repository.git",
                    "target_ref": "refs/heads/main",
                    "local_head_oid": self.initial_head,
                    "remote_state": "present",
                    "remote_oid": self.initial_head,
                    "private_changes": rows,
                    "git_executable_sha256": digest,
                    "git_config_trust_sha256": digest,
                }
            )
            return {
                "ok": True,
                "plan_sha256": expected_plan,
                "repository": {"relation": {"state": "equal"}},
            }

        with patch.object(planning, "git_backup_plan", side_effect=fake_plan):
            prepared = writer.prepare_git_backup(
                self.root,
                expected_plan_sha256=expected_plan,
                selection_manifest_path=self.selection_path,
                credential_mode="stored",
            )
        self.assertEqual(len(prepared.groups), len(chunks))
        self.assertEqual(
            sum(len(group.change_refs) for group in prepared.groups),
            8192,
        )
        self.assertEqual(
            len({reference for group in prepared.groups for reference in group.change_refs}),
            8192,
        )
        with patch.object(planning, "git_backup_plan", side_effect=fake_plan):
            repeated = writer.prepare_git_backup(
                self.root,
                expected_plan_sha256=expected_plan,
                selection_manifest_path=self.selection_path,
                credential_mode="stored",
            )
        self.assertEqual(repeated.public_plan(), prepared.public_plan())
        self.assertEqual(repeated.manifest.document(), prepared.manifest.document())

        incomplete = {
            "schema": writer.GIT_BACKUP_SELECTION_SCHEMA,
            "expected_plan_sha256": expected_plan,
            "groups": [
                {
                    "group_id": "group:missing-one",
                    "change_refs": ["change:000001"],
                    "commit_subject": "Back up incomplete group",
                }
            ],
        }
        with self.assertRaises(writer.GitBackupWriterError) as missing:
            writer._selection_groups(
                incomplete,
                expected_plan_sha256=expected_plan,
                observed_change_refs=("change:000001", "change:000002"),
            )
        self.assertEqual(missing.exception.code, "git_backup_selection_incomplete")

        giant = {
            "schema": writer.GIT_BACKUP_SELECTION_SCHEMA,
            "expected_plan_sha256": expected_plan,
            "groups": [
                {
                    "group_id": "group:too-large",
                    "change_refs": [
                        row["public_observation"]["change_ref"]  # type: ignore[index]
                        for row in rows
                    ],
                    "commit_subject": "Back up oversized group",
                }
            ],
        }
        self.selection_path.write_text(
            json.dumps(giant, sort_keys=True),
            encoding="utf-8",
        )
        with patch.object(planning, "git_backup_plan", side_effect=fake_plan):
            with self.assertRaises(writer.GitBackupWriterError) as oversized:
                writer.prepare_git_backup(
                    self.root,
                    expected_plan_sha256=expected_plan,
                    selection_manifest_path=self.selection_path,
                    credential_mode="stored",
                )
        self.assertEqual(oversized.exception.code, "git_backup_selection_invalid")


if __name__ == "__main__":
    unittest.main()
