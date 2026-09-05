"""Existing Git command's explicit session route, without public authority knobs.

The legacy file-based Git route stays separate. This adapter uses the existing
session wait/runtime boundary and the concrete held workflow. It never accepts
an approval id, private manifest, replacement original reviewer or key/native
provider from the command line.
"""

from __future__ import annotations

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

        if (type(mode) is not str or mode not in {"preview", "apply", "resume"}
                or not callable(cancel_requested) or not callable(progress)
                or options is not None and type(options) is not dict):
            return _failure("work_session_git_command_invalid", mode=mode)
        if mode == "resume" and (reviewer_claim is not None or options):
            return _failure("work_session_git_original_inputs_forbidden", mode=mode)
        if mode != "apply" and reviewer_claim is not None:
            return _failure("work_session_git_command_invalid", mode=mode)
        if mode == "apply" and (type(reviewer_claim) is not str or not reviewer_claim.strip()):
            return _failure("git_backup_reviewer_required", mode=mode)
        sessions._refs(client_app_ref, task_route_ref, work_session_ref,
                       require_session=mode != "resume")
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
