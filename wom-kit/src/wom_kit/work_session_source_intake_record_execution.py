"""Caller-held single-record execution; no legacy writer or public admission.

Only the concrete retained session workflow admits writes. Original continuation
uses retained input bytes, not a missing caller JSON file. A completed proof is
historical output authentication, never present actor/ownership authority.
"""

from __future__ import annotations

from contextlib import ExitStack
import os
import uuid

from . import archive_services
from . import exact_human_approval as approval
from . import exact_operation_manifest as exact
from . import project_update_transaction as durable
from . import source_intake_batch_exact as batch
from . import source_intake_record_exact as record
from . import work_session_bundle as controls
from . import work_session_registry as registry
from .exact_human_approval_windows import ExactHumanApprovalContext


_ERRORS = frozenset({"source_intake_record_scope_context_required", "source_intake_record_lock_required",
    "source_intake_record_plan_blocked", "source_intake_record_approval_required",
    "source_intake_record_target_collision", "source_intake_record_target_unsafe",
    "source_intake_record_state_drifted", "source_intake_record_write_failed",
    "source_intake_record_completion_evidence_required"})
_RECEIPT_ROOT = ("receipts", "sources")


class WorkSessionSourceIntakeRecordExecutionError(RuntimeError):
    def __init__(self, code="source_intake_record_write_failed"):
        self.code = code if type(code) is str and code in _ERRORS else "source_intake_record_write_failed"
        super().__init__(self.code)


def _safe_call(call, default="source_intake_record_write_failed"):
    code = default
    try:
        return call()
    except WorkSessionSourceIntakeRecordExecutionError as error:
        code = error.code
    except record.SourceIntakeRecordExactError as error:
        code = error.code if type(error.code) is str and error.code in _ERRORS else default
    except Exception:
        pass
    # A rejected OS/provider/owner observation must not leak via error chains.
    raise WorkSessionSourceIntakeRecordExecutionError(code)


def _require_source_intake_record_held_lock(plan, held):
    def check():
        if type(plan) is not record.SourceIntakeRecordExactPlan or type(held) is not exact.ExactOperationWriterLock:
            raise WorkSessionSourceIntakeRecordExecutionError("source_intake_record_lock_required")
        actual, archive_id = approval._archive_identity(plan.archive_root)
        held.verify_held()
        if not os.path.samefile(actual, held.archive_root) or plan.archive_id != archive_id:
            raise WorkSessionSourceIntakeRecordExecutionError("source_intake_record_lock_required")
    return _safe_call(check, "source_intake_record_lock_required")


def _context(plan, context, claim, held, *, succeeded):
    _require_source_intake_record_held_lock(plan, held)
    if (type(plan.manifest) is not exact.ExactOperationManifest or not plan.approveable
            or type(context) is not ExactHumanApprovalContext or type(claim) is not approval._ClaimedExactHumanApproval
            or record.approval_context(plan, reviewer_claim=context.reviewer_claim) != context):
        raise WorkSessionSourceIntakeRecordExecutionError("source_intake_record_approval_required")
    reference = (claim.assert_succeeded_for_context(context) if succeeded else claim.assert_ready_for_context(context))
    if not os.path.samefile(claim._path,
            plan.archive_root / approval.CLAIMS_RELATIVE_ROOT / (claim.approval_id + ".json")):
        raise WorkSessionSourceIntakeRecordExecutionError("source_intake_record_approval_required")
    return reference, exact.ExactOperationApprovalAuthority.from_reference(reference)


def _source_intake_record_completion_evidence_view(plan, *, context, reference, execution, final):
    """Pure exact result shape. It neither checks a MAC nor admits execution."""
    def view():
        if (type(plan) is not record.SourceIntakeRecordExactPlan or type(plan.manifest) is not exact.ExactOperationManifest
                or type(context) is not ExactHumanApprovalContext
                or record.approval_context(plan, reviewer_claim=context.reviewer_claim) != context
                or type(final) is not dict or type(final.get("result")) is not dict):
            raise WorkSessionSourceIntakeRecordExecutionError("source_intake_record_completion_evidence_required")
        authority = exact.ExactOperationApprovalAuthority.from_reference(reference)
        result = final["result"]
        auth = result.get("completion_authentication")
        evidence, binding = plan.manifest.operation_evidence, plan.manifest.work_session_binding
        if (authority.context_sha256 != approval.exact_human_approval_context_sha256(context)
                or execution != exact.exact_operation_execution_sha256(plan.manifest, approval_authority=authority)
                or type(auth) is not dict or result.get("status") != "completed" or result.get("mode") != "apply"
                or result.get("manifest_sha256") != plan.manifest.manifest_sha256
                or result.get("execution_sha256") != execution or result.get("approval_binding_sha256") != authority.binding_sha256
                or result.get("operation_evidence") != (None if evidence is None else evidence.document())
                or result.get("work_session_binding_sha256") != (None if binding is None else binding.binding_sha256)
                or result.get("extension_sha256") != plan.manifest.extension_sha256
                or result.get("item_count") != len(plan.manifest.items)
                or result.get("field_count") != sum(len(item.fields) for item in plan.manifest.items)
                or auth.get("operation") != record.OPERATION
                or auth.get("target_binding_sha256") != plan.manifest.target_set_sha256
                or auth.get("approval_reference") != reference):
            raise WorkSessionSourceIntakeRecordExecutionError("source_intake_record_completion_evidence_required")
        return authority, auth, exact.exact_operation_completion_authentication_payload(result)
    return _safe_call(view, "source_intake_record_completion_evidence_required")


def _verify_source_intake_record_completion_with_claim_held(plan, *, context, claim, writer_lock):
    """Authenticate this original succeeded claim and current whole output only."""
    def verify():
        reference, authority = _context(plan, context, claim, writer_lock, succeeded=True)
        execution = exact.exact_operation_execution_sha256(plan.manifest, approval_authority=authority)
        def authenticated():
            if _context(plan, context, claim, writer_lock, succeeded=True)[0] != reference:
                raise WorkSessionSourceIntakeRecordExecutionError("source_intake_record_completion_evidence_required")
            final = exact.load_exact_operation_final_receipt_read_only(plan.archive_root, execution,
                                                                        heartbeat=writer_lock.verify_held)
            _authority, auth, payload = _source_intake_record_completion_evidence_view(plan,
                context=context, reference=reference, execution=execution, final=final)
            if not claim.exact_terminal_record_matches(reference, context.operation, context.plan_sha256,
                    context.target_binding_sha256, frozenset({"succeeded"}), None, payload, auth["terminal_mac"]):
                raise WorkSessionSourceIntakeRecordExecutionError("source_intake_record_completion_evidence_required")
            return final
        final = authenticated()
        verified = exact.verify_exact_operation(plan.manifest, verifier=_Verifier(plan), state="post",
                                                heartbeat=writer_lock.verify_held)
        if verified.get("all_match") is not True:
            raise WorkSessionSourceIntakeRecordExecutionError("source_intake_record_state_drifted")
        if authenticated() != final:
            raise WorkSessionSourceIntakeRecordExecutionError("source_intake_record_completion_evidence_required")
        _context(plan, context, claim, writer_lock, succeeded=True)
        return {"schema_version": record.RESULT_SCHEMA, "ok": True, "state": "completed",
            "lifecycle_action": "source_intake_record_exact_completion_verify",
            "plan_sha256": plan.manifest.manifest_sha256, "context_sha256": authority.context_sha256,
            "execution_sha256": execution, "approval_binding_sha256": authority.binding_sha256,
            "common_final_receipt_sha256": final["receipt_sha256"], "common_result_sha256": final["result"]["result_sha256"],
            "receipt_create_count": 1, "item_count": 1, "completed_item_count": 1,
            "completion_authentication_verified": True,
            "independent_verification": True, "writes_performed": False, "provider_calls_performed": False,
            "current_claim_authority_evaluated": False, "source_bytes_retained": False,
            "private_values_echoed": False, "paths_echoed": False}
    return _safe_call(verify, "source_intake_record_completion_evidence_required")


def _target(plan):
    expected = archive_services.source_intake_record_path(plan.source_intake_plan_sha256)
    if (type(plan.receipt_relative_path) is not str or plan.receipt_relative_path != expected
            or record.normalize_archive_relative_path(expected) != expected
            or tuple(expected.split("/")[:-1]) != _RECEIPT_ROOT):
        raise WorkSessionSourceIntakeRecordExecutionError("source_intake_record_target_unsafe")
    return plan.archive_root.joinpath(*expected.split("/"))


class _Verifier(record._Verifier):
    """Observe the approved lexical target, never a resolved alias or hardlink."""

    def read_field(self, *, target_kind, target_ref, field_ref, heartbeat):
        def read():
            heartbeat()
            if (target_kind != record.TARGET_KIND or target_ref != self.plan.receipt_relative_path
                    or field_ref != record.FIELD_REF):
                raise WorkSessionSourceIntakeRecordExecutionError("source_intake_record_target_unsafe")
            target = _target(self.plan)
            try:
                with archive_services._hold_activity_group_evidence_file(
                        self.plan.archive_root, target, max_bytes=record._MAX_RECEIPT_BYTES) as held:
                    # The held primitive binds the complete chain and original
                    # file but permits hardlinks. Reuse the strict control
                    # reader for single-link/stable-stat checks on both OSes.
                    raw = controls._read_control(target, maximum=record._MAX_RECEIPT_BYTES)
                    named = os.lstat(target)
                    if (raw != held["raw"] or not exact._safe_regular_stat(named, max_bytes=record._MAX_RECEIPT_BYTES)
                            or (int(named.st_dev), int(named.st_ino)) != held["identity"]):
                        raise WorkSessionSourceIntakeRecordExecutionError("source_intake_record_state_drifted")
            except FileNotFoundError:
                return None
            heartbeat()
            return raw
        return _safe_call(read, "source_intake_record_target_collision")


def _flush_chain(root):
    paths = [root]
    for part in _RECEIPT_ROOT:
        paths.append(paths[-1] / part)
    with ExitStack() as stack:
        bindings = [stack.enter_context(durable._bound_directory_for_move(path)) for path in paths]
        for path, binding in reversed(list(zip(paths, bindings))):
            durable._assert_named_reservation_directory_identity(path, binding.identity)
            durable._require_directory_durable(path)
            durable._assert_named_reservation_directory_identity(path, binding.identity)


class _SessionSourceIntakeRecordWriter:
    def __init__(self, prepared, context, claim, held):
        self.prepared, self.context, self.claim, self.held = prepared, context, claim, held
        self.plan = prepared.plan

    def _require(self):
        from .work_session_source_intake_record_workflow import _require_pending_source_intake_record_scope_held
        return _require_pending_source_intake_record_scope_held(self.prepared,
            context=self.context, claim=self.claim, held=self.held)

    def write_field(self, *, target_kind, target_ref, field_ref, value, heartbeat):
        if (target_kind != record.TARGET_KIND or target_ref != self.plan.receipt_relative_path
                or field_ref != record.FIELD_REF or type(value) is not bytes or value != self.plan.receipt_bytes):
            raise WorkSessionSourceIntakeRecordExecutionError()
        target = _target(self.plan)
        # Arbitrary progress may run here, never between final ownership guard
        # and no-replace publication. The held workflow supplies fixed guards.
        heartbeat()
        self._require()
        directory = exact._ensure_private_directory(self.plan.archive_root, _RECEIPT_ROOT)
        with durable._bound_directory_for_move(directory) as parent:
            _flush_chain(self.plan.archive_root)
            self._require()
            pending = directory / (".pending_" + uuid.uuid4().hex)
            registry._write_private_pending(pending, value, root=self.plan.archive_root)
            durable._require_directory_durable(directory)
            if controls._read_control(pending, maximum=record._MAX_RECEIPT_BYTES) != value:
                raise WorkSessionSourceIntakeRecordExecutionError("source_intake_record_state_drifted")
            self._require()
            durable._assert_named_reservation_directory_identity(directory, parent.identity)
            # Existing partial pending files are never scanned/adopted/deleted.
            # A refusal leaves this private stage intact for honest diagnosis.
            durable._atomic_move_file_no_replace(pending, target, expected_parent_identity=parent.identity)
            durable._require_directory_durable(directory)
            durable._assert_named_reservation_directory_identity(directory, parent.identity)
            if controls._read_control(target, maximum=record._MAX_RECEIPT_BYTES) != value:
                raise WorkSessionSourceIntakeRecordExecutionError("source_intake_record_state_drifted")
        self._require()
        heartbeat()
        self._require()


def _run_session_source_intake_record_exact_operation(prepared, *, context, claim, writer_lock,
                                                      resume, progress_hook=None):
    def run():
        from .work_session_source_intake_record_bundle import PreparedSessionSourceIntakeRecord
        from .work_session_source_intake_record_workflow import (
            _require_pending_source_intake_record_scope_held, _source_intake_record_operation_view,
        )
        if type(prepared) is not PreparedSessionSourceIntakeRecord or type(resume) is not bool:
            raise WorkSessionSourceIntakeRecordExecutionError("source_intake_record_scope_context_required")
        view = _source_intake_record_operation_view(prepared, context, writer_lock)
        frozen = _require_pending_source_intake_record_scope_held(view,
            context=context, claim=claim, held=writer_lock)
        plan = frozen.plan
        _target(plan)
        _reference, authority = _context(plan, context, claim, writer_lock, succeeded=False)
        writer = _SessionSourceIntakeRecordWriter(frozen, context, claim, writer_lock)
        def authenticate(payload):
            writer._require()
            return batch._completion_authenticator(claim)(payload)
        core = exact.apply_exact_operation(plan.manifest, payloads=record._Payloads(plan), writer=writer,
            verifier=_Verifier(plan),
            checkpoint_store=exact.FileExactOperationCheckpointStore(plan.archive_root, writer_lock=writer_lock),
            approval_authority=authority, completion_authenticator=authenticate,
            resume=resume, progress_hook=progress_hook)
        writer._require()
        return {"schema_version": record.RESULT_SCHEMA, "ok": True, "state": "completed",
            "lifecycle_action": "source_intake_record_exact_write", "plan_sha256": plan.manifest.manifest_sha256,
            "execution_sha256": core["execution_sha256"], "final_receipt_sha256": core["final_receipt_sha256"],
            "receipt_create_count": 1, "checkpoint_count": core["checkpoint_count"],
            "written_field_count": core.get("written_field_count", 0), "resumed_field_count": core.get("resumed_field_count", 0),
            "independent_verification": True, "writes_performed": bool(core.get("written_field_count", 0)),
            "source_bytes_retained": False, "provider_calls_performed": False,
            "private_values_echoed": False, "paths_echoed": False}
    return _safe_call(run)
