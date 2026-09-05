"""Pure v0.1 private objet metadata and safe-label contract helpers.

This module is deliberately isolated from archive, provider, database, and
filesystem services.  It validates only the bounded values supplied by a
caller.  SHA-256 object identifiers remain identity; human-readable names are
provenance-bound aliases.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import unicodedata2

from ._unicode17_tables import (
    BIDI_CONTROL_CODE_POINTS,
    CASE_FOLDING_CF,
    EFFECTIVE_SEPARATOR_WHITESPACE_CODE_POINTS,
    UNICODE_VERSION,
)


PRIVATE_METADATA_SCHEMA = "wom-kit/private-objet-source-metadata/v0.1"
SAFE_LABEL_SCHEMA = "wom-kit/objet-safe-label-projection/v0.1"
NORMALIZATION_PROFILE = "wom-kit/filename-normalization/v0.1"

OBJECT_ID_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
SOURCE_SYSTEM_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,63})$")
MEDIA_TYPE_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9!#$&^_.+\-]{0,126}/"
    r"[a-z0-9][a-z0-9!#$&^_.+\-]{0,126}$"
)
RFC3339_PATTERN = re.compile(
    r"^(?!0000)([0-9]{4})-(0[1-9]|1[0-2])-"
    r"(0[1-9]|[12][0-9]|3[01])T"
    r"([01][0-9]|2[0-3]):([0-5][0-9]):([0-5][0-9])"
    r"(?:\.([0-9]{1,9}))?"
    r"(Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])$"
)
PERCENT_TRIPLET_PATTERN = re.compile(r"%[0-9A-Fa-f]{2}")

NAME_INPUT_PROFILES = {
    "literal_unicode",
    "utf8_percent_encoded_component",
}
DECODE_STATUSES = {"not_requested", "decoded", "blocked"}
DERIVATION_STATUSES = {"valid", "blocked"}
PRIVACY_CLASSES = {"private_archive", "restricted"}
AUDIENCES = {"private_archive", "restricted", "public_generic"}
EVIDENCE_KINDS = {
    "source_record_field",
    "source_attachment_metadata",
    "source_snapshot_extract",
}
CANDIDATE_KINDS = {
    "human_reviewed_label",
    "original_filename",
    "decoded_filename",
    "normalized_filename_nfc",
    "extension_generic",
    "media_type_generic",
    "object_id_fallback",
}
FILENAME_CANDIDATE_KINDS = {
    "human_reviewed_label",
    "original_filename",
    "decoded_filename",
    "normalized_filename_nfc",
}
GENERIC_CANDIDATE_KINDS = {"extension_generic", "media_type_generic"}
GENERIC_FAMILIES = {
    "archive",
    "audio",
    "data",
    "document",
    "image",
    "text",
    "video",
    "other",
    "unknown",
}
REVIEW_STATUSES = {"unreviewed", "accepted", "rejected"}
NAME_REASON_CODES = (
    "malformed_percent_escape",
    "invalid_utf8",
    "utf8_bom_forbidden",
    "residual_percent_triplet",
    "path_separator_forbidden",
    "nul_forbidden",
    "c0_control_forbidden",
    "c1_control_forbidden",
    "del_forbidden",
    "bidi_control_forbidden",
    "unicode_separator_forbidden",
    "empty_filename_forbidden",
    "reserved_path_segment_forbidden",
    "derived_name_length_exceeded",
)
PRIVATE_BLOCK_REASONS = {
    "source_derivation_blocked",
    "no_eligible_label_candidate",
    "candidate_evidence_invalid",
    "private_value_forbidden_for_audience",
}
PUBLIC_BLOCK_REASONS = {
    "candidate_evidence_invalid",
    "generic_family_unavailable",
}
KIND_PRECEDENCE = {
    "human_reviewed_label": 1,
    "original_filename": 2,
    "decoded_filename": 3,
    "normalized_filename_nfc": 4,
    "extension_generic": 5,
    "media_type_generic": 5,
    "object_id_fallback": 6,
}
SEARCH_KEY_KINDS = {
    "filename_canonical_caseless",
    "filename_separator_folded",
    "stem_canonical_caseless",
    "stem_separator_folded",
    "extension_ascii_lower",
}

_NAMES_FIELDS = {
    "original_filename",
    "name_input_profile",
    "decode_status",
    "decoded_filename",
    "normalized_filename_nfc",
    "normalized_filename_nfd",
    "filename_stem_nfc",
    "extension_ascii_lower",
    "derivation_status",
    "reason_codes",
}
_MEDIA_FIELDS = {
    "value",
    "basis",
    "registered_status",
    "extension_agreement",
    "extension_comparison_evidence_sha256",
    "registry_evidence",
}
_PROVENANCE_FIELDS = {
    "source_system",
    "source_record_id",
    "source_attachment_id",
    "source_snapshot_sha256",
    "observation_evidence_sha256",
    "evidence_kind",
    "captured_at",
}
_CANDIDATE_FIELDS = {
    "kind",
    "value",
    "privacy_class",
    "evidence_sha256",
    "review_status",
    "review_evidence_sha256",
}
_PROFILE_FIELDS = {
    "id",
    "unicode_version",
    "confusables_data_sha256",
    "confusable_status",
}
_RECORD_FIELDS = {
    "schema",
    "privacy_class",
    "object_id",
    "names",
    "media_type",
    "size_bytes",
    "size_bytes_basis",
    "source_provenance",
    "label_candidates",
    "normalization_profile",
}
_PRIVATE_PROJECTION_FIELDS = {
    "schema",
    "object_id",
    "audience",
    "status",
    "selected_label",
    "selected_kind",
    "alternative_count",
    "ambiguity",
    "reason_codes",
    "privacy",
}
_PUBLIC_PROJECTION_FIELDS = {
    "schema",
    "object_id",
    "audience",
    "status",
    "generic_label",
    "alternative_count",
    "reason_codes",
    "privacy",
}
_PRIVACY_FIELDS = {
    "private_filename_exposed",
    "source_identifier_exposed",
    "local_path_exposed",
    "provider_locator_exposed",
    "secret_value_exposed",
}


def _accepted() -> dict[str, Any]:
    return {"accepted": True, "issue_codes": []}


def _rejected(code: str) -> dict[str, Any]:
    return {"accepted": False, "issue_codes": [code]}


def _projection_refusal(code: str) -> dict[str, Any]:
    return {"projection": None, "issue_codes": [code]}


def _has_unpaired_surrogate(value: str) -> bool:
    return any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def _contains_surrogate(value: Any) -> bool:
    pending = [value]
    visited_containers: set[int] = set()
    while pending:
        current = pending.pop()
        if type(current) is str:
            if _has_unpaired_surrogate(current):
                return True
            continue
        if type(current) not in {list, dict}:
            continue
        identity = id(current)
        if identity in visited_containers:
            continue
        visited_containers.add(identity)
        if type(current) is list:
            pending.extend(current)
            continue
        for key, item in current.items():
            pending.append(key)
            pending.append(item)
    return False


def _is_exact_digest(value: Any) -> bool:
    return type(value) is str and OBJECT_ID_PATTERN.fullmatch(value) is not None


def _is_enum_string(value: Any, allowed: set[str]) -> bool:
    return type(value) is str and value in allowed


def _is_string(
    value: Any,
    *,
    maximum: int,
    minimum: int = 0,
) -> bool:
    return type(value) is str and minimum <= len(value) <= maximum


def _is_optional_string(
    value: Any,
    *,
    maximum: int,
    minimum: int = 1,
) -> bool:
    return value is None or _is_string(value, maximum=maximum, minimum=minimum)


def _is_unique_list(values: list[Any]) -> bool:
    if not values:
        return True
    if all(type(value) is str for value in values):
        return len(set(values)) == len(values)
    if not all(type(value) is dict for value in values):
        return False

    seen: set[tuple[tuple[str, Any], ...]] = set()
    for value in values:
        if any(
            type(key) is not str
            or value_item is not None
            and type(value_item) is not str
            for key, value_item in value.items()
        ):
            return False
        identity = tuple(sorted(value.items()))
        if identity in seen:
            return False
        seen.add(identity)
    return True


def _is_rfc3339(value: str) -> bool:
    if len(value) > 64 or _has_unpaired_surrogate(value):
        return False
    matched = RFC3339_PATTERN.fullmatch(value)
    if matched is None:
        return False
    try:
        date(
            int(matched.group(1)),
            int(matched.group(2)),
            int(matched.group(3)),
        )
    except ValueError:
        return False
    return True


def is_valid_private_metadata_rfc3339(value: Any) -> bool:
    """Return the v0.1 RFC 3339 application-profile predicate."""

    return type(value) is str and _is_rfc3339(value)


def _unicode_profile_is_pinned() -> bool:
    return (
        UNICODE_VERSION == "17.0.0"
        and unicodedata2.unidata_version == "17.0.0"
    )


def _blocked_names(
    original_filename: str,
    name_input_profile: str,
    reason_codes: list[str],
) -> dict[str, Any]:
    decode_status = (
        "not_requested"
        if name_input_profile == "literal_unicode"
        else "blocked"
    )
    return {
        "original_filename": original_filename,
        "name_input_profile": name_input_profile,
        "decode_status": decode_status,
        "decoded_filename": None,
        "normalized_filename_nfc": None,
        "normalized_filename_nfd": None,
        "filename_stem_nfc": None,
        "extension_ascii_lower": None,
        "derivation_status": "blocked",
        "reason_codes": reason_codes,
    }


def _strict_percent_decode(value: str) -> tuple[str | None, str | None]:
    output = bytearray()
    index = 0
    while index < len(value):
        character = value[index]
        if character == "%":
            if index + 2 >= len(value):
                return None, "malformed_percent_escape"
            pair = value[index + 1 : index + 3]
            if (
                len(pair) != 2
                or any(digit not in "0123456789abcdefABCDEF" for digit in pair)
            ):
                return None, "malformed_percent_escape"
            output.append(int(pair, 16))
            index += 3
            continue
        output.extend(character.encode("utf-8"))
        index += 1
    if output.startswith(b"\xef\xbb\xbf"):
        return None, "utf8_bom_forbidden"
    try:
        return bytes(output).decode("utf-8", errors="strict"), None
    except UnicodeDecodeError:
        return None, "invalid_utf8"


def _filename_safety_reasons(
    value: str,
    *,
    include_residual_percent_triplet: bool,
) -> list[str]:
    found: set[str] = set()
    if (
        include_residual_percent_triplet
        and PERCENT_TRIPLET_PATTERN.search(value) is not None
    ):
        found.add("residual_percent_triplet")
    if "/" in value or "\\" in value:
        found.add("path_separator_forbidden")
    for character in value:
        code_point = ord(character)
        if code_point == 0:
            found.add("nul_forbidden")
        elif 0x0001 <= code_point <= 0x001F:
            found.add("c0_control_forbidden")
        elif code_point == 0x007F:
            found.add("del_forbidden")
        elif 0x0080 <= code_point <= 0x009F:
            found.add("c1_control_forbidden")
        if code_point in BIDI_CONTROL_CODE_POINTS:
            found.add("bidi_control_forbidden")
        if code_point in {0x2028, 0x2029}:
            found.add("unicode_separator_forbidden")
    if value == "":
        found.add("empty_filename_forbidden")
    if value in {".", ".."}:
        found.add("reserved_path_segment_forbidden")
    return [reason for reason in NAME_REASON_CODES if reason in found]


def _derive_stem_and_extension(value: str) -> tuple[str, str | None]:
    final_dot = value.rfind(".")
    if final_dot <= 0 or final_dot == len(value) - 1:
        return value, None
    suffix = value[final_dot + 1 :]
    if any(ord(character) > 0x7F for character in suffix):
        return value, None
    lowered = "".join(
        chr(ord(character) + 32)
        if "A" <= character <= "Z"
        else character
        for character in suffix
    )
    return value[:final_dot], lowered


def normalize_private_filename(
    original_filename: Any,
    name_input_profile: Any,
) -> dict[str, Any]:
    """Normalize one bounded private filename without external I/O."""

    if (
        type(original_filename) is not str
        or len(original_filename) > 512
        or type(name_input_profile) is not str
        or name_input_profile not in NAME_INPUT_PROFILES
    ):
        return {"names": None, "issue_codes": ["record_shape_invalid"]}
    if _has_unpaired_surrogate(original_filename):
        return {"names": None, "issue_codes": ["unpaired_surrogate_input"]}
    if not _unicode_profile_is_pinned():
        return {
            "names": None,
            "issue_codes": ["derived_field_invariant_invalid"],
        }

    if name_input_profile == "utf8_percent_encoded_component":
        decoded, decode_issue = _strict_percent_decode(original_filename)
        if decode_issue is not None:
            return {
                "names": _blocked_names(
                    original_filename,
                    name_input_profile,
                    [decode_issue],
                ),
                "issue_codes": [],
            }
        if decoded is None:
            return {
                "names": None,
                "issue_codes": ["derived_field_invariant_invalid"],
            }
        derivation_source = decoded
        include_residual = True
    else:
        decoded = None
        derivation_source = original_filename
        include_residual = False

    safety_reasons = _filename_safety_reasons(
        derivation_source,
        include_residual_percent_triplet=include_residual,
    )
    if safety_reasons:
        return {
            "names": _blocked_names(
                original_filename,
                name_input_profile,
                safety_reasons,
            ),
            "issue_codes": [],
        }

    normalized_nfc = unicodedata2.normalize("NFC", derivation_source)
    normalized_nfd = unicodedata2.normalize("NFD", derivation_source)
    if any(
        len(value) > 512
        for value in (derivation_source, normalized_nfc, normalized_nfd)
    ):
        return {
            "names": _blocked_names(
                original_filename,
                name_input_profile,
                ["derived_name_length_exceeded"],
            ),
            "issue_codes": [],
        }
    stem, extension = _derive_stem_and_extension(normalized_nfc)
    if len(stem) > 512:
        return {
            "names": _blocked_names(
                original_filename,
                name_input_profile,
                ["derived_name_length_exceeded"],
            ),
            "issue_codes": [],
        }
    return {
        "names": {
            "original_filename": original_filename,
            "name_input_profile": name_input_profile,
            "decode_status": (
                "not_requested"
                if name_input_profile == "literal_unicode"
                else "decoded"
            ),
            "decoded_filename": decoded,
            "normalized_filename_nfc": normalized_nfc,
            "normalized_filename_nfd": normalized_nfd,
            "filename_stem_nfc": stem,
            "extension_ascii_lower": extension,
            "derivation_status": "valid",
            "reason_codes": [],
        },
        "issue_codes": [],
    }


def _full_casefold_cf(value: str) -> str:
    folded: list[str] = []
    for character in value:
        code_point = ord(character)
        mapping = CASE_FOLDING_CF.get(code_point)
        if mapping is None:
            folded.append(character)
        else:
            folded.extend(chr(mapped) for mapped in mapping)
    return "".join(folded)


def _canonical_caseless(value: str) -> str:
    decomposed = unicodedata2.normalize("NFD", value)
    folded = _full_casefold_cf(decomposed)
    return unicodedata2.normalize("NFC", folded)


def _separator_fold(value: str) -> str:
    output: list[str] = []
    in_separator_run = False
    for character in value:
        is_separator = (
            ord(character) in EFFECTIVE_SEPARATOR_WHITESPACE_CODE_POINTS
            or character in {"_", "-"}
        )
        if is_separator:
            if output:
                in_separator_run = True
            continue
        if in_separator_run:
            output.append(" ")
            in_separator_run = False
        output.append(character)
    return "".join(output)


def _names_exactly_recompute(names: Any) -> tuple[bool, dict[str, Any] | None]:
    if type(names) is not dict or set(names) != _NAMES_FIELDS:
        return False, None
    original = names.get("original_filename")
    profile = names.get("name_input_profile")
    recomputed = normalize_private_filename(original, profile)
    if recomputed["issue_codes"]:
        return False, None
    expected = recomputed["names"]
    return expected == names, expected


def derive_filename_search_keys(names: Any) -> dict[str, Any]:
    """Derive deterministic Unicode-17 alias keys from validated names."""

    valid, expected = _names_exactly_recompute(names)
    if not valid or expected is None or not _unicode_profile_is_pinned():
        return {
            "search_keys": [],
            "issue_codes": ["derived_field_invariant_invalid"],
        }
    if expected["derivation_status"] == "blocked":
        return {"search_keys": [], "issue_codes": []}

    filename = expected["normalized_filename_nfc"]
    stem = expected["filename_stem_nfc"]
    extension = expected["extension_ascii_lower"]
    if type(filename) is not str or type(stem) is not str:
        return {
            "search_keys": [],
            "issue_codes": ["derived_field_invariant_invalid"],
        }

    filename_q = _canonical_caseless(filename)
    stem_q = _canonical_caseless(stem)
    candidates: list[tuple[str, str | None]] = [
        ("filename_canonical_caseless", filename_q),
        ("filename_separator_folded", _separator_fold(filename_q)),
        ("stem_canonical_caseless", stem_q),
        ("stem_separator_folded", _separator_fold(stem_q)),
        ("extension_ascii_lower", extension),
    ]
    emitted: list[dict[str, str]] = []
    seen_values: set[str] = set()
    for kind, value in candidates:
        if value is None or value == "" or value in seen_values:
            continue
        if len(value) > 2048:
            return {
                "search_keys": [],
                "issue_codes": ["derived_field_invariant_invalid"],
            }
        emitted.append({"kind": kind, "value": value})
        seen_values.add(value)
    return {"search_keys": emitted, "issue_codes": []}


def _names_basic_shape(names: Any) -> bool:
    if type(names) is not dict or set(names) != _NAMES_FIELDS:
        return False
    if not _is_string(names.get("original_filename"), maximum=512):
        return False
    if not _is_enum_string(
        names.get("name_input_profile"),
        NAME_INPUT_PROFILES,
    ):
        return False
    if not _is_enum_string(names.get("decode_status"), DECODE_STATUSES):
        return False
    if not _is_optional_string(names.get("decoded_filename"), maximum=4096):
        return False
    if not _is_optional_string(
        names.get("normalized_filename_nfc"), maximum=4096
    ):
        return False
    if not _is_optional_string(
        names.get("normalized_filename_nfd"), maximum=4096
    ):
        return False
    if not _is_optional_string(names.get("filename_stem_nfc"), maximum=4096):
        return False
    extension = names.get("extension_ascii_lower")
    if extension is not None and not _is_string(
        extension, maximum=4096, minimum=1
    ):
        return False
    if not _is_enum_string(
        names.get("derivation_status"),
        DERIVATION_STATUSES,
    ):
        return False
    reasons = names.get("reason_codes")
    return (
        type(reasons) is list
        and len(reasons) <= 16
        and all(type(reason) is str and reason in NAME_REASON_CODES for reason in reasons)
        and _is_unique_list(reasons)
    )


def _media_basic_shape(media: Any) -> bool:
    if type(media) is not dict or set(media) != _MEDIA_FIELDS:
        return False
    value = media.get("value")
    return (
        (value is None or _is_string(value, maximum=127, minimum=1))
        and _is_enum_string(
            media.get("basis"),
            {"unknown", "source_declared"},
        )
        and media.get("registered_status") == "not_checked"
        and media.get("registry_evidence") is None
        and media.get("extension_agreement") == "unknown"
        and media.get("extension_comparison_evidence_sha256") is None
    )


def _provenance_basic_shape(provenance: Any) -> bool:
    if type(provenance) is not dict or set(provenance) != _PROVENANCE_FIELDS:
        return False
    return (
        _is_string(provenance.get("source_system"), maximum=64, minimum=1)
        and _is_optional_string(
            provenance.get("source_record_id"), maximum=256, minimum=1
        )
        and _is_optional_string(
            provenance.get("source_attachment_id"), maximum=256, minimum=1
        )
        and _is_string(
            provenance.get("source_snapshot_sha256"), maximum=71, minimum=71
        )
        and _is_string(
            provenance.get("observation_evidence_sha256"),
            maximum=71,
            minimum=71,
        )
        and _is_enum_string(
            provenance.get("evidence_kind"),
            EVIDENCE_KINDS,
        )
        and (
            provenance.get("captured_at") is None
            or _is_string(provenance.get("captured_at"), maximum=64, minimum=1)
        )
    )


def _candidate_basic_shape(candidate: Any) -> bool:
    if type(candidate) is not dict or set(candidate) != _CANDIDATE_FIELDS:
        return False
    review_evidence = candidate.get("review_evidence_sha256")
    return (
        _is_enum_string(candidate.get("kind"), CANDIDATE_KINDS)
        and _is_string(candidate.get("value"), maximum=512, minimum=1)
        and _is_enum_string(
            candidate.get("privacy_class"),
            PRIVACY_CLASSES,
        )
        and _is_string(candidate.get("evidence_sha256"), maximum=71, minimum=71)
        and _is_enum_string(
            candidate.get("review_status"),
            REVIEW_STATUSES,
        )
        and (
            review_evidence is None
            or _is_string(review_evidence, maximum=71, minimum=71)
        )
    )


def _profile_basic_shape(profile: Any) -> bool:
    return (
        type(profile) is dict
        and set(profile) == _PROFILE_FIELDS
        and profile.get("id") == NORMALIZATION_PROFILE
        and profile.get("unicode_version") == "17.0.0"
        and profile.get("confusables_data_sha256") is None
        and profile.get("confusable_status") == "not_checked"
    )


def _record_basic_shape(record: Any) -> bool:
    if type(record) is not dict or set(record) != _RECORD_FIELDS:
        return False
    candidates = record.get("label_candidates")
    size = record.get("size_bytes")
    return (
        record.get("schema") == PRIVATE_METADATA_SCHEMA
        and _is_enum_string(record.get("privacy_class"), PRIVACY_CLASSES)
        and _is_string(record.get("object_id"), maximum=71, minimum=71)
        and _names_basic_shape(record.get("names"))
        and _media_basic_shape(record.get("media_type"))
        and (
            size is None
            or (type(size) is int and 0 <= size)
        )
        and _is_enum_string(
            record.get("size_bytes_basis"),
            {"unknown", "source_observed"},
        )
        and _provenance_basic_shape(record.get("source_provenance"))
        and type(candidates) is list
        and len(candidates) <= 64
        and all(_candidate_basic_shape(candidate) for candidate in candidates)
        and _is_unique_list(candidates)
        and _profile_basic_shape(record.get("normalization_profile"))
    )


def _record_self_contained_shape(record: dict[str, Any]) -> bool:
    if not _is_exact_digest(record["object_id"]):
        return False

    names = record["names"]
    reasons = names["reason_codes"]
    if names["derivation_status"] == "valid":
        if reasons:
            return False
        if (
            names["normalized_filename_nfc"] is None
            or names["normalized_filename_nfd"] is None
            or names["filename_stem_nfc"] is None
        ):
            return False
        if names["name_input_profile"] == "literal_unicode":
            if (
                names["decode_status"] != "not_requested"
                or names["decoded_filename"] is not None
            ):
                return False
        elif (
            names["decode_status"] != "decoded"
            or names["decoded_filename"] is None
        ):
            return False
    else:
        if not reasons:
            return False
        if any(
            names[field] is not None
            for field in (
                "decoded_filename",
                "normalized_filename_nfc",
                "normalized_filename_nfd",
                "filename_stem_nfc",
                "extension_ascii_lower",
            )
        ):
            return False
        expected_decode = (
            "not_requested"
            if names["name_input_profile"] == "literal_unicode"
            else "blocked"
        )
        if names["decode_status"] != expected_decode:
            return False

    media = record["media_type"]
    if media["basis"] == "unknown":
        if media["value"] is not None:
            return False
    elif (
        media["value"] is None
        or MEDIA_TYPE_PATTERN.fullmatch(media["value"]) is None
    ):
        return False

    size = record["size_bytes"]
    if record["size_bytes_basis"] == "unknown":
        if size is not None:
            return False
    elif type(size) is not int or size < 0:
        return False

    provenance = record["source_provenance"]
    if SOURCE_SYSTEM_PATTERN.fullmatch(provenance["source_system"]) is None:
        return False
    if not _is_exact_digest(provenance["source_snapshot_sha256"]):
        return False
    if not _is_exact_digest(provenance["observation_evidence_sha256"]):
        return False
    if provenance["evidence_kind"] == "source_record_field":
        if (
            provenance["source_record_id"] is None
            or provenance["source_attachment_id"] is not None
        ):
            return False
    elif provenance["evidence_kind"] == "source_attachment_metadata":
        if provenance["source_attachment_id"] is None:
            return False

    for candidate in record["label_candidates"]:
        if not _is_exact_digest(candidate["evidence_sha256"]):
            return False
        review_digest = candidate["review_evidence_sha256"]
        if review_digest is not None and not _is_exact_digest(review_digest):
            return False
        kind = candidate["kind"]
        if kind in GENERIC_CANDIDATE_KINDS:
            if candidate["value"] not in GENERIC_FAMILIES:
                return False
        elif kind == "object_id_fallback" and not _is_exact_digest(
            candidate["value"]
        ):
            return False
    return True


def _record_rfc3339_valid(record: dict[str, Any]) -> bool:
    captured_at = record["source_provenance"]["captured_at"]
    return captured_at is None or _is_rfc3339(captured_at)


def _candidate_semantics_valid(
    record: dict[str, Any],
    candidate: dict[str, Any],
) -> bool:
    review_status = candidate["review_status"]
    review_digest = candidate["review_evidence_sha256"]
    if (review_status == "unreviewed") != (review_digest is None):
        return False
    if review_status in {"accepted", "rejected"} and not _is_exact_digest(
        review_digest
    ):
        return False

    kind = candidate["kind"]
    value = candidate["value"]
    if kind in FILENAME_CANDIDATE_KINDS:
        if _filename_safety_reasons(
            value,
            include_residual_percent_triplet=False,
        ):
            return False
    names = record["names"]
    if kind == "human_reviewed_label":
        return review_status == "accepted" and review_digest is not None
    if kind == "original_filename":
        return (
            names["derivation_status"] == "valid"
            and value == names["original_filename"]
        )
    if kind == "decoded_filename":
        return (
            names["derivation_status"] == "valid"
            and names["decode_status"] == "decoded"
            and names["decoded_filename"] is not None
            and value == names["decoded_filename"]
        )
    if kind == "normalized_filename_nfc":
        return (
            names["derivation_status"] == "valid"
            and names["normalized_filename_nfc"] is not None
            and value == names["normalized_filename_nfc"]
        )
    if kind in GENERIC_CANDIDATE_KINDS:
        return value in GENERIC_FAMILIES
    if kind == "object_id_fallback":
        return value == record["object_id"]
    return False


def _all_candidate_semantics_valid(record: dict[str, Any]) -> bool:
    return all(
        _candidate_semantics_valid(record, candidate)
        for candidate in record["label_candidates"]
    )


def _record_privacy_valid(record: dict[str, Any]) -> bool:
    return not (
        record["privacy_class"] == "restricted"
        and any(
            candidate["privacy_class"] != "restricted"
            for candidate in record["label_candidates"]
        )
    )


def _record_derived_fields_valid(record: dict[str, Any]) -> bool:
    valid, _ = _names_exactly_recompute(record["names"])
    return valid


def validate_private_metadata_record(record: Any) -> dict[str, Any]:
    """Validate one private metadata record in the fixed issue-code order."""

    if not _record_basic_shape(record):
        return _rejected("record_shape_invalid")
    if _contains_surrogate(record):
        return _rejected("unpaired_surrogate_input")
    if not _record_self_contained_shape(record):
        return _rejected("record_shape_invalid")
    if not _record_rfc3339_valid(record):
        return _rejected("invalid_rfc3339")
    if not _record_derived_fields_valid(record):
        return _rejected("derived_field_invariant_invalid")
    if not _all_candidate_semantics_valid(record):
        return _rejected("candidate_invariant_invalid")
    if not _record_privacy_valid(record):
        return _rejected("privacy_invariant_invalid")
    return _accepted()


def _privacy_projection(private_filename_exposed: bool) -> dict[str, bool]:
    return {
        "private_filename_exposed": private_filename_exposed,
        "source_identifier_exposed": False,
        "local_path_exposed": False,
        "provider_locator_exposed": False,
        "secret_value_exposed": False,
    }


def _private_blocked_projection(
    object_id: str,
    audience: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "schema": SAFE_LABEL_SCHEMA,
        "object_id": object_id,
        "audience": audience,
        "status": "blocked",
        "selected_label": None,
        "selected_kind": None,
        "alternative_count": 0,
        "ambiguity": {"state": "none"},
        "reason_codes": [reason],
        "privacy": _privacy_projection(False),
    }


def _public_blocked_projection(
    object_id: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "schema": SAFE_LABEL_SCHEMA,
        "object_id": object_id,
        "audience": "public_generic",
        "status": "blocked",
        "generic_label": None,
        "alternative_count": 0,
        "reason_codes": [reason],
        "privacy": _privacy_projection(False),
    }


def _candidate_identity(candidate: dict[str, Any]) -> tuple[Any, ...]:
    return (
        candidate["kind"],
        candidate["value"],
        candidate["privacy_class"],
        candidate["evidence_sha256"],
        candidate["review_status"],
        candidate["review_evidence_sha256"],
    )


def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[Any, ...]:
    return (
        KIND_PRECEDENCE[candidate["kind"]],
        candidate["value"].encode("utf-8"),
        candidate["kind"].encode("ascii"),
        candidate["privacy_class"].encode("ascii"),
        candidate["evidence_sha256"].encode("ascii"),
        candidate["review_status"].encode("ascii"),
        (candidate["review_evidence_sha256"] or "").encode("ascii"),
    )


def _deduplicated_candidates(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_identity: dict[tuple[Any, ...], dict[str, Any]] = {}
    for record in records:
        for candidate in record["label_candidates"]:
            identity = _candidate_identity(candidate)
            if identity not in by_identity:
                by_identity[identity] = candidate
    return sorted(by_identity.values(), key=_candidate_sort_key)


def _project_private(
    records: list[dict[str, Any]],
    audience: str,
    object_id: str,
) -> dict[str, Any]:
    candidates = _deduplicated_candidates(records)
    eligible: list[dict[str, Any]] = []
    audience_ineligible = False
    for candidate in candidates:
        if candidate["review_status"] == "rejected":
            continue
        if (
            audience == "restricted"
            and candidate["privacy_class"] != "restricted"
        ):
            audience_ineligible = True
            continue
        eligible.append(candidate)

    if not eligible:
        if audience_ineligible:
            reason = "private_value_forbidden_for_audience"
        elif any(
            record["names"]["derivation_status"] == "blocked"
            for record in records
        ):
            reason = "source_derivation_blocked"
        else:
            reason = "no_eligible_label_candidate"
        return _private_blocked_projection(object_id, audience, reason)

    groups: dict[str, list[dict[str, Any]]] = {}
    for candidate in eligible:
        groups.setdefault(candidate["value"], []).append(candidate)
    group_ranks = {
        value: min(KIND_PRECEDENCE[row["kind"]] for row in rows)
        for value, rows in groups.items()
    }
    highest_rank = min(group_ranks.values())
    tied_values = sorted(
        (
            value
            for value, rank in group_ranks.items()
            if rank == highest_rank
        ),
        key=lambda value: value.encode("utf-8"),
    )
    if len(tied_values) > 1:
        return {
            "schema": SAFE_LABEL_SCHEMA,
            "object_id": object_id,
            "audience": audience,
            "status": "ambiguous",
            "selected_label": None,
            "selected_kind": None,
            "alternative_count": len(tied_values),
            "ambiguity": {"state": "multiple_labels_for_object"},
            "reason_codes": ["multiple_labels_for_object"],
            "privacy": _privacy_projection(False),
        }

    selected_value = tied_values[0]
    selected_rows = [
        row
        for row in groups[selected_value]
        if KIND_PRECEDENCE[row["kind"]] == highest_rank
    ]
    selected_row = min(selected_rows, key=_candidate_sort_key)
    selected_kind = selected_row["kind"]
    return {
        "schema": SAFE_LABEL_SCHEMA,
        "object_id": object_id,
        "audience": audience,
        "status": "selected",
        "selected_label": selected_value,
        "selected_kind": selected_kind,
        "alternative_count": len(groups) - 1,
        "ambiguity": {"state": "none"},
        "reason_codes": [],
        "privacy": _privacy_projection(
            selected_kind in FILENAME_CANDIDATE_KINDS
        ),
    }


def _project_public(
    records: list[dict[str, Any]],
    object_id: str,
) -> dict[str, Any]:
    families = sorted(
        {
            candidate["value"]
            for candidate in _deduplicated_candidates(records)
            if candidate["kind"] in GENERIC_CANDIDATE_KINDS
            and candidate["review_status"] != "rejected"
        }
    )
    if len(families) != 1:
        return _public_blocked_projection(
            object_id,
            "generic_family_unavailable",
        )
    return {
        "schema": SAFE_LABEL_SCHEMA,
        "object_id": object_id,
        "audience": "public_generic",
        "status": "generic_only",
        "generic_label": {"generic_family": families[0]},
        "alternative_count": 0,
        "reason_codes": [],
        "privacy": _privacy_projection(False),
    }


def project_objet_safe_label(
    validated_records: Any,
    audience: Any,
    object_id_disclosure_permitted: Any,
) -> dict[str, Any]:
    """Project a private/restricted label or a closed public generic family."""

    if (
        type(audience) is not str
        or audience not in AUDIENCES
        or type(object_id_disclosure_permitted) is not bool
    ):
        return _projection_refusal("projection_shape_invalid")
    if (
        type(validated_records) is not list
        or not validated_records
        or len(validated_records) > 64
    ):
        return _projection_refusal("record_shape_invalid")

    records: list[dict[str, Any]] = []
    total_candidates = 0
    for raw_record in validated_records:
        if not _record_basic_shape(raw_record):
            return _projection_refusal("record_shape_invalid")
        if (
            _contains_surrogate(raw_record)
            or not _record_self_contained_shape(raw_record)
            or not _record_rfc3339_valid(raw_record)
            or not _record_derived_fields_valid(raw_record)
            or not _record_privacy_valid(raw_record)
        ):
            return _projection_refusal("record_shape_invalid")
        total_candidates += len(raw_record["label_candidates"])
        if total_candidates > 256:
            return _projection_refusal("record_shape_invalid")
        records.append(raw_record)

    object_id = records[0]["object_id"]
    if any(record["object_id"] != object_id for record in records[1:]):
        return _projection_refusal("record_shape_invalid")
    if not object_id_disclosure_permitted:
        return _projection_refusal("privacy_invariant_invalid")
    if any(not _all_candidate_semantics_valid(record) for record in records):
        if audience == "public_generic":
            projection = _public_blocked_projection(
                object_id,
                "candidate_evidence_invalid",
            )
        else:
            projection = _private_blocked_projection(
                object_id,
                audience,
                "candidate_evidence_invalid",
            )
        return {"projection": projection, "issue_codes": []}

    if audience == "public_generic":
        projection = _project_public(records, object_id)
    else:
        projection = _project_private(records, audience, object_id)
    return {"projection": projection, "issue_codes": []}


def _privacy_object_shape(value: Any) -> bool:
    return (
        type(value) is dict
        and set(value) == _PRIVACY_FIELDS
        and all(type(item) is bool for item in value.values())
        and value["source_identifier_exposed"] is False
        and value["local_path_exposed"] is False
        and value["provider_locator_exposed"] is False
        and value["secret_value_exposed"] is False
    )


def _private_projection_shape(value: dict[str, Any]) -> bool:
    if set(value) != _PRIVATE_PROJECTION_FIELDS:
        return False
    if (
        value.get("schema") != SAFE_LABEL_SCHEMA
        or not _is_enum_string(
            value.get("audience"),
            {"private_archive", "restricted"},
        )
        or not _is_exact_digest(value.get("object_id"))
        or not _is_enum_string(
            value.get("status"),
            {"selected", "ambiguous", "blocked"},
        )
        or type(value.get("alternative_count")) is not int
        or not 0 <= value["alternative_count"] <= 256
        or not _privacy_object_shape(value.get("privacy"))
    ):
        return False
    ambiguity = value.get("ambiguity")
    if (
        type(ambiguity) is not dict
        or set(ambiguity) != {"state"}
        or not _is_enum_string(
            ambiguity.get("state"),
            {"none", "multiple_labels_for_object"},
        )
    ):
        return False
    reasons = value.get("reason_codes")
    if (
        type(reasons) is not list
        or len(reasons) > 16
        or not _is_unique_list(reasons)
    ):
        return False

    status = value["status"]
    if status == "selected":
        kind = value.get("selected_kind")
        expected_private = _is_enum_string(kind, FILENAME_CANDIDATE_KINDS)
        return (
            _is_string(value.get("selected_label"), maximum=512, minimum=1)
            and _is_enum_string(kind, CANDIDATE_KINDS)
            and ambiguity["state"] == "none"
            and reasons == []
            and value["privacy"]["private_filename_exposed"]
            is expected_private
        )
    if status == "ambiguous":
        return (
            value.get("selected_label") is None
            and value.get("selected_kind") is None
            and value["alternative_count"] >= 2
            and ambiguity["state"] == "multiple_labels_for_object"
            and reasons == ["multiple_labels_for_object"]
            and value["privacy"]["private_filename_exposed"] is False
        )
    return (
        value.get("selected_label") is None
        and value.get("selected_kind") is None
        and value["alternative_count"] == 0
        and ambiguity["state"] == "none"
        and 1 <= len(reasons) <= 16
        and all(
            _is_enum_string(reason, PRIVATE_BLOCK_REASONS)
            for reason in reasons
        )
        and value["privacy"]["private_filename_exposed"] is False
    )


def _public_projection_shape(value: dict[str, Any]) -> bool:
    if set(value) != _PUBLIC_PROJECTION_FIELDS:
        return False
    if (
        value.get("schema") != SAFE_LABEL_SCHEMA
        or value.get("audience") != "public_generic"
        or not _is_exact_digest(value.get("object_id"))
        or not _is_enum_string(
            value.get("status"),
            {"generic_only", "blocked"},
        )
        or type(value.get("alternative_count")) is not int
        or value.get("alternative_count") != 0
        or not _privacy_object_shape(value.get("privacy"))
        or value["privacy"]["private_filename_exposed"] is not False
    ):
        return False
    reasons = value.get("reason_codes")
    if type(reasons) is not list or not _is_unique_list(reasons):
        return False
    if value["status"] == "generic_only":
        generic = value.get("generic_label")
        return (
            type(generic) is dict
            and set(generic) == {"generic_family"}
            and _is_enum_string(
                generic.get("generic_family"),
                GENERIC_FAMILIES,
            )
            and reasons == []
        )
    return (
        value.get("generic_label") is None
        and 1 <= len(reasons) <= 16
        and all(
            _is_enum_string(reason, PUBLIC_BLOCK_REASONS)
            for reason in reasons
        )
    )


def validate_objet_safe_label_projection(value: Any) -> dict[str, Any]:
    """Validate one serialized safe-label projection without context claims."""

    if type(value) is not dict:
        return _rejected("projection_shape_invalid")
    if _contains_surrogate(value):
        return _rejected("unpaired_surrogate_input")
    audience = value.get("audience")
    if type(audience) is str and audience in {
        "private_archive",
        "restricted",
    }:
        valid = _private_projection_shape(value)
    elif audience == "public_generic":
        valid = _public_projection_shape(value)
    else:
        valid = False
    return _accepted() if valid else _rejected("projection_shape_invalid")


def resolve_label_ambiguity(matched_records: Any) -> dict[str, Any]:
    """Resolve only a bounded, pre-evidenced alias-to-object match set."""

    invalid_result = {
        "status": "blocked",
        "selected_object_id": None,
        "object_ids": [],
        "match_count": 0,
        "reason_codes": ["candidate_evidence_invalid"],
    }
    if type(matched_records) is not list or len(matched_records) > 256:
        return invalid_result
    object_ids: set[str] = set()
    for item in matched_records:
        if (
            type(item) is not dict
            or set(item) != {"object_id", "match_evidence_sha256"}
            or not _is_exact_digest(item.get("object_id"))
            or not _is_exact_digest(item.get("match_evidence_sha256"))
        ):
            return invalid_result
        object_ids.add(item["object_id"])
    ordered = sorted(object_ids, key=lambda value: value.encode("ascii"))
    if not ordered:
        return {
            "status": "blocked",
            "selected_object_id": None,
            "object_ids": [],
            "match_count": 0,
            "reason_codes": ["no_eligible_label_candidate"],
        }
    if len(ordered) == 1:
        return {
            "status": "unique_object",
            "selected_object_id": ordered[0],
            "object_ids": ordered,
            "match_count": 1,
            "reason_codes": [],
        }
    return {
        "status": "ambiguous",
        "selected_object_id": None,
        "object_ids": ordered,
        "match_count": len(ordered),
        "reason_codes": ["alias_matches_multiple_objects"],
    }
