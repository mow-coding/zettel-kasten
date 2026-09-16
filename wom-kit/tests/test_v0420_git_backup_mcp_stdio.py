"""Actual new-process Git MCP wait/cancel, not Git backup or UI acceptance.

The foreign archive OS lock stays held through a later serial response. Thus
the shared admission boundary cannot yield to Git planning, keys or native UI.
No reached domain function is replaced. This does not instrument individual
provider calls, prove installed-wheel behavior, or establish a timing SLO.
"""

import json
import unittest

from wom_kit import exact_operation_manifest as exact

import test_v0420_mcp_session_stdio as existing


APP = "client_app_" + "a" * 32
ROUTE = "task_route_" + "b" * 32
SESSION = "work_session_" + "c" * 32


class GitMcpStdioTests(unittest.TestCase):
    def test_actual_process_git_wait_readonly_bypass_and_ordered_cancellation(self):
        # Composition reuses only the existing process/lock fixture; its two
        # test cases are not inherited or silently counted as Git coverage.
        fixture = existing.McpSessionStdioTests(methodName="runTest")
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        peer = fixture.peer()
        holder, release = fixture.hold_archive()
        before = fixture.private_files()

        def git(request_id, token, mode):
            arguments = {"archive_root": str(fixture.root), "mode": mode,
                         "client_app_ref": APP, "task_route_ref": ROUTE}
            if mode == "preview":
                arguments["work_session_ref"] = SESSION
            peer.request(request_id, "tools/call", {"name": "git_backup_reconcile_plan",
                "arguments": arguments, "_meta": {"progressToken": token}})

        git(20, "git-wait", "preview")
        peer.until(lambda row: row.get("params", {}).get("message") == "git-backup: starting", 10)
        peer.until(lambda row: row.get("params", {}).get("message") == "git-backup: waiting_for_writer", 10)
        self.assertIsNone(holder.poll())
        peer.request(21, "ping")
        self.assertEqual(peer.result(21)["result"], {})
        peer.request(22, "tools/list")
        names = {item["name"] for item in peer.result(22)["result"]["tools"]}
        self.assertIn("git_backup_reconcile_plan", names)
        peer.request(23, "tools/call", {"name": "archive_work_session", "arguments": {
            "archive_root": str(fixture.root), "kind": "app"}})
        self.assertTrue(peer.result(23)["result"]["structuredContent"]["ok"])

        git(26, "queued-original", "resume")
        peer.until(lambda row: row.get("params", {}).get("progressToken") == "queued-original", 10)
        peer.send({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 26}})
        peer.send({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {
            "requestId": 20, "reason": "SYNTHETIC_PRIVATE_CANCEL_REASON"}})

        # Unlike ping, this existing preview is not a reader bypass. Its
        # response proves the active cancelled Git call retired in FIFO order.
        fixture.manage(peer, 24, {"action": "register-app", "dry_run": True,
                                  "request": {"label": existing.PRIVATE_LABEL}})
        barrier = peer.result(24, 10)["result"]["structuredContent"]
        self.assertTrue(barrier["ok"])
        self.assertEqual(fixture.private_files(), before)
        self.assertIsNone(holder.poll())
        with self.assertRaisesRegex(exact.ExactOperationManifestError, "exact_operation_writer_busy"):
            with exact.ExactOperationWriterLock(fixture.root, timeout_seconds=0):
                self.fail("cancellation released the foreign archive lock")
        ids = [row.get("id") for _observed, row in peer.history]
        self.assertNotIn(20, ids)
        self.assertNotIn(26, ids)
        progress = [row["params"] for _observed, row in peer.history
                    if row.get("params", {}).get("progressToken") == "git-wait"]
        self.assertGreaterEqual(len(progress), 2)
        self.assertTrue(all(right["progress"] > left["progress"]
                            for left, right in zip(progress, progress[1:])))
        self.assertTrue(all(set(row) <= {"progressToken", "progress", "message"} for row in progress))

        peer.close()
        self.assertEqual(peer.process.returncode, 0)
        self.assertEqual(peer.errors, [])
        self.assertEqual(fixture.private_files(), before)
        release()
        self.assertEqual(holder.returncode, 0)
        output = json.dumps([row for _observed, row in peer.history])
        for private in (str(fixture.root), existing.PRIVATE_LABEL, "SYNTHETIC_PRIVATE_CANCEL_REASON"):
            self.assertNotIn(private, output)


if __name__ == "__main__":
    unittest.main()
