"""Human-only, atomic credential intake primitives.

The module is intentionally independent from the archive CLI.  It establishes
the boundary requested by the WOM credential-intake contract without opening a
real provider, password manager, or operating-system vault by itself.

The AI-visible parent process may create a content-free plan and launch a
worker, but it never receives a secret.  A worker-only UI supplies one mutable
buffer directly to an exact-match encrypted-store adapter and an identity
verifier.  The buffer is wiped before the worker returns.  Only a non-secret
success receipt or a fixed failure reason leaves the worker.

Adapters are injected so tests never touch a real vault, provider, or UI.  In
particular, the Windows Credential Manager adapter exposes write/probe/delete
for one exact Generic Credential target and deliberately has no enumerate,
search, fuzzy-match, or read-secret method.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import stat as stat_module
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol


PLAN_SCHEMA_VERSION = "wom-credential-secure-intake-plan/v0.1"
RECEIPT_SCHEMA_VERSION = "wom-credential-secure-intake-receipt/v0.1"
RESULT_SCHEMA_VERSION = "wom-credential-secure-intake-result/v0.1"
LIFECYCLE_SCHEMA_VERSION = "wom-credential-duplicate-lifecycle/v0.1"
CLAIM_SCHEMA_VERSION = "wom-credential-secure-intake-claim/v0.1"

MIN_TTL_SECONDS = 30
MAX_TTL_SECONDS = 3600
MAX_SECRET_BYTES = 64 * 1024
MIN_FINGERPRINT_KEY_BYTES = 32
MAX_CLAIM_BYTES = 4096
CLAIM_REPLAY_READ_ATTEMPTS = 64

PROVIDER_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
PURPOSE_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
REQUEST_ID_RE = re.compile(r"^intake_[A-Za-z0-9_-]{16,96}$")
CREDENTIAL_ID_RE = re.compile(r"^cred_[A-Za-z0-9_-]{16,96}$")
BACKEND_ID_RE = re.compile(r"^backend_[A-Za-z0-9_-]{16,96}$")
PUBLIC_FINGERPRINT_RE = re.compile(r"^hmac-sha256:[0-9a-f]{64}$")
WORKSPACE_FINGERPRINT_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SAFE_RECEIPT_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_./:-]{0,511}$")
PUBLIC_LABEL_SECRET_SHAPE_RE = re.compile(
    r"(?i)(?:\b(?:secret|token|password|credential|api[_ -]?key)\s*[:=]\s*\S+"
    r"|\bgithub_pat_[A-Za-z0-9_]{20,}\b|\bsk-[A-Za-z0-9_-]{8,}\b"
    r"|\b(?:secret|ntn)_[A-Za-z0-9_-]{12,}\b)"
)

PLAN_ACTIONS = (
    "human_only_secret_input",
    "encrypted_store_put_exact",
    "encrypted_store_probe_exact",
    "provider_identity_verify",
    "reviewed_workspace_anchor_verify",
    "receipt_commit_atomic",
)

FAILURE_OPERATOR_ACTIONS = {
    "human_cancelled": "restart_human_only_intake_when_ready",
    "secret_input_unavailable": "use_supported_human_only_input_ui",
    "store_write_failed": "repair_encrypted_store_and_retry_with_new_request",
    "store_presence_not_verified": "repair_encrypted_store_and_retry_with_new_request",
    "provider_identity_unverified": "check_provider_access_without_reissuing_credential",
    "workspace_anchor_mismatch": "review_workspace_anchor_and_retry_with_new_request",
    "receipt_commit_failed": "repair_receipt_store_and_retry_with_new_request",
    "request_expired": "create_a_new_intake_plan",
    "request_replayed": "create_a_new_intake_plan",
    "request_user_mismatch": "run_the_worker_as_the_approved_windows_user",
    "request_claim_failed": "repair_local_request_claim_store",
    "plan_digest_mismatch": "review_and_approve_a_new_unchanged_plan",
    "worker_launch_failed": "repair_the_human_only_worker_launcher",
    "worker_result_invalid": "stop_and_review_the_worker_boundary",
}

_FIXED_FAILURE_ERROR = "secure credential intake did not complete"
_UNKNOWN_WORKER_REASON = "worker_state_unknown"
_UNKNOWN_WORKER_ACTION = "reconcile_then_rerun_same_approved_plan"
_UNKNOWN_WORKER_ERROR = "secure credential intake worker state is unknown"

# The exported process launcher is a public parent/child security boundary,
# not a generic JSON relay.  Its default production contract is deliberately
# narrower than the injectable worker primitives: adding a provider capability
# or encrypted backend requires a reviewed code change instead of allowing a
# child process to invent a new public string channel.
_LAUNCHER_PROVIDER_CAPABILITIES = {
    "notion": frozenset(
        {
            "read_content",
            "retrieve_page",
            "retrieve_page_as_markdown",
            "retrieve_user_identity",
            "verify_identity_with_reviewed_anchor",
        }
    ),
}
_LAUNCHER_ENCRYPTED_BACKEND_KINDS = frozenset(
    {"windows_credential_manager_generic"}
)
_LAUNCHER_MAX_VERIFIED_CAPABILITIES = 16


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("secure_intake_time_invalid")
    return value.astimezone(timezone.utc)


def _timestamp(value: datetime) -> str:
    return _as_utc(value).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return _as_utc(parsed)
    except (TypeError, ValueError):
        raise ValueError("secure_intake_time_invalid") from None


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        raise ValueError("secure_intake_public_payload_invalid") from None


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _safe_text(value: Any, code: str, *, maximum: int = 128) -> str:
    text = str(value or "").strip()
    if not text or len(text) > maximum:
        raise ValueError(code)
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        raise ValueError(code)
    return text


def _safe_public_label(value: Any, code: str) -> str:
    """Validate an AI-visible account/workspace label, never a secret value."""

    text = _safe_text(value, code)
    if (
        "@" in text
        or "://" in text
        or "/" in text
        or "\\" in text
        or PUBLIC_LABEL_SECRET_SHAPE_RE.search(text)
    ):
        raise ValueError(code)
    return text


def _safe_provider(value: Any) -> str:
    text = str(value or "").strip().lower()
    if PROVIDER_RE.fullmatch(text) is None:
        raise ValueError("secure_intake_provider_invalid")
    return text


def _safe_purpose(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_")
    if PURPOSE_RE.fullmatch(text) is None:
        raise ValueError("secure_intake_purpose_invalid")
    return text


def _safe_uuid(value: Any, code: str) -> str:
    try:
        return str(uuid.UUID(str(value or "").strip()))
    except (AttributeError, TypeError, ValueError):
        raise ValueError(code) from None


def _owner_digest(owner_binding: str) -> str:
    owner = _safe_text(owner_binding, "secure_intake_owner_invalid", maximum=512)
    return "sha256:" + hashlib.sha256(owner.encode("utf-8")).hexdigest()


def _opaque_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(24)}"


def _normalize_capabilities(values: Sequence[str]) -> tuple[str, ...]:
    normalized: set[str] = set()
    for value in values:
        text = _safe_purpose(value)
        normalized.add(text)
    return tuple(sorted(normalized))


def _fixed_failure(reason_code: str, *, rollback_status: str = "not_required") -> dict[str, Any]:
    if reason_code not in FAILURE_OPERATOR_ACTIONS:
        reason_code = "worker_result_invalid"
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "ok": False,
        "accepted": False,
        "persisted": False,
        "reason_code": reason_code,
        "operator_action": FAILURE_OPERATOR_ACTIONS[reason_code],
        "rollback_status": rollback_status,
        "error": _FIXED_FAILURE_ERROR,
    }


@dataclass(frozen=True)
class SecureIntakePlan:
    """A content-free, closed-action intake plan.

    Creating this object does not issue a credential id, read a secret, open a
    store/provider, or write a request file.  The one-use claim is created only
    after a human approves the plan and a worker starts.
    """

    request_id: str
    provider: str
    account_label: str
    workspace_label: str
    purpose: str
    reviewed_anchor_uuid: str = field(repr=False)
    requested_capabilities: tuple[str, ...]
    created_at: str
    expires_at: str
    ttl_seconds: int
    owner_binding_digest: str
    plan_digest: str
    schema_version: str = PLAN_SCHEMA_VERSION

    def _digest_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "provider": self.provider,
            "account_label": self.account_label,
            "workspace_label": self.workspace_label,
            "purpose": self.purpose,
            "reviewed_anchor_uuid": self.reviewed_anchor_uuid,
            "requested_capabilities": list(self.requested_capabilities),
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "ttl_seconds": self.ttl_seconds,
            "owner_binding_digest": self.owner_binding_digest,
        }

    def recompute_digest(self) -> str:
        return _digest(self._digest_payload())

    def to_public_dict(self) -> dict[str, Any]:
        payload = self._digest_payload()
        # The exact reviewed anchor remains inside the digest-bound worker
        # plan.  AI-visible dry-run and launcher payloads disclose only that a
        # human-reviewed anchor is present.
        payload.pop("reviewed_anchor_uuid", None)
        payload.update(
            {
                "plan_digest": self.plan_digest,
                "reviewed_anchor_present": True,
                "actions": list(PLAN_ACTIONS),
                "closed_actions": {
                    "credential_id_issued": False,
                    "secret_received": False,
                    "credential_store_opened": False,
                    "provider_called": False,
                    "file_written": False,
                },
            }
        )
        return payload


def create_secure_intake_plan(
    *,
    provider: str,
    account_label: str,
    workspace_label: str,
    purpose: str,
    reviewed_anchor_uuid: str,
    owner_binding: str,
    requested_capabilities: Sequence[str] = (),
    ttl_seconds: int = 300,
    now: datetime | None = None,
    request_id_factory: Callable[[], str] | None = None,
) -> SecureIntakePlan:
    """Create a write-free plan for a later human-only worker invocation."""

    if not isinstance(ttl_seconds, int) or not MIN_TTL_SECONDS <= ttl_seconds <= MAX_TTL_SECONDS:
        raise ValueError("secure_intake_ttl_invalid")
    moment = _as_utc(now or _utc_now()).replace(microsecond=0)
    request_id = (request_id_factory or (lambda: _opaque_id("intake")))()
    if REQUEST_ID_RE.fullmatch(str(request_id)) is None:
        raise ValueError("secure_intake_request_id_invalid")
    payload = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "request_id": str(request_id),
        "provider": _safe_provider(provider),
        "account_label": _safe_public_label(
            account_label, "secure_intake_account_label_invalid"
        ),
        "workspace_label": _safe_public_label(
            workspace_label, "secure_intake_workspace_label_invalid"
        ),
        "purpose": _safe_purpose(purpose),
        "reviewed_anchor_uuid": _safe_uuid(
            reviewed_anchor_uuid, "secure_intake_reviewed_anchor_invalid"
        ),
        "requested_capabilities": list(_normalize_capabilities(requested_capabilities)),
        "created_at": _timestamp(moment),
        "expires_at": _timestamp(moment + timedelta(seconds=ttl_seconds)),
        "ttl_seconds": ttl_seconds,
        "owner_binding_digest": _owner_digest(owner_binding),
    }
    return SecureIntakePlan(
        request_id=payload["request_id"],
        provider=payload["provider"],
        account_label=payload["account_label"],
        workspace_label=payload["workspace_label"],
        purpose=payload["purpose"],
        reviewed_anchor_uuid=payload["reviewed_anchor_uuid"],
        requested_capabilities=tuple(payload["requested_capabilities"]),
        created_at=payload["created_at"],
        expires_at=payload["expires_at"],
        ttl_seconds=ttl_seconds,
        owner_binding_digest=payload["owner_binding_digest"],
        plan_digest=_digest(payload),
    )


def validate_secure_intake_plan(
    plan: SecureIntakePlan,
    *,
    expected_plan_digest: str,
    current_owner_binding: str,
    now: datetime | None = None,
) -> str | None:
    """Return a fixed failure code, or ``None`` when the plan may be claimed."""

    if not hmac.compare_digest(plan.plan_digest, plan.recompute_digest()):
        return "plan_digest_mismatch"
    if not hmac.compare_digest(plan.plan_digest, str(expected_plan_digest or "")):
        return "plan_digest_mismatch"
    if not hmac.compare_digest(plan.owner_binding_digest, _owner_digest(current_owner_binding)):
        return "request_user_mismatch"
    moment = _as_utc(now or _utc_now())
    if moment >= _parse_timestamp(plan.expires_at):
        return "request_expired"
    return None


class OneTimeRequestClaims(Protocol):
    def claim(
        self,
        plan: SecureIntakePlan,
        *,
        expected_plan_digest: str,
        current_owner_binding: str,
        now: datetime,
    ) -> str | None: ...


class InMemoryOneTimeRequestClaims:
    """Thread-safe one-use claims for embedding and deterministic tests."""

    def __init__(self) -> None:
        self._claimed: set[str] = set()
        self._lock = threading.Lock()

    def claim(
        self,
        plan: SecureIntakePlan,
        *,
        expected_plan_digest: str,
        current_owner_binding: str,
        now: datetime,
    ) -> str | None:
        failure = validate_secure_intake_plan(
            plan,
            expected_plan_digest=expected_plan_digest,
            current_owner_binding=current_owner_binding,
            now=now,
        )
        if failure:
            return failure
        with self._lock:
            if plan.request_id in self._claimed:
                return "request_replayed"
            self._claimed.add(plan.request_id)
        return None


_CLAIM_REPARSE_FLAG = int(
    getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0x00000400)
)


class _ClaimAuthorityError(OSError):
    """Internal fixed-code error; paths and native exception text never escape."""


def _claim_is_reparse(information: os.stat_result) -> bool:
    return bool(
        stat_module.S_ISLNK(information.st_mode)
        or (
            _CLAIM_REPARSE_FLAG
            and int(getattr(information, "st_file_attributes", 0))
            & _CLAIM_REPARSE_FLAG
        )
    )


def _claim_identity(information: os.stat_result) -> tuple[int, int]:
    return (int(information.st_dev), int(information.st_ino))


def _claim_same_identity(
    left: os.stat_result, right: os.stat_result
) -> bool:
    left_identity = _claim_identity(left)
    right_identity = _claim_identity(right)
    return bool(
        left_identity[1]
        and right_identity[1]
        and left_identity == right_identity
    )


def _claim_safe_directory(information: os.stat_result) -> bool:
    return bool(
        stat_module.S_ISDIR(information.st_mode)
        and not _claim_is_reparse(information)
    )


def _claim_safe_regular(information: os.stat_result, *, links: int = 1) -> bool:
    return bool(
        stat_module.S_ISREG(information.st_mode)
        and not _claim_is_reparse(information)
        and int(getattr(information, "st_nlink", 1)) == links
    )


def _lexical_absolute_path(value: Path | str) -> Path:
    try:
        return Path(os.path.abspath(os.fspath(value)))
    except (TypeError, ValueError, OSError):
        raise _ClaimAuthorityError("claim_path_invalid") from None


class _BoundClaimDirectory:
    """One held, non-reparse directory chain and its exact final directory."""

    def __init__(
        self,
        *,
        path: Path,
        descriptor: int | None,
        identities: list[tuple[Path, tuple[int, int]]],
    ) -> None:
        self.path = path
        self.descriptor = descriptor
        self.identities = identities

    @staticmethod
    def _name(name: str) -> str:
        if (
            not isinstance(name, str)
            or not name
            or Path(name).name != name
            or "/" in name
            or "\\" in name
        ):
            raise _ClaimAuthorityError("claim_name_invalid")
        return name

    def stat_name(self, name: str) -> os.stat_result:
        selected = self._name(name)
        if self.descriptor is not None:
            return os.stat(
                selected,
                dir_fd=self.descriptor,
                follow_symlinks=False,
            )
        return os.lstat(self.path / selected)

    def open_name(self, name: str, flags: int, mode: int = 0o600) -> int:
        selected = self._name(name)
        flags |= int(getattr(os, "O_BINARY", 0))
        flags |= int(getattr(os, "O_NOFOLLOW", 0))
        if self.descriptor is not None:
            return os.open(selected, flags, mode, dir_fd=self.descriptor)
        return os.open(self.path / selected, flags, mode)

    def link_name(self, source: str, destination: str) -> None:
        selected_source = self._name(source)
        selected_destination = self._name(destination)
        if self.descriptor is not None:
            os.link(
                selected_source,
                selected_destination,
                src_dir_fd=self.descriptor,
                dst_dir_fd=self.descriptor,
                follow_symlinks=False,
            )
            return
        os.link(
            self.path / selected_source,
            self.path / selected_destination,
            follow_symlinks=False,
        )

    def unlink_name(self, name: str) -> None:
        selected = self._name(name)
        if self.descriptor is not None:
            os.unlink(selected, dir_fd=self.descriptor)
            return
        os.unlink(self.path / selected)

    def fsync_directory(self) -> None:
        # POSIX requires the containing directory fsync to make the hard-link
        # publication durable.  Python does not expose a directory descriptor
        # for the held Windows handle; the marker file itself is fsynced before
        # publication and the no-delete-share handles keep its path stable.
        if self.descriptor is not None:
            os.fsync(self.descriptor)

    def verify(self) -> None:
        for path, expected_identity in self.identities:
            try:
                current = os.lstat(path)
            except OSError:
                raise _ClaimAuthorityError("claim_directory_changed") from None
            if (
                not _claim_safe_directory(current)
                or _claim_identity(current) != expected_identity
                or not expected_identity[1]
            ):
                raise _ClaimAuthorityError("claim_directory_changed")

@contextmanager
def _bind_claim_directory(
    directory: Path,
    *,
    must_exist_root: Path,
):
    """Hold every filesystem component and create only below the bound root."""

    target = _lexical_absolute_path(directory)
    required_root = _lexical_absolute_path(must_exist_root)
    try:
        target.relative_to(required_root)
        anchor = Path(target.anchor)
        relative = target.relative_to(anchor)
    except ValueError:
        raise _ClaimAuthorityError("claim_path_outside_authority") from None

    identities: list[tuple[Path, tuple[int, int]]] = []
    if os.name != "nt":
        flags = int(os.O_RDONLY)
        flags |= int(getattr(os, "O_DIRECTORY", 0))
        flags |= int(getattr(os, "O_NOFOLLOW", 0))
        descriptors: list[int] = []
        binding: _BoundClaimDirectory | None = None
        try:
            current_descriptor = os.open(anchor, flags)
            descriptors.append(current_descriptor)
            current_path = anchor
            opened = os.fstat(current_descriptor)
            if not _claim_safe_directory(opened):
                raise _ClaimAuthorityError("claim_directory_unsafe")
            identities.append((current_path, _claim_identity(opened)))
            creation_allowed = current_path == required_root
            for part in relative.parts:
                current_path = current_path / part
                try:
                    named = os.stat(
                        part,
                        dir_fd=current_descriptor,
                        follow_symlinks=False,
                    )
                except FileNotFoundError:
                    if not creation_allowed:
                        raise _ClaimAuthorityError("claim_authority_root_missing") from None
                    try:
                        os.mkdir(part, 0o700, dir_fd=current_descriptor)
                    except FileExistsError:
                        pass
                    named = os.stat(
                        part,
                        dir_fd=current_descriptor,
                        follow_symlinks=False,
                    )
                if not _claim_safe_directory(named):
                    raise _ClaimAuthorityError("claim_directory_unsafe")
                child_descriptor = os.open(part, flags, dir_fd=current_descriptor)
                child = os.fstat(child_descriptor)
                if (
                    not _claim_safe_directory(child)
                    or not _claim_same_identity(named, child)
                ):
                    os.close(child_descriptor)
                    raise _ClaimAuthorityError("claim_directory_changed")
                descriptors.append(child_descriptor)
                current_descriptor = child_descriptor
                identities.append((current_path, _claim_identity(child)))
                if current_path == required_root:
                    creation_allowed = True
            if current_path != target:
                raise _ClaimAuthorityError("claim_directory_changed")
            binding = _BoundClaimDirectory(
                path=target,
                descriptor=current_descriptor,
                identities=identities,
            )
            yield binding
        finally:
            first_error: OSError | None = None
            # The binding owns the final descriptor; close all held ancestors
            # here so every component remains stable until the body returns.
            for descriptor in reversed(descriptors):
                try:
                    os.close(descriptor)
                except OSError as error:
                    first_error = first_error or error
            if first_error is not None:
                raise _ClaimAuthorityError("claim_directory_close_failed") from None
        return

    # Windows path functions cannot open relative to a directory descriptor.
    # Hold every checked directory with FILE_SHARE_DELETE omitted, which
    # prevents rename/reparse replacement until the marker transaction ends.
    import ctypes
    from ctypes import wintypes

    class _ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", wintypes.FILETIME),
            ("ftLastAccessTime", wintypes.FILETIME),
            ("ftLastWriteTime", wintypes.FILETIME),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    get_information = kernel32.GetFileInformationByHandle
    get_information.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_ByHandleFileInformation),
    ]
    get_information.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    invalid_handle = wintypes.HANDLE(-1).value
    handles: list[Any] = []
    current_path = anchor
    creation_allowed = current_path == required_root
    binding = None
    try:
        for component in (None, *relative.parts):
            if component is not None:
                current_path = current_path / component
            try:
                named = os.lstat(current_path)
            except FileNotFoundError:
                if not creation_allowed:
                    raise _ClaimAuthorityError("claim_authority_root_missing") from None
                try:
                    os.mkdir(current_path, 0o700)
                except FileExistsError:
                    pass
                named = os.lstat(current_path)
            if not _claim_safe_directory(named):
                raise _ClaimAuthorityError("claim_directory_unsafe")
            handle = create_file(
                str(current_path),
                0x00000080,  # FILE_READ_ATTRIBUTES
                0x00000001 | 0x00000002,  # share read/write, never delete
                None,
                3,  # OPEN_EXISTING
                0x00200000 | 0x02000000,  # OPEN_REPARSE_POINT | BACKUP_SEMANTICS
                None,
            )
            if handle == invalid_handle:
                raise _ClaimAuthorityError("claim_directory_hold_failed")
            information = _ByHandleFileInformation()
            if not get_information(handle, ctypes.byref(information)):
                close_handle(handle)
                raise _ClaimAuthorityError("claim_directory_hold_failed")
            opened_index = (
                int(information.nFileIndexHigh) << 32
            ) | int(information.nFileIndexLow)
            if (
                not opened_index
                or opened_index != int(named.st_ino)
                or not information.dwFileAttributes & 0x00000010
                or information.dwFileAttributes & 0x00000400
            ):
                close_handle(handle)
                raise _ClaimAuthorityError("claim_directory_changed")
            handles.append(handle)
            identities.append((current_path, _claim_identity(named)))
            if current_path == required_root:
                creation_allowed = True
        if current_path != target:
            raise _ClaimAuthorityError("claim_directory_changed")
        binding = _BoundClaimDirectory(
            path=target,
            descriptor=None,
            identities=identities,
        )
        yield binding
    finally:
        first_error = False
        for handle in reversed(handles):
            try:
                if not close_handle(handle):
                    first_error = True
            except OSError:
                first_error = True
        if first_error:
            raise _ClaimAuthorityError("claim_directory_close_failed") from None


def _claim_marker_document(plan: SecureIntakePlan, claimed_at: str) -> dict[str, Any]:
    return {
        "schema_version": CLAIM_SCHEMA_VERSION,
        "request_id": plan.request_id,
        "plan_digest": plan.plan_digest,
        "claimed_at": claimed_at,
        "expires_at": plan.expires_at,
        "owner_binding_digest": plan.owner_binding_digest,
    }


def _claim_marker_matches(raw: bytes, plan: SecureIntakePlan) -> bool:
    """Authenticate one exact canonical marker, including legacy v0.3.310 bytes."""

    if not raw or len(raw) > MAX_CLAIM_BYTES:
        return False
    try:
        text = raw.decode("utf-8")
        document = json.loads(
            text,
            object_pairs_hook=lambda pairs: _reject_duplicate_claim_pairs(pairs),
        )
    except (UnicodeError, ValueError, TypeError):
        return False
    if not isinstance(document, dict):
        return False
    legacy_keys = {
        "request_id",
        "plan_digest",
        "claimed_at",
        "expires_at",
        "owner_binding_digest",
    }
    expected_keys = legacy_keys | {"schema_version"}
    keys = set(document)
    if keys not in (legacy_keys, expected_keys):
        return False
    if keys == expected_keys and document.get("schema_version") != CLAIM_SCHEMA_VERSION:
        return False
    if not (
        type(document.get("request_id")) is str
        and hmac.compare_digest(document["request_id"], plan.request_id)
        and type(document.get("plan_digest")) is str
        and hmac.compare_digest(document["plan_digest"], plan.plan_digest)
        and type(document.get("expires_at")) is str
        and hmac.compare_digest(document["expires_at"], plan.expires_at)
        and type(document.get("owner_binding_digest")) is str
        and hmac.compare_digest(
            document["owner_binding_digest"], plan.owner_binding_digest
        )
        and type(document.get("claimed_at")) is str
    ):
        return False
    try:
        claimed = _parse_timestamp(document["claimed_at"])
        created = _parse_timestamp(plan.created_at)
        expires = _parse_timestamp(plan.expires_at)
    except ValueError:
        return False
    if document["claimed_at"] != _timestamp(claimed) or not created <= claimed < expires:
        return False
    canonical = _canonical_json(document).encode("utf-8")
    return raw in {canonical, canonical + b"\n"}


def _reject_duplicate_claim_pairs(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("claim_duplicate_key")
        result[key] = value
    return result


def _read_bound_claim(
    binding: _BoundClaimDirectory,
    name: str,
) -> tuple[bytes, os.stat_result]:
    before = binding.stat_name(name)
    if (
        not _claim_safe_regular(before)
        or before.st_size <= 0
        or before.st_size > MAX_CLAIM_BYTES
    ):
        raise _ClaimAuthorityError("claim_marker_unsafe")
    descriptor: int | None = None
    close_error: OSError | None = None
    try:
        descriptor = binding.open_name(name, os.O_RDONLY)
        opened = os.fstat(descriptor)
        if (
            not _claim_safe_regular(opened)
            or not _claim_same_identity(before, opened)
            or opened.st_size != before.st_size
        ):
            raise _ClaimAuthorityError("claim_marker_changed")
        chunks: list[bytes] = []
        remaining = int(opened.st_size)
        while remaining:
            chunk = os.read(descriptor, min(remaining, 65536))
            if not chunk:
                raise _ClaimAuthorityError("claim_marker_changed")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise _ClaimAuthorityError("claim_marker_changed")
        after_open = os.fstat(descriptor)
        after_named = binding.stat_name(name)
        if (
            not _claim_same_identity(opened, after_open)
            or not _claim_same_identity(opened, after_named)
            or after_open.st_size != opened.st_size
        ):
            raise _ClaimAuthorityError("claim_marker_changed")
        return b"".join(chunks), opened
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as error:
                close_error = error
        if close_error is not None:
            raise _ClaimAuthorityError("claim_marker_close_failed") from None


def _existing_claim_matches(
    binding: _BoundClaimDirectory,
    name: str,
    plan: SecureIntakePlan,
) -> bool:
    for attempt in range(CLAIM_REPLAY_READ_ATTEMPTS):
        try:
            raw, _information = _read_bound_claim(binding, name)
            return _claim_marker_matches(raw, plan)
        except FileNotFoundError:
            return False
        except _ClaimAuthorityError:
            try:
                information = binding.stat_name(name)
            except OSError:
                return False
            # Atomic hard-link publication is briefly two-linked until the
            # publisher removes its private temp name. Yield only for that
            # bounded, regular-file state; every other unsafe state fails now.
            if attempt + 1 >= CLAIM_REPLAY_READ_ATTEMPTS:
                return False
            if _claim_safe_regular(information):
                continue
            if not _claim_safe_regular(information, links=2):
                return False
            time.sleep(0.001)
    return False


def _unlink_bound_identity(
    binding: _BoundClaimDirectory,
    name: str,
    expected: os.stat_result | None,
) -> None:
    if expected is None:
        return
    try:
        named = binding.stat_name(name)
        if _claim_same_identity(named, expected):
            binding.unlink_name(name)
    except OSError:
        pass


class FileOneTimeRequestClaims:
    """Archive-bound, durable create-if-absent one-use claim authority.

    ``archive_root`` and ``expected_relative_directory`` are optional only for
    source compatibility with test/embedding callers.  Production composition
    passes both, so a caller-controlled absolute directory cannot redirect the
    marker.  Every existing path component is held and checked as a real
    directory; the final marker is fully written and fsynced under a private
    temp name before an atomic same-directory hard-link publishes authority.
    """

    def __init__(
        self,
        claim_directory: Path | str,
        *,
        archive_root: Path | str | None = None,
        expected_relative_directory: Path | str | None = None,
        _failpoint: Callable[[str], None] | None = None,
    ) -> None:
        self._configuration_valid = True
        self._failpoint = _failpoint or (lambda _stage: None)
        try:
            self._directory = _lexical_absolute_path(claim_directory)
            if archive_root is None:
                if expected_relative_directory is not None:
                    raise _ClaimAuthorityError("claim_scope_invalid")
                self._authority_root = self._directory.parent
            else:
                self._authority_root = _lexical_absolute_path(archive_root)
                self._directory.relative_to(self._authority_root)
                if expected_relative_directory is not None:
                    relative = Path(expected_relative_directory)
                    if (
                        relative.is_absolute()
                        or not relative.parts
                        or any(part in {"", ".", ".."} for part in relative.parts)
                    ):
                        raise _ClaimAuthorityError("claim_scope_invalid")
                    expected = self._authority_root.joinpath(*relative.parts)
                    if os.path.normcase(str(expected)) != os.path.normcase(
                        str(self._directory)
                    ):
                        raise _ClaimAuthorityError("claim_scope_invalid")
        except (TypeError, ValueError, OSError):
            self._configuration_valid = False
            self._directory = Path(".")
            self._authority_root = Path(".")

    def __repr__(self) -> str:
        return "<FileOneTimeRequestClaims path=redacted>"

    def _stage(self, name: str) -> None:
        try:
            self._failpoint(name)
        except Exception:
            raise _ClaimAuthorityError("claim_failpoint") from None

    def _claim_bound(
        self,
        binding: _BoundClaimDirectory,
        plan: SecureIntakePlan,
        *,
        final_name: str,
        temp_name: str,
        body: bytes,
    ) -> str | None:
        temp_identity: os.stat_result | None = None
        published_identity: os.stat_result | None = None
        try:
            self._stage("directory_bound")
            binding.verify()
            try:
                binding.stat_name(final_name)
            except FileNotFoundError:
                pass
            else:
                return (
                    "request_replayed"
                    if _existing_claim_matches(binding, final_name, plan)
                    else "request_claim_failed"
                )

            descriptor: int | None = None
            try:
                descriptor = binding.open_name(
                    temp_name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                )
                temp_identity = os.fstat(descriptor)
                if (
                    not _claim_safe_regular(temp_identity)
                    or temp_identity.st_size != 0
                    or not _claim_same_identity(
                        temp_identity, binding.stat_name(temp_name)
                    )
                ):
                    raise _ClaimAuthorityError("claim_temp_unsafe")
                self._stage("temp_opened")
                written = 0
                while written < len(body):
                    count = os.write(descriptor, memoryview(body)[written:])
                    if (
                        type(count) is not int
                        or count <= 0
                        or count > len(body) - written
                    ):
                        raise _ClaimAuthorityError("claim_write_incomplete")
                    written += count
                self._stage("temp_written")
                os.fsync(descriptor)
                self._stage("temp_fsynced")
                completed = os.fstat(descriptor)
                if (
                    not _claim_same_identity(temp_identity, completed)
                    or completed.st_size != len(body)
                ):
                    raise _ClaimAuthorityError("claim_write_incomplete")
                try:
                    os.close(descriptor)
                except OSError:
                    raise _ClaimAuthorityError("claim_temp_close_failed") from None
                descriptor = None
                self._stage("temp_closed")
            finally:
                if descriptor is not None:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass

            binding.verify()
            current_temp = binding.stat_name(temp_name)
            if not (
                temp_identity is not None
                and _claim_same_identity(temp_identity, current_temp)
                and _claim_safe_regular(current_temp)
                and current_temp.st_size == len(body)
            ):
                raise _ClaimAuthorityError("claim_publish_changed")
            try:
                binding.link_name(temp_name, final_name)
            except FileExistsError:
                _unlink_bound_identity(binding, temp_name, temp_identity)
                temp_identity = None
                return (
                    "request_replayed"
                    if _existing_claim_matches(binding, final_name, plan)
                    else "request_claim_failed"
                )
            named_publication = binding.stat_name(final_name)
            if not (
                temp_identity is not None
                and _claim_same_identity(temp_identity, named_publication)
                and _claim_safe_regular(named_publication, links=2)
            ):
                raise _ClaimAuthorityError("claim_publish_changed")
            # Retain only the identity we created. Cleanup must never adopt and
            # delete an attacker's replacement merely because it currently
            # occupies the public name.
            published_identity = temp_identity
            binding.unlink_name(temp_name)
            temp_identity = None
            self._stage("marker_published")
            binding.fsync_directory()
            binding.verify()
            raw, final_information = _read_bound_claim(binding, final_name)
            if (
                not _claim_marker_matches(raw, plan)
                or not _claim_same_identity(published_identity, final_information)
            ):
                raise _ClaimAuthorityError("claim_publish_changed")
            self._stage("marker_verified")
            return None
        except _ClaimAuthorityError as error:
            # A moved/replaced directory must not retain a marker at the held
            # object. Other post-publication failures leave the exact marker
            # in place so a retry cannot perform the one-use action again.
            if str(error) in {"claim_directory_changed", "claim_publish_changed"}:
                _unlink_bound_identity(binding, final_name, published_identity)
            raise
        finally:
            _unlink_bound_identity(binding, temp_name, temp_identity)

    def claim(
        self,
        plan: SecureIntakePlan,
        *,
        expected_plan_digest: str,
        current_owner_binding: str,
        now: datetime,
    ) -> str | None:
        failure = validate_secure_intake_plan(
            plan,
            expected_plan_digest=expected_plan_digest,
            current_owner_binding=current_owner_binding,
            now=now,
        )
        if failure:
            return failure
        if not self._configuration_valid:
            return "request_claim_failed"

        final_name = f"{plan.request_id}.claim.json"
        temp_name = f".{plan.request_id}.{secrets.token_hex(16)}.claim.tmp"
        claimed_at = _timestamp(now)
        body = (_canonical_json(_claim_marker_document(plan, claimed_at)) + "\n").encode(
            "utf-8"
        )
        try:
            with _bind_claim_directory(
                self._directory,
                must_exist_root=self._authority_root,
            ) as binding:
                return self._claim_bound(
                    binding,
                    plan,
                    final_name=final_name,
                    temp_name=temp_name,
                    body=body,
                )
        except (OSError, ValueError, TypeError):
            # Temp files are non-authoritative.  If a directory identity
            # changed, cleanup occurs through the held exact directory binding
            # before its descriptor/Windows handles close wherever possible.
            return "request_claim_failed"


class HumanOnlySecretUI(Protocol):
    """Worker-process-only source of one mutable secret buffer."""

    def request_secret(self, *, request_id: str) -> bytearray | None: ...


@dataclass
class WindowsMaskedDialog:
    """Windows masked-dialog boundary with an injected native prompt.

    ``native_prompt`` must render in the interactive user's desktop and return
    a mutable UTF-8 buffer to the worker process.  This class intentionally
    does not fall back to stdin, environment variables, command arguments, the
    clipboard, or a plaintext file.
    """

    native_prompt: Callable[[str], bytearray | None] = field(repr=False)

    def request_secret(self, *, request_id: str) -> bytearray | None:
        if REQUEST_ID_RE.fullmatch(request_id) is None:
            raise RuntimeError("secure_intake_input_unavailable")
        try:
            value = self.native_prompt(request_id)
        except Exception:
            raise RuntimeError("secure_intake_input_unavailable") from None
        if value is not None and not isinstance(value, bytearray):
            raise RuntimeError("secure_intake_input_unavailable")
        return value


class ExactCredentialStore(Protocol):
    backend_kind: str

    def put_exact(self, backend_id: str, secret: memoryview) -> None: ...

    def probe_exact(self, backend_id: str) -> bool: ...

    def delete_exact(self, backend_id: str) -> None: ...


class WindowsCredentialManagerNativeCalls(Protocol):
    """The only native calls allowed by the exact Windows adapter."""

    def write_generic(self, target_name: str, secret: memoryview) -> None: ...

    def generic_exists(self, target_name: str) -> bool: ...

    def delete_generic(self, target_name: str) -> None: ...


@dataclass
class WindowsCredentialManagerExactStore:
    """Exact Generic Credential adapter; enumeration is not part of its API."""

    native: WindowsCredentialManagerNativeCalls = field(repr=False)
    target_prefix: str = "WOM/credential-intake/"
    backend_kind: str = "windows_credential_manager_generic"

    def _target(self, backend_id: str) -> str:
        if BACKEND_ID_RE.fullmatch(backend_id) is None:
            raise ValueError("secure_intake_backend_id_invalid")
        return f"{self.target_prefix}{backend_id}"

    def put_exact(self, backend_id: str, secret: memoryview) -> None:
        self.native.write_generic(self._target(backend_id), secret)

    def probe_exact(self, backend_id: str) -> bool:
        return bool(self.native.generic_exists(self._target(backend_id)))

    def delete_exact(self, backend_id: str) -> None:
        self.native.delete_generic(self._target(backend_id))


@dataclass(frozen=True)
class VerifiedCredentialIdentity:
    """Private identity evidence returned by a provider adapter."""

    provider: str
    account_subject: str = field(repr=False)
    workspace_identity: str = field(repr=False)
    reviewed_anchor_uuid: str
    capabilities: tuple[str, ...]
    subject_verified: bool = True
    anchor_access_verified: bool = True


class ProviderIdentityVerifier(Protocol):
    def verify_identity(
        self,
        secret: memoryview,
        *,
        provider: str,
        reviewed_anchor_uuid: str,
    ) -> VerifiedCredentialIdentity: ...


class AtomicReceiptCommitter(Protocol):
    def commit_atomic(self, receipt: Mapping[str, Any]) -> str: ...


class AtomicJsonReceiptCommitter:
    """Durably commits one non-secret receipt with create-if-absent semantics."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root)

    def commit_atomic(self, receipt: Mapping[str, Any]) -> str:
        credential_id = str(receipt.get("credential_id") or "")
        if CREDENTIAL_ID_RE.fullmatch(credential_id) is None:
            raise ValueError("secure_intake_receipt_invalid")
        self._root.mkdir(parents=True, exist_ok=True)
        destination = self._root / f"{credential_id}.json"
        temporary = self._root / f".{credential_id}.{secrets.token_hex(8)}.tmp"
        descriptor: int | None = None
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            body = (_canonical_json(dict(receipt)) + "\n").encode("utf-8")
            written = 0
            while written < len(body):
                count = os.write(descriptor, body[written:])
                if count <= 0:
                    raise OSError
                written += count
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = None
            # A same-directory hard link is an atomic create-if-absent commit:
            # unlike replace(), it can never overwrite an existing receipt.
            os.link(temporary, destination)
            try:
                temporary.unlink()
            except OSError:
                # The destination is already committed.  A stale non-secret
                # temp receipt is a cleanup concern, not a reason to delete the
                # now-durable credential from its encrypted backend.
                pass
            try:
                directory_descriptor = os.open(self._root, os.O_RDONLY)
                try:
                    os.fsync(directory_descriptor)
                finally:
                    os.close(directory_descriptor)
            except OSError:
                # Windows may not allow fsync on a directory.  File fsync and
                # atomic replace still provide the supported durability floor.
                pass
        except Exception:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise RuntimeError("secure_intake_receipt_commit_failed") from None
        return destination.name


def _validate_identity(
    identity: VerifiedCredentialIdentity,
    plan: SecureIntakePlan,
) -> tuple[str | None, tuple[str, ...]]:
    try:
        provider = _safe_provider(identity.provider)
        account_subject = _safe_text(
            identity.account_subject, "secure_intake_provider_identity_invalid", maximum=512
        )
        workspace_identity = _safe_text(
            identity.workspace_identity, "secure_intake_provider_identity_invalid", maximum=512
        )
        anchor = _safe_uuid(
            identity.reviewed_anchor_uuid, "secure_intake_provider_identity_invalid"
        )
        capabilities = _normalize_capabilities(identity.capabilities)
    except (AttributeError, TypeError, ValueError):
        return "provider_identity_unverified", ()
    if not identity.subject_verified or provider != plan.provider or not account_subject:
        return "provider_identity_unverified", ()
    if not identity.anchor_access_verified or anchor != plan.reviewed_anchor_uuid or not workspace_identity:
        return "workspace_anchor_mismatch", ()
    requested = set(plan.requested_capabilities)
    if requested and not requested.issubset(capabilities):
        return "provider_identity_unverified", ()
    return None, capabilities


def _fingerprint(secret: memoryview, key: bytes | bytearray) -> str:
    # Keep the complete HMAC digest. It is already non-reversible and avoids
    # weakening the collision boundary used to distinguish multiple still-
    # valid credentials for one account/workspace.
    return "hmac-sha256:" + hmac.new(key, secret, hashlib.sha256).hexdigest()


def _identity_fingerprint(value: str) -> str:
    # Identity fingerprints are canonical cross-module scope keys.  Unlike the
    # secret-derived HMAC display digest, they retain the full SHA-256 width so
    # recovery manifests can bind to the exact same workspace identity.
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _rollback(store: ExactCredentialStore, backend_id: str) -> str:
    try:
        store.delete_exact(backend_id)
        return "deleted"
    except Exception:
        return "delete_failed"


@dataclass
class SecureIntakeWorker:
    """Runs the entire secret-bearing transaction inside one worker process."""

    claims: OneTimeRequestClaims = field(repr=False)
    ui: HumanOnlySecretUI = field(repr=False)
    store: ExactCredentialStore = field(repr=False)
    verifier: ProviderIdentityVerifier = field(repr=False)
    receipt_committer: AtomicReceiptCommitter = field(repr=False)
    fingerprint_key: bytes | bytearray = field(repr=False)
    credential_id_factory: Callable[[], str] = field(
        default=lambda: _opaque_id("cred"), repr=False
    )
    backend_id_factory: Callable[[], str] = field(
        default=lambda: _opaque_id("backend"), repr=False
    )
    now_factory: Callable[[], datetime] = field(default=_utc_now, repr=False)

    def execute(
        self,
        plan: SecureIntakePlan,
        *,
        expected_plan_digest: str,
        current_owner_binding: str,
    ) -> dict[str, Any]:
        """Execute once and wipe a mutable, derived fingerprint key."""

        try:
            return self._execute_once(
                plan,
                expected_plan_digest=expected_plan_digest,
                current_owner_binding=current_owner_binding,
            )
        finally:
            if isinstance(self.fingerprint_key, bytearray):
                for index in range(len(self.fingerprint_key)):
                    self.fingerprint_key[index] = 0

    def _execute_once(
        self,
        plan: SecureIntakePlan,
        *,
        expected_plan_digest: str,
        current_owner_binding: str,
    ) -> dict[str, Any]:
        try:
            moment = _as_utc(self.now_factory())
            claim_failure = self.claims.claim(
                plan,
                expected_plan_digest=expected_plan_digest,
                current_owner_binding=current_owner_binding,
                now=moment,
            )
        except Exception:
            return _fixed_failure("request_claim_failed")
        if claim_failure:
            return _fixed_failure(claim_failure)
        if not isinstance(self.fingerprint_key, (bytes, bytearray)) or len(self.fingerprint_key) < MIN_FINGERPRINT_KEY_BYTES:
            return _fixed_failure("worker_result_invalid")
        try:
            backend_kind = _safe_purpose(self.store.backend_kind)
        except Exception:
            return _fixed_failure("worker_result_invalid")

        secret: bytearray | None = None
        stored = False
        backend_id = ""

        def rollback_once() -> str:
            nonlocal stored
            if not stored:
                return "not_required"
            status = _rollback(self.store, backend_id)
            stored = False
            return status

        try:
            try:
                secret = self.ui.request_secret(request_id=plan.request_id)
            except Exception:
                return _fixed_failure("secret_input_unavailable")
            if secret is None:
                return _fixed_failure("human_cancelled")
            if not isinstance(secret, bytearray) or not 0 < len(secret) <= MAX_SECRET_BYTES:
                return _fixed_failure("secret_input_unavailable")
            secret_view = memoryview(secret)

            backend_id = str(self.backend_id_factory())
            if BACKEND_ID_RE.fullmatch(backend_id) is None:
                return _fixed_failure("worker_result_invalid")
            try:
                # A native put may write and then fail while returning.  Mark
                # the entry as rollback-owned before crossing that boundary.
                stored = True
                self.store.put_exact(backend_id, secret_view)
            except Exception:
                return _fixed_failure(
                    "store_write_failed", rollback_status=rollback_once()
                )
            try:
                present = self.store.probe_exact(backend_id)
            except Exception:
                present = False
            if not present:
                return _fixed_failure(
                    "store_presence_not_verified",
                    rollback_status=rollback_once(),
                )
            try:
                identity = self.verifier.verify_identity(
                    secret_view,
                    provider=plan.provider,
                    reviewed_anchor_uuid=plan.reviewed_anchor_uuid,
                )
            except Exception:
                return _fixed_failure(
                    "provider_identity_unverified",
                    rollback_status=rollback_once(),
                )
            identity_failure, capabilities = _validate_identity(identity, plan)
            if identity_failure:
                return _fixed_failure(
                    identity_failure,
                    rollback_status=rollback_once(),
                )

            fingerprint_digest = _fingerprint(secret_view, self.fingerprint_key)
            account_fingerprint = _identity_fingerprint(identity.account_subject)
            workspace_fingerprint = _identity_fingerprint(identity.workspace_identity)
            credential_id = str(self.credential_id_factory())
            if CREDENTIAL_ID_RE.fullmatch(credential_id) is None:
                return _fixed_failure(
                    "worker_result_invalid", rollback_status=rollback_once()
                )
            verified_at = _timestamp(moment)
            receipt: dict[str, Any] = {
                "schema_version": RECEIPT_SCHEMA_VERSION,
                "credential_id": credential_id,
                "persisted": True,
                "provider": plan.provider,
                "account_label": plan.account_label,
                "workspace_label": plan.workspace_label,
                "purpose": plan.purpose,
                "verified_capabilities": list(capabilities),
                "encrypted_backend_kind": backend_kind,
                "encrypted_backend_id": backend_id,
                "fingerprint_digest": fingerprint_digest,
                "verified_account_fingerprint": account_fingerprint,
                "verified_workspace_fingerprint": workspace_fingerprint,
                "adopted_at": verified_at,
                "last_verified_at": verified_at,
                "rotation_status": "current",
                "lifecycle_status": "active",
                "is_default": False,
                "request_id": plan.request_id,
                "plan_digest": plan.plan_digest,
            }
            success_result: dict[str, Any] = {
                "schema_version": RESULT_SCHEMA_VERSION,
                "ok": True,
                "accepted": True,
                "persisted": True,
                "credential_id": credential_id,
                "provider": plan.provider,
                "account_label": plan.account_label,
                "workspace_label": plan.workspace_label,
                "purpose": plan.purpose,
                "verified_capabilities": list(capabilities),
                "encrypted_backend_kind": backend_kind,
                "encrypted_backend_id": backend_id,
                "fingerprint_digest": fingerprint_digest,
                "verified_account_fingerprint": account_fingerprint,
                "verified_workspace_fingerprint": workspace_fingerprint,
                "adopted_at": verified_at,
                "last_verified_at": verified_at,
                "rotation_status": "current",
                "lifecycle_status": "active",
                "is_default": False,
                "secret_value_present": False,
            }
            try:
                receipt_ref = self.receipt_committer.commit_atomic(receipt)
            except Exception:
                return _fixed_failure(
                    "receipt_commit_failed",
                    rollback_status=rollback_once(),
                )
            # Returning from commit_atomic means the non-secret receipt is
            # durable.  From this point the encrypted entry must not be rolled
            # back.  An invalid adapter reference is replaced with a safe
            # opaque handle instead of echoing untrusted text or breaking the
            # already-committed transaction.
            stored = False  # committed receipt now owns the store entry
            try:
                public_receipt_ref = str(receipt_ref or "")
            except Exception:
                public_receipt_ref = ""
            if (
                SAFE_RECEIPT_REF_RE.fullmatch(public_receipt_ref) is None
                or credential_id not in public_receipt_ref
            ):
                public_receipt_ref = f"receipt:{credential_id}"
            success_result["receipt_ref"] = public_receipt_ref
            return success_result
        except Exception:
            return _fixed_failure(
                "worker_result_invalid", rollback_status=rollback_once()
            )
        finally:
            if secret is not None:
                for index in range(len(secret)):
                    secret[index] = 0
            # ``stored`` can only remain true for a branch that failed before
            # its explicit rollback.  This final guard never runs after a
            # committed receipt.
            if stored and backend_id:
                rollback_once()


@dataclass(frozen=True)
class WorkerInvocation:
    """Secret-free payload that may cross from the AI parent to a worker."""

    plan: SecureIntakePlan
    expected_plan_digest: str

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "plan": self.plan.to_public_dict(),
            "expected_plan_digest": self.expected_plan_digest,
            "stdin_mode": "disabled",
            "secret_transport": "human_only_worker_ui",
        }


class IsolatedWorkerSpawner(Protocol):
    def run_worker(
        self, invocation: WorkerInvocation
    ) -> Mapping[str, Any] | _SecureIntakeWorkerRunOutcome: ...


@dataclass(frozen=True, repr=False)
class _SecureIntakeWorkerRunOutcome:
    """Trusted launcher evidence separating pre-start from post-start loss.

    Bare mappings remain supported for compatibility and are conservatively
    treated as having crossed a started worker boundary.  This private marker
    exists for an in-module process spawner that can prove ``start()`` did not
    return; arbitrary child mappings cannot claim the pre-start path.
    """

    worker_started: bool
    result: Mapping[str, Any] | None = field(default=None, repr=False)


@dataclass
class SecureIntakeProcessLauncher:
    """Parent-side launcher that transports plans and status/receipts only."""

    spawner: IsolatedWorkerSpawner = field(repr=False)

    def launch(
        self,
        plan: SecureIntakePlan,
        *,
        expected_plan_digest: str,
    ) -> dict[str, Any]:
        if not hmac.compare_digest(plan.plan_digest, str(expected_plan_digest or "")):
            return _fixed_failure("plan_digest_mismatch")
        invocation = WorkerInvocation(plan=plan, expected_plan_digest=expected_plan_digest)
        try:
            outcome = self.spawner.run_worker(invocation)
        except Exception:
            # A legacy/injected spawner exception does not prove whether its
            # child failed before or after process.start().  Never report an
            # exact-zero transaction outcome from missing start evidence.
            return _unknown_worker_result()
        if isinstance(outcome, _SecureIntakeWorkerRunOutcome):
            if outcome.worker_started is False and outcome.result is None:
                return _fixed_failure("worker_launch_failed")
            if outcome.worker_started is not True:
                return _unknown_worker_result()
            result = outcome.result
        else:
            # Backward-compatible bare mappings necessarily crossed the
            # untrusted worker-result boundary and therefore count as started.
            result = outcome
        if not isinstance(result, Mapping):
            return _unknown_worker_result()
        projected = _project_worker_result(result, plan=plan)
        return projected if projected is not None else _unknown_worker_result()


_WORKER_FAILURE_KEYS = {
    "schema_version",
    "ok",
    "accepted",
    "persisted",
    "reason_code",
    "operator_action",
    "rollback_status",
    "error",
}
_WORKER_SUCCESS_KEYS = {
    "schema_version",
    "ok",
    "accepted",
    "persisted",
    "credential_id",
    "provider",
    "account_label",
    "workspace_label",
    "purpose",
    "verified_capabilities",
    "encrypted_backend_kind",
    "encrypted_backend_id",
    "fingerprint_digest",
    "verified_account_fingerprint",
    "verified_workspace_fingerprint",
    "adopted_at",
    "last_verified_at",
    "rotation_status",
    "lifecycle_status",
    "is_default",
    "receipt_ref",
    "secret_value_present",
}
_WORKER_FAILURE_REASONS = frozenset(FAILURE_OPERATOR_ACTIONS) - {
    # Only the parent launcher can honestly assert that a worker did not
    # launch.  A mapping received across the child boundary cannot.
    "worker_launch_failed",
}
_WORKER_ROLLBACK_STATUSES = frozenset(
    {"not_required", "deleted", "delete_failed"}
)
_PRE_STORE_FAILURE_REASONS = frozenset(
    {
        "human_cancelled",
        "secret_input_unavailable",
        "request_expired",
        "request_replayed",
        "request_user_mismatch",
        "request_claim_failed",
        "plan_digest_mismatch",
    }
)


def _unknown_worker_result() -> dict[str, Any]:
    """Return one value-free result after a worker may have started."""

    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "ok": False,
        "accepted": None,
        "persisted": None,
        "reason_code": _UNKNOWN_WORKER_REASON,
        "operator_action": _UNKNOWN_WORKER_ACTION,
        "rollback_status": None,
        "error": _UNKNOWN_WORKER_ERROR,
        "secret_value_present": False,
        "reviewed_anchor_present_in_result": False,
        "backend_target_present": False,
        "durable_state": "unknown_may_have_changed",
        "worker_result_accepted": False,
        "operations": {
            "count_status": "unknown_may_be_nonzero",
            "human_secret_ui_calls": None,
            "encrypted_store_reads": None,
            "encrypted_store_writes": None,
            "provider_calls": None,
            "receipt_writes": None,
        },
    }


def _project_worker_failure(result: Mapping[str, Any]) -> dict[str, Any] | None:
    """Rebuild an exact fixed child failure without echoing child values."""

    try:
        plain = dict(result)
    except Exception:
        return None
    if set(plain) != _WORKER_FAILURE_KEYS:
        return None
    reason = plain.get("reason_code")
    rollback = plain.get("rollback_status")
    if not (
        plain.get("schema_version") == RESULT_SCHEMA_VERSION
        and type(plain.get("schema_version")) is str
        and plain.get("ok") is False
        and plain.get("accepted") is False
        and plain.get("persisted") is False
        and type(reason) is str
        and reason in _WORKER_FAILURE_REASONS
        and type(rollback) is str
        and rollback in _WORKER_ROLLBACK_STATUSES
        and (reason not in _PRE_STORE_FAILURE_REASONS or rollback == "not_required")
    ):
        return None
    projected = _fixed_failure(reason, rollback_status=rollback)
    return projected if plain == projected else None


def _project_worker_success(
    result: Mapping[str, Any], *, plan: SecureIntakePlan
) -> dict[str, Any] | None:
    """Rebuild the one success shape from plan-bound, bounded public values."""

    try:
        plain = dict(result)
    except Exception:
        return None
    if set(plain) != _WORKER_SUCCESS_KEYS:
        return None

    credential_id = plain.get("credential_id")
    backend_id = plain.get("encrypted_backend_id")
    backend_kind = plain.get("encrypted_backend_kind")
    fingerprint = plain.get("fingerprint_digest")
    account_fingerprint = plain.get("verified_account_fingerprint")
    workspace_fingerprint = plain.get("verified_workspace_fingerprint")
    receipt_ref = plain.get("receipt_ref")
    capabilities = plain.get("verified_capabilities")
    adopted_at = plain.get("adopted_at")
    last_verified_at = plain.get("last_verified_at")

    try:
        plan_created_at = _parse_timestamp(plan.created_at)
        plan_expires_at = _parse_timestamp(plan.expires_at)
        verified_at = _parse_timestamp(adopted_at)
        canonical_time = _timestamp(verified_at)
    except (TypeError, ValueError):
        return None

    allowed_capabilities = _LAUNCHER_PROVIDER_CAPABILITIES.get(plan.provider)
    if not (
        plain.get("schema_version") == RESULT_SCHEMA_VERSION
        and type(plain.get("schema_version")) is str
        and plain.get("ok") is True
        and plain.get("accepted") is True
        and plain.get("persisted") is True
        and type(credential_id) is str
        and CREDENTIAL_ID_RE.fullmatch(credential_id) is not None
        and PUBLIC_LABEL_SECRET_SHAPE_RE.search(
            credential_id.removeprefix("cred_")
        )
        is None
        and type(plain.get("provider")) is str
        and plain.get("provider") == plan.provider
        and type(plain.get("account_label")) is str
        and _safe_public_label(
            plain.get("account_label"), "secure_intake_worker_label_invalid"
        )
        == plan.account_label
        and type(plain.get("workspace_label")) is str
        and _safe_public_label(
            plain.get("workspace_label"), "secure_intake_worker_label_invalid"
        )
        == plan.workspace_label
        and type(plain.get("purpose")) is str
        and plain.get("purpose") == plan.purpose
        and type(capabilities) is list
        and len(capabilities) <= _LAUNCHER_MAX_VERIFIED_CAPABILITIES
        and all(type(capability) is str for capability in capabilities)
        and allowed_capabilities is not None
        and set(capabilities).issubset(allowed_capabilities)
        and capabilities == sorted(set(capabilities))
        and set(plan.requested_capabilities).issubset(capabilities)
        and type(backend_kind) is str
        and backend_kind in _LAUNCHER_ENCRYPTED_BACKEND_KINDS
        and type(backend_id) is str
        and BACKEND_ID_RE.fullmatch(backend_id) is not None
        and PUBLIC_LABEL_SECRET_SHAPE_RE.search(
            backend_id.removeprefix("backend_")
        )
        is None
        and type(fingerprint) is str
        and PUBLIC_FINGERPRINT_RE.fullmatch(fingerprint) is not None
        and type(account_fingerprint) is str
        and WORKSPACE_FINGERPRINT_RE.fullmatch(account_fingerprint) is not None
        and type(workspace_fingerprint) is str
        and WORKSPACE_FINGERPRINT_RE.fullmatch(workspace_fingerprint) is not None
        and type(adopted_at) is str
        and type(last_verified_at) is str
        and adopted_at == last_verified_at == canonical_time
        and plan_created_at <= verified_at < plan_expires_at
        and plain.get("rotation_status") == "current"
        and type(plain.get("rotation_status")) is str
        and plain.get("lifecycle_status") == "active"
        and type(plain.get("lifecycle_status")) is str
        and plain.get("is_default") is False
        and type(receipt_ref) is str
        and receipt_ref
        in {
            f"{credential_id}.json",
            f"receipts/{credential_id}.json",
            f"receipt:{credential_id}",
        }
        and plain.get("secret_value_present") is False
    ):
        return None

    # Reconstruct every output field.  Never return ``plain`` or the original
    # Mapping even after validation: custom child containers and extra values
    # must not survive the boundary.
    projected = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "ok": True,
        "accepted": True,
        "persisted": True,
        "credential_id": credential_id,
        "provider": plan.provider,
        "account_label": plan.account_label,
        "workspace_label": plan.workspace_label,
        "purpose": plan.purpose,
        "verified_capabilities": list(capabilities),
        "encrypted_backend_kind": backend_kind,
        "encrypted_backend_id": backend_id,
        "fingerprint_digest": fingerprint,
        "verified_account_fingerprint": account_fingerprint,
        "verified_workspace_fingerprint": workspace_fingerprint,
        "adopted_at": canonical_time,
        "last_verified_at": canonical_time,
        "rotation_status": "current",
        "lifecycle_status": "active",
        "is_default": False,
        "receipt_ref": receipt_ref,
        "secret_value_present": False,
    }
    return projected if plain == projected else None


def _project_worker_result(
    result: Mapping[str, Any], *, plan: SecureIntakePlan
) -> dict[str, Any] | None:
    """Reject exception-raising or contaminated child mappings safely."""

    try:
        if result.get("ok") is True:
            return _project_worker_success(result, plan=plan)
        return _project_worker_failure(result)
    except Exception:
        return None


def apply_duplicate_lifecycle_decision(
    receipts: Sequence[Mapping[str, Any]],
    *,
    selected_default_credential_id: str | None = None,
    revocation_pending_credential_ids: Sequence[str] = (),
    human_approved: bool = False,
) -> dict[str, Any]:
    """Classify duplicate valid credentials without deleting or revoking any.

    Every input must describe the same provider and verified workspace.  The
    helper distinguishes different HMAC fingerprint digests, but performs no
    backend delete and no provider revocation.  Without explicit human
    approval it returns a decision-required plan and leaves all states active.
    """

    rows: list[dict[str, Any]] = []
    providers: set[str] = set()
    workspaces: set[str] = set()
    credential_ids: set[str] = set()
    fingerprints: set[str] = set()
    for receipt in receipts:
        credential_id = str(receipt.get("credential_id") or "")
        provider = _safe_provider(receipt.get("provider"))
        workspace = str(receipt.get("verified_workspace_fingerprint") or "")
        fingerprint = str(receipt.get("fingerprint_digest") or "")
        if CREDENTIAL_ID_RE.fullmatch(credential_id) is None:
            raise ValueError("secure_intake_lifecycle_credential_invalid")
        if WORKSPACE_FINGERPRINT_RE.fullmatch(workspace) is None:
            raise ValueError("secure_intake_lifecycle_workspace_invalid")
        if PUBLIC_FINGERPRINT_RE.fullmatch(fingerprint) is None:
            raise ValueError("secure_intake_lifecycle_fingerprint_invalid")
        if credential_id in credential_ids:
            raise ValueError("secure_intake_lifecycle_duplicate_id")
        credential_ids.add(credential_id)
        providers.add(provider)
        workspaces.add(workspace)
        fingerprints.add(fingerprint)
        rows.append(
            {
                "credential_id": credential_id,
                "fingerprint_digest": fingerprint,
                "lifecycle_status": "active",
                "rotation_status": "current",
                "is_default": False,
            }
        )
    if not rows or len(providers) != 1 or len(workspaces) != 1:
        raise ValueError("secure_intake_lifecycle_scope_invalid")
    pending = set(revocation_pending_credential_ids)
    if not pending.issubset(credential_ids):
        raise ValueError("secure_intake_lifecycle_pending_invalid")
    if not human_approved:
        return {
            "schema_version": LIFECYCLE_SCHEMA_VERSION,
            "ok": True,
            "status": "human_decision_required",
            "provider": next(iter(providers)),
            "verified_workspace_fingerprint": next(iter(workspaces)),
            "credential_count": len(rows),
            "credentials": rows,
            "default_changed": False,
            "delete_performed": False,
            "revoke_performed": False,
        }
    if selected_default_credential_id not in credential_ids:
        raise ValueError("secure_intake_lifecycle_default_invalid")
    if selected_default_credential_id in pending:
        raise ValueError("secure_intake_lifecycle_default_pending")
    for row in rows:
        credential_id = row["credential_id"]
        if credential_id == selected_default_credential_id:
            row.update(
                {
                    "lifecycle_status": "active",
                    "rotation_status": "current",
                    "is_default": True,
                }
            )
        elif credential_id in pending:
            row.update(
                {
                    "lifecycle_status": "revocation_pending",
                    "rotation_status": "review_pending",
                }
            )
        else:
            row.update(
                {
                    "lifecycle_status": "legacy_valid",
                    "rotation_status": "legacy",
                }
            )
    return {
        "schema_version": LIFECYCLE_SCHEMA_VERSION,
        "ok": True,
        "status": "decision_recorded",
        "provider": next(iter(providers)),
        "verified_workspace_fingerprint": next(iter(workspaces)),
        "credential_count": len(rows),
        "credentials": rows,
        "default_changed": True,
        "delete_performed": False,
        "revoke_performed": False,
    }


__all__ = [
    "AtomicJsonReceiptCommitter",
    "AtomicReceiptCommitter",
    "ExactCredentialStore",
    "FileOneTimeRequestClaims",
    "HumanOnlySecretUI",
    "InMemoryOneTimeRequestClaims",
    "IsolatedWorkerSpawner",
    "ProviderIdentityVerifier",
    "SecureIntakePlan",
    "SecureIntakeProcessLauncher",
    "SecureIntakeWorker",
    "VerifiedCredentialIdentity",
    "WindowsCredentialManagerExactStore",
    "WindowsCredentialManagerNativeCalls",
    "WindowsMaskedDialog",
    "WorkerInvocation",
    "apply_duplicate_lifecycle_decision",
    "create_secure_intake_plan",
    "validate_secure_intake_plan",
]
