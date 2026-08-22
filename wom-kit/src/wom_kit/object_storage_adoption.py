"""Exact formal adoption of existing object-storage bytes.

The legacy adopter rewrote the central object manifest once per object.  This
module instead plans one immutable, resumable HEAD-verification receipt per
mapped object and one final manifest projection.  Conflicting manifest
definitions are queried and classified, but are never merged or adopted
automatically.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import archive_services
from . import object_storage_preservation as preservation
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


PLAN_SCHEMA = "wom-kit/object-storage-formal-adoption-plan/v0.1"
CONTROL_SCHEMA = "wom-kit/object-storage-formal-adoption-control/v0.1"
RECEIPT_SCHEMA = "wom-kit/object-storage-formal-adoption-receipt/v0.1"
RESULT_SCHEMA = "wom-kit/object-storage-formal-adoption-result/v0.1"
VERIFY_SCHEMA = "wom-kit/object-storage-formal-adoption-verification/v0.1"
OPERATION = ExactHumanApprovalOperation.object_storage_formal_adoption.value
RECEIPT_ROOT = "receipts/providers/object-storage-formal-adoption"
CONTROL_ROOT = "profiles/local/exact-operations/manifests"
MANIFEST_TARGET_REF = "objects/manifests/files.jsonl#formal-adoption-location-batch"

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_BARE_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_BATCH_RE = re.compile(r"^batch:[0-9a-f]{64}$")
_MAX_KEY_MAP_BYTES = 128 * 1024 * 1024
_MAX_JUDGMENT_BYTES = 8 * 1024 * 1024


class ObjectStorageAdoptionError(RuntimeError):
    _CODES = {
        "object_storage_adoption_archive_invalid",
        "object_storage_adoption_plan_invalid",
        "object_storage_adoption_key_map_invalid",
        "object_storage_adoption_judgment_invalid",
        "object_storage_adoption_no_writes",
        "object_storage_adoption_plan_changed",
        "object_storage_adoption_approval_required",
        "object_storage_adoption_remote_unavailable",
        "object_storage_adoption_remote_mismatch",
        "object_storage_adoption_receipt_conflict",
        "object_storage_adoption_control_invalid",
        "object_storage_adoption_resume_invalid",
    }

    def __init__(self, code: str) -> None:
        self.code = code if code in self._CODES else "object_storage_adoption_plan_invalid"
        super().__init__(self.code)


def _fail(code: str) -> ObjectStorageAdoptionError:
    return ObjectStorageAdoptionError(code)


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
        raise _fail("object_storage_adoption_plan_invalid") from None


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
    raise _fail("object_storage_adoption_plan_invalid")


def _plain_file_sha256(path: Path, *, max_bytes: int, code: str) -> str:
    try:
        before = path.stat()
        if not path.is_file() or before.st_size > max_bytes:
            raise OSError("unsafe")
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                block = handle.read(1024 * 1024)
                if not block:
                    break
                digest.update(block)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise OSError("changed")
        return "sha256:" + digest.hexdigest()
    except OSError:
        raise _fail(code) from None


def _locations(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(item) for item in row.get("locations", []) if isinstance(item, Mapping)]


def _matching_adoption_location(
    row: Mapping[str, Any], *, provider_kind: str, store_ref: str, remote_key: str
) -> bool:
    digest = _object_id(row.get("object_id")).removeprefix("sha256:")
    return archive_services.object_storage_wom_uploaded_location_match(
        _locations(row),
        provider_kind=provider_kind,
        store_ref=store_ref,
        digest=digest,
        expected_remote_key=remote_key,
    ) is not None


def _receipt_relative(object_id: str, source_inventory_sha256: str) -> str:
    digest = object_id.removeprefix("sha256:")
    inventory = source_inventory_sha256.removeprefix("sha256:")
    return f"{RECEIPT_ROOT}/{digest}.{inventory[:16]}.json"


def _receipt_token(
    *,
    object_id: str,
    size_bytes: int,
    provider_kind: str,
    store_ref: str,
    remote_key: str,
    classification: str,
    source_inventory_sha256: str,
) -> bytes:
    return _canonical(
        {
            "schema_version": "wom-kit/object-storage-formal-adoption-state/v0.1",
            "object_id": object_id,
            "size_bytes": size_bytes,
            "provider_kind": provider_kind,
            "store_ref": store_ref,
            "remote_key_sha256": _sha(remote_key),
            "classification": classification,
            "source_inventory_sha256": source_inventory_sha256,
            "remote_verification": "head_presence_size_match",
        }
    )


def _target_identity(
    *, archive_id: str, object_id: str, receipt_relative: str, source_token: bytes
) -> str:
    return _sha(
        {
            "schema_version": "wom-kit/object-storage-formal-adoption-target/v0.1",
            "archive_id": archive_id,
            "object_id": object_id,
            "receipt_relative": receipt_relative,
            "source_token_sha256": _sha_bytes(source_token),
        }
    )


@dataclass(frozen=True, repr=False)
class FormalAdoptionSpec:
    object_id: str
    size_bytes: int
    remote_key: str
    classification: str
    receipt_relative: str
    receipt_token: bytes
    source_token: bytes
    target_identity_sha256: str

    @property
    def formal_adoption_eligible(self) -> bool:
        return self.classification == "pending_formal_adoption"


@dataclass(frozen=True, repr=False)
class ConflictBatch:
    batch_fingerprint: str
    group_count: int
    reason_codes: tuple[str, ...]
    judgment: str

    def public_document(self) -> dict[str, Any]:
        return {
            "batch_fingerprint": self.batch_fingerprint,
            "group_count": self.group_count,
            "reason_codes": list(self.reason_codes),
            "judgment": self.judgment,
            "automatic_merge_allowed": False,
            "formal_adoption_allowed": False,
        }


@dataclass(frozen=True, repr=False)
class ObjectStorageFormalAdoptionPlan:
    archive_root: Path
    archive_id: str
    provider_kind: str
    store_ref: str
    source_inventory_sha256: str
    key_map_sha256: str
    manifest: ExactOperationManifest | None
    specs: tuple[FormalAdoptionSpec, ...]
    conflict_batches: tuple[ConflictBatch, ...]
    counts: Mapping[str, int]
    key_map_path: Path | None = None
    judgment_path: Path | None = None
    loaded_from_control: bool = False

    @property
    def adoption_specs(self) -> tuple[FormalAdoptionSpec, ...]:
        return tuple(item for item in self.specs if item.formal_adoption_eligible)

    @property
    def approveable(self) -> bool:
        return self.manifest is not None and bool(self.specs)

    def public_document(self) -> dict[str, Any]:
        return {
            "schema_version": PLAN_SCHEMA,
            "ok": self.approveable,
            "state": "ready_for_exact_human_approval" if self.approveable else "no_mapped_objects",
            "reason_codes": [
                "object_storage_formal_adoption_ready"
                if self.approveable
                else "object_storage_adoption_no_writes"
            ],
            "plan_sha256": self.manifest.manifest_sha256 if self.manifest else None,
            "target_binding_sha256": self.manifest.target_set_sha256 if self.manifest else None,
            "source_binding_sha256": self.manifest.source_set_sha256 if self.manifest else None,
            "effect_binding_sha256": self.manifest.effect_set_sha256 if self.manifest else None,
            "source_inventory_sha256": self.source_inventory_sha256,
            "key_map_sha256": self.key_map_sha256,
            **dict(self.counts),
            "conflict_classification": {
                "status": "batch_judgment_or_review_required",
                "conflicting_definition_count": int(self.counts["conflicting_definition_count"]),
                "batch_count": len(self.conflict_batches),
                "batches": [item.public_document() for item in self.conflict_batches],
                "allowed_judgments": ["defer_review", "keep_definitions_distinct"],
                "automatic_merge_count": 0,
                "formal_adoption_count": 0,
            },
            "manifest_rewrite_planned_count": 1 if self.adoption_specs else 0,
            "per_object_manifest_rewrite_planned_count": 0,
            "provider_head_calls_per_object": 2,
            "provider_put_call_count": 0,
            "provider_api_called": False,
            "credential_values_read": False,
            "writes_performed": False,
            "remote_keys_echoed": False,
            "object_ids_echoed": False,
            "local_paths_echoed": False,
            "common_exact_operation_manifest_used": self.manifest is not None,
        }


def _read_judgments(path: Path | None) -> tuple[dict[str, str], str | None]:
    if path is None:
        return {}, None
    file_sha = _plain_file_sha256(
        path, max_bytes=_MAX_JUDGMENT_BYTES, code="object_storage_adoption_judgment_invalid"
    )
    decisions: dict[str, str] = {}
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            for raw in handle:
                if not raw.strip():
                    continue
                row = json.loads(raw)
                fingerprint = row.get("batch_fingerprint")
                judgment = row.get("judgment")
                if (
                    not isinstance(row, dict)
                    or type(fingerprint) is not str
                    or _BATCH_RE.fullmatch(fingerprint) is None
                    or judgment not in {"defer_review", "keep_definitions_distinct"}
                    or fingerprint in decisions
                ):
                    raise ValueError("invalid")
                decisions[fingerprint] = judgment
    except (OSError, ValueError, json.JSONDecodeError):
        raise _fail("object_storage_adoption_judgment_invalid") from None
    return decisions, file_sha


def _conflict_batches(
    groups: Mapping[str, Sequence[dict[str, Any]]], decisions: Mapping[str, str]
) -> tuple[ConflictBatch, ...]:
    grouped: dict[tuple[str, ...], int] = {}
    for object_id in sorted(groups):
        rows = groups[object_id]
        if len(rows) < 2:
            continue
        projection = preservation._conflict_projection(object_id, rows)
        reasons = tuple(projection["reason_codes"])
        grouped[reasons] = grouped.get(reasons, 0) + 1
    result: list[ConflictBatch] = []
    known: set[str] = set()
    for reasons, count in sorted(grouped.items()):
        fingerprint = "batch:" + hashlib.sha256(
            _canonical({"reason_codes": reasons, "automatic_merge_allowed": False})
        ).hexdigest()
        known.add(fingerprint)
        result.append(
            ConflictBatch(
                batch_fingerprint=fingerprint,
                group_count=count,
                reason_codes=reasons,
                judgment=decisions.get(fingerprint, "defer_review"),
            )
        )
    if set(decisions) - known:
        raise _fail("object_storage_adoption_judgment_invalid")
    return tuple(result)


def _source_token(
    *, object_id: str, rows: Sequence[Mapping[str, Any]], remote_key: str, key_map_sha256: str
) -> bytes:
    row_projection = []
    for row in rows:
        row_projection.append(
            {
                "object_id": _object_id(row.get("object_id")),
                "sha256": _object_id(row.get("sha256")),
                "size_bytes": row.get("size_bytes"),
                "logical_key_sha256": _sha(row.get("logical_key")),
                "mime_sha256": _sha(row.get("mime")),
                "non_adoption_locations_sha256": _sha(
                    [
                        location
                        for location in _locations(row)
                        if not (
                            location.get("provider") == "object_storage"
                            and location.get("availability") == "wom_uploaded"
                            and location.get("remote_key") == remote_key
                            and str(location.get("execution_receipt_ref") or "").startswith(RECEIPT_ROOT + "/")
                        )
                    ]
                ),
            }
        )
    return _canonical(
        {
            "schema_version": "wom-kit/object-storage-formal-adoption-source/v0.1",
            "object_id": object_id,
            "rows": row_projection,
            "remote_key_sha256": _sha(remote_key),
            "key_map_sha256": key_map_sha256,
        }
    )


def _manifest_batch_token(specs: Sequence[FormalAdoptionSpec]) -> bytes:
    return _canonical(
        {
            "schema_version": "wom-kit/object-storage-formal-adoption-location-batch/v0.1",
            "locations": [
                {
                    "object_id": spec.object_id,
                    "remote_key_sha256": _sha(spec.remote_key),
                    "receipt_relative": spec.receipt_relative,
                    "size_bytes": spec.size_bytes,
                }
                for spec in sorted(specs, key=lambda item: item.object_id)
            ],
        }
    )


def _manifest_for_specs(
    archive_id: str,
    specs: Sequence[FormalAdoptionSpec],
    *,
    operation_evidence: Mapping[str, Any] | None = None,
) -> ExactOperationManifest | None:
    items: list[ExactOperationItem] = []
    for ordinal, spec in enumerate(specs):
        items.append(
            ExactOperationItem(
                ordinal=ordinal,
                item_id="item:" + hashlib.sha256(spec.receipt_relative.encode("ascii")).hexdigest(),
                target_kind="object_storage_formal_adoption_receipt",
                target_ref=spec.receipt_relative,
                target_identity_sha256=spec.target_identity_sha256,
                fields=(
                    ExactFieldEffect(
                        field_ref="remote_head_verification",
                        pre_sha256=hash_field_value(None),
                        post_sha256=hash_field_value(spec.receipt_token),
                        source_sha256=hash_field_value(spec.source_token),
                    ),
                ),
            )
        )
    adoption_specs = [item for item in specs if item.formal_adoption_eligible]
    if adoption_specs:
        batch_token = _manifest_batch_token(adoption_specs)
        source_token = _canonical(
            {
                "schema_version": "wom-kit/object-storage-formal-adoption-manifest-source/v0.1",
                "source_tokens": [_sha_bytes(item.source_token) for item in adoption_specs],
            }
        )
        items.append(
            ExactOperationItem(
                ordinal=len(items),
                item_id="item:" + hashlib.sha256(MANIFEST_TARGET_REF.encode("ascii")).hexdigest(),
                target_kind="object_storage_formal_adoption_manifest_batch",
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
                        field_ref="verified_locations",
                        pre_sha256=hash_field_value(None),
                        post_sha256=hash_field_value(batch_token),
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
        operation_evidence=operation_evidence,
    )


def _operation_evidence(
    *,
    counts: Mapping[str, int],
    source_inventory_sha256: str,
    key_map_sha256: str,
    conflict_batches: Sequence[ConflictBatch],
) -> dict[str, Any]:
    return {
        "schema": "wom-kit/r2-formal-adoption-evidence/v1",
        "counts": {
            "bytes_preservation_candidate_count": int(
                counts["bytes_preservation_candidate_count"]
            ),
            "conflicting_definition_count": int(counts["conflicting_definition_count"]),
            "existing_formal_adoption_verification_count": int(
                counts["existing_formal_adoption_verification_count"]
            ),
            "formal_adoption_planned_count": int(counts["formal_adoption_planned_count"]),
            "manifest_row_count": int(counts["manifest_row_count"]),
            "manifest_scope_remote_key_verified_object_count": int(
                counts["manifest_scope_remote_key_verified_object_count"]
            ),
            "official_deduplicated_wom_uploaded_evidence_object_count": int(
                counts["official_deduplicated_wom_uploaded_evidence_object_count"]
            ),
            "remote_query_planned_count": int(counts["remote_query_planned_count"]),
            "unique_object_count": int(counts["unique_object_count"]),
        },
        "digests": {
            "conflict_batch_set_sha256": _sha(
                [item.public_document() for item in conflict_batches]
            ),
            "key_map_sha256": key_map_sha256,
            "source_inventory_sha256": source_inventory_sha256,
        },
        "private_values_echoed": False,
    }


def plan_object_storage_formal_adoption(
    archive_root: Path | str,
    *,
    key_map_path: Path,
    provider_kind: str = "cloudflare-r2",
    store_ref: str,
    judgment_path: Path | None = None,
    only: str | None = None,
    max_objects: int | None = None,
    progress: Callable[[str, str, int | None, int | None], None] | None = None,
) -> ObjectStorageFormalAdoptionPlan:
    try:
        root = archive_services.require_existing_archive_root(archive_root)
        archive_id = archive_services.read_archive_id(root)
    except Exception:
        raise _fail("object_storage_adoption_archive_invalid") from None
    provider = str(provider_kind or "").strip().lower()
    store = str(store_ref or "").strip()
    if (
        provider not in archive_services.OBJECT_STORAGE_ALLOWED_PROVIDERS
        or not archive_services.safe_object_storage_ref(store)
    ):
        raise _fail("object_storage_adoption_plan_invalid")
    key_map_file = Path(key_map_path)
    key_map_sha = _plain_file_sha256(
        key_map_file, max_bytes=_MAX_KEY_MAP_BYTES, code="object_storage_adoption_key_map_invalid"
    )
    loaded = archive_services.read_object_storage_key_map(
        key_map_file, max_entries=archive_services.OBJECT_STORAGE_KEY_MAP_MAX_ENTRIES
    )
    if loaded.get("blockers"):
        raise _fail("object_storage_adoption_key_map_invalid")
    key_map = loaded.get("map") or {}
    decisions, judgment_sha = _read_judgments(judgment_path)
    rows, groups = preservation._read_manifest_groups(root, progress=progress)
    inventory, _unique = preservation._inventory(rows, groups)
    batches = _conflict_batches(groups, decisions)
    selected = _object_id(only) if only else None
    specs: list[FormalAdoptionSpec] = []
    mapped_missing = 0
    mapped_conflicts = 0
    existing_adoption = 0
    pending_adoption = 0
    mapped_total = 0
    for digest, remote_key in sorted(key_map.items()):
        object_id = "sha256:" + digest
        if selected is not None and object_id != selected:
            continue
        group = groups.get(object_id)
        if group is None:
            mapped_missing += 1
            continue
        mapped_total += 1
        sizes = {row.get("size_bytes") for row in group}
        if len(sizes) != 1 or not all(type(value) is int and value >= 0 for value in sizes):
            raise _fail("object_storage_adoption_plan_invalid")
        if len(group) > 1:
            classification = "conflicting_definition_review_required"
            mapped_conflicts += 1
        elif _matching_adoption_location(
            group[0], provider_kind=provider, store_ref=store, remote_key=remote_key
        ):
            classification = "existing_formal_adoption"
            existing_adoption += 1
        else:
            classification = "pending_formal_adoption"
            pending_adoption += 1
        source_token = _source_token(
            object_id=object_id, rows=group, remote_key=remote_key, key_map_sha256=key_map_sha
        )
        source_inventory_sha = str(inventory["source_inventory_sha256"])
        receipt_relative = _receipt_relative(object_id, source_inventory_sha)
        token = _receipt_token(
            object_id=object_id,
            size_bytes=next(iter(sizes)),
            provider_kind=provider,
            store_ref=store,
            remote_key=remote_key,
            classification=classification,
            source_inventory_sha256=source_inventory_sha,
        )
        specs.append(
            FormalAdoptionSpec(
                object_id=object_id,
                size_bytes=next(iter(sizes)),
                remote_key=remote_key,
                classification=classification,
                receipt_relative=receipt_relative,
                receipt_token=token,
                source_token=source_token,
                target_identity_sha256=_target_identity(
                    archive_id=archive_id,
                    object_id=object_id,
                    receipt_relative=receipt_relative,
                    source_token=source_token,
                ),
            )
        )
    if selected is not None and not specs:
        raise _fail("object_storage_adoption_no_writes")
    if max_objects is not None and (
        type(max_objects) is not int or max_objects < 1 or len(specs) > max_objects
    ):
        raise _fail("object_storage_adoption_plan_invalid")
    source_inventory_sha = _sha(
        {
            "manifest_inventory_sha256": inventory["source_inventory_sha256"],
            "key_map_sha256": key_map_sha,
            "judgment_sha256": judgment_sha,
            "selected_only": selected,
        }
    )
    # Rebind receipt names/tokens to the complete input inventory (including the
    # key map and optional judgments), rather than only the manifest inventory.
    rebound: list[FormalAdoptionSpec] = []
    for spec in specs:
        relative = _receipt_relative(spec.object_id, source_inventory_sha)
        token = _receipt_token(
            object_id=spec.object_id,
            size_bytes=spec.size_bytes,
            provider_kind=provider,
            store_ref=store,
            remote_key=spec.remote_key,
            classification=spec.classification,
            source_inventory_sha256=source_inventory_sha,
        )
        rebound.append(
            FormalAdoptionSpec(
                object_id=spec.object_id,
                size_bytes=spec.size_bytes,
                remote_key=spec.remote_key,
                classification=spec.classification,
                receipt_relative=relative,
                receipt_token=token,
                source_token=spec.source_token,
                target_identity_sha256=_target_identity(
                    archive_id=archive_id,
                    object_id=spec.object_id,
                    receipt_relative=relative,
                    source_token=spec.source_token,
                ),
            )
        )
    final_specs = tuple(rebound)
    counts = {
        "manifest_row_count": int(inventory["manifest_row_count"]),
        "unique_object_count": int(inventory["unique_object_count"]),
        "key_map_entry_count": len(key_map),
        "remote_query_planned_count": mapped_total,
        "formal_adoption_planned_count": pending_adoption,
        "existing_formal_adoption_verification_count": existing_adoption,
        "conflicting_definition_count": int(inventory["conflicting_definition_count"]),
        "mapped_conflicting_definition_count": mapped_conflicts,
        "mapped_missing_manifest_count": mapped_missing,
        "manifest_scope_remote_key_verified_object_count": int(
            inventory["manifest_scope_remote_key_verified_object_count"]
        ),
        "official_deduplicated_wom_uploaded_evidence_object_count": int(
            inventory["official_deduplicated_wom_uploaded_evidence_object_count"]
        ),
        "bytes_preservation_candidate_count": int(
            inventory["unique_local_without_remote_record_count"]
        ),
    }
    operation_evidence = _operation_evidence(
        counts=counts,
        source_inventory_sha256=source_inventory_sha,
        key_map_sha256=key_map_sha,
        conflict_batches=batches,
    )
    return ObjectStorageFormalAdoptionPlan(
        archive_root=root,
        archive_id=archive_id,
        provider_kind=provider,
        store_ref=store,
        source_inventory_sha256=source_inventory_sha,
        key_map_sha256=key_map_sha,
        manifest=_manifest_for_specs(
            archive_id, final_specs, operation_evidence=operation_evidence
        ),
        specs=final_specs,
        conflict_batches=batches,
        counts=counts,
        key_map_path=key_map_file,
        judgment_path=Path(judgment_path) if judgment_path is not None else None,
    )


def _manifest_source_token(specs: Sequence[FormalAdoptionSpec]) -> bytes:
    return _canonical(
        {
            "schema_version": "wom-kit/object-storage-formal-adoption-manifest-source/v0.1",
            "source_tokens": [_sha_bytes(item.source_token) for item in specs],
        }
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, repr=False)
class ObjectStorageHeadQueryResult:
    state: str
    present: bool
    size_match: bool
    observed_size: int | None

    def public_document(self) -> dict[str, Any]:
        return {
            "schema_version": "wom-kit/object-storage-head-query-result/v0.1",
            "state": self.state,
            "present": self.present,
            "size_match": self.size_match,
            "observed_size": self.observed_size,
            "verification_scope": "remote_presence_and_size_not_content_hash",
            "remote_key_echoed": False,
            "provider_body_echoed": False,
        }


class ObjectStorageHeadQueryAdapter:
    """Privacy-safe R2/S3 HEAD classification without provider-body reflection."""

    def __init__(self, transport: archive_services.ObjectStorageTransport) -> None:
        self.transport = transport

    def query(
        self,
        *,
        remote_key: str,
        expected_size: int,
        heartbeat: Callable[[], None],
    ) -> ObjectStorageHeadQueryResult:
        heartbeat()
        try:
            result = self.transport.head_object(key=remote_key, presence_only=True)
        except Exception:
            return ObjectStorageHeadQueryResult("unavailable", False, False, None)
        heartbeat()
        if (
            result.get("presence_state") == "unavailable"
            or result.get("verification_state") == "unavailable"
        ):
            return ObjectStorageHeadQueryResult("unavailable", False, False, None)
        present = result.get("present") is True
        observed = result.get("size") if type(result.get("size")) is int else None
        if not present:
            return ObjectStorageHeadQueryResult("absent", False, False, observed)
        if observed != expected_size:
            return ObjectStorageHeadQueryResult("size_mismatch", True, False, observed)
        return ObjectStorageHeadQueryResult("verified_match", True, True, observed)


def _head_verify(
    transport: archive_services.ObjectStorageTransport,
    spec: FormalAdoptionSpec,
    *,
    heartbeat: Callable[[], None],
) -> None:
    result = ObjectStorageHeadQueryAdapter(transport).query(
        remote_key=spec.remote_key,
        expected_size=spec.size_bytes,
        heartbeat=heartbeat,
    )
    if result.state == "unavailable":
        raise _fail("object_storage_adoption_remote_unavailable")
    if result.state != "verified_match":
        raise _fail("object_storage_adoption_remote_mismatch")


def _receipt_document(
    plan: ObjectStorageFormalAdoptionPlan,
    spec: FormalAdoptionSpec,
    *,
    verified_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": RECEIPT_SCHEMA,
        "object_id": spec.object_id,
        "content_sha256": spec.object_id,
        "size_bytes": spec.size_bytes,
        "provider_kind": plan.provider_kind,
        "store_ref": plan.store_ref,
        "remote_key": spec.remote_key,
        "remote_key_sha256": _sha(spec.remote_key),
        "remote_key_verification": "presence_size",
        "remote_key_verified": True,
        "provider_confirmation_by_wom_kit": True,
        "byte_verification_by_wom_kit": False,
        "verification_scope": "remote_presence_and_size_not_content_hash",
        "classification": spec.classification,
        "formal_adoption_eligible": spec.formal_adoption_eligible,
        "formal_adoption_status": (
            "verified_pending_manifest_projection"
            if spec.formal_adoption_eligible
            else (
                "already_adopted_verified"
                if spec.classification == "existing_formal_adoption"
                else "conflict_review_required_verified"
            )
        ),
        "source_inventory_sha256": plan.source_inventory_sha256,
        "receipt_state_sha256": _sha_bytes(spec.receipt_token),
        "verified_at": verified_at,
        "provider_put_called": False,
        "automatic_conflict_merge": False,
        "private_values_echoed": False,
        "credential_values_echoed": False,
        "provider_url_echoed": False,
        "local_path_echoed": False,
    }


def _receipt_path(plan: ObjectStorageFormalAdoptionPlan, spec: FormalAdoptionSpec) -> Path:
    return archive_services.archive_internal_path(plan.archive_root, spec.receipt_relative)


def _read_receipt(
    plan: ObjectStorageFormalAdoptionPlan, spec: FormalAdoptionSpec
) -> dict[str, Any] | None:
    path = _receipt_path(plan, spec)
    if not path.exists():
        return None
    try:
        raw = path.read_bytes()
        if len(raw) > 64 * 1024:
            raise ValueError("large")
        document = preservation._strict_json(raw)
        verified_at = document.get("verified_at")
        datetime.fromisoformat(str(verified_at).replace("Z", "+00:00"))
    except Exception:
        raise _fail("object_storage_adoption_receipt_conflict") from None
    expected = _receipt_document(plan, spec, verified_at=str(verified_at))
    if document != expected:
        raise _fail("object_storage_adoption_receipt_conflict")
    return document


def _create_receipt(
    plan: ObjectStorageFormalAdoptionPlan, spec: FormalAdoptionSpec
) -> dict[str, Any]:
    existing = _read_receipt(plan, spec)
    if existing is not None:
        return existing
    document = _receipt_document(plan, spec, verified_at=_now_iso())
    raw = _canonical(document) + b"\n"
    preservation._create_or_match_receipt(
        plan.archive_root,
        spec.receipt_relative,
        raw,
        max_bytes=64 * 1024,
        failure_code="object_storage_adoption_receipt_conflict",
    )
    return document


def _owned_location(
    plan: ObjectStorageFormalAdoptionPlan,
    spec: FormalAdoptionSpec,
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    location = archive_services.object_storage_wom_uploaded_location(
        digest=spec.object_id.removeprefix("sha256:"),
        provider_kind=plan.provider_kind,
        store_ref=plan.store_ref,
        execution_receipt_ref=spec.receipt_relative,
        uploaded_at=str(receipt["verified_at"]),
        key_strategy=archive_services.OBJECT_STORAGE_UPLOAD_KEY_STRATEGY_PREFIX,
        remote_key=spec.remote_key,
        remote_key_verified=True,
        remote_key_verification="presence_size",
        remote_size=spec.size_bytes,
    )
    location["formal_adoption_verified_at"] = str(receipt["verified_at"])
    location["provider_upload_time_known"] = False
    location["byte_verification_by_wom_kit"] = False
    return location


def _location_owned_by_spec(
    location: Mapping[str, Any],
    plan: ObjectStorageFormalAdoptionPlan,
    spec: FormalAdoptionSpec,
) -> bool:
    return (
        location.get("provider") == "object_storage"
        and location.get("availability") == "wom_uploaded"
        and location.get("provider_kind") == plan.provider_kind
        and location.get("store_ref") == plan.store_ref
        and location.get("remote_key") == spec.remote_key
        and location.get("execution_receipt_ref") == spec.receipt_relative
        and location.get("remote_key_verified") is True
        and location.get("remote_key_verification") == "presence_size"
        and location.get("provider_confirmation_by_wom_kit") is True
        and location.get("byte_verification_by_wom_kit") is False
    )


def _load_current_rows(plan: ObjectStorageFormalAdoptionPlan) -> list[dict[str, Any]]:
    rows, _groups = preservation._read_manifest_groups(plan.archive_root, progress=None)
    return rows


def _batch_state(plan: ObjectStorageFormalAdoptionPlan) -> bytes | None:
    specs = plan.adoption_specs
    if not specs:
        return None
    by_id = {item.object_id: item for item in specs}
    seen: dict[str, int] = {item.object_id: 0 for item in specs}
    matched: dict[str, int] = {item.object_id: 0 for item in specs}
    for row in _load_current_rows(plan):
        object_id = _object_id(row.get("object_id"))
        spec = by_id.get(object_id)
        if spec is None:
            continue
        seen[object_id] += 1
        matched[object_id] += sum(
            1 for location in _locations(row) if _location_owned_by_spec(location, plan, spec)
        )
    if any(value != 1 for value in seen.values()) or any(value > 1 for value in matched.values()):
        raise _fail("object_storage_adoption_plan_changed")
    present = sum(value == 1 for value in matched.values())
    if present == 0:
        return None
    if present != len(specs):
        raise _fail("object_storage_adoption_plan_changed")
    return _manifest_batch_token(specs)


def _apply_manifest_batch(
    plan: ObjectStorageFormalAdoptionPlan, *, destination_present: bool
) -> int:
    specs = plan.adoption_specs
    if not specs:
        return 0
    by_id = {item.object_id: item for item in specs}
    receipts = {item.object_id: _read_receipt(plan, item) for item in specs}
    if destination_present and any(value is None for value in receipts.values()):
        raise _fail("object_storage_adoption_plan_changed")
    manifest_path = archive_services.archive_internal_path(
        plan.archive_root, "objects/manifests/files.jsonl"
    )
    changed = 0
    seen: dict[str, int] = {item.object_id: 0 for item in specs}
    with archive_services._ObjetCaptureManifestLock(plan.archive_root):
        rewritten: list[str] = []
        try:
            raw_lines = manifest_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            raise _fail("object_storage_adoption_plan_changed") from None
        for raw_line in raw_lines:
            if not raw_line.strip():
                rewritten.append(raw_line)
                continue
            try:
                row = json.loads(raw_line)
                object_id = _object_id(row.get("object_id"))
            except Exception:
                raise _fail("object_storage_adoption_plan_changed") from None
            spec = by_id.get(object_id)
            if spec is None:
                rewritten.append(raw_line)
                continue
            seen[object_id] += 1
            current_source = _source_token(
                object_id=object_id,
                rows=[row],
                remote_key=spec.remote_key,
                key_map_sha256=plan.key_map_sha256,
            )
            if current_source != spec.source_token:
                raise _fail("object_storage_adoption_plan_changed")
            locations = _locations(row)
            owned = [item for item in locations if _location_owned_by_spec(item, plan, spec)]
            if len(owned) > 1:
                raise _fail("object_storage_adoption_plan_changed")
            if destination_present and not owned:
                locations.append(_owned_location(plan, spec, receipts[object_id] or {}))
                changed += 1
            elif not destination_present and owned:
                locations = [
                    item for item in locations if not _location_owned_by_spec(item, plan, spec)
                ]
                changed += 1
            row["locations"] = locations
            rewritten.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
        if any(value != 1 for value in seen.values()):
            raise _fail("object_storage_adoption_plan_changed")
        if changed:
            archive_services._atomic_write_text(manifest_path, "\n".join(rewritten) + "\n")
    return changed


class _Payloads:
    def __init__(self, plan: ObjectStorageFormalAdoptionPlan) -> None:
        self.values: dict[tuple[str, str], tuple[bytes | None, bytes, bytes]] = {}
        if plan.manifest is None:
            return
        for item, spec in zip(plan.manifest.items, plan.specs):
            self.values[(item.item_id, "remote_head_verification")] = (
                None,
                spec.receipt_token,
                spec.source_token,
            )
        if plan.adoption_specs:
            item = plan.manifest.items[-1]
            self.values[(item.item_id, "verified_locations")] = (
                None,
                _manifest_batch_token(plan.adoption_specs),
                _manifest_source_token(plan.adoption_specs),
            )

    def field_value(
        self,
        *,
        item_id: str,
        field_ref: str,
        state: str,
        heartbeat: Callable[[], None],
    ) -> bytes | None:
        heartbeat()
        values = self.values.get((item_id, field_ref))
        if values is None or state not in {"pre", "post", "source"}:
            raise ValueError("payload boundary")
        return values[{"pre": 0, "post": 1, "source": 2}[state]]


class _Verifier:
    def __init__(
        self,
        plan: ObjectStorageFormalAdoptionPlan,
        transport: archive_services.ObjectStorageTransport,
    ) -> None:
        self.plan = plan
        self.transport = transport
        self.by_target = {item.receipt_relative: item for item in plan.specs}
        self.remote_verified: set[str] = set()
        _rows, self.groups = preservation._read_manifest_groups(plan.archive_root, progress=None)

    def target_identity_sha256(
        self,
        *,
        target_kind: str,
        target_ref: str,
        heartbeat: Callable[[], None],
    ) -> str:
        heartbeat()
        if target_kind == "object_storage_formal_adoption_receipt":
            spec = self.by_target.get(target_ref)
            if spec is None:
                raise ValueError("target boundary")
            group = self.groups.get(spec.object_id)
            if not group or _source_token(
                object_id=spec.object_id,
                rows=group,
                remote_key=spec.remote_key,
                key_map_sha256=self.plan.key_map_sha256,
            ) != spec.source_token:
                raise ValueError("source drift")
            return spec.target_identity_sha256
        if (
            target_kind == "object_storage_formal_adoption_manifest_batch"
            and target_ref == MANIFEST_TARGET_REF
        ):
            source = _manifest_source_token(self.plan.adoption_specs)
            return _sha(
                {
                    "archive_id": self.plan.archive_id,
                    "target_ref": MANIFEST_TARGET_REF,
                    "source_sha256": _sha_bytes(source),
                }
            )
        raise ValueError("target boundary")

    def read_field(
        self,
        *,
        target_kind: str,
        target_ref: str,
        field_ref: str,
        heartbeat: Callable[[], None],
    ) -> bytes | None:
        if target_kind == "object_storage_formal_adoption_receipt":
            spec = self.by_target.get(target_ref)
            if spec is None or field_ref != "remote_head_verification":
                raise ValueError("read boundary")
            receipt = _read_receipt(self.plan, spec)
            if receipt is None:
                return None
            if target_ref not in self.remote_verified:
                _head_verify(self.transport, spec, heartbeat=heartbeat)
                self.remote_verified.add(target_ref)
            return spec.receipt_token
        if (
            target_kind == "object_storage_formal_adoption_manifest_batch"
            and target_ref == MANIFEST_TARGET_REF
            and field_ref == "verified_locations"
        ):
            return _batch_state(self.plan)
        raise ValueError("read boundary")


class _Writer:
    def __init__(
        self,
        plan: ObjectStorageFormalAdoptionPlan,
        transport: archive_services.ObjectStorageTransport,
    ) -> None:
        self.plan = plan
        self.transport = transport
        self.by_target = {item.receipt_relative: item for item in plan.specs}
        self.remote_head_verified_count = 0
        self.receipts_created_count = 0
        self.manifest_update_count = 0

    def write_field(
        self,
        *,
        target_kind: str,
        target_ref: str,
        field_ref: str,
        value: bytes | None,
        heartbeat: Callable[[], None],
    ) -> None:
        if target_kind == "object_storage_formal_adoption_receipt":
            spec = self.by_target.get(target_ref)
            if spec is None or field_ref != "remote_head_verification":
                raise ValueError("write boundary")
            if value is None:
                receipt = _read_receipt(self.plan, spec)
                if receipt is not None:
                    _receipt_path(self.plan, spec).unlink()
                return
            if value != spec.receipt_token:
                raise ValueError("write boundary")
            existing = _read_receipt(self.plan, spec)
            if existing is None:
                _head_verify(self.transport, spec, heartbeat=heartbeat)
                self.remote_head_verified_count += 1
                _create_receipt(self.plan, spec)
                self.receipts_created_count += 1
            return
        if (
            target_kind == "object_storage_formal_adoption_manifest_batch"
            and target_ref == MANIFEST_TARGET_REF
            and field_ref == "verified_locations"
        ):
            expected = _manifest_batch_token(self.plan.adoption_specs)
            if value not in {None, expected}:
                raise ValueError("write boundary")
            self.manifest_update_count += _apply_manifest_batch(
                self.plan, destination_present=value is not None
            )
            return
        raise ValueError("write boundary")


def _execution_adapters(
    plan: ObjectStorageFormalAdoptionPlan,
    transport: archive_services.ObjectStorageTransport,
) -> tuple[_Payloads, _Writer, _Verifier]:
    return _Payloads(plan), _Writer(plan, transport), _Verifier(plan, transport)


def _approval_binding(plan: ObjectStorageFormalAdoptionPlan) -> ExactOperationApprovalBinding:
    if plan.manifest is None:
        raise _fail("object_storage_adoption_no_writes")
    try:
        return exact_operation_manifest_approval_binding(
            plan.manifest,
            operation=ExactHumanApprovalOperation.object_storage_formal_adoption,
            archive_id=plan.archive_id,
            warnings=(
                "remote_presence_and_size_is_not_content_hash_verification",
                "conflicting_definitions_are_review_only",
                "provider_upload_time_is_unknown_for_formal_adoption",
            ),
        )
    except Exception:
        raise _fail("object_storage_adoption_plan_invalid") from None


def object_storage_formal_adoption_context(
    plan: ObjectStorageFormalAdoptionPlan, *, reviewer_claim: str
) -> ExactHumanApprovalContext:
    reviewer = str(reviewer_claim or "").strip()
    if not reviewer or not plan.approveable:
        raise _fail("object_storage_adoption_plan_invalid")
    return _approval_binding(plan).context(
        archive_id=plan.archive_id, reviewer_claim=reviewer
    )


def _assert_approved(
    plan: ObjectStorageFormalAdoptionPlan,
    claim: _ClaimedExactHumanApproval,
    context: ExactHumanApprovalContext,
) -> ExactOperationApprovalAuthority:
    binding = _approval_binding(plan)
    if (
        type(claim) is not _ClaimedExactHumanApproval
        or context.operation is not ExactHumanApprovalOperation.object_storage_formal_adoption
        or context.plan_sha256 != binding.plan_sha256
        or context.target_binding_sha256 != binding.target_binding_sha256
    ):
        raise _fail("object_storage_adoption_approval_required")
    try:
        reference = _ClaimedExactHumanApproval.assert_ready_for_context(claim, context)
        return ExactOperationApprovalAuthority.from_reference(reference)
    except (ExactHumanApprovalError, ExactOperationManifestError):
        raise _fail("object_storage_adoption_approval_required") from None


def _control_relative(manifest_sha256: str) -> str:
    if _SHA256_RE.fullmatch(manifest_sha256) is None:
        raise _fail("object_storage_adoption_control_invalid")
    return (
        f"{CONTROL_ROOT}/{manifest_sha256.removeprefix('sha256:')}"
        ".object-storage-formal-adoption.json"
    )


def _control_document(plan: ObjectStorageFormalAdoptionPlan) -> dict[str, Any]:
    if plan.manifest is None:
        raise _fail("object_storage_adoption_no_writes")
    basis = {
        "schema_version": CONTROL_SCHEMA,
        "archive_id": plan.archive_id,
        "provider_kind": plan.provider_kind,
        "store_ref": plan.store_ref,
        "source_inventory_sha256": plan.source_inventory_sha256,
        "key_map_sha256": plan.key_map_sha256,
        "counts": dict(plan.counts),
        "conflict_batches": [item.public_document() for item in plan.conflict_batches],
        "manifest": plan.manifest.document(),
        "specs": [
            {
                "object_id": item.object_id,
                "size_bytes": item.size_bytes,
                "remote_key": item.remote_key,
                "classification": item.classification,
                "receipt_relative": item.receipt_relative,
                "receipt_token_sha256": _sha_bytes(item.receipt_token),
                "source_token_sha256": _sha_bytes(item.source_token),
                "target_identity_sha256": item.target_identity_sha256,
            }
            for item in plan.specs
        ],
        "private_control_document": True,
    }
    return {**basis, "control_sha256": _sha(basis)}


def _persist_control(plan: ObjectStorageFormalAdoptionPlan) -> str:
    if plan.manifest is None:
        raise _fail("object_storage_adoption_no_writes")
    relative = _control_relative(plan.manifest.manifest_sha256)
    preservation._create_or_match_receipt(
        plan.archive_root,
        relative,
        preservation._canonical_control_bytes(_control_document(plan)),
        max_bytes=64 * 1024 * 1024,
        failure_code="object_storage_adoption_control_invalid",
    )
    return relative


def load_object_storage_formal_adoption_plan(
    archive_root: Path | str, *, manifest_sha256: str
) -> ObjectStorageFormalAdoptionPlan:
    try:
        root = archive_services.require_existing_archive_root(archive_root)
        archive_id = archive_services.read_archive_id(root)
        path = archive_services.archive_internal_path(root, _control_relative(manifest_sha256))
        raw = path.read_bytes()
        if len(raw) > 64 * 1024 * 1024:
            raise ValueError("large")
        document = preservation._strict_json(raw)
    except Exception:
        raise _fail("object_storage_adoption_control_invalid") from None
    supplied = document.pop("control_sha256", None)
    if (
        document.get("schema_version") != CONTROL_SCHEMA
        or document.get("private_control_document") is not True
        or not isinstance(supplied, str)
        or not hmac.compare_digest(supplied, _sha(document))
        or document.get("archive_id") != archive_id
    ):
        raise _fail("object_storage_adoption_control_invalid")
    try:
        manifest = ExactOperationManifest.from_document(document["manifest"])
        provider = document["provider_kind"]
        store = document["store_ref"]
        source_inventory_sha = document["source_inventory_sha256"]
        key_map_sha = document["key_map_sha256"]
        counts = document["counts"]
        raw_specs = document["specs"]
        _rows, groups = preservation._read_manifest_groups(root, progress=None)
    except Exception:
        raise _fail("object_storage_adoption_control_invalid") from None
    if (
        manifest.manifest_sha256 != manifest_sha256
        or manifest.operation != OPERATION
        or provider not in archive_services.OBJECT_STORAGE_ALLOWED_PROVIDERS
        or not archive_services.safe_object_storage_ref(store)
        or _SHA256_RE.fullmatch(str(source_inventory_sha)) is None
        or _SHA256_RE.fullmatch(str(key_map_sha)) is None
        or not isinstance(counts, dict)
        or not isinstance(raw_specs, list)
    ):
        raise _fail("object_storage_adoption_control_invalid")
    specs: list[FormalAdoptionSpec] = []
    for raw_spec in raw_specs:
        try:
            object_id = _object_id(raw_spec["object_id"])
            remote_key = raw_spec["remote_key"]
            size = raw_spec["size_bytes"]
            classification = raw_spec["classification"]
            receipt_relative = raw_spec["receipt_relative"]
            group = groups[object_id]
        except Exception:
            raise _fail("object_storage_adoption_control_invalid") from None
        if (
            type(remote_key) is not str
            or not archive_services.safe_object_storage_remote_key(remote_key)
            or not archive_services.object_storage_map_key_binds_digest_segment(
                remote_key, object_id.removeprefix("sha256:")
            )
            or type(size) is not int
            or {row.get("size_bytes") for row in group} != {size}
            or classification
            not in {
                "pending_formal_adoption",
                "existing_formal_adoption",
                "conflicting_definition_review_required",
            }
        ):
            raise _fail("object_storage_adoption_control_invalid")
        source_token = _source_token(
            object_id=object_id,
            rows=group,
            remote_key=remote_key,
            key_map_sha256=key_map_sha,
        )
        receipt_token = _receipt_token(
            object_id=object_id,
            size_bytes=size,
            provider_kind=provider,
            store_ref=store,
            remote_key=remote_key,
            classification=classification,
            source_inventory_sha256=source_inventory_sha,
        )
        identity = _target_identity(
            archive_id=archive_id,
            object_id=object_id,
            receipt_relative=receipt_relative,
            source_token=source_token,
        )
        if (
            receipt_relative != _receipt_relative(object_id, source_inventory_sha)
            or raw_spec.get("receipt_token_sha256") != _sha_bytes(receipt_token)
            or raw_spec.get("source_token_sha256") != _sha_bytes(source_token)
            or raw_spec.get("target_identity_sha256") != identity
        ):
            raise _fail("object_storage_adoption_plan_changed")
        specs.append(
            FormalAdoptionSpec(
                object_id=object_id,
                size_bytes=size,
                remote_key=remote_key,
                classification=classification,
                receipt_relative=receipt_relative,
                receipt_token=receipt_token,
                source_token=source_token,
                target_identity_sha256=identity,
            )
        )
    batches: list[ConflictBatch] = []
    for item in document.get("conflict_batches") or []:
        batches.append(
            ConflictBatch(
                batch_fingerprint=item["batch_fingerprint"],
                group_count=item["group_count"],
                reason_codes=tuple(item["reason_codes"]),
                judgment=item["judgment"],
            )
        )
    rebuilt = _manifest_for_specs(
        archive_id,
        specs,
        operation_evidence=(
            manifest.operation_evidence.document()
            if manifest.operation_evidence is not None
            else None
        ),
    )
    if rebuilt is None or rebuilt.document() != manifest.document():
        raise _fail("object_storage_adoption_control_invalid")
    return ObjectStorageFormalAdoptionPlan(
        archive_root=root,
        archive_id=archive_id,
        provider_kind=provider,
        store_ref=store,
        source_inventory_sha256=source_inventory_sha,
        key_map_sha256=key_map_sha,
        manifest=manifest,
        specs=tuple(specs),
        conflict_batches=tuple(batches),
        counts={str(key): int(value) for key, value in counts.items()},
        loaded_from_control=True,
    )


def _fresh_revalidated(plan: ObjectStorageFormalAdoptionPlan) -> ObjectStorageFormalAdoptionPlan:
    if plan.loaded_from_control:
        return plan
    if plan.key_map_path is None or plan.manifest is None:
        raise _fail("object_storage_adoption_plan_changed")
    current = plan_object_storage_formal_adoption(
        plan.archive_root,
        key_map_path=plan.key_map_path,
        provider_kind=plan.provider_kind,
        store_ref=plan.store_ref,
        judgment_path=plan.judgment_path,
    )
    if current.manifest is None or current.manifest.document() != plan.manifest.document():
        raise _fail("object_storage_adoption_plan_changed")
    return current


def _apply_with_store(
    plan: ObjectStorageFormalAdoptionPlan,
    authority: ExactOperationApprovalAuthority,
    transport: archive_services.ObjectStorageTransport,
    checkpoints: FileExactOperationCheckpointStore,
    *,
    resume: bool,
    progress_hook: Callable[[ExactOperationProgress], None] | None,
) -> dict[str, Any]:
    if plan.manifest is None:
        raise _fail("object_storage_adoption_no_writes")
    payloads, writer, verifier = _execution_adapters(plan, transport)
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
    return {
        "schema_version": RESULT_SCHEMA,
        "ok": core.get("status") == "completed",
        "state": "formal_adoption_completed",
        "manifest_sha256": plan.manifest.manifest_sha256,
        "execution": core,
        "remote_query_verified_count": len(plan.specs),
        "formal_adoption_count": len(plan.adoption_specs),
        "existing_adoption_reverified_count": int(
            plan.counts["existing_formal_adoption_verification_count"]
        ),
        "conflict_review_verified_count": int(
            plan.counts["mapped_conflicting_definition_count"]
        ),
        "manifest_location_updates": writer.manifest_update_count,
        "central_manifest_rewrite_count_ceiling": 1,
        "provider_head_called": True,
        "provider_put_called": False,
        "independent_head_verification": True,
        "content_hash_verified": False,
        "private_values_echoed": False,
        "remote_keys_echoed": False,
        "object_ids_echoed": False,
    }


def _apply_core(
    plan: ObjectStorageFormalAdoptionPlan,
    claim: _ClaimedExactHumanApproval,
    *,
    context: ExactHumanApprovalContext,
    transport_factory: Callable[[], archive_services.ObjectStorageTransport],
    resume: bool = False,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
) -> dict[str, Any]:
    current = _fresh_revalidated(plan)
    authority = _assert_approved(current, claim, context)
    with exact_operation_writer_lock(current.archive_root) as writer_lock:
        _persist_control(current)
        checkpoints = FileExactOperationCheckpointStore(
            current.archive_root, writer_lock=writer_lock
        )
        try:
            transport = transport_factory()
        except Exception:
            raise _fail("object_storage_adoption_remote_unavailable") from None
        if transport is None:
            raise _fail("object_storage_adoption_remote_unavailable")
        return _apply_with_store(
            current,
            authority,
            transport,
            checkpoints,
            resume=resume,
            progress_hook=progress_hook,
        )


def execute_object_storage_formal_adoption(
    plan: ObjectStorageFormalAdoptionPlan,
    *,
    reviewer_claim: str,
    transport_factory: Callable[[], archive_services.ObjectStorageTransport],
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
) -> dict[str, Any]:
    if not plan.approveable:
        raise _fail("object_storage_adoption_no_writes")
    context = object_storage_formal_adoption_context(plan, reviewer_claim=reviewer_claim)
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


def resume_object_storage_formal_adoption(
    plan: ObjectStorageFormalAdoptionPlan,
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
        raise _fail("object_storage_adoption_resume_invalid")
    context = object_storage_formal_adoption_context(plan, reviewer_claim=reviewer_claim)
    with exact_operation_writer_lock(plan.archive_root) as writer_lock:
        checkpoints = FileExactOperationCheckpointStore(
            plan.archive_root, writer_lock=writer_lock
        )

        def writer(claim: _ClaimedExactHumanApproval) -> Mapping[str, Any]:
            authority = _assert_approved(plan, claim, context)
            actual = exact_operation_execution_sha256(
                plan.manifest, approval_authority=authority
            )
            if not hmac.compare_digest(actual, execution_sha256):
                raise _fail("object_storage_adoption_resume_invalid")
            try:
                transport = transport_factory()
            except Exception:
                raise _fail("object_storage_adoption_remote_unavailable") from None
            return _apply_with_store(
                plan,
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
            writer,
            key_provider=key_provider,
        )


def verify_object_storage_formal_adoption(
    plan: ObjectStorageFormalAdoptionPlan,
    *,
    transport: archive_services.ObjectStorageTransport,
    heartbeat: Callable[[], None] | None = None,
) -> dict[str, Any]:
    if plan.manifest is None:
        raise _fail("object_storage_adoption_plan_invalid")
    _payloads, _writer, verifier = _execution_adapters(plan, transport)
    result = verify_exact_operation(
        plan.manifest, verifier=verifier, state="post", heartbeat=heartbeat
    )
    return {
        "schema_version": VERIFY_SCHEMA,
        "ok": result["all_match"],
        "manifest_sha256": plan.manifest.manifest_sha256,
        "remote_query_verified_count": len(plan.specs) if result["all_match"] else 0,
        "formal_adoption_count": len(plan.adoption_specs) if result["all_match"] else 0,
        "verification": result,
        "provider_head_called": True,
        "provider_put_called": False,
        "writes_performed": False,
        "remote_keys_echoed": False,
    }


__all__ = [
    "ConflictBatch",
    "FormalAdoptionSpec",
    "ObjectStorageAdoptionError",
    "ObjectStorageFormalAdoptionPlan",
    "ObjectStorageHeadQueryAdapter",
    "ObjectStorageHeadQueryResult",
    "execute_object_storage_formal_adoption",
    "load_object_storage_formal_adoption_plan",
    "object_storage_formal_adoption_context",
    "plan_object_storage_formal_adoption",
    "resume_object_storage_formal_adoption",
    "verify_object_storage_formal_adoption",
]
