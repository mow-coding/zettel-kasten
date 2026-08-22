"""Exact formal adoption of existing object-storage bytes.

The legacy adopter rewrote the central object manifest once per object.  This
module instead plans one immutable, resumable HEAD-verification receipt per
mapped object and one final manifest projection.  Conflicting manifest
definitions are queried and classified, but are never merged or adopted
automatically.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import archive_services
from . import object_storage_preservation as preservation
from .exact_human_approval import exact_human_approval_archive_identity_sha256
from .exact_human_approval_windows import ExactHumanApprovalOperation
from .exact_operation_manifest import (
    ExactFieldEffect,
    ExactOperationItem,
    ExactOperationManifest,
    hash_field_value,
)


PLAN_SCHEMA = "wom-kit/object-storage-formal-adoption-plan/v0.1"
CONTROL_SCHEMA = "wom-kit/object-storage-formal-adoption-control/v0.1"
RECEIPT_SCHEMA = "wom-kit/object-storage-formal-adoption-receipt/v0.1"
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
    archive_id: str, specs: Sequence[FormalAdoptionSpec]
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
    )


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
    }
    return ObjectStorageFormalAdoptionPlan(
        archive_root=root,
        archive_id=archive_id,
        provider_kind=provider,
        store_ref=store,
        source_inventory_sha256=source_inventory_sha,
        key_map_sha256=key_map_sha,
        manifest=_manifest_for_specs(archive_id, final_specs),
        specs=final_specs,
        conflict_batches=batches,
        counts=counts,
        key_map_path=key_map_file,
    )


__all__ = [
    "ConflictBatch",
    "FormalAdoptionSpec",
    "ObjectStorageAdoptionError",
    "ObjectStorageFormalAdoptionPlan",
    "plan_object_storage_formal_adoption",
]
