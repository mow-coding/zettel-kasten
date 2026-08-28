from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wom_kit import archive_services
from wom_kit.exact_human_approval import (
    _claim_exact_human_approval_core as claim_exact_human_approval,
)
from wom_kit.exact_human_approval_windows import (
    _ExactHumanApprovalDecision as ExactHumanApprovalDecision,
)
from wom_kit.operation_approval_binding import (
    mint_zet_approval_binding,
    retire_draft_approval_binding,
    zettel_edge_approval_binding,
)


KIT_ROOT = Path(__file__).resolve().parents[1]
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


class Letter137WriterToctouTests(unittest.TestCase):
    def copy_archive(self, parent: Path) -> Path:
        root = parent / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", root)
        return root

    def claim(self, root: Path, binding, reviewer: str):
        context = binding.context(
            archive_id=archive_services.read_archive_id(root),
            reviewer_claim=reviewer,
        )
        claim = claim_exact_human_approval(
            root,
            context,
            ExactHumanApprovalDecision(
                approved=True,
                synthetic_acknowledged=False,
                reason_code="exact_human_approval_approved",
                plan_sha256=context.plan_sha256,
                target_binding_sha256=context.target_binding_sha256,
            ),
            bytearray(b"t" * 32),
        )
        self.addCleanup(claim.close)
        return claim

    def ready_draft(self, root: Path) -> Path:
        path = root / "inbox" / "zet_20260519_draft_ai_lunch_note.md"
        frontmatter, _body = archive_services.require_readable_zettel_content(path)
        frontmatter["provenance"]["created_by"] = "person:test-fixture"
        frontmatter["provenance"]["creation_mode"] = "human_written"
        frontmatter["title"] = "Letter 137 TOCTOU fixture"
        frontmatter["kind"] = "permanent_note"
        frontmatter["promotion"] = {
            "stage": "promotion_candidate",
            "ready_for_promotion": True,
            "checklist": {
                item_id: True for item_id in PROMOTION_CHECKLIST_IDS
            },
        }
        body = "Writer boundary TOCTOU fixture body. " * 30
        path.write_text(
            "---\n"
            + archive_services.dump_yaml(frontmatter)
            + "---\n\n"
            + body,
            encoding="utf-8",
            newline="\n",
        )
        return path

    def mint_ready_draft(self, root: Path) -> dict:
        preview = archive_services.mint_zettel_dry_run(
            root,
            relative_path="inbox/zet_20260519_draft_ai_lunch_note.md",
        )
        binding = mint_zet_approval_binding(preview)
        claim = self.claim(root, binding, "person:test")
        result = archive_services.mint_zettel(
            root,
            relative_path="inbox/zet_20260519_draft_ai_lunch_note.md",
            reviewed_by="person:test",
            allow_warnings=True,
            expected_exact_approval_plan_sha256=binding.plan_sha256,
            expected_exact_approval_target_binding_sha256=(
                binding.target_binding_sha256
            ),
            exact_human_approval_claim=claim,
        )
        self.assertTrue(result["ok"], result)
        claim.finalize_succeeded()
        return result

    def test_edge_change_after_claim_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            indexed = archive_services.index_archive(root)
            self.assertTrue(indexed["ok"], indexed)
            source_id = "zet_20240504_fake_lunch_thought"
            target_id = "zet_20240505_fake_company_onboarding_insight"
            source_path = root / "zettels" / f"{source_id}.md"
            preview = archive_services.zettel_edge_write(
                root,
                from_zettel=source_id,
                target_ref=target_id,
                edge_type="semantic",
                visibility="private",
                dry_run=True,
            )
            binding = zettel_edge_approval_binding(preview)
            claim = self.claim(root, binding, "person:test")
            original_assert = claim.assert_ready_for_context
            external_bytes = source_path.read_bytes() + b"\nexternal-change\n"

            def approve_then_change(context):
                reference = original_assert(context)
                source_path.write_bytes(external_bytes)
                return reference

            with patch.object(
                claim,
                "assert_ready_for_context",
                side_effect=approve_then_change,
            ):
                with self.assertRaisesRegex(
                    archive_services.ArchiveServiceError,
                    "zettel_edge_source_changed_after_approval",
                ):
                    archive_services.zettel_edge_write(
                        root,
                        from_zettel=source_id,
                        target_ref=target_id,
                        edge_type="semantic",
                        visibility="private",
                        approve=True,
                        reviewed_by="person:test",
                        expected_exact_approval_plan_sha256=(
                            binding.plan_sha256
                        ),
                        expected_exact_approval_target_binding_sha256=(
                            binding.target_binding_sha256
                        ),
                        exact_human_approval_claim=claim,
                    )

            self.assertEqual(source_path.read_bytes(), external_bytes)
            self.assertFalse((root / preview["receipt_path"]).exists())
            self.assertEqual(claim.status, "started")

    def test_retire_change_after_claim_is_not_unlinked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_archive(Path(tmp))
            draft_path = self.ready_draft(root)
            archive_services.index_archive(root)
            self.mint_ready_draft(root)
            preview = archive_services.retire_minted_draft(
                root,
                zettel_id="zet_20260519_draft_ai_lunch_note",
                approve=False,
            )
            binding = retire_draft_approval_binding(preview)
            claim = self.claim(root, binding, "person:test")
            original_assert = claim.assert_ready_for_context
            external_bytes = draft_path.read_bytes() + b"\nexternal-change\n"

            def approve_then_change(context):
                reference = original_assert(context)
                draft_path.write_bytes(external_bytes)
                return reference

            with patch.object(
                claim,
                "assert_ready_for_context",
                side_effect=approve_then_change,
            ):
                with self.assertRaisesRegex(
                    archive_services.ArchiveServiceError,
                    "(?:retired_draft_source_changed_after_approval|"
                    "archive_index_rebuild_required)",
                ):
                    archive_services.retire_minted_draft(
                        root,
                        zettel_id="zet_20260519_draft_ai_lunch_note",
                        reviewed_by="person:test",
                        approve=True,
                        expected_exact_approval_plan_sha256=(
                            binding.plan_sha256
                        ),
                        expected_exact_approval_target_binding_sha256=(
                            binding.target_binding_sha256
                        ),
                        exact_human_approval_claim=claim,
                    )

            self.assertEqual(draft_path.read_bytes(), external_bytes)
            self.assertFalse((root / preview["retire_receipt_path"]).exists())
            self.assertEqual(claim.status, "started")
            self.assertEqual(
                archive_services.require_current_zettel_index(root)[
                    "blockers"
                ],
                [archive_services.INDEX_REBUILD_REQUIRED],
            )


if __name__ == "__main__":
    unittest.main()
