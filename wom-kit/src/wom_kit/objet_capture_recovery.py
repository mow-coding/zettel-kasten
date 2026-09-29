"""Same-claim recovery for one immutable prepared registration selection.

The common exact-operation journal checkpoints logical batch completion. The
existing capture writer independently converges each content-addressed object
and derived record. A signed successful capture receipt plus a fresh complete
read-back is the post-state; partial bytes never masquerade as completion.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import fields
from pathlib import Path

from . import archive_services as services
from . import objet_capture_batch_exact as batch
from . import operation_approval_binding as bindings
from .exact_human_approval_windows import ExactHumanApprovalOperation
from .exact_human_approval_workflow import _resume_exact_human_approved_write_core
from .exact_operation_manifest import (
    ExactFieldEffect, ExactOperationItem, ExactOperationManifest,
    ExactOperationApprovalAuthority, apply_exact_operation,
    exact_operation_execution_sha256, hash_field_value,
    validate_exact_operation_resume_checkpoint_read_only,
)
from .operation_target_leases import TargetLeases, ExecutionCheckpointStore

ROOT = "profiles/local/objet-capture-recovery"
SCHEMA = "wom-kit/objet-capture-recovery/v1"
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_MINT = object()


class CaptureRecoveryError(services.ArchiveServiceError):
    def __init__(self, code="objet_capture_recovery_invalid"):
        self.code = code if re.fullmatch(r"[a-z][a-z0-9_]{0,95}", str(code)) else "objet_capture_recovery_invalid"
        super().__init__(self.code)


def _cause(error):
    return error.code if type(error) is CaptureRecoveryError else batch._content_free_cause_code(error)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def _digest(value):
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _mac_payload(value):
    # Digest framing permits large selections without broadening claim-key use.
    return (SCHEMA + "\0" + _digest(value)).encode("ascii")


def _path(root, execution, suffix="control"):
    if type(execution) is not str or not _DIGEST.fullmatch(execution):
        raise CaptureRecoveryError()
    relative = ROOT + "/" + execution[7:] + "." + suffix + ".json"
    from .operator_feedback_body import _require_effective_gitignore
    _require_effective_gitignore(root, relative)
    return services.archive_internal_path(root, relative)


def _read(root, execution, suffix="control"):
    path = _path(root, execution, suffix)
    try:
        info = path.lstat()
        import stat
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or getattr(info, "st_file_attributes", 0) & 0x400 or info.st_size > 64 * 1024 * 1024):
            raise ValueError()
        def unique(pairs):
            out = {}
            for key, value in pairs:
                if key in out:
                    raise ValueError()
                out[key] = value
            return out
        value = json.loads(path.read_bytes(), object_pairs_hook=unique)
        if set(value) != {"document", "mac"} or not isinstance(value["document"], dict):
            raise ValueError()
        return value
    except Exception:
        raise CaptureRecoveryError("objet_capture_recovery_evidence_unreadable") from None


def _save(root, execution, document, claim, suffix="control"):
    from .project_update_transaction import _require_directory_durable
    path = _path(root, execution, suffix)
    value = {"document": document, "mac": claim.approval_integrity_mac(_mac_payload(document))}
    path.parent.mkdir(parents=True, exist_ok=True)
    path = _path(root, execution, suffix)
    if path.exists():
        if _read(root, execution, suffix) != value:
            raise CaptureRecoveryError("objet_capture_recovery_evidence_changed")
        return
    # Create-only: another execution cannot replace this original authority.
    raw = _canonical(value) + b"\n"
    services._write_bytes_create_if_absent(path, raw)
    _require_directory_durable(path.parent)


def _authenticated(value, claim):
    try:
        if claim.approval_integrity_mac_matches(_mac_payload(value["document"]), value["mac"]) is not True:
            raise ValueError()
        return value["document"]
    except Exception:
        raise CaptureRecoveryError("objet_capture_recovery_authentication_failed") from None


def _operation_ref():
    from .operation_cancellation import ACTIVE
    active = ACTIVE.get()
    return getattr(active[0], "operation_ref", None) if active else None


def _plan_document(plan):
    result = {}
    for field in fields(plan):
        if field.name in {"archive_root", "claim_key_provider", "native_binding"}:
            continue
        value = getattr(plan, field.name)
        if field.name == "request_path":
            value = value.relative_to(plan.archive_root).as_posix()
        elif isinstance(value, tuple):
            value = list(value)
        result[field.name] = copy.deepcopy(value)
    return result


def _load_plan(root, document, key_provider):
    try:
        value = copy.deepcopy(document["plan"])
        value["request_path"] = services.archive_internal_path(root, value["request_path"])
        for name in ("requested_item_ids", "derived_text_requested_item_ids", "blockers"):
            value[name] = tuple(value[name])
        value["native_binding"] = bindings.objet_capture_approval_binding(
            value["native_preview"], operation=ExactHumanApprovalOperation.objet_capture_batch)
        value["archive_root"] = root
        value["claim_key_provider"] = key_provider
        plan = batch.ObjetCaptureBatchExactPlan(**value)
        if not plan.approveable:
            raise ValueError()
        return plan
    except Exception:
        raise CaptureRecoveryError() from None


def _source(plan):
    return _canonical({"selection": plan.selection_document, "request_sha256": plan.request_sha256,
                       "intake_chain_binding_sha256": plan.intake_chain_binding_sha256})


def _post(plan):
    return ("complete:" + hashlib.sha256(_source(plan)).hexdigest()).encode("ascii")


def _manifest(plan, context):
    identity = _digest({"archive": context.archive_identity_sha256, "selection": plan.selection_sha256})
    return ExactOperationManifest.build(operation="objet_capture_batch", archive_identity_sha256=context.archive_identity_sha256,
        items=(ExactOperationItem(0, "item:capture_registration", "capture_registration", plan.selection_sha256,
            identity, (ExactFieldEffect("completed_registration", hash_field_value(None), hash_field_value(_post(plan)),
                                         hash_field_value(_source(plan))),)),))


def _grant_current(root, claim, context):
    from .exact_human_approval_windows import PERMISSION_INTERACTIVE_INTENT_MECHANISM
    if claim.public_summary()["approval_mechanism"] != PERMISSION_INTERACTIVE_INTENT_MECHANISM:
        return
    from .exact_human_approval_workflow import _resolved_session_permission, _UNSET_SESSION_PERMISSION
    grant, reason = _resolved_session_permission(root, _UNSET_SESSION_PERMISSION, context)
    original = claim._assert_current_started().get("session_presenter") or {}
    if (grant is None or original.get("work_session_ref") != grant.work_session_ref
            or original.get("presenter_sha256") != grant.presenter_sha256):
        raise CaptureRecoveryError(reason or "objet_capture_recovery_current_grant_required")


_CONVERGENCE = {
    "capture": {"capture", "repair_append", "skip_already_present"},
    "repair_append": {"repair_append", "skip_already_present"},
    "re_materialize": {"re_materialize", "skip_already_present"},
    "skip_already_present": {"skip_already_present"},
}
_CHANGING = {"planned_action", "action", "stored_sha256_verified", "manifest_record_appended", "status_class"}
_DERIVED_CHANGING = _CHANGING | {"item_status", "planned_writes"}


def _convergent(original, current):
    if (not isinstance(current, dict) or current.get("ok") is not True
            or current.get("warnings") != original.get("warnings")
            or current.get("selection_manifest_sha256") != original.get("selection_manifest_sha256")
            or current.get("project_intake_context") != original.get("project_intake_context")
            or current.get("archive_id") != original.get("archive_id")):
        raise CaptureRecoveryError("objet_capture_recovery_scope_drifted")
    before, after = original.get("items"), current.get("items")
    if not isinstance(after, list) or len(before) != len(after):
        raise CaptureRecoveryError("objet_capture_recovery_scope_drifted")
    for old, new in zip(before, after):
        for left, right, mutable in ((old, new, _CHANGING | {"derived_text"}),
                                    (old.get("derived_text"), new.get("derived_text"), _DERIVED_CHANGING)):
            if left is None and right is None:
                continue
            if not isinstance(left, dict) or not isinstance(right, dict):
                raise CaptureRecoveryError("objet_capture_recovery_scope_drifted")
            if ({k: v for k, v in left.items() if k not in mutable} !=
                    {k: v for k, v in right.items() if k not in mutable}
                    or right.get("planned_action") not in _CONVERGENCE.get(left.get("planned_action"), set())):
                raise CaptureRecoveryError("objet_capture_recovery_scope_drifted")


def _fresh(plan):
    fresh = batch.plan_objet_capture_batch(plan.archive_root, plan.request_path,
        intake_execution_sha256=plan.intake_execution_sha256, claim_key_provider=plan.claim_key_provider)
    stable = ("archive_id", "request_sha256", "selection_sha256", "selection_relative_path", "selection_document",
              "project_intake_receipt", "requested_item_ids", "derived_text_requested_item_ids", "intake_execution_sha256",
              "intake_manifest_sha256", "intake_final_receipt_sha256", "intake_chain_binding_sha256")
    if not fresh.approveable or any(getattr(plan, key) != getattr(fresh, key) for key in stable):
        raise CaptureRecoveryError("objet_capture_recovery_scope_drifted")
    _convergent(plan.native_preview, fresh.native_preview)
    return fresh


class CaptureRecoveryAuthority:
    """A scoped capability minted only inside an authenticated exact execution."""

    def __init__(self, plan, context, claim, execution, *, _mint=None):
        if _mint is not _MINT:
            raise CaptureRecoveryError()
        self.plan, self.context, self.claim, self.execution = plan, context, claim, execution

    def binding_for(self, root, *, selection_path, selection_document, preview, claim, reviewed_by):
        plan = self.plan
        if (claim is not self.claim or Path(root).resolve() != plan.archive_root.resolve()
                or selection_path != plan.selection_relative_path or selection_document != plan.selection_document
                or reviewed_by != self.context.reviewer_claim):
            raise CaptureRecoveryError("objet_capture_recovery_scope_drifted")
        claim.assert_ready_for_context(self.context)
        _grant_current(root, claim, self.context)
        control = _authenticated(_read(root, self.execution), claim)
        if control["plan"] != _plan_document(plan) or control["approval_id"] != claim.approval_id:
            raise CaptureRecoveryError("objet_capture_recovery_scope_drifted")
        _fresh(plan)
        _convergent(plan.native_preview, preview)
        return plan.native_binding


class _Payloads:
    def __init__(self, plan):
        self.plan = plan

    def field_value(self, *, state, **_kwargs):
        return {"pre": None, "post": _post(self.plan), "source": _source(self.plan)}[state]


class _Verifier:
    def __init__(self, plan, manifest, execution, claim):
        self.plan, self.manifest, self.execution, self.claim = plan, manifest, execution, claim

    def target_identity_sha256(self, **_kwargs):
        return self.manifest.items[0].target_identity_sha256

    def read_field(self, **_kwargs):
        fresh = _fresh(self.plan)
        if not _path(self.plan.archive_root, self.execution, "result").exists():
            return None
        result = _authenticated(_read(self.plan.archive_root, self.execution, "result"), self.claim)
        if (result.get("ok") is not True or result.get("selection_manifest_sha256") !=
                self.plan.native_preview["selection_manifest_sha256"]):
            raise CaptureRecoveryError("objet_capture_recovery_result_invalid")
        for item in fresh.native_preview["items"]:
            if item.get("planned_action") != "skip_already_present":
                raise CaptureRecoveryError("objet_capture_recovery_completed_state_drifted")
            derived = item.get("derived_text")
            if derived is not None and derived.get("planned_action") != "skip_already_present":
                raise CaptureRecoveryError("objet_capture_recovery_completed_state_drifted")
        # The historical local receipt remains immutable and keeps its meaning.
        receipt = services.archive_internal_path(self.plan.archive_root, result["receipt_path"])
        raw = receipt.read_bytes()
        if "sha256:" + hashlib.sha256(raw).hexdigest() != result["recovery_receipt_sha256"]:
            raise CaptureRecoveryError("objet_capture_recovery_result_invalid")
        return _post(self.plan)


class _Writer:
    def __init__(self, plan, context, claim, execution, progress_hook):
        self.plan, self.context, self.claim, self.execution, self.progress_hook = plan, context, claim, execution, progress_hook
        self.capture = None

    def write_field(self, *, heartbeat, **_kwargs):
        plan = self.plan
        heartbeat()
        _grant_current(plan.archive_root, self.claim, self.context)
        batch._emit(self.progress_hook, stage="batch-capture", event="start", current=0, total=1)
        self.capture = services.objet_capture_apply(plan.archive_root, plan.selection_relative_path,
            reviewed_by=self.context.reviewer_claim, approval_operation=ExactHumanApprovalOperation.objet_capture_batch,
            project_intake_receipt=plan.project_intake_receipt, selection_document=copy.deepcopy(plan.selection_document),
            expected_exact_approval_plan_sha256=plan.native_binding.plan_sha256,
            expected_exact_approval_target_binding_sha256=plan.native_binding.target_binding_sha256,
            exact_human_approval_claim=self.claim,
            recovery_authority=CaptureRecoveryAuthority(plan, self.context, self.claim, self.execution, _mint=_MINT))
        if not isinstance(self.capture, dict) or batch._capture_result(plan, self.capture).get("ok") is not True:
            codes = (self.capture or {}).get("blockers", []) if isinstance(self.capture, dict) else []
            raise CaptureRecoveryError(codes[0] if codes else "objet_capture_recovery_registration_incomplete")
        receipt = services.archive_internal_path(plan.archive_root, self.capture["receipt_path"])
        result = {**self.capture, "recovery_receipt_sha256": "sha256:" + hashlib.sha256(receipt.read_bytes()).hexdigest()}
        _save(plan.archive_root, self.execution, result, self.claim, "result")


def run_registration(plan, claim, context, *, resume=False, progress_hook=None, control=None):
    authority = ExactOperationApprovalAuthority.from_reference(claim.assert_ready_for_context(context))
    manifest = _manifest(plan, context)
    execution = exact_operation_execution_sha256(manifest, approval_authority=authority)
    root = plan.archive_root
    with TargetLeases(root, [("execution", execution)]) as leases:
        store = ExecutionCheckpointStore(root, execution_sha256=execution, lease=leases.leases[("execution", execution)])
        if resume:
            control = _authenticated(_read(root, execution), claim)
        else:
            control = {"schema": SCHEMA, "plan": _plan_document(plan), "approval_id": claim.approval_id,
                       "execution_sha256": execution, "reviewer_claim": context.reviewer_claim,
                       "origin_operation_ref": _operation_ref()}
            _save(root, execution, control, claim)
        writer = _Writer(plan, context, claim, execution, progress_hook)
        try:
            core = apply_exact_operation(manifest, payloads=_Payloads(plan), writer=writer,
                verifier=_Verifier(plan, manifest, execution, claim), checkpoint_store=store,
                approval_authority=authority, resume=resume,
                completion_authenticator=lambda payload: {"approval_reference": claim.public_reference(),
                                                           "terminal_mac": claim.exact_terminal_record_mac(payload)})
            capture = _authenticated(_read(root, execution, "result"), claim)
            result = batch._capture_result(plan, capture)
            result["registration_final_receipt_sha256"] = core["final_receipt_sha256"]
        except Exception as error:
            result = (batch._capture_result(plan, writer.capture) if isinstance(writer.capture, dict)
                      else batch._outcome_unverified_result(plan, error=error))
            result["ok"] = False
            result["cause_code"] = _cause(error)
            result["cause_stage"] = "domain_writer"
            if result.get("state") == "completed":
                result["state"] = "evidence_incomplete"
            if not result.get("blockers"):
                result["blockers"] = [result["cause_code"] or "objet_capture_recovery_registration_incomplete"]
        checkpoint_present = store.resume_checkpoint_present(execution)
        result["execution_sha256"] = execution
        result["registration_completion_reused"] = bool(resume and writer.capture is None and result["ok"])
        if result["registration_completion_reused"]:
            # The referenced capture receipt describes the original attempt;
            # this attempt only reconciled exact/claim completion evidence.
            result["writes_performed"] = False
            result["files_written"] = []
        result["same_claim_resume_supported"] = checkpoint_present and not result["ok"]
        result["summary"]["same_claim_resume_supported"] = result["same_claim_resume_supported"]
        result["summary"]["convergence_model"] = "authenticated_original_selection_resume"
        result["recovery"] = {"approval_id": claim.approval_id, "execution_sha256": execution,
            "source_intake_execution_sha256": plan.intake_execution_sha256,
            "same_claim_resume_supported": result["same_claim_resume_supported"], "resumed": resume,
            "origin_operation_ref": control["origin_operation_ref"], "current_operation_ref": _operation_ref(),
            "automatic_retry_allowed": False}
        if not result["ok"] and checkpoint_present:
            result["next_safe_actions"] = ["preserve_prepared_request_and_staged_sources", "resolve_reported_cause_then_resume_original_capture_execution"]
            result["exact_human_approval_reconciliation"] = {"required": True, "model": "authenticated_original_selection_resume"}
        batch._emit(progress_hook, stage="batch-capture", event="complete" if result["ok"] else "terminal", current=1, total=1)
        return result


def resume_objet_capture_batch(archive_root, *, reviewer_claim, approval_id, execution_sha256,
                              progress_hook=None, key_provider=None):
    root = services.require_existing_archive_root(archive_root)
    untrusted = _read(root, execution_sha256)
    plan = _load_plan(root, untrusted["document"], key_provider)
    context = batch.approval_context(plan, reviewer_claim=reviewer_claim)
    manifest = _manifest(plan, context)

    def validate_guard(claim):
        control = _authenticated(untrusted, claim)
        if (control.get("schema") != SCHEMA or control.get("approval_id") != approval_id
                or control.get("execution_sha256") != execution_sha256 or control.get("reviewer_claim") != reviewer_claim):
            raise CaptureRecoveryError()
        _grant_current(root, claim, context)
        _fresh(plan)
        authority = ExactOperationApprovalAuthority.from_reference(claim.assert_ready_for_context(context))
        return validate_exact_operation_resume_checkpoint_read_only(root, manifest, execution_sha256=execution_sha256,
                                                                    approval_authority=authority)

    refusal = {}
    def guard(claim):
        try:
            return validate_guard(claim)
        except Exception as error:
            refusal["cause_code"] = _cause(error)
            raise
    try:
        return _resume_exact_human_approved_write_core(root, context, approval_id, guard,
            lambda claim: run_registration(plan, claim, context, resume=True, progress_hook=progress_hook),
            key_provider=key_provider)
    except Exception as error:
        if refusal.get("cause_code") is not None:
            error.cause_code = refusal["cause_code"]
            error.cause_stage = "domain_writer"
        raise
