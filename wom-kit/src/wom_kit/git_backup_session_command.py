"""Existing Git command's explicit session route, without public authority knobs.

The legacy file-based Git route stays separate. This adapter uses the existing
session wait/runtime boundary and the concrete held workflow. It never accepts
an approval id, private manifest, replacement original reviewer or key/native
provider from the command line.
"""

from __future__ import annotations

import re

from . import work_session_service as sessions


def _failure(code, *, mode, effects_started=False, original_commit_verified=False):
    return {
        "schema": "wom-kit/git-backup-session-command/v1",
        "ok": False,
        "status": "blocked",
        "reason_code": code,
        "dry_run": type(mode) is str and mode == "preview",
        "effects_state": "unknown" if effects_started else "none",
        "backup_completion_verified": False,
        "original_commit_verified": original_commit_verified is True,
        "private_values_echoed": False,
    }


def dispatch_session_git_backup(
    root, *, mode, client_app_ref, task_route_ref, work_session_ref=None,
    reviewer_claim=None, options=None, cancel_requested=lambda: False,
    progress=lambda _event: None,
):
    """CLI-owned composition; original continuation never receives fresh inputs."""
    workflow = None
    started = False
    original_verified = False
    code = "work_session_git_command_unavailable"
    try:
        from . import work_session_git_workflow as workflow

        if (type(mode) is not str or mode not in {"preview", "apply", "resume", "review_original"}
                or not callable(cancel_requested) or not callable(progress)
                or options is not None and type(options) is not dict):
            return _failure("work_session_git_command_invalid", mode=mode)
        original_mode = mode in {"resume", "review_original"}
        if original_mode and (reviewer_claim is not None or options):
            return _failure("work_session_git_original_inputs_forbidden", mode=mode)
        if mode != "apply" and reviewer_claim is not None:
            return _failure("work_session_git_command_invalid", mode=mode)
        if mode == "apply" and (type(reviewer_claim) is not str or not reviewer_claim.strip()):
            return _failure("git_backup_reviewer_required", mode=mode)
        sessions._refs(client_app_ref, task_route_ref, work_session_ref,
                       require_session=not original_mode)
        resolved = sessions._root(root)
        fresh_options = dict(options or {})
        if set(fresh_options) - {"remote_name", "branch", "credential_mode", "max_changes", "max_changed_bytes"}:
            return _failure("work_session_git_command_invalid", mode=mode)
        def safe_callback(callback, *args):
            failed = False
            try:
                return callback(*args)
            except KeyboardInterrupt:
                raise
            except Exception:
                failed = True
            if failed:
                # A caller callback cannot impersonate an authenticated domain
                # completion exception, even if it constructs the same class.
                raise RuntimeError("work_session_git_callback_failed")

        safe_progress = lambda event: safe_callback(progress, event)
        safe_cancel = lambda: safe_callback(cancel_requested)
        common = dict(client_app_ref=client_app_ref, task_route_ref=task_route_ref,
                      work_session_ref=work_session_ref, progress_hook=safe_progress)

        def run(held):
            nonlocal started
            started = True
            if mode == "resume":
                return workflow._resume_session_git_backup_held(resolved, held=held, **common)
            if mode == "review_original":
                return workflow._review_original_session_git_backup_held(resolved, held=held, **common)
            if mode == "preview":
                return workflow._preview_session_git_backup_held(resolved, held=held, **common, **fresh_options)
            return workflow._execute_session_git_backup_held(
                resolved, held=held, reviewer_claim=reviewer_claim, **common, **fresh_options,
            )

        result = sessions._write(resolved, cancel_requested=safe_cancel, progress=safe_progress, run=run)
        if type(result) is not dict or type(result.get("ok")) is not bool:
            return _failure("work_session_git_command_unavailable", mode=mode, effects_started=started)
        return result
    except KeyboardInterrupt:
        code = "work_session_wait_cancelled"
    except Exception as error:
        # Only fixed codes from the actual domain/shared facade are forwarded;
        # arbitrary callback/OS strings, args and exception chains are discarded.
        proposed = getattr(error, "code", None)
        allowed = sessions._ERRORS | getattr(workflow, "_ERRORS", frozenset())
        if type(proposed) is str and proposed in allowed:
            code = proposed
        if started and type(error) is getattr(workflow, "WorkSessionGitWorkflowError", None):
            original_verified = getattr(error, "original_commit_verified", False) is True
        if isinstance(error, sessions.WorkSessionWaitError) and error.args in (
            ("work_session_wait_cancelled",), ("work_session_wait_root_changed",),
        ):
            code = error.args[0]
    return _failure(code, mode=mode, effects_started=started, original_commit_verified=original_verified)


def _project_mcp_git_backup_result(result, *, mode):
    """Presentation only: project a domain result, never authenticate its claims.

    The CLI continues to receive its original result. Only exact builtin values
    from a closed field vocabulary cross MCP; no mapping methods, repr, private
    locators or nested operation/anchor documents are forwarded.
    """
    from . import work_session_git_workflow as workflow

    value = result if type(result) is dict and all(type(key) is str for key in result) else {}
    allowed_errors = sessions._ERRORS | workflow._ERRORS | frozenset({
        "work_session_git_command_unavailable", "work_session_git_command_invalid",
        "work_session_git_original_inputs_forbidden", "git_backup_reviewer_required",
    })
    reason = value.get("reason_code")
    reason = reason if type(reason) is str and reason in allowed_errors else "work_session_git_command_unavailable"
    effects = value.get("effects_state")
    public = _failure(reason, mode=mode,
                      effects_started=not (type(effects) is str and effects == "none"),
                      original_commit_verified=value.get("original_commit_verified") is True)
    # These booleans describe observed outcomes, not an authority token. In
    # particular, a previously verified commit survives a later ownership error.
    for key in (
        "original_commit_verified", "current_claim_ownership_verified",
        "current_claim_authority_evaluated", "original_establishment_authenticated",
        "actor_completion_published", "original_operation_already_completed",
        "snapshot_partition_complete", "receipt_only", "document_provenance_evaluated",
        "exact_human_approval_required", "ready_for_write", "backup_performed",
        "artifact_backup_complete", "source_bytes_backed_up", "artifact_capture_performed",
        "write_performed", "domain_writer_reentered", "signed_terminal_tail_only",
        "common_final_tail_only", "native_approval_redisplayed", "original_context_preserved",
    ):
        item = value.get(key)
        if type(item) is bool:
            public[key] = item
    for key in (
        "selected_receipt_count", "selected_output_count", "selected_intake_output_count",
        "excluded_change_count", "other_session_receipt_count", "other_session_output_count",
        "ownership_unverified_count", "unverified_receipt_candidate_count", "intake_context_count",
        "authenticated_intake_original_count", "unverified_intake_context_count", "commit_count",
    ):
        item = value.get(key)
        if type(item) is int and 0 <= item <= 100000:
            public[key] = item
    for key in ("manifest_sha256", "execution_sha256", "common_final_receipt_sha256"):
        item = value.get(key)
        if type(item) is str and re.fullmatch(r"sha256:[0-9a-f]{64}", item):
            public[key] = item
    anchor = value.get("original_git_anchors")
    anchor_valid = (type(anchor) is dict and all(type(key) is str for key in anchor)
        and type(anchor.get("schema")) is str
        and anchor.get("schema") == "wom-kit/work-session-git-anchor-observation/v1"
        and type(anchor.get("status")) is str and anchor.get("status") == "verified"
        and type(anchor.get("commit_count")) is int
        and 1 <= anchor.get("commit_count") <= 100000
        and anchor.get("commit_count") == public.get("commit_count"))
    public["commit_anchors_verified"] = anchor_valid and anchor.get("commit_anchors_verified") is True
    public["remote_ref_independently_verified"] = anchor_valid and anchor.get("remote_ref_independently_verified") is True
    status = value.get("status")
    preview = type(status) is str and status in {
        "receipt_selection_classified", "no_eligible_receipts",
        "session_output_selection_classified", "no_eligible_session_outputs",
    }
    completed = (type(status) is str and status in {"session_receipts_backed_up", "session_outputs_backed_up"}
        and all(public.get(key) is True for key in (
            "backup_performed", "original_commit_verified", "current_claim_ownership_verified",
            "actor_completion_published", "commit_anchors_verified", "remote_ref_independently_verified"))
        and "execution_sha256" in public and "common_final_receipt_sha256" in public)
    if value.get("ok") is True and (preview or completed):
        public.update(ok=True, status=status, backup_completion_verified=completed)
        public.pop("reason_code")
        public["effects_state"] = "none" if preview else "verified"
    return public
