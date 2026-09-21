"""Exact, resumable offload of local Objet bytes after a same-run remote proof.

v0.4.29 answers acceptance row OB-02 ("one approved eligible retention batch
offloads with journal/tombstone/receipt and survives every interruption") on
top of the v0.4.28 restore: the way back exists, so the way out may now.

Decision 6 (2026-09-04) and decisions 9 and 10 (2026-09-19) govern:

- a local file is removed only after a full authenticated GET in the same run
  streams the remote body and reproduces the object id (size and sha256), the
  local bytes re-hash to the object id, the path chain has no reparse point,
  no unminted draft references the object or names it as its fidelity source,
  and the operator's size/age filters select it;
- the manifest row keeps its local location, flipped to ``offloaded`` with the
  receipt reference and time (the tombstone lives in the manifest, so every
  reader sees a recovery dependency, never a missing file);
- the remote object is never deleted; ``delete_object`` is unreachable here;
- a proof marker written before the unlink is the per-object journal: a crash
  between the unlink and the receipt is recovered from the marker on resume
  without a second download, and a marker without an unlink is discarded.

Restore (v0.4.28) reactivates an offloaded location; the two writers share the
receipt, control, sink and manifest-projection machinery.
"""

from __future__ import annotations

from .object_storage_scope import ObjectScope, ObjectStorageScopeError, resolve_scope, validate_scope

import hashlib
import hmac
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence

from . import archive_services
from . import object_storage_preservation as preservation
from . import object_storage_restore as restore
from .legacy_cleanup_bound_delete import LegacyCleanupBoundDeleteError, _delete_exact_approved_file
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
from .target_collection_preview import TargetCollectionItem, TargetCollectionPreview


PLAN_SCHEMA = "wom-kit/object-storage-offload-plan/v0.1"
CONTROL_SCHEMA = "wom-kit/object-storage-offload-control/v0.1"
RECEIPT_SCHEMA = "wom-kit/object-storage-offload-receipt/v0.1"
RESULT_SCHEMA = "wom-kit/object-storage-offload-result/v0.1"
VERIFY_SCHEMA = "wom-kit/object-storage-offload-verification/v0.1"
MARKER_SCHEMA = "wom-kit/object-storage-offload-proof-marker/v0.1"
OPERATION = ExactHumanApprovalOperation.object_storage_bytes_offload.value
RECEIPT_ROOT = "receipts/providers/object-storage-offload"
CONTROL_ROOT = "profiles/local/exact-operations/manifests"
MARKER_ROOT = "profiles/local/exact-operations/offload-proofs"
MANIFEST_TARGET_REF = "objects/manifests/files.jsonl#offload-local-location-batch"

STATUS_BYTES_OFFLOADED = "bytes_offloaded"
STATUS_REVIEW_REQUIRED = "review_required"
_TERMINAL_STATUSES = frozenset({STATUS_BYTES_OFFLOADED, STATUS_REVIEW_REQUIRED})
_REVIEW_REASONS = frozenset(
    {"remote_absent", "remote_size_mismatch", "remote_checksum_mismatch"}
)
DEFAULT_MIN_AGE_DAYS = 30
DEFAULT_MIN_SIZE_BYTES = 0
# Only originals captured by WOM's own intake are offload candidates. Snapshot
# writers (zet revision / title remap / activity-group before-snapshots) and
# provider recoveries append a fresh manifest record when they see no
# available local location, so their objects stay local.
OFFLOADABLE_PROVENANCE_SOURCES = frozenset(
    {"b4_local_objet_capture", "tiro_lossless_recovery_bundle_capture"}
)

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_MAX_RECEIPT_BYTES = 64 * 1024
_MAX_CONTROL_BYTES = 64 * 1024 * 1024
_MAX_DRAFT_BYTES = 8 * 1024 * 1024
_MAX_FIDELITY_RECEIPT_BYTES = 1024 * 1024


class ObjectStorageOffloadError(RuntimeError):
    """Fixed-code failure; the code never carries a path, key or label."""

    CODES = frozenset(
        {
            "object_storage_offload_archive_invalid",
            "object_storage_offload_plan_invalid",
            "object_storage_offload_plan_changed",
            "object_storage_offload_no_writes",
            "object_storage_offload_setup_evidence_missing",
            "object_storage_offload_setup_evidence_mismatch",
            "object_storage_offload_approval_required",
            "object_storage_offload_control_invalid",
            "object_storage_offload_resume_invalid",
            "object_storage_offload_receipt_conflict",
            "object_storage_offload_remote_unavailable",
            "object_storage_offload_local_conflict",
            "object_storage_offload_local_write_failed",
            "object_storage_offload_retention_evidence_unreadable",
            "object_storage_offload_platform_unsupported",
            "archive_index_rebuild_required",
        }
    )

    def __init__(self, code: str) -> None:
        if code not in self.CODES:
            code = "object_storage_offload_plan_invalid"
        super().__init__(code)
        self.code = code

    def __repr__(self) -> str:
        return f"ObjectStorageOffloadError({self.code!r})"


def _fail(code: str) -> ObjectStorageOffloadError:
    return ObjectStorageOffloadError(code)


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise _fail("object_storage_offload_plan_invalid") from None


def _sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _sha_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


# --- retention evidence --------------------------------------------------------


@dataclass(frozen=True)
class RetentionEvidence:
    """Object ids an unminted draft still depends on; content-free."""

    referenced: frozenset[str]
    fidelity_sources: frozenset[str]
    draft_count: int
    unreadable_draft_count: int
    unreadable_fidelity_receipt_count: int


def _draft_retention_evidence(root: Path) -> RetentionEvidence:
    """Scan every inbox draft once for objet references and fidelity sources.

    Every inbox draft counts as unminted (conservative: a minted twin still
    references its objects harmlessly). A draft that cannot be read, or whose
    private fidelity receipt cannot be read, is counted so the plan can refuse
    to offload anything it cannot prove unreferenced.
    """

    referenced: set[str] = set()
    fidelity: set[str] = set()
    draft_count = 0
    unreadable = 0
    unreadable_receipts = 0
    inbox = root / "inbox"
    if inbox.is_dir():
        try:
            paths = archive_services.safe_archive_glob(inbox, "*.md", root, recursive=True)
        except Exception:
            paths = []
            unreadable += 1
        for path in paths:
            draft_count += 1
            try:
                if path.stat().st_size > _MAX_DRAFT_BYTES:
                    unreadable += 1
                    continue
                boundary = archive_services.read_zettel_content_boundary(path)
            except Exception:
                unreadable += 1
                continue
            if boundary.get("state") != "readable":
                unreadable += 1
                continue
            frontmatter = boundary.get("frontmatter") if isinstance(boundary.get("frontmatter"), dict) else {}
            body = boundary.get("body") if isinstance(boundary.get("body"), str) else ""
            try:
                occurrences = archive_services.objet_ref_occurrences_in_text(body, source="body")
                occurrences += archive_services.objet_ref_occurrences_in_value(frontmatter, field="frontmatter")
            except Exception:
                unreadable += 1
                continue
            for item in occurrences:
                object_id = item.get("object_id") if isinstance(item, dict) else None
                if isinstance(object_id, str) and _SHA256_RE.fullmatch(object_id):
                    referenced.add(object_id)
            projection = frontmatter.get("source_fidelity")
            if not isinstance(projection, dict):
                continue
            plan_sha256 = str(projection.get("creation_plan_sha256") or "").strip().lower()
            if archive_services.SHA256_RE.fullmatch(plan_sha256) is None:
                unreadable_receipts += 1
                continue
            receipt_path = root.joinpath(
                *PurePosixPath(f"{archive_services.SOURCE_FIDELITY_DRAFT_RECEIPTS_DIR}/{plan_sha256}.json").parts
            )
            try:
                raw = receipt_path.read_bytes()
                if len(raw) > _MAX_FIDELITY_RECEIPT_BYTES:
                    raise ValueError("large")
                receipt = preservation._strict_json(raw)
                source = receipt["source_fidelity"]["source"]
                object_id = str(source["object_id"]).lower()
                if not _SHA256_RE.fullmatch(object_id):
                    raise ValueError("object id")
            except Exception:
                unreadable_receipts += 1
                continue
            fidelity.add(object_id)
    return RetentionEvidence(
        referenced=frozenset(referenced),
        fidelity_sources=frozenset(fidelity),
        draft_count=draft_count,
        unreadable_draft_count=unreadable,
        unreadable_fidelity_receipt_count=unreadable_receipts,
    )


# --- plan --------------------------------------------------------------------------


def _receipt_relative(object_id: str, source_inventory_sha256: str) -> str:
    digest = object_id.removeprefix("sha256:")
    inventory = source_inventory_sha256.removeprefix("sha256:")
    return f"{RECEIPT_ROOT}/{digest}.{inventory[:16]}.json"


def _source_token(
    *, object_id: str, rows: Sequence[Mapping[str, Any]], remote_key: str, remote_source_kind: str
) -> bytes:
    projection = []
    for row in rows:
        projection.append(
            {
                "object_id": restore._object_id(row.get("object_id")),
                "sha256": restore._object_id(row.get("sha256")),
                "size_bytes": row.get("size_bytes"),
                "logical_key_sha256": _sha(row.get("logical_key")),
                "remote_locations_sha256": _sha(
                    [location for location in restore._locations(row) if location.get("provider") == "object_storage"]
                ),
            }
        )
    return _canonical(
        {
            "schema_version": "wom-kit/object-storage-offload-source/v0.1",
            "object_id": object_id,
            "rows": projection,
            "remote_key_sha256": _sha(remote_key),
            "remote_source_kind": remote_source_kind,
        }
    )


def _receipt_token(
    *, object_id: str, size_bytes: int, provider_kind: str, store_ref: str, remote_key: str, source_inventory_sha256: str
) -> bytes:
    return _canonical(
        {
            "schema_version": "wom-kit/object-storage-offload-state/v0.1",
            "object_id": object_id,
            "size_bytes": size_bytes,
            "provider_kind": provider_kind,
            "store_ref": store_ref,
            "remote_key_sha256": _sha(remote_key),
            "source_inventory_sha256": source_inventory_sha256,
            "remote_verification": "get_rehash_whole_object_same_run",
            "terminal_statuses": sorted(_TERMINAL_STATUSES),
        }
    )


def _target_identity(*, archive_id: str, object_id: str, receipt_relative: str, source_token: bytes) -> str:
    return _sha(
        {
            "schema_version": "wom-kit/object-storage-offload-target/v0.1",
            "archive_id": archive_id,
            "object_id": object_id,
            "receipt_relative": receipt_relative,
            "source_token_sha256": _sha_bytes(source_token),
        }
    )


@dataclass(frozen=True, repr=False)
class OffloadSpec:
    object_id: str
    size_bytes: int
    remote_key: str
    remote_source_kind: str
    local_relative: str
    receipt_relative: str
    receipt_token: bytes
    source_token: bytes
    target_identity_sha256: str


def _manifest_batch_token(specs: Sequence[OffloadSpec]) -> bytes:
    return _canonical(
        {
            "schema_version": "wom-kit/object-storage-offload-location-batch/v0.1",
            "locations": [
                {
                    "object_id": spec.object_id,
                    "local_relative": spec.local_relative,
                    "receipt_relative": spec.receipt_relative,
                    "size_bytes": spec.size_bytes,
                }
                for spec in sorted(specs, key=lambda item: item.object_id)
            ],
        }
    )


def _manifest_source_token(specs: Sequence[OffloadSpec]) -> bytes:
    return _canonical(
        {
            "schema_version": "wom-kit/object-storage-offload-manifest-source/v0.1",
            "source_tokens": [_sha_bytes(item.source_token) for item in specs],
        }
    )


def _manifest_for_specs(archive_id: str, specs: Sequence[OffloadSpec], scope: ObjectScope | None = None) -> ExactOperationManifest | None:
    items: list[ExactOperationItem] = []
    for ordinal, spec in enumerate(specs):
        items.append(
            ExactOperationItem(
                ordinal=ordinal,
                item_id="item:" + hashlib.sha256(spec.receipt_relative.encode("ascii")).hexdigest(),
                target_kind="object_storage_offload_receipt",
                target_ref=spec.receipt_relative,
                target_identity_sha256=spec.target_identity_sha256,
                fields=(
                    ExactFieldEffect(
                        field_ref="local_bytes_offload",
                        pre_sha256=hash_field_value(None),
                        post_sha256=hash_field_value(spec.receipt_token),
                        source_sha256=hash_field_value(spec.source_token),
                    ),
                ),
            )
        )
    if specs:
        source_token = _manifest_source_token(specs)
        items.append(
            ExactOperationItem(
                ordinal=len(items),
                item_id="item:" + hashlib.sha256(MANIFEST_TARGET_REF.encode("ascii")).hexdigest(),
                target_kind="object_storage_offload_manifest_batch",
                target_ref=MANIFEST_TARGET_REF,
                target_identity_sha256=_sha(
                    {"archive_id": archive_id, "target_ref": MANIFEST_TARGET_REF, "source_sha256": _sha_bytes(source_token)}
                ),
                fields=(
                    ExactFieldEffect(
                        field_ref="local_locations",
                        pre_sha256=hash_field_value(None),
                        post_sha256=hash_field_value(_manifest_batch_token(specs)),
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
        operation_evidence=scope.evidence(len(specs)) if scope is not None else None,
    )


@dataclass(frozen=True, repr=False)
class ObjectStorageOffloadPlan:
    archive_root: Path
    archive_id: str
    provider_kind: str
    store_ref: str
    source_inventory_sha256: str
    retention_sha256: str
    min_age_days: int
    min_size_bytes: int
    manifest: ExactOperationManifest | None
    specs: tuple[OffloadSpec, ...]
    counts: Mapping[str, int]
    blockers: tuple[str, ...] = ()
    selected_only: str | None = None
    scope: ObjectScope | None = None
    loaded_from_control: bool = False

    @property
    def approveable(self) -> bool:
        return self.manifest is not None and bool(self.specs) and not self.blockers

    def public_document(self) -> dict[str, Any]:
        if self.blockers:
            state = "blocked"
            reason = list(self.blockers)
        elif self.approveable:
            state = "ready_for_exact_human_approval"
            reason = ["object_storage_offload_ready"]
        else:
            state = "no_offload_targets"
            reason = ["object_storage_offload_no_writes"]
        next_actions: list[str] = []
        if self.approveable:
            next_actions.append(
                "Re-run with --approve --reviewed-by <id> --expected-manifest-sha256 <plan_sha256>; "
                "one native dialog covers every listed object; each is downloaded and re-hashed "
                "before its local file is removed, and object-storage-restore brings it back."
            )
        if self.blockers:
            next_actions.append(
                "A draft or its private fidelity receipt could not be read, so no object can be proven "
                "unreferenced; repair or discard that draft before offloading."
            )
        if int(self.counts["referenced_by_unminted_draft_count"]) or int(self.counts["fidelity_source_of_unminted_draft_count"]):
            next_actions.append(
                "Objects an unminted draft references or was created from stay local until that draft is minted or discarded."
            )
        if int(self.counts["local_bytes_absent_count"]):
            next_actions.append(
                "Objects without local bytes are not offload targets; object-storage-restore is the command for them."
            )
        return {
            "schema_version": PLAN_SCHEMA,
            **(self.scope.summary(int(self.counts.get("unique_object_count") or 0)) if self.scope else {"scope_kind": "legacy_all_sessions"}),
            "ok": self.approveable,
            "state": state,
            "reason_codes": reason,
            "plan_sha256": self.manifest.manifest_sha256 if self.manifest else None,
            "target_binding_sha256": self.manifest.target_set_sha256 if self.manifest else None,
            "source_binding_sha256": self.manifest.source_set_sha256 if self.manifest else None,
            "effect_binding_sha256": self.manifest.effect_set_sha256 if self.manifest else None,
            "source_inventory_sha256": self.source_inventory_sha256,
            "retention_evidence_sha256": self.retention_sha256,
            "min_age_days": self.min_age_days,
            "min_size_bytes": self.min_size_bytes,
            **{str(key): int(value) for key, value in self.counts.items()},
            "planned_object_count": len(self.specs),
            "planned_local_bytes_freed": sum(spec.size_bytes for spec in self.specs),
            "planned_download_bytes_for_proof": sum(spec.size_bytes for spec in self.specs),
            "manifest_rewrite_planned_count": 1 if self.specs else 0,
            "per_object_manifest_rewrite_planned_count": 0,
            "provider_get_calls_per_object": 1,
            "provider_put_call_count": 0,
            "remote_delete_supported": False,
            "manifest_location_removed": False,
            "platform_supported": os.name == "nt",
            "requires_exact_human_approval": True,
            "session_permission_mode_can_skip_dialog": False,
            "common_exact_operation_manifest_used": self.manifest is not None,
            "next_safe_actions": next_actions,
            "provider_api_called": False,
            "credential_values_read": False,
            "writes_performed": False,
            "remote_keys_echoed": False,
            "object_ids_echoed": False,
            "local_paths_echoed": False,
            "draft_content_echoed": False,
        }


def _require_setup_evidence(root: Path, *, provider_kind: str, store_ref: str) -> None:
    try:
        restore._require_setup_evidence(root, provider_kind=provider_kind, store_ref=store_ref)
    except restore.ObjectStorageRestoreError as exc:
        raise _fail(exc.code.replace("object_storage_restore_", "object_storage_offload_")) from None


def _build_plan(
    archive_root: Path | str,
    *,
    provider_kind: str,
    store_ref: str,
    only: str | None,
    scope: ObjectScope | None,
    max_objects: int | None,
    min_age_days: int,
    min_size_bytes: int,
    progress: Callable[[str, str, int | None, int | None], None] | None,
) -> ObjectStorageOffloadPlan:
    try:
        root = archive_services.require_existing_archive_root(archive_root)
        archive_id = archive_services.read_archive_id(root)
    except Exception:
        raise _fail("object_storage_offload_archive_invalid") from None
    normalized_provider = str(provider_kind or "").strip().lower()
    normalized_store = str(store_ref or "").strip()
    if (
        normalized_provider not in archive_services.OBJECT_STORAGE_ALLOWED_PROVIDERS
        or not archive_services.safe_object_storage_ref(normalized_store)
        or (max_objects is not None and (type(max_objects) is not int or max_objects < 1))
        or type(min_age_days) is not int
        or min_age_days < 0
        or type(min_size_bytes) is not int
        or min_size_bytes < 0
    ):
        raise _fail("object_storage_offload_plan_invalid")
    selected_only = restore._object_id(only) if only else None
    _require_setup_evidence(root, provider_kind=normalized_provider, store_ref=normalized_store)
    try:
        rows, groups = preservation._read_manifest_groups(root, progress=progress)
    except preservation.ObjectStoragePreservationError:
        raise _fail("object_storage_offload_plan_invalid") from None
    inventory_sha256 = restore._source_inventory_sha256(rows)
    scope = validate_scope(root, scope, groups, only)
    if progress is not None:
        progress("offload-retention", "scanning drafts", None, None)
    retention = _draft_retention_evidence(root)
    retention_sha256 = _sha(
        {
            "referenced": sorted(retention.referenced),
            "fidelity_sources": sorted(retention.fidelity_sources),
            "draft_count": retention.draft_count,
        }
    )
    now = datetime.now(timezone.utc)
    counts = {
        "manifest_row_count": len(rows),
        "unique_object_count": len(groups),
        "unminted_draft_count": retention.draft_count,
        "unreadable_draft_count": retention.unreadable_draft_count,
        "unreadable_fidelity_receipt_count": retention.unreadable_fidelity_receipt_count,
        "conflicting_definition_count": 0,
        "remote_evidence_missing_count": 0,
        "bytes_preserved_receipt_only_count": 0,
        "already_offloaded_count": 0,
        "local_identity_unavailable_count": 0,
        "local_bytes_absent_count": 0,
        "local_bytes_conflict_count": 0,
        "path_chain_unsafe_count": 0,
        "provenance_source_excluded_count": 0,
        "referenced_by_unminted_draft_count": 0,
        "fidelity_source_of_unminted_draft_count": 0,
        "below_min_size_count": 0,
        "below_min_age_count": 0,
        "captured_at_unknown_count": 0,
        "offload_target_count": 0,
        "selected_object_not_found_count": 0,
    }
    blockers: list[str] = []
    if retention.unreadable_draft_count or retention.unreadable_fidelity_receipt_count:
        blockers.append("object_storage_offload_retention_evidence_unreadable")
    if os.name != "nt":
        # The handle-bound compare-and-delete primitive is Windows-only by
        # design (legacy_cleanup_bound_delete: POSIX never mutates); a plan
        # may be inspected here but never approved.
        blockers.append("object_storage_offload_platform_unsupported")
    heartbeat = (lambda: None) if progress is None else (
        lambda: progress("offload-inventory", "hashing local bytes", None, None)
    )
    specs: list[OffloadSpec] = []
    if selected_only is not None and selected_only not in groups:
        counts["selected_object_not_found_count"] = 1
    for object_id in sorted(groups):
        if not scope.includes(object_id, destructive=True):
            continue
        if selected_only is not None and object_id != selected_only:
            continue
        group = groups[object_id]
        sizes = {row.get("size_bytes") for row in group}
        if len(sizes) != 1:
            counts["conflicting_definition_count"] += 1
            continue
        size_bytes = int(next(iter(sizes)))
        remote = None
        conflicting = False
        for row in group:
            candidate = restore._remote_location(row, provider_kind=normalized_provider, store_ref=normalized_store)
            if candidate is not None:
                if remote is not None and remote.get("remote_key") != candidate.get("remote_key"):
                    conflicting = True
                    break
                remote = candidate
        if conflicting:
            counts["conflicting_definition_count"] += 1
            continue
        # Offload removes the only local copy, so the manifest row itself must
        # carry the remote proof every reader keys on: a WOM-verified
        # wom_uploaded location. A v0.4.13 preservation receipt alone lets the
        # bytes be restored, but not offloaded.
        remote_source_kind = restore.REMOTE_SOURCE_WOM_UPLOADED
        if remote is None:
            if restore._preservation_receipt_remote_key(
                root, object_id, provider_kind=normalized_provider, store_ref=normalized_store
            ) is not None:
                counts["bytes_preserved_receipt_only_count"] += 1
            else:
                counts["remote_evidence_missing_count"] += 1
            continue
        remote_key = str(remote["remote_key"])
        logical_key = restore._logical_key(object_id)
        local_state = "absent"
        for row in group:
            state = restore._local_location_state(row, logical_key)
            if state == "available" or (state == "offloaded" and local_state == "absent"):
                local_state = state
        if local_state == "offloaded":
            counts["already_offloaded_count"] += 1
            continue
        sources = set()
        for row in group:
            provenance = row.get("provenance") if isinstance(row.get("provenance"), dict) else {}
            sources.add(str(provenance.get("source") or ""))
        if not sources or not sources <= OFFLOADABLE_PROVENANCE_SOURCES:
            counts["provenance_source_excluded_count"] += 1
            continue
        if archive_services.objet_capture_path_chain_blockers(root, logical_key):
            counts["path_chain_unsafe_count"] += 1
            continue
        try:
            destination = restore._destination_state(root, object_id, size_bytes, heartbeat=heartbeat)
        except restore.ObjectStorageRestoreError:
            destination = "conflict"
        if destination == "absent":
            counts["local_bytes_absent_count"] += 1
            continue
        if destination == "conflict" or local_state != "available":
            counts["local_bytes_conflict_count"] += 1
            continue
        if _file_identity(archive_services.archive_internal_path(root, logical_key)) is None:
            # st_ino 0 (FAT/exFAT, some shares) or a hard link: the bound
            # delete could not prove it removed exactly this file.
            counts["local_identity_unavailable_count"] += 1
            continue
        if object_id in retention.fidelity_sources:
            counts["fidelity_source_of_unminted_draft_count"] += 1
            continue
        if object_id in retention.referenced:
            counts["referenced_by_unminted_draft_count"] += 1
            continue
        if selected_only is None:
            if size_bytes < min_size_bytes:
                counts["below_min_size_count"] += 1
                continue
            captured = None
            for row in group:
                provenance = row.get("provenance") if isinstance(row.get("provenance"), dict) else {}
                captured = _parse_time(provenance.get("captured_at"))
                if captured is not None:
                    break
            if captured is None:
                counts["captured_at_unknown_count"] += 1
                continue
            if (now - captured).days < min_age_days:
                counts["below_min_age_count"] += 1
                continue
        counts["offload_target_count"] += 1
        source_token = _source_token(
            object_id=object_id, rows=group, remote_key=remote_key, remote_source_kind=remote_source_kind
        )
        receipt_relative = _receipt_relative(object_id, inventory_sha256)
        specs.append(
            OffloadSpec(
                object_id=object_id,
                size_bytes=size_bytes,
                remote_key=remote_key,
                remote_source_kind=remote_source_kind,
                local_relative=logical_key,
                receipt_relative=receipt_relative,
                receipt_token=_receipt_token(
                    object_id=object_id,
                    size_bytes=size_bytes,
                    provider_kind=normalized_provider,
                    store_ref=normalized_store,
                    remote_key=remote_key,
                    source_inventory_sha256=inventory_sha256,
                ),
                source_token=source_token,
                target_identity_sha256=_target_identity(
                    archive_id=archive_id, object_id=object_id, receipt_relative=receipt_relative, source_token=source_token
                ),
            )
        )
    if max_objects is not None and len(specs) > max_objects:
        raise _fail("object_storage_offload_plan_invalid")
    manifest = _manifest_for_specs(archive_id, specs, scope=scope) if not blockers else None
    return ObjectStorageOffloadPlan(
        archive_root=root,
        archive_id=archive_id,
        provider_kind=normalized_provider,
        store_ref=normalized_store,
        source_inventory_sha256=inventory_sha256,
        retention_sha256=retention_sha256,
        min_age_days=min_age_days,
        min_size_bytes=min_size_bytes,
        manifest=manifest,
        specs=tuple(specs),
        counts=counts,
        blockers=tuple(blockers),
        selected_only=selected_only,
        scope=scope,
    )


def plan_object_storage_offload(
    archive_root: Path | str,
    *,
    provider_kind: str = "cloudflare-r2",
    store_ref: str,
    only: str | None = None,
    scope: ObjectScope | None = None,
    max_objects: int | None = None,
    min_age_days: int = DEFAULT_MIN_AGE_DAYS,
    min_size_bytes: int = DEFAULT_MIN_SIZE_BYTES,
    progress: Callable[[str, str, int | None, int | None], None] | None = None,
) -> ObjectStorageOffloadPlan:
    return _build_plan(
        archive_root,
        provider_kind=provider_kind,
        store_ref=store_ref,
        only=only,
        scope=scope,
        max_objects=max_objects,
        min_age_days=min_age_days,
        min_size_bytes=min_size_bytes,
        progress=progress,
    )


# --- receipts and proof markers ----------------------------------------------------


def _receipt_document(
    plan: ObjectStorageOffloadPlan,
    spec: OffloadSpec,
    *,
    offload_status: str,
    completed_at: str,
    remote_state: str,
    review_reason: str | None,
) -> dict[str, Any]:
    if offload_status not in _TERMINAL_STATUSES:
        raise _fail("object_storage_offload_receipt_conflict")
    if review_reason is not None and review_reason not in _REVIEW_REASONS:
        raise _fail("object_storage_offload_receipt_conflict")
    if remote_state not in {"verified_match", "absent", "size_mismatch", "checksum_mismatch"}:
        raise _fail("object_storage_offload_receipt_conflict")
    if (offload_status == STATUS_BYTES_OFFLOADED) != (remote_state == "verified_match"):
        raise _fail("object_storage_offload_receipt_conflict")
    return {
        "schema_version": RECEIPT_SCHEMA,
        "object_id": spec.object_id,
        "content_sha256": spec.object_id,
        "size_bytes": spec.size_bytes,
        "provider_kind": plan.provider_kind,
        "store_ref": plan.store_ref,
        "remote_key_sha256": _sha(spec.remote_key),
        "remote_source_kind": spec.remote_source_kind,
        "source_inventory_sha256": plan.source_inventory_sha256,
        "retention_evidence_sha256": plan.retention_sha256,
        "exact_operation_manifest_sha256": plan.manifest.manifest_sha256 if plan.manifest else None,
        "receipt_state_sha256": _sha_bytes(spec.receipt_token),
        "offload_status": offload_status,
        "completed_at": completed_at,
        "remote_verification": {
            "performed": True,
            "same_run": True,
            "state": remote_state,
            "verification_kind": "get_rehash_whole_object",
            "size_match": remote_state == "verified_match",
            "whole_object_sha256_match": remote_state == "verified_match",
        },
        "local_bytes_rehashed_before_unlink": offload_status == STATUS_BYTES_OFFLOADED,
        "local_bytes_removed": offload_status == STATUS_BYTES_OFFLOADED,
        "local_bytes_freed": spec.size_bytes if offload_status == STATUS_BYTES_OFFLOADED else 0,
        "manifest_location_kept_as_offloaded": offload_status == STATUS_BYTES_OFFLOADED,
        "restore_command": "object-storage-restore",
        "remote_delete_performed": False,
        "review_reason": review_reason,
        "private_values_echoed": False,
        "credential_values_echoed": False,
        "provider_url_echoed": False,
        "local_path_echoed": False,
    }


def _create_or_match_document(root: Path, relative: str, raw: bytes, *, failure_code: str) -> None:
    """Create-only, torn-write-safe: serialize beside the target, fsync, move
    no-replace; an existing target must match byte for byte."""

    if len(raw) > _MAX_RECEIPT_BYTES:
        raise _fail(failure_code)
    target = archive_services.archive_internal_path(root, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        preservation._read_exact_receipt(target, raw, max_bytes=_MAX_RECEIPT_BYTES, failure_code=failure_code)
        return
    temporary = target.parent / f".{target.name}.tmp-{os.getpid()}"
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        descriptor = os.open(temporary, flags, 0o600)
        try:
            offset = 0
            while offset < len(raw):
                written = os.write(descriptor, raw[offset:])
                if written <= 0:
                    raise OSError("short write")
                offset += written
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        try:
            restore._atomic_move_file_no_replace(temporary, target)
        except FileExistsError:
            temporary.unlink(missing_ok=True)
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise _fail(failure_code) from None
    preservation._read_exact_receipt(target, raw, max_bytes=_MAX_RECEIPT_BYTES, failure_code=failure_code)


def _receipt_path(plan: ObjectStorageOffloadPlan, spec: OffloadSpec) -> Path:
    return archive_services.archive_internal_path(plan.archive_root, spec.receipt_relative)


def _read_receipt(plan: ObjectStorageOffloadPlan, spec: OffloadSpec) -> dict[str, Any] | None:
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
        offload_status = str(document.get("offload_status"))
        remote_state = str(document.get("remote_verification", {}).get("state"))
        review_reason = document.get("review_reason")
    except Exception:
        raise _fail("object_storage_offload_receipt_conflict") from None
    expected = _receipt_document(
        plan,
        spec,
        offload_status=offload_status,
        completed_at=completed_at,
        remote_state=remote_state,
        review_reason=None if review_reason is None else str(review_reason),
    )
    if document != expected:
        raise _fail("object_storage_offload_receipt_conflict")
    return document


def _create_receipt(
    plan: ObjectStorageOffloadPlan,
    spec: OffloadSpec,
    *,
    offload_status: str,
    remote_state: str,
    review_reason: str | None,
    completed_at: str | None = None,
) -> dict[str, Any]:
    existing = _read_receipt(plan, spec)
    if existing is not None:
        return existing
    document = _receipt_document(
        plan,
        spec,
        offload_status=offload_status,
        completed_at=completed_at or _now_iso(),
        remote_state=remote_state,
        review_reason=review_reason,
    )
    _create_or_match_document(
        plan.archive_root,
        spec.receipt_relative,
        _canonical(document) + b"\n",
        failure_code="object_storage_offload_receipt_conflict",
    )
    return document


def _marker_relative(plan: ObjectStorageOffloadPlan, spec: OffloadSpec, *, execution_sha256: str) -> str:
    """The proof marker is bound to the approved EXECUTION, not only the plan:
    a re-approval of an identical plan must prove afresh."""

    if plan.manifest is None:
        raise _fail("object_storage_offload_no_writes")
    if _SHA256_RE.fullmatch(str(execution_sha256 or "")) is None:
        raise _fail("object_storage_offload_control_invalid")
    manifest_hex = plan.manifest.manifest_sha256.removeprefix("sha256:")[:16]
    execution_hex = execution_sha256.removeprefix("sha256:")[:16]
    return f"{MARKER_ROOT}/{manifest_hex}/{execution_hex}/{spec.object_id.removeprefix('sha256:')}.proof.json"


def _file_identity(path: Path) -> dict[str, int] | None:
    """Identity the handle-bound delete can honour; None when it cannot."""

    info = restore._plain_regular_file_info(path)
    if info is None:
        return None
    if int(info.st_ino) < 1 or int(getattr(info, "st_nlink", 1)) != 1:
        return None
    return {
        "device": int(info.st_dev),
        "inode": int(info.st_ino),
        "size": int(info.st_size),
        "mtime_ns": int(info.st_mtime_ns),
    }


def _marker_document(
    plan: ObjectStorageOffloadPlan,
    spec: OffloadSpec,
    *,
    proven_at: str,
    identity: Mapping[str, int],
    execution_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_version": MARKER_SCHEMA,
        "object_id": spec.object_id,
        "size_bytes": spec.size_bytes,
        "exact_operation_manifest_sha256": plan.manifest.manifest_sha256 if plan.manifest else None,
        "execution_sha256": execution_sha256,
        "receipt_state_sha256": _sha_bytes(spec.receipt_token),
        "remote_state": "verified_match",
        "local_bytes_rehashed": True,
        "local_identity": {
            "device": int(identity["device"]),
            "inode": int(identity["inode"]),
            "size": int(identity["size"]),
            "mtime_ns": int(identity["mtime_ns"]),
        },
        "proven_at": proven_at,
        "private_control_document": True,
    }


def _read_marker(
    plan: ObjectStorageOffloadPlan, spec: OffloadSpec, *, execution_sha256: str
) -> dict[str, Any] | None:
    """The marker of THIS execution, or None. A torn or foreign marker raises."""

    path = archive_services.archive_internal_path(
        plan.archive_root, _marker_relative(plan, spec, execution_sha256=execution_sha256)
    )
    if not path.exists():
        return None
    try:
        raw = path.read_bytes()
        if len(raw) > _MAX_RECEIPT_BYTES:
            raise ValueError("large")
        document = preservation._strict_json(raw)
        proven_at = str(document.get("proven_at"))
        datetime.fromisoformat(proven_at.replace("Z", "+00:00"))
        identity = document["local_identity"]
        if any(type(identity.get(key)) is not int for key in ("device", "inode", "size", "mtime_ns")):
            raise ValueError("identity")
    except Exception:
        raise _fail("object_storage_offload_receipt_conflict") from None
    if document != _marker_document(
        plan, spec, proven_at=proven_at, identity=identity, execution_sha256=execution_sha256
    ):
        raise _fail("object_storage_offload_receipt_conflict")
    return document


def _write_marker(
    plan: ObjectStorageOffloadPlan, spec: OffloadSpec, *, identity: Mapping[str, int], execution_sha256: str
) -> dict[str, Any]:
    existing = _read_marker(plan, spec, execution_sha256=execution_sha256)
    if existing is not None:
        return existing
    document = _marker_document(
        plan, spec, proven_at=_now_iso(), identity=identity, execution_sha256=execution_sha256
    )
    _create_or_match_document(
        plan.archive_root,
        _marker_relative(plan, spec, execution_sha256=execution_sha256),
        _canonical(document) + b"\n",
        failure_code="object_storage_offload_receipt_conflict",
    )
    return document


def _discard_marker(plan: ObjectStorageOffloadPlan, spec: OffloadSpec, *, execution_sha256: str) -> None:
    try:
        archive_services.archive_internal_path(
            plan.archive_root, _marker_relative(plan, spec, execution_sha256=execution_sha256)
        ).unlink()
    except OSError:
        pass


# --- per-object write -------------------------------------------------------------


def _prove_remote(
    spec: OffloadSpec,
    transport: archive_services.ObjectStorageTransport,
    *,
    heartbeat: Callable[[], None],
) -> str:
    """Full GET re-hash in this run; returns the fixed remote state."""

    try:
        result = preservation.ObjectStorageRemoteQueryAdapter(transport).query(
            remote_key=spec.remote_key,
            expected_size=spec.size_bytes,
            expected_sha256=spec.object_id.removeprefix("sha256:"),
            heartbeat=heartbeat,
        )
    except Exception:
        raise _fail("object_storage_offload_remote_unavailable") from None
    if result.state == "verification_unavailable":
        raise _fail("object_storage_offload_remote_unavailable")
    return result.state


def _offload_one(
    plan: ObjectStorageOffloadPlan,
    spec: OffloadSpec,
    transport: archive_services.ObjectStorageTransport,
    *,
    execution_sha256: str,
    heartbeat: Callable[[], None],
) -> tuple[str, str, str | None, str | None]:
    """Return (offload_status, remote_state, review_reason, completed_at_override).

    Order: proof marker only after the same-run remote proof and a local
    re-hash; unlink only after the marker; receipt only after the unlink. A
    resumed item whose local bytes are gone but whose marker is present was
    proven and removed by an earlier attempt and gets its receipt now.
    """

    if os.name != "nt":
        raise _fail("object_storage_offload_platform_unsupported")
    root = plan.archive_root
    destination = archive_services.archive_internal_path(root, spec.local_relative)
    state = restore._destination_state(root, spec.object_id, spec.size_bytes, heartbeat=heartbeat)
    if state == "conflict":
        raise _fail("object_storage_offload_local_conflict")
    try:
        marker = _read_marker(plan, spec, execution_sha256=execution_sha256)
    except ObjectStorageOffloadError:
        if state != "present_verified":
            raise
        # A torn marker while the bytes are still here is no proof: drop it
        # and prove afresh.
        _discard_marker(plan, spec, execution_sha256=execution_sha256)
        marker = None
    if state == "absent":
        if marker is None:
            # Nothing proves this approved execution removed the bytes: refuse
            # rather than invent a receipt for a file someone else deleted.
            raise _fail("object_storage_offload_local_conflict")
        return STATUS_BYTES_OFFLOADED, "verified_match", None, str(marker["proven_at"])
    if archive_services.objet_capture_path_chain_blockers(root, spec.local_relative):
        raise _fail("object_storage_offload_local_conflict")
    identity = _file_identity(destination)
    if identity is None:
        raise _fail("object_storage_offload_local_conflict")
    if marker is not None and marker["local_identity"] == identity:
        # The proof of an earlier attempt of this approved execution stands:
        # the file is byte-identical (device, inode, size, mtime) and the
        # bound delete re-hashes it through its handle before removing it.
        proof = marker
    else:
        if marker is not None:
            _discard_marker(plan, spec, execution_sha256=execution_sha256)
        remote_state = _prove_remote(spec, transport, heartbeat=heartbeat)
        if remote_state == "absent":
            return STATUS_REVIEW_REQUIRED, "absent", "remote_absent", None
        if remote_state == "size_mismatch":
            return STATUS_REVIEW_REQUIRED, "size_mismatch", "remote_size_mismatch", None
        if remote_state == "checksum_mismatch":
            return STATUS_REVIEW_REQUIRED, "checksum_mismatch", "remote_checksum_mismatch", None
        if remote_state != "verified_match":
            raise _fail("object_storage_offload_remote_unavailable")
        # Local bytes re-hashed once more after the (possibly long) download,
        # and their identity captured for the handle-bound delete.
        if restore._destination_state(root, spec.object_id, spec.size_bytes, heartbeat=heartbeat) != "present_verified":
            raise _fail("object_storage_offload_local_conflict")
        identity = _file_identity(destination)
        if identity is None:
            raise _fail("object_storage_offload_local_conflict")
        proof = _write_marker(plan, spec, identity=identity, execution_sha256=execution_sha256)
    expected = {
        "type": "file",
        "identity": {"device": proof["local_identity"]["device"], "inode": proof["local_identity"]["inode"]},
        "size": proof["local_identity"]["size"],
        "mtime_ns": proof["local_identity"]["mtime_ns"],
        "sha256": spec.object_id.removeprefix("sha256:"),
    }
    try:
        _delete_exact_approved_file(root, destination, expected)
    except LegacyCleanupBoundDeleteError:
        # The bound delete cancels its disposition on any doubt: the file is
        # still there. Drop the proof so the next attempt proves afresh.
        _discard_marker(plan, spec, execution_sha256=execution_sha256)
        raise _fail("object_storage_offload_local_write_failed") from None
    if restore._plain_regular_file_info(destination) is not None:
        _discard_marker(plan, spec, execution_sha256=execution_sha256)
        raise _fail("object_storage_offload_local_write_failed")
    return STATUS_BYTES_OFFLOADED, "verified_match", None, str(proof["proven_at"])


# --- manifest projection ----------------------------------------------------------


def _offloaded_specs(plan: ObjectStorageOffloadPlan) -> dict[str, dict[str, Any]] | None:
    """Receipts of the batch keyed by object id; None while any is missing."""

    documents: dict[str, dict[str, Any]] = {}
    for spec in plan.specs:
        receipt = _read_receipt(plan, spec)
        if receipt is None:
            return None
        if receipt["offload_status"] == STATUS_BYTES_OFFLOADED:
            documents[spec.object_id] = receipt
    return documents


def _location_is_offloaded(location: Mapping[str, Any], logical_key: str) -> bool:
    return (
        location.get("provider") == "local"
        and location.get("path") == logical_key
        and location.get("availability") == "offloaded"
    )


def _location_is_active(location: Mapping[str, Any], logical_key: str) -> bool:
    return (
        location.get("provider") == "local"
        and location.get("path") == logical_key
        and location.get("availability") == "available"
    )


def _batch_state(plan: ObjectStorageOffloadPlan) -> bytes | None:
    specs = plan.specs
    if not specs:
        return None
    offloaded = _offloaded_specs(plan)
    if offloaded is None:
        return None
    by_id = {spec.object_id: spec for spec in specs}
    seen = {spec.object_id: 0 for spec in specs}
    flipped = {spec.object_id: False for spec in specs}
    rows, _groups = preservation._read_manifest_groups(plan.archive_root, progress=None)
    for row in rows:
        object_id = restore._object_id(row.get("object_id"))
        spec = by_id.get(object_id)
        if spec is None:
            continue
        seen[object_id] += 1
        locations = restore._locations(row)
        flipped[object_id] = any(_location_is_offloaded(loc, spec.local_relative) for loc in locations) and not any(
            _location_is_active(loc, spec.local_relative) for loc in locations
        )
    if any(value != 1 for value in seen.values()):
        raise _fail("object_storage_offload_plan_changed")
    marker_absent = restore._projection_marker_absent_for(plan.archive_root, _projection_marker_relative(plan))
    if not offloaded:
        return None if marker_absent else _manifest_batch_token(specs)
    present = {
        object_id
        for object_id in offloaded
        if restore._plain_regular_file_info(
            archive_services.archive_internal_path(plan.archive_root, by_id[object_id].local_relative)
        ) is not None
    }
    applied = [object_id for object_id in offloaded if flipped[object_id] or object_id in present]
    if not marker_absent:
        return _manifest_batch_token(specs)
    if not applied:
        return None
    if len(applied) != len(offloaded):
        raise _fail("object_storage_offload_plan_changed")
    return _manifest_batch_token(specs)


def _projection_marker_relative(plan: ObjectStorageOffloadPlan) -> str:
    if plan.manifest is None:
        raise _fail("object_storage_offload_no_writes")
    digest = plan.manifest.manifest_sha256.removeprefix("sha256:")
    return f"{CONTROL_ROOT}/{digest}.object-storage-offload.projection.json"


def _write_projection_marker(plan: ObjectStorageOffloadPlan, *, changed: int) -> None:
    document = {
        "schema_version": "wom-kit/object-storage-offload-projection/v0.1",
        "exact_operation_manifest_sha256": plan.manifest.manifest_sha256 if plan.manifest else None,
        "local_location_changes": int(changed),
        "private_control_document": True,
    }
    preservation._create_or_match_receipt(
        plan.archive_root,
        _projection_marker_relative(plan),
        _canonical(document) + b"\n",
        max_bytes=_MAX_RECEIPT_BYTES,
        failure_code="object_storage_offload_control_invalid",
    )


def _apply_manifest_batch(plan: ObjectStorageOffloadPlan, *, lifecycle: restore._ManifestIndexLifecycle) -> int:
    specs = plan.specs
    if not specs or plan.manifest is None:
        return 0
    offloaded = _offloaded_specs(plan)
    if offloaded is None:
        raise _fail("object_storage_offload_plan_changed")
    by_id = {spec.object_id: spec for spec in specs}
    manifest_path = archive_services.archive_internal_path(plan.archive_root, "objects/manifests/files.jsonl")
    owner = archive_services.archive_manifest_mutation_owner_sha256(
        operation="object_storage_bytes_offload",
        operation_binding_sha256=plan.manifest.manifest_sha256,
    )
    changed = 0
    seen = {spec.object_id: 0 for spec in specs}
    with archive_services._ObjetCaptureManifestLock(plan.archive_root):
        rewritten: list[str] = []
        try:
            before = archive_services.archive_index_stable_file_snapshot(
                plan.archive_root, manifest_path, max_bytes=archive_services.ZETTEL_OBJET_LINK_MANIFEST_MAX_BYTES
            )
            raw_lines = before["raw"].decode("utf-8").splitlines()
        except (OSError, UnicodeError):
            raise _fail("object_storage_offload_plan_changed") from None
        for raw_line in raw_lines:
            if not raw_line.strip():
                rewritten.append(raw_line)
                continue
            try:
                row = json.loads(raw_line)
                object_id = restore._object_id(row.get("object_id"))
            except Exception:
                raise _fail("object_storage_offload_plan_changed") from None
            spec = by_id.get(object_id)
            if spec is None:
                rewritten.append(raw_line)
                continue
            seen[object_id] += 1
            receipt = offloaded.get(object_id)
            if receipt is None:
                rewritten.append(raw_line)
                continue
            locations = restore._locations(row)
            if any(_location_is_offloaded(loc, spec.local_relative) for loc in locations) and not any(
                _location_is_active(loc, spec.local_relative) for loc in locations
            ):
                rewritten.append(raw_line)
                continue
            if restore._plain_regular_file_info(
                archive_services.archive_internal_path(plan.archive_root, spec.local_relative)
            ) is not None:
                # Bytes reappeared (a capture re-materialised them) before the
                # projection: the row truthfully stays available.
                lifecycle.reappeared += 1
                rewritten.append(raw_line)
                continue
            for location in locations:
                if _location_is_active(location, spec.local_relative):
                    location["availability"] = "offloaded"
                    location["offload_receipt_ref"] = spec.receipt_relative
                    location["offloaded_at"] = str(receipt["completed_at"])
                    location.pop("restore_receipt_ref", None)
            row["locations"] = locations
            changed += 1
            rewritten.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
        if any(value != 1 for value in seen.values()):
            raise _fail("object_storage_offload_plan_changed")
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
                swap_suffix=".object-storage-offload-manifest.swap",
                max_bytes=archive_services.ZETTEL_OBJET_LINK_MANIFEST_MAX_BYTES,
                error_prefix="object_storage_offload",
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


# --- exact operation adapters ------------------------------------------------------


class _Payloads:
    def __init__(self, plan: ObjectStorageOffloadPlan) -> None:
        self.values: dict[tuple[str, str], tuple[bytes | None, bytes, bytes]] = {}
        if plan.manifest is None:
            return
        for item, spec in zip(plan.manifest.items, plan.specs):
            self.values[(item.item_id, "local_bytes_offload")] = (None, spec.receipt_token, spec.source_token)
        if plan.specs:
            item = plan.manifest.items[-1]
            self.values[(item.item_id, "local_locations")] = (
                None,
                _manifest_batch_token(plan.specs),
                _manifest_source_token(plan.specs),
            )

    def field_value(self, *, item_id: str, field_ref: str, state: str, heartbeat: Callable[[], None]) -> bytes | None:
        heartbeat()
        values = self.values.get((item_id, field_ref))
        if values is None or state not in {"pre", "post", "source"}:
            raise ValueError("payload boundary")
        return values[{"pre": 0, "post": 1, "source": 2}[state]]


class _Verifier:
    def __init__(self, plan: ObjectStorageOffloadPlan, *, execution_sha256: str | None = None) -> None:
        self.plan = plan
        self.execution_sha256 = execution_sha256
        self.by_target = {spec.receipt_relative: spec for spec in plan.specs}
        _rows, self.groups = preservation._read_manifest_groups(plan.archive_root, progress=None)

    def target_identity_sha256(self, *, target_kind: str, target_ref: str, heartbeat: Callable[[], None]) -> str:
        heartbeat()
        if target_kind == "object_storage_offload_receipt":
            spec = self.by_target.get(target_ref)
            if spec is None:
                raise ValueError("target boundary")
            group = self.groups.get(spec.object_id)
            if not group or _source_token(
                object_id=spec.object_id, rows=group, remote_key=spec.remote_key, remote_source_kind=spec.remote_source_kind
            ) != spec.source_token:
                raise ValueError("source drift")
            return spec.target_identity_sha256
        if target_kind == "object_storage_offload_manifest_batch" and target_ref == MANIFEST_TARGET_REF:
            source = _manifest_source_token(self.plan.specs)
            return _sha({"archive_id": self.plan.archive_id, "target_ref": MANIFEST_TARGET_REF, "source_sha256": _sha_bytes(source)})
        raise ValueError("target boundary")

    def read_field(self, *, target_kind: str, target_ref: str, field_ref: str, heartbeat: Callable[[], None]) -> bytes | None:
        if target_kind == "object_storage_offload_receipt":
            spec = self.by_target.get(target_ref)
            if spec is None or field_ref != "local_bytes_offload":
                raise ValueError("read boundary")
            receipt = _read_receipt(self.plan, spec)
            state = restore._destination_state(self.plan.archive_root, spec.object_id, spec.size_bytes, heartbeat=heartbeat)
            if receipt is None:
                if state == "present_verified":
                    return None
                if (
                    state == "absent"
                    and self.execution_sha256 is not None
                    and _read_marker(self.plan, spec, execution_sha256=self.execution_sha256) is not None
                ):
                    return None  # proven and removed by this execution; the writer records it
                raise ValueError("local bytes drifted")
            if state == "conflict":
                raise ValueError("local bytes drifted")
            if receipt["offload_status"] == STATUS_REVIEW_REQUIRED and state != "present_verified":
                raise ValueError("local bytes drifted")
            # bytes_offloaded: absent is the expected post state; present_verified
            # means a capture re-materialised the same bytes, which the
            # projection reports instead of failing.
            return spec.receipt_token
        if target_kind == "object_storage_offload_manifest_batch" and target_ref == MANIFEST_TARGET_REF and field_ref == "local_locations":
            return _batch_state(self.plan)
        raise ValueError("read boundary")


class _Writer:
    def __init__(
        self,
        plan: ObjectStorageOffloadPlan,
        transport: archive_services.ObjectStorageTransport,
        *,
        execution_sha256: str,
    ) -> None:
        self.plan = plan
        self.transport = transport
        self.execution_sha256 = execution_sha256
        self.by_target = {spec.receipt_relative: spec for spec in plan.specs}
        self.status_counts: dict[str, int] = {status: 0 for status in sorted(_TERMINAL_STATUSES)}
        self.provider_get_count = 0
        self.receipts_created_count = 0
        self.local_bytes_freed = 0
        self.manifest_update_count = 0
        self.manifest_index_lifecycle = restore._ManifestIndexLifecycle()

    def write_field(self, *, target_kind: str, target_ref: str, field_ref: str, value: bytes | None, heartbeat: Callable[[], None]) -> None:
        if target_kind == "object_storage_offload_receipt":
            spec = self.by_target.get(target_ref)
            if spec is None or field_ref != "local_bytes_offload":
                raise ValueError("write boundary")
            if value is None or value != spec.receipt_token:
                raise ValueError("write boundary")
            if _read_receipt(self.plan, spec) is not None:
                _discard_marker(self.plan, spec, execution_sha256=self.execution_sha256)
                return
            try:
                had_marker = _read_marker(self.plan, spec, execution_sha256=self.execution_sha256) is not None
            except ObjectStorageOffloadError:
                had_marker = False
            status, remote_state, review_reason, completed_at = _offload_one(
                self.plan, spec, self.transport, execution_sha256=self.execution_sha256, heartbeat=heartbeat
            )
            if not had_marker:
                self.provider_get_count += 1
            _create_receipt(
                self.plan,
                spec,
                offload_status=status,
                remote_state=remote_state,
                review_reason=review_reason,
                completed_at=completed_at,
            )
            _discard_marker(self.plan, spec, execution_sha256=self.execution_sha256)
            self.receipts_created_count += 1
            self.status_counts[status] += 1
            if status == STATUS_BYTES_OFFLOADED:
                self.local_bytes_freed += spec.size_bytes
            return
        if target_kind == "object_storage_offload_manifest_batch" and target_ref == MANIFEST_TARGET_REF and field_ref == "local_locations":
            if value != _manifest_batch_token(self.plan.specs):
                raise ValueError("write boundary")
            self.manifest_update_count += _apply_manifest_batch(self.plan, lifecycle=self.manifest_index_lifecycle)
            return
        raise ValueError("write boundary")


# --- approval binding, control, execution ----------------------------------------


def _approval_binding(plan: ObjectStorageOffloadPlan) -> ExactOperationApprovalBinding:
    if plan.manifest is None:
        raise _fail("object_storage_offload_no_writes")
    try:
        return exact_operation_manifest_approval_binding(
            plan.manifest,
            operation=ExactHumanApprovalOperation.object_storage_bytes_offload,
            archive_id=plan.archive_id,
            warnings=(
                "local_bytes_are_removed_only_after_same_run_full_get_proof",
                "manifest_location_stays_as_offloaded_tombstone",
                "remote_object_is_never_deleted",
                "object_storage_restore_brings_bytes_back",
            ),
        )
    except Exception:
        raise _fail("object_storage_offload_plan_invalid") from None


def object_storage_offload_context(plan: ObjectStorageOffloadPlan, *, reviewer_claim: str) -> ExactHumanApprovalContext:
    reviewer = str(reviewer_claim or "").strip()
    if not reviewer or not plan.approveable:
        raise _fail("object_storage_offload_plan_invalid")
    return _approval_binding(plan).context(archive_id=plan.archive_id, reviewer_claim=reviewer)


def _assert_approved(
    plan: ObjectStorageOffloadPlan, claim: _ClaimedExactHumanApproval, context: ExactHumanApprovalContext
) -> ExactOperationApprovalAuthority:
    binding = _approval_binding(plan)
    if (
        type(claim) is not _ClaimedExactHumanApproval
        or context.operation is not ExactHumanApprovalOperation.object_storage_bytes_offload
        or context.plan_sha256 != binding.plan_sha256
        or context.target_binding_sha256 != binding.target_binding_sha256
    ):
        raise _fail("object_storage_offload_approval_required")
    try:
        reference = _ClaimedExactHumanApproval.assert_ready_for_context(claim, context)
        return ExactOperationApprovalAuthority.from_reference(reference)
    except (ExactHumanApprovalError, ExactOperationManifestError):
        raise _fail("object_storage_offload_approval_required") from None


def _control_relative(manifest_sha256: str) -> str:
    if _SHA256_RE.fullmatch(str(manifest_sha256 or "")) is None:
        raise _fail("object_storage_offload_control_invalid")
    return f"{CONTROL_ROOT}/{manifest_sha256.removeprefix('sha256:')}.object-storage-offload.json"


def _control_document(plan: ObjectStorageOffloadPlan) -> dict[str, Any]:
    if plan.manifest is None:
        raise _fail("object_storage_offload_no_writes")
    basis = {
        "schema_version": CONTROL_SCHEMA,
        "archive_id": plan.archive_id,
        "provider_kind": plan.provider_kind,
        "store_ref": plan.store_ref,
        "source_inventory_sha256": plan.source_inventory_sha256,
        "retention_evidence_sha256": plan.retention_sha256,
        "min_age_days": plan.min_age_days,
        "min_size_bytes": plan.min_size_bytes,
        "counts": {str(key): int(value) for key, value in plan.counts.items()},
        "selected_only": plan.selected_only,
        **({"scope": plan.scope.document()} if plan.scope else {}),
        "manifest": plan.manifest.document(),
        "specs": [
            {
                "object_id": spec.object_id,
                "size_bytes": spec.size_bytes,
                "remote_key": spec.remote_key,
                "remote_source_kind": spec.remote_source_kind,
                "local_relative": spec.local_relative,
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


def _persist_control(plan: ObjectStorageOffloadPlan) -> str:
    if plan.manifest is None:
        raise _fail("object_storage_offload_no_writes")
    relative = _control_relative(plan.manifest.manifest_sha256)
    preservation._create_or_match_receipt(
        plan.archive_root,
        relative,
        preservation._canonical_control_bytes(_control_document(plan)),
        max_bytes=_MAX_CONTROL_BYTES,
        failure_code="object_storage_offload_control_invalid",
    )
    return relative


def load_object_storage_offload_plan(archive_root: Path | str, *, manifest_sha256: str) -> ObjectStorageOffloadPlan:
    try:
        root = archive_services.require_existing_archive_root(archive_root)
        archive_id = archive_services.read_archive_id(root)
        path = archive_services.archive_internal_path(root, _control_relative(manifest_sha256))
        raw = path.read_bytes()
        if len(raw) > _MAX_CONTROL_BYTES:
            raise ValueError("large")
        document = preservation._strict_json(raw)
    except ObjectStorageOffloadError:
        raise
    except Exception:
        raise _fail("object_storage_offload_control_invalid") from None
    supplied = document.pop("control_sha256", None)
    if (
        document.get("schema_version") != CONTROL_SCHEMA
        or document.get("private_control_document") is not True
        or not isinstance(supplied, str)
        or not hmac.compare_digest(supplied, _sha(document))
        or document.get("archive_id") != archive_id
    ):
        raise _fail("object_storage_offload_control_invalid")
    try:
        manifest = ExactOperationManifest.from_document(document["manifest"])
        provider = document["provider_kind"]
        store = document["store_ref"]
        inventory_sha = document["source_inventory_sha256"]
        retention_sha = document["retention_evidence_sha256"]
        min_age_days = document["min_age_days"]
        min_size_bytes = document["min_size_bytes"]
        counts = document["counts"]
        raw_specs = document["specs"]
        selected_only = document.get("selected_only")
        _rows, groups = preservation._read_manifest_groups(root, progress=None)
    except Exception:
        raise _fail("object_storage_offload_control_invalid") from None
    if (
        manifest.manifest_sha256 != manifest_sha256
        or manifest.operation != OPERATION
        or provider not in archive_services.OBJECT_STORAGE_ALLOWED_PROVIDERS
        or not archive_services.safe_object_storage_ref(store)
        or _SHA256_RE.fullmatch(str(inventory_sha)) is None
        or _SHA256_RE.fullmatch(str(retention_sha)) is None
        or type(min_age_days) is not int
        or type(min_size_bytes) is not int
        or not isinstance(counts, dict)
        or not isinstance(raw_specs, list)
        or (selected_only is not None and restore._object_id(selected_only) != selected_only)
    ):
        raise _fail("object_storage_offload_control_invalid")
    _require_setup_evidence(root, provider_kind=provider, store_ref=store)
    specs: list[OffloadSpec] = []
    for raw_spec in raw_specs:
        try:
            object_id = restore._object_id(raw_spec["object_id"])
            remote_key = raw_spec["remote_key"]
            remote_source_kind = raw_spec["remote_source_kind"]
            size = raw_spec["size_bytes"]
            local_relative = raw_spec["local_relative"]
            receipt_relative = raw_spec["receipt_relative"]
            group = groups[object_id]
        except Exception:
            raise _fail("object_storage_offload_control_invalid") from None
        if (
            type(remote_key) is not str
            or not archive_services.safe_object_storage_remote_key(remote_key)
            or type(size) is not int
            or {row.get("size_bytes") for row in group} != {size}
            or local_relative != restore._logical_key(object_id)
            or remote_source_kind not in restore._REMOTE_SOURCES
        ):
            raise _fail("object_storage_offload_control_invalid")
        source_token = _source_token(object_id=object_id, rows=group, remote_key=remote_key, remote_source_kind=remote_source_kind)
        receipt_token = _receipt_token(
            object_id=object_id, size_bytes=size, provider_kind=provider, store_ref=store, remote_key=remote_key, source_inventory_sha256=inventory_sha
        )
        identity = _target_identity(archive_id=archive_id, object_id=object_id, receipt_relative=receipt_relative, source_token=source_token)
        if (
            receipt_relative != _receipt_relative(object_id, inventory_sha)
            or raw_spec.get("receipt_token_sha256") != _sha_bytes(receipt_token)
            or raw_spec.get("source_token_sha256") != _sha_bytes(source_token)
            or raw_spec.get("target_identity_sha256") != identity
        ):
            raise _fail("object_storage_offload_plan_changed")
        specs.append(
            OffloadSpec(
                object_id=object_id,
                size_bytes=size,
                remote_key=remote_key,
                remote_source_kind=remote_source_kind,
                local_relative=local_relative,
                receipt_relative=receipt_relative,
                receipt_token=receipt_token,
                source_token=source_token,
                target_identity_sha256=identity,
            )
        )
    loaded_scope = ObjectScope.from_document(document["scope"]) if document.get("scope") is not None else None
    rebuilt = _manifest_for_specs(archive_id, specs, scope=loaded_scope)
    if rebuilt is None or rebuilt.document() != manifest.document():
        raise _fail("object_storage_offload_control_invalid")
    return ObjectStorageOffloadPlan(
        archive_root=root,
        archive_id=archive_id,
        provider_kind=provider,
        store_ref=store,
        source_inventory_sha256=inventory_sha,
        retention_sha256=retention_sha,
        min_age_days=min_age_days,
        min_size_bytes=min_size_bytes,
        manifest=manifest,
        specs=tuple(specs),
        counts={str(key): int(value) for key, value in counts.items()},
        selected_only=selected_only,
        scope=ObjectScope.from_document(document["scope"]) if document.get("scope") is not None else None,
        loaded_from_control=True,
    )


def _fresh_revalidated(plan: ObjectStorageOffloadPlan) -> ObjectStorageOffloadPlan:
    _require_setup_evidence(plan.archive_root, provider_kind=plan.provider_kind, store_ref=plan.store_ref)
    if plan.scope is not None:
        if any(not plan.scope.includes(spec.object_id, destructive=True) for spec in plan.specs):
            raise ObjectStorageScopeError("object_storage_scope_control_mismatch")
        if plan.scope.kind == "captured_by_session":
            current_scope = resolve_scope(plan.archive_root, captured_by_session=plan.scope.session_ref)
            if any(not current_scope.includes(spec.object_id, destructive=True) for spec in plan.specs):
                raise ObjectStorageScopeError("object_storage_scope_changed")
    if plan.loaded_from_control:
        # A resumed plan re-checks retention: a draft written since the
        # approval must not lose its object.
        current = _draft_retention_evidence(plan.archive_root)
        if current.unreadable_draft_count or current.unreadable_fidelity_receipt_count:
            raise _fail("object_storage_offload_retention_evidence_unreadable")
        for spec in plan.specs:
            if spec.object_id in current.referenced or spec.object_id in current.fidelity_sources:
                if _read_receipt(plan, spec) is None:
                    raise _fail("object_storage_offload_plan_changed")
        return plan
    if plan.manifest is None:
        raise _fail("object_storage_offload_plan_changed")
    current_plan = _build_plan(
        plan.archive_root,
        provider_kind=plan.provider_kind,
        store_ref=plan.store_ref,
        only=plan.selected_only,
        scope=plan.scope,
        max_objects=None,
        min_age_days=plan.min_age_days,
        min_size_bytes=plan.min_size_bytes,
        progress=None,
    )
    if current_plan.manifest is None or current_plan.manifest.document() != plan.manifest.document():
        raise _fail("object_storage_offload_plan_changed")
    return current_plan


def _result_document(plan: ObjectStorageOffloadPlan, core: Mapping[str, Any], writer: _Writer) -> dict[str, Any]:
    completed = core.get("status") == "completed"
    return {
        "schema_version": RESULT_SCHEMA,
        "ok": completed,
        "state": "offload_completed" if completed else "offload_incomplete",
        "manifest_sha256": plan.manifest.manifest_sha256 if plan.manifest else None,
        "execution": dict(core),
        "planned_object_count": len(plan.specs),
        "receipts_created_count": writer.receipts_created_count,
        "provider_get_call_count": writer.provider_get_count,
        "status_counts": dict(writer.status_counts),
        "local_bytes_freed": writer.local_bytes_freed,
        "local_bytes_reappeared_count": writer.manifest_index_lifecycle.reappeared,
        "manifest_location_updates": writer.manifest_update_count,
        "generated_index_updated": writer.manifest_index_lifecycle.updated,
        "index_generation": writer.manifest_index_lifecycle.generation,
        "index_mutation_resumed": writer.manifest_index_lifecycle.resumed,
        "central_manifest_rewrite_count_ceiling": 1,
        "manifest_location_removed": False,
        "remote_delete_performed": False,
        "provider_put_called": False,
        "restore_command": "object-storage-restore",
        "private_values_echoed": False,
        "remote_keys_echoed": False,
        "object_ids_echoed": False,
        "local_paths_echoed": False,
    }


def _apply_with_store(
    plan: ObjectStorageOffloadPlan,
    authority: ExactOperationApprovalAuthority,
    transport: archive_services.ObjectStorageTransport,
    checkpoints: FileExactOperationCheckpointStore,
    *,
    resume: bool,
    progress_hook: Callable[[ExactOperationProgress], None] | None,
) -> dict[str, Any]:
    if plan.manifest is None:
        raise _fail("object_storage_offload_no_writes")
    restore._require_manifest_index_authority_for(plan.archive_root, plan.manifest.manifest_sha256, operation="object_storage_bytes_offload")
    execution_sha256 = exact_operation_execution_sha256(plan.manifest, approval_authority=authority)
    payloads = _Payloads(plan)
    writer = _Writer(plan, transport, execution_sha256=execution_sha256)
    verifier = _Verifier(plan, execution_sha256=execution_sha256)
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
    if plan.specs and core.get("status") == "completed":
        evidence = archive_services.require_current_zettel_index(plan.archive_root)
        if not evidence.get("ok") and "archive_index_dirty" in set(evidence.get("reason_codes") or []):
            restore._reseal_dirty_projection_for(
                plan.archive_root, plan.manifest.manifest_sha256, writer.manifest_index_lifecycle, operation="object_storage_bytes_offload"
            )
            evidence = archive_services.require_current_zettel_index(plan.archive_root)
        if not evidence.get("ok"):
            raise _fail("archive_index_rebuild_required")
    return _result_document(plan, core, writer)


def _apply_core(
    plan: ObjectStorageOffloadPlan,
    claim: _ClaimedExactHumanApproval,
    *,
    context: ExactHumanApprovalContext,
    transport_factory: Callable[[], archive_services.ObjectStorageTransport],
    resume: bool = False,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
) -> dict[str, Any]:
    current = _fresh_revalidated(plan)
    restore._require_manifest_index_authority_for(current.archive_root, current.manifest.manifest_sha256, operation="object_storage_bytes_offload")
    authority = _assert_approved(current, claim, context)
    with exact_operation_writer_lock(current.archive_root) as writer_lock:
        _persist_control(current)
        checkpoints = FileExactOperationCheckpointStore(current.archive_root, writer_lock=writer_lock)
        try:
            transport = transport_factory()
        except Exception:
            raise _fail("object_storage_offload_remote_unavailable") from None
        if transport is None:
            raise _fail("object_storage_offload_remote_unavailable")
        return _apply_with_store(current, authority, transport, checkpoints, resume=resume, progress_hook=progress_hook)


def _target_collection(plan: ObjectStorageOffloadPlan) -> TargetCollectionPreview | None:
    try:
        items = tuple(TargetCollectionItem(identity_sha256=spec.object_id, kind="objet") for spec in plan.specs)
        return TargetCollectionPreview(items=items) if items else None
    except ValueError:
        return None


def execute_object_storage_offload(
    plan: ObjectStorageOffloadPlan,
    *,
    reviewer_claim: str,
    transport_factory: Callable[[], archive_services.ObjectStorageTransport],
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
) -> dict[str, Any]:
    if not plan.approveable:
        raise _fail("object_storage_offload_no_writes")
    context = object_storage_offload_context(plan, reviewer_claim=reviewer_claim)
    collection = _target_collection(plan)

    def observe_target_binding() -> str:
        try:
            return _approval_binding(_fresh_revalidated(plan)).target_binding_sha256
        except Exception:
            return "sha256:" + "0" * 64

    return _execute_exact_human_approved_write(
        plan.archive_root,
        context,
        lambda claim: _apply_core(plan, claim, context=context, transport_factory=transport_factory, progress_hook=progress_hook),
        target_collection=collection,
        observe_target_binding=observe_target_binding if collection is not None else None,
    )


def resume_object_storage_offload(
    plan: ObjectStorageOffloadPlan,
    *,
    reviewer_claim: str,
    approval_id: str,
    execution_sha256: str,
    transport_factory: Callable[[], archive_services.ObjectStorageTransport],
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
    key_provider: Any = None,
) -> dict[str, Any]:
    if not plan.loaded_from_control or plan.manifest is None or _SHA256_RE.fullmatch(str(execution_sha256 or "")) is None:
        raise _fail("object_storage_offload_resume_invalid")
    restore._require_manifest_index_authority_for(plan.archive_root, plan.manifest.manifest_sha256, operation="object_storage_bytes_offload")
    context = object_storage_offload_context(plan, reviewer_claim=reviewer_claim)
    with exact_operation_writer_lock(plan.archive_root) as writer_lock:
        checkpoints = FileExactOperationCheckpointStore(plan.archive_root, writer_lock=writer_lock)

        def writer(claim: _ClaimedExactHumanApproval) -> Mapping[str, Any]:
            current = _fresh_revalidated(plan)
            authority = _assert_approved(current, claim, context)
            actual = exact_operation_execution_sha256(current.manifest, approval_authority=authority)
            if not hmac.compare_digest(actual, execution_sha256):
                raise _fail("object_storage_offload_resume_invalid")
            try:
                transport = transport_factory()
            except Exception:
                raise _fail("object_storage_offload_remote_unavailable") from None
            return _apply_with_store(current, authority, transport, checkpoints, resume=True, progress_hook=progress_hook)

        return _resume_exact_human_approved_write_core(
            plan.archive_root,
            context,
            approval_id,
            lambda _claim: checkpoints.resume_checkpoint_present(execution_sha256),
            writer,
            key_provider=key_provider,
        )


def verify_object_storage_offload(plan: ObjectStorageOffloadPlan, *, heartbeat: Callable[[], None] | None = None) -> dict[str, Any]:
    if type(plan) is not ObjectStorageOffloadPlan or plan.manifest is None:
        raise _fail("object_storage_offload_plan_invalid")
    result = verify_exact_operation(plan.manifest, verifier=_Verifier(plan), state="post", heartbeat=heartbeat)
    return {
        "schema_version": VERIFY_SCHEMA,
        "ok": result["all_match"],
        "manifest_sha256": plan.manifest.manifest_sha256,
        "verified_item_count": len(plan.manifest.items) if result["all_match"] else 0,
        "verification": result,
        "provider_api_called": False,
        "writes_performed": False,
        "private_values_echoed": False,
        "remote_keys_echoed": False,
    }


__all__ = [
    "DEFAULT_MIN_AGE_DAYS",
    "DEFAULT_MIN_SIZE_BYTES",
    "ObjectStorageOffloadError",
    "ObjectStorageOffloadPlan",
    "OffloadSpec",
    "RetentionEvidence",
    "execute_object_storage_offload",
    "load_object_storage_offload_plan",
    "object_storage_offload_context",
    "plan_object_storage_offload",
    "resume_object_storage_offload",
    "verify_object_storage_offload",
]
