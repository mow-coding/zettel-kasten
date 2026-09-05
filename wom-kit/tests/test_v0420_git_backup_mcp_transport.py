"""Git transport scheduling/projection, not domain or approval acceptance proof."""

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from wom_kit import _mcp_session_transport as transport
from wom_kit import exact_operation_manifest as exact
from wom_kit import mcp_server as server
from wom_kit import work_session_git_progress as git_progress
from wom_kit import work_session_wait as waiting


PRIVATE = "SYNTHETIC_PRIVATE_GIT_INPUT"


def request(request_id=1, token="git-progress", *, mode="preview", name="git_backup_reconcile_plan"):
    return {"jsonrpc": "2.0", "id": request_id, "method": "tools/call", "params": {
        "name": name, "arguments": {"mode": mode, "archive_root": PRIVATE},
        "_meta": {"progressToken": token}}}


def response(request_id=1, *, ok=True, original=False, reason="work_session_wait_cancelled",
             schema="wom-kit/git-backup-session-command/v1"):
    return {"jsonrpc": "2.0", "id": request_id, "result": {"structuredContent": {
        "schema": schema, "ok": ok, "reason_code": reason, "original_commit_verified": original}}}


def event(**changes):
    original = exact.ExactOperationProgress(
        manifest_sha256=PRIVATE, execution_sha256=PRIVATE, mode="apply", stage="field_verified",
        completed_items=0, total_items=1, completed_fields=1, total_fields=2)
    return replace(original, **changes)


class GitProgressTests(unittest.TestCase):
    def context(self, token="token"):
        sent = []
        return transport.SessionRequest(token, sent.append,
            _progress_family=transport._ProgressFamily.GIT), sent

    def test_family_is_private_closed_and_old_constructor_behavior_is_unchanged(self):
        for value, expected in ((True, transport._ProgressFamily.INTAKE),
                                (False, transport._ProgressFamily.LEGACY),
                                (1, transport._ProgressFamily.LEGACY)):
            subject = transport.SessionRequest(None, lambda _row: None, domain_progress=value)
            self.assertIs(subject._progress_family, expected)
        for value in ("git", True, 1, {}, object()):
            with self.subTest(kind=type(value).__name__), self.assertRaisesRegex(ValueError, "Invalid MCP progress family"):
                transport.SessionRequest(None, lambda _row: None, _progress_family=value)

    def test_git_reuses_closed_projector_and_renders_only_observed_numeric_pairs(self):
        subject, sent = self.context()
        with patch.object(git_progress, "_project", wraps=git_progress._project) as project, \
             patch.object(exact.ExactOperationProgress, "public_document", side_effect=AssertionError("arbitrary callback")):
            for stage in sorted(git_progress._STAGES):
                subject.progress({"phase": stage, "current": 2, "total": 3, "path": PRIVATE,
                                  "message": PRIVATE, "public_document": object()})
            for stage in ("preflight", "heartbeat", "item_started", "field_verified", "item_verified", "completed"):
                subject.progress(event(stage=stage))
        self.assertEqual(project.call_count, len(git_progress._STAGES) + 6)
        self.assertEqual(len(sent), project.call_count)
        self.assertTrue(all("observed units 2/3" in row["params"]["message"] for row in sent[:-6]))
        self.assertTrue(all("completed items 0/1; completed fields 1/2" in row["params"]["message"] for row in sent[-6:]))
        self.assertTrue(all(set(row["params"]) == {"progressToken", "progress", "message"} for row in sent))
        self.assertEqual([row["params"]["progress"] for row in sent], list(range(1, len(sent) + 1)))
        self.assertNotIn(PRIVATE, json.dumps(sent))
        self.assertEqual(repr(subject), "<McpSessionRequest>")

    def test_hostile_objects_subclasses_and_invalid_numbers_never_project(self):
        class Duck:
            def public_document(self):
                raise AssertionError("arbitrary document")
            def __repr__(self):
                raise AssertionError("arbitrary repr")
        class DictSubclass(dict):
            def get(self, *_args):
                raise AssertionError("arbitrary mapping")
        class EventSubclass(exact.ExactOperationProgress):
            pass
        class StringSubclass(str):
            pass
        subject, sent = self.context()
        invalid = [Duck(), DictSubclass(stage="completed"), {"stage": StringSubclass("completed")},
                   {"stage": []}, {"phase": PRIVATE},
                   EventSubclass(PRIVATE, PRIVATE, "apply", "completed", 1, 1, 1, 1)]
        invalid += [{"stage": "heartbeat", "completed_items": value}
                    for value in (True, -1, 1.0, (1 << 53), Duck())]
        invalid += [{"stage": "heartbeat", "elapsed_seconds": value}
                    for value in (False, float("nan"), float("inf"), -1.0)]
        for value in invalid:
            subject.progress(value)
        self.assertEqual(sent, [])

    def test_incomplete_or_reversed_counts_do_not_invent_a_total_or_completion(self):
        subject, sent = self.context()
        for counts in ({"completed_items": 4}, {"total_items": 4},
                       {"completed_items": 5, "total_items": 4}, {"current": 2, "total": 1}):
            subject.progress({"stage": "completed", **counts})
        self.assertTrue(all(row["params"]["message"] == "git-backup: completed" for row in sent))
        subject.progress({"stage": "heartbeat", "completed_bytes": 0, "total_bytes": (1 << 53) - 1})
        self.assertEqual(sent[-1]["params"]["message"], "git-backup: heartbeat; completed bytes 0/9007199254740991")
        self.assertNotIn("completion_verified", json.dumps(sent))

    def test_internal_malformed_mapping_keys_cannot_run_equality_during_projection(self):
        class StringKey(str):
            __hash__ = str.__hash__
            def __eq__(self, _other):
                raise AssertionError("arbitrary key equality")
        class ObjectKey:
            def __hash__(self):
                return hash("stage")
            def __eq__(self, _other):
                raise AssertionError("arbitrary key equality")
        subject, sent = self.context()
        with patch.object(git_progress, "_project", wraps=git_progress._project) as project:
            for value in ({StringKey("stage"): "completed"}, {ObjectKey(): "completed"},
                          {"stage": "completed", 1: PRIVATE}):
                subject.progress(value)
            project.assert_not_called()
        self.assertEqual(sent, [])

    def test_starting_and_five_second_heartbeat_repeat_only_detached_last_observation(self):
        subject, sent = self.context()
        with patch.object(transport.time, "monotonic", return_value=100.0) as clock:
            subject.execution_heartbeat()
            self.assertEqual(sent, [])
            subject.enter_execution()
            self.assertEqual(sent[-1]["params"]["message"], "git-backup: starting")
            for now in (99.0, 104.999):
                clock.return_value = now
                subject.execution_heartbeat()
            self.assertEqual(len(sent), 1)
            clock.return_value = 105.0
            subject.execution_heartbeat()
            self.assertEqual(sent[-1]["params"]["message"], "Awaiting next observed status; git-backup: starting")
            observation = {"stage": "git_original_preimage", "completed_items": 0, "total_items": 2}
            subject.progress(observation)
            observation.update(stage=PRIVATE, completed_items=2, total_items=99)
            clock.return_value = 110.0
            subject.execution_heartbeat()
            self.assertEqual(sent[-1]["params"]["message"],
                "Awaiting next observed status; git-backup: git_original_preimage; completed items 0/2")
            subject.queued_progress()
            self.assertEqual(len(sent), 4)
        self.assertEqual([row["params"]["progress"] for row in sent], [1, 2, 3, 4])
        self.assertNotIn(PRIVATE, json.dumps(sent))

    def test_no_token_cancel_and_terminal_stop_starting_and_domain_liveness(self):
        subject, sent = self.context(None)
        subject.enter_execution()
        subject.progress(event())
        subject.execution_heartbeat()
        self.assertEqual(sent, [])
        for ending in ("cancel", "terminal"):
            for before_entry in (True, False):
                subject, sent = self.context()
                if not before_entry:
                    subject.enter_execution()
                subject.cancel() if ending == "cancel" else subject.finish(None)
                count = len(sent)
                subject.enter_execution()
                subject.progress(event())
                with patch.object(transport.time, "monotonic", return_value=10 ** 12):
                    subject.execution_heartbeat()
                    subject.queued_progress()
                self.assertEqual(len(sent), count)

    def test_only_observed_known_cancel_failure_without_verified_original_is_suppressed(self):
        for observed in (False, True):
            for ok in (False, True):
                for original in (False, True):
                    with self.subTest(observed=observed, ok=ok, original=original):
                        subject, sent = self.context(None)
                        subject.cancel()
                        if observed:
                            self.assertTrue(subject.cancel_requested())
                        result = response(ok=ok, original=original)
                        subject.finish(result)
                        self.assertEqual(sent, [] if observed and not ok and not original else [result])
        for result in (response(ok=False, schema="unknown"), response(ok=False, reason="work_session_git_state_unknown")):
            subject, sent = self.context(None)
            subject.cancel()
            self.assertTrue(subject.cancel_requested())
            subject.finish(result)
            self.assertEqual(sent, [result])


class GitSchedulerTests(unittest.TestCase):
    def lane(self, handle, write=None):
        sent = []
        subject = transport.SessionStdioTransport(handle,
            write or (lambda row: sent.append(row) or True), server.jsonrpc_request_id_is_valid)
        self.addCleanup(subject.close)
        return subject, sent

    def test_exact_tool_and_all_four_modes_select_serial_lane(self):
        for mode in ("preview", "apply", "resume", "review_original"):
            self.assertTrue(transport.is_management_request(request(mode=mode)))
            self.assertTrue(transport._managed_mutation(request(mode=mode)))
        for mode in (None, False, [], "review-original", "unknown"):
            self.assertFalse(transport._managed_mutation(request(mode=mode)))
        self.assertFalse(transport.is_management_request(request(name="git_backup")))
        entered, release, completed = threading.Event(), threading.Event(), threading.Event()
        calls = []
        def handle(message):
            context = transport.current_session_request()
            calls.append((message["id"], context._progress_family if context else None))
            if message["id"] == 1:
                entered.set()
                self.assertTrue(release.wait(5))
            return response(message["id"])
        def write(row):
            if row.get("id") == 4:
                completed.set()
            return True
        lane, _ = self.lane(handle, write)
        self.addCleanup(release.set)
        for index, mode in enumerate(("preview", "apply", "resume", "review_original"), 1):
            lane.dispatch(request(index, index, mode=mode))
            if index == 1:
                self.assertTrue(entered.wait(2))
        self.assertEqual(calls, [(1, transport._ProgressFamily.GIT)])
        release.set()
        self.assertTrue(completed.wait(4))
        lane.close()
        self.assertEqual(calls, [(index, transport._ProgressFamily.GIT) for index in range(1, 5)])

    def test_git_preserves_management_metadata_and_strict_ids(self):
        implementation = server.JsonRpcMcpServer()
        lane, sent = self.lane(implementation.handle_message)
        # Basic malformed JSON-RPC still belongs to the existing server, while
        # the transport adds stricter managed IDs/tokens before tool dispatch.
        with patch.object(implementation, "_dispatch_request") as dispatch:
            for bad in (None, True, False, 1.25, [], {}):
                lane.dispatch(request(bad))
            self.assertTrue(all(row["error"]["code"] == -32600 for row in sent))
            for bad in (None, True, False, 1.25, [], {}):
                lane.dispatch(request(token=bad))
            self.assertTrue(all(row["error"]["code"] == -32602 for row in sent[6:]))
            dispatch.assert_not_called()
        self.assertIsNone(lane._worker)

    def test_queue_bounds_tokens_and_read_only_bypass_remain_shared(self):
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
        lane.dispatch(request(2))  # Active progress token is not reusable.
        for index, name in enumerate(("ping", "tools/list", "archive_work_session"), 101):
            message = {"jsonrpc": "2.0", "id": index, "method": name}
            if name == "archive_work_session":
                message.update(method="tools/call", params={"name": name, "arguments": {}})
            lane.dispatch(message)
        for index in range(transport.MAX_PENDING_REQUESTS):
            lane.dispatch(request(index + 3, index))
        lane.dispatch(request(200, "overflow"))
        oversized = request(201, "oversized")
        oversized["params"]["arguments"]["private"] = "x" * transport.MAX_QUEUED_MESSAGE_BYTES
        lane.dispatch(oversized)
        self.assertEqual(calls, [1, 101, 102, 103])
        self.assertEqual([(row["id"], row["error"]["code"]) for row in sent if "error" in row],
                         [(2, -32600), (200, -32000), (201, -32602)])
        lane.close(wait=False)
        release.set()
        lane.close()
        self.assertEqual(calls, [1, 101, 102, 103])
        self.assertEqual(sent[-1], response())

    def test_git_record_management_and_legacy_share_one_lane_with_fixed_families(self):
        entered, release, drained = threading.Event(), threading.Event(), threading.Event()
        calls = []
        def handle(message):
            context = transport.current_session_request()
            calls.append((message["params"]["name"], context._progress_family if context else None))
            if message["id"] == 1:
                entered.set()
                self.assertTrue(release.wait(5))
            return response(message["id"])
        def write(row):
            if row.get("id") == 4:
                drained.set()
            return True
        lane, _ = self.lane(handle, write)
        self.addCleanup(release.set)
        lane.dispatch(request())
        self.assertTrue(entered.wait(2))
        for index, name in enumerate(("source_intake_record", "archive_work_session_manage", "legacy"), 2):
            row = request(index, index, name=name)
            row["params"]["arguments"]["_progress_family"] = "git"
            lane.dispatch(row)  # Scheduling never treats request fields as progress authority.
        self.assertEqual(len(calls), 1)
        release.set()
        self.assertTrue(drained.wait(4))
        lane.close()
        self.assertEqual(calls, [("git_backup_reconcile_plan", transport._ProgressFamily.GIT),
                                ("source_intake_record", transport._ProgressFamily.INTAKE),
                                ("archive_work_session_manage", transport._ProgressFamily.LEGACY), ("legacy", None)])

    def test_entered_git_liveness_is_independent_and_cancel_does_not_terminate_it(self):
        entered, release, heartbeat = threading.Event(), threading.Event(), threading.Event()
        sent, callbacks = [], []
        def handle(message):
            context = transport.current_session_request()
            callbacks.append("one-safe-observation")
            context.progress(event())
            entered.set()
            self.assertTrue(release.wait(5))
            return response(message["id"], original=True)
        def write(row):
            sent.append(row)
            if row.get("params", {}).get("message", "").startswith("Awaiting next observed status;"):
                heartbeat.set()
            return True
        lane, _ = self.lane(handle, write)
        self.addCleanup(release.set)
        with patch.object(transport, "QUEUE_HEARTBEAT_SECONDS", 0.01):
            lane.dispatch(request())
            self.assertTrue(entered.wait(2))
            self.assertTrue(heartbeat.wait(3))
            self.assertEqual(callbacks, ["one-safe-observation"])
            lane.dispatch({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 1}})
            lane.close(wait=False)
            self.assertTrue(lane._worker.is_alive())
            self.assertFalse(any("id" in row for row in sent))
            count = len(sent)
            context = lane._active[(int, 1)][0]
            context.execution_heartbeat()
            self.assertEqual(len(sent), count)
            release.set()
            lane.close()
        self.assertFalse(lane._worker.is_alive())
        self.assertFalse(lane._heartbeat.is_alive())
        self.assertEqual(sent[-1], response(original=True))
        self.assertNotIn(PRIVATE, json.dumps(sent))

    def test_git_os_lock_wait_cancels_cooperatively_without_releasing_original_holder(self):
        busy, finished = threading.Event(), threading.Event()
        entered = []
        original_enter = exact.ExactOperationWriterLock.__enter__
        def observing_enter(held):
            try:
                return original_enter(held)
            except exact.ExactOperationManifestError as error:
                if error.code == "exact_operation_writer_busy":
                    busy.set()
                raise
        with tempfile.TemporaryDirectory(prefix="wom-git-mcp-wait-") as directory:
            root = Path(directory)
            def handle(message):
                context = transport.current_session_request()
                try:
                    with waiting.wait_for_archive_writer(root, cancel_requested=context.cancel_requested,
                                                         progress=context.progress):
                        entered.append("domain")
                    return response(message["id"])
                except waiting.WorkSessionWaitError as error:
                    self.assertEqual(str(error), "work_session_wait_cancelled")
                    return response(message["id"], ok=False)
                finally:
                    finished.set()
            lane, sent = self.lane(handle)
            with exact.ExactOperationWriterLock(root) as owner, \
                 patch.object(exact.ExactOperationWriterLock, "__enter__", observing_enter):
                lane.dispatch(request())
                self.assertTrue(busy.wait(3))  # A real competing OS acquisition failed.
                lane.dispatch({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 1}})
                self.assertTrue(finished.wait(3))
                lane.close()
                owner.verify_held()
                with self.assertRaisesRegex(exact.ExactOperationManifestError, "exact_operation_writer_busy"):
                    with exact.ExactOperationWriterLock(root, timeout_seconds=0):
                        self.fail("original owner lock was released")
            self.assertEqual(entered, [])
            self.assertFalse(any("id" in row for row in sent))
            self.assertTrue(any(row["params"].get("message") == "git-backup: waiting_for_writer" for row in sent))


if __name__ == "__main__":
    unittest.main()
