"""Exact create-only persistence for one reviewed source-intake plan.

The input plan may live outside the archive, but it must already be redacted
and privacy-safe.  Only its validated JSON document is written below
``receipts/sources``.  The public result never echoes either input or target
paths.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
import stat
from dataclasses import dataclass, field
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
from .paths import (
    ArchivePathError,
    normalize_archive_relative_path,
    resolve_archive_relative_path,
)


OPERATION = "source_intake_record"
PLAN_SCHEMA = "wom-kit/source-intake-record-exact-plan/v0.1"
RESULT_SCHEMA = "wom-kit/source-intake-record-exact-result/v0.1"
EVIDENCE_SCHEMA = "wom-kit/source-intake-record-exact-evidence/v1"
TARGET_KIND = "source_intake_record"
FIELD_REF = "receipt_bytes"
ITEM_ID = "item:source-intake-record"
_MAX_PLAN_BYTES = 8 * 1024 * 1024
_MAX_RECEIPT_BYTES = 8 * 1024 * 1024
_MAX_JSON_DEPTH = 16
_MAX_JSON_NODES = 50_000
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

_TOP_LEVEL_KEYS = frozenset(
    {
        "ok",
        "dry_run",
        "lifecycle_action",
        "archive_id",
        "profile_id",
        "input_kind",
        "source_kind",
        "source_role",
        "objet_status",
        "source_refs_for_draft",
        "objet_ref",
        "provider_object_ref",
        "project_intake_context",
        "object_storage_context",
        "content_access",
        "draft_provenance_suggestions",
        "source_metadata",
        "blockers",
        "warnings",
        "next_safe_actions",
        "would_change",
    }
)
_SOURCE_REF_KEYS = frozenset({"type", "value", "role"})
_OBJET_REF_KEYS = frozenset(
    {
        "ref",
        "object_id",
        "manifested",
        "manifest_path",
        "logical_key",
        "mime",
        "size_bytes",
    }
)
_PROVIDER_OBJECT_REF_KEYS = frozenset(
    {"provider", "provider_kind", "provider_object_id", "manifested"}
)
_PROJECT_CONTEXT_KEYS = frozenset(
    {
        "provided",
        "ok",
        "receipt_path",
        "session_id",
        "reviewed_by",
        "reviewed_at",
        "decision_sha256",
        "checklist_coverage",
        "readiness",
        "decision_values_included",
        "automatic_execution_authorized",
    }
)
_CHECKLIST_COVERAGE_KEYS = frozenset(
    {
        "answered_count",
        "required_count",
        "answered_checklist_ids",
        "missing_checklist_ids",
        "complete",
    }
)
_READINESS_KEYS = frozenset(
    {"status", "ready_for_automatic_execution"}
)
_OBJECT_STORAGE_CONTEXT_KEYS = frozenset(
    {
        "object_storage_configured",
        "candidate_storage_providers",
        "manual_setup_required",
        "upload_performed",
        "provider_api_called",
    }
)
_STORAGE_PROVIDER_KEYS = frozenset(
    {
        "binding_id",
        "provider",
        "provider_kind",
        "bucket",
        "prefix",
        "visibility",
        "enabled",
    }
)
_DRAFT_PROVENANCE_KEYS = frozenset(
    {"source", "assisted_by", "derived_from"}
)
_SOURCE_METADATA_KEYS = frozenset(
    {
        "label",
        "extension",
        "mime",
        "size_bytes",
        "modified_at",
        "local_path",
        "local_file_identity_sha256",
        "local_file_identity_kind",
        "body_read",
        "full_hash_calculated",
        "source_id",
        "source_type",
        "source_map_path",
        "item_id",
        "item_kind",
        "relative_path",
        "scan_status",
        "logical_key",
        "provider",
        "provider_kind",
        "runtime",
        "artifact_kind",
    }
)


class SourceIntakeRecordExactError(RuntimeError):
    """A fixed-code refusal that never retains source content or paths."""

    _CODES = {
        "source_intake_record_archive_invalid",
        "source_intake_record_plan_invalid",
        "source_intake_record_request_invalid",
        "source_intake_record_plan_unsafe",
        "source_intake_record_target_unsafe",
        "source_intake_record_target_collision",
        "source_intake_record_completion_evidence_required",
        "source_intake_record_plan_blocked",
        "source_intake_record_plan_digest_mismatch",
        "source_intake_record_approval_required",
        "source_intake_record_state_drifted",
        "source_intake_record_write_failed",
        "exact_human_approval_cancelled",
    }

    def __init__(self, code: str) -> None:
        self.code = (
            code if code in self._CODES else "source_intake_record_write_failed"
        )
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"SourceIntakeRecordExactError({self.code!r})"


def _fail(code: str) -> SourceIntakeRecordExactError:
    return SourceIntakeRecordExactError(code)


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            archive_services.json_safe(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise _fail("source_intake_record_plan_invalid") from None


def _receipt_bytes(document: dict[str, Any]) -> bytes:
    try:
        return (
            json.dumps(
                archive_services.json_safe(document),
                indent=2,
                ensure_ascii=False,
                default=str,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise _fail("source_intake_record_plan_invalid") from None


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
            parse_constant=lambda _value: (_ for _ in ()).throw(
                ValueError("non_finite_json_number")
            ),
        )
    except (UnicodeError, ValueError, json.JSONDecodeError):
        raise _fail("source_intake_record_plan_invalid") from None
    if not isinstance(loaded, dict):
        raise _fail("source_intake_record_plan_invalid")
    return loaded


def _validate_json_bounds(value: Any) -> None:
    remaining = _MAX_JSON_NODES

    def visit(item: Any, depth: int) -> None:
        nonlocal remaining
        remaining -= 1
        if remaining < 0 or depth > _MAX_JSON_DEPTH:
            raise _fail("source_intake_record_plan_invalid")
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise _fail("source_intake_record_plan_invalid")
                visit(child, depth + 1)
            return
        if isinstance(item, list):
            for child in item:
                visit(child, depth + 1)
            return
        if isinstance(item, float) and not math.isfinite(item):
            raise _fail("source_intake_record_plan_invalid")
        if item is not None and not isinstance(item, (str, int, float, bool)):
            raise _fail("source_intake_record_plan_invalid")

    visit(value, 0)


def _require_mapping(value: Any, allowed: frozenset[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or not set(value).issubset(allowed):
        raise _fail("source_intake_record_plan_invalid")
    return value


def _require_string_list(value: Any) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) for item in value
    ):
        raise _fail("source_intake_record_plan_invalid")
    return value


def _validate_source_intake_shape(document: dict[str, Any]) -> None:
    """Accept only the public source-intake v0.4 plan shape.

    The older draft validator intentionally extracts only fields it needs.  A
    persistence writer must be stricter: otherwise an unknown ``body`` member
    could pass extraction and become durable archive content.
    """

    if set(document) != _TOP_LEVEL_KEYS:
        raise _fail("source_intake_record_plan_invalid")

    refs = document.get("source_refs_for_draft")
    if not isinstance(refs, list):
        raise _fail("source_intake_record_plan_invalid")
    for ref in refs:
        mapping = _require_mapping(ref, _SOURCE_REF_KEYS)
        if set(mapping) != _SOURCE_REF_KEYS:
            raise _fail("source_intake_record_plan_invalid")

    _require_mapping(document.get("objet_ref"), _OBJET_REF_KEYS)
    _require_mapping(
        document.get("provider_object_ref"),
        _PROVIDER_OBJECT_REF_KEYS,
    )

    project = _require_mapping(
        document.get("project_intake_context"),
        _PROJECT_CONTEXT_KEYS,
    )
    if project.get("provided") is True:
        if set(project) != _PROJECT_CONTEXT_KEYS:
            raise _fail("source_intake_record_plan_invalid")
        coverage = _require_mapping(
            project.get("checklist_coverage"),
            _CHECKLIST_COVERAGE_KEYS,
        )
        readiness = _require_mapping(
            project.get("readiness"),
            _READINESS_KEYS,
        )
        if set(coverage) != _CHECKLIST_COVERAGE_KEYS or set(
            readiness
        ) != _READINESS_KEYS:
            raise _fail("source_intake_record_plan_invalid")
        _require_string_list(coverage.get("answered_checklist_ids"))
        _require_string_list(coverage.get("missing_checklist_ids"))
    elif set(project) != {
        "provided",
        "decision_values_included",
        "automatic_execution_authorized",
    }:
        raise _fail("source_intake_record_plan_invalid")

    storage = _require_mapping(
        document.get("object_storage_context"),
        _OBJECT_STORAGE_CONTEXT_KEYS,
    )
    if set(storage) != _OBJECT_STORAGE_CONTEXT_KEYS:
        raise _fail("source_intake_record_plan_invalid")
    candidates = storage.get("candidate_storage_providers")
    if not isinstance(candidates, list):
        raise _fail("source_intake_record_plan_invalid")
    for candidate in candidates:
        _require_mapping(candidate, _STORAGE_PROVIDER_KEYS)

    content_access = _require_mapping(
        document.get("content_access"),
        frozenset(archive_services.SOURCE_INTAKE_CONTENT_ACCESS_EXPECTATIONS),
    )
    if set(content_access) != set(
        archive_services.SOURCE_INTAKE_CONTENT_ACCESS_EXPECTATIONS
    ):
        raise _fail("source_intake_record_plan_invalid")

    provenance = _require_mapping(
        document.get("draft_provenance_suggestions"),
        _DRAFT_PROVENANCE_KEYS,
    )
    for key in ("assisted_by", "derived_from"):
        if key in provenance:
            _require_string_list(provenance[key])

    metadata = _require_mapping(
        document.get("source_metadata"),
        _SOURCE_METADATA_KEYS,
    )
    if any(isinstance(value, (dict, list)) for value in metadata.values()):
        raise _fail("source_intake_record_plan_invalid")

    for key in ("blockers", "warnings", "next_safe_actions"):
        _require_string_list(document.get(key))
    if document.get("would_change") != []:
        raise _fail("source_intake_record_plan_invalid")


def _is_link_or_reparse(info: os.stat_result) -> bool:
    marker = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return stat.S_ISLNK(info.st_mode) or bool(
        int(getattr(info, "st_file_attributes", 0)) & marker
    )


def _reject_link_or_reparse_chain(path: Path) -> None:
    current = path.absolute()
    while True:
        try:
            info = current.lstat()
        except OSError:
            raise _fail("source_intake_record_plan_invalid") from None
        if _is_link_or_reparse(info):
            raise _fail("source_intake_record_plan_invalid")
        parent = current.parent
        if parent == current:
            return
        current = parent


def _stable_regular_bytes(path: Path, *, maximum: int) -> bytes:
    _reject_link_or_reparse_chain(path)
    raw, reason = archive_services._bounded_stable_regular_file_read(
        path,
        max_bytes=maximum,
    )
    if raw is None or reason is not None:
        raise _fail("source_intake_record_plan_invalid")
    return raw


def _resolve_plan_path(root: Path, plan_path: Path | str) -> Path:
    raw = os.fspath(plan_path)
    if not raw or "\x00" in raw:
        raise _fail("source_intake_record_plan_invalid")
    supplied = Path(raw)
    if supplied.is_absolute():
        return supplied
    try:
        normalized = normalize_archive_relative_path(raw)
        lexical = root.resolve().joinpath(*normalized.split("/"))
        _reject_link_or_reparse_chain(lexical)
        return resolve_archive_relative_path(root, raw)
    except ArchivePathError:
        raise _fail("source_intake_record_plan_invalid") from None


def _validated_plan_document(
    raw: bytes,
    *,
    archive_id: str,
) -> tuple[dict[str, Any], str]:
    document = _strict_json_object(raw)
    _validate_json_bounds(document)
    _validate_source_intake_shape(document)
    blockers: list[str] = []
    archive_services.prepare_source_intake_plan_for_draft(document, blockers)
    if document.get("archive_id") != archive_id or blockers:
        raise _fail("source_intake_record_plan_invalid")
    if archive_services.source_intake_plan_has_unsafe_stored_string(document):
        raise _fail("source_intake_record_plan_unsafe")
    return document, archive_services.sha256_json_value(document)


@dataclass(frozen=True, repr=False)
class SourceIntakeRecordExactPlan:
    archive_root: Path = field(repr=False)
    archive_id: str
    input_plan_path: Path = field(repr=False)
    input_plan_bytes_sha256: str | None
    source_intake_plan_sha256: str | None
    receipt_relative_path: str | None = field(repr=False)
    receipt_bytes: bytes | None = field(repr=False)
    source_basis_bytes: bytes | None = field(repr=False)
    manifest: ExactOperationManifest | None = field(repr=False)
    state: str
    blockers: tuple[str, ...]

    @property
    def approveable(self) -> bool:
        return (
            self.manifest is not None
            and self.state == "ready"
            and not self.blockers
        )

    @property
    def preexisting_unverified(self) -> bool:
        return (
            self.state == "preexisting_unverified"
            and self.blockers
            == ("source_intake_record_completion_evidence_required",)
        )

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
            "lifecycle_action": "source_intake_record_exact_plan",
            "plan_sha256": manifest.manifest_sha256 if manifest else None,
            "source_intake_plan_sha256": self.source_intake_plan_sha256,
            "target_binding_sha256": (
                manifest.target_set_sha256 if manifest else None
            ),
            "source_binding_sha256": (
                manifest.source_set_sha256 if manifest else None
            ),
            "effect_binding_sha256": (
                manifest.effect_set_sha256 if manifest else None
            ),
            "receipt_create_count": 1 if self.approveable else 0,
            "receipt_byte_count": len(self.receipt_bytes or b""),
            "general_intake_chain_complete_after_approval": bool(
                self.approveable
            ),
            "blockers": list(self.blockers),
            "warnings": [],
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
    input_path: Path,
    blocker: str,
    state: str = "blocked",
) -> SourceIntakeRecordExactPlan:
    return SourceIntakeRecordExactPlan(
        archive_root=root,
        archive_id=archive_id,
        input_plan_path=input_path,
        input_plan_bytes_sha256=None,
        source_intake_plan_sha256=None,
        receipt_relative_path=None,
        receipt_bytes=None,
        source_basis_bytes=None,
        manifest=None,
        state=state,
        blockers=(blocker,),
    )


def plan_source_intake_record(
    archive_root: Path | str,
    plan_path: Path | str,
) -> SourceIntakeRecordExactPlan:
    """Build one absent-to-exact-bytes receipt creation manifest."""

    try:
        root = archive_services.require_existing_archive_root(archive_root)
        archive_id = archive_services.read_archive_id(root)
    except Exception:
        raise _fail("source_intake_record_archive_invalid") from None
    try:
        input_path = _resolve_plan_path(root, plan_path)
        input_raw = _stable_regular_bytes(input_path, maximum=_MAX_PLAN_BYTES)
        document, document_sha256 = _validated_plan_document(
            input_raw,
            archive_id=archive_id,
        )
        receipt_relative = archive_services.source_intake_record_path(
            document_sha256
        )
        receipt_raw = _receipt_bytes(document)
        if len(receipt_raw) > _MAX_RECEIPT_BYTES:
            raise _fail("source_intake_record_plan_invalid")
        if archive_services.objet_capture_path_chain_blockers(
            root,
            receipt_relative,
        ):
            raise _fail("source_intake_record_target_unsafe")
        receipt_path = archive_services.archive_internal_path(
            root,
            receipt_relative,
        )
    except SourceIntakeRecordExactError as error:
        return _blocked_plan(
            root=root,
            archive_id=archive_id,
            input_path=Path(os.fspath(plan_path)),
            blocker=error.code,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError):
        return _blocked_plan(
            root=root,
            archive_id=archive_id,
            input_path=Path(os.fspath(plan_path)),
            blocker="source_intake_record_plan_invalid",
        )

    archive_identity = exact_human_approval_archive_identity_sha256(archive_id)
    input_sha256 = _sha_bytes(input_raw)
    receipt_sha256 = _sha_bytes(receipt_raw)
    source_basis = _canonical_bytes(
        {
            "schema": "wom-kit/source-intake-record-exact-source/v0.1",
            "archive_identity_sha256": archive_identity,
            "input_plan_bytes_sha256": input_sha256,
            "source_intake_plan_sha256": document_sha256,
            "receipt_bytes_sha256": receipt_sha256,
        }
    )
    target_identity = _sha_document(
        {
            "schema": "wom-kit/source-intake-record-exact-target/v0.1",
            "archive_identity_sha256": archive_identity,
            "target_ref": receipt_relative,
        }
    )
    manifest = ExactOperationManifest.build(
        operation=OPERATION,
        archive_identity_sha256=archive_identity,
        items=(
            ExactOperationItem(
                ordinal=0,
                item_id=ITEM_ID,
                target_kind=TARGET_KIND,
                target_ref=receipt_relative,
                target_identity_sha256=target_identity,
                fields=(
                    ExactFieldEffect(
                        field_ref=FIELD_REF,
                        pre_sha256=ABSENT_FIELD_SHA256,
                        post_sha256=hash_field_value(receipt_raw),
                        source_sha256=hash_field_value(source_basis),
                    ),
                ),
            ),
        ),
        operation_evidence={
            "schema": EVIDENCE_SCHEMA,
            "counts": {
                "receipt_create_count": 1,
                "receipt_byte_count": len(receipt_raw),
            },
            "digests": {
                "input_plan_bytes_sha256": input_sha256,
                "source_intake_plan_sha256": document_sha256,
                "receipt_bytes_sha256": receipt_sha256,
                "source_basis_sha256": _sha_bytes(source_basis),
            },
            "private_values_echoed": False,
        },
    )
    existing, existing_reason = archive_services._bounded_stable_regular_file_read(
        receipt_path,
        max_bytes=_MAX_RECEIPT_BYTES,
    )
    if existing_reason != "missing":
        if (
            existing is not None
            and existing_reason is None
            and hmac.compare_digest(existing, receipt_raw)
        ):
            return SourceIntakeRecordExactPlan(
                archive_root=root,
                archive_id=archive_id,
                input_plan_path=input_path,
                input_plan_bytes_sha256=input_sha256,
                source_intake_plan_sha256=document_sha256,
                receipt_relative_path=receipt_relative,
                receipt_bytes=receipt_raw,
                source_basis_bytes=source_basis,
                manifest=manifest,
                state="preexisting_unverified",
                blockers=(
                    "source_intake_record_completion_evidence_required",
                ),
            )
        return _blocked_plan(
            root=root,
            archive_id=archive_id,
            input_path=input_path,
            blocker="source_intake_record_target_collision",
            state="target_collision",
        )
    return SourceIntakeRecordExactPlan(
        archive_root=root,
        archive_id=archive_id,
        input_plan_path=input_path,
        input_plan_bytes_sha256=input_sha256,
        source_intake_plan_sha256=document_sha256,
        receipt_relative_path=receipt_relative,
        receipt_bytes=receipt_raw,
        source_basis_bytes=source_basis,
        manifest=manifest,
        state="ready",
        blockers=(),
    )


def approval_context(
    plan: SourceIntakeRecordExactPlan,
    *,
    reviewer_claim: str,
) -> ExactHumanApprovalContext:
    if not plan.approveable or plan.manifest is None:
        raise _fail("source_intake_record_plan_blocked")
    if archive_services.safe_project_intake_actor_id(reviewer_claim) is None:
        raise _fail("source_intake_record_approval_required")
    try:
        binding = operation_approval_binding.exact_operation_manifest_approval_binding(
            plan.manifest,
            operation=ExactHumanApprovalOperation.source_intake_record,
            archive_id=plan.archive_id,
            warnings=(),
        )
        return binding.context(
            archive_id=plan.archive_id,
            reviewer_claim=reviewer_claim,
        )
    except Exception:
        raise _fail("source_intake_record_approval_required") from None


def _authority(
    plan: SourceIntakeRecordExactPlan,
    claim: _ClaimedExactHumanApproval,
    context: ExactHumanApprovalContext,
) -> ExactOperationApprovalAuthority:
    if plan.manifest is None:
        raise _fail("source_intake_record_plan_blocked")
    expected = approval_context(plan, reviewer_claim=context.reviewer_claim)
    if context != expected or type(claim) is not _ClaimedExactHumanApproval:
        raise _fail("source_intake_record_approval_required")
    try:
        return ExactOperationApprovalAuthority.from_reference(
            claim.assert_ready_for_context(context)
        )
    except (ExactHumanApprovalError, ExactOperationManifestError):
        raise _fail("source_intake_record_approval_required") from None


class _Payloads:
    def __init__(self, plan: SourceIntakeRecordExactPlan) -> None:
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
            raise _fail("source_intake_record_write_failed")
        if state == "pre":
            return None
        if state == "post" and self.plan.receipt_bytes is not None:
            return self.plan.receipt_bytes
        if state == "source" and self.plan.source_basis_bytes is not None:
            return self.plan.source_basis_bytes
        raise _fail("source_intake_record_write_failed")


class _Verifier:
    def __init__(self, plan: SourceIntakeRecordExactPlan) -> None:
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
            or target_ref != self.plan.receipt_relative_path
        ):
            raise _fail("source_intake_record_write_failed")
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
            or target_ref != self.plan.receipt_relative_path
            or field_ref != FIELD_REF
        ):
            raise _fail("source_intake_record_write_failed")
        try:
            target = archive_services.archive_internal_path(
                self.plan.archive_root,
                target_ref,
            )
        except archive_services.ArchiveServiceError:
            raise _fail("source_intake_record_write_failed") from None
        raw, reason = archive_services._bounded_stable_regular_file_read(
            target,
            max_bytes=_MAX_RECEIPT_BYTES,
        )
        if reason == "missing":
            return None
        if raw is None or reason is not None:
            raise _fail("source_intake_record_target_collision")
        return raw


class _Writer:
    def __init__(self, plan: SourceIntakeRecordExactPlan) -> None:
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
            or target_ref != self.plan.receipt_relative_path
            or field_ref != FIELD_REF
            or value is None
            or value != self.plan.receipt_bytes
        ):
            raise _fail("source_intake_record_write_failed")
        fresh = plan_source_intake_record(
            self.plan.archive_root,
            self.plan.input_plan_path,
        )
        if (
            not fresh.approveable
            or fresh.manifest is None
            or self.plan.manifest is None
            or not hmac.compare_digest(
                fresh.manifest.manifest_sha256,
                self.plan.manifest.manifest_sha256,
            )
        ):
            raise _fail("source_intake_record_state_drifted")
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
                    written = os.write(
                        descriptor,
                        value[offset : offset + 64 * 1024],
                    )
                    if written <= 0:
                        raise OSError("short_write")
                    offset += written
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            archive_services.fsync_directory(target.parent)
        except SourceIntakeRecordExactError:
            raise
        except FileExistsError:
            raise _fail("source_intake_record_target_collision") from None
        except OSError:
            raise _fail("source_intake_record_write_failed") from None


def _execute_core(
    plan: SourceIntakeRecordExactPlan,
    claim: _ClaimedExactHumanApproval,
    context: ExactHumanApprovalContext,
    *,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
) -> dict[str, Any]:
    authority = _authority(plan, claim, context)
    fresh = plan_source_intake_record(
        plan.archive_root,
        plan.input_plan_path,
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
        raise _fail("source_intake_record_state_drifted")
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
        "state": "source_intake_recorded",
        "lifecycle_action": "source_intake_record_exact_write",
        "plan_sha256": fresh.manifest.manifest_sha256,
        "source_intake_plan_sha256": fresh.source_intake_plan_sha256,
        "target_binding_sha256": fresh.manifest.target_set_sha256,
        "source_binding_sha256": fresh.manifest.source_set_sha256,
        "effect_binding_sha256": fresh.manifest.effect_set_sha256,
        "receipt_create_count": 1,
        "checkpoint_count": core["checkpoint_count"],
        "final_receipt_sha256": core["final_receipt_sha256"],
        "general_intake_chain_complete": True,
        "independent_verification": True,
        "writes_performed": True,
        "provider_calls_performed": False,
        "credential_values_read": False,
        "private_values_echoed": False,
        "paths_echoed": False,
    }


def execute_source_intake_record(
    plan: SourceIntakeRecordExactPlan,
    *,
    expected_plan_sha256: str = "",
    reviewer_claim: str,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
) -> dict[str, Any]:
    expected = str(expected_plan_sha256 or "").strip().lower()
    if expected and (
        plan.manifest is None
        or _SHA256_RE.fullmatch(expected) is None
        or not hmac.compare_digest(expected, plan.manifest.manifest_sha256)
    ):
        raise _fail("source_intake_record_plan_digest_mismatch")
    if plan.preexisting_unverified:
        fresh = plan_source_intake_record(
            plan.archive_root,
            plan.input_plan_path,
        )
        if fresh.state == "target_collision":
            raise _fail("source_intake_record_target_collision")
        if (
            not fresh.preexisting_unverified
            or fresh.archive_id != plan.archive_id
            or fresh.manifest is None
            or plan.manifest is None
            or not hmac.compare_digest(
                fresh.manifest.manifest_sha256,
                plan.manifest.manifest_sha256,
            )
            or fresh.input_plan_bytes_sha256 is None
            or plan.input_plan_bytes_sha256 is None
            or not hmac.compare_digest(
                fresh.input_plan_bytes_sha256,
                plan.input_plan_bytes_sha256,
            )
            or fresh.source_intake_plan_sha256 is None
            or plan.source_intake_plan_sha256 is None
            or not hmac.compare_digest(
                fresh.source_intake_plan_sha256,
                plan.source_intake_plan_sha256,
            )
            or fresh.receipt_relative_path != plan.receipt_relative_path
            or fresh.receipt_bytes is None
            or plan.receipt_bytes is None
            or not hmac.compare_digest(
                fresh.receipt_bytes,
                plan.receipt_bytes,
            )
        ):
            raise _fail("source_intake_record_state_drifted")
        raise _fail("source_intake_record_completion_evidence_required")
    if not plan.approveable or plan.manifest is None:
        raise _fail("source_intake_record_plan_blocked")
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
    safe = SourceIntakeRecordExactError(code).code
    return {
        "schema_version": RESULT_SCHEMA,
        "ok": False,
        "state": (
            "preexisting_unverified"
            if safe == "source_intake_record_completion_evidence_required"
            else "blocked"
        ),
        "lifecycle_action": "source_intake_record_exact_write",
        "blockers": [safe],
        "general_intake_chain_complete": False,
        "writes_performed": False,
        "provider_calls_performed": False,
        "credential_values_read": False,
        "private_values_echoed": False,
        "paths_echoed": False,
    }


__all__ = [
    "SourceIntakeRecordExactError",
    "SourceIntakeRecordExactPlan",
    "approval_context",
    "execute_source_intake_record",
    "failure_document",
    "plan_source_intake_record",
]
