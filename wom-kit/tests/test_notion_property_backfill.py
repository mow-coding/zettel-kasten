from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any, Callable
from unittest import mock

import yaml
from jsonschema import Draft202012Validator

from wom_kit.exact_human_approval import (
    _ClaimedExactHumanApproval as ClaimedExactHumanApproval,
    _claim_exact_human_approval_core as claim_exact_human_approval,
)
from wom_kit.exact_human_approval_windows import (
    ExactHumanApprovalOperation,
    _ExactHumanApprovalDecision as ExactHumanApprovalDecision,
)
from wom_kit.exact_human_approval_workflow import ExactHumanApprovalWorkflowError
from wom_kit.exact_operation_manifest import (
    ExactOperationManifest,
    ExactOperationManifestError,
    exact_operation_execution_sha256,
)
from wom_kit import notion_property_backfill as backfill_module
from wom_kit.notion_property_backfill import (
    NOTION_PROPERTY_BACKFILL_OPERATION,
    SOURCE_PROPERTIES_SCHEMA_VERSION,
    NotionPropertyBackfillError,
    _apply_notion_property_backfill_core as apply_notion_property_backfill,
    _notion_property_backfill_context as notion_property_backfill_context,
    _parse_mirror_page as parse_mirror_page,
    _plan_notion_property_backfill_core as plan_notion_property_backfill,
    _revert_notion_property_backfill_core as revert_notion_property_backfill,
    plan_notion_property_backfill as public_notion_property_backfill_plan,
    verify_notion_property_backfill,
)


AUTHENTICATION_KEY = bytes(range(32))
REVIEWER_CLAIM = "person:operator"


class _KeyProvider:
    def use_key(
        self,
        _root: Path | str,
        consumer: Callable[[memoryview], Any],
        *,
        create_if_missing: bool = False,
    ) -> Any:
        if create_if_missing:
            raise AssertionError("resume must never create an authentication key")
        key = bytearray(AUTHENTICATION_KEY)
        try:
            return consumer(memoryview(key))
        finally:
            key[:] = b"\0" * len(key)


def _property(property_id: str, property_type: str, value):
    return {
        "id": property_id,
        "type": property_type,
        property_type: value,
    }


def _api_page(page_id: str, properties: dict[str, dict]):
    return {
        "page_id": page_id,
        "object_record": {
            "object": "page",
            "id": page_id,
            "properties": properties,
        },
        "blocks": [],
    }


def _json_bytes(document) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


class NotionPropertyBackfillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "archive"
        self.root.mkdir()
        (self.root / "archive.yml").write_text(
            "archive_id: archive:test:notion-backfill\n",
            encoding="utf-8",
        )
        (self.root / "zettels").mkdir()
        self.claims: list[ClaimedExactHumanApproval] = []

    def tearDown(self) -> None:
        for claim in self.claims:
            claim.close()
        self.temporary.cleanup()

    def write_canonical(
        self,
        page_id: str,
        *,
        name: str,
        title: str = "Original",
        source_properties: dict | None = None,
    ) -> Path:
        frontmatter = {
            "id": f"zet:{name}",
            "title": title,
            "archive_id": "archive:test:notion-backfill",
            "status": "canonical",
            "facets": {"source_page_id": page_id},
        }
        if source_properties is not None:
            frontmatter["source_properties"] = source_properties
        raw = (
            "---\n"
            + yaml.safe_dump(
                frontmatter,
                allow_unicode=True,
                sort_keys=False,
                width=10_000,
            )
            + "---\nBody before recovery.\n"
        )
        path = self.root / "zettels" / f"{name}.md"
        path.write_text(raw, encoding="utf-8", newline="\n")
        return path

    def write_block_page(self, mirror: Path, document: dict) -> None:
        page_id = document["page_id"]
        (mirror / f"{page_id}.json").write_bytes(_json_bytes(document))

    def claim(self, context, *, seed: int) -> ClaimedExactHumanApproval:
        decision = ExactHumanApprovalDecision(
            approved=True,
            synthetic_acknowledged=False,
            reason_code="exact_human_approval_approved",
            plan_sha256=context.plan_sha256,
            target_binding_sha256=context.target_binding_sha256,
        )
        claim = claim_exact_human_approval(
            self.root,
            context,
            decision,
            AUTHENTICATION_KEY,
            random_hex=lambda _size: f"{seed:032x}",
        )
        self.claims.append(claim)
        return claim

    def one_page_plan(self):
        page_id = "11111111-1111-1111-1111-111111111111"
        mirror = Path(self.temporary.name) / "mirror"
        mirror.mkdir()
        page = _api_page(
            page_id,
            {
                "Client email": _property(
                    "email-id",
                    "email",
                    "client-canary@example.test",
                )
            },
        )
        self.write_block_page(mirror, page)
        target = self.write_canonical(page_id, name="one")
        bootstrap = plan_notion_property_backfill(self.root, mirror)
        acceptance = bootstrap.public_document()["acceptance_candidate"]
        plan = plan_notion_property_backfill(
            self.root,
            mirror,
            acceptance=acceptance,
        )
        context = notion_property_backfill_context(
            plan,
            reviewer_claim=REVIEWER_CLAIM,
        )
        return page_id, mirror, target, plan, context

    def test_block_mirror_accounts_for_every_page_property_and_category(self) -> None:
        mirror = Path(self.temporary.name) / "mixed-block-mirror"
        mirror.mkdir()
        mapped_id = "mapped-page"
        unmapped_id = "unmapped-page"
        record_map_id = "record-map-page"
        record_map_missing_id = "record-map-missing-page"
        equal_id = "equal-page"
        mapped = _api_page(
            mapped_id,
            {"Email": _property("email-id", "email", "private@example.test")},
        )
        unmapped = _api_page(
            unmapped_id,
            {"URL": _property("url-id", "url", "https://private.invalid")},
        )
        record_map = {
            "page_id": record_map_id,
            "recordMap": {
                "block": {
                    record_map_id: {
                        "value": {
                            "value": {
                                "id": record_map_id,
                                "properties": {"internal-title-id": [["Legacy"]]},
                            }
                        }
                    }
                }
            },
        }
        record_map_missing = {
            "page_id": record_map_missing_id,
            "recordMap": {
                "block": {
                    record_map_missing_id: {
                        "value": {"value": {"id": record_map_missing_id}}
                    }
                }
            },
        }
        equal = _api_page(
            equal_id,
            {
                "Date": _property(
                    "date-id",
                    "date",
                    {"start": "2026-08-22", "end": None},
                )
            },
        )
        for page in (mapped, unmapped, record_map, record_map_missing, equal):
            self.write_block_page(mirror, page)
        self.write_canonical(mapped_id, name="mapped")
        self.write_canonical(record_map_id, name="opaque-mapped")
        self.write_canonical(record_map_missing_id, name="review")
        equal_source = parse_mirror_page(_json_bytes(equal)).source_properties()
        self.write_canonical(
            equal_id,
            name="equal",
            source_properties=equal_source,
        )

        bootstrap = public_notion_property_backfill_plan(
            self.root,
            mirror,
        )
        public = public_notion_property_backfill_plan(
            self.root,
            mirror,
            acceptance=bootstrap["acceptance_candidate"],
        )

        self.assertTrue(public["ok"])
        self.assertEqual(public["mirror_source_kind"], "block_mirror_directory")
        self.assertEqual(
            public["source_format_page_counts"],
            {"legacy_record_map": 2, "notion_api_page": 3},
        )
        self.assertEqual(
            public["legacy_record_map_root_page_counts"],
            {"properties_present": 1, "properties_absent": 1},
        )
        self.assertEqual(
            public["normalized_source_id_page_counts"],
            {"unique": 5, "duplicate": 0, "invalid": 0},
        )
        self.assertEqual(
            public["category_counts"],
            {"mapped": 2, "already_equal": 1, "unmapped": 1, "review": 1},
        )
        self.assertEqual(public["unmapped_populated_page_count"], 1)
        self.assertEqual(public["unmapped_populated_property_count"], 1)
        self.assertEqual(
            public["unmapped_reason_counts"],
            {"unmapped_no_canonical_target": 1},
        )
        self.assertTrue(public["unresolved_source_evidence_not_modified"])
        self.assertFalse(public["unresolved_source_lifecycle_guaranteed"])
        self.assertFalse(public["unmapped_treated_as_drop"])
        self.assertRegex(
            public["classification_binding_sha256"],
            r"^sha256:[0-9a-f]{64}$",
        )
        self.assertRegex(
            public["unresolved_reason_set_sha256"],
            r"^sha256:[0-9a-f]{64}$",
        )
        self.assertEqual(sum(public["category_counts"].values()), 5)
        self.assertEqual(sum(public["category_property_counts"].values()), 4)
        self.assertEqual(
            sum(public["category_populated_property_counts"].values()),
            public["populated_property_count"],
        )
        self.assertEqual(
            public["review_reason_counts"],
            {"record_map_root_properties_absent": 1},
        )
        self.assertEqual(public["opaque_source_page_count"], 1)
        self.assertEqual(public["opaque_property_count"], 1)
        self.assertEqual(
            public["category_opaque_property_counts"],
            {"mapped": 1, "already_equal": 0, "unmapped": 0, "review": 0},
        )
        self.assertEqual(
            public["warning_reason_counts"],
            {"record_map_property_semantics_unavailable": 1},
        )
        self.assertIn("opaque_record_map_properties_present", public["warning_codes"])
        self.assertEqual(public["unexplained_missing_populated_property_count"], 0)
        self.assertEqual(
            public["unexplained_missing_populated_property_type_count"], 0
        )
        self.assertTrue(public["zero_silent_omission"])
        serialized = json.dumps(public, ensure_ascii=False, sort_keys=True)
        for canary in (
            "private@example.test",
            "https://private.invalid",
            mapped_id,
            str(self.root),
        ):
            self.assertNotIn(canary, serialized)

    def test_final_receipt_durably_retains_unresolved_classification(self) -> None:
        mirror = Path(self.temporary.name) / "unresolved-receipt-mirror"
        mirror.mkdir()
        mapped_id = "receipt-mapped-page"
        unmapped_id = "receipt-unmapped-page"
        review_id = "receipt-review-page"
        self.write_block_page(
            mirror,
            _api_page(
                mapped_id,
                {"Email": _property("email-id", "email", "secret@example.test")},
            ),
        )
        self.write_block_page(
            mirror,
            _api_page(
                unmapped_id,
                {"URL": _property("url-id", "url", "https://secret.invalid")},
            ),
        )
        self.write_block_page(
            mirror,
            {
                "page_id": review_id,
                "recordMap": {
                    "block": {
                        review_id: {
                            "value": {"value": {"id": review_id}}
                        }
                    }
                },
            },
        )
        self.write_canonical(mapped_id, name="receipt-mapped")
        self.write_canonical(review_id, name="receipt-review")
        bootstrap = plan_notion_property_backfill(self.root, mirror)
        plan = plan_notion_property_backfill(
            self.root,
            mirror,
            acceptance=bootstrap.public_document()["acceptance_candidate"],
        )
        context = notion_property_backfill_context(
            plan,
            reviewer_claim=REVIEWER_CLAIM,
        )

        result = apply_notion_property_backfill(
            plan,
            self.claim(context, seed=91),
            context=context,
        )

        receipt_path = (
            self.root
            / "receipts"
            / "ops"
            / "exact-operations"
            / f"{result['execution']['execution_sha256'][7:]}.json"
        )
        durable = json.loads(receipt_path.read_text(encoding="utf-8"))[
            "result"
        ]["operation_evidence"]
        self.assertEqual(
            durable["counts"],
            {
                "already_equal_page_count": 0,
                "canonical_file_count": 2,
                "effect_count": 1,
                "excluded_non_candidate_malformed_count": 0,
                "mapped_page_count": 1,
                "mapped_populated_property_count": 1,
                "mapped_property_count": 1,
                "opaque_property_count": 0,
                "populated_property_count": 2,
                "review_page_count": 1,
                "source_page_count": 3,
                "source_property_count": 2,
                "unexplained_missing_populated_property_count": 0,
                "unexplained_missing_populated_property_type_count": 0,
                "unmapped_opaque_property_count": 0,
                "unmapped_page_count": 1,
                "unmapped_populated_page_count": 1,
                "unmapped_populated_property_count": 1,
            },
        )
        self.assertEqual(
            durable["digests"]["unresolved_source_set_sha256"],
            plan.unresolved_source_set_sha256,
        )
        self.assertEqual(
            durable["digests"]["unresolved_reason_set_sha256"],
            plan.unresolved_reason_set_sha256,
        )
        self.assertEqual(result["durable_operation_evidence"], durable)
        serialized = json.dumps(durable, ensure_ascii=False, sort_keys=True)
        for canary in (
            mapped_id,
            unmapped_id,
            review_id,
            "secret@example.test",
            "https://secret.invalid",
            str(self.root),
        ):
            self.assertNotIn(canary, serialized)

    def test_every_populated_property_type_is_retained_losslessly(self) -> None:
        values = {
            "title": [{"plain_text": "Title"}],
            "rich_text": [{"plain_text": "Text"}],
            "number": 7,
            "select": {"id": "s", "name": "Selected", "color": "blue"},
            "multi_select": [{"id": "m", "name": "Many", "color": "red"}],
            "date": {"start": "2026-08-22", "end": None},
            "people": [{"object": "user", "id": "person-id"}],
            "files": [{"name": "file", "type": "external", "external": {"url": "https://asset.invalid"}}],
            "checkbox": False,
            "url": "https://example.invalid",
            "email": "person@example.test",
            "phone_number": "+82-00-0000-0000",
            "formula": {"type": "number", "number": 3},
            "relation": [{"id": "related-page"}],
            "rollup": {"type": "number", "number": 4, "function": "sum"},
            "created_time": "2026-08-22T00:00:00.000Z",
            "created_by": {"object": "user", "id": "creator"},
            "last_edited_time": "2026-08-22T01:00:00.000Z",
            "last_edited_by": {"object": "user", "id": "editor"},
            "status": {"id": "status", "name": "Done", "color": "green"},
            "unique_id": {"number": 42, "prefix": "X"},
            "verification": {"state": "verified", "verified_by": {"id": "reviewer"}},
            "button": {"label": "Run"},
            "future_type": {"nested": ["preserve", {"exact": True}]},
        }
        properties = {
            f"Property {index:02d}": _property(f"id-{index:02d}", kind, value)
            for index, (kind, value) in enumerate(values.items())
        }
        parsed = parse_mirror_page(
            _json_bytes(_api_page("all-property-types", properties))
        )

        self.assertEqual(parsed.property_count, len(values))
        self.assertEqual(parsed.populated_property_count, len(values))
        self.assertEqual(parsed.indeterminate_property_count, 0)
        self.assertEqual(parsed.review_codes, ())
        self.assertEqual(
            {item.property_type for item in parsed.properties}, set(values)
        )
        by_name = {item.property_name: item for item in parsed.properties}
        for name, original in properties.items():
            self.assertEqual(by_name[name].raw_json_payload, original)
            self.assertEqual(by_name[name].population_state, "populated")

    def test_11585_inventory_reproduces_historical_probe_without_using_it_as_semantics(self) -> None:
        mirror = Path(self.temporary.name) / "synthetic-11585.jsonl"
        with mirror.open("wb") as stream:
            for index in range(11_585):
                page_id = f"synthetic-page-{index:05d}"
                if index < 901:
                    url_property = _property(
                        "url-id", "url", "https://counted.invalid"
                    )
                    url_name = "URL"
                elif index < 904:
                    # The historical raw-text regex sees this extra ``url``
                    # key, while semantic parsing correctly sees a future
                    # property type rather than a Notion URL property.
                    url_property = {
                        "id": "url-id",
                        "type": "url_shadow",
                        "url": "https://regex-only.invalid",
                        "url_shadow": "opaque",
                    }
                    url_name = "URL"
                elif 4_000 <= index < 4_003:
                    url_property = _property(
                        "url-id", "url", "https://after-head.invalid"
                    )
                    url_name = "URL"
                elif 4_003 <= index < 4_016:
                    url_property = _property(
                        "url-id", "url", "https://other-name.invalid"
                    )
                    url_name = "Website"
                else:
                    url_property = _property("url-id", "url", None)
                    url_name = "URL"
                if index < 2_810:
                    date_property = _property(
                        "date-id", "date", {"start": "2026-08-22"}
                    )
                    date_name = "날짜"
                elif index < 2_827:
                    date_property = _property(
                        "date-id", "date", {"start": "2026-08-22"}
                    )
                    date_name = "날짜"
                elif index < 3_439:
                    date_property = _property(
                        "date-id", "date", {"start": "2026-08-22"}
                    )
                    date_name = "Schedule"
                else:
                    date_property = _property("date-id", "date", None)
                    date_name = "날짜"
                properties = {
                    "이메일": _property(
                        "email-id",
                        "email",
                        "counted@example.test" if index < 51 else None,
                    ),
                    url_name: url_property,
                    date_name: date_property,
                }
                if 2_810 <= index < 2_827 or 4_000 <= index < 4_003:
                    properties["A padding"] = _property(
                        "padding-id", "padding", "x" * 45_000
                    )
                document = {
                    "id": page_id,
                    "properties": properties,
                }
                stream.write(_json_bytes(document) + b"\n")
        self.write_canonical("synthetic-page-00000", name="scale-target")
        progress: list[dict] = []

        public = public_notion_property_backfill_plan(
            self.root,
            mirror,
            progress=progress.append,
        )

        self.assertFalse(public["ok"])
        self.assertFalse(public["acceptance_verified"])
        self.assertEqual(
            public["acceptance_mismatch_codes"],
            ["acceptance_profile_required"],
        )
        self.assertEqual(public["mirror_page_count"], 11_585)
        self.assertEqual(
            public["populated_page_counts_by_property_type"],
            {
                "date": 3_439,
                "email": 51,
                "padding": 20,
                "url": 917,
                "url_shadow": 3,
            },
        )
        self.assertEqual(
            public["historical_named_head_page_counts_by_property_type"],
            {"date": 2_810, "email": 51, "url": 904},
        )
        self.assertEqual(
            public["historical_named_full_page_counts_by_property_type"],
            {"date": 2_827, "email": 51, "url": 907},
        )
        self.assertEqual(
            public["historical_probe_reason_counts_by_property_type"],
            {
                "date": {
                    "exact_name_after_40k": 17,
                    "matched_same_page": 2_810,
                    "other_property_name_only": 612,
                },
                "email": {"matched_same_page": 51},
                "url": {
                    "exact_name_after_40k": 3,
                    "matched_same_page": 901,
                    "other_property_name_only": 13,
                    "regex_without_root_semantic": 3,
                },
            },
        )
        self.assertEqual(
            public["historical_probe_reason_counts_by_source_format"],
            {
                "notion_api_page": public[
                    "historical_probe_reason_counts_by_property_type"
                ]
            },
        )
        self.assertEqual(
            public["category_counts"],
            {"mapped": 1, "already_equal": 0, "unmapped": 11_584, "review": 0},
        )
        self.assertEqual(
            public["source_format_page_counts"], {"notion_api_page": 11_585}
        )
        self.assertEqual(
            sum(public["category_property_counts"].values()),
            public["source_property_count"],
        )
        self.assertEqual(
            sum(public["category_populated_property_counts"].values()),
            public["populated_property_count"],
        )
        self.assertEqual(public["unexplained_missing_populated_property_count"], 0)
        self.assertEqual(
            public["unexplained_missing_populated_property_type_count"], 0
        )
        self.assertTrue(public["zero_silent_omission"])
        self.assertEqual(progress[0]["stage"], "starting")
        self.assertEqual(progress[0]["processed"], 0)
        self.assertIn("acquire_mirror", {event["stage"] for event in progress})
        self.assertIn("scan_canonical", {event["stage"] for event in progress})
        completed_join = next(
            event
            for event in progress
            if event["stage"] == "join_and_classify"
            and event["processed"] == 11_585
        )
        self.assertEqual(completed_join["total"], 11_585)
        self.assertEqual(progress[-1]["stage"], "finalize_plan")
        self.assertEqual(progress[-1]["processed"], progress[-1]["total"])
        self.assertTrue(
            all(
                event["private_values_echoed"] is False
                and event["paths_echoed"] is False
                for event in progress
            )
        )

        wrong_acceptance = dict(public["acceptance_candidate"])
        wrong_acceptance["mirror_page_count"] = 3_605
        wrong_acceptance["source_format_page_counts"] = {
            "notion_api_page": 3_605
        }
        wrong_acceptance["normalized_source_id_page_counts"] = {
            "unique": 3_605,
            "duplicate": 0,
            "invalid": 0,
        }
        mismatch = public_notion_property_backfill_plan(
            self.root,
            mirror,
            acceptance=wrong_acceptance,
        )
        self.assertFalse(mismatch["ok"])
        self.assertFalse(mismatch["acceptance_verified"])
        self.assertEqual(
            mismatch["acceptance_mismatch_codes"],
            [
                "mirror_page_count_mismatch",
                "source_format_page_count_mismatch",
                "normalized_source_id_page_count_mismatch",
            ],
        )

    def test_apply_verify_and_field_scoped_revert_preserve_later_edits(self) -> None:
        page_id, _mirror, target, plan, context = self.one_page_plan()
        self.assertEqual(plan.manifest.operation, NOTION_PROPERTY_BACKFILL_OPERATION)
        self.assertEqual(
            ExactOperationManifest.from_document(
                plan.manifest.document()
            ).document(),
            plan.manifest.document(),
        )
        evidence = plan.manifest.operation_evidence.document()
        self.assertEqual(evidence["counts"]["source_page_count"], 1)
        self.assertEqual(evidence["counts"]["mapped_page_count"], 1)
        self.assertEqual(evidence["counts"]["mapped_property_count"], 1)
        self.assertEqual(
            evidence["counts"]["mapped_populated_property_count"], 1
        )
        self.assertEqual(evidence["counts"]["effect_count"], 1)
        self.assertFalse(evidence["private_values_echoed"])
        self.assertIs(
            context.operation,
            ExactHumanApprovalOperation.notion_property_backfill,
        )
        apply_claim = self.claim(context, seed=1)
        planning_progress: list[dict[str, Any]] = []
        execution_progress = []
        execution_locators: list[dict[str, Any]] = []

        result = apply_notion_property_backfill(
            plan,
            apply_claim,
            context=context,
            planning_progress=planning_progress.append,
            progress_hook=execution_progress.append,
            execution_locator_hook=execution_locators.append,
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["common_exact_operation_manifest_used"])
        self.assertFalse(result["parallel_receipt_created"])
        self.assertTrue(result["classification_bound_by_manifest"])
        self.assertFalse(result["unmapped_treated_as_drop"])
        self.assertEqual(result["applied_property_count"], 1)
        self.assertEqual(result["applied_populated_property_count"], 1)
        self.assertEqual(planning_progress[0]["stage"], "starting")
        self.assertEqual(execution_progress[0].stage, "preflight")
        self.assertEqual(len(execution_locators), 1)
        self.assertEqual(
            execution_locators[0]["approval_id"],
            apply_claim.approval_id,
        )
        self.assertEqual(
            execution_locators[0]["execution_sha256"],
            result["execution"]["execution_sha256"],
        )
        self.assertIn("final_receipt_sha256", result["execution"])
        receipt_path = (
            self.root
            / "receipts"
            / "ops"
            / "exact-operations"
            / f"{result['execution']['execution_sha256'][7:]}.json"
        )
        durable_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(
            durable_receipt["result"]["operation_evidence"],
            evidence,
        )
        self.assertEqual(
            result["durable_operation_evidence"],
            durable_receipt["result"]["operation_evidence"],
        )
        self.assertTrue(verify_notion_property_backfill(plan, state="post")["ok"])
        after_apply = target.read_bytes()
        self.assertIn(b"source_properties:", after_apply)
        self.assertIn(b"wom-kit:notion-source-properties:start", after_apply)
        self.assertEqual(
            len(
                list(
                    (
                        self.root / "receipts" / "ops" / "exact-operations"
                    ).glob("*.json")
                )
            ),
            1,
        )
        self.assertTrue(
            (
                self.root
                / "profiles"
                / "local"
                / "exact-operations"
                / ".writer.lock"
            ).is_file()
        )
        serialized_result = json.dumps(result, ensure_ascii=False, sort_keys=True)
        for canary in (page_id, "client-canary@example.test", str(self.root)):
            self.assertNotIn(canary, serialized_result)

        later = after_apply.replace(b"title: Original", b"title: Later")
        later += b"Later unrelated body revision.\n"
        target.write_bytes(later)
        revert_context = notion_property_backfill_context(
            plan,
            reviewer_claim=REVIEWER_CLAIM,
            mode="revert",
        )
        self.assertIs(
            revert_context.operation,
            ExactHumanApprovalOperation.notion_property_backfill_revert,
        )
        self.assertNotEqual(context.plan_sha256, revert_context.plan_sha256)
        revert_claim = self.claim(revert_context, seed=2)
        revert_locators: list[dict[str, Any]] = []

        reverted = revert_notion_property_backfill(
            plan,
            revert_claim,
            context=revert_context,
            execution_locator_hook=revert_locators.append,
        )

        self.assertTrue(reverted["ok"])
        self.assertEqual(reverted["manifest_sha256"], revert_context.plan_sha256)
        self.assertEqual(
            revert_locators[0]["manifest_sha256"],
            revert_context.plan_sha256,
        )
        self.assertEqual(
            revert_locators[0]["execution_sha256"],
            reverted["execution"]["execution_sha256"],
        )
        final = target.read_bytes()
        self.assertNotIn(b"source_properties:", final)
        self.assertNotIn(b"wom-kit:notion-source-properties", final)
        self.assertIn(b"title: Later", final)
        self.assertTrue(final.endswith(b"Later unrelated body revision.\n"))
        self.assertTrue(verify_notion_property_backfill(plan, state="pre")["ok"])
        self.assertEqual(
            len(
                list(
                    (
                        self.root / "receipts" / "ops" / "exact-operations"
                    ).glob("*.json")
                )
            ),
            2,
        )

    def test_revert_blocks_source_properties_drift_without_overwriting_it(self) -> None:
        _page_id, _mirror, target, plan, context = self.one_page_plan()
        apply_notion_property_backfill(
            plan,
            self.claim(context, seed=3),
            context=context,
        )
        drifted = target.read_bytes().replace(
            b"client-canary@example.test",
            b"later-client@example.test",
        )
        target.write_bytes(drifted)
        revert_context = notion_property_backfill_context(
            plan,
            reviewer_claim=REVIEWER_CLAIM,
            mode="revert",
        )

        with self.assertRaises(NotionPropertyBackfillError) as captured:
            revert_notion_property_backfill(
                plan,
                self.claim(revert_context, seed=4),
                context=revert_context,
            )

        self.assertEqual(
            captured.exception.code,
            "notion_property_backfill_plan_changed",
        )
        self.assertEqual(target.read_bytes(), drifted)

    def test_independent_verifier_rejects_unowned_equal_source_properties(self) -> None:
        _page_id, _mirror, target, plan, context = self.one_page_plan()
        apply_notion_property_backfill(
            plan,
            self.claim(context, seed=41),
            context=context,
        )
        without_markers = b"\n".join(
            line
            for line in target.read_bytes().split(b"\n")
            if not line.startswith(b"# wom-kit:notion-source-properties:")
        )
        target.write_bytes(without_markers)

        with self.assertRaises(ExactOperationManifestError) as captured:
            verify_notion_property_backfill(plan, state="post")

        self.assertEqual(
            captured.exception.code,
            "exact_operation_independent_verify_failed",
        )

    def test_external_edit_between_snapshot_and_cas_is_never_overwritten(self) -> None:
        _page_id, _mirror, target, plan, context = self.one_page_plan()
        original_cas = (
            backfill_module.archive_services
            ._replace_regular_file_bytes_compare_and_swap
        )
        external_bytes = target.read_bytes().replace(
            b"title: Original",
            b"title: External editor",
        )

        def race(root, path, **kwargs):
            path.write_bytes(external_bytes)
            return original_cas(root, path, **kwargs)

        with mock.patch.object(
            backfill_module.archive_services,
            "_replace_regular_file_bytes_compare_and_swap",
            side_effect=race,
        ):
            with self.assertRaises(ExactOperationManifestError) as captured:
                apply_notion_property_backfill(
                    plan,
                    self.claim(context, seed=5),
                    context=context,
                )

        self.assertEqual(captured.exception.code, "exact_operation_write_failed")
        self.assertEqual(target.read_bytes(), external_bytes)
        self.assertFalse(
            list(
                (
                    self.root / "receipts" / "ops" / "exact-operations"
                ).glob("*.json")
            )
        )

    def test_record_map_exact_target_is_written_as_opaque_without_fake_semantics(self) -> None:
        page_id = "opaque-record-map-page"
        mirror = Path(self.temporary.name) / "opaque-record-map"
        mirror.mkdir()
        self.write_block_page(
            mirror,
            {
                "page_id": page_id,
                "recordMap": {
                    "block": {
                        page_id: {
                            "value": {
                                "value": {
                                    "id": page_id,
                                    "properties": {
                                        "internal-property-id": [
                                            ["Synthetic legacy value"]
                                        ]
                                    },
                                }
                            }
                        }
                    }
                },
            },
        )
        target = self.write_canonical(page_id, name="opaque-write")
        bootstrap = plan_notion_property_backfill(self.root, mirror)
        plan = plan_notion_property_backfill(
            self.root,
            mirror,
            acceptance=bootstrap.public_document()["acceptance_candidate"],
        )
        context = notion_property_backfill_context(
            plan,
            reviewer_claim=REVIEWER_CLAIM,
        )

        applied = apply_notion_property_backfill(
            plan,
            self.claim(context, seed=6),
            context=context,
        )

        self.assertTrue(applied["ok"])
        frontmatter = backfill_module._frontmatter(target.read_bytes())
        preserved = frontmatter["source_properties"]
        self.assertEqual(preserved["source_format"], "legacy_record_map")
        self.assertTrue(preserved["semantics_unavailable"])
        self.assertEqual(preserved["properties"], [])
        self.assertEqual(preserved["opaque_property_count"], 1)
        self.assertEqual(
            preserved["opaque_properties"],
            [
                {
                    "property_id": "internal-property-id",
                    "raw_json_value": [["Synthetic legacy value"]],
                }
            ],
        )
        opaque_item = preserved["opaque_properties"][0]
        self.assertNotIn("property_name", opaque_item)
        self.assertNotIn("property_type", opaque_item)

        revert_context = notion_property_backfill_context(
            plan,
            reviewer_claim=REVIEWER_CLAIM,
            mode="revert",
        )
        reverted = revert_notion_property_backfill(
            plan,
            self.claim(revert_context, seed=7),
            context=revert_context,
        )
        self.assertTrue(reverted["ok"])
        self.assertNotIn(
            "source_properties",
            backfill_module._frontmatter(target.read_bytes()),
        )

    def test_malformed_non_candidate_is_accounted_without_poisoning_all_targets(self) -> None:
        _page_id, mirror, _target, original, _context = self.one_page_plan()
        malformed_name = "old-bom-note.md"
        (self.root / "zettels" / malformed_name).write_bytes(
            b"\xef\xbb\xbfnot canonical markdown\nfacets are only prose\n"
        )

        plan = public_notion_property_backfill_plan(
            self.root,
            mirror,
            acceptance=original._acceptance,
        )

        self.assertTrue(plan["ok"])
        self.assertEqual(plan["invalid_canonical_count"], 0)
        self.assertEqual(plan["excluded_non_candidate_malformed_count"], 1)
        self.assertEqual(
            plan["excluded_non_candidate_malformed"][0]["reason_code"],
            "bom_non_candidate_no_source_page_id",
        )
        self.assertRegex(
            plan["excluded_non_candidate_malformed"][0]["opaque_ref_sha256"],
            r"^sha256:[0-9a-f]{64}$",
        )
        self.assertNotIn(malformed_name, json.dumps(plan, sort_keys=True))
        self.assertEqual(plan["category_counts"]["mapped"], 1)

    def test_unreadable_or_identity_invalid_canonical_blocks_every_join(self) -> None:
        page_id, mirror, _target, original, _context = self.one_page_plan()
        utf16 = (
            "---\n"
            "id: zet:utf16-duplicate\n"
            "archive_id: archive:test:notion-backfill\n"
            "status: canonical\n"
            "facets:\n"
            f"  source_page_id: {page_id}\n"
            "---\nUnreadable duplicate.\n"
        ).encode("utf-16")
        (self.root / "zettels" / "utf16-duplicate.md").write_bytes(utf16)

        blocked = public_notion_property_backfill_plan(
            self.root,
            mirror,
            acceptance=original._acceptance,
        )

        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["invalid_canonical_count"], 1)
        self.assertEqual(blocked["excluded_non_candidate_malformed_count"], 0)
        self.assertEqual(blocked["category_counts"]["review"], 1)
        self.assertEqual(
            blocked["review_reason_counts"],
            {"canonical_scan_incomplete": 1},
        )

        (self.root / "zettels" / "utf16-duplicate.md").unlink()
        missing_id = (
            "---\n"
            "archive_id: archive:test:notion-backfill\n"
            "status: canonical\n"
            "facets:\n"
            f"  source_page_id: {page_id}\n"
            "---\nMissing identity.\n"
        )
        (self.root / "zettels" / "missing-id.md").write_text(
            missing_id,
            encoding="utf-8",
            newline="\n",
        )
        blocked_identity = public_notion_property_backfill_plan(
            self.root,
            mirror,
            acceptance=original._acceptance,
        )
        self.assertFalse(blocked_identity["ok"])
        self.assertEqual(blocked_identity["invalid_canonical_count"], 1)
        self.assertEqual(blocked_identity["category_counts"]["review"], 1)

    def test_redacted_or_noncanonical_target_never_receives_private_properties(self) -> None:
        page_id = "redacted-source-page"
        mirror = Path(self.temporary.name) / "redacted-mirror"
        mirror.mkdir()
        self.write_block_page(
            mirror,
            _api_page(
                page_id,
                {"Email": _property("email-id", "email", "redacted@test")},
            ),
        )
        target = self.write_canonical(page_id, name="redacted")
        raw = target.read_text(encoding="utf-8").replace(
            "status: canonical",
            "status: redacted",
        )
        target.write_text(raw, encoding="utf-8", newline="\n")
        bootstrap = public_notion_property_backfill_plan(self.root, mirror)
        plan = public_notion_property_backfill_plan(
            self.root,
            mirror,
            acceptance=bootstrap["acceptance_candidate"],
        )

        self.assertFalse(plan["ok"])
        self.assertEqual(plan["category_counts"]["unmapped"], 1)
        self.assertEqual(plan["manifest_effect_count"], 0)
        self.assertNotIn(b"source_properties:", target.read_bytes())

    def test_property_schema_limit_is_a_review_boundary(self) -> None:
        page_id = "oversized-property-page"
        properties = {
            f"Property {index}": _property(
                f"property-{index}",
                "rich_text",
                [],
            )
            for index in range(backfill_module.MAX_PROPERTIES_PER_PAGE + 1)
        }
        parsed = parse_mirror_page(_json_bytes(_api_page(page_id, properties)))
        self.assertIn(
            "property_count_exceeds_schema_limit",
            parsed.review_codes,
        )
        schema = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "schemas"
                / "notion-source-properties-v0.1.schema.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            schema["properties"]["properties"]["maxItems"],
            backfill_module.MAX_PROPERTIES_PER_PAGE,
        )

        mirror = Path(self.temporary.name) / "oversized-mirror"
        mirror.mkdir()
        self.write_block_page(mirror, _api_page(page_id, properties))
        self.write_canonical(page_id, name="oversized")
        bootstrap = public_notion_property_backfill_plan(self.root, mirror)
        plan = public_notion_property_backfill_plan(
            self.root,
            mirror,
            acceptance=bootstrap["acceptance_candidate"],
        )
        self.assertFalse(plan["ok"])
        self.assertEqual(plan["category_counts"]["review"], 1)
        self.assertEqual(plan["manifest_effect_count"], 0)
        self.assertEqual(
            plan["review_reason_counts"],
            {"property_count_exceeds_schema_limit": 1},
        )

    def test_acceptance_binds_snapshot_and_property_totals(self) -> None:
        page_id, mirror, _target, original, _context = self.one_page_plan()
        mirror_file = next(mirror.glob("*.json"))
        candidate = dict(original._acceptance)
        self.assertRegex(
            candidate["mirror_snapshot_sha256"],
            r"^sha256:[0-9a-f]{64}$",
        )
        self.assertEqual(candidate["source_property_count"], 1)
        self.assertEqual(candidate["populated_property_count"], 1)

        same_count_substitution = _api_page(
            page_id,
            {
                "Client email": _property(
                    "email-id",
                    "email",
                    "different-private-value@example.test",
                )
            },
        )
        mirror_file.write_bytes(_json_bytes(same_count_substitution))
        substituted = public_notion_property_backfill_plan(
            self.root,
            mirror,
            acceptance=candidate,
        )
        self.assertFalse(substituted["acceptance_verified"])
        self.assertEqual(
            substituted["acceptance_mismatch_codes"],
            ["mirror_snapshot_mismatch"],
        )
        self.assertNotIn(
            "different-private-value@example.test",
            json.dumps(substituted, sort_keys=True),
        )

        mirror_file.write_bytes(_json_bytes(_api_page(page_id, {})))
        emptied = public_notion_property_backfill_plan(
            self.root,
            mirror,
            acceptance=candidate,
        )
        self.assertFalse(emptied["acceptance_verified"])
        self.assertEqual(
            emptied["acceptance_mismatch_codes"],
            [
                "mirror_snapshot_mismatch",
                "source_property_count_mismatch",
                "populated_property_count_mismatch",
                "populated_property_type_count_mismatch",
            ],
        )

    def test_linked_inputs_and_incomplete_walk_fail_closed(self) -> None:
        page_id, mirror, _target, original, _context = self.one_page_plan()
        temporary = Path(self.temporary.name)
        mirror_link = temporary / "mirror-link"
        archive_link = temporary / "archive-link"
        try:
            mirror_link.symlink_to(mirror, target_is_directory=True)
            archive_link.symlink_to(self.root, target_is_directory=True)
        except OSError:
            linked_inputs_available = False
        else:
            linked_inputs_available = True

        if linked_inputs_available:
            with self.assertRaises(NotionPropertyBackfillError):
                public_notion_property_backfill_plan(
                    self.root,
                    mirror_link,
                    acceptance=original._acceptance,
                )
            with self.assertRaises(NotionPropertyBackfillError):
                public_notion_property_backfill_plan(
                    archive_link,
                    mirror,
                    acceptance=original._acceptance,
                )

        real_lstat = backfill_module.os.lstat
        real_link_check = backfill_module._is_link_or_reparse
        zettels_info = real_lstat(self.root / "zettels")
        zettels_path = (self.root / "zettels").absolute()
        reparse_info = mock.Mock()
        reparse_info.st_mode = zettels_info.st_mode

        def reparse_zettels(path):
            info = real_lstat(path)
            if Path(path).absolute() == zettels_path:
                return reparse_info
            return info

        def forced_link_check(info):
            return info is reparse_info or real_link_check(info)

        with (
            mock.patch.object(
                backfill_module.os,
                "lstat",
                side_effect=reparse_zettels,
            ),
            mock.patch.object(
                backfill_module,
                "_is_link_or_reparse",
                side_effect=forced_link_check,
            ),
        ):
            _targets, _count, invalid_root, _excluded = (
                backfill_module._scan_canonical(
                    self.root,
                    "archive:test:notion-backfill",
                    progress=backfill_module._PlanningProgressPublisher(None),
                )
            )
        self.assertEqual(invalid_root, 1)

        with mock.patch.object(backfill_module.os, "walk") as mocked_walk:
            def incomplete_walk(*_args, **kwargs):
                kwargs["onerror"](PermissionError("private traversal detail"))
                return iter(())

            mocked_walk.side_effect = incomplete_walk
            files, invalid = backfill_module._discover_canonical_files(
                self.root,
                self.root / "zettels",
            )
        self.assertEqual(files, ())
        self.assertEqual(invalid, 1)

    def test_source_page_join_drift_blocks_before_field_write(self) -> None:
        _page_id, _mirror, target, plan, context = self.one_page_plan()
        changed = target.read_text(encoding="utf-8").replace(
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
        )
        target.write_text(changed, encoding="utf-8", newline="\n")

        with self.assertRaises(NotionPropertyBackfillError) as captured:
            apply_notion_property_backfill(
                plan,
                self.claim(context, seed=11),
                context=context,
            )
        self.assertEqual(
            captured.exception.code,
            "notion_property_backfill_plan_changed",
        )
        self.assertNotIn(b"source_properties:", target.read_bytes())

    def test_each_mirror_and_canonical_file_is_read_once_per_plan(self) -> None:
        _page_id, mirror, target, original, _context = self.one_page_plan()
        original_read = backfill_module._read_regular
        reads: dict[Path, int] = {}
        lock = threading.Lock()

        def tracked(path: Path, *, max_bytes: int) -> bytes:
            resolved = path.resolve()
            with lock:
                reads[resolved] = reads.get(resolved, 0) + 1
            return original_read(path, max_bytes=max_bytes)

        with mock.patch.object(
            backfill_module,
            "_read_regular",
            side_effect=tracked,
        ):
            plan_notion_property_backfill(
                self.root,
                mirror,
                acceptance=original._acceptance,
            )

        mirror_file = next(mirror.glob("*.json")).resolve()
        self.assertEqual(reads[mirror_file], 1)
        self.assertEqual(reads[target.resolve()], 1)
        self.assertTrue(all(count == 1 for count in reads.values()))

    def test_resume_guard_reauthenticates_claim_and_derives_exact_execution(self) -> None:
        _page_id, mirror, target, plan, context = self.one_page_plan()
        original_manifest_document = plan.manifest.document()
        claim = self.claim(context, seed=8)
        authority = backfill_module._assert_approved_manifest(
            plan,
            claim,
            context,
            mode="apply",
        )
        execution_sha256 = exact_operation_execution_sha256(
            plan.manifest,
            approval_authority=authority,
        )
        approval_id = claim.approval_id
        original_write = backfill_module._NotionPropertyWriter.write_field

        def write_then_crash(writer, *args, **kwargs):
            original_write(writer, *args, **kwargs)
            raise RuntimeError("synthetic write-before-field-receipt crash")

        with mock.patch.object(
            backfill_module._NotionPropertyWriter,
            "write_field",
            new=write_then_crash,
        ):
            with self.assertRaises(ExactOperationManifestError) as interrupted:
                apply_notion_property_backfill(plan, claim, context=context)
        self.assertEqual(interrupted.exception.code, "exact_operation_write_failed")
        self.assertIn(b"source_properties:", target.read_bytes())
        claim.close()

        # Simulate a new CLI process: reconstruct only from the exact mirror,
        # reviewed acceptance, and current partially-written archive.  The
        # owned managed-equal field normalizes back to its original mapped
        # effect, so no in-memory manifest object is needed for resume.
        restarted_plan = plan_notion_property_backfill(
            self.root,
            mirror,
            acceptance=plan._acceptance,
        )
        self.assertIsNot(restarted_plan, plan)
        self.assertEqual(
            restarted_plan.category_counts,
            {"mapped": 0, "already_equal": 1, "unmapped": 0, "review": 0},
        )
        self.assertEqual(
            restarted_plan.manifest.document(),
            original_manifest_document,
        )
        self.assertEqual(
            ExactOperationManifest.from_document(
                restarted_plan.manifest.document()
            ).document(),
            original_manifest_document,
        )
        plan = restarted_plan

        wrong_execution = "sha256:" + "f" * 64
        self.assertNotEqual(wrong_execution, execution_sha256)
        with self.assertRaises(ExactHumanApprovalWorkflowError) as wrong:
            backfill_module._resume_notion_property_backfill_approved_core(
                plan,
                reviewer_claim=REVIEWER_CLAIM,
                approval_id=approval_id,
                execution_sha256=wrong_execution,
                mode="apply",
                key_provider=_KeyProvider(),
            )
        self.assertEqual(
            wrong.exception.code,
            "exact_human_approval_resume_checkpoint_invalid",
        )

        resumed = backfill_module._resume_notion_property_backfill_approved_core(
            plan,
            reviewer_claim=REVIEWER_CLAIM,
            approval_id=approval_id,
            execution_sha256=execution_sha256,
            mode="apply",
            key_provider=_KeyProvider(),
        )

        self.assertTrue(resumed["ok"])
        self.assertEqual(
            resumed["exact_human_approval"]["approval_id"], approval_id
        )
        self.assertEqual(
            resumed["exact_human_approval"]["status"], "succeeded"
        )
        self.assertEqual(resumed["applied_property_count"], 1)
        self.assertEqual(resumed["applied_populated_property_count"], 1)
        self.assertTrue(verify_notion_property_backfill(plan, state="post")["ok"])
        self.assertEqual(
            len(
                list(
                    (
                        self.root / "receipts" / "ops" / "exact-operations"
                    ).glob("*.json")
                )
            ),
            1,
        )

    def test_interrupted_revert_resumes_from_its_direction_bound_locator(self) -> None:
        _page_id, mirror, target, plan, apply_context = self.one_page_plan()
        original_apply_manifest = plan.manifest.document()
        original_revert_manifest = (
            backfill_module._notion_property_operation_manifest(
                plan,
                mode="revert",
            ).document()
        )
        apply_notion_property_backfill(
            plan,
            self.claim(apply_context, seed=81),
            context=apply_context,
        )
        plan = plan_notion_property_backfill(
            self.root,
            mirror,
            acceptance=plan._acceptance,
        )
        self.assertEqual(plan.manifest.document(), original_apply_manifest)
        self.assertEqual(
            backfill_module._notion_property_operation_manifest(
                plan,
                mode="revert",
            ).document(),
            original_revert_manifest,
        )
        revert_context = notion_property_backfill_context(
            plan,
            reviewer_claim=REVIEWER_CLAIM,
            mode="revert",
        )
        revert_claim = self.claim(revert_context, seed=82)
        locators: list[dict[str, Any]] = []
        original_write = backfill_module._NotionPropertyWriter.write_field

        def write_then_crash(writer, *args, **kwargs):
            original_write(writer, *args, **kwargs)
            raise RuntimeError("synthetic revert write-before-receipt crash")

        with mock.patch.object(
            backfill_module._NotionPropertyWriter,
            "write_field",
            new=write_then_crash,
        ):
            with self.assertRaises(ExactOperationManifestError):
                revert_notion_property_backfill(
                    plan,
                    revert_claim,
                    context=revert_context,
                    execution_locator_hook=locators.append,
                )
        self.assertEqual(len(locators), 1)
        locator = locators[0]
        self.assertEqual(locator["manifest_sha256"], revert_context.plan_sha256)
        self.assertNotIn(b"source_properties:", target.read_bytes())
        revert_claim.close()

        plan = plan_notion_property_backfill(
            self.root,
            mirror,
            acceptance=plan._acceptance,
        )
        self.assertEqual(plan.manifest.document(), original_apply_manifest)
        self.assertEqual(
            backfill_module._notion_property_operation_manifest(
                plan,
                mode="revert",
            ).document(),
            original_revert_manifest,
        )

        resumed = backfill_module._resume_notion_property_backfill_approved_core(
            plan,
            reviewer_claim=REVIEWER_CLAIM,
            approval_id=locator["approval_id"],
            execution_sha256=locator["execution_sha256"],
            mode="revert",
            key_provider=_KeyProvider(),
        )

        self.assertTrue(resumed["ok"])
        self.assertEqual(
            resumed["execution"]["execution_sha256"],
            locator["execution_sha256"],
        )
        self.assertEqual(
            resumed["manifest_sha256"],
            revert_context.plan_sha256,
        )

    def test_revert_wrapper_checks_post_state_before_native_approval(self) -> None:
        _page_id, _mirror, _target, plan, _context = self.one_page_plan()
        with mock.patch.object(
            backfill_module,
            "_execute_exact_human_approved_write",
        ) as native_boundary:
            with self.assertRaises(NotionPropertyBackfillError) as captured:
                backfill_module.execute_notion_property_backfill_revert(
                    plan,
                    reviewer_claim=REVIEWER_CLAIM,
                )

        self.assertEqual(
            captured.exception.code,
            "notion_property_backfill_revert_no_writes",
        )
        native_boundary.assert_not_called()

    def test_locator_hook_cannot_change_canonical_join_before_write(self) -> None:
        page_id, _mirror, target, plan, context = self.one_page_plan()

        def add_duplicate(_locator):
            self.write_canonical(page_id, name="late-duplicate")

        with self.assertRaises(NotionPropertyBackfillError) as captured:
            apply_notion_property_backfill(
                plan,
                self.claim(context, seed=83),
                context=context,
                execution_locator_hook=add_duplicate,
            )

        self.assertEqual(
            captured.exception.code,
            "notion_property_backfill_plan_changed",
        )
        self.assertNotIn(b"source_properties:", target.read_bytes())

    def test_planner_rejects_replacement_over_canonical_size_limit(self) -> None:
        _page_id, mirror, _target, original, _context = self.one_page_plan()

        class OversizedCandidate:
            def __len__(self) -> int:
                return backfill_module.MAX_CANONICAL_FILE_BYTES + 1

        with mock.patch.object(
            backfill_module,
            "_insert_managed_field",
            return_value=OversizedCandidate(),
        ):
            blocked = public_notion_property_backfill_plan(
                self.root,
                mirror,
                acceptance=original._acceptance,
            )

        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["category_counts"]["review"], 1)
        self.assertEqual(
            blocked["review_reason_counts"],
            {"canonical_size_limit_exceeded": 1},
        )
        self.assertEqual(blocked["planned_write_count"], 0)

    def test_acceptance_candidate_is_private_create_only_and_byte_exact(self) -> None:
        (self.root / ".gitignore").write_text(
            "profiles/local/\n",
            encoding="utf-8",
            newline="\n",
        )
        _page_id, _mirror, _target, plan, _context = self.one_page_plan()
        relative = (
            "profiles/local/notion-property-backfill/"
            "synthetic-candidate.json"
        )
        result = (
            backfill_module.persist_notion_property_backfill_acceptance_candidate(
                plan,
                relative,
            )
        )
        output = self.root.joinpath(*relative.split("/"))
        raw = output.read_bytes()

        self.assertEqual(
            result["acceptance_document_sha256"],
            plan.acceptance_document_sha256,
        )
        self.assertEqual(raw, backfill_module._canonical_bytes(plan._acceptance))
        self.assertEqual(os.lstat(output).st_nlink, 1)
        self.assertTrue(result["namespace_durability_confirmed"])
        self.assertTrue(result["temporary_cleanup_complete"])
        self.assertEqual(
            backfill_module.load_notion_property_backfill_acceptance(output),
            plan._acceptance,
        )
        with self.assertRaises(NotionPropertyBackfillError) as duplicate:
            backfill_module.persist_notion_property_backfill_acceptance_candidate(
                plan,
                relative,
            )
        self.assertEqual(
            duplicate.exception.code,
            "notion_property_backfill_acceptance_output_exists",
        )
        with self.assertRaises(NotionPropertyBackfillError) as traversal:
            backfill_module.persist_notion_property_backfill_acceptance_candidate(
                plan,
                "../outside.json",
            )
        self.assertEqual(
            traversal.exception.code,
            "notion_property_backfill_path_unsafe",
        )

        outside = Path(self.temporary.name) / "acceptance-outside"
        outside.mkdir()
        linked = output.parent / "linked"
        try:
            linked.symlink_to(outside, target_is_directory=True)
        except (NotImplementedError, OSError):
            pass
        else:
            with self.assertRaises(NotionPropertyBackfillError):
                backfill_module.persist_notion_property_backfill_acceptance_candidate(
                    plan,
                    (
                        "profiles/local/notion-property-backfill/linked/"
                        "escaped.json"
                    ),
                )
            self.assertFalse((outside / "escaped.json").exists())

        (self.root / ".gitignore").write_text(
            "profiles/local/\n!profiles/local/reincluded.json\n",
            encoding="utf-8",
            newline="\n",
        )
        with self.assertRaises(NotionPropertyBackfillError) as exposed:
            backfill_module.persist_notion_property_backfill_acceptance_candidate(
                plan,
                (
                    "profiles/local/notion-property-backfill/"
                    "another-candidate.json"
                ),
            )
        self.assertEqual(
            exposed.exception.code,
            "notion_property_backfill_acceptance_output_not_private",
        )

        noncanonical = Path(self.temporary.name) / "noncanonical.json"
        noncanonical.write_bytes(raw.rstrip(b"\n"))
        with self.assertRaises(NotionPropertyBackfillError) as rejected:
            backfill_module.load_notion_property_backfill_acceptance(
                noncanonical
            )
        self.assertEqual(
            rejected.exception.code,
            "notion_property_backfill_plan_invalid",
        )

    def test_missing_or_wrong_acceptance_cannot_be_approved(self) -> None:
        page_id = "acceptance-page"
        mirror = Path(self.temporary.name) / "acceptance-mirror"
        mirror.mkdir()
        self.write_block_page(
            mirror,
            _api_page(
                page_id,
                {"Email": _property("email-id", "email", "x@example.test")},
            ),
        )
        self.write_canonical(page_id, name="acceptance")

        missing = plan_notion_property_backfill(self.root, mirror)
        self.assertFalse(missing.approveable)
        self.assertEqual(
            missing.acceptance_mismatch_codes,
            ("acceptance_profile_required",),
        )
        with self.assertRaises(NotionPropertyBackfillError) as captured:
            notion_property_backfill_context(
                missing,
                reviewer_claim=REVIEWER_CLAIM,
            )
        self.assertEqual(captured.exception.code, "notion_property_backfill_no_writes")

        wrong_acceptance = missing.public_document()["acceptance_candidate"]
        wrong_acceptance["populated_page_counts_by_property_type"] = {
            "email": 50
        }
        wrong = plan_notion_property_backfill(
            self.root,
            mirror,
            acceptance=wrong_acceptance,
        )
        self.assertFalse(wrong.approveable)
        self.assertEqual(
            wrong.acceptance_mismatch_codes,
            ("populated_property_type_count_mismatch",),
        )

    def test_schema_and_public_fixture_contain_no_real_archive_values(self) -> None:
        schema_path = (
            Path(__file__).resolve().parents[1]
            / "schemas"
            / "notion-source-properties-v0.1.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(schema["$id"], "notion-source-properties-v0.1.schema.json")
        self.assertEqual(
            schema["properties"]["schema_version"]["const"],
            SOURCE_PROPERTIES_SCHEMA_VERSION,
        )
        Draft202012Validator.check_schema(schema)
        source_document = parse_mirror_page(
            _json_bytes(
                _api_page(
                    "schema-page",
                    {
                        "Email": _property(
                            "email-id",
                            "email",
                            "synthetic@example.test",
                        )
                    },
                )
            )
        ).source_properties()
        self.assertEqual(
            list(Draft202012Validator(schema).iter_errors(source_document)),
            [],
        )
        acceptance_schema = json.loads(
            (
                schema_path.parent
                / "notion-property-backfill-acceptance-v0.1.schema.json"
            ).read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(acceptance_schema)
        _page_id, _mirror, _target, plan, _context = self.one_page_plan()
        self.assertEqual(
            list(
                Draft202012Validator(acceptance_schema).iter_errors(
                    plan._acceptance
                )
            ),
            [],
        )
        serialized = json.dumps(schema, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("mylifeisbusy", serialized)
        private_project_marker = "zettel-kasten-" + bytes(
            [98, 97, 115, 111, 111, 110]
        ).decode("ascii")
        self.assertNotIn(private_project_marker, serialized)


if __name__ == "__main__":
    unittest.main()
