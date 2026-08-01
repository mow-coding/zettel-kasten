from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator, FormatChecker

from wom_kit import private_objet_metadata as contract


KIT_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_SCHEMA_PATH = (
    KIT_ROOT / "schemas" / "private-objet-source-metadata-v0.1.schema.json"
)
PROJECTION_SCHEMA_PATH = (
    KIT_ROOT / "schemas" / "objet-safe-label-projection-v0.1.schema.json"
)
OBJECT_ID = "sha256:" + ("0" * 64)
SOURCE_DIGEST = "sha256:" + ("1" * 64)
OBSERVATION_DIGEST = "sha256:" + ("2" * 64)
REVIEW_DIGEST = "sha256:" + ("3" * 64)


def _digest(index: int) -> str:
    return f"sha256:{index:064x}"


def _checker() -> FormatChecker:
    checker = FormatChecker()

    @checker.checks("date-time")
    def fixed_rfc3339(value: object) -> bool:
        return contract.is_valid_private_metadata_rfc3339(value)

    return checker


def _load_schema(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


PRIVATE_SCHEMA = _load_schema(PRIVATE_SCHEMA_PATH)
PROJECTION_SCHEMA = _load_schema(PROJECTION_SCHEMA_PATH)
PRIVATE_VALIDATOR = Draft202012Validator(PRIVATE_SCHEMA, format_checker=_checker())
PROJECTION_VALIDATOR = Draft202012Validator(
    PROJECTION_SCHEMA,
    format_checker=_checker(),
)


def _draft_result(
    validator: Draft202012Validator,
    instance: object,
) -> dict[str, object]:
    if validator.is_valid(instance):
        return {"accepted": True, "issue_codes": []}
    return {
        "accepted": False,
        "issue_codes": ["draft202012_instance_rejected"],
    }


def _base_record() -> dict[str, object]:
    names_result = contract.normalize_private_filename(
        "example.hwpx",
        "literal_unicode",
    )
    return {
        "schema": contract.PRIVATE_METADATA_SCHEMA,
        "privacy_class": "private_archive",
        "object_id": OBJECT_ID,
        "names": names_result["names"],
        "media_type": {
            "value": None,
            "basis": "unknown",
            "registered_status": "not_checked",
            "extension_agreement": "unknown",
            "extension_comparison_evidence_sha256": None,
            "registry_evidence": None,
        },
        "size_bytes": None,
        "size_bytes_basis": "unknown",
        "source_provenance": {
            "source_system": "synthetic-fixture",
            "source_record_id": None,
            "source_attachment_id": "attachment-1",
            "source_snapshot_sha256": SOURCE_DIGEST,
            "observation_evidence_sha256": OBSERVATION_DIGEST,
            "evidence_kind": "source_attachment_metadata",
            "captured_at": None,
        },
        "label_candidates": [],
        "normalization_profile": {
            "id": contract.NORMALIZATION_PROFILE,
            "unicode_version": "17.0.0",
            "confusables_data_sha256": None,
            "confusable_status": "not_checked",
        },
    }


def _privacy(private_filename_exposed: bool = False) -> dict[str, bool]:
    return {
        "private_filename_exposed": private_filename_exposed,
        "source_identifier_exposed": False,
        "local_path_exposed": False,
        "provider_locator_exposed": False,
        "secret_value_exposed": False,
    }


def _candidate(
    kind: str,
    value: str,
    *,
    review_status: str = "unreviewed",
    review_evidence_sha256: str | None = None,
    evidence_sha256: str = SOURCE_DIGEST,
) -> dict[str, object]:
    return {
        "kind": kind,
        "value": value,
        "privacy_class": "private_archive",
        "evidence_sha256": evidence_sha256,
        "review_status": review_status,
        "review_evidence_sha256": review_evidence_sha256,
    }


def _projection_corpus() -> tuple[dict[str, object], ...]:
    return (
        {
            "schema": contract.SAFE_LABEL_SCHEMA,
            "object_id": OBJECT_ID,
            "audience": "private_archive",
            "status": "selected",
            "selected_label": "example.hwpx",
            "selected_kind": "original_filename",
            "alternative_count": 0,
            "ambiguity": {"state": "none"},
            "reason_codes": [],
            "privacy": _privacy(True),
        },
        {
            "schema": contract.SAFE_LABEL_SCHEMA,
            "object_id": OBJECT_ID,
            "audience": "restricted",
            "status": "ambiguous",
            "selected_label": None,
            "selected_kind": None,
            "alternative_count": 2,
            "ambiguity": {"state": "multiple_labels_for_object"},
            "reason_codes": ["multiple_labels_for_object"],
            "privacy": _privacy(),
        },
        {
            "schema": contract.SAFE_LABEL_SCHEMA,
            "object_id": OBJECT_ID,
            "audience": "private_archive",
            "status": "blocked",
            "selected_label": None,
            "selected_kind": None,
            "alternative_count": 0,
            "ambiguity": {"state": "none"},
            "reason_codes": ["no_eligible_label_candidate"],
            "privacy": _privacy(),
        },
        {
            "schema": contract.SAFE_LABEL_SCHEMA,
            "object_id": OBJECT_ID,
            "audience": "public_generic",
            "status": "generic_only",
            "generic_label": {"generic_family": "document"},
            "alternative_count": 0,
            "reason_codes": [],
            "privacy": _privacy(),
        },
        {
            "schema": contract.SAFE_LABEL_SCHEMA,
            "object_id": OBJECT_ID,
            "audience": "public_generic",
            "status": "blocked",
            "generic_label": None,
            "alternative_count": 0,
            "reason_codes": ["generic_family_unavailable"],
            "privacy": _privacy(),
        },
    )


def _iter_mapping_paths(
    value: object,
    path: tuple[object, ...] = (),
) -> list[tuple[object, ...]]:
    paths: list[tuple[object, ...]] = []
    if type(value) is dict:
        paths.append(path)
        for key, item in value.items():
            paths.extend(_iter_mapping_paths(item, path + (key,)))
    elif type(value) is list:
        for index, item in enumerate(value):
            paths.extend(_iter_mapping_paths(item, path + (index,)))
    return paths


def _mapping_at_path(
    value: object,
    path: tuple[object, ...],
) -> dict[str, object]:
    current = value
    for component in path:
        current = current[component]  # type: ignore[index]
    if type(current) is not dict:
        raise AssertionError("expected mapping path")
    return current


def _candidate_value(record: dict[str, object], kind: str) -> str:
    names = record["names"]
    values = {
        "human_reviewed_label": "Reviewed document",
        "original_filename": names["original_filename"],
        "decoded_filename": names["decoded_filename"],
        "normalized_filename_nfc": names["normalized_filename_nfc"],
        "extension_generic": "document",
        "media_type_generic": "document",
        "object_id_fallback": record["object_id"],
    }
    value = values[kind]
    if type(value) is not str:
        raise AssertionError("candidate fixture value must be a string")
    return value


def _record_with_encoded_names() -> dict[str, object]:
    record = _base_record()
    record["names"] = contract.normalize_private_filename(
        "example%2Ehwpx",
        "utf8_percent_encoded_component",
    )["names"]
    return record


class PrivateObjetMetadataSchemaTests(unittest.TestCase):
    def test_schemas_pass_draft_2020_12_meta_schema(self) -> None:
        Draft202012Validator.check_schema(PRIVATE_SCHEMA)
        Draft202012Validator.check_schema(PROJECTION_SCHEMA)

    def test_every_object_schema_is_closed_and_requires_every_property(self) -> None:
        def inspect(node: object) -> None:
            if type(node) is dict:
                if node.get("type") == "object":
                    self.assertIs(
                        node.get("additionalProperties"),
                        False,
                        "object schema must be closed",
                    )
                    properties = node.get("properties")
                    required = node.get("required")
                    self.assertEqual(
                        set(required),
                        set(properties),
                        "object schema must require every declared property",
                    )
                for value in node.values():
                    inspect(value)
            elif type(node) is list:
                for value in node:
                    inspect(value)

        inspect(PRIVATE_SCHEMA)
        inspect(PROJECTION_SCHEMA)

    def test_every_required_field_and_nested_extra_field_is_rejected(self) -> None:
        record = _base_record()
        record["label_candidates"] = [
            _candidate("original_filename", "example.hwpx")
        ]
        self.assertTrue(PRIVATE_VALIDATOR.is_valid(record))
        self.assertTrue(
            contract.validate_private_metadata_record(record)["accepted"]
        )
        for path in _iter_mapping_paths(record):
            original_mapping = _mapping_at_path(record, path)
            for key in tuple(original_mapping):
                missing = deepcopy(record)
                del _mapping_at_path(missing, path)[key]
                self.assertFalse(
                    PRIVATE_VALIDATOR.is_valid(missing),
                    "missing required field was accepted by Draft 2020-12",
                )
                self.assertFalse(
                    contract.validate_private_metadata_record(missing)["accepted"],
                    "missing required field was accepted by runtime",
                )
            extra = deepcopy(record)
            _mapping_at_path(extra, path)["unexpected_contract_field"] = False
            self.assertFalse(
                PRIVATE_VALIDATOR.is_valid(extra),
                "nested extra field was accepted by Draft 2020-12",
            )
            self.assertFalse(
                contract.validate_private_metadata_record(extra)["accepted"],
                "nested extra field was accepted by runtime",
            )

        for projection in _projection_corpus():
            for path in _iter_mapping_paths(projection):
                original_mapping = _mapping_at_path(projection, path)
                for key in tuple(original_mapping):
                    missing = deepcopy(projection)
                    del _mapping_at_path(missing, path)[key]
                    self.assertFalse(
                        PROJECTION_VALIDATOR.is_valid(missing),
                        "missing projection field was accepted by Draft 2020-12",
                    )
                    self.assertFalse(
                        contract.validate_objet_safe_label_projection(missing)[
                            "accepted"
                        ],
                        "missing projection field was accepted by runtime",
                    )
                extra = deepcopy(projection)
                _mapping_at_path(extra, path)[
                    "unexpected_contract_field"
                ] = False
                self.assertFalse(
                    PROJECTION_VALIDATOR.is_valid(extra),
                    "nested projection extra field was accepted by Draft 2020-12",
                )
                self.assertFalse(
                    contract.validate_objet_safe_label_projection(extra)[
                        "accepted"
                    ],
                    "nested projection extra field was accepted by runtime",
                )

    def test_literal_bound_keywords_match_the_v0_1_contract(self) -> None:
        private_defs = PRIVATE_SCHEMA["$defs"]
        projection_defs = PROJECTION_SCHEMA["$defs"]
        self.assertEqual(private_defs["sha256"]["maxLength"], 71)
        self.assertEqual(private_defs["scalar512"]["maxLength"], 512)
        self.assertEqual(private_defs["nonEmptyScalar512"]["maxLength"], 512)
        self.assertEqual(private_defs["opaqueSourceId"]["maxLength"], 256)
        self.assertEqual(
            PRIVATE_SCHEMA["properties"]["label_candidates"]["maxItems"],
            64,
        )
        self.assertEqual(
            private_defs["names"]["properties"]["reason_codes"]["maxItems"],
            16,
        )
        self.assertEqual(
            private_defs["names"]["properties"]["extension_ascii_lower"][
                "oneOf"
            ][1]["maxLength"],
            512,
        )
        self.assertEqual(
            private_defs["mediaType"]["properties"]["value"]["oneOf"][1][
                "maxLength"
            ],
            127,
        )
        self.assertEqual(
            private_defs["sourceProvenance"]["properties"]["source_system"][
                "maxLength"
            ],
            64,
        )
        self.assertEqual(
            private_defs["sourceProvenance"]["properties"]["captured_at"][
                "oneOf"
            ][1]["maxLength"],
            64,
        )
        self.assertEqual(projection_defs["selectedLabel"]["maxLength"], 512)
        self.assertEqual(
            projection_defs["privateProjection"]["properties"][
                "alternative_count"
            ]["maximum"],
            256,
        )
        self.assertEqual(
            projection_defs["privateProjection"]["properties"]["reason_codes"][
                "maxItems"
            ],
            16,
        )
        self.assertEqual(
            projection_defs["publicGenericProjection"]["properties"][
                "reason_codes"
            ]["maxItems"],
            16,
        )

    def test_positive_record_has_schema_runtime_parity(self) -> None:
        record = _base_record()
        self.assertTrue(PRIVATE_VALIDATOR.is_valid(record))
        self.assertEqual(
            contract.validate_private_metadata_record(record),
            {"accepted": True, "issue_codes": []},
        )

    def test_entire_runtime_accepted_positive_corpus_is_draft_valid(self) -> None:
        records = [_base_record(), _record_with_encoded_names()]
        for length in (1, 511, 512):
            record = _base_record()
            record["names"] = contract.normalize_private_filename(
                "x" * length,
                "literal_unicode",
            )["names"]
            records.append(record)
        for evidence_kind, source_record_id, source_attachment_id in (
            ("source_record_field", "record-1", None),
            ("source_attachment_metadata", None, "attachment-1"),
            ("source_attachment_metadata", "record-1", "attachment-1"),
            ("source_snapshot_extract", None, None),
            ("source_snapshot_extract", "record-1", None),
            ("source_snapshot_extract", None, "attachment-1"),
            ("source_snapshot_extract", "record-1", "attachment-1"),
        ):
            record = _base_record()
            provenance = record["source_provenance"]
            provenance["evidence_kind"] = evidence_kind
            provenance["source_record_id"] = source_record_id
            provenance["source_attachment_id"] = source_attachment_id
            records.append(record)
        for kind in (
            "human_reviewed_label",
            "original_filename",
            "decoded_filename",
            "normalized_filename_nfc",
            "extension_generic",
            "media_type_generic",
            "object_id_fallback",
        ):
            statuses = (
                ("accepted",)
                if kind == "human_reviewed_label"
                else ("unreviewed", "accepted", "rejected")
            )
            for review_status in statuses:
                record = _record_with_encoded_names()
                record["label_candidates"] = [
                    _candidate(
                        kind,
                        _candidate_value(record, kind),
                        review_status=review_status,
                        review_evidence_sha256=(
                            None
                            if review_status == "unreviewed"
                            else REVIEW_DIGEST
                        ),
                    )
                ]
                records.append(record)
        max_candidates = _base_record()
        max_candidates["label_candidates"] = [
            _candidate(
                "extension_generic",
                "document",
                evidence_sha256=_digest(index + 16),
            )
            for index in range(64)
        ]
        records.append(max_candidates)

        for record in records:
            runtime = contract.validate_private_metadata_record(record)
            self.assertTrue(
                runtime["accepted"],
                "positive runtime corpus unexpectedly failed",
            )
            self.assertTrue(
                PRIVATE_VALIDATOR.is_valid(record),
                "runtime-accepted record was rejected by Draft 2020-12",
            )

        for projection in _projection_corpus():
            runtime = contract.validate_objet_safe_label_projection(projection)
            self.assertTrue(
                runtime["accepted"],
                "positive projection runtime corpus unexpectedly failed",
            )
            self.assertTrue(
                PROJECTION_VALIDATOR.is_valid(projection),
                "runtime-accepted projection was rejected by Draft 2020-12",
            )

    def test_private_schema_rejects_extra_field_and_bad_hashes(self) -> None:
        extra = _base_record()
        extra["unexpected"] = True
        uppercase = _base_record()
        uppercase["object_id"] = "sha256:" + ("A" * 64)
        short = _base_record()
        short["source_provenance"]["source_snapshot_sha256"] = "sha256:1"
        for record in (extra, uppercase, short):
            self.assertFalse(PRIVATE_VALIDATOR.is_valid(record))
            self.assertFalse(
                contract.validate_private_metadata_record(record)["accepted"]
            )

    def test_size_basis_allows_only_exact_iff_pairs_and_rejects_boolean(self) -> None:
        accepted_pairs = (
            (None, "unknown"),
            (0, "source_observed"),
            (10, "source_observed"),
        )
        for size, basis in accepted_pairs:
            record = _base_record()
            record["size_bytes"] = size
            record["size_bytes_basis"] = basis
            self.assertTrue(PRIVATE_VALIDATOR.is_valid(record))
            self.assertTrue(
                contract.validate_private_metadata_record(record)["accepted"]
            )
        rejected_pairs = (
            (True, "source_observed"),
            (1, "unknown"),
            (None, "source_observed"),
            (1, "object_manifest"),
            (1, "byte_inspected"),
        )
        for size, basis in rejected_pairs:
            record = _base_record()
            record["size_bytes"] = size
            record["size_bytes_basis"] = basis
            self.assertFalse(PRIVATE_VALIDATOR.is_valid(record))
            self.assertFalse(
                contract.validate_private_metadata_record(record)["accepted"]
            )

    def test_media_type_basis_and_evidence_axes_are_closed(self) -> None:
        declared = _base_record()
        declared["media_type"]["value"] = "application/pdf"
        declared["media_type"]["basis"] = "source_declared"
        self.assertTrue(PRIVATE_VALIDATOR.is_valid(declared))
        self.assertTrue(
            contract.validate_private_metadata_record(declared)["accepted"]
        )
        invalid_media = (
            ("application/pdf", "unknown"),
            (None, "source_declared"),
            ("Application/PDF", "source_declared"),
            ("application/pdf; charset=utf-8", "source_declared"),
        )
        for value, basis in invalid_media:
            record = _base_record()
            record["media_type"]["value"] = value
            record["media_type"]["basis"] = basis
            self.assertFalse(PRIVATE_VALIDATOR.is_valid(record))
            self.assertFalse(
                contract.validate_private_metadata_record(record)["accepted"]
            )
        for field, value in (
            ("registered_status", "registered"),
            ("registry_evidence", SOURCE_DIGEST),
            ("extension_agreement", "agrees"),
            ("extension_comparison_evidence_sha256", SOURCE_DIGEST),
        ):
            record = _base_record()
            record["media_type"][field] = value
            self.assertFalse(PRIVATE_VALIDATOR.is_valid(record))
            self.assertFalse(
                contract.validate_private_metadata_record(record)["accepted"]
            )

    def test_evidence_kind_id_conditionals_have_two_sided_parity(self) -> None:
        source_record = _base_record()
        provenance = source_record["source_provenance"]
        provenance["evidence_kind"] = "source_record_field"
        provenance["source_record_id"] = "record-1"
        provenance["source_attachment_id"] = None
        self.assertTrue(PRIVATE_VALIDATOR.is_valid(source_record))
        self.assertTrue(
            contract.validate_private_metadata_record(source_record)["accepted"]
        )
        invalid = deepcopy(source_record)
        invalid["source_provenance"]["source_attachment_id"] = "attachment-1"
        self.assertFalse(PRIVATE_VALIDATOR.is_valid(invalid))
        self.assertEqual(
            contract.validate_private_metadata_record(invalid)["issue_codes"],
            ["record_shape_invalid"],
        )

    def test_candidate_kind_review_status_and_evidence_binding_matrix(self) -> None:
        evidence_bindings = (
            ("source_record_field", "record-1", None),
            ("source_attachment_metadata", None, "attachment-1"),
            ("source_attachment_metadata", "record-1", "attachment-1"),
            ("source_snapshot_extract", None, None),
            ("source_snapshot_extract", "record-1", None),
            ("source_snapshot_extract", None, "attachment-1"),
            ("source_snapshot_extract", "record-1", "attachment-1"),
        )
        kinds = (
            "human_reviewed_label",
            "original_filename",
            "decoded_filename",
            "normalized_filename_nfc",
            "extension_generic",
            "media_type_generic",
            "object_id_fallback",
        )
        statuses = ("unreviewed", "accepted", "rejected")
        for evidence_kind, source_record_id, source_attachment_id in (
            evidence_bindings
        ):
            for kind in kinds:
                for review_status in statuses:
                    record = _record_with_encoded_names()
                    provenance = record["source_provenance"]
                    provenance["evidence_kind"] = evidence_kind
                    provenance["source_record_id"] = source_record_id
                    provenance["source_attachment_id"] = source_attachment_id
                    review_evidence = (
                        None
                        if review_status == "unreviewed"
                        else REVIEW_DIGEST
                    )
                    record["label_candidates"] = [
                        _candidate(
                            kind,
                            _candidate_value(record, kind),
                            review_status=review_status,
                            review_evidence_sha256=review_evidence,
                        )
                    ]
                    self.assertTrue(
                        PRIVATE_VALIDATOR.is_valid(record),
                        "shape-valid candidate matrix row failed Draft",
                    )
                    runtime = contract.validate_private_metadata_record(record)
                    expected_accepted = (
                        kind != "human_reviewed_label"
                        or review_status == "accepted"
                    )
                    self.assertEqual(
                        runtime["accepted"],
                        expected_accepted,
                        "candidate matrix runtime result differed",
                    )
                    if not expected_accepted:
                        self.assertEqual(
                            runtime["issue_codes"],
                            ["candidate_invariant_invalid"],
                        )

    def test_review_evidence_nullability_relations_fail_semantically(self) -> None:
        kinds = (
            "human_reviewed_label",
            "original_filename",
            "decoded_filename",
            "normalized_filename_nfc",
            "extension_generic",
            "media_type_generic",
            "object_id_fallback",
        )
        invalid_relations = (
            ("unreviewed", REVIEW_DIGEST),
            ("accepted", None),
            ("rejected", None),
        )
        for kind in kinds:
            for review_status, review_evidence in invalid_relations:
                record = _record_with_encoded_names()
                record["label_candidates"] = [
                    _candidate(
                        kind,
                        _candidate_value(record, kind),
                        review_status=review_status,
                        review_evidence_sha256=review_evidence,
                    )
                ]
                self.assertTrue(
                    PRIVATE_VALIDATOR.is_valid(record),
                    "semantic-only review relation failed Draft shape",
                )
                self.assertEqual(
                    contract.validate_private_metadata_record(record),
                    {
                        "accepted": False,
                        "issue_codes": ["candidate_invariant_invalid"],
                    },
                )

    def test_all_evidence_kind_id_bindings_accept_or_reject_on_both_paths(
        self,
    ) -> None:
        accepted_bindings = (
            ("source_record_field", "record-1", None),
            ("source_attachment_metadata", None, "attachment-1"),
            ("source_attachment_metadata", "record-1", "attachment-1"),
            ("source_snapshot_extract", None, None),
            ("source_snapshot_extract", "record-1", None),
            ("source_snapshot_extract", None, "attachment-1"),
            ("source_snapshot_extract", "record-1", "attachment-1"),
        )
        rejected_bindings = (
            ("source_record_field", None, None),
            ("source_record_field", None, "attachment-1"),
            ("source_record_field", "record-1", "attachment-1"),
            ("source_attachment_metadata", None, None),
            ("source_attachment_metadata", "record-1", None),
        )
        for evidence_kind, source_record_id, source_attachment_id in (
            accepted_bindings
        ):
            record = _base_record()
            provenance = record["source_provenance"]
            provenance["evidence_kind"] = evidence_kind
            provenance["source_record_id"] = source_record_id
            provenance["source_attachment_id"] = source_attachment_id
            self.assertTrue(PRIVATE_VALIDATOR.is_valid(record))
            self.assertTrue(
                contract.validate_private_metadata_record(record)["accepted"]
            )
        for evidence_kind, source_record_id, source_attachment_id in (
            rejected_bindings
        ):
            record = _base_record()
            provenance = record["source_provenance"]
            provenance["evidence_kind"] = evidence_kind
            provenance["source_record_id"] = source_record_id
            provenance["source_attachment_id"] = source_attachment_id
            self.assertFalse(PRIVATE_VALIDATOR.is_valid(record))
            self.assertEqual(
                contract.validate_private_metadata_record(record)["issue_codes"],
                ["record_shape_invalid"],
            )

    def test_candidate_kind_bindings_and_filename_safety_fail_closed(self) -> None:
        semantic_only_cases = (
            ("human_reviewed_label", "unsafe/path", "literal_unicode"),
            ("human_reviewed_label", "unsafe\u0001control", "literal_unicode"),
            ("human_reviewed_label", "unsafe\u2066bidi", "literal_unicode"),
            ("original_filename", "other.hwpx", "literal_unicode"),
            ("decoded_filename", "other.hwpx", "utf8_percent_encoded_component"),
            (
                "normalized_filename_nfc",
                "other.hwpx",
                "literal_unicode",
            ),
            ("object_id_fallback", _digest(99), "literal_unicode"),
        )
        for kind, value, profile in semantic_only_cases:
            record = (
                _record_with_encoded_names()
                if profile == "utf8_percent_encoded_component"
                else _base_record()
            )
            record["label_candidates"] = [
                _candidate(
                    kind,
                    value,
                    review_status=(
                        "accepted"
                        if kind == "human_reviewed_label"
                        else "unreviewed"
                    ),
                    review_evidence_sha256=(
                        REVIEW_DIGEST
                        if kind == "human_reviewed_label"
                        else None
                    ),
                )
            ]
            self.assertTrue(
                PRIVATE_VALIDATOR.is_valid(record),
                "semantic-only binding failed Draft shape",
            )
            self.assertEqual(
                contract.validate_private_metadata_record(record)[
                    "issue_codes"
                ],
                ["candidate_invariant_invalid"],
            )

        literal_decoded = _base_record()
        literal_decoded["label_candidates"] = [
            _candidate("decoded_filename", "example.hwpx")
        ]
        self.assertTrue(PRIVATE_VALIDATOR.is_valid(literal_decoded))
        self.assertEqual(
            contract.validate_private_metadata_record(literal_decoded)[
                "issue_codes"
            ],
            ["candidate_invariant_invalid"],
        )

        for generic_kind in ("extension_generic", "media_type_generic"):
            record = _base_record()
            record["label_candidates"] = [
                _candidate(generic_kind, "not-a-generic-family")
            ]
            self.assertFalse(PRIVATE_VALIDATOR.is_valid(record))
            self.assertEqual(
                contract.validate_private_metadata_record(record)[
                    "issue_codes"
                ],
                ["record_shape_invalid"],
            )

    def test_timestamp_profile_matches_custom_format_checker(self) -> None:
        valid_values = (
            "2024-02-29T23:59:59Z",
            "2024-02-29T23:59:59.1+23:59",
            "2024-02-29T23:59:59.123456789-00:00",
        )
        invalid_values = (
            "0000-01-01T00:00:00Z",
            "2023-02-29T00:00:00Z",
            "2024-01-01t00:00:00z",
            "2024-01-01 00:00:00Z",
            "2024-01-01T00:00Z",
            "2024-01-01T00:00:60Z",
            "2024-01-01T00:00:00.1234567890Z",
            "2024-01-01T24:00:00Z",
            "2024-01-01T00:00:00+24:00",
        )
        for captured_at in valid_values:
            record = _base_record()
            record["source_provenance"]["captured_at"] = captured_at
            self.assertTrue(PRIVATE_VALIDATOR.is_valid(record))
            self.assertTrue(
                contract.validate_private_metadata_record(record)["accepted"]
            )
        for captured_at in invalid_values:
            record = _base_record()
            record["source_provenance"]["captured_at"] = captured_at
            self.assertFalse(PRIVATE_VALIDATOR.is_valid(record))
            self.assertEqual(
                contract.validate_private_metadata_record(record)["issue_codes"],
                ["invalid_rfc3339"],
            )

    def test_semantic_candidate_failure_is_not_mislabeled_schema_parity(self) -> None:
        record = _base_record()
        record["label_candidates"] = [
            {
                "kind": "human_reviewed_label",
                "value": "reviewed.hwpx",
                "privacy_class": "private_archive",
                "evidence_sha256": SOURCE_DIGEST,
                "review_status": "unreviewed",
                "review_evidence_sha256": None,
            }
        ]
        self.assertTrue(PRIVATE_VALIDATOR.is_valid(record))
        self.assertEqual(
            contract.validate_private_metadata_record(record),
            {
                "accepted": False,
                "issue_codes": ["candidate_invariant_invalid"],
            },
        )

    def test_restricted_record_privacy_is_schema_and_runtime_enforced(self) -> None:
        record = _base_record()
        record["privacy_class"] = "restricted"
        record["label_candidates"] = [
            {
                "kind": "human_reviewed_label",
                "value": "safe-label",
                "privacy_class": "private_archive",
                "evidence_sha256": SOURCE_DIGEST,
                "review_status": "accepted",
                "review_evidence_sha256": REVIEW_DIGEST,
            }
        ]
        self.assertFalse(PRIVATE_VALIDATOR.is_valid(record))
        self.assertEqual(
            contract.validate_private_metadata_record(record)["issue_codes"],
            ["privacy_invariant_invalid"],
        )
        self.assertEqual(
            contract.project_objet_safe_label([record], "public_generic", True),
            {"projection": None, "issue_codes": ["record_shape_invalid"]},
        )

    def test_claimed_oversize_derived_field_is_runtime_invariant_failure(self) -> None:
        record = _base_record()
        record["names"]["normalized_filename_nfd"] = "x" * 513
        self.assertFalse(PRIVATE_VALIDATOR.is_valid(record))
        self.assertEqual(
            contract.validate_private_metadata_record(record)["issue_codes"],
            ["derived_field_invariant_invalid"],
        )

    def test_projection_one_of_branches_and_runtime_validator(self) -> None:
        for projection in _projection_corpus():
            self.assertTrue(PROJECTION_VALIDATOR.is_valid(projection))
            self.assertEqual(
                contract.validate_objet_safe_label_projection(projection),
                {"accepted": True, "issue_codes": []},
            )

    def test_projection_rejects_cross_branch_private_fields(self) -> None:
        projection = {
            "schema": contract.SAFE_LABEL_SCHEMA,
            "object_id": OBJECT_ID,
            "audience": "public_generic",
            "status": "generic_only",
            "generic_label": {"generic_family": "document"},
            "alternative_count": 0,
            "reason_codes": [],
            "privacy": _privacy(),
            "selected_label": "must-not-appear",
        }
        self.assertFalse(PROJECTION_VALIDATOR.is_valid(projection))
        self.assertEqual(
            contract.validate_objet_safe_label_projection(projection),
            {
                "accepted": False,
                "issue_codes": ["projection_shape_invalid"],
            },
        )

    def test_literal_bounds_are_unicode_scalar_bounds(self) -> None:
        record = _base_record()
        record["names"] = contract.normalize_private_filename(
            "가" * 512,
            "literal_unicode",
        )["names"]
        self.assertTrue(PRIVATE_VALIDATOR.is_valid(record))
        self.assertTrue(
            contract.validate_private_metadata_record(record)["accepted"]
        )
        over = deepcopy(record)
        over["names"]["original_filename"] = "가" * 513
        self.assertFalse(PRIVATE_VALIDATOR.is_valid(over))
        self.assertEqual(
            contract.validate_private_metadata_record(over)["issue_codes"],
            ["record_shape_invalid"],
        )

        source_boundary = _base_record()
        source_boundary["source_provenance"]["source_system"] = "a" * 64
        source_boundary["source_provenance"]["source_attachment_id"] = "가" * 256
        self.assertTrue(PRIVATE_VALIDATOR.is_valid(source_boundary))
        source_over = deepcopy(source_boundary)
        source_over["source_provenance"]["source_system"] = "a" * 65
        self.assertFalse(PRIVATE_VALIDATOR.is_valid(source_over))
        id_over = deepcopy(source_boundary)
        id_over["source_provenance"]["source_attachment_id"] = "가" * 257
        self.assertFalse(PRIVATE_VALIDATOR.is_valid(id_over))

    def test_bound_minus_one_bound_and_bound_plus_one_have_runtime_direction(
        self,
    ) -> None:
        def assert_record(record: dict[str, object], accepted: bool) -> None:
            draft_accepted = PRIVATE_VALIDATOR.is_valid(record)
            runtime_accepted = contract.validate_private_metadata_record(record)[
                "accepted"
            ]
            self.assertEqual(
                draft_accepted,
                accepted,
                "record Draft boundary result differed",
            )
            self.assertEqual(
                runtime_accepted,
                accepted,
                "record runtime boundary result differed",
            )

        for length in (511, 512):
            record = _base_record()
            record["names"] = contract.normalize_private_filename(
                "x" * length,
                "literal_unicode",
            )["names"]
            assert_record(record, True)
            encoded_record = _base_record()
            encoded_record["names"] = contract.normalize_private_filename(
                "x" * length,
                "utf8_percent_encoded_component",
            )["names"]
            self.assertEqual(
                len(encoded_record["names"]["decoded_filename"]),
                length,
            )
            assert_record(encoded_record, True)
        overlong_name = _base_record()
        for field in (
            "original_filename",
            "normalized_filename_nfc",
            "normalized_filename_nfd",
            "filename_stem_nfc",
        ):
            overlong_name["names"][field] = "x" * 513
        assert_record(overlong_name, False)
        overlong_decoded = _record_with_encoded_names()
        overlong_decoded["names"]["decoded_filename"] = "x" * 513
        assert_record(overlong_decoded, False)

        expanding = "\u0344"
        for source, expected_nfd_length in (
            ((expanding * 255) + "a", 511),
            (expanding * 256, 512),
        ):
            record = _base_record()
            record["names"] = contract.normalize_private_filename(
                source,
                "literal_unicode",
            )["names"]
            self.assertEqual(
                len(record["names"]["normalized_filename_nfd"]),
                expected_nfd_length,
            )
            assert_record(record, True)
        blocked_derived_overflow = _base_record()
        blocked_derived_overflow["names"] = (
            contract.normalize_private_filename(
                (expanding * 256) + "a",
                "literal_unicode",
            )["names"]
        )
        self.assertEqual(
            blocked_derived_overflow["names"]["reason_codes"],
            ["derived_name_length_exceeded"],
        )
        assert_record(blocked_derived_overflow, True)

        for length, accepted in (
            (0, False),
            (1, True),
            (2, True),
            (511, True),
            (512, True),
            (513, False),
        ):
            record = _base_record()
            record["label_candidates"] = [
                _candidate(
                    "human_reviewed_label",
                    "x" * length,
                    review_status="accepted",
                    review_evidence_sha256=REVIEW_DIGEST,
                )
            ]
            assert_record(record, accepted)

        for length, accepted in (
            (0, False),
            (1, True),
            (2, True),
            (63, True),
            (64, True),
            (65, False),
        ):
            record = _base_record()
            record["source_provenance"]["source_system"] = "a" * length
            assert_record(record, accepted)

        for length, accepted in (
            (0, False),
            (1, True),
            (2, True),
            (255, True),
            (256, True),
            (257, False),
        ):
            record = _base_record()
            record["source_provenance"]["source_attachment_id"] = "가" * length
            assert_record(record, accepted)

        for length, accepted in (
            (2, False),
            (3, True),
            (4, True),
            (126, True),
            (127, True),
            (128, False),
        ):
            record = _base_record()
            record["media_type"]["value"] = (
                "a/" + ("b" * max(0, length - 2))
            )
            record["media_type"]["basis"] = "source_declared"
            assert_record(record, accepted)

        for size, accepted in ((-1, False), (0, True), (1, True)):
            record = _base_record()
            record["size_bytes"] = size
            record["size_bytes_basis"] = "source_observed"
            assert_record(record, accepted)

        for count, accepted in ((63, True), (64, True), (65, False)):
            record = _base_record()
            record["label_candidates"] = [
                _candidate(
                    "extension_generic",
                    "document",
                    evidence_sha256=_digest(index + 16),
                )
                for index in range(count)
            ]
            assert_record(record, accepted)

        for digest_payload_length, accepted in (
            (63, False),
            (64, True),
            (65, False),
        ):
            record = _base_record()
            record["object_id"] = "sha256:" + ("0" * digest_payload_length)
            assert_record(record, accepted)

        timestamp_boundaries = (
            ("2024-01-01T00:00:0Z", False),
            ("2024-01-01T00:00:00Z", True),
            ("2024-01-01T00:00:00ZZ", False),
            ("2" * 63, False),
            ("2" * 64, False),
            ("2" * 65, False),
        )
        for captured_at, accepted in timestamp_boundaries:
            record = _base_record()
            record["source_provenance"]["captured_at"] = captured_at
            assert_record(record, accepted)

        selected = _projection_corpus()[0]
        for length, accepted in (
            (0, False),
            (1, True),
            (2, True),
            (511, True),
            (512, True),
            (513, False),
        ):
            projection = deepcopy(selected)
            projection["selected_label"] = "x" * length
            self.assertEqual(
                PROJECTION_VALIDATOR.is_valid(projection),
                accepted,
                "projection Draft label boundary result differed",
            )
            self.assertEqual(
                contract.validate_objet_safe_label_projection(projection)[
                    "accepted"
                ],
                accepted,
                "projection runtime label boundary result differed",
            )

        for count, accepted in (
            (-1, False),
            (0, True),
            (1, True),
            (255, True),
            (256, True),
            (257, False),
        ):
            projection = deepcopy(selected)
            projection["alternative_count"] = count
            self.assertEqual(
                PROJECTION_VALIDATOR.is_valid(projection),
                accepted,
                "projection Draft count boundary result differed",
            )
            self.assertEqual(
                contract.validate_objet_safe_label_projection(projection)[
                    "accepted"
                ],
                accepted,
                "projection runtime count boundary result differed",
            )

    def test_unreachable_loose_bounds_preserve_directional_validation(self) -> None:
        for length in (511, 512):
            record = _base_record()
            record["names"]["extension_ascii_lower"] = "x" * length
            self.assertTrue(
                PRIVATE_VALIDATOR.is_valid(record),
                "schema rejected an in-bound claimed extension",
            )
            self.assertEqual(
                contract.validate_private_metadata_record(record)[
                    "issue_codes"
                ],
                ["derived_field_invariant_invalid"],
            )
        overlong_extension = _base_record()
        overlong_extension["names"]["extension_ascii_lower"] = "x" * 513
        self.assertFalse(PRIVATE_VALIDATOR.is_valid(overlong_extension))
        self.assertFalse(
            contract.validate_private_metadata_record(overlong_extension)[
                "accepted"
            ]
        )

        blocked = _base_record()
        blocked["names"] = contract.normalize_private_filename(
            "%252F",
            "utf8_percent_encoded_component",
        )["names"]
        all_name_reasons = list(contract.NAME_REASON_CODES)
        for count in (13, 14):
            record = deepcopy(blocked)
            record["names"]["reason_codes"] = all_name_reasons[:count]
            self.assertTrue(
                PRIVATE_VALIDATOR.is_valid(record),
                "schema rejected an in-bound unique reason array",
            )
            self.assertEqual(
                contract.validate_private_metadata_record(record)[
                    "issue_codes"
                ],
                ["derived_field_invariant_invalid"],
            )
        for count in (15, 16, 17):
            record = deepcopy(blocked)
            reasons = list(all_name_reasons)
            while len(reasons) < count:
                reasons.append(all_name_reasons[0])
            record["names"]["reason_codes"] = reasons
            self.assertFalse(PRIVATE_VALIDATOR.is_valid(record))
            self.assertFalse(
                contract.validate_private_metadata_record(record)["accepted"]
            )

        private_blocked = _projection_corpus()[2]
        allowed = (
            "source_derivation_blocked",
            "no_eligible_label_candidate",
            "candidate_evidence_invalid",
            "private_value_forbidden_for_audience",
        )
        for count in (15, 16, 17):
            projection = deepcopy(private_blocked)
            projection["reason_codes"] = [
                allowed[index % len(allowed)] for index in range(count)
            ]
            self.assertFalse(PROJECTION_VALIDATOR.is_valid(projection))
            self.assertFalse(
                contract.validate_objet_safe_label_projection(projection)[
                    "accepted"
                ]
            )

    def test_public_alternative_count_rejects_json_boolean(self) -> None:
        projection = {
            "schema": contract.SAFE_LABEL_SCHEMA,
            "object_id": OBJECT_ID,
            "audience": "public_generic",
            "status": "blocked",
            "generic_label": None,
            "alternative_count": False,
            "reason_codes": ["generic_family_unavailable"],
            "privacy": _privacy(),
        }
        self.assertFalse(PROJECTION_VALIDATOR.is_valid(projection))
        self.assertEqual(
            contract.validate_objet_safe_label_projection(projection),
            {
                "accepted": False,
                "issue_codes": ["projection_shape_invalid"],
            },
        )

    def test_surrogate_canary_rejection_is_content_free(self) -> None:
        canary = json.loads(r'"\ud800"')
        record = _base_record()
        record["names"]["original_filename"] = canary
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            draft = _draft_result(PRIVATE_VALIDATOR, record)
            runtime = contract.validate_private_metadata_record(record)
        self.assertEqual(
            draft,
            {
                "accepted": False,
                "issue_codes": ["draft202012_instance_rejected"],
            },
        )
        self.assertEqual(
            runtime,
            {
                "accepted": False,
                "issue_codes": ["unpaired_surrogate_input"],
            },
        )
        with self.assertRaises(AssertionError) as raised:
            self.assertEqual(
                draft,
                {"accepted": True, "issue_codes": []},
            )
        self.assertTrue(
            canary not in str(raised.exception),
            "unexpected assertion text reflected the private canary",
        )
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
