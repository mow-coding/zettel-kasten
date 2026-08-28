from __future__ import annotations

import hashlib
import io
import json
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from jsonschema import Draft202012Validator

from wom_kit import archive_services, object_storage_preservation as preservation_module
from wom_kit.archive_cli import main as cli_main
from wom_kit.exact_operation_manifest import (
    ExactOperationApprovalAuthority,
    ExactOperationManifestError,
    FileExactOperationCheckpointStore,
    exact_operation_writer_lock,
)
from wom_kit.object_storage_preservation import (
    ObjectStoragePreservationError,
    ObjectStorageRemoteQueryAdapter,
    _apply_with_store,
    _persist_control,
    _plan_core,
    load_object_storage_bytes_preservation_plan,
    plan_object_storage_bytes_preservation,
    verify_object_storage_bytes_preservation,
)


class _MemoryTransport:
    def __init__(self, *, unavailable_calls: set[int] | None = None) -> None:
        self.objects: dict[str, bytes] = {}
        self.head_calls = 0
        self.put_calls = 0
        self.unavailable_calls = set(unavailable_calls or ())

    def head_object(self, *, key: str, presence_only: bool = False):
        self.head_calls += 1
        if self.head_calls in self.unavailable_calls:
            return {
                "present": False,
                "size": None,
                "checksum_sha256": None,
                "presence_state": "unavailable",
                "verification_state": "unavailable",
            }
        if key not in self.objects:
            return {
                "present": False,
                "size": None,
                "checksum_sha256": None,
                "presence_state": "absent",
                "verification_state": "complete",
            }
        raw = self.objects[key]
        return {
            "present": True,
            "size": len(raw),
            "checksum_sha256": None if presence_only else hashlib.sha256(raw).hexdigest(),
            "presence_state": "present",
            "verification_state": "complete",
        }

    def put_object(
        self,
        *,
        key: str,
        data_path: Path,
        size: int,
        content_sha256: str,
        create_only: bool = False,
    ):
        self.put_calls += 1
        if create_only and key in self.objects:
            return {"status_class": "precondition_failed"}
        raw = data_path.read_bytes()
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != content_sha256:
            return {"status_class": "failed"}
        self.objects[key] = raw
        return {
            "status_class": "ok",
            "size": size,
            "checksum_sha256": content_sha256,
            "etag_opaque": "opaque",
        }

    def create_multipart(self, *, key: str):
        raise AssertionError("small fixtures must not use multipart")

    def put_part(self, **_kwargs):
        raise AssertionError("small fixtures must not use multipart")

    def complete_multipart(self, **_kwargs):
        raise AssertionError("small fixtures must not use multipart")

    def abort_multipart(self, **_kwargs):
        return {"status_class": "ok"}

    def delete_object(self, **_kwargs):
        raise AssertionError("preservation never deletes remote objects")


def _authority() -> ExactOperationApprovalAuthority:
    return ExactOperationApprovalAuthority.from_reference(
        {
            "schema_version": "wom-kit/exact-human-approval-reference/v0.1",
            "approval_id": "approval_" + "a" * 32,
            "context_sha256": "sha256:" + "b" * 64,
            "approval_authority_sha256": "sha256:" + "c" * 64,
            "one_use": True,
        }
    )


class ObjectStoragePreservationTests(unittest.TestCase):
    def _root(self, parent: Path) -> Path:
        root = parent / "archive"
        (root / "objects" / "manifests").mkdir(parents=True)
        (root / "archive.yml").write_text(
            "archive_id: archive:test:object-storage-preservation\n",
            encoding="utf-8",
        )
        archive_id = archive_services.read_archive_id(root)
        binding = archive_services.build_object_storage_provider_binding(
            archive_id=archive_id,
            profile_id="profile:test:object-storage-preservation",
            profile_slug="object-storage-preservation",
            provider_kind="cloudflare-r2",
            storage_account_ref="storage:account:test",
            bucket_name="zettel-kasten-object-storage-preservation-objets",
            region="auto",
            endpoint_ref="provider:endpoint:cloudflare-r2",
            objet_prefix=f"archives/{archive_id}/objets/",
            visibility="private",
        )
        (root / "provider-bindings.yml").write_text(
            archive_services.dump_yaml(
                {
                    "version": "provider-bindings/v0.1",
                    "archive_id": archive_id,
                    "bindings": [binding],
                }
            ),
            encoding="utf-8",
        )
        receipt_relative = archive_services.object_storage_provider_setup_receipt_path(
            "zettel-kasten-object-storage-preservation-objets"
        )
        receipt = archive_services.build_object_storage_provider_setup_receipt(
            archive_id=archive_id,
            profile_id="profile:test:object-storage-preservation",
            profile_slug="object-storage-preservation",
            provider_kind="cloudflare-r2",
            storage_account_ref="storage:account:test",
            bucket_name="zettel-kasten-object-storage-preservation-objets",
            region="auto",
            endpoint_ref="provider:endpoint:cloudflare-r2",
            objet_prefix=f"archives/{archive_id}/objets/",
            visibility="private",
            receipt_path=receipt_relative,
            reviewed_by="person:test",
            timestamp="2026-08-25T00:00:00+09:00",
            dry_run=False,
            manual_steps=[],
        )
        receipt_path = root / receipt_relative
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=True, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return root

    def _local_row(self, root: Path, raw: bytes, *, logical_suffix: str = "local") -> dict:
        digest = hashlib.sha256(raw).hexdigest()
        relative = f"objects/by-sha256/{digest[:2]}/{digest}"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return {
            "object_id": f"sha256:{digest}",
            "sha256": digest,
            "logical_key": f"objects/{logical_suffix}/{digest}",
            "mime": "application/octet-stream",
            "size_bytes": len(raw),
            "locations": [
                {
                    "provider": "local",
                    "availability": "available",
                    "path": relative,
                }
            ],
            "provenance": {"source": "test"},
        }

    def _declared_row(self, raw: bytes, *, verified: bool = False, logical_suffix: str = "remote") -> dict:
        digest = hashlib.sha256(raw).hexdigest()
        locations = [
            {
                "provider": "object_storage",
                "provider_kind": "cloudflare-r2",
                "store_ref": "storage:account:test",
                "availability": "declared_uploaded",
            }
        ]
        if verified:
            locations.append(
                {
                    "provider": "object_storage",
                    "provider_kind": "cloudflare-r2",
                    "store_ref": "storage:account:test",
                    "availability": "wom_uploaded",
                    "remote_key": f"sha256/{digest[:2]}/{digest}",
                    "remote_key_verified": True,
                    "byte_verification_by_wom_kit": True,
                    "provider_confirmation_by_wom_kit": True,
                    "execution_receipt_ref": "receipts/providers/object-storage-executions/test.json",
                }
            )
        return {
            "object_id": f"sha256:{digest}",
            "sha256": digest,
            "logical_key": f"objects/{logical_suffix}/{digest}",
            "mime": "application/pdf",
            "size_bytes": len(raw),
            "locations": locations,
            "provenance": {"source": "test-remote"},
        }

    def _write_rows(self, root: Path, rows: list[dict]) -> bytes:
        raw = b"".join(
            (json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n").encode("ascii")
            for row in rows
        )
        (root / "objects" / "manifests" / "files.jsonl").write_bytes(raw)
        return raw

    def test_inventory_keeps_manifest_scope_and_official_deduplicated_metrics_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            local_only = self._local_row(root, b"local-only")
            official_verified = self._declared_row(b"official", verified=True)
            conflict_local = self._local_row(root, b"conflict", logical_suffix="captured")
            conflict_remote = self._declared_row(
                b"conflict", verified=True, logical_suffix="external"
            )
            legacy_official_evidence = self._declared_row(
                b"legacy-official-evidence", verified=True
            )
            legacy_wom = legacy_official_evidence["locations"][1]
            legacy_wom.pop("remote_key")
            legacy_wom["remote_key_verified"] = False
            pending = self._declared_row(b"pending")
            self._write_rows(
                root,
                [
                    official_verified,
                    conflict_remote,
                    local_only,
                    pending,
                    conflict_local,
                    legacy_official_evidence,
                ],
            )

            result = plan_object_storage_bytes_preservation(
                root,
                store_ref="storage:account:test",
            )

            self.assertEqual(result["manifest_row_count"], 6)
            self.assertEqual(result["unique_object_count"], 5)
            self.assertEqual(result["conflict_classification"]["conflicting_definition_count"], 1)
            self.assertEqual(result["local_location_count"], 2)
            self.assertEqual(result["local_unique_without_remote_record_count"], 1)
            self.assertEqual(result["preservation_planned_count"], 1)
            metrics = result["remote_evidence_metrics"]
            self.assertEqual(metrics["manifest_scope_remote_key_verified_object_count"], 2)
            self.assertEqual(
                metrics["official_deduplicated_wom_uploaded_evidence_object_count"],
                2,
            )
            self.assertEqual(metrics["nonconflicting_remote_declared_pending_adoption_count"], 1)
            self.assertTrue(result["classification_sum_matches_unique_objects"])
            self.assertEqual(result["conflict_classification"]["automatic_merge_count"], 0)

    def test_remote_query_adapter_distinguishes_absent_unavailable_conflict_and_match(self):
        transport = _MemoryTransport()
        adapter = ObjectStorageRemoteQueryAdapter(transport)
        key = "wom-bytes-preserved/v1/sha256/aa/" + "a" * 64
        absent = adapter.query(
            remote_key=key,
            expected_size=3,
            expected_sha256=hashlib.sha256(b"abc").hexdigest(),
            heartbeat=lambda: None,
        )
        self.assertEqual(absent.state, "absent")
        transport.objects[key] = b"xyz"
        mismatch = adapter.query(
            remote_key=key,
            expected_size=3,
            expected_sha256=hashlib.sha256(b"abc").hexdigest(),
            heartbeat=lambda: None,
        )
        self.assertEqual(mismatch.state, "checksum_mismatch")
        transport.objects[key] = b"abc"
        match = adapter.query(
            remote_key=key,
            expected_size=3,
            expected_sha256=hashlib.sha256(b"abc").hexdigest(),
            heartbeat=lambda: None,
        )
        self.assertEqual(match.state, "verified_match")
        transport.unavailable_calls.add(transport.head_calls + 1)
        unavailable = adapter.query(
            remote_key=key,
            expected_size=3,
            expected_sha256=hashlib.sha256(b"abc").hexdigest(),
            heartbeat=lambda: None,
        )
        self.assertEqual(unavailable.state, "verification_unavailable")
        self.assertNotIn(key, json.dumps(match.public_document(), sort_keys=True))

    def test_blocking_remote_query_emits_cooperative_heartbeats(self):
        transport = _MemoryTransport()
        original = transport.head_object

        def slow_head(**kwargs):
            time.sleep(0.02)
            return original(**kwargs)

        transport.head_object = slow_head
        heartbeat_count = 0

        def heartbeat():
            nonlocal heartbeat_count
            heartbeat_count += 1

        key = "wom-bytes-preserved/v1/sha256/aa/" + "a" * 64
        with mock.patch.object(
            preservation_module,
            "_REMOTE_HEARTBEAT_POLL_SECONDS",
            0.002,
        ):
            result = ObjectStorageRemoteQueryAdapter(transport).query(
                remote_key=key,
                expected_size=3,
                expected_sha256=hashlib.sha256(b"abc").hexdigest(),
                heartbeat=heartbeat,
            )
        self.assertEqual(result.state, "absent")
        self.assertGreaterEqual(heartbeat_count, 3)

    def test_create_only_put_is_signed_and_412_is_distinct(self):
        calls = []

        def fake_send(*, method, url, headers, data_path=None, data_bytes=None):
            calls.append((method, url, dict(headers)))
            return {
                "status": 412,
                "headers": {},
                "body": b"<Error><Code>PreconditionFailed</Code></Error>",
            }

        transport = archive_services._object_storage_resolve_transport(
            "cloudflare-r2",
            send=fake_send,
            credential={
                "endpoint_host": "acct.r2.cloudflarestorage.com",
                "bucket": "private-bucket",
                "access_key_id": "AKIAEXAMPLE",
                "secret_access_key": "s" * 40,
                "region": "auto",
            },
        )
        result = transport.put_object(
            key="wom-bytes-preserved/v1/sha256/aa/" + "a" * 64,
            data_path=None,
            size=3,
            content_sha256="a" * 64,
            create_only=True,
        )
        self.assertEqual(result["status_class"], "precondition_failed")
        headers = calls[0][2]
        self.assertEqual(headers["if-none-match"], "*")
        self.assertIn(";if-none-match;", headers["authorization"])

    def test_create_only_multipart_complete_is_signed_and_409_is_distinct(self):
        calls = []

        def fake_send(*, method, url, headers, data_path=None, data_bytes=None):
            calls.append((method, url, dict(headers)))
            return {
                "status": 409,
                "headers": {},
                "body": b"<Error><Code>ConditionalRequestConflict</Code></Error>",
            }

        transport = archive_services._object_storage_resolve_transport(
            "cloudflare-r2",
            send=fake_send,
            credential={
                "endpoint_host": "acct.r2.cloudflarestorage.com",
                "bucket": "private-bucket",
                "access_key_id": "AKIAEXAMPLE",
                "secret_access_key": "s" * 40,
                "region": "auto",
            },
        )
        result = transport.complete_multipart(
            key="wom-bytes-preserved/v1/sha256/bb/" + "b" * 64,
            upload_id="upload-1",
            parts=[{"part_number": 1, "etag_opaque": '"etag"'}],
            content_sha256="b" * 64,
            create_only=True,
        )
        self.assertEqual(result["status_class"], "conditional_conflict")
        headers = calls[0][2]
        self.assertEqual(headers["if-none-match"], "*")
        self.assertIn(";if-none-match;", headers["authorization"])

    def test_conditional_409_is_body_independent_and_all_transients_retry(self):
        classifier = archive_services._object_storage_classify_http_status
        self.assertEqual(classifier(409, None), "conditional_conflict")
        self.assertEqual(classifier(409, "Unknown"), "conditional_conflict")
        self.assertEqual(classifier(429, None), "rate_limited")
        for status in (500, 501, 502, 503, 504, 599):
            self.assertEqual(classifier(status, None), "rate_limited")
        self.assertEqual(classifier(400, "ClientDisconnect"), "rate_limited")

    def test_complete_200_embedded_errors_keep_exact_status_classes(self):
        cases = {
            "PreconditionFailed": "precondition_failed",
            "ConditionalRequestConflict": "conditional_conflict",
            "SlowDown": "rate_limited",
            "ClientDisconnect": "rate_limited",
        }
        for error_code, expected in cases.items():
            with self.subTest(error_code=error_code):
                def fake_send(*, method, url, headers, data_path=None, data_bytes=None):
                    return {
                        "status": 200,
                        "headers": {},
                        "body": f"<Error><Code>{error_code}</Code></Error>".encode("ascii"),
                    }

                transport = archive_services._object_storage_resolve_transport(
                    "cloudflare-r2",
                    send=fake_send,
                    credential={
                        "endpoint_host": "acct.r2.cloudflarestorage.com",
                        "bucket": "private-bucket",
                        "access_key_id": "AKIAEXAMPLE",
                        "secret_access_key": "s" * 40,
                        "region": "auto",
                    },
                )
                result = transport.complete_multipart(
                    key="wom-bytes-preserved/v1/sha256/cc/" + "c" * 64,
                    upload_id="upload-embedded-error",
                    parts=[{"part_number": 1, "etag_opaque": '"etag"'}],
                    content_sha256="c" * 64,
                    create_only=True,
                )
                self.assertEqual(result["status_class"], expected)

    def test_create_and_upload_part_transport_errors_are_retryable(self):
        def fake_send(*, method, url, headers, data_path=None, data_bytes=None):
            return {
                "status": 0,
                "headers": {},
                "body": b"",
                "transport_error": True,
            }

        transport = archive_services._object_storage_resolve_transport(
            "cloudflare-r2",
            send=fake_send,
            credential={
                "endpoint_host": "acct.r2.cloudflarestorage.com",
                "bucket": "private-bucket",
                "access_key_id": "AKIAEXAMPLE",
                "secret_access_key": "s" * 40,
                "region": "auto",
            },
        )
        with self.assertRaises(archive_services._ObjectStorageProviderError) as created:
            transport.create_multipart(key="sha256/create")
        self.assertEqual(created.exception.status_class, "rate_limited")
        with self.assertRaises(archive_services._ObjectStorageProviderError) as uploaded:
            transport.put_part(
                key="sha256/part",
                upload_id="upload-1",
                part_number=1,
                data=b"part",
            )
        self.assertEqual(uploaded.exception.status_class, "rate_limited")

    def test_abort_multipart_requires_confirmed_provider_success(self):
        responses = iter(
            [
                {"status": 503, "headers": {}, "body": b""},
                {"status": 204, "headers": {}, "body": b""},
            ]
        )

        def fake_send(*, method, url, headers, data_path=None, data_bytes=None):
            return next(responses)

        transport = archive_services._object_storage_resolve_transport(
            "cloudflare-r2",
            send=fake_send,
            credential={
                "endpoint_host": "acct.r2.cloudflarestorage.com",
                "bucket": "private-bucket",
                "access_key_id": "AKIAEXAMPLE",
                "secret_access_key": "s" * 40,
                "region": "auto",
            },
        )
        failed = transport.abort_multipart(
            key="sha256/abort", upload_id="upload-failed-abort"
        )
        confirmed = transport.abort_multipart(
            key="sha256/abort", upload_id="upload-confirmed-abort"
        )
        self.assertEqual(failed["status_class"], "rate_limited")
        self.assertEqual(confirmed["status_class"], "ok")

    def test_multipart_counts_real_calls_and_abort_uncertainty_is_resumable(self):
        class _AbortUnconfirmedTransport:
            def __init__(self):
                self.calls = []

            def create_multipart(self, *, key):
                self.calls.append("create")
                return "upload-1"

            def put_part(self, **_kwargs):
                self.calls.append("part")
                raise archive_services._ObjectStorageProviderError("rate_limited")

            def complete_multipart(self, **_kwargs):
                raise AssertionError("complete must not run")

            def abort_multipart(self, **_kwargs):
                self.calls.append("abort")
                return {"status_class": "rate_limited"}

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "multipart.bin"
            path.write_bytes(b"multipart-data")
            transport = _AbortUnconfirmedTransport()
            result, part_count = archive_services._object_storage_multipart_put(
                transport=transport,
                key="sha256/multipart",
                data_path=path,
                content_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                part_size_bytes=4,
                max_provider_mutation_calls=4,
            )
        self.assertEqual(transport.calls, ["create", "part", "abort"])
        self.assertEqual(part_count, 1)
        self.assertEqual(result["provider_mutation_calls"], 3)
        self.assertEqual(result["status_class"], "cleanup_unverified")
        self.assertEqual(
            result["multipart_cleanup_state"], "unconfirmed_abort_response"
        )

    def test_executor_stops_each_provider_call_at_remaining_ceiling(self):
        class _RateLimitedTransport(_MemoryTransport):
            def put_object(self, **_kwargs):
                self.put_calls += 1
                return {"status_class": "rate_limited"}

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "one.bin"
            path.write_bytes(b"one")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            transport = _RateLimitedTransport()
            result = archive_services._object_storage_execute_one_upload(
                transport=transport,
                key="sha256/one",
                data_path=path,
                size=path.stat().st_size,
                content_sha256=digest,
                multipart_threshold_bytes=1024,
                skip_uploaded=False,
                ledger=archive_services._ResumeLedger(
                    Path(temporary) / "common-ledger.jsonl"
                ),
                max_attempts=10,
                max_provider_mutation_calls=3,
                force_upload=True,
                sleep=lambda _seconds: None,
                rng=lambda: 0.0,
            )
        self.assertEqual(transport.put_calls, 3)
        self.assertEqual(result["put_calls"], 3)
        self.assertEqual(result["result_status"], "failed_provider_call_ceiling")

    def test_multipart_create_failures_are_durable_and_exhaust_manifest_ceiling(self):
        class _CreateRateLimitedTransport(_MemoryTransport):
            def __init__(self):
                super().__init__()
                self.create_calls = 0

            def create_multipart(self, *, key):
                self.create_calls += 1
                raise archive_services._ObjectStorageProviderError("rate_limited")

        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            self._write_rows(root, [self._local_row(root, b"multipart-create")])
            plan = _plan_core(root, provider_kind="cloudflare-r2", store_ref="storage:account:test")
            transport = _CreateRateLimitedTransport()
            with (
                mock.patch.object(
                    archive_services, "OBJECT_STORAGE_MULTIPART_THRESHOLD_BYTES", 1
                ),
                mock.patch.object(
                    archive_services, "OBJECT_STORAGE_MAX_ATTEMPTS_PER_OBJECT", 4
                ),
                mock.patch.object(
                    preservation_module, "_provider_put_call_budget", return_value=(1, 4)
                ),
                mock.patch.object(
                    archive_services, "_object_storage_backoff_ms", return_value=0
                ),
            ):
                writer = preservation_module._Writer(plan, transport)
                with self.assertRaises(ObjectStoragePreservationError):
                    writer.write_field(
                        target_kind="object_storage_preservation_terminal_receipt",
                        target_ref=plan.specs[0].receipt_relative,
                        field_ref="terminal_state_token",
                        value=plan.specs[0].receipt_token,
                        heartbeat=lambda: None,
                    )
                self.assertEqual(transport.create_calls, 4)
                self.assertEqual(writer.ledger.total_put_calls(), 4)
                self.assertIsNone(writer.ledger.terminal_for(plan.specs[0]))
                self.assertFalse((root / plan.specs[0].receipt_relative).exists())

                resumed = preservation_module._Writer(plan, transport)
                with self.assertRaises(ObjectStoragePreservationError):
                    resumed.write_field(
                        target_kind="object_storage_preservation_terminal_receipt",
                        target_ref=plan.specs[0].receipt_relative,
                        field_ref="terminal_state_token",
                        value=plan.specs[0].receipt_token,
                        heartbeat=lambda: None,
                    )
                self.assertEqual(transport.create_calls, 4)
                self.assertEqual(resumed.ledger.total_put_calls(), 4)

    def test_exact_writer_uploads_verifies_receipts_and_never_rewrites_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            row = self._local_row(root, b"preserve me")
            manifest_before = self._write_rows(root, [row])
            plan = _plan_core(root, provider_kind="cloudflare-r2", store_ref="storage:account:test")
            transport = _MemoryTransport()
            with exact_operation_writer_lock(root) as lock:
                checkpoints = FileExactOperationCheckpointStore(root, writer_lock=lock)
                result = _apply_with_store(
                    plan,
                    _authority(),
                    transport,
                    checkpoints,
                    resume=False,
                    progress_hook=None,
                )

            self.assertTrue(result["ok"])
            self.assertEqual(result["state"], "bytes_preserved")
            self.assertEqual(result["formal_adoption_status"], "not_adopted")
            self.assertEqual(result["manifest_location_updates"], 0)
            self.assertEqual(result["uploaded_count"], 1)
            self.assertEqual(transport.put_calls, 1)
            self.assertGreaterEqual(transport.head_calls, 3)
            self.assertEqual(
                (root / "objects" / "manifests" / "files.jsonl").read_bytes(),
                manifest_before,
            )
            receipt = root / plan.specs[0].receipt_relative
            data = json.loads(receipt.read_text(encoding="ascii"))
            self.assertEqual(data["preservation_status"], "bytes_preserved")
            self.assertEqual(data["formal_adoption_status"], "not_adopted")
            self.assertFalse(data["manifest_location_updated"])
            verified = verify_object_storage_bytes_preservation(plan, transport=transport)
            self.assertTrue(verified["ok"])

    def test_interrupted_after_receipt_resumes_same_execution_without_second_put(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            self._write_rows(root, [self._local_row(root, b"resume me")])
            plan = _plan_core(root, provider_kind="cloudflare-r2", store_ref="storage:account:test")
            transport = _MemoryTransport(unavailable_calls={3})
            authority = _authority()
            with exact_operation_writer_lock(root) as lock:
                checkpoints = FileExactOperationCheckpointStore(root, writer_lock=lock)
                with self.assertRaises(ExactOperationManifestError):
                    _apply_with_store(
                        plan,
                        authority,
                        transport,
                        checkpoints,
                        resume=False,
                        progress_hook=None,
                    )
            self.assertEqual(transport.put_calls, 1)
            self.assertTrue((root / plan.specs[0].receipt_relative).is_file())
            transport.unavailable_calls.clear()
            with exact_operation_writer_lock(root) as lock:
                checkpoints = FileExactOperationCheckpointStore(root, writer_lock=lock)
                resumed = _apply_with_store(
                    plan,
                    authority,
                    transport,
                    checkpoints,
                    resume=True,
                    progress_hook=None,
                )
            self.assertTrue(resumed["ok"])
            self.assertEqual(resumed["execution"]["resumed_field_count"], 1)
            self.assertEqual(transport.put_calls, 1)

    def test_remote_content_conflict_becomes_durable_review_without_put(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            self._write_rows(root, [self._local_row(root, b"correct")])
            plan = _plan_core(root, provider_kind="cloudflare-r2", store_ref="storage:account:test")
            transport = _MemoryTransport()
            transport.objects[plan.specs[0].remote_key] = b"wrong!!"
            with exact_operation_writer_lock(root) as lock:
                checkpoints = FileExactOperationCheckpointStore(root, writer_lock=lock)
                result = _apply_with_store(
                    plan,
                    _authority(),
                    transport,
                    checkpoints,
                    resume=False,
                    progress_hook=None,
                )
            self.assertEqual(transport.put_calls, 0)
            self.assertEqual(result["state"], "completed_with_review")
            self.assertEqual(result["review_required_count"], 1)
            self.assertEqual(result["classification_counts"]["review_required"], 1)
            receipt = json.loads(
                (root / plan.specs[0].receipt_relative).read_text(encoding="ascii")
            )
            self.assertEqual(receipt["preservation_status"], "review_required")
            self.assertEqual(receipt["provider_put_call_count"], 0)
            self.assertEqual(receipt["review_reason"], "remote_checksum_mismatch")

    def test_existing_review_receipt_stays_visible_while_safe_targets_continue(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            first = self._local_row(root, b"existing review")
            second = self._local_row(root, b"safe continuation")
            self._write_rows(root, [first, second])
            review_plan = _plan_core(
                root,
                provider_kind="cloudflare-r2",
                store_ref="storage:account:test",
                only=first["object_id"],
            )
            review_transport = _MemoryTransport()
            review_transport.objects[review_plan.specs[0].remote_key] = b"wrong bytes!!!!"
            with exact_operation_writer_lock(root) as lock:
                review_result = _apply_with_store(
                    review_plan,
                    _authority(),
                    review_transport,
                    FileExactOperationCheckpointStore(root, writer_lock=lock),
                    resume=False,
                    progress_hook=None,
                )
            self.assertEqual(review_result["review_required_count"], 1)

            continued = _plan_core(
                root,
                provider_kind="cloudflare-r2",
                store_ref="storage:account:test",
            )
            public = continued.public_document()
            self.assertTrue(continued.approveable)
            self.assertEqual(len(continued.specs), 1)
            self.assertEqual(continued.existing_review_required_count, 1)
            self.assertEqual(continued.already_recorded_count, 0)
            self.assertEqual(
                public["state"],
                "ready_for_exact_human_approval_with_existing_review",
            )
            self.assertEqual(public["existing_review_required_count"], 1)
            self.assertIn(
                "object_storage_bytes_preservation_existing_review_required",
                public["reason_codes"],
            )

            safe_transport = _MemoryTransport()
            with exact_operation_writer_lock(root) as lock:
                safe_result = _apply_with_store(
                    continued,
                    _authority(),
                    safe_transport,
                    FileExactOperationCheckpointStore(root, writer_lock=lock),
                    resume=False,
                    progress_hook=None,
                )
            self.assertEqual(safe_result["bytes_preserved_count"], 1)
            self.assertEqual(
                safe_result["state"], "completed_with_existing_review"
            )
            self.assertEqual(safe_result["preexisting_review_required_count"], 1)
            final_plan = _plan_core(
                root,
                provider_kind="cloudflare-r2",
                store_ref="storage:account:test",
            )
            final_public = final_plan.public_document()
            self.assertFalse(final_plan.approveable)
            self.assertEqual(final_plan.existing_review_required_count, 1)
            self.assertEqual(final_plan.already_recorded_count, 1)
            self.assertEqual(final_public["state"], "existing_review_required")
            self.assertNotEqual(final_public["state"], "no_new_bytes_to_preserve")

    def test_already_remote_match_is_durable_and_never_put(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            raw = b"already remote"
            self._write_rows(root, [self._local_row(root, raw)])
            plan = _plan_core(root, provider_kind="cloudflare-r2", store_ref="storage:account:test")
            transport = _MemoryTransport()
            transport.objects[plan.specs[0].remote_key] = raw
            with exact_operation_writer_lock(root) as lock:
                result = _apply_with_store(
                    plan,
                    _authority(),
                    transport,
                    FileExactOperationCheckpointStore(root, writer_lock=lock),
                    resume=False,
                    progress_hook=None,
                )
            self.assertEqual(transport.put_calls, 0)
            self.assertEqual(result["already_remote_verified_count"], 1)
            self.assertEqual(result["provider_put_call_count"], 0)
            receipt = json.loads(
                (root / plan.specs[0].receipt_relative).read_text(encoding="ascii")
            )
            self.assertEqual(receipt["preservation_status"], "already_remote_verified")

    def test_create_only_race_requeries_and_never_falls_back_to_overwrite(self):
        class _RaceTransport(_MemoryTransport):
            def put_object(
                self,
                *,
                key,
                data_path,
                size,
                content_sha256,
                create_only=False,
            ):
                self.put_calls += 1
                self.objects[key] = data_path.read_bytes()
                return {"status_class": "precondition_failed"}

        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            self._write_rows(root, [self._local_row(root, b"won by another writer")])
            plan = _plan_core(root, provider_kind="cloudflare-r2", store_ref="storage:account:test")
            transport = _RaceTransport()
            with exact_operation_writer_lock(root) as lock:
                result = _apply_with_store(
                    plan,
                    _authority(),
                    transport,
                    FileExactOperationCheckpointStore(root, writer_lock=lock),
                    resume=False,
                    progress_hook=None,
                )
            self.assertEqual(transport.put_calls, 1)
            self.assertEqual(result["bytes_preserved_count"], 0)
            self.assertEqual(result["already_remote_verified_count"], 1)
            self.assertEqual(result["provider_put_call_count"], 1)

    def test_crash_after_manifest_bound_ledger_before_receipt_never_second_put(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            self._write_rows(root, [self._local_row(root, b"ledger first")])
            plan = _plan_core(root, provider_kind="cloudflare-r2", store_ref="storage:account:test")
            transport = _MemoryTransport()
            authority = _authority()
            with mock.patch.object(
                preservation_module,
                "_create_terminal_receipt",
                side_effect=RuntimeError("crash after ledger fsync"),
            ):
                with exact_operation_writer_lock(root) as lock:
                    with self.assertRaises(ExactOperationManifestError):
                        _apply_with_store(
                            plan,
                            authority,
                            transport,
                            FileExactOperationCheckpointStore(root, writer_lock=lock),
                            resume=False,
                            progress_hook=None,
                        )
            self.assertEqual(transport.put_calls, 1)
            self.assertFalse((root / plan.specs[0].receipt_relative).exists())

            with exact_operation_writer_lock(root) as lock:
                resumed = _apply_with_store(
                    plan,
                    authority,
                    transport,
                    FileExactOperationCheckpointStore(root, writer_lock=lock),
                    resume=True,
                    progress_hook=None,
                )
            self.assertTrue(resumed["ok"])
            self.assertEqual(transport.put_calls, 1)
            self.assertEqual(resumed["bytes_preserved_count"], 1)
            self.assertEqual(resumed["provider_put_call_count"], 1)

    def test_remote_unavailable_has_no_terminal_receipt_and_remains_resumable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            self._write_rows(root, [self._local_row(root, b"unavailable")])
            plan = _plan_core(root, provider_kind="cloudflare-r2", store_ref="storage:account:test")
            transport = _MemoryTransport(unavailable_calls={1})
            with exact_operation_writer_lock(root) as lock:
                with self.assertRaises(ExactOperationManifestError):
                    _apply_with_store(
                        plan,
                        _authority(),
                        transport,
                        FileExactOperationCheckpointStore(root, writer_lock=lock),
                        resume=False,
                        progress_hook=None,
                    )
            self.assertEqual(transport.put_calls, 0)
            self.assertFalse((root / plan.specs[0].receipt_relative).exists())
            ledger = preservation_module._ManifestBoundPreservationLedger(plan)
            self.assertIsNone(ledger.terminal_for(plan.specs[0]))

    def test_present_without_proven_integer_size_is_unavailable_not_mismatch(self):
        class _UnknownSizeTransport(_MemoryTransport):
            def head_object(self, *, key, presence_only=False):
                self.head_calls += 1
                return {
                    "present": True,
                    "size": None,
                    "checksum_sha256": None,
                    "presence_state": "present",
                    "verification_state": "unavailable",
                }

        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            self._write_rows(root, [self._local_row(root, b"unknown remote size")])
            plan = _plan_core(
                root,
                provider_kind="cloudflare-r2",
                store_ref="storage:account:test",
            )
            transport = _UnknownSizeTransport()
            with exact_operation_writer_lock(root) as lock:
                with self.assertRaises(ExactOperationManifestError):
                    _apply_with_store(
                        plan,
                        _authority(),
                        transport,
                        FileExactOperationCheckpointStore(root, writer_lock=lock),
                        resume=False,
                        progress_hook=None,
                    )
            self.assertEqual(transport.put_calls, 0)
            self.assertFalse((root / plan.specs[0].receipt_relative).exists())
            self.assertIsNone(
                preservation_module._ManifestBoundPreservationLedger(plan).terminal_for(
                    plan.specs[0]
                )
            )

    def test_writer_subtracts_durable_calls_before_invoking_executor(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            self._write_rows(root, [self._local_row(root, b"remaining budget")])
            plan = _plan_core(
                root,
                provider_kind="cloudflare-r2",
                store_ref="storage:account:test",
            )
            with mock.patch.object(
                preservation_module,
                "_provider_put_call_budget",
                return_value=(1, 4),
            ):
                writer = preservation_module._Writer(plan, _MemoryTransport())
            writer.ledger.append_attempt(
                {
                    "object_id": plan.specs[0].object_id,
                    "result_status": "failed_rate_limited",
                    "bytes": 0,
                    "part_count": 0,
                    "attempts": 1,
                    "put_calls": 1,
                    "backoff_ms_total": 0,
                    "multipart_cleanup_state": "not_applicable",
                }
            )
            captured = {}

            def fake_execute(**kwargs):
                captured.update(kwargs)
                return {
                    "object_id": plan.specs[0].object_id,
                    "result_status": "failed_rate_limited",
                    "bytes": 0,
                    "part_count": 0,
                    "attempts": 3,
                    "put_calls": 3,
                    "backoff_ms_total": 0,
                    "multipart_cleanup_state": "not_applicable",
                }

            with mock.patch.object(
                archive_services,
                "_object_storage_execute_one_upload",
                side_effect=fake_execute,
            ):
                with self.assertRaises(ObjectStoragePreservationError):
                    writer.write_field(
                        target_kind="object_storage_preservation_terminal_receipt",
                        target_ref=plan.specs[0].receipt_relative,
                        field_ref="terminal_state_token",
                        value=plan.specs[0].receipt_token,
                        heartbeat=lambda: None,
                    )
            self.assertEqual(captured["max_provider_mutation_calls"], 3)
            self.assertEqual(captured["max_attempts"], 3)
            self.assertEqual(writer.ledger.total_put_calls(), 4)

    def test_post_put_verification_unavailable_resumes_without_second_put(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            self._write_rows(root, [self._local_row(root, b"post-put unavailable")])
            plan = _plan_core(root, provider_kind="cloudflare-r2", store_ref="storage:account:test")
            transport = _MemoryTransport(unavailable_calls={2})
            authority = _authority()
            with exact_operation_writer_lock(root) as lock:
                with self.assertRaises(ExactOperationManifestError):
                    _apply_with_store(
                        plan,
                        authority,
                        transport,
                        FileExactOperationCheckpointStore(root, writer_lock=lock),
                        resume=False,
                        progress_hook=None,
                    )
            self.assertEqual(transport.put_calls, 1)
            self.assertFalse((root / plan.specs[0].receipt_relative).exists())
            self.assertIsNone(
                preservation_module._ManifestBoundPreservationLedger(plan).terminal_for(
                    plan.specs[0]
                )
            )

            transport.unavailable_calls.clear()
            with exact_operation_writer_lock(root) as lock:
                resumed = _apply_with_store(
                    plan,
                    authority,
                    transport,
                    FileExactOperationCheckpointStore(root, writer_lock=lock),
                    resume=True,
                    progress_hook=None,
                )
            self.assertTrue(resumed["ok"])
            self.assertEqual(transport.put_calls, 1)
            self.assertEqual(resumed["already_remote_verified_count"], 1)
            self.assertEqual(resumed["provider_put_call_count"], 1)

    def test_manifest_bound_ledger_rejects_copied_or_tampered_authority(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            self._write_rows(root, [self._local_row(root, b"ledger binding")])
            plan = _plan_core(root, provider_kind="cloudflare-r2", store_ref="storage:account:test")
            transport = _MemoryTransport()
            with exact_operation_writer_lock(root) as lock:
                _apply_with_store(
                    plan,
                    _authority(),
                    transport,
                    FileExactOperationCheckpointStore(root, writer_lock=lock),
                    resume=False,
                    progress_hook=None,
                )
            ledger_path = root / preservation_module._ledger_relative(
                plan.manifest.manifest_sha256
            )
            row = json.loads(ledger_path.read_text(encoding="ascii"))
            row["manifest_sha256"] = "sha256:" + ("0" * 64)
            ledger_path.write_text(
                json.dumps(row, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
                + "\n",
                encoding="ascii",
                newline="\n",
            )
            with self.assertRaises(ObjectStoragePreservationError):
                preservation_module._ManifestBoundPreservationLedger(plan)

    def test_full_source_preflight_blocks_all_puts_when_later_source_drifted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            first = self._local_row(root, b"first source")
            second = self._local_row(root, b"later source")
            self._write_rows(root, [first, second])
            plan = _plan_core(
                root,
                provider_kind="cloudflare-r2",
                store_ref="storage:account:test",
            )
            plan.specs[1].local_path.write_bytes(b"drifted source")
            transport = _MemoryTransport()
            with exact_operation_writer_lock(root) as lock:
                checkpoints = FileExactOperationCheckpointStore(root, writer_lock=lock)
                with self.assertRaises(ExactOperationManifestError):
                    _apply_with_store(
                        plan,
                        _authority(),
                        transport,
                        checkpoints,
                        resume=False,
                        progress_hook=None,
                    )
            self.assertEqual(transport.put_calls, 0)
            self.assertFalse(any((root / spec.receipt_relative).exists() for spec in plan.specs))

    def test_exact_manifest_bound_batch_is_not_truncated_by_legacy_64_put_ceiling(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            rows = [
                self._local_row(root, f"preserve-batch-{index}".encode("ascii"))
                for index in range(65)
            ]
            self._write_rows(root, rows)
            plan = _plan_core(
                root,
                provider_kind="cloudflare-r2",
                store_ref="storage:account:test",
            )
            transport = _MemoryTransport()
            with exact_operation_writer_lock(root) as lock:
                checkpoints = FileExactOperationCheckpointStore(root, writer_lock=lock)
                result = _apply_with_store(
                    plan,
                    _authority(),
                    transport,
                    checkpoints,
                    resume=False,
                    progress_hook=None,
                )
            self.assertTrue(result["ok"])
            self.assertEqual(transport.put_calls, 65)
            self.assertEqual(result["provider_put_call_count"], 65)
            self.assertEqual(result["expected_no_retry_provider_put_call_count"], 65)
            self.assertEqual(
                result["manifest_bound_provider_put_call_ceiling"],
                65 * archive_services.OBJECT_STORAGE_MAX_ATTEMPTS_PER_OBJECT,
            )

    def test_public_plan_does_not_echo_paths_keys_or_object_ids(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            row = self._local_row(root, b"private boundary")
            self._write_rows(root, [row])
            result = plan_object_storage_bytes_preservation(root, store_ref="storage:account:test")
            serialized = json.dumps(result, ensure_ascii=True, sort_keys=True)
            self.assertNotIn(str(root), serialized)
            self.assertNotIn(row["object_id"], serialized)
            self.assertNotIn(row["locations"][0]["path"], serialized)
            self.assertNotIn("wom-bytes-preserved/v1/", serialized)
            self.assertTrue(result["private_values_echoed"] is False)

    def test_single_pass_inventory_is_bounded_on_large_remote_only_fixture(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            rows = [self._declared_row(f"remote-{index}".encode("ascii")) for index in range(5000)]
            self._write_rows(root, rows)
            started = time.monotonic()
            result = plan_object_storage_bytes_preservation(root, store_ref="storage:account:test")
            elapsed = time.monotonic() - started
            self.assertEqual(result["manifest_row_count"], 5000)
            self.assertEqual(result["unique_object_count"], 5000)
            self.assertEqual(result["preservation_planned_count"], 0)
            self.assertLess(elapsed, 8.0)

    def test_large_private_control_document_is_persisted_and_loaded_exactly(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            rows = [
                self._local_row(root, f"local-{index}".encode("ascii"))
                for index in range(600)
            ]
            self._write_rows(root, rows)
            plan = _plan_core(
                root,
                provider_kind="cloudflare-r2",
                store_ref="storage:account:test",
            )
            relative = _persist_control(plan)
            control = root / relative
            self.assertGreater(control.stat().st_size, 64 * 1024)
            loaded = load_object_storage_bytes_preservation_plan(
                root,
                manifest_sha256=plan.manifest.manifest_sha256,
            )
            self.assertTrue(loaded.loaded_from_control)
            self.assertEqual(loaded.manifest.document(), plan.manifest.document())
            self.assertEqual(len(loaded.specs), 600)

    def test_b7_control_and_ledger_resume_without_rewriting_or_second_put(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            payload = b"b7-ledger-before-receipt"
            self._write_rows(root, [self._local_row(root, payload)])
            plan = _plan_core(root, provider_kind="cloudflare-r2", store_ref="storage:account:test")
            spec = plan.specs[0]

            legacy_basis = preservation_module._control_document(plan)
            legacy_basis.pop("control_sha256")
            legacy_basis.pop("existing_review_required_count")
            legacy_basis["schema_version"] = preservation_module.LEGACY_CONTROL_SCHEMA
            legacy_control = {
                **legacy_basis,
                "control_sha256": preservation_module._sha256_document(legacy_basis),
            }
            control_path = root / preservation_module._control_relative(
                plan.manifest.manifest_sha256
            )
            control_path.parent.mkdir(parents=True, exist_ok=True)
            control_bytes = preservation_module._canonical_control_bytes(legacy_control)
            control_path.write_bytes(control_bytes)

            ledger_path = root / preservation_module._ledger_relative(
                plan.manifest.manifest_sha256
            )
            ledger_path.parent.mkdir(parents=True, exist_ok=True)
            legacy_row = {
                "schema_version": preservation_module.LEGACY_LEDGER_SCHEMA,
                "operation": preservation_module.OPERATION,
                "manifest_sha256": plan.manifest.manifest_sha256,
                "target_identity_sha256": spec.target_identity_sha256,
                "object_id": spec.object_id,
                "remote_key_sha256": preservation_module._sha256_document(spec.remote_key),
                "result_status": "uploaded",
                "preservation_status": "bytes_preserved",
                "remote_state": "verified_match",
                "bytes": spec.size_bytes,
                "part_count": 1,
                "attempts": 1,
                "put_calls": 1,
                "backoff_ms_total": 0,
                "completed_at": "2026-08-28T00:00:00Z",
            }
            ledger_path.write_text(
                json.dumps(legacy_row, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="ascii",
            )

            loaded = load_object_storage_bytes_preservation_plan(
                root, manifest_sha256=plan.manifest.manifest_sha256
            )
            _persist_control(loaded)
            self.assertEqual(control_path.read_bytes(), control_bytes)
            transport = _MemoryTransport()
            transport.objects[spec.remote_key] = payload
            writer = preservation_module._Writer(loaded, transport)
            writer.write_field(
                target_kind="object_storage_preservation_terminal_receipt",
                target_ref=spec.receipt_relative,
                field_ref="terminal_state_token",
                value=spec.receipt_token,
                heartbeat=lambda: None,
            )
            self.assertEqual(transport.put_calls, 0)
            self.assertTrue((root / spec.receipt_relative).is_file())
            self.assertEqual(writer.ledger.total_put_calls(), 1)

    def test_legacy_schema_shapes_are_exact_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            self._write_rows(root, [self._local_row(root, b"strict-legacy")])
            plan = _plan_core(root, provider_kind="cloudflare-r2", store_ref="storage:account:test")
            legacy = preservation_module._control_document(plan)
            legacy.pop("control_sha256")
            legacy["schema_version"] = preservation_module.LEGACY_CONTROL_SCHEMA
            # A v0.2 document that claims a v0.3-only field is ambiguous even
            # when its self-hash is recomputed.
            legacy["control_sha256"] = preservation_module._sha256_document(legacy)
            path = root / preservation_module._control_relative(plan.manifest.manifest_sha256)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(preservation_module._canonical_control_bytes(legacy))
            with self.assertRaises(ObjectStoragePreservationError):
                load_object_storage_bytes_preservation_plan(
                    root, manifest_sha256=plan.manifest.manifest_sha256
                )

            spec = plan.specs[0]
            row = {
                "schema_version": preservation_module.LEGACY_LEDGER_SCHEMA,
                "operation": preservation_module.OPERATION,
                "manifest_sha256": plan.manifest.manifest_sha256,
                "target_identity_sha256": spec.target_identity_sha256,
                "object_id": spec.object_id,
                "remote_key_sha256": preservation_module._sha256_document(spec.remote_key),
                "result_status": "failed_upload",
                "preservation_status": None,
                "remote_state": None,
                "bytes": 0,
                "part_count": 0,
                "attempts": 1,
                "put_calls": 1,
                "backoff_ms_total": 0,
                "completed_at": "2026-08-28T00:00:00Z",
            }
            ledger_path = root / preservation_module._ledger_relative(
                plan.manifest.manifest_sha256
            )
            ledger_path.parent.mkdir(parents=True, exist_ok=True)
            ambiguous_rows = (
                {**row, "multipart_cleanup_state": "not_required"},
                {
                    **row,
                    "schema_version": preservation_module.LEDGER_SCHEMA,
                },
            )
            for ambiguous in ambiguous_rows:
                with self.subTest(schema=ambiguous["schema_version"]):
                    ledger_path.write_text(
                        json.dumps(ambiguous, sort_keys=True, separators=(",", ":"))
                        + "\n",
                        encoding="ascii",
                    )
                    with self.assertRaises(ObjectStoragePreservationError):
                        preservation_module._ManifestBoundPreservationLedger(plan)

    def test_resume_control_rejects_non_target_inventory_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            local = self._local_row(root, b"resume target")
            remote = self._declared_row(b"unselected remote")
            self._write_rows(root, [local, remote])
            plan = _plan_core(
                root,
                provider_kind="cloudflare-r2",
                store_ref="storage:account:test",
            )
            _persist_control(plan)
            remote["logical_key"] = "objects/changed-after-approval"
            self._write_rows(root, [local, remote])
            with self.assertRaises(ObjectStoragePreservationError) as captured:
                load_object_storage_bytes_preservation_plan(
                    root,
                    manifest_sha256=plan.manifest.manifest_sha256,
                )
            self.assertEqual(captured.exception.code, "object_storage_preservation_plan_changed")

    def test_control_and_remote_verification_require_current_setup_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            local = self._local_row(root, b"setup-gated-resume")
            self._write_rows(root, [local])
            plan = _plan_core(
                root,
                provider_kind="cloudflare-r2",
                store_ref="storage:account:test",
            )
            _persist_control(plan)
            for receipt in (root / "receipts" / "providers").glob(
                "*.object-storage-setup.json"
            ):
                receipt.unlink()

            with self.assertRaises(ObjectStoragePreservationError) as load_error:
                load_object_storage_bytes_preservation_plan(
                    root,
                    manifest_sha256=plan.manifest.manifest_sha256,
                )
            self.assertEqual(
                load_error.exception.code,
                "object_storage_preservation_setup_evidence_missing",
            )

            transport = _MemoryTransport()
            with self.assertRaises(ObjectStoragePreservationError) as verify_error:
                verify_object_storage_bytes_preservation(plan, transport=transport)
            self.assertEqual(
                verify_error.exception.code,
                "object_storage_preservation_setup_evidence_missing",
            )
            self.assertEqual(transport.head_calls, 0)
            self.assertEqual(transport.put_calls, 0)

    def test_cli_extends_adopt_family_with_content_free_preservation_preview(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            row = self._local_row(root, b"cli private bytes")
            self._write_rows(root, [row])
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                status = cli_main(
                    [
                        "object-storage-adopt-existing",
                        str(root),
                        "--preserve-local-only",
                        "--store-ref",
                        "storage:account:test",
                        "--dry-run",
                        "--format",
                        "json",
                    ]
                )
            result = json.loads(stdout.getvalue())
            serialized = json.dumps(result, sort_keys=True)
            self.assertEqual(status, 0)
            self.assertEqual(result["preservation_planned_count"], 1)
            self.assertFalse(result["provider_api_called"])
            self.assertNotIn(str(root), serialized)
            self.assertNotIn(row["object_id"], serialized)
            self.assertEqual(stderr.getvalue(), "")
            self.assertFalse(
                (root / "receipts" / "providers" / "object-storage-bytes-preserved").exists()
            )
            self.assertFalse(
                (root / "profiles" / "local" / "exact-operations").exists()
            )

    def test_cli_refuses_approve_without_bound_manifest_before_secret_read(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            self._write_rows(root, [self._local_row(root, b"never read a credential")])
            stdout = io.StringIO()
            stderr = io.StringIO()
            with mock.patch.object(
                archive_services,
                "_resolve_credential_value",
                side_effect=AssertionError("credential read"),
            ), redirect_stdout(stdout), redirect_stderr(stderr):
                status = cli_main(
                    [
                        "object-storage-adopt-existing",
                        str(root),
                        "--preserve-local-only",
                        "--store-ref",
                        "storage:account:test",
                        "--approve",
                        "--reviewed-by",
                        "reviewer",
                        "--format",
                        "json",
                    ]
                )
            result = json.loads(stdout.getvalue())
            self.assertEqual(status, 1)
            self.assertEqual(
                result["reason_codes"],
                ["object_storage_preservation_approval_required"],
            )
            self.assertEqual(stderr.getvalue(), "")

    def test_receipt_schema_is_packaged_in_parity_and_validates_exact_receipt(self):
        kit_root = Path(__file__).resolve().parents[1]
        source_path = (
            kit_root
            / "schemas"
            / "object-storage-preservation-terminal-receipt-v0.2.schema.json"
        )
        packaged_path = (
            kit_root
            / "src"
            / "wom_kit"
            / "_resources"
            / "schemas"
            / "object-storage-preservation-terminal-receipt-v0.2.schema.json"
        )
        self.assertEqual(source_path.read_bytes(), packaged_path.read_bytes())
        schema = json.loads(source_path.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            self._write_rows(root, [self._local_row(root, b"schema receipt")])
            plan = _plan_core(
                root,
                provider_kind="cloudflare-r2",
                store_ref="storage:account:test",
            )
            transport = _MemoryTransport()
            with exact_operation_writer_lock(root) as lock:
                _apply_with_store(
                    plan,
                    _authority(),
                    transport,
                    FileExactOperationCheckpointStore(root, writer_lock=lock),
                    resume=False,
                    progress_hook=None,
                )
            receipt = json.loads(
                (root / plan.specs[0].receipt_relative).read_text(encoding="ascii")
            )
        Draft202012Validator(schema).validate(receipt)

    def test_v01_receipt_contract_is_immutable_and_conservatively_reused(self):
        kit_root = Path(__file__).resolve().parents[1]
        source_path = (
            kit_root
            / "schemas"
            / "object-storage-bytes-preserved-receipt-v0.1.schema.json"
        )
        packaged_path = (
            kit_root
            / "src"
            / "wom_kit"
            / "_resources"
            / "schemas"
            / "object-storage-bytes-preserved-receipt-v0.1.schema.json"
        )
        self.assertEqual(source_path.read_bytes(), packaged_path.read_bytes())
        schema = json.loads(source_path.read_text(encoding="utf-8"))
        self.assertEqual(
            schema["properties"]["preservation_status"],
            {"const": "bytes_preserved"},
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            self._write_rows(root, [self._local_row(root, b"legacy receipt")])
            original = _plan_core(
                root,
                provider_kind="cloudflare-r2",
                store_ref="storage:account:test",
            )
            spec = original.specs[0]
            legacy = preservation_module._legacy_receipt_document(
                object_id=spec.object_id,
                size_bytes=spec.size_bytes,
                provider_kind=original.provider_kind,
                store_ref=original.store_ref,
                inventory_sha256=original.source_inventory_sha256,
            )
            Draft202012Validator(schema).validate(legacy)
            receipt_path = root / spec.receipt_relative
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_bytes(
                preservation_module._canonical_receipt_bytes(legacy)
            )
            resumed_plan = _plan_core(
                root,
                provider_kind="cloudflare-r2",
                store_ref="storage:account:test",
            )
            self.assertEqual(resumed_plan.already_recorded_count, 1)
            self.assertEqual(resumed_plan.specs, ())
            self.assertEqual(
                json.loads(receipt_path.read_text(encoding="ascii")),
                legacy,
            )


if __name__ == "__main__":
    unittest.main()
