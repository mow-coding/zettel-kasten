"""Exact, resumable upload of local Objet bytes under one native approval.

v0.4.33 (beta letter 164 ①③④) reopens ``object-storage-upload`` as the
composition of two writers that already exist in the v0.4 line:

* the **preservation PUT** of :mod:`object_storage_preservation` (v0.4.13):
  create-only PUT (``If-None-Match: *``), a whole-object GET re-hash before and
  after, a manifest-bound provider-call budget with write-ahead reservations,
  a private append-only ledger whose terminal row is written before anything
  public, and the fixed ``review_required`` outcome for a remote copy whose
  bytes differ;
* the **formal-adoption projection** of :mod:`object_storage_adoption`: one
  compare-and-swap rewrite of ``objects/manifests/files.jsonl`` under the
  manifest-index authority that adds a ``wom_uploaded`` location per verified
  object.

What is new is only the binding: the remote key is the v0.3 content-addressed
``sha256/<2>/<digest>`` so restore, offload, the gating matcher and the
client's existing v0.3 objects share one layout; the public receipt is the
v0.3 execution receipt (``receipts/providers/object-storage-executions/…
.object-storage-upload.json``) so Doctor, backup-evidence and the tier reader
keep working unchanged; and the receipts are created by the trailing
manifest-batch item *after* the projection, so ``manifest_update_applied``
is never a forward claim.

Boundaries: no provider call and no credential read in the plan; the plan is
refused (``local_bytes_missing``) when a manifest row claims local bytes that
are absent or the wrong size unless ``--local-bytes-only`` is set; a remote
copy with different bytes is never overwritten; the remote object is never
deleted; there is no tier gate (the approved manifest and the plan-time
provider-call ceiling bound the batch, as in preservation).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import archive_services
from . import object_storage_preservation as preservation
from . import object_storage_restore as restore
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


PLAN_SCHEMA = "wom-kit/object-storage-upload-plan/v0.1"
RESULT_SCHEMA = "wom-kit/object-storage-upload-result/v0.1"
VERIFY_SCHEMA = "wom-kit/object-storage-upload-verification/v0.1"
CONTROL_SCHEMA = "wom-kit/object-storage-upload-control/v0.1"
OPERATION = ExactHumanApprovalOperation.object_storage_bytes_upload.value
RECEIPT_ROOT = archive_services.OBJECT_STORAGE_EXECUTIONS_DIR
CONTROL_ROOT = preservation.CONTROL_ROOT
MANIFEST_TARGET_REF = "objects/manifests/files.jsonl#upload-local-location-batch"
RECEIPT_TARGET_KIND = "object_storage_upload_execution_receipt"
BATCH_TARGET_KIND = "object_storage_upload_manifest_batch"
REMOTE_KEY_LAYOUT = archive_services.OBJECT_STORAGE_UPLOAD_KEY_STRATEGY  # sha256_content_addressed
LIVE_TRANSPORT_PROVIDERS = frozenset({"cloudflare-r2", "generic-s3"})

STATUS_UPLOADED = "uploaded"
STATUS_SKIPPED_REMOTE_SAME = "skipped_remote_same"
STATUS_REVIEW_REQUIRED = "review_required"
_LEDGER_TO_PUBLIC = {
    "bytes_preserved": STATUS_UPLOADED,
    "already_remote_verified": STATUS_SKIPPED_REMOTE_SAME,
    "review_required": STATUS_REVIEW_REQUIRED,
}
_PUBLIC_STATUSES = (STATUS_UPLOADED, STATUS_SKIPPED_REMOTE_SAME, STATUS_REVIEW_REQUIRED)
WRITER_UNAVAILABLE_REASONS = (
    "provider_unsupported",
    "store_ref_invalid",
    "store_setup_missing",
    "store_setup_mismatch",
)
_MAX_RECEIPT_BYTES = 64 * 1024
_MAX_CONTROL_BYTES = 64 * 1024 * 1024
_SHA256_RE = preservation._SHA256_RE
_BARE_SHA256_RE = preservation._BARE_SHA256_RE


class ObjectStorageUploadError(RuntimeError):
    """Fixed-code failure that never retains a private path or provider body."""

    _CODES = {
        "object_storage_upload_archive_invalid",
        "object_storage_upload_manifest_invalid",
        "object_storage_upload_plan_invalid",
        "object_storage_upload_plan_changed",
        "object_storage_upload_no_writes",
        "object_storage_upload_writer_unavailable",
        "object_storage_upload_local_bytes_missing",
        "object_storage_upload_approval_required",
        "object_storage_upload_source_drifted",
        "object_storage_upload_remote_unavailable",
        "object_storage_upload_remote_conflict",
        "object_storage_upload_failed",
        "object_storage_upload_receipt_conflict",
        "object_storage_upload_control_invalid",
        "object_storage_upload_resume_invalid",
        "object_storage_upload_setup_evidence_missing",
        "object_storage_upload_setup_evidence_mismatch",
        "archive_index_rebuild_required",
        # v0.4.36 (beta letter 168 ①): the two gates the dry-run never
        # checked are refused before the dialog with their own codes.
        "object_storage_upload_credential_ref_unresolved",
    }

    def __init__(self, code: str) -> None:
        self.code = code if code in self._CODES else "object_storage_upload_plan_invalid"
        # v0.4.36: set to "none" by the writer when the failure provably
        # preceded its first durable write; the broker then finalizes the
        # claim as failed instead of leaving it started.
        self.effects: str | None = None
        self.cause_code: str | None = None
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"ObjectStorageUploadError({self.code!r})"


def _fail(code: str) -> ObjectStorageUploadError:
    return ObjectStorageUploadError(code)


_canonical = preservation._canonical_bytes
_sha = preservation._sha256_document
_sha_bytes = preservation._sha256_bytes
_strict_json = preservation._strict_json
_object_id = preservation._normalize_object_id
_locations = preservation._locations
_has_local = preservation._has_local
_local_paths = preservation._local_paths
_verified_remote = preservation._verified_remote
_official_wom_uploaded_evidence = preservation._official_wom_uploaded_evidence


def _translated(exc: preservation.ObjectStoragePreservationError, *, code: str) -> ObjectStorageUploadError:
    """Map a preservation helper's fixed code onto this module's vocabulary."""

    if exc.code == "object_storage_preservation_manifest_invalid":
        return _fail("object_storage_upload_manifest_invalid")
    if exc.code == "object_storage_preservation_source_drifted":
        return _fail("object_storage_upload_source_drifted")
    if "remote_unavailable" in exc.code:
        return _fail("object_storage_upload_remote_unavailable")
    if "remote_conflict" in exc.code:
        return _fail("object_storage_upload_remote_conflict")
    if "upload_failed" in exc.code:
        return _fail("object_storage_upload_failed")
    if "control_invalid" in exc.code:
        return _fail("object_storage_upload_control_invalid")
    if "receipt_conflict" in exc.code:
        return _fail("object_storage_upload_receipt_conflict")
    return _fail(code)


def _preservation_guard(call: Callable[[], Any], *, code: str) -> Any:
    """Run a preservation helper and translate its fixed code into ours."""

    try:
        return call()
    except preservation.ObjectStoragePreservationError as exc:
        raise _translated(exc, code=code) from None


# --- spec, tokens, manifest ----------------------------------------------------


@dataclass(frozen=True, repr=False)
class UploadSpec:
    object_id: str
    size_bytes: int
    local_relative: str
    local_path: Path
    remote_key: str
    receipt_relative: str
    receipt_token: bytes
    source_token: bytes
    target_identity_sha256: str


def _remote_key(object_id: str) -> str:
    return archive_services.object_storage_content_addressed_key_hint(object_id)


def _receipt_relative(object_id: str, inventory_sha256: str) -> str:
    digest = object_id.removeprefix("sha256:")
    inventory = inventory_sha256.removeprefix("sha256:")
    return f"{RECEIPT_ROOT}/{digest}.{inventory[:16]}.object-storage-upload.json"


def _receipt_token(
    *, object_id: str, size_bytes: int, provider_kind: str, store_ref: str, inventory_sha256: str
) -> bytes:
    return _canonical(
        {
            "schema_version": "wom-kit/object-storage-upload-terminal-state/v0.1",
            "object_id": object_id,
            "size_bytes": size_bytes,
            "provider_kind": provider_kind,
            "store_ref": store_ref,
            "remote_key_sha256": _sha(_remote_key(object_id)),
            "source_inventory_sha256": inventory_sha256,
            "terminal_statuses": list(_PUBLIC_STATUSES),
        }
    )


def _source_token(*, object_id: str, size_bytes: int, local_relative: str, inventory_sha256: str) -> bytes:
    return _canonical(
        {
            "schema_version": "wom-kit/object-storage-upload-source/v0.1",
            "object_id": object_id,
            "size_bytes": size_bytes,
            "local_relative_sha256": _sha(local_relative),
            "source_inventory_sha256": inventory_sha256,
        }
    )


def _target_identity(
    *, archive_id: str, object_id: str, receipt_relative: str, provider_kind: str, store_ref: str
) -> str:
    return _sha(
        {
            "schema_version": "wom-kit/object-storage-upload-terminal-target/v0.1",
            "archive_id": archive_id,
            "object_id": object_id,
            "receipt_relative": receipt_relative,
            "provider_kind": provider_kind,
            "store_ref": store_ref,
        }
    )


def _manifest_batch_token(specs: Sequence[UploadSpec]) -> bytes:
    return _canonical(
        {
            "schema_version": "wom-kit/object-storage-upload-location-batch/v0.1",
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


def _manifest_source_token(specs: Sequence[UploadSpec]) -> bytes:
    return _canonical(
        {
            "schema_version": "wom-kit/object-storage-upload-manifest-source/v0.1",
            "source_tokens": [_sha_bytes(item.source_token) for item in specs],
        }
    )


def _batch_target_identity(archive_id: str, specs: Sequence[UploadSpec]) -> str:
    return _sha(
        {
            "archive_id": archive_id,
            "target_ref": MANIFEST_TARGET_REF,
            "source_sha256": _sha_bytes(_manifest_source_token(specs)),
        }
    )


def _item_id_for(spec: UploadSpec) -> str:
    return "item:" + hashlib.sha256((spec.object_id + "\x00" + spec.receipt_relative).encode("ascii")).hexdigest()


def _manifest_for_specs(*, archive_id: str, specs: Sequence[UploadSpec]) -> ExactOperationManifest | None:
    items: list[ExactOperationItem] = []
    for ordinal, spec in enumerate(specs):
        items.append(
            ExactOperationItem(
                ordinal=ordinal,
                item_id=_item_id_for(spec),
                target_kind=RECEIPT_TARGET_KIND,
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
    items.append(
        ExactOperationItem(
            ordinal=len(items),
            item_id="item:" + hashlib.sha256(MANIFEST_TARGET_REF.encode("ascii")).hexdigest(),
            target_kind=BATCH_TARGET_KIND,
            target_ref=MANIFEST_TARGET_REF,
            target_identity_sha256=_batch_target_identity(archive_id, specs),
            fields=(
                ExactFieldEffect(
                    field_ref="remote_locations",
                    pre_sha256=hash_field_value(None),
                    post_sha256=hash_field_value(_manifest_batch_token(specs)),
                    source_sha256=hash_field_value(_manifest_source_token(specs)),
                ),
            ),
        )
    )
    return ExactOperationManifest.build(
        operation=OPERATION,
        archive_identity_sha256=exact_human_approval_archive_identity_sha256(archive_id),
        items=items,
    )


# --- plan ------------------------------------------------------------------------


_CLASSIFICATION_KEYS = (
    "conflicting_definition_count",
    "excluded_byte_external_count",
    "excluded_already_uploaded_count",
    "excluded_already_preserved_count",
    "excluded_offloaded_count",
    "local_absent_count",
    "local_size_conflict_count",
    "local_path_ambiguous_count",
    "excluded_by_filter_count",
    "already_recorded_count",
    "source_review_count",
    "candidate_count",
)


@dataclass(frozen=True, repr=False)
class ObjectStorageUploadPlan:
    archive_root: Path
    archive_id: str
    provider_kind: str
    store_ref: str
    writer_state: str
    writer_unavailable_reason: str | None
    manifest_scanned: bool
    source_inventory_sha256: str | None
    inventory: dict[str, Any]
    classification: dict[str, int]
    manifest: ExactOperationManifest | None
    specs: tuple[UploadSpec, ...]
    blockers: tuple[str, ...]
    local_bytes_only: bool
    selected_only: str | None
    max_objects: int | None
    loaded_from_control: bool = False

    @property
    def approveable(self) -> bool:
        return self.manifest is not None and bool(self.specs) and not self.blockers

    @property
    def planned_upload_bytes(self) -> int:
        return sum(spec.size_bytes for spec in self.specs)

    def public_document(self) -> dict[str, Any]:
        planned = len(self.specs)
        expected_put_calls, put_call_ceiling = preservation._provider_put_call_budget(self.specs)
        if self.writer_state != "available":
            state = "writer_unavailable"
        elif self.approveable:
            state = "ready_for_exact_human_approval"
        elif "local_bytes_missing" in self.blockers:
            state = "local_bytes_missing"
        elif planned == 0 and self.classification.get("source_review_count", 0) == 0:
            state = "no_new_bytes_to_upload"
        else:
            state = "review_required"
        reason_codes = {
            "writer_unavailable": ["object_storage_upload_writer_unavailable"],
            "ready_for_exact_human_approval": ["object_storage_upload_ready"],
            "local_bytes_missing": ["object_storage_upload_local_bytes_missing"],
            "no_new_bytes_to_upload": ["object_storage_upload_no_writes"],
            "review_required": ["object_storage_upload_review_required"],
        }[state]
        next_safe_actions: list[str] = []
        if state == "writer_unavailable" and self.writer_unavailable_reason == "store_setup_missing":
            # v0.4.36 (beta letter 168 ②): the registration may exist under
            # another label; say so instead of "register the store".
            next_safe_actions.append(
                "No store registration matches this --store-ref. The registered labels are the setup registration receipt's account_ref values (registered_store_refs below); rerun with one of them, or register this label first (archive object-storage --dry-run / --approve)."
            )
        elif state == "writer_unavailable":
            next_safe_actions.append(
                "Register the store first (archive object-storage --dry-run / --approve) and use a provider kind with a live transport (cloudflare-r2 or generic-s3)."
            )
        elif state == "local_bytes_missing":
            next_safe_actions.append(
                "Repair or restore the missing local bytes (archive object-storage-restore --dry-run), or rerun with --local-bytes-only to upload only the objects whose bytes are present."
            )
        elif state == "ready_for_exact_human_approval":
            next_safe_actions.append(
                "Rerun with --approve --reviewed-by <id> --expected-manifest-sha256 <plan_sha256> and the endpoint, bucket and credential refs; one native dialog covers the whole plan."
            )
        if self.classification.get("excluded_already_preserved_count", 0):
            next_safe_actions.append(
                "Objects that only have an emergency-preserved copy are excluded; adopt them with archive object-storage-adopt-existing --formal-adoption."
            )
        return {
            "schema_version": PLAN_SCHEMA,
            "ok": self.approveable,
            "state": state,
            "reason_codes": reason_codes,
            "writer_state": self.writer_state,
            "writer_unavailable_reason": self.writer_unavailable_reason,
            "manifest_scanned": self.manifest_scanned,
            "plan_sha256": self.manifest.manifest_sha256 if self.manifest else None,
            "target_binding_sha256": self.manifest.target_set_sha256 if self.manifest else None,
            "source_binding_sha256": self.manifest.source_set_sha256 if self.manifest else None,
            "effect_binding_sha256": self.manifest.effect_set_sha256 if self.manifest else None,
            "source_inventory_sha256": self.source_inventory_sha256,
            "manifest_row_count": int(self.inventory.get("manifest_row_count") or 0),
            "unique_object_count": int(self.inventory.get("unique_object_count") or 0),
            "classification": {key: int(self.classification.get(key, 0)) for key in _CLASSIFICATION_KEYS},
            "upload_planned_count": planned,
            "planned_upload_bytes": self.planned_upload_bytes,
            "expected_no_retry_provider_put_call_count": expected_put_calls,
            "manifest_bound_provider_put_call_ceiling": put_call_ceiling,
            "local_bytes_only": self.local_bytes_only,
            "max_objects": self.max_objects,
            "remote_key_layout": REMOTE_KEY_LAYOUT,
            "manifest_location_projection_planned": planned > 0,
            "tier_gate_applied": False,
            "requires_exact_human_approval": True,
            "common_exact_operation_manifest_used": self.manifest is not None,
            "provider_calls_in_plan": 0,
            "provider_api_called": False,
            "credential_values_read": False,
            # v0.4.36 (beta letter 168 ①②): the writer's post-dialog gates
            # and the registered labels, readable before any approval.
            "manifest_index_authority": manifest_index_authority_state(self),
            "registered_store_refs": (
                registered_store_refs(self.archive_root, provider_kind=self.provider_kind)
                if state == "writer_unavailable" else None
            ),
            "object_bytes_hashed": self.manifest_scanned,
            "writes_performed": False,
            "remote_delete_on_revert_supported": False,
            "existing_remote_copy_never_overwritten": True,
            "blockers": list(self.blockers),
            "next_safe_actions": next_safe_actions,
            "private_values_echoed": False,
            "local_paths_echoed": False,
            "remote_keys_echoed": False,
            "object_ids_echoed": False,
            "credential_refs_echoed": False,
        }


def _byte_external(row: Mapping[str, Any]) -> bool:
    return any(
        location.get("provider") == "external_prehashed"
        or location.get("availability") == "declared_external"
        for location in _locations(row)
    )


def _offloaded_only(row: Mapping[str, Any]) -> bool:
    return not _has_local(row) and any(
        location.get("provider") == "local" and location.get("availability") == "offloaded"
        for location in _locations(row)
    )


def _has_preserved_receipt(root: Path, object_id: str, *, provider_kind: str, store_ref: str) -> bool:
    """True when a v0.4.13 emergency-preservation receipt proves this object remote."""

    digest = object_id.removeprefix("sha256:")
    directory = archive_services.archive_internal_path(root, preservation.RECEIPT_ROOT)
    if not directory.is_dir():
        return False
    try:
        names = sorted(name for name in os.listdir(directory) if name.startswith(digest + ".") and name.endswith(".json"))
    except OSError:
        return False
    for name in names:
        path = directory / name
        try:
            info = os.lstat(path)
            if not stat.S_ISREG(info.st_mode) or info.st_size > _MAX_RECEIPT_BYTES:
                continue
            document = _strict_json(path.read_bytes())
        except Exception:
            continue
        if (
            document.get("object_id") == object_id
            and document.get("provider_kind") == provider_kind
            and document.get("store_ref") == store_ref
            and document.get("preservation_status") in {"bytes_preserved", "already_remote_verified"}
        ):
            return True
    return False


def _stat_local(root: Path, relative: str) -> tuple[Path | None, os.stat_result | None]:
    try:
        path = archive_services.archive_internal_path(root, relative)
        info = preservation._plain_regular_file(path)
    except Exception:
        return None, None
    return path, info


def _writer_state(root: Path, provider_kind: str, store_ref: str) -> tuple[str, str | None]:
    if provider_kind not in LIVE_TRANSPORT_PROVIDERS:
        return "unavailable", "provider_unsupported"
    if not archive_services.safe_object_storage_ref(store_ref):
        return "unavailable", "store_ref_invalid"
    try:
        object_storage_setup_registration.validate_object_storage_setup_evidence(
            root, provider_kind=provider_kind, store_ref=store_ref
        )
    except object_storage_setup_registration.ObjectStorageSetupRegistrationError as exc:
        return "unavailable", (
            "store_setup_missing" if exc.code == "object_storage_setup_evidence_missing" else "store_setup_mismatch"
        )
    return "available", None


def _require_setup_evidence(root: Path, *, provider_kind: str, store_ref: str) -> None:
    state, reason = _writer_state(root, provider_kind, store_ref)
    if state != "available":
        raise _fail(
            "object_storage_upload_setup_evidence_missing"
            if reason == "store_setup_missing"
            else "object_storage_upload_setup_evidence_mismatch"
            if reason == "store_setup_mismatch"
            else "object_storage_upload_writer_unavailable"
        )


def _classify_and_build(
    root: Path,
    archive_id: str,
    provider_kind: str,
    store_ref: str,
    inventory: Mapping[str, Any],
    groups: Mapping[str, Sequence[dict[str, Any]]],
    unique_rows: Mapping[str, dict[str, Any]],
    *,
    only: str | None,
    max_objects: int | None,
    local_bytes_only: bool,
    progress: Callable[[str, str, int | None, int | None], None] | None,
) -> tuple[tuple[UploadSpec, ...], dict[str, int], tuple[str, ...]]:
    inventory_sha = str(inventory["source_inventory_sha256"])
    selected_id = _object_id(only) if only else None
    counts = {key: 0 for key in _CLASSIFICATION_KEYS}
    counts["conflicting_definition_count"] = int(inventory["conflicting_definition_count"])
    candidates: list[tuple[str, dict[str, Any], str, Path]] = []
    if progress is not None:
        progress("upload-inventory", "start", 0, len(unique_rows))
    for index, (object_id, row) in enumerate(sorted(unique_rows.items()), start=1):
        if progress is not None and (index == 1 or index % 1000 == 0 or index == len(unique_rows)):
            progress("upload-inventory", "classified manifest objects", index, len(unique_rows))
        if _byte_external(row):
            counts["excluded_byte_external_count"] += 1
            continue
        if _verified_remote(row) or _official_wom_uploaded_evidence(row):
            counts["excluded_already_uploaded_count"] += 1
            continue
        if _has_preserved_receipt(root, object_id, provider_kind=provider_kind, store_ref=store_ref):
            counts["excluded_already_preserved_count"] += 1
            continue
        if _offloaded_only(row):
            counts["excluded_offloaded_count"] += 1
            continue
        if not _has_local(row):
            counts["local_absent_count"] += 1
            continue
        paths = _local_paths(row)
        if len(paths) != 1:
            counts["local_path_ambiguous_count"] += 1
            continue
        local_path, info = _stat_local(root, paths[0])
        if local_path is None or info is None:
            counts["local_absent_count"] += 1
            continue
        if info.st_size != row["size_bytes"]:
            counts["local_size_conflict_count"] += 1
            continue
        if selected_id is not None and object_id != selected_id:
            counts["excluded_by_filter_count"] += 1
            continue
        candidates.append((object_id, row, paths[0], local_path))
    if progress is not None:
        progress("upload-inventory", "done", len(unique_rows), len(unique_rows))
    if selected_id is not None and not candidates:
        raise _fail("object_storage_upload_no_writes")
    if max_objects is not None:
        if type(max_objects) is not int or max_objects < 1:
            raise _fail("object_storage_upload_plan_invalid")
        if len(candidates) > max_objects:
            counts["excluded_by_filter_count"] += len(candidates) - max_objects
            candidates = candidates[:max_objects]
    blockers: list[str] = []
    if not local_bytes_only and (counts["local_absent_count"] or counts["local_size_conflict_count"]):
        blockers.append("local_bytes_missing")
    specs: list[UploadSpec] = []
    if progress is not None:
        progress("upload-source-hash", "start", 0, len(candidates))
    for index, (object_id, row, local_relative, local_path) in enumerate(candidates, start=1):
        digest, size = _preservation_guard(
            lambda: preservation._hash_plain_file(
                local_path,
                heartbeat=(
                    (lambda i=index: progress("upload-source-hash", "heartbeat", i - 1, len(candidates)))
                    if progress is not None
                    else (lambda: None)
                ),
            ),
            code="object_storage_upload_plan_invalid",
        )
        if digest != object_id.removeprefix("sha256:") or size != row["size_bytes"]:
            counts["source_review_count"] += 1
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
                counts["source_review_count"] += 1
                continue
            if existing.get("receipt_state_sha256") == _sha_bytes(receipt_token) and existing.get(
                "result_status"
            ) in {STATUS_UPLOADED, STATUS_SKIPPED_REMOTE_SAME}:
                counts["already_recorded_count"] += 1
                continue
            counts["source_review_count"] += 1
            continue
        specs.append(
            UploadSpec(
                object_id=object_id,
                size_bytes=size,
                local_relative=local_relative,
                local_path=local_path,
                remote_key=_remote_key(object_id),
                receipt_relative=receipt_relative,
                receipt_token=receipt_token,
                source_token=_source_token(
                    object_id=object_id,
                    size_bytes=size,
                    local_relative=local_relative,
                    inventory_sha256=inventory_sha,
                ),
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
            progress("upload-source-hash", "hashed local objects", index, len(candidates))
    if progress is not None:
        progress("upload-source-hash", "done", len(candidates), len(candidates))
    counts["candidate_count"] = len(specs)
    return tuple(specs), counts, tuple(blockers)


def _plan_core(
    archive_root: Path | str,
    *,
    provider_kind: str,
    store_ref: str,
    only: str | None = None,
    max_objects: int | None = None,
    local_bytes_only: bool = False,
    progress: Callable[[str, str, int | None, int | None], None] | None = None,
) -> ObjectStorageUploadPlan:
    try:
        root = archive_services.require_existing_archive_root(archive_root)
        archive_id = archive_services.read_archive_id(root)
    except Exception:
        raise _fail("object_storage_upload_archive_invalid") from None
    normalized_provider = str(provider_kind or "").strip().lower()
    normalized_store = str(store_ref or "").strip()
    if normalized_provider not in archive_services.OBJECT_STORAGE_ALLOWED_PROVIDERS:
        raise _fail("object_storage_upload_plan_invalid")
    if type(local_bytes_only) is not bool:
        raise _fail("object_storage_upload_plan_invalid")
    writer_state, reason = _writer_state(root, normalized_provider, normalized_store)
    if writer_state != "available":
        # ③: the writer line comes first; the manifest is not read.
        return ObjectStorageUploadPlan(
            archive_root=root,
            archive_id=archive_id,
            provider_kind=normalized_provider,
            store_ref=normalized_store if archive_services.safe_object_storage_ref(normalized_store) else "",
            writer_state=writer_state,
            writer_unavailable_reason=reason,
            manifest_scanned=False,
            source_inventory_sha256=None,
            inventory={},
            classification={key: 0 for key in _CLASSIFICATION_KEYS},
            manifest=None,
            specs=(),
            blockers=("writer_unavailable",),
            local_bytes_only=local_bytes_only,
            selected_only=_object_id(only) if only else None,
            max_objects=max_objects,
        )
    rows, groups = _preservation_guard(
        lambda: preservation._read_manifest_groups(root, progress=progress),
        code="object_storage_upload_manifest_invalid",
    )
    inventory, unique_rows = preservation._inventory(rows, groups)
    specs, counts, blockers = _classify_and_build(
        root,
        archive_id,
        normalized_provider,
        normalized_store,
        inventory,
        groups,
        unique_rows,
        only=only,
        max_objects=max_objects,
        local_bytes_only=local_bytes_only,
        progress=progress,
    )
    manifest = None if blockers else _manifest_for_specs(archive_id=archive_id, specs=specs)
    return ObjectStorageUploadPlan(
        archive_root=root,
        archive_id=archive_id,
        provider_kind=normalized_provider,
        store_ref=normalized_store,
        writer_state="available",
        writer_unavailable_reason=None,
        manifest_scanned=True,
        source_inventory_sha256=str(inventory["source_inventory_sha256"]),
        inventory=dict(inventory),
        classification=counts,
        manifest=manifest,
        specs=specs,
        blockers=blockers,
        local_bytes_only=local_bytes_only,
        selected_only=_object_id(only) if only else None,
        max_objects=max_objects,
    )


def plan_object_storage_upload(
    archive_root: Path | str,
    *,
    provider_kind: str = "cloudflare-r2",
    store_ref: str,
    only: str | None = None,
    max_objects: int | None = None,
    local_bytes_only: bool = False,
    progress: Callable[[str, str, int | None, int | None], None] | None = None,
) -> ObjectStorageUploadPlan:
    return _plan_core(
        archive_root,
        provider_kind=provider_kind,
        store_ref=store_ref,
        only=only,
        max_objects=max_objects,
        local_bytes_only=local_bytes_only,
        progress=progress,
    )


# --- private control document (resume) -----------------------------------------


def _control_relative(manifest_sha256: str) -> str:
    if _SHA256_RE.fullmatch(str(manifest_sha256 or "")) is None:
        raise _fail("object_storage_upload_control_invalid")
    return f"{CONTROL_ROOT}/{manifest_sha256.removeprefix('sha256:')}.object-storage-upload.json"


_CONTROL_FIELDS = frozenset(
    {
        "schema_version",
        "archive_id",
        "provider_kind",
        "store_ref",
        "source_inventory_sha256",
        "inventory",
        "classification",
        "selected_only",
        "max_objects",
        "local_bytes_only",
        "manifest",
        "specs",
        "private_control_document",
    }
)


def _control_document(plan: ObjectStorageUploadPlan) -> dict[str, Any]:
    if plan.manifest is None:
        raise _fail("object_storage_upload_no_writes")
    basis = {
        "schema_version": CONTROL_SCHEMA,
        "archive_id": plan.archive_id,
        "provider_kind": plan.provider_kind,
        "store_ref": plan.store_ref,
        "source_inventory_sha256": plan.source_inventory_sha256,
        "inventory": plan.inventory,
        "classification": plan.classification,
        "selected_only": plan.selected_only,
        "max_objects": plan.max_objects,
        "local_bytes_only": plan.local_bytes_only,
        "manifest": plan.manifest.document(),
        "specs": [
            {
                "object_id": spec.object_id,
                "size_bytes": spec.size_bytes,
                "local_relative": spec.local_relative,
                "remote_key": spec.remote_key,
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


def _persist_control(plan: ObjectStorageUploadPlan) -> str:
    if plan.manifest is None:
        raise _fail("object_storage_upload_no_writes")
    relative = _control_relative(plan.manifest.manifest_sha256)
    path = archive_services.archive_internal_path(plan.archive_root, relative)
    if path.exists():
        existing = load_object_storage_upload_plan(plan.archive_root, manifest_sha256=plan.manifest.manifest_sha256)
        if not _same_control_plan(existing, plan):
            raise _fail("object_storage_upload_control_invalid")
        return relative
    raw = preservation._canonical_control_bytes(_control_document(plan))
    _preservation_guard(
        lambda: preservation._create_or_match_receipt(
            plan.archive_root,
            relative,
            raw,
            max_bytes=_MAX_CONTROL_BYTES,
            failure_code="object_storage_preservation_control_invalid",
        ),
        code="object_storage_upload_control_invalid",
    )
    return relative


def _same_control_plan(left: ObjectStorageUploadPlan, right: ObjectStorageUploadPlan) -> bool:
    if left.manifest is None or right.manifest is None:
        return False
    return (
        left.archive_root == right.archive_root
        and left.archive_id == right.archive_id
        and left.provider_kind == right.provider_kind
        and left.store_ref == right.store_ref
        and left.source_inventory_sha256 == right.source_inventory_sha256
        and left.inventory == right.inventory
        and left.manifest.document() == right.manifest.document()
        and left.specs == right.specs
        and left.classification == right.classification
        and left.selected_only == right.selected_only
        and left.max_objects == right.max_objects
        and left.local_bytes_only == right.local_bytes_only
    )


def load_object_storage_upload_plan(archive_root: Path | str, *, manifest_sha256: str) -> ObjectStorageUploadPlan:
    try:
        root = archive_services.require_existing_archive_root(archive_root)
        current_archive_id = archive_services.read_archive_id(root)
        relative = _control_relative(manifest_sha256)
        path = archive_services.archive_internal_path(root, relative)
        before = preservation._plain_regular_file(path, max_bytes=_MAX_CONTROL_BYTES)
        raw = path.read_bytes()
        after = preservation._plain_regular_file(path, max_bytes=_MAX_CONTROL_BYTES)
        if len(raw) != before.st_size or after.st_size != before.st_size or after.st_mtime_ns != before.st_mtime_ns:
            raise ValueError("control changed while reading")
        document = _strict_json(raw)
    except Exception:
        raise _fail("object_storage_upload_control_invalid") from None
    supplied_control_sha = document.pop("control_sha256", None)
    if (
        document.get("schema_version") != CONTROL_SCHEMA
        or set(document) != _CONTROL_FIELDS
        or document.get("private_control_document") is not True
        or type(supplied_control_sha) is not str
        or not hmac.compare_digest(supplied_control_sha, _sha(document))
    ):
        raise _fail("object_storage_upload_control_invalid")
    try:
        manifest = ExactOperationManifest.from_document(document["manifest"])
    except Exception:
        raise _fail("object_storage_upload_control_invalid") from None
    provider_kind = document.get("provider_kind")
    store_ref = document.get("store_ref")
    inventory = document.get("inventory")
    classification = document.get("classification")
    specs_raw = document.get("specs")
    if (
        manifest.manifest_sha256 != manifest_sha256
        or document.get("archive_id") != current_archive_id
        or type(provider_kind) is not str
        or provider_kind not in archive_services.OBJECT_STORAGE_ALLOWED_PROVIDERS
        or type(store_ref) is not str
        or not archive_services.safe_object_storage_ref(store_ref)
        or not isinstance(inventory, dict)
        or not isinstance(classification, dict)
        or _SHA256_RE.fullmatch(str(document.get("source_inventory_sha256") or "")) is None
        or type(specs_raw) is not list
        or len(specs_raw) + 1 != len(manifest.items)
        or manifest.operation != OPERATION
        or type(document.get("local_bytes_only")) is not bool
        or manifest.archive_identity_sha256 != exact_human_approval_archive_identity_sha256(current_archive_id)
    ):
        raise _fail("object_storage_upload_control_invalid")
    _require_setup_evidence(root, provider_kind=provider_kind, store_ref=store_ref)
    rows, groups = _preservation_guard(
        lambda: preservation._read_manifest_groups(root, progress=None),
        code="object_storage_upload_manifest_invalid",
    )
    # The live inventory is not compared here: this writer's own projection
    # changes it (the wom_uploaded locations), and a resume after that
    # projection must still load. Each spec is revalidated row by row instead.
    inventory_sha = str(document["source_inventory_sha256"])
    specs: list[UploadSpec] = []
    for item, raw_spec in zip(manifest.items[:-1], specs_raw):
        if not isinstance(raw_spec, Mapping):
            raise _fail("object_storage_upload_control_invalid")
        try:
            object_id = _object_id(raw_spec.get("object_id"))
            size = raw_spec.get("size_bytes")
            local_relative = raw_spec.get("local_relative")
            group = groups[object_id]
        except Exception:
            raise _fail("object_storage_upload_plan_changed") from None
        if (
            type(size) is not int
            or type(local_relative) is not str
            or len(item.fields) != 1
            or len(group) != 1
            or group[0].get("size_bytes") != size
            or _local_paths(group[0]) != [local_relative]
        ):
            raise _fail("object_storage_upload_plan_changed")
        local_path, info = _stat_local(root, local_relative)
        if local_path is None or info is None or info.st_size != size:
            raise _fail("object_storage_upload_plan_changed")
        receipt_relative = _receipt_relative(object_id, inventory_sha)
        receipt_token = _receipt_token(
            object_id=object_id,
            size_bytes=size,
            provider_kind=provider_kind,
            store_ref=store_ref,
            inventory_sha256=inventory_sha,
        )
        source_token = _source_token(
            object_id=object_id, size_bytes=size, local_relative=local_relative, inventory_sha256=inventory_sha
        )
        target_identity = _target_identity(
            archive_id=document["archive_id"],
            object_id=object_id,
            receipt_relative=receipt_relative,
            provider_kind=provider_kind,
            store_ref=store_ref,
        )
        spec = UploadSpec(
            object_id=object_id,
            size_bytes=size,
            local_relative=local_relative,
            local_path=local_path,
            remote_key=_remote_key(object_id),
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
            or raw_spec.get("receipt_token_sha256") != _sha_bytes(receipt_token)
            or raw_spec.get("source_token_sha256") != _sha_bytes(source_token)
            or raw_spec.get("remote_key") != spec.remote_key
            or raw_spec.get("receipt_relative") != receipt_relative
            or raw_spec.get("target_identity_sha256") != target_identity
        ):
            raise _fail("object_storage_upload_control_invalid")
        specs.append(spec)
    batch_item = manifest.items[-1]
    if (
        batch_item.target_kind != BATCH_TARGET_KIND
        or batch_item.target_ref != MANIFEST_TARGET_REF
        or batch_item.target_identity_sha256 != _batch_target_identity(document["archive_id"], specs)
        or batch_item.fields[0].post_sha256 != hash_field_value(_manifest_batch_token(specs))
    ):
        raise _fail("object_storage_upload_control_invalid")
    return ObjectStorageUploadPlan(
        archive_root=root,
        archive_id=document["archive_id"],
        provider_kind=provider_kind,
        store_ref=store_ref,
        writer_state="available",
        writer_unavailable_reason=None,
        manifest_scanned=True,
        source_inventory_sha256=inventory_sha,
        inventory=inventory,
        classification={key: int(classification.get(key, 0)) for key in _CLASSIFICATION_KEYS},
        manifest=manifest,
        specs=tuple(specs),
        blockers=(),
        local_bytes_only=bool(document["local_bytes_only"]),
        selected_only=document.get("selected_only"),
        max_objects=document.get("max_objects"),
        loaded_from_control=True,
    )


# --- receipts and the manifest projection --------------------------------------


def _receipt_document(
    plan: ObjectStorageUploadPlan,
    spec: UploadSpec,
    terminal: Mapping[str, Any],
    ledger: preservation._ManifestBoundPreservationLedger,
    *,
    reviewed_by: str,
    manifest_update_applied: bool,
) -> dict[str, Any]:
    if plan.manifest is None:
        raise _fail("object_storage_upload_receipt_conflict")
    status = _LEDGER_TO_PUBLIC.get(str(terminal.get("preservation_status") or ""))
    if status is None:
        raise _fail("object_storage_upload_receipt_conflict")
    remote_state = str(terminal.get("remote_state") or "")
    result_status = "remote_conflict_different_bytes" if status == STATUS_REVIEW_REQUIRED else status
    uploaded = status == STATUS_UPLOADED
    return {
        "schema": archive_services.OBJECT_STORAGE_UPLOAD_RECEIPT_SCHEMA,
        "receipt_id": f"objstore-{spec.object_id.removeprefix('sha256:')[:12]}-{_sha_bytes(spec.receipt_token)[:16]}",
        "receipt_path": spec.receipt_relative,
        "lifecycle_action": "object_storage_upload_execute",
        "operation": "upload_object",
        "dry_run": False,
        "archive_id": plan.archive_id,
        "object_id": spec.object_id,
        "provider_kind": plan.provider_kind,
        "store_ref": plan.store_ref,
        "key_strategy": REMOTE_KEY_LAYOUT,
        "key_hint": spec.remote_key,
        "remote_key": spec.remote_key,
        "result_status": result_status,
        "bytes_uploaded": spec.size_bytes if uploaded else 0,
        "checksum_algorithm": archive_services.OBJECT_STORAGE_CHECKSUM_ALGORITHM,
        "effective_multipart_threshold_bytes": int(archive_services.OBJECT_STORAGE_MULTIPART_THRESHOLD_BYTES),
        "effective_multipart_part_size_bytes": int(archive_services.OBJECT_STORAGE_MULTIPART_PART_SIZE_BYTES),
        "part_count": int(terminal.get("part_count") or 0),
        "forced_reupload": False,
        "retry_summary": {
            "attempts": int(terminal.get("attempts") or 0),
            "last_status_class": result_status,
            "backoff_ms_total": int(terminal.get("backoff_ms_total") or 0),
        },
        "object_count": 1,
        "reviewed_by": reviewed_by,
        "availability_transition": {
            "from": "local_only_or_declared",
            "to": "wom_uploaded" if manifest_update_applied else "unchanged",
        },
        "manifest_update_applied": bool(manifest_update_applied),
        "privacy_guards": {
            "secret_values_echoed": False,
            "exact_credential_refs_echoed": False,
            "bucket_names_echoed": False,
            "provider_urls_echoed": False,
            "local_absolute_paths_echoed": False,
            "generated_urls_echoed": False,
        },
        # v0.4.33 exact-approval additions (the v0.3 schema allows extra fields).
        "exact_operation": OPERATION,
        "exact_operation_manifest_sha256": plan.manifest.manifest_sha256,
        "source_inventory_sha256": plan.source_inventory_sha256,
        "receipt_state_sha256": _sha_bytes(spec.receipt_token),
        "classified_at": str(terminal.get("completed_at") or ""),
        "provider_put_call_count": ledger.observed_calls_for(spec),
        "provider_put_call_charged_count": ledger.charged_calls_for(spec),
        "provider_put_call_count_evidence": ledger.call_count_evidence_for(spec),
        "remote_verification": {
            "head_present": True,
            "size_match": remote_state != "size_mismatch",
            "whole_object_sha256_match": remote_state == "verified_match",
            "verification_kind": "get_rehash_whole_object" if remote_state != "size_mismatch" else "head_size_mismatch",
        },
        "review_reason": (
            None
            if status != STATUS_REVIEW_REQUIRED
            else ("remote_size_mismatch" if remote_state == "size_mismatch" else "remote_checksum_mismatch")
        ),
        "existing_remote_copy_overwritten": False,
        "remote_delete_on_revert_supported": False,
    }


def _receipt_path(plan: ObjectStorageUploadPlan, spec: UploadSpec) -> Path:
    return archive_services.archive_internal_path(plan.archive_root, spec.receipt_relative)


def _read_receipt(plan: ObjectStorageUploadPlan, spec: UploadSpec) -> dict[str, Any] | None:
    path = _receipt_path(plan, spec)
    if not path.exists():
        return None
    try:
        before = preservation._plain_regular_file(path, max_bytes=_MAX_RECEIPT_BYTES)
        raw = path.read_bytes()
        after = preservation._plain_regular_file(path, max_bytes=_MAX_RECEIPT_BYTES)
        if len(raw) != before.st_size or after.st_size != before.st_size or after.st_mtime_ns != before.st_mtime_ns:
            raise ValueError("changed")
        document = _strict_json(raw)
    except Exception:
        raise _fail("object_storage_upload_receipt_conflict") from None
    if (
        document.get("receipt_state_sha256") != _sha_bytes(spec.receipt_token)
        or document.get("receipt_path") != spec.receipt_relative
        or document.get("object_id") != spec.object_id
        or (plan.manifest is not None and document.get("exact_operation_manifest_sha256") != plan.manifest.manifest_sha256)
    ):
        raise _fail("object_storage_upload_receipt_conflict")
    return document


def _create_receipt(
    plan: ObjectStorageUploadPlan,
    spec: UploadSpec,
    ledger: preservation._ManifestBoundPreservationLedger,
    *,
    reviewed_by: str,
    manifest_update_applied: bool,
) -> dict[str, Any]:
    existing = _read_receipt(plan, spec)
    if existing is not None:
        return existing
    terminal = ledger.terminal_for(spec)
    if terminal is None:
        raise _fail("object_storage_upload_receipt_conflict")
    document = _receipt_document(
        plan, spec, terminal, ledger, reviewed_by=reviewed_by, manifest_update_applied=manifest_update_applied
    )
    _preservation_guard(
        lambda: preservation._create_or_match_receipt(
            plan.archive_root,
            spec.receipt_relative,
            preservation._canonical_receipt_bytes(document),
            failure_code="object_storage_preservation_receipt_conflict",
        ),
        code="object_storage_upload_receipt_conflict",
    )
    return document


def _projection_marker_relative(plan: ObjectStorageUploadPlan) -> str:
    if plan.manifest is None:
        raise _fail("object_storage_upload_no_writes")
    return f"{CONTROL_ROOT}/{plan.manifest.manifest_sha256.removeprefix('sha256:')}.object-storage-upload.projection.json"


def _projection_marker_absent(plan: ObjectStorageUploadPlan) -> bool:
    return not archive_services.archive_internal_path(plan.archive_root, _projection_marker_relative(plan)).exists()


def _write_projection_marker(plan: ObjectStorageUploadPlan, *, changed: int) -> None:
    document = {
        "schema_version": "wom-kit/object-storage-upload-projection/v0.1",
        "exact_operation_manifest_sha256": plan.manifest.manifest_sha256 if plan.manifest else None,
        "remote_location_changes": int(changed),
        "private_control_document": True,
    }
    _preservation_guard(
        lambda: preservation._create_or_match_receipt(
            plan.archive_root,
            _projection_marker_relative(plan),
            _canonical(document) + b"\n",
            max_bytes=_MAX_RECEIPT_BYTES,
            failure_code="object_storage_preservation_control_invalid",
        ),
        code="object_storage_upload_control_invalid",
    )


def _terminal_successes(
    plan: ObjectStorageUploadPlan, ledger: preservation._ManifestBoundPreservationLedger
) -> tuple[list[UploadSpec], list[UploadSpec]] | None:
    """(successes, reviews) from the private ledger; None while any object is nonterminal."""

    successes: list[UploadSpec] = []
    reviews: list[UploadSpec] = []
    for spec in plan.specs:
        terminal = ledger.terminal_for(spec)
        if terminal is None:
            return None
        status = _LEDGER_TO_PUBLIC.get(str(terminal.get("preservation_status") or ""))
        if status in {STATUS_UPLOADED, STATUS_SKIPPED_REMOTE_SAME}:
            successes.append(spec)
        elif status == STATUS_REVIEW_REQUIRED:
            reviews.append(spec)
        else:
            raise _fail("object_storage_upload_control_invalid")
    return successes, reviews


def _location_present(row: Mapping[str, Any], spec: UploadSpec, plan: ObjectStorageUploadPlan) -> bool:
    return archive_services._object_storage_wom_uploaded_remote_key_present(
        list(row.get("locations") or []),
        provider_kind=plan.provider_kind,
        store_ref=plan.store_ref,
        remote_key=spec.remote_key,
    )


def _batch_state(
    plan: ObjectStorageUploadPlan, ledger: preservation._ManifestBoundPreservationLedger
) -> bytes | None:
    if not plan.specs:
        return None
    terminals = _terminal_successes(plan, ledger)
    if terminals is None:
        return None
    successes, reviews = terminals
    if _projection_marker_absent(plan):
        return None
    rows, _groups = _preservation_guard(
        lambda: preservation._read_manifest_groups(plan.archive_root, progress=None),
        code="object_storage_upload_manifest_invalid",
    )
    by_id = {spec.object_id: spec for spec in successes}
    seen = {spec.object_id: 0 for spec in plan.specs}
    present = {spec.object_id: False for spec in successes}
    for row in rows:
        object_id = _object_id(row.get("object_id"))
        if object_id in seen:
            seen[object_id] += 1
        spec = by_id.get(object_id)
        if spec is not None:
            present[object_id] = _location_present(row, spec, plan)
    if any(value != 1 for value in seen.values()):
        raise _fail("object_storage_upload_plan_changed")
    if not all(present.values()):
        raise _fail("object_storage_upload_plan_changed")
    for spec in plan.specs:
        if _read_receipt(plan, spec) is None:
            return None
    return _manifest_batch_token(plan.specs)


def _apply_manifest_batch(
    plan: ObjectStorageUploadPlan,
    ledger: preservation._ManifestBoundPreservationLedger,
    *,
    lifecycle: restore._ManifestIndexLifecycle,
    reviewed_by: str,
) -> tuple[int, int]:
    """Add one wom_uploaded location per verified object (one CAS rewrite), then the receipts.

    Returns (location changes, receipts created). Idempotent: a present marker
    means the projection ran; missing receipts are then created from the
    ledger's terminal rows without touching the manifest again.
    """

    if plan.manifest is None:
        raise _fail("object_storage_upload_no_writes")
    terminals = _terminal_successes(plan, ledger)
    if terminals is None:
        raise _fail("object_storage_upload_plan_changed")
    successes, reviews = terminals
    changed = 0
    if _projection_marker_absent(plan):
        changed = _project_locations(plan, ledger, successes, lifecycle=lifecycle)
    receipts_created = 0
    for spec in successes:
        if _read_receipt(plan, spec) is None:
            _create_receipt(plan, spec, ledger, reviewed_by=reviewed_by, manifest_update_applied=True)
            receipts_created += 1
    for spec in reviews:
        if _read_receipt(plan, spec) is None:
            _create_receipt(plan, spec, ledger, reviewed_by=reviewed_by, manifest_update_applied=False)
            receipts_created += 1
    return changed, receipts_created


def _project_locations(
    plan: ObjectStorageUploadPlan,
    ledger: preservation._ManifestBoundPreservationLedger,
    successes: Sequence[UploadSpec],
    *,
    lifecycle: restore._ManifestIndexLifecycle,
) -> int:
    assert plan.manifest is not None
    by_id = {spec.object_id: spec for spec in successes}
    manifest_path = archive_services.archive_internal_path(plan.archive_root, "objects/manifests/files.jsonl")
    owner = archive_services.archive_manifest_mutation_owner_sha256(
        operation=OPERATION, operation_binding_sha256=plan.manifest.manifest_sha256
    )
    seen = {spec.object_id: 0 for spec in plan.specs}
    changed = 0
    with archive_services._ObjetCaptureManifestLock(plan.archive_root):
        rewritten: list[str] = []
        try:
            before = archive_services.archive_index_stable_file_snapshot(
                plan.archive_root, manifest_path, max_bytes=archive_services.ZETTEL_OBJET_LINK_MANIFEST_MAX_BYTES
            )
            raw_lines = before["raw"].decode("utf-8").splitlines()
        except (OSError, UnicodeError):
            raise _fail("object_storage_upload_plan_changed") from None
        for raw_line in raw_lines:
            if not raw_line.strip():
                rewritten.append(raw_line)
                continue
            try:
                row = json.loads(raw_line)
                object_id = _object_id(row.get("object_id"))
            except Exception:
                raise _fail("object_storage_upload_plan_changed") from None
            if object_id in seen:
                seen[object_id] += 1
            spec = by_id.get(object_id)
            if spec is None:
                rewritten.append(raw_line)
                continue
            if _location_present(row, spec, plan):
                rewritten.append(raw_line)
                continue
            terminal = ledger.terminal_for(spec) or {}
            locations = list(row.get("locations") or [])
            locations.append(
                archive_services.object_storage_wom_uploaded_location(
                    digest=spec.object_id.removeprefix("sha256:"),
                    provider_kind=plan.provider_kind,
                    store_ref=plan.store_ref,
                    execution_receipt_ref=spec.receipt_relative,
                    uploaded_at=str(terminal.get("completed_at") or preservation._now_iso()),
                    key_strategy=REMOTE_KEY_LAYOUT,
                    remote_key=spec.remote_key,
                    remote_key_verified=True,
                    remote_key_verification="content_hash",
                    remote_size=spec.size_bytes,
                )
            )
            row["locations"] = locations
            changed += 1
            rewritten.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
        if any(value != 1 for value in seen.values()):
            raise _fail("object_storage_upload_plan_changed")
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
                swap_suffix=".object-storage-upload-manifest.swap",
                max_bytes=archive_services.ZETTEL_OBJET_LINK_MANIFEST_MAX_BYTES,
                error_prefix="object_storage_upload",
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


def _require_manifest_index_authority(plan: ObjectStorageUploadPlan) -> None:
    if not plan.specs or plan.manifest is None:
        return
    try:
        restore._require_manifest_index_authority_for(plan.archive_root, plan.manifest.manifest_sha256, operation=OPERATION)
    except restore.ObjectStorageRestoreError:
        raise _fail("archive_index_rebuild_required") from None


def manifest_index_authority_state(plan: ObjectStorageUploadPlan) -> str:
    """v0.4.36 (beta letter 168 ①): the gate the writer applied only after the
    dialog, now readable by the dry-run and checked by approve before it.
    ``current`` / ``rebuild_required`` / ``not_applicable`` (nothing to write)."""

    if not plan.specs or plan.manifest is None:
        return "not_applicable"
    try:
        _require_manifest_index_authority(plan)
    except ObjectStorageUploadError:
        return "rebuild_required"
    return "current"


def registered_store_refs(archive_root: Path | str, *, provider_kind: str | None = None) -> list[str]:
    """v0.4.36 (beta letter 168 ②): the store labels the setup registration
    knows, so a ``store_setup_missing`` result can say which label to use
    instead of "register the store". Labels are the operator's own bindings;
    no credential value is read. Never raises."""

    try:
        root = archive_services.require_existing_archive_root(archive_root)
        document, _raw = object_storage_setup_registration._provider_document(root)
    except Exception:
        return []
    provider = str(provider_kind or "").strip().lower() or None
    labels: list[str] = []
    for binding in document.get("bindings") or []:
        if not isinstance(binding, dict) or binding.get("provider") != "object_storage":
            continue
        if provider is not None and binding.get("provider_kind") != provider:
            continue
        label = object_storage_setup_registration._binding_account_ref(binding)
        if label and archive_services.safe_object_storage_ref(label) and label not in labels:
            labels.append(label)
    return sorted(labels)


# --- exact operation adapters ------------------------------------------------------


class _Payloads:
    def __init__(self, plan: ObjectStorageUploadPlan) -> None:
        self.values: dict[tuple[str, str], tuple[bytes | None, bytes, bytes, UploadSpec | None]] = {}
        if plan.manifest is None:
            return
        for spec in plan.specs:
            self.values[(_item_id_for(spec), "terminal_state_token")] = (None, spec.receipt_token, spec.source_token, spec)
        batch = plan.manifest.items[-1]
        self.values[(batch.item_id, "remote_locations")] = (
            None,
            _manifest_batch_token(plan.specs),
            _manifest_source_token(plan.specs),
            None,
        )

    def field_value(self, *, item_id: str, field_ref: str, state: str, heartbeat: Callable[[], None]) -> bytes | None:
        heartbeat()
        values = self.values.get((item_id, field_ref))
        if values is None or state not in {"pre", "post", "source"}:
            raise ValueError("payload boundary")
        pre, post, source, spec = values
        if state == "pre":
            return pre
        if state == "post":
            return post
        if spec is not None:
            digest, size = _preservation_guard(
                lambda: preservation._hash_plain_file(spec.local_path, heartbeat=heartbeat),
                code="object_storage_upload_source_drifted",
            )
            if digest != spec.object_id.removeprefix("sha256:") or size != spec.size_bytes:
                raise _fail("object_storage_upload_source_drifted")
        return source


class _Verifier:
    def __init__(
        self,
        plan: ObjectStorageUploadPlan,
        query: preservation.ObjectStorageRemoteQueryAdapter,
        ledger: preservation._ManifestBoundPreservationLedger,
    ) -> None:
        self.plan = plan
        self.by_target = {spec.receipt_relative: spec for spec in plan.specs}
        self.query = query
        self.ledger = ledger
        self._verified: set[str] = set()

    def target_identity_sha256(self, *, target_kind: str, target_ref: str, heartbeat: Callable[[], None]) -> str:
        heartbeat()
        if target_kind == RECEIPT_TARGET_KIND:
            spec = self.by_target.get(target_ref)
            if spec is None:
                raise ValueError("target boundary")
            return spec.target_identity_sha256
        if target_kind == BATCH_TARGET_KIND and target_ref == MANIFEST_TARGET_REF:
            return _batch_target_identity(self.plan.archive_id, self.plan.specs)
        raise ValueError("target boundary")

    def read_field(self, *, target_kind: str, target_ref: str, field_ref: str, heartbeat: Callable[[], None]) -> bytes | None:
        if target_kind == RECEIPT_TARGET_KIND:
            spec = self.by_target.get(target_ref)
            if spec is None or field_ref != "terminal_state_token":
                raise ValueError("read boundary")
            terminal = self.ledger.terminal_for(spec)
            if terminal is None:
                return None
            if target_ref not in self._verified:
                evidence = self.query.query(
                    remote_key=spec.remote_key,
                    expected_size=spec.size_bytes,
                    expected_sha256=spec.object_id.removeprefix("sha256:"),
                    heartbeat=heartbeat,
                )
                if evidence.state != terminal["remote_state"]:
                    raise ValueError("remote verification")
                self._verified.add(target_ref)
            return spec.receipt_token
        if target_kind == BATCH_TARGET_KIND and target_ref == MANIFEST_TARGET_REF and field_ref == "remote_locations":
            return _batch_state(self.plan, self.ledger)
        raise ValueError("read boundary")


class _Writer:
    """Per-object: preservation's PUT spine at the content-addressed key; then the batch projection + receipts."""

    def __init__(
        self,
        plan: ObjectStorageUploadPlan,
        transport: archive_services.ObjectStorageTransport,
        *,
        reviewed_by: str,
    ) -> None:
        self.plan = plan
        self.transport = transport
        self.reviewed_by = reviewed_by
        self.by_target = {spec.receipt_relative: spec for spec in plan.specs}
        self.query = preservation.ObjectStorageRemoteQueryAdapter(transport)
        self.ledger = _preservation_guard(
            lambda: preservation._ManifestBoundPreservationLedger(plan), code="object_storage_upload_control_invalid"
        )
        self.expected_no_retry_put_calls, self.manifest_bound_put_call_ceiling = preservation._provider_put_call_budget(
            plan.specs
        )
        self.manifest_update_count = 0
        self.receipts_created_count = 0
        self.manifest_index_lifecycle = restore._ManifestIndexLifecycle()

    def _query(self, spec: UploadSpec, digest: str, heartbeat: Callable[[], None]) -> preservation.ObjectStorageRemoteQueryResult:
        return _preservation_guard(
            lambda: self.query.query(
                remote_key=spec.remote_key, expected_size=spec.size_bytes, expected_sha256=digest, heartbeat=heartbeat
            ),
            code="object_storage_upload_plan_invalid",
        )

    def _write_object(self, spec: UploadSpec, heartbeat: Callable[[], None]) -> None:
        digest, size = _preservation_guard(
            lambda: preservation._hash_plain_file(spec.local_path, heartbeat=heartbeat),
            code="object_storage_upload_source_drifted",
        )
        if digest != spec.object_id.removeprefix("sha256:") or size != spec.size_bytes:
            raise _fail("object_storage_upload_source_drifted")
        ledger = self.ledger
        terminal = ledger.terminal_for(spec)
        if terminal is not None:
            evidence = self._query(spec, digest, heartbeat)
            if evidence.state == "verification_unavailable":
                raise _fail("object_storage_upload_remote_unavailable")
            if evidence.state != terminal["remote_state"]:
                raise _fail("object_storage_upload_remote_conflict")
            return
        before = self._query(spec, digest, heartbeat)
        unresolved_multipart = ledger.unresolved_provider_phases_for(spec) & {
            "create_multipart",
            "put_part",
            "complete_multipart",
            "abort_multipart",
        }
        if unresolved_multipart and before.state != "verified_match":
            raise _fail("object_storage_upload_remote_unavailable")
        try:
            if before.state == "verified_match":
                ledger.append_terminal(spec, preservation_status="already_remote_verified", remote_state="verified_match")
            elif before.state == "absent":
                used = ledger.total_put_calls()
                remaining = self.manifest_bound_put_call_ceiling - used
                if remaining <= 0:
                    raise _fail("object_storage_upload_failed")
                result = preservation._call_with_heartbeat(
                    lambda: archive_services._object_storage_execute_one_upload(
                        transport=preservation._JournaledPreservationTransport(self.transport, ledger, spec),
                        key=spec.remote_key,
                        data_path=spec.local_path,
                        size=spec.size_bytes,
                        content_sha256=digest,
                        multipart_threshold_bytes=archive_services.OBJECT_STORAGE_MULTIPART_THRESHOLD_BYTES,
                        multipart_part_size_bytes=archive_services.OBJECT_STORAGE_MULTIPART_PART_SIZE_BYTES,
                        skip_uploaded=False,
                        ledger=ledger,
                        force_upload=True,
                        create_only=True,
                        max_attempts=min(archive_services.OBJECT_STORAGE_MAX_ATTEMPTS_PER_OBJECT, remaining),
                        max_provider_mutation_calls=remaining,
                    ),
                    heartbeat=heartbeat,
                )
                status = result.get("result_status")
                if status in {"conditional_precondition_failed", "conditional_conflict"}:
                    after_conflict = self._query(spec, digest, heartbeat)
                    put_calls = int(result.get("put_calls") or 0)
                    cleanup = str(result.get("multipart_cleanup_state") or "not_applicable")
                    if after_conflict.state == "verified_match":
                        ledger.append_terminal(
                            spec,
                            preservation_status="already_remote_verified",
                            remote_state="verified_match",
                            put_calls=put_calls,
                            multipart_cleanup_state=cleanup,
                        )
                    elif after_conflict.state in {"size_mismatch", "checksum_mismatch"}:
                        ledger.append_terminal(
                            spec,
                            preservation_status="review_required",
                            remote_state=after_conflict.state,
                            put_calls=put_calls,
                            multipart_cleanup_state=cleanup,
                        )
                    elif after_conflict.state == "verification_unavailable":
                        ledger.append_attempt(result)
                        raise _fail("object_storage_upload_remote_unavailable")
                    else:
                        ledger.append_attempt(result)
                        raise _fail("object_storage_upload_failed")
                elif status != "uploaded" or int(result.get("put_calls") or 0) < 1:
                    ledger.append_attempt(result)
                    if status in {
                        "failed_auth",
                        "failed_rate_limited",
                        "failed_upload",
                        "failed_cleanup_unverified",
                        "failed_provider_call_ceiling",
                    }:
                        raise _fail("object_storage_upload_remote_unavailable")
                    raise _fail("object_storage_upload_failed")
                if ledger.total_put_calls() > self.manifest_bound_put_call_ceiling:
                    raise _fail("object_storage_upload_failed")
            elif before.state in {"size_mismatch", "checksum_mismatch"}:
                ledger.append_terminal(spec, preservation_status="review_required", remote_state=before.state)
            else:
                raise _fail("object_storage_upload_remote_unavailable")
        except preservation.ObjectStoragePreservationError as exc:
            raise _translated(exc, code="object_storage_upload_control_invalid") from None

    def write_field(self, *, target_kind: str, target_ref: str, field_ref: str, value: bytes | None, heartbeat: Callable[[], None]) -> None:
        if target_kind == RECEIPT_TARGET_KIND:
            spec = self.by_target.get(target_ref)
            if spec is None or field_ref != "terminal_state_token" or value != spec.receipt_token:
                raise ValueError("write boundary")
            self._write_object(spec, heartbeat)
            return
        if target_kind == BATCH_TARGET_KIND and target_ref == MANIFEST_TARGET_REF and field_ref == "remote_locations":
            if value != _manifest_batch_token(self.plan.specs):
                raise ValueError("write boundary")
            changed, receipts = _apply_manifest_batch(
                self.plan, self.ledger, lifecycle=self.manifest_index_lifecycle, reviewed_by=self.reviewed_by
            )
            self.manifest_update_count += changed
            self.receipts_created_count += receipts
            return
        raise ValueError("write boundary")


# --- approval binding, execution ------------------------------------------------


def _approval_binding(plan: ObjectStorageUploadPlan) -> ExactOperationApprovalBinding:
    if plan.manifest is None:
        raise _fail("object_storage_upload_no_writes")
    try:
        return exact_operation_manifest_approval_binding(
            plan.manifest,
            operation=ExactHumanApprovalOperation.object_storage_bytes_upload,
            archive_id=plan.archive_id,
            warnings=(
                "existing_remote_copy_is_never_overwritten",
                "remote_object_is_never_deleted",
                "review_required_objects_get_no_manifest_location",
            ),
        )
    except Exception:
        raise _fail("object_storage_upload_plan_invalid") from None


def object_storage_upload_context(plan: ObjectStorageUploadPlan, *, reviewer_claim: str) -> ExactHumanApprovalContext:
    reviewer = str(reviewer_claim or "").strip()
    if not reviewer or not plan.approveable:
        raise _fail("object_storage_upload_plan_invalid")
    return _approval_binding(plan).context(archive_id=plan.archive_id, reviewer_claim=reviewer)


def _assert_approved(
    plan: ObjectStorageUploadPlan, claim: _ClaimedExactHumanApproval, context: ExactHumanApprovalContext
) -> ExactOperationApprovalAuthority:
    binding = _approval_binding(plan)
    if (
        type(claim) is not _ClaimedExactHumanApproval
        or type(context) is not ExactHumanApprovalContext
        or context.operation is not ExactHumanApprovalOperation.object_storage_bytes_upload
        or context.plan_sha256 != binding.plan_sha256
        or context.target_binding_sha256 != binding.target_binding_sha256
    ):
        raise _fail("object_storage_upload_approval_required")
    try:
        reference = _ClaimedExactHumanApproval.assert_ready_for_context(claim, context)
        return ExactOperationApprovalAuthority.from_reference(reference)
    except (ExactHumanApprovalError, ExactOperationManifestError):
        raise _fail("object_storage_upload_approval_required") from None


def _fresh_revalidated(
    plan: ObjectStorageUploadPlan, *, progress_hook: Callable[[ExactOperationProgress], None] | None
) -> ObjectStorageUploadPlan:
    _require_setup_evidence(plan.archive_root, provider_kind=plan.provider_kind, store_ref=plan.store_ref)
    if plan.loaded_from_control:
        return plan
    if plan.manifest is None:
        raise _fail("object_storage_upload_no_writes")
    total_items = len(plan.manifest.items)
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

    def revalidation_progress(stage: str, message: str, current: int | None, _total: int | None) -> None:
        nonlocal last_emitted
        now = time.monotonic()
        done = stage == "upload-source-hash" and message == "done"
        if done or now - last_emitted >= 10.0:
            publish(int(current or 0) if stage == "upload-source-hash" else 0)
            last_emitted = now

    current = _plan_core(
        plan.archive_root,
        provider_kind=plan.provider_kind,
        store_ref=plan.store_ref,
        only=plan.selected_only,
        max_objects=plan.max_objects,
        local_bytes_only=plan.local_bytes_only,
        progress=revalidation_progress,
    )
    if (
        current.manifest is None
        or current.manifest.document() != plan.manifest.document()
        or current.source_inventory_sha256 != plan.source_inventory_sha256
    ):
        raise _fail("object_storage_upload_plan_changed")
    return current


def _durable_result_counts(
    plan: ObjectStorageUploadPlan, ledger: preservation._ManifestBoundPreservationLedger
) -> dict[str, Any]:
    counts = {status: 0 for status in _PUBLIC_STATUSES}
    bytes_uploaded = 0
    put_calls = 0
    charged = 0
    conservative = False
    for spec in plan.specs:
        receipt = _read_receipt(plan, spec)
        if receipt is None:
            raise _fail("object_storage_upload_receipt_conflict")
        result_status = str(receipt.get("result_status") or "")
        status = STATUS_REVIEW_REQUIRED if result_status == "remote_conflict_different_bytes" else result_status
        if status not in counts:
            raise _fail("object_storage_upload_receipt_conflict")
        counts[status] += 1
        bytes_uploaded += int(receipt.get("bytes_uploaded") or 0)
        put_calls += int(receipt.get("provider_put_call_count") or 0)
        charged += int(receipt.get("provider_put_call_charged_count") or 0)
        conservative = conservative or receipt.get("provider_put_call_count_evidence") == "conservative_reserved"
    if sum(counts.values()) != len(plan.specs):
        raise _fail("object_storage_upload_receipt_conflict")
    return {
        "classification_counts": counts,
        "bytes_uploaded": bytes_uploaded,
        "provider_put_call_count": put_calls,
        "provider_put_call_charged_count": charged,
        "provider_put_call_count_evidence": "conservative_reserved" if conservative else "exact_observed",
    }


def _apply_with_store(
    plan: ObjectStorageUploadPlan,
    authority: ExactOperationApprovalAuthority,
    transport: archive_services.ObjectStorageTransport,
    checkpoints: FileExactOperationCheckpointStore,
    *,
    reviewed_by: str,
    resume: bool,
    progress_hook: Callable[[ExactOperationProgress], None] | None,
    _runner_entered: list[bool] | None = None,
) -> dict[str, Any]:
    if plan.manifest is None:
        raise _fail("object_storage_upload_no_writes")
    _require_manifest_index_authority(plan)
    writer = _Writer(plan, transport, reviewed_by=reviewed_by)
    verifier = _Verifier(plan, writer.query, writer.ledger)
    if _runner_entered is not None:
        _runner_entered[0] = True
    core = apply_exact_operation(
        plan.manifest,
        payloads=_Payloads(plan),
        writer=writer,
        verifier=verifier,
        checkpoint_store=checkpoints,
        approval_authority=authority,
        resume=resume,
        progress_hook=progress_hook,
    )
    durable = _durable_result_counts(plan, writer.ledger)
    counts = durable["classification_counts"]
    review_count = int(counts[STATUS_REVIEW_REQUIRED])
    return {
        "schema_version": RESULT_SCHEMA,
        "ok": core.get("status") == "completed",
        "state": "completed_with_review" if review_count else "uploaded",
        "manifest_sha256": plan.manifest.manifest_sha256,
        "execution": core,
        "item_count": len(plan.specs),
        "uploaded_count": int(counts[STATUS_UPLOADED]),
        "skipped_remote_same_count": int(counts[STATUS_SKIPPED_REMOTE_SAME]),
        "review_required_count": review_count,
        "status_counts": counts,
        "classification_sum_matches_item_count": sum(counts.values()) == len(plan.specs),
        "bytes_uploaded": durable["bytes_uploaded"],
        "provider_put_call_count": durable["provider_put_call_count"],
        "provider_put_call_charged_count": durable["provider_put_call_charged_count"],
        "provider_put_call_count_evidence": durable["provider_put_call_count_evidence"],
        "expected_no_retry_provider_put_call_count": writer.expected_no_retry_put_calls,
        "manifest_bound_provider_put_call_ceiling": writer.manifest_bound_put_call_ceiling,
        "manifest_location_updates": writer.manifest_update_count,
        "receipts_created_count": writer.receipts_created_count,
        "manifest_index_generation": writer.manifest_index_lifecycle.generation,
        "manifest_index_resealed": writer.manifest_index_lifecycle.resumed,
        "independent_remote_verification": True,
        "remote_key_layout": REMOTE_KEY_LAYOUT,
        "existing_remote_copy_overwritten": False,
        "remote_object_deleted": False,
        "remote_delete_on_revert_supported": False,
        "common_exact_operation_manifest_used": True,
        "manifest_bound_private_ledger_used": True,
        "next_safe_actions": (
            [
                "Review the review_required objects: the remote copy at the content-addressed key holds different bytes; it was not overwritten and got no manifest location."
            ]
            if review_count
            else []
        ),
        "private_values_echoed": False,
        "local_paths_echoed": False,
        "remote_keys_echoed": False,
        "credential_values_echoed": False,
    }


def _apply_core(
    plan: ObjectStorageUploadPlan,
    claim: _ClaimedExactHumanApproval,
    *,
    context: ExactHumanApprovalContext,
    reviewed_by: str,
    transport_factory: Callable[[], archive_services.ObjectStorageTransport],
    resume: bool = False,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
) -> dict[str, Any]:
    if type(plan) is not ObjectStorageUploadPlan or plan.manifest is None:
        raise _fail("object_storage_upload_no_writes")
    # v0.4.36 (beta letter 168 ①): everything before the exact runner's first
    # checkpoint (re-plan, approval binding, lock, control document,
    # transport, index authority, ledger) writes nothing durable to the
    # archive; a failure there is marked so the broker can close the claim.
    runner_entered = [False]
    try:
        current = _fresh_revalidated(plan, progress_hook=progress_hook)
        authority = _assert_approved(current, claim, context)
        with exact_operation_writer_lock(current.archive_root) as writer_lock:
            _persist_control(current)
            checkpoints = FileExactOperationCheckpointStore(current.archive_root, writer_lock=writer_lock)
            try:
                transport = transport_factory()
            except Exception:
                raise _fail("object_storage_upload_remote_unavailable") from None
            if transport is None:
                raise _fail("object_storage_upload_remote_unavailable")
            return _apply_with_store(
                current,
                authority,
                transport,
                checkpoints,
                reviewed_by=reviewed_by,
                resume=resume,
                progress_hook=progress_hook,
                _runner_entered=runner_entered,
            )
    except (ObjectStorageUploadError, ExactOperationManifestError, preservation.ObjectStoragePreservationError) as failure:
        if not resume and not runner_entered[0] and getattr(failure, "effects", None) is None:
            try:
                failure.effects = "none"
            except Exception:
                pass
        raise


def execute_object_storage_upload(
    plan: ObjectStorageUploadPlan,
    *,
    reviewer_claim: str,
    transport_factory: Callable[[], archive_services.ObjectStorageTransport],
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
) -> dict[str, Any]:
    if type(plan) is not ObjectStorageUploadPlan or not plan.approveable:
        raise _fail("object_storage_upload_no_writes")
    context = object_storage_upload_context(plan, reviewer_claim=reviewer_claim)
    reviewer = str(reviewer_claim).strip()
    return _execute_exact_human_approved_write(
        plan.archive_root,
        context,
        lambda claim: _apply_core(
            plan,
            claim,
            context=context,
            reviewed_by=reviewer,
            transport_factory=transport_factory,
            progress_hook=progress_hook,
        ),
    )


def resume_object_storage_upload(
    plan: ObjectStorageUploadPlan,
    *,
    reviewer_claim: str,
    approval_id: str,
    execution_sha256: str,
    transport_factory: Callable[[], archive_services.ObjectStorageTransport],
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
    key_provider: Any = None,
) -> dict[str, Any]:
    if (
        type(plan) is not ObjectStorageUploadPlan
        or not plan.loaded_from_control
        or plan.manifest is None
        or _SHA256_RE.fullmatch(str(execution_sha256 or "")) is None
    ):
        raise _fail("object_storage_upload_resume_invalid")
    context = object_storage_upload_context(plan, reviewer_claim=reviewer_claim)
    reviewer = str(reviewer_claim).strip()
    with exact_operation_writer_lock(plan.archive_root) as writer_lock:
        checkpoints = FileExactOperationCheckpointStore(plan.archive_root, writer_lock=writer_lock)

        def _writer(claim: _ClaimedExactHumanApproval) -> Mapping[str, Any]:
            current = _fresh_revalidated(plan, progress_hook=progress_hook)
            authority = _assert_approved(current, claim, context)
            actual = exact_operation_execution_sha256(current.manifest, approval_authority=authority)
            if not hmac.compare_digest(actual, execution_sha256):
                raise _fail("object_storage_upload_resume_invalid")
            try:
                transport = transport_factory()
            except Exception:
                raise _fail("object_storage_upload_remote_unavailable") from None
            return _apply_with_store(
                current,
                authority,
                transport,
                checkpoints,
                reviewed_by=reviewer,
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


def verify_object_storage_upload(
    plan: ObjectStorageUploadPlan,
    *,
    transport: archive_services.ObjectStorageTransport,
    heartbeat: Callable[[], None] | None = None,
) -> dict[str, Any]:
    if type(plan) is not ObjectStorageUploadPlan or plan.manifest is None:
        raise _fail("object_storage_upload_plan_invalid")
    _require_setup_evidence(plan.archive_root, provider_kind=plan.provider_kind, store_ref=plan.store_ref)
    query = preservation.ObjectStorageRemoteQueryAdapter(transport)
    ledger = _preservation_guard(
        lambda: preservation._ManifestBoundPreservationLedger(plan), code="object_storage_upload_control_invalid"
    )
    verifier = _Verifier(plan, query, ledger)
    result = verify_exact_operation(plan.manifest, verifier=verifier, state="post", heartbeat=heartbeat)
    return {
        "schema_version": VERIFY_SCHEMA,
        "ok": result["all_match"],
        "manifest_sha256": plan.manifest.manifest_sha256,
        "verified_item_count": len(plan.specs) if result["all_match"] else 0,
        "verification": result,
        "provider_api_called": True,
        "writes_performed": False,
        "private_values_echoed": False,
        "remote_keys_echoed": False,
    }


__all__ = [
    "ObjectStorageUploadError",
    "ObjectStorageUploadPlan",
    "UploadSpec",
    "execute_object_storage_upload",
    "load_object_storage_upload_plan",
    "object_storage_upload_context",
    "plan_object_storage_upload",
    "resume_object_storage_upload",
    "verify_object_storage_upload",
]
