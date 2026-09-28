"""Read-only diagnosis of this caller; never transfer or create a grant."""

from . import work_session_permission as permission


def context_diagnostic():
    """Presence is diagnostic only; never echo or reconstruct private refs."""
    import os
    present = [bool(os.environ.get(name)) for name in permission.CONTEXT_ENV]
    return {
        "state": "missing" if not any(present) else (
            "incomplete" if not all(present) else (
                "valid_shape" if permission._current_context() is not None else "invalid_shape"
            )
        ),
        "missing_fields": [name for name, exists in zip(permission.CONTEXT_ENV, present) if not exists],
        "values_echoed": False,
        "missing_context_proves_grant_expired": False,
    }


def recovery_steps(reason):
    """Executable existing routes with explicit placeholders, not borrowed identity."""
    inspect = ["archive", "work-session", "<archive-root>", "--action", "inspect", "--caller-status", "--format", "json"]
    if reason in {"work_session_caller_context_missing", "work_session_caller_session_mismatch"}:
        return [{
            "action": "restore_own_retained_context",
            "instruction": "Restore the three retained routing refs from this conversation's original work-session result in the calling process. Do not select another session from the registry.",
            "required_fields": list(permission.CONTEXT_ENV),
            "command_after_restore": inspect,
            "if_original_context_unavailable": ["archive", "work-session", "<archive-root>", "--action", "request-init", "--client-app-ref", "<own-registered-app-ref>", "--dry-run", "--format", "json"],
            "activates_permission": False,
        }]
    if reason is None:
        return []
    return [{
        "action": "restore_own_presenter_or_reset_permission",
        "instruction": "For a missing presenter, reuse only the live caller's retained presenter. If it is lost, expired, or mismatched, use the official permission action below with this conversation's own routing refs. Inspection cannot restore a lost secret.",
        "command": ["archive", "work-session", "<archive-root>", "--action", "set-permission-mode", "--client-app-ref", "<own-client-app-ref>", "--task-route-ref", "<own-task-route-ref>", "--work-session-ref", "<own-work-session-ref>", "--request-stdin", "--approve", "--format", "json"],
        "private_stdin_fields": ["reviewer_claim", "permission_mode", "operations"],
        "command_after_restore": inspect,
        "activates_permission": False,
    }]


def runtime_status(root):
    from .archive_services import wom_kit_version_info

    info = wom_kit_version_info(root, redact_local_paths=True)
    # Project only fixed diagnostic fields, never paths, labels, tokens or
    # version output's human-authored warnings. Keep unknown distinct from false.
    pin = info.get("project_pin") or {}
    runtime = info.get("project_runtime") or {}
    alignment = info.get("runtime_alignment") or {}
    launch = info.get("path_shadow_diagnostic") or {}
    return {
        "running_version": info.get("version"),
        "consistency_state": info.get("consistency_state"),
        "project_pin_status": pin.get("status"),
        "project_runtime_status": runtime.get("status"),
        "alignment_status": alignment.get("status"),
        "selected_launcher_is_running_launcher": launch.get("running_launcher_matches_selected"),
        "next_action": "archive version --format json",
    }


def inspect_caller(root, *, session_ref, session_row):
    from .operation_observation import inspect as inspect_execution
    context = permission._current_context()
    grant = None
    if context is None:
        reason = "work_session_caller_context_missing"
    elif context["work_session_ref"] != session_ref:
        reason = "work_session_caller_session_mismatch"
    else:
        grant, reason = permission.resolve_grant_outcome(root, **context)
        if grant is None and reason is None:
            reason = "work_session_permission_manual"
    actions = {
        "work_session_caller_context_missing": "bind_this_conversations_official_session_route",
        "work_session_caller_session_mismatch": "inspect_this_callers_session_without_ref",
        "work_session_permission_manual": "work_session_set_permission_mode_approve",
        "work_session_presenter_missing": "restore_live_conversation_presenter_or_set_permission_mode_approve",
        "work_session_presenter_mismatch": "use_own_session_or_official_handoff",
        "work_session_grant_expired": "work_session_set_permission_mode_approve",
        "work_session_grant_legacy_shape": "work_session_set_permission_mode_approve",
    }
    saved = session_row.get("permission")
    shape = permission.permission_shape(saved)
    return {
        "schema": "wom-kit/work-session-caller-status/v1",
        "read_only": True,
        "recorded_permission": {
            "mode": "manual" if saved is None else saved["mode"],
            "operations": [] if saved is None else list(saved["operations"]),
            "granted_at": saved["granted_at"] if shape == "v2" else None,
            "expires_at": saved["expires_at"] if shape == "v2" else None,
            "evidence": "validated_session_registry",
        },
        "caller": {
            "same_session": None if context is None else context["work_session_ref"] == session_ref,
            "can_use_recorded_grant": grant is not None,
            "reason_code": reason,
            "next_action": actions.get(reason, "recheck_official_session_route") if reason else None,
            "recovery_steps": recovery_steps(reason),
            "context": context_diagnostic(),
            "presenter_state": "available" if grant is not None else (
                "missing" if reason == "work_session_presenter_missing" else "not_verified"
            ),
            "grant_expired": permission.permission_expired(saved) if saved is not None else None,
            "caller_process_termination": "not_established_by_missing_presenter",
            "permission_activated_by_inspection": False,
            "presenter_echoed": False,
        },
        # A claimed session is ownership, not proof of a running process. The
        # target coordinator adds observed operation leases separately.
        "execution": inspect_execution(root, session_ref),
        "runtime": runtime_status(root),
        "observation_is_future_write_authority": False,
    }
