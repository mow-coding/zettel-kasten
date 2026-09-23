"""Synthetic session selection, delegated lists and interrupted storage work."""
import io
import sys
from pathlib import Path

# Support both direct unittest discovery and CI package-qualified loading.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import json
import os
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

from wom_kit import archive_cli, archive_services, exact_approval_claims
from wom_kit import object_storage_scope as scope
from wom_kit import object_storage_upload_exact as upload
from wom_kit import object_storage_restore as restore
from wom_kit import object_storage_offload as offload
import test_v0433_object_storage_upload as up
import test_v0428_object_storage_restore as rs
import test_v0429_object_storage_offload as ofs
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import exact_human_approval_windows as windows
from wom_kit.exact_human_approval import CLAIMS_RELATIVE_ROOT
from wom_kit.exact_operation_manifest import ExactOperationApprovalAuthority, exact_operation_execution_sha256

A = "work_session_" + "a" * 32
B = "work_session_" + "b" * 32


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.archive = up._Archive()
        self.addCleanup(self.archive.close)
        self.root = self.archive.root
        self.a, self.b = b"session A synthetic payload", b"session B synthetic payload"
        self.archive.write([self.archive.local(self.a), self.archive.local(self.b)])

    def test_absent_session_never_selects_archive(self):
        with patch.dict(os.environ, {}, clear=True):
            for planner in (upload.plan_object_storage_upload, restore.plan_object_storage_restore, offload.plan_object_storage_offload):
                with self.assertRaisesRegex(scope.ObjectStorageScopeError, "session_scope_required"):
                    planner(self.root, store_ref=rs.STORE)
            out = io.StringIO()
            with redirect_stdout(out), redirect_stderr(io.StringIO()):
                code = archive_cli.main(["object-storage-upload", str(self.root), "--store-ref", rs.STORE, "--dry-run", "--format", "json"])
            self.assertEqual(code, 1)
            self.assertIn("object_storage_session_scope_required", json.loads(out.getvalue())["reason_codes"])

    def test_exact_list_upload_never_puts_other_session(self):
        path = self.root / "selected-objects.txt"
        path.write_text(up._oid(self.a) + "\n", encoding="utf-8")
        selected = scope.resolve_scope(self.root, object_list=path)
        plan = upload.plan_object_storage_upload(self.root, store_ref=rs.STORE, scope=selected)
        preview = plan.public_document()
        self.assertEqual(preview["scope_object_count"], 1)
        self.assertEqual(preview["excluded_out_of_scope_count"], 1)
        transport = up._MemoryTransport()
        result = up._run(plan, transport)
        self.assertTrue(result["ok"])
        self.assertEqual(set(transport.objects), {up._key(self.a)})
        self.assertEqual(rs._dest(self.root, self.b).read_bytes(), self.b)

    def test_list_snapshot_survives_restart_and_does_not_expand(self):
        selected = scope.ObjectScope("object_list", (up._oid(self.a),))
        plan = upload.plan_object_storage_upload(self.root, store_ref=rs.STORE, scope=selected)
        upload._persist_control(plan)
        loaded = upload.load_object_storage_upload_plan(self.root, manifest_sha256=plan.manifest.manifest_sha256)
        self.assertEqual(loaded.scope, selected)
        with patch.dict(os.environ, {"WOM_WORK_SESSION_REF": B}):
            self.assertEqual([x.object_id for x in loaded.specs], [up._oid(self.a)])
        changed = scope.ObjectScope("object_list", tuple(sorted((up._oid(self.a), up._oid(self.b)))))
        wider = upload.plan_object_storage_upload(self.root, store_ref=rs.STORE, scope=changed)
        self.assertNotEqual(plan.manifest.manifest_sha256, wider.manifest.manifest_sha256)

    @unittest.skipUnless(os.name == "nt", "handle-bound offload deletion is Windows-only")
    def test_restore_and_offload_touch_only_explicit_delegate(self):
        self.archive.write([ofs._aged_row(self.a), ofs._aged_row(self.b)])
        selected = scope.ObjectScope("object_list", (up._oid(self.b),))
        plan = offload.plan_object_storage_offload(self.root, store_ref=rs.STORE, scope=selected,
                                                  min_age_days=0, min_size_bytes=0)
        transport = ofs._ProofTransport({up._key(self.a): self.a, up._key(self.b): self.b})
        self.assertTrue(ofs._run_offload(plan, transport)["ok"])
        self.assertTrue(rs._dest(self.root, self.a).exists())
        self.assertFalse(rs._dest(self.root, self.b).exists())
        back = restore.plan_object_storage_restore(self.root, store_ref=rs.STORE, scope=selected)
        self.assertEqual([x.object_id for x in back.specs], [up._oid(self.b)])
        self.assertTrue(rs._run(back, rs._MemoryTransport({up._key(self.b): self.b}))["ok"])
        self.assertEqual(rs._dest(self.root, self.b).read_bytes(), self.b)
        self.assertEqual(rs._dest(self.root, self.a).read_bytes(), self.a)

    def test_conflicting_scope_and_bad_lists_fail_closed(self):
        with self.assertRaises(scope.ObjectStorageScopeError):
            scope.resolve_scope(self.root, all_sessions=True, this_session=True)
        for text in ("", "not-an-object\n", up._oid(self.a) + "\n\n"):
            path = self.root / "bad-list.txt"
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(scope.ObjectStorageScopeError):
                scope.resolve_scope(self.root, object_list=path)
        with self.assertRaisesRegex(scope.ObjectStorageScopeError, "object_missing"):
            upload.plan_object_storage_upload(self.root, store_ref=rs.STORE,
                                             scope=scope.ObjectScope("object_list", (up._oid(b"missing"),)))

    def _capture_receipt(self, raw, owner, number):
        oid = up._oid(raw)
        items = [{"object_id": oid, "approved_object_id": oid,
                  "logical_key": f"objects/sha256/{oid[7:9]}/{oid[7:]}",
                  "planned_action": "capture", "action": "captured", "size_bytes": len(raw),
                  "mime": "application/octet-stream", "blockers": [], "warnings": [],
                  "stored_sha256_verified": True, "manifest_record_appended": True}]
        filename = f"20260921T000000Z-{number:012x}.json"
        receipt = {"schema": "wom-kit/objet-capture-receipt/v0.2", "receipt_id": f"receipt:objet-capture:{filename[:-5]}",
                   "dry_run": False, "ok": True, "aborted": False, "archive_id": archive_services.read_archive_id(self.root),
                   "captured_at": "2026-09-21T00:00:00Z", "reviewed_by": "person:synthetic",
                   "selection_manifest_id": "selection:synthetic", "selection_manifest_sha256": "sha256:" + "d" * 64,
                   "items": items, "summary": archive_services.objet_capture_summary(items, approve=True),
                   "blockers": [], "warnings": [],
                   "exact_human_approval": {"approval_id": str(number), "context_sha256": "sha256:" + "c" * 64}}
        directory = self.root / archive_services.OBJET_CAPTURE_RECEIPTS_DIR
        directory.mkdir(parents=True, exist_ok=True)
        (directory / filename).write_text(json.dumps(receipt), encoding="utf-8")
        return {"approval_id": str(number), "context_sha256": "sha256:" + "c" * 64, "operation": "objet_capture",
                "status": "succeeded", "session_presenter": {"work_session_ref": owner}}

    def test_default_session_and_explicit_delegation_use_receipt_linkage(self):
        claims = [self._capture_receipt(self.a, A, 1), self._capture_receipt(self.b, B, 2)]
        # Only the authenticated-store boundary is substituted; receipt parsing is real.
        with patch.object(exact_approval_claims, "list_exact_human_approval_claims", return_value={"claims": claims, "blocker_codes": []}), patch.dict(os.environ, {"WOM_WORK_SESSION_REF": A}):
            current = scope.resolve_scope(self.root)
            delegated = scope.resolve_scope(self.root, captured_by_session=B)
            self.assertEqual(current.object_ids, (up._oid(self.a),))
            self.assertEqual(delegated.object_ids, (up._oid(self.b),))
            self.assertEqual([x.object_id for x in upload.plan_object_storage_upload(self.root, store_ref=rs.STORE).specs], [up._oid(self.a)])
            self.assertEqual(scope.resolve_scope(self.root, all_sessions=True).kind, "all_sessions")

    def test_chain_intake_claim_selects_captured_object(self):
        claims = [self._capture_receipt(self.a, A, 11)]
        claims[0]["operation"] = "source_intake_chain"
        with patch.object(exact_approval_claims, "list_exact_human_approval_claims", return_value={"claims": claims, "blocker_codes": []}):
            self.assertEqual(scope.resolve_scope(self.root, captured_by_session=A).object_ids, (up._oid(self.a),))

    def test_session_used_existing_object_is_included_without_search_attribution(self):
        claims = [self._capture_receipt(self.a, B, 11)]
        claims.append({"approval_id": "usage", "context_sha256": "sha256:" + "d" * 64,
            "operation": "zettel_objet_link", "status": "succeeded", "session_presenter": {"work_session_ref": A}})
        directory = self.root / "receipts/objects/zettel-links"
        directory.mkdir(parents=True)
        receipt = {"archive_id": archive_services.read_archive_id(self.root), "action": "add_zettel_objet_link",
            "object_id": up._oid(self.a), "exact_human_approval": {"exact_human_approval":
                {"approval_id": "usage", "context_sha256": "sha256:" + "d" * 64}}}
        (directory / "synthetic.json").write_text(json.dumps(receipt), encoding="utf-8")
        with patch.object(exact_approval_claims, "list_exact_human_approval_claims", return_value={"claims": claims, "blocker_codes": []}):
            # A copied valid approval reference is not authentication of this
            # independently fabricated object-use receipt.
            with self.assertRaisesRegex(scope.ObjectStorageScopeError, "session_scope_unavailable"):
                scope.resolve_scope(self.root, captured_by_session=A)
            receipt["exact_human_approval"]["exact_human_approval"]["context_sha256"] = "sha256:" + "f" * 64
            (directory / "synthetic.json").write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaisesRegex(scope.ObjectStorageScopeError, "session_scope_unavailable"):
                scope.resolve_scope(self.root, captured_by_session=A)

    def test_incomplete_session_evidence_never_falls_back_to_all(self):
        with patch.object(exact_approval_claims, "list_exact_human_approval_claims", return_value={"claims": [], "blocker_codes": ["incomplete"]}):
            with self.assertRaisesRegex(scope.ObjectStorageScopeError, "evidence_incomplete"):
                scope.resolve_scope(self.root, captured_by_session=A)

    def test_partial_upload_abandon_preserves_effects_and_new_plan_is_narrow(self):
        plan = upload.plan_object_storage_upload(self.root, store_ref=rs.STORE, scope=scope.ObjectScope("all_sessions"))
        blocked_key = plan.specs[1].remote_key
        class InterruptedTransport(up._MemoryTransport):
            def head_object(self, *, key, presence_only=False):
                if key == blocked_key:
                    return {"present": False, "size": None, "checksum_sha256": None,
                            "presence_state": "unavailable", "verification_state": "unavailable"}
                return super().head_object(key=key, presence_only=presence_only)
        transport = InterruptedTransport()
        key_provider = rs._KeyProvider()
        native = rs._Native()
        with patch.object(broker, "_production_key_provider", return_value=key_provider), patch.object(windows, "_CtypesTaskDialogNative", return_value=native):
            with self.assertRaises(Exception):
                upload.execute_object_storage_upload(plan, reviewer_claim=up.REVIEWER, transport_factory=lambda: transport)
            self.assertEqual(len(transport.objects), 1)
            self.assertNotIn(blocked_key, transport.objects)
            claims = list((self.root / CLAIMS_RELATIVE_ROOT).glob("*.json"))
            self.assertEqual(len(claims), 1)
            claim = json.loads(claims[0].read_text(encoding="utf-8"))
            self.assertEqual(claim["status"], "started")
            reference = {"schema_version": "wom-kit/exact-human-approval-reference/v0.1", "one_use": True,
                         **{k: claim[k] for k in ("approval_id", "context_sha256", "approval_authority_sha256")}}
            execution = exact_operation_execution_sha256(plan.manifest, approval_authority=ExactOperationApprovalAuthority.from_reference(reference))
            loaded = upload.load_object_storage_upload_plan(self.root, manifest_sha256=plan.manifest.manifest_sha256)
            before = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in (self.root / "receipts").rglob("*") if p.is_file()}
            preview = upload.abandon_object_storage_upload(loaded, reviewer_claim=up.REVIEWER, approval_id=claim["approval_id"], execution_sha256=execution, dry_run=True, key_provider=key_provider)
            self.assertTrue(preview["ok"])
            self.assertEqual(json.loads(claims[0].read_text(encoding="utf-8"))["status"], "started")
            puts = transport.put_calls
            result = upload.abandon_object_storage_upload(loaded, reviewer_claim=up.REVIEWER, approval_id=claim["approval_id"], execution_sha256=execution, key_provider=key_provider)
            self.assertTrue(result["ok"])
            terminal = json.loads(claims[0].read_text(encoding="utf-8"))
            self.assertEqual(terminal["status"], "failed")
            self.assertEqual(terminal["failure_code"], "object_storage_upload_abandoned_with_effects_preserved")
            self.assertEqual(transport.put_calls, puts)
            for relative, raw in before.items():
                if relative != claims[0].relative_to(self.root).as_posix():
                    self.assertEqual((self.root / relative).read_bytes(), raw)
            narrow = upload.plan_object_storage_upload(self.root, store_ref=rs.STORE, scope=scope.ObjectScope("object_list", (plan.specs[0].object_id,)))
            done = upload.execute_object_storage_upload(narrow, reviewer_claim=up.REVIEWER, transport_factory=lambda: transport)
            self.assertTrue(done["ok"])
            self.assertEqual(transport.put_calls, puts)
            self.assertEqual(len(narrow.specs), 1)
            with self.assertRaises(Exception):
                upload.resume_object_storage_upload(loaded, reviewer_claim=up.REVIEWER, approval_id=claim["approval_id"], execution_sha256=execution, transport_factory=lambda: transport, key_provider=key_provider)

    def test_same_objects_different_delegation_have_distinct_plan_digests(self):
        exact = scope.ObjectScope("object_list", tuple(sorted((up._oid(self.a), up._oid(self.b)))))
        all_objects = upload.plan_object_storage_upload(self.root, store_ref=rs.STORE, scope=scope.ObjectScope("all_sessions"))
        delegated = upload.plan_object_storage_upload(self.root, store_ref=rs.STORE, scope=exact)
        self.assertEqual(len(all_objects.specs), len(delegated.specs))
        self.assertNotEqual(all_objects.manifest.manifest_sha256, delegated.manifest.manifest_sha256)
        upload._persist_control(all_objects)
        upload._persist_control(delegated)

    def test_scope_is_bound_to_control_manifest_not_only_control_checksum(self):
        plan = upload.plan_object_storage_upload(self.root, store_ref=rs.STORE,
                                               scope=scope.ObjectScope("object_list", (up._oid(self.a),)))
        relative = upload._persist_control(plan)
        document = json.loads((self.root / relative).read_bytes())
        document["scope"] = scope.ObjectScope("object_list", (up._oid(self.b),)).document()
        document.pop("control_sha256")
        document["control_sha256"] = upload._sha(document)
        (self.root / relative).write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaises(upload.ObjectStorageUploadError):
            upload.load_object_storage_upload_plan(self.root, manifest_sha256=plan.manifest.manifest_sha256)


if __name__ == "__main__":
    unittest.main()
