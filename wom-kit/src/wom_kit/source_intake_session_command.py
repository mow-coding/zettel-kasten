"""Explicit existing intake command route; no public approval or claim knobs.

This adapter owns grammar, the shared wait/runtime/held boundary and a closed
public projection. The private workflow alone authenticates the original
session, approval and completion. Legacy file-based dispatch stays separate.
"""

from pathlib import Path
import re

from . import work_session_service as sessions
from .exact_operation_manifest import ExactOperationProgress


_SCHEMA = "wom-kit/source-intake-session-command/v1"
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_BOOLEANS = frozenset({
    "ready_for_write", "current_claim_ownership_verified", "original_establishment_authenticated",
    "writes_performed", "source_bytes_retained", "artifact_capture_performed",
    "original_completion_verified", "actor_completion_published", "original_operation_already_completed",
    "prepared_capture_request_verified", "completion_authentication_verified", "independent_verification",
    "source_bytes_reverified", "requires_new_capture_approval", "domain_writer_reentered",
    "prepared_capture_request_created", "native_approval_redisplayed", "original_context_preserved",
})
_COUNTS = frozenset({"item_count", "completed_item_count"})
_DIGESTS = frozenset({
    "manifest_sha256", "plan_sha256", "context_sha256", "execution_sha256",
    "approval_binding_sha256", "common_final_receipt_sha256", "common_result_sha256",
})
_EXACT_STAGES = frozenset({"preflight", "heartbeat", "item_started", "field_verified", "item_verified", "completed"})
_PHASES = frozenset({"intake_preflight", "intake_revalidation", "waiting_for_writer",
                     "writer_acquired_revalidation_required"})


def _project_progress(event):
    """Read only exact event fields or a fixed dictionary phase; no callbacks."""
    current = total = None
    if type(event) is ExactOperationProgress:
        phase = event.stage
        if type(phase) is not str or phase not in _EXACT_STAGES:
            return None
        current, total = event.completed_items, event.total_items
        if (type(current) is not int or type(total) is not int
                or not 0 <= current <= total <= (1 << 63) - 1):
            return None
        stage = "exact-operation-" + phase
    elif type(event) is dict:
        phase = event.get("phase", event.get("stage"))
        if type(phase) is not str or phase not in _PHASES:
            return None
        stage = "source-intake-session-" + phase
    else:
        return None
    return stage, current, total


def _failure(code, *, mode, effects_started=False, original_completion_verified=False):
    return {
        "schema": _SCHEMA, "ok": False, "state": "blocked", "reason_code": code,
        "dry_run": type(mode) is str and mode == "preview",
        # Domain effects only: preview enters the common lock/runtime lane but
        # never enters an intake writer. Its control lock is not a domain write.
        "effects_state": "unknown" if effects_started and mode != "preview" else "none",
        "completion_verified": False, "original_completion_verified": original_completion_verified is True,
        "private_values_echoed": False, "paths_echoed": False,
    }


def _public_result(result, *, mode):
    """Never evaluate arbitrary repr, Mapping hooks or nested domain payloads."""
    if type(result) is not dict or result.get("ok") is not True:
        raise ValueError("work_session_intake_result_invalid")
    public = {"schema": _SCHEMA, "ok": True, "state": "ready_for_write" if mode == "preview" else "completed",
              "dry_run": mode == "preview", "private_values_echoed": False, "paths_echoed": False}
    for name in sorted(_BOOLEANS):
        if name in result:
            if type(result[name]) is not bool:
                raise ValueError("work_session_intake_result_invalid")
            public[name] = result[name]
    for name in sorted(_COUNTS):
        if name in result:
            if type(result[name]) is not int or not 0 <= result[name] <= (1 << 63) - 1:
                raise ValueError("work_session_intake_result_invalid")
            public[name] = result[name]
    for name in sorted(_DIGESTS):
        if name in result:
            if type(result[name]) is not str or _DIGEST.fullmatch(result[name]) is None:
                raise ValueError("work_session_intake_result_invalid")
            public[name] = result[name]
    if mode == "preview":
        if (public.get("ready_for_write") is not True or public.get("writes_performed") is not False
                or "manifest_sha256" not in public or "item_count" not in public):
            raise ValueError("work_session_intake_result_invalid")
    elif (public.get("original_completion_verified") is not True
          or public.get("completion_authentication_verified") is not True
          or public.get("independent_verification") is not True
          or "execution_sha256" not in public or "common_final_receipt_sha256" not in public):
        raise ValueError("work_session_intake_result_invalid")
    return public


def _dispatch_session_source_intake(
    root, *, mode, client_app_ref, task_route_ref, work_session_ref=None,
    request_path=None, reviewer_claim=None, cancel_requested=lambda: False, progress=lambda _event: None,
    family,
):
    """One held archive lane; resume receives only the retained caller route."""
    workflow, started, original_verified = None, False, False
    code = "work_session_intake_command_unavailable"
    try:
        if (type(family) is not str or family not in {"batch", "record"}
                or type(mode) is not str or mode not in {"preview", "apply", "resume", "review_original"}
                or not callable(cancel_requested) or not callable(progress)):
            return _failure("work_session_intake_command_invalid", mode=mode)
        original_mode = mode in {"resume", "review_original"}
        if original_mode and (request_path is not None or reviewer_claim is not None):
            return _failure("work_session_intake_original_inputs_forbidden", mode=mode)
        if not original_mode and (not (type(request_path) is str or isinstance(request_path, Path))
                                     or type(request_path) is str and not request_path):
            return _failure("work_session_intake_request_required", mode=mode)
        if mode != "apply" and reviewer_claim is not None:
            return _failure("work_session_intake_command_invalid", mode=mode)
        if mode == "apply" and (type(reviewer_claim) is not str or not reviewer_claim.strip()):
            return _failure("work_session_intake_reviewer_required", mode=mode)
        sessions._refs(client_app_ref, task_route_ref, work_session_ref, require_session=not original_mode)
        if work_session_ref is not None:
            sessions._refs(client_app_ref, task_route_ref, work_session_ref, require_session=True)
        resolved = sessions._root(root)
        if family == "batch":
            from . import work_session_source_intake_workflow as workflow
            preview = workflow._preview_session_source_intake_batch_held
            apply = workflow._execute_session_source_intake_batch_held
            resume = workflow._resume_session_source_intake_batch_held
        else:
            from . import work_session_source_intake_record_workflow as workflow
            preview = workflow._preview_session_source_intake_record_held
            apply = workflow._execute_session_source_intake_record_held
            resume = workflow._resume_session_source_intake_record_held

        def safe_callback(callback, *args):
            failed = False
            try:
                return callback(*args)
            except KeyboardInterrupt:
                raise
            except Exception:
                failed = True
            if failed:
                # A callback cannot impersonate an authenticated completion.
                raise RuntimeError("work_session_intake_callback_failed")

        safe_progress = lambda event: safe_callback(progress, event)
        safe_cancel = lambda: safe_callback(cancel_requested)
        common = dict(client_app_ref=client_app_ref, task_route_ref=task_route_ref,
                      work_session_ref=work_session_ref, progress_hook=safe_progress)

        def run(held):
            nonlocal started
            started = True
            if mode == "review_original":
                if family == "batch":
                    return workflow._review_original_session_source_intake_batch_held(resolved, held=held, **common)
                return workflow._review_original_session_source_intake_record_held(resolved, held=held, **common)
            if mode == "resume":
                return resume(resolved, held=held, **common)
            if mode == "preview":
                return preview(resolved, request_path, held=held, **common)
            return apply(
                resolved, request_path, held=held, reviewer_claim=reviewer_claim, **common)

        result = sessions._write(resolved, cancel_requested=safe_cancel, progress=safe_progress, run=run)
        return _public_result(result, mode=mode)
    except KeyboardInterrupt:
        code = "work_session_wait_cancelled"
    except Exception as error:
        if type(error) is getattr(workflow, "WorkSessionIntakeWorkflowError", None):
            proposed = error.code
            if type(proposed) is str and proposed in workflow._ERRORS:
                code = proposed
            if started:
                original_verified = getattr(error, "original_completion_verified", False) is True
        elif isinstance(error, sessions.WorkSessionServiceError):
            if type(error.code) is str and error.code in sessions._ERRORS:
                code = error.code
        elif isinstance(error, sessions.WorkSessionWaitError) and error.args in (
                ("work_session_wait_cancelled",), ("work_session_wait_root_changed",)):
            code = error.args[0]
    return _failure(code, mode=mode, effects_started=started, original_completion_verified=original_verified)


def dispatch_session_source_intake(
    root, *, mode, client_app_ref, task_route_ref, work_session_ref=None,
    request_path=None, reviewer_claim=None, cancel_requested=lambda: False, progress=lambda _event: None,
):
    """Existing batch route; keeps its public call grammar unchanged."""
    return _dispatch_session_source_intake(root, mode=mode, client_app_ref=client_app_ref,
        task_route_ref=task_route_ref, work_session_ref=work_session_ref, request_path=request_path,
        reviewer_claim=reviewer_claim, cancel_requested=cancel_requested, progress=progress, family="batch")


def dispatch_session_source_intake_record(
    root, *, mode, client_app_ref, task_route_ref, work_session_ref=None,
    plan_path=None, reviewer_claim=None, cancel_requested=lambda: False, progress=lambda _event: None,
):
    """Single receipt route; no batch request or source-byte capture effects."""
    return _dispatch_session_source_intake(root, mode=mode, client_app_ref=client_app_ref,
        task_route_ref=task_route_ref, work_session_ref=work_session_ref, request_path=plan_path,
        reviewer_claim=reviewer_claim, cancel_requested=cancel_requested, progress=progress, family="record")
