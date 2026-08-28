from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from wom_kit import archive_services, completion_workflows


KIT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = KIT_ROOT / "examples" / "fake-life-archive"
ZETTEL_ID = "zet_20240504_fake_lunch_thought"
DRAFT_ZETTEL_ID = "zet_20260519_draft_ai_lunch_note"
OBJECT_ID = (
    "sha256:"
    "9dabf9b965a3f789b1b36100f3f70515ce8dfd81b411b1503e1e2c3304303647"
)


class V0412ArchiveIndexProjectionTests(unittest.TestCase):
    def tearDown(self) -> None:
        archive_services._close_all_zettel_objet_link_projection_sessions()

    def archive(self, parent: Path) -> Path:
        root = parent / "archive"
        shutil.copytree(FIXTURE, root)
        return root

    def test_rebuild_binds_strong_zettel_generation_and_duplicate_ordinals(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            manifest_path = root / "objects" / "manifests" / "files.jsonl"
            records = [
                line
                for line in manifest_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            manifest_path.write_text(
                "\n".join([*records, records[1]]) + "\n",
                encoding="utf-8",
            )

            rebuilt = archive_services.index_archive(root)
            self.assertTrue(rebuilt["ok"], rebuilt)
            projection = archive_services.build_zettel_objet_link_authority_projection(
                root
            )
            self.assertTrue(projection["ok"], projection)
            lookup = archive_services.lookup_zettel_objet_link_authority_projection(
                root,
                projection,
                zettel_id=ZETTEL_ID,
                object_id=OBJECT_ID,
            )
            self.assertTrue(lookup["ok"], lookup)
            self.assertEqual(len(lookup["manifest_records"]), 2)

            conn = archive_services.connect_archive_index(
                root / archive_services.INDEX_RELATIVE_PATH,
                row_factory=True,
            )
            try:
                rows = conn.execute(
                    "SELECT record_ordinal FROM objet_manifest_projection "
                    "ORDER BY record_ordinal"
                ).fetchall()
                zettel = conn.execute(
                    "SELECT file_sha256, file_dev, file_ino, file_ctime_ns, "
                    "file_size, file_mtime_ns FROM zettels WHERE zettel_id = ?",
                    (ZETTEL_ID,),
                ).fetchone()
                metadata = archive_services.read_archive_index_metadata(conn)
            finally:
                conn.close()
            self.assertEqual([row["record_ordinal"] for row in rows], [1, 2, 3])
            self.assertRegex(str(zettel["file_sha256"]), r"^sha256:[0-9a-f]{64}$")
            for field in (
                "file_dev",
                "file_ino",
                "file_ctime_ns",
                "file_size",
                "file_mtime_ns",
            ):
                self.assertGreaterEqual(int(zettel[field]), 0)
            self.assertNotIn(
                archive_services.INDEX_SEAL_PENDING_KEY,
                metadata,
            )
            self.assertNotIn(
                archive_services.INDEX_MUTATION_OWNER_KEY,
                metadata,
            )

    def test_committed_pending_seal_blocks_public_health_after_crash_gap(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            generation = str(
                archive_services.index_archive(root)["index_generation"]
            )
            lease_token = archive_services.begin_archive_index_mutation(
                root,
                expected_generation=generation,
            )
            fence = archive_services._ArchiveIndexAuthorityFence(root)
            conn = archive_services.connect_archive_index(
                root / archive_services.INDEX_RELATIVE_PATH,
                write=True,
                row_factory=True,
            )
            try:
                conn.execute("BEGIN IMMEDIATE")
                archive_services.seal_archive_index_mutation(
                    root,
                    conn,
                    expected_generation=generation,
                    _authority_fence=fence,
                )
                conn.commit()
            finally:
                conn.close()
                fence.close()
                archive_services._release_archive_index_mutation_lease(
                    root,
                    lease_token=lease_token,
                )

            evidence = archive_services.require_current_zettel_index(root)
            self.assertFalse(evidence["ok"], evidence)
            self.assertIn(
                "archive_index_mutation_in_progress",
                evidence["reason_codes"],
            )
            proof = archive_services.connect_archive_index(
                root / archive_services.INDEX_RELATIVE_PATH,
                row_factory=True,
            )
            try:
                metadata = archive_services.read_archive_index_metadata(proof)
            finally:
                proof.close()
            self.assertEqual(
                metadata.get("state"),
                archive_services.INDEX_STATE_CURRENT,
            )
            self.assertEqual(metadata.get("generation"), generation)
            self.assertRegex(
                str(
                    metadata.get(
                        archive_services.INDEX_SEAL_PENDING_KEY
                    )
                ),
                r"^seal:[0-9a-f]{32}$",
            )

    def test_postcommit_watcher_failure_restores_same_generation_dirty(
        self,
    ) -> None:
        class ChangedFence:
            def __init__(self, _root: Path) -> None:
                self.closed = False

            def arm_closing_guard(self) -> None:
                return None

            def verify_clean(self) -> None:
                raise OSError("synthetic_source_change")

            def close(self) -> None:
                self.closed = True

        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            generation = str(
                archive_services.index_archive(root)["index_generation"]
            )
            lease_token = archive_services.begin_archive_index_mutation(
                root,
                expected_generation=generation,
            )
            with patch.object(
                archive_services,
                "_ArchiveIndexAuthorityFence",
                ChangedFence,
            ):
                sealed = (
                    archive_services.reseal_archive_index_mutation_without_delta(
                        root,
                        expected_generation=generation,
                        lease_token=lease_token,
                    )
                )
            self.assertFalse(sealed)
            proof = archive_services.connect_archive_index(
                root / archive_services.INDEX_RELATIVE_PATH,
                row_factory=True,
            )
            try:
                metadata = archive_services.read_archive_index_metadata(proof)
            finally:
                proof.close()
            self.assertEqual(
                metadata.get("state"),
                archive_services.INDEX_STATE_DIRTY,
            )
            self.assertEqual(metadata.get("generation"), generation)
            self.assertNotIn(
                archive_services.INDEX_SEAL_PENDING_KEY,
                metadata,
            )

    def test_publication_uncertainty_retains_exact_recovery_lease(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            generation = str(
                archive_services.index_archive(root)["index_generation"]
            )
            lease_token = archive_services.begin_archive_index_mutation(
                root,
                expected_generation=generation,
            )
            try:
                with (
                    patch.object(
                        archive_services,
                        "_publish_archive_index_completed_seal",
                        return_value=False,
                    ),
                    patch.object(
                        archive_services,
                        "_restore_archive_index_dirty_after_failed_seal",
                        return_value=False,
                    ),
                    self.assertRaises(
                        archive_services._ArchiveIndexDirtyRestoreUncertainError
                    ),
                ):
                    archive_services.reseal_archive_index_mutation_without_delta(
                        root,
                        expected_generation=generation,
                        lease_token=lease_token,
                    )
                archive_services._require_archive_index_mutation_lease(
                    root,
                    expected_generation=generation,
                    lease_token=lease_token,
                )
                self.assertTrue(
                    archive_services._ensure_archive_index_dirty_with_retained_lease(
                        root,
                        expected_generation=generation,
                        lease_token=lease_token,
                    )
                )
            finally:
                archive_services._release_archive_index_mutation_lease(
                    root,
                    lease_token=lease_token,
                )

    def test_pending_publication_rejects_foreign_owner_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            generation = str(
                archive_services.index_archive(root)["index_generation"]
            )
            original_owner = "sha256:" + "5" * 64
            foreign_owner = "sha256:" + "6" * 64
            lease_token = archive_services.begin_archive_index_mutation(
                root,
                expected_generation=generation,
                mutation_owner_sha256=original_owner,
            )
            try:
                fence = archive_services._ArchiveIndexAuthorityFence(root)
                conn = archive_services.connect_archive_index(
                    root / archive_services.INDEX_RELATIVE_PATH,
                    write=True,
                    row_factory=True,
                )
                try:
                    conn.execute("BEGIN IMMEDIATE")
                    archive_services.seal_archive_index_mutation(
                        root,
                        conn,
                        expected_generation=generation,
                        _authority_fence=fence,
                    )
                    conn.commit()
                    pending = archive_services.read_archive_index_metadata(
                        conn
                    )[archive_services.INDEX_SEAL_PENDING_KEY]
                finally:
                    conn.close()
                    fence.close()
                tamper = archive_services.connect_archive_index(
                    root / archive_services.INDEX_RELATIVE_PATH,
                    write=True,
                )
                try:
                    tamper.execute(
                        "UPDATE index_metadata SET value = ? WHERE key = ?",
                        (
                            foreign_owner,
                            archive_services.INDEX_MUTATION_OWNER_KEY,
                        ),
                    )
                    tamper.commit()
                finally:
                    tamper.close()
                publish = archive_services.connect_archive_index(
                    root / archive_services.INDEX_RELATIVE_PATH,
                    write=True,
                    row_factory=True,
                )
                try:
                    self.assertFalse(
                        archive_services._publish_archive_index_completed_seal(
                            publish,
                            expected_generation=generation,
                            expected_seal_pending=str(pending),
                            expected_mutation_owner_sha256=original_owner,
                        )
                    )
                    metadata = archive_services.read_archive_index_metadata(
                        publish
                    )
                finally:
                    publish.close()
                self.assertEqual(
                    metadata.get(archive_services.INDEX_MUTATION_OWNER_KEY),
                    foreign_owner,
                )
                self.assertEqual(
                    metadata.get(archive_services.INDEX_SEAL_PENDING_KEY),
                    pending,
                )
                self.assertTrue(
                    archive_services._ensure_archive_index_dirty_with_retained_lease(
                        root,
                        expected_generation=generation,
                        lease_token=lease_token,
                    )
                )
            finally:
                archive_services._release_archive_index_mutation_lease(
                    root,
                    lease_token=lease_token,
                )

    def test_invalid_or_mismatched_internal_marker_allows_fail_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            archive_services.index_archive(root)
            conn = archive_services.connect_archive_index(
                root / archive_services.INDEX_RELATIVE_PATH,
                write=True,
            )
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO index_metadata(key, value) "
                    "VALUES (?, ?)",
                    (archive_services.INDEX_SEAL_PENDING_KEY, "invalid"),
                )
                conn.execute(
                    "INSERT OR REPLACE INTO index_metadata(key, value) "
                    "VALUES (?, ?)",
                    (archive_services.INDEX_MUTATION_OWNER_KEY, "invalid"),
                )
                conn.commit()
            finally:
                conn.close()
            invalid = archive_services.require_current_zettel_index(
                root,
                _allow_seal_pending="invalid",
                _allow_mutation_owner="invalid",
            )
            self.assertFalse(invalid["ok"], invalid)
            self.assertIn(
                "archive_index_mutation_in_progress",
                invalid["reason_codes"],
            )
            stored_pending = "seal:" + "1" * 32
            allowed_pending = "seal:" + "2" * 32
            stored_owner = "sha256:" + "3" * 64
            allowed_owner = "sha256:" + "4" * 64
            conn = archive_services.connect_archive_index(
                root / archive_services.INDEX_RELATIVE_PATH,
                write=True,
            )
            try:
                conn.execute(
                    "UPDATE index_metadata SET value = ? WHERE key = ?",
                    (stored_pending, archive_services.INDEX_SEAL_PENDING_KEY),
                )
                conn.execute(
                    "UPDATE index_metadata SET value = ? WHERE key = ?",
                    (stored_owner, archive_services.INDEX_MUTATION_OWNER_KEY),
                )
                conn.commit()
            finally:
                conn.close()
            mismatched = archive_services.require_current_zettel_index(
                root,
                _allow_seal_pending=allowed_pending,
                _allow_mutation_owner=allowed_owner,
            )
            self.assertFalse(mismatched["ok"], mismatched)
            self.assertIn(
                "archive_index_mutation_in_progress",
                mismatched["reason_codes"],
            )

    def test_old_metadata_generation_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            archive_services.index_archive(root)
            conn = archive_services.connect_archive_index(
                root / archive_services.INDEX_RELATIVE_PATH,
                write=True,
            )
            try:
                conn.execute(
                    "UPDATE index_metadata SET value = ? WHERE key = 'schema'",
                    ("wom-kit/archive-index-metadata/v0.3",),
                )
                conn.commit()
            finally:
                conn.close()
            current = archive_services.require_current_zettel_index(root)
            self.assertFalse(current["ok"], current)
            self.assertIn(
                "archive_index_metadata_schema_mismatch",
                current["reason_codes"],
            )
            projection = archive_services.build_zettel_objet_link_authority_projection(
                root
            )
            self.assertEqual(
                projection["reason_codes"],
                ["zettel_identity_projection_stale"],
            )

    def test_manifest_projection_row_must_be_exact_member_of_hashed_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            archive_services.index_archive(root)
            projection = archive_services.build_zettel_objet_link_authority_projection(
                root
            )
            self.assertTrue(projection["ok"], projection)
            conn = archive_services.connect_archive_index(
                root / archive_services.INDEX_RELATIVE_PATH,
                write=True,
                row_factory=True,
            )
            try:
                row = conn.execute(
                    "SELECT record_ordinal, record_json FROM "
                    "objet_manifest_projection WHERE object_id = ? LIMIT 1",
                    (OBJECT_ID,),
                ).fetchone()
                forged = json.loads(str(row["record_json"]))
                forged["logical_key"] = "objects/forged-but-hash-consistent.bin"
                forged_json = json.dumps(
                    forged,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                forged_sha = "sha256:" + hashlib.sha256(
                    (forged_json + "\n").encode("utf-8")
                ).hexdigest()
                conn.execute(
                    "UPDATE objet_manifest_projection SET record_json = ?, "
                    "record_sha256 = ? WHERE record_ordinal = ?",
                    (forged_json, forged_sha, int(row["record_ordinal"])),
                )
                conn.commit()
            finally:
                conn.close()

            lookup = archive_services.lookup_zettel_objet_link_authority_projection(
                root,
                projection,
                zettel_id=ZETTEL_ID,
                object_id=OBJECT_ID,
            )
            self.assertFalse(lookup["ok"], lookup)
            self.assertEqual(
                lookup["reason_codes"],
                ["zettel_identity_projection_stale"],
            )

    def test_zettel_row_tamper_invalidates_identity_projection_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            archive_services.index_archive(root)
            conn = archive_services.connect_archive_index(
                root / archive_services.INDEX_RELATIVE_PATH,
                write=True,
            )
            try:
                conn.execute(
                    "UPDATE zettels SET zettel_id = ? WHERE zettel_id = ?",
                    ("zet_20990101_forged_identity", ZETTEL_ID),
                )
                conn.commit()
            finally:
                conn.close()
            evidence = archive_services.require_current_zettel_index(root)
            self.assertFalse(evidence["ok"], evidence)
            self.assertIn(
                "archive_index_zettel_identity_projection_mismatch",
                evidence["reason_codes"],
            )

    def test_stable_snapshot_rejects_symlinked_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            parent = Path(temp_dir)
            root = self.archive(parent)
            external = parent / "external"
            external.mkdir()
            (external / "manifest.jsonl").write_text("{}\n", encoding="utf-8")
            linked_parent = root / "linked-parent"
            try:
                linked_parent.symlink_to(external, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlink unavailable: {exc}")
            with self.assertRaisesRegex(
                OSError,
                "archive_index_projection_file_unsafe",
            ):
                archive_services.archive_index_stable_file_snapshot(
                    root,
                    linked_parent / "manifest.jsonl",
                    max_bytes=1024,
                )

    def test_rebuild_rejects_zettel_change_at_final_commit_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            target = sorted((root / "zettels").glob("*.md"))[0]
            original_replace = archive_services.replace_archive_index_metadata
            changed = False

            def replace_then_change(*args, **kwargs):
                nonlocal changed
                result = original_replace(*args, **kwargs)
                if not changed:
                    target.write_bytes(target.read_bytes() + b"\n")
                    changed = True
                return result

            with patch.object(
                archive_services,
                "replace_archive_index_metadata",
                side_effect=replace_then_change,
            ):
                with self.assertRaisesRegex(
                    archive_services.ArchiveServiceError,
                    "(archive_index_source_changed_during_rebuild|"
                    "private_objet_metadata_rebuild_failed)",
            ):
                    archive_services.index_archive(root)
            self.assertTrue(changed)
            try:
                evidence = archive_services.require_current_zettel_index(root)
            except (
                archive_services.ArchiveIndexReadBoundaryError,
                archive_services.ArchiveServiceError,
            ):
                evidence = {"ok": False}
            self.assertFalse(evidence["ok"])

    def test_rebuild_rejects_change_after_private_commit_returns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            target = sorted((root / "zettels").glob("*.md"))[0]
            real_factory = (
                archive_services._private_objet_index_rebuild_session
            )
            committed_generation: str | None = None
            changed = False

            def factory(*args, **kwargs):
                session = real_factory(*args, **kwargs)
                real_validate = session.validate_and_commit

                def validate_then_change():
                    nonlocal committed_generation, changed
                    result = real_validate()
                    proof = archive_services.connect_archive_index(
                        root / archive_services.INDEX_RELATIVE_PATH,
                        row_factory=True,
                    )
                    try:
                        metadata = (
                            archive_services.read_archive_index_metadata(proof)
                        )
                    finally:
                        proof.close()
                    committed_generation = str(
                        metadata.get("generation") or ""
                    )
                    with target.open("ab") as handle:
                        handle.write(b"\n")
                        handle.flush()
                        os.fsync(handle.fileno())
                    changed = True
                    return result

                session.validate_and_commit = validate_then_change
                return session

            with patch.object(
                archive_services,
                "_private_objet_index_rebuild_session",
                side_effect=factory,
            ):
                with self.assertRaisesRegex(
                    archive_services.ArchiveServiceError,
                    archive_services.INDEX_REBUILD_REQUIRED,
                ):
                    archive_services.index_archive(root)

            self.assertTrue(changed)
            self.assertRegex(
                str(committed_generation),
                r"^gen:[0-9a-f]{32}$",
            )
            proof = archive_services.connect_archive_index(
                root / archive_services.INDEX_RELATIVE_PATH,
                row_factory=True,
            )
            try:
                metadata = archive_services.read_archive_index_metadata(proof)
            finally:
                proof.close()
            self.assertEqual(
                metadata.get("state"),
                archive_services.INDEX_STATE_DIRTY,
            )
            self.assertEqual(
                metadata.get("generation"),
                committed_generation,
            )
            self.assertNotIn(
                archive_services.INDEX_SEAL_PENDING_KEY,
                metadata,
            )
            evidence = archive_services.require_current_zettel_index(root)
            self.assertFalse(evidence["ok"], evidence)

    def test_lookup_rejects_late_nonselected_zettel_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            archive_services.index_archive(root)
            projection = archive_services.build_zettel_objet_link_authority_projection(
                root
            )
            selected = root / "zettels" / f"{ZETTEL_ID}.md"
            unrelated = next(
                path
                for path in sorted((root / "zettels").glob("*.md"))
                if path != selected
            )
            original_records = (
                archive_services._archive_index_manifest_records_at_ordinals
            )
            changed = False

            def records_then_change(*args, **kwargs):
                nonlocal changed
                result = original_records(*args, **kwargs)
                if not changed:
                    unrelated.write_bytes(unrelated.read_bytes() + b"\n")
                    changed = True
                return result

            with patch.object(
                archive_services,
                "_archive_index_manifest_records_at_ordinals",
                side_effect=records_then_change,
            ):
                lookup = (
                    archive_services.lookup_zettel_objet_link_authority_projection(
                        root,
                        projection,
                        zettel_id=ZETTEL_ID,
                        object_id=OBJECT_ID,
                    )
                )
            self.assertTrue(changed)
            self.assertFalse(lookup["ok"], lookup)
            self.assertEqual(
                lookup["reason_codes"],
                ["zettel_tree_changed_during_plan"],
            )

    def test_warm_lookup_uses_session_without_full_zettel_tree_scan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            archive_services.index_archive(root)
            projection = archive_services.build_zettel_objet_link_authority_projection(
                root
            )
            self.assertTrue(projection["ok"], projection)

            with patch.object(
                archive_services,
                "strict_live_zettel_stat_snapshot",
                side_effect=AssertionError("warm lookup rescanned the Zet tree"),
            ):
                lookup = (
                    archive_services.lookup_zettel_objet_link_authority_projection(
                        root,
                        dict(projection),
                        zettel_id=ZETTEL_ID,
                        object_id=OBJECT_ID,
                    )
                )

            self.assertTrue(lookup["ok"], lookup)

    def test_warm_lookup_rejects_out_of_band_index_status_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            archive_services.index_archive(root)
            projection = archive_services.build_zettel_objet_link_authority_projection(
                root
            )
            self.assertTrue(projection["ok"], projection)

            conn = archive_services.connect_archive_index(
                root / archive_services.INDEX_RELATIVE_PATH,
                write=True,
            )
            try:
                conn.execute(
                    "UPDATE zettels SET status = 'review' "
                    "WHERE status = 'draft' AND zettel_id <> ?",
                    (ZETTEL_ID,),
                )
                self.assertEqual(conn.execute("SELECT changes()").fetchone()[0], 1)
                conn.commit()
            finally:
                conn.close()

            lookup = archive_services.lookup_zettel_objet_link_authority_projection(
                root,
                projection,
                zettel_id=ZETTEL_ID,
                object_id=OBJECT_ID,
            )

            self.assertFalse(lookup["ok"], lookup)
            self.assertEqual(
                lookup["reason_codes"],
                ["zettel_identity_projection_stale"],
            )

    def test_slow_lookup_binds_selected_status_to_zettel_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            archive_services.index_archive(root)
            projection = archive_services.build_zettel_objet_link_authority_projection(
                root
            )
            self.assertTrue(projection["ok"], projection)
            archive_services._close_all_zettel_objet_link_projection_sessions()

            conn = archive_services.connect_archive_index(
                root / archive_services.INDEX_RELATIVE_PATH,
                write=True,
            )
            try:
                conn.execute(
                    "UPDATE zettels SET status = 'review' WHERE zettel_id = ?",
                    (DRAFT_ZETTEL_ID,),
                )
                self.assertEqual(conn.execute("SELECT changes()").fetchone()[0], 1)
                conn.commit()
            finally:
                conn.close()

            lookup = archive_services.lookup_zettel_objet_link_authority_projection(
                root,
                dict(projection),
                zettel_id=DRAFT_ZETTEL_ID,
                object_id=OBJECT_ID,
            )

            self.assertFalse(lookup["ok"], lookup)
            self.assertEqual(
                lookup["reason_codes"],
                ["zettel_tree_changed_during_plan"],
            )

    def test_projection_watcher_is_armed_before_database_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            archive_services.index_archive(root)
            original_init = archive_services._ZettelObjetLinkProjectionWatcher.__init__
            changed = False

            def init_then_change_database(watcher, watched_root):
                nonlocal changed
                original_init(watcher, watched_root)
                conn = archive_services.connect_archive_index(
                    root / archive_services.INDEX_RELATIVE_PATH,
                    write=True,
                )
                try:
                    conn.execute(
                        "UPDATE zettels SET status = 'review' "
                        "WHERE status = 'draft' AND zettel_id <> ?",
                        (ZETTEL_ID,),
                    )
                    self.assertEqual(
                        conn.execute("SELECT changes()").fetchone()[0],
                        1,
                    )
                    conn.commit()
                finally:
                    conn.close()
                changed = True

            with patch.object(
                archive_services._ZettelObjetLinkProjectionWatcher,
                "__init__",
                new=init_then_change_database,
            ):
                projection = (
                    archive_services.build_zettel_objet_link_authority_projection(
                        root
                    )
                )

            self.assertTrue(changed)
            self.assertFalse(projection["ok"], projection)
            self.assertEqual(
                projection["reason_codes"],
                ["zettel_identity_projection_stale"],
            )

    def test_foreign_pid_session_cleanup_never_acquires_inherited_lock(self) -> None:
        class PoisonedInheritedLock:
            def __enter__(self):
                raise AssertionError("inherited projection lock was acquired")

            def __exit__(self, exc_type, exc, traceback):
                return False

        watcher = Mock()
        session = archive_services._ZettelObjetLinkProjectionSession(
            key=("synthetic-root", "synthetic-digest"),
            watcher=watcher,
            pid=os.getpid() + 1,
            created_monotonic=0.0,
            last_used_monotonic=0.0,
            lock=PoisonedInheritedLock(),
        )

        archive_services._close_zettel_objet_link_projection_sessions([session])

        watcher.close.assert_called_once_with()

    def test_after_fork_reset_replaces_poisoned_global_guard(self) -> None:
        class PoisonedInheritedGuard:
            def __enter__(self):
                raise AssertionError("inherited registry guard was acquired")

            def __exit__(self, exc_type, exc, traceback):
                return False

        watcher = Mock()
        session = archive_services._ZettelObjetLinkProjectionSession(
            key=("synthetic-root", "synthetic-digest"),
            watcher=watcher,
            pid=os.getpid() - 1,
            created_monotonic=0.0,
            last_used_monotonic=0.0,
            lock=PoisonedInheritedGuard(),
        )
        poisoned = PoisonedInheritedGuard()
        archive_services._ZETTEL_OBJET_LINK_PROJECTION_SESSIONS[session.key] = (
            session
        )
        archive_services._ZETTEL_OBJET_LINK_PROJECTION_SESSION_GUARD = poisoned

        archive_services._reset_zettel_objet_link_projection_sessions_after_fork()

        self.assertEqual(
            archive_services._ZETTEL_OBJET_LINK_PROJECTION_SESSIONS,
            {},
        )
        self.assertIsNot(
            archive_services._ZETTEL_OBJET_LINK_PROJECTION_SESSION_GUARD,
            poisoned,
        )
        with archive_services._ZETTEL_OBJET_LINK_PROJECTION_SESSION_GUARD:
            pass
        watcher.close.assert_called_once_with()

    def test_linux_session_watcher_filters_only_index_authority_files(self) -> None:
        watcher = object.__new__(archive_services._ArchiveIndexLinuxInotifyWatcher)
        watcher._include_database = True

        self.assertTrue(
            watcher._event_is_relevant(
                "archive-root",
                archive_services._ArchiveIndexLinuxInotifyWatcher._IN_MOVED_TO,
                "db",
            )
        )
        for name in (
            "archive-index.sqlite",
            "archive-index.sqlite-journal",
            "archive-index.sqlite-wal",
        ):
            with self.subTest(name=name):
                self.assertTrue(
                    watcher._event_is_relevant(
                        "database-parent",
                        archive_services._ArchiveIndexLinuxInotifyWatcher._IN_MODIFY,
                        name,
                    )
                )
        self.assertFalse(
            watcher._event_is_relevant(
                "database-parent",
                archive_services._ArchiveIndexLinuxInotifyWatcher._IN_CREATE,
                "archive-index.sqlite-shm",
            )
        )

    @unittest.skipUnless(os.name == "nt", "Windows watcher checkpoint contract")
    def test_windows_watcher_poll_keeps_pending_request_armed(self) -> None:
        watcher = object.__new__(
            completion_workflows._ZettelObjetLinkWindowsDirectoryWatcher
        )
        watcher._active = True
        watcher._verified = False
        watcher._handle = 123
        watcher._overlapped = object()
        watcher._ctypes = Mock()
        watcher._ctypes.byref.side_effect = lambda value: value
        watcher._ctypes.get_last_error.return_value = 996
        watcher._get_result = Mock(return_value=False)
        watcher._cancel_io = Mock(
            side_effect=AssertionError("poll_clean cancelled the pending watch")
        )
        watcher._wait = Mock(
            side_effect=AssertionError("poll_clean waited on the pending watch")
        )

        watcher.poll_clean()
        watcher.poll_clean()

        self.assertTrue(watcher._active)
        self.assertFalse(watcher._verified)
        self.assertEqual(watcher._get_result.call_count, 2)
        watcher._cancel_io.assert_not_called()
        watcher._wait.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "Windows subtree watcher race")
    def test_current_check_rejects_first_and_closing_lstat_append_races(
        self,
    ) -> None:
        for raced_observation in (1, 2):
            with (
                self.subTest(raced_observation=raced_observation),
                tempfile.TemporaryDirectory() as temp_dir,
            ):
                root = self.archive(Path(temp_dir))
                archive_services.index_archive(root)
                target = sorted((root / "zettels").glob("*.md"))[0]
                real_lstat = archive_services.os.lstat
                observations = 0

                def append_after_observation(path):
                    nonlocal observations
                    observed = real_lstat(path)
                    candidate = Path(path)
                    if (
                        candidate.name == target.name
                        and candidate.parent.name == "zettels"
                    ):
                        observations += 1
                        if observations == raced_observation:
                            with target.open("ab") as handle:
                                handle.write(b"\n")
                                handle.flush()
                                os.fsync(handle.fileno())
                    return observed

                with patch.object(
                    archive_services.os,
                    "lstat",
                    side_effect=append_after_observation,
                ):
                    evidence = archive_services.require_current_zettel_index(
                        root
                    )

                self.assertGreaterEqual(observations, raced_observation)
                self.assertFalse(evidence["ok"], evidence)
                self.assertIn(
                    "archive_index_live_authority_changed_during_check",
                    evidence["reason_codes"],
                )

    def test_current_check_rejects_unrelated_add_delete_and_change_races(
        self,
    ) -> None:
        for case in ("added", "deleted", "changed"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp_dir:
                root = self.archive(Path(temp_dir))
                archive_services.index_archive(root)
                existing = sorted((root / "zettels").glob("*.md"))
                original_scan = archive_services._strict_live_zettel_stat_scan
                scans = 0

                def scan_then_race(*args, **kwargs):
                    nonlocal scans
                    result = original_scan(*args, **kwargs)
                    scans += 1
                    if scans == 1:
                        if case == "added":
                            (root / "inbox" / "late-added.md").write_text(
                                "---\nid: zet_20990101_late_added\n"
                                "title: Late added\nstatus: draft\n---\n",
                                encoding="utf-8",
                            )
                        elif case == "deleted":
                            existing[-1].unlink()
                        else:
                            with existing[-1].open("ab") as handle:
                                handle.write(b"\n")
                                handle.flush()
                                os.fsync(handle.fileno())
                    return result

                with patch.object(
                    archive_services,
                    "_strict_live_zettel_stat_scan",
                    side_effect=scan_then_race,
                ):
                    evidence = archive_services.require_current_zettel_index(
                        root
                    )

                self.assertEqual(scans, 2)
                self.assertFalse(evidence["ok"], evidence)

    def test_linux_inotify_overflow_and_unknown_watch_fail_closed(self) -> None:
        for watch_descriptor, mask in (
            (-1, archive_services._ArchiveIndexLinuxInotifyWatcher._IN_Q_OVERFLOW),
            (99, archive_services._ArchiveIndexLinuxInotifyWatcher._IN_MODIFY),
        ):
            with self.subTest(watch_descriptor=watch_descriptor, mask=mask):
                watcher = object.__new__(
                    archive_services._ArchiveIndexLinuxInotifyWatcher
                )
                watcher._fd = 123
                watcher._roles_by_watch_descriptor = {1: "zettel-tree"}
                event = b"".join(
                    (
                        int(watch_descriptor).to_bytes(
                            4,
                            byteorder=sys.byteorder,
                            signed=True,
                        ),
                        int(mask).to_bytes(
                            4,
                            byteorder=sys.byteorder,
                            signed=False,
                        ),
                        (0).to_bytes(4, byteorder=sys.byteorder),
                        (0).to_bytes(4, byteorder=sys.byteorder),
                    )
                )
                with patch.object(
                    archive_services.os,
                    "read",
                    return_value=event,
                ):
                    with self.assertRaises(OSError):
                        watcher.verify_clean()

    def test_large_manifest_builder_hashes_without_json_decoding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            archive_services.index_archive(root)
            manifest_path = root / "objects" / "manifests" / "files.jsonl"
            target_size = 37 * 1024 * 1024
            seed = manifest_path.read_bytes()
            manifest_path.write_bytes(seed + b" " * (target_size - len(seed)))
            snapshot = archive_services.archive_index_stable_file_snapshot(
                root,
                manifest_path,
                max_bytes=archive_services.ZETTEL_OBJET_LINK_MANIFEST_MAX_BYTES,
            )
            conn = archive_services.connect_archive_index(
                root / archive_services.INDEX_RELATIVE_PATH,
                write=True,
            )
            try:
                updates = {
                    "manifest_sha256": snapshot["file_sha256"],
                    **{
                        "manifest_" + key: str(value)
                        for key, value in snapshot["file_generation"].items()
                    },
                }
                for key, value in updates.items():
                    conn.execute(
                        "INSERT OR REPLACE INTO index_metadata(key, value) "
                        "VALUES (?, ?)",
                        (key, value),
                    )
                conn.commit()
            finally:
                conn.close()

            with patch.object(
                archive_services.json,
                "loads",
                side_effect=AssertionError("normal projection builder parsed JSON"),
            ):
                projection = (
                    archive_services.build_zettel_objet_link_authority_projection(
                        root
                    )
                )
            self.assertTrue(projection["ok"], projection)
            self.assertEqual(
                projection["manifest_sha256"],
                "sha256:" + hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            )


if __name__ == "__main__":
    unittest.main()
