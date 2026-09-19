"""Exact, resumable restore of verified remote Objet bytes into the local store.

v0.4.28 answers acceptance rows OB-01 (a full authenticated GET whose size and
sha256 reproduce the object id is the only remote-bytes proof) and OB-03 (the
resolver rehydrates verified bytes without overwriting a local file and without
deleting the remote object).  The 2026-09-04 decision log (decision 6) planned
both for v0.4.23; the update-failure hotfix train pushed them aside.

One approved plan restores N objects.  Every object is one immutable receipt
item: the writer streams the remote body into a private create-only sink,
promotes the sink into ``objects/sha256/<2>/<64>`` only when the streamed size
and sha256 match the manifest identity and the destination is still absent,
and records the outcome.  A remote copy that is absent or mismatching ends as
``review_required`` and never blocks the other objects.  One final manifest
projection adds or reactivates the local location of every restored object in
a single rewrite.  ``verify_only`` runs the same GET proof and receipt without
writing local bytes (OB-01 general workflow).

The remote object is never deleted: the transport's ``delete_object`` is not
reachable from this module.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import archive_services
from . import object_storage_preservation as preservation
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
    ExactOperationItem,
    ExactOperationManifest,
    ExactOperationManifestError,
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
from .project_update_transaction import _atomic_move_file_no_replace
from .target_collection_preview import TargetCollectionItem, TargetCollectionPreview


PLAN_SCHEMA = "wom-kit/object-storage-restore-plan/v0.1"
CONTROL_SCHEMA = "wom-kit/object-storage-restore-control/v0.1"
RECEIPT_SCHEMA = "wom-kit/object-storage-restore-receipt/v0.1"
RESULT_SCHEMA = "wom-kit/object-storage-restore-result/v0.1"
VERIFY_SCHEMA = "wom-kit/object-storage-restore-verification/v0.1"
OPERATION = ExactHumanApprovalOperation.object_storage_bytes_restore.value
RECEIPT_ROOT = "receipts/providers/object-storage-restore"
CONTROL_ROOT = "profiles/local/exact-operations/manifests"
SINK_ROOT = "profiles/local/exact-operations/restore-sinks"
MANIFEST_TARGET_REF = "objects/manifests/files.jsonl#restore-local-location-batch"

MODE_RESTORE = "restore"
MODE_VERIFY_ONLY = "verify_only"
MODES = (MODE_RESTORE, MODE_VERIFY_ONLY)

STATUS_BYTES_RESTORED = "bytes_restored"
STATUS_ALREADY_PRESENT = "already_present_verified"
STATUS_REMOTE_VERIFIED = "remote_verified"
STATUS_REVIEW_REQUIRED = "review_required"
_TERMINAL_STATUSES = frozenset(
    {
        STATUS_BYTES_RESTORED,
        STATUS_ALREADY_PRESENT,
        STATUS_REMOTE_VERIFIED,
        STATUS_REVIEW_REQUIRED,
    }
)
_REVIEW_REASONS = frozenset(
    {"remote_absent", "remote_size_mismatch", "remote_checksum_mismatch"}
)
_LOCAL_STATES = ("available", "offloaded", "absent")
REMOTE_SOURCE_WOM_UPLOADED = "wom_uploaded_location"
REMOTE_SOURCE_PRESERVED = "bytes_preserved_receipt"
_REMOTE_SOURCES = (REMOTE_SOURCE_WOM_UPLOADED, REMOTE_SOURCE_PRESERVED)
_PRESERVED_RECEIPT_STATUSES = frozenset({"bytes_preserved", "already_remote_verified"})

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_BARE_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_RECEIPT_BYTES = 64 * 1024
_MAX_CONTROL_BYTES = 64 * 1024 * 1024


class ObjectStorageRestoreError(RuntimeError):
    """Fixed-code failure; the code never carries a path, key or label."""

    CODES = frozenset(
        {
            "object_storage_restore_archive_invalid",
            "object_storage_restore_plan_invalid",
            "object_storage_restore_plan_changed",
            "object_storage_restore_no_writes",
            "object_storage_restore_setup_evidence_missing",
            "object_storage_restore_setup_evidence_mismatch",
            "object_storage_restore_approval_required",
            "object_storage_restore_control_invalid",
            "object_storage_restore_resume_invalid",
            "object_storage_restore_receipt_conflict",
            "object_storage_restore_remote_unavailable",
            "object_storage_restore_local_conflict",
            "object_storage_restore_local_write_failed",
            "archive_index_rebuild_required",
        }
    )

    def __init__(self, code: str) -> None:
        if code not in self.CODES:
            code = "object_storage_restore_plan_invalid"
        super().__init__(code)
        self.code = code

    def __repr__(self) -> str:
        return f"ObjectStorageRestoreError({self.code!r})"


def _fail(code: str) -> ObjectStorageRestoreError:
    return ObjectStorageRestoreError(code)


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise _fail("object_storage_restore_plan_invalid") from None


def _sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _sha_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _object_id(value: Any) -> str:
    text = str(value or "").strip().lower()
    if _BARE_SHA256_RE.fullmatch(text):
        return "sha256:" + text
    if _SHA256_RE.fullmatch(text):
        return text
    raise _fail("object_storage_restore_plan_invalid")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _locations(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(value) for value in row.get("locations", []) if isinstance(value, Mapping)]


def _logical_key(object_id: str) -> str:
    digest = object_id.removeprefix("sha256:")
    return f"objects/sha256/{digest[:2]}/{digest}"


def _remote_location(
    row: Mapping[str, Any], *, provider_kind: str, store_ref: str
) -> dict[str, Any] | None:
    """Return the one verified ``wom_uploaded`` location for this store, if any.

    Only WOM's own upload or formal-adoption evidence counts (decision 6 and
    the local-sovereignty contract): a ``declared_uploaded`` claim is not a
    remote-bytes proof and is never restored from.
    """

    matches = [
        location
        for location in _locations(row)
        if location.get("provider") == "object_storage"
        and location.get("availability") == "wom_uploaded"
        and location.get("provider_kind") == provider_kind
        and location.get("store_ref") == store_ref
        and location.get("provider_confirmation_by_wom_kit") is True
        and location.get("remote_key_verified") is True
        and type(location.get("remote_key")) is str
        and archive_services.safe_object_storage_remote_key(location["remote_key"])
        and type(location.get("execution_receipt_ref")) is str
        and bool(location.get("execution_receipt_ref"))
    ]
    if len(matches) != 1:
        return None
    return matches[0]


def _preservation_receipt_remote_key(
    root: Path, object_id: str, *, provider_kind: str, store_ref: str
) -> str | None:
    """Return the content-addressed preservation key when a v0.4.13 emergency
    preservation receipt proves the bytes were put (and re-hashed) remotely.

    The receipt records ``bytes_preserved`` or ``already_remote_verified`` for
    this provider and store; its key is derived from the digest, never read
    from the document. Unreadable or foreign receipts are ignored.
    """

    digest = object_id.removeprefix("sha256:")
    try:
        directory = archive_services.archive_internal_path(root, preservation.RECEIPT_ROOT)
    except Exception:
        return None
    if not directory.is_dir():
        return None
    try:
        candidates = sorted(directory.glob(f"{digest}.*.json"))
    except OSError:
        return None
    for path in candidates:
        try:
            raw = path.read_bytes()
            if len(raw) > _MAX_RECEIPT_BYTES:
                continue
            document = preservation._strict_json(raw)
        except Exception:
            continue
        if (
            document.get("object_id") != object_id
            or document.get("provider_kind") != provider_kind
            or document.get("store_ref") != store_ref
            or document.get("remote_key_strategy") != "wom_bytes_preserved_v1"
            or document.get("preservation_status") not in _PRESERVED_RECEIPT_STATUSES
        ):
            continue
        try:
            return preservation.object_storage_bytes_preserved_remote_key(object_id)
        except preservation.ObjectStoragePreservationError:
            return None
    return None


def _local_location_state(row: Mapping[str, Any], logical_key: str) -> str:
    states = set()
    for location in _locations(row):
        if location.get("provider") != "local" or location.get("path") != logical_key:
            continue
        availability = location.get("availability")
        if availability == "available":
            states.add("available")
        elif availability == "offloaded":
            states.add("offloaded")
    if "available" in states:
        return "available"
    if "offloaded" in states:
        return "offloaded"
    return "absent"


def _plain_regular_file_info(path: Path) -> os.stat_result | None:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return None
    except OSError:
        raise _fail("object_storage_restore_local_conflict") from None
    if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or preservation._path_is_reparse(info):
        raise _fail("object_storage_restore_local_conflict")
    return info


def _hash_file(path: Path, *, heartbeat: Callable[[], None]) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
            heartbeat()
    return digest.hexdigest(), size


def _destination_state(
    root: Path, spec_object_id: str, expected_size: int, *, heartbeat: Callable[[], None]
) -> str:
    """Classify the objet-store destination: absent, present_verified or conflict."""

    destination = archive_services.archive_internal_path(root, _logical_key(spec_object_id))
    info = _plain_regular_file_info(destination)
    if info is None:
        return "absent"
    if info.st_size != expected_size:
        return "conflict"
    observed, size = _hash_file(destination, heartbeat=heartbeat)
    if size != expected_size or not hmac.compare_digest(observed, spec_object_id.removeprefix("sha256:")):
        return "conflict"
    return "present_verified"


def _receipt_relative(object_id: str, source_inventory_sha256: str) -> str:
    digest = object_id.removeprefix("sha256:")
    inventory = source_inventory_sha256.removeprefix("sha256:")
    return f"{RECEIPT_ROOT}/{digest}.{inventory[:16]}.json"


def _source_token(
    *,
    object_id: str,
    rows: Sequence[Mapping[str, Any]],
    remote_key: str,
    mode: str,
    remote_source_kind: str,
) -> bytes:
    projection = []
    for row in rows:
        projection.append(
            {
                "object_id": _object_id(row.get("object_id")),
                "sha256": _object_id(row.get("sha256")),
                "size_bytes": row.get("size_bytes"),
                "logical_key_sha256": _sha(row.get("logical_key")),
                "remote_locations_sha256": _sha(
                    [
                        location
                        for location in _locations(row)
                        if location.get("provider") == "object_storage"
                    ]
                ),
            }
        )
    return _canonical(
        {
            "schema_version": "wom-kit/object-storage-restore-source/v0.1",
            "object_id": object_id,
            "rows": projection,
            "remote_key_sha256": _sha(remote_key),
            "remote_source_kind": remote_source_kind,
            "mode": mode,
        }
    )


def _receipt_token(
    *,
    object_id: str,
    size_bytes: int,
    provider_kind: str,
    store_ref: str,
    remote_key: str,
    mode: str,
    source_inventory_sha256: str,
) -> bytes:
    return _canonical(
        {
            "schema_version": "wom-kit/object-storage-restore-state/v0.1",
            "object_id": object_id,
            "size_bytes": size_bytes,
            "provider_kind": provider_kind,
            "store_ref": store_ref,
            "remote_key_sha256": _sha(remote_key),
            "mode": mode,
            "source_inventory_sha256": source_inventory_sha256,
            "remote_verification": "get_rehash_whole_object",
            "terminal_statuses": sorted(_TERMINAL_STATUSES),
        }
    )


def _target_identity(
    *, archive_id: str, object_id: str, receipt_relative: str, source_token: bytes
) -> str:
    return _sha(
        {
            "schema_version": "wom-kit/object-storage-restore-target/v0.1",
            "archive_id": archive_id,
            "object_id": object_id,
            "receipt_relative": receipt_relative,
            "source_token_sha256": _sha_bytes(source_token),
        }
    )


@dataclass(frozen=True, repr=False)
class RestoreSpec:
    object_id: str
    size_bytes: int
    remote_key: str
    remote_source_kind: str
    local_relative: str
    local_location_state: str
    receipt_relative: str
    receipt_token: bytes
    source_token: bytes
    target_identity_sha256: str

    @property
    def needs_local_location(self) -> bool:
        return self.local_location_state != "available"


def _manifest_batch_token(specs: Sequence[RestoreSpec]) -> bytes:
    return _canonical(
        {
            "schema_version": "wom-kit/object-storage-restore-location-batch/v0.1",
            "locations": [
                {
                    "object_id": spec.object_id,
                    "local_relative": spec.local_relative,
                    "receipt_relative": spec.receipt_relative,
                    "size_bytes": spec.size_bytes,
                    "local_location_state_before": spec.local_location_state,
                }
                for spec in sorted(specs, key=lambda item: item.object_id)
            ],
        }
    )


def _manifest_source_token(specs: Sequence[RestoreSpec]) -> bytes:
    return _canonical(
        {
            "schema_version": "wom-kit/object-storage-restore-manifest-source/v0.1",
            "source_tokens": [_sha_bytes(item.source_token) for item in specs],
        }
    )


def _manifest_for_specs(
    archive_id: str, specs: Sequence[RestoreSpec], *, mode: str
) -> ExactOperationManifest | None:
    items: list[ExactOperationItem] = []
    for ordinal, spec in enumerate(specs):
        items.append(
            ExactOperationItem(
                ordinal=ordinal,
                item_id="item:" + hashlib.sha256(spec.receipt_relative.encode("ascii")).hexdigest(),
                target_kind="object_storage_restore_receipt",
                target_ref=spec.receipt_relative,
                target_identity_sha256=spec.target_identity_sha256,
                fields=(
                    ExactFieldEffect(
                        field_ref="remote_bytes_restoration",
                        pre_sha256=hash_field_value(None),
                        post_sha256=hash_field_value(spec.receipt_token),
                        source_sha256=hash_field_value(spec.source_token),
                    ),
                ),
            )
        )
    batch = [spec for spec in specs if spec.needs_local_location] if mode == MODE_RESTORE else []
    if batch:
        source_token = _manifest_source_token(batch)
        items.append(
            ExactOperationItem(
                ordinal=len(items),
                item_id="item:" + hashlib.sha256(MANIFEST_TARGET_REF.encode("ascii")).hexdigest(),
                target_kind="object_storage_restore_manifest_batch",
                target_ref=MANIFEST_TARGET_REF,
                target_identity_sha256=_sha(
                    {
                        "archive_id": archive_id,
                        "target_ref": MANIFEST_TARGET_REF,
                        "source_sha256": _sha_bytes(source_token),
                    }
                ),
                fields=(
                    ExactFieldEffect(
                        field_ref="local_locations",
                        pre_sha256=hash_field_value(None),
                        post_sha256=hash_field_value(_manifest_batch_token(batch)),
                        source_sha256=hash_field_value(source_token),
                    ),
                ),
            )
        )
    if not items:
        return None
    return ExactOperationManifest.build(
        operation=OPERATION,
        archive_identity_sha256=exact_human_approval_archive_identity_sha256(archive_id),
        items=items,
    )


@dataclass(frozen=True, repr=False)
class ObjectStorageRestorePlan:
    archive_root: Path
    archive_id: str
    provider_kind: str
    store_ref: str
    mode: str
    source_inventory_sha256: str
    manifest: ExactOperationManifest | None
    specs: tuple[RestoreSpec, ...]
    counts: Mapping[str, int]
    selected_only: str | None = None
    loaded_from_control: bool = False

    @property
    def batch_specs(self) -> tuple[RestoreSpec, ...]:
        if self.mode != MODE_RESTORE:
            return ()
        return tuple(spec for spec in self.specs if spec.needs_local_location)

    @property
    def approveable(self) -> bool:
        return self.manifest is not None and bool(self.specs)

    def public_document(self) -> dict[str, Any]:
        state = "ready_for_exact_human_approval" if self.approveable else "no_restore_targets"
        reason = "object_storage_restore_ready" if self.approveable else "object_storage_restore_no_writes"
        next_actions: list[str] = []
        if self.approveable:
            next_actions.append(
                "Re-run with --approve --reviewed-by <id> --expected-manifest-sha256 <plan_sha256>; "
                "one native dialog covers every listed object."
            )
        if int(self.counts["local_conflict_count"]):
            next_actions.append(
                "A local file at an objet-store path does not reproduce its object id; "
                "it is never overwritten. Inspect it before restoring that object."
            )
        if int(self.counts["remote_evidence_missing_count"]):
            next_actions.append(
                "Objects without a WOM-verified wom_uploaded location for this store cannot be restored; "
                "formal adoption or a WOM upload must record the remote bytes first."
            )
        return {
            "schema_version": PLAN_SCHEMA,
            "ok": self.approveable,
            "state": state,
            "reason_codes": [reason],
            "mode": self.mode,
            "plan_sha256": self.manifest.manifest_sha256 if self.manifest else None,
            "target_binding_sha256": self.manifest.target_set_sha256 if self.manifest else None,
            "source_binding_sha256": self.manifest.source_set_sha256 if self.manifest else None,
            "effect_binding_sha256": self.manifest.effect_set_sha256 if self.manifest else None,
            "source_inventory_sha256": self.source_inventory_sha256,
            **{str(key): int(value) for key, value in self.counts.items()},
            "planned_object_count": len(self.specs),
            "planned_download_bytes": sum(spec.size_bytes for spec in self.specs),
            "manifest_rewrite_planned_count": 1 if self.batch_specs else 0,
            "per_object_manifest_rewrite_planned_count": 0,
            "provider_get_calls_per_object": 1,
            "provider_put_call_count": 0,
            "remote_delete_supported": False,
            "local_overwrite_supported": False,
            "requires_exact_human_approval": True,
            "common_exact_operation_manifest_used": self.manifest is not None,
            "next_safe_actions": next_actions,
            "provider_api_called": False,
            "credential_values_read": False,
            "writes_performed": False,
            "remote_keys_echoed": False,
            "object_ids_echoed": False,
            "local_paths_echoed": False,
        }


def _require_setup_evidence(
    root: Path, *, provider_kind: str, store_ref: str
) -> object_storage_setup_registration.ObjectStorageSetupEvidence:
    try:
        return object_storage_setup_registration.validate_object_storage_setup_evidence(
            root, provider_kind=provider_kind, store_ref=store_ref
        )
    except object_storage_setup_registration.ObjectStorageSetupRegistrationError as exc:
        code = (
            "object_storage_restore_setup_evidence_missing"
            if exc.code == "object_storage_setup_evidence_missing"
            else "object_storage_restore_setup_evidence_mismatch"
        )
        raise _fail(code) from None


def _source_inventory_sha256(rows: Sequence[Mapping[str, Any]]) -> str:
    return _sha(
        {
            "schema_version": "wom-kit/object-storage-restore-inventory/v0.1",
            "rows": [
                {
                    "object_id": row.get("object_id"),
                    "size_bytes": row.get("size_bytes"),
                    "locations_sha256": _sha(_locations(row)),
                }
                for row in rows
            ],
        }
    )


def _build_plan(
    archive_root: Path | str,
    *,
    provider_kind: str,
    store_ref: str,
    mode: str,
    only: str | None,
    max_objects: int | None,
    progress: Callable[[str, str, int | None, int | None], None] | None,
) -> ObjectStorageRestorePlan:
    try:
        root = archive_services.require_existing_archive_root(archive_root)
        archive_id = archive_services.read_archive_id(root)
    except Exception:
        raise _fail("object_storage_restore_archive_invalid") from None
    normalized_provider = str(provider_kind or "").strip().lower()
    normalized_store = str(store_ref or "").strip()
    if (
        normalized_provider not in archive_services.OBJECT_STORAGE_ALLOWED_PROVIDERS
        or not archive_services.safe_object_storage_ref(normalized_store)
        or mode not in MODES
        or (max_objects is not None and (type(max_objects) is not int or max_objects < 1))
    ):
        raise _fail("object_storage_restore_plan_invalid")
    selected_only = _object_id(only) if only else None
    _require_setup_evidence(root, provider_kind=normalized_provider, store_ref=normalized_store)
    try:
        rows, groups = preservation._read_manifest_groups(root, progress=progress)
    except preservation.ObjectStoragePreservationError:
        raise _fail("object_storage_restore_plan_invalid") from None
    inventory_sha256 = _source_inventory_sha256(rows)
    counts = {
        "manifest_row_count": len(rows),
        "unique_object_count": len(groups),
        "conflicting_definition_count": 0,
        "remote_evidence_missing_count": 0,
        "wom_uploaded_source_count": 0,
        "bytes_preserved_receipt_source_count": 0,
        "already_present_count": 0,
        "local_conflict_count": 0,
        "restore_target_count": 0,
        "verify_target_count": 0,
        "local_location_add_count": 0,
        "local_location_reactivate_count": 0,
        "selected_object_not_found_count": 0,
    }
    heartbeat = (lambda: None) if progress is None else (
        lambda: progress("restore-inventory", "hashing local bytes", None, None)
    )
    specs: list[RestoreSpec] = []
    if selected_only is not None and selected_only not in groups:
        counts["selected_object_not_found_count"] = 1
    for object_id in sorted(groups):
        if selected_only is not None and object_id != selected_only:
            continue
        group = groups[object_id]
        sizes = {row.get("size_bytes") for row in group}
        if len(sizes) != 1:
            counts["conflicting_definition_count"] += 1
            continue
        size_bytes = int(next(iter(sizes)))
        remote = None
        for row in group:
            candidate = _remote_location(row, provider_kind=normalized_provider, store_ref=normalized_store)
            if candidate is not None:
                if remote is not None and remote.get("remote_key") != candidate.get("remote_key"):
                    remote = None
                    counts["conflicting_definition_count"] += 1
                    break
                remote = candidate
        else:
            remote_key: str | None = None
            remote_source_kind = REMOTE_SOURCE_WOM_UPLOADED
            if remote is not None:
                remote_key = str(remote["remote_key"])
            else:
                remote_key = _preservation_receipt_remote_key(
                    root, object_id, provider_kind=normalized_provider, store_ref=normalized_store
                )
                remote_source_kind = REMOTE_SOURCE_PRESERVED
            if remote_key is None:
                counts["remote_evidence_missing_count"] += 1
                continue
            logical_key = _logical_key(object_id)
            local_state = "absent"
            for row in group:
                state = _local_location_state(row, logical_key)
                if state == "available" or (state == "offloaded" and local_state == "absent"):
                    local_state = state
            destination = _destination_state(root, object_id, size_bytes, heartbeat=heartbeat)
            if destination == "conflict":
                counts["local_conflict_count"] += 1
                continue
            if mode == MODE_RESTORE:
                if destination == "present_verified" and local_state == "available":
                    counts["already_present_count"] += 1
                    continue
                counts["restore_target_count"] += 1
                if local_state == "absent":
                    counts["local_location_add_count"] += 1
                elif local_state == "offloaded":
                    counts["local_location_reactivate_count"] += 1
            else:
                counts["verify_target_count"] += 1
            if remote_source_kind == REMOTE_SOURCE_WOM_UPLOADED:
                counts["wom_uploaded_source_count"] += 1
            else:
                counts["bytes_preserved_receipt_source_count"] += 1
            source_token = _source_token(
                object_id=object_id,
                rows=group,
                remote_key=remote_key,
                mode=mode,
                remote_source_kind=remote_source_kind,
            )
            receipt_relative = _receipt_relative(object_id, inventory_sha256)
            specs.append(
                RestoreSpec(
                    object_id=object_id,
                    size_bytes=size_bytes,
                    remote_key=remote_key,
                    remote_source_kind=remote_source_kind,
                    local_relative=logical_key,
                    local_location_state=local_state,
                    receipt_relative=receipt_relative,
                    receipt_token=_receipt_token(
                        object_id=object_id,
                        size_bytes=size_bytes,
                        provider_kind=normalized_provider,
                        store_ref=normalized_store,
                        remote_key=remote_key,
                        mode=mode,
                        source_inventory_sha256=inventory_sha256,
                    ),
                    source_token=source_token,
                    target_identity_sha256=_target_identity(
                        archive_id=archive_id,
                        object_id=object_id,
                        receipt_relative=receipt_relative,
                        source_token=source_token,
                    ),
                )
            )
    if max_objects is not None and len(specs) > max_objects:
        raise _fail("object_storage_restore_plan_invalid")
    manifest = _manifest_for_specs(archive_id, specs, mode=mode)
    return ObjectStorageRestorePlan(
        archive_root=root,
        archive_id=archive_id,
        provider_kind=normalized_provider,
        store_ref=normalized_store,
        mode=mode,
        source_inventory_sha256=inventory_sha256,
        manifest=manifest,
        specs=tuple(specs),
        counts=counts,
        selected_only=selected_only,
    )


def plan_object_storage_restore(
    archive_root: Path | str,
    *,
    provider_kind: str = "cloudflare-r2",
    store_ref: str,
    mode: str = MODE_RESTORE,
    only: str | None = None,
    max_objects: int | None = None,
    progress: Callable[[str, str, int | None, int | None], None] | None = None,
) -> ObjectStorageRestorePlan:
    return _build_plan(
        archive_root,
        provider_kind=provider_kind,
        store_ref=store_ref,
        mode=mode,
        only=only,
        max_objects=max_objects,
        progress=progress,
    )


# --- receipts ----------------------------------------------------------------


def _receipt_document(
    plan: ObjectStorageRestorePlan,
    spec: RestoreSpec,
    *,
    restore_status: str,
    completed_at: str,
    remote_state: str,
    review_reason: str | None,
) -> dict[str, Any]:
    if restore_status not in _TERMINAL_STATUSES:
        raise _fail("object_storage_restore_receipt_conflict")
    if review_reason is not None and review_reason not in _REVIEW_REASONS:
        raise _fail("object_storage_restore_receipt_conflict")
    if remote_state not in {"verified_match", "absent", "size_mismatch", "checksum_mismatch", "not_queried"}:
        raise _fail("object_storage_restore_receipt_conflict")
    local_written = restore_status == STATUS_BYTES_RESTORED
    return {
        "schema_version": RECEIPT_SCHEMA,
        "object_id": spec.object_id,
        "content_sha256": spec.object_id,
        "size_bytes": spec.size_bytes,
        "provider_kind": plan.provider_kind,
        "store_ref": plan.store_ref,
        "remote_key_sha256": _sha(spec.remote_key),
        "remote_source_kind": spec.remote_source_kind,
        "mode": plan.mode,
        "source_inventory_sha256": plan.source_inventory_sha256,
        "exact_operation_manifest_sha256": plan.manifest.manifest_sha256 if plan.manifest else None,
        "receipt_state_sha256": _sha_bytes(spec.receipt_token),
        "restore_status": restore_status,
        "completed_at": completed_at,
        "remote_verification": {
            "performed": remote_state != "not_queried",
            "state": remote_state,
            "verification_kind": "get_rehash_whole_object",
            "size_match": remote_state == "verified_match",
            "whole_object_sha256_match": remote_state == "verified_match",
        },
        "local_bytes_written": local_written,
        "local_bytes_verified_after_write": local_written,
        "local_location_state_before": spec.local_location_state,
        "local_overwrite_performed": False,
        "remote_delete_performed": False,
        "review_reason": review_reason,
        "private_values_echoed": False,
        "credential_values_echoed": False,
        "provider_url_echoed": False,
        "local_path_echoed": False,
    }


def _receipt_path(plan: ObjectStorageRestorePlan, spec: RestoreSpec) -> Path:
    return archive_services.archive_internal_path(plan.archive_root, spec.receipt_relative)


def _read_receipt(plan: ObjectStorageRestorePlan, spec: RestoreSpec) -> dict[str, Any] | None:
    path = _receipt_path(plan, spec)
    if not path.exists():
        return None
    try:
        raw = path.read_bytes()
        if len(raw) > _MAX_RECEIPT_BYTES:
            raise ValueError("large")
        document = preservation._strict_json(raw)
        completed_at = str(document.get("completed_at"))
        datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
        restore_status = str(document.get("restore_status"))
        remote_state = str(document.get("remote_verification", {}).get("state"))
        review_reason = document.get("review_reason")
    except Exception:
        raise _fail("object_storage_restore_receipt_conflict") from None
    expected = _receipt_document(
        plan,
        spec,
        restore_status=restore_status,
        completed_at=completed_at,
        remote_state=remote_state,
        review_reason=review_reason if review_reason is None else str(review_reason),
    )
    if document != expected:
        raise _fail("object_storage_restore_receipt_conflict")
    return document


def _create_receipt(
    plan: ObjectStorageRestorePlan,
    spec: RestoreSpec,
    *,
    restore_status: str,
    remote_state: str,
    review_reason: str | None,
) -> dict[str, Any]:
    existing = _read_receipt(plan, spec)
    if existing is not None:
        return existing
    document = _receipt_document(
        plan,
        spec,
        restore_status=restore_status,
        completed_at=_now_iso(),
        remote_state=remote_state,
        review_reason=review_reason,
    )
    preservation._create_or_match_receipt(
        plan.archive_root,
        spec.receipt_relative,
        _canonical(document) + b"\n",
        max_bytes=_MAX_RECEIPT_BYTES,
        failure_code="object_storage_restore_receipt_conflict",
    )
    return document


# --- remote GET + local promotion ---------------------------------------------


def _sink_relative(plan: ObjectStorageRestorePlan, spec: RestoreSpec) -> str:
    if plan.manifest is None:
        raise _fail("object_storage_restore_no_writes")
    manifest_hex = plan.manifest.manifest_sha256.removeprefix("sha256:")[:16]
    return f"{SINK_ROOT}/{manifest_hex}/{spec.object_id.removeprefix('sha256:')}.part"


def _fetch_and_promote(
    plan: ObjectStorageRestorePlan,
    spec: RestoreSpec,
    transport: archive_services.ObjectStorageTransport,
    *,
    heartbeat: Callable[[], None],
) -> tuple[str, str, str | None]:
    """Return (restore_status, remote_state, review_reason) for one object.

    Raises the fixed unavailable code on transport trouble so the item can be
    resumed; a definite remote absence or mismatch is a terminal review outcome.
    """

    root = plan.archive_root
    digest = spec.object_id.removeprefix("sha256:")
    destination = archive_services.archive_internal_path(root, spec.local_relative)
    if plan.mode == MODE_RESTORE:
        state = _destination_state(root, spec.object_id, spec.size_bytes, heartbeat=heartbeat)
        if state == "conflict":
            raise _fail("object_storage_restore_local_conflict")
        if state == "present_verified":
            # Bytes reappeared locally after the plan; nothing to download and
            # nothing to overwrite. The local location batch still reactivates.
            return STATUS_ALREADY_PRESENT, "not_queried", None
    sink = archive_services.archive_internal_path(root, _sink_relative(plan, spec))
    try:
        sink.parent.mkdir(parents=True, exist_ok=True)
        stale = _plain_regular_file_info(sink)
        if stale is not None:
            sink.unlink()
    except ObjectStorageRestoreError:
        raise
    except OSError:
        raise _fail("object_storage_restore_local_write_failed") from None
    try:
        result = preservation._call_with_heartbeat(
            lambda: transport.get_object(
                key=spec.remote_key,
                sink_path=sink,
                expected_size=spec.size_bytes,
                expected_sha256=digest,
            ),
            heartbeat=heartbeat,
        )
    except Exception:
        raise _fail("object_storage_restore_remote_unavailable") from None
    if not isinstance(result, Mapping):
        raise _fail("object_storage_restore_remote_unavailable")
    status_class = result.get("status_class")
    if status_class == "absent":
        return STATUS_REVIEW_REQUIRED, "absent", "remote_absent"
    if status_class != "ok":
        raise _fail("object_storage_restore_remote_unavailable")
    if result.get("size_match") is not True:
        return STATUS_REVIEW_REQUIRED, "size_mismatch", "remote_size_mismatch"
    if result.get("checksum_match") is not True:
        return STATUS_REVIEW_REQUIRED, "checksum_mismatch", "remote_checksum_mismatch"
    if plan.mode == MODE_VERIFY_ONLY:
        try:
            sink.unlink()
        except OSError:
            pass
        return STATUS_REMOTE_VERIFIED, "verified_match", None
    if result.get("sink_written") is not True:
        raise _fail("object_storage_restore_remote_unavailable")
    # Independent re-hash of the sink before it can become canonical bytes.
    observed, size = _hash_file(sink, heartbeat=heartbeat)
    if size != spec.size_bytes or not hmac.compare_digest(observed, digest):
        try:
            sink.unlink()
        except OSError:
            pass
        raise _fail("object_storage_restore_local_write_failed")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        _atomic_move_file_no_replace(sink, destination)
    except FileExistsError:
        # A file appeared meanwhile: keep it only if it is the same bytes.
        try:
            sink.unlink()
        except OSError:
            pass
        state = _destination_state(root, spec.object_id, spec.size_bytes, heartbeat=heartbeat)
        if state != "present_verified":
            raise _fail("object_storage_restore_local_conflict") from None
        return STATUS_ALREADY_PRESENT, "verified_match", None
    except OSError:
        try:
            sink.unlink()
        except OSError:
            pass
        raise _fail("object_storage_restore_local_write_failed") from None
    if _destination_state(root, spec.object_id, spec.size_bytes, heartbeat=heartbeat) != "present_verified":
        raise _fail("object_storage_restore_local_write_failed")
    return STATUS_BYTES_RESTORED, "verified_match", None


# --- manifest projection --------------------------------------------------------


def _restored_object_ids(plan: ObjectStorageRestorePlan) -> set[str] | None:
    """Object ids whose receipts allow a local location; None while any batch receipt is missing."""

    restored: set[str] = set()
    for spec in plan.batch_specs:
        receipt = _read_receipt(plan, spec)
        if receipt is None:
            return None
        if receipt["restore_status"] in {STATUS_BYTES_RESTORED, STATUS_ALREADY_PRESENT}:
            restored.add(spec.object_id)
    return restored


def _location_is_active_local(location: Mapping[str, Any], logical_key: str) -> bool:
    return (
        location.get("provider") == "local"
        and location.get("path") == logical_key
        and location.get("availability") == "available"
    )


def _batch_state(plan: ObjectStorageRestorePlan) -> bytes | None:
    specs = plan.batch_specs
    if not specs:
        return None
    restored = _restored_object_ids(plan)
    if restored is None:
        # Receipts are still being written: the projection cannot have run.
        return None
    by_id = {spec.object_id: spec for spec in specs}
    seen = {spec.object_id: 0 for spec in specs}
    active = {spec.object_id: False for spec in specs}
    rows, _groups = preservation._read_manifest_groups(plan.archive_root, progress=None)
    for row in rows:
        object_id = _object_id(row.get("object_id"))
        spec = by_id.get(object_id)
        if spec is None:
            continue
        seen[object_id] += 1
        active[object_id] = any(
            _location_is_active_local(location, spec.local_relative) for location in _locations(row)
        )
    if any(value != 1 for value in seen.values()):
        raise _fail("object_storage_restore_plan_changed")
    applied = [object_id for object_id in restored if active[object_id]]
    if not restored:
        # Nothing restorable in this batch: the projection is a recorded no-op.
        return None if _projection_marker_absent(plan) else _manifest_batch_token(specs)
    if not applied:
        return None
    if len(applied) != len(restored):
        raise _fail("object_storage_restore_plan_changed")
    return _manifest_batch_token(specs)


def _projection_marker_relative(plan: ObjectStorageRestorePlan) -> str:
    if plan.manifest is None:
        raise _fail("object_storage_restore_no_writes")
    digest = plan.manifest.manifest_sha256.removeprefix("sha256:")
    return f"{CONTROL_ROOT}/{digest}.object-storage-restore.projection.json"


def _projection_marker_absent(plan: ObjectStorageRestorePlan) -> bool:
    return not archive_services.archive_internal_path(
        plan.archive_root, _projection_marker_relative(plan)
    ).exists()


def _write_projection_marker(plan: ObjectStorageRestorePlan, *, changed: int) -> None:
    document = {
        "schema_version": "wom-kit/object-storage-restore-projection/v0.1",
        "exact_operation_manifest_sha256": plan.manifest.manifest_sha256 if plan.manifest else None,
        "local_location_changes": int(changed),
        "private_control_document": True,
    }
    preservation._create_or_match_receipt(
        plan.archive_root,
        _projection_marker_relative(plan),
        _canonical(document) + b"\n",
        max_bytes=_MAX_RECEIPT_BYTES,
        failure_code="object_storage_restore_control_invalid",
    )


@dataclass
class _ManifestIndexLifecycle:
    generation: str | None = None
    lease_token: archive_services.ArchiveIndexMutationLeaseToken | None = None
    updated: bool = False
    resumed: bool = False


def _require_manifest_index_authority(plan: ObjectStorageRestorePlan) -> None:
    if not plan.batch_specs or plan.manifest is None:
        return
    manifest_path = archive_services.archive_internal_path(plan.archive_root, "objects/manifests/files.jsonl")
    try:
        owner = archive_services.archive_manifest_mutation_owner_sha256(
            operation="object_storage_bytes_restore",
            operation_binding_sha256=plan.manifest.manifest_sha256,
        )
        snapshot = archive_services.archive_index_stable_file_snapshot(
            plan.archive_root,
            manifest_path,
            max_bytes=archive_services.ZETTEL_OBJET_LINK_MANIFEST_MAX_BYTES,
        )
        archive_services.require_archive_manifest_index_mutation_authority(
            plan.archive_root,
            operation_owner_sha256=owner,
            expected_pre_manifest_sha256=snapshot["file_sha256"],
            expected_post_manifest_sha256=snapshot["file_sha256"],
        )
    except (archive_services.ArchiveServiceError, OSError):
        raise _fail("archive_index_rebuild_required") from None


def _apply_manifest_batch(plan: ObjectStorageRestorePlan, *, lifecycle: _ManifestIndexLifecycle) -> int:
    specs = plan.batch_specs
    if not specs or plan.manifest is None:
        return 0
    restored = _restored_object_ids(plan)
    if restored is None:
        raise _fail("object_storage_restore_plan_changed")
    by_id = {spec.object_id: spec for spec in specs}
    manifest_path = archive_services.archive_internal_path(plan.archive_root, "objects/manifests/files.jsonl")
    owner = archive_services.archive_manifest_mutation_owner_sha256(
        operation="object_storage_bytes_restore",
        operation_binding_sha256=plan.manifest.manifest_sha256,
    )
    changed = 0
    seen = {spec.object_id: 0 for spec in specs}
    with archive_services._ObjetCaptureManifestLock(plan.archive_root):
        rewritten: list[str] = []
        try:
            before = archive_services.archive_index_stable_file_snapshot(
                plan.archive_root,
                manifest_path,
                max_bytes=archive_services.ZETTEL_OBJET_LINK_MANIFEST_MAX_BYTES,
            )
            raw_lines = before["raw"].decode("utf-8").splitlines()
        except (OSError, UnicodeError):
            raise _fail("object_storage_restore_plan_changed") from None
        for raw_line in raw_lines:
            if not raw_line.strip():
                rewritten.append(raw_line)
                continue
            try:
                row = json.loads(raw_line)
                object_id = _object_id(row.get("object_id"))
            except Exception:
                raise _fail("object_storage_restore_plan_changed") from None
            spec = by_id.get(object_id)
            if spec is None:
                rewritten.append(raw_line)
                continue
            seen[object_id] += 1
            if object_id not in restored:
                rewritten.append(raw_line)
                continue
            locations = _locations(row)
            if any(_location_is_active_local(location, spec.local_relative) for location in locations):
                rewritten.append(raw_line)
                continue
            reactivated = False
            for location in locations:
                if (
                    location.get("provider") == "local"
                    and location.get("path") == spec.local_relative
                    and location.get("availability") == "offloaded"
                ):
                    location["availability"] = "available"
                    location.pop("offload_receipt_ref", None)
                    location.pop("offloaded_at", None)
                    location["restore_receipt_ref"] = spec.receipt_relative
                    reactivated = True
                    break
            if not reactivated:
                locations.append(
                    {
                        "provider": "local",
                        "path": spec.local_relative,
                        "availability": "available",
                        "restore_receipt_ref": spec.receipt_relative,
                    }
                )
            row["locations"] = locations
            changed += 1
            rewritten.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
        if any(value != 1 for value in seen.values()):
            raise _fail("object_storage_restore_plan_changed")
        if not changed:
            _write_projection_marker(plan, changed=0)
            return 0
        replacement = ("\n".join(rewritten) + "\n").encode("utf-8")
        replacement_sha256 = "sha256:" + hashlib.sha256(replacement).hexdigest()
        try:
            generation, began, lease_token = archive_services.prepare_archive_manifest_index_mutation(
                plan.archive_root,
                operation_owner_sha256=owner,
                expected_pre_manifest_sha256=before["file_sha256"],
                expected_post_manifest_sha256=replacement_sha256,
            )
        except archive_services.ArchiveServiceError:
            raise _fail("archive_index_rebuild_required") from None
        lifecycle.generation = generation
        lifecycle.lease_token = lease_token
        lifecycle.resumed = lifecycle.resumed or not began
        try:
            archive_services._replace_regular_file_bytes_compare_and_swap(
                plan.archive_root,
                manifest_path,
                expected_bytes=before["raw"],
                replacement_bytes=replacement,
                transaction_sha256=owner,
                swap_suffix=".object-storage-restore-manifest.swap",
                max_bytes=archive_services.ZETTEL_OBJET_LINK_MANIFEST_MAX_BYTES,
                error_prefix="object_storage_restore",
            )
        except Exception:
            try:
                observed = manifest_path.read_bytes()
            except OSError:
                observed = None
            if observed == replacement:
                pass
            elif observed == before["raw"]:
                archive_services.replace_archive_index_manifest_projection(
                    plan.archive_root,
                    expected_generation=generation,
                    expected_manifest_sha256=before["file_sha256"],
                    expected_mutation_owner_sha256=owner,
                    lease_token=lease_token,
                )
                raise
            else:
                archive_services.mark_archive_index_dirty(
                    plan.archive_root,
                    expected_generation=generation,
                    expected_mutation_owner_sha256=owner,
                    lease_token=lease_token,
                )
                raise _fail("archive_index_rebuild_required") from None
        updated = archive_services.replace_archive_index_manifest_projection(
            plan.archive_root,
            expected_generation=generation,
            expected_manifest_sha256=replacement_sha256,
            expected_mutation_owner_sha256=owner,
            lease_token=lease_token,
        )
        if not updated:
            archive_services.mark_archive_index_dirty(
                plan.archive_root,
                expected_generation=generation,
                expected_mutation_owner_sha256=owner,
                lease_token=lease_token,
            )
            raise _fail("archive_index_rebuild_required")
        lifecycle.updated = True
        _write_projection_marker(plan, changed=changed)
        return changed


def _reseal_dirty_projection(plan: ObjectStorageRestorePlan, lifecycle: _ManifestIndexLifecycle) -> None:
    """Resume the one honest partial state: the manifest already holds its post
    state while the generated index stayed same-generation dirty (a crash
    between the compare-and-swap and the projection)."""

    if plan.manifest is None:
        raise _fail("object_storage_restore_no_writes")
    manifest_path = archive_services.archive_internal_path(plan.archive_root, "objects/manifests/files.jsonl")
    owner = archive_services.archive_manifest_mutation_owner_sha256(
        operation="object_storage_bytes_restore",
        operation_binding_sha256=plan.manifest.manifest_sha256,
    )
    try:
        snapshot = archive_services.archive_index_stable_file_snapshot(
            plan.archive_root, manifest_path, max_bytes=archive_services.ZETTEL_OBJET_LINK_MANIFEST_MAX_BYTES
        )
        generation, began, lease_token = archive_services.prepare_archive_manifest_index_mutation(
            plan.archive_root,
            operation_owner_sha256=owner,
            expected_pre_manifest_sha256=snapshot["file_sha256"],
            expected_post_manifest_sha256=snapshot["file_sha256"],
        )
    except (archive_services.ArchiveServiceError, OSError):
        raise _fail("archive_index_rebuild_required") from None
    if began or not archive_services.replace_archive_index_manifest_projection(
        plan.archive_root,
        expected_generation=generation,
        expected_manifest_sha256=snapshot["file_sha256"],
        expected_mutation_owner_sha256=owner,
        lease_token=lease_token,
    ):
        archive_services.mark_archive_index_dirty(
            plan.archive_root,
            expected_generation=generation,
            expected_mutation_owner_sha256=owner,
            lease_token=lease_token,
        )
        raise _fail("archive_index_rebuild_required")
    lifecycle.generation = generation
    lifecycle.lease_token = lease_token
    lifecycle.updated = True
    lifecycle.resumed = True


# --- exact operation adapters -------------------------------------------------


class _Payloads:
    def __init__(self, plan: ObjectStorageRestorePlan) -> None:
        self.values: dict[tuple[str, str], tuple[bytes | None, bytes, bytes]] = {}
        if plan.manifest is None:
            return
        for item, spec in zip(plan.manifest.items, plan.specs):
            self.values[(item.item_id, "remote_bytes_restoration")] = (
                None,
                spec.receipt_token,
                spec.source_token,
            )
        if plan.batch_specs:
            item = plan.manifest.items[-1]
            self.values[(item.item_id, "local_locations")] = (
                None,
                _manifest_batch_token(plan.batch_specs),
                _manifest_source_token(plan.batch_specs),
            )

    def field_value(self, *, item_id: str, field_ref: str, state: str, heartbeat: Callable[[], None]) -> bytes | None:
        heartbeat()
        values = self.values.get((item_id, field_ref))
        if values is None or state not in {"pre", "post", "source"}:
            raise ValueError("payload boundary")
        return values[{"pre": 0, "post": 1, "source": 2}[state]]


class _Verifier:
    def __init__(self, plan: ObjectStorageRestorePlan) -> None:
        self.plan = plan
        self.by_target = {spec.receipt_relative: spec for spec in plan.specs}
        _rows, self.groups = preservation._read_manifest_groups(plan.archive_root, progress=None)

    def target_identity_sha256(self, *, target_kind: str, target_ref: str, heartbeat: Callable[[], None]) -> str:
        heartbeat()
        if target_kind == "object_storage_restore_receipt":
            spec = self.by_target.get(target_ref)
            if spec is None:
                raise ValueError("target boundary")
            group = self.groups.get(spec.object_id)
            if not group or _source_token(
                object_id=spec.object_id,
                rows=group,
                remote_key=spec.remote_key,
                mode=self.plan.mode,
                remote_source_kind=spec.remote_source_kind,
            ) != spec.source_token:
                raise ValueError("source drift")
            return spec.target_identity_sha256
        if target_kind == "object_storage_restore_manifest_batch" and target_ref == MANIFEST_TARGET_REF:
            source = _manifest_source_token(self.plan.batch_specs)
            return _sha(
                {
                    "archive_id": self.plan.archive_id,
                    "target_ref": MANIFEST_TARGET_REF,
                    "source_sha256": _sha_bytes(source),
                }
            )
        raise ValueError("target boundary")

    def read_field(self, *, target_kind: str, target_ref: str, field_ref: str, heartbeat: Callable[[], None]) -> bytes | None:
        if target_kind == "object_storage_restore_receipt":
            spec = self.by_target.get(target_ref)
            if spec is None or field_ref != "remote_bytes_restoration":
                raise ValueError("read boundary")
            receipt = _read_receipt(self.plan, spec)
            if receipt is None:
                return None
            if receipt["restore_status"] in {STATUS_BYTES_RESTORED, STATUS_ALREADY_PRESENT}:
                # Independent proof: the canonical bytes are on disk and match.
                state = _destination_state(
                    self.plan.archive_root, spec.object_id, spec.size_bytes, heartbeat=heartbeat
                )
                if state != "present_verified":
                    raise ValueError("local bytes drifted")
            return spec.receipt_token
        if (
            target_kind == "object_storage_restore_manifest_batch"
            and target_ref == MANIFEST_TARGET_REF
            and field_ref == "local_locations"
        ):
            return _batch_state(self.plan)
        raise ValueError("read boundary")


class _Writer:
    def __init__(self, plan: ObjectStorageRestorePlan, transport: archive_services.ObjectStorageTransport) -> None:
        self.plan = plan
        self.transport = transport
        self.by_target = {spec.receipt_relative: spec for spec in plan.specs}
        self.status_counts: dict[str, int] = {status: 0 for status in sorted(_TERMINAL_STATUSES)}
        self.provider_get_count = 0
        self.receipts_created_count = 0
        self.manifest_update_count = 0
        self.manifest_index_lifecycle = _ManifestIndexLifecycle()

    def write_field(self, *, target_kind: str, target_ref: str, field_ref: str, value: bytes | None, heartbeat: Callable[[], None]) -> None:
        if target_kind == "object_storage_restore_receipt":
            spec = self.by_target.get(target_ref)
            if spec is None or field_ref != "remote_bytes_restoration":
                raise ValueError("write boundary")
            if value is None:
                # Revert direction is not offered: receipts and restored bytes stay.
                raise ValueError("write boundary")
            if value != spec.receipt_token:
                raise ValueError("write boundary")
            existing = _read_receipt(self.plan, spec)
            if existing is not None:
                return
            restore_status, remote_state, review_reason = _fetch_and_promote(
                self.plan, spec, self.transport, heartbeat=heartbeat
            )
            if remote_state != "not_queried":
                self.provider_get_count += 1
            _create_receipt(
                self.plan,
                spec,
                restore_status=restore_status,
                remote_state=remote_state,
                review_reason=review_reason,
            )
            self.receipts_created_count += 1
            self.status_counts[restore_status] += 1
            return
        if (
            target_kind == "object_storage_restore_manifest_batch"
            and target_ref == MANIFEST_TARGET_REF
            and field_ref == "local_locations"
        ):
            expected = _manifest_batch_token(self.plan.batch_specs)
            if value != expected:
                raise ValueError("write boundary")
            self.manifest_update_count += _apply_manifest_batch(
                self.plan, lifecycle=self.manifest_index_lifecycle
            )
            return
        raise ValueError("write boundary")


# --- approval binding, control, execution ------------------------------------


def _approval_binding(plan: ObjectStorageRestorePlan) -> ExactOperationApprovalBinding:
    if plan.manifest is None:
        raise _fail("object_storage_restore_no_writes")
    try:
        return exact_operation_manifest_approval_binding(
            plan.manifest,
            operation=ExactHumanApprovalOperation.object_storage_bytes_restore,
            archive_id=plan.archive_id,
            warnings=(
                "remote_object_is_never_deleted",
                "existing_local_file_is_never_overwritten",
                "review_required_objects_keep_no_local_location",
            ),
        )
    except Exception:
        raise _fail("object_storage_restore_plan_invalid") from None


def object_storage_restore_context(
    plan: ObjectStorageRestorePlan, *, reviewer_claim: str
) -> ExactHumanApprovalContext:
    reviewer = str(reviewer_claim or "").strip()
    if not reviewer or not plan.approveable:
        raise _fail("object_storage_restore_plan_invalid")
    return _approval_binding(plan).context(archive_id=plan.archive_id, reviewer_claim=reviewer)


def _assert_approved(
    plan: ObjectStorageRestorePlan,
    claim: _ClaimedExactHumanApproval,
    context: ExactHumanApprovalContext,
) -> ExactOperationApprovalAuthority:
    binding = _approval_binding(plan)
    if (
        type(claim) is not _ClaimedExactHumanApproval
        or context.operation is not ExactHumanApprovalOperation.object_storage_bytes_restore
        or context.plan_sha256 != binding.plan_sha256
        or context.target_binding_sha256 != binding.target_binding_sha256
    ):
        raise _fail("object_storage_restore_approval_required")
    try:
        reference = _ClaimedExactHumanApproval.assert_ready_for_context(claim, context)
        return ExactOperationApprovalAuthority.from_reference(reference)
    except (ExactHumanApprovalError, ExactOperationManifestError):
        raise _fail("object_storage_restore_approval_required") from None


def _control_relative(manifest_sha256: str) -> str:
    if _SHA256_RE.fullmatch(str(manifest_sha256 or "")) is None:
        raise _fail("object_storage_restore_control_invalid")
    return f"{CONTROL_ROOT}/{manifest_sha256.removeprefix('sha256:')}.object-storage-restore.json"


def _control_document(plan: ObjectStorageRestorePlan) -> dict[str, Any]:
    if plan.manifest is None:
        raise _fail("object_storage_restore_no_writes")
    basis = {
        "schema_version": CONTROL_SCHEMA,
        "archive_id": plan.archive_id,
        "provider_kind": plan.provider_kind,
        "store_ref": plan.store_ref,
        "mode": plan.mode,
        "source_inventory_sha256": plan.source_inventory_sha256,
        "counts": {str(key): int(value) for key, value in plan.counts.items()},
        "selected_only": plan.selected_only,
        "manifest": plan.manifest.document(),
        "specs": [
            {
                "object_id": spec.object_id,
                "size_bytes": spec.size_bytes,
                "remote_key": spec.remote_key,
                "remote_source_kind": spec.remote_source_kind,
                "local_relative": spec.local_relative,
                "local_location_state": spec.local_location_state,
                "receipt_relative": spec.receipt_relative,
                "receipt_token_sha256": _sha_bytes(spec.receipt_token),
                "source_token_sha256": _sha_bytes(spec.source_token),
                "target_identity_sha256": spec.target_identity_sha256,
            }
            for spec in plan.specs
        ],
        "private_control_document": True,
    }
    return {**basis, "control_sha256": _sha(basis)}


def _persist_control(plan: ObjectStorageRestorePlan) -> str:
    if plan.manifest is None:
        raise _fail("object_storage_restore_no_writes")
    relative = _control_relative(plan.manifest.manifest_sha256)
    preservation._create_or_match_receipt(
        plan.archive_root,
        relative,
        preservation._canonical_control_bytes(_control_document(plan)),
        max_bytes=_MAX_CONTROL_BYTES,
        failure_code="object_storage_restore_control_invalid",
    )
    return relative


def load_object_storage_restore_plan(
    archive_root: Path | str, *, manifest_sha256: str
) -> ObjectStorageRestorePlan:
    try:
        root = archive_services.require_existing_archive_root(archive_root)
        archive_id = archive_services.read_archive_id(root)
        path = archive_services.archive_internal_path(root, _control_relative(manifest_sha256))
        raw = path.read_bytes()
        if len(raw) > _MAX_CONTROL_BYTES:
            raise ValueError("large")
        document = preservation._strict_json(raw)
    except ObjectStorageRestoreError:
        raise
    except Exception:
        raise _fail("object_storage_restore_control_invalid") from None
    supplied = document.pop("control_sha256", None)
    if (
        document.get("schema_version") != CONTROL_SCHEMA
        or document.get("private_control_document") is not True
        or not isinstance(supplied, str)
        or not hmac.compare_digest(supplied, _sha(document))
        or document.get("archive_id") != archive_id
    ):
        raise _fail("object_storage_restore_control_invalid")
    try:
        manifest = ExactOperationManifest.from_document(document["manifest"])
        provider = document["provider_kind"]
        store = document["store_ref"]
        mode = document["mode"]
        inventory_sha = document["source_inventory_sha256"]
        counts = document["counts"]
        raw_specs = document["specs"]
        selected_only = document.get("selected_only")
        _rows, groups = preservation._read_manifest_groups(root, progress=None)
    except Exception:
        raise _fail("object_storage_restore_control_invalid") from None
    if (
        manifest.manifest_sha256 != manifest_sha256
        or manifest.operation != OPERATION
        or provider not in archive_services.OBJECT_STORAGE_ALLOWED_PROVIDERS
        or not archive_services.safe_object_storage_ref(store)
        or mode not in MODES
        or _SHA256_RE.fullmatch(str(inventory_sha)) is None
        or not isinstance(counts, dict)
        or not isinstance(raw_specs, list)
        or (selected_only is not None and _object_id(selected_only) != selected_only)
    ):
        raise _fail("object_storage_restore_control_invalid")
    _require_setup_evidence(root, provider_kind=provider, store_ref=store)
    specs: list[RestoreSpec] = []
    for raw_spec in raw_specs:
        try:
            object_id = _object_id(raw_spec["object_id"])
            remote_key = raw_spec["remote_key"]
            remote_source_kind = raw_spec["remote_source_kind"]
            size = raw_spec["size_bytes"]
            local_relative = raw_spec["local_relative"]
            local_state = raw_spec["local_location_state"]
            receipt_relative = raw_spec["receipt_relative"]
            group = groups[object_id]
        except Exception:
            raise _fail("object_storage_restore_control_invalid") from None
        if (
            type(remote_key) is not str
            or not archive_services.safe_object_storage_remote_key(remote_key)
            or type(size) is not int
            or {row.get("size_bytes") for row in group} != {size}
            or local_relative != _logical_key(object_id)
            or local_state not in _LOCAL_STATES
            or remote_source_kind not in _REMOTE_SOURCES
        ):
            raise _fail("object_storage_restore_control_invalid")
        source_token = _source_token(
            object_id=object_id,
            rows=group,
            remote_key=remote_key,
            mode=mode,
            remote_source_kind=remote_source_kind,
        )
        receipt_token = _receipt_token(
            object_id=object_id,
            size_bytes=size,
            provider_kind=provider,
            store_ref=store,
            remote_key=remote_key,
            mode=mode,
            source_inventory_sha256=inventory_sha,
        )
        identity = _target_identity(
            archive_id=archive_id,
            object_id=object_id,
            receipt_relative=receipt_relative,
            source_token=source_token,
        )
        if (
            receipt_relative != _receipt_relative(object_id, inventory_sha)
            or raw_spec.get("receipt_token_sha256") != _sha_bytes(receipt_token)
            or raw_spec.get("source_token_sha256") != _sha_bytes(source_token)
            or raw_spec.get("target_identity_sha256") != identity
        ):
            raise _fail("object_storage_restore_plan_changed")
        specs.append(
            RestoreSpec(
                object_id=object_id,
                size_bytes=size,
                remote_key=remote_key,
                remote_source_kind=remote_source_kind,
                local_relative=local_relative,
                local_location_state=local_state,
                receipt_relative=receipt_relative,
                receipt_token=receipt_token,
                source_token=source_token,
                target_identity_sha256=identity,
            )
        )
    rebuilt = _manifest_for_specs(archive_id, specs, mode=mode)
    if rebuilt is None or rebuilt.document() != manifest.document():
        raise _fail("object_storage_restore_control_invalid")
    return ObjectStorageRestorePlan(
        archive_root=root,
        archive_id=archive_id,
        provider_kind=provider,
        store_ref=store,
        mode=mode,
        source_inventory_sha256=inventory_sha,
        manifest=manifest,
        specs=tuple(specs),
        counts={str(key): int(value) for key, value in counts.items()},
        selected_only=selected_only,
        loaded_from_control=True,
    )


def _fresh_revalidated(plan: ObjectStorageRestorePlan) -> ObjectStorageRestorePlan:
    _require_setup_evidence(plan.archive_root, provider_kind=plan.provider_kind, store_ref=plan.store_ref)
    if plan.loaded_from_control:
        return plan
    if plan.manifest is None:
        raise _fail("object_storage_restore_plan_changed")
    current = _build_plan(
        plan.archive_root,
        provider_kind=plan.provider_kind,
        store_ref=plan.store_ref,
        mode=plan.mode,
        only=plan.selected_only,
        max_objects=None,
        progress=None,
    )
    if current.manifest is None or current.manifest.document() != plan.manifest.document():
        raise _fail("object_storage_restore_plan_changed")
    return current


def _result_document(plan: ObjectStorageRestorePlan, core: Mapping[str, Any], writer: _Writer) -> dict[str, Any]:
    completed = core.get("status") == "completed"
    return {
        "schema_version": RESULT_SCHEMA,
        "ok": completed,
        "state": (
            ("restore_completed" if plan.mode == MODE_RESTORE else "remote_verification_completed")
            if completed
            else "restore_incomplete"
        ),
        "mode": plan.mode,
        "manifest_sha256": plan.manifest.manifest_sha256 if plan.manifest else None,
        "execution": dict(core),
        "planned_object_count": len(plan.specs),
        "receipts_created_count": writer.receipts_created_count,
        "provider_get_call_count": writer.provider_get_count,
        "status_counts": dict(writer.status_counts),
        "manifest_location_updates": writer.manifest_update_count,
        "generated_index_updated": writer.manifest_index_lifecycle.updated,
        "index_generation": writer.manifest_index_lifecycle.generation,
        "index_mutation_resumed": writer.manifest_index_lifecycle.resumed,
        "central_manifest_rewrite_count_ceiling": 1,
        "remote_delete_performed": False,
        "local_overwrite_performed": False,
        "provider_put_called": False,
        "private_values_echoed": False,
        "remote_keys_echoed": False,
        "object_ids_echoed": False,
        "local_paths_echoed": False,
    }


def _apply_with_store(
    plan: ObjectStorageRestorePlan,
    authority: ExactOperationApprovalAuthority,
    transport: archive_services.ObjectStorageTransport,
    checkpoints: FileExactOperationCheckpointStore,
    *,
    resume: bool,
    progress_hook: Callable[[ExactOperationProgress], None] | None,
) -> dict[str, Any]:
    if plan.manifest is None:
        raise _fail("object_storage_restore_no_writes")
    _require_manifest_index_authority(plan)
    payloads = _Payloads(plan)
    writer = _Writer(plan, transport)
    verifier = _Verifier(plan)
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
    if plan.batch_specs and core.get("status") == "completed":
        evidence = archive_services.require_current_zettel_index(plan.archive_root)
        if not evidence.get("ok") and "archive_index_dirty" in set(evidence.get("reason_codes") or []):
            _reseal_dirty_projection(plan, writer.manifest_index_lifecycle)
            evidence = archive_services.require_current_zettel_index(plan.archive_root)
        if not evidence.get("ok"):
            raise _fail("archive_index_rebuild_required")
    return _result_document(plan, core, writer)


def _apply_core(
    plan: ObjectStorageRestorePlan,
    claim: _ClaimedExactHumanApproval,
    *,
    context: ExactHumanApprovalContext,
    transport_factory: Callable[[], archive_services.ObjectStorageTransport],
    resume: bool = False,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
) -> dict[str, Any]:
    current = _fresh_revalidated(plan)
    _require_manifest_index_authority(current)
    authority = _assert_approved(current, claim, context)
    with exact_operation_writer_lock(current.archive_root) as writer_lock:
        _persist_control(current)
        checkpoints = FileExactOperationCheckpointStore(current.archive_root, writer_lock=writer_lock)
        try:
            transport = transport_factory()
        except Exception:
            raise _fail("object_storage_restore_remote_unavailable") from None
        if transport is None:
            raise _fail("object_storage_restore_remote_unavailable")
        return _apply_with_store(
            current, authority, transport, checkpoints, resume=resume, progress_hook=progress_hook
        )


def _target_collection(plan: ObjectStorageRestorePlan) -> TargetCollectionPreview | None:
    """Count-first objet list for the dialog; identities only, no key or path."""

    try:
        items = tuple(
            TargetCollectionItem(identity_sha256=spec.object_id, kind="objet") for spec in plan.specs
        )
        return TargetCollectionPreview(items=items) if items else None
    except ValueError:
        return None


def execute_object_storage_restore(
    plan: ObjectStorageRestorePlan,
    *,
    reviewer_claim: str,
    transport_factory: Callable[[], archive_services.ObjectStorageTransport],
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
) -> dict[str, Any]:
    if not plan.approveable:
        raise _fail("object_storage_restore_no_writes")
    context = object_storage_restore_context(plan, reviewer_claim=reviewer_claim)
    collection = _target_collection(plan)

    def observe_target_binding() -> str:
        # Re-derive the binding from the live archive while the dialog is open;
        # any drift (or a plan that no longer rebuilds) reads as a mismatch.
        try:
            return _approval_binding(_fresh_revalidated(plan)).target_binding_sha256
        except Exception:
            return "sha256:" + "0" * 64

    return _execute_exact_human_approved_write(
        plan.archive_root,
        context,
        lambda claim: _apply_core(
            plan, claim, context=context, transport_factory=transport_factory, progress_hook=progress_hook
        ),
        target_collection=collection,
        observe_target_binding=observe_target_binding if collection is not None else None,
    )


def resume_object_storage_restore(
    plan: ObjectStorageRestorePlan,
    *,
    reviewer_claim: str,
    approval_id: str,
    execution_sha256: str,
    transport_factory: Callable[[], archive_services.ObjectStorageTransport],
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
    key_provider: Any = None,
) -> dict[str, Any]:
    if (
        not plan.loaded_from_control
        or plan.manifest is None
        or _SHA256_RE.fullmatch(str(execution_sha256 or "")) is None
    ):
        raise _fail("object_storage_restore_resume_invalid")
    _require_manifest_index_authority(plan)
    context = object_storage_restore_context(plan, reviewer_claim=reviewer_claim)
    with exact_operation_writer_lock(plan.archive_root) as writer_lock:
        checkpoints = FileExactOperationCheckpointStore(plan.archive_root, writer_lock=writer_lock)

        def writer(claim: _ClaimedExactHumanApproval) -> Mapping[str, Any]:
            current = _fresh_revalidated(plan)
            authority = _assert_approved(current, claim, context)
            actual = exact_operation_execution_sha256(current.manifest, approval_authority=authority)
            if not hmac.compare_digest(actual, execution_sha256):
                raise _fail("object_storage_restore_resume_invalid")
            try:
                transport = transport_factory()
            except Exception:
                raise _fail("object_storage_restore_remote_unavailable") from None
            return _apply_with_store(
                current, authority, transport, checkpoints, resume=True, progress_hook=progress_hook
            )

        return _resume_exact_human_approved_write_core(
            plan.archive_root,
            context,
            approval_id,
            lambda _claim: checkpoints.resume_checkpoint_present(execution_sha256),
            writer,
            key_provider=key_provider,
        )


def verify_object_storage_restore(
    plan: ObjectStorageRestorePlan,
    *,
    heartbeat: Callable[[], None] | None = None,
) -> dict[str, Any]:
    if type(plan) is not ObjectStorageRestorePlan or plan.manifest is None:
        raise _fail("object_storage_restore_plan_invalid")
    result = verify_exact_operation(
        plan.manifest,
        verifier=_Verifier(plan),
        state="post",
        heartbeat=heartbeat,
    )
    return {
        "schema_version": VERIFY_SCHEMA,
        "ok": result["all_match"],
        "mode": plan.mode,
        "manifest_sha256": plan.manifest.manifest_sha256,
        "verified_item_count": len(plan.manifest.items) if result["all_match"] else 0,
        "verification": result,
        "provider_api_called": False,
        "writes_performed": False,
        "private_values_echoed": False,
        "remote_keys_echoed": False,
    }


__all__ = [
    "MODE_RESTORE",
    "MODE_VERIFY_ONLY",
    "ObjectStorageRestoreError",
    "ObjectStorageRestorePlan",
    "RestoreSpec",
    "execute_object_storage_restore",
    "load_object_storage_restore_plan",
    "object_storage_restore_context",
    "plan_object_storage_restore",
    "resume_object_storage_restore",
    "verify_object_storage_restore",
]
