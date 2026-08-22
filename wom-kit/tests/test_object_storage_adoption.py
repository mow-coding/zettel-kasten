from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from wom_kit import archive_services
from wom_kit.exact_operation_manifest import (
    ExactOperationApprovalAuthority,
    FileExactOperationCheckpointStore,
    exact_operation_writer_lock,
)
from wom_kit.object_storage_adoption import (
    ObjectStorageAdoptionError,
    _apply_with_store,
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
            serialized = json.dumps(result)
            self.assertNotIn(pending["sha256"], serialized)
            self.assertNotIn("private-a", serialized)
            self.assertNotIn("custom/", serialized)

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

            # A wholly separate verifier performs fresh HEAD calls and accepts
            # the immutable receipts plus the one aggregate manifest projection.
            verified = verify_object_storage_formal_adoption(plan, transport=transport)
            self.assertTrue(verified["ok"])
            self.assertEqual(transport.head_calls, 6)

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


if __name__ == "__main__":
    unittest.main()
