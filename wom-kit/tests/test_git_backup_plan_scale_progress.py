from __future__ import annotations

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


class GitBackupPlanScaleProgressTests(unittest.TestCase):
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
        root = parent / "archive"
        root.mkdir()
        self.git(root, "init", "-b", "main")
        self.git(root, "config", "user.name", "scale-test")
        self.git(root, "config", "user.email", "scale-test@example.invalid")
        (root / "archive.yml").write_text(
            "archive_id: archive:personal:scale-fixture\n",
            encoding="utf-8",
        )
        (root / ".gitignore").write_text("scratch/\n", encoding="utf-8")
        (root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        self.git(root, "add", "archive.yml", ".gitignore", "tracked.txt")
        self.git(root, "commit", "-m", "fixture")
        self.git(
            root,
            "remote",
            "add",
            "origin",
            "https://example.invalid/private/repository.git",
        )
        return root

    @staticmethod
    def fixed_handoff() -> dict[str, object]:
        return {
            "state_digest": "sha256:" + "a" * 64,
            "status": "current_verified",
            "ready_for_context_reset": True,
        }

    def test_ignored_40000_file_tree_finishes_with_hard_bound(self) -> None:
        """Regression for the former archive-wide scandir/lstat preflight."""

        if shutil.which("git") is None:
            self.skipTest("git is required")
        with tempfile.TemporaryDirectory() as temporary:
            root = self.create_repository(Path(temporary))
            scratch = root / "scratch"
            scratch.mkdir()
            for directory_ordinal in range(200):
                directory = scratch / f"part-{directory_ordinal:03d}"
                directory.mkdir()
                for file_ordinal in range(200):
                    (directory / f"item-{file_ordinal:03d}.tmp").touch()
            head = self.git(root, "rev-parse", "HEAD")
            events: list[tuple[float, dict[str, object]]] = []
            started = time.monotonic()
            with (
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
            ):
                result = planner.git_backup_plan(
                    root,
                    progress_hook=lambda event: events.append(
                        (time.monotonic(), dict(event))
                    ),
                )
            elapsed = time.monotonic() - started

            self.assertTrue(result["ok"], result)
            self.assertLess(elapsed, 20.0, f"large-tree plan took {elapsed:.3f}s")
            self.assertTrue(events)
            self.assertLess(events[0][0] - started, 2.0)
            self.assertEqual(events[0][1]["stage"], "starting")
            self.assertTrue(
                all(event["private_values_echoed"] is False for _, event in events)
            )

    def test_progress_heartbeats_while_one_stage_is_blocked(self) -> None:
        events: list[tuple[float, dict[str, object]]] = []
        started = time.monotonic()

        def slow_pin():
            time.sleep(5.3)
            return None

        with patch.object(planner, "_pin_git_executable", side_effect=slow_pin):
            result = planner.git_backup_plan(
                "PRIVATE_UNUSED_ROOT",
                progress_hook=lambda event: events.append(
                    (time.monotonic(), dict(event))
                ),
            )

        self.assertIn("git_executable_unavailable_or_unsafe", result["blockers"])
        self.assertLess(events[0][0] - started, 2.0)
        heartbeats = [row for row in events if row[1]["event"] == "heartbeat"]
        self.assertTrue(heartbeats, events)
        gaps = [
            later[0] - earlier[0]
            for earlier, later in zip(events, events[1:])
        ]
        self.assertLessEqual(max(gaps), 10.0)

    def test_receipt_inventory_is_metadata_only_and_cas_rechecked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "archive"
            receipts = root / "receipts" / "ops" / "bulk"
            receipts.mkdir(parents=True)
            for ordinal in range(2_000):
                (receipts / f"receipt-{ordinal:05d}.json").write_bytes(b"{}\n")

            with patch.object(
                planner,
                "_hash_stable_plain_file",
                side_effect=AssertionError("historical receipt bodies must not be read"),
            ):
                inventory, cache, blockers = planner._receipt_inventory(root)

            self.assertEqual(blockers, [])
            self.assertIsNotNone(cache)
            self.assertEqual(inventory.file_count, 2_000)
            self.assertEqual(inventory.total_bytes, 6_000)
            assert cache is not None
            self.assertEqual(planner._receipt_inventory_recheck(root, cache), [])
            (receipts / "receipt-00000.json").write_bytes(b'{"changed":true}\n')
            self.assertEqual(
                planner._receipt_inventory_recheck(root, cache),
                ["receipt_inventory_drifted"],
            )

    def test_git_backup_does_not_run_unrelated_session_handoff_inventory(self) -> None:
        with patch.object(
            planner.archive_services,
            "session_handoff_checkpoint",
            side_effect=AssertionError("unrelated scratch inventory must not run"),
        ):
            result = planner._handoff_observation(Path("PRIVATE_UNUSED_ROOT"))
        self.assertEqual(result["status"], "not_required_for_git_backup")
        self.assertFalse(result["ready_for_context_reset"])


if __name__ == "__main__":
    unittest.main()
