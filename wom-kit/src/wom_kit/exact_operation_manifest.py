"""Domain-neutral exact operation manifests and resumable field execution.

This module does not display approval UI, mint authority, or choose a target.
It provides the common archive-wide writer lock and durable checkpoint/result
store, while callers bind a manifest through the existing
:mod:`wom_kit.operation_approval_binding` workflow and pass the authenticated
approval reference into the runner.  Domain adapters still inject their
already-authorized writer, independent reader, and payload provider.

The manifest binds stable target identity and field-local pre/post/source
hashes.  It deliberately does *not* bind an entire target-file hash: doing so
would make a later, unrelated field change destroy otherwise safe field-level
revert authority.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Mapping, Protocol, Sequence


MANIFEST_SCHEMA = "wom-kit/exact-operation-manifest/v1"
CHECKPOINT_SCHEMA = "wom-kit/exact-operation-checkpoint/v1"
FIELD_RECEIPT_SCHEMA = "wom-kit/exact-operation-field-receipt/v1"
VERIFICATION_SCHEMA = "wom-kit/exact-operation-verification/v1"
RESULT_SCHEMA = "wom-kit/exact-operation-result/v1"
FINAL_RECEIPT_SCHEMA = "wom-kit/exact-operation-final-receipt/v1"
APPROVAL_AUTHORITY_SCHEMA = "wom-kit/exact-operation-approval-authority/v1"

EXACT_OPERATION_LOCAL_ROOT = "profiles/local/exact-operations"
EXACT_OPERATION_RECEIPTS_ROOT = "receipts/ops/exact-operations"
EXACT_OPERATION_WRITER_LOCK = (
    EXACT_OPERATION_LOCAL_ROOT + "/.writer.lock"
)

FIRST_STATUS_DEADLINE_SECONDS = 2
HEARTBEAT_INTERVAL_SECONDS = 10

ABSENT_FIELD_SHA256 = "sha256:" + hashlib.sha256(
    b"wom-kit/exact-operation-field-absent/v1\n"
).hexdigest()

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
_ITEM_ID_RE = re.compile(r"^item:[A-Za-z0-9][A-Za-z0-9._:-]{0,126}$")
_APPROVAL_ID_RE = re.compile(r"^approval_[0-9a-f]{32}$")
_EXACT_HUMAN_APPROVAL_REFERENCE_SCHEMA = (
    "wom-kit/exact-human-approval-reference/v0.1"
)
_MAX_ITEMS = 100_000
_MAX_FIELDS_PER_ITEM = 1_024
_MAX_TOTAL_FIELDS = 1_000_000
_MAX_TEXT_BYTES = 4_096
_MAX_FIELD_VALUE_BYTES = 64 * 1024 * 1024
_MAX_CANONICAL_BYTES = 64 * 1024 * 1024
_MAX_CHECKPOINT_FILE_BYTES = 256 * 1024 * 1024
_LOCK_BYTES = b"wom-kit/exact-operation-writer-lock/v1\n"

FieldValue = bytes | None
ExecutionMode = Literal["apply", "revert"]
ProgressStage = Literal[
    "preflight",
    "heartbeat",
    "item_started",
    "field_verified",
    "item_verified",
    "completed",
]


class ExactOperationManifestError(RuntimeError):
    """Fixed-code failure for malformed, drifted, or unsafe exact operations."""

    _CODES = {
        "exact_operation_manifest_invalid",
        "exact_operation_manifest_digest_mismatch",
        "exact_operation_payload_mismatch",
        "exact_operation_target_identity_mismatch",
        "exact_operation_target_state_drifted",
        "exact_operation_checkpoint_invalid",
        "exact_operation_checkpoint_write_failed",
        "exact_operation_checkpoint_store_invalid",
        "exact_operation_resume_required",
        "exact_operation_resume_checkpoint_missing",
        "exact_operation_writer_lock_invalid",
        "exact_operation_writer_lock_required",
        "exact_operation_writer_busy",
        "exact_operation_write_failed",
        "exact_operation_independent_verify_failed",
        "exact_operation_revert_selection_invalid",
        "exact_operation_result_receipt_failed",
    }

    def __init__(self, code: str) -> None:
        self.code = (
            code if code in self._CODES else "exact_operation_manifest_invalid"
        )
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"ExactOperationManifestError({self.code!r})"


def _fail(code: str) -> ExactOperationManifestError:
    return ExactOperationManifestError(code)


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        raw = json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise _fail("exact_operation_manifest_invalid") from None
    if len(raw) > _MAX_CANONICAL_BYTES:
        raise _fail("exact_operation_manifest_invalid")
    return raw


def _digest_document(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _digest(value: Any, *, code: str = "exact_operation_manifest_invalid") -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise _fail(code)
    return value


def _bounded_text(value: Any, *, code_pattern: re.Pattern[str] | None = None) -> str:
    if type(value) is not str or not value:
        raise _fail("exact_operation_manifest_invalid")
    try:
        raw = value.encode("utf-8", errors="strict")
    except UnicodeError:
        raise _fail("exact_operation_manifest_invalid") from None
    if (
        len(raw) > _MAX_TEXT_BYTES
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
        or (code_pattern is not None and code_pattern.fullmatch(value) is None)
    ):
        raise _fail("exact_operation_manifest_invalid")
    return value


def hash_field_value(value: FieldValue) -> str:
    """Return the field-state hash used by manifests and CAS verification.

    ``None`` means that the field is absent.  A present JSON ``null`` or other
    typed value must be encoded by the domain adapter before this boundary.
    """

    if value is None:
        return ABSENT_FIELD_SHA256
    if type(value) is not bytes or len(value) > _MAX_FIELD_VALUE_BYTES:
        raise _fail("exact_operation_payload_mismatch")
    return "sha256:" + hashlib.sha256(value).hexdigest()


@dataclass(frozen=True)
class ExactOperationApprovalAuthority:
    """Content-free binding to one authenticated exact-human approval claim."""

    approval_id: str
    context_sha256: str
    approval_authority_sha256: str
    binding_sha256: str

    def __post_init__(self) -> None:
        if (
            type(self.approval_id) is not str
            or _APPROVAL_ID_RE.fullmatch(self.approval_id) is None
        ):
            raise _fail("exact_operation_manifest_invalid")
        _digest(self.context_sha256)
        _digest(self.approval_authority_sha256)
        _digest(self.binding_sha256)
        expected = _digest_document(self._basis())
        if not hmac.compare_digest(self.binding_sha256, expected):
            raise _fail("exact_operation_manifest_digest_mismatch")

    def _basis(self) -> dict[str, Any]:
        return {
            "schema": APPROVAL_AUTHORITY_SCHEMA,
            "approval_id": self.approval_id,
            "context_sha256": self.context_sha256,
            "approval_authority_sha256": self.approval_authority_sha256,
        }

    def document(self) -> dict[str, Any]:
        return {**self._basis(), "binding_sha256": self.binding_sha256}

    @classmethod
    def from_reference(
        cls,
        reference: Mapping[str, Any],
    ) -> "ExactOperationApprovalAuthority":
        """Build only from the strict public reference of a live claim."""

        if not isinstance(reference, Mapping) or set(reference) != {
            "schema_version",
            "approval_id",
            "context_sha256",
            "approval_authority_sha256",
            "one_use",
        }:
            raise _fail("exact_operation_manifest_invalid")
        if (
            reference.get("schema_version")
            != _EXACT_HUMAN_APPROVAL_REFERENCE_SCHEMA
            or reference.get("one_use") is not True
        ):
            raise _fail("exact_operation_manifest_invalid")
        basis = {
            "schema": APPROVAL_AUTHORITY_SCHEMA,
            "approval_id": reference.get("approval_id"),
            "context_sha256": reference.get("context_sha256"),
            "approval_authority_sha256": reference.get(
                "approval_authority_sha256"
            ),
        }
        return cls(
            approval_id=basis["approval_id"],
            context_sha256=basis["context_sha256"],
            approval_authority_sha256=basis[
                "approval_authority_sha256"
            ],
            binding_sha256=_digest_document(basis),
        )


@dataclass(frozen=True)
class ExactFieldEffect:
    field_ref: str
    pre_sha256: str
    post_sha256: str
    source_sha256: str

    def __post_init__(self) -> None:
        _bounded_text(self.field_ref)
        _digest(self.pre_sha256)
        _digest(self.post_sha256)
        _digest(self.source_sha256)
        if hmac.compare_digest(self.pre_sha256, self.post_sha256):
            raise _fail("exact_operation_manifest_invalid")

    def document(self) -> dict[str, Any]:
        return {
            "field_ref": self.field_ref,
            "pre_sha256": self.pre_sha256,
            "post_sha256": self.post_sha256,
            "source_sha256": self.source_sha256,
        }


@dataclass(frozen=True)
class ExactOperationItem:
    ordinal: int
    item_id: str
    target_kind: str
    target_ref: str
    target_identity_sha256: str
    fields: tuple[ExactFieldEffect, ...]

    def __post_init__(self) -> None:
        if type(self.ordinal) is not int or not 0 <= self.ordinal < _MAX_ITEMS:
            raise _fail("exact_operation_manifest_invalid")
        _bounded_text(self.item_id, code_pattern=_ITEM_ID_RE)
        _bounded_text(self.target_kind, code_pattern=_CODE_RE)
        _bounded_text(self.target_ref)
        _digest(self.target_identity_sha256)
        if (
            type(self.fields) is not tuple
            or not self.fields
            or len(self.fields) > _MAX_FIELDS_PER_ITEM
            or any(type(field) is not ExactFieldEffect for field in self.fields)
        ):
            raise _fail("exact_operation_manifest_invalid")
        field_refs = [field.field_ref for field in self.fields]
        if field_refs != sorted(field_refs) or len(field_refs) != len(set(field_refs)):
            raise _fail("exact_operation_manifest_invalid")

    def document(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "item_id": self.item_id,
            "target": {
                "kind": self.target_kind,
                "ref": self.target_ref,
                "identity_sha256": self.target_identity_sha256,
            },
            "fields": [field.document() for field in self.fields],
        }


@dataclass(frozen=True)
class ExactOperationManifest:
    operation: str
    archive_identity_sha256: str
    items: tuple[ExactOperationItem, ...]
    target_set_sha256: str
    source_set_sha256: str
    effect_set_sha256: str
    manifest_sha256: str

    def __post_init__(self) -> None:
        """Reject forged direct construction as strictly as JSON loading."""

        operation = _bounded_text(self.operation, code_pattern=_CODE_RE)
        archive_identity_sha256 = _digest(self.archive_identity_sha256)
        if type(self.items) is not tuple:
            raise _fail("exact_operation_manifest_invalid")
        _validate_item_set(self.items)
        component_digests = _manifest_component_digests(self.items)
        for name, expected in component_digests.items():
            supplied = _digest(getattr(self, name))
            if not hmac.compare_digest(supplied, expected):
                raise _fail("exact_operation_manifest_digest_mismatch")
        basis = _manifest_basis(
            operation=operation,
            archive_identity_sha256=archive_identity_sha256,
            items=self.items,
            **component_digests,
        )
        supplied_manifest = _digest(self.manifest_sha256)
        if not hmac.compare_digest(supplied_manifest, _digest_document(basis)):
            raise _fail("exact_operation_manifest_digest_mismatch")

    @classmethod
    def build(
        cls,
        *,
        operation: str,
        archive_identity_sha256: str,
        items: Iterable[ExactOperationItem],
    ) -> "ExactOperationManifest":
        normalized_operation = _bounded_text(operation, code_pattern=_CODE_RE)
        normalized_archive = _digest(archive_identity_sha256)
        normalized_items = tuple(items)
        _validate_item_set(normalized_items)
        digests = _manifest_component_digests(normalized_items)
        basis = _manifest_basis(
            operation=normalized_operation,
            archive_identity_sha256=normalized_archive,
            items=normalized_items,
            **digests,
        )
        return cls(
            operation=normalized_operation,
            archive_identity_sha256=normalized_archive,
            items=normalized_items,
            manifest_sha256=_digest_document(basis),
            **digests,
        )

    @classmethod
    def from_document(cls, value: Mapping[str, Any]) -> "ExactOperationManifest":
        if not isinstance(value, Mapping) or set(value) != {
            "schema",
            "operation",
            "archive_identity_sha256",
            "item_count",
            "field_count",
            "target_set_sha256",
            "source_set_sha256",
            "effect_set_sha256",
            "items",
            "manifest_sha256",
        }:
            raise _fail("exact_operation_manifest_invalid")
        if value.get("schema") != MANIFEST_SCHEMA or type(value.get("items")) is not list:
            raise _fail("exact_operation_manifest_invalid")
        parsed_items: list[ExactOperationItem] = []
        for raw_item in value["items"]:
            if not isinstance(raw_item, Mapping) or set(raw_item) != {
                "ordinal",
                "item_id",
                "target",
                "fields",
            }:
                raise _fail("exact_operation_manifest_invalid")
            target = raw_item.get("target")
            fields = raw_item.get("fields")
            if (
                not isinstance(target, Mapping)
                or set(target) != {"kind", "ref", "identity_sha256"}
                or type(fields) is not list
            ):
                raise _fail("exact_operation_manifest_invalid")
            parsed_fields: list[ExactFieldEffect] = []
            for raw_field in fields:
                if not isinstance(raw_field, Mapping) or set(raw_field) != {
                    "field_ref",
                    "pre_sha256",
                    "post_sha256",
                    "source_sha256",
                }:
                    raise _fail("exact_operation_manifest_invalid")
                parsed_fields.append(
                    ExactFieldEffect(
                        field_ref=raw_field["field_ref"],
                        pre_sha256=raw_field["pre_sha256"],
                        post_sha256=raw_field["post_sha256"],
                        source_sha256=raw_field["source_sha256"],
                    )
                )
            parsed_items.append(
                ExactOperationItem(
                    ordinal=raw_item["ordinal"],
                    item_id=raw_item["item_id"],
                    target_kind=target["kind"],
                    target_ref=target["ref"],
                    target_identity_sha256=target["identity_sha256"],
                    fields=tuple(parsed_fields),
                )
            )
        rebuilt = cls.build(
            operation=value.get("operation"),
            archive_identity_sha256=value.get("archive_identity_sha256"),
            items=parsed_items,
        )
        expected_counts = (
            len(rebuilt.items),
            sum(len(item.fields) for item in rebuilt.items),
        )
        if (
            type(value.get("item_count")) is not int
            or type(value.get("field_count")) is not int
            or (value["item_count"], value["field_count"]) != expected_counts
        ):
            raise _fail("exact_operation_manifest_invalid")
        for name in (
            "target_set_sha256",
            "source_set_sha256",
            "effect_set_sha256",
            "manifest_sha256",
        ):
            supplied = _digest(value.get(name))
            if not hmac.compare_digest(supplied, getattr(rebuilt, name)):
                raise _fail("exact_operation_manifest_digest_mismatch")
        return rebuilt

    def document(self) -> dict[str, Any]:
        basis = _manifest_basis(
            operation=self.operation,
            archive_identity_sha256=self.archive_identity_sha256,
            items=self.items,
            target_set_sha256=self.target_set_sha256,
            source_set_sha256=self.source_set_sha256,
            effect_set_sha256=self.effect_set_sha256,
        )
        return {**basis, "manifest_sha256": self.manifest_sha256}

    def approval_digest_context(self) -> dict[str, Any]:
        """Return only the digest context consumed by the existing broker."""

        return {
            "schema": MANIFEST_SCHEMA,
            "operation": self.operation,
            "manifest_sha256": self.manifest_sha256,
            "target_set_sha256": self.target_set_sha256,
            "source_set_sha256": self.source_set_sha256,
            "effect_set_sha256": self.effect_set_sha256,
            "item_count": len(self.items),
            "field_count": sum(len(item.fields) for item in self.items),
            "private_values_echoed": False,
            "target_refs_echoed": False,
            "field_refs_echoed": False,
        }


def _validate_item_set(items: tuple[ExactOperationItem, ...]) -> None:
    if not items or len(items) > _MAX_ITEMS:
        raise _fail("exact_operation_manifest_invalid")
    if any(type(item) is not ExactOperationItem for item in items):
        raise _fail("exact_operation_manifest_invalid")
    if [item.ordinal for item in items] != list(range(len(items))):
        raise _fail("exact_operation_manifest_invalid")
    item_ids = [item.item_id for item in items]
    if len(item_ids) != len(set(item_ids)):
        raise _fail("exact_operation_manifest_invalid")
    target_fields = [
        (item.target_kind, item.target_ref, field.field_ref)
        for item in items
        for field in item.fields
    ]
    if (
        len(target_fields) > _MAX_TOTAL_FIELDS
        or len(target_fields) != len(set(target_fields))
    ):
        raise _fail("exact_operation_manifest_invalid")


def _manifest_component_digests(
    items: tuple[ExactOperationItem, ...],
) -> dict[str, str]:
    targets = [
        {
            "ordinal": item.ordinal,
            "item_id": item.item_id,
            "target_kind": item.target_kind,
            "target_ref": item.target_ref,
            "target_identity_sha256": item.target_identity_sha256,
            "field_refs": [field.field_ref for field in item.fields],
        }
        for item in items
    ]
    sources = [
        {
            "ordinal": item.ordinal,
            "field_ref": field.field_ref,
            "source_sha256": field.source_sha256,
        }
        for item in items
        for field in item.fields
    ]
    effects = [
        {
            "ordinal": item.ordinal,
            "field_ref": field.field_ref,
            "pre_sha256": field.pre_sha256,
            "post_sha256": field.post_sha256,
        }
        for item in items
        for field in item.fields
    ]
    return {
        "target_set_sha256": _digest_document(targets),
        "source_set_sha256": _digest_document(sources),
        "effect_set_sha256": _digest_document(effects),
    }


def _manifest_basis(
    *,
    operation: str,
    archive_identity_sha256: str,
    items: tuple[ExactOperationItem, ...],
    target_set_sha256: str,
    source_set_sha256: str,
    effect_set_sha256: str,
) -> dict[str, Any]:
    return {
        "schema": MANIFEST_SCHEMA,
        "operation": operation,
        "archive_identity_sha256": archive_identity_sha256,
        "item_count": len(items),
        "field_count": sum(len(item.fields) for item in items),
        "target_set_sha256": target_set_sha256,
        "source_set_sha256": source_set_sha256,
        "effect_set_sha256": effect_set_sha256,
        "items": [item.document() for item in items],
    }


class ExactOperationPayloadProvider(Protocol):
    def field_value(
        self,
        *,
        item_id: str,
        field_ref: str,
        state: Literal["pre", "post", "source"],
        heartbeat: Callable[[], None],
    ) -> FieldValue: ...


class ExactOperationTargetWriter(Protocol):
    def write_field(
        self,
        *,
        target_kind: str,
        target_ref: str,
        field_ref: str,
        value: FieldValue,
        heartbeat: Callable[[], None],
    ) -> None: ...


class ExactOperationIndependentVerifier(Protocol):
    def target_identity_sha256(
        self,
        *,
        target_kind: str,
        target_ref: str,
        heartbeat: Callable[[], None],
    ) -> str: ...

    def read_field(
        self,
        *,
        target_kind: str,
        target_ref: str,
        field_ref: str,
        heartbeat: Callable[[], None],
    ) -> FieldValue: ...


class ExactOperationCheckpointStore(Protocol):
    def load(
        self,
        execution_sha256: str,
        *,
        heartbeat: Callable[[], None],
    ) -> Sequence[Mapping[str, Any]]: ...

    def append(
        self,
        execution_sha256: str,
        checkpoint: Mapping[str, Any],
        *,
        heartbeat: Callable[[], None],
    ) -> None: ...

    def finalize(
        self,
        result: Mapping[str, Any],
        *,
        heartbeat: Callable[[], None],
    ) -> str: ...


@dataclass(frozen=True)
class ExactOperationProgress:
    manifest_sha256: str
    execution_sha256: str | None
    mode: ExecutionMode
    stage: ProgressStage
    completed_items: int
    total_items: int
    completed_fields: int
    total_fields: int
    item_ordinal: int | None = None

    def public_document(self) -> dict[str, Any]:
        return {
            "manifest_sha256": self.manifest_sha256,
            "execution_sha256": self.execution_sha256,
            "mode": self.mode,
            "stage": self.stage,
            "completed_items": self.completed_items,
            "total_items": self.total_items,
            "completed_fields": self.completed_fields,
            "total_fields": self.total_fields,
            "item_ordinal": self.item_ordinal,
            "private_values_echoed": False,
        }


def _path_is_reparse(info: os.stat_result) -> bool:
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(flag and getattr(info, "st_file_attributes", 0) & flag)


def _plain_directory(path: Path) -> bool:
    try:
        info = os.lstat(path)
    except OSError:
        return False
    return bool(
        stat.S_ISDIR(info.st_mode)
        and not stat.S_ISLNK(info.st_mode)
        and not _path_is_reparse(info)
    )


def _fsync_directory(path: Path) -> bool:
    if os.name == "nt":
        # Windows does not expose a portable directory fsync through os.open.
        # File fsync boundaries remain mandatory there.
        return True
    descriptor = -1
    try:
        descriptor = os.open(path, os.O_RDONLY)
        os.fsync(descriptor)
    except OSError:
        return False
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
    return True


def _exact_operation_archive_root(value: Path | str) -> Path:
    try:
        root = Path(os.path.abspath(os.fspath(value))).resolve(strict=True)
    except (OSError, RuntimeError, TypeError, ValueError):
        raise _fail("exact_operation_checkpoint_store_invalid") from None
    if not _plain_directory(root):
        raise _fail("exact_operation_checkpoint_store_invalid")
    return root


def _ensure_private_directory(root: Path, parts: tuple[str, ...]) -> Path:
    current = root
    for part in parts:
        current = current / part
        try:
            os.mkdir(current, 0o700)
            if not _fsync_directory(current.parent):
                raise OSError("exact_operation_directory_sync_failed")
        except FileExistsError:
            pass
        except OSError:
            raise _fail("exact_operation_checkpoint_store_invalid") from None
        if not _plain_directory(current):
            raise _fail("exact_operation_checkpoint_store_invalid")
    return current


def _same_file_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return bool(
        (not left.st_dev or not right.st_dev or left.st_dev == right.st_dev)
        and (not left.st_ino or not right.st_ino or left.st_ino == right.st_ino)
    )


def _safe_regular_stat(info: os.stat_result, *, max_bytes: int) -> bool:
    return bool(
        stat.S_ISREG(info.st_mode)
        and not stat.S_ISLNK(info.st_mode)
        and not _path_is_reparse(info)
        and int(getattr(info, "st_nlink", 1)) == 1
        and 0 <= info.st_size <= max_bytes
    )


def _read_plain_file_snapshot(
    path: Path,
    *,
    max_bytes: int,
    heartbeat: Callable[[], None],
) -> tuple[bytes, os.stat_result]:
    """Read one stable plain file and return its verified final identity.

    The checkpoint appender needs the final stat from the *same* descriptor it
    read.  Taking a new path stat after ``_read_plain_file`` returned would
    leave a replacement race between those two operations.
    """

    before = os.lstat(path)
    if not _safe_regular_stat(before, max_bytes=max_bytes):
        raise OSError("exact_operation_file_unsafe")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if not (
            _safe_regular_stat(opened, max_bytes=max_bytes)
            and _same_file_identity(before, opened)
            and before.st_size == opened.st_size
        ):
            raise OSError("exact_operation_file_changed")
        chunks: list[bytes] = []
        remaining = opened.st_size
        while remaining:
            heartbeat()
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                raise OSError("exact_operation_file_read_incomplete")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise OSError("exact_operation_file_grew")
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    named_after = os.lstat(path)
    if not (
        _safe_regular_stat(after, max_bytes=max_bytes)
        and _safe_regular_stat(named_after, max_bytes=max_bytes)
        and _same_file_identity(before, after)
        and _same_file_identity(after, named_after)
        and before.st_size == after.st_size == named_after.st_size
        and before.st_mtime_ns == after.st_mtime_ns == named_after.st_mtime_ns
    ):
        raise OSError("exact_operation_file_changed")
    return b"".join(chunks), named_after


def _read_plain_file(
    path: Path,
    *,
    max_bytes: int,
    heartbeat: Callable[[], None],
) -> bytes:
    raw, _ = _read_plain_file_snapshot(
        path,
        max_bytes=max_bytes,
        heartbeat=heartbeat,
    )
    return raw


def _write_descriptor_all(
    descriptor: int,
    raw: bytes,
    *,
    heartbeat: Callable[[], None],
) -> None:
    offset = 0
    while offset < len(raw):
        heartbeat()
        written = os.write(descriptor, raw[offset : offset + 64 * 1024])
        if written <= 0:
            raise OSError("exact_operation_write_incomplete")
        offset += written


class ExactOperationWriterLock:
    """One fixed archive-wide OS lock shared by all exact-operation writers."""

    def __init__(
        self,
        archive_root: Path | str,
        *,
        timeout_seconds: float = 2.0,
        heartbeat: Callable[[], None] | None = None,
    ) -> None:
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not 0 <= timeout_seconds <= 60
        ):
            raise _fail("exact_operation_writer_lock_invalid")
        self.archive_root = _exact_operation_archive_root(archive_root)
        self.private_root = _ensure_private_directory(
            self.archive_root,
            tuple(Path(EXACT_OPERATION_LOCAL_ROOT).parts),
        )
        self.path = self.private_root / ".writer.lock"
        self.timeout_seconds = float(timeout_seconds)
        self.heartbeat = heartbeat or (lambda: None)
        self._operation_mutex = threading.RLock()
        self._handle: Any = None
        self._identity: tuple[int, int] | None = None
        self._dependent_descriptors: set[int] = set()
        self.held = False

    def _open(self) -> Any:
        flags = os.O_RDWR | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        created = False
        try:
            descriptor = os.open(
                self.path,
                flags | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            created = True
        except FileExistsError:
            descriptor = os.open(self.path, flags)
        try:
            if created:
                _write_descriptor_all(
                    descriptor,
                    _LOCK_BYTES,
                    heartbeat=self.heartbeat,
                )
                os.fsync(descriptor)
                if not _fsync_directory(self.private_root):
                    raise OSError("exact_operation_directory_sync_failed")
            opened = os.fstat(descriptor)
            named = os.lstat(self.path)
            if not (
                _safe_regular_stat(opened, max_bytes=len(_LOCK_BYTES))
                and _safe_regular_stat(named, max_bytes=len(_LOCK_BYTES))
                and opened.st_size == named.st_size == len(_LOCK_BYTES)
                and _same_file_identity(opened, named)
            ):
                raise OSError("exact_operation_writer_lock_unsafe")
            return os.fdopen(descriptor, "r+b", buffering=0)
        except BaseException:
            os.close(descriptor)
            raise

    def __enter__(self) -> "ExactOperationWriterLock":
        if self._handle is not None:
            raise _fail("exact_operation_writer_lock_invalid")
        try:
            self._handle = self._open()
        except OSError:
            raise _fail("exact_operation_writer_lock_invalid") from None
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            try:
                self._handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(
                        self._handle.fileno(),
                        fcntl.LOCK_EX | fcntl.LOCK_NB,
                    )
                break
            except OSError:
                if time.monotonic() >= deadline:
                    self._handle.close()
                    self._handle = None
                    raise _fail("exact_operation_writer_busy") from None
                self.heartbeat()
                time.sleep(0.02)
        opened = os.fstat(self._handle.fileno())
        named = os.lstat(self.path)
        self._handle.seek(0)
        raw = self._handle.read(len(_LOCK_BYTES) + 1)
        if not (
            _safe_regular_stat(opened, max_bytes=len(_LOCK_BYTES))
            and _safe_regular_stat(named, max_bytes=len(_LOCK_BYTES))
            and _same_file_identity(opened, named)
            and opened.st_size == named.st_size == len(_LOCK_BYTES)
            and raw == _LOCK_BYTES
        ):
            self.__exit__(None, None, None)
            raise _fail("exact_operation_writer_lock_invalid")
        self._identity = (opened.st_dev, opened.st_ino)
        self.held = True
        return self

    def verify_held(self) -> None:
        if not self.held or self._handle is None or self._identity is None:
            raise _fail("exact_operation_writer_lock_required")
        try:
            opened = os.fstat(self._handle.fileno())
            named = os.lstat(self.path)
            self._handle.seek(0)
            raw = self._handle.read(len(_LOCK_BYTES) + 1)
        except OSError:
            raise _fail("exact_operation_writer_lock_invalid") from None
        if not (
            _safe_regular_stat(opened, max_bytes=len(_LOCK_BYTES))
            and _safe_regular_stat(named, max_bytes=len(_LOCK_BYTES))
            and _same_file_identity(opened, named)
            and (opened.st_dev, opened.st_ino) == self._identity
            and raw == _LOCK_BYTES
        ):
            raise _fail("exact_operation_writer_lock_invalid")

    def _track_dependent_descriptor(self, descriptor: int) -> None:
        """Keep an append handle inside this writer-lock lifetime."""

        self.verify_held()
        if type(descriptor) is not int or descriptor < 0:
            raise OSError("exact_operation_writer_descriptor_invalid")
        self._dependent_descriptors.add(descriptor)

    def _dependent_descriptor_is_tracked(self, descriptor: int) -> bool:
        return bool(self.held and descriptor in self._dependent_descriptors)

    def _close_dependent_descriptor(
        self,
        descriptor: int,
        *,
        suppress_errors: bool,
    ) -> None:
        if descriptor not in self._dependent_descriptors:
            return
        self._dependent_descriptors.discard(descriptor)
        try:
            os.close(descriptor)
        except OSError:
            if not suppress_errors:
                raise

    def __exit__(self, *_exc_info: Any) -> bool:
        if self._handle is None:
            return False
        try:
            if self.held:
                # Checkpoint append handles never outlive the archive-wide
                # writer lock.  Closing them before unlock prevents a later
                # writer from racing stale cached descriptors after failures.
                for descriptor in tuple(self._dependent_descriptors):
                    self._close_dependent_descriptor(
                        descriptor,
                        suppress_errors=True,
                    )
                self._handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.held = False
            self._identity = None
            self._handle.close()
            self._handle = None
        return False


def exact_operation_writer_lock(
    archive_root: Path | str,
    *,
    timeout_seconds: float = 2.0,
    heartbeat: Callable[[], None] | None = None,
) -> ExactOperationWriterLock:
    return ExactOperationWriterLock(
        archive_root,
        timeout_seconds=timeout_seconds,
        heartbeat=heartbeat,
    )


def _strict_json_document(raw: bytes) -> dict[str, Any]:
    def no_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_json_member")
            result[key] = value
        return result

    parsed = json.loads(raw.decode("ascii"), object_pairs_hook=no_duplicate_pairs)
    if not isinstance(parsed, dict) or _canonical_json_bytes(parsed) != raw:
        raise ValueError("noncanonical_json_document")
    return parsed


@dataclass(frozen=True)
class _CheckpointAppendCursor:
    """Verified file state from the one linear checkpoint scan.

    A missing file is represented by ``stat_result=None``.  Existing empty
    files remain distinguishable from missing files so a crash-created or
    colliding empty path is never silently adopted as a new checkpoint.
    """

    stat_result: os.stat_result | None

    @property
    def exists(self) -> bool:
        return self.stat_result is not None

    @property
    def size(self) -> int:
        if self.stat_result is None:
            return 0
        return self.stat_result.st_size


def _checkpoint_cursor_matches(
    expected: _CheckpointAppendCursor,
    observed: os.stat_result,
    *,
    compare_change_time: bool = False,
) -> bool:
    prior = expected.stat_result
    return bool(
        prior is not None
        and _safe_regular_stat(
            observed,
            max_bytes=_MAX_CHECKPOINT_FILE_BYTES,
        )
        and _same_file_identity(prior, observed)
        and prior.st_size == observed.st_size
        and prior.st_mtime_ns == observed.st_mtime_ns
        and (
            not compare_change_time
            or prior.st_ctime_ns == observed.st_ctime_ns
        )
    )


def _read_descriptor_range(
    descriptor: int,
    *,
    offset: int,
    size: int,
    heartbeat: Callable[[], None],
) -> bytes:
    """Read one bounded range from an already verified read/write handle."""

    if offset < 0 or size < 0 or size > 64 * 1024:
        raise OSError("exact_operation_checkpoint_range_invalid")
    os.lseek(descriptor, offset, os.SEEK_SET)
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        heartbeat()
        chunk = os.read(descriptor, remaining)
        if not chunk:
            raise OSError("exact_operation_checkpoint_range_incomplete")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


class FileExactOperationCheckpointStore:
    """Durable private JSONL checkpoints and create-or-match final receipts."""

    def __init__(
        self,
        archive_root: Path | str,
        *,
        writer_lock: ExactOperationWriterLock,
    ) -> None:
        self.archive_root = _exact_operation_archive_root(archive_root)
        if (
            type(writer_lock) is not ExactOperationWriterLock
            or writer_lock.archive_root != self.archive_root
        ):
            raise _fail("exact_operation_writer_lock_required")
        writer_lock.verify_held()
        self.writer_lock = writer_lock
        self.private_root = _ensure_private_directory(
            self.archive_root,
            tuple(Path(EXACT_OPERATION_LOCAL_ROOT).parts),
        )
        self.checkpoints_root = _ensure_private_directory(
            self.private_root,
            ("checkpoints",),
        )
        self.results_root = _ensure_private_directory(
            self.archive_root,
            tuple(Path(EXACT_OPERATION_RECEIPTS_ROOT).parts),
        )
        # All stores that share this held archive writer lock share one mutex.
        # This makes accidental same-process concurrent use deterministic
        # instead of allowing callers to race append cursors or finalization.
        self._checkpoint_mutex = writer_lock._operation_mutex
        self._append_cursors: dict[str, _CheckpointAppendCursor] = {}
        self._append_descriptors: dict[str, int] = {}

    def _assert_lock(self) -> None:
        self.writer_lock.verify_held()

    def _close_append_descriptor(
        self,
        execution_sha256: str,
        *,
        suppress_errors: bool,
    ) -> None:
        descriptor = self._append_descriptors.pop(execution_sha256, None)
        if descriptor is None:
            return
        self.writer_lock._close_dependent_descriptor(
            descriptor,
            suppress_errors=suppress_errors,
        )

    @staticmethod
    def _filename(execution_sha256: str, suffix: str) -> str:
        return _digest(
            execution_sha256,
            code="exact_operation_checkpoint_store_invalid",
        ).removeprefix("sha256:") + suffix

    def _checkpoint_path(self, execution_sha256: str) -> Path:
        return self.checkpoints_root / self._filename(execution_sha256, ".jsonl")

    def _result_path(self, execution_sha256: str) -> Path:
        return self.results_root / self._filename(execution_sha256, ".json")

    def _load_raw_with_cursor(
        self,
        execution_sha256: str,
        *,
        heartbeat: Callable[[], None],
    ) -> tuple[bytes, _CheckpointAppendCursor]:
        path = self._checkpoint_path(execution_sha256)
        try:
            raw, info = _read_plain_file_snapshot(
                path,
                max_bytes=_MAX_CHECKPOINT_FILE_BYTES,
                heartbeat=heartbeat,
            )
            return raw, _CheckpointAppendCursor(info)
        except FileNotFoundError:
            return b"", _CheckpointAppendCursor(None)
        except OSError:
            raise _fail("exact_operation_checkpoint_store_invalid") from None

    def load(
        self,
        execution_sha256: str,
        *,
        heartbeat: Callable[[], None],
    ) -> Sequence[Mapping[str, Any]]:
        with self._checkpoint_mutex:
            self._assert_lock()
            try:
                self._close_append_descriptor(
                    execution_sha256,
                    suppress_errors=False,
                )
            except OSError:
                raise _fail("exact_operation_checkpoint_store_invalid") from None
            raw, cursor = self._load_raw_with_cursor(
                execution_sha256,
                heartbeat=heartbeat,
            )
            if not raw:
                self._append_cursors[execution_sha256] = cursor
                return []
            if not raw.endswith(b"\n"):
                raise _fail("exact_operation_checkpoint_store_invalid")
            rows: list[dict[str, Any]] = []
            try:
                for line in raw.splitlines(keepends=True):
                    heartbeat()
                    if not line.endswith(b"\n") or line == b"\n":
                        raise ValueError("invalid_jsonl_record")
                    rows.append(_strict_json_document(line[:-1]))
            except (UnicodeError, ValueError, json.JSONDecodeError):
                raise _fail("exact_operation_checkpoint_store_invalid") from None
            # Publish the cursor only after every existing row passed strict
            # canonical JSON validation.  A resumed process therefore pays one
            # O(n) scan, while all following appends are bounded O(1).
            self._append_cursors[execution_sha256] = cursor
            return rows

    def resume_checkpoint_present(
        self,
        execution_sha256: str,
        *,
        heartbeat: Callable[[], None] | None = None,
    ) -> bool:
        """Fail closed unless the exact execution has a strict durable row."""

        return bool(
            self.load(
                execution_sha256,
                heartbeat=heartbeat or (lambda: None),
            )
        )

    def append(
        self,
        execution_sha256: str,
        checkpoint: Mapping[str, Any],
        *,
        heartbeat: Callable[[], None],
    ) -> None:
        with self._checkpoint_mutex:
            self._assert_lock()
            if not isinstance(checkpoint, Mapping):
                raise _fail("exact_operation_checkpoint_store_invalid")
            line = _canonical_json_bytes(dict(checkpoint)) + b"\n"
            if len(line) > 64 * 1024:
                raise _fail("exact_operation_checkpoint_store_invalid")
            path = self._checkpoint_path(execution_sha256)
            cursor = self._append_cursors.get(execution_sha256)
            if cursor is None:
                # Direct store users may call append() without load().  Scan
                # once here so legacy v1 JSONL remains compatible and corrupt
                # prefixes are never extended.
                self.load(execution_sha256, heartbeat=heartbeat)
                cursor = self._append_cursors[execution_sha256]
            if cursor.size + len(line) > _MAX_CHECKPOINT_FILE_BYTES:
                raise _fail("exact_operation_checkpoint_store_invalid")
            # An existing zero-byte checkpoint is a collision or a prior crash
            # before the first durable row.  Preserve the former fail-closed
            # behavior instead of treating it as a missing path.
            if cursor.exists and cursor.size == 0:
                raise _fail("exact_operation_checkpoint_write_failed")

            flags = os.O_RDWR | os.O_APPEND | getattr(os, "O_BINARY", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            created = not cursor.exists
            descriptor = self._append_descriptors.get(execution_sha256)
            if (
                descriptor is not None
                and not self.writer_lock._dependent_descriptor_is_tracked(
                    descriptor
                )
            ):
                self._append_descriptors.pop(execution_sha256, None)
                descriptor = None
            if descriptor is None:
                try:
                    descriptor = os.open(
                        path,
                        (
                            flags | os.O_CREAT | os.O_EXCL
                            if created
                            else flags
                        ),
                        0o600,
                    )
                except OSError:
                    raise _fail("exact_operation_checkpoint_write_failed") from None
                try:
                    self.writer_lock._track_dependent_descriptor(descriptor)
                    self._append_descriptors[execution_sha256] = descriptor
                except BaseException:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass
                    raise
            final_info: os.stat_result | None = None
            try:
                opened = os.fstat(descriptor)
                named = os.lstat(path)
                valid_start = bool(
                    _safe_regular_stat(
                        opened,
                        max_bytes=_MAX_CHECKPOINT_FILE_BYTES,
                    )
                    and _safe_regular_stat(
                        named,
                        max_bytes=_MAX_CHECKPOINT_FILE_BYTES,
                    )
                    and _same_file_identity(opened, named)
                )
                if created:
                    valid_start = valid_start and opened.st_size == named.st_size == 0
                else:
                    valid_start = bool(
                        valid_start
                        and _checkpoint_cursor_matches(cursor, opened)
                        and _checkpoint_cursor_matches(
                            cursor,
                            named,
                            compare_change_time=True,
                        )
                    )
                if not valid_start:
                    raise OSError("exact_operation_checkpoint_changed")

                _write_descriptor_all(descriptor, line, heartbeat=heartbeat)
                # Every row remains its own crash-durability boundary.  The
                # containing directory only needs a durability sync when this
                # call created the name; file growth is covered by this fsync.
                os.fsync(descriptor)
                after_write = os.fstat(descriptor)
                named_after_write = os.lstat(path)
                expected_size = cursor.size + len(line)
                if not (
                    _safe_regular_stat(
                        after_write,
                        max_bytes=_MAX_CHECKPOINT_FILE_BYTES,
                    )
                    and _safe_regular_stat(
                        named_after_write,
                        max_bytes=_MAX_CHECKPOINT_FILE_BYTES,
                    )
                    and _same_file_identity(opened, after_write)
                    and _same_file_identity(after_write, named_after_write)
                    and after_write.st_size
                    == named_after_write.st_size
                    == expected_size
                    and _read_descriptor_range(
                        descriptor,
                        offset=cursor.size,
                        size=len(line),
                        heartbeat=heartbeat,
                    )
                    == line
                ):
                    raise OSError("exact_operation_checkpoint_changed")
                after_verify = os.fstat(descriptor)
                named_after_verify = os.lstat(path)
                if not (
                    _same_file_identity(after_write, after_verify)
                    and _same_file_identity(after_verify, named_after_verify)
                    and after_verify.st_size
                    == named_after_verify.st_size
                    == expected_size
                    and after_write.st_mtime_ns
                    == after_verify.st_mtime_ns
                    == named_after_verify.st_mtime_ns
                ):
                    raise OSError("exact_operation_checkpoint_changed")
                final_info = after_verify
            except OSError:
                self._close_append_descriptor(
                    execution_sha256,
                    suppress_errors=True,
                )
                raise _fail("exact_operation_checkpoint_write_failed") from None

            if created:
                if not _fsync_directory(self.checkpoints_root):
                    self._close_append_descriptor(
                        execution_sha256,
                        suppress_errors=True,
                    )
                    raise _fail("exact_operation_checkpoint_write_failed")
            assert final_info is not None
            try:
                named_final = os.lstat(path)
            except OSError:
                self._close_append_descriptor(
                    execution_sha256,
                    suppress_errors=True,
                )
                raise _fail("exact_operation_checkpoint_write_failed") from None
            final_cursor = _CheckpointAppendCursor(final_info)
            if not _checkpoint_cursor_matches(final_cursor, named_final):
                self._close_append_descriptor(
                    execution_sha256,
                    suppress_errors=True,
                )
                raise _fail("exact_operation_checkpoint_write_failed")
            self._append_cursors[execution_sha256] = _CheckpointAppendCursor(
                named_final
            )

    def finalize(
        self,
        result: Mapping[str, Any],
        *,
        heartbeat: Callable[[], None],
    ) -> str:
        with self._checkpoint_mutex:
            return self._finalize_locked(result, heartbeat=heartbeat)

    def _finalize_locked(
        self,
        result: Mapping[str, Any],
        *,
        heartbeat: Callable[[], None],
    ) -> str:
        self._assert_lock()
        result_document = _validate_stable_result_document(result)
        checkpoint_rows = self.load(
            result_document["execution_sha256"],
            heartbeat=heartbeat,
        )
        _validate_final_checkpoint_evidence(
            checkpoint_rows,
            result=result_document,
        )
        receipt_basis = {
            "schema": FINAL_RECEIPT_SCHEMA,
            "result": result_document,
        }
        receipt_sha256 = _digest_document(receipt_basis)
        receipt = {**receipt_basis, "receipt_sha256": receipt_sha256}
        raw = _canonical_json_bytes(receipt) + b"\n"
        path = self._result_path(result_document["execution_sha256"])
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = -1
        try:
            descriptor = os.open(path, flags, 0o600)
            _write_descriptor_all(descriptor, raw, heartbeat=heartbeat)
            os.fsync(descriptor)
        except FileExistsError:
            try:
                existing = _read_plain_file(
                    path,
                    max_bytes=_MAX_CANONICAL_BYTES,
                    heartbeat=heartbeat,
                )
            except OSError:
                raise _fail("exact_operation_result_receipt_failed") from None
            if existing != raw:
                raise _fail("exact_operation_result_receipt_failed")
            return receipt_sha256
        except OSError:
            raise _fail("exact_operation_result_receipt_failed") from None
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        if not _fsync_directory(self.results_root):
            raise _fail("exact_operation_result_receipt_failed")
        try:
            reread = _read_plain_file(
                path,
                max_bytes=_MAX_CANONICAL_BYTES,
                heartbeat=heartbeat,
            )
        except OSError:
            raise _fail("exact_operation_result_receipt_failed") from None
        if reread != raw:
            raise _fail("exact_operation_result_receipt_failed")
        return receipt_sha256

    def load_final_receipt(
        self,
        execution_sha256: str,
        *,
        heartbeat: Callable[[], None] | None = None,
    ) -> dict[str, Any] | None:
        with self._checkpoint_mutex:
            return self._load_final_receipt_locked(
                execution_sha256,
                heartbeat=heartbeat,
            )

    def _load_final_receipt_locked(
        self,
        execution_sha256: str,
        *,
        heartbeat: Callable[[], None] | None = None,
    ) -> dict[str, Any] | None:
        self._assert_lock()
        path = self._result_path(execution_sha256)
        callback = heartbeat or (lambda: None)
        try:
            raw = _read_plain_file(
                path,
                max_bytes=_MAX_CANONICAL_BYTES,
                heartbeat=callback,
            )
        except FileNotFoundError:
            return None
        except OSError:
            raise _fail("exact_operation_result_receipt_failed") from None
        if not raw.endswith(b"\n"):
            raise _fail("exact_operation_result_receipt_failed")
        try:
            document = _strict_json_document(raw[:-1])
        except (UnicodeError, ValueError, json.JSONDecodeError):
            raise _fail("exact_operation_result_receipt_failed") from None
        if (
            document.get("schema") != FINAL_RECEIPT_SCHEMA
            or not isinstance(document.get("result"), Mapping)
            or document["result"].get("execution_sha256") != execution_sha256
            or type(document.get("receipt_sha256")) is not str
        ):
            raise _fail("exact_operation_result_receipt_failed")
        _validate_stable_result_document(document["result"])
        supplied = _digest(
            document["receipt_sha256"],
            code="exact_operation_result_receipt_failed",
        )
        basis = dict(document)
        basis.pop("receipt_sha256")
        if not hmac.compare_digest(supplied, _digest_document(basis)):
            raise _fail("exact_operation_result_receipt_failed")
        return document


def _validate_final_checkpoint_evidence(
    rows: Sequence[Mapping[str, Any]],
    *,
    result: Mapping[str, Any],
) -> None:
    """Require a complete generic checkpoint chain before final publication."""

    if (
        not isinstance(rows, Sequence)
        or isinstance(rows, (str, bytes))
        or not rows
        or len(rows) != result["checkpoint_count"]
    ):
        raise _fail("exact_operation_result_receipt_failed")
    expected_keys = {
        "schema",
        "manifest_sha256",
        "execution_sha256",
        "sequence",
        "mode",
        "approval",
        "item_ordinal",
        "item_id",
        "stage",
        "field_ref",
        "observed_sha256",
        "field_receipt_sha256",
        "previous_checkpoint_sha256",
        "checkpoint_sha256",
    }
    previous: str | None = None
    approval_document: dict[str, Any] | None = None
    approval_initialized = False
    current_item: tuple[int, str] | None = None
    current_fields: set[str] = set()
    started_items: set[tuple[int, str]] = set()
    verified_items: set[tuple[int, str]] = set()
    field_receipts: list[str] = []
    for sequence, raw_row in enumerate(rows):
        if not isinstance(raw_row, Mapping):
            raise _fail("exact_operation_result_receipt_failed")
        row = dict(raw_row)
        if set(row) != expected_keys:
            raise _fail("exact_operation_result_receipt_failed")
        if (
            row.get("schema") != CHECKPOINT_SCHEMA
            or row.get("manifest_sha256") != result["manifest_sha256"]
            or row.get("execution_sha256") != result["execution_sha256"]
            or row.get("sequence") != sequence
            or row.get("mode") != result["mode"]
            or row.get("previous_checkpoint_sha256") != previous
            or type(row.get("item_ordinal")) is not int
            or row["item_ordinal"] < 0
            or type(row.get("item_id")) is not str
            or not row["item_id"]
        ):
            raise _fail("exact_operation_result_receipt_failed")
        basis = dict(row)
        supplied_checkpoint = _digest(
            basis.pop("checkpoint_sha256"),
            code="exact_operation_result_receipt_failed",
        )
        if not hmac.compare_digest(
            supplied_checkpoint,
            _digest_document(basis),
        ):
            raise _fail("exact_operation_result_receipt_failed")
        previous = supplied_checkpoint

        raw_approval = row.get("approval")
        if raw_approval is None:
            row_approval = None
        elif isinstance(raw_approval, Mapping):
            approval = dict(raw_approval)
            if set(approval) != {
                "schema",
                "approval_id",
                "context_sha256",
                "approval_authority_sha256",
                "binding_sha256",
            } or approval.get("schema") != APPROVAL_AUTHORITY_SCHEMA:
                raise _fail("exact_operation_result_receipt_failed")
            try:
                parsed_authority = ExactOperationApprovalAuthority(
                    approval_id=approval["approval_id"],
                    context_sha256=approval["context_sha256"],
                    approval_authority_sha256=approval[
                        "approval_authority_sha256"
                    ],
                    binding_sha256=approval["binding_sha256"],
                )
            except ExactOperationManifestError:
                raise _fail("exact_operation_result_receipt_failed") from None
            row_approval = parsed_authority.document()
        else:
            raise _fail("exact_operation_result_receipt_failed")
        if not approval_initialized:
            approval_document = row_approval
            approval_initialized = True
        elif row_approval != approval_document:
            raise _fail("exact_operation_result_receipt_failed")

        item = (row["item_ordinal"], row["item_id"])
        stage = row.get("stage")
        field_ref = row.get("field_ref")
        observed = row.get("observed_sha256")
        field_receipt = row.get("field_receipt_sha256")
        if stage == "started":
            if (
                current_item is not None
                or item in started_items
                or field_ref is not None
                or observed is not None
                or field_receipt is not None
            ):
                raise _fail("exact_operation_result_receipt_failed")
            current_item = item
            current_fields = set()
            started_items.add(item)
        elif stage == "field_verified":
            if (
                current_item != item
                or type(field_ref) is not str
                or not field_ref
                or field_ref in current_fields
            ):
                raise _fail("exact_operation_result_receipt_failed")
            _digest(observed, code="exact_operation_result_receipt_failed")
            validated_receipt = _digest(
                field_receipt,
                code="exact_operation_result_receipt_failed",
            )
            current_fields.add(field_ref)
            field_receipts.append(validated_receipt)
        elif stage == "item_verified":
            if (
                current_item != item
                or not current_fields
                or item in verified_items
                or field_ref is not None
                or field_receipt is not None
            ):
                raise _fail("exact_operation_result_receipt_failed")
            _digest(observed, code="exact_operation_result_receipt_failed")
            verified_items.add(item)
            current_item = None
            current_fields = set()
        else:
            raise _fail("exact_operation_result_receipt_failed")
    expected_approval_binding = (
        approval_document["binding_sha256"]
        if approval_document is not None
        else None
    )
    if (
        current_item is not None
        or started_items != verified_items
        or len(started_items) != result["item_count"]
        or len(field_receipts) != result["field_count"]
        or len(field_receipts) != result["field_receipt_count"]
        or _digest_document(field_receipts)
        != result["field_receipt_set_sha256"]
        or expected_approval_binding != result["approval_binding_sha256"]
    ):
        raise _fail("exact_operation_result_receipt_failed")


@dataclass
class _CheckpointState:
    rows: list[dict[str, Any]]
    started_items: set[int]
    completed_fields: dict[int, set[str]]
    completed_field_count: int
    verified_items: set[int]
    last_checkpoint_sha256: str | None

    @property
    def next_sequence(self) -> int:
        return len(self.rows)


def _selection(
    manifest: ExactOperationManifest,
    *,
    mode: ExecutionMode,
    selected_fields: Iterable[tuple[str, str]] | None,
) -> tuple[tuple[ExactOperationItem, tuple[ExactFieldEffect, ...]], ...]:
    if mode == "apply":
        if selected_fields is not None:
            raise _fail("exact_operation_revert_selection_invalid")
        return tuple((item, item.fields) for item in manifest.items)
    if selected_fields is None:
        raise _fail("exact_operation_revert_selection_invalid")
    requested = tuple(selected_fields)
    if not requested or any(
        type(value) is not tuple
        or len(value) != 2
        or type(value[0]) is not str
        or type(value[1]) is not str
        for value in requested
    ):
        raise _fail("exact_operation_revert_selection_invalid")
    requested_set = set(requested)
    if len(requested_set) != len(requested):
        raise _fail("exact_operation_revert_selection_invalid")
    selected: list[tuple[ExactOperationItem, tuple[ExactFieldEffect, ...]]] = []
    found: set[tuple[str, str]] = set()
    for item in manifest.items:
        fields = tuple(
            field
            for field in item.fields
            if (item.item_id, field.field_ref) in requested_set
        )
        if fields:
            selected.append((item, fields))
            found.update((item.item_id, field.field_ref) for field in fields)
    if found != requested_set:
        raise _fail("exact_operation_revert_selection_invalid")
    return tuple(selected)


def _execution_sha256(
    manifest: ExactOperationManifest,
    *,
    mode: ExecutionMode,
    selection: tuple[tuple[ExactOperationItem, tuple[ExactFieldEffect, ...]], ...],
    approval_authority: ExactOperationApprovalAuthority | None,
) -> str:
    return _digest_document(
        {
            "schema": "wom-kit/exact-operation-execution/v1",
            "manifest_sha256": manifest.manifest_sha256,
            "mode": mode,
            "approval_binding_sha256": (
                approval_authority.binding_sha256
                if approval_authority is not None
                else None
            ),
            "selection": [
                {
                    "ordinal": item.ordinal,
                    "item_id": item.item_id,
                    "field_refs": [field.field_ref for field in fields],
                }
                for item, fields in selection
            ],
        }
    )


def exact_operation_execution_sha256(
    manifest: ExactOperationManifest,
    *,
    mode: ExecutionMode = "apply",
    selected_fields: Iterable[tuple[str, str]] | None = None,
    approval_authority: ExactOperationApprovalAuthority | None = None,
) -> str:
    """Return the fixed digest that addresses checkpoints for one execution."""

    if type(manifest) is not ExactOperationManifest or mode not in {
        "apply",
        "revert",
    }:
        raise _fail("exact_operation_manifest_invalid")
    if (
        approval_authority is not None
        and type(approval_authority) is not ExactOperationApprovalAuthority
    ):
        raise _fail("exact_operation_manifest_invalid")
    selection = _selection(
        manifest,
        mode=mode,
        selected_fields=selected_fields,
    )
    return _execution_sha256(
        manifest,
        mode=mode,
        selection=selection,
        approval_authority=approval_authority,
    )


def _expected_hash(field: ExactFieldEffect, *, mode: ExecutionMode, destination: bool) -> str:
    if mode == "apply":
        return field.post_sha256 if destination else field.pre_sha256
    return field.pre_sha256 if destination else field.post_sha256


def _payload_state(mode: ExecutionMode, *, destination: bool) -> Literal["pre", "post"]:
    if mode == "apply":
        return "post" if destination else "pre"
    return "pre" if destination else "post"


def _validate_payloads(
    selection: tuple[tuple[ExactOperationItem, tuple[ExactFieldEffect, ...]], ...],
    payloads: ExactOperationPayloadProvider,
    *,
    heartbeat: Callable[[], None],
) -> None:
    for item, fields in selection:
        for field in fields:
            for state, expected in (
                ("pre", field.pre_sha256),
                ("post", field.post_sha256),
                ("source", field.source_sha256),
            ):
                try:
                    value = payloads.field_value(
                        item_id=item.item_id,
                        field_ref=field.field_ref,
                        state=state,
                        heartbeat=heartbeat,
                    )
                except Exception:
                    raise _fail("exact_operation_payload_mismatch") from None
                if not hmac.compare_digest(hash_field_value(value), expected):
                    raise _fail("exact_operation_payload_mismatch")


def _read_hash(
    verifier: ExactOperationIndependentVerifier,
    item: ExactOperationItem,
    field: ExactFieldEffect,
    *,
    heartbeat: Callable[[], None],
) -> str:
    try:
        identity = _digest(
            verifier.target_identity_sha256(
                target_kind=item.target_kind,
                target_ref=item.target_ref,
                heartbeat=heartbeat,
            ),
            code="exact_operation_target_identity_mismatch",
        )
        if not hmac.compare_digest(identity, item.target_identity_sha256):
            raise _fail("exact_operation_target_identity_mismatch")
        value = verifier.read_field(
            target_kind=item.target_kind,
            target_ref=item.target_ref,
            field_ref=field.field_ref,
            heartbeat=heartbeat,
        )
        return hash_field_value(value)
    except ExactOperationManifestError:
        raise
    except Exception:
        raise _fail("exact_operation_independent_verify_failed") from None


def _checkpoint_item_state_sha256(
    fields: tuple[ExactFieldEffect, ...],
    *,
    mode: ExecutionMode,
) -> str:
    return _digest_document(
        [
            {
                "field_ref": field.field_ref,
                "sha256": _expected_hash(field, mode=mode, destination=True),
            }
            for field in fields
        ]
    )


def _field_receipt_sha256(
    manifest: ExactOperationManifest,
    *,
    execution_sha256: str,
    mode: ExecutionMode,
    item: ExactOperationItem,
    field: ExactFieldEffect,
    observed_sha256: str,
) -> str:
    """Bind one independently observed field write without echoing its value."""

    return _digest_document(
        {
            "schema": FIELD_RECEIPT_SCHEMA,
            "manifest_sha256": manifest.manifest_sha256,
            "execution_sha256": execution_sha256,
            "mode": mode,
            "item_ordinal": item.ordinal,
            "item_id": item.item_id,
            "target_identity_sha256": item.target_identity_sha256,
            "field_ref": field.field_ref,
            "pre_sha256": field.pre_sha256,
            "post_sha256": field.post_sha256,
            "source_sha256": field.source_sha256,
            "observed_sha256": observed_sha256,
        }
    )


def _validate_stable_result_document(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise _fail("exact_operation_result_receipt_failed")
    result = dict(value)
    if set(result) != {
        "schema",
        "status",
        "mode",
        "manifest_sha256",
        "execution_sha256",
        "approval_binding_sha256",
        "item_count",
        "field_count",
        "checkpoint_count",
        "field_receipt_count",
        "field_receipt_set_sha256",
        "independent_verification_sha256",
        "private_values_echoed",
        "result_sha256",
    }:
        raise _fail("exact_operation_result_receipt_failed")
    if (
        result.get("schema") != RESULT_SCHEMA
        or result.get("status") != "completed"
        or result.get("mode") not in {"apply", "revert"}
        or result.get("private_values_echoed") is not False
    ):
        raise _fail("exact_operation_result_receipt_failed")
    for name in (
        "manifest_sha256",
        "execution_sha256",
        "field_receipt_set_sha256",
        "independent_verification_sha256",
        "result_sha256",
    ):
        _digest(result.get(name), code="exact_operation_result_receipt_failed")
    approval_binding_sha256 = result.get("approval_binding_sha256")
    if approval_binding_sha256 is not None:
        _digest(
            approval_binding_sha256,
            code="exact_operation_result_receipt_failed",
        )
    for name in (
        "item_count",
        "field_count",
        "checkpoint_count",
        "field_receipt_count",
    ):
        if type(result.get(name)) is not int or result[name] < 0:
            raise _fail("exact_operation_result_receipt_failed")
    if (
        result["field_receipt_count"] != result["field_count"]
        or result["checkpoint_count"]
        != result["field_count"] + 2 * result["item_count"]
    ):
        raise _fail("exact_operation_result_receipt_failed")
    basis = dict(result)
    supplied = basis.pop("result_sha256")
    if not hmac.compare_digest(supplied, _digest_document(basis)):
        raise _fail("exact_operation_result_receipt_failed")
    return result


def _checkpoint_basis(
    *,
    manifest_sha256: str,
    execution_sha256: str,
    sequence: int,
    mode: ExecutionMode,
    item: ExactOperationItem,
    stage: str,
    field_ref: str | None,
    observed_sha256: str | None,
    field_receipt_sha256: str | None,
    previous_checkpoint_sha256: str | None,
    approval_authority: ExactOperationApprovalAuthority | None,
) -> dict[str, Any]:
    return {
        "schema": CHECKPOINT_SCHEMA,
        "manifest_sha256": manifest_sha256,
        "execution_sha256": execution_sha256,
        "sequence": sequence,
        "mode": mode,
        "approval": (
            approval_authority.document()
            if approval_authority is not None
            else None
        ),
        "item_ordinal": item.ordinal,
        "item_id": item.item_id,
        "stage": stage,
        "field_ref": field_ref,
        "observed_sha256": observed_sha256,
        "field_receipt_sha256": field_receipt_sha256,
        "previous_checkpoint_sha256": previous_checkpoint_sha256,
    }


def _load_checkpoint_state(
    manifest: ExactOperationManifest,
    *,
    mode: ExecutionMode,
    execution_sha256: str,
    selection: tuple[tuple[ExactOperationItem, tuple[ExactFieldEffect, ...]], ...],
    checkpoint_store: ExactOperationCheckpointStore,
    heartbeat: Callable[[], None],
    approval_authority: ExactOperationApprovalAuthority | None,
) -> _CheckpointState:
    try:
        raw_rows = checkpoint_store.load(
            execution_sha256,
            heartbeat=heartbeat,
        )
    except Exception:
        raise _fail("exact_operation_checkpoint_invalid") from None
    if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, (str, bytes)):
        raise _fail("exact_operation_checkpoint_invalid")
    expected_rows_max = sum(len(fields) + 2 for _, fields in selection)
    if len(raw_rows) > expected_rows_max:
        raise _fail("exact_operation_checkpoint_invalid")
    by_ordinal = {item.ordinal: (item, fields) for item, fields in selection}
    started: set[int] = set()
    completed_fields: dict[int, set[str]] = {
        item.ordinal: set() for item, _ in selection
    }
    verified: set[int] = set()
    rows: list[dict[str, Any]] = []
    previous: str | None = None
    expected_item_position = 0
    selection_ordinals = [item.ordinal for item, _ in selection]
    for sequence, raw_row in enumerate(raw_rows):
        if not isinstance(raw_row, Mapping):
            raise _fail("exact_operation_checkpoint_invalid")
        row = dict(raw_row)
        if set(row) != {
            "schema",
            "manifest_sha256",
            "execution_sha256",
            "sequence",
            "mode",
            "approval",
            "item_ordinal",
            "item_id",
            "stage",
            "field_ref",
            "observed_sha256",
            "field_receipt_sha256",
            "previous_checkpoint_sha256",
            "checkpoint_sha256",
        }:
            raise _fail("exact_operation_checkpoint_invalid")
        ordinal = row.get("item_ordinal")
        if type(ordinal) is not int or ordinal not in by_ordinal:
            raise _fail("exact_operation_checkpoint_invalid")
        item, fields = by_ordinal[ordinal]
        if (
            row.get("schema") != CHECKPOINT_SCHEMA
            or row.get("manifest_sha256") != manifest.manifest_sha256
            or row.get("execution_sha256") != execution_sha256
            or row.get("sequence") != sequence
            or row.get("mode") != mode
            or row.get("approval")
            != (
                approval_authority.document()
                if approval_authority is not None
                else None
            )
            or row.get("item_id") != item.item_id
            or row.get("previous_checkpoint_sha256") != previous
        ):
            raise _fail("exact_operation_checkpoint_invalid")
        basis = {key: value for key, value in row.items() if key != "checkpoint_sha256"}
        checkpoint_sha256 = _digest(
            row.get("checkpoint_sha256"), code="exact_operation_checkpoint_invalid"
        )
        if not hmac.compare_digest(checkpoint_sha256, _digest_document(basis)):
            raise _fail("exact_operation_checkpoint_invalid")
        if expected_item_position >= len(selection_ordinals) or ordinal != selection_ordinals[
            expected_item_position
        ]:
            raise _fail("exact_operation_checkpoint_invalid")
        stage = row.get("stage")
        field_ref = row.get("field_ref")
        observed = row.get("observed_sha256")
        field_receipt = row.get("field_receipt_sha256")
        field_by_ref = {field.field_ref: field for field in fields}
        if stage == "started":
            if (
                ordinal in started
                or field_ref is not None
                or observed is not None
                or field_receipt is not None
            ):
                raise _fail("exact_operation_checkpoint_invalid")
            started.add(ordinal)
        elif stage == "field_verified":
            if (
                ordinal not in started
                or type(field_ref) is not str
                or field_ref not in field_by_ref
                or field_ref in completed_fields[ordinal]
            ):
                raise _fail("exact_operation_checkpoint_invalid")
            field = field_by_ref[field_ref]
            if observed != _expected_hash(field, mode=mode, destination=True):
                raise _fail("exact_operation_checkpoint_invalid")
            expected_field_receipt = _field_receipt_sha256(
                manifest,
                execution_sha256=execution_sha256,
                mode=mode,
                item=item,
                field=field,
                observed_sha256=observed,
            )
            if not (
                type(field_receipt) is str
                and hmac.compare_digest(field_receipt, expected_field_receipt)
            ):
                raise _fail("exact_operation_checkpoint_invalid")
            expected_field_index = len(completed_fields[ordinal])
            if fields[expected_field_index].field_ref != field_ref:
                raise _fail("exact_operation_checkpoint_invalid")
            completed_fields[ordinal].add(field_ref)
        elif stage == "item_verified":
            if (
                ordinal not in started
                or completed_fields[ordinal] != set(field_by_ref)
                or ordinal in verified
                or field_ref is not None
                or observed != _checkpoint_item_state_sha256(fields, mode=mode)
                or field_receipt is not None
            ):
                raise _fail("exact_operation_checkpoint_invalid")
            verified.add(ordinal)
            expected_item_position += 1
        else:
            raise _fail("exact_operation_checkpoint_invalid")
        previous = checkpoint_sha256
        rows.append(row)
    return _CheckpointState(
        rows,
        started,
        completed_fields,
        sum(len(value) for value in completed_fields.values()),
        verified,
        previous,
    )


def _append_checkpoint(
    state: _CheckpointState,
    *,
    manifest: ExactOperationManifest,
    execution_sha256: str,
    mode: ExecutionMode,
    item: ExactOperationItem,
    stage: str,
    field_ref: str | None,
    observed_sha256: str | None,
    checkpoint_store: ExactOperationCheckpointStore,
    heartbeat: Callable[[], None],
    approval_authority: ExactOperationApprovalAuthority | None,
) -> None:
    field = None
    field_receipt_sha256 = None
    if stage == "field_verified" and field_ref is not None and observed_sha256 is not None:
        field = next(
            (candidate for candidate in item.fields if candidate.field_ref == field_ref),
            None,
        )
        if field is None:
            raise _fail("exact_operation_checkpoint_invalid")
        field_receipt_sha256 = _field_receipt_sha256(
            manifest,
            execution_sha256=execution_sha256,
            mode=mode,
            item=item,
            field=field,
            observed_sha256=observed_sha256,
        )
    basis = _checkpoint_basis(
        manifest_sha256=manifest.manifest_sha256,
        execution_sha256=execution_sha256,
        sequence=state.next_sequence,
        mode=mode,
        item=item,
        stage=stage,
        field_ref=field_ref,
        observed_sha256=observed_sha256,
        field_receipt_sha256=field_receipt_sha256,
        previous_checkpoint_sha256=state.last_checkpoint_sha256,
        approval_authority=approval_authority,
    )
    row = {**basis, "checkpoint_sha256": _digest_document(basis)}
    try:
        checkpoint_store.append(
            execution_sha256,
            row,
            heartbeat=heartbeat,
        )
    except Exception:
        raise _fail("exact_operation_checkpoint_write_failed") from None
    state.rows.append(row)
    state.last_checkpoint_sha256 = row["checkpoint_sha256"]
    if stage == "started":
        state.started_items.add(item.ordinal)
    elif stage == "field_verified" and field_ref is not None:
        state.completed_fields[item.ordinal].add(field_ref)
        state.completed_field_count += 1
    elif stage == "item_verified":
        state.verified_items.add(item.ordinal)


def _emit(
    hook: Callable[[ExactOperationProgress], None] | None,
    event: ExactOperationProgress,
) -> bool:
    if hook is None:
        return True
    try:
        hook(event)
        return True
    except Exception:
        # Progress is observability, never mutation authority.  A broken sink
        # cannot turn a completed durable write into a false rollback signal.
        return False


@dataclass
class _ProgressPublisher:
    """Keep progress content-free while exposing cooperative heartbeats.

    The runner publishes its first state before it calls any injected adapter.
    An adapter that may remain inside one call for longer than
    ``HEARTBEAT_INTERVAL_SECONDS`` must invoke the supplied ``heartbeat``
    callback at least that often.  Blocking I/O that cannot cooperate must use
    a timeout no longer than that interval.
    """

    hook: Callable[[ExactOperationProgress], None] | None
    clock: Callable[[], float] = time.monotonic
    current: ExactOperationProgress | None = None
    failure_count: int = 0
    last_publish_monotonic: float | None = None

    def publish(self, event: ExactOperationProgress) -> None:
        self.current = event
        self.last_publish_monotonic = self.clock()
        if not _emit(self.hook, event):
            self.failure_count += 1

    def heartbeat(self) -> None:
        if self.current is None:
            return
        now = self.clock()
        if (
            self.last_publish_monotonic is not None
            and now - self.last_publish_monotonic < HEARTBEAT_INTERVAL_SECONDS
        ):
            return
        heartbeat_event = replace(self.current, stage="heartbeat")
        self.current = heartbeat_event
        self.last_publish_monotonic = now
        if not _emit(self.hook, heartbeat_event):
            self.failure_count += 1


def _preflight_target_states(
    selection: tuple[tuple[ExactOperationItem, tuple[ExactFieldEffect, ...]], ...],
    *,
    mode: ExecutionMode,
    verifier: ExactOperationIndependentVerifier,
    checkpoint_state: _CheckpointState,
    resume: bool,
    heartbeat: Callable[[], None],
) -> None:
    """Verify the whole selected CAS boundary before the first new write."""

    for item, fields in selection:
        for field in fields:
            observed = _read_hash(
                verifier,
                item,
                field,
                heartbeat=heartbeat,
            )
            destination = _expected_hash(field, mode=mode, destination=True)
            source = _expected_hash(field, mode=mode, destination=False)
            if (
                item.ordinal in checkpoint_state.verified_items
                or field.field_ref in checkpoint_state.completed_fields[item.ordinal]
            ):
                allowed = hmac.compare_digest(observed, destination)
            elif resume and item.ordinal in checkpoint_state.started_items:
                # Only the currently started item can contain a write that
                # reached the target before its field receipt was appended.
                allowed = hmac.compare_digest(
                    observed, source
                ) or hmac.compare_digest(observed, destination)
            else:
                allowed = hmac.compare_digest(observed, source)
            if not allowed:
                raise _fail("exact_operation_target_state_drifted")


def verify_exact_operation(
    manifest: ExactOperationManifest,
    *,
    verifier: ExactOperationIndependentVerifier,
    state: Literal["pre", "post"],
    selected_fields: Iterable[tuple[str, str]] | None = None,
    heartbeat: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Independently verify exact field state without reading unrelated fields.

    A domain adapter performing a long verification supplies ``heartbeat`` and
    forwards it to its underlying reader at least every ten seconds.
    """

    if type(manifest) is not ExactOperationManifest or state not in {"pre", "post"}:
        raise _fail("exact_operation_manifest_invalid")
    if state == "post":
        selection = _selection(manifest, mode="apply", selected_fields=None)
    elif selected_fields is None:
        selection = tuple((item, item.fields) for item in manifest.items)
    else:
        selection = _selection(
            manifest,
            mode="revert",
            selected_fields=selected_fields,
        )
    rows: list[dict[str, Any]] = []
    all_match = True
    heartbeat_callback = heartbeat or (lambda: None)
    for item, fields in selection:
        item_match = True
        for field in fields:
            observed = _read_hash(
                verifier,
                item,
                field,
                heartbeat=heartbeat_callback,
            )
            expected = field.post_sha256 if state == "post" else field.pre_sha256
            item_match = item_match and hmac.compare_digest(observed, expected)
        rows.append(
            {
                "item_ordinal": item.ordinal,
                "field_count": len(fields),
                "matches": item_match,
            }
        )
        all_match = all_match and item_match
    result_basis = {
        "schema": VERIFICATION_SCHEMA,
        "manifest_sha256": manifest.manifest_sha256,
        "expected_state": state,
        "item_count": len(selection),
        "field_count": sum(len(fields) for _, fields in selection),
        "all_match": all_match,
        "items": rows,
        "private_values_echoed": False,
    }
    return {**result_basis, "verification_sha256": _digest_document(result_basis)}


def _run_exact_operation(
    manifest: ExactOperationManifest,
    *,
    mode: ExecutionMode,
    selected_fields: Iterable[tuple[str, str]] | None,
    payloads: ExactOperationPayloadProvider,
    writer: ExactOperationTargetWriter,
    verifier: ExactOperationIndependentVerifier,
    checkpoint_store: ExactOperationCheckpointStore,
    approval_authority: ExactOperationApprovalAuthority | None,
    resume: bool,
    progress_hook: Callable[[ExactOperationProgress], None] | None,
) -> dict[str, Any]:
    if type(manifest) is not ExactOperationManifest or mode not in {"apply", "revert"}:
        raise _fail("exact_operation_manifest_invalid")
    if writer is verifier:
        raise _fail("exact_operation_independent_verify_failed")
    if (
        approval_authority is not None
        and type(approval_authority) is not ExactOperationApprovalAuthority
    ):
        raise _fail("exact_operation_manifest_invalid")
    publisher = _ProgressPublisher(progress_hook)
    publisher.publish(
        ExactOperationProgress(
            manifest.manifest_sha256,
            None,
            mode,
            "preflight",
            0,
            len(manifest.items),
            0,
            sum(len(item.fields) for item in manifest.items),
        )
    )
    selection = _selection(
        manifest,
        mode=mode,
        selected_fields=selected_fields,
    )
    execution_sha256 = _execution_sha256(
        manifest,
        mode=mode,
        selection=selection,
        approval_authority=approval_authority,
    )
    total_fields = sum(len(fields) for _, fields in selection)
    publisher.publish(
        ExactOperationProgress(
            manifest.manifest_sha256,
            execution_sha256,
            mode,
            "preflight",
            0,
            len(selection),
            0,
            total_fields,
        )
    )
    checkpoint_state = _load_checkpoint_state(
        manifest,
        mode=mode,
        execution_sha256=execution_sha256,
        selection=selection,
        checkpoint_store=checkpoint_store,
        heartbeat=publisher.heartbeat,
        approval_authority=approval_authority,
    )
    if checkpoint_state.rows and not resume:
        raise _fail("exact_operation_resume_required")
    if resume and not checkpoint_state.rows:
        raise _fail("exact_operation_resume_checkpoint_missing")

    _validate_payloads(
        selection,
        payloads,
        heartbeat=publisher.heartbeat,
    )
    _preflight_target_states(
        selection,
        mode=mode,
        verifier=verifier,
        checkpoint_state=checkpoint_state,
        resume=resume,
        heartbeat=publisher.heartbeat,
    )
    publisher.publish(
        ExactOperationProgress(
            manifest.manifest_sha256,
            execution_sha256,
            mode,
            "preflight",
            len(checkpoint_state.verified_items),
            len(selection),
            checkpoint_state.completed_field_count,
            total_fields,
        )
    )

    written_fields = 0
    resumed_fields = checkpoint_state.completed_field_count
    for item, fields in selection:
        if item.ordinal in checkpoint_state.verified_items:
            for field in fields:
                if not hmac.compare_digest(
                    _read_hash(
                        verifier,
                        item,
                        field,
                        heartbeat=publisher.heartbeat,
                    ),
                    _expected_hash(field, mode=mode, destination=True),
                ):
                    raise _fail("exact_operation_target_state_drifted")
            continue
        if item.ordinal not in checkpoint_state.started_items:
            _append_checkpoint(
                checkpoint_state,
                manifest=manifest,
                execution_sha256=execution_sha256,
                mode=mode,
                item=item,
                stage="started",
                field_ref=None,
                observed_sha256=None,
                checkpoint_store=checkpoint_store,
                heartbeat=publisher.heartbeat,
                approval_authority=approval_authority,
            )
            publisher.publish(
                ExactOperationProgress(
                    manifest.manifest_sha256,
                    execution_sha256,
                    mode,
                    "item_started",
                    len(checkpoint_state.verified_items),
                    len(selection),
                    checkpoint_state.completed_field_count,
                    total_fields,
                    item.ordinal,
                )
            )
        for field in fields:
            destination_sha256 = _expected_hash(field, mode=mode, destination=True)
            source_sha256 = _expected_hash(field, mode=mode, destination=False)
            observed_sha256 = _read_hash(
                verifier,
                item,
                field,
                heartbeat=publisher.heartbeat,
            )
            if field.field_ref in checkpoint_state.completed_fields[item.ordinal]:
                if not hmac.compare_digest(observed_sha256, destination_sha256):
                    raise _fail("exact_operation_target_state_drifted")
                continue
            if hmac.compare_digest(observed_sha256, destination_sha256):
                # A prior process may have completed the write but crashed
                # before appending its field checkpoint.  Independent state is
                # sufficient to advance the exact same execution digest.
                resumed_fields += 1
            elif hmac.compare_digest(observed_sha256, source_sha256):
                payload_state = _payload_state(mode, destination=True)
                try:
                    value = payloads.field_value(
                        item_id=item.item_id,
                        field_ref=field.field_ref,
                        state=payload_state,
                        heartbeat=publisher.heartbeat,
                    )
                    writer.write_field(
                        target_kind=item.target_kind,
                        target_ref=item.target_ref,
                        field_ref=field.field_ref,
                        value=value,
                        heartbeat=publisher.heartbeat,
                    )
                except Exception:
                    raise _fail("exact_operation_write_failed") from None
                written_fields += 1
                if not hmac.compare_digest(
                    _read_hash(
                        verifier,
                        item,
                        field,
                        heartbeat=publisher.heartbeat,
                    ),
                    destination_sha256,
                ):
                    raise _fail("exact_operation_independent_verify_failed")
            else:
                raise _fail("exact_operation_target_state_drifted")
            _append_checkpoint(
                checkpoint_state,
                manifest=manifest,
                execution_sha256=execution_sha256,
                mode=mode,
                item=item,
                stage="field_verified",
                field_ref=field.field_ref,
                observed_sha256=destination_sha256,
                checkpoint_store=checkpoint_store,
                heartbeat=publisher.heartbeat,
                approval_authority=approval_authority,
            )
            publisher.publish(
                ExactOperationProgress(
                    manifest.manifest_sha256,
                    execution_sha256,
                    mode,
                    "field_verified",
                    len(checkpoint_state.verified_items),
                    len(selection),
                    checkpoint_state.completed_field_count,
                    total_fields,
                    item.ordinal,
                )
            )
        _append_checkpoint(
            checkpoint_state,
            manifest=manifest,
            execution_sha256=execution_sha256,
            mode=mode,
            item=item,
            stage="item_verified",
            field_ref=None,
            observed_sha256=_checkpoint_item_state_sha256(fields, mode=mode),
            checkpoint_store=checkpoint_store,
            heartbeat=publisher.heartbeat,
            approval_authority=approval_authority,
        )
        publisher.publish(
            ExactOperationProgress(
                manifest.manifest_sha256,
                execution_sha256,
                mode,
                "item_verified",
                len(checkpoint_state.verified_items),
                len(selection),
                checkpoint_state.completed_field_count,
                total_fields,
                item.ordinal,
            )
        )

    verification = verify_exact_operation(
        manifest,
        verifier=verifier,
        state="post" if mode == "apply" else "pre",
        selected_fields=(
            None
            if mode == "apply"
            else tuple(
                (item.item_id, field.field_ref)
                for item, fields in selection
                for field in fields
            )
        ),
        heartbeat=publisher.heartbeat,
    )
    if verification["all_match"] is not True:
        raise _fail("exact_operation_independent_verify_failed")
    field_receipts = [
        row["field_receipt_sha256"]
        for row in checkpoint_state.rows
        if row["stage"] == "field_verified"
    ]
    stable_result_basis = {
        "schema": RESULT_SCHEMA,
        "status": "completed",
        "mode": mode,
        "manifest_sha256": manifest.manifest_sha256,
        "execution_sha256": execution_sha256,
        "approval_binding_sha256": (
            approval_authority.binding_sha256
            if approval_authority is not None
            else None
        ),
        "item_count": len(selection),
        "field_count": total_fields,
        "checkpoint_count": len(checkpoint_state.rows),
        "field_receipt_count": len(field_receipts),
        "field_receipt_set_sha256": _digest_document(field_receipts),
        "independent_verification_sha256": verification["verification_sha256"],
        "private_values_echoed": False,
    }
    stable_result = {
        **stable_result_basis,
        "result_sha256": _digest_document(stable_result_basis),
    }
    try:
        final_receipt_sha256 = _digest(
            checkpoint_store.finalize(
                stable_result,
                heartbeat=publisher.heartbeat,
            ),
            code="exact_operation_result_receipt_failed",
        )
    except ExactOperationManifestError:
        raise
    except Exception:
        raise _fail("exact_operation_result_receipt_failed") from None
    publisher.publish(
        ExactOperationProgress(
            manifest.manifest_sha256,
            execution_sha256,
            mode,
            "completed",
            len(selection),
            len(selection),
            total_fields,
            total_fields,
        )
    )
    invocation_basis = {
        "schema": "wom-kit/exact-operation-invocation/v1",
        "result_sha256": stable_result["result_sha256"],
        "final_receipt_sha256": final_receipt_sha256,
        "written_field_count": written_fields,
        "resumed_field_count": resumed_fields,
        "progress_delivery_failure_count": publisher.failure_count,
    }
    return {
        **stable_result,
        "final_receipt_sha256": final_receipt_sha256,
        "written_field_count": written_fields,
        "resumed_field_count": resumed_fields,
        "progress_delivery_failure_count": publisher.failure_count,
        "invocation_sha256": _digest_document(invocation_basis),
    }


def apply_exact_operation(
    manifest: ExactOperationManifest,
    *,
    payloads: ExactOperationPayloadProvider,
    writer: ExactOperationTargetWriter,
    verifier: ExactOperationIndependentVerifier,
    checkpoint_store: ExactOperationCheckpointStore,
    approval_authority: ExactOperationApprovalAuthority | None = None,
    resume: bool = False,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
) -> dict[str, Any]:
    return _run_exact_operation(
        manifest,
        mode="apply",
        selected_fields=None,
        payloads=payloads,
        writer=writer,
        verifier=verifier,
        checkpoint_store=checkpoint_store,
        approval_authority=approval_authority,
        resume=resume,
        progress_hook=progress_hook,
    )


def revert_exact_operation_fields(
    manifest: ExactOperationManifest,
    *,
    selected_fields: Iterable[tuple[str, str]],
    payloads: ExactOperationPayloadProvider,
    writer: ExactOperationTargetWriter,
    verifier: ExactOperationIndependentVerifier,
    checkpoint_store: ExactOperationCheckpointStore,
    approval_authority: ExactOperationApprovalAuthority | None = None,
    resume: bool = False,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
) -> dict[str, Any]:
    return _run_exact_operation(
        manifest,
        mode="revert",
        selected_fields=selected_fields,
        payloads=payloads,
        writer=writer,
        verifier=verifier,
        checkpoint_store=checkpoint_store,
        approval_authority=approval_authority,
        resume=resume,
        progress_hook=progress_hook,
    )


__all__ = [
    "ABSENT_FIELD_SHA256",
    "APPROVAL_AUTHORITY_SCHEMA",
    "CHECKPOINT_SCHEMA",
    "EXACT_OPERATION_LOCAL_ROOT",
    "EXACT_OPERATION_RECEIPTS_ROOT",
    "EXACT_OPERATION_WRITER_LOCK",
    "FIELD_RECEIPT_SCHEMA",
    "FINAL_RECEIPT_SCHEMA",
    "FIRST_STATUS_DEADLINE_SECONDS",
    "HEARTBEAT_INTERVAL_SECONDS",
    "ExactFieldEffect",
    "ExactOperationApprovalAuthority",
    "ExactOperationCheckpointStore",
    "ExactOperationIndependentVerifier",
    "ExactOperationItem",
    "ExactOperationManifest",
    "ExactOperationManifestError",
    "ExactOperationPayloadProvider",
    "ExactOperationProgress",
    "ExactOperationTargetWriter",
    "ExactOperationWriterLock",
    "FileExactOperationCheckpointStore",
    "MANIFEST_SCHEMA",
    "RESULT_SCHEMA",
    "VERIFICATION_SCHEMA",
    "apply_exact_operation",
    "exact_operation_execution_sha256",
    "exact_operation_writer_lock",
    "hash_field_value",
    "revert_exact_operation_fields",
    "verify_exact_operation",
]
