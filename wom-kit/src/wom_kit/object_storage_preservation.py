"""Exact, resumable emergency preservation for local-only Objet bytes.

This module intentionally does not call the emergency copy an adoption.  A
successful item creates one immutable ``bytes_preserved`` receipt after a
content-addressed upload (or an idempotent already-present result) and two
whole-object checks.  It does not add a ``wom_uploaded`` manifest location and
therefore cannot satisfy or bypass the formal adoption workflow.

The central object manifest is scanned once.  It is never rewritten once per
item: the common ExactOperationManifest checkpoint store and immutable
per-object receipts provide the append-only execution surface.  Duplicate
object definitions remain review-only even when their digest and size agree.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from . import archive_services
from . import object_storage_setup_registration
from .exact_human_approval import (
    ExactHumanApprovalError,
    _ClaimedExactHumanApproval,
    exact_human_approval_archive_identity_sha256,
)
from .exact_human_approval_workflow import (
    _execute_exact_human_approved_write,
    _resume_exact_human_approved_write_core,
)
from .exact_human_approval_windows import (
    ExactHumanApprovalContext,
    ExactHumanApprovalOperation,
)
from .exact_operation_manifest import (
    ExactFieldEffect,
    ExactOperationApprovalAuthority,
    ExactOperationManifest,
    ExactOperationManifestError,
    ExactOperationItem,
    ExactOperationProgress,
    FileExactOperationCheckpointStore,
    apply_exact_operation,
    exact_operation_execution_sha256,
    exact_operation_writer_lock,
    hash_field_value,
    verify_exact_operation,
)
from .operation_approval_binding import (
    ExactOperationApprovalBinding,
    exact_operation_manifest_approval_binding,
)


PLAN_SCHEMA = "wom-kit/object-storage-bytes-preservation-plan/v0.2"
RESULT_SCHEMA = "wom-kit/object-storage-bytes-preservation-result/v0.2"
VERIFY_SCHEMA = "wom-kit/object-storage-bytes-preservation-verification/v0.2"
LEGACY_RECEIPT_SCHEMA = "wom-kit/object-storage-bytes-preserved-receipt/v0.1"
RECEIPT_SCHEMA = "wom-kit/object-storage-preservation-terminal-receipt/v0.2"
CONTROL_SCHEMA = "wom-kit/object-storage-bytes-preservation-control/v0.2"
REMOTE_QUERY_SCHEMA = "wom-kit/object-storage-remote-query-result/v0.1"
LEDGER_SCHEMA = "wom-kit/object-storage-bytes-preservation-ledger/v0.1"
OPERATION = ExactHumanApprovalOperation.object_storage_bytes_preservation.value

RECEIPT_ROOT = "receipts/providers/object-storage-bytes-preserved"
CONTROL_ROOT = "profiles/local/exact-operations/manifests"
LEDGER_ROOT = "profiles/local/exact-operations/ledgers"
REMOTE_KEY_PREFIX = "wom-bytes-preserved/v1"

_TERMINAL_STATUSES = frozenset(
    {"bytes_preserved", "already_remote_verified", "review_required"}
)

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_BARE_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SAFE_PROVIDER_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_MAX_MANIFEST_ROWS = 200_000
_MAX_MANIFEST_BYTES = 256 * 1024 * 1024
_MAX_MANIFEST_LINE_BYTES = 4 * 1024 * 1024
_MAX_RECEIPT_BYTES = 64 * 1024
_MAX_CONTROL_BYTES = 64 * 1024 * 1024
_MAX_LEDGER_BYTES = 256 * 1024 * 1024
_HASH_CHUNK_BYTES = 1024 * 1024
_REMOTE_HEARTBEAT_POLL_SECONDS = 1.0


class ObjectStoragePreservationError(RuntimeError):
    """Fixed-code failure that never retains a private path or provider body."""

    _CODES = {
        "object_storage_preservation_archive_invalid",
        "object_storage_preservation_manifest_invalid",
        "object_storage_preservation_plan_invalid",
        "object_storage_preservation_plan_changed",
        "object_storage_preservation_no_writes",
        "object_storage_preservation_approval_required",
        "object_storage_preservation_source_drifted",
        "object_storage_preservation_remote_unavailable",
        "object_storage_preservation_remote_conflict",
        "object_storage_preservation_upload_failed",
        "object_storage_preservation_receipt_conflict",
        "object_storage_preservation_control_invalid",
        "object_storage_preservation_resume_invalid",
        "object_storage_preservation_setup_evidence_missing",
        "object_storage_preservation_setup_evidence_mismatch",
    }

    def __init__(self, code: str) -> None:
        self.code = code if code in self._CODES else "object_storage_preservation_plan_invalid"
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"ObjectStoragePreservationError({self.code!r})"


def _fail(code: str) -> ObjectStoragePreservationError:
    return ObjectStoragePreservationError(code)


def _canonical_bytes(value: Any) -> bytes:
    try:
        raw = json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise _fail("object_storage_preservation_plan_invalid") from None
    if len(raw) > _MAX_MANIFEST_BYTES:
        raise _fail("object_storage_preservation_plan_invalid")
    return raw


def _canonical_receipt_bytes(value: Mapping[str, Any]) -> bytes:
    raw = _canonical_bytes(dict(value)) + b"\n"
    if len(raw) > _MAX_RECEIPT_BYTES:
        raise _fail("object_storage_preservation_plan_invalid")
    return raw


def _canonical_control_bytes(value: Mapping[str, Any]) -> bytes:
    raw = _canonical_bytes(dict(value)) + b"\n"
    if len(raw) > _MAX_CONTROL_BYTES:
        raise _fail("object_storage_preservation_control_invalid")
    return raw


def _sha256_document(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _strict_json(raw: bytes) -> dict[str, Any]:
    def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate member")
            result[key] = value
        return result

    parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    if not isinstance(parsed, dict):
        raise ValueError("not an object")
    return parsed


def _normalize_object_id(value: Any) -> str:
    text = str(value or "").strip().lower()
    if _BARE_SHA256_RE.fullmatch(text):
        return "sha256:" + text
    if _SHA256_RE.fullmatch(text):
        return text
    raise _fail("object_storage_preservation_manifest_invalid")


def object_storage_bytes_preserved_remote_key(object_id: str) -> str:
    normalized = _normalize_object_id(object_id)
    digest = normalized.removeprefix("sha256:")
    key = f"{REMOTE_KEY_PREFIX}/sha256/{digest[:2]}/{digest}"
    if not (
        archive_services.safe_object_storage_remote_key(key)
        and archive_services.object_storage_map_key_binds_digest_segment(key, digest)
    ):
        raise _fail("object_storage_preservation_plan_invalid")
    return key


def _path_is_reparse(info: os.stat_result) -> bool:
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(flag and getattr(info, "st_file_attributes", 0) & flag)


def _plain_regular_file(path: Path, *, max_bytes: int | None = None) -> os.stat_result:
    try:
        info = os.lstat(path)
    except OSError:
        raise _fail("object_storage_preservation_source_drifted") from None
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or _path_is_reparse(info)
        or int(getattr(info, "st_nlink", 1)) != 1
        or info.st_size < 0
        or (max_bytes is not None and info.st_size > max_bytes)
    ):
        raise _fail("object_storage_preservation_source_drifted")
    return info


def _hash_plain_file(path: Path, *, heartbeat: Callable[[], None]) -> tuple[str, int]:
    before = _plain_regular_file(path)
    digest = hashlib.sha256()
    total = 0
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if (
            opened.st_size != before.st_size
            or (before.st_ino and opened.st_ino and before.st_ino != opened.st_ino)
            or (before.st_dev and opened.st_dev and before.st_dev != opened.st_dev)
        ):
            raise OSError("changed")
        while True:
            heartbeat()
            chunk = os.read(descriptor, _HASH_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if total > opened.st_size:
                raise OSError("grew")
            digest.update(chunk)
        after = os.fstat(descriptor)
    except OSError:
        raise _fail("object_storage_preservation_source_drifted") from None
    finally:
        try:
            os.close(descriptor)
        except (OSError, UnboundLocalError):
            pass
    named_after = _plain_regular_file(path)
    if (
        total != before.st_size
        or after.st_size != before.st_size
        or named_after.st_size != before.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or after.st_mtime_ns != named_after.st_mtime_ns
        or (after.st_ino and named_after.st_ino and after.st_ino != named_after.st_ino)
    ):
        raise _fail("object_storage_preservation_source_drifted")
    return digest.hexdigest(), total


def _call_with_heartbeat(
    call: Callable[[], Any],
    *,
    heartbeat: Callable[[], None],
) -> Any:
    """Run one blocking provider call while the exact core remains observable.

    The worker is deliberately non-daemon. If the foreground is interrupted,
    it waits for the in-flight provider call before propagating the interrupt;
    an upload is never abandoned as an untracked background mutation.
    """

    completed = threading.Event()
    outcome: dict[str, Any] = {}

    def run() -> None:
        try:
            outcome["value"] = call()
        except Exception as exc:  # caller converts this to a fixed public state
            outcome["error"] = exc
        finally:
            completed.set()

    worker = threading.Thread(
        target=run,
        name="wom-object-storage-provider-call",
        daemon=False,
    )
    heartbeat()
    worker.start()
    interrupted: BaseException | None = None
    try:
        while not completed.wait(_REMOTE_HEARTBEAT_POLL_SECONDS):
            heartbeat()
    except BaseException as exc:
        interrupted = exc
        while not completed.wait(_REMOTE_HEARTBEAT_POLL_SECONDS):
            pass
    finally:
        worker.join()
        heartbeat()
    if interrupted is not None:
        raise interrupted
    error = outcome.get("error")
    if isinstance(error, Exception):
        raise error
    return outcome.get("value")


def _read_manifest_groups(
    root: Path,
    *,
    progress: Callable[[str, str, int | None, int | None], None] | None,
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    path = archive_services.archive_internal_path(root, "objects/manifests/files.jsonl")
    info = _plain_regular_file(path, max_bytes=_MAX_MANIFEST_BYTES)
    rows: list[dict[str, Any]] = []
    groups: dict[str, list[dict[str, Any]]] = {}
    read_bytes = 0
    if progress is not None:
        progress("preservation-inventory", "start", 0, None)
    try:
        with path.open("rb") as handle:
            for line_number, raw in enumerate(handle, start=1):
                read_bytes += len(raw)
                if (
                    line_number > _MAX_MANIFEST_ROWS
                    or len(raw) > _MAX_MANIFEST_LINE_BYTES
                    or read_bytes > _MAX_MANIFEST_BYTES
                ):
                    raise _fail("object_storage_preservation_manifest_invalid")
                if not raw.strip():
                    continue
                try:
                    row = _strict_json(raw)
                    object_id = _normalize_object_id(row.get("object_id"))
                    digest = _normalize_object_id(row.get("sha256"))
                except (ValueError, UnicodeError, ObjectStoragePreservationError):
                    raise _fail("object_storage_preservation_manifest_invalid") from None
                if object_id != digest:
                    raise _fail("object_storage_preservation_manifest_invalid")
                if (
                    type(row.get("size_bytes")) is not int
                    or row["size_bytes"] < 0
                    or not isinstance(row.get("locations"), list)
                ):
                    raise _fail("object_storage_preservation_manifest_invalid")
                row["object_id"] = object_id
                rows.append(row)
                groups.setdefault(object_id, []).append(row)
                if progress is not None and (line_number == 1 or line_number % 1000 == 0):
                    progress("preservation-inventory", "scanned manifest rows", line_number, None)
    except ObjectStoragePreservationError:
        raise
    except (OSError, ValueError):
        raise _fail("object_storage_preservation_manifest_invalid") from None
    after = _plain_regular_file(path, max_bytes=_MAX_MANIFEST_BYTES)
    if after.st_size != info.st_size or after.st_mtime_ns != info.st_mtime_ns:
        raise _fail("object_storage_preservation_manifest_invalid")
    if not rows:
        raise _fail("object_storage_preservation_manifest_invalid")
    if progress is not None:
        progress("preservation-inventory", "done", len(rows), len(rows))
    return rows, groups


def _locations(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(value) for value in row.get("locations", []) if isinstance(value, Mapping)]


def _has_local(row: Mapping[str, Any]) -> bool:
    return any(
        location.get("provider") == "local"
        and location.get("availability") == "available"
        and type(location.get("path")) is str
        and bool(location.get("path"))
        for location in _locations(row)
    )


def _local_paths(row: Mapping[str, Any]) -> list[str]:
    return sorted(
        {
            str(location["path"])
            for location in _locations(row)
            if location.get("provider") == "local"
            and location.get("availability") == "available"
            and type(location.get("path")) is str
            and bool(location.get("path"))
        }
    )


def _has_object_storage_record(row: Mapping[str, Any]) -> bool:
    return any(location.get("provider") == "object_storage" for location in _locations(row))


def _declared_remote(row: Mapping[str, Any]) -> bool:
    return any(
        location.get("provider") == "object_storage"
        and location.get("availability") == "declared_uploaded"
        for location in _locations(row)
    )


def _verified_remote(row: Mapping[str, Any]) -> bool:
    for location in _locations(row):
        if (
            location.get("provider") == "object_storage"
            and location.get("availability") == "wom_uploaded"
            and location.get("byte_verification_by_wom_kit") is True
            and location.get("provider_confirmation_by_wom_kit") is True
            and location.get("remote_key_verified") is True
            and type(location.get("remote_key")) is str
            and archive_services.safe_object_storage_remote_key(location["remote_key"])
            and type(location.get("execution_receipt_ref")) is str
            and bool(location.get("execution_receipt_ref"))
        ):
            return True
    return False


def _official_wom_uploaded_evidence(row: Mapping[str, Any]) -> bool:
    """Return de-duplicated WOM upload evidence, including two legacy key gaps.

    A small legacy set has a WOM byte-verification/provider-confirmation receipt
    but no manifest remote_key.  It is real prior remote evidence and therefore
    must not be emergency re-uploaded under a new key.  It is deliberately not
    called independently key-verified; the separate strict metric below still
    requires a safe remote_key and remote_key_verified=true.
    """

    return any(
        location.get("provider") == "object_storage"
        and location.get("availability") == "wom_uploaded"
        and location.get("byte_verification_by_wom_kit") is True
        and location.get("provider_confirmation_by_wom_kit") is True
        and type(location.get("execution_receipt_ref")) is str
        and bool(location.get("execution_receipt_ref"))
        for location in _locations(row)
    )


def _conflict_projection(object_id: str, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    sizes = {row.get("size_bytes") for row in rows}
    logical_keys = {row.get("logical_key") for row in rows}
    mimes = {row.get("mime") for row in rows}
    has_local = any(_has_local(row) for row in rows)
    has_declared = any(_declared_remote(row) for row in rows)
    has_verified = any(_verified_remote(row) for row in rows)
    has_remote_key = any(
        type(location.get("remote_key")) is str
        for row in rows
        for location in _locations(row)
        if location.get("provider") == "object_storage"
    )
    has_receipt = any(
        type(location.get("execution_receipt_ref")) is str
        for row in rows
        for location in _locations(row)
        if location.get("provider") == "object_storage"
    )
    reasons = ["same_object_id_byte_identity"]
    reasons.append("same_size" if len(sizes) == 1 else "size_conflict")
    reasons.append("same_logical_key" if len(logical_keys) == 1 else "logical_key_conflict")
    reasons.append("same_mime" if len(mimes) == 1 else "mime_conflict")
    if has_local and (has_declared or has_verified):
        reasons.append("remote_local_complementary_evidence")
    if has_remote_key:
        reasons.append("existing_remote_key_evidence")
    if has_receipt:
        reasons.append("existing_execution_receipt_evidence")
    return {
        "object_id_sha256": _sha256_document(object_id),
        "row_count": len(rows),
        "reason_codes": sorted(reasons),
        "same_byte_identity": True,
        "same_size": len(sizes) == 1,
        "remote_local_complementary": has_local and (has_declared or has_verified),
        "has_existing_remote_key": has_remote_key,
        "has_execution_receipt": has_receipt,
        "automatic_merge_allowed": False,
    }


def _inventory(
    rows: Sequence[dict[str, Any]],
    groups: Mapping[str, Sequence[dict[str, Any]]],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    conflicts: dict[str, dict[str, Any]] = {}
    conflict_reason_counts: dict[str, int] = {}
    manifest_scope_remote_key_verified = 0
    official_deduplicated_wom_uploaded_evidence = 0
    declared_object_count = 0
    official_declared_object_count = 0
    unique_local_without_remote_record = 0
    nonconflicting_remote_declared_pending = 0
    nonconflicting_remote_recorded_other = 0
    local_location_count = sum(
        1
        for row in rows
        for location in _locations(row)
        if location.get("provider") == "local"
        and location.get("availability") == "available"
    )
    group_projection: list[dict[str, Any]] = []
    unique_rows: dict[str, dict[str, Any]] = {}
    for object_id in sorted(groups):
        group = list(groups[object_id])
        verified = any(_verified_remote(row) for row in group)
        official_evidence = any(
            _official_wom_uploaded_evidence(row) for row in group
        )
        declared = any(_declared_remote(row) for row in group)
        if verified:
            manifest_scope_remote_key_verified += 1
        if declared:
            declared_object_count += 1
        if len(group) > 1:
            projection = _conflict_projection(object_id, group)
            conflicts[object_id] = projection
            for reason in projection["reason_codes"]:
                conflict_reason_counts[reason] = conflict_reason_counts.get(reason, 0) + 1
            group_projection.append(
                {
                    "object_id_sha256": projection["object_id_sha256"],
                    "classification": "conflicting_definition",
                    "row_count": len(group),
                    "reason_codes": projection["reason_codes"],
                }
            )
            continue
        row = group[0]
        unique_rows[object_id] = row
        has_remote = _has_object_storage_record(row)
        if official_evidence:
            official_deduplicated_wom_uploaded_evidence += 1
        if declared:
            official_declared_object_count += 1
        if _has_local(row) and not has_remote:
            unique_local_without_remote_record += 1
        if has_remote and not official_evidence:
            if declared:
                nonconflicting_remote_declared_pending += 1
            else:
                nonconflicting_remote_recorded_other += 1
        group_projection.append(
            {
                "object_id_sha256": _sha256_document(object_id),
                "classification": (
                    "remote_key_verified"
                    if verified
                    else (
                        "remote_official_evidence_missing_key"
                        if official_evidence
                        else (
                            "remote_declared_pending_adoption"
                            if declared
                            else (
                                "remote_recorded_other"
                                if has_remote
                                else (
                                    "local_without_remote_record"
                                    if _has_local(row)
                                    else "review"
                                )
                            )
                        )
                    )
                ),
                "size_bytes": row.get("size_bytes"),
                "logical_key_sha256": _sha256_document(row.get("logical_key")),
                "local_path_set_sha256": _sha256_document(_local_paths(row)),
            }
        )
    basis = {
        "schema_version": "wom-kit/object-storage-source-inventory/v0.1",
        "manifest_row_count": len(rows),
        "unique_object_count": len(groups),
        "conflicting_definition_count": len(conflicts),
        "local_location_count": local_location_count,
        "unique_local_without_remote_record_count": unique_local_without_remote_record,
        "manifest_scope_remote_key_verified_object_count": manifest_scope_remote_key_verified,
        "official_deduplicated_wom_uploaded_evidence_object_count": (
            official_deduplicated_wom_uploaded_evidence
        ),
        "declared_object_count": declared_object_count,
        "official_deduplicated_declared_object_count": official_declared_object_count,
        "nonconflicting_remote_declared_pending_adoption_count": (
            nonconflicting_remote_declared_pending
        ),
        "nonconflicting_remote_recorded_other_count": nonconflicting_remote_recorded_other,
        "conflict_reason_counts": dict(sorted(conflict_reason_counts.items())),
        "group_projection_sha256": _sha256_document(group_projection),
    }
    return {
        **basis,
        "source_inventory_sha256": _sha256_document(basis),
    }, unique_rows


def _safe_local_path(root: Path, relative: str) -> Path:
    if type(relative) is not str or not relative:
        raise _fail("object_storage_preservation_plan_invalid")
    try:
        path = archive_services.archive_internal_path(root, relative)
    except Exception:
        raise _fail("object_storage_preservation_plan_invalid") from None
    _plain_regular_file(path)
    return path


def _receipt_relative(object_id: str, inventory_sha256: str) -> str:
    digest = object_id.removeprefix("sha256:")
    inventory = inventory_sha256.removeprefix("sha256:")
    return f"{RECEIPT_ROOT}/{digest}.{inventory[:16]}.json"


def _legacy_receipt_document(
    *,
    object_id: str,
    size_bytes: int,
    provider_kind: str,
    store_ref: str,
    inventory_sha256: str,
) -> dict[str, Any]:
    """Rebuild the immutable v0.1 receipt exactly as the prior release did."""

    return {
        "schema_version": LEGACY_RECEIPT_SCHEMA,
        "object_id": object_id,
        "content_sha256": object_id,
        "size_bytes": size_bytes,
        "provider_kind": provider_kind,
        "store_ref": store_ref,
        "remote_key_strategy": "wom_bytes_preserved_v1",
        "remote_key_sha256": _sha256_document(
            object_storage_bytes_preserved_remote_key(object_id)
        ),
        "source_inventory_sha256": inventory_sha256,
        "preservation_status": "bytes_preserved",
        "formal_adoption_status": "not_adopted",
        "manifest_location_updated": False,
        "remote_verification": {
            "head_present": True,
            "size_match": True,
            "whole_object_sha256_match": True,
            "verification_kind": "head_then_get_rehash",
        },
        "remote_delete_on_revert_supported": False,
        "private_values_echoed": False,
        "credential_values_echoed": False,
        "provider_url_echoed": False,
        "local_path_echoed": False,
    }


def _receipt_document(
    *,
    manifest_sha256: str,
    receipt_token: bytes,
    object_id: str,
    size_bytes: int,
    provider_kind: str,
    store_ref: str,
    inventory_sha256: str,
    preservation_status: str,
    classified_at: str,
    provider_put_call_count: int,
    remote_state: str,
) -> dict[str, Any]:
    if preservation_status not in _TERMINAL_STATUSES:
        raise _fail("object_storage_preservation_receipt_conflict")
    if remote_state not in {"verified_match", "size_mismatch", "checksum_mismatch"}:
        raise _fail("object_storage_preservation_receipt_conflict")
    remote_match = remote_state == "verified_match"
    size_match = remote_state != "size_mismatch"
    remote_key = object_storage_bytes_preserved_remote_key(object_id)
    return {
        "schema_version": RECEIPT_SCHEMA,
        "object_id": object_id,
        "content_sha256": object_id,
        "size_bytes": size_bytes,
        "provider_kind": provider_kind,
        "store_ref": store_ref,
        "remote_key_strategy": "wom_bytes_preserved_v1",
        "remote_key_sha256": _sha256_document(remote_key),
        "source_inventory_sha256": inventory_sha256,
        "exact_operation_manifest_sha256": manifest_sha256,
        "receipt_state_sha256": _sha256_bytes(receipt_token),
        "preservation_status": preservation_status,
        "classified_at": classified_at,
        "provider_put_call_count": provider_put_call_count,
        "bytes_uploaded": size_bytes if preservation_status == "bytes_preserved" else 0,
        "formal_adoption_status": "not_adopted",
        "manifest_location_updated": False,
        "remote_verification": {
            "head_present": True,
            "size_match": size_match,
            "whole_object_sha256_match": remote_match,
            "verification_kind": (
                "head_then_get_rehash" if size_match else "head_size_mismatch"
            ),
        },
        "review_reason": (
            None
            if preservation_status != "review_required"
            else (
                "remote_size_mismatch"
                if remote_state == "size_mismatch"
                else "remote_checksum_mismatch"
            )
        ),
        "remote_delete_on_revert_supported": False,
        "private_values_echoed": False,
        "credential_values_echoed": False,
        "provider_url_echoed": False,
        "local_path_echoed": False,
    }


def _existing_receipt_matches(
    document: Mapping[str, Any],
    *,
    receipt_token: bytes,
    object_id: str,
    size_bytes: int,
    provider_kind: str,
    store_ref: str,
    inventory_sha256: str,
) -> bool:
    """Conservatively validate immutable v0.1 or current v0.2 evidence."""

    if document.get("schema_version") == LEGACY_RECEIPT_SCHEMA:
        return dict(document) == _legacy_receipt_document(
            object_id=object_id,
            size_bytes=size_bytes,
            provider_kind=provider_kind,
            store_ref=store_ref,
            inventory_sha256=inventory_sha256,
        )
    if document.get("schema_version") != RECEIPT_SCHEMA:
        return False
    required = {
        "schema_version",
        "object_id",
        "content_sha256",
        "size_bytes",
        "provider_kind",
        "store_ref",
        "remote_key_strategy",
        "remote_key_sha256",
        "source_inventory_sha256",
        "exact_operation_manifest_sha256",
        "receipt_state_sha256",
        "preservation_status",
        "classified_at",
        "provider_put_call_count",
        "bytes_uploaded",
        "formal_adoption_status",
        "manifest_location_updated",
        "remote_verification",
        "review_reason",
        "remote_delete_on_revert_supported",
        "private_values_echoed",
        "credential_values_echoed",
        "provider_url_echoed",
        "local_path_echoed",
    }
    if set(document) != required:
        return False
    status = document.get("preservation_status")
    put_calls = document.get("provider_put_call_count")
    classified_at = document.get("classified_at")
    if (
        status not in _TERMINAL_STATUSES
        or type(put_calls) is not int
        or put_calls < 0
        or type(classified_at) is not str
        or not classified_at
        or _SHA256_RE.fullmatch(str(document.get("exact_operation_manifest_sha256") or ""))
        is None
        or document.get("receipt_state_sha256") != _sha256_bytes(receipt_token)
    ):
        return False
    try:
        datetime.fromisoformat(classified_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if not (
        document.get("object_id") == object_id
        and document.get("content_sha256") == object_id
        and document.get("size_bytes") == size_bytes
        and document.get("provider_kind") == provider_kind
        and document.get("store_ref") == store_ref
        and document.get("remote_key_strategy") == "wom_bytes_preserved_v1"
        and document.get("remote_key_sha256")
        == _sha256_document(object_storage_bytes_preserved_remote_key(object_id))
        and document.get("source_inventory_sha256") == inventory_sha256
        and document.get("bytes_uploaded")
        == (size_bytes if status == "bytes_preserved" else 0)
        and document.get("formal_adoption_status") == "not_adopted"
        and document.get("manifest_location_updated") is False
        and document.get("remote_delete_on_revert_supported") is False
        and document.get("private_values_echoed") is False
        and document.get("credential_values_echoed") is False
        and document.get("provider_url_echoed") is False
        and document.get("local_path_echoed") is False
    ):
        return False
    remote = document.get("remote_verification")
    if type(remote) is not dict or set(remote) != {
        "head_present",
        "size_match",
        "whole_object_sha256_match",
        "verification_kind",
    }:
        return False
    if status in {"bytes_preserved", "already_remote_verified"}:
        return remote == {
            "head_present": True,
            "size_match": True,
            "whole_object_sha256_match": True,
            "verification_kind": "head_then_get_rehash",
        } and document.get("review_reason") is None
    if document.get("review_reason") == "remote_size_mismatch":
        return remote == {
            "head_present": True,
            "size_match": False,
            "whole_object_sha256_match": False,
            "verification_kind": "head_size_mismatch",
        }
    if document.get("review_reason") == "remote_checksum_mismatch":
        return remote == {
            "head_present": True,
            "size_match": True,
            "whole_object_sha256_match": False,
            "verification_kind": "head_then_get_rehash",
        }
    return False


def _receipt_token(
    *,
    object_id: str,
    size_bytes: int,
    provider_kind: str,
    store_ref: str,
    inventory_sha256: str,
) -> bytes:
    remote_key = object_storage_bytes_preserved_remote_key(object_id)
    return _canonical_bytes(
        {
            "schema_version": "wom-kit/object-storage-preservation-terminal-state/v0.1",
            "object_id": object_id,
            "size_bytes": size_bytes,
            "provider_kind": provider_kind,
            "store_ref": store_ref,
            "remote_key_sha256": _sha256_document(remote_key),
            "source_inventory_sha256": inventory_sha256,
            "terminal_statuses": sorted(_TERMINAL_STATUSES),
        }
    )


@dataclass(frozen=True, repr=False)
class _PreservationSpec:
    object_id: str
    size_bytes: int
    local_relative: str
    local_path: Path
    remote_key: str
    receipt_relative: str
    receipt_token: bytes
    source_token: bytes
    target_identity_sha256: str


def _single_attempt_provider_put_calls(size_bytes: int) -> int:
    if size_bytes < archive_services.OBJECT_STORAGE_MULTIPART_THRESHOLD_BYTES:
        return 1
    part_size = archive_services.OBJECT_STORAGE_MULTIPART_PART_SIZE_BYTES
    part_count = max(1, (size_bytes + part_size - 1) // part_size)
    return part_count + 2  # create multipart + parts + complete multipart


def _provider_put_call_budget(
    specs: Sequence[_PreservationSpec],
) -> tuple[int, int]:
    no_retry = sum(_single_attempt_provider_put_calls(spec.size_bytes) for spec in specs)
    ceiling = no_retry * archive_services.OBJECT_STORAGE_MAX_ATTEMPTS_PER_OBJECT
    return no_retry, ceiling


def _target_identity(
    *,
    archive_id: str,
    object_id: str,
    receipt_relative: str,
    provider_kind: str,
    store_ref: str,
) -> str:
    return _sha256_document(
        {
            "schema_version": "wom-kit/object-storage-preservation-terminal-target/v0.1",
            "archive_id": archive_id,
            "object_id": object_id,
            "receipt_relative": receipt_relative,
            "provider_kind": provider_kind,
            "store_ref": store_ref,
        }
    )


@dataclass(frozen=True, repr=False)
class ObjectStorageBytesPreservationPlan:
    archive_root: Path
    archive_id: str
    provider_kind: str
    store_ref: str
    source_inventory_sha256: str
    inventory: dict[str, Any]
    manifest: ExactOperationManifest | None
    specs: tuple[_PreservationSpec, ...]
    already_recorded_count: int
    review_count: int
    selected_only: str | None
    loaded_from_control: bool = False

    @property
    def approveable(self) -> bool:
        return self.manifest is not None and bool(self.specs) and self.review_count == 0

    def public_document(self) -> dict[str, Any]:
        conflict_count = int(self.inventory["conflicting_definition_count"])
        unique_count = int(self.inventory["unique_object_count"])
        verified_official = int(
            self.inventory["official_deduplicated_wom_uploaded_evidence_object_count"]
        )
        pending_adopt = int(
            self.inventory["nonconflicting_remote_declared_pending_adoption_count"]
        )
        other_remote = int(self.inventory["nonconflicting_remote_recorded_other_count"])
        planned = len(self.specs)
        expected_put_calls, put_call_ceiling = _provider_put_call_budget(self.specs)
        accounted = (
            conflict_count
            + verified_official
            + pending_adopt
            + other_remote
            + int(self.inventory["unique_local_without_remote_record_count"])
        )
        return {
            "schema_version": PLAN_SCHEMA,
            "ok": self.approveable,
            "state": (
                "ready_for_exact_human_approval"
                if self.approveable
                else (
                    "no_new_bytes_to_preserve"
                    if planned == 0 and self.review_count == 0
                    else "review_required"
                )
            ),
            "reason_codes": (
                ["object_storage_bytes_preservation_ready"]
                if self.approveable
                else (
                    ["object_storage_bytes_preservation_no_writes"]
                    if self.review_count == 0
                    else ["object_storage_bytes_preservation_review_required"]
                )
            ),
            "plan_sha256": self.manifest.manifest_sha256 if self.manifest else None,
            "target_binding_sha256": self.manifest.target_set_sha256 if self.manifest else None,
            "source_binding_sha256": self.manifest.source_set_sha256 if self.manifest else None,
            "effect_binding_sha256": self.manifest.effect_set_sha256 if self.manifest else None,
            "source_inventory_sha256": self.source_inventory_sha256,
            "manifest_row_count": int(self.inventory["manifest_row_count"]),
            "unique_object_count": unique_count,
            "classification_accounted_object_count": accounted,
            "classification_sum_matches_unique_objects": accounted == unique_count,
            "local_location_count": int(self.inventory["local_location_count"]),
            "local_unique_without_remote_record_count": int(
                self.inventory["unique_local_without_remote_record_count"]
            ),
            "preservation_planned_count": planned,
            "expected_no_retry_provider_put_call_count": expected_put_calls,
            "manifest_bound_provider_put_call_ceiling": put_call_ceiling,
            "bytes_preserved_receipt_already_recorded_count": self.already_recorded_count,
            "review_count": self.review_count,
            "remote_evidence_metrics": {
                "manifest_scope_remote_key_verified_object_count": int(
                    self.inventory["manifest_scope_remote_key_verified_object_count"]
                ),
                "official_deduplicated_wom_uploaded_evidence_object_count": verified_official,
                "declared_object_count": int(self.inventory["declared_object_count"]),
                "official_deduplicated_declared_object_count": int(
                    self.inventory["official_deduplicated_declared_object_count"]
                ),
                "nonconflicting_remote_declared_pending_adoption_count": pending_adopt,
            },
            "conflict_classification": {
                "status": "review_required",
                "conflicting_definition_count": conflict_count,
                "reason_counts": dict(self.inventory["conflict_reason_counts"]),
                "automatic_merge_count": 0,
            },
            "bytes_preserved_is_formal_adoption": False,
            "formal_adoption_manifest_updates_planned": 0,
            "remote_delete_on_revert_supported": False,
            "requires_exact_human_approval": True,
            "common_exact_operation_manifest_used": self.manifest is not None,
            "provider_api_called": False,
            "credential_values_read": False,
            "object_bytes_hashed": True,
            "writes_performed": False,
            "private_values_echoed": False,
            "local_paths_echoed": False,
            "remote_keys_echoed": False,
            "object_ids_echoed": False,
        }


def _build_specs(
    root: Path,
    archive_id: str,
    provider_kind: str,
    store_ref: str,
    inventory: Mapping[str, Any],
    unique_rows: Mapping[str, dict[str, Any]],
    *,
    only: str | None,
    max_objects: int | None,
    progress: Callable[[str, str, int | None, int | None], None] | None,
) -> tuple[tuple[_PreservationSpec, ...], int, int]:
    inventory_sha = str(inventory["source_inventory_sha256"])
    selected_id = _normalize_object_id(only) if only else None
    candidates: list[tuple[str, dict[str, Any], str]] = []
    review_count = 0
    for object_id, row in sorted(unique_rows.items()):
        if selected_id is not None and object_id != selected_id:
            continue
        if not _has_local(row) or _has_object_storage_record(row):
            continue
        paths = _local_paths(row)
        if len(paths) != 1:
            review_count += 1
            continue
        candidates.append((object_id, row, paths[0]))
    if selected_id is not None and not candidates:
        raise _fail("object_storage_preservation_no_writes")
    if max_objects is not None:
        if type(max_objects) is not int or max_objects < 1:
            raise _fail("object_storage_preservation_plan_invalid")
        if len(candidates) > max_objects:
            raise _fail("object_storage_preservation_plan_invalid")
    specs: list[_PreservationSpec] = []
    already_recorded = 0
    if progress is not None:
        progress("preservation-source-hash", "start", 0, len(candidates))
    for index, (object_id, row, local_relative) in enumerate(candidates, start=1):
        local_path = _safe_local_path(root, local_relative)
        digest, size = _hash_plain_file(
            local_path,
            heartbeat=(
                (lambda i=index: progress("preservation-source-hash", "heartbeat", i - 1, len(candidates)))
                if progress is not None
                else (lambda: None)
            ),
        )
        expected_digest = object_id.removeprefix("sha256:")
        if digest != expected_digest or size != row["size_bytes"]:
            review_count += 1
            continue
        receipt_relative = _receipt_relative(object_id, inventory_sha)
        receipt_token = _receipt_token(
            object_id=object_id,
            size_bytes=size,
            provider_kind=provider_kind,
            store_ref=store_ref,
            inventory_sha256=inventory_sha,
        )
        receipt_path = archive_services.archive_internal_path(root, receipt_relative)
        if receipt_path.exists():
            try:
                existing = _strict_json(receipt_path.read_bytes())
            except Exception:
                review_count += 1
                continue
            if _existing_receipt_matches(
                existing,
                receipt_token=receipt_token,
                object_id=object_id,
                size_bytes=size,
                provider_kind=provider_kind,
                store_ref=store_ref,
                inventory_sha256=inventory_sha,
            ):
                already_recorded += 1
                continue
            review_count += 1
            continue
        source_token = _canonical_bytes(
            {
                "schema_version": "wom-kit/object-storage-bytes-preservation-source/v0.1",
                "object_id": object_id,
                "size_bytes": size,
                "local_relative_sha256": _sha256_document(local_relative),
                "source_inventory_sha256": inventory_sha,
            }
        )
        specs.append(
            _PreservationSpec(
                object_id=object_id,
                size_bytes=size,
                local_relative=local_relative,
                local_path=local_path,
                remote_key=object_storage_bytes_preserved_remote_key(object_id),
                receipt_relative=receipt_relative,
                receipt_token=receipt_token,
                source_token=source_token,
                target_identity_sha256=_target_identity(
                    archive_id=archive_id,
                    object_id=object_id,
                    receipt_relative=receipt_relative,
                    provider_kind=provider_kind,
                    store_ref=store_ref,
                ),
            )
        )
        if progress is not None and (index == 1 or index == len(candidates) or index % 100 == 0):
            progress("preservation-source-hash", "hashed local objects", index, len(candidates))
    if progress is not None:
        progress("preservation-source-hash", "done", len(candidates), len(candidates))
    return tuple(specs), already_recorded, review_count


def _manifest_for_specs(
    *,
    archive_id: str,
    specs: Sequence[_PreservationSpec],
) -> ExactOperationManifest | None:
    items: list[ExactOperationItem] = []
    for ordinal, spec in enumerate(specs):
        item_id = "item:" + hashlib.sha256(
            (spec.object_id + "\x00" + spec.receipt_relative).encode("ascii")
        ).hexdigest()
        items.append(
            ExactOperationItem(
                ordinal=ordinal,
                item_id=item_id,
                target_kind="object_storage_preservation_terminal_receipt",
                target_ref=spec.receipt_relative,
                target_identity_sha256=spec.target_identity_sha256,
                fields=(
                    ExactFieldEffect(
                        field_ref="terminal_state_token",
                        pre_sha256=hash_field_value(None),
                        post_sha256=hash_field_value(spec.receipt_token),
                        source_sha256=hash_field_value(spec.source_token),
                    ),
                ),
            )
        )
    if not items:
        return None
    return ExactOperationManifest.build(
        operation=OPERATION,
        archive_identity_sha256=(
            exact_human_approval_archive_identity_sha256(archive_id)
        ),
        items=items,
    )


def _require_setup_evidence(
    root: Path,
    *,
    provider_kind: str,
    store_ref: str,
) -> object_storage_setup_registration.ObjectStorageSetupEvidence:
    """Require current archive-scoped setup evidence before provider work."""

    try:
        return object_storage_setup_registration.validate_object_storage_setup_evidence(
            root,
            provider_kind=provider_kind,
            store_ref=store_ref,
        )
    except object_storage_setup_registration.ObjectStorageSetupRegistrationError as exc:
        code = (
            "object_storage_preservation_setup_evidence_missing"
            if exc.code == "object_storage_setup_evidence_missing"
            else "object_storage_preservation_setup_evidence_mismatch"
        )
        raise _fail(code) from None


def _plan_core(
    archive_root: Path | str,
    *,
    provider_kind: str,
    store_ref: str,
    only: str | None = None,
    max_objects: int | None = None,
    progress: Callable[[str, str, int | None, int | None], None] | None = None,
) -> ObjectStorageBytesPreservationPlan:
    try:
        root = archive_services.require_existing_archive_root(archive_root)
        archive_id = archive_services.read_archive_id(root)
    except Exception:
        raise _fail("object_storage_preservation_archive_invalid") from None
    normalized_provider = str(provider_kind or "").strip().lower()
    normalized_store = str(store_ref or "").strip()
    if (
        _SAFE_PROVIDER_RE.fullmatch(normalized_provider) is None
        or normalized_provider not in archive_services.OBJECT_STORAGE_ALLOWED_PROVIDERS
        or not archive_services.safe_object_storage_ref(normalized_store)
    ):
        raise _fail("object_storage_preservation_plan_invalid")
    _require_setup_evidence(
        root,
        provider_kind=normalized_provider,
        store_ref=normalized_store,
    )
    rows, groups = _read_manifest_groups(root, progress=progress)
    inventory, unique_rows = _inventory(rows, groups)
    specs, already_recorded, review_count = _build_specs(
        root,
        archive_id,
        normalized_provider,
        normalized_store,
        inventory,
        unique_rows,
        only=only,
        max_objects=max_objects,
        progress=progress,
    )
    manifest = _manifest_for_specs(archive_id=archive_id, specs=specs)
    return ObjectStorageBytesPreservationPlan(
        archive_root=root,
        archive_id=archive_id,
        provider_kind=normalized_provider,
        store_ref=normalized_store,
        source_inventory_sha256=str(inventory["source_inventory_sha256"]),
        inventory=dict(inventory),
        manifest=manifest,
        specs=specs,
        already_recorded_count=already_recorded,
        review_count=review_count,
        selected_only=_normalize_object_id(only) if only else None,
    )


def plan_object_storage_bytes_preservation(
    archive_root: Path | str,
    *,
    provider_kind: str = "cloudflare-r2",
    store_ref: str,
    only: str | None = None,
    max_objects: int | None = None,
    progress: Callable[[str, str, int | None, int | None], None] | None = None,
) -> dict[str, Any]:
    return _plan_core(
        archive_root,
        provider_kind=provider_kind,
        store_ref=store_ref,
        only=only,
        max_objects=max_objects,
        progress=progress,
    ).public_document()


@dataclass(frozen=True)
class ObjectStorageRemoteQueryResult:
    state: str
    present: bool
    size_match: bool
    checksum_match: bool

    def public_document(self) -> dict[str, Any]:
        return {
            "schema_version": REMOTE_QUERY_SCHEMA,
            "state": self.state,
            "present": self.present,
            "size_match": self.size_match,
            "whole_object_sha256_match": self.checksum_match,
            "remote_key_echoed": False,
            "provider_body_echoed": False,
            "provider_url_echoed": False,
            "credential_values_echoed": False,
        }


class ObjectStorageRemoteQueryAdapter:
    """Normalize provider HEAD+GET evidence to fixed, non-secret states."""

    def __init__(self, transport: archive_services.ObjectStorageTransport) -> None:
        self.transport = transport

    def query(
        self,
        *,
        remote_key: str,
        expected_size: int,
        expected_sha256: str,
        heartbeat: Callable[[], None],
    ) -> ObjectStorageRemoteQueryResult:
        if (
            not archive_services.safe_object_storage_remote_key(remote_key)
            or type(expected_size) is not int
            or expected_size < 0
            or _BARE_SHA256_RE.fullmatch(expected_sha256) is None
        ):
            raise _fail("object_storage_preservation_plan_invalid")
        try:
            result = _call_with_heartbeat(
                lambda: self.transport.head_object(
                    key=remote_key,
                    presence_only=False,
                ),
                heartbeat=heartbeat,
            )
        except Exception:
            return ObjectStorageRemoteQueryResult("verification_unavailable", False, False, False)
        if not isinstance(result, Mapping):
            return ObjectStorageRemoteQueryResult("verification_unavailable", False, False, False)
        presence_state = result.get("presence_state")
        if presence_state == "absent" and result.get("present") is False:
            return ObjectStorageRemoteQueryResult("absent", False, False, False)
        if presence_state != "present" or result.get("present") is not True:
            return ObjectStorageRemoteQueryResult("verification_unavailable", False, False, False)
        remote_size = result.get("size")
        size_match = type(remote_size) is int and remote_size == expected_size
        if not size_match:
            return ObjectStorageRemoteQueryResult("size_mismatch", True, False, False)
        checksum = result.get("checksum_sha256")
        if (
            result.get("verification_state") not in {None, "complete"}
            or type(checksum) is not str
            or _BARE_SHA256_RE.fullmatch(checksum) is None
        ):
            return ObjectStorageRemoteQueryResult("verification_unavailable", True, True, False)
        if not hmac.compare_digest(checksum, expected_sha256):
            return ObjectStorageRemoteQueryResult("checksum_mismatch", True, True, False)
        return ObjectStorageRemoteQueryResult("verified_match", True, True, True)


def _read_exact_receipt(
    path: Path,
    expected: bytes,
    *,
    max_bytes: int = _MAX_RECEIPT_BYTES,
    failure_code: str = "object_storage_preservation_receipt_conflict",
) -> bytes | None:
    if not path.exists():
        return None
    try:
        info = _plain_regular_file(path, max_bytes=max_bytes)
        raw = path.read_bytes()
        after = _plain_regular_file(path, max_bytes=max_bytes)
    except (OSError, ObjectStoragePreservationError):
        raise _fail(failure_code) from None
    if (
        len(raw) != info.st_size
        or after.st_size != info.st_size
        or after.st_mtime_ns != info.st_mtime_ns
        or raw != expected
    ):
        raise _fail(failure_code)
    return raw


def _create_or_match_receipt(
    root: Path,
    relative: str,
    raw: bytes,
    *,
    max_bytes: int = _MAX_RECEIPT_BYTES,
    failure_code: str = "object_storage_preservation_receipt_conflict",
) -> None:
    if len(raw) > max_bytes:
        raise _fail(failure_code)
    path = archive_services.archive_internal_path(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        parent = path.parent.resolve(strict=True)
        if not parent.is_relative_to(root):
            raise OSError("outside")
        parent_info = os.lstat(parent)
        if not stat.S_ISDIR(parent_info.st_mode) or stat.S_ISLNK(parent_info.st_mode) or _path_is_reparse(parent_info):
            raise OSError("unsafe parent")
    except (OSError, RuntimeError):
        raise _fail(failure_code) from None
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        _read_exact_receipt(path, raw, max_bytes=max_bytes, failure_code=failure_code)
        return
    except OSError:
        raise _fail(failure_code) from None
    try:
        offset = 0
        while offset < len(raw):
            written = os.write(descriptor, raw[offset:])
            if written <= 0:
                raise OSError("short write")
            offset += written
        os.fsync(descriptor)
    except OSError:
        try:
            os.close(descriptor)
        finally:
            path.unlink(missing_ok=True)
        raise _fail(failure_code) from None
    else:
        os.close(descriptor)
    _read_exact_receipt(path, raw, max_bytes=max_bytes, failure_code=failure_code)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ledger_relative(manifest_sha256: str) -> str:
    if _SHA256_RE.fullmatch(str(manifest_sha256 or "")) is None:
        raise _fail("object_storage_preservation_control_invalid")
    digest = manifest_sha256.removeprefix("sha256:")
    return f"{LEDGER_ROOT}/{digest}.object-storage-bytes-preservation.jsonl"


class _ManifestBoundPreservationLedger(archive_services._ResumeLedger):
    """Private append-only provider ledger bound to one exact manifest.

    The common upload spine writes its successful upload row here before the
    human-readable terminal receipt is created.  A restart can therefore
    recreate the receipt without a second PUT while still rejecting a ledger
    copied from another manifest, target, provider, or remote key.
    """

    _ROW_FIELDS = (
        "schema_version",
        "operation",
        "manifest_sha256",
        "target_identity_sha256",
        "object_id",
        "remote_key_sha256",
        "result_status",
        "preservation_status",
        "remote_state",
        "bytes",
        "part_count",
        "attempts",
        "put_calls",
        "backoff_ms_total",
        "completed_at",
    )
    _RESULT_STATUSES = frozenset(
        {
            "uploaded",
            "skipped_remote_same",
            "review_required",
            "conditional_precondition_failed",
            "conditional_conflict",
            "failed_upload",
            "failed_auth",
            "failed_rate_limited",
        }
    )

    def __init__(self, plan: ObjectStorageBytesPreservationPlan) -> None:
        if plan.manifest is None:
            raise _fail("object_storage_preservation_no_writes")
        relative = _ledger_relative(plan.manifest.manifest_sha256)
        super().__init__(archive_services.archive_internal_path(plan.archive_root, relative))
        self.plan = plan
        self.by_object = {spec.object_id: spec for spec in plan.specs}
        self._torn_trailing_prefix_bytes: int | None = None
        self._rows_cache = self._read_validated_rows()
        self._terminal_by_object: dict[str, dict[str, Any]] = {}
        self._put_calls_by_object: dict[str, int] = {}
        self._total_put_call_count = 0
        for row in self._rows_cache:
            self._index_row(row)

    def _index_row(self, row: Mapping[str, Any]) -> None:
        object_id = str(row["object_id"])
        put_calls = int(row["put_calls"])
        self._put_calls_by_object[object_id] = (
            self._put_calls_by_object.get(object_id, 0) + put_calls
        )
        self._total_put_call_count += put_calls
        if row["preservation_status"] in _TERMINAL_STATUSES:
            if object_id in self._terminal_by_object:
                raise _fail("object_storage_preservation_control_invalid")
            self._terminal_by_object[object_id] = dict(row)

    def _bound_row(
        self,
        values: Mapping[str, Any],
        *,
        preservation_status: str | None,
        remote_state: str | None,
    ) -> dict[str, Any]:
        object_id = str(values.get("object_id") or "")
        spec = self.by_object.get(object_id)
        if spec is None or self.plan.manifest is None:
            raise _fail("object_storage_preservation_control_invalid")
        result_status = str(values.get("result_status") or "")
        if result_status not in self._RESULT_STATUSES:
            raise _fail("object_storage_preservation_control_invalid")
        if preservation_status is not None and preservation_status not in _TERMINAL_STATUSES:
            raise _fail("object_storage_preservation_control_invalid")
        if remote_state is not None and remote_state not in {
            "verified_match",
            "size_mismatch",
            "checksum_mismatch",
        }:
            raise _fail("object_storage_preservation_control_invalid")
        if preservation_status is None:
            if remote_state is not None or result_status in {
                "uploaded",
                "skipped_remote_same",
                "review_required",
            }:
                raise _fail("object_storage_preservation_control_invalid")
        elif preservation_status == "bytes_preserved":
            if result_status != "uploaded" or remote_state != "verified_match":
                raise _fail("object_storage_preservation_control_invalid")
        elif preservation_status == "already_remote_verified":
            if result_status != "skipped_remote_same" or remote_state != "verified_match":
                raise _fail("object_storage_preservation_control_invalid")
        elif (
            preservation_status != "review_required"
            or result_status != "review_required"
            or remote_state not in {"size_mismatch", "checksum_mismatch"}
        ):
            raise _fail("object_storage_preservation_control_invalid")

        def nonnegative_int(name: str) -> int:
            value = values.get(name, 0)
            if type(value) is not int or value < 0:
                raise _fail("object_storage_preservation_control_invalid")
            return value

        completed_at = str(values.get("completed_at") or "")
        try:
            datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            raise _fail("object_storage_preservation_control_invalid") from None
        row = {
            "schema_version": LEDGER_SCHEMA,
            "operation": OPERATION,
            "manifest_sha256": self.plan.manifest.manifest_sha256,
            "target_identity_sha256": spec.target_identity_sha256,
            "object_id": object_id,
            "remote_key_sha256": _sha256_document(spec.remote_key),
            "result_status": result_status,
            "preservation_status": preservation_status,
            "remote_state": remote_state,
            "bytes": nonnegative_int("bytes"),
            "part_count": nonnegative_int("part_count"),
            "attempts": nonnegative_int("attempts"),
            "put_calls": nonnegative_int("put_calls"),
            "backoff_ms_total": nonnegative_int("backoff_ms_total"),
            "completed_at": completed_at,
        }
        if result_status == "uploaded" and (
            row["bytes"] != spec.size_bytes or row["put_calls"] < 1
        ):
            raise _fail("object_storage_preservation_control_invalid")
        if result_status != "uploaded" and row["bytes"] != 0:
            raise _fail("object_storage_preservation_control_invalid")
        return row

    def _append_bound(self, row: Mapping[str, Any]) -> None:
        if (
            row.get("preservation_status") in _TERMINAL_STATUSES
            and str(row.get("object_id") or "") in self._terminal_by_object
        ):
            raise _fail("object_storage_preservation_control_invalid")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            root = self.plan.archive_root.resolve(strict=True)
            parent = self.path.parent.resolve(strict=True)
            parent_info = os.lstat(parent)
            if (
                not parent.is_relative_to(root)
                or not stat.S_ISDIR(parent_info.st_mode)
                or stat.S_ISLNK(parent_info.st_mode)
                or _path_is_reparse(parent_info)
            ):
                raise OSError("unsafe ledger parent")
            if self.path.exists():
                _plain_regular_file(self.path, max_bytes=_MAX_LEDGER_BYTES)
            if self._torn_trailing_prefix_bytes is not None:
                repair_flags = os.O_WRONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
                repair_descriptor = os.open(self.path, repair_flags)
                try:
                    os.ftruncate(repair_descriptor, self._torn_trailing_prefix_bytes)
                    os.fsync(repair_descriptor)
                finally:
                    os.close(repair_descriptor)
                self._torn_trailing_prefix_bytes = None
            raw = (
                json.dumps(
                    dict(row),
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("ascii")
                + b"\n"
            )
            if len(raw) > _MAX_MANIFEST_LINE_BYTES:
                raise OSError("ledger row too large")
            flags = (
                os.O_WRONLY
                | os.O_APPEND
                | os.O_CREAT
                | getattr(os, "O_BINARY", 0)
                | getattr(os, "O_NOFOLLOW", 0)
            )
            descriptor = os.open(self.path, flags, 0o600)
            try:
                opened = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(opened.st_mode)
                    or stat.S_ISLNK(opened.st_mode)
                    or _path_is_reparse(opened)
                    or int(getattr(opened, "st_nlink", 1)) != 1
                    or opened.st_size + len(raw) > _MAX_LEDGER_BYTES
                ):
                    raise OSError("unsafe ledger")
                offset = 0
                while offset < len(raw):
                    written = os.write(descriptor, raw[offset:])
                    if written <= 0:
                        raise OSError("short ledger append")
                    offset += written
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            _plain_regular_file(self.path, max_bytes=_MAX_LEDGER_BYTES)
        except (OSError, TypeError, ValueError, UnicodeError, ObjectStoragePreservationError):
            raise _fail("object_storage_preservation_control_invalid") from None
        self._rows_cache.append(dict(row))
        self._index_row(row)

    def _read_validated_rows(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            before = _plain_regular_file(self.path, max_bytes=_MAX_LEDGER_BYTES)
            raw = self.path.read_bytes()
            after = _plain_regular_file(self.path, max_bytes=_MAX_LEDGER_BYTES)
            if (
                len(raw) != before.st_size
                or after.st_size != before.st_size
                or after.st_mtime_ns != before.st_mtime_ns
            ):
                raise ValueError("ledger changed")
            raw_lines = raw.splitlines(keepends=True)
            rows: list[dict[str, Any]] = []
            consumed = 0
            for index, raw_line in enumerate(raw_lines):
                if len(raw_line) > _MAX_MANIFEST_LINE_BYTES:
                    raise ValueError("ledger row too large")
                has_newline = raw_line.endswith(b"\n")
                line = raw_line[:-1] if has_newline else raw_line
                if line.endswith(b"\r"):
                    line = line[:-1]
                try:
                    parsed = _strict_json(line)
                except Exception:
                    if index == len(raw_lines) - 1 and not has_newline:
                        self._torn_trailing_prefix_bytes = consumed
                        break
                    raise
                if not has_newline:
                    # A valid JSON row without its terminating newline is also a
                    # torn append; do not grant it durable authority.
                    self._torn_trailing_prefix_bytes = consumed
                    break
                if set(parsed) != set(self._ROW_FIELDS):
                    raise ValueError("ledger fields")
                rebuilt = self._bound_row(
                    parsed,
                    preservation_status=parsed.get("preservation_status"),
                    remote_state=parsed.get("remote_state"),
                )
                if rebuilt != parsed:
                    raise ValueError("ledger binding")
                rows.append(rebuilt)
                consumed += len(raw_line)
            return rows
        except Exception:
            raise _fail("object_storage_preservation_control_invalid") from None

    def append(self, row: dict[str, Any]) -> None:
        result_status = str(row.get("result_status") or "")
        preservation_status = (
            "bytes_preserved"
            if result_status == "uploaded"
            else (
                "already_remote_verified"
                if result_status == "skipped_remote_same"
                else None
            )
        )
        remote_state = "verified_match" if preservation_status is not None else None
        self._append_bound(
            self._bound_row(
                row,
                preservation_status=preservation_status,
                remote_state=remote_state,
            )
        )

    def append_terminal(
        self,
        spec: _PreservationSpec,
        *,
        preservation_status: str,
        remote_state: str,
        put_calls: int = 0,
    ) -> dict[str, Any]:
        result_status = (
            "review_required"
            if preservation_status == "review_required"
            else "skipped_remote_same"
        )
        row = self._bound_row(
            {
                "object_id": spec.object_id,
                "result_status": result_status,
                "bytes": 0,
                "part_count": 0,
                "attempts": 1,
                "put_calls": put_calls,
                "backoff_ms_total": 0,
                "completed_at": _now_iso(),
            },
            preservation_status=preservation_status,
            remote_state=remote_state,
        )
        self._append_bound(row)
        return row

    def append_attempt(self, result: Mapping[str, Any]) -> None:
        row = dict(result)
        row["completed_at"] = _now_iso()
        self._append_bound(
            self._bound_row(row, preservation_status=None, remote_state=None)
        )

    def rows(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._rows_cache]

    def put_calls_for(self, spec: _PreservationSpec) -> int:
        return self._put_calls_by_object.get(spec.object_id, 0)

    def terminal_for(self, spec: _PreservationSpec) -> dict[str, Any] | None:
        row = self._terminal_by_object.get(spec.object_id)
        return None if row is None else dict(row)

    def terminal_success_object_ids(self) -> set[str]:
        return {
            object_id
            for object_id, row in self._terminal_by_object.items()
            if row["preservation_status"]
            in {"bytes_preserved", "already_remote_verified"}
        }

    def total_put_calls(self) -> int:
        return self._total_put_call_count


def _receipt_path(plan: ObjectStorageBytesPreservationPlan, spec: _PreservationSpec) -> Path:
    return archive_services.archive_internal_path(plan.archive_root, spec.receipt_relative)


def _read_terminal_receipt(
    plan: ObjectStorageBytesPreservationPlan,
    spec: _PreservationSpec,
    ledger: _ManifestBoundPreservationLedger,
) -> dict[str, Any] | None:
    path = _receipt_path(plan, spec)
    if not path.exists():
        return None
    terminal = ledger.terminal_for(spec)
    if terminal is None or plan.manifest is None:
        raise _fail("object_storage_preservation_receipt_conflict")
    try:
        before = _plain_regular_file(path, max_bytes=_MAX_RECEIPT_BYTES)
        raw = path.read_bytes()
        after = _plain_regular_file(path, max_bytes=_MAX_RECEIPT_BYTES)
        if (
            len(raw) != before.st_size
            or after.st_size != before.st_size
            or after.st_mtime_ns != before.st_mtime_ns
        ):
            raise ValueError("changed")
        document = _strict_json(raw)
    except Exception:
        raise _fail("object_storage_preservation_receipt_conflict") from None
    expected = _receipt_document(
        manifest_sha256=plan.manifest.manifest_sha256,
        receipt_token=spec.receipt_token,
        object_id=spec.object_id,
        size_bytes=spec.size_bytes,
        provider_kind=plan.provider_kind,
        store_ref=plan.store_ref,
        inventory_sha256=plan.source_inventory_sha256,
        preservation_status=str(terminal["preservation_status"]),
        classified_at=str(terminal["completed_at"]),
        provider_put_call_count=ledger.put_calls_for(spec),
        remote_state=str(terminal["remote_state"]),
    )
    if document != expected:
        raise _fail("object_storage_preservation_receipt_conflict")
    return document


def _create_terminal_receipt(
    plan: ObjectStorageBytesPreservationPlan,
    spec: _PreservationSpec,
    ledger: _ManifestBoundPreservationLedger,
) -> dict[str, Any]:
    existing = _read_terminal_receipt(plan, spec, ledger)
    if existing is not None:
        return existing
    terminal = ledger.terminal_for(spec)
    if terminal is None or plan.manifest is None:
        raise _fail("object_storage_preservation_receipt_conflict")
    document = _receipt_document(
        manifest_sha256=plan.manifest.manifest_sha256,
        receipt_token=spec.receipt_token,
        object_id=spec.object_id,
        size_bytes=spec.size_bytes,
        provider_kind=plan.provider_kind,
        store_ref=plan.store_ref,
        inventory_sha256=plan.source_inventory_sha256,
        preservation_status=str(terminal["preservation_status"]),
        classified_at=str(terminal["completed_at"]),
        provider_put_call_count=ledger.put_calls_for(spec),
        remote_state=str(terminal["remote_state"]),
    )
    _create_or_match_receipt(
        plan.archive_root,
        spec.receipt_relative,
        _canonical_receipt_bytes(document),
    )
    return document


class _Payloads:
    def __init__(self, specs: Sequence[_PreservationSpec]) -> None:
        self.by_item = {
            "item:"
            + hashlib.sha256(
                (spec.object_id + "\x00" + spec.receipt_relative).encode("ascii")
            ).hexdigest(): spec
            for spec in specs
        }

    def field_value(
        self,
        *,
        item_id: str,
        field_ref: str,
        state: str,
        heartbeat: Callable[[], None],
    ) -> bytes | None:
        heartbeat()
        spec = self.by_item.get(item_id)
        if spec is None or field_ref != "terminal_state_token":
            raise ValueError("payload boundary")
        if state == "pre":
            return None
        if state == "post":
            return spec.receipt_token
        if state == "source":
            digest, size = _hash_plain_file(spec.local_path, heartbeat=heartbeat)
            if digest != spec.object_id.removeprefix("sha256:") or size != spec.size_bytes:
                raise _fail("object_storage_preservation_source_drifted")
            return spec.source_token
        raise ValueError("payload state")


class _Verifier:
    def __init__(
        self,
        root: Path,
        specs: Sequence[_PreservationSpec],
        query: ObjectStorageRemoteQueryAdapter,
        plan: ObjectStorageBytesPreservationPlan,
        ledger: _ManifestBoundPreservationLedger,
    ) -> None:
        self.root = root
        self.by_target = {spec.receipt_relative: spec for spec in specs}
        self.query = query
        self.plan = plan
        self.ledger = ledger
        self._verified: set[str] = set()

    def target_identity_sha256(
        self,
        *,
        target_kind: str,
        target_ref: str,
        heartbeat: Callable[[], None],
    ) -> str:
        heartbeat()
        spec = self.by_target.get(target_ref)
        if target_kind != "object_storage_preservation_terminal_receipt" or spec is None:
            raise ValueError("target boundary")
        return spec.target_identity_sha256

    def read_field(
        self,
        *,
        target_kind: str,
        target_ref: str,
        field_ref: str,
        heartbeat: Callable[[], None],
    ) -> bytes | None:
        spec = self.by_target.get(target_ref)
        if (
            target_kind != "object_storage_preservation_terminal_receipt"
            or field_ref != "terminal_state_token"
            or spec is None
        ):
            raise ValueError("field boundary")
        receipt = _read_terminal_receipt(self.plan, spec, self.ledger)
        if receipt is None:
            return None
        if target_ref not in self._verified:
            evidence = self.query.query(
                remote_key=spec.remote_key,
                expected_size=spec.size_bytes,
                expected_sha256=spec.object_id.removeprefix("sha256:"),
                heartbeat=heartbeat,
            )
            terminal = self.ledger.terminal_for(spec)
            if terminal is None or evidence.state != terminal["remote_state"]:
                raise ValueError("remote verification")
            self._verified.add(target_ref)
        return spec.receipt_token


class _Writer:
    def __init__(
        self,
        plan: ObjectStorageBytesPreservationPlan,
        transport: archive_services.ObjectStorageTransport,
    ) -> None:
        self.plan = plan
        self.by_target = {spec.receipt_relative: spec for spec in plan.specs}
        self.transport = transport
        self.query = ObjectStorageRemoteQueryAdapter(transport)
        self.ledger = _ManifestBoundPreservationLedger(plan)
        (
            self.expected_no_retry_put_calls,
            self.manifest_bound_put_call_ceiling,
        ) = _provider_put_call_budget(plan.specs)

    def write_field(
        self,
        *,
        target_kind: str,
        target_ref: str,
        field_ref: str,
        value: bytes | None,
        heartbeat: Callable[[], None],
    ) -> None:
        spec = self.by_target.get(target_ref)
        if (
            target_kind != "object_storage_preservation_terminal_receipt"
            or field_ref != "terminal_state_token"
            or spec is None
            or value != spec.receipt_token
        ):
            raise ValueError("write boundary")
        digest, size = _hash_plain_file(spec.local_path, heartbeat=heartbeat)
        if digest != spec.object_id.removeprefix("sha256:") or size != spec.size_bytes:
            raise _fail("object_storage_preservation_source_drifted")
        terminal = self.ledger.terminal_for(spec)
        if terminal is not None:
            evidence = self.query.query(
                remote_key=spec.remote_key,
                expected_size=spec.size_bytes,
                expected_sha256=digest,
                heartbeat=heartbeat,
            )
            if evidence.state == "verification_unavailable":
                raise _fail("object_storage_preservation_remote_unavailable")
            if evidence.state != terminal["remote_state"]:
                raise _fail("object_storage_preservation_remote_conflict")
            _create_terminal_receipt(self.plan, spec, self.ledger)
            return

        before = self.query.query(
            remote_key=spec.remote_key,
            expected_size=spec.size_bytes,
            expected_sha256=digest,
            heartbeat=heartbeat,
        )
        if before.state == "verified_match":
            self.ledger.append_terminal(
                spec,
                preservation_status="already_remote_verified",
                remote_state="verified_match",
            )
        elif before.state == "absent":
            if self.ledger.total_put_calls() >= self.manifest_bound_put_call_ceiling:
                raise _fail("object_storage_preservation_upload_failed")
            result = _call_with_heartbeat(
                lambda: archive_services._object_storage_execute_one_upload(
                    transport=self.transport,
                    key=spec.remote_key,
                    data_path=spec.local_path,
                    size=spec.size_bytes,
                    content_sha256=digest,
                    multipart_threshold_bytes=archive_services.OBJECT_STORAGE_MULTIPART_THRESHOLD_BYTES,
                    multipart_part_size_bytes=archive_services.OBJECT_STORAGE_MULTIPART_PART_SIZE_BYTES,
                    skip_uploaded=False,
                    ledger=self.ledger,
                    force_upload=True,
                    create_only=True,
                ),
                heartbeat=heartbeat,
            )
            if result.get("result_status") in {
                "conditional_precondition_failed",
                "conditional_conflict",
            }:
                after_conflict = self.query.query(
                    remote_key=spec.remote_key,
                    expected_size=spec.size_bytes,
                    expected_sha256=digest,
                    heartbeat=heartbeat,
                )
                if after_conflict.state == "verified_match":
                    self.ledger.append_terminal(
                        spec,
                        preservation_status="already_remote_verified",
                        remote_state="verified_match",
                        put_calls=int(result.get("put_calls") or 0),
                    )
                elif after_conflict.state in {"size_mismatch", "checksum_mismatch"}:
                    self.ledger.append_terminal(
                        spec,
                        preservation_status="review_required",
                        remote_state=after_conflict.state,
                        put_calls=int(result.get("put_calls") or 0),
                    )
                elif after_conflict.state == "verification_unavailable":
                    self.ledger.append_attempt(result)
                    raise _fail("object_storage_preservation_remote_unavailable")
                else:
                    # A 409/412 followed by absence remains safe to resume.  It
                    # never falls through to an unconditional write.
                    self.ledger.append_attempt(result)
                    raise _fail("object_storage_preservation_upload_failed")
            elif result.get("result_status") != "uploaded" or int(result.get("put_calls") or 0) < 1:
                self.ledger.append_attempt(result)
                if result.get("result_status") in {
                    "failed_auth",
                    "failed_rate_limited",
                    "failed_upload",
                }:
                    raise _fail("object_storage_preservation_remote_unavailable")
                raise _fail("object_storage_preservation_upload_failed")
            if self.ledger.total_put_calls() > self.manifest_bound_put_call_ceiling:
                raise _fail("object_storage_preservation_upload_failed")
        elif before.state in {"size_mismatch", "checksum_mismatch"}:
            self.ledger.append_terminal(
                spec,
                preservation_status="review_required",
                remote_state=before.state,
            )
        else:
            raise _fail("object_storage_preservation_remote_unavailable")
        # The manifest binds a logical terminal-state token; the private ledger
        # records which of the three allowed outcomes occurred.  Only after that
        # fsync succeeds do we create the dynamic immutable receipt.  The exact
        # verifier independently re-queries the remote before checkpointing.
        _create_terminal_receipt(self.plan, spec, self.ledger)


def _approval_binding(plan: ObjectStorageBytesPreservationPlan) -> ExactOperationApprovalBinding:
    if plan.manifest is None:
        raise _fail("object_storage_preservation_no_writes")
    try:
        return exact_operation_manifest_approval_binding(
            plan.manifest,
            operation=ExactHumanApprovalOperation.object_storage_bytes_preservation,
            archive_id=plan.archive_id,
            warnings=(
                "bytes_preserved_is_not_formal_adoption",
                "remote_delete_on_revert_is_not_supported",
            ),
        )
    except Exception:
        raise _fail("object_storage_preservation_plan_invalid") from None


def object_storage_bytes_preservation_context(
    plan: ObjectStorageBytesPreservationPlan,
    *,
    reviewer_claim: str,
) -> ExactHumanApprovalContext:
    reviewer = str(reviewer_claim or "").strip()
    if not reviewer or not plan.approveable:
        raise _fail("object_storage_preservation_plan_invalid")
    return _approval_binding(plan).context(archive_id=plan.archive_id, reviewer_claim=reviewer)


def _assert_approved(
    plan: ObjectStorageBytesPreservationPlan,
    claim: _ClaimedExactHumanApproval,
    context: ExactHumanApprovalContext,
) -> ExactOperationApprovalAuthority:
    binding = _approval_binding(plan)
    if (
        type(claim) is not _ClaimedExactHumanApproval
        or type(context) is not ExactHumanApprovalContext
        or context.operation is not ExactHumanApprovalOperation.object_storage_bytes_preservation
        or context.plan_sha256 != binding.plan_sha256
        or context.target_binding_sha256 != binding.target_binding_sha256
    ):
        raise _fail("object_storage_preservation_approval_required")
    try:
        reference = _ClaimedExactHumanApproval.assert_ready_for_context(claim, context)
        return ExactOperationApprovalAuthority.from_reference(reference)
    except (ExactHumanApprovalError, ExactOperationManifestError):
        raise _fail("object_storage_preservation_approval_required") from None


def _control_relative(manifest_sha256: str) -> str:
    if _SHA256_RE.fullmatch(manifest_sha256) is None:
        raise _fail("object_storage_preservation_control_invalid")
    return f"{CONTROL_ROOT}/{manifest_sha256.removeprefix('sha256:')}.object-storage-bytes-preservation.json"


def _control_document(plan: ObjectStorageBytesPreservationPlan) -> dict[str, Any]:
    if plan.manifest is None:
        raise _fail("object_storage_preservation_no_writes")
    basis = {
        "schema_version": CONTROL_SCHEMA,
        "archive_id": plan.archive_id,
        "provider_kind": plan.provider_kind,
        "store_ref": plan.store_ref,
        "source_inventory_sha256": plan.source_inventory_sha256,
        "inventory": plan.inventory,
        "selected_only": plan.selected_only,
        "already_recorded_count": plan.already_recorded_count,
        "review_count": plan.review_count,
        "manifest": plan.manifest.document(),
        "ledger_relative": _ledger_relative(plan.manifest.manifest_sha256),
        "specs": [
            {
                "object_id": spec.object_id,
                "size_bytes": spec.size_bytes,
                "local_relative": spec.local_relative,
                "remote_key": spec.remote_key,
                "receipt_relative": spec.receipt_relative,
                "receipt_token_sha256": _sha256_bytes(spec.receipt_token),
                "source_token_sha256": _sha256_bytes(spec.source_token),
                "target_identity_sha256": spec.target_identity_sha256,
            }
            for spec in plan.specs
        ],
        "private_control_document": True,
    }
    return {**basis, "control_sha256": _sha256_document(basis)}


def _persist_control(plan: ObjectStorageBytesPreservationPlan) -> str:
    if plan.manifest is None:
        raise _fail("object_storage_preservation_no_writes")
    relative = _control_relative(plan.manifest.manifest_sha256)
    raw = _canonical_control_bytes(_control_document(plan))
    _create_or_match_receipt(
        plan.archive_root,
        relative,
        raw,
        max_bytes=_MAX_CONTROL_BYTES,
        failure_code="object_storage_preservation_control_invalid",
    )
    return relative


def load_object_storage_bytes_preservation_plan(
    archive_root: Path | str,
    *,
    manifest_sha256: str,
) -> ObjectStorageBytesPreservationPlan:
    try:
        root = archive_services.require_existing_archive_root(archive_root)
        current_archive_id = archive_services.read_archive_id(root)
        relative = _control_relative(manifest_sha256)
        path = archive_services.archive_internal_path(root, relative)
        before = _plain_regular_file(path, max_bytes=_MAX_CONTROL_BYTES)
        raw = path.read_bytes()
        after = _plain_regular_file(path, max_bytes=_MAX_CONTROL_BYTES)
        if (
            len(raw) != before.st_size
            or after.st_size != before.st_size
            or after.st_mtime_ns != before.st_mtime_ns
        ):
            raise ValueError("control changed while reading")
        document = _strict_json(raw)
    except Exception:
        raise _fail("object_storage_preservation_control_invalid") from None
    supplied_control_sha = document.pop("control_sha256", None)
    if (
        document.get("schema_version") != CONTROL_SCHEMA
        or document.get("private_control_document") is not True
        or type(supplied_control_sha) is not str
        or not hmac.compare_digest(supplied_control_sha, _sha256_document(document))
    ):
        raise _fail("object_storage_preservation_control_invalid")
    try:
        manifest = ExactOperationManifest.from_document(document["manifest"])
    except Exception:
        raise _fail("object_storage_preservation_control_invalid") from None
    if manifest.manifest_sha256 != manifest_sha256:
        raise _fail("object_storage_preservation_control_invalid")
    provider_kind = document.get("provider_kind")
    store_ref = document.get("store_ref")
    inventory = document.get("inventory")
    specs_raw = document.get("specs")
    if (
        document.get("archive_id") != current_archive_id
        or type(provider_kind) is not str
        or provider_kind not in archive_services.OBJECT_STORAGE_ALLOWED_PROVIDERS
        or type(store_ref) is not str
        or not archive_services.safe_object_storage_ref(store_ref)
        or not isinstance(inventory, dict)
        or _SHA256_RE.fullmatch(str(document.get("source_inventory_sha256") or "")) is None
        or type(specs_raw) is not list
        or len(specs_raw) != len(manifest.items)
        or manifest.operation != OPERATION
        or document.get("ledger_relative") != _ledger_relative(manifest.manifest_sha256)
        or manifest.archive_identity_sha256
        != exact_human_approval_archive_identity_sha256(current_archive_id)
    ):
        raise _fail("object_storage_preservation_control_invalid")
    _require_setup_evidence(
        root,
        provider_kind=provider_kind,
        store_ref=store_ref,
    )
    rows, groups = _read_manifest_groups(root, progress=None)
    current_inventory, _current_unique_rows = _inventory(rows, groups)
    if (
        current_inventory != inventory
        or current_inventory.get("source_inventory_sha256")
        != document.get("source_inventory_sha256")
    ):
        raise _fail("object_storage_preservation_plan_changed")
    specs: list[_PreservationSpec] = []
    for item, raw_spec in zip(manifest.items, specs_raw):
        if not isinstance(raw_spec, Mapping):
            raise _fail("object_storage_preservation_control_invalid")
        try:
            object_id = _normalize_object_id(raw_spec.get("object_id"))
            size = raw_spec.get("size_bytes")
            local_relative = raw_spec.get("local_relative")
            group = groups[object_id]
        except Exception:
            raise _fail("object_storage_preservation_plan_changed") from None
        if (
            type(size) is not int
            or type(local_relative) is not str
            or len(item.fields) != 1
            or len(group) != 1
            or group[0].get("size_bytes") != size
            or _has_object_storage_record(group[0])
            or _local_paths(group[0]) != [local_relative]
        ):
            raise _fail("object_storage_preservation_plan_changed")
        local_path = _safe_local_path(root, local_relative)
        inventory_sha = str(document.get("source_inventory_sha256") or "")
        receipt_relative = _receipt_relative(object_id, inventory_sha)
        receipt_token = _receipt_token(
            object_id=object_id,
            size_bytes=size,
            provider_kind=provider_kind,
            store_ref=store_ref,
            inventory_sha256=inventory_sha,
        )
        source_token = _canonical_bytes(
            {
                "schema_version": "wom-kit/object-storage-bytes-preservation-source/v0.1",
                "object_id": object_id,
                "size_bytes": size,
                "local_relative_sha256": _sha256_document(local_relative),
                "source_inventory_sha256": inventory_sha,
            }
        )
        target_identity = _target_identity(
            archive_id=document["archive_id"],
            object_id=object_id,
            receipt_relative=receipt_relative,
            provider_kind=provider_kind,
            store_ref=store_ref,
        )
        spec = _PreservationSpec(
            object_id=object_id,
            size_bytes=size,
            local_relative=local_relative,
            local_path=local_path,
            remote_key=object_storage_bytes_preserved_remote_key(object_id),
            receipt_relative=receipt_relative,
            receipt_token=receipt_token,
            source_token=source_token,
            target_identity_sha256=target_identity,
        )
        if (
            item.target_ref != receipt_relative
            or item.target_identity_sha256 != target_identity
            or item.fields[0].post_sha256 != hash_field_value(receipt_token)
            or item.fields[0].source_sha256 != hash_field_value(source_token)
            or raw_spec.get("receipt_token_sha256") != _sha256_bytes(receipt_token)
            or raw_spec.get("source_token_sha256") != _sha256_bytes(source_token)
            or raw_spec.get("remote_key") != spec.remote_key
            or raw_spec.get("receipt_relative") != receipt_relative
            or raw_spec.get("target_identity_sha256") != target_identity
        ):
            raise _fail("object_storage_preservation_control_invalid")
        specs.append(spec)
    return ObjectStorageBytesPreservationPlan(
        archive_root=root,
        archive_id=document["archive_id"],
        provider_kind=provider_kind,
        store_ref=store_ref,
        source_inventory_sha256=document["source_inventory_sha256"],
        inventory=inventory,
        manifest=manifest,
        specs=tuple(specs),
        already_recorded_count=int(document.get("already_recorded_count") or 0),
        review_count=int(document.get("review_count") or 0),
        selected_only=document.get("selected_only"),
        loaded_from_control=True,
    )


def _fresh_revalidated(
    plan: ObjectStorageBytesPreservationPlan,
    *,
    progress_hook: Callable[[ExactOperationProgress], None] | None,
) -> ObjectStorageBytesPreservationPlan:
    _require_setup_evidence(
        plan.archive_root,
        provider_kind=plan.provider_kind,
        store_ref=plan.store_ref,
    )
    if plan.loaded_from_control:
        return plan
    if plan.manifest is None:
        raise _fail("object_storage_preservation_no_writes")
    total_items = len(plan.specs)
    total_fields = sum(len(item.fields) for item in plan.manifest.items)
    last_emitted = time.monotonic()

    def publish(completed_items: int) -> None:
        if progress_hook is not None:
            progress_hook(
                ExactOperationProgress(
                    plan.manifest.manifest_sha256,
                    None,
                    "apply",
                    "preflight",
                    max(0, min(completed_items, total_items)),
                    total_items,
                    0,
                    total_fields,
                )
            )

    publish(0)

    def revalidation_progress(
        stage: str,
        message: str,
        current: int | None,
        _total: int | None,
    ) -> None:
        nonlocal last_emitted
        now = time.monotonic()
        done = stage == "preservation-source-hash" and message == "done"
        if done or now - last_emitted >= 10.0:
            publish(int(current or 0) if stage == "preservation-source-hash" else 0)
            last_emitted = now

    current = _plan_core(
        plan.archive_root,
        provider_kind=plan.provider_kind,
        store_ref=plan.store_ref,
        only=plan.selected_only,
        max_objects=None,
        progress=revalidation_progress,
    )
    if (
        current.manifest is None
        or plan.manifest is None
        or current.manifest.document() != plan.manifest.document()
        or current.source_inventory_sha256 != plan.source_inventory_sha256
    ):
        raise _fail("object_storage_preservation_plan_changed")
    return current


def _execution_adapters(
    plan: ObjectStorageBytesPreservationPlan,
    transport: archive_services.ObjectStorageTransport,
) -> tuple[_Payloads, _Writer, _Verifier, _ManifestBoundPreservationLedger]:
    query = ObjectStorageRemoteQueryAdapter(transport)
    writer = _Writer(plan, transport)
    verifier = _Verifier(
        plan.archive_root,
        plan.specs,
        query,
        plan,
        writer.ledger,
    )
    return _Payloads(plan.specs), writer, verifier, writer.ledger


def _durable_result_counts(
    plan: ObjectStorageBytesPreservationPlan,
    ledger: _ManifestBoundPreservationLedger,
) -> dict[str, Any]:
    counts = {status: 0 for status in sorted(_TERMINAL_STATUSES)}
    bytes_uploaded = 0
    provider_put_calls = 0
    for spec in plan.specs:
        receipt = _read_terminal_receipt(plan, spec, ledger)
        if receipt is None:
            raise _fail("object_storage_preservation_receipt_conflict")
        status = str(receipt.get("preservation_status") or "")
        if status not in counts:
            raise _fail("object_storage_preservation_receipt_conflict")
        counts[status] += 1
        bytes_uploaded += int(receipt.get("bytes_uploaded") or 0)
        provider_put_calls += int(receipt.get("provider_put_call_count") or 0)
    if sum(counts.values()) != len(plan.specs):
        raise _fail("object_storage_preservation_receipt_conflict")
    return {
        "classification_counts": counts,
        "bytes_uploaded": bytes_uploaded,
        "provider_put_call_count": provider_put_calls,
    }


def _apply_with_store(
    plan: ObjectStorageBytesPreservationPlan,
    authority: ExactOperationApprovalAuthority,
    transport: archive_services.ObjectStorageTransport,
    checkpoints: FileExactOperationCheckpointStore,
    *,
    resume: bool,
    progress_hook: Callable[[ExactOperationProgress], None] | None,
) -> dict[str, Any]:
    if plan.manifest is None:
        raise _fail("object_storage_preservation_no_writes")
    payloads, writer, verifier, ledger = _execution_adapters(plan, transport)
    core = apply_exact_operation(
        plan.manifest,
        payloads=payloads,
        writer=writer,
        verifier=verifier,
        checkpoint_store=checkpoints,
        approval_authority=authority,
        resume=resume,
        progress_hook=progress_hook,
    )
    durable = _durable_result_counts(plan, ledger)
    classifications = durable["classification_counts"]
    review_count = int(classifications["review_required"])
    result_state = "completed_with_review" if review_count else "bytes_preserved"
    return {
        "schema_version": RESULT_SCHEMA,
        "ok": core.get("status") == "completed",
        "state": result_state,
        "manifest_sha256": plan.manifest.manifest_sha256,
        "execution": core,
        "item_count": len(plan.specs),
        "uploaded_count": int(classifications["bytes_preserved"]),
        "bytes_preserved_count": int(classifications["bytes_preserved"]),
        "already_remote_verified_count": int(
            classifications["already_remote_verified"]
        ),
        "review_required_count": review_count,
        "classification_counts": classifications,
        "classification_sum_matches_item_count": sum(classifications.values())
        == len(plan.specs),
        "bytes_uploaded": durable["bytes_uploaded"],
        "provider_put_call_count": durable["provider_put_call_count"],
        "expected_no_retry_provider_put_call_count": writer.expected_no_retry_put_calls,
        "manifest_bound_provider_put_call_ceiling": writer.manifest_bound_put_call_ceiling,
        "independent_remote_verification": True,
        "preservation_status": result_state,
        "formal_adoption_status": "not_adopted",
        "manifest_location_updates": 0,
        "bytes_preserved_is_formal_adoption": False,
        "remote_delete_on_revert_supported": False,
        "common_exact_operation_manifest_used": True,
        "manifest_bound_private_ledger_used": True,
        "private_values_echoed": False,
        "local_paths_echoed": False,
        "remote_keys_echoed": False,
        "credential_values_echoed": False,
    }


def _apply_core(
    plan: ObjectStorageBytesPreservationPlan,
    claim: _ClaimedExactHumanApproval,
    *,
    context: ExactHumanApprovalContext,
    transport_factory: Callable[[], archive_services.ObjectStorageTransport],
    resume: bool = False,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
) -> dict[str, Any]:
    if type(plan) is not ObjectStorageBytesPreservationPlan or plan.manifest is None:
        raise _fail("object_storage_preservation_no_writes")
    current = _fresh_revalidated(plan, progress_hook=progress_hook)
    authority = _assert_approved(current, claim, context)
    with exact_operation_writer_lock(current.archive_root) as writer_lock:
        _persist_control(current)
        checkpoints = FileExactOperationCheckpointStore(current.archive_root, writer_lock=writer_lock)
        try:
            transport = transport_factory()
        except Exception:
            raise _fail("object_storage_preservation_remote_unavailable") from None
        if transport is None:
            raise _fail("object_storage_preservation_remote_unavailable")
        return _apply_with_store(
            current,
            authority,
            transport,
            checkpoints,
            resume=resume,
            progress_hook=progress_hook,
        )


def execute_object_storage_bytes_preservation(
    plan: ObjectStorageBytesPreservationPlan,
    *,
    reviewer_claim: str,
    transport_factory: Callable[[], archive_services.ObjectStorageTransport],
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
) -> dict[str, Any]:
    if type(plan) is not ObjectStorageBytesPreservationPlan or not plan.approveable:
        raise _fail("object_storage_preservation_no_writes")
    context = object_storage_bytes_preservation_context(plan, reviewer_claim=reviewer_claim)
    return _execute_exact_human_approved_write(
        plan.archive_root,
        context,
        lambda claim: _apply_core(
            plan,
            claim,
            context=context,
            transport_factory=transport_factory,
            progress_hook=progress_hook,
        ),
    )


def resume_object_storage_bytes_preservation(
    plan: ObjectStorageBytesPreservationPlan,
    *,
    reviewer_claim: str,
    approval_id: str,
    execution_sha256: str,
    transport_factory: Callable[[], archive_services.ObjectStorageTransport],
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
    key_provider: Any = None,
) -> dict[str, Any]:
    if (
        type(plan) is not ObjectStorageBytesPreservationPlan
        or not plan.loaded_from_control
        or plan.manifest is None
        or _SHA256_RE.fullmatch(str(execution_sha256 or "")) is None
    ):
        raise _fail("object_storage_preservation_resume_invalid")
    context = object_storage_bytes_preservation_context(plan, reviewer_claim=reviewer_claim)
    with exact_operation_writer_lock(plan.archive_root) as writer_lock:
        checkpoints = FileExactOperationCheckpointStore(plan.archive_root, writer_lock=writer_lock)

        def _writer(claim: _ClaimedExactHumanApproval) -> Mapping[str, Any]:
            current = _fresh_revalidated(plan, progress_hook=progress_hook)
            authority = _assert_approved(current, claim, context)
            actual = exact_operation_execution_sha256(
                current.manifest,
                approval_authority=authority,
            )
            if not hmac.compare_digest(actual, execution_sha256):
                raise _fail("object_storage_preservation_resume_invalid")
            try:
                transport = transport_factory()
            except Exception:
                raise _fail("object_storage_preservation_remote_unavailable") from None
            return _apply_with_store(
                current,
                authority,
                transport,
                checkpoints,
                resume=True,
                progress_hook=progress_hook,
            )

        return _resume_exact_human_approved_write_core(
            plan.archive_root,
            context,
            approval_id,
            lambda _claim: checkpoints.resume_checkpoint_present(execution_sha256),
            _writer,
            key_provider=key_provider,
        )


def verify_object_storage_bytes_preservation(
    plan: ObjectStorageBytesPreservationPlan,
    *,
    transport: archive_services.ObjectStorageTransport,
    heartbeat: Callable[[], None] | None = None,
) -> dict[str, Any]:
    if type(plan) is not ObjectStorageBytesPreservationPlan or plan.manifest is None:
        raise _fail("object_storage_preservation_plan_invalid")
    _require_setup_evidence(
        plan.archive_root,
        provider_kind=plan.provider_kind,
        store_ref=plan.store_ref,
    )
    _payloads, _writer, verifier, _ledger = _execution_adapters(plan, transport)
    result = verify_exact_operation(
        plan.manifest,
        verifier=verifier,
        state="post",
        heartbeat=heartbeat,
    )
    return {
        "schema_version": VERIFY_SCHEMA,
        "ok": result["all_match"],
        "manifest_sha256": plan.manifest.manifest_sha256,
        "verified_item_count": len(plan.specs) if result["all_match"] else 0,
        "verification": result,
        "formal_adoption_status": "not_adopted",
        "provider_api_called": True,
        "writes_performed": False,
        "private_values_echoed": False,
        "remote_keys_echoed": False,
    }


__all__ = [
    "ObjectStorageBytesPreservationPlan",
    "ObjectStoragePreservationError",
    "ObjectStorageRemoteQueryAdapter",
    "ObjectStorageRemoteQueryResult",
    "execute_object_storage_bytes_preservation",
    "load_object_storage_bytes_preservation_plan",
    "object_storage_bytes_preserved_remote_key",
    "object_storage_bytes_preservation_context",
    "plan_object_storage_bytes_preservation",
    "resume_object_storage_bytes_preservation",
    "verify_object_storage_bytes_preservation",
]
