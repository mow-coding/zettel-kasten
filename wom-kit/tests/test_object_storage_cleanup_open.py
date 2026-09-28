"""Synthetic A01/A02 regressions. No bucket, credential or native UI access."""
from __future__ import annotations

from contextlib import ExitStack, redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_v0428_object_storage_restore as restore_fixture
import test_v0421_lifecycle_batches_exact_approval as approval_fixture
import test_object_storage_preservation as preservation_fixture

from wom_kit import archive_services as services
from wom_kit import archive_cli
from wom_kit import object_storage_cleanup as cleanup
from wom_kit import object_storage_open as opening
from wom_kit import object_storage_restore as restoration
from wom_kit import object_storage_preservation as preservation
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker
from wom_kit.operation_approval_binding import plan_digest_approval_binding

STORE = restore_fixture.STORE
BINDING = {"service": "s3", "endpoint_host": "synthetic.invalid", "bucket": "synthetic-bucket", "region": "auto"}
BODY = b"SYNTHETIC disposable intermediate bytes"
OID = "sha256:" + hashlib.sha256(BODY).hexdigest()
KEY = "legacy/old folder/\ud569\uc131 %2F draft.bin"
REVIEWER = "person:synthetic-disposal-reviewer"


class MemoryTransport:
    conditional_delete_supported = False

    def __init__(self, objects=None):
        self.objects = dict(objects if objects is not None else {KEY: BODY})
        self.calls = []
        self.delete_unknown = False
        self.reject_delete = False

    def preservation_binding(self):
        return dict(BINDING)

    def head_object(self, *, key, presence_only=False):
        self.calls.append(("HEAD" if presence_only else "FULL_GET", key))
        if key not in self.objects:
            return {"present": False, "presence_state": "absent"}
        raw = self.objects[key]
        return {"present": True, "presence_state": "present", "verification_state": "complete", "size": len(raw),
                "checksum_sha256": None if presence_only else hashlib.sha256(raw).hexdigest(), "whole_get_etag": '"synthetic-etag"'}

    def delete_exact(self, *, key, etag=None):
        self.calls.append(("DELETE", key, etag))
        if self.reject_delete:
            return {"state": "rejected"}
        self.objects.pop(key, None)
        return {"state": "unknown" if self.delete_unknown else "accepted"}

    def list_page(self, *, prefix, continuation_token=None):
        self.calls.append(("LIST", prefix, continuation_token))
        keys = sorted(key for key in self.objects if key.startswith(prefix))
        return {"keys": keys, "continuation_token": None}


class CleanupOpenTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="wom-synthetic-remote-disposal-")
        self.addCleanup(temp.cleanup)
        self.root = restore_fixture._build_root(Path(temp.name))
        (self.root / ".gitignore").write_text("profiles/local/\n", encoding="utf-8")
        (self.root / "objects/manifests/files.jsonl").write_text("", encoding="utf-8")
        self.key_provider = approval_fixture._KeyProvider()
        self.native = approval_fixture._PagedNative()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
        stack.enter_context(patch.object(broker, "_production_key_provider", return_value=self.key_provider))
        self.transport = MemoryTransport()
        self.eid = cleanup.entry_id(STORE, KEY)
        self.request = {"schema": cleanup.REQUEST_SCHEMA, "provider_kind": "cloudflare-r2", "store_ref": STORE,
                        "remote_binding": BINDING, "classification_path": "profiles/local/classification.json",
                        "management_path": "profiles/local/management.json",
                        "entries": [{"remote_key": KEY, "object_id": OID, "size": len(BODY)}]}
        self.classification = {"schema": cleanup.CLASSIFICATION_SCHEMA, "entries": [{"entry_id": self.eid,
                               "object_id": OID, "decision": "temporary_unnecessary", "reason": "Synthetic intermediate, never used."}]}
        self.management = {"schema": cleanup.MANAGEMENT_SCHEMA, "archive_identity_sha256": cleanup._archive_identity(self.root),
                           "store_ref": STORE, "remote_binding": BINDING, "authority": "exclusive_wom",
                           "external_writers": "excluded", "immutable_keys": True, "entry_ids": [self.eid]}
        self.sync()

    def write(self, relative, document):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document), encoding="utf-8")

    def sync(self):
        self.write("profiles/local/request.json", self.request)
        self.write("profiles/local/classification.json", self.classification)
        self.write("profiles/local/management.json", self.management)

    def approved(self, function, plan, operation="object_storage_remote_cleanup", **kwargs):
        binding = plan_digest_approval_binding(getattr(windows.ExactHumanApprovalOperation, operation), plan["plan_sha256"])
        context = binding.context(archive_id=services.read_archive_id(self.root), reviewer_claim=REVIEWER)
        return broker._execute_exact_human_approved_write(self.root, context, lambda claim: function(
            self.root, expected_plan_sha256=plan["plan_sha256"], reviewed_by=REVIEWER,
            exact_human_approval_claim=claim, expected_exact_approval_plan_sha256=binding.plan_sha256,
            expected_exact_approval_target_binding_sha256=binding.target_binding_sha256,
            transport_factory=lambda: self.transport, key_provider=self.key_provider, **kwargs))

    def run_cleanup(self, **kwargs):
        plan = cleanup.plan_cleanup(self.root, request_path="profiles/local/request.json")
        return self.approved(cleanup.execute_cleanup_approved, plan, request_path="profiles/local/request.json", **kwargs)

    def test_legacy_key_without_upload_receipt_deletes_after_exact_approval_and_full_get(self):
        result = self.run_cleanup()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["items"][0]["state"], "deleted")
        self.assertNotIn(KEY, self.transport.objects)
        self.assertEqual([row[0] for row in self.transport.calls], ["FULL_GET", "DELETE", "HEAD"])
        self.assertEqual(self.native.calls, 1)
        self.assertFalse(result["recovery_guaranteed"])
        self.assertNotIn(KEY, json.dumps(result))
        with self.assertRaisesRegex(cleanup.ObjectStorageCleanupError, "without_usable_copy"):
            cleanup.assert_referenceable(self.root, [OID])
        with self.assertRaisesRegex(cleanup.ObjectStorageCleanupError, "disposed_or_pending"):
            cleanup.assert_remote_available(self.root, store_ref=STORE, remote_key=KEY)

    def test_no_claim_never_calls_provider_or_writes_tombstone(self):
        plan = cleanup.plan_cleanup(self.root, request_path="profiles/local/request.json")
        with self.assertRaisesRegex(cleanup.ObjectStorageCleanupError, "approval_required"):
            cleanup.execute_cleanup_approved(self.root, request_path="profiles/local/request.json", expected_plan_sha256=plan["plan_sha256"],
                reviewed_by=REVIEWER, exact_human_approval_claim=None, expected_exact_approval_plan_sha256="sha256:" + "0"*64,
                expected_exact_approval_target_binding_sha256="sha256:" + "0"*64, transport_factory=lambda: self.transport)
        self.assertEqual(self.transport.calls, [])
        self.assertFalse((self.root / cleanup.ROOT).exists())

    def test_external_writer_possible_remains_actionable_and_preserved(self):
        self.management["external_writers"] = "possible"
        self.sync()
        plan = cleanup.plan_cleanup(self.root, request_path="profiles/local/request.json")
        self.assertEqual(plan["eligible_count"], 0)
        self.assertIn("external_writer_possible", plan["items"][0]["reason_codes"])
        self.assertEqual(self.transport.calls, [])

    def test_current_reference_and_retained_revision_preserve_objects(self):
        for relative in ("zettels/active.md", "inbox/draft.md", "receipts/revisions/canonical/revision.json"):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("---\nid: zet_synthetic_active\ntitle: Synthetic\nstatus: draft\n---\nobjet:" + OID, encoding="utf-8")
            plan = cleanup.plan_cleanup(self.root, request_path="profiles/local/request.json")
            self.assertEqual(plan["eligible_count"], 0, relative)
            path.unlink()

    def test_adopted_manifest_identity_does_not_permanently_exclude_qualification(self):
        row = {"object_id": OID, "size_bytes": len(BODY), "provenance": {"source": "object_storage_adopt_existing"}, "locations": []}
        (self.root / "objects/manifests/files.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
        self.assertTrue(self.run_cleanup()["ok"])

    def test_changed_remote_bytes_never_delete_and_release_pending_fence(self):
        self.transport.objects[KEY] = b"replacement"
        result = self.run_cleanup()
        self.assertEqual(result["items"][0]["state"], "remote_changed")
        self.assertFalse(any(row[0] == "DELETE" for row in self.transport.calls))
        cleanup.assert_referenceable(self.root, [OID])

    def test_manifest_changed_after_approval_is_refused(self):
        plan = cleanup.plan_cleanup(self.root, request_path="profiles/local/request.json")
        (self.root / "zettels").mkdir()
        (self.root / "zettels/new-use.md").write_text(OID, encoding="utf-8")
        with self.assertRaises(broker.ExactHumanApprovalWorkflowError):
            self.approved(cleanup.execute_cleanup_approved, plan, request_path="profiles/local/request.json")
        self.assertEqual(self.transport.calls, [])

    def test_delete_response_lost_but_absence_confirmed_completes(self):
        self.transport.delete_unknown = True
        result = self.run_cleanup()
        self.assertEqual(result["items"][0]["state"], "deleted")

    def test_crash_after_delete_resumes_by_head_without_repeating_delete(self):
        def crash(stage, _entry):
            if stage == "delete_returned":
                raise RuntimeError("synthetic-interruption")
        with self.assertRaises(broker.ExactHumanApprovalWorkflowError):
            self.run_cleanup(fault_hook=crash)
        self.assertNotIn(KEY, self.transport.objects)
        self.assertTrue(self.run_cleanup()["ok"])
        self.assertEqual(sum(row[0] == "DELETE" for row in self.transport.calls), 1)

    def test_crash_before_delete_reproves_bytes_before_resuming(self):
        def crash(stage, _entry):
            if stage == "delete_intent_recorded":
                raise RuntimeError("synthetic-interruption")
        with self.assertRaises(broker.ExactHumanApprovalWorkflowError):
            self.run_cleanup(fault_hook=crash)
        result = self.run_cleanup()
        self.assertTrue(result["ok"])
        self.assertEqual(sum(row[0] == "FULL_GET" for row in self.transport.calls), 2)
        self.assertEqual(sum(row[0] == "DELETE" for row in self.transport.calls), 1)

    def test_pending_fence_prevents_new_reference_during_provider_call(self):
        def assert_pending(stage, _entry):
            if stage == "pending_published":
                with self.assertRaisesRegex(cleanup.ObjectStorageCleanupError, "disposed_or_pending"):
                    cleanup.assert_referenceable(self.root, [OID])
        self.assertTrue(self.run_cleanup(fault_hook=assert_pending)["ok"])

    def test_authenticated_journal_cannot_be_forged_to_allow_a_new_reference(self):
        self.run_cleanup()
        path = self.root / cleanup._state_path(STORE, KEY)
        value = json.loads(path.read_bytes())
        value["document"]["state"] = "preserved"
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(cleanup.ObjectStorageCleanupError, "journal_invalid"):
            cleanup.assert_referenceable(self.root, [OID])

    def test_inventory_then_qualification_uses_legacy_exact_key_and_body_hash(self):
        inv_request = {"schema": "wom-kit/remote-disposal-inventory-request/v1", "store_ref": STORE,
                       "remote_binding": BINDING, "keys": [KEY]}
        self.write("profiles/local/inventory-request.json", inv_request)
        plan = cleanup.plan_inventory(self.root, request_path="profiles/local/inventory-request.json")
        inventory = self.approved(cleanup.execute_inventory_approved, plan, request_path="profiles/local/inventory-request.json")
        self.request.pop("entries")
        self.request.update(inventory_path=inventory["inventory_path"], entry_ids=[self.eid])
        self.sync()
        self.assertTrue(self.run_cleanup()["ok"])
        self.assertEqual(sum(row[0] == "FULL_GET" for row in self.transport.calls), 2)

    def test_inventory_pagination_and_token_loop_fail_closed(self):
        self.write("profiles/local/inventory-request.json", {"schema": "wom-kit/remote-disposal-inventory-request/v1",
                   "store_ref": STORE, "remote_binding": BINDING, "prefix": "legacy/"})
        plan = cleanup.plan_inventory(self.root, request_path="profiles/local/inventory-request.json")
        self.transport.list_page = lambda **kw: {"keys": [], "continuation_token": "repeated-token"}
        with self.assertRaises(broker.ExactHumanApprovalWorkflowError):
            self.approved(cleanup.execute_inventory_approved, plan, request_path="profiles/local/inventory-request.json")
        self.assertFalse((self.root / cleanup.ROOT / "inventories").exists())

    def open_fixture(self):
        # The established row helper emits the real uploaded-location schema.
        key = services.object_storage_content_addressed_key_hint(OID)
        self.transport.objects[key] = BODY
        row = restore_fixture._row(BODY, locations=[restore_fixture._remote(BODY)])
        (self.root / "objects/manifests/files.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
        return key

    def test_open_delivers_expiring_url_directly_but_never_returns_or_retains_it(self):
        key = self.open_fixture()
        delivered = []
        self.transport._access_key_id = "SYNTHETICACCESS"
        self.transport._secret_access_key = "synthetic-secret-not-a-real-credential"
        now = datetime(2026, 9, 28, tzinfo=timezone.utc)
        plan = opening.plan_open(self.root, object_id=OID, store_ref=STORE, remote_binding=BINDING)
        result = self.approved(opening.execute_open_approved, plan, operation="object_storage_open", object_id=OID,
                               store_ref=STORE, remote_binding=BINDING, deliver=lambda url: delivered.append(url) or True, now=now)
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(delivered), 1)
        self.assertEqual(result["expires_at"], "2026-09-28T00:15:00Z")
        parsed = urlsplit(delivered[0])
        self.assertEqual(unquote(parsed.path), "/synthetic-bucket/" + key)
        self.assertEqual(parse_qs(parsed.query)["X-Amz-Expires"], ["900"])
        self.assertNotIn("X-Amz", json.dumps(result))
        for path in (self.root / "profiles/local").rglob("*.json"):
            self.assertNotIn("X-Amz-Signature", path.read_text(encoding="utf-8"), str(path))

    def test_open_refuses_wrong_bucket_before_get_or_signing(self):
        self.open_fixture()
        self.transport.preservation_binding = lambda: {**BINDING, "bucket": "other-bucket"}
        plan = opening.plan_open(self.root, object_id=OID, store_ref=STORE, remote_binding=BINDING)
        with self.assertRaises(broker.ExactHumanApprovalWorkflowError):
            self.approved(opening.execute_open_approved, plan, operation="object_storage_open", object_id=OID,
                          store_ref=STORE, remote_binding=BINDING)
        self.assertEqual(self.transport.calls, [])

    def test_open_ttl_and_signature_encode_opaque_key_once(self):
        self.transport._access_key_id = "SYNTHETICACCESS"
        self.transport._secret_access_key = "synthetic-secret-not-a-real-credential"
        url = opening.presign_get(self.transport, key=KEY, ttl_seconds=60, now=datetime(2026, 9, 28, tzinfo=timezone.utc))
        self.assertIn("%252F", url)
        self.assertEqual(unquote(urlsplit(url).path), "/synthetic-bucket/" + KEY)
        for invalid in (0, 59, 86401, True, "900"):
            with self.assertRaises(opening.ObjectStorageOpenError):
                opening.presign_get(self.transport, key=KEY, ttl_seconds=invalid)

    def test_r2_adapter_never_claims_conditional_delete_and_preserves_http_outcome(self):
        calls = []
        class Fake:
            def _dispatch(self, **kwargs):
                calls.append(kwargs)
                return {"status": 403, "body": b"SYNTHETIC SECRET PROVIDER RESPONSE"}
        adapter = cleanup.CleanupTransportAdapter(Fake())
        self.assertFalse(adapter.conditional_delete_supported)
        self.assertEqual(adapter.delete_exact(key=KEY), {"state": "rejected"})
        self.assertNotIn("extra_headers", calls[0])

    def test_inventory_xml_decodes_once_and_rejects_entities(self):
        from urllib.parse import quote
        class Fake:
            def _dispatch(self, **kwargs):
                return {"status": 200, "body": ('<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
                         '<IsTruncated>false</IsTruncated><Contents><Key>' + quote(KEY, safe="") + '</Key></Contents></ListBucketResult>').encode()}
        adapter = cleanup.CleanupTransportAdapter(Fake())
        self.assertEqual(adapter.list_page(prefix="legacy/")["keys"], [KEY])
        adapter.transport._dispatch = lambda **kw: {"status": 200, "body": b'<!DOCTYPE x [<!ENTITY x SYSTEM "file:///never">]><x/>'}
        with self.assertRaises(cleanup.ObjectStorageCleanupError):
            adapter.list_page(prefix="legacy/")

    def test_actual_s3_sender_retains_bounded_inventory_xml_above_old_control_limit(self):
        keys = ["legacy/" + str(index) + "-" + "x"*160 for index in range(500)]
        xml = ("<ListBucketResult><IsTruncated>false</IsTruncated>" + "".join(
            "<Contents><Key>" + key + "</Key></Contents>" for key in keys) + "</ListBucketResult>").encode()
        self.assertGreater(len(xml), 65536)
        class Response(io.BytesIO):
            status = 200
            def __init__(self):
                super().__init__(xml)
                self.headers = {"content-length": str(len(xml))}
        class Opener:
            def open(self, request, timeout):
                return Response()
        with patch("urllib.request.build_opener", return_value=Opener()):
            sender = services._default_urllib_sender()
        transport = services._object_storage_resolve_transport("cloudflare-r2", send=sender,
            credential={**{key: value for key, value in BINDING.items() if key != "service"},
                        "access_key_id": "SYNTHETICACCESS", "secret_access_key": "synthetic-unused-secret"})
        self.assertEqual(cleanup.CleanupTransportAdapter(transport).list_page(prefix="legacy/")["keys"], keys)

    def test_retained_snapshot_body_protects_its_only_remaining_reference(self):
        snapshot = ("---\nstatus: canonical\n---\nobjet:" + OID).encode()
        digest = hashlib.sha256(snapshot).hexdigest()
        relative = "objects/sha256/" + digest[:2] + "/" + digest
        path = self.root / relative
        path.parent.mkdir(parents=True)
        path.write_bytes(snapshot)
        row = {"object_id": "sha256:" + digest, "size_bytes": len(snapshot),
               "provenance": {"source": "canonical_zet_before_revision"},
               "locations": [{"provider": "local", "path": relative, "availability": "available"}]}
        (self.root / "objects/manifests/files.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
        plan = cleanup.plan_cleanup(self.root, request_path="profiles/local/request.json")
        self.assertEqual(plan["eligible_count"], 0)
        path.write_bytes(b"tampered snapshot")
        with self.assertRaisesRegex(cleanup.ObjectStorageCleanupError, "reference_scan_incomplete"):
            cleanup.plan_cleanup(self.root, request_path="profiles/local/request.json")

    def test_completed_disposal_filters_only_selected_location(self):
        self.run_cleanup()
        deleted = {"provider": "object_storage", "store_ref": STORE, "remote_key": KEY}
        other = {"provider": "object_storage", "store_ref": STORE, "remote_key": "retained/another-copy"}
        local = {"provider": "local", "path": "objects/synthetic.bin", "availability": "available"}
        self.assertEqual(cleanup.filter_remote_locations(self.root, [deleted, other, local], object_id=OID), [other, local])
        restore_fixture._write_local(self.root, BODY)
        restore_fixture._write_rows(self.root, [restore_fixture._row(BODY, locations=[restore_fixture._local(BODY)])])
        cleanup.assert_referenceable(self.root, [OID])

    def test_deleted_only_copy_cannot_be_referenced_through_stale_manifest(self):
        key = "old/" + OID[7:]
        self.select_cleanup_key(key)
        restore_fixture._write_rows(self.root, [restore_fixture._row(BODY, locations=[restore_fixture._remote(BODY, key=key)])])
        self.assertTrue(self.run_cleanup()["ok"])
        with self.assertRaisesRegex(cleanup.ObjectStorageCleanupError, "without_usable_copy"):
            cleanup.assert_referenceable(self.root, [OID])

    def test_surviving_local_copy_must_match_actual_hash_before_new_reference(self):
        self.run_cleanup()
        path = restore_fixture._write_local(self.root, BODY)
        restore_fixture._write_rows(self.root, [restore_fixture._row(BODY, locations=[restore_fixture._local(BODY)])])
        cleanup.assert_referenceable(self.root, [OID])
        path.write_bytes(b"x" * len(BODY))
        with self.assertRaisesRegex(cleanup.ObjectStorageCleanupError, "without_usable_copy"):
            cleanup.assert_referenceable(self.root, [OID])

    def test_other_verified_remote_copy_allows_reference_but_declared_copy_does_not(self):
        self.run_cleanup()
        location = restore_fixture._remote(BODY, key="retained/" + OID[7:])
        location["execution_receipt_ref"] = "receipts/providers/object-storage-executions/synthetic.object-storage-upload.json"
        restore_fixture._write_rows(self.root, [restore_fixture._row(BODY, locations=[location])])
        cleanup.assert_referenceable(self.root, [OID])
        location["availability"] = "declared_uploaded"
        restore_fixture._write_rows(self.root, [restore_fixture._row(BODY, locations=[location])])
        with self.assertRaisesRegex(cleanup.ObjectStorageCleanupError, "without_usable_copy"):
            cleanup.assert_referenceable(self.root, [OID])

    def test_two_exact_keys_with_same_hash_are_independent(self):
        self.transport.objects["retained/other-copy"] = BODY
        self.assertTrue(self.run_cleanup()["ok"])
        self.assertEqual(self.transport.objects["retained/other-copy"], BODY)
        cleanup.assert_remote_available(self.root, store_ref=STORE, remote_key="retained/other-copy", object_id=OID)

    def test_wrong_archive_management_and_missing_classification_never_qualify(self):
        self.classification["entries"] = []
        self.sync()
        self.assertEqual(cleanup.plan_cleanup(self.root, request_path="profiles/local/request.json")["eligible_count"], 0)
        self.management["archive_identity_sha256"] = "sha256:" + "0"*64
        self.sync()
        with self.assertRaisesRegex(cleanup.ObjectStorageCleanupError, "qualification_invalid"):
            cleanup.plan_cleanup(self.root, request_path="profiles/local/request.json")

    def test_failed_browser_delivery_does_not_leak_exception_or_url(self):
        self.open_fixture()
        self.transport._access_key_id = "SYNTHETICACCESS"
        self.transport._secret_access_key = "synthetic-secret-not-a-real-credential"
        plan = opening.plan_open(self.root, object_id=OID, store_ref=STORE, remote_binding=BINDING)
        def refuse(url):
            raise RuntimeError(url)
        result = self.approved(opening.execute_open_approved, plan, operation="object_storage_open", object_id=OID,
                               store_ref=STORE, remote_binding=BINDING, deliver=refuse)
        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "browser_delivery_failed")
        self.assertNotIn("X-Amz", json.dumps(result))

    def cli(self, command, *arguments):
        out, err = io.StringIO(), io.StringIO()
        with patch.object(archive_cli, "_object_storage_live_transport_factory", return_value=lambda: self.transport), redirect_stdout(out), redirect_stderr(err):
            status = archive_cli.main([command, str(self.root), "--endpoint-host", BINDING["endpoint_host"],
                "--bucket", BINDING["bucket"], "--access-key-id-ref", "env:SYNTHETIC_ACCESS",
                "--secret-access-key-ref", "env:SYNTHETIC_SECRET", "--format", "json", *arguments])
        if err.getvalue():
            self.assertRegex(err.getvalue(), r"^\[object-storage-cleanup\] operation_ref=op:sha256:[0-9a-f]{64}\n$")
        return status, json.loads(out.getvalue())

    def test_public_cli_cleanup_dry_run_then_approve_uses_same_plan(self):
        code, preview = self.cli("object-storage-cleanup", "--request", "profiles/local/request.json", "--dry-run")
        self.assertEqual(code, 0, preview)
        self.assertEqual(self.transport.calls, [])
        code, result = self.cli("object-storage-cleanup", "--request", "profiles/local/request.json", "--approve",
                                "--reviewed-by", REVIEWER, "--expected-plan-sha256", preview["plan_sha256"])
        self.assertEqual(code, 0, result)
        self.assertEqual(result["items"][0]["state"], "deleted")
        self.assertEqual(self.native.calls, 1)

    def test_public_cli_open_uses_browser_and_never_prints_bearer(self):
        self.open_fixture()
        self.transport._access_key_id = "SYNTHETICACCESS"
        self.transport._secret_access_key = "synthetic-secret-not-a-real-credential"
        with patch.object(opening.webbrowser, "open", return_value=True) as browser:
            code, result = self.cli("object-storage-open", "--object-id", OID, "--store-ref", STORE,
                                    "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["state"], "browser_opened")
        self.assertTrue(browser.called)
        self.assertNotIn("X-Amz", json.dumps(result))

    def select_cleanup_key(self, key):
        self.eid = cleanup.entry_id(STORE, key)
        self.request["entries"][0]["remote_key"] = key
        self.classification["entries"][0]["entry_id"] = self.eid
        self.management["entry_ids"] = [self.eid]
        self.transport.objects[key] = BODY
        self.sync()

    def test_restore_uses_retained_other_key_after_exact_location_disposal(self):
        deleted_key, retained_key = "old/" + OID[7:], "retained/" + OID[7:]
        self.select_cleanup_key(deleted_key)
        retained = restore_fixture._remote(BODY, key=retained_key)
        retained["execution_receipt_ref"] = "receipts/providers/object-storage-executions/synthetic.object-storage-upload.json"
        restore_fixture._write_rows(self.root, [restore_fixture._row(BODY, locations=[
            restore_fixture._remote(BODY, key=deleted_key), retained])])
        self.assertTrue(self.run_cleanup()["ok"])
        plan = restoration.plan_object_storage_restore(self.root, provider_kind="cloudflare-r2", store_ref=STORE, only=OID)
        self.assertEqual(len(plan.specs), 1)
        self.assertEqual(plan.specs[0].remote_key, retained_key)
        transport = restore_fixture._MemoryTransport({retained_key: BODY})
        result = restoration.execute_object_storage_restore(plan, reviewer_claim=REVIEWER, transport_factory=lambda: transport)
        self.assertTrue(result["ok"], result)
        self.assertEqual(restore_fixture._dest(self.root, BODY).read_bytes(), BODY)
        self.assertEqual(transport.get_calls, 1)

    def test_restore_stale_plan_cannot_reactivate_a_deleted_remote_location(self):
        key = "old/" + OID[7:]
        self.select_cleanup_key(key)
        restore_fixture._write_rows(self.root, [restore_fixture._row(BODY, locations=[restore_fixture._remote(BODY, key=key)])])
        plan = restoration.plan_object_storage_restore(self.root, provider_kind="cloudflare-r2", store_ref=STORE, only=OID)
        self.assertTrue(self.run_cleanup()["ok"])
        factory_calls = []
        with self.assertRaises(broker.ExactHumanApprovalWorkflowError):
            restoration.execute_object_storage_restore(plan, reviewer_claim=REVIEWER,
                transport_factory=lambda: factory_calls.append(True))
        self.assertEqual(factory_calls, [])
        self.assertFalse(restore_fixture._dest(self.root, BODY).exists())

    def test_preservation_stale_plan_cannot_reupload_disposed_key(self):
        key = preservation.object_storage_bytes_preserved_remote_key(OID)
        self.select_cleanup_key(key)
        restore_fixture._write_local(self.root, BODY)
        restore_fixture._write_rows(self.root, [restore_fixture._row(BODY, locations=[restore_fixture._local(BODY)])])
        plan = preservation._plan_core(self.root, provider_kind="cloudflare-r2", store_ref=STORE, only=OID)
        self.assertTrue(self.run_cleanup()["ok"])
        transport = preservation_fixture._MemoryTransport()
        with self.assertRaises(broker.ExactHumanApprovalWorkflowError):
            preservation.execute_object_storage_bytes_preservation(plan, reviewer_claim=REVIEWER, transport_factory=lambda: transport)
        self.assertEqual(transport.put_calls, 0)
        self.assertEqual(restore_fixture._dest(self.root, BODY).read_bytes(), BODY)

    def test_preservation_can_keep_a_different_key_from_surviving_local_bytes(self):
        key = "old/" + OID[7:]
        self.select_cleanup_key(key)
        restore_fixture._write_local(self.root, BODY)
        restore_fixture._write_rows(self.root, [restore_fixture._row(BODY, locations=[
            restore_fixture._local(BODY), restore_fixture._remote(BODY, key=key)])])
        self.assertTrue(self.run_cleanup()["ok"])
        plan = preservation._plan_core(self.root, provider_kind="cloudflare-r2", store_ref=STORE, only=OID)
        self.assertEqual(len(plan.specs), 1)
        self.assertNotEqual(plan.specs[0].remote_key, key)
        transport = preservation_fixture._MemoryTransport()
        result = preservation.execute_object_storage_bytes_preservation(plan, reviewer_claim=REVIEWER, transport_factory=lambda: transport)
        self.assertTrue(result["ok"], result)
        self.assertEqual(transport.put_calls, 1)
        self.assertNotIn(key, transport.objects)
        self.assertEqual(transport.objects[plan.specs[0].remote_key], BODY)
        loaded = preservation.load_object_storage_bytes_preservation_plan(self.root, manifest_sha256=plan.manifest.manifest_sha256)
        self.assertEqual(loaded.specs[0].remote_key, plan.specs[0].remote_key)

    def test_pending_cleanup_blocks_preservation_of_same_hash_at_another_key(self):
        restore_fixture._write_local(self.root, BODY)
        restore_fixture._write_rows(self.root, [restore_fixture._row(BODY, locations=[restore_fixture._local(BODY)])])
        plan = preservation._plan_core(self.root, provider_kind="cloudflare-r2", store_ref=STORE, only=OID)
        def crash(stage, _entry):
            if stage == "pending_published":
                raise RuntimeError("synthetic-pause")
        with self.assertRaises(broker.ExactHumanApprovalWorkflowError):
            self.run_cleanup(fault_hook=crash)
        transport = preservation_fixture._MemoryTransport()
        with self.assertRaises(broker.ExactHumanApprovalWorkflowError):
            preservation.execute_object_storage_bytes_preservation(plan, reviewer_claim=REVIEWER, transport_factory=lambda: transport)
        self.assertEqual(transport.put_calls, 0)

    def test_restore_does_not_resurrect_disposed_preservation_receipt_source(self):
        restore_fixture._write_local(self.root, BODY)
        restore_fixture._write_rows(self.root, [restore_fixture._row(BODY, locations=[restore_fixture._local(BODY)])])
        plan = preservation._plan_core(self.root, provider_kind="cloudflare-r2", store_ref=STORE, only=OID)
        transport = preservation_fixture._MemoryTransport()
        self.assertTrue(preservation.execute_object_storage_bytes_preservation(plan, reviewer_claim=REVIEWER,
                        transport_factory=lambda: transport)["ok"])
        before = restoration.plan_object_storage_restore(self.root, provider_kind="cloudflare-r2", store_ref=STORE,
                                                         only=OID, mode=restoration.MODE_VERIFY_ONLY)
        self.assertEqual(len(before.specs), 1)
        self.select_cleanup_key(plan.specs[0].remote_key)
        self.assertTrue(self.run_cleanup()["ok"])
        after = restoration.plan_object_storage_restore(self.root, provider_kind="cloudflare-r2", store_ref=STORE,
                                                        only=OID, mode=restoration.MODE_VERIFY_ONLY)
        self.assertEqual(len(after.specs), 0)

    def test_receipt_backed_preservation_is_a_surviving_copy_until_its_exact_key_is_deleted(self):
        restore_fixture._write_local(self.root, BODY)
        restore_fixture._write_rows(self.root, [restore_fixture._row(BODY, locations=[restore_fixture._local(BODY)])])
        plan = preservation._plan_core(self.root, provider_kind="cloudflare-r2", store_ref=STORE, only=OID)
        remote = preservation_fixture._MemoryTransport()
        self.assertTrue(preservation.execute_object_storage_bytes_preservation(plan, reviewer_claim=REVIEWER,
                        transport_factory=lambda: remote)["ok"])
        restore_fixture._write_rows(self.root, [restore_fixture._row(BODY, locations=[restore_fixture._local(BODY, availability="offloaded")])])
        self.assertTrue(self.run_cleanup()["ok"])
        cleanup.assert_referenceable(self.root, [OID])
        self.select_cleanup_key(plan.specs[0].remote_key)
        self.assertTrue(self.run_cleanup()["ok"])
        with self.assertRaisesRegex(cleanup.ObjectStorageCleanupError, "without_usable_copy"):
            cleanup.assert_referenceable(self.root, [OID])

    def test_common_note_create_refuses_deleted_only_copy_then_accepts_rehashed_local_copy(self):
        self.assertTrue(self.run_cleanup()["ok"])
        path = self.root / "inbox/synthetic-new-reference.md"
        path.parent.mkdir()
        raw = ("---\nstatus: draft\n---\nobjet:" + OID).encode()
        with self.assertRaisesRegex(cleanup.ObjectStorageCleanupError, "without_usable_copy"):
            services._write_bytes_create_if_absent(path, raw)
        self.assertFalse(path.exists())
        restore_fixture._write_local(self.root, BODY)
        restore_fixture._write_rows(self.root, [restore_fixture._row(BODY, locations=[restore_fixture._local(BODY)])])
        services._write_bytes_create_if_absent(path, raw)
        self.assertEqual(path.read_bytes(), raw)

    def test_target_lease_is_not_mistaken_for_canonical_archive_writer_lock(self):
        from wom_kit.exact_operation_manifest import current_writer_lock, exact_operation_writer_lock, ExactOperationWriterLock
        from wom_kit.operation_target_leases import TargetLeases
        with TargetLeases(self.root, [("object", OID)]):
            self.assertIsNone(current_writer_lock(self.root))
            with exact_operation_writer_lock(self.root) as writer:
                self.assertIs(type(current_writer_lock(self.root)), ExactOperationWriterLock)
                self.assertIs(current_writer_lock(self.root), writer)
            self.assertIsNone(current_writer_lock(self.root))


if __name__ == "__main__":
    unittest.main()
