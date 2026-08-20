"""Small, live-capable Notion GET adapter with content-free failures.

The adapter is deliberately transport-injected.  Production callers may use
the stdlib opener created by default, while tests and planning code can provide
an opener without touching the network.  Authorization exists only on the
ephemeral ``urllib.request.Request`` passed to that transport; it is never
retained in public results, exceptions, or object representations.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
import codecs
from datetime import datetime
import hashlib
import json
import math
import random
import re
import time
from typing import Any, Callable, Mapping, Protocol
from urllib import error as urllib_error
from urllib import request as urllib_request
import uuid

from .credential_secure_intake import (
    CredentialIntakeStageError,
    NOTION_PAT_WORKSPACE_IDENTITY_BASIS,
    NOTION_WORKSPACE_IDENTITY_BASIS,
)
from .notion_page_recovery import NOTION_API_VERSION, ProviderResponse


OFFICIAL_NOTION_API_BASE = "https://api.notion.com"
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MIN_RESPONSE_BYTES = 1024
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
MAX_TIMEOUT_SECONDS = 60.0
MAX_ADAPTER_ATTEMPTS = 5
DEFAULT_MAX_RETRY_DELAY_SECONDS = 60.0
_RETRYABLE_STATUSES = {409, 429, 500, 502, 503, 504, 529, 599}

_SAFE_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SAFE_RETRY_AFTER_RE = re.compile(r"^[0-9]{1,9}(?:\.[0-9]{1,3})?$")
_CAPABILITIES = {
    "read_content": True,
    "retrieve_page": True,
    "retrieve_page_as_markdown": True,
    "retrieve_user_identity": True,
    "verify_identity_with_reviewed_anchor": True,
}
_SECURE_INTAKE_CAPABILITIES = tuple(sorted(_CAPABILITIES))


class NotionHttpAdapterError(RuntimeError):
    """Configuration failure containing only a stable reason code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class HttpTransport(Protocol):
    def open(self, request: urllib_request.Request, *, timeout: float) -> Any: ...


class _NoRedirectHandler(urllib_request.HTTPRedirectHandler):
    """Refuse redirects so a bearer is never forwarded to another origin."""

    def redirect_request(
        self,
        request: urllib_request.Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Mapping[str, str],
        new_url: str,
    ) -> None:
        return None


class _NotionBearerSecret:
    """A short-lived mutable bearer whose public forms are always redacted.

    A receipt-backed broker may bind a content-free authority revalidator.
    Recovery calls it immediately before each provider attempt so a lifecycle
    revision/default change cannot silently keep authorizing this cached bearer.
    The callback never exposes or rereads the bearer itself.
    """

    __slots__ = (
        "__value",
        "__closed",
        "__authority_revalidator",
        "__capability_authorizer",
    )

    def __init__(self, value: str) -> None:
        if not isinstance(value, str):
            raise NotionHttpAdapterError("notion_secret_invalid")
        try:
            mutable = bytearray(value, "ascii")
        except (UnicodeError, ValueError):
            raise NotionHttpAdapterError("notion_secret_invalid") from None
        self._adopt_mutable(mutable)

    @classmethod
    def _from_owned_mutable(cls, value: bytearray) -> "_NotionBearerSecret":
        """Take ownership of one exact native buffer without copying it."""

        instance = cls.__new__(cls)
        instance._adopt_mutable(value)
        return instance

    def _adopt_mutable(self, value: bytearray) -> None:
        if (
            not isinstance(value, bytearray)
            or not value
            or len(value) > 4096
            or any(byte < 33 or byte > 126 for byte in value)
        ):
            if isinstance(value, bytearray):
                for index in range(len(value)):
                    value[index] = 0
            raise NotionHttpAdapterError("notion_secret_invalid")
        self.__value = value
        self.__closed = False
        self.__authority_revalidator: Callable[[], None] | None = None
        self.__capability_authorizer: Callable[[str], None] | None = None

    def __repr__(self) -> str:
        return "<_NotionBearerSecret redacted>"

    def __str__(self) -> str:
        return "[redacted]"

    def _authorization_value(self) -> str:
        if self.__closed:
            raise NotionHttpAdapterError("notion_secret_closed")
        return "Bearer " + codecs.decode(self.__value, "ascii", errors="strict")

    def _bind_authority_revalidator(self, callback: Callable[[], None]) -> None:
        """Bind one broker-owned, content-free authority check exactly once."""

        if self.__closed:
            raise NotionHttpAdapterError("notion_secret_closed")
        if not callable(callback) or self.__authority_revalidator is not None:
            raise NotionHttpAdapterError("notion_authority_revalidator_invalid")
        self.__authority_revalidator = callback

    def _bind_capability_authorizer(
        self,
        callback: Callable[[str], None],
    ) -> None:
        """Bind one broker-owned endpoint capability exactly once.

        The callback receives only a fixed endpoint-class label.  It never
        receives the bearer, URL, request object, response, or page id.
        """

        if self.__closed:
            raise NotionHttpAdapterError("notion_secret_closed")
        if not callable(callback) or self.__capability_authorizer is not None:
            raise NotionHttpAdapterError("notion_capability_authorizer_invalid")
        self.__capability_authorizer = callback

    def revalidate_authority(self) -> None:
        """Revalidate the receipt/lifecycle authority without reading the secret."""

        if self.__closed:
            raise NotionHttpAdapterError("notion_secret_closed")
        callback = self.__authority_revalidator
        if callback is None:
            raise NotionHttpAdapterError("notion_authority_revalidator_missing")
        callback()

    def authorize_provider_request(self, endpoint_class: str) -> None:
        """Consume one fixed endpoint authorization before a provider call."""

        if self.__closed:
            raise NotionHttpAdapterError("notion_secret_closed")
        callback = self.__capability_authorizer
        if callback is None:
            raise NotionHttpAdapterError("notion_capability_authorizer_missing")
        if type(endpoint_class) is not str:
            raise NotionHttpAdapterError("notion_endpoint_class_invalid")
        callback(endpoint_class)

    def close(self) -> None:
        if self.__closed:
            return
        for index in range(len(self.__value)):
            self.__value[index] = 0
        self.__authority_revalidator = None
        self.__capability_authorizer = None
        self.__closed = True


@dataclass(frozen=True)
class _HttpResult:
    status: int
    payload: Mapping[str, Any] | None
    headers: Mapping[str, str]
    reason_code: str | None


class _NotionIdentityVerifier:
    """Callable wrapper suitable for a later secure-intake verifier callback."""

    __slots__ = ("_adapter", "_anchor_page_id", "_anchor_valid")

    def __init__(
        self,
        adapter: "_NotionHttpAdapter",
        reviewed_anchor_page_id: str,
    ) -> None:
        self._adapter = adapter
        normalized = _normalize_uuid(reviewed_anchor_page_id)
        self._anchor_page_id = normalized or ""
        self._anchor_valid = normalized is not None

    def __call__(self, secret: str | _NotionBearerSecret) -> dict[str, Any]:
        if not self._anchor_valid:
            return _identity_evidence("notion_workspace_anchor_id_invalid")
        return self._adapter.verify_identity(secret, self._anchor_page_id)

    def __repr__(self) -> str:
        return "<_NotionIdentityVerifier provider=notion anchor=redacted>"


@dataclass(frozen=True)
class _NotionSecureIntakeIdentity:
    """Duck-typed private identity accepted by credential_secure_intake."""

    provider: str
    account_subject: str = dataclass_field(repr=False)
    workspace_identity: str = dataclass_field(repr=False)
    reviewed_anchor_uuid: str = dataclass_field(repr=False)
    capabilities: tuple[str, ...]
    workspace_identity_basis: str
    subject_verified: bool = True
    anchor_access_verified: bool = True


class _NotionSecureIntakeVerifier:
    """Bridge for ``ProviderIdentityVerifier`` without returning raw ids."""

    __slots__ = ("_adapter",)

    def __init__(self, adapter: "_NotionHttpAdapter") -> None:
        self._adapter = adapter

    def validate_secret_input(self, secret: memoryview, provider: str) -> bool:
        """Validate one provider token locally without decoding or transport.

        Notion bearer values accepted by this bridge are non-empty, bounded,
        printable ASCII byte sequences.  Keeping this check byte-only lets the
        intake worker distinguish malformed console input from a provider
        authentication rejection before it writes or sends anything.
        """

        if provider != "notion" or not isinstance(secret, memoryview):
            return False
        if (
            secret.ndim != 1
            or secret.itemsize != 1
            or secret.format not in {"B", "b", "c"}
            or not secret.contiguous
            or secret.nbytes < 1
            or secret.nbytes > 4096
        ):
            return False
        try:
            octets = secret.cast("B")
            return all(33 <= byte <= 126 for byte in octets)
        except (TypeError, ValueError):
            return False

    def verify_identity(
        self,
        secret: memoryview,
        *,
        provider: str,
        reviewed_anchor_uuid: str,
        provider_request_observer: Callable[[], None],
    ) -> _NotionSecureIntakeIdentity:
        if provider != "notion":
            raise NotionHttpAdapterError("notion_provider_mismatch")
        if not callable(provider_request_observer):
            raise NotionHttpAdapterError("notion_request_observer_invalid")
        if not self.validate_secret_input(secret, provider):
            raise CredentialIntakeStageError(
                "credential_input_invalid_for_provider"
            )
        try:
            # Decode the mutable worker view directly. The provider still
            # needs a short-lived text Authorization header, but this avoids
            # an additional immutable raw-token bytes copy first.
            secret_text = codecs.decode(secret, "ascii", errors="strict")
        except (AttributeError, TypeError, UnicodeDecodeError, ValueError):
            raise CredentialIntakeStageError(
                "credential_input_invalid_for_provider"
            ) from None

        provider_request_attempted = False

        def observe_provider_request_once() -> None:
            nonlocal provider_request_attempted
            if provider_request_attempted:
                return
            provider_request_observer()
            provider_request_attempted = True

        evidence = self._adapter.verify_identity(
            secret_text,
            reviewed_anchor_uuid,
            provider_request_observer=observe_provider_request_once,
        )
        if not (
            evidence.get("identity_verified") is True
            and evidence.get("workspace_anchor_verified") is True
            and isinstance(evidence.get("account_fingerprint"), str)
            and isinstance(evidence.get("workspace_fingerprint"), str)
        ):
            reason = evidence.get("reason_code")
            if not isinstance(reason, str) or not reason.startswith("notion_"):
                reason = "notion_identity_unverified"
            raise CredentialIntakeStageError(
                _secure_intake_stage_reason(
                    reason,
                    evidence=evidence,
                    provider_request_attempted=provider_request_attempted,
                )
            )
        normalized_anchor = _normalize_uuid(reviewed_anchor_uuid)
        if normalized_anchor is None:
            raise CredentialIntakeStageError("reviewed_anchor_inaccessible")
        return _NotionSecureIntakeIdentity(
            provider="notion",
            account_subject=str(evidence["account_fingerprint"]),
            workspace_identity=str(evidence["workspace_fingerprint"]),
            reviewed_anchor_uuid=normalized_anchor,
            capabilities=_SECURE_INTAKE_CAPABILITIES,
            workspace_identity_basis=str(evidence["workspace_identity_basis"]),
        )

    def __repr__(self) -> str:
        return "<_NotionSecureIntakeVerifier provider=notion transport=redacted>"


class _NotionHttpAdapter:
    """Notion 2026-03-11 read-only adapter over one injected stdlib opener."""

    def __init__(
        self,
        *,
        transport: HttpTransport | Callable[..., Any] | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        request_pacer: object | Callable[[], None] | None = None,
        max_attempts: int = 1,
        max_retry_delay_seconds: float = DEFAULT_MAX_RETRY_DELAY_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or not math.isfinite(float(timeout_seconds))
            or float(timeout_seconds) <= 0
            or float(timeout_seconds) > MAX_TIMEOUT_SECONDS
        ):
            raise NotionHttpAdapterError("notion_timeout_invalid")
        if (
            not isinstance(max_response_bytes, int)
            or isinstance(max_response_bytes, bool)
            or max_response_bytes < MIN_RESPONSE_BYTES
            or max_response_bytes > MAX_RESPONSE_BYTES
        ):
            raise NotionHttpAdapterError("notion_response_limit_invalid")
        if (
            not isinstance(max_attempts, int)
            or isinstance(max_attempts, bool)
            or max_attempts < 1
            or max_attempts > MAX_ADAPTER_ATTEMPTS
        ):
            raise NotionHttpAdapterError("notion_retry_attempts_invalid")
        if (
            not isinstance(max_retry_delay_seconds, (int, float))
            or isinstance(max_retry_delay_seconds, bool)
            or not math.isfinite(float(max_retry_delay_seconds))
            or float(max_retry_delay_seconds) < 0
            or float(max_retry_delay_seconds) > DEFAULT_MAX_RETRY_DELAY_SECONDS
        ):
            raise NotionHttpAdapterError("notion_retry_delay_invalid")
        if not callable(sleep) or not callable(jitter):
            raise NotionHttpAdapterError("notion_retry_dependency_invalid")
        if request_pacer is not None and not (
            callable(request_pacer)
            or callable(getattr(request_pacer, "before_request", None))
        ):
            raise NotionHttpAdapterError("notion_request_pacer_invalid")
        # Notion's fixed API endpoints are not expected to redirect.  The
        # stdlib redirect handler may otherwise carry Authorization to the
        # redirected request, so production fails closed on every 3xx.
        self._transport = transport or urllib_request.build_opener(_NoRedirectHandler())
        self._timeout_seconds = float(timeout_seconds)
        self._max_response_bytes = max_response_bytes
        self._request_pacer = request_pacer
        self._max_attempts = max_attempts
        self._max_retry_delay_seconds = float(max_retry_delay_seconds)
        self._sleep = sleep
        self._jitter = jitter

    def __repr__(self) -> str:
        return (
            "<_NotionHttpAdapter provider=notion api_version="
            f"{NOTION_API_VERSION} transport=redacted>"
        )

    @property
    def capability_transport_attempts_per_call(self) -> int:
        """Return the transport retry multiplier used by live recovery.

        Capability-backed recovery accepts only ``1``.  That makes each
        consumed logical authorization correspond to at most one raw HTTP
        transport attempt.
        """

        return self._max_attempts

    def retrieve_page(
        self,
        page_id: str,
        credential: object,
        *,
        api_version: str,
    ) -> ProviderResponse:
        normalized = _normalize_uuid(page_id)
        if normalized is None:
            return _safe_provider_error(400, "notion_page_id_invalid")
        if api_version != NOTION_API_VERSION:
            return _safe_provider_error(400, "notion_api_version_invalid")
        owned = not isinstance(credential, _NotionBearerSecret)
        secret = _coerce_secret(credential)
        if secret is None:
            return _safe_provider_error(401, "notion_secret_invalid")
        try:
            result = self._get_json(f"/v1/pages/{normalized}", secret)
            if result.status != 200:
                return ProviderResponse(
                    status=result.status,
                    payload={"reason_code": result.reason_code or _status_reason(result.status)},
                    headers=result.headers,
                )
            payload = _page_projection(result.payload, expected_id=normalized)
            if payload is None:
                return ProviderResponse(
                    status=502,
                    payload={"reason_code": "notion_response_malformed"},
                    headers=result.headers,
                )
            return ProviderResponse(
                status=result.status,
                payload=payload,
                headers=result.headers,
            )
        finally:
            if owned:
                secret.close()

    def retrieve_page_as_markdown(
        self,
        page_or_block_id: str,
        credential: object,
        *,
        api_version: str,
    ) -> ProviderResponse:
        normalized = _normalize_uuid(page_or_block_id)
        if normalized is None:
            return _safe_provider_error(400, "notion_page_or_block_id_invalid")
        if api_version != NOTION_API_VERSION:
            return _safe_provider_error(400, "notion_api_version_invalid")
        owned = not isinstance(credential, _NotionBearerSecret)
        secret = _coerce_secret(credential)
        if secret is None:
            return _safe_provider_error(401, "notion_secret_invalid")
        try:
            result = self._get_json(f"/v1/pages/{normalized}/markdown", secret)
            if result.status != 200:
                return ProviderResponse(
                    status=result.status,
                    payload={"reason_code": result.reason_code or _status_reason(result.status)},
                    headers=result.headers,
                )
            payload = _markdown_projection(result.payload, expected_id=normalized)
            if payload is None:
                return ProviderResponse(
                    status=502,
                    payload={"reason_code": "notion_response_malformed"},
                    headers=result.headers,
                )
            return ProviderResponse(
                status=result.status,
                payload=payload,
                headers=result.headers,
            )
        finally:
            if owned:
                secret.close()

    def verify_identity(
        self,
        secret: str | _NotionBearerSecret,
        reviewed_anchor_page_id: str,
        *,
        provider_request_observer: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        """Verify the token identity and one reviewed workspace anchor page."""

        normalized_anchor = _normalize_uuid(reviewed_anchor_page_id)
        if normalized_anchor is None:
            return _identity_evidence("notion_workspace_anchor_id_invalid")
        owned = not isinstance(secret, _NotionBearerSecret)
        wrapped = _coerce_secret(secret)
        if wrapped is None:
            return _identity_evidence("notion_secret_invalid")
        try:
            identity = self._get_json(
                "/v1/users/me",
                wrapped,
                provider_request_observer=provider_request_observer,
            )
            if identity.status != 200:
                return _identity_evidence(
                    _identity_status_reason(identity.status, identity.reason_code)
                )
            account_id = _user_identity_id(identity.payload)
            if account_id is None:
                return _identity_evidence("notion_identity_response_malformed")
            account_fingerprint = _fingerprint("account", account_id)
            identity_type = identity.payload.get("type") if identity.payload else None
            if identity_type == "bot":
                workspace_id = _bot_workspace_id(identity.payload)
                if workspace_id is None:
                    return _identity_evidence(
                        "notion_workspace_identity_response_malformed",
                        identity_verified=True,
                        account_fingerprint=account_fingerprint,
                    )
                workspace_identity = _fingerprint("workspace", workspace_id)
                workspace_identity_basis = NOTION_WORKSPACE_IDENTITY_BASIS
                success_reason = "notion_identity_and_workspace_anchor_verified"
            elif identity_type == "person" and isinstance(
                identity.payload.get("person"), Mapping
            ):
                # Official Notion PATs are user-scoped and belong to exactly
                # one user in one workspace, but /v1/users/me intentionally
                # returns a person without a workspace_id.  The adapter marks
                # that provider contract explicitly; secure intake derives the
                # actual private scope from the authenticated exact-secret HMAC
                # and never substitutes the reviewed page UUID.
                workspace_identity = _fingerprint(
                    "workspace-basis",
                    NOTION_PAT_WORKSPACE_IDENTITY_BASIS,
                )
                workspace_identity_basis = NOTION_PAT_WORKSPACE_IDENTITY_BASIS
                success_reason = "notion_pat_identity_and_workspace_anchor_verified"
            else:
                return _identity_evidence(
                    "notion_workspace_identity_response_malformed",
                    identity_verified=True,
                    account_fingerprint=account_fingerprint,
                )

            anchor = self.retrieve_page(
                normalized_anchor,
                wrapped,
                api_version=NOTION_API_VERSION,
            )
            if anchor.status != 200:
                return _identity_evidence(
                    _anchor_status_reason(anchor.status, anchor.payload),
                    identity_verified=True,
                    account_fingerprint=account_fingerprint,
                    workspace_identity_basis=workspace_identity_basis,
                )
            anchor_payload = anchor.payload
            if (
                not isinstance(anchor_payload, Mapping)
                or anchor_payload.get("id") != normalized_anchor
            ):
                return _identity_evidence(
                    "notion_workspace_anchor_response_malformed",
                    identity_verified=True,
                    account_fingerprint=account_fingerprint,
                    workspace_identity_basis=workspace_identity_basis,
                )
            if anchor_payload.get("in_trash") is True:
                return _identity_evidence(
                    "notion_workspace_anchor_deleted",
                    identity_verified=True,
                    account_fingerprint=account_fingerprint,
                    workspace_identity_basis=workspace_identity_basis,
                )
            return _identity_evidence(
                success_reason,
                identity_verified=True,
                workspace_anchor_verified=True,
                account_fingerprint=account_fingerprint,
                workspace_fingerprint=workspace_identity,
                workspace_identity_basis=workspace_identity_basis,
            )
        finally:
            if owned:
                wrapped.close()

    def identity_verifier(
        self,
        reviewed_anchor_page_id: str,
    ) -> _NotionIdentityVerifier:
        return _NotionIdentityVerifier(self, reviewed_anchor_page_id)

    def secure_intake_verifier(self) -> _NotionSecureIntakeVerifier:
        """Return a verifier matching credential_secure_intake's Protocol."""

        return _NotionSecureIntakeVerifier(self)

    def _get_json(
        self,
        path: str,
        secret: _NotionBearerSecret,
        *,
        provider_request_observer: Callable[[], None] | None = None,
    ) -> _HttpResult:
        result = _HttpResult(599, None, {}, "notion_transport_error")
        provider_request_observed = False

        def observe_provider_request_once() -> None:
            nonlocal provider_request_observed
            if provider_request_observed or provider_request_observer is None:
                return
            provider_request_observer()
            provider_request_observed = True

        for attempt in range(1, self._max_attempts + 1):
            if not self._pace_request():
                return _HttpResult(599, None, {}, "notion_transport_error")
            result = self._get_json_once(
                path,
                secret,
                provider_request_observer=observe_provider_request_once,
            )
            if result.status not in _RETRYABLE_STATUSES or attempt >= self._max_attempts:
                return result
            retry_after = _retry_after_seconds(result.headers)
            delay = retry_after if retry_after is not None else min(
                float(2 ** (attempt - 1)) + _bounded_jitter(self._jitter),
                self._max_retry_delay_seconds,
            )
            if delay > self._max_retry_delay_seconds:
                return result
            try:
                self._sleep(delay)
            except Exception:
                return _HttpResult(599, None, {}, "notion_transport_error")
        return result

    def _pace_request(self) -> bool:
        if self._request_pacer is None:
            return True
        try:
            callback = getattr(self._request_pacer, "before_request", None)
            if callable(callback):
                callback()
            else:
                self._request_pacer()
            return True
        except Exception:
            return False

    def _get_json_once(
        self,
        path: str,
        secret: _NotionBearerSecret,
        *,
        provider_request_observer: Callable[[], None] | None = None,
    ) -> _HttpResult:
        # ``path`` is constructed only from fixed literals and normalized UUIDs.
        request = urllib_request.Request(
            OFFICIAL_NOTION_API_BASE + path,
            method="GET",
            headers={
                "Accept": "application/json",
                "Authorization": secret._authorization_value(),
                "Notion-Version": NOTION_API_VERSION,
            },
        )
        response: Any = None
        try:
            if provider_request_observer is not None:
                provider_request_observer()
            if callable(self._transport) and not hasattr(self._transport, "open"):
                response = self._transport(request, timeout=self._timeout_seconds)
            else:
                response = self._transport.open(request, timeout=self._timeout_seconds)
        except urllib_error.HTTPError as exc:
            response = exc
        except Exception:
            return _HttpResult(599, None, {}, "notion_transport_error")

        try:
            status = _response_status(response)
            headers = _project_response_headers(getattr(response, "headers", None))
            if status is None:
                return _HttpResult(502, None, headers, "notion_response_malformed")
            if status != 200:
                return _HttpResult(status, None, headers, _status_reason(status))
            if _declared_oversize(getattr(response, "headers", None), self._max_response_bytes):
                return _HttpResult(413, None, headers, "notion_response_oversize")
            try:
                raw = response.read(self._max_response_bytes + 1)
            except Exception:
                return _HttpResult(599, None, headers, "notion_transport_error")
            if not isinstance(raw, bytes):
                return _HttpResult(502, None, headers, "notion_response_malformed")
            if len(raw) > self._max_response_bytes:
                return _HttpResult(413, None, headers, "notion_response_oversize")
            payload = _decode_json_object(raw)
            if payload is None:
                return _HttpResult(502, None, headers, "notion_response_malformed")
            return _HttpResult(status, payload, headers, None)
        except Exception:
            return _HttpResult(502, None, {}, "notion_response_malformed")
        finally:
            try:
                response.close()
            except Exception:
                pass


def _coerce_secret(value: object) -> _NotionBearerSecret | None:
    if isinstance(value, _NotionBearerSecret):
        return value
    if not isinstance(value, str):
        return None
    try:
        return _NotionBearerSecret(value)
    except NotionHttpAdapterError:
        return None


def _normalize_uuid(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError, TypeError):
        return None


def _response_status(response: Any) -> int | None:
    status = getattr(response, "status", None)
    if status is None:
        try:
            status = response.getcode()
        except Exception:
            return None
    if isinstance(status, bool) or not isinstance(status, int) or status < 100 or status > 599:
        return None
    return status


def _project_response_headers(headers: Any) -> dict[str, str]:
    if headers is None:
        return {}
    try:
        items = list(headers.items())
    except Exception:
        return {}
    projected: dict[str, str] = {}
    for key, value in items:
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        lowered = key.lower()
        stripped = value.strip()
        if lowered == "retry-after" and _SAFE_RETRY_AFTER_RE.fullmatch(stripped):
            projected["Retry-After"] = stripped
        elif lowered in {"request-id", "x-request-id"} and _SAFE_REQUEST_ID_RE.fullmatch(
            stripped
        ):
            projected["request-id"] = stripped
    return projected


def _retry_after_seconds(headers: Mapping[str, str]) -> float | None:
    value = headers.get("Retry-After")
    if not isinstance(value, str) or _SAFE_RETRY_AFTER_RE.fullmatch(value) is None:
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) and parsed >= 0 else None


def _bounded_jitter(callback: Callable[[], float]) -> float:
    try:
        value = callback()
    except Exception:
        return 0.0
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
    ):
        return 0.0
    return min(max(float(value), 0.0), 1.0)


def _declared_oversize(headers: Any, limit: int) -> bool:
    if headers is None:
        return False
    try:
        value = headers.get("Content-Length")
    except Exception:
        return False
    if not isinstance(value, str) or not value.isascii() or not value.isdigit():
        return False
    try:
        return int(value) > limit
    except ValueError:
        return False


def _decode_json_object(raw: bytes) -> Mapping[str, Any] | None:
    try:
        text = raw.decode("utf-8")

        def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate")
                result[key] = value
            return result

        value = json.loads(text, object_pairs_hook=reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
        return None
    return value if isinstance(value, Mapping) else None


def _page_projection(
    payload: Mapping[str, Any] | None,
    *,
    expected_id: str,
) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    page_id = _normalize_uuid(payload.get("id"))
    last_edited_time = payload.get("last_edited_time")
    in_trash = payload.get("in_trash")
    if (
        payload.get("object") != "page"
        or page_id != expected_id
        or not _valid_notion_timestamp(last_edited_time)
        or not isinstance(in_trash, bool)
    ):
        return None
    return {
        "object": "page",
        "id": page_id,
        "last_edited_time": last_edited_time,
        "in_trash": in_trash,
    }


def _valid_notion_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value or len(value) > 128:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _markdown_projection(
    payload: Mapping[str, Any] | None,
    *,
    expected_id: str,
) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    object_type = payload.get("object")
    response_id = _normalize_uuid(payload.get("id"))
    markdown = payload.get("markdown")
    truncated = payload.get("truncated")
    unknown_raw = payload.get("unknown_block_ids")
    if (
        object_type != "page_markdown"
        or response_id != expected_id
        or not isinstance(markdown, str)
        or not isinstance(truncated, bool)
        or not isinstance(unknown_raw, list)
        or len(unknown_raw) > 100
    ):
        return None
    unknown: list[str] = []
    seen: set[str] = set()
    for value in unknown_raw:
        normalized = _normalize_uuid(value)
        if normalized is None:
            return None
        if normalized not in seen:
            unknown.append(normalized)
            seen.add(normalized)
    return {
        "object": "page_markdown",
        "id": response_id,
        "markdown": markdown,
        "truncated": truncated,
        "unknown_block_ids": unknown,
    }


def _user_identity_id(payload: Mapping[str, Any] | None) -> str | None:
    if not isinstance(payload, Mapping) or payload.get("object") != "user":
        return None
    return _normalize_uuid(payload.get("id"))


def _bot_workspace_id(payload: Mapping[str, Any] | None) -> str | None:
    if (
        not isinstance(payload, Mapping)
        or payload.get("object") != "user"
        or payload.get("type") != "bot"
    ):
        return None
    bot = payload.get("bot")
    if not isinstance(bot, Mapping):
        return None
    return _normalize_uuid(bot.get("workspace_id"))


def _status_reason(status: int) -> str:
    if status == 401:
        return "notion_unauthorized"
    if status == 403:
        return "notion_forbidden"
    if status == 404:
        return "notion_not_found_or_not_shared"
    if status == 413:
        return "notion_response_oversize"
    if status == 599:
        return "notion_transport_error"
    if status == 502:
        return "notion_response_malformed"
    return "notion_http_error"


def _identity_status_reason(status: int, existing: str | None) -> str:
    if status == 401:
        return "notion_identity_unauthorized"
    if status == 403:
        return "notion_identity_forbidden"
    if status == 404:
        return "notion_identity_not_found"
    if existing in {
        "notion_transport_error",
        "notion_response_oversize",
        "notion_response_malformed",
    }:
        return existing
    return "notion_identity_http_error"


def _anchor_status_reason(status: int, payload: Mapping[str, Any] | None) -> str:
    if status == 401:
        return "notion_workspace_anchor_unauthorized"
    if status == 403:
        return "notion_workspace_anchor_forbidden"
    if status == 404:
        return "notion_workspace_anchor_not_found_or_not_shared"
    reason = payload.get("reason_code") if isinstance(payload, Mapping) else None
    if reason == "notion_response_malformed":
        return "notion_workspace_anchor_response_malformed"
    if reason in {
        "notion_transport_error",
        "notion_response_oversize",
    }:
        return str(reason)
    return "notion_workspace_anchor_http_error"


def _secure_intake_stage_reason(
    reason: str,
    *,
    evidence: Mapping[str, Any],
    provider_request_attempted: bool,
) -> str:
    """Project a private Notion failure into one fixed operator-visible stage."""

    if reason == "notion_secret_invalid":
        return "credential_input_invalid_for_provider"
    if provider_request_attempted and reason in {
        "notion_identity_unauthorized",
        "notion_identity_forbidden",
    }:
        return "provider_auth_rejected"
    if reason.startswith("notion_workspace_anchor_"):
        return "reviewed_anchor_inaccessible"
    if evidence.get("identity_verified") is True and reason in {
        "notion_transport_error",
        "notion_response_oversize",
        "notion_response_malformed",
    }:
        return "reviewed_anchor_inaccessible"
    if reason in {
        "notion_transport_error",
        "notion_response_oversize",
        "notion_response_malformed",
        "notion_identity_not_found",
        "notion_identity_http_error",
        "notion_identity_response_malformed",
        "notion_workspace_identity_response_malformed",
        "notion_workspace_anchor_response_malformed",
        "notion_workspace_anchor_http_error",
    }:
        return "provider_identity_endpoint_unavailable"
    return "provider_identity_unverified"


def _safe_provider_error(status: int, reason_code: str) -> ProviderResponse:
    return ProviderResponse(status=status, payload={"reason_code": reason_code}, headers={})


def _fingerprint(kind: str, value: str) -> str:
    digest = hashlib.sha256(
        f"wom:notion:{NOTION_API_VERSION}:{kind}:{value}".encode("utf-8")
    ).hexdigest()
    return "sha256:" + digest


def _identity_evidence(
    reason_code: str,
    *,
    identity_verified: bool = False,
    workspace_anchor_verified: bool = False,
    account_fingerprint: str | None = None,
    workspace_fingerprint: str | None = None,
    workspace_identity_basis: str | None = None,
) -> dict[str, Any]:
    return {
        "provider": "notion",
        "reason_code": reason_code,
        "identity_verified": identity_verified,
        "workspace_anchor_verified": workspace_anchor_verified,
        "account_fingerprint": account_fingerprint,
        "workspace_fingerprint": workspace_fingerprint,
        "workspace_identity_basis": workspace_identity_basis,
        "capabilities": dict(_CAPABILITIES),
        "api_version": NOTION_API_VERSION,
        "privacy_guards": {
            "secret_echoed": False,
            "authorization_header_echoed": False,
            "account_id_echoed": False,
            "workspace_anchor_id_echoed": False,
            "name_echoed": False,
            "email_echoed": False,
            "title_echoed": False,
            "provider_url_echoed": False,
            "raw_error_echoed": False,
        },
    }
