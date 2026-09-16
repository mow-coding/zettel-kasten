"""MCP grammar/projection/held routing only; mocked Git is not backup proof."""

import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wom_kit import exact_operation_manifest as exact
from wom_kit import git_backup_session_command as command
from wom_kit import mcp_server as mcp
from wom_kit import _mcp_session_transport as transport
from wom_kit import work_session_git_workflow as workflow


APP = "client_app_" + "a" * 32
ROUTE = "task_route_" + "b" * 32
SESSION = "work_session_" + "c" * 32
DIGEST = "sha256:" + "d" * 64
PRIVATE = "SYNTHETIC_PRIVATE_URL_PATH_LABEL"
TOOL = "git_backup_reconcile_plan"
FRESH = {"remote_name": "origin", "branch": "main", "credential_mode": "stored",
         "max_changes": 100000, "max_changed_bytes": 2147483648}


def result(mode):
    if mode == "preview":
        return {"ok": True, "status": "session_output_selection_classified", "ready_for_write": True,
                "manifest_sha256": DIGEST, "selected_output_count": 2, "backup_performed": False}
    return {"ok": True, "status": "session_outputs_backed_up", "backup_performed": True,
            "original_commit_verified": True, "current_claim_ownership_verified": True,
            "actor_completion_published": True, "original_operation_already_completed": mode == "resume",
            "execution_sha256": DIGEST, "common_final_receipt_sha256": DIGEST, "commit_count": 1,
            "selected_output_count": 2, "selected_receipt_count": 2, "excluded_change_count": 3,
            "domain_writer_reentered": False, "source_bytes_backed_up": False,
            "original_git_anchors": {"schema": "wom-kit/work-session-git-anchor-observation/v1",
                "status": "verified", "commit_count": 1, "commit_anchors_verified": True,
                "remote_ref_independently_verified": True},
            "operation_evidence": {"private": PRIVATE}, "archive_root": PRIVATE, "context_sha256": DIGEST}


def request(arguments, token="progress"):
    return {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
        "name": TOOL, "arguments": arguments, "_meta": {"progressToken": token}}}


class StringSubclass(str):
    pass


class DictSubclass(dict):
    def get(self, *_args):
        raise AssertionError("arbitrary mapping callback")


class Poison:
    def __eq__(self, _other):
        raise AssertionError("arbitrary equality callback")

    def __repr__(self):
        raise AssertionError("arbitrary repr callback")

    def public_document(self):
        raise AssertionError("arbitrary projection callback")


class PoisonKey(str):
    __hash__ = str.__hash__

    def __eq__(self, _other):
        raise AssertionError("arbitrary key equality callback")


class GitMcpGrammarTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.server = mcp.JsonRpcMcpServer()

    def arguments(self, mode="resume", **changes):
        values = dict(archive_root=str(self.root), mode=mode, client_app_ref=APP, task_route_ref=ROUTE)
        if mode in ("preview", "apply"):
            values["work_session_ref"] = SESSION
        if mode == "apply":
            values["reviewed_by"] = "person:synthetic-reviewer"
        values.update(changes)
        return values

    def assert_invalid(self, values):
        with patch.object(command, "dispatch_session_git_backup") as dispatch:
            response = self.server.handle_message(request(values))
        self.assertEqual(response["error"]["code"], -32602)
        dispatch.assert_not_called()
        self.assertNotIn(PRIVATE, json.dumps(response))

    def test_closed_schema_exact_fields_and_honest_description(self):
        tool = next(value for value in mcp.TOOL_DEFINITIONS if value["name"] == TOOL)
        schema = tool["inputSchema"]
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["properties"]), set(self.arguments("apply")) | set(FRESH))
        self.assertEqual(schema["properties"]["mode"]["enum"], ["preview", "apply", "resume", "review_original"])
        self.assertEqual(schema["properties"]["credential_mode"]["enum"], ["stored"])
        self.assertEqual(schema["properties"]["max_changes"]["maximum"], 100000)
        self.assertEqual(schema["properties"]["max_changed_bytes"]["maximum"], 2147483648)
        self.assertIn("null/default", tool["description"])
        self.assertIn("not a completed backup", tool["description"])
        self.assertIn("source-byte capture", tool["description"])

    def test_all_modes_once_same_adapter_with_transport_owned_callbacks(self):
        context = transport.SessionRequest("progress", lambda _value: True)
        token = transport._SESSION_REQUEST.set(context)
        self.addCleanup(lambda: transport._SESSION_REQUEST.reset(token))
        with patch.dict(os.environ, {mcp.MCP_ALLOWED_ROOTS_ENV: str(self.root)}):
            for mode in ("preview", "apply", "resume", "review_original"):
                for optional_session in (False, True) if mode in ("resume", "review_original") else (True,):
                    values = self.arguments(mode)
                    if mode in ("preview", "apply"):
                        values.update(FRESH)
                    elif optional_session:
                        values["work_session_ref"] = SESSION
                    raw = result(mode)
                    unchanged = copy.deepcopy(raw)
                    with patch.object(command, "dispatch_session_git_backup", return_value=raw) as dispatch:
                        response = self.server.handle_message(request(values))
                    dispatch.assert_called_once()
                    self.assertEqual(dispatch.call_args.args, (self.root,))
                    kwargs = dispatch.call_args.kwargs
                    self.assertEqual(kwargs["mode"], mode)
                    self.assertEqual(kwargs["options"], FRESH if mode in ("preview", "apply") else {})
                    self.assertEqual(kwargs["work_session_ref"], SESSION if optional_session else None)
                    self.assertEqual(kwargs["reviewer_claim"], "person:synthetic-reviewer" if mode == "apply" else None)
                    self.assertEqual(kwargs["progress"], context.progress)
                    self.assertEqual(kwargs["cancel_requested"], context.cancel_requested)
                    public = response["result"]["structuredContent"]
                    self.assertFalse(response["result"]["isError"])
                    self.assertEqual(public["backup_completion_verified"], mode != "preview")
                    self.assertEqual(raw, unchanged)  # CLI's raw object is never rewritten.
                    self.assertNotIn(str(self.root), json.dumps(response))
                    self.assertNotIn(PRIVATE, json.dumps(response))

    def test_original_forbids_presence_of_every_fresh_value_and_reviewer(self):
        for mode in ("resume", "review_original"):
            for key, default in {**FRESH, "reviewed_by": "person:synthetic-reviewer"}.items():
                for value in (default, None, "", False, {}, []):
                    self.assert_invalid(self.arguments(mode, **{key: value}))

    def test_extra_authority_and_nested_option_inputs_refused_before_domain(self):
        for key in ("native", "key_provider", "claim", "context", "progress", "cancel_requested",
                    "approval_id", "execution_sha256", "expected_plan_sha256", "manifest", "selection",
                    "reviewer_claim", "options", "target_work_session_ref", "force"):
            self.assert_invalid(self.arguments("apply", **{key: PRIVATE}))

    def test_exact_primitive_grammar_and_required_mode_fields(self):
        for key in ("archive_root", "mode", "client_app_ref", "task_route_ref", "work_session_ref", "reviewed_by"):
            for value in (None, True, 1, 1.0, [], {}, "", " ", StringSubclass(PRIVATE)):
                values = self.arguments("apply")
                values[key] = value
                self.assert_invalid(values)
        for mode, key in (("apply", "reviewed_by"), ("apply", "work_session_ref"), ("preview", "work_session_ref"),
                          ("resume", "client_app_ref"), ("resume", "task_route_ref"), ("resume", "archive_root")):
            values = self.arguments(mode)
            del values[key]
            self.assert_invalid(values)
        self.assert_invalid(self.arguments("preview", reviewed_by="person:synthetic-reviewer"))
        self.assert_invalid(self.arguments(mode="unknown"))
        self.assert_invalid(DictSubclass(self.arguments()))
        values = self.arguments()
        values[StringSubclass("extra")] = PRIVATE
        self.assert_invalid(values)

    def test_numeric_bounds_exact_integers_and_stored_credentials_only(self):
        for key, limit in (("max_changes", 100000), ("max_changed_bytes", 2147483648)):
            for value in (True, False, None, 1.0, "1", 0, -1, limit + 1, 10 ** 10000):
                self.assert_invalid(self.arguments("preview", **{key: value}))
            for value in (1, limit):
                with patch.object(command, "dispatch_session_git_backup", return_value=result("preview")) as dispatch:
                    response = self.server.handle_message(request(self.arguments("preview", **{key: value})))
                self.assertFalse(response["result"]["isError"])
                self.assertEqual(dispatch.call_args.kwargs["options"], {key: value})
        for mode in ("prompt", "none", "", None, {}, StringSubclass("stored")):
            self.assert_invalid(self.arguments("preview", credential_mode=mode))

    def test_total_ascii_json_budget_metadata_and_root_allowlist(self):
        for values in (self.arguments("preview", branch="x" * 65536),
                       self.arguments("preview", branch="\uac00" * 11000),
                       self.arguments("preview", branch="x" * 33000, remote_name="y" * 33000)):
            self.assert_invalid(values)
        values = self.arguments("preview")
        values["branch"] = "x"
        overhead = len(json.dumps(values, ensure_ascii=True).encode("utf-8")) - 1
        values["branch"] = "x" * (65536 - overhead)
        with patch.object(command, "dispatch_session_git_backup", return_value=result("preview")) as dispatch:
            self.assertFalse(self.server.handle_message(request(values))["result"]["isError"])
        dispatch.assert_called_once()
        values["branch"] += "x"
        self.assert_invalid(values)
        for invalid in (False, None, 1.25, {}, []):
            with patch.object(command, "dispatch_session_git_backup") as dispatch:
                response = self.server.handle_message(request(self.arguments(), token=invalid))
            self.assertEqual(response["error"]["code"], -32602)
            dispatch.assert_not_called()
        with patch.dict(os.environ, {mcp.MCP_ALLOWED_ROOTS_ENV: str(self.root)}), \
             patch.object(command, "dispatch_session_git_backup") as dispatch:
            response = self.server.handle_message(request(self.arguments(archive_root=str(self.root.parent / PRIVATE))))
        self.assertTrue(response["result"]["isError"])
        dispatch.assert_not_called()
        self.assertNotIn(PRIVATE, json.dumps(response))
        self.assertNotIn(str(self.root), json.dumps(response))


class GitMcpProjectionTests(unittest.TestCase):
    def test_closed_flat_result_ignores_private_nested_and_duck_values(self):
        raw = result("resume")
        raw.update(path=Poison(), private_context=Poison(), plan=Poison(), remote_url=PRIVATE)
        public = command._project_mcp_git_backup_result(raw, mode="resume")
        self.assertTrue(public["backup_completion_verified"])
        self.assertTrue(public["commit_anchors_verified"])
        self.assertTrue(public["remote_ref_independently_verified"])
        self.assertFalse(public["domain_writer_reentered"])
        self.assertNotIn("original_git_anchors", public)
        self.assertNotIn("context_sha256", public)
        self.assertTrue(all(type(value) in (str, int, bool) for value in public.values()))
        self.assertNotIn(PRIVATE, json.dumps(public))
        for value in (Poison(), DictSubclass(), [], None):
            public = command._project_mcp_git_backup_result(value, mode="resume")
            self.assertFalse(public["ok"])
            self.assertFalse(public["backup_completion_verified"])
        for field in ("status", "reason_code", "effects_state", "execution_sha256", "selected_output_count",
                      "original_commit_verified", "original_git_anchors"):
            raw = result("resume")
            raw[field] = Poison()
            json.dumps(command._project_mcp_git_backup_result(raw, mode="resume"))

    def test_nonexact_mapping_keys_never_invoke_colliding_equality(self):
        for key in ("effects_state", "ok", "reason_code"):
            raw = {PoisonKey(key): PRIVATE}
            public = command._project_mcp_git_backup_result(raw, mode="resume")
            self.assertFalse(public["ok"])
            self.assertNotIn(PRIVATE, json.dumps(public))
        for key in ("schema", "status", "commit_count"):
            raw = result("resume")
            raw["original_git_anchors"] = {PoisonKey(key): PRIVATE}
            public = command._project_mcp_git_backup_result(raw, mode="resume")
            self.assertFalse(public["ok"])
            self.assertFalse(public["backup_completion_verified"])
            self.assertNotIn(PRIVATE, json.dumps(public))

    def test_no_eligible_and_incomplete_success_do_not_claim_backup_completion(self):
        for status in ("no_eligible_receipts", "no_eligible_session_outputs"):
            raw = {"ok": True, "status": status, "ready_for_write": False, "backup_performed": False,
                   "snapshot_partition_complete": True, "selected_output_count": 0}
            public = command._project_mcp_git_backup_result(raw, mode="apply")
            self.assertTrue(public["ok"])
            self.assertFalse(public["backup_completion_verified"])
            self.assertFalse(public["backup_performed"])
            self.assertEqual(public["effects_state"], "none")
        for field in ("original_commit_verified", "current_claim_ownership_verified", "actor_completion_published",
                      "execution_sha256", "common_final_receipt_sha256", "original_git_anchors", "commit_count"):
            raw = result("resume")
            del raw[field]
            public = command._project_mcp_git_backup_result(raw, mode="resume")
            self.assertFalse(public["ok"])
            self.assertFalse(public["backup_completion_verified"])
        for field, value in (("commit_count", True), ("commit_count", 2), ("status", "remote_mismatch"),
                             ("schema", PRIVATE), ("remote_ref_independently_verified", False)):
            raw = result("resume")
            raw["original_git_anchors"][field] = value
            self.assertFalse(command._project_mcp_git_backup_result(raw, mode="resume")["backup_completion_verified"])

    def test_fixed_failure_keeps_old_commit_separate_and_rejects_invalid_output_values(self):
        raw = command._failure("work_session_git_ownership_unavailable", mode="resume", effects_started=True,
                               original_commit_verified=True)
        public = command._project_mcp_git_backup_result(raw, mode="resume")
        self.assertFalse(public["ok"])
        self.assertFalse(public["backup_completion_verified"])
        self.assertTrue(public["original_commit_verified"])
        self.assertEqual(public["reason_code"], "work_session_git_ownership_unavailable")
        for field, values in (("selected_output_count", (True, -1, 100001, 1.0, 10 ** 10000)),
                              ("execution_sha256", (PRIVATE, StringSubclass(DIGEST), DIGEST.upper())),
                              ("source_bytes_backed_up", (1, "true", [], {}))):
            for value in values:
                raw = result("resume")
                raw[field] = value
                public = command._project_mcp_git_backup_result(raw, mode="resume")
                self.assertNotIn(field, public)
        raw = {"ok": False, "reason_code": PRIVATE, "status": PRIVATE}
        public = command._project_mcp_git_backup_result(raw, mode="resume")
        self.assertEqual(public["reason_code"], "work_session_git_command_unavailable")
        self.assertNotIn(PRIVATE, json.dumps(public))


class GitMcpHeldRoutingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / "archive.yml").write_text("archive_id: archive:personal:git-command-fixture\n", encoding="utf-8")

    def arguments(self, mode):
        values = dict(archive_root=str(self.root), mode=mode, client_app_ref=APP, task_route_ref=ROUTE)
        if mode in ("preview", "apply"):
            values["work_session_ref"] = SESSION
        if mode == "apply":
            values["reviewed_by"] = "person:synthetic-reviewer"
        return values

    def test_each_mode_retains_real_shared_runtime_and_same_archive_held_lock(self):
        helds, roots = [], []
        original = command.sessions._runtime_guard
        def guard(root):
            roots.append(root)
            return original(root)
        for mode, name in (("preview", "_preview_session_git_backup_held"), ("apply", "_execute_session_git_backup_held"),
                           ("resume", "_resume_session_git_backup_held"), ("review_original", "_review_original_session_git_backup_held")):
            def run(root, *, held, **kwargs):
                self.assertEqual(root, self.root)
                self.assertIs(type(held), exact.ExactOperationWriterLock)
                held.verify_held()
                helds.append(held)
                return result(mode)
            with patch.object(workflow, name, side_effect=run) as domain, \
                 patch.object(command.sessions, "_runtime_guard", side_effect=guard):
                response = mcp.tool_git_backup_reconcile_plan(self.arguments(mode))
            domain.assert_called_once()
            self.assertFalse(response["isError"])
        self.assertEqual(roots, [self.root] * 4)
        for held in helds:
            with self.assertRaises(exact.ExactOperationManifestError):
                held.verify_held()

    def test_runtime_and_observed_wait_cancel_block_before_domain_privately(self):
        with patch.object(workflow, "_resume_session_git_backup_held") as domain:
            with patch.object(command.sessions, "_runtime_guard", side_effect=command.sessions.WorkSessionServiceError("project_runtime_mismatch")):
                response = mcp.tool_git_backup_reconcile_plan(self.arguments("resume"))
            self.assertEqual(response["structuredContent"]["reason_code"], "project_runtime_mismatch")
            context = transport.SessionRequest(None, lambda _value: True)
            context.cancel()
            token = transport._SESSION_REQUEST.set(context)
            try:
                response = mcp.tool_git_backup_reconcile_plan(self.arguments("resume"))
            finally:
                transport._SESSION_REQUEST.reset(token)
            domain.assert_not_called()
        self.assertEqual(response["structuredContent"]["reason_code"], "work_session_wait_cancelled")
        self.assertEqual(response["structuredContent"]["effects_state"], "none")
        self.assertFalse(response["structuredContent"]["backup_completion_verified"])
        self.assertNotIn(str(self.root), json.dumps(response))


if __name__ == "__main__":
    unittest.main()
