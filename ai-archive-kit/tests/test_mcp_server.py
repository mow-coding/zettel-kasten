from __future__ import annotations

import json
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

from ai_archive_kit import archive_cli


class McpServerTests(unittest.TestCase):
    def start_server(self) -> subprocess.Popen[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        return subprocess.Popen(
            [sys.executable, "-m", "ai_archive_kit.mcp_server"],
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
            tool_names = {tool["name"] for tool in tools["result"]["tools"]}
            self.assertIn("archive_doctor", tool_names)
            self.assertIn("create_draft_zettel", tool_names)
            self.assertIn("archive_index", tool_names)
            self.assertIn("archive_search", tool_names)
            self.assertIn("promotion_check", tool_names)
            self.assertIn("share_check", tool_names)
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
            self.assertNotIn("promote_zettel", tool_names)
            self.assertNotIn("archive_promote", tool_names)
            self.assertNotIn("share_archive_scope", tool_names)
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

