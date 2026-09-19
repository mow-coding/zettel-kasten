"""v0.4.32 — beta letter 164: the finalize scan, the permission preview and the probe failure kinds."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from wom_kit import archive_services
from wom_kit import exact_approval_claims as claims
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
        self.assertTrue(result["always_dialog_operations"])
        self.assertFalse(set(result["grantable_operations"]) & set(result["always_dialog_operations"]))
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


if __name__ == "__main__":
    unittest.main()
