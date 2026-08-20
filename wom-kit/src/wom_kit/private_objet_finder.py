"""Private, exact-indexed, read-only objet finder for v0.3.298.

The caller's query is ephemeral.  It is normalized in memory, used only as a
bound SQLite value inside the opaque v0.3.297 read session, and never reflected
in a result or diagnostic.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any, BinaryIO, TextIO

from . import archive_services
from . import private_objet_metadata_index_health as private_health
from .private_objet_metadata import (
    NAME_REASON_CODES,
    PERCENT_TRIPLET_PATTERN,
    _strict_percent_decode,
    derive_filename_search_keys,
    normalize_private_filename,
    validate_objet_safe_label_projection,
)
from .private_objet_metadata_index import (
    GENERATED_SCHEMA_ID,
    NORMALIZATION_PROFILE_ID,
    PROJECTION_SCHEMA_ID,
    canonical_json_bytes,
    sha256_digest,
)
from .private_objet_metadata_index_authority import (
    _is_reparse,
    _stat_identity,
)
from .private_objet_metadata_index_session import (
    PRIVATE_HEALTH_KEYS,
    _PrivateObjetIndexReadAPI,
    PrivateObjetIndexSessionError,
    PrivateObjetMetadataHealthDecision,
    validate_private_objet_metadata_health_envelope,
)


REQUEST_SCHEMA_ID = "wom-kit/private-objet-finder-request/v0.1"
RESULT_SCHEMA_ID = "wom-kit/private-objet-finder-result/v0.1"
SEARCH_METHOD = "exact_indexed_alias_key_v1"
AUDIENCE = "private_archive"
DEFAULT_LIMIT = 20
MAX_LIMIT = 100
MAX_RAW_QUERY_SCALARS = 6144
MAX_RAW_QUERY_BYTES = 6144
MAX_LOGICAL_QUERY_SCALARS = 512
MAX_LOGICAL_QUERY_BYTES = 2048
MAX_STDIN_READ_BYTES = 6147

ROOT_KEYS = (
    "schema",
    "ok",
    "status",
    "audience",
    "search_method",
    "query_present",
    "query_profile_validated",
    "limit",
    "checked_layers",
    "incomplete_layers",
    "private_health_case",
    "private_health",
    "distinct_object_count",
    "count_exact",
    "count_lower_bound",
    "returned",
    "has_more",
    "results",
    "diagnostic_codes",
    "blockers",
    "warnings",
    "privacy",
)
RESULT_ITEM_KEYS = (
    "object_id",
    "safe_label",
    "matched_alias_kinds",
    "matched_alias_count",
    "evidence",
)
EVIDENCE_KEYS = (
    "generated_schema_id",
    "normalization_profile_id",
    "projection_schema_id",
    "observation_count",
    "candidate_count",
)
PRIVACY_KEYS = (
    "wom_request_value_reflected",
    "wom_request_value_stored",
    "stored_private_projection_exposed",
    "source_identifier_exposed",
    "local_path_exposed",
    "provider_locator_exposed",
    "secret_value_exposed",
    "argv_query_exposure_possible",
)
LAYERS = (
    "request",
    "archive_boundary",
    "private_authority",
    "private_generated_index",
    "private_alias_index",
    "private_label_projection",
)
STATUSES = (
    "blocked",
    "search_incomplete",
    "not_found_in_index",
    "found",
    "ambiguous",
)
ALIAS_KINDS = (
    "filename_canonical_caseless",
    "filename_separator_folded",
    "stem_canonical_caseless",
    "stem_separator_folded",
    "extension_ascii_lower",
)
ALIAS_KIND_SET = frozenset(ALIAS_KINDS)
QUERY_PROFILES = frozenset(
    {"literal_unicode", "utf8_percent_encoded_component"}
)
FORMATS = frozenset({"json", "text"})
KNOWN_OPTIONS = frozenset(
    {
        "--audience",
        "--query-profile",
        "--query",
        "--query-stdin",
        "--limit",
        "--format",
    }
)
VALUE_OPTIONS = KNOWN_OPTIONS - {"--query-stdin"}

REQUEST_BLOCKER_CODES = (
    "find_objet_archive_root_missing",
    "find_objet_archive_root_extra",
    "find_objet_unexpected_positional",
    "find_objet_unknown_option",
    "find_objet_option_value_missing",
    "find_objet_audience_missing",
    "find_objet_audience_duplicate",
    "find_objet_audience_unsupported",
    "find_objet_query_profile_missing",
    "find_objet_query_profile_duplicate",
    "find_objet_query_profile_unsupported",
    "find_objet_query_transport_missing",
    "find_objet_query_transport_conflicting",
    "find_objet_query_transport_duplicate",
    "find_objet_limit_duplicate",
    "find_objet_limit_invalid",
    "find_objet_format_duplicate",
    "find_objet_format_unsupported",
    "find_objet_request_schema_unsupported",
    "find_objet_request_type_invalid",
    "find_objet_request_extra_property",
    "find_objet_query_raw_scalar_limit_exceeded",
    "find_objet_query_raw_utf8_limit_exceeded",
    "find_objet_query_stdin_bom_forbidden",
    "find_objet_query_stdin_second_line_forbidden",
    "find_objet_query_stdin_read_failed",
    "find_objet_query_unpaired_surrogate",
    "find_objet_query_utf8_bom_forbidden",
    "find_objet_query_malformed_percent_escape",
    "find_objet_query_invalid_utf8",
    "find_objet_query_residual_percent_triplet",
    "find_objet_query_path_separator_forbidden",
    "find_objet_query_nul_forbidden",
    "find_objet_query_c0_control_forbidden",
    "find_objet_query_c1_control_forbidden",
    "find_objet_query_del_forbidden",
    "find_objet_query_bidi_control_forbidden",
    "find_objet_query_unicode_separator_forbidden",
    "find_objet_query_empty_forbidden",
    "find_objet_query_reserved_path_segment_forbidden",
    "find_objet_query_logical_scalar_limit_exceeded",
    "find_objet_query_logical_utf8_limit_exceeded",
    "find_objet_query_derived_name_length_exceeded",
    "find_objet_query_derived_invariant_invalid",
)
REQUEST_BLOCKER_SET = frozenset(REQUEST_BLOCKER_CODES)
ARCHIVE_BOUNDARY_BLOCKER_CODE = "find_objet_archive_boundary_unsafe"
SERIALIZATION_BLOCKER_CODE = "find_objet_result_serialization_failed"

WARNING_ORDER = (
    "find_objet_argv_query_exposure_possible",
    "find_objet_private_projection_exposed",
    "find_objet_ambiguous_no_winner",
    "find_objet_negative_scope_limited",
)
OBJECT_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ASCII_LIMIT_RE = re.compile(r"^(?:[1-9]|[1-9][0-9]|100)$", re.ASCII)
HELP_TEXT = (
    "usage: archive find-objet <archive-root> "
    "--audience private_archive "
    "--query-profile literal_unicode|utf8_percent_encoded_component "
    "(--query <value> | --query-stdin) "
    "[--limit <1..100>] [--format json|text]\n"
    "options:\n"
    "  -h, --help\n"
    "  --audience private_archive\n"
    "  --query-profile literal_unicode|utf8_percent_encoded_component\n"
    "  --query <value>\n"
    "  --query-stdin\n"
    "  --limit <1..100>\n"
    "  --format json|text"
)
TEXT_HEADERS = {
    "blocked": "BLOCKED",
    "search_incomplete": "SEARCH INCOMPLETE",
    "not_found_in_index": "NOT FOUND IN COMPLETE CURRENT PRIVATE INDEX",
    "found": "FOUND",
    "ambiguous": "AMBIGUOUS",
}

NAME_REASON_TO_BLOCKER = {
    "malformed_percent_escape": "find_objet_query_malformed_percent_escape",
    "invalid_utf8": "find_objet_query_invalid_utf8",
    "utf8_bom_forbidden": "find_objet_query_utf8_bom_forbidden",
    "residual_percent_triplet": "find_objet_query_residual_percent_triplet",
    "path_separator_forbidden": "find_objet_query_path_separator_forbidden",
    "nul_forbidden": "find_objet_query_nul_forbidden",
    "c0_control_forbidden": "find_objet_query_c0_control_forbidden",
    "c1_control_forbidden": "find_objet_query_c1_control_forbidden",
    "del_forbidden": "find_objet_query_del_forbidden",
    "bidi_control_forbidden": "find_objet_query_bidi_control_forbidden",
    "unicode_separator_forbidden": (
        "find_objet_query_unicode_separator_forbidden"
    ),
    "empty_filename_forbidden": "find_objet_query_empty_forbidden",
    "reserved_path_segment_forbidden": (
        "find_objet_query_reserved_path_segment_forbidden"
    ),
    "derived_name_length_exceeded": (
        "find_objet_query_derived_name_length_exceeded"
    ),
}

CASE_DIAGNOSTICS = {
    "C1": ("private_objet_metadata_snapshot_changed",),
    "C2": ("private_objet_metadata_projection_unavailable",),
    "C3": ("private_objet_metadata_authority_blocked",),
    "C4": ("private_objet_metadata_authority_invalid",),
    "C5": ("find_objet_private_index_database_absent",),
    "C6": ("private_objet_metadata_projection_unavailable",),
    "C7": ("private_objet_metadata_projection_invalid",),
    "C8": ("private_objet_metadata_missing",),
    "C9": ("private_objet_metadata_stale",),
    "C10": ("find_objet_exact_match_not_found",),
}
CASE_BLOCKERS = {
    "C3": ("private_objet_metadata_authority_blocked",),
    "C4": ("private_objet_metadata_authority_invalid",),
    "C7": ("private_objet_metadata_projection_invalid",),
}
CASE_STATUS = {
    "C1": "search_incomplete",
    "C2": "search_incomplete",
    "C3": "blocked",
    "C4": "blocked",
    "C5": "search_incomplete",
    "C6": "search_incomplete",
    "C7": "blocked",
    "C8": "search_incomplete",
    "C9": "search_incomplete",
    "C10": "not_found_in_index",
}
CASE_LAYERS = {
    "C1": (LAYERS[:4], ("private_authority", "private_generated_index")),
    "C2": (LAYERS[:4], ("private_generated_index",)),
    "C3": (LAYERS[:3], ()),
    "C4": (LAYERS[:3], ()),
    "C5": (LAYERS[:4], ("private_generated_index",)),
    "C6": (LAYERS[:4], ("private_generated_index",)),
    "C8": (LAYERS[:4], ("private_generated_index",)),
    "C9": (LAYERS[:4], ("private_generated_index",)),
    "C10": (LAYERS, ()),
    "C11": (LAYERS, ()),
}

FALLBACK_JSON_LITERAL = (
    '{"schema":"wom-kit/private-objet-finder-result/v0.1",'
    '"ok":false,"status":"blocked","audience":"private_archive",'
    '"search_method":"exact_indexed_alias_key_v1","query_present":false,'
    '"query_profile_validated":false,"limit":20,'
    '"checked_layers":["request"],"incomplete_layers":[],'
    '"private_health_case":null,"private_health":null,'
    '"distinct_object_count":null,"count_exact":false,'
    '"count_lower_bound":null,"returned":0,"has_more":false,'
    '"results":[],"diagnostic_codes":'
    '["find_objet_result_serialization_failed"],'
    '"blockers":["find_objet_result_serialization_failed"],'
    '"warnings":["find_objet_argv_query_exposure_possible"],'
    '"privacy":{"wom_request_value_reflected":false,'
    '"wom_request_value_stored":false,'
    '"stored_private_projection_exposed":false,'
    '"source_identifier_exposed":false,"local_path_exposed":false,'
    '"provider_locator_exposed":false,"secret_value_exposed":false,'
    '"argv_query_exposure_possible":true}}'
)
FALLBACK_TEXT_LITERAL = (
    "BLOCKED\n"
    "diagnostic_codes=find_objet_result_serialization_failed\n"
    "blockers=find_objet_result_serialization_failed\n"
    "warnings=find_objet_argv_query_exposure_possible"
)


@dataclass(repr=False)
class _ParsedInvocation:
    help_requested: bool = False
    archive_root: str | None = field(default=None, repr=False)
    values: dict[str, list[str]] = field(default_factory=dict, repr=False)
    stdin_count: int = 0
    query_value_missing: bool = False
    failures: dict[int, set[str]] = field(default_factory=dict)
    argv_exposure_possible: bool = False
    selected_limit: int = DEFAULT_LIMIT
    selected_format: str = "text"

    def add_failure(self, phase: int, code: str) -> None:
        self.failures.setdefault(phase, set()).add(code)

    @property
    def first_failure(self) -> str | None:
        if not self.failures:
            return None
        codes = self.failures[min(self.failures)]
        return next(code for code in REQUEST_BLOCKER_CODES if code in codes)


@dataclass(frozen=True, repr=False)
class _QueryPlan:
    values: tuple[str, ...] = field(repr=False)


@dataclass(frozen=True)
class _LookupOutcome:
    distinct_object_count: int | None
    count_exact: bool
    count_lower_bound: int
    has_more: bool
    results: tuple[dict[str, object], ...]


class _BoundaryError(RuntimeError):
    pass


def _is_dash_token(value: str) -> bool:
    return value.startswith("-")


def _query_exposure(argv: Sequence[str]) -> bool:
    for index, token in enumerate(argv):
        if token.startswith("--query="):
            return True
        if (
            token == "--query"
            and index + 1 < len(argv)
            and not _is_dash_token(argv[index + 1])
        ):
            return True
    return False


def _scan_invocation(argv: Sequence[str]) -> _ParsedInvocation:
    parsed = _ParsedInvocation()
    parsed.values = {option: [] for option in VALUE_OPTIONS}
    parsed.help_requested = any(token in {"-h", "--help"} for token in argv)
    parsed.argv_exposure_possible = _query_exposure(argv)
    if parsed.help_requested:
        return parsed

    if not argv or _is_dash_token(argv[0]):
        parsed.add_failure(1, "find_objet_archive_root_missing")
        index = 0
    else:
        parsed.archive_root = argv[0]
        index = 1

    option_scanning = False
    while index < len(argv):
        token = argv[index]
        if token in KNOWN_OPTIONS:
            option_scanning = True
            if token == "--query-stdin":
                parsed.stdin_count += 1
                index += 1
                continue
            if index + 1 >= len(argv) or _is_dash_token(argv[index + 1]):
                if token == "--query":
                    parsed.query_value_missing = True
                parsed.add_failure(
                    5,
                    "find_objet_option_value_missing",
                )
                if index + 1 < len(argv) and argv[index + 1] not in KNOWN_OPTIONS:
                    parsed.add_failure(4, "find_objet_unknown_option")
                index += 1
                continue
            parsed.values[token].append(argv[index + 1])
            index += 2
            continue
        if _is_dash_token(token):
            option_scanning = True
            parsed.add_failure(4, "find_objet_unknown_option")
            index += 1
            continue
        parsed.add_failure(
            3 if option_scanning else 2,
            (
                "find_objet_unexpected_positional"
                if option_scanning
                else "find_objet_archive_root_extra"
            ),
        )
        index += 1

    _scan_phase_six(parsed)
    return parsed


def _scan_phase_six(parsed: _ParsedInvocation) -> None:
    audience_values = parsed.values["--audience"]
    if not audience_values:
        parsed.add_failure(6, "find_objet_audience_missing")
    if len(audience_values) > 1:
        parsed.add_failure(6, "find_objet_audience_duplicate")
    if len(audience_values) == 1 and audience_values[0] != AUDIENCE:
        parsed.add_failure(6, "find_objet_audience_unsupported")

    profile_values = parsed.values["--query-profile"]
    if not profile_values:
        parsed.add_failure(6, "find_objet_query_profile_missing")
    if len(profile_values) > 1:
        parsed.add_failure(6, "find_objet_query_profile_duplicate")
    if len(profile_values) == 1 and profile_values[0] not in QUERY_PROFILES:
        parsed.add_failure(6, "find_objet_query_profile_unsupported")

    query_count = len(parsed.values["--query"])
    if query_count == 0 and parsed.stdin_count == 0:
        parsed.add_failure(6, "find_objet_query_transport_missing")
    if query_count and parsed.stdin_count:
        parsed.add_failure(6, "find_objet_query_transport_conflicting")
    if query_count > 1 or parsed.stdin_count > 1:
        parsed.add_failure(6, "find_objet_query_transport_duplicate")

    limit_values = parsed.values["--limit"]
    if len(limit_values) > 1:
        parsed.add_failure(6, "find_objet_limit_duplicate")
    if len(limit_values) == 1:
        value = limit_values[0]
        if ASCII_LIMIT_RE.fullmatch(value) is None:
            parsed.add_failure(6, "find_objet_limit_invalid")
        else:
            parsed.selected_limit = int(value)

    format_values = parsed.values["--format"]
    if len(format_values) > 1:
        parsed.add_failure(6, "find_objet_format_duplicate")
    if len(format_values) == 1:
        value = format_values[0]
        if value not in FORMATS:
            parsed.add_failure(6, "find_objet_format_unsupported")
        else:
            parsed.selected_format = value

    if len(limit_values) != 1 or (
        limit_values and ASCII_LIMIT_RE.fullmatch(limit_values[0]) is None
    ):
        parsed.selected_limit = DEFAULT_LIMIT
    if len(format_values) != 1 or (
        format_values and format_values[0] not in FORMATS
    ):
        parsed.selected_format = "text"


def _has_unpaired_surrogate(value: str) -> bool:
    return any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def validate_private_objet_finder_request(value: object) -> str | None:
    """Return one closed request-shape blocker, or ``None`` when accepted."""

    if type(value) is not dict:
        return "find_objet_request_type_invalid"
    expected_keys = {
        "schema",
        "archive_root",
        "audience",
        "query_profile",
        "query_transport",
        "query",
        "limit",
        "format",
    }
    if (
        "schema" in value
        and value.get("schema") != REQUEST_SCHEMA_ID
    ):
        return "find_objet_request_schema_unsupported"
    if not expected_keys.issubset(value):
        return "find_objet_request_type_invalid"
    archive_root = value.get("archive_root")
    audience = value.get("audience")
    query_profile = value.get("query_profile")
    query_transport = value.get("query_transport")
    query = value.get("query")
    limit = value.get("limit")
    output_format = value.get("format")
    if (
        type(archive_root) is not str
        or not 1 <= len(archive_root) <= 4096
        or type(audience) is not str
        or audience != AUDIENCE
        or type(query_profile) is not str
        or query_profile not in QUERY_PROFILES
        or type(query_transport) is not str
        or query_transport not in {"argv", "stdin"}
        or type(query) is not str
        or len(query) > MAX_RAW_QUERY_SCALARS
        or type(limit) is not int
        or not 1 <= limit <= MAX_LIMIT
        or type(output_format) is not str
        or output_format not in FORMATS
    ):
        return "find_objet_request_type_invalid"
    if set(value) - expected_keys:
        return "find_objet_request_extra_property"
    return None


def _read_stdin_payload(
    stream: BinaryIO | TextIO | None,
) -> tuple[str | None, set[str], bool]:
    actual = stream
    if actual is None:
        actual = getattr(sys.stdin, "buffer", sys.stdin)
    try:
        raw = actual.read(MAX_STDIN_READ_BYTES)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        return None, {"find_objet_query_stdin_read_failed"}, False
    if type(raw) is str:
        try:
            payload_bytes = raw.encode("utf-8", errors="strict")
        except UnicodeError:
            return None, {"find_objet_query_unpaired_surrogate"}, True
    elif type(raw) is bytes:
        payload_bytes = raw
    else:
        return None, {"find_objet_query_stdin_read_failed"}, False

    failures: set[str] = set()
    if payload_bytes.startswith(b"\xef\xbb\xbf"):
        failures.add("find_objet_query_stdin_bom_forbidden")
    if payload_bytes.endswith(b"\r\n"):
        content = payload_bytes[:-2]
    elif payload_bytes.endswith(b"\n"):
        content = payload_bytes[:-1]
    else:
        content = payload_bytes
    if b"\n" in content:
        failures.add("find_objet_query_stdin_second_line_forbidden")
    if len(content) > MAX_RAW_QUERY_BYTES:
        failures.add("find_objet_query_raw_utf8_limit_exceeded")
    try:
        text = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        failures.add("find_objet_query_invalid_utf8")
        return None, failures, True
    return text, failures, True


def _first_request_blocker(codes: set[str]) -> str:
    return next(code for code in REQUEST_BLOCKER_CODES if code in codes)


def _query_plan(query: str, profile: str) -> tuple[_QueryPlan | None, str | None]:
    failures: set[str] = set()
    if len(query) > MAX_RAW_QUERY_SCALARS:
        failures.add("find_objet_query_raw_scalar_limit_exceeded")
    if _has_unpaired_surrogate(query):
        failures.add("find_objet_query_unpaired_surrogate")
        return None, _first_request_blocker(failures)
    try:
        raw_bytes = query.encode("utf-8", errors="strict")
    except UnicodeError:
        failures.add("find_objet_query_unpaired_surrogate")
        return None, _first_request_blocker(failures)
    if len(raw_bytes) > MAX_RAW_QUERY_BYTES:
        failures.add("find_objet_query_raw_utf8_limit_exceeded")
    if failures:
        return None, _first_request_blocker(failures)

    if profile == "utf8_percent_encoded_component":
        decoded, issue = _strict_percent_decode(query)
        if issue is not None:
            failures.add(NAME_REASON_TO_BLOCKER[issue])
            return None, _first_request_blocker(failures)
        if decoded is None:
            return None, "find_objet_query_derived_invariant_invalid"
        logical = decoded
        if PERCENT_TRIPLET_PATTERN.search(logical) is not None:
            failures.add("find_objet_query_residual_percent_triplet")
    else:
        logical = query

    if logical.startswith("\ufeff"):
        failures.add("find_objet_query_utf8_bom_forbidden")
    if len(logical) > MAX_LOGICAL_QUERY_SCALARS:
        failures.add("find_objet_query_logical_scalar_limit_exceeded")
    try:
        logical_bytes = logical.encode("utf-8", errors="strict")
    except UnicodeError:
        failures.add("find_objet_query_unpaired_surrogate")
        return None, _first_request_blocker(failures)
    if len(logical_bytes) > MAX_LOGICAL_QUERY_BYTES:
        failures.add("find_objet_query_logical_utf8_limit_exceeded")

    normalized = normalize_private_filename(logical, "literal_unicode")
    if (
        type(normalized) is not dict
        or normalized.get("issue_codes")
        or type(normalized.get("names")) is not dict
    ):
        failures.add("find_objet_query_derived_invariant_invalid")
    else:
        names = normalized["names"]
        reasons = names.get("reason_codes")
        if (
            type(reasons) is not list
            or any(reason not in NAME_REASON_CODES for reason in reasons)
        ):
            failures.add("find_objet_query_derived_invariant_invalid")
        else:
            failures.update(NAME_REASON_TO_BLOCKER[reason] for reason in reasons)
    if failures:
        return None, _first_request_blocker(failures)

    derived = derive_filename_search_keys(normalized["names"])
    if (
        type(derived) is not dict
        or derived.get("issue_codes")
        or type(derived.get("search_keys")) is not list
    ):
        return None, "find_objet_query_derived_invariant_invalid"
    values: list[str] = []
    for item in derived["search_keys"]:
        if (
            type(item) is not dict
            or set(item) != {"kind", "value"}
            or item.get("kind") not in ALIAS_KIND_SET
            or type(item.get("value")) is not str
            or not 1 <= len(item["value"]) <= 2048
            or item["value"] in values
        ):
            return None, "find_objet_query_derived_invariant_invalid"
        values.append(item["value"])
    if not 1 <= len(values) <= 5:
        return None, "find_objet_query_derived_invariant_invalid"
    return _QueryPlan(tuple(values)), None


def _derive_archive_boundary(archive_root: str) -> tuple[Path, str]:
    try:
        requested_root = Path(archive_root).absolute()
        requested_info = os.lstat(requested_root)
        if (
            not stat.S_ISDIR(requested_info.st_mode)
            or stat.S_ISLNK(requested_info.st_mode)
            or _is_reparse(requested_info)
        ):
            raise _BoundaryError
        canonical_root = requested_root.resolve(strict=True)
        canonical_info = os.lstat(canonical_root)
        if (
            not stat.S_ISDIR(canonical_info.st_mode)
            or stat.S_ISLNK(canonical_info.st_mode)
            or _is_reparse(canonical_info)
            or _stat_identity(canonical_info) != _stat_identity(requested_info)
        ):
            raise _BoundaryError
        root = archive_services.require_existing_archive_root(canonical_root)
        if root != canonical_root:
            raise _BoundaryError
        archive_id = archive_services.read_archive_id(root)
        if type(archive_id) is not str:
            raise _BoundaryError
        return root, archive_id
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        raise _BoundaryError from None


def _query_values_select(values: Sequence[str]) -> tuple[str, tuple[object, ...]]:
    fragments = ["SELECT ? AS alias_search_key"]
    fragments.extend("SELECT ?" for _ in values[1:])
    return " UNION ALL ".join(fragments), tuple(values)


def _require_object_id(value: object) -> str:
    if type(value) is not str or OBJECT_ID_RE.fullmatch(value) is None:
        raise PrivateObjetIndexSessionError(
            "private_objet_metadata_projection_invalid"
        )
    return value


def _projection_result(
    api: _PrivateObjetIndexReadAPI,
    object_id: str,
) -> dict[str, object]:
    rows = api.fetch_all(
        "SELECT object_id, audience, projection_schema_id, projection_json, "
        "projection_sha256, projection_status, observation_count, "
        "candidate_count FROM private_objet_label_projections "
        "WHERE object_id = ? COLLATE BINARY AND audience = ? COLLATE BINARY",
        (object_id, AUDIENCE),
    )
    if len(rows) != 1 or len(rows[0]) != 8:
        raise PrivateObjetIndexSessionError(
            "private_objet_metadata_projection_invalid"
        )
    (
        stored_object_id,
        audience,
        projection_schema_id,
        projection_json,
        projection_sha256,
        projection_status,
        observation_count,
        candidate_count,
    ) = rows[0]
    if (
        stored_object_id != object_id
        or audience != AUDIENCE
        or projection_schema_id != PROJECTION_SCHEMA_ID
        or type(projection_json) is not str
        or type(projection_sha256) is not str
        or DIGEST_RE.fullmatch(projection_sha256) is None
        or type(projection_status) is not str
        or type(observation_count) is not int
        or not 1 <= observation_count <= 64
        or type(candidate_count) is not int
        or not 0 <= candidate_count <= 256
    ):
        raise PrivateObjetIndexSessionError(
            "private_objet_metadata_projection_invalid"
        )
    try:
        projection = json.loads(projection_json)
        encoded = canonical_json_bytes(projection)
    except (TypeError, ValueError, UnicodeError):
        raise PrivateObjetIndexSessionError(
            "private_objet_metadata_projection_invalid"
        ) from None
    if (
        type(projection) is not dict
        or encoded.decode("ascii") != projection_json
        or sha256_digest(encoded) != projection_sha256
        or validate_objet_safe_label_projection(projection).get("accepted")
        is not True
        or projection.get("object_id") != object_id
        or projection.get("audience") != AUDIENCE
        or projection.get("status") != projection_status
    ):
        raise PrivateObjetIndexSessionError(
            "private_objet_metadata_projection_invalid"
        )
    return {
        "safe_label": projection,
        "evidence": {
            "generated_schema_id": GENERATED_SCHEMA_ID,
            "normalization_profile_id": NORMALIZATION_PROFILE_ID,
            "projection_schema_id": PROJECTION_SCHEMA_ID,
            "observation_count": observation_count,
            "candidate_count": candidate_count,
        },
    }


def _alias_evidence(
    api: _PrivateObjetIndexReadAPI,
    object_id: str,
    query_values: Sequence[str],
) -> tuple[list[str], int]:
    key_select, key_parameters = _query_values_select(query_values)
    rows = api.fetch_all(
        "SELECT a.authority_key_sha256, a.alias_ordinal, a.alias_kind "
        "FROM objet_name_aliases AS a "
        f"JOIN ({key_select}) AS q "
        "ON a.alias_search_key COLLATE BINARY = "
        "q.alias_search_key COLLATE BINARY "
        "WHERE a.object_id = ? COLLATE BINARY "
        "AND a.normalization_profile_id = ? COLLATE BINARY "
        "ORDER BY a.alias_kind COLLATE BINARY, "
        "a.authority_key_sha256 COLLATE BINARY, a.alias_ordinal",
        (*key_parameters, object_id, NORMALIZATION_PROFILE_ID),
    )
    identities: set[tuple[str, int]] = set()
    kinds: set[str] = set()
    for row in rows:
        if len(row) != 3:
            raise PrivateObjetIndexSessionError(
                "private_objet_metadata_projection_invalid"
            )
        authority_key, ordinal, kind = row
        if (
            type(authority_key) is not str
            or DIGEST_RE.fullmatch(authority_key) is None
            or type(ordinal) is not int
            or ordinal < 0
            or type(kind) is not str
            or kind not in ALIAS_KIND_SET
        ):
            raise PrivateObjetIndexSessionError(
                "private_objet_metadata_projection_invalid"
            )
        identities.add((authority_key, ordinal))
        kinds.add(kind)
    if not 1 <= len(identities) <= 320 or not 1 <= len(kinds) <= 5:
        raise PrivateObjetIndexSessionError(
            "private_objet_metadata_projection_invalid"
        )
    ordered_kinds = sorted(kinds, key=lambda item: item.encode("utf-8"))
    return ordered_kinds, len(identities)


def _lookup(
    api: _PrivateObjetIndexReadAPI,
    query_plan: _QueryPlan,
    limit: int,
    *,
    before_projection: Any,
) -> _LookupOutcome:
    key_select, key_parameters = _query_values_select(query_plan.values)
    rows = api.fetch_all(
        "SELECT DISTINCT a.object_id "
        "FROM objet_name_aliases AS a "
        f"JOIN ({key_select}) AS q "
        "ON a.alias_search_key COLLATE BINARY = "
        "q.alias_search_key COLLATE BINARY "
        "WHERE a.normalization_profile_id = ? COLLATE BINARY "
        "ORDER BY a.object_id COLLATE BINARY LIMIT ?",
        (*key_parameters, NORMALIZATION_PROFILE_ID, limit + 1),
    )
    object_ids: list[str] = []
    for row in rows:
        if len(row) != 1:
            raise PrivateObjetIndexSessionError(
                "private_objet_metadata_projection_invalid"
            )
        object_id = _require_object_id(row[0])
        if object_id in object_ids:
            raise PrivateObjetIndexSessionError(
                "private_objet_metadata_projection_invalid"
            )
        object_ids.append(object_id)
    if object_ids != sorted(
        object_ids,
        key=lambda item: item.encode("utf-8"),
    ):
        raise PrivateObjetIndexSessionError(
            "private_objet_metadata_projection_invalid"
        )

    truncated = len(object_ids) == limit + 1
    returned_ids = object_ids[:limit]
    results: list[dict[str, object]] = []
    for object_id in returned_ids:
        alias_kinds, alias_count = _alias_evidence(
            api,
            object_id,
            query_plan.values,
        )
        before_projection()
        projection = _projection_result(api, object_id)
        results.append(
            {
                "object_id": object_id,
                "safe_label": projection["safe_label"],
                "matched_alias_kinds": alias_kinds,
                "matched_alias_count": alias_count,
                "evidence": projection["evidence"],
            }
        )
    if truncated:
        return _LookupOutcome(
            distinct_object_count=None,
            count_exact=False,
            count_lower_bound=limit + 1,
            has_more=True,
            results=tuple(results),
        )
    count = len(object_ids)
    return _LookupOutcome(
        distinct_object_count=count,
        count_exact=True,
        count_lower_bound=count,
        has_more=False,
        results=tuple(results),
    )


def _privacy(returned: int, argv_exposure_possible: bool) -> dict[str, bool]:
    return {
        "wom_request_value_reflected": False,
        "wom_request_value_stored": False,
        "stored_private_projection_exposed": returned > 0,
        "source_identifier_exposed": False,
        "local_path_exposed": False,
        "provider_locator_exposed": False,
        "secret_value_exposed": False,
        "argv_query_exposure_possible": argv_exposure_possible,
    }


def _warnings(
    status: str,
    returned: int,
    argv_exposure_possible: bool,
) -> list[str]:
    predicates = {
        "find_objet_argv_query_exposure_possible": argv_exposure_possible,
        "find_objet_private_projection_exposed": returned > 0,
        "find_objet_ambiguous_no_winner": status == "ambiguous",
        "find_objet_negative_scope_limited": status == "not_found_in_index",
    }
    return [code for code in WARNING_ORDER if predicates[code]]


def _result(
    *,
    status: str,
    query_present: bool,
    query_profile_validated: bool,
    limit: int,
    checked_layers: Sequence[str],
    incomplete_layers: Sequence[str],
    private_health_case: str | None,
    private_health_value: Mapping[str, object] | None,
    distinct_object_count: int | None,
    count_exact: bool,
    count_lower_bound: int | None,
    has_more: bool,
    results: Sequence[Mapping[str, object]],
    diagnostics: Sequence[str],
    blockers: Sequence[str],
    argv_exposure_possible: bool,
) -> dict[str, object]:
    copied_results = [dict(item) for item in results]
    returned = len(copied_results)
    return {
        "schema": RESULT_SCHEMA_ID,
        "ok": status in {"not_found_in_index", "found", "ambiguous"},
        "status": status,
        "audience": AUDIENCE,
        "search_method": SEARCH_METHOD,
        "query_present": query_present,
        "query_profile_validated": query_profile_validated,
        "limit": limit,
        "checked_layers": list(checked_layers),
        "incomplete_layers": list(incomplete_layers),
        "private_health_case": private_health_case,
        "private_health": (
            dict(private_health_value)
            if private_health_value is not None
            else None
        ),
        "distinct_object_count": distinct_object_count,
        "count_exact": count_exact,
        "count_lower_bound": count_lower_bound,
        "returned": returned,
        "has_more": has_more,
        "results": copied_results,
        "diagnostic_codes": list(diagnostics),
        "blockers": list(blockers),
        "warnings": _warnings(
            status,
            returned,
            argv_exposure_possible,
        ),
        "privacy": _privacy(returned, argv_exposure_possible),
    }


def _request_blocked_result(
    code: str,
    *,
    query_present: bool,
    limit: int,
    argv_exposure_possible: bool,
) -> dict[str, object]:
    return _result(
        status="blocked",
        query_present=query_present,
        query_profile_validated=False,
        limit=limit,
        checked_layers=("request",),
        incomplete_layers=(),
        private_health_case=None,
        private_health_value=None,
        distinct_object_count=None,
        count_exact=False,
        count_lower_bound=None,
        has_more=False,
        results=(),
        diagnostics=(code,),
        blockers=(code,),
        argv_exposure_possible=argv_exposure_possible,
    )


def _boundary_blocked_result(
    *,
    limit: int,
    argv_exposure_possible: bool,
) -> dict[str, object]:
    return _result(
        status="blocked",
        query_present=True,
        query_profile_validated=True,
        limit=limit,
        checked_layers=LAYERS[:2],
        incomplete_layers=(),
        private_health_case=None,
        private_health_value=None,
        distinct_object_count=None,
        count_exact=False,
        count_lower_bound=None,
        has_more=False,
        results=(),
        diagnostics=(ARCHIVE_BOUNDARY_BLOCKER_CODE,),
        blockers=(ARCHIVE_BOUNDARY_BLOCKER_CODE,),
        argv_exposure_possible=argv_exposure_possible,
    )


def _semantic_result(
    decision: PrivateObjetMetadataHealthDecision,
    lookup: _LookupOutcome | None,
    *,
    consumer_phase: str,
    consumer_completed: bool,
    observed_case: str | None,
    limit: int,
    argv_exposure_possible: bool,
) -> dict[str, object]:
    case_id = decision.case_id
    checked_health = validate_private_objet_metadata_health_envelope(
        decision.envelope
    )
    if case_id == "C11":
        if lookup is None:
            raise PrivateObjetIndexSessionError(
                "private_objet_metadata_projection_invalid"
            )
        count = lookup.distinct_object_count
        if lookup.count_exact and count == 0:
            status = "not_found_in_index"
            diagnostics = ("find_objet_exact_match_not_found",)
        elif lookup.count_exact and count == 1:
            status = "found"
            diagnostics = ("find_objet_exact_match_found",)
        else:
            status = "ambiguous"
            diagnostics = (
                ("find_objet_exact_match_ambiguous",)
                if lookup.count_exact
                else (
                    "find_objet_exact_match_ambiguous",
                    "find_objet_result_truncated",
                )
            )
        return _result(
            status=status,
            query_present=True,
            query_profile_validated=True,
            limit=limit,
            checked_layers=LAYERS,
            incomplete_layers=(),
            private_health_case=case_id,
            private_health_value=checked_health,
            distinct_object_count=count,
            count_exact=lookup.count_exact,
            count_lower_bound=lookup.count_lower_bound,
            has_more=lookup.has_more,
            results=lookup.results,
            diagnostics=diagnostics,
            blockers=(),
            argv_exposure_possible=argv_exposure_possible,
        )

    if case_id == "C7":
        if (
            observed_case == "C10"
            or consumer_completed
            or consumer_phase == "private_label_projection"
        ):
            checked_layers = LAYERS
        elif consumer_phase == "private_alias_index":
            checked_layers = LAYERS[:5]
        else:
            checked_layers = LAYERS[:4]
        incomplete_layers: Sequence[str] = ()
    else:
        checked_layers, incomplete_layers = CASE_LAYERS[case_id]
    status = CASE_STATUS[case_id]
    return _result(
        status=status,
        query_present=True,
        query_profile_validated=True,
        limit=limit,
        checked_layers=checked_layers,
        incomplete_layers=incomplete_layers,
        private_health_case=case_id,
        private_health_value=checked_health,
        distinct_object_count=(0 if case_id == "C10" else None),
        count_exact=case_id == "C10",
        count_lower_bound=(0 if case_id == "C10" else None),
        has_more=False,
        results=(),
        diagnostics=CASE_DIAGNOSTICS[case_id],
        blockers=CASE_BLOCKERS.get(case_id, ()),
        argv_exposure_possible=argv_exposure_possible,
    )


def _canonical_mapping_order(value: object) -> bool:
    if type(value) is dict:
        keys = tuple(value)
        if keys != tuple(sorted(keys)):
            return False
        return all(_canonical_mapping_order(item) for item in value.values())
    if type(value) is list:
        return all(_canonical_mapping_order(item) for item in value)
    return True


def _validate_result_items(items: object) -> bool:
    if type(items) is not list or len(items) > 100:
        return False
    object_ids: list[str] = []
    for item in items:
        if type(item) is not dict or tuple(item) != RESULT_ITEM_KEYS:
            return False
        object_id = item["object_id"]
        safe_label = item["safe_label"]
        kinds = item["matched_alias_kinds"]
        evidence = item["evidence"]
        if (
            type(object_id) is not str
            or OBJECT_ID_RE.fullmatch(object_id) is None
            or type(safe_label) is not dict
            or not _canonical_mapping_order(safe_label)
            or validate_objet_safe_label_projection(safe_label).get(
                "accepted"
            )
            is not True
            or safe_label.get("object_id") != object_id
            or safe_label.get("audience") != AUDIENCE
            or type(kinds) is not list
            or not 1 <= len(kinds) <= 5
            or any(type(kind) is not str or kind not in ALIAS_KIND_SET for kind in kinds)
            or len(kinds) != len(set(kinds))
            or kinds
            != sorted(kinds, key=lambda value: value.encode("utf-8"))
            or type(item["matched_alias_count"]) is not int
            or not 1 <= item["matched_alias_count"] <= 320
            or type(evidence) is not dict
            or tuple(evidence) != EVIDENCE_KEYS
            or evidence["generated_schema_id"] != GENERATED_SCHEMA_ID
            or evidence["normalization_profile_id"]
            != NORMALIZATION_PROFILE_ID
            or evidence["projection_schema_id"] != PROJECTION_SCHEMA_ID
            or type(evidence["observation_count"]) is not int
            or not 1 <= evidence["observation_count"] <= 64
            or type(evidence["candidate_count"]) is not int
            or not 0 <= evidence["candidate_count"] <= 256
        ):
            return False
        object_ids.append(object_id)
    return (
        len(object_ids) == len(set(object_ids))
        and object_ids
        == sorted(object_ids, key=lambda value: value.encode("utf-8"))
    )


def _expected_layers(value: Mapping[str, object]) -> tuple[tuple[str, ...], ...]:
    diagnostics = tuple(value["diagnostic_codes"])  # type: ignore[arg-type]
    case_id = value["private_health_case"]
    if diagnostics and diagnostics[0] in REQUEST_BLOCKER_SET:
        return (("request",),)
    if diagnostics == (ARCHIVE_BOUNDARY_BLOCKER_CODE,):
        return (LAYERS[:2],)
    if diagnostics == (SERIALIZATION_BLOCKER_CODE,):
        return (("request",),)
    if case_id == "C7":
        return (LAYERS[:4], LAYERS[:5], LAYERS)
    if type(case_id) is str and case_id in CASE_LAYERS:
        return (tuple(CASE_LAYERS[case_id][0]),)
    return (LAYERS,)


def _expected_incomplete_layers(
    value: Mapping[str, object],
) -> tuple[str, ...]:
    diagnostics = tuple(value["diagnostic_codes"])  # type: ignore[arg-type]
    case_id = value["private_health_case"]
    if (
        (diagnostics and diagnostics[0] in REQUEST_BLOCKER_SET)
        or diagnostics in {
            (ARCHIVE_BOUNDARY_BLOCKER_CODE,),
            (SERIALIZATION_BLOCKER_CODE,),
        }
        or case_id == "C7"
        or case_id == "C11"
    ):
        return ()
    if type(case_id) is str and case_id in CASE_LAYERS:
        return tuple(CASE_LAYERS[case_id][1])
    return ()


def _validate_result(value: object) -> bool:
    if type(value) is not dict or tuple(value) != ROOT_KEYS:
        return False
    if (
        value["schema"] != RESULT_SCHEMA_ID
        or type(value["ok"]) is not bool
        or value["status"] not in STATUSES
        or value["audience"] != AUDIENCE
        or value["search_method"] != SEARCH_METHOD
        or type(value["query_present"]) is not bool
        or type(value["query_profile_validated"]) is not bool
        or type(value["limit"]) is not int
        or not 1 <= value["limit"] <= MAX_LIMIT
        or type(value["checked_layers"]) is not list
        or type(value["incomplete_layers"]) is not list
        or tuple(value["checked_layers"]) not in _expected_layers(value)
        or tuple(value["incomplete_layers"])
        != _expected_incomplete_layers(value)
        or not _validate_result_items(value["results"])
        or type(value["returned"]) is not int
        or value["returned"] != len(value["results"])
        or not 0 <= value["returned"] <= value["limit"]
        or type(value["count_exact"]) is not bool
        or type(value["has_more"]) is not bool
        or type(value["diagnostic_codes"]) is not list
        or type(value["blockers"]) is not list
        or type(value["warnings"]) is not list
        or any(type(item) is not str for item in value["diagnostic_codes"])
        or any(type(item) is not str for item in value["blockers"])
        or any(type(item) is not str for item in value["warnings"])
        or len(value["diagnostic_codes"])
        != len(set(value["diagnostic_codes"]))
        or len(value["blockers"]) != len(set(value["blockers"]))
        or len(value["warnings"]) != len(set(value["warnings"]))
        or type(value["privacy"]) is not dict
        or tuple(value["privacy"]) != PRIVACY_KEYS
        or any(type(item) is not bool for item in value["privacy"].values())
    ):
        return False

    case_id = value["private_health_case"]
    health_value = value["private_health"]
    if case_id is None:
        if health_value is not None:
            return False
    else:
        if (
            type(case_id) is not str
            or case_id not in {f"C{number}" for number in range(1, 12)}
            or type(health_value) is not dict
            or tuple(health_value) != PRIVATE_HEALTH_KEYS
        ):
            return False
        checked = validate_private_objet_metadata_health_envelope(health_value)
        if private_health._case_id_from_envelope(checked) != case_id:
            return False

    status = value["status"]
    returned = value["returned"]
    distinct = value["distinct_object_count"]
    lower = value["count_lower_bound"]
    if status in {"blocked", "search_incomplete"}:
        arithmetic = (
            distinct is None
            and value["count_exact"] is False
            and lower is None
            and returned == 0
            and value["has_more"] is False
        )
    elif status == "not_found_in_index":
        arithmetic = (
            distinct == 0
            and type(distinct) is int
            and value["count_exact"] is True
            and lower == 0
            and type(lower) is int
            and returned == 0
            and value["has_more"] is False
        )
    elif status == "found":
        arithmetic = (
            distinct == 1
            and type(distinct) is int
            and value["count_exact"] is True
            and lower == 1
            and type(lower) is int
            and returned == 1
            and value["has_more"] is False
        )
    elif value["count_exact"] is True:
        arithmetic = (
            type(distinct) is int
            and distinct >= 2
            and lower == distinct
            and type(lower) is int
            and returned == min(distinct, value["limit"])
            and value["has_more"] is (distinct > returned)
        )
    else:
        arithmetic = (
            distinct is None
            and lower == value["limit"] + 1
            and type(lower) is int
            and returned == value["limit"]
            and value["has_more"] is True
        )
    if not arithmetic:
        return False

    if value["ok"] is not (
        status in {"not_found_in_index", "found", "ambiguous"}
    ):
        return False
    if status == "blocked":
        if len(value["blockers"]) != 1:
            return False
    elif value["blockers"] != []:
        return False

    expected_warnings = _warnings(
        status,
        returned,
        value["privacy"]["argv_query_exposure_possible"],
    )
    if value["warnings"] != expected_warnings:
        return False
    expected_privacy = _privacy(
        returned,
        value["privacy"]["argv_query_exposure_possible"],
    )
    if value["privacy"] != expected_privacy:
        return False

    diagnostics = value["diagnostic_codes"]
    blockers = value["blockers"]
    if diagnostics and diagnostics[0] in REQUEST_BLOCKER_SET:
        if (
            case_id is not None
            or health_value is not None
            or blockers != diagnostics
            or value["query_profile_validated"] is not False
        ):
            return False
    elif diagnostics == [ARCHIVE_BOUNDARY_BLOCKER_CODE]:
        if (
            case_id is not None
            or health_value is not None
            or blockers != diagnostics
            or value["query_present"] is not True
            or value["query_profile_validated"] is not True
        ):
            return False
    elif diagnostics == [SERIALIZATION_BLOCKER_CODE]:
        return value == json.loads(FALLBACK_JSON_LITERAL)
    elif type(case_id) is str:
        if (
            value["query_present"] is not True
            or value["query_profile_validated"] is not True
        ):
            return False
        if case_id == "C11":
            if status == "not_found_in_index":
                expected_diagnostics = ["find_objet_exact_match_not_found"]
            elif status == "found":
                expected_diagnostics = ["find_objet_exact_match_found"]
            elif status == "ambiguous" and value["count_exact"]:
                expected_diagnostics = ["find_objet_exact_match_ambiguous"]
            else:
                expected_diagnostics = [
                    "find_objet_exact_match_ambiguous",
                    "find_objet_result_truncated",
                ]
            if diagnostics != expected_diagnostics or blockers != []:
                return False
        elif (
            diagnostics != list(CASE_DIAGNOSTICS[case_id])
            or blockers != list(CASE_BLOCKERS.get(case_id, ()))
            or status != CASE_STATUS[case_id]
        ):
            return False
    else:
        return False
    return True


def validate_private_objet_finder_result(value: object) -> bool:
    """Pure total validation for the complete finder application contract."""

    try:
        return _validate_result(value) is True
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        return False


def _render_text(result: Mapping[str, object]) -> str:
    lines = [
        TEXT_HEADERS[result["status"]],  # type: ignore[index]
        f"status={result['status']}",
        f"distinct_object_count={json.dumps(result['distinct_object_count'])}",
        f"count_exact={str(result['count_exact']).lower()}",
        f"count_lower_bound={json.dumps(result['count_lower_bound'])}",
        f"returned={result['returned']}",
        f"has_more={str(result['has_more']).lower()}",
    ]
    for index, item in enumerate(result["results"]):  # type: ignore[union-attr]
        lines.extend(
            (
                f"result[{index}].object_id={item['object_id']}",
                "result[{}].safe_label={}".format(
                    index,
                    json.dumps(
                        item["safe_label"],
                        ensure_ascii=False,
                        allow_nan=False,
                        separators=(",", ":"),
                        sort_keys=False,
                    ),
                ),
                "result[{}].matched_alias_kinds={}".format(
                    index,
                    ",".join(item["matched_alias_kinds"]),
                ),
                f"result[{index}].matched_alias_count="
                f"{item['matched_alias_count']}",
            )
        )
    lines.extend(
        (
            "diagnostic_codes=" + ",".join(result["diagnostic_codes"]),  # type: ignore[arg-type]
            "blockers=" + ",".join(result["blockers"]),  # type: ignore[arg-type]
            "warnings=" + ",".join(result["warnings"]),  # type: ignore[arg-type]
        )
    )
    return "\n".join(lines)


def _semantic_exit(result: Mapping[str, object]) -> int:
    status = result.get("status")
    if status == "blocked":
        return 2
    if status == "search_incomplete":
        return 1
    return 0


def _deliver_literal(rendered: str) -> bool:
    from .archive_cli import best_effort_terminal_print

    return best_effort_terminal_print(rendered)


def _deliver_result(result: object, output_format: str) -> int:
    try:
        accepted = validate_private_objet_finder_result(result)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        accepted = False
    if accepted is not True:
        rendered = (
            FALLBACK_JSON_LITERAL
            if output_format == "json"
            else FALLBACK_TEXT_LITERAL
        )
        _deliver_literal(rendered)
        return 2

    try:
        if output_format == "json":
            rendered = json.dumps(
                result,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=False,
            )
        else:
            rendered = _render_text(result)  # type: ignore[arg-type]
        rendered = rendered.encode("utf-8", errors="strict").decode(
            "utf-8",
            errors="strict",
        )
    except (TypeError, ValueError, UnicodeError):
        rendered = (
            FALLBACK_JSON_LITERAL
            if output_format == "json"
            else FALLBACK_TEXT_LITERAL
        )
        _deliver_literal(rendered)
        return 2
    _deliver_literal(rendered)
    return _semantic_exit(result)  # type: ignore[arg-type]


def _query_present_for_early_failure(parsed: _ParsedInvocation) -> bool:
    query_count = len(parsed.values["--query"])
    return (
        query_count == 1
        and parsed.stdin_count == 0
        and parsed.query_value_missing is False
    )


def _execute(
    argv: Sequence[str],
    *,
    stdin_stream: BinaryIO | TextIO | None,
) -> int:
    parsed = _scan_invocation(argv)
    if parsed.help_requested:
        _deliver_literal(HELP_TEXT)
        return 0

    blocker = parsed.first_failure
    if blocker is not None:
        return _deliver_result(
            _request_blocked_result(
                blocker,
                query_present=_query_present_for_early_failure(parsed),
                limit=parsed.selected_limit,
                argv_exposure_possible=parsed.argv_exposure_possible,
            ),
            parsed.selected_format,
        )

    if (
        parsed.archive_root is None
        or len(parsed.values["--audience"]) != 1
        or len(parsed.values["--query-profile"]) != 1
    ):
        raise AssertionError("accepted scanner state is incomplete")
    profile = parsed.values["--query-profile"][0]
    if parsed.stdin_count == 1:
        query, stdin_failures, query_present = _read_stdin_payload(stdin_stream)
        if stdin_failures:
            return _deliver_result(
                _request_blocked_result(
                    _first_request_blocker(stdin_failures),
                    query_present=query_present,
                    limit=parsed.selected_limit,
                    argv_exposure_possible=parsed.argv_exposure_possible,
                ),
                parsed.selected_format,
            )
        if query is None:
            raise AssertionError("accepted stdin state is incomplete")
        query_transport = "stdin"
    else:
        query = parsed.values["--query"][0]
        query_present = True
        query_transport = "argv"

    request = {
        "schema": REQUEST_SCHEMA_ID,
        "archive_root": parsed.archive_root,
        "audience": AUDIENCE,
        "query_profile": profile,
        "query_transport": query_transport,
        "query": query,
        "limit": parsed.selected_limit,
        "format": parsed.selected_format,
    }
    request_blocker = validate_private_objet_finder_request(request)
    if request_blocker is not None:
        return _deliver_result(
            _request_blocked_result(
                request_blocker,
                query_present=query_present,
                limit=parsed.selected_limit,
                argv_exposure_possible=parsed.argv_exposure_possible,
            ),
            parsed.selected_format,
        )
    query_plan, query_blocker = _query_plan(query, profile)
    if query_blocker is not None or query_plan is None:
        return _deliver_result(
            _request_blocked_result(
                query_blocker
                or "find_objet_query_derived_invariant_invalid",
                query_present=query_present,
                limit=parsed.selected_limit,
                argv_exposure_possible=parsed.argv_exposure_possible,
            ),
            parsed.selected_format,
        )

    try:
        root, archive_id = _derive_archive_boundary(parsed.archive_root)
    except _BoundaryError:
        return _deliver_result(
            _boundary_blocked_result(
                limit=parsed.selected_limit,
                argv_exposure_possible=parsed.argv_exposure_possible,
            ),
            parsed.selected_format,
        )

    lookup: _LookupOutcome | None = None
    observed_case: str | None = None
    consumer_phase = "before_consumer"
    consumer_completed = False

    def internal_consumer(
        api: _PrivateObjetIndexReadAPI,
        health_value: Mapping[str, object],
    ) -> None:
        nonlocal lookup, observed_case, consumer_phase, consumer_completed
        observed_case = private_health._case_id_from_envelope(health_value)
        if observed_case == "C11":
            consumer_phase = "private_alias_index"

            def before_projection() -> None:
                nonlocal consumer_phase
                consumer_phase = "private_label_projection"

            lookup = _lookup(
                api,
                query_plan,
                parsed.selected_limit,
                before_projection=before_projection,
            )
            consumer_completed = True

    decision = private_health._evaluate_private_objet_metadata_index_with_consumer(
        root,
        archive_id,
        internal_consumer,
    )
    semantic = _semantic_result(
        decision,
        lookup,
        consumer_phase=consumer_phase,
        consumer_completed=consumer_completed,
        observed_case=observed_case,
        limit=parsed.selected_limit,
        argv_exposure_possible=parsed.argv_exposure_possible,
    )
    return _deliver_result(semantic, parsed.selected_format)


def command_find_objet_argv(
    argv: Sequence[str],
    *,
    stdin_stream: BinaryIO | TextIO | None = None,
) -> int:
    """Execute the private-safe finder grammar without argparse diagnostics."""

    tokens: tuple[str, ...] | None = None
    try:
        if isinstance(argv, (str, bytes, bytearray)):
            raise TypeError("finder argv must be a string sequence")
        tokens = tuple(argv)
        if any(type(item) is not str for item in tokens):
            raise TypeError("finder argv must be a string sequence")
        return _execute(tokens, stdin_stream=stdin_stream)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        # An impossible internal path still emits only the fixed,
        # content-free serialization fallback.
        output_format = "text"
        if tokens is not None:
            try:
                output_format = _scan_invocation(tokens).selected_format
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception:
                output_format = "text"
        _deliver_literal(
            FALLBACK_JSON_LITERAL
            if output_format == "json"
            else FALLBACK_TEXT_LITERAL
        )
        return 2


__all__ = [
    "ARCHIVE_BOUNDARY_BLOCKER_CODE",
    "FALLBACK_JSON_LITERAL",
    "FALLBACK_TEXT_LITERAL",
    "HELP_TEXT",
    "REQUEST_BLOCKER_CODES",
    "REQUEST_SCHEMA_ID",
    "RESULT_SCHEMA_ID",
    "SERIALIZATION_BLOCKER_CODE",
    "command_find_objet_argv",
    "validate_private_objet_finder_request",
    "validate_private_objet_finder_result",
]
