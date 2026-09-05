"""Small transport contracts; domain execution is covered by fresh stdio tests."""

import io
import json
import threading
import unittest
from unittest.mock import patch

from wom_kit import mcp_server as server
from wom_kit import _mcp_session_transport as transport


def managed(request_id=1, token="progress", **changes):
    result = {"jsonrpc": "2.0", "id": request_id, "method": "tools/call", "params": {
        "name": "archive_work_session_manage", "arguments": {
            "action": "register-app", "apply": True}, "_meta": {"progressToken": token}}}
    result.update(changes)
    return result


def response(request_id, *, cancelled=False):
    content = {"schema": "wom-kit/work-session-management/v1", "ok": not cancelled}
    if cancelled:
        content["reason_code"] = "work_session_wait_cancelled"
    return {"jsonrpc": "2.0", "id": request_id, "result": {"structuredContent": content}}


class SessionContextTests(unittest.TestCase):
    def test_metadata_and_management_ids_are_strict_without_changing_legacy_ids(self):
        subject = server.JsonRpcMcpServer()
        with patch.object(subject, "_dispatch_request", return_value={}) as dispatch:
            for value in (None, False, True, 1.25, [], {}):
                with self.subTest(value=value):
                    result = subject.handle_message(managed(value))
                    self.assertEqual(result["error"]["code"], -32600)
            dispatch.assert_not_called()
            for value in (1, "1"):
                self.assertEqual(subject.handle_message(managed(value))["result"], {})
            for value in (None, 1.25):
                self.assertEqual(subject.handle_message({"jsonrpc": "2.0", "id": value,
                    "method": "ping"})["result"], {})
        for value in (None, False, True, 1.25, [], {}):
            with self.subTest(token=value):
                self.assertFalse(transport.management_metadata({"_meta": {"progressToken": value}})[0])
        for value in (0, "", "token"):
            self.assertEqual(transport.management_metadata({"_meta": {"progressToken": value}}), (True, value))
        self.assertEqual(transport.management_metadata({}), (True, None))
        self.assertFalse(transport.management_metadata({"_meta": "PRIVATE_META"})[0])

    def test_public_tool_metadata_cannot_inject_internal_callbacks(self):
        for meta in ({"progressToken": False}, "PRIVATE_META"):
            with self.subTest(meta=meta), self.assertRaises(server.InvalidParamsError):
                server.handle_tools_call({"name": "archive_work_session_manage", "arguments": {}, "_meta": meta})
        for key in ("context", "cancel_requested", "progress", "native", "key_provider"):
            with self.subTest(key=key), self.assertRaises(server.InvalidParamsError):
                server.tool_archive_work_session_manage({"archive_root": "PRIVATE_PATH", "action": "claim", key: "PRIVATE_INPUT"})

    def test_progress_is_strict_increasing_common_protocol_and_has_no_private_event_fields(self):
        sent = []
        context = transport.SessionRequest("echo-only-token", sent.append)
        for stage in ("waiting_for_writer", "waiting_for_writer", "writer_acquired_revalidation_required"):
            context.progress({"stage": stage, "elapsed_seconds": 0.0, "label": "PRIVATE_LABEL", "message": "PRIVATE_MESSAGE"})
        context.progress({"stage": "PRIVATE_UNKNOWN"})
        self.assertEqual([row["params"]["progress"] for row in sent], [1, 2, 3])
        self.assertTrue(all(set(row["params"]) == {"progressToken", "progress"} for row in sent))
        self.assertNotIn("PRIVATE_", json.dumps(sent))
        self.assertNotIn("echo-only-token", repr(context))
        context.finish(response(1))
        context.progress({"stage": "waiting_for_writer"})
        self.assertEqual(len(sent), 4)
        no_token = transport.SessionRequest(None, sent.append)
        no_token.progress({"stage": "waiting_for_writer"})
        self.assertEqual(len(sent), 4)

    def test_only_actual_observed_wait_cancellation_suppresses_result(self):
        for observed, cancelled in ((False, True), (False, False), (True, False), (True, True)):
            with self.subTest(observed=observed, cancelled=cancelled):
                sent = []
                context = transport.SessionRequest(None, sent.append)
                context.cancel()
                if observed:
                    self.assertTrue(context.cancel_requested())
                context.finish(response(1, cancelled=cancelled))
                self.assertEqual(len(sent), 0 if observed and cancelled else 1)
                self.assertFalse(context.cancel_requested())

    def test_cancel_stops_queue_and_domain_progress_but_late_success_is_still_returned(self):
        sent = []
        context = transport.SessionRequest("token", sent.append)
        context.queued_progress()
        context.cancel()
        context.queued_progress()
        context.progress({"stage": "waiting_for_writer"})
        context.finish(response(1))
        context.finish(response(1))
        context.queued_progress()
        self.assertEqual(len(sent), 2)
        self.assertEqual(sent[-1], response(1))


class SchedulerTests(unittest.TestCase):
    def lane(self, handler, write=None):
        output = []
        subject = transport.SessionStdioTransport(handler,
            write or (lambda value: output.append(value) or True), server.jsonrpc_request_id_is_valid)
        self.addCleanup(subject.close)
        return subject, output

    def test_legacy_only_stays_inline_and_serialization_guards_are_preserved(self):
        subject = server.JsonRpcMcpServer()
        output = io.StringIO()
        with patch.object(subject, "_dispatch_request", side_effect=[{"invalid": object()}, {}, {}]):
            self.assertEqual(subject.serve(io.StringIO(
                '{"jsonrpc":"2.0","id":1,"method":"ping"}\n'
                '{"jsonrpc":"2.0","id":2,"method":"ping"}\n'
                '{"jsonrpc":"2.0","id":3,"method":"ping"}\n'), output), 0)
        rows = [json.loads(row) for row in output.getvalue().splitlines()]
        self.assertEqual([row["id"] for row in rows], [1, 2, 3])
        self.assertEqual(rows[0]["error"]["code"], -32603)

    def test_active_collision_queue_cancel_safe_queries_and_legacy_serialization(self):
        entered, release, drained = threading.Event(), threading.Event(), threading.Event()
        calls = []

        def handle(message):
            calls.append(message["id"])
            if message["id"] == 1:
                entered.set()
                self.assertTrue(release.wait(3))
            if message["id"] == 5:
                drained.set()
            return response(message["id"])

        lane, sent = self.lane(handle)
        self.addCleanup(release.set)
        lane.dispatch(managed())
        self.assertTrue(entered.wait(2))
        lane.dispatch(managed(2))  # same active token
        lane.dispatch({"jsonrpc": "2.0", "id": 1, "method": "ping"})
        lane.dispatch({"jsonrpc": "2.0", "id": 1.0, "method": "ping"})
        malformed = managed(1)
        malformed["params"]["_meta"] = "PRIVATE_MALFORMED_META"
        lane.dispatch(malformed)
        lane.dispatch({"jsonrpc": "2.0", "id": "1", "method": "ping"})
        lane.dispatch(managed(3, "different"))
        lane.dispatch({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {
            "requestId": 3, "reason": "PRIVATE_CANCEL_REASON"}})
        lane.dispatch({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "legacy"}})
        self.assertEqual(calls, [1, "1"])
        release.set()
        self.assertTrue(drained.wait(2))
        lane.close()
        self.assertEqual(calls, [1, "1", 5])
        self.assertEqual([row["id"] for row in sent if "error" in row], [2, None, None, None])
        self.assertNotIn("PRIVATE_", json.dumps(sent))
        self.assertNotIn(3, [row.get("id") for row in sent])
        self.assertIsNone(transport.current_session_request())

    def test_queue_count_and_payload_bounds_reject_without_dispatch(self):
        entered, release = threading.Event(), threading.Event()
        calls = []
        def handle(message):
            calls.append(message["id"])
            entered.set()
            self.assertTrue(release.wait(3))
            return response(message["id"])
        lane, sent = self.lane(handle)
        self.addCleanup(release.set)
        lane.dispatch(managed())
        self.assertTrue(entered.wait(2))
        for index in range(transport.MAX_PENDING_REQUESTS):
            lane.dispatch(managed(index + 2, index))
        lane.dispatch(managed(100, "overflow"))
        oversized = managed(101, "large")
        oversized["params"]["arguments"]["request"] = {"label": "x" * transport.MAX_QUEUED_MESSAGE_BYTES}
        lane.dispatch(oversized)
        self.assertEqual([(row["id"], row["error"]["code"]) for row in sent if "error" in row], [(100, -32000), (101, -32602)])
        lane.close(wait=False)
        release.set()
        lane.close()
        self.assertEqual(calls, [1])
        self.assertEqual(sent[-1], response(1))  # entered success not relabeled by EOF

    def test_shutdown_cancels_waiting_and_never_starts_queued_legacy_mutation(self):
        entered = threading.Event()
        calls = []
        def handle(message):
            calls.append(message["id"])
            context = transport.current_session_request()
            entered.set()
            # Wait without a polling loop; shutdown sets cancellation, and the
            # final callback is the same observation that the real waiter uses.
            self.assertTrue(shutdown.wait(3))
            self.assertTrue(context.cancel_requested())
            return response(message["id"], cancelled=True)
        shutdown = threading.Event()
        lane, sent = self.lane(handle)
        self.addCleanup(shutdown.set)
        lane.dispatch(managed())
        self.assertTrue(entered.wait(2))
        lane.dispatch({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "legacy"}})
        lane.close(wait=False)
        shutdown.set()
        lane.close()
        self.assertEqual(calls, [1])
        self.assertFalse(any("id" in row for row in sent))

    def test_broken_output_cancels_wait_callback_without_private_errors(self):
        failed = threading.Event()
        def handle(message):
            context = transport.current_session_request()
            context.progress({"stage": "waiting_for_writer"})
            self.assertTrue(context.cancel_requested())
            return response(message["id"], cancelled=True)
        def write(_value):
            failed.set()
            return False
        lane, _ = self.lane(handle, write)
        lane.dispatch(managed())
        self.assertTrue(failed.wait(2))
        lane.close()
        self.assertTrue(lane.stopped)

    def test_output_callback_exception_is_a_closed_sink_not_a_thread_traceback(self):
        def write(_value):
            raise OSError("PRIVATE_OUTPUT_FAILURE")
        lane, _ = self.lane(lambda _message: None, write)
        self.assertFalse(lane.send(response(1)))
        self.assertTrue(lane.stopped)

    def test_queue_heartbeat_cancel_releases_slot_and_token_before_active_job_finishes(self):
        entered, release, second_tick = threading.Event(), threading.Event(), threading.Event()
        calls, sent = [], []
        def handle(message):
            calls.append(message["id"])
            entered.set()
            self.assertTrue(release.wait(5))
            return response(message["id"])
        def write(value):
            sent.append(value)
            if value.get("params", {}).get("progressToken") == "queued" and value["params"]["progress"] >= 2:
                second_tick.set()
            return True
        lane, _ = self.lane(handle, write)
        self.addCleanup(release.set)
        with patch.object(transport, "QUEUE_HEARTBEAT_SECONDS", 0.01):
            lane.dispatch(managed())
            self.assertTrue(entered.wait(2))
            lane.dispatch(managed(2, "queued"))
            self.assertTrue(second_tick.wait(3))
            lane.dispatch({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 2}})
            self.assertNotIn((int, 2), lane._active)
            self.assertNotIn((str, "queued"), lane._tokens)
            self.assertFalse(lane._pending)
            count = len(sent)
            lane.dispatch(managed(3, "queued"))
            self.assertTrue(all("error" not in value for value in sent[count:]))
            lane.close(wait=False)
        release.set()
        lane.close()
        self.assertEqual(calls, [1])
        self.assertIsNotNone(lane._heartbeat)
        self.assertFalse(lane._heartbeat.is_alive())

    def test_active_legacy_numeric_and_null_requests_are_tracked_without_changing_legacy_dispatch(self):
        entered, release = threading.Event(), threading.Event()
        def handle(message):
            if message["id"] == "active":
                entered.set()
                self.assertTrue(release.wait(3))
            return response(message["id"])
        lane, sent = self.lane(handle)
        self.addCleanup(release.set)
        lane.dispatch(managed("active"))
        self.assertTrue(entered.wait(2))
        for request_id in (1.0, None):
            lane.dispatch({"jsonrpc": "2.0", "id": request_id, "method": "tools/call", "params": {"name": "legacy"}})
        lane.dispatch(managed(1, "another-token"))
        lane.dispatch({"jsonrpc": "2.0", "id": None, "method": "ping"})
        errors = [row for row in sent if "error" in row]
        self.assertEqual(len(errors), 2)
        self.assertTrue(all(row["id"] is None and row["error"]["code"] == -32600 for row in errors))
        lane.close(wait=False)
        release.set()
        lane.close()

    def test_stdout_line_and_flush_are_serialized_across_progress_and_response(self):
        entered, release = threading.Event(), threading.Event()
        pieces = []
        class SplitOutput:
            def write(self, value):
                pieces.append(value[:len(value) // 2])
                if len(pieces) == 1:
                    entered.set()
                    if not release.wait(3):
                        raise AssertionError("bounded synthetic output wait")
                pieces.append(value[len(value) // 2:])
            def flush(self):
                pass
        output = SplitOutput()
        implementation = server.JsonRpcMcpServer()
        lane, _ = self.lane(lambda _message: None, lambda value: implementation._write(output, value))
        self.addCleanup(release.set)
        first = threading.Thread(target=lambda: lane.send({"jsonrpc": "2.0", "method": "notifications/progress", "params": {"progressToken": 1, "progress": 1}}))
        second = threading.Thread(target=lambda: lane.send(response(1)))
        first.start()
        self.assertTrue(entered.wait(2))
        second.start()
        release.set()
        first.join(timeout=3)
        second.join(timeout=3)
        self.assertFalse(first.is_alive() or second.is_alive())
        rows = [json.loads(line) for line in "".join(pieces).splitlines()]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["method"], "notifications/progress")
        self.assertEqual(rows[1], response(1))

    def test_terminal_sink_arrival_reuses_completed_token_before_old_finally_cleanup(self):
        accepted = threading.Event()
        completed = threading.Event()
        arrivals, sent = [], []
        lane = None
        def handle(message):
            return response(message["id"])
        def write(value):
            sent.append(value)
            if value.get("id") == 1:
                # The peer has received the first terminal response, while its
                # original writer stack has not yet returned to the finally.
                arrival = threading.Thread(target=lambda: lane.dispatch(managed(2, "shared-token")))
                arrivals.append(arrival)
                arrival.start()
                with lane._condition:
                    if lane._condition.wait_for(lambda: (int, 2) in lane._active, timeout=2):
                        accepted.set()
            if value.get("id") == 2:
                completed.set()
            return True
        lane, _ = self.lane(handle, write)
        lane.dispatch(managed(1, "shared-token"))
        self.assertTrue(accepted.wait(3))
        self.assertTrue(completed.wait(3))
        for arrival in arrivals:
            arrival.join(timeout=2)
            self.assertFalse(arrival.is_alive())
        lane.close()
        self.assertFalse(any("error" in value for value in sent))
        self.assertEqual([value["id"] for value in sent if "id" in value], [1, 2])

    def test_old_entry_retirement_cannot_remove_new_identity_including_legacy_none_context(self):
        lane, _ = self.lane(lambda _message: None)
        for context in (None, transport.SessionRequest("token", lambda _value: True)):
            with self.subTest(legacy=context is None):
                token_key = (str, "token")
                old_entry = (context, token_key)
                new_entry = tuple([context, token_key])
                self.assertIsNot(old_entry, new_entry)
                lane._active[(int, 1)] = new_entry
                lane._tokens.add(token_key)
                lane._remove((int, 1), old_entry)
                self.assertIs(lane._active[(int, 1)], new_entry)
                self.assertIn(token_key, lane._tokens)
                lane._remove((int, 1), new_entry)
                self.assertNotIn((int, 1), lane._active)
                self.assertNotIn(token_key, lane._tokens)

    def test_notifications_are_scoped_and_malformed_or_late_cancellation_is_ignored(self):
        lane, sent = self.lane(lambda message: response(message["id"]))
        for params in (None, [], {"requestId": True}, {"requestId": 1.0}, {"requestId": "unknown"}):
            lane.dispatch({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": params})
        lane.dispatch({"jsonrpc": "2.0", "method": "initialize", "params": {}})
        self.assertEqual(sent, [])


if __name__ == "__main__":
    unittest.main()
