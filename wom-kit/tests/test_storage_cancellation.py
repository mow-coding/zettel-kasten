"""Synthetic provider boundaries with real journals and non-reentrant keys."""
from contextlib import ExitStack, contextmanager
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import signal
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import test_object_storage_cleanup_open as cleanup_fixtures
import test_object_storage_preservation as preserve_fixtures
import test_v0428_object_storage_restore as restore_fixtures
import test_v0433_object_storage_upload as upload_fixtures
import test_v0429_object_storage_offload as offload_fixtures
import test_activity_cleanup as activity_fixtures

from wom_kit import archive_services as services
from wom_kit import exact_human_approval as claims
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import exact_human_approval_windows as windows
from wom_kit import object_storage_cleanup as cleanup
from wom_kit import object_storage_preservation as preservation
from wom_kit import object_storage_restore as restore
from wom_kit import object_storage_upload_exact as upload
from wom_kit import object_storage_offload as offload
from wom_kit import activity_cleanup as activity
from wom_kit import operation_cancellation as cancellation
from wom_kit import operation_control as control
from wom_kit.object_storage_scope import ObjectScope


class StrictKeys:
    def __init__(self):
        self.active = False
        self.calls = 0
        self.nested_calls = 0

    def use_key(self, root, consumer, *, create_if_missing=False):
        if self.active:
            self.nested_calls += 1
            raise AssertionError("nested key consumer is forbidden")
        self.active = True
        self.calls += 1
        try:
            return consumer(memoryview(bytes(range(32))))
        finally:
            self.active = False


class StorageCancellationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wom-synthetic-cancel-")
        self.addCleanup(self.tmp.cleanup)
        self.keys = StrictKeys()
        self.native = restore_fixtures._Native()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(broker, "_production_key_provider", return_value=self.keys))
        self.stack.enter_context(mock.patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))

    @contextmanager
    def observation(self, root, kind):
        # These are domain/journal integration tests. Public CLI support is
        # registered separately only after all routes for a kind are wired.
        command = "synthetic-" + kind.replace("_", "-")
        with (mock.patch.dict(control.COMMAND_KINDS, {command: kind}),
              mock.patch.dict(control.KIND_COMMANDS, {kind: command}),
              mock.patch.dict(control.COMMAND_STAGES, {command: frozenset({"starting", "unknown"})}),
              mock.patch.object(cancellation, "SUPPORTED", cancellation.SUPPORTED | {kind})):
            journal = control.OperationRunJournal.prepare(root, command=command, run_id="a" * 32,
                output_relative=".wom-scratch/diagnostics/synthetic-storage.json")
            try:
                value = cancellation._binding(vars(journal))
                # A separate approved caller can publish this request during
                # I/O. Preparing its bytes here avoids pretending that the
                # remote provider itself has authority to mint cancellation.
                raw = cancellation._canonical({"document": value, "mac": cancellation._mac(root, value, self.keys)})
                def request():
                    journal.journal_path.with_suffix(".cancel.json").write_bytes(raw)
                with cancellation.observing(journal, provider=self.keys):
                    yield journal, request
            finally:
                journal.close()

    def cleanup_fixture(self, count=2):
        f = cleanup_fixtures.CleanupOpenTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        # The shared fixture patches the key provider; keep this test strict.
        self.stack.enter_context(mock.patch.object(broker, "_production_key_provider", return_value=self.keys))
        f.key_provider = self.keys
        if count == 2:
            key = "synthetic/another-intermediate.bin"
            raw = b"second synthetic disposable object"
            oid = "sha256:" + hashlib.sha256(raw).hexdigest()
            eid = cleanup.entry_id(cleanup_fixtures.STORE, key)
            f.transport.objects[key] = raw
            f.request["entries"].append({"remote_key": key, "object_id": oid, "size": len(raw)})
            f.classification["entries"].append({"entry_id": eid, "object_id": oid,
                "decision": "temporary_unnecessary", "reason": "Synthetic temporary object."})
            f.management["entry_ids"].append(eid)
            f.sync()
        return f

    def test_cleanup_waits_for_delete_head_and_journal_before_ack(self):
        f = self.cleanup_fixture()
        with self.observation(f.root, "object_storage_cleanup") as (journal, request):
            old = f.transport.delete_exact
            def delete(**kwargs):
                request()
                self.assertFalse(journal.journal_path.with_suffix(".cancel-ack.json").exists())
                return old(**kwargs)
            with mock.patch.object(f.transport, "delete_exact", side_effect=delete):
                result = f.run_cleanup()
            self.assertEqual(result["state"], "cancelled_at_checkpoint", result)
            self.assertEqual([row["state"] for row in result["items"]], ["deleted", "not_attempted"])
            self.assertEqual([call[0] for call in f.transport.calls], ["FULL_GET", "DELETE", "HEAD"])
            first_key = f.transport.calls[0][1]
            evidence = cleanup._load_signed(f.root, cleanup._state_path(cleanup_fixtures.STORE, first_key), self.keys)
            self.assertEqual(evidence["state"], "deleted")
            self.assertTrue(cancellation.state(f.root, journal.journal_path, vars(journal), self.keys)["cancel_acknowledged"])
        resumed = f.run_cleanup()
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(sum(call[0] == "DELETE" for call in f.transport.calls), 2)
        self.assertEqual(self.keys.nested_calls, 0)

    def assert_cli_stopped(self, root, result):
        self.assertEqual(result["state"], "cancelled_at_checkpoint", result)
        self.assertTrue(result["operation"]["cancel_supported"], result)
        observed = control.inspect_operation(root, result["operation_ref"])
        self.assertTrue(observed["terminal"], observed)
        self.assertTrue(observed["result"]["binding_verified"], observed)
        self.assertTrue(observed["result"]["artifact_available"], observed)
        self.assertFalse(observed["result"]["ok"], observed)
        self.assertTrue(observed["control"]["cancel_acknowledged"], observed)
        self.assertTrue(observed["control"]["cancellation_completed"], observed)
        self.assertFalse(observed["result"]["domain_truth_verified"], observed)
        self.assertEqual(self.keys.nested_calls, 0)

    def test_public_cleanup_cli_ctrl_c_persists_terminal_result_before_resume(self):
        f = self.cleanup_fixture()
        old = f.transport.delete_exact
        def delete(**kwargs):
            signal.raise_signal(signal.SIGINT)
            return old(**kwargs)
        with mock.patch.object(f.transport, "delete_exact", side_effect=delete):
            code, result = f.cli("object-storage-cleanup", "--request", "profiles/local/request.json",
                                 "--approve", "--reviewed-by", cleanup_fixtures.REVIEWER)
        self.assertEqual(code, 1, result)
        self.assertEqual([row["state"] for row in result["items"]], ["deleted", "not_attempted"])
        self.assert_cli_stopped(f.root, result)
        code, resumed = f.cli("object-storage-cleanup", "--request", "profiles/local/request.json", "--resume",
                              "--approve", "--reviewed-by", cleanup_fixtures.REVIEWER)
        self.assertEqual(code, 0, resumed)
        self.assertNotEqual(resumed["operation_ref"], result["operation_ref"])
        self.assertEqual(sum(call[0] == "DELETE" for call in f.transport.calls), 2)
        self.assertEqual(self.keys.nested_calls, 0)

    def test_public_inventory_cli_ctrl_c_keeps_partial_scan_unpublished(self):
        f = self.cleanup_fixture()
        path = "profiles/local/synthetic-inventory.json"
        f.write(path, {"schema": "wom-kit/remote-disposal-inventory-request/v1", "store_ref": cleanup_fixtures.STORE,
                       "remote_binding": cleanup_fixtures.BINDING, "keys": list(f.transport.objects)})
        old = f.transport.head_object
        def get(**kwargs):
            signal.raise_signal(signal.SIGINT)
            return old(**kwargs)
        with mock.patch.object(f.transport, "head_object", side_effect=get):
            code, result = f.cli("object-storage-cleanup", "--inventory", "--request", path,
                                 "--approve", "--reviewed-by", cleanup_fixtures.REVIEWER)
        self.assertEqual(code, 1, result)
        self.assertFalse(result["inventory_created"])
        self.assertEqual(result["inspected_entry_count"], 1)
        self.assert_cli_stopped(f.root, result)

    def test_public_restore_cli_ctrl_c_resumes_original_claim_and_new_journal(self):
        f = restore_fixtures.RestoreCliTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.stack.enter_context(mock.patch.object(broker, "_production_key_provider", return_value=self.keys))
        code, preview = f.run_cli(*f.base_args(), "--dry-run")
        self.assertEqual(code, 0, preview)
        send, calls = restore_fixtures._sink_sender(f.raw)
        def interrupted_sender(**request):
            response = send(**request)
            signal.raise_signal(signal.SIGINT)
            return response
        with mock.patch.object(services, "_default_urllib_sender", return_value=interrupted_sender):
            code, result = f.run_cli(*f.base_args(), "--approve", "--reviewed-by", restore_fixtures.REVIEWER,
                                    "--expected-manifest-sha256", preview["plan_sha256"])
        self.assertEqual(code, 1, result)
        self.assertEqual(result["durable_terminal_receipt_count"], 1)
        self.assert_cli_stopped(f.root, result)
        with mock.patch.object(services, "_default_urllib_sender", return_value=send):
            code, resumed = f.run_cli(*f.base_args(), "--approve", "--reviewed-by", restore_fixtures.REVIEWER,
                "--expected-manifest-sha256", preview["plan_sha256"],
                "--resume-approval-id", result["recovery"]["approval_id"],
                "--resume-execution-sha256", result["execution_sha256"])
        self.assertEqual(code, 0, resumed)
        self.assertNotEqual(resumed["operation_ref"], result["operation_ref"])
        self.assertEqual(sum(call["method"] == "GET" for call in calls), 1)
        self.assertEqual(f.native.calls, 1)
        self.assertEqual(self.keys.nested_calls, 0)

    def test_cleanup_unknown_remote_outcome_is_recorded_before_stop(self):
        f = self.cleanup_fixture()
        with self.observation(f.root, "object_storage_cleanup") as (journal, request):
            def unknown(**kwargs):
                f.transport.calls.append(("DELETE", kwargs["key"]))
                request()
                return {"state": "unknown"}
            with mock.patch.object(f.transport, "delete_exact", side_effect=unknown):
                result = f.run_cleanup()
            self.assertEqual(result["unknown_outcome_count"], 1, result)
            first_key = f.transport.calls[0][1]
            evidence = cleanup._load_signed(f.root, cleanup._state_path(cleanup_fixtures.STORE, first_key), self.keys)
            self.assertEqual(evidence["state"], "outcome_unknown")
            self.assertEqual(sum(call[0] == "DELETE" for call in f.transport.calls), 1)
            self.assertTrue(journal.journal_path.with_suffix(".cancel-ack.json").exists())
        self.assertEqual(self.keys.nested_calls, 0)

    def test_cleanup_request_before_effect_does_not_call_remote(self):
        f = self.cleanup_fixture()
        with self.observation(f.root, "object_storage_cleanup") as (_journal, request):
            request()
            result = f.run_cleanup()
            self.assertEqual(result["recorded_item_count"], 0)
            self.assertTrue(all(row["state"] == "not_attempted" for row in result["items"]))
            self.assertEqual(f.transport.calls, [])
        self.assertEqual(self.keys.nested_calls, 0)

    def test_tampered_request_is_not_acknowledged_and_no_remote_effect_starts(self):
        f = self.cleanup_fixture()
        with self.observation(f.root, "object_storage_cleanup") as (journal, request):
            request()
            path = journal.journal_path.with_suffix(".cancel.json")
            value = json.loads(path.read_bytes())
            value["document"]["control_digest"] = "sha256:" + "0" * 64
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(broker.ExactHumanApprovalWorkflowError):
                f.run_cleanup()
            self.assertFalse(journal.journal_path.with_suffix(".cancel-ack.json").exists())
            self.assertEqual(f.transport.calls, [])
        self.assertEqual(self.keys.nested_calls, 0)

    def test_inventory_cancel_after_full_get_never_publishes_partial_inventory(self):
        f = self.cleanup_fixture()
        path = "profiles/local/synthetic-inventory.json"
        f.write(path, {"schema": "wom-kit/remote-disposal-inventory-request/v1", "store_ref": cleanup_fixtures.STORE,
                       "remote_binding": cleanup_fixtures.BINDING, "keys": list(f.transport.objects)})
        plan = cleanup.plan_inventory(f.root, request_path=path)
        with self.observation(f.root, "object_storage_cleanup") as (journal, request):
            old = f.transport.head_object
            def get(**kwargs):
                result = old(**kwargs)
                request()
                self.assertFalse(journal.journal_path.with_suffix(".cancel-ack.json").exists())
                return result
            with mock.patch.object(f.transport, "head_object", side_effect=get):
                result = f.approved(cleanup.execute_inventory_approved, plan, request_path=path)
        self.assertEqual(result["state"], "cancelled_at_checkpoint", result)
        self.assertEqual(result["inspected_entry_count"], 1)
        self.assertFalse(result["inventory_created"])
        self.assertFalse((f.root / cleanup.ROOT / "inventories").exists())
        self.assertEqual(self.keys.nested_calls, 0)

    def preservation_fixture(self):
        fixture = preserve_fixtures.ObjectStoragePreservationTests()
        root = fixture._root(Path(self.tmp.name))
        fixture._write_rows(root, [fixture._local_row(root, raw) for raw in (b"first synthetic preserved", b"second synthetic preserved")])
        plan = preservation._plan_core(root, provider_kind="cloudflare-r2", store_ref="storage:account:test")
        return root, plan, preserve_fixtures._MemoryTransport()

    def test_preservation_waits_for_put_and_terminal_receipt_then_resumes_without_duplicate_put(self):
        root, plan, transport = self.preservation_fixture()
        with self.observation(root, "object_storage_bytes_preservation") as (journal, request):
            old = transport.put_object
            def put(**kwargs):
                result = old(**kwargs)
                request()
                self.assertFalse(journal.journal_path.with_suffix(".cancel-ack.json").exists())
                return result
            with mock.patch.object(transport, "put_object", side_effect=put):
                result = preservation.execute_object_storage_bytes_preservation(plan,
                    reviewer_claim=restore_fixtures.REVIEWER, transport_factory=lambda: transport)
            self.assertEqual(result["state"], "cancelled_at_checkpoint", result)
            self.assertEqual(result["durable_terminal_receipt_count"], 1)
            self.assertEqual(result["checkpointed_item_count"], 0)
            self.assertTrue(journal.journal_path.with_suffix(".cancel-ack.json").exists())
        loaded = preservation.load_object_storage_bytes_preservation_plan(root, manifest_sha256=plan.manifest.manifest_sha256)
        resumed = preservation.resume_object_storage_bytes_preservation(loaded, reviewer_claim=restore_fixtures.REVIEWER,
            approval_id=result["recovery"]["approval_id"], execution_sha256=result["execution_sha256"],
            transport_factory=lambda: transport, key_provider=self.keys)
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(transport.put_calls, 2)
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.keys.nested_calls, 0)

    def restore_fixture(self, *, mode=restore.MODE_RESTORE):
        root = restore_fixtures._build_root(Path(self.tmp.name))
        bodies = (b"first synthetic restore", b"second synthetic restore")
        restore_fixtures._write_rows(root, [restore_fixtures._row(raw, locations=[restore_fixtures._remote(raw)]) for raw in bodies])
        plan = restore.plan_object_storage_restore(root, provider_kind=restore_fixtures.PROVIDER,
            store_ref=restore_fixtures.STORE, mode=mode, scope=ObjectScope("all_sessions"))
        by_hash = {"sha256:" + hashlib.sha256(raw).hexdigest(): raw for raw in bodies}
        transport = restore_fixtures._MemoryTransport({spec.remote_key: by_hash[spec.object_id] for spec in plan.specs})
        return root, plan, transport

    def test_restore_finishes_get_promotion_receipt_then_resumes_remaining_and_projection(self):
        root, plan, transport = self.restore_fixture()
        with self.observation(root, "object_storage_restore") as (journal, request):
            old = transport.get_object
            def get(**kwargs):
                result = old(**kwargs)
                request()
                self.assertFalse(journal.journal_path.with_suffix(".cancel-ack.json").exists())
                return result
            with mock.patch.object(transport, "get_object", side_effect=get):
                result = restore.execute_object_storage_restore(plan, reviewer_claim=restore_fixtures.REVIEWER,
                    transport_factory=lambda: transport)
            self.assertEqual(result["state"], "cancelled_at_checkpoint", result)
            self.assertEqual(result["durable_terminal_receipt_count"], 1)
            self.assertEqual(transport.get_calls, 1)
            completed = next(spec for spec in plan.specs if (root / spec.receipt_relative).exists())
            self.assertTrue((root / completed.local_relative).is_file())
            self.assertTrue(journal.journal_path.with_suffix(".cancel-ack.json").exists())
        loaded = restore.load_object_storage_restore_plan(root, manifest_sha256=plan.manifest.manifest_sha256)
        resumed = restore.resume_object_storage_restore(loaded, reviewer_claim=restore_fixtures.REVIEWER,
            approval_id=result["recovery"]["approval_id"], execution_sha256=result["execution_sha256"],
            transport_factory=lambda: transport, key_provider=self.keys)
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(transport.get_calls, 2)
        self.assertEqual(resumed["manifest_location_updates"], 2)
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.keys.nested_calls, 0)

    def test_restore_verify_only_cancellation_preserves_read_only_remote_contract(self):
        root, plan, transport = self.restore_fixture(mode=restore.MODE_VERIFY_ONLY)
        with self.observation(root, "object_storage_restore") as (_journal, request):
            old = transport.get_object
            def get(**kwargs):
                result = old(**kwargs)
                request()
                return result
            with mock.patch.object(transport, "get_object", side_effect=get):
                result = restore.execute_object_storage_restore(plan, reviewer_claim=restore_fixtures.REVIEWER,
                    transport_factory=lambda: transport)
        self.assertEqual(result["state"], "cancelled_at_checkpoint", result)
        self.assertEqual(result["mode"], restore.MODE_VERIFY_ONLY)
        self.assertTrue(all(not (root / spec.local_relative).exists() for spec in plan.specs))
        self.assertEqual(transport.put_calls, 0)
        self.assertEqual(transport.delete_calls, 0)
        self.assertEqual(self.keys.nested_calls, 0)

    def test_started_claim_mac_rejects_cross_archive_and_closed_claim(self):
        f = self.cleanup_fixture(count=1)
        other = restore_fixtures._build_root(Path(self.tmp.name))
        plan = cleanup.plan_cleanup(f.root, request_path="profiles/local/request.json")
        binding = cleanup_fixtures.plan_digest_approval_binding(windows.ExactHumanApprovalOperation.object_storage_remote_cleanup,
                                                               plan["plan_sha256"])
        context = binding.context(archive_id=services.read_archive_id(f.root), reviewer_claim=restore_fixtures.REVIEWER)
        kept = []
        def capabilities(claim):
            return (claim.operation_cancel_mac, claim.remote_disposal_mac,
                    claim.activity_cleanup_mac, claim.remote_preservation_proof_mac)
        def writer(claim):
            kept.append(claim)
            for method in capabilities(claim):
                with self.assertRaises(claims.ExactHumanApprovalError):
                    method(other, b"{}")
                self.assertEqual(len(method(f.root, b"{}")), 64)
                for invalid in (b"", bytearray(b"{}"), "{}"):
                    with self.assertRaises(claims.ExactHumanApprovalError):
                        method(f.root, invalid)
            for method, limit in ((claim.activity_cleanup_mac, 32 * 1024 * 1024),
                                  (claim.remote_preservation_proof_mac, 16384)):
                with self.assertRaises(claims.ExactHumanApprovalError):
                    method(f.root, b"x" * (limit + 1))
            return {"ok": True}
        broker._execute_exact_human_approved_write(f.root, context, writer)
        for method in capabilities(kept[0]):
            with self.assertRaises(claims.ExactHumanApprovalError):
                method(f.root, b"{}")
        self.assertEqual(self.keys.nested_calls, 0)

    def test_proof_store_captured_claim_works_in_worker_but_not_after_close(self):
        from wom_kit.remote_preservation_proof import ProofStore, SCHEMA
        f = self.cleanup_fixture(count=1)
        plan = cleanup.plan_cleanup(f.root, request_path="profiles/local/request.json")
        binding = cleanup_fixtures.plan_digest_approval_binding(windows.ExactHumanApprovalOperation.object_storage_remote_cleanup,
                                                               plan["plan_sha256"])
        context = binding.context(archive_id=services.read_archive_id(f.root), reviewer_claim=restore_fixtures.REVIEWER)
        proof = {"schema": SCHEMA, "binding": {"remote": cleanup_fixtures.BINDING, "key": "synthetic/key"},
                 "sha256": "a" * 64, "size": 1, "etag": '"synthetic"', "execution_sha256": "sha256:" + "b" * 64}
        held = []
        def writer(claim):
            store = ProofStore(f.root)
            held.append(store)
            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(store.save, proof).result()
            self.assertEqual(store.load(proof["binding"]), proof)
            return {"ok": True}
        broker._execute_exact_human_approved_write(f.root, context, writer)
        with self.assertRaises(claims.ExactHumanApprovalError):
            held[0]._mac(proof)
        self.assertEqual(self.keys.nested_calls, 0)

    @unittest.skipUnless(os.name == "nt", "offload and activity cleanup use the Windows-only handle-bound delete")
    def test_activity_official_child_upload_cancel_resumes_without_duplicate_remote_put(self):
        f, _ = self.activity_fixture("preserve")
        common = dict(archive_id=services.read_archive_id(f.root), profile_id="profile:synthetic:activity",
            profile_slug="synthetic-activity", provider_kind="cloudflare-r2", storage_account_ref="synthetic-store",
            bucket_name="synthetic-activity-bucket", region="auto", endpoint_ref="provider:endpoint:synthetic",
            objet_prefix="archives/synthetic/objets/", visibility="private")
        binding = services.build_object_storage_provider_binding(**common)
        (f.root / "provider-bindings.yml").write_text(services.dump_yaml({"version": "provider-bindings/v0.1",
            "archive_id": common["archive_id"], "bindings": [binding]}), encoding="utf-8")
        relative = services.object_storage_provider_setup_receipt_path(common["bucket_name"])
        receipt = services.build_object_storage_provider_setup_receipt(**common, receipt_path=relative,
            reviewed_by="person:synthetic", timestamp="2026-09-23T00:00:00Z", dry_run=False, manual_steps=[])
        target = f.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(receipt), encoding="utf-8")
        services.index_archive(f.root)
        f.document["storage"] = {"provider_kind": "cloudflare-r2", "store_ref": "synthetic-store"}
        f.request.write_text(json.dumps(f.document), encoding="utf-8")
        candidate = activity.plan(f.root, f.request, key_provider=self.keys)
        transport = preserve_fixtures._MemoryTransport()
        transport.preservation_binding = lambda: cleanup_fixtures.BINDING
        old_head = transport.head_object
        def strong_proof(**kwargs):
            return {**old_head(**kwargs), "whole_get_etag": '"synthetic-activity-proof"'}
        transport.head_object = strong_proof
        f.backend = activity.OfficialPreservationBackend(candidate, reviewer="person:synthetic", transport_factory=lambda: transport)
        with self.observation(f.root, "activity_cleanup") as (_journal, request):
            old = transport.put_object
            def put(**kwargs):
                result = old(**kwargs)
                request()
                return result
            with mock.patch.object(transport, "put_object", side_effect=put):
                result = self.run_activity(f, candidate)
        self.assertEqual(result["state"], "cancelled_at_checkpoint", result)
        self.assertEqual(transport.put_calls, 1)
        self.assertTrue(result["child_recovery"]["same_claim_resume_supported"])
        self.assertFalse(result["child_operation_terminal_verified"])
        self.assertTrue(all(Path(item["path"]).exists() for item in candidate["material"]["items"]))
        self.assertEqual(self.keys.nested_calls, 0)
        resumed_candidate = activity.plan(f.root, f.request, resume=True, key_provider=self.keys)
        f.backend = activity.OfficialPreservationBackend(resumed_candidate, reviewer="person:synthetic", transport_factory=lambda: transport)
        resumed = self.run_activity(f, resumed_candidate, resume=True)
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(transport.put_calls, 2)
        self.assertEqual(self.keys.nested_calls, 0)

    def test_upload_stops_after_durable_ledger_then_resumes_batch_without_duplicate_put(self):
        archive = upload_fixtures._Archive()
        self.addCleanup(archive.close)
        archive.write([archive.local(raw) for raw in (b"synthetic upload one", b"synthetic upload two")])
        plan = archive.plan()
        transport = preserve_fixtures._MemoryTransport()
        with self.observation(archive.root, "object_storage_upload") as (_journal, request):
            old = transport.put_object
            def put(**kwargs):
                result = old(**kwargs)
                request()
                return result
            with mock.patch.object(transport, "put_object", side_effect=put):
                result = upload.execute_object_storage_upload(plan, reviewer_claim=upload_fixtures.REVIEWER,
                    transport_factory=lambda: transport)
        self.assertEqual(result["state"], "cancelled_at_checkpoint", result)
        self.assertEqual(result["durable_terminal_ledger_count"], 1)
        self.assertEqual(result["durable_terminal_receipt_count"], 0)
        self.assertEqual(result["manifest_location_updates"], 0)
        loaded = upload.load_object_storage_upload_plan(archive.root, manifest_sha256=plan.manifest.manifest_sha256)
        resumed = upload.resume_object_storage_upload(loaded, reviewer_claim=upload_fixtures.REVIEWER,
            approval_id=result["recovery"]["approval_id"], execution_sha256=result["execution_sha256"],
            transport_factory=lambda: transport, key_provider=self.keys)
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(transport.put_calls, 2)
        self.assertEqual(resumed["receipts_created_count"], 2)
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.keys.nested_calls, 0)

    def test_public_upload_and_preserve_cli_stop_and_resume_with_terminal_artifacts(self):
        for preserve in (False, True):
            with self.subTest(preserve_local_only=preserve):
                f = upload_fixtures.UploadCliTests()
                f.setUp()
                self.addCleanup(f.doCleanups)
                with mock.patch.object(broker, "_production_key_provider", return_value=self.keys):
                    args = f.base_args()
                    if preserve:
                        args[0] = "object-storage-adopt-existing"
                        args.remove("--all-sessions")
                        args.append("--preserve-local-only")
                    code, preview = f.run_cli(*args, "--dry-run")
                    self.assertEqual(code, 0, preview)
                    old = f.transport.put_object
                    def put(**kwargs):
                        result = old(**kwargs)
                        signal.raise_signal(signal.SIGINT)
                        return result
                    with mock.patch.object(f.transport, "put_object", side_effect=put):
                        code, result = f.run_cli(*args, "--approve", "--reviewed-by", upload_fixtures.REVIEWER,
                            "--expected-manifest-sha256", preview["plan_sha256"])
                    self.assertEqual(code, 1, result)
                    self.assert_cli_stopped(f.archive.root, result)
                    code, resumed = f.run_cli(*args, "--approve", "--reviewed-by", upload_fixtures.REVIEWER,
                        "--expected-manifest-sha256", preview["plan_sha256"],
                        "--resume-approval-id", result["recovery"]["approval_id"],
                        "--resume-execution-sha256", result["execution_sha256"])
                    self.assertEqual(code, 0, resumed)
                    self.assertNotEqual(resumed["operation_ref"], result["operation_ref"])
                    self.assertEqual(f.transport.put_calls, 1)
                    self.assertEqual(f.native.calls, 1)
                    self.assertEqual(self.keys.nested_calls, 0)

    @unittest.skipUnless(os.name == "nt", "offload and activity cleanup use the Windows-only handle-bound delete")
    def test_public_offload_cli_stop_and_resume_with_terminal_artifacts(self):
        f = offload_fixtures.OffloadCliTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.stack.enter_context(mock.patch.object(broker, "_production_key_provider", return_value=self.keys))
        code, preview = f.run_cli(*f.base_args(), "--dry-run")
        self.assertEqual(code, 0, preview)
        send, calls = restore_fixtures._sink_sender(f.raw)
        old = offload._create_receipt
        def receipt(*args, **kwargs):
            signal.raise_signal(signal.SIGINT)
            return old(*args, **kwargs)
        with mock.patch.object(services, "_default_urllib_sender", return_value=send):
            with mock.patch.object(offload, "_create_receipt", side_effect=receipt):
                code, result = f.run_cli(*f.base_args(), "--approve", "--reviewed-by", offload_fixtures.REVIEWER,
                                        "--expected-manifest-sha256", preview["plan_sha256"])
            self.assertEqual(code, 1, result)
            self.assertEqual(result["recorded_local_unlink_count"], 1)
            self.assert_cli_stopped(f.root, result)
            code, resumed = f.run_cli(*f.base_args(), "--approve", "--reviewed-by", offload_fixtures.REVIEWER,
                "--expected-manifest-sha256", preview["plan_sha256"],
                "--resume-approval-id", result["recovery"]["approval_id"],
                "--resume-execution-sha256", result["execution_sha256"])
        self.assertEqual(code, 0, resumed)
        self.assertNotEqual(resumed["operation_ref"], result["operation_ref"])
        self.assertEqual(sum(call["method"] == "GET" for call in calls), 1)
        self.assertEqual(f.native.calls, 1)
        self.assertEqual(self.keys.nested_calls, 0)

    @unittest.skipUnless(os.name == "nt", "offload and activity cleanup use the Windows-only handle-bound delete")
    def test_offload_records_native_unlink_receipt_before_stop_and_resume(self):
        root = restore_fixtures._build_root(Path(self.tmp.name))
        (root / ".gitignore").write_text("profiles/local/\n", encoding="utf-8")
        bodies = (b"synthetic offload one", b"synthetic offload two")
        restore_fixtures._write_rows(root, [offload_fixtures._aged_row(raw) for raw in bodies])
        for raw in bodies:
            restore_fixtures._write_local(root, raw)
        plan = offload.plan_object_storage_offload(root, provider_kind=restore_fixtures.PROVIDER,
            store_ref=restore_fixtures.STORE, min_age_days=0, min_size_bytes=0, scope=ObjectScope("all_sessions"))
        transport = offload_fixtures._ProofTransport(offload_fixtures._objects_for(plan, {str(i): raw for i, raw in enumerate(bodies)}))
        transport.preservation_binding = lambda: cleanup_fixtures.BINDING
        old = transport.head_object
        def strong_proof(**kwargs):
            return {**old(**kwargs), "whole_get_etag": '"synthetic-offload-proof"'}
        transport.head_object = strong_proof
        with self.observation(root, "object_storage_offload") as (journal, request):
            original = offload._create_receipt
            def receipt(*args, **kwargs):
                # Cancellation arrives after native deletion and before its
                # receipt. The writer must finish recording before checkpoint.
                request()
                self.assertFalse(journal.journal_path.with_suffix(".cancel-ack.json").exists())
                return original(*args, **kwargs)
            with mock.patch.object(offload, "_create_receipt", side_effect=receipt):
                result = offload.execute_object_storage_offload(plan, reviewer_claim=offload_fixtures.REVIEWER,
                    transport_factory=lambda: transport)
        self.assertEqual(result["state"], "cancelled_at_checkpoint", result)
        self.assertEqual(result["durable_terminal_receipt_count"], 1)
        self.assertEqual(sum((root / spec.local_relative).exists() for spec in plan.specs), 1)
        self.assertEqual(len(list((root / "profiles/local/remote-byte-proofs").rglob("*.json"))), 1)
        loaded = offload.load_object_storage_offload_plan(root, manifest_sha256=plan.manifest.manifest_sha256)
        resumed = offload.resume_object_storage_offload(loaded, reviewer_claim=offload_fixtures.REVIEWER,
            approval_id=result["recovery"]["approval_id"], execution_sha256=result["execution_sha256"],
            transport_factory=lambda: transport, key_provider=self.keys)
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(transport.head_calls, 2)
        self.assertEqual(transport.delete_calls, 0)
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.keys.nested_calls, 0)

    def activity_fixture(self, disposition):
        f = activity_fixtures.ActivityCleanupTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        second = f.external / "second-synthetic.txt"
        second.write_bytes(b"second synthetic source")
        f.document["items"].append({"path": str(second), "role": "source", "reason": "Synthetic source", "disposition": disposition})
        for item in f.document["items"]:
            item["disposition"] = disposition
            if disposition == "discard":
                item["role"] = "temporary"
                item["discard_intent"] = True
        f.request.write_text(json.dumps(f.document), encoding="utf-8")
        candidate = activity.plan(f.root, f.request, key_provider=self.keys)
        return f, candidate

    def run_activity(self, f, candidate, *, resume=False):
        binding = activity.approval_binding(candidate)
        context = binding.context(archive_id=candidate["material"]["archive_id"], reviewer_claim="person:synthetic")
        writer = lambda claim: activity.execute(candidate, reviewer="person:synthetic", claim=claim, backend=f.backend)
        if resume:
            approval = candidate["journal"].read("approval")
            return broker._resume_exact_human_approved_write_core(f.root, context, approval["approval_id"],
                lambda claim: candidate["journal"].read("intent") == candidate["material"], writer)
        return broker._execute_exact_human_approved_write(f.root, context, writer)

    @unittest.skipUnless(os.name == "nt", "offload and activity cleanup use the Windows-only handle-bound delete")
    def test_activity_stops_after_bound_delete_journal_and_resumes_remaining(self):
        f, candidate = self.activity_fixture("discard")
        from wom_kit import legacy_cleanup_bound_delete as native_delete
        original = native_delete._delete_exact_approved_file
        with self.observation(f.root, "activity_cleanup") as (journal, request):
            def remove(*args, **kwargs):
                request()
                self.assertFalse(journal.journal_path.with_suffix(".cancel-ack.json").exists())
                return original(*args, **kwargs)
            with mock.patch.object(native_delete, "_delete_exact_approved_file", side_effect=remove):
                result = self.run_activity(f, candidate)
        self.assertEqual(result["state"], "cancelled_at_checkpoint", result)
        self.assertEqual([row["state"] for row in result["items"]], ["deleted", "not_attempted"])
        self.assertIsNotNone(candidate["journal"].read("item-0-deleted"))
        self.assertIsNone(candidate["journal"].read("completed"))
        self.assertEqual(result["measurements"]["unprocessed_item_count"], 1)
        self.assertTrue(f.external.is_dir())
        resumed = self.run_activity(f, activity.plan(f.root, f.request, resume=True, key_provider=self.keys), resume=True)
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.keys.nested_calls, 0)

    @unittest.skipUnless(os.name == "nt", "offload and activity cleanup use the Windows-only handle-bound delete")
    def test_public_activity_cli_cancel_records_terminal_attempt_and_resumes_remaining(self):
        from contextlib import redirect_stdout, redirect_stderr
        import io
        from wom_kit import archive_cli
        from wom_kit import legacy_cleanup_bound_delete as native_delete
        f, _candidate = self.activity_fixture("discard")
        args = ["activity-cleanup", str(f.root), "--request", str(f.request),
                "--reviewed-by", "person:synthetic", "--format", "json"]
        def invoke(*extra):
            output = io.StringIO()
            with redirect_stdout(output), redirect_stderr(io.StringIO()):
                code = archive_cli.main([*args, *extra])
            return code, json.loads(output.getvalue())
        original = native_delete._delete_exact_approved_file
        def remove(*args, **kwargs):
            signal.raise_signal(signal.SIGINT)
            return original(*args, **kwargs)
        with mock.patch.object(native_delete, "_delete_exact_approved_file", side_effect=remove):
            code, result = invoke("--approve")
        self.assertEqual(code, 1, result)
        self.assert_cli_stopped(f.root, result)
        self.assertEqual([item["state"] for item in result["items"]], ["deleted", "not_attempted"])
        code, resumed = invoke("--resume")
        self.assertEqual(code, 0, resumed)
        self.assertNotEqual(result["operation_ref"], resumed["operation_ref"])
        self.assertFalse(f.external.exists())
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.keys.nested_calls, 0)

    @unittest.skipUnless(os.name == "nt", "offload and activity cleanup use the Windows-only handle-bound delete")
    def test_activity_child_cancel_does_not_continue_to_next_item_or_delete_original(self):
        f, candidate = self.activity_fixture("preserve")
        with self.observation(f.root, "activity_cleanup") as (journal, request):
            def interrupted_child(*args):
                request()
                cancellation.checkpoint()
            f.backend.preserve.side_effect = interrupted_child
            result = self.run_activity(f, candidate)
            self.assertTrue(journal.journal_path.with_suffix(".cancel-ack.json").exists())
            self.assertFalse(control.inspect_operation(f.root, journal.operation_ref)["terminal"])
        self.assertEqual(result["state"], "cancelled_at_checkpoint", result)
        self.assertEqual([row["state"] for row in result["items"]], ["interrupted", "not_attempted"])
        self.assertFalse(result["child_operation_terminal_verified"])
        self.assertEqual(f.backend.preserve.call_count, 1)
        self.assertTrue(all(Path(item["path"]).exists() for item in candidate["material"]["items"]))
        self.assertIsNone(candidate["journal"].read("completed"))
        self.assertEqual(self.keys.nested_calls, 0)

    @unittest.skipUnless(os.name == "nt", "offload and activity cleanup use the Windows-only handle-bound delete")
    def test_activity_failed_delete_receipt_is_unknown_not_retained_at_cancel(self):
        f, candidate = self.activity_fixture("discard")
        journal = candidate["journal"]
        old = journal.write
        with self.observation(f.root, "activity_cleanup") as (_operation, request):
            def fail_after_delete(name, document):
                if name == "item-0-deleted":
                    request()
                    raise OSError("synthetic receipt write interruption")
                return old(name, document)
            with mock.patch.object(journal, "write", side_effect=fail_after_delete):
                result = self.run_activity(f, candidate)
        self.assertEqual(result["state"], "cancelled_at_checkpoint", result)
        self.assertEqual([row["state"] for row in result["items"]], ["outcome_unknown", "not_attempted"])
        self.assertEqual(result["measurements"]["unknown_local_outcome_count"], 1)
        self.assertIsNone(journal.read("item-0-deleted"))
        self.assertIsNotNone(journal.read("item-0-delete-intent"))
        self.assertFalse(Path(candidate["material"]["items"][0]["path"]).exists())
        self.assertTrue(Path(candidate["material"]["items"][1]["path"]).exists())
        self.assertEqual(self.keys.nested_calls, 0)

    @unittest.skipUnless(os.name == "nt", "offload and activity cleanup use the Windows-only handle-bound delete")
    def test_activity_restore_stops_after_child_before_external_publication_then_resumes(self):
        f, candidate = self.activity_fixture("preserve")
        item = candidate["material"]["items"][0]
        candidate["journal"].write("item-0-preserved", {"object_id": item["object_id"], "size": item["state"]["size"]})
        destination = f.external / "synthetic-restored.txt"
        planned = activity.restore_plan(candidate, number=0, destination=str(destination))
        binding = activity.restore_binding(planned)
        context = binding.context(archive_id=services.read_archive_id(f.root), reviewer_claim="person:synthetic")
        with self.observation(f.root, "activity_cleanup") as (_journal, request):
            def child(_item):
                request()
                return Path(item["path"])
            f.backend.restore_object.side_effect = child
            result = broker._execute_exact_human_approved_write(f.root, context,
                lambda claim: activity.restore_item(planned, reviewer="person:synthetic", claim=claim, backend=f.backend))
        self.assertEqual(result["state"], "cancelled_at_checkpoint", result)
        self.assertFalse(result["publication_recorded"])
        self.assertFalse(destination.exists())
        loaded = activity.restore_plan(candidate, number=0, destination=str(destination), resume=True)
        f.backend.restore_object.side_effect = None
        f.backend.restore_object.return_value = Path(item["path"])
        resumed = broker._resume_exact_human_approved_write_core(f.root, context,
            loaded["restore_approval"]["approval_id"], lambda claim: loaded["restore_approval"]["intent"] == loaded["restore"],
            lambda claim: activity.restore_item(loaded, reviewer="person:synthetic", claim=claim, backend=f.backend))
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(destination.read_bytes(), Path(item["path"]).read_bytes())
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.keys.nested_calls, 0)

    @unittest.skipUnless(os.name == "nt", "offload and activity cleanup use the Windows-only handle-bound delete")
    def test_activity_existing_local_bytes_still_finish_interrupted_child_restore(self):
        from wom_kit import exact_approval_claims as claim_listing
        f = activity_fixtures.ActivityCleanupTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        root = restore_fixtures._build_root(Path(self.tmp.name))
        (root / ".gitignore").write_text("profiles/local/\n", encoding="utf-8")
        raw = f.source.read_bytes()
        restore_fixtures._write_rows(root, [restore_fixtures._row(raw, locations=[restore_fixtures._remote(raw)])])
        f.document["storage"] = {"provider_kind": restore_fixtures.PROVIDER, "store_ref": restore_fixtures.STORE}
        f.request.write_text(json.dumps(f.document), encoding="utf-8")
        candidate = activity.plan(root, f.request, key_provider=self.keys)
        item = candidate["material"]["items"][0]
        candidate["journal"].write("item-0-preserved", {"object_id": item["object_id"], "size": item["state"]["size"]})
        target = f.base / "restored-synthetic.txt"
        planned = activity.restore_plan(candidate, number=0, destination=str(target))
        context = activity.restore_binding(planned).context(archive_id=services.read_archive_id(root), reviewer_claim=restore_fixtures.REVIEWER)
        transport = restore_fixtures._MemoryTransport({restore_fixtures._remote(raw)["remote_key"]: raw})
        backend = activity.OfficialPreservationBackend(planned, reviewer=restore_fixtures.REVIEWER, transport_factory=lambda: transport)
        with self.observation(root, "activity_cleanup") as (_journal, request):
            old = transport.get_object
            def get(**kwargs):
                result = old(**kwargs)
                request()
                return result
            with mock.patch.object(transport, "get_object", side_effect=get):
                first = broker._execute_exact_human_approved_write(root, context,
                    lambda claim: activity.restore_item(planned, reviewer=restore_fixtures.REVIEWER, claim=claim, backend=backend))
        self.assertEqual(first["state"], "cancelled_at_checkpoint", first)
        self.assertFalse(target.exists())
        child_control = candidate["journal"].read("item-0-restore-control")
        def child_states():
            return [row["status"] for row in claim_listing.list_exact_human_approval_claims(root, status="all")["claims"]
                    if row["context_sha256"] == child_control["context_sha256"]]
        self.assertEqual(child_states(), ["started"])
        loaded = activity.restore_plan(candidate, number=0, destination=str(target), resume=True)
        backend = activity.OfficialPreservationBackend(loaded, reviewer=restore_fixtures.REVIEWER, transport_factory=lambda: transport)
        resumed = broker._resume_exact_human_approved_write_core(root, context, loaded["restore_approval"]["approval_id"],
            lambda claim: loaded["restore_approval"]["intent"] == loaded["restore"],
            lambda claim: activity.restore_item(loaded, reviewer=restore_fixtures.REVIEWER, claim=claim, backend=backend))
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(target.read_bytes(), raw)
        self.assertEqual(transport.get_calls, 1)
        self.assertEqual(child_states(), ["succeeded"])
        locations = restore_fixtures._rows_after(root)[item["object_id"]]["locations"]
        self.assertTrue(any(row.get("provider") == "local" and row.get("availability") == "available" for row in locations), locations)
        self.assertEqual(self.keys.nested_calls, 0)


if __name__ == "__main__":
    unittest.main()
