"""One exact human approval for the three-step objet intake chain.

v0.4.21 LR-01e (letter 160 ⑦).  The client's intake of one staged original
runs ``source-intake-record`` → ``objet-capture-selection --exact-existing-intake``
→ ``objet-capture --exact-local`` and paid three native dialogs per objet.
This module plans the three steps as one chain from the same inputs, opens
one dialog and executes the steps in order under one authenticated claim.

No new approval system is introduced.  The chain is a heterogeneous batch
under the LR-01b/c batch authority: the chain binding covers each step's own
single-operation binding, and every step proves that its fresh binding is an
approved chain item and re-asserts the chain claim against the chain context
before it writes.  The record and selection steps are exact operations
(manifest, checkpoints, independent verification) whose final receipts bind
the chain claim's reference; the capture step is the native capture writer
with the per-step authority.

Planning before the earlier steps have written anything is possible because
every step is deterministic: the record's receipt bytes are known at plan
time, the selection is planned from those projected bytes, and the capture
is previewed from the projected selection document.  Execution re-plans each
step from disk after the previous step wrote its bytes and requires the same
digests.  A failure after an earlier write is reported as ``partial`` with
each step's state and the written paths; nothing is rolled back, because the
written intake record and selection are valid standalone artifacts that the
single-step commands can finish.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import (
    archive_services,
    objet_capture_selection_exact,
    operation_approval_binding,
    source_intake_record_exact,
)
from .exact_human_approval import ExactHumanApprovalError, _ClaimedExactHumanApproval
from .exact_human_approval_windows import (
    ExactHumanApprovalContext,
    ExactHumanApprovalOperation,
    ExactHumanApprovalWindowsError,
)
from .exact_human_approval_workflow import (
    ExactHumanApprovalWorkflowError,
    _execute_exact_human_approved_write,
)
from .exact_operation_manifest import ExactOperationManifestError, ExactOperationProgress
from .paths import ArchivePathError, normalize_archive_relative_path


PLAN_SCHEMA = "wom-kit/source-intake-chain-exact-plan/v0.1"
RESULT_SCHEMA = "wom-kit/source-intake-chain-exact-result/v0.1"
RECEIPT_SCHEMA = "wom-kit/source-intake-chain-receipt/v0.1"
CHAIN_RECEIPTS_DIR = "receipts/source-intake-chains"
CHAIN_ID_PREFIX = "source-intake-chain:"
STEP_NAMES = ("source_intake_record", "objet_capture_selection", "objet_capture")

_SHA256_RE = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")


class SourceIntakeChainExactError(RuntimeError):
    """A fixed-code refusal that never retains source content or paths."""

    _CODES = {
        "source_intake_chain_archive_invalid",
        "source_intake_chain_request_invalid",
        "source_intake_chain_approval_required",
        "source_intake_chain_plan_blocked",
        "source_intake_chain_plan_digest_mismatch",
        "source_intake_chain_state_drifted",
        "source_intake_chain_write_failed",
        "exact_human_approval_cancelled",
    }

    def __init__(self, code: str) -> None:
        self.code = code if code in self._CODES else "source_intake_chain_write_failed"
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"SourceIntakeChainExactError({self.code!r})"


def _fail(code: str) -> SourceIntakeChainExactError:
    return SourceIntakeChainExactError(code)


def _sha_json(value: Any) -> str:
    return "sha256:" + archive_services.sha256_json_hex(value)


def chain_receipt_relative_path(chain_id: str) -> str:
    digest = chain_id.removeprefix(CHAIN_ID_PREFIX)
    return f"{CHAIN_RECEIPTS_DIR}/{digest[:24]}.source-intake-chain.json"


def _record_item_identity(plan: source_intake_record_exact.SourceIntakeRecordExactPlan) -> str:
    return archive_services._exact_batch_item_identity(
        "source_intake_record",
        receipt_path=plan.receipt_relative_path,
        source_intake_plan_sha256=plan.source_intake_plan_sha256,
    )


def _selection_item_identity(
    plan: objet_capture_selection_exact.ExistingIntakeCaptureSelectionPlan,
) -> str:
    return archive_services._exact_batch_item_identity(
        "objet_capture_selection",
        selection_path=plan.selection_relative_path,
        staged_path=plan.staged_path,
        source_intake_receipt=plan.source_intake_receipt,
    )


@dataclass(frozen=True)
class _ChainStep:
    step: str
    state: str
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    plan_sha256: str | None
    target_binding_sha256: str | None
    item_identity_sha256: str | None
    output_path: str | None

    def public_document(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "state": self.state,
            "write_status": "would_write" if self.state == "ready" else "blocked",
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "approval_plan_sha256": self.plan_sha256,
            "approval_target_binding_sha256": self.target_binding_sha256,
            "approval_item_identity_sha256": self.item_identity_sha256,
            "output_path": self.output_path,
        }


@dataclass(frozen=True)
class SourceIntakeChainExactPlan:
    archive_root: Path = field(repr=False)
    archive_id: str
    input_plan_path: Path = field(repr=False)
    staged_path: str
    item_id: str
    manifest_id: str | None
    project_intake_receipt: str | None
    record: source_intake_record_exact.SourceIntakeRecordExactPlan | None = field(repr=False)
    selection: objet_capture_selection_exact.ExistingIntakeCaptureSelectionPlan | None = field(
        repr=False
    )
    capture_preview: dict[str, Any] | None = field(repr=False)
    steps: tuple[_ChainStep, ...]
    chain_id: str | None
    receipt_relative_path: str | None
    source_intake_plan_sha256: str | None
    staged_bytes_sha256: str | None
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    state: str

    @property
    def approveable(self) -> bool:
        return (
            self.state == "ready"
            and not self.blockers
            and len(self.steps) == 3
            and all(step.state == "ready" for step in self.steps)
            and self.record is not None
            and self.selection is not None
            and self.capture_preview is not None
        )

    def public_document(self) -> dict[str, Any]:
        document = {
            "schema_version": PLAN_SCHEMA,
            "ok": self.approveable,
            "dry_run": True,
            "state": "ready_for_exact_human_approval" if self.approveable else self.state,
            "lifecycle_action": "source_intake_chain_plan",
            "write_status": "would_write" if self.approveable else "blocked",
            "chain_id": self.chain_id,
            "receipt_path": self.receipt_relative_path,
            "source_intake_plan_sha256": self.source_intake_plan_sha256,
            "staged_bytes_sha256": self.staged_bytes_sha256,
            "steps": [step.public_document() for step in self.steps],
            "step_count": len(self.steps),
            "approval_count": 1 if self.approveable else 0,
            "single_step_approval_count": 3,
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "writes_performed": False,
            "provider_calls_performed": False,
            "credential_values_read": False,
            "private_values_echoed": False,
            "paths_echoed": True,
        }
        if self.approveable:
            try:
                binding = source_intake_chain_approval_binding(self)
            except operation_approval_binding.OperationApprovalBindingError:
                document["ok"] = False
                document["state"] = "blocked"
                document["write_status"] = "blocked"
                document["blockers"] = ["source_intake_chain_plan_blocked"]
                return document
            document["plan_sha256"] = binding.plan_sha256
            document["target_binding_sha256"] = binding.target_binding_sha256
        else:
            document["plan_sha256"] = None
            document["target_binding_sha256"] = None
        return document


def source_intake_chain_approval_binding(
    plan: SourceIntakeChainExactPlan,
) -> operation_approval_binding.ExactOperationApprovalBinding:
    basis = {
        "ok": True,
        "dry_run": True,
        "lifecycle_action": "source_intake_chain_plan",
        "write_status": "would_write",
        "chain_id": plan.chain_id,
        "receipt_path": plan.receipt_relative_path,
        "source_intake_plan_sha256": plan.source_intake_plan_sha256,
        "staged_bytes_sha256": plan.staged_bytes_sha256,
        "steps": [step.public_document() for step in plan.steps],
        "blockers": [],
        "warnings": list(plan.warnings),
    }
    return operation_approval_binding.source_intake_chain_approval_binding(basis)


def _blocked_step(step: str, blocker: str, *, warnings: tuple[str, ...] = ()) -> _ChainStep:
    return _ChainStep(
        step=step,
        state="blocked",
        blockers=(blocker,),
        warnings=warnings,
        plan_sha256=None,
        target_binding_sha256=None,
        item_identity_sha256=None,
        output_path=None,
    )


def _blocked_plan(
    *,
    root: Path,
    archive_id: str,
    input_plan_path: Path,
    staged_path: str,
    item_id: str,
    manifest_id: str | None,
    project_intake_receipt: str | None,
    steps: tuple[_ChainStep, ...],
    blocker: str,
    record: source_intake_record_exact.SourceIntakeRecordExactPlan | None = None,
    selection: objet_capture_selection_exact.ExistingIntakeCaptureSelectionPlan | None = None,
) -> SourceIntakeChainExactPlan:
    return SourceIntakeChainExactPlan(
        archive_root=root,
        archive_id=archive_id,
        input_plan_path=input_plan_path,
        staged_path=staged_path,
        item_id=item_id,
        manifest_id=manifest_id,
        project_intake_receipt=project_intake_receipt,
        record=record,
        selection=selection,
        capture_preview=None,
        steps=steps,
        chain_id=None,
        receipt_relative_path=None,
        source_intake_plan_sha256=record.source_intake_plan_sha256 if record else None,
        staged_bytes_sha256=selection.staged_bytes_sha256 if selection else None,
        blockers=(blocker,),
        warnings=(),
        state="blocked",
    )


def plan_source_intake_chain(
    archive_root: Path | str,
    source_intake_plan_path: Path | str,
    *,
    staged_path: str,
    item_id: str = "item",
    manifest_id: str | None = None,
    project_intake_receipt: str | None = None,
) -> SourceIntakeChainExactPlan:
    """Plan record, selection and capture from projected bytes; write nothing."""

    try:
        root = archive_services.require_existing_archive_root(archive_root)
        archive_id = archive_services.read_archive_id(root)
    except Exception:
        raise _fail("source_intake_chain_archive_invalid") from None
    input_plan_path = Path(source_intake_plan_path)
    try:
        normalized_staged = normalize_archive_relative_path(staged_path)
    except ArchivePathError:
        raise _fail("source_intake_chain_request_invalid") from None
    if (
        type(item_id) is not str
        or not item_id
        or (manifest_id is not None and (type(manifest_id) is not str or not manifest_id))
        or (
            project_intake_receipt is not None
            and (type(project_intake_receipt) is not str or not project_intake_receipt)
        )
    ):
        raise _fail("source_intake_chain_request_invalid")

    common = dict(
        root=root,
        archive_id=archive_id,
        input_plan_path=input_plan_path,
        staged_path=normalized_staged,
        item_id=item_id,
        manifest_id=manifest_id,
        project_intake_receipt=project_intake_receipt,
    )

    # Step 1: the intake record from the reviewed source-intake plan file.
    try:
        record = source_intake_record_exact.plan_source_intake_record(root, input_plan_path)
    except source_intake_record_exact.SourceIntakeRecordExactError as error:
        return _blocked_plan(
            **common,
            steps=(_blocked_step(STEP_NAMES[0], error.code),),
            blocker="source_intake_chain_plan_blocked",
        )
    if (
        not record.approveable
        or record.manifest is None
        or record.manifest.work_session_binding is not None
        or record.receipt_relative_path is None
        or record.receipt_bytes is None
    ):
        blocker = (
            record.blockers[0]
            if record.blockers
            else "source_intake_record_plan_blocked"
        )
        return _blocked_plan(
            **common,
            record=record,
            steps=(_blocked_step(STEP_NAMES[0], blocker),),
            blocker="source_intake_chain_plan_blocked",
        )
    record_binding = operation_approval_binding.exact_operation_manifest_approval_binding(
        record.manifest,
        operation=ExactHumanApprovalOperation.source_intake_record,
        archive_id=archive_id,
        warnings=(),
    )
    record_step = _ChainStep(
        step=STEP_NAMES[0],
        state="ready",
        blockers=(),
        warnings=(),
        plan_sha256=record_binding.plan_sha256,
        target_binding_sha256=record_binding.target_binding_sha256,
        item_identity_sha256=_record_item_identity(record),
        output_path=record.receipt_relative_path,
    )

    # Step 2: the selection, validated against the projected receipt bytes.
    try:
        selection = objet_capture_selection_exact.plan_existing_intake_capture_selection(
            root,
            staged_path=normalized_staged,
            source_intake_receipt=record.receipt_relative_path,
            item_id=item_id,
            manifest_id=manifest_id,
            projected_source_intake_receipt_bytes=record.receipt_bytes,
        )
    except objet_capture_selection_exact.ExistingIntakeCaptureSelectionError as error:
        return _blocked_plan(
            **common,
            record=record,
            steps=(record_step, _blocked_step(STEP_NAMES[1], error.code)),
            blocker="source_intake_chain_plan_blocked",
        )
    if (
        not selection.approveable
        or selection.manifest is None
        or selection.selection_relative_path is None
        or selection.selection_bytes is None
    ):
        blocker = (
            selection.blockers[0]
            if selection.blockers
            else "existing_intake_capture_selection_plan_blocked"
        )
        return _blocked_plan(
            **common,
            record=record,
            selection=selection,
            steps=(
                record_step,
                _blocked_step(STEP_NAMES[1], blocker, warnings=tuple(selection.warnings)),
            ),
            blocker="source_intake_chain_plan_blocked",
        )
    selection_binding = operation_approval_binding.exact_operation_manifest_approval_binding(
        selection.manifest,
        operation=ExactHumanApprovalOperation.objet_capture_selection_record,
        archive_id=archive_id,
        warnings=selection.warnings,
    )
    selection_step = _ChainStep(
        step=STEP_NAMES[1],
        state="ready",
        blockers=(),
        warnings=tuple(selection.warnings),
        plan_sha256=selection_binding.plan_sha256,
        target_binding_sha256=selection_binding.target_binding_sha256,
        item_identity_sha256=_selection_item_identity(selection),
        output_path=selection.selection_relative_path,
    )

    # Step 3: the capture, previewed from the projected selection document.
    try:
        selection_document = json.loads(selection.selection_bytes.decode("utf-8"))
        if not isinstance(selection_document, dict):
            raise ValueError("selection document must be an object")
        preview = archive_services._objet_capture_run(
            root,
            None,
            approve=False,
            reviewed_by=None,
            project_intake_receipt=project_intake_receipt,
            selection_document=selection_document,
            selection_document_path=selection.selection_relative_path,
            native_exact_authorized=True,
            projected_source_intake_receipts={
                record.receipt_relative_path: record.receipt_bytes
            },
        )
    except (
        archive_services.ArchiveServiceError,
        OSError,
        ValueError,
        UnicodeDecodeError,
    ):
        return _blocked_plan(
            **common,
            record=record,
            selection=selection,
            steps=(record_step, selection_step, _blocked_step(STEP_NAMES[2], "objet_capture_plan_failed")),
            blocker="source_intake_chain_plan_blocked",
        )
    capture_blockers = preview.get("blockers") if isinstance(preview.get("blockers"), list) else []
    item_blockers = [
        blocker
        for item in (preview.get("items") if isinstance(preview.get("items"), list) else [])
        if isinstance(item, dict)
        for blocker in (item.get("blockers") if isinstance(item.get("blockers"), list) else [])
    ]
    capture_warnings = tuple(
        str(value)
        for value in (preview.get("warnings") if isinstance(preview.get("warnings"), list) else [])
    )
    try:
        capture_binding = operation_approval_binding.objet_capture_approval_binding(preview)
    except operation_approval_binding.OperationApprovalBindingError:
        capture_binding = None
    # The capture apply refuses without a current archive index (manifest
    # mutation authority).  The single-step preview does not check this, but
    # a chain must know before the record and selection steps have written.
    summary = preview.get("summary") if isinstance(preview.get("summary"), dict) else {}
    if (
        not capture_blockers
        and not item_blockers
        and capture_binding is not None
        and (summary.get("would_capture") or summary.get("would_repair_append"))
    ):
        try:
            manifest_snapshot = archive_services.archive_index_stable_file_snapshot(
                root,
                root / archive_services.ZETTEL_OBJET_LINK_MANIFEST_RELATIVE_PATH,
                max_bytes=archive_services.ZETTEL_OBJET_LINK_MANIFEST_MAX_BYTES,
            )
            archive_services.require_archive_manifest_index_mutation_authority(
                root,
                operation_owner_sha256=archive_services.archive_manifest_mutation_owner_sha256(
                    operation="objet_capture",
                    operation_binding_sha256=str(preview.get("selection_manifest_sha256") or ""),
                ),
                expected_pre_manifest_sha256=manifest_snapshot["file_sha256"],
                expected_post_manifest_sha256=manifest_snapshot["file_sha256"],
            )
        except Exception:
            capture_blockers = [archive_services.INDEX_REBUILD_REQUIRED]
    if preview.get("ok") is not True or capture_blockers or item_blockers or capture_binding is None:
        blocker = str((capture_blockers or item_blockers or ["objet_capture_plan_blocked"])[0])
        return _blocked_plan(
            **common,
            record=record,
            selection=selection,
            steps=(
                record_step,
                selection_step,
                _blocked_step(STEP_NAMES[2], blocker, warnings=capture_warnings),
            ),
            blocker="source_intake_chain_plan_blocked",
        )
    capture_step = _ChainStep(
        step=STEP_NAMES[2],
        state="ready",
        blockers=(),
        warnings=capture_warnings,
        plan_sha256=capture_binding.plan_sha256,
        target_binding_sha256=capture_binding.target_binding_sha256,
        item_identity_sha256=archive_services._objet_capture_item_identity(preview),
        # The capture receipt name is minted at capture time; the result
        # document carries the actual path.
        output_path=None,
    )

    steps = (record_step, selection_step, capture_step)
    chain_id = CHAIN_ID_PREFIX + hashlib.sha256(
        json.dumps(
            [[step.plan_sha256, step.target_binding_sha256] for step in steps],
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    warnings = tuple(dict.fromkeys(selection_step.warnings + capture_step.warnings))
    return SourceIntakeChainExactPlan(
        archive_root=root,
        archive_id=archive_id,
        input_plan_path=input_plan_path,
        staged_path=normalized_staged,
        item_id=item_id,
        manifest_id=manifest_id,
        project_intake_receipt=project_intake_receipt,
        record=record,
        selection=selection,
        capture_preview=copy.deepcopy(preview),
        steps=steps,
        chain_id=chain_id,
        receipt_relative_path=chain_receipt_relative_path(chain_id),
        source_intake_plan_sha256=record.source_intake_plan_sha256,
        staged_bytes_sha256=selection.staged_bytes_sha256,
        blockers=(),
        warnings=warnings,
        state="ready",
    )


def approval_context(
    plan: SourceIntakeChainExactPlan,
    *,
    reviewer_claim: str,
) -> ExactHumanApprovalContext:
    if not plan.approveable:
        raise _fail("source_intake_chain_plan_blocked")
    if archive_services.safe_project_intake_actor_id(reviewer_claim) is None:
        raise _fail("source_intake_chain_approval_required")
    try:
        return source_intake_chain_approval_binding(plan).context(
            archive_id=plan.archive_id,
            reviewer_claim=reviewer_claim,
        )
    except Exception:
        raise _fail("source_intake_chain_approval_required") from None


def _step_result_document(step: _ChainStep, result: dict[str, Any] | None, state: str) -> dict[str, Any]:
    document = {
        "step": step.step,
        "state": state,
        "output_path": step.output_path,
        "approval_plan_sha256": step.plan_sha256,
        "approval_target_binding_sha256": step.target_binding_sha256,
        "approval_item_identity_sha256": step.item_identity_sha256,
    }
    if result is not None:
        receipt_path = result.get("receipt_path")
        if document["output_path"] is None and isinstance(receipt_path, str) and receipt_path:
            document["output_path"] = receipt_path
        for key in (
            "plan_sha256",
            "final_receipt_sha256",
            "checkpoint_count",
            "selection_path",
            "receipt_path",
            "blockers",
            "reason_codes",
        ):
            if key in result:
                document[key] = copy.deepcopy(result[key])
        capture_summary = result.get("summary")
        if isinstance(capture_summary, dict):
            document["summary"] = copy.deepcopy(capture_summary)
        files_written = result.get("files_written")
        if isinstance(files_written, list):
            document["files_written"] = list(files_written)
    return document


def _write_chain_receipt(
    root: Path,
    plan: SourceIntakeChainExactPlan,
    *,
    approval: dict[str, Any],
    steps: list[dict[str, Any]],
    state: str,
) -> str | None:
    if plan.receipt_relative_path is None:
        return None
    try:
        path = archive_services.archive_internal_path(root, plan.receipt_relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        archive_services._atomic_write_json(
            path,
            {
                "schema_version": RECEIPT_SCHEMA,
                "archive_id": plan.archive_id,
                "chain_id": plan.chain_id,
                "state": state,
                "source_intake_plan_sha256": plan.source_intake_plan_sha256,
                "staged_bytes_sha256": plan.staged_bytes_sha256,
                "steps": steps,
                "exact_human_approval": approval,
            },
        )
    except (archive_services.ArchiveServiceError, OSError, TypeError, ValueError):
        return None
    return plan.receipt_relative_path


def _execute_core(
    plan: SourceIntakeChainExactPlan,
    claim: _ClaimedExactHumanApproval,
    *,
    reviewer_claim: str,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
) -> dict[str, Any]:
    root = plan.archive_root
    if not plan.approveable or plan.record is None or plan.selection is None:
        raise _fail("source_intake_chain_plan_blocked")
    # Fresh chain plan immediately before the first write; the chain claim is
    # verified against it and the approved step set is frozen.
    fresh = plan_source_intake_chain(
        root,
        plan.input_plan_path,
        staged_path=plan.staged_path,
        item_id=plan.item_id,
        manifest_id=plan.manifest_id,
        project_intake_receipt=plan.project_intake_receipt,
    )
    if not fresh.approveable or fresh.record is None or fresh.selection is None:
        raise _fail("source_intake_chain_state_drifted")
    try:
        binding = source_intake_chain_approval_binding(fresh)
        expected = source_intake_chain_approval_binding(plan)
    except operation_approval_binding.OperationApprovalBindingError:
        raise _fail("source_intake_chain_state_drifted") from None
    if (
        binding.plan_sha256 != expected.plan_sha256
        or binding.target_binding_sha256 != expected.target_binding_sha256
    ):
        raise _fail("source_intake_chain_state_drifted")
    try:
        authority = archive_services._build_exact_batch_authority(
            root,
            binding,
            reviewer_claim=reviewer_claim,
            expected_plan_sha256=expected.plan_sha256,
            expected_target_binding_sha256=expected.target_binding_sha256,
            claim=claim,
            item_results=[step.public_document() for step in fresh.steps],
        )
    except archive_services.ArchiveServiceError as error:
        code = str(getattr(error, "code", "") or error)
        raise _fail(code if code in SourceIntakeChainExactError._CODES else "source_intake_chain_approval_required") from None

    record_step, selection_step, capture_step = fresh.steps
    step_documents: list[dict[str, Any]] = []
    files_written: list[str] = []
    state = "completed"
    failure_code: str | None = None

    # Step 1: record.
    try:
        record_result = source_intake_record_exact.execute_source_intake_record_in_chain(
            fresh.record,
            claim=claim,
            chain_authority=authority.for_item(str(record_step.item_identity_sha256)),
            progress_hook=progress_hook,
        )
    except (
        source_intake_record_exact.SourceIntakeRecordExactError,
        archive_services.ArchiveServiceError,
        ExactHumanApprovalError,
        ExactOperationManifestError,
        OSError,
    ) as error:
        failure_code = str(getattr(error, "code", "") or "source_intake_record_write_failed")
        step_documents.append(_step_result_document(record_step, {"reason_codes": [failure_code]}, "failed"))
        state = "blocked"
        record_result = None
    if record_result is not None:
        step_documents.append(_step_result_document(record_step, record_result, "written"))
        if record_step.output_path:
            files_written.append(record_step.output_path)

        # Step 2: selection, re-planned from the receipt now on disk.
        try:
            selection_plan = objet_capture_selection_exact.plan_existing_intake_capture_selection(
                root,
                staged_path=fresh.staged_path,
                source_intake_receipt=str(fresh.record.receipt_relative_path),
                item_id=fresh.item_id,
                manifest_id=fresh.manifest_id,
            )
            if (
                not selection_plan.approveable
                or selection_plan.manifest is None
                or fresh.selection.manifest is None
                or selection_plan.manifest.manifest_sha256
                != fresh.selection.manifest.manifest_sha256
            ):
                raise _fail("source_intake_chain_state_drifted")
            selection_result = objet_capture_selection_exact.execute_existing_intake_capture_selection_in_chain(
                selection_plan,
                claim=claim,
                chain_authority=authority.for_item(str(selection_step.item_identity_sha256)),
                progress_hook=progress_hook,
            )
        except (
            SourceIntakeChainExactError,
            objet_capture_selection_exact.ExistingIntakeCaptureSelectionError,
            archive_services.ArchiveServiceError,
            ExactHumanApprovalError,
            ExactOperationManifestError,
            OSError,
        ) as error:
            failure_code = str(
                getattr(error, "code", "") or "existing_intake_capture_selection_write_failed"
            )
            step_documents.append(
                _step_result_document(selection_step, {"reason_codes": [failure_code]}, "failed")
            )
            state = "partial"
            selection_result = None
        if selection_result is not None:
            step_documents.append(_step_result_document(selection_step, selection_result, "written"))
            if selection_step.output_path:
                files_written.append(selection_step.output_path)

            # Step 3: capture from the selection file now on disk.
            try:
                capture_result = archive_services.objet_capture_apply(
                    root,
                    Path(str(fresh.selection.selection_relative_path)),
                    reviewed_by=reviewer_claim,
                    project_intake_receipt=fresh.project_intake_receipt,
                    exact_human_approval_claim=claim,
                    batch_authority=authority.for_item(str(capture_step.item_identity_sha256)),
                )
            except (archive_services.ArchiveServiceError, OSError) as error:
                failure_code = str(getattr(error, "code", "") or "objet_capture_write_failed")
                step_documents.append(
                    _step_result_document(capture_step, {"reason_codes": [failure_code]}, "failed")
                )
                state = "partial"
                capture_result = None
            if capture_result is not None:
                # The capture writer may publish object bytes and its
                # always-written receipt even when it reports ok:false; the
                # chain must list those durable writes either way.
                capture_ok = (
                    capture_result.get("ok") is True
                    and capture_result.get("dry_run") is not True
                )
                capture_document = _step_result_document(
                    capture_step, capture_result, "written" if capture_ok else "failed"
                )
                if not capture_ok:
                    blockers = capture_result.get("blockers")
                    item_blockers = [
                        code
                        for item in (
                            capture_result.get("items")
                            if isinstance(capture_result.get("items"), list)
                            else []
                        )
                        if isinstance(item, dict)
                        for code in (item.get("blockers") if isinstance(item.get("blockers"), list) else [])
                    ]
                    reason_codes = [
                        str(code)
                        for code in (
                            list(blockers) if isinstance(blockers, list) and blockers else item_blockers
                        )
                    ] or ["objet_capture_blocked"]
                    capture_document["reason_codes"] = reason_codes
                    failure_code = reason_codes[0]
                    state = "partial"
                step_documents.append(capture_document)
                _merge_written_paths(files_written, capture_result)

    written_steps = sum(1 for step in step_documents if step.get("state") == "written")
    warnings = list(fresh.warnings)
    receipt_path: str | None = None
    if written_steps > 0 or files_written:
        # A chain receipt is evidence of writes; when nothing was written
        # there is nothing to record and no receipt is created.
        receipt_path = _write_chain_receipt(
            root,
            fresh,
            approval=authority.receipt,
            steps=step_documents,
            state=state,
        )
        if receipt_path is not None:
            files_written.append(receipt_path)
        else:
            warnings.append("source_intake_chain_receipt_not_written")
    return {
        "schema_version": RESULT_SCHEMA,
        "ok": state == "completed",
        "dry_run": False,
        "state": state,
        "lifecycle_action": "source_intake_chain_write",
        "chain_id": fresh.chain_id,
        "receipt_path": receipt_path,
        "plan_sha256": expected.plan_sha256,
        "target_binding_sha256": expected.target_binding_sha256,
        "source_intake_plan_sha256": fresh.source_intake_plan_sha256,
        "staged_bytes_sha256": fresh.staged_bytes_sha256,
        "steps": step_documents,
        "step_count": len(fresh.steps),
        "steps_written": written_steps,
        "approval_count": 1,
        "single_step_approval_count": 3,
        "files_written": files_written,
        "receipt_written": receipt_path is not None,
        "blockers": [failure_code] if failure_code else [],
        "reason_codes": [failure_code] if failure_code else [],
        "warnings": warnings,
        "next_safe_actions": (
            []
            if state == "completed"
            else _next_safe_actions(written_steps, fresh)
        ),
        "general_intake_chain_complete": state == "completed",
        "writes_performed": bool(files_written),
        "provider_calls_performed": False,
        "credential_values_read": False,
        "private_values_echoed": False,
        "paths_echoed": True,
    }


def _merge_written_paths(files_written: list[str], result: dict[str, Any]) -> None:
    """Add a step result's receipt and written paths once each, in order."""

    receipt = result.get("receipt_path")
    candidates = [receipt] if isinstance(receipt, str) and receipt else []
    written = result.get("files_written")
    if isinstance(written, list):
        candidates.extend(item for item in written if isinstance(item, str) and item)
    for path in candidates:
        if path not in files_written:
            files_written.append(path)


def _next_safe_actions(written_steps: int, fresh: SourceIntakeChainExactPlan) -> list[str]:
    if written_steps == 0:
        return [
            "Nothing was written; review the blocker, then run source-intake-chain --dry-run again.",
        ]
    if written_steps == 1:
        return [
            "The intake record was written. Finish with objet-capture-selection "
            "--exact-existing-intake --source-intake-receipt "
            f"{fresh.record.receipt_relative_path if fresh.record else '<receipt>'} "
            "and then objet-capture --exact-local --selection <selection>.",
        ]
    return [
        "The intake record and selection were written. Finish with objet-capture "
        "--exact-local --selection "
        f"{fresh.selection.selection_relative_path if fresh.selection else '<selection>'}.",
    ]


def execute_source_intake_chain(
    plan: SourceIntakeChainExactPlan,
    *,
    expected_plan_sha256: str = "",
    reviewer_claim: str,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
    observe_target_binding: Callable[[], str] | None = None,
    target_collection: Any = None,
) -> dict[str, Any]:
    """Open one native dialog for the chain and run its three steps."""

    if not plan.approveable:
        raise _fail("source_intake_chain_plan_blocked")
    expected = str(expected_plan_sha256 or "").strip().lower()
    if expected:
        try:
            binding = source_intake_chain_approval_binding(plan)
        except operation_approval_binding.OperationApprovalBindingError:
            raise _fail("source_intake_chain_plan_blocked") from None
        if _SHA256_RE.fullmatch(expected) is None or expected != binding.plan_sha256:
            raise _fail("source_intake_chain_plan_digest_mismatch")
    context = approval_context(plan, reviewer_claim=reviewer_claim)
    return _execute_exact_human_approved_write(
        plan.archive_root,
        context,
        lambda claim: _execute_core(
            plan,
            claim,
            reviewer_claim=reviewer_claim,
            progress_hook=progress_hook,
        ),
        **(
            {
                "target_collection": target_collection,
                "observe_target_binding": observe_target_binding,
            }
            if target_collection is not None and observe_target_binding is not None
            else {}
        ),
    )


def failure_document(code: str) -> dict[str, Any]:
    safe = SourceIntakeChainExactError(code).code
    return {
        "schema_version": RESULT_SCHEMA,
        "ok": False,
        "dry_run": False,
        "state": "blocked",
        "lifecycle_action": "source_intake_chain_write",
        "steps": [],
        "step_count": 3,
        "steps_written": 0,
        "files_written": [],
        "blockers": [safe],
        "reason_codes": [safe],
        "warnings": [],
        "general_intake_chain_complete": False,
        "writes_performed": False,
        "provider_calls_performed": False,
        "credential_values_read": False,
        "private_values_echoed": False,
        "paths_echoed": False,
    }


__all__ = [
    "CHAIN_RECEIPTS_DIR",
    "PLAN_SCHEMA",
    "RESULT_SCHEMA",
    "STEP_NAMES",
    "SourceIntakeChainExactError",
    "SourceIntakeChainExactPlan",
    "approval_context",
    "chain_receipt_relative_path",
    "execute_source_intake_chain",
    "failure_document",
    "plan_source_intake_chain",
    "source_intake_chain_approval_binding",
]
