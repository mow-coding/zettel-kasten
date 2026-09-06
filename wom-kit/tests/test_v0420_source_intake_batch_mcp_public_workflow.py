"""Real public batch CLI/MCP original continuation; synthetic native/key only.

The first actual receipt publication is interrupted before its checkpoint.
These source-tree, in-process JSON-RPC tests are not installed, stdio, timing
or power-loss acceptance. A prepared capture request is not captured bytes.
"""

from contextlib import ExitStack
import hashlib
import json
import os
import unittest
from unittest.mock import patch

import test_v0420_source_intake_session_public_workflow as public_fixture
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import exact_operation_manifest as exact
from wom_kit import mcp_server as mcp
from wom_kit import source_intake_batch_exact as intake
from wom_kit import work_session_actor as actor
from wom_kit import work_session_source_intake_bundle as bundle
from wom_kit import work_session_source_intake_inventory as inventory


class SourceIntakeBatchMcpPublicWorkflowTests(unittest.TestCase):
    def setUp(self):
        # Public register/request/create/claim and sources, not seeded authority.
        # Composition avoids inheriting or rerunning the old test methods.
        self.fixture = public_fixture.PublicSessionSourceIntakeJourneyTests("runTest")
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.root = self.fixture.root
        self.server = mcp.JsonRpcMcpServer()
        self.request_id = 0
        self.outputs = []
        # The existing caller JSON is a sibling of this temporary archive.
        roots = patch.dict(os.environ, {mcp.MCP_ALLOWED_ROOTS_ENV: str(self.root.parent)})
        roots.start()
        self.addCleanup(roots.stop)

    def cli(self, *, resume=False, ok=True):
        flags = ["--resume"] if resume else ["--work-session-ref", self.fixture.session,
            "--manifest", str(self.fixture.request), "--approve", "--reviewed-by", "person:synthetic-intake-reviewer"]
        result = self.fixture.call("source-intake-batch", *self.fixture.refs, *flags, ok=ok)
        self.outputs.append(result)
        return result

    def mcp(self, *, resume=False, ok=True):
        values = {"archive_root": str(self.root), "mode": "resume" if resume else "apply",
                  "client_app_ref": self.fixture.app, "task_route_ref": self.fixture.route}
        if not resume:
            values.update(manifest=str(self.fixture.request), reviewed_by="person:synthetic-intake-reviewer",
                          work_session_ref=self.fixture.session)
        self.request_id += 1
        response = self.server.handle_message({"jsonrpc": "2.0", "id": self.request_id,
            "method": "tools/call", "params": {"name": "source_intake_batch", "arguments": values}})
        self.assertNotIn("error", response, response)
        self.assertEqual(response["id"], self.request_id)
        result = response["result"]
        self.assertIs(result["isError"], not ok, result)
        public = result["structuredContent"]
        self.assertIs(public["ok"], ok, result)
        self.assertEqual(public["schema"], "wom-kit/source-intake-session-command/v1")
        self.assertNotIn("prepared_capture_request", public)
        for private in (str(self.root), str(self.fixture.request), self.fixture.app,
                        self.fixture.route, self.fixture.session, "SYNTHETIC_PRIVATE"):
            self.assertNotIn(private, json.dumps(result))
        self.outputs.append(public)
        return public

    @staticmethod
    def identity(path):
        value = path.stat()
        return value.st_dev, value.st_ino, value.st_nlink, value.st_size, value.st_mtime_ns

    def original_only(self, *, completed=False):
        stack = ExitStack()
        forbidden = [
            (intake, "plan_source_intake_batch"), (intake, "_request_items"),
            (bundle, "_save_original_source_intake_context_held"),
            (approval, "_claim_exact_human_approval_core"), (broker, "_claim_exact_human_approval_core"),
            (windows, "_CtypesTaskDialogNative"),
            (inventory, "_capture_source_intake_context_inventory_held"),
            (inventory, "_capture_source_intake_record_context_inventory_held"),
        ]
        if completed:
            forbidden.extend([
                (intake, "_revalidate_item"), (intake, "_run_session_source_intake_batch_exact_operation"),
                (intake._SessionSourceIntakeWriter, "write_field"), (intake._Writer, "write_field"),
                (intake, "_completion_authenticator"), (exact.FileExactOperationCheckpointStore, "finalize"),
                (actor.WorkSessionActorStore, "save"),
            ])
        # Do not forbid pure recomputation of an OLD MAC during authentication.
        # Concrete writer/authenticator/finalize above forbid new evidence.
        for owner, name in forbidden:
            stack.enter_context(patch.object(owner, name, side_effect=AssertionError("original-only intake continuation")))
        return stack

    def journey(self, fresh, resume):
        original_files, original_claims = self.fixture.files(), self.fixture.claims()
        registry_before = self.fixture.store.read().sha256
        archive_before = (self.root / "archive.yml").read_bytes()
        effects = []
        write_field = intake._SessionSourceIntakeWriter.write_field

        def effect_then_cut(writer, **kwargs):
            result = write_field(writer, **kwargs)
            writer.held.verify_held()
            if kwargs["target_kind"] == intake.TARGET_KIND and not effects:
                path = self.root / kwargs["target_ref"]
                effects.append((kwargs["target_ref"], path.read_bytes(), self.identity(path)))
                raise OSError("SYNTHETIC_PRIVATE_BATCH_PUBLICATION_CUT")
            return result

        with patch.object(intake._SessionSourceIntakeWriter, "write_field", new=effect_then_cut):
            failed = fresh(ok=False)
        self.assertEqual(failed["reason_code"], "exact_human_approval_state_unknown", failed)
        self.assertFalse(failed["original_completion_verified"])
        self.assertEqual(len(effects), 1, failed)
        self.assertEqual(self.fixture.native.calls, 2)
        pointer = self.fixture.routing._read(current=False).pending_operation().document()
        self.assertEqual(pointer["kind"], "source_intake_batch")
        bound = self.fixture.retained(pointer)
        plan, context = bound.prepared.plan, bound.context
        self.assertEqual(len(plan.items), 2)
        self.assertEqual(plan.manifest.work_session_binding, self.fixture.store.read().binding(self.fixture.session))
        self.assertEqual(sum((self.root / item.receipt_relative_path).is_file() for item in plan.items), 1)
        capture = plan.prepared_capture_request
        self.assertFalse((self.root / capture.relative_path).exists())
        cut_claims = self.fixture.claims()
        added_claims = set(cut_claims) - set(original_claims)
        self.assertEqual(len(added_claims), 1)
        claim_name = next(iter(added_claims))
        started = json.loads(cut_claims[claim_name])
        self.assertEqual(started["status"], "started")
        self.assertEqual(started["context_sha256"], pointer["context_sha256"])
        self.assertEqual(started["context"]["plan_sha256"], plan.manifest.manifest_sha256)
        checkpoint_prefix = {path: raw for path, raw in self.fixture.files().items()
            if path not in original_files and "/exact-operations/checkpoints/" in path and path.endswith(".jsonl")}
        self.assertEqual(len(checkpoint_prefix), 1)
        for raw in checkpoint_prefix.values():
            self.assertEqual([json.loads(row)["stage"] for row in raw.splitlines()], ["started"])
        self.assertEqual(self.fixture.request.read_bytes(), self.fixture.original_request_bytes)
        self.assertEqual({path: path.read_bytes() for path in self.fixture.sources}, self.fixture.source_bytes)
        self.fixture.request.unlink()  # Delete only the original caller's fixture JSON.
        writes = []

        def observe_write(writer, **kwargs):
            writes.append(kwargs["target_ref"])
            return write_field(writer, **kwargs)

        with self.original_only(), patch.object(intake._SessionSourceIntakeWriter, "write_field", new=observe_write):
            completed = resume(resume=True)
        self.assertTrue(completed["original_completion_verified"] and completed["completion_authentication_verified"])
        self.assertTrue(completed["independent_verification"] and completed["actor_completion_published"])
        self.assertFalse(completed["original_operation_already_completed"] or completed["artifact_capture_performed"])
        self.assertTrue(completed["requires_new_capture_approval"])
        self.assertEqual(completed["completed_item_count"], 2)
        expected_writes = {item.receipt_relative_path for item in plan.items if item.receipt_relative_path != effects[0][0]}
        expected_writes.add(capture.relative_path)
        self.assertEqual(len(writes), len(expected_writes))
        self.assertEqual(set(writes), expected_writes)
        self.assertEqual(self.identity(self.root / effects[0][0]), effects[0][2])
        self.assertEqual((self.root / effects[0][0]).read_bytes(), effects[0][1])
        self.assertEqual(self.fixture.retained(pointer)._raw, bound._raw)
        self.assertEqual(self.fixture.retained(pointer).context, context)
        self.assertEqual(completed["context_sha256"], pointer["context_sha256"])
        self.assertEqual(set(self.fixture.claims()), set(cut_claims))
        succeeded = json.loads(self.fixture.claims()[claim_name])
        self.assertEqual(succeeded["status"], "succeeded")
        for field in ("approval_id", "context", "context_sha256", "approval_authority_sha256",
                      "reviewer_claim_sha256", "approved_at", "started_at"):
            self.assertEqual(succeeded[field], started[field])
        for name, raw in original_claims.items():
            self.assertEqual(self.fixture.claims()[name], raw)
        for path, raw in checkpoint_prefix.items():
            self.assertTrue(self.fixture.files()[path].startswith(raw))
            self.assertTrue(path.endswith(completed["execution_sha256"][7:] + ".jsonl"))
        selected = self.fixture.routing._read(current=False)
        self.assertIsNone(selected.pending_operation())
        self.assertEqual(selected.document()["last_completed_operation"], pointer)
        self.assertEqual(self.fixture.store.read().sha256, registry_before)

        # Independent original common MAC/checkpoint/whole-output verification.
        final = exact.load_exact_operation_final_receipt_read_only(self.root, completed["execution_sha256"])
        self.assertEqual(final["receipt_sha256"], completed["common_final_receipt_sha256"])
        self.assertEqual(final["result"]["completion_authentication"]["approval_reference"]["approval_id"], started["approval_id"])
        verified = intake.reconcile_source_intake_batch(plan,
            execution_sha256=completed["execution_sha256"], key_provider=self.fixture.key)
        self.assertTrue(verified["ok"] and verified["completion_authentication_verified"] and verified["independent_verification"])
        for item, source in zip(plan.items, self.fixture.sources):
            self.assertEqual((self.root / item.receipt_relative_path).read_bytes(), item.receipt_bytes)
            self.assertEqual(item.capture_staged_path, source.relative_to(self.root).as_posix())
            self.assertEqual(item.source_bytes_sha256, "sha256:" + hashlib.sha256(self.fixture.source_bytes[source]).hexdigest())
            self.assertEqual(source.read_bytes(), self.fixture.source_bytes[source])
        self.assertEqual((self.root / capture.relative_path).read_bytes(), capture.request_bytes)

        for source in self.fixture.sources:
            source.unlink()  # Fixture-owned source inputs, only after completed metadata recording.
        self.assertFalse(self.fixture.request.exists())
        before_replay = self.fixture.files()
        with self.original_only(completed=True):
            replay = fresh(resume=True)
        self.assertTrue(replay["original_operation_already_completed"] and replay["original_completion_verified"])
        self.assertTrue(replay["completion_authentication_verified"] and replay["independent_verification"])
        self.assertFalse(replay["writes_performed"] or replay["actor_completion_published"])
        self.assertFalse(replay["source_bytes_reverified"] or replay["artifact_capture_performed"])
        self.assertEqual(replay["execution_sha256"], completed["execution_sha256"])
        self.assertEqual(replay["common_final_receipt_sha256"], completed["common_final_receipt_sha256"])
        self.assertEqual(self.fixture.files(), before_replay)
        self.assertEqual(self.fixture.native.calls, 2)
        self.assertEqual((self.root / "archive.yml").read_bytes(), archive_before)
        self.assertFalse(self.fixture.key.active)
        for marker in ("SYNTHETIC_PRIVATE", str(self.root), str(self.fixture.request), started["approval_id"],
                       self.fixture.routing._read(current=False).document()["claim_ref"]):
            self.assertNotIn(marker, json.dumps(self.outputs))

    def test_cli_receipt_cut_mcp_original_resume_cli_source_free_completed_replay(self):
        self.journey(self.cli, self.mcp)

    def test_mcp_receipt_cut_cli_original_resume_mcp_source_free_completed_replay(self):
        self.journey(self.mcp, self.cli)


if __name__ == "__main__":
    unittest.main()
