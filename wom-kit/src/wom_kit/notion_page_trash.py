"""Move verified-recovered Notion pages to the Notion trash (v0.4.41).

The owner's idea (2026-09-24): a Notion page whose content WOM has already
recovered into the archive can leave Notion. The design (decision log
2026-09-24, "Planned: Notion Trash Cleanup") keeps that safe:

- Only pages whose recovery is verified qualify: a terminal ``recovered``
  journal row, every stored fragment re-hashing to its recorded digest and
  size, and the manifest and projection rows present (the recovery store's
  own ``preview_verified``).
- Nothing is permanently deleted. ``PATCH /v1/pages/{id}`` with
  ``{"in_trash": true}`` moves the page to the Notion trash, where it can be
  restored; ``restore=True`` moves pages this workflow trashed back out.
- Immediately before each PATCH a fresh GET must show the page not already
  in the trash and not edited since its recovery; a changed page is skipped.
  Notion reports ``last_edited_time`` to the minute, so a page edited in the
  same minute as its recovery completed (or later) counts as changed.
- A private journal row precedes each PATCH and a terminal row follows the
  GET that confirms the new state, so an interrupted run resumes; a PATCH is
  never retried blind.

This module is the injectable engine (provider and credential broker are
parameters). Page ids never appear in public results.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .notion_page_recovery import (
    NOTION_API_VERSION,
    ManifestValidationError,
    RecoveryItem,
    RecoveryPlan,
    RecoveryRequest,
    RecoveryStorageError,
    _FilesystemRecoveryStorage,
    _authorize_credential_provider_request,
    _canonical_json_bytes,
    _close_resolved_credentials,
    _digest_part,
    _ensure_archive_directory_chain,
    _exclusive_file_lock,
    _last_edited_time,
    _privacy_guards,
    _read_jsonl,
    _resolve_credential,
    _revalidate_credential_authority,
    _sha256_id,
    parse_manifest,
)

PLAN_SCHEMA = "wom-kit/notion-page-trash-plan/v0.1"
JOURNAL_SCHEMA = "wom-kit/notion-page-trash-journal/v0.1"
RECEIPT_SCHEMA = "wom-kit/notion-page-trash-receipt/v0.1"
JOURNAL_RELATIVE = ("profiles", "local", "notion-page-trash")
RECEIPT_RELATIVE = ("receipts", "notion-page-trash")
MAX_TRASH_ITEMS = 200

TRASH_OUTCOMES = (
    "trashed",
    "already_in_trash",
    "changed_since_recovery",
    "forbidden",
    "not_found_or_not_shared",
    "retryable_error",
    "unconfirmed",
)
RESTORE_OUTCOMES = ("restored", "already_restored", "forbidden", "not_found_or_not_shared",
                    "retryable_error", "unconfirmed")
# Outcomes a later run does not try again.
_SETTLED = {"trashed", "already_in_trash", "changed_since_recovery", "not_found_or_not_shared",
            "restored", "already_restored"}


class NotionTrashError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class TrashCandidate:
    item: RecoveryItem
    scope_revision: str
    recovery_plan_sha256: str
    recovered_at: str
    fragment_sha256: tuple[str, ...]


def _request_sha256(request: RecoveryRequest) -> str:
    return _sha256_id(_canonical_json_bytes(request.canonical_document()))


def _journal_dir(root: Path) -> Path:
    return root.joinpath(*JOURNAL_RELATIVE)


def _journal_path(root: Path, plan_sha256: str) -> Path:
    return _journal_dir(root) / f"{_digest_part(plan_sha256)}.journal.jsonl"


def _recovered_index(storage: _FilesystemRecoveryStorage, request_sha256: str) -> dict[tuple[str, str], tuple[str, str]]:
    """(item_id, page_id) -> (recovery plan digest, completed_at) of the latest
    terminal ``recovered`` row across every recovery journal of the request."""

    index: dict[tuple[str, str], tuple[str, str]] = {}
    root = storage.private_root
    try:
        names = sorted(entry.name for entry in os.scandir(root) if entry.name.endswith(".resume.jsonl"))
    except FileNotFoundError:
        return index
    except OSError:
        raise NotionTrashError("notion_page_trash_recovery_state_unavailable") from None
    for name in names:
        rows, _ = _read_jsonl(root / name, archive_root=storage.root)
        for row in rows:
            if (
                row.get("request_sha256") == request_sha256
                and row.get("phase") == "terminal"
                and isinstance(row.get("item_id"), str)
                and isinstance(row.get("page_id"), str)
                and isinstance(row.get("plan_sha256"), str)
            ):
                key = (row["item_id"], row["page_id"])
                if row.get("outcome") == "recovered" and isinstance(row.get("completed_at"), str):
                    index[key] = (row["plan_sha256"], row["completed_at"])
                else:
                    index.pop(key, None)
    return index


def _journal_state(root: Path, plan_sha256: str) -> dict[str, str]:
    rows, _ = _read_jsonl(_journal_path(root, plan_sha256), archive_root=root)
    latest: dict[str, str] = {}
    for row in rows:
        if row.get("schema") == JOURNAL_SCHEMA and row.get("phase") == "terminal" and isinstance(row.get("item_id"), str):
            latest[row["item_id"]] = str(row.get("outcome"))
    return latest


def _trashed_by_this_workflow(root: Path, request_sha256: str) -> set[str]:
    """Item ids whose latest trash-workflow terminal row, across every trash
    journal of the request, is ``trashed`` (the restore candidates)."""

    directory = _journal_dir(root)
    latest: dict[str, tuple[str, str]] = {}
    try:
        names = sorted(entry.name for entry in os.scandir(directory) if entry.name.endswith(".journal.jsonl"))
    except FileNotFoundError:
        return set()
    except OSError:
        raise NotionTrashError("notion_page_trash_journal_unavailable") from None
    for name in names:
        rows, _ = _read_jsonl(directory / name, archive_root=root)
        for row in rows:
            if (
                row.get("schema") == JOURNAL_SCHEMA
                and row.get("request_sha256") == request_sha256
                and row.get("phase") == "terminal"
                and isinstance(row.get("item_id"), str)
            ):
                at = str(row.get("at") or "")
                if row["item_id"] not in latest or at >= latest[row["item_id"]][0]:
                    latest[row["item_id"]] = (at, str(row.get("outcome")))
    # A page that was already in the trash before this workflow looked is the
    # user's own choice and is never restored by it.
    return {item_id for item_id, (_at, outcome) in latest.items() if outcome == "trashed"}


def _select(
    root: Path,
    request: RecoveryRequest,
    *,
    max_items: int,
    offset: int,
    restore: bool,
    storage: _FilesystemRecoveryStorage,
) -> tuple[str, list[TrashCandidate], int]:
    if not isinstance(max_items, int) or isinstance(max_items, bool) or not 1 <= max_items <= MAX_TRASH_ITEMS:
        raise NotionTrashError("notion_page_trash_max_items_invalid")
    if not isinstance(offset, int) or isinstance(offset, bool) or not 0 <= offset < max(1, len(request.items)):
        raise NotionTrashError("notion_page_trash_offset_invalid")
    request_sha256 = _request_sha256(request)
    if not storage.validate_plan_boundary():
        raise NotionTrashError("notion_page_trash_recovery_state_unavailable")
    recovered = _recovered_index(storage, request_sha256)
    trashed = _trashed_by_this_workflow(root, request_sha256) if restore else set()
    revisions = {group.group_id: group.scope_binding.revision for group in request.groups}
    selected = request.items[offset: offset + max_items]
    candidates: list[TrashCandidate] = []
    for item in selected:
        found = recovered.get((item.item_id, item.page_id))
        if found is None:
            continue
        recovery_plan_sha256, recovered_at = found
        plan = RecoveryPlan(request_sha256, recovery_plan_sha256, 1, 0, ())
        stored = storage.preview_verified(request, plan, item, revisions[item.group_id])
        if stored is None:
            continue
        if restore and item.item_id not in trashed:
            continue
        candidates.append(TrashCandidate(
            item=item,
            scope_revision=revisions[item.group_id],
            recovery_plan_sha256=recovery_plan_sha256,
            recovered_at=recovered_at,
            fragment_sha256=tuple(fragment.sha256 for fragment in stored.fragments),
        ))
    return request_sha256, candidates, len(selected)


def _plan_digest(request_sha256: str, candidates: Sequence[TrashCandidate], *, max_items: int, offset: int,
                 restore: bool) -> str:
    return _sha256_id(_canonical_json_bytes({
        "schema": PLAN_SCHEMA,
        "request_sha256": request_sha256,
        "mode": "restore" if restore else "trash",
        "max_items": max_items,
        "offset": offset,
        "items": [
            {
                "item_id": candidate.item.item_id,
                "group_id": candidate.item.group_id,
                "page_id": candidate.item.page_id,
                "recovery_plan_sha256": candidate.recovery_plan_sha256,
                "recovered_at": candidate.recovered_at,
                "fragment_sha256": list(candidate.fragment_sha256),
            }
            for candidate in candidates
        ],
    }))


def _blocked(code: str, **extra: Any) -> dict[str, Any]:
    return {
        "ok": False,
        "lifecycle_action": "notion_page_trash",
        "reason_code": code,
        "blockers": [code],
        "provider_calls": 0,
        "writes": 0,
        "privacy_guards": {**_privacy_guards(), "page_ids_echoed": False},
        **extra,
    }


def plan_trash(
    archive_root: Path | str,
    manifest: Mapping[str, Any],
    *,
    max_items: int,
    offset: int = 0,
    restore: bool = False,
    storage: _FilesystemRecoveryStorage | None = None,
) -> dict[str, Any]:
    """Read-only plan: which selected pages are verified-recovered and would
    move to (or, with ``restore``, back out of) the Notion trash."""

    try:
        request = parse_manifest(manifest)
    except ManifestValidationError:
        return _blocked("notion_page_trash_request_invalid", dry_run=True)
    state = storage or _FilesystemRecoveryStorage(archive_root)
    root = state.root
    try:
        request_sha256, candidates, selected_count = _select(
            root, request, max_items=max_items, offset=offset, restore=restore, storage=state,
        )
        settled = _journal_state(root, _plan_digest(request_sha256, candidates, max_items=max_items,
                                                    offset=offset, restore=restore))
    except NotionTrashError as exc:
        return _blocked(exc.code, dry_run=True)
    except RecoveryStorageError as exc:
        return _blocked(str(getattr(exc, "code", "notion_page_trash_recovery_state_unavailable")), dry_run=True)
    plan_sha256 = _plan_digest(request_sha256, candidates, max_items=max_items, offset=offset, restore=restore)
    done = sum(1 for candidate in candidates if settled.get(candidate.item.item_id) in _SETTLED)
    blockers = [] if candidates else ["notion_page_trash_nothing_to_" + ("restore" if restore else "trash")]
    return {
        "ok": not blockers,
        "dry_run": True,
        "lifecycle_action": "notion_page_trash_plan",
        "mode": "restore" if restore else "trash",
        "request_sha256": request_sha256,
        "plan_sha256": plan_sha256,
        "counts": {
            "input_item_count": len(request.items),
            "selected_item_count": selected_count,
            "eligible_item_count": len(candidates),
            "not_eligible_item_count": selected_count - len(candidates),
            "already_settled_count": done,
            "provider_pending_count": len(candidates) - done,
        },
        "permanent_delete": False,
        "provider_calls": 0,
        "credential_reads": 0,
        "writes": 0,
        "privacy_guards": {**_privacy_guards(), "page_ids_echoed": False},
        "blockers": blockers,
    }


def changed_since_recovery(last_edited_time: str | None, recovered_at: str) -> bool:
    """True when the page may have changed after its recovery completed.

    Notion's ``last_edited_time`` has minute precision, so an edit in the
    same minute as the recovery completion is indistinguishable from one
    just before it; both count as changed. Unparseable values count as
    changed.
    """

    try:
        edited = datetime.fromisoformat(str(last_edited_time).replace("Z", "+00:00"))
        recovered = datetime.fromisoformat(str(recovered_at).replace("Z", "+00:00"))
    except ValueError:
        return True
    if edited.tzinfo is None or recovered.tzinfo is None:
        return True
    recovered_minute = recovered.astimezone(timezone.utc).replace(second=0, microsecond=0)
    return edited.astimezone(timezone.utc) >= recovered_minute


def _now(clock: Callable[[], datetime] | None) -> str:
    value = clock() if clock is not None else datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _append_journal(root: Path, path: Path, row: Mapping[str, Any]) -> None:
    raw = (json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0), 0o600)
    try:
        os.write(descriptor, raw)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def execute_trash(
    archive_root: Path | str,
    manifest: Mapping[str, Any],
    *,
    expected_plan_sha256: str,
    max_items: int,
    offset: int = 0,
    restore: bool = False,
    provider: Any,
    credential_broker: Any,
    clock: Callable[[], datetime] | None = None,
    request_pacer: Callable[[], None] | None = None,
    storage: _FilesystemRecoveryStorage | None = None,
) -> dict[str, Any]:
    """Run one reviewed trash (or restore) plan. The caller has already
    verified the exact approval for ``expected_plan_sha256``."""

    state = storage or _FilesystemRecoveryStorage(archive_root)
    root = state.root
    try:
        request = parse_manifest(manifest)
    except ManifestValidationError:
        return _blocked("notion_page_trash_request_invalid", dry_run=False)
    journal_dir = _journal_dir(root)
    if not _ensure_archive_directory_chain(root, journal_dir, create=True):
        return _blocked("notion_page_trash_journal_unavailable", dry_run=False)
    receipt_dir = root.joinpath(*RECEIPT_RELATIVE)
    if not _ensure_archive_directory_chain(root, receipt_dir, create=True):
        return _blocked("notion_page_trash_receipt_unavailable", dry_run=False)
    with _exclusive_file_lock(journal_dir / f"{_digest_part(expected_plan_sha256)}.lock", archive_root=root):
        try:
            request_sha256, candidates, _selected = _select(
                root, request, max_items=max_items, offset=offset, restore=restore, storage=state,
            )
        except (NotionTrashError, RecoveryStorageError) as exc:
            return _blocked(str(getattr(exc, "code", "notion_page_trash_recovery_state_unavailable")), dry_run=False)
        plan_sha256 = _plan_digest(request_sha256, candidates, max_items=max_items, offset=offset, restore=restore)
        if plan_sha256 != expected_plan_sha256:
            return _blocked("notion_page_trash_plan_changed", dry_run=False)
        journal = _journal_path(root, plan_sha256)
        settled = _journal_state(root, plan_sha256)
        scopes = {group.group_id: group.scope_binding for group in request.groups}
        credentials: dict[str, object] = {}
        counts = {outcome: 0 for outcome in (RESTORE_OUTCOMES if restore else TRASH_OUTCOMES)}
        counts["skipped_settled"] = 0
        provider_calls = 0
        stop_reason: str | None = None

        def record(candidate: TrashCandidate, phase: str, outcome: str | None) -> None:
            row = {
                "schema": JOURNAL_SCHEMA,
                "request_sha256": request_sha256,
                "plan_sha256": plan_sha256,
                "mode": "restore" if restore else "trash",
                "item_id": candidate.item.item_id,
                "page_id": candidate.item.page_id,
                "phase": phase,
                "at": _now(clock),
            }
            if outcome is not None:
                row["outcome"] = outcome
            _append_journal(root, journal, row)

        def authorized(credential: object, endpoint: str) -> None:
            if request_pacer is not None:
                before = getattr(request_pacer, "before_request", None)
                before() if callable(before) else request_pacer()
            _revalidate_credential_authority(credential)
            _authorize_credential_provider_request(credential, endpoint)

        try:
            for candidate in candidates:
                if settled.get(candidate.item.item_id) in _SETTLED:
                    counts["skipped_settled"] += 1
                    continue
                group_id = candidate.item.group_id
                if group_id not in credentials:
                    credentials[group_id] = _resolve_credential(credential_broker, scopes[group_id])
                credential = credentials[group_id]

                authorized(credential, "retrieve_page")
                provider_calls += 1
                before = provider.retrieve_page(candidate.item.page_id, credential, api_version=NOTION_API_VERSION)
                if before.status == 401:
                    stop_reason = "notion_page_trash_credential_unauthorized"
                    break
                if before.status in {403, 404} or before.status != 200:
                    outcome = {403: "forbidden", 404: "not_found_or_not_shared"}.get(before.status, "retryable_error")
                    record(candidate, "terminal", outcome)
                    counts[outcome] += 1
                    continue
                payload = before.payload if isinstance(before.payload, Mapping) else {}
                currently = payload.get("in_trash")
                if restore:
                    if currently is False:
                        record(candidate, "terminal", "already_restored")
                        counts["already_restored"] += 1
                        continue
                else:
                    if currently is True:
                        record(candidate, "terminal", "already_in_trash")
                        counts["already_in_trash"] += 1
                        continue
                    if changed_since_recovery(_last_edited_time(payload), candidate.recovered_at):
                        record(candidate, "terminal", "changed_since_recovery")
                        counts["changed_since_recovery"] += 1
                        continue

                record(candidate, "patch_started", None)
                authorized(credential, "move_page_to_trash")
                provider_calls += 1
                moved = provider.move_page_to_trash(
                    candidate.item.page_id, credential, api_version=NOTION_API_VERSION, in_trash=not restore,
                )
                if moved.status == 403:
                    # The token can read but not update: every later PATCH
                    # would fail the same way.
                    record(candidate, "terminal", "forbidden")
                    counts["forbidden"] += 1
                    stop_reason = "notion_update_capability_missing"
                    break
                if moved.status == 401:
                    record(candidate, "terminal", "unconfirmed")
                    counts["unconfirmed"] += 1
                    stop_reason = "notion_page_trash_credential_unauthorized"
                    break

                authorized(credential, "retrieve_page")
                provider_calls += 1
                after = provider.retrieve_page(candidate.item.page_id, credential, api_version=NOTION_API_VERSION)
                after_payload = after.payload if isinstance(after.payload, Mapping) else {}
                if after.status == 200 and after_payload.get("in_trash") is (not restore):
                    outcome = "restored" if restore else "trashed"
                else:
                    outcome = "unconfirmed"
                record(candidate, "terminal", outcome)
                counts[outcome] += 1
        except NotionTrashError as exc:
            stop_reason = exc.code
        except OSError:
            stop_reason = "notion_page_trash_journal_write_failed"
        except Exception:
            stop_reason = "notion_page_trash_provider_boundary_failed"
        finally:
            credentials_closed = _close_resolved_credentials(credentials.values())

        receipt = {
            "schema": RECEIPT_SCHEMA,
            "request_sha256": request_sha256,
            "plan_sha256": plan_sha256,
            "mode": "restore" if restore else "trash",
            "counts": counts,
            "stop_reason": stop_reason,
            "permanent_delete": False,
            "completed_at": _now(clock),
        }
        receipt_raw = _canonical_json_bytes(receipt)
        receipt_path = receipt_dir / f"{_digest_part(plan_sha256)[:16]}.{_digest_part(_sha256_id(receipt_raw))[:16]}.receipt.json"
        try:
            descriptor = os.open(receipt_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
            try:
                os.write(descriptor, receipt_raw + b"\n")
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            receipt_relative = receipt_path.relative_to(root).as_posix()
        except OSError:
            receipt_relative = None
        pending = sum(1 for candidate in candidates
                      if _journal_state(root, plan_sha256).get(candidate.item.item_id) not in _SETTLED)
        return {
            "ok": stop_reason is None,
            "dry_run": False,
            "lifecycle_action": "notion_page_trash",
            "mode": "restore" if restore else "trash",
            "request_sha256": request_sha256,
            "plan_sha256": plan_sha256,
            "counts": {**counts, "remaining_count": pending},
            "stop_reason": stop_reason,
            "reason_code": stop_reason or "notion_page_trash_completed",
            "blockers": [stop_reason] if stop_reason else [],
            "receipt_path": receipt_relative,
            "permanent_delete": False,
            "provider_calls": provider_calls,
            "credentials_closed": credentials_closed,
            "privacy_guards": {**_privacy_guards(), "page_ids_echoed": False},
            "next_step": (
                "Rerun the same command to resume; settled pages are skipped."
                if pending else None
            ),
        }
