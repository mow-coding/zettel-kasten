"""v0.4.32 — beta letter 164: the finalize scan, the permission preview and the probe failure kinds."""
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
from unittest import mock

from wom_kit import archive_services
from wom_kit import exact_approval_claims as claims
from wom_kit import git_backup_attention as attention_module
from wom_kit import git_backup_plan
from wom_kit import work_session_command
from wom_kit import work_session_service
from wom_kit import work_session_command_modes


KIT_ROOT = Path(__file__).resolve().parents[1]
CLIENT_APP_REF = "client_app_" + "1" * 32
TASK_ROUTE_REF = "task_route_" + "2" * 32
WORK_SESSION_REF = "work_session_" + "3" * 32


class V0432ProbeFailureKindTests(unittest.TestCase):
    """Letter 164 ⑤: an unavailable git probe says which probe and which fixed kind."""

    def setUp(self) -> None:
        archive_services._wom_kit_git_take_failure()
        self.addCleanup(archive_services._wom_kit_git_take_failure)

    def test_failure_kinds_are_a_fixed_vocabulary(self) -> None:
        self.assertEqual(
            sorted(archive_services._WOM_KIT_GIT_FAILURE_KINDS),
            [
                "argument_invalid",
                "launch_failed",
                "output_cap_exceeded",
                "probe_budget_exhausted",
                "stdin_write_failed",
                "stream_read_failed",
                "stream_unavailable",
                "timeout",
            ],
        )
        archive_services._wom_kit_git_note_failure("PRIVATE-KIND-CANARY")
        self.assertEqual(archive_services._wom_kit_git_take_failure(), "launch_failed")
        self.assertIsNone(archive_services._wom_kit_git_take_failure())

    def test_run_capped_notes_argument_launch_timeout_and_cap_kinds(self) -> None:
        environment = os.environ.copy()
        self.assertIsNone(
            archive_services._wom_kit_project_update_run_capped(
                [sys.executable, "-c", "pass"],
                environment=environment,
                timeout_seconds=0,
                max_output_bytes=16,
            )
        )
        self.assertEqual(archive_services._wom_kit_git_take_failure(), "argument_invalid")
        self.assertIsNone(
            archive_services._wom_kit_project_update_run_capped(
                [str(Path(tempfile.gettempdir()) / "wom-kit-no-such-executable-5f2a")],
                environment=environment,
                timeout_seconds=5,
                max_output_bytes=16,
            )
        )
        self.assertEqual(archive_services._wom_kit_git_take_failure(), "launch_failed")
        self.assertIsNone(
            archive_services._wom_kit_project_update_run_capped(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                environment=environment,
                timeout_seconds=0.5,
                max_output_bytes=16,
            )
        )
        self.assertEqual(archive_services._wom_kit_git_take_failure(), "timeout")
        self.assertIsNone(
            archive_services._wom_kit_project_update_run_capped(
                [sys.executable, "-c", "import sys; sys.stdout.write('x' * 4096)"],
                environment=environment,
                timeout_seconds=10,
                max_output_bytes=16,
            )
        )
        self.assertEqual(archive_services._wom_kit_git_take_failure(), "output_cap_exceeded")
        # a completed run leaves no kind behind
        self.assertEqual(
            archive_services._wom_kit_project_update_run_capped(
                [sys.executable, "-c", "print('ok', end='')"],
                environment=environment,
                timeout_seconds=10,
                max_output_bytes=16,
            ),
            (0, b"ok"),
        )
        self.assertIsNone(archive_services._wom_kit_git_take_failure())

    def _observation_with(self, side_effect):
        symbolic = {"state": "passed", "reason_code": "verified", "head_state": "detached", "branch": None}
        with mock.patch.object(
            archive_services, "wom_kit_project_update_symbolic_head_observation", return_value=symbolic
        ), mock.patch.object(
            archive_services, "_wom_kit_project_update_run_capped", side_effect=side_effect
        ), mock.patch.object(
            archive_services, "wom_kit_project_update_git_command", return_value=["git"]
        ), mock.patch.object(
            archive_services, "wom_kit_project_update_git_environment", return_value={}
        ):
            return archive_services._wom_kit_project_update_git_snapshot_observation(
                Path("ignored"), runner=object()
            )

    def test_snapshot_observation_names_the_failed_probe_and_kind(self) -> None:
        def timed_out(*args, **kwargs):
            archive_services._wom_kit_git_note_failure("timeout")
            return None

        result = self._observation_with(timed_out)
        self.assertEqual(result["state"], "unavailable")
        self.assertIsNone(result["snapshot"])
        self.assertEqual(
            result["probes"][0],
            {"probe": "rev-parse", "available": False, "return_code": None, "failure_kind": "timeout"},
        )
        # every probe the observation ran is recorded, each with its own kind
        self.assertGreaterEqual(len(result["probes"]), 1)
        self.assertEqual({record["failure_kind"] for record in result["probes"]}, {"timeout"})
        self.assertEqual({record["available"] for record in result["probes"]}, {False})
        self.assertEqual(
            set(result["probes"][0]), {"probe", "available", "return_code", "failure_kind"}
        )
        self.assertNotIn("output", json.dumps(result["probes"]))

    def test_snapshot_observation_records_exit_codes_without_output(self) -> None:
        result = self._observation_with(lambda *args, **kwargs: (128, b"fatal: PRIVATE-OUTPUT-CANARY"))
        self.assertEqual(result["state"], "failed")
        self.assertEqual(result["probes"][0]["probe"], "rev-parse")
        self.assertTrue(result["probes"][0]["available"])
        self.assertEqual(result["probes"][0]["return_code"], 128)
        self.assertIsNone(result["probes"][0]["failure_kind"])
        self.assertNotIn("PRIVATE-OUTPUT-CANARY", json.dumps(result))

    def test_exhausted_probe_budget_is_its_own_kind(self) -> None:
        budget_local = archive_services._WOM_KIT_GIT_PROBE_BUDGET_LOCAL
        budget_local.state = {
            "deadline": time.monotonic() - 1.0,
            "exhausted": False,
            "git_calls_skipped": 0,
            "git_calls_started": 0,
        }
        try:
            result = self._observation_with(lambda *args, **kwargs: (0, b"unreachable"))
        finally:
            budget_local.state = None
        self.assertEqual(result["state"], "unavailable")
        self.assertEqual(result["probes"][0]["failure_kind"], "probe_budget_exhausted")
        self.assertFalse(result["probes"][0]["available"])


class V0432PermissionPreviewTests(unittest.TestCase):
    """Letter 164 ⑦: --action set-permission-mode --dry-run previews the grant without a dialog."""

    def test_mode_selection_is_read_only(self) -> None:
        mode = work_session_command_modes.resolve_work_session_mode(
            action="set-permission-mode", dry_run=True,
        )
        self.assertTrue(mode["available"], mode)
        self.assertEqual(mode["mode"], "permission_mode_preview")
        self.assertTrue(mode["read_only"])
        self.assertFalse(mode["potential_write"])
        self.assertFalse(mode["native_approval_required"])
        for flag in ("approve", "apply", "resume", "review_original"):
            refused = work_session_command_modes.resolve_work_session_mode(
                action="set-permission-mode", dry_run=True, **{flag: True},
            )
            self.assertFalse(refused["available"], flag)

    def _archive(self, tmp: str) -> Path:
        root = Path(tmp) / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", root)
        return root

    def test_preview_returns_names_and_would_set_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._archive(tmp)
            before = sorted(p.as_posix() for p in root.rglob("*"))
            result = work_session_service.preview_permission_mode(
                root,
                client_app_ref=CLIENT_APP_REF,
                task_route_ref=TASK_ROUTE_REF,
                work_session_ref=WORK_SESSION_REF,
                permission_mode="limited",
                operations=["create_draft"],
            )
            after = sorted(p.as_posix() for p in root.rglob("*"))
        self.assertEqual(before, after)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["schema"], "wom-kit/work-session-permission-preview/v1")
        self.assertTrue(result["dry_run"])
        self.assertTrue(result["read_only"])
        self.assertFalse(result["session_state_read"])
        self.assertTrue(result["native_approval_required_for_write"])
        self.assertEqual(result["would_set"], {"mode": "limited", "operations": ["create_draft"]})
        self.assertIn("create_draft", result["grantable_operations"])
        self.assertEqual(result["always_dialog_operations"], [])  # v0.4.36 (letter 168 ⑥)
        self.assertEqual(result["dialog_only_actions"], ["set-permission-mode"])
        from wom_kit.exact_human_approval_windows import ExactHumanApprovalOperation
        self.assertEqual(len(result["grantable_operations"]), len(ExactHumanApprovalOperation))
        self.assertEqual(result["permission_modes"], ["manual", "limited", "allow_all"])

    def test_preview_names_the_refusal_without_a_dialog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = work_session_service.preview_permission_mode(
                self._archive(tmp),
                client_app_ref=CLIENT_APP_REF,
                task_route_ref=TASK_ROUTE_REF,
                work_session_ref=WORK_SESSION_REF,
                permission_mode="limited",
                operations=["PRIVATE-OP-CANARY"],
            )
        self.assertFalse(result["ok"])
        self.assertTrue(result["reason_code"])
        self.assertIn("grantable_operations", result)
        self.assertNotIn("PRIVATE-OP-CANARY", json.dumps({k: v for k, v in result.items() if k != "reason_detail"}))


class V0432ClaimScanTests(unittest.TestCase):
    """Letter 164 ②: the finalize receipt scan streams bytes and only real failures block."""

    def test_byte_scanner_finds_ids_across_chunk_boundaries(self) -> None:
        approval_id = "approval_" + "ab" * 16
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "big.json"
            prefix = b"{" + b" " * (claims._EVIDENCE_CHUNK_BYTES - 10)
            path.write_bytes(prefix + approval_id.encode("ascii") + b"}")
            found = claims._scan_file_for_approval_ids(path, {approval_id})
            other = claims._scan_file_for_approval_ids(path, {"approval_" + "cd" * 16})
        self.assertEqual(found, {approval_id})
        self.assertEqual(other, set())

    def test_ceiling_is_generous_and_named(self) -> None:
        self.assertGreaterEqual(claims._MAX_EVIDENCE_FILE_BYTES, 64 * 1024 * 1024)
        self.assertGreaterEqual(claims._MAX_EVIDENCE_FILES, 100_000)
        self.assertGreaterEqual(claims._EVIDENCE_OVERLAP_BYTES, len("approval_") + 32)


class V0432GitBackupAttentionTests(unittest.TestCase):
    """Letter 164 ⑥: session start, backup evidence and work-session create say what Git does not hold."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.root = self.tmp / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", self.root)

    def git(self, *arguments: str) -> None:
        subprocess.run(
            ["git", "-C", str(self.root), *arguments],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

    def init_repository(self) -> None:
        self.git("init", "-q")
        self.git("config", "user.email", "wom-test@example.invalid")
        self.git("config", "user.name", "WOM Test")
        self.git("config", "core.autocrlf", "false")

    def assert_private_free(self, block: dict) -> None:
        text = json.dumps(block)
        for private in (str(self.tmp), "remote-mirror", "origin", "private-branch", "archive.yml", "inbox/"):
            self.assertNotIn(private, text)
        self.assertEqual(set(block), attention_module.GIT_BACKUP_ATTENTION_KEYS)
        self.assertFalse(block["network_checked"])
        self.assertFalse(block["remote_state_is_proof"])
        self.assertFalse(block["paths_branches_or_messages_echoed"])

    def test_status_records_are_counted_not_kept(self) -> None:
        raw = b"?? inbox/new.md\0 M archive.yml\0R  new.md\0old.md\0A  zets/x.md\0"
        self.assertEqual(attention_module._count_status_records(raw), (4, 1, 3))
        self.assertEqual(attention_module._count_status_records(b""), (0, 0, 0))
        self.assertIsNone(attention_module._count_status_records(b"R  only-new\0"))
        self.assertIsNone(attention_module._count_status_records(b"garbage"))

    def test_not_a_repository_is_calm_and_git_unavailable_is_quiet(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is required")
        block = attention_module.git_backup_attention(self.root)
        self.assertEqual(block["state"], "not_a_repository")
        self.assertTrue(block["repository_inspected"])
        self.assertFalse(block["review_recommended"])
        self.assert_private_free(block)
        with mock.patch.object(git_backup_plan, "_pin_git_executable", return_value=None):
            missing = attention_module.git_backup_attention(self.root)
        self.assertEqual(missing["state"], "git_unavailable")
        self.assertFalse(missing["repository_inspected"])
        self.assertFalse(missing["review_recommended"])
        self.assert_private_free(missing)

    def test_counts_ages_and_push_gap_without_any_private_value(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is required")
        self.init_repository()
        unborn = attention_module.git_backup_attention(self.root)
        self.assertEqual(unborn["head_state"], "unborn")
        self.assertIn("head_unborn", unborn["attention"])
        self.assertIn("uncommitted_changes_present", unborn["attention"])
        self.assertGreater(unborn["uncommitted_change_count"], 0)
        self.git("checkout", "-q", "-b", "private-branch")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "first private subject")
        no_upstream = attention_module.git_backup_attention(self.root)
        self.assertEqual(no_upstream["uncommitted_change_count"], 0)
        self.assertEqual(no_upstream["upstream_state"], "missing")
        self.assertEqual(no_upstream["attention"], ["upstream_missing"])
        self.assertEqual(no_upstream["last_commit_age_days"], 0)
        remote = self.tmp / "remote-mirror.git"
        subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
        self.git("remote", "add", "origin", str(remote))
        self.git("push", "-q", "-u", "origin", "HEAD")
        (self.root / "inbox" / "new private note.md").write_text("x", encoding="utf-8")
        (self.root / "archive.yml").write_text(
            (self.root / "archive.yml").read_text(encoding="utf-8") + "\n# touched\n", encoding="utf-8"
        )
        dirty = attention_module.git_backup_attention(self.root)
        self.assertEqual(dirty["state"], "observed")
        self.assertEqual(dirty["repository_scope"], "archive_root")
        self.assertEqual(dirty["uncommitted_change_count"], 2)
        self.assertEqual(dirty["untracked_count"], 1)
        self.assertEqual(dirty["tracked_change_count"], 1)
        self.assertEqual(dirty["uncommitted_change_count_state"], "exact")
        self.assertEqual(dirty["upstream_state"], "tracked")
        self.assertEqual((dirty["ahead_count"], dirty["behind_count"]), (0, 0))
        self.assertEqual(dirty["remote_tip_age_days"], 0)
        self.assertEqual(dirty["attention"], ["uncommitted_changes_present"])
        self.assertTrue(dirty["review_recommended"])
        self.assertIn("2 uncommitted change(s)", dirty["human_summary"])
        self.assertEqual([p["probe"] for p in dirty["probes"]],
                         ["rev-parse", "log", "status", "rev-parse-upstream", "rev-list", "log-upstream"])
        self.assertTrue(all(p["available"] and p["failure_kind"] is None for p in dirty["probes"]))
        self.assert_private_free(dirty)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "second private subject")
        ahead = attention_module.git_backup_attention(self.root)
        self.assertEqual(ahead["ahead_count"], 1)
        self.assertEqual(ahead["attention"], ["commits_not_pushed"])
        self.assertIn("1 commit(s) not pushed", ahead["human_summary"])
        self.assert_private_free(ahead)
        # ages come from commit times, in whole days
        with mock.patch.object(attention_module.time, "time", return_value=time.time() + 30 * 86400):
            stale = attention_module.git_backup_attention(self.root)
        self.assertEqual(stale["last_commit_age_days"], 30)
        self.assertEqual(stale["remote_tip_age_days"], 30)
        self.assertEqual(
            stale["attention"],
            ["commits_not_pushed", "last_commit_older_than_7_days", "remote_tip_older_than_7_days"],
        )

    def test_probe_budget_exhaustion_degrades_with_its_kind(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is required")
        self.init_repository()
        with mock.patch.object(attention_module, "GIT_BACKUP_ATTENTION_BUDGET_SECONDS", 0.0):
            block = attention_module.git_backup_attention(self.root)
        self.assertEqual(block["state"], "unavailable")
        self.assertEqual(block["reason_code"], "git_repository_probe_unavailable")
        self.assertEqual(block["probes"][0]["failure_kind"], "probe_budget_exhausted")
        self.assertTrue(block["review_recommended"])
        self.assert_private_free(block)
        with mock.patch.object(attention_module, "git_backup_attention", side_effect=RuntimeError("PRIVATE-CANARY")):
            quiet = archive_services.write_result_git_backup_attention(self.root)
        self.assertEqual(quiet["state"], "unavailable")
        self.assertEqual(set(quiet), attention_module.GIT_BACKUP_ATTENTION_KEYS)
        self.assertNotIn("PRIVATE-CANARY", json.dumps(quiet))

    def test_start_here_evidence_and_work_session_carry_the_block(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is required")
        self.init_repository()
        result = archive_services.ai_start_here(self.root)
        block = result["git_backup_attention"]
        self.assertEqual(block["state"], "observed")
        self.assertEqual(result["summary"]["git_backup_attention_state"], "observed")
        self.assertEqual(result["summary"]["uncommitted_change_count"], block["uncommitted_change_count"])
        self.assertIn(block["human_summary"], result["warnings"])
        self.assertTrue(any("git-backup-plan" in step for step in result["next_safe_steps"]))
        self.assert_private_free(block)
        evidence = archive_services.backup_evidence_status(self.root)
        lane = evidence["lanes"]["github"]
        self.assertEqual(lane["status"], "unverified_no_generic_completion_receipt")
        self.assertTrue(lane["local_commit_inspected"])
        self.assertEqual(lane["local_repository_attention"]["state"], "observed")
        self.assertFalse(lane["remote_ref_checked"])
        self.assertFalse(lane["completion_claim_ready"])
        self.assertTrue(evidence["closed_actions"]["git_repository_inspected"])
        self.assertFalse(evidence["closed_actions"]["network_checked"])
        self.assertFalse(evidence["privacy_guards"]["git_paths_branches_or_messages_echoed"])
        self.assertIn(lane["local_repository_attention"]["human_summary"], evidence["warnings"])
        self.assertTrue(any("git-backup-plan" in action for action in evidence["next_safe_actions"]))
        from wom_kit import work_session_service

        with mock.patch.object(work_session_service, "create_task", return_value={"ok": True, "schema": "x"}):
            envelope = work_session_command.dispatch_work_session_management(
                self.root, action="create", approve=True, client_app_ref="app:x", task_route_ref="route:y",
                request={"label": "synthetic", "reviewer_claim": "person:synthetic-reviewer"},
            )
        self.assertTrue(envelope["ok"], envelope)
        self.assertEqual(set(envelope["git_backup_attention"]), attention_module.GIT_BACKUP_ATTENTION_KEYS)
        self.assertEqual(envelope["git_backup_attention"]["state"], "observed")


if __name__ == "__main__":
    unittest.main()
