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
reviewed anchor id.  Plain ``AtomicJsonReceiptCommitter`` receipts remain
discoverable as unauthenticated history, but are never broker-authoritative.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
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
    AtomicJsonReceiptCommitter,
    RECEIPT_SCHEMA_VERSION,
)
from .credential_secure_intake_windows import windows_credential_target
from .notion_http_adapter import NotionBearerSecret
from .notion_page_recovery import ScopeBinding


RECEIPTS_RELATIVE = "profiles/local/credential-intake/receipts"
LIFECYCLE_RELATIVE = "profiles/local/credential-intake/lifecycle.json"
LOCK_RELATIVE = "profiles/local/credential-intake/.registry.lock"

RECEIPT_AUTHENTICATION_SCHEMA = "wom-credential-receipt-authentication/v0.1"
LIFECYCLE_SCHEMA_VERSION = "wom-credential-secure-registry-lifecycle/v0.1"
LIFECYCLE_PLAN_SCHEMA_VERSION = "wom-credential-secure-registry-lifecycle-plan/v0.1"
LIFECYCLE_AUTHENTICATION_SCHEMA = "wom-credential-lifecycle-authentication/v0.1"
REGISTRY_RESULT_SCHEMA_VERSION = "wom-credential-secure-registry-result/v0.1"

RECEIPT_AUTHENTICATION_DOMAIN = (
    b"wom/credential-secure-registry/receipt-authentication/v0.1\x00"
)
LIFECYCLE_AUTHENTICATION_DOMAIN = (
    b"wom/credential-secure-registry/lifecycle-authentication/v0.1\x00"
)
ARCHIVE_KEY_TARGET_DOMAIN = b"wom/credential-secure-registry/archive-key-target/v0.1\x00"

WINDOWS_ARCHIVE_KEY_TARGET_PREFIX = "WOM/credential-intake/backend_key_"

MAX_RECEIPT_BYTES = 64 * 1024
MAX_LIFECYCLE_BYTES = 256 * 1024
MAX_ARCHIVE_DOCUMENT_BYTES = 256 * 1024
MAX_RECEIPTS = 512
AUTHENTICATION_KEY_BYTES = 32
REPARSE_FLAG = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

_CREDENTIAL_ID_RE = re.compile(r"^cred_[A-Za-z0-9_-]{16,96}$")
_RECEIPT_TEMP_RE = re.compile(
    r"^\.(cred_[A-Za-z0-9_-]{16,96})\.[0-9a-f]{16}\.tmp$"
)
_BACKEND_ID_RE = re.compile(r"^backend_[A-Za-z0-9_-]{16,96}$")
_REQUEST_ID_RE = re.compile(r"^intake_[A-Za-z0-9_-]{16,96}$")
_PROVIDER_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_PURPOSE_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_HEX_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_HMAC_SHA256_RE = re.compile(r"^hmac-sha256:[0-9a-f]{64}$")
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


def _ensure_safe_parent_chain(root: Path, path: Path) -> None:
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
        raise _fail("credential_registry_local_document_unsafe")


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
    expected = set(_RECEIPT_KEYS)
    if authentication_optional:
        if keys not in (expected, expected | {"receipt_authentication"}):
            raise _fail("credential_registry_receipt_schema_invalid")
    elif keys != expected:
        raise _fail("credential_registry_receipt_schema_invalid")
    if result.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise _fail("credential_registry_receipt_schema_invalid")
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
            self._handle = self.path.open(
                "a+b" if self.create_if_missing else "r+b"
            )
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
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
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


@dataclass(repr=False)
class AuthenticatedArchiveReceiptCommitter:
    """Atomic intake committer fixed to one archive's ignored-local path."""

    archive_root: Path
    archive_id: str
    _authentication_key: bytes | bytearray = field(repr=False)

    def __repr__(self) -> str:
        return "<AuthenticatedArchiveReceiptCommitter path=fixed key=redacted>"

    def commit_atomic(self, receipt: Mapping[str, Any]) -> str:
        root, archive_id = _validate_archive(self.archive_root)
        if archive_id != self.archive_id:
            raise _fail("credential_registry_archive_identity_changed")
        document = _validate_receipt_document(receipt, authentication_optional=False)
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
                reference = AtomicJsonReceiptCommitter(receipts_root).commit_atomic(authenticated)
            except Exception:
                raise _fail("credential_registry_receipt_commit_failed") from None
            # AtomicJsonReceiptCommitter returns only after file fsync and the
            # create-if-absent hard-link publication. Never introduce a new
            # failure after that commit point: the intake worker would
            # otherwise delete the encrypted entry while a valid persisted
            # receipt remained. Future reads authenticate the receipt again.
            return reference


def create_archive_atomic_json_receipt_committer(
    archive_root: Path | str,
    *,
    expected_archive_id: str,
    receipt_authentication_key: bytes | bytearray | memoryview,
) -> AuthenticatedArchiveReceiptCommitter:
    """Create an authenticated ``AtomicJsonReceiptCommitter``-compatible adapter."""

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
    return AuthenticatedArchiveReceiptCommitter(root, archive_id, key)


@dataclass(repr=False)
class StableArchiveFingerprintKeyProvider:
    """Create once and reuse one exact archive-specific Windows key.

    The only API is callback-based.  The mutable key buffer is wiped after the
    callback returns; callers should return a configured object, digest, or
    status rather than the key itself.
    """

    native: ExactWindowsCredentialNative = field(repr=False)
    random_bytes: Callable[[int], bytes] = field(default=secrets.token_bytes, repr=False)

    def __repr__(self) -> str:
        return "<StableArchiveFingerprintKeyProvider native=exact key=redacted>"

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
            # AtomicJsonReceiptCommitter may leave this exact, non-authority
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
            )
        )
    return records


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
    revision = (
        scope["revision"]
        if scope is not None
        else "receipt-" + record.receipt_sha256.removeprefix("sha256:")
    )
    lifecycle_scope_matches = bool(
        scope is not None
        and scope["provider"] == document["provider"]
        and scope["workspace_fingerprint"] == document["verified_workspace_fingerprint"]
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
        "verified_workspace_fingerprint": document["verified_workspace_fingerprint"],
        "receipt_sha256": record.receipt_sha256,
        "receipt_authentication_status": record.authentication_status,
        "lifecycle_authentication_status": lifecycle_authentication_status,
        "broker_authoritative": broker_authoritative,
        "scope_binding": {
            "credential_id": document["credential_id"],
            "workspace_fingerprint": document["verified_workspace_fingerprint"],
            "scope_receipt_sha256": record.receipt_sha256,
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
        records = _read_receipt_records(root, key)
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
                and record.document["verified_workspace_fingerprint"]
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


def persist_duplicate_lifecycle_decision(
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
        records = _read_receipt_records(root, key)
        scoped = [
            record
            for record in records
            if record.document["provider"] == provider
            and record.document["verified_workspace_fingerprint"] == workspace_fingerprint
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
                "receipt_sha256": record.receipt_sha256,
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


@dataclass(repr=False)
class ReceiptBackedNotionCredentialBroker:
    """Resolve one approved Notion scope through one exact native read."""

    archive_root: Path | str
    native: ExactWindowsCredentialNative = field(repr=False)
    receipt_authentication_key: bytes | bytearray | memoryview = field(repr=False)
    secret_fingerprint_key: bytes | bytearray | memoryview | None = field(
        default=None, repr=False
    )

    def __repr__(self) -> str:
        return "<ReceiptBackedNotionCredentialBroker provider=notion native=exact secret=redacted>"

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
            records = _read_receipt_records(root, key)
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
            if not hmac.compare_digest(record.receipt_sha256, scope_binding.scope_receipt_sha256):
                raise _fail("credential_registry_scope_receipt_mismatch")
            if not hmac.compare_digest(
                document["verified_workspace_fingerprint"],
                scope_binding.workspace_fingerprint,
            ):
                raise _fail("credential_registry_scope_workspace_mismatch")
            if (
                scope["provider"] != document["provider"]
                or scope["workspace_fingerprint"] != document["verified_workspace_fingerprint"]
            ):
                raise _fail("credential_registry_lifecycle_scope_mismatch")
            lifecycle_ids = {row["credential_id"] for row in scope["credentials"]}
            receipt_ids = {
                item.document["credential_id"]
                for item in records
                if item.document["provider"] == document["provider"]
                and item.document["verified_workspace_fingerprint"]
                == document["verified_workspace_fingerprint"]
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

    def resolve(self, scope_binding: ScopeBinding) -> NotionBearerSecret:
        target, expected_fingerprint = self._assert_current_authority(scope_binding)
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
                wrapped = NotionBearerSecret._from_owned_mutable(secret_buffer)
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
                    lambda: ReceiptBackedNotionCredentialBroker._assert_authority(
                        authority_root,
                        authority_key,
                        scope_binding,
                    )
                )
            except Exception:
                wrapped.close()
                raise _fail("credential_registry_authority_revalidator_invalid") from None
            return wrapped
        finally:
            if secret_buffer is not None:
                for index in range(len(secret_buffer)):
                    secret_buffer[index] = 0


__all__ = [
    "AuthenticatedArchiveReceiptCommitter",
    "ExactWindowsCredentialNative",
    "ReceiptBackedNotionCredentialBroker",
    "SecureCredentialRegistryError",
    "StableArchiveFingerprintKeyProvider",
    "create_archive_atomic_json_receipt_committer",
    "list_secure_credentials",
    "lookup_secure_credential",
    "persist_duplicate_lifecycle_decision",
]
