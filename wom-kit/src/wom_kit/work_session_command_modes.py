"""Content-free work-session invocation modes, independent of authority.

Availability here means only that this exact flag combination is supported.
It does not attest app identity, claim a session, acquire a lock, validate an
existing approval, or authorize a writer. In particular, resume never means
fresh native approval, and absence of native approval is not a lock exemption.
"""

from __future__ import annotations


def resolve_work_session_mode(
    *,
    action: str,
    dry_run: bool = False,
    approve: bool = False,
    apply: bool = False,
    resume: bool = False,
    review_original: bool = False,
) -> dict[str, bool | str | None]:
    """Classify strict public inputs without reading state or reflecting them."""

    unavailable = {
        "available": False,
        "mode": None,
        "read_only": None,
        "native_approval_required": False,
        "potential_write": False,
        "reason_code": "work_session_mode_unavailable",
    }
    flags = (dry_run, approve, apply, resume, review_original)
    if type(action) is not str or any(type(value) is not bool for value in flags):
        return unavailable

    mode = None
    if action in {"list", "inspect"}:
        if not any((approve, apply, resume, review_original)):
            mode = "read_only_query"
    elif action == "request-init":
        if not any((approve, apply, resume, review_original)):
            mode = "task_request_init"
    elif action == "register-app":
        if not approve and not review_original:
            mode = {
                (True, False, False): "registration_preview",
                (False, True, False): "registration_apply",
                (False, False, True): "registration_resume",
            }.get((dry_run, apply, resume))
    elif action == "create":
        if not dry_run and not apply:
            mode = {
                (True, False, False): "create",
                (True, False, True): "original_rereview",
                (False, True, False): "original_create_resume",
            }.get((approve, resume, review_original))
    elif action == "claim":
        if not dry_run and not approve and not review_original:
            mode = {
                (True, False): "claim_apply",
                (False, True): "claim_resume",
            }.get((apply, resume))

    if mode is None:
        return unavailable
    read_only = mode in {"read_only_query", "registration_preview", "task_request_init"}
    return {
        "available": True,
        "mode": mode,
        "read_only": read_only,
        "native_approval_required": mode in {"create", "original_rereview"},
        "potential_write": not read_only,
        "reason_code": None,
    }
