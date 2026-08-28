from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wom_kit import archive_services
from wom_kit import duplicate_object_reconciliation as duplicate_module
from wom_kit import object_storage_adoption as adoption_module
from wom_kit.exact_human_approval import (
    _ClaimedExactHumanApproval,
    _audit_exact_human_approval_terminal_record_core,
    _claim_exact_human_approval_core,
)
from wom_kit.exact_human_approval_windows import (
    _ExactHumanApprovalDecision,
)
from wom_kit.exact_operation_manifest import (
    ExactOperationApprovalAuthority,
    FileExactOperationCheckpointStore,
    exact_operation_writer_lock,
    revert_exact_operation_fields,
)
from wom_kit.object_storage_adoption import (
    _ManifestIndexLifecycle,
    _apply_manifest_batch,
    ObjectStorageAdoptionError,
    _apply_with_store,
    _execution_adapters,
    plan_object_storage_formal_adoption,
)


KIT_ROOT = Path(__file__).resolve().parents[1]
APPROVAL_KEY = bytes(range(32))


class _MemoryHeadTransport:
    def __init__(self, objects: dict[str, int]) -> None:
        self.objects = dict(objects)
        self.head_calls = 0

    def head_object(self, *, key: str, presence_only: bool = False):
        del presence_only
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
        raise AssertionError("formal adoption must never PUT")


def _operation_authority() -> ExactOperationApprovalAuthority:
    return ExactOperationApprovalAuthority.from_reference(
        {
            "schema_version": "wom-kit/exact-human-approval-reference/v0.1",
            "approval_id": "approval_" + "a" * 32,
            "context_sha256": "sha256:" + "b" * 64,
            "approval_authority_sha256": "sha256:" + "c" * 64,
            "one_use": True,
        }
    )


class ManifestWriterIndexLifecycleTests(unittest.TestCase):
    def copy_archive(self, parent: Path) -> Path:
        root = parent / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", root)
        return root

    @staticmethod
    def manifest_path(root: Path) -> Path:
        return root / archive_services.ZETTEL_OBJET_LINK_MANIFEST_RELATIVE_PATH

    @staticmethod
    def valid_record(raw: bytes, *, label: str) -> dict[str, object]:
        digest = hashlib.sha256(raw).hexdigest()
        logical_key = f"objects/sha256/{digest[:2]}/{digest}"
        return {
            "object_id": "sha256:" + digest,
            "sha256": digest,
            "logical_key": logical_key,
            "mime": "application/octet-stream",
            "size_bytes": len(raw),
            "locations": [
                {
                    "provider": "local",
                    "path": logical_key,
                    "availability": "available",
                }
            ],
            "provenance": {
                "created_in": "archive:test",
                "source": label,
                "captured_at": "2026-08-28T00:00:00Z",
            },
        }

    @staticmethod
    def file_snapshot(root: Path) -> dict[str, str]:
        return {
            path.relative_to(root).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in root.rglob("*")
            if path.is_file()
        }

    def append_post_state(
        self,
        root: Path,
        record: dict[str, object],
    ) -> tuple[bytes, bytes, str, str]:
        manifest = self.manifest_path(root)
        before = manifest.read_bytes()
        after = archive_services._jsonl_records_post_bytes(before, [record])
        return (
            before,
            after,
            "sha256:" + hashlib.sha256(before).hexdigest(),
            "sha256:" + hashlib.sha256(after).hexdigest(),
        )

    @staticmethod
    def mutation_owner(label: str) -> str:
        binding = "sha256:" + hashlib.sha256(label.encode("ascii")).hexdigest()
        return archive_services.archive_manifest_mutation_owner_sha256(
            operation="v0412_manifest_test",
            operation_binding_sha256=binding,
        )

    def test_projection_success_and_interrupted_begin_resume_same_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_archive(Path(temporary))
            rebuilt = archive_services.index_archive(root)
            generation = str(rebuilt["index_generation"])
            record = self.valid_record(b"v0412-manifest-success", label="success")
            _before, after, pre_sha, post_sha = self.append_post_state(root, record)
            owner = self.mutation_owner("projection-success")

            first_generation, began, first_lease_token = (
                archive_services.prepare_archive_manifest_index_mutation(
                    root,
                    operation_owner_sha256=owner,
                    expected_pre_manifest_sha256=pre_sha,
                    expected_post_manifest_sha256=post_sha,
                )
            )
            self.assertTrue(began)
            self.assertEqual(first_generation, generation)
            self.assertIn(
                "archive_index_mutation_in_progress",
                archive_services.require_current_zettel_index(root)[
                    "reason_codes"
                ],
            )
            archive_services._release_archive_index_mutation_lease(
                root,
                lease_token=first_lease_token,
            )

            resumed_generation, began_again, resumed_lease_token = (
                archive_services.prepare_archive_manifest_index_mutation(
                    root,
                    operation_owner_sha256=owner,
                    expected_pre_manifest_sha256=pre_sha,
                    expected_post_manifest_sha256=post_sha,
                )
            )
            self.assertFalse(began_again)
            self.assertEqual(resumed_generation, generation)
            self.manifest_path(root).write_bytes(after)
            self.assertTrue(
                archive_services.replace_archive_index_manifest_projection(
                    root,
                    expected_generation=generation,
                    expected_manifest_sha256=post_sha,
                    expected_mutation_owner_sha256=owner,
                    lease_token=resumed_lease_token,
                )
            )
            evidence = archive_services.require_current_zettel_index(root)
            self.assertTrue(evidence["ok"], evidence)
            self.assertEqual(evidence["generation"], generation)

            connection = archive_services.connect_archive_index(
                root / archive_services.INDEX_RELATIVE_PATH,
                row_factory=True,
            )
            try:
                object_row = connection.execute(
                    "SELECT logical_key, manifest_json FROM objects WHERE object_id = ?",
                    (record["object_id"],),
                ).fetchone()
                projection_row = connection.execute(
                    "SELECT record_json FROM objet_manifest_projection "
                    "WHERE object_id = ?",
                    (record["object_id"],),
                ).fetchone()
            finally:
                connection.close()
            self.assertEqual(object_row["logical_key"], record["logical_key"])
            self.assertEqual(
                json.loads(object_row["manifest_json"]),
                record,
            )
            self.assertEqual(json.loads(projection_row["record_json"]), record)

    def test_read_only_noop_authority_never_begins(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_archive(Path(temporary))
            rebuilt = archive_services.index_archive(root)
            manifest_sha = archive_services.archive_index_stable_file_snapshot(
                root,
                self.manifest_path(root),
                max_bytes=archive_services.ZETTEL_OBJET_LINK_MANIFEST_MAX_BYTES,
            )["file_sha256"]
            owner = self.mutation_owner("read-only-noop")
            with patch.object(
                archive_services,
                "begin_archive_index_mutation",
                wraps=archive_services.begin_archive_index_mutation,
            ) as begin:
                authority = (
                    archive_services.require_archive_manifest_index_mutation_authority(
                        root,
                        operation_owner_sha256=owner,
                        expected_pre_manifest_sha256=manifest_sha,
                        expected_post_manifest_sha256=manifest_sha,
                    )
                )
            begin.assert_not_called()
            self.assertEqual(authority["state"], "current")
            self.assertEqual(
                authority["generation"],
                rebuilt["index_generation"],
            )

    def test_current_index_rejects_unindexed_valid_manifest_append(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_archive(Path(temporary))
            archive_services.index_archive(root)
            record = self.valid_record(
                b"v0412-unindexed-manifest-append",
                label="unindexed-append",
            )
            _before, after, _pre_sha, _post_sha = self.append_post_state(
                root,
                record,
            )
            self.manifest_path(root).write_bytes(after)

            evidence = archive_services.require_current_zettel_index(root)

            self.assertFalse(evidence["ok"], evidence)
            self.assertEqual(
                evidence["blockers"],
                [archive_services.INDEX_REBUILD_REQUIRED],
            )
            self.assertIn(
                "archive_index_manifest_changed",
                evidence["reason_codes"],
            )
            connection = archive_services.connect_archive_index(
                root / archive_services.INDEX_RELATIVE_PATH,
            )
            try:
                projected_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM objet_manifest_projection"
                    ).fetchone()[0]
                )
            finally:
                connection.close()
            live_count = sum(1 for line in after.splitlines() if line.strip())
            self.assertEqual(live_count, projected_count + 1)

    def test_current_index_rejects_same_byte_manifest_descriptor_replacement(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_archive(Path(temporary))
            archive_services.index_archive(root)
            manifest = self.manifest_path(root)
            before = archive_services.archive_index_stable_file_snapshot(
                root,
                manifest,
                max_bytes=archive_services.ZETTEL_OBJET_LINK_MANIFEST_MAX_BYTES,
            )
            replacement = manifest.with_name(manifest.name + ".replacement")
            replacement.write_bytes(before["raw"])
            os.replace(replacement, manifest)
            after = archive_services.archive_index_stable_file_snapshot(
                root,
                manifest,
                max_bytes=archive_services.ZETTEL_OBJET_LINK_MANIFEST_MAX_BYTES,
            )
            self.assertEqual(after["file_sha256"], before["file_sha256"])
            self.assertNotEqual(
                after["file_generation"],
                before["file_generation"],
            )

            evidence = archive_services.require_current_zettel_index(root)

            self.assertFalse(evidence["ok"], evidence)
            self.assertIn(
                "archive_index_manifest_changed",
                evidence["reason_codes"],
            )

    def test_current_authority_rejects_unindexed_expected_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_archive(Path(temporary))
            archive_services.index_archive(root)
            record = self.valid_record(
                b"v0412-current-authority-manifest-drift",
                label="current-authority-drift",
            )
            _before, after, _pre_sha, post_sha = self.append_post_state(
                root,
                record,
            )
            self.manifest_path(root).write_bytes(after)
            owner = self.mutation_owner("current-authority-drift")

            with self.assertRaisesRegex(
                archive_services.ArchiveServiceError,
                archive_services.INDEX_REBUILD_REQUIRED,
            ):
                archive_services.require_archive_manifest_index_mutation_authority(
                    root,
                    operation_owner_sha256=owner,
                    expected_pre_manifest_sha256=post_sha,
                    expected_post_manifest_sha256=post_sha,
                )

    def test_dirty_resume_requires_exact_owner_and_approved_manifest_state(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_archive(Path(temporary))
            archive_services.index_archive(root)
            record = self.valid_record(
                b"v0412-dirty-resume-approved-post",
                label="dirty-resume-approved",
            )
            _before, after, pre_sha, post_sha = self.append_post_state(root, record)
            owner = self.mutation_owner("dirty-resume-owner")
            _generation, began, lease_token = (
                archive_services.prepare_archive_manifest_index_mutation(
                    root,
                    operation_owner_sha256=owner,
                    expected_pre_manifest_sha256=pre_sha,
                    expected_post_manifest_sha256=post_sha,
                )
            )
            self.assertTrue(began)
            archive_services._release_archive_index_mutation_lease(
                root,
                lease_token=lease_token,
            )
            self.manifest_path(root).write_bytes(after)

            authority = (
                archive_services.require_archive_manifest_index_mutation_authority(
                    root,
                    operation_owner_sha256=owner,
                    expected_pre_manifest_sha256=pre_sha,
                    expected_post_manifest_sha256=post_sha,
                )
            )
            self.assertEqual(authority["state"], archive_services.INDEX_STATE_DIRTY)

            with self.assertRaisesRegex(
                archive_services.ArchiveServiceError,
                archive_services.INDEX_REBUILD_REQUIRED,
            ):
                archive_services.require_archive_manifest_index_mutation_authority(
                    root,
                    operation_owner_sha256=self.mutation_owner(
                        "dirty-resume-foreign-owner"
                    ),
                    expected_pre_manifest_sha256=pre_sha,
                    expected_post_manifest_sha256=post_sha,
                )

            unapproved = archive_services._jsonl_records_post_bytes(
                after,
                [
                    self.valid_record(
                        b"v0412-dirty-resume-unapproved-state",
                        label="dirty-resume-unapproved",
                    )
                ],
            )
            self.manifest_path(root).write_bytes(unapproved)
            with self.assertRaisesRegex(
                archive_services.ArchiveServiceError,
                archive_services.INDEX_REBUILD_REQUIRED,
            ):
                archive_services.require_archive_manifest_index_mutation_authority(
                    root,
                    operation_owner_sha256=owner,
                    expected_pre_manifest_sha256=pre_sha,
                    expected_post_manifest_sha256=post_sha,
                )

    def test_manifest_missing_or_replaced_during_delta_stays_dirty(self) -> None:
        for case in ("missing", "replaced"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_archive(Path(temporary))
                rebuilt = archive_services.index_archive(root)
                generation = str(rebuilt["index_generation"])
                record = self.valid_record(
                    ("manifest-" + case).encode("ascii"),
                    label=case,
                )
                _before, after, pre_sha, post_sha = self.append_post_state(
                    root,
                    record,
                )
                owner = self.mutation_owner("delta-drift-" + case)
                _started_generation, _began, lease_token = (
                    archive_services.prepare_archive_manifest_index_mutation(
                    root,
                    operation_owner_sha256=owner,
                    expected_pre_manifest_sha256=pre_sha,
                    expected_post_manifest_sha256=post_sha,
                    )
                )
                manifest = self.manifest_path(root)
                manifest.write_bytes(after)
                real_seal = archive_services.seal_archive_index_mutation

                def drift_then_seal(*args, **kwargs):
                    if case == "missing":
                        manifest.unlink()
                    else:
                        replacement = manifest.with_suffix(".replacement")
                        replacement.write_bytes(after)
                        os.replace(replacement, manifest)
                    return real_seal(*args, **kwargs)

                with patch.object(
                    archive_services,
                    "seal_archive_index_mutation",
                    side_effect=drift_then_seal,
                ):
                    updated = (
                        archive_services.replace_archive_index_manifest_projection(
                            root,
                            expected_generation=generation,
                            expected_manifest_sha256=post_sha,
                            expected_mutation_owner_sha256=owner,
                            lease_token=lease_token,
                        )
                    )
                self.assertFalse(updated)
                evidence = archive_services.require_current_zettel_index(root)
                self.assertFalse(evidence["ok"], evidence)
                self.assertIn("archive_index_dirty", evidence["reason_codes"])
                self.assertEqual(evidence["generation"], generation)

    def test_dirty_manifest_generation_is_exclusive_to_original_owner(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_archive(Path(temporary))
            generation = str(
                archive_services.index_archive(root)["index_generation"]
            )
            record = self.valid_record(
                b"v0412-owner-exclusive-manifest",
                label="owner-exclusive",
            )
            _before, after, pre_sha, post_sha = self.append_post_state(
                root,
                record,
            )
            original_owner = self.mutation_owner("original-owner")
            foreign_owner = self.mutation_owner("foreign-owner")

            started_generation, began, original_lease_token = (
                archive_services.prepare_archive_manifest_index_mutation(
                    root,
                    operation_owner_sha256=original_owner,
                    expected_pre_manifest_sha256=pre_sha,
                    expected_post_manifest_sha256=post_sha,
                )
            )
            self.assertTrue(began)
            self.assertEqual(started_generation, generation)

            with self.assertRaises(archive_services.ArchiveServiceError):
                archive_services.prepare_archive_manifest_index_mutation(
                    root,
                    operation_owner_sha256=foreign_owner,
                    expected_pre_manifest_sha256=pre_sha,
                    expected_post_manifest_sha256=post_sha,
                )

            archive_services._release_archive_index_mutation_lease(
                root,
                lease_token=original_lease_token,
            )
            resumed_generation, began_again, resumed_lease_token = (
                archive_services.prepare_archive_manifest_index_mutation(
                    root,
                    operation_owner_sha256=original_owner,
                    expected_pre_manifest_sha256=pre_sha,
                    expected_post_manifest_sha256=post_sha,
                )
            )
            self.assertFalse(began_again)
            self.assertEqual(resumed_generation, generation)

            self.manifest_path(root).write_bytes(after)
            self.assertFalse(
                archive_services.replace_archive_index_manifest_projection(
                    root,
                    expected_generation=generation,
                    expected_manifest_sha256=post_sha,
                    expected_mutation_owner_sha256=foreign_owner,
                )
            )
            dirty = archive_services.require_current_zettel_index(root)
            self.assertFalse(dirty["ok"], dirty)
            self.assertIsNone(dirty["generation"])
            self.assertIn(
                "archive_index_mutation_in_progress",
                dirty["reason_codes"],
            )
            conn = archive_services.connect_archive_index(
                root / archive_services.INDEX_RELATIVE_PATH,
                row_factory=True,
            )
            try:
                durable_dirty = archive_services.read_archive_index_metadata(
                    conn
                )
            finally:
                conn.close()
            self.assertEqual(
                durable_dirty.get("state"),
                archive_services.INDEX_STATE_DIRTY,
            )
            self.assertEqual(durable_dirty.get("generation"), generation)

            self.assertTrue(
                archive_services.replace_archive_index_manifest_projection(
                    root,
                    expected_generation=generation,
                    expected_manifest_sha256=post_sha,
                    expected_mutation_owner_sha256=original_owner,
                    lease_token=resumed_lease_token,
                )
            )
            current = archive_services.require_current_zettel_index(root)
            self.assertTrue(current["ok"], current)
            self.assertEqual(current["generation"], generation)

class ObjetCaptureManifestIndexLifecycleTests(ManifestWriterIndexLifecycleTests):
    def source_receipt(self, root: Path) -> str:
        relative = "receipts/sources/v0412.source-intake-plan.json"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "ok": True,
                    "dry_run": True,
                    "lifecycle_action": "source_intake_plan",
                    "blockers": [],
                    "content_access": dict(
                        archive_services.SOURCE_INTAKE_CONTENT_ACCESS_EXPECTATIONS
                    ),
                    "source_refs_for_draft": [],
                }
            ),
            encoding="utf-8",
        )
        return relative

    def selection(
        self,
        root: Path,
        *,
        label: str,
        paired: bool = False,
    ) -> dict[str, object]:
        staged = f"staging/incoming/{label}.pdf"
        source = root / staged
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"%PDF-1.4\n" + label.encode("utf-8") + b"\n")
        kwargs: dict[str, object] = {}
        if paired:
            derived = f"staging/incoming/{label}.txt"
            (root / derived).write_text(
                "paired derived text\n",
                encoding="utf-8",
            )
            kwargs = {
                "derived_text_staged_path": derived,
                "derivation_kind": "parser",
                "tool_name": "v0412-parser",
                "tool_version": "1.0.0",
                "review_status": "unreviewed",
                "language": "en",
                "born_digital": True,
            }
        planned = archive_services.objet_capture_selection_manifest(
            root,
            staged_path=staged,
            source_intake_receipt=self.source_receipt(root),
            item_id="item-" + label,
            dry_run=True,
            **kwargs,
        )
        self.assertTrue(planned["ok"], planned)
        return planned["selection_manifest"]

    def run_capture(
        self,
        root: Path,
        selection: dict[str, object],
    ) -> dict[str, object]:
        return archive_services._objet_capture_run(
            root,
            None,
            approve=True,
            reviewed_by="person:v0412",
            selection_document=selection,
            native_exact_authorized=True,
        )

    def test_capture_success_pair_and_current_noop_never_begin(self) -> None:
        for paired in (False, True):
            with self.subTest(paired=paired), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_archive(Path(temporary))
                rebuilt = archive_services.index_archive(root)
                generation = str(rebuilt["index_generation"])
                selection = self.selection(
                    root,
                    label="paired" if paired else "plain",
                    paired=paired,
                )
                index_path = root / archive_services.INDEX_RELATIVE_PATH
                index_before = hashlib.sha256(index_path.read_bytes()).hexdigest()
                result = self.run_capture(root, selection)
                if paired:
                    self.assertFalse(result["ok"], result)
                    self.assertIn(
                        "compound_exact_human_approval_binding_required",
                        result["blockers"],
                    )
                else:
                    self.assertTrue(result["ok"], result)
                self.assertTrue(result["generated_index_updated"])
                self.assertFalse(result["index_marked_dirty"])
                self.assertIn(
                    archive_services.INDEX_RELATIVE_PATH,
                    result["files_written"],
                )
                self.assertNotEqual(
                    hashlib.sha256(index_path.read_bytes()).hexdigest(),
                    index_before,
                )
                evidence = archive_services.require_current_zettel_index(root)
                self.assertTrue(evidence["ok"], evidence)
                self.assertEqual(evidence["generation"], generation)
                object_id = result["items"][0]["object_id"]
                connection = archive_services.connect_archive_index(
                    root / archive_services.INDEX_RELATIVE_PATH,
                    row_factory=True,
                )
                try:
                    count = connection.execute(
                        "SELECT COUNT(*) FROM objet_manifest_projection "
                        "WHERE object_id = ?",
                        (object_id,),
                    ).fetchone()[0]
                finally:
                    connection.close()
                self.assertEqual(count, 1)

                with patch.object(
                    archive_services,
                    "begin_archive_index_mutation",
                    wraps=archive_services.begin_archive_index_mutation,
                ) as begin:
                    replay_index_before = hashlib.sha256(
                        index_path.read_bytes()
                    ).hexdigest()
                    replay = self.run_capture(root, selection)
                if paired:
                    self.assertFalse(replay["ok"], replay)
                    self.assertIn(
                        "compound_exact_human_approval_binding_required",
                        replay["blockers"],
                    )
                else:
                    self.assertTrue(replay["ok"], replay)
                begin.assert_not_called()
                self.assertFalse(replay["generated_index_updated"])
                self.assertFalse(replay["index_marked_dirty"])
                self.assertNotIn(
                    archive_services.INDEX_RELATIVE_PATH,
                    replay["files_written"],
                )
                self.assertEqual(
                    hashlib.sha256(index_path.read_bytes()).hexdigest(),
                    replay_index_before,
                )

    def test_capture_delta_failure_is_partial_and_replay_repairs_dirty(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_archive(Path(temporary))
            rebuilt = archive_services.index_archive(root)
            generation = str(rebuilt["index_generation"])
            selection = self.selection(root, label="delta-failure")
            index_path = root / archive_services.INDEX_RELATIVE_PATH
            index_before = hashlib.sha256(index_path.read_bytes()).hexdigest()
            with patch.object(
                archive_services,
                "replace_archive_index_manifest_projection",
                return_value=False,
            ):
                failed = self.run_capture(root, selection)
            self.assertFalse(failed["ok"], failed)
            self.assertEqual(failed["status_class"], "partial")
            self.assertIn(
                archive_services.INDEX_REBUILD_REQUIRED,
                failed["blockers"],
            )
            self.assertFalse(failed["generated_index_updated"])
            self.assertTrue(failed["index_marked_dirty"])
            self.assertIn(
                archive_services.INDEX_RELATIVE_PATH,
                failed["files_written"],
            )
            self.assertNotEqual(
                hashlib.sha256(index_path.read_bytes()).hexdigest(),
                index_before,
            )
            dirty = archive_services.require_current_zettel_index(root)
            self.assertIn("archive_index_dirty", dirty["reason_codes"])
            self.assertEqual(dirty["generation"], generation)

            dirty_index_sha = hashlib.sha256(index_path.read_bytes()).hexdigest()
            recovered = self.run_capture(root, selection)
            self.assertTrue(recovered["ok"], recovered)
            self.assertTrue(recovered["generated_index_updated"])
            self.assertFalse(recovered["index_marked_dirty"])
            self.assertTrue(recovered["index_mutation_resumed"])
            self.assertIn(
                archive_services.INDEX_RELATIVE_PATH,
                recovered["files_written"],
            )
            self.assertNotEqual(
                hashlib.sha256(index_path.read_bytes()).hexdigest(),
                dirty_index_sha,
            )
            current = archive_services.require_current_zettel_index(root)
            self.assertTrue(current["ok"], current)
            self.assertEqual(current["generation"], generation)

    def test_capture_missing_or_stale_index_blocks_before_all_writer_outputs(self) -> None:
        for state in ("missing", "stale"):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_archive(Path(temporary))
                if state == "stale":
                    archive_services.index_archive(root)
                    stale = root / "inbox" / "unindexed.md"
                    stale.parent.mkdir(parents=True, exist_ok=True)
                    stale.write_text("unindexed\n", encoding="utf-8")
                selection = self.selection(root, label=state + "-index")
                before = self.file_snapshot(root)
                result = self.run_capture(root, selection)
                after = self.file_snapshot(root)
                self.assertFalse(result["ok"], result)
                self.assertEqual(
                    result["blockers"],
                    [archive_services.INDEX_REBUILD_REQUIRED],
                )
                self.assertEqual(result["files_written"], [])
                self.assertFalse(result["generated_index_updated"])
                self.assertFalse(result["index_marked_dirty"])
                self.assertEqual(after, before)


class FormalAdoptionManifestIndexLifecycleTests(
    ManifestWriterIndexLifecycleTests
):
    def adoption_root(self, parent: Path) -> Path:
        root = parent / "archive"
        (root / "objects" / "manifests").mkdir(parents=True)
        (root / "archive.yml").write_text(
            "archive_id: archive:test:object-storage-adoption\n",
            encoding="utf-8",
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
        receipt_relative = (
            archive_services.object_storage_provider_setup_receipt_path(
                "zettel-kasten-object-storage-adoption-objets"
            )
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
            timestamp="2026-08-28T00:00:00+09:00",
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

    def adoption_plan(self, parent: Path):
        root = self.adoption_root(parent)
        raw = b"v0412-formal-adoption"
        digest = hashlib.sha256(raw).hexdigest()
        row = {
            "object_id": "sha256:" + digest,
            "sha256": digest,
            "logical_key": f"objects/external/prehashed/r2/{digest[:2]}/{digest}",
            "mime": "application/octet-stream",
            "size_bytes": len(raw),
            "locations": [
                {
                    "provider": "object_storage",
                    "availability": "declared_uploaded",
                }
            ],
            "provenance": {
                "created_in": "archive:archive:test:object-storage-adoption",
                "source": "v0412-test",
                "captured_at": "2026-08-28T00:00:00Z",
            },
        }
        self.manifest_path(root).write_text(
            json.dumps(row, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        remote_key = f"custom/{digest}"
        key_map = parent / "key-map.jsonl"
        key_map.write_text(
            json.dumps(
                {"sha256": digest, "remote_key": remote_key},
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        plan = plan_object_storage_formal_adoption(
            root,
            key_map_path=key_map,
            store_ref="storage:account:test",
        )
        return root, plan, remote_key, len(raw)

    def test_precomputed_manifest_cas_rejects_stale_bytes_and_preserves_newer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root, plan, _remote_key, _size = self.adoption_plan(parent)
            archive_services.index_archive(root)
            for spec in plan.specs:
                adoption_module._create_receipt(plan, spec)

            manifest = self.manifest_path(root)
            original = manifest.read_bytes()
            newer_record = self.valid_record(
                b"v0412-concurrent-newer-manifest-row",
                label="concurrent-newer",
            )
            newer = original + (
                json.dumps(
                    newer_record,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")
            real_compare_and_swap = (
                archive_services._replace_regular_file_bytes_compare_and_swap
            )
            raced = False

            def install_newer_then_compare_and_swap(*args, **kwargs):
                nonlocal raced
                if not raced:
                    raced = True
                    manifest.write_bytes(newer)
                return real_compare_and_swap(*args, **kwargs)

            with patch.object(
                archive_services,
                "_replace_regular_file_bytes_compare_and_swap",
                side_effect=install_newer_then_compare_and_swap,
            ):
                with self.assertRaises(ObjectStorageAdoptionError) as raised:
                    _apply_manifest_batch(
                        plan,
                        destination_present=True,
                        lifecycle=_ManifestIndexLifecycle(),
                    )

            self.assertTrue(raced)
            self.assertEqual(
                raised.exception.code,
                archive_services.INDEX_REBUILD_REQUIRED,
            )
            self.assertEqual(manifest.read_bytes(), newer)

    def test_formal_adoption_success_noop_and_exact_revert_keep_same_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root, plan, remote_key, size = self.adoption_plan(parent)
            original = self.manifest_path(root).read_bytes()
            rebuilt = archive_services.index_archive(root)
            generation = str(rebuilt["index_generation"])
            transport = _MemoryHeadTransport({remote_key: size})
            with exact_operation_writer_lock(root) as lock:
                result = _apply_with_store(
                    plan,
                    _operation_authority(),
                    transport,
                    FileExactOperationCheckpointStore(root, writer_lock=lock),
                    resume=False,
                    progress_hook=None,
                )
            self.assertTrue(result["ok"], result)
            self.assertTrue(result["generated_index_updated"])
            self.assertEqual(result["index_generation"], generation)
            self.assertTrue(
                archive_services.require_current_zettel_index(root)["ok"]
            )

            with patch.object(
                archive_services,
                "begin_archive_index_mutation",
                wraps=archive_services.begin_archive_index_mutation,
            ) as begin:
                changed = _apply_manifest_batch(
                    plan,
                    destination_present=True,
                    lifecycle=_ManifestIndexLifecycle(),
                )
            self.assertEqual(changed, 0)
            begin.assert_not_called()

            with exact_operation_writer_lock(root) as lock:
                payloads, writer, verifier = _execution_adapters(
                    plan,
                    transport,
                )
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
                        root,
                        writer_lock=lock,
                    ),
                    approval_authority=_operation_authority(),
                )
            self.assertEqual(reverted["status"], "completed")
            self.assertEqual(self.manifest_path(root).read_bytes(), original)
            evidence = archive_services.require_current_zettel_index(root)
            self.assertTrue(evidence["ok"], evidence)
            self.assertEqual(evidence["generation"], generation)

    def test_formal_adoption_missing_or_stale_index_blocks_before_all_outputs(self) -> None:
        for state in ("missing", "stale"):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as temporary:
                parent = Path(temporary)
                root, plan, remote_key, size = self.adoption_plan(parent)
                if state == "stale":
                    archive_services.index_archive(root)
                    stale = root / "inbox" / "unindexed.md"
                    stale.parent.mkdir(parents=True, exist_ok=True)
                    stale.write_text("unindexed\n", encoding="utf-8")
                before = self.file_snapshot(root)
                with self.assertRaises(ObjectStorageAdoptionError) as raised:
                    _apply_with_store(
                        plan,
                        _operation_authority(),
                        _MemoryHeadTransport({remote_key: size}),
                        object(),
                        resume=False,
                        progress_hook=None,
                    )
                self.assertEqual(
                    raised.exception.code,
                    archive_services.INDEX_REBUILD_REQUIRED,
                )
                self.assertEqual(self.file_snapshot(root), before)

    def test_formal_adoption_delta_failure_resumes_same_dirty_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root, plan, remote_key, size = self.adoption_plan(parent)
            rebuilt = archive_services.index_archive(root)
            generation = str(rebuilt["index_generation"])
            transport = _MemoryHeadTransport({remote_key: size})
            with patch.object(
                archive_services,
                "replace_archive_index_manifest_projection",
                return_value=False,
            ):
                with exact_operation_writer_lock(root) as lock:
                    with self.assertRaises(Exception):
                        _apply_with_store(
                            plan,
                            _operation_authority(),
                            transport,
                            FileExactOperationCheckpointStore(
                                root,
                                writer_lock=lock,
                            ),
                            resume=False,
                            progress_hook=None,
                        )
            dirty = archive_services.require_current_zettel_index(root)
            self.assertIn("archive_index_dirty", dirty["reason_codes"])
            self.assertEqual(dirty["generation"], generation)

            with exact_operation_writer_lock(root) as lock:
                recovered = _apply_with_store(
                    plan,
                    _operation_authority(),
                    transport,
                    FileExactOperationCheckpointStore(
                        root,
                        writer_lock=lock,
                    ),
                    resume=True,
                    progress_hook=None,
                )
            self.assertTrue(recovered["ok"], recovered)
            self.assertTrue(recovered["generated_index_updated"])
            self.assertTrue(recovered["index_mutation_resumed"])
            evidence = archive_services.require_current_zettel_index(root)
            self.assertTrue(evidence["ok"], evidence)
            self.assertEqual(evidence["generation"], generation)


class DuplicateReconciliationManifestIndexLifecycleTests(
    ManifestWriterIndexLifecycleTests
):
    def duplicate_root(self, parent: Path) -> Path:
        root = parent / "archive"
        root.mkdir()
        (root / "archive.yml").write_text(
            "archive_id: archive:test:duplicate-v0412\n",
            encoding="utf-8",
        )
        self.manifest_path(root).parent.mkdir(parents=True)
        return root

    def duplicate_rows(self, root: Path) -> bytes:
        first = self.valid_record(b"duplicate-v0412", label="duplicate")
        other = self.valid_record(b"other-v0412", label="other")
        raw = b"".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
            + b"\n"
            for row in (first, first, other)
        )
        self.manifest_path(root).write_bytes(raw)
        return raw

    def claim(self, root: Path, context, *, seed: int) -> _ClaimedExactHumanApproval:
        decision = _ExactHumanApprovalDecision(
            approved=True,
            synthetic_acknowledged=False,
            reason_code="exact_human_approval_approved",
            plan_sha256=context.plan_sha256,
            target_binding_sha256=context.target_binding_sha256,
        )
        return _claim_exact_human_approval_core(
            root,
            context,
            decision,
            APPROVAL_KEY,
            random_hex=lambda _size: f"{seed:032x}",
        )

    @staticmethod
    def terminal_auditor(root: Path):
        def audit(
            reference,
            expected_operation,
            expected_plan_sha256,
            expected_target_binding_sha256,
            allowed_statuses,
            expected_succeeded_evidence,
            payload,
            expected_mac,
        ):
            return _audit_exact_human_approval_terminal_record_core(
                root,
                reference,
                expected_operation=expected_operation,
                expected_plan_sha256=expected_plan_sha256,
                expected_target_binding_sha256=(
                    expected_target_binding_sha256
                ),
                allowed_statuses=allowed_statuses,
                expected_succeeded_evidence_digests=(
                    expected_succeeded_evidence
                ),
                payload=payload,
                expected_mac=expected_mac,
                receipt_authentication_key=memoryview(APPROVAL_KEY),
            )

        return audit

    def test_duplicate_forward_and_exact_revert_keep_projection_current(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.duplicate_root(Path(temporary))
            original = self.duplicate_rows(root)
            rebuilt = archive_services.index_archive(root)
            generation = str(rebuilt["index_generation"])
            plan = duplicate_module._plan_duplicate_object_reconciliation_core(
                root
            )
            context = duplicate_module._duplicate_object_reconciliation_context(
                plan,
                reviewer_claim="person:v0412",
            )
            claim = self.claim(root, context, seed=1)
            try:
                result = (
                    duplicate_module._apply_duplicate_object_reconciliation_core(
                        plan,
                        claim,
                        context=context,
                    )
                )
                self.assertTrue(result["ok"], result)
                self.assertTrue(result["generated_index_updated"])
                self.assertEqual(result["index_generation"], generation)
                self.assertTrue(
                    archive_services.require_current_zettel_index(root)["ok"]
                )
                claim.finalize_succeeded()
            finally:
                claim.close()

            revert_plan = (
                duplicate_module._plan_duplicate_object_reconciliation_revert_core(
                    root,
                    terminal_auditor=self.terminal_auditor(root),
                )
            )
            revert_context = (
                duplicate_module._duplicate_object_reconciliation_revert_context(
                    revert_plan,
                    reviewer_claim="person:v0412",
                )
            )
            revert_claim = self.claim(root, revert_context, seed=2)
            try:
                reverted = (
                    duplicate_module._apply_duplicate_object_reconciliation_revert_core(
                        revert_plan,
                        revert_claim,
                        context=revert_context,
                    )
                )
                self.assertTrue(reverted["ok"], reverted)
                self.assertTrue(reverted["generated_index_updated"])
                revert_claim.finalize_succeeded()
                duplicate_module._finalize_duplicate_object_reconciliation_revert_core(
                    revert_plan,
                    revert_claim,
                    context=revert_context,
                )
            finally:
                revert_claim.close()
            self.assertEqual(self.manifest_path(root).read_bytes(), original)
            evidence = archive_services.require_current_zettel_index(root)
            self.assertTrue(evidence["ok"], evidence)
            self.assertEqual(evidence["generation"], generation)

    def test_duplicate_missing_or_stale_index_has_zero_writer_changes(self) -> None:
        for state in ("missing", "stale"):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as temporary:
                root = self.duplicate_root(Path(temporary))
                self.duplicate_rows(root)
                if state == "stale":
                    archive_services.index_archive(root)
                    stale = root / "inbox" / "unindexed.md"
                    stale.parent.mkdir(parents=True, exist_ok=True)
                    stale.write_text("unindexed\n", encoding="utf-8")
                plan = duplicate_module._plan_duplicate_object_reconciliation_core(
                    root
                )
                context = (
                    duplicate_module._duplicate_object_reconciliation_context(
                        plan,
                        reviewer_claim="person:v0412",
                    )
                )
                claim = self.claim(root, context, seed=3 if state == "missing" else 4)
                try:
                    before = self.file_snapshot(root)
                    with self.assertRaises(
                        duplicate_module.DuplicateObjectReconciliationError
                    ) as raised:
                        duplicate_module._apply_duplicate_object_reconciliation_core(
                            plan,
                            claim,
                            context=context,
                        )
                    self.assertEqual(
                        raised.exception.code,
                        archive_services.INDEX_REBUILD_REQUIRED,
                    )
                    self.assertEqual(self.file_snapshot(root), before)
                finally:
                    claim.close()


if __name__ == "__main__":
    unittest.main()
