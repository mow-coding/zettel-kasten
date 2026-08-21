from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path
from typing import Any, Callable

from wom_kit import exact_human_approval_windows
from wom_kit.exact_human_approval_windows import ExactHumanApprovalOperation
from wom_kit.operation_approval_binding import (
    OperationApprovalBindingError,
    zettel_objet_link_approval_binding,
)


WOM_KIT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_SCHEMA = (
    WOM_KIT_ROOT / "schemas" / "operation-exact-human-approval-v0.1.schema.json"
)
PACKAGED_SCHEMA = (
    WOM_KIT_ROOT
    / "src"
    / "wom_kit"
    / "_resources"
    / "schemas"
    / "operation-exact-human-approval-v0.1.schema.json"
)


def _service_jsonl_sha256(value: Any) -> str:
    raw = (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _reverse_mappings(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _reverse_mappings(item)
            for key, item in reversed(list(value.items()))
        }
    if isinstance(value, list):
        return [_reverse_mappings(item) for item in value]
    return value


class Letter140ZettelObjetBindingTests(unittest.TestCase):
    @staticmethod
    def control_path(zettel_id: str) -> str:
        return (
            "receipts/objects/zettel-links/.locks/"
            + hashlib.sha256(zettel_id.encode("utf-8")).hexdigest()
            + ".lock"
        )

    def plan(self) -> dict[str, Any]:
        zettel_id = "PRIVATE_ZETTEL_ID"
        zettel_sha256 = "sha256:" + "1" * 64
        control_sha256 = "sha256:" + hashlib.sha256(
            b"wom-kit/zettel-objet-link-lock/v0.1\n"
        ).hexdigest()
        control_path = self.control_path(zettel_id)
        transaction_sha256 = "sha256:" + "7" * 64
        canonical_swap_path = (
            "zettels/." + "7" * 64 + "." + "8" * 24
            + ".zettel-objet-link.swap"
        )
        canonical_previous_path = canonical_swap_path + ".previous"
        support_effect_set = {
            "zettel": {
                "path": "zettels/private-zettel.md",
                "before_sha256": zettel_sha256,
            },
            "snapshot": {
                "path": (
                    "receipts/objects/zettel-links/snapshots/"
                    + "1" * 64
                    + ".md"
                ),
                "state": "absent",
                "sha256": zettel_sha256,
            },
            "receipt": {
                "path": (
                    "receipts/objects/zettel-links/"
                    "link.555555555555555555555555.g0001.json"
                ),
                "generation": 1,
            },
            "canonical_compare_and_swap": {
                "transaction_sha256": transaction_sha256,
                "swap_path": canonical_swap_path,
                "previous_path": canonical_previous_path,
                "state": "absent",
            },
        }
        plan = {
            "ok": True,
            "state": "ready",
            "dry_run": True,
            "lifecycle_action": "zettel_objet_link_plan",
            "summary": {
                "zettel_id": zettel_id,
                "zettel_path": support_effect_set["zettel"]["path"],
                "object_id": "sha256:" + "2" * 64,
                "role": "primary_source",
                "label_present": True,
                "label_sha256": "sha256:" + "3" * 64,
                "link_id": "asset:sha256:" + "5" * 64,
                "current_asset_count": 2,
                "manifest_record_count": 1,
                "manifest_record_set_sha256": "sha256:" + "4" * 64,
                "zettel_sha256": zettel_sha256,
                "receipt_path": support_effect_set["receipt"]["path"],
                "receipt_generation": 1,
                "snapshot_path": support_effect_set["snapshot"]["path"],
                "snapshot_state": "absent",
                "snapshot_sha256": zettel_sha256,
                "support_effect_set_sha256": _service_jsonl_sha256(
                    support_effect_set
                ),
                "transaction_sha256": transaction_sha256,
                "canonical_swap_path": canonical_swap_path,
                "canonical_previous_path": canonical_previous_path,
                "canonical_swap_state": "absent",
                "control_artifact_path": control_path,
                "control_artifact_state": "absent",
                "control_artifact_sha256": control_sha256,
                "plan_sha256": "sha256:" + "6" * 64,
            },
            "data": {
                "manifest_record_set_complete": True,
                "manifest_record_set_unique": True,
                "support_effect_set": support_effect_set,
                "control_artifact": {
                    "kind": "zettel_objet_link_lock",
                    "path": control_path,
                    "state": "absent",
                    "sha256": control_sha256,
                },
                "record_shape": {
                    "required_fields": ["object_id", "role"],
                    "optional_fields": ["label"],
                    "unknown_fields_allowed": False,
                },
                "receipt_schema": "wom-kit/zettel-objet-link-receipt/v0.1",
                "exact_byte_revert_supported": True,
            },
            "blockers": [],
            "warnings": ["manifest_record_set_reviewed"],
            "would_change": [
                "zettels/private-zettel.md frontmatter.assets +1",
                support_effect_set["snapshot"]["path"],
                support_effect_set["receipt"]["path"],
            ],
        }
        return plan

    def refresh_service_digests(self, plan: dict[str, Any]) -> None:
        summary = plan["summary"]
        summary["support_effect_set_sha256"] = _service_jsonl_sha256(
            plan["data"]["support_effect_set"]
        )
        plan_basis = {
            "summary": {
                key: value
                for key, value in summary.items()
                if key != "plan_sha256"
            },
            "data": plan["data"],
            "warnings": plan["warnings"],
            "would_change": plan["would_change"],
        }
        summary["plan_sha256"] = _service_jsonl_sha256(plan_basis)

    def assert_target_drift(
        self,
        mutate: Callable[[dict[str, Any]], None],
    ) -> None:
        original_plan = self.plan()
        original = zettel_objet_link_approval_binding(original_plan)
        changed_plan = copy.deepcopy(original_plan)
        mutate(changed_plan)
        self.refresh_service_digests(changed_plan)
        changed = zettel_objet_link_approval_binding(changed_plan)
        self.assertNotEqual(original.target_binding_sha256, changed.target_binding_sha256)
        self.assertNotEqual(original.plan_sha256, changed.plan_sha256)

    def test_binding_is_deterministic_content_free_and_has_safe_label(self) -> None:
        plan = self.plan()
        first = zettel_objet_link_approval_binding(plan)
        second = zettel_objet_link_approval_binding(_reverse_mappings(plan))

        self.assertIs(
            first.operation,
            ExactHumanApprovalOperation.zettel_objet_link,
        )
        self.assertEqual(first, second)
        public = json.dumps(first.public_document(), ensure_ascii=False)
        self.assertNotIn("PRIVATE_ZETTEL_ID", public)
        self.assertNotIn("private-zettel.md", public)
        context = first.context(
            archive_id="archive:letter140-test",
            reviewer_claim="person:reviewer",
        )
        dialog = exact_human_approval_windows._dialog_content(context)
        self.assertIn("작업: 제텔-오브제 연결 생성", dialog)
        self.assertNotIn("PRIVATE_ZETTEL_ID", dialog)

    def test_every_target_and_effect_component_changes_the_binding(self) -> None:
        def zettel_id(plan: dict[str, Any]) -> None:
            changed = "PRIVATE_ZETTEL_ID_CHANGED"
            changed_control_path = self.control_path(changed)
            plan["summary"]["zettel_id"] = changed
            plan["summary"]["control_artifact_path"] = changed_control_path
            plan["data"]["control_artifact"]["path"] = changed_control_path

        def zettel_path(plan: dict[str, Any]) -> None:
            changed = "zettels/private-zettel-moved.md"
            plan["summary"]["zettel_path"] = changed
            plan["data"]["support_effect_set"]["zettel"]["path"] = changed

        def zettel_bytes(plan: dict[str, Any]) -> None:
            changed = "sha256:" + "7" * 64
            plan["summary"]["zettel_sha256"] = changed
            plan["summary"]["snapshot_sha256"] = changed
            plan["data"]["support_effect_set"]["zettel"][
                "before_sha256"
            ] = changed
            plan["data"]["support_effect_set"]["snapshot"]["sha256"] = changed

        def receipt_path(plan: dict[str, Any]) -> None:
            changed = (
                "receipts/objects/zettel-links/"
                "link.555555555555555555555555.g0002.json"
            )
            plan["summary"]["receipt_path"] = changed
            plan["data"]["support_effect_set"]["receipt"]["path"] = changed

        def receipt_generation(plan: dict[str, Any]) -> None:
            plan["summary"]["receipt_generation"] = 2
            plan["data"]["support_effect_set"]["receipt"]["generation"] = 2

        def snapshot_path(plan: dict[str, Any]) -> None:
            changed = "receipts/objects/zettel-links/snapshots/alternate.md"
            plan["summary"]["snapshot_path"] = changed
            plan["data"]["support_effect_set"]["snapshot"]["path"] = changed

        def snapshot_state(plan: dict[str, Any]) -> None:
            plan["summary"]["snapshot_state"] = "existing_exact"
            plan["data"]["support_effect_set"]["snapshot"][
                "state"
            ] = "existing_exact"

        def control_artifact_state(plan: dict[str, Any]) -> None:
            plan["summary"]["control_artifact_state"] = "existing_exact"
            plan["data"]["control_artifact"]["state"] = "existing_exact"

        def transaction_sha256(plan: dict[str, Any]) -> None:
            changed = "sha256:" + "c" * 64
            plan["summary"]["transaction_sha256"] = changed
            plan["data"]["support_effect_set"][
                "canonical_compare_and_swap"
            ]["transaction_sha256"] = changed

        def canonical_swap_path(plan: dict[str, Any]) -> None:
            changed = (
                "zettels/." + "c" * 64 + "." + "d" * 24
                + ".zettel-objet-link.swap"
            )
            plan["summary"]["canonical_swap_path"] = changed
            plan["data"]["support_effect_set"][
                "canonical_compare_and_swap"
            ]["swap_path"] = changed

        def canonical_previous_path(plan: dict[str, Any]) -> None:
            changed = (
                "zettels/." + "c" * 64 + "." + "d" * 24
                + ".zettel-objet-link.swap.previous"
            )
            plan["summary"]["canonical_previous_path"] = changed
            plan["data"]["support_effect_set"][
                "canonical_compare_and_swap"
            ]["previous_path"] = changed

        mutations: dict[str, Callable[[dict[str, Any]], None]] = {
            "zettel_id_and_control_artifact_path": zettel_id,
            "zettel_path_digest": zettel_path,
            "zettel_current_sha256": zettel_bytes,
            "object_id": lambda plan: plan["summary"].__setitem__(
                "object_id", "sha256:" + "8" * 64
            ),
            "manifest_record_set_sha256": lambda plan: plan["summary"].__setitem__(
                "manifest_record_set_sha256", "sha256:" + "9" * 64
            ),
            "role": lambda plan: plan["summary"].__setitem__(
                "role", "supporting_source"
            ),
            "label_sha256": lambda plan: plan["summary"].__setitem__(
                "label_sha256", "sha256:" + "a" * 64
            ),
            "link_id": lambda plan: plan["summary"].__setitem__(
                "link_id", "asset:sha256:" + "b" * 64
            ),
            "receipt_path": receipt_path,
            "receipt_generation": receipt_generation,
            "snapshot_path": snapshot_path,
            "snapshot_state": snapshot_state,
            "transaction_sha256": transaction_sha256,
            "canonical_swap_path": canonical_swap_path,
            "canonical_previous_path": canonical_previous_path,
            "control_artifact_state": control_artifact_state,
            "current_asset_count": lambda plan: plan["summary"].__setitem__(
                "current_asset_count", 3
            ),
            "label_present": lambda plan: plan["summary"].__setitem__(
                "label_present", False
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(component=name):
                self.assert_target_drift(mutate)

    def test_warnings_and_would_change_each_invalidate_the_plan_only(self) -> None:
        first = zettel_objet_link_approval_binding(self.plan())
        for field, value in (
            ("warnings", ["manifest_record_set_reviewed", "new_warning"]),
            ("would_change", ["a different complete effect projection"]),
        ):
            changed_plan = self.plan()
            changed_plan[field] = value
            self.refresh_service_digests(changed_plan)
            changed = zettel_objet_link_approval_binding(changed_plan)
            with self.subTest(component=field):
                self.assertNotEqual(first.plan_sha256, changed.plan_sha256)
                self.assertEqual(
                    first.target_binding_sha256,
                    changed.target_binding_sha256,
                )

    def test_manifest_completeness_and_uniqueness_are_mandatory(self) -> None:
        for field in (
            "manifest_record_set_complete",
            "manifest_record_set_unique",
        ):
            plan = self.plan()
            plan["data"][field] = False
            with self.subTest(field=field), self.assertRaises(
                OperationApprovalBindingError
            ) as captured:
                zettel_objet_link_approval_binding(plan)
            self.assertEqual(
                captured.exception.code,
                "operation_approval_plan_invalid",
            )

        plan = self.plan()
        plan["summary"]["manifest_record_count"] = 2
        with self.assertRaises(OperationApprovalBindingError):
            zettel_objet_link_approval_binding(plan)

    def test_support_effect_representations_must_match_exactly(self) -> None:
        mismatches = (
            ("zettel_path", ("zettel", "path"), "zettels/drift.md"),
            (
                "zettel_sha256",
                ("zettel", "before_sha256"),
                "sha256:" + "c" * 64,
            ),
            ("snapshot_path", ("snapshot", "path"), "snapshots/drift.md"),
            ("snapshot_state", ("snapshot", "state"), "existing_exact"),
            (
                "snapshot_sha256",
                ("snapshot", "sha256"),
                "sha256:" + "d" * 64,
            ),
            ("receipt_path", ("receipt", "path"), "receipts/drift.json"),
            ("receipt_generation", ("receipt", "generation"), 2),
        )
        for name, (effect, field), value in mismatches:
            plan = self.plan()
            plan["data"]["support_effect_set"][effect][field] = value
            plan["summary"]["support_effect_set_sha256"] = _service_jsonl_sha256(
                plan["data"]["support_effect_set"]
            )
            with self.subTest(component=name), self.assertRaises(
                OperationApprovalBindingError
            ):
                zettel_objet_link_approval_binding(plan)

        plan = self.plan()
        plan["summary"]["support_effect_set_sha256"] = "sha256:" + "e" * 64
        with self.assertRaises(OperationApprovalBindingError):
            zettel_objet_link_approval_binding(plan)

    def test_snapshot_digest_must_equal_current_zettel_bytes(self) -> None:
        plan = self.plan()
        changed = "sha256:" + "f" * 64
        plan["summary"]["snapshot_sha256"] = changed
        plan["data"]["support_effect_set"]["snapshot"]["sha256"] = changed
        plan["summary"]["support_effect_set_sha256"] = _service_jsonl_sha256(
            plan["data"]["support_effect_set"]
        )
        with self.assertRaises(OperationApprovalBindingError):
            zettel_objet_link_approval_binding(plan)

    def test_control_artifact_is_exact_and_cannot_be_omitted_or_substituted(
        self,
    ) -> None:
        mutations: tuple[Callable[[dict[str, Any]], None], ...] = (
            lambda plan: plan["summary"].__setitem__(
                "control_artifact_path",
                "receipts/objects/zettel-links/.locks/wrong.lock",
            ),
            lambda plan: plan["summary"].__setitem__(
                "control_artifact_sha256",
                "sha256:" + "0" * 64,
            ),
            lambda plan: plan["data"]["control_artifact"].__setitem__(
                "kind",
                "different_lock",
            ),
            lambda plan: plan["data"].pop("control_artifact"),
        )
        for index, mutate in enumerate(mutations):
            plan = self.plan()
            mutate(plan)
            with self.subTest(case=index), self.assertRaises(
                OperationApprovalBindingError
            ):
                zettel_objet_link_approval_binding(plan)

    def test_all_digest_references_and_state_codes_are_strict(self) -> None:
        digest_fields = (
            "zettel_sha256",
            "object_id",
            "manifest_record_set_sha256",
            "label_sha256",
            "snapshot_sha256",
            "support_effect_set_sha256",
            "control_artifact_sha256",
            "plan_sha256",
        )
        for field in digest_fields:
            plan = self.plan()
            plan["summary"][field] = "not-a-digest"
            with self.subTest(field=field), self.assertRaises(
                OperationApprovalBindingError
            ):
                zettel_objet_link_approval_binding(plan)

        for state in ("existing_mismatch", "unknown", ""):
            plan = self.plan()
            plan["summary"]["snapshot_state"] = state
            plan["data"]["support_effect_set"]["snapshot"]["state"] = state
            plan["summary"]["support_effect_set_sha256"] = _service_jsonl_sha256(
                plan["data"]["support_effect_set"]
            )
            with self.subTest(state=state), self.assertRaises(
                OperationApprovalBindingError
            ):
                zettel_objet_link_approval_binding(plan)

    def test_blocked_non_dry_run_or_incomplete_plan_fails_closed(self) -> None:
        variants = []
        blocked = self.plan()
        blocked["ok"] = False
        variants.append((blocked, "operation_approval_plan_blocked"))
        live = self.plan()
        live["dry_run"] = False
        variants.append((live, "operation_approval_plan_blocked"))
        incomplete = self.plan()
        del incomplete["data"]["support_effect_set"]["snapshot"]
        variants.append((incomplete, "operation_approval_plan_invalid"))
        for plan, expected_code in variants:
            with self.subTest(code=expected_code), self.assertRaises(
                OperationApprovalBindingError
            ) as captured:
                zettel_objet_link_approval_binding(plan)
            self.assertEqual(captured.exception.code, expected_code)
            self.assertNotIn("PRIVATE", str(captured.exception))

    def test_source_and_packaged_receipt_schema_enums_stay_in_parity(self) -> None:
        self.assertEqual(SOURCE_SCHEMA.read_bytes(), PACKAGED_SCHEMA.read_bytes())
        source = json.loads(SOURCE_SCHEMA.read_text(encoding="utf-8"))
        packaged = json.loads(PACKAGED_SCHEMA.read_text(encoding="utf-8"))
        expected = {
            "promote_zet",
            "warning_override",
            "mint_zet",
            "zettel_edge",
            "zettel_objet_link",
            "retire_draft",
        }
        self.assertEqual(set(source["properties"]["operation"]["enum"]), expected)
        self.assertEqual(
            source["properties"]["operation"]["enum"],
            packaged["properties"]["operation"]["enum"],
        )
        self.assertIn(
            "zettel_objet_link",
            {operation.value for operation in ExactHumanApprovalOperation},
        )


if __name__ == "__main__":
    unittest.main()
