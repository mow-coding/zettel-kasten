"""Bounded duplicate object-manifest classification and exact-row repair.

The module deliberately separates three cases that used to collapse into one
``duplicate_object_id`` blocker:

* byte-identical repeated rows, which can be removed without merging evidence;
* compatible repeated evidence, which needs a human-designed merge policy; and
* conflicting definitions, which must remain blocked.

Only the first case is mechanically repairable.  The writer is bound to one
live, one-use :mod:`wom_kit.exact_human_approval` reference and preserves the
original manifest bytes in a create-only snapshot before replacing the
manifest.  Public results contain counts and digests, never object ids, paths,
location labels, provenance values, or row contents.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat as stat_module
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

import yaml

from .exact_human_approval import (
    _ClaimedExactHumanApproval,
    ExactHumanApprovalError,
    exact_human_approval_archive_identity_sha256,
)
from .exact_human_approval_windows import (
    ExactHumanApprovalContext,
    ExactHumanApprovalOperation,
)


PLAN_SCHEMA_VERSION = "wom-kit/duplicate-object-reconciliation-plan/v0.1"
RESULT_SCHEMA_VERSION = "wom-kit/duplicate-object-reconciliation-result/v0.1"
JOURNAL_SCHEMA_VERSION = "wom-kit/duplicate-object-reconciliation-journal/v0.1"
RECEIPT_SCHEMA_VERSION = "wom-kit/duplicate-object-reconciliation-receipt/v0.1"
MANIFEST_RELATIVE_PATH = PurePosixPath("objects/manifests/files.jsonl")
SNAPSHOT_ROOT = PurePosixPath("snapshots/objects/duplicate-reconciliation")
JOURNAL_ROOT = PurePosixPath("journals/objects/duplicate-reconciliation")
RECEIPT_ROOT = PurePosixPath("receipts/objects/duplicate-reconciliation")
LOCK_ROOT = PurePosixPath("profiles/local/duplicate-object-reconciliation/locks")
MAX_MANIFEST_BYTES = 64 * 1024 * 1024
MAX_MANIFEST_ROWS = 1_000_000

_OBJECT_ID_RE = re.compile(r"sha256:([0-9a-f]{64})\Z")
_SHA256_RE = re.compile(r"(?:sha256:)?([0-9a-f]{64})\Z")
_CORE_FIELDS = ("object_id", "sha256", "logical_key", "mime", "size_bytes")
_WINDOWS_REPARSE_ATTRIBUTE = 0x400


class DuplicateObjectReconciliationError(RuntimeError):
    _CODES = {
        "duplicate_object_archive_invalid",
        "duplicate_object_manifest_missing",
        "duplicate_object_manifest_unsafe",
        "duplicate_object_manifest_too_large",
        "duplicate_object_manifest_invalid",
        "duplicate_object_manifest_changed",
        "duplicate_object_no_duplicates",
        "duplicate_object_human_resolution_required",
        "duplicate_object_plan_invalid",
        "duplicate_object_approval_required",
        "duplicate_object_reconciliation_conflict",
        "duplicate_object_reconciliation_state_unknown",
    }

    def __init__(self, code: str) -> None:
        self.code = code if code in self._CODES else "duplicate_object_reconciliation_state_unknown"
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"DuplicateObjectReconciliationError({self.code!r})"


def _fail(code: str) -> DuplicateObjectReconciliationError:
    return DuplicateObjectReconciliationError(code)


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _canonical_bytes(document: Mapping[str, Any]) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii") + b"\n"


def _is_reparse_point(value: os.stat_result) -> bool:
    return bool(
        int(getattr(value, "st_file_attributes", 0))
        & _WINDOWS_REPARSE_ATTRIBUTE
    )


def _identity(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        int(value.st_dev),
        int(value.st_ino),
        int(value.st_mode),
        int(value.st_size),
        int(value.st_mtime_ns),
        int(value.st_ctime_ns),
    )


def _assert_internal_parents(root: Path, path: Path, *, create: bool) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError:
        raise _fail("duplicate_object_manifest_unsafe") from None
    current = root
    for part in relative.parts[:-1]:
        current = current / part
        if create:
            try:
                current.mkdir()
            except FileExistsError:
                pass
        try:
            current_stat = os.lstat(current)
        except OSError:
            raise _fail("duplicate_object_manifest_unsafe") from None
        if (
            stat_module.S_ISLNK(current_stat.st_mode)
            or _is_reparse_point(current_stat)
            or not stat_module.S_ISDIR(current_stat.st_mode)
        ):
            raise _fail("duplicate_object_manifest_unsafe")


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _safe_root(value: Path | str) -> tuple[Path, str]:
    try:
        root = Path(value).resolve(strict=True)
        root_stat = os.lstat(root)
        marker = root / "archive.yml"
        marker_stat = os.lstat(marker)
        if (
            stat_module.S_ISLNK(root_stat.st_mode)
            or _is_reparse_point(root_stat)
            or not stat_module.S_ISDIR(root_stat.st_mode)
            or stat_module.S_ISLNK(marker_stat.st_mode)
            or _is_reparse_point(marker_stat)
            or not stat_module.S_ISREG(marker_stat.st_mode)
            or marker_stat.st_size > 1024 * 1024
        ):
            raise OSError
        marker_raw = marker.read_bytes()
        if _identity(os.lstat(marker)) != _identity(marker_stat):
            raise OSError
        document = yaml.safe_load(marker_raw.decode("utf-8"))
        archive_id = document.get("archive_id") if isinstance(document, dict) else None
        if type(archive_id) is not str or not archive_id.strip():
            raise ValueError
        return root, archive_id.strip()
    except BaseException:
        raise _fail("duplicate_object_archive_invalid") from None


def _manifest_path(root: Path) -> Path:
    return root.joinpath(*MANIFEST_RELATIVE_PATH.parts)


def _read_manifest(root: Path) -> bytes:
    path = _manifest_path(root)
    _assert_internal_parents(root, path, create=False)
    try:
        before = os.lstat(path)
    except FileNotFoundError:
        raise _fail("duplicate_object_manifest_missing") from None
    except OSError:
        raise _fail("duplicate_object_manifest_unsafe") from None
    if (
        stat_module.S_ISLNK(before.st_mode)
        or _is_reparse_point(before)
        or not stat_module.S_ISREG(before.st_mode)
        or before.st_size > MAX_MANIFEST_BYTES
    ):
        code = (
            "duplicate_object_manifest_too_large"
            if before.st_size > MAX_MANIFEST_BYTES
            else "duplicate_object_manifest_unsafe"
        )
        raise _fail(code)
    try:
        raw = path.read_bytes()
        after = os.lstat(path)
    except OSError:
        raise _fail("duplicate_object_manifest_unsafe") from None
    if _identity(before) != _identity(after):
        raise _fail("duplicate_object_manifest_changed")
    if len(raw) > MAX_MANIFEST_BYTES:
        raise _fail("duplicate_object_manifest_too_large")
    return raw


def _line_content(raw_line: bytes) -> bytes:
    if raw_line.endswith(b"\r\n"):
        return raw_line[:-2]
    if raw_line.endswith((b"\r", b"\n")):
        return raw_line[:-1]
    return raw_line


@dataclass(frozen=True, repr=False)
class _DuplicateObjectReconciliationPlan:
    archive_root: Path
    archive_id: str
    manifest_sha256: str
    plan_sha256: str
    row_count: int
    duplicate_group_count: int
    duplicate_row_count: int
    exact_group_count: int
    compatible_group_count: int
    conflicting_group_count: int
    removable_row_count: int
    approveable: bool
    _manifest_bytes: bytes
    _replacement_bytes: bytes

    def public_document(self) -> dict[str, Any]:
        reason = (
            "duplicate_object_exact_reconciliation_ready"
            if self.approveable
            else "duplicate_object_human_resolution_required"
        )
        return {
            "schema_version": PLAN_SCHEMA_VERSION,
            "ok": self.approveable,
            "reason_code": reason,
            "manifest_sha256": self.manifest_sha256,
            "plan_sha256": self.plan_sha256,
            "row_count": self.row_count,
            "duplicate_group_count": self.duplicate_group_count,
            "duplicate_row_count": self.duplicate_row_count,
            "classification_counts": {
                "exact_byte_duplicate": self.exact_group_count,
                "compatible_repeated_evidence": self.compatible_group_count,
                "conflicting_definition": self.conflicting_group_count,
            },
            "removable_row_count": self.removable_row_count,
            "automatic_merge_permitted": False,
            "exact_row_deduplication_permitted": self.approveable,
            "requires_exact_human_approval": True,
            "object_ids_echoed": False,
            "paths_echoed": False,
            "row_content_echoed": False,
            "next_safe_actions": (
                ["approve_exact_duplicate_row_reconciliation"]
                if self.approveable
                else ["review_duplicate_object_evidence_without_mutation"]
            ),
        }


def _plan_duplicate_object_reconciliation_core(
    archive_root: Path | str,
) -> _DuplicateObjectReconciliationPlan:
    root, archive_id = _safe_root(archive_root)
    manifest = _read_manifest(root)
    lines = manifest.splitlines(keepends=True)
    if len(lines) > MAX_MANIFEST_ROWS:
        raise _fail("duplicate_object_manifest_too_large")

    parsed: list[tuple[int, bytes, dict[str, Any]]] = []
    groups: dict[str, list[tuple[int, bytes, dict[str, Any]]]] = {}
    nonempty_count = 0
    try:
        for index, raw_line in enumerate(lines):
            content = _line_content(raw_line)
            if not content.strip():
                continue
            nonempty_count += 1
            document = json.loads(
                content.decode("utf-8"), object_pairs_hook=_reject_duplicate_pairs
            )
            if not isinstance(document, dict):
                raise ValueError
            object_id = document.get("object_id")
            match = _OBJECT_ID_RE.fullmatch(str(object_id or ""))
            if match is None:
                raise ValueError
            sha = document.get("sha256")
            sha_match = _SHA256_RE.fullmatch(str(sha or ""))
            if sha_match is None or sha_match.group(1) != match.group(1):
                raise ValueError
            if (
                type(document.get("logical_key")) is not str
                or type(document.get("mime")) is not str
                or type(document.get("size_bytes")) is not int
                or document["size_bytes"] < 0
            ):
                raise ValueError
            row = (index, content, document)
            parsed.append(row)
            groups.setdefault(object_id, []).append(row)
    except (UnicodeError, json.JSONDecodeError, ValueError, TypeError):
        raise _fail("duplicate_object_manifest_invalid") from None

    duplicate_groups = [rows for rows in groups.values() if len(rows) > 1]
    if not duplicate_groups:
        raise _fail("duplicate_object_no_duplicates")

    exact = compatible = conflicting = removable = 0
    remove_indexes: set[int] = set()
    duplicate_rows = 0
    for rows in duplicate_groups:
        duplicate_rows += len(rows) - 1
        first_content = rows[0][1]
        if all(row[1] == first_content for row in rows[1:]):
            exact += 1
            removable += len(rows) - 1
            remove_indexes.update(row[0] for row in rows[1:])
            continue
        first_core = tuple(rows[0][2].get(field) for field in _CORE_FIELDS)
        if all(
            tuple(row[2].get(field) for field in _CORE_FIELDS) == first_core
            for row in rows[1:]
        ):
            compatible += 1
        else:
            conflicting += 1

    approveable = compatible == 0 and conflicting == 0 and removable > 0
    replacement = b"".join(
        raw_line for index, raw_line in enumerate(lines) if index not in remove_indexes
    )
    manifest_sha = _sha256(manifest)
    plan_basis = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "archive_identity_sha256": exact_human_approval_archive_identity_sha256(
            archive_id
        ),
        "manifest_sha256": manifest_sha,
        "replacement_sha256": _sha256(replacement),
        "row_count": nonempty_count,
        "duplicate_group_count": len(duplicate_groups),
        "duplicate_row_count": duplicate_rows,
        "exact_group_count": exact,
        "compatible_group_count": compatible,
        "conflicting_group_count": conflicting,
        "removable_row_count": removable,
    }
    plan_sha = _sha256(_canonical_bytes(plan_basis))
    return _DuplicateObjectReconciliationPlan(
        archive_root=root,
        archive_id=archive_id,
        manifest_sha256=manifest_sha,
        plan_sha256=plan_sha,
        row_count=nonempty_count,
        duplicate_group_count=len(duplicate_groups),
        duplicate_row_count=duplicate_rows,
        exact_group_count=exact,
        compatible_group_count=compatible,
        conflicting_group_count=conflicting,
        removable_row_count=removable,
        approveable=approveable,
        _manifest_bytes=manifest,
        _replacement_bytes=replacement,
    )


def plan_duplicate_object_reconciliation(
    archive_root: Path | str,
) -> dict[str, Any]:
    """Return only the content-free public projection of a private plan."""

    return _plan_duplicate_object_reconciliation_core(
        archive_root
    ).public_document()


def _duplicate_object_reconciliation_context(
    plan: _DuplicateObjectReconciliationPlan,
    *,
    reviewer_claim: str,
) -> ExactHumanApprovalContext:
    if type(plan) is not _DuplicateObjectReconciliationPlan:
        raise _fail("duplicate_object_plan_invalid")
    return ExactHumanApprovalContext(
        operation=ExactHumanApprovalOperation.duplicate_object_reconcile,
        archive_identity_sha256=exact_human_approval_archive_identity_sha256(
            plan.archive_id
        ),
        plan_sha256=plan.plan_sha256,
        target_binding_sha256=plan.manifest_sha256,
        reviewer_claim=reviewer_claim,
        review_binding_codes=(
            "duplicate_classification_counts",
            "manifest_digest",
            "replacement_digest",
        ),
    )


def _create_only(root: Path, path: Path, raw: bytes) -> None:
    _assert_internal_parents(root, path, create=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            descriptor = -1
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _atomic_replace(root: Path, path: Path, raw: bytes) -> None:
    _assert_internal_parents(root, path, create=False)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".duplicate-reconcile-", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            descriptor = -1
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _apply_duplicate_object_reconciliation_core(
    plan: _DuplicateObjectReconciliationPlan,
    approval_claim: _ClaimedExactHumanApproval,
    *,
    context: ExactHumanApprovalContext,
) -> dict[str, Any]:
    """Apply an exact-row-only plan from one current authenticated claim.

    The shared exact-human workflow owns terminal claim finalization.  This
    writer only reauthenticates the still-started concrete claim immediately
    before its first mutation and stores the reference returned by that check.
    """

    if type(plan) is not _DuplicateObjectReconciliationPlan or not plan.approveable:
        raise _fail("duplicate_object_human_resolution_required")
    if (
        type(approval_claim) is not _ClaimedExactHumanApproval
        or type(context) is not ExactHumanApprovalContext
        or context.operation is not ExactHumanApprovalOperation.duplicate_object_reconcile
        or context.plan_sha256 != plan.plan_sha256
        or context.target_binding_sha256 != plan.manifest_sha256
    ):
        raise _fail("duplicate_object_approval_required")

    root, archive_id = _safe_root(plan.archive_root)
    if archive_id != plan.archive_id or root != plan.archive_root:
        raise _fail("duplicate_object_plan_invalid")
    current = _read_manifest(root)
    if current != plan._manifest_bytes:
        raise _fail("duplicate_object_manifest_changed")

    reconcile_id = plan.plan_sha256.removeprefix("sha256:")[:24]
    lock_path = root.joinpath(*LOCK_ROOT.parts, f"{reconcile_id}.lock")
    snapshot_path = root.joinpath(*SNAPSHOT_ROOT.parts, f"{reconcile_id}.manifest.bin")
    journal_path = root.joinpath(*JOURNAL_ROOT.parts, f"{reconcile_id}.json")
    receipt_path = root.joinpath(*RECEIPT_ROOT.parts, f"{reconcile_id}.json")
    lock_descriptor = -1
    lock_created = False
    manifest_replaced = False
    try:
        try:
            approval_reference = (
                _ClaimedExactHumanApproval.assert_ready_for_context(
                    approval_claim,
                    context,
                )
            )
        except ExactHumanApprovalError:
            raise _fail("duplicate_object_approval_required") from None

        # This is the first mutation boundary.  The authenticated started
        # claim above is deliberately rechecked after every read-only preflight.
        _assert_internal_parents(root, lock_path, create=True)
        lock_descriptor = os.open(
            lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
        lock_created = True
        os.write(lock_descriptor, plan.plan_sha256.encode("ascii") + b"\n")
        os.fsync(lock_descriptor)

        _create_only(root, snapshot_path, plan._manifest_bytes)
        journal = {
            "schema_version": JOURNAL_SCHEMA_VERSION,
            "reconciliation_id": reconcile_id,
            "plan_sha256": plan.plan_sha256,
            "manifest_before_sha256": plan.manifest_sha256,
            "manifest_after_sha256": _sha256(plan._replacement_bytes),
            "approval_reference": dict(approval_reference),
            "status": "started",
            "snapshot_created": True,
            "manifest_replaced": False,
            "receipt_created": False,
        }
        _create_only(root, journal_path, _canonical_bytes(journal))
        _atomic_replace(root, _manifest_path(root), plan._replacement_bytes)
        manifest_replaced = True
        if _read_manifest(root) != plan._replacement_bytes:
            raise OSError("manifest_verification_failed")
        receipt = {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "reconciliation_id": reconcile_id,
            "plan_sha256": plan.plan_sha256,
            "manifest_before_sha256": plan.manifest_sha256,
            "manifest_after_sha256": _sha256(plan._replacement_bytes),
            "removed_exact_duplicate_row_count": plan.removable_row_count,
            "compatible_group_count": 0,
            "conflicting_group_count": 0,
            "approval_reference": dict(approval_reference),
            "snapshot_preserved": True,
            "automatic_merge_performed": False,
            "object_ids_stored_in_receipt": False,
            "paths_echoed_in_public_result": False,
        }
        _create_only(root, receipt_path, _canonical_bytes(receipt))
        finalized = dict(journal)
        finalized.update(
            {
                "status": "succeeded",
                "manifest_replaced": True,
                "receipt_created": True,
                "receipt_sha256": _sha256(_canonical_bytes(receipt)),
            }
        )
        _atomic_replace(root, journal_path, _canonical_bytes(finalized))
        return {
            "schema_version": RESULT_SCHEMA_VERSION,
            "ok": True,
            "reason_code": "duplicate_object_exact_reconciliation_succeeded",
            "plan_sha256": plan.plan_sha256,
            "manifest_before_sha256": plan.manifest_sha256,
            "manifest_after_sha256": _sha256(plan._replacement_bytes),
            "removed_exact_duplicate_row_count": plan.removable_row_count,
            "snapshot_preserved": True,
            "receipt_created": True,
            "automatic_merge_performed": False,
            "object_ids_echoed": False,
            "paths_echoed": False,
        }
    except FileExistsError:
        raise _fail("duplicate_object_reconciliation_conflict") from None
    except DuplicateObjectReconciliationError:
        raise
    except BaseException:
        code = (
            "duplicate_object_reconciliation_state_unknown"
            if manifest_replaced
            else "duplicate_object_reconciliation_conflict"
        )
        raise _fail(code) from None
    finally:
        if lock_descriptor >= 0:
            os.close(lock_descriptor)
        # Keep a lock after an ambiguous/applied mutation as durable evidence.
        if lock_created and not manifest_replaced:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass


__all__ = [
    "DuplicateObjectReconciliationError",
    "plan_duplicate_object_reconciliation",
]
