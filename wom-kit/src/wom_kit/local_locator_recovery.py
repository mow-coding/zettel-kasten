"""Read-only, receipt-bound recovery planning for imported locator loss.

The public surface of this module is content-free.  Source page identifiers,
provider URLs, zettel identifiers, titles, bodies, and absolute paths are used
only inside the planner and are replaced by SHA-256 references in its result.
No provider is contacted and no archive byte is written.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from . import archive_services, completion_workflows
from .exact_human_approval import (
    audit_exact_human_approval_succeeded_terminal_record_read_only,
    exact_human_approval_archive_identity_sha256,
)
from .exact_human_approval_windows import ExactHumanApprovalOperation
from .exact_operation_manifest import (
    EXACT_OPERATION_RECEIPTS_ROOT,
    ExactFieldEffect,
    ExactOperationEvidence,
    ExactOperationItem,
    ExactOperationManifest,
    ExactOperationManifestError,
    _load_exact_operation_checkpoints_read_only,
    exact_operation_completion_authentication_payload,
    hash_field_value,
    load_exact_operation_final_receipt_read_only,
)
from .local_recovery_execution import (
    APPLY_OPERATION,
    LEDGER_ROOT,
    LocalRecoveryFieldSpec,
    LocalRecoveryPlan,
    _marker_projection as _execution_marker_projection,
    build_local_recovery_plan,
    combine_local_recovery_plans,
    local_recovery_ledger_identity_sha256,
    local_recovery_ledger_relative,
    local_recovery_zettel_identity_sha256,
)


MIRROR_RECOVERY_SCHEMA = "wom-kit/notion-locator-mirror-recovery-plan/v0.1"
ORPHAN_RECOVERY_SCHEMA = "wom-kit/notion-locator-orphan-recovery-plan/v0.1"
ORPHAN_RECOVERY_LEDGER_SCHEMA = (
    "wom-kit/notion-locator-orphan-recovery-ledger/v0.2"
)
ORPHAN_RECOVERY_LEGACY_LEDGER_SCHEMAS = frozenset(
    {"wom-kit/notion-locator-orphan-recovery-ledger/v0.1"}
)
ORPHAN_RECOVERY_EVIDENCE_SCHEMA = (
    "wom-kit/notion-locator-orphan-recovery-evidence/v1"
)
COMPOSITE_LOCAL_RECOVERY_EVIDENCE_SCHEMA = (
    "wom-kit/local-recovery-composite-evidence/v1"
)
MAX_MIRROR_BYTES = 64 * 1024 * 1024
MAX_MIRROR_ROWS = 10_000
MAX_MIRROR_LINE_BYTES = 16 * 1024 * 1024
MAX_MARKUP_RECEIPTS = 100
MAX_MARKUP_BINDING_MANIFESTS = 100
MAX_VERIFIED_RESOLUTION_LEDGERS = 4096
MAX_EXACT_OPERATION_RECEIPTS = 4096
MAX_RETURNED_ITEMS = 10_000
_MARKUP_BINDING_MANIFEST_ROOT = ".wom-scratch/markup-bindings"
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


def discover_markup_normalization_receipts(
    archive_root: Path | str,
) -> list[str]:
    """Return every canonical markup receipt without exposing file names.

    This is the operator-friendly replacement for manually counting or
    copying receipt paths.  Only the fixed receipt directory and exact
    64-hex filenames are accepted; malformed or excessive inventories stop
    the whole discovery instead of silently selecting a subset.
    """

    root = archive_services.require_existing_archive_root(archive_root)
    directory = archive_services.archive_internal_path(
        root,
        "receipts/markup-normalization",
    )
    entries = _safe_private_entries(
        directory,
        maximum=MAX_MARKUP_RECEIPTS,
        missing_ok=False,
    )
    relatives: list[str] = []
    for path in entries:
        relative = archive_services.archive_relative_path(path, root)
        raw, reason = archive_services._bounded_stable_regular_file_read(
            path,
            max_bytes=64 * 1024 * 1024,
        )
        if (
            _MARKUP_RECEIPT_RE.fullmatch(relative) is None
            or raw is None
            or reason is not None
        ):
            raise archive_services.ArchiveServiceError(
                "local_locator_markup_receipt_inventory_invalid"
            )
        relatives.append(relative)
    if not relatives:
        raise archive_services.ArchiveServiceError(
            "local_locator_markup_receipt_inventory_empty"
        )
    return sorted(relatives)


def _plain_private_directory(path: Path) -> bool:
    try:
        info = os.lstat(path)
    except OSError:
        return False
    return bool(
        stat.S_ISDIR(info.st_mode)
        and not stat.S_ISLNK(info.st_mode)
        and not bool(getattr(info, "st_file_attributes", 0) & 0x400)
    )


def _receipt_reference_bindings(
    root: Path,
    receipt: dict[str, Any],
    *,
    validation_context: dict[str, Any],
    progress_callback: Callable[[str, str, int | None, int | None], None]
    | None = None,
) -> tuple[
    dict[str, dict[str, dict[int | None, dict[str, Any]]]],
    str | None,
]:
    """Load the one hash-bound historical binding manifest, if declared.

    The operator is never asked to locate or compare this private file.  WOM
    searches only the fixed ignored-local binding directory, requires one
    unique byte-for-byte SHA-256 match, and then reuses the original strict
    binding validator against the current archive.
    """

    expected = receipt.get("binding_manifest_sha256")
    if expected is None:
        return {}, None
    if (
        not isinstance(expected, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected) is None
    ):
        raise archive_services.ArchiveServiceError(
            "local_locator_markup_binding_evidence_invalid"
        )
    directory = archive_services.archive_internal_path(
        root,
        _MARKUP_BINDING_MANIFEST_ROOT,
    )
    if not _plain_private_directory(directory):
        raise archive_services.ArchiveServiceError(
            "local_locator_markup_binding_evidence_missing"
        )
    try:
        entries = tuple(sorted(directory.iterdir(), key=lambda path: path.name))
    except OSError as exc:
        raise archive_services.ArchiveServiceError(
            "local_locator_markup_binding_evidence_invalid"
        ) from exc
    if len(entries) > MAX_MARKUP_BINDING_MANIFESTS:
        raise archive_services.ArchiveServiceError(
            "local_locator_markup_binding_evidence_invalid"
        )
    matches: list[Path] = []
    for path in entries:
        if path.suffix.casefold() != ".json":
            continue
        raw, reason = archive_services._bounded_stable_regular_file_read(
            path,
            max_bytes=64 * 1024 * 1024,
        )
        if raw is None or reason is not None:
            raise archive_services.ArchiveServiceError(
                "local_locator_markup_binding_evidence_invalid"
            )
        if hashlib.sha256(raw).hexdigest() == expected:
            matches.append(path)
    if len(matches) != 1:
        raise archive_services.ArchiveServiceError(
            "local_locator_markup_binding_evidence_missing"
            if not matches
            else "local_locator_markup_binding_evidence_ambiguous"
        )
    bindings, actual, blockers = completion_workflows._markup_reference_bindings(
        root,
        binding_manifest=matches[0],
        validation_context=validation_context,
        progress_callback=progress_callback,
    )
    if actual != expected or blockers:
        raise archive_services.ArchiveServiceError(
            "local_locator_markup_binding_evidence_invalid"
        )
    return bindings, expected


def _path_bound_reference_bindings(
    all_bindings: dict[
        str,
        dict[str, dict[int | None, dict[str, Any]]],
    ],
    *,
    zettel_id: str,
    relative_path: str,
) -> dict[str, dict[int | None, dict[str, Any]]]:
    bound: dict[str, dict[int | None, dict[str, Any]]] = {}
    for tag_sha256, selectors in all_bindings.get(zettel_id, {}).items():
        selected = {
            selector: binding
            for selector, binding in selectors.items()
            if binding.get("source_relative_path") == relative_path
        }
        if selected:
            bound[tag_sha256] = selected
    return bound


def _trace_binding_replacement(
    trace: dict[str, Any],
    bindings: dict[str, dict[int | None, dict[str, Any]]],
) -> str | None:
    tag_sha256 = trace.get("tag_sha256")
    occurrence_index = trace.get("occurrence_index")
    if (
        not isinstance(tag_sha256, str)
        or type(occurrence_index) is not int
    ):
        return None
    selectors = bindings.get(tag_sha256, {})
    binding = selectors.get(occurrence_index)
    if binding is None:
        binding = selectors.get(None)
    if not isinstance(binding, dict):
        return None
    replacement = binding.get("replacement")
    if (
        not isinstance(replacement, str)
        or completion_workflows._sha256_bytes(replacement.encode("utf-8"))
        != trace.get("replacement_sha256")
        or binding.get("binding_kind") != trace.get("binding_kind")
        or binding.get("binding_id") != trace.get("binding_id")
    ):
        return None
    return replacement


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
    return _execution_marker_projection(body)


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

    receipt_rows: list[
        tuple[
            str,
            dict[str, Any],
            dict[str, dict[str, dict[int | None, dict[str, Any]]]],
            str | None,
        ]
    ] = []
    receipt_refs: list[str] = []
    binding_manifest_refs: list[str] = []
    binding_validation_context: dict[str, Any] = {}
    try:
        for receipt_relative in sorted(markup_receipts):
            receipt_raw, receipt = _read_markup_receipt(
                root,
                receipt_relative,
                archive_id=archive_id,
            )
            receipt_sha256 = _sha(receipt_raw)
            receipt_refs.append(receipt_sha256)
            receipt_bindings, binding_manifest_sha256 = (
                _receipt_reference_bindings(
                    root,
                    receipt,
                    validation_context=binding_validation_context,
                    progress_callback=progress_callback,
                )
            )
            if binding_manifest_sha256 is not None:
                binding_manifest_refs.append(
                    "sha256:" + binding_manifest_sha256
                )
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
                receipt_rows.append(
                    (
                        receipt_sha256,
                        item,
                        receipt_bindings,
                        binding_manifest_sha256,
                    )
                )
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
        "resolved_by_verified_reference": 0,
        "restore_ready": 0,
        "review_pending": 0,
    }
    ledger_items: list[dict[str, Any]] = []
    orphan_target_identities: set[str] = set()
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
            receipt_bindings,
            binding_manifest_sha256,
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
            marker_only_transition = bool(
                before_body.replace(marker, "")
                == after_body.replace(marker, "")
            )
            removed_marker_count += max(0, before_count - after_count)
            preexisting_orphan_row_count += max(0, declared - before_count)
            new_orphans = max(
                0,
                min(declared, before_count) - min(declared, after_count),
            )
            if new_orphans <= 0 or after_count != 0:
                continue

            path_bound_bindings = _path_bound_reference_bindings(
                receipt_bindings,
                zettel_id=str(expected_zettel_id),
                relative_path=str(item.get("path") or ""),
            )
            replay = completion_workflows._normalize_markup_body(
                before_body,
                bindings=path_bound_bindings,
            )
            replay_exact = bool(
                not replay.get("blocker_codes")
                and replay.get("normalized_body") == after_body
            )
            applied_binding_traces = [
                trace
                for trace in replay.get("applied_reference_bindings", [])
                if isinstance(trace, dict)
            ]
            marker_binding_traces = [
                trace
                for trace in applied_binding_traces
                if int(trace.get("source_omission_marker_count") or 0) > 0
            ]
            verified_reference_marker_count = sum(
                int(trace.get("source_omission_marker_count") or 0)
                for trace in marker_binding_traces
            )
            verified_replacements: list[str] = []
            trace_invalid = False
            for trace in marker_binding_traces:
                replacement = _trace_binding_replacement(
                    trace,
                    path_bound_bindings,
                )
                if (
                    replacement is None
                    or int(
                        trace.get("replacement_omission_marker_count") or 0
                    )
                    != 0
                ):
                    trace_invalid = True
                    break
                verified_replacements.append(replacement)
            verified_reference_resolution_candidate = bool(
                replay_exact
                and not trace_invalid
                and before_count - after_count == new_orphans
                and marker_binding_traces
                and 0 < verified_reference_marker_count <= new_orphans
            )
            verified_reference_resolved_count = 0
            review_pending_orphan_count = 0

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
                current_declared = None
                blocker_codes = ["current_canonical_unreadable"]
            else:
                current_frontmatter, current_body = _zettel_parts(current_raw)
                current_count = current_body.count(marker)
                current_declared = (
                    archive_services.notion_import_locator_omitted_count(
                        current_frontmatter
                    )
                )
                current_canonical_identity_matches = bool(
                    current_frontmatter.get("id") == expected_zettel_id
                    and current_frontmatter.get("archive_id") == archive_id
                    and current_frontmatter.get("status") == "canonical"
                )
                current_omission_identity_matches = bool(
                    archive_services.notion_import_frontmatter_is_notion(
                        current_frontmatter
                    )
                    and current_declared == declared
                )
                if not current_canonical_identity_matches:
                    state = "review_pending"
                    blocker_codes = ["current_canonical_identity_changed"]
                elif not current_omission_identity_matches:
                    state = "review_pending"
                    blocker_codes = ["current_omission_identity_changed"]
                elif _marker_projection(current_body) == _marker_projection(
                    before_body
                ):
                    state = "normal_maintain"
                    blocker_codes = []
                elif (
                    current_count == after_count
                    and current_body == after_body
                    and verified_reference_resolution_candidate
                ):
                    verified_reference_resolved_count = (
                        verified_reference_marker_count
                    )
                    review_pending_orphan_count = (
                        new_orphans - verified_reference_resolved_count
                    )
                    state = (
                        "resolved_by_verified_reference"
                        if review_pending_orphan_count == 0
                        else "partially_resolved_by_verified_reference"
                    )
                    blocker_codes = (
                        []
                        if review_pending_orphan_count == 0
                        else [
                            "verified_reference_marker_coverage_incomplete"
                        ]
                    )
                elif (
                    current_count == after_count
                    and current_body == after_body
                    and marker_only_transition
                    and before_count - after_count == new_orphans
                ):
                    state = "restore_ready"
                    blocker_codes = []
                else:
                    state = "review_pending"
                    blocker_codes = []
                    if not marker_only_transition:
                        blocker_codes.append(
                            "markup_changed_more_than_omission_markers"
                        )
                    if before_count - after_count != new_orphans:
                        blocker_codes.append(
                            "removed_marker_count_disagrees_with_orphan_rows"
                        )
                    if current_body != after_body:
                        blocker_codes.append(
                            "current_body_diverged_after_transaction"
                        )
                    if not replay_exact:
                        blocker_codes.append(
                            "historical_markup_transaction_not_exactly_replayable"
                        )
                    if verified_reference_marker_count:
                        blocker_codes.append(
                            "verified_reference_marker_coverage_incomplete"
                        )
            if state == "normal_maintain":
                state_counts["normal_maintain"] += new_orphans
            elif state == "restore_ready":
                state_counts["restore_ready"] += new_orphans
            elif state in {
                "resolved_by_verified_reference",
                "partially_resolved_by_verified_reference",
            }:
                state_counts["resolved_by_verified_reference"] += (
                    verified_reference_resolved_count
                )
                state_counts["review_pending"] += review_pending_orphan_count
            else:
                review_pending_orphan_count = new_orphans
                state_counts["review_pending"] += new_orphans
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
                    "verified_reference_binding_count": len(
                        marker_binding_traces
                    ),
                    "verified_reference_marker_count": (
                        verified_reference_marker_count
                    ),
                    "verified_reference_resolved_count": (
                        verified_reference_resolved_count
                    ),
                    "review_pending_orphan_count": (
                        review_pending_orphan_count
                    ),
                    "blocker_codes": blocker_codes,
                }
            )
            target_identity = local_recovery_zettel_identity_sha256(
                archive_id,
                str(item["zettel_id"]),
                str(item["path"]),
            )
            orphan_target_identities.add(target_identity)
            ledger_items.append(
                {
                    "ordinal": len(public_items) - 1,
                    "item_ref_sha256": item_ref,
                    "target_identity_sha256": target_identity,
                    "state": state,
                    "orphan_row_count": new_orphans,
                    "verified_reference_marker_count": (
                        verified_reference_marker_count
                    ),
                    "verified_reference_binding_count": len(
                        marker_binding_traces
                    ),
                    "verified_reference_resolved_count": (
                        verified_reference_resolved_count
                    ),
                    "review_pending_orphan_count": (
                        review_pending_orphan_count
                    ),
                    "declared_omission_count": declared,
                    "blocker_codes": blocker_codes,
                    "current_body_sha256": (
                        _sha(current_body.encode("utf-8"))
                        if current_raw is not None
                        else None
                    ),
                    "expected_post_body_sha256": (
                        _sha(
                            (
                                before_body
                                if state == "restore_ready"
                                else current_body
                            ).encode("utf-8")
                        )
                        if current_raw is not None
                        else None
                    ),
                    "historical_after_body_sha256": _sha(
                        after_body.encode("utf-8")
                    ),
                    "receipt_sha256": receipt_sha256,
                    "binding_manifest_sha256": (
                        "sha256:" + binding_manifest_sha256
                        if binding_manifest_sha256 is not None
                        else None
                    ),
                    "verified_replacement_set_sha256": _sha(
                        _canonical_bytes(sorted(verified_replacements))
                    ),
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
                exact_item = ExactOperationItem(
                        ordinal=len(exact_items),
                        item_id=f"item:{transaction_ordinal:06d}",
                        target_kind="zettel",
                        target_ref=target_ref,
                        target_identity_sha256=target_identity,
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
        "binding_manifest_set_sha256": _sha(
            _canonical_bytes(sorted(binding_manifest_refs))
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
                    for (
                        receipt_sha256,
                        item,
                        _receipt_bindings,
                        _binding_manifest_sha256,
                    ) in receipt_rows
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
        "resolved_by_verified_reference_set_sha256": _sha(
            _canonical_bytes(
                [
                    item["item_ref_sha256"]
                    for item in public_items
                    if int(
                        item.get("verified_reference_resolved_count") or 0
                    )
                    > 0
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
                    if int(item.get("review_pending_orphan_count") or 0) > 0
                ]
            )
        ),
    }
    counts = {
        "markup_receipt_count": len(receipt_refs),
        "markup_transaction_item_count": len(receipt_rows),
        "removed_marker_count": removed_marker_count,
        "preexisting_orphan_row_count": preexisting_orphan_row_count,
        "orphan_zettel_count": len(orphan_target_identities),
        "orphan_row_count": orphan_row_count,
        "classified_orphan_row_count": sum(state_counts.values()),
        "normal_maintain_count": state_counts["normal_maintain"],
        "resolved_by_verified_reference_count": state_counts[
            "resolved_by_verified_reference"
        ],
        "restore_ready_count": state_counts["restore_ready"],
        "review_pending_count": state_counts["review_pending"],
    }
    operation_evidence = ExactOperationEvidence(
        schema=ORPHAN_RECOVERY_EVIDENCE_SCHEMA,
        counts=tuple(sorted(counts.items())),
        digests=tuple(sorted(digests.items())),
    )
    marker_item_count = len(exact_items)
    ledger_bytes = _canonical_bytes(
        {
            "schema": ORPHAN_RECOVERY_LEDGER_SCHEMA,
            "archive_identity_sha256": (
                exact_human_approval_archive_identity_sha256(archive_id)
            ),
            "classification_items": ledger_items,
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


def _safe_private_entries(
    directory: Path,
    *,
    maximum: int,
    missing_ok: bool,
) -> tuple[Path, ...]:
    if not directory.exists():
        if missing_ok:
            return ()
        raise archive_services.ArchiveServiceError(
            "local_locator_resolution_evidence_invalid"
        )
    if not _plain_private_directory(directory):
        raise archive_services.ArchiveServiceError(
            "local_locator_resolution_evidence_invalid"
        )
    try:
        entries = tuple(sorted(directory.iterdir(), key=lambda path: path.name))
    except OSError as exc:
        raise archive_services.ArchiveServiceError(
            "local_locator_resolution_evidence_invalid"
        ) from exc
    if len(entries) > maximum:
        raise archive_services.ArchiveServiceError(
            "local_locator_resolution_evidence_invalid"
        )
    return entries


def _receipt_orphan_evidence_refs(
    evidence: ExactOperationEvidence,
) -> tuple[str, ...]:
    """Return orphan-member evidence hashes carried by one exact receipt.

    A standalone orphan recovery carries its evidence directly.  The combined
    locator recovery rewrites the outer manifest with composite evidence, so
    the original orphan evidence is carried under a deterministic member key.
    Only these two fixed schemas are eligible; legacy or unrelated evidence is
    ignored rather than promoted into resolution proof.
    """

    if evidence.schema == ORPHAN_RECOVERY_EVIDENCE_SCHEMA:
        return (evidence.evidence_sha256,)
    if evidence.schema != COMPOSITE_LOCAL_RECOVERY_EVIDENCE_SCHEMA:
        return ()
    digests = dict(evidence.digests)
    refs = [
        value
        for key, value in sorted(digests.items())
        if re.fullmatch(r"member_[0-9]{2}_evidence_sha256", key)
    ]
    return tuple(dict.fromkeys(refs))


def _merge_verified_resolution_candidate(
    by_target: dict[str, dict[str, Any]],
    conflicted_targets: set[str],
    *,
    target_identity: str,
    candidate: dict[str, Any],
) -> bool:
    """Merge one target result and remove all trust after a disagreement.

    Returns ``True`` only when this call newly discovers a conflict.  Once a
    target conflicts, later identical rows cannot accidentally reinstate it.
    """

    if target_identity in conflicted_targets:
        return False
    previous = by_target.get(target_identity)
    if previous is not None and previous != candidate:
        by_target.pop(target_identity, None)
        conflicted_targets.add(target_identity)
        return True
    by_target[target_identity] = candidate
    return False


def _verified_resolution_receipts_by_evidence(
    root: Path,
    *,
    claim_key_provider: Any | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], list[str], int]:
    """Index completed, approved exact-operation receipts by evidence hash."""

    directory = archive_services.archive_internal_path(
        root,
        EXACT_OPERATION_RECEIPTS_ROOT,
    )
    try:
        entries = _safe_private_entries(
            directory,
            maximum=MAX_EXACT_OPERATION_RECEIPTS,
            missing_ok=True,
        )
    except archive_services.ArchiveServiceError:
        return {}, ["local_locator_resolution_receipt_scan_invalid"], 0
    indexed: dict[str, list[dict[str, Any]]] = {}
    scanned = 0
    for path in entries:
        match = re.fullmatch(r"([0-9a-f]{64})\.json", path.name)
        if match is None:
            return {}, ["local_locator_resolution_receipt_scan_invalid"], scanned
        execution_sha256 = "sha256:" + match.group(1)
        try:
            receipt = load_exact_operation_final_receipt_read_only(
                root,
                execution_sha256,
            )
        except (ExactOperationManifestError, OSError, ValueError):
            return {}, ["local_locator_resolution_receipt_scan_invalid"], scanned
        scanned += 1
        if receipt is None:
            return {}, ["local_locator_resolution_receipt_scan_invalid"], scanned
        result = receipt.get("result")
        if not isinstance(result, dict):
            return {}, ["local_locator_resolution_receipt_scan_invalid"], scanned
        evidence_document = result.get("operation_evidence")
        if not isinstance(evidence_document, dict):
            continue
        try:
            evidence = ExactOperationEvidence.from_document(
                evidence_document
            )
        except ExactOperationManifestError:
            return {}, ["local_locator_resolution_receipt_scan_invalid"], scanned
        evidence_refs = _receipt_orphan_evidence_refs(evidence)
        if not evidence_refs:
            continue
        approval_binding = result.get("approval_binding_sha256")
        completion_authentication = result.get("completion_authentication")
        if (
            result.get("status") != "completed"
            or result.get("mode") != "apply"
            or not isinstance(approval_binding, str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", approval_binding) is None
            or not isinstance(completion_authentication, dict)
            or completion_authentication.get("operation") != APPLY_OPERATION
            or not isinstance(
                completion_authentication.get("approval_reference"),
                dict,
            )
            or not isinstance(
                completion_authentication.get("target_binding_sha256"),
                str,
            )
            or not isinstance(
                completion_authentication.get("terminal_mac"),
                str,
            )
        ):
            continue
        try:
            completion_payload = (
                exact_operation_completion_authentication_payload(result)
            )
        except ExactOperationManifestError:
            continue
        if not audit_exact_human_approval_succeeded_terminal_record_read_only(
            root,
            completion_authentication["approval_reference"],
            expected_operation=ExactHumanApprovalOperation.local_recovery,
            expected_plan_sha256=result.get("manifest_sha256"),
            expected_target_binding_sha256=completion_authentication[
                "target_binding_sha256"
            ],
            payload=completion_payload,
            expected_mac=completion_authentication["terminal_mac"],
            key_provider=claim_key_provider,
        ):
            continue
        try:
            checkpoints = _load_exact_operation_checkpoints_read_only(
                root,
                execution_sha256,
                heartbeat=None,
            )
        except (ExactOperationManifestError, OSError, ValueError):
            return {}, ["local_locator_resolution_receipt_scan_invalid"], scanned
        candidate = {
            "result": result,
            "checkpoints": checkpoints,
        }
        for evidence_ref in evidence_refs:
            indexed.setdefault(evidence_ref, []).append(candidate)
    return indexed, [], scanned


def verified_notion_locator_resolution_evidence(
    archive_root: Path | str,
    *,
    _claim_key_provider: Any | None = None,
) -> dict[str, Any]:
    """Read completed resolution ledgers without exposing target identities.

    The returned ``by_target_identity`` map is private in-process evidence for
    the locator-loss audit.  Callers must never serialize it.  Every accepted
    ledger is byte-hashed, self-consistent with its operation evidence, and
    paired with the approved exact-operation final receipt and checkpoint that
    independently observed the ledger write.
    """

    root = archive_services.require_existing_archive_root(archive_root)
    archive_id = archive_services.read_archive_id(root)
    archive_identity = exact_human_approval_archive_identity_sha256(archive_id)
    receipts_by_evidence, blockers, receipt_count = (
        _verified_resolution_receipts_by_evidence(
            root,
            claim_key_provider=_claim_key_provider,
        )
    )
    directory = archive_services.archive_internal_path(
        root,
        f"{LEDGER_ROOT}/notion_locator_orphan",
    )
    try:
        entries = _safe_private_entries(
            directory,
            maximum=MAX_VERIFIED_RESOLUTION_LEDGERS,
            missing_ok=True,
        )
    except archive_services.ArchiveServiceError:
        entries = ()
        blockers.append("local_locator_resolution_ledger_scan_invalid")

    by_target: dict[str, dict[str, Any]] = {}
    conflicted_targets: set[str] = set()
    verified_ledger_count = 0
    skipped_legacy_ledger_count = 0
    for path in entries:
        match = re.fullmatch(r"([0-9a-f]{64})\.json", path.name)
        raw, reason = archive_services._bounded_stable_regular_file_read(
            path,
            max_bytes=64 * 1024 * 1024,
        )
        if (
            match is None
            or raw is None
            or reason is not None
            or not raw.endswith(b"\n")
            or hashlib.sha256(raw).hexdigest() != match.group(1)
        ):
            blockers.append("local_locator_resolution_ledger_scan_invalid")
            continue
        try:
            document = json.loads(
                raw[:-1].decode("ascii"),
                object_pairs_hook=_reject_duplicate_pairs,
                parse_constant=_reject_nonfinite,
            )
        except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError):
            blockers.append("local_locator_resolution_ledger_scan_invalid")
            continue
        if (
            not isinstance(document, dict)
            or _canonical_bytes(document) + b"\n" != raw
        ):
            blockers.append("local_locator_resolution_ledger_scan_invalid")
            continue
        if document.get("schema") in ORPHAN_RECOVERY_LEGACY_LEDGER_SCHEMAS:
            if (
                document.get("archive_identity_sha256") == archive_identity
                and document.get("private_values_echoed") is False
            ):
                skipped_legacy_ledger_count += 1
            else:
                blockers.append("local_locator_resolution_ledger_scan_invalid")
            continue
        if (
            set(document)
            != {
                "schema",
                "archive_identity_sha256",
                "classification_items",
                "operation_evidence",
                "private_values_echoed",
            }
            or document.get("schema") != ORPHAN_RECOVERY_LEDGER_SCHEMA
            or document.get("archive_identity_sha256") != archive_identity
            or document.get("private_values_echoed") is not False
            or not isinstance(document.get("classification_items"), list)
            or len(document["classification_items"]) > MAX_RETURNED_ITEMS
        ):
            blockers.append("local_locator_resolution_ledger_scan_invalid")
            continue
        try:
            evidence = ExactOperationEvidence.from_document(
                document["operation_evidence"]
            )
        except (ExactOperationManifestError, KeyError, TypeError):
            blockers.append("local_locator_resolution_ledger_scan_invalid")
            continue
        if evidence.schema != ORPHAN_RECOVERY_EVIDENCE_SCHEMA:
            blockers.append("local_locator_resolution_ledger_scan_invalid")
            continue
        candidates = receipts_by_evidence.get(evidence.evidence_sha256, [])
        ledger_field_hash = hash_field_value(raw)
        completed = [
            candidate
            for candidate in candidates
            if sum(
                1
                for row in candidate["checkpoints"]
                if row.get("stage") == "field_verified"
                and row.get("field_ref") == "classification.ledger"
                and row.get("observed_sha256") == ledger_field_hash
            )
            == 1
        ]
        if not completed:
            blockers.append("local_locator_resolution_receipt_missing")
            continue

        public_projection: list[dict[str, Any]] = []
        ledger_valid = True
        resolved_rows: list[dict[str, Any]] = []
        auditable_rows: list[dict[str, Any]] = []
        expected_item_keys = {
            "ordinal",
            "item_ref_sha256",
            "target_identity_sha256",
            "state",
            "orphan_row_count",
            "verified_reference_marker_count",
            "verified_reference_binding_count",
            "verified_reference_resolved_count",
            "review_pending_orphan_count",
            "declared_omission_count",
            "blocker_codes",
            "current_body_sha256",
            "expected_post_body_sha256",
            "historical_after_body_sha256",
            "receipt_sha256",
            "binding_manifest_sha256",
            "verified_replacement_set_sha256",
        }
        for ordinal, item in enumerate(document["classification_items"]):
            if not isinstance(item, dict) or set(item) != expected_item_keys:
                ledger_valid = False
                break
            public_projection.append(
                {
                    "ordinal": item.get("ordinal"),
                    "item_ref_sha256": item.get("item_ref_sha256"),
                    "state": item.get("state"),
                    "orphan_row_count": item.get("orphan_row_count"),
                    "verified_reference_binding_count": item.get(
                        "verified_reference_binding_count"
                    ),
                    "verified_reference_marker_count": item.get(
                        "verified_reference_marker_count"
                    ),
                    "verified_reference_resolved_count": item.get(
                        "verified_reference_resolved_count"
                    ),
                    "review_pending_orphan_count": item.get(
                        "review_pending_orphan_count"
                    ),
                    "blocker_codes": item.get("blocker_codes"),
                }
            )
            if (
                item.get("ordinal") != ordinal
                or re.fullmatch(
                    r"sha256:[0-9a-f]{64}",
                    str(item.get("item_ref_sha256") or ""),
                )
                is None
                or re.fullmatch(
                    r"sha256:[0-9a-f]{64}",
                    str(item.get("target_identity_sha256") or ""),
                )
                is None
                or type(item.get("orphan_row_count")) is not int
                or int(item["orphan_row_count"]) <= 0
                or type(item.get("verified_reference_marker_count")) is not int
                or int(item["verified_reference_marker_count"]) < 0
                or type(item.get("verified_reference_binding_count")) is not int
                or int(item["verified_reference_binding_count"]) < 0
                or type(item.get("verified_reference_resolved_count"))
                is not int
                or int(item["verified_reference_resolved_count"]) < 0
                or type(item.get("review_pending_orphan_count")) is not int
                or int(item["review_pending_orphan_count"]) < 0
                or type(item.get("declared_omission_count")) is not int
                or int(item["declared_omission_count"])
                < int(item["orphan_row_count"])
                or not isinstance(item.get("blocker_codes"), list)
                or item.get("state")
                not in {
                    "normal_maintain",
                    "resolved_by_verified_reference",
                    "partially_resolved_by_verified_reference",
                    "restore_ready",
                    "review_pending",
                }
            ):
                ledger_valid = False
                break
            resolved_count = int(item["verified_reference_resolved_count"])
            review_count = int(item["review_pending_orphan_count"])
            if item.get("state") in {
                "resolved_by_verified_reference",
                "partially_resolved_by_verified_reference",
            }:
                if (
                    resolved_count <= 0
                    or resolved_count + review_count
                    != item["orphan_row_count"]
                    or (
                        item.get("state")
                        == "resolved_by_verified_reference"
                        and review_count != 0
                    )
                    or (
                        item.get("state")
                        == "partially_resolved_by_verified_reference"
                        and review_count <= 0
                    )
                ):
                    ledger_valid = False
                    break
            elif item.get("state") == "review_pending":
                if resolved_count != 0 or review_count != item["orphan_row_count"]:
                    ledger_valid = False
                    break
            elif resolved_count != 0 or review_count != 0:
                ledger_valid = False
                break
            current_body_sha256 = item.get("current_body_sha256")
            expected_post_body_sha256 = item.get(
                "expected_post_body_sha256"
            )
            current_body_readable = bool(
                re.fullmatch(
                    r"sha256:[0-9a-f]{64}",
                    str(current_body_sha256 or ""),
                )
            )
            expected_post_body_readable = bool(
                re.fullmatch(
                    r"sha256:[0-9a-f]{64}",
                    str(expected_post_body_sha256 or ""),
                )
            )
            if current_body_readable != expected_post_body_readable:
                ledger_valid = False
                break
            if not current_body_readable:
                if (
                    current_body_sha256 is not None
                    or expected_post_body_sha256 is not None
                    or item.get("state") != "review_pending"
                ):
                    ledger_valid = False
                    break
            else:
                if (
                    item.get("state") != "restore_ready"
                    and expected_post_body_sha256 != current_body_sha256
                ):
                    ledger_valid = False
                    break
                auditable_rows.append(item)
            if re.fullmatch(
                r"sha256:[0-9a-f]{64}",
                str(item.get("historical_after_body_sha256") or ""),
            ) is None:
                ledger_valid = False
                break
            if item.get("state") == "restore_ready" and (
                current_body_sha256
                != item.get("historical_after_body_sha256")
            ):
                ledger_valid = False
                break
            if resolved_count == 0:
                continue
            if (
                item["verified_reference_marker_count"]
                != resolved_count
                or item["verified_reference_binding_count"] <= 0
                or item.get("current_body_sha256")
                != item.get("historical_after_body_sha256")
                or re.fullmatch(
                    r"sha256:[0-9a-f]{64}",
                    str(item.get("current_body_sha256") or ""),
                )
                is None
                or re.fullmatch(
                    r"sha256:[0-9a-f]{64}",
                    str(item.get("binding_manifest_sha256") or ""),
                )
                is None
            ):
                ledger_valid = False
                break
            resolved_rows.append(item)
        evidence_counts = dict(evidence.counts)
        evidence_digests = dict(evidence.digests)
        if (
            not ledger_valid
            or evidence_counts.get("classified_orphan_row_count")
            != sum(int(item["orphan_row_count"]) for item in document["classification_items"])
            or evidence_counts.get("resolved_by_verified_reference_count")
            != sum(
                int(item["verified_reference_resolved_count"])
                for item in resolved_rows
            )
            or evidence_counts.get("review_pending_count")
            != sum(
                int(item["review_pending_orphan_count"])
                for item in document["classification_items"]
            )
            or evidence_digests.get("orphan_classification_set_sha256")
            != _sha(_canonical_bytes(public_projection))
        ):
            blockers.append("local_locator_resolution_ledger_scan_invalid")
            continue
        verified_ledger_count += 1
        for item in auditable_rows:
            target_identity = str(item["target_identity_sha256"])
            candidate = {
                "resolved_occurrence_count": int(
                    item["verified_reference_resolved_count"]
                ),
                "review_pending_occurrence_count": int(
                    item["review_pending_orphan_count"]
                ),
                "classified_occurrence_count": int(item["orphan_row_count"]),
                "expected_body_sha256": str(
                    item["expected_post_body_sha256"]
                ),
                "expected_declared_omission_count": int(
                    item["declared_omission_count"]
                ),
            }
            if _merge_verified_resolution_candidate(
                by_target,
                conflicted_targets,
                target_identity=target_identity,
                candidate=candidate,
            ):
                blockers.append("local_locator_resolution_ledger_conflict")
    return {
        "by_target_identity": by_target,
        "verified_ledger_count": verified_ledger_count,
        "skipped_legacy_ledger_count": skipped_legacy_ledger_count,
        "conflicted_target_count": len(conflicted_targets),
        "verified_resolution_zettel_count": len(by_target),
        "verified_resolution_row_count": sum(
            int(item["resolved_occurrence_count"])
            for item in by_target.values()
        ),
        "verified_classified_row_count": sum(
            int(item["classified_occurrence_count"])
            for item in by_target.values()
        ),
        "verified_review_pending_row_count": sum(
            int(item["review_pending_occurrence_count"])
            for item in by_target.values()
        ),
        "exact_operation_receipt_count": receipt_count,
        "blockers": archive_services.unique_preserve_order(blockers),
        "private_values_echoed": False,
        "paths_echoed": False,
    }


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
    "discover_markup_normalization_receipts",
    "notion_locator_local_recovery_execution_plan",
    "notion_locator_mirror_recovery_execution_plan",
    "notion_locator_mirror_recovery_plan",
    "notion_locator_orphan_recovery_execution_plan",
    "notion_locator_orphan_recovery_plan",
    "verified_notion_locator_resolution_evidence",
]
