"""Actual public CLI/MCP single-record continuation; synthetic native/key only.

The test injects an exception after real atomic publication, not a power cut.
It is source-tree acceptance, not installed-wheel, live stdio or timing proof.
"""

from contextlib import ExitStack
import json
import os
import unittest
from unittest.mock import patch

import test_v0420_source_intake_session_public_workflow as public_fixture
from wom_kit import archive_services
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_windows as windows
from wom_kit import mcp_server as mcp
from wom_kit import source_intake_record_exact as record
from wom_kit import work_session_actor as actor
from wom_kit import work_session_source_intake_record_bundle as bundle
from wom_kit import work_session_source_intake_record_execution as domain


class PublicSingleRecordJourneyTests(unittest.TestCase):
    def setUp(self):
        self.fixture = public_fixture.PublicSessionSourceIntakeJourneyTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.input = self.root.parent / "synthetic-single-plan.json"
        value = archive_services.source_intake_plan(self.root,
            local_path=self.fixture.sources[0], redact_local_paths=True)
        self.assertTrue(value["ok"])
        self.input.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        self.server = mcp.JsonRpcMcpServer()
        self.env = patch.dict(os.environ, {mcp.MCP_ALLOWED_ROOTS_ENV: str(self.root.parent)})
        self.env.start()
        self.addCleanup(self.env.stop)

    def cli(self, *, resume=False, ok=True):
        flags = ["--resume"] if resume else ["--work-session-ref", self.fixture.session,
            "--source-intake-plan", str(self.input), "--approve", "--reviewed-by", "person:synthetic-record-reviewer"]
        return self.fixture.call("source-intake-record", *self.fixture.refs, *flags, ok=ok)

    def mcp(self, *, resume=False, ok=True):
        values = {"archive_root": str(self.root), "mode": "resume" if resume else "apply",
                  "client_app_ref": self.fixture.app, "task_route_ref": self.fixture.route}
        if not resume:
            values.update(source_intake_plan=str(self.input), reviewed_by="person:synthetic-record-reviewer",
                          work_session_ref=self.fixture.session)
        response = self.server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "source_intake_record", "arguments": values}})
        self.assertNotIn("error", response, response)
        result = response["result"]
        self.assertEqual(result["isError"], not ok, result)
        self.assertEqual(result["structuredContent"]["ok"], ok, result)
        public = json.dumps(result)
        self.assertNotIn(str(self.root), public)
        self.assertNotIn(str(self.input), public)
        return result["structuredContent"]

    def journey(self, fresh, resumed):
        files_before = self.fixture.files()
        origin_claims = self.fixture.claims()
        registry_before = self.fixture.store.read().sha256
        calls = []
        original_write = domain._SessionSourceIntakeRecordWriter.write_field

        def effect_then_cut(writer, **kwargs):
            result = original_write(writer, **kwargs)
            calls.append(kwargs["target_ref"])
            self.assertEqual((self.root / kwargs["target_ref"]).read_bytes(), writer.plan.receipt_bytes)
            raise OSError("SYNTHETIC_RECORD_PUBLICATION_CUT")

        with patch.object(domain._SessionSourceIntakeRecordWriter, "write_field", new=effect_then_cut):
            failed = fresh(ok=False)
        self.assertEqual(failed["reason_code"], "exact_human_approval_state_unknown")
        self.assertFalse(failed["original_completion_verified"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.fixture.native.calls, 2)
        selected = self.fixture.routing._read(current=False)
        pointer = selected.pending_operation().document()
        self.assertEqual(pointer["kind"], "source_intake_record")
        bound_raw = bundle._read_raw(self.root, pointer["manifest_sha256"])
        claim_files = self.fixture.claims()
        new_claims = set(claim_files) - set(origin_claims)
        self.assertEqual(len(new_claims), 1)
        started_claim = json.loads(claim_files[next(iter(new_claims))])
        self.assertEqual(started_claim["status"], "started")
        self.assertEqual(started_claim["context_sha256"], pointer["context_sha256"])
        checkpoints = [raw for path, raw in self.fixture.files().items()
            if path not in files_before and "/exact-operations/checkpoints/" in path and path.endswith(".jsonl")]
        self.assertEqual(len(checkpoints), 1)
        self.assertEqual([json.loads(row)["stage"] for row in checkpoints[0].splitlines()], ["started"])
        receipt_before = (self.root / calls[0]).read_bytes()
        self.assertEqual(self.fixture.store.read().sha256, registry_before)
        registry_before = self.fixture.register_unrelated_app()
        self.assertEqual(bundle._read_raw(self.root, pointer["manifest_sha256"]), bound_raw)
        self.input.unlink()
        with ExitStack() as stack:
            for owner, name in ((record, "plan_source_intake_record"),
                                (bundle, "_save_original_source_intake_record_context_held"),
                                (approval, "_claim_exact_human_approval_core"),
                                (windows, "_CtypesTaskDialogNative"),
                                (domain._SessionSourceIntakeRecordWriter, "write_field")):
                stack.enter_context(patch.object(owner, name, side_effect=AssertionError("original-only resume")))
            completed = resumed(resume=True)
        self.assertTrue(completed["original_completion_verified"])
        self.assertTrue(completed["completion_authentication_verified"])
        self.assertTrue(completed["independent_verification"])
        self.assertTrue(completed["actor_completion_published"])
        self.assertFalse(completed["artifact_capture_performed"])
        self.assertFalse(completed["prepared_capture_request_created"])
        self.assertFalse(completed["source_bytes_retained"])
        self.assertEqual(bundle._read_raw(self.root, pointer["manifest_sha256"]), bound_raw)
        self.assertEqual((self.root / calls[0]).read_bytes(), receipt_before)
        self.assertEqual(self.fixture.store.read().sha256, registry_before)
        self.assertEqual(set(self.fixture.claims()), set(claim_files))
        self.assertEqual(self.fixture.native.calls, 2)
        added = set(self.fixture.files()) - set(files_before)
        self.assertFalse(any("capture-requests" in path for path in added))
        for path, raw in self.fixture.source_bytes.items():
            self.assertEqual(path.read_bytes(), raw)
        before_replay = self.fixture.files()
        with ExitStack() as stack:
            for owner, name in ((record, "plan_source_intake_record"),
                                (bundle, "_save_original_source_intake_record_context_held"),
                                (domain, "_run_session_source_intake_record_exact_operation"),
                                (approval._ClaimedExactHumanApproval, "exact_terminal_record_mac"),
                                (actor.WorkSessionActorStore, "save"), (windows, "_CtypesTaskDialogNative")):
                stack.enter_context(patch.object(owner, name, side_effect=AssertionError("read-only original replay")))
            replay = fresh(resume=True)
        self.assertTrue(replay["original_operation_already_completed"])
        self.assertFalse(replay["writes_performed"] or replay["actor_completion_published"])
        self.assertEqual(self.fixture.files(), before_replay)
        for marker in (self.fixture.app, self.fixture.route, self.fixture.session, str(self.root),
                       "SYNTHETIC_RECORD_PUBLICATION_CUT"):
            self.assertNotIn(marker, json.dumps([failed, completed, replay]))

    def test_cli_publication_cut_mcp_original_resume_cli_completed_replay(self):
        self.journey(self.cli, self.mcp)

    def test_mcp_publication_cut_cli_original_resume_mcp_completed_replay(self):
        self.journey(self.mcp, self.cli)


if __name__ == "__main__":
    unittest.main()
