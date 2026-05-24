from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import archive_cli
from wom_kit import archive_services
from wom_kit import mcp_server


class SecurityHardeningTests(unittest.TestCase):
    def test_dockerfile_uses_pinned_non_root_hashed_install(self) -> None:
        dockerfile = (KIT_ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("FROM python:3.12-slim@sha256:", dockerfile)
        self.assertIn("--require-hashes -r requirements-container.txt", dockerfile)
        self.assertIn("--no-build-isolation --no-deps -e .", dockerfile)
        self.assertIn("USER archive", dockerfile)
        self.assertNotIn("pip install --no-cache-dir --upgrade pip", dockerfile)

    def test_container_requirements_are_hash_locked(self) -> None:
        requirements = (KIT_ROOT / "requirements-container.txt").read_text(encoding="utf-8")
        self.assertIn("pip==26.1.1", requirements)
        self.assertIn("setuptools==82.0.1", requirements)
        self.assertIn("PyYAML==6.0.3", requirements)
        self.assertIn("--hash=sha256:", requirements)
        self.assertNotIn("PyYAML>=", requirements)

    def test_compose_runtime_security_defaults(self) -> None:
        compose = yaml.safe_load((KIT_ROOT / "compose.yaml").read_text(encoding="utf-8"))
        self.assertIsInstance(compose, dict)
        services = compose["services"]
        for name in ["archive-cli", "archive-mcp"]:
            service = services[name]
            self.assertEqual(service["user"], "${ARCHIVE_UID:-10001}:${ARCHIVE_GID:-10001}")
            self.assertIs(service["read_only"], True)
            self.assertIn("/tmp:rw,noexec,nosuid,nodev", service["tmpfs"])
            self.assertIn("ALL", service["cap_drop"])
            self.assertIn("no-new-privileges:true", service["security_opt"])
            self.assertEqual(service["network_mode"], "none")
            self.assertEqual(service["environment"]["AI_ARCHIVE_MCP_ALLOWED_ROOTS"], "/archives")
            self.assertNotIn("privileged", service)
            self.assertNotIn("/var/run/docker.sock", str(service))

    def test_dockerignore_excludes_secret_like_build_context_files(self) -> None:
        dockerignore = (KIT_ROOT / ".dockerignore").read_text(encoding="utf-8")
        for pattern in [
            ".env",
            ".env.*",
            "secrets/",
            "profiles/local/",
            "keyrings/local/",
            ".archive-local/",
            "*.pem",
            "*.kdbx",
            "credentials.json",
            "token.json",
            "rclone.conf",
        ]:
            self.assertIn(pattern, dockerignore)

    def test_env_example_declares_non_root_runtime_identity_without_secrets(self) -> None:
        env_example = (KIT_ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertIn("ARCHIVE_UID=10001", env_example)
        self.assertIn("ARCHIVE_GID=10001", env_example)
        self.assertNotRegex(env_example, r"(?i)(token|password|secret|api[_-]?key)\s*=")

    def test_windows_setup_rejects_repository_root_as_archive_root(self) -> None:
        shell = shutil.which("powershell") or shutil.which("pwsh")
        if shell is None:
            self.skipTest("PowerShell is not available.")
        command = [shell, "-NoProfile"]
        if Path(shell).name.lower().startswith("powershell"):
            command.extend(["-ExecutionPolicy", "Bypass"])
        command.extend(
            [
                "-File",
                str(KIT_ROOT / "scripts" / "setup-windows.ps1"),
                "-DryRun",
                "-ArchiveRoot",
                str(KIT_ROOT),
                "-ArchiveId",
                "archive:personal:unsafe",
                "-PrincipalId",
                "person:unsafe",
            ]
        )
        env = os.environ.copy()
        env["AI_ARCHIVE_TEST_DOCKER_STATE"] = "ready"
        result = subprocess.run(command, cwd=KIT_ROOT, capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(result.returncode, 1)
        self.assertIn("repository root", result.stdout + result.stderr)

    def test_windows_setup_rejects_system_directory_descendants(self) -> None:
        shell = shutil.which("powershell") or shutil.which("pwsh")
        if shell is None:
            self.skipTest("PowerShell is not available.")
        system_root = os.environ.get("SystemRoot")
        if not system_root:
            self.skipTest("SystemRoot is not available.")
        command = [shell, "-NoProfile"]
        if Path(shell).name.lower().startswith("powershell"):
            command.extend(["-ExecutionPolicy", "Bypass"])
        command.extend(
            [
                "-File",
                str(KIT_ROOT / "scripts" / "setup-windows.ps1"),
                "-DryRun",
                "-ArchiveRoot",
                str(Path(system_root) / "Temp" / "zettel-kasten-unsafe"),
                "-ArchiveId",
                "archive:personal:unsafe",
                "-PrincipalId",
                "person:unsafe",
            ]
        )
        env = os.environ.copy()
        env["AI_ARCHIVE_TEST_DOCKER_STATE"] = "ready"
        result = subprocess.run(command, cwd=KIT_ROOT, capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(result.returncode, 1)
        self.assertIn("system directory", result.stdout + result.stderr)

    def test_unix_setup_rejects_repository_root_as_archive_root(self) -> None:
        shell = shutil.which("bash") or shutil.which("sh")
        if shell is None:
            self.skipTest("A POSIX shell is not available.")
        probe = subprocess.run([shell, "-c", "printf ok"], cwd=KIT_ROOT, capture_output=True, text=True, encoding="utf-8")
        if probe.returncode != 0:
            self.skipTest("A working POSIX shell is not available.")
        env = os.environ.copy()
        env["AI_ARCHIVE_TEST_DOCKER_STATE"] = "ready"
        result = subprocess.run(
            [
                shell,
                str(KIT_ROOT / "scripts" / "setup-unix.sh"),
                "--dry-run",
                "--archive-root",
                str(KIT_ROOT).replace("\\", "/"),
                "--archive-id",
                "archive:personal:unsafe",
                "--principal-id",
                "person:unsafe",
            ],
            cwd=KIT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("repository root", result.stdout + result.stderr)

    def test_mcp_path_allowlist_blocks_paths_outside_archives(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            allowed = Path(tmp) / "archives"
            allowed.mkdir()
            outside = Path(tmp) / "outside"
            outside.mkdir()
            previous = os.environ.get(mcp_server.MCP_ALLOWED_ROOTS_ENV)
            os.environ[mcp_server.MCP_ALLOWED_ROOTS_ENV] = str(allowed)
            try:
                mcp_server.enforce_mcp_path_allowlist((allowed / "personal").resolve())
                with self.assertRaises(mcp_server.ToolError):
                    mcp_server.enforce_mcp_path_allowlist(outside.resolve())
            finally:
                if previous is None:
                    os.environ.pop(mcp_server.MCP_ALLOWED_ROOTS_ENV, None)
                else:
                    os.environ[mcp_server.MCP_ALLOWED_ROOTS_ENV] = previous

    def test_symlink_escape_is_flagged_and_not_indexed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", root)
            outside = Path(tmp) / "outside.md"
            outside.write_text(
                "---\nid: zet_outside_secret\ntitle: Outside Secret\ncreated_at: 2026-05-21\nupdated_at: 2026-05-21\narchive_id: outside\nstatus: draft\nfacets: {}\nassets: []\nedges: []\nprovenance: {created_by: test, created_in: outside, source: symlink, derived_from: []}\nvisibility: {scope: private, source_visibility: private}\n---\n\noutside secret\n",
                encoding="utf-8",
            )
            link = root / "inbox" / "zet_outside_secret.md"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"Symlinks are not available in this environment: {exc}")

            doctor = archive_cli.Doctor(root)
            diagnostics = doctor.run()
            codes = {item.code for item in diagnostics}
            self.assertIn("archive_symlink_escapes_root", codes)

            listed = archive_services.list_zettels(root, status="draft")
            self.assertFalse(any(item.get("id") == "zet_outside_secret" for item in listed["zettels"]))

    def test_archive_write_paths_reject_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", root)
            outside = Path(tmp) / "outside-inbox"
            outside.mkdir()
            shutil.rmtree(root / "inbox")
            try:
                (root / "inbox").symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"Symlinks are not available in this environment: {exc}")

            with self.assertRaises(archive_services.ArchiveServiceError):
                archive_services.create_draft_zettel(
                    root,
                    title="Should not escape",
                    body="This write should not leave the archive.",
                )

    def test_optional_docker_runtime_is_non_root_read_only_except_archives(self) -> None:
        if os.environ.get("AI_ARCHIVE_RUN_DOCKER_TESTS") != "1":
            self.skipTest("Set AI_ARCHIVE_RUN_DOCKER_TESTS=1 to run Docker runtime hardening tests.")
        docker = shutil.which("docker")
        if docker is None:
            self.skipTest("Docker is not available.")
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["ARCHIVE_HOST_ROOT"] = tmp
            result = subprocess.run(
                [
                    docker,
                    "compose",
                    "run",
                    "--rm",
                    "--entrypoint",
                    "sh",
                    "archive-cli",
                    "-c",
                    'test "$(id -u)" != "0" && ! touch /app/security-write-test && touch /archives/security-write-test && rm /archives/security-write-test',
                ],
                cwd=KIT_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
                timeout=180,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
