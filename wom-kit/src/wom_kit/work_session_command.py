"""Bounded private management input shared by CLI and MCP routing.

Mode availability is syntax, never approval, runtime or ownership authority.
Only the existing service may perform a transition after its own checks.
"""

import json

from .work_session_command_modes import resolve_work_session_mode


REQUEST_LIMIT_BYTES = 32768
SCHEMA = "wom-kit/work-session-management/v1"


class WorkSessionRequestError(ValueError):
    def __init__(self):
        super().__init__("work_session_request_invalid")


def read_private_request(stream):
    """Read one bounded UTF-8 object, rejecting duplicate keys and constants."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise WorkSessionRequestError()
            result[key] = value
        return result

    def constant(_value):
        raise WorkSessionRequestError()

    try:
        if stream.isatty():
            raise WorkSessionRequestError()
        value = getattr(stream, "buffer", stream).read(REQUEST_LIMIT_BYTES + 1)
        raw = value.encode("utf-8") if type(value) is str else value
        if type(raw) is not bytes or len(raw) > REQUEST_LIMIT_BYTES:
            raise WorkSessionRequestError()
        parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
        if type(parsed) is dict:
            return parsed
    except Exception:
        pass
    # Do not retain parser messages, private request bytes or their context.
    raise WorkSessionRequestError()


def management_failure(reason_code, *, original_commit_verified=False):
    return {"schema": SCHEMA, "ok": False, "reason_code": reason_code,
            "original_commit_verified": original_commit_verified is True,
            "private_values_echoed": False}


def dispatch_work_session_management(root, *, action, dry_run=False, approve=False,
                                     apply=False, resume=False, review_original=False,
                                     client_app_ref=None, task_route_ref=None,
                                     work_session_ref=None, request=None,
                                     cancel_requested=lambda: False, progress=lambda _event: None):
    """Route only a supported invocation; never infer an app or task selector."""
    resolved = resolve_work_session_mode(action=action, dry_run=dry_run, approve=approve,
                                        apply=apply, resume=resume, review_original=review_original)
    mode = resolved["mode"]
    if not resolved["available"] or mode == "read_only_query":
        return management_failure("work_session_mode_unavailable")
    required_request = {
        "registration_preview": {"label"},
        "registration_apply": {"selection", "label"},
        "registration_resume": {"selection", "label"},
        "create": {"label", "reviewer_claim"},
    }.get(mode, set())
    value = {} if request is None else request
    needs_session = mode.startswith("claim_") or mode in {
        "state_transition_apply", "original_state_transition_resume",
    }
    if (type(value) is not dict or any(type(key) is not str for key in value)
            or set(value) != required_request):
        return management_failure("work_session_request_invalid")
    if mode.startswith("registration_"):
        if any(item is not None for item in (client_app_ref, task_route_ref, work_session_ref)):
            return management_failure("work_session_request_invalid")
    elif mode == "task_request_init":
        if (type(client_app_ref) is not str or task_route_ref is not None or work_session_ref is not None):
            return management_failure("work_session_request_invalid")
    elif (type(client_app_ref) is not str or type(task_route_ref) is not str
          or (needs_session and type(work_session_ref) is not str)
          or (not needs_session and work_session_ref is not None)):
        return management_failure("work_session_request_invalid")
    from . import work_session_service as service

    wait = {"cancel_requested": cancel_requested, "progress": progress}
    selected = {"client_app_ref": client_app_ref, "task_route_ref": task_route_ref}
    try:
        if mode == "registration_preview":
            result = service.preview_registration(root, label=value["label"])
        elif mode == "task_request_init":
            result = service.initialize_task_request(root, client_app_ref=client_app_ref)
        elif mode in {"registration_apply", "registration_resume"}:
            result = service.apply_or_resume_registration(root, selection=value["selection"],
                                                          label=value["label"], **wait)
        elif mode == "create":
            result = service.create_task(root, **selected, label=value["label"],
                                         reviewer_claim=value["reviewer_claim"], **wait)
        elif mode == "original_create_resume":
            result = service.resume_task_create(root, **selected, **wait)
        elif mode == "original_rereview":
            result = service.review_original_task_create(root, **selected, **wait)
        elif mode in {"state_transition_apply", "original_state_transition_resume"}:
            result = service.transition_task_state(root, **selected, action=action,
                original_resume=mode == "original_state_transition_resume",
                work_session_ref=work_session_ref, **wait)
        else:
            result = service.apply_or_resume_task_claim(root, **selected,
                                                        work_session_ref=work_session_ref, **wait)
    except service.WorkSessionServiceError as error:
        return management_failure(error.code,
                                  original_commit_verified=getattr(error, "original_commit_verified", False))
    succeeded = (type(result) is dict and (
        result.get("ok") is True or (mode == "registration_preview" and
        result.get("schema") == "wom-kit/work-session-registration-selection/v1")))
    return {"schema": SCHEMA, "ok": succeeded, "mode": mode, "result": result,
            "private_values_echoed": False}
