from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import archive_cli, archive_services, completion_workflows
from wom_kit.exact_human_approval import (
    _claim_exact_human_approval_core as claim_exact_human_approval,
    exact_human_approval_archive_identity_sha256,
)
from wom_kit.exact_human_approval_windows import (
    ExactHumanApprovalContext,
    ExactHumanApprovalOperation,
    _ExactHumanApprovalDecision as ExactHumanApprovalDecision,
    exact_human_approval_warning_codes,
)
from wom_kit.operation_approval_binding import (
    mint_zet_approval_binding,
    promote_zet_approval_binding,
    retire_draft_approval_binding,
    warning_override_approval_binding,
    zettel_edge_approval_binding,
    zettel_edge_revert_approval_binding,
)


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
SOURCE_ID = "zet_20240504_fake_lunch_thought"
TARGET_ID = "zet_20240505_fake_company_onboarding_insight"
class SingleZettelWriterIndexLifecycleV0412Tests(unittest.TestCase):
    def copy_archive(self, parent: Path) -> Path:
        root = parent / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", root)
        return root

    def metadata(self, root: Path) -> dict[str, str]:
        conn = archive_services.connect_archive_index(
            root / archive_services.INDEX_RELATIVE_PATH,
            row_factory=True,
        )
        try:
            return archive_services.read_archive_index_metadata(conn)
        finally:
            conn.close()

    def run_cli(self, args: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = archive_cli.main(args)
        return int(code), stdout.getvalue(), stderr.getvalue()

    def exact_claim(self, root: Path, context: ExactHumanApprovalContext):
        return claim_exact_human_approval(
            root,
            context,
            ExactHumanApprovalDecision(
                approved=True,
                synthetic_acknowledged=False,
                reason_code="exact_human_approval_approved",
                plan_sha256=context.plan_sha256,
                target_binding_sha256=context.target_binding_sha256,
            ),
            bytearray(b"v" * 32),
        )

    def install_source_object(self, root: Path) -> str:
        raw = b"Reviewed v0.4.12 source fidelity fixture.\n"
        digest = hashlib.sha256(raw).hexdigest()
        object_id = f"sha256:{digest}"
        logical_key = f"objects/sha256/{digest[:2]}/{digest}"
        object_path = root.joinpath(*logical_key.split("/"))
        object_path.parent.mkdir(parents=True, exist_ok=True)
        object_path.write_bytes(raw)
        manifest = root / archive_services.ZETTEL_OBJET_LINK_MANIFEST_RELATIVE_PATH
        record = {
            "object_id": object_id,
            "sha256": digest,
            "logical_key": logical_key,
            "mime": "text/plain",
            "size_bytes": len(raw),
            "locations": [
                {
                    "provider": "local",
                    "path": logical_key,
                    "availability": "available",
                }
            ],
            "provenance": {
                "created_in": archive_services.read_archive_id(root),
                "source": "test_fixture",
            },
        }
        with manifest.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return object_id

    def run_bound_writer(self, root: Path, binding, reviewer: str, writer):
        context = binding.context(
            archive_id=archive_services.read_archive_id(root),
            reviewer_claim=reviewer,
        )
        claim = self.exact_claim(root, context)
        try:
            result = writer(claim, binding)
            if result.get("ok") is True:
                claim.finalize_succeeded()
            else:
                claim.finalize_failed(
                    str((result.get("blockers") or ["operation_blocked"])[0])
                )
            return result
        finally:
            claim.close()

    def write_edge(self, root: Path) -> dict[str, object]:
        reviewer = "person:v0412-reviewer"
        preview = archive_services.zettel_edge_write(
            root,
            from_zettel=SOURCE_ID,
            target_ref=TARGET_ID,
            edge_type="semantic",
            visibility="private",
            dry_run=True,
        )
        self.assertTrue(preview["ok"], preview)
        binding = zettel_edge_approval_binding(preview)
        return self.run_bound_writer(
            root,
            binding,
            reviewer,
            lambda claim, bound: archive_services.zettel_edge_write(
                root,
                from_zettel=SOURCE_ID,
                target_ref=TARGET_ID,
                edge_type="semantic",
                visibility="private",
                approve=True,
                reviewed_by=reviewer,
                expected_exact_approval_plan_sha256=bound.plan_sha256,
                expected_exact_approval_target_binding_sha256=(
                    bound.target_binding_sha256
                ),
                exact_human_approval_claim=claim,
            ),
        )

    def revert_edge(
        self,
        root: Path,
        receipt_path: str,
    ) -> dict[str, object]:
        reviewer = "person:v0412-reviewer"
        preview = archive_services.zettel_edge_revert(
            root,
            receipt=receipt_path,
            dry_run=True,
        )
        self.assertTrue(preview["ok"], preview)
        binding = zettel_edge_revert_approval_binding(preview)
        return self.run_bound_writer(
            root,
            binding,
            reviewer,
            lambda claim, bound: archive_services.zettel_edge_revert(
                root,
                receipt=receipt_path,
                approve=True,
                reviewed_by=reviewer,
                expected_exact_approval_plan_sha256=bound.plan_sha256,
                expected_exact_approval_target_binding_sha256=(
                    bound.target_binding_sha256
                ),
                exact_human_approval_claim=claim,
            ),
        )

    def create_draft_kwargs(self, object_id: str) -> dict[str, object]:
        return {
            "title": "v0.4.12 indexed draft fixture",
            "body": "",
            "abstract": "A reviewed index lifecycle fixture.",
            "kind": "record_note",
            "facets": {"record_type": "index_lifecycle"},
            "created_by": "ai_runtime:test",
            "source": "test_fixture",
            "creation_mode": "ai_assisted",
            "assisted_by": ["ai_runtime:test"],
            "draft_id": "zet_20260828_v0412_indexed_draft",
            "created_at": "2026-08-28T10:00:00+09:00",
            "source_fidelity_mode": "verbatim",
            "source_fidelity_audience": "private_self",
            "fidelity_source_object_id": object_id,
        }

    def create_draft(
        self,
        root: Path,
        object_id: str,
        *,
        preview: dict[str, object] | None = None,
    ) -> dict[str, object]:
        kwargs = self.create_draft_kwargs(object_id)
        preview = preview or archive_services.create_draft_zettel(
            root, dry_run=True, **kwargs
        )
        self.assertTrue(preview["ok"], preview)
        reviewer = "person:v0412-reviewer"
        bound_preview = archive_services.create_draft_zettel(
            root,
            dry_run=True,
            approved=True,
            draft_approved_by=reviewer,
            expected_body_sha256=preview["body_sha256"],
            expected_source_fidelity_plan_sha256=preview[
                "source_fidelity_plan_sha256"
            ],
            **kwargs,
        )
        self.assertTrue(bound_preview["ok"], bound_preview)
        context = ExactHumanApprovalContext(
            operation=ExactHumanApprovalOperation.create_draft,
            archive_identity_sha256=exact_human_approval_archive_identity_sha256(
                archive_services.read_archive_id(root)
            ),
            plan_sha256=(
                "sha256:" + str(bound_preview["source_fidelity_plan_sha256"])
            ),
            target_binding_sha256=(
                "sha256:" + str(bound_preview["body_sha256"])
            ),
            reviewer_claim=reviewer,
            review_binding_codes=(
                "body_digest_reviewed",
                "draft_identity_reviewed",
                "source_fidelity_reviewed",
            ),
            warning_codes=exact_human_approval_warning_codes(
                list(bound_preview.get("warnings") or [])
            ),
        )
        claim = self.exact_claim(root, context)
        try:
            result = archive_services.create_draft_zettel(
                root,
                approved=True,
                draft_approved_by=reviewer,
                expected_body_sha256=preview["body_sha256"],
                expected_source_fidelity_plan_sha256=preview[
                    "source_fidelity_plan_sha256"
                ],
                exact_human_approval_claim=claim,
                **kwargs,
            )
            if result.get("ok") is True:
                claim.finalize_succeeded()
            else:
                claim.finalize_failed(
                    str((result.get("blockers") or ["operation_blocked"])[0])
                )
            return result
        finally:
            claim.close()

    def ready_draft(self, root: Path) -> Path:
        path = root / "inbox" / "zet_20260519_draft_ai_lunch_note.md"
        frontmatter, body = archive_services.require_readable_zettel_content(path)
        frontmatter["provenance"]["created_by"] = "person:test-fixture"
        frontmatter["provenance"]["creation_mode"] = "human_written"
        frontmatter["title"] = "v0.4.12 existing lifecycle regression"
        frontmatter["kind"] = "permanent_note"
        frontmatter["promotion"] = {
            "stage": "promotion_candidate",
            "ready_for_promotion": True,
            "checklist": {
                item_id: True for item_id in PROMOTION_CHECKLIST_IDS
            },
        }
        path.write_text(
            "---\n"
            + archive_services.dump_yaml(frontmatter)
            + "---\n\n"
            + body,
            encoding="utf-8",
            newline="\n",
        )
        return path

    def publish_existing(self, root: Path, operation: str) -> dict[str, object]:
        reviewer = "person:v0412-reviewer"
        relative = "inbox/zet_20260519_draft_ai_lunch_note.md"
        if operation == "promote":
            preview = archive_services.promote_zettel_dry_run(
                root,
                relative_path=relative,
            )
            binding = (
                warning_override_approval_binding(preview)
                if preview.get("warnings")
                else promote_zet_approval_binding(preview)
            )
            return self.run_bound_writer(
                root,
                binding,
                reviewer,
                lambda claim, bound: archive_services.promote_zettel(
                    root,
                    relative_path=relative,
                    reviewed_by=reviewer,
                    allow_warnings=True,
                    expected_exact_approval_plan_sha256=bound.plan_sha256,
                    expected_exact_approval_target_binding_sha256=(
                        bound.target_binding_sha256
                    ),
                    exact_human_approval_claim=claim,
                ),
            )
        preview = archive_services.mint_zettel_dry_run(
            root,
            relative_path=relative,
        )
        binding = mint_zet_approval_binding(preview)
        return self.run_bound_writer(
            root,
            binding,
            reviewer,
            lambda claim, bound: archive_services.mint_zettel(
                root,
                relative_path=relative,
                reviewed_by=reviewer,
                allow_warnings=True,
                expected_exact_approval_plan_sha256=bound.plan_sha256,
                expected_exact_approval_target_binding_sha256=(
                    bound.target_binding_sha256
                ),
                exact_human_approval_claim=claim,
            ),
        )

    def retire_draft(self, root: Path) -> dict[str, object]:
        reviewer = "person:v0412-reviewer"
        preview = archive_services.retire_minted_draft(
            root,
            zettel_id="zet_20260519_draft_ai_lunch_note",
            approve=False,
        )
        binding = retire_draft_approval_binding(preview)
        return self.run_bound_writer(
            root,
            binding,
            reviewer,
            lambda claim, bound: archive_services.retire_minted_draft(
                root,
                zettel_id="zet_20260519_draft_ai_lunch_note",
                approve=True,
                reviewed_by=reviewer,
                expected_exact_approval_plan_sha256=bound.plan_sha256,
                expected_exact_approval_target_binding_sha256=(
                    bound.target_binding_sha256
                ),
                exact_human_approval_claim=claim,
            ),
        )

    def test_create_draft_updates_same_generation_and_replay_does_not_begin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            object_id = self.install_source_object(root)
            rebuilt = archive_services.index_archive(root)
            generation = str(rebuilt["index_generation"])
            preview = archive_services.create_draft_zettel(
                root,
                dry_run=True,
                **self.create_draft_kwargs(object_id),
            )
            self.assertTrue(preview["ok"], preview)

            created = self.create_draft(root, object_id, preview=preview)
            self.assertTrue(created["ok"], created)
            self.assertTrue(created["generated_index_updated"])
            evidence = archive_services.require_current_zettel_index(root)
            self.assertTrue(evidence["ok"], evidence)
            self.assertEqual(evidence["generation"], generation)
            conn = archive_services.connect_archive_index(
                root / archive_services.INDEX_RELATIVE_PATH,
                row_factory=True,
            )
            try:
                row = conn.execute(
                    "SELECT status, file_sha256 FROM zettels WHERE path = ?",
                    (created["path"],),
                ).fetchone()
            finally:
                conn.close()
            self.assertEqual(row["status"], "draft")
            self.assertEqual(
                row["file_sha256"],
                "sha256:"
                + hashlib.sha256((root / str(created["path"])).read_bytes()).hexdigest(),
            )

            with patch.object(
                archive_services,
                "begin_archive_index_mutation",
                wraps=archive_services.begin_archive_index_mutation,
            ) as begin:
                replay = self.create_draft(root, object_id, preview=preview)
            self.assertTrue(replay["ok"], replay)
            self.assertTrue(replay["idempotent_replay"], replay)
            self.assertEqual(replay["created_paths"], [])
            begin.assert_not_called()
            self.assertTrue(
                archive_services.require_current_zettel_index(root)["ok"]
            )

    def test_create_draft_index_delta_failure_is_durable_dirty_partial(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            object_id = self.install_source_object(root)
            generation = str(archive_services.index_archive(root)["index_generation"])
            with patch.object(
                archive_services,
                "upsert_zettel_index_entry",
                return_value=False,
            ):
                result = self.create_draft(root, object_id)
            self.assertFalse(result["ok"], result)
            self.assertEqual(result["blockers"], [archive_services.INDEX_REBUILD_REQUIRED])
            self.assertEqual(result["index_generation"], generation)
            self.assertTrue((root / str(result["path"])).is_file())
            self.assertEqual(self.metadata(root)["state"], "dirty")

    def test_edge_write_and_exact_revert_keep_same_generation_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            generation = str(archive_services.index_archive(root)["index_generation"])
            written = self.write_edge(root)
            self.assertTrue(written["ok"], written)
            self.assertTrue(written["generated_index_updated"])
            self.assertEqual(
                archive_services.require_current_zettel_index(root)["generation"],
                generation,
            )

            reverted = self.revert_edge(root, str(written["receipt_path"]))
            self.assertTrue(reverted["ok"], reverted)
            self.assertTrue(reverted["generated_index_updated"])
            evidence = archive_services.require_current_zettel_index(root)
            self.assertTrue(evidence["ok"], evidence)
            self.assertEqual(evidence["generation"], generation)
            conn = archive_services.connect_archive_index(
                root / archive_services.INDEX_RELATIVE_PATH,
                row_factory=True,
            )
            try:
                remaining = conn.execute(
                    "SELECT COUNT(*) FROM edges WHERE from_id = ? AND to_id = ?",
                    (SOURCE_ID, TARGET_ID),
                ).fetchone()[0]
            finally:
                conn.close()
            self.assertEqual(remaining, 0)

    def test_edge_receipt_failure_restores_exact_bytes_and_reseals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            generation = str(archive_services.index_archive(root)["index_generation"])
            source = root / "zettels" / f"{SOURCE_ID}.md"
            original = source.read_bytes()
            with patch.object(
                archive_services,
                "write_json_new_file",
                side_effect=OSError("synthetic receipt failure"),
            ), patch.object(
                archive_services,
                "upsert_zettel_index_entry",
                wraps=archive_services.upsert_zettel_index_entry,
            ) as upsert:
                with self.assertRaisesRegex(OSError, "synthetic receipt failure"):
                    self.write_edge(root)
            self.assertEqual(source.read_bytes(), original)
            upsert.assert_called_once()
            evidence = archive_services.require_current_zettel_index(root)
            self.assertTrue(evidence["ok"], evidence)
            self.assertEqual(evidence["generation"], generation)

    def test_edge_write_and_revert_delta_failures_leave_same_generation_dirty(self) -> None:
        with self.subTest(operation="write"), tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            generation = str(archive_services.index_archive(root)["index_generation"])
            with patch.object(
                archive_services,
                "upsert_zettel_index_entry",
                return_value=False,
            ):
                written = self.write_edge(root)
            self.assertFalse(written["ok"], written)
            self.assertEqual(written["blockers"], [archive_services.INDEX_REBUILD_REQUIRED])
            self.assertEqual(written["index_generation"], generation)
            self.assertEqual(self.metadata(root)["state"], "dirty")
            self.assertTrue((root / str(written["receipt_path"])).is_file())

        with self.subTest(operation="revert"), tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            generation = str(archive_services.index_archive(root)["index_generation"])
            written = self.write_edge(root)
            self.assertTrue(written["ok"], written)
            with patch.object(
                archive_services,
                "upsert_zettel_index_entry",
                return_value=False,
            ):
                reverted = self.revert_edge(root, str(written["receipt_path"]))
            self.assertFalse(reverted["ok"], reverted)
            self.assertEqual(reverted["blockers"], [archive_services.INDEX_REBUILD_REQUIRED])
            self.assertEqual(reverted["index_generation"], generation)
            self.assertEqual(self.metadata(root)["state"], "dirty")
            self.assertTrue((root / str(reverted["revert_receipt_path"])).is_file())

    def test_edge_write_and_revert_cas_never_overwrite_racing_bytes(self) -> None:
        for operation in ("write", "revert"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as tmp:
                root = self.copy_archive(Path(tmp))
                archive_services.index_archive(root)
                source = root / "zettels" / f"{SOURCE_ID}.md"
                if operation == "revert":
                    written = self.write_edge(root)
                    self.assertTrue(written["ok"], written)
                    receipt_path = str(written["receipt_path"])
                else:
                    receipt_path = ""
                foreign_bytes = (
                    source.read_bytes()
                    + f"\nforeign-{operation}-between-read-and-cas\n".encode(
                        "ascii"
                    )
                )
                real_cas = (
                    archive_services._replace_regular_file_bytes_compare_and_swap
                )
                injected = False

                def race_then_cas(*args, **kwargs):
                    nonlocal injected
                    expected_prefix = (
                        "zettel_edge_revert"
                        if operation == "revert"
                        else "zettel_edge"
                    )
                    if (
                        not injected
                        and kwargs.get("error_prefix") == expected_prefix
                    ):
                        injected = True
                        Path(args[1]).write_bytes(foreign_bytes)
                    return real_cas(*args, **kwargs)

                with patch.object(
                    archive_services,
                    "_replace_regular_file_bytes_compare_and_swap",
                    side_effect=race_then_cas,
                ):
                    with self.assertRaisesRegex(
                        OSError,
                        "canonical_changed_before_swap",
                    ):
                        if operation == "revert":
                            self.revert_edge(root, receipt_path)
                        else:
                            self.write_edge(root)

                self.assertTrue(injected)
                self.assertEqual(source.read_bytes(), foreign_bytes)
                self.assertEqual(self.metadata(root)["state"], "dirty")
                if operation == "write":
                    self.assertEqual(
                        list((root / "receipts" / "edges").glob(
                            "*.zettel-edge.json"
                        )),
                        [],
                    )
                else:
                    self.assertEqual(
                        list(
                            (root / "receipts" / "edges" / "reverts").glob(
                                "*.zettel-edge-revert.json"
                            )
                        ),
                        [],
                    )

    def test_edge_write_and_revert_rollback_never_overwrite_post_cas_edit(
        self,
    ) -> None:
        for operation in ("write", "revert"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as tmp:
                root = self.copy_archive(Path(tmp))
                archive_services.index_archive(root)
                source = root / "zettels" / f"{SOURCE_ID}.md"
                if operation == "revert":
                    written = self.write_edge(root)
                    self.assertTrue(written["ok"], written)
                    receipt_path = str(written["receipt_path"])
                    receipt_suffix = ".zettel-edge-revert.json"
                else:
                    receipt_path = ""
                    receipt_suffix = ".zettel-edge.json"
                real_write_json = archive_services.write_json_new_file
                foreign_bytes: bytes | None = None

                def foreign_edit_then_fail_receipt(path, document):
                    nonlocal foreign_bytes
                    if str(Path(path).name).endswith(receipt_suffix):
                        foreign_bytes = (
                            source.read_bytes()
                            + f"\nforeign-{operation}-after-cas\n".encode("ascii")
                        )
                        source.write_bytes(foreign_bytes)
                        raise OSError("synthetic edge receipt race")
                    return real_write_json(path, document)

                with patch.object(
                    archive_services,
                    "write_json_new_file",
                    side_effect=foreign_edit_then_fail_receipt,
                ):
                    with self.assertRaisesRegex(
                        OSError,
                        "synthetic edge receipt race",
                    ):
                        if operation == "revert":
                            self.revert_edge(root, receipt_path)
                        else:
                            self.write_edge(root)

                self.assertIsNotNone(foreign_bytes)
                self.assertEqual(source.read_bytes(), foreign_bytes)
                self.assertEqual(self.metadata(root)["state"], "dirty")
                if operation == "write":
                    self.assertEqual(
                        list(
                            (root / "receipts" / "edges").glob(
                                "*.zettel-edge.json"
                            )
                        ),
                        [],
                    )
                else:
                    self.assertEqual(
                        list(
                            (root / "receipts" / "edges" / "reverts").glob(
                                "*.zettel-edge-revert.json"
                            )
                        ),
                        [],
                    )

    def test_retire_cas_delete_restores_racing_occupant_without_unlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            draft = self.ready_draft(root)
            archive_services.index_archive(root)
            minted = self.publish_existing(root, "mint")
            self.assertTrue(minted["ok"], minted)
            foreign_bytes = (
                draft.read_bytes()
                + b"\nforeign-retire-between-read-and-namespace-move\n"
            )
            real_move = archive_services._move_activity_group_entry_no_replace
            injected = False

            def race_then_move(binding, source, destination):
                nonlocal injected
                if not injected:
                    injected = True
                    draft.write_bytes(foreign_bytes)
                return real_move(binding, source, destination)

            with patch.object(
                archive_services,
                "_move_activity_group_entry_no_replace",
                side_effect=race_then_move,
            ):
                with self.assertRaisesRegex(
                    OSError,
                    "retired_draft_source_changed_during_delete",
                ):
                    self.retire_draft(root)

            self.assertTrue(injected)
            self.assertEqual(draft.read_bytes(), foreign_bytes)
            self.assertEqual(self.metadata(root)["state"], "dirty")
            self.assertFalse(
                (
                    root
                    / "receipts"
                    / "mint"
                    / "retired-drafts"
                    / "zet_20260519_draft_ai_lunch_note.retire-draft.json"
                ).exists()
            )

    def test_retire_cas_delete_rejects_byte_identical_replacement_identity(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            draft = self.ready_draft(root)
            archive_services.index_archive(root)
            minted = self.publish_existing(root, "mint")
            self.assertTrue(minted["ok"], minted)
            original_bytes = draft.read_bytes()
            original_identity = (
                int(draft.stat().st_dev),
                int(draft.stat().st_ino),
            )
            replacement_identity: tuple[int, int] | None = None
            real_move = archive_services._move_activity_group_entry_no_replace
            injected = False

            def replace_identity_then_move(binding, source, destination):
                nonlocal injected, replacement_identity
                if not injected:
                    injected = True
                    replacement = draft.with_name(draft.name + ".racing-replacement")
                    replacement.write_bytes(original_bytes)
                    os.replace(replacement, draft)
                    replacement_identity = (
                        int(draft.stat().st_dev),
                        int(draft.stat().st_ino),
                    )
                return real_move(binding, source, destination)

            with patch.object(
                archive_services,
                "_move_activity_group_entry_no_replace",
                side_effect=replace_identity_then_move,
            ):
                with self.assertRaisesRegex(
                    OSError,
                    "retired_draft_source_changed_during_delete",
                ):
                    self.retire_draft(root)

            self.assertTrue(injected)
            self.assertIsNotNone(replacement_identity)
            self.assertNotEqual(replacement_identity, original_identity)
            self.assertEqual(draft.read_bytes(), original_bytes)
            self.assertFalse(
                (
                    root
                    / "receipts"
                    / "mint"
                    / "retired-drafts"
                    / "zet_20260519_draft_ai_lunch_note.retire-draft.json"
                ).exists()
            )

    def test_seal_rejects_missing_changed_or_replaced_manifest_and_stays_dirty(self) -> None:
        for mutation in ("missing", "content_changed", "byte_identical_replaced"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root = self.copy_archive(Path(tmp))
                generation = str(
                    archive_services.index_archive(root)["index_generation"]
                )
                source = root / "zettels" / f"{SOURCE_ID}.md"
                frontmatter, body = archive_services.require_readable_zettel_content(
                    source
                )
                source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
                manifest = root / archive_services.ZETTEL_OBJET_LINK_MANIFEST_RELATIVE_PATH
                manifest_bytes = manifest.read_bytes()

                lease_token = archive_services.begin_archive_index_mutation(
                    root,
                    expected_generation=generation,
                )
                if mutation == "missing":
                    manifest.unlink()
                elif mutation == "content_changed":
                    manifest.write_bytes(manifest_bytes + b"\n")
                else:
                    archive_services.write_bytes_atomic(manifest, manifest_bytes)

                updated = archive_services.upsert_zettel_index_entry(
                    root,
                    source,
                    frontmatter,
                    body,
                    expected_generation=generation,
                    expected_file_sha256=source_sha256,
                    lease_token=lease_token,
                )

                self.assertFalse(updated)
                metadata = self.metadata(root)
                self.assertEqual(metadata["state"], "dirty")
                self.assertEqual(metadata["generation"], generation)
                self.assertFalse(
                    archive_services.reseal_archive_index_mutation_without_delta(
                        root,
                        expected_generation=generation,
                        lease_token=lease_token,
                    )
                )

    def test_existing_mint_promote_retire_lifecycle_regression(self) -> None:
        for operation in ("promote", "mint"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as tmp:
                root = self.copy_archive(Path(tmp))
                self.ready_draft(root)
                generation = str(
                    archive_services.index_archive(root)["index_generation"]
                )
                result = self.publish_existing(root, operation)
                self.assertTrue(result["ok"], result)
                evidence = archive_services.require_current_zettel_index(root)
                self.assertTrue(evidence["ok"], evidence)
                self.assertEqual(evidence["generation"], generation)

        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            self.ready_draft(root)
            generation = str(archive_services.index_archive(root)["index_generation"])
            minted = self.publish_existing(root, "mint")
            self.assertTrue(minted["ok"], minted)
            retired = self.retire_draft(root)
            self.assertTrue(retired["ok"], retired)
            evidence = archive_services.require_current_zettel_index(root)
            self.assertTrue(evidence["ok"], evidence)
            self.assertEqual(evidence["generation"], generation)

    def test_open_writer_previews_fail_closed_on_missing_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            object_id = self.install_source_object(root)

            edge = archive_services.zettel_edge_write(
                root,
                from_zettel=SOURCE_ID,
                target_ref=TARGET_ID,
                edge_type="semantic",
                visibility="private",
                dry_run=True,
            )
            self.assertFalse(edge["ok"], edge)
            self.assertIn(
                archive_services.INDEX_REBUILD_REQUIRED,
                edge["blockers"],
            )

            initial_draft = archive_services.create_draft_zettel(
                root,
                dry_run=True,
                **self.create_draft_kwargs(object_id),
            )
            self.assertTrue(initial_draft["ok"], initial_draft)
            approval_draft = archive_services.create_draft_zettel(
                root,
                dry_run=True,
                approved=True,
                draft_approved_by="person:v0412-reviewer",
                expected_body_sha256=initial_draft["body_sha256"],
                expected_source_fidelity_plan_sha256=initial_draft[
                    "source_fidelity_plan_sha256"
                ],
                **self.create_draft_kwargs(object_id),
            )
            self.assertFalse(approval_draft["ok"], approval_draft)
            self.assertIn(
                archive_services.INDEX_REBUILD_REQUIRED,
                approval_draft["blockers"],
            )

            self.ready_draft(root)
            promoted = archive_services.promote_zettel_dry_run(
                root,
                relative_path="inbox/zet_20260519_draft_ai_lunch_note.md",
            )
            minted = archive_services.mint_zettel_dry_run(
                root,
                relative_path="inbox/zet_20260519_draft_ai_lunch_note.md",
            )
            self.assertFalse(promoted["ok"], promoted)
            self.assertFalse(minted["ok"], minted)
            self.assertIn(
                archive_services.INDEX_REBUILD_MINT_BLOCKER,
                promoted["blockers"],
            )
            self.assertIn(
                archive_services.INDEX_REBUILD_MINT_BLOCKER,
                minted["blockers"],
            )

            objet_link = completion_workflows.zettel_objet_link_plan(
                root,
                zettel_id=SOURCE_ID,
                object_id=object_id,
                role="evidence",
            )
            self.assertFalse(objet_link["ok"], objet_link)
            self.assertIn(
                "zettel_identity_projection_stale",
                objet_link["blockers"],
            )

    def test_edge_approval_cli_blocks_before_binding_and_native_broker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            with (
                patch.object(
                    archive_cli,
                    "_execute_exact_human_approved_write",
                    side_effect=AssertionError("native broker must not open"),
                ) as native_broker,
                patch.object(
                    archive_cli.operation_approval_binding,
                    "zettel_edge_approval_binding",
                    side_effect=AssertionError("approval binding must not run"),
                ) as approval_binding,
            ):
                code, stdout, stderr = self.run_cli(
                    [
                        "zettel-edge",
                        str(root),
                        "--from-zettel",
                        SOURCE_ID,
                        "--target",
                        TARGET_ID,
                        "--edge-type",
                        "semantic",
                        "--visibility",
                        "private",
                        "--approve",
                        "--reviewed-by",
                        "person:v0412-reviewer",
                        "--format",
                        "json",
                    ]
                )

            self.assertEqual(code, 1, (stdout, stderr))
            result = json.loads(stdout)
            self.assertIn(
                archive_services.INDEX_REBUILD_REQUIRED,
                result["blockers"],
            )
            self.assertEqual(result["files_written"], [])
            native_broker.assert_not_called()
            approval_binding.assert_not_called()

    def test_other_open_writer_clis_block_before_native_broker(self) -> None:
        with self.subTest(operation="create_draft"), tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            object_id = self.install_source_object(root)
            kwargs = self.create_draft_kwargs(object_id)
            initial = archive_services.create_draft_zettel(
                root,
                dry_run=True,
                **kwargs,
            )
            self.assertTrue(initial["ok"], initial)
            with patch.object(
                archive_cli,
                "_execute_exact_human_approved_write",
                side_effect=AssertionError("native broker must not open"),
            ) as native_broker:
                code, stdout, stderr = self.run_cli(
                    [
                        "create-draft",
                        str(root),
                        "--title",
                        str(kwargs["title"]),
                        "--abstract",
                        str(kwargs["abstract"]),
                        "--kind",
                        str(kwargs["kind"]),
                        "--facet",
                        "record_type=index_lifecycle",
                        "--created-by",
                        str(kwargs["created_by"]),
                        "--source",
                        str(kwargs["source"]),
                        "--creation-mode",
                        str(kwargs["creation_mode"]),
                        "--assisted-by",
                        "ai_runtime:test",
                        "--draft-id",
                        str(kwargs["draft_id"]),
                        "--created-at",
                        str(kwargs["created_at"]),
                        "--source-fidelity",
                        str(kwargs["source_fidelity_mode"]),
                        "--fidelity-audience",
                        str(kwargs["source_fidelity_audience"]),
                        "--fidelity-source-object-id",
                        object_id,
                        "--approve",
                        "--draft-approved-by",
                        "person:v0412-reviewer",
                        "--expected-body-sha256",
                        str(initial["body_sha256"]),
                        "--expected-source-fidelity-plan-sha256",
                        str(initial["source_fidelity_plan_sha256"]),
                        "--format",
                        "json",
                    ]
                )
            self.assertEqual(code, 1, (stdout, stderr))
            self.assertEqual(json.loads(stdout)["files_written"], [])
            native_broker.assert_not_called()

        for operation in ("promote", "mint-zet"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as tmp:
                root = self.copy_archive(Path(tmp))
                self.ready_draft(root)
                with patch.object(
                    archive_cli,
                    "_execute_exact_human_approved_write",
                    side_effect=AssertionError("native broker must not open"),
                ) as native_broker:
                    code, stdout, stderr = self.run_cli(
                        [
                            operation,
                            str(root),
                            "--path",
                            "inbox/zet_20260519_draft_ai_lunch_note.md",
                            "--approve",
                            "--reviewed-by",
                            "person:v0412-reviewer",
                            "--allow-warnings",
                            "--format",
                            "json",
                        ]
                    )
                self.assertEqual(code, 1, (stdout, stderr))
                self.assertEqual(json.loads(stdout)["files_written"], [])
                native_broker.assert_not_called()

        with self.subTest(operation="zettel_objet_link"), tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            object_id = self.install_source_object(root)
            with patch.object(
                archive_cli,
                "_execute_zettel_objet_link_exact_human_approved_write",
                side_effect=AssertionError("native broker must not open"),
            ) as native_broker:
                code, stdout, stderr = self.run_cli(
                    [
                        "zettel-objet-link",
                        str(root),
                        "--zettel-id",
                        SOURCE_ID,
                        "--object-id",
                        object_id,
                        "--role",
                        "evidence",
                        "--approve",
                        "--reviewed-by",
                        "person:v0412-reviewer",
                        "--expected-plan-sha256",
                        "a" * 64,
                        "--format",
                        "json",
                    ]
                )
            self.assertEqual(code, 1, (stdout, stderr))
            self.assertEqual(json.loads(stdout)["files_written"], [])
            native_broker.assert_not_called()

    def test_edge_revert_preview_and_retire_cli_block_before_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            archive_services.index_archive(root)
            written = self.write_edge(root)
            self.assertTrue(written["ok"], written)
            (root / archive_services.INDEX_RELATIVE_PATH).unlink()

            revert = archive_services.zettel_edge_revert(
                root,
                receipt=str(written["receipt_path"]),
                dry_run=True,
            )
            self.assertFalse(revert["ok"], revert)
            self.assertIn(
                archive_services.INDEX_REBUILD_REQUIRED,
                revert["blockers"],
            )
            self.assertEqual(revert["files_written"], [])
            with patch.object(
                archive_cli,
                "_execute_exact_human_approved_write",
                side_effect=AssertionError("native broker must not open"),
            ) as native_broker:
                code, stdout, stderr = self.run_cli(
                    [
                        "revert-edge",
                        str(root),
                        "--receipt",
                        str(written["receipt_path"]),
                        "--approve",
                        "--exact-local",
                        "--reviewed-by",
                        "person:v0412-reviewer",
                        "--format",
                        "json",
                    ]
                )
            self.assertEqual(code, 1, (stdout, stderr))
            self.assertEqual(json.loads(stdout)["files_written"], [])
            native_broker.assert_not_called()

        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            self.ready_draft(root)
            archive_services.index_archive(root)
            minted = self.publish_existing(root, "mint")
            self.assertTrue(minted["ok"], minted)
            unrelated = root / "zettels" / f"{TARGET_ID}.md"
            unrelated.write_bytes(unrelated.read_bytes() + b"\n")
            retire_preview = archive_services.retire_minted_draft(
                root,
                zettel_id="zet_20260519_draft_ai_lunch_note",
                approve=False,
            )
            self.assertFalse(retire_preview["ok"], retire_preview)
            self.assertIn(
                archive_services.INDEX_REBUILD_REQUIRED,
                retire_preview["blockers"],
            )
            with patch.object(
                archive_cli,
                "_execute_exact_human_approved_write",
                side_effect=AssertionError("native broker must not open"),
            ) as native_broker:
                code, stdout, stderr = self.run_cli(
                    [
                        "retire-draft",
                        str(root),
                        "--zettel-id",
                        "zet_20260519_draft_ai_lunch_note",
                        "--approve",
                        "--reviewed-by",
                        "person:v0412-reviewer",
                        "--format",
                        "json",
                    ]
                )

            self.assertEqual(code, 1, (stdout, stderr))
            result = json.loads(stdout)
            self.assertIn(
                archive_services.INDEX_REBUILD_REQUIRED,
                result["reason_codes"],
            )
            self.assertEqual(result["files_written"], [])
            native_broker.assert_not_called()

    def test_publish_and_retire_block_concurrent_rebuild_and_dirty_same_generation(self) -> None:
        for operation in ("promote", "mint"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as tmp:
                root = self.copy_archive(Path(tmp))
                draft = self.ready_draft(root)
                draft_bytes = draft.read_bytes()
                original_generation = str(
                    archive_services.index_archive(root)["index_generation"]
                )
                rebuild_attempts: list[str] = []

                def rebuild_then_fail_upsert(*_args, **_kwargs) -> bool:
                    rebuild_attempts.append("attempted")
                    with self.assertRaisesRegex(
                        archive_services.ArchiveServiceError,
                        "archive_index_mutation_in_progress",
                    ):
                        archive_services.index_archive(root)
                    return False

                with patch.object(
                    archive_services,
                    "upsert_zettel_index_entry",
                    side_effect=rebuild_then_fail_upsert,
                ):
                    result = self.publish_existing(root, operation)

                self.assertFalse(result["ok"], result)
                self.assertEqual(
                    result["blockers"],
                    [archive_services.INDEX_REBUILD_REQUIRED],
                )
                self.assertTrue(result["index_marked_dirty"])
                self.assertEqual(rebuild_attempts, ["attempted"])
                self.assertEqual(draft.read_bytes(), draft_bytes)
                metadata = self.metadata(root)
                self.assertEqual(metadata["state"], "dirty")
                self.assertEqual(metadata["generation"], original_generation)

        with self.subTest(operation="retire"), tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            draft = self.ready_draft(root)
            archive_services.index_archive(root)
            minted = self.publish_existing(root, "mint")
            self.assertTrue(minted["ok"], minted)
            canonical = root / str(minted["canonical_path"])
            canonical_bytes = canonical.read_bytes()
            original_generation = self.metadata(root)["generation"]
            rebuild_attempts: list[str] = []

            def rebuild_then_fail_delete(*_args, **_kwargs) -> bool:
                rebuild_attempts.append("attempted")
                with self.assertRaisesRegex(
                    archive_services.ArchiveServiceError,
                    "archive_index_mutation_in_progress",
                ):
                    archive_services.index_archive(root)
                return False

            with patch.object(
                archive_services,
                "delete_zettel_index_entry",
                side_effect=rebuild_then_fail_delete,
            ):
                result = self.retire_draft(root)

            self.assertFalse(result["ok"], result)
            self.assertEqual(
                    result["blockers"],
                    [archive_services.INDEX_REBUILD_REQUIRED],
                )
            self.assertTrue(result["index_marked_dirty"])
            self.assertEqual(rebuild_attempts, ["attempted"])
            self.assertFalse(draft.exists())
            self.assertEqual(canonical.read_bytes(), canonical_bytes)
            self.assertTrue((root / str(result["retire_receipt_path"])).is_file())
            metadata = self.metadata(root)
            self.assertEqual(metadata["state"], "dirty")
            self.assertEqual(metadata["generation"], original_generation)


if __name__ == "__main__":
    unittest.main()
