from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import git_backup_plan as planner


class Letter139GitBackupPlanTests(unittest.TestCase):
    maxDiff = None

    @staticmethod
    def git(repository: Path, *args: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(repository), *args],
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    def create_repository(self, parent: Path) -> Path:
        root = parent / "private-archive-root"
        root.mkdir()
        self.git(root, "init", "-b", "main")
        self.git(root, "config", "user.name", "archive-test")
        self.git(root, "config", "user.email", "archive-test@example.invalid")
        (root / "archive.yml").write_text(
            "archive_id: archive:personal:private-fixture\n",
            encoding="utf-8",
        )
        (root / "tracked.txt").write_text("before bytes\n", encoding="utf-8")
        self.git(root, "add", "archive.yml", "tracked.txt")
        self.git(root, "commit", "-m", "fixture")
        self.git(
            root,
            "remote",
            "add",
            "origin",
            "https://example.invalid/private-owner/private-repository.git",
        )
        return root

    def fixed_handoff(self) -> dict[str, object]:
        return {
            "state_digest": "sha256:" + "a" * 64,
            "status": "current_verified",
            "ready_for_context_reset": True,
        }

    def plan_patches(self, root: Path):
        head = self.git(root, "rev-parse", "HEAD")
        return (
            patch.object(
                planner,
                "_query_remote_ref",
                return_value=("present", head),
            ),
            patch.object(
                planner,
                "_handoff_observation",
                return_value=self.fixed_handoff(),
            ),
        )

    def test_plan_is_stable_content_free_and_never_writes(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is required")
        with tempfile.TemporaryDirectory() as temporary:
            root = self.create_repository(Path(temporary))
            sensitive_path = root / "client-secret-filename-민감.txt"
            sensitive_body = "do-not-return-this-private-body"
            sensitive_path.write_text(sensitive_body, encoding="utf-8")
            (root / "tracked.txt").write_text("after bytes\n", encoding="utf-8")
            before_head = self.git(root, "rev-parse", "HEAD")
            before_status = subprocess.run(
                ["git", "-C", str(root), "status", "--porcelain=v2", "-z"],
                check=True,
                capture_output=True,
            ).stdout
            before_index = subprocess.run(
                ["git", "-C", str(root), "ls-files", "--stage", "-z"],
                check=True,
                capture_output=True,
            ).stdout
            remote_patch, handoff_patch = self.plan_patches(root)
            with remote_patch, handoff_patch:
                first = planner.git_backup_plan(root)
                second = planner.git_backup_plan(root)

            self.assertTrue(first["ok"], first)
            self.assertEqual(first["status"], "plan_ready")
            self.assertEqual(first["plan_sha256"], second["plan_sha256"])
            self.assertEqual(
                first["hidden_effect_set_sha256"],
                second["hidden_effect_set_sha256"],
            )
            self.assertEqual(
                [item["change_ref"] for item in first["changes"]],
                ["change:000001", "change:000002"],
            )
            self.assertFalse(first["ready_for_write"])
            self.assertFalse(first["writer_available"])
            self.assertEqual(first["would_change"], [])
            self.assertTrue(first["git_executable"]["stability_verified"])
            serialized = json.dumps(first, ensure_ascii=False)
            for private_value in (
                str(root),
                root.name,
                sensitive_path.name,
                sensitive_body,
                "archive:personal:private-fixture",
                "https://example.invalid/private-owner/private-repository.git",
            ):
                self.assertNotIn(private_value, serialized)
            self.assertEqual(self.git(root, "rev-parse", "HEAD"), before_head)
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(root), "status", "--porcelain=v2", "-z"],
                    check=True,
                    capture_output=True,
                ).stdout,
                before_status,
            )
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(root), "ls-files", "--stage", "-z"],
                    check=True,
                    capture_output=True,
                ).stdout,
                before_index,
            )

    def test_current_gitattributes_blocks_before_malicious_filter_executes(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is required")
        with tempfile.TemporaryDirectory() as temporary:
            root = self.create_repository(Path(temporary))
            sentinel = root / "filter-ran.sentinel"
            script = root / "malicious-filter.py"
            script.write_text(
                "from pathlib import Path\n"
                f"Path({str(sentinel)!r}).write_text('ran', encoding='utf-8')\n",
                encoding="utf-8",
            )
            (root / ".gitattributes").write_text(
                "*.txt filter=malicious\n",
                encoding="utf-8",
            )
            self.git(
                root,
                "config",
                "filter.malicious.clean",
                f'"{sys.executable}" "{script}"',
            )
            (root / "tracked.txt").write_text("would trigger\n", encoding="utf-8")
            result = planner.git_backup_plan(root)
            self.assertIn("repository_attributes_not_supported", result["blockers"])
            self.assertFalse(sentinel.exists())
            self.assertFalse(result["inspection_complete"])

    def test_deleted_tracked_gitattributes_blocks_before_filter_executes(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is required")
        with tempfile.TemporaryDirectory() as temporary:
            root = self.create_repository(Path(temporary))
            sentinel = root / "deleted-filter-ran.sentinel"
            script = root / "deleted-malicious-filter.py"
            script.write_text(
                "from pathlib import Path\n"
                f"Path({str(sentinel)!r}).write_text('ran', encoding='utf-8')\n",
                encoding="utf-8",
            )
            attributes = root / ".gitattributes"
            attributes.write_text("*.txt filter=malicious\n", encoding="utf-8")
            self.git(root, "add", ".gitattributes")
            self.git(root, "commit", "-m", "tracked attributes")
            attributes.unlink()
            self.git(
                root,
                "config",
                "filter.malicious.clean",
                f'"{sys.executable}" "{script}"',
            )
            (root / "tracked.txt").write_text("would trigger\n", encoding="utf-8")
            result = planner.git_backup_plan(root)
            self.assertIn(
                "tracked_repository_attributes_not_supported",
                result["blockers"],
            )
            self.assertFalse(sentinel.exists())

    def test_count_limit_stops_before_any_changed_or_receipt_body_hash(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is required")
        with tempfile.TemporaryDirectory() as temporary:
            root = self.create_repository(Path(temporary))
            (root / "tracked.txt").write_text("changed\n", encoding="utf-8")
            (root / "second.txt").write_text("second\n", encoding="utf-8")
            remote_patch, handoff_patch = self.plan_patches(root)
            with (
                remote_patch,
                handoff_patch,
                patch.object(
                    planner,
                    "_hash_stable_plain_file",
                    side_effect=AssertionError("body hash must not run"),
                ),
            ):
                result = planner.git_backup_plan(root, max_changes=1)
            self.assertIn("requested_changed_item_limit_exceeded", result["blockers"])

    def test_byte_limit_is_applied_before_file_body_read(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is required")
        with tempfile.TemporaryDirectory() as temporary:
            root = self.create_repository(Path(temporary))
            (root / "large-private.bin").write_bytes(b"x" * 64)
            observed_caps: list[int] = []
            real_hash = planner._hash_stable_plain_file

            def bounded_hash(root_arg: Path, path: Path, *, max_bytes: int):
                observed_caps.append(max_bytes)
                return real_hash(root_arg, path, max_bytes=max_bytes)

            remote_patch, handoff_patch = self.plan_patches(root)
            with (
                remote_patch,
                handoff_patch,
                patch.object(planner, "_hash_stable_plain_file", side_effect=bounded_hash),
            ):
                result = planner.git_backup_plan(root, max_changed_bytes=8)
            self.assertIn("requested_changed_bytes_limit_exceeded", result["blockers"])
            self.assertTrue(observed_caps)
            self.assertLessEqual(max(observed_caps), 8)

    def test_remote_missing_and_other_branch_are_fixed_blockers(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is required")
        with tempfile.TemporaryDirectory() as temporary:
            root = self.create_repository(Path(temporary))
            self.git(root, "branch", "other")
            with (
                patch.object(
                    planner,
                    "_query_remote_ref",
                    return_value=("target_ref_missing", None),
                ),
                patch.object(
                    planner,
                    "_handoff_observation",
                    return_value=self.fixed_handoff(),
                ),
            ):
                missing = planner.git_backup_plan(root)
                other = planner.git_backup_plan(root, branch="other")
            self.assertIn("remote_target_ref_missing", missing["blockers"])
            self.assertEqual(
                missing["repository"]["relation"]["state"],
                "remote_branch_missing",
            )
            self.assertIn("target_branch_not_checked_out", other["blockers"])
            self.assertEqual(
                other["repository"]["relation"]["state"],
                "not_computed",
            )

    def test_remote_config_drift_and_git_executable_drift_fail_closed(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is required")
        with tempfile.TemporaryDirectory() as temporary:
            root = self.create_repository(Path(temporary))
            head = self.git(root, "rev-parse", "HEAD")
            with (
                patch.object(
                    planner,
                    "_configured_remote_url",
                    side_effect=[
                        "https://example.invalid/one.git",
                        "https://example.invalid/two.git",
                    ],
                ),
                patch.object(
                    planner,
                    "_query_remote_ref",
                    return_value=("present", head),
                ) as remote_query,
                patch.object(
                    planner,
                    "_handoff_observation",
                    return_value=self.fixed_handoff(),
                ),
            ):
                drifted_remote = planner.git_backup_plan(root)
            self.assertIn(
                "configuration_drifted",
                drifted_remote["blockers"],
            )
            self.assertEqual(remote_query.call_count, 1)

            pinned = planner._pin_git_executable()
            self.assertIsNotNone(pinned)
            remote_patch, handoff_patch = self.plan_patches(root)
            with (
                remote_patch,
                handoff_patch,
                patch.object(planner, "_pin_git_executable", return_value=pinned),
                patch.object(planner, "_pin_git_at", return_value=None),
            ):
                drifted_git = planner.git_backup_plan(root)
            self.assertEqual(drifted_git["blockers"], ["git_executable_drifted"])

    def test_any_existing_git_lock_stops_before_remote_or_body_hash(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is required")
        for relative_lock in ("config.lock", "refs/heads/main.lock"):
            with self.subTest(relative_lock=relative_lock):
                with tempfile.TemporaryDirectory() as temporary:
                    root = self.create_repository(Path(temporary))
                    lock_path = root / ".git" / Path(relative_lock)
                    lock_path.parent.mkdir(parents=True, exist_ok=True)
                    lock_path.write_bytes(b"private lock bytes")
                    with (
                        patch.object(
                            planner,
                            "_query_remote_ref",
                            side_effect=AssertionError("remote must not run"),
                        ),
                        patch.object(
                            planner,
                            "_hash_stable_plain_file",
                            side_effect=AssertionError("body hash must not run"),
                        ),
                    ):
                        result = planner.git_backup_plan(root)
                    self.assertEqual(result["blockers"], ["git_lock_files_present"])
                    self.assertEqual(result["git_lock_evidence"]["count"], 1)
                    self.assertRegex(
                        result["git_lock_evidence"]["inventory_sha256"],
                        r"^sha256:[0-9a-f]{64}$",
                    )
                    self.assertNotIn(relative_lock, json.dumps(result))

    def test_wom_lock_and_git_operation_stop_before_all_active_observation(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is required")
        cases = (
            (
                ".zettel-kasten/git-backup.lock",
                "archive_git_backup_lock_present",
            ),
            (".git/MERGE_HEAD", "git_operation_or_lock_in_progress"),
            (".git/AUTO_MERGE", "git_operation_or_lock_in_progress"),
            (".git/MERGE_AUTOSTASH", "git_operation_or_lock_in_progress"),
            (".git/REBASE_HEAD", "git_operation_or_lock_in_progress"),
            (".git/BISECT_START", "git_operation_or_lock_in_progress"),
        )
        for relative_marker, expected_blocker in cases:
            with self.subTest(relative_marker=relative_marker):
                with tempfile.TemporaryDirectory() as temporary:
                    root = self.create_repository(Path(temporary))
                    marker_path = root / Path(relative_marker)
                    marker_path.parent.mkdir(parents=True, exist_ok=True)
                    marker_path.write_bytes(b"private marker bytes")
                    with (
                        patch.object(
                            planner,
                            "_local_git_raw",
                            side_effect=AssertionError(
                                "tracked attr/status must not run"
                            ),
                        ),
                        patch.object(
                            planner,
                            "_query_remote_ref",
                            side_effect=AssertionError("remote must not run"),
                        ),
                        patch.object(
                            planner,
                            "_handoff_observation",
                            side_effect=AssertionError("handoff must not run"),
                        ),
                        patch.object(
                            planner,
                            "_hash_stable_plain_file",
                            side_effect=AssertionError("body hash must not run"),
                        ),
                    ):
                        result = planner.git_backup_plan(root)
                    self.assertEqual(result["blockers"], [expected_blocker])
                    self.assertFalse(result["inspection_complete"])
                    self.assertFalse(result["closed_actions"]["network_checked"])
                    self.assertEqual(result["changes"], [])

    def test_blob_physical_memory_cap_fails_before_body_batch(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is required")
        with tempfile.TemporaryDirectory() as temporary:
            root = self.create_repository(Path(temporary))
            (root / "tracked.txt").write_text("changed\n", encoding="utf-8")
            remote_patch, handoff_patch = self.plan_patches(root)
            with (
                remote_patch,
                handoff_patch,
                patch.object(planner, "GIT_BACKUP_PLAN_MAX_BLOB_BATCH_BYTES", 1),
            ):
                result = planner.git_backup_plan(root)
            self.assertIn(
                "changed_git_blob_physical_read_limit_exceeded",
                result["blockers"],
            )

    def test_invalid_git_metadata_stops_before_any_git_or_archive_body_query(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is required")
        with tempfile.TemporaryDirectory() as temporary:
            root = self.create_repository(Path(temporary))
            git_config = root / ".git" / "config"
            git_config.unlink()
            git_config.mkdir()
            (git_config / "external-pointer").write_text(
                "must not be traversed by Git",
                encoding="utf-8",
            )
            with (
                patch.object(
                    planner,
                    "_local_git_raw",
                    side_effect=AssertionError("ls-files/status must not run"),
                ),
                patch.object(
                    planner,
                    "_query_remote_ref",
                    side_effect=AssertionError("remote must not run"),
                ),
                patch.object(
                    planner,
                    "_hash_stable_plain_file",
                    side_effect=AssertionError("body hash must not run"),
                ),
            ):
                result = planner.git_backup_plan(root)
            self.assertEqual(
                result["blockers"],
                ["git_metadata_boundary_not_local_or_real"],
            )

    def test_remote_transport_environment_is_neutral_and_write_free(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is required")
        pinned = planner._pin_git_executable()
        self.assertIsNotNone(pinned)
        assert pinned is not None
        captured: dict[str, object] = {}

        def fake_transport(command, *, environment, timeout_seconds, max_output_bytes):
            captured["command"] = command
            captured["environment"] = environment
            return 0, ("b" * 40 + "\trefs/heads/main\n").encode("ascii")

        token = planner._PINNED_GIT_EXECUTABLE.set(pinned)
        try:
            with (
                patch.dict(
                    os.environ,
                    {
                        "GIT_ASKPASS": "malicious-git-askpass",
                        "SSH_ASKPASS": "malicious-ssh-askpass",
                        "HTTPS_PROXY": "http://malicious-proxy.invalid",
                        "FTP_PROXY": "http://malicious-ftp-proxy.invalid",
                        "SSLKEYLOGFILE": str(Path(tempfile.gettempdir()) / "must-not-write"),
                    },
                    clear=False,
                ),
                patch.object(
                    planner,
                    "_run_transport_capped",
                    side_effect=fake_transport,
                ),
            ):
                state, oid = planner._query_remote_ref(
                    "https://example.invalid/repository.git",
                    "refs/heads/main",
                )
        finally:
            planner._PINNED_GIT_EXECUTABLE.reset(token)
        self.assertEqual(state, "present")
        self.assertEqual(oid, "b" * 40)
        environment = captured["environment"]
        command = captured["command"]
        assert isinstance(environment, dict)
        assert isinstance(command, list)
        upper_keys = {str(key).upper() for key in environment}
        self.assertNotIn("GIT_ASKPASS", upper_keys)
        self.assertNotIn("SSH_ASKPASS", upper_keys)
        self.assertNotIn("SSLKEYLOGFILE", upper_keys)
        self.assertFalse(any(key.endswith("_PROXY") for key in upper_keys))
        self.assertEqual(environment["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertIn("/dev/null", str(environment["GIT_CONFIG_GLOBAL"]).replace("\\", "/"))
        self.assertIn(".wom-git-backup-no-home-", environment["HOME"])
        self.assertIn("credential.helper=", command)
        self.assertIn("credential.interactive=never", command)
        self.assertEqual(command[0], pinned.path)

    def test_transport_parent_exit_immediately_terminates_stdout_child(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sentinel = Path(temporary) / "descendant-must-not-write.sentinel"
            child_code = (
                "import time\n"
                "from pathlib import Path\n"
                "time.sleep(0.35)\n"
                f"Path({str(sentinel)!r}).write_text('ran', encoding='utf-8')\n"
            )
            parent_code = (
                "import subprocess, sys\n"
                "subprocess.Popen("
                f"[sys.executable, '-c', {child_code!r}], "
                "stdout=sys.stdout, stderr=subprocess.DEVNULL)\n"
            )
            result = planner._run_transport_capped(
                [sys.executable, "-c", parent_code],
                environment=dict(os.environ),
                timeout_seconds=10,
                max_output_bytes=1024,
            )
            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result[0], 0)
            time.sleep(0.8)
            self.assertFalse(sentinel.exists())

    def test_reconcile_requires_exact_plan_and_optional_bindings(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is required")
        with tempfile.TemporaryDirectory() as temporary:
            root = self.create_repository(Path(temporary))
            (root / "tracked.txt").write_text("changed\n", encoding="utf-8")
            remote_patch, handoff_patch = self.plan_patches(root)
            with remote_patch, handoff_patch:
                plan = planner.git_backup_plan(root)
            remote_patch, handoff_patch = self.plan_patches(root)
            with remote_patch, handoff_patch:
                reconciled = planner.git_backup_reconcile_plan(
                    root,
                    expected_plan_sha256=plan["plan_sha256"],
                    expected_hidden_effect_set_sha256=plan[
                        "hidden_effect_set_sha256"
                    ],
                    expected_local_head_oid=plan["repository"]["local_head_oid"],
                    expected_remote_oid=plan["repository"]["remote_oid"],
                )
            self.assertTrue(reconciled["ok"], reconciled)
            self.assertEqual(reconciled["status"], "reconciled")
            self.assertTrue(
                all(value is True for value in reconciled["expected_bindings"].values())
            )
            remote_patch, handoff_patch = self.plan_patches(root)
            with remote_patch, handoff_patch:
                stale = planner.git_backup_reconcile_plan(
                    root,
                    expected_plan_sha256="sha256:" + "0" * 64,
                )
            self.assertIn("expected_plan_sha256_mismatch", stale["blockers"])
            self.assertFalse(stale["ready_for_write"])
            self.assertEqual(stale["would_change"], [])

    def test_machine_status_parser_handles_nul_framing_without_disclosure(self) -> None:
        parsed = planner._parse_status(b"? line\nname.txt\x00")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed[0].path, "line\nname.txt")
        self.assertIsNone(planner._parse_status(b"1 \xff N... 100644 100644 100644 " + b"0" * 120 + b" x\x00"))


if __name__ == "__main__":
    unittest.main()
