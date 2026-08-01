from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock
import urllib.request

from wom_kit import private_objet_metadata as contract


OBJECT_ID = "sha256:" + ("0" * 64)
OBJECT_ID_B = "sha256:" + ("1" * 64)
SOURCE_DIGEST = "sha256:" + ("2" * 64)
OBSERVATION_DIGEST = "sha256:" + ("3" * 64)
REVIEW_DIGEST = "sha256:" + ("4" * 64)
MATCH_DIGEST = "sha256:" + ("5" * 64)


def _digest(index: int) -> str:
    return f"sha256:{index:064x}"


def _record(
    filename: str = "example.hwpx",
    *,
    profile: str = "literal_unicode",
    object_id: str = OBJECT_ID,
    privacy_class: str = "private_archive",
) -> dict[str, object]:
    names = contract.normalize_private_filename(filename, profile)["names"]
    return {
        "schema": contract.PRIVATE_METADATA_SCHEMA,
        "privacy_class": privacy_class,
        "object_id": object_id,
        "names": names,
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
            "captured_at": "2026-07-31T23:59:59.123456789-00:00",
        },
        "label_candidates": [],
        "normalization_profile": {
            "id": contract.NORMALIZATION_PROFILE,
            "unicode_version": "17.0.0",
            "confusables_data_sha256": None,
            "confusable_status": "not_checked",
        },
    }


def _candidate(
    kind: str,
    value: str,
    *,
    privacy_class: str = "private_archive",
    evidence: str = SOURCE_DIGEST,
    review_status: str = "unreviewed",
    review_evidence: str | None = None,
) -> dict[str, object]:
    return {
        "kind": kind,
        "value": value,
        "privacy_class": privacy_class,
        "evidence_sha256": evidence,
        "review_status": review_status,
        "review_evidence_sha256": review_evidence,
    }


def _generic_candidates(count: int) -> list[dict[str, object]]:
    return [
        _candidate(
            "extension_generic",
            "document",
            evidence=_digest(index + 16),
        )
        for index in range(count)
    ]


class PrivateFilenameNormalizationTests(unittest.TestCase):
    def test_literal_percent_triplet_is_not_decoded(self) -> None:
        result = contract.normalize_private_filename(
            "literal%2Fname.txt",
            "literal_unicode",
        )
        self.assertEqual(result["issue_codes"], [])
        self.assertEqual(result["names"]["derivation_status"], "valid")
        self.assertEqual(
            result["names"]["normalized_filename_nfc"],
            "literal%2Fname.txt",
        )

    def test_encoded_component_decodes_exactly_once_and_preserves_plus(self) -> None:
        result = contract.normalize_private_filename(
            "한%20글+memo%2ETXT",
            "utf8_percent_encoded_component",
        )
        self.assertEqual(result["issue_codes"], [])
        self.assertEqual(result["names"]["decoded_filename"], "한 글+memo.TXT")
        self.assertEqual(result["names"]["filename_stem_nfc"], "한 글+memo")
        self.assertEqual(result["names"]["extension_ascii_lower"], "txt")
        residual = contract.normalize_private_filename(
            "%252F",
            "utf8_percent_encoded_component",
        )
        self.assertEqual(
            residual["names"]["reason_codes"],
            ["residual_percent_triplet"],
        )

    def test_decode_failures_are_fixed_blocked_results(self) -> None:
        cases = (
            ("%", "malformed_percent_escape"),
            ("%GG", "malformed_percent_escape"),
            ("%FF", "invalid_utf8"),
            ("%EF%BB%BFsecret", "utf8_bom_forbidden"),
            ("%2F", "path_separator_forbidden"),
        )
        for value, reason in cases:
            result = contract.normalize_private_filename(
                value,
                "utf8_percent_encoded_component",
            )
            names = result["names"]
            self.assertEqual(result["issue_codes"], [])
            self.assertEqual(names["derivation_status"], "blocked")
            self.assertEqual(names["reason_codes"], [reason])
            for field in (
                "decoded_filename",
                "normalized_filename_nfc",
                "normalized_filename_nfd",
                "filename_stem_nfc",
                "extension_ascii_lower",
            ):
                self.assertIsNone(names[field])

    def test_multiple_safety_reasons_have_normative_stable_order(self) -> None:
        result = contract.normalize_private_filename(
            "%2F%00%C2%85%E2%80%A8",
            "utf8_percent_encoded_component",
        )
        self.assertEqual(
            result["names"]["reason_codes"],
            [
                "path_separator_forbidden",
                "nul_forbidden",
                "c1_control_forbidden",
                "unicode_separator_forbidden",
            ],
        )

    def test_empty_reserved_bidi_and_unpaired_inputs_fail_closed(self) -> None:
        empty = contract.normalize_private_filename("", "literal_unicode")
        reserved = contract.normalize_private_filename("..", "literal_unicode")
        bidi = contract.normalize_private_filename(
            "safe\u2066name",
            "literal_unicode",
        )
        surrogate = json.loads(r'"\ud800"')
        invalid_scalar = contract.normalize_private_filename(
            surrogate,
            "literal_unicode",
        )
        self.assertEqual(
            empty["names"]["reason_codes"],
            ["empty_filename_forbidden"],
        )
        self.assertEqual(
            reserved["names"]["reason_codes"],
            ["reserved_path_segment_forbidden"],
        )
        self.assertEqual(
            bidi["names"]["reason_codes"],
            ["bidi_control_forbidden"],
        )
        self.assertEqual(
            invalid_scalar,
            {"names": None, "issue_codes": ["unpaired_surrogate_input"]},
        )

    def test_derived_length_511_512_and_513_boundaries(self) -> None:
        expanding = "\u0344"
        valid_511 = contract.normalize_private_filename(
            (expanding * 255) + "a",
            "literal_unicode",
        )
        valid_512 = contract.normalize_private_filename(
            expanding * 256,
            "literal_unicode",
        )
        blocked_513 = contract.normalize_private_filename(
            (expanding * 256) + "a",
            "literal_unicode",
        )
        self.assertEqual(
            len(valid_511["names"]["normalized_filename_nfd"]),
            511,
        )
        self.assertEqual(
            len(valid_512["names"]["normalized_filename_nfd"]),
            512,
        )
        self.assertEqual(
            blocked_513["names"]["reason_codes"],
            ["derived_name_length_exceeded"],
        )
        self.assertEqual(blocked_513["names"]["decode_status"], "not_requested")
        for field in (
            "decoded_filename",
            "normalized_filename_nfc",
            "normalized_filename_nfd",
            "filename_stem_nfc",
            "extension_ascii_lower",
        ):
            self.assertIsNone(blocked_513["names"][field])

        encoded = contract.normalize_private_filename(
            (expanding * 256) + "%61",
            "utf8_percent_encoded_component",
        )
        self.assertEqual(
            encoded["names"]["reason_codes"],
            ["derived_name_length_exceeded"],
        )
        self.assertEqual(encoded["names"]["decode_status"], "blocked")

    def test_scalar_extension_table(self) -> None:
        cases = (
            ("report", "report", None),
            (".env", ".env", None),
            (".profile.LOCAL", ".profile", "local"),
            ("report.", "report.", None),
            (".x.", ".x.", None),
            ("report.TAR.GZ", "report.TAR", "gz"),
            ("a..TXT", "a.", "txt"),
            ("report.한글", "report.한글", None),
            ("report\u2024TXT", "report\u2024TXT", None),
        )
        for filename, stem, extension in cases:
            names = contract.normalize_private_filename(
                filename,
                "literal_unicode",
            )["names"]
            self.assertEqual(names["filename_stem_nfc"], stem)
            self.assertEqual(names["extension_ascii_lower"], extension)

    def test_search_keys_use_canonical_not_compatibility_equivalence(self) -> None:
        composed = contract.normalize_private_filename(
            "가나다.txt",
            "literal_unicode",
        )["names"]
        decomposed = contract.normalize_private_filename(
            "가나다.txt",
            "literal_unicode",
        )["names"]
        composed_keys = contract.derive_filename_search_keys(composed)
        decomposed_keys = contract.derive_filename_search_keys(decomposed)
        self.assertEqual(composed_keys, decomposed_keys)

        compatibility = contract.normalize_private_filename(
            "①.txt",
            "literal_unicode",
        )["names"]
        ascii_name = contract.normalize_private_filename(
            "1.txt",
            "literal_unicode",
        )["names"]
        self.assertNotEqual(
            contract.derive_filename_search_keys(compatibility)["search_keys"][0][
                "value"
            ],
            contract.derive_filename_search_keys(ascii_name)["search_keys"][0][
                "value"
            ],
        )

    def test_separator_fold_is_an_alias_only_and_stable_first_wins(self) -> None:
        values = []
        for filename in ("alpha beta.txt", "alpha_beta.txt", "alpha-beta.txt"):
            names = contract.normalize_private_filename(
                filename,
                "literal_unicode",
            )["names"]
            keys = contract.derive_filename_search_keys(names)["search_keys"]
            values.append(
                "alpha beta.txt"
                if any(item["value"] == "alpha beta.txt" for item in keys)
                else ""
            )
            self.assertEqual(
                len({item["value"] for item in keys}),
                len(keys),
            )
        self.assertEqual(values, ["alpha beta.txt"] * 3)

    def test_search_helper_rejects_claimed_fields_and_accepts_blocked_names(self) -> None:
        names = contract.normalize_private_filename(
            "example.txt",
            "literal_unicode",
        )["names"]
        claimed = deepcopy(names)
        claimed["normalized_filename_nfc"] = "changed.txt"
        self.assertEqual(
            contract.derive_filename_search_keys(claimed),
            {
                "search_keys": [],
                "issue_codes": ["derived_field_invariant_invalid"],
            },
        )
        blocked = contract.normalize_private_filename(
            "%252F",
            "utf8_percent_encoded_component",
        )["names"]
        self.assertEqual(
            contract.derive_filename_search_keys(blocked),
            {"search_keys": [], "issue_codes": []},
        )

    def test_search_key_2047_2048_and_2049_defensive_boundaries(self) -> None:
        names = contract.normalize_private_filename(
            "example",
            "literal_unicode",
        )["names"]
        for length in (2047, 2048):
            with mock.patch.object(
                contract,
                "_canonical_caseless",
                return_value="x" * length,
            ):
                result = contract.derive_filename_search_keys(names)
            self.assertEqual(result["issue_codes"], [])
            self.assertEqual(len(result["search_keys"]), 1)
            self.assertEqual(len(result["search_keys"][0]["value"]), length)

        with mock.patch.object(
            contract,
            "_canonical_caseless",
            return_value="x" * 2049,
        ):
            overflow = contract.derive_filename_search_keys(names)
        self.assertEqual(
            overflow,
            {
                "search_keys": [],
                "issue_codes": ["derived_field_invariant_invalid"],
            },
        )

    def test_search_key_array_reaches_four_and_exact_maximum_five(self) -> None:
        expected_counts = (
            ("A.B-C", 4),
            ("Alpha-Beta.TXT", 5),
        )
        for filename, expected_count in expected_counts:
            names = contract.normalize_private_filename(
                filename,
                "literal_unicode",
            )["names"]
            result = contract.derive_filename_search_keys(names)
            self.assertEqual(result["issue_codes"], [])
            self.assertEqual(len(result["search_keys"]), expected_count)
            self.assertLessEqual(len(result["search_keys"]), 5)

    def test_unicode_profile_mismatch_precedes_valid_and_blocked_derivation(self) -> None:
        blocked_record = _record(
            "%252F",
            profile="utf8_percent_encoded_component",
        )
        blocked_record["label_candidates"] = [
            _candidate("extension_generic", "document")
        ]
        expected_issue = {
            "names": None,
            "issue_codes": ["derived_field_invariant_invalid"],
        }
        with mock.patch.object(
            contract.unicodedata2,
            "unidata_version",
            "16.0.0",
        ):
            self.assertEqual(
                contract.normalize_private_filename(
                    "valid.txt",
                    "literal_unicode",
                ),
                expected_issue,
            )
            self.assertEqual(
                contract.normalize_private_filename(
                    "%252F",
                    "utf8_percent_encoded_component",
                ),
                expected_issue,
            )
            self.assertEqual(
                contract.validate_private_metadata_record(blocked_record),
                {
                    "accepted": False,
                    "issue_codes": ["derived_field_invariant_invalid"],
                },
            )
            self.assertEqual(
                contract.project_objet_safe_label(
                    [blocked_record],
                    "public_generic",
                    True,
                ),
                {
                    "projection": None,
                    "issue_codes": ["record_shape_invalid"],
                },
            )


class PrivateMetadataProjectionTests(unittest.TestCase):
    def test_record_validator_accepts_exact_computed_record(self) -> None:
        record = _record()
        record["label_candidates"] = [
            _candidate("original_filename", "example.hwpx"),
            _candidate(
                "human_reviewed_label",
                "Reviewed document",
                review_status="accepted",
                review_evidence=REVIEW_DIGEST,
            ),
        ]
        self.assertEqual(
            contract.validate_private_metadata_record(record),
            {"accepted": True, "issue_codes": []},
        )

    def test_candidate_binding_failure_becomes_blocked_projection(self) -> None:
        record = _record()
        record["label_candidates"] = [
            _candidate("original_filename", "not-the-source-name.hwpx")
        ]
        self.assertEqual(
            contract.validate_private_metadata_record(record)["issue_codes"],
            ["candidate_invariant_invalid"],
        )
        projected = contract.project_objet_safe_label(
            [record],
            "private_archive",
            True,
        )
        self.assertEqual(projected["issue_codes"], [])
        self.assertEqual(projected["projection"]["status"], "blocked")
        self.assertEqual(
            projected["projection"]["reason_codes"],
            ["candidate_evidence_invalid"],
        )

    def test_human_reviewed_label_wins_and_privacy_exposure_is_explicit(self) -> None:
        record = _record()
        record["label_candidates"] = [
            _candidate("original_filename", "example.hwpx"),
            _candidate(
                "human_reviewed_label",
                "Reviewed document",
                review_status="accepted",
                review_evidence=REVIEW_DIGEST,
            ),
            _candidate("extension_generic", "document"),
        ]
        projection = contract.project_objet_safe_label(
            [record],
            "private_archive",
            True,
        )["projection"]
        self.assertEqual(projection["status"], "selected")
        self.assertEqual(projection["selected_label"], "Reviewed document")
        self.assertEqual(projection["selected_kind"], "human_reviewed_label")
        self.assertEqual(projection["alternative_count"], 2)
        self.assertTrue(projection["privacy"]["private_filename_exposed"])

    def test_same_rank_distinct_values_are_ambiguous_without_winner(self) -> None:
        first = _record("first.txt")
        second = _record("second.txt")
        first["label_candidates"] = [
            _candidate(
                "human_reviewed_label",
                "Alpha",
                evidence=SOURCE_DIGEST,
                review_status="accepted",
                review_evidence=REVIEW_DIGEST,
            )
        ]
        second["label_candidates"] = [
            _candidate(
                "human_reviewed_label",
                "Beta",
                evidence=OBSERVATION_DIGEST,
                review_status="accepted",
                review_evidence=REVIEW_DIGEST,
            )
        ]
        expected = contract.project_objet_safe_label(
            [first, second],
            "private_archive",
            True,
        )
        shuffled = contract.project_objet_safe_label(
            [second, first],
            "private_archive",
            True,
        )
        self.assertEqual(expected, shuffled)
        projection = expected["projection"]
        self.assertEqual(projection["status"], "ambiguous")
        self.assertIsNone(projection["selected_label"])
        self.assertEqual(projection["alternative_count"], 2)

    def test_exact_duplicates_deduplicate_but_distinct_evidence_is_preserved(self) -> None:
        first = _record()
        second = _record()
        third = _record()
        first["label_candidates"] = [
            _candidate("extension_generic", "document")
        ]
        second["label_candidates"] = [
            _candidate("extension_generic", "document")
        ]
        third["label_candidates"] = [
            _candidate(
                "media_type_generic",
                "document",
                evidence=OBSERVATION_DIGEST,
            )
        ]
        projection = contract.project_objet_safe_label(
            [third, second, first],
            "private_archive",
            True,
        )["projection"]
        self.assertEqual(projection["status"], "selected")
        self.assertEqual(projection["selected_kind"], "extension_generic")
        self.assertEqual(projection["alternative_count"], 0)
        self.assertFalse(projection["privacy"]["private_filename_exposed"])

    def test_rejected_and_audience_ineligible_candidates_follow_priority(self) -> None:
        record = _record()
        record["label_candidates"] = [
            _candidate(
                "extension_generic",
                "document",
                review_status="rejected",
                review_evidence=REVIEW_DIGEST,
            ),
            _candidate("original_filename", "example.hwpx"),
        ]
        restricted = contract.project_objet_safe_label(
            [record],
            "restricted",
            True,
        )["projection"]
        self.assertEqual(
            restricted["reason_codes"],
            ["private_value_forbidden_for_audience"],
        )

    def test_blocked_derivation_reason_does_not_reflect_source(self) -> None:
        private_canary = "%252F_PRIVATE_CANARY"
        record = _record(
            private_canary,
            profile="utf8_percent_encoded_component",
        )
        projection = contract.project_objet_safe_label(
            [record],
            "private_archive",
            True,
        )["projection"]
        self.assertEqual(
            projection["reason_codes"],
            ["source_derivation_blocked"],
        )
        self.assertTrue(
            private_canary not in json.dumps(projection),
            "blocked projection reflected a private value",
        )

    def test_public_generic_projection_never_returns_private_values(self) -> None:
        private_canary = "PRIVATE_FILENAME_TOKEN_CANARY.hwpx"
        record = _record(private_canary)
        record["source_provenance"]["source_record_id"] = "PRIVATE_SOURCE_ID"
        record["label_candidates"] = [
            _candidate("original_filename", private_canary),
            _candidate("extension_generic", "document"),
        ]
        projection = contract.project_objet_safe_label(
            [record],
            "public_generic",
            True,
        )["projection"]
        serialized = json.dumps(projection, sort_keys=True)
        self.assertEqual(projection["status"], "generic_only")
        self.assertEqual(
            projection["generic_label"],
            {"generic_family": "document"},
        )
        self.assertTrue(
            private_canary not in serialized,
            "public projection leaked a private filename",
        )
        self.assertTrue(
            "PRIVATE_SOURCE_ID" not in serialized,
            "public projection leaked a private source identifier",
        )
        self.assertEqual(projection["alternative_count"], 0)

    def test_public_projection_does_not_reflect_path_url_provider_token_or_controls(
        self,
    ) -> None:
        canaries = (
            r"C:\private\archive\SECRET-PATH.txt",
            "https://provider.invalid/private/SECRET-URL",
            "notion-provider-SECRET-LOCATOR",
            "token_SECRET-VALUE-123456789",
            "control\u0001SECRET-CONTROL",
            "bidi\u2066SECRET-BIDI",
        )
        generic = _record("safe.txt")
        generic["label_candidates"] = [
            _candidate("extension_generic", "document")
        ]
        records = [generic]
        for index, canary in enumerate(canaries):
            record = _record(canary)
            record["source_provenance"]["source_record_id"] = (
                f"private-source-{index}-{canary}"
            )
            records.append(record)

        result = contract.project_objet_safe_label(
            records,
            "public_generic",
            True,
        )
        projection = result["projection"]
        serialized = json.dumps(
            projection,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        self.assertEqual(result["issue_codes"], [])
        self.assertEqual(projection["status"], "generic_only")
        self.assertEqual(
            projection["generic_label"],
            {"generic_family": "document"},
        )
        for canary in canaries:
            self.assertNotIn(canary, serialized)
            self.assertNotIn(
                json.dumps(canary, ensure_ascii=True)[1:-1],
                serialized,
            )

    def test_public_generic_rejected_zero_one_and_multiple_family_rules(self) -> None:
        zero = _record()
        zero["label_candidates"] = [
            _candidate(
                "extension_generic",
                "document",
                review_status="rejected",
                review_evidence=REVIEW_DIGEST,
            )
        ]
        zero_projection = contract.project_objet_safe_label(
            [zero],
            "public_generic",
            True,
        )["projection"]
        self.assertEqual(
            zero_projection["reason_codes"],
            ["generic_family_unavailable"],
        )

        one = _record()
        one["label_candidates"] = [
            _candidate(
                "extension_generic",
                "document",
                privacy_class="restricted",
            )
        ]
        self.assertEqual(
            contract.project_objet_safe_label(
                [one],
                "public_generic",
                True,
            )["projection"]["generic_label"],
            {"generic_family": "document"},
        )

        multiple = _record()
        multiple["label_candidates"] = [
            _candidate("extension_generic", "document"),
            _candidate("media_type_generic", "image"),
        ]
        multiple_projection = contract.project_objet_safe_label(
            [multiple],
            "public_generic",
            True,
        )["projection"]
        self.assertEqual(
            multiple_projection["reason_codes"],
            ["generic_family_unavailable"],
        )

    def test_projector_no_output_validation_order_is_exact(self) -> None:
        record = _record()
        self.assertEqual(
            contract.project_objet_safe_label([], "invalid", False),
            {
                "projection": None,
                "issue_codes": ["projection_shape_invalid"],
            },
        )
        self.assertEqual(
            contract.project_objet_safe_label([], "private_archive", False),
            {"projection": None, "issue_codes": ["record_shape_invalid"]},
        )
        self.assertEqual(
            contract.project_objet_safe_label(
                [record],
                "private_archive",
                False,
            ),
            {
                "projection": None,
                "issue_codes": ["privacy_invariant_invalid"],
            },
        )

    def test_projector_record_and_flattened_candidate_boundaries(self) -> None:
        for record_count in (63, 64):
            records = [_record() for _ in range(record_count)]
            projected = contract.project_objet_safe_label(
                records,
                "private_archive",
                True,
            )
            self.assertEqual(projected["issue_codes"], [])
            self.assertEqual(
                projected["projection"]["reason_codes"],
                ["no_eligible_label_candidate"],
            )
        self.assertEqual(
            contract.project_objet_safe_label(
                [_record() for _ in range(65)],
                "private_archive",
                True,
            ),
            {"projection": None, "issue_codes": ["record_shape_invalid"]},
        )

        for counts in ((64, 64, 64, 63), (64, 64, 64, 64)):
            records = []
            for count in counts:
                record = _record()
                record["label_candidates"] = _generic_candidates(count)
                records.append(record)
            projected = contract.project_objet_safe_label(
                records,
                "private_archive",
                True,
            )
            self.assertEqual(projected["issue_codes"], [])
            self.assertEqual(projected["projection"]["status"], "selected")
            self.assertEqual(projected["projection"]["selected_label"], "document")

        overflow_records = []
        for count in (64, 64, 64, 64, 1):
            record = _record()
            record["label_candidates"] = _generic_candidates(count)
            overflow_records.append(record)
        self.assertEqual(
            contract.project_objet_safe_label(
                overflow_records,
                "private_archive",
                True,
            ),
            {"projection": None, "issue_codes": ["record_shape_invalid"]},
        )

    def test_mixed_object_ids_are_no_output_refusal(self) -> None:
        first = _record()
        second = _record(object_id=OBJECT_ID_B)
        self.assertEqual(
            contract.project_objet_safe_label(
                [first, second],
                "private_archive",
                True,
            ),
            {"projection": None, "issue_codes": ["record_shape_invalid"]},
        )

    def test_helpers_preserve_archive_and_make_zero_io_provider_calls(self) -> None:
        from wom_kit import archive_services

        def archive_digest(root: Path) -> str:
            digest = hashlib.sha256()
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    digest.update(path.relative_to(root).as_posix().encode("utf-8"))
                    digest.update(b"\0")
                    digest.update(path.read_bytes())
                    digest.update(b"\0")
            return digest.hexdigest()

        names = contract.normalize_private_filename(
            "example.txt",
            "literal_unicode",
        )["names"]
        record = _record()
        with tempfile.TemporaryDirectory() as temporary:
            archive_root = Path(temporary) / "synthetic-archive"
            archive_root.mkdir()
            (archive_root / "private-source.bin").write_bytes(
                b"synthetic-private-source"
            )
            before = archive_digest(archive_root)
            with (
                mock.patch("builtins.open", side_effect=AssertionError) as opened,
                mock.patch.object(
                    socket,
                    "create_connection",
                    side_effect=AssertionError,
                ) as connected,
                mock.patch.object(
                    urllib.request,
                    "urlopen",
                    side_effect=AssertionError,
                ) as fetched,
                mock.patch.object(
                    archive_services,
                    "normalize_notion_provider_locator",
                    side_effect=AssertionError,
                ) as provider_called,
            ):
                contract.normalize_private_filename(
                    "example.txt",
                    "literal_unicode",
                )
                contract.derive_filename_search_keys(names)
                contract.validate_private_metadata_record(record)
                contract.project_objet_safe_label(
                    [record],
                    "public_generic",
                    True,
                )
                contract.resolve_label_ambiguity([])
            after = archive_digest(archive_root)
        self.assertEqual(before, after)
        opened.assert_not_called()
        connected.assert_not_called()
        fetched.assert_not_called()
        provider_called.assert_not_called()

    def test_untrusted_json_value_types_never_escape_as_raw_exceptions(self) -> None:
        record = _record()
        record["privacy_class"] = []
        self.assertEqual(
            contract.validate_private_metadata_record(record),
            {"accepted": False, "issue_codes": ["record_shape_invalid"]},
        )
        self.assertEqual(
            contract.project_objet_safe_label(
                [record],
                "private_archive",
                True,
            ),
            {"projection": None, "issue_codes": ["record_shape_invalid"]},
        )
        projection = {
            "schema": contract.SAFE_LABEL_SCHEMA,
            "object_id": OBJECT_ID,
            "audience": "private_archive",
            "status": "selected",
            "selected_label": "safe",
            "selected_kind": [],
            "alternative_count": 0,
            "ambiguity": {"state": "none"},
            "reason_codes": [],
            "privacy": {
                "private_filename_exposed": False,
                "source_identifier_exposed": False,
                "local_path_exposed": False,
                "provider_locator_exposed": False,
                "secret_value_exposed": False,
            },
        }
        self.assertEqual(
            contract.validate_objet_safe_label_projection(projection),
            {
                "accepted": False,
                "issue_codes": ["projection_shape_invalid"],
            },
        )

    def test_untrusted_bool_int_list_dict_and_unhashable_values_fail_closed(
        self,
    ) -> None:
        invalid_normalizer_inputs = (True, 1, [], {})
        for value in invalid_normalizer_inputs:
            self.assertEqual(
                contract.normalize_private_filename(
                    value,
                    "literal_unicode",
                ),
                {"names": None, "issue_codes": ["record_shape_invalid"]},
            )

        for value in (True, 1, [], {}, {"reason_codes": [[], {}]}):
            self.assertEqual(
                contract.derive_filename_search_keys(value),
                {
                    "search_keys": [],
                    "issue_codes": ["derived_field_invariant_invalid"],
                },
            )
            self.assertEqual(
                contract.validate_private_metadata_record(value),
                {
                    "accepted": False,
                    "issue_codes": ["record_shape_invalid"],
                },
            )

        for audience in (True, 1, [], {}):
            self.assertEqual(
                contract.project_objet_safe_label(
                    [_record()],
                    audience,
                    True,
                ),
                {
                    "projection": None,
                    "issue_codes": ["projection_shape_invalid"],
                },
            )
        for disclosure in (0, 1, [], {}):
            self.assertEqual(
                contract.project_objet_safe_label(
                    [_record()],
                    "private_archive",
                    disclosure,
                ),
                {
                    "projection": None,
                    "issue_codes": ["projection_shape_invalid"],
                },
            )

        invalid_projection = {
            "schema": contract.SAFE_LABEL_SCHEMA,
            "object_id": OBJECT_ID,
            "audience": "public_generic",
            "status": "blocked",
            "generic_label": None,
            "alternative_count": 0,
            "reason_codes": [[], {}],
            "privacy": {
                "private_filename_exposed": False,
                "source_identifier_exposed": False,
                "local_path_exposed": False,
                "provider_locator_exposed": False,
                "secret_value_exposed": False,
            },
        }
        self.assertEqual(
            contract.validate_objet_safe_label_projection(invalid_projection),
            {
                "accepted": False,
                "issue_codes": ["projection_shape_invalid"],
            },
        )
        for value in (True, 1, {}, [[], {}]):
            self.assertEqual(
                contract.resolve_label_ambiguity(value),
                {
                    "status": "blocked",
                    "selected_object_id": None,
                    "object_ids": [],
                    "match_count": 0,
                    "reason_codes": ["candidate_evidence_invalid"],
                },
            )

    def test_deep_json_and_cyclic_python_values_never_raise_raw_exceptions(
        self,
    ) -> None:
        deep_json = (
            '{"audience":"public_generic","unexpected":'
            + ("[" * 500)
            + "null"
            + ("]" * 500)
            + "}"
        )
        deep_value = json.loads(deep_json)
        expected = {
            "accepted": False,
            "issue_codes": ["projection_shape_invalid"],
        }
        self.assertEqual(
            contract.validate_objet_safe_label_projection(deep_value),
            expected,
        )

        cyclic_list: list[object] = []
        cyclic_list.append(cyclic_list)
        cyclic_dict: dict[str, object] = {}
        cyclic_dict["self"] = cyclic_dict
        for cyclic in (cyclic_list, cyclic_dict):
            self.assertEqual(
                contract.validate_objet_safe_label_projection(
                    {
                        "audience": "public_generic",
                        "unexpected": cyclic,
                    }
                ),
                expected,
            )

        first_cycle: list[object] = []
        second_cycle: list[object] = []
        first_cycle.append(first_cycle)
        second_cycle.append(second_cycle)
        cyclic_reason_projection = {
            "schema": contract.SAFE_LABEL_SCHEMA,
            "object_id": OBJECT_ID,
            "audience": "public_generic",
            "status": "blocked",
            "generic_label": None,
            "alternative_count": 0,
            "reason_codes": [first_cycle, second_cycle],
            "privacy": {
                "private_filename_exposed": False,
                "source_identifier_exposed": False,
                "local_path_exposed": False,
                "provider_locator_exposed": False,
                "secret_value_exposed": False,
            },
        }
        self.assertEqual(
            contract.validate_objet_safe_label_projection(
                cyclic_reason_projection
            ),
            expected,
        )


class LabelAmbiguityResolverTests(unittest.TestCase):
    def test_empty_unique_and_ambiguous_results_have_exact_shape(self) -> None:
        empty = contract.resolve_label_ambiguity([])
        self.assertEqual(
            empty,
            {
                "status": "blocked",
                "selected_object_id": None,
                "object_ids": [],
                "match_count": 0,
                "reason_codes": ["no_eligible_label_candidate"],
            },
        )
        unique = contract.resolve_label_ambiguity(
            [
                {
                    "object_id": OBJECT_ID,
                    "match_evidence_sha256": MATCH_DIGEST,
                },
                {
                    "object_id": OBJECT_ID,
                    "match_evidence_sha256": SOURCE_DIGEST,
                },
            ]
        )
        self.assertEqual(unique["status"], "unique_object")
        self.assertEqual(unique["selected_object_id"], OBJECT_ID)
        self.assertEqual(unique["match_count"], 1)

        ambiguous = contract.resolve_label_ambiguity(
            [
                {
                    "object_id": OBJECT_ID_B,
                    "match_evidence_sha256": MATCH_DIGEST,
                },
                {
                    "object_id": OBJECT_ID,
                    "match_evidence_sha256": MATCH_DIGEST,
                },
            ]
        )
        self.assertEqual(ambiguous["status"], "ambiguous")
        self.assertEqual(
            ambiguous["object_ids"],
            [OBJECT_ID, OBJECT_ID_B],
        )
        self.assertEqual(ambiguous["match_count"], 2)
        self.assertIsNone(ambiguous["selected_object_id"])

    def test_invalid_row_contaminates_whole_result(self) -> None:
        result = contract.resolve_label_ambiguity(
            [
                {
                    "object_id": OBJECT_ID,
                    "match_evidence_sha256": MATCH_DIGEST,
                },
                {
                    "object_id": OBJECT_ID_B,
                    "match_evidence_sha256": "invalid",
                },
            ]
        )
        self.assertEqual(
            result,
            {
                "status": "blocked",
                "selected_object_id": None,
                "object_ids": [],
                "match_count": 0,
                "reason_codes": ["candidate_evidence_invalid"],
            },
        )

    def test_resolver_rejects_extra_fields_and_bound_overflow(self) -> None:
        invalid = contract.resolve_label_ambiguity(
            [
                {
                    "object_id": OBJECT_ID,
                    "match_evidence_sha256": MATCH_DIGEST,
                    "query": "not-accepted",
                }
            ]
        )
        overflow = contract.resolve_label_ambiguity(
            [
                {
                    "object_id": OBJECT_ID,
                    "match_evidence_sha256": MATCH_DIGEST,
                }
            ]
            * 257
        )
        self.assertEqual(
            invalid["reason_codes"],
            ["candidate_evidence_invalid"],
        )
        self.assertEqual(
            overflow["reason_codes"],
            ["candidate_evidence_invalid"],
        )

    def test_resolver_255_256_and_257_record_boundaries(self) -> None:
        for count in (255, 256):
            records = [
                {
                    "object_id": _digest(index),
                    "match_evidence_sha256": MATCH_DIGEST,
                }
                for index in range(count)
            ]
            result = contract.resolve_label_ambiguity(records)
            self.assertEqual(result["status"], "ambiguous")
            self.assertEqual(result["match_count"], count)
            self.assertEqual(len(result["object_ids"]), count)
            self.assertEqual(
                result["object_ids"],
                sorted(result["object_ids"], key=lambda value: value.encode("ascii")),
            )

        overflow = contract.resolve_label_ambiguity(
            [
                {
                    "object_id": _digest(index),
                    "match_evidence_sha256": MATCH_DIGEST,
                }
                for index in range(257)
            ]
        )
        self.assertEqual(
            overflow,
            {
                "status": "blocked",
                "selected_object_id": None,
                "object_ids": [],
                "match_count": 0,
                "reason_codes": ["candidate_evidence_invalid"],
            },
        )


if __name__ == "__main__":
    unittest.main()
