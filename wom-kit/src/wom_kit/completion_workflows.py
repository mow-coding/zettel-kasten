"""Integrated Letters 098-111 completion workflows.

This module keeps the newer locator, normalization, relation-review, and bulk
intake surfaces cohesive while reusing the mature archive primitives in
``archive_services``. Public results never echo private locator values, local
absolute paths, zettel bodies, or exception text.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import archive_services


EXTERNAL_LOCATOR_SCHEMA = "wom-kit/external-locator-record/v0.1"
EXTERNAL_LOCATOR_RECEIPT_SCHEMA = "wom-kit/external-locator-receipt/v0.1"
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
    "wom-kit/markup-reference-binding-manifest/v0.1"
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
_STRUCTURAL_MARKUP_TAGS = frozenset({"article", "div", "p", "section"})
_REFERENCE_MARKUP_TAGS = frozenset(
    {"file", "media", "mention", "synced-ref", "synced_ref"}
)
MARKUP_REFERENCE_BINDING_KINDS = (
    "external_locator",
    "zettel_edge",
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


def _safe_zettel_id(value: str | None) -> str | None:
    text = str(value or "").strip()
    if archive_services.ZETTEL_EDGE_ZETTEL_ID_RE.fullmatch(text):
        return text
    return None


def _record_relative(zettel_id: str) -> str:
    return f"{EXTERNAL_LOCATOR_DIR}/{zettel_id}.json"


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
        lock_dir = archive_services.archive_internal_path(
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
    path = archive_services.archive_internal_path(root, _record_relative(zettel_id))
    if not path.exists():
        return None, None, None
    if not path.is_file() or path.is_symlink():
        return None, None, "external_locator_record_unsafe"
    try:
        raw = path.read_bytes()
        loaded = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, None, "external_locator_record_unreadable"
    if (
        not isinstance(loaded, dict)
        or loaded.get("schema") != EXTERNAL_LOCATOR_SCHEMA
        or loaded.get("zettel_id") != zettel_id
        or not isinstance(loaded.get("locators"), list)
    ):
        return None, None, "external_locator_record_invalid"
    return loaded, raw, None


def _locator_plan_core(
    archive_root: Path | str,
    *,
    zettel_id: str | None,
    locator_type: str,
    locator_ref: str | None,
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
    locator_id = (
        f"locator:sha256:{locator_sha256}"
        if locator_sha256 is not None
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
    current_locators = (
        current_record.get("locators", [])
        if isinstance(current_record, dict)
        else []
    )
    if locator_id and any(
        isinstance(item, dict) and item.get("locator_id") == locator_id
        for item in current_locators
    ):
        blockers.append("external_locator_already_recorded")

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
        "current_record_sha256": current_sha256,
        "action": "add_locator",
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
            "locator_id": locator_id,
            "record_path": record_relative if safe_id else None,
            "current_locator_count": len(current_locators),
            "record_exists": current_record is not None,
            "current_record_sha256": current_sha256,
            "plan_sha256": plan_sha256 if not blockers else None,
        },
        "data": {
            "record_schema": EXTERNAL_LOCATOR_SCHEMA,
            "receipt_schema": EXTERNAL_LOCATOR_RECEIPT_SCHEMA,
            "locator_types": list(EXTERNAL_LOCATOR_TYPES),
            "multiple_locators_supported": True,
            "provider_neutral": True,
            "global_recoverability_claimed": False,
        },
        "blockers": blockers,
        "warnings": [],
        "would_change": [record_relative] if not blockers else [],
        "privacy_guards": {
            "locator_ref_echoed": False,
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
        "locator_id": locator_id,
        "locator_sha256": locator_sha256,
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
) -> dict[str, Any]:
    result, _private = _locator_plan_core(
        archive_root,
        zettel_id=zettel_id,
        locator_type=locator_type,
        locator_ref=locator_ref,
    )
    return result


def external_locator_record(
    archive_root: Path | str,
    *,
    zettel_id: str | None,
    locator_type: str,
    locator_ref: str | None,
    expected_plan_sha256: str | None,
    reviewed_by: str | None,
) -> dict[str, Any]:
    result, private = _locator_plan_core(
        archive_root,
        zettel_id=zettel_id,
        locator_type=locator_type,
        locator_ref=locator_ref,
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
        locators.append(
            {
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
        )
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
            snapshot_path = archive_services.archive_internal_path(
                root,
                snapshot_relative,
            )
        receipt_relative = _receipt_relative(
            "record",
            safe_id,
            timestamp,
            after_sha256,
        )
        receipt_path = archive_services.archive_internal_path(
            root,
            receipt_relative,
        )
        record_path = archive_services.archive_internal_path(
            root,
            fresh_private["record_relative"],
        )
        receipt = {
            "schema": EXTERNAL_LOCATOR_RECEIPT_SCHEMA,
            "action": "add_locator",
            "archive_id": archive_services.read_archive_id(root),
            "zettel_id": safe_id,
            "locator_id": fresh_private["locator_id"],
            "locator_type": fresh_private["normalized_type"],
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
        created: list[Path] = []
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
                created.append(snapshot_path)
            archive_services._write_bytes_create_if_absent(
                receipt_path,
                _canonical_json_bytes(receipt),
            )
            created.append(receipt_path)
            archive_services.write_bytes_atomic(record_path, record_bytes)
            archive_services.fsync_directory(record_path.parent)
        except OSError:
            for path in reversed(created):
                path.unlink(missing_ok=True)
            return {
                **fresh,
                "ok": False,
                "state": "blocked",
                "dry_run": False,
                "approved": False,
                "lifecycle_action": "external_locator_record",
                "blockers": ["external_locator_write_failed"],
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
        }
        for item in locators
        if isinstance(item, dict)
    ]
    state = (
        "blocked"
        if blockers
        else "unresolved"
        if not projections
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
            "active_locator_count": sum(
                1 for item in projections if item["status"] == "active"
            ),
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
            else []
        ),
        "would_change": [],
        "privacy_guards": {
            "locator_ref_echoed": False,
            "provider_url_echoed": False,
            "local_absolute_path_echoed": False,
            "zettel_body_echoed": False,
            "writes": False,
        },
    }


def _external_locator_revert_plan_core(
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
        blockers.append("external_locator_receipt_path_invalid")
    else:
        try:
            receipt_bytes = receipt_path.read_bytes()
            loaded = json.loads(receipt_bytes.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            loaded = None
        if (
            not isinstance(loaded, dict)
            or loaded.get("schema") != EXTERNAL_LOCATOR_RECEIPT_SCHEMA
            or loaded.get("archive_id") != archive_id
        ):
            blockers.append("external_locator_receipt_invalid")
        else:
            receipt_doc = loaded

    record_path: Path | None = None
    before_bytes: bytes | None = None
    current_sha256: str | None = None
    before_sha256: str | None = None
    after_sha256: str | None = None
    zettel_id: str | None = None
    if receipt_doc is not None:
        zettel_id = _safe_zettel_id(receipt_doc.get("zettel_id"))
        before_sha256 = receipt_doc.get("before_record_sha256")
        after_sha256 = str(receipt_doc.get("after_record_sha256") or "")
        if (
            zettel_id is None
            or (
                before_sha256 is not None
                and not re.fullmatch(r"[0-9a-f]{64}", str(before_sha256))
            )
            or not re.fullmatch(r"[0-9a-f]{64}", after_sha256)
        ):
            blockers.append("external_locator_receipt_invalid")
        try:
            record_path = archive_services.archive_internal_path(
                root,
                str(receipt_doc.get("record_path") or ""),
            )
        except archive_services.ArchiveServiceError:
            blockers.append("external_locator_receipt_invalid")
        if record_path is not None:
            try:
                current_bytes = record_path.read_bytes()
                current_sha256 = _sha256_bytes(current_bytes)
            except OSError:
                current_sha256 = None
            if current_sha256 != after_sha256:
                blockers.append("external_locator_record_changed")
        snapshot_value = receipt_doc.get("before_snapshot_path")
        if before_sha256 is None:
            if snapshot_value is not None:
                blockers.append("external_locator_receipt_invalid")
        elif isinstance(snapshot_value, str):
            try:
                snapshot_path = archive_services.archive_internal_path(
                    root,
                    snapshot_value,
                )
                before_bytes = snapshot_path.read_bytes()
            except (archive_services.ArchiveServiceError, OSError):
                blockers.append("external_locator_snapshot_missing")
            if (
                before_bytes is not None
                and _sha256_bytes(before_bytes) != before_sha256
            ):
                blockers.append("external_locator_snapshot_mismatch")
        else:
            blockers.append("external_locator_snapshot_missing")

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
            [str(receipt_doc.get("record_path"))]
            if not aggregate and receipt_doc is not None
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
        if fresh_private["before_bytes"] is None:
            fresh_private["record_path"].unlink()
            restore_action = "removed_new_record"
        else:
            archive_services.write_bytes_atomic(
                fresh_private["record_path"],
                fresh_private["before_bytes"],
            )
            restore_action = "restored_previous_record"
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
        revert_receipt_path = archive_services.archive_internal_path(
            root,
            revert_receipt_relative,
        )
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
        "lifecycle_action": "external_locator_revert",
        "summary": {
            **fresh["summary"],
            "restore_action": restore_action,
            "receipt_path": revert_receipt_relative,
        },
        "blockers": [],
        "would_change": [],
        "files_written": [
            str(fresh_private["receipt_doc"]["record_path"]),
            revert_receipt_relative,
        ],
        "privacy_guards": {
            **fresh["privacy_guards"],
            "writes": True,
        },
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
                "markup": "file_media_mention_synced_ref",
                "action": "require_reviewed_edge_or_locator_binding",
                "silent_deletion_allowed": False,
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


def _markup_reference_bindings(
    root: Path,
    *,
    binding_manifest: Path | str | None,
) -> tuple[
    dict[str, dict[str, dict[str, str]]],
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
        loaded = json.loads(raw.decode("utf-8"))
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ):
        return {}, None, ["markup_binding_manifest_invalid"]
    archive_id = archive_services.read_archive_id(root)
    if (
        not isinstance(loaded, dict)
        or loaded.get("schema")
        != MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA
        or loaded.get("archive_id") != archive_id
        or not isinstance(loaded.get("bindings"), list)
        or len(loaded["bindings"]) > MARKUP_NORMALIZATION_MAX_CHANGES
    ):
        return {}, None, ["markup_binding_manifest_invalid"]

    blockers: list[str] = []
    bindings: dict[str, dict[str, dict[str, str]]] = {}
    for item in loaded["bindings"]:
        if not isinstance(item, dict):
            blockers.append("markup_binding_manifest_invalid")
            continue
        zettel_id = _safe_zettel_id(item.get("zettel_id"))
        tag_sha256 = str(item.get("tag_sha256") or "").strip().lower()
        binding_kind = str(item.get("binding_kind") or "").strip().lower()
        binding_id = str(item.get("binding_id") or "").strip()
        if (
            zettel_id is None
            or not re.fullmatch(r"[0-9a-f]{64}", tag_sha256)
            or binding_kind not in MARKUP_REFERENCE_BINDING_KINDS
        ):
            blockers.append("markup_binding_manifest_invalid")
            continue
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
        else:
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
        if replacement is None:
            continue
        zettel_bindings = bindings.setdefault(zettel_id, {})
        if tag_sha256 in zettel_bindings:
            blockers.append("markup_binding_duplicate")
            continue
        zettel_bindings[tag_sha256] = {
            "binding_kind": binding_kind,
            "binding_id": binding_id,
            "replacement": replacement,
        }
    return (
        bindings,
        _sha256_bytes(raw),
        archive_services.unique_preserve_order(blockers),
    )


def _normalize_markup_body(
    body: str,
    *,
    bindings: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    active_bindings = bindings or {}
    counts = {
        "empty_block": 0,
        "span": 0,
        "structural_container": 0,
        "reference_binding_applied": 0,
        "reference_binding_required": 0,
        "unknown_semantic_tag": 0,
    }
    normalized, empty_count = re.subn(
        r"(?im)^[ \t]*<\s*empty-block\s*/\s*>[ \t]*(?:\r?\n|$)",
        "",
        body,
    )
    counts["empty_block"] = empty_count

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
        r"(?is)<\s*/?\s*(?:article|div|section|p)(?:\s+[^<>]*?)?\s*>",
        structural_replacement,
        normalized,
    )

    reference_tag_digests: list[dict[str, str]] = []
    used_binding_sha256s: set[str] = set()

    def reference_replacement(match: re.Match[str]) -> str:
        name = match.group("name").casefold()
        if name not in _REFERENCE_MARKUP_TAGS:
            return match.group(0)
        tag_sha256 = _sha256_bytes(match.group(0).encode("utf-8"))
        reference_tag_digests.append(
            {
                "tag_name": name.replace("_", "-"),
                "tag_sha256": tag_sha256,
            }
        )
        binding = active_bindings.get(tag_sha256)
        if (
            binding is None
            or match.group("closing")
            or not match.group("self")
        ):
            return match.group(0)
        used_binding_sha256s.add(tag_sha256)
        counts["reference_binding_applied"] += 1
        return binding["replacement"]

    normalized = _MARKUP_TAG_RE.sub(reference_replacement, normalized)
    remaining = list(_MARKUP_TAG_RE.finditer(normalized))
    unknown_names: set[str] = set()
    reference_names: set[str] = set()
    for match in remaining:
        name = match.group("name").casefold()
        if name in _MARKDOWN_COMPATIBLE_HTML_TAGS:
            continue
        if name in _REFERENCE_MARKUP_TAGS:
            counts["reference_binding_required"] += 1
            reference_names.add(name.replace("_", "-"))
            continue
        if name == "empty-block" or name == "span" or name in _STRUCTURAL_MARKUP_TAGS:
            unknown_names.add(name)
            continue
        counts["unknown_semantic_tag"] += 1
        unknown_names.add(name)

    blocker_codes: list[str] = []
    if reference_names:
        blocker_codes.append("markup_reference_binding_required")
    if unknown_names:
        blocker_codes.append("unknown_semantic_markup")
    return {
        "normalized_body": normalized,
        "changed": normalized != body,
        "counts": counts,
        "reference_tag_names": sorted(reference_names),
        "reference_tag_digests": sorted(
            reference_tag_digests,
            key=lambda item: (item["tag_name"], item["tag_sha256"]),
        ),
        "used_binding_sha256s": sorted(used_binding_sha256s),
        "unknown_tag_names": sorted(unknown_names),
        "blocker_codes": blocker_codes,
    }


def _markup_zettel_analysis(
    root: Path,
    path: Path,
    *,
    policy: str,
    bindings_by_zettel: (
        dict[str, dict[str, dict[str, str]]] | None
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
    normalized = _normalize_markup_body(
        body,
        bindings=(bindings_by_zettel or {}).get(str(zettel_id), {}),
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
        "path": archive_services.archive_relative_path(path, root),
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
        "used_binding_sha256s": normalized["used_binding_sha256s"],
    }
    return public, private


def _markup_plan_core(
    archive_root: Path | str,
    *,
    policy: str,
    max_items: int,
    max_changes: int,
    binding_manifest: Path | str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = archive_services.require_existing_archive_root(archive_root)
    archive_id = archive_services.read_archive_id(root)
    normalized_policy = str(policy or "").strip().lower()
    blockers: list[str] = []
    if normalized_policy not in MARKUP_NORMALIZATION_POLICIES:
        blockers.append("markup_policy_invalid")
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
    used_binding_keys: set[tuple[str, str]] = set()
    if not blockers:
        for path in all_paths:
            public, private = _markup_zettel_analysis(
                root,
                path,
                policy=normalized_policy,
                bindings_by_zettel=bindings,
            )
            if (
                sum(int(value) for value in public.get("counts", {}).values())
                or public["blocker_codes"]
            ):
                public_items.append(public)
            if private is not None:
                used_binding_keys.update(
                    (str(private["zettel_id"]), tag_sha256)
                    for tag_sha256 in private["used_binding_sha256s"]
                )
            if private is not None and private["state"] == "ready":
                private_items.append(private)
        configured_binding_keys = {
            (zettel_id, tag_sha256)
            for zettel_id, zettel_bindings in bindings.items()
            for tag_sha256 in zettel_bindings
        }
        if configured_binding_keys - used_binding_keys:
            blockers.append("markup_binding_unused")
        if len(private_items) > change_limit:
            blockers.append("markup_change_bound_exceeded")
        for item in public_items:
            blockers.extend(item["blocker_codes"])

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
        "max_items": item_limit,
        "max_changes": change_limit,
        "binding_manifest_sha256": binding_manifest_sha256,
        "items": plan_items,
    }
    plan_sha256 = _sha256_bytes(_canonical_json_bytes(plan_document))
    aggregate_blockers = archive_services.unique_preserve_order(blockers)
    summary = {
        "policy": (
            normalized_policy
            if normalized_policy in MARKUP_NORMALIZATION_POLICIES
            else None
        ),
        "scanned_zettel_count": len(all_paths),
        "candidate_zettel_count": len(public_items),
        "ready_change_count": len(private_items),
        "blocked_zettel_count": sum(
            1 for item in public_items if item["state"] == "blocked"
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
        "state": "ready" if not aggregate_blockers else "blocked",
        "dry_run": True,
        "lifecycle_action": "markup_normalization_plan",
        "archive_id": archive_id,
        "summary": summary,
        "items": plan_items,
        "style_guide": markup_style_guide(),
        "blockers": aggregate_blockers,
        "warnings": (
            [
                "Preserve policy records the inventory and intentionally leaves source markup unchanged."
            ]
            if normalized_policy == "preserve"
            else []
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
    }
    return result, private


def markup_normalization_plan(
    archive_root: Path | str,
    *,
    policy: str = "normalize",
    max_items: int = MARKUP_NORMALIZATION_MAX_ITEMS,
    max_changes: int = MARKUP_NORMALIZATION_MAX_CHANGES,
    binding_manifest: Path | str | None = None,
) -> dict[str, Any]:
    result, _private = _markup_plan_core(
        archive_root,
        policy=policy,
        max_items=max_items,
        max_changes=max_changes,
        binding_manifest=binding_manifest,
    )
    return result


def markup_normalization_apply(
    archive_root: Path | str,
    *,
    policy: str,
    max_items: int,
    max_changes: int,
    binding_manifest: Path | str | None = None,
    expected_plan_sha256: str | None,
    reviewed_by: str | None,
) -> dict[str, Any]:
    result, private = _markup_plan_core(
        archive_root,
        policy=policy,
        max_items=max_items,
        max_changes=max_changes,
        binding_manifest=binding_manifest,
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
