"""Batch/record scheduling and fixed intake startup, not domain acceptance.

Starting covers the interval before the first handler/wait observation. The
existing waiter already emits progress before runtime inspection. Deterministic
clock and Event oracles below do not establish an installed-client timing SLO.
"""

import json
import threading
import unittest
from unittest.mock import patch

from wom_kit import _mcp_session_transport as transport
from wom_kit import exact_operation_manifest as exact
from wom_kit import mcp_server as server
from wom_kit import source_intake_session_command as command


PRIVATE = "SYNTHETIC_PRIVATE_BATCH_INPUT"


def request(request_id=1, token="batch-progress", *, name="source_intake_batch", mode="preview"):
    return {"jsonrpc": "2.0", "id": request_id, "method": "tools/call", "params": {
        "name": name, "arguments": {"mode": mode, "archive_root": PRIVATE},
        "_meta": {"progressToken": token}}}


def response(request_id=1, *, ok=True, reason="work_session_wait_cancelled"):
    return {"jsonrpc": "2.0", "id": request_id, "result": {"structuredContent": {
        "schema": "wom-kit/source-intake-session-command/v1", "ok": ok, "reason_code": reason}}}


def event():
    return exact.ExactOperationProgress(
        manifest_sha256=PRIVATE, execution_sha256=PRIVATE, mode="apply", stage="field_verified",
        completed_items=0, total_items=1000, completed_fields=1, total_fields=1001)


class IntakeStartingTests(unittest.TestCase):
    def context(self, token="token"):
        sent = []
        return transport.SessionRequest(token, sent.append,
            _progress_family=transport._ProgressFamily.INTAKE), sent

    def test_fixed_starting_five_second_liveness_and_next_observed_tuple(self):
        subject, sent = self.context()
        with patch.object(transport.time, "monotonic", return_value=100.0) as clock:
            subject.execution_heartbeat()
            self.assertEqual(sent, [])
            subject.enter_execution()
            self.assertEqual(subject._domain_status, ("starting", None, None))
            self.assertEqual(sent[0]["params"], {"progressToken": "token", "progress": 1,
                                                "message": "source-intake: starting"})
            for now in (99.0, 104.999):
                clock.return_value = now
                subject.execution_heartbeat()
            self.assertEqual(len(sent), 1)
            clock.return_value = 105.0
            subject.execution_heartbeat()
            self.assertEqual(sent[-1]["params"]["message"], "Awaiting next observed status; source-intake: starting")
            self.assertNotIn("completed", json.dumps(sent))
            self.assertNotIn("total", json.dumps(sent))
            observed = {"phase": "intake_preflight", "message": PRIVATE, "total": 1000}
            subject.progress(observed)
            observed["phase"] = PRIVATE
            clock.return_value = 110.0
            subject.execution_heartbeat()
            self.assertEqual(sent[-1]["params"]["message"],
                "Awaiting next observed status; source-intake: source-intake-session-intake_preflight")
            subject.progress(event())
            clock.return_value = 115.0
            subject.execution_heartbeat()
            self.assertEqual(sent[-1]["params"]["message"],
                "Awaiting next observed status; source-intake: exact-operation-field_verified; completed items 0/1000")
        self.assertEqual([row["params"]["progress"] for row in sent], [1, 2, 3, 4, 5, 6])
        self.assertNotIn(PRIVATE, json.dumps(sent))
        # The seed is transport-owned, not an expanded caller phase vocabulary.
        self.assertIsNone(command._project_progress({"phase": "starting"}))

    def test_no_token_cancel_and_terminal_never_emit_start_or_late_progress(self):
        subject, sent = self.context(None)
        subject.enter_execution()
        subject.progress(event())
        with patch.object(transport.time, "monotonic", return_value=10 ** 12):
            subject.execution_heartbeat()
        self.assertEqual(sent, [])
        for ending in ("cancel", "terminal"):
            for before_entry in (True, False):
                with self.subTest(ending=ending, before_entry=before_entry):
                    subject, sent = self.context()
                    if not before_entry:
                        subject.enter_execution()
                    subject.cancel() if ending == "cancel" else subject.finish(None)
                    expected = len(sent)
                    subject.enter_execution()
                    subject.progress(event())
                    with patch.object(transport.time, "monotonic", return_value=10 ** 12):
                        subject.execution_heartbeat()
                        subject.queued_progress()
                    self.assertEqual(len(sent), expected)

    def test_starting_remains_family_fixed_and_legacy_constructor_compatible(self):
        for family, message in ((transport._ProgressFamily.INTAKE, "source-intake: starting"),
                                (transport._ProgressFamily.GIT, "git-backup: starting"),
                                (transport._ProgressFamily.LEGACY, None)):
            sent = []
            subject = transport.SessionRequest("token", sent.append, _progress_family=family)
            subject.enter_execution()
            self.assertEqual([row["params"]["message"] for row in sent], [] if message is None else [message])
        sent = []
        transport.SessionRequest("token", sent.append, domain_progress=True).enter_execution()
        self.assertEqual(sent[0]["params"]["message"], "source-intake: starting")
        for legacy in (False, 1):
            sent = []
            transport.SessionRequest("token", sent.append, domain_progress=legacy).enter_execution()
            self.assertEqual(sent, [])

    def test_existing_common_cancel_schema_suppresses_only_observed_cancel_failure(self):
        for observed in (False, True):
            for ok in (False, True):
                subject, sent = self.context(None)
                subject.cancel()
                if observed:
                    self.assertTrue(subject.cancel_requested())
                result = response(ok=ok)
                subject.finish(result)
                self.assertEqual(sent, [] if observed and not ok else [result])
        subject, sent = self.context(None)
        subject.cancel()
        self.assertTrue(subject.cancel_requested())
        result = response(ok=False, reason="work_session_intake_command_unavailable")
        subject.finish(result)
        self.assertEqual(sent, [result])


class BatchSchedulerTests(unittest.TestCase):
    def lane(self, handle, write=None):
        sent = []
        subject = transport.SessionStdioTransport(handle,
            write or (lambda row: sent.append(row) or True), server.jsonrpc_request_id_is_valid)
        self.addCleanup(subject.close)
        return subject, sent

    def test_only_fixed_batch_and_record_names_have_four_serial_modes(self):
        for name in ("source_intake_batch", "source_intake_record"):
            for mode in ("preview", "apply", "resume", "review_original"):
                self.assertTrue(transport.is_management_request(request(name=name, mode=mode)))
                self.assertTrue(transport._managed_mutation(request(name=name, mode=mode)))
            for mode in ("replace_original", "unknown", None, False, []):
                self.assertFalse(transport._managed_mutation(request(name=name, mode=mode)))
        for name in ("source-intake-batch", "source_intake", [], {}, None):
            self.assertFalse(transport.is_management_request(request(name=name)))

    def test_batch_metadata_and_ids_are_strict_before_tool_dispatch(self):
        implementation = server.JsonRpcMcpServer()
        lane, sent = self.lane(implementation.handle_message)
        with patch.object(implementation, "_dispatch_request") as dispatch:
            for bad in (None, True, False, 1.25, [], {}):
                lane.dispatch(request(bad))
            self.assertEqual([row["error"]["code"] for row in sent], [-32600] * 6)
            for bad in (None, True, False, 1.25, [], {}):
                lane.dispatch(request(token=bad))
            self.assertEqual([row["error"]["code"] for row in sent[6:]], [-32602] * 6)
            dispatch.assert_not_called()
        self.assertIsNone(lane._worker)

    def test_starting_precedes_first_handler_observation_and_can_repeat_without_callbacks(self):
        for name in ("source_intake_record", "source_intake_batch"):
            with self.subTest(name=name):
                started, entered, release, finished = (threading.Event() for _ in range(4))
                sent, contexts = [], []
                def handle(message):
                    self.assertTrue(started.is_set())
                    contexts.append(transport.current_session_request())
                    entered.set()
                    self.assertTrue(release.wait(5))
                    return response(message["id"])
                def write(row):
                    sent.append(row)
                    if row.get("params", {}).get("message") == "source-intake: starting":
                        started.set()
                    if row.get("id") == 1:
                        finished.set()
                    return True
                lane, _ = self.lane(handle, write)
                self.addCleanup(release.set)
                with patch.object(transport.time, "monotonic", return_value=100.0) as clock:
                    lane.dispatch(request(name=name))
                    self.assertTrue(entered.wait(2))
                    self.assertEqual(len(contexts), 1)
                    clock.return_value = 105.0
                    contexts[0].execution_heartbeat()
                    self.assertEqual(sent[-1]["params"]["message"],
                        "Awaiting next observed status; source-intake: starting")
                    self.assertEqual(len(contexts), 1)
                    self.assertFalse(any("id" in row for row in sent))
                    release.set()
                    self.assertTrue(finished.wait(3))
                    lane.close()
                self.assertNotIn(PRIVATE, json.dumps(sent))

    def test_batch_and_record_cross_in_both_directions_with_one_fixed_family_lane(self):
        for first, second in (("source_intake_batch", "source_intake_record"),
                              ("source_intake_record", "source_intake_batch")):
            with self.subTest(first=first):
                entered, release, finished = threading.Event(), threading.Event(), threading.Event()
                calls = []
                def handle(message):
                    context = transport.current_session_request()
                    calls.append((message["id"], context._progress_family if context else None))
                    if message["id"] == 1:
                        entered.set()
                        self.assertTrue(release.wait(5))
                    return response(message["id"])
                def write(row):
                    if row.get("id") == 5:
                        finished.set()
                    return True
                lane, _ = self.lane(handle, write)
                self.addCleanup(release.set)
                lane.dispatch(request(name=first))
                self.assertTrue(entered.wait(2))
                for index, name in enumerate((second, "git_backup_reconcile_plan", "archive_work_session_manage", "legacy"), 2):
                    row = request(index, index, name=name)
                    row["params"]["arguments"]["_progress_family"] = "legacy"
                    lane.dispatch(row)  # This is scheduling, not public grammar admission.
                self.assertEqual(calls, [(1, transport._ProgressFamily.INTAKE)])
                release.set()
                self.assertTrue(finished.wait(3))
                lane.close()
                self.assertEqual(calls, [(1, transport._ProgressFamily.INTAKE), (2, transport._ProgressFamily.INTAKE),
                    (3, transport._ProgressFamily.GIT), (4, transport._ProgressFamily.LEGACY), (5, None)])

    def test_queued_batch_cancel_retires_token_without_starting_and_late_record_success_survives(self):
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        calls, sent = [], []
        def handle(message):
            calls.append(message["id"])
            if message["id"] == 1:
                entered.set()
                self.assertTrue(release.wait(5))
            return response(message["id"])
        def write(row):
            sent.append(row)
            if row.get("id") == 3:
                finished.set()
            return True
        lane, _ = self.lane(handle, write)
        self.addCleanup(release.set)
        lane.dispatch(request(name="source_intake_record"))
        self.assertTrue(entered.wait(2))
        lane.dispatch(request(2, "queued", mode="resume"))
        lane.dispatch({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 2}})
        self.assertNotIn((int, 2), lane._active)
        self.assertNotIn((str, "queued"), lane._tokens)
        self.assertFalse(any(row.get("params", {}).get("progressToken") == "queued"
                             and "message" in row["params"] for row in sent))
        lane.dispatch(request(3, "queued", mode="apply"))
        lane.dispatch({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 1}})
        release.set()
        self.assertTrue(finished.wait(3))
        lane.close()
        self.assertEqual(calls, [1, 3])
        self.assertEqual([row["id"] for row in sent if "id" in row], [1, 3])
        self.assertFalse(any("error" in row for row in sent))

    def test_batch_queue_bounds_and_readonly_bypass_remain_shared(self):
        entered, release = threading.Event(), threading.Event()
        calls = []
        def handle(message):
            calls.append(message["id"])
            if message["id"] == 1:
                entered.set()
                self.assertTrue(release.wait(5))
            return response(message["id"])
        lane, sent = self.lane(handle)
        self.addCleanup(release.set)
        lane.dispatch(request())
        self.assertTrue(entered.wait(2))
        for index, method in enumerate(("ping", "tools/list"), 100):
            lane.dispatch({"jsonrpc": "2.0", "id": index, "method": method})
        lane.dispatch({"jsonrpc": "2.0", "id": 102, "method": "tools/call", "params": {"name": "archive_work_session"}})
        for index in range(transport.MAX_PENDING_REQUESTS):
            lane.dispatch(request(index + 2, index))
        lane.dispatch(request(200, "overflow"))
        large = request(201, "oversized")
        large["params"]["arguments"]["manifest"] = "x" * transport.MAX_QUEUED_MESSAGE_BYTES
        lane.dispatch(large)
        self.assertEqual(calls, [1, 100, 101, 102])
        self.assertEqual([(row["id"], row["error"]["code"]) for row in sent if "error" in row],
                         [(200, -32000), (201, -32602)])
        lane.close(wait=False)
        release.set()
        lane.close()
        self.assertEqual(calls, [1, 100, 101, 102])
        self.assertEqual(sent[-1], response())


if __name__ == "__main__":
    unittest.main()
