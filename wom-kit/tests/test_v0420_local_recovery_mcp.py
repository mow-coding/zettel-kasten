"""Title MCP grammar and serial transport, separate from actual field journeys."""

import json
from pathlib import Path
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wom_kit import _mcp_session_transport as transport
from wom_kit import exact_operation_manifest as exact
from wom_kit import local_recovery_session as command
from wom_kit import mcp_server as mcp
from wom_kit import archive_cli as cli
from wom_kit import work_session_service as sessions


PRIVATE = "SYNTHETIC_PRIVATE_TITLE_INPUT"
APP, ROUTE, SESSION = "client_app_" + "a" * 32, "task_route_" + "b" * 32, "work_session_" + "c" * 32


def request(values, request_id=1, token="title-progress"):
    return {"jsonrpc": "2.0", "id": request_id, "method": "tools/call", "params": {
        "name": "zet_title_remap_write", "arguments": values, "_meta": {"progressToken": token}}}


class TitleMcpTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.server = mcp.JsonRpcMcpServer()

    def arguments(self, mode="resume"):
        result = dict(archive_root=str(self.root), mode=mode, client_app_ref=APP, task_route_ref=ROUTE)
        if mode in {"preview", "apply"}:
            result.update(work_session_ref=SESSION, source_mirror=PRIVATE)
        if mode == "apply":
            result["reviewed_by"] = "person:synthetic-reviewer"
        return result

    def test_original_inputs_and_private_invalid_arguments_stop_before_dispatch(self):
        variants = []
        for mode in ("resume", "review_original"):
            for key in ("source_mirror", "reviewed_by", "approval_id", "manifest_sha256",
                        "max_items", "expected_identifier_title_count"):
                for value in (None, PRIVATE, 1):
                    variants.append({**self.arguments(mode), key: value})
        for mode in ("preview", "apply"):
            for key in ("source_mirror", "work_session_ref"):
                missing = self.arguments(mode)
                del missing[key]
                variants.append(missing)
        variants.extend([{**self.arguments("apply"), "max_items": True},
                         {**self.arguments("preview"), "reviewed_by": PRIVATE},
                         {**self.arguments(), "mode": "revert"}])
        with patch.object(command, "_dispatch_session_local_recovery") as dispatch:
            for values in variants:
                response = self.server.handle_message(request(values))
                self.assertEqual(response["error"]["code"], -32602, response)
                self.assertNotIn(PRIVATE, json.dumps(response))
        dispatch.assert_not_called()

    def test_four_modes_preserve_fixed_domain_and_transport_callbacks(self):
        context = transport.SessionRequest("token", lambda _row: True,
            _progress_family=transport._ProgressFamily.RECOVERY)
        token = transport._SESSION_REQUEST.set(context)
        self.addCleanup(lambda: transport._SESSION_REQUEST.reset(token))
        for mode in ("preview", "apply", "resume", "review_original"):
            with patch.object(command, "_dispatch_session_local_recovery", return_value={"ok": True}) as dispatch:
                response = self.server.handle_message(request(self.arguments(mode)))
            self.assertNotIn("error", response)
            dispatch.assert_called_once()
            self.assertEqual(dispatch.call_args.args, (self.root,))
            values = dispatch.call_args.kwargs
            self.assertEqual(values["allowed_domains"], {"zet_title_recovery"})
            self.assertEqual(values["cancel_requested"], context.cancel_requested)
            self.assertEqual(values["progress"], context.progress)
            self.assertEqual(values["mode"], mode)
            if mode in {"resume", "review_original"}:
                self.assertIsNone(values["plan_factory"])
                self.assertIsNone(values["reviewer_claim"])
            else:
                self.assertTrue(callable(values["plan_factory"]))
            self.assertNotIn(PRIVATE, json.dumps(response))

    def test_actual_wait_cancellation_stops_before_runtime_original_or_native(self):
        # Only archive fixture selection is replaced; the actual wait and
        # dispatcher error projection must observe and report cancellation.
        with patch.object(sessions, "_root", return_value=self.root), \
             patch.object(sessions, "_runtime_guard", side_effect=AssertionError("runtime after cancel")), \
             patch.object(command, "_resume_session_local_recovery_held", side_effect=AssertionError("domain after cancel")):
            result = command._dispatch_session_local_recovery(self.root, mode="resume",
                client_app_ref=APP, task_route_ref=ROUTE, allowed_domains={"zet_title_recovery"},
                cancel_requested=lambda: True)
        self.assertEqual(result["reason_codes"], ["work_session_wait_cancelled"])
        self.assertEqual(result["effects_state"], "none")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_document_observation_projects_only_counts_and_flags(self):
        result = {"ok": True, "state": "applied", "domain": "zet_title_recovery",
            "original_completion_verified": True, "completion_authentication_verified": True,
            "independent_verification": True, "whole_document_transition_verified": True,
            "whole_document_ownership_verified": False, "whole_document_count": 2,
            "document_images": [{"relative_path": PRIVATE, "private": PRIVATE}]}
        with patch.object(sessions, "_root", return_value=self.root), \
             patch.object(sessions, "_write", return_value=result):
            public = command._dispatch_session_local_recovery(self.root, mode="resume",
                client_app_ref=APP, task_route_ref=ROUTE, allowed_domains={"zet_title_recovery"})
        self.assertTrue(public["ok"])
        self.assertTrue(public["whole_document_transition_verified"])
        self.assertFalse(public["whole_document_ownership_verified"])
        self.assertEqual(public["whole_document_count"], 2)
        self.assertNotIn("document_images", public)
        self.assertNotIn(PRIVATE, json.dumps(public))

    def test_cli_projects_actual_wait_stage_without_private_values(self):
        observed = []
        reporter = SimpleNamespace(progress=lambda *values: observed.append(values))
        args = SimpleNamespace(archive_root=str(self.root), client_app_ref=APP, task_route_ref=ROUTE,
                               work_session_ref=None, reviewed_by=None, dry_run=False)

        def dispatch(*_args, **kwargs):
            for stage in ("waiting_for_writer", "writer_acquired_revalidation_required"):
                kwargs["progress"]({"stage": stage, "message": PRIVATE, "elapsed_seconds": 1.0})
            return {"ok": False, "effects_state": "none"}

        with patch.object(command, "_dispatch_session_local_recovery", side_effect=dispatch):
            cli._execute_local_recovery_cli_mode(args, allowed_domains={"zet_title_recovery"},
                plan_factory=None, expected_manifest_sha256="", resume=True, revert=False, reporter=reporter)
        self.assertEqual(observed, [("local-recovery-waiting_for_writer", "apply", None, None),
            ("local-recovery-writer_acquired_revalidation_required", "apply", None, None)])
        self.assertNotIn(PRIVATE, repr(observed))

    def test_closed_progress_and_only_observed_uneffected_cancellation(self):
        sent = []
        context = transport.SessionRequest("token", sent.append, _progress_family=transport._ProgressFamily.RECOVERY)
        context.enter_execution()
        context.progress({"phase": "waiting_for_writer", "message": PRIVATE})
        context.progress(exact.ExactOperationProgress(manifest_sha256=PRIVATE, execution_sha256=PRIVATE,
            mode="apply", stage="field_verified", completed_items=1, total_items=2,
            completed_fields=1, total_fields=2))
        self.assertEqual(sent[0]["params"]["message"], "local-recovery: starting")
        self.assertIn("completed items 1/2", sent[-1]["params"]["message"])
        before = list(sent)
        context.progress({"phase": "intake_preflight", "private": PRIVATE})
        context.progress({"phase": PRIVATE})
        self.assertEqual(sent, before)
        self.assertNotIn(PRIVATE, json.dumps(sent))
        for observed in (False, True):
            for effects in ("none", "unknown"):
                sent = []
                context = transport.SessionRequest(None, sent.append,
                    _progress_family=transport._ProgressFamily.RECOVERY)
                context.cancel()
                if observed:
                    self.assertTrue(context.cancel_requested())
                response = {"jsonrpc": "2.0", "id": 1, "result": {"structuredContent": {
                    "schema_version": "wom-kit/local-recovery-execution-result/v0.1", "ok": False,
                    "reason_codes": ["work_session_wait_cancelled"], "effects_state": effects}}}
                context.finish(response)
                self.assertEqual(sent, [] if observed and effects == "none" else [response])

    def test_preview_uses_serial_lane_with_live_ping_and_no_private_progress(self):
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        observed, sent = [], []

        def handle(message):
            if message.get("method") == "ping":
                return {"jsonrpc": "2.0", "id": message["id"], "result": {}}
            context = transport.current_session_request()
            observed.append(context._progress_family)
            entered.set()
            if not release.wait(10):
                raise AssertionError("synthetic serial lane timeout")
            return {"jsonrpc": "2.0", "id": message["id"], "result": {"structuredContent": {"ok": True}}}

        def send(row):
            sent.append(row)
            if row.get("id") == 1:
                finished.set()
            return True

        lane = transport.SessionStdioTransport(handle, send, mcp.jsonrpc_request_id_is_valid)
        self.addCleanup(lane.close)
        self.addCleanup(release.set)
        message = request(self.arguments("preview"))
        self.assertTrue(transport.is_management_request(message))
        self.assertTrue(transport._managed_mutation(message))
        lane.dispatch(message)
        self.assertTrue(entered.wait(10))
        lane.dispatch({"jsonrpc": "2.0", "id": 2, "method": "ping"})
        self.assertTrue(any(row.get("id") == 2 for row in sent))
        release.set()
        self.assertTrue(finished.wait(10))
        self.assertEqual(observed, [transport._ProgressFamily.RECOVERY])
        self.assertNotIn(PRIVATE, json.dumps(sent))


if __name__ == "__main__":
    unittest.main()
