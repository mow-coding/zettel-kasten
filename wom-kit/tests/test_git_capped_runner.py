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
            with (
                archive_services.project_update_git_runner
                .TrustedProjectUpdateGitRunner.resolve_preapproval()
            ) as runner:
                runner.close_transport_boundary()
                expected_snapshot = (
                    archive_services._wom_kit_project_update_git_snapshot(
                        mirror,
                        runner=runner,
                    )
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
                with (
                    archive_services.project_update_git_runner
                    .TrustedProjectUpdateGitRunner.resolve_preapproval()
                ) as source_runner:
                    source_runner.close_transport_boundary()
                    source_matches = (
                        archive_services
                        .wom_kit_project_update_source_matches_snapshot(
                            project_root,
                            mirror,
                            expected_snapshot,
                            runner=source_runner,
                        )
                    )

            self.assertEqual(len(head_lines), 1)
            self.assertTrue(source_matches)
            self.assertGreater(capped_runner.call_count, 1)

    def test_attribute_probe_batches_large_unicode_path_inventory(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is required")
        # Synthetic paths need not exist for check-attr; retain long UTF-8 names.
        paths = [f"자료 정리/{'가나다' * 14}/item-{i:05d}.md" for i in range(11132)]
        self.assertGreater(len("\0".join(paths).encode("utf-8")), 1024 * 1024)
        with tempfile.TemporaryDirectory() as temporary:
            root = self.create_repository(Path(temporary))
            token = git_backup_plan._PINNED_GIT_EXECUTABLE.set(
                git_backup_plan._pin_git_executable()
            )
            try:
                with patch.object(
                    archive_services, "_wom_kit_project_update_run_capped",
                    wraps=archive_services._wom_kit_project_update_run_capped,
                ) as runner:
                    self.assertTrue(git_backup_plan._changed_path_attributes_are_inert(root, paths))
                self.assertGreater(runner.call_count, 1)
                self.assertTrue(all(len(call.kwargs["input_bytes"]) <= 1024 * 1024
                                    for call in runner.call_args_list))
                # An unsafe attribute in the last batch must still block.
                (root / ".gitattributes").write_text("*11131.md filter=unsafe\n", encoding="utf-8")
                self.assertFalse(git_backup_plan._changed_path_attributes_are_inert(root, paths))
            finally:
                git_backup_plan._PINNED_GIT_EXECUTABLE.reset(token)

    @patch.object(git_backup_plan, "_git_command", return_value=["git"])
    def test_attribute_probe_rejects_missing_duplicate_and_foreign_records(self, _command) -> None:
        good = b"a\0filter\0unspecified\0a\0working-tree-encoding\0unset\0"
        cases = [good[:-1], good.split(b"a\0working")[0],
                 good.replace(b"working-tree-encoding", b"filter"),
                 good.replace(b"a\0working", b"PRIVATE_PATH\0working"),
                 good.replace(b"unset", b"\xff")]
        for raw in cases:
            with self.subTest(raw=raw), patch.object(
                archive_services, "_wom_kit_project_update_run_capped", return_value=(0, raw)
            ):
                diagnostics = {}
                self.assertIsNone(git_backup_plan._changed_path_attributes_are_inert(
                    Path("."), ["a"], diagnostics=diagnostics))
                self.assertTrue(diagnostics["reason"].startswith("response_"))
                self.assertNotIn("PRIVATE_PATH", str(diagnostics))

    @patch.object(git_backup_plan, "_git_command", return_value=["git"])
    def test_attribute_probe_boundaries_and_fixed_failure_diagnostics(self, _command) -> None:
        def answer(command, **kwargs):
            rows = kwargs["input_bytes"].split(b"\0")[:-1]
            return (0, b"".join(path + b"\0" + attr + b"\0unspecified\0"
                               for path in rows for attr in (b"filter", b"working-tree-encoding")))
        with patch.object(git_backup_plan, "GIT_ATTRIBUTE_BATCH_MAX_BYTES", 6), patch.object(
            archive_services, "_wom_kit_project_update_run_capped", side_effect=answer,
        ) as runner:
            diagnostics = {}
            self.assertTrue(git_backup_plan._changed_path_attributes_are_inert(
                Path("."), ["abcde", "a", "가"], diagnostics=diagnostics))
            self.assertEqual(diagnostics["completed_batches"], 3)
            self.assertEqual(sorted(call.kwargs["input_bytes"] for call in runner.call_args_list),
                             [b"a\0", b"abcde\0", "가\0".encode()])

        for reason in ("timeout", "output_cap_exceeded", "launch_failed", "stdin_write_failed"):
            def failed(*args, **kwargs):
                archive_services._wom_kit_git_note_failure(reason)
                return None
            with self.subTest(reason=reason), patch.object(
                archive_services, "_wom_kit_project_update_run_capped", side_effect=failed,
            ):
                diagnostics = {}
                self.assertIsNone(git_backup_plan._changed_path_attributes_are_inert(
                    Path("."), ["private.txt"], diagnostics=diagnostics))
                self.assertEqual(diagnostics["reason"], reason)
                self.assertNotIn("private.txt", str(diagnostics))

    def test_empty_and_invalid_attribute_inputs_do_not_launch_git(self) -> None:
        with patch.object(archive_services, "_wom_kit_project_update_run_capped") as runner:
            self.assertTrue(git_backup_plan._changed_path_attributes_are_inert(Path("."), []))
            for path in ("", "bad\0path", "\ud800", "x" * (1024 * 1024)):
                diagnostics = {}
                self.assertIsNone(git_backup_plan._changed_path_attributes_are_inert(
                    Path("."), [path], diagnostics=diagnostics))
                self.assertIsNotNone(diagnostics["reason"])
            runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
