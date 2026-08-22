from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from wom_kit.object_storage_adoption import (
    ObjectStorageAdoptionError,
    plan_object_storage_formal_adoption,
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


if __name__ == "__main__":
    unittest.main()
