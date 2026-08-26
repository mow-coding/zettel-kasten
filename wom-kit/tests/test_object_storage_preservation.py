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

    def put_object(self, *, key: str, data_path: Path, size: int, content_sha256: str):
        self.put_calls += 1
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
        return None

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

    def test_remote_content_conflict_fails_closed_without_put_or_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            self._write_rows(root, [self._local_row(root, b"correct")])
            plan = _plan_core(root, provider_kind="cloudflare-r2", store_ref="storage:account:test")
            transport = _MemoryTransport()
            transport.objects[plan.specs[0].remote_key] = b"wrong!!"
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
            self.assertFalse((root / plan.specs[0].receipt_relative).exists())

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
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(Path(temporary))
            self._write_rows(root, [self._local_row(root, b"schema receipt")])
            plan = _plan_core(
                root,
                provider_kind="cloudflare-r2",
                store_ref="storage:account:test",
            )
            receipt = json.loads(plan.specs[0].receipt_bytes.decode("ascii"))
        Draft202012Validator(schema).validate(receipt)


if __name__ == "__main__":
    unittest.main()
