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
module and running its tests cannot open a real credential popup, credential
store, or network connection.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import json
import math
import multiprocessing
import os
from pathlib import Path
import re
import signal
import time
from typing import Any, Protocol

from .credential_secure_intake import (
    FileOneTimeRequestClaims,
    SecureIntakePlan,
    SecureIntakeWorker,
    LEGACY_RECEIPT_SCHEMA_VERSION,
    NOTION_PAT_SCOPE_FINGERPRINT_DOMAIN,
    NOTION_PAT_WORKSPACE_IDENTITY_BASIS,
    NOTION_WORKSPACE_IDENTITY_BASIS,
    NOTION_WORKSPACE_IDENTITY_BASES,
    WindowsCredentialManagerExactStore,
    create_secure_intake_plan,
)
from .credential_secure_intake_windows import (
    CtypesWindowsNativeFacade,
    CredentialPopupPromptContext,
    WindowsCredentialPopupSecretUI,
    WindowsSecureIntakeError,
    WindowsSecureIntakeNative,
    current_windows_owner_binding,
    derive_windows_fingerprint_key,
    windows_credential_target_prefix,
)
from .credential_secure_registry import (
    AuthenticatedCredentialReuseEvidence,
    LEGACY_WORKSPACE_IDENTITY_BASIS,
    ReceiptBackedNotionCredentialBroker,
    SecureCredentialRegistryError,
    StableArchiveFingerprintKeyProvider,
    create_archive_atomic_json_receipt_committer,
    evolve_legacy_authenticated_workspace_scope,
    list_secure_credentials,
    persist_duplicate_lifecycle_decision,
    use_authenticated_secure_credential_for_revalidation,
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


WORKFLOW_PLAN_SCHEMA_VERSION = "wom-credential-workflow-plan/v0.2"
WORKFLOW_RESULT_SCHEMA_VERSION = "wom-credential-workflow-result/v0.3"
INTERACTION_CONTEXT_SCHEMA_VERSION = "wom-credential-interaction-context/v0.1"
PLANNING_OWNER_BINDING = "credential-workflow-non-live-planning-owner"

_HEX_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_FIXED_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{2,127}$")
_CREDENTIAL_ID_RE = re.compile(r"^cred_[A-Za-z0-9_-]{16,96}$")
_SAFE_ARCHIVE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+/-]{0,255}$")
_SAFE_INTERACTION_TEXT_RE = re.compile(r"^[^\x00-\x1f\x7f]{1,240}$")
_INTERACTION_SECRET_SHAPE_RE = re.compile(
    r"(?i)(?:bearer\s+\S+|(?:ntn_|secret_|github_pat_|sk-)[A-Za-z0-9_./+=-]{16,})"
)
_INTERACTION_PRIVATE_LOCATOR_RE = re.compile(
    r"(?i)(?:https?://|\\\\|[A-Z]:\\|\b[0-9a-f]{8}-[0-9a-f-]{27,}\b|\b[0-9a-f]{32,}\b|\S+@\S+)"
)
_WORKFLOW_ROLLBACK_CANONICAL = {
    "not_required": "not_required",
    "deleted": "deleted",
    "delete_failed": "delete_failed",
}

_ADOPTION_APPROVED_EXECUTION_STEPS = (
    "archive_identity_validate",
    "current_windows_owner_bind",
    "archive_scoped_authentication_key_initialize_or_reuse",
    "assistant_task_context_and_fixed_wom_security_copy_verify",
    "authenticated_existing_registration_check_before_prompt",
    "one_time_request_claim_and_masked_human_secret_prompt",
    "exact_encrypted_store_write",
    "provider_and_reviewed_anchor_verify",
    "authenticated_receipt_commit",
    "authenticated_rediscovery_verify",
)

_ADOPTION_STAGE_FIELDS = (
    "credential_input_received",
    "complete_line_received",
    "temporary_store_write_attempted",
    "provider_request_attempted",
)


def _adoption_stage_evidence(
    *,
    credential_input_received: bool = False,
    complete_line_received: bool = False,
    temporary_store_write_attempted: bool = False,
    provider_request_attempted: bool = False,
) -> dict[str, bool]:
    values = (
        credential_input_received,
        complete_line_received,
        temporary_store_write_attempted,
        provider_request_attempted,
    )
    if any(type(value) is not bool for value in values):
        raise ValueError("credential_adoption_stage_evidence_invalid")
    return dict(zip(_ADOPTION_STAGE_FIELDS, values, strict=True))


def _adoption_stage_evidence_from_mapping(
    value: Mapping[str, Any],
) -> dict[str, bool] | None:
    evidence = {field: value.get(field) for field in _ADOPTION_STAGE_FIELDS}
    if any(type(item) is not bool for item in evidence.values()):
        return None
    vector = tuple(evidence[field] for field in _ADOPTION_STAGE_FIELDS)
    if vector not in {
        (False, False, False, False),
        (True, False, False, False),
        (True, True, False, False),
        (True, True, True, False),
        (True, True, True, True),
        # Authenticated reuse has no fresh prompt or store write, but it does
        # revalidate the exact saved credential with the provider.
        (False, False, False, True),
    }:
        return None
    return evidence  # type: ignore[return-value]


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

    The worker deliberately does not export detailed native/provider counts:
    such telemetry would be another secret-adjacent IPC surface.  The separate
    four-bit stage evidence reports only whether each major boundary was
    crossed; it never reports values, lengths, response status, or timing.
    Once the approved worker boundary is entered, SID lookup, archive-key
    initialization/reuse, request claiming, and the hidden UI may already have
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
    credential_input_received: bool = False,
    complete_line_received: bool = False,
    temporary_store_write_attempted: bool = False,
    provider_request_attempted: bool = False,
) -> dict[str, Any]:
    """Build one fixed, content-free failure result."""

    safe_reason = (
        reason_code
        if type(reason_code) is str and _FIXED_CODE_RE.fullmatch(reason_code)
        else "credential_workflow_failed"
    )
    safe_rollback = _WORKFLOW_ROLLBACK_CANONICAL.get(
        rollback_status if type(rollback_status) is str else "",
        "not_required",
    )
    if safe_rollback == "delete_failed":
        operator_action = "stop_and_remove_the_exact_encrypted_store_entry"
    elif safe_reason == "credential_input_cancelled_or_empty":
        operator_action = "create_a_new_intake_plan_when_ready"
    elif safe_reason == "credential_input_not_received":
        operator_action = "retry_secure_popup_input_with_a_new_plan"
    elif safe_reason == "credential_input_invalid_for_provider":
        operator_action = "enter_a_complete_provider_credential_with_a_new_plan"
    elif safe_reason == "credential_input_boundary_failed":
        operator_action = "repair_secure_input_boundary_and_create_a_new_plan"
    elif safe_reason == "provider_request_not_attempted":
        operator_action = "stop_and_review_the_provider_adapter_before_retrying"
    elif safe_reason == "provider_auth_rejected":
        operator_action = "review_the_notion_credential_and_create_a_new_plan"
    elif safe_reason == "provider_identity_endpoint_unavailable":
        operator_action = "create_a_new_plan_after_provider_identity_service_recovers"
    elif safe_reason == "reviewed_anchor_inaccessible":
        operator_action = "review_page_access_and_create_a_new_plan"
    elif safe_reason == "credential_adoption_existing_scope_revalidation_failed":
        operator_action = "review_current_notion_anchor_and_connection_before_retry"
    elif safe_reason == "credential_adoption_existing_scope_migration_failed":
        operator_action = "rerun_same_approved_plan_to_complete_scope_migration"
    elif safe_reason in {
        "credential_adoption_existing_store_missing",
        "credential_adoption_existing_store_probe_failed",
        "credential_adoption_existing_store_fingerprint_mismatch",
    }:
        operator_action = "create_and_review_fresh_replace_existing_plan"
    elif accepted and persisted:
        operator_action = "stop_and_repair_authenticated_rediscovery"
    else:
        operator_action = "review_the_fixed_reason_code_before_retry"
    result = {
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
    if action == "secure_credential_adoption_execute":
        result.update(
            _adoption_stage_evidence(
                credential_input_received=credential_input_received,
                complete_line_received=complete_line_received,
                temporary_store_write_attempted=temporary_store_write_attempted,
                provider_request_attempted=provider_request_attempted,
            )
        )
    return result


def _approved_adoption_worker_failure(
    reason_code: str,
    *,
    accepted: bool = False,
    persisted: bool = False,
    rollback_status: str = "not_required",
    credential_input_received: bool = False,
    complete_line_received: bool = False,
    temporary_store_write_attempted: bool = False,
    provider_request_attempted: bool = False,
) -> dict[str, Any]:
    """Build a failure that cannot falsely claim zero work after approval."""

    return _workflow_failure(
        "secure_credential_adoption_execute",
        reason_code,
        accepted=accepted,
        persisted=persisted,
        rollback_status=rollback_status,
        operations=_approved_adoption_worker_operations(),
        credential_input_received=credential_input_received,
        complete_line_received=complete_line_received,
        temporary_store_write_attempted=temporary_store_write_attempted,
        provider_request_attempted=provider_request_attempted,
    )


@dataclass(frozen=True)
class _ExistingRegistrationScopeRevalidation:
    exact_match: bool
    migration_required: bool
    verified_workspace_fingerprint: str | None = None
    workspace_identity_basis: str | None = None


def _existing_registration_scope_matches(
    secret: memoryview,
    evidence: AuthenticatedCredentialReuseEvidence,
    *,
    plan: SecureIntakePlan,
    verifier: Any,
    provider_request_observer: Callable[[], None],
) -> _ExistingRegistrationScopeRevalidation:
    """Recheck the saved token against this plan's reviewed Notion anchor."""

    try:
        if verifier.validate_secret_input(secret, plan.provider) is not True:
            return _ExistingRegistrationScopeRevalidation(False, False)
        identity = verifier.verify_identity(
            secret,
            provider=plan.provider,
            reviewed_anchor_uuid=plan.reviewed_anchor_uuid,
            provider_request_observer=provider_request_observer,
        )
        provider = identity.provider
        account_subject = identity.account_subject
        workspace_identity = identity.workspace_identity
        anchor = identity.reviewed_anchor_uuid
        capabilities = tuple(sorted(set(identity.capabilities)))
        workspace_identity_basis = identity.workspace_identity_basis
    except Exception:
        return _ExistingRegistrationScopeRevalidation(False, False)
    if not (
        identity.subject_verified is True
        and identity.anchor_access_verified is True
        and provider == plan.provider == evidence.provider
        and isinstance(account_subject, str)
        and 0 < len(account_subject) <= 512
        and isinstance(workspace_identity, str)
        and 0 < len(workspace_identity) <= 512
        and anchor == plan.reviewed_anchor_uuid
        and all(
            isinstance(capability, str)
            and _FIXED_CODE_RE.fullmatch(capability) is not None
            for capability in capabilities
        )
        and set(plan.requested_capabilities).issubset(capabilities)
        and capabilities == evidence.verified_capabilities
        and workspace_identity_basis in NOTION_WORKSPACE_IDENTITY_BASES
    ):
        return _ExistingRegistrationScopeRevalidation(False, False)
    account_fingerprint = "sha256:" + hashlib.sha256(
        account_subject.encode("utf-8")
    ).hexdigest()
    if not hmac.compare_digest(
        account_fingerprint,
        evidence.verified_account_fingerprint,
    ):
        return _ExistingRegistrationScopeRevalidation(False, False)
    if workspace_identity_basis == NOTION_WORKSPACE_IDENTITY_BASIS:
        workspace_fingerprint = "sha256:" + hashlib.sha256(
            workspace_identity.encode("utf-8")
        ).hexdigest()
    elif workspace_identity_basis == NOTION_PAT_WORKSPACE_IDENTITY_BASIS:
        workspace_fingerprint = "sha256:" + hashlib.sha256(
            NOTION_PAT_SCOPE_FINGERPRINT_DOMAIN
            + evidence.credential_fingerprint.encode("ascii")
        ).hexdigest()
    else:  # pragma: no cover - retained as a fail-closed guard.
        return _ExistingRegistrationScopeRevalidation(False, False)
    if evidence.workspace_identity_basis == LEGACY_WORKSPACE_IDENTITY_BASIS:
        return _ExistingRegistrationScopeRevalidation(
            False,
            True,
            workspace_fingerprint,
            workspace_identity_basis,
        )
    if evidence.workspace_identity_basis != workspace_identity_basis:
        return _ExistingRegistrationScopeRevalidation(False, False)
    return _ExistingRegistrationScopeRevalidation(
        hmac.compare_digest(
            workspace_fingerprint,
            evidence.verified_workspace_fingerprint,
        ),
        False,
        workspace_fingerprint,
        workspace_identity_basis,
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
        "credential_input_received": None,
        "complete_line_received": None,
        "temporary_store_write_attempted": None,
        "provider_request_attempted": None,
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


def _validated_interaction_text(value: Any) -> str:
    text = str(value or "").strip()
    if (
        _SAFE_INTERACTION_TEXT_RE.fullmatch(text) is None
        or _INTERACTION_SECRET_SHAPE_RE.search(text) is not None
        or _INTERACTION_PRIVATE_LOCATOR_RE.search(text) is not None
    ):
        raise ValueError("credential_adoption_interaction_context_invalid")
    return text


def _interaction_context(
    plan: SecureIntakePlan,
    *,
    task_summary: str,
    connection_reason: str,
) -> tuple[dict[str, str], str]:
    context = {
        "schema": INTERACTION_CONTEXT_SCHEMA_VERSION,
        "provider": plan.provider,
        "purpose": plan.purpose,
        "account_label": plan.account_label,
        "workspace_label": plan.workspace_label,
        "task_summary": _validated_interaction_text(task_summary),
        "connection_reason": _validated_interaction_text(connection_reason),
    }
    canonical = json.dumps(
        context,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return context, "sha256:" + hashlib.sha256(canonical).hexdigest()


def plan_secure_credential_adoption(
    *,
    expected_archive_id: str,
    account_label: str,
    workspace_label: str,
    purpose: str,
    task_summary: str,
    connection_reason: str,
    replace_existing: bool = False,
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
        interaction_context, interaction_context_sha256 = _interaction_context(
            plan,
            task_summary=task_summary,
            connection_reason=connection_reason,
        )
        if type(replace_existing) is not bool:
            raise ValueError("credential_adoption_replacement_intent_invalid")
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
        "interaction_context": interaction_context,
        "interaction_context_sha256": interaction_context_sha256,
        "replacement_approved": replace_existing,
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
) -> tuple[SecureIntakePlan, CredentialPopupPromptContext, str]:
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
    replacement_approved = approval_plan.get("replacement_approved")
    if type(replacement_approved) is not bool:
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
    raw_context = approval_plan.get("interaction_context")
    supplied_context_sha256 = approval_plan.get("interaction_context_sha256")
    if not isinstance(raw_context, Mapping):
        raise ValueError("credential_adoption_interaction_context_invalid")
    expected_context, rebuilt_context_sha256 = _interaction_context(
        rebuilt,
        task_summary=str(raw_context.get("task_summary") or ""),
        connection_reason=str(raw_context.get("connection_reason") or ""),
    )
    if not (
        dict(raw_context) == expected_context
        and isinstance(supplied_context_sha256, str)
        and _SHA256_RE.fullmatch(supplied_context_sha256)
        and hmac.compare_digest(
            supplied_context_sha256,
            rebuilt_context_sha256,
        )
    ):
        raise ValueError("credential_adoption_interaction_context_invalid")
    prompt_context = CredentialPopupPromptContext(
        provider=expected_context["provider"],
        purpose=expected_context["purpose"],
        account_label=expected_context["account_label"],
        workspace_label=expected_context["workspace_label"],
        task_summary=expected_context["task_summary"],
        connection_reason=expected_context["connection_reason"],
    )
    return rebuilt, prompt_context, rebuilt_context_sha256


@dataclass(frozen=True)
class CredentialAdoptionWorkerInvocation:
    """Pickle-safe, secret-free input sent to the live child process."""

    archive_root: str = field(repr=False)
    approval_plan: Mapping[str, Any] = field(repr=False)
    expected_plan_digest: str
    expected_interaction_context_sha256: str
    replacement_approved: bool
    expected_archive_id: str
    reviewed_anchor_uuid: str = field(repr=False)
    requested_capabilities: tuple[str, ...]

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "archive_root_present": bool(self.archive_root),
            "approval_plan_present": bool(self.approval_plan),
            "expected_plan_digest": self.expected_plan_digest,
            "interaction_context_present": True,
            "interaction_context_sha256": self.expected_interaction_context_sha256,
            "replacement_approved": self.replacement_approved,
            "expected_archive_id": self.expected_archive_id,
            "reviewed_anchor_present": True,
            "requested_capabilities": list(self.requested_capabilities),
            "secret_transport": "child_native_popup_length_opaque_input_only",
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
        reviewed_plan, prompt_context, interaction_context_sha256 = _rebuild_approved_planning_contract(
            invocation.approval_plan,
            expected_plan_digest=invocation.expected_plan_digest,
            expected_archive_id=invocation.expected_archive_id,
            reviewed_anchor_uuid=invocation.reviewed_anchor_uuid,
            requested_capabilities=invocation.requested_capabilities,
        )
        if not hmac.compare_digest(
            invocation.expected_interaction_context_sha256,
            interaction_context_sha256,
        ) or invocation.replacement_approved is not invocation.approval_plan.get(
            "replacement_approved"
        ):
            raise ValueError("credential_adoption_interaction_context_invalid")
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
        callback_archive_projection = list_secure_credentials(
            invocation.archive_root,
            receipt_authentication_key=key_view,
        )
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
        existing_rows = callback_archive_projection.get("credentials")
        if not isinstance(existing_rows, list) or any(
            not isinstance(row, Mapping)
            or row.get("receipt_authentication_status") != "valid"
            for row in existing_rows
        ):
            return _approved_adoption_worker_failure(
                "credential_adoption_existing_registry_untrusted"
            )
        matching_existing = [
            row
            for row in existing_rows
            if row.get("provider") == actual_plan.provider
            and row.get("purpose") == actual_plan.purpose
        ]
        if matching_existing and invocation.replacement_approved is not True:
            if len(matching_existing) != 1:
                return _approved_adoption_worker_failure(
                    "credential_adoption_existing_registrations_require_lifecycle_review"
                )
            existing = matching_existing[0]
            credential_id = existing.get("credential_id")
            if not isinstance(credential_id, str) or _CREDENTIAL_ID_RE.fullmatch(
                credential_id
            ) is None:
                return _approved_adoption_worker_failure(
                    "credential_adoption_existing_registry_untrusted"
                )
            existing_provider_request_attempted = False

            def observe_existing_provider_request() -> None:
                nonlocal existing_provider_request_attempted
                existing_provider_request_attempted = True

            def existing_stage_evidence() -> dict[str, bool]:
                return _adoption_stage_evidence(
                    provider_request_attempted=existing_provider_request_attempted
                )

            fingerprint_key: bytearray | None = None
            try:
                fingerprint_key = derive_windows_fingerprint_key(
                    key_view,
                    owner_binding,
                )
                verifier = notion_adapter.secure_intake_verifier()
                scope_revalidation = use_authenticated_secure_credential_for_revalidation(
                    archive_path,
                    credential_id,
                    receipt_authentication_key=key_view,
                    secret_fingerprint_key=fingerprint_key,
                    native=native,
                    consumer=lambda secret, evidence: (
                        _existing_registration_scope_matches(
                            secret,
                            evidence,
                            plan=actual_plan,
                            verifier=verifier,
                            provider_request_observer=observe_existing_provider_request,
                        )
                    ),
                )
            except SecureCredentialRegistryError as error:
                if error.code == "credential_registry_store_missing":
                    reason = "credential_adoption_existing_store_missing"
                elif error.code in {
                    "credential_registry_store_probe_failed",
                    "credential_registry_secret_read_failed",
                }:
                    reason = "credential_adoption_existing_store_probe_failed"
                elif error.code == "credential_registry_secret_fingerprint_mismatch":
                    reason = (
                        "credential_adoption_existing_store_fingerprint_mismatch"
                    )
                else:
                    reason = (
                        "credential_adoption_existing_scope_revalidation_failed"
                    )
                return _approved_adoption_worker_failure(
                    reason,
                    **existing_stage_evidence(),
                )
            except Exception:
                return _approved_adoption_worker_failure(
                    "credential_adoption_existing_scope_revalidation_failed",
                    **existing_stage_evidence(),
                )
            finally:
                if fingerprint_key is not None:
                    for index in range(len(fingerprint_key)):
                        fingerprint_key[index] = 0
            if not isinstance(
                scope_revalidation, _ExistingRegistrationScopeRevalidation
            ):
                return _approved_adoption_worker_failure(
                    "credential_adoption_existing_scope_revalidation_failed",
                    **existing_stage_evidence(),
                )
            workspace_scope_migrated = False
            workspace_scope_migration_required = bool(
                scope_revalidation.migration_required
                or (
                    scope_revalidation.exact_match
                    and existing.get("workspace_scope_evolved") is True
                    and existing.get("workspace_scope_transition_pending") is True
                )
            )
            if workspace_scope_migration_required:
                if not (
                    isinstance(
                        scope_revalidation.verified_workspace_fingerprint, str
                    )
                    and isinstance(scope_revalidation.workspace_identity_basis, str)
                ):
                    return _approved_adoption_worker_failure(
                        "credential_adoption_existing_scope_revalidation_failed",
                        **existing_stage_evidence(),
                    )
                migration_fingerprint_key: bytearray | None = None
                try:
                    migration_moment = execution_now().astimezone(
                        timezone.utc
                    ).replace(microsecond=0)
                    migration_fingerprint_key = derive_windows_fingerprint_key(
                        key_view,
                        owner_binding,
                    )
                    migration = evolve_legacy_authenticated_workspace_scope(
                        archive_path,
                        credential_id,
                        evolved_workspace_fingerprint=(
                            scope_revalidation.verified_workspace_fingerprint
                        ),
                        workspace_identity_basis=(
                            scope_revalidation.workspace_identity_basis
                        ),
                        verified_account_fingerprint=(
                            existing["verified_account_fingerprint"]
                        ),
                        verified_capabilities=tuple(
                            existing["verified_capabilities"]
                        ),
                        receipt_authentication_key=key_view,
                        secret_fingerprint_key=migration_fingerprint_key,
                        native=native,
                        evolved_at=migration_moment.isoformat().replace(
                            "+00:00", "Z"
                        ),
                    )
                except SecureCredentialRegistryError as error:
                    if error.code == (
                        "credential_registry_evolution_lifecycle_review_required"
                    ):
                        return _approved_adoption_worker_failure(
                            "credential_adoption_existing_registrations_require_lifecycle_review",
                            **existing_stage_evidence(),
                        )
                    if error.code == "credential_registry_store_missing":
                        return _approved_adoption_worker_failure(
                            "credential_adoption_existing_store_missing",
                            **existing_stage_evidence(),
                        )
                    if error.code in {
                        "credential_registry_store_probe_failed",
                        "credential_registry_secret_read_failed",
                    }:
                        return _approved_adoption_worker_failure(
                            "credential_adoption_existing_store_probe_failed",
                            **existing_stage_evidence(),
                        )
                    if error.code == (
                        "credential_registry_secret_fingerprint_mismatch"
                    ):
                        return _approved_adoption_worker_failure(
                            "credential_adoption_existing_store_fingerprint_mismatch",
                            **existing_stage_evidence(),
                        )
                    return _approved_adoption_worker_failure(
                        "credential_adoption_existing_scope_migration_failed",
                        **existing_stage_evidence(),
                    )
                except Exception:
                    return _approved_adoption_worker_failure(
                        "credential_adoption_existing_scope_migration_failed",
                        **existing_stage_evidence(),
                    )
                finally:
                    if migration_fingerprint_key is not None:
                        for index in range(len(migration_fingerprint_key)):
                            migration_fingerprint_key[index] = 0
                if migration.get("ok") is not True:
                    return _approved_adoption_worker_failure(
                        "credential_adoption_existing_scope_migration_failed",
                        **existing_stage_evidence(),
                    )
                workspace_scope_migrated = True
                refreshed = list_secure_credentials(
                    archive_path,
                    receipt_authentication_key=key_view,
                )
                refreshed_matches = [
                    row
                    for row in refreshed.get("credentials", [])
                    if isinstance(row, Mapping)
                    and row.get("credential_id") == credential_id
                ]
                if len(refreshed_matches) != 1:
                    return _approved_adoption_worker_failure(
                        "credential_adoption_existing_scope_migration_failed",
                        **existing_stage_evidence(),
                    )
                existing = refreshed_matches[0]
            elif scope_revalidation.exact_match is not True:
                return _approved_adoption_worker_failure(
                    "credential_adoption_existing_scope_revalidation_failed",
                    **existing_stage_evidence(),
                )
            return {
                "schema_version": WORKFLOW_RESULT_SCHEMA_VERSION,
                "ok": True,
                "lifecycle_action": action,
                "accepted": False,
                "persisted": True,
                "reason_code": (
                    "credential_adoption_legacy_scope_evolved_without_prompt"
                    if workspace_scope_migrated
                    else "credential_adoption_existing_registration_preserved_without_prompt"
                ),
                "credential_id": credential_id,
                "authenticated_rediscovery_verified": True,
                "human_default_decision_required": not bool(
                    existing.get("broker_authoritative")
                ),
                "secret_prompt_performed": False,
                "existing_registration_reused": True,
                "workspace_scope_migrated": workspace_scope_migrated,
                "secret_value_present": False,
                "reviewed_anchor_present_in_result": False,
                "backend_target_present": False,
                "crash_or_power_loss_rollback_guaranteed": False,
                "operations": _approved_adoption_worker_operations(),
                **existing_stage_evidence(),
            }
        worker_kwargs: dict[str, Any] = {
            "claims": FileOneTimeRequestClaims(
                archive_path / "profiles" / "local" / "credential-intake" / "claims",
                archive_root=archive_path,
                expected_relative_directory=(
                    Path("profiles") / "local" / "credential-intake" / "claims"
                ),
            ),
            "ui": WindowsCredentialPopupSecretUI(
                native,
                prompt_context,
            ),
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
        raw_stage_evidence = _adoption_stage_evidence_from_mapping(raw_result)
        if raw_stage_evidence is None:
            return _uncertain_adoption_worker_result()
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
                **raw_stage_evidence,
            )
        if raw_stage_evidence != _adoption_stage_evidence(
            credential_input_received=True,
            complete_line_received=True,
            temporary_store_write_attempted=True,
            provider_request_attempted=True,
        ):
            return _uncertain_adoption_worker_result()

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
                **raw_stage_evidence,
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
                **raw_stage_evidence,
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
            **raw_stage_evidence,
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


def _adoption_worker_detached_ack() -> dict[str, str]:
    """Return the sole fixed ACK emitted before popup/native live work."""

    return {"worker_transport_status": "popup_child_detached"}


def _is_exact_adoption_worker_detached_ack(value: Any) -> bool:
    return bool(
        type(value) is dict
        and set(value) == {"worker_transport_status"}
        and type(value.get("worker_transport_status")) is str
        and value["worker_transport_status"] == "popup_child_detached"
    )


def _detach_spawned_popup_child_console(
    *,
    kernel32: Any | None = None,
    platform_name: str | None = None,
) -> bool:
    """Detach only the spawned popup child from its inherited console.

    Production calls the exact zero-argument ``FreeConsole`` Win32 boundary.
    The former console belongs to the parent and is never configured or read by
    this child. Injected non-Boolean values are rejected rather than treated by
    Python truthiness; a real ctypes BOOL result is canonicalized to ``bool``.
    """

    if (platform_name or os.name) != "nt":
        return False
    try:
        if kernel32 is None:
            loader = getattr(ctypes, "WinDLL", None)
            if loader is None:
                return False
            kernel32 = loader("kernel32", use_last_error=True)
        free_console = kernel32.FreeConsole
        free_console.argtypes = []
        free_console.restype = wintypes.BOOL
        raw_result = free_console()
        if type(raw_result) is bool:
            return raw_result
        native_function_type = getattr(ctypes, "_CFuncPtr", None)
        if (
            native_function_type is not None
            and isinstance(free_console, native_function_type)
            and type(raw_result) is int
        ):
            # Win32 BOOL success is any nonzero value. Only a real ctypes
            # function result receives this canonicalization; injected Python
            # integers remain invalid evidence above.
            return raw_result != 0
        return False
    except BaseException:
        raise


def _spawned_adoption_entry(
    send_connection: Any,
    invocation: CredentialAdoptionWorkerInvocation,
) -> None:
    """Top-level Windows-spawn entry; sends only a sanitized status mapping."""

    try:
        try:
            if _detach_spawned_popup_child_console() is not True:
                return
        except BaseException:
            return
        try:
            send_connection.send(_adoption_worker_detached_ack())
        except BaseException:
            # No popup/native/store/provider work is allowed unless the parent
            # can prove this exact detached-child ACK.
            return
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
        except BaseException:
            result = _adoption_worker_transport_marker()
        try:
            send_connection.send(result)
        except BaseException:
            pass
    finally:
        try:
            send_connection.close()
        except BaseException:
            pass


def _join_started_credential_worker(process: Any) -> None:
    """Wait until a started worker exits without opening a terminate path.

    The worker can own the only secret buffer and an in-flight exact-target
    rollback, so a transient ``join`` failure must never let the parent resume
    while that child is still alive.
    A successful no-timeout ``join`` proves termination.  After an exceptional
    join, exact ``is_alive() is False`` is the only alternative completion
    proof; otherwise the parent keeps its protection lease and retries.
    """

    while True:
        try:
            process.join()
            return
        except (Exception, KeyboardInterrupt):
            try:
                if process.is_alive() is False:
                    return
            except (Exception, KeyboardInterrupt):
                pass
            try:
                time.sleep(0.05)
            except BaseException:
                # An injected interruption must not escape while the child may
                # still own secret/rollback state. The exact no-timeout join is
                # retried without changing any parent input state.
                pass


@dataclass(frozen=True, repr=False)
class _CredentialWorkerStartSignalLease:
    """Captured parent handlers that must be restored before IPC resumes."""

    signals: tuple[Any, ...]
    originals: tuple[Any, ...] = field(repr=False)


def _credential_worker_start_signals() -> tuple[Any, Any] | None:
    """Return the two Windows console signals required for an atomic start."""

    sigbreak = getattr(signal, "SIGBREAK", None)
    if sigbreak is None:
        return None
    return signal.SIGINT, sigbreak


def _restore_credential_worker_start_signal_lease(
    lease: _CredentialWorkerStartSignalLease,
    *,
    signal_getter: Callable[[Any], Any],
    signal_setter: Callable[[Any, Any], Any],
) -> None:
    """Gate forever until every attempted handler is exactly restored.

    A setter may change a handler and then raise.  Callers therefore include a
    signal in ``lease`` *before* attempting its install.  Neither an injected
    ``BaseException`` nor a false-success setter may reopen the parent while a
    child could exist under temporary ignored-signal state.
    """

    pending = list(zip(lease.signals, lease.originals, strict=True))
    while pending:
        unresolved: list[tuple[Any, Any]] = []
        for signal_number, original_handler in reversed(pending):
            try:
                signal_setter(signal_number, original_handler)
            except BaseException:
                pass
            try:
                restored_handler = signal_getter(signal_number)
            except BaseException:
                unresolved.append((signal_number, original_handler))
                continue
            if restored_handler is not original_handler:
                unresolved.append((signal_number, original_handler))
        pending = list(reversed(unresolved))
        if pending:
            try:
                time.sleep(0.01)
            except BaseException:
                pass


def _capture_credential_worker_start_signal_lease(
    *,
    signal_getter: Callable[[Any], Any],
) -> _CredentialWorkerStartSignalLease | None:
    """Capture both exact original handlers before attempting any mutation."""

    signal_numbers = _credential_worker_start_signals()
    if signal_numbers is None:
        return None
    originals: list[Any] = []
    try:
        for signal_number in signal_numbers:
            originals.append(signal_getter(signal_number))
    except BaseException:
        return None
    return _CredentialWorkerStartSignalLease(
        signals=signal_numbers,
        originals=(originals[0], originals[1]),
    )


def _install_credential_worker_start_signal_lease(
    lease: _CredentialWorkerStartSignalLease,
    *,
    signal_getter: Callable[[Any], Any],
    signal_setter: Callable[[Any, Any], Any],
) -> bool:
    """Install both ignored handlers after the full restore lease is owned."""

    try:
        for signal_number in lease.signals:
            # The caller stores the complete lease before this setter call: a
            # setter may change the handler and then raise asynchronously.
            signal_setter(signal_number, signal.SIG_IGN)
            if signal_getter(signal_number) is not signal.SIG_IGN:
                return False
    except BaseException:
        return False
    return True


def _close_credential_worker_send_connection(send_connection: Any) -> None:
    """Close the parent send duplicate without allowing interruption escape."""

    while True:
        try:
            send_connection.close()
            return
        except BaseException:
            try:
                time.sleep(0.01)
            except BaseException:
                pass


@dataclass(frozen=True, repr=False)
class _CredentialWorkerPipeOutcome:
    worker_started: bool
    result: Mapping[str, Any] | None = field(default=None, repr=False)


def _drain_credential_worker_pipe(
    receive_connection: Any,
) -> _CredentialWorkerPipeOutcome:
    """Drain ACK, final mapping, and terminal EOF without interruption escape.

    On Windows, child creation can precede the public ``Process`` start proof.
    The inherited one-way send handle is therefore the containment boundary:
    terminal EOF proves that no bootstrap/worker still owns it. EOF before the
    fixed detached ACK proves no live popup/native/store/provider work began.
    Any malformed, missing-final, or extra sequence is conservatively projected
    as started/unknown. Exceptions and their text never cross IPC.
    """

    final_mapping: Mapping[str, Any] | None = None
    ack_observed = False
    any_message_observed = False
    malformed = False
    message_count = 0
    while True:
        try:
            message = receive_connection.recv()
        except EOFError:
            if not any_message_observed:
                return _CredentialWorkerPipeOutcome(worker_started=False)
            if (
                ack_observed
                and message_count == 2
                and not malformed
                and isinstance(final_mapping, Mapping)
            ):
                return _CredentialWorkerPipeOutcome(
                    worker_started=True,
                    result=final_mapping,
                )
            return _CredentialWorkerPipeOutcome(worker_started=True)
        except BaseException:
            try:
                time.sleep(0.01)
            except BaseException:
                pass
            continue
        any_message_observed = True
        message_count += 1
        if message_count == 1:
            ack_observed = _is_exact_adoption_worker_detached_ack(message)
            malformed = not ack_observed
        elif (
            message_count == 2
            and ack_observed
            and isinstance(message, Mapping)
            and not _is_exact_adoption_worker_detached_ack(message)
        ):
            final_mapping = message
        else:
            final_mapping = None
            malformed = True


@dataclass(repr=False)
class SpawnCredentialAdoptionWorkerSpawner:
    """Concrete production seam using a fresh ``multiprocessing.spawn`` child.

    The parent deliberately has no timeout/terminate path.  Python documents
    that terminating a process can interrupt ``finally`` blocks and corrupt
    pipes/locks; here it could also skip the worker's exact-target rollback.
    A human must finish or cancel the native popup. Process crash and power
    loss remain an explicitly reported durability gap. The parent never reads
    interactive input and never changes terminal modes or Windows console
    handlers. It holds a narrow Python SIGINT/SIGBREAK ignore lease only across
    ``Process.start`` and its exact-return proof, restores both exact handlers,
    then drains fixed detached ACK, final result, and terminal EOF from the
    isolated popup worker before the parent can resume.
    """

    _signal_getter: Callable[[Any], Any] = field(
        default=signal.getsignal,
        repr=False,
    )
    _signal_setter: Callable[[Any, Any], Any] = field(
        default=signal.signal,
        repr=False,
    )

    def run_worker(
        self,
        invocation: CredentialAdoptionWorkerInvocation,
    ) -> _CredentialAdoptionWorkerRunOutcome:
        process: Any = None
        receive_connection: Any = None
        send_connection: Any = None
        start_lease: _CredentialWorkerStartSignalLease | None = None
        start_lease_restored = False
        start_invoked = False
        process_start_returned = False
        pipe_drained = False
        worker_joined = False
        pipe_outcome = _CredentialWorkerPipeOutcome(worker_started=False)
        outcome = _CredentialAdoptionWorkerRunOutcome(worker_started=False)

        def restore_start_lease_if_needed() -> None:
            nonlocal start_lease_restored
            if start_lease is not None and not start_lease_restored:
                _restore_credential_worker_start_signal_lease(
                    start_lease,
                    signal_getter=self._signal_getter,
                    signal_setter=self._signal_setter,
                )
                start_lease_restored = True

        def drain_and_contain_started_boundary() -> None:
            nonlocal pipe_drained, pipe_outcome, worker_joined
            if not pipe_drained:
                if send_connection is not None:
                    _close_credential_worker_send_connection(send_connection)
                if receive_connection is not None:
                    pipe_outcome = _drain_credential_worker_pipe(
                        receive_connection
                    )
                else:
                    # A start call cannot be allowed without its containment
                    # pipe. This branch is defensive and must never be reached
                    # by the multiprocessing construction above.
                    pipe_outcome = _CredentialWorkerPipeOutcome(
                        worker_started=True
                    )
                pipe_drained = True
            if (
                process_start_returned
                and process is not None
                and not worker_joined
            ):
                _join_started_credential_worker(process)
                worker_joined = True

        def process_exited_cleanly() -> bool:
            try:
                return bool(process is not None and process.exitcode == 0)
            except BaseException:
                return False

        def current_outcome() -> _CredentialAdoptionWorkerRunOutcome:
            if pipe_outcome.worker_started is not True:
                return _CredentialAdoptionWorkerRunOutcome(worker_started=False)
            if not isinstance(pipe_outcome.result, Mapping):
                return _CredentialAdoptionWorkerRunOutcome(worker_started=True)
            if process_start_returned and not process_exited_cleanly():
                return _CredentialAdoptionWorkerRunOutcome(worker_started=True)
            return _CredentialAdoptionWorkerRunOutcome(
                worker_started=True,
                result=pipe_outcome.result,
            )

        try:
            context = multiprocessing.get_context("spawn")
            receive_connection, send_connection = context.Pipe(duplex=False)
            process = context.Process(
                target=_spawned_adoption_entry,
                args=(send_connection, invocation),
                daemon=False,
            )
            start_lease = _capture_credential_worker_start_signal_lease(
                signal_getter=self._signal_getter,
            )
            if start_lease is not None:
                try:
                    if _install_credential_worker_start_signal_lease(
                        start_lease,
                        signal_getter=self._signal_getter,
                        signal_setter=self._signal_setter,
                    ):
                        try:
                            start_invoked = True
                            process.start()
                        except BaseException:
                            # CPython's Windows spawn can create/inherit the
                            # child pipe before Process.start publishes public
                            # joinability. ACK plus EOF resolve that ambiguity.
                            pass
                        else:
                            # Record this exact proof while both handlers are
                            # still ignored, immediately after start returns.
                            process_start_returned = True
                finally:
                    restore_start_lease_if_needed()
            if start_invoked:
                drain_and_contain_started_boundary()
            outcome = current_outcome()
        except BaseException:
            # Never force-terminate a started intake child: it owns the only
            # secret buffer and must retain the opportunity to run rollback.
            restore_start_lease_if_needed()
            if start_invoked:
                drain_and_contain_started_boundary()
            outcome = current_outcome()
        finally:
            restore_start_lease_if_needed()
            if start_invoked:
                drain_and_contain_started_boundary()
            try:
                if receive_connection is not None:
                    receive_connection.close()
            except BaseException:
                pass
            try:
                if send_connection is not None:
                    send_connection.close()
            except BaseException:
                pass
            outcome = current_outcome()
        return outcome


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
} | set(_ADOPTION_STAGE_FIELDS)
_ADOPTION_WORKER_REUSE_KEYS = _ADOPTION_WORKER_SUCCESS_KEYS | {
    "secret_prompt_performed",
    "existing_registration_reused",
    "workspace_scope_migrated",
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
} | set(_ADOPTION_STAGE_FIELDS)
_ADOPTION_WORKER_FAILURE_REASONS = {
    "credential_input_cancelled_or_empty",
    "credential_input_not_received",
    "credential_input_invalid_for_provider",
    "credential_input_boundary_failed",
    "provider_request_not_attempted",
    "provider_auth_rejected",
    "provider_identity_endpoint_unavailable",
    "reviewed_anchor_inaccessible",
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
    "credential_adoption_existing_registry_untrusted",
    "credential_adoption_existing_registrations_require_lifecycle_review",
    "credential_adoption_existing_store_missing",
    "credential_adoption_existing_store_probe_failed",
    "credential_adoption_existing_store_fingerprint_mismatch",
    "credential_adoption_existing_scope_revalidation_failed",
    "credential_adoption_existing_scope_migration_failed",
}
_ADOPTION_WORKER_FAILURE_REASON_CANONICAL = {
    reason: reason for reason in _ADOPTION_WORKER_FAILURE_REASONS
}
_ADOPTION_WORKER_REUSE_REASON_CANONICAL = {
    "credential_adoption_existing_registration_preserved_without_prompt": (
        "credential_adoption_existing_registration_preserved_without_prompt"
    ),
    "credential_adoption_legacy_scope_evolved_without_prompt": (
        "credential_adoption_legacy_scope_evolved_without_prompt"
    ),
}
_ADOPTION_PERSISTED_FAILURE_REASONS = {
    "credential_adoption_archive_identity_changed",
    "credential_adoption_rediscovery_verification_failed",
}
_STAGE_0000 = (False, False, False, False)
_STAGE_1000 = (True, False, False, False)
_STAGE_1100 = (True, True, False, False)
_STAGE_1110 = (True, True, True, False)
_STAGE_1111 = (True, True, True, True)
_STAGE_0001_REUSE = (False, False, False, True)

_ADOPTION_INPUT_NOT_RECEIVED_REASONS = {
    "credential_input_not_received",
}
_ADOPTION_ZERO_EVIDENCE_LEGACY_REASONS = {
    "secret_input_unavailable",
    "human_cancelled",
}
_ADOPTION_COMPLETE_LOCAL_INPUT_REASONS = {
    "credential_input_invalid_for_provider",
}
_ADOPTION_INPUT_BOUNDARY_REASONS = {
    "credential_input_boundary_failed",
}
_ADOPTION_PRE_PROVIDER_STORE_REASONS = {
    "store_write_failed",
    "store_presence_not_verified",
    "provider_request_not_attempted",
}
_ADOPTION_PROVIDER_STAGE_REASONS = {
    "provider_auth_rejected",
    "provider_identity_endpoint_unavailable",
    "reviewed_anchor_inaccessible",
    "provider_identity_unverified",
    "workspace_anchor_mismatch",
    "receipt_commit_failed",
}
_ADOPTION_PRE_EXECUTION_REASONS = {
    "request_expired",
    "request_replayed",
    "request_user_mismatch",
    "request_claim_failed",
    "plan_digest_mismatch",
    "worker_launch_failed",
    "credential_adoption_archive_identity_mismatch",
    "credential_adoption_preflight_failed",
    "credential_adoption_existing_registry_untrusted",
}
_ADOPTION_EXISTING_OPTIONAL_REVALIDATION_REASONS = {
    "credential_adoption_existing_registrations_require_lifecycle_review",
    "credential_adoption_existing_store_missing",
    "credential_adoption_existing_store_probe_failed",
    "credential_adoption_existing_store_fingerprint_mismatch",
    "credential_adoption_existing_scope_revalidation_failed",
    "credential_adoption_existing_scope_migration_failed",
}


def _adoption_failure_stage_valid(
    reason: str,
    evidence: Mapping[str, bool],
) -> bool:
    vector = tuple(evidence[field] for field in _ADOPTION_STAGE_FIELDS)
    if reason in _ADOPTION_INPUT_NOT_RECEIVED_REASONS:
        return vector in {_STAGE_0000, _STAGE_1000}
    if reason in _ADOPTION_ZERO_EVIDENCE_LEGACY_REASONS:
        return vector == _STAGE_0000
    if reason == "credential_input_cancelled_or_empty":
        return vector in {_STAGE_0000, _STAGE_1000, _STAGE_1100}
    if reason in _ADOPTION_COMPLETE_LOCAL_INPUT_REASONS:
        return vector == _STAGE_1100
    if reason in _ADOPTION_INPUT_BOUNDARY_REASONS:
        return vector in {_STAGE_1000, _STAGE_1100}
    if reason in _ADOPTION_PRE_PROVIDER_STORE_REASONS:
        return vector == _STAGE_1110
    if reason in _ADOPTION_PROVIDER_STAGE_REASONS:
        return vector == _STAGE_1111
    if reason in _ADOPTION_PRE_EXECUTION_REASONS:
        return vector == _STAGE_0000
    if reason in _ADOPTION_EXISTING_OPTIONAL_REVALIDATION_REASONS:
        return vector in {_STAGE_0000, _STAGE_0001_REUSE}
    if reason in _ADOPTION_PERSISTED_FAILURE_REASONS:
        return vector == _STAGE_1111
    if reason == "worker_result_invalid":
        return vector in {
            _STAGE_0000,
            _STAGE_1000,
            _STAGE_1100,
            _STAGE_1110,
            _STAGE_1111,
        }
    return False


def _approved_adoption_worker_operations_are_exact(value: Any) -> bool:
    """Accept the fixed operations shape only with plain-string enums."""

    return (
        isinstance(value, Mapping)
        and type(value.get("live_operation_boundary")) is str
        and type(value.get("count_status")) is str
        and value == _approved_adoption_worker_operations()
    )


def _project_adoption_worker_result_unchecked(
    result: Mapping[str, Any],
) -> dict[str, Any]:
    """Strictly reconstruct the only status shapes allowed across the pipe."""

    action = "secure_credential_adoption_execute"
    keys = set(result)
    stage_evidence = _adoption_stage_evidence_from_mapping(result)
    if (
        stage_evidence is None
        or type(result.get("schema_version")) is not str
        or type(result.get("lifecycle_action")) is not str
        or type(result.get("reason_code")) is not str
    ):
        return _uncertain_adoption_worker_result()
    if result.get("ok") is True:
        credential_id = result.get("credential_id")
        reason = result.get("reason_code")
        reuse_reason = _ADOPTION_WORKER_REUSE_REASON_CANONICAL.get(reason)
        if reuse_reason is not None:
            migrated = reuse_reason == (
                "credential_adoption_legacy_scope_evolved_without_prompt"
            )
            expected_reuse = {
                "schema_version": WORKFLOW_RESULT_SCHEMA_VERSION,
                "ok": True,
                "lifecycle_action": action,
                "accepted": False,
                "persisted": True,
                "reason_code": reuse_reason,
                "credential_id": credential_id,
                "authenticated_rediscovery_verified": True,
                "human_default_decision_required": result.get(
                    "human_default_decision_required"
                ),
                "secret_prompt_performed": False,
                "existing_registration_reused": True,
                "workspace_scope_migrated": migrated,
                "secret_value_present": False,
                "reviewed_anchor_present_in_result": False,
                "backend_target_present": False,
                "crash_or_power_loss_rollback_guaranteed": False,
                "operations": _approved_adoption_worker_operations(),
                **stage_evidence,
            }
            if not (
                keys == _ADOPTION_WORKER_REUSE_KEYS
                and tuple(
                    stage_evidence[field] for field in _ADOPTION_STAGE_FIELDS
                )
                == _STAGE_0001_REUSE
                and type(credential_id) is str
                and _CREDENTIAL_ID_RE.fullmatch(credential_id)
                and isinstance(result.get("human_default_decision_required"), bool)
                and _approved_adoption_worker_operations_are_exact(
                    result.get("operations")
                )
                and dict(result) == expected_reuse
            ):
                return _uncertain_adoption_worker_result()
            return expected_reuse
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
            **stage_evidence,
        }
        if not (
            keys == _ADOPTION_WORKER_SUCCESS_KEYS
            and result.get("schema_version") == WORKFLOW_RESULT_SCHEMA_VERSION
            and result.get("lifecycle_action") == action
            and result.get("accepted") is True
            and result.get("persisted") is True
            and result.get("reason_code")
            == "credential_adoption_persisted_and_rediscoverable"
            and type(credential_id) is str
            and _CREDENTIAL_ID_RE.fullmatch(credential_id)
            and result.get("authenticated_rediscovery_verified") is True
            and isinstance(result.get("human_default_decision_required"), bool)
            and result.get("secret_value_present") is False
            and result.get("reviewed_anchor_present_in_result") is False
            and result.get("backend_target_present") is False
            and result.get("crash_or_power_loss_rollback_guaranteed") is False
            and _approved_adoption_worker_operations_are_exact(
                result.get("operations")
            )
            and tuple(stage_evidence[field] for field in _ADOPTION_STAGE_FIELDS)
            == _STAGE_1111
            and dict(result) == expected_success
        ):
            return _uncertain_adoption_worker_result()
        return expected_success
    if keys != _ADOPTION_WORKER_FAILURE_KEYS:
        return _uncertain_adoption_worker_result()
    raw_reason = result.get("reason_code")
    raw_rollback = result.get("rollback_status")
    if (
        type(raw_rollback) is not str
        or type(result.get("operator_action")) is not str
    ):
        return _uncertain_adoption_worker_result()
    reason = _ADOPTION_WORKER_FAILURE_REASON_CANONICAL.get(raw_reason)
    rollback = _WORKFLOW_ROLLBACK_CANONICAL.get(raw_rollback)
    expected_persisted = reason in _ADOPTION_PERSISTED_FAILURE_REASONS
    if not (
        result.get("schema_version") == WORKFLOW_RESULT_SCHEMA_VERSION
        and result.get("lifecycle_action") == action
        and result.get("ok") is False
        and isinstance(result.get("accepted"), bool)
        and isinstance(result.get("persisted"), bool)
        and result.get("accepted") is expected_persisted
        and result.get("persisted") is expected_persisted
        and reason is not None
        and rollback is not None
        and _adoption_failure_stage_valid(reason, stage_evidence)
        and (
            (
                expected_persisted
                and rollback == "not_required"
            )
            or (
                not expected_persisted
                and stage_evidence["temporary_store_write_attempted"] is False
                and rollback == "not_required"
            )
            or (
                not expected_persisted
                and stage_evidence["temporary_store_write_attempted"] is True
                and rollback in {"deleted", "delete_failed"}
            )
        )
        and result.get("credential_id_present") is False
        and result.get("secret_value_present") is False
        and result.get("reviewed_anchor_present_in_result") is False
        and result.get("backend_target_present") is False
        and result.get("crash_or_power_loss_rollback_guaranteed") is False
        and _approved_adoption_worker_operations_are_exact(
            result.get("operations")
        )
    ):
        return _uncertain_adoption_worker_result()
    expected_failure = _approved_adoption_worker_failure(
        reason,
        accepted=result["accepted"],
        persisted=result["persisted"],
        rollback_status=rollback,
        **stage_evidence,
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
        _reviewed_plan, _prompt_context, interaction_context_sha256 = _rebuild_approved_planning_contract(
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
            expected_interaction_context_sha256=interaction_context_sha256,
            replacement_approved=approval_plan["replacement_approved"],
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
        if run_outcome.worker_started is False and run_outcome.result is None:
            return _workflow_failure(
                action,
                "credential_adoption_worker_launch_failed",
            )
        if run_outcome.worker_started is not True:
            return _uncertain_adoption_worker_result()
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
