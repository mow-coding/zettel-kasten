"""Strict saved-view authority and approval-gated lifecycle workflows."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import archive_services


SAVED_VIEW_WRITE_REQUEST_SCHEMA = "wom-kit/saved-view-write-request/v0.1"
SAVED_VIEW_WRITE_RECEIPT_SCHEMA = "wom-kit/saved-view-write-receipt/v0.1"
SAVED_VIEW_REVERT_RECEIPT_SCHEMA = "wom-kit/saved-view-revert-receipt/v0.1"
SAVED_VIEW_REVERT_JOURNAL_SCHEMA = "wom-kit/saved-view-revert-journal/v0.1"
SAVED_VIEW_REQUEST_DIR = ".wom-scratch/private/saved-views"
SAVED_VIEW_RECEIPTS_DIR = "receipts/views"
SAVED_VIEW_REQUEST_MAX_BYTES = 64 * 1024
SAVED_VIEW_MAX_FILTERS = 8
SAVED_VIEW_NAME_MAX_CHARS = 200
SAVED_VIEW_FILTER_VALUE_MAX_CHARS = 500
SAVED_VIEW_ACTOR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._-]{0,199}$")
SAVED_VIEW_FILTER_KEY_RE = re.compile(r"^facets\.[a-z][a-z0-9_]{0,79}$")
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
WRITE_RECEIPT_PATH_RE = re.compile(
    r"^receipts/views/[0-9a-f]{20}\.[0-9a-f]{16}\.saved-view-write\.json$"
)
GENERATED_VIEW_PATH_RE = re.compile(r"^views/generated-[0-9a-f]{20}\.yml$")


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _safe_private_scalar(value: Any, *, max_chars: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if (
        not text
        or len(text) > max_chars
        or any(ord(character) < 32 for character in text)
        or archive_services.source_intake_secret_like(text)
        or archive_services.source_intake_has_provider_url(text)
        or archive_services.contains_forbidden_location_reference(text)
    ):
        return None
    return text


def _safe_actor(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not SAVED_VIEW_ACTOR_RE.fullmatch(text):
        return None
    if archive_services.source_intake_secret_like(text):
        return None
    return text


def _safe_archive_input(
    root: Path,
    raw_relative: str,
    *,
    required_prefix: str,
    suffix: str,
    blocker_codes: list[str],
) -> tuple[str | None, Path | None]:
    if not isinstance(raw_relative, str):
        blocker_codes.append("saved_view_input_path_invalid")
        return None, None
    relative = raw_relative.strip().replace("\\", "/")
    if (
        not relative
        or relative.startswith("/")
        or ":" in relative
        or not relative.startswith(required_prefix.rstrip("/") + "/")
        or not relative.endswith(suffix)
    ):
        blocker_codes.append("saved_view_input_path_invalid")
        return None, None
    try:
        path = archive_services.archive_internal_path(root, relative)
    except archive_services.ArchiveServiceError:
        blocker_codes.append("saved_view_input_path_unsafe")
        return None, None
    try:
        if path.is_symlink() or not path.is_file():
            blocker_codes.append("saved_view_input_file_missing_or_unsafe")
            return relative, None
        cursor = path.parent
        while cursor != root:
            if cursor.is_symlink():
                blocker_codes.append("saved_view_input_path_unsafe")
                return relative, None
            cursor = cursor.parent
    except (OSError, RuntimeError, ValueError):
        blocker_codes.append("saved_view_input_path_unsafe")
        return relative, None
    return relative, path


def _load_request(
    root: Path,
    request_path: str,
    blocker_codes: list[str],
) -> dict[str, Any] | None:
    _relative, path = _safe_archive_input(
        root,
        request_path,
        required_prefix=SAVED_VIEW_REQUEST_DIR,
        suffix=".json",
        blocker_codes=blocker_codes,
    )
    if path is None:
        return None
    try:
        raw = path.read_bytes()
    except OSError:
        blocker_codes.append("saved_view_request_unreadable")
        return None
    if len(raw) > SAVED_VIEW_REQUEST_MAX_BYTES:
        blocker_codes.append("saved_view_request_too_large")
        return None
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        blocker_codes.append("saved_view_request_invalid_json")
        return None
    if not isinstance(payload, dict):
        blocker_codes.append("saved_view_request_not_object")
        return None
    if set(payload) != {"schema", "view_id", "name", "filters"}:
        blocker_codes.append("saved_view_request_fields_invalid")
    if payload.get("schema") != SAVED_VIEW_WRITE_REQUEST_SCHEMA:
        blocker_codes.append("saved_view_request_schema_unsupported")

    view_id = str(payload.get("view_id") or "").strip()
    if not archive_services.SAVED_VIEW_ID_RE.fullmatch(view_id):
        blocker_codes.append("saved_view_request_id_invalid")
    name = _safe_private_scalar(
        payload.get("name"),
        max_chars=SAVED_VIEW_NAME_MAX_CHARS,
    )
    if name is None:
        blocker_codes.append("saved_view_request_name_invalid")
    raw_filters = payload.get("filters")
    filters: dict[str, str] = {}
    if not isinstance(raw_filters, dict) or not 1 <= len(raw_filters) <= SAVED_VIEW_MAX_FILTERS:
        blocker_codes.append("saved_view_request_filters_invalid")
    else:
        for raw_key, raw_value in raw_filters.items():
            key = str(raw_key).strip()
            if not SAVED_VIEW_FILTER_KEY_RE.fullmatch(key):
                blocker_codes.append("saved_view_request_filter_key_invalid")
                continue
            facet_key = key.split(".", 1)[1]
            role, _reason = archive_services.facet_role_for_key(facet_key)
            if role != "navigation":
                blocker_codes.append("saved_view_request_filter_axis_not_navigation")
                continue
            safe_value = _safe_private_scalar(
                raw_value,
                max_chars=SAVED_VIEW_FILTER_VALUE_MAX_CHARS,
            )
            if safe_value is None:
                blocker_codes.append("saved_view_request_filter_value_invalid")
                continue
            filters[key] = safe_value

    if blocker_codes:
        return None
    normalized = {
        "schema": SAVED_VIEW_WRITE_REQUEST_SCHEMA,
        "view_id": view_id,
        "name": name,
        "filters": {key: filters[key] for key in sorted(filters)},
    }
    return {
        "request": normalized,
        "request_sha256": _sha256_bytes(raw),
        "request_canonical_sha256": archive_services.sha256_json_value(normalized),
    }


def _render_view(request: dict[str, Any]) -> tuple[dict[str, Any], bytes]:
    document = {
        "id": request["view_id"],
        "name": request["name"],
        "for": "ai_context",
        "filters": request["filters"],
        "include": {
            "zettels": True,
            "originals": "references_only",
            "relations": True,
        },
        "sort": [{"field": "updated_at", "direction": "descending"}],
        "context_policy": {
            "max_zettels": 100,
            "include_large_media": "never_directly",
            "prefer_summaries": True,
        },
    }
    rendered = archive_services.dump_yaml(document).encode("utf-8")
    return document, rendered


def _paths(view_id: str, view_sha256: str) -> dict[str, str]:
    id_hash = hashlib.sha256(view_id.encode("utf-8")).hexdigest()
    view_hash = view_sha256.split(":", 1)[1]
    stem = f"{id_hash[:20]}.{view_hash[:16]}"
    return {
        "target": f"views/generated-{id_hash[:20]}.yml",
        "receipt": f"{SAVED_VIEW_RECEIPTS_DIR}/{stem}.saved-view-write.json",
        "revert_receipt": f"{SAVED_VIEW_RECEIPTS_DIR}/reverts/{stem}.saved-view-revert.json",
        "revert_journal": f"{SAVED_VIEW_RECEIPTS_DIR}/journals/{stem}.saved-view-revert-journal.json",
    }


def _load_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, None
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > SAVED_VIEW_REQUEST_MAX_BYTES:
            return None, "saved_view_evidence_unsafe"
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, "saved_view_evidence_unreadable"
    if not isinstance(payload, dict):
        return None, "saved_view_evidence_invalid"
    return payload, _sha256_bytes(raw)


def _receipt_matches(
    receipt: dict[str, Any],
    *,
    archive_id: str,
    paths: dict[str, str],
    request_info: dict[str, Any],
    view_sha256: str,
) -> bool:
    return (
        receipt.get("schema") == SAVED_VIEW_WRITE_RECEIPT_SCHEMA
        and receipt.get("lifecycle_action") == "saved_view_write"
        and receipt.get("archive_id") == archive_id
        and receipt.get("target_path") == paths["target"]
        and receipt.get("request_sha256") == request_info["request_sha256"]
        and receipt.get("request_canonical_sha256")
        == request_info["request_canonical_sha256"]
        and receipt.get("view_sha256") == view_sha256
        and receipt.get("view_id_sha256")
        == _sha256_bytes(request_info["request"]["view_id"].encode("utf-8"))
    )


def _view_match_count(root: Path, filters: dict[str, str]) -> int | None:
    db_path = root / archive_services.INDEX_RELATIVE_PATH
    if not db_path.is_file():
        return None
    normalized = {key.split(".", 1)[1]: value for key, value in filters.items()}
    conn = archive_services.connect_archive_index(db_path, row_factory=True)
    try:
        return archive_services.count_indexed_zets_for_facets(conn, normalized)
    finally:
        conn.close()


def _write_plan_core(root: Path, request_path: str) -> tuple[dict[str, Any], dict[str, Any]]:
    archive_id = archive_services.read_archive_id(root)
    blockers: list[str] = []
    request_info = _load_request(root, request_path, blockers)
    authority = archive_services.saved_view_authority_scan(root)
    blockers.extend(authority["issue_codes"])
    if request_info is None:
        private: dict[str, Any] = {}
        return _public_plan(
            archive_id=archive_id,
            action="blocked",
            authority=authority,
            paths={},
            request_info=None,
            view_sha256=None,
            match_count=None,
            blockers=blockers,
        ), private

    request = request_info["request"]
    _document, view_bytes = _render_view(request)
    view_sha256 = _sha256_bytes(view_bytes)
    paths = _paths(request["view_id"], view_sha256)
    target_path = archive_services.archive_internal_path(root, paths["target"])
    receipt_path = archive_services.archive_internal_path(root, paths["receipt"])
    receipt, _receipt_sha = _load_json_object(receipt_path)
    if receipt_path.exists() and receipt is None:
        blockers.append("saved_view_write_receipt_invalid")

    target_bytes: bytes | None = None
    if target_path.exists():
        try:
            if target_path.is_symlink() or not target_path.is_file():
                blockers.append("saved_view_target_unsafe")
            else:
                target_bytes = target_path.read_bytes()
        except OSError:
            blockers.append("saved_view_target_unreadable")
    target_matches = target_bytes == view_bytes if target_bytes is not None else False
    matching_definition = next(
        (item for item in authority["views"] if item.get("id") == request["view_id"]),
        None,
    )
    if matching_definition is not None and matching_definition.get("source_path") != paths["target"]:
        blockers.append("saved_view_id_already_exists")

    match_count = _view_match_count(root, request["filters"])
    if match_count is None:
        blockers.append("archive_index_missing")
    elif match_count < 1:
        blockers.append("saved_view_filters_match_zero_zets")

    action = "create"
    if target_bytes is not None and not target_matches:
        blockers.append("saved_view_target_collision")
    elif receipt is not None:
        if not target_matches or not _receipt_matches(
            receipt,
            archive_id=archive_id,
            paths=paths,
            request_info=request_info,
            view_sha256=view_sha256,
        ):
            blockers.append("saved_view_write_evidence_mismatch")
        else:
            action = "already_recorded"
    elif target_matches:
        action = "finalize_receipt"

    if blockers:
        action = "blocked"
    public = _public_plan(
        archive_id=archive_id,
        action=action,
        authority=authority,
        paths=paths,
        request_info=request_info,
        view_sha256=view_sha256,
        match_count=match_count,
        blockers=blockers,
    )
    private = {
        "root": root,
        "archive_id": archive_id,
        "request_info": request_info,
        "view_bytes": view_bytes,
        "view_sha256": view_sha256,
        "paths": paths,
        "action": action,
    }
    return public, private


def _public_plan(
    *,
    archive_id: str,
    action: str,
    authority: dict[str, Any],
    paths: dict[str, str],
    request_info: dict[str, Any] | None,
    view_sha256: str | None,
    match_count: int | None,
    blockers: list[str],
) -> dict[str, Any]:
    plan_basis = {
        "schema": "wom-kit/saved-view-write-plan/v0.1",
        "archive_id": archive_id,
        "action": action,
        "authority_sha256": authority["authority_sha256"],
        "request_sha256": request_info["request_sha256"] if request_info else None,
        "request_canonical_sha256": request_info["request_canonical_sha256"]
        if request_info
        else None,
        "view_sha256": view_sha256,
        "target_path": paths.get("target"),
        "receipt_path": paths.get("receipt"),
        "match_count": match_count,
    }
    plan_sha256 = archive_services.sha256_json_value(plan_basis)
    writable = action in {"create", "finalize_receipt"} and not blockers
    return {
        "ok": not blockers,
        "dry_run": True,
        "approved": False,
        "state": "blocked" if blockers else action,
        "lifecycle_action": "saved_view_write_plan",
        "archive_id": archive_id,
        "summary": {
            "action": action,
            "filter_count": len(request_info["request"]["filters"])
            if request_info
            else 0,
            "matching_zettel_count": match_count,
            "target_path": paths.get("target"),
            "receipt_path": paths.get("receipt"),
            "request_sha256": request_info["request_sha256"] if request_info else None,
            "view_sha256": view_sha256,
            "authority_sha256": authority["authority_sha256"],
            "plan_sha256": plan_sha256,
        },
        "authority": {
            "state": "valid" if authority["ok"] else "blocked",
            "file_count": authority["file_count"],
            "view_count": len(authority["views"]),
            "issue_codes": authority["issue_codes"],
        },
        "would_change": (
            [paths["target"], paths["receipt"]]
            if action == "create" and writable
            else [paths["receipt"]]
            if action == "finalize_receipt" and writable
            else []
        ),
        "privacy_guards": {
            "view_name_echoed": False,
            "facet_keys_echoed": False,
            "facet_values_echoed": False,
            "zettel_titles_echoed": False,
            "zettel_bodies_read": False,
            "absolute_local_paths_echoed": False,
            "provider_api_called": False,
            "writes": False,
        },
        "blockers": archive_services.unique_preserve_order(blockers),
        "warnings": [],
    }


class _SavedViewLock:
    def __init__(self, root: Path) -> None:
        lock_dir = archive_services.archive_internal_path(
            root,
            f"{SAVED_VIEW_RECEIPTS_DIR}/.locks",
        )
        lock_dir.mkdir(parents=True, exist_ok=True)
        self._path = lock_dir / "authority.lock"
        self._handle: Any = None

    def __enter__(self) -> "_SavedViewLock":
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
                    msvcrt.locking(self._handle.fileno(), msvcrt.LK_LOCK, 1)
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

                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()
        return False


def saved_view_write_plan(
    archive_root: Path | str,
    *,
    request_path: str,
) -> dict[str, Any]:
    root = archive_services.require_existing_archive_root(archive_root)
    public, _private = _write_plan_core(root, request_path)
    return public


def _write_receipt(
    private: dict[str, Any],
    *,
    reviewer: str,
    plan_sha256: str,
    action: str,
) -> None:
    request_info = private["request_info"]
    paths = private["paths"]
    receipt = {
        "schema": SAVED_VIEW_WRITE_RECEIPT_SCHEMA,
        "lifecycle_action": "saved_view_write",
        "archive_id": private["archive_id"],
        "action": action,
        "target_path": paths["target"],
        "receipt_path": paths["receipt"],
        "request_sha256": request_info["request_sha256"],
        "request_canonical_sha256": request_info["request_canonical_sha256"],
        "view_id_sha256": _sha256_bytes(
            request_info["request"]["view_id"].encode("utf-8")
        ),
        "view_sha256": private["view_sha256"],
        "plan_sha256": plan_sha256,
        "reviewed_by": reviewer,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "privacy": {
            "view_name_recorded": False,
            "facet_keys_recorded": False,
            "facet_values_recorded": False,
        },
    }
    receipt_path = archive_services.archive_internal_path(
        private["root"], paths["receipt"]
    )
    archive_services._write_bytes_create_if_absent(
        receipt_path,
        _canonical_json_bytes(receipt),
    )


def saved_view_write(
    archive_root: Path | str,
    *,
    request_path: str,
    expected_plan_sha256: str,
    reviewed_by: str | None,
    affirm_view_reviewed: bool,
) -> dict[str, Any]:
    return archive_services._compound_exact_human_approval_blocked(
        lifecycle_action="saved_view_write",
    )

    # Dormant legacy implementation retained for compatibility analysis.
    # It is not an approval authority.
    root = archive_services.require_existing_archive_root(archive_root)
    reviewer = _safe_actor(reviewed_by)
    initial, _private = _write_plan_core(root, request_path)
    extra_blockers: list[str] = []
    if not SHA256_RE.fullmatch(str(expected_plan_sha256 or "")):
        extra_blockers.append("saved_view_expected_plan_sha256_invalid")
    if reviewer is None:
        extra_blockers.append("saved_view_reviewer_invalid")
    if not affirm_view_reviewed:
        extra_blockers.append("saved_view_review_affirmation_required")
    if extra_blockers:
        return {
            **initial,
            "ok": False,
            "state": "blocked",
            "blockers": archive_services.unique_preserve_order(
                [*initial["blockers"], *extra_blockers]
            ),
        }
    if not initial["ok"] or initial["state"] == "already_recorded":
        return initial

    with _SavedViewLock(root):
        fresh, private = _write_plan_core(root, request_path)
        fresh_plan = fresh["summary"]["plan_sha256"]
        if not fresh["ok"] or fresh_plan != expected_plan_sha256:
            return {
                **fresh,
                "ok": False,
                "state": "blocked",
                "blockers": archive_services.unique_preserve_order(
                    [*fresh["blockers"], "saved_view_plan_changed"]
                ),
            }
        action = private["action"]
        target_path = archive_services.archive_internal_path(
            root, private["paths"]["target"]
        )
        if action == "create":
            archive_services._write_bytes_create_if_absent(
                target_path,
                private["view_bytes"],
            )
        _write_receipt(
            private,
            reviewer=reviewer,
            plan_sha256=expected_plan_sha256,
            action=action,
        )

    return {
        **fresh,
        "ok": True,
        "dry_run": False,
        "approved": True,
        "state": "created" if action == "create" else "receipt_finalized",
        "lifecycle_action": "saved_view_write",
        "would_change": [],
        "files_written": (
            [private["paths"]["target"], private["paths"]["receipt"]]
            if action == "create"
            else [private["paths"]["receipt"]]
        ),
        "privacy_guards": {**fresh["privacy_guards"], "writes": True},
        "blockers": [],
    }


def _load_write_receipt(
    root: Path,
    receipt_relative: str,
    blockers: list[str],
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    relative, path = _safe_archive_input(
        root,
        receipt_relative,
        required_prefix=SAVED_VIEW_RECEIPTS_DIR,
        suffix=".saved-view-write.json",
        blocker_codes=blockers,
    )
    if path is None:
        return None, None, relative
    payload, receipt_sha256 = _load_json_object(path)
    if payload is None or receipt_sha256 is None:
        blockers.append("saved_view_write_receipt_invalid")
        return None, None, relative
    required = {
        "schema",
        "lifecycle_action",
        "archive_id",
        "action",
        "target_path",
        "receipt_path",
        "request_sha256",
        "request_canonical_sha256",
        "view_id_sha256",
        "view_sha256",
        "plan_sha256",
        "reviewed_by",
        "created_at",
        "privacy",
    }
    if (
        set(payload) != required
        or payload.get("schema") != SAVED_VIEW_WRITE_RECEIPT_SCHEMA
        or payload.get("lifecycle_action") != "saved_view_write"
        or payload.get("archive_id") != archive_services.read_archive_id(root)
        or payload.get("action") not in {"create", "finalize_receipt"}
        or payload.get("receipt_path") != relative
        or not WRITE_RECEIPT_PATH_RE.fullmatch(str(relative or ""))
        or not GENERATED_VIEW_PATH_RE.fullmatch(
            str(payload.get("target_path") or "")
        )
        or any(
            not SHA256_RE.fullmatch(str(payload.get(field) or ""))
            for field in (
                "request_sha256",
                "request_canonical_sha256",
                "view_id_sha256",
                "view_sha256",
                "plan_sha256",
            )
        )
        or _safe_actor(payload.get("reviewed_by")) is None
        or not isinstance(payload.get("created_at"), str)
        or payload.get("privacy")
        != {
            "view_name_recorded": False,
            "facet_keys_recorded": False,
            "facet_values_recorded": False,
        }
    ):
        blockers.append("saved_view_write_receipt_invalid")
        return None, None, relative
    return payload, receipt_sha256, relative


def _revert_receipt_matches(
    document: dict[str, Any],
    *,
    archive_id: str,
    source_receipt: str,
    source_receipt_sha256: str,
    target_path: str,
    view_sha256: str,
) -> bool:
    return (
        set(document)
        == {
            "schema",
            "lifecycle_action",
            "archive_id",
            "source_receipt_path",
            "source_receipt_sha256",
            "target_path",
            "view_sha256",
            "revert_plan_sha256",
            "reviewed_by",
            "created_at",
        }
        and document.get("schema") == SAVED_VIEW_REVERT_RECEIPT_SCHEMA
        and document.get("lifecycle_action") == "saved_view_revert"
        and document.get("archive_id") == archive_id
        and document.get("source_receipt_path") == source_receipt
        and document.get("source_receipt_sha256") == source_receipt_sha256
        and document.get("target_path") == target_path
        and document.get("view_sha256") == view_sha256
        and SHA256_RE.fullmatch(str(document.get("revert_plan_sha256") or ""))
        is not None
        and _safe_actor(document.get("reviewed_by")) is not None
        and isinstance(document.get("created_at"), str)
    )


def _revert_journal_matches(
    document: dict[str, Any],
    *,
    archive_id: str,
    source_receipt: str,
    source_receipt_sha256: str,
    target_path: str,
    view_sha256: str,
    revert_receipt_path: str,
) -> bool:
    return (
        set(document)
        == {
            "schema",
            "archive_id",
            "source_receipt_path",
            "source_receipt_sha256",
            "target_path",
            "view_sha256",
            "revert_receipt_path",
            "created_at",
        }
        and document.get("schema") == SAVED_VIEW_REVERT_JOURNAL_SCHEMA
        and document.get("archive_id") == archive_id
        and document.get("source_receipt_path") == source_receipt
        and document.get("source_receipt_sha256") == source_receipt_sha256
        and document.get("target_path") == target_path
        and document.get("view_sha256") == view_sha256
        and document.get("revert_receipt_path") == revert_receipt_path
        and isinstance(document.get("created_at"), str)
    )


def _revert_plan_core(root: Path, receipt_relative: str) -> tuple[dict[str, Any], dict[str, Any]]:
    archive_id = archive_services.read_archive_id(root)
    blockers: list[str] = []
    receipt, receipt_sha256, normalized_receipt = _load_write_receipt(
        root, receipt_relative, blockers
    )
    authority = archive_services.saved_view_authority_scan(root)
    blockers.extend(authority["issue_codes"])
    if receipt is None or receipt_sha256 is None or normalized_receipt is None:
        return _public_revert_plan(
            archive_id=archive_id,
            action="blocked",
            authority=authority,
            receipt_sha256=receipt_sha256,
            target_path=None,
            revert_receipt=None,
            journal=None,
            blockers=blockers,
        ), {}

    view_id_hash = str(receipt["view_id_sha256"]).split(":", 1)[-1]
    view_hash = str(receipt["view_sha256"]).split(":", 1)[-1]
    stem = f"{view_id_hash[:20]}.{view_hash[:16]}"
    revert_receipt_relative = (
        f"{SAVED_VIEW_RECEIPTS_DIR}/reverts/{stem}.saved-view-revert.json"
    )
    journal_relative = (
        f"{SAVED_VIEW_RECEIPTS_DIR}/journals/{stem}.saved-view-revert-journal.json"
    )
    target_relative = str(receipt["target_path"])
    target_path = archive_services.archive_internal_path(root, target_relative)
    revert_path = archive_services.archive_internal_path(root, revert_receipt_relative)
    journal_path = archive_services.archive_internal_path(root, journal_relative)
    revert_doc, _revert_sha = _load_json_object(revert_path)
    journal_doc, _journal_sha = _load_json_object(journal_path)
    if revert_path.exists() and revert_doc is None:
        blockers.append("saved_view_revert_evidence_invalid")
    if journal_path.exists() and journal_doc is None:
        blockers.append("saved_view_revert_journal_invalid")
    journal_valid = (
        journal_doc is not None
        and _revert_journal_matches(
            journal_doc,
            archive_id=archive_id,
            source_receipt=normalized_receipt,
            source_receipt_sha256=receipt_sha256,
            target_path=target_relative,
            view_sha256=receipt["view_sha256"],
            revert_receipt_path=revert_receipt_relative,
        )
    )
    if journal_doc is not None and not journal_valid:
        blockers.append("saved_view_revert_journal_invalid")
    target_exists = target_path.exists()
    target_matches = False
    if target_exists:
        try:
            target_matches = (
                not target_path.is_symlink()
                and target_path.is_file()
                and _sha256_bytes(target_path.read_bytes()) == receipt["view_sha256"]
            )
        except OSError:
            blockers.append("saved_view_revert_target_unreadable")
    if target_exists and not target_matches:
        blockers.append("saved_view_revert_target_changed")

    action = "revert"
    if revert_doc is not None:
        if not _revert_receipt_matches(
            revert_doc,
            archive_id=archive_id,
            source_receipt=normalized_receipt,
            source_receipt_sha256=receipt_sha256,
            target_path=target_relative,
            view_sha256=receipt["view_sha256"],
        ) or target_exists:
            blockers.append("saved_view_revert_evidence_mismatch")
        else:
            action = (
                "finalize_journal_cleanup"
                if journal_doc is not None
                else "already_reverted"
            )
    elif journal_doc is not None:
        if not journal_valid:
            blockers.append("saved_view_revert_journal_invalid")
        else:
            action = "resume_revert" if target_exists else "finalize_revert_receipt"
    elif not target_exists:
        blockers.append("saved_view_revert_target_missing_without_evidence")

    if blockers:
        action = "blocked"
    public = _public_revert_plan(
        archive_id=archive_id,
        action=action,
        authority=authority,
        receipt_sha256=receipt_sha256,
        target_path=target_relative,
        revert_receipt=revert_receipt_relative,
        journal=journal_relative,
        blockers=blockers,
    )
    return public, {
        "root": root,
        "archive_id": archive_id,
        "action": action,
        "source_receipt": normalized_receipt,
        "source_receipt_sha256": receipt_sha256,
        "target_path": target_path,
        "target_relative": target_relative,
        "view_sha256": receipt["view_sha256"],
        "revert_receipt_path": revert_path,
        "revert_receipt_relative": revert_receipt_relative,
        "journal_path": journal_path,
        "journal_relative": journal_relative,
    }


def _public_revert_plan(
    *,
    archive_id: str,
    action: str,
    authority: dict[str, Any],
    receipt_sha256: str | None,
    target_path: str | None,
    revert_receipt: str | None,
    journal: str | None,
    blockers: list[str],
) -> dict[str, Any]:
    plan_basis = {
        "schema": "wom-kit/saved-view-revert-plan/v0.1",
        "archive_id": archive_id,
        "action": action,
        "authority_sha256": authority["authority_sha256"],
        "source_receipt_sha256": receipt_sha256,
        "target_path": target_path,
        "revert_receipt_path": revert_receipt,
        "journal_path": journal,
    }
    plan_sha256 = archive_services.sha256_json_value(plan_basis)
    writable = action in {
        "revert",
        "resume_revert",
        "finalize_revert_receipt",
        "finalize_journal_cleanup",
    }
    would_change_by_action = {
        "revert": [target_path, revert_receipt, journal],
        "resume_revert": [target_path, revert_receipt, journal],
        "finalize_revert_receipt": [revert_receipt, journal],
        "finalize_journal_cleanup": [journal],
    }
    return {
        "ok": not blockers,
        "dry_run": True,
        "approved": False,
        "state": "blocked" if blockers else action,
        "lifecycle_action": "saved_view_revert_plan",
        "archive_id": archive_id,
        "summary": {
            "action": action,
            "source_receipt_sha256": receipt_sha256,
            "target_path": target_path,
            "revert_receipt_path": revert_receipt,
            "journal_path": journal,
            "authority_sha256": authority["authority_sha256"],
            "plan_sha256": plan_sha256,
        },
        "would_change": [
            path
            for path in would_change_by_action.get(action, [])
            if path
        ] if writable and not blockers else [],
        "privacy_guards": {
            "view_name_echoed": False,
            "facet_keys_echoed": False,
            "facet_values_echoed": False,
            "zettel_bodies_read": False,
            "provider_api_called": False,
            "writes": False,
        },
        "blockers": archive_services.unique_preserve_order(blockers),
        "warnings": [],
    }


def saved_view_revert_plan(
    archive_root: Path | str,
    *,
    receipt_path: str,
) -> dict[str, Any]:
    root = archive_services.require_existing_archive_root(archive_root)
    public, _private = _revert_plan_core(root, receipt_path)
    return public


def saved_view_revert(
    archive_root: Path | str,
    *,
    receipt_path: str,
    expected_plan_sha256: str,
    reviewed_by: str | None,
) -> dict[str, Any]:
    return archive_services._compound_exact_human_approval_blocked(
        lifecycle_action="saved_view_revert",
    )

    # Dormant legacy implementation retained for compatibility analysis.
    # It is not an approval authority.
    root = archive_services.require_existing_archive_root(archive_root)
    reviewer = _safe_actor(reviewed_by)
    initial, _private = _revert_plan_core(root, receipt_path)
    extra: list[str] = []
    if not SHA256_RE.fullmatch(str(expected_plan_sha256 or "")):
        extra.append("saved_view_expected_plan_sha256_invalid")
    if reviewer is None:
        extra.append("saved_view_reviewer_invalid")
    if extra:
        return {
            **initial,
            "ok": False,
            "state": "blocked",
            "blockers": archive_services.unique_preserve_order(
                [*initial["blockers"], *extra]
            ),
        }
    if not initial["ok"] or initial["state"] == "already_reverted":
        return initial

    with _SavedViewLock(root):
        fresh, private = _revert_plan_core(root, receipt_path)
        if (
            not fresh["ok"]
            or fresh["summary"]["plan_sha256"] != expected_plan_sha256
        ):
            return {
                **fresh,
                "ok": False,
                "state": "blocked",
                "blockers": archive_services.unique_preserve_order(
                    [*fresh["blockers"], "saved_view_plan_changed"]
                ),
            }
        action = private["action"]
        if action == "revert":
            journal = {
                "schema": SAVED_VIEW_REVERT_JOURNAL_SCHEMA,
                "archive_id": private["archive_id"],
                "source_receipt_path": private["source_receipt"],
                "source_receipt_sha256": private["source_receipt_sha256"],
                "target_path": private["target_relative"],
                "view_sha256": private["view_sha256"],
                "revert_receipt_path": private["revert_receipt_relative"],
                "created_at": datetime.now(timezone.utc)
                .replace(microsecond=0)
                .isoformat(),
            }
            archive_services._write_bytes_create_if_absent(
                private["journal_path"], _canonical_json_bytes(journal)
            )
        if action in {"revert", "resume_revert"}:
            private["target_path"].unlink()
            archive_services.fsync_directory(private["target_path"].parent)
        if action != "finalize_journal_cleanup":
            revert_receipt = {
                "schema": SAVED_VIEW_REVERT_RECEIPT_SCHEMA,
                "lifecycle_action": "saved_view_revert",
                "archive_id": private["archive_id"],
                "source_receipt_path": private["source_receipt"],
                "source_receipt_sha256": private["source_receipt_sha256"],
                "target_path": private["target_relative"],
                "view_sha256": private["view_sha256"],
                "revert_plan_sha256": expected_plan_sha256,
                "reviewed_by": reviewer,
                "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            }
            archive_services._write_bytes_create_if_absent(
                private["revert_receipt_path"],
                _canonical_json_bytes(revert_receipt),
            )
        if private["journal_path"].exists():
            private["journal_path"].unlink()
            archive_services.fsync_directory(private["journal_path"].parent)

    return {
        **fresh,
        "ok": True,
        "dry_run": False,
        "approved": True,
        "state": (
            "journal_cleanup_finalized"
            if action == "finalize_journal_cleanup"
            else "reverted"
        ),
        "lifecycle_action": "saved_view_revert",
        "would_change": [],
        "files_written": (
            []
            if action == "finalize_journal_cleanup"
            else [private["revert_receipt_relative"]]
        ),
        "files_removed": (
            [private["target_relative"]]
            if action in {"revert", "resume_revert"}
            else [private["journal_relative"]]
            if action == "finalize_journal_cleanup"
            else []
        ),
        "privacy_guards": {**fresh["privacy_guards"], "writes": True},
        "blockers": [],
    }
