"""Exact create-only capture selection from a pre-existing intake record.

This module deliberately does not create source-intake evidence.  It only
bridges an already persisted, valid ``receipts/sources`` plan record to the
existing local Objet capture selection format.  The public result is
content-free; private archive-relative paths and selected bytes stay inside the
exact operation manifest and its domain adapters.
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import archive_services, operation_approval_binding
from .exact_human_approval import (
    ExactHumanApprovalError,
    _ClaimedExactHumanApproval,
    exact_human_approval_archive_identity_sha256,
)
from .exact_human_approval_windows import (
    ExactHumanApprovalContext,
    ExactHumanApprovalOperation,
)
from .exact_human_approval_workflow import _execute_exact_human_approved_write
from .exact_operation_manifest import (
    ABSENT_FIELD_SHA256,
    ExactFieldEffect,
    ExactOperationApprovalAuthority,
    ExactOperationItem,
    ExactOperationManifest,
    ExactOperationManifestError,
    ExactOperationProgress,
    FileExactOperationCheckpointStore,
    apply_exact_operation,
    exact_operation_writer_lock,
    hash_field_value,
)
from .paths import ArchivePathError, normalize_archive_relative_path


OPERATION = "objet_capture_selection_record"
PLAN_SCHEMA = "wom-kit/existing-intake-capture-selection-plan/v0.1"
RESULT_SCHEMA = "wom-kit/existing-intake-capture-selection-result/v0.1"
EVIDENCE_SCHEMA = "wom-kit/existing-intake-capture-selection/v1"
CAPABILITY_SCOPE = "preexisting_artifact_only"
TARGET_KIND = "objet_capture_selection"
FIELD_REF = "file_bytes"
ITEM_ID = "item:capture-selection"
_MAX_RECEIPT_BYTES = 8 * 1024 * 1024
_MAX_SELECTION_BYTES = 8 * 1024 * 1024
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SAFE_WARNING_CODES = frozenset({"zero_byte_file"})


class ExistingIntakeCaptureSelectionError(RuntimeError):
    """A content-free fixed-code refusal."""

    _CODES = {
        "existing_intake_capture_selection_archive_invalid",
        "existing_intake_capture_selection_request_invalid",
        "existing_intake_capture_selection_source_intake_invalid",
        "existing_intake_capture_selection_staged_input_invalid",
        "existing_intake_capture_selection_target_collision",
        "existing_intake_capture_selection_exact_target_present",
        "existing_intake_capture_selection_plan_blocked",
        "existing_intake_capture_selection_plan_digest_mismatch",
        "existing_intake_capture_selection_approval_required",
        "existing_intake_capture_selection_state_drifted",
        "existing_intake_capture_selection_write_failed",
        "exact_human_approval_cancelled",
    }

    def __init__(self, code: str) -> None:
        self.code = (
            code
            if code in self._CODES
            else "existing_intake_capture_selection_write_failed"
        )
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"ExistingIntakeCaptureSelectionError({self.code!r})"


def _fail(code: str) -> ExistingIntakeCaptureSelectionError:
    return ExistingIntakeCaptureSelectionError(code)


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise _fail("existing_intake_capture_selection_request_invalid") from None


def _sha_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha_document(value: Any) -> str:
    return _sha_bytes(_canonical_bytes(value))


def _strict_json_object(raw: bytes) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_json_member")
            result[key] = value
        return result

    try:
        loaded = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
        )
    except (UnicodeError, ValueError, json.JSONDecodeError):
        raise _fail("existing_intake_capture_selection_source_intake_invalid") from None
    if not isinstance(loaded, dict):
        raise _fail("existing_intake_capture_selection_source_intake_invalid")
    return loaded


def _stable_regular_bytes(path: Path, *, max_bytes: int) -> bytes:
    raw, reason = archive_services._bounded_stable_regular_file_read(
        path,
        max_bytes=max_bytes,
    )
    if raw is None or reason is not None:
        raise _fail("existing_intake_capture_selection_source_intake_invalid")
    return raw


def _stable_file_digest(
    path: Path,
    *,
    heartbeat: Callable[[], None],
) -> tuple[str, int]:
    """Hash one stable regular file without retaining its bytes."""

    try:
        before = os.lstat(path)
    except OSError:
        raise _fail("existing_intake_capture_selection_state_drifted") from None
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if (
        stat.S_ISLNK(before.st_mode)
        or not stat.S_ISREG(before.st_mode)
        or (
            reparse_flag
            and getattr(before, "st_file_attributes", 0) & reparse_flag
        )
    ):
        raise _fail("existing_intake_capture_selection_state_drifted")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(str(path), flags)
    except OSError:
        raise _fail("existing_intake_capture_selection_state_drifted") from None
    digest = hashlib.sha256()
    size = 0
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise _fail("existing_intake_capture_selection_state_drifted")
        while True:
            heartbeat()
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
        after = os.fstat(descriptor)
    except ExistingIntakeCaptureSelectionError:
        raise
    except OSError:
        raise _fail("existing_intake_capture_selection_state_drifted") from None
    finally:
        os.close(descriptor)
    before_ino = int(getattr(before, "st_ino", 0) or 0)
    opened_ino = int(getattr(opened, "st_ino", 0) or 0)
    if (
        int(before.st_dev) != int(opened.st_dev)
        or (before_ino and opened_ino and before_ino != opened_ino)
        or int(before.st_size) != size
        or int(after.st_size) != size
        or int(getattr(before, "st_mtime_ns", 0))
        != int(getattr(after, "st_mtime_ns", 0))
    ):
        raise _fail("existing_intake_capture_selection_state_drifted")
    return "sha256:" + digest.hexdigest(), size


@dataclass(frozen=True, repr=False)
class ExistingIntakeCaptureSelectionPlan:
    archive_root: Path
    archive_id: str
    staged_path: str
    source_intake_receipt: str
    request_item_id: str
    request_manifest_id: str | None
    selection_relative_path: str | None
    selection_bytes: bytes | None
    source_basis_bytes: bytes | None
    staged_bytes_sha256: str | None
    staged_size_bytes: int
    source_intake_receipt_bytes_sha256: str | None
    selection_document_sha256: str | None
    manifest: ExactOperationManifest | None
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    state: str

    @property
    def approveable(self) -> bool:
        return self.manifest is not None and not self.blockers and self.state == "ready"

    def public_document(self) -> dict[str, Any]:
        manifest = self.manifest
        return {
            "schema_version": PLAN_SCHEMA,
            "ok": self.approveable,
            "state": (
                "ready_for_exact_human_approval"
                if self.approveable
                else self.state
            ),
            "lifecycle_action": "objet_capture_selection_exact_plan",
            "capability_scope": CAPABILITY_SCOPE,
            "general_intake_chain_complete": False,
            "requires_existing_source_intake_receipt": True,
            "plan_sha256": manifest.manifest_sha256 if manifest else None,
            "target_binding_sha256": manifest.target_set_sha256 if manifest else None,
            "source_binding_sha256": manifest.source_set_sha256 if manifest else None,
            "effect_binding_sha256": manifest.effect_set_sha256 if manifest else None,
            "selected_item_count": 1 if manifest else 0,
            "source_intake_receipt_count": 1 if manifest else 0,
            "staged_byte_count": self.staged_size_bytes if manifest else 0,
            "selection_byte_count": len(self.selection_bytes or b""),
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "writes_performed": False,
            "provider_calls_performed": False,
            "credential_values_read": False,
            "private_values_echoed": False,
            "paths_echoed": False,
        }


def _blocked_plan(
    *,
    root: Path,
    archive_id: str,
    staged_path: str,
    source_intake_receipt: str,
    item_id: str,
    manifest_id: str | None,
    blocker: str,
    state: str = "blocked",
) -> ExistingIntakeCaptureSelectionPlan:
    return ExistingIntakeCaptureSelectionPlan(
        archive_root=root,
        archive_id=archive_id,
        staged_path=staged_path,
        source_intake_receipt=source_intake_receipt,
        request_item_id=item_id,
        request_manifest_id=manifest_id,
        selection_relative_path=None,
        selection_bytes=None,
        source_basis_bytes=None,
        staged_bytes_sha256=None,
        staged_size_bytes=0,
        source_intake_receipt_bytes_sha256=None,
        selection_document_sha256=None,
        manifest=None,
        blockers=(blocker,),
        warnings=(),
        state=state,
    )


def _read_valid_source_intake_receipt(
    root: Path,
    archive_id: str,
    relative: str,
) -> tuple[bytes, str]:
    try:
        normalized = normalize_archive_relative_path(relative)
    except ArchivePathError:
        raise _fail("existing_intake_capture_selection_source_intake_invalid") from None
    if not normalized.startswith("receipts/sources/"):
        raise _fail("existing_intake_capture_selection_source_intake_invalid")
    if archive_services.objet_capture_path_chain_blockers(root, normalized):
        raise _fail("existing_intake_capture_selection_source_intake_invalid")
    try:
        path = archive_services.archive_internal_path(root, normalized)
    except archive_services.ArchiveServiceError:
        raise _fail("existing_intake_capture_selection_source_intake_invalid") from None
    raw = _stable_regular_bytes(path, max_bytes=_MAX_RECEIPT_BYTES)
    document = _strict_json_object(raw)
    blockers: list[str] = []
    archive_services.prepare_source_intake_plan_for_draft(document, blockers)
    document_sha256 = archive_services.sha256_json_value(document)
    if (
        blockers
        or document.get("archive_id") != archive_id
        or archive_services.source_intake_plan_has_unsafe_stored_string(document)
        or normalized != archive_services.source_intake_record_path(document_sha256)
    ):
        raise _fail("existing_intake_capture_selection_source_intake_invalid")
    return raw, document_sha256


def plan_existing_intake_capture_selection(
    archive_root: Path | str,
    *,
    staged_path: str,
    source_intake_receipt: str,
    item_id: str = "item",
    manifest_id: str | None = None,
) -> ExistingIntakeCaptureSelectionPlan:
    """Build one stable, private-path-bound selection creation manifest."""

    try:
        root = archive_services.require_existing_archive_root(archive_root)
        archive_id = archive_services.read_archive_id(root)
    except Exception:
        raise _fail("existing_intake_capture_selection_archive_invalid") from None
    try:
        normalized_receipt = normalize_archive_relative_path(source_intake_receipt)
    except ArchivePathError:
        return _blocked_plan(
            root=root,
            archive_id=archive_id,
            staged_path=staged_path,
            source_intake_receipt=source_intake_receipt,
            item_id=item_id,
            manifest_id=manifest_id,
            blocker="existing_intake_capture_selection_source_intake_invalid",
        )
    try:
        receipt_bytes, receipt_document_sha256 = _read_valid_source_intake_receipt(
            root,
            archive_id,
            normalized_receipt,
        )
    except ExistingIntakeCaptureSelectionError as error:
        return _blocked_plan(
            root=root,
            archive_id=archive_id,
            staged_path=staged_path,
            source_intake_receipt=normalized_receipt,
            item_id=item_id,
            manifest_id=manifest_id,
            blocker=error.code,
        )

    try:
        legacy_preview = archive_services.objet_capture_selection_manifest(
            root,
            staged_path=staged_path,
            source_intake_receipt=normalized_receipt,
            item_id=item_id,
            manifest_id=manifest_id,
            dry_run=True,
            approve=False,
            reviewed_by=None,
        )
    except Exception:
        return _blocked_plan(
            root=root,
            archive_id=archive_id,
            staged_path=staged_path,
            source_intake_receipt=normalized_receipt,
            item_id=item_id,
            manifest_id=manifest_id,
            blocker="existing_intake_capture_selection_staged_input_invalid",
        )
    selection = legacy_preview.get("selection_manifest")
    if legacy_preview.get("ok") is not True or not isinstance(selection, dict):
        return _blocked_plan(
            root=root,
            archive_id=archive_id,
            staged_path=staged_path,
            source_intake_receipt=normalized_receipt,
            item_id=item_id,
            manifest_id=manifest_id,
            blocker="existing_intake_capture_selection_staged_input_invalid",
        )
    selection = copy.deepcopy(selection)
    selection["created_at"] = None
    selection["created_by"] = None
    if selection.get("project_intake_receipt_path") is not None:
        return _blocked_plan(
            root=root,
            archive_id=archive_id,
            staged_path=staged_path,
            source_intake_receipt=normalized_receipt,
            item_id=item_id,
            manifest_id=manifest_id,
            blocker="existing_intake_capture_selection_request_invalid",
        )
    items = selection.get("items")
    if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
        return _blocked_plan(
            root=root,
            archive_id=archive_id,
            staged_path=staged_path,
            source_intake_receipt=normalized_receipt,
            item_id=item_id,
            manifest_id=manifest_id,
            blocker="existing_intake_capture_selection_request_invalid",
        )
    selected = items[0]
    if "derived_text" in selected:
        return _blocked_plan(
            root=root,
            archive_id=archive_id,
            staged_path=staged_path,
            source_intake_receipt=normalized_receipt,
            item_id=item_id,
            manifest_id=manifest_id,
            blocker="existing_intake_capture_selection_request_invalid",
        )
    staged_digest = str(selected.get("approved_object_id") or "")
    staged_size = selected.get("expected_size_bytes")
    normalized_staged = str(selected.get("staged_path") or "")
    if (
        _SHA256_RE.fullmatch(staged_digest) is None
        or type(staged_size) is not int
        or staged_size < 0
        or not normalized_staged
        or selected.get("source_intake_plan_sha256")
        != receipt_document_sha256
    ):
        return _blocked_plan(
            root=root,
            archive_id=archive_id,
            staged_path=staged_path,
            source_intake_receipt=normalized_receipt,
            item_id=item_id,
            manifest_id=manifest_id,
            blocker="existing_intake_capture_selection_staged_input_invalid",
        )

    selection_document_sha256 = archive_services.sha256_json_value(selection)
    selection_bytes = _canonical_bytes(selection) + b"\n"
    if len(selection_bytes) > _MAX_SELECTION_BYTES:
        return _blocked_plan(
            root=root,
            archive_id=archive_id,
            staged_path=normalized_staged,
            source_intake_receipt=normalized_receipt,
            item_id=item_id,
            manifest_id=manifest_id,
            blocker="existing_intake_capture_selection_request_invalid",
        )
    selection_relative = (
        f"{archive_services.OBJET_CAPTURE_SELECTION_MANIFESTS_DIR}/"
        f"{selection_document_sha256.removeprefix('sha256:')}.selection.json"
    )
    try:
        selection_path = archive_services.archive_internal_path(
            root,
            selection_relative,
        )
    except archive_services.ArchiveServiceError:
        raise _fail("existing_intake_capture_selection_archive_invalid") from None
    target_raw, target_reason = archive_services._bounded_stable_regular_file_read(
        selection_path,
        max_bytes=_MAX_SELECTION_BYTES,
    )
    if target_reason != "missing":
        blocker = (
            "existing_intake_capture_selection_target_collision"
            if target_raw != selection_bytes
            else "existing_intake_capture_selection_exact_target_present"
        )
        state = "target_collision" if target_raw != selection_bytes else "exact_target_present"
        return _blocked_plan(
            root=root,
            archive_id=archive_id,
            staged_path=normalized_staged,
            source_intake_receipt=normalized_receipt,
            item_id=item_id,
            manifest_id=manifest_id,
            blocker=blocker,
            state=state,
        )

    archive_identity = exact_human_approval_archive_identity_sha256(archive_id)
    receipt_bytes_sha256 = _sha_bytes(receipt_bytes)
    selection_bytes_sha256 = _sha_bytes(selection_bytes)
    source_basis = _canonical_bytes(
        {
            "schema": "wom-kit/existing-intake-capture-selection-source/v0.1",
            "archive_identity_sha256": archive_identity,
            "staged_path": normalized_staged,
            "staged_bytes_sha256": staged_digest,
            "staged_size_bytes": staged_size,
            "source_intake_receipt_path": normalized_receipt,
            "source_intake_receipt_bytes_sha256": receipt_bytes_sha256,
            "source_intake_receipt_document_sha256": receipt_document_sha256,
            "selection_path": selection_relative,
            "selection_bytes_sha256": selection_bytes_sha256,
            "selection_document_sha256": selection_document_sha256,
        }
    )
    target_identity = _sha_document(
        {
            "schema": "wom-kit/existing-intake-capture-selection-target/v0.1",
            "archive_identity_sha256": archive_identity,
            "target_ref": selection_relative,
        }
    )
    field = ExactFieldEffect(
        field_ref=FIELD_REF,
        pre_sha256=ABSENT_FIELD_SHA256,
        post_sha256=hash_field_value(selection_bytes),
        source_sha256=hash_field_value(source_basis),
    )
    manifest = ExactOperationManifest.build(
        operation=OPERATION,
        archive_identity_sha256=archive_identity,
        items=(
            ExactOperationItem(
                ordinal=0,
                item_id=ITEM_ID,
                target_kind=TARGET_KIND,
                target_ref=selection_relative,
                target_identity_sha256=target_identity,
                fields=(field,),
            ),
        ),
        operation_evidence={
            "schema": EVIDENCE_SCHEMA,
            "counts": {
                "selected_item_count": 1,
                "selection_byte_count": len(selection_bytes),
                "source_intake_receipt_count": 1,
                "staged_byte_count": staged_size,
            },
            "digests": {
                "selection_bytes_sha256": selection_bytes_sha256,
                "selection_document_sha256": selection_document_sha256,
                "source_basis_sha256": _sha_bytes(source_basis),
                "source_intake_receipt_bytes_sha256": receipt_bytes_sha256,
                "source_intake_receipt_document_sha256": receipt_document_sha256,
                "staged_bytes_sha256": staged_digest,
            },
            "private_values_echoed": False,
        },
    )
    warnings = tuple(
        sorted(
            warning
            for warning in legacy_preview.get("warnings", [])
            if warning in _SAFE_WARNING_CODES
        )
    )
    return ExistingIntakeCaptureSelectionPlan(
        archive_root=root,
        archive_id=archive_id,
        staged_path=normalized_staged,
        source_intake_receipt=normalized_receipt,
        request_item_id=item_id,
        request_manifest_id=manifest_id,
        selection_relative_path=selection_relative,
        selection_bytes=selection_bytes,
        source_basis_bytes=source_basis,
        staged_bytes_sha256=staged_digest,
        staged_size_bytes=staged_size,
        source_intake_receipt_bytes_sha256=receipt_bytes_sha256,
        selection_document_sha256=selection_document_sha256,
        manifest=manifest,
        blockers=(),
        warnings=warnings,
        state="ready",
    )


def approval_context(
    plan: ExistingIntakeCaptureSelectionPlan,
    *,
    reviewer_claim: str,
) -> ExactHumanApprovalContext:
    if not plan.approveable or plan.manifest is None:
        raise _fail("existing_intake_capture_selection_plan_blocked")
    try:
        binding = operation_approval_binding.exact_operation_manifest_approval_binding(
            plan.manifest,
            operation=ExactHumanApprovalOperation.objet_capture_selection_record,
            archive_id=plan.archive_id,
            warnings=plan.warnings,
        )
        return binding.context(
            archive_id=plan.archive_id,
            reviewer_claim=reviewer_claim,
        )
    except Exception:
        raise _fail("existing_intake_capture_selection_approval_required") from None


def _authority(
    plan: ExistingIntakeCaptureSelectionPlan,
    claim: _ClaimedExactHumanApproval,
    context: ExactHumanApprovalContext,
) -> ExactOperationApprovalAuthority:
    if plan.manifest is None:
        raise _fail("existing_intake_capture_selection_plan_blocked")
    expected = approval_context(plan, reviewer_claim=context.reviewer_claim)
    if context != expected or type(claim) is not _ClaimedExactHumanApproval:
        raise _fail("existing_intake_capture_selection_approval_required")
    try:
        return ExactOperationApprovalAuthority.from_reference(
            claim.assert_ready_for_context(context)
        )
    except (ExactHumanApprovalError, ExactOperationManifestError):
        raise _fail("existing_intake_capture_selection_approval_required") from None


def _verify_private_sources(
    plan: ExistingIntakeCaptureSelectionPlan,
    *,
    heartbeat: Callable[[], None],
) -> None:
    if (
        plan.staged_bytes_sha256 is None
        or plan.source_intake_receipt_bytes_sha256 is None
    ):
        raise _fail("existing_intake_capture_selection_state_drifted")
    try:
        staged = archive_services.archive_internal_path(
            plan.archive_root,
            plan.staged_path,
        )
        receipt = archive_services.archive_internal_path(
            plan.archive_root,
            plan.source_intake_receipt,
        )
    except archive_services.ArchiveServiceError:
        raise _fail("existing_intake_capture_selection_state_drifted") from None
    staged_sha256, staged_size = _stable_file_digest(
        staged,
        heartbeat=heartbeat,
    )
    try:
        receipt_bytes = _stable_regular_bytes(
            receipt,
            max_bytes=_MAX_RECEIPT_BYTES,
        )
    except ExistingIntakeCaptureSelectionError:
        raise _fail("existing_intake_capture_selection_state_drifted") from None
    if not (
        hmac.compare_digest(staged_sha256, plan.staged_bytes_sha256)
        and staged_size == plan.staged_size_bytes
        and hmac.compare_digest(
            _sha_bytes(receipt_bytes),
            plan.source_intake_receipt_bytes_sha256,
        )
    ):
        raise _fail("existing_intake_capture_selection_state_drifted")


class _Payloads:
    def __init__(self, plan: ExistingIntakeCaptureSelectionPlan) -> None:
        self.plan = plan

    def field_value(
        self,
        *,
        item_id: str,
        field_ref: str,
        state: str,
        heartbeat: Callable[[], None],
    ) -> bytes | None:
        heartbeat()
        if item_id != ITEM_ID or field_ref != FIELD_REF:
            raise _fail("existing_intake_capture_selection_write_failed")
        if state == "pre":
            return None
        if state == "post" and self.plan.selection_bytes is not None:
            return self.plan.selection_bytes
        if state == "source" and self.plan.source_basis_bytes is not None:
            return self.plan.source_basis_bytes
        raise _fail("existing_intake_capture_selection_write_failed")


class _Verifier:
    def __init__(self, plan: ExistingIntakeCaptureSelectionPlan) -> None:
        self.plan = plan

    def target_identity_sha256(
        self,
        *,
        target_kind: str,
        target_ref: str,
        heartbeat: Callable[[], None],
    ) -> str:
        heartbeat()
        if (
            self.plan.manifest is None
            or target_kind != TARGET_KIND
            or target_ref != self.plan.selection_relative_path
        ):
            raise _fail("existing_intake_capture_selection_write_failed")
        return self.plan.manifest.items[0].target_identity_sha256

    def read_field(
        self,
        *,
        target_kind: str,
        target_ref: str,
        field_ref: str,
        heartbeat: Callable[[], None],
    ) -> bytes | None:
        heartbeat()
        if (
            target_kind != TARGET_KIND
            or target_ref != self.plan.selection_relative_path
            or field_ref != FIELD_REF
        ):
            raise _fail("existing_intake_capture_selection_write_failed")
        try:
            target = archive_services.archive_internal_path(
                self.plan.archive_root,
                target_ref,
            )
        except archive_services.ArchiveServiceError:
            raise _fail("existing_intake_capture_selection_write_failed") from None
        raw, reason = archive_services._bounded_stable_regular_file_read(
            target,
            max_bytes=_MAX_SELECTION_BYTES,
        )
        if reason == "missing":
            return None
        if raw is None or reason is not None:
            raise _fail("existing_intake_capture_selection_target_collision")
        return raw


class _Writer:
    def __init__(self, plan: ExistingIntakeCaptureSelectionPlan) -> None:
        self.plan = plan

    def write_field(
        self,
        *,
        target_kind: str,
        target_ref: str,
        field_ref: str,
        value: bytes | None,
        heartbeat: Callable[[], None],
    ) -> None:
        if (
            target_kind != TARGET_KIND
            or target_ref != self.plan.selection_relative_path
            or field_ref != FIELD_REF
            or value != self.plan.selection_bytes
            or value is None
        ):
            raise _fail("existing_intake_capture_selection_write_failed")
        _verify_private_sources(self.plan, heartbeat=heartbeat)
        try:
            target = archive_services.archive_internal_path(
                self.plan.archive_root,
                target_ref,
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            if archive_services.objet_capture_path_chain_blockers(
                self.plan.archive_root,
                target_ref,
            ):
                raise OSError("unsafe_target_chain")
            flags = (
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_BINARY", 0)
                | getattr(os, "O_NOFOLLOW", 0)
            )
            descriptor = os.open(str(target), flags, 0o600)
            try:
                offset = 0
                while offset < len(value):
                    heartbeat()
                    written = os.write(descriptor, value[offset : offset + 64 * 1024])
                    if written <= 0:
                        raise OSError("short_write")
                    offset += written
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            archive_services.fsync_directory(target.parent)
        except ExistingIntakeCaptureSelectionError:
            raise
        except FileExistsError:
            raise _fail("existing_intake_capture_selection_target_collision") from None
        except OSError:
            raise _fail("existing_intake_capture_selection_write_failed") from None


def _execute_core(
    plan: ExistingIntakeCaptureSelectionPlan,
    claim: _ClaimedExactHumanApproval,
    context: ExactHumanApprovalContext,
    *,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
) -> dict[str, Any]:
    authority = _authority(plan, claim, context)
    fresh = plan_existing_intake_capture_selection(
        plan.archive_root,
        staged_path=plan.staged_path,
        source_intake_receipt=plan.source_intake_receipt,
        item_id=plan.request_item_id,
        manifest_id=plan.request_manifest_id,
    )
    if (
        not fresh.approveable
        or fresh.manifest is None
        or plan.manifest is None
        or not hmac.compare_digest(
            fresh.manifest.manifest_sha256,
            plan.manifest.manifest_sha256,
        )
    ):
        raise _fail("existing_intake_capture_selection_state_drifted")
    with exact_operation_writer_lock(plan.archive_root) as writer_lock:
        checkpoints = FileExactOperationCheckpointStore(
            plan.archive_root,
            writer_lock=writer_lock,
        )
        core = apply_exact_operation(
            fresh.manifest,
            payloads=_Payloads(fresh),
            writer=_Writer(fresh),
            verifier=_Verifier(fresh),
            checkpoint_store=checkpoints,
            approval_authority=authority,
            progress_hook=progress_hook,
        )
    return {
        "schema_version": RESULT_SCHEMA,
        "ok": True,
        "state": "selection_recorded",
        "lifecycle_action": "objet_capture_selection_exact_record",
        "capability_scope": CAPABILITY_SCOPE,
        "general_intake_chain_complete": False,
        "requires_existing_source_intake_receipt": True,
        "plan_sha256": fresh.manifest.manifest_sha256,
        "target_binding_sha256": fresh.manifest.target_set_sha256,
        "source_binding_sha256": fresh.manifest.source_set_sha256,
        "effect_binding_sha256": fresh.manifest.effect_set_sha256,
        "selected_item_count": 1,
        "source_intake_receipt_count": 1,
        "checkpoint_count": core["checkpoint_count"],
        "final_receipt_sha256": core["final_receipt_sha256"],
        "independent_verification": True,
        "writes_performed": True,
        "provider_calls_performed": False,
        "credential_values_read": False,
        "private_values_echoed": False,
        "paths_echoed": False,
    }


def execute_existing_intake_capture_selection(
    plan: ExistingIntakeCaptureSelectionPlan,
    *,
    expected_plan_sha256: str = "",
    reviewer_claim: str,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
) -> dict[str, Any]:
    if not plan.approveable or plan.manifest is None:
        raise _fail("existing_intake_capture_selection_plan_blocked")
    expected = str(expected_plan_sha256 or "").strip().lower()
    if expected and (
        _SHA256_RE.fullmatch(expected) is None
        or not hmac.compare_digest(expected, plan.manifest.manifest_sha256)
    ):
        raise _fail("existing_intake_capture_selection_plan_digest_mismatch")
    context = approval_context(plan, reviewer_claim=reviewer_claim)
    return _execute_exact_human_approved_write(
        plan.archive_root,
        context,
        lambda claim: _execute_core(
            plan,
            claim,
            context,
            progress_hook=progress_hook,
        ),
    )


def failure_document(code: str) -> dict[str, Any]:
    safe = ExistingIntakeCaptureSelectionError(code).code
    return {
        "schema_version": RESULT_SCHEMA,
        "ok": False,
        "state": "blocked",
        "lifecycle_action": "objet_capture_selection_exact_record",
        "capability_scope": CAPABILITY_SCOPE,
        "general_intake_chain_complete": False,
        "requires_existing_source_intake_receipt": True,
        "blockers": [safe],
        "writes_performed": False,
        "provider_calls_performed": False,
        "credential_values_read": False,
        "private_values_echoed": False,
        "paths_echoed": False,
    }


__all__ = [
    "CAPABILITY_SCOPE",
    "ExistingIntakeCaptureSelectionError",
    "ExistingIntakeCaptureSelectionPlan",
    "approval_context",
    "execute_existing_intake_capture_selection",
    "failure_document",
    "plan_existing_intake_capture_selection",
]
