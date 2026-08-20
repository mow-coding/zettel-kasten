"""Content-free approval audit and append-only integrity remediation.

Legacy mint, zettel-edge, and retired-draft receipts were approval-gated but
were not authenticated with a MAC or signature.  This module never upgrades
their reviewer or affirmation strings into exact human authority.  It can
classify those receipts without reading zettel bodies, and it can append a
separate authenticated overlay after a new exact, one-use human approval.

The original operation receipt and every canonical/edge/draft artifact remain
immutable.  Public results contain only fixed enums, counts, booleans, and
domain-separated SHA-256 bindings; paths, labels, titles, reviewer strings,
and source prose are deliberately absent.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence

import yaml

from .exact_human_approval import (
    APPROVAL_INTEGRITY_MAC_DOMAIN,
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


AUDIT_SCHEMA_VERSION = "wom-kit/approval-integrity-audit-result/v0.1"
OPERATION_APPROVAL_SCHEMA_VERSION = (
    "wom-kit/operation-exact-human-approval/v0.1"
)
OVERLAY_ENTRY_SCHEMA_VERSION = (
    "wom-kit/approval-integrity-overlay-entry/v0.1"
)
OVERLAY_PLAN_SCHEMA_VERSION = (
    "wom-kit/approval-integrity-overlay-plan/v0.1"
)
OVERLAY_GUARD_SCHEMA_VERSION = (
    "wom-kit/approval-integrity-overlay-guard/v0.1"
)
OVERLAY_RESULT_SCHEMA_VERSION = (
    "wom-kit/approval-integrity-overlay-result/v0.1"
)
OVERLAY_AUTHENTICATION_SCHEMA_VERSION = (
    "wom-kit/approval-integrity-overlay-authentication/v0.1"
)

CLASSIFICATIONS = (
    "exact_v0400",
    "legacy_unbound_approval",
    "circular_self_source",
    "unsupported_affirmation",
    "receipt_invalid",
    "unknown",
)
OVERLAY_STATES = (
    "review_required",
    "evidence_supplemented",
    "withdrawn",
    "repair_planned",
)
AFFECTED_KINDS = ("canonical_mint", "zettel_edge", "retired_draft")
BLOCKING_OVERLAY_STATES = frozenset({"review_required", "withdrawn"})

_KIND_OPERATION = {
    "canonical_mint": "mint_zet",
    "zettel_edge": "zettel_edge",
    "retired_draft": "retire_draft",
}
_RECEIPT_LOCATIONS = (
    ("canonical_mint", ("receipts", "mint"), ".mint.json"),
    (
        "retired_draft",
        ("receipts", "mint", "retired-drafts"),
        ".retire-draft.json",
    ),
    ("zettel_edge", ("receipts", "edges"), ".zettel-edge.json"),
)

_AFFECTED_DOMAIN = b"wom-kit/approval-integrity-affected/v0.1\x00"
_INVALID_AFFECTED_DOMAIN = (
    b"wom-kit/approval-integrity-invalid-affected/v0.1\x00"
)
_GENESIS_DOMAIN = b"wom-kit/approval-integrity-overlay-genesis/v0.1\x00"
_ENTRY_DIGEST_DOMAIN = b"wom-kit/approval-integrity-overlay-entry/v0.1\x00"
_ENTRY_MAC_DOMAIN = APPROVAL_INTEGRITY_MAC_DOMAIN
_PLAN_DOMAIN = b"wom-kit/approval-integrity-overlay-plan/v0.1\x00"

_ARCHIVE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,191}$")
_EDGE_ID_RE = re.compile(r"^edge:[0-9a-f]{64}$")
_APPROVAL_ID_RE = re.compile(r"^approval_[0-9a-f]{32}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_HMAC_RE = re.compile(r"^hmac-sha256:[0-9a-f]{64}$")
_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,95}$")
_KEY_BYTES = 32
_MAX_OPERATION_RECEIPT_BYTES = 2 * 1024 * 1024
_MAX_FIDELITY_RECEIPT_BYTES = 2 * 1024 * 1024
_MAX_OVERLAY_ENTRY_BYTES = 128 * 1024
_DEFAULT_MAX_RECEIPTS = 4096
_DEFAULT_MAX_OVERLAYS = 1024


class ApprovalIntegrityError(RuntimeError):
    """Fixed-code failure that never retains caller text or a private path."""

    _CODES = {
        "approval_integrity_archive_invalid",
        "approval_integrity_key_invalid",
        "approval_integrity_argument_invalid",
        "approval_integrity_operation_receipt_unsafe",
        "approval_integrity_operation_receipt_invalid",
        "approval_integrity_operation_receipt_changed",
        "approval_integrity_operation_receipt_sha256_mismatch",
        "approval_integrity_affected_binding_mismatch",
        "approval_integrity_overlay_state_invalid",
        "approval_integrity_overlay_expected_current_required",
        "approval_integrity_overlay_expected_current_mismatch",
        "approval_integrity_overlay_plan_mismatch",
        "approval_integrity_overlay_ledger_invalid",
        "approval_integrity_overlay_lock_held",
        "approval_integrity_overlay_commit_failed",
        "approval_integrity_overlay_replayed",
        "approval_integrity_approval_claim_invalid",
        "approval_integrity_approval_context_invalid",
        "approval_integrity_time_invalid",
    }

    def __init__(self, code: str) -> None:
        self.code = (
            code
            if code in self._CODES
            else "approval_integrity_operation_receipt_invalid"
        )
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"ApprovalIntegrityError({self.code!r})"


def _fail(code: str) -> ApprovalIntegrityError:
    return ApprovalIntegrityError(code)


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


def _domain_digest(domain: bytes, document: Mapping[str, Any]) -> str:
    return _sha256(domain + _canonical_bytes(document))


def _is_reparse(info: os.stat_result) -> bool:
    return bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _same_file(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        left.st_dev == right.st_dev
        and left.st_ino == right.st_ino
        and stat.S_IFMT(left.st_mode) == stat.S_IFMT(right.st_mode)
    )


def _archive_identity(archive_root: Path | str) -> tuple[Path, str, str]:
    try:
        root = Path(archive_root).resolve(strict=True)
        root_info = os.lstat(root)
    except (OSError, RuntimeError, TypeError, ValueError):
        raise _fail("approval_integrity_archive_invalid") from None
    if _is_reparse(root_info) or not stat.S_ISDIR(root_info.st_mode):
        raise _fail("approval_integrity_archive_invalid")
    marker = root / "archive.yml"
    try:
        raw = _stable_read(marker, max_bytes=128 * 1024)
        document = yaml.safe_load(raw.decode("utf-8"))
    except ApprovalIntegrityError:
        raise _fail("approval_integrity_archive_invalid") from None
    except (UnicodeError, yaml.YAMLError):
        raise _fail("approval_integrity_archive_invalid") from None
    archive_id = document.get("archive_id") if isinstance(document, Mapping) else None
    if type(archive_id) is not str or _ARCHIVE_ID_RE.fullmatch(archive_id) is None:
        raise _fail("approval_integrity_archive_invalid")
    try:
        identity_sha256 = exact_human_approval_archive_identity_sha256(archive_id)
    except ExactHumanApprovalError:
        raise _fail("approval_integrity_archive_invalid") from None
    return root, archive_id, identity_sha256


def _validated_key(
    value: bytes | bytearray | memoryview | None,
    *,
    required: bool,
) -> bytearray | None:
    if value is None and not required:
        return None
    try:
        raw = bytes(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise _fail("approval_integrity_key_invalid") from None
    if len(raw) != _KEY_BYTES:
        raise _fail("approval_integrity_key_invalid")
    return bytearray(raw)


def _wipe(value: bytearray | None) -> None:
    if value is not None:
        for index in range(len(value)):
            value[index] = 0


def _stable_read(path: Path, *, max_bytes: int) -> bytes:
    descriptor: int | None = None
    try:
        before = os.lstat(path)
        if _is_reparse(before) or not stat.S_ISREG(before.st_mode):
            raise _fail("approval_integrity_operation_receipt_unsafe")
        flags = os.O_RDONLY
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags)
        opened_before = os.fstat(descriptor)
        if not _same_file(before, opened_before) or opened_before.st_size > max_bytes:
            raise _fail("approval_integrity_operation_receipt_unsafe")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(65_536, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise _fail("approval_integrity_operation_receipt_unsafe")
        opened_after = os.fstat(descriptor)
        after = os.lstat(path)
        if (
            not _same_file(opened_before, opened_after)
            or not _same_file(opened_after, after)
            or opened_before.st_size != opened_after.st_size
            or getattr(opened_before, "st_mtime_ns", None)
            != getattr(opened_after, "st_mtime_ns", None)
            or getattr(opened_before, "st_ctime_ns", None)
            != getattr(opened_after, "st_ctime_ns", None)
        ):
            raise _fail("approval_integrity_operation_receipt_changed")
        raw = b"".join(chunks)
        if len(raw) != opened_after.st_size:
            raise _fail("approval_integrity_operation_receipt_changed")
        return raw
    except ApprovalIntegrityError:
        raise
    except (FileNotFoundError, OSError):
        raise _fail("approval_integrity_operation_receipt_unsafe") from None
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass


class _DuplicateKey(ValueError):
    pass


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey(key)
        result[key] = value
    return result


def _parse_json(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)),
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        _DuplicateKey,
        ValueError,
        RecursionError,
    ):
        raise _fail("approval_integrity_operation_receipt_invalid") from None
    if not isinstance(value, dict):
        raise _fail("approval_integrity_operation_receipt_invalid")
    return value


def _safe_directory(path: Path, *, create: bool) -> bool:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        if not create:
            return False
        try:
            path.mkdir()
            info = os.lstat(path)
        except (OSError, FileExistsError):
            raise _fail("approval_integrity_overlay_ledger_invalid") from None
    except OSError:
        raise _fail("approval_integrity_overlay_ledger_invalid") from None
    if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
        raise _fail("approval_integrity_overlay_ledger_invalid")
    return True


def _directory_chain(
    root: Path,
    parts: Sequence[str],
    *,
    create: bool,
) -> Path | None:
    current = root
    for part in parts:
        current = current / part
        if not _safe_directory(current, create=create):
            return None
    return current


def approval_integrity_affected_id_sha256(
    affected_kind: str,
    affected_id: str,
) -> str:
    """Hash one raw identifier without retaining or returning it."""

    if affected_kind not in AFFECTED_KINDS or type(affected_id) is not str:
        raise _fail("approval_integrity_argument_invalid")
    if affected_kind == "zettel_edge":
        valid = _EDGE_ID_RE.fullmatch(affected_id) is not None
    else:
        valid = _SAFE_ID_RE.fullmatch(affected_id) is not None
    if not valid:
        raise _fail("approval_integrity_argument_invalid")
    return _domain_digest(
        _AFFECTED_DOMAIN,
        {"affected_kind": affected_kind, "affected_id": affected_id},
    )


def _invalid_affected_id_sha256(
    affected_kind: str,
    operation_receipt_sha256: str,
) -> str:
    return _domain_digest(
        _INVALID_AFFECTED_DOMAIN,
        {
            "affected_kind": affected_kind,
            "operation_receipt_sha256": operation_receipt_sha256,
        },
    )


def _exact_reference_shape(value: Any) -> bool:
    return bool(
        isinstance(value, Mapping)
        and set(value)
        == {
            "schema_version",
            "approval_id",
            "context_sha256",
            "approval_authority_sha256",
            "one_use",
        }
        and value.get("schema_version") == REFERENCE_SCHEMA_VERSION
        and type(value.get("approval_id")) is str
        and _APPROVAL_ID_RE.fullmatch(value["approval_id"]) is not None
        and type(value.get("context_sha256")) is str
        and _SHA256_RE.fullmatch(value["context_sha256"]) is not None
        and type(value.get("approval_authority_sha256")) is str
        and _SHA256_RE.fullmatch(value["approval_authority_sha256"])
        is not None
        and value.get("one_use") is True
    )


def _claim_path(root: Path, approval_id: str) -> Path:
    claims = _directory_chain(
        root,
        tuple(PurePosixPath(CLAIMS_RELATIVE_ROOT).parts),
        create=False,
    )
    if claims is None:
        raise _fail("approval_integrity_approval_claim_invalid")
    return claims / f"{approval_id}.json"


def _validated_exact_reference_status(
    root: Path,
    archive_id: str,
    archive_identity_sha256: str,
    reference: Mapping[str, Any],
    key: bytearray,
    *,
    expected_operation: str,
    expected_plan_sha256: str,
    expected_target_binding_sha256: str,
) -> str | None:
    if not _exact_reference_shape(reference):
        return None
    try:
        claim = _read_exact_human_approval_claim(
            _claim_path(root, reference["approval_id"]),
            archive_id=archive_id,
            key=key,
        )
    except (ApprovalIntegrityError, ExactHumanApprovalError):
        return None
    context = claim.get("context")
    if not isinstance(context, Mapping):
        return None
    if not bool(
        hmac.compare_digest(claim["approval_id"], reference["approval_id"])
        and hmac.compare_digest(
            claim["context_sha256"], reference["context_sha256"]
        )
        and hmac.compare_digest(
            claim["approval_authority_sha256"],
            reference["approval_authority_sha256"],
        )
        and context.get("operation") == expected_operation
        and hmac.compare_digest(
            context.get("archive_identity_sha256", ""),
            archive_identity_sha256,
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
    status = claim.get("status")
    return status if status in {"started", "succeeded", "failed"} else None


def _verify_exact_reference(
    root: Path,
    archive_id: str,
    archive_identity_sha256: str,
    reference: Mapping[str, Any],
    key: bytearray,
    *,
    expected_operation: str,
    expected_plan_sha256: str,
    expected_target_binding_sha256: str,
    required_status: str,
) -> bool:
    status = _validated_exact_reference_status(
        root,
        archive_id,
        archive_identity_sha256,
        reference,
        key,
        expected_operation=expected_operation,
        expected_plan_sha256=expected_plan_sha256,
        expected_target_binding_sha256=expected_target_binding_sha256,
    )
    return status == required_status


def _claim_capability_reference_status(
    approval_claim: _ClaimedExactHumanApproval,
    reference: Mapping[str, Any],
    *,
    expected_operation: str,
    expected_plan_sha256: str,
    expected_target_binding_sha256: str,
) -> str | None:
    try:
        operation = ExactHumanApprovalOperation(expected_operation)
        return approval_claim.approval_integrity_reference_status(
            reference,
            expected_operation=operation,
            expected_plan_sha256=expected_plan_sha256,
            expected_target_binding_sha256=expected_target_binding_sha256,
        )
    except (ValueError, ExactHumanApprovalError):
        raise _fail("approval_integrity_approval_claim_invalid") from None


def _operation_shape(
    document: Mapping[str, Any],
    *,
    affected_kind: str,
    archive_id: str,
) -> tuple[bool, str | None]:
    if document.get("archive_id") != archive_id:
        return False, None
    if affected_kind == "canonical_mint":
        zettel = document.get("zettel")
        affected_id = zettel.get("id") if isinstance(zettel, Mapping) else None
        affirmations = document.get("affirmations")
        valid = bool(
            document.get("action") == "mint_zettel"
            and document.get("dry_run") is False
            and document.get("authority_mode") == "basic"
            and type(affected_id) is str
            and _SAFE_ID_RE.fullmatch(affected_id) is not None
            and document.get("receipt_id") == f"receipt:mint:{affected_id}"
            and document.get("receipt_path")
            == f"receipts/mint/{affected_id}.mint.json"
            and isinstance(document.get("source"), Mapping)
            and isinstance(document.get("target"), Mapping)
            and isinstance(document.get("snapshot"), Mapping)
            and isinstance(document.get("result"), Mapping)
            and type(document["target"].get("sha256")) is str
            and _HEX64_RE.fullmatch(document["target"]["sha256"]) is not None
            and (affirmations is None or isinstance(affirmations, list))
        )
        return valid, affected_id if valid else None
    if affected_kind == "retired_draft":
        zettel = document.get("zettel")
        affected_id = zettel.get("id") if isinstance(zettel, Mapping) else None
        valid = bool(
            document.get("action") == "retire_minted_draft"
            and document.get("dry_run") is False
            and document.get("authority_mode") == "basic"
            and type(affected_id) is str
            and _SAFE_ID_RE.fullmatch(affected_id) is not None
            and document.get("receipt_id")
            == f"receipt:mint-retired-draft:{affected_id}"
            and document.get("receipt_path")
            == (
                "receipts/mint/retired-drafts/"
                f"{affected_id}.retire-draft.json"
            )
            and isinstance(document.get("source"), Mapping)
            and isinstance(document.get("target"), Mapping)
            and isinstance(document.get("mint_receipt"), Mapping)
            and isinstance(document.get("snapshot"), Mapping)
            and isinstance(document.get("result"), Mapping)
        )
        return valid, affected_id if valid else None
    if affected_kind == "zettel_edge":
        affected_id = document.get("edge_id")
        valid = bool(
            document.get("schema_version")
            == "wom-kit/zettel-edge-receipt/v0.1"
            and document.get("lifecycle_action") == "zettel_edge_write"
            and document.get("receipt_kind") == "zettel_edge_write"
            and type(affected_id) is str
            and _EDGE_ID_RE.fullmatch(affected_id) is not None
            and type(document.get("source_zettel_id")) is str
            and _SAFE_ID_RE.fullmatch(document["source_zettel_id"]) is not None
            and type(document.get("edge_type")) is str
            and bool(document["edge_type"])
            and type(document.get("target_ref")) is str
            and bool(document["target_ref"])
            and isinstance(document.get("result"), Mapping)
            and document["result"].get("edge_written") is True
            and document["result"].get("receipt_written") is True
        )
        return valid, affected_id if valid else None
    return False, None


def _safe_affected_id_from_document(
    document: Mapping[str, Any],
    affected_kind: str,
) -> str | None:
    if affected_kind == "zettel_edge":
        candidate = document.get("edge_id")
        return (
            candidate
            if type(candidate) is str and _EDGE_ID_RE.fullmatch(candidate)
            else None
        )
    zettel = document.get("zettel")
    candidate = zettel.get("id") if isinstance(zettel, Mapping) else None
    return (
        candidate
        if type(candidate) is str and _SAFE_ID_RE.fullmatch(candidate)
        else None
    )


def _legacy_actor_present(document: Mapping[str, Any]) -> bool:
    return any(
        type(document.get(name)) is str and bool(document.get(name))
        for name in ("reviewed_by", "approved_by", "actor", "affirmed_by")
    )


def _unsupported_affirmation_present(document: Mapping[str, Any]) -> bool:
    affirmations = document.get("affirmations")
    return bool(
        (isinstance(affirmations, list) and affirmations)
        or (type(affirmations) is str and affirmations)
    )


def _parse_utc(value: Any) -> datetime | None:
    if type(value) is not str:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _canonical_overlay_timestamp(value: Any) -> bool:
    parsed = _parse_utc(value)
    return bool(
        parsed is not None
        and parsed.isoformat(timespec="microseconds").replace("+00:00", "Z")
        == value
    )


def _json_digest_hex(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _fidelity_receipt_shape_and_bindings_valid(
    receipt: Mapping[str, Any],
    *,
    archive_id: str,
    affected_id: str,
    plan_sha256: str,
) -> bool:
    outer_keys = {
        "schema",
        "action",
        "archive_id",
        "archive_type",
        "draft_id",
        "draft_path",
        "body_sha256",
        "creation_mode",
        "frontmatter_authority_sha256",
        "source_fidelity_plan_sha256",
        "reviewed_by",
        "review_binding_sha256",
        "candidate_created_at",
        "source_fidelity",
        "content_contract",
        "result",
    }
    if set(receipt) != outer_keys:
        return False
    if not (
        receipt.get("schema")
        == "wom-kit/source-fidelity-draft-receipt/v0.2"
        and receipt.get("action") == "create_source_fidelity_draft"
        and receipt.get("archive_id") == archive_id
        and receipt.get("draft_id") == affected_id
        and receipt.get("source_fidelity_plan_sha256") == plan_sha256
        and (
            receipt.get("archive_type") is None
            or type(receipt.get("archive_type")) is str
        )
        and type(receipt.get("draft_path")) is str
        and re.fullmatch(
            r"inbox/[A-Za-z0-9_-]+\.md", receipt["draft_path"]
        )
        is not None
        and receipt.get("creation_mode") in {"ai_assisted", "ai_generated"}
        and type(receipt.get("reviewed_by")) is str
        and bool(receipt["reviewed_by"])
        and type(receipt.get("candidate_created_at")) is str
        and _parse_utc(receipt["candidate_created_at"]) is not None
    ):
        return False
    for name in (
        "body_sha256",
        "frontmatter_authority_sha256",
        "source_fidelity_plan_sha256",
        "review_binding_sha256",
    ):
        if type(receipt.get(name)) is not str or _HEX64_RE.fullmatch(
            receipt[name]
        ) is None:
            return False

    content_contract = receipt.get("content_contract")
    if not isinstance(content_contract, Mapping) or set(content_contract) != {
        "source_text_stored",
        "source_locator_stored",
        "source_path_stored",
    } or any(value is not False for value in content_contract.values()):
        return False
    result = receipt.get("result")
    if not isinstance(result, Mapping) or set(result) != {
        "draft_written_create_only",
        "receipt_written_create_only",
        "source_changed",
        "share_performed",
    } or result != {
        "draft_written_create_only": True,
        "receipt_written_create_only": True,
        "source_changed": False,
        "share_performed": False,
    }:
        return False

    fidelity = receipt.get("source_fidelity")
    fidelity_keys = {
        "schema",
        "mode",
        "audience",
        "comparison_basis",
        "source",
        "region",
        "byte_exact",
        "mechanically_verified",
        "semantic_fidelity_machine_verified",
        "human_review_required",
        "source_changed",
        "share_performed",
        "source_text_stored",
        "source_locator_stored",
        "creation_plan_sha256",
        "evidence_id",
    }
    if not isinstance(fidelity, Mapping) or set(fidelity) != fidelity_keys:
        return False
    mode = fidelity.get("mode")
    if not (
        fidelity.get("schema") == "wom-kit/source-fidelity/v0.2"
        and mode in {"verbatim", "faithful_summary", "sanitized_derivative"}
        and fidelity.get("audience")
        in {
            "private_self",
            "ai_working_context",
            "client_report",
            "public_web",
            "legal_copyright_request",
        }
        and fidelity.get("comparison_basis") == "utf8_newlines_lf"
        and fidelity.get("byte_exact") is False
        and fidelity.get("mechanically_verified") is (mode == "verbatim")
        and fidelity.get("semantic_fidelity_machine_verified") is False
        and fidelity.get("human_review_required") is True
        and fidelity.get("source_changed") is False
        and fidelity.get("share_performed") is False
        and fidelity.get("source_text_stored") is False
        and fidelity.get("source_locator_stored") is False
        and fidelity.get("creation_plan_sha256") == plan_sha256
        and type(fidelity.get("evidence_id")) is str
        and re.fullmatch(
            r"source-fidelity-evidence:[0-9a-f]{24}",
            fidelity["evidence_id"],
        )
        is not None
    ):
        return False

    region = fidelity.get("region")
    if mode == "verbatim":
        if not isinstance(region, Mapping) or set(region) != {
            "offset_bytes",
            "length_bytes",
            "sha256",
        }:
            return False
        if (
            isinstance(region.get("offset_bytes"), bool)
            or not isinstance(region.get("offset_bytes"), int)
            or region["offset_bytes"] < 0
            or isinstance(region.get("length_bytes"), bool)
            or not isinstance(region.get("length_bytes"), int)
            or region["length_bytes"] < 0
            or type(region.get("sha256")) is not str
            or _HEX64_RE.fullmatch(region["sha256"]) is None
        ):
            return False
    elif region is not None:
        return False

    source = fidelity.get("source")
    common_source_keys = {
        "authority_kind",
        "raw_sha256",
        "raw_size_bytes",
        "normalized_sha256",
        "normalized_size_bytes",
        "comparison_basis",
        "newline_transformation_applied",
        "source_text_stored",
        "source_locator_stored",
    }
    if not isinstance(source, Mapping):
        return False
    for name in ("raw_sha256", "normalized_sha256"):
        if type(source.get(name)) is not str or _HEX64_RE.fullmatch(
            source[name]
        ) is None:
            return False
    for name in ("raw_size_bytes", "normalized_size_bytes"):
        if (
            isinstance(source.get(name), bool)
            or not isinstance(source.get(name), int)
            or source[name] < 0
        ):
            return False
    if not (
        source.get("comparison_basis") == "utf8_newlines_lf"
        and type(source.get("newline_transformation_applied")) is bool
        and source.get("source_text_stored") is False
        and source.get("source_locator_stored") is False
    ):
        return False

    authority_kind = source.get("authority_kind")
    if authority_kind == "manifested_object":
        if set(source) != common_source_keys | {"object_id", "provenance"}:
            return False
        if not (
            type(source.get("object_id")) is str
            and _SHA256_RE.fullmatch(source["object_id"]) is not None
            and source["object_id"].removeprefix("sha256:")
            == source["raw_sha256"]
        ):
            return False
        provenance = source.get("provenance")
        provenance_keys = {
            "binding_state",
            "captured_at",
            "source_role",
            "input_kind",
            "source_intake_plan_sha256",
            "staged_source_class",
            "independent_external_provenance",
            "raw_source_locator_stored",
            "raw_source_locator_echoed",
        }
        if not isinstance(provenance, Mapping) or set(provenance) != provenance_keys:
            return False
        captured_at = provenance.get("captured_at")
        intake_plan = provenance.get("source_intake_plan_sha256")
        if not (
            provenance.get("binding_state")
            in {"manifest_intake_bound", "legacy_unbound"}
            and (
                captured_at is None
                or (type(captured_at) is str and _parse_utc(captured_at) is not None)
            )
            and provenance.get("source_role")
            in {"primary_source", "context", "attachment", "derived_context", None}
            and (
                provenance.get("input_kind") is None
                or type(provenance.get("input_kind")) is str
            )
            and (
                intake_plan is None
                or (type(intake_plan) is str and _SHA256_RE.fullmatch(intake_plan))
            )
            and type(provenance.get("staged_source_class")) is str
            and bool(provenance["staged_source_class"])
            and type(provenance.get("independent_external_provenance")) is bool
            and provenance.get("raw_source_locator_stored") is False
            and provenance.get("raw_source_locator_echoed") is False
        ):
            return False
    elif authority_kind == "reviewed_session_evidence":
        session_keys = {
            "evidence_id",
            "source_role",
            "producer_kind",
            "produced_at",
            "captured_at",
            "session_ref_sha256",
            "input_provenance_sha256",
            "semantic_fidelity_machine_verified",
            "receipt_sha256",
        }
        if set(source) != common_source_keys | session_keys:
            return False
        produced_at = _parse_utc(source.get("produced_at"))
        captured_at = _parse_utc(source.get("captured_at"))
        provenance_digests = source.get("input_provenance_sha256")
        if not (
            type(source.get("evidence_id")) is str
            and re.fullmatch(
                r"source-fidelity-session-evidence:[0-9a-f]{64}",
                source["evidence_id"],
            )
            is not None
            and source.get("source_role")
            in {
                "external_primary_source",
                "external_context",
                "human_authored_source",
                "reviewed_session_transcript",
                "reviewed_multi_source_bundle",
                "human_reviewed_summary",
                "self_authored_candidate",
            }
            and source.get("producer_kind")
            in {"human", "external_system", "ai_runtime", "mixed"}
            and produced_at is not None
            and captured_at is not None
            and produced_at <= captured_at
            and type(source.get("session_ref_sha256")) is str
            and _SHA256_RE.fullmatch(source["session_ref_sha256"]) is not None
            and isinstance(provenance_digests, list)
            and len(set(provenance_digests)) == len(provenance_digests)
            and all(
                type(item) is str and _SHA256_RE.fullmatch(item) is not None
                for item in provenance_digests
            )
            and source.get("semantic_fidelity_machine_verified") is False
            and type(source.get("receipt_sha256")) is str
            and _SHA256_RE.fullmatch(source["receipt_sha256"]) is not None
        ):
            return False
    else:
        return False

    expected_evidence_id = "source-fidelity-evidence:" + _json_digest_hex(
        {
            "source": source,
            "region": region,
            "mode": mode,
            "audience": fidelity["audience"],
            "comparison_basis": "utf8_newlines_lf",
        }
    )[:24]
    if not hmac.compare_digest(fidelity["evidence_id"], expected_evidence_id):
        return False

    fidelity_authority = {
        key: value
        for key, value in fidelity.items()
        if key != "creation_plan_sha256"
    }
    expected_plan = _json_digest_hex(
        {
            "schema": "wom-kit/source-fidelity/v0.2",
            "archive_id": archive_id,
            "archive_type": receipt["archive_type"],
            "draft_id": affected_id,
            "draft_path": receipt["draft_path"],
            "created_at": receipt["candidate_created_at"],
            "creation_mode": receipt["creation_mode"],
            "source_fidelity": fidelity_authority,
            "final_body_sha256": receipt["body_sha256"],
            "region": region,
            "frontmatter_authority_sha256": receipt[
                "frontmatter_authority_sha256"
            ],
        }
    )
    if not hmac.compare_digest(plan_sha256, expected_plan):
        return False
    expected_review_binding = _json_digest_hex(
        {
            "schema": "wom-kit/source-fidelity-review-binding/v0.1",
            "archive_id": archive_id,
            "draft_id": affected_id,
            "draft_path": receipt["draft_path"],
            "body_sha256": receipt["body_sha256"],
            "source_fidelity_plan_sha256": plan_sha256,
            "reviewed_by": receipt["reviewed_by"],
        }
    )
    return hmac.compare_digest(
        receipt["review_binding_sha256"], expected_review_binding
    )


def _fidelity_facts(
    root: Path,
    *,
    archive_id: str,
    operation_document: Mapping[str, Any],
    affected_id: str,
) -> tuple[bool, bool, bool, bool]:
    """Return claimed, valid, mechanical equality, positive provenance."""

    projection = operation_document.get("source_fidelity")
    if projection is None:
        return False, False, False, False
    if not isinstance(projection, Mapping):
        return True, False, False, False
    # v0.1 is a known legacy-unbound fidelity projection.  It lacks the
    # provenance union needed to prove circularity, but that absence is not
    # corruption and must not be promoted to ``receipt_invalid``.
    if projection.get("schema") == "wom-kit/source-fidelity/v0.1":
        return False, False, False, False
    if projection.get("schema") != "wom-kit/source-fidelity/v0.2":
        return True, False, False, False
    plan_sha256 = projection.get("creation_plan_sha256")
    if type(plan_sha256) is not str or _HEX64_RE.fullmatch(plan_sha256) is None:
        return True, False, False, False
    directory = _directory_chain(
        root, ("receipts", "source-fidelity", "drafts"), create=False
    )
    if directory is None:
        return True, False, False, False
    try:
        raw = _stable_read(
            directory / f"{plan_sha256}.json",
            max_bytes=_MAX_FIDELITY_RECEIPT_BYTES,
        )
        receipt = _parse_json(raw)
    except ApprovalIntegrityError:
        return True, False, False, False
    fidelity = receipt.get("source_fidelity")
    source = fidelity.get("source") if isinstance(fidelity, Mapping) else None
    valid = _fidelity_receipt_shape_and_bindings_valid(
        receipt,
        archive_id=archive_id,
        affected_id=affected_id,
        plan_sha256=plan_sha256,
    )
    if not valid:
        return True, False, False, False
    mechanical = hmac.compare_digest(
        source["normalized_sha256"], receipt["body_sha256"]
    )
    provenance = False
    if mechanical and source.get("authority_kind") == "reviewed_session_evidence":
        if source.get("source_role") == "self_authored_candidate":
            provenance = True
        else:
            produced_at = _parse_utc(source.get("produced_at"))
            candidate_created_at = _parse_utc(receipt.get("candidate_created_at"))
            provenance = bool(
                source.get("producer_kind") == "ai_runtime"
                and produced_at is not None
                and candidate_created_at is not None
                and produced_at >= candidate_created_at
            )
    elif mechanical and source.get("authority_kind") == "manifested_object":
        facts = source.get("provenance")
        provenance = bool(
            isinstance(facts, Mapping)
            and facts.get("independent_external_provenance") is False
            and (
                facts.get("source_role") == "derived_context"
                or facts.get("staged_source_class") == "archive_ai_scratch"
            )
        )
    return True, True, mechanical, provenance


def _invalid_result(
    affected_kind: str,
    operation_receipt_sha256: str,
    *,
    affected_id_sha256: str | None = None,
) -> dict[str, Any]:
    return {
        "affected_kind": affected_kind,
        "affected_id_sha256": affected_id_sha256
        or _invalid_affected_id_sha256(affected_kind, operation_receipt_sha256),
        "operation_receipt_sha256": operation_receipt_sha256,
        "classification": "receipt_invalid",
        "operation_receipt_mac_or_signature_verified": False,
        "exact_human_approval_reference_present": False,
        "exact_human_approval_claim_verified": False,
        "legacy_actor_present": False,
        "unsupported_affirmation_present": False,
        "mechanical_equality_proven": False,
        "provenance_facts_proven": False,
        "related_fidelity_receipt_valid": False,
        "private_content_read": False,
        "private_identifier_echoed": False,
        "receipt_path_echoed": False,
    }


def _inspect_raw_operation_receipt(
    root: Path,
    *,
    archive_id: str,
    archive_identity_sha256: str,
    affected_kind: str,
    raw: bytes,
    key: bytearray | None,
    approval_claim: _ClaimedExactHumanApproval | None = None,
) -> dict[str, Any]:
    operation_receipt_sha256 = _sha256(raw)
    try:
        document = _parse_json(raw)
    except ApprovalIntegrityError:
        return _invalid_result(affected_kind, operation_receipt_sha256)
    shape_valid, affected_id = _operation_shape(
        document, affected_kind=affected_kind, archive_id=archive_id
    )
    if not shape_valid or affected_id is None:
        stable_affected_id = _safe_affected_id_from_document(
            document, affected_kind
        )
        return _invalid_result(
            affected_kind,
            operation_receipt_sha256,
            affected_id_sha256=(
                approval_integrity_affected_id_sha256(
                    affected_kind, stable_affected_id
                )
                if stable_affected_id is not None
                else None
            ),
        )
    affected_id_sha256 = approval_integrity_affected_id_sha256(
        affected_kind, affected_id
    )
    legacy_actor = _legacy_actor_present(document)
    unsupported_affirmation = _unsupported_affirmation_present(document)
    envelope = document.get("exact_human_approval")
    exact_reference_present = envelope is not None
    exact_verified = False
    exact_uncertain = False
    exact_invalid = False
    if envelope is not None:
        expected_operation = _KIND_OPERATION[affected_kind]
        exact_invalid = not bool(
            isinstance(envelope, Mapping)
            and set(envelope)
            == {
                "schema_version",
                "operation",
                "plan_sha256",
                "target_binding_sha256",
                "exact_human_approval",
            }
            and envelope.get("schema_version")
            == OPERATION_APPROVAL_SCHEMA_VERSION
            and envelope.get("operation") == expected_operation
            and type(envelope.get("plan_sha256")) is str
            and _SHA256_RE.fullmatch(envelope["plan_sha256"]) is not None
            and type(envelope.get("target_binding_sha256")) is str
            and _SHA256_RE.fullmatch(envelope["target_binding_sha256"])
            is not None
            and _exact_reference_shape(envelope.get("exact_human_approval"))
        )
        if not exact_invalid and (key is not None or approval_claim is not None):
            claim_status = (
                _validated_exact_reference_status(
                    root,
                    archive_id,
                    archive_identity_sha256,
                    envelope["exact_human_approval"],
                    key,
                    expected_operation=expected_operation,
                    expected_plan_sha256=envelope["plan_sha256"],
                    expected_target_binding_sha256=envelope[
                        "target_binding_sha256"
                    ],
                )
                if key is not None
                else _claim_capability_reference_status(
                    approval_claim,
                    envelope["exact_human_approval"],
                    expected_operation=expected_operation,
                    expected_plan_sha256=envelope["plan_sha256"],
                    expected_target_binding_sha256=envelope[
                        "target_binding_sha256"
                    ],
                )
            )
            exact_verified = claim_status == "succeeded"
            exact_uncertain = claim_status == "started"
            exact_invalid = claim_status in {None, "failed"}

    fidelity_claimed = False
    fidelity_valid = False
    mechanical = False
    provenance = False
    if affected_kind == "canonical_mint":
        fidelity_claimed, fidelity_valid, mechanical, provenance = _fidelity_facts(
            root,
            archive_id=archive_id,
            operation_document=document,
            affected_id=affected_id,
        )
    if exact_invalid or (fidelity_claimed and not fidelity_valid):
        classification = "receipt_invalid"
    elif exact_verified:
        classification = "exact_v0400"
    elif mechanical and provenance:
        classification = "circular_self_source"
    elif unsupported_affirmation:
        classification = "unsupported_affirmation"
    elif exact_reference_present and (
        (key is None and approval_claim is None) or exact_uncertain
    ):
        classification = "unknown"
    elif legacy_actor:
        classification = "legacy_unbound_approval"
    else:
        classification = "unknown"
    return {
        "affected_kind": affected_kind,
        "affected_id_sha256": affected_id_sha256,
        "operation_receipt_sha256": operation_receipt_sha256,
        "classification": classification,
        "operation_receipt_mac_or_signature_verified": False,
        "exact_human_approval_reference_present": exact_reference_present,
        "exact_human_approval_claim_verified": exact_verified,
        "legacy_actor_present": legacy_actor,
        "unsupported_affirmation_present": unsupported_affirmation,
        "mechanical_equality_proven": mechanical,
        "provenance_facts_proven": provenance,
        "related_fidelity_receipt_valid": fidelity_valid,
        "private_content_read": False,
        "private_identifier_echoed": False,
        "receipt_path_echoed": False,
    }


def _kind_for_relative_path(relative: PurePosixPath) -> str | None:
    parent = tuple(relative.parent.parts)
    for affected_kind, expected_parent, suffix in _RECEIPT_LOCATIONS:
        if parent == expected_parent and relative.name.endswith(suffix):
            return affected_kind
    return None


def _resolve_operation_receipt(
    root: Path,
    operation_receipt: Path | str,
) -> tuple[Path, str]:
    try:
        supplied = Path(operation_receipt)
        candidate = supplied if supplied.is_absolute() else root.joinpath(supplied)
        absolute = candidate.absolute()
        relative = absolute.relative_to(root)
        relative_posix = PurePosixPath(*relative.parts)
    except (TypeError, ValueError, OSError):
        raise _fail("approval_integrity_operation_receipt_unsafe") from None
    affected_kind = _kind_for_relative_path(relative_posix)
    if affected_kind is None:
        raise _fail("approval_integrity_operation_receipt_unsafe")
    safe_parent = _directory_chain(
        root, tuple(relative.parts[:-1]), create=False
    )
    if safe_parent is None:
        raise _fail("approval_integrity_operation_receipt_unsafe")
    return safe_parent / relative.name, affected_kind


def inspect_approval_integrity_operation_receipt(
    archive_root: Path | str,
    operation_receipt: Path | str,
    *,
    receipt_authentication_key: bytes | bytearray | memoryview | None = None,
) -> dict[str, Any]:
    """Inspect one known receipt path and return no path or raw identifier."""

    root, archive_id, archive_identity_sha256 = _archive_identity(archive_root)
    key = _validated_key(receipt_authentication_key, required=False)
    try:
        path, affected_kind = _resolve_operation_receipt(root, operation_receipt)
        raw = _stable_read(path, max_bytes=_MAX_OPERATION_RECEIPT_BYTES)
        return _inspect_raw_operation_receipt(
            root,
            archive_id=archive_id,
            archive_identity_sha256=archive_identity_sha256,
            affected_kind=affected_kind,
            raw=raw,
            key=key,
        )
    finally:
        _wipe(key)


def _scan_receipts(
    root: Path,
    *,
    max_receipts: int,
) -> tuple[list[tuple[str, Path]], list[str], bool]:
    found: list[tuple[str, Path]] = []
    blocker_codes: list[str] = []
    complete = True
    limit_hit = False
    for affected_kind, parts, suffix in _RECEIPT_LOCATIONS:
        try:
            directory = _directory_chain(root, parts, create=False)
        except ApprovalIntegrityError:
            blocker_codes.append("approval_integrity_receipt_directory_unsafe")
            complete = False
            continue
        if directory is None:
            continue
        try:
            before = os.lstat(directory)
            with os.scandir(directory) as iterator:
                for entry in iterator:
                    if not entry.name.endswith(suffix):
                        continue
                    try:
                        info = entry.stat(follow_symlinks=False)
                    except OSError:
                        blocker_codes.append(
                            "approval_integrity_receipt_set_unstable"
                        )
                        complete = False
                        continue
                    if _is_reparse(info) or not stat.S_ISREG(info.st_mode):
                        blocker_codes.append(
                            "approval_integrity_receipt_entry_unsafe"
                        )
                        complete = False
                        continue
                    found.append((affected_kind, Path(entry.path)))
                    if len(found) > max_receipts:
                        limit_hit = True
                        break
            after = os.lstat(directory)
            if (
                not _same_file(before, after)
                or getattr(before, "st_mtime_ns", None)
                != getattr(after, "st_mtime_ns", None)
            ):
                blocker_codes.append("approval_integrity_receipt_set_unstable")
                complete = False
        except OSError:
            blocker_codes.append("approval_integrity_receipt_directory_unsafe")
            complete = False
        if limit_hit:
            break
    if limit_hit:
        found = found[:max_receipts]
        blocker_codes.append("approval_integrity_receipt_limit_exceeded")
        complete = False
    return found, sorted(set(blocker_codes)), complete


def audit_approval_integrity(
    archive_root: Path | str,
    *,
    max_receipts: int = _DEFAULT_MAX_RECEIPTS,
    receipt_authentication_key: bytes | bytearray | memoryview | None = None,
) -> dict[str, Any]:
    """Classify the bounded legacy receipt set without reading artifact bytes."""

    if type(max_receipts) is not int or not 1 <= max_receipts <= 10_000:
        raise _fail("approval_integrity_argument_invalid")
    root, archive_id, archive_identity_sha256 = _archive_identity(archive_root)
    key = _validated_key(receipt_authentication_key, required=False)
    try:
        paths, blocker_codes, complete = _scan_receipts(
            root, max_receipts=max_receipts
        )
        results: list[dict[str, Any]] = []
        for affected_kind, path in paths:
            try:
                raw = _stable_read(path, max_bytes=_MAX_OPERATION_RECEIPT_BYTES)
                result = _inspect_raw_operation_receipt(
                    root,
                    archive_id=archive_id,
                    archive_identity_sha256=archive_identity_sha256,
                    affected_kind=affected_kind,
                    raw=raw,
                    key=key,
                )
            except ApprovalIntegrityError:
                try:
                    raw = _stable_read(path, max_bytes=_MAX_OPERATION_RECEIPT_BYTES)
                    operation_sha256 = _sha256(raw)
                except ApprovalIntegrityError:
                    complete = False
                    blocker_codes.append(
                        "approval_integrity_receipt_read_failed"
                    )
                    continue
                result = _invalid_result(affected_kind, operation_sha256)
            results.append(result)
        results.sort(
            key=lambda item: (
                item["affected_kind"], item["operation_receipt_sha256"]
            )
        )
        counts = {classification: 0 for classification in CLASSIFICATIONS}
        for item in results:
            counts[item["classification"]] += 1
        blockers = sorted(set(blocker_codes))
        return {
            "schema_version": AUDIT_SCHEMA_VERSION,
            "ok": complete and not blockers,
            "complete": complete and not blockers,
            "bounded": True,
            "receipt_limit": max_receipts,
            "receipt_count": len(results),
            "classification_counts": counts,
            "results": results,
            "blocker_codes": blockers,
            "operation_receipts_authenticated": False,
            "exact_human_approval_claims_checked": key is not None,
            "privacy": {
                "private_content_read": False,
                "private_content_echoed": False,
                "private_identifier_echoed": False,
                "receipt_path_echoed": False,
            },
        }
    finally:
        _wipe(key)


def _genesis_digest(affected_kind: str, affected_id_sha256: str) -> str:
    return _domain_digest(
        _GENESIS_DOMAIN,
        {
            "affected_kind": affected_kind,
            "affected_id_sha256": affected_id_sha256,
        },
    )


def _overlay_directory(
    root: Path,
    affected_id_sha256: str,
    *,
    create: bool,
) -> Path | None:
    if type(affected_id_sha256) is not str or _SHA256_RE.fullmatch(
        affected_id_sha256
    ) is None:
        raise _fail("approval_integrity_argument_invalid")
    return _directory_chain(
        root,
        (
            "receipts",
            "approval-integrity",
            "overlays",
            affected_id_sha256.removeprefix("sha256:"),
        ),
        create=create,
    )


def _entry_core(document: Mapping[str, Any]) -> dict[str, Any]:
    core = dict(document)
    core.pop("entry_digest", None)
    core.pop("authentication", None)
    return core


def _entry_digest(document: Mapping[str, Any]) -> str:
    return _domain_digest(_ENTRY_DIGEST_DOMAIN, _entry_core(document))


def _entry_mac(
    document: Mapping[str, Any],
    key: bytes | bytearray,
) -> str:
    return "hmac-sha256:" + hmac.new(
        key,
        _ENTRY_MAC_DOMAIN + _entry_mac_payload(document),
        hashlib.sha256,
    ).hexdigest()


def _entry_mac_payload(document: Mapping[str, Any]) -> bytes:
    payload = dict(document)
    payload.pop("authentication", None)
    return _canonical_bytes(payload)


def _entry_mac_with_claim(
    document: Mapping[str, Any],
    approval_claim: _ClaimedExactHumanApproval,
) -> str:
    try:
        return approval_claim.approval_integrity_mac(
            _entry_mac_payload(document)
        )
    except ExactHumanApprovalError:
        raise _fail("approval_integrity_approval_claim_invalid") from None


def _entry_mac_matches_claim(
    document: Mapping[str, Any],
    expected_mac: str,
    approval_claim: _ClaimedExactHumanApproval,
) -> bool:
    try:
        return approval_claim.approval_integrity_mac_matches(
            _entry_mac_payload(document), expected_mac
        )
    except ExactHumanApprovalError:
        raise _fail("approval_integrity_approval_claim_invalid") from None


def _timestamp(clock: Callable[[], datetime]) -> str:
    try:
        value = clock()
    except BaseException:
        raise _fail("approval_integrity_time_invalid") from None
    if type(value) is not datetime or value.tzinfo is None:
        raise _fail("approval_integrity_time_invalid")
    return value.astimezone(timezone.utc).isoformat(
        timespec="microseconds"
    ).replace("+00:00", "Z")


def approval_integrity_review_binding_codes(state: str) -> tuple[str, ...]:
    if state not in OVERLAY_STATES:
        raise _fail("approval_integrity_overlay_state_invalid")
    return tuple(
        sorted(
            {
                "affected_binding_verified",
                "append_only_overlay",
                "operation_receipt_digest_verified",
                f"transition_{state}",
            }
        )
    )


def approval_integrity_warning_codes(
    classification: str,
    state: str,
) -> tuple[str, ...]:
    if classification not in CLASSIFICATIONS or state not in OVERLAY_STATES:
        raise _fail("approval_integrity_argument_invalid")
    values = {
        "operation_receipt_not_authenticated",
        f"classification_{classification}",
    }
    if state == "withdrawn":
        values.add("withdrawn_guard_blocks_future_writes")
    return tuple(sorted(values))


def _overlay_plan_authority(
    *,
    archive_identity_sha256: str,
    operation_receipt_sha256: str,
    affected_kind: str,
    affected_id_sha256: str,
    classification: str,
    state: str,
    prior_overlay_digest: str,
) -> dict[str, Any]:
    return {
        "schema_version": OVERLAY_PLAN_SCHEMA_VERSION,
        "archive_identity_sha256": archive_identity_sha256,
        "operation_receipt_sha256": operation_receipt_sha256,
        "operation_receipt_mac_or_signature_verified": False,
        "affected_kind": affected_kind,
        "affected_id_sha256": affected_id_sha256,
        "classification": classification,
        "state": state,
        "prior_overlay_digest": prior_overlay_digest,
        "target_binding_sha256": affected_id_sha256,
        "review_binding_codes": list(
            approval_integrity_review_binding_codes(state)
        ),
        "warning_codes": list(
            approval_integrity_warning_codes(classification, state)
        ),
        "private_content_read": False,
        "private_identifier_echoed": False,
        "receipt_path_echoed": False,
    }


def _validate_overlay_entry(
    root: Path,
    *,
    archive_id: str,
    archive_identity_sha256: str,
    affected_kind: str,
    affected_id_sha256: str,
    raw: bytes,
    filename: str,
    key: bytearray | None,
    approval_claim: _ClaimedExactHumanApproval | None = None,
) -> dict[str, Any]:
    if (key is None) == (approval_claim is None):
        raise _fail("approval_integrity_overlay_ledger_invalid")
    document = _parse_json(raw)
    expected_keys = {
        "schema_version",
        "entry_digest",
        "archive_identity_sha256",
        "operation_receipt_sha256",
        "operation_receipt_mac_or_signature_verified",
        "affected_kind",
        "affected_id_sha256",
        "classification_at_transition",
        "state",
        "prior_overlay_digest",
        "transition_plan_sha256",
        "target_binding_sha256",
        "exact_human_approval",
        "created_at",
        "private_content_read",
        "private_identifier_echoed",
        "authentication",
    }
    if set(document) != expected_keys:
        raise _fail("approval_integrity_overlay_ledger_invalid")
    for name in (
        "entry_digest",
        "archive_identity_sha256",
        "operation_receipt_sha256",
        "affected_id_sha256",
        "prior_overlay_digest",
        "transition_plan_sha256",
        "target_binding_sha256",
    ):
        if type(document.get(name)) is not str or _SHA256_RE.fullmatch(
            document[name]
        ) is None:
            raise _fail("approval_integrity_overlay_ledger_invalid")
    if (
        document.get("schema_version") != OVERLAY_ENTRY_SCHEMA_VERSION
        or document.get("archive_identity_sha256")
        != archive_identity_sha256
        or document.get("affected_kind") != affected_kind
        or document.get("affected_id_sha256") != affected_id_sha256
        or document.get("target_binding_sha256") != affected_id_sha256
        or document.get("classification_at_transition") not in CLASSIFICATIONS
        or document.get("state") not in OVERLAY_STATES
        or document.get("operation_receipt_mac_or_signature_verified") is not False
        or document.get("private_content_read") is not False
        or document.get("private_identifier_echoed") is not False
        or not _canonical_overlay_timestamp(document.get("created_at"))
        or not _exact_reference_shape(document.get("exact_human_approval"))
    ):
        raise _fail("approval_integrity_overlay_ledger_invalid")
    expected_digest = _entry_digest(document)
    if not hmac.compare_digest(document["entry_digest"], expected_digest):
        raise _fail("approval_integrity_overlay_ledger_invalid")
    expected_plan_sha256 = _domain_digest(
        _PLAN_DOMAIN,
        _overlay_plan_authority(
            archive_identity_sha256=archive_identity_sha256,
            operation_receipt_sha256=document["operation_receipt_sha256"],
            affected_kind=affected_kind,
            affected_id_sha256=affected_id_sha256,
            classification=document["classification_at_transition"],
            state=document["state"],
            prior_overlay_digest=document["prior_overlay_digest"],
        ),
    )
    if not hmac.compare_digest(
        document["transition_plan_sha256"], expected_plan_sha256
    ):
        raise _fail("approval_integrity_overlay_ledger_invalid")
    if filename != (
        expected_digest.removeprefix("sha256:") + ".approval-integrity.json"
    ):
        raise _fail("approval_integrity_overlay_ledger_invalid")
    authentication = document.get("authentication")
    if not isinstance(authentication, Mapping) or set(authentication) != {
        "schema_version",
        "algorithm",
        "mac",
    }:
        raise _fail("approval_integrity_overlay_ledger_invalid")
    mac = authentication.get("mac")
    if (
        authentication.get("schema_version")
        != OVERLAY_AUTHENTICATION_SCHEMA_VERSION
        or authentication.get("algorithm") != "hmac-sha256"
        or type(mac) is not str
        or _HMAC_RE.fullmatch(mac) is None
        or not (
            hmac.compare_digest(mac, _entry_mac(document, key))
            if key is not None
            else _entry_mac_matches_claim(document, mac, approval_claim)
        )
    ):
        raise _fail("approval_integrity_overlay_ledger_invalid")
    if not hmac.compare_digest(raw, _canonical_bytes(document)):
        raise _fail("approval_integrity_overlay_ledger_invalid")
    reference_status = (
        _validated_exact_reference_status(
            root,
            archive_id,
            archive_identity_sha256,
            document["exact_human_approval"],
            key,
            expected_operation=ExactHumanApprovalOperation.integrity_repair.value,
            expected_plan_sha256=document["transition_plan_sha256"],
            expected_target_binding_sha256=affected_id_sha256,
        )
        if key is not None
        else _claim_capability_reference_status(
            approval_claim,
            document["exact_human_approval"],
            expected_operation=ExactHumanApprovalOperation.integrity_repair.value,
            expected_plan_sha256=document["transition_plan_sha256"],
            expected_target_binding_sha256=affected_id_sha256,
        )
    )
    if reference_status != "succeeded":
        raise _fail("approval_integrity_overlay_ledger_invalid")
    return document


def _guard_with_key(
    root: Path,
    *,
    archive_id: str,
    archive_identity_sha256: str,
    affected_kind: str,
    affected_id_sha256: str,
    key: bytearray | None,
    max_overlays: int,
    approval_claim: _ClaimedExactHumanApproval | None = None,
) -> dict[str, Any]:
    if (key is None) == (approval_claim is None):
        raise _fail("approval_integrity_overlay_ledger_invalid")
    genesis = _genesis_digest(affected_kind, affected_id_sha256)
    blocker_codes: list[str] = []
    entries: list[dict[str, Any]] = []
    try:
        directory = _overlay_directory(
            root, affected_id_sha256, create=False
        )
    except ApprovalIntegrityError:
        directory = None
        blocker_codes.append("approval_integrity_overlay_directory_unsafe")
    if directory is not None and not blocker_codes:
        try:
            before = os.lstat(directory)
            scanned: list[os.DirEntry[str]] = []
            with os.scandir(directory) as iterator:
                for item in iterator:
                    scanned.append(item)
                    if len(scanned) > max_overlays:
                        break
            limit_hit = len(scanned) > max_overlays
            if limit_hit:
                blocker_codes.append("approval_integrity_overlay_limit_exceeded")
                scanned = scanned[:max_overlays]
            for item in scanned:
                try:
                    info = item.stat(follow_symlinks=False)
                except OSError:
                    blocker_codes.append("approval_integrity_overlay_entry_unsafe")
                    continue
                if (
                    _is_reparse(info)
                    or not stat.S_ISREG(info.st_mode)
                    or not item.name.endswith(".approval-integrity.json")
                ):
                    blocker_codes.append("approval_integrity_overlay_entry_unsafe")
                    continue
                try:
                    raw = _stable_read(
                        Path(item.path), max_bytes=_MAX_OVERLAY_ENTRY_BYTES
                    )
                    entries.append(
                        _validate_overlay_entry(
                            root,
                            archive_id=archive_id,
                            archive_identity_sha256=archive_identity_sha256,
                            affected_kind=affected_kind,
                            affected_id_sha256=affected_id_sha256,
                            raw=raw,
                            filename=item.name,
                            key=key,
                            approval_claim=approval_claim,
                        )
                    )
                except ApprovalIntegrityError:
                    blocker_codes.append("approval_integrity_overlay_entry_invalid")
            after = os.lstat(directory)
            if (
                not _same_file(before, after)
                or getattr(before, "st_mtime_ns", None)
                != getattr(after, "st_mtime_ns", None)
            ):
                blocker_codes.append("approval_integrity_overlay_set_unstable")
        except OSError:
            blocker_codes.append("approval_integrity_overlay_directory_unsafe")

    latest: dict[str, Any] | None = None
    if not blocker_codes:
        by_digest: dict[str, dict[str, Any]] = {}
        children: dict[str, list[str]] = {}
        for entry in entries:
            digest = entry["entry_digest"]
            if digest in by_digest:
                blocker_codes.append("approval_integrity_overlay_duplicate")
                break
            by_digest[digest] = entry
            children.setdefault(entry["prior_overlay_digest"], []).append(digest)
        if not blocker_codes:
            for prior, child_digests in children.items():
                if prior != genesis and prior not in by_digest:
                    blocker_codes.append(
                        "approval_integrity_overlay_chain_disconnected"
                    )
                    break
                if len(child_digests) != 1:
                    blocker_codes.append("approval_integrity_overlay_chain_forked")
                    break
        if not blocker_codes:
            visited: set[str] = set()
            current = genesis
            while current in children:
                child = children[current][0]
                if child in visited:
                    blocker_codes.append("approval_integrity_overlay_chain_cycle")
                    break
                visited.add(child)
                current = child
            if not blocker_codes and len(visited) != len(entries):
                blocker_codes.append(
                    "approval_integrity_overlay_chain_disconnected"
                )
            elif not blocker_codes and current != genesis:
                latest = by_digest[current]

    blockers = sorted(set(blocker_codes))
    integrity_ok = not blockers
    current_digest = (
        latest["entry_digest"] if integrity_ok and latest is not None else genesis
        if integrity_ok
        else None
    )
    current_state = latest["state"] if integrity_ok and latest is not None else None
    active_block = bool(current_state in BLOCKING_OVERLAY_STATES)
    return {
        "schema_version": OVERLAY_GUARD_SCHEMA_VERSION,
        "ok": integrity_ok,
        "allowed": integrity_ok and not active_block,
        "blocked": (not integrity_ok) or active_block,
        "affected_kind": affected_kind,
        "affected_id_sha256": affected_id_sha256,
        "current_overlay_digest": current_digest,
        "current_state": current_state,
        "entry_count": len(entries),
        "blocker_codes": blockers
        if blockers
        else ([f"approval_integrity_{current_state}"] if active_block else []),
        "operation_receipts_authenticated": False,
        "overlay_entries_hmac_verified": integrity_ok and bool(entries),
        "private_content_read": False,
        "private_identifier_echoed": False,
        "receipt_path_echoed": False,
    }


def approval_integrity_guard(
    archive_root: Path | str,
    *,
    affected_kind: str,
    affected_id_sha256: str,
    receipt_authentication_key: bytes | bytearray | memoryview,
    max_overlays: int = _DEFAULT_MAX_OVERLAYS,
) -> dict[str, Any]:
    """Fail closed when the target overlay is invalid or actively blocked."""

    if (
        affected_kind not in AFFECTED_KINDS
        or type(affected_id_sha256) is not str
        or _SHA256_RE.fullmatch(affected_id_sha256) is None
        or type(max_overlays) is not int
        or not 1 <= max_overlays <= 10_000
    ):
        raise _fail("approval_integrity_argument_invalid")
    root, archive_id, archive_identity_sha256 = _archive_identity(archive_root)
    key = _validated_key(receipt_authentication_key, required=True)
    assert key is not None
    try:
        return _guard_with_key(
            root,
            archive_id=archive_id,
            archive_identity_sha256=archive_identity_sha256,
            affected_kind=affected_kind,
            affected_id_sha256=affected_id_sha256,
            key=key,
            max_overlays=max_overlays,
        )
    finally:
        _wipe(key)


def _plan_with_key(
    root: Path,
    *,
    archive_id: str,
    archive_identity_sha256: str,
    operation_receipt: Path | str,
    expected_operation_receipt_sha256: str,
    affected_kind: str,
    affected_id_sha256: str,
    state: str,
    expected_current_overlay_digest: str | None,
    key: bytearray | None,
    max_overlays: int,
    approval_claim: _ClaimedExactHumanApproval | None = None,
) -> dict[str, Any]:
    if (key is None) == (approval_claim is None):
        raise _fail("approval_integrity_argument_invalid")
    if (
        affected_kind not in AFFECTED_KINDS
        or type(affected_id_sha256) is not str
        or _SHA256_RE.fullmatch(affected_id_sha256) is None
        or type(expected_operation_receipt_sha256) is not str
        or _SHA256_RE.fullmatch(expected_operation_receipt_sha256) is None
    ):
        raise _fail("approval_integrity_argument_invalid")
    if state not in OVERLAY_STATES:
        raise _fail("approval_integrity_overlay_state_invalid")
    if expected_current_overlay_digest is not None and (
        type(expected_current_overlay_digest) is not str
        or _SHA256_RE.fullmatch(expected_current_overlay_digest) is None
    ):
        raise _fail("approval_integrity_argument_invalid")
    path, actual_kind = _resolve_operation_receipt(root, operation_receipt)
    if actual_kind != affected_kind:
        raise _fail("approval_integrity_affected_binding_mismatch")
    raw = _stable_read(path, max_bytes=_MAX_OPERATION_RECEIPT_BYTES)
    actual_operation_receipt_sha256 = _sha256(raw)
    if not hmac.compare_digest(
        actual_operation_receipt_sha256, expected_operation_receipt_sha256
    ):
        raise _fail("approval_integrity_operation_receipt_sha256_mismatch")
    inspection = _inspect_raw_operation_receipt(
        root,
        archive_id=archive_id,
        archive_identity_sha256=archive_identity_sha256,
        affected_kind=affected_kind,
        raw=raw,
        key=key,
        approval_claim=approval_claim,
    )
    if not hmac.compare_digest(
        inspection["affected_id_sha256"], affected_id_sha256
    ):
        raise _fail("approval_integrity_affected_binding_mismatch")
    guard = _guard_with_key(
        root,
        archive_id=archive_id,
        archive_identity_sha256=archive_identity_sha256,
        affected_kind=affected_kind,
        affected_id_sha256=affected_id_sha256,
        key=key,
        max_overlays=max_overlays,
        approval_claim=approval_claim,
    )
    if not guard["ok"] or guard["current_overlay_digest"] is None:
        raise _fail("approval_integrity_overlay_ledger_invalid")
    current_digest = guard["current_overlay_digest"]
    if expected_current_overlay_digest is not None and not hmac.compare_digest(
        current_digest, expected_current_overlay_digest
    ):
        raise _fail("approval_integrity_overlay_expected_current_mismatch")
    authority = _overlay_plan_authority(
        archive_identity_sha256=archive_identity_sha256,
        operation_receipt_sha256=actual_operation_receipt_sha256,
        affected_kind=affected_kind,
        affected_id_sha256=affected_id_sha256,
        classification=inspection["classification"],
        state=state,
        prior_overlay_digest=current_digest,
    )
    plan_sha256 = _domain_digest(_PLAN_DOMAIN, authority)
    return {
        **authority,
        "ok": True,
        "dry_run": True,
        "approval_required_for_write": True,
        "plan_sha256": plan_sha256,
    }


def plan_approval_integrity_overlay(
    archive_root: Path | str,
    *,
    operation_receipt: Path | str,
    expected_operation_receipt_sha256: str,
    affected_kind: str,
    affected_id_sha256: str,
    state: str,
    receipt_authentication_key: bytes | bytearray | memoryview,
    expected_current_overlay_digest: str | None = None,
    max_overlays: int = _DEFAULT_MAX_OVERLAYS,
) -> dict[str, Any]:
    """Plan one append-only transition; no approval claim is consumed."""

    if type(max_overlays) is not int or not 1 <= max_overlays <= 10_000:
        raise _fail("approval_integrity_argument_invalid")
    root, archive_id, archive_identity_sha256 = _archive_identity(archive_root)
    key = _validated_key(receipt_authentication_key, required=True)
    assert key is not None
    try:
        return _plan_with_key(
            root,
            archive_id=archive_id,
            archive_identity_sha256=archive_identity_sha256,
            operation_receipt=operation_receipt,
            expected_operation_receipt_sha256=expected_operation_receipt_sha256,
            affected_kind=affected_kind,
            affected_id_sha256=affected_id_sha256,
            state=state,
            expected_current_overlay_digest=expected_current_overlay_digest,
            key=key,
            max_overlays=max_overlays,
        )
    finally:
        _wipe(key)


@dataclass
class _TargetLock:
    path: Path
    info: os.stat_result | None = None

    def acquire(self) -> None:
        descriptor: int | None = None
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_BINARY"):
                flags |= os.O_BINARY
            descriptor = os.open(self.path, flags, 0o600)
            os.write(descriptor, b"approval-integrity-lock\n")
            os.fsync(descriptor)
            self.info = os.fstat(descriptor)
        except FileExistsError:
            raise _fail("approval_integrity_overlay_lock_held") from None
        except ApprovalIntegrityError:
            raise
        except OSError:
            raise _fail("approval_integrity_overlay_commit_failed") from None
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass

    def release(self) -> None:
        if self.info is None:
            return
        try:
            current = os.lstat(self.path)
            if (
                not _is_reparse(current)
                and stat.S_ISREG(current.st_mode)
                and _same_file(self.info, current)
            ):
                self.path.unlink()
        except OSError:
            pass
        self.info = None


def _target_lock(root: Path, affected_id_sha256: str) -> _TargetLock:
    directory = _directory_chain(
        root, ("receipts", "approval-integrity", ".locks"), create=True
    )
    if directory is None:
        raise _fail("approval_integrity_overlay_commit_failed")
    return _TargetLock(
        directory / f"{affected_id_sha256.removeprefix('sha256:')}.lock"
    )


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
        raise _fail("approval_integrity_overlay_replayed") from None
    except ApprovalIntegrityError:
        raise
    except OSError:
        raise _fail("approval_integrity_overlay_commit_failed") from None
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _publish_overlay_create_only(
    root: Path,
    *,
    affected_id_sha256: str,
    document: Mapping[str, Any],
    random_hex: Callable[[int], str],
) -> None:
    directory = _overlay_directory(root, affected_id_sha256, create=True)
    if directory is None:
        raise _fail("approval_integrity_overlay_commit_failed")
    digest_hex = document["entry_digest"].removeprefix("sha256:")
    final = directory / f"{digest_hex}.approval-integrity.json"
    try:
        suffix = random_hex(8)
    except BaseException:
        raise _fail("approval_integrity_overlay_commit_failed") from None
    if type(suffix) is not str or re.fullmatch(r"[0-9a-f]{16}", suffix) is None:
        raise _fail("approval_integrity_overlay_commit_failed")
    temporary = directory / f".{digest_hex}.tmp-{suffix}"
    raw = _canonical_bytes(document)
    linked = False
    try:
        _exclusive_write(temporary, raw)
        try:
            os.link(temporary, final)
            linked = True
        except FileExistsError:
            raise _fail("approval_integrity_overlay_replayed") from None
        except OSError:
            raise _fail("approval_integrity_overlay_commit_failed") from None
        if not hmac.compare_digest(
            _stable_read(final, max_bytes=_MAX_OVERLAY_ENTRY_BYTES), raw
        ):
            raise _fail("approval_integrity_overlay_commit_failed")
    finally:
        try:
            info = os.lstat(temporary)
            if not _is_reparse(info) and stat.S_ISREG(info.st_mode):
                temporary.unlink()
        except OSError:
            pass
        if not linked:
            try:
                info = os.lstat(final)
                if (
                    not _is_reparse(info)
                    and stat.S_ISREG(info.st_mode)
                    and hmac.compare_digest(
                        _stable_read(final, max_bytes=_MAX_OVERLAY_ENTRY_BYTES),
                        raw,
                    )
                ):
                    # A successful hard link followed by an exception is still a
                    # committed append.  Never delete it during error recovery.
                    linked = True
            except (OSError, ApprovalIntegrityError):
                pass


def _build_overlay_entry(
    plan: Mapping[str, Any],
    *,
    exact_reference: Mapping[str, Any],
    created_at: str,
    approval_claim: _ClaimedExactHumanApproval,
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "schema_version": OVERLAY_ENTRY_SCHEMA_VERSION,
        "archive_identity_sha256": plan["archive_identity_sha256"],
        "operation_receipt_sha256": plan["operation_receipt_sha256"],
        "operation_receipt_mac_or_signature_verified": False,
        "affected_kind": plan["affected_kind"],
        "affected_id_sha256": plan["affected_id_sha256"],
        "classification_at_transition": plan["classification"],
        "state": plan["state"],
        "prior_overlay_digest": plan["prior_overlay_digest"],
        "transition_plan_sha256": plan["plan_sha256"],
        "target_binding_sha256": plan["target_binding_sha256"],
        "exact_human_approval": dict(exact_reference),
        "created_at": created_at,
        "private_content_read": False,
        "private_identifier_echoed": False,
    }
    document["entry_digest"] = _entry_digest(document)
    document["authentication"] = {
        "schema_version": OVERLAY_AUTHENTICATION_SCHEMA_VERSION,
        "algorithm": "hmac-sha256",
        "mac": _entry_mac_with_claim(document, approval_claim),
    }
    return document


def create_approval_integrity_overlay(
    archive_root: Path | str,
    *,
    operation_receipt: Path | str,
    expected_operation_receipt_sha256: str,
    affected_kind: str,
    affected_id_sha256: str,
    state: str,
    expected_current_overlay_digest: str,
    expected_plan_sha256: str,
    approval_claim: _ClaimedExactHumanApproval,
    approval_context: ExactHumanApprovalContext,
    max_overlays: int = _DEFAULT_MAX_OVERLAYS,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    random_hex: Callable[[int], str] = secrets.token_hex,
) -> dict[str, Any]:
    """Append one overlay only after rechecking an exact started claim.

    Claim finalization belongs to the private exact-human workflow.  A
    successful return has ``ok=True`` so that orchestrator can finalize once;
    an exception or process crash deliberately leaves the claim ``started``
    and the newly visible overlay (if any) therefore fails the future guard
    closed until reconciled.
    """

    if (
        type(expected_current_overlay_digest) is not str
        or _SHA256_RE.fullmatch(expected_current_overlay_digest) is None
    ):
        raise _fail("approval_integrity_overlay_expected_current_required")
    if type(expected_plan_sha256) is not str or _SHA256_RE.fullmatch(
        expected_plan_sha256
    ) is None:
        raise _fail("approval_integrity_argument_invalid")
    if (
        affected_kind not in AFFECTED_KINDS
        or type(affected_id_sha256) is not str
        or _SHA256_RE.fullmatch(affected_id_sha256) is None
        or type(expected_operation_receipt_sha256) is not str
        or _SHA256_RE.fullmatch(expected_operation_receipt_sha256) is None
        or state not in OVERLAY_STATES
    ):
        raise _fail("approval_integrity_argument_invalid")
    if type(max_overlays) is not int or not 1 <= max_overlays <= 10_000:
        raise _fail("approval_integrity_argument_invalid")
    if type(approval_claim) is not _ClaimedExactHumanApproval:
        raise _fail("approval_integrity_approval_claim_invalid")
    if type(approval_context) is not ExactHumanApprovalContext:
        raise _fail("approval_integrity_approval_context_invalid")

    root, archive_id, archive_identity_sha256 = _archive_identity(archive_root)
    try:
        approval_claim.assert_ready_for_context(approval_context)
    except ExactHumanApprovalError:
        raise _fail("approval_integrity_approval_claim_invalid") from None
    lock = _target_lock(root, affected_id_sha256)
    lock.acquire()
    try:
        plan = _plan_with_key(
            root,
            archive_id=archive_id,
            archive_identity_sha256=archive_identity_sha256,
            operation_receipt=operation_receipt,
            expected_operation_receipt_sha256=expected_operation_receipt_sha256,
            affected_kind=affected_kind,
            affected_id_sha256=affected_id_sha256,
            state=state,
            expected_current_overlay_digest=expected_current_overlay_digest,
            key=None,
            max_overlays=max_overlays,
            approval_claim=approval_claim,
        )
        if not hmac.compare_digest(plan["plan_sha256"], expected_plan_sha256):
            raise _fail("approval_integrity_overlay_plan_mismatch")
        expected_review_codes = tuple(plan["review_binding_codes"])
        expected_warning_codes = tuple(plan["warning_codes"])
        if not (
            approval_context.operation
            is ExactHumanApprovalOperation.integrity_repair
            and hmac.compare_digest(
                approval_context.archive_identity_sha256,
                archive_identity_sha256,
            )
            and hmac.compare_digest(
                approval_context.plan_sha256, plan["plan_sha256"]
            )
            and hmac.compare_digest(
                approval_context.target_binding_sha256,
                affected_id_sha256,
            )
            and approval_context.review_binding_codes
            == expected_review_codes
            and approval_context.warning_codes == expected_warning_codes
        ):
            raise _fail("approval_integrity_approval_context_invalid")
        try:
            exact_reference = approval_claim.assert_ready_for_context(
                approval_context
            )
        except ExactHumanApprovalError:
            raise _fail("approval_integrity_approval_claim_invalid") from None
        if not _exact_reference_shape(exact_reference) or (
            _claim_capability_reference_status(
                approval_claim,
                exact_reference,
                expected_operation=ExactHumanApprovalOperation.integrity_repair.value,
                expected_plan_sha256=plan["plan_sha256"],
                expected_target_binding_sha256=affected_id_sha256,
            )
            != "started"
        ):
            raise _fail("approval_integrity_approval_claim_invalid")
        entry = _build_overlay_entry(
            plan,
            exact_reference=exact_reference,
            created_at=_timestamp(clock),
            approval_claim=approval_claim,
        )
        _publish_overlay_create_only(
            root,
            affected_id_sha256=affected_id_sha256,
            document=entry,
            random_hex=random_hex,
        )
        return {
            "schema_version": OVERLAY_RESULT_SCHEMA_VERSION,
            "ok": True,
            "created": True,
            "affected_kind": affected_kind,
            "affected_id_sha256": affected_id_sha256,
            "operation_receipt_sha256": expected_operation_receipt_sha256,
            "operation_receipt_mac_or_signature_verified": False,
            "classification_at_transition": plan["classification"],
            "state": state,
            "prior_overlay_digest": expected_current_overlay_digest,
            "current_overlay_digest": entry["entry_digest"],
            "plan_sha256": expected_plan_sha256,
            "exact_human_approval": dict(exact_reference),
            "claim_status_at_return": "started",
            "claim_finalization_required": True,
            "private_content_read": False,
            "private_identifier_echoed": False,
            "receipt_path_echoed": False,
        }
    except ApprovalIntegrityError:
        raise
    except ExactHumanApprovalError:
        raise _fail("approval_integrity_approval_claim_invalid") from None
    except BaseException:
        raise _fail("approval_integrity_overlay_commit_failed") from None
    finally:
        lock.release()


__all__ = [
    "AFFECTED_KINDS",
    "AUDIT_SCHEMA_VERSION",
    "ApprovalIntegrityError",
    "BLOCKING_OVERLAY_STATES",
    "CLASSIFICATIONS",
    "OPERATION_APPROVAL_SCHEMA_VERSION",
    "OVERLAY_ENTRY_SCHEMA_VERSION",
    "OVERLAY_STATES",
    "approval_integrity_affected_id_sha256",
    "approval_integrity_guard",
    "approval_integrity_review_binding_codes",
    "approval_integrity_warning_codes",
    "audit_approval_integrity",
    "create_approval_integrity_overlay",
    "inspect_approval_integrity_operation_receipt",
    "plan_approval_integrity_overlay",
]
