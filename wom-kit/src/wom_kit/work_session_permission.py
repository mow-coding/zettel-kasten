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
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import work_session_registry as registry
from .exact_human_approval_windows import ExactHumanApprovalOperation
from .target_collection_preview import TargetCollectionItem

MODE_MANUAL = "manual"
MODE_LIMITED = "limited"
MODE_ALLOW_ALL = "allow_all"
MODES = (MODE_MANUAL, MODE_LIMITED, MODE_ALLOW_ALL)
CLAIM_MECHANISM = "work_session_permission_mode"
CONTEXT_ENV = ("WOM_CLIENT_APP_REF", "WOM_TASK_ROUTE_REF", "WOM_WORK_SESSION_REF")

ALWAYS_DIALOG_OPERATIONS = frozenset({
    ExactHumanApprovalOperation.project_version_update,
    ExactHumanApprovalOperation.git_backup,
    ExactHumanApprovalOperation.notion_property_backfill,
    ExactHumanApprovalOperation.notion_property_backfill_revert,
    ExactHumanApprovalOperation.object_storage_setup_registration,
    ExactHumanApprovalOperation.object_storage_bytes_preservation,
    ExactHumanApprovalOperation.object_storage_formal_adoption,
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
})


class WorkSessionPermissionError(ValueError):
    def __init__(self, code: str = "work_session_permission_invalid") -> None:
        super().__init__(code)
        self.code = code if code in _ERRORS else "work_session_permission_invalid"


def _fail(code: str = "work_session_permission_invalid") -> WorkSessionPermissionError:
    return WorkSessionPermissionError(code)


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
    for item in operations:
        if item not in values:
            raise _fail("work_session_permission_operation_not_grantable")
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

    def permits(self, operation: ExactHumanApprovalOperation) -> bool:
        if type(operation) is not ExactHumanApprovalOperation or operation in ALWAYS_DIALOG_OPERATIONS:
            return False
        if self.mode == MODE_ALLOW_ALL:
            return True
        return self.mode == MODE_LIMITED and operation.value in self.operations

    def public_projection(self) -> dict[str, Any]:
        return {"schema": "wom-kit/work-session-permission/v1", "mode": self.mode,
                "operations": list(self.operations), "private_values_echoed": False}

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


def resolve_grant(archive_root, *, client_app_ref, task_route_ref, work_session_ref) -> SessionPermissionGrant | None:
    """Read-only: the grant only if the caller's route retains this claimed session.

    Any doubt (unregistered app, unknown route, foreign session, no claim, no
    permission, unreadable registry) resolves to None, which means the dialog.
    """

    try:
        from . import work_session_actor as actor
        from . import work_session_registration as registration

        for value, prefix in ((client_app_ref, "client_app"), (task_route_ref, "task_route"),
                              (work_session_ref, "work_session")):
            if not registry._ref(value, prefix):
                return None
        store = registration._store(archive_root)
        snapshot = store.read()
        row = snapshot._document["sessions"].get(work_session_ref)
        if row is None or row["state"] != "claimed" or row["client_app_ref"] != client_app_ref:
            return None
        permission = row.get("permission")
        if permission is None:
            return None
        routing = actor.WorkSessionActorStore(store, client_app_ref=client_app_ref, task_route_ref=task_route_ref)
        selected = routing.read()
        if selected is None:
            return None
        document = selected.document()
        if (document["work_session_ref"] != work_session_ref or document["claim_ref"] != row["claim_ref"]
                or document["observed_binding"] != snapshot.binding(work_session_ref).document()):
            return None
        return SessionPermissionGrant(
            client_app_ref=client_app_ref, task_route_ref=task_route_ref,
            work_session_ref=work_session_ref, claim_ref=row["claim_ref"],
            binding_sha256=snapshot.binding(work_session_ref).binding_sha256,
            mode=permission["mode"], operations=tuple(permission["operations"]),
        )
    except Exception:
        return None


def resolve_grant_from_environment(archive_root) -> SessionPermissionGrant | None:
    context = _current_context()
    if context is None:
        return None
    return resolve_grant(archive_root, **context)


def grant_still_permits(archive_root, grant: SessionPermissionGrant, operation: ExactHumanApprovalOperation) -> bool:
    """Re-resolve right before the claim is published; a revoked mode fails closed."""

    if type(grant) is not SessionPermissionGrant:
        return False
    current = resolve_grant(archive_root, client_app_ref=grant.client_app_ref,
                            task_route_ref=grant.task_route_ref, work_session_ref=grant.work_session_ref)
    return (current is not None and current.claim_ref == grant.claim_ref
            and current.binding_sha256 == grant.binding_sha256 and current.mode == grant.mode
            and current.operations == grant.operations and current.permits(operation))
