"""Exact-human adapter for one deterministic objet-capture batch.

The legacy batch workflow already owns the strict request reader and the
deterministic request-to-selection projection.  This module deliberately does
not add another parser or another capture writer.  It binds that projection to
the native ``objet_capture_batch`` approval and delegates the actual mutation
to ``archive_services.objet_capture_apply`` while keeping the batch operation
bound through the lower-level writer.

No selection file is published by this adapter.  The canonical selection
document is passed directly to the native writer, whose durable capture receipt
binds its digest.  This keeps cancellation free of domain writes and avoids an
unapproved support-file mutation between the native decision and the writer.
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import (
    archive_services,
    completion_workflows,
    operation_approval_binding,
    source_intake_batch_exact,
)
from .exact_human_approval import (
    _ClaimedExactHumanApproval,
    audit_exact_human_approval_succeeded_terminal_record_read_only,
)
from .exact_human_approval_windows import (
    ExactHumanApprovalContext,
    ExactHumanApprovalOperation,
)
from .exact_human_approval_workflow import _execute_exact_human_approved_write
from .exact_operation_manifest import (
    ExactOperationManifestError,
    exact_operation_completion_authentication_payload,
    load_exact_operation_final_receipt_read_only,
)


PLAN_SCHEMA = "wom-kit/objet-capture-batch-exact-plan/v0.1"
RESULT_SCHEMA = "wom-kit/objet-capture-batch-exact-result/v0.1"
_SHA256_RE = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")

_TERMINAL_STATES = frozenset(
    {
        "captured",
        "already_present",
        "partial",
        "blocked",
        "evidence_incomplete",
        "outcome_unverified",
    }
)


class ObjetCaptureBatchExactError(RuntimeError):
    """A fixed-code refusal that never retains request values or paths."""

    _CODES = {
        "objet_capture_batch_archive_invalid",
        "objet_capture_batch_plan_blocked",
        "objet_capture_batch_plan_digest_mismatch",
        "objet_capture_batch_reviewer_invalid",
        "objet_capture_batch_intake_execution_required",
        "objet_capture_batch_intake_chain_invalid",
        "objet_capture_batch_state_drifted",
        "objet_capture_batch_write_failed",
        "exact_human_approval_cancelled",
    }

    def __init__(self, code: str) -> None:
        self.code = (
            code if code in self._CODES else "objet_capture_batch_write_failed"
        )
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"ObjetCaptureBatchExactError({self.code!r})"


def _fail(code: str) -> ObjetCaptureBatchExactError:
    return ObjetCaptureBatchExactError(code)


@dataclass(frozen=True)
class ObjetCaptureBatchProgress:
    """Content-free progress event suitable for a CLI heartbeat reporter."""

    stage: str
    event: str
    current: int
    total: int

    def public_document(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "event": self.event,
            "current": self.current,
            "total": self.total,
            "private_values_echoed": False,
            "paths_echoed": False,
        }


ProgressHook = Callable[[ObjetCaptureBatchProgress], None]


def _emit(
    hook: ProgressHook | None,
    *,
    stage: str,
    event: str,
    current: int,
    total: int,
) -> None:
    if hook is not None:
        hook(
            ObjetCaptureBatchProgress(
                stage=stage,
                event=event,
                current=max(int(current), 0),
                total=max(int(total), 0),
            )
        )


@dataclass(frozen=True, repr=False)
class ObjetCaptureBatchExactPlan:
    archive_root: Path = field(repr=False)
    request_path: Path = field(repr=False)
    archive_id: str
    batch_plan_sha256: str | None
    request_sha256: str | None
    selection_sha256: str | None
    selection_relative_path: str | None = field(repr=False)
    selection_document: dict[str, Any] | None = field(repr=False)
    project_intake_receipt: str | None = field(repr=False)
    requested_item_ids: tuple[str, ...] = field(repr=False)
    derived_text_requested_item_ids: tuple[str, ...] = field(repr=False)
    native_preview: dict[str, Any] | None = field(repr=False)
    native_binding: operation_approval_binding.ExactOperationApprovalBinding | None = field(
        repr=False
    )
    public_plan: dict[str, Any] = field(repr=False)
    state: str
    blockers: tuple[str, ...]
    intake_execution_sha256: str | None = None
    intake_manifest_sha256: str | None = None
    intake_final_receipt_sha256: str | None = None
    intake_chain_binding_sha256: str | None = None
    claim_key_provider: Any | None = field(default=None, repr=False, compare=False)

    @property
    def approveable(self) -> bool:
        return (
            self.state == "ready"
            and not self.blockers
            and self.batch_plan_sha256 is not None
            and self.selection_document is not None
            and self.selection_relative_path is not None
            and self.native_preview is not None
            and self.native_binding is not None
            and self.intake_execution_sha256 is not None
            and self.intake_manifest_sha256 is not None
            and self.intake_final_receipt_sha256 is not None
            and self.intake_chain_binding_sha256 is not None
        )

    def public_document(self) -> dict[str, Any]:
        return copy.deepcopy(self.public_plan)


def _request_item_ids(private: dict[str, Any]) -> tuple[str, ...] | None:
    request = private.get("request")
    selection = private.get("selection")
    if not isinstance(request, dict) or not isinstance(selection, dict):
        return None
    request_items = request.get("items")
    selection_items = selection.get("items")
    if (
        not isinstance(request_items, list)
        or not request_items
        or not isinstance(selection_items, list)
        or len(request_items) != len(selection_items)
    ):
        return None
    requested: list[str] = []
    selected: list[str] = []
    for request_item, selection_item in zip(request_items, selection_items):
        if not isinstance(request_item, dict) or not isinstance(selection_item, dict):
            return None
        raw_requested = request_item.get("item_id")
        raw_selected = selection_item.get("item_id")
        if not isinstance(raw_requested, str) or not isinstance(raw_selected, str):
            return None
        requested.append(raw_requested.strip())
        selected.append(raw_selected)
    if requested != selected or len(set(requested)) != len(requested):
        return None
    return tuple(requested)


def _blocked_public_plan(
    base: dict[str, Any],
    *,
    blockers: list[str],
) -> dict[str, Any]:
    normalized = archive_services.unique_preserve_order(
        str(code) for code in blockers if isinstance(code, str) and code
    )
    if not normalized:
        normalized = ["objet_capture_batch_plan_blocked"]
    summary = base.get("summary") if isinstance(base.get("summary"), dict) else {}
    items = base.get("items") if isinstance(base.get("items"), list) else []
    return {
        "schema_version": PLAN_SCHEMA,
        "ok": False,
        "state": "blocked",
        "lifecycle_action": "objet_capture_batch_exact_plan",
        "plan_sha256": None,
        "exact_approval_plan_sha256": None,
        "target_binding_sha256": None,
        "summary": {
            "item_count": int(summary.get("item_count") or len(items)),
            "ready_item_count": 0,
            "blocked_item_count": int(summary.get("item_count") or len(items)),
            "convergence_model": "fresh_exact_dry_run_then_reapproval",
            "all_or_nothing_claimed": False,
            "same_claim_resume_supported": False,
            "automatic_retry_allowed": False,
        },
        "items": copy.deepcopy(items),
        "blockers": normalized,
        "warnings": [],
        "writes_performed": False,
        "provider_calls_performed": False,
        "credential_material_used_for_local_authentication": True,
        "credential_values_echoed": False,
        "private_values_echoed": False,
        "paths_echoed": False,
    }


def _plan_from_exact_preview(
    base: dict[str, Any],
    private: dict[str, Any],
    preview: dict[str, Any],
    binding: operation_approval_binding.ExactOperationApprovalBinding,
    requested_item_ids: tuple[str, ...],
) -> dict[str, Any]:
    preview_items = [
        item for item in preview.get("items", []) if isinstance(item, dict)
    ]
    preview_by_id = {
        str(item.get("item_id") or ""): item for item in preview_items
    }
    paired = set(private.get("derived_text_requested_item_ids") or [])
    projected: list[dict[str, Any]] = []
    for index, item_id in enumerate(requested_item_ids):
        item = preview_by_id.get(item_id)
        if item is None:
            projected.append(
                {
                    "index": index,
                    "item_id": item_id,
                    "state": "blocked",
                    "status_class": "blocked",
                    "blocker_codes": ["batch_original_projection_missing"],
                    "derived_text_requested": item_id in paired,
                }
            )
            continue
        projection = completion_workflows._batch_project_capture_item(
            item,
            derived_text_requested=item_id in paired,
        )
        projected.append(
            {
                "index": index,
                "item_id": item_id,
                "state": "ready",
                "planned_action": projection.get("planned_action"),
                "status_class": projection.get("status_class"),
                "blocker_codes": list(projection.get("blockers", [])),
                "warnings": list(projection.get("warnings", [])),
                "derived_text_requested": item_id in paired,
                **(
                    {"derived_text": projection.get("derived_text")}
                    if item_id in paired
                    else {}
                ),
            }
        )
    completion_counts = completion_workflows._batch_completion_counts(
        preview_items,
        original_requested=len(requested_item_ids),
        derived_text_requested_item_ids=list(paired),
        approve=False,
    )
    preview_summary = (
        preview.get("summary") if isinstance(preview.get("summary"), dict) else {}
    )
    base_summary = base.get("summary") if isinstance(base.get("summary"), dict) else {}
    return {
        "schema_version": PLAN_SCHEMA,
        "ok": True,
        "state": "ready_for_exact_human_approval",
        "lifecycle_action": "objet_capture_batch_exact_plan",
        "plan_sha256": private["plan_sha256"],
        "exact_approval_plan_sha256": binding.plan_sha256,
        "target_binding_sha256": binding.target_binding_sha256,
        "summary": {
            "batch_id": base_summary.get("batch_id"),
            "request_sha256": private.get("request_sha256"),
            "selection_sha256": private.get("selection_sha256"),
            "plan_sha256": private.get("plan_sha256"),
            "item_count": len(requested_item_ids),
            "ready_item_count": len(requested_item_ids),
            "blocked_item_count": 0,
            "would_capture": preview_summary.get("would_capture", 0),
            "would_repair_append": preview_summary.get("would_repair_append", 0),
            "would_re_materialize": preview_summary.get("would_re_materialize", 0),
            "would_skip": preview_summary.get("would_skip", 0),
            **completion_counts,
            "convergence_model": "fresh_exact_dry_run_then_reapproval",
            "all_or_nothing_claimed": False,
            "same_claim_resume_supported": False,
            "automatic_retry_allowed": False,
        },
        "items": projected,
        "blockers": [],
        "warnings": archive_services.unique_preserve_order(
            str(code) for code in preview.get("warnings", []) if isinstance(code, str)
        ),
        "writes_performed": False,
        "provider_calls_performed": False,
        "credential_material_used_for_local_authentication": True,
        "credential_values_echoed": False,
        "private_values_echoed": False,
        "paths_echoed": False,
    }


def _prefixed_sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _normalized_execution_sha256(value: str) -> str | None:
    text = str(value or "").strip().lower()
    if _SHA256_RE.fullmatch(text) is None:
        return None
    return "sha256:" + text.removeprefix("sha256:")


def _load_intake_completion(
    root: Path,
    execution_sha256: str,
    *,
    claim_key_provider: Any | None,
) -> tuple[str, dict[str, Any]]:
    normalized = _normalized_execution_sha256(execution_sha256)
    if normalized is None:
        raise _fail("objet_capture_batch_intake_execution_required")
    try:
        final = load_exact_operation_final_receipt_read_only(root, normalized)
    except ExactOperationManifestError:
        raise _fail("objet_capture_batch_intake_chain_invalid") from None
    if final is None:
        raise _fail("objet_capture_batch_intake_chain_invalid")
    result = final.get("result")
    authentication = (
        result.get("completion_authentication")
        if isinstance(result, dict)
        else None
    )
    evidence = result.get("operation_evidence") if isinstance(result, dict) else None
    digests = evidence.get("digests") if isinstance(evidence, dict) else None
    request_sha = (
        digests.get("prepared_capture_request_sha256")
        if isinstance(digests, dict)
        else None
    )
    if (
        not isinstance(result, dict)
        or result.get("status") != "completed"
        or result.get("mode") != "apply"
        or not isinstance(result.get("approval_binding_sha256"), str)
        or not isinstance(authentication, dict)
        or authentication.get("operation") != "source_intake_batch"
        or not isinstance(authentication.get("target_binding_sha256"), str)
        or not isinstance(authentication.get("approval_reference"), dict)
        or not isinstance(authentication.get("terminal_mac"), str)
        or not isinstance(evidence, dict)
        or evidence.get("schema") != source_intake_batch_exact.EVIDENCE_SCHEMA
        or not isinstance(request_sha, str)
        or _SHA256_RE.fullmatch(request_sha) is None
    ):
        raise _fail("objet_capture_batch_intake_chain_invalid")
    try:
        payload = exact_operation_completion_authentication_payload(result)
    except ExactOperationManifestError:
        raise _fail("objet_capture_batch_intake_chain_invalid") from None
    if not audit_exact_human_approval_succeeded_terminal_record_read_only(
        root,
        authentication["approval_reference"],
        expected_operation=ExactHumanApprovalOperation.source_intake_batch,
        expected_plan_sha256=result["manifest_sha256"],
        expected_target_binding_sha256=authentication[
            "target_binding_sha256"
        ],
        payload=payload,
        expected_mac=authentication["terminal_mac"],
        key_provider=claim_key_provider,
    ):
        raise _fail("objet_capture_batch_intake_chain_invalid")
    return normalized, final


def _validated_intake_chain(
    root: Path,
    *,
    archive_id: str,
    private: dict[str, Any],
    intake_execution_sha256: str,
    final_receipt: dict[str, Any],
) -> dict[str, str]:
    """Prove this capture request came from one completed exact intake.

    The execution digest is returned by ``source-intake-batch``.  No user is
    asked to inspect counts or paths: WOM loads that exact final receipt and
    recomputes the request/receipt/object binding from current bytes.
    """

    normalized_execution = _normalized_execution_sha256(intake_execution_sha256)
    if normalized_execution is None:
        raise _fail("objet_capture_batch_intake_execution_required")
    final = final_receipt
    result = final.get("result")
    evidence = result.get("operation_evidence") if isinstance(result, dict) else None
    counts = evidence.get("counts") if isinstance(evidence, dict) else None
    digests = evidence.get("digests") if isinstance(evidence, dict) else None
    request = private.get("request")
    selection = private.get("selection")
    request_sha = private.get("request_sha256")
    if (
        not isinstance(result, dict)
        or result.get("status") != "completed"
        or result.get("mode") != "apply"
        or not isinstance(result.get("approval_binding_sha256"), str)
        or not isinstance(evidence, dict)
        or evidence.get("schema") != source_intake_batch_exact.EVIDENCE_SCHEMA
        or not isinstance(counts, dict)
        or not isinstance(digests, dict)
        or not isinstance(request, dict)
        or not isinstance(selection, dict)
        or not isinstance(request_sha, str)
        or re.fullmatch(r"[0-9a-f]{64}", request_sha) is None
    ):
        raise _fail("objet_capture_batch_intake_chain_invalid")
    batch_id = request.get("batch_id")
    request_items = request.get("items")
    selection_items = selection.get("items")
    if (
        not isinstance(batch_id, str)
        or not isinstance(request_items, list)
        or not request_items
        or not isinstance(selection_items, list)
        or len(request_items) != len(selection_items)
    ):
        raise _fail("objet_capture_batch_intake_chain_invalid")
    item_bindings: list[dict[str, Any]] = []
    for ordinal, (request_item, selection_item) in enumerate(
        zip(request_items, selection_items)
    ):
        if not isinstance(request_item, dict) or not isinstance(selection_item, dict):
            raise _fail("objet_capture_batch_intake_chain_invalid")
        item_id = request_item.get("item_id")
        staged_path = request_item.get("staged_path")
        if item_id != selection_item.get("item_id") or not isinstance(item_id, str):
            raise _fail("objet_capture_batch_intake_chain_invalid")
        if not isinstance(staged_path, str):
            raise _fail("objet_capture_batch_intake_chain_invalid")
        receipt_ref = selection_item.get("source_intake_receipt_path")
        source_object_id = selection_item.get("approved_object_id")
        source_size = selection_item.get("expected_size_bytes")
        source_plan_sha = selection_item.get("source_intake_plan_sha256")
        if (
            not isinstance(receipt_ref, str)
            or not isinstance(source_object_id, str)
            or _SHA256_RE.fullmatch(source_object_id) is None
            or type(source_size) is not int
            or source_size < 0
            or not isinstance(source_plan_sha, str)
            or _SHA256_RE.fullmatch(source_plan_sha) is None
        ):
            raise _fail("objet_capture_batch_intake_chain_invalid")
        try:
            receipt_path = archive_services.archive_internal_path(root, receipt_ref)
            receipt_raw, receipt_reason = (
                archive_services._bounded_stable_regular_file_read(
                    receipt_path,
                    max_bytes=8 * 1024 * 1024,
                )
            )
        except (archive_services.ArchiveServiceError, OSError):
            raise _fail("objet_capture_batch_intake_chain_invalid") from None
        if receipt_raw is None or receipt_reason is not None:
            raise _fail("objet_capture_batch_intake_chain_invalid")
        item_bindings.append(
            {
                "ordinal": ordinal,
                "item_id": item_id,
                "staged_path_ref_sha256": _prefixed_sha256(
                    staged_path.encode("utf-8")
                ),
                "source_object_id": (
                    "sha256:" + source_object_id.removeprefix("sha256:")
                ),
                "source_size_bytes": source_size,
                "source_intake_plan_sha256": (
                    "sha256:" + source_plan_sha.removeprefix("sha256:")
                ),
                "receipt_ref_sha256": _prefixed_sha256(
                    receipt_ref.encode("utf-8")
                ),
                "receipt_bytes_sha256": _prefixed_sha256(receipt_raw),
            }
        )
    current_request_sha256 = "sha256:" + request_sha
    chain_binding = source_intake_batch_exact.intake_capture_chain_binding_sha256(
        archive_id=archive_id,
        batch_id=batch_id,
        capture_request_sha256=current_request_sha256,
        item_bindings=item_bindings,
    )
    expected_item_count = len(item_bindings)
    if (
        counts.get("source_item_count") != expected_item_count
        or counts.get("prepared_capture_request_count") != 1
        or result.get("item_count") != expected_item_count + 1
        or result.get("field_count") != expected_item_count + 1
        or digests.get("prepared_capture_request_sha256")
        != current_request_sha256
        or digests.get("intake_capture_chain_sha256") != chain_binding
    ):
        raise _fail("objet_capture_batch_intake_chain_invalid")
    manifest_sha = result.get("manifest_sha256")
    final_receipt_sha = final.get("receipt_sha256")
    if (
        not isinstance(manifest_sha, str)
        or _SHA256_RE.fullmatch(manifest_sha) is None
        or not isinstance(final_receipt_sha, str)
        or _SHA256_RE.fullmatch(final_receipt_sha) is None
    ):
        raise _fail("objet_capture_batch_intake_chain_invalid")
    return {
        "execution_sha256": normalized_execution,
        "manifest_sha256": "sha256:" + manifest_sha.removeprefix("sha256:"),
        "final_receipt_sha256": (
            "sha256:" + final_receipt_sha.removeprefix("sha256:")
        ),
        "chain_binding_sha256": chain_binding,
    }


def plan_objet_capture_batch(
    archive_root: Path | str,
    manifest_path: Path | str | None = None,
    *,
    intake_execution_sha256: str = "",
    progress_hook: ProgressHook | None = None,
    claim_key_provider: Any | None = None,
) -> ObjetCaptureBatchExactPlan:
    """Re-use the batch planner, then bind its selection to native approval."""

    _emit(progress_hook, stage="batch-plan", event="start", current=0, total=1)
    try:
        root = archive_services.require_existing_archive_root(archive_root)
        archive_id = archive_services.read_archive_id(root)
        normalized_intake_execution, intake_final = _load_intake_completion(
            root,
            intake_execution_sha256,
            claim_key_provider=claim_key_provider,
        )
        intake_result = intake_final.get("result")
        intake_evidence = (
            intake_result.get("operation_evidence")
            if isinstance(intake_result, dict)
            else None
        )
        intake_digests = (
            intake_evidence.get("digests")
            if isinstance(intake_evidence, dict)
            else None
        )
        prepared_sha = (
            intake_digests.get("prepared_capture_request_sha256")
            if isinstance(intake_digests, dict)
            else None
        )
        if not isinstance(prepared_sha, str) or _SHA256_RE.fullmatch(prepared_sha) is None:
            raise _fail("objet_capture_batch_intake_chain_invalid")
        prepared_relative = (
            f"{source_intake_batch_exact.CAPTURE_REQUESTS_ROOT}/"
            f"{prepared_sha.removeprefix('sha256:')}.objet-capture-request.json"
        )
        prepared_path = archive_services.archive_internal_path(
            root,
            prepared_relative,
        )
        if manifest_path is not None and str(manifest_path).strip():
            supplied = Path(manifest_path)
            if not supplied.is_absolute():
                supplied = root / supplied
            try:
                if supplied.resolve(strict=True) != prepared_path.resolve(strict=True):
                    raise _fail("objet_capture_batch_intake_chain_invalid")
            except (OSError, RuntimeError):
                raise _fail("objet_capture_batch_intake_chain_invalid") from None
        request_path = prepared_path
        base, private = completion_workflows._batch_plan_core(
            root,
            manifest_path=request_path,
        )
        planned_root = private.get("root")
        if not isinstance(planned_root, Path) or planned_root != root:
            raise _fail("objet_capture_batch_archive_invalid")
    except ObjetCaptureBatchExactError:
        raise
    except Exception:
        raise _fail("objet_capture_batch_archive_invalid") from None

    requested_item_ids = _request_item_ids(private)
    selection = private.get("selection")
    selection_relative = private.get("selection_relative")
    batch_plan_sha256 = private.get("plan_sha256")
    request_sha256 = private.get("request_sha256")
    selection_sha256 = private.get("selection_sha256")
    structural_ok = (
        requested_item_ids is not None
        and isinstance(selection, dict)
        and isinstance(selection_relative, str)
        and bool(selection_relative)
        and isinstance(batch_plan_sha256, str)
        and re.fullmatch(r"[0-9a-f]{64}", batch_plan_sha256) is not None
        and isinstance(request_sha256, str)
        and re.fullmatch(r"[0-9a-f]{64}", request_sha256) is not None
        and isinstance(selection_sha256, str)
        and re.fullmatch(r"[0-9a-f]{64}", selection_sha256) is not None
    )
    if not structural_ok:
        public = _blocked_public_plan(
            base,
            blockers=list(base.get("blockers", [])),
        )
        _emit(progress_hook, stage="batch-plan", event="blocked", current=1, total=1)
        return ObjetCaptureBatchExactPlan(
            archive_root=root,
            request_path=request_path,
            archive_id=archive_id,
            batch_plan_sha256=None,
            request_sha256=None,
            selection_sha256=None,
            selection_relative_path=None,
            selection_document=None,
            project_intake_receipt=None,
            requested_item_ids=(),
            derived_text_requested_item_ids=(),
            native_preview=None,
            native_binding=None,
            public_plan=public,
            state="blocked",
            blockers=tuple(public["blockers"]),
            claim_key_provider=claim_key_provider,
        )

    assert requested_item_ids is not None
    assert isinstance(selection, dict)
    assert isinstance(selection_relative, str)
    try:
        intake_chain = _validated_intake_chain(
            root,
            archive_id=archive_id,
            private=private,
            intake_execution_sha256=normalized_intake_execution,
            final_receipt=intake_final,
        )
        preview = archive_services._objet_capture_run(
            root,
            selection_relative,
            approve=False,
            reviewed_by=None,
            project_intake_receipt=private.get("project_receipt"),
            selection_document=copy.deepcopy(selection),
            selection_document_path=selection_relative,
            native_exact_authorized=True,
        )
        preview_items = [
            item for item in preview.get("items", []) if isinstance(item, dict)
        ]
        completion_counts = completion_workflows._batch_completion_counts(
            preview_items,
            original_requested=len(requested_item_ids),
            derived_text_requested_item_ids=list(
                private.get("derived_text_requested_item_ids") or []
            ),
            approve=False,
        )
        blockers = [
            str(code)
            for code in preview.get("blockers", [])
            if isinstance(code, str)
        ]
        blockers.extend(
            completion_workflows._batch_completion_blockers(
                completion_counts,
                approve=False,
            )
        )
        if preview.get("ok") is not True or blockers:
            raise _fail("objet_capture_batch_plan_blocked")
        binding = operation_approval_binding.objet_capture_approval_binding(
            preview,
            operation=ExactHumanApprovalOperation.objet_capture_batch,
        )
        public = _plan_from_exact_preview(
            base,
            private,
            preview,
            binding,
            requested_item_ids,
        )
        public["source_intake_completion"] = {
            "verified": True,
            "execution_sha256": intake_chain["execution_sha256"],
            "manifest_sha256": intake_chain["manifest_sha256"],
            "final_receipt_sha256": intake_chain["final_receipt_sha256"],
            "chain_binding_sha256": intake_chain["chain_binding_sha256"],
            "paths_echoed": False,
        }
    except ObjetCaptureBatchExactError as error:
        public = _blocked_public_plan(
            base,
            blockers=[
                *[
                    str(code)
                    for code in (
                        preview.get("blockers", [])
                        if isinstance(locals().get("preview"), dict)
                        else []
                    )
                    if isinstance(code, str)
                ],
                error.code,
            ],
        )
        _emit(progress_hook, stage="batch-plan", event="blocked", current=1, total=1)
        return ObjetCaptureBatchExactPlan(
            archive_root=root,
            request_path=request_path,
            archive_id=archive_id,
            batch_plan_sha256=None,
            request_sha256=request_sha256,
            selection_sha256=selection_sha256,
            selection_relative_path=None,
            selection_document=None,
            project_intake_receipt=None,
            requested_item_ids=requested_item_ids,
            derived_text_requested_item_ids=tuple(
                private.get("derived_text_requested_item_ids") or []
            ),
            native_preview=None,
            native_binding=None,
            public_plan=public,
            state="blocked",
            blockers=tuple(public["blockers"]),
            claim_key_provider=claim_key_provider,
        )
    except Exception:
        public = _blocked_public_plan(
            base,
            blockers=["objet_capture_batch_plan_blocked"],
        )
        _emit(progress_hook, stage="batch-plan", event="blocked", current=1, total=1)
        return ObjetCaptureBatchExactPlan(
            archive_root=root,
            request_path=request_path,
            archive_id=archive_id,
            batch_plan_sha256=None,
            request_sha256=request_sha256,
            selection_sha256=selection_sha256,
            selection_relative_path=None,
            selection_document=None,
            project_intake_receipt=None,
            requested_item_ids=requested_item_ids,
            derived_text_requested_item_ids=tuple(
                private.get("derived_text_requested_item_ids") or []
            ),
            native_preview=None,
            native_binding=None,
            public_plan=public,
            state="blocked",
            blockers=tuple(public["blockers"]),
            claim_key_provider=claim_key_provider,
        )

    _emit(progress_hook, stage="batch-plan", event="complete", current=1, total=1)
    return ObjetCaptureBatchExactPlan(
        archive_root=root,
        request_path=request_path,
        archive_id=archive_id,
        batch_plan_sha256=batch_plan_sha256,
        request_sha256=request_sha256,
        selection_sha256=selection_sha256,
        selection_relative_path=selection_relative,
        selection_document=copy.deepcopy(selection),
        project_intake_receipt=private.get("project_receipt"),
        requested_item_ids=requested_item_ids,
        derived_text_requested_item_ids=tuple(
            private.get("derived_text_requested_item_ids") or []
        ),
        native_preview=copy.deepcopy(preview),
        native_binding=binding,
        public_plan=public,
        state="ready",
        blockers=(),
        intake_execution_sha256=intake_chain["execution_sha256"],
        intake_manifest_sha256=intake_chain["manifest_sha256"],
        intake_final_receipt_sha256=intake_chain["final_receipt_sha256"],
        intake_chain_binding_sha256=intake_chain["chain_binding_sha256"],
        claim_key_provider=claim_key_provider,
    )


def approval_context(
    plan: ObjetCaptureBatchExactPlan,
    *,
    reviewer_claim: str,
) -> ExactHumanApprovalContext:
    if not plan.approveable or plan.native_binding is None:
        raise _fail("objet_capture_batch_plan_blocked")
    reviewer = archive_services.safe_project_intake_actor_id(reviewer_claim)
    if reviewer is None:
        raise _fail("objet_capture_batch_reviewer_invalid")
    try:
        return plan.native_binding.context(
            archive_id=plan.archive_id,
            reviewer_claim=reviewer,
        )
    except Exception:
        raise _fail("objet_capture_batch_reviewer_invalid") from None


def _same_plan(
    original: ObjetCaptureBatchExactPlan,
    fresh: ObjetCaptureBatchExactPlan,
) -> bool:
    if (
        not original.approveable
        or not fresh.approveable
        or original.native_binding is None
        or fresh.native_binding is None
    ):
        return False
    compared = (
        (original.archive_id, fresh.archive_id),
        (original.batch_plan_sha256, fresh.batch_plan_sha256),
        (original.request_sha256, fresh.request_sha256),
        (original.selection_sha256, fresh.selection_sha256),
        (
            original.intake_execution_sha256,
            fresh.intake_execution_sha256,
        ),
        (
            original.intake_manifest_sha256,
            fresh.intake_manifest_sha256,
        ),
        (
            original.intake_final_receipt_sha256,
            fresh.intake_final_receipt_sha256,
        ),
        (
            original.intake_chain_binding_sha256,
            fresh.intake_chain_binding_sha256,
        ),
        (original.native_binding.plan_sha256, fresh.native_binding.plan_sha256),
        (
            original.native_binding.target_binding_sha256,
            fresh.native_binding.target_binding_sha256,
        ),
    )
    return (
        original.requested_item_ids == fresh.requested_item_ids
        and original.derived_text_requested_item_ids
        == fresh.derived_text_requested_item_ids
        and all(
            isinstance(left, str)
            and isinstance(right, str)
            and hmac.compare_digest(left, right)
            for left, right in compared
        )
    )


def _terminal_item(
    item: dict[str, Any],
    *,
    derived_text_requested: bool,
    evidence_incomplete: bool,
) -> dict[str, Any]:
    projection = completion_workflows._batch_project_capture_item(
        item,
        derived_text_requested=derived_text_requested,
    )
    action = str(projection.get("action") or "")
    if action == "skip_already_present":
        data_state = "already_present"
    elif action in archive_services.OBJET_CAPTURE_ORIGINAL_OK_ACTIONS:
        data_state = "captured"
    else:
        data_state = "blocked"

    derived_terminal: str | None = None
    if derived_text_requested:
        derived = projection.get("derived_text")
        derived_status = (
            str(derived.get("item_status") or "")
            if isinstance(derived, dict)
            else ""
        )
        if derived_status == "written":
            derived_terminal = "captured"
        elif derived_status == "skipped":
            derived_terminal = "already_present"
        else:
            derived_terminal = "blocked"
        if data_state != "blocked" and derived_terminal == "blocked":
            data_state = "partial"
        elif (
            data_state == "already_present"
            and derived_terminal == "captured"
        ):
            data_state = "captured"

    terminal_state = "evidence_incomplete" if evidence_incomplete else data_state
    if terminal_state not in _TERMINAL_STATES:
        terminal_state = "outcome_unverified"
    return {
        **projection,
        "terminal_state": terminal_state,
        "data_terminal_state": data_state,
        **(
            {"derived_text_terminal_state": derived_terminal}
            if derived_text_requested
            else {}
        ),
    }


def _terminal_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {state: 0 for state in sorted(_TERMINAL_STATES)}
    for item in items:
        state = str(item.get("terminal_state") or "outcome_unverified")
        counts[state if state in counts else "outcome_unverified"] += 1
    return {
        "terminal_item_count": len(items),
        **{f"{state}_item_count": count for state, count in counts.items()},
    }


def _outcome_unverified_result(
    plan: ObjetCaptureBatchExactPlan,
) -> dict[str, Any]:
    items = [
        {
            "item_id": item_id,
            "terminal_state": "outcome_unverified",
            "derived_text_requested": item_id
            in set(plan.derived_text_requested_item_ids),
            "blockers": ["batch_capture_outcome_unverified"],
            "warnings": [],
        }
        for item_id in plan.requested_item_ids
    ]
    return {
        "schema_version": RESULT_SCHEMA,
        "ok": False,
        "state": "outcome_unverified",
        "lifecycle_action": "objet_capture_batch_exact_write",
        "plan_sha256": plan.batch_plan_sha256,
        "source_intake_completion": {
            "verified": True,
            "execution_sha256": plan.intake_execution_sha256,
            "chain_binding_sha256": plan.intake_chain_binding_sha256,
            "paths_echoed": False,
        },
        "summary": {
            **_terminal_counts(items),
            "convergence_model": "fresh_exact_dry_run_then_reapproval",
            "same_claim_resume_supported": False,
            "automatic_retry_allowed": False,
        },
        "items": items,
        "blockers": ["batch_capture_outcome_unverified"],
        "warnings": [],
        "next_safe_actions": list(
            completion_workflows.OBJET_CAPTURE_BATCH_OUTCOME_UNVERIFIED_NEXT_SAFE_ACTIONS
        ),
        "files_written": [],
        "writes_performed": False,
        "writes_may_have_occurred": True,
        "outcome_unverified": True,
        "automatic_retry_allowed": False,
        "same_claim_resume_supported": False,
        "exact_human_approval_reconciliation": {
            "required": True,
            "model": "fresh_current_state_plan_and_new_native_approval",
        },
        "provider_calls_performed": False,
        "credential_material_used_for_local_authentication": True,
        "credential_values_echoed": False,
        "private_values_echoed": False,
        "paths_echoed": False,
    }


def _drift_result(plan: ObjetCaptureBatchExactPlan) -> dict[str, Any]:
    items = [
        {
            "item_id": item_id,
            "terminal_state": "blocked",
            "derived_text_requested": item_id
            in set(plan.derived_text_requested_item_ids),
            "blockers": ["objet_capture_batch_state_drifted"],
            "warnings": [],
        }
        for item_id in plan.requested_item_ids
    ]
    return {
        "schema_version": RESULT_SCHEMA,
        "ok": False,
        "state": "blocked",
        "lifecycle_action": "objet_capture_batch_exact_write",
        "plan_sha256": plan.batch_plan_sha256,
        "source_intake_completion": {
            "verified": False,
            "execution_sha256": plan.intake_execution_sha256,
            "paths_echoed": False,
        },
        "summary": _terminal_counts(items),
        "items": items,
        "blockers": ["objet_capture_batch_state_drifted"],
        "warnings": [],
        "next_safe_actions": ["fresh_batch_dry_run_then_review"],
        "files_written": [],
        "writes_performed": False,
        "writes_may_have_occurred": False,
        "automatic_retry_allowed": False,
        "same_claim_resume_supported": False,
        "provider_calls_performed": False,
        "credential_material_used_for_local_authentication": True,
        "credential_values_echoed": False,
        "private_values_echoed": False,
        "paths_echoed": False,
    }


def _capture_result(
    plan: ObjetCaptureBatchExactPlan,
    capture: dict[str, Any],
) -> dict[str, Any]:
    expected_ids = list(plan.requested_item_ids)
    paired = set(plan.derived_text_requested_item_ids)
    try:
        shape_valid = completion_workflows._batch_capture_result_shape_valid(
            capture,
            expected_item_ids=expected_ids,
            paired_item_ids=paired,
            expected_archive_id=plan.archive_id,
            expected_selection_manifest_id=str(
                (plan.selection_document or {}).get("manifest_id") or ""
            ),
            expected_selection_sha256=archive_services.sha256_json_value(
                plan.selection_document or {}
            ),
        )
    except Exception:
        shape_valid = False
    if not shape_valid:
        return _outcome_unverified_result(plan)

    by_id = {
        str(item.get("item_id") or ""): item
        for item in capture.get("items", [])
        if isinstance(item, dict)
    }
    evidence_incomplete = capture.get("status_class") == "evidence_incomplete"
    items = [
        _terminal_item(
            by_id[item_id],
            derived_text_requested=item_id in paired,
            evidence_incomplete=evidence_incomplete,
        )
        for item_id in expected_ids
    ]
    counts = _terminal_counts(items)
    public_plan_summary = (
        plan.public_plan.get("summary")
        if isinstance(plan.public_plan.get("summary"), dict)
        else {}
    )
    completed = counts["captured_item_count"] + counts["already_present_item_count"]
    final_ok = capture.get("ok") is True and completed == len(expected_ids)
    state = (
        "completed"
        if final_ok
        else "evidence_incomplete"
        if evidence_incomplete
        else "partial"
        if counts["partial_item_count"] or completed
        else "blocked"
    )
    return {
        "schema_version": RESULT_SCHEMA,
        "ok": final_ok,
        "state": state,
        "lifecycle_action": "objet_capture_batch_exact_write",
        "plan_sha256": plan.batch_plan_sha256,
        "exact_approval_plan_sha256": (
            plan.native_binding.plan_sha256 if plan.native_binding else None
        ),
        "target_binding_sha256": (
            plan.native_binding.target_binding_sha256
            if plan.native_binding
            else None
        ),
        "source_intake_completion": {
            "verified": True,
            "execution_sha256": plan.intake_execution_sha256,
            "manifest_sha256": plan.intake_manifest_sha256,
            "final_receipt_sha256": plan.intake_final_receipt_sha256,
            "chain_binding_sha256": plan.intake_chain_binding_sha256,
            "paths_echoed": False,
        },
        "summary": {
            "batch_id": public_plan_summary.get("batch_id"),
            **counts,
            "capture_summary": copy.deepcopy(capture.get("summary", {})),
            "capture_receipt_path": capture.get("receipt_path"),
            "capture_status_class": capture.get("status_class"),
            "convergence_model": "fresh_exact_dry_run_then_reapproval",
            "same_claim_resume_supported": False,
            "automatic_retry_allowed": False,
        },
        "items": items,
        "blockers": archive_services.unique_preserve_order(
            str(code) for code in capture.get("blockers", []) if isinstance(code, str)
        ),
        "warnings": archive_services.unique_preserve_order(
            str(code) for code in capture.get("warnings", []) if isinstance(code, str)
        ),
        "next_safe_actions": copy.deepcopy(capture.get("next_safe_actions") or []),
        "files_written": copy.deepcopy(capture.get("files_written", [])),
        "writes_performed": bool(capture.get("files_written")),
        "writes_may_have_occurred": bool(capture.get("files_written")),
        "automatic_retry_allowed": False,
        "same_claim_resume_supported": False,
        "exact_human_approval_reconciliation": {
            "required": not final_ok,
            "model": "fresh_current_state_plan_and_new_native_approval",
        },
        "provider_calls_performed": False,
        "credential_material_used_for_local_authentication": True,
        "credential_values_echoed": False,
        "private_values_echoed": False,
        # Only archive-relative, content-addressed outputs and the durable
        # receipt ref are exposed; no staged or absolute source path is.
        "paths_echoed": bool(
            capture.get("receipt_path") or capture.get("files_written")
        ),
        "absolute_paths_echoed": False,
        "staged_paths_echoed": False,
    }


def _execute_core(
    plan: ObjetCaptureBatchExactPlan,
    claim: _ClaimedExactHumanApproval,
    context: ExactHumanApprovalContext,
    *,
    progress_hook: ProgressHook | None = None,
) -> dict[str, Any]:
    _emit(progress_hook, stage="batch-rederive", event="start", current=0, total=1)
    fresh = plan_objet_capture_batch(
        plan.archive_root,
        plan.request_path,
        intake_execution_sha256=plan.intake_execution_sha256 or "",
        progress_hook=None,
        claim_key_provider=plan.claim_key_provider,
    )
    expected_context = (
        approval_context(fresh, reviewer_claim=context.reviewer_claim)
        if fresh.approveable
        else None
    )
    if expected_context != context or not _same_plan(plan, fresh):
        _emit(progress_hook, stage="batch-rederive", event="blocked", current=1, total=1)
        return _drift_result(plan)
    _emit(progress_hook, stage="batch-rederive", event="complete", current=1, total=1)

    assert fresh.native_binding is not None
    assert fresh.selection_document is not None
    assert fresh.selection_relative_path is not None
    _emit(progress_hook, stage="batch-capture", event="start", current=0, total=1)
    try:
        capture = archive_services.objet_capture_apply(
            fresh.archive_root,
            fresh.selection_relative_path,
            reviewed_by=context.reviewer_claim,
            approval_operation=ExactHumanApprovalOperation.objet_capture_batch,
            project_intake_receipt=fresh.project_intake_receipt,
            selection_document=copy.deepcopy(fresh.selection_document),
            expected_exact_approval_plan_sha256=(
                fresh.native_binding.plan_sha256
            ),
            expected_exact_approval_target_binding_sha256=(
                fresh.native_binding.target_binding_sha256
            ),
            exact_human_approval_claim=claim,
        )
    except Exception:
        _emit(
            progress_hook,
            stage="batch-capture",
            event="outcome-unverified",
            current=1,
            total=1,
        )
        return _outcome_unverified_result(fresh)
    if not isinstance(capture, dict):
        _emit(
            progress_hook,
            stage="batch-capture",
            event="outcome-unverified",
            current=1,
            total=1,
        )
        return _outcome_unverified_result(fresh)
    result = _capture_result(fresh, capture)
    _emit(
        progress_hook,
        stage="batch-capture",
        event="complete" if result.get("ok") else "terminal",
        current=1,
        total=1,
    )
    return result


def execute_objet_capture_batch(
    plan: ObjetCaptureBatchExactPlan,
    *,
    expected_plan_sha256: str = "",
    reviewer_claim: str,
    progress_hook: ProgressHook | None = None,
) -> dict[str, Any]:
    expected = str(expected_plan_sha256 or "").strip().lower()
    normalized_expected = expected.removeprefix("sha256:")
    if expected and (
        _SHA256_RE.fullmatch(expected) is None
        or plan.batch_plan_sha256 is None
        or not hmac.compare_digest(normalized_expected, plan.batch_plan_sha256)
    ):
        raise _fail("objet_capture_batch_plan_digest_mismatch")
    if not plan.approveable:
        raise _fail("objet_capture_batch_plan_blocked")
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
    safe = ObjetCaptureBatchExactError(code).code
    # Only ``state_unknown`` can be raised after the mutation boundary has
    # been entered.  Native-dialog failures and workflow argument/contract
    # failures happen before the writer is called, so their capture effect is
    # known to be zero.
    outcome_unverified = code == "exact_human_approval_state_unknown"
    return {
        "schema_version": RESULT_SCHEMA,
        "ok": False,
        "state": "blocked",
        "lifecycle_action": "objet_capture_batch_exact_write",
        "blockers": [safe],
        "summary": {"terminal_item_count": 0},
        "items": [],
        "files_written": [],
        "writes_performed": False,
        "writes_may_have_occurred": outcome_unverified,
        "outcome_unverified": outcome_unverified,
        "safe_recovery_actions": (
            [
                "preserve_state",
                "fresh_dry_run_then_new_approval",
                "do_not_reuse_previous_approval",
            ]
            if outcome_unverified
            else []
        ),
        "next_safe_actions": (
            [
                "Preserve the current archive state; the prior capture outcome is not verified.",
                "Run a fresh dry-run for the same source-intake execution, review the current effect, then make a new native approval decision.",
                "Do not reuse the previous capture approval or automatically retry it.",
            ]
            if outcome_unverified
            else []
        ),
        "provider_calls_performed": False,
        # The exception alone does not prove whether key access completed.
        "credential_material_used_for_local_authentication": None,
        "credential_values_echoed": False,
        "private_values_echoed": False,
        "paths_echoed": False,
    }


__all__ = [
    "ObjetCaptureBatchExactError",
    "ObjetCaptureBatchExactPlan",
    "ObjetCaptureBatchProgress",
    "approval_context",
    "execute_objet_capture_batch",
    "failure_document",
    "plan_objet_capture_batch",
]
