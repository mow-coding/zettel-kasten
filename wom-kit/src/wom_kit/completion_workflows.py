"""Integrated Letters 098-111 completion workflows.

This module keeps the newer locator, normalization, relation-review, and bulk
intake surfaces cohesive while reusing the mature archive primitives in
``archive_services``. Public results never echo private locator values, local
absolute paths, zettel bodies, or exception text.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import stat
import urllib.parse
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from . import archive_services


EXTERNAL_LOCATOR_SCHEMA = "wom-kit/external-locator-record/v0.3"
EXTERNAL_LOCATOR_LEGACY_SCHEMAS = frozenset(
    {
        "wom-kit/external-locator-record/v0.1",
        "wom-kit/external-locator-record/v0.2",
    }
)
EXTERNAL_LOCATOR_RECEIPT_SCHEMA = "wom-kit/external-locator-receipt/v0.4"
EXTERNAL_LOCATOR_LEGACY_RECEIPT_SCHEMAS = frozenset(
    {
        "wom-kit/external-locator-receipt/v0.1",
        "wom-kit/external-locator-receipt/v0.2",
        "wom-kit/external-locator-receipt/v0.3",
    }
)
EXTERNAL_LOCATOR_REVERT_RECEIPT_SCHEMA = (
    "wom-kit/external-locator-revert-receipt/v0.1"
)
EXTERNAL_LOCATOR_DIR = "ops/external-locators"
EXTERNAL_LOCATOR_RECEIPTS_DIR = "receipts/external-locators"
EXTERNAL_LOCATOR_SNAPSHOT_DIR = (
    ".wom-scratch/external-locators/snapshots"
)
EXTERNAL_LOCATOR_TYPES = (
    "source_url",
    "provider_page_id",
    "object_store_key",
    "filesystem_hint",
    "export_coordinate",
    "other",
)
ZETTEL_OBJET_LINK_RECEIPT_SCHEMA = (
    "wom-kit/zettel-objet-link-receipt/v0.1"
)
ZETTEL_OBJET_LINK_REVERT_RECEIPT_SCHEMA = (
    "wom-kit/zettel-objet-link-revert-receipt/v0.1"
)
ZETTEL_OBJET_LINK_RECEIPTS_DIR = "receipts/objects/zettel-links"
ZETTEL_OBJET_LINK_SNAPSHOT_DIR = (
    "receipts/objects/zettel-links/snapshots"
)
ZETTEL_OBJET_ROLE_RE = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
DRAFT_DISCARD_RECEIPT_SCHEMA = "wom-kit/draft-discard-receipt/v0.1"
DRAFT_DISCARD_RESTORE_RECEIPT_SCHEMA = (
    "wom-kit/draft-discard-restore-receipt/v0.1"
)
DRAFT_DISCARD_RECEIPTS_DIR = "receipts/discarded-drafts"
DRAFT_DISCARD_SNAPSHOT_DIR = "receipts/discarded-drafts/snapshots"
OBJET_CAPTURE_BATCH_REQUEST_SCHEMA = (
    "wom-kit/objet-capture-batch-request/v0.1"
)
OBJET_CAPTURE_BATCH_RECEIPT_SCHEMA = (
    "wom-kit/objet-capture-batch-receipt/v0.1"
)
OBJET_CAPTURE_BATCH_RECEIPTS_DIR = "receipts/objet-capture-batches"
OBJET_CAPTURE_BATCH_MAX_ITEMS = 2000
OBJET_CAPTURE_BATCH_TITLE_MAX_CHARACTERS = 2000
MARKUP_NORMALIZATION_PLAN_SCHEMA = (
    "wom-kit/markup-normalization-plan/v0.1"
)
MARKUP_NORMALIZATION_RECEIPT_SCHEMA = (
    "wom-kit/markup-normalization-receipt/v0.1"
)
MARKUP_NORMALIZATION_REVERT_RECEIPT_SCHEMA = (
    "wom-kit/markup-normalization-revert-receipt/v0.1"
)
MARKUP_NORMALIZATION_RECOVERY_RECEIPT_SCHEMA = (
    "wom-kit/markup-normalization-recovery-receipt/v0.1"
)
MARKUP_NORMALIZATION_JOURNAL_SCHEMA = (
    "wom-kit/markup-normalization-journal/v0.1"
)
MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA = (
    "wom-kit/markup-reference-binding-manifest/v0.2"
)
MARKUP_REFERENCE_BINDING_MANIFEST_LEGACY_SCHEMAS = frozenset(
    {"wom-kit/markup-reference-binding-manifest/v0.1"}
)
MARKUP_NORMALIZATION_RECEIPTS_DIR = "receipts/markup-normalization"
MARKUP_NORMALIZATION_SCRATCH_DIR = ".wom-scratch/markup-normalization"
MARKUP_NORMALIZATION_POLICIES = ("preserve", "normalize")
MARKUP_NORMALIZATION_RECOVERY_MODES = ("resume", "rollback")
MARKUP_NORMALIZATION_MAX_ITEMS = 10000
MARKUP_NORMALIZATION_MAX_CHANGES = 5000
_MARKUP_TAG_RE = re.compile(
    r"<\s*(?P<closing>/)?\s*(?P<name>[A-Za-z][A-Za-z0-9:_-]*)"
    r"(?P<attrs>\s+[^<>]*?)?\s*(?P<self>/)?\s*>",
    re.DOTALL,
)
_MARKDOWN_COMPATIBLE_HTML_TAGS = frozenset(
    {
        "a",
        "abbr",
        "b",
        "blockquote",
        "br",
        "code",
        "del",
        "details",
        "em",
        "i",
        "img",
        "kbd",
        "mark",
        "pre",
        "s",
        "small",
        "strong",
        "sub",
        "summary",
        "sup",
    }
)
_TABLE_CELL_PAIRED_INLINE_TAGS = frozenset(
    {
        "a",
        "abbr",
        "b",
        "code",
        "del",
        "em",
        "i",
        "kbd",
        "mark",
        "s",
        "small",
        "strong",
        "sub",
        "sup",
    }
)
_TABLE_CELL_SPAN_ATTRIBUTES = frozenset(
    {"color", "underline", "discussion-urls"}
)
_TABLE_CELL_UNSAFE_URL_SCHEME_RE = re.compile(
    r"(?i)(?:data|file|javascript|vbscript)\s*:"
)
_STRUCTURAL_MARKUP_TAGS = frozenset(
    {"article", "column", "columns", "div", "p", "section"}
)
_REFERENCE_MARKUP_TAGS = frozenset(
    {
        "audio",
        "database",
        "file",
        "media",
        "mention",
        "mention-page",
        "synced-ref",
        "synced_ref",
        "unknown:audio",
        "unknown:synced_block",
        "unknown:transclusion_container",
        "unknown:transclusion_reference",
        "video",
    }
)
_PAIRED_REFERENCE_MARKUP_TAGS = frozenset(
    {"audio", "database", "file", "video"}
)
_UNKNOWN_CONTENT_REFERENCE_MARKUP_TAGS = frozenset(
    {
        "unknown:synced_block",
        "unknown:transclusion_container",
        "unknown:transclusion_reference",
    }
)
_PROTECTED_CONTEXT_MARKUP_TAGS = frozenset(
    {
        "empty-block",
        "mention-date",
        "span",
        "synced_block",
        "synced_block_reference",
        "table",
        "unknown:table_of_contents",
        *_STRUCTURAL_MARKUP_TAGS,
        *_REFERENCE_MARKUP_TAGS,
    }
)
_PROTECTED_CONTEXT_MARKUP_RE = re.compile(
    r"(?is)<\s*/?\s*(?:"
    + "|".join(
        re.escape(name)
        for name in sorted(
            _PROTECTED_CONTEXT_MARKUP_TAGS,
            key=lambda value: (-len(value), value),
        )
    )
    + r")\b"
)


def _public_markup_tag_name(name: str) -> str:
    """Return the stable public spelling for a parsed markup tag name."""
    return "synced-ref" if name == "synced_ref" else name


MARKUP_REFERENCE_BINDING_KINDS = (
    "external_locator",
    "zettel_edge",
    "zettel_reference",
    "objet",
)
RELATION_CANDIDATE_PLAN_SCHEMA = (
    "wom-kit/relation-candidate-plan/v0.1"
)
RELATION_JUDGMENT_SCHEMA = "wom-kit/relation-judgment/v0.1"
RELATION_JUDGMENT_RECEIPT_SCHEMA = (
    "wom-kit/relation-judgment-receipt/v0.1"
)
RELATION_JUDGMENT_DIR = "ops/relation-judgments"
RELATION_JUDGMENT_RECEIPTS_DIR = "receipts/relation-judgments"
RELATION_CANDIDATE_MAX_CANDIDATES = 500
RELATION_DECISIONS = ("accept", "reject")
PRINCIPAL_REGISTRATION_RECEIPT_SCHEMA = (
    "wom-kit/principal-registration-receipt/v0.1"
)
PRINCIPAL_UNREGISTRATION_RECEIPT_SCHEMA = (
    "wom-kit/principal-unregistration-receipt/v0.1"
)
PRINCIPAL_RECEIPTS_DIR = "receipts/principals"
PROJECT_BYTECODE_REPAIR_RECEIPT_SCHEMA = (
    "wom-kit/project-bytecode-repair-receipt/v0.1"
)
PROJECT_BYTECODE_REPAIR_RECEIPTS_DIR = (
    ".zettel-kasten/receipts/project-bytecode-repair"
)
PROJECT_BYTECODE_REPAIR_MAX_FILES = 10000
_SENSITIVE_QUERY_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "credential",
        "password",
        "secret",
        "signature",
        "token",
    }
)


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            archive_services.json_safe(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_locator_ref(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if (
        not text
        or len(text) > 4096
        or any(ord(character) < 32 for character in text)
        or archive_services.source_intake_secret_like(text)
    ):
        return None
    parsed = urllib.parse.urlsplit(text)
    if parsed.scheme:
        if parsed.username is not None or parsed.password is not None:
            return None
        for key, _item in urllib.parse.parse_qsl(
            parsed.query,
            keep_blank_values=True,
        ):
            if key.casefold() in _SENSITIVE_QUERY_KEYS:
                return None
    return text


def _safe_locator_coordinate(
    value: str | None,
    *,
    max_length: int,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    text = value.strip()
    if (
        not text
        or len(text) > max_length
        or any(ord(character) < 32 for character in text)
        or archive_services.source_intake_secret_like(text)
        or archive_services.source_intake_has_provider_url(text)
        or archive_services.contains_forbidden_location_reference(text)
    ):
        return None
    return text


def _safe_zettel_id(value: str | None) -> str | None:
    text = str(value or "").strip()
    if archive_services.ZETTEL_EDGE_ZETTEL_ID_RE.fullmatch(text):
        return text
    return None


def _record_relative(zettel_id: str) -> str:
    return f"{EXTERNAL_LOCATOR_DIR}/{zettel_id}.json"


_EXTERNAL_LOCATOR_ID_RE = re.compile(r"^locator:sha256:[0-9a-f]{64}$")
_EXTERNAL_LOCATOR_RECORD_FIELDS = {
    "schema",
    "archive_id",
    "zettel_id",
    "created_at",
    "updated_at",
    "locators",
}
_EXTERNAL_LOCATOR_ROW_BASE_FIELDS = {
    "locator_id",
    "locator_type",
    "locator_ref",
    "status",
    "recorded_at",
    "reviewed_by",
    "provenance",
}
_EXTERNAL_LOCATOR_ROW_COORDINATE_LIMITS = {
    "service_ref": 120,
    "account_ref": 320,
    "occurrence_anchor": 240,
}


def _locator_internal_path(root: Path, relative_path: str) -> Path:
    """Resolve one locator-owned path without following a lexical reparse hop."""
    try:
        normalized = archive_services.normalize_archive_relative_path(relative_path)
    except Exception as exc:
        raise archive_services.ArchiveServiceError(
            "External locator path is unsafe."
        ) from exc
    lexical_path = root.joinpath(*normalized.split("/"))
    if archive_services.zet_revision_path_has_symlink_component(
        root,
        lexical_path,
    ):
        raise archive_services.ArchiveServiceError(
            "External locator path contains a symlink or reparse point."
        )
    lexical_parent = root
    for part in normalized.split("/")[:-1]:
        lexical_parent = lexical_parent / part
        try:
            parent_stat = os.lstat(lexical_parent)
        except FileNotFoundError:
            break
        except OSError as exc:
            raise archive_services.ArchiveServiceError(
                "External locator path parent is unreadable."
            ) from exc
        if not stat.S_ISDIR(parent_stat.st_mode):
            raise archive_services.ArchiveServiceError(
                "External locator path parent is not a directory."
            )
    return archive_services.archive_internal_path(root, normalized)


def _locator_row_is_valid(item: Any, *, schema: str) -> bool:
    if not isinstance(item, dict):
        return False
    allowed_fields = set(_EXTERNAL_LOCATOR_ROW_BASE_FIELDS)
    if schema != "wom-kit/external-locator-record/v0.1":
        allowed_fields.update(_EXTERNAL_LOCATOR_ROW_COORDINATE_LIMITS)
    if set(item) - allowed_fields or not _EXTERNAL_LOCATOR_ROW_BASE_FIELDS <= set(item):
        return False
    provenance = item.get("provenance")
    allowed_statuses = (
        {"active", "inactive"}
        if schema == EXTERNAL_LOCATOR_SCHEMA
        else {"active"}
    )
    if (
        not isinstance(item.get("locator_id"), str)
        or _EXTERNAL_LOCATOR_ID_RE.fullmatch(item["locator_id"]) is None
        or item.get("locator_type") not in EXTERNAL_LOCATOR_TYPES
        or not isinstance(item.get("locator_ref"), str)
        or not 1 <= len(item["locator_ref"]) <= 4096
        or item.get("status") not in allowed_statuses
        or not isinstance(item.get("recorded_at"), str)
        or not item["recorded_at"]
        or not isinstance(item.get("reviewed_by"), str)
        or not item["reviewed_by"]
        or not isinstance(provenance, dict)
        or set(provenance) != {"source", "automatic_recovery_claimed"}
        or provenance.get("source") != "human_reviewed_cli"
        or provenance.get("automatic_recovery_claimed") is not False
    ):
        return False
    return all(
        field_name not in item
        or (
            isinstance(item[field_name], str)
            and 1 <= len(item[field_name]) <= max_length
        )
        for field_name, max_length in _EXTERNAL_LOCATOR_ROW_COORDINATE_LIMITS.items()
    )


def _locator_record_is_valid(
    value: Any,
    *,
    archive_id: str,
    zettel_id: str,
) -> bool:
    if not isinstance(value, dict) or set(value) != _EXTERNAL_LOCATOR_RECORD_FIELDS:
        return False
    schema = value.get("schema")
    locators = value.get("locators")
    return bool(
        schema in {EXTERNAL_LOCATOR_SCHEMA, *EXTERNAL_LOCATOR_LEGACY_SCHEMAS}
        and value.get("archive_id") == archive_id
        and value.get("zettel_id") == zettel_id
        and isinstance(value.get("created_at"), str)
        and value["created_at"]
        and isinstance(value.get("updated_at"), str)
        and value["updated_at"]
        and isinstance(locators, list)
        and locators
        and all(_locator_row_is_valid(item, schema=schema) for item in locators)
    )


def _locator_record_bytes_are_valid(
    raw: bytes,
    *,
    archive_id: str,
    zettel_id: str,
) -> bool:
    try:
        loaded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    return _locator_record_is_valid(
        loaded,
        archive_id=archive_id,
        zettel_id=zettel_id,
    )


def _locator_snapshot_state(
    root: Path,
    current_bytes: bytes | None,
) -> tuple[Path | None, str | None, bool]:
    """Validate an existing content-addressed snapshot before any lifecycle write."""
    if current_bytes is None:
        return None, None, False
    digest = _sha256_bytes(current_bytes)
    relative = f"{EXTERNAL_LOCATOR_SNAPSHOT_DIR}/{digest}.json"
    try:
        path = _locator_internal_path(root, relative)
    except archive_services.ArchiveServiceError:
        return None, "external_locator_snapshot_unsafe", False
    if not path.exists():
        return path, None, False
    if not path.is_file() or path.is_symlink():
        return path, "external_locator_snapshot_unsafe", True
    try:
        snapshot_bytes = path.read_bytes()
    except OSError:
        return path, "external_locator_snapshot_unreadable", True
    if snapshot_bytes != current_bytes:
        return path, "external_locator_snapshot_mismatch", True
    return path, None, True


def _remove_locator_artifact_if_created(
    path: Path | None,
    *,
    expected_bytes: bytes | None,
    existed_before: bool,
) -> bool:
    if path is None or existed_before:
        return True
    if not path.exists() and not path.is_symlink():
        return True
    if path.is_symlink() or not path.is_file() or expected_bytes is None:
        return False
    try:
        if path.read_bytes() != expected_bytes:
            return False
        path.unlink()
        archive_services.fsync_directory(path.parent)
    except OSError:
        return False
    return not path.exists()


def _rollback_locator_record_write(
    record_path: Path,
    *,
    before_bytes: bytes | None,
    attempted_after_bytes: bytes,
) -> bool:
    try:
        if before_bytes is None:
            if not record_path.exists() and not record_path.is_symlink():
                return True
            if (
                record_path.is_symlink()
                or not record_path.is_file()
                or record_path.read_bytes() != attempted_after_bytes
            ):
                return False
            record_path.unlink()
            archive_services.fsync_directory(record_path.parent)
            return not record_path.exists()
        archive_services.write_bytes_atomic(record_path, before_bytes)
        return record_path.read_bytes() == before_bytes
    except OSError:
        return False


def _receipt_relative(
    action: str,
    zettel_id: str,
    timestamp: str,
    digest: str,
) -> str:
    compact = re.sub(r"[^0-9TZ]", "", timestamp)
    return (
        f"{EXTERNAL_LOCATOR_RECEIPTS_DIR}/"
        f"{action}.{zettel_id}.{compact}.{digest[:16]}.json"
    )


class _LocatorLock:
    def __init__(self, root: Path, zettel_id: str) -> None:
        lock_dir = _locator_internal_path(
            root,
            f"{EXTERNAL_LOCATOR_RECEIPTS_DIR}/.locks",
        )
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_name = hashlib.sha256(zettel_id.encode("utf-8")).hexdigest()
        self._path = lock_dir / f"{lock_name}.lock"
        self._handle: Any = None

    def __enter__(self) -> "_LocatorLock":
        self._handle = self._path.open("a+b")
        self._handle.seek(0, os.SEEK_END)
        if self._handle.tell() == 0:
            self._handle.write(b"\0")
            self._handle.flush()
            os.fsync(self._handle.fileno())
        self._handle.seek(0)
        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    msvcrt.locking(
                        self._handle.fileno(),
                        msvcrt.LK_LOCK,
                        1,
                    )
                    break
                except OSError:
                    continue
        else:
            import fcntl

            fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc_info: Any) -> bool:
        try:
            self._handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(
                    self._handle.fileno(),
                    msvcrt.LK_UNLCK,
                    1,
                )
            else:
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()
        return False


def _read_locator_record(
    root: Path,
    zettel_id: str,
) -> tuple[dict[str, Any] | None, bytes | None, str | None]:
    try:
        path = _locator_internal_path(root, _record_relative(zettel_id))
    except archive_services.ArchiveServiceError:
        return None, None, "external_locator_record_unsafe"
    if not path.exists():
        return None, None, None
    if not path.is_file() or path.is_symlink():
        return None, None, "external_locator_record_unsafe"
    try:
        raw = path.read_bytes()
        loaded = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, None, "external_locator_record_unreadable"
    if not _locator_record_is_valid(
        loaded,
        archive_id=archive_services.read_archive_id(root),
        zettel_id=zettel_id,
    ):
        return None, None, "external_locator_record_invalid"
    return loaded, raw, None


def _locator_plan_core(
    archive_root: Path | str,
    *,
    zettel_id: str | None,
    locator_type: str,
    locator_ref: str | None,
    service_ref: str | None = None,
    account_ref: str | None = None,
    occurrence_anchor: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = archive_services.require_existing_archive_root(archive_root)
    archive_id = archive_services.read_archive_id(root)
    blockers: list[str] = []
    safe_id = _safe_zettel_id(zettel_id)
    if safe_id is None:
        blockers.append("external_locator_zettel_id_invalid")
    normalized_type = str(locator_type or "").strip().lower()
    if normalized_type not in EXTERNAL_LOCATOR_TYPES:
        blockers.append("external_locator_type_invalid")
    safe_ref = _safe_locator_ref(locator_ref)
    if safe_ref is None:
        blockers.append("external_locator_ref_invalid_or_secret_like")
    safe_service_ref = _safe_locator_coordinate(service_ref, max_length=120)
    safe_account_ref = _safe_locator_coordinate(account_ref, max_length=320)
    safe_occurrence_anchor = _safe_locator_coordinate(
        occurrence_anchor,
        max_length=240,
    )
    if service_ref is not None and safe_service_ref is None:
        blockers.append("external_locator_service_ref_invalid_or_secret_like")
    if account_ref is not None and safe_account_ref is None:
        blockers.append("external_locator_account_ref_invalid_or_secret_like")
    if occurrence_anchor is not None and safe_occurrence_anchor is None:
        blockers.append("external_locator_occurrence_anchor_invalid_or_secret_like")

    zettel_path: Path | None = None
    if safe_id is not None:
        try:
            zettel_path = archive_services.resolve_zettel_path(
                root,
                zettel_id=safe_id,
                relative_path=None,
            )
            frontmatter, _body = archive_services.require_readable_zettel_content(
                zettel_path
            )
            if frontmatter.get("status") not in archive_services.ZETTEL_QUERYABLE_STATUSES:
                blockers.append("external_locator_zettel_unavailable")
        except archive_services.ArchiveServiceError:
            blockers.append("external_locator_zettel_unavailable")

    locator_sha256 = (
        _sha256_bytes(safe_ref.encode("utf-8")) if safe_ref is not None else None
    )
    locator_identity = {
        "locator_ref": safe_ref,
        "service_ref": safe_service_ref,
        "account_ref": safe_account_ref,
        "occurrence_anchor": safe_occurrence_anchor,
    }
    locator_identity_sha256 = (
        _sha256_bytes(_canonical_json_bytes(locator_identity))
        if safe_ref is not None
        else None
    )
    locator_id = (
        f"locator:sha256:{locator_identity_sha256}"
        if locator_identity_sha256 is not None
        else None
    )
    current_record: dict[str, Any] | None = None
    current_bytes: bytes | None = None
    record_error: str | None = None
    if safe_id is not None:
        current_record, current_bytes, record_error = _read_locator_record(
            root,
            safe_id,
        )
    if record_error is not None:
        blockers.append(record_error)
    try:
        _locator_internal_path(
            root,
            f"{EXTERNAL_LOCATOR_RECEIPTS_DIR}/.locks/.path-check",
        )
    except archive_services.ArchiveServiceError:
        blockers.append("external_locator_receipt_path_unsafe")
    _snapshot_path, snapshot_error, _snapshot_exists = _locator_snapshot_state(
        root,
        current_bytes,
    )
    if snapshot_error is not None:
        blockers.append(snapshot_error)
    current_locators = (
        current_record.get("locators", [])
        if isinstance(current_record, dict)
        else []
    )
    requested_coordinates = {
        "service_ref": safe_service_ref,
        "account_ref": safe_account_ref,
        "occurrence_anchor": safe_occurrence_anchor,
    }
    matching_reference_indexes = [
        index
        for index, item in enumerate(current_locators)
        if isinstance(item, dict)
        and item.get("locator_type") == normalized_type
        and item.get("locator_ref") == safe_ref
        and item.get("status") == "active"
    ]
    exact_match_indexes = [
        index
        for index in matching_reference_indexes
        if all(
            current_locators[index].get(field_name) == requested_value
            for field_name, requested_value in requested_coordinates.items()
        )
    ]
    occurrence_match_indexes = [
        index
        for index in matching_reference_indexes
        if (
            current_locators[index].get("occurrence_anchor")
            in {None, safe_occurrence_anchor}
            if safe_occurrence_anchor is not None
            else current_locators[index].get("occurrence_anchor") is None
        )
    ]
    planned_action = "add_locator"
    target_locator_index: int | None = None
    target_locator_id = locator_id
    if exact_match_indexes:
        blockers.append("external_locator_already_recorded")
        target_locator_index = exact_match_indexes[0]
        target_locator_id = current_locators[target_locator_index].get(
            "locator_id"
        )
    elif len(occurrence_match_indexes) > 1:
        blockers.append("external_locator_matching_occurrence_ambiguous")
    elif len(occurrence_match_indexes) == 1:
        candidate_index = occurrence_match_indexes[0]
        candidate = current_locators[candidate_index]
        conflicts = [
            field_name
            for field_name, requested_value in requested_coordinates.items()
            if requested_value is not None
            and candidate.get(field_name) is not None
            and candidate.get(field_name) != requested_value
        ]
        additions = [
            field_name
            for field_name, requested_value in requested_coordinates.items()
            if requested_value is not None
            and candidate.get(field_name) is None
        ]
        if conflicts:
            blockers.append("external_locator_coordinate_conflict")
        elif additions:
            planned_action = "update_locator_coordinates"
            target_locator_index = candidate_index
            target_locator_id = candidate.get("locator_id")
        else:
            blockers.append("external_locator_already_recorded")
    elif matching_reference_indexes and safe_occurrence_anchor is None:
        blockers.append("external_locator_matching_occurrence_ambiguous")
    if (
        planned_action == "update_locator_coordinates"
        and (
            not isinstance(target_locator_id, str)
            or re.fullmatch(
                r"locator:sha256:[0-9a-f]{64}",
                target_locator_id,
            )
            is None
        )
    ):
        blockers.append("external_locator_record_invalid")
    target_locator = (
        current_locators[target_locator_index]
        if isinstance(target_locator_index, int)
        and 0 <= target_locator_index < len(current_locators)
        and isinstance(current_locators[target_locator_index], dict)
        else {}
    )
    resulting_coordinate_presence = {
        field_name: (
            requested_value is not None
            or isinstance(target_locator.get(field_name), str)
        )
        for field_name, requested_value in requested_coordinates.items()
    }

    current_sha256 = (
        _sha256_bytes(current_bytes) if current_bytes is not None else None
    )
    plan_binding = {
        "schema": "wom-kit/external-locator-plan-binding/v0.1",
        "archive_id": archive_id,
        "zettel_id": safe_id,
        "locator_type": (
            normalized_type
            if normalized_type in EXTERNAL_LOCATOR_TYPES
            else None
        ),
        "locator_sha256": locator_sha256,
        "locator_identity_sha256": locator_identity_sha256,
        "target_locator_id": target_locator_id,
        "coordinate_presence": {
            "service_ref": safe_service_ref is not None,
            "account_ref": safe_account_ref is not None,
            "occurrence_anchor": safe_occurrence_anchor is not None,
        },
        "current_record_sha256": current_sha256,
        "action": planned_action,
    }
    plan_sha256 = _sha256_bytes(_canonical_json_bytes(plan_binding))
    record_relative = _record_relative(safe_id or "invalid-zettel")
    result = {
        "ok": not blockers,
        "state": "ready" if not blockers else "blocked",
        "dry_run": True,
        "lifecycle_action": "external_locator_plan",
        "archive_id": archive_id,
        "summary": {
            "zettel_id": safe_id,
            "locator_type": (
                normalized_type
                if normalized_type in EXTERNAL_LOCATOR_TYPES
                else None
            ),
            "locator_id": target_locator_id,
            "planned_action": planned_action,
            "coordinate_presence": {
                "service_ref": safe_service_ref is not None,
                "account_ref": safe_account_ref is not None,
                "occurrence_anchor": safe_occurrence_anchor is not None,
            },
            "resulting_coordinate_presence": resulting_coordinate_presence,
            "record_path": record_relative if safe_id else None,
            "current_locator_count": len(current_locators),
            "matching_locator_ref_count": len(matching_reference_indexes),
            "record_exists": current_record is not None,
            "current_record_sha256": current_sha256,
            "plan_sha256": plan_sha256 if not blockers else None,
        },
        "data": {
            "record_schema": EXTERNAL_LOCATOR_SCHEMA,
            "receipt_schema": EXTERNAL_LOCATOR_RECEIPT_SCHEMA,
            "locator_types": list(EXTERNAL_LOCATOR_TYPES),
            "multiple_locators_supported": True,
            "same_locator_multiple_occurrences_supported": True,
            "matching_locator_coordinate_enrichment_in_place": True,
            "coordinate_conflicts_overwritten": False,
            "provider_neutral": True,
            "global_recoverability_claimed": False,
        },
        "blockers": blockers,
        "warnings": [],
        "would_change": [record_relative] if not blockers else [],
        "privacy_guards": {
            "locator_ref_echoed": False,
            "service_ref_echoed": False,
            "account_ref_echoed": False,
            "occurrence_anchor_echoed": False,
            "provider_url_echoed": False,
            "local_absolute_path_echoed": False,
            "zettel_body_echoed": False,
            "network_checked": False,
            "provider_called": False,
            "writes": False,
        },
    }
    private = {
        "root": root,
        "safe_id": safe_id,
        "safe_ref": safe_ref,
        "normalized_type": normalized_type,
        "locator_id": target_locator_id,
        "new_locator_id": locator_id,
        "locator_sha256": locator_sha256,
        "locator_identity_sha256": locator_identity_sha256,
        "safe_service_ref": safe_service_ref,
        "safe_account_ref": safe_account_ref,
        "safe_occurrence_anchor": safe_occurrence_anchor,
        "planned_action": planned_action,
        "target_locator_index": target_locator_index,
        "current_record": current_record,
        "current_bytes": current_bytes,
        "current_sha256": current_sha256,
        "record_relative": record_relative,
        "plan_sha256": plan_sha256,
        "zettel_path": zettel_path,
    }
    return result, private


def external_locator_plan(
    archive_root: Path | str,
    *,
    zettel_id: str | None,
    locator_type: str,
    locator_ref: str | None,
    service_ref: str | None = None,
    account_ref: str | None = None,
    occurrence_anchor: str | None = None,
) -> dict[str, Any]:
    result, _private = _locator_plan_core(
        archive_root,
        zettel_id=zettel_id,
        locator_type=locator_type,
        locator_ref=locator_ref,
        service_ref=service_ref,
        account_ref=account_ref,
        occurrence_anchor=occurrence_anchor,
    )
    return result


def external_locator_record(
    archive_root: Path | str,
    *,
    zettel_id: str | None,
    locator_type: str,
    locator_ref: str | None,
    service_ref: str | None = None,
    account_ref: str | None = None,
    occurrence_anchor: str | None = None,
    expected_plan_sha256: str | None,
    reviewed_by: str | None,
) -> dict[str, Any]:
    result, private = _locator_plan_core(
        archive_root,
        zettel_id=zettel_id,
        locator_type=locator_type,
        locator_ref=locator_ref,
        service_ref=service_ref,
        account_ref=account_ref,
        occurrence_anchor=occurrence_anchor,
    )
    blockers = list(result["blockers"])
    expected = str(expected_plan_sha256 or "").strip().lower()
    reviewer = archive_services.safe_project_intake_actor_id(reviewed_by)
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        blockers.append("external_locator_expected_plan_sha256_invalid")
    elif expected != private["plan_sha256"]:
        blockers.append("external_locator_plan_changed")
    if reviewer is None:
        blockers.append("external_locator_reviewer_invalid")
    if blockers or private["safe_id"] is None:
        return {
            **result,
            "ok": False,
            "state": "blocked",
            "dry_run": False,
            "approved": False,
            "lifecycle_action": "external_locator_record",
            "blockers": archive_services.unique_preserve_order(blockers),
            "would_change": [],
            "files_written": [],
        }

    root: Path = private["root"]
    safe_id: str = private["safe_id"]
    with _LocatorLock(root, safe_id):
        fresh, fresh_private = _locator_plan_core(
            root,
            zettel_id=safe_id,
            locator_type=locator_type,
            locator_ref=locator_ref,
            service_ref=service_ref,
            account_ref=account_ref,
            occurrence_anchor=occurrence_anchor,
        )
        if (
            not fresh["ok"]
            or fresh_private["plan_sha256"] != expected
        ):
            return {
                **fresh,
                "ok": False,
                "state": "blocked",
                "dry_run": False,
                "approved": False,
                "lifecycle_action": "external_locator_record",
                "blockers": archive_services.unique_preserve_order(
                    [
                        *fresh["blockers"],
                        "external_locator_plan_changed",
                    ]
                ),
                "would_change": [],
                "files_written": [],
            }

        timestamp = _now()
        current_record = fresh_private["current_record"]
        locators = (
            list(current_record.get("locators", []))
            if isinstance(current_record, dict)
            else []
        )
        locator_entry = {
                "locator_id": fresh_private["locator_id"],
                "locator_type": fresh_private["normalized_type"],
                "locator_ref": fresh_private["safe_ref"],
                "status": "active",
                "recorded_at": timestamp,
                "reviewed_by": reviewer,
                "provenance": {
                    "source": "human_reviewed_cli",
                    "automatic_recovery_claimed": False,
                },
            }
        for field_name, private_name in (
            ("service_ref", "safe_service_ref"),
            ("account_ref", "safe_account_ref"),
            ("occurrence_anchor", "safe_occurrence_anchor"),
        ):
            if fresh_private[private_name] is not None:
                locator_entry[field_name] = fresh_private[private_name]
        if fresh_private["planned_action"] == "update_locator_coordinates":
            target_index = fresh_private["target_locator_index"]
            if not isinstance(target_index, int) or not 0 <= target_index < len(locators):
                return {
                    **fresh,
                    "ok": False,
                    "state": "blocked",
                    "dry_run": False,
                    "approved": False,
                    "lifecycle_action": "external_locator_record",
                    "blockers": ["external_locator_plan_changed"],
                    "would_change": [],
                    "files_written": [],
                }
            locator_entry = dict(locators[target_index])
            for field_name, private_name in (
                ("service_ref", "safe_service_ref"),
                ("account_ref", "safe_account_ref"),
                ("occurrence_anchor", "safe_occurrence_anchor"),
            ):
                if fresh_private[private_name] is not None:
                    locator_entry[field_name] = fresh_private[private_name]
            locators[target_index] = locator_entry
        else:
            locators.append(locator_entry)
        record = {
            "schema": EXTERNAL_LOCATOR_SCHEMA,
            "archive_id": archive_services.read_archive_id(root),
            "zettel_id": safe_id,
            "created_at": (
                current_record.get("created_at")
                if isinstance(current_record, dict)
                else timestamp
            ),
            "updated_at": timestamp,
            "locators": locators,
        }
        record_bytes = _canonical_json_bytes(record)
        after_sha256 = _sha256_bytes(record_bytes)
        snapshot_relative: str | None = None
        snapshot_path: Path | None = None
        if fresh_private["current_bytes"] is not None:
            before_sha256 = fresh_private["current_sha256"]
            snapshot_relative = (
                f"{EXTERNAL_LOCATOR_SNAPSHOT_DIR}/{before_sha256}.json"
            )
            snapshot_path = _locator_internal_path(
                root,
                snapshot_relative,
            )
        receipt_relative = _receipt_relative(
            "record",
            safe_id,
            timestamp,
            after_sha256,
        )
        receipt_path = _locator_internal_path(
            root,
            receipt_relative,
        )
        record_path = _locator_internal_path(
            root,
            fresh_private["record_relative"],
        )
        receipt = {
            "schema": EXTERNAL_LOCATOR_RECEIPT_SCHEMA,
            "action": fresh_private["planned_action"],
            "archive_id": archive_services.read_archive_id(root),
            "zettel_id": safe_id,
            "locator_id": fresh_private["locator_id"],
            "locator_type": fresh_private["normalized_type"],
            "coordinate_presence": fresh["summary"]["coordinate_presence"],
            "plan_sha256": expected,
            "before_record_sha256": fresh_private["current_sha256"],
            "after_record_sha256": after_sha256,
            "before_snapshot_path": snapshot_relative,
            "record_path": fresh_private["record_relative"],
            "reviewed_by": reviewer,
            "created_at": timestamp,
            "privacy": {
                "locator_ref_included": False,
                "provider_called": False,
                "network_checked": False,
            },
        }
        receipt_bytes = _canonical_json_bytes(receipt)
        snapshot_preexisting = bool(
            snapshot_path is not None and snapshot_path.exists()
        )
        receipt_preexisting = receipt_path.exists() or receipt_path.is_symlink()
        record_write_attempted = False
        try:
            if (
                snapshot_path is not None
                and not snapshot_path.exists()
                and fresh_private["current_bytes"] is not None
            ):
                archive_services._write_bytes_create_if_absent(
                    snapshot_path,
                    fresh_private["current_bytes"],
                )
            archive_services._write_bytes_create_if_absent(
                receipt_path,
                receipt_bytes,
            )
            record_write_attempted = True
            archive_services.write_bytes_atomic(record_path, record_bytes)
            archive_services.fsync_directory(record_path.parent)
        except OSError:
            rollback_ok = _remove_locator_artifact_if_created(
                receipt_path,
                expected_bytes=receipt_bytes,
                existed_before=receipt_preexisting,
            )
            rollback_ok = (
                _remove_locator_artifact_if_created(
                    snapshot_path,
                    expected_bytes=fresh_private["current_bytes"],
                    existed_before=snapshot_preexisting,
                )
                and rollback_ok
            )
            if record_write_attempted:
                rollback_ok = (
                    _rollback_locator_record_write(
                        record_path,
                        before_bytes=fresh_private["current_bytes"],
                        attempted_after_bytes=record_bytes,
                    )
                    and rollback_ok
                )
            write_blockers = ["external_locator_write_failed"]
            if not rollback_ok:
                write_blockers.append("external_locator_rollback_failed")
            return {
                **fresh,
                "ok": False,
                "state": "blocked",
                "dry_run": False,
                "approved": False,
                "lifecycle_action": "external_locator_record",
                "blockers": write_blockers,
                "would_change": [],
                "files_written": [],
            }

    return {
        **fresh,
        "ok": True,
        "state": "written",
        "dry_run": False,
        "approved": True,
        "lifecycle_action": "external_locator_record",
        "summary": {
            **fresh["summary"],
            "current_locator_count": len(locators),
            "current_record_sha256": after_sha256,
            "receipt_path": receipt_relative,
        },
        "blockers": [],
        "would_change": [],
        "files_written": [
            fresh_private["record_relative"],
            receipt_relative,
        ],
        "privacy_guards": {
            **fresh["privacy_guards"],
            "writes": True,
        },
    }


def _external_locator_deactivate_plan_core(
    archive_root: Path | str,
    *,
    zettel_id: str | None,
    locator_id: str | None,
    keep_locator_id: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = archive_services.require_existing_archive_root(archive_root)
    archive_id = archive_services.read_archive_id(root)
    blockers: list[str] = []
    safe_id = _safe_zettel_id(zettel_id)
    if safe_id is None:
        blockers.append("external_locator_zettel_id_invalid")
    locator_id_pattern = r"locator:sha256:[0-9a-f]{64}"
    raw_locator_id = str(locator_id or "").strip().lower()
    raw_keep_locator_id = str(keep_locator_id or "").strip().lower()
    safe_locator_id = (
        raw_locator_id
        if re.fullmatch(locator_id_pattern, raw_locator_id)
        else None
    )
    safe_keep_locator_id = (
        raw_keep_locator_id
        if re.fullmatch(locator_id_pattern, raw_keep_locator_id)
        else None
    )
    if safe_locator_id is None:
        blockers.append("external_locator_deactivate_locator_id_invalid")
    if safe_keep_locator_id is None:
        blockers.append("external_locator_deactivate_keep_locator_id_invalid")
    if (
        safe_locator_id is not None
        and safe_keep_locator_id is not None
        and safe_locator_id == safe_keep_locator_id
    ):
        blockers.append("external_locator_deactivate_ids_must_differ")

    zettel_bytes: bytes | None = None
    zettel_body: str | None = None
    if safe_id is not None:
        try:
            zettel_path = archive_services.resolve_zettel_path(
                root,
                zettel_id=safe_id,
                relative_path=None,
            )
            zettel_bytes = zettel_path.read_bytes()
            zettel_text = archive_services.decode_utf8_with_universal_newlines(
                zettel_bytes
            )
            frontmatter, zettel_body = (
                archive_services.require_readable_zettel_text(zettel_text)
            )
            if (
                frontmatter.get("status")
                not in archive_services.ZETTEL_QUERYABLE_STATUSES
            ):
                blockers.append("external_locator_zettel_unavailable")
        except (archive_services.ArchiveServiceError, OSError, UnicodeError):
            blockers.append("external_locator_zettel_unavailable")

    current_record: dict[str, Any] | None = None
    current_bytes: bytes | None = None
    if safe_id is not None:
        current_record, current_bytes, record_error = _read_locator_record(
            root,
            safe_id,
        )
        if record_error is not None:
            blockers.append(record_error)
    try:
        _locator_internal_path(
            root,
            f"{EXTERNAL_LOCATOR_RECEIPTS_DIR}/.locks/.path-check",
        )
    except archive_services.ArchiveServiceError:
        blockers.append("external_locator_receipt_path_unsafe")
    _snapshot_path, snapshot_error, _snapshot_exists = _locator_snapshot_state(
        root,
        current_bytes,
    )
    if snapshot_error is not None:
        blockers.append(snapshot_error)
    current_locators = (
        current_record.get("locators", [])
        if isinstance(current_record, dict)
        else []
    )
    locator_row_fields = {
        "locator_id",
        "locator_type",
        "locator_ref",
        "service_ref",
        "account_ref",
        "occurrence_anchor",
        "status",
        "recorded_at",
        "reviewed_by",
        "provenance",
    }

    def locator_row_is_valid(item: Any) -> bool:
        if not isinstance(item, dict) or set(item) - locator_row_fields:
            return False
        provenance = item.get("provenance")
        if (
            re.fullmatch(locator_id_pattern, str(item.get("locator_id") or ""))
            is None
            or item.get("locator_type") not in EXTERNAL_LOCATOR_TYPES
            or not isinstance(item.get("locator_ref"), str)
            or not 1 <= len(item["locator_ref"]) <= 4096
            or item.get("status") not in {"active", "inactive"}
            or not isinstance(item.get("recorded_at"), str)
            or not item["recorded_at"]
            or not isinstance(item.get("reviewed_by"), str)
            or not item["reviewed_by"]
            or not isinstance(provenance, dict)
            or set(provenance) != {
                "source",
                "automatic_recovery_claimed",
            }
            or provenance.get("source") != "human_reviewed_cli"
            or provenance.get("automatic_recovery_claimed") is not False
        ):
            return False
        return all(
            field_name not in item
            or (
                isinstance(item[field_name], str)
                and 1 <= len(item[field_name]) <= max_length
            )
            for field_name, max_length in (
                ("service_ref", 120),
                ("account_ref", 320),
                ("occurrence_anchor", 240),
            )
        )

    record_fields = {
        "schema",
        "archive_id",
        "zettel_id",
        "created_at",
        "updated_at",
        "locators",
    }
    if isinstance(current_record, dict) and (
        set(current_record) != record_fields
        or current_record.get("archive_id") != archive_id
        or not isinstance(current_record.get("created_at"), str)
        or not current_record.get("created_at")
        or not isinstance(current_record.get("updated_at"), str)
        or not current_record.get("updated_at")
    ):
        blockers.append("external_locator_record_invalid")
    if any(not locator_row_is_valid(item) for item in current_locators):
        blockers.append("external_locator_record_invalid")

    def rows_for_id(candidate_id: str | None) -> list[tuple[int, dict[str, Any]]]:
        if candidate_id is None:
            return []
        return [
            (index, item)
            for index, item in enumerate(current_locators)
            if isinstance(item, dict) and item.get("locator_id") == candidate_id
        ]

    target_rows = rows_for_id(safe_locator_id)
    keeper_rows = rows_for_id(safe_keep_locator_id)
    active_target_rows = [
        row for row in target_rows if row[1].get("status") == "active"
    ]
    active_keeper_rows = [
        row for row in keeper_rows if row[1].get("status") == "active"
    ]
    if safe_locator_id is not None:
        if not target_rows:
            blockers.append("external_locator_deactivate_target_missing")
        elif len(target_rows) != 1:
            blockers.append("external_locator_deactivate_target_ambiguous")
        elif not active_target_rows:
            blockers.append("external_locator_deactivate_target_inactive")
    if safe_keep_locator_id is not None:
        if not keeper_rows:
            blockers.append("external_locator_deactivate_keeper_missing")
        elif len(keeper_rows) != 1:
            blockers.append("external_locator_deactivate_keeper_ambiguous")
        elif not active_keeper_rows:
            blockers.append("external_locator_deactivate_keeper_inactive")

    target_index: int | None = None
    target_row: dict[str, Any] = {}
    keeper_row: dict[str, Any] = {}
    if len(active_target_rows) == 1:
        target_index, target_row = active_target_rows[0]
    if len(active_keeper_rows) == 1:
        _keeper_index, keeper_row = active_keeper_rows[0]
    if target_row and keeper_row:
        if (
            target_row.get("locator_type") != keeper_row.get("locator_type")
            or target_row.get("locator_ref") != keeper_row.get("locator_ref")
        ):
            blockers.append("external_locator_deactivate_ref_type_mismatch")
        if target_row.get("occurrence_anchor") != keeper_row.get(
            "occurrence_anchor"
        ):
            blockers.append("external_locator_deactivate_occurrence_mismatch")
        if any(
            target_row.get(field_name) is not None
            and keeper_row.get(field_name) != target_row.get(field_name)
            for field_name in ("service_ref", "account_ref")
        ):
            blockers.append("external_locator_deactivate_coordinate_conflict")
    if safe_locator_id is not None and isinstance(zettel_body, str):
        target_digest = safe_locator_id.removeprefix("locator:sha256:")
        if (
            f"wom-locator://sha256/{target_digest}".casefold()
            in zettel_body.casefold()
        ):
            blockers.append("external_locator_deactivate_target_referenced")

    current_sha256 = (
        _sha256_bytes(current_bytes) if current_bytes is not None else None
    )
    zettel_sha256 = (
        _sha256_bytes(zettel_bytes) if zettel_bytes is not None else None
    )
    plan_binding = {
        "schema": "wom-kit/external-locator-deactivate-plan-binding/v0.1",
        "archive_id": archive_id,
        "zettel_id": safe_id,
        "locator_id": safe_locator_id,
        "keep_locator_id": safe_keep_locator_id,
        "current_record_sha256": current_sha256,
        "canonical_zettel_sha256": zettel_sha256,
        "action": "deactivate_duplicate_locator",
    }
    plan_sha256 = _sha256_bytes(_canonical_json_bytes(plan_binding))
    aggregate = archive_services.unique_preserve_order(blockers)
    record_relative = _record_relative(safe_id or "invalid-zettel")

    def coordinate_presence(row: dict[str, Any]) -> dict[str, bool]:
        return {
            field_name: isinstance(row.get(field_name), str)
            for field_name in (
                "service_ref",
                "account_ref",
                "occurrence_anchor",
            )
        }

    result = {
        "ok": not aggregate,
        "state": "ready" if not aggregate else "blocked",
        "dry_run": True,
        "lifecycle_action": "external_locator_deactivate_plan",
        "archive_id": archive_id,
        "summary": {
            "zettel_id": safe_id,
            "locator_id": safe_locator_id,
            "kept_locator_id": safe_keep_locator_id,
            "locator_type": (
                target_row.get("locator_type") if target_row else None
            ),
            "planned_action": "deactivate_duplicate_locator",
            "coordinate_presence": coordinate_presence(target_row),
            "kept_coordinate_presence": coordinate_presence(keeper_row),
            "record_path": record_relative if safe_id else None,
            "current_locator_count": len(current_locators),
            "active_locator_count": sum(
                1
                for item in current_locators
                if isinstance(item, dict) and item.get("status") == "active"
            ),
            "inactive_locator_count": sum(
                1
                for item in current_locators
                if isinstance(item, dict) and item.get("status") == "inactive"
            ),
            "current_record_sha256": current_sha256,
            "plan_sha256": plan_sha256 if not aggregate else None,
        },
        "data": {
            "record_schema": EXTERNAL_LOCATOR_SCHEMA,
            "receipt_schema": EXTERNAL_LOCATOR_RECEIPT_SCHEMA,
            "dedupe_only": True,
            "rows_deleted": False,
            "provider_called": False,
        },
        "blockers": aggregate,
        "warnings": [],
        "would_change": [record_relative] if not aggregate else [],
        "files_written": [],
        "privacy_guards": {
            "locator_ref_echoed": False,
            "service_ref_echoed": False,
            "account_ref_echoed": False,
            "occurrence_anchor_echoed": False,
            "provider_url_echoed": False,
            "local_absolute_path_echoed": False,
            "zettel_body_echoed": False,
            "exception_echoed": False,
            "network_checked": False,
            "provider_called": False,
            "writes": False,
        },
    }
    private = {
        "root": root,
        "safe_id": safe_id,
        "safe_locator_id": safe_locator_id,
        "safe_keep_locator_id": safe_keep_locator_id,
        "target_index": target_index,
        "target_row": target_row,
        "keeper_row": keeper_row,
        "current_record": current_record,
        "current_bytes": current_bytes,
        "current_sha256": current_sha256,
        "record_relative": record_relative,
        "plan_sha256": plan_sha256,
    }
    return result, private


def external_locator_deactivate_plan(
    archive_root: Path | str,
    *,
    zettel_id: str | None,
    locator_id: str | None,
    keep_locator_id: str | None,
) -> dict[str, Any]:
    result, _private = _external_locator_deactivate_plan_core(
        archive_root,
        zettel_id=zettel_id,
        locator_id=locator_id,
        keep_locator_id=keep_locator_id,
    )
    return result


def external_locator_deactivate(
    archive_root: Path | str,
    *,
    zettel_id: str | None,
    locator_id: str | None,
    keep_locator_id: str | None,
    expected_plan_sha256: str | None,
    reviewed_by: str | None,
) -> dict[str, Any]:
    result, private = _external_locator_deactivate_plan_core(
        archive_root,
        zettel_id=zettel_id,
        locator_id=locator_id,
        keep_locator_id=keep_locator_id,
    )
    blockers = list(result["blockers"])
    expected = str(expected_plan_sha256 or "").strip().lower()
    reviewer = archive_services.safe_project_intake_actor_id(reviewed_by)
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        blockers.append(
            "external_locator_deactivate_expected_plan_sha256_invalid"
        )
    elif expected != private["plan_sha256"]:
        blockers.append("external_locator_deactivate_plan_changed")
    if reviewer is None:
        blockers.append("external_locator_deactivate_reviewer_invalid")
    if blockers or private["safe_id"] is None:
        return {
            **result,
            "ok": False,
            "state": "blocked",
            "dry_run": False,
            "approved": False,
            "lifecycle_action": "external_locator_deactivate",
            "blockers": archive_services.unique_preserve_order(blockers),
            "would_change": [],
            "files_written": [],
        }

    root: Path = private["root"]
    safe_id: str = private["safe_id"]
    with _LocatorLock(root, safe_id):
        fresh, fresh_private = _external_locator_deactivate_plan_core(
            root,
            zettel_id=safe_id,
            locator_id=locator_id,
            keep_locator_id=keep_locator_id,
        )
        if not fresh["ok"] or fresh_private["plan_sha256"] != expected:
            return {
                **fresh,
                "ok": False,
                "state": "blocked",
                "dry_run": False,
                "approved": False,
                "lifecycle_action": "external_locator_deactivate",
                "blockers": archive_services.unique_preserve_order(
                    [
                        *fresh["blockers"],
                        "external_locator_deactivate_plan_changed",
                    ]
                ),
                "would_change": [],
                "files_written": [],
            }

        current_record = fresh_private["current_record"]
        target_index = fresh_private["target_index"]
        if (
            not isinstance(current_record, dict)
            or not isinstance(target_index, int)
        ):
            return {
                **fresh,
                "ok": False,
                "state": "blocked",
                "dry_run": False,
                "approved": False,
                "lifecycle_action": "external_locator_deactivate",
                "blockers": ["external_locator_deactivate_plan_changed"],
                "would_change": [],
                "files_written": [],
            }
        locators = [
            dict(item) for item in current_record.get("locators", [])
        ]
        if (
            not 0 <= target_index < len(locators)
            or locators[target_index].get("status") != "active"
        ):
            return {
                **fresh,
                "ok": False,
                "state": "blocked",
                "dry_run": False,
                "approved": False,
                "lifecycle_action": "external_locator_deactivate",
                "blockers": ["external_locator_deactivate_plan_changed"],
                "would_change": [],
                "files_written": [],
            }

        timestamp = _now()
        target_row = dict(locators[target_index])
        target_row["status"] = "inactive"
        locators[target_index] = target_row
        record = dict(current_record)
        record["schema"] = EXTERNAL_LOCATOR_SCHEMA
        record["updated_at"] = timestamp
        record["locators"] = locators
        record_bytes = _canonical_json_bytes(record)
        after_sha256 = _sha256_bytes(record_bytes)
        before_sha256 = fresh_private["current_sha256"]
        snapshot_relative = (
            f"{EXTERNAL_LOCATOR_SNAPSHOT_DIR}/{before_sha256}.json"
        )
        snapshot_path = _locator_internal_path(
            root,
            snapshot_relative,
        )
        receipt_relative = _receipt_relative(
            "deactivate",
            safe_id,
            timestamp,
            after_sha256,
        )
        receipt_path = _locator_internal_path(
            root,
            receipt_relative,
        )
        record_path = _locator_internal_path(
            root,
            fresh_private["record_relative"],
        )
        coordinate_presence = {
            field_name: isinstance(
                fresh_private["target_row"].get(field_name),
                str,
            )
            for field_name in (
                "service_ref",
                "account_ref",
                "occurrence_anchor",
            )
        }
        receipt = {
            "schema": EXTERNAL_LOCATOR_RECEIPT_SCHEMA,
            "action": "deactivate_duplicate_locator",
            "archive_id": archive_services.read_archive_id(root),
            "zettel_id": safe_id,
            "locator_id": fresh_private["safe_locator_id"],
            "kept_locator_id": fresh_private["safe_keep_locator_id"],
            "locator_type": fresh_private["target_row"].get("locator_type"),
            "coordinate_presence": coordinate_presence,
            "previous_status": "active",
            "new_status": "inactive",
            "plan_sha256": expected,
            "before_record_sha256": before_sha256,
            "after_record_sha256": after_sha256,
            "before_snapshot_path": snapshot_relative,
            "record_path": fresh_private["record_relative"],
            "reviewed_by": reviewer,
            "created_at": timestamp,
            "privacy": {
                "locator_ref_included": False,
                "provider_called": False,
                "network_checked": False,
            },
        }
        receipt_bytes = _canonical_json_bytes(receipt)
        snapshot_preexisting = snapshot_path.exists()
        receipt_preexisting = receipt_path.exists() or receipt_path.is_symlink()
        record_write_attempted = False
        try:
            if not snapshot_path.exists():
                archive_services._write_bytes_create_if_absent(
                    snapshot_path,
                    fresh_private["current_bytes"],
                )
            archive_services._write_bytes_create_if_absent(
                receipt_path,
                receipt_bytes,
            )
            record_write_attempted = True
            archive_services.write_bytes_atomic(record_path, record_bytes)
            archive_services.fsync_directory(record_path.parent)
        except OSError:
            rollback_ok = _remove_locator_artifact_if_created(
                receipt_path,
                expected_bytes=receipt_bytes,
                existed_before=receipt_preexisting,
            )
            rollback_ok = (
                _remove_locator_artifact_if_created(
                    snapshot_path,
                    expected_bytes=fresh_private["current_bytes"],
                    existed_before=snapshot_preexisting,
                )
                and rollback_ok
            )
            if record_write_attempted:
                rollback_ok = (
                    _rollback_locator_record_write(
                        record_path,
                        before_bytes=fresh_private["current_bytes"],
                        attempted_after_bytes=record_bytes,
                    )
                    and rollback_ok
                )
            write_blockers = ["external_locator_deactivate_write_failed"]
            if not rollback_ok:
                write_blockers.append(
                    "external_locator_deactivate_rollback_failed"
                )
            return {
                **fresh,
                "ok": False,
                "state": "blocked",
                "dry_run": False,
                "approved": False,
                "lifecycle_action": "external_locator_deactivate",
                "blockers": write_blockers,
                "would_change": [],
                "files_written": [],
            }

    return {
        **fresh,
        "ok": True,
        "state": "written",
        "dry_run": False,
        "approved": True,
        "lifecycle_action": "external_locator_deactivate",
        "summary": {
            **fresh["summary"],
            "active_locator_count": sum(
                1 for item in locators if item.get("status") == "active"
            ),
            "inactive_locator_count": sum(
                1 for item in locators if item.get("status") == "inactive"
            ),
            "current_record_sha256": after_sha256,
            "receipt_path": receipt_relative,
        },
        "blockers": [],
        "would_change": [],
        "files_written": [
            fresh_private["record_relative"],
            receipt_relative,
        ],
        "privacy_guards": {
            **fresh["privacy_guards"],
            "writes": True,
        },
    }


def external_locator_recovery_plan(
    archive_root: Path | str,
    *,
    zettel_id: str | None,
) -> dict[str, Any]:
    root = archive_services.require_existing_archive_root(archive_root)
    archive_id = archive_services.read_archive_id(root)
    safe_id = _safe_zettel_id(zettel_id)
    blockers: list[str] = []
    if safe_id is None:
        blockers.append("external_locator_zettel_id_invalid")
    record: dict[str, Any] | None = None
    record_bytes: bytes | None = None
    if safe_id is not None:
        record, record_bytes, error = _read_locator_record(root, safe_id)
        if error:
            blockers.append(error)
    locators = (
        record.get("locators", [])
        if isinstance(record, dict)
        else []
    )
    projections = [
        {
            "locator_id": item.get("locator_id"),
            "locator_type": item.get("locator_type"),
            "status": item.get("status"),
            "coordinate_presence": {
                "service_ref": isinstance(item.get("service_ref"), str),
                "account_ref": isinstance(item.get("account_ref"), str),
                "occurrence_anchor": isinstance(item.get("occurrence_anchor"), str),
            },
        }
        for item in locators
        if isinstance(item, dict)
    ]
    active_locator_count = sum(
        1 for item in projections if item["status"] == "active"
    )
    inactive_locator_count = sum(
        1 for item in projections if item["status"] == "inactive"
    )
    all_inactive = bool(projections) and active_locator_count == 0
    state = (
        "blocked"
        if blockers
        else "unresolved"
        if not projections
        else "all_candidates_inactive"
        if all_inactive
        else "candidates_available"
    )
    return {
        "ok": not blockers,
        "state": state,
        "dry_run": True,
        "lifecycle_action": "external_locator_recovery_plan",
        "archive_id": archive_id,
        "summary": {
            "zettel_id": safe_id,
            "record_exists": record is not None,
            "record_sha256": (
                _sha256_bytes(record_bytes)
                if record_bytes is not None
                else None
            ),
            "locator_count": len(projections),
            "active_locator_count": active_locator_count,
            "inactive_locator_count": inactive_locator_count,
            "all_inactive": all_inactive,
            "multiple_locators": len(projections) > 1,
        },
        "locators": projections,
        "truth_boundaries": {
            "locator_presence_proves_remote_reachability": False,
            "provider_checked": False,
            "network_checked": False,
            "global_recoverability_claimed": False,
            "human_selection_required_before_use": True,
        },
        "blockers": blockers,
        "warnings": (
            ["No recorded locator candidates are available."]
            if not blockers and not projections
            else ["All recorded locator candidates are inactive."]
            if not blockers and all_inactive
            else []
        ),
        "would_change": [],
        "privacy_guards": {
            "locator_ref_echoed": False,
            "service_ref_echoed": False,
            "account_ref_echoed": False,
            "occurrence_anchor_echoed": False,
            "provider_url_echoed": False,
            "local_absolute_path_echoed": False,
            "zettel_body_echoed": False,
            "writes": False,
        },
    }


_EXTERNAL_LOCATOR_RECEIPT_COMMON_FIELDS = {
    "schema",
    "action",
    "archive_id",
    "zettel_id",
    "locator_id",
    "locator_type",
    "plan_sha256",
    "before_record_sha256",
    "after_record_sha256",
    "before_snapshot_path",
    "record_path",
    "reviewed_by",
    "created_at",
    "privacy",
}
_EXTERNAL_LOCATOR_RECEIPT_ACTIONS = {
    "wom-kit/external-locator-receipt/v0.1": {"add_locator"},
    "wom-kit/external-locator-receipt/v0.2": {"add_locator"},
    "wom-kit/external-locator-receipt/v0.3": {
        "add_locator",
        "update_locator_coordinates",
    },
    EXTERNAL_LOCATOR_RECEIPT_SCHEMA: {
        "add_locator",
        "update_locator_coordinates",
        "deactivate_duplicate_locator",
    },
}
_EXTERNAL_LOCATOR_DEACTIVATE_RECEIPT_FIELDS = {
    "kept_locator_id",
    "previous_status",
    "new_status",
}


def _external_locator_receipt_is_valid(
    value: Any,
    *,
    archive_id: str,
) -> bool:
    if not isinstance(value, dict):
        return False
    schema = value.get("schema")
    action = value.get("action")
    allowed_actions = _EXTERNAL_LOCATOR_RECEIPT_ACTIONS.get(schema)
    zettel_id = _safe_zettel_id(value.get("zettel_id"))
    if allowed_actions is None or action not in allowed_actions or zettel_id is None:
        return False
    required_fields = set(_EXTERNAL_LOCATOR_RECEIPT_COMMON_FIELDS)
    allowed_fields = set(required_fields)
    if schema != "wom-kit/external-locator-receipt/v0.1":
        required_fields.add("coordinate_presence")
        allowed_fields.add("coordinate_presence")
    if schema == EXTERNAL_LOCATOR_RECEIPT_SCHEMA:
        allowed_fields.update(_EXTERNAL_LOCATOR_DEACTIVATE_RECEIPT_FIELDS)
    if not required_fields <= set(value) or set(value) - allowed_fields:
        return False
    if action == "deactivate_duplicate_locator":
        if not _EXTERNAL_LOCATOR_DEACTIVATE_RECEIPT_FIELDS <= set(value):
            return False
        if (
            not isinstance(value.get("kept_locator_id"), str)
            or _EXTERNAL_LOCATOR_ID_RE.fullmatch(value["kept_locator_id"]) is None
            or value.get("previous_status") != "active"
            or value.get("new_status") != "inactive"
        ):
            return False
    elif set(value) & _EXTERNAL_LOCATOR_DEACTIVATE_RECEIPT_FIELDS:
        return False

    coordinate_presence = value.get("coordinate_presence")
    if schema == "wom-kit/external-locator-receipt/v0.1":
        if coordinate_presence is not None:
            return False
    elif (
        not isinstance(coordinate_presence, dict)
        or set(coordinate_presence)
        != {"service_ref", "account_ref", "occurrence_anchor"}
        or any(type(item) is not bool for item in coordinate_presence.values())
    ):
        return False

    before_sha256 = value.get("before_record_sha256")
    after_sha256 = value.get("after_record_sha256")
    plan_sha256 = value.get("plan_sha256")
    if before_sha256 is not None and (
        not isinstance(before_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", before_sha256) is None
    ):
        return False
    if (
        not isinstance(after_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", after_sha256) is None
        or not isinstance(plan_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", plan_sha256) is None
    ):
        return False
    expected_snapshot = (
        f"{EXTERNAL_LOCATOR_SNAPSHOT_DIR}/{before_sha256}.json"
        if before_sha256 is not None
        else None
    )
    if value.get("before_snapshot_path") != expected_snapshot:
        return False
    if before_sha256 is None and action != "add_locator":
        return False
    if value.get("record_path") != _record_relative(zettel_id):
        return False

    privacy = value.get("privacy")
    return bool(
        value.get("archive_id") == archive_id
        and isinstance(value.get("locator_id"), str)
        and _EXTERNAL_LOCATOR_ID_RE.fullmatch(value["locator_id"]) is not None
        and value.get("locator_type") in EXTERNAL_LOCATOR_TYPES
        and isinstance(value.get("reviewed_by"), str)
        and value["reviewed_by"]
        and isinstance(value.get("created_at"), str)
        and value["created_at"]
        and isinstance(privacy, dict)
        and set(privacy)
        == {"locator_ref_included", "provider_called", "network_checked"}
        and privacy.get("locator_ref_included") is False
        and privacy.get("provider_called") is False
        and privacy.get("network_checked") is False
    )


def _resolve_locator_receipt_input(
    root: Path,
    value: Path | str,
) -> tuple[Path | None, str | None]:
    raw = os.fspath(value).strip()
    if not raw:
        return None, "input_path_invalid"
    candidate = Path(raw).expanduser()
    try:
        receipt_root = _locator_internal_path(
            root,
            EXTERNAL_LOCATOR_RECEIPTS_DIR,
        )
        lexical_receipt_root = root.joinpath(
            *EXTERNAL_LOCATOR_RECEIPTS_DIR.split("/")
        )
        if candidate.is_absolute():
            lexical_path = candidate
            lexical_root = Path(candidate.anchor).resolve()
        else:
            normalized = archive_services.normalize_archive_relative_path(raw)
            lexical_path = root.joinpath(*normalized.split("/"))
            lexical_root = root
            lexical_path.relative_to(lexical_receipt_root)
        if archive_services.zet_revision_path_has_symlink_component(
            lexical_root,
            lexical_path,
        ):
            return None, "input_path_unsafe"
    except Exception:
        return None, "input_path_invalid"
    path, path_error = _resolve_json_input(root, value)
    if path_error is not None or path is None:
        return path, path_error
    try:
        path.relative_to(receipt_root)
        path_stat = os.lstat(path)
    except (OSError, ValueError):
        return None, "input_path_invalid"
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if (
        not stat.S_ISREG(path_stat.st_mode)
        or (
            reparse_flag
            and getattr(path_stat, "st_file_attributes", 0) & reparse_flag
        )
    ):
        return None, "input_path_unsafe"
    return path, None


def _external_locator_revert_plan_core(
    archive_root: Path | str,
    *,
    receipt: Path | str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = archive_services.require_existing_archive_root(archive_root)
    archive_id = archive_services.read_archive_id(root)
    receipt_path, path_error = _resolve_locator_receipt_input(root, receipt)
    blockers: list[str] = []
    receipt_doc: dict[str, Any] | None = None
    receipt_bytes: bytes | None = None
    if path_error or receipt_path is None:
        blockers.append("external_locator_receipt_path_invalid")
    else:
        try:
            receipt_bytes = receipt_path.read_bytes()
            loaded = json.loads(receipt_bytes.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            loaded = None
        if not _external_locator_receipt_is_valid(
            loaded,
            archive_id=archive_id,
        ):
            blockers.append("external_locator_receipt_invalid")
        else:
            receipt_doc = loaded

    record_path: Path | None = None
    before_bytes: bytes | None = None
    current_bytes: bytes | None = None
    current_sha256: str | None = None
    before_sha256: str | None = None
    after_sha256: str | None = None
    zettel_id: str | None = None
    if receipt_doc is not None:
        zettel_id = _safe_zettel_id(receipt_doc.get("zettel_id"))
        before_sha256 = receipt_doc.get("before_record_sha256")
        after_sha256 = receipt_doc.get("after_record_sha256")
        try:
            record_path = _locator_internal_path(
                root,
                _record_relative(zettel_id or "invalid-zettel"),
            )
        except archive_services.ArchiveServiceError:
            blockers.append("external_locator_record_unsafe")
        if record_path is not None and zettel_id is not None:
            _current_record, current_bytes, record_error = _read_locator_record(
                root,
                zettel_id,
            )
            if record_error is not None:
                blockers.append(record_error)
            if current_bytes is not None:
                current_sha256 = _sha256_bytes(current_bytes)
            if current_sha256 != after_sha256:
                blockers.append("external_locator_record_changed")
        if before_sha256 is not None and zettel_id is not None:
            snapshot_relative = (
                f"{EXTERNAL_LOCATOR_SNAPSHOT_DIR}/{before_sha256}.json"
            )
            try:
                snapshot_path = _locator_internal_path(
                    root,
                    snapshot_relative,
                )
            except archive_services.ArchiveServiceError:
                snapshot_path = None
                blockers.append("external_locator_snapshot_unsafe")
            if snapshot_path is None:
                pass
            elif not snapshot_path.is_file() or snapshot_path.is_symlink():
                blockers.append("external_locator_snapshot_missing")
            else:
                try:
                    before_bytes = snapshot_path.read_bytes()
                except OSError:
                    blockers.append("external_locator_snapshot_missing")
                if before_bytes is not None:
                    if _sha256_bytes(before_bytes) != before_sha256:
                        blockers.append("external_locator_snapshot_mismatch")
                    elif not _locator_record_bytes_are_valid(
                        before_bytes,
                        archive_id=archive_id,
                        zettel_id=zettel_id,
                    ):
                        blockers.append("external_locator_snapshot_invalid")

    binding = {
        "schema": "wom-kit/external-locator-revert-plan-binding/v0.1",
        "archive_id": archive_id,
        "source_receipt_sha256": (
            _sha256_bytes(receipt_bytes)
            if receipt_bytes is not None
            else None
        ),
        "zettel_id": zettel_id,
        "current_record_sha256": current_sha256,
        "restore_record_sha256": before_sha256,
    }
    plan_sha256 = _sha256_bytes(_canonical_json_bytes(binding))
    aggregate = archive_services.unique_preserve_order(blockers)
    result = {
        "ok": not aggregate,
        "state": "ready" if not aggregate else "blocked",
        "dry_run": True,
        "lifecycle_action": "external_locator_revert_plan",
        "archive_id": archive_id,
        "summary": {
            "zettel_id": zettel_id,
            "current_record_sha256": current_sha256,
            "restore_record_sha256": before_sha256,
            "restore_action": (
                "exact_byte_restore"
                if before_sha256 is not None
                else "remove_new_record"
            ),
            "plan_sha256": plan_sha256 if not aggregate else None,
        },
        "blockers": aggregate,
        "warnings": [],
        "would_change": (
            [_record_relative(zettel_id)]
            if not aggregate and zettel_id is not None
            else []
        ),
        "privacy_guards": {
            "locator_ref_echoed": False,
            "provider_url_echoed": False,
            "snapshot_bytes_echoed": False,
            "local_absolute_path_echoed": False,
            "writes": False,
        },
    }
    private = {
        "root": root,
        "receipt_doc": receipt_doc,
        "receipt_bytes": receipt_bytes,
        "record_path": record_path,
        "current_bytes": current_bytes,
        "before_bytes": before_bytes,
        "before_sha256": before_sha256,
        "after_sha256": after_sha256,
        "zettel_id": zettel_id,
        "plan_sha256": plan_sha256,
    }
    return result, private


def external_locator_revert_plan(
    archive_root: Path | str,
    *,
    receipt: Path | str,
) -> dict[str, Any]:
    result, _private = _external_locator_revert_plan_core(
        archive_root,
        receipt=receipt,
    )
    return result


def external_locator_revert(
    archive_root: Path | str,
    *,
    receipt: Path | str,
    expected_plan_sha256: str | None,
    reviewed_by: str | None,
) -> dict[str, Any]:
    result, private = _external_locator_revert_plan_core(
        archive_root,
        receipt=receipt,
    )
    blockers = list(result["blockers"])
    expected = str(expected_plan_sha256 or "").strip().lower()
    reviewer = archive_services.safe_project_intake_actor_id(reviewed_by)
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        blockers.append("external_locator_revert_plan_sha256_invalid")
    elif expected != private["plan_sha256"]:
        blockers.append("external_locator_revert_plan_changed")
    if reviewer is None:
        blockers.append("external_locator_revert_reviewer_invalid")
    if blockers or private["zettel_id"] is None:
        return {
            **result,
            "ok": False,
            "state": "blocked",
            "dry_run": False,
            "approved": False,
            "lifecycle_action": "external_locator_revert",
            "blockers": archive_services.unique_preserve_order(blockers),
            "would_change": [],
            "files_written": [],
        }
    root: Path = private["root"]
    with _LocatorLock(root, private["zettel_id"]):
        fresh, fresh_private = _external_locator_revert_plan_core(
            root,
            receipt=receipt,
        )
        if not fresh["ok"] or fresh_private["plan_sha256"] != expected:
            return {
                **fresh,
                "ok": False,
                "state": "blocked",
                "dry_run": False,
                "approved": False,
                "lifecycle_action": "external_locator_revert",
                "blockers": archive_services.unique_preserve_order(
                    [
                        *fresh["blockers"],
                        "external_locator_revert_plan_changed",
                    ]
                ),
                "would_change": [],
                "files_written": [],
            }
        restore_action = (
            "removed_new_record"
            if fresh_private["before_bytes"] is None
            else "restored_previous_record"
        )
        timestamp = _now()
        source_receipt_sha256 = _sha256_bytes(
            fresh_private["receipt_bytes"] or b""
        )
        revert_receipt_relative = _receipt_relative(
            "revert",
            fresh_private["zettel_id"],
            timestamp,
            source_receipt_sha256,
        )
        try:
            revert_receipt_path = _locator_internal_path(
                root,
                revert_receipt_relative,
            )
        except archive_services.ArchiveServiceError:
            return {
                **fresh,
                "ok": False,
                "state": "blocked",
                "dry_run": False,
                "approved": False,
                "lifecycle_action": "external_locator_revert",
                "blockers": ["external_locator_revert_receipt_unsafe"],
                "would_change": [],
                "files_written": [],
            }
        if revert_receipt_path.exists() or revert_receipt_path.is_symlink():
            return {
                **fresh,
                "ok": False,
                "state": "blocked",
                "dry_run": False,
                "approved": False,
                "lifecycle_action": "external_locator_revert",
                "blockers": ["external_locator_revert_receipt_exists"],
                "would_change": [],
                "files_written": [],
            }
        revert_receipt = {
            "schema": EXTERNAL_LOCATOR_REVERT_RECEIPT_SCHEMA,
            "archive_id": archive_services.read_archive_id(root),
            "zettel_id": fresh_private["zettel_id"],
            "source_receipt_sha256": source_receipt_sha256,
            "revert_plan_sha256": expected,
            "restore_action": restore_action,
            "restored_record_sha256": fresh_private["before_sha256"],
            "reviewed_by": reviewer,
            "created_at": timestamp,
        }
        try:
            if fresh_private["before_bytes"] is None:
                fresh_private["record_path"].unlink()
                archive_services.fsync_directory(
                    fresh_private["record_path"].parent
                )
            else:
                archive_services.write_bytes_atomic(
                    fresh_private["record_path"],
                    fresh_private["before_bytes"],
                )
            archive_services._write_bytes_create_if_absent(
                revert_receipt_path,
                _canonical_json_bytes(revert_receipt),
            )
        except OSError:
            if (
                revert_receipt_path.exists()
                and revert_receipt_path.is_file()
                and not revert_receipt_path.is_symlink()
            ):
                try:
                    revert_receipt_path.unlink()
                    archive_services.fsync_directory(
                        revert_receipt_path.parent
                    )
                except OSError:
                    pass
            rollback_blockers = ["external_locator_revert_write_failed"]
            try:
                if fresh_private["current_bytes"] is None:
                    raise OSError("missing current locator bytes for rollback")
                archive_services.write_bytes_atomic(
                    fresh_private["record_path"],
                    fresh_private["current_bytes"],
                )
            except OSError:
                rollback_blockers.append(
                    "external_locator_revert_rollback_failed"
                )
            return {
                **fresh,
                "ok": False,
                "state": "blocked",
                "dry_run": False,
                "approved": False,
                "lifecycle_action": "external_locator_revert",
                "blockers": rollback_blockers,
                "would_change": [],
                "files_written": [],
            }
    return {
        **fresh,
        "ok": True,
        "state": "reverted",
        "dry_run": False,
        "approved": True,
        "lifecycle_action": "external_locator_revert",
        "summary": {
            **fresh["summary"],
            "restore_action": restore_action,
            "receipt_path": revert_receipt_relative,
        },
        "blockers": [],
        "would_change": [],
        "files_written": [
            _record_relative(fresh_private["zettel_id"]),
            revert_receipt_relative,
        ],
        "privacy_guards": {
            **fresh["privacy_guards"],
            "writes": True,
        },
    }


class _ZettelObjetLinkLock(_LocatorLock):
    def __init__(self, root: Path, zettel_id: str) -> None:
        lock_dir = archive_services.archive_internal_path(
            root,
            f"{ZETTEL_OBJET_LINK_RECEIPTS_DIR}/.locks",
        )
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_name = hashlib.sha256(zettel_id.encode("utf-8")).hexdigest()
        self._path = lock_dir / f"{lock_name}.lock"
        self._handle = None


def _safe_zettel_objet_label(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    text = value.strip()
    if (
        not text
        or len(text) > 500
        or any(ord(character) < 32 for character in text)
        or archive_services.source_intake_secret_like(text)
        or archive_services.contains_forbidden_location_reference(text)
        or archive_services.source_intake_has_provider_url(text)
    ):
        return None
    return text


def _zettel_objet_link_plan_core(
    archive_root: Path | str,
    *,
    zettel_id: str | None,
    relative_path: str | None,
    object_id: str | None,
    role: str,
    label: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = archive_services.require_existing_archive_root(archive_root)
    archive_id = archive_services.read_archive_id(root)
    blockers: list[str] = []
    if bool(zettel_id) == bool(relative_path):
        blockers.append("zettel_objet_link_target_required")

    normalized_object_id = str(object_id or "").strip().lower()
    if archive_services.OBJECT_ID_RE.fullmatch(normalized_object_id) is None:
        blockers.append("zettel_objet_link_object_id_invalid")
    normalized_role = str(role or "").strip().lower().replace("-", "_")
    if ZETTEL_OBJET_ROLE_RE.fullmatch(normalized_role) is None:
        blockers.append("zettel_objet_link_role_invalid")
    safe_label = _safe_zettel_objet_label(label)
    if label is not None and safe_label is None:
        blockers.append("zettel_objet_link_label_invalid_or_private")

    zettel_path: Path | None = None
    zettel_frontmatter: dict[str, Any] = {}
    zettel_body = ""
    before_bytes: bytes | None = None
    before_sha256: str | None = None
    safe_zettel_id: str | None = None
    zettel_relative: str | None = None
    if bool(zettel_id) != bool(relative_path):
        try:
            zettel_path = archive_services.resolve_zettel_path(
                root,
                zettel_id=zettel_id,
                relative_path=relative_path,
            )
            zettel_frontmatter, zettel_body = (
                archive_services.require_readable_zettel_content(zettel_path)
            )
            safe_zettel_id = _safe_zettel_id(zettel_frontmatter.get("id"))
            if (
                safe_zettel_id is None
                or zettel_frontmatter.get("status")
                not in archive_services.ZETTEL_QUERYABLE_STATUSES
            ):
                blockers.append("zettel_objet_link_zettel_unavailable")
            zettel_relative = archive_services.archive_relative_path(
                zettel_path,
                root,
            )
            before_bytes = zettel_path.read_bytes()
            before_sha256 = _sha256_bytes(before_bytes)
        except (archive_services.ArchiveServiceError, OSError):
            blockers.append("zettel_objet_link_zettel_unavailable")

    manifest_record: dict[str, Any] | None = None
    if archive_services.OBJECT_ID_RE.fullmatch(normalized_object_id):
        manifest_record = archive_services.find_manifest_record(
            root,
            normalized_object_id,
        )
        if manifest_record is None:
            blockers.append("zettel_objet_link_manifest_record_missing")

    assets = zettel_frontmatter.get("assets")
    if zettel_path is not None and not isinstance(assets, list):
        blockers.append("zettel_objet_link_assets_not_array")
        assets = []
    existing_assets = assets if isinstance(assets, list) else []
    if any(
        isinstance(item, dict)
        and item.get("object_id") == normalized_object_id
        for item in existing_assets
    ):
        blockers.append("zettel_objet_link_already_present")

    link_seed = {
        "archive_id": archive_id,
        "zettel_id": safe_zettel_id,
        "object_id": normalized_object_id,
        "role": normalized_role,
    }
    link_digest = _sha256_bytes(_canonical_json_bytes(link_seed))
    link_id = f"asset:sha256:{link_digest}"
    receipt_root = archive_services.archive_internal_path(
        root,
        ZETTEL_OBJET_LINK_RECEIPTS_DIR,
    )
    receipt_prefix = f"link.{link_digest[:24]}.g"
    generation = 1 + sum(
        1
        for path in receipt_root.glob(f"{receipt_prefix}*.json")
        if path.is_file()
    ) if receipt_root.is_dir() else 1
    receipt_relative = (
        f"{ZETTEL_OBJET_LINK_RECEIPTS_DIR}/"
        f"{receipt_prefix}{generation:04d}.json"
    )
    if archive_services.archive_internal_path(root, receipt_relative).exists():
        blockers.append("zettel_objet_link_receipt_collision")

    manifest_sha256 = (
        _sha256_bytes(_canonical_json_bytes(manifest_record))
        if manifest_record is not None
        else None
    )
    label_sha256 = (
        _sha256_bytes(safe_label.encode("utf-8"))
        if safe_label is not None
        else None
    )
    plan_binding = {
        "schema": "wom-kit/zettel-objet-link-plan-binding/v0.1",
        "archive_id": archive_id,
        "zettel_id": safe_zettel_id,
        "zettel_sha256": before_sha256,
        "object_id": normalized_object_id,
        "manifest_record_sha256": manifest_sha256,
        "role": normalized_role,
        "label_sha256": label_sha256,
        "link_id": link_id,
        "receipt_path": receipt_relative,
        "generation": generation,
    }
    plan_sha256 = _sha256_bytes(_canonical_json_bytes(plan_binding))
    result = {
        "ok": not blockers,
        "state": "ready" if not blockers else "blocked",
        "dry_run": True,
        "lifecycle_action": "zettel_objet_link_plan",
        "archive_id": archive_id,
        "summary": {
            "zettel_id": safe_zettel_id,
            "zettel_path": zettel_relative,
            "object_id": normalized_object_id,
            "role": normalized_role,
            "label_present": safe_label is not None,
            "link_id": link_id,
            "current_asset_count": len(existing_assets),
            "manifest_record_verified": manifest_record is not None,
            "zettel_sha256": before_sha256,
            "receipt_path": receipt_relative,
            "plan_sha256": plan_sha256 if not blockers else None,
        },
        "data": {
            "record_shape": {
                "required_fields": ["object_id", "role"],
                "optional_fields": ["label"],
                "unknown_fields_allowed": False,
            },
            "receipt_schema": ZETTEL_OBJET_LINK_RECEIPT_SCHEMA,
            "exact_byte_revert_supported": True,
        },
        "blockers": archive_services.unique_preserve_order(blockers),
        "warnings": [],
        "would_change": (
            [
                f"{zettel_relative} frontmatter.assets +1",
                receipt_relative,
            ]
            if not blockers and zettel_relative
            else []
        ),
        "privacy_guards": {
            "label_echoed": False,
            "zettel_body_echoed": False,
            "object_bytes_read": False,
            "provider_called": False,
            "network_checked": False,
            "local_absolute_path_echoed": False,
            "writes": False,
        },
    }
    return result, {
        "root": root,
        "zettel_path": zettel_path,
        "zettel_frontmatter": zettel_frontmatter,
        "zettel_body": zettel_body,
        "zettel_relative": zettel_relative,
        "safe_zettel_id": safe_zettel_id,
        "before_bytes": before_bytes,
        "before_sha256": before_sha256,
        "object_id": normalized_object_id,
        "role": normalized_role,
        "safe_label": safe_label,
        "link_id": link_id,
        "receipt_relative": receipt_relative,
        "plan_sha256": plan_sha256,
        "existing_assets": existing_assets,
    }


def zettel_objet_link_plan(
    archive_root: Path | str,
    *,
    zettel_id: str | None = None,
    relative_path: str | None = None,
    object_id: str | None,
    role: str,
    label: str | None = None,
) -> dict[str, Any]:
    result, _private = _zettel_objet_link_plan_core(
        archive_root,
        zettel_id=zettel_id,
        relative_path=relative_path,
        object_id=object_id,
        role=role,
        label=label,
    )
    return result


def zettel_objet_link_apply(
    archive_root: Path | str,
    *,
    zettel_id: str | None = None,
    relative_path: str | None = None,
    object_id: str | None,
    role: str,
    label: str | None = None,
    expected_plan_sha256: str | None,
    reviewed_by: str | None,
) -> dict[str, Any]:
    result, private = _zettel_objet_link_plan_core(
        archive_root,
        zettel_id=zettel_id,
        relative_path=relative_path,
        object_id=object_id,
        role=role,
        label=label,
    )
    blockers = list(result["blockers"])
    expected = str(expected_plan_sha256 or "").strip().lower()
    reviewer = archive_services.safe_project_intake_actor_id(reviewed_by)
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        blockers.append("zettel_objet_link_expected_plan_sha256_invalid")
    elif expected != private["plan_sha256"]:
        blockers.append("zettel_objet_link_plan_changed")
    if reviewer is None:
        blockers.append("zettel_objet_link_reviewer_invalid")
    if blockers or private["safe_zettel_id"] is None:
        return {
            **result,
            "ok": False,
            "state": "blocked",
            "dry_run": False,
            "approved": False,
            "lifecycle_action": "zettel_objet_link_apply",
            "blockers": archive_services.unique_preserve_order(blockers),
            "would_change": [],
            "files_written": [],
        }

    root: Path = private["root"]
    with _ZettelObjetLinkLock(root, private["safe_zettel_id"]):
        fresh, fresh_private = _zettel_objet_link_plan_core(
            root,
            zettel_id=zettel_id,
            relative_path=relative_path,
            object_id=object_id,
            role=role,
            label=label,
        )
        if not fresh["ok"] or fresh_private["plan_sha256"] != expected:
            return {
                **fresh,
                "ok": False,
                "state": "blocked",
                "dry_run": False,
                "approved": False,
                "lifecycle_action": "zettel_objet_link_apply",
                "blockers": archive_services.unique_preserve_order(
                    [*fresh["blockers"], "zettel_objet_link_plan_changed"]
                ),
                "would_change": [],
                "files_written": [],
            }

        timestamp = _now()
        asset = {
            "object_id": fresh_private["object_id"],
            "role": fresh_private["role"],
        }
        if fresh_private["safe_label"] is not None:
            asset["label"] = fresh_private["safe_label"]
        updated_frontmatter = dict(fresh_private["zettel_frontmatter"])
        updated_frontmatter["assets"] = [
            *fresh_private["existing_assets"],
            asset,
        ]
        updated_frontmatter["updated_at"] = timestamp
        updated_text = (
            "---\n"
            + archive_services.dump_yaml(updated_frontmatter)
            + "---\n"
            + fresh_private["zettel_body"]
        )
        updated_bytes = updated_text.encode("utf-8")
        after_sha256 = _sha256_bytes(updated_bytes)
        snapshot_relative = (
            f"{ZETTEL_OBJET_LINK_SNAPSHOT_DIR}/"
            f"{fresh_private['before_sha256']}.zettel.md"
        )
        snapshot_path = archive_services.archive_internal_path(
            root,
            snapshot_relative,
        )
        receipt_path = archive_services.archive_internal_path(
            root,
            fresh_private["receipt_relative"],
        )
        receipt = {
            "schema": ZETTEL_OBJET_LINK_RECEIPT_SCHEMA,
            "action": "add_zettel_objet_link",
            "archive_id": archive_services.read_archive_id(root),
            "zettel_id": fresh_private["safe_zettel_id"],
            "zettel_path": fresh_private["zettel_relative"],
            "object_id": fresh_private["object_id"],
            "role": fresh_private["role"],
            "label_sha256": (
                _sha256_bytes(fresh_private["safe_label"].encode("utf-8"))
                if fresh_private["safe_label"] is not None
                else None
            ),
            "link_id": fresh_private["link_id"],
            "plan_sha256": expected,
            "before_zettel_sha256": fresh_private["before_sha256"],
            "after_zettel_sha256": after_sha256,
            "before_snapshot_path": snapshot_relative,
            "reviewed_by": reviewer,
            "created_at": timestamp,
            "privacy": {
                "label_included": False,
                "zettel_body_included": False,
                "object_bytes_read": False,
                "provider_called": False,
            },
        }
        snapshot_created = False
        receipt_created = False
        zettel_written = False
        try:
            if not snapshot_path.exists():
                archive_services._write_bytes_create_if_absent(
                    snapshot_path,
                    fresh_private["before_bytes"],
                )
                snapshot_created = True
            archive_services.write_bytes_atomic(
                fresh_private["zettel_path"],
                updated_bytes,
            )
            zettel_written = True
            archive_services._write_bytes_create_if_absent(
                receipt_path,
                _canonical_json_bytes(receipt),
            )
            receipt_created = True
        except OSError:
            if zettel_written:
                archive_services.write_bytes_atomic(
                    fresh_private["zettel_path"],
                    fresh_private["before_bytes"],
                )
            if receipt_created:
                receipt_path.unlink(missing_ok=True)
            if snapshot_created:
                snapshot_path.unlink(missing_ok=True)
            raise

    return {
        **fresh,
        "ok": True,
        "state": "written",
        "dry_run": False,
        "approved": True,
        "lifecycle_action": "zettel_objet_link_apply",
        "summary": {
            **fresh["summary"],
            "current_asset_count": len(fresh_private["existing_assets"]) + 1,
            "zettel_sha256": after_sha256,
            "snapshot_path": snapshot_relative,
        },
        "blockers": [],
        "would_change": [],
        "files_written": [
            fresh_private["zettel_relative"],
            snapshot_relative,
            fresh_private["receipt_relative"],
        ],
        "privacy_guards": {**fresh["privacy_guards"], "writes": True},
    }


def _zettel_objet_link_revert_plan_core(
    archive_root: Path | str,
    *,
    receipt: Path | str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = archive_services.require_existing_archive_root(archive_root)
    archive_id = archive_services.read_archive_id(root)
    blockers: list[str] = []
    receipt_path, path_error = _resolve_json_input(root, receipt)
    receipt_doc: dict[str, Any] | None = None
    receipt_bytes: bytes | None = None
    if path_error or receipt_path is None:
        blockers.append("zettel_objet_link_receipt_path_invalid")
    else:
        try:
            receipt_bytes = receipt_path.read_bytes()
            loaded = json.loads(receipt_bytes.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            loaded = None
        if (
            not isinstance(loaded, dict)
            or loaded.get("schema") != ZETTEL_OBJET_LINK_RECEIPT_SCHEMA
            or loaded.get("archive_id") != archive_id
            or archive_services.validate_schema(
                loaded,
                "zettel-objet-link-receipt.schema.json",
            )
        ):
            blockers.append("zettel_objet_link_receipt_invalid")
        else:
            try:
                receipt_relative = archive_services.archive_relative_path(
                    receipt_path,
                    root,
                )
            except Exception:
                receipt_relative = ""
            if (
                not receipt_relative.startswith(
                    f"{ZETTEL_OBJET_LINK_RECEIPTS_DIR}/link."
                )
                or not receipt_relative.endswith(".json")
            ):
                blockers.append("zettel_objet_link_receipt_path_invalid")
            else:
                receipt_doc = loaded

    zettel_path: Path | None = None
    current_bytes: bytes | None = None
    snapshot_bytes: bytes | None = None
    safe_zettel_id: str | None = None
    revert_receipt_relative: str | None = None
    if receipt_doc is not None:
        safe_zettel_id = _safe_zettel_id(receipt_doc.get("zettel_id"))
        try:
            zettel_path = archive_services.archive_internal_path(
                root,
                str(receipt_doc.get("zettel_path") or ""),
            )
            current_bytes = zettel_path.read_bytes()
        except (archive_services.ArchiveServiceError, OSError):
            blockers.append("zettel_objet_link_current_zettel_unavailable")
        if (
            current_bytes is not None
            and _sha256_bytes(current_bytes)
            != receipt_doc.get("after_zettel_sha256")
        ):
            blockers.append("zettel_objet_link_current_zettel_changed")
        try:
            snapshot_path = archive_services.archive_internal_path(
                root,
                str(receipt_doc.get("before_snapshot_path") or ""),
            )
            snapshot_bytes = snapshot_path.read_bytes()
        except (archive_services.ArchiveServiceError, OSError):
            blockers.append("zettel_objet_link_snapshot_missing")
        if (
            snapshot_bytes is not None
            and _sha256_bytes(snapshot_bytes)
            != receipt_doc.get("before_zettel_sha256")
        ):
            blockers.append("zettel_objet_link_snapshot_mismatch")
        if safe_zettel_id is None:
            blockers.append("zettel_objet_link_receipt_invalid")
        source_receipt_sha256 = _sha256_bytes(receipt_bytes or b"")
        revert_receipt_relative = (
            f"{ZETTEL_OBJET_LINK_RECEIPTS_DIR}/reverts/"
            f"{source_receipt_sha256[:24]}.json"
        )
        if archive_services.archive_internal_path(
            root,
            revert_receipt_relative,
        ).exists():
            blockers.append("zettel_objet_link_revert_already_recorded")
    else:
        source_receipt_sha256 = None

    binding = {
        "schema": "wom-kit/zettel-objet-link-revert-plan-binding/v0.1",
        "archive_id": archive_id,
        "source_receipt_sha256": source_receipt_sha256,
        "zettel_id": safe_zettel_id,
        "current_zettel_sha256": (
            _sha256_bytes(current_bytes) if current_bytes is not None else None
        ),
        "restore_zettel_sha256": (
            _sha256_bytes(snapshot_bytes)
            if snapshot_bytes is not None
            else None
        ),
        "revert_receipt_path": revert_receipt_relative,
    }
    plan_sha256 = _sha256_bytes(_canonical_json_bytes(binding))
    aggregate = archive_services.unique_preserve_order(blockers)
    result = {
        "ok": not aggregate,
        "state": "ready" if not aggregate else "blocked",
        "dry_run": True,
        "lifecycle_action": "zettel_objet_link_revert_plan",
        "archive_id": archive_id,
        "summary": {
            "zettel_id": safe_zettel_id,
            "object_id": receipt_doc.get("object_id") if receipt_doc else None,
            "link_id": receipt_doc.get("link_id") if receipt_doc else None,
            "revert_receipt_path": revert_receipt_relative,
            "plan_sha256": plan_sha256 if not aggregate else None,
            "exact_byte_restore": True,
        },
        "blockers": aggregate,
        "warnings": [],
        "would_change": (
            [str(receipt_doc.get("zettel_path")), revert_receipt_relative]
            if not aggregate and receipt_doc and revert_receipt_relative
            else []
        ),
        "privacy_guards": {
            "label_echoed": False,
            "zettel_body_echoed": False,
            "snapshot_bytes_echoed": False,
            "object_bytes_read": False,
            "writes": False,
        },
    }
    return result, {
        "root": root,
        "receipt_doc": receipt_doc,
        "receipt_bytes": receipt_bytes,
        "zettel_path": zettel_path,
        "current_bytes": current_bytes,
        "snapshot_bytes": snapshot_bytes,
        "safe_zettel_id": safe_zettel_id,
        "revert_receipt_relative": revert_receipt_relative,
        "source_receipt_sha256": source_receipt_sha256,
        "plan_sha256": plan_sha256,
    }


def zettel_objet_link_revert_plan(
    archive_root: Path | str,
    *,
    receipt: Path | str,
) -> dict[str, Any]:
    result, _private = _zettel_objet_link_revert_plan_core(
        archive_root,
        receipt=receipt,
    )
    return result


def zettel_objet_link_revert(
    archive_root: Path | str,
    *,
    receipt: Path | str,
    expected_plan_sha256: str | None,
    reviewed_by: str | None,
) -> dict[str, Any]:
    result, private = _zettel_objet_link_revert_plan_core(
        archive_root,
        receipt=receipt,
    )
    blockers = list(result["blockers"])
    expected = str(expected_plan_sha256 or "").strip().lower()
    reviewer = archive_services.safe_project_intake_actor_id(reviewed_by)
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        blockers.append("zettel_objet_link_revert_plan_sha256_invalid")
    elif expected != private["plan_sha256"]:
        blockers.append("zettel_objet_link_revert_plan_changed")
    if reviewer is None:
        blockers.append("zettel_objet_link_revert_reviewer_invalid")
    if blockers or private["safe_zettel_id"] is None:
        return {
            **result,
            "ok": False,
            "state": "blocked",
            "dry_run": False,
            "approved": False,
            "lifecycle_action": "zettel_objet_link_revert",
            "blockers": archive_services.unique_preserve_order(blockers),
            "would_change": [],
            "files_written": [],
        }
    root: Path = private["root"]
    with _ZettelObjetLinkLock(root, private["safe_zettel_id"]):
        fresh, fresh_private = _zettel_objet_link_revert_plan_core(
            root,
            receipt=receipt,
        )
        if not fresh["ok"] or fresh_private["plan_sha256"] != expected:
            return {
                **fresh,
                "ok": False,
                "state": "blocked",
                "dry_run": False,
                "approved": False,
                "lifecycle_action": "zettel_objet_link_revert",
                "blockers": archive_services.unique_preserve_order(
                    [*fresh["blockers"], "zettel_objet_link_revert_plan_changed"]
                ),
                "would_change": [],
                "files_written": [],
            }
        timestamp = _now()
        revert_receipt = {
            "schema": ZETTEL_OBJET_LINK_REVERT_RECEIPT_SCHEMA,
            "action": "restore_zettel_before_objet_link",
            "archive_id": archive_services.read_archive_id(root),
            "zettel_id": fresh_private["safe_zettel_id"],
            "source_receipt_sha256": fresh_private["source_receipt_sha256"],
            "revert_plan_sha256": expected,
            "restored_zettel_sha256": fresh_private["receipt_doc"]["before_zettel_sha256"],
            "reviewed_by": reviewer,
            "created_at": timestamp,
        }
        revert_receipt_path = archive_services.archive_internal_path(
            root,
            fresh_private["revert_receipt_relative"],
        )
        zettel_restored = False
        try:
            archive_services.write_bytes_atomic(
                fresh_private["zettel_path"],
                fresh_private["snapshot_bytes"],
            )
            zettel_restored = True
            archive_services._write_bytes_create_if_absent(
                revert_receipt_path,
                _canonical_json_bytes(revert_receipt),
            )
        except OSError:
            if zettel_restored:
                archive_services.write_bytes_atomic(
                    fresh_private["zettel_path"],
                    fresh_private["current_bytes"],
                )
            revert_receipt_path.unlink(missing_ok=True)
            raise
    return {
        **fresh,
        "ok": True,
        "state": "reverted",
        "dry_run": False,
        "approved": True,
        "lifecycle_action": "zettel_objet_link_revert",
        "blockers": [],
        "would_change": [],
        "files_written": [
            fresh_private["receipt_doc"]["zettel_path"],
            fresh_private["revert_receipt_relative"],
        ],
        "privacy_guards": {**fresh["privacy_guards"], "writes": True},
    }


class _DraftDiscardLock(_LocatorLock):
    def __init__(self, root: Path, zettel_id: str) -> None:
        lock_dir = archive_services.archive_internal_path(
            root,
            f"{DRAFT_DISCARD_RECEIPTS_DIR}/.locks",
        )
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_name = hashlib.sha256(zettel_id.encode("utf-8")).hexdigest()
        self._path = lock_dir / f"{lock_name}.lock"
        self._handle = None


def _safe_discard_reason(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if (
        not text
        or len(text) > 1000
        or any(ord(character) < 32 for character in text)
        or not archive_services.safe_source_intake_text(text)
    ):
        return None
    return text


def _draft_discard_plan_core(
    archive_root: Path | str,
    *,
    zettel_id: str | None,
    relative_path: str | None,
    reason: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = archive_services.require_existing_archive_root(archive_root)
    archive_id = archive_services.read_archive_id(root)
    blockers: list[str] = []
    if bool(zettel_id) == bool(relative_path):
        blockers.append("discard_draft_target_required")
    safe_reason = _safe_discard_reason(reason)
    if safe_reason is None:
        blockers.append("discard_draft_reason_invalid_or_private")

    draft_path: Path | None = None
    draft_relative: str | None = None
    draft_bytes: bytes | None = None
    draft_sha256: str | None = None
    safe_zettel_id: str | None = None
    frontmatter: dict[str, Any] = {}
    if bool(zettel_id) != bool(relative_path):
        try:
            draft_path = archive_services.resolve_inbox_draft_path(
                root,
                zettel_id,
                relative_path,
            )
            frontmatter, _body = archive_services.require_readable_zettel_content(
                draft_path
            )
            safe_zettel_id = _safe_zettel_id(frontmatter.get("id"))
            if safe_zettel_id is None or frontmatter.get("status") != "draft":
                blockers.append("discard_draft_source_invalid")
            draft_relative = archive_services.archive_relative_path(
                draft_path,
                root,
            )
            draft_bytes = draft_path.read_bytes()
            draft_sha256 = _sha256_bytes(draft_bytes)
        except (archive_services.ArchiveServiceError, OSError):
            blockers.append("discard_draft_source_unavailable")

    mint_receipt_relative = (
        f"{archive_services.MINT_RECEIPTS_DIR}/{safe_zettel_id}.mint.json"
        if safe_zettel_id
        else None
    )
    if (
        mint_receipt_relative
        and archive_services.archive_internal_path(root, mint_receipt_relative).exists()
    ):
        blockers.append("discard_draft_mint_receipt_present_use_retire_draft")
    canonical_twin_present = False
    if safe_zettel_id and (root / "zettels").is_dir():
        for candidate in archive_services.safe_archive_glob(
            root / "zettels",
            "*.md",
            root,
            recursive=True,
        ):
            inspection = archive_services.inspect_zettel_frontmatter_boundary(
                candidate
            )
            if (
                inspection.get("metadata_readable")
                and inspection.get("frontmatter", {}).get("id") == safe_zettel_id
            ):
                canonical_twin_present = True
                break
    if canonical_twin_present:
        blockers.append("discard_draft_canonical_twin_present_use_retire_draft")

    snapshot_relative = (
        f"{DRAFT_DISCARD_SNAPSHOT_DIR}/{draft_sha256}.draft.md"
        if draft_sha256
        else None
    )
    receipt_relative = (
        f"{DRAFT_DISCARD_RECEIPTS_DIR}/{safe_zettel_id}."
        f"{str(draft_sha256 or '')[:16]}.discard.json"
        if safe_zettel_id and draft_sha256
        else None
    )
    if (
        receipt_relative
        and archive_services.archive_internal_path(root, receipt_relative).exists()
    ):
        blockers.append("discard_draft_receipt_already_exists")
    reason_sha256 = (
        _sha256_bytes(safe_reason.encode("utf-8"))
        if safe_reason is not None
        else None
    )
    plan_binding = {
        "schema": "wom-kit/draft-discard-plan-binding/v0.1",
        "archive_id": archive_id,
        "zettel_id": safe_zettel_id,
        "draft_path": draft_relative,
        "draft_sha256": draft_sha256,
        "reason_sha256": reason_sha256,
        "snapshot_path": snapshot_relative,
        "receipt_path": receipt_relative,
    }
    plan_sha256 = _sha256_bytes(_canonical_json_bytes(plan_binding))
    aggregate = archive_services.unique_preserve_order(blockers)
    next_safe_actions = (
        [
            f"archive retire-draft <archive-root> --zettel-id {safe_zettel_id} --dry-run --format json"
        ]
        if safe_zettel_id
        and any("use_retire_draft" in item for item in aggregate)
        else []
    )
    result = {
        "ok": not aggregate,
        "state": "ready" if not aggregate else "blocked",
        "dry_run": True,
        "lifecycle_action": "discard_draft_plan",
        "archive_id": archive_id,
        "summary": {
            "zettel_id": safe_zettel_id,
            "draft_path": draft_relative,
            "draft_sha256": draft_sha256,
            "reason_sha256": reason_sha256,
            "snapshot_path": snapshot_relative,
            "receipt_path": receipt_relative,
            "plan_sha256": plan_sha256 if not aggregate else None,
            "mint_receipt_present": (
                "discard_draft_mint_receipt_present_use_retire_draft" in aggregate
            ),
            "canonical_twin_present": canonical_twin_present,
            "exact_byte_restore_supported": True,
        },
        "blockers": aggregate,
        "warnings": [],
        "next_safe_actions": next_safe_actions,
        "would_change": (
            [
                f"remove {draft_relative}",
                f"write {snapshot_relative}",
                f"write {receipt_relative}",
            ]
            if not aggregate
            else []
        ),
        "privacy_guards": {
            "reason_echoed": False,
            "draft_body_echoed": False,
            "snapshot_bytes_echoed": False,
            "local_absolute_path_echoed": False,
            "writes": False,
        },
    }
    return result, {
        "root": root,
        "draft_path": draft_path,
        "draft_relative": draft_relative,
        "draft_bytes": draft_bytes,
        "draft_sha256": draft_sha256,
        "safe_zettel_id": safe_zettel_id,
        "safe_reason": safe_reason,
        "reason_sha256": reason_sha256,
        "snapshot_relative": snapshot_relative,
        "receipt_relative": receipt_relative,
        "plan_sha256": plan_sha256,
    }


def draft_discard_plan(
    archive_root: Path | str,
    *,
    zettel_id: str | None = None,
    relative_path: str | None = None,
    reason: str | None,
) -> dict[str, Any]:
    result, _private = _draft_discard_plan_core(
        archive_root,
        zettel_id=zettel_id,
        relative_path=relative_path,
        reason=reason,
    )
    return result


def draft_discard_apply(
    archive_root: Path | str,
    *,
    zettel_id: str | None = None,
    relative_path: str | None = None,
    reason: str | None,
    expected_plan_sha256: str | None,
    reviewed_by: str | None,
) -> dict[str, Any]:
    result, private = _draft_discard_plan_core(
        archive_root,
        zettel_id=zettel_id,
        relative_path=relative_path,
        reason=reason,
    )
    blockers = list(result["blockers"])
    expected = str(expected_plan_sha256 or "").strip().lower()
    reviewer = archive_services.safe_project_intake_actor_id(reviewed_by)
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        blockers.append("discard_draft_expected_plan_sha256_invalid")
    elif expected != private["plan_sha256"]:
        blockers.append("discard_draft_plan_changed")
    if reviewer is None:
        blockers.append("discard_draft_reviewer_invalid")
    if blockers or private["safe_zettel_id"] is None:
        return {
            **result,
            "ok": False,
            "state": "blocked",
            "dry_run": False,
            "approved": False,
            "lifecycle_action": "discard_draft_apply",
            "blockers": archive_services.unique_preserve_order(blockers),
            "would_change": [],
            "files_written": [],
        }
    root: Path = private["root"]
    with _DraftDiscardLock(root, private["safe_zettel_id"]):
        fresh, fresh_private = _draft_discard_plan_core(
            root,
            zettel_id=zettel_id,
            relative_path=relative_path,
            reason=reason,
        )
        if not fresh["ok"] or fresh_private["plan_sha256"] != expected:
            return {
                **fresh,
                "ok": False,
                "state": "blocked",
                "dry_run": False,
                "approved": False,
                "lifecycle_action": "discard_draft_apply",
                "blockers": archive_services.unique_preserve_order(
                    [*fresh["blockers"], "discard_draft_plan_changed"]
                ),
                "would_change": [],
                "files_written": [],
            }
        timestamp = _now()
        receipt = {
            "schema": DRAFT_DISCARD_RECEIPT_SCHEMA,
            "action": "discard_unminted_draft",
            "archive_id": archive_services.read_archive_id(root),
            "zettel_id": fresh_private["safe_zettel_id"],
            "draft_path": fresh_private["draft_relative"],
            "draft_sha256": fresh_private["draft_sha256"],
            "reason": fresh_private["safe_reason"],
            "reason_sha256": fresh_private["reason_sha256"],
            "snapshot_path": fresh_private["snapshot_relative"],
            "plan_sha256": expected,
            "reviewed_by": reviewer,
            "created_at": timestamp,
            "result": {
                "draft_removed": True,
                "snapshot_written": True,
                "exact_byte_restore_supported": True,
            },
        }
        snapshot_path = archive_services.archive_internal_path(
            root,
            fresh_private["snapshot_relative"],
        )
        receipt_path = archive_services.archive_internal_path(
            root,
            fresh_private["receipt_relative"],
        )
        snapshot_created = False
        draft_removed = False
        try:
            if not snapshot_path.exists():
                archive_services._write_bytes_create_if_absent(
                    snapshot_path,
                    fresh_private["draft_bytes"],
                )
                snapshot_created = True
            elif _sha256_bytes(snapshot_path.read_bytes()) != fresh_private["draft_sha256"]:
                raise OSError("discard snapshot collision")
            fresh_private["draft_path"].unlink()
            draft_removed = True
            archive_services._write_bytes_create_if_absent(
                receipt_path,
                _canonical_json_bytes(receipt),
            )
        except OSError:
            if draft_removed:
                archive_services._write_bytes_create_if_absent(
                    fresh_private["draft_path"],
                    fresh_private["draft_bytes"],
                )
            receipt_path.unlink(missing_ok=True)
            if snapshot_created:
                snapshot_path.unlink(missing_ok=True)
            raise
    return {
        **fresh,
        "ok": True,
        "state": "discarded",
        "dry_run": False,
        "approved": True,
        "lifecycle_action": "discard_draft_apply",
        "blockers": [],
        "would_change": [],
        "files_written": [
            fresh_private["snapshot_relative"],
            fresh_private["receipt_relative"],
        ],
        "removed_paths": [fresh_private["draft_relative"]],
        "privacy_guards": {**fresh["privacy_guards"], "writes": True},
    }


def _draft_discard_restore_plan_core(
    archive_root: Path | str,
    *,
    receipt: Path | str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = archive_services.require_existing_archive_root(archive_root)
    archive_id = archive_services.read_archive_id(root)
    blockers: list[str] = []
    receipt_path, path_error = _resolve_json_input(root, receipt)
    receipt_doc: dict[str, Any] | None = None
    receipt_bytes: bytes | None = None
    if path_error or receipt_path is None:
        blockers.append("discard_draft_receipt_path_invalid")
    else:
        try:
            receipt_bytes = receipt_path.read_bytes()
            loaded = json.loads(receipt_bytes.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            loaded = None
        if (
            not isinstance(loaded, dict)
            or loaded.get("schema") != DRAFT_DISCARD_RECEIPT_SCHEMA
            or loaded.get("archive_id") != archive_id
            or archive_services.validate_schema(
                loaded,
                "draft-discard-receipt.schema.json",
            )
        ):
            blockers.append("discard_draft_receipt_invalid")
        else:
            try:
                receipt_relative = archive_services.archive_relative_path(
                    receipt_path,
                    root,
                )
            except Exception:
                receipt_relative = ""
            if (
                not receipt_relative.startswith(
                    f"{DRAFT_DISCARD_RECEIPTS_DIR}/"
                )
                or "/snapshots/" in f"/{receipt_relative}"
                or not receipt_relative.endswith(".discard.json")
            ):
                blockers.append("discard_draft_receipt_path_invalid")
            else:
                receipt_doc = loaded
    draft_path: Path | None = None
    snapshot_bytes: bytes | None = None
    safe_zettel_id: str | None = None
    restore_receipt_relative: str | None = None
    if receipt_doc is not None:
        safe_zettel_id = _safe_zettel_id(receipt_doc.get("zettel_id"))
        try:
            draft_path = archive_services.archive_internal_path(
                root,
                str(receipt_doc.get("draft_path") or ""),
            )
        except archive_services.ArchiveServiceError:
            blockers.append("discard_draft_receipt_invalid")
        if draft_path is not None and draft_path.exists():
            blockers.append("discard_draft_restore_target_exists")
        try:
            snapshot_path = archive_services.archive_internal_path(
                root,
                str(receipt_doc.get("snapshot_path") or ""),
            )
            snapshot_bytes = snapshot_path.read_bytes()
        except (archive_services.ArchiveServiceError, OSError):
            blockers.append("discard_draft_snapshot_missing")
        if (
            snapshot_bytes is not None
            and _sha256_bytes(snapshot_bytes) != receipt_doc.get("draft_sha256")
        ):
            blockers.append("discard_draft_snapshot_mismatch")
        if safe_zettel_id is None:
            blockers.append("discard_draft_receipt_invalid")
        source_receipt_sha256 = _sha256_bytes(receipt_bytes or b"")
        restore_receipt_relative = (
            f"{DRAFT_DISCARD_RECEIPTS_DIR}/restores/"
            f"{source_receipt_sha256[:24]}.json"
        )
        if archive_services.archive_internal_path(
            root,
            restore_receipt_relative,
        ).exists():
            blockers.append("discard_draft_restore_already_recorded")
    else:
        source_receipt_sha256 = None
    binding = {
        "schema": "wom-kit/draft-discard-restore-plan-binding/v0.1",
        "archive_id": archive_id,
        "source_receipt_sha256": source_receipt_sha256,
        "zettel_id": safe_zettel_id,
        "restore_path": receipt_doc.get("draft_path") if receipt_doc else None,
        "restore_sha256": (
            _sha256_bytes(snapshot_bytes) if snapshot_bytes is not None else None
        ),
        "restore_receipt_path": restore_receipt_relative,
    }
    plan_sha256 = _sha256_bytes(_canonical_json_bytes(binding))
    aggregate = archive_services.unique_preserve_order(blockers)
    result = {
        "ok": not aggregate,
        "state": "ready" if not aggregate else "blocked",
        "dry_run": True,
        "lifecycle_action": "discard_draft_restore_plan",
        "archive_id": archive_id,
        "summary": {
            "zettel_id": safe_zettel_id,
            "restore_path": receipt_doc.get("draft_path") if receipt_doc else None,
            "restore_sha256": receipt_doc.get("draft_sha256") if receipt_doc else None,
            "restore_receipt_path": restore_receipt_relative,
            "plan_sha256": plan_sha256 if not aggregate else None,
            "exact_byte_restore": True,
        },
        "blockers": aggregate,
        "warnings": [],
        "would_change": (
            [str(receipt_doc.get("draft_path")), restore_receipt_relative]
            if not aggregate and receipt_doc and restore_receipt_relative
            else []
        ),
        "privacy_guards": {
            "reason_echoed": False,
            "draft_body_echoed": False,
            "snapshot_bytes_echoed": False,
            "writes": False,
        },
    }
    return result, {
        "root": root,
        "receipt_doc": receipt_doc,
        "receipt_bytes": receipt_bytes,
        "draft_path": draft_path,
        "snapshot_bytes": snapshot_bytes,
        "safe_zettel_id": safe_zettel_id,
        "source_receipt_sha256": source_receipt_sha256,
        "restore_receipt_relative": restore_receipt_relative,
        "plan_sha256": plan_sha256,
    }


def draft_discard_restore_plan(
    archive_root: Path | str,
    *,
    receipt: Path | str,
) -> dict[str, Any]:
    result, _private = _draft_discard_restore_plan_core(
        archive_root,
        receipt=receipt,
    )
    return result


def draft_discard_restore(
    archive_root: Path | str,
    *,
    receipt: Path | str,
    expected_plan_sha256: str | None,
    reviewed_by: str | None,
) -> dict[str, Any]:
    result, private = _draft_discard_restore_plan_core(
        archive_root,
        receipt=receipt,
    )
    blockers = list(result["blockers"])
    expected = str(expected_plan_sha256 or "").strip().lower()
    reviewer = archive_services.safe_project_intake_actor_id(reviewed_by)
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        blockers.append("discard_draft_restore_plan_sha256_invalid")
    elif expected != private["plan_sha256"]:
        blockers.append("discard_draft_restore_plan_changed")
    if reviewer is None:
        blockers.append("discard_draft_restore_reviewer_invalid")
    if blockers or private["safe_zettel_id"] is None:
        return {
            **result,
            "ok": False,
            "state": "blocked",
            "dry_run": False,
            "approved": False,
            "lifecycle_action": "discard_draft_restore",
            "blockers": archive_services.unique_preserve_order(blockers),
            "would_change": [],
            "files_written": [],
        }
    root: Path = private["root"]
    with _DraftDiscardLock(root, private["safe_zettel_id"]):
        fresh, fresh_private = _draft_discard_restore_plan_core(
            root,
            receipt=receipt,
        )
        if not fresh["ok"] or fresh_private["plan_sha256"] != expected:
            return {
                **fresh,
                "ok": False,
                "state": "blocked",
                "dry_run": False,
                "approved": False,
                "lifecycle_action": "discard_draft_restore",
                "blockers": archive_services.unique_preserve_order(
                    [*fresh["blockers"], "discard_draft_restore_plan_changed"]
                ),
                "would_change": [],
                "files_written": [],
            }
        timestamp = _now()
        restore_receipt = {
            "schema": DRAFT_DISCARD_RESTORE_RECEIPT_SCHEMA,
            "action": "restore_discarded_draft",
            "archive_id": archive_services.read_archive_id(root),
            "zettel_id": fresh_private["safe_zettel_id"],
            "source_receipt_sha256": fresh_private["source_receipt_sha256"],
            "restore_plan_sha256": expected,
            "restored_path": fresh_private["receipt_doc"]["draft_path"],
            "restored_sha256": fresh_private["receipt_doc"]["draft_sha256"],
            "reviewed_by": reviewer,
            "created_at": timestamp,
        }
        restore_receipt_path = archive_services.archive_internal_path(
            root,
            fresh_private["restore_receipt_relative"],
        )
        draft_created = False
        try:
            archive_services._write_bytes_create_if_absent(
                fresh_private["draft_path"],
                fresh_private["snapshot_bytes"],
            )
            draft_created = True
            archive_services._write_bytes_create_if_absent(
                restore_receipt_path,
                _canonical_json_bytes(restore_receipt),
            )
        except OSError:
            if draft_created:
                fresh_private["draft_path"].unlink(missing_ok=True)
            restore_receipt_path.unlink(missing_ok=True)
            raise
    return {
        **fresh,
        "ok": True,
        "state": "restored",
        "dry_run": False,
        "approved": True,
        "lifecycle_action": "discard_draft_restore",
        "blockers": [],
        "would_change": [],
        "files_written": [
            fresh_private["receipt_doc"]["draft_path"],
            fresh_private["restore_receipt_relative"],
        ],
        "privacy_guards": {**fresh["privacy_guards"], "writes": True},
    }


def _resolve_json_input(
    root: Path,
    value: Path | str,
) -> tuple[Path | None, str | None]:
    raw = os.fspath(value).strip()
    if not raw:
        return None, "input_path_invalid"
    candidate = Path(raw).expanduser()
    try:
        if candidate.is_absolute():
            path = candidate.resolve()
        else:
            normalized = archive_services.normalize_archive_relative_path(raw)
            path = archive_services.archive_internal_path(root, normalized)
    except Exception:
        return None, "input_path_invalid"
    if not path.is_file() or path.is_symlink():
        return None, "input_file_missing_or_not_regular"
    return path, None


def _batch_request(
    root: Path,
    manifest_path: Path | str,
) -> tuple[dict[str, Any] | None, bytes | None, list[str]]:
    path, path_error = _resolve_json_input(root, manifest_path)
    if path_error or path is None:
        return None, None, [path_error or "input_path_invalid"]
    try:
        raw = path.read_bytes()
    except OSError:
        return None, None, ["input_file_unreadable"]
    try:
        loaded = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        return None, None, ["input_invalid_utf8"]
    except json.JSONDecodeError:
        return None, None, ["input_invalid_json"]
    if not isinstance(loaded, dict):
        return None, None, ["input_not_object"]
    return loaded, raw, []


def _safe_batch_title(
    value: Any,
) -> tuple[str | None, str | None]:
    if value is None:
        return None, None
    if not isinstance(value, str):
        return None, "title_not_string"
    title = value.strip()
    if not title:
        return None, "title_empty"
    if len(title) > OBJET_CAPTURE_BATCH_TITLE_MAX_CHARACTERS:
        return None, "title_too_long"
    if (
        any(ord(character) < 32 for character in title)
        or "\n" in title
        or "\r" in title
        or archive_services.source_intake_secret_like(title)
        or archive_services.source_intake_has_provider_url(title)
        or archive_services.contains_forbidden_location_reference(title)
    ):
        return None, "title_unsafe"
    return title, None


def _batch_plan_core(
    archive_root: Path | str,
    *,
    manifest_path: Path | str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = archive_services.require_existing_archive_root(archive_root)
    archive_id = archive_services.read_archive_id(root)
    request, request_bytes, blockers = _batch_request(root, manifest_path)
    item_results: list[dict[str, Any]] = []
    selection_items: list[dict[str, Any]] = []
    project_receipt: str | None = None
    batch_id: str | None = None
    if request is not None:
        if request.get("schema") != OBJET_CAPTURE_BATCH_REQUEST_SCHEMA:
            blockers.append("batch_request_schema_invalid")
        batch_id_value = str(request.get("batch_id") or "").strip()
        if not archive_services.safe_source_intake_ref(batch_id_value):
            blockers.append("batch_id_invalid")
        else:
            batch_id = batch_id_value
        project_value = request.get("project_intake_receipt_path")
        if project_value is not None and not isinstance(project_value, str):
            blockers.append("project_intake_receipt_invalid")
        elif isinstance(project_value, str):
            project_receipt = project_value
        items = request.get("items")
        if not isinstance(items, list) or not items:
            blockers.append("batch_items_invalid")
            items = []
        elif len(items) > OBJET_CAPTURE_BATCH_MAX_ITEMS:
            blockers.append("batch_item_limit_exceeded")
            items = []

        structural: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        seen_paths: set[str] = set()
        for index, item in enumerate(items):
            codes: list[str] = []
            if not isinstance(item, dict):
                item_results.append(
                    {
                        "index": index,
                        "item_id": None,
                        "state": "blocked",
                        "blocker_codes": ["batch_item_not_object"],
                    }
                )
                blockers.append("batch_item_not_object")
                continue
            item_id = str(item.get("item_id") or "").strip()
            if not archive_services.safe_source_intake_ref(item_id):
                codes.append("batch_item_id_invalid")
            elif item_id in seen_ids:
                codes.append("batch_item_id_duplicate")
            else:
                seen_ids.add(item_id)
            raw_staged = item.get("staged_path")
            try:
                staged_path = archive_services.normalize_archive_relative_path(
                    str(raw_staged or "")
                )
            except Exception:
                staged_path = ""
                codes.append("unsafe_staged_path")
            if staged_path:
                if staged_path in seen_paths:
                    codes.append("duplicate_selection_target")
                else:
                    seen_paths.add(staged_path)
            source_receipt = item.get("source_intake_receipt_path")
            if not isinstance(source_receipt, str):
                codes.append("source_intake_evidence_invalid")
                source_receipt = ""
            safe_title, title_error = _safe_batch_title(item.get("title"))
            if title_error:
                codes.append(title_error)
            if codes:
                blockers.extend(codes)
                item_results.append(
                    {
                        "index": index,
                        "item_id": (
                            item_id
                            if archive_services.safe_source_intake_ref(item_id)
                            else None
                        ),
                        "state": "blocked",
                        "blocker_codes": archive_services.unique_preserve_order(
                            codes
                        ),
                    }
                )
            else:
                structural.append(
                    {
                        "index": index,
                        "item_id": item_id,
                        "staged_path": staged_path,
                        "source_intake_receipt_path": source_receipt,
                        "title": safe_title,
                    }
                )

        # Whole-manifest structural validation completes before source bytes are
        # opened. A single malformed row therefore blocks the entire batch.
        if not blockers:
            for item in structural:
                individual = archive_services.objet_capture_selection_manifest(
                    root,
                    staged_path=item["staged_path"],
                    source_intake_receipt=item[
                        "source_intake_receipt_path"
                    ],
                    item_id=item["item_id"],
                    project_intake_receipt=project_receipt,
                    dry_run=True,
                )
                codes = [
                    str(code) for code in individual.get("blockers", [])
                ]
                selection_manifest = individual.get("selection_manifest")
                selected_item = (
                    selection_manifest.get("items", [None])[0]
                    if isinstance(selection_manifest, dict)
                    else None
                )
                if codes or not isinstance(selected_item, dict):
                    blockers.extend(codes or ["batch_item_preflight_failed"])
                    item_results.append(
                        {
                            "index": item["index"],
                            "item_id": item["item_id"],
                            "state": "blocked",
                            "blocker_codes": codes
                            or ["batch_item_preflight_failed"],
                        }
                    )
                    continue
                if item["title"] is not None:
                    selected_item["title"] = item["title"]
                selection_items.append(selected_item)
                item_results.append(
                    {
                        "index": item["index"],
                        "item_id": item["item_id"],
                        "state": "ready",
                        "blocker_codes": [],
                    }
                )

    request_sha256 = (
        _sha256_bytes(request_bytes) if request_bytes is not None else None
    )
    selection = {
        "manifest_id": (
            f"selection-batch:{request_sha256[:16]}"
            if request_sha256 is not None
            else "selection-batch:invalid"
        ),
        "schema": archive_services.OBJET_CAPTURE_SELECTION_SCHEMA,
        "action": archive_services.OBJET_CAPTURE_SELECTION_ACTION,
        "archive_id": archive_id,
        "created_at": None,
        "created_by": None,
        "project_intake_receipt_path": project_receipt,
        "items": selection_items,
        "privacy_guards": {
            key: True
            for key in archive_services.OBJET_CAPTURE_REQUIRED_PRIVACY_GUARDS
        },
    }
    if not blockers:
        blockers.extend(
            archive_services.objet_capture_envelope_blockers(
                selection,
                archive_id,
            )
        )
    capture_preview: dict[str, Any] | None = None
    if not blockers:
        capture_preview = archive_services.objet_capture_document_dry_run(
            root,
            selection,
            project_intake_receipt=project_receipt,
        )
        if not capture_preview.get("ok"):
            blockers.extend(
                str(code)
                for code in capture_preview.get("blockers", [])
            )
            for entry in capture_preview.get("items", []):
                if isinstance(entry, dict):
                    blockers.extend(
                        str(code)
                        for code in entry.get("blockers", [])
                    )

    selection_sha256 = _sha256_bytes(_canonical_json_bytes(selection))
    plan_binding = {
        "schema": "wom-kit/objet-capture-batch-plan-binding/v0.1",
        "archive_id": archive_id,
        "batch_id": batch_id,
        "request_sha256": request_sha256,
        "selection_sha256": selection_sha256,
    }
    plan_sha256 = _sha256_bytes(_canonical_json_bytes(plan_binding))
    selection_relative = (
        f"{archive_services.OBJET_CAPTURE_SELECTION_MANIFESTS_DIR}/"
        f"batch.{selection_sha256[:16]}.selection.json"
    )
    aggregate_codes = archive_services.unique_preserve_order(blockers)
    summary = (
        capture_preview.get("summary", {})
        if isinstance(capture_preview, dict)
        else {}
    )
    result = {
        "ok": not aggregate_codes,
        "state": "ready" if not aggregate_codes else "blocked",
        "dry_run": True,
        "lifecycle_action": "objet_capture_batch_plan",
        "archive_id": archive_id,
        "summary": {
            "batch_id": batch_id,
            "request_sha256": request_sha256,
            "selection_sha256": selection_sha256,
            "plan_sha256": plan_sha256 if not aggregate_codes else None,
            "item_count": len(
                request.get("items", [])
                if isinstance(request, dict)
                and isinstance(request.get("items"), list)
                else []
            ),
            "ready_item_count": len(selection_items),
            "blocked_item_count": sum(
                1 for item in item_results if item["state"] == "blocked"
            ),
            "would_capture": summary.get("would_capture", 0),
            "would_skip": summary.get("would_skip", 0),
            "selection_path": selection_relative,
            "convergence_model": "bounded_per_item_with_replay",
            "all_or_nothing_claimed": False,
        },
        "items": sorted(item_results, key=lambda item: item["index"]),
        "blockers": aggregate_codes,
        "warnings": [],
        "would_change": [selection_relative] if not aggregate_codes else [],
        "privacy_guards": {
            "manifest_path_echoed": False,
            "staged_paths_echoed": False,
            "titles_echoed": False,
            "file_bodies_echoed": False,
            "source_bytes_hashed": bool(capture_preview),
            "network_checked": False,
            "provider_called": False,
            "writes": False,
        },
    }
    private = {
        "root": root,
        "request": request,
        "request_sha256": request_sha256,
        "selection": selection,
        "selection_bytes": _canonical_json_bytes(selection),
        "selection_sha256": selection_sha256,
        "selection_relative": selection_relative,
        "plan_sha256": plan_sha256,
        "project_receipt": project_receipt,
    }
    return result, private


def objet_capture_batch_plan(
    archive_root: Path | str,
    *,
    manifest_path: Path | str,
) -> dict[str, Any]:
    result, _private = _batch_plan_core(
        archive_root,
        manifest_path=manifest_path,
    )
    return result


def objet_capture_batch_apply(
    archive_root: Path | str,
    *,
    manifest_path: Path | str,
    expected_plan_sha256: str | None,
    reviewed_by: str | None,
) -> dict[str, Any]:
    result, private = _batch_plan_core(
        archive_root,
        manifest_path=manifest_path,
    )
    blockers = list(result["blockers"])
    expected = str(expected_plan_sha256 or "").strip().lower()
    reviewer = archive_services.safe_project_intake_actor_id(reviewed_by)
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        blockers.append("batch_expected_plan_sha256_invalid")
    elif expected != private["plan_sha256"]:
        blockers.append("batch_plan_changed")
    if reviewer is None:
        blockers.append("batch_reviewer_invalid")
    if blockers:
        return {
            **result,
            "ok": False,
            "state": "blocked",
            "dry_run": False,
            "approved": False,
            "lifecycle_action": "objet_capture_batch",
            "blockers": archive_services.unique_preserve_order(blockers),
            "would_change": [],
            "files_written": [],
        }

    root: Path = private["root"]
    selection_path = archive_services.archive_internal_path(
        root,
        private["selection_relative"],
    )
    selection_written = False
    if selection_path.exists():
        try:
            if selection_path.read_bytes() != private["selection_bytes"]:
                blockers.append("batch_selection_collision")
        except OSError:
            blockers.append("batch_selection_unreadable")
    else:
        try:
            archive_services._write_bytes_create_if_absent(
                selection_path,
                private["selection_bytes"],
            )
            selection_written = True
        except OSError:
            blockers.append("batch_selection_write_failed")
    if blockers:
        return {
            **result,
            "ok": False,
            "state": "blocked",
            "dry_run": False,
            "approved": False,
            "lifecycle_action": "objet_capture_batch",
            "blockers": archive_services.unique_preserve_order(blockers),
            "would_change": [],
            "files_written": [],
        }

    capture = archive_services.objet_capture_apply(
        root,
        selection_path,
        reviewed_by=reviewer,
        project_intake_receipt=private["project_receipt"],
    )
    timestamp = _now()
    batch_receipt_relative = (
        f"{OBJET_CAPTURE_BATCH_RECEIPTS_DIR}/"
        f"{private['plan_sha256']}.json"
    )
    batch_receipt_path = archive_services.archive_internal_path(
        root,
        batch_receipt_relative,
    )
    batch_receipt = {
        "schema": OBJET_CAPTURE_BATCH_RECEIPT_SCHEMA,
        "archive_id": archive_services.read_archive_id(root),
        "batch_id": result["summary"]["batch_id"],
        "request_sha256": private["request_sha256"],
        "selection_sha256": private["selection_sha256"],
        "plan_sha256": private["plan_sha256"],
        "selection_path": private["selection_relative"],
        "capture_receipt_path": capture.get("receipt_path"),
        "status_class": capture.get("status_class"),
        "ok": bool(capture.get("ok")),
        "reviewed_by": reviewer,
        "created_at": timestamp,
        "convergence_model": "bounded_per_item_with_replay",
        "all_or_nothing_claimed": False,
        "privacy": {
            "manifest_values_included": False,
            "staged_paths_included": False,
            "titles_included": False,
        },
    }
    receipt_written = False
    if batch_receipt_path.exists():
        try:
            prior = json.loads(batch_receipt_path.read_text(encoding="utf-8"))
            if (
                not isinstance(prior, dict)
                or prior.get("plan_sha256") != private["plan_sha256"]
            ):
                blockers.append("batch_receipt_collision")
        except (OSError, json.JSONDecodeError):
            blockers.append("batch_receipt_unreadable")
    else:
        try:
            archive_services._write_bytes_create_if_absent(
                batch_receipt_path,
                _canonical_json_bytes(batch_receipt),
            )
            receipt_written = True
        except OSError:
            blockers.append("batch_receipt_write_failed")

    projected_items = [
        {
            "item_id": item.get("item_id"),
            "planned_action": item.get("planned_action"),
            "action": item.get("action"),
            "status_class": item.get("status_class"),
            "blockers": item.get("blockers", []),
            "warnings": item.get("warnings", []),
        }
        for item in capture.get("items", [])
        if isinstance(item, dict)
    ]
    files_written = []
    if selection_written:
        files_written.append(private["selection_relative"])
    files_written.extend(
        str(path) for path in capture.get("files_written", [])
    )
    if receipt_written:
        files_written.append(batch_receipt_relative)
    final_ok = bool(capture.get("ok")) and not blockers
    return {
        **result,
        "ok": final_ok,
        "state": (
            "written"
            if final_ok
            else capture.get("status_class")
            or "blocked"
        ),
        "dry_run": False,
        "approved": True,
        "lifecycle_action": "objet_capture_batch",
        "summary": {
            **result["summary"],
            "capture_summary": capture.get("summary", {}),
            "capture_receipt_path": capture.get("receipt_path"),
            "batch_receipt_path": batch_receipt_relative,
            "status_class": capture.get("status_class"),
        },
        "items": projected_items,
        "blockers": archive_services.unique_preserve_order(
            [*blockers, *capture.get("blockers", [])]
        ),
        "warnings": archive_services.unique_preserve_order(
            capture.get("warnings", [])
        ),
        "would_change": [],
        "files_written": archive_services.unique_preserve_order(files_written),
        "privacy_guards": {
            **result["privacy_guards"],
            "writes": True,
        },
    }


class _MarkupMutationLock:
    def __init__(self, root: Path) -> None:
        lock_dir = archive_services.archive_internal_path(
            root,
            f"{MARKUP_NORMALIZATION_SCRATCH_DIR}/locks",
        )
        lock_dir.mkdir(parents=True, exist_ok=True)
        self._path = lock_dir / "mutation.lock"
        self._handle: Any = None

    def __enter__(self) -> "_MarkupMutationLock":
        self._handle = self._path.open("a+b")
        self._handle.seek(0, os.SEEK_END)
        if self._handle.tell() == 0:
            self._handle.write(b"\0")
            self._handle.flush()
            os.fsync(self._handle.fileno())
        self._handle.seek(0)
        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    msvcrt.locking(
                        self._handle.fileno(),
                        msvcrt.LK_LOCK,
                        1,
                    )
                    break
                except OSError:
                    continue
        else:
            import fcntl

            fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc_info: Any) -> bool:
        try:
            self._handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(
                    self._handle.fileno(),
                    msvcrt.LK_UNLCK,
                    1,
                )
            else:
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()
        return False


def markup_style_guide() -> dict[str, Any]:
    return {
        "ok": True,
        "dry_run": True,
        "lifecycle_action": "markup_style_guide",
        "policy_choices": {
            "preserve": (
                "Keep source markup byte-for-byte; record that no canonical "
                "normalization was requested."
            ),
            "normalize": (
                "Remove reviewed migration wrappers while preserving visible "
                "text and immutable before-byte snapshots."
            ),
        },
        "rules": [
            {
                "markup": "empty-block",
                "action": "discard_marker_only",
                "visible_text_preserved": True,
            },
            {
                "markup": "span",
                "action": "remove_wrapper_preserve_inner_text",
                "visible_text_preserved": True,
            },
            {
                "markup": "article_div_section_p",
                "action": "convert_container_boundary_to_markdown_paragraph_boundary",
                "visible_text_preserved": True,
            },
            {
                "markup": "file_audio_video_media_mention_synced_ref",
                "action": "require_reviewed_objet_edge_or_locator_binding",
                "silent_deletion_allowed": False,
            },
            {
                "markup": "self_closing_mention_date",
                "action": "render_strict_iso_date_time_and_timezone_as_text",
                "visible_text_preserved": True,
            },
            {
                "markup": "unknown:table_of_contents",
                "action": "remove_exact_generated_navigation_placeholder",
                "authored_body_text_preserved": True,
                "generated_navigation_materialized": False,
            },
            {
                "markup": "unknown_synced_and_transclusion_placeholders",
                "action": "require_reviewed_static_zettel_or_objet_binding",
                "accepted_shape": "exact_lowercase_attribute_free_self_closing",
                "live_sync_or_transclusion_claimed": False,
                "silent_deletion_allowed": False,
            },
            {
                "markup": "database",
                "action": "require_reviewed_zettel_reference_for_empty_strict_pair",
                "database_view_materialized": False,
                "silent_deletion_allowed": False,
            },
            {
                "markup": "synced_block_and_synced_block_reference",
                "action": "remove_migration_wrapper_preserve_complete_inner_snapshot",
                "visible_text_preserved": True,
                "live_sync_claimed": False,
            },
            {
                "markup": "callout_unknown_column_and_unsupported",
                "action": "block_pending_lossless_structure_or_source_recovery",
                "silent_deletion_allowed": False,
            },
            {
                "markup": "protected_context",
                "action": "preserve_entire_zettel_as_expected_terminal_literal",
                "source_bytes_preserved": True,
                "partial_outside_span_normalization_implemented": False,
            },
            {
                "markup": "unknown_semantic_tag",
                "action": "block_and_report_tag_name",
                "silent_deletion_allowed": False,
            },
            {
                "markup": "markdown_compatible_inline_html",
                "action": "preserve",
                "silent_rewrite_allowed": False,
            },
        ],
        "truth_boundaries": {
            "normalization_is_import": False,
            "normalization_infers_relations": False,
            "normalization_deletes_unknown_semantics": False,
            "normalization_preserves_live_provider_sync": False,
            "normalization_reconstructs_transcluded_children": False,
            "protected_context_is_actionable_migration_debt": False,
            "source_bytes_snapshotted_before_write": True,
            "revert_is_exact_byte_restore": True,
        },
        "would_change": [],
    }


def _verified_edge_binding(
    root: Path,
    *,
    zettel_id: str,
    edge_id: str,
) -> bool:
    try:
        path = archive_services.resolve_zettel_path(
            root,
            zettel_id=zettel_id,
            relative_path=None,
        )
        frontmatter, _body = archive_services.require_readable_zettel_content(
            path
        )
    except archive_services.ArchiveServiceError:
        return False
    edges = frontmatter.get("edges")
    return isinstance(edges, list) and any(
        isinstance(item, dict)
        and item.get("edge_id") == edge_id
        and isinstance(item.get("target"), str)
        and bool(item.get("target"))
        for item in edges
    )


def _verified_locator_binding(
    root: Path,
    *,
    zettel_id: str,
    locator_id: str,
) -> bool:
    record, _raw, error = _read_locator_record(root, zettel_id)
    return (
        error is None
        and isinstance(record, dict)
        and any(
            isinstance(item, dict)
            and item.get("locator_id") == locator_id
            and item.get("status") == "active"
            for item in record.get("locators", [])
        )
    )


def _verified_objet_binding(
    root: Path,
    *,
    object_id: str,
    manifest_index: dict[str, dict[str, Any]],
) -> bool:
    return (
        archive_services.OBJECT_ID_RE.fullmatch(object_id) is not None
        and object_id in manifest_index
    )


def _verified_zettel_reference_binding(
    root: Path,
    *,
    source_zettel_id: str,
    target_zettel_id: str,
    snapshots_by_id: dict[str, list[Any]],
) -> bool:
    """Verify one reviewed navigational target without inferring an edge."""

    if (
        _safe_zettel_id(target_zettel_id) is None
        or target_zettel_id == source_zettel_id
    ):
        return False
    matches = snapshots_by_id.get(target_zettel_id, [])
    if len(matches) != 1:
        return False
    snapshot = matches[0]
    inspection = snapshot.inspection
    frontmatter = inspection.get("frontmatter")
    if not (
        snapshot.relative_path.startswith("zettels/")
        and isinstance(frontmatter, dict)
        and bool(inspection.get("metadata_readable"))
        and frontmatter.get("id") == target_zettel_id
        and frontmatter.get("archive_id")
        == archive_services.read_archive_id(root)
        and frontmatter.get("status") == "canonical"
        and not archive_services.validate_schema(
            frontmatter,
            "zettel-frontmatter.schema.json",
        )
    ):
        return False
    try:
        validated = archive_services.validated_zet_revision_snapshot(
            snapshot.path,
            expected_zettel_id=target_zettel_id,
            expected_archive_id=archive_services.read_archive_id(root),
        )
    except (
        archive_services.ArchiveServiceError,
        OSError,
        RuntimeError,
        UnicodeError,
        ValueError,
    ):
        return False
    return validated.get("ok") is True


def _reject_duplicate_json_members(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_member")
        result[key] = value
    return result


def _markup_reference_bindings(
    root: Path,
    *,
    binding_manifest: Path | str | None,
) -> tuple[
    dict[
        str,
        dict[str, dict[int | None, dict[str, str | int | None]]],
    ],
    str | None,
    list[str],
]:
    if binding_manifest is None:
        return {}, None, []
    path, path_error = _resolve_json_input(root, binding_manifest)
    if path_error or path is None:
        return {}, None, ["markup_binding_manifest_path_invalid"]
    try:
        path.resolve().relative_to(root.resolve())
        raw = path.read_bytes()
        loaded = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_json_members,
        )
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ):
        return {}, None, ["markup_binding_manifest_invalid"]
    archive_id = archive_services.read_archive_id(root)
    manifest_schema = loaded.get("schema") if isinstance(loaded, dict) else None
    supported_manifest_schemas = {
        MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA,
        *MARKUP_REFERENCE_BINDING_MANIFEST_LEGACY_SCHEMAS,
    }
    if (
        not isinstance(loaded, dict)
        or set(loaded) != {"schema", "archive_id", "bindings"}
        or not isinstance(manifest_schema, str)
        or manifest_schema not in supported_manifest_schemas
        or loaded.get("archive_id") != archive_id
        or not isinstance(loaded.get("bindings"), list)
        or len(loaded["bindings"]) > MARKUP_NORMALIZATION_MAX_CHANGES
    ):
        return {}, None, ["markup_binding_manifest_invalid"]

    blockers: list[str] = []
    bindings: dict[
        str,
        dict[str, dict[int | None, dict[str, str | int | None]]],
    ] = {}
    objet_manifest_index: dict[str, dict[str, Any]] | None = None
    zettel_snapshots_by_id: dict[str, list[Any]] = {}
    zettel_snapshot_boundary_valid = True
    try:
        snapshots = archive_services.strict_local_zettel_snapshots(root)
    except (
        archive_services.ArchiveServiceError,
        OSError,
        RuntimeError,
        UnicodeError,
        ValueError,
    ):
        snapshots = []
        zettel_snapshot_boundary_valid = False
    for snapshot in snapshots:
        frontmatter = snapshot.inspection.get("frontmatter")
        candidate_id = (
            frontmatter.get("id")
            if isinstance(frontmatter, dict)
            else None
        )
        if isinstance(candidate_id, str) and candidate_id:
            zettel_snapshots_by_id.setdefault(candidate_id, []).append(
                snapshot
            )
    for item in loaded["bindings"]:
        if not isinstance(item, dict):
            blockers.append("markup_binding_manifest_invalid")
            continue
        allowed_keys = {
            "zettel_id",
            "tag_sha256",
            "binding_kind",
            "binding_id",
        }
        if manifest_schema == MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA:
            allowed_keys.add("occurrence_index")
        if (
            not {
                "zettel_id",
                "tag_sha256",
                "binding_kind",
                "binding_id",
            }.issubset(item)
            or set(item) - allowed_keys
        ):
            blockers.append("markup_binding_manifest_invalid")
            continue
        raw_zettel_id = item.get("zettel_id")
        raw_tag_sha256 = item.get("tag_sha256")
        raw_binding_kind = item.get("binding_kind")
        raw_binding_id = item.get("binding_id")
        zettel_id = (
            raw_zettel_id
            if isinstance(raw_zettel_id, str)
            and _safe_zettel_id(raw_zettel_id) == raw_zettel_id
            else None
        )
        tag_sha256 = (
            raw_tag_sha256
            if isinstance(raw_tag_sha256, str)
            and raw_tag_sha256 == raw_tag_sha256.strip().lower()
            else ""
        )
        binding_kind = (
            raw_binding_kind
            if isinstance(raw_binding_kind, str)
            and raw_binding_kind == raw_binding_kind.strip().lower()
            else ""
        )
        binding_id = (
            raw_binding_id
            if isinstance(raw_binding_id, str)
            and raw_binding_id == raw_binding_id.strip()
            else ""
        )
        occurrence_index: int | None = None
        if "occurrence_index" in item:
            raw_occurrence_index = item["occurrence_index"]
            if (
                type(raw_occurrence_index) is not int
                or not 1
                <= raw_occurrence_index
                <= MARKUP_NORMALIZATION_MAX_CHANGES
            ):
                blockers.append("markup_binding_manifest_invalid")
                continue
            occurrence_index = raw_occurrence_index
        if (
            zettel_id is None
            or not re.fullmatch(r"[0-9a-f]{64}", tag_sha256)
            or binding_kind not in MARKUP_REFERENCE_BINDING_KINDS
            or not isinstance(raw_binding_id, str)
            or raw_binding_id != raw_binding_id.strip()
            or (
                manifest_schema
                in MARKUP_REFERENCE_BINDING_MANIFEST_LEGACY_SCHEMAS
                and binding_kind == "zettel_reference"
            )
        ):
            blockers.append("markup_binding_manifest_invalid")
            continue
        if not zettel_snapshot_boundary_valid:
            blockers.append("markup_binding_source_unverified")
            if binding_kind == "zettel_reference":
                blockers.append(
                    "markup_zettel_reference_binding_unverified"
                )
            continue
        if len(zettel_snapshots_by_id.get(zettel_id, [])) != 1:
            blockers.append("markup_binding_source_unverified")
            continue
        source_relative_path = zettel_snapshots_by_id[zettel_id][
            0
        ].relative_path
        replacement: str | None = None
        if binding_kind == "external_locator":
            match = re.fullmatch(
                r"locator:sha256:(?P<digest>[0-9a-f]{64})",
                binding_id,
            )
            if (
                match is None
                or not _verified_locator_binding(
                    root,
                    zettel_id=zettel_id,
                    locator_id=binding_id,
                )
            ):
                blockers.append("markup_locator_binding_unverified")
            else:
                replacement = (
                    "[External reference]"
                    f"(wom-locator://sha256/{match.group('digest')})"
                )
        elif binding_kind == "zettel_edge":
            match = re.fullmatch(
                r"edge:(?P<digest>[0-9a-f]{64})",
                binding_id,
            )
            if (
                match is None
                or not _verified_edge_binding(
                    root,
                    zettel_id=zettel_id,
                    edge_id=binding_id,
                )
            ):
                blockers.append("markup_edge_binding_unverified")
            else:
                replacement = (
                    "[Related zettel]"
                    f"(wom-edge://sha256/{match.group('digest')})"
                )
        elif binding_kind == "zettel_reference":
            if not _verified_zettel_reference_binding(
                root,
                source_zettel_id=zettel_id,
                target_zettel_id=binding_id,
                snapshots_by_id=zettel_snapshots_by_id,
            ):
                blockers.append(
                    "markup_zettel_reference_binding_unverified"
                )
            else:
                replacement = (
                    "[Referenced zettel]"
                    f"(wom-zettel:{binding_id})"
                )
        else:
            match = re.fullmatch(
                r"sha256:(?P<digest>[0-9a-f]{64})",
                binding_id,
            )
            if objet_manifest_index is None:
                try:
                    objet_manifest_index = (
                        archive_services.manifest_records_by_object_id(root)
                    )
                except (
                    archive_services.ArchiveServiceError,
                    OSError,
                    ValueError,
                ):
                    objet_manifest_index = {}
            if (
                match is None
                or not _verified_objet_binding(
                    root,
                    object_id=binding_id,
                    manifest_index=objet_manifest_index,
                )
            ):
                blockers.append("markup_objet_binding_unverified")
            else:
                replacement = (
                    "[Attached objet]"
                    f"(wom-objet:sha256:{match.group('digest')})"
                )
        if replacement is None:
            continue
        zettel_bindings = bindings.setdefault(zettel_id, {})
        digest_bindings = zettel_bindings.setdefault(tag_sha256, {})
        if occurrence_index in digest_bindings:
            blockers.append("markup_binding_duplicate")
            continue
        if digest_bindings and (
            occurrence_index is None or None in digest_bindings
        ):
            blockers.append("markup_binding_occurrence_mixed")
            continue
        digest_bindings[occurrence_index] = {
            "binding_kind": binding_kind,
            "binding_id": binding_id,
            "replacement": replacement,
            "occurrence_index": occurrence_index,
            "source_relative_path": source_relative_path,
        }
    return (
        bindings,
        _sha256_bytes(raw),
        archive_services.unique_preserve_order(blockers),
    )


class _GfmTableParser(HTMLParser):
    """Parse one reviewed table fragment without interpreting the whole zet."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.table_depth = 0
        self.rows: list[list[dict[str, Any]]] = []
        self.current_row: list[dict[str, Any]] | None = None
        self.current_cell: dict[str, Any] | None = None
        self.section_stack: list[str] = []
        self.colgroup_depth = 0
        self.blockers: list[str] = []
        self.header_row_hint: bool | None = None
        self.header_column_hint: bool | None = None
        self.presentational_col_width_count = 0

    def add_blocker(self, code: str) -> None:
        if code not in self.blockers:
            self.blockers.append(code)

    @staticmethod
    def _attribute_names_are_unique(
        attrs: list[tuple[str, str | None]],
    ) -> bool:
        names = [name.casefold() for name, _value in attrs]
        return len(names) == len(set(names))

    @staticmethod
    def _safe_inline_url(value: str) -> bool:
        if (
            not value
            or len(value) > 2048
            or "|" in value
            or any(ord(character) < 0x20 for character in value)
            or _TABLE_CELL_UNSAFE_URL_SCHEME_RE.search(value)
        ):
            return False
        parsed = urllib.parse.urlsplit(value)
        if parsed.scheme.casefold() in {"http", "https"}:
            return bool(parsed.netloc)
        if parsed.scheme.casefold() == "mailto":
            return bool(parsed.path)
        return not parsed.scheme and value.startswith(("#", "/", "./", "../"))

    def _render_inline_start(
        self,
        name: str,
        attrs: list[tuple[str, str | None]],
    ) -> str | None:
        if not self._attribute_names_are_unique(attrs):
            self.add_blocker("markup_table_cell_attributes_unsupported")
            return None
        attributes = {key.casefold(): value for key, value in attrs}
        if name == "a":
            if set(attributes) - {"href", "title"}:
                self.add_blocker("markup_table_cell_attributes_unsupported")
                return None
            href = str(attributes.get("href") or "").strip()
            if not self._safe_inline_url(href):
                self.add_blocker("markup_table_cell_url_unsafe")
                return None
            title = attributes.get("title")
            if title is not None and (
                len(title) > 1000
                or "|" in title
                or any(ord(character) < 0x20 for character in title)
            ):
                self.add_blocker("markup_table_cell_attributes_unsupported")
                return None
            rendered = f'<a href="{html.escape(href, quote=True)}"'
            if title is not None:
                rendered += f' title="{html.escape(title, quote=True)}"'
            return rendered + ">"
        if name == "abbr":
            if set(attributes) - {"title"}:
                self.add_blocker("markup_table_cell_attributes_unsupported")
                return None
            title = attributes.get("title")
            if title is None:
                return "<abbr>"
            if (
                len(title) > 1000
                or "|" in title
                or any(ord(character) < 0x20 for character in title)
            ):
                self.add_blocker("markup_table_cell_attributes_unsupported")
                return None
            return f'<abbr title="{html.escape(title, quote=True)}">'
        if attributes:
            self.add_blocker("markup_table_cell_attributes_unsupported")
            return None
        return f"<{name}>"

    def _span_attributes_are_safe(
        self,
        attrs: list[tuple[str, str | None]],
    ) -> bool:
        if not self._attribute_names_are_unique(attrs):
            return False
        attributes = {key.casefold(): value for key, value in attrs}
        if set(attributes) - _TABLE_CELL_SPAN_ATTRIBUTES:
            return False
        if "color" in attributes and re.fullmatch(
            r"[A-Za-z][A-Za-z0-9_-]{0,63}",
            str(attributes["color"] or "").strip(),
        ) is None:
            return False
        if "underline" in attributes and str(
            attributes["underline"] or ""
        ).strip().casefold() not in {"", "true", "false"}:
            return False
        discussion_urls = attributes.get("discussion-urls")
        return discussion_urls is None or (
            len(discussion_urls) <= 4096
            and not any(ord(character) < 0x20 for character in discussion_urls)
            and "<" not in discussion_urls
            and ">" not in discussion_urls
            and _TABLE_CELL_UNSAFE_URL_SCHEME_RE.search(discussion_urls) is None
        )

    def _handle_cell_start(
        self,
        name: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if self.current_cell is None:
            return
        if name == "br":
            if attrs:
                self.add_blocker("markup_table_cell_attributes_unsupported")
            else:
                self.current_cell["parts"].append(("markup", "<br>"))
            return
        if name == "span":
            if not self._span_attributes_are_safe(attrs):
                self.add_blocker("markup_table_cell_attributes_unsupported")
                return
            self.current_cell["inline_stack"].append(name)
            return
        if name in _TABLE_CELL_PAIRED_INLINE_TAGS:
            rendered = self._render_inline_start(name, attrs)
            if rendered is None:
                return
            self.current_cell["parts"].append(("markup", rendered))
            self.current_cell["inline_stack"].append(name)
            return
        self.add_blocker("markup_table_cell_markup_unsupported")

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        name = tag.casefold()
        if (
            (name == "table" or self.table_depth == 1)
            and not self._attribute_names_are_unique(attrs)
        ):
            self.add_blocker("markup_table_attributes_duplicate")
        attributes = {key.casefold(): value for key, value in attrs}
        if name == "table":
            self.table_depth += 1
            if self.table_depth != 1:
                self.add_blocker("markup_table_nested_unsupported")
                return
            for attribute_name, target_name in (
                ("header-row", "header_row_hint"),
                ("header-column", "header_column_hint"),
            ):
                if attribute_name not in attributes:
                    continue
                value = str(attributes[attribute_name] or "").strip().casefold()
                if value not in {"true", "false"}:
                    self.add_blocker("markup_table_header_semantics_unsupported")
                else:
                    setattr(self, target_name, value == "true")
            if set(attributes) - {"class", "header-row", "header-column"}:
                self.add_blocker("markup_table_attributes_unsupported")
            return
        if self.table_depth != 1:
            return
        if name in {"thead", "tbody", "tfoot"}:
            if attrs:
                self.add_blocker(
                    "markup_table_structure_attributes_unsupported"
                )
            if (
                self.current_row is not None
                or self.current_cell is not None
                or self.section_stack
                or self.colgroup_depth
            ):
                self.add_blocker("markup_table_structure_invalid")
            else:
                self.section_stack.append(name)
            return
        if name == "colgroup":
            if attrs:
                self.add_blocker(
                    "markup_table_structure_attributes_unsupported"
                )
            if (
                self.current_row is not None
                or self.current_cell is not None
                or self.section_stack
                or self.colgroup_depth
            ):
                self.add_blocker("markup_table_structure_invalid")
            else:
                self.colgroup_depth = 1
            return
        if name == "col":
            if self.current_row is not None or self.current_cell is not None:
                self.add_blocker("markup_table_structure_invalid")
            unsupported = set(attributes) - {"width"}
            width = str(attributes.get("width") or "").strip()
            if unsupported or (
                "width" in attributes
                and re.fullmatch(r"[1-9][0-9]*(?:\.[0-9]+)?", width) is None
            ):
                self.add_blocker("markup_table_column_semantics_unsupported")
            elif "width" in attributes:
                self.presentational_col_width_count += 1
            return
        if name == "tr":
            if attrs:
                self.add_blocker(
                    "markup_table_structure_attributes_unsupported"
                )
            if self.current_row is not None or self.current_cell is not None:
                self.add_blocker("markup_table_structure_invalid")
            if self.colgroup_depth:
                self.add_blocker("markup_table_structure_invalid")
            self.current_row = []
            return
        if name in {"td", "th"}:
            if self.current_row is None or self.current_cell is not None:
                self.add_blocker("markup_table_structure_invalid")
                return
            for span_name in ("rowspan", "colspan"):
                span_value = str(attributes.get(span_name) or "1").strip()
                if span_value != "1":
                    self.add_blocker("markup_table_span_unsupported")
            alignment = str(attributes.get("align") or "").strip().casefold()
            if alignment not in {"", "left", "center", "right"}:
                self.add_blocker("markup_table_alignment_unsupported")
            style = str(attributes.get("style") or "").strip().casefold()
            if style:
                match = re.fullmatch(
                    r"\s*text-align\s*:\s*(left|center|right)\s*;?\s*",
                    style,
                )
                if match is None:
                    self.add_blocker("markup_table_cell_semantics_unsupported")
                elif alignment and alignment != match.group(1):
                    self.add_blocker("markup_table_alignment_conflict")
                elif not alignment:
                    alignment = match.group(1)
            unsupported_attributes = set(attributes) - {
                "align",
                "colspan",
                "rowspan",
                "style",
            }
            if unsupported_attributes:
                self.add_blocker("markup_table_cell_semantics_unsupported")
            self.current_cell = {
                "kind": name,
                "parts": [],
                "alignment": alignment or None,
                "inline_stack": [],
            }
            return
        if self.current_cell is None:
            if name not in {"caption"}:
                self.add_blocker("markup_table_structure_invalid")
            else:
                self.add_blocker("markup_table_caption_unsupported")
            return
        self._handle_cell_start(name, attrs)

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        name = tag.casefold()
        if name in {
            "table",
            "thead",
            "tbody",
            "tfoot",
            "tr",
            "td",
            "th",
            "colgroup",
            "col",
        }:
            self.add_blocker("markup_table_structure_invalid")
            return
        if self.table_depth == 1 and self.current_cell is not None:
            if name == "mention-date":
                raw = self.get_starttag_text() or ""
                match = _MARKUP_TAG_RE.fullmatch(raw)
                rendered = (
                    _render_self_closing_mention_date(
                        match.group("attrs") or ""
                    )
                    if match is not None
                    and match.group("name").casefold() == "mention-date"
                    and match.group("self") is not None
                    else None
                )
                if rendered is None:
                    self.add_blocker(
                        "markup_mention_date_attributes_unsupported"
                    )
                else:
                    self.current_cell["parts"].append(("text", rendered))
                return
            if name == "br":
                self._handle_cell_start(name, attrs)
                return
            self.add_blocker("markup_table_cell_markup_unsupported")
            return
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        name = tag.casefold()
        if name == "table":
            if self.table_depth == 1 and (
                self.current_row is not None
                or self.current_cell is not None
                or self.section_stack
                or self.colgroup_depth
            ):
                self.add_blocker("markup_table_structure_invalid")
            self.table_depth = max(0, self.table_depth - 1)
            return
        if self.table_depth != 1:
            return
        if name in {"thead", "tbody", "tfoot"}:
            if (
                self.current_row is not None
                or self.current_cell is not None
                or not self.section_stack
                or self.section_stack[-1] != name
            ):
                self.add_blocker("markup_table_structure_invalid")
            else:
                self.section_stack.pop()
            return
        if name == "colgroup":
            if (
                self.current_row is not None
                or self.current_cell is not None
                or self.colgroup_depth != 1
            ):
                self.add_blocker("markup_table_structure_invalid")
            else:
                self.colgroup_depth = 0
            return
        if name == "col":
            self.add_blocker("markup_table_structure_invalid")
            return
        if name in {"td", "th"}:
            if self.current_cell is None or self.current_row is None:
                self.add_blocker("markup_table_structure_invalid")
                return
            if self.current_cell["kind"] != name:
                self.add_blocker("markup_table_structure_invalid")
            if self.current_cell["inline_stack"]:
                self.add_blocker("markup_table_cell_markup_unbalanced")
            self.current_row.append(self.current_cell)
            self.current_cell = None
            return
        if name == "tr":
            if self.current_row is None or self.current_cell is not None:
                self.add_blocker("markup_table_structure_invalid")
                return
            if self.current_row:
                self.rows.append(self.current_row)
            else:
                self.add_blocker("markup_table_structure_invalid")
            self.current_row = None
            return
        if self.current_cell is not None:
            stack = self.current_cell["inline_stack"]
            if name not in {"span", *_TABLE_CELL_PAIRED_INLINE_TAGS}:
                self.add_blocker("markup_table_cell_markup_unsupported")
            elif not stack or stack[-1] != name:
                self.add_blocker("markup_table_cell_markup_unbalanced")
            else:
                stack.pop()
                if name != "span":
                    self.current_cell["parts"].append(
                        ("markup", f"</{name}>")
                    )
            return
        self.add_blocker("markup_table_structure_invalid")

    def handle_comment(self, data: str) -> None:
        if self.table_depth == 1:
            self.add_blocker("markup_table_cell_markup_unsupported")

    def handle_decl(self, decl: str) -> None:
        if self.table_depth == 1:
            self.add_blocker("markup_table_cell_markup_unsupported")

    def handle_pi(self, data: str) -> None:
        if self.table_depth == 1:
            self.add_blocker("markup_table_cell_markup_unsupported")

    def unknown_decl(self, data: str) -> None:
        if self.table_depth == 1:
            self.add_blocker("markup_table_cell_markup_unsupported")

    def handle_data(self, data: str) -> None:
        if self.table_depth != 1:
            return
        if self.current_cell is not None:
            self.current_cell["parts"].append(("text", data))
        elif data.strip():
            self.add_blocker("markup_table_structure_invalid")

    def handle_entityref(self, name: str) -> None:
        if self.table_depth != 1:
            return
        if self.current_cell is not None:
            self.current_cell["parts"].append(("entity", f"&{name};"))
        else:
            self.add_blocker("markup_table_structure_invalid")

    def handle_charref(self, name: str) -> None:
        if self.table_depth != 1:
            return
        if self.current_cell is not None:
            self.current_cell["parts"].append(("entity", f"&#{name};"))
        else:
            self.add_blocker("markup_table_structure_invalid")

    def close_and_render(self) -> tuple[str | None, list[str]]:
        try:
            self.close()
        except Exception:
            self.add_blocker("markup_table_parse_failed")
        if (
            self.table_depth
            or self.current_row is not None
            or self.current_cell is not None
            or self.section_stack
            or self.colgroup_depth
        ):
            self.add_blocker("markup_table_structure_invalid")
        if not self.rows:
            self.add_blocker("markup_table_empty_unsupported")
        if self.blockers:
            return None, self.blockers

        width = max(len(row) for row in self.rows)
        if width == 0:
            return None, ["markup_table_empty_unsupported"]
        first_kinds = {cell["kind"] for cell in self.rows[0]}
        if "th" in first_kinds and first_kinds != {"th"}:
            return None, ["markup_table_header_layout_unsupported"]
        if any(
            cell["kind"] == "th"
            for row in self.rows[1:]
            for cell in row
        ):
            return None, ["markup_table_header_layout_unsupported"]

        has_header = first_kinds == {"th"} or self.header_row_hint is True
        header = self.rows[0] if has_header else []
        body_rows = self.rows[1:] if has_header else self.rows
        alignments: list[str | None] = [None] * width
        for index in range(width):
            observed = {
                row[index]["alignment"]
                for row in self.rows
                if index < len(row) and row[index].get("alignment")
            }
            if len(observed) > 1:
                return None, ["markup_table_alignment_conflict"]
            if observed:
                alignments[index] = next(iter(observed))

        def cell_text(cell: dict[str, Any] | None) -> str:
            if cell is None:
                return ""
            rendered_parts: list[str] = []
            for part_kind, part_value in cell["parts"]:
                value = str(part_value)
                if part_kind == "text":
                    value = re.sub(r"[ \t\r\n\f\v]+", " ", value)
                rendered_parts.append(value)
            value = "".join(rendered_parts)
            return value.strip(" \t\r\n\f\v").replace("|", r"\|")

        def row_text(
            row: list[dict[str, Any]],
            *,
            body_row: bool = False,
        ) -> str:
            cells = [
                cell_text(row[index] if index < len(row) else None)
                for index in range(width)
            ]
            if body_row and self.header_column_hint is True and cells and cells[0]:
                cells[0] = f"**{cells[0]}**"
            return "| " + " | ".join(cells) + " |"

        header_row = row_text(header) if has_header else row_text([])
        delimiters = []
        for alignment in alignments:
            delimiters.append(
                ":---:"
                if alignment == "center"
                else "---:"
                if alignment == "right"
                else ":---"
                if alignment == "left"
                else "---"
            )
        rendered = [header_row, "| " + " | ".join(delimiters) + " |"]
        rendered.extend(row_text(row, body_row=True) for row in body_rows)
        return "\n".join(rendered), []


_TABLE_FRAGMENT_RE = re.compile(
    r"(?is)<\s*table(?:\s+[^<>]*?)?\s*>.*?<\s*/\s*table\s*>"
)
_TABLE_CANDIDATE_RE = re.compile(r"(?is)<\s*/?\s*table\b")
_TABLE_STRUCTURE_TAG_RE = re.compile(
    r"(?is)<\s*/?\s*(?:table|thead|tbody|tfoot|tr|td|th|colgroup|col)"
    r"\b[^<>]*>"
)
_TABLE_OPEN_TAG_RE = re.compile(r"(?is)<\s*table\b[^<>]*>")
_TABLE_CLOSING_TAG_RE = re.compile(
    r"(?is)<(?P<before_slash>\s*)/(?P<after_slash>\s*)"
    r"(?P<name>[A-Za-z][A-Za-z0-9:-]*)(?P<tail>[^<>]*)>"
)
_TABLE_UNTERMINATED_ENTITY_RE = re.compile(
    r"&(?:#[xX][0-9A-Fa-f]+|#[0-9]+|[A-Za-z][A-Za-z0-9]*)"
    r"(?![A-Za-z0-9]*;)"
)
_TABLE_RAW_HTML_BLOCK_TAGS = frozenset(
    {
        "address",
        "article",
        "aside",
        "base",
        "basefont",
        "blockquote",
        "body",
        "caption",
        "center",
        "col",
        "colgroup",
        "dd",
        "details",
        "dialog",
        "dir",
        "div",
        "dl",
        "dt",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "form",
        "frame",
        "frameset",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "head",
        "header",
        "hr",
        "html",
        "iframe",
        "legend",
        "li",
        "link",
        "main",
        "menu",
        "menuitem",
        "nav",
        "noframes",
        "ol",
        "optgroup",
        "option",
        "p",
        "param",
        "search",
        "section",
        "summary",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "title",
        "tr",
        "track",
        "ul",
    }
)
_TABLE_RAW_HTML_BLOCK_START_RE = re.compile(
    r"^ {0,3}<\s*/?\s*(?P<name>[A-Za-z][A-Za-z0-9:-]*)"
    r"(?:[ \t]+|/?>)"
)
_TABLE_RAW_HTML_COMPLETE_TAG_LINE_RE = re.compile(
    r'''(?x)^[ ]{0,3}(?:
        </[A-Za-z][A-Za-z0-9:-]*\s*>
        |
        <[A-Za-z][A-Za-z0-9:-]*
        (?:\s+[A-Za-z_:][A-Za-z0-9_.:-]*
            (?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'=<>`]+))?
        )*\s*/?>
    )[ \t]*$'''
)
_TABLE_ATX_HEADING_LINE_RE = re.compile(
    r"^ {0,3}#{1,6}(?:[ \t]+|$)"
)
_TABLE_MARKDOWN_LIST_MARKER_RE = re.compile(
    r"^(?P<indent> {0,3})(?P<marker>[*+-]|[0-9]{1,9}[.)])"
    r"(?P<spacing>[ \t]+)"
)


def _table_unterminated_entity_is_ambiguous(
    match: re.Match[str],
) -> bool:
    token = match.group(0)[1:]
    if token.startswith("#"):
        return True
    return token in html.entities.html5 or f"{token};" in html.entities.html5


def _escape_unknown_table_entity_candidates(fragment: str) -> str:
    return _TABLE_UNTERMINATED_ENTITY_RE.sub(
        lambda match: "&amp;" + match.group(0)[1:],
        fragment,
    )


def _table_is_markdown_list_continuation(
    body: str,
    opening_line_start: int,
    opening_prefix: str,
) -> bool:
    opening_width = len(opening_prefix.expandtabs(4))
    if opening_width < 2:
        return False
    for line in reversed(body[:opening_line_start].splitlines()):
        if not line.strip():
            continue
        marker = _TABLE_MARKDOWN_LIST_MARKER_RE.match(line)
        if marker is not None:
            content_prefix = (
                marker.group("indent")
                + marker.group("marker")
                + marker.group("spacing")
            )
            return opening_width >= len(content_prefix.expandtabs(4))
        leading = re.match(r"[ \t]*", line)
        leading_width = len((leading.group(0) if leading else "").expandtabs(4))
        if leading_width < opening_width:
            return False
    return False


def _table_has_reviewed_raw_html_context(
    body: str,
    opening_line_start: int,
) -> bool:
    active_block_lines: list[str] = []
    for line in reversed(body[:opening_line_start].splitlines()):
        if not line.strip():
            break
        active_block_lines.append(line)
        match = _TABLE_RAW_HTML_BLOCK_START_RE.match(line)
        if (
            match is not None
            and match.group("name").casefold()
            in _TABLE_RAW_HTML_BLOCK_TAGS
        ):
            return True
    active_block_lines.reverse()
    for index, line in enumerate(active_block_lines):
        if _TABLE_RAW_HTML_COMPLETE_TAG_LINE_RE.fullmatch(line) is None:
            continue
        if index == 0 or _TABLE_ATX_HEADING_LINE_RE.match(
            active_block_lines[index - 1]
        ):
            return True
    return False


def _table_fragment_is_standalone(
    body: str,
    match: re.Match[str],
) -> bool:
    opening_line_start = body.rfind("\n", 0, match.start()) + 1
    opening_prefix = body[opening_line_start : match.start()]
    if opening_prefix.strip(" \t"):
        return False
    if _table_is_markdown_list_continuation(
        body,
        opening_line_start,
        opening_prefix,
    ):
        return False
    if (
        "\t" in opening_prefix or len(opening_prefix) > 3
    ) and not _table_has_reviewed_raw_html_context(
        body,
        opening_line_start,
    ):
        return False

    closing_line_end = body.find("\n", match.end())
    if closing_line_end < 0:
        closing_line_end = len(body)
    closing_suffix = body[match.end() : closing_line_end]
    return not closing_suffix.strip(" \t\r")


def _table_fragment_has_nested_table(fragment: str) -> bool:
    opening_count = 0
    for match in _TABLE_OPEN_TAG_RE.finditer(fragment):
        if not re.search(r"/\s*>\Z", match.group(0)):
            opening_count += 1
    return opening_count > 1


def _table_fragment_has_malformed_closing_tag(fragment: str) -> bool:
    return any(
        bool(match.group("before_slash"))
        or bool(match.group("after_slash"))
        or bool(match.group("tail").strip())
        for match in _TABLE_CLOSING_TAG_RE.finditer(fragment)
    )


def _normalize_gfm_tables(body: str) -> tuple[str, int, list[str]]:
    fragment_matches = list(_TABLE_FRAGMENT_RE.finditer(body))
    if not fragment_matches:
        if _TABLE_CANDIDATE_RE.search(body):
            return body, 0, ["markup_table_structure_invalid"]
        return body, 0, []

    fragment_spans = [
        (match.start(), match.end()) for match in fragment_matches
    ]
    structural_tag_outside_fragment = any(
        not any(
            start <= tag_match.start() and tag_match.end() <= end
            for start, end in fragment_spans
        )
        for tag_match in _TABLE_STRUCTURE_TAG_RE.finditer(body)
    )
    if structural_tag_outside_fragment and not any(
        _table_fragment_has_nested_table(match.group(0))
        for match in fragment_matches
    ):
        return body, 0, ["markup_table_structure_invalid"]

    if any(
        not _table_fragment_has_nested_table(match.group(0))
        and not _table_fragment_is_standalone(body, match)
        for match in fragment_matches
    ):
        return body, 0, ["markup_table_block_context_unsupported"]

    if any(
        _table_fragment_has_malformed_closing_tag(match.group(0))
        for match in fragment_matches
    ):
        return body, 0, ["markup_table_structure_invalid"]

    if any(
        any(
            _table_unterminated_entity_is_ambiguous(entity_match)
            for entity_match in _TABLE_UNTERMINATED_ENTITY_RE.finditer(
                match.group(0)
            )
        )
        for match in fragment_matches
    ):
        return body, 0, ["markup_table_entity_unterminated"]

    converted_count = 0
    blockers: list[str] = []

    def replacement(match: re.Match[str]) -> str:
        nonlocal converted_count
        parser = _GfmTableParser()
        try:
            parser.feed(
                _escape_unknown_table_entity_candidates(match.group(0))
            )
            rendered, fragment_blockers = parser.close_and_render()
        except Exception:
            rendered = None
            fragment_blockers = ["markup_table_parse_failed"]
        blockers.extend(fragment_blockers)
        if rendered is None:
            return match.group(0)
        converted_count += 1
        return "\n\n" + rendered + "\n\n"

    normalized = _TABLE_FRAGMENT_RE.sub(replacement, body)
    return (
        normalized,
        converted_count,
        archive_services.unique_preserve_order(blockers),
    )


_STRICT_MARKUP_ATTRIBUTE_RE = re.compile(
    r"\s+(?P<name>[A-Za-z_:][A-Za-z0-9_.:-]*)\s*=\s*"
    r"(?P<quote>[\"'])(?P<value>.*?)(?P=quote)",
    re.DOTALL,
)


def _strict_markup_attributes(raw: str) -> dict[str, str] | None:
    attributes: dict[str, str] = {}
    position = 0
    for match in _STRICT_MARKUP_ATTRIBUTE_RE.finditer(raw):
        if raw[position : match.start()].strip():
            return None
        name = match.group("name").casefold()
        if name in attributes:
            return None
        attributes[name] = html.unescape(match.group("value")).strip()
        position = match.end()
    if raw[position:].strip():
        return None
    return attributes


def _database_reference_attributes_supported(raw: str) -> bool:
    attributes = _strict_markup_attributes(raw)
    if attributes is None:
        return False
    required = {"inline", "url"}
    allowed = {"data-source-url", *required}
    if not required.issubset(attributes) or set(attributes) - allowed:
        return False
    if attributes["inline"] not in {"false", "true"}:
        return False
    for name in ("url", "data-source-url"):
        value = attributes.get(name)
        if value is not None and (
            not value
            or len(value) > 4096
            or any(ord(character) < 0x20 for character in value)
        ):
            return False
    return True


def _render_self_closing_mention_date(raw_attributes: str) -> str | None:
    attributes = _strict_markup_attributes(raw_attributes)
    allowed = {"start", "end", "starttime", "endtime", "timezone"}
    if attributes is None or set(attributes) - allowed:
        return None
    start = attributes.get("start")
    end = attributes.get("end")
    starttime = attributes.get("starttime")
    endtime = attributes.get("endtime")
    timezone_name = attributes.get("timezone")
    try:
        if start is None:
            return None
        datetime.strptime(start, "%Y-%m-%d")
        if end is not None:
            datetime.strptime(end, "%Y-%m-%d")
        for value in (starttime, endtime):
            if value is not None and re.fullmatch(
                r"(?:[01][0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?",
                value,
            ) is None:
                return None
    except ValueError:
        return None
    if endtime is not None and end is None:
        return None
    if timezone_name is not None and re.fullmatch(
        r"[A-Za-z_]+(?:/[A-Za-z0-9_+\-]+)+",
        timezone_name,
    ) is None:
        return None

    start_text = start + (f" {starttime}" if starttime else "")
    rendered = start_text
    if end is not None:
        rendered += " – " + end + (f" {endtime}" if endtime else "")
    if timezone_name is not None:
        rendered += f" ({timezone_name})"
    return rendered


def _contains_normalizable_markup(value: str) -> bool:
    return _PROTECTED_CONTEXT_MARKUP_RE.search(value) is not None


_MARKDOWN_CONTAINER_PREFIX_RE = re.compile(
    r" {0,3}(?:>[ \t]?|(?:[-+*]|[0-9]{1,9}[.)])[ \t]+)"
)


def _markdown_container_payload(line: str) -> str:
    offset = 0
    while True:
        container = _MARKDOWN_CONTAINER_PREFIX_RE.match(line, offset)
        if container is None:
            return line[offset:]
        offset = container.end()


def _quoted_html_attribute_contains_normalizable_markup(body: str) -> bool:
    index = 0
    while index < len(body):
        opening = body.find("<", index)
        if opening < 0:
            break
        cursor = opening + 1
        while cursor < len(body) and body[cursor] in " \t\r\n":
            cursor += 1
        name = re.match(r"[A-Za-z][A-Za-z0-9:-]*", body[cursor:])
        if name is None:
            index = opening + 1
            continue
        cursor += name.end()
        quote: str | None = None
        quoted_start = 0
        while cursor < len(body):
            character = body[cursor]
            if quote is not None:
                if character == quote:
                    if _contains_normalizable_markup(
                        body[quoted_start:cursor]
                    ):
                        return True
                    quote = None
                cursor += 1
                continue
            if character in {'"', "'"}:
                quote = character
                quoted_start = cursor + 1
            elif character == ">":
                cursor += 1
                break
            elif character == "<":
                break
            cursor += 1
        if quote is not None and _contains_normalizable_markup(
            body[quoted_start:cursor]
        ):
            return True
        index = max(opening + 1, cursor)
    return False


_REVIEWED_MIGRATION_RAW_HTML_BLOCK_TAGS = frozenset(
    {
        "article",
        "column",
        "columns",
        "details",
        "div",
        "p",
        "section",
        "table",
    }
)
_RAW_HTML_BLOCK_START_RE = re.compile(
    r"^ {0,3}<\s*(?P<closing>/)?\s*(?P<name>[A-Za-z][A-Za-z0-9:-]*)"
    r"(?:[ \t]+|/?>)"
)


def _unreviewed_raw_html_block_contains_normalizable_markup(
    body: str,
) -> bool:
    lines = []
    for source_line in body.splitlines(keepends=True):
        content = source_line.rstrip("\r\n")
        newline = source_line[len(content) :]
        lines.append(_markdown_container_payload(content) + newline)
    index = 0
    while index < len(lines):
        line = lines[index].rstrip("\r\n")
        opening = _RAW_HTML_BLOCK_START_RE.match(line)
        if opening is None:
            index += 1
            continue
        name = opening.group("name").casefold()
        is_type_6 = name in _TABLE_RAW_HTML_BLOCK_TAGS
        is_type_7 = (
            _TABLE_RAW_HTML_COMPLETE_TAG_LINE_RE.fullmatch(line) is not None
        )
        if not is_type_6 and not is_type_7:
            index += 1
            continue
        end = index + 1
        while end < len(lines) and lines[end].strip():
            end += 1
        if not opening.group("closing") and (
            name in _REVIEWED_MIGRATION_RAW_HTML_BLOCK_TAGS
            or name in _PROTECTED_CONTEXT_MARKUP_TAGS
        ):
            index = max(index + 1, end)
            continue
        block = "".join(lines[index:end])
        first_tag_end = block.find(">")
        payload = block[first_tag_end + 1 :] if first_tag_end >= 0 else block
        if _contains_normalizable_markup(payload):
            return True
        index = max(index + 1, end)
    return False


_REFERENCE_DEFINITION_START_RE = re.compile(
    r"(?ms)^ {0,3}\[(?:\\.|[^\\\[\]]){1,999}\][ \t]*:"
)


def _reference_definition_contains_normalizable_markup(body: str) -> bool:
    logical_lines: list[str] = []
    for line in body.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        newline = line[len(content) :]
        logical_lines.append(_markdown_container_payload(content) + newline)
    logical_body = "".join(logical_lines)

    for block in re.split(r"\r?\n[ \t]*\r?\n", logical_body):
        if (
            _REFERENCE_DEFINITION_START_RE.search(block) is not None
            and _contains_normalizable_markup(block)
        ):
            return True
    return False


def _fenced_code_spans(body: str) -> list[tuple[int, int]]:
    """Conservatively protect a document containing any fence-looking line.

    Correctly matching CommonMark fences inside arbitrarily nested list and
    blockquote containers requires retaining the complete container state.
    Letter 115 does not need to edit code examples, so a fence marker anywhere
    makes the whole document a protected span.  This deliberately prefers a
    false-positive blocker over treating a literal tag as live markup.
    """

    for line in body.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        payload = _markdown_container_payload(content)
        # Once a line has been reduced to its obvious container payload, keep
        # the guard deliberately broader than CommonMark's root-level
        # three-space rule.  A list continuation can legitimately indent its
        # fence by the list content offset (for example four or five spaces).
        # Treating any whitespace-prefixed fence-looking payload as protected
        # avoids rewriting literal markup when we do not retain full list
        # container state.
        if re.match(r"[ \t]*(?:`{3,}|~{3,})", payload) is not None:
            return [(0, len(body))]
    return []


def _protected_markup_context_present(body: str) -> bool:
    if (
        _quoted_html_attribute_contains_normalizable_markup(body)
        or _unreviewed_raw_html_block_contains_normalizable_markup(body)
        or _reference_definition_contains_normalizable_markup(body)
    ):
        return True
    fenced_spans = _fenced_code_spans(body)
    if any(
        _contains_normalizable_markup(body[start:end])
        for start, end in fenced_spans
    ):
        return True

    protected_patterns = (
        re.compile(r"(?is)<!--.*?(?:-->|\Z)"),
        re.compile(r"(?is)<\?.*?(?:\?>|\Z)"),
        re.compile(r"(?is)<!\[CDATA\[.*?(?:\]\]>|\Z)"),
        re.compile(r"(?is)<![A-Z].*?(?:>|\Z)"),
        re.compile(
            r"(?is)<\s*(?P<name>code|pre|script|style|textarea|xmp)"
            r"(?:\s+[^<>]*?)?\s*>"
            r".*?(?:<\s*/\s*(?P=name)\s*>|\Z)"
        ),
    )
    for pattern in protected_patterns:
        if any(
            _contains_normalizable_markup(match.group(0))
            for match in pattern.finditer(body)
        ):
            return True

    raw_container_spans = [
        (match.start(), match.end())
        for name in ("columns", "details")
        for match in re.finditer(
            rf"(?is)<\s*{name}\b[^<>]*>.*?<\s*/\s*{name}\s*>",
            body,
        )
    ]

    def blockquote_payload(value: str) -> str:
        payload = value
        while True:
            marker = re.match(r" {0,3}>[ \t]?", payload)
            if marker is None:
                break
            payload = payload[marker.end() :]
        return payload

    line_offset = 0
    previous_line_blank = True
    in_root_indented_code = False
    for line in body.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        payload = blockquote_payload(content)
        has_blockquote_container = payload != content
        is_indented = re.match(r"(?: {4,}|\t)", payload) is not None
        protected_indented_context = is_indented and (
            has_blockquote_container
            or in_root_indented_code
            or previous_line_blank
        )
        if protected_indented_context:
            for candidate in _PROTECTED_CONTEXT_MARKUP_RE.finditer(payload):
                candidate_offset = (
                    line_offset + len(content) - len(payload) + candidate.start()
                )
                if not any(
                    start <= candidate_offset < end
                    for start, end in raw_container_spans
                ):
                    return True
        if not has_blockquote_container:
            if is_indented and (
                in_root_indented_code or previous_line_blank
            ):
                in_root_indented_code = True
            elif content.strip():
                in_root_indented_code = False
        list_code = re.match(
            r" {0,3}(?:[-+*]|[0-9]{1,9}[.)])[ \t]{4,}(?P<code>.*)",
            payload,
        )
        if (
            list_code is not None
            and _contains_normalizable_markup(list_code.group("code"))
        ):
            return True
        previous_line_blank = not content.strip()
        line_offset += len(line)

    outside_fences: list[str] = []
    cursor = 0
    for start, end in fenced_spans:
        if cursor < start:
            outside_fences.append(body[cursor:start])
        outside_fences.append(" " * (end - start))
        cursor = end
    outside_fences.append(body[cursor:])
    unfenced = "".join(outside_fences)
    inline_code_re = re.compile(
        r"(?s)(?<!`)(?P<ticks>`+)(?!`).*?(?<!`)(?P=ticks)(?!`)"
    )
    if any(
        _contains_normalizable_markup(match.group(0))
        for match in inline_code_re.finditer(unfenced)
    ):
        return True

    # Scan inline-link destinations with balanced parentheses and quoted
    # titles instead of stopping at the first ``)``.  The latter can be part
    # of a nested destination or a quoted title, and normalizing tag-looking
    # text there would silently change the link itself.  A literal ``](``
    # that is not ultimately a valid link may cause a conservative blocker;
    # preserving bytes is preferable to guessing at Markdown grammar here.
    link_candidates = list(_PROTECTED_CONTEXT_MARKUP_RE.finditer(body))
    link_search_start = 0
    link_candidate_index = 0
    while link_candidate_index < len(link_candidates):
        opener_start = body.find("](", link_search_start)
        if opener_start < 0:
            break
        target_start = opener_start + 2
        while (
            link_candidate_index < len(link_candidates)
            and link_candidates[link_candidate_index].start() < target_start
        ):
            link_candidate_index += 1
        if link_candidate_index >= len(link_candidates):
            break
        depth = 1
        quote: str | None = None
        in_angle_destination = False
        index = target_start
        while index < len(body):
            character = body[index]
            if character == "\\":
                index += 2
                continue
            if quote is not None:
                if character == quote:
                    quote = None
                index += 1
                continue
            if in_angle_destination:
                if character == ">":
                    in_angle_destination = False
                index += 1
                continue
            if character in {'"', "'"}:
                quote = character
            elif character == "<":
                in_angle_destination = True
            elif character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    break
            index += 1
        if link_candidates[link_candidate_index].start() < index:
            return True
        if index >= len(body):
            break
        link_search_start = index + 1
    for reference_definition in re.finditer(
        r"(?im)^ {0,3}\[[^\]\r\n]+\]:[^\r\n]*"
        r"(?:\r?\n[ \t]+[^\r\n]*)*",
        body,
    ):
        if _contains_normalizable_markup(reference_definition.group(0)):
            return True

    for match in _PROTECTED_CONTEXT_MARKUP_RE.finditer(body):
        backslash_count = 0
        index = match.start() - 1
        while index >= 0 and body[index] == "\\":
            backslash_count += 1
            index -= 1
        if backslash_count % 2 == 1:
            return True
    return False


def _normalize_markup_body(
    body: str,
    *,
    bindings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    active_bindings = bindings or {}
    counts = {
        "empty_block": 0,
        "span": 0,
        "mention_date": 0,
        "table_of_contents": 0,
        "synced_block": 0,
        "synced_block_reference": 0,
        "table": 0,
        "table_blocked": 0,
        "structural_container": 0,
        "reference_binding_applied": 0,
        "reference_binding_required": 0,
        "unknown_semantic_tag": 0,
    }
    if _protected_markup_context_present(body):
        return {
            "normalized_body": body,
            "changed": False,
            "counts": counts,
            "reference_tag_names": [],
            "reference_tag_digests": [],
            "used_binding_selectors": [],
            "unknown_tag_names": [],
            "blocker_codes": ["markup_protected_context_unsupported"],
        }
    table_of_contents_line = re.compile(
        r"\A(?P<leading>(?:[ \t]*(?:\r\n|\n))*)"
        r"<unknown:table_of_contents/>"
        r"(?P<ending>\r\n|\n|\Z)"
    )
    normalized = body
    if body.count("<unknown:table_of_contents/>") == 1:
        table_of_contents_match = table_of_contents_line.match(body)
        if table_of_contents_match is not None:
            normalized = (
                table_of_contents_match.group("leading")
                + body[table_of_contents_match.end() :]
            )
            counts["table_of_contents"] = 1

    normalized, table_count, table_blockers = _normalize_gfm_tables(
        normalized
    )
    counts["table"] = table_count
    counts["table_blocked"] = len(table_blockers)

    normalized, empty_count = re.subn(
        r"(?im)^[ \t]*<\s*empty-block\s*/\s*>[ \t]*(?:\r?\n|$)",
        "",
        normalized,
    )
    counts["empty_block"] = empty_count

    mention_date_blockers: list[str] = []

    def self_closing_mention_date_replacement(
        match: re.Match[str],
    ) -> str:
        rendered = _render_self_closing_mention_date(
            match.group("attrs") or ""
        )
        if rendered is None:
            mention_date_blockers.append(
                "markup_mention_date_attributes_unsupported"
            )
            return match.group(0)
        counts["mention_date"] += 1
        return rendered

    normalized = re.sub(
        r"(?is)<\s*mention-date(?P<attrs>\s+[^<>]*?)?\s*/\s*>",
        self_closing_mention_date_replacement,
        normalized,
    )

    reference_tag_digests: list[dict[str, str | int]] = []
    used_binding_selectors: set[tuple[str, int | None]] = set()
    reference_blockers: list[str] = []
    reference_occurrence_seen: dict[str, int] = {}
    paired_unbound_reference_counts = {
        name: 0 for name in _PAIRED_REFERENCE_MARKUP_TAGS
    }

    def add_reference_blocker(code: str) -> None:
        if code not in reference_blockers:
            reference_blockers.append(code)

    paired_reference_names = "|".join(
        re.escape(name) for name in sorted(_PAIRED_REFERENCE_MARKUP_TAGS)
    )
    paired_reference_re = re.compile(
        rf"(?is)(?P<opening><\s*(?P<name>{paired_reference_names})"
        r"(?:\s+[^<>]*?)?\s*>)"
        r"(?P<inner>.*?)<\s*/\s*(?P=name)\s*>"
    )

    def selector_bindings(
        tag_sha256: str,
    ) -> dict[int | None, dict[str, Any]]:
        raw = active_bindings.get(tag_sha256)
        if not isinstance(raw, dict):
            return {}
        # Keep the small direct-test/internal-call compatibility surface. The
        # manifest loader always returns the selector-keyed representation.
        if "replacement" in raw:
            return {None: raw}
        return {
            selector: binding
            for selector, binding in raw.items()
            if (selector is None or type(selector) is int)
            and isinstance(binding, dict)
        }

    reference_occurrence_totals: dict[str, int] = {}

    def count_reference_occurrence(tag_sha256: str) -> None:
        reference_occurrence_totals[tag_sha256] = (
            reference_occurrence_totals.get(tag_sha256, 0) + 1
        )

    for candidate in paired_reference_re.finditer(normalized):
        opening = _MARKUP_TAG_RE.fullmatch(candidate.group("opening"))
        name = candidate.group("name").casefold()
        if opening is None or opening.group("self"):
            continue
        if name == "file" and _strict_markup_attributes(
            opening.group("attrs") or ""
        ) is None:
            continue
        if name == "database" and not _database_reference_attributes_supported(
            opening.group("attrs") or ""
        ):
            continue
        if candidate.group("inner").strip():
            continue
        count_reference_occurrence(
            _sha256_bytes(candidate.group(0).encode("utf-8"))
        )
    for candidate in _MARKUP_TAG_RE.finditer(normalized):
        candidate_name = candidate.group("name").casefold()
        if (
            candidate_name in _REFERENCE_MARKUP_TAGS
            and not candidate.group("closing")
            and bool(candidate.group("self"))
            and (
                candidate_name not in _UNKNOWN_CONTENT_REFERENCE_MARKUP_TAGS
                or not (candidate.group("attrs") or "").strip()
            )
        ):
            count_reference_occurrence(
                _sha256_bytes(candidate.group(0).encode("utf-8"))
            )

    blocked_reference_digests: set[str] = set()
    for tag_sha256, total in reference_occurrence_totals.items():
        selectors = selector_bindings(tag_sha256)
        if not selectors:
            continue
        if None in selectors:
            if total > 1:
                add_reference_blocker(
                    "markup_reference_binding_occurrence_required"
                )
                blocked_reference_digests.add(tag_sha256)
            continue
        explicit_indexes = {
            selector
            for selector in selectors
            if type(selector) is int
        }
        if any(index > total for index in explicit_indexes):
            add_reference_blocker(
                "markup_reference_binding_occurrence_out_of_range"
            )
            blocked_reference_digests.add(tag_sha256)
        elif total > 1 and explicit_indexes != set(range(1, total + 1)):
            add_reference_blocker(
                "markup_reference_binding_occurrence_incomplete"
            )
            blocked_reference_digests.add(tag_sha256)

    def next_reference_occurrence(tag_sha256: str) -> int:
        occurrence_index = reference_occurrence_seen.get(tag_sha256, 0) + 1
        reference_occurrence_seen[tag_sha256] = occurrence_index
        return occurrence_index

    def selected_binding(
        tag_sha256: str,
        occurrence_index: int,
    ) -> dict[str, Any] | None:
        if tag_sha256 in blocked_reference_digests:
            return None
        selectors = selector_bindings(tag_sha256)
        if not selectors:
            return None
        if None in selectors:
            return selectors[None]
        return selectors.get(occurrence_index)

    def paired_reference_replacement(match: re.Match[str]) -> str:
        name = match.group("name").casefold()
        fragment = match.group(0)
        opening = _MARKUP_TAG_RE.fullmatch(match.group("opening"))
        if opening is None or opening.group("self"):
            add_reference_blocker(
                "markup_paired_reference_self_closing_opener"
            )
            paired_unbound_reference_counts[name] += 1
            return fragment
        if name == "file" and _strict_markup_attributes(
            opening.group("attrs") or ""
        ) is None:
            add_reference_blocker("markup_file_attributes_unsupported")
            paired_unbound_reference_counts[name] += 1
            return fragment
        if name == "database" and not _database_reference_attributes_supported(
            opening.group("attrs") or ""
        ):
            add_reference_blocker("markup_database_attributes_unsupported")
            paired_unbound_reference_counts[name] += 1
            return fragment
        if match.group("inner").strip():
            add_reference_blocker(
                f"markup_{name}_inner_content_unsupported"
            )
            paired_unbound_reference_counts[name] += 1
            return fragment
        tag_sha256 = _sha256_bytes(fragment.encode("utf-8"))
        occurrence_index = next_reference_occurrence(tag_sha256)
        reference_tag_digests.append(
            {
                "tag_name": name,
                "tag_sha256": tag_sha256,
                "occurrence_index": occurrence_index,
            }
        )
        binding = selected_binding(tag_sha256, occurrence_index)
        if binding is None:
            paired_unbound_reference_counts[name] += 1
            return fragment
        allowed_binding_kinds = (
            {"zettel_reference"} if name == "database" else {"objet"}
        )
        if binding.get("binding_kind") not in allowed_binding_kinds:
            add_reference_blocker(
                "markup_reference_binding_kind_mismatch"
            )
            paired_unbound_reference_counts[name] += 1
            return fragment
        used_binding_selectors.add(
            (tag_sha256, binding.get("occurrence_index"))
        )
        counts["reference_binding_applied"] += 1
        return binding["replacement"]

    normalized = paired_reference_re.sub(
        paired_reference_replacement,
        normalized,
    )

    for _pass in range(32):
        normalized, mention_date_count = re.subn(
            r"(?is)<\s*mention-date(?:\s+[^<>]*?)?\s*>(.*?)<\s*/\s*mention-date\s*>",
            lambda match: match.group(1),
            normalized,
        )
        counts["mention_date"] += mention_date_count
        if mention_date_count == 0:
            break

    for tag_name, count_key in (
        ("synced_block_reference", "synced_block_reference"),
        ("synced_block", "synced_block"),
    ):
        tag_pattern = re.compile(
            rf"(?is)<\s*{tag_name}(?:\s+[^<>]*?)?\s*>"
            rf"(.*?)<\s*/\s*{tag_name}\s*>"
        )
        for _pass in range(32):
            normalized, wrapper_count = tag_pattern.subn(
                lambda match: match.group(1),
                normalized,
            )
            counts[count_key] += wrapper_count
            if wrapper_count == 0:
                break

    # Repeated passes handle ordinary nested spans without interpreting their
    # attributes or changing the visible inner text.
    for _pass in range(32):
        normalized, span_count = re.subn(
            r"(?is)<\s*span(?:\s+[^<>]*?)?\s*>(.*?)<\s*/\s*span\s*>",
            lambda match: match.group(1),
            normalized,
        )
        counts["span"] += span_count
        if span_count == 0:
            break

    def structural_replacement(match: re.Match[str]) -> str:
        counts["structural_container"] += 1
        return "\n\n"

    normalized = re.sub(
        r"(?is)<\s*/?\s*(?:article|column|columns|div|section|p)(?:\s+[^<>]*?)?\s*>",
        structural_replacement,
        normalized,
    )

    unknown_audio_ambiguous_digests: set[str] = set()
    for candidate in _MARKUP_TAG_RE.finditer(normalized):
        if (
            candidate.group("name").casefold() != "unknown:audio"
            or candidate.group("closing")
            or not candidate.group("self")
            or (candidate.group("attrs") or "").strip()
        ):
            continue
        tag_sha256 = _sha256_bytes(candidate.group(0).encode("utf-8"))
        if reference_occurrence_totals.get(tag_sha256, 0) <= 1:
            continue
        selectors = selector_bindings(tag_sha256)
        if (
            not selectors
            or None in selectors
            or tag_sha256 in blocked_reference_digests
        ):
            unknown_audio_ambiguous_digests.add(tag_sha256)
    if unknown_audio_ambiguous_digests:
        add_reference_blocker("markup_unknown_audio_binding_ambiguous")

    def reference_replacement(match: re.Match[str]) -> str:
        name = match.group("name").casefold()
        if name not in _REFERENCE_MARKUP_TAGS:
            return match.group(0)
        if name in _PAIRED_REFERENCE_MARKUP_TAGS and not match.group("self"):
            return match.group(0)
        if name == "database":
            add_reference_blocker("markup_database_shape_unsupported")
            return match.group(0)
        if name in _UNKNOWN_CONTENT_REFERENCE_MARKUP_TAGS and match.group(
            0
        ) != f"<{name}/>":
            add_reference_blocker(
                "markup_unknown_content_reference_shape_unsupported"
            )
            return match.group(0)
        tag_sha256 = _sha256_bytes(match.group(0).encode("utf-8"))
        occurrence_index = next_reference_occurrence(tag_sha256)
        reference_tag_digests.append(
            {
                "tag_name": _public_markup_tag_name(name),
                "tag_sha256": tag_sha256,
                "occurrence_index": occurrence_index,
            }
        )
        if (
            name == "unknown:audio"
            and tag_sha256 in unknown_audio_ambiguous_digests
            and not match.group("closing")
            and bool(match.group("self"))
            and not (match.group("attrs") or "").strip()
        ):
            return match.group(0)
        if (
            name == "unknown:audio"
            and not match.group("closing")
            and bool(match.group("self"))
            and (match.group("attrs") or "").strip()
        ):
            add_reference_blocker(
                "markup_unknown_audio_attributes_unsupported"
            )
            return match.group(0)
        binding = selected_binding(tag_sha256, occurrence_index)
        if (
            binding is None
            or match.group("closing")
            or not match.group("self")
        ):
            return match.group(0)
        allowed_binding_kinds = (
            {"zettel_edge", "zettel_reference"}
            if name == "mention-page"
            else {"objet", "zettel_reference"}
            if name in _UNKNOWN_CONTENT_REFERENCE_MARKUP_TAGS
            else {"objet"}
            if name == "unknown:audio"
            else {"external_locator", "zettel_edge", "objet"}
        )
        if (
            allowed_binding_kinds is not None
            and binding.get("binding_kind") not in allowed_binding_kinds
        ):
            add_reference_blocker(
                "markup_reference_binding_kind_mismatch"
            )
            return match.group(0)
        used_binding_selectors.add(
            (tag_sha256, binding.get("occurrence_index"))
        )
        counts["reference_binding_applied"] += 1
        return binding["replacement"]

    normalized = _MARKUP_TAG_RE.sub(reference_replacement, normalized)
    remaining = list(_MARKUP_TAG_RE.finditer(normalized))
    unknown_names: set[str] = set()
    reference_names: set[str] = set()
    remaining_paired_tag_counts = {
        name: 0 for name in _PAIRED_REFERENCE_MARKUP_TAGS
    }
    for match in remaining:
        name = match.group("name").casefold()
        if name in _MARKDOWN_COMPATIBLE_HTML_TAGS:
            continue
        if name in _PAIRED_REFERENCE_MARKUP_TAGS:
            remaining_paired_tag_counts[name] += 1
            continue
        if name in _REFERENCE_MARKUP_TAGS:
            counts["reference_binding_required"] += 1
            reference_names.add(_public_markup_tag_name(name))
            continue
        if name == "empty-block" or name == "span" or name in _STRUCTURAL_MARKUP_TAGS:
            unknown_names.add(name)
            continue
        counts["unknown_semantic_tag"] += 1
        unknown_names.add(name)

    for name in sorted(_PAIRED_REFERENCE_MARKUP_TAGS):
        paired_count = paired_unbound_reference_counts[name]
        unmatched_tag_count = max(
            0,
            remaining_paired_tag_counts[name] - (2 * paired_count),
        )
        required_count = paired_count + unmatched_tag_count
        if required_count:
            counts["reference_binding_required"] += required_count
            reference_names.add(name)

    blocker_codes: list[str] = [
        *table_blockers,
        *mention_date_blockers,
        *reference_blockers,
    ]
    if reference_names:
        blocker_codes.append("markup_reference_binding_required")
    if unknown_names:
        blocker_codes.append("unknown_semantic_markup")
    blocker_codes = archive_services.unique_preserve_order(blocker_codes)
    restore_blocked_body = bool(blocker_codes)
    return {
        "normalized_body": (
            body if restore_blocked_body else normalized
        ),
        "changed": (
            normalized != body and not restore_blocked_body
        ),
        "counts": counts,
        "reference_tag_names": sorted(reference_names),
        "reference_tag_digests": sorted(
            reference_tag_digests,
            key=lambda item: (
                item["tag_name"],
                item["tag_sha256"],
                item["occurrence_index"],
            ),
        ),
        "used_binding_selectors": sorted(
            used_binding_selectors,
            key=lambda item: (
                item[0],
                0 if item[1] is None else item[1],
            ),
        ),
        "unknown_tag_names": sorted(unknown_names),
        "blocker_codes": blocker_codes,
    }


def _markup_zettel_analysis(
    root: Path,
    path: Path,
    *,
    policy: str,
    bindings_by_zettel: (
        dict[
            str,
            dict[str, dict[int | None, dict[str, str | int | None]]],
        ]
        | None
    ) = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    try:
        before_bytes = path.read_bytes()
        text = before_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return {
            "zettel_id": None,
            "path": archive_services.archive_relative_path(path, root),
            "state": "blocked",
            "before_sha256": None,
            "after_sha256": None,
            "blocker_codes": ["markup_source_unreadable"],
            "counts": {},
        }, None
    boundary = archive_services.FRONTMATTER_RE.match(text)
    if boundary is None:
        return {
            "zettel_id": None,
            "path": archive_services.archive_relative_path(path, root),
            "state": "blocked",
            "before_sha256": _sha256_bytes(before_bytes),
            "after_sha256": None,
            "blocker_codes": ["markup_frontmatter_boundary_invalid"],
            "counts": {},
        }, None
    try:
        frontmatter = archive_services.load_yaml(boundary.group(1))
    except Exception:
        frontmatter = None
    zettel_id = (
        str(frontmatter.get("id") or "").strip()
        if isinstance(frontmatter, dict)
        else None
    )
    body = text[boundary.end() :]
    relative_path = archive_services.archive_relative_path(path, root)
    zettel_bindings = (bindings_by_zettel or {}).get(str(zettel_id), {})
    path_bound_bindings = {
        tag_sha256: {
            occurrence_index: binding
            for occurrence_index, binding in selector_bindings.items()
            if binding.get("source_relative_path") == relative_path
        }
        for tag_sha256, selector_bindings in zettel_bindings.items()
    }
    path_bound_bindings = {
        tag_sha256: selector_bindings
        for tag_sha256, selector_bindings in path_bound_bindings.items()
        if selector_bindings
    }
    normalized = _normalize_markup_body(
        body,
        bindings=path_bound_bindings,
    )
    candidate_count = sum(
        int(value) for value in normalized["counts"].values()
    )
    before_sha256 = _sha256_bytes(before_bytes)
    if policy == "preserve":
        after_bytes = before_bytes
        blocker_codes: list[str] = []
        state = "preserved" if candidate_count else "no_change"
    else:
        after_text = text[: boundary.end()] + normalized["normalized_body"]
        after_bytes = after_text.encode("utf-8")
        blocker_codes = list(normalized["blocker_codes"])
        state = (
            "blocked"
            if blocker_codes
            else "ready"
            if after_bytes != before_bytes
            else "no_change"
        )
    after_sha256 = _sha256_bytes(after_bytes)
    public = {
        "zettel_id": zettel_id,
        "path": relative_path,
        "state": state,
        "before_sha256": before_sha256,
        "after_sha256": after_sha256,
        "blocker_codes": blocker_codes,
        "counts": normalized["counts"],
        "reference_tag_names": normalized["reference_tag_names"],
        "reference_tag_digests": normalized["reference_tag_digests"],
        "unknown_tag_names": normalized["unknown_tag_names"],
    }
    private = {
        "path": path,
        "before_bytes": before_bytes,
        "after_bytes": after_bytes,
        "before_sha256": before_sha256,
        "after_sha256": after_sha256,
        "relative": public["path"],
        "zettel_id": zettel_id,
        "state": state,
        "used_binding_selectors": normalized["used_binding_selectors"],
    }
    return public, private


def _markup_plan_core(
    archive_root: Path | str,
    *,
    policy: str,
    max_items: int,
    max_changes: int,
    binding_manifest: Path | str | None,
    only_ready: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = archive_services.require_existing_archive_root(archive_root)
    archive_id = archive_services.read_archive_id(root)
    normalized_policy = str(policy or "").strip().lower()
    blockers: list[str] = []
    if normalized_policy not in MARKUP_NORMALIZATION_POLICIES:
        blockers.append("markup_policy_invalid")
    selection_mode = "ready_only" if only_ready else "strict"
    if only_ready and normalized_policy != "normalize":
        blockers.append("markup_only_ready_requires_normalize")
    try:
        item_limit = int(max_items)
        change_limit = int(max_changes)
    except (TypeError, ValueError):
        item_limit = 0
        change_limit = 0
        blockers.append("markup_bounds_invalid")
    if not 1 <= item_limit <= MARKUP_NORMALIZATION_MAX_ITEMS:
        blockers.append("markup_max_items_invalid")
    if not 1 <= change_limit <= MARKUP_NORMALIZATION_MAX_CHANGES:
        blockers.append("markup_max_changes_invalid")

    bindings, binding_manifest_sha256, binding_blockers = (
        _markup_reference_bindings(
            root,
            binding_manifest=binding_manifest,
        )
    )
    blockers.extend(binding_blockers)
    all_paths = list(archive_services.iter_zettel_paths(root))
    if len(all_paths) > item_limit > 0:
        blockers.append("markup_item_bound_exceeded")
    public_items: list[dict[str, Any]] = []
    private_items: list[dict[str, Any]] = []
    used_binding_keys: set[tuple[str, str, int | None]] = set()
    analyzed_zettel_id_counts: dict[str, int] = {}
    if not blockers:
        for path in all_paths:
            public, private = _markup_zettel_analysis(
                root,
                path,
                policy=normalized_policy,
                bindings_by_zettel=bindings,
            )
            analyzed_zettel_id = public.get("zettel_id")
            if isinstance(analyzed_zettel_id, str):
                analyzed_zettel_id_counts[analyzed_zettel_id] = (
                    analyzed_zettel_id_counts.get(analyzed_zettel_id, 0)
                    + 1
                )
            if (
                sum(int(value) for value in public.get("counts", {}).values())
                or public["blocker_codes"]
            ):
                public_items.append(public)
            if private is not None:
                used_binding_keys.update(
                    (
                        str(private["zettel_id"]),
                        tag_sha256,
                        occurrence_index,
                    )
                    for tag_sha256, occurrence_index in private[
                        "used_binding_selectors"
                    ]
                )
            if private is not None and private["state"] == "ready":
                private_items.append(private)
        configured_binding_keys = {
            (zettel_id, tag_sha256, occurrence_index)
            for zettel_id, zettel_bindings in bindings.items()
            for tag_sha256, selector_bindings in zettel_bindings.items()
            for occurrence_index in selector_bindings
        }
        if any(
            analyzed_zettel_id_counts.get(zettel_id, 0) != 1
            for zettel_id in bindings
        ):
            blockers.append("markup_binding_source_unverified")
        if configured_binding_keys - used_binding_keys:
            blockers.append("markup_binding_unused")
        if len(private_items) > change_limit:
            blockers.append("markup_change_bound_exceeded")
        if not only_ready:
            for item in public_items:
                blockers.extend(item["blocker_codes"])
        elif not private_items:
            blockers.append("markup_no_ready_changes")

    plan_items = [
        {
            "zettel_id": item["zettel_id"],
            "path": item["path"],
            "state": item["state"],
            "before_sha256": item["before_sha256"],
            "after_sha256": item["after_sha256"],
            "blocker_codes": item["blocker_codes"],
            "counts": item["counts"],
            "reference_tag_names": item.get("reference_tag_names", []),
            "reference_tag_digests": item.get(
                "reference_tag_digests",
                [],
            ),
            "unknown_tag_names": item.get("unknown_tag_names", []),
        }
        for item in public_items
    ]
    plan_document = {
        "schema": MARKUP_NORMALIZATION_PLAN_SCHEMA,
        "archive_id": archive_id,
        "policy": normalized_policy,
        "selection_mode": selection_mode,
        "max_items": item_limit,
        "max_changes": change_limit,
        "binding_manifest_sha256": binding_manifest_sha256,
        "items": plan_items,
    }
    plan_sha256 = _sha256_bytes(_canonical_json_bytes(plan_document))
    aggregate_blockers = archive_services.unique_preserve_order(blockers)
    deferred_blocker_codes = archive_services.unique_preserve_order(
        code
        for item in public_items
        if item["state"] == "blocked"
        for code in item["blocker_codes"]
    )
    blocked_zettel_count = sum(
        1 for item in public_items if item["state"] == "blocked"
    )
    summary = {
        "policy": (
            normalized_policy
            if normalized_policy in MARKUP_NORMALIZATION_POLICIES
            else None
        ),
        "selection_mode": selection_mode,
        "scanned_zettel_count": len(all_paths),
        "candidate_zettel_count": len(public_items),
        "ready_change_count": len(private_items),
        "blocked_zettel_count": blocked_zettel_count,
        "deferred_blocker_codes": (
            deferred_blocker_codes if only_ready else []
        ),
        "preserved_zettel_count": sum(
            1 for item in public_items if item["state"] == "preserved"
        ),
        "reference_binding_count": len(used_binding_keys),
        "binding_manifest_sha256": binding_manifest_sha256,
        "plan_sha256": plan_sha256 if not aggregate_blockers else None,
    }
    result = {
        "ok": not aggregate_blockers,
        "state": (
            "blocked"
            if aggregate_blockers
            else "partial_ready"
            if only_ready and blocked_zettel_count
            else "ready"
        ),
        "dry_run": True,
        "lifecycle_action": "markup_normalization_plan",
        "archive_id": archive_id,
        "summary": summary,
        "items": plan_items,
        "style_guide": markup_style_guide(),
        "blockers": aggregate_blockers,
        "warnings": (
            ([
                "Preserve policy records the inventory and intentionally leaves source markup unchanged."
            ]
            if normalized_policy == "preserve"
            else [])
            + (
                [
                    "Ready-only selection leaves blocked zets byte-identical; review deferred blocker codes separately."
                ]
                if only_ready and blocked_zettel_count and not aggregate_blockers
                else []
            )
        ),
        "would_change": (
            [item["relative"] for item in private_items]
            if not aggregate_blockers
            else []
        ),
        "privacy_guards": {
            "zettel_titles_echoed": False,
            "zettel_bodies_echoed": False,
            "tag_attributes_echoed": False,
            "local_absolute_paths_echoed": False,
            "source_bytes_hashed": True,
            "writes": False,
        },
    }
    private = {
        "root": root,
        "plan_document": plan_document,
        "plan_sha256": plan_sha256,
        "items": private_items,
        "policy": normalized_policy,
        "binding_manifest_sha256": binding_manifest_sha256,
        "selection_mode": selection_mode,
    }
    return result, private


def markup_normalization_plan(
    archive_root: Path | str,
    *,
    policy: str = "normalize",
    max_items: int = MARKUP_NORMALIZATION_MAX_ITEMS,
    max_changes: int = MARKUP_NORMALIZATION_MAX_CHANGES,
    binding_manifest: Path | str | None = None,
    only_ready: bool = False,
) -> dict[str, Any]:
    result, _private = _markup_plan_core(
        archive_root,
        policy=policy,
        max_items=max_items,
        max_changes=max_changes,
        binding_manifest=binding_manifest,
        only_ready=only_ready,
    )
    return result


def markup_normalization_apply(
    archive_root: Path | str,
    *,
    policy: str,
    max_items: int,
    max_changes: int,
    binding_manifest: Path | str | None = None,
    only_ready: bool = False,
    expected_plan_sha256: str | None,
    reviewed_by: str | None,
) -> dict[str, Any]:
    result, private = _markup_plan_core(
        archive_root,
        policy=policy,
        max_items=max_items,
        max_changes=max_changes,
        binding_manifest=binding_manifest,
        only_ready=only_ready,
    )
    blockers = list(result["blockers"])
    expected = str(expected_plan_sha256 or "").strip().lower()
    reviewer = archive_services.safe_project_intake_actor_id(reviewed_by)
    if private["policy"] != "normalize":
        blockers.append("markup_preserve_policy_has_no_write")
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        blockers.append("markup_expected_plan_sha256_invalid")
    elif expected != private["plan_sha256"]:
        blockers.append("markup_plan_changed")
    if reviewer is None:
        blockers.append("markup_reviewer_invalid")
    if blockers:
        return {
            **result,
            "ok": False,
            "state": "blocked",
            "dry_run": False,
            "approved": False,
            "lifecycle_action": "markup_normalization",
            "blockers": archive_services.unique_preserve_order(blockers),
            "would_change": [],
            "files_written": [],
        }

    root: Path = private["root"]
    transaction_relative = (
        f"{MARKUP_NORMALIZATION_SCRATCH_DIR}/transactions/{expected}"
    )
    snapshot_root_relative = f"{transaction_relative}/snapshots"
    journal_relative = f"{transaction_relative}/journal.json"
    journal_path = archive_services.archive_internal_path(root, journal_relative)
    receipt_relative = (
        f"{MARKUP_NORMALIZATION_RECEIPTS_DIR}/{expected}.json"
    )
    receipt_path = archive_services.archive_internal_path(root, receipt_relative)
    with _MarkupMutationLock(root):
        fresh, fresh_private = _markup_plan_core(
            root,
            policy=policy,
            max_items=max_items,
            max_changes=max_changes,
            binding_manifest=binding_manifest,
            only_ready=only_ready,
        )
        if not fresh["ok"] or fresh_private["plan_sha256"] != expected:
            return {
                **fresh,
                "ok": False,
                "state": "blocked",
                "dry_run": False,
                "approved": False,
                "lifecycle_action": "markup_normalization",
                "blockers": archive_services.unique_preserve_order(
                    [*fresh["blockers"], "markup_plan_changed"]
                ),
                "would_change": [],
                "files_written": [],
            }
        if receipt_path.exists():
            return {
                **fresh,
                "ok": True,
                "state": "already_applied",
                "dry_run": False,
                "approved": True,
                "lifecycle_action": "markup_normalization",
                "summary": {
                    **fresh["summary"],
                    "receipt_path": receipt_relative,
                },
                "blockers": [],
                "would_change": [],
                "files_written": [],
            }

        timestamp = _now()
        journal_items: list[dict[str, Any]] = []
        for index, item in enumerate(fresh_private["items"]):
            before_snapshot_relative = (
                f"{snapshot_root_relative}/{index:06d}.before."
                f"{item['before_sha256']}.bin"
            )
            after_snapshot_relative = (
                f"{snapshot_root_relative}/{index:06d}.after."
                f"{item['after_sha256']}.bin"
            )
            before_snapshot_path = archive_services.archive_internal_path(
                root,
                before_snapshot_relative,
            )
            after_snapshot_path = archive_services.archive_internal_path(
                root,
                after_snapshot_relative,
            )
            if not before_snapshot_path.exists():
                archive_services._write_bytes_create_if_absent(
                    before_snapshot_path,
                    item["before_bytes"],
                )
            if not after_snapshot_path.exists():
                archive_services._write_bytes_create_if_absent(
                    after_snapshot_path,
                    item["after_bytes"],
                )
            journal_items.append(
                {
                    "index": index,
                    "zettel_id": item["zettel_id"],
                    "path": item["relative"],
                    "before_sha256": item["before_sha256"],
                    "after_sha256": item["after_sha256"],
                    "snapshot_path": before_snapshot_relative,
                    "before_snapshot_path": before_snapshot_relative,
                    "after_snapshot_path": after_snapshot_relative,
                }
            )
        journal = {
            "schema": MARKUP_NORMALIZATION_JOURNAL_SCHEMA,
            "archive_id": archive_services.read_archive_id(root),
            "plan_sha256": expected,
            "policy": policy,
            "binding_manifest_sha256": fresh_private[
                "binding_manifest_sha256"
            ],
            "state": "prepared",
            "applied_count": 0,
            "item_count": len(journal_items),
            "items": journal_items,
            "reviewed_by": reviewer,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        archive_services.write_bytes_atomic(
            journal_path,
            _canonical_json_bytes(journal),
        )
        applied_count = 0
        for item in fresh_private["items"]:
            current = item["path"].read_bytes()
            if _sha256_bytes(current) != item["before_sha256"]:
                journal["state"] = "interrupted"
                journal["updated_at"] = _now()
                archive_services.write_bytes_atomic(
                    journal_path,
                    _canonical_json_bytes(journal),
                )
                return {
                    **fresh,
                    "ok": False,
                    "state": "partial",
                    "dry_run": False,
                    "approved": True,
                    "lifecycle_action": "markup_normalization",
                    "summary": {
                        **fresh["summary"],
                        "applied_count": applied_count,
                        "journal_path": journal_relative,
                        "recovery_required": True,
                    },
                    "blockers": ["markup_source_changed_during_apply"],
                    "would_change": [],
                    "files_written": [
                        entry["relative"]
                        for entry in fresh_private["items"][:applied_count]
                    ],
                }
            archive_services.write_bytes_atomic(
                item["path"],
                item["after_bytes"],
            )
            applied_count += 1
            journal["applied_count"] = applied_count
            journal["state"] = (
                "applied" if applied_count == len(journal_items) else "applying"
            )
            journal["updated_at"] = _now()
            archive_services.write_bytes_atomic(
                journal_path,
                _canonical_json_bytes(journal),
            )

        receipt = {
            "schema": MARKUP_NORMALIZATION_RECEIPT_SCHEMA,
            "archive_id": archive_services.read_archive_id(root),
            "plan_sha256": expected,
            "policy": policy,
            "binding_manifest_sha256": fresh_private[
                "binding_manifest_sha256"
            ],
            "journal_path": journal_relative,
            "reviewed_by": reviewer,
            "created_at": _now(),
            "item_count": len(journal_items),
            "items": journal_items,
            "source_bytes_snapshotted": True,
            "exact_byte_revert_supported": True,
        }
        archive_services._write_bytes_create_if_absent(
            receipt_path,
            _canonical_json_bytes(receipt),
        )
        journal["state"] = "committed"
        journal["receipt_path"] = receipt_relative
        journal["updated_at"] = _now()
        archive_services.write_bytes_atomic(
            journal_path,
            _canonical_json_bytes(journal),
        )

    return {
        **fresh,
        "ok": True,
        "state": "written",
        "dry_run": False,
        "approved": True,
        "lifecycle_action": "markup_normalization",
        "summary": {
            **fresh["summary"],
            "applied_count": len(fresh_private["items"]),
            "journal_path": journal_relative,
            "receipt_path": receipt_relative,
            "recovery_required": False,
        },
        "blockers": [],
        "would_change": [],
        "files_written": [
            *[item["relative"] for item in fresh_private["items"]],
            receipt_relative,
        ],
        "privacy_guards": {
            **fresh["privacy_guards"],
            "writes": True,
        },
    }


def _markup_revert_plan_core(
    archive_root: Path | str,
    *,
    receipt: Path | str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = archive_services.require_existing_archive_root(archive_root)
    archive_id = archive_services.read_archive_id(root)
    receipt_path, path_error = _resolve_json_input(root, receipt)
    blockers: list[str] = []
    receipt_doc: dict[str, Any] | None = None
    receipt_bytes: bytes | None = None
    if path_error or receipt_path is None:
        blockers.append("markup_receipt_path_invalid")
    else:
        try:
            receipt_bytes = receipt_path.read_bytes()
            loaded = json.loads(receipt_bytes.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            loaded = None
        if (
            not isinstance(loaded, dict)
            or loaded.get("schema") != MARKUP_NORMALIZATION_RECEIPT_SCHEMA
            or loaded.get("archive_id") != archive_id
            or not isinstance(loaded.get("items"), list)
        ):
            blockers.append("markup_receipt_invalid")
        else:
            receipt_doc = loaded

    public_items: list[dict[str, Any]] = []
    private_items: list[dict[str, Any]] = []
    if receipt_doc is not None:
        for index, item in enumerate(receipt_doc["items"]):
            codes: list[str] = []
            if not isinstance(item, dict):
                blockers.append("markup_receipt_invalid")
                continue
            try:
                target = archive_services.archive_internal_path(
                    root,
                    str(item.get("path") or ""),
                )
                snapshot = archive_services.archive_internal_path(
                    root,
                    str(item.get("snapshot_path") or ""),
                )
            except archive_services.ArchiveServiceError:
                blockers.append("markup_receipt_invalid")
                continue
            try:
                current_bytes = target.read_bytes()
                snapshot_bytes = snapshot.read_bytes()
            except OSError:
                codes.append("markup_revert_material_missing")
                current_bytes = b""
                snapshot_bytes = b""
            before_sha256 = str(item.get("before_sha256") or "")
            after_sha256 = str(item.get("after_sha256") or "")
            current_sha256 = _sha256_bytes(current_bytes)
            snapshot_sha256 = _sha256_bytes(snapshot_bytes)
            if snapshot_sha256 != before_sha256:
                codes.append("markup_snapshot_mismatch")
            if current_sha256 == after_sha256:
                state = "ready"
            elif current_sha256 == before_sha256:
                state = "already_reverted"
            else:
                state = "blocked"
                codes.append("markup_current_bytes_diverged")
            blockers.extend(codes)
            public_items.append(
                {
                    "index": index,
                    "zettel_id": item.get("zettel_id"),
                    "path": item.get("path"),
                    "state": state,
                    "current_sha256": current_sha256,
                    "before_sha256": before_sha256,
                    "after_sha256": after_sha256,
                    "blocker_codes": codes,
                }
            )
            if not codes and state == "ready":
                private_items.append(
                    {
                        "path": target,
                        "relative": item.get("path"),
                        "snapshot_bytes": snapshot_bytes,
                        "before_sha256": before_sha256,
                        "after_sha256": after_sha256,
                    }
                )

    binding = {
        "schema": "wom-kit/markup-normalization-revert-plan-binding/v0.1",
        "archive_id": archive_id,
        "source_receipt_sha256": (
            _sha256_bytes(receipt_bytes)
            if receipt_bytes is not None
            else None
        ),
        "items": [
            {
                "path": item["path"],
                "state": item["state"],
                "current_sha256": item["current_sha256"],
                "before_sha256": item["before_sha256"],
                "after_sha256": item["after_sha256"],
            }
            for item in public_items
        ],
    }
    plan_sha256 = _sha256_bytes(_canonical_json_bytes(binding))
    aggregate = archive_services.unique_preserve_order(blockers)
    result = {
        "ok": not aggregate,
        "state": "ready" if not aggregate else "blocked",
        "dry_run": True,
        "lifecycle_action": "markup_normalization_revert_plan",
        "archive_id": archive_id,
        "summary": {
            "item_count": len(public_items),
            "ready_revert_count": len(private_items),
            "already_reverted_count": sum(
                1
                for item in public_items
                if item["state"] == "already_reverted"
            ),
            "plan_sha256": plan_sha256 if not aggregate else None,
            "exact_byte_restore": True,
        },
        "items": public_items,
        "blockers": aggregate,
        "warnings": [],
        "would_change": (
            [str(item["relative"]) for item in private_items]
            if not aggregate
            else []
        ),
        "privacy_guards": {
            "zettel_titles_echoed": False,
            "zettel_bodies_echoed": False,
            "snapshot_bytes_echoed": False,
            "local_absolute_paths_echoed": False,
            "writes": False,
        },
    }
    private = {
        "root": root,
        "plan_sha256": plan_sha256,
        "receipt_doc": receipt_doc,
        "receipt_bytes": receipt_bytes,
        "items": private_items,
    }
    return result, private


def markup_normalization_revert_plan(
    archive_root: Path | str,
    *,
    receipt: Path | str,
) -> dict[str, Any]:
    result, _private = _markup_revert_plan_core(
        archive_root,
        receipt=receipt,
    )
    return result


def markup_normalization_revert(
    archive_root: Path | str,
    *,
    receipt: Path | str,
    expected_plan_sha256: str | None,
    reviewed_by: str | None,
) -> dict[str, Any]:
    result, private = _markup_revert_plan_core(
        archive_root,
        receipt=receipt,
    )
    blockers = list(result["blockers"])
    expected = str(expected_plan_sha256 or "").strip().lower()
    reviewer = archive_services.safe_project_intake_actor_id(reviewed_by)
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        blockers.append("markup_revert_expected_plan_sha256_invalid")
    elif expected != private["plan_sha256"]:
        blockers.append("markup_revert_plan_changed")
    if reviewer is None:
        blockers.append("markup_revert_reviewer_invalid")
    if blockers:
        return {
            **result,
            "ok": False,
            "state": "blocked",
            "dry_run": False,
            "approved": False,
            "lifecycle_action": "markup_normalization_revert",
            "blockers": archive_services.unique_preserve_order(blockers),
            "would_change": [],
            "files_written": [],
        }
    root: Path = private["root"]
    with _MarkupMutationLock(root):
        fresh, fresh_private = _markup_revert_plan_core(
            root,
            receipt=receipt,
        )
        if not fresh["ok"] or fresh_private["plan_sha256"] != expected:
            return {
                **fresh,
                "ok": False,
                "state": "blocked",
                "dry_run": False,
                "approved": False,
                "lifecycle_action": "markup_normalization_revert",
                "blockers": archive_services.unique_preserve_order(
                    [*fresh["blockers"], "markup_revert_plan_changed"]
                ),
                "would_change": [],
                "files_written": [],
            }
        for item in fresh_private["items"]:
            archive_services.write_bytes_atomic(
                item["path"],
                item["snapshot_bytes"],
            )
        timestamp = _now()
        source_receipt_sha256 = _sha256_bytes(
            fresh_private["receipt_bytes"] or b""
        )
        revert_receipt_relative = (
            f"{MARKUP_NORMALIZATION_RECEIPTS_DIR}/reverts/"
            f"{source_receipt_sha256}.{expected}.json"
        )
        revert_receipt_path = archive_services.archive_internal_path(
            root,
            revert_receipt_relative,
        )
        revert_receipt = {
            "schema": MARKUP_NORMALIZATION_REVERT_RECEIPT_SCHEMA,
            "archive_id": archive_services.read_archive_id(root),
            "source_receipt_sha256": source_receipt_sha256,
            "revert_plan_sha256": expected,
            "reviewed_by": reviewer,
            "created_at": timestamp,
            "item_count": len(fresh_private["items"]),
            "exact_byte_restore": True,
            "items": [
                {
                    "path": item["relative"],
                    "restored_sha256": item["before_sha256"],
                }
                for item in fresh_private["items"]
            ],
        }
        if not revert_receipt_path.exists():
            archive_services._write_bytes_create_if_absent(
                revert_receipt_path,
                _canonical_json_bytes(revert_receipt),
            )

    return {
        **fresh,
        "ok": True,
        "state": "reverted",
        "dry_run": False,
        "approved": True,
        "lifecycle_action": "markup_normalization_revert",
        "summary": {
            **fresh["summary"],
            "reverted_count": len(fresh_private["items"]),
            "receipt_path": revert_receipt_relative,
        },
        "blockers": [],
        "would_change": [],
        "files_written": [
            *[str(item["relative"]) for item in fresh_private["items"]],
            revert_receipt_relative,
        ],
        "privacy_guards": {
            **fresh["privacy_guards"],
            "writes": True,
        },
    }


def _markup_recovery_plan_core(
    archive_root: Path | str,
    *,
    journal: Path | str,
    mode: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = archive_services.require_existing_archive_root(archive_root)
    archive_id = archive_services.read_archive_id(root)
    normalized_mode = str(mode or "").strip().lower()
    blockers: list[str] = []
    if normalized_mode not in MARKUP_NORMALIZATION_RECOVERY_MODES:
        blockers.append("markup_recovery_mode_invalid")

    journal_path, path_error = _resolve_json_input(root, journal)
    journal_doc: dict[str, Any] | None = None
    journal_bytes: bytes | None = None
    journal_relative: str | None = None
    if path_error or journal_path is None:
        blockers.append("markup_recovery_journal_path_invalid")
    else:
        try:
            journal_path.resolve().relative_to(root.resolve())
            journal_relative = archive_services.archive_relative_path(
                journal_path,
                root,
            )
            journal_bytes = journal_path.read_bytes()
            loaded = json.loads(journal_bytes.decode("utf-8"))
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValueError,
        ):
            loaded = None
        if (
            not isinstance(loaded, dict)
            or loaded.get("schema") != MARKUP_NORMALIZATION_JOURNAL_SCHEMA
            or loaded.get("archive_id") != archive_id
            or not isinstance(loaded.get("items"), list)
            or not re.fullmatch(
                r"[0-9a-f]{64}",
                str(loaded.get("plan_sha256") or ""),
            )
        ):
            blockers.append("markup_recovery_journal_invalid")
        else:
            journal_doc = loaded

    public_items: list[dict[str, Any]] = []
    private_items: list[dict[str, Any]] = []
    terminal_state: str | None = None
    if journal_doc is not None:
        journal_state = str(journal_doc.get("state") or "")
        if journal_state in {"committed", "rolled_back"}:
            terminal_state = journal_state
        elif journal_state not in {
            "prepared",
            "applying",
            "applied",
            "interrupted",
        }:
            blockers.append("markup_recovery_journal_state_invalid")

        for index, item in enumerate(journal_doc["items"]):
            codes: list[str] = []
            if not isinstance(item, dict):
                blockers.append("markup_recovery_journal_invalid")
                continue
            before_sha256 = str(item.get("before_sha256") or "")
            after_sha256 = str(item.get("after_sha256") or "")
            if (
                not re.fullmatch(r"[0-9a-f]{64}", before_sha256)
                or not re.fullmatch(r"[0-9a-f]{64}", after_sha256)
            ):
                blockers.append("markup_recovery_journal_invalid")
                continue
            before_relative = str(
                item.get("before_snapshot_path")
                or item.get("snapshot_path")
                or ""
            )
            after_relative = str(item.get("after_snapshot_path") or "")
            try:
                target = archive_services.archive_internal_path(
                    root,
                    str(item.get("path") or ""),
                )
                before_snapshot = archive_services.archive_internal_path(
                    root,
                    before_relative,
                )
                after_snapshot = (
                    archive_services.archive_internal_path(
                        root,
                        after_relative,
                    )
                    if after_relative
                    else None
                )
                current_bytes = target.read_bytes()
                before_bytes = before_snapshot.read_bytes()
                after_bytes = (
                    after_snapshot.read_bytes()
                    if after_snapshot is not None
                    else None
                )
            except (archive_services.ArchiveServiceError, OSError):
                codes.append("markup_recovery_material_missing")
                current_bytes = b""
                before_bytes = b""
                after_bytes = None
                target = root
            current_sha256 = _sha256_bytes(current_bytes)
            if _sha256_bytes(before_bytes) != before_sha256:
                codes.append("markup_recovery_before_snapshot_mismatch")
            if normalized_mode == "resume":
                if (
                    after_bytes is None
                    or _sha256_bytes(after_bytes) != after_sha256
                ):
                    codes.append("markup_recovery_after_snapshot_mismatch")
            if current_sha256 == before_sha256:
                current_state = "before"
            elif current_sha256 == after_sha256:
                current_state = "after"
            else:
                current_state = "diverged"
                codes.append("markup_recovery_current_bytes_diverged")
            desired_state = (
                "after" if normalized_mode == "resume" else "before"
            )
            item_state = (
                "needs_change"
                if current_state != desired_state
                else "already_desired"
            )
            blockers.extend(codes)
            public_items.append(
                {
                    "index": index,
                    "zettel_id": item.get("zettel_id"),
                    "path": item.get("path"),
                    "current_state": current_state,
                    "desired_state": desired_state,
                    "state": item_state,
                    "current_sha256": current_sha256,
                    "before_sha256": before_sha256,
                    "after_sha256": after_sha256,
                    "blocker_codes": codes,
                }
            )
            if not codes and item_state == "needs_change":
                private_items.append(
                    {
                        "path": target,
                        "relative": item.get("path"),
                        "before_bytes": before_bytes,
                        "after_bytes": after_bytes,
                        "before_sha256": before_sha256,
                        "after_sha256": after_sha256,
                    }
                )

    binding = {
        "schema": "wom-kit/markup-normalization-recovery-plan-binding/v0.1",
        "archive_id": archive_id,
        "journal_sha256": (
            _sha256_bytes(journal_bytes)
            if journal_bytes is not None
            else None
        ),
        "mode": (
            normalized_mode
            if normalized_mode in MARKUP_NORMALIZATION_RECOVERY_MODES
            else None
        ),
        "terminal_state": terminal_state,
        "items": [
            {
                "path": item["path"],
                "current_sha256": item["current_sha256"],
                "before_sha256": item["before_sha256"],
                "after_sha256": item["after_sha256"],
                "desired_state": item["desired_state"],
            }
            for item in public_items
        ],
    }
    plan_sha256 = _sha256_bytes(_canonical_json_bytes(binding))
    aggregate = archive_services.unique_preserve_order(blockers)
    result = {
        "ok": not aggregate,
        "state": (
            "already_terminal"
            if terminal_state is not None and not aggregate
            else "ready"
            if not aggregate
            else "blocked"
        ),
        "dry_run": True,
        "lifecycle_action": "markup_normalization_recovery_plan",
        "archive_id": archive_id,
        "summary": {
            "mode": (
                normalized_mode
                if normalized_mode in MARKUP_NORMALIZATION_RECOVERY_MODES
                else None
            ),
            "journal_path": journal_relative,
            "journal_state": (
                journal_doc.get("state")
                if journal_doc is not None
                else None
            ),
            "item_count": len(public_items),
            "change_count": len(private_items),
            "already_desired_count": sum(
                1
                for item in public_items
                if item["state"] == "already_desired"
            ),
            "plan_sha256": plan_sha256 if not aggregate else None,
            "exact_byte_recovery": True,
        },
        "items": public_items,
        "blockers": aggregate,
        "warnings": [],
        "would_change": (
            [str(item["relative"]) for item in private_items]
            if not aggregate and terminal_state is None
            else []
        ),
        "privacy_guards": {
            "zettel_titles_echoed": False,
            "zettel_bodies_echoed": False,
            "snapshot_bytes_echoed": False,
            "local_absolute_paths_echoed": False,
            "writes": False,
        },
    }
    private = {
        "root": root,
        "journal_path": journal_path,
        "journal_relative": journal_relative,
        "journal_doc": journal_doc,
        "journal_bytes": journal_bytes,
        "plan_sha256": plan_sha256,
        "mode": normalized_mode,
        "terminal_state": terminal_state,
        "items": private_items,
    }
    return result, private


def markup_normalization_recovery_plan(
    archive_root: Path | str,
    *,
    journal: Path | str,
    mode: str,
) -> dict[str, Any]:
    result, _private = _markup_recovery_plan_core(
        archive_root,
        journal=journal,
        mode=mode,
    )
    return result


def markup_normalization_recover(
    archive_root: Path | str,
    *,
    journal: Path | str,
    mode: str,
    expected_plan_sha256: str | None,
    reviewed_by: str | None,
) -> dict[str, Any]:
    result, private = _markup_recovery_plan_core(
        archive_root,
        journal=journal,
        mode=mode,
    )
    blockers = list(result["blockers"])
    expected = str(expected_plan_sha256 or "").strip().lower()
    reviewer = archive_services.safe_project_intake_actor_id(reviewed_by)
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        blockers.append("markup_recovery_expected_plan_sha256_invalid")
    elif expected != private["plan_sha256"]:
        blockers.append("markup_recovery_plan_changed")
    if reviewer is None:
        blockers.append("markup_recovery_reviewer_invalid")
    if blockers:
        return {
            **result,
            "ok": False,
            "state": "blocked",
            "dry_run": False,
            "approved": False,
            "lifecycle_action": "markup_normalization_recovery",
            "blockers": archive_services.unique_preserve_order(blockers),
            "would_change": [],
            "files_written": [],
        }
    if private["terminal_state"] is not None:
        return {
            **result,
            "ok": True,
            "state": "already_terminal",
            "dry_run": False,
            "approved": True,
            "lifecycle_action": "markup_normalization_recovery",
            "blockers": [],
            "would_change": [],
            "files_written": [],
        }

    root: Path = private["root"]
    with _MarkupMutationLock(root):
        fresh, fresh_private = _markup_recovery_plan_core(
            root,
            journal=journal,
            mode=mode,
        )
        if (
            not fresh["ok"]
            or fresh_private["plan_sha256"] != expected
            or fresh_private["terminal_state"] is not None
        ):
            return {
                **fresh,
                "ok": False,
                "state": "blocked",
                "dry_run": False,
                "approved": False,
                "lifecycle_action": "markup_normalization_recovery",
                "blockers": archive_services.unique_preserve_order(
                    [*fresh["blockers"], "markup_recovery_plan_changed"]
                ),
                "would_change": [],
                "files_written": [],
            }
        for item in fresh_private["items"]:
            desired_bytes = (
                item["after_bytes"]
                if fresh_private["mode"] == "resume"
                else item["before_bytes"]
            )
            assert desired_bytes is not None
            archive_services.write_bytes_atomic(
                item["path"],
                desired_bytes,
            )

        timestamp = _now()
        journal_doc = dict(fresh_private["journal_doc"])
        source_journal_sha256 = _sha256_bytes(
            fresh_private["journal_bytes"] or b""
        )
        recovery_receipt_relative = (
            f"{MARKUP_NORMALIZATION_RECEIPTS_DIR}/recoveries/"
            f"{source_journal_sha256}.{fresh_private['mode']}."
            f"{expected}.json"
        )
        recovery_receipt_path = archive_services.archive_internal_path(
            root,
            recovery_receipt_relative,
        )
        recovery_receipt = {
            "schema": MARKUP_NORMALIZATION_RECOVERY_RECEIPT_SCHEMA,
            "archive_id": archive_services.read_archive_id(root),
            "source_journal_sha256": source_journal_sha256,
            "source_plan_sha256": journal_doc["plan_sha256"],
            "recovery_plan_sha256": expected,
            "mode": fresh_private["mode"],
            "reviewed_by": reviewer,
            "created_at": timestamp,
            "item_count": len(journal_doc["items"]),
            "changed_count": len(fresh_private["items"]),
            "exact_byte_recovery": True,
            "items": [
                {
                    "path": item["relative"],
                    "restored_sha256": (
                        item["after_sha256"]
                        if fresh_private["mode"] == "resume"
                        else item["before_sha256"]
                    ),
                }
                for item in fresh_private["items"]
            ],
        }
        archive_services._write_bytes_create_if_absent(
            recovery_receipt_path,
            _canonical_json_bytes(recovery_receipt),
        )

        files_written = [
            str(item["relative"]) for item in fresh_private["items"]
        ]
        if fresh_private["mode"] == "resume":
            receipt_relative = (
                f"{MARKUP_NORMALIZATION_RECEIPTS_DIR}/"
                f"{journal_doc['plan_sha256']}.json"
            )
            receipt_path = archive_services.archive_internal_path(
                root,
                receipt_relative,
            )
            normalization_receipt = {
                "schema": MARKUP_NORMALIZATION_RECEIPT_SCHEMA,
                "archive_id": archive_services.read_archive_id(root),
                "plan_sha256": journal_doc["plan_sha256"],
                "policy": journal_doc.get("policy"),
                "binding_manifest_sha256": journal_doc.get(
                    "binding_manifest_sha256"
                ),
                "journal_path": fresh_private["journal_relative"],
                "reviewed_by": reviewer,
                "created_at": timestamp,
                "item_count": len(journal_doc["items"]),
                "items": journal_doc["items"],
                "source_bytes_snapshotted": True,
                "exact_byte_revert_supported": True,
                "completed_by_recovery": True,
                "recovery_receipt_path": recovery_receipt_relative,
            }
            archive_services._write_bytes_create_if_absent(
                receipt_path,
                _canonical_json_bytes(normalization_receipt),
            )
            files_written.append(receipt_relative)
            journal_doc["state"] = "committed"
            journal_doc["receipt_path"] = receipt_relative
            journal_doc["applied_count"] = len(journal_doc["items"])
        else:
            journal_doc["state"] = "rolled_back"
            journal_doc["applied_count"] = 0
        journal_doc["recovery_mode"] = fresh_private["mode"]
        journal_doc["recovery_receipt_path"] = recovery_receipt_relative
        journal_doc["recovered_by"] = reviewer
        journal_doc["updated_at"] = timestamp
        archive_services.write_bytes_atomic(
            fresh_private["journal_path"],
            _canonical_json_bytes(journal_doc),
        )
        files_written.extend(
            [
                str(fresh_private["journal_relative"]),
                recovery_receipt_relative,
            ]
        )

    return {
        **fresh,
        "ok": True,
        "state": (
            "resumed"
            if fresh_private["mode"] == "resume"
            else "rolled_back"
        ),
        "dry_run": False,
        "approved": True,
        "lifecycle_action": "markup_normalization_recovery",
        "summary": {
            **fresh["summary"],
            "changed_count": len(fresh_private["items"]),
            "recovery_receipt_path": recovery_receipt_relative,
            "exact_byte_recovery": True,
        },
        "blockers": [],
        "would_change": [],
        "files_written": files_written,
        "privacy_guards": {
            **fresh["privacy_guards"],
            "writes": True,
        },
    }


def relation_semantics_guide() -> dict[str, Any]:
    return {
        "ok": True,
        "dry_run": True,
        "lifecycle_action": "relation_semantics_guide",
        "distinctions": [
            {
                "concept": "continues",
                "meaning": (
                    "The target is the next installment in the same line of "
                    "thought or the same continuing work. Consecutive weeks "
                    "of the same course use continues."
                ),
                "canonical_edge_type": "continues",
                "not_for": [
                    "generic ordered steps",
                    "source provenance",
                    "replacement",
                ],
            },
            {
                "concept": "sequence",
                "meaning": (
                    "The target is the next reviewed step in a generic "
                    "administrative, operational, or life-event process. It "
                    "is active as a directed sequence edge, but only a human "
                    "may approve one pair at a time."
                ),
                "canonical_edge_type": "sequence",
                "promoted_automatically": False,
            },
            {
                "concept": "recurring_program_instance",
                "meaning": (
                    "Each occurrence remains its own event/zet and shares a "
                    "reviewed recurring-series coordinate; recurrence alone "
                    "does not prove continues."
                ),
                "recommended_coordinate": "facets.recurring_series",
                "relationship_rule": (
                    "A shared recurring_series coordinate creates a candidate "
                    "context, not an edge. Use activity_group when several "
                    "zets belong to one occurrence."
                ),
            },
            {
                "concept": "third_party_principal",
                "meaning": (
                    "A Principal may represent another person, role, team, "
                    "family, company, or other actor; the archive owner and the "
                    "subject principal must not be silently conflated."
                ),
                "entity_type": "Principal",
                "registration_path": (
                    "principal-register-plan -> principal-register"
                ),
            },
            {
                "concept": "format_variant",
                "meaning": (
                    "Use only for alternate renditions of the same intellectual "
                    "content after human confirmation."
                ),
                "canonical_edge_type": "format_variant",
            },
        ],
        "rules": {
            "candidate_is_edge": False,
            "recommendation_is_human_decision": False,
            "activity_group_implies_relation": False,
            "recurrence_implies_continuation": False,
            "provider_or_llm_required": False,
            "same_course_next_week_edge": "continues",
            "generic_process_next_step_edge": "sequence",
            "sequence_batch_write_allowed": False,
            "activity_group_requires_existing_event_anchor": True,
            "notion_private_join_authority": "facets.source_page_id",
            "notion_mirror_zettel_field_is_join_authority": False,
        },
        "would_change": [],
    }


def _relation_safe_title(value: Any) -> str:
    warnings: list[str] = []
    safe = archive_services.safe_zettel_overview_string(
        value,
        warnings,
        "$.frontmatter.title",
    )
    if safe is None or len(safe) > 240:
        return "[title withheld]"
    return safe


def _relation_values(value: Any) -> set[str]:
    if isinstance(value, str) and value.strip():
        return {value.strip()}
    if isinstance(value, list):
        return {
            str(item).strip()
            for item in value
            if isinstance(item, (str, int)) and str(item).strip()
        }
    return set()


def _relation_time_values(value: Any) -> set[str]:
    values: set[str] = set()
    for raw in _relation_values(value):
        date_match = re.match(r"^(\d{4}-\d{2}-\d{2})", raw.strip())
        if date_match:
            values.add(date_match.group(1))
    return values


def _relation_zettel_projection(
    root: Path,
    path: Path,
) -> dict[str, Any] | None:
    inspection = archive_services.inspect_zettel_frontmatter_boundary(path)
    if (
        not inspection.get("metadata_readable")
        or not isinstance(inspection.get("frontmatter"), dict)
    ):
        return None
    frontmatter = inspection["frontmatter"]
    if frontmatter.get("status") not in archive_services.ZETTEL_QUERYABLE_STATUSES:
        return None
    zettel_id = str(frontmatter.get("id") or "").strip()
    if not archive_services.ZETTEL_EDGE_ZETTEL_ID_RE.fullmatch(zettel_id):
        return None
    try:
        raw_sha256 = _sha256_bytes(path.read_bytes())
    except OSError:
        return None
    facets = (
        frontmatter.get("facets")
        if isinstance(frontmatter.get("facets"), dict)
        else {}
    )
    title = _relation_safe_title(frontmatter.get("title"))
    title_tokens = {
        token.casefold()
        for token in re.findall(r"[\w가-힣]{2,}", title, flags=re.UNICODE)
        if token.casefold()
        not in {
            "the",
            "and",
            "for",
            "with",
            "from",
            "this",
            "that",
            "synthetic",
        }
    }
    source_refs: set[str] = set()
    for key in ("source_refs", "sources", "source_ref"):
        source_refs.update(_relation_values(frontmatter.get(key)))
    edges = (
        frontmatter.get("edges")
        if isinstance(frontmatter.get("edges"), list)
        else []
    )
    existing_targets = {
        str(
            edge.get("target")
            or edge.get("target_id")
            or edge.get("zettel_id")
            or ""
        ).strip()
        for edge in edges
        if isinstance(edge, dict)
    }
    sequence_index = facets.get("sequence_index")
    if not isinstance(sequence_index, int):
        sequence_index = None
    return {
        "zettel_id": zettel_id,
        "path": archive_services.archive_relative_path(path, root),
        "title": title,
        "raw_sha256": raw_sha256,
        "activity_groups": _relation_values(facets.get("activity_group")),
        "time_coordinates": (
            _relation_time_values(facets.get("notion_event_time_start"))
            | _relation_time_values(facets.get("notion_event_time_end"))
            | _relation_time_values(facets.get("thought_date"))
        ),
        "category_coordinates": (
            _relation_values(facets.get("source_category"))
            | _relation_values(facets.get("db1_category"))
            | _relation_values(facets.get("db1_subcategory"))
        ),
        "series": (
            _relation_values(facets.get("recurring_series"))
            | _relation_values(facets.get("series"))
        ),
        "sequence_groups": (
            _relation_values(facets.get("sequence"))
            | _relation_values(facets.get("process_sequence"))
            | _relation_values(facets.get("administrative_sequence"))
        ),
        "format_groups": _relation_values(facets.get("format_group")),
        "sequence_index": sequence_index,
        "source_refs": source_refs,
        "title_tokens": title_tokens,
        "existing_targets": existing_targets,
        "edge_count": len(edges),
    }


def _relation_signal(
    source: dict[str, Any],
    target: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str], int]:
    signals: list[dict[str, Any]] = []
    suggested_types: list[str] = []
    score = 0
    shared_series = source["series"] & target["series"]
    if shared_series:
        adjacent = (
            source["sequence_index"] is not None
            and target["sequence_index"] is not None
            and abs(source["sequence_index"] - target["sequence_index"]) == 1
        )
        signals.append(
            {
                "kind": "shared_recurring_or_series_coordinate",
                "strength": "high",
                "adjacent_sequence_index": adjacent,
            }
        )
        score += 50 + (20 if adjacent else 0)
        if adjacent:
            suggested_types.append("continues")
        else:
            suggested_types.append("semantic")
    shared_sequence_groups = (
        source["sequence_groups"] & target["sequence_groups"]
    )
    if shared_sequence_groups:
        adjacent = (
            source["sequence_index"] is not None
            and target["sequence_index"] is not None
            and target["sequence_index"] - source["sequence_index"] == 1
        )
        signals.append(
            {
                "kind": "shared_process_sequence_coordinate",
                "strength": "high" if adjacent else "medium",
                "source_precedes_target_by_one": adjacent,
            }
        )
        score += 55 + (20 if adjacent else 0)
        suggested_types.append("sequence" if adjacent else "semantic")
    if source["format_groups"] & target["format_groups"]:
        signals.append(
            {
                "kind": "shared_format_group_coordinate",
                "strength": "high",
            }
        )
        score += 60
        suggested_types.append("format_variant")
    if source["activity_groups"] & target["activity_groups"]:
        signals.append(
            {
                "kind": "shared_activity_group_coordinate",
                "strength": "medium",
                "relation_implied": False,
            }
        )
        score += 35
        suggested_types.append("semantic")
    if source["time_coordinates"] & target["time_coordinates"]:
        signals.append(
            {
                "kind": "shared_event_date_coordinate",
                "strength": "medium",
                "coordinate_values_echoed": False,
            }
        )
        score += 28
        suggested_types.append("semantic")
    if source["category_coordinates"] & target["category_coordinates"]:
        signals.append(
            {
                "kind": "shared_archive_category_coordinate",
                "strength": "medium",
                "coordinate_values_echoed": False,
            }
        )
        score += 25
        suggested_types.append("semantic")
    if source["source_refs"] & target["source_refs"]:
        signals.append(
            {
                "kind": "shared_source_coordinate",
                "strength": "medium",
            }
        )
        score += 30
        suggested_types.extend(["references", "semantic"])
    overlap = source["title_tokens"] & target["title_tokens"]
    if len(overlap) >= 2:
        union = source["title_tokens"] | target["title_tokens"]
        ratio = round(len(overlap) / max(1, len(union)), 3)
        signals.append(
            {
                "kind": "title_token_overlap",
                "strength": "low",
                "shared_token_count": len(overlap),
                "jaccard": ratio,
            }
        )
        score += min(20, len(overlap) * 4)
        suggested_types.append("semantic")
    return (
        signals,
        archive_services.unique_preserve_order(suggested_types),
        score,
    )


def _judgment_path(candidate_id: str) -> str:
    digest = candidate_id.removeprefix("candidate:")
    return f"{RELATION_JUDGMENT_DIR}/{digest}.json"


def _relation_candidate_plan_core(
    archive_root: Path | str,
    *,
    from_zettel: str | None,
    max_candidates: int,
    include_rejected: bool,
    suppress_zero_edge_advisory: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = archive_services.require_existing_archive_root(archive_root)
    archive_id = archive_services.read_archive_id(root)
    blockers: list[str] = []
    source_id = _safe_zettel_id(from_zettel)
    if source_id is None:
        blockers.append("relation_source_zettel_id_invalid")
    try:
        candidate_limit = int(max_candidates)
    except (TypeError, ValueError):
        candidate_limit = 0
    if not 1 <= candidate_limit <= RELATION_CANDIDATE_MAX_CANDIDATES:
        blockers.append("relation_max_candidates_invalid")

    projections = [
        projection
        for path in archive_services.iter_zettel_paths(root)
        for projection in [_relation_zettel_projection(root, path)]
        if projection is not None
    ]
    by_id = {item["zettel_id"]: item for item in projections}
    source = by_id.get(source_id or "")
    if source is None:
        blockers.append("relation_source_zettel_unavailable")

    candidates: list[dict[str, Any]] = []
    private_candidates: dict[str, dict[str, Any]] = {}
    rejected_suppressed_count = 0
    if source is not None and not blockers:
        for target in projections:
            if (
                target["zettel_id"] == source["zettel_id"]
                or target["zettel_id"] in source["existing_targets"]
            ):
                continue
            signals, suggested_types, score = _relation_signal(
                source,
                target,
            )
            if not signals:
                continue
            seed = {
                "archive_id": archive_id,
                "source_zettel_id": source["zettel_id"],
                "target_zettel_id": target["zettel_id"],
                "source_sha256": source["raw_sha256"],
                "target_sha256": target["raw_sha256"],
                "signals": signals,
            }
            candidate_id = "candidate:" + _sha256_bytes(
                _canonical_json_bytes(seed)
            )
            judgment_path = archive_services.archive_internal_path(
                root,
                _judgment_path(candidate_id),
            )
            prior_rejected = False
            if judgment_path.is_file():
                try:
                    judgment = json.loads(
                        judgment_path.read_text(encoding="utf-8")
                    )
                    prior_rejected = (
                        isinstance(judgment, dict)
                        and judgment.get("candidate_id") == candidate_id
                        and judgment.get("decision") == "reject"
                    )
                except (OSError, json.JSONDecodeError):
                    blockers.append("relation_judgment_unreadable")
            if prior_rejected and not include_rejected:
                rejected_suppressed_count += 1
                continue
            public = {
                "candidate_id": candidate_id,
                "source": {
                    "zettel_id": source["zettel_id"],
                    "title": source["title"],
                },
                "target": {
                    "zettel_id": target["zettel_id"],
                    "title": target["title"],
                },
                "signals": signals,
                "suggested_edge_types": suggested_types,
                "score": score,
                "recommendation_origin": "deterministic_local_metadata",
                "edge_type_requires_human_confirmation": True,
                "prior_rejected": prior_rejected,
            }
            candidates.append(public)
            private_candidates[candidate_id] = {
                "public": public,
                "source": source,
                "target": target,
            }
    candidates.sort(
        key=lambda item: (
            -int(item["score"]),
            item["target"]["zettel_id"],
        )
    )
    truncated_count = max(0, len(candidates) - candidate_limit)
    candidates = candidates[:candidate_limit]
    private_candidates = {
        item["candidate_id"]: private_candidates[item["candidate_id"]]
        for item in candidates
    }
    plan_document = {
        "schema": RELATION_CANDIDATE_PLAN_SCHEMA,
        "archive_id": archive_id,
        "source_zettel_id": source_id,
        "source_sha256": source.get("raw_sha256") if source else None,
        "max_candidates": candidate_limit,
        "include_rejected": bool(include_rejected),
        "candidates": candidates,
    }
    plan_sha256 = _sha256_bytes(_canonical_json_bytes(plan_document))
    advisory = None
    if (
        source is not None
        and source["edge_count"] == 0
        and not suppress_zero_edge_advisory
    ):
        advisory = {
            "code": "zero_edge_advisory",
            "severity": "advisory",
            "blocking": False,
            "suppressible": True,
            "message": (
                "This zettel currently has zero edges. Review candidates; "
                "do not create an edge merely to clear the advisory."
            ),
        }
    aggregate = archive_services.unique_preserve_order(blockers)
    result = {
        "ok": not aggregate,
        "state": "ready" if not aggregate else "blocked",
        "dry_run": True,
        "lifecycle_action": "relation_candidate_plan",
        "archive_id": archive_id,
        "summary": {
            "source_zettel_id": source_id,
            "source_edge_count": source.get("edge_count") if source else None,
            "candidate_count": len(candidates),
            "truncated_count": truncated_count,
            "rejected_suppressed_count": rejected_suppressed_count,
            "plan_sha256": plan_sha256 if not aggregate else None,
            "coordinate_first": True,
            "provider_or_llm_used": False,
        },
        "candidates": candidates,
        "advisory": advisory,
        "semantics": relation_semantics_guide(),
        "blockers": aggregate,
        "warnings": [],
        "would_change": [],
        "privacy_guards": {
            "zettel_bodies_read": False,
            "provider_called": False,
            "network_checked": False,
            "llm_called": False,
            "local_absolute_paths_echoed": False,
            "writes": False,
        },
    }
    private = {
        "root": root,
        "plan_sha256": plan_sha256,
        "plan_document": plan_document,
        "candidates": private_candidates,
    }
    return result, private


def relation_candidate_plan(
    archive_root: Path | str,
    *,
    from_zettel: str | None,
    max_candidates: int = 50,
    include_rejected: bool = False,
    suppress_zero_edge_advisory: bool = False,
) -> dict[str, Any]:
    result, _private = _relation_candidate_plan_core(
        archive_root,
        from_zettel=from_zettel,
        max_candidates=max_candidates,
        include_rejected=include_rejected,
        suppress_zero_edge_advisory=suppress_zero_edge_advisory,
    )
    return result


def relation_candidate_decide(
    archive_root: Path | str,
    *,
    from_zettel: str | None,
    candidate_id: str | None,
    decision: str,
    edge_type: str | None,
    visibility: str,
    reason: str | None,
    confidence: str | None,
    expected_plan_sha256: str | None,
    reviewed_by: str | None,
    max_candidates: int = 50,
    include_rejected: bool = False,
) -> dict[str, Any]:
    plan, private = _relation_candidate_plan_core(
        archive_root,
        from_zettel=from_zettel,
        max_candidates=max_candidates,
        include_rejected=include_rejected,
        suppress_zero_edge_advisory=False,
    )
    blockers = list(plan["blockers"])
    expected = str(expected_plan_sha256 or "").strip().lower()
    normalized_decision = str(decision or "").strip().lower()
    normalized_candidate_id = str(candidate_id or "").strip().lower()
    normalized_edge_type = (
        str(edge_type or "").strip().lower().replace("-", "_")
    )
    normalized_visibility = str(visibility or "").strip().lower()
    safe_reason = archive_services.safe_operator_feedback_scalar(
        reason,
        max_length=600,
    )
    reviewer = archive_services.safe_project_intake_actor_id(reviewed_by)
    normalized_confidence = str(confidence or "").strip().lower()
    if normalized_decision not in RELATION_DECISIONS:
        blockers.append("relation_decision_invalid")
    if normalized_candidate_id not in private["candidates"]:
        blockers.append("relation_candidate_not_in_plan")
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        blockers.append("relation_expected_plan_sha256_invalid")
    elif expected != private["plan_sha256"]:
        blockers.append("relation_plan_changed")
    if safe_reason is None:
        blockers.append("relation_review_reason_invalid")
    if normalized_confidence not in {"low", "medium", "high"}:
        blockers.append("relation_review_confidence_invalid")
    if reviewer is None:
        blockers.append("relation_reviewer_invalid")
    if normalized_decision == "accept" and not normalized_edge_type:
        blockers.append("relation_accept_edge_type_required")
    if normalized_decision == "reject" and normalized_edge_type:
        blockers.append("relation_reject_must_not_choose_edge_type")
    if not archive_services.safe_source_intake_plan_scalar(
        normalized_visibility
    ):
        blockers.append("relation_visibility_invalid")

    candidate_private = private["candidates"].get(normalized_candidate_id)
    edge_preview: dict[str, Any] | None = None
    if (
        candidate_private is not None
        and normalized_decision == "accept"
        and normalized_edge_type
    ):
        edge_preview = archive_services.zettel_edge_write(
            private["root"],
            from_zettel=candidate_private["source"]["zettel_id"],
            target_ref=candidate_private["target"]["zettel_id"],
            edge_type=normalized_edge_type,
            visibility=normalized_visibility,
            dry_run=True,
        )
        if not edge_preview.get("ok"):
            blockers.extend(
                str(item) for item in edge_preview.get("blockers", [])
            )
    aggregate = archive_services.unique_preserve_order(blockers)
    if aggregate or candidate_private is None:
        return {
            **plan,
            "ok": False,
            "state": "blocked",
            "dry_run": False,
            "approved": False,
            "lifecycle_action": "relation_candidate_decide",
            "decision": normalized_decision,
            "candidate_id": (
                normalized_candidate_id
                if re.fullmatch(r"candidate:[0-9a-f]{64}", normalized_candidate_id)
                else None
            ),
            "edge_preview": edge_preview,
            "blockers": aggregate,
            "would_change": [],
            "files_written": [],
        }

    root: Path = private["root"]
    with _MarkupMutationLock(root):
        fresh, fresh_private = _relation_candidate_plan_core(
            root,
            from_zettel=from_zettel,
            max_candidates=max_candidates,
            include_rejected=include_rejected,
            suppress_zero_edge_advisory=False,
        )
        fresh_candidate = fresh_private["candidates"].get(
            normalized_candidate_id
        )
        if (
            not fresh["ok"]
            or fresh_private["plan_sha256"] != expected
            or fresh_candidate is None
        ):
            return {
                **fresh,
                "ok": False,
                "state": "blocked",
                "dry_run": False,
                "approved": False,
                "lifecycle_action": "relation_candidate_decide",
                "decision": normalized_decision,
                "candidate_id": normalized_candidate_id,
                "blockers": archive_services.unique_preserve_order(
                    [*fresh["blockers"], "relation_plan_changed"]
                ),
                "would_change": [],
                "files_written": [],
            }

        judgment_relative = _judgment_path(normalized_candidate_id)
        judgment_path = archive_services.archive_internal_path(
            root,
            judgment_relative,
        )
        if judgment_path.exists():
            try:
                existing = json.loads(
                    judgment_path.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                existing = None
            if (
                isinstance(existing, dict)
                and existing.get("candidate_id")
                == normalized_candidate_id
                and existing.get("decision") == normalized_decision
                and existing.get("edge_type")
                == (
                    normalized_edge_type
                    if normalized_decision == "accept"
                    else None
                )
            ):
                return {
                    **fresh,
                    "ok": True,
                    "state": "already_decided",
                    "dry_run": False,
                    "approved": True,
                    "lifecycle_action": "relation_candidate_decide",
                    "decision": normalized_decision,
                    "candidate_id": normalized_candidate_id,
                    "judgment_path": judgment_relative,
                    "blockers": [],
                    "would_change": [],
                    "files_written": [],
                }
            return {
                **fresh,
                "ok": False,
                "state": "blocked",
                "dry_run": False,
                "approved": False,
                "lifecycle_action": "relation_candidate_decide",
                "decision": normalized_decision,
                "candidate_id": normalized_candidate_id,
                "blockers": ["relation_judgment_collision"],
                "would_change": [],
                "files_written": [],
            }

        timestamp = _now()
        edge_result: dict[str, Any] | None = None
        files_written: list[str] = []
        if normalized_decision == "accept":
            edge_result = archive_services.zettel_edge_write(
                root,
                from_zettel=fresh_candidate["source"]["zettel_id"],
                target_ref=fresh_candidate["target"]["zettel_id"],
                edge_type=normalized_edge_type,
                visibility=normalized_visibility,
                approve=True,
                reviewed_by=reviewer,
            )
            if not edge_result.get("ok"):
                return {
                    **fresh,
                    "ok": False,
                    "state": "blocked",
                    "dry_run": False,
                    "approved": True,
                    "lifecycle_action": "relation_candidate_decide",
                    "decision": normalized_decision,
                    "candidate_id": normalized_candidate_id,
                    "edge_result": edge_result,
                    "blockers": edge_result.get("blockers", []),
                    "would_change": [],
                    "files_written": edge_result.get("files_written", []),
                }
            files_written.extend(
                str(item) for item in edge_result.get("files_written", [])
            )

        envelope = {
            "source_zettel_id": fresh_candidate["source"]["zettel_id"],
            "target_zettel_id": fresh_candidate["target"]["zettel_id"],
            "edge_type": (
                normalized_edge_type
                if normalized_decision == "accept"
                else None
            ),
            "visibility": normalized_visibility,
            "review_scope": "single_candidate_pair",
            "recommendation_origin": "deterministic_local_metadata",
            "candidate_plan_sha256": expected,
            "reason": safe_reason,
            "confidence": normalized_confidence,
            "reviewed_by": reviewer,
        }
        judgment = {
            "schema": RELATION_JUDGMENT_SCHEMA,
            "archive_id": archive_services.read_archive_id(root),
            "candidate_id": normalized_candidate_id,
            "decision": normalized_decision,
            "edge_type": envelope["edge_type"],
            "decision_envelope": envelope,
            "edge_id": (
                edge_result.get("edge_id")
                if isinstance(edge_result, dict)
                else None
            ),
            "edge_receipt_path": (
                edge_result.get("receipt_path")
                if isinstance(edge_result, dict)
                else None
            ),
            "created_at": timestamp,
        }
        judgment_bytes = _canonical_json_bytes(judgment)
        judgment_sha256 = _sha256_bytes(judgment_bytes)
        receipt_relative = (
            f"{RELATION_JUDGMENT_RECEIPTS_DIR}/"
            f"{judgment_sha256}.json"
        )
        receipt_path = archive_services.archive_internal_path(
            root,
            receipt_relative,
        )
        receipt_doc = {
            "schema": RELATION_JUDGMENT_RECEIPT_SCHEMA,
            "archive_id": archive_services.read_archive_id(root),
            "candidate_id": normalized_candidate_id,
            "decision": normalized_decision,
            "judgment_path": judgment_relative,
            "judgment_sha256": judgment_sha256,
            "edge_id": judgment["edge_id"],
            "edge_receipt_path": judgment["edge_receipt_path"],
            "reviewed_by": reviewer,
            "created_at": timestamp,
        }
        try:
            archive_services._write_bytes_create_if_absent(
                judgment_path,
                judgment_bytes,
            )
            archive_services._write_bytes_create_if_absent(
                receipt_path,
                _canonical_json_bytes(receipt_doc),
            )
        except OSError:
            # An accepted edge already carries its own durable receipt. Report
            # the judgment gap honestly instead of rolling back a valid edge
            # with an unreviewed compensating mutation.
            return {
                **fresh,
                "ok": False,
                "state": "partial",
                "dry_run": False,
                "approved": True,
                "lifecycle_action": "relation_candidate_decide",
                "decision": normalized_decision,
                "candidate_id": normalized_candidate_id,
                "edge_result": edge_result,
                "blockers": ["relation_judgment_write_failed"],
                "would_change": [],
                "files_written": files_written,
            }
        files_written.extend([judgment_relative, receipt_relative])

        edge_verified = normalized_decision == "reject"
        if normalized_decision == "accept" and edge_result is not None:
            try:
                source_path = archive_services.resolve_zettel_path(
                    root,
                    zettel_id=fresh_candidate["source"]["zettel_id"],
                    relative_path=None,
                )
                frontmatter, _body = archive_services.require_readable_zettel_content(
                    source_path
                )
                edges = (
                    frontmatter.get("edges")
                    if isinstance(frontmatter.get("edges"), list)
                    else []
                )
                edge_verified = any(
                    isinstance(item, dict)
                    and item.get("edge_id") == edge_result.get("edge_id")
                    and item.get("receipt") == edge_result.get("receipt_path")
                    for item in edges
                )
            except archive_services.ArchiveServiceError:
                edge_verified = False

    return {
        **fresh,
        "ok": edge_verified,
        "state": "decided" if edge_verified else "partial",
        "dry_run": False,
        "approved": True,
        "lifecycle_action": "relation_candidate_decide",
        "decision": normalized_decision,
        "candidate_id": normalized_candidate_id,
        "judgment_path": judgment_relative,
        "judgment_receipt_path": receipt_relative,
        "edge_result": edge_result,
        "verification": {
            "durable_judgment_verified": True,
            "durable_edge_verified": (
                edge_verified
                if normalized_decision == "accept"
                else None
            ),
            "rejection_memory_verified": (
                edge_verified
                if normalized_decision == "reject"
                else None
            ),
        },
        "blockers": (
            [] if edge_verified else ["relation_post_write_verification_failed"]
        ),
        "would_change": [],
        "files_written": archive_services.unique_preserve_order(files_written),
        "privacy_guards": {
            **fresh["privacy_guards"],
            "writes": True,
        },
    }


def _project_mirror_for_repair(
    inspection_root: Path,
) -> tuple[Path | None, str | None]:
    for _label, search_root in (
        archive_services.wom_kit_project_source_mirror_search_roots(
            inspection_root
        )
    ):
        mirror = search_root / ".zettel-kasten" / "source"
        if (
            archive_services.wom_kit_real_path_kind(search_root, mirror)
            == "directory"
            and archive_services.wom_kit_project_update_git_metadata_is_local_real(
                search_root,
                mirror,
            )
        ):
            return mirror, None
    return None, "project_source_mirror_unavailable"


class _PrincipalLock:
    def __init__(self, root: Path, principal_id: str) -> None:
        lock_dir = archive_services.archive_internal_path(
            root,
            f"{PRINCIPAL_RECEIPTS_DIR}/.locks",
        )
        lock_dir.mkdir(parents=True, exist_ok=True)
        digest = _sha256_bytes(principal_id.encode("utf-8"))
        self._path = lock_dir / f"{digest}.lock"
        self._handle: Any = None

    def __enter__(self) -> "_PrincipalLock":
        self._handle = self._path.open("a+b")
        self._handle.seek(0, os.SEEK_END)
        if self._handle.tell() == 0:
            self._handle.write(b"\0")
            self._handle.flush()
            os.fsync(self._handle.fileno())
        self._handle.seek(0)
        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    msvcrt.locking(
                        self._handle.fileno(),
                        msvcrt.LK_LOCK,
                        1,
                    )
                    break
                except OSError:
                    continue
        else:
            import fcntl

            fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc_info: Any) -> bool:
        try:
            self._handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(
                    self._handle.fileno(),
                    msvcrt.LK_UNLCK,
                    1,
                )
            else:
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()
        return False


def _safe_principal_display_name(value: str | None) -> str | None:
    text = str(value or "").strip()
    if (
        not text
        or len(text) > 300
        or any(ord(character) < 32 for character in text)
        or archive_services.source_intake_secret_like(text)
        or archive_services.contains_forbidden_location_reference(text)
    ):
        return None
    return text


def _principal_registration_plan_core(
    archive_root: Path | str,
    *,
    principal_id: str | None,
    kind: str | None,
    display_name: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = archive_services.require_existing_archive_root(archive_root)
    archive_id = archive_services.read_archive_id(root)
    normalized_id = str(principal_id or "").strip()
    normalized_kind = str(kind or "").strip().lower()
    safe_name = _safe_principal_display_name(display_name)
    blockers: list[str] = []
    if not archive_services.PRINCIPAL_ID_RE.fullmatch(normalized_id):
        blockers.append("principal_id_invalid")
    if normalized_kind not in archive_services.PRINCIPAL_KINDS:
        blockers.append("principal_kind_invalid")
    if safe_name is None:
        blockers.append("principal_display_name_invalid")

    records, registry_issues = archive_services.load_registered_principals(
        root
    )
    blockers.extend(registry_issues)
    existing = [
        record
        for record in records
        if record.get("principal_id") == normalized_id
    ]
    if existing:
        blockers.append("principal_id_already_registered")

    record_relative = (
        archive_services.principal_record_relative_path(normalized_id)
        if archive_services.PRINCIPAL_ID_RE.fullmatch(normalized_id)
        else None
    )
    if (
        record_relative
        and archive_services.archive_internal_path(
            root,
            record_relative,
        ).exists()
    ):
        blockers.append("principal_record_path_already_exists")
    binding = {
        "schema": "wom-kit/principal-registration-plan/v0.1",
        "archive_id": archive_id,
        "principal_id": normalized_id,
        "kind": normalized_kind,
        "display_name_sha256": (
            _sha256_bytes(safe_name.encode("utf-8"))
            if safe_name is not None
            else None
        ),
        "record_path": record_relative,
        "expected_state": "absent",
    }
    plan_sha256 = _sha256_bytes(_canonical_json_bytes(binding))
    aggregate = archive_services.unique_preserve_order(blockers)
    result = {
        "ok": not aggregate,
        "state": "ready" if not aggregate else "blocked",
        "dry_run": True,
        "lifecycle_action": "principal_registration_plan",
        "archive_id": archive_id,
        "principal": {
            "principal_id": normalized_id or None,
            "kind": normalized_kind or None,
            "display_name_char_count": (
                len(safe_name) if safe_name is not None else None
            ),
            "display_name_sha256": binding["display_name_sha256"],
        },
        "record_path": record_relative,
        "plan_sha256": plan_sha256 if not aggregate else None,
        "blockers": aggregate,
        "warnings": [],
        "would_change": (
            [record_relative] if not aggregate and record_relative else []
        ),
        "privacy_guards": {
            "display_name_echoed": False,
            "zettel_bodies_read": False,
            "local_absolute_paths_echoed": False,
            "provider_called": False,
            "network_checked": False,
            "writes": False,
        },
    }
    return result, {
        "root": root,
        "archive_id": archive_id,
        "principal_id": normalized_id,
        "kind": normalized_kind,
        "display_name": safe_name,
        "record_relative": record_relative,
        "binding": binding,
        "plan_sha256": plan_sha256,
    }


def principal_registration_plan(
    archive_root: Path | str,
    *,
    principal_id: str | None,
    kind: str | None,
    display_name: str | None,
) -> dict[str, Any]:
    result, _private = _principal_registration_plan_core(
        archive_root,
        principal_id=principal_id,
        kind=kind,
        display_name=display_name,
    )
    return result


def principal_register(
    archive_root: Path | str,
    *,
    principal_id: str | None,
    kind: str | None,
    display_name: str | None,
    expected_plan_sha256: str | None,
    reviewed_by: str | None,
) -> dict[str, Any]:
    plan, private = _principal_registration_plan_core(
        archive_root,
        principal_id=principal_id,
        kind=kind,
        display_name=display_name,
    )
    blockers = list(plan["blockers"])
    expected = str(expected_plan_sha256 or "").strip().lower()
    reviewer = archive_services.safe_project_intake_actor_id(reviewed_by)
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        blockers.append("principal_expected_plan_sha256_invalid")
    elif expected != private["plan_sha256"]:
        blockers.append("principal_registration_plan_changed")
    if reviewer is None:
        blockers.append("principal_reviewer_invalid")
    if blockers:
        return {
            **plan,
            "ok": False,
            "state": "blocked",
            "dry_run": False,
            "approved": False,
            "lifecycle_action": "principal_register",
            "blockers": archive_services.unique_preserve_order(blockers),
            "would_change": [],
            "files_written": [],
        }

    root: Path = private["root"]
    with _PrincipalLock(root, private["principal_id"]):
        fresh, fresh_private = _principal_registration_plan_core(
            root,
            principal_id=private["principal_id"],
            kind=private["kind"],
            display_name=private["display_name"],
        )
        if (
            not fresh["ok"]
            or fresh_private["plan_sha256"] != expected
        ):
            return {
                **fresh,
                "ok": False,
                "state": "blocked",
                "dry_run": False,
                "approved": False,
                "lifecycle_action": "principal_register",
                "blockers": archive_services.unique_preserve_order(
                    [
                        *fresh["blockers"],
                        "principal_registration_plan_changed",
                    ]
                ),
                "would_change": [],
                "files_written": [],
            }
        timestamp = _now()
        record = {
            "schema": archive_services.PRINCIPAL_RECORD_SCHEMA,
            "principal_id": fresh_private["principal_id"],
            "kind": fresh_private["kind"],
            "display_name": fresh_private["display_name"],
            "status": "active",
            "created_at": timestamp,
            "reviewed_by": reviewer,
        }
        record_bytes = archive_services.dump_yaml(record).encode("utf-8")
        record_sha256 = _sha256_bytes(record_bytes)
        receipt_relative = (
            f"{PRINCIPAL_RECEIPTS_DIR}/register."
            f"{_sha256_bytes(fresh_private['principal_id'].encode('utf-8'))}."
            f"{re.sub(r'[^0-9TZ]', '', timestamp)}."
            f"{record_sha256[:16]}.json"
        )
        record_path = archive_services.archive_internal_path(
            root,
            fresh_private["record_relative"],
        )
        receipt_path = archive_services.archive_internal_path(
            root,
            receipt_relative,
        )
        receipt = {
            "schema": PRINCIPAL_REGISTRATION_RECEIPT_SCHEMA,
            "archive_id": fresh_private["archive_id"],
            "principal_id": fresh_private["principal_id"],
            "kind": fresh_private["kind"],
            "record_path": fresh_private["record_relative"],
            "record_sha256": record_sha256,
            "plan_sha256": expected,
            "reviewed_by": reviewer,
            "created_at": timestamp,
        }
        record_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        archive_services._write_bytes_create_if_absent(
            record_path,
            record_bytes,
        )
        try:
            archive_services._write_bytes_create_if_absent(
                receipt_path,
                _canonical_json_bytes(receipt),
            )
        except BaseException:
            try:
                if (
                    record_path.is_file()
                    and record_path.read_bytes() == record_bytes
                ):
                    record_path.unlink()
            except OSError:
                pass
            raise

    return {
        **fresh,
        "ok": True,
        "state": "registered",
        "dry_run": False,
        "approved": True,
        "lifecycle_action": "principal_register",
        "record_sha256": record_sha256,
        "receipt_path": receipt_relative,
        "blockers": [],
        "warnings": [],
        "would_change": [],
        "files_written": [
            fresh_private["record_relative"],
            receipt_relative,
        ],
        "privacy_guards": {
            **fresh["privacy_guards"],
            "writes": True,
        },
    }


def principal_list(
    archive_root: Path | str,
    *,
    include_display_names: bool = False,
) -> dict[str, Any]:
    root = archive_services.require_existing_archive_root(archive_root)
    archive_id = archive_services.read_archive_id(root)
    records, issues = archive_services.load_registered_principals(root)
    return {
        "ok": not issues,
        "state": "ready" if not issues else "blocked",
        "dry_run": True,
        "lifecycle_action": "principal_list",
        "archive_id": archive_id,
        "principal_count": len(records) if not issues else 0,
        "principals": (
            [
                {
                    "principal_id": record.get("principal_id"),
                    "kind": record.get("kind"),
                    "storage": record.get("storage"),
                    **(
                        {"display_name": record.get("display_name")}
                        if include_display_names
                        else {}
                    ),
                }
                for record in records
            ]
            if not issues
            else []
        ),
        "blockers": issues,
        "warnings": [],
        "would_change": [],
        "privacy_guards": {
            "display_names_echoed": bool(include_display_names),
            "zettel_bodies_read": False,
            "local_absolute_paths_echoed": False,
            "provider_called": False,
            "network_checked": False,
            "writes": False,
        },
    }


def _principal_usage(
    root: Path,
    principal_id: str,
) -> tuple[list[str], list[str]]:
    used_in: list[str] = []
    blockers: list[str] = []
    for path in archive_services.iter_zettel_paths(root):
        inspection = archive_services.inspect_zettel_frontmatter_boundary(path)
        if not inspection.get("metadata_readable"):
            blockers.append("principal_edge_usage_unavailable")
            continue
        frontmatter = inspection.get("frontmatter")
        if not isinstance(frontmatter, dict):
            blockers.append("principal_edge_usage_unavailable")
            continue
        edges = frontmatter.get("edges")
        if edges is None:
            continue
        if not isinstance(edges, list):
            blockers.append("principal_edge_usage_unavailable")
            continue
        if any(
            isinstance(edge, dict)
            and str(
                edge.get("target")
                or edge.get("target_id")
                or edge.get("zettel_id")
                or ""
            ).strip()
            == principal_id
            for edge in edges
        ):
            used_in.append(
                archive_services.archive_relative_path(path, root)
            )
    return (
        archive_services.unique_preserve_order(used_in),
        archive_services.unique_preserve_order(blockers),
    )


def _principal_unregistration_plan_core(
    archive_root: Path | str,
    *,
    principal_id: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = archive_services.require_existing_archive_root(archive_root)
    archive_id = archive_services.read_archive_id(root)
    normalized_id = str(principal_id or "").strip()
    blockers: list[str] = []
    if not archive_services.PRINCIPAL_ID_RE.fullmatch(normalized_id):
        blockers.append("principal_id_invalid")
    records, issues = archive_services.load_registered_principals(root)
    blockers.extend(issues)
    matches = [
        record
        for record in records
        if record.get("principal_id") == normalized_id
    ]
    record = matches[0] if len(matches) == 1 else None
    if record is None:
        blockers.append("principal_not_registered")
    elif record.get("storage") != "registered_third_party":
        blockers.append("archive_owner_principal_cannot_be_unregistered")
    used_in, usage_blockers = _principal_usage(root, normalized_id)
    blockers.extend(usage_blockers)
    if used_in:
        blockers.append("principal_is_referenced_by_zettel_edge")

    record_relative = (
        str(record.get("record_path"))
        if isinstance(record, dict)
        and isinstance(record.get("record_path"), str)
        else None
    )
    record_bytes: bytes | None = None
    record_sha256: str | None = None
    if record_relative:
        record_path = archive_services.archive_internal_path(
            root,
            record_relative,
        )
        try:
            if record_path.is_symlink() or not record_path.is_file():
                raise OSError
            record_bytes = record_path.read_bytes()
            record_sha256 = _sha256_bytes(record_bytes)
        except OSError:
            blockers.append("principal_record_unavailable")
    binding = {
        "schema": "wom-kit/principal-unregistration-plan/v0.1",
        "archive_id": archive_id,
        "principal_id": normalized_id,
        "record_path": record_relative,
        "record_sha256": record_sha256,
        "used_in": sorted(used_in),
    }
    plan_sha256 = _sha256_bytes(_canonical_json_bytes(binding))
    aggregate = archive_services.unique_preserve_order(blockers)
    result = {
        "ok": not aggregate,
        "state": "ready" if not aggregate else "blocked",
        "dry_run": True,
        "lifecycle_action": "principal_unregistration_plan",
        "archive_id": archive_id,
        "principal_id": normalized_id or None,
        "record_path": record_relative,
        "record_sha256": record_sha256,
        "used_in": used_in,
        "plan_sha256": plan_sha256 if not aggregate else None,
        "blockers": aggregate,
        "warnings": [],
        "would_change": (
            [record_relative] if not aggregate and record_relative else []
        ),
        "privacy_guards": {
            "display_name_echoed": False,
            "zettel_bodies_read": True,
            "zettel_body_semantics_used": False,
            "zettel_bodies_echoed": False,
            "local_absolute_paths_echoed": False,
            "provider_called": False,
            "network_checked": False,
            "writes": False,
        },
    }
    return result, {
        "root": root,
        "archive_id": archive_id,
        "principal_id": normalized_id,
        "record_relative": record_relative,
        "record_bytes": record_bytes,
        "record_sha256": record_sha256,
        "plan_sha256": plan_sha256,
    }


def principal_unregistration_plan(
    archive_root: Path | str,
    *,
    principal_id: str | None,
) -> dict[str, Any]:
    result, _private = _principal_unregistration_plan_core(
        archive_root,
        principal_id=principal_id,
    )
    return result


def principal_unregister(
    archive_root: Path | str,
    *,
    principal_id: str | None,
    expected_plan_sha256: str | None,
    reviewed_by: str | None,
) -> dict[str, Any]:
    plan, private = _principal_unregistration_plan_core(
        archive_root,
        principal_id=principal_id,
    )
    blockers = list(plan["blockers"])
    expected = str(expected_plan_sha256 or "").strip().lower()
    reviewer = archive_services.safe_project_intake_actor_id(reviewed_by)
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        blockers.append("principal_expected_plan_sha256_invalid")
    elif expected != private["plan_sha256"]:
        blockers.append("principal_unregistration_plan_changed")
    if reviewer is None:
        blockers.append("principal_reviewer_invalid")
    if blockers:
        return {
            **plan,
            "ok": False,
            "state": "blocked",
            "dry_run": False,
            "approved": False,
            "lifecycle_action": "principal_unregister",
            "blockers": archive_services.unique_preserve_order(blockers),
            "would_change": [],
            "files_written": [],
        }

    root: Path = private["root"]
    with _PrincipalLock(root, private["principal_id"]):
        fresh, fresh_private = _principal_unregistration_plan_core(
            root,
            principal_id=private["principal_id"],
        )
        if (
            not fresh["ok"]
            or fresh_private["plan_sha256"] != expected
            or fresh_private["record_bytes"] is None
        ):
            return {
                **fresh,
                "ok": False,
                "state": "blocked",
                "dry_run": False,
                "approved": False,
                "lifecycle_action": "principal_unregister",
                "blockers": archive_services.unique_preserve_order(
                    [
                        *fresh["blockers"],
                        "principal_unregistration_plan_changed",
                    ]
                ),
                "would_change": [],
                "files_written": [],
            }
        timestamp = _now()
        receipt_relative = (
            f"{PRINCIPAL_RECEIPTS_DIR}/unregister."
            f"{_sha256_bytes(fresh_private['principal_id'].encode('utf-8'))}."
            f"{re.sub(r'[^0-9TZ]', '', timestamp)}."
            f"{fresh_private['record_sha256'][:16]}.json"
        )
        record_path = archive_services.archive_internal_path(
            root,
            fresh_private["record_relative"],
        )
        receipt_path = archive_services.archive_internal_path(
            root,
            receipt_relative,
        )
        receipt = {
            "schema": PRINCIPAL_UNREGISTRATION_RECEIPT_SCHEMA,
            "archive_id": fresh_private["archive_id"],
            "principal_id": fresh_private["principal_id"],
            "record_path": fresh_private["record_relative"],
            "removed_record_sha256": fresh_private["record_sha256"],
            "plan_sha256": expected,
            "reviewed_by": reviewer,
            "created_at": timestamp,
        }
        record_path.unlink()
        try:
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            archive_services._write_bytes_create_if_absent(
                receipt_path,
                _canonical_json_bytes(receipt),
            )
        except BaseException:
            try:
                archive_services._write_bytes_create_if_absent(
                    record_path,
                    fresh_private["record_bytes"],
                )
            except OSError:
                pass
            raise

    return {
        **fresh,
        "ok": True,
        "state": "unregistered",
        "dry_run": False,
        "approved": True,
        "lifecycle_action": "principal_unregister",
        "receipt_path": receipt_relative,
        "blockers": [],
        "warnings": [],
        "would_change": [],
        "files_written": [receipt_relative],
        "privacy_guards": {
            **fresh["privacy_guards"],
            "writes": True,
        },
    }


def _project_bytecode_plan_core(
    inspection_root: Path | str,
    *,
    max_files: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = Path(inspection_root).expanduser().resolve()
    blockers: list[str] = []
    if not root.is_dir() or root.is_symlink():
        blockers.append("project_root_invalid")
    try:
        file_limit = int(max_files)
    except (TypeError, ValueError):
        file_limit = 0
    if not 1 <= file_limit <= PROJECT_BYTECODE_REPAIR_MAX_FILES:
        blockers.append("project_bytecode_max_files_invalid")
    mirror: Path | None = None
    if not blockers:
        mirror, mirror_error = _project_mirror_for_repair(root)
        if mirror_error:
            blockers.append(mirror_error)
    source_root = (
        mirror / "wom-kit" / "src" / "wom_kit"
        if mirror is not None
        else None
    )
    if (
        source_root is None
        or archive_services.wom_kit_real_path_kind(
            root,
            source_root,
        )
        != "directory"
    ):
        blockers.append("project_runtime_source_root_unavailable")

    candidates: list[dict[str, Any]] = []
    pycache_dirs: list[Path] = []
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if not blockers and source_root is not None and mirror is not None:
        try:
            for directory, dirnames, filenames in os.walk(
                source_root,
                topdown=True,
                followlinks=False,
            ):
                directory_path = Path(directory)
                safe_dirnames: list[str] = []
                for dirname in dirnames:
                    child = directory_path / dirname
                    child_stat = os.lstat(child)
                    if (
                        stat.S_ISLNK(child_stat.st_mode)
                        or (
                            reparse_flag
                            and getattr(
                                child_stat,
                                "st_file_attributes",
                                0,
                            )
                            & reparse_flag
                        )
                    ):
                        blockers.append(
                            "project_bytecode_path_unsafe"
                        )
                        continue
                    safe_dirnames.append(dirname)
                    if dirname.casefold() == "__pycache__":
                        pycache_dirs.append(child)
                dirnames[:] = safe_dirnames
                for filename in filenames:
                    if not filename.casefold().endswith((".pyc", ".pyo")):
                        continue
                    path = directory_path / filename
                    path_stat = os.lstat(path)
                    if (
                        not stat.S_ISREG(path_stat.st_mode)
                        or stat.S_ISLNK(path_stat.st_mode)
                        or not archive_services.wom_kit_path_components_are_real(
                            root,
                            path,
                        )
                    ):
                        blockers.append(
                            "project_bytecode_path_unsafe"
                        )
                        continue
                    relative = path.relative_to(mirror).as_posix()
                    tracked, _output = (
                        archive_services.wom_kit_project_update_git(
                            mirror,
                            [
                                "ls-files",
                                "--error-unmatch",
                                "--",
                                relative,
                            ],
                        )
                    )
                    if tracked:
                        blockers.append(
                            "project_bytecode_tracked_file_refused"
                        )
                        continue
                    value = path.read_bytes()
                    candidates.append(
                        {
                            "path": path,
                            "relative": relative,
                            "bytes": len(value),
                            "sha256": _sha256_bytes(value),
                        }
                    )
                    if len(candidates) > file_limit:
                        blockers.append(
                            "project_bytecode_file_bound_exceeded"
                        )
                        break
                if "project_bytecode_file_bound_exceeded" in blockers:
                    break
        except (OSError, RuntimeError, ValueError):
            blockers.append("project_bytecode_inventory_failed")

    binding = {
        "schema": "wom-kit/project-bytecode-repair-plan-binding/v0.1",
        "mirror_head": None,
        "files": [
            {
                "relative": item["relative"],
                "bytes": item["bytes"],
                "sha256": item["sha256"],
            }
            for item in candidates
        ],
    }
    if mirror is not None:
        head_ok, head_value = archive_services.wom_kit_project_update_git(
            mirror,
            ["rev-parse", "HEAD"],
        )
        if head_ok and re.fullmatch(r"[0-9a-fA-F]{40,64}", head_value):
            binding["mirror_head"] = head_value.lower()
        else:
            blockers.append("project_mirror_head_unavailable")
    plan_sha256 = _sha256_bytes(_canonical_json_bytes(binding))
    aggregate = archive_services.unique_preserve_order(blockers)
    result = {
        "ok": not aggregate,
        "state": (
            "ready"
            if not aggregate and candidates
            else "clean"
            if not aggregate
            else "blocked"
        ),
        "dry_run": True,
        "lifecycle_action": "project_bytecode_repair_plan",
        "summary": {
            "bytecode_file_count": len(candidates),
            "bytecode_total_bytes": sum(
                int(item["bytes"]) for item in candidates
            ),
            "pycache_directory_count": len(pycache_dirs),
            "plan_sha256": plan_sha256 if not aggregate else None,
            "source_files_modified": False,
            "derived_bytecode_only": True,
        },
        "blockers": aggregate,
        "warnings": (
            ["No runtime bytecode cleanup is needed."]
            if not aggregate and not candidates
            else []
        ),
        "would_change": (
            ["project runtime bytecode files (count only)"]
            if not aggregate and candidates
            else []
        ),
        "privacy_guards": {
            "project_absolute_path_echoed": False,
            "bytecode_filenames_echoed": False,
            "source_bytes_read": False,
            "source_files_written": False,
            "network_checked": False,
            "writes": False,
        },
    }
    private = {
        "root": root,
        "mirror": mirror,
        "source_root": source_root,
        "candidates": candidates,
        "pycache_dirs": pycache_dirs,
        "binding": binding,
        "plan_sha256": plan_sha256,
    }
    return result, private


def project_bytecode_repair_plan(
    inspection_root: Path | str,
    *,
    max_files: int = PROJECT_BYTECODE_REPAIR_MAX_FILES,
) -> dict[str, Any]:
    result, _private = _project_bytecode_plan_core(
        inspection_root,
        max_files=max_files,
    )
    return result


def project_bytecode_repair(
    inspection_root: Path | str,
    *,
    max_files: int,
    expected_plan_sha256: str | None,
    reviewed_by: str | None,
) -> dict[str, Any]:
    result, private = _project_bytecode_plan_core(
        inspection_root,
        max_files=max_files,
    )
    blockers = list(result["blockers"])
    expected = str(expected_plan_sha256 or "").strip().lower()
    reviewer = archive_services.safe_project_intake_actor_id(reviewed_by)
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        blockers.append("project_bytecode_expected_plan_sha256_invalid")
    elif expected != private["plan_sha256"]:
        blockers.append("project_bytecode_plan_changed")
    if reviewer is None:
        blockers.append("project_bytecode_reviewer_invalid")
    if not private["candidates"]:
        blockers.append("project_bytecode_nothing_to_repair")
    if blockers:
        return {
            **result,
            "ok": False,
            "state": "blocked",
            "dry_run": False,
            "approved": False,
            "lifecycle_action": "project_bytecode_repair",
            "blockers": archive_services.unique_preserve_order(blockers),
            "would_change": [],
            "files_written": [],
        }

    root: Path = private["root"]
    lock_root = root / ".zettel-kasten" / "locks"
    lock_root.mkdir(parents=True, exist_ok=True)
    # The generic mutation lock needs archive-internal path semantics, while
    # project repair may run above an archive. Use an adjacent project lock.
    lock_path = lock_root / "project-bytecode-repair.lock"
    with lock_path.open("a+b") as lock_handle:
        if lock_handle.seek(0, os.SEEK_END) == 0:
            lock_handle.write(b"\0")
            lock_handle.flush()
            os.fsync(lock_handle.fileno())
        lock_handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(lock_handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            fresh, fresh_private = _project_bytecode_plan_core(
                root,
                max_files=max_files,
            )
            if not fresh["ok"] or fresh_private["plan_sha256"] != expected:
                return {
                    **fresh,
                    "ok": False,
                    "state": "blocked",
                    "dry_run": False,
                    "approved": False,
                    "lifecycle_action": "project_bytecode_repair",
                    "blockers": archive_services.unique_preserve_order(
                        [*fresh["blockers"], "project_bytecode_plan_changed"]
                    ),
                    "would_change": [],
                    "files_written": [],
                }
            removed_count = 0
            for item in fresh_private["candidates"]:
                try:
                    current = item["path"].read_bytes()
                except OSError:
                    return {
                        **fresh,
                        "ok": False,
                        "state": "partial",
                        "dry_run": False,
                        "approved": True,
                        "lifecycle_action": "project_bytecode_repair",
                        "summary": {
                            **fresh["summary"],
                            "removed_count": removed_count,
                            "recovery": "rerun_fresh_plan",
                        },
                        "blockers": ["project_bytecode_changed_during_repair"],
                        "would_change": [],
                        "files_written": [],
                    }
                if (
                    len(current) != item["bytes"]
                    or _sha256_bytes(current) != item["sha256"]
                ):
                    return {
                        **fresh,
                        "ok": False,
                        "state": "partial",
                        "dry_run": False,
                        "approved": True,
                        "lifecycle_action": "project_bytecode_repair",
                        "summary": {
                            **fresh["summary"],
                            "removed_count": removed_count,
                            "recovery": "rerun_fresh_plan",
                        },
                        "blockers": ["project_bytecode_changed_during_repair"],
                        "would_change": [],
                        "files_written": [],
                    }
                item["path"].unlink()
                removed_count += 1
            removed_dir_count = 0
            for directory in sorted(
                fresh_private["pycache_dirs"],
                key=lambda path: len(path.parts),
                reverse=True,
            ):
                try:
                    directory.rmdir()
                    removed_dir_count += 1
                except OSError:
                    continue
            timestamp = _now()
            receipt_relative = (
                f"{PROJECT_BYTECODE_REPAIR_RECEIPTS_DIR}/{expected}.json"
            )
            receipt_path = root.joinpath(
                *Path(receipt_relative).parts
            )
            receipt_doc = {
                "schema": PROJECT_BYTECODE_REPAIR_RECEIPT_SCHEMA,
                "plan_sha256": expected,
                "mirror_head": fresh_private["binding"]["mirror_head"],
                "removed_file_count": removed_count,
                "removed_total_bytes": fresh["summary"][
                    "bytecode_total_bytes"
                ],
                "removed_empty_pycache_directory_count": removed_dir_count,
                "source_files_modified": False,
                "reviewed_by": reviewer,
                "created_at": timestamp,
            }
            if not receipt_path.exists():
                archive_services._write_bytes_create_if_absent(
                    receipt_path,
                    _canonical_json_bytes(receipt_doc),
                )
        finally:
            lock_handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(
                    lock_handle.fileno(),
                    msvcrt.LK_UNLCK,
                    1,
                )
            else:
                import fcntl

                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    return {
        **fresh,
        "ok": True,
        "state": "repaired",
        "dry_run": False,
        "approved": True,
        "lifecycle_action": "project_bytecode_repair",
        "summary": {
            **fresh["summary"],
            "removed_count": removed_count,
            "removed_empty_pycache_directory_count": removed_dir_count,
            "receipt_path": receipt_relative,
            "source_files_modified": False,
        },
        "blockers": [],
        "warnings": [],
        "would_change": [],
        "files_written": [receipt_relative],
        "privacy_guards": {
            **fresh["privacy_guards"],
            "writes": True,
        },
    }
