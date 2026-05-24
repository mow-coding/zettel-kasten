from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import archive_cli


class McpServerTests(unittest.TestCase):
    def start_server(self, extra_env: dict[str, str] | None = None) -> subprocess.Popen[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        if extra_env:
            env.update(extra_env)
        return subprocess.Popen(
            [sys.executable, "-m", "wom_kit.mcp_server"],
            cwd=KIT_ROOT,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

    def send(self, process: subprocess.Popen[str], message: dict) -> dict:
        assert process.stdin is not None
        assert process.stdout is not None
        process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        process.stdin.flush()
        line = process.stdout.readline()
        self.assertTrue(line, "Server did not return a response.")
        return json.loads(line)

    def notify(self, process: subprocess.Popen[str], message: dict) -> None:
        assert process.stdin is not None
        process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        process.stdin.flush()

    def stop_server(self, process: subprocess.Popen[str]) -> None:
        if process.stdin:
            process.stdin.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()

    def copy_fake_archive(self, root: Path) -> Path:
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", root)
        return root

    def copy_fake_archive_as_company_target(self, root: Path) -> Path:
        archive_root = self.copy_fake_archive(root)
        archive_path = archive_root / "archive.yml"
        archive_data = archive_cli.load_yaml(archive_path.read_text(encoding="utf-8"))
        archive_data["archive_id"] = "archive:company:fake-blue"
        archive_data["name"] = "Fake Blue Target Archive"
        archive_data["type"] = "company"
        archive_path.write_text(archive_cli.dump_yaml(archive_data), encoding="utf-8")

        identity_path = archive_root / "archive-identity.yml"
        identity = archive_cli.load_yaml(identity_path.read_text(encoding="utf-8"))
        identity["identity"]["archive_id"] = "archive:company:fake-blue"
        identity["identity"]["identity_id"] = "identity:archive:company:fake-blue"
        identity["identity"]["scope"] = "company"
        identity["identity"]["principal_id"] = "company:fake-blue"
        identity["identity"]["display_name"] = "Fake Blue Company"
        identity["ownership"]["owner_id"] = "company:fake-blue"
        identity["ownership"]["owner_kind"] = "company"
        identity["ownership"]["owner_display_name"] = "Fake Blue Company"
        identity["ownership"]["owner_archive_id"] = "archive:company:fake-blue"
        identity["trusted_counterparties"].append(
            {
                "identity_id": "identity:archive:personal:fake-life",
                "archive_id": "archive:personal:fake-life",
                "principal_id": "person:fake-user",
                "expected_fingerprint": "SHA256:fake-user-primary",
                "trust_level": "out_of_band_verified",
            }
        )
        identity_path.write_text(archive_cli.dump_yaml(identity), encoding="utf-8")
        return archive_root

    def write_json_receipt(self, archive_root: Path, relative_path: str, payload: dict) -> Path:
        path = archive_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path

    def write_profile_registry(self, path: Path, archive_root: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            archive_cli.dump_yaml(
                {
                    "version": "wom-profile-registry/v0.1",
                    "default_profile": "profile:personal:me",
                    "profiles": [
                        {
                            "profile_id": "profile:personal:me",
                            "label": "Personal archive",
                            "aliases": ["me", "personal"],
                            "node_id": "person:me",
                            "archive_id": "archive:personal:me",
                            "archive_type": "personal",
                            "archive_root": archive_root,
                            "operator_id": "person:me",
                            "authority_mode": "owner_operator",
                            "token": {"state": "present", "token_ref": "local-keyring:wom/profile/example-personal"},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return path

    def init_transfer_ready_family_archive(self, root: Path) -> Path:
        result = subprocess.run(
            [
                sys.executable,
                "cli/archive.py",
                "init",
                str(root),
                "--type",
                "family",
                "--archive-id",
                "archive:family:example-household",
                "--principal-id",
                "family:example-household",
                "--principal-kind",
                "family",
                "--principal-name",
                "Example Household",
                "--name",
                "Example Household Archive",
            ],
            cwd=KIT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        identity_path = root / "archive-identity.yml"
        identity = archive_cli.load_yaml(identity_path.read_text(encoding="utf-8"))
        identity["trusted_counterparties"].append(
            {
                "identity_id": "identity:archive:child:example-child",
                "archive_id": "archive:child:example-child",
                "principal_id": "person:child-template",
                "expected_fingerprint": "SHA256:example-child-primary",
                "trust_level": "out_of_band_verified",
            }
        )
        identity_path.write_text(archive_cli.dump_yaml(identity), encoding="utf-8")
        return root

    def test_initialize_and_list_tools(self) -> None:
        process = self.start_server()
        try:
            initialize = self.send(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-11-25",
                        "capabilities": {},
                        "clientInfo": {"name": "test-client", "version": "0.1"},
                    },
                },
            )
            self.assertEqual(initialize["result"]["serverInfo"]["name"], "zettel-kasten-archive-mcp")
            self.notify(process, {"jsonrpc": "2.0", "method": "notifications/initialized"})

            tools = self.send(process, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            tools_by_name = {tool["name"]: tool for tool in tools["result"]["tools"]}
            tool_names = {tool["name"] for tool in tools["result"]["tools"]}
            self.assertIn("wom_profile_list", tool_names)
            self.assertIn("wom_profile_resolve", tool_names)
            self.assertIn("archive_doctor", tool_names)
            self.assertIn("archive_runtime_context", tool_names)
            self.assertIn("github_repository_setup_plan", tool_names)
            self.assertIn("create_draft_zettel", tool_names)
            self.assertIn("archive_index", tool_names)
            self.assertIn("archive_search", tool_names)
            self.assertIn("promotion_check", tool_names)
            self.assertIn("mint_zettel_check", tool_names)
            self.assertIn("share_check", tool_names)
            self.assertIn("delegate_zet_check", tool_names)
            self.assertIn("attest_zet_check", tool_names)
            self.assertIn("anchor_zet_check", tool_names)
            self.assertIn("archive_onboarding_plan", tool_names)
            self.assertIn("real_pilot_plan", tool_names)
            self.assertIn("archive_preflight_check", tool_names)
            self.assertIn("recovery_plan", tool_names)
            self.assertIn("restore_drill_plan", tool_names)
            self.assertIn("external_import_plan", tool_names)
            self.assertIn("list_sources", tool_names)
            self.assertIn("source_scan_plan", tool_names)
            self.assertIn("source_registration_plan", tool_names)
            self.assertIn("source_mount_plan", tool_names)
            self.assertIn("ownership_transfer_check", tool_names)
            share_required = tools_by_name["share_check"]["inputSchema"]["required"]
            delegate_schema = tools_by_name["delegate_zet_check"]["inputSchema"]
            self.assertIn("target_archive", share_required)
            self.assertNotIn("target_policy", tools_by_name["share_check"]["inputSchema"]["properties"])
            self.assertNotIn("target_archive", delegate_schema["required"])
            self.assertIn("target_policy", delegate_schema["properties"])
            self.assertNotIn("promote_zettel", tool_names)
            self.assertNotIn("archive_promote", tool_names)
            self.assertNotIn("mint_zettel", tool_names)
            self.assertNotIn("archive_mint_zettel", tool_names)
            self.assertNotIn("mint_zettel_apply", tool_names)
            self.assertNotIn("wom_profile_register", tool_names)
            self.assertNotIn("wom_profile_apply", tool_names)
            self.assertNotIn("wom_profile_token_register", tool_names)
            self.assertNotIn("profile_token_register", tool_names)
            self.assertNotIn("archive_runtime_context_apply", tool_names)
            self.assertNotIn("github_repository_setup_apply", tool_names)
            self.assertNotIn("github_repository_create", tool_names)
            self.assertNotIn("github_repository_connect", tool_names)
            self.assertNotIn("github_repository_push", tool_names)
            self.assertNotIn("github_repository_sync", tool_names)
            self.assertNotIn("share_archive_scope", tool_names)
            self.assertNotIn("delegate_zet", tool_names)
            self.assertNotIn("attest_zet", tool_names)
            self.assertNotIn("anchor_zet", tool_names)
            self.assertNotIn("archive_onboard", tool_names)
            self.assertNotIn("archive_onboarding_apply", tool_names)
            self.assertNotIn("real_pilot_apply", tool_names)
            self.assertNotIn("archive_preflight_apply", tool_names)
            self.assertNotIn("restore_drill_apply", tool_names)
            self.assertNotIn("archive_restore_drill", tool_names)
            self.assertNotIn("recovery_apply", tool_names)
            self.assertNotIn("external_import_apply", tool_names)
            self.assertNotIn("import_external_archive", tool_names)
            self.assertNotIn("scan_source", tool_names)
            self.assertNotIn("source_scan_apply", tool_names)
            self.assertNotIn("archive_scan_source", tool_names)
            self.assertNotIn("add_source", tool_names)
            self.assertNotIn("source_registration_apply", tool_names)
            self.assertNotIn("transfer_ownership", tool_names)
            self.assertNotIn("ownership_transfer_apply", tool_names)
            self.assertNotIn("archive_transfer_ownership", tool_names)
        finally:
            self.stop_server(process)

    def test_archive_doctor_tool_passes_fake_archive(self) -> None:
        process = self.start_server()
        try:
            archive_root = KIT_ROOT / "examples" / "fake-life-archive"
            response = self.send(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "archive_doctor",
                        "arguments": {"archive_root": str(archive_root), "strict": True},
                    },
                },
            )
            result = response["result"]
            self.assertFalse(result["isError"])
            self.assertTrue(result["structuredContent"]["ok"])
            self.assertEqual(result["structuredContent"]["errors"], 0)
            self.assertEqual(result["structuredContent"]["warnings"], 0)
        finally:
            self.stop_server(process)

    def test_wom_profile_tools_respect_allowed_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            allowed_root = tmp_root / "allowed"
            outside_root = tmp_root / "outside"
            allowed_registry = self.write_profile_registry(
                allowed_root / "profiles.yml",
                str((allowed_root / "archive").resolve()),
            )
            outside_registry = self.write_profile_registry(
                outside_root / "profiles.yml",
                str((outside_root / "archive").resolve()),
            )

            process = self.start_server({"AI_ARCHIVE_MCP_ALLOWED_ROOTS": str(allowed_root)})
            try:
                list_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "wom_profile_list",
                            "arguments": {"registry": str(allowed_registry)},
                        },
                    },
                )
                self.assertFalse(list_response["result"]["isError"])
                structured = list_response["result"]["structuredContent"]
                self.assertTrue(structured["ok"])
                self.assertEqual(structured["lifecycle_action"], "profile_list")
                self.assertEqual(structured["profiles"][0]["archive_root"], "<local-path-redacted>")
                self.assertNotIn(str(allowed_root), json.dumps(structured))

                outside_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "wom_profile_resolve",
                            "arguments": {"registry": str(outside_registry), "target": "personal"},
                        },
                    },
                )
                self.assertTrue(outside_response["result"]["isError"])
                self.assertIn("outside allowed archive root", outside_response["result"]["structuredContent"]["error"])
            finally:
                self.stop_server(process)

    def test_wom_profile_resolve_ignores_local_path_disclosure_without_env_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = str((Path(tmp) / "archive").resolve())
            registry = self.write_profile_registry(Path(tmp) / "profiles.yml", archive_root)
            process = self.start_server()
            try:
                response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "wom_profile_resolve",
                            "arguments": {
                                "registry": str(registry),
                                "target": "personal",
                                "redact_local_paths": False,
                            },
                        },
                    },
                )
                result = response["result"]
                self.assertFalse(result["isError"])
                structured = result["structuredContent"]
                self.assertTrue(structured["redaction"]["local_paths_redacted"])
                self.assertEqual(structured["target_archive_context_preview"]["archive_root"], "<local-path-redacted>")
                self.assertNotIn(archive_root, json.dumps(structured))
                self.assertTrue(
                    any("AI_ARCHIVE_MCP_ALLOW_LOCAL_PATHS=1" in warning for warning in structured["warnings"])
                )
            finally:
                self.stop_server(process)

    def test_wom_profile_resolve_can_disclose_local_paths_with_env_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = str((Path(tmp) / "archive").resolve())
            registry = self.write_profile_registry(Path(tmp) / "profiles.yml", archive_root)
            process = self.start_server({"AI_ARCHIVE_MCP_ALLOW_LOCAL_PATHS": "1"})
            try:
                response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "wom_profile_resolve",
                            "arguments": {
                                "registry": str(registry),
                                "target": "personal",
                                "redact_local_paths": False,
                            },
                        },
                    },
                )
                result = response["result"]
                self.assertFalse(result["isError"])
                structured = result["structuredContent"]
                self.assertFalse(structured["redaction"]["local_paths_redacted"])
                self.assertEqual(structured["target_archive_context_preview"]["archive_root"], archive_root)
            finally:
                self.stop_server(process)

    def test_archive_runtime_context_tool_respects_allowed_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            allowed_root = tmp_root / "allowed"
            outside_root = tmp_root / "outside"
            allowed_archive = self.copy_fake_archive(allowed_root / "archive")
            outside_archive = self.copy_fake_archive(outside_root / "archive")

            process = self.start_server({"AI_ARCHIVE_MCP_ALLOWED_ROOTS": str(allowed_root)})
            try:
                allowed_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "archive_runtime_context",
                            "arguments": {"archive_root": str(allowed_archive)},
                        },
                    },
                )
                allowed_result = allowed_response["result"]
                self.assertFalse(allowed_result["isError"])
                structured = allowed_result["structuredContent"]
                self.assertTrue(structured["ok"])
                self.assertEqual(structured["lifecycle_action"], "runtime_context")
                self.assertTrue(structured["redaction"]["local_paths_redacted"])
                self.assertNotIn(str(allowed_archive), json.dumps(structured))

                outside_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "archive_runtime_context",
                            "arguments": {"archive_root": str(outside_archive)},
                        },
                    },
                )
                outside_result = outside_response["result"]
                self.assertTrue(outside_result["isError"])
                self.assertIn("outside allowed archive root", outside_result["structuredContent"]["error"])
            finally:
                self.stop_server(process)

    def test_archive_runtime_context_tool_ignores_local_path_disclosure_without_env_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            process = self.start_server()
            try:
                response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "archive_runtime_context",
                            "arguments": {"archive_root": str(archive_root), "redact_local_paths": False},
                        },
                    },
                )
                result = response["result"]
                self.assertFalse(result["isError"])
                structured = result["structuredContent"]
                self.assertTrue(structured["redaction"]["local_paths_redacted"])
                self.assertNotIn("local_archive_root", structured)
                self.assertNotIn("local_paths", structured)
                self.assertTrue(
                    any("AI_ARCHIVE_MCP_ALLOW_LOCAL_PATHS=1" in warning for warning in structured["warnings"])
                )
                self.assertNotIn(str(archive_root), json.dumps(structured))
            finally:
                self.stop_server(process)

    def test_github_repository_setup_plan_tool_writes_nothing_and_respects_allowed_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            allowed_root = tmp_root / "allowed"
            outside_root = tmp_root / "outside"
            allowed_archive = self.copy_fake_archive(allowed_root / "archive")
            outside_archive = self.copy_fake_archive(outside_root / "archive")
            before = {
                path.relative_to(allowed_archive).as_posix(): path.read_text(encoding="utf-8")
                for path in sorted(allowed_archive.rglob("*"))
                if path.is_file()
            }

            process = self.start_server({"AI_ARCHIVE_MCP_ALLOWED_ROOTS": str(allowed_root)})
            try:
                response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "github_repository_setup_plan",
                            "arguments": {
                                "archive_root": str(allowed_archive),
                                "profile_id": "profile:personal:HongGilDong",
                                "profile_slug": "HongGilDong",
                                "github_owner": "example-user",
                                "github_account_ref": "github:account:honggildong",
                            },
                        },
                    },
                )
                result = response["result"]
                self.assertFalse(result["isError"])
                structured = result["structuredContent"]
                self.assertTrue(structured["ok"])
                self.assertTrue(structured["dry_run"])
                self.assertEqual(structured["lifecycle_action"], "github_repository_setup_plan")
                self.assertEqual(structured["proposed_repo_name"], "zettel-kasten-HongGilDong")
                self.assertFalse(structured["provider_setup_receipt_preview"]["external_actions"]["github_api_called"])
                after = {
                    path.relative_to(allowed_archive).as_posix(): path.read_text(encoding="utf-8")
                    for path in sorted(allowed_archive.rglob("*"))
                    if path.is_file()
                }
                self.assertEqual(after, before)

                outside_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "github_repository_setup_plan",
                            "arguments": {
                                "archive_root": str(outside_archive),
                                "profile_id": "profile:personal:HongGilDong",
                                "profile_slug": "HongGilDong",
                                "github_owner": "example-user",
                                "github_account_ref": "github:account:honggildong",
                            },
                        },
                    },
                )
                outside_result = outside_response["result"]
                self.assertTrue(outside_result["isError"])
                self.assertIn("outside allowed archive root", outside_result["structuredContent"]["error"])
            finally:
                self.stop_server(process)

    def test_archive_onboarding_plan_never_writes_files(self) -> None:
        process = self.start_server()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                archive_root = Path(tmp) / "mcp-onboard"
                response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "archive_onboarding_plan",
                            "arguments": {
                                "target_root": str(archive_root),
                                "archive_type": "personal",
                                "archive_id": "archive:personal:mcp-onboard",
                                "principal_id": "person:mcp-onboard",
                                "principal_name": "MCP Onboard",
                                "provider_profile": "object_storage_planned",
                            },
                        },
                    },
                )
                result = response["result"]
                self.assertFalse(result["isError"])
                structured = result["structuredContent"]
                self.assertTrue(structured["ok"])
                self.assertTrue(structured["dry_run"])
                self.assertEqual(structured["action"], "onboard_archive")
                self.assertEqual(structured["docker_runtime"]["container_os"], "linux")
                self.assertIn("cloudflare_r2", structured["provider_bindings"]["enabled_providers"])
                self.assertFalse(archive_root.exists())
        finally:
            self.stop_server(process)

    def test_real_pilot_plan_never_writes_files(self) -> None:
        process = self.start_server()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                personal_root = Path(tmp) / "personal-life"
                team_root = Path(tmp) / "team-archive"
                response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "real_pilot_plan",
                            "arguments": {
                                "personal_root": str(personal_root),
                                "team_root": str(team_root),
                            },
                        },
                    },
                )
                result = response["result"]
                self.assertFalse(result["isError"])
                structured = result["structuredContent"]
                self.assertTrue(structured["ok"])
                self.assertTrue(structured["dry_run"])
                self.assertEqual(structured["action"], "plan_real_archive_pilot")
                self.assertFalse(personal_root.exists())
                self.assertFalse(team_root.exists())
        finally:
            self.stop_server(process)

    def test_archive_preflight_check_is_read_only(self) -> None:
        process = self.start_server()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                archive_root = Path(tmp) / "archive"
                self.copy_fake_archive(archive_root)
                before = (archive_root / "source-bindings.yml").read_text(encoding="utf-8")
                response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "archive_preflight_check",
                            "arguments": {
                                "archive_root": str(archive_root),
                                "strict": True,
                            },
                        },
                    },
                )
                result = response["result"]
                self.assertFalse(result["isError"])
                structured = result["structuredContent"]
                self.assertTrue(structured["ok"])
                self.assertEqual(structured["doctor"]["errors"], 0)
                self.assertEqual((archive_root / "source-bindings.yml").read_text(encoding="utf-8"), before)
        finally:
            self.stop_server(process)

    def test_recovery_and_restore_drill_plans_never_write_files(self) -> None:
        process = self.start_server()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                archive_root = Path(tmp) / "archive"
                target = Path(tmp) / "restore-copy"
                self.copy_fake_archive(archive_root)
                before = sorted(path.relative_to(archive_root).as_posix() for path in archive_root.rglob("*"))

                recovery_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "recovery_plan",
                            "arguments": {"archive_root": str(archive_root)},
                        },
                    },
                )
                self.assertFalse(recovery_response["result"]["isError"])
                self.assertEqual(recovery_response["result"]["structuredContent"]["action"], "archive_recovery_plan")

                drill_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "restore_drill_plan",
                            "arguments": {"archive_root": str(archive_root), "target": str(target)},
                        },
                    },
                )
                self.assertFalse(drill_response["result"]["isError"])
                structured = drill_response["result"]["structuredContent"]
                self.assertTrue(structured["dry_run"])
                self.assertTrue(structured["ok"])
                self.assertFalse(target.exists())
                after = sorted(path.relative_to(archive_root).as_posix() for path in archive_root.rglob("*"))
                self.assertEqual(after, before)
        finally:
            self.stop_server(process)

    def test_external_import_plan_never_writes_files(self) -> None:
        process = self.start_server()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                archive_root = Path(tmp) / "archive"
                init_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "archive_init",
                            "arguments": {
                                "archive_root": str(archive_root),
                                "archive_type": "personal",
                                "archive_id": "archive:personal:mcp-external-import",
                                "principal_id": "person:mcp-external-import",
                            },
                        },
                    },
                )
                self.assertFalse(init_response["result"]["isError"])

                export_root = KIT_ROOT / "examples" / "external-imports" / "notion-export"
                response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "external_import_plan",
                            "arguments": {
                                "archive_root": str(archive_root),
                                "source": "notion",
                                "export_path": str(export_root),
                            },
                        },
                    },
                )
                result = response["result"]
                self.assertFalse(result["isError"])
                structured = result["structuredContent"]
                self.assertTrue(structured["dry_run"])
                self.assertTrue(structured["ok"])
                self.assertEqual(structured["source_system"], "notion")
                self.assertEqual(structured["item_count"], 1)
                self.assertFalse((archive_root / structured["items"][0]["target_path"]).exists())
                self.assertFalse((archive_root / structured["proposed_receipt_path"]).exists())
        finally:
            self.stop_server(process)

    def test_source_scan_plan_lists_sources_and_never_writes_files(self) -> None:
        process = self.start_server()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                archive_root = Path(tmp) / "archive"
                init_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "archive_init",
                            "arguments": {
                                "archive_root": str(archive_root),
                                "archive_type": "personal",
                                "archive_id": "archive:personal:mcp-source",
                                "principal_id": "person:mcp-source",
                            },
                        },
                    },
                )
                self.assertFalse(init_response["result"]["isError"])

                source_root = Path(tmp) / "source-root"
                source_root.mkdir()
                (source_root / "mcp-source-note.txt").write_text("metadata only", encoding="utf-8")

                list_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "list_sources",
                            "arguments": {"archive_root": str(archive_root)},
                        },
                    },
                )
                self.assertFalse(list_response["result"]["isError"])
                self.assertGreaterEqual(list_response["result"]["structuredContent"]["source_count"], 2)

                scan_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {
                            "name": "source_scan_plan",
                            "arguments": {
                                "archive_root": str(archive_root),
                                "source": "local:personal-documents",
                                "source_root": str(source_root),
                            },
                        },
                    },
                )
                result = scan_response["result"]
                self.assertFalse(result["isError"])
                structured = result["structuredContent"]
                self.assertTrue(structured["dry_run"])
                self.assertTrue(structured["ok"])
                self.assertEqual(structured["scan_mode"], "metadata_only")
                self.assertEqual(structured["item_count"], 1)
                self.assertFalse((archive_root / structured["proposed_source_map_path"]).exists())
                self.assertFalse((archive_root / structured["proposed_receipt_path"]).exists())
        finally:
            self.stop_server(process)

    def test_source_registration_and_mount_plans_never_write_files(self) -> None:
        process = self.start_server()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                archive_root = Path(tmp) / "archive"
                init_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "archive_init",
                            "arguments": {
                                "archive_root": str(archive_root),
                                "archive_type": "personal",
                                "archive_id": "archive:personal:mcp-source-register",
                                "principal_id": "person:mcp-source-register",
                            },
                        },
                    },
                )
                self.assertFalse(init_response["result"]["isError"])
                before = (archive_root / "source-bindings.yml").read_text(encoding="utf-8")

                plan_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "source_registration_plan",
                            "arguments": {
                                "archive_root": str(archive_root),
                                "source_id": "local:mcp-desktop",
                                "source_type": "local_folder",
                                "write_local_profile": False,
                            },
                        },
                    },
                )
                result = plan_response["result"]
                self.assertFalse(result["isError"])
                structured = result["structuredContent"]
                self.assertTrue(structured["dry_run"])
                self.assertTrue(structured["ok"])
                self.assertEqual(structured["source_binding"]["root_ref"], "ARCHIVE_SOURCE_LOCAL_MCP_DESKTOP_ROOT")
                self.assertEqual((archive_root / "source-bindings.yml").read_text(encoding="utf-8"), before)

                mount_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {
                            "name": "source_mount_plan",
                            "arguments": {"archive_root": str(archive_root)},
                        },
                    },
                )
                self.assertFalse(mount_response["result"]["isError"])
                self.assertEqual(mount_response["result"]["structuredContent"]["strategy"], "docker_compose_override_or_host_native_cli")
        finally:
            self.stop_server(process)

    def test_list_zettels_tool_returns_json_safe_paths_and_dates(self) -> None:
        process = self.start_server()
        try:
            archive_root = KIT_ROOT / "examples" / "fake-life-archive"
            response = self.send(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "list_zettels",
                        "arguments": {"archive_root": str(archive_root), "status": "all"},
                    },
                },
            )
            result = response["result"]
            self.assertFalse(result["isError"])
            zettels = result["structuredContent"]["zettels"]
            self.assertGreaterEqual(len(zettels), 1)
            self.assertNotIn("\\", zettels[0]["path"])
            self.assertIsInstance(zettels[0]["created_at"], str)
        finally:
            self.stop_server(process)

    def test_create_draft_zettel_tool_writes_to_inbox(self) -> None:
        process = self.start_server()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                archive_root = Path(tmp) / "archive"
                init_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "archive_init",
                            "arguments": {
                                "archive_root": str(archive_root),
                                "archive_type": "personal",
                                "archive_id": "archive:personal:mcp-test",
                                "principal_id": "person:mcp-test",
                                "principal_name": "MCP Test",
                            },
                        },
                    },
                )
                self.assertFalse(init_response["result"]["isError"])

                draft_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "create_draft_zettel",
                            "arguments": {
                                "archive_root": str(archive_root),
                                "title": "MCP draft note",
                                "body": "# MCP draft note\n\nCreated by a test.",
                                "facets": {"domain": "test"},
                            },
                        },
                    },
                )
                self.assertFalse(draft_response["result"]["isError"])
                relative_path = draft_response["result"]["structuredContent"]["path"]
                self.assertTrue(relative_path.startswith("inbox"))
                self.assertNotIn("\\", relative_path)
                self.assertTrue((archive_root / relative_path).is_file())

                read_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {
                            "name": "read_zettel",
                            "arguments": {
                                "archive_root": str(archive_root),
                                "path": relative_path.replace("/", "\\"),
                            },
                        },
                    },
                )
                self.assertFalse(read_response["result"]["isError"])
                self.assertEqual(read_response["result"]["structuredContent"]["path"], relative_path)
        finally:
            self.stop_server(process)

    def test_create_draft_zettel_dry_run_writes_no_file(self) -> None:
        process = self.start_server()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                archive_root = Path(tmp) / "archive"
                init_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "archive_init",
                            "arguments": {
                                "archive_root": str(archive_root),
                                "archive_type": "personal",
                                "archive_id": "archive:personal:mcp-dry-run",
                                "principal_id": "person:mcp-dry-run",
                                "principal_name": "MCP Dry Run",
                            },
                        },
                    },
                )
                self.assertFalse(init_response["result"]["isError"])

                draft_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "create_draft_zettel",
                            "arguments": {
                                "archive_root": str(archive_root),
                                "title": "MCP dry-run draft",
                                "body": "Safe MCP draft body.",
                                "dry_run": True,
                                "expected_archive_id": "archive:personal:mcp-dry-run",
                                "expected_type": "personal",
                                "profile_context": {
                                    "profile_id": "profile:personal:mcp",
                                    "operator_id": "person:mcp-dry-run",
                                    "authority_mode": "draft_only",
                                },
                                "creation_mode": "ai_assisted",
                                "created_by": "ai_runtime:codex",
                                "source": "user_conversation",
                                "assisted_by": ["ai_runtime:codex"],
                                "supervised_by": ["person:mcp-dry-run"],
                                "derived_from": ["object:mcp-source"],
                                "source_refs": [
                                    {"type": "local_ai_session", "value": "session:mcp-dry-run", "role": "prompt_context"}
                                ],
                                "local_ai_sessions": [
                                    {
                                        "runtime": "codex",
                                        "session_ref": "session:mcp-dry-run",
                                        "profile_id": "profile:personal:mcp",
                                        "archive_id": "archive:personal:mcp-dry-run",
                                        "authority_mode": "draft_only",
                                    }
                                ],
                                "draft_id": "zet_20260524_mcp_dry_run",
                                "created_at": "2026-05-24T03:04:05+09:00",
                            },
                        },
                    },
                )
                self.assertFalse(draft_response["result"]["isError"])
                result = draft_response["result"]["structuredContent"]
                self.assertTrue(result["dry_run"])
                self.assertEqual(result["proposed_path"], "inbox/zet_20260524_mcp_dry_run.md")
                self.assertFalse((archive_root / result["proposed_path"]).exists())
        finally:
            self.stop_server(process)

    def test_create_draft_zettel_dry_run_blocks_ai_mode_without_assisted_by(self) -> None:
        process = self.start_server()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                archive_root = Path(tmp) / "archive"
                init_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "archive_init",
                            "arguments": {
                                "archive_root": str(archive_root),
                                "archive_type": "personal",
                                "archive_id": "archive:personal:mcp-ai-identity",
                                "principal_id": "person:mcp-ai-identity",
                                "principal_name": "MCP AI Identity",
                            },
                        },
                    },
                )
                self.assertFalse(init_response["result"]["isError"])

                draft_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "create_draft_zettel",
                            "arguments": {
                                "archive_root": str(archive_root),
                                "title": "MCP AI identity draft",
                                "body": "Safe MCP draft body.",
                                "dry_run": True,
                                "creation_mode": "ai_assisted",
                                "created_by": "mcp:zettel-kasten-archive-mcp",
                            },
                        },
                    },
                )
                self.assertFalse(draft_response["result"]["isError"])
                result = draft_response["result"]["structuredContent"]
                self.assertFalse(result["ok"])
                self.assertIn("assisting AI runtime", "; ".join(result["blockers"]))
                self.assertEqual(list((archive_root / "inbox").glob("*.md")), [])
        finally:
            self.stop_server(process)

    def test_create_draft_zettel_normal_mode_writes_profile_provenance_after_approval(self) -> None:
        process = self.start_server()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                archive_root = Path(tmp) / "archive"
                init_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "archive_init",
                            "arguments": {
                                "archive_root": str(archive_root),
                                "archive_type": "personal",
                                "archive_id": "archive:personal:mcp-approved",
                                "principal_id": "person:mcp-approved",
                                "principal_name": "MCP Approved",
                            },
                        },
                    },
                )
                self.assertFalse(init_response["result"]["isError"])
                body = "Approved MCP draft body."
                expected_hash = hashlib.sha256((body.rstrip() + "\n").encode("utf-8")).hexdigest()

                draft_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "create_draft_zettel",
                            "arguments": {
                                "archive_root": str(archive_root),
                                "title": "MCP approved draft",
                                "body": body,
                                "expected_archive_id": "archive:personal:mcp-approved",
                                "expected_type": "personal",
                                "profile_context": {
                                    "profile_id": "profile:personal:mcp",
                                    "operator_id": "person:mcp-approved",
                                    "authority_mode": "draft_only",
                                },
                                "creation_mode": "ai_assisted",
                                "created_by": "ai_runtime:codex",
                                "source": "user_conversation",
                                "assisted_by": ["ai_runtime:codex"],
                                "supervised_by": ["person:mcp-approved"],
                                "source_refs": [
                                    {"type": "local_ai_session", "value": "session:mcp-approved", "role": "prompt_context"}
                                ],
                                "local_ai_sessions": [
                                    {
                                        "runtime": "codex",
                                        "session_ref": "session:mcp-approved",
                                        "profile_id": "profile:personal:mcp",
                                        "archive_id": "archive:personal:mcp-approved",
                                        "authority_mode": "draft_only",
                                    }
                                ],
                                "draft_id": "zet_20260524_mcp_approved",
                                "created_at": "2026-05-24T04:05:06+09:00",
                                "expected_body_sha256": expected_hash,
                                "draft_approved_by": "person:mcp-approved",
                            },
                        },
                    },
                )
                self.assertFalse(draft_response["result"]["isError"])
                relative_path = draft_response["result"]["structuredContent"]["path"]
                draft_path = archive_root / relative_path
                self.assertTrue(draft_path.is_file())
                match = archive_cli.FRONTMATTER_RE.match(draft_path.read_text(encoding="utf-8"))
                self.assertIsNotNone(match)
                assert match is not None
                frontmatter = archive_cli.load_yaml(match.group(1))
                self.assertEqual(frontmatter["provenance"]["created_by"], "ai_runtime:codex")
                self.assertEqual(frontmatter["local_ai_sessions"][0]["profile_id"], "profile:personal:mcp")
                self.assertEqual(frontmatter["draft_creation"]["approved_body_sha256"], expected_hash)
        finally:
            self.stop_server(process)

    def test_read_zettel_rejects_escaping_paths(self) -> None:
        process = self.start_server()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                archive_root = Path(tmp) / "archive"
                init_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "archive_init",
                            "arguments": {
                                "archive_root": str(archive_root),
                                "archive_type": "personal",
                                "archive_id": "archive:personal:mcp-path-test",
                                "principal_id": "person:mcp-path-test",
                            },
                        },
                    },
                )
                self.assertFalse(init_response["result"]["isError"])

                read_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "read_zettel",
                            "arguments": {
                                "archive_root": str(archive_root),
                                "path": "../archive.yml",
                            },
                        },
                    },
                )
                self.assertTrue(read_response["result"]["isError"])
                self.assertIn("unsafe", read_response["result"]["structuredContent"]["error"])
        finally:
            self.stop_server(process)

    def test_archive_index_then_search_tool(self) -> None:
        process = self.start_server()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                archive_root = self.copy_fake_archive(Path(tmp) / "archive")
                index_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "archive_index",
                            "arguments": {"archive_root": str(archive_root)},
                        },
                    },
                )
                index_result = index_response["result"]
                self.assertFalse(index_result["isError"])
                self.assertEqual(index_result["structuredContent"]["index_path"], "db/archive-index.sqlite")

                search_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "archive_search",
                            "arguments": {"archive_root": str(archive_root), "query": "lunch"},
                        },
                    },
                )
                search_result = search_response["result"]
                self.assertFalse(search_result["isError"])
                self.assertGreaterEqual(search_result["structuredContent"]["count"], 1)
                first_path = search_result["structuredContent"]["results"][0]["path"]
                self.assertNotIn("\\", first_path)
        finally:
            self.stop_server(process)

    def test_promotion_check_dry_run_never_writes_canonical_memory(self) -> None:
        process = self.start_server()
        try:
            archive_root = KIT_ROOT / "examples" / "fake-life-archive"
            response = self.send(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "promotion_check",
                        "arguments": {
                            "archive_root": str(archive_root),
                            "path": "inbox/zet_20260519_draft_ai_lunch_note.md",
                        },
                    },
                },
            )
            result = response["result"]
            self.assertFalse(result["isError"])
            self.assertTrue(result["structuredContent"]["dry_run"])
            self.assertFalse(result["structuredContent"]["ok"])
            self.assertIn("receipt_preview", result["structuredContent"])
            self.assertIn("checklist", result["structuredContent"])
            self.assertEqual(
                result["structuredContent"]["proposed_receipt_path"],
                "receipts/promotion/zet_20260519_draft_ai_lunch_note.promotion.json",
            )
            self.assertFalse((archive_root / "zettels" / "zet_20260519_draft_ai_lunch_note.md").exists())
            self.assertFalse(
                (archive_root / "receipts" / "promotion" / "zet_20260519_draft_ai_lunch_note.promotion.json").exists()
            )
        finally:
            self.stop_server(process)

    def test_mint_zettel_check_dry_run_never_writes_files(self) -> None:
        process = self.start_server()
        try:
            archive_root = KIT_ROOT / "examples" / "fake-life-archive"
            response = self.send(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "mint_zettel_check",
                        "arguments": {
                            "archive_root": str(archive_root),
                            "path": "inbox/zet_20260519_draft_ai_lunch_note.md",
                        },
                    },
                },
            )
            result = response["result"]
            self.assertFalse(result["isError"])
            self.assertTrue(result["structuredContent"]["dry_run"])
            self.assertFalse(result["structuredContent"]["ok"])
            self.assertIn("receipt_preview", result["structuredContent"])
            self.assertIn("checklist", result["structuredContent"])
            self.assertEqual(
                result["structuredContent"]["proposed_mint_receipt_path"],
                "receipts/mint/zet_20260519_draft_ai_lunch_note.mint.json",
            )
            self.assertEqual(
                result["structuredContent"]["proposed_draft_snapshot_path"],
                "receipts/mint/drafts/zet_20260519_draft_ai_lunch_note.draft.md",
            )
            self.assertFalse((archive_root / "zettels" / "zet_20260519_draft_ai_lunch_note.md").exists())
            self.assertFalse((archive_root / "receipts" / "mint" / "zet_20260519_draft_ai_lunch_note.mint.json").exists())
            self.assertFalse(
                (archive_root / "receipts" / "mint" / "drafts" / "zet_20260519_draft_ai_lunch_note.draft.md").exists()
            )
        finally:
            self.stop_server(process)

    def test_share_check_dry_run_never_writes_receipts(self) -> None:
        process = self.start_server()
        try:
            archive_root = KIT_ROOT / "examples" / "fake-life-archive"
            response = self.send(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "share_check",
                        "arguments": {
                            "archive_root": str(archive_root),
                            "view": "view.fake.company.derived",
                            "target_archive": "archive:company:fake-blue",
                            "counterparty_id": "archive:company:fake-blue",
                            "counterparty_fingerprint": "SHA256:fake-company-blue",
                        },
                    },
                },
            )
            result = response["result"]
            self.assertFalse(result["isError"])
            structured = result["structuredContent"]
            self.assertTrue(structured["dry_run"])
            self.assertTrue(structured["ok"])
            self.assertEqual(structured["trust_gate"]["status"], "verified")
            self.assertEqual(len(structured["scope_gate"]["included"]), 1)
            self.assertFalse(structured["ownership_gate"]["ownership_transfer"])
            self.assertFalse((archive_root / structured["proposed_receipt_path"]).exists())
        finally:
            self.stop_server(process)

    def test_delegate_attest_anchor_checks_are_dry_run_only(self) -> None:
        process = self.start_server()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                source_root = self.copy_fake_archive(Path(tmp) / "source")
                target_root = self.copy_fake_archive_as_company_target(Path(tmp) / "target")
                delegate_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "delegate_zet_check",
                            "arguments": {
                                "archive_root": str(source_root),
                                "view": "view.fake.company.derived",
                                "target_archive": "archive:company:fake-blue",
                                "counterparty_id": "archive:company:fake-blue",
                                "counterparty_fingerprint": "SHA256:fake-company-blue",
                            },
                        },
                    },
                )
                delegate_result = delegate_response["result"]
                self.assertFalse(delegate_result["isError"])
                delegated = delegate_result["structuredContent"]
                self.assertTrue(delegated["ok"])
                self.assertEqual(delegated["lifecycle_action"], "delegate")
                self.assertEqual(len(delegated["delegated_zets"]), 1)
                self.assertFalse((source_root / delegated["proposed_delegate_receipt_path"]).exists())

                delegate_path = self.write_json_receipt(
                    target_root,
                    delegated["proposed_delegate_receipt_path"],
                    delegated["delegate_receipt_preview"],
                )
                attest_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "attest_zet_check",
                            "arguments": {
                                "archive_root": str(target_root),
                                "delegate_receipt": archive_cli.archive_relative_path(delegate_path, target_root),
                                "counterparty_id": "archive:personal:fake-life",
                                "counterparty_fingerprint": "SHA256:fake-user-primary",
                            },
                        },
                    },
                )
                attest_result = attest_response["result"]
                self.assertFalse(attest_result["isError"])
                attested = attest_result["structuredContent"]
                self.assertTrue(attested["ok"])
                self.assertEqual(attested["lifecycle_action"], "attest")
                self.assertEqual(attested["trust_gate"]["status"], "verified")
                self.assertFalse((target_root / attested["proposed_attestation_receipt_path"]).exists())

                attestation_path = self.write_json_receipt(
                    target_root,
                    attested["proposed_attestation_receipt_path"],
                    attested["attestation_receipt_preview"],
                )
                anchor_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {
                            "name": "anchor_zet_check",
                            "arguments": {
                                "archive_root": str(target_root),
                                "attestation_receipt": archive_cli.archive_relative_path(attestation_path, target_root),
                            },
                        },
                    },
                )
                anchor_result = anchor_response["result"]
                self.assertFalse(anchor_result["isError"])
                anchored = anchor_result["structuredContent"]
                self.assertTrue(anchored["ok"])
                self.assertEqual(anchored["lifecycle_action"], "anchor")
                self.assertEqual(len(anchored["anchored_zets"]), 1)
                self.assertFalse((target_root / anchored["proposed_anchor_metadata_path"]).exists())

                claimable_delegate_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 4,
                        "method": "tools/call",
                        "params": {
                            "name": "delegate_zet_check",
                            "arguments": {
                                "archive_root": str(source_root),
                                "view": "view.fake.company.derived",
                                "target_policy": "claimable_once",
                            },
                        },
                    },
                )
                claimable_delegate_result = claimable_delegate_response["result"]
                self.assertFalse(claimable_delegate_result["isError"])
                claimable_delegated = claimable_delegate_result["structuredContent"]
                self.assertTrue(claimable_delegated["ok"])
                self.assertIsNone(claimable_delegated["target_archive"])
                self.assertEqual(claimable_delegated["delegation_capability"]["target_policy"], "claimable_once")
                self.assertEqual(claimable_delegated["trust_gate"]["status"], "deferred_until_attestation")
                self.assertFalse((source_root / claimable_delegated["proposed_delegate_receipt_path"]).exists())

                claimable_delegate_path = self.write_json_receipt(
                    target_root,
                    claimable_delegated["proposed_delegate_receipt_path"],
                    claimable_delegated["delegate_receipt_preview"],
                )
                claimable_attest_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 5,
                        "method": "tools/call",
                        "params": {
                            "name": "attest_zet_check",
                            "arguments": {
                                "archive_root": str(target_root),
                                "delegate_receipt": archive_cli.archive_relative_path(claimable_delegate_path, target_root),
                                "counterparty_id": "archive:personal:fake-life",
                                "counterparty_fingerprint": "SHA256:fake-user-primary",
                            },
                        },
                    },
                )
                claimable_attest_result = claimable_attest_response["result"]
                self.assertFalse(claimable_attest_result["isError"])
                claimable_attested = claimable_attest_result["structuredContent"]
                self.assertTrue(claimable_attested["ok"])
                self.assertEqual(claimable_attested["claim_binding"]["claimed_by_archive"], "archive:company:fake-blue")
                self.assertEqual(claimable_attested["claim_binding"]["spent_state_after_attestation"], "spent_preview")
                self.assertFalse((target_root / claimable_attested["proposed_attestation_receipt_path"]).exists())

                claimable_attestation_path = self.write_json_receipt(
                    target_root,
                    claimable_attested["proposed_attestation_receipt_path"],
                    claimable_attested["attestation_receipt_preview"],
                )
                claimable_anchor_response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 6,
                        "method": "tools/call",
                        "params": {
                            "name": "anchor_zet_check",
                            "arguments": {
                                "archive_root": str(target_root),
                                "attestation_receipt": archive_cli.archive_relative_path(claimable_attestation_path, target_root),
                            },
                        },
                    },
                )
                claimable_anchor_result = claimable_anchor_response["result"]
                self.assertFalse(claimable_anchor_result["isError"])
                claimable_anchored = claimable_anchor_result["structuredContent"]
                self.assertTrue(claimable_anchored["ok"])
                self.assertEqual(claimable_anchored["claim_binding"]["target_policy"], "claimable_once")
                self.assertFalse((target_root / claimable_anchored["proposed_anchor_metadata_path"]).exists())
        finally:
            self.stop_server(process)

    def test_ownership_transfer_check_dry_run_never_writes_receipts(self) -> None:
        process = self.start_server()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                archive_root = self.init_transfer_ready_family_archive(Path(tmp) / "family-archive")
                response = self.send(
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "ownership_transfer_check",
                            "arguments": {
                                "archive_root": str(archive_root),
                                "new_owner": "person:child-template",
                                "operators_after": ["person:child-template"],
                                "approved_by": ["person:member-a", "person:member-b"],
                                "counterparty_id": "person:child-template",
                                "counterparty_fingerprint": "SHA256:example-child-primary",
                            },
                        },
                    },
                )
                result = response["result"]
                self.assertFalse(result["isError"])
                structured = result["structuredContent"]
                self.assertTrue(structured["dry_run"])
                self.assertTrue(structured["ok"])
                self.assertEqual(structured["trust_gate"]["status"], "verified")
                self.assertTrue(structured["ownership_gate"]["ownership_transfer"])
                self.assertEqual(structured["provider_change_plan"]["status"], "manual_required")
                self.assertEqual(structured["receipt_preview"]["action"], "transfer_archive_ownership")
                self.assertIn("provider_change_plan", structured["receipt_preview"])
                self.assertEqual(
                    archive_cli.validate_schema(
                        structured["receipt_preview"],
                        "ownership-transfer-receipt.schema.json",
                    ),
                    [],
                )
                for field in [
                    "scope_manifest",
                    "trust_gate",
                    "ownership_gate",
                    "lineage",
                    "operators_before",
                    "operators_after",
                ]:
                    self.assertIn(field, structured["receipt_preview"])
                self.assertFalse((archive_root / structured["proposed_receipt_path"]).exists())

                identity = archive_cli.load_yaml((archive_root / "archive-identity.yml").read_text(encoding="utf-8"))
                self.assertEqual(identity["ownership"]["owner_id"], "family:example-household")
        finally:
            self.stop_server(process)


if __name__ == "__main__":
    unittest.main()

