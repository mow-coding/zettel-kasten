from __future__ import annotations

import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from wom_kit import archive_services, local_recovery_execution
from wom_kit.exact_human_approval import (
    exact_human_approval_archive_identity_sha256,
)
from wom_kit.exact_operation_manifest import (
    ExactFieldEffect,
    ExactOperationItem,
    ExactOperationManifest,
    FileExactOperationCheckpointStore,
    exact_operation_writer_lock,
    hash_field_value,
)
from wom_kit.local_recovery_execution import (
    APPLY_OPERATION,
    LocalRecoveryFieldSpec,
    _run_with_store,
    build_local_recovery_plan,
    execute_local_recovery,
    local_recovery_zettel_identity_sha256,
)


KIT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = KIT_ROOT / "examples" / "fake-life-archive"
TARGETS = (
    "zet_20240504_fake_lunch_thought",
    "zet_20110228_fake_school_record",
)


class BatchZettelWriterIndexLifecycleTests(unittest.TestCase):
    def archive(self, parent: Path) -> Path:
        root = parent / "archive"
        shutil.copytree(FIXTURE, root)
        indexed = archive_services.index_archive(root)
        self.assertEqual(indexed["zettels"], 5)
        evidence = archive_services.require_current_zettel_index(root)
        self.assertTrue(evidence["ok"], evidence)
        return root

    def plan(self, root: Path):
        archive_id = archive_services.read_archive_id(root)
        items: list[ExactOperationItem] = []
        specs: list[LocalRecoveryFieldSpec] = []
        for ordinal, zettel_id in enumerate(TARGETS):
            relative = f"zettels/{zettel_id}.md"
            path = root.joinpath(*relative.split("/"))
            frontmatter, _body = archive_services.require_readable_zettel_content(
                path
            )
            before = str(frontmatter["title"]).encode("utf-8")
            after = f"Indexed recovered title {ordinal + 1}".encode("utf-8")
            source = (
                f'{{"source":"batch-index-{ordinal + 1}"}}'.encode("ascii")
            )
            identity = local_recovery_zettel_identity_sha256(
                archive_id,
                zettel_id,
                relative,
            )
            item = ExactOperationItem(
                ordinal=ordinal,
                item_id=f"item:{ordinal:06d}",
                target_kind="zettel",
                target_ref=identity,
                target_identity_sha256=identity,
                fields=(
                    ExactFieldEffect(
                        field_ref="frontmatter.title",
                        pre_sha256=hash_field_value(before),
                        post_sha256=hash_field_value(after),
                        source_sha256=hash_field_value(source),
                    ),
                ),
            )
            items.append(item)
            specs.append(
                LocalRecoveryFieldSpec(
                    item_id=item.item_id,
                    target_kind=item.target_kind,
                    target_ref=item.target_ref,
                    target_identity_sha256=item.target_identity_sha256,
                    field_ref=item.fields[0].field_ref,
                    target_relative=relative,
                    zettel_id=zettel_id,
                    pre_value=before,
                    post_value=after,
                    source_value=source,
                )
            )
        manifest = ExactOperationManifest.build(
            operation=APPLY_OPERATION,
            archive_identity_sha256=(
                exact_human_approval_archive_identity_sha256(archive_id)
            ),
            items=items,
        )
        return build_local_recovery_plan(
            root,
            domain="synthetic_batch_index",
            manifest=manifest,
            specs=specs,
        )

    def execute(
        self,
        plan: Any,
        *,
        mode: str = "apply",
        resume: bool = False,
    ) -> dict[str, Any]:
        with exact_operation_writer_lock(plan.archive_root) as lock:
            store = FileExactOperationCheckpointStore(
                plan.archive_root,
                writer_lock=lock,
            )
            return _run_with_store(
                plan,
                None,
                store,
                mode=mode,
                resume=resume,
                progress_hook=None,
            )

    def metadata(self, root: Path) -> dict[str, str]:
        conn = archive_services.connect_archive_index(
            root / archive_services.INDEX_RELATIVE_PATH,
            row_factory=True,
        )
        try:
            return archive_services.read_archive_index_metadata(conn)
        finally:
            conn.close()

    def assert_searches_updated_titles(self, root: Path) -> None:
        for ordinal in range(len(TARGETS)):
            title = f"Indexed recovered title {ordinal + 1}"
            search = archive_services.search_archive(root, title)
            self.assertTrue(search["ok"], search)
            self.assertTrue(
                any(result.get("title") == title for result in search["results"]),
                search,
            )

    def exact_index_entries(self, root: Path) -> tuple[dict[str, Any], ...]:
        entries = []
        for zettel_id in TARGETS:
            path = root / "zettels" / f"{zettel_id}.md"
            raw = path.read_bytes()
            frontmatter, body = archive_services.require_readable_zettel_content(
                path
            )
            entries.append(
                {
                    "path": path,
                    "frontmatter": frontmatter,
                    "body": body,
                    "expected_file_sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
        return tuple(entries)

    def test_multi_item_success_seals_one_generation_and_updates_search(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.archive(Path(temporary))
            generation = self.metadata(root)["generation"]
            plan = self.plan(root)

            result = self.execute(plan)

            self.assertTrue(result["ok"], result)
            self.assertTrue(result["generated_index_updated"])
            self.assertTrue(result["index_mutation_started"])
            self.assertFalse(result["index_mutation_resumed"])
            self.assertTrue(result["index_current"])
            self.assertFalse(result["index_rebuild_required"])
            self.assertEqual(result["index_generation"], generation)
            evidence = archive_services.require_current_zettel_index(root)
            self.assertTrue(evidence["ok"], evidence)
            self.assertEqual(evidence["generation"], generation)
            self.assert_searches_updated_titles(root)

    def test_interruption_keeps_dirty_and_resume_seals_complete_live_batch(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.archive(Path(temporary))
            generation = self.metadata(root)["generation"]
            plan = self.plan(root)
            original = local_recovery_execution._Writer.write_field
            calls = 0

            def write_first_then_crash(writer, **kwargs):
                nonlocal calls
                original(writer, **kwargs)
                calls += 1
                if calls == 1:
                    raise RuntimeError("synthetic indexed batch interruption")

            with mock.patch.object(
                local_recovery_execution._Writer,
                "write_field",
                new=write_first_then_crash,
            ):
                interrupted = self.execute(plan)

            self.assertFalse(interrupted["ok"], interrupted)
            self.assertTrue(interrupted["index_mutation_started"])
            self.assertTrue(interrupted["index_marked_dirty"])
            self.assertTrue(interrupted["index_rebuild_required"])
            dirty = self.metadata(root)
            self.assertEqual(dirty["state"], archive_services.INDEX_STATE_DIRTY)
            self.assertEqual(dirty["generation"], generation)

            resumed = self.execute(plan, resume=True)

            self.assertTrue(resumed["ok"], resumed)
            self.assertTrue(resumed["generated_index_updated"])
            self.assertFalse(resumed["index_mutation_started"])
            self.assertTrue(resumed["index_mutation_resumed"])
            self.assertTrue(resumed["index_current"])
            self.assertEqual(resumed["index_generation"], generation)
            evidence = archive_services.require_current_zettel_index(root)
            self.assertTrue(evidence["ok"], evidence)
            self.assertEqual(evidence["generation"], generation)
            self.assert_searches_updated_titles(root)

    def test_batch_delta_failure_reports_durable_dirty_not_success(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.archive(Path(temporary))
            generation = self.metadata(root)["generation"]
            plan = self.plan(root)

            with mock.patch.object(
                archive_services,
                "upsert_zettel_index_entries",
                return_value=False,
            ):
                failed = self.execute(plan)

            self.assertFalse(failed["ok"], failed)
            self.assertEqual(failed["state"], "applied_index_update_failed")
            self.assertTrue(failed["index_delta_failed"])
            self.assertTrue(failed["index_marked_dirty"])
            self.assertEqual(
                failed["blockers"],
                [archive_services.INDEX_REBUILD_REQUIRED],
            )
            for spec in plan.specs:
                path = root.joinpath(*spec.target_relative.split("/"))
                frontmatter, _body = archive_services.require_readable_zettel_content(
                    path
                )
                self.assertEqual(
                    frontmatter["title"], spec.post_value.decode("utf-8")
                )
            dirty = self.metadata(root)
            self.assertEqual(dirty["state"], archive_services.INDEX_STATE_DIRTY)
            self.assertEqual(dirty["generation"], generation)
            blocked_search = archive_services.search_archive(
                root,
                "Indexed recovered title",
            )
            self.assertFalse(blocked_search["ok"], blocked_search)

            repaired = self.execute(plan, resume=True)
            self.assertTrue(repaired["ok"], repaired)
            self.assertTrue(repaired["index_mutation_resumed"])
            self.assertTrue(repaired["generated_index_updated"])
            self.assert_searches_updated_titles(root)

    def test_batch_adapter_rolls_back_partial_sql_delta_and_keeps_dirty(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.archive(Path(temporary))
            generation = self.metadata(root)["generation"]
            original_titles = {}
            changed_bytes = {}
            for ordinal, zettel_id in enumerate(TARGETS):
                path = root / "zettels" / f"{zettel_id}.md"
                frontmatter, _body = (
                    archive_services.require_readable_zettel_content(path)
                )
                original_title = str(frontmatter["title"])
                original_titles[zettel_id] = original_title
                replacement = f"Transactional recovered title {ordinal + 1}"
                raw = path.read_bytes()
                needle = f"title: {original_title}".encode("utf-8")
                self.assertEqual(raw.count(needle), 1)
                changed_bytes[zettel_id] = raw.replace(
                    needle,
                    f"title: {replacement}".encode("utf-8"),
                    1,
                )
            owner = "sha256:" + hashlib.sha256(
                b"v0412-batch-sql-rollback-owner"
            ).hexdigest()
            lease_token = archive_services.begin_archive_index_mutation(
                root,
                expected_generation=generation,
                mutation_owner_sha256=owner,
            )
            for zettel_id, raw in changed_bytes.items():
                (root / "zettels" / f"{zettel_id}.md").write_bytes(raw)
            entries = self.exact_index_entries(root)
            original_collect = archive_services.collect_referenced_zets
            calls = 0

            def fail_during_second_row(frontmatter):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise ValueError("synthetic second-row SQL delta failure")
                return original_collect(frontmatter)

            with mock.patch.object(
                archive_services,
                "collect_referenced_zets",
                side_effect=fail_during_second_row,
            ):
                updated = archive_services.upsert_zettel_index_entries(
                    root,
                    entries,
                    expected_generation=generation,
                    expected_mutation_owner_sha256=owner,
                    lease_token=lease_token,
                )

            self.assertFalse(updated)
            dirty = self.metadata(root)
            self.assertEqual(dirty["state"], archive_services.INDEX_STATE_DIRTY)
            self.assertEqual(dirty["generation"], generation)
            conn = archive_services.connect_archive_index(
                root / archive_services.INDEX_RELATIVE_PATH,
                row_factory=True,
            )
            try:
                indexed_titles = {
                    str(row["zettel_id"]): str(row["title"])
                    for row in conn.execute(
                        "SELECT zettel_id, title FROM zettels "
                        "WHERE zettel_id IN (?, ?)",
                        TARGETS,
                    ).fetchall()
                }
            finally:
                conn.close()
            self.assertEqual(indexed_titles, original_titles)
            self.assertFalse(
                archive_services.search_archive(
                    root,
                    "Transactional recovered title",
                )["ok"]
            )

            resumed_token = archive_services.resume_archive_index_mutation(
                root,
                expected_generation=generation,
                expected_mutation_owner_sha256=owner,
            )
            self.assertTrue(
                archive_services.upsert_zettel_index_entries(
                    root,
                    entries,
                    expected_generation=generation,
                    expected_mutation_owner_sha256=owner,
                    lease_token=resumed_token,
                )
            )
            self.assertTrue(
                archive_services.require_current_zettel_index(root)["ok"]
            )

    def test_completed_resume_is_noop_and_does_not_begin_or_delta(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.archive(Path(temporary))
            plan = self.plan(root)
            applied = self.execute(plan)
            self.assertTrue(applied["ok"], applied)

            with mock.patch.object(
                archive_services,
                "begin_archive_index_mutation",
                side_effect=AssertionError("no-op must not begin"),
            ) as begin, mock.patch.object(
                archive_services,
                "upsert_zettel_index_entries",
                side_effect=AssertionError("no-op must not write a delta"),
            ) as delta:
                no_op = self.execute(plan, resume=True)

            self.assertTrue(no_op["ok"], no_op)
            self.assertFalse(no_op["generated_index_updated"])
            self.assertFalse(no_op["index_mutation_started"])
            self.assertFalse(no_op["index_mutation_resumed"])
            self.assertTrue(no_op["index_current"])
            begin.assert_not_called()
            delta.assert_not_called()
            self.assertTrue(
                archive_services.require_current_zettel_index(root)["ok"]
            )

    def test_exact_full_revert_reseals_original_rows_in_same_generation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.archive(Path(temporary))
            generation = self.metadata(root)["generation"]
            plan = self.plan(root)
            original_titles = {
                spec.zettel_id: spec.pre_value.decode("utf-8")
                for spec in plan.specs
            }
            applied = self.execute(plan)
            self.assertTrue(applied["ok"], applied)

            reverted = self.execute(plan, mode="revert")

            self.assertTrue(reverted["ok"], reverted)
            self.assertTrue(reverted["generated_index_updated"])
            self.assertTrue(reverted["index_mutation_started"])
            self.assertTrue(reverted["index_current"])
            self.assertEqual(reverted["index_generation"], generation)
            current = archive_services.require_current_zettel_index(root)
            self.assertTrue(current["ok"], current)
            self.assertEqual(current["generation"], generation)
            for zettel_id, title in original_titles.items():
                search = archive_services.search_archive(root, title)
                self.assertTrue(search["ok"], search)
                self.assertTrue(
                    any(
                        result.get("id") == zettel_id
                        and result.get("title") == title
                        for result in search["results"]
                    ),
                    search,
                )

    def test_missing_or_stale_index_blocks_before_canonical_or_checkpoint_write(
        self,
    ) -> None:
        for initial_index in ("missing", "stale"):
            with self.subTest(initial_index=initial_index), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "archive"
                shutil.copytree(FIXTURE, root)
                if initial_index == "stale":
                    archive_services.index_archive(root)
                    unrelated = (
                        root
                        / "zettels"
                        / "zet_20260519_fake_family_memory.md"
                    )
                    unrelated.write_bytes(
                        unrelated.read_bytes() + b"\nUnindexed unrelated edit.\n"
                    )
                    self.assertFalse(
                        archive_services.require_current_zettel_index(root)["ok"]
                    )
                plan = self.plan(root)
                target_bytes = {
                    spec.target_relative: root.joinpath(
                        *spec.target_relative.split("/")
                    ).read_bytes()
                    for spec in plan.specs
                }

                with mock.patch.object(
                    archive_services,
                    "begin_archive_index_mutation",
                    side_effect=AssertionError("untrusted index must not begin"),
                ) as begin, mock.patch.object(
                    archive_services,
                    "upsert_zettel_index_entries",
                    side_effect=AssertionError("untrusted index must not seal"),
                ) as delta:
                    result = self.execute(plan)

                self.assertFalse(result["ok"], result)
                self.assertEqual(
                    result["state"],
                    "local_recovery_index_rebuild_required",
                )
                self.assertEqual(
                    result["blockers"],
                    [archive_services.INDEX_REBUILD_REQUIRED],
                )
                self.assertFalse(result["index_current"])
                self.assertTrue(result["index_rebuild_required"])
                self.assertEqual(
                    result["index_reason_codes"],
                    [archive_services.INDEX_REBUILD_REQUIRED],
                )
                self.assertFalse(result["generated_index_updated"])
                self.assertFalse(result["index_delta_failed"])
                self.assertFalse(result["writes_performed"])
                self.assertEqual(result["checkpointed_field_count"], 0)
                for relative, before in target_bytes.items():
                    self.assertEqual(
                        root.joinpath(*relative.split("/")).read_bytes(),
                        before,
                    )
                checkpoints = (
                    root
                    / "profiles"
                    / "local"
                    / "exact-operations"
                    / "checkpoints"
                )
                self.assertFalse(list(checkpoints.glob("*.jsonl")))
                receipts = root / "receipts" / "ops" / "exact-operations"
                self.assertFalse(list(receipts.glob("*.json")))
                begin.assert_not_called()
                delta.assert_not_called()

    def test_missing_index_blocks_before_native_human_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "archive"
            shutil.copytree(FIXTURE, root)
            plan = self.plan(root)
            before = {
                spec.target_relative: root.joinpath(
                    *spec.target_relative.split("/")
                ).read_bytes()
                for spec in plan.specs
            }

            with mock.patch.object(
                local_recovery_execution,
                "_execute_exact_human_approved_write",
                side_effect=AssertionError("approval must not open"),
            ) as approval:
                result = execute_local_recovery(plan)

            self.assertFalse(result["ok"], result)
            self.assertEqual(
                result["blockers"],
                [archive_services.INDEX_REBUILD_REQUIRED],
            )
            approval.assert_not_called()
            for relative, raw in before.items():
                self.assertEqual(
                    root.joinpath(*relative.split("/")).read_bytes(),
                    raw,
                )


if __name__ == "__main__":
    unittest.main()
