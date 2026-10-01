"""v0.4.54 (owner decision 2026-09-30): delivered feedback letters are deleted.

The operator asked for delivered letters to stop taking space on the PC ("이미
전달된 건 … 내 컴퓨터에 계속 남아 있는 게 불편한데"). v0.4.36 read that request as
"move them to a folder outside the archive" (``operator-feedback-archive``), so
the letters still sat on the same PC. The owner corrected this on 2026-09-30:
cleaning up delivered or resolved letters means deleting them. This module
replaces the move:

* every record whose status is delivered, acknowledged or resolved loses its
  letter body, its body receipts and its revision snapshots for good; nothing is
  copied anywhere;
* the record becomes a content-free deleted record (``feedback_id``,
  ``status: deleted``, ``deleted_at``, ``deleted_from_status``, ``updated_at``);
  no title, no body reference, no hash of the text. It only says "letter N was
  deleted", so the ledger, the body check and the next letter number keep
  working;
* letters that the v0.4.36 move already placed in a folder outside the archive
  are deleted too when that folder is named with ``--moved-folder``: each copy is
  recognised by its bytes matching the archived record, and the old archived
  record becomes a deleted record;
* one deletion receipt names the plan, the ids and the approval so the finalize
  scanner sees the approval id in ``receipts/``.

Dry-run reads and hashes; approve runs under the exact approval broker as the
grantable kind ``operator_feedback_delete`` (one dialog, or the session grant).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import archive_services
from .operator_feedback_body import (
    BODY_PREFIX,
    FEEDBACK_ID_RE,
    MAX_BODY_BYTES,
    MAX_RECEIPT_BYTES,
    MAX_RECORD_BYTES,
    RECEIPT_PREFIX,
    RECORD_PREFIX,
    REVISION_PREFIX,
)

OPERATION = "operator_feedback_delete"
LIFECYCLE_ACTION = "operator_feedback_delete"
SCHEMA_PLAN = "wom-kit/operator-feedback-delete-plan/v0.1"
SCHEMA_RESULT = "wom-kit/operator-feedback-delete-result/v0.1"
SCHEMA_RECEIPT = "wom-kit/operator-feedback-delete-receipt/v0.1"
DELETE_RECEIPT_PREFIX = f"{RECEIPT_PREFIX}/deletions"
DELETABLE_STATUSES = ("delivered", "acknowledged", "resolved")
DELETED_STATUS = "deleted"
# v0.4.36 moved records (retired command operator-feedback-archive).
ARCHIVED_STATUS = "archived"
DELETED_RECORD_KEYS = ("feedback_id", "status", "deleted_at", "deleted_from_status", "updated_at")
ARCHIVED_STUB_KEYS = (
    "archived_at",
    "archived_from_status",
    "body_sha256",
    "body_utf8_bytes",
    "receipt_count",
    "destination_sha256",
    "archived_body_relative",
)
MAX_ITEMS = 5000
MAX_MOVED_RECEIPTS = 256
REVIEW_BINDING_CODES = ("plan_digest_reviewed", "feedback_ids_reviewed")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_REPARSE_FLAG = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

_ERRORS = frozenset({
    "feedback_delete_moved_folder_invalid",
    "feedback_delete_moved_folder_inside_archive",
    "feedback_delete_moved_folder_missing",
    "feedback_delete_plan_changed",
    "feedback_delete_nothing_to_delete",
    "feedback_delete_status_not_deletable",
    "feedback_delete_record_invalid",
    "feedback_delete_write_failed",
    "feedback_delete_approval_claim_invalid",
    "feedback_body_id_invalid",
})


class OperatorFeedbackDeleteError(RuntimeError):
    """Fixed-code failure; never carries a path, a title or body text."""

    def __init__(self, code: str) -> None:
        self.code = code if code in _ERRORS else "feedback_delete_write_failed"
        self.effects: str | None = None
        self.cause_code: str | None = None
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"OperatorFeedbackDeleteError({self.code!r})"


def _fail(code: str, *, effects: str | None = None) -> OperatorFeedbackDeleteError:
    error = OperatorFeedbackDeleteError(code)
    error.effects = effects
    return error


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _is_reparse(info: os.stat_result) -> bool:
    return bool(stat.S_ISLNK(info.st_mode) or (_REPARSE_FLAG and getattr(info, "st_file_attributes", 0) & _REPARSE_FLAG))


def _read_bounded(path: Path, maximum: int) -> bytes | None:
    """Regular-file bytes up to ``maximum`` or None when absent; raises on a reparse point / oversize."""

    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return None
    if _is_reparse(info) or not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
        raise _fail("feedback_delete_record_invalid")
    with path.open("rb") as handle:
        return handle.read(maximum + 1)


def _moved_folder(archive_root: Path, folder: Path | str | None) -> Path | None:
    """The folder the v0.4.36 move used: absolute, outside the archive, an existing plain directory."""

    if folder is None or not str(folder).strip():
        return None
    candidate = Path(str(folder)).expanduser()
    if not candidate.is_absolute():
        raise _fail("feedback_delete_moved_folder_invalid")
    resolved = candidate.resolve()
    root = archive_root.resolve()
    if resolved == root or root in resolved.parents or resolved in root.parents:
        raise _fail("feedback_delete_moved_folder_inside_archive")
    try:
        info = os.lstat(resolved)
    except FileNotFoundError:
        raise _fail("feedback_delete_moved_folder_missing") from None
    if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
        raise _fail("feedback_delete_moved_folder_invalid")
    return resolved


def _record(root: Path, feedback_id: str) -> tuple[Path, dict[str, Any] | None, bytes | None]:
    path = archive_services.archive_internal_path(root, f"{RECORD_PREFIX}/{feedback_id}.yml")
    raw = _read_bounded(path, MAX_RECORD_BYTES)
    if raw is None:
        return path, None, None
    try:
        loaded = archive_services.load_yaml(raw.decode("utf-8"))
    except Exception:
        raise _fail("feedback_delete_record_invalid") from None
    if not isinstance(loaded, dict):
        raise _fail("feedback_delete_record_invalid")
    return path, loaded, raw


def _receipts(root: Path, feedback_id: str) -> list[tuple[str, Path]]:
    """Body receipts and revision snapshots of one id (relative, absolute)."""

    found: list[tuple[str, Path]] = []
    receipt_dir = archive_services.archive_internal_path(root, RECEIPT_PREFIX)
    if receipt_dir.is_dir():
        for path in sorted(receipt_dir.glob(f"{feedback_id}.*.json")):
            if path.is_file() and not _is_reparse(os.lstat(path)):
                found.append((f"{RECEIPT_PREFIX}/{path.name}", path))
    revision_dir = archive_services.archive_internal_path(root, f"{REVISION_PREFIX}/{feedback_id}")
    if revision_dir.is_dir():
        for path in sorted(revision_dir.iterdir()):
            if path.is_file() and not _is_reparse(os.lstat(path)):
                found.append((f"{REVISION_PREFIX}/{feedback_id}/{path.name}", path))
    return found


def _moved_copy(folder: Path, feedback_id: str, body_sha256: str) -> tuple[str, list[tuple[str, int]]]:
    """State of one v0.4.36 copy: ("present", files) when its body bytes match, ("absent", []) or ("changed", [])."""

    base = folder / feedback_id
    try:
        info = os.lstat(base)
    except FileNotFoundError:
        return "absent", []
    if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
        return "changed", []
    try:
        raw = _read_bounded(base / f"{feedback_id}.md", MAX_BODY_BYTES)
    except OperatorFeedbackDeleteError:
        return "changed", []
    if raw is None:
        return "absent", []
    if _sha256(raw) != body_sha256:
        return "changed", []
    files = [(f"{feedback_id}.md", len(raw))]
    receipts = base / "receipts"
    if receipts.is_dir() and not _is_reparse(os.lstat(receipts)):
        for path in sorted(receipts.iterdir())[:MAX_MOVED_RECEIPTS]:
            name = path.name
            if not (name.startswith(f"{feedback_id}.") or name.startswith(f"revisions__{feedback_id}__")):
                continue
            path_info = os.lstat(path)
            if _is_reparse(path_info) or not stat.S_ISREG(path_info.st_mode):
                continue
            files.append((f"receipts/{name}", path_info.st_size))
    return "present", files


def plan_operator_feedback_delete(
    archive_root: Path | str,
    *,
    statuses: tuple[str, ...] | list[str] | None = None,
    feedback_ids: tuple[str, ...] | list[str] | None = None,
    moved_folder: Path | str | None = None,
) -> dict[str, Any]:
    """Read-only plan: which delivered letters would be deleted, with byte digests."""

    root = archive_services.require_existing_archive_root(archive_root)
    blockers: list[str] = []
    try:
        folder = _moved_folder(root, moved_folder)
    except OperatorFeedbackDeleteError as exc:
        return {
            "schema": SCHEMA_PLAN, "ok": False, "state": "blocked", "dry_run": True,
            "lifecycle_action": LIFECYCLE_ACTION, "blockers": [exc.code], "reason_codes": [exc.code],
            "next_safe_actions": [
                "--moved-folder is optional: pass it only to also delete letters that WOM v0.4.36-v0.4.53 moved out of the archive, as the absolute path of that existing folder outside the archive; the path is never echoed."
            ],
            "private_values_echoed": False, "local_paths_echoed": False,
        }
    wanted = tuple(statuses) if statuses else DELETABLE_STATUSES
    if any(status not in DELETABLE_STATUSES for status in wanted):
        blockers.append("feedback_delete_status_not_deletable")
    selected_ids: list[str] | None = None
    if feedback_ids:
        selected_ids = []
        for value in feedback_ids:
            if not isinstance(value, str) or FEEDBACK_ID_RE.fullmatch(value) is None:
                blockers.append("feedback_body_id_invalid")
                break
            selected_ids.append(value)
    items: list[dict[str, Any]] = []
    skipped = {"already_deleted": 0, "other_status": 0, "not_selected": 0, "unreadable": 0,
               "moved_letter_needs_moved_folder": 0, "moved_copy_changed": 0}
    feedback_dir = root / archive_services.OPERATOR_FEEDBACK_DIR
    if feedback_dir.is_dir() and not blockers:
        for path in archive_services.safe_archive_glob(feedback_dir, "*.yml", root):
            projection = archive_services._read_operator_feedback_record_projection(path)
            if projection is None or not projection.get("feedback_id"):
                skipped["unreadable"] += 1
                continue
            feedback_id = projection["feedback_id"]
            status = projection.get("status")
            if selected_ids is not None and feedback_id not in selected_ids:
                skipped["not_selected"] += 1
                continue
            try:
                _record_path, record, record_raw = _record(root, feedback_id)
            except OperatorFeedbackDeleteError:
                skipped["unreadable"] += 1
                continue
            if record is None or record_raw is None:
                skipped["unreadable"] += 1
                continue
            body_path = archive_services.archive_internal_path(root, f"{BODY_PREFIX}/{feedback_id}.md")
            try:
                body_raw = _read_bounded(body_path, MAX_BODY_BYTES)
            except OperatorFeedbackDeleteError:
                skipped["unreadable"] += 1
                continue
            receipts = []
            for relative, receipt_path in _receipts(root, feedback_id):
                try:
                    receipt_raw = _read_bounded(receipt_path, MAX_RECEIPT_BYTES)
                except OperatorFeedbackDeleteError:
                    receipt_raw = None
                if receipt_raw is not None:
                    receipts.append({"relative": relative, "sha256": _sha256(receipt_raw), "bytes": len(receipt_raw)})
            moved: dict[str, Any] | None = None
            if status == DELETED_STATUS:
                # a deleted record whose files survived an interrupted run is finished here
                if body_raw is None and not receipts:
                    skipped["already_deleted"] += 1
                    continue
                source_status = str(record.get("deleted_from_status") or DELETED_STATUS)
            elif status == ARCHIVED_STATUS:
                stub_sha = record.get("body_sha256")
                if folder is None or not isinstance(stub_sha, str) or _SHA_RE.fullmatch(stub_sha) is None:
                    skipped["moved_letter_needs_moved_folder"] += 1
                    continue
                copy_state, files = _moved_copy(folder, feedback_id, stub_sha)
                if copy_state == "changed":
                    skipped["moved_copy_changed"] += 1
                    continue
                moved = {"state": copy_state, "files": [name for name, _size in files],
                         "bytes": sum(size for _name, size in files)}
                source_status = ARCHIVED_STATUS
            elif status in wanted:
                source_status = str(status)
            else:
                skipped["other_status"] += 1
                continue
            items.append({
                "feedback_id": feedback_id,
                "status": source_status,
                "record_sha256": _sha256(record_raw),
                "body_sha256": _sha256(body_raw) if body_raw is not None else None,
                "body_bytes": len(body_raw) if body_raw is not None else 0,
                "receipts": receipts,
                "receipt_bytes": sum(r["bytes"] for r in receipts),
                "moved_copy": moved,
            })
            if len(items) >= MAX_ITEMS:
                break
    items.sort(key=lambda item: item["feedback_id"])
    if not items and not blockers:
        blockers.append("feedback_delete_nothing_to_delete")
    feedback_id_list = [item["feedback_id"] for item in items]
    plan_basis = {
        "schema": SCHEMA_PLAN, "statuses": list(wanted), "moved_folder_named": folder is not None,
        "items": [{"feedback_id": item["feedback_id"], "status": item["status"], "record_sha256": item["record_sha256"],
                   "body_sha256": item["body_sha256"], "receipts": [[r["relative"], r["sha256"]] for r in item["receipts"]],
                   "moved_copy": item["moved_copy"]} for item in items],
    }
    plan_sha256 = _sha256(_canonical(plan_basis))
    counted = (*DELETABLE_STATUSES, ARCHIVED_STATUS, DELETED_STATUS)
    status_counts = {status: sum(1 for item in items if item["status"] == status) for status in counted}
    body_bytes = sum(item["body_bytes"] for item in items)
    receipt_count = sum(len(item["receipts"]) for item in items)
    receipt_bytes = sum(item["receipt_bytes"] for item in items)
    moved_items = [item for item in items if item["moved_copy"] and item["moved_copy"]["state"] == "present"]
    moved_files = sum(len(item["moved_copy"]["files"]) for item in moved_items)
    moved_bytes = sum(item["moved_copy"]["bytes"] for item in moved_items)
    needs_folder = skipped["moved_letter_needs_moved_folder"]
    next_safe: list[str]
    if not blockers:
        next_safe = ["Rerun with --approve --reviewed-by <person:...> --expected-plan-sha256 <plan_sha256> and the same options; one dialog (or the session grant) deletes the whole plan. Deleted letters cannot be recovered by WOM."]
    elif "feedback_delete_nothing_to_delete" in blockers:
        next_safe = ["Nothing to delete: no delivered, acknowledged or resolved letter is left in the archive."]
    else:
        next_safe = []
    if needs_folder:
        next_safe.append(
            f"{needs_folder} letter(s) were moved out of the archive by an older WOM (operator-feedback-archive). To delete those copies as well, add --moved-folder <the absolute folder chosen then>."
        )
    return {
        "schema": SCHEMA_PLAN,
        "ok": not blockers,
        "state": "ready_for_exact_human_approval" if not blockers else "blocked",
        "dry_run": True,
        "lifecycle_action": LIFECYCLE_ACTION,
        "plan_sha256": plan_sha256,
        "feedback_ids_sha256": _sha256(_canonical(feedback_id_list)),
        "moved_folder_named": folder is not None,
        "statuses": list(wanted),
        "item_count": len(items),
        "status_counts": status_counts,
        "feedback_ids": feedback_id_list,
        "body_bytes_total": body_bytes,
        "receipt_count_total": receipt_count,
        "receipt_bytes_total": receipt_bytes,
        "moved_copy_count": len(moved_items),
        "moved_file_count": moved_files,
        "moved_bytes_total": moved_bytes,
        "bytes_freed_total": body_bytes + receipt_bytes + moved_bytes,
        "skipped": skipped,
        "deleted_record_keys": list(DELETED_RECORD_KEYS),
        "recoverable": False,
        "would_change": [
            f"permanently delete {sum(1 for item in items if item['body_sha256'])} letter bodies and {receipt_count} body receipts from the archive ({body_bytes + receipt_bytes} bytes)",
            f"permanently delete {len(moved_items)} letters ({moved_files} files, {moved_bytes} bytes) that an older WOM moved to the named folder",
            f"replace {len(items)} records under {RECORD_PREFIX}/ with one-line deleted records (id, status deleted, date; no title, no text)",
            f"write one deletion receipt under {DELETE_RECEIPT_PREFIX}/",
        ] if items else [],
        "blockers": blockers,
        "reason_codes": blockers or ["operator_feedback_delete_ready"],
        "next_safe_actions": next_safe,
        "private_values_echoed": False,
        "local_paths_echoed": False,
        "titles_echoed": False,
    }


def _deleted_record(feedback_id: str, *, from_status: str, deleted_at: str) -> dict[str, Any]:
    return {
        "feedback_id": feedback_id,
        "status": DELETED_STATUS,
        "deleted_at": deleted_at,
        "deleted_from_status": from_status,
        "updated_at": deleted_at,
    }


def _remove_empty_dir(path: Path) -> None:
    try:
        path.rmdir()
    except OSError:
        pass


def approve_operator_feedback_delete(
    archive_root: Path | str,
    *,
    expected_plan_sha256: str,
    reviewed_by: str,
    statuses: tuple[str, ...] | list[str] | None = None,
    feedback_ids: tuple[str, ...] | list[str] | None = None,
    moved_folder: Path | str | None = None,
    exact_human_approval_claim: Any = None,
) -> dict[str, Any]:
    """The approved deletion: files first, then the one-line record, one id at a time, then one receipt."""

    root = archive_services.require_existing_archive_root(archive_root)
    plan = plan_operator_feedback_delete(root, statuses=statuses, feedback_ids=feedback_ids, moved_folder=moved_folder)
    if not plan.get("ok"):
        raise _fail("feedback_delete_plan_changed" if plan.get("blockers") != ["feedback_delete_nothing_to_delete"]
                    else "feedback_delete_nothing_to_delete", effects="none")
    expected = str(expected_plan_sha256 or "").strip().lower()
    if _SHA_RE.fullmatch(expected) is None or not secrets.compare_digest(plan["plan_sha256"], expected):
        raise _fail("feedback_delete_plan_changed", effects="none")
    envelope: dict[str, Any] | None = None
    if exact_human_approval_claim is not None:
        reference = exact_human_approval_claim.public_reference()
        if not isinstance(reference, Mapping):
            raise _fail("feedback_delete_approval_claim_invalid", effects="none")
        envelope = {**dict(reference), "operation": OPERATION}
    folder = _moved_folder(root, moved_folder)
    deleted_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    deleted: list[str] = []
    failed_id: str | None = None
    failure_code: str | None = None
    receipts_deleted = 0
    moved_files_deleted = 0
    bytes_freed = 0
    for feedback_id in plan["feedback_ids"]:
        try:
            record_path, record, _raw = _record(root, feedback_id)
            if record is None:
                raise _fail("feedback_delete_record_invalid")
            status = str(record.get("status") or "")
            if status == DELETED_STATUS:
                from_status = str(record.get("deleted_from_status") or DELETED_STATUS)
            elif status == ARCHIVED_STATUS or status in DELETABLE_STATUSES:
                from_status = status
            else:
                raise _fail("feedback_delete_plan_changed")
            for _relative, receipt_path in _receipts(root, feedback_id):
                size = os.lstat(receipt_path).st_size
                receipt_path.unlink()
                receipts_deleted += 1
                bytes_freed += size
            revision_dir = archive_services.archive_internal_path(root, f"{REVISION_PREFIX}/{feedback_id}")
            if revision_dir.is_dir():
                _remove_empty_dir(revision_dir)
            body_path = archive_services.archive_internal_path(root, f"{BODY_PREFIX}/{feedback_id}.md")
            if body_path.exists():
                bytes_freed += os.lstat(body_path).st_size
                body_path.unlink()
            if status == ARCHIVED_STATUS and folder is not None:
                stub_sha = str(record.get("body_sha256") or "")
                copy_state, files = _moved_copy(folder, feedback_id, stub_sha)
                if copy_state == "changed":
                    raise _fail("feedback_delete_plan_changed")
                for name, size in files:
                    (folder / feedback_id / name).unlink()
                    moved_files_deleted += 1
                    bytes_freed += size
                _remove_empty_dir(folder / feedback_id / "receipts")
                _remove_empty_dir(folder / feedback_id)
            archive_services._atomic_write_text(
                record_path,
                archive_services.dump_yaml(_deleted_record(feedback_id, from_status=from_status, deleted_at=deleted_at)),
            )
            deleted.append(feedback_id)
        except OperatorFeedbackDeleteError as exc:
            failed_id, failure_code = feedback_id, exc.code
            break
        except OSError:
            failed_id, failure_code = feedback_id, "feedback_delete_write_failed"
            break
    if folder is not None:
        _remove_empty_dir(folder)
    receipt_relative = f"{DELETE_RECEIPT_PREFIX}/{plan['plan_sha256'][:16]}.json"
    receipt_document: dict[str, Any] = {
        "schema": SCHEMA_RECEIPT,
        "lifecycle_action": LIFECYCLE_ACTION,
        "plan_sha256": plan["plan_sha256"],
        "deleted_at": deleted_at,
        "reviewed_by": reviewed_by,
        "deleted_feedback_ids": deleted,
        "deleted_count": len(deleted),
        "receipts_deleted": receipts_deleted,
        "moved_files_deleted": moved_files_deleted,
        "bytes_freed": bytes_freed,
        "failed_feedback_id": failed_id,
        "failure_code": failure_code,
        "complete": failed_id is None,
    }
    if envelope is not None:
        receipt_document["exact_human_approval"] = envelope
    try:
        archive_services._atomic_write_json(archive_services.archive_internal_path(root, receipt_relative), receipt_document)
        receipt_written = True
    except OSError:
        receipt_written = False
    complete = failed_id is None and receipt_written
    return {
        "schema": SCHEMA_RESULT,
        "ok": complete,
        "state": "deleted" if complete else "partially_deleted",
        "dry_run": False,
        "approved": True,
        "lifecycle_action": LIFECYCLE_ACTION,
        "plan_sha256": plan["plan_sha256"],
        "deleted_count": len(deleted),
        "planned_count": plan["item_count"],
        "receipts_deleted": receipts_deleted,
        "moved_files_deleted": moved_files_deleted,
        "bytes_freed": bytes_freed,
        "deleted_feedback_ids": deleted,
        "failed_feedback_id": failed_id,
        "failure_code": failure_code,
        "receipt_relative_path": receipt_relative if receipt_written else None,
        "deleted_record_keys": list(DELETED_RECORD_KEYS),
        "recoverable": False,
        "blockers": [] if complete else [failure_code or "feedback_delete_write_failed"],
        "next_safe_actions": (
            ["Deleted letters keep only a one-line record (status deleted); operator-feedback-body-check reports them as deleted_record and the ledger counts them as deleted."]
            if complete else
            ["The run stopped at failed_feedback_id after deleting deleted_count letters. Fix the named condition and rerun --dry-run: the remaining letters (including any half-deleted one) form a new plan."]
        ),
        "private_values_echoed": False,
        "local_paths_echoed": False,
        "titles_echoed": False,
    }


def deleted_record(root: Path, feedback_id: str) -> dict[str, Any] | None:
    """The fields of a deleted record, or None when the record is not one."""

    try:
        _path, record, _raw = _record(root, feedback_id)
    except OperatorFeedbackDeleteError:
        return None
    if record is None or record.get("status") != DELETED_STATUS:
        return None
    return {key: record.get(key) for key in DELETED_RECORD_KEYS}


def archived_stub(root: Path, feedback_id: str) -> dict[str, Any] | None:
    """The stub fields of a v0.4.36 archived record, or None when the record is not one."""

    try:
        _path, record, _raw = _record(root, feedback_id)
    except OperatorFeedbackDeleteError:
        return None
    if record is None or record.get("status") != ARCHIVED_STATUS:
        return None
    if not all(key in record for key in ARCHIVED_STUB_KEYS):
        return None
    body_sha = record.get("body_sha256")
    if not isinstance(body_sha, str) or _SHA_RE.fullmatch(body_sha) is None:
        return None
    return {key: record.get(key) for key in ARCHIVED_STUB_KEYS}


__all__ = [
    "ARCHIVED_STATUS",
    "DELETABLE_STATUSES",
    "DELETED_STATUS",
    "OPERATION",
    "OperatorFeedbackDeleteError",
    "REVIEW_BINDING_CODES",
    "approve_operator_feedback_delete",
    "archived_stub",
    "deleted_record",
    "plan_operator_feedback_delete",
]
