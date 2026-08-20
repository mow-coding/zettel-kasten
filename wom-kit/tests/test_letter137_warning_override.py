from __future__ import annotations

import copy
import hashlib
import json
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
    promote_zet_approval_binding,
    warning_override_approval_binding,
)


KIT_ROOT = Path(__file__).resolve().parents[1]
DRAFT_RELATIVE = "inbox/zet_20260519_draft_ai_lunch_note.md"
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


def archive_snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class Letter137WarningOverrideTests(unittest.TestCase):
    def prepare_archive(self, parent: Path, *, warning: bool = True) -> Path:
        root = parent / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", root)
        draft = root / DRAFT_RELATIVE
        frontmatter, _body = archive_services.require_readable_zettel_content(
            draft
        )
        frontmatter["provenance"]["created_by"] = "person:test-fixture"
        frontmatter["provenance"]["creation_mode"] = "human_written"
        frontmatter["title"] = "Warning override fixture"
        frontmatter["abstract"] = (
            "A bounded first read for the warning override fixture."
        )
        frontmatter["kind"] = (
            "unknown_warning_kind" if warning else "permanent_note"
        )
        frontmatter["promotion"] = {
            "stage": "promotion_candidate",
            "ready_for_promotion": True,
            "checklist": {
                item_id: True for item_id in PROMOTION_CHECKLIST_IDS
            },
        }
        body = "Warning override fixture body. " * 30
        draft.write_text(
            "---\n"
            + archive_services.dump_yaml(frontmatter)
            + "---\n\n"
            + body,
            encoding="utf-8",
            newline="\n",
        )
        archive_services.index_archive(root)
        return root

    def preview(self, root: Path) -> dict:
        result = archive_services.promote_zettel_dry_run(
            root,
            relative_path=DRAFT_RELATIVE,
        )
        self.assertTrue(result["ok"], result)
        return result

    def claim(self, root: Path, binding):
        context = binding.context(
            archive_id=archive_services.read_archive_id(root),
            reviewer_claim="person:test",
        )
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
            bytearray(b"w" * 32),
        )

    def promote_with_claim(
        self,
        root: Path,
        binding,
        claim,
        *,
        allow_warnings: bool = True,
    ):
        return archive_services.promote_zettel(
            root,
            relative_path=DRAFT_RELATIVE,
            reviewed_by="person:test",
            allow_warnings=allow_warnings,
            expected_exact_approval_plan_sha256=binding.plan_sha256,
            expected_exact_approval_target_binding_sha256=(
                binding.target_binding_sha256
            ),
            exact_human_approval_claim=claim,
        )

    def test_binding_is_deterministic_and_covers_warning_source_and_target(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.prepare_archive(Path(tmp))
            plan = self.preview(root)
            self.assertTrue(plan["warnings"])
            first = warning_override_approval_binding(plan)
            second = warning_override_approval_binding(self.preview(root))
            self.assertEqual(first, second)
            self.assertEqual(first.operation.value, "warning_override")
            self.assertEqual(len(first.warning_codes), 1)
            self.assertTrue(first.warning_codes[0].startswith("warning_set_"))
            self.assertNotIn(
                "unknown_warning_kind",
                json.dumps(first.public_document()),
            )

            changed_warning = copy.deepcopy(plan)
            changed_warning["warnings"].append("changed private warning")
            changed_warning["receipt_preview"]["warnings"] = list(
                changed_warning["warnings"]
            )
            warning_binding = warning_override_approval_binding(
                changed_warning
            )
            self.assertNotEqual(
                first.plan_sha256,
                warning_binding.plan_sha256,
            )

            changed_source = copy.deepcopy(plan)
            changed_source["source_sha256"] = "1" * 64
            changed_source["receipt_preview"]["source"]["sha256"] = (
                "1" * 64
            )
            source_binding = warning_override_approval_binding(changed_source)
            self.assertNotEqual(
                first.target_binding_sha256,
                source_binding.target_binding_sha256,
            )

            changed_target = copy.deepcopy(plan)
            changed_target["proposed_canonical_path"] = (
                "zettels/changed-target.md"
            )
            changed_target["receipt_preview"]["target"]["path"] = (
                "zettels/changed-target.md"
            )
            target_binding = warning_override_approval_binding(changed_target)
            self.assertNotEqual(
                first.target_binding_sha256,
                target_binding.target_binding_sha256,
            )

    def test_allow_warnings_without_claim_blocks_with_zero_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.prepare_archive(Path(tmp))
            binding = warning_override_approval_binding(self.preview(root))
            before = archive_snapshot(root)

            with self.assertRaisesRegex(
                archive_services.ArchiveServiceError,
                "exact_human_approval_required",
            ):
                archive_services.promote_zettel(
                    root,
                    relative_path=DRAFT_RELATIVE,
                    reviewed_by="person:test",
                    allow_warnings=True,
                    expected_exact_approval_plan_sha256=binding.plan_sha256,
                    expected_exact_approval_target_binding_sha256=(
                        binding.target_binding_sha256
                    ),
                )

            self.assertEqual(archive_snapshot(root), before)

    def test_changed_warning_blocks_with_zero_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.prepare_archive(Path(tmp))
            binding = warning_override_approval_binding(self.preview(root))
            claim = self.claim(root, binding)
            self.addCleanup(claim.close)
            before = archive_snapshot(root)
            real_dry_run = archive_services.promote_zettel_dry_run

            def changed_warning(*args, **kwargs):
                result = copy.deepcopy(real_dry_run(*args, **kwargs))
                result["warnings"].append("changed private warning")
                result["receipt_preview"]["warnings"] = list(
                    result["warnings"]
                )
                return result

            with patch.object(
                archive_services,
                "promote_zettel_dry_run",
                side_effect=changed_warning,
            ):
                with self.assertRaisesRegex(
                    archive_services.ArchiveServiceError,
                    "operation_approval_binding_mismatch",
                ):
                    self.promote_with_claim(root, binding, claim)

            self.assertEqual(archive_snapshot(root), before)
            self.assertEqual(claim.status, "started")

    def test_changed_source_blocks_with_zero_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.prepare_archive(Path(tmp))
            binding = warning_override_approval_binding(self.preview(root))
            claim = self.claim(root, binding)
            self.addCleanup(claim.close)
            before = archive_snapshot(root)
            real_dry_run = archive_services.promote_zettel_dry_run

            def changed_source(*args, **kwargs):
                result = copy.deepcopy(real_dry_run(*args, **kwargs))
                result["source_sha256"] = "2" * 64
                result["receipt_preview"]["source"]["sha256"] = "2" * 64
                return result

            with patch.object(
                archive_services,
                "promote_zettel_dry_run",
                side_effect=changed_source,
            ):
                with self.assertRaisesRegex(
                    archive_services.ArchiveServiceError,
                    "source draft changed after dry-run",
                ):
                    self.promote_with_claim(root, binding, claim)

            self.assertEqual(archive_snapshot(root), before)
            self.assertEqual(claim.status, "started")

    def test_changed_target_blocks_with_zero_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.prepare_archive(Path(tmp))
            binding = warning_override_approval_binding(self.preview(root))
            claim = self.claim(root, binding)
            self.addCleanup(claim.close)
            before = archive_snapshot(root)
            real_dry_run = archive_services.promote_zettel_dry_run

            def changed_target(*args, **kwargs):
                result = copy.deepcopy(real_dry_run(*args, **kwargs))
                result["proposed_canonical_path"] = (
                    "zettels/changed-target.md"
                )
                result["receipt_preview"]["target"]["path"] = (
                    "zettels/changed-target.md"
                )
                return result

            with patch.object(
                archive_services,
                "promote_zettel_dry_run",
                side_effect=changed_target,
            ):
                with self.assertRaisesRegex(
                    archive_services.ArchiveServiceError,
                    "operation_approval_binding_mismatch",
                ):
                    self.promote_with_claim(root, binding, claim)

            self.assertEqual(archive_snapshot(root), before)
            self.assertEqual(claim.status, "started")

    def test_valid_claim_succeeds_and_receipt_records_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.prepare_archive(Path(tmp))
            preview = self.preview(root)
            binding = warning_override_approval_binding(preview)
            claim = self.claim(root, binding)
            self.addCleanup(claim.close)

            result = self.promote_with_claim(root, binding, claim)

            self.assertTrue(result["ok"], result)
            self.assertEqual(claim.status, "started")
            envelope = result["receipt"]["exact_human_approval"]
            self.assertEqual(envelope["operation"], "warning_override")
            self.assertEqual(envelope["plan_sha256"], binding.plan_sha256)
            self.assertEqual(
                envelope["target_binding_sha256"],
                binding.target_binding_sha256,
            )
            self.assertEqual(
                envelope["exact_human_approval"]["approval_id"],
                claim.public_reference()["approval_id"],
            )
            durable = json.loads(
                (root / result["receipt_path"]).read_text(encoding="utf-8")
            )
            self.assertEqual(durable["exact_human_approval"], envelope)

    def test_no_warning_normal_promotion_requires_promote_claim(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.prepare_archive(Path(tmp), warning=False)
            preview = self.preview(root)
            self.assertEqual(preview["warnings"], [])
            binding = promote_zet_approval_binding(preview)
            self.assertEqual(binding.operation.value, "promote_zet")
            before = archive_snapshot(root)

            with self.assertRaisesRegex(
                archive_services.ArchiveServiceError,
                "exact_human_approval_required",
            ):
                archive_services.promote_zettel(
                    root,
                    relative_path=DRAFT_RELATIVE,
                    reviewed_by="person:test",
                    allow_warnings=False,
                )
            self.assertEqual(archive_snapshot(root), before)

            claim = self.claim(root, binding)
            self.addCleanup(claim.close)
            result = self.promote_with_claim(
                root,
                binding,
                claim,
                allow_warnings=False,
            )

            self.assertTrue(result["ok"], result)
            self.assertEqual(claim.status, "started")
            self.assertEqual(
                result["receipt"]["exact_human_approval"]["operation"],
                "promote_zet",
            )


if __name__ == "__main__":
    unittest.main()
