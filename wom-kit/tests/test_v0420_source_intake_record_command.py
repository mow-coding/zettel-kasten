"""Single-record grammar/transport only; mocked domain is not acceptance proof."""

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import inspect
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from wom_kit import archive_cli as cli
from wom_kit import cli_entry
from wom_kit import exact_operation_manifest as exact
from wom_kit import mcp_server as mcp
from wom_kit import _mcp_session_transport as transport
from wom_kit import source_intake_record_exact as legacy
from wom_kit import source_intake_session_command as command
from wom_kit import work_session_source_intake_record_workflow as workflow


APP = "client_app_" + "a" * 32
ROUTE = "task_route_" + "b" * 32
SESSION = "work_session_" + "c" * 32
DIGEST = "sha256:" + "d" * 64
PRIVATE = "SYNTHETIC_PRIVATE_RECORD_PATH"


def result(mode):
    if mode == "preview":
        return {"ok": True, "ready_for_write": True, "manifest_sha256": DIGEST,
                "item_count": 1, "writes_performed": False}
    return {"ok": True, "original_completion_verified": True, "completion_authentication_verified": True,
            "independent_verification": True, "execution_sha256": DIGEST, "common_final_receipt_sha256": DIGEST,
            "prepared_capture_request_created": False, "source_bytes_retained": False}


def request(request_id=1, token="progress", **changes):
    arguments = {"archive_root": PRIVATE, "mode": "resume", "client_app_ref": APP, "task_route_ref": ROUTE}
    arguments.update(changes)
    return {"jsonrpc": "2.0", "id": request_id, "method": "tools/call", "params": {
        "name": "source_intake_record", "arguments": arguments, "_meta": {"progressToken": token}}}


def progress_event(**changes):
    event = exact.ExactOperationProgress(
        manifest_sha256=PRIVATE, execution_sha256=PRIVATE, mode="apply", stage="field_verified",
        completed_items=0, total_items=1, completed_fields=0, total_fields=1,
    )
    return replace(event, **changes)


class RecordCliGrammarTests(unittest.TestCase):
    def call(self, flags):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["source-intake-record", PRIVATE, "--format", "json", *flags])
        return code, out.getvalue(), err.getvalue()

    def test_fresh_routes_use_single_plan_and_exact_refs_without_public_authority_knobs(self):
        for flag, mode in (("--dry-run", "preview"), ("--approve", "apply")):
            flags = [flag, "--client-app-ref", APP, "--task-route-ref", ROUTE, "--work-session-ref", SESSION,
                     "--source-intake-plan", PRIVATE, "--no-progress"]
            if mode == "apply":
                flags += ["--reviewed-by", "person:synthetic-reviewer"]
            with patch.object(command, "dispatch_session_source_intake_record", return_value=result(mode)) as dispatch, \
                 patch.object(command, "dispatch_session_source_intake", side_effect=AssertionError("batch route")):
                code, out, err = self.call(flags)
            self.assertEqual(code, 0, out)
            self.assertEqual(dispatch.call_args.kwargs["plan_path"], PRIVATE)
            self.assertEqual(dispatch.call_args.kwargs["mode"], mode)
            self.assertEqual(dispatch.call_args.kwargs["work_session_ref"], SESSION)
            self.assertNotIn("request_path", dispatch.call_args.kwargs)
            self.assertNotIn(PRIVATE, out + err)
        for name in ("native", "key_provider", "claim", "context", "approval_id", "expected_plan_sha256"):
            self.assertNotIn(name, inspect.signature(command.dispatch_session_source_intake_record).parameters)

    def test_original_resume_only_keeps_route_with_optional_session_and_assignment_syntax(self):
        for additional in ([], ["--work-session-ref=" + SESSION]):
            with patch.object(command, "dispatch_session_source_intake_record", return_value=result("resume")) as dispatch:
                code, out, err = self.call(["--client-app-ref=" + APP, "--task-route-ref=" + ROUTE,
                                          "--resume", "--no-progress", *additional])
            self.assertEqual(code, 0, out)
            values = dispatch.call_args.kwargs
            self.assertEqual(values["mode"], "resume")
            self.assertIsNone(values["plan_path"])
            self.assertIsNone(values["reviewer_claim"])
            self.assertEqual(values["work_session_ref"], SESSION if additional else None)
            self.assertNotIn(PRIVATE, out + err)

    def test_replacement_and_conflicting_flags_refuse_before_dispatch_without_private_echo(self):
        base = ["--client-app-ref", APP, "--task-route-ref", ROUTE, "--resume", "--no-progress"]
        for flags in (["--source-intake-plan", PRIVATE], ["--reviewed-by", PRIVATE],
                      ["--expected-plan-sha256", PRIVATE], ["--approve"], ["--dry-run"],
                      ["--resume-approval-id", PRIVATE], ["--review-original"], ["--manifest", PRIVATE]):
            with self.subTest(flags=flags), patch.object(command, "dispatch_session_source_intake_record") as dispatch:
                code, out, err = self.call(base + flags)
                self.assertNotEqual(code, 0)
                dispatch.assert_not_called()
                self.assertNotIn(PRIVATE, out + err)

    def test_conditional_missing_plan_preserves_legacy_rc2_and_legacy_dispatch(self):
        for flags in (["--dry-run"], ["--resume"], ["--client-app-ref", APP, "--dry-run"],
                      ["--client-app-ref", APP, "--approve"]):
            with patch.object(command, "dispatch_session_source_intake_record") as dispatch:
                code, out, err = self.call(flags)
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(out)["missing_arguments"], ["--source-intake-plan"])
            self.assertEqual(json.loads(out)["reason_codes"], ["cli_required_arguments_missing"])
            self.assertEqual(err, "")
            dispatch.assert_not_called()
        plan = unittest.mock.Mock()
        plan.public_document.return_value = {"ok": True}
        plan.approveable = True
        with patch.object(command, "dispatch_session_source_intake_record") as dispatch, \
             patch.object(legacy, "plan_source_intake_record", return_value=plan) as planner:
            code, out, _err = self.call(["--dry-run", "--source-intake-plan", PRIVATE])
        self.assertEqual(code, 0, out)
        dispatch.assert_not_called()
        planner.assert_called_once()

    def test_startup_and_reporter_defaults_do_not_change_unscoped_progress(self):
        for ref in ("--client-app-ref=" + APP, "--task-route-ref=" + ROUTE, "--work-session-ref=" + SESSION):
            flags = ["source-intake-record", PRIVATE, ref, "--resume"]
            self.assertTrue(cli_entry.startup_progress_requested(flags))
            for silent in ("--no-progress", "--help", "--version"):
                self.assertFalse(cli_entry.startup_progress_requested(flags + [silent]))
        self.assertFalse(cli_entry.startup_progress_requested(["source-intake-record", PRIVATE, "--dry-run"]))
        self.assertFalse(cli_entry.startup_progress_requested(["source-intake-record", PRIVATE, "--", "--client-app-ref=" + APP]))
        with patch.object(command, "dispatch_session_source_intake_record", return_value=result("resume")), \
             patch.object(cli, "CommandProgressReporter") as reporter:
            code, out, _err = self.call(["--client-app-ref", APP, "--task-route-ref", ROUTE, "--resume"])
        self.assertEqual(code, 0, out)
        self.assertIs(reporter.call_args.args[0], True)
        self.assertEqual(reporter.call_args.kwargs["heartbeat_interval_seconds"], 5.0)
        reporter.return_value.close.assert_called_once()

    def test_lifecycle_interrupt_preserves_already_verified_original_result(self):
        for boundary in ("construct", "close"):
            with patch.object(command, "dispatch_session_source_intake_record", return_value=result("resume")) as dispatch, \
                 patch.object(cli, "CommandProgressReporter") as reporter:
                if boundary == "construct":
                    reporter.side_effect = KeyboardInterrupt(PRIVATE)
                else:
                    reporter.return_value.close.side_effect = KeyboardInterrupt(PRIVATE)
                code, out, err = self.call(["--client-app-ref", APP, "--task-route-ref", ROUTE, "--resume"])
            public = json.loads(out)
            self.assertEqual(code, 1)
            self.assertEqual(public["reason_code"], "work_session_wait_cancelled")
            self.assertEqual(public["original_completion_verified"], boundary == "close")
            self.assertEqual(dispatch.call_count, int(boundary == "close"))
            self.assertNotIn(PRIVATE, out + err)


class RecordCommandHeldTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / "archive.yml").write_text("archive_id: archive:personal:single-command-fixture\n", encoding="utf-8")

    def call(self, mode, **changes):
        values = dict(mode=mode, client_app_ref=APP, task_route_ref=ROUTE, work_session_ref=SESSION)
        if mode != "resume":
            values["plan_path"] = PRIVATE
        if mode == "apply":
            values["reviewer_claim"] = "person:synthetic-reviewer"
        values.update(changes)
        return command.dispatch_session_source_intake_record(self.root, **values)

    def test_all_modes_use_same_real_held_lock_and_runtime_guard(self):
        helds, guards = [], []
        original_guard = command.sessions._runtime_guard
        def guard(root):
            guards.append(root)
            return original_guard(root)
        for mode, name in (("preview", "_preview_session_source_intake_record_held"),
                           ("apply", "_execute_session_source_intake_record_held"),
                           ("resume", "_resume_session_source_intake_record_held")):
            def run(root, *inputs, held, **values):
                self.assertIs(type(held), exact.ExactOperationWriterLock)
                held.verify_held()
                helds.append(held)
                self.assertEqual(len(inputs), 0 if mode == "resume" else 1)
                return result(mode)
            with patch.object(workflow, name, side_effect=run), patch.object(command.sessions, "_runtime_guard", side_effect=guard):
                self.assertTrue(self.call(mode)["ok"])
        self.assertEqual(len(guards), 3)
        for held in helds:
            with self.assertRaises(exact.ExactOperationManifestError):
                held.verify_held()

    def test_runtime_cancel_and_bad_original_inputs_refuse_before_domain(self):
        with patch.object(workflow, "_resume_session_source_intake_record_held") as run:
            for changes in ({"plan_path": PRIVATE}, {"reviewer_claim": PRIVATE}, {"client_app_ref": PRIVATE}):
                self.assertFalse(self.call("resume", **changes)["ok"])
            cancelled = self.call("resume", cancel_requested=lambda: True)
            self.assertEqual(cancelled["effects_state"], "none")
            self.assertEqual(cancelled["reason_code"], "work_session_wait_cancelled")
            with patch.object(command.sessions, "_runtime_guard", side_effect=command.sessions.WorkSessionServiceError("project_runtime_mismatch")):
                refusal = self.call("resume")
            self.assertEqual(refusal["reason_code"], "project_runtime_mismatch")
            run.assert_not_called()


class RecordMcpGrammarTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.server = mcp.JsonRpcMcpServer()

    def call(self, **changes):
        message = request(**changes)
        message["params"]["arguments"]["archive_root"] = str(self.root)
        return self.server.handle_message(message)

    def test_closed_schema_and_callbacks_are_transport_owned_only(self):
        tool = next(value for value in mcp.TOOL_DEFINITIONS if value["name"] == "source_intake_record")
        self.assertFalse(tool["inputSchema"]["additionalProperties"])
        self.assertEqual(tool["inputSchema"]["properties"]["mode"]["enum"], ["preview", "apply", "resume"])
        self.assertIn("metadata only", tool["description"])
        for key in ("native", "key_provider", "claim", "context", "progress", "cancel_requested", "approval_id", "expected_plan_sha256"):
            with patch.object(command, "dispatch_session_source_intake_record") as dispatch:
                response = self.call(**{key: PRIVATE})
            self.assertEqual(response["error"]["code"], -32602)
            dispatch.assert_not_called()
            self.assertNotIn(PRIVATE, json.dumps(response))

    def test_all_modes_use_same_single_adapter_and_relative_plan_policy(self):
        sent = []
        context = transport.SessionRequest("token", sent.append)
        token = transport._SESSION_REQUEST.set(context)
        self.addCleanup(lambda: transport._SESSION_REQUEST.reset(token))
        with patch.dict(os.environ, {mcp.MCP_ALLOWED_ROOTS_ENV: str(self.root)}):
            for mode in ("preview", "apply", "resume"):
                changes = {"mode": mode, "work_session_ref": SESSION}
                if mode != "resume":
                    changes["source_intake_plan"] = "input.json"
                if mode == "apply":
                    changes["reviewed_by"] = "person:synthetic-reviewer"
                with patch.object(command, "dispatch_session_source_intake_record", return_value=result(mode)) as dispatch:
                    response = self.call(**changes)
                self.assertFalse(response["result"]["isError"])
                values = dispatch.call_args.kwargs
                self.assertEqual(values["plan_path"], None if mode == "resume" else self.root / "input.json")
                self.assertEqual(values["progress"], context.progress)
                self.assertEqual(values["cancel_requested"], context.cancel_requested)
                self.assertNotIn(str(self.root), json.dumps(response))

    def test_bad_types_replacement_metadata_and_outside_paths_fail_privately(self):
        for changes in ({"source_intake_plan": PRIVATE}, {"reviewed_by": PRIVATE}, {"mode": True},
                        {"mode": "preview", "reviewed_by": PRIVATE}, {"work_session_ref": None},
                        {"mode": "apply", "source_intake_plan": "x" * 65536}):
            with patch.object(command, "dispatch_session_source_intake_record") as dispatch:
                response = self.call(**changes)
            self.assertEqual(response["error"]["code"], -32602)
            dispatch.assert_not_called()
            self.assertNotIn(PRIVATE, json.dumps(response))
        with patch.dict(os.environ, {mcp.MCP_ALLOWED_ROOTS_ENV: str(self.root)}), \
             patch.object(command, "dispatch_session_source_intake_record") as dispatch:
            response = self.call(mode="preview", source_intake_plan=str(self.root.parent / PRIVATE), work_session_ref=SESSION)
        self.assertTrue(response["result"]["isError"])
        dispatch.assert_not_called()
        self.assertNotIn(str(self.root), json.dumps(response))
        self.assertNotIn(PRIVATE, json.dumps(response))
        for bad in (False, None, 1.25, {}, []):
            response = self.server.handle_message(request(token=bad))
            self.assertEqual(response["error"]["code"], -32602)


class RecordTransportTests(unittest.TestCase):
    def test_domain_projector_retains_only_closed_stages_and_validated_item_counts(self):
        sent = []
        context = transport.SessionRequest("token", sent.append, domain_progress=True)
        context.enter_execution()
        with patch.object(exact.ExactOperationProgress, "public_document", side_effect=AssertionError("arbitrary callback")):
            for stage in ("preflight", "heartbeat", "item_started", "field_verified", "item_verified", "completed"):
                context.progress(progress_event(stage=stage, completed_items=1))
            for phase in ("intake_preflight", "intake_revalidation", "waiting_for_writer", "writer_acquired_revalidation_required"):
                context.progress({"phase": phase, "message": PRIVATE, "total": PRIVATE, "path": PRIVATE})
        self.assertEqual(len(sent), 11)
        self.assertEqual([row["params"]["progress"] for row in sent], list(range(1, 12)))
        self.assertEqual(sent[0]["params"]["message"], "source-intake: starting")
        for row in sent[1:7]:
            self.assertEqual(set(row["params"]), {"progressToken", "progress", "message"})
            self.assertIn("completed items 1/1", row["params"]["message"])
        self.assertNotIn(PRIVATE, json.dumps(sent))
        self.assertNotIn(PRIVATE, repr(context))

        class Duck:
            def public_document(self):
                raise AssertionError("arbitrary projection")

        class EventSubclass(exact.ExactOperationProgress):
            pass

        class DictSubclass(dict):
            def get(self, *_args):
                raise AssertionError("arbitrary mapping")

        class StringSubclass(str):
            pass

        invalid = [Duck(), DictSubclass(phase="intake_preflight"), {"phase": []}, {"stage": PRIVATE},
                   {"phase": StringSubclass("intake_preflight")},
                   EventSubclass(PRIVATE, PRIVATE, "apply", "completed", 1, 1, 1, 1)]
        invalid += [progress_event(stage=value) for value in ([], PRIVATE, StringSubclass("completed"))]
        invalid += [progress_event(completed_items=value) for value in (True, -1, 2, 1.0, 10 ** 10000)]
        invalid += [progress_event(total_items=value) for value in (False, -1, 1.0, 1 << 63)]
        for event in invalid:
            context.progress(event)
        self.assertEqual(len(sent), 11)

    def test_domain_heartbeat_uses_monotonic_boundary_and_repeats_only_observed_facts(self):
        sent = []
        context = transport.SessionRequest("token", sent.append, domain_progress=True)
        with patch.object(transport.time, "monotonic", return_value=100.0) as monotonic:
            context.execution_heartbeat()  # Neither queue nor missing observation invents status.
            self.assertEqual(sent, [])
            context.enter_execution()
            context.execution_heartbeat()
            self.assertEqual(len(sent), 1)
            self.assertEqual(sent[0]["params"]["message"], "source-intake: starting")
            context.progress(progress_event())
            original = sent[-1]["params"]["message"]
            for now in (104.999, 99.0):
                monotonic.return_value = now
                context.execution_heartbeat()
            self.assertEqual(len(sent), 2)
            monotonic.return_value = 105.0
            context.execution_heartbeat()
            self.assertEqual(len(sent), 3)
            self.assertEqual(sent[-1]["params"]["message"], "Awaiting next observed status; " + original)
            self.assertIn("completed items 0/1", sent[-1]["params"]["message"])
            context.queued_progress()
            monotonic.return_value = 109.999
            context.execution_heartbeat()
            self.assertEqual(len(sent), 3)
            monotonic.return_value = 110.0
            context.execution_heartbeat()
            self.assertEqual(len(sent), 4)
            context.progress(progress_event(stage="item_verified", completed_items=1))
            monotonic.return_value = 115.0
            context.execution_heartbeat()
            self.assertEqual(len(sent), 6)
            self.assertIn("exact-operation-item_verified; completed items 1/1", sent[-1]["params"]["message"])
        self.assertEqual([row["params"]["progress"] for row in sent], [1, 2, 3, 4, 5, 6])
        self.assertNotIn(PRIVATE, json.dumps(sent))

    def test_no_domain_progress_after_terminal_cancel_without_token_or_for_legacy_management(self):
        for ending in ("terminal", "cancel"):
            sent = []
            context = transport.SessionRequest("token", sent.append, domain_progress=True)
            context.enter_execution()
            context.progress(progress_event())
            context.finish(None) if ending == "terminal" else context.cancel()
            with patch.object(transport.time, "monotonic", return_value=10 ** 12):
                context.progress(progress_event(stage="completed", completed_items=1))
                context.execution_heartbeat()
                context.queued_progress()
            self.assertEqual(len(sent), 2)
        for token, enabled in ((None, True), ("token", False), ("token", 1)):
            sent = []
            context = transport.SessionRequest(token, sent.append, domain_progress=enabled)
            context.enter_execution()
            context.progress(progress_event())
            context.progress({"phase": "intake_preflight"})
            with patch.object(transport.time, "monotonic", return_value=10 ** 12):
                context.execution_heartbeat()
            self.assertEqual(sent, [])
            context.progress({"stage": "waiting_for_writer", "message": PRIVATE})
            self.assertEqual(len(sent), 0 if token is None else 1)
            self.assertNotIn(PRIVATE, json.dumps(sent))

    def test_only_closed_record_tool_enables_domain_projection_in_actual_serial_lane(self):
        entered, release, completed = threading.Event(), threading.Event(), threading.Event()
        sent, enabled = [], []

        def handle(message):
            context = transport.current_session_request()
            enabled.append((message["params"]["name"], context._domain_enabled))
            if message["id"] == 1:
                entered.set()
                self.assertTrue(release.wait(4))
            context.progress(progress_event(stage="completed", completed_items=1))
            return {"jsonrpc": "2.0", "id": message["id"], "result": {}}

        def write(row):
            sent.append(row)
            if row.get("id") == 2:
                completed.set()
            return True

        lane = transport.SessionStdioTransport(handle, write, mcp.jsonrpc_request_id_is_valid)
        self.addCleanup(lane.close)
        self.addCleanup(release.set)
        lane.dispatch(request(1, "record"))
        self.assertTrue(entered.wait(2))
        management = request(2, "management")
        management["params"]["name"] = "archive_work_session_manage"
        management["params"]["arguments"] = {"action": "status"}
        lane.dispatch(management)
        release.set()
        # Waiting for the terminal result lets the real serial lane drain before
        # close: close intentionally cancels queued work instead of flushing it.
        self.assertTrue(completed.wait(4))
        lane.close()
        self.assertEqual(enabled, [("source_intake_record", True), ("archive_work_session_manage", False)])
        domain = [row for row in sent if "message" in row.get("params", {})]
        self.assertEqual(len(domain), 2)
        self.assertEqual(domain[0]["params"]["message"], "source-intake: starting")
        self.assertEqual(domain[1]["params"]["message"], "source-intake: exact-operation-completed; completed items 1/1")
        self.assertTrue(all(row["params"]["progressToken"] == "record" for row in domain))
        self.assertNotIn(PRIVATE, json.dumps(sent))

    def test_unhashable_and_nonstring_tool_names_never_activate_managed_lane(self):
        server = mcp.JsonRpcMcpServer()
        for name in ([], {}, True, None, 1, 1.0):
            message = request()
            message["params"]["name"] = name
            self.assertFalse(transport.is_management_request(message))
            response = server.handle_message(message)
            self.assertEqual(response["error"]["code"], -32602)
            self.assertNotIn(PRIVATE, json.dumps(response))

    def test_all_modes_are_serial_and_only_observed_wait_cancel_suppresses_response(self):
        for mode in ("preview", "apply", "resume"):
            self.assertTrue(transport._managed_mutation(request(mode=mode)))
        self.assertFalse(transport._managed_mutation(request(mode=True)))
        for observed, failed in ((False, True), (True, False), (True, True)):
            sent = []
            context = transport.SessionRequest(None, sent.append)
            context.cancel()
            if observed:
                self.assertTrue(context.cancel_requested())
            content = command._failure("work_session_wait_cancelled", mode="resume") if failed else result("resume")
            content["schema"] = command._SCHEMA
            response = {"id": 1, "result": {"structuredContent": content}}
            context.finish(response)
            self.assertEqual(sent, [] if observed and failed else [response])

    def test_actual_serial_queue_cancellation_never_enters_cancelled_record_and_late_success_survives(self):
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        calls, sent = [], []
        def handle(message):
            calls.append(message["id"])
            if message["id"] == 1:
                self.assertIs(type(transport.current_session_request()), transport.SessionRequest)
                entered.set()
                self.assertTrue(release.wait(4))
                finished.set()
            return {"id": message["id"], "result": {"structuredContent": {"schema": command._SCHEMA, **result("resume")}}}
        lane = transport.SessionStdioTransport(handle, lambda value: sent.append(value) or True, mcp.jsonrpc_request_id_is_valid)
        self.addCleanup(lane.close)
        self.addCleanup(release.set)
        lane.dispatch(request(1, "one"))
        self.assertTrue(entered.wait(2))
        lane.dispatch(request(2, "two"))
        lane.dispatch({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 2, "reason": PRIVATE}})
        lane.dispatch({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 1, "reason": PRIVATE}})
        release.set()
        self.assertTrue(finished.wait(2))
        lane.close()
        self.assertEqual(calls, [1])
        self.assertEqual([row["id"] for row in sent if "id" in row], [1])
        self.assertNotIn(PRIVATE, json.dumps(sent))
        self.assertIsNone(transport.current_session_request())


if __name__ == "__main__":
    unittest.main()
