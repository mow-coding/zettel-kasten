"""Read-only, receipt-bound recovery planning for imported locator loss.

The public surface of this module is content-free.  Source page identifiers,
provider URLs, zettel identifiers, titles, bodies, and absolute paths are used
only inside the planner and are replaced by SHA-256 references in its result.
No provider is contacted and no archive byte is written.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from . import archive_services, completion_workflows
from .exact_human_approval import exact_human_approval_archive_identity_sha256
from .exact_operation_manifest import (
    ExactFieldEffect,
    ExactOperationEvidence,
    ExactOperationItem,
    ExactOperationManifest,
    hash_field_value,
)
from .local_recovery_execution import (
    APPLY_OPERATION,
    LocalRecoveryFieldSpec,
    LocalRecoveryPlan,
    build_local_recovery_plan,
    combine_local_recovery_plans,
    local_recovery_ledger_identity_sha256,
    local_recovery_ledger_relative,
    local_recovery_zettel_identity_sha256,
)


MIRROR_RECOVERY_SCHEMA = "wom-kit/notion-locator-mirror-recovery-plan/v0.1"
ORPHAN_RECOVERY_SCHEMA = "wom-kit/notion-locator-orphan-recovery-plan/v0.1"
MAX_MIRROR_BYTES = 64 * 1024 * 1024
MAX_MIRROR_ROWS = 10_000
MAX_MIRROR_LINE_BYTES = 16 * 1024 * 1024
MAX_MARKUP_RECEIPTS = 100
MAX_RETURNED_ITEMS = 10_000
_URL_RE = re.compile(r"(?i)\bhttps?://[^\s<>\")\]]+")
_MARKUP_RECEIPT_RE = re.compile(
    r"receipts/markup-normalization/[0-9a-f]{64}\.json"
)


class _DuplicateKey(ValueError):
    pass


def _reject_duplicate_pairs(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
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


def _safe_max_items(value: int) -> int:
    return max(0, min(int(value), MAX_RETURNED_ITEMS))


def _private_file_snapshot(
    path: Path,
    *,
    max_bytes: int,
    expected_name: str | None = None,
) -> bytes:
    if expected_name is not None and path.name != expected_name:
        raise archive_services.ArchiveServiceError(
            "local_locator_private_evidence_invalid"
        )
    raw, reason = archive_services._bounded_stable_regular_file_read(
        path,
        max_bytes=max_bytes,
    )
    if raw is None or reason is not None:
        raise archive_services.ArchiveServiceError(
            "local_locator_private_evidence_invalid"
        )
    return raw


def _parse_source_mirror(
    source_mirror: Path | str,
    *,
    progress_callback: Callable[[str, str, int | None, int | None], None]
    | None = None,
) -> tuple[bytes, dict[str, dict[str, Any]], int]:
    path = Path(source_mirror)
    raw = _private_file_snapshot(
        path,
        max_bytes=MAX_MIRROR_BYTES,
        expected_name="pages.markdown.jsonl",
    )
    raw_lines = raw.splitlines()
    if not raw_lines or len(raw_lines) > MAX_MIRROR_ROWS:
        raise archive_services.ArchiveServiceError(
            "local_locator_source_mirror_invalid"
        )
    index: dict[str, dict[str, Any]] = {}
    if progress_callback is not None:
        progress_callback("source-mirror", "start", 0, len(raw_lines))
    for ordinal, raw_line in enumerate(raw_lines, start=1):
        if not raw_line or len(raw_line) > MAX_MIRROR_LINE_BYTES:
            raise archive_services.ArchiveServiceError(
                "local_locator_source_mirror_invalid"
            )
        try:
            row = json.loads(
                raw_line.decode("utf-8-sig" if ordinal == 1 else "utf-8"),
                object_pairs_hook=_reject_duplicate_pairs,
                parse_constant=_reject_nonfinite,
            )
        except (
            UnicodeError,
            json.JSONDecodeError,
            RecursionError,
            ValueError,
        ) as exc:
            raise archive_services.ArchiveServiceError(
                "local_locator_source_mirror_invalid"
            ) from exc
        if not isinstance(row, dict):
            raise archive_services.ArchiveServiceError(
                "local_locator_source_mirror_invalid"
            )
        page_id = archive_services._normalize_notion_locator_source_page_id(
            row.get("page_id")
        )
        markdown = row.get("markdown")
        if page_id is None or not isinstance(markdown, str) or page_id in index:
            raise archive_services.ArchiveServiceError(
                "local_locator_source_mirror_invalid"
            )
        urls = sorted(set(_URL_RE.findall(markdown)))
        index[page_id] = {
            "row_sha256": _sha(raw_line),
            "urls": urls,
        }
        if progress_callback is not None and (
            ordinal == 1
            or ordinal == len(raw_lines)
            or ordinal % 250 == 0
        ):
            progress_callback(
                "source-mirror", "scanned", ordinal, len(raw_lines)
            )
    if progress_callback is not None:
        progress_callback(
            "source-mirror", "done", len(raw_lines), len(raw_lines)
        )
    return raw, index, len(raw_lines)


def _current_locator_targets(
    root: Path,
    *,
    source_index: dict[str, dict[str, Any]],
    progress_callback: Callable[[str, str, int | None, int | None], None]
    | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int], list[str]]:
    counters = {
        "canonical_zettel_count": 0,
        "body_marker_zettel_count": 0,
        "body_marker_count": 0,
        "source_page_join_count": 0,
        "mirror_url_zettel_count": 0,
        "already_recorded_zettel_count": 0,
        "already_recorded_locator_count": 0,
        "unreadable_zettel_count": 0,
    }
    blockers: list[str] = []
    targets: list[dict[str, Any]] = []
    paths = sorted((root / "zettels").glob("*.md"))
    if progress_callback is not None:
        progress_callback("canonical-locators", "start", 0, len(paths))
    for ordinal, path in enumerate(paths, start=1):
        raw, reason = archive_services._bounded_stable_regular_file_read(
            path,
            max_bytes=archive_services.NOTION_LOCATOR_EVIDENCE_MAX_CANONICAL_FILE_BYTES,
        )
        if raw is None or reason is not None:
            counters["unreadable_zettel_count"] += 1
            continue
        try:
            text = raw.decode("utf-8-sig")
            boundary = archive_services.parse_approval_zettel_content_boundary(
                text
            )
        except (UnicodeError, RecursionError, ValueError):
            counters["unreadable_zettel_count"] += 1
            continue
        frontmatter = boundary.get("frontmatter")
        if (
            boundary.get("state") == "blocked"
            or not isinstance(frontmatter, dict)
            or frontmatter.get("status") != "canonical"
        ):
            counters["unreadable_zettel_count"] += 1
            continue
        counters["canonical_zettel_count"] += 1
        body = str(boundary.get("body") or "")
        marker_count = body.count(
            archive_services.NOTION_IMPORT_LOCATOR_OMISSION_MARKER
        )
        if marker_count <= 0:
            continue
        counters["body_marker_zettel_count"] += 1
        counters["body_marker_count"] += marker_count
        source_page_id, source_state, _candidates = (
            archive_services._notion_locator_exact_source_page_id(
                frontmatter
            )
        )
        source = (
            source_index.get(source_page_id)
            if source_page_id is not None
            else None
        )
        if source is None:
            continue
        counters["source_page_join_count"] += 1
        urls = source["urls"]
        if not urls:
            continue
        counters["mirror_url_zettel_count"] += 1
        zettel_id = frontmatter.get("id")
        if not isinstance(zettel_id, str):
            counters["unreadable_zettel_count"] += 1
            continue
        current_record, current_bytes, record_error = (
            completion_workflows._read_locator_record(root, zettel_id)
        )
        if record_error is not None:
            blockers.append("local_locator_record_scan_incomplete")
            continue
        if current_record is not None:
            counters["already_recorded_zettel_count"] += 1
            counters["already_recorded_locator_count"] += len(
                current_record.get("locators", [])
            )
            continue
        targets.append(
            {
                "zettel_id": zettel_id,
                "path": archive_services.archive_relative_path(path, root),
                "canonical_sha256": _sha(raw),
                "source_page_id": source_page_id,
                "source_row_sha256": source["row_sha256"],
                "urls": urls,
                "current_record_bytes": current_bytes,
                "marker_count": marker_count,
                "declared_count": archive_services.notion_import_locator_omitted_count(
                    frontmatter
                ),
                "source_state": source_state,
            }
        )
        if progress_callback is not None and (
            ordinal == 1 or ordinal == len(paths) or ordinal % 250 == 0
        ):
            progress_callback(
                "canonical-locators", "scanned", ordinal, len(paths)
            )
    if progress_callback is not None:
        progress_callback(
            "canonical-locators", "done", len(paths), len(paths)
        )
    if counters["unreadable_zettel_count"]:
        blockers.append("local_locator_canonical_scan_incomplete")
    return targets, counters, archive_services.unique_preserve_order(blockers)


def notion_locator_mirror_recovery_plan(
    archive_root: Path | str,
    *,
    source_mirror: Path | str,
    dry_run: bool = True,
    max_items: int = 200,
    expected_zettel_count: int | None = None,
    expected_pair_count: int | None = None,
    progress_callback: Callable[[str, str, int | None, int | None], None]
    | None = None,
    _build_execution: bool = False,
) -> dict[str, Any] | LocalRecoveryPlan:
    """Bind one local Notion mirror to all currently unrecorded locator pairs."""

    root = archive_services.require_existing_archive_root(archive_root)
    archive_id = archive_services.read_archive_id(root)
    blockers: list[str] = []
    warnings: list[str] = []
    if not dry_run:
        blockers.append("local_locator_recovery_dry_run_required")
    try:
        returned_limit = _safe_max_items(max_items)
    except (TypeError, ValueError, OverflowError):
        returned_limit = 200
        blockers.append("local_locator_recovery_max_items_invalid")
    try:
        mirror_raw, source_index, source_row_count = _parse_source_mirror(
            source_mirror,
            progress_callback=progress_callback,
        )
        targets, census, scan_blockers = _current_locator_targets(
            root,
            source_index=source_index,
            progress_callback=progress_callback,
        )
        blockers.extend(scan_blockers)
    except (archive_services.ArchiveServiceError, OSError, ValueError):
        return {
            "ok": False,
            "schema": MIRROR_RECOVERY_SCHEMA,
            "lifecycle_action": "notion_locator_mirror_recovery_plan",
            "state": "blocked",
            "dry_run": True,
            "summary": {
                "target_zettel_count": 0,
                "locator_pair_count": 0,
                "classified_pair_count": 0,
            },
            "items": [],
            "exact_operation_manifest": None,
            "blockers": ["local_locator_recovery_evidence_invalid"],
            "warnings": [],
            "would_change": [],
            "privacy_guards": _privacy_guards(),
        }

    mirror_sha256 = _sha(mirror_raw)
    try:
        mirror_mtime = Path(source_mirror).stat().st_mtime
        recorded_at = (
            datetime.fromtimestamp(mirror_mtime, timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
    except (OSError, OverflowError, ValueError):
        blockers.append("local_locator_source_mirror_timestamp_invalid")
        recorded_at = ""
    public_pairs: list[dict[str, Any]] = []
    exact_items: list[ExactOperationItem] = []
    exact_specs: list[LocalRecoveryFieldSpec] = []
    pair_counts = {"exact_record_ready": 0, "review_required": 0}
    target_counts = {"exact_record_ready": 0, "review_required": 0}
    if progress_callback is not None:
        progress_callback("locator-classification", "start", 0, len(targets))
    for target_ordinal, target in enumerate(targets):
        target_ref = _sha(
            _canonical_bytes(
                {
                    "archive_id": archive_id,
                    "zettel_id": target["zettel_id"],
                    "path": target["path"],
                }
            )
        )
        safe_urls: list[str] = []
        target_has_review = False
        for url in target["urls"]:
            pair_ref = _sha(
                _canonical_bytes(
                    {
                        "target_ref": target_ref,
                        "locator_ref": url,
                    }
                )
            )
            blocker_codes: list[str] = []
            if completion_workflows._safe_locator_ref(url) != url:
                blocker_codes.append("locator_ref_invalid_or_secret_like")
                state = "review_required"
                target_has_review = True
            else:
                state = "exact_record_ready"
                safe_urls.append(url)
            pair_counts[state] += 1
            public_pairs.append(
                {
                    "ordinal": len(public_pairs),
                    "pair_ref_sha256": pair_ref,
                    "target_ref_sha256": target_ref,
                    "state": state,
                    "blocker_codes": blocker_codes,
                }
            )
        target_state = (
            "review_required" if target_has_review else "exact_record_ready"
        )
        target_counts[target_state] += 1
        if not target_has_review:
            coordinate_set = _canonical_bytes(
                [
                    {
                        "locator_type": "source_url",
                        "locator_ref": url,
                    }
                    for url in safe_urls
                ]
            )
            locator_rows = []
            for url in safe_urls:
                locator_identity = _canonical_bytes(
                    {
                        "locator_ref": url,
                        "service_ref": None,
                        "account_ref": None,
                        "occurrence_anchor": None,
                    }
                )
                locator_rows.append(
                    {
                        "locator_id": (
                            "locator:sha256:"
                            + hashlib.sha256(locator_identity).hexdigest()
                        ),
                        "locator_type": "source_url",
                        "locator_ref": url,
                        "status": "active",
                        "recorded_at": recorded_at,
                        "reviewed_by": "exact_human_approval",
                        "provenance": {
                            "source": "receipt_bound_local_recovery",
                            "automatic_recovery_claimed": False,
                        },
                    }
                )
            record = {
                "schema": completion_workflows.EXTERNAL_LOCATOR_SCHEMA,
                "archive_id": archive_id,
                "zettel_id": target["zettel_id"],
                "created_at": recorded_at,
                "updated_at": recorded_at,
                "locators": locator_rows,
            }
            record_bytes = completion_workflows._canonical_json_bytes(record)
            source_value = _canonical_bytes(
                {
                    "source_row_sha256": target["source_row_sha256"],
                    "source_page_id": target["source_page_id"],
                    "locator_refs": safe_urls,
                    "record_sha256": _sha(record_bytes),
                }
            )
            target_identity = local_recovery_zettel_identity_sha256(
                archive_id,
                target["zettel_id"],
                target["path"],
            )
            exact_item = ExactOperationItem(
                    ordinal=len(exact_items),
                    item_id=f"item:{target_ordinal:06d}",
                    target_kind="external_locator_record",
                    target_ref=target_ref,
                    target_identity_sha256=target_identity,
                    fields=(
                        ExactFieldEffect(
                            field_ref="external_locator.coordinate_set",
                            pre_sha256=hash_field_value(None),
                            post_sha256=hash_field_value(coordinate_set),
                            source_sha256=hash_field_value(source_value),
                        ),
                    ),
                )
            exact_items.append(exact_item)
            exact_specs.append(
                LocalRecoveryFieldSpec(
                    item_id=exact_item.item_id,
                    target_kind=exact_item.target_kind,
                    target_ref=exact_item.target_ref,
                    target_identity_sha256=exact_item.target_identity_sha256,
                    field_ref="external_locator.coordinate_set",
                    target_relative=target["path"],
                    zettel_id=target["zettel_id"],
                    pre_value=None,
                    post_value=coordinate_set,
                    source_value=source_value,
                    post_file_bytes=record_bytes,
                )
            )
        completed = target_ordinal + 1
        if progress_callback is not None and (
            completed == 1
            or completed == len(targets)
            or completed % 100 == 0
        ):
            progress_callback(
                "locator-classification", "scanned", completed, len(targets)
            )
    if progress_callback is not None:
        progress_callback(
            "locator-classification", "done", len(targets), len(targets)
        )

    pair_count = len(public_pairs)
    if expected_zettel_count is not None and int(expected_zettel_count) != len(
        targets
    ):
        blockers.append("local_locator_expected_zettel_count_mismatch")
    if expected_pair_count is not None and int(expected_pair_count) != pair_count:
        blockers.append("local_locator_expected_pair_count_mismatch")
    if sum(pair_counts.values()) != pair_count:
        blockers.append("local_locator_pair_classification_incomplete")

    target_refs = [
        item["target_ref_sha256"]
        for item in public_pairs
    ]
    unique_target_refs = sorted(set(target_refs))
    digests = {
        "source_mirror_sha256": mirror_sha256,
        "source_mirror_row_set_sha256": _sha(
            _canonical_bytes(
                sorted(row["row_sha256"] for row in source_index.values())
            )
        ),
        "target_zettel_set_sha256": _sha(_canonical_bytes(unique_target_refs)),
        "locator_pair_set_sha256": _sha(
            _canonical_bytes(
                [item["pair_ref_sha256"] for item in public_pairs]
            )
        ),
        "locator_pair_classification_set_sha256": _sha(
            _canonical_bytes(public_pairs)
        ),
        "exact_record_ready_pair_set_sha256": _sha(
            _canonical_bytes(
                [
                    item["pair_ref_sha256"]
                    for item in public_pairs
                    if item["state"] == "exact_record_ready"
                ]
            )
        ),
        "review_required_pair_set_sha256": _sha(
            _canonical_bytes(
                [
                    item["pair_ref_sha256"]
                    for item in public_pairs
                    if item["state"] == "review_required"
                ]
            )
        ),
    }
    counts = {
        **census,
        "source_mirror_row_count": source_row_count,
        "target_zettel_count": len(targets),
        "classified_target_count": sum(target_counts.values()),
        "exact_record_ready_target_count": target_counts["exact_record_ready"],
        "review_required_target_count": target_counts["review_required"],
        "locator_pair_count": pair_count,
        "classified_pair_count": sum(pair_counts.values()),
        "exact_record_ready_pair_count": pair_counts["exact_record_ready"],
        "review_required_pair_count": pair_counts["review_required"],
    }
    operation_evidence = ExactOperationEvidence(
        schema="wom-kit/notion-locator-mirror-recovery-evidence/v1",
        counts=tuple(sorted(counts.items())),
        digests=tuple(sorted(digests.items())),
    )
    locator_record_item_count = len(exact_items)
    ledger_bytes = _canonical_bytes(
        {
            "schema": "wom-kit/notion-locator-mirror-recovery-ledger/v0.1",
            "archive_identity_sha256": (
                exact_human_approval_archive_identity_sha256(archive_id)
            ),
            "classification_items": public_pairs,
            "operation_evidence": operation_evidence.document(),
            "private_values_echoed": False,
        }
    ) + b"\n"
    ledger_relative = local_recovery_ledger_relative(
        "notion_locator_mirror",
        ledger_bytes,
    )
    ledger_identity = local_recovery_ledger_identity_sha256(
        archive_id,
        "notion_locator_mirror",
        ledger_relative,
    )
    ledger_source = _canonical_bytes(
        {
            "operation_evidence_sha256": operation_evidence.evidence_sha256,
            "source_mirror_sha256": mirror_sha256,
        }
    )
    ledger_item = ExactOperationItem(
        ordinal=len(exact_items),
        item_id=f"item:{pair_count:06d}:classification",
        target_kind="local_recovery_ledger",
        target_ref=_sha(ledger_relative.encode("utf-8")),
        target_identity_sha256=ledger_identity,
        fields=(
            ExactFieldEffect(
                field_ref="classification.ledger",
                pre_sha256=hash_field_value(None),
                post_sha256=hash_field_value(ledger_bytes),
                source_sha256=hash_field_value(ledger_source),
            ),
        ),
    )
    exact_items.append(ledger_item)
    exact_specs.append(
        LocalRecoveryFieldSpec(
            item_id=ledger_item.item_id,
            target_kind=ledger_item.target_kind,
            target_ref=ledger_item.target_ref,
            target_identity_sha256=ledger_item.target_identity_sha256,
            field_ref="classification.ledger",
            target_relative=ledger_relative,
            zettel_id=None,
            pre_value=None,
            post_value=ledger_bytes,
            source_value=ledger_source,
        )
    )
    exact_manifest_object = None
    exact_manifest = None
    if not blockers:
        exact_manifest_object = ExactOperationManifest.build(
            operation=APPLY_OPERATION,
            archive_identity_sha256=(
                exact_human_approval_archive_identity_sha256(archive_id)
            ),
            items=exact_items,
            operation_evidence=operation_evidence,
        )
        exact_manifest = exact_manifest_object.document()
    returned_items = public_pairs[:returned_limit]
    if len(returned_items) < pair_count:
        warnings.append("local_locator_items_truncated")
    result = {
        "ok": not blockers,
        "schema": MIRROR_RECOVERY_SCHEMA,
        "lifecycle_action": "notion_locator_mirror_recovery_plan",
        "state": "blocked" if blockers else "classified",
        "dry_run": True,
        "summary": {
            **counts,
            **digests,
            "operation_evidence_sha256": operation_evidence.evidence_sha256,
            "exact_manifest_item_count": len(exact_items),
            "locator_record_manifest_item_count": locator_record_item_count,
            "classification_ledger_item_count": 1,
            "returned_item_count": len(returned_items),
            "truncated_item_count": pair_count - len(returned_items),
            "expected_zettel_count": expected_zettel_count,
            "expected_pair_count": expected_pair_count,
        },
        "items": returned_items,
        "exact_operation_manifest": exact_manifest,
        "blockers": archive_services.unique_preserve_order(blockers),
        "warnings": archive_services.unique_preserve_order(warnings),
        "would_change": (
            (
                (["ops/external-locators"] if locator_record_item_count else [])
                + ["classification.ledger"]
            )
            if exact_manifest is not None
            else []
        ),
        "privacy_guards": _privacy_guards(),
    }
    if _build_execution:
        if exact_manifest_object is None:
            raise archive_services.ArchiveServiceError(
                "notion_locator_mirror_execution_blocked"
            )
        execution_warnings = []
        if pair_counts["review_required"]:
            execution_warnings.append("review_locator_pairs_present")
        return build_local_recovery_plan(
            root,
            domain="notion_locator_mirror",
            manifest=exact_manifest_object,
            specs=exact_specs,
            warning_codes=execution_warnings,
            public_summary=result["summary"],
        )
    return result


def _read_markup_receipt(
    root: Path,
    receipt_relative: str,
    *,
    archive_id: str,
) -> tuple[bytes, dict[str, Any]]:
    try:
        normalized = archive_services.normalize_archive_relative_path(
            receipt_relative
        )
    except (archive_services.ArchivePathError, TypeError, ValueError) as exc:
        raise archive_services.ArchiveServiceError(
            "local_locator_markup_receipt_invalid"
        ) from exc
    if _MARKUP_RECEIPT_RE.fullmatch(normalized) is None:
        raise archive_services.ArchiveServiceError(
            "local_locator_markup_receipt_invalid"
        )
    path = archive_services.archive_internal_path(root, normalized)
    raw = _private_file_snapshot(path, max_bytes=64 * 1024 * 1024)
    try:
        receipt = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_nonfinite,
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        RecursionError,
        ValueError,
    ) as exc:
        raise archive_services.ArchiveServiceError(
            "local_locator_markup_receipt_invalid"
        ) from exc
    if (
        not isinstance(receipt, dict)
        or receipt.get("schema")
        != completion_workflows.MARKUP_NORMALIZATION_RECEIPT_SCHEMA
        or receipt.get("archive_id") != archive_id
        or not isinstance(receipt.get("items"), list)
        or receipt.get("item_count") != len(receipt["items"])
        or re.fullmatch(
            r"[0-9a-f]{64}", str(receipt.get("plan_sha256") or "")
        )
        is None
        or PurePosixPath(normalized).stem != receipt.get("plan_sha256")
    ):
        raise archive_services.ArchiveServiceError(
            "local_locator_markup_receipt_invalid"
        )
    return raw, receipt


def _receipt_snapshot_bytes(
    root: Path,
    item: dict[str, Any],
    field: str,
    expected_sha_field: str,
) -> bytes:
    relative = item.get(field)
    expected = item.get(expected_sha_field)
    if (
        not isinstance(relative, str)
        or not re.fullmatch(r"[0-9a-f]{64}", str(expected or ""))
    ):
        raise archive_services.ArchiveServiceError(
            "local_locator_markup_snapshot_invalid"
        )
    path = archive_services.archive_internal_path(root, relative)
    raw = _private_file_snapshot(
        path,
        max_bytes=archive_services.NOTION_LOCATOR_EVIDENCE_MAX_CANONICAL_FILE_BYTES,
    )
    if hashlib.sha256(raw).hexdigest() != expected:
        raise archive_services.ArchiveServiceError(
            "local_locator_markup_snapshot_invalid"
        )
    return raw


def _zettel_parts(raw: bytes) -> tuple[dict[str, Any], str]:
    try:
        text = raw.decode("utf-8-sig")
        boundary = archive_services.parse_approval_zettel_content_boundary(text)
    except (UnicodeError, RecursionError, ValueError) as exc:
        raise archive_services.ArchiveServiceError(
            "local_locator_markup_snapshot_invalid"
        ) from exc
    frontmatter = boundary.get("frontmatter")
    if boundary.get("state") == "blocked" or not isinstance(frontmatter, dict):
        raise archive_services.ArchiveServiceError(
            "local_locator_markup_snapshot_invalid"
        )
    return frontmatter, str(boundary.get("body") or "")


def _marker_projection(body: str) -> bytes:
    marker = archive_services.NOTION_IMPORT_LOCATOR_OMISSION_MARKER
    rows: list[dict[str, Any]] = []
    start = 0
    ordinal = 0
    while True:
        position = body.find(marker, start)
        if position < 0:
            break
        ordinal += 1
        rows.append(
            {
                "ordinal": ordinal,
                "before_anchor_sha256": _sha(
                    body[max(0, position - 64) : position].encode("utf-8")
                ),
                "after_anchor_sha256": _sha(
                    body[
                        position + len(marker) : position + len(marker) + 64
                    ].encode("utf-8")
                ),
            }
        )
        start = position + len(marker)
    return _canonical_bytes(rows)


def notion_locator_orphan_recovery_plan(
    archive_root: Path | str,
    *,
    markup_receipts: list[str],
    dry_run: bool = True,
    max_items: int = 200,
    expected_orphan_row_count: int | None = None,
    progress_callback: Callable[[str, str, int | None, int | None], None]
    | None = None,
    _build_execution: bool = False,
) -> dict[str, Any] | LocalRecoveryPlan:
    """Classify marker-loss rows introduced by exact markup transactions."""

    root = archive_services.require_existing_archive_root(archive_root)
    archive_id = archive_services.read_archive_id(root)
    blockers: list[str] = []
    warnings: list[str] = []
    if not dry_run:
        blockers.append("local_locator_orphan_recovery_dry_run_required")
    try:
        returned_limit = _safe_max_items(max_items)
    except (TypeError, ValueError, OverflowError):
        returned_limit = 200
        blockers.append("local_locator_orphan_recovery_max_items_invalid")
    if (
        not isinstance(markup_receipts, list)
        or not 1 <= len(markup_receipts) <= MAX_MARKUP_RECEIPTS
        or len(markup_receipts) != len(set(markup_receipts))
    ):
        blockers.append("local_locator_markup_receipt_set_invalid")
        markup_receipts = []

    receipt_rows: list[tuple[str, dict[str, Any]]] = []
    receipt_refs: list[str] = []
    try:
        for receipt_relative in sorted(markup_receipts):
            receipt_raw, receipt = _read_markup_receipt(
                root,
                receipt_relative,
                archive_id=archive_id,
            )
            receipt_sha256 = _sha(receipt_raw)
            receipt_refs.append(receipt_sha256)
            transaction_root = (
                ".wom-scratch/markup-normalization/transactions/"
                + receipt["plan_sha256"]
                + "/snapshots/"
            )
            for expected_index, item in enumerate(receipt["items"]):
                zettel_id = (
                    item.get("zettel_id")
                    if isinstance(item, dict)
                    else None
                )
                before_sha256 = (
                    item.get("before_sha256") if isinstance(item, dict) else None
                )
                after_sha256 = (
                    item.get("after_sha256") if isinstance(item, dict) else None
                )
                expected_before = (
                    f"{transaction_root}{expected_index:06d}.before."
                    f"{before_sha256}.bin"
                )
                expected_after = (
                    f"{transaction_root}{expected_index:06d}.after."
                    f"{after_sha256}.bin"
                )
                if (
                    not isinstance(item, dict)
                    or item.get("index") != expected_index
                    or not isinstance(zettel_id, str)
                    or not zettel_id
                    or item.get("path") != f"zettels/{zettel_id}.md"
                    or re.fullmatch(r"[0-9a-f]{64}", str(before_sha256 or ""))
                    is None
                    or re.fullmatch(r"[0-9a-f]{64}", str(after_sha256 or ""))
                    is None
                    or item.get("snapshot_path") != expected_before
                    or item.get("before_snapshot_path") != expected_before
                    or item.get("after_snapshot_path") != expected_after
                ):
                    raise archive_services.ArchiveServiceError(
                        "local_locator_markup_receipt_invalid"
                    )
                receipt_rows.append((receipt_sha256, item))
    except (archive_services.ArchiveServiceError, OSError, ValueError):
        return {
            "ok": False,
            "schema": ORPHAN_RECOVERY_SCHEMA,
            "lifecycle_action": "notion_locator_orphan_recovery_plan",
            "state": "blocked",
            "dry_run": True,
            "summary": {
                "markup_receipt_count": len(markup_receipts),
                "orphan_row_count": 0,
                "classified_orphan_row_count": 0,
            },
            "items": [],
            "exact_operation_manifest": None,
            "blockers": ["local_locator_orphan_recovery_evidence_invalid"],
            "warnings": [],
            "would_change": [],
            "privacy_guards": _privacy_guards(),
        }

    public_items: list[dict[str, Any]] = []
    exact_items: list[ExactOperationItem] = []
    exact_specs: list[LocalRecoveryFieldSpec] = []
    state_counts = {
        "normal_maintain": 0,
        "restore_ready": 0,
        "review_pending": 0,
    }
    removed_marker_count = 0
    preexisting_orphan_row_count = 0
    if progress_callback is not None:
        progress_callback(
            "markup-orphan-classification", "start", 0, len(receipt_rows)
        )
    try:
        for transaction_ordinal, (
            receipt_sha256,
            item,
        ) in enumerate(receipt_rows):
            before_raw = _receipt_snapshot_bytes(
                root, item, "before_snapshot_path", "before_sha256"
            )
            after_raw = _receipt_snapshot_bytes(
                root, item, "after_snapshot_path", "after_sha256"
            )
            before_frontmatter, before_body = _zettel_parts(before_raw)
            after_frontmatter, after_body = _zettel_parts(after_raw)
            expected_zettel_id = item.get("zettel_id")
            if (
                before_frontmatter.get("id") != expected_zettel_id
                or after_frontmatter.get("id") != expected_zettel_id
                or before_frontmatter.get("archive_id") != archive_id
                or after_frontmatter.get("archive_id") != archive_id
                or before_frontmatter.get("status") != "canonical"
                or after_frontmatter.get("status") != "canonical"
                or before_frontmatter != after_frontmatter
            ):
                raise archive_services.ArchiveServiceError(
                    "local_locator_markup_snapshot_invalid"
                )
            declared = archive_services.notion_import_locator_omitted_count(
                after_frontmatter
            )
            marker = archive_services.NOTION_IMPORT_LOCATOR_OMISSION_MARKER
            before_count = before_body.count(marker)
            after_count = after_body.count(marker)
            removed_marker_count += max(0, before_count - after_count)
            preexisting_orphan_row_count += max(0, declared - before_count)
            new_orphans = max(
                0,
                min(declared, before_count) - min(declared, after_count),
            )
            if new_orphans <= 0 or after_count != 0:
                continue

            target_path = archive_services.archive_internal_path(
                root, str(item.get("path") or "")
            )
            current_raw, reason = (
                archive_services._bounded_stable_regular_file_read(
                    target_path,
                    max_bytes=archive_services.NOTION_LOCATOR_EVIDENCE_MAX_CANONICAL_FILE_BYTES,
                )
            )
            if current_raw is None or reason is not None:
                state = "review_pending"
                current_body = ""
                blocker_codes = ["current_canonical_unreadable"]
            else:
                _current_frontmatter, current_body = _zettel_parts(current_raw)
                current_count = current_body.count(marker)
                if current_count >= new_orphans:
                    state = "normal_maintain"
                    blocker_codes = []
                elif _sha(current_body.encode("utf-8")) == _sha(
                    after_body.encode("utf-8")
                ):
                    state = "restore_ready"
                    blocker_codes = []
                else:
                    state = "review_pending"
                    blocker_codes = ["current_body_diverged_after_transaction"]
            state_counts[state] += new_orphans
            target_ref = _sha(
                _canonical_bytes(
                    {
                        "archive_id": archive_id,
                        "zettel_id": item.get("zettel_id"),
                        "path": item.get("path"),
                    }
                )
            )
            item_ref = _sha(
                _canonical_bytes(
                    {
                        "receipt_sha256": receipt_sha256,
                        "transaction_ordinal": transaction_ordinal,
                        "target_ref": target_ref,
                        "orphan_row_count": new_orphans,
                    }
                )
            )
            public_items.append(
                {
                    "ordinal": len(public_items),
                    "item_ref_sha256": item_ref,
                    "state": state,
                    "orphan_row_count": new_orphans,
                    "blocker_codes": blocker_codes,
                }
            )
            if state == "restore_ready" and current_raw is not None:
                pre_value = _marker_projection(current_body)
                post_value = _marker_projection(before_body)
                source_value = _canonical_bytes(
                    {
                        "receipt_sha256": receipt_sha256,
                        "transaction_ordinal": transaction_ordinal,
                        "before_sha256": item.get("before_sha256"),
                        "after_sha256": item.get("after_sha256"),
                        "orphan_row_count": new_orphans,
                    }
                )
                identity = local_recovery_zettel_identity_sha256(
                    archive_id,
                    item["zettel_id"],
                    item["path"],
                )
                exact_item = ExactOperationItem(
                        ordinal=len(exact_items),
                        item_id=f"item:{transaction_ordinal:06d}",
                        target_kind="zettel",
                        target_ref=target_ref,
                        target_identity_sha256=identity,
                        fields=(
                            ExactFieldEffect(
                                field_ref=(
                                    "body.source_locator_omission_markers"
                                ),
                                pre_sha256=hash_field_value(pre_value),
                                post_sha256=hash_field_value(post_value),
                                source_sha256=hash_field_value(source_value),
                            ),
                        ),
                    )
                exact_items.append(exact_item)
                exact_specs.append(
                    LocalRecoveryFieldSpec(
                        item_id=exact_item.item_id,
                        target_kind=exact_item.target_kind,
                        target_ref=exact_item.target_ref,
                        target_identity_sha256=exact_item.target_identity_sha256,
                        field_ref=(
                            "body.source_locator_omission_markers"
                        ),
                        target_relative=item["path"],
                        zettel_id=item["zettel_id"],
                        pre_value=pre_value,
                        post_value=post_value,
                        source_value=source_value,
                        marker_pre_body=current_body,
                        marker_post_body=before_body,
                    )
                )
            completed = transaction_ordinal + 1
            if progress_callback is not None and (
                completed == 1
                or completed == len(receipt_rows)
                or completed % 100 == 0
            ):
                progress_callback(
                    "markup-orphan-classification",
                    "scanned",
                    completed,
                    len(receipt_rows),
                )
    except (archive_services.ArchiveServiceError, OSError, ValueError):
        blockers.append("local_locator_orphan_recovery_evidence_invalid")
    if progress_callback is not None:
        progress_callback(
            "markup-orphan-classification",
            "done",
            len(receipt_rows),
            len(receipt_rows),
        )

    orphan_row_count = sum(
        int(item["orphan_row_count"]) for item in public_items
    )
    if (
        expected_orphan_row_count is not None
        and int(expected_orphan_row_count) != orphan_row_count
    ):
        blockers.append("local_locator_expected_orphan_row_count_mismatch")
    if sum(state_counts.values()) != orphan_row_count:
        blockers.append("local_locator_orphan_classification_incomplete")
    digests = {
        "markup_receipt_set_sha256": _sha(
            _canonical_bytes(sorted(receipt_refs))
        ),
        "markup_transaction_item_set_sha256": _sha(
            _canonical_bytes(
                [
                    _sha(
                        _canonical_bytes(
                            {
                                "receipt_sha256": receipt_sha256,
                                "index": item.get("index"),
                                "before_sha256": item.get("before_sha256"),
                                "after_sha256": item.get("after_sha256"),
                            }
                        )
                    )
                    for receipt_sha256, item in receipt_rows
                ]
            )
        ),
        "orphan_row_set_sha256": _sha(
            _canonical_bytes(
                [
                    {
                        "item_ref_sha256": item["item_ref_sha256"],
                        "orphan_row_count": item["orphan_row_count"],
                    }
                    for item in public_items
                ]
            )
        ),
        "orphan_classification_set_sha256": _sha(
            _canonical_bytes(public_items)
        ),
        "restore_ready_set_sha256": _sha(
            _canonical_bytes(
                [
                    item["item_ref_sha256"]
                    for item in public_items
                    if item["state"] == "restore_ready"
                ]
            )
        ),
        "normal_maintain_set_sha256": _sha(
            _canonical_bytes(
                [
                    item["item_ref_sha256"]
                    for item in public_items
                    if item["state"] == "normal_maintain"
                ]
            )
        ),
        "review_pending_set_sha256": _sha(
            _canonical_bytes(
                [
                    item["item_ref_sha256"]
                    for item in public_items
                    if item["state"] == "review_pending"
                ]
            )
        ),
    }
    counts = {
        "markup_receipt_count": len(receipt_refs),
        "markup_transaction_item_count": len(receipt_rows),
        "removed_marker_count": removed_marker_count,
        "preexisting_orphan_row_count": preexisting_orphan_row_count,
        "orphan_zettel_count": len(public_items),
        "orphan_row_count": orphan_row_count,
        "classified_orphan_row_count": sum(state_counts.values()),
        "normal_maintain_count": state_counts["normal_maintain"],
        "restore_ready_count": state_counts["restore_ready"],
        "review_pending_count": state_counts["review_pending"],
    }
    operation_evidence = ExactOperationEvidence(
        schema="wom-kit/notion-locator-orphan-recovery-evidence/v1",
        counts=tuple(sorted(counts.items())),
        digests=tuple(sorted(digests.items())),
    )
    marker_item_count = len(exact_items)
    ledger_bytes = _canonical_bytes(
        {
            "schema": "wom-kit/notion-locator-orphan-recovery-ledger/v0.1",
            "archive_identity_sha256": (
                exact_human_approval_archive_identity_sha256(archive_id)
            ),
            "classification_items": public_items,
            "operation_evidence": operation_evidence.document(),
            "private_values_echoed": False,
        }
    ) + b"\n"
    ledger_relative = local_recovery_ledger_relative(
        "notion_locator_orphan",
        ledger_bytes,
    )
    ledger_identity = local_recovery_ledger_identity_sha256(
        archive_id,
        "notion_locator_orphan",
        ledger_relative,
    )
    ledger_source = _canonical_bytes(
        {
            "operation_evidence_sha256": operation_evidence.evidence_sha256,
            "markup_receipt_set_sha256": digests["markup_receipt_set_sha256"],
        }
    )
    ledger_item = ExactOperationItem(
        ordinal=len(exact_items),
        item_id=f"item:{orphan_row_count:06d}:classification",
        target_kind="local_recovery_ledger",
        target_ref=_sha(ledger_relative.encode("utf-8")),
        target_identity_sha256=ledger_identity,
        fields=(
            ExactFieldEffect(
                field_ref="classification.ledger",
                pre_sha256=hash_field_value(None),
                post_sha256=hash_field_value(ledger_bytes),
                source_sha256=hash_field_value(ledger_source),
            ),
        ),
    )
    exact_items.append(ledger_item)
    exact_specs.append(
        LocalRecoveryFieldSpec(
            item_id=ledger_item.item_id,
            target_kind=ledger_item.target_kind,
            target_ref=ledger_item.target_ref,
            target_identity_sha256=ledger_item.target_identity_sha256,
            field_ref="classification.ledger",
            target_relative=ledger_relative,
            zettel_id=None,
            pre_value=None,
            post_value=ledger_bytes,
            source_value=ledger_source,
        )
    )
    exact_manifest_object = None
    exact_manifest = None
    if not blockers:
        exact_manifest_object = ExactOperationManifest.build(
            operation=APPLY_OPERATION,
            archive_identity_sha256=(
                exact_human_approval_archive_identity_sha256(archive_id)
            ),
            items=exact_items,
            operation_evidence=operation_evidence,
        )
        exact_manifest = exact_manifest_object.document()
    returned_items = public_items[:returned_limit]
    if len(returned_items) < len(public_items):
        warnings.append("local_locator_orphan_items_truncated")
    result = {
        "ok": not blockers,
        "schema": ORPHAN_RECOVERY_SCHEMA,
        "lifecycle_action": "notion_locator_orphan_recovery_plan",
        "state": "blocked" if blockers else "classified",
        "dry_run": True,
        "summary": {
            **counts,
            **digests,
            "operation_evidence_sha256": operation_evidence.evidence_sha256,
            "exact_manifest_item_count": len(exact_items),
            "marker_restore_manifest_item_count": marker_item_count,
            "classification_ledger_item_count": 1,
            "returned_item_count": len(returned_items),
            "truncated_item_count": len(public_items) - len(returned_items),
            "expected_orphan_row_count": expected_orphan_row_count,
        },
        "items": returned_items,
        "exact_operation_manifest": exact_manifest,
        "blockers": archive_services.unique_preserve_order(blockers),
        "warnings": archive_services.unique_preserve_order(warnings),
        "would_change": (
            (
                (["body.source_locator_omission_markers"] if marker_item_count else [])
                + ["classification.ledger"]
            )
            if exact_manifest is not None
            else []
        ),
        "privacy_guards": _privacy_guards(),
    }
    if _build_execution:
        if exact_manifest_object is None:
            raise archive_services.ArchiveServiceError(
                "notion_locator_orphan_execution_blocked"
            )
        execution_warnings = []
        if state_counts["review_pending"]:
            execution_warnings.append("review_marker_rows_present")
        return build_local_recovery_plan(
            root,
            domain="notion_locator_orphan",
            manifest=exact_manifest_object,
            specs=exact_specs,
            warning_codes=execution_warnings,
            public_summary=result["summary"],
        )
    return result


def _privacy_guards() -> dict[str, bool]:
    return {
        "source_page_id_echoed": False,
        "locator_echoed": False,
        "locator_fingerprint_echoed": False,
        "zettel_id_echoed": False,
        "title_echoed": False,
        "body_echoed": False,
        "filename_or_path_echoed": False,
        "absolute_local_path_echoed": False,
        "source_snapshot_contents_echoed": False,
        "provider_api_called": False,
        "writes": False,
    }


def notion_locator_mirror_recovery_execution_plan(
    archive_root: Path | str,
    *,
    source_mirror: Path | str,
    max_items: int = 200,
    expected_zettel_count: int | None = None,
    expected_pair_count: int | None = None,
    progress_callback: Callable[[str, str, int | None, int | None], None]
    | None = None,
) -> LocalRecoveryPlan:
    plan = notion_locator_mirror_recovery_plan(
        archive_root,
        source_mirror=source_mirror,
        dry_run=True,
        max_items=max_items,
        expected_zettel_count=expected_zettel_count,
        expected_pair_count=expected_pair_count,
        progress_callback=progress_callback,
        _build_execution=True,
    )
    if type(plan) is not LocalRecoveryPlan:
        raise archive_services.ArchiveServiceError(
            "notion_locator_mirror_execution_blocked"
        )
    return plan


def notion_locator_orphan_recovery_execution_plan(
    archive_root: Path | str,
    *,
    markup_receipts: list[str],
    max_items: int = 200,
    expected_orphan_row_count: int | None = None,
    progress_callback: Callable[[str, str, int | None, int | None], None]
    | None = None,
) -> LocalRecoveryPlan:
    plan = notion_locator_orphan_recovery_plan(
        archive_root,
        markup_receipts=markup_receipts,
        dry_run=True,
        max_items=max_items,
        expected_orphan_row_count=expected_orphan_row_count,
        progress_callback=progress_callback,
        _build_execution=True,
    )
    if type(plan) is not LocalRecoveryPlan:
        raise archive_services.ArchiveServiceError(
            "notion_locator_orphan_execution_blocked"
        )
    return plan


def notion_locator_local_recovery_execution_plan(
    archive_root: Path | str,
    *,
    source_mirror: Path | str,
    markup_receipts: list[str],
    max_items: int = 200,
    expected_zettel_count: int | None = None,
    expected_pair_count: int | None = None,
    expected_orphan_row_count: int | None = None,
    progress_callback: Callable[[str, str, int | None, int | None], None]
    | None = None,
) -> LocalRecoveryPlan:
    mirror = notion_locator_mirror_recovery_execution_plan(
        archive_root,
        source_mirror=source_mirror,
        max_items=max_items,
        expected_zettel_count=expected_zettel_count,
        expected_pair_count=expected_pair_count,
        progress_callback=progress_callback,
    )
    orphan = notion_locator_orphan_recovery_execution_plan(
        archive_root,
        markup_receipts=markup_receipts,
        max_items=max_items,
        expected_orphan_row_count=expected_orphan_row_count,
        progress_callback=progress_callback,
    )
    return combine_local_recovery_plans(
        (mirror, orphan),
        domain="notion_locator_local_recovery",
        public_summary={
            "locator_pair_count": mirror.public_summary.get(
                "locator_pair_count", 0
            ),
            "locator_record_count": mirror.public_summary.get(
                "locator_record_manifest_item_count", 0
            ),
            "orphan_row_count": orphan.public_summary.get(
                "orphan_row_count", 0
            ),
            "marker_restore_count": orphan.public_summary.get(
                "marker_restore_manifest_item_count", 0
            ),
        },
    )


__all__ = [
    "notion_locator_local_recovery_execution_plan",
    "notion_locator_mirror_recovery_execution_plan",
    "notion_locator_mirror_recovery_plan",
    "notion_locator_orphan_recovery_execution_plan",
    "notion_locator_orphan_recovery_plan",
]
