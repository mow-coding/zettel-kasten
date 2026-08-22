"""Receipt-driven, content-free planning for local Zettel-Objet recovery.

This module is deliberately read-only.  It turns one already-completed Objet
capture receipt into a complete target classification and, only where a
canonical zettel preserves the same source page identifier uniquely, an
``ExactOperationManifest v1`` approval candidate.  Original filenames, source
paths, page ids, page titles, and provider locators never leave this boundary.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from . import archive_services, completion_workflows
from .exact_operation_manifest import (
    ExactFieldEffect,
    ExactOperationItem,
    ExactOperationManifest,
    hash_field_value,
)


RECOVERY_SCHEMA = "wom-kit/zettel-objet-link-recovery-plan/v0.1"
MAX_RECEIPT_BYTES = 64 * 1024 * 1024
MAX_RECEIPT_ITEMS = 10_000
_UUID_TOKEN_RE = re.compile(
    r"(?i)(?<![0-9a-f])"
    r"[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?"
    r"[0-9a-f]{4}-?[0-9a-f]{12}(?![0-9a-f])"
)
_SUCCESS_ACTIONS = frozenset(
    {"captured", "repair_appended", "re_materialized", "skip_already_present"}
)


class _DuplicateKey(ValueError):
    pass


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey(key)
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> Any:
    raise ValueError(value)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")


def _sha(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _normalize_source_id(value: Any) -> str | None:
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return None
    text = str(value).strip()
    match = _UUID_TOKEN_RE.fullmatch(text)
    if match is None:
        return None
    return match.group(0).replace("-", "").lower()


def _source_ids_in_text(value: Any) -> set[str]:
    if not isinstance(value, str):
        return set()
    return {
        match.group(0).replace("-", "").lower()
        for match in _UUID_TOKEN_RE.finditer(value)
    }


def _frontmatter_source_ids(value: Any, *, key: str | None = None) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for child_key, child in value.items():
            found.update(
                _frontmatter_source_ids(child, key=str(child_key))
            )
        return found
    if isinstance(value, list):
        for child in value:
            found.update(_frontmatter_source_ids(child, key=key))
        return found
    if key is None:
        return found
    normalized_key = archive_services.notion_source_map_normalized_key(key)
    source_family = archive_services.notion_source_map_ref_family_for_key(key)
    if source_family == "page_refs" or normalized_key in {
        "source_id",
        "source_page_id",
        "notion_page_id",
        "external_id",
    }:
        normalized = _normalize_source_id(value)
        if normalized is not None:
            found.add(normalized)
    return found


def _normalize_title(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(
        unicodedata.normalize("NFKC", html.unescape(value)).split()
    ).casefold()
    return normalized or None


def _receipt_filename_title(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    stem = PurePosixPath(value).stem
    stem = re.sub(r"(?i)[ _-][0-9a-f]{32}$", "", stem)
    return _normalize_title(stem)


def _read_capture_receipt(
    root: Path,
    receipt_relative: str,
    *,
    archive_id: str,
) -> tuple[bytes, dict[str, Any]]:
    try:
        normalized = archive_services.normalize_archive_relative_path(
            receipt_relative
        )
    except archive_services.ArchivePathError as exc:
        raise archive_services.ArchiveServiceError(
            "zettel_objet_link_recovery_receipt_unsafe"
        ) from exc
    if not re.fullmatch(
        r"receipts/objet-capture/[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}\.json",
        normalized,
    ):
        raise archive_services.ArchiveServiceError(
            "zettel_objet_link_recovery_receipt_unsafe"
        )
    if archive_services.objet_capture_path_chain_blockers(root, normalized):
        raise archive_services.ArchiveServiceError(
            "zettel_objet_link_recovery_receipt_unsafe"
        )
    path = archive_services.resolve_archive_relative_path(root, normalized)
    raw, reason = archive_services._bounded_stable_regular_file_read(
        path,
        max_bytes=MAX_RECEIPT_BYTES,
    )
    if raw is None or reason is not None:
        raise archive_services.ArchiveServiceError(
            "zettel_objet_link_recovery_receipt_unreadable"
        )
    try:
        document = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_nonfinite,
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise archive_services.ArchiveServiceError(
            "zettel_objet_link_recovery_receipt_invalid"
        ) from exc
    if not isinstance(document, dict) or not archive_services._staged_cleanup_valid_objet_receipt_envelope(
        document,
        filename=path.name,
        archive_id=archive_id,
    ):
        raise archive_services.ArchiveServiceError(
            "zettel_objet_link_recovery_receipt_invalid"
        )
    items = document.get("items")
    if (
        not isinstance(items, list)
        or not items
        or len(items) > MAX_RECEIPT_ITEMS
    ):
        raise archive_services.ArchiveServiceError(
            "zettel_objet_link_recovery_receipt_invalid"
        )
    return raw, document


def _canonical_index(
    root: Path,
    *,
    progress_callback: Callable[[str, str, int | None, int | None], None]
    | None = None,
) -> tuple[list[dict[str, Any]], int]:
    targets: list[dict[str, Any]] = []
    unreadable = 0
    path_entries = archive_services.zet_catalog_paths(root, "canonical")
    total = len(path_entries)
    if progress_callback is not None:
        progress_callback("canonical-index", "start", 0, total)
    for ordinal, (path, _status) in enumerate(path_entries, start=1):
        inspection = archive_services.inspect_zettel_frontmatter_boundary(path)
        frontmatter = inspection.get("frontmatter")
        if (
            inspection.get("metadata_readable") is not True
            or not isinstance(frontmatter, dict)
            or frontmatter.get("status") != "canonical"
            or not isinstance(frontmatter.get("id"), str)
        ):
            unreadable += 1
            continue
        targets.append(
            {
                "id": frontmatter["id"],
                "path": archive_services.archive_relative_path(path, root),
                "source_ids": _frontmatter_source_ids(frontmatter),
                "title": _normalize_title(frontmatter.get("title")),
                "assets": frontmatter.get("assets"),
            }
        )
        if progress_callback is not None and (
            ordinal == 1 or ordinal == total or ordinal % 250 == 0
        ):
            progress_callback("canonical-index", "scanned", ordinal, total)
    if progress_callback is not None:
        progress_callback("canonical-index", "done", total, total)
    return targets, unreadable


def zettel_objet_link_recovery_plan(
    archive_root: Path | str,
    *,
    capture_receipt: str,
    role: str = "source_document",
    dry_run: bool = True,
    max_items: int = MAX_RECEIPT_ITEMS,
    progress_callback: Callable[[str, str, int | None, int | None], None]
    | None = None,
) -> dict[str, Any]:
    """Classify every captured Objet without reading object bytes or writing."""

    root = archive_services.require_existing_archive_root(archive_root)
    archive_id = archive_services.read_archive_id(root)
    blockers: list[str] = []
    warnings: list[str] = []
    if not dry_run:
        blockers.append("zettel_objet_link_recovery_dry_run_required")
    requested_max = int(max_items)
    effective_max = max(1, min(requested_max, MAX_RECEIPT_ITEMS))
    if requested_max != effective_max:
        blockers.append("zettel_objet_link_recovery_max_items_out_of_range")
    normalized_role = str(role or "").strip().lower().replace("-", "_")
    if completion_workflows.ZETTEL_OBJET_ROLE_RE.fullmatch(normalized_role) is None:
        blockers.append("zettel_objet_link_recovery_role_invalid")

    try:
        if progress_callback is not None:
            progress_callback("capture-receipt", "start", 0, 1)
        receipt_raw, receipt = _read_capture_receipt(
            root,
            capture_receipt,
            archive_id=archive_id,
        )
        if progress_callback is not None:
            progress_callback("capture-receipt", "done", 1, 1)
            progress_callback("object-manifest", "start", None, None)
        manifest_records = completion_workflows._strict_zettel_objet_manifest_records(
            root
        )
        if progress_callback is not None:
            progress_callback(
                "object-manifest", "done", len(manifest_records), len(manifest_records)
            )
        targets, unreadable_count = _canonical_index(
            root,
            progress_callback=progress_callback,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError):
        return {
            "ok": False,
            "schema": RECOVERY_SCHEMA,
            "lifecycle_action": "zettel_objet_link_recovery_plan",
            "state": "blocked",
            "dry_run": True,
            "summary": {"capture_item_count": 0, "classified_item_count": 0},
            "items": [],
            "exact_operation_manifest": None,
            "blockers": ["zettel_objet_link_recovery_evidence_invalid"],
            "warnings": [],
            "would_change": [],
            "privacy_guards": _privacy_guards(),
        }

    receipt_items = receipt["items"]
    if len(receipt_items) > effective_max:
        blockers.append("zettel_objet_link_recovery_item_count_exceeds_max")
    if unreadable_count:
        blockers.append("zettel_objet_link_recovery_canonical_scan_incomplete")

    source_index: dict[str, list[dict[str, Any]]] = {}
    title_index: dict[str, list[dict[str, Any]]] = {}
    for target in targets:
        for source_id in target["source_ids"]:
            source_index.setdefault(source_id, []).append(target)
        if target["title"] is not None:
            title_index.setdefault(target["title"], []).append(target)
    manifest_index: dict[str, list[dict[str, Any]]] = {}
    for record in manifest_records:
        object_id = str(record.get("object_id") or "").strip().lower()
        manifest_index.setdefault(object_id, []).append(record)

    public_items: list[dict[str, Any]] = []
    exact_items: list[ExactOperationItem] = []
    counts = {
        "exact_link_ready": 0,
        "already_linked": 0,
        "review_required": 0,
        "no_target": 0,
    }
    receipt_sha256 = _sha(receipt_raw)
    if progress_callback is not None:
        progress_callback("classification", "start", 0, len(receipt_items))
    for receipt_ordinal, item in enumerate(receipt_items):
        object_id = str(item.get("object_id") or "").strip().lower()
        source_ids = set()
        for value in (
            item.get("source_staged_path"),
            item.get("original_filename"),
        ):
            source_ids.update(_source_ids_in_text(value))
        source_targets = {
            target["id"]: target
            for source_id in source_ids
            for target in source_index.get(source_id, [])
        }
        title_key = _receipt_filename_title(item.get("original_filename"))
        title_targets = {
            target["id"]: target
            for target in title_index.get(title_key, [])
        }
        evidence_basis: list[str] = []
        candidate_targets: dict[str, dict[str, Any]] = {}
        if source_targets:
            candidate_targets.update(source_targets)
            evidence_basis.append("preserved_source_id")
        if title_targets:
            candidate_targets.update(title_targets)
            evidence_basis.append("normalized_original_filename_title")

        item_blockers: list[str] = []
        exact_target: dict[str, Any] | None = None
        if len(manifest_index.get(object_id, [])) != 1:
            item_blockers.append("object_manifest_record_not_unique")
        if len(source_targets) == 1:
            exact_target = next(iter(source_targets.values()))
            if title_targets and exact_target["id"] not in title_targets:
                item_blockers.append("source_id_and_title_evidence_disagree")
        elif len(source_targets) > 1:
            item_blockers.append("source_id_target_ambiguous")
        elif title_targets:
            item_blockers.append("title_only_evidence_requires_review")

        if exact_target is None and not candidate_targets:
            state = "no_target"
        elif exact_target is None or item_blockers:
            state = "review_required"
        else:
            assets = exact_target.get("assets")
            if not isinstance(assets, list) or any(
                not isinstance(asset, dict) for asset in assets
            ):
                state = "review_required"
                item_blockers.append("target_assets_not_array")
            elif any(asset.get("object_id") == object_id for asset in assets):
                state = "already_linked"
            else:
                state = "exact_link_ready"
                after_assets = [*assets, {"object_id": object_id, "role": normalized_role}]
                target_ref = _sha(
                    _canonical_bytes(
                        {
                            "archive_id": archive_id,
                            "zettel_id": exact_target["id"],
                            "zettel_path": exact_target["path"],
                        }
                    )
                )
                source_sha256 = _sha(
                    _canonical_bytes(
                        {
                            "capture_receipt_sha256": receipt_sha256,
                            "receipt_ordinal": receipt_ordinal,
                            "object_id": object_id,
                            "source_ids": sorted(source_ids),
                        }
                    )
                )
                exact_items.append(
                    ExactOperationItem(
                        ordinal=len(exact_items),
                        item_id=f"item:{receipt_ordinal:06d}",
                        target_kind="zettel",
                        target_ref=target_ref,
                        target_identity_sha256=target_ref,
                        fields=(
                            ExactFieldEffect(
                                field_ref="frontmatter.assets",
                                pre_sha256=hash_field_value(_canonical_bytes(assets)),
                                post_sha256=hash_field_value(_canonical_bytes(after_assets)),
                                source_sha256=source_sha256,
                            ),
                        ),
                    )
                )
        counts[state] += 1
        public_items.append(
            {
                "ordinal": receipt_ordinal,
                "item_ref_sha256": _sha(
                    _canonical_bytes(
                        {
                            "receipt_sha256": receipt_sha256,
                            "ordinal": receipt_ordinal,
                            "object_id": object_id,
                        }
                    )
                ),
                "state": state,
                "candidate_count": len(candidate_targets),
                "evidence_basis": evidence_basis,
                "blocker_codes": item_blockers,
            }
        )
        completed = receipt_ordinal + 1
        if progress_callback is not None and (
            completed == 1
            or completed == len(receipt_items)
            or completed % 100 == 0
        ):
            progress_callback(
                "classification", "scanned", completed, len(receipt_items)
            )

    if progress_callback is not None:
        progress_callback(
            "classification", "done", len(receipt_items), len(receipt_items)
        )

    exact_manifest = None
    if exact_items and not blockers:
        exact_manifest = ExactOperationManifest.build(
            operation="zettel_objet_link_recovery",
            archive_identity_sha256=hash_field_value(archive_id.encode("utf-8")),
            items=exact_items,
        ).document()
    classified_count = sum(counts.values())
    if classified_count != len(receipt_items):
        blockers.append("zettel_objet_link_recovery_classification_incomplete")
    state = "blocked" if blockers else "classified"
    return {
        "ok": not blockers,
        "schema": RECOVERY_SCHEMA,
        "lifecycle_action": "zettel_objet_link_recovery_plan",
        "state": state,
        "dry_run": True,
        "summary": {
            "capture_receipt_sha256": receipt_sha256,
            "capture_item_count": len(receipt_items),
            "classified_item_count": classified_count,
            **counts,
            "exact_manifest_item_count": len(exact_items),
            "canonical_zettel_count": len(targets),
            "unreadable_canonical_count": unreadable_count,
            "object_manifest_row_count": len(manifest_records),
            "classification_set_sha256": _sha(_canonical_bytes(public_items)),
        },
        "items": public_items,
        "exact_operation_manifest": exact_manifest,
        "blockers": archive_services.unique_preserve_order(blockers),
        "warnings": archive_services.unique_preserve_order(warnings),
        "would_change": (
            ["frontmatter.assets"] if exact_manifest is not None else []
        ),
        "privacy_guards": _privacy_guards(),
    }


def _privacy_guards() -> dict[str, bool]:
    return {
        "original_filename_echoed": False,
        "source_path_echoed": False,
        "source_id_echoed": False,
        "page_title_echoed": False,
        "provider_locator_echoed": False,
        "zettel_id_echoed": False,
        "absolute_local_path_echoed": False,
        "object_file_bytes_read": False,
        "provider_api_called": False,
        "writes": False,
    }


__all__ = ["zettel_objet_link_recovery_plan"]
