"""Pure v0.3.296 private objet metadata writer contracts.

This module owns only bounded parsing, closed document validation,
canonicalization, deterministic identifiers, and the intake-to-row builder.
It performs no filesystem, archive, provider, network, database, or index
operation.  The mutation state machine lives in the archive service layer.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from typing import Any, Callable

from . import private_objet_metadata as private_metadata


INTAKE_SCHEMA = "wom-kit/private-objet-source-metadata-intake/v0.1"
DURABLE_SCHEMA = "wom-kit/private-objet-source-metadata/v0.1"
PLAN_SCHEMA = "wom-kit/private-objet-source-metadata-write-plan/v0.1"
AUTHORITY_CHAIN_SCHEMA = (
    "wom-kit/private-objet-source-metadata-authority-chain/v0.1"
)
RECEIPT_SCHEMA = "wom-kit/private-objet-source-metadata-write-receipt/v0.1"
JOURNAL_SCHEMA = "wom-kit/private-objet-source-metadata-write-journal/v0.1"
WRITER_STATE_MACHINE_VERSION = (
    "wom-kit/private-objet-source-metadata-writer-state/v0.1"
)
AUTHORITY_KEY_NAMESPACE = (
    "wom-kit/private-objet-source-metadata-authority-key/v0.1"
)
MUTATION_PLATFORM_PROFILE = (
    "windows_ntfs_win32_process_interruption/v0.1"
)

OBJECT_MANIFEST_PATH = "objects/manifests/files.jsonl"
PRIVATE_MANIFEST_PATH = "objects/manifests/private-source-metadata.jsonl"
OBJECT_MANIFEST_LOCK = "objects/manifests/.files.jsonl.lock"
PRIVATE_METADATA_LOCK = (
    "objects/manifests/.private-source-metadata.jsonl.lock"
)
JOURNAL_PATH = (
    "objects/manifests/.private-source-metadata-write.journal.json"
)
RECEIPT_DIRECTORY = "receipts/objects/private-source-metadata/"

INTAKE_MAX_BYTES = 4_194_304
MAX_SIGNED_64 = 9_223_372_036_854_775_807
WORST_CASE_REVIEWED_BY = "operator:" + ("A" * 191)
DIGEST_SIZE_SENTINEL = "sha256:" + ("0" * 64)

NORMALIZATION_PROFILE_VALUE = {
    "id": "wom-kit/filename-normalization/v0.1",
    "unicode_version": "17.0.0",
    "confusables_data_sha256": None,
    "confusable_status": "not_checked",
}

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SOURCE_SYSTEM_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,63})$")
_MEDIA_TYPE_RE = re.compile(
    r"^[a-z0-9][a-z0-9!#$&^_.+\-]{0,126}/"
    r"[a-z0-9][a-z0-9!#$&^_.+\-]{0,126}$"
)
_REVIEWED_BY_RE = re.compile(
    r"^operator:[A-Za-z0-9][A-Za-z0-9._-]{0,190}$"
)
_RECEIPT_PATH_RE = re.compile(
    r"^receipts/objects/private-source-metadata/[0-9a-f]{64}\.json$"
)
_JOURNAL_TEMP_PATH_RE = re.compile(
    r"^objects/manifests/\.private-source-metadata-write\."
    r"[0-9a-f]{64}\.journal\.tmp$"
)
_MANIFEST_TEMP_PATH_RE = re.compile(
    r"^objects/manifests/\.private-source-metadata-write\."
    r"[0-9a-f]{64}\.manifest\.tmp$"
)
_RECEIPT_TEMP_PATH_RE = re.compile(
    r"^receipts/objects/private-source-metadata/\."
    r"[0-9a-f]{64}\.receipt\.tmp$"
)

_INTAKE_FIELDS = {
    "schema",
    "object_id",
    "privacy_class",
    "name_observation",
    "media_observation",
    "size_bytes_observed",
    "size_bytes_basis",
    "source_provenance",
    "review_evidence",
}
_NAME_OBSERVATION_FIELDS = {"original_filename", "name_input_profile"}
_MEDIA_OBSERVATION_FIELDS = {"value", "basis"}
_SOURCE_PROVENANCE_FIELDS = {
    "source_system",
    "source_record_id",
    "source_attachment_id",
    "source_snapshot_sha256",
    "observation_evidence_sha256",
    "evidence_kind",
    "captured_at",
}
_REVIEW_EVIDENCE_FIELDS = {"review_evidence_sha256", "review_status"}

_FILE_STATE_FIELDS = {
    "state",
    "sha256",
    "byte_count",
    "row_count",
    "link_count",
}
_DIRECTORY_STATE_FIELDS = {"state", "entry_count"}
_DIRECTORY_CHAIN_FIELDS = {
    "receipts_root",
    "objects_parent",
    "private_receipt_directory",
}
_OWNED_TEMP_STATE_FIELDS = {
    "journal_temp",
    "manifest_temp",
    "receipt_temp",
}
_RESOURCE_BINDING_FIELDS = {
    "basis",
    "private_manifest_current_bytes",
    "private_manifest_current_rows",
    "canonical_stored_row_bytes",
    "receipt_final_count_current",
    "receipt_final_total_bytes_current",
    "receipt_directory_entries_current",
    "receipt_root_entries_after_bootstrap",
    "receipt_objects_entries_after_bootstrap",
    "manifest_directory_entries_with_both_locks",
    "prospective_private_manifest_bytes",
    "prospective_private_manifest_rows",
    "prospective_receipt_bytes",
    "prospective_receipt_final_count",
    "prospective_receipt_final_total_bytes",
    "prospective_receipt_directory_peak_entries",
    "prospective_manifest_directory_peak_entries",
    "prospective_journal_bytes",
}
_PLAN_FIELDS = {
    "schema",
    "writer_state_machine_version",
    "archive_id",
    "intake_sha256",
    "canonical_row_sha256",
    "observation_evidence_sha256",
    "review_evidence_sha256",
    "object_id",
    "object_manifest_state",
    "object_manifest_match_count",
    "private_manifest_before",
    "private_manifest_after",
    "receipt_directory_chain_before",
    "receipt_directory_chain_after",
    "receipt_state",
    "journal_state",
    "journal_sha256",
    "owned_temp_states",
    "planned_receipt_sha256",
    "prior_row_state",
    "receipt_inventory_state",
    "authority_chain_scope",
    "authority_chain_validation",
    "authority_chain_sha256",
    "intake_schema",
    "durable_schema",
    "normalization_profile",
    "action",
    "blocked_context",
    "derived_alias_count",
    "existing_exact_row_count",
    "exact_receipt_count",
    "resource_binding",
    "private_manifest_relative_path",
    "receipt_directory_relative_path",
    "authority_key_sha256",
    "receipt_relative_path",
}
_AUTHORITY_CHAIN_FIELDS = {"schema", "private_manifest_state", "entries"}
_AUTHORITY_ENTRY_FIELDS = {
    "row_number",
    "intake_sha256",
    "canonical_row_sha256",
    "observation_evidence_sha256",
    "review_evidence_sha256",
    "authority_key_sha256",
    "receipt_relative_path",
    "receipt_sha256",
    "manifest_before",
    "manifest_after",
}
_CLOSED_ACTION_FIELDS = {
    "source_artifact_modified",
    "object_bytes_opened",
    "provider_or_network_called",
    "database_or_index_written",
}
_RECEIPT_FIELDS = {
    "schema",
    "writer_state_machine_version",
    "lifecycle",
    "action",
    "artifact_class",
    "archive_id",
    "record_privacy_class",
    "object_id",
    "authority_key_sha256",
    "intake_sha256",
    "canonical_row_sha256",
    "observation_evidence_sha256",
    "review_evidence_sha256",
    "reviewed_by",
    "external_writers_quiescent_affirmed",
    "mutation_platform_profile",
    "power_loss_durability_verified",
    "plan_binding",
    "plan_sha256",
    "object_manifest_state",
    "authority_chain_before_sha256",
    "private_manifest_before",
    "private_manifest_after",
    "intake_schema",
    "durable_schema",
    "normalization_profile",
    "derived_alias_count",
    "closed_actions",
}
_JOURNAL_FIELDS = {
    "schema",
    "writer_state_machine_version",
    "transition",
    "plan_sha256",
    "authority_chain_before_sha256",
    "authority_key_sha256",
    "receipt_relative_path",
    "receipt_document",
    "receipt_sha256",
    "object_manifest_state",
    "private_manifest_before",
    "private_manifest_after",
    "owned_temp_relative_paths",
}

_PLAN_ACTIONS = {
    "append",
    "rollback_required",
    "already_applied",
    "recovery_required",
    "manual_hold",
    "blocked",
}
_PRIOR_ROW_STATES = {"absent", "exact", "collision", "multiple"}
_RECEIPT_INVENTORY_STATES = {
    "absent",
    "exact",
    "conflicting",
    "multiple",
    "orphan",
}
_AUTHORITY_SCOPES = {
    "complete_current",
    "prefix_before_interrupted_append",
}
_AUTHORITY_VALIDATIONS = {
    "valid_complete",
    "valid_recovery_prefix",
    "manual_hold",
}
_RESOURCE_BASES = {
    "append_worst_case_actor",
    "recovery_exact_journal",
    "no_write",
}


class _DuplicateKeyError(ValueError):
    pass


class _IntegerTokenError(ValueError):
    pass


def _contains_surrogate(value: Any) -> bool:
    pending = [value]
    visited: set[int] = set()
    while pending:
        current = pending.pop()
        if type(current) is str:
            if any(0xD800 <= ord(character) <= 0xDFFF for character in current):
                return True
            continue
        if type(current) not in {dict, list}:
            continue
        identity = id(current)
        if identity in visited:
            continue
        visited.add(identity)
        if type(current) is list:
            pending.extend(current)
        else:
            for key, item in current.items():
                pending.append(key)
                pending.append(item)
    return False


def _closed_object(value: Any, fields: set[str]) -> bool:
    return (
        type(value) is dict
        and all(type(key) is str for key in value)
        and set(value) == fields
    )


def _is_scalar(value: Any, *, minimum: int = 0, maximum: int) -> bool:
    return (
        type(value) is str
        and minimum <= len(value) <= maximum
        and not _contains_surrogate(value)
    )


def _is_optional_scalar(
    value: Any,
    *,
    minimum: int = 1,
    maximum: int,
) -> bool:
    return value is None or _is_scalar(
        value,
        minimum=minimum,
        maximum=maximum,
    )


def _is_digest(value: Any) -> bool:
    return type(value) is str and _DIGEST_RE.fullmatch(value) is not None


def _is_optional_digest(value: Any) -> bool:
    return value is None or _is_digest(value)


def _is_nonnegative_integer(value: Any) -> bool:
    return type(value) is int and value >= 0


def _is_enum(value: Any, allowed: set[str]) -> bool:
    return type(value) is str and value in allowed


def _is_optional_enum(value: Any, allowed: set[str]) -> bool:
    return value is None or _is_enum(value, allowed)


def _is_profile(value: Any) -> bool:
    return type(value) is dict and value == NORMALIZATION_PROFILE_VALUE


def _is_file_state(value: Any) -> bool:
    if not _closed_object(value, _FILE_STATE_FIELDS):
        return False
    state = value["state"]
    if state == "absent":
        return (
            value["sha256"] is None
            and type(value["byte_count"]) is int
            and value["byte_count"] == 0
            and type(value["row_count"]) is int
            and value["row_count"] == 0
            and type(value["link_count"]) is int
            and value["link_count"] == 0
        )
    if state == "present":
        return (
            _is_digest(value["sha256"])
            and _is_nonnegative_integer(value["byte_count"])
            and _is_nonnegative_integer(value["row_count"])
            and _is_nonnegative_integer(value["link_count"])
        )
    if state == "present_invalid":
        return (
            _is_digest(value["sha256"])
            and _is_nonnegative_integer(value["byte_count"])
            and value["row_count"] is None
            and _is_nonnegative_integer(value["link_count"])
        )
    if state == "unavailable":
        return (
            value["sha256"] is None
            and (
                value["byte_count"] is None
                or _is_nonnegative_integer(value["byte_count"])
            )
            and value["row_count"] is None
            and (
                value["link_count"] is None
                or _is_nonnegative_integer(value["link_count"])
            )
        )
    return False


def _is_directory_state(value: Any) -> bool:
    if not _closed_object(value, _DIRECTORY_STATE_FIELDS):
        return False
    if value["state"] == "absent":
        return (
            type(value["entry_count"]) is int
            and value["entry_count"] == 0
        )
    return (
        value["state"] == "present"
        and _is_nonnegative_integer(value["entry_count"])
    )


def _is_directory_chain(value: Any) -> bool:
    return (
        _closed_object(value, _DIRECTORY_CHAIN_FIELDS)
        and all(_is_directory_state(value[key]) for key in _DIRECTORY_CHAIN_FIELDS)
    )


def _is_owned_temp_states(value: Any) -> bool:
    return (
        _closed_object(value, _OWNED_TEMP_STATE_FIELDS)
        and all(_is_file_state(value[key]) for key in _OWNED_TEMP_STATE_FIELDS)
    )


def _is_resource_binding(value: Any) -> bool:
    if not _closed_object(value, _RESOURCE_BINDING_FIELDS):
        return False
    if not _is_enum(value["basis"], _RESOURCE_BASES):
        return False
    return all(
        _is_nonnegative_integer(item)
        for key, item in value.items()
        if key != "basis"
    )


def _is_absent_file_state(value: Any) -> bool:
    return _is_file_state(value) and value["state"] == "absent"


def _is_present_file_state(
    value: Any,
    *,
    link_counts: set[int] | frozenset[int] = frozenset({1}),
    single_document: bool = False,
) -> bool:
    if (
        not _is_file_state(value)
        or value["state"] != "present"
        or value["byte_count"] < 1
        or value["link_count"] not in link_counts
    ):
        return False
    if single_document:
        return value["row_count"] == 1
    return value["row_count"] >= 1


def _is_present_invalid_file_state(
    value: Any,
    *,
    link_counts: set[int] | frozenset[int] = frozenset({1}),
) -> bool:
    return bool(
        _is_file_state(value)
        and value["state"] == "present_invalid"
        and value["link_count"] in link_counts
    )


def _is_logically_possible_directory_chain(value: Any) -> bool:
    if not _is_directory_chain(value):
        return False
    root_present = value["receipts_root"]["state"] == "present"
    objects_present = value["objects_parent"]["state"] == "present"
    private_present = (
        value["private_receipt_directory"]["state"] == "present"
    )
    return bool(
        (not objects_present or root_present)
        and (not private_present or objects_present)
    )


def _project_receipt_directory_chain(
    before: dict[str, Any],
) -> dict[str, Any] | None:
    if not _is_logically_possible_directory_chain(before):
        return None
    projected = deepcopy(before)
    root = projected["receipts_root"]
    objects = projected["objects_parent"]
    private = projected["private_receipt_directory"]
    if root["state"] == "absent":
        return {
            "receipts_root": {"state": "present", "entry_count": 1},
            "objects_parent": {"state": "present", "entry_count": 1},
            "private_receipt_directory": {
                "state": "present",
                "entry_count": 0,
            },
        }
    if objects["state"] == "absent":
        root["entry_count"] += 1
        projected["objects_parent"] = {
            "state": "present",
            "entry_count": 1,
        }
        projected["private_receipt_directory"] = {
            "state": "present",
            "entry_count": 0,
        }
        return projected
    if private["state"] == "absent":
        objects["entry_count"] += 1
        projected["private_receipt_directory"] = {
            "state": "present",
            "entry_count": 0,
        }
    return projected


def _directory_chain_is_complete(value: Any) -> bool:
    return bool(
        _is_logically_possible_directory_chain(value)
        and all(
            value[key]["state"] == "present"
            for key in _DIRECTORY_CHAIN_FIELDS
        )
    )


def _current_manifest_counts(
    state: dict[str, Any],
) -> tuple[int, int] | None:
    if _is_absent_file_state(state):
        return 0, 0
    if _is_present_file_state(state):
        return int(state["byte_count"]), int(state["row_count"])
    return None


def _accepted() -> dict[str, Any]:
    return {"accepted": True, "issue_codes": []}


def _rejected(code: str) -> dict[str, Any]:
    return {"accepted": False, "issue_codes": [code]}


def _duplicate_key_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError
        result[key] = value
    return result


def _reject_constant(_: str) -> Any:
    raise ValueError


def _bounded_int(token: str) -> int:
    digits = token[1:] if token.startswith("-") else token
    if len(digits) > 19:
        raise _IntegerTokenError
    return int(token)


def _parse_document(
    raw: bytes,
    *,
    validator: Callable[[Any], dict[str, Any]],
    invalid_code: str,
    maximum_bytes: int | None = None,
    bounded_integers: bool = False,
    canonical_storage: str | None = None,
    preserve_validation_issue_codes: bool = False,
) -> dict[str, Any]:
    if (
        type(raw) is not bytes
        or (maximum_bytes is not None and len(raw) > maximum_bytes)
        or raw.startswith(b"\xef\xbb\xbf")
    ):
        return {
            "accepted": False,
            "document": None,
            "issue_codes": [invalid_code],
        }
    try:
        text = raw.decode("utf-8", errors="strict")
        document = json.loads(
            text,
            object_pairs_hook=_duplicate_key_object,
            parse_constant=_reject_constant,
            parse_int=_bounded_int if bounded_integers else int,
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        _DuplicateKeyError,
        _IntegerTokenError,
        ValueError,
    ):
        return {
            "accepted": False,
            "document": None,
            "issue_codes": [invalid_code],
        }
    validation = validator(document)
    if not validation["accepted"]:
        return {
            "accepted": False,
            "document": None,
            "issue_codes": (
                list(validation["issue_codes"])
                if preserve_validation_issue_codes
                else [invalid_code]
            ),
        }
    if canonical_storage is not None:
        try:
            expected = (
                canonical_json_bytes(document)
                if canonical_storage == "cjson"
                else stored_json_bytes(document)
            )
        except ValueError:
            expected = None
        if canonical_storage not in {"cjson", "stored_json"} or raw != expected:
            return {
                "accepted": False,
                "document": None,
                "issue_codes": [invalid_code],
            }
    return {
        "accepted": True,
        "document": document,
        "issue_codes": [],
    }


def canonical_json_bytes(value: Any) -> bytes:
    """Return the exact v0.3.296 ``CJSON`` bytes."""

    if _contains_surrogate(value):
        raise ValueError("JSON document contains a Unicode surrogate scalar")
    try:
        return json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ValueError("JSON document is not canonically encodable") from exc


def stored_json_bytes(value: Any) -> bytes:
    """Return the exact v0.3.296 ``STORED_JSON`` bytes."""

    return canonical_json_bytes(value) + b"\n"


def sha256_digest(value: bytes) -> str:
    """Return an exact ``sha256:``-prefixed lowercase digest."""

    if type(value) is not bytes:
        raise TypeError("sha256_digest requires bytes")
    return "sha256:" + hashlib.sha256(value).hexdigest()


def authority_key_sha256(observation_evidence_sha256: str) -> str:
    """Derive the fixed v0.3.296 authority key."""

    if not _is_digest(observation_evidence_sha256):
        raise ValueError("invalid observation evidence digest")
    material = (
        AUTHORITY_KEY_NAMESPACE.encode("ascii")
        + b"\x00"
        + observation_evidence_sha256.encode("ascii")
    )
    return sha256_digest(material)


def receipt_relative_path(authority_key: str) -> str:
    """Return the deterministic private receipt path."""

    if not _is_digest(authority_key):
        raise ValueError("invalid authority key digest")
    return RECEIPT_DIRECTORY + authority_key[7:] + ".json"


def owned_temp_relative_paths(authority_key: str) -> list[str]:
    """Return the three exact owned temp paths in canonical order."""

    if not _is_digest(authority_key):
        raise ValueError("invalid authority key digest")
    authority_hex = authority_key[7:]
    return [
        (
            "objects/manifests/.private-source-metadata-write."
            f"{authority_hex}.journal.tmp"
        ),
        (
            "objects/manifests/.private-source-metadata-write."
            f"{authority_hex}.manifest.tmp"
        ),
        (
            "receipts/objects/private-source-metadata/."
            f"{authority_hex}.receipt.tmp"
        ),
    ]


def validate_private_metadata_intake(value: Any) -> dict[str, Any]:
    """Validate the dependency-light closed v0.1 intake contract."""

    if _contains_surrogate(value) or not _closed_object(value, _INTAKE_FIELDS):
        return _rejected("private_metadata_intake_invalid")
    if (
        value["schema"] != INTAKE_SCHEMA
        or not _is_digest(value["object_id"])
        or not _is_enum(
            value["privacy_class"],
            {"private_archive", "restricted"},
        )
        or value["size_bytes_basis"] != "source_observed"
        or not _is_nonnegative_integer(value["size_bytes_observed"])
        or value["size_bytes_observed"] > MAX_SIGNED_64
    ):
        return _rejected("private_metadata_intake_invalid")

    name = value["name_observation"]
    if (
        not _closed_object(name, _NAME_OBSERVATION_FIELDS)
        or not _is_scalar(name["original_filename"], maximum=512)
        or not _is_enum(
            name["name_input_profile"],
            {"literal_unicode", "utf8_percent_encoded_component"},
        )
    ):
        return _rejected("private_metadata_intake_invalid")

    media = value["media_observation"]
    if not _closed_object(media, _MEDIA_OBSERVATION_FIELDS):
        return _rejected("private_metadata_intake_invalid")
    if media["basis"] == "unknown":
        if media["value"] is not None:
            return _rejected("private_metadata_intake_invalid")
    elif media["basis"] == "source_declared":
        if (
            type(media["value"]) is not str
            or not 3 <= len(media["value"]) <= 127
            or _MEDIA_TYPE_RE.fullmatch(media["value"]) is None
        ):
            return _rejected("private_metadata_intake_invalid")
    else:
        return _rejected("private_metadata_intake_invalid")

    provenance = value["source_provenance"]
    if not _closed_object(provenance, _SOURCE_PROVENANCE_FIELDS):
        return _rejected("private_metadata_intake_invalid")
    if (
        type(provenance["source_system"]) is not str
        or not 1 <= len(provenance["source_system"]) <= 64
        or _SOURCE_SYSTEM_RE.fullmatch(provenance["source_system"]) is None
        or not _is_optional_scalar(
            provenance["source_record_id"],
            maximum=256,
        )
        or not _is_optional_scalar(
            provenance["source_attachment_id"],
            maximum=256,
        )
        or not _is_digest(provenance["source_snapshot_sha256"])
        or not _is_digest(provenance["observation_evidence_sha256"])
        or not _is_enum(
            provenance["evidence_kind"],
            {
                "source_record_field",
                "source_attachment_metadata",
                "source_snapshot_extract",
            },
        )
        or (
            provenance["captured_at"] is not None
            and not private_metadata.is_valid_private_metadata_rfc3339(
                provenance["captured_at"]
            )
        )
    ):
        return _rejected("private_metadata_intake_invalid")
    if provenance["evidence_kind"] == "source_record_field" and (
        provenance["source_record_id"] is None
        or provenance["source_attachment_id"] is not None
    ):
        return _rejected("private_metadata_intake_invalid")
    if (
        provenance["evidence_kind"] == "source_attachment_metadata"
        and provenance["source_attachment_id"] is None
    ):
        return _rejected("private_metadata_intake_invalid")

    review = value["review_evidence"]
    if (
        not _closed_object(review, _REVIEW_EVIDENCE_FIELDS)
        or not _is_digest(review["review_evidence_sha256"])
        or review["review_status"] != "human_reviewed"
    ):
        return _rejected("private_metadata_intake_invalid")
    return _accepted()


def parse_private_metadata_intake_bytes(raw: bytes) -> dict[str, Any]:
    """Parse one bounded strict UTF-8 intake and bind its exact raw digest."""

    result = _parse_document(
        raw,
        validator=validate_private_metadata_intake,
        invalid_code="private_metadata_intake_invalid",
        maximum_bytes=INTAKE_MAX_BYTES,
        bounded_integers=True,
    )
    if not result["accepted"]:
        return {
            "accepted": False,
            "intake": None,
            "intake_sha256": None,
            "issue_codes": result["issue_codes"],
        }
    return {
        "accepted": True,
        "intake": result["document"],
        "intake_sha256": sha256_digest(raw),
        "issue_codes": [],
    }


def build_private_metadata_row(intake: Any) -> dict[str, Any]:
    """Build the one canonical v0.3.296 durable row from a valid intake."""

    validation = validate_private_metadata_intake(intake)
    if not validation["accepted"]:
        return {
            "accepted": False,
            "row": None,
            "canonical_json_bytes": None,
            "stored_row_bytes": None,
            "canonical_row_sha256": None,
            "issue_codes": validation["issue_codes"],
        }

    normalization = private_metadata.normalize_private_filename(
        intake["name_observation"]["original_filename"],
        intake["name_observation"]["name_input_profile"],
    )
    if normalization["issue_codes"] or normalization["names"] is None:
        return {
            "accepted": False,
            "row": None,
            "canonical_json_bytes": None,
            "stored_row_bytes": None,
            "canonical_row_sha256": None,
            "issue_codes": ["private_metadata_intake_invalid"],
        }

    names = deepcopy(normalization["names"])
    candidates: list[dict[str, Any]] = []
    if names["derivation_status"] == "valid":
        if names["name_input_profile"] == "literal_unicode":
            kind = "original_filename"
            label_value = names["original_filename"]
        else:
            kind = "decoded_filename"
            label_value = names["decoded_filename"]
            if type(label_value) is not str:
                return {
                    "accepted": False,
                    "row": None,
                    "canonical_json_bytes": None,
                    "stored_row_bytes": None,
                    "canonical_row_sha256": None,
                    "issue_codes": ["private_metadata_intake_invalid"],
                }
        candidates.append(
            {
                "kind": kind,
                "value": label_value,
                "privacy_class": intake["privacy_class"],
                "evidence_sha256": intake["source_provenance"][
                    "observation_evidence_sha256"
                ],
                "review_status": "accepted",
                "review_evidence_sha256": intake["review_evidence"][
                    "review_evidence_sha256"
                ],
            }
        )

    row = {
        "schema": DURABLE_SCHEMA,
        "privacy_class": intake["privacy_class"],
        "object_id": intake["object_id"],
        "names": names,
        "media_type": {
            "value": intake["media_observation"]["value"],
            "basis": intake["media_observation"]["basis"],
            "registered_status": "not_checked",
            "extension_agreement": "unknown",
            "extension_comparison_evidence_sha256": None,
            "registry_evidence": None,
        },
        "size_bytes": intake["size_bytes_observed"],
        "size_bytes_basis": "source_observed",
        "source_provenance": deepcopy(intake["source_provenance"]),
        "label_candidates": candidates,
        "normalization_profile": deepcopy(NORMALIZATION_PROFILE_VALUE),
    }
    record_validation = private_metadata.validate_private_metadata_record(row)
    if not record_validation["accepted"]:
        return {
            "accepted": False,
            "row": None,
            "canonical_json_bytes": None,
            "stored_row_bytes": None,
            "canonical_row_sha256": None,
            "issue_codes": ["private_metadata_intake_invalid"],
        }
    canonical = canonical_json_bytes(row)
    return {
        "accepted": True,
        "row": row,
        "canonical_json_bytes": canonical,
        "stored_row_bytes": canonical + b"\n",
        "canonical_row_sha256": sha256_digest(canonical),
        "issue_codes": [],
    }


def validate_private_metadata_write_plan(value: Any) -> dict[str, Any]:
    """Validate the dependency-light closed plan document shape."""

    if _contains_surrogate(value) or not _closed_object(value, _PLAN_FIELDS):
        return _rejected("private_metadata_write_plan_invalid")
    if (
        value["schema"] != PLAN_SCHEMA
        or value["writer_state_machine_version"]
        != WRITER_STATE_MACHINE_VERSION
        or not _is_scalar(value["archive_id"], minimum=1, maximum=200)
        or not all(
            _is_digest(value[key])
            for key in (
                "intake_sha256",
                "canonical_row_sha256",
                "observation_evidence_sha256",
                "review_evidence_sha256",
                "object_id",
                "authority_key_sha256",
            )
        )
        or not _is_file_state(value["object_manifest_state"])
        or not _is_nonnegative_integer(value["object_manifest_match_count"])
        or not _is_file_state(value["private_manifest_before"])
        or not _is_file_state(value["private_manifest_after"])
        or not _is_directory_chain(value["receipt_directory_chain_before"])
        or not _is_directory_chain(value["receipt_directory_chain_after"])
        or not _is_file_state(value["receipt_state"])
        or not _is_file_state(value["journal_state"])
        or not _is_optional_digest(value["journal_sha256"])
        or not _is_owned_temp_states(value["owned_temp_states"])
        or not _is_optional_digest(value["planned_receipt_sha256"])
        or not _is_enum(value["prior_row_state"], _PRIOR_ROW_STATES)
        or not _is_enum(
            value["receipt_inventory_state"],
            _RECEIPT_INVENTORY_STATES,
        )
        or not _is_enum(
            value["authority_chain_scope"],
            _AUTHORITY_SCOPES,
        )
        or not _is_enum(
            value["authority_chain_validation"],
            _AUTHORITY_VALIDATIONS,
        )
        or not _is_optional_digest(value["authority_chain_sha256"])
        or value["intake_schema"] != INTAKE_SCHEMA
        or value["durable_schema"] != DURABLE_SCHEMA
        or not _is_profile(value["normalization_profile"])
        or not _is_enum(value["action"], _PLAN_ACTIONS)
        or not _is_optional_enum(
            value["blocked_context"],
            {"append", "recovery"},
        )
        or not _is_nonnegative_integer(value["derived_alias_count"])
        or value["derived_alias_count"] > 1
        or not _is_nonnegative_integer(value["existing_exact_row_count"])
        or not _is_nonnegative_integer(value["exact_receipt_count"])
        or not _is_resource_binding(value["resource_binding"])
        or value["private_manifest_relative_path"] != PRIVATE_MANIFEST_PATH
        or value["receipt_directory_relative_path"] != RECEIPT_DIRECTORY
        or type(value["receipt_relative_path"]) is not str
        or _RECEIPT_PATH_RE.fullmatch(value["receipt_relative_path"]) is None
    ):
        return _rejected("private_metadata_write_plan_invalid")
    if (
        value["action"] == "blocked"
        and not _is_enum(
            value["blocked_context"],
            {"append", "recovery"},
        )
    ) or (
        value["action"] != "blocked"
        and value["blocked_context"] is not None
    ):
        return _rejected("private_metadata_write_plan_invalid")
    if (
        value["authority_chain_validation"] == "manual_hold"
        and value["authority_chain_sha256"] is not None
    ) or (
        value["authority_chain_validation"] != "manual_hold"
        and not _is_digest(value["authority_chain_sha256"])
    ):
        return _rejected("private_metadata_write_plan_invalid")
    if value["journal_state"]["state"] in {"present", "present_invalid"}:
        if not _is_digest(value["journal_sha256"]):
            return _rejected("private_metadata_write_plan_invalid")
    elif value["journal_sha256"] is not None:
        return _rejected("private_metadata_write_plan_invalid")
    return _accepted()


def _all_owned_temp_states_absent(value: dict[str, Any]) -> bool:
    return all(
        _is_absent_file_state(value[key])
        for key in ("journal_temp", "manifest_temp", "receipt_temp")
    )


def _no_write_resource_binding_is_exact(
    resource: dict[str, Any],
) -> bool:
    return bool(
        resource["basis"] == "no_write"
        and resource["prospective_private_manifest_bytes"]
        == resource["private_manifest_current_bytes"]
        and resource["prospective_private_manifest_rows"]
        == resource["private_manifest_current_rows"]
        and resource["prospective_receipt_bytes"] == 0
        and resource["prospective_receipt_final_count"]
        == resource["receipt_final_count_current"]
        and resource["prospective_receipt_final_total_bytes"]
        == resource["receipt_final_total_bytes_current"]
        and resource["prospective_receipt_directory_peak_entries"]
        == resource["receipt_directory_entries_current"]
        and resource["prospective_manifest_directory_peak_entries"]
        == resource["manifest_directory_entries_with_both_locks"]
        and resource["prospective_journal_bytes"] == 0
    )


def _append_resource_binding_is_exact(
    resource: dict[str, Any],
) -> bool:
    return bool(
        resource["basis"] == "append_worst_case_actor"
        and resource["prospective_private_manifest_bytes"]
        == resource["private_manifest_current_bytes"]
        + resource["canonical_stored_row_bytes"]
        and resource["prospective_private_manifest_rows"]
        == resource["private_manifest_current_rows"] + 1
        and resource["prospective_receipt_final_count"]
        == resource["receipt_final_count_current"] + 1
        and resource["prospective_receipt_final_total_bytes"]
        == resource["receipt_final_total_bytes_current"]
        + resource["prospective_receipt_bytes"]
        and resource["prospective_receipt_directory_peak_entries"]
        == resource["receipt_directory_entries_current"] + 2
        and resource["prospective_manifest_directory_peak_entries"]
        == resource["manifest_directory_entries_with_both_locks"] + 2
    )


def _recovery_resource_binding_is_exact(
    resource: dict[str, Any],
    *,
    journal_state: dict[str, Any],
    receipt_temp_state: dict[str, Any],
) -> bool:
    extra_receipt_entry = (
        2 if receipt_temp_state["state"] == "absent" else 1
    )
    return bool(
        resource["basis"] == "recovery_exact_journal"
        and resource["prospective_private_manifest_bytes"]
        == resource["private_manifest_current_bytes"]
        and resource["prospective_private_manifest_rows"]
        == resource["private_manifest_current_rows"]
        and resource["prospective_receipt_bytes"] >= 1
        and resource["prospective_receipt_final_count"]
        == resource["receipt_final_count_current"] + 1
        and resource["prospective_receipt_final_total_bytes"]
        == resource["receipt_final_total_bytes_current"]
        + resource["prospective_receipt_bytes"]
        and resource["prospective_receipt_directory_peak_entries"]
        == resource["receipt_directory_entries_current"]
        + extra_receipt_entry
        and resource["prospective_manifest_directory_peak_entries"]
        == resource["manifest_directory_entries_with_both_locks"]
        and resource["prospective_journal_bytes"]
        == journal_state["byte_count"]
    )


def _size_receipt_for_append_plan(
    plan: dict[str, Any],
    *,
    privacy_class: str,
) -> dict[str, Any]:
    plan_sha256 = sha256_digest(canonical_json_bytes(plan))
    return {
        "schema": RECEIPT_SCHEMA,
        "writer_state_machine_version": WRITER_STATE_MACHINE_VERSION,
        "lifecycle": "private_objet_source_metadata_write",
        "action": "applied",
        "artifact_class": privacy_class,
        "archive_id": plan["archive_id"],
        "record_privacy_class": privacy_class,
        "object_id": plan["object_id"],
        "authority_key_sha256": plan["authority_key_sha256"],
        "intake_sha256": plan["intake_sha256"],
        "canonical_row_sha256": plan["canonical_row_sha256"],
        "observation_evidence_sha256": plan[
            "observation_evidence_sha256"
        ],
        "review_evidence_sha256": plan["review_evidence_sha256"],
        "reviewed_by": WORST_CASE_REVIEWED_BY,
        "external_writers_quiescent_affirmed": True,
        "mutation_platform_profile": MUTATION_PLATFORM_PROFILE,
        "power_loss_durability_verified": False,
        "plan_binding": deepcopy(plan),
        "plan_sha256": plan_sha256,
        "object_manifest_state": deepcopy(plan["object_manifest_state"]),
        "authority_chain_before_sha256": plan["authority_chain_sha256"],
        "private_manifest_before": deepcopy(plan["private_manifest_before"]),
        "private_manifest_after": deepcopy(plan["private_manifest_after"]),
        "intake_schema": INTAKE_SCHEMA,
        "durable_schema": DURABLE_SCHEMA,
        "normalization_profile": deepcopy(NORMALIZATION_PROFILE_VALUE),
        "derived_alias_count": plan["derived_alias_count"],
        "closed_actions": {
            "source_artifact_modified": False,
            "object_bytes_opened": False,
            "provider_or_network_called": False,
            "database_or_index_written": False,
        },
    }


def _size_journal_for_receipt(
    receipt: dict[str, Any],
) -> dict[str, Any]:
    plan = receipt["plan_binding"]
    return {
        "schema": JOURNAL_SCHEMA,
        "writer_state_machine_version": WRITER_STATE_MACHINE_VERSION,
        "transition": "append",
        "plan_sha256": receipt["plan_sha256"],
        "authority_chain_before_sha256": receipt[
            "authority_chain_before_sha256"
        ],
        "authority_key_sha256": receipt["authority_key_sha256"],
        "receipt_relative_path": plan["receipt_relative_path"],
        "receipt_document": deepcopy(receipt),
        "receipt_sha256": sha256_digest(stored_json_bytes(receipt)),
        "object_manifest_state": deepcopy(plan["object_manifest_state"]),
        "private_manifest_before": deepcopy(plan["private_manifest_before"]),
        "private_manifest_after": deepcopy(plan["private_manifest_after"]),
        "owned_temp_relative_paths": owned_temp_relative_paths(
            receipt["authority_key_sha256"]
        ),
    }


def _append_size_plan(value: dict[str, Any]) -> dict[str, Any]:
    candidate = deepcopy(value)
    if (
        candidate["action"] == "blocked"
        and candidate["blocked_context"] == "append"
    ):
        resource = candidate["resource_binding"]
        candidate["action"] = "append"
        candidate["blocked_context"] = None
        candidate["private_manifest_after"] = {
            "state": "present",
            "sha256": DIGEST_SIZE_SENTINEL,
            "byte_count": resource["prospective_private_manifest_bytes"],
            "row_count": resource["prospective_private_manifest_rows"],
            "link_count": 1,
        }
    return candidate


def _append_size_binding_pairs(
    value: dict[str, Any],
    *,
    privacy_class: str,
) -> tuple[set[tuple[int, int]], tuple[int, int] | None]:
    size_plan = _append_size_plan(value)
    resource = size_plan["resource_binding"]
    pairs: set[tuple[int, int]] = set()
    receipt_bytes = 0
    journal_bytes = 0
    for _ in range(16):
        candidate = deepcopy(size_plan)
        candidate_resource = candidate["resource_binding"]
        candidate_resource["prospective_receipt_bytes"] = receipt_bytes
        candidate_resource["prospective_receipt_final_total_bytes"] = (
            candidate_resource["receipt_final_total_bytes_current"]
            + receipt_bytes
        )
        candidate_resource["prospective_journal_bytes"] = journal_bytes
        pairs.add((receipt_bytes, journal_bytes))
        receipt = _size_receipt_for_append_plan(
            candidate,
            privacy_class=privacy_class,
        )
        journal = _size_journal_for_receipt(receipt)
        next_pair = (
            len(stored_json_bytes(receipt)),
            len(stored_json_bytes(journal)),
        )
        if next_pair == (receipt_bytes, journal_bytes):
            return pairs, next_pair
        receipt_bytes, journal_bytes = next_pair
    return pairs, None


def _append_size_binding_is_exact(
    value: dict[str, Any],
    *,
    require_fixed_point: bool,
    expected_privacy_class: str | None,
) -> bool:
    resource = value["resource_binding"]
    observed = (
        resource["prospective_receipt_bytes"],
        resource["prospective_journal_bytes"],
    )
    privacy_classes = (
        (expected_privacy_class,)
        if expected_privacy_class is not None
        else ("private_archive", "restricted")
    )
    for privacy_class in privacy_classes:
        pairs, fixed_point = _append_size_binding_pairs(
            value,
            privacy_class=privacy_class,
        )
        if require_fixed_point:
            if fixed_point is not None and observed == fixed_point:
                return True
        elif observed in pairs:
            return True
    return False


def _plan_common_semantics_are_valid(value: dict[str, Any]) -> bool:
    expected_authority_key = authority_key_sha256(
        value["observation_evidence_sha256"]
    )
    if (
        value["authority_key_sha256"] != expected_authority_key
        or value["receipt_relative_path"]
        != receipt_relative_path(expected_authority_key)
        or value["object_manifest_match_count"] != 1
        or not _is_present_file_state(value["object_manifest_state"])
        or _current_manifest_counts(value["private_manifest_before"]) is None
        or _current_manifest_counts(value["private_manifest_after"]) is None
        or not _is_logically_possible_directory_chain(
            value["receipt_directory_chain_before"]
        )
        or not _is_logically_possible_directory_chain(
            value["receipt_directory_chain_after"]
        )
    ):
        return False

    before_counts = _current_manifest_counts(
        value["private_manifest_before"]
    )
    assert before_counts is not None
    resource = value["resource_binding"]
    chain_before = value["receipt_directory_chain_before"]
    chain_after = value["receipt_directory_chain_after"]
    receipt_directory_entries = (
        chain_before["private_receipt_directory"]["entry_count"]
        if chain_before["private_receipt_directory"]["state"] == "present"
        else 0
    )
    private_row_count = before_counts[1]
    if (
        resource["private_manifest_current_bytes"] != before_counts[0]
        or resource["private_manifest_current_rows"] != private_row_count
        or resource["canonical_stored_row_bytes"] < 1
        or resource["receipt_directory_entries_current"]
        != receipt_directory_entries
        or resource["receipt_root_entries_after_bootstrap"]
        != chain_after["receipts_root"]["entry_count"]
        or resource["receipt_objects_entries_after_bootstrap"]
        != chain_after["objects_parent"]["entry_count"]
        or resource["receipt_final_count_current"]
        > resource["receipt_directory_entries_current"]
        or resource["receipt_final_total_bytes_current"]
        < resource["receipt_final_count_current"]
        or value["existing_exact_row_count"] > private_row_count
        or value["exact_receipt_count"]
        > resource["receipt_final_count_current"]
    ):
        return False
    if value["journal_state"]["state"] in {"present", "present_invalid"}:
        if value["journal_sha256"] != value["journal_state"]["sha256"]:
            return False
    elif value["journal_sha256"] is not None:
        return False
    return True


def _append_or_blocked_append_semantics_are_valid(
    value: dict[str, Any],
    *,
    require_final_size_binding: bool,
    expected_privacy_class: str | None,
) -> bool:
    action = value["action"]
    resource = value["resource_binding"]
    expected_chain_after = _project_receipt_directory_chain(
        value["receipt_directory_chain_before"]
    )
    if (
        expected_chain_after is None
        or value["receipt_directory_chain_after"] != expected_chain_after
        or not _is_absent_file_state(value["receipt_state"])
        or not _is_absent_file_state(value["journal_state"])
        or not _all_owned_temp_states_absent(value["owned_temp_states"])
        or value["planned_receipt_sha256"] is not None
        or value["prior_row_state"] != "absent"
        or value["receipt_inventory_state"] != "absent"
        or value["authority_chain_scope"] != "complete_current"
        or value["authority_chain_validation"] != "valid_complete"
        or value["authority_chain_sha256"] is None
        or value["existing_exact_row_count"] != 0
        or value["exact_receipt_count"] != 0
        or not _append_resource_binding_is_exact(resource)
    ):
        return False
    if action == "append":
        after = value["private_manifest_after"]
        if (
            not _is_present_file_state(after)
            or after["byte_count"]
            != resource["prospective_private_manifest_bytes"]
            or after["row_count"]
            != resource["prospective_private_manifest_rows"]
        ):
            return False
    elif (
        action != "blocked"
        or value["blocked_context"] != "append"
        or value["private_manifest_after"]
        != value["private_manifest_before"]
    ):
        return False
    return _append_size_binding_is_exact(
        value,
        require_fixed_point=require_final_size_binding,
        expected_privacy_class=expected_privacy_class,
    )


def _rollback_semantics_are_valid(value: dict[str, Any]) -> bool:
    journal = value["journal_state"]
    temps = value["owned_temp_states"]
    journal_temp = temps["journal_temp"]
    manifest_temp = temps["manifest_temp"]
    first_cell = bool(
        _is_absent_file_state(journal)
        and _is_present_file_state(
            journal_temp,
            single_document=True,
        )
        and _is_absent_file_state(manifest_temp)
        and _is_absent_file_state(temps["receipt_temp"])
    )
    fixed_cell = bool(
        _is_present_file_state(
            journal,
            link_counts={1, 2},
            single_document=True,
        )
        and (
            _is_absent_file_state(journal_temp)
            or (
                journal["link_count"] == 2
                and _is_present_file_state(
                    journal_temp,
                    link_counts={2},
                    single_document=True,
                )
                and journal_temp["sha256"] == journal["sha256"]
                and journal_temp["byte_count"] == journal["byte_count"]
            )
        )
        and (
            _is_absent_file_state(manifest_temp)
            or _is_present_file_state(manifest_temp)
            or _is_present_invalid_file_state(manifest_temp)
        )
        and _is_absent_file_state(temps["receipt_temp"])
    )
    if journal["state"] == "present" and journal["link_count"] == 1:
        fixed_cell = fixed_cell and _is_absent_file_state(journal_temp)
    if journal["state"] == "present" and journal["link_count"] == 2:
        fixed_cell = fixed_cell and not _is_absent_file_state(journal_temp)
    return bool(
        value["private_manifest_after"] == value["private_manifest_before"]
        and _directory_chain_is_complete(
            value["receipt_directory_chain_before"]
        )
        and value["receipt_directory_chain_after"]
        == value["receipt_directory_chain_before"]
        and _is_absent_file_state(value["receipt_state"])
        and _is_digest(value["planned_receipt_sha256"])
        and value["prior_row_state"] == "absent"
        and value["receipt_inventory_state"] == "absent"
        and value["authority_chain_scope"] == "complete_current"
        and value["authority_chain_validation"] == "valid_complete"
        and value["authority_chain_sha256"] is not None
        and value["existing_exact_row_count"] == 0
        and value["exact_receipt_count"] == 0
        and _no_write_resource_binding_is_exact(value["resource_binding"])
        and (first_cell or fixed_cell)
    )


def _recovery_or_blocked_recovery_semantics_are_valid(
    value: dict[str, Any],
) -> bool:
    resource = value["resource_binding"]
    journal = value["journal_state"]
    temps = value["owned_temp_states"]
    receipt_temp = temps["receipt_temp"]
    if not (
        _is_absent_file_state(receipt_temp)
        or _is_present_file_state(receipt_temp, single_document=True)
        or _is_present_invalid_file_state(receipt_temp)
    ):
        return False
    if (
        receipt_temp["state"] == "present"
        and (
            receipt_temp["sha256"] != value["planned_receipt_sha256"]
            or receipt_temp["byte_count"]
            != resource["prospective_receipt_bytes"]
        )
    ):
        return False
    if (
        receipt_temp["state"] == "present_invalid"
        and receipt_temp["byte_count"]
        >= resource["prospective_receipt_bytes"]
    ):
        return False
    return bool(
        value["private_manifest_after"] == value["private_manifest_before"]
        and _is_present_file_state(value["private_manifest_before"])
        and _directory_chain_is_complete(
            value["receipt_directory_chain_before"]
        )
        and value["receipt_directory_chain_after"]
        == value["receipt_directory_chain_before"]
        and _is_absent_file_state(value["receipt_state"])
        and _is_present_file_state(journal, single_document=True)
        and _is_absent_file_state(temps["journal_temp"])
        and _is_absent_file_state(temps["manifest_temp"])
        and _is_digest(value["planned_receipt_sha256"])
        and value["prior_row_state"] == "exact"
        and value["receipt_inventory_state"] == "absent"
        and value["authority_chain_scope"]
        == "prefix_before_interrupted_append"
        and value["authority_chain_validation"] == "valid_recovery_prefix"
        and value["authority_chain_sha256"] is not None
        and value["existing_exact_row_count"] == 1
        and value["exact_receipt_count"] == 0
        and _recovery_resource_binding_is_exact(
            resource,
            journal_state=journal,
            receipt_temp_state=receipt_temp,
        )
    )


def _already_applied_semantics_are_valid(value: dict[str, Any]) -> bool:
    receipt = value["receipt_state"]
    journal = value["journal_state"]
    temps = value["owned_temp_states"]
    clean = bool(
        _is_absent_file_state(journal)
        and _all_owned_temp_states_absent(temps)
        and _is_present_file_state(
            receipt,
            link_counts={1},
            single_document=True,
        )
    )
    completed_residue = bool(
        _is_present_file_state(journal, single_document=True)
        and _is_absent_file_state(temps["journal_temp"])
        and _is_absent_file_state(temps["manifest_temp"])
        and (
            (
                _is_present_file_state(
                    receipt,
                    link_counts={1},
                    single_document=True,
                )
                and _is_absent_file_state(temps["receipt_temp"])
            )
            or (
                _is_present_file_state(
                    receipt,
                    link_counts={2},
                    single_document=True,
                )
                and _is_present_file_state(
                    temps["receipt_temp"],
                    link_counts={2},
                    single_document=True,
                )
                and receipt["sha256"] == temps["receipt_temp"]["sha256"]
                and receipt["byte_count"]
                == temps["receipt_temp"]["byte_count"]
            )
        )
    )
    return bool(
        value["private_manifest_after"] == value["private_manifest_before"]
        and _is_present_file_state(value["private_manifest_before"])
        and _directory_chain_is_complete(
            value["receipt_directory_chain_before"]
        )
        and value["receipt_directory_chain_after"]
        == value["receipt_directory_chain_before"]
        and _is_digest(value["planned_receipt_sha256"])
        and value["planned_receipt_sha256"] == receipt["sha256"]
        and value["prior_row_state"] == "exact"
        and value["receipt_inventory_state"] == "exact"
        and value["authority_chain_scope"] == "complete_current"
        and value["authority_chain_validation"] == "valid_complete"
        and value["authority_chain_sha256"] is not None
        and value["existing_exact_row_count"] == 1
        and value["exact_receipt_count"] == 1
        and _no_write_resource_binding_is_exact(value["resource_binding"])
        and (clean or completed_residue)
    )


def _is_observed_single_document(value: Any) -> bool:
    return bool(
        _is_file_state(value)
        and value["state"] == "present"
        and value["byte_count"] >= 1
        and value["row_count"] == 1
        and value["link_count"] in {1, 2}
    )


def _manual_hold_artifact_state_is_supported(
    value: Any,
    *,
    link_counts: set[int] | frozenset[int],
    single_document: bool,
) -> bool:
    if _is_absent_file_state(value):
        return True
    if _is_present_file_state(
        value,
        link_counts=link_counts,
        single_document=single_document,
    ):
        return True
    return _is_present_invalid_file_state(
        value,
        link_counts=link_counts,
    )


def _manual_hold_artifact_states_are_supported(
    value: dict[str, Any],
) -> bool:
    document_link_counts = frozenset({1, 2})
    temps = value["owned_temp_states"]
    return bool(
        _manual_hold_artifact_state_is_supported(
            value["receipt_state"],
            link_counts=document_link_counts,
            single_document=True,
        )
        and _manual_hold_artifact_state_is_supported(
            value["journal_state"],
            link_counts=document_link_counts,
            single_document=True,
        )
        and _manual_hold_artifact_state_is_supported(
            temps["journal_temp"],
            link_counts=document_link_counts,
            single_document=True,
        )
        and _manual_hold_artifact_state_is_supported(
            temps["receipt_temp"],
            link_counts=document_link_counts,
            single_document=True,
        )
        and _manual_hold_artifact_state_is_supported(
            temps["manifest_temp"],
            link_counts=frozenset({1}),
            single_document=False,
        )
    )


def _manual_hold_prior_state_is_consistent(
    value: dict[str, Any],
) -> bool:
    prior_state = value["prior_row_state"]
    exact_count = value["existing_exact_row_count"]
    manifest_rows = value["resource_binding"][
        "private_manifest_current_rows"
    ]
    if (prior_state == "exact") != (exact_count == 1):
        return False
    if prior_state == "absent":
        return exact_count == 0
    if prior_state == "exact":
        return manifest_rows >= 1
    if prior_state == "collision":
        return exact_count == 0 and manifest_rows >= 1
    if prior_state == "multiple":
        return exact_count != 1 and manifest_rows >= 2
    return False


def _manual_hold_receipt_state_is_consistent(
    value: dict[str, Any],
) -> bool:
    inventory_state = value["receipt_inventory_state"]
    receipt = value["receipt_state"]
    exact_count = value["exact_receipt_count"]
    resource = value["resource_binding"]
    receipt_absent = _is_absent_file_state(receipt)
    receipt_exact_document = _is_observed_single_document(receipt)

    if inventory_state == "absent":
        if not receipt_absent or exact_count != 0:
            return False
    elif inventory_state == "exact":
        if not receipt_exact_document or exact_count != 1:
            return False
    elif inventory_state == "conflicting":
        if receipt_absent or exact_count != 0:
            return False
    elif inventory_state == "multiple":
        if receipt_absent or exact_count < 2:
            return False
    elif inventory_state == "orphan":
        if not receipt_exact_document or exact_count != 1:
            return False
    else:
        return False

    if not receipt_absent:
        private_directory = value["receipt_directory_chain_before"][
            "private_receipt_directory"
        ]
        if (
            private_directory["state"] != "present"
            or private_directory["entry_count"] < 1
            or resource["receipt_final_count_current"] < 1
        ):
            return False
        observed_bytes = receipt["byte_count"]
        if (
            type(observed_bytes) is int
            and resource["receipt_final_total_bytes_current"]
            < observed_bytes
        ):
            return False

    planned_receipt = value["planned_receipt_sha256"]
    journal = value["journal_state"]
    journal_temp = value["owned_temp_states"]["journal_temp"]
    journal_receipt_evidence = bool(
        _is_observed_single_document(journal)
        or _is_observed_single_document(journal_temp)
    )
    deterministic_receipt_evidence = bool(
        inventory_state in {"exact", "orphan"}
        and receipt_exact_document
    )
    if deterministic_receipt_evidence:
        return planned_receipt == receipt["sha256"]
    if planned_receipt is not None and not journal_receipt_evidence:
        return False
    return True


def _manual_hold_semantics_are_valid(value: dict[str, Any]) -> bool:
    return bool(
        value["private_manifest_after"] == value["private_manifest_before"]
        and value["receipt_directory_chain_after"]
        == value["receipt_directory_chain_before"]
        and value["authority_chain_scope"] == "complete_current"
        and value["authority_chain_validation"]
        in {"valid_complete", "manual_hold"}
        and _no_write_resource_binding_is_exact(value["resource_binding"])
        and _manual_hold_artifact_states_are_supported(value)
        and _manual_hold_prior_state_is_consistent(value)
        and _manual_hold_receipt_state_is_consistent(value)
    )


def validate_private_metadata_write_plan_semantics(
    value: Any,
    *,
    require_final_size_binding: bool = False,
    expected_privacy_class: str | None = None,
) -> dict[str, Any]:
    """Validate deterministic plan derivations and action invariants.

    The writer's bounded fixed-point builder validates each exact intermediate
    append pair, while standalone stored documents and embedded receipts pass
    ``require_final_size_binding=True``.
    """

    if not validate_private_metadata_write_plan(value)["accepted"]:
        return _rejected("private_metadata_write_plan_invalid")
    if expected_privacy_class not in {None, "private_archive", "restricted"}:
        return _rejected("private_metadata_write_plan_invalid")
    if not _plan_common_semantics_are_valid(value):
        return _rejected("private_metadata_write_plan_invalid")
    action = value["action"]
    if (
        action == "append"
        or (action == "blocked" and value["blocked_context"] == "append")
    ):
        valid = _append_or_blocked_append_semantics_are_valid(
            value,
            require_final_size_binding=require_final_size_binding,
            expected_privacy_class=expected_privacy_class,
        )
    elif action == "rollback_required":
        valid = _rollback_semantics_are_valid(value)
    elif (
        action == "recovery_required"
        or (action == "blocked" and value["blocked_context"] == "recovery")
    ):
        valid = _recovery_or_blocked_recovery_semantics_are_valid(value)
    elif action == "already_applied":
        valid = _already_applied_semantics_are_valid(value)
    else:
        valid = action == "manual_hold" and _manual_hold_semantics_are_valid(
            value
        )
    if not valid:
        return _rejected("private_metadata_write_plan_invalid")
    return _accepted()


def parse_private_metadata_write_plan_bytes(raw: bytes) -> dict[str, Any]:
    def validate_stored_plan(value: Any) -> dict[str, Any]:
        return validate_private_metadata_write_plan_semantics(
            value,
            require_final_size_binding=True,
        )

    return _parse_document(
        raw,
        validator=validate_stored_plan,
        invalid_code="private_metadata_write_plan_invalid",
        canonical_storage="cjson",
    )


def validate_private_metadata_authority_chain(value: Any) -> dict[str, Any]:
    """Validate the dependency-light closed authority-chain document shape."""

    if (
        _contains_surrogate(value)
        or not _closed_object(value, _AUTHORITY_CHAIN_FIELDS)
        or value["schema"] != AUTHORITY_CHAIN_SCHEMA
        or not _is_file_state(value["private_manifest_state"])
        or type(value["entries"]) is not list
    ):
        return _rejected("private_metadata_authority_chain_invalid")
    for entry in value["entries"]:
        if (
            not _closed_object(entry, _AUTHORITY_ENTRY_FIELDS)
            or type(entry["row_number"]) is not int
            or entry["row_number"] < 1
            or not all(
                _is_digest(entry[key])
                for key in (
                    "intake_sha256",
                    "canonical_row_sha256",
                    "observation_evidence_sha256",
                    "review_evidence_sha256",
                    "authority_key_sha256",
                    "receipt_sha256",
                )
            )
            or type(entry["receipt_relative_path"]) is not str
            or _RECEIPT_PATH_RE.fullmatch(entry["receipt_relative_path"])
            is None
            or not _is_file_state(entry["manifest_before"])
            or not _is_file_state(entry["manifest_after"])
        ):
            return _rejected("private_metadata_authority_chain_invalid")
    return _accepted()


def validate_private_metadata_authority_chain_semantics(
    value: Any,
) -> dict[str, Any]:
    """Validate exact row order, authority derivation, and prefix states."""

    if not validate_private_metadata_authority_chain(value)["accepted"]:
        return _rejected("private_metadata_authority_chain_invalid")
    entries = value["entries"]
    if not entries:
        if not _is_absent_file_state(value["private_manifest_state"]):
            return _rejected("private_metadata_authority_chain_invalid")
        return _accepted()

    seen_observations: set[str] = set()
    seen_rows: set[str] = set()
    seen_authority_keys: set[str] = set()
    seen_receipt_paths: set[str] = set()
    previous_after: dict[str, Any] | None = None
    for expected_row, entry in enumerate(value["entries"], start=1):
        expected_authority_key = authority_key_sha256(
            entry["observation_evidence_sha256"]
        )
        before = entry["manifest_before"]
        after = entry["manifest_after"]
        if (
            entry["row_number"] != expected_row
            or entry["authority_key_sha256"] != expected_authority_key
            or entry["receipt_relative_path"]
            != receipt_relative_path(expected_authority_key)
            or entry["observation_evidence_sha256"]
            in seen_observations
            or entry["canonical_row_sha256"] in seen_rows
            or entry["authority_key_sha256"] in seen_authority_keys
            or entry["receipt_relative_path"] in seen_receipt_paths
            or not _is_present_file_state(after)
            or after["row_count"] != expected_row
            or (
                expected_row == 1
                and not _is_absent_file_state(before)
            )
            or (
                expected_row > 1
                and before != previous_after
            )
            or after["byte_count"] <= before["byte_count"]
        ):
            return _rejected("private_metadata_authority_chain_invalid")
        seen_observations.add(entry["observation_evidence_sha256"])
        seen_rows.add(entry["canonical_row_sha256"])
        seen_authority_keys.add(entry["authority_key_sha256"])
        seen_receipt_paths.add(entry["receipt_relative_path"])
        previous_after = after
    if value["private_manifest_state"] != previous_after:
        return _rejected("private_metadata_authority_chain_invalid")
    return _accepted()


def parse_private_metadata_authority_chain_bytes(raw: bytes) -> dict[str, Any]:
    return _parse_document(
        raw,
        validator=validate_private_metadata_authority_chain_semantics,
        invalid_code="private_metadata_authority_chain_invalid",
        canonical_storage="cjson",
    )


def _is_closed_actions(value: Any) -> bool:
    return (
        _closed_object(value, _CLOSED_ACTION_FIELDS)
        and all(value[key] is False for key in _CLOSED_ACTION_FIELDS)
    )


def validate_private_metadata_write_receipt(value: Any) -> dict[str, Any]:
    """Validate the dependency-light closed receipt document shape."""

    if _contains_surrogate(value) or not _closed_object(value, _RECEIPT_FIELDS):
        return _rejected("private_metadata_write_receipt_invalid")
    if (
        value["schema"] != RECEIPT_SCHEMA
        or value["writer_state_machine_version"]
        != WRITER_STATE_MACHINE_VERSION
        or value["lifecycle"] != "private_objet_source_metadata_write"
        or value["action"] != "applied"
        or not _is_enum(
            value["artifact_class"],
            {"private_archive", "restricted"},
        )
        or not _is_enum(
            value["record_privacy_class"],
            {"private_archive", "restricted"},
        )
        or value["artifact_class"] != value["record_privacy_class"]
        or not _is_scalar(value["archive_id"], minimum=1, maximum=200)
        or not all(
            _is_digest(value[key])
            for key in (
                "object_id",
                "authority_key_sha256",
                "intake_sha256",
                "canonical_row_sha256",
                "observation_evidence_sha256",
                "review_evidence_sha256",
                "plan_sha256",
                "authority_chain_before_sha256",
            )
        )
        or type(value["reviewed_by"]) is not str
        or not 10 <= len(value["reviewed_by"].encode("ascii", "ignore")) <= 200
        or not value["reviewed_by"].isascii()
        or _REVIEWED_BY_RE.fullmatch(value["reviewed_by"]) is None
        or value["external_writers_quiescent_affirmed"] is not True
        or value["mutation_platform_profile"] != MUTATION_PLATFORM_PROFILE
        or value["power_loss_durability_verified"] is not False
        or not validate_private_metadata_write_plan(value["plan_binding"])[
            "accepted"
        ]
        or not _is_file_state(value["object_manifest_state"])
        or not _is_file_state(value["private_manifest_before"])
        or not _is_file_state(value["private_manifest_after"])
        or value["intake_schema"] != INTAKE_SCHEMA
        or value["durable_schema"] != DURABLE_SCHEMA
        or not _is_profile(value["normalization_profile"])
        or not _is_nonnegative_integer(value["derived_alias_count"])
        or value["derived_alias_count"] > 1
        or not _is_closed_actions(value["closed_actions"])
    ):
        return _rejected("private_metadata_write_receipt_invalid")
    return _accepted()


def validate_private_metadata_write_receipt_semantics(
    value: Any,
    *,
    canonical_row: Any | None = None,
    expected_archive_id: str | None = None,
    expected_intake_sha256: str | None = None,
    expected_object_manifest_state: Any | None = None,
    expected_private_manifest_before: Any | None = None,
    expected_private_manifest_after: Any | None = None,
) -> dict[str, Any]:
    """Validate internal receipt bindings and optional current authority."""

    if not validate_private_metadata_write_receipt(value)["accepted"]:
        return _rejected(
            "private_metadata_receipt_plan_authority_chain_mismatch"
        )
    plan = value["plan_binding"]
    expected_authority_key = authority_key_sha256(
        value["observation_evidence_sha256"]
    )
    checks = (
        plan["action"] == "append",
        plan["blocked_context"] is None,
        plan["planned_receipt_sha256"] is None,
        validate_private_metadata_write_plan_semantics(
            plan,
            require_final_size_binding=True,
            expected_privacy_class=value["record_privacy_class"],
        )["accepted"],
        value["plan_sha256"] == sha256_digest(canonical_json_bytes(plan)),
        value["authority_chain_before_sha256"]
        == plan["authority_chain_sha256"],
        value["archive_id"] == plan["archive_id"],
        value["object_id"] == plan["object_id"],
        value["authority_key_sha256"] == expected_authority_key,
        value["authority_key_sha256"] == plan["authority_key_sha256"],
        value["intake_sha256"] == plan["intake_sha256"],
        value["canonical_row_sha256"] == plan["canonical_row_sha256"],
        value["observation_evidence_sha256"]
        == plan["observation_evidence_sha256"],
        value["review_evidence_sha256"] == plan["review_evidence_sha256"],
        value["object_manifest_state"] == plan["object_manifest_state"],
        value["private_manifest_before"] == plan["private_manifest_before"],
        value["private_manifest_after"] == plan["private_manifest_after"],
        value["intake_schema"] == plan["intake_schema"],
        value["durable_schema"] == plan["durable_schema"],
        value["normalization_profile"] == plan["normalization_profile"],
        value["derived_alias_count"] == plan["derived_alias_count"],
        expected_archive_id is None
        or value["archive_id"] == expected_archive_id,
        expected_intake_sha256 is None
        or value["intake_sha256"] == expected_intake_sha256,
        expected_object_manifest_state is None
        or value["object_manifest_state"]
        == expected_object_manifest_state,
        expected_private_manifest_before is None
        or value["private_manifest_before"]
        == expected_private_manifest_before,
        expected_private_manifest_after is None
        or value["private_manifest_after"]
        == expected_private_manifest_after,
    )
    if not all(checks):
        return _rejected(
            "private_metadata_receipt_plan_authority_chain_mismatch"
        )
    if canonical_row is not None:
        try:
            row_digest = sha256_digest(canonical_json_bytes(canonical_row))
            row_ok = (
                private_metadata.validate_private_metadata_record(canonical_row)[
                    "accepted"
                ]
                and value["canonical_row_sha256"] == row_digest
                and value["record_privacy_class"]
                == canonical_row["privacy_class"]
                and value["object_id"] == canonical_row["object_id"]
                and value["observation_evidence_sha256"]
                == canonical_row["source_provenance"][
                    "observation_evidence_sha256"
                ]
                and value["normalization_profile"]
                == canonical_row["normalization_profile"]
                and value["derived_alias_count"]
                == len(canonical_row["label_candidates"])
            )
        except (KeyError, TypeError, ValueError):
            row_ok = False
        if not row_ok:
            return _rejected(
                "private_metadata_receipt_plan_authority_chain_mismatch"
            )
    return _accepted()


def parse_private_metadata_write_receipt_bytes(raw: bytes) -> dict[str, Any]:
    def validate_stored_receipt(value: Any) -> dict[str, Any]:
        shape = validate_private_metadata_write_receipt(value)
        if not shape["accepted"]:
            return shape
        return validate_private_metadata_write_receipt_semantics(value)

    return _parse_document(
        raw,
        validator=validate_stored_receipt,
        invalid_code="private_metadata_write_receipt_invalid",
        canonical_storage="stored_json",
        preserve_validation_issue_codes=True,
    )


def validate_private_metadata_write_journal(value: Any) -> dict[str, Any]:
    """Validate the dependency-light closed journal document shape."""

    if _contains_surrogate(value) or not _closed_object(value, _JOURNAL_FIELDS):
        return _rejected("private_metadata_write_journal_invalid")
    if (
        value["schema"] != JOURNAL_SCHEMA
        or value["writer_state_machine_version"]
        != WRITER_STATE_MACHINE_VERSION
        or value["transition"] != "append"
        or not all(
            _is_digest(value[key])
            for key in (
                "plan_sha256",
                "authority_chain_before_sha256",
                "authority_key_sha256",
                "receipt_sha256",
            )
        )
        or type(value["receipt_relative_path"]) is not str
        or _RECEIPT_PATH_RE.fullmatch(value["receipt_relative_path"]) is None
        or not validate_private_metadata_write_receipt(
            value["receipt_document"]
        )["accepted"]
        or not _is_file_state(value["object_manifest_state"])
        or not _is_file_state(value["private_manifest_before"])
        or not _is_file_state(value["private_manifest_after"])
        or type(value["owned_temp_relative_paths"]) is not list
        or len(value["owned_temp_relative_paths"]) != 3
        or type(value["owned_temp_relative_paths"][0]) is not str
        or _JOURNAL_TEMP_PATH_RE.fullmatch(
            value["owned_temp_relative_paths"][0]
        )
        is None
        or type(value["owned_temp_relative_paths"][1]) is not str
        or _MANIFEST_TEMP_PATH_RE.fullmatch(
            value["owned_temp_relative_paths"][1]
        )
        is None
        or type(value["owned_temp_relative_paths"][2]) is not str
        or _RECEIPT_TEMP_PATH_RE.fullmatch(
            value["owned_temp_relative_paths"][2]
        )
        is None
    ):
        return _rejected("private_metadata_write_journal_invalid")
    return _accepted()


def validate_private_metadata_write_journal_semantics(
    value: Any,
    *,
    canonical_row: Any | None = None,
    expected_archive_id: str | None = None,
    expected_intake_sha256: str | None = None,
    expected_object_manifest_state: Any | None = None,
    expected_private_manifest_before: Any | None = None,
    expected_private_manifest_after: Any | None = None,
) -> dict[str, Any]:
    """Validate journal cross-fields and optional current authority."""

    if not validate_private_metadata_write_journal(value)["accepted"]:
        return _rejected("private_metadata_journal_cross_field_mismatch")
    receipt = value["receipt_document"]
    plan = receipt["plan_binding"]
    expected_authority_key = authority_key_sha256(
        receipt["observation_evidence_sha256"]
    )
    checks = (
        validate_private_metadata_write_receipt_semantics(
            receipt,
            canonical_row=canonical_row,
            expected_archive_id=expected_archive_id,
            expected_intake_sha256=expected_intake_sha256,
            expected_object_manifest_state=expected_object_manifest_state,
            expected_private_manifest_before=expected_private_manifest_before,
            expected_private_manifest_after=expected_private_manifest_after,
        )["accepted"],
        value["plan_sha256"] == receipt["plan_sha256"],
        value["plan_sha256"] == sha256_digest(canonical_json_bytes(plan)),
        value["authority_chain_before_sha256"]
        == receipt["authority_chain_before_sha256"],
        value["authority_chain_before_sha256"]
        == plan["authority_chain_sha256"],
        value["authority_key_sha256"] == expected_authority_key,
        value["authority_key_sha256"] == receipt["authority_key_sha256"],
        value["authority_key_sha256"] == plan["authority_key_sha256"],
        value["object_manifest_state"] == receipt["object_manifest_state"],
        value["object_manifest_state"] == plan["object_manifest_state"],
        value["private_manifest_before"]
        == receipt["private_manifest_before"],
        value["private_manifest_before"] == plan["private_manifest_before"],
        value["private_manifest_after"] == receipt["private_manifest_after"],
        value["private_manifest_after"] == plan["private_manifest_after"],
        value["receipt_relative_path"]
        == receipt_relative_path(value["authority_key_sha256"]),
        value["receipt_relative_path"]
        == receipt_relative_path(receipt["authority_key_sha256"]),
        value["receipt_relative_path"] == plan["receipt_relative_path"],
        value["receipt_sha256"] == sha256_digest(stored_json_bytes(receipt)),
        value["owned_temp_relative_paths"]
        == owned_temp_relative_paths(value["authority_key_sha256"]),
        expected_archive_id is None
        or receipt["archive_id"] == expected_archive_id,
        expected_intake_sha256 is None
        or receipt["intake_sha256"] == expected_intake_sha256,
        expected_object_manifest_state is None
        or value["object_manifest_state"]
        == expected_object_manifest_state,
        expected_private_manifest_before is None
        or value["private_manifest_before"]
        == expected_private_manifest_before,
        expected_private_manifest_after is None
        or value["private_manifest_after"]
        == expected_private_manifest_after,
    )
    if not all(checks):
        return _rejected("private_metadata_journal_cross_field_mismatch")
    return _accepted()


def parse_private_metadata_write_journal_bytes(raw: bytes) -> dict[str, Any]:
    def validate_stored_journal(value: Any) -> dict[str, Any]:
        shape = validate_private_metadata_write_journal(value)
        if not shape["accepted"]:
            return shape
        return validate_private_metadata_write_journal_semantics(value)

    return _parse_document(
        raw,
        validator=validate_stored_journal,
        invalid_code="private_metadata_write_journal_invalid",
        canonical_storage="stored_json",
        preserve_validation_issue_codes=True,
    )
