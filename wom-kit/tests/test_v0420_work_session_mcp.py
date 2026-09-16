"""Real JSON-RPC routing and shared registry query without lifecycle writes."""

from contextlib import redirect_stdout, redirect_stderr
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wom_kit import archive_cli, mcp_server
from wom_kit import exact_human_approval as approval
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_registry as registry


class WorkSessionMcpTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="wom-session-mcp-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "archive"
        self.root.mkdir()
        archive_id = "archive:synthetic:work-session-mcp"
        (self.root / "archive.yml").write_text("archive_id: " + archive_id + "\n", encoding="utf-8")
        self.store = registry.WorkSessionRegistryStore(
            self.root, approval.exact_human_approval_archive_identity_sha256(archive_id),
        )
        for label in ("PRIVATE_MCP_FIRST", "PRIVATE_MCP_SECOND"):
            transition = registry.plan_transition(self.store.read(), action="register-app", label=label)
            with exact.ExactOperationWriterLock(self.root) as held:
                self.store.commit(transition, held_lock=held)
        self.server = mcp_server.JsonRpcMcpServer()
        self.environment = patch.dict(os.environ, {mcp_server.MCP_ALLOWED_ROOTS_ENV: str(self.root)})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def request(self, method, params=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            response = self.server.handle_message({"jsonrpc": "2.0", "id": 1, "method": method,
                                                   "params": {} if params is None else params})
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")
        return response

    def call(self, **arguments):
        return self.request("tools/call", {"name": "archive_work_session",
                                           "arguments": {"archive_root": str(self.root), **arguments}})

    def files(self):
        return {str(path.relative_to(self.root)): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()}

    def test_tools_list_exposes_only_read_contract_without_authority_injection(self):
        response = self.request("tools/list")
        tool, = [tool for tool in response["result"]["tools"] if tool["name"] == "archive_work_session"]
        self.assertTrue(tool["annotations"]["readOnlyHint"])
        self.assertFalse(tool["inputSchema"]["additionalProperties"])
        self.assertEqual(tool["inputSchema"]["properties"]["action"]["enum"], ["list", "inspect"])
        self.assertFalse({"native", "key_provider", "approve", "claim_ref", "reviewed_by"}
                         & set(tool["inputSchema"]["properties"]))

    def test_actual_cli_and_mcp_share_generation_filter_and_cursor_under_writer_lock(self):
        before = self.files()
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = archive_cli.main(["work-session", str(self.root), "--kind", "app", "--page-size", "1"])
        self.assertEqual(code, 0)
        cli = json.loads(stdout.getvalue())
        with exact.ExactOperationWriterLock(self.root) as held:
            response = self.call(kind="app", page_size=1)
            held.verify_held()
        self.assertFalse(response["result"]["isError"])
        self.assertEqual(response["result"]["structuredContent"], cli)
        second = self.call(kind="app", page_size=1, cursor=cli["pagination"]["next_cursor"])
        self.assertFalse(second["result"]["structuredContent"]["pagination"]["has_more"])
        self.assertNotEqual(second["result"]["structuredContent"]["items"], cli["items"])
        self.assertNotIn("PRIVATE_MCP", json.dumps([response, second]))
        self.assertNotIn(str(self.root), json.dumps([response, second]))
        self.assertEqual(before, self.files())

    def test_untrusted_fields_types_and_lifecycle_actions_fail_before_query(self):
        cases = ({"native": "PRIVATE_MARKER"}, {"key_provider": "PRIVATE_MARKER"},
                 {"approve": True}, {"claim_ref": "PRIVATE_MARKER"}, {"page_size": True},
                 {"page_size": 2001}, {"action": "create"}, {"kind": []}, {"cursor": None})
        before = self.files()
        for arguments in cases:
            with self.subTest(keys=list(arguments)):
                response = self.call(**arguments)
                self.assertEqual(response["error"]["code"], mcp_server.JSONRPC_INVALID_PARAMS)
                self.assertNotIn("PRIVATE_MARKER", json.dumps(response))
        self.assertEqual(before, self.files())

    def test_path_allowlist_and_bad_cursor_are_fixed_errors_and_no_effects(self):
        before = self.files()
        denied = self.call(archive_root=str(self.base))
        self.assertTrue(denied["result"]["isError"])
        self.assertNotIn(str(self.base), json.dumps(denied))
        invalid = self.call(cursor="PRIVATE_CURSOR")
        self.assertTrue(invalid["result"]["isError"])
        self.assertEqual(invalid["result"]["structuredContent"]["reason_code"], "snapshot_pagination_cursor_invalid")
        self.assertNotIn("PRIVATE_CURSOR", json.dumps(invalid))
        self.assertEqual(before, self.files())

    def test_stdio_contains_only_jsonrpc_responses(self):
        before = self.files()
        messages = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
                        "name": "archive_work_session", "arguments": {"archive_root": str(self.root), "kind": "app"}}}]
        stream = io.StringIO("\n".join(json.dumps(message) for message in messages) + "\n")
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stderr(stderr):
            self.assertEqual(self.server.serve(stream, stdout), 0)
        responses = [json.loads(line) for line in stdout.getvalue().splitlines()]
        self.assertEqual([row["id"] for row in responses], [1, 2])
        self.assertEqual(responses[1]["result"]["structuredContent"]["counts"]["selected"], 2)
        self.assertEqual(stderr.getvalue(), "")
        self.assertNotIn("PRIVATE_MCP", stdout.getvalue())
        self.assertEqual(before, self.files())


if __name__ == "__main__":
    unittest.main()
