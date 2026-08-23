from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit.project_update_git_runner import (
    ProjectUpdateGitRunnerError,
    TrustedProjectUpdateGitRunner,
    load_private_binding_bytes,
)


class TrustedProjectUpdateGitRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def assert_code(self, expected: str, action) -> None:
        with self.assertRaises(ProjectUpdateGitRunnerError) as caught:
            action()
        self.assertEqual(caught.exception.code, expected)
        self.assertEqual(str(caught.exception), expected)

    def actual_git(self) -> Path:
        candidate = shutil.which("git")
        if candidate is None:
            self.skipTest("git executable unavailable")
        return Path(os.path.abspath(candidate))

    def dummy_git(self) -> Path:
        candidate = self.root / ("git.exe" if os.name == "nt" else "git")
        candidate.write_bytes(b"dummy trusted git executable\n")
        if os.name != "nt":
            candidate.chmod(0o700)
        return candidate

    def project_command(self, command: list[str]) -> list[str]:
        return [
            "--no-optional-locks",
            "-c",
            "core.fsmonitor=false",
            "-c",
            f"core.hooksPath={os.devnull}",
            "-c",
            f"core.attributesFile={os.devnull}",
            "-c",
            f"core.excludesFile={os.devnull}",
            "-C",
            str(self.root.resolve()),
            *command,
        ]

    def test_public_summary_and_argv_never_echo_or_re_resolve_path(self) -> None:
        runner = TrustedProjectUpdateGitRunner.resolve_preapproval(
            self.actual_git()
        )
        self.addCleanup(runner.close)
        private_path = runner.binding.executable_locator
        summary = runner.public_summary()
        self.assertNotIn(private_path, str(summary))
        with mock.patch.dict(os.environ, {"PATH": str(self.root)}, clear=False):
            argv = runner.command(["--version"])
        self.assertEqual(argv[0], private_path)
        self.assertTrue(Path(argv[0]).is_absolute())
        output = subprocess.run(
            argv,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
        self.assertIn("git version", output.casefold())

    def test_private_binding_reopens_exact_executable_without_path_lookup(self) -> None:
        first = TrustedProjectUpdateGitRunner.resolve_preapproval(
            self.actual_git()
        )
        raw = first.private_binding_bytes()
        expected = load_private_binding_bytes(raw)
        first.close()
        with mock.patch("shutil.which", side_effect=AssertionError("PATH used")):
            reopened = TrustedProjectUpdateGitRunner.reopen_private(expected)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.binding, expected)

    def test_transport_boundary_is_one_way_and_local_commands_reject_transport(self) -> None:
        runner = TrustedProjectUpdateGitRunner.resolve_preapproval(
            self.actual_git()
        )
        self.addCleanup(runner.close)
        self.assertEqual(
            runner.command(
                self.project_command(["fetch", "origin"]), transport=True
            )[0],
            runner.binding.executable_locator,
        )
        runner.close_transport_boundary()
        self.assert_code(
            "project_update_git_runner_phase_invalid",
            lambda: runner.command(
                self.project_command(["fetch", "origin"]), transport=True
            ),
        )
        self.assert_code(
            "project_update_git_runner_command_invalid",
            lambda: runner.command(self.project_command(["fetch", "origin"])),
        )
        self.assertEqual(
            runner.command(self.project_command(["rev-parse", "HEAD"]))[0],
            runner.binding.executable_locator,
        )

    def test_local_runner_admits_only_bounded_plumbing_without_external_filters(self) -> None:
        runner = TrustedProjectUpdateGitRunner.resolve_preapproval(
            self.actual_git()
        )
        self.addCleanup(runner.close)
        runner.close_transport_boundary()
        safe_commands = (
            ["cat-file", "--batch"],
            ["config", "--includes", "--null", "--list", "--show-origin"],
            ["config", "--type=bool", "--get", "core.autocrlf"],
            [
                "config",
                "--local",
                "--no-includes",
                "--name-only",
                "--get-regexp",
                r"^remote\.origin\.url$",
            ],
            ["hash-object", "--stdin"],
            ["hash-object", "--no-filters", "--", "wom-kit/src/example.py"],
            ["read-tree", "a" * 40],
            ["update-ref", "--no-deref", "HEAD", "a" * 40],
        )
        for command in safe_commands:
            with self.subTest(command=command):
                self.assertEqual(
                    runner.command(self.project_command(command))[0],
                    runner.binding.executable_locator,
                )
        rejected_commands = (
            ["archive", "--remote=origin", "HEAD"],
            ["checkout", "HEAD"],
            ["remote", "update"],
            ["cat-file", "--filters", "HEAD:file"],
            ["config", "--edit"],
            ["hash-object", "-w", "--stdin"],
            ["hash-object", "--no-filters", "--", "../outside.py"],
            ["hash-object", "--no-filters", "--", "C:/outside.py"],
            ["hash-object", "--no-filters", "--", "dir\\outside.py"],
            ["read-tree", "-u", "HEAD"],
        )
        for command in rejected_commands:
            with self.subTest(command=command):
                self.assert_code(
                    "project_update_git_runner_command_invalid",
                    lambda command=command: runner.command(
                        self.project_command(command)
                    ),
                )
        for command in (
            ["-C", str(self.root), "rev-parse", "HEAD"],
            ["-c", "core.fsmonitor=false", "rev-parse", "HEAD"],
            ["--git-dir", str(self.root), "rev-parse", "HEAD"],
        ):
            with self.subTest(unsafe_prologue=command):
                self.assert_code(
                    "project_update_git_runner_command_invalid",
                    lambda command=command: runner.command(command),
                )

    def test_held_file_blocks_or_detects_same_path_replacement(self) -> None:
        path = self.dummy_git()
        runner = TrustedProjectUpdateGitRunner.resolve_preapproval(path)
        original = path.read_bytes()
        replacement_succeeded = False
        try:
            try:
                path.write_bytes(b"changed executable bytes\n")
                replacement_succeeded = True
            except OSError:
                pass
            if replacement_succeeded:
                self.assert_code(
                    "project_update_git_runner_drift",
                    runner.assert_unchanged,
                )
            else:
                self.assertEqual(path.read_bytes(), original)
                runner.assert_unchanged()
        finally:
            runner.close()

    def test_reopen_rejects_same_size_byte_drift(self) -> None:
        path = self.dummy_git()
        runner = TrustedProjectUpdateGitRunner.resolve_preapproval(path)
        binding = runner.binding
        runner.close()
        original = path.read_bytes()
        path.write_bytes(b"x" * len(original))
        self.assert_code(
            "project_update_git_runner_drift",
            lambda: TrustedProjectUpdateGitRunner.reopen_private(binding),
        )

    def test_duplicate_private_json_key_is_rejected(self) -> None:
        runner = TrustedProjectUpdateGitRunner.resolve_preapproval(
            self.actual_git()
        )
        raw = runner.private_binding_bytes()
        runner.close()
        duplicated = raw.replace(
            b'{',
            b'{"schema":"wom-kit/project-update-trusted-git-runner-private/v0.4.3",',
            1,
        )
        self.assert_code(
            "project_update_git_runner_binding_invalid",
            lambda: load_private_binding_bytes(duplicated),
        )

    def test_symlink_is_rejected_and_hardlink_count_is_bound(self) -> None:
        source = self.dummy_git()
        symlink = self.root / ("link-git.exe" if os.name == "nt" else "link-git")
        try:
            symlink.symlink_to(source)
        except OSError:
            symlink = None
        if symlink is not None:
            self.assert_code(
                "project_update_git_runner_unsafe",
                lambda: TrustedProjectUpdateGitRunner.resolve_preapproval(
                    symlink
                ),
            )

        hardlink_root = self.root / "hardlink"
        hardlink_root.mkdir()
        hardlink = hardlink_root / source.name
        try:
            os.link(source, hardlink)
        except OSError:
            self.skipTest("hardlinks unavailable")
        runner = TrustedProjectUpdateGitRunner.resolve_preapproval(source)
        try:
            self.assertEqual(runner.binding.link_count, 2)
            try:
                hardlink.write_bytes(b"mutated through second link\n")
            except OSError:
                runner.assert_unchanged()
            else:
                self.assert_code(
                    "project_update_git_runner_drift",
                    runner.assert_unchanged,
                )
        finally:
            runner.close()


if __name__ == "__main__":
    unittest.main()
