"""High-level, approval-gated credential and Notion recovery workflows.

The lower-level modules in this package intentionally expose small injectable
primitives.  This module is the composition boundary used by a CLI or another
trusted local caller.  It keeps five important promises:

* planning never opens Windows Credential Manager, calls Notion, or writes;
* live intake starts only after an explicit approval and an unchanged plan;
* the archive authentication key remains inside ``use_key`` callbacks;
* only authenticated receipts plus an approved default lifecycle can broker a
  credential for recovery; and
* public results never contain a raw secret, reviewed anchor, backend target,
  authentication key, or exception text.

Every operating-system and provider dependency is injectable.  Importing this
module and running its tests cannot open a real dialog, credential store, or
network connection.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hmac
import math
import multiprocessing
from pathlib import Path
import re
from typing import Any, Protocol

from .credential_secure_intake import (
    FileOneTimeRequestClaims,
    SecureIntakePlan,
    SecureIntakeWorker,
    WindowsCredentialManagerExactStore,
    create_secure_intake_plan,
)
from .credential_secure_intake_windows import (
    CtypesWindowsNativeFacade,
    WindowsNativeMaskedSecretUI,
    WindowsSecureIntakeError,
    WindowsSecureIntakeNative,
    current_windows_owner_binding,
    derive_windows_fingerprint_key,
    windows_credential_target_prefix,
)
from .credential_secure_registry import (
    ReceiptBackedNotionCredentialBroker,
    SecureCredentialRegistryError,
    StableArchiveFingerprintKeyProvider,
    create_archive_atomic_json_receipt_committer,
    list_secure_credentials,
    persist_duplicate_lifecycle_decision,
)
from .notion_http_adapter import NotionHttpAdapter, NotionHttpAdapterError
from .notion_page_recovery import (
    ArchiveInterprocessRequestPacer,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_MAX_RETRY_DELAY_SECONDS,
    FilesystemRecoveryStorage,
    MAX_UNKNOWN_BLOCK_IDS,
    ProviderRequestPacer,
    execute_recovery,
    plan_recovery,
)


WORKFLOW_PLAN_SCHEMA_VERSION = "wom-credential-workflow-plan/v0.1"
WORKFLOW_RESULT_SCHEMA_VERSION = "wom-credential-workflow-result/v0.1"
PLANNING_OWNER_BINDING = "credential-workflow-non-live-planning-owner"

_HEX_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_FIXED_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{2,127}$")
_CREDENTIAL_ID_RE = re.compile(r"^cred_[A-Za-z0-9_-]{16,96}$")
_SAFE_ARCHIVE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+/-]{0,255}$")

_ADOPTION_APPROVED_EXECUTION_STEPS = (
    "archive_identity_validate",
    "current_windows_owner_bind",
    "archive_scoped_authentication_key_initialize_or_reuse",
    "one_time_request_claim_and_masked_human_secret_prompt",
    "exact_encrypted_store_write",
    "provider_and_reviewed_anchor_verify",
    "authenticated_receipt_commit",
    "authenticated_rediscovery_verify",
)


def _zero_operations() -> dict[str, int]:
    return {
        "native_calls": 0,
        "provider_calls": 0,
        "credential_store_reads": 0,
        "credential_store_writes": 0,
        "archive_writes": 0,
    }


def _authenticated_key_operation_boundary(
    *,
    archive_writes_may_occur: bool,
) -> dict[str, Any]:
    """Describe work honestly once authenticated archive-key access begins.

    ``StableArchiveFingerprintKeyProvider`` intentionally keeps native key
    telemetry inside its callback boundary.  A presence probe or exact key
    read may therefore have happened before either the callback or registry
    operation fails.  Counts at this public boundary are unknown, never zero.
    Lifecycle approval may additionally have published an archive document;
    read-only listing and lifecycle planning cannot do so.
    """

    return {
        "live_operation_boundary": "authenticated_archive_key_access_entered",
        "count_status": "unknown_may_be_nonzero",
        "native_calls": None,
        "provider_calls": 0,
        "credential_store_reads": None,
        "credential_store_writes": 0,
        "archive_writes": None if archive_writes_may_occur else 0,
    }


def _approved_adoption_worker_operations() -> dict[str, Any]:
    """Report the only honest public bound after an approved worker starts.

    The worker deliberately does not export detailed native/provider telemetry:
    such telemetry would be another secret-adjacent IPC surface.  Once the
    approved worker boundary is entered, however, SID lookup, archive-key
    initialization/reuse, request claiming, and the masked UI may already have
    happened even when the human cancels or a later step fails.  ``None`` is
    therefore an intentional JSON ``null`` count, never an implied zero.
    """

    return {
        "live_operation_boundary": "approved_worker_execution_entered",
        "count_status": "unknown_may_be_nonzero",
        "native_calls": None,
        "provider_calls": None,
        "credential_store_reads": None,
        "credential_store_writes": None,
        "archive_writes": None,
    }


def _workflow_failure(
    action: str,
    reason_code: str,
    *,
    accepted: bool = False,
    persisted: bool = False,
    rollback_status: str = "not_required",
    operations: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one fixed, content-free failure result."""

    safe_reason = (
        reason_code
        if isinstance(reason_code, str) and _FIXED_CODE_RE.fullmatch(reason_code)
        else "credential_workflow_failed"
    )
    safe_rollback = (
        rollback_status
        if rollback_status in {"not_required", "deleted", "delete_failed"}
        else "not_required"
    )
    if safe_rollback == "delete_failed":
        operator_action = "stop_and_remove_the_exact_encrypted_store_entry"
    elif accepted and persisted:
        operator_action = "stop_and_repair_authenticated_rediscovery"
    else:
        operator_action = "review_the_fixed_reason_code_before_retry"
    return {
        "schema_version": WORKFLOW_RESULT_SCHEMA_VERSION,
        "ok": False,
        "lifecycle_action": action,
        "accepted": accepted,
        "persisted": persisted,
        "reason_code": safe_reason,
        "rollback_status": safe_rollback,
        # ``persisted: false`` is a transaction outcome, not an independent
        # proof that an OS entry is absent.  Be conservative across child
        # crashes and unknown exceptions: only a confirmed exact-target delete
        # proves absence at this boundary.
        "store_absence_verified": bool(
            not persisted and safe_rollback == "deleted"
        ),
        "operator_action": operator_action,
        "credential_id_present": False,
        "secret_value_present": False,
        "reviewed_anchor_present_in_result": False,
        "backend_target_present": False,
        "crash_or_power_loss_rollback_guaranteed": False,
        "operations": (
            dict(operations) if operations is not None else _zero_operations()
        ),
    }


def _approved_adoption_worker_failure(
    reason_code: str,
    *,
    accepted: bool = False,
    persisted: bool = False,
    rollback_status: str = "not_required",
) -> dict[str, Any]:
    """Build a failure that cannot falsely claim zero work after approval."""

    return _workflow_failure(
        "secure_credential_adoption_execute",
        reason_code,
        accepted=accepted,
        persisted=persisted,
        rollback_status=rollback_status,
        operations=_approved_adoption_worker_operations(),
    )


def _uncertain_adoption_worker_result() -> dict[str, Any]:
    """Return the only honest result after adoption worker state is lost."""

    return {
        "schema_version": WORKFLOW_RESULT_SCHEMA_VERSION,
        "ok": False,
        "lifecycle_action": "secure_credential_adoption_execute",
        "accepted": None,
        "persisted": None,
        "reason_code": "credential_adoption_worker_state_unknown",
        "rollback_status": None,
        "store_absence_verified": False,
        "operator_action": "reconcile_then_rerun_same_approved_command_and_plan",
        "credential_id_present": False,
        "secret_value_present": False,
        "reviewed_anchor_present_in_result": False,
        "backend_target_present": False,
        "crash_or_power_loss_rollback_guaranteed": False,
        "operations": _approved_adoption_worker_operations(),
        "durable_state": "unknown_may_have_changed",
        "worker_result_accepted": False,
    }


def _exception_code(error: BaseException, fallback: str) -> str:
    """Project only a module-owned stable code, never exception text."""

    if isinstance(
        error,
        (SecureCredentialRegistryError, WindowsSecureIntakeError, NotionHttpAdapterError),
    ):
        code = getattr(error, "code", None)
        if isinstance(code, str) and _FIXED_CODE_RE.fullmatch(code):
            return code
    return fallback


def _parse_public_time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("credential_workflow_plan_time_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("credential_workflow_plan_time_invalid") from None
    if parsed.tzinfo is None:
        raise ValueError("credential_workflow_plan_time_invalid")
    return parsed.astimezone(timezone.utc)


def _key_provider(
    native: WindowsSecureIntakeNative,
    selected: StableArchiveFingerprintKeyProvider | None,
) -> StableArchiveFingerprintKeyProvider:
    return selected if selected is not None else StableArchiveFingerprintKeyProvider(native)


def plan_secure_credential_adoption(
    *,
    expected_archive_id: str,
    account_label: str,
    workspace_label: str,
    purpose: str,
    reviewed_anchor_uuid: str,
    requested_capabilities: Sequence[str] = (),
    ttl_seconds: int = 300,
    now: datetime | None = None,
    request_id_factory: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """Create a Notion credential-intake approval contract without live I/O.

    A fixed symbolic owner is used here on purpose: a dry-run must not query the
    live Windows SID.  The approved execution independently binds its private
    worker plan to the current SID after this complete public plan (including
    the hidden anchor through its digest) has been revalidated.
    """

    try:
        if (
            not isinstance(expected_archive_id, str)
            or _SAFE_ARCHIVE_ID_RE.fullmatch(expected_archive_id) is None
        ):
            raise ValueError("credential_adoption_archive_identity_invalid")
        plan = create_secure_intake_plan(
            provider="notion",
            account_label=account_label,
            workspace_label=workspace_label,
            purpose=purpose,
            reviewed_anchor_uuid=reviewed_anchor_uuid,
            owner_binding=PLANNING_OWNER_BINDING,
            requested_capabilities=requested_capabilities,
            ttl_seconds=ttl_seconds,
            now=now,
            request_id_factory=request_id_factory,
        )
    except Exception:
        result = _workflow_failure(
            "secure_credential_adoption_plan",
            "credential_adoption_plan_invalid",
        )
        result["dry_run"] = True
        return result

    return {
        "schema_version": WORKFLOW_PLAN_SCHEMA_VERSION,
        "ok": True,
        "dry_run": True,
        "lifecycle_action": "secure_credential_adoption_plan",
        "reason_code": "credential_adoption_plan_ready",
        "plan_digest": plan.plan_digest,
        "expected_archive_id": expected_archive_id,
        "intake_plan": plan.to_public_dict(),
        "approved_execution_steps": list(_ADOPTION_APPROVED_EXECUTION_STEPS),
        "human_approval_required": True,
        "secret_value_present": False,
        "reviewed_anchor_present_in_result": False,
        "backend_target_present": False,
        "operations": _zero_operations(),
    }


def _rebuild_approved_planning_contract(
    approval_plan: Mapping[str, Any],
    *,
    expected_plan_digest: str,
    expected_archive_id: str,
    reviewed_anchor_uuid: str,
    requested_capabilities: Sequence[str],
) -> SecureIntakePlan:
    if (
        not isinstance(approval_plan, Mapping)
        or approval_plan.get("schema_version") != WORKFLOW_PLAN_SCHEMA_VERSION
        or approval_plan.get("ok") is not True
        or approval_plan.get("dry_run") is not True
        or approval_plan.get("lifecycle_action") != "secure_credential_adoption_plan"
    ):
        raise ValueError("credential_adoption_plan_invalid")
    if approval_plan.get("approved_execution_steps") != list(
        _ADOPTION_APPROVED_EXECUTION_STEPS
    ):
        raise ValueError("credential_adoption_plan_digest_mismatch")
    planned_archive_id = approval_plan.get("expected_archive_id")
    if not (
        isinstance(expected_archive_id, str)
        and _SAFE_ARCHIVE_ID_RE.fullmatch(expected_archive_id) is not None
        and isinstance(planned_archive_id, str)
        and _SAFE_ARCHIVE_ID_RE.fullmatch(planned_archive_id) is not None
        and hmac.compare_digest(expected_archive_id, planned_archive_id)
    ):
        raise ValueError("credential_adoption_plan_digest_mismatch")
    public_plan = approval_plan.get("intake_plan")
    if not isinstance(public_plan, Mapping):
        raise ValueError("credential_adoption_plan_invalid")
    supplied_digest = approval_plan.get("plan_digest")
    nested_digest = public_plan.get("plan_digest")
    if not (
        isinstance(expected_plan_digest, str)
        and _HEX_SHA256_RE.fullmatch(expected_plan_digest)
        and isinstance(supplied_digest, str)
        and isinstance(nested_digest, str)
        and hmac.compare_digest(expected_plan_digest, supplied_digest)
        and hmac.compare_digest(expected_plan_digest, nested_digest)
    ):
        raise ValueError("credential_adoption_plan_digest_mismatch")

    created_at = _parse_public_time(public_plan.get("created_at"))
    ttl_seconds = public_plan.get("ttl_seconds")
    request_id = public_plan.get("request_id")
    if not isinstance(ttl_seconds, int) or isinstance(ttl_seconds, bool):
        raise ValueError("credential_adoption_plan_invalid")
    if not isinstance(request_id, str):
        raise ValueError("credential_adoption_plan_invalid")
    rebuilt = create_secure_intake_plan(
        provider=str(public_plan.get("provider") or ""),
        account_label=str(public_plan.get("account_label") or ""),
        workspace_label=str(public_plan.get("workspace_label") or ""),
        purpose=str(public_plan.get("purpose") or ""),
        reviewed_anchor_uuid=reviewed_anchor_uuid,
        owner_binding=PLANNING_OWNER_BINDING,
        requested_capabilities=requested_capabilities,
        ttl_seconds=ttl_seconds,
        now=created_at,
        request_id_factory=lambda: request_id,
    )
    if rebuilt.to_public_dict() != dict(public_plan):
        raise ValueError("credential_adoption_plan_digest_mismatch")
    if not hmac.compare_digest(rebuilt.plan_digest, expected_plan_digest):
        raise ValueError("credential_adoption_plan_digest_mismatch")
    if rebuilt.provider != "notion":
        raise ValueError("credential_adoption_provider_invalid")
    return rebuilt


@dataclass(frozen=True)
class CredentialAdoptionWorkerInvocation:
    """Pickle-safe, secret-free input sent to the live child process."""

    archive_root: str = field(repr=False)
    approval_plan: Mapping[str, Any] = field(repr=False)
    expected_plan_digest: str
    expected_archive_id: str
    reviewed_anchor_uuid: str = field(repr=False)
    requested_capabilities: tuple[str, ...]

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "archive_root_present": bool(self.archive_root),
            "approval_plan_present": bool(self.approval_plan),
            "expected_plan_digest": self.expected_plan_digest,
            "expected_archive_id": self.expected_archive_id,
            "reviewed_anchor_present": True,
            "requested_capabilities": list(self.requested_capabilities),
            "secret_transport": "child_native_masked_ui_only",
        }


@dataclass(frozen=True, repr=False)
class _CredentialAdoptionWorkerRunOutcome:
    """Parent-owned evidence distinguishing pre-start from post-start failure."""

    worker_started: bool
    result: Mapping[str, Any] | None = field(default=None, repr=False)


class CredentialAdoptionWorkerSpawner(Protocol):
    def run_worker(
        self,
        invocation: CredentialAdoptionWorkerInvocation,
    ) -> Mapping[str, Any] | _CredentialAdoptionWorkerRunOutcome: ...


def _execute_adoption_inside_worker(
    invocation: CredentialAdoptionWorkerInvocation,
    *,
    native: WindowsSecureIntakeNative,
    notion_adapter: NotionHttpAdapter,
    key_provider: StableArchiveFingerprintKeyProvider | None = None,
    now_factory: Callable[[], datetime] | None = None,
    credential_id_factory: Callable[[], str] | None = None,
    backend_id_factory: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """Secret-bearing worker body; never call this from a production parent."""

    action = "secure_credential_adoption_execute"
    try:
        reviewed_plan = _rebuild_approved_planning_contract(
            invocation.approval_plan,
            expected_plan_digest=invocation.expected_plan_digest,
            expected_archive_id=invocation.expected_archive_id,
            reviewed_anchor_uuid=invocation.reviewed_anchor_uuid,
            requested_capabilities=invocation.requested_capabilities,
        )
        archive_projection = list_secure_credentials(invocation.archive_root)
        archive_id = archive_projection["archive_id"]
        if not (
            isinstance(archive_id, str)
            and hmac.compare_digest(archive_id, invocation.expected_archive_id)
        ):
            return _approved_adoption_worker_failure(
                "credential_adoption_archive_identity_mismatch"
            )
        owner_binding = current_windows_owner_binding(native)
        selected_key_provider = _key_provider(native, key_provider)
        actual_plan = create_secure_intake_plan(
            provider=reviewed_plan.provider,
            account_label=reviewed_plan.account_label,
            workspace_label=reviewed_plan.workspace_label,
            purpose=reviewed_plan.purpose,
            reviewed_anchor_uuid=invocation.reviewed_anchor_uuid,
            owner_binding=owner_binding,
            requested_capabilities=invocation.requested_capabilities,
            ttl_seconds=reviewed_plan.ttl_seconds,
            now=_parse_public_time(reviewed_plan.created_at),
            request_id_factory=lambda: reviewed_plan.request_id,
        )
    except Exception:
        return _approved_adoption_worker_failure(
            "credential_adoption_preflight_failed",
        )

    execution_now = now_factory or (lambda: datetime.now(timezone.utc))
    archive_path = Path(invocation.archive_root)

    def run_with_archive_key(key_view: memoryview) -> dict[str, Any]:
        callback_archive_projection = list_secure_credentials(invocation.archive_root)
        callback_archive_id = callback_archive_projection.get("archive_id")
        if not (
            isinstance(callback_archive_id, str)
            and hmac.compare_digest(
                callback_archive_id,
                invocation.expected_archive_id,
            )
        ):
            return _approved_adoption_worker_failure(
                "credential_adoption_archive_identity_mismatch"
            )
        worker_kwargs: dict[str, Any] = {
            "claims": FileOneTimeRequestClaims(
                archive_path / "profiles" / "local" / "credential-intake" / "claims",
                archive_root=archive_path,
                expected_relative_directory=(
                    Path("profiles") / "local" / "credential-intake" / "claims"
                ),
            ),
            "ui": WindowsNativeMaskedSecretUI(native),
            "store": WindowsCredentialManagerExactStore(
                native=native,
                target_prefix=windows_credential_target_prefix(str(archive_id)),
            ),
            "verifier": notion_adapter.secure_intake_verifier(),
            "receipt_committer": create_archive_atomic_json_receipt_committer(
                archive_path,
                expected_archive_id=invocation.expected_archive_id,
                receipt_authentication_key=key_view,
            ),
            "fingerprint_key": derive_windows_fingerprint_key(
                key_view,
                owner_binding,
            ),
            "now_factory": execution_now,
        }
        if credential_id_factory is not None:
            worker_kwargs["credential_id_factory"] = credential_id_factory
        if backend_id_factory is not None:
            worker_kwargs["backend_id_factory"] = backend_id_factory
        worker = SecureIntakeWorker(**worker_kwargs)
        raw_result = worker.execute(
            actual_plan,
            expected_plan_digest=actual_plan.plan_digest,
            current_owner_binding=owner_binding,
        )
        if raw_result.get("ok") is not True:
            reason = raw_result.get("reason_code")
            rollback_status = raw_result.get("rollback_status")
            return _approved_adoption_worker_failure(
                reason if isinstance(reason, str) else "credential_adoption_failed",
                rollback_status=(
                    rollback_status
                    if isinstance(rollback_status, str)
                    else "not_required"
                ),
            )

        credential_id = raw_result.get("credential_id")
        authenticated = list_secure_credentials(
            archive_path,
            receipt_authentication_key=key_view,
        )
        if not (
            isinstance(authenticated.get("archive_id"), str)
            and hmac.compare_digest(
                authenticated["archive_id"], invocation.expected_archive_id
            )
        ):
            return _approved_adoption_worker_failure(
                "credential_adoption_archive_identity_changed",
                accepted=True,
                persisted=True,
            )
        matches = [
            row
            for row in authenticated.get("credentials", [])
            if isinstance(row, Mapping) and row.get("credential_id") == credential_id
        ]
        if len(matches) != 1 or matches[0].get("receipt_authentication_status") != "valid":
            return _approved_adoption_worker_failure(
                "credential_adoption_rediscovery_verification_failed",
                accepted=True,
                persisted=True,
            )
        safe_credential = dict(matches[0])
        return {
            "schema_version": WORKFLOW_RESULT_SCHEMA_VERSION,
            "ok": True,
            "lifecycle_action": action,
            "accepted": True,
            "persisted": True,
            "reason_code": "credential_adoption_persisted_and_rediscoverable",
            "credential_id": str(safe_credential["credential_id"]),
            "authenticated_rediscovery_verified": True,
            "human_default_decision_required": not bool(
                safe_credential.get("broker_authoritative")
            ),
            "secret_value_present": False,
            "reviewed_anchor_present_in_result": False,
            "backend_target_present": False,
            "crash_or_power_loss_rollback_guaranteed": False,
            "operations": _approved_adoption_worker_operations(),
        }

    try:
        result = selected_key_provider.use_key(
            archive_path,
            run_with_archive_key,
            create_if_missing=True,
        )
        if not isinstance(result, dict):
            return _uncertain_adoption_worker_result()
        return result
    except Exception:
        return _uncertain_adoption_worker_result()


@dataclass(repr=False)
class InjectedCredentialAdoptionWorkerSpawner:
    """Test/embedding seam whose caller supplies an already isolated worker.

    Production callers must use :class:`SpawnCredentialAdoptionWorkerSpawner`.
    This adapter exists so unit tests can prove the complete transaction using
    synthetic native/provider objects without touching Windows or the network.
    """

    native: WindowsSecureIntakeNative = field(repr=False)
    notion_adapter: NotionHttpAdapter = field(repr=False)
    key_provider: StableArchiveFingerprintKeyProvider | None = field(
        default=None, repr=False
    )
    now_factory: Callable[[], datetime] | None = field(default=None, repr=False)
    credential_id_factory: Callable[[], str] | None = field(default=None, repr=False)
    backend_id_factory: Callable[[], str] | None = field(default=None, repr=False)

    def run_worker(
        self,
        invocation: CredentialAdoptionWorkerInvocation,
    ) -> _CredentialAdoptionWorkerRunOutcome:
        return _CredentialAdoptionWorkerRunOutcome(
            worker_started=True,
            result=_execute_adoption_inside_worker(
                invocation,
                native=self.native,
                notion_adapter=self.notion_adapter,
                key_provider=self.key_provider,
                now_factory=self.now_factory,
                credential_id_factory=self.credential_id_factory,
                backend_id_factory=self.backend_id_factory,
            ),
        )


def _adoption_worker_transport_marker() -> dict[str, str]:
    """Return a fixed child transport marker with no transaction assertions."""

    return {"worker_transport_status": "result_unavailable"}


def _spawned_adoption_entry(
    send_connection: Any,
    invocation: CredentialAdoptionWorkerInvocation,
) -> None:
    """Top-level Windows-spawn entry; sends only a sanitized status mapping."""

    try:
        native = CtypesWindowsNativeFacade(cli_live_approved=True)
        result = _execute_adoption_inside_worker(
            invocation,
            native=native,
            notion_adapter=NotionHttpAdapter(
                request_pacer=ArchiveInterprocessRequestPacer(
                    invocation.archive_root
                ),
                max_attempts=5,
            ),
            key_provider=StableArchiveFingerprintKeyProvider(native),
        )
    except Exception:
        result = _adoption_worker_transport_marker()
    try:
        send_connection.send(result)
    except Exception:
        pass
    finally:
        try:
            send_connection.close()
        except Exception:
            pass


@dataclass(repr=False)
class SpawnCredentialAdoptionWorkerSpawner:
    """Concrete production seam using a fresh ``multiprocessing.spawn`` child.

    The parent deliberately has no timeout/terminate path.  Python documents
    that terminating a process can interrupt ``finally`` blocks and corrupt
    pipes/locks; here it could also skip the worker's exact-target rollback.
    A human must finish or cancel the native dialog.  Process crash and power
    loss remain an explicitly reported durability gap.
    """

    def run_worker(
        self,
        invocation: CredentialAdoptionWorkerInvocation,
    ) -> _CredentialAdoptionWorkerRunOutcome:
        process: Any = None
        receive_connection: Any = None
        send_connection: Any = None
        worker_started = False
        try:
            context = multiprocessing.get_context("spawn")
            receive_connection, send_connection = context.Pipe(duplex=False)
            process = context.Process(
                target=_spawned_adoption_entry,
                args=(send_connection, invocation),
                daemon=False,
            )
            process.start()
            worker_started = True
            send_connection.close()
            try:
                result = receive_connection.recv()
            except Exception:
                result = _adoption_worker_transport_marker()
            process.join()
            if process.exitcode != 0 or not isinstance(result, Mapping):
                return _CredentialAdoptionWorkerRunOutcome(worker_started=True)
            return _CredentialAdoptionWorkerRunOutcome(
                worker_started=True,
                result=result,
            )
        except Exception:
            # Never force-terminate a started intake child: it owns the only
            # secret buffer and must retain the opportunity to run rollback.
            if worker_started and process is not None and process.is_alive():
                process.join()
            return _CredentialAdoptionWorkerRunOutcome(
                worker_started=worker_started,
            )
        finally:
            try:
                if receive_connection is not None:
                    receive_connection.close()
            except Exception:
                pass
            try:
                if send_connection is not None:
                    send_connection.close()
            except Exception:
                pass


_ADOPTION_WORKER_SUCCESS_KEYS = {
    "schema_version",
    "ok",
    "lifecycle_action",
    "accepted",
    "persisted",
    "reason_code",
    "credential_id",
    "authenticated_rediscovery_verified",
    "human_default_decision_required",
    "secret_value_present",
    "reviewed_anchor_present_in_result",
    "backend_target_present",
    "crash_or_power_loss_rollback_guaranteed",
    "operations",
}
_ADOPTION_WORKER_FAILURE_KEYS = {
    "schema_version",
    "ok",
    "lifecycle_action",
    "accepted",
    "persisted",
    "reason_code",
    "rollback_status",
    "store_absence_verified",
    "operator_action",
    "credential_id_present",
    "secret_value_present",
    "reviewed_anchor_present_in_result",
    "backend_target_present",
    "crash_or_power_loss_rollback_guaranteed",
    "operations",
}
_ADOPTION_WORKER_FAILURE_REASONS = {
    "human_cancelled",
    "secret_input_unavailable",
    "store_write_failed",
    "store_presence_not_verified",
    "provider_identity_unverified",
    "workspace_anchor_mismatch",
    "receipt_commit_failed",
    "request_expired",
    "request_replayed",
    "request_user_mismatch",
    "request_claim_failed",
    "plan_digest_mismatch",
    "worker_launch_failed",
    "worker_result_invalid",
    "credential_adoption_archive_identity_mismatch",
    "credential_adoption_archive_identity_changed",
    "credential_adoption_preflight_failed",
    "credential_adoption_rediscovery_verification_failed",
}
_ADOPTION_PERSISTED_FAILURE_REASONS = {
    "credential_adoption_archive_identity_changed",
    "credential_adoption_rediscovery_verification_failed",
}


def _project_adoption_worker_result_unchecked(
    result: Mapping[str, Any],
) -> dict[str, Any]:
    """Strictly reconstruct the only status shapes allowed across the pipe."""

    action = "secure_credential_adoption_execute"
    keys = set(result)
    if result.get("ok") is True:
        credential_id = result.get("credential_id")
        expected_success = {
            "schema_version": WORKFLOW_RESULT_SCHEMA_VERSION,
            "ok": True,
            "lifecycle_action": action,
            "accepted": True,
            "persisted": True,
            "reason_code": "credential_adoption_persisted_and_rediscoverable",
            "credential_id": credential_id,
            "authenticated_rediscovery_verified": True,
            "human_default_decision_required": result.get(
                "human_default_decision_required"
            ),
            "secret_value_present": False,
            "reviewed_anchor_present_in_result": False,
            "backend_target_present": False,
            "crash_or_power_loss_rollback_guaranteed": False,
            "operations": _approved_adoption_worker_operations(),
        }
        if not (
            keys == _ADOPTION_WORKER_SUCCESS_KEYS
            and result.get("schema_version") == WORKFLOW_RESULT_SCHEMA_VERSION
            and result.get("lifecycle_action") == action
            and result.get("accepted") is True
            and result.get("persisted") is True
            and result.get("reason_code")
            == "credential_adoption_persisted_and_rediscoverable"
            and isinstance(credential_id, str)
            and _CREDENTIAL_ID_RE.fullmatch(credential_id)
            and result.get("authenticated_rediscovery_verified") is True
            and isinstance(result.get("human_default_decision_required"), bool)
            and result.get("secret_value_present") is False
            and result.get("reviewed_anchor_present_in_result") is False
            and result.get("backend_target_present") is False
            and result.get("crash_or_power_loss_rollback_guaranteed") is False
            and result.get("operations") == _approved_adoption_worker_operations()
            and dict(result) == expected_success
        ):
            return _uncertain_adoption_worker_result()
        return expected_success
    if keys != _ADOPTION_WORKER_FAILURE_KEYS:
        return _uncertain_adoption_worker_result()
    reason = result.get("reason_code")
    rollback = result.get("rollback_status")
    expected_persisted = (
        isinstance(reason, str)
        and reason in _ADOPTION_PERSISTED_FAILURE_REASONS
    )
    if not (
        result.get("schema_version") == WORKFLOW_RESULT_SCHEMA_VERSION
        and result.get("lifecycle_action") == action
        and result.get("ok") is False
        and isinstance(result.get("accepted"), bool)
        and isinstance(result.get("persisted"), bool)
        and result.get("accepted") is expected_persisted
        and result.get("persisted") is expected_persisted
        and isinstance(reason, str)
        and reason in _ADOPTION_WORKER_FAILURE_REASONS
        and rollback in {"not_required", "deleted", "delete_failed"}
        and result.get("credential_id_present") is False
        and result.get("secret_value_present") is False
        and result.get("reviewed_anchor_present_in_result") is False
        and result.get("backend_target_present") is False
        and result.get("crash_or_power_loss_rollback_guaranteed") is False
        and isinstance(result.get("operations"), Mapping)
        and result.get("operations") == _approved_adoption_worker_operations()
    ):
        return _uncertain_adoption_worker_result()
    expected_failure = _approved_adoption_worker_failure(
        reason,
        accepted=result["accepted"],
        persisted=result["persisted"],
        rollback_status=rollback,
    )
    if dict(result) != expected_failure:
        return _uncertain_adoption_worker_result()
    return expected_failure


def _project_adoption_worker_result(result: Mapping[str, Any]) -> dict[str, Any]:
    """Reject malformed or exception-raising child mappings as unknown state."""

    try:
        return _project_adoption_worker_result_unchecked(result)
    except Exception:
        return _uncertain_adoption_worker_result()


def execute_windows_notion_credential_adoption(
    archive_root: Path | str,
    approval_plan: Mapping[str, Any],
    *,
    expected_plan_digest: str,
    expected_archive_id: str,
    reviewed_anchor_uuid: str,
    requested_capabilities: Sequence[str],
    approved: bool,
    worker_spawner: CredentialAdoptionWorkerSpawner | None = None,
) -> dict[str, Any]:
    """Launch the Windows UI -> store -> Notion -> receipt child transaction.

    ``approved=False`` returns before inspecting the plan, archive, native
    object, child process, credential store, or Notion adapter.  Plan
    reconstruction catches every changed public field, the digest-bound hidden
    anchor, and the separately reviewed archive identity before the child is
    spawned.  The child rechecks that identity before SID/key/UI work and at
    the archive-key callback boundary.  The production default is a real
    ``spawn`` process; raw secret bytes exist only in that child.
    """

    action = "secure_credential_adoption_execute"
    if approved is not True:
        return _workflow_failure(action, "credential_adoption_approval_required")
    try:
        _rebuild_approved_planning_contract(
            approval_plan,
            expected_plan_digest=expected_plan_digest,
            expected_archive_id=expected_archive_id,
            reviewed_anchor_uuid=reviewed_anchor_uuid,
            requested_capabilities=requested_capabilities,
        )
    except Exception:
        return _workflow_failure(action, "credential_adoption_plan_digest_mismatch")

    try:
        invocation = CredentialAdoptionWorkerInvocation(
            archive_root=str(Path(archive_root).resolve()),
            approval_plan=dict(approval_plan),
            expected_plan_digest=expected_plan_digest,
            expected_archive_id=expected_archive_id,
            reviewed_anchor_uuid=reviewed_anchor_uuid,
            requested_capabilities=tuple(requested_capabilities),
        )
    except Exception:
        return _workflow_failure(action, "credential_adoption_archive_root_invalid")
    selected_spawner = worker_spawner or SpawnCredentialAdoptionWorkerSpawner()
    try:
        run_outcome = selected_spawner.run_worker(invocation)
    except Exception:
        return _uncertain_adoption_worker_result()
    if isinstance(run_outcome, _CredentialAdoptionWorkerRunOutcome):
        if run_outcome.worker_started is not True:
            return _workflow_failure(
                action,
                "credential_adoption_worker_launch_failed",
            )
        result = run_outcome.result
    else:
        # A backward-compatible bare mapping has crossed its injected worker
        # boundary, so malformed output can no longer imply exact zero state.
        result = run_outcome
    if not isinstance(result, Mapping):
        return _uncertain_adoption_worker_result()
    return _project_adoption_worker_result(result)


def list_authenticated_secure_credentials(
    archive_root: Path | str,
    *,
    native: WindowsSecureIntakeNative,
    key_provider: StableArchiveFingerprintKeyProvider | None = None,
) -> dict[str, Any]:
    """Rediscover authenticated credentials without creating missing state."""

    action = "authenticated_secure_credential_list"
    selected = _key_provider(native, key_provider)
    operations = _authenticated_key_operation_boundary(
        archive_writes_may_occur=False,
    )
    try:
        result = selected.use_key(
            archive_root,
            lambda key: list_secure_credentials(
                archive_root,
                receipt_authentication_key=key,
            ),
            create_if_missing=False,
        )
        if not isinstance(result, dict):
            return _workflow_failure(
                action,
                "credential_registry_result_invalid",
                operations=operations,
            )
        projected = dict(result)
        projected["lifecycle_action"] = action
        projected["reason_code"] = "authenticated_secure_credentials_listed"
        projected["operations"] = operations
        return projected
    except Exception as exc:
        return _workflow_failure(
            action,
            _exception_code(exc, "credential_registry_unavailable"),
            operations=operations,
        )


def decide_authenticated_credential_lifecycle(
    archive_root: Path | str,
    *,
    provider: str,
    workspace_fingerprint: str,
    selected_default_credential_id: str | None,
    revocation_pending_credential_ids: Sequence[str] = (),
    approved: bool,
    expected_plan_sha256: str | None = None,
    reviewed_by: str | None = None,
    native: WindowsSecureIntakeNative,
    key_provider: StableArchiveFingerprintKeyProvider | None = None,
) -> dict[str, Any]:
    """Plan or persist the authenticated default/legacy lifecycle decision."""

    action = "authenticated_credential_lifecycle_decision"
    selected = _key_provider(native, key_provider)
    operations = _authenticated_key_operation_boundary(
        archive_writes_may_occur=approved is True,
    )

    def decide(key_view: memoryview) -> dict[str, Any]:
        return persist_duplicate_lifecycle_decision(
            archive_root,
            provider=provider,
            workspace_fingerprint=workspace_fingerprint,
            selected_default_credential_id=selected_default_credential_id,
            revocation_pending_credential_ids=revocation_pending_credential_ids,
            human_approved=approved is True,
            receipt_authentication_key=key_view,
            expected_plan_sha256=expected_plan_sha256,
            reviewed_by=reviewed_by,
        )

    try:
        result = selected.use_key(
            archive_root,
            decide,
            create_if_missing=False,
        )
        if not isinstance(result, dict):
            return _workflow_failure(
                action,
                "credential_lifecycle_result_invalid",
                operations=operations,
            )
        projected = dict(result)
        projected["lifecycle_action"] = action
        projected["secret_value_present"] = False
        projected["backend_target_present"] = False
        projected["operations"] = operations
        return projected
    except Exception as exc:
        return _workflow_failure(
            action,
            _exception_code(exc, "credential_lifecycle_decision_failed"),
            operations=operations,
        )


def plan_authenticated_credential_lifecycle(
    archive_root: Path | str,
    *,
    provider: str,
    workspace_fingerprint: str,
    selected_default_credential_id: str | None,
    revocation_pending_credential_ids: Sequence[str] = (),
    native: WindowsSecureIntakeNative,
    key_provider: StableArchiveFingerprintKeyProvider | None = None,
) -> dict[str, Any]:
    """Convenience wrapper that can never persist a lifecycle decision."""

    return decide_authenticated_credential_lifecycle(
        archive_root,
        provider=provider,
        workspace_fingerprint=workspace_fingerprint,
        selected_default_credential_id=selected_default_credential_id,
        revocation_pending_credential_ids=revocation_pending_credential_ids,
        approved=False,
        expected_plan_sha256=None,
        reviewed_by=None,
        native=native,
        key_provider=key_provider,
    )


def approve_authenticated_credential_lifecycle(
    archive_root: Path | str,
    *,
    provider: str,
    workspace_fingerprint: str,
    selected_default_credential_id: str,
    expected_plan_sha256: str,
    reviewed_by: str,
    revocation_pending_credential_ids: Sequence[str] = (),
    native: WindowsSecureIntakeNative,
    key_provider: StableArchiveFingerprintKeyProvider | None = None,
) -> dict[str, Any]:
    """Convenience wrapper for one explicitly approved unchanged decision."""

    return decide_authenticated_credential_lifecycle(
        archive_root,
        provider=provider,
        workspace_fingerprint=workspace_fingerprint,
        selected_default_credential_id=selected_default_credential_id,
        revocation_pending_credential_ids=revocation_pending_credential_ids,
        approved=True,
        expected_plan_sha256=expected_plan_sha256,
        reviewed_by=reviewed_by,
        native=native,
        key_provider=key_provider,
    )


class _NeverCredentialBroker:
    def resolve(self, _scope_binding: object) -> object:
        raise RuntimeError("unexpected_credential_resolution")


class _NeverNotionProvider:
    def retrieve_page(self, *_args: Any, **_kwargs: Any) -> object:
        raise RuntimeError("unexpected_provider_call")

    def retrieve_page_as_markdown(self, *_args: Any, **_kwargs: Any) -> object:
        raise RuntimeError("unexpected_provider_call")


class _NeverWindowsNative:
    """Replay-only sentinel proving that no Windows call is reachable."""

    def __getattr__(self, _name: str) -> Any:
        raise RuntimeError("unexpected_native_call")


def execute_authenticated_notion_page_recovery(
    archive_root: Path | str,
    manifest: Mapping[str, Any],
    *,
    expected_plan_sha256: str,
    reviewed_by: str,
    max_items: int,
    approved: bool,
    native: WindowsSecureIntakeNative,
    notion_adapter: NotionHttpAdapter | None = None,
    key_provider: StableArchiveFingerprintKeyProvider | None = None,
    offset: int = 0,
    storage: FilesystemRecoveryStorage | None = None,
    request_pacer: ProviderRequestPacer | Callable[[], None] | None = None,
    sleep: Callable[[float], None] | None = None,
    jitter: Callable[[], float] | None = None,
    clock: Callable[[], datetime] | None = None,
    max_attempts: int = 5,
    max_retry_delay_seconds: float = 60.0,
) -> dict[str, Any]:
    """Execute one exact authenticated recovery request inside the key scope."""

    action = "authenticated_notion_page_recovery_execute"
    if approved is not True:
        return _workflow_failure(action, "notion_page_recovery_approval_required")
    if not isinstance(manifest, Mapping):
        return _workflow_failure(action, "notion_page_recovery_manifest_invalid")
    try:
        archive_projection = list_secure_credentials(archive_root)
    except Exception:
        return _workflow_failure(action, "notion_page_recovery_archive_unavailable")
    if manifest.get("archive_id") != archive_projection.get("archive_id"):
        return _workflow_failure(
            action, "notion_page_recovery_archive_identity_mismatch"
        )

    try:
        preview = plan_recovery(
            archive_root,
            manifest,
            max_items=max_items,
            offset=offset,
            storage=storage,
        )
    except Exception:
        return _workflow_failure(action, "notion_page_recovery_plan_failed")
    if preview.get("ok") is not True:
        return _workflow_failure(action, "notion_page_recovery_manifest_invalid")
    actual_plan_sha256 = preview.get("plan_sha256")
    if not (
        isinstance(expected_plan_sha256, str)
        and _SHA256_RE.fullmatch(expected_plan_sha256)
        and isinstance(actual_plan_sha256, str)
        and hmac.compare_digest(expected_plan_sha256, actual_plan_sha256)
    ):
        return _workflow_failure(action, "expected_plan_sha256_mismatch")

    execute_kwargs: dict[str, Any] = {
        "expected_plan_sha256": expected_plan_sha256,
        "reviewed_by": reviewed_by,
        "max_items": max_items,
        "offset": offset,
        "storage": storage,
        "request_pacer": request_pacer,
        "max_attempts": max_attempts,
        "max_retry_delay_seconds": max_retry_delay_seconds,
    }
    if sleep is not None:
        execute_kwargs["sleep"] = sleep
    if jitter is not None:
        execute_kwargs["jitter"] = jitter
    if clock is not None:
        execute_kwargs["clock"] = clock

    pending = preview.get("counts", {}).get("provider_pending_count")
    if pending == 0:
        # Replayed objects are already content-hash verified by plan_recovery.
        # A never-provider/never-broker closes the TOCTOU boundary: if that
        # state changes, execution blocks instead of silently becoming live.
        return execute_recovery(
            archive_root,
            manifest,
            provider=_NeverNotionProvider(),
            credential_broker=_NeverCredentialBroker(),
            **execute_kwargs,
        )

    selected = _key_provider(native, key_provider)
    provider = notion_adapter if notion_adapter is not None else NotionHttpAdapter()

    def recover_with_archive_key(key_view: memoryview) -> dict[str, Any]:
        owner_binding = current_windows_owner_binding(native)
        fingerprint_key = derive_windows_fingerprint_key(key_view, owner_binding)
        try:
            broker = ReceiptBackedNotionCredentialBroker(
                archive_root=archive_root,
                native=native,
                receipt_authentication_key=key_view,
                secret_fingerprint_key=fingerprint_key,
            )
            return execute_recovery(
                archive_root,
                manifest,
                provider=provider,
                credential_broker=broker,
                **execute_kwargs,
            )
        finally:
            for index in range(len(fingerprint_key)):
                fingerprint_key[index] = 0

    try:
        result = selected.use_key(
            archive_root,
            recover_with_archive_key,
            create_if_missing=False,
        )
        if not isinstance(result, dict):
            return _workflow_failure(action, "notion_page_recovery_result_invalid")
        return result
    except Exception as exc:
        return _workflow_failure(
            action,
            _exception_code(exc, "notion_page_recovery_execution_failed"),
        )


@dataclass(frozen=True)
class NotionRecoveryWorkerInvocation:
    """Pickle-safe, secret-free request sent to a recovery child process."""

    archive_root: str = field(repr=False)
    manifest: Mapping[str, Any] = field(repr=False)
    expected_plan_sha256: str
    reviewed_by: str = field(repr=False)
    max_items: int
    offset: int


class NotionRecoveryWorkerSpawner(Protocol):
    def run_worker(
        self,
        invocation: NotionRecoveryWorkerInvocation,
    ) -> Mapping[str, Any] | _NotionRecoveryWorkerRunOutcome: ...


@dataclass(frozen=True, repr=False)
class _NotionRecoveryWorkerRunOutcome:
    """Parent-owned evidence distinguishing pre-start from post-start failure."""

    worker_started: bool
    result: Mapping[str, Any] | None = field(default=None, repr=False)


@dataclass(repr=False)
class InjectedNotionRecoveryWorkerSpawner:
    """Synthetic-only seam for exercising the child composition in tests."""

    native: WindowsSecureIntakeNative = field(repr=False)
    notion_adapter: NotionHttpAdapter = field(repr=False)
    key_provider: StableArchiveFingerprintKeyProvider | None = field(
        default=None, repr=False
    )
    storage: FilesystemRecoveryStorage | None = field(default=None, repr=False)
    request_pacer: ProviderRequestPacer | Callable[[], None] | None = field(
        default=None, repr=False
    )
    sleep: Callable[[float], None] | None = field(default=None, repr=False)
    jitter: Callable[[], float] | None = field(default=None, repr=False)
    clock: Callable[[], datetime] | None = field(default=None, repr=False)

    def run_worker(
        self,
        invocation: NotionRecoveryWorkerInvocation,
    ) -> _NotionRecoveryWorkerRunOutcome:
        return _NotionRecoveryWorkerRunOutcome(
            worker_started=True,
            result=execute_authenticated_notion_page_recovery(
                invocation.archive_root,
                invocation.manifest,
                expected_plan_sha256=invocation.expected_plan_sha256,
                reviewed_by=invocation.reviewed_by,
                max_items=invocation.max_items,
                offset=invocation.offset,
                approved=True,
                native=self.native,
                notion_adapter=self.notion_adapter,
                key_provider=self.key_provider,
                storage=self.storage,
                request_pacer=self.request_pacer,
                sleep=self.sleep,
                jitter=self.jitter,
                clock=self.clock,
            ),
        )


def _recovery_worker_transport_marker() -> dict[str, str]:
    """Return a fixed internal marker with no false operation assertions."""

    return {"worker_transport_status": "result_unavailable"}


def _spawned_recovery_entry(
    send_connection: Any,
    invocation: NotionRecoveryWorkerInvocation,
) -> None:
    """Top-level spawn entry; the live bearer exists only in this process."""

    try:
        native = CtypesWindowsNativeFacade(cli_live_approved=True)
        result = execute_authenticated_notion_page_recovery(
            invocation.archive_root,
            invocation.manifest,
            expected_plan_sha256=invocation.expected_plan_sha256,
            reviewed_by=invocation.reviewed_by,
            max_items=invocation.max_items,
            offset=invocation.offset,
            approved=True,
            native=native,
            notion_adapter=NotionHttpAdapter(),
            key_provider=StableArchiveFingerprintKeyProvider(native),
        )
    except Exception:
        result = _recovery_worker_transport_marker()
    try:
        send_connection.send(result)
    except Exception:
        pass
    finally:
        try:
            send_connection.close()
        except Exception:
            pass


@dataclass(repr=False)
class SpawnNotionRecoveryWorkerSpawner:
    """Production recovery boundary using a fresh Windows spawn child."""

    def run_worker(
        self,
        invocation: NotionRecoveryWorkerInvocation,
    ) -> _NotionRecoveryWorkerRunOutcome:
        process: Any = None
        receive_connection: Any = None
        send_connection: Any = None
        worker_started = False
        try:
            context = multiprocessing.get_context("spawn")
            receive_connection, send_connection = context.Pipe(duplex=False)
            process = context.Process(
                target=_spawned_recovery_entry,
                args=(send_connection, invocation),
                daemon=False,
            )
            process.start()
            worker_started = True
            send_connection.close()
            try:
                result = receive_connection.recv()
            except Exception:
                result = _recovery_worker_transport_marker()
            process.join()
            if process.exitcode != 0 or not isinstance(result, Mapping):
                return _NotionRecoveryWorkerRunOutcome(worker_started=True)
            return _NotionRecoveryWorkerRunOutcome(
                worker_started=True,
                result=result,
            )
        except Exception:
            if worker_started and process is not None and process.is_alive():
                process.join()
            return _NotionRecoveryWorkerRunOutcome(
                worker_started=worker_started,
            )
        finally:
            try:
                if receive_connection is not None:
                    receive_connection.close()
            except Exception:
                pass
            try:
                if send_connection is not None:
                    send_connection.close()
            except Exception:
                pass


_RECOVERY_RESULT_KEYS = {
    "ok",
    "dry_run",
    "lifecycle_action",
    "status_class",
    "reason_code",
    "request_sha256",
    "plan_sha256",
    "counts",
    "operations",
    "receipt_created",
    "privacy_guards",
    "blockers",
}
_RECOVERY_COUNT_KEYS = {
    "input_item_count",
    "selected_item_count",
    "processed_item_count",
    "pending_item_count",
    "unselected_item_count",
    "replayed_recovered_count",
    "outcomes",
    "total_accounted_count",
}
_RECOVERY_OUTCOMES = {
    "recovered",
    "deleted",
    "forbidden",
    "not_found_or_not_shared",
    "retryable_error",
    "partial",
}
_RECOVERY_OPERATION_KEYS = {
    "provider_calls",
    "paced_request_count",
    "credential_resolution_attempts",
    "credential_reads",
    "retry_count",
    "sleep_seconds",
    "objects_created",
    "manifest_rows_created",
    "projection_rows_created",
    "resume_rows_created",
}

_RECOVERY_PRIVACY_GUARDS = {
    "token_echoed": False,
    "provider_body_echoed": False,
    "page_title_echoed": False,
    "email_echoed": False,
    "provider_url_echoed": False,
    "raw_cursor_echoed": False,
    "raw_cursor_persisted": False,
    "rate_limiter_clock_echoed": False,
}
_RECOVERY_REASON_BY_STATUS = {
    "written": "notion_page_recovery_written",
    "no_change": "notion_page_recovery_replayed",
    "partial": "notion_page_recovery_partial",
    "blocked": "notion_page_recovery_blocked",
}
_RECOVERY_STORAGE_BLOCKERS = {
    "atomic_create_unavailable",
    "archive_root_invalid",
    "archive_root_missing",
    "empty_recovery_payload",
    "content_address_collision",
    "invalid_outcome",
    "digest_invalid",
    "clock_failed",
    "clock_invalid",
    "recovery_storage_error",
    "recovery_authority_conflict",
    "private_state_read_failed",
    "private_state_invalid",
    "archive_path_unsafe",
    "plan_lock_failed",
    "notion_page_recovery_archive_identity_changed",
    "durable_write_failed",
    "durable_write_verification_failed",
}
_RECOVERY_EXECUTION_BLOCKERS = _RECOVERY_STORAGE_BLOCKERS | {
    "credential_resolution_failed",
    "credential_authority_changed",
    "batch_credential_unauthorized",
    "recovery_execution_failed",
    "credential_close_failed",
    "count_invariant_failed",
    "receipt_write_failed",
}


@dataclass(frozen=True)
class _RecoveryProjectionContract:
    """Trusted parent preview values that a child may never redefine."""

    request_sha256: str
    plan_sha256: str
    group_count: int
    input_item_count: int
    selected_item_count: int
    unselected_item_count: int
    recovered_verified_count: int
    provider_pending_count: int


def _build_recovery_projection_contract(
    preview: Mapping[str, Any],
    *,
    expected_plan_sha256: str,
) -> _RecoveryProjectionContract:
    if (
        preview.get("ok") is not True
        or preview.get("dry_run") is not True
        or preview.get("lifecycle_action") != "notion_page_recovery_plan"
        or preview.get("reason_code") != "notion_page_recovery_plan_ready"
        or preview.get("blockers") != []
        or preview.get("privacy_guards") != _RECOVERY_PRIVACY_GUARDS
    ):
        raise ValueError("notion_page_recovery_preview_invalid")
    request_sha256 = preview.get("request_sha256")
    plan_sha256 = preview.get("plan_sha256")
    if not (
        isinstance(request_sha256, str)
        and _SHA256_RE.fullmatch(request_sha256) is not None
        and isinstance(plan_sha256, str)
        and _SHA256_RE.fullmatch(plan_sha256) is not None
        and isinstance(expected_plan_sha256, str)
        and hmac.compare_digest(plan_sha256, expected_plan_sha256)
    ):
        raise ValueError("notion_page_recovery_preview_invalid")
    counts = preview.get("counts")
    expected_count_keys = {
        "group_count",
        "input_item_count",
        "selected_item_count",
        "unselected_item_count",
        "recovered_verified_count",
        "provider_pending_count",
    }
    if not isinstance(counts, Mapping) or set(counts) != expected_count_keys:
        raise ValueError("notion_page_recovery_preview_invalid")
    if any(
        not isinstance(counts.get(name), int)
        or isinstance(counts.get(name), bool)
        or counts[name] < 0
        for name in expected_count_keys
    ):
        raise ValueError("notion_page_recovery_preview_invalid")
    if not (
        counts["group_count"] >= 1
        and counts["input_item_count"]
        == counts["selected_item_count"] + counts["unselected_item_count"]
        and counts["selected_item_count"]
        == counts["recovered_verified_count"] + counts["provider_pending_count"]
    ):
        raise ValueError("notion_page_recovery_preview_invalid")
    return _RecoveryProjectionContract(
        request_sha256=request_sha256,
        plan_sha256=plan_sha256,
        group_count=counts["group_count"],
        input_item_count=counts["input_item_count"],
        selected_item_count=counts["selected_item_count"],
        unselected_item_count=counts["unselected_item_count"],
        recovered_verified_count=counts["recovered_verified_count"],
        provider_pending_count=counts["provider_pending_count"],
    )


def _uncertain_recovery_worker_result(
    contract: _RecoveryProjectionContract,
) -> dict[str, Any]:
    """Project one fixed recovery state after an untrusted worker boundary.

    The child may have durably committed an object or ledger row before a pipe
    failure.  Unknown counts are JSON nulls; this result never converts that
    uncertainty into an all-zero claim.
    """

    return {
        "ok": False,
        "dry_run": False,
        "lifecycle_action": "notion_page_recovery_execute",
        "status_class": "blocked",
        "reason_code": "notion_page_recovery_worker_state_unknown",
        "request_sha256": contract.request_sha256,
        "plan_sha256": contract.plan_sha256,
        "counts": {
            "input_item_count": contract.input_item_count,
            "selected_item_count": contract.selected_item_count,
            "processed_item_count": None,
            "pending_item_count": None,
            "unselected_item_count": contract.unselected_item_count,
            "replayed_recovered_count": None,
            "outcomes": {name: None for name in sorted(_RECOVERY_OUTCOMES)},
            "total_accounted_count": None,
        },
        "operations": {
            "live_operation_boundary": "approved_recovery_worker_may_have_started",
            "count_status": "unknown_may_be_nonzero",
            **{name: None for name in sorted(_RECOVERY_OPERATION_KEYS)},
        },
        "receipt_created": None,
        "privacy_guards": dict(_RECOVERY_PRIVACY_GUARDS),
        "blockers": ["notion_page_recovery_worker_state_unknown"],
        "durable_state": "unknown_may_have_changed",
        "operator_action": "reconcile_and_rerun_same_approved_plan",
        "worker_result_accepted": False,
    }


def _project_recovery_worker_result(
    result: Mapping[str, Any],
    *,
    contract: _RecoveryProjectionContract,
) -> dict[str, Any]:
    """Rebuild only parent-bound aggregate fields allowed across IPC."""

    try:
        if set(result) != _RECOVERY_RESULT_KEYS:
            raise ValueError
        status_class = result.get("status_class")
        reason_code = result.get("reason_code")
        if (
            not isinstance(result.get("ok"), bool)
            or result.get("dry_run") is not False
            or result.get("lifecycle_action") != "notion_page_recovery_execute"
            or status_class not in _RECOVERY_REASON_BY_STATUS
            or reason_code
            not in {
                *_RECOVERY_REASON_BY_STATUS.values(),
                "notion_page_recovery_approval_blocked",
            }
            or not isinstance(result.get("receipt_created"), bool)
        ):
            raise ValueError
        if not (
            result.get("request_sha256") == contract.request_sha256
            and result.get("plan_sha256") == contract.plan_sha256
        ):
            raise ValueError
        counts = result.get("counts")
        operations = result.get("operations")
        privacy = result.get("privacy_guards")
        blockers = result.get("blockers")
        if not isinstance(counts, Mapping) or set(counts) != _RECOVERY_COUNT_KEYS:
            raise ValueError
        if any(
            not isinstance(counts.get(name), int)
            or isinstance(counts.get(name), bool)
            or counts[name] < 0
            for name in _RECOVERY_COUNT_KEYS - {"outcomes"}
        ):
            raise ValueError
        outcomes = counts.get("outcomes")
        if (
            not isinstance(outcomes, Mapping)
            or set(outcomes) != _RECOVERY_OUTCOMES
            or any(
                not isinstance(value, int) or isinstance(value, bool) or value < 0
                for value in outcomes.values()
            )
        ):
            raise ValueError
        if not isinstance(operations, Mapping) or set(operations) != _RECOVERY_OPERATION_KEYS:
            raise ValueError
        for name, value in operations.items():
            if name == "sleep_seconds":
                if (
                    not isinstance(value, (int, float))
                    or isinstance(value, bool)
                    or not math.isfinite(float(value))
                    or value < 0
                ):
                    raise ValueError
            elif not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError
        if (
            not isinstance(privacy, Mapping)
            or dict(privacy) != _RECOVERY_PRIVACY_GUARDS
        ):
            raise ValueError
        if (
            not isinstance(blockers, list)
            or blockers != sorted(set(blockers))
            or any(
                code
                not in _RECOVERY_EXECUTION_BLOCKERS | {"reviewed_by_invalid"}
                for code in blockers
            )
        ):
            raise ValueError

        input_count = counts["input_item_count"]
        selected_count = counts["selected_item_count"]
        processed_count = counts["processed_item_count"]
        pending_count = counts["pending_item_count"]
        unselected_count = counts["unselected_item_count"]
        replayed_count = counts["replayed_recovered_count"]
        total_accounted = counts["total_accounted_count"]
        outcome_total = sum(outcomes.values())
        if not (
            input_count == contract.input_item_count
            and selected_count == contract.selected_item_count
            and unselected_count == contract.unselected_item_count
            and processed_count + pending_count == selected_count
            and outcome_total == processed_count
            and total_accounted == input_count
            and outcome_total + pending_count + unselected_count == input_count
            and replayed_count <= outcomes["recovered"]
        ):
            raise ValueError

        max_request_attempt_slots = (
            selected_count
            * (MAX_UNKNOWN_BLOCK_IDS + 3)
            * DEFAULT_MAX_ATTEMPTS
        )
        max_fragment_rows = selected_count * (MAX_UNKNOWN_BLOCK_IDS + 1)
        if not (
            operations["provider_calls"] <= operations["paced_request_count"]
            and operations["paced_request_count"] - operations["provider_calls"] <= 1
            and operations["provider_calls"] <= max_request_attempt_slots
            and operations["paced_request_count"] <= max_request_attempt_slots
            and operations["retry_count"] <= max_request_attempt_slots
            and operations["sleep_seconds"]
            <= operations["retry_count"] * DEFAULT_MAX_RETRY_DELAY_SECONDS
            and operations["credential_reads"]
            <= operations["credential_resolution_attempts"]
            <= min(contract.group_count, selected_count)
            and (
                operations["provider_calls"] == 0
                or operations["credential_reads"] > 0
            )
            and operations["objects_created"] <= max_fragment_rows
            and operations["manifest_rows_created"] <= max_fragment_rows
            and operations["projection_rows_created"] <= selected_count
            and operations["resume_rows_created"] <= selected_count * 2
        ):
            raise ValueError

        operations_are_zero = all(
            value == 0 for value in operations.values()
        )
        if reason_code == "notion_page_recovery_approval_blocked":
            if not (
                status_class == "blocked"
                and result["ok"] is False
                and blockers == ["reviewed_by_invalid"]
                and processed_count == 0
                and pending_count == selected_count
                and replayed_count == 0
                and outcome_total == 0
                and operations_are_zero
                and result["receipt_created"] is False
            ):
                raise ValueError
        else:
            if reason_code != _RECOVERY_REASON_BY_STATUS[status_class]:
                raise ValueError
            expected_ok = status_class in {"written", "no_change"}
            if result["ok"] is not expected_ok:
                raise ValueError
            non_recovered = outcome_total - outcomes["recovered"]
            if status_class in {"written", "no_change"}:
                if not (
                    blockers == []
                    and pending_count == 0
                    and non_recovered == 0
                    and processed_count == selected_count
                ):
                    raise ValueError
            elif (
                status_class == "partial"
                and processed_count == 0
                and operations_are_zero
                and result["receipt_created"] is not True
            ):
                raise ValueError
            elif status_class == "blocked" and processed_count != 0:
                raise ValueError
            if status_class == "no_change" and not (
                operations["provider_calls"] == 0
                and operations["objects_created"] == 0
                and replayed_count == selected_count
            ):
                raise ValueError
            if status_class == "written" and not (
                operations["provider_calls"] > 0
                or operations["objects_created"] > 0
            ):
                raise ValueError
            if status_class in {"partial", "blocked"} and not (
                blockers or pending_count or non_recovered
            ):
                raise ValueError
        if (
            set(blockers) & (_RECOVERY_STORAGE_BLOCKERS | {"receipt_write_failed"})
            and result["receipt_created"] is not False
        ):
            raise ValueError
        return {
            "ok": result["ok"],
            "dry_run": False,
            "lifecycle_action": "notion_page_recovery_execute",
            "status_class": status_class,
            "reason_code": reason_code,
            "request_sha256": contract.request_sha256,
            "plan_sha256": contract.plan_sha256,
            "counts": {
                name: (
                    {key: outcomes[key] for key in sorted(outcomes)}
                    if name == "outcomes"
                    else counts[name]
                )
                for name in _RECOVERY_COUNT_KEYS
            },
            "operations": {name: operations[name] for name in _RECOVERY_OPERATION_KEYS},
            "receipt_created": result["receipt_created"],
            "privacy_guards": dict(_RECOVERY_PRIVACY_GUARDS),
            "blockers": list(blockers),
        }
    except Exception:
        return _uncertain_recovery_worker_result(contract)


def execute_spawned_authenticated_notion_page_recovery(
    archive_root: Path | str,
    manifest: Mapping[str, Any],
    *,
    expected_plan_sha256: str,
    reviewed_by: str,
    max_items: int,
    offset: int = 0,
    approved: bool = True,
    worker_spawner: NotionRecoveryWorkerSpawner | None = None,
) -> dict[str, Any]:
    """Run live recovery in a child; verified replay stays zero-live in parent."""

    action = "authenticated_notion_page_recovery_execute"
    if approved is not True:
        return _workflow_failure(action, "notion_page_recovery_approval_required")
    if not isinstance(manifest, Mapping):
        return _workflow_failure(action, "notion_page_recovery_manifest_invalid")
    try:
        archive_projection = list_secure_credentials(archive_root)
        if manifest.get("archive_id") != archive_projection.get("archive_id"):
            return _workflow_failure(
                action, "notion_page_recovery_archive_identity_mismatch"
            )
        preview = plan_recovery(
            archive_root,
            manifest,
            max_items=max_items,
            offset=offset,
        )
    except Exception:
        return _workflow_failure(action, "notion_page_recovery_plan_failed")
    if preview.get("ok") is not True:
        return _workflow_failure(action, "notion_page_recovery_manifest_invalid")
    actual = preview.get("plan_sha256")
    if not (
        isinstance(expected_plan_sha256, str)
        and _SHA256_RE.fullmatch(expected_plan_sha256)
        and isinstance(actual, str)
        and hmac.compare_digest(expected_plan_sha256, actual)
    ):
        return _workflow_failure(action, "expected_plan_sha256_mismatch")
    try:
        projection_contract = _build_recovery_projection_contract(
            preview,
            expected_plan_sha256=expected_plan_sha256,
        )
    except Exception:
        return _workflow_failure(action, "notion_page_recovery_plan_failed")
    if preview.get("counts", {}).get("provider_pending_count") == 0:
        return execute_authenticated_notion_page_recovery(
            archive_root,
            manifest,
            expected_plan_sha256=expected_plan_sha256,
            reviewed_by=reviewed_by,
            max_items=max_items,
            offset=offset,
            approved=True,
            native=_NeverWindowsNative(),
        )
    try:
        invocation = NotionRecoveryWorkerInvocation(
            archive_root=str(Path(archive_root).resolve()),
            manifest=dict(manifest),
            expected_plan_sha256=expected_plan_sha256,
            reviewed_by=reviewed_by,
            max_items=max_items,
            offset=offset,
        )
    except Exception:
        return _workflow_failure(action, "notion_page_recovery_worker_launch_failed")

    selected = worker_spawner or SpawnNotionRecoveryWorkerSpawner()
    try:
        run_outcome = selected.run_worker(invocation)
    except Exception:
        # An arbitrary injected spawner cannot prove that it failed before its
        # live boundary. Production returns the parent-owned outcome below.
        return _uncertain_recovery_worker_result(projection_contract)
    if isinstance(run_outcome, _NotionRecoveryWorkerRunOutcome):
        if run_outcome.worker_started is not True:
            return _workflow_failure(
                action,
                "notion_page_recovery_worker_launch_failed",
            )
        raw_result = run_outcome.result
    else:
        # Backward-compatible injected spawners returning a bare mapping have
        # entered their worker boundary by definition.
        raw_result = run_outcome
    if not isinstance(raw_result, Mapping):
        return _uncertain_recovery_worker_result(projection_contract)
    return _project_recovery_worker_result(
        raw_result,
        contract=projection_contract,
    )


__all__ = [
    "CredentialAdoptionWorkerInvocation",
    "CredentialAdoptionWorkerSpawner",
    "InjectedCredentialAdoptionWorkerSpawner",
    "InjectedNotionRecoveryWorkerSpawner",
    "NotionRecoveryWorkerInvocation",
    "NotionRecoveryWorkerSpawner",
    "SpawnNotionRecoveryWorkerSpawner",
    "SpawnCredentialAdoptionWorkerSpawner",
    "WORKFLOW_PLAN_SCHEMA_VERSION",
    "WORKFLOW_RESULT_SCHEMA_VERSION",
    "approve_authenticated_credential_lifecycle",
    "decide_authenticated_credential_lifecycle",
    "execute_authenticated_notion_page_recovery",
    "execute_spawned_authenticated_notion_page_recovery",
    "execute_windows_notion_credential_adoption",
    "list_authenticated_secure_credentials",
    "plan_authenticated_credential_lifecycle",
    "plan_secure_credential_adoption",
]
