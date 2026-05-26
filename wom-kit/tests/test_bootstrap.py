from __future__ import annotations

import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = KIT_ROOT.parent


def read_package_version() -> str:
    for line in (KIT_ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        if line.startswith("version = "):
            return line.split("=", 1)[1].strip().strip('"')
    raise AssertionError("pyproject.toml is missing a project version.")


class BootstrapTests(unittest.TestCase):
    def run_powershell_script(self, script_name: str, args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        shell = shutil.which("powershell") or shutil.which("pwsh")
        if shell is None:
            self.skipTest("PowerShell is not available.")
        command = [shell, "-NoProfile"]
        if Path(shell).name.lower().startswith("powershell"):
            command.extend(["-ExecutionPolicy", "Bypass"])
        command.extend(["-File", str(KIT_ROOT / "scripts" / script_name)])
        command.extend(args)
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        return subprocess.run(command, cwd=KIT_ROOT, capture_output=True, text=True, encoding="utf-8", env=merged_env)

    def assert_no_baseline_created(self, env_before: str | None, archives_existed_before: bool) -> None:
        env_path = KIT_ROOT / ".env"
        env_after = env_path.read_text(encoding="utf-8") if env_path.exists() else None
        self.assertEqual(env_after, env_before)
        self.assertEqual((KIT_ROOT / "archives").exists(), archives_existed_before)

    def test_windows_bootstrap_dry_run_changes_nothing(self) -> None:
        env_path = KIT_ROOT / ".env"
        before = env_path.read_text(encoding="utf-8") if env_path.exists() else None
        result = self.run_powershell_script("install-windows.ps1", ["-DryRun"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Dry run only", result.stdout)
        self.assertIn("Docker daemon available", result.stdout)
        after = env_path.read_text(encoding="utf-8") if env_path.exists() else None
        self.assertEqual(after, before)

    def test_root_wom_kit_shim_resolves_package(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import wom_kit; import wom_kit.archive_cli; print(wom_kit.__version__)",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "0.2.47")
        self.assertEqual(result.stdout.strip(), read_package_version())

    def test_windows_setup_dry_run_changes_nothing(self) -> None:
        env_path = KIT_ROOT / ".env"
        before = env_path.read_text(encoding="utf-8") if env_path.exists() else None
        archives_before = (KIT_ROOT / "archives").exists()
        result = self.run_powershell_script(
            "setup-windows.ps1",
            [
                "-DryRun",
                "-ArchiveId",
                "archive:personal:setup",
                "-PrincipalId",
                "person:setup",
                "-PrincipalName",
                "Setup Person",
            ],
            env={"AI_ARCHIVE_TEST_DOCKER_STATE": "ready"},
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Zettel-Kasten one-command setup", result.stdout)
        self.assertIn("Dry run only", result.stdout)
        self.assertIn("Onboarding dry-run command", result.stdout)
        self.assert_no_baseline_created(before, archives_before)

    def test_windows_setup_mock_docker_states(self) -> None:
        cases = [
            ("missing", "winget install --id Docker.DockerDesktop"),
            ("compose_missing", "Docker Compose is missing"),
            ("daemon_down", "Docker Desktop would be started"),
            ("ready", "Docker daemon available: True"),
        ]
        for state, expected in cases:
            with self.subTest(state=state):
                result = self.run_powershell_script(
                    "setup-windows.ps1",
                    ["-DryRun"],
                    env={"AI_ARCHIVE_TEST_DOCKER_STATE": state},
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn(expected, result.stdout)

    def test_windows_setup_daemon_down_fails_friendly_without_files(self) -> None:
        env_path = KIT_ROOT / ".env"
        before = env_path.read_text(encoding="utf-8") if env_path.exists() else None
        archives_before = (KIT_ROOT / "archives").exists()
        result = self.run_powershell_script(
            "setup-windows.ps1",
            [
                "-DockerWaitSeconds",
                "0",
                "-ArchiveId",
                "archive:personal:daemon-down",
                "-PrincipalId",
                "person:daemon-down",
            ],
            env={"AI_ARCHIVE_TEST_DOCKER_STATE": "daemon_down"},
        )
        self.assertEqual(result.returncode, 1)
        combined = result.stdout + result.stderr
        self.assertRegex(combined, r"daem\s*on is not reachable")
        self.assertNotIn("NativeCommandError", combined)
        self.assert_no_baseline_created(before, archives_before)

    def test_windows_setup_noninteractive_missing_onboarding_values_fails_before_files(self) -> None:
        env_path = KIT_ROOT / ".env"
        before = env_path.read_text(encoding="utf-8") if env_path.exists() else None
        archives_before = (KIT_ROOT / "archives").exists()
        result = self.run_powershell_script(
            "setup-windows.ps1",
            ["-Yes"],
            env={"AI_ARCHIVE_TEST_DOCKER_STATE": "ready"},
        )
        self.assertEqual(result.returncode, 1)
        combined = result.stdout + result.stderr
        self.assertIn("Onboarding values are missing", combined)
        self.assertIn("-ArchiveId", combined)
        self.assert_no_baseline_created(before, archives_before)

    def test_unix_bootstrap_dry_run_changes_nothing(self) -> None:
        shell = shutil.which("bash") or shutil.which("sh")
        if shell is None:
            self.skipTest("A POSIX shell is not available.")
        probe = subprocess.run(
            [shell, "-c", "printf ok"],
            cwd=KIT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if probe.returncode != 0:
            self.skipTest("A working POSIX shell is not available.")
        env_path = KIT_ROOT / ".env"
        before = env_path.read_text(encoding="utf-8") if env_path.exists() else None
        result = subprocess.run(
            [shell, str(KIT_ROOT / "scripts" / "install-unix.sh"), "--dry-run"],
            cwd=KIT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Dry run only", result.stdout)
        self.assertIn("Docker daemon available", result.stdout)
        after = env_path.read_text(encoding="utf-8") if env_path.exists() else None
        self.assertEqual(after, before)

    def test_unix_setup_dry_run_changes_nothing(self) -> None:
        shell = shutil.which("bash") or shutil.which("sh")
        if shell is None:
            self.skipTest("A POSIX shell is not available.")
        probe = subprocess.run(
            [shell, "-c", "printf ok"],
            cwd=KIT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if probe.returncode != 0:
            self.skipTest("A working POSIX shell is not available.")
        env_path = KIT_ROOT / ".env"
        before = env_path.read_text(encoding="utf-8") if env_path.exists() else None
        archives_before = (KIT_ROOT / "archives").exists()
        env = os.environ.copy()
        env["AI_ARCHIVE_TEST_DOCKER_STATE"] = "missing"
        result = subprocess.run(
            [
                shell,
                str(KIT_ROOT / "scripts" / "setup-unix.sh"),
                "--dry-run",
                "--archive-id",
                "archive:personal:setup",
                "--principal-id",
                "person:setup",
            ],
            cwd=KIT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Zettel-Kasten one-command setup", result.stdout)
        self.assertIn("Dry run only", result.stdout)
        self.assert_no_baseline_created(before, archives_before)

    def test_unix_setup_noninteractive_missing_onboarding_values_fails_before_files(self) -> None:
        shell = shutil.which("bash") or shutil.which("sh")
        if shell is None:
            self.skipTest("A POSIX shell is not available.")
        probe = subprocess.run(
            [shell, "-c", "printf ok"],
            cwd=KIT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if probe.returncode != 0:
            self.skipTest("A working POSIX shell is not available.")
        env_path = KIT_ROOT / ".env"
        before = env_path.read_text(encoding="utf-8") if env_path.exists() else None
        archives_before = (KIT_ROOT / "archives").exists()
        env = os.environ.copy()
        env["AI_ARCHIVE_TEST_DOCKER_STATE"] = "ready"
        result = subprocess.run(
            [shell, str(KIT_ROOT / "scripts" / "setup-unix.sh"), "--yes"],
            cwd=KIT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )
        self.assertEqual(result.returncode, 1)
        combined = result.stdout + result.stderr
        self.assertIn("Onboarding values are missing", combined)
        self.assertIn("--archive-id", combined)
        self.assert_no_baseline_created(before, archives_before)

    def test_docker_compose_config_when_docker_is_available(self) -> None:
        docker = shutil.which("docker")
        if docker is None:
            self.skipTest("Docker is not available.")
        version = subprocess.run(
            [docker, "compose", "version"],
            cwd=KIT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if version.returncode != 0:
            self.skipTest("Docker Compose is not available.")
        result = subprocess.run(
            [docker, "compose", "config"],
            cwd=KIT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("archive-cli", result.stdout)
        self.assertIn("archive-mcp", result.stdout)

    def test_optional_docker_runtime_doctor(self) -> None:
        if os.environ.get("AI_ARCHIVE_RUN_DOCKER_TESTS") != "1":
            self.skipTest("Set AI_ARCHIVE_RUN_DOCKER_TESTS=1 to run Docker runtime tests.")
        docker = shutil.which("docker")
        if docker is None:
            self.skipTest("Docker is not available.")
        result = subprocess.run(
            [
                docker,
                "compose",
                "run",
                "--rm",
                "archive-cli",
                "doctor",
                "examples/fake-life-archive",
                "--strict",
            ],
            cwd=KIT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
