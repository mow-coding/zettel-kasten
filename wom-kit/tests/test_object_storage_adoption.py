from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from jsonschema import Draft202012Validator

from wom_kit import archive_services
from wom_kit.archive_cli import main as cli_main
from wom_kit.exact_operation_manifest import (
    ExactOperationApprovalAuthority,
    FileExactOperationCheckpointStore,
    exact_operation_writer_lock,
    revert_exact_operation_fields,
)
from wom_kit.object_storage_adoption import (
    ObjectStorageAdoptionError,
    ObjectStorageHeadQueryAdapter,
    _apply_with_store,
    _execution_adapters,
    _persist_control,
    load_object_storage_formal_adoption_plan,
    plan_object_storage_formal_adoption,
    verify_object_storage_formal_adoption,
)


class _MemoryHeadTransport:
    def __init__(self, objects: dict[str, int]) -> None:
        self.objects = dict(objects)
        self.head_calls = 0
        self.put_calls = 0

    def head_object(self, *, key: str, presence_only: bool = False):
        self.head_calls += 1
        if key not in self.objects:
            return {
                "present": False,
                "size": None,
                "presence_state": "absent",
                "verification_state": "complete",
            }
        return {
            "present": True,
            "size": self.objects[key],
            "checksum_sha256": None,
            "presence_state": "present",
            "verification_state": "complete",
        }

    def put_object(self, **_kwargs):
        self.put_calls += 1
        raise AssertionError("formal adoption must never PUT")


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


class ObjectStorageFormalAdoptionPlanTests(unittest.TestCase):
    def _root(self, parent: Path) -> Path:
        root = parent / "archive"
        (root / "objects" / "manifests").mkdir(parents=True)
        (root / "archive.yml").write_text(
            "archive_id: archive:test:object-storage-adoption\n", encoding="utf-8"
        )
        archive_id = archive_services.read_archive_id(root)
        binding = archive_services.build_object_storage_provider_binding(
            archive_id=archive_id,
            profile_id="profile:test:object-storage-adoption",
            profile_slug="object-storage-adoption",
            provider_kind="cloudflare-r2",
            storage_account_ref="storage:account:test",
            bucket_name="zettel-kasten-object-storage-adoption-objets",
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
            "zettel-kasten-object-storage-adoption-objets"
        )
        receipt = archive_services.build_object_storage_provider_setup_receipt(
            archive_id=archive_id,
            profile_id="profile:test:object-storage-adoption",
            profile_slug="object-storage-adoption",
            provider_kind="cloudflare-r2",
            storage_account_ref="storage:account:test",
            bucket_name="zettel-kasten-object-storage-adoption-objets",
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

    @staticmethod
    def _row(raw: bytes, *, logical_key: str, mime: str, locations: list[dict]) -> dict:
        digest = hashlib.sha256(raw).hexdigest()
        return {
            "object_id": "sha256:" + digest,
            "sha256": digest,
            "logical_key": logical_key,
            "mime": mime,
            "size_bytes": len(raw),
            "locations": locations,
        }

    @staticmethod
    def _write_rows(root: Path, rows: list[dict]) -> None:
        (root / "objects" / "manifests" / "files.jsonl").write_text(
            "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
            encoding="utf-8",
        )

    @staticmethod
    def _write_map(parent: Path, rows: list[dict]) -> Path:
        path = parent / "key-map.jsonl"
        path.write_text(
            "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
            encoding="utf-8",
        )
        return path

    def test_plan_queries_all_mapped_and_adopts_only_unique_pending_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = self._root(parent)
            pending = self._row(
                b"pending",
                logical_key="pending",
                mime="application/octet-stream",
                locations=[{"provider": "object_storage", "availability": "declared_uploaded"}],
            )
            existing = self._row(
                b"existing",
                logical_key="existing",
                mime="application/octet-stream",
                locations=[],
            )
            existing_digest = existing["sha256"]
            existing_key = f"custom/{existing_digest}"
            existing["locations"].append(
                {
                    "provider": "object_storage",
                    "provider_kind": "cloudflare-r2",
                    "store_ref": "storage:account:test",
                    "availability": "wom_uploaded",
                    "content_addressed": True,
                    "key_strategy": "prefix",
                    "key_hint": f"sha256/{existing_digest[:2]}/{existing_digest}",
                    "remote_key": existing_key,
                    "remote_key_verified": True,
                    "remote_key_verification": "presence_size",
                    "byte_verification_by_wom_kit": True,
                    "provider_confirmation_by_wom_kit": True,
                    "execution_receipt_ref": "receipts/providers/object-storage-executions/old.json",
                }
            )
            conflict_a = self._row(
                b"conflict",
                logical_key="captured",
                mime="image/png",
                locations=[{"provider": "local", "availability": "available", "path": "private-a"}],
            )
            conflict_b = self._row(
                b"conflict",
                logical_key="declared",
                mime="application/octet-stream",
                locations=[{"provider": "object_storage", "availability": "declared_uploaded"}],
            )
            self._write_rows(root, [pending, existing, conflict_a, conflict_b])
            key_map = self._write_map(
                parent,
                [
                    {"sha256": pending["sha256"], "remote_key": f"custom/{pending['sha256']}"},
                    {"sha256": existing_digest, "remote_key": existing_key},
                    {"sha256": conflict_a["sha256"], "remote_key": f"custom/{conflict_a['sha256']}"},
                ],
            )

            plan = plan_object_storage_formal_adoption(
                root, key_map_path=key_map, store_ref="storage:account:test"
            )
            result = plan.public_document()

            self.assertEqual(result["manifest_row_count"], 4)
            self.assertEqual(result["unique_object_count"], 3)
            self.assertEqual(result["remote_query_planned_count"], 3)
            self.assertEqual(result["formal_adoption_planned_count"], 1)
            self.assertEqual(result["existing_formal_adoption_verification_count"], 1)
            self.assertEqual(result["mapped_conflicting_definition_count"], 1)
            self.assertEqual(result["manifest_rewrite_planned_count"], 1)
            self.assertEqual(result["per_object_manifest_rewrite_planned_count"], 0)
            self.assertEqual(len(plan.manifest.items), 4)
            self.assertEqual(result["conflict_classification"]["automatic_merge_count"], 0)
            evidence = plan.manifest.operation_evidence.document()
            self.assertEqual(evidence["counts"]["manifest_row_count"], 4)
            self.assertEqual(evidence["counts"]["unique_object_count"], 3)
            self.assertEqual(evidence["counts"]["conflicting_definition_count"], 1)
            self.assertEqual(evidence["counts"]["remote_query_planned_count"], 3)
            self.assertFalse(evidence["private_values_echoed"])
            serialized = json.dumps(result)
            self.assertNotIn(pending["sha256"], serialized)
            self.assertNotIn("private-a", serialized)
            self.assertNotIn("custom/", serialized)

    def test_head_adapter_distinguishes_match_absence_mismatch_and_unavailable(self):
        key = "custom/" + "a" * 64
        transport = _MemoryHeadTransport({key: 7})
        adapter = ObjectStorageHeadQueryAdapter(transport)
        matched = adapter.query(remote_key=key, expected_size=7, heartbeat=lambda: None)
        mismatch = adapter.query(remote_key=key, expected_size=8, heartbeat=lambda: None)
        absent = adapter.query(
            remote_key="custom/" + "b" * 64,
            expected_size=7,
            heartbeat=lambda: None,
        )
        self.assertEqual(matched.state, "verified_match")
        self.assertEqual(mismatch.state, "size_mismatch")
        self.assertEqual(absent.state, "absent")
        self.assertFalse(matched.public_document()["remote_key_echoed"])

        class Unavailable:
            @staticmethod
            def head_object(**_kwargs):
                raise RuntimeError("private provider body")

        unavailable = ObjectStorageHeadQueryAdapter(Unavailable()).query(
            remote_key=key, expected_size=7, heartbeat=lambda: None
        )
        self.assertEqual(unavailable.state, "unavailable")
        self.assertNotIn("private provider body", json.dumps(unavailable.public_document()))

    def test_batch_judgment_is_fingerprint_bound_and_never_enables_merge_or_adopt(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = self._root(parent)
            a = self._row(
                b"same",
                logical_key="a",
                mime="text/plain",
                locations=[{"provider": "local", "availability": "available", "path": "a"}],
            )
            b = self._row(
                b"same",
                logical_key="b",
                mime="application/octet-stream",
                locations=[{"provider": "object_storage", "availability": "declared_uploaded"}],
            )
            self._write_rows(root, [a, b])
            key_map = self._write_map(
                parent,
                [{"sha256": a["sha256"], "remote_key": f"custom/{a['sha256']}"}],
            )
            first = plan_object_storage_formal_adoption(
                root, key_map_path=key_map, store_ref="storage:account:test"
            )
            fingerprint = first.conflict_batches[0].batch_fingerprint
            judgment = parent / "judgment.jsonl"
            judgment.write_text(
                json.dumps(
                    {
                        "batch_fingerprint": fingerprint,
                        "judgment": "keep_definitions_distinct",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            second = plan_object_storage_formal_adoption(
                root,
                key_map_path=key_map,
                judgment_path=judgment,
                store_ref="storage:account:test",
            )
            batch = second.public_document()["conflict_classification"]["batches"][0]
            self.assertEqual(batch["judgment"], "keep_definitions_distinct")
            self.assertFalse(batch["automatic_merge_allowed"])
            self.assertFalse(batch["formal_adoption_allowed"])
            self.assertEqual(second.public_document()["formal_adoption_planned_count"], 0)

            judgment.write_text(
                json.dumps(
                    {"batch_fingerprint": "batch:" + "f" * 64, "judgment": "defer_review"}
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(ObjectStorageAdoptionError) as captured:
                plan_object_storage_formal_adoption(
                    root,
                    key_map_path=key_map,
                    judgment_path=judgment,
                    store_ref="storage:account:test",
                )
            self.assertEqual(captured.exception.code, "object_storage_adoption_judgment_invalid")

    def test_exact_writer_heads_every_mapping_twice_and_rewrites_manifest_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = self._root(parent)
            pending = self._row(
                b"pending",
                logical_key="pending",
                mime="application/octet-stream",
                locations=[{"provider": "object_storage", "availability": "declared_uploaded"}],
            )
            existing = self._row(
                b"existing",
                logical_key="existing",
                mime="application/octet-stream",
                locations=[],
            )
            keys = {
                pending["sha256"]: f"custom/{pending['sha256']}",
                existing["sha256"]: f"custom/{existing['sha256']}",
            }
            existing["locations"].append(
                archive_services.object_storage_wom_uploaded_location(
                    digest=existing["sha256"],
                    provider_kind="cloudflare-r2",
                    store_ref="storage:account:test",
                    execution_receipt_ref="receipts/providers/object-storage-executions/old.json",
                    uploaded_at="2026-08-22T00:00:00Z",
                    key_strategy="prefix",
                    remote_key=keys[existing["sha256"]],
                    remote_key_verification="presence_size",
                    remote_size=len(b"existing"),
                )
            )
            self._write_rows(root, [pending, existing])
            key_map = self._write_map(
                parent,
                [
                    {"sha256": digest, "remote_key": remote_key}
                    for digest, remote_key in keys.items()
                ],
            )
            plan = plan_object_storage_formal_adoption(
                root, key_map_path=key_map, store_ref="storage:account:test"
            )
            transport = _MemoryHeadTransport(
                {
                    keys[pending["sha256"]]: len(b"pending"),
                    keys[existing["sha256"]]: len(b"existing"),
                }
            )
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
            self.assertEqual(result["remote_query_verified_count"], 2)
            self.assertEqual(result["formal_adoption_count"], 1)
            self.assertEqual(result["manifest_location_updates"], 1)
            self.assertEqual(result["central_manifest_rewrite_count_ceiling"], 1)
            self.assertEqual(
                result["execution"]["operation_evidence"]["counts"][
                    "remote_query_planned_count"
                ],
                2,
            )
            self.assertEqual(transport.head_calls, 4)
            self.assertEqual(transport.put_calls, 0)
            rows = [
                json.loads(line)
                for line in (root / "objects" / "manifests" / "files.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            pending_after = next(row for row in rows if row["object_id"] == pending["object_id"])
            owned = [
                item
                for item in pending_after["locations"]
                if item.get("execution_receipt_ref", "").startswith(
                    "receipts/providers/object-storage-formal-adoption/"
                )
            ]
            self.assertEqual(len(owned), 1)
            self.assertFalse(owned[0]["byte_verification_by_wom_kit"])
            self.assertFalse(owned[0]["provider_upload_time_known"])
            receipt = json.loads((root / plan.specs[0].receipt_relative).read_text(encoding="utf-8"))
            schema_path = (
                Path(__file__).resolve().parents[1]
                / "schemas"
                / "object-storage-formal-adoption-receipt-v0.1.schema.json"
            )
            Draft202012Validator(
                json.loads(schema_path.read_text(encoding="utf-8")),
                format_checker=Draft202012Validator.FORMAT_CHECKER,
            ).validate(receipt)

            # A wholly separate verifier performs fresh HEAD calls and accepts
            # the immutable receipts plus the one aggregate manifest projection.
            verified = verify_object_storage_formal_adoption(plan, transport=transport)
            self.assertTrue(verified["ok"])
            self.assertEqual(transport.head_calls, 6)

            with exact_operation_writer_lock(root) as lock:
                payloads, writer, verifier = _execution_adapters(plan, transport)
                reverted = revert_exact_operation_fields(
                    plan.manifest,
                    selected_fields=tuple(
                        (item.item_id, field.field_ref)
                        for item in plan.manifest.items
                        for field in item.fields
                    ),
                    payloads=payloads,
                    writer=writer,
                    verifier=verifier,
                    checkpoint_store=FileExactOperationCheckpointStore(
                        root, writer_lock=lock
                    ),
                    approval_authority=_authority(),
                )
            self.assertEqual(reverted["status"], "completed")
            self.assertEqual(reverted["mode"], "revert")
            self.assertFalse((root / plan.specs[0].receipt_relative).exists())
            reverted_rows = [
                json.loads(line)
                for line in (root / "objects" / "manifests" / "files.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            pending_reverted = next(
                row for row in reverted_rows if row["object_id"] == pending["object_id"]
            )
            self.assertFalse(
                any(
                    item.get("execution_receipt_ref", "").startswith(
                        "receipts/providers/object-storage-formal-adoption/"
                    )
                    for item in pending_reverted["locations"]
                )
            )

    def test_control_resume_reloads_after_manifest_projection_without_source_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = self._root(parent)
            row = self._row(
                b"pending",
                logical_key="pending",
                mime="application/octet-stream",
                locations=[{"provider": "object_storage", "availability": "declared_uploaded"}],
            )
            self._write_rows(root, [row])
            remote_key = f"custom/{row['sha256']}"
            key_map = self._write_map(
                parent, [{"sha256": row["sha256"], "remote_key": remote_key}]
            )
            plan = plan_object_storage_formal_adoption(
                root, key_map_path=key_map, store_ref="storage:account:test"
            )
            _persist_control(plan)
            transport = _MemoryHeadTransport({remote_key: len(b"pending")})
            with exact_operation_writer_lock(root) as lock:
                result = _apply_with_store(
                    plan,
                    _authority(),
                    transport,
                    FileExactOperationCheckpointStore(root, writer_lock=lock),
                    resume=False,
                    progress_hook=None,
                )
            self.assertTrue(result["ok"])
            loaded = load_object_storage_formal_adoption_plan(
                root, manifest_sha256=plan.manifest.manifest_sha256
            )
            self.assertTrue(loaded.loaded_from_control)
            self.assertEqual(loaded.manifest.document(), plan.manifest.document())

    def test_control_and_remote_verification_require_current_setup_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = self._root(parent)
            row = self._row(
                b"setup-gated-adoption",
                logical_key="pending",
                mime="application/octet-stream",
                locations=[
                    {"provider": "object_storage", "availability": "declared_uploaded"}
                ],
            )
            self._write_rows(root, [row])
            remote_key = f"custom/{row['sha256']}"
            key_map = self._write_map(
                parent, [{"sha256": row["sha256"], "remote_key": remote_key}]
            )
            plan = plan_object_storage_formal_adoption(
                root, key_map_path=key_map, store_ref="storage:account:test"
            )
            _persist_control(plan)
            for receipt in (root / "receipts" / "providers").glob(
                "*.object-storage-setup.json"
            ):
                receipt.unlink()

            with self.assertRaises(ObjectStorageAdoptionError) as load_error:
                load_object_storage_formal_adoption_plan(
                    root, manifest_sha256=plan.manifest.manifest_sha256
                )
            self.assertEqual(
                load_error.exception.code,
                "object_storage_adoption_setup_evidence_missing",
            )

            transport = _MemoryHeadTransport({remote_key: len(b"setup-gated-adoption")})
            with self.assertRaises(ObjectStorageAdoptionError) as verify_error:
                verify_object_storage_formal_adoption(plan, transport=transport)
            self.assertEqual(
                verify_error.exception.code,
                "object_storage_adoption_setup_evidence_missing",
            )
            self.assertEqual(transport.head_calls, 0)
            self.assertEqual(transport.put_calls, 0)

    def test_remote_mismatch_fails_before_receipt_or_manifest_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = self._root(parent)
            row = self._row(
                b"pending",
                logical_key="pending",
                mime="application/octet-stream",
                locations=[{"provider": "object_storage", "availability": "declared_uploaded"}],
            )
            original_manifest = json.dumps(row, separators=(",", ":")) + "\n"
            self._write_rows(root, [row])
            remote_key = f"custom/{row['sha256']}"
            key_map = self._write_map(
                parent, [{"sha256": row["sha256"], "remote_key": remote_key}]
            )
            plan = plan_object_storage_formal_adoption(
                root, key_map_path=key_map, store_ref="storage:account:test"
            )
            transport = _MemoryHeadTransport({remote_key: len(b"pending") + 1})
            with exact_operation_writer_lock(root) as lock:
                with self.assertRaises(Exception):
                    _apply_with_store(
                        plan,
                        _authority(),
                        transport,
                        FileExactOperationCheckpointStore(root, writer_lock=lock),
                        resume=False,
                        progress_hook=None,
                    )
            self.assertFalse((root / plan.specs[0].receipt_relative).exists())
            self.assertEqual(
                (root / "objects" / "manifests" / "files.jsonl").read_text(encoding="utf-8"),
                original_manifest,
            )
            self.assertEqual(transport.put_calls, 0)

    def test_cli_extends_existing_adopt_family_without_provider_or_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = self._root(parent)
            row = self._row(
                b"pending",
                logical_key="pending",
                mime="application/octet-stream",
                locations=[{"provider": "object_storage", "availability": "declared_uploaded"}],
            )
            self._write_rows(root, [row])
            key_map = self._write_map(
                parent,
                [{"sha256": row["sha256"], "remote_key": f"custom/{row['sha256']}"}],
            )
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                status = cli_main(
                    [
                        "object-storage-adopt-existing",
                        str(root),
                        "--formal-adoption",
                        "--key-map",
                        str(key_map),
                        "--store-ref",
                        "storage:account:test",
                        "--dry-run",
                        "--format",
                        "json",
                    ]
                )
            result = json.loads(stdout.getvalue())
            serialized = json.dumps(result)
            self.assertEqual(status, 0)
            self.assertEqual(result["remote_query_planned_count"], 1)
            self.assertEqual(result["formal_adoption_planned_count"], 1)
            self.assertFalse(result["provider_api_called"])
            self.assertFalse(result["writes_performed"])
            self.assertNotIn(str(root), serialized)
            self.assertNotIn(row["sha256"], serialized)
            self.assertNotIn("custom/", serialized)
            self.assertEqual(stderr.getvalue(), "")
            self.assertFalse((root / "profiles" / "local" / "exact-operations").exists())


if __name__ == "__main__":
    unittest.main()
