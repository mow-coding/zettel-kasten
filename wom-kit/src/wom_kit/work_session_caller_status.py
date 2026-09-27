"""Read-only diagnosis of this caller; never transfer or create a grant."""

from . import work_session_permission as permission


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
            "permission_activated_by_inspection": False,
            "presenter_echoed": False,
        },
        # A claimed session is ownership, not proof of a running process. The
        # target coordinator adds observed operation leases separately.
        "execution": inspect_execution(root, session_ref),
        "runtime": runtime_status(root),
        "observation_is_future_write_authority": False,
    }
