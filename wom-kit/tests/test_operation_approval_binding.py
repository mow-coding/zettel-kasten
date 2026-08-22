from __future__ import annotations

import copy
import json
import unittest

from wom_kit.exact_human_approval_windows import ExactHumanApprovalOperation
from wom_kit.exact_human_approval import exact_human_approval_context_sha256
from wom_kit.operation_approval_binding import (
    OperationApprovalBindingError,
    assert_same_binding,
    build_operation_exact_human_approval_receipt,
    mint_zet_approval_binding,
    project_version_update_approval_binding,
    retire_draft_approval_binding,
    zettel_edge_approval_binding,
)


class OperationApprovalBindingTests(unittest.TestCase):
    def mint_plan(self):
        return {
            "ok": True,
            "dry_run": True,
            "zettel_id": "PRIVATE_ZET_ID",
            "proposed_canonical_path": "zettels/private.md",
            "proposed_mint_receipt_path": "receipts/private.json",
            "proposed_draft_snapshot_path": "snapshots/private.md",
            "warnings": ["sensitive_content_reviewed"],
            "checklist": [{"id": "one_clear_purpose", "status": "passed"}],
            "near_duplicates": [],
            "duplicate_check": {"state": "clear"},
            "first_read_check": {"ready": True},
            "quality_check": {"ok": True},
            "self_contained_check": {"ok": True},
            "source_fidelity": None,
            "scratch_cleanup": {"count": 0},
            "receipt_preview": {
                "source": {"sha256": "1" * 64, "path": "inbox/private.md"}
            },
            "would_change": ["private path"],
        }

    def test_mint_binding_covers_warnings_checklist_and_full_dry_run(self) -> None:
        plan = self.mint_plan()
        first = mint_zet_approval_binding(plan)
        self.assertIs(first.operation, ExactHumanApprovalOperation.mint_zet)
        self.assertEqual(first.warning_codes, ("sensitive_content_reviewed",))
        self.assertNotIn("PRIVATE_ZET_ID", json.dumps(first.public_document()))
        changed = copy.deepcopy(plan)
        changed["checklist"][0]["status"] = "failed"
        second = mint_zet_approval_binding(changed)
        self.assertNotEqual(first.plan_sha256, second.plan_sha256)
        with self.assertRaises(OperationApprovalBindingError):
            assert_same_binding(
                second,
                expected_plan_sha256=first.plan_sha256,
                expected_target_binding_sha256=first.target_binding_sha256,
            )

    def test_mint_binding_ignores_only_volatile_scratch_receipt_locator(self) -> None:
        plan = self.mint_plan()
        first_receipt = (
            "receipts/ops/ai-scratch-gc/private.20260820T010101000000+0900."
            "scratch-gc.json"
        )
        second_receipt = (
            "receipts/ops/ai-scratch-gc/private.20260820T010102000000+0900."
            "scratch-gc.json"
        )
        plan["scratch_cleanup"] = {
            "blockers": [],
            "candidate_count": 1,
            "candidates": [
                {
                    "path": ".wom-scratch/session/private.txt",
                    "state": "ready",
                    "sha256": "2" * 64,
                    "bytes": 7,
                }
            ],
            "missing": [],
            "receipt_path": first_receipt,
            "safe_to_cleanup": True,
            "scratch_reference_count": 1,
            "would_change": [
                "delete .wom-scratch/session/private.txt",
                f"write {first_receipt}",
            ],
            "zettel_id": "PRIVATE_ZET_ID",
            "zettel_path": "inbox/private.md",
        }
        plan["would_change"] = [
            "write zettels/private.md",
            "delete .wom-scratch/session/private.txt",
            f"write {first_receipt}",
        ]
        first = mint_zet_approval_binding(plan)

        changed_locator = copy.deepcopy(plan)
        changed_locator["scratch_cleanup"]["receipt_path"] = second_receipt
        changed_locator["scratch_cleanup"]["would_change"][-1] = (
            f"write {second_receipt}"
        )
        changed_locator["would_change"][-1] = f"write {second_receipt}"
        second = mint_zet_approval_binding(changed_locator)
        self.assertEqual(first.plan_sha256, second.plan_sha256)
        self.assertEqual(first.target_binding_sha256, second.target_binding_sha256)

        changed_effect = copy.deepcopy(changed_locator)
        changed_effect["scratch_cleanup"]["candidates"][0]["sha256"] = "3" * 64
        third = mint_zet_approval_binding(changed_effect)
        self.assertNotEqual(first.plan_sha256, third.plan_sha256)

    def test_edge_binding_requires_current_source_digest_and_covers_target(self) -> None:
        plan = {
            "ok": True,
            "dry_run": True,
            "source": {
                "zettel_id": "private",
                "current_sha256": "sha256:" + "2" * 64,
            },
            "target": {"ref": "private-target", "verified": True},
            "edge_id": "edge:private",
            "receipt_path": "receipts/private.json",
            "proposed_edge": {"type": "supports"},
            "entity_type_contract": {"status": "allowed"},
            "warnings": [],
            "would_change": [],
        }
        binding = zettel_edge_approval_binding(plan)
        changed = copy.deepcopy(plan)
        changed["source"]["current_sha256"] = "sha256:" + "3" * 64
        self.assertNotEqual(
            binding.target_binding_sha256,
            zettel_edge_approval_binding(changed).target_binding_sha256,
        )

    def test_retire_binding_covers_all_four_durable_refs(self) -> None:
        refs = {
            name: {"sha256": str(index) * 64, "path": f"private-{name}"}
            for index, name in enumerate(
                ("source", "target", "mint_receipt", "snapshot"), start=4
            )
        }
        plan = {
            "ok": True,
            "dry_run": True,
            "zettel_id": "private",
            "retire_receipt_path": "private",
            "receipt_preview": refs,
            "warnings": [],
            "would_change": [],
        }
        first = retire_draft_approval_binding(plan)
        changed = copy.deepcopy(plan)
        changed["receipt_preview"]["snapshot"]["sha256"] = "8" * 64
        second = retire_draft_approval_binding(changed)
        self.assertNotEqual(first.plan_sha256, second.plan_sha256)
        self.assertNotEqual(first.target_binding_sha256, second.target_binding_sha256)

    def test_blocked_or_missing_required_digest_fails_content_free(self) -> None:
        plan = self.mint_plan()
        plan["ok"] = False
        with self.assertRaises(OperationApprovalBindingError) as captured:
            mint_zet_approval_binding(plan)
        self.assertEqual(captured.exception.code, "operation_approval_plan_blocked")
        self.assertNotIn("PRIVATE", str(captured.exception))

    def test_receipt_reference_must_match_the_fresh_exact_context(self) -> None:
        binding = mint_zet_approval_binding(self.mint_plan())
        context = binding.context(
            archive_id="archive:test",
            reviewer_claim="person:reviewer",
        )
        reference = {
            "schema_version": "wom-kit/exact-human-approval-reference/v0.1",
            "approval_id": "approval_" + "a" * 32,
            "context_sha256": exact_human_approval_context_sha256(context),
            "approval_authority_sha256": "sha256:" + "b" * 64,
            "one_use": True,
        }
        receipt = build_operation_exact_human_approval_receipt(
            binding,
            archive_id="archive:test",
            reviewer_claim="person:reviewer",
            exact_human_approval_reference=reference,
        )
        self.assertEqual(receipt["operation"], "mint_zet")
        tampered = dict(reference)
        tampered["context_sha256"] = "sha256:" + "c" * 64
        with self.assertRaises(OperationApprovalBindingError):
            build_operation_exact_human_approval_receipt(
                binding,
                archive_id="archive:test",
                reviewer_claim="person:reviewer",
                exact_human_approval_reference=tampered,
            )

    def test_non_string_warning_is_generic_and_never_crashes_or_echoes(self) -> None:
        plan = self.mint_plan()
        plan["warnings"] = [{"private": "value"}]
        binding = mint_zet_approval_binding(plan)
        self.assertEqual(binding.warning_codes, ("non_code_warning_present",))
        self.assertNotIn('"value"', json.dumps(binding.public_document()))

    def test_project_version_update_binding_covers_head_target_pins_and_preflight(
        self,
    ) -> None:
        plan = {
            "ok": True,
            "schema": "wom-kit/project-version-update/v0.1",
            "lifecycle_action": "project_version_update",
            "status": "ready_to_fetch_on_approve",
            "mode": "dry_run",
            "target": {
                "tag": "v0.4.3",
                "version": "0.4.3",
                "target_commit": None,
                "tag_available_locally": False,
            },
            "source_mirror": {
                "path": "parent_of_archive/.zettel-kasten/source",
                "head_commit_before": "a" * 40,
            },
            "pins": {
                "planned": [
                    {
                        "path": "parent_of_archive/.zettel-kasten/installed-version.txt",
                        "previous_version": "v0.4.0",
                        "target_version": "v0.4.3",
                    }
                ]
            },
            "materialization_preflight": {
                "state": "deferred_until_approval_fetch"
            },
            "fetch": {
                "attempted": False,
                "git_transport_called": False,
            },
            "write_boundary": {
                "checkpointed_change_detection": True,
                "external_writer_quiescence_required": True,
            },
            "warnings": ["private prose is digest-bound but never echoed"],
            "would_change": ["logical project mirror and pins"],
        }
        first = project_version_update_approval_binding(plan)
        self.assertIs(
            first.operation,
            ExactHumanApprovalOperation.project_version_update,
        )
        self.assertNotIn("private prose", json.dumps(first.public_document()))

        changed_head = copy.deepcopy(plan)
        changed_head["source_mirror"]["head_commit_before"] = "b" * 40
        second = project_version_update_approval_binding(changed_head)
        self.assertNotEqual(first.plan_sha256, second.plan_sha256)
        self.assertNotEqual(
            first.target_binding_sha256,
            second.target_binding_sha256,
        )

        changed_pin = copy.deepcopy(plan)
        changed_pin["pins"]["planned"][0]["previous_version"] = "v0.4.1"
        third = project_version_update_approval_binding(changed_pin)
        self.assertNotEqual(first.target_binding_sha256, third.target_binding_sha256)


if __name__ == "__main__":
    unittest.main()
