from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from wom_kit import archive_services
from wom_kit.exact_human_approval import (
    _claim_exact_human_approval_core as claim_exact_human_approval,
)
from wom_kit.exact_human_approval_windows import (
    _ExactHumanApprovalDecision as ExactHumanApprovalDecision,
)
from wom_kit.operation_approval_binding import mint_zet_approval_binding


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


class MintScratchCleanupToctouTests(unittest.TestCase):
    def make_archive_with_scratch_draft(
        self,
        parent: Path,
    ) -> tuple[Path, Path, Path]:
        root = parent / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", root)
        scratch_relative = ".wom-scratch/session/private-research.txt"
        scratch_path = root / Path(scratch_relative)
        scratch_path.parent.mkdir(parents=True, exist_ok=True)
        scratch_path.write_bytes(b"approved scratch bytes")

        draft_path = root / "inbox" / "zet_20260820_scratch_toctou.md"
        frontmatter = {
            "id": "zet_20260820_scratch_toctou",
            "title": "Scratch cleanup approval boundary",
            "abstract": (
                "Durable context is preserved before approved temporary "
                "scratch material is removed."
            ),
            "created_at": "2026-08-20T10:10:00+09:00",
            "updated_at": "2026-08-20T10:10:00+09:00",
            "archive_id": "archive:personal:fake-life",
            "status": "draft",
            "kind": "permanent_note",
            "facets": {"domain": "test"},
            "assets": [],
            "edges": [],
            "source_refs": [
                {
                    "type": "ai_scratch",
                    "value": scratch_relative,
                    "role": "working_material",
                }
            ],
            "provenance": {
                "created_by": "person:test-fixture",
                "creation_mode": "human_written",
                "created_in": "archive:personal:fake-life",
                "source": "test_fixture",
                "derived_from": [],
            },
            "visibility": {
                "scope": "private",
                "allowed_archives": [],
                "source_visibility": "private",
            },
            "promotion": {
                "stage": "promotion_candidate",
                "ready_for_promotion": True,
                "checklist": {
                    item_id: True for item_id in PROMOTION_CHECKLIST_IDS
                },
            },
        }
        body = (
            "All durable context from the temporary research file is now "
            "preserved inside this zettel. "
        ) * 12
        draft_path.write_text(
            "---\n"
            + archive_services.dump_yaml(frontmatter)
            + "---\n\n"
            + body,
            encoding="utf-8",
            newline="\n",
        )
        self.assertTrue(archive_services.index_archive(root)["index_complete"])
        return root, draft_path, scratch_path

    def approved_mint(
        self,
        root: Path,
        *,
        mutate_after_claim=None,
    ) -> tuple[dict, object]:
        relative_path = "inbox/zet_20260820_scratch_toctou.md"
        preview = archive_services.mint_zettel_dry_run(
            root,
            relative_path=relative_path,
        )
        self.assertTrue(preview["ok"], preview)
        binding = mint_zet_approval_binding(preview)
        context = binding.context(
            archive_id=archive_services.read_archive_id(root),
            reviewer_claim="person:test",
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
            bytearray(b"s" * 32),
        )
        self.addCleanup(claim.close)

        original_upsert = archive_services.upsert_zettel_index_entry

        def upsert_with_optional_mutation(*args, **kwargs):
            if mutate_after_claim is not None:
                mutate_after_claim()
            return original_upsert(*args, **kwargs)

        with patch.object(
            archive_services,
            "upsert_zettel_index_entry",
            side_effect=upsert_with_optional_mutation,
        ):
            result = archive_services.mint_zettel(
                root,
                relative_path=relative_path,
                reviewed_by="person:test",
                allow_warnings=True,
                expected_exact_approval_plan_sha256=binding.plan_sha256,
                expected_exact_approval_target_binding_sha256=(
                    binding.target_binding_sha256
                ),
                exact_human_approval_claim=claim,
            )
        return result, claim

    def test_replacement_after_claim_is_preserved_as_honest_mint_partial(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _draft_path, scratch_path = (
                self.make_archive_with_scratch_draft(Path(tmp))
            )
            replacement = b"replacement bytes after claim revalidation"
            result, claim = self.approved_mint(
                root,
                mutate_after_claim=lambda: scratch_path.write_bytes(replacement),
            )

            self.assertFalse(result["ok"])
            self.assertEqual(
                result["state"],
                "canonical_written_scratch_cleanup_reconciliation_required",
            )
            self.assertEqual(
                result["blockers"],
                [archive_services.MINT_SCRATCH_CLEANUP_RECONCILIATION_REQUIRED],
            )
            self.assertTrue(result["reconciliation_required"])
            self.assertFalse(result["automatic_retry"])
            self.assertEqual(
                result["partial_result"],
                {
                    "canonical_receipt_and_snapshot_written": True,
                    "index_current": True,
                    "scratch_cleanup_attempted": True,
                    "scratch_cleanup_complete": False,
                    "reconciliation_required": True,
                },
            )
            self.assertEqual(claim.status, "started")
            self.assertTrue(scratch_path.is_file())
            self.assertEqual(scratch_path.read_bytes(), replacement)
            self.assertNotIn(
                replacement.decode("utf-8"),
                json.dumps(result, sort_keys=True),
            )
            self.assertEqual(
                result["scratch_cleanup"]["blockers"],
                [archive_services.AI_SCRATCH_GC_APPROVAL_BINDING_CHANGED],
            )
            self.assertEqual(result["scratch_cleanup"]["deleted_count"], 0)
            self.assertNotIn(
                ".wom-scratch/session/private-research.txt",
                json.dumps(result["scratch_cleanup"], sort_keys=True),
            )
            for relative in result["created_paths"]:
                self.assertTrue((root / relative).is_file())
            receipt_root = root / archive_services.AI_SCRATCH_GC_RECEIPTS_DIR
            self.assertEqual(
                list(receipt_root.glob("*.scratch-gc.json"))
                if receipt_root.exists()
                else [],
                [],
            )

    def test_matching_approved_projection_still_cleans_original_candidate(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _draft_path, scratch_path = (
                self.make_archive_with_scratch_draft(Path(tmp))
            )
            result, claim = self.approved_mint(root)

            self.assertTrue(result["ok"], result)
            self.assertFalse(scratch_path.exists())
            self.assertEqual(result["scratch_cleanup"]["deleted"][0]["bytes"], 22)
            self.assertTrue(
                (root / result["scratch_cleanup"]["receipt_path"]).is_file()
            )
            self.assertEqual(claim.status, "started")

    def test_windows_path_and_fd_ctime_difference_keeps_surface_checks(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scratch_relative = ".wom-scratch/session/ctime-surfaces.txt"
            scratch_path = root / Path(scratch_relative)
            scratch_path.parent.mkdir(parents=True)
            scratch_path.write_bytes(b"approved scratch bytes")
            candidate = {
                "path": scratch_relative,
                "state": "ready",
                "sha256": archive_services.sha256_path(scratch_path),
                "bytes": scratch_path.stat().st_size,
            }
            stable_identity = (1, 2, 3, 22, 4, 5)

            with patch.object(
                archive_services,
                "_ai_scratch_stat_identity",
                side_effect=[stable_identity] * 4,
            ) as identity, patch.object(
                archive_services,
                "_ai_scratch_stat_change_time_ns",
                side_effect=[100, 200, 200, 100],
            ) as change_time:
                matched = (
                    archive_services._ai_scratch_candidate_matches_current_file(
                        root,
                        candidate,
                    )
                )

            self.assertTrue(matched)
            self.assertEqual(identity.call_count, 4)
            self.assertEqual(change_time.call_count, 4)

    def test_windows_surface_ctime_drift_still_fails_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scratch_relative = ".wom-scratch/session/ctime-drift.txt"
            scratch_path = root / Path(scratch_relative)
            scratch_path.parent.mkdir(parents=True)
            scratch_path.write_bytes(b"approved scratch bytes")
            candidate = {
                "path": scratch_relative,
                "state": "ready",
                "sha256": archive_services.sha256_path(scratch_path),
                "bytes": scratch_path.stat().st_size,
            }
            stable_identity = (1, 2, 3, 22, 4, 5)

            for change_times in (
                [100, 200, 201, 100],
                [100, 200, 200, 101],
            ):
                with self.subTest(change_times=change_times), patch.object(
                    archive_services,
                    "_ai_scratch_stat_identity",
                    side_effect=[stable_identity] * 4,
                ), patch.object(
                    archive_services,
                    "_ai_scratch_stat_change_time_ns",
                    side_effect=change_times,
                ):
                    matched = archive_services._ai_scratch_candidate_matches_current_file(
                        root,
                        candidate,
                    )
                self.assertFalse(matched)

    def test_windows_stable_time_supports_python_310_and_312_stats(
        self,
    ) -> None:
        python_310_stat = SimpleNamespace(
            st_ctime_ns=310_123,
            st_ctime=0.000310123,
        )
        python_312_stat = SimpleNamespace(
            st_birthtime_ns=312_456,
            st_birthtime=0.000312456,
            st_ctime_ns=312_789,
            st_ctime=0.000312789,
        )

        self.assertEqual(
            archive_services._ai_scratch_windows_stable_time_ns(
                python_310_stat
            ),
            310_123,
        )
        self.assertEqual(
            archive_services._ai_scratch_windows_stable_time_ns(
                python_312_stat
            ),
            312_456,
        )
        with self.assertRaisesRegex(
            ValueError,
            "scratch_file_timestamp_unavailable",
        ):
            archive_services._ai_scratch_windows_stable_time_ns(
                SimpleNamespace()
            )

    def test_cross_surface_stable_identity_mismatch_fails_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scratch_relative = ".wom-scratch/session/replaced-identity.txt"
            scratch_path = root / Path(scratch_relative)
            scratch_path.parent.mkdir(parents=True)
            scratch_path.write_bytes(b"approved scratch bytes")
            candidate = {
                "path": scratch_relative,
                "state": "ready",
                "sha256": archive_services.sha256_path(scratch_path),
                "bytes": scratch_path.stat().st_size,
            }

            with patch.object(
                archive_services,
                "_ai_scratch_stat_identity",
                side_effect=[
                    (1, 2, 3, 22, 4, 5),
                    (1, 9, 3, 22, 4, 6),
                ],
            ):
                matched = (
                    archive_services._ai_scratch_candidate_matches_current_file(
                        root,
                        candidate,
                    )
                )

            self.assertFalse(matched)

    def test_receipt_timestamp_rollover_is_not_a_cleanup_effect_change(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, draft_path, _scratch_path = (
                self.make_archive_with_scratch_draft(Path(tmp))
            )
            frontmatter, body = archive_services.require_readable_zettel_content(
                draft_path
            )
            with patch.object(
                archive_services,
                "ai_scratch_gc_receipt_path",
                side_effect=[
                    "receipts/scratch-gc/zet.first-second.scratch-gc.json",
                    "receipts/scratch-gc/zet.next-second.scratch-gc.json",
                ],
            ):
                approved_plan = archive_services.build_ai_scratch_gc_plan(
                    root,
                    draft_path,
                    frontmatter,
                    body,
                )
                fresh_plan = archive_services.build_ai_scratch_gc_plan(
                    root,
                    draft_path,
                    frontmatter,
                    body,
                )

            self.assertNotEqual(
                approved_plan["receipt_path"],
                fresh_plan["receipt_path"],
            )
            self.assertNotEqual(
                approved_plan["would_change"],
                fresh_plan["would_change"],
            )
            self.assertEqual(
                archive_services._ai_scratch_gc_approval_projection(
                    approved_plan
                ),
                archive_services._ai_scratch_gc_approval_projection(
                    fresh_plan
                ),
            )

    def test_standalone_gc_dry_run_keeps_existing_plan_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _draft_path, scratch_path = (
                self.make_archive_with_scratch_draft(Path(tmp))
            )
            result = archive_services.ai_scratch_gc_for_zettel(
                root,
                relative_path="inbox/zet_20260820_scratch_toctou.md",
                dry_run=True,
            )

            self.assertTrue(result["ok"], result)
            self.assertTrue(result["dry_run"])
            self.assertEqual(result["cleanup_plan"]["candidate_count"], 1)
            self.assertEqual(result["cleanup_plan"]["candidates"][0]["bytes"], 22)
            self.assertTrue(scratch_path.is_file())
            self.assertTrue(result["would_change"])


if __name__ == "__main__":
    unittest.main()
