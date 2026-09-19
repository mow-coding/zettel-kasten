"""Per-work-session permission modes (v0.4.24): eligibility, grants, lookup.

A permission mode is a human decision recorded on the claimed work session
(`work-session --action set-permission-mode --approve`). It lets the exact
approval broker mint a write's one-use claim without opening the native
dialog for the operation kinds it names. It is not a new approval system:
every write still publishes its own authenticated claim bound to its exact
plan and target digests, the claim records that the permission mode was the
mechanism, and the grant dies with the claim it was granted under (pause,
handoff, complete and recover clear it).

Always-dialog operations can never be granted: project updates, remote
providers, the session lifecycle itself, repairs and overrides. Credential
writers use their own Windows credential native path and are unaffected.

v0.4.34 (beta letter 165 [A]): a grant is presenter-bound and time-boxed.
``set-permission-mode --approve`` mints a random presenter secret whose
sha256 is written into the immutable ``permission`` row together with
``granted_at`` / ``expires_at``; the secret is returned exactly once in that
approve result and lives only in the granting conversation's process
(``WOM_WORK_SESSION_PRESENTER`` or the in-process holder an MCP host keeps).
A write that presents the three refs without the matching secret, or after
the expiry, gets the dialog and a fixed refusal code on its result. Rows
written before v0.4.34 (the two-key shape) are refused the same way until the
grant is set again. The token binds the grant to whoever received the approve
result; the claim's presenter fingerprint, the expiry and the operator's
recover route are the guards against reuse by another conversation.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from . import work_session_registry as registry
from .exact_human_approval_windows import ExactHumanApprovalOperation
from .target_collection_preview import TargetCollectionItem

MODE_MANUAL = "manual"
MODE_LIMITED = "limited"
MODE_ALLOW_ALL = "allow_all"
MODES = (MODE_MANUAL, MODE_LIMITED, MODE_ALLOW_ALL)
CLAIM_MECHANISM = "work_session_permission_mode"
CONTEXT_ENV = ("WOM_CLIENT_APP_REF", "WOM_TASK_ROUTE_REF", "WOM_WORK_SESSION_REF")
# v0.4.34: the presenter secret travels only here (or the MCP host's holder).
PRESENTER_ENV = "WOM_WORK_SESSION_PRESENTER"
PERMISSION_SCHEMA_V1 = "wom-kit/work-session-permission/v1"
PERMISSION_SCHEMA_V2 = "wom-kit/work-session-permission/v2"
GRANT_HOURS_DEFAULT = 8
GRANT_HOURS_MAX = 24
PRESENTER_TOKEN_BYTES = 32
PERMISSION_V1_KEYS = frozenset({"mode", "operations"})
PERMISSION_V2_KEYS = frozenset({"mode", "operations", "presenter_sha256", "granted_at", "expires_at"})
_TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{43}\Z")
_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_TIMESTAMP_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")
GRANT_REFUSAL_CODES = frozenset({
    "work_session_presenter_missing",
    "work_session_presenter_mismatch",
    "work_session_grant_expired",
    "work_session_grant_legacy_shape",
    "work_session_grant_unavailable",
    "work_session_grant_warning_review_required",
})
# v0.4.34 (letter 165 [B]): a grant never covers a write whose bound warning
# set names a legacy identifier; the human sees that body in the dialog.
GRANT_BLOCKING_WARNING_CODES = frozenset({
    "legacy_identifier_in_new_record",
    "legacy_identifier_in_migrated_record",
    "label_legacy_identifier_review",
})
_clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)

ALWAYS_DIALOG_OPERATIONS = frozenset({
    ExactHumanApprovalOperation.project_version_update,
    ExactHumanApprovalOperation.git_backup,
    ExactHumanApprovalOperation.notion_property_backfill,
    ExactHumanApprovalOperation.notion_property_backfill_revert,
    ExactHumanApprovalOperation.object_storage_setup_registration,
    ExactHumanApprovalOperation.object_storage_bytes_preservation,
    ExactHumanApprovalOperation.object_storage_formal_adoption,
    ExactHumanApprovalOperation.object_storage_bytes_restore,
    ExactHumanApprovalOperation.object_storage_bytes_offload,
    ExactHumanApprovalOperation.object_storage_bytes_upload,
    ExactHumanApprovalOperation.exact_approval_claim_finalize,
    ExactHumanApprovalOperation.work_session,
    ExactHumanApprovalOperation.integrity_repair,
    ExactHumanApprovalOperation.duplicate_object_reconcile,
    ExactHumanApprovalOperation.local_recovery,
    ExactHumanApprovalOperation.local_recovery_revert,
    ExactHumanApprovalOperation.warning_override,
    ExactHumanApprovalOperation.human_artifact_lifecycle,
})
GRANTABLE_OPERATIONS = frozenset(
    member for member in ExactHumanApprovalOperation if member not in ALWAYS_DIALOG_OPERATIONS
)
_ERRORS = frozenset({
    "work_session_permission_invalid",
    "work_session_permission_operation_not_grantable",
    "work_session_permission_grant_hours_invalid",
})


class WorkSessionPermissionError(ValueError):
    def __init__(self, code: str = "work_session_permission_invalid", *, detail: dict[str, Any] | None = None) -> None:
        super().__init__(code)
        self.code = code if code in _ERRORS else "work_session_permission_invalid"
        # v0.4.27: content-free detail (positions and fixed operation names
        # only); the refused request value itself is never echoed.
        self.detail = dict(detail) if type(detail) is dict else None


def _fail(code: str = "work_session_permission_invalid") -> WorkSessionPermissionError:
    return WorkSessionPermissionError(code)


def normalize_grant_hours(value: Any) -> int:
    """1..24 whole hours; absent means the default. Never echoes the value."""

    if value is None:
        return GRANT_HOURS_DEFAULT
    if type(value) is not int or isinstance(value, bool) or not 1 <= value <= GRANT_HOURS_MAX:
        raise _fail("work_session_permission_grant_hours_invalid")
    return value


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_timestamp(value: Any) -> datetime | None:
    if type(value) is not str or _TIMESTAMP_RE.fullmatch(value) is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def mint_presenter() -> tuple[str, str]:
    """(secret token, sha256 ref of it). The token is shown once and never stored."""

    token = base64.urlsafe_b64encode(secrets.token_bytes(PRESENTER_TOKEN_BYTES)).decode("ascii").rstrip("=")
    return token, presenter_sha256(token)


def presenter_sha256(token: str) -> str:
    return "sha256:" + hashlib.sha256(token.encode("utf-8")).hexdigest()


def bind_grant(grant: dict[str, Any] | None, *, presenter_sha256: str, grant_hours: int,
               now: datetime | None = None) -> dict[str, Any] | None:
    """Freeze the v2 row: the normalized mode plus presenter hash and the time box."""

    if grant is None:
        return None
    if type(presenter_sha256) is not str or _DIGEST_RE.fullmatch(presenter_sha256) is None:
        raise _fail()
    hours = normalize_grant_hours(grant_hours)
    started = _clock() if now is None else now
    return {
        "mode": grant["mode"],
        "operations": list(grant["operations"]),
        "presenter_sha256": presenter_sha256,
        "granted_at": _timestamp(started),
        "expires_at": _timestamp(started + timedelta(hours=hours)),
    }


def permission_shape(permission: Any) -> str | None:
    """'v2' for a presenter-bound row, 'legacy' for the pre-v0.4.34 two-key row, None otherwise."""

    if type(permission) is not dict:
        return None
    keys = set(permission)
    if keys == PERMISSION_V2_KEYS:
        return "v2"
    if keys == PERMISSION_V1_KEYS:
        return "legacy"
    return None


def permission_expired(permission: Any, *, now: datetime | None = None) -> bool | None:
    """True/False for a v2 row, None when the row carries no usable expiry."""

    if permission_shape(permission) != "v2":
        return None
    expires = _parse_timestamp(permission.get("expires_at"))
    if expires is None:
        return None
    current = _clock() if now is None else now
    return current >= expires


_PROCESS_PRESENTERS: dict[str, str] = {}
_PROCESS_PRESENTERS_LOCK = threading.Lock()


def hold_presenter(work_session_ref: str, token: str) -> None:
    """Keep the token in this process only (an MCP host never shows it to the model)."""

    if not registry._ref(work_session_ref, "work_session") or type(token) is not str or _TOKEN_RE.fullmatch(token) is None:
        raise _fail()
    with _PROCESS_PRESENTERS_LOCK:
        _PROCESS_PRESENTERS[work_session_ref] = token


def release_presenter(work_session_ref: str) -> None:
    with _PROCESS_PRESENTERS_LOCK:
        _PROCESS_PRESENTERS.pop(work_session_ref, None)


def _process_presenter(work_session_ref: str) -> str | None:
    """The held token for this session, else the environment variable, else None."""

    with _PROCESS_PRESENTERS_LOCK:
        held = _PROCESS_PRESENTERS.get(work_session_ref)
    if held is not None:
        return held
    value = os.environ.get(PRESENTER_ENV)
    if type(value) is not str or _TOKEN_RE.fullmatch(value) is None:
        return None
    return value


def normalize_grant(permission_mode: Any, operations: Any) -> dict[str, Any] | None:
    """Turn the caller's request into the registry's content-free grant (None = manual)."""

    if permission_mode not in MODES or type(permission_mode) is not str:
        raise _fail()
    if operations is None:
        operations = []
    if type(operations) is not list or len(operations) > 64 or any(type(item) is not str for item in operations):
        raise _fail()
    if permission_mode == MODE_MANUAL:
        if operations:
            raise _fail()
        return None
    if permission_mode == MODE_ALLOW_ALL:
        if operations:
            raise _fail()
        return {"mode": MODE_ALLOW_ALL, "operations": []}
    if not operations:
        raise _fail()
    values = {member.value for member in GRANTABLE_OPERATIONS}
    for index, item in enumerate(operations):
        if item not in values:
            raise WorkSessionPermissionError(
                "work_session_permission_operation_not_grantable",
                detail={"rejected_operation_index": index,
                        "grantable_operations": sorted(values),
                        "always_dialog_operations": sorted(member.value for member in ALWAYS_DIALOG_OPERATIONS)},
            )
    return {"mode": MODE_LIMITED, "operations": sorted(set(operations))}


@dataclass(frozen=True, repr=False)
class SessionPermissionGrant:
    """The resolved grant for one caller: content-free refs and the mode."""

    client_app_ref: str
    task_route_ref: str
    work_session_ref: str
    claim_ref: str
    binding_sha256: str
    mode: str
    operations: tuple[str, ...]
    # v0.4.34: the presenter hash and the expiry the row was granted with.
    presenter_sha256: str | None = None
    expires_at: str | None = None

    def permits(self, operation: ExactHumanApprovalOperation) -> bool:
        if type(operation) is not ExactHumanApprovalOperation or operation in ALWAYS_DIALOG_OPERATIONS:
            return False
        if self.mode == MODE_ALLOW_ALL:
            return True
        return self.mode == MODE_LIMITED and operation.value in self.operations

    def public_projection(self) -> dict[str, Any]:
        return {"schema": PERMISSION_SCHEMA_V2, "mode": self.mode,
                "operations": list(self.operations), "presenter_bound": self.presenter_sha256 is not None,
                "expires_at": self.expires_at, "private_values_echoed": False}

    def __repr__(self) -> str:
        return "SessionPermissionGrant(<content-free>)"


def preview_items(*, archive_identity_sha256: str, permission: dict[str, Any] | None) -> list[TargetCollectionItem]:
    """Dialog lines: the mode and each granted kind by its Korean label."""

    mode = MODE_MANUAL if permission is None else permission["mode"]
    labels = {MODE_MANUAL: "수동 승인 (모든 쓰기마다 승인 창)",
              MODE_LIMITED: "제한 승인 (아래 작업 종류만 승인 창 없이)",
              MODE_ALLOW_ALL: "전체 허용 (프로젝트 업데이트·자격증명 제외, 승인 창 없이)"}
    items = [TargetCollectionItem(
        identity_sha256=registry._digest({"archive": archive_identity_sha256, "kind": "permission_mode", "mode": mode}),
        kind="permission_mode", title=labels[mode],
    )]
    if permission is not None and permission["mode"] == MODE_LIMITED:
        from .exact_human_approval_windows import _OPERATION_LABELS
        for value in permission["operations"]:
            member = ExactHumanApprovalOperation(value)
            items.append(TargetCollectionItem(
                identity_sha256=registry._digest({"archive": archive_identity_sha256, "kind": "operation", "operation": value}),
                kind="operation", title=_OPERATION_LABELS.get(member, value),
            ))
    if permission_shape(permission) == "v2":
        # v0.4.34: the reviewer sees the time box and that the grant is bound
        # to the conversation that receives the approve result.
        granted, expires = _parse_timestamp(permission["granted_at"]), _parse_timestamp(permission["expires_at"])
        hours = int((expires - granted).total_seconds() // 3600) if granted and expires else 0
        items.append(TargetCollectionItem(
            identity_sha256=registry._digest({"archive": archive_identity_sha256, "kind": "grant_box",
                                              "presenter_sha256": permission["presenter_sha256"],
                                              "expires_at": permission["expires_at"]}),
            kind="grant_box", title=f"유효 시간 {hours}시간 · 이 대화(제시 토큰)에만 적용",
        ))
    return items


def _current_context() -> dict[str, str] | None:
    """The caller's retained session refs, from the process environment."""

    import os

    values = tuple(os.environ.get(name) for name in CONTEXT_ENV)
    if any(value is None or not value for value in values):
        return None
    client_app_ref, task_route_ref, work_session_ref = values
    if (not registry._ref(client_app_ref, "client_app") or not registry._ref(task_route_ref, "task_route")
            or not registry._ref(work_session_ref, "work_session")):
        return None
    return {"client_app_ref": client_app_ref, "task_route_ref": task_route_ref, "work_session_ref": work_session_ref}


_UNSET_PRESENTER = object()


def resolve_grant_outcome(archive_root, *, client_app_ref, task_route_ref, work_session_ref,
                          presenter: Any = _UNSET_PRESENTER) -> tuple[SessionPermissionGrant | None, str | None]:
    """Read-only: (grant, None) when the caller's route retains this claimed session
    AND presents the grant's secret before its expiry; (None, reason) otherwise.

    The reason is one fixed code from GRANT_REFUSAL_CODES, or None when the
    session simply carries no permission (manual). Any doubt (unregistered
    app, unknown route, foreign session, no claim, unreadable registry)
    resolves to the dialog. v0.4.34: ``presenter`` unset means the process
    holder or WOM_WORK_SESSION_PRESENTER; None means "no secret presented".
    """

    try:
        from . import work_session_actor as actor
        from . import work_session_registration as registration

        for value, prefix in ((client_app_ref, "client_app"), (task_route_ref, "task_route"),
                              (work_session_ref, "work_session")):
            if not registry._ref(value, prefix):
                return None, "work_session_grant_unavailable"
        store = registration._store(archive_root)
        snapshot = store.read()
        row = snapshot._document["sessions"].get(work_session_ref)
        if row is None or row["state"] != "claimed" or row["client_app_ref"] != client_app_ref:
            return None, "work_session_grant_unavailable"
        permission = row.get("permission")
        if permission is None:
            return None, None
        routing = actor.WorkSessionActorStore(store, client_app_ref=client_app_ref, task_route_ref=task_route_ref)
        selected = routing.read()
        if selected is None:
            return None, "work_session_grant_unavailable"
        document = selected.document()
        if (document["work_session_ref"] != work_session_ref or document["claim_ref"] != row["claim_ref"]
                or document["observed_binding"] != snapshot.binding(work_session_ref).document()):
            return None, "work_session_grant_unavailable"
        shape = permission_shape(permission)
        if shape != "v2":
            return None, "work_session_grant_legacy_shape"
        expired = permission_expired(permission)
        if expired is None or expired:
            return None, "work_session_grant_expired"
        token = _process_presenter(work_session_ref) if presenter is _UNSET_PRESENTER else presenter
        if type(token) is not str or _TOKEN_RE.fullmatch(token) is None:
            return None, "work_session_presenter_missing"
        if not hmac.compare_digest(presenter_sha256(token), permission["presenter_sha256"]):
            return None, "work_session_presenter_mismatch"
        return SessionPermissionGrant(
            client_app_ref=client_app_ref, task_route_ref=task_route_ref,
            work_session_ref=work_session_ref, claim_ref=row["claim_ref"],
            binding_sha256=snapshot.binding(work_session_ref).binding_sha256,
            mode=permission["mode"], operations=tuple(permission["operations"]),
            presenter_sha256=permission["presenter_sha256"], expires_at=permission["expires_at"],
        ), None
    except Exception:
        return None, "work_session_grant_unavailable"


def resolve_grant(archive_root, *, client_app_ref, task_route_ref, work_session_ref,
                  presenter: Any = _UNSET_PRESENTER) -> SessionPermissionGrant | None:
    """The None projection of resolve_grant_outcome (any refusal means the dialog)."""

    grant, _reason = resolve_grant_outcome(archive_root, client_app_ref=client_app_ref,
                                           task_route_ref=task_route_ref, work_session_ref=work_session_ref,
                                           presenter=presenter)
    return grant


def resolve_grant_from_environment(archive_root) -> SessionPermissionGrant | None:
    context = _current_context()
    if context is None:
        return None
    return resolve_grant(archive_root, **context)


def resolve_grant_outcome_from_environment(archive_root) -> tuple[SessionPermissionGrant | None, str | None]:
    context = _current_context()
    if context is None:
        return None, None
    return resolve_grant_outcome(archive_root, **context)


def grant_still_permits(archive_root, grant: SessionPermissionGrant, operation: ExactHumanApprovalOperation) -> bool:
    """Re-resolve right before the claim is published; a revoked mode fails closed."""

    if type(grant) is not SessionPermissionGrant:
        return False
    current = resolve_grant(archive_root, client_app_ref=grant.client_app_ref,
                            task_route_ref=grant.task_route_ref, work_session_ref=grant.work_session_ref)
    return (current is not None and current.claim_ref == grant.claim_ref
            and current.binding_sha256 == grant.binding_sha256 and current.mode == grant.mode
            and current.operations == grant.operations and current.presenter_sha256 == grant.presenter_sha256
            and current.expires_at == grant.expires_at and current.permits(operation))


def grant_blocking_warnings(warning_codes: Any) -> tuple[str, ...]:
    """The bound warning codes (literal, not digested) that force the dialog."""

    if type(warning_codes) not in {tuple, list}:
        return ()
    return tuple(sorted(code for code in warning_codes if type(code) is str and code in GRANT_BLOCKING_WARNING_CODES))
