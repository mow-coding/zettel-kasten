"""v0.4.36 (beta letter 164 ⑧ / 168 ⑤-2, request 8): delivered-feedback archival.

The operator asked three times for delivered letters to leave the archive: "이미
전달된 건 … 내 아카이브가 아니잖아. 내 컴퓨터에 계속 남아 있는 게 불편한데."
The design the client answered in letter 168 ⑤-2 is implemented as written:

* the operator designates a sibling folder OUTSIDE the archive (never inside
  it, never a WOM-managed path); its absolute path is never echoed, only its
  SHA-256;
* every record whose status is immutable-delivered (``delivered``,
  ``acknowledged``, ``resolved``) is moved: the letter body and its body
  receipts go to ``<destination>/<feedback_id>/``, byte-verified after the
  copy, and only then removed from the archive;
* a content-free stub stays in ``ops/feedback/<id>.yml`` (status ``archived``,
  ``archived_at``, ``archived_from_status``, ``body_sha256``,
  ``body_utf8_bytes``, ``receipt_count``, ``destination_sha256``,
  ``archived_body_relative``), so the ledger, the body check and the
  supersession chain keep recognising the id;
* one archive receipt names the plan, the ids and the claim so the finalize
  scanner sees the approval id in ``receipts/``.

Dry-run reads and hashes; approve runs under the exact approval broker as the
grantable kind ``operator_feedback_archive`` (one dialog, or the session grant).
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

OPERATION = "operator_feedback_archive"
LIFECYCLE_ACTION = "operator_feedback_archive"
SCHEMA_PLAN = "wom-kit/operator-feedback-archive-plan/v0.1"
SCHEMA_RESULT = "wom-kit/operator-feedback-archive-result/v0.1"
SCHEMA_RECEIPT = "wom-kit/operator-feedback-archive-receipt/v0.1"
ARCHIVE_RECEIPT_PREFIX = f"{RECEIPT_PREFIX}/archivals"
ARCHIVABLE_STATUSES = ("delivered", "acknowledged", "resolved")
ARCHIVED_STATUS = "archived"
STUB_KEYS = (
    "archived_at",
    "archived_from_status",
    "body_sha256",
    "body_utf8_bytes",
    "receipt_count",
    "destination_sha256",
    "archived_body_relative",
)
MAX_ITEMS = 5000
REVIEW_BINDING_CODES = ("plan_digest_reviewed", "destination_digest_reviewed")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_REPARSE_FLAG = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

_ERRORS = frozenset({
    "feedback_archive_destination_invalid",
    "feedback_archive_destination_inside_archive",
    "feedback_archive_destination_conflict",
    "feedback_archive_plan_changed",
    "feedback_archive_nothing_to_archive",
    "feedback_archive_body_missing",
    "feedback_archive_record_invalid",
    "feedback_archive_copy_verification_failed",
    "feedback_archive_write_failed",
    "feedback_archive_approval_claim_invalid",
})


class OperatorFeedbackArchiveError(RuntimeError):
    """Fixed-code failure; never carries a path, a title or body text."""

    def __init__(self, code: str) -> None:
        self.code = code if code in _ERRORS else "feedback_archive_write_failed"
        self.effects: str | None = None
        self.cause_code: str | None = None
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"OperatorFeedbackArchiveError({self.code!r})"


def _fail(code: str, *, effects: str | None = None) -> OperatorFeedbackArchiveError:
    error = OperatorFeedbackArchiveError(code)
    error.effects = effects
    return error


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _is_reparse(info: os.stat_result) -> bool:
    return bool(stat.S_ISLNK(info.st_mode) or (_REPARSE_FLAG and getattr(info, "st_file_attributes", 0) & _REPARSE_FLAG))


def _read_bounded(path: Path, maximum: int) -> bytes | None:
    """Regular-file bytes up to ``maximum`` or None when absent; raises on a reparse point / oversize."""

    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return None
    if _is_reparse(info) or not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
        raise _fail("feedback_archive_record_invalid")
    with path.open("rb") as handle:
        return handle.read(maximum + 1)


def _destination(archive_root: Path, destination: Path | str | None) -> tuple[Path, str]:
    """The operator-designated folder: absolute, outside the archive, no reparse point."""

    if destination is None or not str(destination).strip():
        raise _fail("feedback_archive_destination_invalid")
    candidate = Path(str(destination)).expanduser()
    if not candidate.is_absolute():
        raise _fail("feedback_archive_destination_invalid")
    resolved = candidate.resolve()
    root = archive_root.resolve()
    if resolved == root or root in resolved.parents:
        raise _fail("feedback_archive_destination_inside_archive")
    if resolved in root.parents:
        # the archive's own parent chain is not a sibling folder
        raise _fail("feedback_archive_destination_inside_archive")
    if resolved.exists():
        info = os.lstat(resolved)
        if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
            raise _fail("feedback_archive_destination_invalid")
    return resolved, _sha256(str(resolved).encode("utf-8"))


def _record(root: Path, feedback_id: str) -> tuple[Path, dict[str, Any] | None]:
    path = archive_services.archive_internal_path(root, f"{RECORD_PREFIX}/{feedback_id}.yml")
    raw = _read_bounded(path, MAX_RECORD_BYTES)
    if raw is None:
        return path, None
    try:
        loaded = archive_services.load_yaml(raw.decode("utf-8"))
    except Exception:
        raise _fail("feedback_archive_record_invalid") from None
    if not isinstance(loaded, dict):
        raise _fail("feedback_archive_record_invalid")
    return path, loaded


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


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def plan_operator_feedback_archive(
    archive_root: Path | str,
    *,
    destination: Path | str | None,
    statuses: tuple[str, ...] | list[str] | None = None,
    feedback_ids: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    """Read-only plan: which delivered records would move, with byte digests."""

    root = archive_services.require_existing_archive_root(archive_root)
    blockers: list[str] = []
    try:
        dest, dest_sha = _destination(root, destination)
    except OperatorFeedbackArchiveError as exc:
        return {
            "schema": SCHEMA_PLAN, "ok": False, "state": "blocked", "dry_run": True,
            "lifecycle_action": LIFECYCLE_ACTION, "blockers": [exc.code], "reason_codes": [exc.code],
            "next_safe_actions": [
                "Pass --destination <absolute folder outside the archive root> (an operator-designated sibling folder such as <parent of archive>/ops-feedback-archive); the path is never echoed."
            ],
            "private_values_echoed": False, "local_paths_echoed": False,
        }
    wanted = tuple(statuses) if statuses else ARCHIVABLE_STATUSES
    if any(status not in ARCHIVABLE_STATUSES for status in wanted):
        blockers.append("feedback_archive_status_not_archivable")
    selected_ids = None
    if feedback_ids:
        selected_ids = []
        for value in feedback_ids:
            if not isinstance(value, str) or FEEDBACK_ID_RE.fullmatch(value) is None:
                blockers.append("feedback_body_id_invalid")
                break
            selected_ids.append(value)
    items: list[dict[str, Any]] = []
    skipped: dict[str, int] = {"already_archived": 0, "other_status": 0, "body_missing": 0, "not_selected": 0, "unreadable": 0}
    body_missing_ids: list[str] = []
    feedback_dir = root / archive_services.OPERATOR_FEEDBACK_DIR
    if feedback_dir.is_dir() and not blockers:
        for path in archive_services.safe_archive_glob(feedback_dir, "*.yml", root):
            projection = archive_services._read_operator_feedback_record_projection(path)
            if projection is None or not projection.get("feedback_id"):
                skipped["unreadable"] += 1
                continue
            feedback_id = projection["feedback_id"]
            status = projection.get("status")
            if status == ARCHIVED_STATUS:
                skipped["already_archived"] += 1
                continue
            if status not in wanted:
                skipped["other_status"] += 1
                continue
            if selected_ids is not None and feedback_id not in selected_ids:
                skipped["not_selected"] += 1
                continue
            body_path = archive_services.archive_internal_path(root, f"{BODY_PREFIX}/{feedback_id}.md")
            try:
                raw = _read_bounded(body_path, MAX_BODY_BYTES)
            except OperatorFeedbackArchiveError:
                skipped["unreadable"] += 1
                continue
            if raw is None:
                skipped["body_missing"] += 1
                body_missing_ids.append(feedback_id)
                continue
            receipts = []
            receipt_bytes = 0
            for relative, receipt_path in _receipts(root, feedback_id):
                try:
                    receipt_raw = _read_bounded(receipt_path, MAX_RECEIPT_BYTES)
                except OperatorFeedbackArchiveError:
                    receipt_raw = None
                if receipt_raw is None:
                    continue
                receipts.append({"relative": relative, "sha256": _sha256(receipt_raw), "bytes": len(receipt_raw)})
                receipt_bytes += len(receipt_raw)
            items.append({
                "feedback_id": feedback_id, "status": status,
                "body_sha256": _sha256(raw), "body_utf8_bytes": len(raw),
                "receipts": receipts, "receipt_count": len(receipts), "receipt_bytes": receipt_bytes,
            })
            if len(items) >= MAX_ITEMS:
                break
    items.sort(key=lambda item: item["feedback_id"])
    if not items and not blockers:
        blockers.append("feedback_archive_nothing_to_archive")
    plan_basis = {
        "schema": SCHEMA_PLAN, "destination_sha256": dest_sha, "statuses": list(wanted),
        "items": [{"feedback_id": item["feedback_id"], "status": item["status"], "body_sha256": item["body_sha256"],
                   "body_utf8_bytes": item["body_utf8_bytes"],
                   "receipts": [[r["relative"], r["sha256"]] for r in item["receipts"]]} for item in items],
    }
    plan_sha256 = _sha256(_canonical(plan_basis))
    status_counts = {status: sum(1 for item in items if item["status"] == status) for status in ARCHIVABLE_STATUSES}
    return {
        "schema": SCHEMA_PLAN,
        "ok": not blockers,
        "state": "ready_for_exact_human_approval" if not blockers else "blocked",
        "dry_run": True,
        "lifecycle_action": LIFECYCLE_ACTION,
        "plan_sha256": plan_sha256,
        "destination_sha256": dest_sha,
        "destination_exists": dest.exists(),
        "statuses": list(wanted),
        "item_count": len(items),
        "status_counts": status_counts,
        "body_bytes_total": sum(item["body_utf8_bytes"] for item in items),
        "receipt_count_total": sum(item["receipt_count"] for item in items),
        "receipt_bytes_total": sum(item["receipt_bytes"] for item in items),
        "feedback_ids": [item["feedback_id"] for item in items],
        "skipped": skipped,
        "body_missing_feedback_ids": body_missing_ids,
        "stub_keys": list(STUB_KEYS),
        "would_change": [
            f"copy {len(items)} letter bodies and {sum(item['receipt_count'] for item in items)} body receipts to <destination>/<feedback_id>/ and verify every copy byte for byte",
            f"rewrite {len(items)} records under {RECORD_PREFIX}/ as content-free archived stubs",
            f"remove the {len(items)} letter bodies and their receipts from the archive after verification",
            f"write one archive receipt under {ARCHIVE_RECEIPT_PREFIX}/",
        ] if items else [],
        "blockers": blockers,
        "reason_codes": blockers or ["operator_feedback_archive_ready"],
        "next_safe_actions": (
            ["Rerun with --approve --reviewed-by <person:...> --expected-plan-sha256 <plan_sha256> and the same --destination; one dialog (or the session grant) covers the whole plan."]
            if not blockers else
            (["Nothing to archive: every delivered / acknowledged / resolved record is already archived or has no body in the archive."
              + (" body_missing_feedback_ids lists records whose letter is absent; they are left as they are." if body_missing_ids else "")]
             if "feedback_archive_nothing_to_archive" in blockers else [])
        ),
        "private_values_echoed": False,
        "local_paths_echoed": False,
        "destination_echoed": False,
        "titles_echoed": False,
    }


def _copy_verified(source_raw: bytes, target: Path) -> None:
    """Write the bytes to a new file (or accept an identical existing one) and read them back."""

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        existing = _read_bounded(target, max(MAX_BODY_BYTES, MAX_RECEIPT_BYTES))
        if existing == source_raw:
            return
        raise _fail("feedback_archive_destination_conflict")
    tmp = target.parent / (target.name + ".part-" + secrets.token_hex(8))
    try:
        with tmp.open("wb") as handle:
            handle.write(source_raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)
    if _read_bounded(target, len(source_raw) + 1) != source_raw:
        raise _fail("feedback_archive_copy_verification_failed")


def _stub(record: dict[str, Any], *, item: dict[str, Any], destination_sha256: str, archived_at: str) -> dict[str, Any]:
    stub = dict(record)
    stub["status"] = ARCHIVED_STATUS
    stub["archived_at"] = archived_at
    stub["archived_from_status"] = item["status"]
    stub["body_sha256"] = item["body_sha256"]
    stub["body_utf8_bytes"] = item["body_utf8_bytes"]
    stub["receipt_count"] = item["receipt_count"]
    stub["destination_sha256"] = destination_sha256
    stub["archived_body_relative"] = f"{item['feedback_id']}/{item['feedback_id']}.md"
    stub["updated_at"] = archived_at
    return stub


def approve_operator_feedback_archive(
    archive_root: Path | str,
    *,
    destination: Path | str | None,
    expected_plan_sha256: str,
    reviewed_by: str,
    statuses: tuple[str, ...] | list[str] | None = None,
    feedback_ids: tuple[str, ...] | list[str] | None = None,
    exact_human_approval_claim: Any = None,
) -> dict[str, Any]:
    """The approved move: copy → verify → stub → remove, one id at a time, then one receipt."""

    root = archive_services.require_existing_archive_root(archive_root)
    plan = plan_operator_feedback_archive(root, destination=destination, statuses=statuses, feedback_ids=feedback_ids)
    if not plan.get("ok"):
        raise _fail("feedback_archive_plan_changed" if plan.get("blockers") != ["feedback_archive_nothing_to_archive"]
                    else "feedback_archive_nothing_to_archive", effects="none")
    expected = str(expected_plan_sha256 or "").strip().lower()
    if _SHA_RE.fullmatch(expected) is None or not secrets.compare_digest(plan["plan_sha256"], expected):
        raise _fail("feedback_archive_plan_changed", effects="none")
    envelope: dict[str, Any] | None = None
    if exact_human_approval_claim is not None:
        reference = exact_human_approval_claim.public_reference()
        if not isinstance(reference, Mapping):
            raise _fail("feedback_archive_approval_claim_invalid", effects="none")
        envelope = {**dict(reference), "operation": OPERATION}
    dest, dest_sha = _destination(root, destination)
    dest.mkdir(parents=True, exist_ok=True)
    archived_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    archived: list[str] = []
    failed_id: str | None = None
    failure_code: str | None = None
    receipts_moved = 0
    for feedback_id in plan["feedback_ids"]:
        try:
            record_path, record = _record(root, feedback_id)
            if record is None:
                raise _fail("feedback_archive_record_invalid")
            body_path = archive_services.archive_internal_path(root, f"{BODY_PREFIX}/{feedback_id}.md")
            raw = _read_bounded(body_path, MAX_BODY_BYTES)
            if raw is None:
                raise _fail("feedback_archive_body_missing")
            item = {"feedback_id": feedback_id, "status": str(record.get("status") or ""),
                    "body_sha256": _sha256(raw), "body_utf8_bytes": len(raw), "receipt_count": 0}
            if item["status"] not in ARCHIVABLE_STATUSES:
                raise _fail("feedback_archive_plan_changed")
            _copy_verified(raw, dest / feedback_id / f"{feedback_id}.md")
            moved_receipts: list[Path] = []
            for relative, receipt_path in _receipts(root, feedback_id):
                receipt_raw = _read_bounded(receipt_path, MAX_RECEIPT_BYTES)
                if receipt_raw is None:
                    continue
                target_name = relative.removeprefix(RECEIPT_PREFIX + "/").replace("/", "__")
                _copy_verified(receipt_raw, dest / feedback_id / "receipts" / target_name)
                moved_receipts.append(receipt_path)
            item["receipt_count"] = len(moved_receipts)
            stub = _stub(record, item=item, destination_sha256=dest_sha, archived_at=archived_at)
            archive_services._atomic_write_text(record_path, archive_services.dump_yaml(stub))
            body_path.unlink()
            for receipt_path in moved_receipts:
                receipt_path.unlink(missing_ok=True)
            receipts_moved += len(moved_receipts)
            archived.append(feedback_id)
        except OperatorFeedbackArchiveError as exc:
            failed_id, failure_code = feedback_id, exc.code
            break
        except OSError:
            failed_id, failure_code = feedback_id, "feedback_archive_write_failed"
            break
    receipt_relative = f"{ARCHIVE_RECEIPT_PREFIX}/{plan['plan_sha256'][:16]}.json"
    receipt_document: dict[str, Any] = {
        "schema": SCHEMA_RECEIPT,
        "lifecycle_action": LIFECYCLE_ACTION,
        "plan_sha256": plan["plan_sha256"],
        "destination_sha256": dest_sha,
        "archived_at": archived_at,
        "reviewed_by": reviewed_by,
        "archived_feedback_ids": archived,
        "archived_count": len(archived),
        "receipts_moved": receipts_moved,
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
        "state": "archived" if complete else "partially_archived",
        "dry_run": False,
        "approved": True,
        "lifecycle_action": LIFECYCLE_ACTION,
        "plan_sha256": plan["plan_sha256"],
        "destination_sha256": dest_sha,
        "archived_count": len(archived),
        "planned_count": plan["item_count"],
        "receipts_moved": receipts_moved,
        "archived_feedback_ids": archived,
        "failed_feedback_id": failed_id,
        "failure_code": failure_code,
        "receipt_relative_path": receipt_relative if receipt_written else None,
        "stub_keys": list(STUB_KEYS),
        "blockers": [] if complete else [failure_code or "feedback_archive_write_failed"],
        "next_safe_actions": (
            ["Archived records keep a content-free stub (status archived); operator-feedback-body-check reports them as archived_stub and the ledger counts them as archived."]
            if complete else
            ["The run stopped at failed_feedback_id after archiving archived_count records; those already moved are complete (stub written, body removed). Fix the named condition and rerun --dry-run: the remaining records form a new plan."]
        ),
        "private_values_echoed": False,
        "local_paths_echoed": False,
        "destination_echoed": False,
        "titles_echoed": False,
    }


def archived_stub(root: Path, feedback_id: str) -> dict[str, Any] | None:
    """The stub fields of an archived record, or None when the record is not an archived stub."""

    try:
        _path, record = _record(root, feedback_id)
    except OperatorFeedbackArchiveError:
        return None
    if record is None or record.get("status") != ARCHIVED_STATUS:
        return None
    if not all(key in record for key in STUB_KEYS):
        return None
    body_sha = record.get("body_sha256")
    if not isinstance(body_sha, str) or _SHA_RE.fullmatch(body_sha) is None:
        return None
    return {key: record.get(key) for key in STUB_KEYS}


__all__ = [
    "ARCHIVABLE_STATUSES",
    "ARCHIVED_STATUS",
    "OPERATION",
    "OperatorFeedbackArchiveError",
    "REVIEW_BINDING_CODES",
    "STUB_KEYS",
    "approve_operator_feedback_archive",
    "archived_stub",
    "plan_operator_feedback_archive",
]
