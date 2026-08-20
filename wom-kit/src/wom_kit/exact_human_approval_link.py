"""Create-only correlation receipts for exact-human-approved legacy writes.

Some older operation receipts cannot safely grow a new field without breaking
their byte-for-byte replay contract.  This module publishes a separate,
content-free link keyed by the exact approval id.  The link binds the public
approval reference to the exact operation plan, target set, and immutable
source operation receipt.

The link never upgrades a historical write merely because a human reviewed an
idempotent replay later.  Only ``effect="created"`` is positive evidence that
the original operation happened under this approval; ``already_present_exact``
records review continuity without changing the historical provenance.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import stat
from pathlib import Path
from typing import Any, Mapping

import yaml

from .exact_human_approval import (
    APPROVAL_LINK_MAC_DOMAIN,
    CLAIMS_RELATIVE_ROOT,
    REFERENCE_SCHEMA_VERSION,
    _ClaimedExactHumanApproval,
    ExactHumanApprovalError,
    _read_claim as _read_exact_human_approval_claim,
    exact_human_approval_archive_identity_sha256,
)
from .exact_human_approval_windows import (
    ExactHumanApprovalContext,
    ExactHumanApprovalOperation,
)


LINK_RECEIPT_SCHEMA_VERSION = (
    "wom-kit/exact-human-approval-link-receipt/v0.1"
)
LINK_RESULT_SCHEMA_VERSION = "wom-kit/exact-human-approval-link-result/v0.1"
LINK_AUTHENTICATION_SCHEMA_VERSION = (
    "wom-kit/exact-human-approval-link-authentication/v0.1"
)
LINKS_RELATIVE_ROOT = "receipts/exact-human-approvals/links"

LINK_OPERATIONS = frozenset(
    {
        ExactHumanApprovalOperation.create_draft.value,
        ExactHumanApprovalOperation.source_fidelity_session_evidence.value,
    }
)
LINK_EFFECTS = frozenset({"created", "already_present_exact"})

_LINK_DIGEST_DOMAIN = b"wom-kit/exact-human-approval-link-receipt/v0.1\x00"
_LINK_MAC_DOMAIN = APPROVAL_LINK_MAC_DOMAIN
_APPROVAL_ID_RE = re.compile(r"^approval_[0-9a-f]{32}$")
_ARCHIVE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_HMAC_RE = re.compile(r"^hmac-sha256:[0-9a-f]{64}$")
_CREATE_DRAFT_RECEIPT_RE = re.compile(
    r"^receipts/source-fidelity/drafts/[0-9a-f]{64}\.json$"
)
_SESSION_EVIDENCE_RECEIPT_RE = re.compile(
    r"^receipts/source-fidelity/session-evidence/[0-9a-f]{64}\.json$"
)
_MAX_ARCHIVE_MARKER_BYTES = 64 * 1024
_MAX_SOURCE_RECEIPT_BYTES = 4 * 1024 * 1024
_MAX_LINK_RECEIPT_BYTES = 32 * 1024
_KEY_BYTES = 32


class ExactHumanApprovalLinkError(RuntimeError):
    """A fixed-code error that never includes paths or receipt content."""

    _CODES = {
        "exact_human_approval_link_archive_invalid",
        "exact_human_approval_link_argument_invalid",
        "exact_human_approval_link_approval_reference_invalid",
        "exact_human_approval_link_operation_invalid",
        "exact_human_approval_link_binding_invalid",
        "exact_human_approval_link_source_receipt_ref_invalid",
        "exact_human_approval_link_source_receipt_missing",
        "exact_human_approval_link_source_receipt_unsafe",
        "exact_human_approval_link_source_receipt_sha256_mismatch",
        "exact_human_approval_link_path_unsafe",
        "exact_human_approval_link_document_invalid",
        "exact_human_approval_link_digest_invalid",
        "exact_human_approval_link_missing",
        "exact_human_approval_link_replayed",
        "exact_human_approval_link_commit_failed",
        "exact_human_approval_link_binding_mismatch",
        "exact_human_approval_link_key_invalid",
        "exact_human_approval_link_authentication_invalid",
        "exact_human_approval_link_approval_claim_invalid",
    }

    def __init__(self, code: str) -> None:
        self.code = (
            code
            if code in self._CODES
            else "exact_human_approval_link_document_invalid"
        )
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"ExactHumanApprovalLinkError({self.code!r})"


def _fail(code: str) -> ExactHumanApprovalLinkError:
    return ExactHumanApprovalLinkError(code)


def _canonical_bytes(document: Mapping[str, Any]) -> bytes:
    try:
        raw = json.dumps(
            dict(document),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii") + b"\n"
    except (TypeError, ValueError, UnicodeError):
        raise _fail("exact_human_approval_link_document_invalid") from None
    if len(raw) > _MAX_LINK_RECEIPT_BYTES:
        raise _fail("exact_human_approval_link_document_invalid")
    return raw


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _link_digest(document: Mapping[str, Any]) -> str:
    payload = dict(document)
    payload.pop("link_sha256", None)
    payload.pop("authentication", None)
    return _sha256(_LINK_DIGEST_DOMAIN + _canonical_bytes(payload))


def _link_mac_payload(document: Mapping[str, Any]) -> bytes:
    payload = dict(document)
    payload.pop("authentication", None)
    return _canonical_bytes(payload)


def _link_mac(
    document: Mapping[str, Any],
    key: bytes | bytearray,
) -> str:
    return "hmac-sha256:" + hmac.new(
        key,
        _LINK_MAC_DOMAIN + _link_mac_payload(document),
        hashlib.sha256,
    ).hexdigest()


def _validated_key(value: bytes | bytearray | memoryview) -> bytearray:
    try:
        raw = bytes(value)
    except (TypeError, ValueError):
        raise _fail("exact_human_approval_link_key_invalid") from None
    if len(raw) != _KEY_BYTES:
        raise _fail("exact_human_approval_link_key_invalid")
    return bytearray(raw)


def _wipe(value: bytearray) -> None:
    for index in range(len(value)):
        value[index] = 0


def _is_reparse(info: os.stat_result) -> bool:
    return bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _same_file(left: os.stat_result, right: os.stat_result) -> bool:
    return bool(
        stat.S_IFMT(left.st_mode) == stat.S_IFMT(right.st_mode)
        and left.st_ino != 0
        and right.st_ino != 0
        and left.st_dev == right.st_dev
        and left.st_ino == right.st_ino
    )


def _safe_directory(path: Path, *, create: bool) -> os.stat_result:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        if not create:
            raise _fail("exact_human_approval_link_path_unsafe") from None
        try:
            path.mkdir()
        except FileExistsError:
            pass
        except OSError:
            raise _fail("exact_human_approval_link_path_unsafe") from None
        try:
            info = os.lstat(path)
        except OSError:
            raise _fail("exact_human_approval_link_path_unsafe") from None
    except OSError:
        raise _fail("exact_human_approval_link_path_unsafe") from None
    if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
        raise _fail("exact_human_approval_link_path_unsafe")
    return info


def _archive_root(archive_root: Path | str) -> tuple[Path, str]:
    try:
        root = Path(archive_root).resolve(strict=True)
        root_info = os.lstat(root)
    except (OSError, RuntimeError, TypeError, ValueError):
        raise _fail("exact_human_approval_link_archive_invalid") from None
    if _is_reparse(root_info) or not stat.S_ISDIR(root_info.st_mode):
        raise _fail("exact_human_approval_link_archive_invalid")
    marker = root / "archive.yml"
    try:
        marker_info = os.lstat(marker)
        if _is_reparse(marker_info) or not stat.S_ISREG(marker_info.st_mode):
            raise _fail("exact_human_approval_link_archive_invalid")
        if marker_info.st_size > _MAX_ARCHIVE_MARKER_BYTES:
            raise _fail("exact_human_approval_link_archive_invalid")
        document = yaml.safe_load(marker.read_text(encoding="utf-8"))
    except ExactHumanApprovalLinkError:
        raise
    except (OSError, UnicodeError, yaml.YAMLError):
        raise _fail("exact_human_approval_link_archive_invalid") from None
    archive_id = document.get("archive_id") if isinstance(document, Mapping) else None
    if type(archive_id) is not str or _ARCHIVE_ID_RE.fullmatch(archive_id) is None:
        raise _fail("exact_human_approval_link_archive_invalid")
    return root, archive_id


def _directory_chain(
    root: Path,
    parts: tuple[str, ...],
    *,
    create: bool,
) -> tuple[Path, os.stat_result]:
    current = root
    info = os.lstat(root)
    for part in parts:
        current = current / part
        info = _safe_directory(current, create=create)
    return current, info


def _links_root(root: Path, *, create: bool) -> tuple[Path, os.stat_result]:
    return _directory_chain(
        root,
        ("receipts", "exact-human-approvals", "links"),
        create=create,
    )


def _operation(value: Any) -> str:
    if type(value) is ExactHumanApprovalOperation:
        operation = value.value
    elif type(value) is str:
        operation = value
    else:
        raise _fail("exact_human_approval_link_operation_invalid")
    if operation not in LINK_OPERATIONS:
        raise _fail("exact_human_approval_link_operation_invalid")
    return operation


def _sha_reference(value: Any) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise _fail("exact_human_approval_link_binding_invalid")
    return value


def _approval_reference(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise _fail("exact_human_approval_link_approval_reference_invalid")
    reference = dict(value)
    if set(reference) != {
        "schema_version",
        "approval_id",
        "context_sha256",
        "approval_authority_sha256",
        "one_use",
    }:
        raise _fail("exact_human_approval_link_approval_reference_invalid")
    if reference.get("schema_version") != REFERENCE_SCHEMA_VERSION:
        raise _fail("exact_human_approval_link_approval_reference_invalid")
    approval_id = reference.get("approval_id")
    if type(approval_id) is not str or _APPROVAL_ID_RE.fullmatch(approval_id) is None:
        raise _fail("exact_human_approval_link_approval_reference_invalid")
    for name in ("context_sha256", "approval_authority_sha256"):
        if type(reference.get(name)) is not str or _SHA256_RE.fullmatch(
            reference[name]
        ) is None:
            raise _fail("exact_human_approval_link_approval_reference_invalid")
    if reference.get("one_use") is not True:
        raise _fail("exact_human_approval_link_approval_reference_invalid")
    return reference


def _require_succeeded_claim(
    root: Path,
    *,
    archive_id: str,
    reference: Mapping[str, Any],
    operation: str,
    plan_sha256: str,
    target_binding_sha256: str,
    key: bytearray,
) -> None:
    try:
        claims, _claims_info = _directory_chain(
            root,
            tuple(CLAIMS_RELATIVE_ROOT.split("/")),
            create=False,
        )
        claim = _read_exact_human_approval_claim(
            claims / f"{reference['approval_id']}.json",
            archive_id=archive_id,
            key=key,
        )
    except (ExactHumanApprovalLinkError, ExactHumanApprovalError):
        raise _fail("exact_human_approval_link_approval_claim_invalid") from None
    context = claim.get("context")
    if not isinstance(context, Mapping) or not bool(
        claim.get("status") == "succeeded"
        and hmac.compare_digest(
            claim.get("approval_id", ""), reference["approval_id"]
        )
        and hmac.compare_digest(
            claim.get("context_sha256", ""), reference["context_sha256"]
        )
        and hmac.compare_digest(
            claim.get("approval_authority_sha256", ""),
            reference["approval_authority_sha256"],
        )
        and context.get("operation") == operation
        and hmac.compare_digest(
            context.get("plan_sha256", ""), plan_sha256
        )
        and hmac.compare_digest(
            context.get("target_binding_sha256", ""),
            target_binding_sha256,
        )
    ):
        raise _fail("exact_human_approval_link_approval_claim_invalid")


def _source_receipt_relative(value: Any, operation: str) -> str:
    if isinstance(value, Path):
        value = value.as_posix()
    if (
        type(value) is not str
        or not value
        or "\\" in value
        or "\x00" in value
        or value.startswith("/")
        or ":" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise _fail("exact_human_approval_link_source_receipt_ref_invalid")
    expected = (
        _CREATE_DRAFT_RECEIPT_RE
        if operation == ExactHumanApprovalOperation.create_draft.value
        else _SESSION_EVIDENCE_RECEIPT_RE
    )
    if expected.fullmatch(value) is None:
        raise _fail("exact_human_approval_link_source_receipt_ref_invalid")
    return value


def _read_stable_regular(
    path: Path,
    *,
    maximum: int,
    missing_code: str,
    unsafe_code: str,
) -> bytes:
    descriptor: int | None = None
    try:
        before = os.lstat(path)
        if _is_reparse(before) or not stat.S_ISREG(before.st_mode):
            raise _fail(unsafe_code)
        if before.st_size < 0 or before.st_size > maximum:
            raise _fail(unsafe_code)
        flags = os.O_RDONLY
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if (
            _is_reparse(opened)
            or not stat.S_ISREG(opened.st_mode)
            or not _same_file(before, opened)
        ):
            raise _fail(unsafe_code)
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(64 * 1024, maximum + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum:
                raise _fail(unsafe_code)
        after_open = os.fstat(descriptor)
        if (
            not _same_file(opened, after_open)
            or opened.st_size != after_open.st_size
            or getattr(opened, "st_mtime_ns", None)
            != getattr(after_open, "st_mtime_ns", None)
            or total != after_open.st_size
        ):
            raise _fail(unsafe_code)
        os.close(descriptor)
        descriptor = None
        after_path = os.lstat(path)
        if (
            _is_reparse(after_path)
            or not stat.S_ISREG(after_path.st_mode)
            or not _same_file(after_open, after_path)
            or after_open.st_size != after_path.st_size
            or getattr(after_open, "st_mtime_ns", None)
            != getattr(after_path, "st_mtime_ns", None)
        ):
            raise _fail(unsafe_code)
        return b"".join(chunks)
    except FileNotFoundError:
        raise _fail(missing_code) from None
    except ExactHumanApprovalLinkError:
        raise
    except OSError:
        raise _fail(unsafe_code) from None
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _source_receipt(
    root: Path,
    *,
    operation: str,
    relative: Any,
    expected_sha256: Any,
) -> tuple[str, str]:
    normalized = _source_receipt_relative(relative, operation)
    digest = _sha_reference(expected_sha256)
    parts = normalized.split("/")
    directory, _directory_info = _directory_chain(
        root, tuple(parts[:-1]), create=False
    )
    raw = _read_stable_regular(
        directory / parts[-1],
        maximum=_MAX_SOURCE_RECEIPT_BYTES,
        missing_code="exact_human_approval_link_source_receipt_missing",
        unsafe_code="exact_human_approval_link_source_receipt_unsafe",
    )
    if not hmac.compare_digest(_sha256(raw), digest):
        raise _fail("exact_human_approval_link_source_receipt_sha256_mismatch")
    return normalized, digest


def _build_unsigned_document(
    *,
    exact_human_approval: Mapping[str, Any],
    operation: str,
    plan_sha256: str,
    target_binding_sha256: str,
    source_receipt_relative: str,
    source_receipt_sha256: str,
    effect: str,
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "schema_version": LINK_RECEIPT_SCHEMA_VERSION,
        "exact_human_approval": dict(exact_human_approval),
        "operation": operation,
        "plan_sha256": plan_sha256,
        "target_binding_sha256": target_binding_sha256,
        "source_operation_receipt": {
            "relative_path": source_receipt_relative,
            "sha256": source_receipt_sha256,
        },
        "effect": effect,
        "original_operation_evidence_upgraded": effect == "created",
        "content_contract": {
            "private_content_stored": False,
            "absolute_path_stored": False,
            "reviewer_claim_stored": False,
            "source_operation_receipt_content_stored": False,
        },
    }
    document["link_sha256"] = _link_digest(document)
    return document


def _build_document(
    *,
    exact_human_approval: Mapping[str, Any],
    operation: str,
    plan_sha256: str,
    target_binding_sha256: str,
    source_receipt_relative: str,
    source_receipt_sha256: str,
    effect: str,
    approval_claim: _ClaimedExactHumanApproval,
) -> dict[str, Any]:
    document = _build_unsigned_document(
        exact_human_approval=exact_human_approval,
        operation=operation,
        plan_sha256=plan_sha256,
        target_binding_sha256=target_binding_sha256,
        source_receipt_relative=source_receipt_relative,
        source_receipt_sha256=source_receipt_sha256,
        effect=effect,
    )
    try:
        mac = approval_claim.exact_human_approval_link_mac(
            _link_mac_payload(document)
        )
    except ExactHumanApprovalError:
        raise _fail("exact_human_approval_link_approval_claim_invalid") from None
    document["authentication"] = {
        "schema_version": LINK_AUTHENTICATION_SCHEMA_VERSION,
        "algorithm": "hmac-sha256",
        "mac": mac,
    }
    return document


def _validate_document(
    document: Any,
    *,
    key: bytearray | None = None,
    approval_claim: _ClaimedExactHumanApproval | None = None,
) -> dict[str, Any]:
    if (key is None) == (approval_claim is None):
        raise _fail("exact_human_approval_link_authentication_invalid")
    if not isinstance(document, Mapping):
        raise _fail("exact_human_approval_link_document_invalid")
    result = dict(document)
    if set(result) != {
        "schema_version",
        "exact_human_approval",
        "operation",
        "plan_sha256",
        "target_binding_sha256",
        "source_operation_receipt",
        "effect",
        "original_operation_evidence_upgraded",
        "content_contract",
        "link_sha256",
        "authentication",
    }:
        raise _fail("exact_human_approval_link_document_invalid")
    if result.get("schema_version") != LINK_RECEIPT_SCHEMA_VERSION:
        raise _fail("exact_human_approval_link_document_invalid")
    reference = _approval_reference(result.get("exact_human_approval"))
    operation = _operation(result.get("operation"))
    plan_sha256 = _sha_reference(result.get("plan_sha256"))
    target_binding_sha256 = _sha_reference(result.get("target_binding_sha256"))
    source = result.get("source_operation_receipt")
    if not isinstance(source, Mapping) or set(source) != {"relative_path", "sha256"}:
        raise _fail("exact_human_approval_link_document_invalid")
    source_relative = _source_receipt_relative(source.get("relative_path"), operation)
    source_sha256 = _sha_reference(source.get("sha256"))
    effect = result.get("effect")
    if effect not in LINK_EFFECTS:
        raise _fail("exact_human_approval_link_document_invalid")
    if result.get("original_operation_evidence_upgraded") is not (
        effect == "created"
    ):
        raise _fail("exact_human_approval_link_document_invalid")
    if result.get("content_contract") != {
        "private_content_stored": False,
        "absolute_path_stored": False,
        "reviewer_claim_stored": False,
        "source_operation_receipt_content_stored": False,
    }:
        raise _fail("exact_human_approval_link_document_invalid")
    link_sha256 = result.get("link_sha256")
    if type(link_sha256) is not str or _SHA256_RE.fullmatch(link_sha256) is None:
        raise _fail("exact_human_approval_link_digest_invalid")
    if not hmac.compare_digest(link_sha256, _link_digest(result)):
        raise _fail("exact_human_approval_link_digest_invalid")
    authentication = result.get("authentication")
    if not isinstance(authentication, Mapping) or set(authentication) != {
        "schema_version",
        "algorithm",
        "mac",
    }:
        raise _fail("exact_human_approval_link_authentication_invalid")
    mac = authentication.get("mac")
    if (
        authentication.get("schema_version")
        != LINK_AUTHENTICATION_SCHEMA_VERSION
        or authentication.get("algorithm") != "hmac-sha256"
        or type(mac) is not str
        or _HMAC_RE.fullmatch(mac) is None
    ):
        raise _fail("exact_human_approval_link_authentication_invalid")
    if key is not None:
        if not hmac.compare_digest(mac, _link_mac(result, key)):
            raise _fail("exact_human_approval_link_authentication_invalid")
    else:
        try:
            authenticated = approval_claim.exact_human_approval_link_mac_matches(
                _link_mac_payload(result), mac
            )
            reference_status = (
                approval_claim.exact_human_approval_link_reference_status(
                    reference,
                    expected_operation=ExactHumanApprovalOperation(operation),
                    expected_plan_sha256=plan_sha256,
                    expected_target_binding_sha256=target_binding_sha256,
                )
            )
        except (ExactHumanApprovalError, ValueError):
            raise _fail("exact_human_approval_link_approval_claim_invalid") from None
        if not authenticated:
            raise _fail("exact_human_approval_link_authentication_invalid")
        if reference_status != "started":
            raise _fail("exact_human_approval_link_approval_claim_invalid")
    # Rebuild the normalized value so callers never observe Mapping subclasses.
    result["exact_human_approval"] = reference
    result["operation"] = operation
    result["plan_sha256"] = plan_sha256
    result["target_binding_sha256"] = target_binding_sha256
    result["source_operation_receipt"] = {
        "relative_path": source_relative,
        "sha256": source_sha256,
    }
    return result


def _exclusive_write(path: Path, raw: bytes) -> None:
    descriptor: int | None = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
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
        raise _fail("exact_human_approval_link_commit_failed") from None
    except ExactHumanApprovalLinkError:
        raise
    except OSError:
        raise _fail("exact_human_approval_link_commit_failed") from None
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _publish_create_only(
    directory: Path,
    directory_info: os.stat_result,
    *,
    approval_id: str,
    document: Mapping[str, Any],
    random_hex: Any,
) -> Path:
    final = directory / f"{approval_id}.json"
    try:
        existing = os.lstat(final)
    except FileNotFoundError:
        pass
    except OSError:
        raise _fail("exact_human_approval_link_path_unsafe") from None
    else:
        if _is_reparse(existing) or not stat.S_ISREG(existing.st_mode):
            raise _fail("exact_human_approval_link_path_unsafe")
        raise _fail("exact_human_approval_link_replayed")
    try:
        suffix = random_hex(8)
    except BaseException:
        raise _fail("exact_human_approval_link_commit_failed") from None
    if type(suffix) is not str or re.fullmatch(r"[0-9a-f]{16}", suffix) is None:
        raise _fail("exact_human_approval_link_commit_failed")
    temporary = directory / f".{approval_id}.tmp-{suffix}"
    raw = _canonical_bytes(document)
    linked = False
    try:
        _exclusive_write(temporary, raw)
        try:
            os.link(temporary, final)
            linked = True
        except FileExistsError:
            raise _fail("exact_human_approval_link_replayed") from None
        except OSError:
            raise _fail("exact_human_approval_link_commit_failed") from None
        current_directory = os.lstat(directory)
        if (
            _is_reparse(current_directory)
            or not stat.S_ISDIR(current_directory.st_mode)
            or not _same_file(directory_info, current_directory)
        ):
            raise _fail("exact_human_approval_link_path_unsafe")
        committed = _read_stable_regular(
            final,
            maximum=_MAX_LINK_RECEIPT_BYTES,
            missing_code="exact_human_approval_link_commit_failed",
            unsafe_code="exact_human_approval_link_commit_failed",
        )
        if not hmac.compare_digest(committed, raw):
            raise _fail("exact_human_approval_link_commit_failed")
        return final
    finally:
        try:
            temporary_info = os.lstat(temporary)
            if not _is_reparse(temporary_info) and stat.S_ISREG(
                temporary_info.st_mode
            ):
                temporary.unlink()
        except OSError:
            pass
        if not linked:
            # A hard link that became visible before an uncertain error is a
            # committed append.  Never erase it during cleanup.
            try:
                final_info = os.lstat(final)
                if _is_reparse(final_info) or not stat.S_ISREG(final_info.st_mode):
                    pass
            except OSError:
                pass


def _read_link(
    root: Path,
    *,
    archive_id: str,
    approval_id: str,
    key: bytearray,
) -> tuple[dict[str, Any], bytes, str]:
    if type(approval_id) is not str or _APPROVAL_ID_RE.fullmatch(approval_id) is None:
        raise _fail("exact_human_approval_link_argument_invalid")
    directory, _directory_info = _links_root(root, create=False)
    path = directory / f"{approval_id}.json"
    raw = _read_stable_regular(
        path,
        maximum=_MAX_LINK_RECEIPT_BYTES,
        missing_code="exact_human_approval_link_missing",
        unsafe_code="exact_human_approval_link_path_unsafe",
    )
    try:
        parsed = json.loads(raw.decode("ascii"))
    except (UnicodeError, json.JSONDecodeError):
        raise _fail("exact_human_approval_link_document_invalid") from None
    document = _validate_document(parsed, key=key)
    if not hmac.compare_digest(raw, _canonical_bytes(document)):
        raise _fail("exact_human_approval_link_document_invalid")
    reference = document["exact_human_approval"]
    if not hmac.compare_digest(reference["approval_id"], approval_id):
        raise _fail("exact_human_approval_link_binding_mismatch")
    source = document["source_operation_receipt"]
    _source_receipt(
        root,
        operation=document["operation"],
        relative=source["relative_path"],
        expected_sha256=source["sha256"],
    )
    _require_succeeded_claim(
        root,
        archive_id=archive_id,
        reference=reference,
        operation=document["operation"],
        plan_sha256=document["plan_sha256"],
        target_binding_sha256=document["target_binding_sha256"],
        key=key,
    )
    return document, raw, f"{LINKS_RELATIVE_ROOT}/{approval_id}.json"


def write_exact_human_approval_link(
    archive_root: Path | str,
    *,
    approval_claim: _ClaimedExactHumanApproval,
    approval_context: ExactHumanApprovalContext,
    operation: ExactHumanApprovalOperation | str,
    plan_sha256: str,
    target_binding_sha256: str,
    source_operation_receipt: Path | str,
    expected_source_operation_receipt_sha256: str,
    effect: str,
    random_hex: Any = secrets.token_hex,
) -> dict[str, Any]:
    """Publish one immutable link after the source operation receipt exists.

    The caller must invoke this *after* the source operation receipt has been
    durably verified and before returning success to the approval workflow.  If
    this function raises after the source write, the workflow must leave the
    exact approval claim ``started`` for reconciliation.
    """

    if type(approval_claim) is not _ClaimedExactHumanApproval:
        raise _fail("exact_human_approval_link_approval_claim_invalid")
    if type(approval_context) is not ExactHumanApprovalContext:
        raise _fail("exact_human_approval_link_approval_claim_invalid")
    root, archive_id = _archive_root(archive_root)
    normalized_operation = _operation(operation)
    normalized_plan = _sha_reference(plan_sha256)
    normalized_target = _sha_reference(target_binding_sha256)
    if effect not in LINK_EFFECTS:
        raise _fail("exact_human_approval_link_argument_invalid")
    if not (
        approval_context.operation.value == normalized_operation
        and hmac.compare_digest(
            approval_context.archive_identity_sha256,
            exact_human_approval_archive_identity_sha256(archive_id),
        )
        and hmac.compare_digest(
            approval_context.plan_sha256, normalized_plan
        )
        and hmac.compare_digest(
            approval_context.target_binding_sha256, normalized_target
        )
    ):
        raise _fail("exact_human_approval_link_binding_mismatch")
    source_relative, source_sha256 = _source_receipt(
        root,
        operation=normalized_operation,
        relative=source_operation_receipt,
        expected_sha256=expected_source_operation_receipt_sha256,
    )
    try:
        reference = approval_claim.assert_ready_for_context(approval_context)
    except ExactHumanApprovalError:
        raise _fail("exact_human_approval_link_approval_claim_invalid") from None
    document = _build_document(
        exact_human_approval=reference,
        operation=normalized_operation,
        plan_sha256=normalized_plan,
        target_binding_sha256=normalized_target,
        source_receipt_relative=source_relative,
        source_receipt_sha256=source_sha256,
        effect=effect,
        approval_claim=approval_claim,
    )
    _validate_document(document, approval_claim=approval_claim)
    directory, directory_info = _links_root(root, create=True)
    _publish_create_only(
        directory,
        directory_info,
        approval_id=reference["approval_id"],
        document=document,
        random_hex=random_hex,
    )
    raw = _canonical_bytes(document)
    relative = f"{LINKS_RELATIVE_ROOT}/{reference['approval_id']}.json"
    return {
        "schema_version": LINK_RESULT_SCHEMA_VERSION,
        "ok": True,
        "created": True,
        "approval_id": reference["approval_id"],
        "operation": normalized_operation,
        "effect": effect,
        "original_operation_evidence_upgraded": effect == "created",
        "receipt_relative_path": relative,
        "receipt_sha256": _sha256(raw),
        "source_operation_receipt_sha256": source_sha256,
        "source_operation_receipt_bytes_hashed": True,
        "source_operation_receipt_content_parsed": False,
        "private_content_echoed": False,
        "absolute_path_echoed": False,
        "reviewer_claim_echoed": False,
        "claim_status_at_return": "started",
        "claim_finalization_required": True,
    }


def read_exact_human_approval_link(
    archive_root: Path | str,
    approval_id: str,
    *,
    receipt_authentication_key: bytes | bytearray | memoryview,
) -> dict[str, Any]:
    """Read one MAC-authenticated link backed by a succeeded exact claim."""

    root, archive_id = _archive_root(archive_root)
    key = _validated_key(receipt_authentication_key)
    try:
        document, _raw, _relative = _read_link(
            root,
            archive_id=archive_id,
            approval_id=approval_id,
            key=key,
        )
        return document
    finally:
        _wipe(key)


def verify_exact_human_approval_link(
    archive_root: Path | str,
    *,
    exact_human_approval: Mapping[str, Any],
    operation: ExactHumanApprovalOperation | str,
    plan_sha256: str,
    target_binding_sha256: str,
    source_operation_receipt: Path | str,
    expected_source_operation_receipt_sha256: str,
    effect: str,
    receipt_authentication_key: bytes | bytearray | memoryview,
) -> dict[str, Any]:
    """Verify a discovered link against independently expected bindings."""

    root, archive_id = _archive_root(archive_root)
    reference = _approval_reference(exact_human_approval)
    normalized_operation = _operation(operation)
    normalized_plan = _sha_reference(plan_sha256)
    normalized_target = _sha_reference(target_binding_sha256)
    if effect not in LINK_EFFECTS:
        raise _fail("exact_human_approval_link_argument_invalid")
    source_relative = _source_receipt_relative(
        source_operation_receipt, normalized_operation
    )
    source_sha256 = _sha_reference(expected_source_operation_receipt_sha256)
    key = _validated_key(receipt_authentication_key)
    try:
        document, raw, relative = _read_link(
            root,
            archive_id=archive_id,
            approval_id=reference["approval_id"],
            key=key,
        )
        expected = _build_unsigned_document(
            exact_human_approval=reference,
            operation=normalized_operation,
            plan_sha256=normalized_plan,
            target_binding_sha256=normalized_target,
            source_receipt_relative=source_relative,
            source_receipt_sha256=source_sha256,
            effect=effect,
        )
        actual = dict(document)
        actual.pop("authentication", None)
        if not hmac.compare_digest(
            _canonical_bytes(actual), _canonical_bytes(expected)
        ):
            raise _fail("exact_human_approval_link_binding_mismatch")
        return {
            "schema_version": LINK_RESULT_SCHEMA_VERSION,
            "ok": True,
            "verified": True,
            "approval_id": reference["approval_id"],
            "operation": normalized_operation,
            "effect": effect,
            "original_operation_evidence_upgraded": effect == "created",
            "receipt_relative_path": relative,
            "receipt_sha256": _sha256(raw),
            "source_operation_receipt_sha256": source_sha256,
            "private_content_echoed": False,
            "absolute_path_echoed": False,
            "reviewer_claim_echoed": False,
        }
    finally:
        _wipe(key)


def exact_human_approval_link_upgrades_original_operation(
    archive_root: Path | str,
    approval_id: str,
    *,
    receipt_authentication_key: bytes | bytearray | memoryview,
) -> bool:
    """Return true only for a MAC-valid link with a succeeded exact claim."""

    validated = read_exact_human_approval_link(
        archive_root,
        approval_id,
        receipt_authentication_key=receipt_authentication_key,
    )
    return bool(
        validated["effect"] == "created"
        and validated["original_operation_evidence_upgraded"] is True
    )


__all__ = [
    "ExactHumanApprovalLinkError",
    "LINK_AUTHENTICATION_SCHEMA_VERSION",
    "LINK_EFFECTS",
    "LINK_OPERATIONS",
    "LINK_RECEIPT_SCHEMA_VERSION",
    "LINK_RESULT_SCHEMA_VERSION",
    "LINKS_RELATIVE_ROOT",
    "exact_human_approval_link_upgrades_original_operation",
    "read_exact_human_approval_link",
    "verify_exact_human_approval_link",
    "write_exact_human_approval_link",
]
