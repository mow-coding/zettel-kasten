"""Exact, create-only persistence for a reviewed batch of source intakes.

This module deliberately does not reopen ``archive_services.source_intake_batch``.
That legacy function remains a metadata preview with a fixed-closed approval
branch.  The implementation below rebuilds the ordinary redacted intake plan
for every requested local file, binds every source byte digest, warning set,
receipt byte string, and target to one :class:`ExactOperationManifest`, and
then delegates checkpointing, resume, and independent verification to the
common exact-operation runner.

No source path or source body is returned in a public document.  Source bytes
are streamed only to calculate a bounded, stable SHA-256 identity; they are
never retained in a receipt.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
import stat
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from . import archive_services, operation_approval_binding, source_intake_record_exact
from .exact_human_approval import (
    CLAIMS_RELATIVE_ROOT,
    ExactHumanApprovalError,
    _ClaimedExactHumanApproval,
    _rehydrate_exact_human_approval_core,
    audit_exact_human_approval_succeeded_terminal_record_read_only,
    exact_human_approval_archive_identity_sha256,
)
from .exact_human_approval_windows import (
    ExactHumanApprovalContext,
    ExactHumanApprovalOperation,
)
from .exact_human_approval_workflow import (
    _execute_exact_human_approved_write,
    _production_key_provider,
    _resume_exact_human_approved_write_core,
)
from .exact_operation_manifest import (
    ABSENT_FIELD_SHA256,
    ExactFieldEffect,
    ExactOperationApprovalAuthority,
    ExactOperationItem,
    ExactOperationManifest,
    ExactOperationManifestError,
    ExactOperationProgress,
    FileExactOperationCheckpointStore,
    apply_exact_operation,
    exact_operation_completion_authentication_payload,
    exact_operation_execution_sha256,
    exact_operation_writer_lock,
    hash_field_value,
    load_exact_operation_final_receipt_read_only,
    validate_exact_operation_resume_checkpoint_read_only,
    verify_exact_operation,
)
from .paths import ArchivePathError, normalize_archive_relative_path


OPERATION = "source_intake_batch"
REQUEST_SCHEMA = "wom-kit/source-intake-batch-request/v0.1"
PLAN_SCHEMA = "wom-kit/source-intake-batch-exact-plan/v0.1"
RESULT_SCHEMA = "wom-kit/source-intake-batch-exact-result/v0.1"
EVIDENCE_SCHEMA = "wom-kit/source-intake-batch-exact/v2"
CAPTURE_CHAIN_SCHEMA = "wom-kit/source-intake-capture-chain/v0.1"
CAPTURE_REQUEST_SCHEMA = "wom-kit/objet-capture-batch-request/v0.1"
TARGET_KIND = "source_intake_record"
FIELD_REF = "receipt_bytes"
CAPTURE_REQUEST_TARGET_KIND = "source_intake_capture_request"
CAPTURE_REQUEST_FIELD_REF = "request_bytes"
CAPTURE_REQUESTS_ROOT = (
    "receipts/ops/source-intake-batches/capture-requests"
)

_MAX_REQUEST_BYTES = 8 * 1024 * 1024
_MAX_RECEIPT_BYTES = 8 * 1024 * 1024
_MAX_SOURCE_BYTES = 8 * 1024 * 1024 * 1024
_MAX_ITEMS = 1000
_MAX_JSON_DEPTH = 12
_MAX_JSON_NODES = 25_000
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_APPROVAL_FILENAME_RE = re.compile(r"^(approval_[0-9a-f]{32})\.json$")
_SAFE_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,199}$")
_ITEM_KEYS = frozenset({"item_id", "local_path", "source_role", "title", "mime"})
_SOURCE_ROLES = frozenset({"attachment", "context", "derived_context", "primary_source"})


class SourceIntakeBatchExactError(RuntimeError):
    """A fixed-code refusal which never contains a path or source value."""

    _CODES = {
        "source_intake_batch_archive_invalid",
        "source_intake_batch_request_invalid",
        "source_intake_batch_request_unsafe",
        "source_intake_batch_item_invalid",
        "source_intake_batch_item_limit_exceeded",
        "source_intake_batch_source_invalid",
        "source_intake_batch_source_too_large",
        "source_intake_batch_source_drifted",
        "source_intake_batch_duplicate_item",
        "source_intake_batch_duplicate_source",
        "source_intake_batch_duplicate_target",
        "source_intake_batch_capture_request_required",
        "source_intake_batch_target_unsafe",
        "source_intake_batch_target_collision",
        "source_intake_batch_completion_evidence_required",
        "source_intake_batch_plan_blocked",
        "source_intake_batch_plan_digest_mismatch",
        "source_intake_batch_approval_required",
        "source_intake_batch_resume_required",
        "source_intake_batch_resume_ambiguous",
        "source_intake_batch_resume_invalid",
        "source_intake_batch_state_drifted",
        "source_intake_batch_write_failed",
        "exact_human_approval_cancelled",
    }

    def __init__(self, code: str) -> None:
        self.code = code if code in self._CODES else "source_intake_batch_write_failed"
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"SourceIntakeBatchExactError({self.code!r})"


def _fail(code: str) -> SourceIntakeBatchExactError:
    return SourceIntakeBatchExactError(code)


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            archive_services.json_safe(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise _fail("source_intake_batch_request_invalid") from None


def _sha_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha_document(value: Any) -> str:
    return _sha_bytes(_canonical_bytes(value))


def _receipt_bytes(document: Mapping[str, Any]) -> bytes:
    try:
        raw = (
            json.dumps(
                archive_services.json_safe(dict(document)),
                indent=2,
                ensure_ascii=False,
                default=str,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise _fail("source_intake_batch_item_invalid") from None
    if len(raw) > _MAX_RECEIPT_BYTES:
        raise _fail("source_intake_batch_item_invalid")
    return raw


def _strict_json_object(raw: bytes) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_json_member")
            result[key] = value
        return result

    try:
        loaded = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                ValueError("non_finite_json_number")
            ),
        )
    except (UnicodeError, ValueError, json.JSONDecodeError):
        raise _fail("source_intake_batch_request_invalid") from None
    if not isinstance(loaded, dict):
        raise _fail("source_intake_batch_request_invalid")
    return loaded


def _validate_json_bounds(value: Any) -> None:
    remaining = _MAX_JSON_NODES

    def visit(item: Any, depth: int) -> None:
        nonlocal remaining
        remaining -= 1
        if remaining < 0 or depth > _MAX_JSON_DEPTH:
            raise _fail("source_intake_batch_request_invalid")
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise _fail("source_intake_batch_request_invalid")
                visit(child, depth + 1)
            return
        if isinstance(item, list):
            for child in item:
                visit(child, depth + 1)
            return
        if isinstance(item, float) and not math.isfinite(item):
            raise _fail("source_intake_batch_request_invalid")
        if item is not None and not isinstance(item, (str, int, float, bool)):
            raise _fail("source_intake_batch_request_invalid")

    visit(value, 0)


def _is_link_or_reparse(info: os.stat_result) -> bool:
    marker = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return stat.S_ISLNK(info.st_mode) or bool(
        int(getattr(info, "st_file_attributes", 0)) & marker
    )


def _reject_link_or_reparse_chain(path: Path, *, code: str) -> None:
    current = path.absolute()
    while True:
        try:
            info = current.lstat()
        except OSError:
            raise _fail(code) from None
        if _is_link_or_reparse(info):
            raise _fail(code)
        parent = current.parent
        if parent == current:
            return
        current = parent


def _resolve_input_path(
    root: Path,
    value: Path | str,
    *,
    code: str,
) -> Path:
    try:
        raw = os.fspath(value)
    except TypeError:
        raise _fail(code) from None
    if not raw or "\x00" in raw:
        raise _fail(code)
    supplied = Path(raw)
    if supplied.is_absolute():
        resolved = supplied.absolute()
    else:
        try:
            normalized = normalize_archive_relative_path(raw)
        except ArchivePathError:
            raise _fail(code) from None
        resolved = root.resolve().joinpath(*normalized.split("/"))
    _reject_link_or_reparse_chain(resolved, code=code)
    try:
        canonical = resolved.resolve(strict=True)
    except (OSError, RuntimeError):
        raise _fail(code) from None
    _reject_link_or_reparse_chain(canonical, code=code)
    return canonical


def _stable_request_bytes(path: Path) -> bytes:
    _reject_link_or_reparse_chain(path, code="source_intake_batch_request_invalid")
    raw, reason = archive_services._bounded_stable_regular_file_read(
        path,
        max_bytes=_MAX_REQUEST_BYTES,
    )
    if raw is None or reason is not None:
        raise _fail("source_intake_batch_request_invalid")
    return raw


def _stat_identity(info: os.stat_result) -> tuple[int, int, int, int]:
    return (
        int(getattr(info, "st_dev", 0) or 0),
        int(getattr(info, "st_ino", 0) or 0),
        int(info.st_size),
        int(getattr(info, "st_mtime_ns", 0) or 0),
    )


def _same_file_identity(left: os.stat_result, right: os.stat_result) -> bool:
    left_dev, left_ino, *_ = _stat_identity(left)
    right_dev, right_ino, *_ = _stat_identity(right)
    return bool(
        left_dev == right_dev
        and (not left_ino or not right_ino or left_ino == right_ino)
    )


def _stable_source_digest(
    path: Path,
    *,
    expected_before: os.stat_result | None = None,
    heartbeat: Callable[[], None] | None = None,
) -> tuple[str, int, str, os.stat_result]:
    """Stream one regular source through a held handle and reject path swaps."""

    callback = heartbeat or (lambda: None)
    _reject_link_or_reparse_chain(path, code="source_intake_batch_source_invalid")
    try:
        before = os.lstat(path)
    except OSError:
        raise _fail("source_intake_batch_source_invalid") from None
    if _is_link_or_reparse(before) or not stat.S_ISREG(before.st_mode):
        raise _fail("source_intake_batch_source_invalid")
    if expected_before is not None and (
        not _same_file_identity(expected_before, before)
        or _stat_identity(expected_before) != _stat_identity(before)
    ):
        raise _fail("source_intake_batch_source_drifted")
    if int(before.st_size) > _MAX_SOURCE_BYTES:
        raise _fail("source_intake_batch_source_too_large")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(str(path), flags)
    except OSError:
        raise _fail("source_intake_batch_source_invalid") from None
    digest = hashlib.sha256()
    total = 0
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or _is_link_or_reparse(opened)
            or not _same_file_identity(before, opened)
        ):
            raise _fail("source_intake_batch_source_drifted")
        while True:
            callback()
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > _MAX_SOURCE_BYTES:
                raise _fail("source_intake_batch_source_too_large")
            digest.update(chunk)
        after_handle = os.fstat(descriptor)
    except SourceIntakeBatchExactError:
        raise
    except OSError:
        raise _fail("source_intake_batch_source_drifted") from None
    finally:
        os.close(descriptor)
    try:
        after_path = os.lstat(path)
    except OSError:
        raise _fail("source_intake_batch_source_drifted") from None
    if (
        _is_link_or_reparse(after_path)
        or not stat.S_ISREG(after_path.st_mode)
        or not _same_file_identity(opened, after_handle)
        or not _same_file_identity(opened, after_path)
        or _stat_identity(opened) != _stat_identity(after_handle)
        or _stat_identity(opened) != _stat_identity(after_path)
        or total != int(opened.st_size)
    ):
        raise _fail("source_intake_batch_source_drifted")
    identity = _sha_document(
        {
            "device": int(getattr(opened, "st_dev", 0) or 0),
            "inode": int(getattr(opened, "st_ino", 0) or 0),
            "size": total,
            "mtime_ns": int(getattr(opened, "st_mtime_ns", 0) or 0),
        }
    )
    return "sha256:" + digest.hexdigest(), total, identity, after_path


def _source_stat_before_plan(path: Path) -> os.stat_result:
    _reject_link_or_reparse_chain(path, code="source_intake_batch_source_invalid")
    try:
        info = os.lstat(path)
    except OSError:
        raise _fail("source_intake_batch_source_invalid") from None
    if _is_link_or_reparse(info) or not stat.S_ISREG(info.st_mode):
        raise _fail("source_intake_batch_source_invalid")
    if int(info.st_size) > _MAX_SOURCE_BYTES:
        raise _fail("source_intake_batch_source_too_large")
    return info


def _legacy_local_file_identity(
    archive_id: str,
    source_path: Path,
    info: os.stat_result,
) -> str:
    """Reproduce ``archive_services.source_intake_plan`` stat binding."""

    identity_material = "\0".join(
        [
            archive_id,
            os.path.normcase(str(source_path.expanduser().resolve())),
            str(getattr(info, "st_dev", 0)),
            str(getattr(info, "st_ino", 0)),
            str(info.st_size),
            str(
                getattr(
                    info,
                    "st_mtime_ns",
                    int(info.st_mtime * 1_000_000_000),
                )
            ),
        ]
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(identity_material).hexdigest()


def _validate_request(document: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    _validate_json_bounds(document)
    if set(document) != {"schema", "batch_id", "items"}:
        raise _fail("source_intake_batch_request_invalid")
    if document.get("schema") != REQUEST_SCHEMA:
        raise _fail("source_intake_batch_request_invalid")
    batch_id = document.get("batch_id")
    if (
        not isinstance(batch_id, str)
        or _SAFE_REF_RE.fullmatch(batch_id) is None
        or archive_services.source_intake_secret_like(batch_id)
    ):
        raise _fail("source_intake_batch_request_unsafe")
    raw_items = document.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise _fail("source_intake_batch_item_invalid")
    if len(raw_items) > _MAX_ITEMS:
        raise _fail("source_intake_batch_item_limit_exceeded")
    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for value in raw_items:
        if (
            not isinstance(value, dict)
            or not {"item_id", "local_path"}.issubset(value)
            or not set(value).issubset(_ITEM_KEYS)
        ):
            raise _fail("source_intake_batch_item_invalid")
        item_id = value.get("item_id")
        local_path = value.get("local_path")
        if (
            not isinstance(item_id, str)
            or _SAFE_REF_RE.fullmatch(item_id) is None
            or archive_services.source_intake_secret_like(item_id)
            or not isinstance(local_path, str)
            or not 1 <= len(local_path) <= 4096
            or "\x00" in local_path
            or archive_services.source_intake_has_provider_url(local_path)
            or archive_services.source_intake_secret_like(local_path)
        ):
            raise _fail("source_intake_batch_item_invalid")
        if item_id in seen_ids:
            raise _fail("source_intake_batch_duplicate_item")
        seen_ids.add(item_id)
        role = value.get("source_role", archive_services.SOURCE_INTAKE_DEFAULT_ROLE)
        if not isinstance(role, str) or role not in _SOURCE_ROLES:
            raise _fail("source_intake_batch_item_invalid")
        for key, maximum in (("title", 500), ("mime", 200)):
            scalar = value.get(key)
            if scalar is not None and (
                not isinstance(scalar, str)
                or not 1 <= len(scalar) <= maximum
                or not archive_services.safe_source_intake_text(scalar)
            ):
                raise _fail("source_intake_batch_item_invalid")
        items.append(dict(value))
    return batch_id, items


@dataclass(frozen=True, repr=False)
class SourceIntakeBatchExactItem:
    ordinal: int
    request_item_id: str
    operation_item_id: str
    source_path: Path = field(repr=False)
    capture_staged_path: str | None = field(repr=False)
    capture_title: str | None = field(repr=False)
    request_item_sha256: str
    source_path_binding_sha256: str
    source_physical_identity_sha256: str
    source_bytes_sha256: str
    source_size_bytes: int
    source_file_identity_sha256: str
    source_intake_plan_sha256: str
    receipt_relative_path: str = field(repr=False)
    receipt_bytes: bytes = field(repr=False)
    source_basis_bytes: bytes = field(repr=False)
    warnings: tuple[str, ...]
    target_state: str

    def public_document(self) -> dict[str, Any]:
        return {
            "item_id": self.request_item_id,
            "ordinal": self.ordinal,
            "terminal_classification": self.target_state,
            "source_bytes_sha256": self.source_bytes_sha256,
            "source_size_bytes": self.source_size_bytes,
            "source_intake_plan_sha256": self.source_intake_plan_sha256,
            "receipt_bytes_sha256": _sha_bytes(self.receipt_bytes),
            "warning_count": len(self.warnings),
            "path_echoed": False,
        }


@dataclass(frozen=True, repr=False)
class PreparedObjetCaptureBatchRequest:
    operation_item_id: str
    relative_path: str = field(repr=False)
    request_bytes: bytes = field(repr=False)
    request_sha256: str
    source_basis_bytes: bytes = field(repr=False)
    chain_binding_sha256: str
    target_state: str

    def public_document(self) -> dict[str, Any]:
        return {
            "ready": True,
            "request_ref": self.relative_path,
            "request_sha256": self.request_sha256,
            "chain_binding_sha256": self.chain_binding_sha256,
            "terminal_classification": self.target_state,
            "archive_relative_digest_path_only": True,
        }


@dataclass(frozen=True, repr=False)
class SourceIntakeBatchExactPlan:
    archive_root: Path = field(repr=False)
    archive_id: str
    request_path: Path = field(repr=False)
    request_bytes_sha256: str | None
    request_document_sha256: str | None
    batch_id: str | None
    items: tuple[SourceIntakeBatchExactItem, ...] = field(repr=False)
    prepared_capture_request: PreparedObjetCaptureBatchRequest | None = field(
        repr=False
    )
    manifest: ExactOperationManifest | None = field(repr=False)
    state: str
    blockers: tuple[str, ...]

    @property
    def approveable(self) -> bool:
        return bool(
            self.manifest is not None
            and self.items
            and self.state == "ready"
            and not self.blockers
        )

    @property
    def resume_candidate(self) -> bool:
        artifact = self.prepared_capture_request
        return bool(
            self.manifest is not None
            and self.items
            and self.state in {"ready", "partial_unverified", "preexisting_unverified"}
            and all(item.target_state in {"ready_to_create", "exact_target_present"} for item in self.items)
            and (
                artifact is None
                or artifact.target_state
                in {"ready_to_create", "exact_target_present"}
            )
        )

    @property
    def warnings(self) -> tuple[str, ...]:
        return tuple(sorted({warning for item in self.items for warning in item.warnings}))

    def public_document(self) -> dict[str, Any]:
        manifest = self.manifest
        ready_count = sum(item.target_state == "ready_to_create" for item in self.items)
        exact_count = sum(item.target_state == "exact_target_present" for item in self.items)
        collision_count = sum(item.target_state == "target_collision" for item in self.items)
        artifact = self.prepared_capture_request
        return {
            "schema_version": PLAN_SCHEMA,
            "ok": self.approveable,
            "state": "ready_for_exact_human_approval" if self.approveable else self.state,
            "lifecycle_action": "source_intake_batch_exact_plan",
            "batch_id": self.batch_id,
            "plan_sha256": manifest.manifest_sha256 if manifest else None,
            "target_binding_sha256": manifest.target_set_sha256 if manifest else None,
            "source_binding_sha256": manifest.source_set_sha256 if manifest else None,
            "effect_binding_sha256": manifest.effect_set_sha256 if manifest else None,
            "request_bytes_sha256": self.request_bytes_sha256,
            "item_count": len(self.items),
            "ready_to_create_count": ready_count,
            "exact_target_present_count": exact_count,
            "target_collision_count": collision_count,
            "receipt_create_count": ready_count if self.approveable else 0,
            "warning_count": sum(len(item.warnings) for item in self.items),
            "items": [item.public_document() for item in self.items],
            "prepared_capture_request": (
                artifact.public_document()
                if artifact is not None
                else {
                    "ready": False,
                    "reason_code": "capture_sources_must_be_archive_relative",
                }
            ),
            "blockers": list(self.blockers),
            "writes_performed": False,
            "source_bytes_hashed": bool(self.items),
            "source_bytes_retained": False,
            "provider_calls_performed": False,
            "credential_material_used_for_local_authentication": False,
            "credential_values_echoed": False,
            "private_values_echoed": False,
            # The only public path is a digest-named archive-relative handoff
            # under receipts/ops; source paths and filenames remain private.
            "paths_echoed": artifact is not None,
            "absolute_paths_echoed": False,
            "source_paths_echoed": False,
        }


def _blocked_plan(
    *,
    root: Path,
    archive_id: str,
    request_path: Path,
    blocker: str,
) -> SourceIntakeBatchExactPlan:
    return SourceIntakeBatchExactPlan(
        archive_root=root,
        archive_id=archive_id,
        request_path=request_path,
        request_bytes_sha256=None,
        request_document_sha256=None,
        batch_id=None,
        items=(),
        prepared_capture_request=None,
        manifest=None,
        state="blocked",
        blockers=(blocker,),
    )


def _target_state(root: Path, relative: str, expected: bytes) -> str:
    if archive_services.objet_capture_path_chain_blockers(root, relative):
        raise _fail("source_intake_batch_target_unsafe")
    try:
        target = archive_services.archive_internal_path(root, relative)
    except archive_services.ArchiveServiceError:
        raise _fail("source_intake_batch_target_unsafe") from None
    raw, reason = archive_services._bounded_stable_regular_file_read(
        target,
        max_bytes=_MAX_RECEIPT_BYTES,
    )
    if reason == "missing":
        return "ready_to_create"
    if raw is not None and reason is None and hmac.compare_digest(raw, expected):
        return "exact_target_present"
    return "target_collision"


def _capture_staged_path(root: Path, source_path: Path) -> str | None:
    """Return a capture-safe archive-relative source ref, never an absolute path."""

    try:
        relative = source_path.relative_to(root.resolve(strict=True)).as_posix()
        normalized = normalize_archive_relative_path(relative)
    except (ArchivePathError, OSError, RuntimeError, ValueError):
        return None
    return normalized


def intake_capture_chain_binding_sha256(
    *,
    archive_id: str,
    batch_id: str,
    capture_request_sha256: str,
    item_bindings: Sequence[Mapping[str, Any]],
) -> str:
    """Bind the exact intake outputs to the downstream capture request.

    The public digest contains no paths.  Both sides construct the same basis:
    the source writer from its approved receipt payloads, and the capture
    planner from the persisted receipts plus its freshly hashed selection.
    """

    return _sha_document(
        {
            "schema": CAPTURE_CHAIN_SCHEMA,
            "archive_identity_sha256": (
                exact_human_approval_archive_identity_sha256(archive_id)
            ),
            "batch_id": batch_id,
            "capture_request_sha256": capture_request_sha256,
            "items": [dict(item) for item in item_bindings],
        }
    )


def _capture_item_binding(item: SourceIntakeBatchExactItem) -> dict[str, Any]:
    assert item.capture_staged_path is not None
    return {
        "ordinal": item.ordinal,
        "item_id": item.request_item_id,
        "staged_path_ref_sha256": _sha_bytes(
            item.capture_staged_path.encode("utf-8")
        ),
        "source_object_id": item.source_bytes_sha256,
        "source_size_bytes": item.source_size_bytes,
        "source_intake_plan_sha256": item.source_intake_plan_sha256,
        "receipt_ref_sha256": _sha_bytes(
            item.receipt_relative_path.encode("utf-8")
        ),
        "receipt_bytes_sha256": _sha_bytes(item.receipt_bytes),
    }


def _prepared_capture_request(
    root: Path,
    *,
    archive_id: str,
    batch_id: str,
    items: Sequence[SourceIntakeBatchExactItem],
) -> PreparedObjetCaptureBatchRequest | None:
    if not items or any(item.capture_staged_path is None for item in items):
        return None
    request_items: list[dict[str, Any]] = []
    for item in items:
        assert item.capture_staged_path is not None
        request_item = {
            "item_id": item.request_item_id,
            "staged_path": item.capture_staged_path,
            "source_intake_receipt_path": item.receipt_relative_path,
        }
        if item.capture_title is not None:
            request_item["title"] = item.capture_title
        request_items.append(request_item)
    request_document = {
        "schema": CAPTURE_REQUEST_SCHEMA,
        "batch_id": batch_id,
        "items": request_items,
    }
    request_bytes = _canonical_bytes(request_document) + b"\n"
    request_sha256 = _sha_bytes(request_bytes)
    chain_binding = intake_capture_chain_binding_sha256(
        archive_id=archive_id,
        batch_id=batch_id,
        capture_request_sha256=request_sha256,
        item_bindings=[_capture_item_binding(item) for item in items],
    )
    digest = request_sha256.removeprefix("sha256:")
    relative = (
        f"{CAPTURE_REQUESTS_ROOT}/{digest}.objet-capture-request.json"
    )
    source_basis = _canonical_bytes(
        {
            "schema": "wom-kit/source-intake-capture-request-source/v0.1",
            "capture_request_sha256": request_sha256,
            "chain_binding_sha256": chain_binding,
        }
    )
    return PreparedObjetCaptureBatchRequest(
        operation_item_id=f"item:source-intake:capture-request:{digest[:20]}",
        relative_path=relative,
        request_bytes=request_bytes,
        request_sha256=request_sha256,
        source_basis_bytes=source_basis,
        chain_binding_sha256=chain_binding,
        target_state=_target_state(root, relative, request_bytes),
    )


def _build_item(
    root: Path,
    archive_id: str,
    *,
    ordinal: int,
    request_bytes_sha256: str,
    raw_item: Mapping[str, Any],
    heartbeat: Callable[[], None] | None = None,
) -> SourceIntakeBatchExactItem:
    source_path = _resolve_input_path(
        root,
        str(raw_item["local_path"]),
        code="source_intake_batch_source_invalid",
    )
    capture_staged_path = _capture_staged_path(root, source_path)
    before_plan = _source_stat_before_plan(source_path)
    source_plan = archive_services.source_intake_plan(
        root,
        local_path=source_path,
        source_role=str(raw_item.get("source_role") or archive_services.SOURCE_INTAKE_DEFAULT_ROLE),
        title=raw_item.get("title") if isinstance(raw_item.get("title"), str) else None,
        mime=raw_item.get("mime") if isinstance(raw_item.get("mime"), str) else None,
        redact_local_paths=True,
    )
    source_sha, source_size, source_identity, source_stat = _stable_source_digest(
        source_path,
        expected_before=before_plan,
        heartbeat=heartbeat,
    )
    if source_plan.get("ok") is not True:
        raise _fail("source_intake_batch_item_invalid")
    receipt_raw = _receipt_bytes(source_plan)
    try:
        validated, document_sha256 = source_intake_record_exact._validated_plan_document(
            receipt_raw,
            archive_id=archive_id,
        )
    except Exception:
        raise _fail("source_intake_batch_item_invalid") from None
    if validated != source_plan:
        raise _fail("source_intake_batch_item_invalid")
    metadata = source_plan.get("source_metadata")
    expected_legacy_identity = _legacy_local_file_identity(
        archive_id,
        source_path,
        source_stat,
    )
    if (
        not isinstance(metadata, dict)
        or metadata.get("size_bytes") != source_size
        or metadata.get("local_file_identity_sha256") != expected_legacy_identity
        or metadata.get("local_file_identity_kind")
        != "path_stat_fingerprint_not_content_identity"
    ):
        raise _fail("source_intake_batch_source_drifted")
    receipt_relative = archive_services.source_intake_record_path(document_sha256)
    request_item_sha256 = _sha_document(dict(raw_item))
    source_path_binding_sha256 = _sha_bytes(
        os.path.normcase(str(source_path.absolute())).encode("utf-8")
    )
    source_device = int(getattr(source_stat, "st_dev", 0) or 0)
    source_inode = int(getattr(source_stat, "st_ino", 0) or 0)
    source_physical_identity_sha256 = (
        _sha_document(
            {
                "schema": "wom-kit/source-intake-batch-physical-file/v0.1",
                "device": source_device,
                "inode": source_inode,
            }
        )
        if source_inode
        else source_path_binding_sha256
    )
    warnings = tuple(
        str(value)
        for value in source_plan.get("warnings", [])
        if isinstance(value, str)
    )
    warning_set_sha256 = _sha_document(list(warnings))
    receipt_sha256 = _sha_bytes(receipt_raw)
    source_basis = _canonical_bytes(
        {
            "schema": "wom-kit/source-intake-batch-exact-source/v0.1",
            "archive_identity_sha256": exact_human_approval_archive_identity_sha256(archive_id),
            "request_bytes_sha256": request_bytes_sha256,
            "request_item_sha256": request_item_sha256,
            "source_path_binding_sha256": source_path_binding_sha256,
            "source_physical_identity_sha256": (
                source_physical_identity_sha256
            ),
            "source_bytes_sha256": source_sha,
            "source_size_bytes": source_size,
            "source_file_identity_sha256": source_identity,
            "source_intake_plan_sha256": document_sha256,
            "receipt_bytes_sha256": receipt_sha256,
            "target_ref_sha256": _sha_bytes(receipt_relative.encode("utf-8")),
            "warning_set_sha256": warning_set_sha256,
        }
    )
    item_id_digest = hashlib.sha256(
        (str(raw_item["item_id"]) + "\0" + request_item_sha256).encode("utf-8")
    ).hexdigest()[:20]
    return SourceIntakeBatchExactItem(
        ordinal=ordinal,
        request_item_id=str(raw_item["item_id"]),
        operation_item_id=f"item:source-intake:{ordinal:04d}:{item_id_digest}",
        source_path=source_path,
        capture_staged_path=capture_staged_path,
        capture_title=(
            str(raw_item["title"])
            if isinstance(raw_item.get("title"), str)
            else None
        ),
        request_item_sha256=request_item_sha256,
        source_path_binding_sha256=source_path_binding_sha256,
        source_physical_identity_sha256=source_physical_identity_sha256,
        source_bytes_sha256=source_sha,
        source_size_bytes=source_size,
        source_file_identity_sha256=source_identity,
        source_intake_plan_sha256=document_sha256,
        receipt_relative_path=receipt_relative,
        receipt_bytes=receipt_raw,
        source_basis_bytes=source_basis,
        warnings=warnings,
        target_state=_target_state(root, receipt_relative, receipt_raw),
    )


def plan_source_intake_batch(
    archive_root: Path | str,
    request_path: Path | str,
    *,
    heartbeat: Callable[[], None] | None = None,
) -> SourceIntakeBatchExactPlan:
    """Build one exact manifest for 1-1000 legacy-v0.1 local requests."""

    try:
        root = archive_services.require_existing_archive_root(archive_root)
        archive_id = archive_services.read_archive_id(root)
    except Exception:
        raise _fail("source_intake_batch_archive_invalid") from None
    try:
        resolved_request = _resolve_input_path(
            root,
            request_path,
            code="source_intake_batch_request_invalid",
        )
        request_raw = _stable_request_bytes(resolved_request)
        request_document = _strict_json_object(request_raw)
        batch_id, raw_items = _validate_request(request_document)
        request_bytes_sha256 = _sha_bytes(request_raw)
        request_document_sha256 = _sha_document(request_document)
        items = tuple(
            _build_item(
                root,
                archive_id,
                ordinal=index,
                request_bytes_sha256=request_bytes_sha256,
                raw_item=raw_item,
                heartbeat=heartbeat,
            )
            for index, raw_item in enumerate(raw_items)
        )
        prepared_capture_request = _prepared_capture_request(
            root,
            archive_id=archive_id,
            batch_id=batch_id,
            items=items,
        )
        target_refs = [item.receipt_relative_path for item in items]
        if prepared_capture_request is not None:
            target_refs.append(prepared_capture_request.relative_path)
        source_refs = [
            item.source_physical_identity_sha256 for item in items
        ]
        if len(source_refs) != len(set(source_refs)):
            raise _fail("source_intake_batch_duplicate_source")
        if len(target_refs) != len(set(target_refs)):
            raise _fail("source_intake_batch_duplicate_target")
        if prepared_capture_request is None:
            return SourceIntakeBatchExactPlan(
                archive_root=root,
                archive_id=archive_id,
                request_path=resolved_request,
                request_bytes_sha256=request_bytes_sha256,
                request_document_sha256=request_document_sha256,
                batch_id=batch_id,
                items=items,
                prepared_capture_request=None,
                manifest=None,
                state="blocked",
                blockers=("source_intake_batch_capture_request_required",),
            )
        archive_identity = exact_human_approval_archive_identity_sha256(archive_id)
        receipt_operation_items = tuple(
            ExactOperationItem(
                ordinal=item.ordinal,
                item_id=item.operation_item_id,
                target_kind=TARGET_KIND,
                target_ref=item.receipt_relative_path,
                target_identity_sha256=_sha_document(
                    {
                        "schema": "wom-kit/source-intake-batch-exact-target/v0.1",
                        "archive_identity_sha256": archive_identity,
                        "target_ref": item.receipt_relative_path,
                    }
                ),
                fields=(
                    ExactFieldEffect(
                        field_ref=FIELD_REF,
                        pre_sha256=ABSENT_FIELD_SHA256,
                        post_sha256=hash_field_value(item.receipt_bytes),
                        source_sha256=hash_field_value(item.source_basis_bytes),
                    ),
                ),
            )
            for item in items
        )
        support_operation_items: tuple[ExactOperationItem, ...] = ()
        if prepared_capture_request is not None:
            artifact = prepared_capture_request
            support_operation_items = (
                ExactOperationItem(
                    ordinal=len(items),
                    item_id=artifact.operation_item_id,
                    target_kind=CAPTURE_REQUEST_TARGET_KIND,
                    target_ref=artifact.relative_path,
                    target_identity_sha256=_sha_document(
                        {
                            "schema": (
                                "wom-kit/source-intake-capture-request-target/v0.1"
                            ),
                            "archive_identity_sha256": archive_identity,
                            "target_ref": artifact.relative_path,
                        }
                    ),
                    fields=(
                        ExactFieldEffect(
                            field_ref=CAPTURE_REQUEST_FIELD_REF,
                            pre_sha256=ABSENT_FIELD_SHA256,
                            post_sha256=hash_field_value(
                                artifact.request_bytes
                            ),
                            source_sha256=hash_field_value(
                                artifact.source_basis_bytes
                            ),
                        ),
                    ),
                ),
            )
        operation_items = receipt_operation_items + support_operation_items
        manifest = ExactOperationManifest.build(
            operation=OPERATION,
            archive_identity_sha256=archive_identity,
            items=operation_items,
            operation_evidence={
                "schema": EVIDENCE_SCHEMA,
                "counts": {
                    "source_item_count": len(items),
                    "receipt_byte_count": sum(len(item.receipt_bytes) for item in items),
                    "source_byte_count": sum(item.source_size_bytes for item in items),
                    "warning_count": sum(len(item.warnings) for item in items),
                    "prepared_capture_request_count": (
                        1 if prepared_capture_request is not None else 0
                    ),
                },
                "digests": {
                    "item_receipt_set_sha256": _sha_document(
                        [
                            {
                                "item_id": item.request_item_id,
                                "receipt_bytes_sha256": _sha_bytes(item.receipt_bytes),
                                "target_ref_sha256": _sha_bytes(item.receipt_relative_path.encode("utf-8")),
                            }
                            for item in items
                        ]
                    ),
                    "item_source_set_sha256": _sha_document(
                        [
                            {
                                "item_id": item.request_item_id,
                                "source_bytes_sha256": item.source_bytes_sha256,
                                "source_basis_sha256": _sha_bytes(item.source_basis_bytes),
                            }
                            for item in items
                        ]
                    ),
                    "request_bytes_sha256": request_bytes_sha256,
                    "request_document_sha256": request_document_sha256,
                    "prepared_capture_request_sha256": (
                        prepared_capture_request.request_sha256
                        if prepared_capture_request is not None
                        else _sha_document([])
                    ),
                    "intake_capture_chain_sha256": (
                        prepared_capture_request.chain_binding_sha256
                        if prepared_capture_request is not None
                        else _sha_document([])
                    ),
                    "warning_set_sha256": _sha_document(
                        [
                            {"item_id": item.request_item_id, "warnings": list(item.warnings)}
                            for item in items
                        ]
                    ),
                },
                "private_values_echoed": False,
            },
        )
    except SourceIntakeBatchExactError as error:
        try:
            safe_request = Path(os.fspath(request_path))
        except TypeError:
            safe_request = Path("invalid-source-intake-batch-request")
        return _blocked_plan(
            root=root,
            archive_id=archive_id,
            request_path=safe_request,
            blocker=error.code,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError):
        return _blocked_plan(
            root=root,
            archive_id=archive_id,
            request_path=Path("invalid-source-intake-batch-request"),
            blocker="source_intake_batch_request_invalid",
        )

    states = {item.target_state for item in items}
    if prepared_capture_request is not None:
        states.add(prepared_capture_request.target_state)
    if "target_collision" in states:
        state = "target_collision"
        blockers = ("source_intake_batch_target_collision",)
    elif states == {"ready_to_create"}:
        state = "ready"
        blockers = ()
    elif states == {"exact_target_present"}:
        state = "preexisting_unverified"
        blockers = ("source_intake_batch_completion_evidence_required",)
    else:
        state = "partial_unverified"
        blockers = ("source_intake_batch_completion_evidence_required",)
    return SourceIntakeBatchExactPlan(
        archive_root=root,
        archive_id=archive_id,
        request_path=resolved_request,
        request_bytes_sha256=request_bytes_sha256,
        request_document_sha256=request_document_sha256,
        batch_id=batch_id,
        items=items,
        prepared_capture_request=prepared_capture_request,
        manifest=manifest,
        state=state,
        blockers=blockers,
    )


def approval_context(
    plan: SourceIntakeBatchExactPlan,
    *,
    reviewer_claim: str,
    allow_resume: bool = False,
) -> ExactHumanApprovalContext:
    if (
        plan.manifest is None
        or not plan.items
        or (not plan.resume_candidate if allow_resume else not plan.approveable)
        or archive_services.safe_project_intake_actor_id(reviewer_claim) is None
    ):
        raise _fail("source_intake_batch_approval_required")
    try:
        binding = operation_approval_binding.exact_operation_manifest_approval_binding(
            plan.manifest,
            operation=ExactHumanApprovalOperation.source_intake_batch,
            archive_id=plan.archive_id,
            warnings=plan.warnings,
        )
        return binding.context(
            archive_id=plan.archive_id,
            reviewer_claim=reviewer_claim,
        )
    except Exception:
        raise _fail("source_intake_batch_approval_required") from None


def _authority(
    plan: SourceIntakeBatchExactPlan,
    claim: _ClaimedExactHumanApproval,
    context: ExactHumanApprovalContext,
    *,
    allow_resume: bool,
) -> ExactOperationApprovalAuthority:
    expected = approval_context(
        plan,
        reviewer_claim=context.reviewer_claim,
        allow_resume=allow_resume,
    )
    if context != expected or type(claim) is not _ClaimedExactHumanApproval:
        raise _fail("source_intake_batch_approval_required")
    try:
        return ExactOperationApprovalAuthority.from_reference(
            claim.assert_ready_for_context(context)
        )
    except (ExactHumanApprovalError, ExactOperationManifestError):
        raise _fail("source_intake_batch_approval_required") from None


def _item_by_operation_id(
    plan: SourceIntakeBatchExactPlan,
    item_id: str,
) -> SourceIntakeBatchExactItem:
    matches = [item for item in plan.items if item.operation_item_id == item_id]
    if len(matches) != 1:
        raise _fail("source_intake_batch_write_failed")
    return matches[0]


def _item_by_target(
    plan: SourceIntakeBatchExactPlan,
    target_ref: str,
) -> SourceIntakeBatchExactItem:
    matches = [item for item in plan.items if item.receipt_relative_path == target_ref]
    if len(matches) != 1:
        raise _fail("source_intake_batch_write_failed")
    return matches[0]


def _prepared_by_operation_id(
    plan: SourceIntakeBatchExactPlan,
    item_id: str,
) -> PreparedObjetCaptureBatchRequest | None:
    artifact = plan.prepared_capture_request
    if artifact is not None and artifact.operation_item_id == item_id:
        return artifact
    return None


def _prepared_by_target(
    plan: SourceIntakeBatchExactPlan,
    target_ref: str,
) -> PreparedObjetCaptureBatchRequest | None:
    artifact = plan.prepared_capture_request
    if artifact is not None and artifact.relative_path == target_ref:
        return artifact
    return None


def _request_items(plan: SourceIntakeBatchExactPlan) -> dict[str, dict[str, Any]]:
    if plan.request_bytes_sha256 is None:
        raise _fail("source_intake_batch_state_drifted")
    raw = _stable_request_bytes(plan.request_path)
    if not hmac.compare_digest(_sha_bytes(raw), plan.request_bytes_sha256):
        raise _fail("source_intake_batch_state_drifted")
    document = _strict_json_object(raw)
    _batch_id, raw_items = _validate_request(document)
    return {str(item["item_id"]): item for item in raw_items}


def _revalidate_item(
    plan: SourceIntakeBatchExactPlan,
    expected: SourceIntakeBatchExactItem,
    *,
    request_items: Mapping[str, Mapping[str, Any]],
    heartbeat: Callable[[], None],
) -> None:
    raw_item = request_items.get(expected.request_item_id)
    if raw_item is None or plan.request_bytes_sha256 is None:
        raise _fail("source_intake_batch_state_drifted")
    current = _build_item(
        plan.archive_root,
        plan.archive_id,
        ordinal=expected.ordinal,
        request_bytes_sha256=plan.request_bytes_sha256,
        raw_item=raw_item,
        heartbeat=heartbeat,
    )
    stable_fields = (
        "request_item_id",
        "operation_item_id",
        "request_item_sha256",
        "source_path_binding_sha256",
        "source_physical_identity_sha256",
        "source_bytes_sha256",
        "source_size_bytes",
        "source_file_identity_sha256",
        "source_intake_plan_sha256",
        "receipt_relative_path",
        "receipt_bytes",
        "source_basis_bytes",
        "warnings",
    )
    if any(getattr(current, name) != getattr(expected, name) for name in stable_fields):
        raise _fail("source_intake_batch_source_drifted")


class _Payloads:
    def __init__(self, plan: SourceIntakeBatchExactPlan) -> None:
        self.plan = plan

    def field_value(
        self,
        *,
        item_id: str,
        field_ref: str,
        state: str,
        heartbeat: Callable[[], None],
    ) -> bytes | None:
        heartbeat()
        artifact = _prepared_by_operation_id(self.plan, item_id)
        if artifact is not None:
            if field_ref != CAPTURE_REQUEST_FIELD_REF:
                raise _fail("source_intake_batch_write_failed")
            if state == "pre":
                return None
            if state == "post":
                return artifact.request_bytes
            if state == "source":
                return artifact.source_basis_bytes
            raise _fail("source_intake_batch_write_failed")
        if field_ref != FIELD_REF:
            raise _fail("source_intake_batch_write_failed")
        item = _item_by_operation_id(self.plan, item_id)
        if state == "pre":
            return None
        if state == "post":
            return item.receipt_bytes
        if state == "source":
            return item.source_basis_bytes
        raise _fail("source_intake_batch_write_failed")


class _Verifier:
    def __init__(self, plan: SourceIntakeBatchExactPlan) -> None:
        self.plan = plan

    def target_identity_sha256(
        self,
        *,
        target_kind: str,
        target_ref: str,
        heartbeat: Callable[[], None],
    ) -> str:
        heartbeat()
        if self.plan.manifest is None:
            raise _fail("source_intake_batch_write_failed")
        artifact = _prepared_by_target(self.plan, target_ref)
        if artifact is not None:
            if target_kind != CAPTURE_REQUEST_TARGET_KIND:
                raise _fail("source_intake_batch_write_failed")
            return self.plan.manifest.items[len(self.plan.items)].target_identity_sha256
        if target_kind != TARGET_KIND:
            raise _fail("source_intake_batch_write_failed")
        item = _item_by_target(self.plan, target_ref)
        return self.plan.manifest.items[item.ordinal].target_identity_sha256

    def read_field(
        self,
        *,
        target_kind: str,
        target_ref: str,
        field_ref: str,
        heartbeat: Callable[[], None],
    ) -> bytes | None:
        heartbeat()
        artifact = _prepared_by_target(self.plan, target_ref)
        if artifact is not None:
            if (
                target_kind != CAPTURE_REQUEST_TARGET_KIND
                or field_ref != CAPTURE_REQUEST_FIELD_REF
            ):
                raise _fail("source_intake_batch_write_failed")
        elif target_kind != TARGET_KIND or field_ref != FIELD_REF:
            raise _fail("source_intake_batch_write_failed")
        else:
            _item_by_target(self.plan, target_ref)
        target = _approved_lexical_target(self.plan, target_ref)
        try:
            with archive_services._hold_activity_group_evidence_file(
                self.plan.archive_root,
                target,
                max_bytes=_MAX_RECEIPT_BYTES,
            ) as held:
                raw = bytes(held["raw"])
        except FileNotFoundError:
            return None
        except (OSError, archive_services.ArchiveServiceError):
            raise _fail("source_intake_batch_target_collision")
        heartbeat()
        return raw


class _Writer:
    def __init__(
        self,
        plan: SourceIntakeBatchExactPlan,
        *,
        request_items: Mapping[str, Mapping[str, Any]],
    ) -> None:
        self.plan = plan
        # The approved request is read, bounded, hashed, parsed, and validated
        # once at the post-decision boundary.  Per-item writes still re-hash
        # the corresponding source bytes immediately before mutation, but do
        # not re-read the whole request N times.
        self.request_items = request_items

    def write_field(
        self,
        *,
        target_kind: str,
        target_ref: str,
        field_ref: str,
        value: bytes | None,
        heartbeat: Callable[[], None],
    ) -> None:
        if value is None:
            raise _fail("source_intake_batch_write_failed")
        artifact = _prepared_by_target(self.plan, target_ref)
        if artifact is not None:
            if (
                target_kind != CAPTURE_REQUEST_TARGET_KIND
                or field_ref != CAPTURE_REQUEST_FIELD_REF
                or not hmac.compare_digest(value, artifact.request_bytes)
            ):
                raise _fail("source_intake_batch_write_failed")
        else:
            if target_kind != TARGET_KIND or field_ref != FIELD_REF:
                raise _fail("source_intake_batch_write_failed")
            item = _item_by_target(self.plan, target_ref)
            if not hmac.compare_digest(value, item.receipt_bytes):
                raise _fail("source_intake_batch_write_failed")
            _revalidate_item(
                self.plan,
                item,
                request_items=self.request_items,
                heartbeat=heartbeat,
            )
        try:
            target = _approved_lexical_target(self.plan, target_ref)
            with archive_services._activity_group_bound_directory_chain(
                self.plan.archive_root,
                target.parent,
                create=True,
            ) as parent_binding:
                archive_services._write_activity_group_bytes_new_file_bound(
                    parent_binding,
                    target,
                    value,
                    heartbeat=heartbeat,
                )
        except SourceIntakeBatchExactError:
            raise
        except FileExistsError:
            raise _fail("source_intake_batch_target_collision") from None
        except OSError:
            raise _fail("source_intake_batch_write_failed") from None


def _approved_lexical_target(
    plan: SourceIntakeBatchExactPlan,
    target_ref: str,
) -> Path:
    """Build the approved target without resolving attacker-controlled parts."""
    try:
        normalized = normalize_archive_relative_path(target_ref)
    except ArchivePathError:
        raise _fail("source_intake_batch_write_failed") from None
    if not hmac.compare_digest(normalized, target_ref):
        raise _fail("source_intake_batch_write_failed")
    return plan.archive_root.joinpath(*normalized.split("/"))


def _same_manifest(
    left: SourceIntakeBatchExactPlan,
    right: SourceIntakeBatchExactPlan,
) -> bool:
    return bool(
        left.manifest is not None
        and right.manifest is not None
        and hmac.compare_digest(
            left.manifest.manifest_sha256,
            right.manifest.manifest_sha256,
        )
        and left.request_bytes_sha256 is not None
        and right.request_bytes_sha256 is not None
        and hmac.compare_digest(left.request_bytes_sha256, right.request_bytes_sha256)
    )


def _success_document(
    plan: SourceIntakeBatchExactPlan,
    core: Mapping[str, Any],
) -> dict[str, Any]:
    assert plan.manifest is not None
    artifact = plan.prepared_capture_request
    execution_sha256 = core.get("execution_sha256")
    return {
        "schema_version": RESULT_SCHEMA,
        "ok": True,
        "state": "completed",
        "lifecycle_action": "source_intake_batch_exact_write",
        "batch_id": plan.batch_id,
        "plan_sha256": plan.manifest.manifest_sha256,
        "execution_sha256": execution_sha256,
        "target_binding_sha256": plan.manifest.target_set_sha256,
        "source_binding_sha256": plan.manifest.source_set_sha256,
        "effect_binding_sha256": plan.manifest.effect_set_sha256,
        "item_count": len(plan.items),
        "receipt_create_count": len(plan.items),
        "checkpoint_count": core.get("checkpoint_count", 0),
        "written_field_count": core.get("written_field_count", 0),
        "resumed_field_count": core.get("resumed_field_count", 0),
        "final_receipt_sha256": core.get("final_receipt_sha256"),
        "item_terminal_classifications": [
            {"item_id": item.request_item_id, "state": "recorded_and_verified"}
            for item in plan.items
        ],
        "prepared_capture_request": (
            {
                **artifact.public_document(),
                "state": "prepared_and_verified",
                "intake_execution_sha256": execution_sha256,
                "requires_new_capture_approval": True,
                "same_claim_reused": False,
            }
            if artifact is not None
            else {
                "ready": False,
                "reason_code": "capture_sources_must_be_archive_relative",
            }
        ),
        "independent_verification": True,
        "replay_reconciliation_available": True,
        "writes_performed": bool(core.get("written_field_count", 0)),
        "source_bytes_hashed": True,
        "source_bytes_retained": False,
        "provider_calls_performed": False,
        "credential_material_used_for_local_authentication": True,
        "credential_values_echoed": False,
        "private_values_echoed": False,
        "paths_echoed": artifact is not None,
        "absolute_paths_echoed": False,
        "source_paths_echoed": False,
    }


def _apply_with_store(
    plan: SourceIntakeBatchExactPlan,
    authority: ExactOperationApprovalAuthority,
    store: FileExactOperationCheckpointStore,
    *,
    request_items: Mapping[str, Mapping[str, Any]],
    resume: bool,
    progress_hook: Callable[[ExactOperationProgress], None] | None,
    completion_authenticator: Callable[[bytes], Mapping[str, Any]],
) -> dict[str, Any]:
    assert plan.manifest is not None
    core = apply_exact_operation(
        plan.manifest,
        payloads=_Payloads(plan),
        writer=_Writer(plan, request_items=request_items),
        verifier=_Verifier(plan),
        checkpoint_store=store,
        approval_authority=authority,
        completion_authenticator=completion_authenticator,
        resume=resume,
        progress_hook=progress_hook,
    )
    return _success_document(plan, core)


def _completion_authenticator(
    claim: _ClaimedExactHumanApproval,
) -> Callable[[bytes], Mapping[str, Any]]:
    """Bind the exact-operation terminal result to this live approval claim."""

    def authenticate(payload: bytes) -> Mapping[str, Any]:
        return {
            "approval_reference": claim.public_reference(),
            "terminal_mac": claim.exact_terminal_record_mac(payload),
        }

    return authenticate


def _execute_core(
    plan: SourceIntakeBatchExactPlan,
    claim: _ClaimedExactHumanApproval,
    context: ExactHumanApprovalContext,
    *,
    progress_hook: Callable[[ExactOperationProgress], None] | None,
) -> dict[str, Any]:
    authority = _authority(plan, claim, context, allow_resume=False)
    with exact_operation_writer_lock(plan.archive_root) as writer_lock:
        # Revalidate the approved request once.  Each source is independently
        # re-hashed by the writer immediately before its own create-only
        # receipt mutation, so a second whole-batch planning pass is both
        # redundant and expensive for 508/1000-item real workloads.
        request_items = _request_items(plan)
        store = FileExactOperationCheckpointStore(
            plan.archive_root,
            writer_lock=writer_lock,
        )
        return _apply_with_store(
            plan,
            authority,
            store,
            request_items=request_items,
            resume=False,
            progress_hook=progress_hook,
            completion_authenticator=_completion_authenticator(claim),
        )


def execute_source_intake_batch(
    plan: SourceIntakeBatchExactPlan,
    *,
    expected_plan_sha256: str = "",
    reviewer_claim: str,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
) -> dict[str, Any]:
    expected = str(expected_plan_sha256 or "").strip().lower()
    if expected and (
        plan.manifest is None
        or _SHA256_RE.fullmatch(expected) is None
        or not hmac.compare_digest(expected, plan.manifest.manifest_sha256)
    ):
        raise _fail("source_intake_batch_plan_digest_mismatch")
    if not plan.approveable or plan.manifest is None:
        raise _fail("source_intake_batch_plan_blocked")
    context = approval_context(plan, reviewer_claim=reviewer_claim)
    return _execute_exact_human_approved_write(
        plan.archive_root,
        context,
        lambda claim: _execute_core(
            plan,
            claim,
            context,
            progress_hook=progress_hook,
        ),
    )


@dataclass(frozen=True, repr=False)
class SourceIntakeBatchResumeDiscovery:
    """One authenticated resumable candidate with a content-free projection."""

    approval_id: str = field(repr=False)
    execution_sha256: str = field(repr=False)

    def public_document(self) -> dict[str, Any]:
        return {
            "schema": "wom-kit/source-intake-batch-resume-discovery/v0.1",
            "state": "exactly_one_authenticated_candidate",
            "candidate_count": 1,
            "archive_manifest_context_bound": True,
            "checkpoint_chain_validated_read_only": True,
            "operator_identifiers_required": False,
            "private_folder_inspection_required": False,
            "writes_performed": False,
            "directories_created": False,
            "locks_created_or_acquired": False,
            "credential_values_echoed": False,
            "private_values_echoed": False,
            "paths_echoed": False,
        }


@contextmanager
def _claim_resume_boundary(
    plan: SourceIntakeBatchExactPlan,
) -> Iterable[tuple[Path, dict[str, Any]]]:
    claims_root = plan.archive_root.joinpath(*Path(CLAIMS_RELATIVE_ROOT).parts)
    with archive_services._activity_group_bound_directory_chain(
        plan.archive_root,
        claims_root,
        create=False,
    ) as binding:
        yield plan.archive_root, binding


def _bound_directory_names(binding: Mapping[str, Any]) -> tuple[str, ...]:
    descriptor = binding.get("descriptor")
    try:
        raw_names = os.listdir(
            descriptor if type(descriptor) is int else binding.get("path")
        )
    except (OSError, TypeError, ValueError):
        raise _fail("source_intake_batch_resume_invalid") from None
    if len(raw_names) > 100_000 or any(type(name) is not str for name in raw_names):
        raise _fail("source_intake_batch_resume_invalid")
    return tuple(sorted(raw_names))


def discover_source_intake_batch_resume_read_only(
    plan: SourceIntakeBatchExactPlan,
    *,
    reviewer_claim: str,
    key_provider: Any | None = None,
) -> SourceIntakeBatchResumeDiscovery:
    """Find exactly one authenticated started claim without creating state."""

    if not plan.resume_candidate or plan.manifest is None:
        raise _fail("source_intake_batch_resume_invalid")
    context = approval_context(
        plan,
        reviewer_claim=reviewer_claim,
        allow_resume=True,
    )
    candidates: list[SourceIntakeBatchResumeDiscovery] = []

    try:
        with _claim_resume_boundary(plan) as filesystem_boundary:
            names = _bound_directory_names(filesystem_boundary[1])
            candidate_ids = tuple(
                match.group(1)
                for name in names
                if (match := _APPROVAL_FILENAME_RE.fullmatch(name)) is not None
            )
            selected = (
                key_provider
                if key_provider is not None
                else _production_key_provider()
            )
            use_key = getattr(selected, "use_key", None)
            if not callable(use_key):
                raise _fail("source_intake_batch_resume_invalid")

            def inspect(key: memoryview) -> None:
                for approval_id in candidate_ids:
                    try:
                        claim = _rehydrate_exact_human_approval_core(
                            plan.archive_root,
                            context,
                            approval_id,
                            key,
                            bound_archive_root=filesystem_boundary[0],
                            claim_parent_binding=filesystem_boundary[1],
                        )
                    except ExactHumanApprovalError:
                        # A valid claim for another exact context is irrelevant;
                        # an unauthenticated lookalike can never become a
                        # candidate.  Both are projected only as non-matches.
                        continue
                    try:
                        authority = _authority(
                            plan,
                            claim,
                            context,
                            allow_resume=True,
                        )
                        execution_sha256 = exact_operation_execution_sha256(
                            plan.manifest,
                            mode="apply",
                            approval_authority=authority,
                        )
                        if validate_exact_operation_resume_checkpoint_read_only(
                            plan.archive_root,
                            plan.manifest,
                            execution_sha256=execution_sha256,
                            approval_authority=authority,
                        ):
                            candidates.append(
                                SourceIntakeBatchResumeDiscovery(
                                    approval_id=approval_id,
                                    execution_sha256=execution_sha256,
                                )
                            )
                    finally:
                        claim.close()

            use_key(
                plan.archive_root,
                inspect,
                create_if_missing=False,
            )
    except FileNotFoundError:
        candidates = []
    except SourceIntakeBatchExactError:
        raise
    except (ExactOperationManifestError, OSError):
        raise _fail("source_intake_batch_resume_invalid") from None
    except Exception:
        raise _fail("source_intake_batch_resume_invalid") from None

    if not candidates:
        raise _fail("source_intake_batch_resume_required")
    if len(candidates) != 1:
        raise _fail("source_intake_batch_resume_ambiguous")
    return candidates[0]


def resume_source_intake_batch(
    plan: SourceIntakeBatchExactPlan,
    *,
    reviewer_claim: str,
    approval_id: str,
    execution_sha256: str,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
    key_provider: Any | None = None,
) -> dict[str, Any]:
    """Resume only the authenticated started claim for this exact manifest."""

    if (
        not plan.resume_candidate
        or plan.manifest is None
        or _SHA256_RE.fullmatch(str(execution_sha256 or "")) is None
    ):
        raise _fail("source_intake_batch_resume_invalid")
    context = approval_context(
        plan,
        reviewer_claim=reviewer_claim,
        allow_resume=True,
    )
    with exact_operation_writer_lock(plan.archive_root) as writer_lock:
        request_items = _request_items(plan)
        store = FileExactOperationCheckpointStore(
            plan.archive_root,
            writer_lock=writer_lock,
        )
        authority_box: dict[str, ExactOperationApprovalAuthority] = {}

        def authority_and_execution(
            claim: _ClaimedExactHumanApproval,
        ) -> tuple[ExactOperationApprovalAuthority, str]:
            if not hmac.compare_digest(claim.approval_id, approval_id):
                raise _fail("source_intake_batch_approval_required")
            authority = _authority(plan, claim, context, allow_resume=True)
            actual = exact_operation_execution_sha256(
                plan.manifest,
                mode="apply",
                approval_authority=authority,
            )
            if not hmac.compare_digest(actual, execution_sha256):
                raise _fail("source_intake_batch_resume_invalid")
            return authority, actual

        def checkpoint_guard(claim: _ClaimedExactHumanApproval) -> bool:
            authority, actual = authority_and_execution(claim)
            authority_box["authority"] = authority
            return store.resume_checkpoint_present(actual)

        def writer(claim: _ClaimedExactHumanApproval) -> Mapping[str, Any]:
            authority, _actual = authority_and_execution(claim)
            if authority_box.get("authority") != authority:
                raise _fail("source_intake_batch_resume_invalid")
            return _apply_with_store(
                plan,
                authority,
                store,
                request_items=request_items,
                resume=True,
                progress_hook=progress_hook,
                completion_authenticator=_completion_authenticator(claim),
            )

        return _resume_exact_human_approved_write_core(
            plan.archive_root,
            context,
            approval_id,
            checkpoint_guard,
            writer,
            key_provider=key_provider,
            resume_boundary=lambda: _claim_resume_boundary(plan),
        )


def resume_source_intake_batch_auto(
    plan: SourceIntakeBatchExactPlan,
    *,
    reviewer_claim: str,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
    key_provider: Any | None = None,
) -> dict[str, Any]:
    """Resume the only authenticated candidate without operator-supplied IDs."""

    discovery = discover_source_intake_batch_resume_read_only(
        plan,
        reviewer_claim=reviewer_claim,
        key_provider=key_provider,
    )
    result = resume_source_intake_batch(
        plan,
        reviewer_claim=reviewer_claim,
        approval_id=discovery.approval_id,
        execution_sha256=discovery.execution_sha256,
        progress_hook=progress_hook,
        key_provider=key_provider,
    )
    return {
        **result,
        "resume_discovery": discovery.public_document(),
        "automatic_resume_discovery": True,
        "operator_resume_identifiers_supplied": False,
        "native_approval_redisplayed": False,
        "private_values_echoed": False,
        "paths_echoed": bool(result.get("paths_echoed", False)),
    }


def reconcile_source_intake_batch(
    plan: SourceIntakeBatchExactPlan,
    *,
    execution_sha256: str,
    key_provider: Any | None = None,
) -> dict[str, Any]:
    """Read-only classification from authenticated completion and fresh targets."""

    if plan.manifest is None or _SHA256_RE.fullmatch(str(execution_sha256 or "")) is None:
        raise _fail("source_intake_batch_resume_invalid")
    try:
        final = load_exact_operation_final_receipt_read_only(
            plan.archive_root,
            execution_sha256,
        )
    except ExactOperationManifestError:
        final = None
    final_result = final.get("result") if isinstance(final, Mapping) else None
    authentication = (
        final_result.get("completion_authentication")
        if isinstance(final_result, Mapping)
        else None
    )
    completion_authenticated = False
    if (
        isinstance(authentication, Mapping)
        and authentication.get("operation") == OPERATION
        and authentication.get("target_binding_sha256")
        == plan.manifest.target_set_sha256
        and isinstance(authentication.get("approval_reference"), Mapping)
        and isinstance(authentication.get("terminal_mac"), str)
        and isinstance(final_result, Mapping)
        and final_result.get("manifest_sha256") == plan.manifest.manifest_sha256
    ):
        try:
            payload = exact_operation_completion_authentication_payload(
                final_result
            )
            completion_authenticated = (
                audit_exact_human_approval_succeeded_terminal_record_read_only(
                    plan.archive_root,
                    authentication["approval_reference"],
                    expected_operation=(
                        ExactHumanApprovalOperation.source_intake_batch
                    ),
                    expected_plan_sha256=plan.manifest.manifest_sha256,
                    expected_target_binding_sha256=(
                        plan.manifest.target_set_sha256
                    ),
                    payload=payload,
                    expected_mac=authentication["terminal_mac"],
                    key_provider=key_provider,
                )
            )
        except ExactOperationManifestError:
            completion_authenticated = False
    verification = verify_exact_operation(
        plan.manifest,
        verifier=_Verifier(plan),
        state="post",
    )
    completed = bool(
        isinstance(final_result, Mapping)
        and final_result.get("status") == "completed"
        and final_result.get("mode") == "apply"
        and final_result.get("manifest_sha256") == plan.manifest.manifest_sha256
        and completion_authenticated
        and verification.get("all_match") is True
    )
    return {
        "schema_version": RESULT_SCHEMA,
        "ok": completed,
        "state": "completed" if completed else plan.state,
        "lifecycle_action": "source_intake_batch_exact_reconcile",
        "plan_sha256": plan.manifest.manifest_sha256,
        "execution_sha256": execution_sha256,
        "item_count": len(plan.items),
        "completed_item_count": len(plan.items) if completed else 0,
        "item_terminal_classifications": [
            {
                "item_id": item.request_item_id,
                "state": "recorded_and_verified" if completed else item.target_state,
            }
            for item in plan.items
        ],
        "final_receipt_present": final is not None,
        "completion_authentication_verified": completion_authenticated,
        "independent_verification": verification.get("all_match") is True,
        "blockers": [] if completed else list(plan.blockers),
        "writes_performed": False,
        "credential_material_used_for_local_authentication": (
            True if completion_authenticated else None
        ),
        "credential_values_echoed": False,
        "private_values_echoed": False,
        "paths_echoed": False,
    }


def failure_document(code: str) -> dict[str, Any]:
    safe = SourceIntakeBatchExactError(code).code
    # Only ``state_unknown`` can be raised after the mutation boundary has
    # been entered.  Native-dialog failures and workflow argument/contract
    # failures happen before the writer is called, so they are proven
    # zero-write blockers and must not advertise a nonexistent resume claim.
    outcome_unverified = code == "exact_human_approval_state_unknown"
    next_safe_actions = (
        [
            {
                "action": "rerun_unchanged_request_with_resume",
                "cli_flag": "--resume",
                "automatic_authenticated_candidate_discovery": True,
                "operator_identifiers_required": False,
                "private_folder_inspection_required": False,
            }
        ]
        if outcome_unverified
        else []
    )
    return {
        "schema_version": RESULT_SCHEMA,
        "ok": False,
        "state": "blocked",
        "lifecycle_action": "source_intake_batch_exact_write",
        "blockers": [safe],
        "writes_performed": False,
        "writes_may_have_occurred": outcome_unverified,
        "outcome_unverified": outcome_unverified,
        "safe_recovery_actions": (
            ["reconcile", "resume"] if outcome_unverified else []
        ),
        "next_safe_actions": next_safe_actions,
        "source_bytes_retained": False,
        "provider_calls_performed": False,
        # The exception alone does not prove whether key access completed.
        "credential_material_used_for_local_authentication": None,
        "credential_values_echoed": False,
        "private_values_echoed": False,
        "paths_echoed": False,
    }


__all__ = [
    "SourceIntakeBatchExactError",
    "SourceIntakeBatchExactItem",
    "SourceIntakeBatchExactPlan",
    "SourceIntakeBatchResumeDiscovery",
    "PreparedObjetCaptureBatchRequest",
    "approval_context",
    "discover_source_intake_batch_resume_read_only",
    "execute_source_intake_batch",
    "failure_document",
    "intake_capture_chain_binding_sha256",
    "plan_source_intake_batch",
    "reconcile_source_intake_batch",
    "resume_source_intake_batch",
    "resume_source_intake_batch_auto",
]
