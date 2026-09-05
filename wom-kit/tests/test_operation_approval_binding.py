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
    objet_capture_approval_binding,
    project_version_update_approval_binding,
    retire_draft_approval_binding,
    zettel_edge_approval_binding,
    zettel_edge_revert_approval_binding,
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
                "source": {"sha256": "1" * 64, "path": "inbox/private.md"},
                "zettel": {
                    "id": "PRIVATE_ZET_ID",
                    "title": "검토할 zet 제목",
                },
            },
            "would_change": ["private path"],
        }

    def test_mint_binding_covers_warnings_checklist_and_full_dry_run(self) -> None:
        plan = self.mint_plan()
        first = mint_zet_approval_binding(plan)
        self.assertIs(first.operation, ExactHumanApprovalOperation.mint_zet)
        self.assertEqual(first.warning_codes, ("sensitive_content_reviewed",))
        self.assertEqual(first.target_preview.kind, "zet")
        self.assertEqual(first.target_preview.primary, "private.md")
        self.assertIsNone(first.target_preview.secondary)
        self.assertEqual(first.target_preview.primary_label, "검토할 zet 제목")
        self.assertNotIn("PRIVATE_ZET_ID", json.dumps(first.public_document()))
        self.assertNotIn("private.md", json.dumps(first.public_document()))
        self.assertNotIn("검토할 zet 제목", json.dumps(first.public_document()))
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

        changed_display_only = copy.deepcopy(plan)
        changed_display_only["title"] = "unbound spoofed title"
        same = mint_zet_approval_binding(changed_display_only)
        self.assertEqual(same.plan_sha256, first.plan_sha256)
        self.assertEqual(same.target_preview, first.target_preview)

    def test_mint_preview_requires_one_bound_identity(self) -> None:
        plan = self.mint_plan()
        plan["proposed_canonical_path"] = None
        plan["zettel_id"] = None
        with self.assertRaises(OperationApprovalBindingError) as captured:
            mint_zet_approval_binding(plan)
        self.assertEqual(captured.exception.code, "operation_approval_plan_invalid")

    def test_mint_preview_suppresses_unsafe_bound_title_without_blocking_plan(self) -> None:
        windows_path = r"C:" + r"\Users\private\do-not-show.md"
        for unsafe_title in (
            windows_path,
            f"Path note `{windows_path}`",
            f"Path note {{{windows_path}}}",
            "owner@example.com 사건",
            "https://private.example 사건",
        ):
            with self.subTest(unsafe_title=unsafe_title):
                plan = self.mint_plan()
                plan["receipt_preview"]["zettel"]["title"] = unsafe_title

                binding = mint_zet_approval_binding(plan)

                self.assertEqual(binding.target_preview.primary, "private.md")
                self.assertIsNone(binding.target_preview.primary_label)

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
        self.assertEqual(binding.target_preview.kind, "zet_edge")
        self.assertEqual(binding.target_preview.primary, "private")
        self.assertEqual(binding.target_preview.secondary, "private-target")
        self.assertEqual(binding.target_preview.relation, "supports")
        changed = copy.deepcopy(plan)
        changed["source"]["current_sha256"] = "sha256:" + "3" * 64
        self.assertNotEqual(
            binding.target_binding_sha256,
            zettel_edge_approval_binding(changed).target_binding_sha256,
        )

    def test_edge_revert_and_objet_capture_bind_current_effect_sets(self) -> None:
        edge_plan = {
            "ok": True,
            "dry_run": True,
            "lifecycle_action": "zettel_edge_revert_plan",
            "source": {
                "zettel_id": "private",
                "current_sha256": "sha256:" + "4" * 64,
            },
            "edge": {"edge_id": "edge:private", "target_ref": "private"},
            "edge_receipt_path": "receipts/edges/private.json",
            "revert_receipt_path": "receipts/edges/reverts/private.json",
            "would_change": ["private"],
            "warnings": [],
        }
        first_edge = zettel_edge_revert_approval_binding(edge_plan)
        changed_edge = copy.deepcopy(edge_plan)
        changed_edge["source"]["current_sha256"] = "sha256:" + "5" * 64
        self.assertNotEqual(
            first_edge.target_binding_sha256,
            zettel_edge_revert_approval_binding(changed_edge).target_binding_sha256,
        )

        capture_plan = {
            "ok": True,
            "dry_run": True,
            "lifecycle_action": "objet_capture_plan",
            "selection_manifest_sha256": "sha256:" + "6" * 64,
            "items": [{"item_id": "private", "source_sha256": "7" * 64}],
            "planned_writes": ["private"],
            "summary": {"would_capture": 1},
            "project_intake_context": {},
            "warnings": [],
        }
        first_capture = objet_capture_approval_binding(capture_plan)
        batch_capture = objet_capture_approval_binding(
            capture_plan,
            operation=ExactHumanApprovalOperation.objet_capture_batch,
        )
        self.assertIs(
            first_capture.operation,
            ExactHumanApprovalOperation.objet_capture,
        )
        self.assertIs(
            batch_capture.operation,
            ExactHumanApprovalOperation.objet_capture_batch,
        )
        self.assertNotEqual(first_capture.plan_sha256, batch_capture.plan_sha256)
        self.assertEqual(
            first_capture.target_binding_sha256,
            batch_capture.target_binding_sha256,
        )
        changed_capture = copy.deepcopy(capture_plan)
        changed_capture["items"][0]["source_sha256"] = "8" * 64
        self.assertNotEqual(
            first_capture.target_binding_sha256,
            objet_capture_approval_binding(changed_capture).target_binding_sha256,
        )
        with self.assertRaises(OperationApprovalBindingError) as invalid:
            objet_capture_approval_binding(
                capture_plan,
                operation=ExactHumanApprovalOperation.mint_zet,
            )
        self.assertEqual(invalid.exception.code, "operation_approval_plan_invalid")

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
        self.assertEqual(first.target_preview.primary, "private-source")
        self.assertIsNone(first.target_preview.secondary)
        changed = copy.deepcopy(plan)
        changed["receipt_preview"]["snapshot"]["sha256"] = "8" * 64
        second = retire_draft_approval_binding(changed)
        self.assertNotEqual(first.plan_sha256, second.plan_sha256)
        self.assertNotEqual(first.target_binding_sha256, second.target_binding_sha256)

        changed_display_only = copy.deepcopy(plan)
        changed_display_only["draft_path"] = "inbox/spoofed.md"
        changed_display_only["title"] = "spoofed title"
        same = retire_draft_approval_binding(changed_display_only)
        self.assertEqual(same.plan_sha256, first.plan_sha256)
        self.assertEqual(same.target_preview, first.target_preview)

        missing_identity = copy.deepcopy(plan)
        missing_identity["zettel_id"] = None
        missing_identity["receipt_preview"]["source"]["path"] = None
        with self.assertRaises(OperationApprovalBindingError) as captured:
            retire_draft_approval_binding(missing_identity)
        self.assertEqual(captured.exception.code, "operation_approval_plan_invalid")

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

    @staticmethod
    def durable_project_update_plan() -> dict[str, object]:
        transaction_ref = "update_" + "a" * 32
        domain_plan_sha256 = "sha256:" + "3" * 64
        domain_target_sha256 = "sha256:" + "4" * 64
        wheel_sha256 = "sha256:" + "6" * 64
        supply_lock_sha256 = "sha256:" + "5" * 64
        supply_artifacts = [
            {
                "role": "dependency",
                "distribution": "PyYAML",
                "version": "6.0.3",
                "file_name": "pyyaml-6.0.3-cp312-cp312-win_amd64.whl",
                "size_bytes": 154_003,
                "sha256": "sha256:" + "7" * 64,
                "source_kind": "public_pypi_file",
                "download_url_echoed": False,
            },
            {
                "role": "dependency",
                "distribution": "unicodedata2",
                "version": "17.0.1",
                "file_name": "unicodedata2-17.0.1-cp312-cp312-win_amd64.whl",
                "size_bytes": 484_194,
                "sha256": "sha256:" + "8" * 64,
                "source_kind": "public_pypi_file",
                "download_url_echoed": False,
            },
        ]
        artifact_inventory = [
            {
                key: value
                for key, value in item.items()
                if key not in {"source_kind", "download_url_echoed"}
            }
            for item in supply_artifacts
        ]
        artifact_inventory.append(
            {
                "role": "runtime",
                "distribution": "wom-kit",
                "version": "0.4.3",
                "file_name": "wom_kit-0.4.3-py3-none-any.whl",
                "size_bytes": 987_654,
                "sha256": wheel_sha256,
            }
        )
        artifact_inventory.sort(
            key=lambda item: (item["file_name"].casefold(), item["file_name"])
        )
        runtime_candidate = {
            "schema": "wom-kit/project-runtime-candidate/v0.1",
            "status": "sealed",
            "target_tag": "v0.4.3",
            "target_version": "0.4.3",
            "target_commit": "b" * 40,
            "transaction_ref": transaction_ref,
            "candidate_locator": (
                ".zettel-kasten/private/version-updates/"
                f"{transaction_ref}/runtime-candidate"
            ),
            "seal_locator": (
                ".zettel-kasten/private/version-updates/"
                f"{transaction_ref}/runtime-candidate-seal.json"
            ),
            "inventory_sha256": "sha256:" + "9" * 64,
            "candidate_sha256": "sha256:" + "a" * 64,
            "inventory_count": 4321,
            "inventory_bytes": 12_345_678,
            "receipt_sha256": "sha256:" + "b" * 64,
            "runtime_receipt_schema": (
                "wom-kit/project-runtime-receipt/v0.1"
            ),
            "wheel_file_name": "wom_kit-0.4.3-py3-none-any.whl",
            "wheel_sha256": wheel_sha256,
            "supply_lock_sha256": supply_lock_sha256,
            "artifact_inventory": artifact_inventory,
            "installed_payload_sha256": "sha256:" + "c" * 64,
            "python_version": "3.12.10",
            "verification": {
                "wheel_sha256": True,
                "pip_check": True,
                "version": True,
                "package_resources": True,
                "new_process": True,
                "supply_lock": True,
                "artifact_hashes": True,
                "artifact_sizes": True,
                "artifact_inventory": True,
                "installed_payload": True,
                "live_process": True,
            },
            "existing_runtime_reusable": False,
            "existing_runtime_repair_required": False,
            "existing_runtime_preimage_sha256": None,
            "existing_runtime_preimage_count": 0,
            "existing_runtime_preimage_bytes": 0,
            "repair_preimage_exactly_bound": False,
            "will_preserve_during_active_transaction": False,
            "complete_runtime_image": True,
            "network_complete": True,
            "toolchain_complete": True,
            "same_volume_verified": True,
            "runtime_parent_existed_before": False,
            "post_approval_child_process_allowed": False,
            "post_approval_network_allowed": False,
            "post_approval_copy_allowed": False,
            "marker_free_final_postimage": True,
            "reopenable_from_private_seal": True,
            "durability_barriers_complete": True,
            "cleanup_contract": "sealed_exact_tree_only",
            "download_urls_echoed": False,
            "private_values_echoed": False,
            "absolute_paths_echoed": False,
        }
        transaction = {
            "schema": (
                "wom-kit/project-update-transaction-public-summary/v0.4.3"
            ),
            "transaction_ref": transaction_ref,
            "transaction_logical_ref": (
                f".zettel-kasten/private/version-updates/{transaction_ref}"
            ),
            "intent_sha256": "sha256:" + "0" * 64,
            "lock_backlinked": True,
            "directory_fsync_required": True,
            "static_receipt_domain_plan_sha256": domain_plan_sha256,
            "static_receipt_domain_target_binding_sha256": (
                domain_target_sha256
            ),
        }
        static_receipt = {
            "schema": "wom-kit/project-version-update-receipt/v0.3",
            "logical_path": (
                f".zettel-kasten/receipts/version-updates/{transaction_ref}.json"
            ),
            "sha256": "sha256:" + "d" * 64,
            "domain_plan_sha256": domain_plan_sha256,
            "domain_target_binding_sha256": domain_target_sha256,
            "dynamic_claim_fields_embedded": False,
            "deterministic_one_pass_construction": True,
        }
        trusted_runner = {
            "schema": "wom-kit/project-update-trusted-git-runner/v0.4.3",
            "runner_sha256": "sha256:" + "1" * 64,
            "executable_sha256": "sha256:" + "2" * 64,
            "size_bytes": 1_234_567,
            "phase": "local_only",
            "absolute_path_echoed": False,
            "path_lookup_after_resolution": False,
            "executable_handle_held": True,
            "postapproval_transport_allowed": False,
        }
        preparation = {
            "lock_held": True,
            "network_complete": True,
            "post_approval_network_allowed": False,
            "target_ref_snapshot": {
                "tag_object": "d" * 40,
                "target_commit": "b" * 40,
                "origin_main": "e" * 40,
            },
            "preapproval_control_writes_completed": True,
            "preapproval_domain_writes_completed": False,
            "fetched_refs_may_change": True,
            "preapproval_control_scaffold_created": True,
            "preapproval_persistent_domain_effect": False,
            "preapproval_runtime_content_installed": False,
            "preapproval_activation_changed": False,
            "runtime_postapproval_child_process_allowed": False,
            "project_update_postapproval_local_git_allowed": True,
            "postapproval_git_transport_allowed": False,
            "trusted_git_runner": trusted_runner,
            "transaction": transaction,
            "runtime_candidate": copy.deepcopy(runtime_candidate),
            "static_receipt": static_receipt,
        }
        return {
            "ok": True,
            "schema": "wom-kit/project-version-update/v0.1",
            "lifecycle_action": "project_version_update",
            "status": "ready_for_approval",
            "mode": "approval_prepared",
            "target": {
                "tag": "v0.4.3",
                "version": "0.4.3",
                "target_commit": "b" * 40,
                "tag_available_locally": True,
                "annotated_tag_verified": True,
                "configured_origin_main_ancestry_verified": True,
            },
            "source_mirror": {
                "path": "parent_of_archive/.zettel-kasten/source",
                "head_commit_before": "a" * 40,
            },
            "pins": {
                "planned": [
                    {
                        "path": (
                            "parent_of_archive/.zettel-kasten/"
                            "installed-version.txt"
                        ),
                        "previous_version": "v0.4.0",
                        "target_version": "v0.4.3",
                    }
                ]
            },
            "materialization_preflight": {
                "state": "ready",
                "evaluated": True,
                "safe": True,
                "bounded": True,
                "no_write": True,
            },
            "project_runtime": {
                "policy_state": "required",
                "required": True,
                "project_runtime_argv": [r".\.zettel-kasten\bin\archive.cmd"],
                "bootstrap": {
                    "available": True,
                    "reason_code": "exact_public_release_wheel_verified",
                    "source_kind": "public_github_release",
                    "release_tag": "v0.4.3",
                    "wheel_file_name": "wom_kit-0.4.3-py3-none-any.whl",
                    "wheel_sha256": wheel_sha256,
                    "download_url_echoed": False,
                },
                "policy": {
                    "state": "required",
                    "required": True,
                    "schema": "wom-kit/project-runtime-policy/v0.1",
                    "policy_sha256": "sha256:" + "e" * 64,
                    "source_path": "wom-kit/project-runtime-policy.json",
                    "supply_lock_path": (
                        "wom-kit/project-runtime-supply-lock-v0.4.3.json"
                    ),
                    "supply_lock_sha256": supply_lock_sha256,
                },
                "supply": {
                    "schema": "wom-kit/project-runtime-supply-lock/v0.1",
                    "target_tag": "v0.4.3",
                    "lock_sha256": supply_lock_sha256,
                    "interpreter": {
                        "implementation": "cpython",
                        "python_version": "3.12",
                        "python_tag": "cp312",
                        "abi_tag": "cp312",
                        "platform_tag": "win_amd64",
                    },
                    "artifacts": supply_artifacts,
                    "index_resolution": False,
                    "all_artifacts_hash_and_size_bound": True,
                    "download_urls_echoed": False,
                },
                "runtime_candidate": runtime_candidate,
            },
            "fetch": {
                "attempted": True,
                "succeeded": True,
                "git_transport_called": True,
                "phase": "before_native_approval",
            },
            "approval_preparation": preparation,
            "write_boundary": {
                "checkpointed_change_detection": True,
                "external_writer_quiescence_required": True,
                "post_approval_network_allowed": False,
                "project_update_lock_acquired": True,
                "preapproval_control_writes_completed": True,
                "preapproval_domain_writes_completed": False,
                "fetched_refs_may_change": True,
                "preapproval_control_scaffold_created": True,
                "preapproval_persistent_domain_effect": False,
                "preapproval_runtime_content_installed": False,
                "preapproval_activation_changed": False,
                "runtime_postapproval_child_process_allowed": False,
                "project_update_postapproval_local_git_allowed": True,
                "postapproval_git_transport_allowed": False,
            },
            "warnings": ["private prose is digest-bound but never echoed"],
            "would_change": ["logical project mirror and pins"],
        }

    def test_project_version_update_binding_covers_durable_exact_preparation(
        self,
    ) -> None:
        plan = self.durable_project_update_plan()
        first = project_version_update_approval_binding(plan)
        self.assertIs(
            first.operation,
            ExactHumanApprovalOperation.project_version_update,
        )
        self.assertNotIn("private prose", json.dumps(first.public_document()))
        self.assertIn("project_update_intent", first.review_binding_codes)
        self.assertIn("project_update_static_receipt", first.review_binding_codes)
        self.assertNotIn(
            "project_runtime_prepared_bundle",
            first.review_binding_codes,
        )

        current_observed_policy = copy.deepcopy(plan)
        current_observed_policy["project_runtime"]["policy"].update(
            {
                "observation_state": "passed",
                "observation_reason_code": "verified",
            }
        )
        observed_binding = project_version_update_approval_binding(
            current_observed_policy
        )
        self.assertNotEqual(first.plan_sha256, observed_binding.plan_sha256)
        unavailable_policy = copy.deepcopy(current_observed_policy)
        unavailable_policy["project_runtime"]["policy"].update(
            {
                "observation_state": "unavailable",
                "observation_reason_code": (
                    "project_runtime_policy_unavailable"
                ),
            }
        )
        with self.assertRaises(OperationApprovalBindingError):
            project_version_update_approval_binding(unavailable_policy)

        empty_repair = copy.deepcopy(plan)
        for runtime_candidate in (
            empty_repair["approval_preparation"]["runtime_candidate"],
            empty_repair["project_runtime"]["runtime_candidate"],
        ):
            runtime_candidate.update(
                {
                    "existing_runtime_reusable": False,
                    "existing_runtime_repair_required": True,
                    "existing_runtime_preimage_sha256": (
                        "sha256:" + "e" * 64
                    ),
                    "existing_runtime_preimage_count": 0,
                    "existing_runtime_preimage_bytes": 0,
                    "runtime_receipt_schema": (
                        "wom-kit/project-runtime-receipt/v0.2"
                    ),
                    "repair_preimage_exactly_bound": True,
                    "will_preserve_during_active_transaction": True,
                }
            )
        empty_repair["approval_preparation"]["static_receipt"][
            "schema"
        ] = "wom-kit/project-version-update-receipt/v0.4"
        empty_repair_binding = project_version_update_approval_binding(
            empty_repair
        )
        self.assertNotEqual(
            first.plan_sha256,
            empty_repair_binding.plan_sha256,
        )

        ordinary_with_repair_receipt = copy.deepcopy(plan)
        ordinary_with_repair_receipt["approval_preparation"][
            "static_receipt"
        ]["schema"] = "wom-kit/project-version-update-receipt/v0.4"
        with self.assertRaises(OperationApprovalBindingError):
            project_version_update_approval_binding(
                ordinary_with_repair_receipt
            )

        repair_with_ordinary_receipt = copy.deepcopy(empty_repair)
        repair_with_ordinary_receipt["approval_preparation"][
            "static_receipt"
        ]["schema"] = "wom-kit/project-version-update-receipt/v0.3"
        with self.assertRaises(OperationApprovalBindingError):
            project_version_update_approval_binding(
                repair_with_ordinary_receipt
            )

        repair_with_ordinary_runtime_receipt = copy.deepcopy(empty_repair)
        for runtime_candidate in (
            repair_with_ordinary_runtime_receipt["approval_preparation"][
                "runtime_candidate"
            ],
            repair_with_ordinary_runtime_receipt["project_runtime"][
                "runtime_candidate"
            ],
        ):
            runtime_candidate["runtime_receipt_schema"] = (
                "wom-kit/project-runtime-receipt/v0.1"
            )
        with self.assertRaises(OperationApprovalBindingError):
            project_version_update_approval_binding(
                repair_with_ordinary_runtime_receipt
            )

        ordinary_with_repair_runtime_receipt = copy.deepcopy(plan)
        for runtime_candidate in (
            ordinary_with_repair_runtime_receipt["approval_preparation"][
                "runtime_candidate"
            ],
            ordinary_with_repair_runtime_receipt["project_runtime"][
                "runtime_candidate"
            ],
        ):
            runtime_candidate["runtime_receipt_schema"] = (
                "wom-kit/project-runtime-receipt/v0.2"
            )
        with self.assertRaises(OperationApprovalBindingError):
            project_version_update_approval_binding(
                ordinary_with_repair_runtime_receipt
            )

        impossible_repair = copy.deepcopy(empty_repair)
        for runtime_candidate in (
            impossible_repair["approval_preparation"]["runtime_candidate"],
            impossible_repair["project_runtime"]["runtime_candidate"],
        ):
            runtime_candidate["existing_runtime_reusable"] = True
        with self.assertRaises(OperationApprovalBindingError):
            project_version_update_approval_binding(impossible_repair)

        preparation = plan["approval_preparation"]
        for key in tuple(preparation):
            changed = copy.deepcopy(plan)
            del changed["approval_preparation"][key]
            with self.subTest(scope="preparation_missing", key=key):
                with self.assertRaises(OperationApprovalBindingError):
                    project_version_update_approval_binding(changed)
        changed = copy.deepcopy(plan)
        changed["approval_preparation"]["transaction_nonce_sha256"] = (
            "sha256:" + "f" * 64
        )
        with self.assertRaises(OperationApprovalBindingError):
            project_version_update_approval_binding(changed)

        exact_nested = (
            "trusted_git_runner",
            "transaction",
            "runtime_candidate",
            "static_receipt",
        )
        for nested in exact_nested:
            for key in tuple(preparation[nested]):
                changed = copy.deepcopy(plan)
                del changed["approval_preparation"][nested][key]
                with self.subTest(scope=f"{nested}_missing", key=key):
                    with self.assertRaises(OperationApprovalBindingError):
                        project_version_update_approval_binding(changed)
            changed = copy.deepcopy(plan)
            changed["approval_preparation"][nested]["unexpected"] = False
            with self.subTest(scope=f"{nested}_extra"):
                with self.assertRaises(OperationApprovalBindingError):
                    project_version_update_approval_binding(changed)

        fixed_truth = {
            "lock_held": False,
            "network_complete": False,
            "post_approval_network_allowed": True,
            "preapproval_control_writes_completed": False,
            "preapproval_domain_writes_completed": True,
            "fetched_refs_may_change": False,
            "preapproval_persistent_domain_effect": True,
            "preapproval_runtime_content_installed": True,
            "preapproval_activation_changed": True,
            "runtime_postapproval_child_process_allowed": True,
            "project_update_postapproval_local_git_allowed": False,
            "postapproval_git_transport_allowed": True,
        }
        for key, value in fixed_truth.items():
            changed = copy.deepcopy(plan)
            changed["approval_preparation"][key] = value
            with self.subTest(scope="preparation_truth", key=key):
                with self.assertRaises(OperationApprovalBindingError):
                    project_version_update_approval_binding(changed)

        cross_binding_mutations = (
            ("transaction", "static_receipt_domain_plan_sha256", "f"),
            ("transaction", "static_receipt_domain_target_binding_sha256", "f"),
            ("static_receipt", "domain_plan_sha256", "f"),
            ("static_receipt", "domain_target_binding_sha256", "f"),
            ("runtime_candidate", "candidate_sha256", "f"),
        )
        for nested, key, digit in cross_binding_mutations:
            changed = copy.deepcopy(plan)
            changed["approval_preparation"][nested][key] = (
                "sha256:" + digit * 64
            )
            with self.subTest(scope="cross_binding", nested=nested, key=key):
                with self.assertRaises(OperationApprovalBindingError):
                    project_version_update_approval_binding(changed)

        invariant_mutations = (
            ("transaction", "schema", "v0.4.2"),
            ("transaction", "intent_sha256", "sha256:" + "z" * 64),
            ("static_receipt", "schema", "v0.2"),
            ("static_receipt", "dynamic_claim_fields_embedded", True),
            ("runtime_candidate", "status", "prepared"),
            ("runtime_candidate", "post_approval_child_process_allowed", True),
            ("trusted_git_runner", "phase", "transport_open"),
            ("trusted_git_runner", "postapproval_transport_allowed", True),
        )
        for nested, key, value in invariant_mutations:
            changed = copy.deepcopy(plan)
            changed["approval_preparation"][nested][key] = value
            with self.subTest(scope="invariant", nested=nested, key=key):
                with self.assertRaises(OperationApprovalBindingError):
                    project_version_update_approval_binding(changed)

        legacy_bundle = copy.deepcopy(plan)
        legacy_bundle["project_runtime"]["prepared_bundle"] = {}
        with self.assertRaises(OperationApprovalBindingError):
            project_version_update_approval_binding(legacy_bundle)

        circular_claim = copy.deepcopy(plan)
        circular_claim["approval_preparation"]["static_receipt"][
            "final_approval_plan_sha256"
        ] = "sha256:" + "f" * 64
        with self.assertRaises(OperationApprovalBindingError):
            project_version_update_approval_binding(circular_claim)

        independently_bound_changes = []
        changed = copy.deepcopy(plan)
        changed["approval_preparation"]["transaction"]["intent_sha256"] = (
            "sha256:" + "f" * 64
        )
        independently_bound_changes.append(changed)
        changed = copy.deepcopy(plan)
        changed["approval_preparation"]["trusted_git_runner"][
            "runner_sha256"
        ] = "sha256:" + "f" * 64
        independently_bound_changes.append(changed)
        changed = copy.deepcopy(plan)
        for location in (
            changed["approval_preparation"]["runtime_candidate"],
            changed["project_runtime"]["runtime_candidate"],
        ):
            location["candidate_sha256"] = "sha256:" + "f" * 64
        independently_bound_changes.append(changed)
        changed = copy.deepcopy(plan)
        changed["approval_preparation"]["static_receipt"]["sha256"] = (
            "sha256:" + "f" * 64
        )
        independently_bound_changes.append(changed)
        changed = copy.deepcopy(plan)
        changed["approval_preparation"]["transaction"][
            "static_receipt_domain_plan_sha256"
        ] = "sha256:" + "f" * 64
        changed["approval_preparation"]["static_receipt"][
            "domain_plan_sha256"
        ] = "sha256:" + "f" * 64
        independently_bound_changes.append(changed)
        for index, changed in enumerate(independently_bound_changes):
            rebound = project_version_update_approval_binding(changed)
            with self.subTest(scope="digest_bound", index=index):
                self.assertNotEqual(first.plan_sha256, rebound.plan_sha256)
                self.assertNotEqual(
                    first.target_binding_sha256,
                    rebound.target_binding_sha256,
                )

        ordinary_dry_run = copy.deepcopy(plan)
        ordinary_dry_run["mode"] = "dry_run"
        with self.assertRaises(OperationApprovalBindingError) as captured:
            project_version_update_approval_binding(ordinary_dry_run)
        self.assertEqual(
            captured.exception.code,
            "operation_approval_plan_blocked",
        )


if __name__ == "__main__":
    unittest.main()
