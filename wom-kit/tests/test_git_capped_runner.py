from __future__ import annotations

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

from wom_kit import archive_services  # noqa: E402
from wom_kit import git_backup_plan  # noqa: E402


class GitCappedRunnerTests(unittest.TestCase):
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
        repository = parent / "source"
        repository.mkdir()
        self.git(repository, "init", "-b", "main")
        self.git(repository, "config", "user.name", "runner-test")
        self.git(
            repository,
            "config",
            "user.email",
            "runner-test@example.invalid",
        )
        (repository / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        self.git(repository, "add", "tracked.txt")
        self.git(repository, "commit", "-m", "fixture")
        return repository

    def test_capped_runner_duplexes_large_stdin_and_stdout(self) -> None:
        payload = (b"0123456789abcdef" * 32 * 1024)[:512 * 1024]
        child = (
            "import os, threading, time\n"
            "def watchdog():\n"
            "    time.sleep(4)\n"
            "    os._exit(91)\n"
            "threading.Thread(target=watchdog, daemon=True).start()\n"
            "while True:\n"
            "    chunk = os.read(0, 4096)\n"
            "    if not chunk:\n"
            "        break\n"
            "    os.write(1, chunk)\n"
        )
        started = time.monotonic()
        completed = archive_services._wom_kit_project_update_run_capped(
            [sys.executable, "-c", child],
            environment=os.environ.copy(),
            timeout_seconds=8,
            max_output_bytes=len(payload),
            input_bytes=payload,
        )
        elapsed = time.monotonic() - started

        self.assertEqual(completed, (0, payload))
        self.assertLess(elapsed, 4.0)

    def test_git_attribute_probe_handles_more_than_6500_paths(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is required")
        with tempfile.TemporaryDirectory() as temporary:
            repository = self.create_repository(Path(temporary))
            paths = [f"bulk/path-{index:05d}.md" for index in range(6501)]
            pinned = git_backup_plan._pin_git_executable()
            self.assertIsNotNone(pinned)
            token = git_backup_plan._PINNED_GIT_EXECUTABLE.set(pinned)
            try:
                started = time.monotonic()
                inert = git_backup_plan._changed_path_attributes_are_inert(
                    repository,
                    paths,
                )
                elapsed = time.monotonic() - started
            finally:
                git_backup_plan._PINNED_GIT_EXECUTABLE.reset(token)

        self.assertTrue(inert)
        self.assertLess(elapsed, 10.0)

    def test_version_and_source_match_paths_use_the_common_capped_runner(self) -> None:
        """Cover both archive-version tags and project source provenance."""

        if shutil.which("git") is None:
            self.skipTest("git is required")
        with tempfile.TemporaryDirectory() as temporary:
            project_root = Path(temporary) / "project"
            project_root.mkdir()
            mirror = self.create_repository(project_root)
            expected_snapshot = (
                archive_services._wom_kit_project_update_git_snapshot(mirror)
            )
            self.assertIsNotNone(expected_snapshot)
            real_runner = archive_services._wom_kit_project_update_run_capped
            with patch.object(
                archive_services,
                "_wom_kit_project_update_run_capped",
                wraps=real_runner,
            ) as capped_runner:
                head_lines = archive_services.git_output_lines(
                    mirror,
                    ["rev-parse", "HEAD"],
                )
                source_matches = (
                    archive_services.wom_kit_project_update_source_matches_snapshot(
                        project_root,
                        mirror,
                        expected_snapshot,
                    )
                )

            self.assertEqual(len(head_lines), 1)
            self.assertTrue(source_matches)
            self.assertGreater(capped_runner.call_count, 1)


if __name__ == "__main__":
    unittest.main()
