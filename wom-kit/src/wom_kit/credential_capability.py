"""Strict, secret-free capability values for live Notion recovery.

The capability is an invocation authority descriptor, not a secret container.
It is issued in the parent process after explicit human approval, then checked
and durably claimed by the isolated recovery worker before any credential read.

This module deliberately does not persist claims or authenticate claim files.
The receipt-backed registry owns that boundary.  ``CredentialCapabilityLease``
is the small, thread-safe in-memory budget used only after a durable claim has
been committed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import re
import secrets
import threading
from typing import Any, ClassVar, Mapping, Sequence


CREDENTIAL_CAPABILITY_SCHEMA = "wom-kit/credential-capability/v0.1"
CREDENTIAL_CAPABILITY_PROVIDER = "notion"
CREDENTIAL_CAPABILITY_OPERATION = "notion_page_recovery_read"
CREDENTIAL_CAPABILITY_CONSUMER = "wom:workflow:notion-page-recovery"
CREDENTIAL_CAPABILITY_APPROVAL_DECISION = "approve_once"

CREDENTIAL_CAPABILITY_ALLOWED_METHODS = ("GET",)
CREDENTIAL_CAPABILITY_ENDPOINT_CLASSES = (
    "retrieve_page",
    "retrieve_page_as_markdown",
)
CREDENTIAL_CAPABILITY_REQUIRED_REGISTERED_CAPABILITIES = (
    "read_content",
    "retrieve_page",
    "retrieve_page_as_markdown",
)

DEFAULT_CAPABILITY_TTL_SECONDS = 900
MIN_CAPABILITY_TTL_SECONDS = 30
MAX_CAPABILITY_TTL_SECONDS = 3600
MAX_CAPABILITY_SCOPES = 1000
# The workflow binds a much smaller exact logical-provider-attempt budget from
# the approved plan.  This defensive protocol ceiling leaves room for bounded
# retry-policy evolution while still rejecting implausibly large documents.
MAX_CAPABILITY_PROVIDER_REQUESTS = 5_000_000

_CAPABILITY_ID_RE = re.compile(r"^cap_[0-9a-f]{32}$")
_CREDENTIAL_ID_RE = re.compile(r"^cred_[A-Za-z0-9_-]{16,96}$")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SAFE_REVISION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+-]{0,127}$")
_SAFE_REVIEWER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@:+-]{0,127}$")
_SECRET_SHAPE_RE = re.compile(
    r"(?i)(?:github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{8,}"
    r"|(?:secret|ntn)_[A-Za-z0-9_-]{12,})"
)
_UTC_TIMESTAMP_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
)
_ERROR_CODE_RE = re.compile(r"^credential_capability_[a-z0-9_]{1,96}$")

_CAPABILITY_DOCUMENT_KEYS = frozenset(
    {
        "schema",
        "capability_id",
        "provider",
        "operation",
        "consumer",
        "approval_decision",
        "reviewed_by",
        "allowed_methods",
        "endpoint_classes",
        "required_registered_capabilities",
        "request_sha256",
        "plan_sha256",
        "scopes",
        "issued_at",
        "expires_at",
        "ttl_seconds",
        "max_uses",
        "max_provider_requests",
    }
)
_SCOPE_DOCUMENT_KEYS = frozenset(
    {
        "credential_id",
        "workspace_fingerprint",
        "scope_receipt_sha256",
        "revision",
    }
)


class CredentialCapabilityError(RuntimeError):
    """A content-free capability validation or authorization failure."""

    def __init__(self, code: str) -> None:
        safe_code = (
            code
            if _is_exact_string(code) and _ERROR_CODE_RE.fullmatch(code) is not None
            else "credential_capability_error"
        )
        self.code = safe_code
        super().__init__(safe_code)


def _fail(code: str) -> CredentialCapabilityError:
    return CredentialCapabilityError(code)


def _is_exact_string(value: object) -> bool:
    return type(value) is str


def _is_exact_int(value: object) -> bool:
    # ``bool`` is an ``int`` subclass and must never satisfy a budget field.
    return type(value) is int


def _validate_exact_utc_datetime(value: datetime, *, code: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise _fail(code)
    try:
        offset = value.utcoffset()
    except Exception:
        raise _fail(code) from None
    if offset != timedelta(0):
        raise _fail(code)
    return value.astimezone(timezone.utc)


def _format_exact_utc(value: datetime) -> str:
    normalized = _validate_exact_utc_datetime(
        value, code="credential_capability_time_invalid"
    ).replace(microsecond=0)
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_exact_utc(value: object, *, code: str) -> datetime:
    if not _is_exact_string(value) or _UTC_TIMESTAMP_RE.fullmatch(value) is None:
        raise _fail(code)
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise _fail(code) from None
    return parsed.replace(tzinfo=timezone.utc)


def _canonical_json_bytes(document: Mapping[str, Any]) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class CredentialCapabilityScope:
    """One exact receipt/lifecycle scope, with identifying values redacted."""

    credential_id: str
    workspace_fingerprint: str
    scope_receipt_sha256: str
    revision: str

    def __post_init__(self) -> None:
        if (
            not _is_exact_string(self.credential_id)
            or _CREDENTIAL_ID_RE.fullmatch(self.credential_id) is None
        ):
            raise _fail("credential_capability_scope_credential_invalid")
        if (
            not _is_exact_string(self.workspace_fingerprint)
            or _SHA256_RE.fullmatch(self.workspace_fingerprint) is None
        ):
            raise _fail("credential_capability_scope_workspace_invalid")
        if (
            not _is_exact_string(self.scope_receipt_sha256)
            or _SHA256_RE.fullmatch(self.scope_receipt_sha256) is None
        ):
            raise _fail("credential_capability_scope_receipt_invalid")
        if (
            not _is_exact_string(self.revision)
            or _SAFE_REVISION_RE.fullmatch(self.revision) is None
        ):
            raise _fail("credential_capability_scope_revision_invalid")

    def __repr__(self) -> str:
        return "<CredentialCapabilityScope redacted>"

    @property
    def sort_key(self) -> tuple[str, str, str, str]:
        return (
            self.credential_id,
            self.workspace_fingerprint,
            self.scope_receipt_sha256,
            self.revision,
        )

    def canonical_document(self) -> dict[str, str]:
        return {
            "credential_id": self.credential_id,
            "workspace_fingerprint": self.workspace_fingerprint,
            "scope_receipt_sha256": self.scope_receipt_sha256,
            "revision": self.revision,
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "CredentialCapabilityScope":
        if type(document) is not dict or set(document) != _SCOPE_DOCUMENT_KEYS:
            raise _fail("credential_capability_scope_document_invalid")
        return cls(
            credential_id=document["credential_id"],
            workspace_fingerprint=document["workspace_fingerprint"],
            scope_receipt_sha256=document["scope_receipt_sha256"],
            revision=document["revision"],
        )


def _strict_scopes(
    scopes: Sequence[CredentialCapabilityScope],
    *,
    sort_for_issue: bool,
) -> tuple[CredentialCapabilityScope, ...]:
    if type(scopes) not in {list, tuple} or not scopes:
        raise _fail("credential_capability_scopes_invalid")
    if len(scopes) > MAX_CAPABILITY_SCOPES or any(
        type(scope) is not CredentialCapabilityScope for scope in scopes
    ):
        raise _fail("credential_capability_scopes_invalid")
    values = tuple(scopes)
    sorted_values = tuple(sorted(values, key=lambda scope: scope.sort_key))
    if len(set(sorted_values)) != len(sorted_values):
        raise _fail("credential_capability_scopes_duplicate")
    if not sort_for_issue and values != sorted_values:
        raise _fail("credential_capability_scopes_unsorted")
    return sorted_values


@dataclass(frozen=True, slots=True)
class CredentialCapability:
    """One strict, single-invocation Notion recovery capability."""

    schema: str
    capability_id: str
    provider: str
    operation: str
    consumer: str
    approval_decision: str
    reviewed_by: str
    allowed_methods: tuple[str, ...]
    endpoint_classes: tuple[str, ...]
    required_registered_capabilities: tuple[str, ...]
    request_sha256: str
    plan_sha256: str
    scopes: tuple[CredentialCapabilityScope, ...]
    issued_at: str
    expires_at: str
    ttl_seconds: int
    max_uses: int
    max_provider_requests: int

    SCHEMA: ClassVar[str] = CREDENTIAL_CAPABILITY_SCHEMA

    def __post_init__(self) -> None:
        if (
            not _is_exact_string(self.schema)
            or self.schema != CREDENTIAL_CAPABILITY_SCHEMA
        ):
            raise _fail("credential_capability_schema_invalid")
        if (
            not _is_exact_string(self.capability_id)
            or _CAPABILITY_ID_RE.fullmatch(self.capability_id) is None
        ):
            raise _fail("credential_capability_id_invalid")
        if (
            not _is_exact_string(self.provider)
            or self.provider != CREDENTIAL_CAPABILITY_PROVIDER
        ):
            raise _fail("credential_capability_provider_invalid")
        if (
            not _is_exact_string(self.operation)
            or self.operation != CREDENTIAL_CAPABILITY_OPERATION
        ):
            raise _fail("credential_capability_operation_invalid")
        if (
            not _is_exact_string(self.consumer)
            or self.consumer != CREDENTIAL_CAPABILITY_CONSUMER
        ):
            raise _fail("credential_capability_consumer_invalid")
        if (
            not _is_exact_string(self.approval_decision)
            or self.approval_decision != CREDENTIAL_CAPABILITY_APPROVAL_DECISION
        ):
            raise _fail("credential_capability_approval_invalid")
        if (
            not _is_exact_string(self.reviewed_by)
            or _SAFE_REVIEWER_RE.fullmatch(self.reviewed_by) is None
            or _SECRET_SHAPE_RE.search(self.reviewed_by) is not None
        ):
            raise _fail("credential_capability_reviewer_invalid")
        if (
            type(self.allowed_methods) is not tuple
            or any(not _is_exact_string(item) for item in self.allowed_methods)
            or self.allowed_methods != CREDENTIAL_CAPABILITY_ALLOWED_METHODS
        ):
            raise _fail("credential_capability_methods_invalid")
        if (
            type(self.endpoint_classes) is not tuple
            or any(not _is_exact_string(item) for item in self.endpoint_classes)
            or self.endpoint_classes != CREDENTIAL_CAPABILITY_ENDPOINT_CLASSES
        ):
            raise _fail("credential_capability_endpoints_invalid")
        if (
            type(self.required_registered_capabilities) is not tuple
            or any(
                not _is_exact_string(item)
                for item in self.required_registered_capabilities
            )
            or self.required_registered_capabilities
            != CREDENTIAL_CAPABILITY_REQUIRED_REGISTERED_CAPABILITIES
        ):
            raise _fail("credential_capability_registered_capabilities_invalid")
        if (
            not _is_exact_string(self.request_sha256)
            or _SHA256_RE.fullmatch(self.request_sha256) is None
        ):
            raise _fail("credential_capability_request_digest_invalid")
        if (
            not _is_exact_string(self.plan_sha256)
            or _SHA256_RE.fullmatch(self.plan_sha256) is None
        ):
            raise _fail("credential_capability_plan_digest_invalid")
        if type(self.scopes) is not tuple:
            raise _fail("credential_capability_scopes_invalid")
        _strict_scopes(self.scopes, sort_for_issue=False)
        if (
            not _is_exact_int(self.ttl_seconds)
            or self.ttl_seconds < MIN_CAPABILITY_TTL_SECONDS
            or self.ttl_seconds > MAX_CAPABILITY_TTL_SECONDS
        ):
            raise _fail("credential_capability_ttl_invalid")
        if not _is_exact_int(self.max_uses) or self.max_uses != 1:
            raise _fail("credential_capability_max_uses_invalid")
        if (
            not _is_exact_int(self.max_provider_requests)
            or self.max_provider_requests < 1
            or self.max_provider_requests > MAX_CAPABILITY_PROVIDER_REQUESTS
        ):
            raise _fail("credential_capability_request_budget_invalid")
        issued = _parse_exact_utc(
            self.issued_at, code="credential_capability_issued_at_invalid"
        )
        expires = _parse_exact_utc(
            self.expires_at, code="credential_capability_expires_at_invalid"
        )
        if expires - issued != timedelta(seconds=self.ttl_seconds):
            raise _fail("credential_capability_expiry_window_invalid")

    def __repr__(self) -> str:
        return (
            "<CredentialCapability provider=notion "
            "operation=notion_page_recovery_read bindings=redacted>"
        )

    @classmethod
    def issue(
        cls,
        *,
        request_sha256: str,
        plan_sha256: str,
        scopes: Sequence[CredentialCapabilityScope],
        reviewed_by: str,
        max_provider_requests: int,
        issued_at: datetime | None = None,
        ttl_seconds: int = DEFAULT_CAPABILITY_TTL_SECONDS,
    ) -> "CredentialCapability":
        """Issue a fresh 128-bit parent-side capability after approval."""

        if issued_at is None:
            issued_at = datetime.now(timezone.utc)
        issued = _validate_exact_utc_datetime(
            issued_at, code="credential_capability_issued_at_invalid"
        ).replace(microsecond=0)
        if (
            not _is_exact_int(ttl_seconds)
            or ttl_seconds < MIN_CAPABILITY_TTL_SECONDS
            or ttl_seconds > MAX_CAPABILITY_TTL_SECONDS
        ):
            raise _fail("credential_capability_ttl_invalid")
        sorted_scopes = _strict_scopes(scopes, sort_for_issue=True)
        capability_id = "cap_" + secrets.token_hex(16)
        if _CAPABILITY_ID_RE.fullmatch(capability_id) is None:
            raise _fail("credential_capability_id_generation_failed")
        return cls(
            schema=CREDENTIAL_CAPABILITY_SCHEMA,
            capability_id=capability_id,
            provider=CREDENTIAL_CAPABILITY_PROVIDER,
            operation=CREDENTIAL_CAPABILITY_OPERATION,
            consumer=CREDENTIAL_CAPABILITY_CONSUMER,
            approval_decision=CREDENTIAL_CAPABILITY_APPROVAL_DECISION,
            reviewed_by=reviewed_by,
            allowed_methods=CREDENTIAL_CAPABILITY_ALLOWED_METHODS,
            endpoint_classes=CREDENTIAL_CAPABILITY_ENDPOINT_CLASSES,
            required_registered_capabilities=(
                CREDENTIAL_CAPABILITY_REQUIRED_REGISTERED_CAPABILITIES
            ),
            request_sha256=request_sha256,
            plan_sha256=plan_sha256,
            scopes=sorted_scopes,
            issued_at=_format_exact_utc(issued),
            expires_at=_format_exact_utc(issued + timedelta(seconds=ttl_seconds)),
            ttl_seconds=ttl_seconds,
            max_uses=1,
            max_provider_requests=max_provider_requests,
        )

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "CredentialCapability":
        """Parse one exact document and reject missing or unknown fields."""

        if type(document) is not dict or set(document) != _CAPABILITY_DOCUMENT_KEYS:
            raise _fail("credential_capability_document_invalid")
        scopes_document = document["scopes"]
        if type(scopes_document) is not list:
            raise _fail("credential_capability_scopes_invalid")
        scopes = tuple(
            CredentialCapabilityScope.from_document(scope)
            for scope in scopes_document
        )
        for key in (
            "allowed_methods",
            "endpoint_classes",
            "required_registered_capabilities",
        ):
            if type(document[key]) is not list:
                raise _fail("credential_capability_document_invalid")
        return cls(
            schema=document["schema"],
            capability_id=document["capability_id"],
            provider=document["provider"],
            operation=document["operation"],
            consumer=document["consumer"],
            approval_decision=document["approval_decision"],
            reviewed_by=document["reviewed_by"],
            allowed_methods=tuple(document["allowed_methods"]),
            endpoint_classes=tuple(document["endpoint_classes"]),
            required_registered_capabilities=tuple(
                document["required_registered_capabilities"]
            ),
            request_sha256=document["request_sha256"],
            plan_sha256=document["plan_sha256"],
            scopes=scopes,
            issued_at=document["issued_at"],
            expires_at=document["expires_at"],
            ttl_seconds=document["ttl_seconds"],
            max_uses=document["max_uses"],
            max_provider_requests=document["max_provider_requests"],
        )

    def canonical_document(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "capability_id": self.capability_id,
            "provider": self.provider,
            "operation": self.operation,
            "consumer": self.consumer,
            "approval_decision": self.approval_decision,
            "reviewed_by": self.reviewed_by,
            "allowed_methods": list(self.allowed_methods),
            "endpoint_classes": list(self.endpoint_classes),
            "required_registered_capabilities": list(
                self.required_registered_capabilities
            ),
            "request_sha256": self.request_sha256,
            "plan_sha256": self.plan_sha256,
            "scopes": [scope.canonical_document() for scope in self.scopes],
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "ttl_seconds": self.ttl_seconds,
            "max_uses": self.max_uses,
            "max_provider_requests": self.max_provider_requests,
        }

    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(
            _canonical_json_bytes(self.canonical_document())
        ).hexdigest()

    @property
    def digest_sha256(self) -> str:
        return self.digest()

    def assert_active(self, *, now_utc: datetime) -> None:
        now = _validate_exact_utc_datetime(
            now_utc, code="credential_capability_now_invalid"
        )
        issued = _parse_exact_utc(
            self.issued_at, code="credential_capability_issued_at_invalid"
        )
        expires = _parse_exact_utc(
            self.expires_at, code="credential_capability_expires_at_invalid"
        )
        if now < issued:
            raise _fail("credential_capability_not_yet_valid")
        if now >= expires:
            raise _fail("credential_capability_expired")

    def validate_recovery_binding(
        self,
        *,
        request_sha256: str,
        plan_sha256: str,
        scopes: Sequence[CredentialCapabilityScope],
        reviewed_by: str,
        now_utc: datetime,
    ) -> None:
        """Recompute and validate all caller-controlled recovery bindings."""

        self.assert_active(now_utc=now_utc)
        if (
            not _is_exact_string(request_sha256)
            or _SHA256_RE.fullmatch(request_sha256) is None
            or not hmac.compare_digest(self.request_sha256, request_sha256)
        ):
            raise _fail("credential_capability_request_mismatch")
        if (
            not _is_exact_string(plan_sha256)
            or _SHA256_RE.fullmatch(plan_sha256) is None
            or not hmac.compare_digest(self.plan_sha256, plan_sha256)
        ):
            raise _fail("credential_capability_plan_mismatch")
        if (
            not _is_exact_string(reviewed_by)
            or not hmac.compare_digest(self.reviewed_by, reviewed_by)
        ):
            raise _fail("credential_capability_reviewer_mismatch")
        try:
            expected_scopes = _strict_scopes(scopes, sort_for_issue=True)
        except CredentialCapabilityError:
            raise _fail("credential_capability_scope_mismatch") from None
        if expected_scopes != self.scopes:
            raise _fail("credential_capability_scope_mismatch")

    def new_lease(self, *, claimed_at: datetime) -> "CredentialCapabilityLease":
        """Create the in-memory budget after the registry commits a claim."""

        self.assert_active(now_utc=claimed_at)
        return CredentialCapabilityLease(self, claimed_at=claimed_at)


class CredentialCapabilityLease:
    """Thread-safe scope, endpoint, and provider-request budget after claim.

    ``expires_at`` is deliberately a claim deadline.  Once the registry has
    committed the single invocation claim and constructed this lease, a long
    recovery does not lose authority merely because wall-clock time advances.
    """

    __slots__ = (
        "_capability",
        "_provider_requests_authorized",
        "_lock",
    )

    def __init__(
        self,
        capability: CredentialCapability,
        *,
        claimed_at: datetime,
    ) -> None:
        if type(capability) is not CredentialCapability:
            raise _fail("credential_capability_lease_invalid")
        claimed = _validate_exact_utc_datetime(
            claimed_at, code="credential_capability_claimed_at_invalid"
        )
        capability.assert_active(now_utc=claimed)
        self._capability = capability
        self._provider_requests_authorized = 0
        self._lock = threading.Lock()

    def __repr__(self) -> str:
        return "<CredentialCapabilityLease bindings=redacted>"

    @property
    def capability(self) -> CredentialCapability:
        return self._capability

    @property
    def provider_requests_authorized(self) -> int:
        with self._lock:
            return self._provider_requests_authorized

    @property
    def provider_requests_remaining(self) -> int:
        with self._lock:
            return (
                self._capability.max_provider_requests
                - self._provider_requests_authorized
            )

    def authorize_request(
        self,
        endpoint_class: str,
        *,
        scope: CredentialCapabilityScope,
    ) -> int:
        """Atomically authorize one provider attempt and return its sequence."""

        if (
            not _is_exact_string(endpoint_class)
            or endpoint_class not in self._capability.endpoint_classes
        ):
            raise _fail("credential_capability_endpoint_not_allowed")
        if type(scope) is not CredentialCapabilityScope:
            raise _fail("credential_capability_scope_not_allowed")
        with self._lock:
            if scope not in self._capability.scopes:
                raise _fail("credential_capability_scope_not_allowed")
            if (
                self._provider_requests_authorized
                >= self._capability.max_provider_requests
            ):
                raise _fail("credential_capability_request_budget_exhausted")
            self._provider_requests_authorized += 1
            return self._provider_requests_authorized


__all__ = [
    "CREDENTIAL_CAPABILITY_ALLOWED_METHODS",
    "CREDENTIAL_CAPABILITY_APPROVAL_DECISION",
    "CREDENTIAL_CAPABILITY_CONSUMER",
    "CREDENTIAL_CAPABILITY_ENDPOINT_CLASSES",
    "CREDENTIAL_CAPABILITY_OPERATION",
    "CREDENTIAL_CAPABILITY_PROVIDER",
    "CREDENTIAL_CAPABILITY_REQUIRED_REGISTERED_CAPABILITIES",
    "CREDENTIAL_CAPABILITY_SCHEMA",
    "CredentialCapability",
    "CredentialCapabilityError",
    "CredentialCapabilityLease",
    "CredentialCapabilityScope",
    "DEFAULT_CAPABILITY_TTL_SECONDS",
    "MAX_CAPABILITY_PROVIDER_REQUESTS",
    "MAX_CAPABILITY_SCOPES",
    "MAX_CAPABILITY_TTL_SECONDS",
    "MIN_CAPABILITY_TTL_SECONDS",
]
