"""Actual CLI/MCP scoped Git continuation with synthetic native/key/transport.

Public A/B registration, creation, claims and metadata recording are real;
Git uses an isolated bare remote. The reused fixture's legacy handoff
planning prerequisite alone is synthetic/read-only. Exception cuts are not
power-loss tests. In-process JSON-RPC is not stdio, timing or installed proof.
No source-byte custody or whole-archive backup is asserted.
"""

import json
import os
import unittest
from unittest.mock import patch

import test_v0420_source_intake_record_git_public_workflow as public_fixture
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import git_backup_writer as writer
from wom_kit import mcp_server as mcp
from wom_kit import work_session_actor as actor
from wom_kit import work_session_git_terminal as terminal


class GitBackupMcpPublicWorkflowTests(unittest.TestCase):
    def setUp(self):
        # Composition only: no inherited batch or record journey test methods.
        self.journey = public_fixture.SingleRecordGitPublicWorkflowTests("runTest")
        self.journey.setUp()
        self.addCleanup(self.journey.doCleanups)
        self.base = self.journey.base
        self.root, self.git = self.base.root, self.base.git
        self.server = mcp.JsonRpcMcpServer()
        self.request_id = 0
        self.mcp_results = []
        roots = patch.dict(os.environ, {mcp.MCP_ALLOWED_ROOTS_ENV: str(self.root)})
        roots.start()
        self.addCleanup(roots.stop)

    def call_mcp(self, case, *, mode, ok=True):
        task = case["a"]
        arguments = {"archive_root": str(self.root), "mode": mode,
                     "client_app_ref": task["app"], "task_route_ref": task["route"]}
        if mode == "apply":
            arguments.update(work_session_ref=task["session"], credential_mode="stored",
                             reviewed_by="person:synthetic-git-reviewer")
        self.request_id += 1
        response = self.server.handle_message({"jsonrpc": "2.0", "id": self.request_id,
            "method": "tools/call", "params": {"name": "git_backup_reconcile_plan", "arguments": arguments}})
        self.assertNotIn("error", response, response)
        self.assertEqual(response["id"], self.request_id)
        result = response["result"]
        self.assertIs(result["isError"], not ok, result)
        public = result["structuredContent"]
        self.assertIs(public["ok"], ok, result)
        self.assertEqual(public["schema"], "wom-kit/git-backup-session-command/v1")
        self.assertNotIn("original_git_anchors", public)
        self.assertIs(public["backup_completion_verified"], ok)
        if ok:
            self.assertTrue(public["commit_anchors_verified"] and public["remote_ref_independently_verified"])
            self.assertEqual(public["selected_output_count"], len(case["selected"]))
            self.assertEqual(public["selected_receipt_count"], len(case["selected"]))
        serialized = json.dumps(result)
        for marker in ("SYNTHETIC_PRIVATE", str(self.root), str(self.base.fixture.remote), case["generic"],
                       task["app"], task["route"], task["session"]):
            self.assertNotIn(marker, serialized)
        self.mcp_results.append(public)
        return public

    def remote_head(self):
        return self.base.fixture.git_dir(self.base.fixture.remote, "rev-parse", "refs/heads/main").stdout.strip()

    def register_unrelated_app_after_cut(self, case, original, pointer):
        # A and the existing B already have metadata. Register a third,
        # unrelated app only AFTER A's original Git approval scope was saved.
        before = self.base.store.read()
        pending = self.base.routing(case["a"])._read(current=False)._raw
        claims = {path.name: path.read_bytes() for path in
                  self.root.joinpath(approval.CLAIMS_RELATIVE_ROOT).glob("*.json")}
        native_calls, head, remote = self.base.native.calls, self.git("rev-parse", "HEAD").stdout, self.remote_head()
        frozen = writer._canonical(writer._bundle_document(original.prepared))
        label = "SYNTHETIC_PRIVATE_CONCURRENT_APP_C"
        preview = self.base.session_call("--action", "register-app", "--dry-run", "--request-stdin",
            request={"label": label})
        self.base.session_call("--action", "register-app", "--apply", "--request-stdin",
            request={"selection": preview, "label": label})
        after = self.base.store.read()
        self.assertNotIn(preview["client_app_ref"], (case["a"]["app"], case["b"]["app"]))
        self.assertNotEqual(before.sha256, after.sha256)
        self.assertEqual(original.prepared.session_scope.document()["registry_preimage_sha256"], before.sha256)
        for task in (case["a"], case["b"]):
            self.assertEqual(after.binding(task["session"]), before.binding(task["session"]))
        self.assertEqual(self.base.routing(case["a"])._read(current=False)._raw, pending)
        current, current_pointer = self.journey.verify_original_and_exclusions(case)
        self.assertEqual(current_pointer, pointer)
        self.assertEqual(current.context, original.context)
        self.assertEqual(writer._canonical(writer._bundle_document(current.prepared)), frozen)
        self.assertEqual({path.name: path.read_bytes() for path in
                          self.root.joinpath(approval.CLAIMS_RELATIVE_ROOT).glob("*.json")}, claims)
        self.assertEqual((self.base.native.calls, self.git("rev-parse", "HEAD").stdout, self.remote_head()),
                         (native_calls, head, remote))
        case["registry"] = after.sha256  # Expected live registry, never rewrite original evidence.

    def frozen_state(self):
        return {"files": self.base.files(), "index": self.git("ls-files", "--stage").stdout,
                "head": self.git("rev-parse", "HEAD").stdout.strip(), "remote": self.remote_head(),
                "native_calls": self.base.native.calls, "transport_calls": len(self.base.fixture.transport_commands)}

    def forbid_replay_effects(self):
        stack = self.journey.forbid_discovery()
        # The shared session-origin reader recomputes exact_terminal_record_mac
        # to compare the OLD receipt's MAC. Do not forbid that authentication;
        # forbid new Git terminal construction/publication and all domain writes.
        for owner, name in (
            (writer, "_run_git_backup_exact_operation"),
            (terminal, "_build_git_terminal_record"),
            (actor.WorkSessionActorStore, "save"),
            (windows, "_CtypesTaskDialogNative"),
            (broker, "_claim_exact_human_approval_core"),
        ):
            stack.enter_context(patch.object(owner, name, side_effect=AssertionError("read-only original replay")))
        return stack

    def assert_replay(self, case, call):
        # Original source files are deliberately removed only after real push.
        # Metadata-only historical verification must not recreate them.
        for intake in (case["intake_a"], case["intake_b"]):
            self.assertFalse(intake["request"].exists())
            (self.root / intake["source"]).unlink()
        before = self.frozen_state()
        with self.forbid_replay_effects():
            replay = call()
        self.assertTrue(replay["ok"] and replay["original_operation_already_completed"])
        self.assertTrue(replay["original_commit_verified"] and replay["current_claim_ownership_verified"])
        self.assertFalse(replay["domain_writer_reentered"])
        self.assertFalse(replay["artifact_backup_complete"] or replay["source_bytes_backed_up"])
        self.assertEqual(self.frozen_state(), before)
        return replay

    def test_cli_pre_push_cut_mcp_original_resume_cli_completed_replay(self):
        case = self.journey.prepare(common_tracked=True)
        with patch.object(writer._GitBackupBackend, "_push",
                          side_effect=RuntimeError("SYNTHETIC_PRIVATE_CLI_PUSH_CUT")) as cut:
            failed = self.base.call("git-backup-reconcile-plan", *case["a"]["refs"],
                "--work-session-ref", case["a"]["session"], "--approve", "--credential-mode", "stored",
                "--reviewed-by", "person:synthetic-git-reviewer", ok=False)
        self.assertEqual(cut.call_count, 1, failed)
        cut.assert_called_once()
        self.assertFalse(failed["backup_completion_verified"])
        committed = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertNotEqual(committed, case["baseline"])
        self.assertEqual(self.remote_head(), case["baseline"])
        original, pointer = self.journey.verify_original_and_exclusions(case)
        self.register_unrelated_app_after_cut(case, original, pointer)
        native_before = self.base.native.calls
        with self.journey.forbid_discovery(), \
             patch.object(writer._GitBackupBackend, "_commit_group", side_effect=AssertionError("second commit")), \
             patch.object(windows, "_CtypesTaskDialogNative", side_effect=AssertionError("new native decision")), \
             patch.object(broker, "_claim_exact_human_approval_core", side_effect=AssertionError("new claim")):
            completed = self.call_mcp(case, mode="resume")
        self.assertEqual(self.journey.verify_finished(case, completed, original, pointer), committed)
        self.assertEqual(self.base.native.calls, native_before)
        self.assert_replay(case, lambda: self.base.call("git-backup-reconcile-plan", *case["a"]["refs"], "--resume"))

    def test_mcp_preclaim_cut_cli_original_review_mcp_completed_replay(self):
        case = self.journey.prepare(common_tracked=False)
        with patch.object(broker, "_claim_exact_human_approval_core",
                          side_effect=RuntimeError("SYNTHETIC_PRIVATE_MCP_PRECLAIM_CUT")) as cut:
            failed = self.call_mcp(case, mode="apply", ok=False)
        self.assertEqual(cut.call_count, 1, failed)
        cut.assert_called_once()
        self.assertFalse(failed["backup_completion_verified"])
        original, pointer = self.journey.verify_original_and_exclusions(case)
        pending = self.base.routing(case["a"])._read(current=False)._raw
        self.assertEqual(set(self.root.joinpath(approval.CLAIMS_RELATIVE_ROOT).glob("*.json")), case["claims"])
        self.assertEqual(self.git("rev-parse", "HEAD").stdout.strip(), case["baseline"])
        self.assertEqual(self.remote_head(), case["baseline"])
        self.register_unrelated_app_after_cut(case, original, pointer)
        observed = []
        request_native = broker._request_exact_human_approval_core

        def review(context, **options):
            observed.append(approval.exact_human_approval_context_sha256(context))
            self.assertEqual(self.base.routing(case["a"])._read(current=False)._raw, pending)
            return request_native(context, **options)

        with self.journey.forbid_discovery(), patch.object(broker, "_request_exact_human_approval_core", side_effect=review):
            completed = self.base.call("git-backup-reconcile-plan", *case["a"]["refs"], "--approve", "--review-original")
        self.assertTrue(completed["native_approval_redisplayed"])
        self.assertEqual(observed, [pointer["context_sha256"]])
        self.journey.verify_finished(case, completed, original, pointer)
        self.assert_replay(case, lambda: self.call_mcp(case, mode="resume"))


if __name__ == "__main__":
    unittest.main()
