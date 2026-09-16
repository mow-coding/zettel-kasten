"""Actual intake original re-review across public CLI/MCP, with synthetic UI/key.

A deliberate preclaim exception leaves the genuine retained bundle/pending
actor but no intake approval claim. Metadata recording is real; source custody,
installed transport, timing and native power-loss acceptance are not asserted.
"""

from contextlib import ExitStack
import hashlib
import json
import os
import unittest
from unittest.mock import patch

import test_v0420_source_intake_session_public_workflow as public_fixture
from wom_kit import archive_services
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import exact_operation_manifest as exact
from wom_kit import mcp_server as mcp
from wom_kit import source_intake_batch_exact as batch
from wom_kit import source_intake_record_exact as record
from wom_kit import work_session_actor as actor
from wom_kit import work_session_source_intake_bundle as batch_bundle
from wom_kit import work_session_source_intake_completion as completion
from wom_kit import work_session_source_intake_inventory as inventory
from wom_kit import work_session_source_intake_record_bundle as record_bundle
from wom_kit import work_session_source_intake_record_execution as record_domain


class SourceIntakeOriginalReviewPublicWorkflowTests(unittest.TestCase):
    def prepare(self, family):
        # Compose public lifecycle setup only, never inherit its test cases.
        self.fixture = public_fixture.PublicSessionSourceIntakeJourneyTests("runTest")
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.family, self.root = family, self.fixture.root
        self.command = "source-intake-" + family
        self.tool = "source_intake_" + family
        self.input_key = "manifest" if family == "batch" else "source_intake_plan"
        self.input = self.fixture.request
        self.sources = self.fixture.sources if family == "batch" else self.fixture.sources[:1]
        if family == "record":
            value = archive_services.source_intake_plan(self.root, local_path=self.sources[0], redact_local_paths=True)
            self.assertTrue(value["ok"])
            self.input = self.root.parent / "synthetic-original-record.json"
            self.input.write_text(json.dumps(value), encoding="utf-8")
        self.server, self.request_id, self.outputs = mcp.JsonRpcMcpServer(), 0, []
        roots = patch.dict(os.environ, {mcp.MCP_ALLOWED_ROOTS_ENV: str(self.root.parent)})
        roots.start()
        self.addCleanup(roots.stop)

    def cli(self, mode, *, ok=True):
        if mode == "apply":
            flags = ["--approve", "--work-session-ref", self.fixture.session,
                "--" + self.input_key.replace("_", "-"), str(self.input), "--reviewed-by", "person:synthetic-intake-reviewer"]
        else:
            flags = ["--resume"] if mode == "resume" else ["--approve", "--review-original"]
        result = self.fixture.call(self.command, *self.fixture.refs, *flags, ok=ok)
        self.outputs.append(result)
        return result

    def mcp(self, mode, *, ok=True):
        arguments = {"archive_root": str(self.root), "mode": mode,
                     "client_app_ref": self.fixture.app, "task_route_ref": self.fixture.route}
        if mode == "apply":
            arguments.update(work_session_ref=self.fixture.session, reviewed_by="person:synthetic-intake-reviewer")
            arguments[self.input_key] = str(self.input)
        self.request_id += 1
        response = self.server.handle_message({"jsonrpc": "2.0", "id": self.request_id,
            "method": "tools/call", "params": {"name": self.tool, "arguments": arguments}})
        self.assertNotIn("error", response, response)
        result = response["result"]
        self.assertIs(result["isError"], not ok, result)
        public = result["structuredContent"]
        self.assertIs(public["ok"], ok, result)
        self.assertEqual(public["schema"], "wom-kit/source-intake-session-command/v1")
        for private in (str(self.root), str(self.input), self.fixture.app, self.fixture.route, self.fixture.session,
                        "SYNTHETIC_PRIVATE"):
            self.assertNotIn(private, json.dumps(result))
        self.outputs.append(public)
        return public

    def retained(self, pointer):
        load = (batch_bundle._load_original_source_intake_context_held if self.family == "batch"
                else record_bundle._load_original_source_intake_record_context_held)
        with exact.ExactOperationWriterLock(self.root) as held:
            return load(self.root, manifest_sha256=pointer["manifest_sha256"], held=held)

    def metadata(self, plan):
        if self.family == "record":
            return {plan.receipt_relative_path: plan.receipt_bytes}
        return {**{item.receipt_relative_path: item.receipt_bytes for item in plan.items},
                plan.prepared_capture_request.relative_path: plan.prepared_capture_request.request_bytes}

    def original_only(self, *, no_effects=False):
        stack = ExitStack()
        forbidden = [
            (batch, "plan_source_intake_batch"), (batch, "_request_items"), (record, "plan_source_intake_record"),
            (batch_bundle, "_save_original_source_intake_context_held"),
            (record_bundle, "_save_original_source_intake_record_context_held"),
            (inventory, "_capture_source_intake_context_inventory_held"),
            (inventory, "_capture_source_intake_record_context_inventory_held"),
        ]
        if no_effects:
            forbidden.extend([
                (batch, "_run_session_source_intake_batch_exact_operation"),
                (record_domain, "_run_session_source_intake_record_exact_operation"),
                (batch._SessionSourceIntakeWriter, "write_field"), (record_domain._SessionSourceIntakeRecordWriter, "write_field"),
                (batch, "_completion_authenticator"), (exact.FileExactOperationCheckpointStore, "finalize"),
                (actor.WorkSessionActorStore, "save"), (broker, "_claim_exact_human_approval_core"),
                (approval, "_claim_exact_human_approval_core"), (windows, "_CtypesTaskDialogNative"),
            ])
        # Old receipt MAC recomputation remains real; new evidence generation
        # and publication have concrete, separate sentinels above.
        for owner, name in forbidden:
            stack.enter_context(patch.object(owner, name, side_effect=AssertionError("original intake must be preserved")))
        return stack

    def journey(self, family, fresh, review):
        self.prepare(family)
        original_files, original_claims = self.fixture.files(), self.fixture.claims()
        registry_before = self.fixture.store.read().sha256
        fresh_contexts = []
        request_native = broker._request_exact_human_approval_core

        def first_review(context, **options):
            fresh_contexts.append(approval.exact_human_approval_context_sha256(context))
            return request_native(context, **options)

        with patch.object(broker, "_request_exact_human_approval_core", side_effect=first_review), \
             patch.object(broker, "_claim_exact_human_approval_core", side_effect=RuntimeError("SYNTHETIC_PRIVATE_INTAKE_PRECLAIM_CUT")) as cut:
            failed = fresh("apply", ok=False)
        self.assertEqual(cut.call_count, 1, failed)
        cut.assert_called_once()
        self.assertFalse(failed["original_completion_verified"])
        self.assertEqual(self.fixture.native.calls, 2)
        self.assertEqual(self.fixture.claims(), original_claims)
        selected = self.fixture.routing._read(current=False)
        pending_raw, pointer = selected._raw, selected.pending_operation().document()
        self.assertEqual(pointer["kind"], "source_intake_" + family)
        original = self.retained(pointer)
        plan, context = original.prepared.plan, original.context
        outputs = self.metadata(plan)
        self.assertEqual(fresh_contexts, [pointer["context_sha256"]])
        self.assertEqual(approval.exact_human_approval_context_sha256(context), pointer["context_sha256"])
        self.assertEqual(plan.manifest.work_session_binding, self.fixture.store.read().binding(self.fixture.session))
        self.assertTrue(all(not (self.root / path).exists() for path in outputs))
        self.assertFalse(any(path not in original_files and "/exact-operations/checkpoints/" in path
                             for path in self.fixture.files()))
        self.assertEqual(original.prepared.scope.document()["registry_preimage_sha256"], registry_before)
        registry_before = self.fixture.register_unrelated_app()
        self.assertEqual(self.retained(pointer)._raw, original._raw)
        self.input.unlink()
        if family == "record":
            # Its approved operation records metadata only, not fresh bytes.
            self.sources[0].unlink()
        before_normal = self.fixture.files()
        key_calls = len(self.fixture.key.create_if_missing_calls)
        with self.original_only(no_effects=True):
            blocked = review("resume", ok=False)
        self.assertEqual(blocked["reason_code"], "work_session_intake_original_approval_missing")
        self.assertFalse(blocked["original_completion_verified"])
        self.assertEqual(self.fixture.files(), before_normal)
        self.assertEqual(self.fixture.native.calls, 2)
        self.assertEqual(self.fixture.routing._read(current=False)._raw, pending_raw)

        observed, written, actor_publications = [], [], []
        actor_save = actor.WorkSessionActorStore.save
        writer_type = batch._SessionSourceIntakeWriter if family == "batch" else record_domain._SessionSourceIntakeRecordWriter
        original_write = writer_type.write_field

        def redisplay(retained_context, **options):
            observed.append(approval.exact_human_approval_context_sha256(retained_context))
            self.assertEqual(retained_context, context)
            self.assertEqual(self.fixture.routing._read(current=False)._raw, pending_raw)
            self.assertEqual(self.fixture.claims(), original_claims)
            return request_native(retained_context, **options)

        def real_write(writer, **values):
            writer.held.verify_held()
            self.assertEqual(writer.claim.status, "started")
            self.assertEqual(self.fixture.routing._read(current=False)._raw, pending_raw)
            result = original_write(writer, **values)
            written.append(values["target_ref"])
            return result

        def final_actor_only(store, **values):
            self.assertIsNone(values["pending_operation"])
            self.assertEqual(values["last_completed_operation"].document(), pointer)
            self.assertEqual(values["expected_sha256"], selected.sha256)
            actor_publications.append(True)
            return actor_save(store, **values)

        with self.original_only(), patch.object(broker, "_request_exact_human_approval_core", side_effect=redisplay), \
             patch.object(writer_type, "write_field", new=real_write), \
             patch.object(actor.WorkSessionActorStore, "save", new=final_actor_only):
            completed = review("review_original")
        self.assertTrue(completed["native_approval_redisplayed"] and completed["original_context_preserved"])
        self.assertTrue(completed["original_completion_verified"] and completed["completion_authentication_verified"])
        self.assertTrue(completed["current_claim_ownership_verified"] and completed["independent_verification"])
        self.assertFalse(completed["artifact_capture_performed"])
        self.assertEqual(observed, [pointer["context_sha256"]])
        self.assertEqual(self.fixture.native.calls, 3)
        self.assertEqual(actor_publications, [True])
        self.assertEqual(len(written), len(outputs))
        self.assertEqual(set(written), set(outputs))
        self.assertEqual(self.retained(pointer)._raw, original._raw)
        self.assertEqual(completed["context_sha256"], pointer["context_sha256"])
        self.assertEqual(self.fixture.store.read().sha256, registry_before)
        new_claims = set(self.fixture.claims()) - set(original_claims)
        self.assertEqual(len(new_claims), 1)
        claim = json.loads(self.fixture.claims()[next(iter(new_claims))])
        self.assertEqual(claim["status"], "succeeded")
        self.assertEqual(claim["context_sha256"], pointer["context_sha256"])
        for name, raw in original_claims.items():
            self.assertEqual(self.fixture.claims()[name], raw)
        self.assertTrue(self.fixture.key.create_if_missing_calls[key_calls:])
        self.assertTrue(all(value is False for value in self.fixture.key.create_if_missing_calls[key_calls:]))

        # Authenticate the original MAC/checkpoints and whole outputs through
        # a separate historical reader, not the public success booleans.
        read = (completion._read_completed_session_source_intake_held if family == "batch"
                else completion._read_completed_session_source_intake_record_held)
        with exact.ExactOperationWriterLock(self.root) as held:
            verified = read(self.root, held=held, manifest_sha256=pointer["manifest_sha256"],
                            context_sha256=pointer["context_sha256"], key_provider=self.fixture.key)
        facts = verified.proof_document()
        self.assertEqual(facts["execution_sha256"], completed["execution_sha256"])
        self.assertEqual(facts["common_final_receipt_sha256"], completed["common_final_receipt_sha256"])
        common = "receipts/ops/exact-operations/" + completed["execution_sha256"][7:] + ".json"
        self.assertEqual(verified.common_final_receipt_raw, (self.root / common).read_bytes())
        self.assertEqual(set(verified.approved_output_map()), set(outputs) | {common})
        for path, raw in outputs.items():
            self.assertEqual((self.root / path).read_bytes(), raw)
            self.assertEqual(verified.approved_output_map()[path]["sha256"], "sha256:" + hashlib.sha256(raw).hexdigest())
        if family == "batch":
            self.assertTrue(completed["requires_new_capture_approval"])
            for source in self.sources:
                self.assertEqual(source.read_bytes(), self.fixture.source_bytes[source])
                source.unlink()  # Batch source checks finished before deletion.
        else:
            self.assertFalse(completed["prepared_capture_request_created"] or completed["source_bytes_retained"])
        before_replay = self.fixture.files()
        with self.original_only(no_effects=True):
            replay = fresh("review_original")
        self.assertTrue(replay["original_operation_already_completed"] and replay["original_completion_verified"])
        self.assertFalse(replay["native_approval_redisplayed"] or replay["writes_performed"] or replay["actor_completion_published"])
        self.assertEqual(replay["execution_sha256"], completed["execution_sha256"])
        self.assertEqual(self.fixture.files(), before_replay)
        self.assertEqual(self.fixture.native.calls, 3)
        self.assertFalse(self.fixture.key.active)
        for private in ("SYNTHETIC_PRIVATE", str(self.root), str(self.input), claim["approval_id"]):
            self.assertNotIn(private, json.dumps(self.outputs))

    def test_batch_cli_preclaim_cut_mcp_original_review_then_cli_completed_review(self):
        self.journey("batch", self.cli, self.mcp)

    def test_record_mcp_preclaim_cut_cli_source_free_original_review_then_mcp_completed_review(self):
        self.journey("record", self.mcp, self.cli)


if __name__ == "__main__":
    unittest.main()
