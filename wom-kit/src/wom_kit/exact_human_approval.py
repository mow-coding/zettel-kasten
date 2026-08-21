"""Authenticated, one-use claim for an exact human-confirmed write plan.

The native dialog in :mod:`exact_human_approval_windows` establishes local
interactive intent.  This module turns that ephemeral decision into a durable
archive-bound claim *before* the first write.  A claim is authenticated with
the existing archive-specific key, cannot be reused, and remains ``started``
after a crash so reconciliation never silently treats an uncertain write as
safe to repeat.

The claim is stored below ignored-local ``profiles/local``.  Public projections
contain only random identifiers, SHA-256 bindings, fixed states, and booleans.
The supplied reviewer label is explicitly a claim, not authenticated identity;
only its domain-separated digest is persisted.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import stat
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import yaml

from .exact_human_approval_windows import (
    ExactHumanApprovalContext,
    ExactHumanApprovalOperation,
    _ExactHumanApprovalDecision,
)


CLAIM_SCHEMA_VERSION = "wom-kit/exact-human-approval-claim/v0.1"
REFERENCE_SCHEMA_VERSION = "wom-kit/exact-human-approval-reference/v0.1"
SUMMARY_SCHEMA_VERSION = "wom-kit/exact-human-approval-summary/v0.1"
AUTHENTICATION_SCHEMA_VERSION = (
    "wom-kit/exact-human-approval-claim-authentication/v0.1"
)
CLAIMS_RELATIVE_ROOT = "profiles/local/exact-human-approvals/claims"
APPROVAL_INTEGRITY_MAC_DOMAIN = (
    b"wom-kit/approval-integrity-overlay-mac/v0.1\x00"
)
APPROVAL_INTEGRITY_MAC_MAX_PAYLOAD_BYTES = 128 * 1024
APPROVAL_LINK_MAC_DOMAIN = b"wom-kit/exact-human-approval-link-mac/v0.1\x00"
APPROVAL_LINK_MAC_MAX_PAYLOAD_BYTES = 32 * 1024

_AUTHENTICATION_DOMAIN = b"wom-kit/exact-human-approval-claim/v0.1\x00"
_AUTHORITY_DOMAIN = b"wom-kit/exact-human-approval-authority/v0.1\x00"
_REVIEWER_DOMAIN = b"wom-kit/exact-human-approval-reviewer-claim/v0.1\x00"
_ARCHIVE_IDENTITY_DOMAIN = b"wom-kit/exact-human-approval-archive-id/v0.1\x00"
_APPROVAL_ID_RE = re.compile(r"^approval_[0-9a-f]{32}$")
_ARCHIVE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_FAILURE_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,95}$")
_CONTEXT_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_KEY_BYTES = 32
_MAX_CLAIM_BYTES = 32_768


class ExactHumanApprovalError(RuntimeError):
    """Fixed-code error; native, filesystem, and caller text is discarded."""

    _CODES = {
        "exact_human_approval_archive_invalid",
        "exact_human_approval_key_invalid",
        "exact_human_approval_decision_required",
        "exact_human_approval_binding_mismatch",
        "exact_human_approval_reviewer_claim_invalid",
        "exact_human_approval_time_invalid",
        "exact_human_approval_claim_path_unsafe",
        "exact_human_approval_claim_replayed",
        "exact_human_approval_claim_commit_failed",
        "exact_human_approval_claim_missing",
        "exact_human_approval_claim_document_invalid",
        "exact_human_approval_claim_authentication_invalid",
        "exact_human_approval_claim_state_invalid",
        "exact_human_approval_failure_code_invalid",
        "exact_human_approval_finalization_failed",
        "exact_human_approval_integrity_payload_invalid",
        "exact_human_approval_integrity_mac_invalid",
        "exact_human_approval_integrity_reference_invalid",
        "exact_human_approval_link_payload_invalid",
        "exact_human_approval_link_mac_invalid",
    }

    def __init__(self, code: str) -> None:
        self.code = code if code in self._CODES else "exact_human_approval_claim_document_invalid"
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"ExactHumanApprovalError({self.code!r})"


def _fail(code: str) -> ExactHumanApprovalError:
    return ExactHumanApprovalError(code)


def _canonical_bytes(document: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            dict(document),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _is_reparse(info: os.stat_result) -> bool:
    return bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _safe_directory(path: Path, *, create: bool) -> None:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        if not create:
            raise _fail("exact_human_approval_claim_path_unsafe") from None
        try:
            path.mkdir()
            info = os.lstat(path)
        except (OSError, FileExistsError):
            raise _fail("exact_human_approval_claim_path_unsafe") from None
    except OSError:
        raise _fail("exact_human_approval_claim_path_unsafe") from None
    if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
        raise _fail("exact_human_approval_claim_path_unsafe")


def _archive_identity(archive_root: Path | str) -> tuple[Path, str]:
    try:
        root = Path(archive_root).resolve(strict=True)
        root_info = os.lstat(root)
    except (OSError, RuntimeError, TypeError, ValueError):
        raise _fail("exact_human_approval_archive_invalid") from None
    if _is_reparse(root_info) or not stat.S_ISDIR(root_info.st_mode):
        raise _fail("exact_human_approval_archive_invalid")
    marker = root / "archive.yml"
    try:
        marker_info = os.lstat(marker)
        if _is_reparse(marker_info) or not stat.S_ISREG(marker_info.st_mode):
            raise _fail("exact_human_approval_archive_invalid")
        raw = marker.read_bytes()
        document = yaml.safe_load(raw.decode("utf-8"))
    except ExactHumanApprovalError:
        raise
    except (OSError, UnicodeError, yaml.YAMLError):
        raise _fail("exact_human_approval_archive_invalid") from None
    archive_id = document.get("archive_id") if isinstance(document, Mapping) else None
    if type(archive_id) is not str or _ARCHIVE_ID_RE.fullmatch(archive_id) is None:
        raise _fail("exact_human_approval_archive_invalid")
    return root, archive_id


def _claims_root(root: Path, *, create: bool) -> Path:
    current = root
    for name in ("profiles", "local", "exact-human-approvals", "claims"):
        current = current / name
        _safe_directory(current, create=create)
    return current


def _validated_key(value: bytes | bytearray | memoryview) -> bytearray:
    try:
        raw = bytes(value)
    except (TypeError, ValueError):
        raise _fail("exact_human_approval_key_invalid") from None
    if len(raw) != _KEY_BYTES:
        raise _fail("exact_human_approval_key_invalid")
    return bytearray(raw)


def _now(clock: Callable[[], datetime]) -> datetime:
    try:
        value = clock()
    except BaseException:
        raise _fail("exact_human_approval_time_invalid") from None
    if type(value) is not datetime or value.tzinfo is None:
        raise _fail("exact_human_approval_time_invalid")
    return value.astimezone(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_timestamp(value: Any) -> datetime:
    if type(value) is not str:
        raise _fail("exact_human_approval_claim_document_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise _fail("exact_human_approval_claim_document_invalid") from None
    if parsed.tzinfo is None or _timestamp(parsed.astimezone(timezone.utc)) != value:
        raise _fail("exact_human_approval_claim_document_invalid")
    return parsed.astimezone(timezone.utc)


def _context_document(context: ExactHumanApprovalContext) -> dict[str, Any]:
    return {
        "operation": context.operation.value,
        "archive_identity_sha256": context.archive_identity_sha256,
        "plan_sha256": context.plan_sha256,
        "target_binding_sha256": context.target_binding_sha256,
        "reviewer_claim_sha256": _sha256(
            _REVIEWER_DOMAIN + context.reviewer_claim.encode("utf-8")
        ),
        "review_binding_codes": list(context.review_binding_codes),
        "warning_codes": list(context.warning_codes),
    }


def exact_human_approval_context_sha256(
    context: ExactHumanApprovalContext,
) -> str:
    if type(context) is not ExactHumanApprovalContext:
        raise _fail("exact_human_approval_binding_mismatch")
    return _sha256(_AUTHORITY_DOMAIN + _canonical_bytes(_context_document(context)))


def exact_human_approval_archive_identity_sha256(archive_id: str) -> str:
    """Return the only archive-id projection accepted by the claim boundary."""

    if type(archive_id) is not str or _ARCHIVE_ID_RE.fullmatch(archive_id) is None:
        raise _fail("exact_human_approval_archive_invalid")
    return _sha256(_ARCHIVE_IDENTITY_DOMAIN + archive_id.encode("utf-8"))


def _authentication_payload(document: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(document)
    payload.pop("authentication", None)
    return payload


def _claim_mac(document: Mapping[str, Any], key: bytes | bytearray) -> str:
    return "hmac-sha256:" + hmac.new(
        key,
        _AUTHENTICATION_DOMAIN + _canonical_bytes(_authentication_payload(document)),
        hashlib.sha256,
    ).hexdigest()


def _authenticated(document: Mapping[str, Any], key: bytes | bytearray) -> dict[str, Any]:
    result = dict(document)
    result["authentication"] = {
        "schema_version": AUTHENTICATION_SCHEMA_VERSION,
        "algorithm": "hmac-sha256",
        "mac": _claim_mac(result, key),
    }
    return result


def _validate_claim_document(
    document: Any,
    *,
    archive_id: str,
    key: bytes | bytearray,
) -> dict[str, Any]:
    if not isinstance(document, Mapping):
        raise _fail("exact_human_approval_claim_document_invalid")
    result = dict(document)
    expected = {
        "schema_version",
        "approval_id",
        "archive_id",
        "context",
        "context_sha256",
        "approval_authority_sha256",
        "reviewer_claim_sha256",
        "reviewer_identity_authenticated",
        "interactive_intent",
        "approved_at",
        "started_at",
        "status",
        "finished_at",
        "failure_code",
        "authentication",
    }
    if set(result) != expected:
        raise _fail("exact_human_approval_claim_document_invalid")
    if result.get("schema_version") != CLAIM_SCHEMA_VERSION:
        raise _fail("exact_human_approval_claim_document_invalid")
    if type(result.get("approval_id")) is not str or _APPROVAL_ID_RE.fullmatch(
        result["approval_id"]
    ) is None:
        raise _fail("exact_human_approval_claim_document_invalid")
    if type(result.get("archive_id")) is not str or not hmac.compare_digest(
        result["archive_id"], archive_id
    ):
        raise _fail("exact_human_approval_claim_document_invalid")
    context = result.get("context")
    if not isinstance(context, Mapping) or set(context) != {
        "operation",
        "archive_identity_sha256",
        "plan_sha256",
        "target_binding_sha256",
        "reviewer_claim_sha256",
        "review_binding_codes",
        "warning_codes",
    }:
        raise _fail("exact_human_approval_claim_document_invalid")
    if context.get("operation") not in {
        operation.value for operation in ExactHumanApprovalOperation
    }:
        raise _fail("exact_human_approval_claim_document_invalid")
    for name, required in (("review_binding_codes", True), ("warning_codes", False)):
        codes = context.get(name)
        if type(codes) is not list or len(codes) > 32 or (required and not codes):
            raise _fail("exact_human_approval_claim_document_invalid")
        if any(
            type(code) is not str or _CONTEXT_CODE_RE.fullmatch(code) is None
            for code in codes
        ) or sorted(set(codes)) != codes:
            raise _fail("exact_human_approval_claim_document_invalid")
    for name in (
        "archive_identity_sha256",
        "plan_sha256",
        "target_binding_sha256",
        "reviewer_claim_sha256",
    ):
        if type(context.get(name)) is not str or _SHA256_RE.fullmatch(context[name]) is None:
            raise _fail("exact_human_approval_claim_document_invalid")
    for name in (
        "context_sha256",
        "approval_authority_sha256",
        "reviewer_claim_sha256",
    ):
        if type(result.get(name)) is not str or _SHA256_RE.fullmatch(result[name]) is None:
            raise _fail("exact_human_approval_claim_document_invalid")
    if not hmac.compare_digest(
        context["archive_identity_sha256"],
        exact_human_approval_archive_identity_sha256(archive_id),
    ) or not hmac.compare_digest(
        context["reviewer_claim_sha256"], result["reviewer_claim_sha256"]
    ):
        raise _fail("exact_human_approval_claim_document_invalid")
    if not hmac.compare_digest(
        result["context_sha256"],
        _sha256(_AUTHORITY_DOMAIN + _canonical_bytes(context)),
    ):
        raise _fail("exact_human_approval_claim_document_invalid")
    authority = {
        "approval_id": result["approval_id"],
        "archive_id": archive_id,
        "context_sha256": result["context_sha256"],
        "reviewer_claim_sha256": result["reviewer_claim_sha256"],
        "approved_at": result["approved_at"],
    }
    if not hmac.compare_digest(
        result["approval_authority_sha256"],
        _sha256(_AUTHORITY_DOMAIN + _canonical_bytes(authority)),
    ):
        raise _fail("exact_human_approval_claim_document_invalid")
    if result.get("reviewer_identity_authenticated") is not False:
        raise _fail("exact_human_approval_claim_document_invalid")
    if result.get("interactive_intent") != {
        "mechanism": "windows_task_dialog_checkbox_and_button",
        "confirmed": True,
    }:
        raise _fail("exact_human_approval_claim_document_invalid")
    status = result.get("status")
    if status not in {"started", "succeeded", "failed"}:
        raise _fail("exact_human_approval_claim_state_invalid")
    approved_at = _parse_timestamp(result.get("approved_at"))
    started_at = _parse_timestamp(result.get("started_at"))
    if approved_at != started_at:
        raise _fail("exact_human_approval_claim_document_invalid")
    if status == "started":
        if result.get("finished_at") is not None or result.get("failure_code") is not None:
            raise _fail("exact_human_approval_claim_state_invalid")
    elif status == "succeeded":
        if result.get("failure_code") is not None:
            raise _fail("exact_human_approval_claim_state_invalid")
        finished_at = _parse_timestamp(result.get("finished_at"))
        if finished_at < started_at:
            raise _fail("exact_human_approval_claim_state_invalid")
    elif (
        type(result.get("failure_code")) is not str
        or _FAILURE_CODE_RE.fullmatch(result["failure_code"]) is None
    ):
        raise _fail("exact_human_approval_claim_state_invalid")
    elif _parse_timestamp(result.get("finished_at")) < started_at:
        raise _fail("exact_human_approval_claim_state_invalid")
    authentication = result.get("authentication")
    if not isinstance(authentication, Mapping) or authentication != {
        "schema_version": AUTHENTICATION_SCHEMA_VERSION,
        "algorithm": "hmac-sha256",
        "mac": authentication.get("mac"),
    }:
        raise _fail("exact_human_approval_claim_authentication_invalid")
    mac = authentication.get("mac")
    if type(mac) is not str or not hmac.compare_digest(mac, _claim_mac(result, key)):
        raise _fail("exact_human_approval_claim_authentication_invalid")
    return result


def _read_bound_claim_bytes(
    path: Path,
    *,
    parent_binding: dict[str, Any],
) -> bytes:
    """Read one single-link claim through its already-bound parent."""

    if parent_binding.get("path") != path.parent:
        raise OSError("exact_human_approval_claim_parent_mismatch")
    parent_descriptor = parent_binding.get("descriptor")
    if isinstance(parent_descriptor, int):
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path.name, flags, dir_fd=parent_descriptor)
        try:
            info = os.fstat(descriptor)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_size > _MAX_CLAIM_BYTES
            ):
                raise OSError("exact_human_approval_claim_file_unsafe")
            chunks: list[bytes] = []
            remaining = info.st_size
            while remaining:
                chunk = os.read(descriptor, min(remaining, 65536))
                if not chunk:
                    raise OSError("exact_human_approval_claim_read_incomplete")
                chunks.append(chunk)
                remaining -= len(chunk)
            if os.read(descriptor, 1):
                raise OSError("exact_human_approval_claim_file_changed")
            return b"".join(chunks)
        finally:
            os.close(descriptor)

    named_info = os.lstat(path)
    if (
        _is_reparse(named_info)
        or not stat.S_ISREG(named_info.st_mode)
        or named_info.st_nlink != 1
        or named_info.st_size > _MAX_CLAIM_BYTES
    ):
        raise OSError("exact_human_approval_claim_file_unsafe")

    import ctypes
    from ctypes import wintypes

    class ByHandleFileInformation(ctypes.Structure):
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
        ctypes.POINTER(ByHandleFileInformation),
    ]
    get_information.restype = wintypes.BOOL
    read_file = kernel32.ReadFile
    read_file.argtypes = [
        wintypes.HANDLE,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    ]
    read_file.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    generic_read = 0x80000000
    file_share_read = 0x00000001
    open_existing = 3
    file_flag_open_reparse_point = 0x00200000
    file_attribute_directory = 0x00000010
    file_attribute_reparse_point = 0x00000400
    handle = create_file(
        str(path),
        generic_read,
        file_share_read,
        None,
        open_existing,
        file_flag_open_reparse_point,
        None,
    )
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        information = ByHandleFileInformation()
        if not get_information(handle, ctypes.byref(information)):
            raise ctypes.WinError(ctypes.get_last_error())
        size = (
            int(information.nFileSizeHigh) << 32
        ) | int(information.nFileSizeLow)
        if (
            information.dwFileAttributes
            & (file_attribute_directory | file_attribute_reparse_point)
            or information.nNumberOfLinks != 1
            or size > _MAX_CLAIM_BYTES
        ):
            raise OSError("exact_human_approval_claim_file_unsafe")
        chunks: list[bytes] = []
        remaining = size
        while remaining:
            chunk_size = min(remaining, 65536)
            buffer = ctypes.create_string_buffer(chunk_size)
            read_count = wintypes.DWORD()
            if not read_file(
                handle,
                buffer,
                chunk_size,
                ctypes.byref(read_count),
                None,
            ) or read_count.value == 0:
                raise OSError("exact_human_approval_claim_read_incomplete")
            chunks.append(buffer.raw[: read_count.value])
            remaining -= read_count.value
        return b"".join(chunks)
    finally:
        close_handle(handle)


def _read_claim(
    path: Path,
    *,
    archive_id: str,
    key: bytes | bytearray,
    bound_archive_root: Path | None = None,
    claim_parent_binding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        if (
            bound_archive_root is not None
            and claim_parent_binding is not None
        ):
            if claim_parent_binding.get("path") != path.parent:
                raise _fail("exact_human_approval_claim_path_unsafe")
            raw = _read_bound_claim_bytes(
                path,
                parent_binding=claim_parent_binding,
            )
        elif (
            bound_archive_root is not None
            or claim_parent_binding is not None
        ):
            raise _fail("exact_human_approval_claim_path_unsafe")
        else:
            info = os.lstat(path)
            if _is_reparse(info) or not stat.S_ISREG(info.st_mode):
                raise _fail("exact_human_approval_claim_path_unsafe")
            raw = path.read_bytes()
    except FileNotFoundError:
        raise _fail("exact_human_approval_claim_missing") from None
    except ExactHumanApprovalError:
        raise
    except OSError:
        raise _fail("exact_human_approval_claim_document_invalid") from None
    if len(raw) > _MAX_CLAIM_BYTES:
        raise _fail("exact_human_approval_claim_document_invalid")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise _fail("exact_human_approval_claim_document_invalid") from None
    document = _validate_claim_document(parsed, archive_id=archive_id, key=key)
    if not hmac.compare_digest(raw, _canonical_bytes(document)):
        raise _fail("exact_human_approval_claim_document_invalid")
    return document


def _exclusive_create(path: Path, raw: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags, 0o600)
        view = memoryview(raw)
        offset = 0
        while offset < len(view):
            written = os.write(descriptor, view[offset:])
            if written <= 0:
                raise OSError("short write")
            offset += written
        os.fsync(descriptor)
    except FileExistsError:
        raise _fail("exact_human_approval_claim_replayed") from None
    except ExactHumanApprovalError:
        raise
    except OSError:
        raise _fail("exact_human_approval_claim_commit_failed") from None
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _atomic_replace(path: Path, raw: bytes) -> None:
    temporary = path.with_name(path.name + ".tmp-" + secrets.token_hex(8))
    descriptor: int | None = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        descriptor = os.open(temporary, flags, 0o600)
        view = memoryview(raw)
        offset = 0
        while offset < len(view):
            written = os.write(descriptor, view[offset:])
            if written <= 0:
                raise OSError("short write")
            offset += written
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.replace(temporary, path)
    except OSError:
        raise _fail("exact_human_approval_finalization_failed") from None
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
class _ClaimedExactHumanApproval:
    """A durable started claim that can reach one terminal state exactly once."""

    _path: Path = field(repr=False)
    _archive_id: str = field(repr=False)
    _key: bytearray = field(repr=False)
    _approval_id: str
    _context_sha256: str
    _authority_sha256: str
    _clock: Callable[[], datetime] = field(repr=False)
    _bound_archive_root: Path | None = field(default=None, repr=False)
    _claim_parent_binding: dict[str, Any] | None = field(
        default=None,
        repr=False,
    )
    _status: str = field(default="started", init=False)
    _lock: Any = field(default_factory=threading.RLock, init=False, repr=False)

    def __repr__(self) -> str:
        return "<_ClaimedExactHumanApproval claim=authenticated bindings=sha256>"

    @property
    def approval_id(self) -> str:
        return self._approval_id

    @property
    def status(self) -> str:
        return self._status

    def public_reference(self) -> dict[str, Any]:
        return {
            "schema_version": REFERENCE_SCHEMA_VERSION,
            "approval_id": self._approval_id,
            "context_sha256": self._context_sha256,
            "approval_authority_sha256": self._authority_sha256,
            "one_use": True,
        }

    def public_summary(self) -> dict[str, Any]:
        return {
            "schema_version": SUMMARY_SCHEMA_VERSION,
            "approval_id": self._approval_id,
            "context_sha256": self._context_sha256,
            "approval_authority_sha256": self._authority_sha256,
            "claim_created": True,
            "one_use": True,
            "status": self._status,
            "reviewer_identity_authenticated": False,
        }

    def _assert_current_started(self) -> dict[str, Any]:
        if self._status != "started":
            raise _fail("exact_human_approval_claim_state_invalid")
        current = _read_claim(
            self._path,
            archive_id=self._archive_id,
            key=self._key,
            bound_archive_root=self._bound_archive_root,
            claim_parent_binding=self._claim_parent_binding,
        )
        if (
            current["status"] != "started"
            or not hmac.compare_digest(current["approval_id"], self._approval_id)
            or not hmac.compare_digest(
                current["context_sha256"], self._context_sha256
            )
            or not hmac.compare_digest(
                current["approval_authority_sha256"], self._authority_sha256
            )
        ):
            raise _fail("exact_human_approval_claim_state_invalid")
        return current

    @staticmethod
    def _approval_integrity_payload(payload: bytes) -> bytes:
        if (
            type(payload) is not bytes
            or not payload
            or len(payload) > APPROVAL_INTEGRITY_MAC_MAX_PAYLOAD_BYTES
        ):
            raise _fail("exact_human_approval_integrity_payload_invalid")
        return payload

    def approval_integrity_mac(self, payload: bytes) -> str:
        """Authenticate one bounded overlay payload in one fixed domain.

        The archive key remains inside this started claim.  Callers cannot
        select another domain, obtain the key, or use a terminal/tampered
        claim as a signing oracle.
        """

        raw = self._approval_integrity_payload(payload)
        with self._lock:
            self._assert_current_started()
            return "hmac-sha256:" + hmac.new(
                self._key,
                APPROVAL_INTEGRITY_MAC_DOMAIN + raw,
                hashlib.sha256,
            ).hexdigest()

    def approval_integrity_mac_matches(
        self,
        payload: bytes,
        expected_mac: str,
    ) -> bool:
        """Constant-time verification for the same fixed overlay domain."""

        raw = self._approval_integrity_payload(payload)
        if (
            type(expected_mac) is not str
            or re.fullmatch(r"hmac-sha256:[0-9a-f]{64}", expected_mac) is None
        ):
            raise _fail("exact_human_approval_integrity_mac_invalid")
        with self._lock:
            self._assert_current_started()
            actual = "hmac-sha256:" + hmac.new(
                self._key,
                APPROVAL_INTEGRITY_MAC_DOMAIN + raw,
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(actual, expected_mac)

    def approval_integrity_reference_status(
        self,
        reference: Mapping[str, Any],
        *,
        expected_operation: ExactHumanApprovalOperation,
        expected_plan_sha256: str,
        expected_target_binding_sha256: str,
    ) -> str | None:
        """Validate a content-free exact-reference projection for this archive.

        This narrowly scoped verifier lets the integrity writer recheck an
        existing overlay chain without receiving the archive key.  It returns
        only the fixed claim state and never returns a claim document.
        """

        if (
            not isinstance(reference, Mapping)
            or set(reference)
            != {
                "schema_version",
                "approval_id",
                "context_sha256",
                "approval_authority_sha256",
                "one_use",
            }
            or reference.get("schema_version") != REFERENCE_SCHEMA_VERSION
            or type(reference.get("approval_id")) is not str
            or _APPROVAL_ID_RE.fullmatch(reference["approval_id"]) is None
            or type(reference.get("context_sha256")) is not str
            or _SHA256_RE.fullmatch(reference["context_sha256"]) is None
            or type(reference.get("approval_authority_sha256")) is not str
            or _SHA256_RE.fullmatch(reference["approval_authority_sha256"])
            is None
            or reference.get("one_use") is not True
            or type(expected_operation) is not ExactHumanApprovalOperation
            or type(expected_plan_sha256) is not str
            or _SHA256_RE.fullmatch(expected_plan_sha256) is None
            or type(expected_target_binding_sha256) is not str
            or _SHA256_RE.fullmatch(expected_target_binding_sha256) is None
        ):
            raise _fail("exact_human_approval_integrity_reference_invalid")
        with self._lock:
            self._assert_current_started()
            try:
                candidate = _read_claim(
                    self._path.parent / f"{reference['approval_id']}.json",
                    archive_id=self._archive_id,
                    key=self._key,
                    bound_archive_root=self._bound_archive_root,
                    claim_parent_binding=self._claim_parent_binding,
                )
            except ExactHumanApprovalError:
                return None
            context = candidate.get("context")
            if not isinstance(context, Mapping) or not bool(
                hmac.compare_digest(
                    candidate["approval_id"], reference["approval_id"]
                )
                and hmac.compare_digest(
                    candidate["context_sha256"], reference["context_sha256"]
                )
                and hmac.compare_digest(
                    candidate["approval_authority_sha256"],
                    reference["approval_authority_sha256"],
                )
                and context.get("operation") == expected_operation.value
                and hmac.compare_digest(
                    context.get("archive_identity_sha256", ""),
                    exact_human_approval_archive_identity_sha256(
                        self._archive_id
                    ),
                )
                and hmac.compare_digest(
                    context.get("plan_sha256", ""), expected_plan_sha256
                )
                and hmac.compare_digest(
                    context.get("target_binding_sha256", ""),
                    expected_target_binding_sha256,
                )
            ):
                return None
            status = candidate.get("status")
            return status if status in {"started", "succeeded", "failed"} else None

    @staticmethod
    def _exact_human_approval_link_payload(payload: bytes) -> bytes:
        if (
            type(payload) is not bytes
            or not payload
            or len(payload) > APPROVAL_LINK_MAC_MAX_PAYLOAD_BYTES
        ):
            raise _fail("exact_human_approval_link_payload_invalid")
        return payload

    def exact_human_approval_link_mac(self, payload: bytes) -> str:
        """Authenticate one bounded approval-link payload in its fixed domain."""

        raw = self._exact_human_approval_link_payload(payload)
        with self._lock:
            self._assert_current_started()
            return "hmac-sha256:" + hmac.new(
                self._key,
                APPROVAL_LINK_MAC_DOMAIN + raw,
                hashlib.sha256,
            ).hexdigest()

    def exact_human_approval_link_mac_matches(
        self,
        payload: bytes,
        expected_mac: str,
    ) -> bool:
        """Constant-time verification for the fixed approval-link domain."""

        raw = self._exact_human_approval_link_payload(payload)
        if (
            type(expected_mac) is not str
            or re.fullmatch(r"hmac-sha256:[0-9a-f]{64}", expected_mac) is None
        ):
            raise _fail("exact_human_approval_link_mac_invalid")
        with self._lock:
            self._assert_current_started()
            actual = "hmac-sha256:" + hmac.new(
                self._key,
                APPROVAL_LINK_MAC_DOMAIN + raw,
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(actual, expected_mac)

    def exact_human_approval_link_reference_status(
        self,
        reference: Mapping[str, Any],
        *,
        expected_operation: ExactHumanApprovalOperation,
        expected_plan_sha256: str,
        expected_target_binding_sha256: str,
    ) -> str | None:
        """Return only the fixed state of one archive-local link reference."""

        return self.approval_integrity_reference_status(
            reference,
            expected_operation=expected_operation,
            expected_plan_sha256=expected_plan_sha256,
            expected_target_binding_sha256=expected_target_binding_sha256,
        )

    def assert_ready_for_context(
        self, context: ExactHumanApprovalContext
    ) -> dict[str, Any]:
        """Reauthenticate the started claim and one exact context before a write."""

        if type(context) is not ExactHumanApprovalContext:
            raise _fail("exact_human_approval_claim_state_invalid")
        expected_context = exact_human_approval_context_sha256(context)
        if not hmac.compare_digest(expected_context, self._context_sha256):
            raise _fail("exact_human_approval_binding_mismatch")
        with self._lock:
            self._assert_current_started()
            return self.public_reference()

    def _finalize(self, *, status: str, failure_code: str | None) -> None:
        with self._lock:
            if status not in {"succeeded", "failed"}:
                raise _fail("exact_human_approval_claim_state_invalid")
            if status == "failed" and (
                type(failure_code) is not str
                or _FAILURE_CODE_RE.fullmatch(failure_code) is None
            ):
                raise _fail("exact_human_approval_failure_code_invalid")
            if status == "succeeded" and failure_code is not None:
                raise _fail("exact_human_approval_failure_code_invalid")
            current = self._assert_current_started()
            finalized = dict(current)
            finalized.update(
                {
                    "status": status,
                    "finished_at": _timestamp(_now(self._clock)),
                    "failure_code": failure_code,
                }
            )
            finalized = _authenticated(finalized, self._key)
            _validate_claim_document(
                finalized, archive_id=self._archive_id, key=self._key
            )
            finalized_raw = _canonical_bytes(finalized)
            if (
                self._bound_archive_root is not None
                and self._claim_parent_binding is not None
            ):
                from . import archive_services

                current_raw = _canonical_bytes(current)
                transaction_sha256 = "sha256:" + hashlib.sha256(
                    b"wom-kit/exact-human-approval-claim-finalize/v0.1\x00"
                    + current_raw
                    + finalized_raw
                ).hexdigest()
                try:
                    archive_services._replace_regular_file_bytes_compare_and_swap(
                        self._bound_archive_root,
                        self._path,
                        expected_bytes=current_raw,
                        replacement_bytes=finalized_raw,
                        transaction_sha256=transaction_sha256,
                        swap_suffix=".exact-human-approval-claim.swap",
                        max_bytes=_MAX_CLAIM_BYTES,
                        error_prefix="exact_human_approval",
                    )
                except OSError:
                    raise _fail(
                        "exact_human_approval_finalization_failed"
                    ) from None
            else:
                _atomic_replace(self._path, finalized_raw)
            reread = _read_claim(
                self._path,
                archive_id=self._archive_id,
                key=self._key,
                bound_archive_root=self._bound_archive_root,
                claim_parent_binding=self._claim_parent_binding,
            )
            if reread["status"] != status:
                raise _fail("exact_human_approval_finalization_failed")
            self._status = status

    def finalize_succeeded(self) -> None:
        self._finalize(status="succeeded", failure_code=None)

    def finalize_failed(self, failure_code: str) -> None:
        self._finalize(status="failed", failure_code=failure_code)

    def close(self) -> None:
        with self._lock:
            for index in range(len(self._key)):
                self._key[index] = 0


def _claim_exact_human_approval_core(
    archive_root: Path | str,
    context: ExactHumanApprovalContext,
    decision: _ExactHumanApprovalDecision,
    receipt_authentication_key: bytes | bytearray | memoryview,
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    random_hex: Callable[[int], str] = secrets.token_hex,
    bound_archive_root: Path | None = None,
    claim_parent_binding: dict[str, Any] | None = None,
) -> _ClaimedExactHumanApproval:
    """Persist an authenticated started claim after an exact live decision."""

    root, archive_id = _archive_identity(archive_root)
    if type(context) is not ExactHumanApprovalContext:
        raise _fail("exact_human_approval_binding_mismatch")
    if (
        type(decision) is not _ExactHumanApprovalDecision
        or decision.approved is not True
        or decision.synthetic_acknowledged is not False
        or decision.reason_code != "exact_human_approval_approved"
    ):
        raise _fail("exact_human_approval_decision_required")
    if not (
        hmac.compare_digest(decision.plan_sha256, context.plan_sha256)
        and hmac.compare_digest(
            decision.target_binding_sha256, context.target_binding_sha256
        )
    ):
        raise _fail("exact_human_approval_binding_mismatch")
    if not hmac.compare_digest(
        context.archive_identity_sha256,
        exact_human_approval_archive_identity_sha256(archive_id),
    ):
        raise _fail("exact_human_approval_binding_mismatch")
    key = _validated_key(receipt_authentication_key)
    try:
        started = _now(clock)
        try:
            suffix = random_hex(16)
        except BaseException:
            raise _fail("exact_human_approval_claim_commit_failed") from None
        approval_id = "approval_" + suffix
        if _APPROVAL_ID_RE.fullmatch(approval_id) is None:
            raise _fail("exact_human_approval_claim_commit_failed")
        context_document = _context_document(context)
        context_sha256 = exact_human_approval_context_sha256(context)
        reviewer_claim_sha256 = context_document["reviewer_claim_sha256"]
        approved_at = _timestamp(started)
        authority = {
            "approval_id": approval_id,
            "archive_id": archive_id,
            "context_sha256": context_sha256,
            "reviewer_claim_sha256": reviewer_claim_sha256,
            "approved_at": approved_at,
        }
        authority_sha256 = _sha256(
            _AUTHORITY_DOMAIN + _canonical_bytes(authority)
        )
        document = _authenticated(
            {
                "schema_version": CLAIM_SCHEMA_VERSION,
                "approval_id": approval_id,
                "archive_id": archive_id,
                "context": context_document,
                "context_sha256": context_sha256,
                "approval_authority_sha256": authority_sha256,
                "reviewer_claim_sha256": reviewer_claim_sha256,
                "reviewer_identity_authenticated": False,
                "interactive_intent": {
                    "mechanism": "windows_task_dialog_checkbox_and_button",
                    "confirmed": True,
                },
                "approved_at": approved_at,
                "started_at": approved_at,
                "status": "started",
                "finished_at": None,
                "failure_code": None,
            },
            key,
        )
        _validate_claim_document(document, archive_id=archive_id, key=key)
        if (
            bound_archive_root is not None
            and claim_parent_binding is not None
        ):
            claims_root = root.joinpath(*Path(CLAIMS_RELATIVE_ROOT).parts)
            if (
                root != bound_archive_root
                or claim_parent_binding.get("path") != claims_root
            ):
                raise _fail("exact_human_approval_claim_path_unsafe")
        elif (
            bound_archive_root is not None
            or claim_parent_binding is not None
        ):
            raise _fail("exact_human_approval_claim_path_unsafe")
        else:
            claims_root = _claims_root(root, create=True)
        claim_path = claims_root / f"{approval_id}.json"
        if claim_parent_binding is not None:
            from . import archive_services

            try:
                archive_services._write_activity_group_bytes_new_file_bound(
                    claim_parent_binding,
                    claim_path,
                    _canonical_bytes(document),
                )
            except FileExistsError:
                raise _fail("exact_human_approval_claim_replayed") from None
            except OSError:
                raise _fail("exact_human_approval_claim_commit_failed") from None
        else:
            _exclusive_create(claim_path, _canonical_bytes(document))
        reread = _read_claim(
            claim_path,
            archive_id=archive_id,
            key=key,
            bound_archive_root=bound_archive_root,
            claim_parent_binding=claim_parent_binding,
        )
        if reread["status"] != "started":
            raise _fail("exact_human_approval_claim_commit_failed")
        return _ClaimedExactHumanApproval(
            _path=claim_path,
            _archive_id=archive_id,
            _key=key,
            _approval_id=approval_id,
            _context_sha256=context_sha256,
            _authority_sha256=authority_sha256,
            _clock=clock,
            _bound_archive_root=bound_archive_root,
            _claim_parent_binding=claim_parent_binding,
        )
    except BaseException:
        for index in range(len(key)):
            key[index] = 0
        raise


__all__ = [
    "APPROVAL_INTEGRITY_MAC_DOMAIN",
    "APPROVAL_INTEGRITY_MAC_MAX_PAYLOAD_BYTES",
    "APPROVAL_LINK_MAC_DOMAIN",
    "APPROVAL_LINK_MAC_MAX_PAYLOAD_BYTES",
    "AUTHENTICATION_SCHEMA_VERSION",
    "CLAIMS_RELATIVE_ROOT",
    "CLAIM_SCHEMA_VERSION",
    "ExactHumanApprovalError",
    "REFERENCE_SCHEMA_VERSION",
    "SUMMARY_SCHEMA_VERSION",
    "exact_human_approval_archive_identity_sha256",
    "exact_human_approval_context_sha256",
]
