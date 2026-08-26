"""Field-local title receipt audit and source-id-bound title recovery plans."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from . import archive_services
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


FIELD_AUDIT_SCHEMA = "wom-kit/zet-title-field-local-audit/v0.1"
IDENTIFIER_RECOVERY_SCHEMA = (
    "wom-kit/zet-identifier-title-recovery-plan/v0.1"
)
MAX_SOURCE_INDEX_BYTES = 64 * 1024 * 1024
MAX_SOURCE_INDEX_ROWS = 10_000
MAX_RETURNED_ITEMS = 10_000
_RECEIPT_NAME_RE = re.compile(
    r"[0-9a-f]{64}\.zet-title-remap\.json"
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


def _title_sha(value: str) -> str:
    return _sha(value.encode("utf-8"))


def _safe_max_items(value: int) -> int:
    return max(0, min(int(value), MAX_RETURNED_ITEMS))


def _read_current_title(
    root: Path,
    relative: str,
) -> tuple[bytes, str, dict[str, Any], str]:
    path = archive_services.archive_internal_path(root, relative)
    raw, reason = archive_services._bounded_stable_regular_file_read(
        path,
        max_bytes=archive_services.ZET_TITLE_REMAP_MAX_CANONICAL_FILE_BYTES,
    )
    if raw is None or reason is not None:
        raise archive_services.ArchiveServiceError(
            "title_field_current_canonical_invalid"
        )
    try:
        text = raw.decode("utf-8-sig")
        boundary = archive_services.parse_approval_zettel_content_boundary(text)
    except (UnicodeError, RecursionError, ValueError) as exc:
        raise archive_services.ArchiveServiceError(
            "title_field_current_canonical_invalid"
        ) from exc
    frontmatter = boundary.get("frontmatter")
    title = frontmatter.get("title") if isinstance(frontmatter, dict) else None
    if (
        boundary.get("state") == "blocked"
        or not isinstance(frontmatter, dict)
        or frontmatter.get("status") != "canonical"
        or not isinstance(title, str)
    ):
        raise archive_services.ArchiveServiceError(
            "title_field_current_canonical_invalid"
        )
    return raw, title, frontmatter, str(boundary.get("body") or "")


def _read_before_title(
    root: Path,
    item: dict[str, Any],
) -> tuple[bytes, str]:
    snapshot = item.get("before_snapshot")
    if not isinstance(snapshot, dict):
        raise archive_services.ArchiveServiceError(
            "title_field_snapshot_invalid"
        )
    logical_key = snapshot.get("logical_key")
    if not isinstance(logical_key, str):
        raise archive_services.ArchiveServiceError(
            "title_field_snapshot_invalid"
        )
    path = root.joinpath(*PurePosixPath(logical_key).parts)
    raw, reason = archive_services._bounded_stable_regular_file_read(
        path,
        max_bytes=archive_services.ZET_TITLE_REMAP_MAX_CANONICAL_FILE_BYTES,
    )
    if (
        raw is None
        or reason is not None
        or _sha(raw) != item.get("before_file_sha256")
    ):
        raise archive_services.ArchiveServiceError(
            "title_field_snapshot_invalid"
        )
    try:
        text = raw.decode("utf-8-sig")
        boundary = archive_services.parse_approval_zettel_content_boundary(text)
    except (UnicodeError, RecursionError, ValueError) as exc:
        raise archive_services.ArchiveServiceError(
            "title_field_snapshot_invalid"
        ) from exc
    frontmatter = boundary.get("frontmatter")
    title = frontmatter.get("title") if isinstance(frontmatter, dict) else None
    if (
        boundary.get("state") == "blocked"
        or not isinstance(title, str)
        or _title_sha(title) != item.get("before_title_sha256")
    ):
        raise archive_services.ArchiveServiceError(
            "title_field_snapshot_invalid"
        )
    return raw, title


def _receipt_paths(
    root: Path,
    receipt_path: str | None,
) -> list[Path]:
    receipt_root = archive_services.archive_internal_path(
        root, archive_services.ZET_TITLE_REMAP_RECEIPTS_DIR
    )
    if receipt_path is None:
        return sorted(receipt_root.glob("*.zet-title-remap.json"))
    try:
        normalized = archive_services.normalize_archive_relative_path(
            receipt_path
        )
    except (archive_services.ArchivePathError, TypeError, ValueError) as exc:
        raise archive_services.ArchiveServiceError(
            "title_field_receipt_invalid"
        ) from exc
    if (
        not normalized.startswith(
            archive_services.ZET_TITLE_REMAP_RECEIPTS_DIR + "/"
        )
        or _RECEIPT_NAME_RE.fullmatch(PurePosixPath(normalized).name) is None
    ):
        raise archive_services.ArchiveServiceError(
            "title_field_receipt_invalid"
        )
    return [archive_services.archive_internal_path(root, normalized)]


def zet_title_field_local_recovery_plan(
    archive_root: Path | str,
    *,
    receipt_path: str | None = None,
    expected_receipt_sha256: str | None = None,
    dry_run: bool = True,
    max_items: int = 200,
    build_revert_manifest: bool = False,
    progress_callback: Callable[[str, str, int | None, int | None], None]
    | None = None,
    _build_execution: bool = False,
) -> dict[str, Any] | LocalRecoveryPlan:
    """Audit title fields independently of unrelated later body/file changes."""

    root = archive_services.require_existing_archive_root(archive_root)
    archive_id = archive_services.read_archive_id(root)
    blockers: list[str] = []
    warnings: list[str] = []
    if not dry_run:
        blockers.append("title_field_audit_dry_run_required")
    try:
        returned_limit = _safe_max_items(max_items)
    except (TypeError, ValueError, OverflowError):
        returned_limit = 200
        blockers.append("title_field_audit_max_items_invalid")
    if build_revert_manifest and receipt_path is None:
        blockers.append("title_field_revert_receipt_required")
    try:
        paths = _receipt_paths(root, receipt_path)
    except archive_services.ArchiveServiceError:
        paths = []
        blockers.append("title_field_receipt_invalid")
    if not paths:
        if _build_execution and not build_revert_manifest:
            warnings.append("title_field_receipt_population_empty")
        else:
            blockers.append("title_field_receipt_missing")

    public_items: list[dict[str, Any]] = []
    exact_items: list[ExactOperationItem] = []
    exact_specs: list[LocalRecoveryFieldSpec] = []
    receipt_refs: list[str] = []
    receipt_item_count = 0
    states = {
        "applied_title_matches": 0,
        "reverted_title_matches": 0,
        "title_divergent": 0,
        "missing_or_unreadable": 0,
    }
    receipt_documents: list[tuple[str, dict[str, Any]]] = []
    try:
        for path in paths:
            raw, document, _proposal = (
                archive_services.read_zet_title_remap_receipt_for_audit(
                    root,
                    path,
                    archive_id=archive_id,
                )
            )
            receipt_sha256 = _sha(raw)
            receipt_refs.append(receipt_sha256)
            receipt_documents.append((receipt_sha256, document))
            receipt_item_count += len(document["items"])
    except archive_services.ArchiveServiceError:
        blockers.append("title_field_receipt_invalid")
        receipt_documents = []
    normalized_expected = str(expected_receipt_sha256 or "").strip().lower()
    if expected_receipt_sha256 is not None:
        if re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", normalized_expected) is None:
            blockers.append("title_field_expected_receipt_sha256_invalid")
        else:
            if not normalized_expected.startswith("sha256:"):
                normalized_expected = "sha256:" + normalized_expected
            if len(receipt_refs) != 1 or receipt_refs[0] != normalized_expected:
                blockers.append("title_field_receipt_sha256_mismatch")

    if progress_callback is not None:
        progress_callback("title-field-audit", "start", 0, receipt_item_count)
    seen_targets: set[str] = set()
    scanned = 0
    for receipt_sha256, document in receipt_documents:
        for item in document["items"]:
            scanned += 1
            blocker_codes: list[str] = []
            current_raw: bytes | None = None
            current_title: str | None = None
            before_title: str | None = None
            try:
                current_raw, current_title, _frontmatter, _body = (
                    _read_current_title(root, item["canonical_path"])
                )
                _snapshot_raw, before_title = _read_before_title(root, item)
            except (archive_services.ArchiveServiceError, OSError, ValueError):
                blocker_codes.append("title_field_evidence_unreadable")
            target_ref = _sha(
                _canonical_bytes(
                    {
                        "archive_id": archive_id,
                        "zettel_id": item.get("zettel_id"),
                        "canonical_path": item.get("canonical_path"),
                    }
                )
            )
            if target_ref in seen_targets:
                blocker_codes.append("title_field_target_repeated")
            seen_targets.add(target_ref)
            if current_title is None or before_title is None:
                state = "missing_or_unreadable"
            elif _title_sha(current_title) == item.get("after_title_sha256"):
                state = "applied_title_matches"
            elif _title_sha(current_title) == item.get("before_title_sha256"):
                state = "reverted_title_matches"
            else:
                state = "title_divergent"
                blocker_codes.append("current_title_diverged")
            states[state] += 1
            item_ref = _sha(
                _canonical_bytes(
                    {
                        "receipt_sha256": receipt_sha256,
                        "row_index": item.get("row_index"),
                        "target_ref": target_ref,
                    }
                )
            )
            public_items.append(
                {
                    "ordinal": len(public_items),
                    "item_ref_sha256": item_ref,
                    "state": state,
                    "blocker_codes": blocker_codes,
                }
            )
            if (
                build_revert_manifest
                and state == "applied_title_matches"
                and not blocker_codes
                and current_raw is not None
                and before_title is not None
            ):
                pre_value = current_title.encode("utf-8")
                post_value = before_title.encode("utf-8")
                source_value = _canonical_bytes(
                    {
                        "receipt_sha256": receipt_sha256,
                        "row_index": item.get("row_index"),
                        "before_title_sha256": item.get(
                            "before_title_sha256"
                        ),
                        "after_title_sha256": item.get(
                            "after_title_sha256"
                        ),
                    }
                )
                identity = local_recovery_zettel_identity_sha256(
                    archive_id,
                    item["zettel_id"],
                    item["canonical_path"],
                )
                exact_item = ExactOperationItem(
                        ordinal=len(exact_items),
                        item_id=f"item:{int(item['row_index']):06d}",
                        target_kind="zettel",
                        target_ref=target_ref,
                        target_identity_sha256=identity,
                        fields=(
                            ExactFieldEffect(
                                field_ref="frontmatter.title",
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
                        field_ref="frontmatter.title",
                        target_relative=item["canonical_path"],
                        zettel_id=item["zettel_id"],
                        pre_value=pre_value,
                        post_value=post_value,
                        source_value=source_value,
                    )
                )
            if progress_callback is not None and (
                scanned == 1
                or scanned == receipt_item_count
                or scanned % 100 == 0
            ):
                progress_callback(
                    "title-field-audit", "scanned", scanned, receipt_item_count
                )
    if progress_callback is not None:
        progress_callback(
            "title-field-audit", "done", scanned, receipt_item_count
        )

    classified_count = sum(states.values())
    if classified_count != receipt_item_count:
        blockers.append("title_field_classification_incomplete")
    if states["missing_or_unreadable"]:
        blockers.append("title_field_evidence_unreadable")
    digests = {
        "title_receipt_set_sha256": _sha(
            _canonical_bytes(sorted(receipt_refs))
        ),
        "title_receipt_item_set_sha256": _sha(
            _canonical_bytes(
                [item["item_ref_sha256"] for item in public_items]
            )
        ),
        "title_field_classification_set_sha256": _sha(
            _canonical_bytes(public_items)
        ),
        "applied_title_match_set_sha256": _sha(
            _canonical_bytes(
                [
                    item["item_ref_sha256"]
                    for item in public_items
                    if item["state"] == "applied_title_matches"
                ]
            )
        ),
        "reverted_title_match_set_sha256": _sha(
            _canonical_bytes(
                [
                    item["item_ref_sha256"]
                    for item in public_items
                    if item["state"] == "reverted_title_matches"
                ]
            )
        ),
        "title_divergent_set_sha256": _sha(
            _canonical_bytes(
                [
                    item["item_ref_sha256"]
                    for item in public_items
                    if item["state"] == "title_divergent"
                ]
            )
        ),
        "title_missing_set_sha256": _sha(
            _canonical_bytes(
                [
                    item["item_ref_sha256"]
                    for item in public_items
                    if item["state"] == "missing_or_unreadable"
                ]
            )
        ),
    }
    counts = {
        "title_receipt_count": len(receipt_refs),
        "title_receipt_item_count": receipt_item_count,
        "classified_title_item_count": classified_count,
        **{f"{key}_count": value for key, value in states.items()},
    }
    operation_evidence = ExactOperationEvidence(
        schema="wom-kit/zet-title-field-local-evidence/v1",
        counts=tuple(sorted(counts.items())),
        digests=tuple(sorted(digests.items())),
    )
    title_item_count = len(exact_items)
    ledger_bytes = _canonical_bytes(
        {
            "schema": "wom-kit/zet-title-field-local-ledger/v0.1",
            "archive_identity_sha256": (
                exact_human_approval_archive_identity_sha256(archive_id)
            ),
            "classification_items": public_items,
            "operation_evidence": operation_evidence.document(),
            "private_values_echoed": False,
        }
    ) + b"\n"
    ledger_relative = local_recovery_ledger_relative(
        "zet_title_field",
        ledger_bytes,
    )
    ledger_identity = local_recovery_ledger_identity_sha256(
        archive_id,
        "zet_title_field",
        ledger_relative,
    )
    ledger_source = _canonical_bytes(
        {
            "operation_evidence_sha256": operation_evidence.evidence_sha256,
            "title_receipt_set_sha256": digests["title_receipt_set_sha256"],
        }
    )
    ledger_item = ExactOperationItem(
        ordinal=len(exact_items),
        item_id=f"item:{receipt_item_count:06d}:classification",
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
        warnings.append("title_field_items_truncated")
    result = {
        "ok": not blockers,
        "schema": FIELD_AUDIT_SCHEMA,
        "lifecycle_action": (
            "zet_title_field_local_revert_plan"
            if build_revert_manifest
            else "zet_title_field_local_audit"
        ),
        "state": "blocked" if blockers else "classified",
        "dry_run": True,
        "summary": {
            **counts,
            **digests,
            "operation_evidence_sha256": operation_evidence.evidence_sha256,
            "exact_manifest_item_count": len(exact_items),
            "title_change_manifest_item_count": title_item_count,
            "classification_ledger_item_count": 1,
            "returned_item_count": len(returned_items),
            "truncated_item_count": len(public_items) - len(returned_items),
        },
        "items": returned_items,
        "exact_operation_manifest": exact_manifest,
        "blockers": archive_services.unique_preserve_order(blockers),
        "warnings": archive_services.unique_preserve_order(warnings),
        "would_change": (
            (
                (["frontmatter.title"] if title_item_count else [])
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
                "title_field_execution_plan_blocked"
            )
        execution_warnings = []
        if states["title_divergent"]:
            execution_warnings.append("divergent_titles_present")
        if states["reverted_title_matches"]:
            execution_warnings.append("already_reverted_titles_present")
        return build_local_recovery_plan(
            root,
            domain=(
                "zet_title_field_revert"
                if build_revert_manifest
                else "zet_title_field_audit"
            ),
            manifest=exact_manifest_object,
            specs=exact_specs,
            warning_codes=execution_warnings,
            public_summary=result["summary"],
        )
    return result


def _source_title_index(
    source_mirror: Path | str,
    *,
    progress_callback: Callable[[str, str, int | None, int | None], None]
    | None = None,
) -> tuple[bytes, dict[str, dict[str, Any]], int]:
    markdown_path = Path(source_mirror)
    if markdown_path.name != "pages.markdown.jsonl":
        raise archive_services.ArchiveServiceError(
            "identifier_title_source_index_invalid"
        )
    title_path = markdown_path.with_name("pages.index.jsonl")
    markdown_raw, markdown_reason = (
        archive_services._bounded_stable_regular_file_read(
            markdown_path,
            max_bytes=MAX_SOURCE_INDEX_BYTES,
        )
    )
    title_raw, title_reason = archive_services._bounded_stable_regular_file_read(
        title_path,
        max_bytes=MAX_SOURCE_INDEX_BYTES,
    )
    if (
        markdown_raw is None
        or markdown_reason is not None
        or title_raw is None
        or title_reason is not None
    ):
        raise archive_services.ArchiveServiceError(
            "identifier_title_source_index_invalid"
        )
    markdown_lines = markdown_raw.splitlines()
    title_lines = title_raw.splitlines()
    if (
        not markdown_lines
        or not title_lines
        or len(markdown_lines) > MAX_SOURCE_INDEX_ROWS
        or len(title_lines) > MAX_SOURCE_INDEX_ROWS
    ):
        raise archive_services.ArchiveServiceError(
            "identifier_title_source_index_invalid"
        )
    markdown_index: dict[str, str] = {}
    if progress_callback is not None:
        progress_callback(
            "title-source-index",
            "start",
            0,
            len(markdown_lines) + len(title_lines),
        )

    def parse(line: bytes, ordinal: int) -> dict[str, Any]:
        try:
            document = json.loads(
                line.decode("utf-8-sig" if ordinal == 1 else "utf-8"),
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
                "identifier_title_source_index_invalid"
            ) from exc
        if not isinstance(document, dict):
            raise archive_services.ArchiveServiceError(
                "identifier_title_source_index_invalid"
            )
        return document

    total_rows = len(markdown_lines) + len(title_lines)
    for ordinal, line in enumerate(markdown_lines, start=1):
        row = parse(line, ordinal)
        source_id = archive_services._normalize_notion_locator_source_page_id(
            row.get("page_id")
        )
        markdown = row.get("markdown")
        if (
            source_id is None
            or not isinstance(markdown, str)
            or source_id in markdown_index
        ):
            raise archive_services.ArchiveServiceError(
                "identifier_title_source_index_invalid"
            )
        markdown_index[source_id] = _sha(line)
        if progress_callback is not None and (
            ordinal == 1
            or ordinal == len(markdown_lines)
            or ordinal % 250 == 0
        ):
            progress_callback(
                "title-source-index", "scanned", ordinal, total_rows
            )

    index: dict[str, dict[str, Any]] = {}
    for index_ordinal, line in enumerate(title_lines, start=1):
        row = parse(line, index_ordinal)
        source_id = archive_services._normalize_notion_locator_source_page_id(
            row.get("page_id")
        )
        source_title = row.get("index")
        if (
            source_id is None
            or not isinstance(source_title, str)
            or source_id in index
        ):
            raise archive_services.ArchiveServiceError(
                "identifier_title_source_index_invalid"
            )
        markdown_row_sha256 = markdown_index.get(source_id)
        if markdown_row_sha256 is None:
            raise archive_services.ArchiveServiceError(
                "identifier_title_source_index_invalid"
            )
        title_row_sha256 = _sha(line)
        index[source_id] = {
            "title": source_title,
            "title_sha256": _title_sha(source_title),
            "title_row_sha256": title_row_sha256,
            "markdown_row_sha256": markdown_row_sha256,
            "row_sha256": _sha(
                _canonical_bytes(
                    {
                        "title_row_sha256": title_row_sha256,
                        "markdown_row_sha256": markdown_row_sha256,
                    }
                )
            ),
        }
        completed = len(markdown_lines) + index_ordinal
        if progress_callback is not None and (
            index_ordinal == 1
            or index_ordinal == len(title_lines)
            or index_ordinal % 250 == 0
        ):
            progress_callback(
                "title-source-index", "scanned", completed, total_rows
            )
    if set(index) != set(markdown_index):
        raise archive_services.ArchiveServiceError(
            "identifier_title_source_index_invalid"
        )
    source_evidence = _canonical_bytes(
        {
            "schema": "wom-kit/identifier-title-source-mirror/v1",
            "markdown_sha256": _sha(markdown_raw),
            "title_index_sha256": _sha(title_raw),
            "page_id_set_sha256": _sha(_canonical_bytes(sorted(index))),
        }
    )
    if progress_callback is not None:
        progress_callback(
            "title-source-index", "done", total_rows, total_rows
        )
    return source_evidence, index, len(index)


def zet_identifier_title_recovery_plan(
    archive_root: Path | str,
    *,
    source_mirror: Path | str,
    dry_run: bool = True,
    max_items: int = 200,
    expected_identifier_title_count: int | None = None,
    progress_callback: Callable[[str, str, int | None, int | None], None]
    | None = None,
    _build_execution: bool = False,
) -> dict[str, Any] | LocalRecoveryPlan:
    """Plan replacements only from each zettel's own exact source page id."""

    root = archive_services.require_existing_archive_root(archive_root)
    archive_id = archive_services.read_archive_id(root)
    blockers: list[str] = []
    warnings: list[str] = []
    if not dry_run:
        blockers.append("identifier_title_recovery_dry_run_required")
    try:
        returned_limit = _safe_max_items(max_items)
        source_raw, source_index, source_row_count = _source_title_index(
            source_mirror,
            progress_callback=progress_callback,
        )
    except (
        archive_services.ArchiveServiceError,
        OSError,
        TypeError,
        ValueError,
        OverflowError,
    ):
        return {
            "ok": False,
            "schema": IDENTIFIER_RECOVERY_SCHEMA,
            "lifecycle_action": "zet_identifier_title_recovery_plan",
            "state": "blocked",
            "dry_run": True,
            "summary": {
                "identifier_title_count": 0,
                "classified_identifier_title_count": 0,
            },
            "items": [],
            "exact_operation_manifest": None,
            "blockers": ["identifier_title_recovery_evidence_invalid"],
            "warnings": [],
            "would_change": [],
            "privacy_guards": _privacy_guards(),
        }

    public_items: list[dict[str, Any]] = []
    exact_items: list[ExactOperationItem] = []
    exact_specs: list[LocalRecoveryFieldSpec] = []
    states = {
        "exact_recovery_ready": 0,
        "review_required": 0,
        "source_title_unavailable": 0,
    }
    paths = sorted((root / "zettels").glob("*.md"))
    if progress_callback is not None:
        progress_callback("identifier-title-scan", "start", 0, len(paths))
    unreadable = 0
    for path_ordinal, path in enumerate(paths, start=1):
        try:
            relative = archive_services.archive_relative_path(path, root)
            raw, current_title, frontmatter, _body = _read_current_title(
                root, relative
            )
        except archive_services.ArchiveServiceError:
            unreadable += 1
            continue
        if not archive_services.zet_title_is_identifier_shaped(current_title):
            continue
        blocker_codes: list[str] = []
        source_page_id, source_state, _candidates = (
            archive_services._notion_locator_exact_source_page_id(frontmatter)
        )
        source = (
            source_index.get(source_page_id)
            if source_page_id is not None
            else None
        )
        replacement = source.get("title") if source is not None else None
        if (
            source is None
            or not isinstance(replacement, str)
            or not replacement.strip()
        ):
            state = "source_title_unavailable"
            blocker_codes.append("own_source_page_title_unavailable")
        else:
            title_blockers: list[str] = []
            normalized_candidate = archive_services.normalized_zet_title_candidate(
                replacement,
                title_blockers,
                basis="source_export_property",
            )
            if title_blockers or normalized_candidate is None:
                blocker_codes.append("source_title_not_safe_for_remap")
            if source_state != "exact":
                blocker_codes.append("own_source_page_id_not_exact")
            state = (
                "exact_recovery_ready" if not blocker_codes else "review_required"
            )
        states[state] += 1
        target_ref = _sha(
            _canonical_bytes(
                {
                    "archive_id": archive_id,
                    "zettel_id": frontmatter.get("id"),
                    "path": relative,
                }
            )
        )
        item_ref = _sha(
            _canonical_bytes(
                {
                    "target_ref": target_ref,
                    "current_title_sha256": _title_sha(current_title),
                    "source_row_sha256": (
                        source.get("row_sha256") if source is not None else None
                    ),
                }
            )
        )
        public_items.append(
            {
                "ordinal": len(public_items),
                "item_ref_sha256": item_ref,
                "state": state,
                "detected_duplicate_suffix": bool(
                    archive_services.zet_title_identifier_duplicate_suffix(
                        current_title
                    )
                ),
                "blocker_codes": blocker_codes,
            }
        )
        if state == "exact_recovery_ready" and isinstance(replacement, str):
            pre_value = current_title.encode("utf-8")
            post_value = replacement.encode("utf-8")
            source_value = _canonical_bytes(
                {
                    "source_page_id": source_page_id,
                    "source_row_sha256": source["row_sha256"],
                    "source_title_sha256": source["title_sha256"],
                    "source_title_row_sha256": source["title_row_sha256"],
                    "source_markdown_row_sha256": source[
                        "markdown_row_sha256"
                    ],
                }
            )
            identity = local_recovery_zettel_identity_sha256(
                archive_id,
                frontmatter["id"],
                relative,
            )
            exact_item = ExactOperationItem(
                    ordinal=len(exact_items),
                    item_id=f"item:{len(public_items) - 1:06d}",
                    target_kind="zettel",
                    target_ref=target_ref,
                    target_identity_sha256=identity,
                    fields=(
                        ExactFieldEffect(
                            field_ref="frontmatter.title",
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
                    field_ref="frontmatter.title",
                    target_relative=relative,
                    zettel_id=frontmatter["id"],
                    pre_value=pre_value,
                    post_value=post_value,
                    source_value=source_value,
                )
            )
        if progress_callback is not None and (
            path_ordinal == 1
            or path_ordinal == len(paths)
            or path_ordinal % 250 == 0
        ):
            progress_callback(
                "identifier-title-scan", "scanned", path_ordinal, len(paths)
            )
    if progress_callback is not None:
        progress_callback(
            "identifier-title-scan", "done", len(paths), len(paths)
        )
    identifier_count = len(public_items)
    if (
        expected_identifier_title_count is not None
        and int(expected_identifier_title_count) != identifier_count
    ):
        blockers.append("identifier_title_expected_count_mismatch")
    if sum(states.values()) != identifier_count:
        blockers.append("identifier_title_classification_incomplete")
    if unreadable:
        blockers.append("identifier_title_canonical_scan_incomplete")

    digests = {
        "source_index_sha256": _sha(source_raw),
        "source_index_row_set_sha256": _sha(
            _canonical_bytes(
                sorted(row["row_sha256"] for row in source_index.values())
            )
        ),
        "identifier_title_set_sha256": _sha(
            _canonical_bytes(
                [item["item_ref_sha256"] for item in public_items]
            )
        ),
        "identifier_title_classification_set_sha256": _sha(
            _canonical_bytes(public_items)
        ),
        "exact_recovery_ready_set_sha256": _sha(
            _canonical_bytes(
                [
                    item["item_ref_sha256"]
                    for item in public_items
                    if item["state"] == "exact_recovery_ready"
                ]
            )
        ),
        "review_required_set_sha256": _sha(
            _canonical_bytes(
                [
                    item["item_ref_sha256"]
                    for item in public_items
                    if item["state"] == "review_required"
                ]
            )
        ),
        "source_title_unavailable_set_sha256": _sha(
            _canonical_bytes(
                [
                    item["item_ref_sha256"]
                    for item in public_items
                    if item["state"] == "source_title_unavailable"
                ]
            )
        ),
    }
    counts = {
        "source_index_row_count": source_row_count,
        "canonical_zettel_count": len(paths),
        "unreadable_canonical_count": unreadable,
        "identifier_title_count": identifier_count,
        "classified_identifier_title_count": sum(states.values()),
        "exact_recovery_ready_count": states["exact_recovery_ready"],
        "review_required_count": states["review_required"],
        "source_title_unavailable_count": states["source_title_unavailable"],
        "duplicate_suffix_identifier_title_count": sum(
            1
            for item in public_items
            if item["detected_duplicate_suffix"]
        ),
    }
    operation_evidence = ExactOperationEvidence(
        schema="wom-kit/zet-identifier-title-recovery-evidence/v1",
        counts=tuple(sorted(counts.items())),
        digests=tuple(sorted(digests.items())),
    )
    title_item_count = len(exact_items)
    ledger_bytes = _canonical_bytes(
        {
            "schema": "wom-kit/zet-identifier-title-recovery-ledger/v0.1",
            "archive_identity_sha256": (
                exact_human_approval_archive_identity_sha256(archive_id)
            ),
            "classification_items": public_items,
            "operation_evidence": operation_evidence.document(),
            "private_values_echoed": False,
        }
    ) + b"\n"
    ledger_relative = local_recovery_ledger_relative(
        "zet_identifier_title",
        ledger_bytes,
    )
    ledger_identity = local_recovery_ledger_identity_sha256(
        archive_id,
        "zet_identifier_title",
        ledger_relative,
    )
    ledger_source = _canonical_bytes(
        {
            "operation_evidence_sha256": operation_evidence.evidence_sha256,
            "source_index_sha256": digests["source_index_sha256"],
        }
    )
    ledger_item = ExactOperationItem(
        ordinal=len(exact_items),
        item_id=f"item:{identifier_count:06d}:classification",
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
    if len(returned_items) < identifier_count:
        warnings.append("identifier_title_items_truncated")
    result = {
        "ok": not blockers,
        "schema": IDENTIFIER_RECOVERY_SCHEMA,
        "lifecycle_action": "zet_identifier_title_recovery_plan",
        "state": "blocked" if blockers else "classified",
        "dry_run": True,
        "summary": {
            **counts,
            **digests,
            "operation_evidence_sha256": operation_evidence.evidence_sha256,
            "exact_manifest_item_count": len(exact_items),
            "title_change_manifest_item_count": title_item_count,
            "classification_ledger_item_count": 1,
            "returned_item_count": len(returned_items),
            "truncated_item_count": identifier_count - len(returned_items),
            "expected_identifier_title_count": expected_identifier_title_count,
        },
        "items": returned_items,
        "exact_operation_manifest": exact_manifest,
        "blockers": archive_services.unique_preserve_order(blockers),
        "warnings": archive_services.unique_preserve_order(warnings),
        "would_change": (
            (
                (["frontmatter.title"] if title_item_count else [])
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
                "identifier_title_execution_plan_blocked"
            )
        execution_warnings = []
        if states["review_required"]:
            execution_warnings.append("review_titles_present")
        if states["source_title_unavailable"]:
            execution_warnings.append("unavailable_source_titles_present")
        return build_local_recovery_plan(
            root,
            domain="zet_identifier_title",
            manifest=exact_manifest_object,
            specs=exact_specs,
            warning_codes=execution_warnings,
            public_summary=result["summary"],
        )
    return result


def zet_title_field_local_execution_plan(
    archive_root: Path | str,
    *,
    receipt_path: str | None = None,
    expected_receipt_sha256: str | None = None,
    max_items: int = 200,
    build_revert_manifest: bool = False,
    progress_callback: Callable[[str, str, int | None, int | None], None]
    | None = None,
) -> LocalRecoveryPlan:
    plan = zet_title_field_local_recovery_plan(
        archive_root,
        receipt_path=receipt_path,
        expected_receipt_sha256=expected_receipt_sha256,
        dry_run=True,
        max_items=max_items,
        build_revert_manifest=build_revert_manifest,
        progress_callback=progress_callback,
        _build_execution=True,
    )
    if type(plan) is not LocalRecoveryPlan:
        raise archive_services.ArchiveServiceError(
            "title_field_execution_plan_blocked"
        )
    return plan


def zet_identifier_title_recovery_execution_plan(
    archive_root: Path | str,
    *,
    source_mirror: Path | str,
    max_items: int = 200,
    expected_identifier_title_count: int | None = None,
    progress_callback: Callable[[str, str, int | None, int | None], None]
    | None = None,
) -> LocalRecoveryPlan:
    plan = zet_identifier_title_recovery_plan(
        archive_root,
        source_mirror=source_mirror,
        dry_run=True,
        max_items=max_items,
        expected_identifier_title_count=expected_identifier_title_count,
        progress_callback=progress_callback,
        _build_execution=True,
    )
    if type(plan) is not LocalRecoveryPlan:
        raise archive_services.ArchiveServiceError(
            "identifier_title_execution_plan_blocked"
        )
    return plan


def zet_title_recovery_execution_plan(
    archive_root: Path | str,
    *,
    source_mirror: Path | str,
    max_items: int = 200,
    expected_identifier_title_count: int | None = None,
    progress_callback: Callable[[str, str, int | None, int | None], None]
    | None = None,
) -> LocalRecoveryPlan:
    audit = zet_title_field_local_execution_plan(
        archive_root,
        max_items=max_items,
        progress_callback=progress_callback,
    )
    recovery = zet_identifier_title_recovery_execution_plan(
        archive_root,
        source_mirror=source_mirror,
        max_items=max_items,
        expected_identifier_title_count=expected_identifier_title_count,
        progress_callback=progress_callback,
    )
    return combine_local_recovery_plans(
        (audit, recovery),
        domain="zet_title_recovery",
        public_summary={
            "title_receipt_item_count": audit.public_summary.get(
                "title_receipt_item_count", 0
            ),
            "identifier_title_count": recovery.public_summary.get(
                "identifier_title_count", 0
            ),
            "identifier_title_change_count": recovery.public_summary.get(
                "title_change_manifest_item_count", 0
            ),
        },
    )


def _privacy_guards() -> dict[str, bool]:
    return {
        "title_echoed": False,
        "source_page_id_echoed": False,
        "zettel_id_echoed": False,
        "body_echoed": False,
        "filename_or_path_echoed": False,
        "absolute_local_path_echoed": False,
        "source_snapshot_contents_echoed": False,
        "provider_api_called": False,
        "writes": False,
    }


__all__ = [
    "zet_identifier_title_recovery_execution_plan",
    "zet_identifier_title_recovery_plan",
    "zet_title_field_local_execution_plan",
    "zet_title_field_local_recovery_plan",
    "zet_title_recovery_execution_plan",
]
