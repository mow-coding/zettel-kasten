"""Batch MCP grammar and shared-record compatibility, not writer acceptance.

Mocked domain results test routing/projection only. Actual batch and record
journeys remain separate; no synthetic result here grants approval authority.
"""

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wom_kit import exact_operation_manifest as exact
from wom_kit import mcp_server as mcp
from wom_kit import _mcp_session_transport as transport
from wom_kit import source_intake_session_command as command
from wom_kit import work_session_source_intake_workflow as workflow


APP = "client_app_" + "a" * 32
ROUTE = "task_route_" + "b" * 32
SESSION = "work_session_" + "c" * 32
DIGEST = "sha256:" + "d" * 64
PRIVATE = "SYNTHETIC_PRIVATE_BATCH_PATH_LABEL"
TOOL = "source_intake_batch"


def raw_result(mode):
    if mode == "preview":
        return {"ok": True, "ready_for_write": True, "manifest_sha256": DIGEST,
                "item_count": 2, "writes_performed": False}
    return {"ok": True, "original_completion_verified": True, "completion_authentication_verified": True,
            "independent_verification": True, "execution_sha256": DIGEST, "common_final_receipt_sha256": DIGEST,
            "completed_item_count": 2, "prepared_capture_request_verified": True,
            "artifact_capture_performed": False, "requires_new_capture_approval": True}


def request(arguments, *, tool=TOOL, token="progress"):
    return {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
        "name": tool, "arguments": arguments, "_meta": {"progressToken": token}}}


class StringSubclass(str):
    pass


class PoisonKey(str):
    __hash__ = str.__hash__

    def __eq__(self, _other):
        raise AssertionError("arbitrary key comparison")


class DictSubclass(dict):
    def get(self, *_args):
        raise AssertionError("arbitrary mapping callback")


class PrivateObject:
    def __repr__(self):
        raise AssertionError("arbitrary repr callback")

    def public_document(self):
        raise AssertionError("arbitrary projection callback")


class BatchMcpGrammarTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.server = mcp.JsonRpcMcpServer()

    def arguments(self, mode="resume", **changes):
        values = dict(archive_root=str(self.root), mode=mode, client_app_ref=APP, task_route_ref=ROUTE)
        if mode in ("preview", "apply"):
            values.update(work_session_ref=SESSION, manifest="private-input.json")
        if mode == "apply":
            values["reviewed_by"] = "person:synthetic-reviewer"
        values.update(changes)
        return values

    def invalid(self, values, *, tool=TOOL):
        with patch.object(command, "dispatch_session_source_intake") as batch, \
             patch.object(command, "dispatch_session_source_intake_record") as record:
            response = self.server.handle_message(request(values, tool=tool))
        self.assertEqual(response["error"]["code"], -32602)
        batch.assert_not_called()
        record.assert_not_called()
        self.assertNotIn(PRIVATE, json.dumps(response))

    def test_batch_schema_is_closed_and_record_definition_bytes_are_unchanged(self):
        tool = next(row for row in mcp.TOOL_DEFINITIONS if row["name"] == TOOL)
        schema = tool["inputSchema"]
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["properties"]), set(self.arguments("apply")))
        self.assertEqual(schema["properties"]["mode"]["enum"], ["preview", "apply", "resume"])
        self.assertIn("does not capture source bytes", tool["description"])
        self.assertIn("including null", tool["description"])
        self.assertIn("No replacement approval", tool["description"])
        record = next(row for row in mcp.TOOL_DEFINITIONS if row["name"] == "source_intake_record")
        raw = (json.dumps(record, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        # Existing record name/schema/description/annotations, not a newly
        # generated self-comparison or a relaxed predecessor fixture.
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         "d26272794b97c5acd09db5afd0251887183b40bf2e851964752a5cca3ecd3748")

    def test_all_modes_call_batch_once_with_only_transport_callbacks_and_original_optional_session(self):
        context = transport.SessionRequest("progress", lambda _value: True)
        token = transport._SESSION_REQUEST.set(context)
        self.addCleanup(lambda: transport._SESSION_REQUEST.reset(token))
        for mode in ("preview", "apply", "resume"):
            for session in (False, True) if mode == "resume" else (True,):
                values = self.arguments(mode)
                if session:
                    values["work_session_ref"] = SESSION
                public = command._public_result(raw_result(mode), mode=mode)
                with patch.object(command, "dispatch_session_source_intake", return_value=public) as batch, \
                     patch.object(command, "dispatch_session_source_intake_record") as record:
                    response = self.server.handle_message(request(values))
                batch.assert_called_once()
                record.assert_not_called()
                self.assertEqual(batch.call_args.args, (self.root,))
                values = batch.call_args.kwargs
                self.assertEqual(set(values), {"mode", "client_app_ref", "task_route_ref", "work_session_ref",
                                              "request_path", "reviewer_claim", "progress", "cancel_requested"})
                self.assertEqual(values["request_path"], None if mode == "resume" else self.root / "private-input.json")
                self.assertEqual(values["work_session_ref"], SESSION if session else None)
                self.assertEqual(values["reviewer_claim"], "person:synthetic-reviewer" if mode == "apply" else None)
                self.assertEqual(values["progress"], context.progress)
                self.assertEqual(values["cancel_requested"], context.cancel_requested)
                self.assertIs(response["result"]["structuredContent"], public)
                self.assertFalse(response["result"]["isError"])
                self.assertNotIn(str(self.root), json.dumps(response))

    def test_new_fresh_requirements_and_original_presence_rejection_precede_domain(self):
        for mode in ("preview", "apply"):
            for key in ("manifest", "work_session_ref") + (("reviewed_by",) if mode == "apply" else ()):
                values = self.arguments(mode)
                del values[key]
                self.invalid(values)
        for key in ("manifest", "reviewed_by"):
            for value in (None, "", " ", PRIVATE, False, {}, []):
                self.invalid(self.arguments("resume", **{key: value}))
        self.invalid(self.arguments("preview", reviewed_by="person:synthetic-reviewer"))
        self.invalid(self.arguments("review_original"))

    def test_exact_primitives_keys_and_total_byte_budget(self):
        for key in self.arguments("apply"):
            for value in (None, False, 1, 1.0, [], {}, "", " ", StringSubclass(PRIVATE)):
                values = self.arguments("apply")
                values[key] = value
                self.invalid(values)
        self.invalid(DictSubclass(self.arguments()))
        self.invalid({PoisonKey("mode"): "resume"})
        for values in (self.arguments("preview", client_app_ref="x" * 65536),
                       self.arguments("preview", client_app_ref="\uac00" * 11000),
                       self.arguments("preview", client_app_ref="x" * 33000, task_route_ref="y" * 33000)):
            self.invalid(values)
        values = self.arguments("preview", client_app_ref="x")
        overhead = len(json.dumps(values, ensure_ascii=True).encode("utf-8")) - 1
        values["client_app_ref"] = "x" * (65536 - overhead)
        with patch.object(command, "dispatch_session_source_intake",
                          return_value=command._public_result(raw_result("preview"), mode="preview")) as batch:
            self.assertFalse(self.server.handle_message(request(values))["result"]["isError"])
        batch.assert_called_once()
        values["client_app_ref"] += "x"
        self.invalid(values)

    def test_cross_family_inputs_and_all_authority_knobs_are_rejected(self):
        for key in ("source_intake_plan", "plan_path", "request_path", "family", "native", "key_provider", "claim",
                    "context", "approval_id", "execution_sha256", "expected_plan_sha256", "review_original",
                    "progress", "cancel_requested", "reconcile", "capture", "options"):
            self.invalid(self.arguments("apply", **{key: PRIVATE}))
        record = self.arguments("apply")
        record["source_intake_plan"] = record.pop("manifest")
        record["manifest"] = PRIVATE
        self.invalid(record, tool="source_intake_record")
        for family in (None, False, [], {}, StringSubclass("batch"), "git", "record_extra"):
            with patch.object(command, "dispatch_session_source_intake") as batch, \
                 patch.object(command, "dispatch_session_source_intake_record") as record:
                with self.assertRaises(mcp.InvalidParamsError):
                    mcp._tool_session_source_intake(self.arguments(), family=family)
            batch.assert_not_called()
            record.assert_not_called()

    def test_allowed_archive_relative_and_absolute_manifest_paths_and_metadata(self):
        allowed = {mcp.MCP_ALLOWED_ROOTS_ENV: str(self.root)}
        for path in ("input.json", str(self.root / "input.json")):
            with patch.dict(os.environ, allowed), patch.object(command, "dispatch_session_source_intake",
                    return_value=command._public_result(raw_result("preview"), mode="preview")) as batch:
                response = self.server.handle_message(request(self.arguments("preview", manifest=path)))
            self.assertFalse(response["result"]["isError"])
            self.assertEqual(batch.call_args.kwargs["request_path"], self.root / "input.json")
            self.assertNotIn(str(self.root), json.dumps(response))
        for changes in ({"archive_root": str(self.root.parent / PRIVATE)},
                        {"manifest": str(self.root.parent / PRIVATE)}, {"manifest": "../" + PRIVATE}):
            with patch.dict(os.environ, allowed), patch.object(command, "dispatch_session_source_intake") as batch:
                response = self.server.handle_message(request(self.arguments("preview", **changes)))
            self.assertTrue(response["result"]["isError"])
            batch.assert_not_called()
            self.assertNotIn(PRIVATE, json.dumps(response))
            self.assertNotIn(str(self.root), json.dumps(response))
        for token in (None, False, 1.25, {}, []):
            with patch.object(command, "dispatch_session_source_intake") as batch:
                response = self.server.handle_message(request(self.arguments(), token=token))
            self.assertEqual(response["error"]["code"], -32602)
            batch.assert_not_called()

    def test_record_missing_fresh_and_empty_fields_keep_existing_structured_failures(self):
        cases = [
            (dict(mode="preview"), "work_session_intake_request_required"),
            (dict(mode="apply"), "work_session_intake_request_required"),
            (dict(mode="apply", source_intake_plan="input.json", work_session_ref=SESSION), "work_session_intake_reviewer_required"),
            (dict(mode="preview", source_intake_plan="input.json"), "work_session_task_context_required"),
            (dict(mode="preview", source_intake_plan="input.json", work_session_ref=SESSION, client_app_ref=""), "work_session_task_context_mismatch"),
            (dict(mode="apply", source_intake_plan="input.json", work_session_ref=SESSION, reviewed_by=" "), "work_session_intake_reviewer_required"),
        ]
        for changes, reason in cases:
            values = self.arguments()
            values.update(changes)
            with patch.object(command.sessions, "_write", side_effect=AssertionError("missing record field entered held domain")):
                response = self.server.handle_message(request(values, tool="source_intake_record"))
            self.assertNotIn("error", response)
            result = response["result"]
            self.assertTrue(result["isError"])
            self.assertEqual(result["content"], [{"type": "text", "text": "Source-intake record could not be completed."}])
            self.assertEqual(result["structuredContent"], command._failure(reason, mode=values["mode"]))

    def test_record_original_text_path_label_and_empty_plan_resolution_are_unchanged(self):
        original_path = mcp.require_path_arg
        for input_value in ("input.json", "", str(self.root / "input.json")):
            values = self.arguments("preview")
            values.pop("manifest")
            values["source_intake_plan"] = input_value
            expected = self.root if input_value == "" else self.root / "input.json"
            public = command._public_result({**raw_result("preview"), "item_count": 1}, mode="preview")
            with patch.object(command, "dispatch_session_source_intake_record", return_value=public) as record, \
                 patch.object(command, "dispatch_session_source_intake") as batch, \
                 patch.object(mcp, "require_path_arg", wraps=original_path) as paths:
                response = self.server.handle_message(request(values, tool="source_intake_record"))
            batch.assert_not_called()
            record.assert_called_once()
            self.assertEqual(record.call_args.kwargs["plan_path"], expected)
            self.assertEqual(paths.call_args.args, ({"plan": str(expected)}, "plan"))
            self.assertEqual(response["result"]["content"], [{"type": "text",
                "text": "Source-intake metadata record returned; source bytes are not captured."}])
            self.assertIs(response["result"]["structuredContent"], public)


class BatchMcpHeldRoutingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / "archive.yml").write_text("archive_id: archive:personal:batch-command-fixture\n", encoding="utf-8")

    def arguments(self, mode):
        values = dict(archive_root=str(self.root), mode=mode, client_app_ref=APP, task_route_ref=ROUTE)
        if mode != "resume":
            values.update(work_session_ref=SESSION, manifest="private-input.json")
        if mode == "apply":
            values["reviewed_by"] = "person:synthetic-reviewer"
        return values

    def test_all_modes_reuse_real_runtime_and_held_lock_with_unchanged_closed_projection(self):
        roots, helds = [], []
        original_guard = command.sessions._runtime_guard
        def guard(root):
            roots.append(root)
            return original_guard(root)
        for mode, name in (("preview", "_preview_session_source_intake_batch_held"),
                           ("apply", "_execute_session_source_intake_batch_held"),
                           ("resume", "_resume_session_source_intake_batch_held")):
            def run(root, *inputs, held, **kwargs):
                self.assertIs(type(held), exact.ExactOperationWriterLock)
                held.verify_held()
                helds.append(held)
                self.assertEqual(root, self.root)
                self.assertEqual(inputs, () if mode == "resume" else (self.root / "private-input.json",))
                return {**raw_result(mode), "private": PrivateObject(), "operation_evidence": {"path": PRIVATE}}
            with patch.object(workflow, name, side_effect=run) as domain, \
                 patch.object(command.sessions, "_runtime_guard", side_effect=guard):
                response = mcp.tool_source_intake_batch(self.arguments(mode))
            domain.assert_called_once()
            self.assertFalse(response["isError"])
            public = response["structuredContent"]
            self.assertEqual(public, command._public_result(raw_result(mode), mode=mode))
            self.assertNotIn(PRIVATE, json.dumps(response))
            self.assertNotIn(str(self.root), json.dumps(response))
        self.assertEqual(roots, [self.root] * 3)
        for held in helds:
            with self.assertRaises(exact.ExactOperationManifestError):
                held.verify_held()

    def test_runtime_and_observed_wait_cancel_refuse_before_domain(self):
        with patch.object(workflow, "_resume_session_source_intake_batch_held") as domain:
            with patch.object(command.sessions, "_runtime_guard", side_effect=command.sessions.WorkSessionServiceError("project_runtime_mismatch")):
                response = mcp.tool_source_intake_batch(self.arguments("resume"))
            self.assertEqual(response["structuredContent"]["reason_code"], "project_runtime_mismatch")
            context = transport.SessionRequest(None, lambda _value: True)
            context.cancel()
            token = transport._SESSION_REQUEST.set(context)
            try:
                response = mcp.tool_source_intake_batch(self.arguments("resume"))
            finally:
                transport._SESSION_REQUEST.reset(token)
            domain.assert_not_called()
        self.assertEqual(response["structuredContent"]["reason_code"], "work_session_wait_cancelled")
        self.assertEqual(response["structuredContent"]["effects_state"], "none")
        self.assertNotIn(str(self.root), json.dumps(response))


if __name__ == "__main__":
    unittest.main()
