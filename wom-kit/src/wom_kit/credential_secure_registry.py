"""Authenticated local registry for securely-intaken credentials.

This module bridges :mod:`credential_secure_intake` receipts to a later WOM
process without asking a human to enter the same secret again.  It deliberately
keeps two different kinds of lookup separate:

* receipt discovery enumerates only the fixed, git-ignored archive directory;
* secret resolution reads one exact Windows Generic Credential target that was
  authenticated by that receipt.  It has no enumeration or fuzzy-search API.

Receipts and duplicate-lifecycle decisions are authenticated with a stable,
archive-specific key.  Public projections never contain the authentication
key, receipt MAC, encrypted backend id, raw credential, account identity, or
reviewed anchor id.  Plain ``_AtomicJsonReceiptCommitter`` receipts remain
discoverable as unauthenticated history, but are never broker-authoritative.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import stat
import threading
from typing import Any, Protocol, TypeVar

import yaml

from .credential_secure_intake import (
    _AtomicJsonReceiptCommitter,
    LEGACY_RECEIPT_SCHEMA_VERSION,
    NOTION_PAT_SCOPE_FINGERPRINT_DOMAIN,
    NOTION_PAT_WORKSPACE_IDENTITY_BASIS,
    NOTION_WORKSPACE_IDENTITY_BASES,
    NOTION_WORKSPACE_IDENTITY_BASIS,
    RECEIPT_SCHEMA_VERSION,
)
from .credential_secure_intake_windows import windows_credential_target
from .credential_capability import (
    CREDENTIAL_CAPABILITY_CONSUMER,
    CREDENTIAL_CAPABILITY_OPERATION,
    CREDENTIAL_CAPABILITY_PROVIDER,
    CREDENTIAL_CAPABILITY_REQUIRED_REGISTERED_CAPABILITIES,
    _CredentialCapability,
    CredentialCapabilityError,
    _CredentialCapabilityLease,
    CredentialCapabilityScope,
)
from .notion_http_adapter import _NotionBearerSecret
from .notion_page_recovery import ScopeBinding


RECEIPTS_RELATIVE = "profiles/local/credential-intake/receipts"
EVOLUTIONS_RELATIVE = "profiles/local/credential-intake/evolutions"
LIFECYCLE_RELATIVE = "profiles/local/credential-intake/lifecycle.json"
LOCK_RELATIVE = "profiles/local/credential-intake/.registry.lock"
CAPABILITY_CLAIMS_RELATIVE = "profiles/local/credential-capabilities/claims"

RECEIPT_AUTHENTICATION_SCHEMA = "wom-credential-receipt-authentication/v0.1"
LIFECYCLE_SCHEMA_VERSION = "wom-credential-secure-registry-lifecycle/v0.1"
LIFECYCLE_PLAN_SCHEMA_VERSION = "wom-credential-secure-registry-lifecycle-plan/v0.1"
LIFECYCLE_AUTHENTICATION_SCHEMA = "wom-credential-lifecycle-authentication/v0.1"
REGISTRY_RESULT_SCHEMA_VERSION = "wom-credential-secure-registry-result/v0.1"
WORKSPACE_SCOPE_EVOLUTION_SCHEMA_VERSION = (
    "wom-credential-workspace-scope-evolution/v0.1"
)
WORKSPACE_SCOPE_EVOLUTION_AUTHENTICATION_SCHEMA = (
    "wom-credential-workspace-scope-evolution-authentication/v0.1"
)
CAPABILITY_USE_CLAIM_SCHEMA_VERSION = "wom-credential-capability-use-claim/v0.1"
CAPABILITY_USE_SUMMARY_SCHEMA_VERSION = (
    "wom-credential-capability-use-summary/v0.1"
)
CAPABILITY_USE_CLAIM_AUTHENTICATION_SCHEMA = (
    "wom-credential-capability-use-claim-authentication/v0.1"
)
LEGACY_WORKSPACE_IDENTITY_BASIS = "legacy_reviewed_anchor_v1"

RECEIPT_AUTHENTICATION_DOMAIN = (
    b"wom/credential-secure-registry/receipt-authentication/v0.1\x00"
)
LIFECYCLE_AUTHENTICATION_DOMAIN = (
    b"wom/credential-secure-registry/lifecycle-authentication/v0.1\x00"
)
ARCHIVE_KEY_TARGET_DOMAIN = b"wom/credential-secure-registry/archive-key-target/v0.1\x00"
WORKSPACE_SCOPE_EVOLUTION_AUTHENTICATION_DOMAIN = (
    b"wom/credential-secure-registry/workspace-scope-evolution/v0.1\x00"
)
CAPABILITY_USE_CLAIM_AUTHENTICATION_DOMAIN = (
    b"wom/credential-secure-registry/capability-use-claim/v0.1\x00"
)

WINDOWS_ARCHIVE_KEY_TARGET_PREFIX = "WOM/credential-intake/backend_key_"

MAX_RECEIPT_BYTES = 64 * 1024
MAX_LIFECYCLE_BYTES = 256 * 1024
MAX_ARCHIVE_DOCUMENT_BYTES = 256 * 1024
MAX_RECEIPTS = 512
MAX_EVOLUTIONS = 512
MAX_EVOLUTION_BYTES = 64 * 1024
MAX_CAPABILITY_USE_CLAIM_BYTES = 64 * 1024
AUTHENTICATION_KEY_BYTES = 32
REPARSE_FLAG = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

_CREDENTIAL_ID_RE = re.compile(r"^cred_[A-Za-z0-9_-]{16,96}$")
_RECEIPT_TEMP_RE = re.compile(
    r"^\.(cred_[A-Za-z0-9_-]{16,96})\.[0-9a-f]{16}\.tmp$"
)
_EVOLUTION_FILE_RE = re.compile(
    r"^(cred_[A-Za-z0-9_-]{16,96})\.workspace-scope-v1\.json$"
)
_EVOLUTION_TEMP_RE = re.compile(
    r"^\.(cred_[A-Za-z0-9_-]{16,96})\.workspace-scope-v1\.[0-9a-f]{16}\.tmp$"
)
_BACKEND_ID_RE = re.compile(r"^backend_[A-Za-z0-9_-]{16,96}$")
_REQUEST_ID_RE = re.compile(r"^intake_[A-Za-z0-9_-]{16,96}$")
_PROVIDER_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_PURPOSE_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_HEX_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_HMAC_SHA256_RE = re.compile(r"^hmac-sha256:[0-9a-f]{64}$")
_CAPABILITY_ID_RE = re.compile(r"^cap_[0-9a-f]{32}$")
_SAFE_ARCHIVE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+/-]{0,255}$")
_SAFE_REVISION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+-]{0,127}$")
_SAFE_REVIEWER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@:+-]{0,127}$")
_SECRET_SHAPE_RE = re.compile(
    r"(?i)(?:github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{8,}"
    r"|(?:secret|ntn)_[A-Za-z0-9_-]{12,})"
)
_TIMESTAMP_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})$"
)

_RECEIPT_KEYS = {
    "schema_version",
    "credential_id",
    "persisted",
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
    "request_id",
    "plan_digest",
}
_RECEIPT_V2_KEYS = _RECEIPT_KEYS | {"workspace_identity_basis"}
_RECEIPT_AUTH_KEYS = {"schema_version", "algorithm", "mac"}
_LIFECYCLE_KEYS = {"schema_version", "archive_id", "scopes", "authentication"}
_LIFECYCLE_SCOPE_KEYS = {
    "provider",
    "workspace_fingerprint",
    "revision",
    "plan_sha256",
    "reviewed_by",
    "credentials",
}
_LIFECYCLE_CREDENTIAL_KEYS = {
    "credential_id",
    "lifecycle_status",
    "rotation_status",
    "is_default",
}
_AUTHENTICATION_KEYS = {"schema_version", "algorithm", "mac"}
_EVOLUTION_KEYS = {
    "schema_version",
    "credential_id",
    "provider",
    "base_receipt_sha256",
    "previous_workspace_fingerprint",
    "previous_workspace_identity_basis",
    "verified_account_fingerprint",
    "verified_capabilities",
    "evolved_workspace_fingerprint",
    "workspace_identity_basis",
    "evolved_at",
    "authentication",
}
_CAPABILITY_USE_CLAIM_KEYS = {
    "schema_version",
    "archive_id",
    "capability_id",
    "capability_sha256",
    "request_sha256",
    "plan_sha256",
    "provider",
    "operation",
    "consumer",
    "max_uses",
    "max_provider_requests",
    "status",
    "started_at",
    "finished_at",
    "failure_code",
    "provider_requests_authorized",
    "authentication",
}

_THREAD_LOCKS: dict[str, threading.RLock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()

_T = TypeVar("_T")


class SecureCredentialRegistryError(RuntimeError):
    """Sanitized registry error containing only one stable reason code."""

    def __init__(self, code: str) -> None:
        self.code = code if _PURPOSE_RE.fullmatch(str(code or "")) else "credential_registry_error"
        super().__init__(self.code)


def _fail(code: str) -> SecureCredentialRegistryError:
    return SecureCredentialRegistryError(code)


class ExactWindowsCredentialNative(Protocol):
    """Exact-only Windows operations required by this registry.

    Implementations intentionally expose no enumerate, search, or delete method.
    """

    def write_generic(self, target_name: str, secret: memoryview) -> None: ...

    def generic_exists(self, target_name: str) -> bool: ...

    def read_generic_secret_exact(self, target_name: str) -> bytearray: ...


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise _fail("credential_registry_document_invalid") from None


def _is_reparse(info: os.stat_result) -> bool:
    return bool(
        stat.S_ISLNK(info.st_mode)
        or (REPARSE_FLAG and getattr(info, "st_file_attributes", 0) & REPARSE_FLAG)
    )


def _validated_archive_root(archive_root: Path | str) -> Path:
    supplied = Path(archive_root)
    if not supplied.is_absolute():
        supplied = Path(os.path.abspath(str(supplied)))
    try:
        info = os.lstat(supplied)
        if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
            raise _fail("credential_registry_archive_root_unsafe")
        return supplied.resolve(strict=True)
    except SecureCredentialRegistryError:
        raise
    except OSError:
        raise _fail("credential_registry_archive_root_unavailable") from None


def _archive_path(root: Path, relative: str) -> Path:
    parts = Path(relative).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise _fail("credential_registry_internal_path_invalid")
    candidate = root.joinpath(*parts)
    try:
        candidate.relative_to(root)
    except ValueError:
        raise _fail("credential_registry_internal_path_invalid") from None
    return candidate


def _ensure_safe_parent_chain(
    root: Path,
    path: Path,
    *,
    leaf_reparse_code: str = "credential_registry_local_document_unsafe",
) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError:
        raise _fail("credential_registry_internal_path_invalid") from None
    current = root
    for part in relative.parts[:-1]:
        current = current / part
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            continue
        except OSError:
            raise _fail("credential_registry_local_parent_unavailable") from None
        if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
            raise _fail("credential_registry_local_parent_unsafe")
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return
    except OSError:
        raise _fail("credential_registry_local_document_unavailable") from None
    if _is_reparse(info):
        raise _fail(leaf_reparse_code)


def _read_exact_bytes(path: Path, *, maximum: int, missing_code: str) -> bytes:
    try:
        before = os.lstat(path)
    except FileNotFoundError:
        raise _fail(missing_code) from None
    except OSError:
        raise _fail("credential_registry_local_document_unavailable") from None
    if _is_reparse(before) or not stat.S_ISREG(before.st_mode):
        raise _fail("credential_registry_local_document_unsafe")
    if before.st_size <= 0 or before.st_size > maximum:
        raise _fail("credential_registry_local_document_size_invalid")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if (
            _is_reparse(opened)
            or not stat.S_ISREG(opened.st_mode)
            or opened.st_size != before.st_size
            or (before.st_ino and opened.st_ino and before.st_ino != opened.st_ino)
            or (before.st_dev and opened.st_dev and before.st_dev != opened.st_dev)
        ):
            raise _fail("credential_registry_local_document_changed")
        chunks: list[bytes] = []
        remaining = opened.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 65536))
            if not chunk:
                raise _fail("credential_registry_local_document_changed")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise _fail("credential_registry_local_document_changed")
        return b"".join(chunks)
    except SecureCredentialRegistryError:
        raise
    except OSError:
        raise _fail("credential_registry_local_document_unavailable") from None
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _ensure_local_profile_ignored(root: Path) -> None:
    gitignore = _archive_path(root, ".gitignore")
    body = _read_exact_bytes(
        gitignore,
        maximum=MAX_ARCHIVE_DOCUMENT_BYTES,
        missing_code="credential_registry_local_profile_not_ignored",
    )
    try:
        lines = body.decode("utf-8-sig").splitlines()
    except UnicodeError:
        raise _fail("credential_registry_local_profile_not_ignored") from None
    normalized = {
        line.strip().replace("\\", "/")
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    }
    if not normalized.intersection(
        {"profiles/local/", "/profiles/local/", "profiles/local", "/profiles/local"}
    ):
        raise _fail("credential_registry_local_profile_not_ignored")
    # A later gitignore negation can make a private credential receipt or
    # request trackable even though the broad directory rule is present.
    # Fail closed for every negation that can target this subtree.
    for pattern in normalized:
        if not pattern.startswith("!"):
            continue
        target = pattern[1:].lstrip("/")
        if (
            target in {"profiles", "profiles/", "profiles/local", "profiles/local/"}
            or target.startswith("profiles/local/")
            or target.startswith("profiles/**")
            or target in {"*", "**", "**/*"}
        ):
            raise _fail("credential_registry_local_profile_not_ignored")


def _read_archive_id(root: Path) -> str:
    path = _archive_path(root, "archive.yml")
    body = _read_exact_bytes(
        path,
        maximum=MAX_ARCHIVE_DOCUMENT_BYTES,
        missing_code="credential_registry_archive_identity_missing",
    )
    try:
        document = yaml.safe_load(body.decode("utf-8-sig"))
    except (UnicodeError, yaml.YAMLError):
        raise _fail("credential_registry_archive_identity_invalid") from None
    if not isinstance(document, Mapping):
        raise _fail("credential_registry_archive_identity_invalid")
    archive_id = document.get("archive_id")
    if not isinstance(archive_id, str) or _SAFE_ARCHIVE_ID_RE.fullmatch(archive_id) is None:
        raise _fail("credential_registry_archive_identity_invalid")
    return archive_id


def _validate_archive(archive_root: Path | str) -> tuple[Path, str]:
    root = _validated_archive_root(archive_root)
    _ensure_local_profile_ignored(root)
    return root, _read_archive_id(root)


def _safe_text(value: Any, code: str, *, maximum: int = 128) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise _fail(code)
    if value != value.strip() or any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise _fail(code)
    return value


def _validate_timestamp(value: Any) -> str:
    if not isinstance(value, str) or _TIMESTAMP_RE.fullmatch(value) is None:
        raise _fail("credential_registry_receipt_timestamp_invalid")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise _fail("credential_registry_receipt_timestamp_invalid") from None
    return value


def _validate_authentication_key(
    key: bytes | bytearray | memoryview,
) -> bytes | bytearray:
    if isinstance(key, memoryview):
        # The archive key provider deliberately supplies a full mutable view
        # and wipes its backing bytearray when the callback returns. Reusing
        # that exact backing buffer avoids leaving an unwipeable immutable
        # bytes copy behind in the trusted worker or recovery process.
        if (
            key.readonly
            or not key.c_contiguous
            or key.itemsize != 1
            or not isinstance(key.obj, bytearray)
            or key.nbytes != len(key.obj)
        ):
            raise _fail("credential_registry_authentication_key_invalid")
        material = key.obj
    elif isinstance(key, bytearray):
        material = key
    elif isinstance(key, bytes):
        material = key
    else:
        raise _fail("credential_registry_authentication_key_invalid")
    if len(material) < AUTHENTICATION_KEY_BYTES or len(material) > 4096:
        raise _fail("credential_registry_authentication_key_invalid")
    return material


def _validate_receipt_document(document: Any, *, authentication_optional: bool) -> dict[str, Any]:
    if not isinstance(document, Mapping):
        raise _fail("credential_registry_receipt_schema_invalid")
    result = dict(document)
    keys = set(result)
    schema_version = result.get("schema_version")
    if schema_version == LEGACY_RECEIPT_SCHEMA_VERSION:
        expected = set(_RECEIPT_KEYS)
    elif schema_version == RECEIPT_SCHEMA_VERSION:
        expected = set(_RECEIPT_V2_KEYS)
    else:
        raise _fail("credential_registry_receipt_schema_invalid")
    if authentication_optional:
        if keys not in (expected, expected | {"receipt_authentication"}):
            raise _fail("credential_registry_receipt_schema_invalid")
    elif keys != expected:
        raise _fail("credential_registry_receipt_schema_invalid")
    if schema_version == RECEIPT_SCHEMA_VERSION and (
        result.get("workspace_identity_basis") not in NOTION_WORKSPACE_IDENTITY_BASES
    ):
        raise _fail("credential_registry_receipt_identity_basis_invalid")
    credential_id = result.get("credential_id")
    if not isinstance(credential_id, str) or _CREDENTIAL_ID_RE.fullmatch(credential_id) is None:
        raise _fail("credential_registry_receipt_credential_invalid")
    if result.get("persisted") is not True:
        raise _fail("credential_registry_receipt_not_persisted")
    provider = result.get("provider")
    purpose = result.get("purpose")
    if not isinstance(provider, str) or _PROVIDER_RE.fullmatch(provider) is None:
        raise _fail("credential_registry_receipt_provider_invalid")
    if not isinstance(purpose, str) or _PURPOSE_RE.fullmatch(purpose) is None:
        raise _fail("credential_registry_receipt_purpose_invalid")
    _safe_text(result.get("account_label"), "credential_registry_receipt_label_invalid")
    _safe_text(result.get("workspace_label"), "credential_registry_receipt_label_invalid")
    capabilities = result.get("verified_capabilities")
    if not isinstance(capabilities, list):
        raise _fail("credential_registry_receipt_capabilities_invalid")
    normalized_capabilities: list[str] = []
    for capability in capabilities:
        if not isinstance(capability, str) or _PURPOSE_RE.fullmatch(capability) is None:
            raise _fail("credential_registry_receipt_capabilities_invalid")
        normalized_capabilities.append(capability)
    if normalized_capabilities != sorted(set(normalized_capabilities)):
        raise _fail("credential_registry_receipt_capabilities_invalid")
    backend_kind = result.get("encrypted_backend_kind")
    backend_id = result.get("encrypted_backend_id")
    if not isinstance(backend_kind, str) or _PURPOSE_RE.fullmatch(backend_kind) is None:
        raise _fail("credential_registry_receipt_backend_invalid")
    if not isinstance(backend_id, str) or _BACKEND_ID_RE.fullmatch(backend_id) is None:
        raise _fail("credential_registry_receipt_backend_invalid")
    if not isinstance(result.get("fingerprint_digest"), str) or _HMAC_SHA256_RE.fullmatch(
        result["fingerprint_digest"]
    ) is None:
        raise _fail("credential_registry_receipt_fingerprint_invalid")
    for key in ("verified_account_fingerprint", "verified_workspace_fingerprint"):
        value = result.get(key)
        if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
            raise _fail("credential_registry_receipt_identity_invalid")
    if (
        schema_version == RECEIPT_SCHEMA_VERSION
        and result.get("workspace_identity_basis")
        == NOTION_PAT_WORKSPACE_IDENTITY_BASIS
        and not hmac.compare_digest(
            result["verified_workspace_fingerprint"],
            _notion_pat_scope_fingerprint(result["fingerprint_digest"]),
        )
    ):
        raise _fail("credential_registry_receipt_identity_invalid")
    _validate_timestamp(result.get("adopted_at"))
    _validate_timestamp(result.get("last_verified_at"))
    if result.get("rotation_status") not in {"current", "legacy", "review_pending"}:
        raise _fail("credential_registry_receipt_lifecycle_invalid")
    if result.get("lifecycle_status") not in {"active", "legacy_valid", "revocation_pending"}:
        raise _fail("credential_registry_receipt_lifecycle_invalid")
    if not isinstance(result.get("is_default"), bool):
        raise _fail("credential_registry_receipt_lifecycle_invalid")
    request_id = result.get("request_id")
    if not isinstance(request_id, str) or _REQUEST_ID_RE.fullmatch(request_id) is None:
        raise _fail("credential_registry_receipt_request_invalid")
    plan_digest = result.get("plan_digest")
    if not isinstance(plan_digest, str) or _HEX_SHA256_RE.fullmatch(plan_digest) is None:
        raise _fail("credential_registry_receipt_plan_invalid")
    if "receipt_authentication" in result:
        authentication = result["receipt_authentication"]
        if not isinstance(authentication, Mapping) or set(authentication) != _RECEIPT_AUTH_KEYS:
            raise _fail("credential_registry_receipt_authentication_invalid")
        if (
            authentication.get("schema_version") != RECEIPT_AUTHENTICATION_SCHEMA
            or authentication.get("algorithm") != "hmac-sha256"
            or not isinstance(authentication.get("mac"), str)
            or _HEX_SHA256_RE.fullmatch(authentication["mac"]) is None
        ):
            raise _fail("credential_registry_receipt_authentication_invalid")
    return result


def _receipt_authentication_payload(document: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(document)
    payload.pop("receipt_authentication", None)
    return payload


def _receipt_mac(document: Mapping[str, Any], key: bytes | bytearray) -> str:
    return hmac.new(
        key,
        RECEIPT_AUTHENTICATION_DOMAIN + _canonical_json_bytes(
            _receipt_authentication_payload(document)
        ),
        hashlib.sha256,
    ).hexdigest()


def _notion_pat_scope_fingerprint(credential_fingerprint: str) -> str:
    """Derive the only valid authority scope for a person/PAT receipt."""

    if _HMAC_SHA256_RE.fullmatch(credential_fingerprint) is None:
        raise _fail("credential_registry_evolution_identity_invalid")
    return "sha256:" + hashlib.sha256(
        NOTION_PAT_SCOPE_FINGERPRINT_DOMAIN
        + credential_fingerprint.encode("ascii")
    ).hexdigest()


def _receipt_authentication_status(
    document: Mapping[str, Any], key: bytes | bytearray | None
) -> str:
    authentication = document.get("receipt_authentication")
    if not isinstance(authentication, Mapping):
        return "missing"
    if key is None:
        return "not_checked"
    actual = str(authentication.get("mac") or "")
    expected = _receipt_mac(document, key)
    return "valid" if hmac.compare_digest(actual, expected) else "invalid"


class _InterprocessLock:
    def __init__(self, path: Path, *, create_if_missing: bool = True) -> None:
        self.path = path
        self.create_if_missing = create_if_missing
        self._handle: Any = None

    def __enter__(self) -> "_InterprocessLock":
        _ensure_safe_parent_chain(self.path.parents[3], self.path)
        if self.create_if_missing:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                from ._windows_file_safety import (
                    open_regular_rw_descriptor_no_reparse,
                )

                descriptor = open_regular_rw_descriptor_no_reparse(
                    self.path,
                    create_if_missing=self.create_if_missing,
                )
                self._handle = os.fdopen(descriptor, "r+b")
            else:
                flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
                if self.create_if_missing:
                    flags |= os.O_CREAT
                descriptor = os.open(self.path, flags, 0o600)
                self._handle = os.fdopen(descriptor, "r+b")
            self._handle.seek(0, os.SEEK_END)
            if self._handle.tell() == 0:
                if not self.create_if_missing:
                    raise OSError
                self._handle.write(b"\0")
                self._handle.flush()
                os.fsync(self._handle.fileno())
            self._handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._handle.fileno(), msvcrt.LK_LOCK, 1)
            else:  # pragma: no cover - Windows is the primary supported host.
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX)
            return self
        except Exception:
            if self._handle is not None:
                self._handle.close()
                self._handle = None
            raise _fail("credential_registry_lock_failed") from None

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        del exc_type, exc, traceback
        if self._handle is None:
            return
        try:
            self._handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:  # pragma: no cover
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        finally:
            self._handle.close()
            self._handle = None


def _thread_lock_for(root: Path) -> threading.RLock:
    key = os.path.normcase(str(root))
    with _THREAD_LOCKS_GUARD:
        return _THREAD_LOCKS.setdefault(key, threading.RLock())


@contextmanager
def _archive_lock(root: Path, *, create_if_missing: bool = True):
    lock_path = _archive_path(root, LOCK_RELATIVE)
    with _thread_lock_for(root):
        if not create_if_missing:
            try:
                os.lstat(lock_path)
            except FileNotFoundError:
                # Empty/read-only registries do not need an on-disk lock. All
                # registry writes create the permanent one-byte lock before
                # publishing any state, so an existing registry is still read
                # under the interprocess lock.
                yield
                return
            except OSError:
                raise _fail("credential_registry_lock_failed") from None
        with _InterprocessLock(
            lock_path, create_if_missing=create_if_missing
        ):
            yield


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except (OSError, ValueError):
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _atomic_replace_json(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
    body = _canonical_json_bytes(document) + b"\n"
    descriptor: int | None = None
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_BINARY", 0),
            0o600,
        )
        written = 0
        while written < len(body):
            count = os.write(descriptor, body[written:])
            if count <= 0:
                raise OSError
            written += count
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.replace(temporary, path)
        _fsync_directory(path.parent)
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
        raise _fail("credential_registry_atomic_write_failed") from None


def _atomic_create_json(
    root: Path, path: Path, document: Mapping[str, Any]
) -> tuple[bytes, bool]:
    """Publish one immutable canonical document; identical replay is success."""

    path.parent.mkdir(parents=True, exist_ok=True)
    _ensure_safe_parent_chain(root, path)
    body = _canonical_json_bytes(document) + b"\n"
    temporary = path.parent / (
        f".{path.name.removesuffix('.json')}.{secrets.token_hex(8)}.tmp"
    )
    descriptor: int | None = None
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_BINARY", 0),
            0o600,
        )
        written = 0
        while written < len(body):
            count = os.write(descriptor, body[written:])
            if count <= 0:
                raise OSError
            written += count
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        try:
            os.link(temporary, path)
            created = True
        except FileExistsError:
            existing = _read_exact_bytes(
                path,
                maximum=MAX_EVOLUTION_BYTES,
                missing_code="credential_registry_evolution_missing",
            )
            if not hmac.compare_digest(existing, body):
                raise _fail("credential_registry_evolution_conflict")
            created = False
        try:
            temporary.unlink()
        except OSError:
            pass
        _fsync_directory(path.parent)
        return body, created
    except SecureCredentialRegistryError:
        raise
    except Exception:
        raise _fail("credential_registry_evolution_commit_failed") from None
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


@dataclass(repr=False)
class _AuthenticatedArchiveReceiptCommitter:
    """Atomic intake committer fixed to one archive's ignored-local path."""

    archive_root: Path
    archive_id: str
    _authentication_key: bytes | bytearray = field(repr=False)

    def __repr__(self) -> str:
        return "<_AuthenticatedArchiveReceiptCommitter path=fixed key=redacted>"

    def commit_atomic(self, receipt: Mapping[str, Any]) -> str:
        root, archive_id = _validate_archive(self.archive_root)
        if archive_id != self.archive_id:
            raise _fail("credential_registry_archive_identity_changed")
        document = _validate_receipt_document(receipt, authentication_optional=False)
        if document["schema_version"] != RECEIPT_SCHEMA_VERSION:
            raise _fail("credential_registry_legacy_receipt_write_forbidden")
        authenticated = dict(document)
        authenticated["receipt_authentication"] = {
            "schema_version": RECEIPT_AUTHENTICATION_SCHEMA,
            "algorithm": "hmac-sha256",
            "mac": _receipt_mac(document, self._authentication_key),
        }
        _validate_receipt_document(authenticated, authentication_optional=True)
        receipts_root = _archive_path(root, RECEIPTS_RELATIVE)
        _ensure_safe_parent_chain(root, receipts_root)
        with _archive_lock(root):
            _ensure_safe_parent_chain(root, receipts_root)
            try:
                reference = _AtomicJsonReceiptCommitter(receipts_root).commit_atomic(
                    authenticated
                )
            except Exception:
                raise _fail("credential_registry_receipt_commit_failed") from None
            # _AtomicJsonReceiptCommitter returns only after file fsync and the
            # create-if-absent hard-link publication. Never introduce a new
            # failure after that commit point: the intake worker would
            # otherwise delete the encrypted entry while a valid persisted
            # receipt remained. Future reads authenticate the receipt again.
            return reference


def _create_archive_atomic_json_receipt_committer(
    archive_root: Path | str,
    *,
    expected_archive_id: str,
    receipt_authentication_key: bytes | bytearray | memoryview,
) -> _AuthenticatedArchiveReceiptCommitter:
    """Create an authenticated ``_AtomicJsonReceiptCommitter``-compatible adapter."""

    root, archive_id = _validate_archive(archive_root)
    if not (
        isinstance(expected_archive_id, str)
        and _SAFE_ARCHIVE_ID_RE.fullmatch(expected_archive_id) is not None
        and hmac.compare_digest(expected_archive_id, archive_id)
    ):
        raise _fail("credential_registry_archive_identity_changed")
    key = _validate_authentication_key(receipt_authentication_key)
    receipts_root = _archive_path(root, RECEIPTS_RELATIVE)
    _ensure_safe_parent_chain(root, receipts_root)
    return _AuthenticatedArchiveReceiptCommitter(root, archive_id, key)


@dataclass(repr=False)
class _StableArchiveFingerprintKeyProvider:
    """Create once and reuse one exact archive-specific Windows key.

    The only API is callback-based.  The mutable key buffer is wiped after the
    callback returns; callers should return a configured object, digest, or
    status rather than the key itself.
    """

    native: ExactWindowsCredentialNative = field(repr=False)
    random_bytes: Callable[[int], bytes] = field(default=secrets.token_bytes, repr=False)

    def __repr__(self) -> str:
        return "<_StableArchiveFingerprintKeyProvider native=exact key=redacted>"

    def _target(self, archive_id: str) -> str:
        digest = hashlib.sha256(
            ARCHIVE_KEY_TARGET_DOMAIN + archive_id.encode("utf-8")
        ).hexdigest()
        return WINDOWS_ARCHIVE_KEY_TARGET_PREFIX + digest

    def use_key(
        self,
        archive_root: Path | str,
        consumer: Callable[[memoryview], _T],
        *,
        create_if_missing: bool = False,
    ) -> _T:
        root, archive_id = _validate_archive(archive_root)
        if not callable(consumer):
            raise _fail("credential_registry_key_consumer_invalid")
        target = self._target(archive_id)
        key_buffer: bytearray | None = None
        candidate: bytearray | None = None
        try:
            with _archive_lock(root, create_if_missing=create_if_missing):
                try:
                    exists = bool(self.native.generic_exists(target))
                except Exception:
                    raise _fail("credential_registry_key_probe_failed") from None
                if not exists:
                    if create_if_missing is not True:
                        raise _fail("credential_registry_key_not_found")
                    try:
                        generated = self.random_bytes(AUTHENTICATION_KEY_BYTES)
                    except Exception:
                        raise _fail("credential_registry_key_generation_failed") from None
                    if not isinstance(generated, (bytes, bytearray)) or len(generated) != AUTHENTICATION_KEY_BYTES:
                        raise _fail("credential_registry_key_generation_failed")
                    candidate = bytearray(generated)
                    try:
                        self.native.write_generic(target, memoryview(candidate))
                        if not self.native.generic_exists(target):
                            raise _fail("credential_registry_key_persistence_failed")
                    except SecureCredentialRegistryError:
                        raise
                    except Exception:
                        raise _fail("credential_registry_key_persistence_failed") from None
                try:
                    key_buffer = self.native.read_generic_secret_exact(target)
                except Exception:
                    raise _fail("credential_registry_key_read_failed") from None
                if not isinstance(key_buffer, bytearray) or len(key_buffer) != AUTHENTICATION_KEY_BYTES:
                    raise _fail("credential_registry_key_invalid")
                if candidate is not None and not hmac.compare_digest(candidate, key_buffer):
                    raise _fail("credential_registry_key_persistence_failed")
            return consumer(memoryview(key_buffer))
        finally:
            for mutable in (candidate, key_buffer):
                if mutable is not None:
                    for index in range(len(mutable)):
                        mutable[index] = 0


@dataclass(frozen=True)
class _ReceiptRecord:
    path: Path = field(repr=False)
    raw: bytes = field(repr=False)
    document: Mapping[str, Any] = field(repr=False)
    receipt_sha256: str
    authentication_status: str
    effective_workspace_fingerprint: str
    workspace_identity_basis: str
    authority_sha256: str
    workspace_scope_evolved: bool = False
    evolution_document: Mapping[str, Any] | None = field(default=None, repr=False)


def _read_receipt_records(
    root: Path, key: bytes | bytearray | None
) -> list[_ReceiptRecord]:
    receipts_root = _archive_path(root, RECEIPTS_RELATIVE)
    _ensure_safe_parent_chain(root, receipts_root)
    try:
        info = os.lstat(receipts_root)
    except FileNotFoundError:
        return []
    except OSError:
        raise _fail("credential_registry_receipt_directory_unavailable") from None
    if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
        raise _fail("credential_registry_receipt_directory_unsafe")
    try:
        entries = sorted(os.scandir(receipts_root), key=lambda entry: entry.name)
    except OSError:
        raise _fail("credential_registry_receipt_directory_unavailable") from None
    receipt_entries: list[os.DirEntry[str]] = []
    for entry in entries:
        if entry.name.endswith(".json"):
            receipt_entries.append(entry)
            continue
        if _RECEIPT_TEMP_RE.fullmatch(entry.name) is not None:
            try:
                info = entry.stat(follow_symlinks=False)
            except OSError:
                raise _fail("credential_registry_receipt_entry_invalid") from None
            if _is_reparse(info) or not stat.S_ISREG(info.st_mode):
                raise _fail("credential_registry_receipt_entry_invalid")
            # _AtomicJsonReceiptCommitter may leave this exact, non-authority
            # temporary after its durable hard-link publication.  It is safe
            # to ignore under the registry lock; arbitrary names still fail.
            continue
        raise _fail("credential_registry_receipt_entry_invalid")
    if len(receipt_entries) > MAX_RECEIPTS:
        raise _fail("credential_registry_receipt_count_exceeded")
    records: list[_ReceiptRecord] = []
    seen: set[str] = set()
    for entry in receipt_entries:
        stem = entry.name[:-5]
        if _CREDENTIAL_ID_RE.fullmatch(stem) is None:
            raise _fail("credential_registry_receipt_entry_invalid")
        raw = _read_exact_bytes(
            Path(entry.path),
            maximum=MAX_RECEIPT_BYTES,
            missing_code="credential_registry_receipt_missing",
        )
        try:
            document = _validate_receipt_document(
                json.loads(raw.decode("utf-8")), authentication_optional=True
            )
        except (UnicodeError, json.JSONDecodeError):
            raise _fail("credential_registry_receipt_schema_invalid") from None
        if document["credential_id"] != stem or stem in seen:
            raise _fail("credential_registry_receipt_identity_mismatch")
        seen.add(stem)
        records.append(
            _ReceiptRecord(
                path=Path(entry.path),
                raw=raw,
                document=document,
                receipt_sha256="sha256:" + hashlib.sha256(raw).hexdigest(),
                authentication_status=_receipt_authentication_status(document, key),
                effective_workspace_fingerprint=document[
                    "verified_workspace_fingerprint"
                ],
                workspace_identity_basis=(
                    document["workspace_identity_basis"]
                    if document["schema_version"] == RECEIPT_SCHEMA_VERSION
                    else LEGACY_WORKSPACE_IDENTITY_BASIS
                ),
                authority_sha256="sha256:" + hashlib.sha256(raw).hexdigest(),
            )
        )
    return records


def _evolution_authentication_payload(document: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(document)
    payload.pop("authentication", None)
    return payload


def _evolution_mac(document: Mapping[str, Any], key: bytes | bytearray) -> str:
    return hmac.new(
        key,
        WORKSPACE_SCOPE_EVOLUTION_AUTHENTICATION_DOMAIN
        + _canonical_json_bytes(_evolution_authentication_payload(document)),
        hashlib.sha256,
    ).hexdigest()


def _validate_evolution_document(document: Any) -> dict[str, Any]:
    if not isinstance(document, Mapping) or set(document) != _EVOLUTION_KEYS:
        raise _fail("credential_registry_evolution_schema_invalid")
    result = dict(document)
    if result.get("schema_version") != WORKSPACE_SCOPE_EVOLUTION_SCHEMA_VERSION:
        raise _fail("credential_registry_evolution_schema_invalid")
    credential_id = result.get("credential_id")
    if not isinstance(credential_id, str) or _CREDENTIAL_ID_RE.fullmatch(credential_id) is None:
        raise _fail("credential_registry_evolution_identity_invalid")
    provider = result.get("provider")
    if not isinstance(provider, str) or _PROVIDER_RE.fullmatch(provider) is None:
        raise _fail("credential_registry_evolution_identity_invalid")
    for name in (
        "base_receipt_sha256",
        "previous_workspace_fingerprint",
        "verified_account_fingerprint",
        "evolved_workspace_fingerprint",
    ):
        value = result.get(name)
        if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
            raise _fail("credential_registry_evolution_identity_invalid")
    if result.get("previous_workspace_identity_basis") != LEGACY_WORKSPACE_IDENTITY_BASIS:
        raise _fail("credential_registry_evolution_identity_basis_invalid")
    if result.get("workspace_identity_basis") not in NOTION_WORKSPACE_IDENTITY_BASES:
        raise _fail("credential_registry_evolution_identity_basis_invalid")
    capabilities = result.get("verified_capabilities")
    if not isinstance(capabilities, list) or capabilities != sorted(set(capabilities)):
        raise _fail("credential_registry_evolution_capabilities_invalid")
    if any(
        not isinstance(capability, str) or _PURPOSE_RE.fullmatch(capability) is None
        for capability in capabilities
    ):
        raise _fail("credential_registry_evolution_capabilities_invalid")
    _validate_timestamp(result.get("evolved_at"))
    authentication = result.get("authentication")
    if not isinstance(authentication, Mapping) or set(authentication) != _AUTHENTICATION_KEYS:
        raise _fail("credential_registry_evolution_authentication_invalid")
    if (
        authentication.get("schema_version")
        != WORKSPACE_SCOPE_EVOLUTION_AUTHENTICATION_SCHEMA
        or authentication.get("algorithm") != "hmac-sha256"
        or not isinstance(authentication.get("mac"), str)
        or _HEX_SHA256_RE.fullmatch(authentication["mac"]) is None
    ):
        raise _fail("credential_registry_evolution_authentication_invalid")
    return result


def _read_evolution_documents(
    root: Path,
) -> list[tuple[Path, bytes, dict[str, Any]]]:
    evolutions_root = _archive_path(root, EVOLUTIONS_RELATIVE)
    _ensure_safe_parent_chain(
        root,
        evolutions_root,
        leaf_reparse_code="credential_registry_evolution_directory_unsafe",
    )
    try:
        info = os.lstat(evolutions_root)
    except FileNotFoundError:
        return []
    except OSError:
        raise _fail("credential_registry_evolution_directory_unavailable") from None
    if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
        raise _fail("credential_registry_evolution_directory_unsafe")
    try:
        entries = sorted(os.scandir(evolutions_root), key=lambda entry: entry.name)
    except OSError:
        raise _fail("credential_registry_evolution_directory_unavailable") from None
    authority_entries: list[os.DirEntry[str]] = []
    for entry in entries:
        if _EVOLUTION_FILE_RE.fullmatch(entry.name) is not None:
            authority_entries.append(entry)
            continue
        if _EVOLUTION_TEMP_RE.fullmatch(entry.name) is not None:
            try:
                temp_info = entry.stat(follow_symlinks=False)
            except OSError:
                raise _fail("credential_registry_evolution_entry_invalid") from None
            if _is_reparse(temp_info) or not stat.S_ISREG(temp_info.st_mode):
                raise _fail("credential_registry_evolution_entry_invalid")
            continue
        raise _fail("credential_registry_evolution_entry_invalid")
    if len(authority_entries) > MAX_EVOLUTIONS:
        raise _fail("credential_registry_evolution_count_exceeded")
    result: list[tuple[Path, bytes, dict[str, Any]]] = []
    seen: set[str] = set()
    for entry in authority_entries:
        match = _EVOLUTION_FILE_RE.fullmatch(entry.name)
        if match is None or match.group(1) in seen:
            raise _fail("credential_registry_evolution_duplicate")
        seen.add(match.group(1))
        raw = _read_exact_bytes(
            Path(entry.path),
            maximum=MAX_EVOLUTION_BYTES,
            missing_code="credential_registry_evolution_missing",
        )
        try:
            document = _validate_evolution_document(json.loads(raw.decode("utf-8")))
        except (UnicodeError, json.JSONDecodeError):
            raise _fail("credential_registry_evolution_schema_invalid") from None
        if document["credential_id"] != match.group(1):
            raise _fail("credential_registry_evolution_identity_invalid")
        result.append((Path(entry.path), raw, document))
    return result


def _apply_workspace_scope_evolutions(
    root: Path,
    records: Sequence[_ReceiptRecord],
    key: bytes | bytearray | None,
) -> list[_ReceiptRecord]:
    by_id = {record.document["credential_id"]: record for record in records}
    evolved: dict[str, _ReceiptRecord] = dict(by_id)
    for _path, raw, document in _read_evolution_documents(root):
        credential_id = document["credential_id"]
        record = by_id.get(credential_id)
        if record is None:
            raise _fail("credential_registry_evolution_orphaned")
        if record.document["schema_version"] != LEGACY_RECEIPT_SCHEMA_VERSION:
            raise _fail("credential_registry_evolution_conflict")
        if not (
            document["provider"] == record.document["provider"]
            and document["base_receipt_sha256"] == record.receipt_sha256
            and document["previous_workspace_fingerprint"]
            == record.document["verified_workspace_fingerprint"]
            and document["verified_account_fingerprint"]
            == record.document["verified_account_fingerprint"]
            and document["verified_capabilities"]
            == record.document["verified_capabilities"]
        ):
            raise _fail("credential_registry_evolution_conflict")
        if (
            document["workspace_identity_basis"]
            == NOTION_PAT_WORKSPACE_IDENTITY_BASIS
            and not hmac.compare_digest(
                document["evolved_workspace_fingerprint"],
                _notion_pat_scope_fingerprint(
                    record.document["fingerprint_digest"]
                ),
            )
        ):
            raise _fail("credential_registry_evolution_conflict")
        authentication = document["authentication"]
        if key is None:
            authentication_status = "not_checked"
        else:
            authentication_status = (
                "valid"
                if hmac.compare_digest(
                    str(authentication["mac"]), _evolution_mac(document, key)
                )
                else "invalid"
            )
        authority_sha256 = "sha256:" + hashlib.sha256(raw).hexdigest()
        evolved[credential_id] = replace(
            record,
            authentication_status=(
                "valid"
                if record.authentication_status == "valid"
                and authentication_status == "valid"
                else (
                    "not_checked"
                    if record.authentication_status == "not_checked"
                    and authentication_status == "not_checked"
                    else "invalid"
                )
            ),
            effective_workspace_fingerprint=document[
                "evolved_workspace_fingerprint"
            ],
            workspace_identity_basis=document["workspace_identity_basis"],
            authority_sha256=authority_sha256,
            workspace_scope_evolved=True,
            evolution_document=document,
        )
    return [evolved[record.document["credential_id"]] for record in records]


def _read_effective_receipt_records(
    root: Path, key: bytes | bytearray | None
) -> list[_ReceiptRecord]:
    return _apply_workspace_scope_evolutions(
        root,
        _read_receipt_records(root, key),
        key,
    )


def _lifecycle_mac(document: Mapping[str, Any], key: bytes | bytearray) -> str:
    payload = dict(document)
    payload.pop("authentication", None)
    return hmac.new(
        key,
        LIFECYCLE_AUTHENTICATION_DOMAIN + _canonical_json_bytes(payload),
        hashlib.sha256,
    ).hexdigest()


def _validate_lifecycle_document(document: Any, *, archive_id: str) -> dict[str, Any]:
    if not isinstance(document, Mapping) or set(document) != _LIFECYCLE_KEYS:
        raise _fail("credential_registry_lifecycle_schema_invalid")
    result = dict(document)
    if result.get("schema_version") != LIFECYCLE_SCHEMA_VERSION or result.get("archive_id") != archive_id:
        raise _fail("credential_registry_lifecycle_schema_invalid")
    authentication = result.get("authentication")
    if not isinstance(authentication, Mapping) or set(authentication) != _AUTHENTICATION_KEYS:
        raise _fail("credential_registry_lifecycle_authentication_invalid")
    if (
        authentication.get("schema_version") != LIFECYCLE_AUTHENTICATION_SCHEMA
        or authentication.get("algorithm") != "hmac-sha256"
        or not isinstance(authentication.get("mac"), str)
        or _HEX_SHA256_RE.fullmatch(authentication["mac"]) is None
    ):
        raise _fail("credential_registry_lifecycle_authentication_invalid")
    scopes = result.get("scopes")
    if not isinstance(scopes, list):
        raise _fail("credential_registry_lifecycle_schema_invalid")
    identities: set[tuple[str, str]] = set()
    previous_identity: tuple[str, str] | None = None
    for scope in scopes:
        if not isinstance(scope, Mapping) or set(scope) != _LIFECYCLE_SCOPE_KEYS:
            raise _fail("credential_registry_lifecycle_schema_invalid")
        provider = scope.get("provider")
        workspace = scope.get("workspace_fingerprint")
        revision = scope.get("revision")
        plan_sha256 = scope.get("plan_sha256")
        reviewed_by = scope.get("reviewed_by")
        if not isinstance(provider, str) or _PROVIDER_RE.fullmatch(provider) is None:
            raise _fail("credential_registry_lifecycle_scope_invalid")
        if not isinstance(workspace, str) or _SHA256_RE.fullmatch(workspace) is None:
            raise _fail("credential_registry_lifecycle_scope_invalid")
        if not isinstance(revision, str) or _SAFE_REVISION_RE.fullmatch(revision) is None:
            raise _fail("credential_registry_lifecycle_scope_invalid")
        if not isinstance(plan_sha256, str) or _SHA256_RE.fullmatch(plan_sha256) is None:
            raise _fail("credential_registry_lifecycle_scope_invalid")
        if (
            not isinstance(reviewed_by, str)
            or _SAFE_REVIEWER_RE.fullmatch(reviewed_by) is None
            or _SECRET_SHAPE_RE.search(reviewed_by)
        ):
            raise _fail("credential_registry_lifecycle_scope_invalid")
        identity = (provider, workspace)
        if identity in identities or (previous_identity is not None and identity < previous_identity):
            raise _fail("credential_registry_lifecycle_scope_invalid")
        identities.add(identity)
        previous_identity = identity
        credentials = scope.get("credentials")
        if not isinstance(credentials, list) or not credentials:
            raise _fail("credential_registry_lifecycle_credentials_invalid")
        defaults = 0
        credential_ids: list[str] = []
        for row in credentials:
            if not isinstance(row, Mapping) or set(row) != _LIFECYCLE_CREDENTIAL_KEYS:
                raise _fail("credential_registry_lifecycle_credentials_invalid")
            credential_id = row.get("credential_id")
            if not isinstance(credential_id, str) or _CREDENTIAL_ID_RE.fullmatch(credential_id) is None:
                raise _fail("credential_registry_lifecycle_credentials_invalid")
            credential_ids.append(credential_id)
            status = row.get("lifecycle_status")
            rotation = row.get("rotation_status")
            is_default = row.get("is_default")
            if status not in {"active", "legacy_valid", "revocation_pending"}:
                raise _fail("credential_registry_lifecycle_credentials_invalid")
            if rotation not in {"current", "legacy", "review_pending"} or not isinstance(is_default, bool):
                raise _fail("credential_registry_lifecycle_credentials_invalid")
            if is_default:
                defaults += 1
                if status != "active" or rotation != "current":
                    raise _fail("credential_registry_lifecycle_default_invalid")
            elif status == "active" or rotation == "current":
                raise _fail("credential_registry_lifecycle_credentials_invalid")
        if credential_ids != sorted(set(credential_ids)) or defaults != 1:
            raise _fail("credential_registry_lifecycle_default_invalid")
    return result


def _read_lifecycle(
    root: Path,
    archive_id: str,
    key: bytes | bytearray | None,
) -> tuple[dict[str, Any] | None, str]:
    path = _archive_path(root, LIFECYCLE_RELATIVE)
    _ensure_safe_parent_chain(root, path)
    try:
        raw = _read_exact_bytes(
            path,
            maximum=MAX_LIFECYCLE_BYTES,
            missing_code="credential_registry_lifecycle_missing",
        )
    except SecureCredentialRegistryError as exc:
        if exc.code == "credential_registry_lifecycle_missing":
            return None, "missing"
        raise
    try:
        document = _validate_lifecycle_document(json.loads(raw.decode("utf-8")), archive_id=archive_id)
    except (UnicodeError, json.JSONDecodeError):
        raise _fail("credential_registry_lifecycle_schema_invalid") from None
    if key is None:
        return document, "not_checked"
    actual = str(document["authentication"]["mac"])
    expected = _lifecycle_mac(document, key)
    return document, "valid" if hmac.compare_digest(actual, expected) else "invalid"


def _lifecycle_index(document: Mapping[str, Any] | None) -> dict[str, tuple[Mapping[str, Any], Mapping[str, Any]]]:
    index: dict[str, tuple[Mapping[str, Any], Mapping[str, Any]]] = {}
    if document is None:
        return index
    for scope in document["scopes"]:
        for row in scope["credentials"]:
            if row["credential_id"] in index:
                raise _fail("credential_registry_lifecycle_credential_duplicate")
            index[row["credential_id"]] = (scope, row)
    return index


def _public_receipt(
    record: _ReceiptRecord,
    lifecycle: tuple[Mapping[str, Any], Mapping[str, Any]] | None,
    lifecycle_authentication_status: str,
    lifecycle_scope_complete: bool,
) -> dict[str, Any]:
    document = record.document
    if record.authentication_status != "valid":
        # Even syntactically safe labels and provider values are untrusted until
        # the exact canonical receipt has a valid MAC.  In particular, do not
        # let a tampered local file turn a token-shaped string into AI-visible
        # output.  The filename-bound id is checked against the document id by
        # the reader and is the only identity projected here.
        return {
            "credential_id": document["credential_id"],
            "receipt_authentication_status": record.authentication_status,
            "lifecycle_authentication_status": lifecycle_authentication_status,
            "broker_authoritative": False,
            "scope_binding": None,
        }
    scope, state = lifecycle if lifecycle is not None else (None, None)
    lifecycle_status = state["lifecycle_status"] if state is not None else document["lifecycle_status"]
    rotation_status = state["rotation_status"] if state is not None else document["rotation_status"]
    is_default = state["is_default"] if state is not None else document["is_default"]
    workspace_fingerprint = record.effective_workspace_fingerprint
    authority_sha256 = record.authority_sha256
    revision = (
        scope["revision"]
        if scope is not None
        else "receipt-" + authority_sha256.removeprefix("sha256:")
    )
    lifecycle_scope_matches = bool(
        scope is not None
        and scope["provider"] == document["provider"]
        and scope["workspace_fingerprint"] == workspace_fingerprint
    )
    workspace_scope_transition_pending = bool(
        record.workspace_scope_evolved
        and lifecycle_authentication_status == "valid"
        and scope is not None
        and scope["provider"] == document["provider"]
        and scope["workspace_fingerprint"] != workspace_fingerprint
    )
    authenticated = record.authentication_status == "valid"
    lifecycle_authenticated = lifecycle_authentication_status == "valid"
    broker_authoritative = bool(
        authenticated
        and lifecycle_authenticated
        and lifecycle_scope_matches
        and lifecycle_scope_complete
        and lifecycle_status == "active"
        and rotation_status == "current"
        and is_default is True
    )
    return {
        "credential_id": document["credential_id"],
        "provider": document["provider"],
        "account_label": document["account_label"],
        "workspace_label": document["workspace_label"],
        "purpose": document["purpose"],
        "verified_capabilities": list(document["verified_capabilities"]),
        "credential_fingerprint": document["fingerprint_digest"],
        "verified_account_fingerprint": document["verified_account_fingerprint"],
        "lifecycle_status": lifecycle_status,
        "rotation_status": rotation_status,
        "is_default": is_default,
        "verified_workspace_fingerprint": workspace_fingerprint,
        "workspace_identity_basis": record.workspace_identity_basis,
        "workspace_scope_evolved": record.workspace_scope_evolved,
        "workspace_scope_transition_pending": workspace_scope_transition_pending,
        "receipt_sha256": authority_sha256,
        "receipt_authentication_status": record.authentication_status,
        "lifecycle_authentication_status": lifecycle_authentication_status,
        "broker_authoritative": broker_authoritative,
        "scope_binding": {
            "credential_id": document["credential_id"],
            "workspace_fingerprint": workspace_fingerprint,
            "scope_receipt_sha256": authority_sha256,
            "revision": revision,
            # In a recovery manifest, ``persisted`` is an authority bit rather
            # than a restatement of the intake receipt.  A newly intaken secret
            # is rediscoverable, but not executable until a human records the
            # one active/current/default lifecycle choice.
            "persisted": broker_authoritative,
            "workspace_evidence_verified": authenticated,
        },
    }


def list_secure_credentials(
    archive_root: Path | str,
    *,
    receipt_authentication_key: bytes | bytearray | memoryview | None = None,
) -> dict[str, Any]:
    """Return a content-free rediscovery projection from the fixed local path."""

    root, archive_id = _validate_archive(archive_root)
    key = (
        None
        if receipt_authentication_key is None
        else _validate_authentication_key(receipt_authentication_key)
    )
    with _archive_lock(root, create_if_missing=False):
        records = _read_effective_receipt_records(root, key)
        lifecycle_document, lifecycle_status = _read_lifecycle(root, archive_id, key)
    # An unauthenticated lifecycle file may not override even presentation
    # state.  Valid receipt metadata remains visible, but lifecycle/default
    # values fall back to the authenticated intake receipt until the lifecycle
    # MAC is checked successfully.
    lifecycle = (
        _lifecycle_index(lifecycle_document)
        if lifecycle_status == "valid"
        else {}
    )
    lifecycle_completeness: dict[str, bool] = {}
    if lifecycle_status == "valid" and lifecycle_document is not None:
        all_receipts_authenticated = all(
            record.authentication_status == "valid" for record in records
        )
        for scope in lifecycle_document["scopes"]:
            lifecycle_ids = {
                row["credential_id"] for row in scope["credentials"]
            }
            receipt_ids = {
                record.document["credential_id"]
                for record in records
                if record.authentication_status == "valid"
                and record.document["provider"] == scope["provider"]
                and record.effective_workspace_fingerprint
                == scope["workspace_fingerprint"]
            }
            complete = all_receipts_authenticated and lifecycle_ids == receipt_ids
            for credential_id in lifecycle_ids:
                lifecycle_completeness[credential_id] = complete
    rows = [
        _public_receipt(
            record,
            lifecycle.get(record.document["credential_id"]),
            lifecycle_status,
            lifecycle_completeness.get(record.document["credential_id"], False),
        )
        for record in records
    ]
    return {
        "schema_version": REGISTRY_RESULT_SCHEMA_VERSION,
        "ok": True,
        "archive_id": archive_id,
        "credential_count": len(rows),
        "credentials": rows,
        "secret_value_present": False,
        "backend_id_present": False,
        "native_enumeration_performed": False,
        "provider_call_performed": False,
        "write_performed": False,
    }


@dataclass(frozen=True, repr=False)
class AuthenticatedCredentialReuseEvidence:
    """Receipt-authenticated, non-secret scope evidence for one reuse check."""

    provider: str
    verified_account_fingerprint: str
    verified_workspace_fingerprint: str
    workspace_identity_basis: str
    credential_fingerprint: str = field(repr=False)
    verified_capabilities: tuple[str, ...]


@dataclass(frozen=True, repr=False)
class _AuthenticatedCredentialReuseAuthority:
    target: str = field(repr=False)
    receipt_sha256: str
    expected_secret_fingerprint: str = field(repr=False)
    evidence: AuthenticatedCredentialReuseEvidence


def _authenticated_credential_reuse_authority(
    archive_root: Path | str,
    credential_id: str,
    *,
    receipt_authentication_key: bytes | bytearray | memoryview,
) -> _AuthenticatedCredentialReuseAuthority:
    if not isinstance(credential_id, str) or _CREDENTIAL_ID_RE.fullmatch(
        credential_id
    ) is None:
        raise _fail("credential_registry_credential_id_invalid")
    root, archive_id = _validate_archive(archive_root)
    key = _validate_authentication_key(receipt_authentication_key)
    with _archive_lock(root, create_if_missing=False):
        records = _read_effective_receipt_records(root, key)
        if any(record.authentication_status != "valid" for record in records):
            raise _fail("credential_registry_receipt_set_untrusted")
        matching = [
            record
            for record in records
            if record.document["credential_id"] == credential_id
        ]
        if len(matching) != 1:
            raise _fail("credential_registry_credential_not_found")
        document = matching[0].document
        if document["encrypted_backend_kind"] != "windows_credential_manager_generic":
            raise _fail("credential_registry_backend_not_supported")
        backend_id = document["encrypted_backend_id"]
        if _BACKEND_ID_RE.fullmatch(backend_id) is None:
            raise _fail("credential_registry_receipt_backend_invalid")
        return _AuthenticatedCredentialReuseAuthority(
            target=windows_credential_target(archive_id, backend_id),
            receipt_sha256=matching[0].authority_sha256,
            expected_secret_fingerprint=document["fingerprint_digest"],
            evidence=AuthenticatedCredentialReuseEvidence(
                provider=document["provider"],
                verified_account_fingerprint=document[
                    "verified_account_fingerprint"
                ],
                verified_workspace_fingerprint=matching[
                    0
                ].effective_workspace_fingerprint,
                workspace_identity_basis=matching[0].workspace_identity_basis,
                credential_fingerprint=document["fingerprint_digest"],
                verified_capabilities=tuple(document["verified_capabilities"]),
            ),
        )


def _use_authenticated_secure_credential_for_revalidation(
    archive_root: Path | str,
    credential_id: str,
    *,
    receipt_authentication_key: bytes | bytearray | memoryview,
    secret_fingerprint_key: bytes | bytearray | memoryview,
    native: ExactWindowsCredentialNative,
    consumer: Callable[[memoryview, AuthenticatedCredentialReuseEvidence], _T],
) -> _T:
    """Revalidate one saved secret without exporting it from the worker.

    The authenticated receipt selects exactly one backend target.  The secret
    is read into a mutable buffer, HMAC-compared with the receipt, passed only
    to the trusted in-process callback, and wiped.  Receipt and store authority
    are then observed a second time so a successful reuse result cannot be
    based on a record or credential that changed during provider verification.
    """

    fingerprint_key = _validate_authentication_key(secret_fingerprint_key)
    before = _authenticated_credential_reuse_authority(
        archive_root,
        credential_id,
        receipt_authentication_key=receipt_authentication_key,
    )

    def read_and_verify(authority: _AuthenticatedCredentialReuseAuthority) -> bytearray:
        try:
            present = native.generic_exists(authority.target)
        except Exception:
            raise _fail("credential_registry_store_probe_failed") from None
        if not present:
            raise _fail("credential_registry_store_missing")
        try:
            secret_buffer = native.read_generic_secret_exact(authority.target)
        except Exception:
            raise _fail("credential_registry_secret_read_failed") from None
        if not isinstance(secret_buffer, bytearray) or not secret_buffer:
            if isinstance(secret_buffer, bytearray):
                for index in range(len(secret_buffer)):
                    secret_buffer[index] = 0
            raise _fail("credential_registry_secret_read_failed")
        actual_fingerprint = "hmac-sha256:" + hmac.new(
            fingerprint_key,
            secret_buffer,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(
            actual_fingerprint,
            authority.expected_secret_fingerprint,
        ):
            for index in range(len(secret_buffer)):
                secret_buffer[index] = 0
            raise _fail("credential_registry_secret_fingerprint_mismatch")
        return secret_buffer

    secret_buffer: bytearray | None = None
    secret_view: memoryview | None = None
    try:
        secret_buffer = read_and_verify(before)
        secret_view = memoryview(secret_buffer)
        result = consumer(secret_view, before.evidence)
    finally:
        if secret_view is not None:
            secret_view.release()
        if secret_buffer is not None:
            for index in range(len(secret_buffer)):
                secret_buffer[index] = 0

    after = _authenticated_credential_reuse_authority(
        archive_root,
        credential_id,
        receipt_authentication_key=receipt_authentication_key,
    )
    if not (
        hmac.compare_digest(before.target, after.target)
        and hmac.compare_digest(before.receipt_sha256, after.receipt_sha256)
        and hmac.compare_digest(
            before.expected_secret_fingerprint,
            after.expected_secret_fingerprint,
        )
        and before.evidence == after.evidence
    ):
        raise _fail("credential_registry_reuse_authority_changed")

    final_buffer: bytearray | None = None
    try:
        final_buffer = read_and_verify(after)
    finally:
        if final_buffer is not None:
            for index in range(len(final_buffer)):
                final_buffer[index] = 0
    return result


def _verify_exact_saved_secret(
    authority: _AuthenticatedCredentialReuseAuthority,
    *,
    native: ExactWindowsCredentialNative,
    fingerprint_key: bytes | bytearray,
) -> None:
    secret_buffer: bytearray | None = None
    try:
        try:
            if not native.generic_exists(authority.target):
                raise _fail("credential_registry_store_missing")
        except SecureCredentialRegistryError:
            raise
        except Exception:
            raise _fail("credential_registry_store_probe_failed") from None
        try:
            secret_buffer = native.read_generic_secret_exact(authority.target)
        except Exception:
            raise _fail("credential_registry_secret_read_failed") from None
        if not isinstance(secret_buffer, bytearray) or not secret_buffer:
            raise _fail("credential_registry_secret_read_failed")
        actual = "hmac-sha256:" + hmac.new(
            fingerprint_key, secret_buffer, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(actual, authority.expected_secret_fingerprint):
            raise _fail("credential_registry_secret_fingerprint_mismatch")
    finally:
        if secret_buffer is not None:
            for index in range(len(secret_buffer)):
                secret_buffer[index] = 0


def _singleton_lifecycle_transition(
    existing: Mapping[str, Any] | None,
    *,
    provider: str,
    credential_id: str,
    previous_workspace_fingerprint: str,
    evolved_workspace_fingerprint: str,
    evolution_authority_sha256: str,
) -> dict[str, Any] | None:
    """Return a safe singleton transition, None for no lifecycle, or fail."""

    if existing is None:
        return None
    occurrences: list[tuple[int, Mapping[str, Any], Mapping[str, Any]]] = []
    for index, scope in enumerate(existing["scopes"]):
        for state in scope["credentials"]:
            if state["credential_id"] == credential_id:
                occurrences.append((index, scope, state))
    if len(occurrences) != 1:
        raise _fail("credential_registry_evolution_lifecycle_review_required")
    index, scope, _state = occurrences[0]
    if (
        scope["provider"] == provider
        and scope["workspace_fingerprint"] == evolved_workspace_fingerprint
        and len(scope["credentials"]) == 1
    ):
        replay = dict(existing)
        replay.pop("authentication", None)
        return replay
    if not (
        scope["provider"] == provider
        and scope["workspace_fingerprint"] == previous_workspace_fingerprint
        and len(scope["credentials"]) == 1
    ):
        raise _fail("credential_registry_evolution_lifecycle_review_required")
    if any(
        candidate["provider"] == provider
        and candidate["workspace_fingerprint"] == evolved_workspace_fingerprint
        and candidate is not scope
        for candidate in existing["scopes"]
    ):
        raise _fail("credential_registry_evolution_lifecycle_review_required")
    transition_seed = {
        "credential_id": credential_id,
        "previous_workspace_fingerprint": previous_workspace_fingerprint,
        "evolved_workspace_fingerprint": evolved_workspace_fingerprint,
        "evolution_authority_sha256": evolution_authority_sha256,
        "preserved_credentials": scope["credentials"],
    }
    transition_sha256 = "sha256:" + hashlib.sha256(
        _canonical_json_bytes(transition_seed)
    ).hexdigest()
    transitioned_scope = dict(scope)
    transitioned_scope.update(
        {
            "workspace_fingerprint": evolved_workspace_fingerprint,
            "revision": "scope-evolution-"
            + transition_sha256.removeprefix("sha256:"),
            "plan_sha256": transition_sha256,
        }
    )
    scopes = [dict(candidate) for candidate in existing["scopes"]]
    scopes[index] = transitioned_scope
    scopes.sort(key=lambda candidate: (candidate["provider"], candidate["workspace_fingerprint"]))
    return {
        "schema_version": LIFECYCLE_SCHEMA_VERSION,
        "archive_id": existing["archive_id"],
        "scopes": scopes,
    }


def _evolve_legacy_authenticated_workspace_scope(
    archive_root: Path | str,
    credential_id: str,
    *,
    evolved_workspace_fingerprint: str,
    workspace_identity_basis: str,
    verified_account_fingerprint: str,
    verified_capabilities: Sequence[str],
    receipt_authentication_key: bytes | bytearray | memoryview,
    secret_fingerprint_key: bytes | bytearray | memoryview,
    native: ExactWindowsCredentialNative,
    evolved_at: str | None = None,
    after_evolution_commit: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Evolve one released v0.1 anchor scope without changing its saved PAT.

    Provider verification occurs immediately before this call.  This commit
    gate independently authenticates the base receipt, exact saved-secret HMAC,
    and any existing evolution/lifecycle.  It never writes or deletes a native
    credential.  A complex lifecycle fails before first publication.
    """

    if not isinstance(credential_id, str) or _CREDENTIAL_ID_RE.fullmatch(credential_id) is None:
        raise _fail("credential_registry_credential_id_invalid")
    if not isinstance(evolved_workspace_fingerprint, str) or _SHA256_RE.fullmatch(
        evolved_workspace_fingerprint
    ) is None:
        raise _fail("credential_registry_evolution_identity_invalid")
    if workspace_identity_basis not in NOTION_WORKSPACE_IDENTITY_BASES:
        raise _fail("credential_registry_evolution_identity_basis_invalid")
    if not isinstance(verified_account_fingerprint, str) or _SHA256_RE.fullmatch(
        verified_account_fingerprint
    ) is None:
        raise _fail("credential_registry_evolution_identity_invalid")
    capabilities = list(verified_capabilities)
    if capabilities != sorted(set(capabilities)) or any(
        not isinstance(capability, str) or _PURPOSE_RE.fullmatch(capability) is None
        for capability in capabilities
    ):
        raise _fail("credential_registry_evolution_capabilities_invalid")
    key = _validate_authentication_key(receipt_authentication_key)
    fingerprint_key = _validate_authentication_key(secret_fingerprint_key)
    root, archive_id = _validate_archive(archive_root)
    timestamp = evolved_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    _validate_timestamp(timestamp)

    with _archive_lock(root):
        base_records = _read_receipt_records(root, key)
        if any(record.authentication_status != "valid" for record in base_records):
            raise _fail("credential_registry_receipt_set_untrusted")
        matching = [
            record
            for record in base_records
            if record.document["credential_id"] == credential_id
        ]
        if len(matching) != 1:
            raise _fail("credential_registry_credential_not_found")
        base = matching[0]
        document = base.document
        if document["schema_version"] != LEGACY_RECEIPT_SCHEMA_VERSION:
            raise _fail("credential_registry_evolution_not_legacy")
        if (
            workspace_identity_basis == NOTION_PAT_WORKSPACE_IDENTITY_BASIS
            and not hmac.compare_digest(
                evolved_workspace_fingerprint,
                _notion_pat_scope_fingerprint(document["fingerprint_digest"]),
            )
        ):
            raise _fail("credential_registry_evolution_identity_mismatch")
        if not (
            document["provider"] == "notion"
            and document["verified_account_fingerprint"]
            == verified_account_fingerprint
            and document["verified_capabilities"] == capabilities
        ):
            raise _fail("credential_registry_evolution_identity_mismatch")
        if document["encrypted_backend_kind"] != "windows_credential_manager_generic":
            raise _fail("credential_registry_backend_not_supported")
        authority = _AuthenticatedCredentialReuseAuthority(
            target=windows_credential_target(
                archive_id, document["encrypted_backend_id"]
            ),
            receipt_sha256=base.receipt_sha256,
            expected_secret_fingerprint=document["fingerprint_digest"],
            evidence=AuthenticatedCredentialReuseEvidence(
                provider=document["provider"],
                verified_account_fingerprint=document[
                    "verified_account_fingerprint"
                ],
                verified_workspace_fingerprint=document[
                    "verified_workspace_fingerprint"
                ],
                workspace_identity_basis=LEGACY_WORKSPACE_IDENTITY_BASIS,
                credential_fingerprint=document["fingerprint_digest"],
                verified_capabilities=tuple(capabilities),
            ),
        )
        existing_lifecycle, lifecycle_status = _read_lifecycle(
            root, archive_id, key
        )
        if existing_lifecycle is not None and lifecycle_status != "valid":
            raise _fail("credential_registry_lifecycle_authentication_invalid")

        existing_evolutions = _read_evolution_documents(root)
        effective_before = _apply_workspace_scope_evolutions(
            root, base_records, key
        )
        if any(
            record.authentication_status != "valid"
            for record in effective_before
        ):
            raise _fail("credential_registry_evolution_authentication_invalid")
        matching_evolution = [
            (raw, evolution)
            for _path, raw, evolution in existing_evolutions
            if evolution["credential_id"] == credential_id
        ]
        if len(matching_evolution) > 1:
            raise _fail("credential_registry_evolution_duplicate")
        if any(
            record.document["credential_id"] != credential_id
            and record.document["provider"] == "notion"
            and record.effective_workspace_fingerprint
            == evolved_workspace_fingerprint
            for record in effective_before
        ):
            # Collapsing two independently authenticated registrations into
            # one authority scope is a human lifecycle decision, never an
            # automatic migration side effect.
            raise _fail("credential_registry_evolution_lifecycle_review_required")

        if matching_evolution:
            evolution_raw, evolution = matching_evolution[0]
            validated = _apply_workspace_scope_evolutions(root, base_records, key)
            effective = next(
                record
                for record in validated
                if record.document["credential_id"] == credential_id
            )
            if not (
                effective.authentication_status == "valid"
                and effective.effective_workspace_fingerprint
                == evolved_workspace_fingerprint
                and evolution["verified_account_fingerprint"]
                == verified_account_fingerprint
                and evolution["verified_capabilities"] == capabilities
                and evolution["workspace_identity_basis"]
                == workspace_identity_basis
            ):
                raise _fail("credential_registry_evolution_conflict")
            _verify_exact_saved_secret(
                authority, native=native, fingerprint_key=fingerprint_key
            )
            evolution_authority_sha256 = "sha256:" + hashlib.sha256(
                evolution_raw
            ).hexdigest()
            created = False
        else:
            # Decide whether lifecycle topology is migratable before publishing
            # the append-only authority.  No-lifecycle remains non-authoritative.
            prospective_authority = "sha256:" + ("0" * 64)
            _singleton_lifecycle_transition(
                existing_lifecycle,
                provider="notion",
                credential_id=credential_id,
                previous_workspace_fingerprint=document[
                    "verified_workspace_fingerprint"
                ],
                evolved_workspace_fingerprint=evolved_workspace_fingerprint,
                evolution_authority_sha256=prospective_authority,
            )
            _verify_exact_saved_secret(
                authority, native=native, fingerprint_key=fingerprint_key
            )
            evolution = {
                "schema_version": WORKSPACE_SCOPE_EVOLUTION_SCHEMA_VERSION,
                "credential_id": credential_id,
                "provider": "notion",
                "base_receipt_sha256": base.receipt_sha256,
                "previous_workspace_fingerprint": document[
                    "verified_workspace_fingerprint"
                ],
                "previous_workspace_identity_basis": LEGACY_WORKSPACE_IDENTITY_BASIS,
                "verified_account_fingerprint": verified_account_fingerprint,
                "verified_capabilities": capabilities,
                "evolved_workspace_fingerprint": evolved_workspace_fingerprint,
                "workspace_identity_basis": workspace_identity_basis,
                "evolved_at": timestamp,
            }
            evolution["authentication"] = {
                "schema_version": WORKSPACE_SCOPE_EVOLUTION_AUTHENTICATION_SCHEMA,
                "algorithm": "hmac-sha256",
                "mac": _evolution_mac(evolution, key),
            }
            _validate_evolution_document(evolution)
            evolution_path = _archive_path(root, EVOLUTIONS_RELATIVE) / (
                credential_id + ".workspace-scope-v1.json"
            )
            evolution_raw, created = _atomic_create_json(
                root, evolution_path, evolution
            )
            evolution_authority_sha256 = "sha256:" + hashlib.sha256(
                evolution_raw
            ).hexdigest()

        transitioned = _singleton_lifecycle_transition(
            existing_lifecycle,
            provider="notion",
            credential_id=credential_id,
            previous_workspace_fingerprint=document[
                "verified_workspace_fingerprint"
            ],
            evolved_workspace_fingerprint=evolved_workspace_fingerprint,
            evolution_authority_sha256=evolution_authority_sha256,
        )
        if created and after_evolution_commit is not None:
            after_evolution_commit()
        lifecycle_migrated = False
        if transitioned is not None:
            transitioned["authentication"] = {
                "schema_version": LIFECYCLE_AUTHENTICATION_SCHEMA,
                "algorithm": "hmac-sha256",
                "mac": _lifecycle_mac(transitioned, key),
            }
            _validate_lifecycle_document(transitioned, archive_id=archive_id)
            lifecycle_path = _archive_path(root, LIFECYCLE_RELATIVE)
            _atomic_replace_json(lifecycle_path, transitioned)
            lifecycle_migrated = True

        # Final interpretation must authenticate the newly effective authority.
        final_records = _read_effective_receipt_records(root, key)
        final = next(
            record
            for record in final_records
            if record.document["credential_id"] == credential_id
        )
        if not (
            final.authentication_status == "valid"
            and final.authority_sha256 == evolution_authority_sha256
            and final.effective_workspace_fingerprint
            == evolved_workspace_fingerprint
        ):
            raise _fail("credential_registry_evolution_verification_failed")
        _verify_exact_saved_secret(
            authority, native=native, fingerprint_key=fingerprint_key
        )
        final_lifecycle, final_lifecycle_status = _read_lifecycle(
            root, archive_id, key
        )
        broker_authoritative = False
        if final_lifecycle_status == "valid" and final_lifecycle is not None:
            final_lifecycle_index = _lifecycle_index(final_lifecycle)
            final_lifecycle_entry = final_lifecycle_index.get(credential_id)
            if final_lifecycle_entry is not None:
                final_scope, final_state = final_lifecycle_entry
                lifecycle_ids = {
                    row["credential_id"]
                    for row in final_scope["credentials"]
                }
                receipt_ids = {
                    record.document["credential_id"]
                    for record in final_records
                    if record.authentication_status == "valid"
                    and record.document["provider"] == final_scope["provider"]
                    and record.effective_workspace_fingerprint
                    == final_scope["workspace_fingerprint"]
                }
                broker_authoritative = bool(
                    all(
                        record.authentication_status == "valid"
                        for record in final_records
                    )
                    and final_scope["provider"] == "notion"
                    and final_scope["workspace_fingerprint"]
                    == evolved_workspace_fingerprint
                    and lifecycle_ids == receipt_ids
                    and final_state["lifecycle_status"] == "active"
                    and final_state["rotation_status"] == "current"
                    and final_state["is_default"] is True
                )
    return {
        "schema_version": REGISTRY_RESULT_SCHEMA_VERSION,
        "ok": True,
        "status": (
            "workspace_scope_evolved"
            if created
            else "workspace_scope_evolution_replayed"
        ),
        "credential_id": credential_id,
        "verified_workspace_fingerprint": evolved_workspace_fingerprint,
        "workspace_identity_basis": workspace_identity_basis,
        "authority_sha256": evolution_authority_sha256,
        "lifecycle_migrated": lifecycle_migrated,
        "broker_authoritative": broker_authoritative,
        "credential_store_write_performed": False,
        "credential_store_delete_performed": False,
        "secret_prompt_performed": False,
    }


def lookup_secure_credential(
    archive_root: Path | str,
    credential_id: str,
    *,
    receipt_authentication_key: bytes | bytearray | memoryview | None = None,
) -> dict[str, Any]:
    """Look up one safe credential projection by exact fixed credential id."""

    if not isinstance(credential_id, str) or _CREDENTIAL_ID_RE.fullmatch(credential_id) is None:
        raise _fail("credential_registry_credential_id_invalid")
    report = list_secure_credentials(
        archive_root,
        receipt_authentication_key=receipt_authentication_key,
    )
    matches = [row for row in report["credentials"] if row["credential_id"] == credential_id]
    if len(matches) != 1:
        raise _fail("credential_registry_credential_not_found")
    return matches[0]


def _persist_duplicate_lifecycle_decision(
    archive_root: Path | str,
    *,
    provider: str,
    workspace_fingerprint: str,
    selected_default_credential_id: str | None,
    revocation_pending_credential_ids: Sequence[str] = (),
    human_approved: bool,
    receipt_authentication_key: bytes | bytearray | memoryview,
    expected_plan_sha256: str | None = None,
    reviewed_by: str | None = None,
) -> dict[str, Any]:
    """Persist a human-approved default/legacy lifecycle without revocation."""

    root, archive_id = _validate_archive(archive_root)
    key = _validate_authentication_key(receipt_authentication_key)
    if not isinstance(provider, str) or _PROVIDER_RE.fullmatch(provider) is None:
        raise _fail("credential_registry_lifecycle_scope_invalid")
    if not isinstance(workspace_fingerprint, str) or _SHA256_RE.fullmatch(workspace_fingerprint) is None:
        raise _fail("credential_registry_lifecycle_scope_invalid")
    if selected_default_credential_id is not None and (
        not isinstance(selected_default_credential_id, str)
        or _CREDENTIAL_ID_RE.fullmatch(selected_default_credential_id) is None
    ):
        raise _fail("credential_registry_lifecycle_default_invalid")
    pending = set(revocation_pending_credential_ids)
    if len(pending) != len(tuple(revocation_pending_credential_ids)) or any(
        not isinstance(value, str) or _CREDENTIAL_ID_RE.fullmatch(value) is None for value in pending
    ):
        raise _fail("credential_registry_lifecycle_pending_invalid")
    with _archive_lock(root, create_if_missing=human_approved is True):
        records = _read_effective_receipt_records(root, key)
        scoped = [
            record
            for record in records
            if record.document["provider"] == provider
            and record.effective_workspace_fingerprint == workspace_fingerprint
        ]
        if not scoped:
            raise _fail("credential_registry_lifecycle_scope_not_found")
        if any(record.authentication_status != "valid" for record in scoped):
            raise _fail("credential_registry_receipt_authentication_invalid")
        existing, existing_status = _read_lifecycle(root, archive_id, key)
        if existing is not None and existing_status != "valid":
            raise _fail("credential_registry_lifecycle_authentication_invalid")
        credential_ids = {record.document["credential_id"] for record in scoped}
        fingerprints = {record.document["fingerprint_digest"] for record in scoped}
        if selected_default_credential_id not in credential_ids:
            raise _fail("credential_registry_lifecycle_default_invalid")
        if not pending.issubset(credential_ids) or selected_default_credential_id in pending:
            raise _fail("credential_registry_lifecycle_pending_invalid")
        credentials: list[dict[str, Any]] = []
        for credential_id in sorted(credential_ids):
            if credential_id == selected_default_credential_id:
                status, rotation, default = "active", "current", True
            elif credential_id in pending:
                status, rotation, default = "revocation_pending", "review_pending", False
            else:
                status, rotation, default = "legacy_valid", "legacy", False
            credentials.append(
                {
                    "credential_id": credential_id,
                    "lifecycle_status": status,
                    "rotation_status": rotation,
                    "is_default": default,
                }
            )
        receipt_set = [
            {
                "credential_id": record.document["credential_id"],
                "receipt_sha256": record.authority_sha256,
                "credential_fingerprint": record.document["fingerprint_digest"],
            }
            for record in sorted(scoped, key=lambda value: value.document["credential_id"])
        ]
        plan_document = {
            "schema_version": LIFECYCLE_PLAN_SCHEMA_VERSION,
            "archive_id": archive_id,
            "provider": provider,
            "workspace_fingerprint": workspace_fingerprint,
            "selected_default_credential_id": selected_default_credential_id,
            "revocation_pending_credential_ids": sorted(pending),
            "receipt_set": receipt_set,
            "existing_lifecycle_sha256": (
                None
                if existing is None
                else "sha256:" + hashlib.sha256(_canonical_json_bytes(existing)).hexdigest()
            ),
            "credentials": credentials,
        }
        plan_sha256 = "sha256:" + hashlib.sha256(
            _canonical_json_bytes(plan_document)
        ).hexdigest()
        decision_result = {
            "schema_version": REGISTRY_RESULT_SCHEMA_VERSION,
            "ok": True,
            "status": "human_decision_required",
            "persisted": False,
            "provider": provider,
            "verified_workspace_fingerprint": workspace_fingerprint,
            "credential_count": len(credentials),
            "distinct_fingerprint_count": len(fingerprints),
            "default_credential_id": selected_default_credential_id,
            "revocation_pending_count": len(pending),
            "legacy_valid_count": len(credentials) - len(pending) - 1,
            "credentials": credentials,
            "plan_sha256": plan_sha256,
            "delete_performed": False,
            "revoke_performed": False,
            "operator_action": "review_and_explicitly_approve_unchanged_default_plan",
        }
        if human_approved is not True:
            return decision_result
        if (
            not isinstance(expected_plan_sha256, str)
            or _SHA256_RE.fullmatch(expected_plan_sha256) is None
            or not hmac.compare_digest(expected_plan_sha256, plan_sha256)
        ):
            raise _fail("credential_registry_lifecycle_plan_mismatch")
        if (
            not isinstance(reviewed_by, str)
            or _SAFE_REVIEWER_RE.fullmatch(reviewed_by) is None
            or _SECRET_SHAPE_RE.search(reviewed_by)
        ):
            raise _fail("credential_registry_lifecycle_reviewer_invalid")
        revision_seed = {
            "plan_sha256": plan_sha256,
            "reviewed_by": reviewed_by,
            "credentials": credentials,
        }
        revision = "lifecycle-" + hashlib.sha256(
            _canonical_json_bytes(revision_seed)
        ).hexdigest()
        new_scope = {
            "provider": provider,
            "workspace_fingerprint": workspace_fingerprint,
            "revision": revision,
            "plan_sha256": plan_sha256,
            "reviewed_by": reviewed_by,
            "credentials": credentials,
        }
        scopes = [] if existing is None else [dict(scope) for scope in existing["scopes"]]
        scopes = [
            scope
            for scope in scopes
            if (scope["provider"], scope["workspace_fingerprint"])
            != (provider, workspace_fingerprint)
        ]
        scopes.append(new_scope)
        scopes.sort(key=lambda scope: (scope["provider"], scope["workspace_fingerprint"]))
        lifecycle_document: dict[str, Any] = {
            "schema_version": LIFECYCLE_SCHEMA_VERSION,
            "archive_id": archive_id,
            "scopes": scopes,
        }
        lifecycle_document["authentication"] = {
            "schema_version": LIFECYCLE_AUTHENTICATION_SCHEMA,
            "algorithm": "hmac-sha256",
            "mac": _lifecycle_mac(lifecycle_document, key),
        }
        _validate_lifecycle_document(lifecycle_document, archive_id=archive_id)
        lifecycle_path = _archive_path(root, LIFECYCLE_RELATIVE)
        _ensure_safe_parent_chain(root, lifecycle_path)
        _atomic_replace_json(lifecycle_path, lifecycle_document)
    return {
        "schema_version": REGISTRY_RESULT_SCHEMA_VERSION,
        "ok": True,
        "status": "decision_recorded",
        "persisted": True,
        "provider": provider,
        "verified_workspace_fingerprint": workspace_fingerprint,
        "credential_count": len(credentials),
        "distinct_fingerprint_count": len(fingerprints),
        "credentials": credentials,
        "revision": revision,
        "plan_sha256": plan_sha256,
        "reviewed_by": reviewed_by,
        "default_credential_id": selected_default_credential_id,
        "delete_performed": False,
        "revoke_performed": False,
    }


def _capability_claim_now(clock: Callable[[], datetime]) -> datetime:
    try:
        value = clock()
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise ValueError
        if value.utcoffset() != timedelta(0):
            raise ValueError
        return value.astimezone(timezone.utc)
    except Exception:
        raise _fail("credential_capability_clock_invalid") from None


def _capability_claim_timestamp(value: datetime) -> str:
    return value.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_capability_claim_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
        value,
    ) is None:
        raise _fail("credential_capability_claim_timestamp_invalid")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        raise _fail("credential_capability_claim_timestamp_invalid") from None


def _capability_claim_authentication_payload(
    document: Mapping[str, Any],
) -> dict[str, Any]:
    payload = dict(document)
    payload.pop("authentication", None)
    return payload


def _capability_claim_mac(
    document: Mapping[str, Any],
    key: bytes | bytearray,
) -> str:
    return hmac.new(
        key,
        CAPABILITY_USE_CLAIM_AUTHENTICATION_DOMAIN
        + _canonical_json_bytes(_capability_claim_authentication_payload(document)),
        hashlib.sha256,
    ).hexdigest()


def _validate_capability_claim_document(
    document: Any,
    *,
    archive_id: str,
) -> dict[str, Any]:
    if type(document) is not dict or set(document) != _CAPABILITY_USE_CLAIM_KEYS:
        raise _fail("credential_capability_claim_document_invalid")
    result = dict(document)
    if result.get("schema_version") != CAPABILITY_USE_CLAIM_SCHEMA_VERSION:
        raise _fail("credential_capability_claim_document_invalid")
    if (
        not isinstance(result.get("archive_id"), str)
        or _SAFE_ARCHIVE_ID_RE.fullmatch(result["archive_id"]) is None
        or not hmac.compare_digest(result["archive_id"], archive_id)
    ):
        raise _fail("credential_capability_claim_archive_mismatch")
    if (
        not isinstance(result.get("capability_id"), str)
        or _CAPABILITY_ID_RE.fullmatch(result["capability_id"]) is None
    ):
        raise _fail("credential_capability_claim_document_invalid")
    if (
        not isinstance(result.get("capability_sha256"), str)
        or _SHA256_RE.fullmatch(result["capability_sha256"]) is None
    ):
        raise _fail("credential_capability_claim_document_invalid")
    if (
        not isinstance(result.get("request_sha256"), str)
        or _SHA256_RE.fullmatch(result["request_sha256"]) is None
        or not isinstance(result.get("plan_sha256"), str)
        or _SHA256_RE.fullmatch(result["plan_sha256"]) is None
    ):
        raise _fail("credential_capability_claim_document_invalid")
    if (
        result.get("provider") != CREDENTIAL_CAPABILITY_PROVIDER
        or result.get("operation") != CREDENTIAL_CAPABILITY_OPERATION
        or result.get("consumer") != CREDENTIAL_CAPABILITY_CONSUMER
        or type(result.get("max_uses")) is not int
        or result["max_uses"] != 1
        or type(result.get("max_provider_requests")) is not int
        or result["max_provider_requests"] < 1
    ):
        raise _fail("credential_capability_claim_document_invalid")
    status = result.get("status")
    if status not in {"started", "succeeded", "failed"}:
        raise _fail("credential_capability_claim_state_invalid")
    started_at = _parse_capability_claim_timestamp(result.get("started_at"))
    finished_at_value = result.get("finished_at")
    failure_code = result.get("failure_code")
    authorized = result.get("provider_requests_authorized")
    if (
        type(authorized) is not int
        or authorized < 0
        or authorized > result["max_provider_requests"]
    ):
        raise _fail("credential_capability_claim_document_invalid")
    if status == "started":
        if finished_at_value is not None or failure_code is not None or authorized != 0:
            raise _fail("credential_capability_claim_state_invalid")
    else:
        finished_at = _parse_capability_claim_timestamp(finished_at_value)
        if finished_at < started_at:
            raise _fail("credential_capability_claim_state_invalid")
        if status == "succeeded" and failure_code is not None:
            raise _fail("credential_capability_claim_state_invalid")
        if status == "failed" and (
            not isinstance(failure_code, str)
            or _PURPOSE_RE.fullmatch(failure_code) is None
            or _SECRET_SHAPE_RE.search(failure_code) is not None
        ):
            raise _fail("credential_capability_claim_state_invalid")
    authentication = result.get("authentication")
    if type(authentication) is not dict or set(authentication) != _AUTHENTICATION_KEYS:
        raise _fail("credential_capability_claim_authentication_invalid")
    if (
        authentication.get("schema_version")
        != CAPABILITY_USE_CLAIM_AUTHENTICATION_SCHEMA
        or authentication.get("algorithm") != "hmac-sha256"
        or not isinstance(authentication.get("mac"), str)
        or _HEX_SHA256_RE.fullmatch(authentication["mac"]) is None
    ):
        raise _fail("credential_capability_claim_authentication_invalid")
    return result


def _exclusive_create_capability_claim(
    root: Path,
    path: Path,
    document: Mapping[str, Any],
) -> None:
    """Publish a complete claim once; every pre-existing leaf is a replay."""

    _ensure_safe_parent_chain(root, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _ensure_safe_parent_chain(root, path)
    body = _canonical_json_bytes(document) + b"\n"
    if len(body) > MAX_CAPABILITY_USE_CLAIM_BYTES:
        raise _fail("credential_capability_claim_document_invalid")
    temporary = path.parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
    descriptor: int | None = None
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_BINARY", 0),
            0o600,
        )
        written = 0
        while written < len(body):
            count = os.write(descriptor, body[written:])
            if count <= 0:
                raise OSError
            written += count
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        try:
            os.link(temporary, path)
        except FileExistsError:
            raise _fail("credential_capability_claim_replayed") from None
        _fsync_directory(path.parent)
    except SecureCredentialRegistryError:
        raise
    except Exception:
        raise _fail("credential_capability_claim_commit_failed") from None
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _read_authenticated_capability_claim(
    root: Path,
    path: Path,
    archive_id: str,
    key: bytes | bytearray,
    capability: _CredentialCapability,
) -> dict[str, Any]:
    _ensure_safe_parent_chain(root, path)
    raw = _read_exact_bytes(
        path,
        maximum=MAX_CAPABILITY_USE_CLAIM_BYTES,
        missing_code="credential_capability_claim_missing",
    )
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise _fail("credential_capability_claim_document_invalid") from None
    document = _validate_capability_claim_document(parsed, archive_id=archive_id)
    canonical = _canonical_json_bytes(document) + b"\n"
    if not hmac.compare_digest(raw, canonical):
        raise _fail("credential_capability_claim_document_invalid")
    authentication = document["authentication"]
    if not hmac.compare_digest(
        authentication["mac"],
        _capability_claim_mac(document, key),
    ):
        raise _fail("credential_capability_claim_authentication_invalid")
    expected_strings = {
        "capability_id": capability.capability_id,
        "capability_sha256": capability.digest_sha256,
        "request_sha256": capability.request_sha256,
        "plan_sha256": capability.plan_sha256,
        "provider": capability.provider,
        "operation": capability.operation,
        "consumer": capability.consumer,
    }
    if any(
        not hmac.compare_digest(document[name], expected)
        for name, expected in expected_strings.items()
    ) or (
        document["max_uses"] != capability.max_uses
        or document["max_provider_requests"] != capability.max_provider_requests
    ):
        raise _fail("credential_capability_claim_binding_mismatch")
    return document


def _capability_scope_from_binding(scope_binding: ScopeBinding) -> CredentialCapabilityScope:
    if not isinstance(scope_binding, ScopeBinding):
        raise _fail("credential_registry_scope_binding_invalid")
    try:
        return CredentialCapabilityScope(
            credential_id=scope_binding.credential_id,
            workspace_fingerprint=scope_binding.workspace_fingerprint,
            scope_receipt_sha256=scope_binding.scope_receipt_sha256,
            revision=scope_binding.revision,
        )
    except CredentialCapabilityError as exc:
        raise _fail(exc.code) from None


_CLAIMED_CAPABILITY_FACTORY_TOKEN = object()


class _ClaimedCredentialCapabilityUse:
    """One durable, authenticated claim plus its in-memory request budget."""

    __slots__ = (
        "_archive_root",
        "_archive_id",
        "_claim_path",
        "_authentication_key",
        "_capability",
        "_lease",
        "_started_at",
        "_clock",
        "_state_lock",
        "_status",
    )

    def __init__(
        self,
        *,
        factory_token: object,
        archive_root: Path,
        archive_id: str,
        claim_path: Path,
        authentication_key: bytes | bytearray,
        capability: _CredentialCapability,
        lease: _CredentialCapabilityLease,
        started_at: str,
        clock: Callable[[], datetime],
    ) -> None:
        if factory_token is not _CLAIMED_CAPABILITY_FACTORY_TOKEN:
            raise _fail("credential_capability_claim_invalid")
        self._archive_root = archive_root
        self._archive_id = archive_id
        self._claim_path = claim_path
        self._authentication_key = authentication_key
        self._capability = capability
        self._lease = lease
        self._started_at = started_at
        self._clock = clock
        self._state_lock = threading.RLock()
        self._status = "started"

    def __repr__(self) -> str:
        return "<_ClaimedCredentialCapabilityUse claim=authenticated bindings=redacted>"

    @property
    def capability(self) -> _CredentialCapability:
        return self._capability

    @property
    def capability_id(self) -> str:
        return self._capability.capability_id

    @property
    def capability_sha256(self) -> str:
        return self._capability.digest_sha256

    @property
    def claim_created(self) -> bool:
        return True

    @property
    def max_uses(self) -> int:
        return self._capability.max_uses

    @property
    def provider_request_authorizations(self) -> int:
        return self._lease.provider_requests_authorized

    @property
    def provider_requests_remaining(self) -> int:
        return self._lease.provider_requests_remaining

    @property
    def status(self) -> str:
        with self._state_lock:
            return self._status

    def public_summary(self) -> dict[str, Any]:
        with self._state_lock:
            return {
                "schema_version": CAPABILITY_USE_SUMMARY_SCHEMA_VERSION,
                "capability_id": self.capability_id,
                "capability_sha256": self.capability_sha256,
                "claim_created": True,
                "max_uses": self.max_uses,
                "provider_request_authorizations": (
                    self.provider_request_authorizations
                ),
                "status": self._status,
            }

    def _assert_started_claim(self) -> None:
        if self._status != "started":
            raise _fail("credential_capability_claim_state_invalid")
        with _archive_lock(self._archive_root, create_if_missing=False):
            document = _read_authenticated_capability_claim(
                self._archive_root,
                self._claim_path,
                self._archive_id,
                self._authentication_key,
                self._capability,
            )
        if document["status"] != "started" or not hmac.compare_digest(
            document["started_at"], self._started_at
        ):
            raise _fail("credential_capability_claim_state_invalid")

    def assert_ready_for_scope(self, scope: ScopeBinding) -> None:
        """Check the durable claim and exact scope without spending a request."""

        with self._state_lock:
            self._assert_started_claim()
            capability_scope = _capability_scope_from_binding(scope)
            if capability_scope not in self._capability.scopes:
                raise _fail("credential_capability_scope_not_allowed")

    def authorize_request(self, endpoint_class: str, *, scope: ScopeBinding) -> int:
        """Reauthenticate the claim, then atomically spend one request."""

        with self._state_lock:
            self._assert_started_claim()
            capability_scope = _capability_scope_from_binding(scope)
            try:
                return self._lease.authorize_request(
                    endpoint_class,
                    scope=capability_scope,
                )
            except CredentialCapabilityError as exc:
                raise _fail(exc.code) from None

    def _finalize(self, *, status: str, failure_code: str | None) -> None:
        with self._state_lock:
            if self._status != "started":
                raise _fail("credential_capability_claim_state_invalid")
            finished_at = _capability_claim_timestamp(
                _capability_claim_now(self._clock)
            )
            with _archive_lock(self._archive_root, create_if_missing=False):
                current = _read_authenticated_capability_claim(
                    self._archive_root,
                    self._claim_path,
                    self._archive_id,
                    self._authentication_key,
                    self._capability,
                )
                if current["status"] != "started" or not hmac.compare_digest(
                    current["started_at"], self._started_at
                ):
                    raise _fail("credential_capability_claim_state_invalid")
                finalized = dict(current)
                finalized.update(
                    {
                        "status": status,
                        "finished_at": finished_at,
                        "failure_code": failure_code,
                        "provider_requests_authorized": (
                            self.provider_request_authorizations
                        ),
                    }
                )
                finalized["authentication"] = {
                    "schema_version": CAPABILITY_USE_CLAIM_AUTHENTICATION_SCHEMA,
                    "algorithm": "hmac-sha256",
                    "mac": _capability_claim_mac(finalized, self._authentication_key),
                }
                _validate_capability_claim_document(
                    finalized,
                    archive_id=self._archive_id,
                )
                _atomic_replace_json(self._claim_path, finalized)
            self._status = status

    def finalize_succeeded(self) -> None:
        self._finalize(status="succeeded", failure_code=None)

    def finalize_failed(self, failure_code: str) -> None:
        if (
            not isinstance(failure_code, str)
            or _PURPOSE_RE.fullmatch(failure_code) is None
            or _SECRET_SHAPE_RE.search(failure_code) is not None
        ):
            raise _fail("credential_capability_failure_code_invalid")
        self._finalize(status="failed", failure_code=failure_code)


def _claim_credential_capability_use(
    archive_root: Path | str,
    capability: _CredentialCapability,
    receipt_authentication_key: bytes | bytearray | memoryview,
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> _ClaimedCredentialCapabilityUse:
    """Exclusively claim one capability before any native secret read."""

    if type(capability) is not _CredentialCapability:
        raise _fail("credential_capability_invalid")
    root, archive_id = _validate_archive(archive_root)
    key = _validate_authentication_key(receipt_authentication_key)
    claim_path = _archive_path(
        root,
        f"{CAPABILITY_CLAIMS_RELATIVE}/{capability.capability_id}.json",
    )
    with _archive_lock(root):
        try:
            os.lstat(claim_path)
        except FileNotFoundError:
            pass
        except OSError:
            raise _fail("credential_capability_claim_commit_failed") from None
        else:
            # Never inspect or accept an existing leaf. A partial, malformed,
            # tampered, finalized, or symlink-shaped claim permanently spends
            # the one-use identifier just like a valid started claim.
            raise _fail("credential_capability_claim_replayed")
        claimed_at = _capability_claim_now(clock)
        try:
            lease = capability.new_lease(claimed_at=claimed_at)
        except CredentialCapabilityError as exc:
            raise _fail(exc.code) from None
        started_at = _capability_claim_timestamp(claimed_at)
        document: dict[str, Any] = {
            "schema_version": CAPABILITY_USE_CLAIM_SCHEMA_VERSION,
            "archive_id": archive_id,
            "capability_id": capability.capability_id,
            "capability_sha256": capability.digest_sha256,
            "request_sha256": capability.request_sha256,
            "plan_sha256": capability.plan_sha256,
            "provider": capability.provider,
            "operation": capability.operation,
            "consumer": capability.consumer,
            "max_uses": capability.max_uses,
            "max_provider_requests": capability.max_provider_requests,
            "status": "started",
            "started_at": started_at,
            "finished_at": None,
            "failure_code": None,
            "provider_requests_authorized": 0,
        }
        document["authentication"] = {
            "schema_version": CAPABILITY_USE_CLAIM_AUTHENTICATION_SCHEMA,
            "algorithm": "hmac-sha256",
            "mac": _capability_claim_mac(document, key),
        }
        _validate_capability_claim_document(document, archive_id=archive_id)
        _exclusive_create_capability_claim(root, claim_path, document)
    return _ClaimedCredentialCapabilityUse(
        factory_token=_CLAIMED_CAPABILITY_FACTORY_TOKEN,
        archive_root=root,
        archive_id=archive_id,
        claim_path=claim_path,
        authentication_key=key,
        capability=capability,
        lease=lease,
        started_at=started_at,
        clock=clock,
    )


@dataclass(repr=False)
class _ReceiptBackedNotionCredentialBroker:
    """Resolve one approved Notion scope through one exact native read."""

    archive_root: Path | str
    native: ExactWindowsCredentialNative = field(repr=False)
    receipt_authentication_key: bytes | bytearray | memoryview = field(repr=False)
    secret_fingerprint_key: bytes | bytearray | memoryview | None = field(
        default=None, repr=False
    )
    claimed_use: _ClaimedCredentialCapabilityUse | None = field(
        default=None, repr=False
    )

    def __repr__(self) -> str:
        return "<_ReceiptBackedNotionCredentialBroker provider=notion native=exact secret=redacted>"

    @staticmethod
    def _assert_authority(
        archive_root: Path | str,
        receipt_authentication_key: bytes | bytearray | memoryview,
        scope_binding: ScopeBinding,
    ) -> tuple[str, str]:
        """Authenticate the exact receipt/lifecycle scope without reading a secret."""

        if not isinstance(scope_binding, ScopeBinding):
            raise _fail("credential_registry_scope_binding_invalid")
        if scope_binding.persisted is not True or scope_binding.workspace_evidence_verified is not True:
            raise _fail("credential_registry_scope_binding_unverified")
        if (
            _CREDENTIAL_ID_RE.fullmatch(str(scope_binding.credential_id or "")) is None
            or _SHA256_RE.fullmatch(str(scope_binding.workspace_fingerprint or "")) is None
            or _SHA256_RE.fullmatch(str(scope_binding.scope_receipt_sha256 or "")) is None
            or _SAFE_REVISION_RE.fullmatch(str(scope_binding.revision or "")) is None
        ):
            raise _fail("credential_registry_scope_binding_invalid")
        root, archive_id = _validate_archive(archive_root)
        key = _validate_authentication_key(receipt_authentication_key)
        with _archive_lock(root, create_if_missing=False):
            records = _read_effective_receipt_records(root, key)
            matching = [
                record
                for record in records
                if record.document["credential_id"] == scope_binding.credential_id
            ]
            if len(matching) != 1:
                raise _fail("credential_registry_credential_not_found")
            record = matching[0]
            # Receipt authentication is checked before trusting provider,
            # workspace, backend id, fingerprint, or the caller's receipt hash.
            if record.authentication_status != "valid":
                raise _fail("credential_registry_receipt_authentication_invalid")
            if any(item.authentication_status != "valid" for item in records):
                raise _fail("credential_registry_receipt_set_untrusted")
            lifecycle_document, lifecycle_auth = _read_lifecycle(root, archive_id, key)
            if lifecycle_document is None or lifecycle_auth != "valid":
                raise _fail("credential_registry_lifecycle_authentication_invalid")
            lifecycle = _lifecycle_index(lifecycle_document).get(scope_binding.credential_id)
            if lifecycle is None:
                raise _fail("credential_registry_lifecycle_entry_missing")
            scope, state = lifecycle
            document = record.document
            if document["provider"] != "notion":
                raise _fail("credential_registry_provider_not_supported")
            if document["purpose"] not in {
                "source_recovery",
                "notion_page_recovery",
            }:
                raise _fail("credential_registry_purpose_not_authorized")
            if not set(CREDENTIAL_CAPABILITY_REQUIRED_REGISTERED_CAPABILITIES).issubset(
                document["verified_capabilities"]
            ):
                raise _fail(
                    "credential_registry_registered_capabilities_insufficient"
                )
            if not hmac.compare_digest(record.authority_sha256, scope_binding.scope_receipt_sha256):
                raise _fail("credential_registry_scope_receipt_mismatch")
            if not hmac.compare_digest(
                record.effective_workspace_fingerprint,
                scope_binding.workspace_fingerprint,
            ):
                raise _fail("credential_registry_scope_workspace_mismatch")
            if (
                scope["provider"] != document["provider"]
                or scope["workspace_fingerprint"]
                != record.effective_workspace_fingerprint
            ):
                raise _fail("credential_registry_lifecycle_scope_mismatch")
            lifecycle_ids = {row["credential_id"] for row in scope["credentials"]}
            receipt_ids = {
                item.document["credential_id"]
                for item in records
                if item.document["provider"] == document["provider"]
                and item.effective_workspace_fingerprint
                == record.effective_workspace_fingerprint
            }
            if lifecycle_ids != receipt_ids:
                raise _fail("credential_registry_lifecycle_receipt_set_drift")
            if not hmac.compare_digest(scope["revision"], scope_binding.revision):
                raise _fail("credential_registry_scope_revision_mismatch")
            if not (
                state["lifecycle_status"] == "active"
                and state["rotation_status"] == "current"
                and state["is_default"] is True
            ):
                raise _fail("credential_registry_lifecycle_not_default")
            if document["encrypted_backend_kind"] != "windows_credential_manager_generic":
                raise _fail("credential_registry_backend_not_supported")
            backend_id = document["encrypted_backend_id"]
            if _BACKEND_ID_RE.fullmatch(backend_id) is None:
                raise _fail("credential_registry_receipt_backend_invalid")
            expected_fingerprint = document["fingerprint_digest"]
            return windows_credential_target(archive_id, backend_id), expected_fingerprint

    def _assert_current_authority(
        self,
        scope_binding: ScopeBinding,
    ) -> tuple[str, str]:
        return self._assert_authority(
            self.archive_root,
            self.receipt_authentication_key,
            scope_binding,
        )

    def revalidate_authority(self, scope_binding: ScopeBinding) -> None:
        """Fail closed if this content-free receipt/lifecycle authority drifted."""

        self._assert_current_authority(scope_binding)

    def resolve(self, scope_binding: ScopeBinding) -> _NotionBearerSecret:
        claimed_use = self.claimed_use
        if claimed_use is None:
            raise _fail("credential_capability_required")
        if type(claimed_use) is not _ClaimedCredentialCapabilityUse:
            raise _fail("credential_capability_claim_invalid")
        target, expected_fingerprint = self._assert_current_authority(scope_binding)
        claimed_use.assert_ready_for_scope(scope_binding)
        if self.secret_fingerprint_key is None:
            raise _fail("credential_registry_secret_fingerprint_key_invalid")
        fingerprint_key = _validate_authentication_key(
            self.secret_fingerprint_key
        )
        secret_buffer: bytearray | None = None
        try:
            try:
                secret_buffer = self.native.read_generic_secret_exact(target)
            except Exception:
                raise _fail("credential_registry_secret_read_failed") from None
            if not isinstance(secret_buffer, bytearray) or not secret_buffer:
                raise _fail("credential_registry_secret_read_failed")
            current_fingerprint = "hmac-sha256:" + hmac.new(
                fingerprint_key,
                secret_buffer,
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(current_fingerprint, expected_fingerprint):
                raise _fail("credential_registry_secret_fingerprint_mismatch")
            try:
                wrapped = _NotionBearerSecret._from_owned_mutable(secret_buffer)
            except Exception:
                raise _fail("credential_registry_secret_invalid") from None
            # The wrapper now owns the exact mutable native buffer. Recovery
            # closes it after the bounded group run; do not wipe it here. The
            # callback retains only the archive authentication material and
            # content-free scope binding. It never retains the native adapter
            # or bearer fingerprint key, and it never rereads the secret.
            secret_buffer = None
            authority_root = self.archive_root
            authority_key = self.receipt_authentication_key
            try:
                wrapped._bind_authority_revalidator(
                    lambda: _ReceiptBackedNotionCredentialBroker._assert_authority(
                        authority_root,
                        authority_key,
                        scope_binding,
                    )
                )
            except Exception:
                wrapped.close()
                raise _fail(
                    "credential_registry_authority_revalidator_invalid"
                ) from None
            try:
                wrapped._bind_capability_authorizer(
                    lambda endpoint_class: claimed_use.authorize_request(
                        endpoint_class,
                        scope=scope_binding,
                    )
                )
            except Exception:
                wrapped.close()
                raise _fail("credential_capability_authorizer_invalid") from None
            return wrapped
        finally:
            if secret_buffer is not None:
                for index in range(len(secret_buffer)):
                    secret_buffer[index] = 0


__all__ = [
    "AuthenticatedCredentialReuseEvidence",
    "CAPABILITY_CLAIMS_RELATIVE",
    "CAPABILITY_USE_CLAIM_AUTHENTICATION_SCHEMA",
    "CAPABILITY_USE_CLAIM_SCHEMA_VERSION",
    "CAPABILITY_USE_SUMMARY_SCHEMA_VERSION",
    "ExactWindowsCredentialNative",
    "SecureCredentialRegistryError",
    "list_secure_credentials",
    "lookup_secure_credential",
]
