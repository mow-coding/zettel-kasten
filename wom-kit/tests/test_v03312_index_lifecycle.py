from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import archive_services


PROMOTION_CHECKLIST_IDS = (
    "one_clear_purpose",
    "understandable_title",
    "future_self_contained",
    "source_clarity",
    "object_id_only",
    "stable_facets",
    "allowed_edges",
    "explicit_visibility",
    "provenance_present",
    "sensitive_content_reviewed",
)


def current_evidence(*, count: int = 0) -> dict[str, object]:
    return {
        "ok": True,
        "state": "current",
        "schema": archive_services.INDEX_METADATA_SCHEMA,
        "generation": "gen:" + "1" * 32,
        "indexed_zettel_count": count,
        "live_zettel_count": count,
        "live_snapshot_sha256": "sha256:" + "2" * 64,
        "staleness_check": "index_metadata_plus_live_stats",
        "reason_codes": [],
        "blockers": [],
    }


class IndexLifecycleV03312Tests(unittest.TestCase):
    def copy_archive(self, parent: Path) -> Path:
        root = parent / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", root)
        return root

    def ready_draft(self, root: Path, *, body: str | None = None) -> Path:
        path = root / "inbox" / "zet_20260519_draft_ai_lunch_note.md"
        frontmatter, existing_body = archive_services.require_readable_zettel_content(path)
        frontmatter["provenance"]["created_by"] = "person:test-fixture"
        frontmatter["provenance"]["creation_mode"] = "human_written"
        frontmatter["title"] = "Letter 123 progress fixture"
        frontmatter["kind"] = "permanent_note"
        frontmatter["promotion"] = {
            "stage": "promotion_candidate",
            "ready_for_promotion": True,
            "checklist": {item_id: True for item_id in PROMOTION_CHECKLIST_IDS},
        }
        rendered_body = body if body is not None else existing_body
        path.write_text(
            "---\n" + archive_services.dump_yaml(frontmatter) + "---\n\n" + rendered_body,
            encoding="utf-8",
            newline="\n",
        )
        return path

    def index_metadata(self, root: Path) -> dict[str, str]:
        conn = archive_services.connect_archive_index(
            root / archive_services.INDEX_RELATIVE_PATH,
            row_factory=True,
        )
        try:
            return archive_services.read_archive_index_metadata(conn)
        finally:
            conn.close()

    def write_query_zettel(
        self,
        root: Path,
        *,
        folder: str,
        name: str,
        zettel_id: str,
        status: str,
        title: str,
        created_at: str,
        minted_at: str | None,
        origin_marker: str,
        receipt_path: str | None = None,
    ) -> Path:
        frontmatter: dict[str, object] = {
            "id": zettel_id,
            "title": title,
            "status": status,
            "kind": "permanent_note",
            "created_at": created_at,
            "updated_at": created_at,
            "facets": {"test_scope": "letter312"},
            "provenance": {
                "created_by": "person:test",
                "created_in": "archive:personal:fake-life",
                "source": "local",
                "derived_from": [],
            },
            "visibility": {"scope": "private", "source_visibility": "private"},
            "edges": [],
            "abstract": "Safe query fixture.",
        }
        if origin_marker == "notion":
            frontmatter["source_system"] = "notion"
        elif origin_marker == "other":
            frontmatter["import_source"] = "evernote"
        if minted_at is not None:
            frontmatter["mint"] = {
                "stage": "minted",
                "minted_at": minted_at,
                "receipt_path": receipt_path or f"receipts/mint/{zettel_id}.mint.json",
            }
        path = root / folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\n"
            + archive_services.dump_yaml(frontmatter)
            + "---\n\n"
            + f"Synthetic query body for {zettel_id}.\n",
            encoding="utf-8",
            newline="\n",
        )
        return path

    def test_v03_metadata_and_strict_current_evidence_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            rebuilt = archive_services.index_archive(root)
            self.assertEqual(rebuilt["index_state"], "current")
            self.assertRegex(rebuilt["index_generation"], r"^gen:[0-9a-f]{32}$")
            self.assertRegex(rebuilt["live_snapshot_sha256"], r"^sha256:[0-9a-f]{64}$")

            original_snapshot = archive_services.strict_live_zettel_stat_snapshot
            with patch.object(
                archive_services,
                "strict_live_zettel_stat_snapshot",
                wraps=original_snapshot,
            ) as snapshot:
                evidence = archive_services.require_current_zettel_index(root)
            self.assertTrue(evidence["ok"], evidence)
            self.assertEqual(snapshot.call_count, 1)
            self.assertNotIn("path", json.dumps(evidence).casefold())

            changed = sorted((root / "zettels").glob("*.md"))[0]
            old = changed.stat()
            os.utime(changed, ns=(old.st_atime_ns, old.st_mtime_ns + 1_000_000_000))
            stale_search = archive_services.search_archive(root, "fixture")
            self.assertFalse(stale_search["ok"], stale_search)
            self.assertEqual(stale_search["blockers"], [archive_services.INDEX_REBUILD_REQUIRED])
            self.assertEqual(stale_search["results"], [])

            archive_services.index_archive(root)
            self.assertTrue(archive_services.mark_archive_index_dirty(root))
            dirty = archive_services.require_current_zettel_index(root)
            self.assertFalse(dirty["ok"], dirty)
            self.assertIn("archive_index_dirty", dirty["reason_codes"])
            self.assertEqual(dirty["blockers"], [archive_services.INDEX_REBUILD_REQUIRED])

            archive_services.index_archive(root)
            db_path = root / archive_services.INDEX_RELATIVE_PATH
            conn = archive_services.connect_archive_index(db_path, write=True)
            try:
                conn.execute(
                    "UPDATE index_metadata SET value = ? WHERE key = 'schema'",
                    ("wom-kit/archive-index-metadata/v0.2",),
                )
                conn.commit()
            finally:
                conn.close()
            legacy = archive_services.require_current_zettel_index(root)
            self.assertFalse(legacy["ok"], legacy)
            self.assertIn("archive_index_metadata_schema_mismatch", legacy["reason_codes"])
            self.assertEqual(legacy["blockers"], [archive_services.INDEX_REBUILD_REQUIRED])

        with tempfile.TemporaryDirectory() as tmp:
            missing_root = self.copy_archive(Path(tmp))
            missing = archive_services.require_current_zettel_index(missing_root)
            self.assertEqual(missing["reason_codes"], ["archive_index_missing"])
            self.assertEqual(missing["blockers"], [archive_services.INDEX_REBUILD_REQUIRED])

    def test_view_filters_projection_sort_and_canonical_dedupe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            self.write_query_zettel(
                root,
                folder="inbox",
                name="zet_letter312_shared.md",
                zettel_id="zet_letter312_shared",
                status="draft",
                title="Shared publication",
                created_at="2026-08-09T10:00:00+09:00",
                minted_at=None,
                origin_marker="wom",
            )
            self.write_query_zettel(
                root,
                folder="zettels",
                name="zet_letter312_shared.md",
                zettel_id="zet_letter312_shared",
                status="canonical",
                title="Shared publication",
                created_at="2026-08-09T10:00:00+09:00",
                minted_at="2026-08-10T09:30:00+09:00",
                origin_marker="wom",
            )
            self.write_query_zettel(
                root,
                folder="zettels",
                name="zet_notion_letter312.md",
                zettel_id="zet_notion_letter312",
                status="canonical",
                title="Notion import",
                created_at="2026-08-08T10:00:00+09:00",
                minted_at="2026-08-10T08:00:00+09:00",
                origin_marker="notion",
            )
            self.write_query_zettel(
                root,
                folder="zettels",
                name="zet_import_letter312.md",
                zettel_id="zet_import_letter312",
                status="canonical",
                title="Other import",
                created_at="2026-08-07T10:00:00+09:00",
                minted_at="2026-08-10T07:00:00+09:00",
                origin_marker="other",
                receipt_path="C:/unsafe/private-receipt.json",
            )
            archive_services.index_archive(root)

            native = archive_services.view_zets(
                root,
                facets={"test_scope": "letter312"},
                origin="wom_native",
                minted_after="2026-08-10T00:00:00+09:00",
                minted_before="2026-08-10T23:59:59+09:00",
                sort="minted_at_desc",
                dedupe_by="zettel_id",
            )
            self.assertTrue(native["ok"], native)
            self.assertEqual([row["id"] for row in native["zettels"]], ["zet_letter312_shared"])
            selected = native["zettels"][0]
            self.assertEqual(selected["status"], "canonical")
            self.assertEqual(selected["origin_class"], "wom_native")
            self.assertEqual(selected["minted_at"], "2026-08-10T00:30:00+00:00")
            self.assertEqual(
                selected["mint_receipt_path"],
                "receipts/mint/zet_letter312_shared.mint.json",
            )

            notion = archive_services.view_zets(
                root,
                facets={"test_scope": "letter312"},
                status="canonical",
                origin="notion_import",
                sort="created_at_desc",
            )
            self.assertEqual([row["id"] for row in notion["zettels"]], ["zet_notion_letter312"])
            other = archive_services.view_zets(
                root,
                facets={"test_scope": "letter312"},
                origin="other_import",
            )
            self.assertEqual([row["id"] for row in other["zettels"]], ["zet_import_letter312"])
            self.assertIsNone(other["zettels"][0]["mint_receipt_path"])

            status_only = archive_services.view_zets(root, status="canonical")
            self.assertTrue(status_only["ok"], status_only)
            self.assertTrue(status_only["zettels"])
            self.assertTrue(all(row["status"] == "canonical" for row in status_only["zettels"]))

            origin_only = archive_services.view_zets(root, origin="wom_native")
            self.assertTrue(origin_only["ok"], origin_only)
            self.assertTrue(origin_only["zettels"])
            self.assertTrue(
                all(row["origin_class"] == "wom_native" for row in origin_only["zettels"])
            )

            minted_sort_dedupe_only = archive_services.view_zets(
                root,
                minted_after="2026-08-10T06:00:00+09:00",
                minted_before="2026-08-10T10:00:00+09:00",
                sort="minted_at_desc",
                dedupe_by="zettel_id",
            )
            self.assertTrue(minted_sort_dedupe_only["ok"], minted_sort_dedupe_only)
            self.assertEqual(
                [row["id"] for row in minted_sort_dedupe_only["zettels"]],
                ["zet_letter312_shared", "zet_notion_letter312", "zet_import_letter312"],
            )

    def test_8599_duplicate_query_reads_only_one_digest_candidate_and_no_body_column(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            db_path = root / archive_services.INDEX_RELATIVE_PATH
            db_path.parent.mkdir(parents=True)
            target_body = "Distinct bounded duplicate prefix. " * 20
            target_digest = archive_services.zettel_index_body_prefix_sha256(target_body)
            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    """
                    CREATE TABLE zettels(
                      path TEXT PRIMARY KEY,
                      zettel_id TEXT,
                      status TEXT,
                      normalized_title TEXT,
                      body_prefix_sha256 TEXT,
                      body TEXT
                    )
                    """
                )
                rows = []
                for index in range(8_599):
                    rows.append(
                        (
                            f"zettels/zet_fixture_{index:05d}.md",
                            f"zet_fixture_{index:05d}",
                            "canonical",
                            f"fixture title {index:05d}",
                            target_digest if index == 4_321 else f"{index:064x}"[-64:],
                            "PRIVATE BODY MUST NOT BE READ",
                        )
                    )
                conn.executemany("INSERT INTO zettels VALUES (?, ?, ?, ?, ?, ?)", rows)
                conn.commit()
            finally:
                conn.close()

            body_column_reads: list[tuple[str | None, str | None]] = []
            original_connect = archive_services.connect_archive_index

            def traced_connect(*args, **kwargs):
                traced = original_connect(*args, **kwargs)

                def authorizer(action, table, column, _db, _trigger):
                    if action == sqlite3.SQLITE_READ and table == "zettels" and column == "body":
                        body_column_reads.append((table, column))
                    return sqlite3.SQLITE_OK

                traced.set_authorizer(authorizer)
                return traced

            started = time.perf_counter()
            with patch.object(archive_services, "connect_archive_index", side_effect=traced_connect), patch.object(
                archive_services,
                "require_current_zettel_index",
                return_value=current_evidence(count=8_599),
            ), patch.object(
                archive_services,
                "read_zettel_content_boundary",
                side_effect=AssertionError("canonical body fallback is forbidden"),
            ):
                duplicate_check: dict[str, object] = {}
                duplicates = archive_services.find_promotion_duplicates(
                    root,
                    root / "inbox" / "target.md",
                    {"id": "zet_target", "title": "Target title"},
                    target_body,
                    "zettels/target.md",
                    duplicate_check=duplicate_check,
                )
            elapsed = time.perf_counter() - started

            self.assertEqual(body_column_reads, [])
            self.assertEqual(duplicate_check["indexed_canonical_count"], 8_599)
            self.assertEqual(duplicate_check["canonical_candidates_checked"], 1)
            self.assertEqual([row["reason"] for row in duplicates], ["very_similar_body_start"])
            self.assertLess(elapsed, 5.0)

    def test_progress_stages_and_stale_duplicate_block_are_content_free(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            draft = self.ready_draft(root, body="Bounded progress fixture body. " * 20)
            archive_services.index_archive(root)
            events: list[tuple[str, str, int | None, int | None]] = []
            result = archive_services.mint_zettel_dry_run(
                root,
                relative_path="inbox/zet_20260519_draft_ai_lunch_note.md",
                progress_callback=lambda stage, message, current, total: events.append(
                    (stage, message, current, total)
                ),
            )
            self.assertTrue(result["ok"], result)
            stages = {stage for stage, _message, _current, _total in events}
            self.assertTrue(
                {
                    "target",
                    "policy",
                    "self_contained",
                    "quality",
                    "index_snapshot",
                    "canonical_conflict",
                    "duplicate_title",
                    "receipt_plan",
                }.issubset(stages),
                events,
            )
            self.assertTrue(stages.issubset(archive_services.MINT_PROGRESS_STAGES))
            event_text = json.dumps(events)
            self.assertNotIn(str(root), event_text)
            self.assertNotIn(draft.name, event_text)

            changed = sorted((root / "zettels").glob("*.md"))[0]
            old = changed.stat()
            os.utime(changed, ns=(old.st_atime_ns, old.st_mtime_ns + 1_000_000_000))
            with patch.object(
                archive_services,
                "read_zettel_content_boundary",
                side_effect=AssertionError("stale index must not fall back to canonical bodies"),
            ):
                duplicate_check: dict[str, object] = {}
                blocked = archive_services.find_promotion_duplicates(
                    root,
                    draft,
                    {"id": "zet_target", "title": "Target"},
                    "Another bounded target body. " * 20,
                    "zettels/target.md",
                    duplicate_check=duplicate_check,
                )
            self.assertEqual([item["reason"] for item in blocked], [archive_services.INDEX_REBUILD_REQUIRED])
            self.assertFalse(duplicate_check["used_generated_index"])
            self.assertEqual(duplicate_check["fallback_reason"], archive_services.INDEX_REBUILD_REQUIRED)

    def test_mint_index_failure_is_honest_partial_and_marks_dirty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            self.ready_draft(root, body="Index failure fixture body. " * 20)
            archive_services.index_archive(root)
            with patch.object(
                archive_services,
                "upsert_zettel_index_entry",
                side_effect=sqlite3.OperationalError("synthetic index failure"),
            ):
                result = archive_services.mint_zettel(
                    root,
                    relative_path="inbox/zet_20260519_draft_ai_lunch_note.md",
                    reviewed_by="person:test",
                    allow_warnings=True,
                )
            self.assertFalse(result["ok"], result)
            self.assertEqual(result["blockers"], [archive_services.INDEX_REBUILD_REQUIRED])
            self.assertTrue(result["partial_result"]["canonical_receipt_and_snapshot_written"])
            self.assertTrue((root / result["canonical_path"]).is_file())
            self.assertTrue((root / result["mint_receipt_path"]).is_file())
            self.assertTrue((root / result["draft_snapshot_path"]).is_file())
            metadata_conn = archive_services.connect_archive_index(
                root / archive_services.INDEX_RELATIVE_PATH,
                row_factory=True,
            )
            try:
                metadata = archive_services.read_archive_index_metadata(metadata_conn)
            finally:
                metadata_conn.close()
            self.assertEqual(metadata["state"], "dirty")

    def test_retire_removes_draft_index_row_and_keeps_generation_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            draft = self.ready_draft(root, body="Retirement index fixture body. " * 20)
            frontmatter, body = archive_services.require_readable_zettel_content(draft)
            frontmatter["mint"] = {"stage": "draft"}
            draft.write_text(
                "---\n" + archive_services.dump_yaml(frontmatter) + "---\n\n" + body,
                encoding="utf-8",
                newline="\n",
            )
            archive_services.index_archive(root)
            minted = archive_services.mint_zettel(
                root,
                relative_path="inbox/zet_20260519_draft_ai_lunch_note.md",
                reviewed_by="person:test",
                allow_warnings=True,
            )
            self.assertTrue(minted["ok"], minted)
            before = archive_services.require_current_zettel_index(root)
            retired = archive_services.retire_minted_draft(
                root,
                zettel_id="zet_20260519_draft_ai_lunch_note",
                reviewed_by="person:test",
                approve=True,
            )
            self.assertTrue(retired["ok"], retired)
            self.assertTrue(retired["index_row_removed"])
            after = archive_services.require_current_zettel_index(root)
            self.assertTrue(after["ok"], after)
            self.assertEqual(before["generation"], after["generation"])
            conn = archive_services.connect_archive_index(
                root / archive_services.INDEX_RELATIVE_PATH,
                row_factory=True,
            )
            try:
                row = conn.execute(
                    "SELECT 1 FROM zettels WHERE path = ?",
                    ("inbox/zet_20260519_draft_ai_lunch_note.md",),
                ).fetchone()
            finally:
                conn.close()
            self.assertIsNone(row)

    def test_retire_index_failure_keeps_filesystem_result_and_marks_index_dirty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            self.ready_draft(root, body="Retirement failure fixture body. " * 20)
            archive_services.index_archive(root)
            minted = archive_services.mint_zettel(
                root,
                relative_path="inbox/zet_20260519_draft_ai_lunch_note.md",
                reviewed_by="person:test",
                allow_warnings=True,
            )
            self.assertTrue(minted["ok"], minted)
            with patch.object(
                archive_services,
                "delete_zettel_index_entry",
                side_effect=sqlite3.OperationalError("synthetic retire index failure"),
            ):
                retired = archive_services.retire_minted_draft(
                    root,
                    zettel_id="zet_20260519_draft_ai_lunch_note",
                    reviewed_by="person:test",
                    approve=True,
                )
            self.assertFalse(retired["ok"], retired)
            self.assertEqual(retired["blockers"], [archive_services.INDEX_REBUILD_REQUIRED])
            self.assertTrue(retired["partial_result"]["draft_removed_and_receipt_written"])
            self.assertFalse((root / retired["draft_path"]).exists())
            self.assertTrue((root / retired["retire_receipt_path"]).is_file())
            metadata_conn = archive_services.connect_archive_index(
                root / archive_services.INDEX_RELATIVE_PATH,
                row_factory=True,
            )
            try:
                metadata = archive_services.read_archive_index_metadata(metadata_conn)
            finally:
                metadata_conn.close()
            self.assertEqual(metadata["state"], "dirty")

    def test_all_three_mutations_commit_dirty_intent_before_first_indexed_file_change(self) -> None:
        original_open = Path.open

        def crash_first_canonical_open(path: Path, *args, **kwargs):
            mode = str(args[0] if args else kwargs.get("mode", "r"))
            if path.parent.name == "zettels" and "x" in mode:
                raise RuntimeError("synthetic crash before canonical write")
            return original_open(path, *args, **kwargs)

        original_create_bytes = archive_services._write_bytes_create_if_absent

        def crash_first_canonical_create(path: Path, payload: bytes):
            if path.parent.name == "zettels":
                raise RuntimeError("synthetic crash before canonical write")
            return original_create_bytes(path, payload)

        for operation in ("promote", "mint"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as tmp:
                root = self.copy_archive(Path(tmp))
                self.ready_draft(root, body=f"{operation} dirty intent fixture body. " * 20)
                archive_services.index_archive(root)
                with self.assertRaisesRegex(RuntimeError, "before canonical write"):
                    if operation == "promote":
                        with patch.object(
                            Path, "open", new=crash_first_canonical_open
                        ):
                            archive_services.promote_zettel(
                                root,
                                relative_path="inbox/zet_20260519_draft_ai_lunch_note.md",
                                reviewed_by="person:test",
                                allow_warnings=True,
                            )
                    else:
                        with patch.object(
                            archive_services,
                            "_write_bytes_create_if_absent",
                            new=crash_first_canonical_create,
                        ):
                            archive_services.mint_zettel(
                                root,
                                relative_path="inbox/zet_20260519_draft_ai_lunch_note.md",
                                reviewed_by="person:test",
                                allow_warnings=True,
                            )
                self.assertEqual(self.index_metadata(root)["state"], "dirty")
                self.assertEqual(
                    archive_services.require_current_zettel_index(root)["blockers"],
                    [archive_services.INDEX_REBUILD_REQUIRED],
                )
                self.assertFalse(
                    (root / "zettels" / "zet_20260519_draft_ai_lunch_note.md").exists()
                )

        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            draft = self.ready_draft(root, body="retire dirty intent fixture body. " * 20)
            archive_services.index_archive(root)
            minted = archive_services.mint_zettel(
                root,
                relative_path="inbox/zet_20260519_draft_ai_lunch_note.md",
                reviewed_by="person:test",
                allow_warnings=True,
            )
            self.assertTrue(minted["ok"], minted)
            original_unlink = Path.unlink

            def crash_before_unlink(path: Path, *args, **kwargs):
                if path.name == draft.name and path.parent.name == "inbox":
                    raise RuntimeError("synthetic crash before draft unlink")
                return original_unlink(path, *args, **kwargs)

            with patch.object(Path, "unlink", new=crash_before_unlink):
                with self.assertRaisesRegex(RuntimeError, "before draft unlink"):
                    archive_services.retire_minted_draft(
                        root,
                        zettel_id="zet_20260519_draft_ai_lunch_note",
                        reviewed_by="person:test",
                        approve=True,
                    )
            self.assertTrue(draft.is_file())
            self.assertEqual(self.index_metadata(root)["state"], "dirty")

    def test_mint_rejects_corruption_between_canonical_write_and_index_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            self.ready_draft(root, body="canonical corruption race fixture body. " * 20)
            archive_services.index_archive(root)
            original_upsert = archive_services.upsert_zettel_index_entry

            def corrupt_then_upsert(root_arg, zettel_path, *args, **kwargs):
                zettel_path.write_text(
                    "---\nid: [synthetic-corruption\n---\nprivate body must not be indexed\n",
                    encoding="utf-8",
                    newline="\n",
                )
                return original_upsert(root_arg, zettel_path, *args, **kwargs)

            with patch.object(
                archive_services,
                "upsert_zettel_index_entry",
                side_effect=corrupt_then_upsert,
            ):
                result = archive_services.mint_zettel(
                    root,
                    relative_path="inbox/zet_20260519_draft_ai_lunch_note.md",
                    reviewed_by="person:test",
                    allow_warnings=True,
                )
            self.assertFalse(result["ok"], result)
            self.assertFalse(result["generated_index_updated"])
            self.assertEqual(result["blockers"], [archive_services.INDEX_REBUILD_REQUIRED])
            self.assertEqual(self.index_metadata(root)["state"], "dirty")
            conn = archive_services.connect_archive_index(
                root / archive_services.INDEX_RELATIVE_PATH,
                row_factory=True,
            )
            try:
                row = conn.execute(
                    "SELECT status FROM zettels WHERE path = ?",
                    (result["canonical_path"],),
                ).fetchone()
            finally:
                conn.close()
            self.assertIsNone(row)

    def test_cleaned_failed_write_reseals_same_generation_without_a_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            rebuilt = archive_services.index_archive(root)
            generation = str(rebuilt["index_generation"])

            archive_services.begin_archive_index_mutation(
                root,
                expected_generation=generation,
            )
            self.assertEqual(self.index_metadata(root)["state"], "dirty")

            resealed = archive_services.reseal_archive_index_mutation_without_delta(
                root,
                expected_generation=generation,
            )

            self.assertTrue(resealed)
            evidence = archive_services.require_current_zettel_index(root)
            self.assertTrue(evidence["ok"], evidence)
            self.assertEqual(evidence["generation"], generation)
            self.assertEqual(self.index_metadata(root)["state"], "current")

    def test_mint_reseal_rechecks_unrelated_live_zet_and_stays_dirty_on_race(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            self.ready_draft(root, body="unrelated live race fixture body. " * 20)
            archive_services.index_archive(root)
            unrelated = sorted((root / "zettels").glob("*.md"))[0]
            original_upsert = archive_services.upsert_zettel_index_entry

            def mutate_unrelated_then_upsert(root_arg, zettel_path, *args, **kwargs):
                previous = unrelated.stat()
                os.utime(
                    unrelated,
                    ns=(previous.st_atime_ns, previous.st_mtime_ns + 1_000_000_000),
                )
                return original_upsert(root_arg, zettel_path, *args, **kwargs)

            with patch.object(
                archive_services,
                "upsert_zettel_index_entry",
                side_effect=mutate_unrelated_then_upsert,
            ):
                result = archive_services.mint_zettel(
                    root,
                    relative_path="inbox/zet_20260519_draft_ai_lunch_note.md",
                    reviewed_by="person:test",
                    allow_warnings=True,
                )
            self.assertFalse(result["ok"], result)
            self.assertEqual(self.index_metadata(root)["state"], "dirty")
            evidence = archive_services.require_current_zettel_index(root)
            self.assertFalse(evidence["ok"], evidence)
            self.assertIn("live_zettel_stat_differs_from_index", evidence["reason_codes"])

    def test_retire_receipt_failure_never_overwrites_concurrent_recreated_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            draft = self.ready_draft(root, body="retire restore conflict fixture body. " * 20)
            archive_services.index_archive(root)
            minted = archive_services.mint_zettel(
                root,
                relative_path="inbox/zet_20260519_draft_ai_lunch_note.md",
                reviewed_by="person:test",
                allow_warnings=True,
            )
            self.assertTrue(minted["ok"], minted)
            plan = archive_services.minted_draft_retirement_plan(
                root,
                zettel_id="zet_20260519_draft_ai_lunch_note",
            )
            retire_receipt_path = root / str(plan["retire_receipt_path"])
            concurrent_bytes = b"CONCURRENT DRAFT MUST BE PRESERVED\n"
            original_open = Path.open

            def recreate_then_fail_receipt(path: Path, *args, **kwargs):
                mode = str(args[0] if args else kwargs.get("mode", "r"))
                if (
                    path.name == retire_receipt_path.name
                    and path.parent.name == retire_receipt_path.parent.name
                    and "x" in mode
                ):
                    with original_open(draft, "xb") as handle:
                        handle.write(concurrent_bytes)
                    raise OSError("synthetic retire receipt failure")
                return original_open(path, *args, **kwargs)

            with patch.object(Path, "open", new=recreate_then_fail_receipt):
                with self.assertRaisesRegex(
                    archive_services.ArchiveServiceError,
                    "retired_draft_restore_conflict",
                ):
                    archive_services.retire_minted_draft(
                        root,
                        zettel_id="zet_20260519_draft_ai_lunch_note",
                        reviewed_by="person:test",
                        approve=True,
                    )
            self.assertEqual(draft.read_bytes(), concurrent_bytes)
            self.assertFalse(retire_receipt_path.exists())
            self.assertEqual(self.index_metadata(root)["state"], "dirty")

    def test_promote_and_mint_cleanup_preserve_replacement_files_and_dirty_index(self) -> None:
        original_open = Path.open
        replacement_bytes = b"EXTERNAL REPLACEMENT MUST NOT BE DELETED\n"

        for operation in ("promote", "mint"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as tmp:
                root = self.copy_archive(Path(tmp))
                draft = self.ready_draft(
                    root,
                    body=f"{operation} cleanup replacement fixture body. " * 20,
                )
                archive_services.index_archive(root)
                if operation == "promote":
                    preview = archive_services.promote_zettel_dry_run(
                        root,
                        relative_path="inbox/zet_20260519_draft_ai_lunch_note.md",
                    )
                    receipt_path = root / str(preview["proposed_receipt_path"])
                else:
                    preview = archive_services.mint_zettel_dry_run(
                        root,
                        relative_path="inbox/zet_20260519_draft_ai_lunch_note.md",
                    )
                    receipt_path = root / str(preview["proposed_mint_receipt_path"])
                canonical_path = root / str(preview["proposed_canonical_path"])

                def replace_then_fail_receipt(path: Path, *args, **kwargs):
                    mode = str(args[0] if args else kwargs.get("mode", "r"))
                    if (
                        path.name == receipt_path.name
                        and path.parent.name == receipt_path.parent.name
                        and "x" in mode
                    ):
                        canonical_path.write_bytes(replacement_bytes)
                        raise OSError("synthetic receipt failure after replacement")
                    return original_open(path, *args, **kwargs)

                with patch.object(Path, "open", new=replace_then_fail_receipt):
                    with self.assertRaisesRegex(OSError, "after replacement"):
                        if operation == "promote":
                            archive_services.promote_zettel(
                                root,
                                relative_path=archive_services.archive_relative_path(draft, root),
                                reviewed_by="person:test",
                                allow_warnings=True,
                            )
                        else:
                            archive_services.mint_zettel(
                                root,
                                relative_path=archive_services.archive_relative_path(draft, root),
                                reviewed_by="person:test",
                                allow_warnings=True,
                            )
                self.assertEqual(canonical_path.read_bytes(), replacement_bytes)
                self.assertEqual(self.index_metadata(root)["state"], "dirty")
                self.assertFalse(archive_services.require_current_zettel_index(root)["ok"])


if __name__ == "__main__":
    unittest.main()
