"""Approval-gated, resumable recovery of reviewed Notion page originals.

This module deliberately contains no network client and no credential-store
implementation.  The caller supplies those capabilities only after a human has
approved the deterministic plan digest returned by :func:`plan_recovery`.

The public result dictionaries are intentionally aggregate-only.  Page ids,
provider payloads, credentials, titles, e-mail addresses, URLs, and pagination
cursors are confined to the private archive files or discarded in memory.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import secrets
import stat as stat_module
import struct
import threading
import time
from typing import Any, Callable, ContextManager, Iterable, Mapping, Protocol, Sequence
import uuid

import yaml


REQUEST_SCHEMA = "wom-kit/notion-page-recovery-request/v0.1"
PLAN_SCHEMA = "wom-kit/notion-page-recovery-plan/v0.1"
RESUME_SCHEMA = "wom-kit/notion-page-recovery-resume/v0.1"
PROJECTION_SCHEMA = "wom-kit/notion-page-recovery-projection/v0.1"
RECEIPT_SCHEMA = "wom-kit/notion-page-recovery-receipt/v0.1"
CREDENTIAL_CAPABILITY_REFERENCE_SCHEMA = (
    "wom-kit/credential-capability-reference/v0.1"
)
NOTION_API_VERSION = "2026-03-11"
MAX_REQUEST_ITEMS = 1000
MAX_UNKNOWN_BLOCK_IDS = 100
DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_MAX_RETRY_DELAY_SECONDS = 60.0
DEFAULT_PROVIDER_REQUESTS_PER_SECOND = 3.0
MAX_ARCHIVE_IDENTITY_BYTES = 256 * 1024

_ARCHIVE_IDENTITY_CHANGED = "notion_page_recovery_archive_identity_changed"

APPROVED_EXECUTION_CAPABILITIES = {
    "credential_reads_may_occur": True,
    "provider_get_requests_may_occur": True,
    "archive_writes_may_occur": True,
    "verified_replay_is_optimization_only": True,
}

_PACER_RELATIVE_ROOT = Path("profiles") / "local" / "notion-page-recovery"
_PACER_LOCK_NAME = ".provider-get-rate-v1.lock"
_PACER_STATE_NAME = ".provider-get-rate-v1.state"
_PACER_STATE = struct.Struct("!8sd")
_PACER_STATE_MAGIC = b"WOMPR1\x00\x00"

OUTCOMES = (
    "recovered",
    "deleted",
    "forbidden",
    "not_found_or_not_shared",
    "retryable_error",
    "partial",
)
_RETRYABLE_GET_STATUSES = {409, 429, 500, 502, 503, 504, 529, 599}

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+-]{0,127}$")
_CREDENTIAL_ID_RE = re.compile(r"^cred_[A-Za-z0-9_-]{16,96}$")
_CAPABILITY_ID_RE = re.compile(r"^cap_[0-9a-f]{32}$")
_SECRET_SHAPE_RE = re.compile(
    r"(?i)(?:github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{8,}"
    r"|(?:secret|ntn)_[A-Za-z0-9_-]{12,})"
)
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_HEX_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_THREAD_LOCKS_GUARD = threading.Lock()
_THREAD_LOCKS: dict[str, threading.RLock] = {}


class _DuplicateYamlKeyError(ValueError):
    pass


class _UniqueKeySafeLoader(yaml.SafeLoader):
    pass


def _construct_unique_yaml_mapping(
    loader: _UniqueKeySafeLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in result
        except TypeError:
            raise _DuplicateYamlKeyError("archive_identity_invalid") from None
        if duplicate:
            raise _DuplicateYamlKeyError("archive_identity_invalid")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_yaml_mapping,
)


class ManifestValidationError(ValueError):
    """A manifest failed strict validation without retaining unsafe values."""

    def __init__(self, codes: Iterable[str]) -> None:
        self.codes = tuple(sorted(set(str(code) for code in codes)))
        super().__init__("manifest_invalid")


class RecoveryStorageError(RuntimeError):
    """A sanitized storage failure."""

    def __init__(self, code: str = "recovery_storage_error") -> None:
        self.code = code if _is_safe_id(code) else "recovery_storage_error"
        super().__init__(self.code)


class RecoveryExecutionBoundaryError(RuntimeError):
    """A content-free live execution authority failure."""

    def __init__(self, code: str = "recovery_execution_boundary_failed") -> None:
        self.code = code if _is_safe_id(code) else "recovery_execution_boundary_failed"
        super().__init__(self.code)


@dataclass(frozen=True)
class ScopeBinding:
    credential_id: str
    workspace_fingerprint: str
    scope_receipt_sha256: str
    revision: str
    persisted: bool
    workspace_evidence_verified: bool


@dataclass(frozen=True)
class RecoveryGroup:
    group_id: str
    expected_count: int
    scope_binding: ScopeBinding


@dataclass(frozen=True)
class RecoveryItem:
    item_id: str
    group_id: str
    page_id: str


@dataclass(frozen=True)
class RecoveryRequest:
    batch_id: str
    archive_id: str
    expected_item_count: int
    groups: tuple[RecoveryGroup, ...]
    items: tuple[RecoveryItem, ...]

    def canonical_document(self) -> dict[str, Any]:
        return {
            "schema": REQUEST_SCHEMA,
            "batch_id": self.batch_id,
            "archive_id": self.archive_id,
            "expected_item_count": self.expected_item_count,
            "groups": [
                {
                    "group_id": group.group_id,
                    "expected_count": group.expected_count,
                    "scope_binding": {
                        "credential_id": group.scope_binding.credential_id,
                        "workspace_fingerprint": group.scope_binding.workspace_fingerprint,
                        "scope_receipt_sha256": group.scope_binding.scope_receipt_sha256,
                        "revision": group.scope_binding.revision,
                        "persisted": group.scope_binding.persisted,
                        "workspace_evidence_verified": group.scope_binding.workspace_evidence_verified,
                    },
                }
                for group in self.groups
            ],
            "items": [
                {
                    "item_id": item.item_id,
                    "group_id": item.group_id,
                    "page_id": item.page_id,
                }
                for item in self.items
            ],
        }


@dataclass(frozen=True)
class RecoveryPlan:
    request_sha256: str
    plan_sha256: str
    max_items: int
    offset: int
    selected_items: tuple[RecoveryItem, ...]


@dataclass(frozen=True)
class ProviderResponse:
    """A provider-neutral HTTP-shaped response used by injected adapters."""

    status: int
    payload: Mapping[str, Any] | None = None
    headers: Mapping[str, str] | None = None


class NotionPageProvider(Protocol):
    """Minimal adapter contract; implementations may call only GET endpoints."""

    def retrieve_page(
        self,
        page_id: str,
        credential: object,
        *,
        api_version: str,
    ) -> ProviderResponse: ...

    def retrieve_page_as_markdown(
        self,
        page_or_block_id: str,
        credential: object,
        *,
        api_version: str,
    ) -> ProviderResponse: ...


class CredentialBroker(Protocol):
    def resolve(self, scope_binding: ScopeBinding) -> object: ...


class ProviderRequestPacer(Protocol):
    """Run-shared gate invoked immediately before each provider GET attempt."""

    def before_request(self) -> None: ...


class FixedIntervalRequestPacer:
    """Thread-safe steady-state pacer capped at Notion's documented average."""

    def __init__(
        self,
        *,
        requests_per_second: float = DEFAULT_PROVIDER_REQUESTS_PER_SECOND,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if (
            not isinstance(requests_per_second, (int, float))
            or isinstance(requests_per_second, bool)
            or not math.isfinite(float(requests_per_second))
            or float(requests_per_second) <= 0
            or float(requests_per_second) > DEFAULT_PROVIDER_REQUESTS_PER_SECOND
        ):
            raise ValueError("provider_request_rate_invalid")
        self._interval_seconds = 1.0 / float(requests_per_second)
        self._monotonic = monotonic
        self._sleep = sleep
        self._next_allowed: float | None = None
        self._lock = threading.Lock()

    def before_request(self) -> None:
        with self._lock:
            try:
                now = float(self._monotonic())
            except Exception:
                raise RuntimeError("provider_pacer_failed") from None
            if not math.isfinite(now):
                raise RuntimeError("provider_pacer_failed")
            if self._next_allowed is None:
                self._next_allowed = now + self._interval_seconds
                return
            delay = max(0.0, self._next_allowed - now)
            if delay:
                try:
                    self._sleep(delay)
                except Exception:
                    raise RuntimeError("provider_pacer_failed") from None
                try:
                    after_sleep = float(self._monotonic())
                except Exception:
                    raise RuntimeError("provider_pacer_failed") from None
                if not math.isfinite(after_sleep):
                    raise RuntimeError("provider_pacer_failed")
            else:
                after_sleep = now
            self._next_allowed = max(self._next_allowed, after_sleep) + self._interval_seconds

    def __repr__(self) -> str:
        return "<FixedIntervalRequestPacer rate_limited=True state=redacted>"


class ArchiveInterprocessRequestPacer:
    """Lazy archive-wide pacing shared by threads and local processes.

    The private lock and state are created only by :meth:`before_request`, so
    dry-runs, approval failures, credential failures, and verified replays do
    not touch pacing state.  The state contains only an opaque monotonic-clock
    grant and is never included in public results or receipts.
    """

    def __init__(
        self,
        archive_root: Path | str,
        *,
        requests_per_second: float = DEFAULT_PROVIDER_REQUESTS_PER_SECOND,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if (
            not isinstance(requests_per_second, (int, float))
            or isinstance(requests_per_second, bool)
            or not math.isfinite(float(requests_per_second))
            or float(requests_per_second) <= 0
            or float(requests_per_second) > DEFAULT_PROVIDER_REQUESTS_PER_SECOND
        ):
            raise ValueError("provider_request_rate_invalid")
        self._archive_root = Path(archive_root)
        self._interval_seconds = 1.0 / float(requests_per_second)
        self._monotonic = monotonic
        self._sleep = sleep

    def before_request(self) -> None:
        try:
            private_root, lock_path, state_path = _prepare_private_pacer_paths(
                self._archive_root
            )
            with _exclusive_private_pacer_lock(lock_path):
                now = self._read_clock()
                previous = _read_private_pacer_state(state_path)
                if previous is not None and previous <= now:
                    target = previous + self._interval_seconds
                    while now < target:
                        delay = target - now
                        self._sleep(delay)
                        after_sleep = self._read_clock()
                        if after_sleep <= now:
                            # A clock that does not advance after a positive
                            # sleep cannot prove that the provider rate held.
                            raise RuntimeError("provider_pacer_failed")
                        now = after_sleep
                # A valid persisted monotonic value greater than the current
                # value denotes an earlier host-boot epoch.  Because the lock
                # is archive-wide and no process survives a reboot, starting a
                # new epoch here does not overlap an old live request.
                _write_private_pacer_state(private_root, state_path, now)
        except Exception:
            # Neither local paths nor clock/state details cross this boundary.
            raise RuntimeError("provider_pacer_failed") from None

    def _read_clock(self) -> float:
        try:
            value = float(self._monotonic())
        except Exception:
            raise RuntimeError("provider_pacer_failed") from None
        if not math.isfinite(value) or value < 0:
            raise RuntimeError("provider_pacer_failed")
        return value

    def __repr__(self) -> str:
        return "<ArchiveInterprocessRequestPacer rate_limited=True state=redacted>"


class DurableWriter(Protocol):
    def create_if_absent(self, path: Path, payload: bytes) -> bool: ...

    def replace(self, path: Path, payload: bytes) -> None: ...

    def append_fsync(self, path: Path, payload: bytes) -> None: ...


@dataclass(frozen=True)
class StoredFragment:
    object_id: str
    sha256: str
    byte_size: int


@dataclass(frozen=True)
class StoredRecovery:
    fragments: tuple[StoredFragment, ...]

    @property
    def primary(self) -> StoredFragment:
        return self.fragments[0]


@dataclass
class _RunStats:
    provider_calls: int = 0
    paced_request_count: int = 0
    credential_resolution_attempts: int = 0
    credential_reads: int = 0
    retry_count: int = 0
    sleep_seconds: float = 0.0
    objects_created: int = 0
    manifest_rows_created: int = 0
    projection_rows_created: int = 0
    resume_rows_created: int = 0


@dataclass(frozen=True)
class _RetryResult:
    response: ProviderResponse
    attempts: int


class _DefaultDurableWriter:
    """Durable filesystem primitives with create-if-absent object semantics."""

    def __init__(
        self,
        archive_root: Path,
        *,
        before_commit: Callable[[], None] | None = None,
    ) -> None:
        self.archive_root = archive_root
        self.before_commit = before_commit or (lambda: None)

    def create_if_absent(self, path: Path, payload: bytes) -> bool:
        _ensure_archive_directory_chain(self.archive_root, path.parent, create=True)
        _validate_archive_destination(self.archive_root, path, allow_missing=True)
        temp = path.parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
        try:
            with _open_archive_exclusive_temp(self.archive_root, temp) as handle:
                _write_all(handle, payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                self.before_commit()
                os.link(temp, path)
                temp.unlink()
                _validate_archive_destination(self.archive_root, path, allow_missing=False)
                _fsync_directory(path.parent)
                if not _file_matches_exact_payload(
                    path,
                    payload,
                    archive_root=self.archive_root,
                ):
                    raise RecoveryStorageError("durable_write_verification_failed")
                return True
            except FileExistsError:
                _validate_archive_destination(self.archive_root, path, allow_missing=False)
                return False
            except OSError as exc:
                # Hard-link publication is required: replacing an existing
                # content-addressed object would violate archive immutability.
                raise RecoveryStorageError("atomic_create_unavailable") from exc
        finally:
            try:
                temp.unlink()
            except FileNotFoundError:
                pass

    def replace(self, path: Path, payload: bytes) -> None:
        _ensure_archive_directory_chain(self.archive_root, path.parent, create=True)
        _validate_archive_destination(self.archive_root, path, allow_missing=True)
        temp = path.parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
        try:
            with _open_archive_exclusive_temp(self.archive_root, temp) as handle:
                _write_all(handle, payload)
                handle.flush()
                os.fsync(handle.fileno())
            _validate_archive_destination(self.archive_root, path, allow_missing=True)
            self.before_commit()
            os.replace(temp, path)
            _validate_archive_destination(self.archive_root, path, allow_missing=False)
            _fsync_directory(path.parent)
            if not _file_matches_exact_payload(
                path,
                payload,
                archive_root=self.archive_root,
            ):
                raise RecoveryStorageError("durable_write_verification_failed")
        finally:
            try:
                temp.unlink()
            except FileNotFoundError:
                pass

    def append_fsync(self, path: Path, payload: bytes) -> None:
        _ensure_archive_directory_chain(self.archive_root, path.parent, create=True)
        with _open_archive_append(self.archive_root, path) as handle:
            offset = os.fstat(handle.fileno()).st_size
            _write_all(handle, payload, before_write=self.before_commit)
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(path.parent)
        if not _file_matches_payload_at_offset(
            path,
            offset,
            payload,
            archive_root=self.archive_root,
        ):
            raise RecoveryStorageError("durable_write_verification_failed")


class _FilesystemRecoveryStorage:
    """Private, append-only recovery state beneath a selected archive root."""

    def __init__(
        self,
        archive_root: Path | str,
        *,
        writer: DurableWriter | None = None,
        failpoint: Callable[[str], None] | None = None,
    ) -> None:
        try:
            self.root = Path(os.path.abspath(os.fspath(archive_root)))
        except (TypeError, ValueError, OSError):
            raise RecoveryStorageError("archive_root_invalid") from None
        self._archive_identity_lock = threading.RLock()
        self._expected_archive_id: str | None = None
        self.writer = writer or _DefaultDurableWriter(
            self.root,
            before_commit=self._assert_bound_archive_identity,
        )
        self.failpoint = failpoint or (lambda _phase: None)
        self.objects_root = self.root / "objects" / "sha256"
        self.object_manifest_path = self.root / "objects" / "manifests" / "files.jsonl"
        self.private_root = self.root / "receipts" / "notion-page-recovery"
        self.projection_root = self.root / "receipts" / "import"

    @contextmanager
    def plan_lock(
        self,
        plan_sha256: str,
        *,
        expected_archive_id: str,
    ) -> Iterable[None]:
        digest = _digest_part(plan_sha256)
        self._bind_archive_identity(expected_archive_id)
        self._validate_execution_boundary()
        with _exclusive_file_lock(
            self.private_root / f"{digest}.lock", archive_root=self.root
        ):
            self._assert_bound_archive_identity()
            yield

    def _bind_archive_identity(self, expected_archive_id: str) -> None:
        if not _is_safe_id(expected_archive_id):
            raise RecoveryStorageError(_ARCHIVE_IDENTITY_CHANGED)
        with self._archive_identity_lock:
            bound = self._expected_archive_id
            if bound is not None and not secrets.compare_digest(
                bound,
                expected_archive_id,
            ):
                raise RecoveryStorageError(_ARCHIVE_IDENTITY_CHANGED)
            current = _read_recovery_archive_id(self.root)
            if not secrets.compare_digest(current, expected_archive_id):
                raise RecoveryStorageError(_ARCHIVE_IDENTITY_CHANGED)
            self._expected_archive_id = expected_archive_id

    def _assert_bound_archive_identity(self) -> None:
        with self._archive_identity_lock:
            expected = self._expected_archive_id
            if expected is None:
                return
            current = _read_recovery_archive_id(self.root)
            if not secrets.compare_digest(current, expected):
                raise RecoveryStorageError(_ARCHIVE_IDENTITY_CHANGED)

    def _validate_execution_boundary(self) -> None:
        root_exists = self.validate_plan_boundary()
        if not root_exists:
            raise RecoveryStorageError("archive_root_missing")
        self._assert_bound_archive_identity()
        _ensure_archive_directory_chain(self.root, self.private_root, create=True)

    def validate_plan_boundary(self) -> bool:
        """Read-only validation of every fixed recovery filesystem surface."""

        if not _ensure_archive_directory_chain(self.root, self.root, create=False):
            return False
        # These fixed surfaces are known before any credential resolution or
        # provider request. Existing link/reparse hops therefore fail closed at
        # the approval boundary; missing safe directories remain lazy.
        for directory in (
            self.root / "objects",
            self.objects_root,
            self.root / "objects" / "manifests",
            self.root / "receipts",
            self.private_root,
            self.projection_root,
        ):
            _ensure_archive_directory_chain(self.root, directory, create=False)
        return True

    def preview_verified(
        self,
        request: RecoveryRequest,
        plan: RecoveryPlan,
        item: RecoveryItem,
        scope_revision: str,
    ) -> StoredRecovery | None:
        """Read-only verification used by dry-run.  It never repairs files."""

        checkpoint = self._latest_object_checkpoint(plan.plan_sha256, item)
        if checkpoint is None:
            return None
        stored = self._stored_from_checkpoint(checkpoint)
        if stored is None or not self._objects_verify(stored):
            return None
        if not self._manifest_verifies(
            request, plan, item, scope_revision, stored
        ):
            return None
        if not self._projection_verifies(
            request, plan, item, scope_revision, stored
        ):
            return None
        terminal = self._latest_terminal_outcome(plan.plan_sha256, item)
        return stored if terminal == "recovered" else None

    def repair_verified(
        self,
        request: RecoveryRequest,
        plan: RecoveryPlan,
        item: RecoveryItem,
        scope_revision: str,
        completed_at: str,
        stats: _RunStats,
    ) -> StoredRecovery | None:
        """Repair a crash between object, manifest, projection, and terminal rows."""

        self._assert_bound_archive_identity()
        checkpoint = self._latest_object_checkpoint(plan.plan_sha256, item)
        if checkpoint is None:
            return None
        stored = self._stored_from_checkpoint(checkpoint)
        if stored is None or not self._objects_verify(stored):
            return None
        self._ensure_manifest_rows(
            request,
            plan,
            item,
            scope_revision,
            stored,
            completed_at,
            stats,
        )
        self._ensure_projection_row(
            request,
            plan,
            item,
            scope_revision,
            stored,
            completed_at,
            stats,
        )
        if self._latest_terminal_outcome(plan.plan_sha256, item) != "recovered":
            self._append_resume(
                plan.plan_sha256,
                _resume_terminal_row(request, plan, item, "recovered", completed_at, stored),
                stats,
            )
        return stored

    def commit_recovered(
        self,
        request: RecoveryRequest,
        plan: RecoveryPlan,
        item: RecoveryItem,
        scope_revision: str,
        fragments: Sequence[bytes],
        completed_at: str,
        stats: _RunStats,
    ) -> StoredRecovery:
        self._assert_bound_archive_identity()
        if not fragments:
            raise RecoveryStorageError("empty_recovery_payload")
        stored_fragments: list[StoredFragment] = []
        for raw in fragments:
            digest = hashlib.sha256(raw).hexdigest()
            object_id = f"sha256:{digest}"
            destination = self.objects_root / digest[:2] / digest
            self._assert_bound_archive_identity()
            created = self.writer.create_if_absent(destination, raw)
            if created:
                stats.objects_created += 1
            elif not _verify_file(
                destination, digest, len(raw), archive_root=self.root
            ):
                raise RecoveryStorageError("content_address_collision")
            stored_fragments.append(
                StoredFragment(object_id=object_id, sha256=digest, byte_size=len(raw))
            )
        stored = StoredRecovery(tuple(stored_fragments))
        self._append_resume(
            plan.plan_sha256,
            _resume_checkpoint_row(request, plan, item, completed_at, stored),
            stats,
        )
        self.failpoint("after_objects_checkpoint")
        self._ensure_manifest_rows(
            request,
            plan,
            item,
            scope_revision,
            stored,
            completed_at,
            stats,
        )
        self.failpoint("after_manifest")
        self._ensure_projection_row(
            request,
            plan,
            item,
            scope_revision,
            stored,
            completed_at,
            stats,
        )
        self.failpoint("after_projection")
        self._append_resume(
            plan.plan_sha256,
            _resume_terminal_row(request, plan, item, "recovered", completed_at, stored),
            stats,
        )
        self.failpoint("after_terminal_resume")
        return stored

    def record_outcome(
        self,
        request: RecoveryRequest,
        plan: RecoveryPlan,
        item: RecoveryItem,
        outcome: str,
        completed_at: str,
        stats: _RunStats,
    ) -> None:
        self._assert_bound_archive_identity()
        if outcome not in OUTCOMES or outcome == "recovered":
            raise RecoveryStorageError("invalid_outcome")
        self._append_resume(
            plan.plan_sha256,
            _resume_terminal_row(request, plan, item, outcome, completed_at, None),
            stats,
        )

    def write_receipt(self, plan_sha256: str, receipt: Mapping[str, Any]) -> bool:
        digest = _digest_part(plan_sha256)
        payload = _canonical_json_bytes(dict(receipt)) + b"\n"
        suffix = hashlib.sha256(payload).hexdigest()[:16]
        path = self.private_root / f"{digest}.{suffix}.receipt.json"
        self._assert_bound_archive_identity()
        created = self.writer.create_if_absent(path, payload)
        if created:
            return True
        try:
            exact_existing_receipt = _file_matches_exact_payload(
                path,
                payload,
                archive_root=self.root,
            )
        except Exception:
            raise RecoveryStorageError("recovery_authority_conflict") from None
        if not exact_existing_receipt:
            raise RecoveryStorageError("recovery_authority_conflict")
        return False

    def _resume_path(self, plan_sha256: str) -> Path:
        return self.private_root / f"{_digest_part(plan_sha256)}.resume.jsonl"

    def _projection_path(self, request_sha256: str) -> Path:
        return self.projection_root / f"notion-page-recovery-{_digest_part(request_sha256)}.jsonl"

    def _append_resume(
        self,
        plan_sha256: str,
        row: Mapping[str, Any],
        stats: _RunStats,
    ) -> None:
        self._assert_bound_archive_identity()
        path = self._resume_path(plan_sha256)
        with _exclusive_file_lock(
            path.with_suffix(path.suffix + ".lock"), archive_root=self.root
        ):
            self._repair_torn_jsonl(path)
            payload = _canonical_json_bytes(dict(row)) + b"\n"
            self._assert_bound_archive_identity()
            self.writer.append_fsync(path, payload)
        stats.resume_rows_created += 1

    def _append_jsonl_unique(
        self,
        path: Path,
        row: Mapping[str, Any],
        predicate: Callable[[Mapping[str, Any]], bool],
        authority_projection: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    ) -> bool:
        self._assert_bound_archive_identity()
        lock_context: ContextManager[None] = (
            _exclusive_object_manifest_lock(self.root)
            if path == self.object_manifest_path
            else _exclusive_file_lock(
                path.with_suffix(path.suffix + ".lock"),
                archive_root=self.root,
            )
        )
        with lock_context:
            self._assert_bound_archive_identity()
            self._repair_torn_jsonl(path)
            rows, _ = _read_jsonl(path, archive_root=self.root)
            authority_state = _authority_row_state(
                rows,
                row,
                predicate=predicate,
                authority_projection=authority_projection,
            )
            if authority_state == "equal":
                return False
            payload = _canonical_json_bytes(dict(row)) + b"\n"
            self._assert_bound_archive_identity()
            self.writer.append_fsync(path, payload)
            return True

    def _repair_torn_jsonl(self, path: Path) -> None:
        rows, torn = _read_jsonl(path, archive_root=self.root)
        if torn:
            repaired = b"".join(_canonical_json_bytes(dict(row)) + b"\n" for row in rows)
            self._assert_bound_archive_identity()
            self.writer.replace(path, repaired)

    def _resume_rows(self, plan_sha256: str) -> list[Mapping[str, Any]]:
        rows, _ = _read_jsonl(
            self._resume_path(plan_sha256), archive_root=self.root
        )
        return rows

    def _latest_object_checkpoint(
        self,
        plan_sha256: str,
        item: RecoveryItem,
    ) -> Mapping[str, Any] | None:
        for row in reversed(self._resume_rows(plan_sha256)):
            if (
                row.get("schema") == RESUME_SCHEMA
                and row.get("item_id") == item.item_id
                and row.get("page_id") == item.page_id
                and isinstance(row.get("fragments"), list)
            ):
                return row
        return None

    def _latest_terminal_outcome(self, plan_sha256: str, item: RecoveryItem) -> str | None:
        for row in reversed(self._resume_rows(plan_sha256)):
            if (
                row.get("schema") == RESUME_SCHEMA
                and row.get("item_id") == item.item_id
                and row.get("page_id") == item.page_id
                and row.get("phase") == "terminal"
                and row.get("outcome") in OUTCOMES
            ):
                return str(row["outcome"])
        return None

    def _stored_from_checkpoint(self, row: Mapping[str, Any]) -> StoredRecovery | None:
        raw_fragments = row.get("fragments")
        if not isinstance(raw_fragments, list) or not raw_fragments:
            return None
        fragments: list[StoredFragment] = []
        for raw in raw_fragments:
            if not isinstance(raw, Mapping):
                return None
            object_id = raw.get("object_id")
            sha256 = raw.get("sha256")
            byte_size = raw.get("byte_size")
            if (
                not isinstance(object_id, str)
                or not _SHA256_RE.fullmatch(object_id)
                or not isinstance(sha256, str)
                or not _HEX_SHA256_RE.fullmatch(sha256)
                or object_id != f"sha256:{sha256}"
                or not isinstance(byte_size, int)
                or isinstance(byte_size, bool)
                or byte_size < 0
            ):
                return None
            fragments.append(StoredFragment(object_id, sha256, byte_size))
        return StoredRecovery(tuple(fragments))

    def _objects_verify(self, stored: StoredRecovery) -> bool:
        return all(
            _verify_file(
                self.objects_root / fragment.sha256[:2] / fragment.sha256,
                fragment.sha256,
                fragment.byte_size,
                archive_root=self.root,
            )
            for fragment in stored.fragments
        )

    def _manifest_verifies(
        self,
        request: RecoveryRequest,
        plan: RecoveryPlan,
        item: RecoveryItem,
        scope_revision: str,
        stored: StoredRecovery,
    ) -> bool:
        rows, _ = _read_jsonl(self.object_manifest_path, archive_root=self.root)
        for fragment in stored.fragments:
            expected = self._manifest_row(
                request,
                fragment,
                completed_at="",
            )
            authority_state = _authority_row_state(
                rows,
                expected,
                predicate=lambda existing, object_id=fragment.object_id: (
                    existing.get("object_id") == object_id
                ),
                authority_projection=_manifest_authority_projection,
            )
            if authority_state == "missing":
                return False
        return True

    def _projection_verifies(
        self,
        request: RecoveryRequest,
        plan: RecoveryPlan,
        item: RecoveryItem,
        scope_revision: str,
        stored: StoredRecovery,
    ) -> bool:
        rows, _ = _read_jsonl(
            self._projection_path(plan.request_sha256), archive_root=self.root
        )
        expected = self._projection_row(
            request, plan, item, scope_revision, stored, completed_at=""
        )
        return _authority_row_state(
            rows,
            expected,
            predicate=lambda existing: (
                existing.get("request_sha256") == plan.request_sha256
                and existing.get("page_id") == item.page_id
            ),
            authority_projection=_projection_authority_projection,
        ) == "equal"

    @staticmethod
    def _manifest_row(
        request: RecoveryRequest,
        fragment: StoredFragment,
        completed_at: str,
    ) -> dict[str, Any]:
        return {
            "object_id": fragment.object_id,
            "sha256": fragment.sha256,
            "logical_key": f"objects/sha256/{fragment.sha256[:2]}/{fragment.sha256}",
            "mime": "text/markdown",
            "size_bytes": fragment.byte_size,
            "locations": [
                {
                    "provider": "local",
                    "path": f"objects/sha256/{fragment.sha256[:2]}/{fragment.sha256}",
                    "availability": "available",
                }
            ],
            "provenance": {
                "created_in": f"archive:{request.archive_id}",
                "source": "notion_page_recovery",
                "captured_at": completed_at,
            },
        }

    @staticmethod
    def _projection_row(
        request: RecoveryRequest,
        plan: RecoveryPlan,
        item: RecoveryItem,
        scope_revision: str,
        stored: StoredRecovery,
        completed_at: str,
    ) -> dict[str, Any]:
        return {
            "schema": PROJECTION_SCHEMA,
            "request_sha256": plan.request_sha256,
            "plan_sha256": plan.plan_sha256,
            "batch_id": request.batch_id,
            "item_id": item.item_id,
            "group_id": item.group_id,
            "page_id": item.page_id,
            "scope_revision": scope_revision,
            "object_id": stored.primary.object_id,
            "sha256": stored.primary.sha256,
            "byte_size": stored.primary.byte_size,
            "fragment_object_ids": [
                fragment.object_id for fragment in stored.fragments
            ],
            "fragment_count": len(stored.fragments),
            "outcome": "recovered",
            "completed_at": completed_at,
        }

    def _ensure_manifest_rows(
        self,
        request: RecoveryRequest,
        plan: RecoveryPlan,
        item: RecoveryItem,
        scope_revision: str,
        stored: StoredRecovery,
        completed_at: str,
        stats: _RunStats,
    ) -> None:
        for fragment in stored.fragments:
            row = self._manifest_row(
                request,
                fragment,
                completed_at,
            )
            created = self._append_jsonl_unique(
                self.object_manifest_path,
                row,
                lambda existing, object_id=fragment.object_id: (
                    existing.get("object_id") == object_id
                ),
                _manifest_authority_projection,
            )
            if created:
                stats.manifest_rows_created += 1

    def _ensure_projection_row(
        self,
        request: RecoveryRequest,
        plan: RecoveryPlan,
        item: RecoveryItem,
        scope_revision: str,
        stored: StoredRecovery,
        completed_at: str,
        stats: _RunStats,
    ) -> None:
        row = self._projection_row(
            request, plan, item, scope_revision, stored, completed_at
        )
        created = self._append_jsonl_unique(
            self._projection_path(plan.request_sha256),
            row,
            lambda existing: (
                existing.get("request_sha256") == plan.request_sha256
                and existing.get("page_id") == item.page_id
            ),
            _projection_authority_projection,
        )
        if created:
            stats.projection_rows_created += 1


def parse_manifest(document: Mapping[str, Any]) -> RecoveryRequest:
    """Parse the allowlisted request format and reject every unknown field."""

    errors: list[str] = []
    if not isinstance(document, Mapping):
        raise ManifestValidationError(["manifest_must_be_object"])
    _check_exact_keys(
        document,
        {"schema", "batch_id", "archive_id", "expected_item_count", "groups", "items"},
        "manifest",
        errors,
    )
    if document.get("schema") != REQUEST_SCHEMA:
        errors.append("manifest_schema_invalid")
    batch_id = _safe_id_value(document.get("batch_id"), "batch_id", errors)
    archive_id = _safe_id_value(document.get("archive_id"), "archive_id", errors)
    expected_item_count = _bounded_int(
        document.get("expected_item_count"),
        "expected_item_count",
        errors,
        minimum=1,
        maximum=MAX_REQUEST_ITEMS,
    )

    groups_raw = document.get("groups")
    if not isinstance(groups_raw, list) or not groups_raw:
        errors.append("groups_invalid")
        groups_raw = []
    items_raw = document.get("items")
    if not isinstance(items_raw, list) or not items_raw:
        errors.append("items_invalid")
        items_raw = []

    groups: list[RecoveryGroup] = []
    group_ids: set[str] = set()
    for raw in groups_raw:
        if not isinstance(raw, Mapping):
            errors.append("group_must_be_object")
            continue
        _check_exact_keys(raw, {"group_id", "expected_count", "scope_binding"}, "group", errors)
        group_id = _safe_id_value(raw.get("group_id"), "group_id", errors)
        expected_count = _bounded_int(
            raw.get("expected_count"),
            "group_expected_count",
            errors,
            minimum=1,
            maximum=MAX_REQUEST_ITEMS,
        )
        scope_raw = raw.get("scope_binding")
        if not isinstance(scope_raw, Mapping):
            errors.append("scope_binding_invalid")
            continue
        _check_exact_keys(
            scope_raw,
            {
                "credential_id",
                "workspace_fingerprint",
                "scope_receipt_sha256",
                "revision",
                "persisted",
                "workspace_evidence_verified",
            },
            "scope_binding",
            errors,
        )
        credential_id = _safe_id_value(scope_raw.get("credential_id"), "credential_id", errors)
        if credential_id is not None and _CREDENTIAL_ID_RE.fullmatch(credential_id) is None:
            errors.append("credential_id_invalid")
        workspace_fingerprint = _sha256_value(
            scope_raw.get("workspace_fingerprint"), "workspace_fingerprint", errors
        )
        scope_receipt_sha256 = _sha256_value(
            scope_raw.get("scope_receipt_sha256"), "scope_receipt_sha256", errors
        )
        revision = _safe_id_value(scope_raw.get("revision"), "scope_revision", errors)
        persisted = scope_raw.get("persisted")
        if persisted is not True:
            errors.append("scope_receipt_not_persisted")
        workspace_evidence_verified = scope_raw.get("workspace_evidence_verified")
        if workspace_evidence_verified is not True:
            errors.append("workspace_evidence_not_verified")
        if group_id in group_ids:
            errors.append("duplicate_group_id")
        group_ids.add(group_id)
        groups.append(
            RecoveryGroup(
                group_id=group_id,
                expected_count=expected_count,
                scope_binding=ScopeBinding(
                    credential_id=credential_id,
                    workspace_fingerprint=workspace_fingerprint,
                    scope_receipt_sha256=scope_receipt_sha256,
                    revision=revision,
                    persisted=persisted is True,
                    workspace_evidence_verified=workspace_evidence_verified is True,
                ),
            )
        )

    items: list[RecoveryItem] = []
    item_ids: set[str] = set()
    page_ids: set[str] = set()
    actual_group_counts: dict[str, int] = {}
    for raw in items_raw:
        if not isinstance(raw, Mapping):
            errors.append("item_must_be_object")
            continue
        _check_exact_keys(raw, {"item_id", "group_id", "page_id"}, "item", errors)
        item_id = _safe_id_value(raw.get("item_id"), "item_id", errors)
        group_id = _safe_id_value(raw.get("group_id"), "item_group_id", errors)
        page_id = _uuid_value(raw.get("page_id"), errors)
        if item_id in item_ids:
            errors.append("duplicate_item_id")
        if page_id in page_ids:
            errors.append("duplicate_page_id")
        if group_id not in group_ids:
            errors.append("item_group_unknown")
        item_ids.add(item_id)
        page_ids.add(page_id)
        actual_group_counts[group_id] = actual_group_counts.get(group_id, 0) + 1
        items.append(RecoveryItem(item_id=item_id, group_id=group_id, page_id=page_id))

    if len(groups) > MAX_REQUEST_ITEMS:
        errors.append("group_count_exceeds_limit")
    if len(items) > MAX_REQUEST_ITEMS:
        errors.append("item_count_exceeds_limit")
    if sum(group.expected_count for group in groups) != expected_item_count:
        errors.append("group_expected_count_sum_mismatch")
    if len(items) != expected_item_count:
        errors.append("item_count_mismatch")
    for group in groups:
        if actual_group_counts.get(group.group_id, 0) != group.expected_count:
            errors.append("group_actual_count_mismatch")

    if errors:
        raise ManifestValidationError(errors)
    return RecoveryRequest(
        batch_id=batch_id,
        archive_id=archive_id,
        expected_item_count=expected_item_count,
        groups=tuple(groups),
        items=tuple(items),
    )


def build_plan(
    request: RecoveryRequest,
    *,
    max_items: int,
    offset: int = 0,
) -> RecoveryPlan:
    if (
        not isinstance(max_items, int)
        or isinstance(max_items, bool)
        or max_items < 1
        or max_items > MAX_REQUEST_ITEMS
    ):
        raise ManifestValidationError(["max_items_invalid"])
    if (
        not isinstance(offset, int)
        or isinstance(offset, bool)
        or offset < 0
        or offset >= request.expected_item_count
    ):
        raise ManifestValidationError(["offset_invalid"])
    selected = request.items[offset : offset + max_items]
    request_sha256 = _sha256_id(_canonical_json_bytes(request.canonical_document()))
    private_plan = {
        "schema": PLAN_SCHEMA,
        "request_sha256": request_sha256,
        "max_items": max_items,
        "offset": offset,
        "approved_execution_capabilities": dict(
            APPROVED_EXECUTION_CAPABILITIES
        ),
        "selected": [
            {"item_id": item.item_id, "group_id": item.group_id, "page_id": item.page_id}
            for item in selected
        ],
    }
    return RecoveryPlan(
        request_sha256=request_sha256,
        plan_sha256=_sha256_id(_canonical_json_bytes(private_plan)),
        max_items=max_items,
        offset=offset,
        selected_items=tuple(selected),
    )


def plan_recovery(
    archive_root: Path | str,
    manifest: Mapping[str, Any],
    *,
    max_items: int,
    offset: int = 0,
    storage: _FilesystemRecoveryStorage | None = None,
) -> dict[str, Any]:
    """Return an aggregate-only plan without provider, secret, or write calls."""

    try:
        request = parse_manifest(manifest)
        plan = build_plan(request, max_items=max_items, offset=offset)
    except ManifestValidationError as exc:
        return _invalid_plan_result(exc.codes)
    state = storage or _FilesystemRecoveryStorage(archive_root)
    try:
        state.validate_plan_boundary()
        group_by_id = {group.group_id: group for group in request.groups}
        replay_verified = sum(
            1
            for item in plan.selected_items
            if state.preview_verified(
                request,
                plan,
                item,
                group_by_id[item.group_id].scope_binding.revision,
            )
            is not None
        )
    except RecoveryStorageError as exc:
        selected_count = len(plan.selected_items)
        return {
            "ok": False,
            "dry_run": True,
            "lifecycle_action": "notion_page_recovery_plan",
            "reason_code": "notion_page_recovery_plan_blocked",
            "request_sha256": plan.request_sha256,
            "plan_sha256": plan.plan_sha256,
            "approved_execution_capabilities": dict(
                APPROVED_EXECUTION_CAPABILITIES
            ),
            "counts": {
                "group_count": len(request.groups),
                "input_item_count": request.expected_item_count,
                "selected_item_count": selected_count,
                "unselected_item_count": request.expected_item_count - selected_count,
                "recovered_verified_count": 0,
                "provider_pending_count": selected_count,
            },
            "provider_calls": 0,
            "credential_reads": 0,
            "writes": 0,
            "privacy_guards": _privacy_guards(),
            "blockers": [exc.code],
        }
    selected_count = len(plan.selected_items)
    return {
        "ok": True,
        "dry_run": True,
        "lifecycle_action": "notion_page_recovery_plan",
        "reason_code": "notion_page_recovery_plan_ready",
        "request_sha256": plan.request_sha256,
        "plan_sha256": plan.plan_sha256,
        "approved_execution_capabilities": dict(
            APPROVED_EXECUTION_CAPABILITIES
        ),
        "counts": {
            "group_count": len(request.groups),
            "input_item_count": request.expected_item_count,
            "selected_item_count": selected_count,
            "unselected_item_count": request.expected_item_count - selected_count,
            "recovered_verified_count": replay_verified,
            "provider_pending_count": selected_count - replay_verified,
        },
        "provider_calls": 0,
        "credential_reads": 0,
        "writes": 0,
        "privacy_guards": _privacy_guards(),
        "blockers": [],
    }


def _validate_credential_capability_reference(
    value: Mapping[str, Any] | None,
) -> dict[str, str] | None:
    if value is None:
        return None
    expected_keys = {
        "schema_version",
        "capability_id",
        "capability_sha256",
    }
    if type(value) is not dict or set(value) != expected_keys:
        raise RecoveryExecutionBoundaryError(
            "credential_capability_reference_invalid"
        )
    schema = value.get("schema_version")
    capability_id = value.get("capability_id")
    capability_sha256 = value.get("capability_sha256")
    if not (
        type(schema) is str
        and schema == CREDENTIAL_CAPABILITY_REFERENCE_SCHEMA
        and type(capability_id) is str
        and _CAPABILITY_ID_RE.fullmatch(capability_id) is not None
        and type(capability_sha256) is str
        and _SHA256_RE.fullmatch(capability_sha256) is not None
    ):
        raise RecoveryExecutionBoundaryError(
            "credential_capability_reference_invalid"
        )
    return {
        "schema_version": CREDENTIAL_CAPABILITY_REFERENCE_SCHEMA,
        "capability_id": capability_id,
        "capability_sha256": capability_sha256,
    }


def _execute_recovery(
    archive_root: Path | str,
    manifest: Mapping[str, Any],
    *,
    expected_plan_sha256: str,
    reviewed_by: str,
    max_items: int,
    provider: NotionPageProvider,
    credential_broker: CredentialBroker | Callable[[ScopeBinding], object],
    credential_capability_reference: Mapping[str, Any] | None = None,
    offset: int = 0,
    storage: _FilesystemRecoveryStorage | None = None,
    request_pacer: ProviderRequestPacer | Callable[[], None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    jitter: Callable[[], float] = random.random,
    clock: Callable[[], datetime] | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    max_retry_delay_seconds: float = DEFAULT_MAX_RETRY_DELAY_SECONDS,
) -> dict[str, Any]:
    """Execute exactly one approved plan, with resumable item-level commits."""

    try:
        request = parse_manifest(manifest)
        plan = build_plan(request, max_items=max_items, offset=offset)
    except ManifestValidationError as exc:
        return _invalid_execute_result(exc.codes)
    blockers: list[str] = []
    try:
        capability_reference = _validate_credential_capability_reference(
            credential_capability_reference
        )
    except RecoveryExecutionBoundaryError as exc:
        capability_reference = None
        blockers.append(exc.code)
    if expected_plan_sha256 != plan.plan_sha256 or not _SHA256_RE.fullmatch(
        str(expected_plan_sha256)
    ):
        blockers.append("expected_plan_sha256_mismatch")
    if not _is_safe_id(reviewed_by) or _SECRET_SHAPE_RE.search(reviewed_by):
        blockers.append("reviewed_by_invalid")
    if (
        not isinstance(max_attempts, int)
        or isinstance(max_attempts, bool)
        or max_attempts < 1
        or max_attempts > 10
    ):
        blockers.append("max_attempts_invalid")
    if (
        not isinstance(max_retry_delay_seconds, (int, float))
        or isinstance(max_retry_delay_seconds, bool)
        or max_retry_delay_seconds < 0
        or max_retry_delay_seconds > 300
    ):
        blockers.append("max_retry_delay_invalid")
    if blockers:
        return _blocked_execute_result(request, plan, blockers)

    state = storage or _FilesystemRecoveryStorage(archive_root)
    stats = _RunStats()
    outcome_counts = {outcome: 0 for outcome in OUTCOMES}
    replayed_count = 0
    processed_count = 0
    credentials: dict[str, object] = {}
    storage_usable = True
    group_by_id = {group.group_id: group for group in request.groups}
    clock_fn = clock or (lambda: datetime.now(timezone.utc))
    active_pacer = (
        request_pacer
        if request_pacer is not None
        else ArchiveInterprocessRequestPacer(archive_root)
    )

    try:
        with state.plan_lock(
            plan.plan_sha256,
            expected_archive_id=request.archive_id,
        ):
            for item in plan.selected_items:
                state._assert_bound_archive_identity()
                group = group_by_id[item.group_id]
                completed_at = _safe_timestamp(clock_fn)
                repaired = state.repair_verified(
                    request,
                    plan,
                    item,
                    group.scope_binding.revision,
                    completed_at,
                    stats,
                )
                if repaired is not None:
                    outcome_counts["recovered"] += 1
                    replayed_count += 1
                    processed_count += 1
                    continue

                if group.group_id not in credentials:
                    try:
                        stats.credential_resolution_attempts += 1
                        credentials[group.group_id] = _resolve_credential(
                            credential_broker, group.scope_binding
                        )
                        stats.credential_reads += 1
                    except Exception:
                        blockers.append("credential_resolution_failed")
                        break

                credential = credentials[group.group_id]
                outcome, fragments, unauthorized = _retrieve_one_page(
                    provider,
                    item,
                    credential,
                    stats,
                    request_pacer=active_pacer,
                    before_provider_request=state._assert_bound_archive_identity,
                    sleep=sleep,
                    jitter=jitter,
                    max_attempts=max_attempts,
                    max_retry_delay_seconds=float(max_retry_delay_seconds),
                )
                if outcome == "recovered" and fragments is not None:
                    state.commit_recovered(
                        request,
                        plan,
                        item,
                        group.scope_binding.revision,
                        fragments,
                        completed_at,
                        stats,
                    )
                else:
                    state.record_outcome(
                        request,
                        plan,
                        item,
                        outcome,
                        completed_at,
                        stats,
                    )
                outcome_counts[outcome] += 1
                processed_count += 1
                if unauthorized:
                    blockers.append("batch_credential_unauthorized")
                    break
    except RecoveryExecutionBoundaryError as exc:
        blockers.append(exc.code)
    except RecoveryStorageError as exc:
        storage_usable = False
        blockers.append(exc.code)
    except Exception:
        blockers.append("recovery_execution_failed")
    finally:
        if not _close_resolved_credentials(credentials.values()):
            blockers.append("credential_close_failed")
        credentials.clear()

    selected_count = len(plan.selected_items)
    pending_count = selected_count - processed_count
    unselected_count = request.expected_item_count - selected_count
    total_accounted = sum(outcome_counts.values()) + pending_count + unselected_count
    if total_accounted != request.expected_item_count:
        blockers.append("count_invariant_failed")

    non_recovered = sum(
        count for outcome, count in outcome_counts.items() if outcome != "recovered"
    )
    if blockers or pending_count or non_recovered:
        status_class = (
            "partial"
            if processed_count or _run_observed_activity(stats)
            else "blocked"
        )
        ok = False
    elif stats.provider_calls == 0 and stats.objects_created == 0:
        status_class = "no_change"
        ok = True
    else:
        status_class = "written"
        ok = True
    reason_code = {
        "written": "notion_page_recovery_written",
        "no_change": "notion_page_recovery_replayed",
        "partial": "notion_page_recovery_partial",
        "blocked": "notion_page_recovery_blocked",
    }[status_class]

    receipt = {
        "schema": RECEIPT_SCHEMA,
        "request_sha256": plan.request_sha256,
        "plan_sha256": plan.plan_sha256,
        "reviewed_by": reviewed_by,
        "status_class": status_class,
        "reason_code": reason_code,
        "counts": {
            "input_item_count": request.expected_item_count,
            "selected_item_count": selected_count,
            "processed_item_count": processed_count,
            "pending_item_count": pending_count,
            "unselected_item_count": unselected_count,
            "replayed_recovered_count": replayed_count,
            "outcomes": outcome_counts,
            "total_accounted_count": total_accounted,
        },
        "operations": {
            "provider_calls": stats.provider_calls,
            "paced_request_count": stats.paced_request_count,
            "credential_resolution_attempts": stats.credential_resolution_attempts,
            "credential_reads": stats.credential_reads,
            "retry_count": stats.retry_count,
            "sleep_seconds": round(stats.sleep_seconds, 6),
            "objects_created": stats.objects_created,
            "manifest_rows_created": stats.manifest_rows_created,
            "projection_rows_created": stats.projection_rows_created,
            "resume_rows_created": stats.resume_rows_created,
        },
        "privacy_guards": _privacy_guards(),
        "blockers": sorted(set(blockers)),
    }
    if capability_reference is not None:
        receipt["credential_capability_reference"] = capability_reference
    try:
        receipt_created = (
            state.write_receipt(plan.plan_sha256, receipt) if storage_usable else False
        )
    except RecoveryStorageError as exc:
        receipt_created = False
        blockers.append(exc.code)
        receipt["blockers"] = sorted(set(blockers))
        receipt["status_class"] = (
            "partial"
            if processed_count or _run_observed_activity(stats)
            else "blocked"
        )
        ok = False
        status_class = receipt["status_class"]
        reason_code = (
            "notion_page_recovery_partial"
            if processed_count
            else "notion_page_recovery_blocked"
        )
        receipt["reason_code"] = reason_code
    except Exception:
        receipt_created = False
        blockers.append("receipt_write_failed")
        receipt["blockers"] = sorted(set(blockers))
        receipt["status_class"] = (
            "partial"
            if processed_count or _run_observed_activity(stats)
            else "blocked"
        )
        ok = False
        status_class = receipt["status_class"]
        reason_code = (
            "notion_page_recovery_partial"
            if processed_count
            else "notion_page_recovery_blocked"
        )
        receipt["reason_code"] = reason_code

    return {
        "ok": ok,
        "dry_run": False,
        "lifecycle_action": "notion_page_recovery_execute",
        "status_class": status_class,
        "reason_code": reason_code,
        "request_sha256": plan.request_sha256,
        "plan_sha256": plan.plan_sha256,
        "counts": receipt["counts"],
        "operations": receipt["operations"],
        "receipt_created": receipt_created,
        "privacy_guards": _privacy_guards(),
        "blockers": sorted(set(blockers)),
    }


def _retrieve_one_page(
    provider: NotionPageProvider,
    item: RecoveryItem,
    credential: object,
    stats: _RunStats,
    *,
    request_pacer: ProviderRequestPacer | Callable[[], None],
    before_provider_request: Callable[[], None],
    sleep: Callable[[float], None],
    jitter: Callable[[], float],
    max_attempts: int,
    max_retry_delay_seconds: float,
) -> tuple[str, tuple[bytes, ...] | None, bool]:
    def assert_request_authority(endpoint_class: str) -> None:
        before_provider_request()
        _revalidate_credential_authority(credential)
        _authorize_credential_provider_request(credential, endpoint_class)

    metadata = _retry_get(
        lambda: provider.retrieve_page(
            item.page_id, credential, api_version=NOTION_API_VERSION
        ),
        stats,
        request_pacer=request_pacer,
        before_request_pacing=before_provider_request,
        before_provider_request=lambda: assert_request_authority("retrieve_page"),
        sleep=sleep,
        jitter=jitter,
        max_attempts=max_attempts,
        max_retry_delay_seconds=max_retry_delay_seconds,
    )
    status = metadata.response.status
    if status == 401:
        return "retryable_error", None, True
    if status == 403:
        return "forbidden", None, False
    if status == 404:
        return "not_found_or_not_shared", None, False
    if status != 200:
        if status in _RETRYABLE_GET_STATUSES:
            return "retryable_error", None, False
        return "partial", None, False
    payload = metadata.response.payload
    if (
        not isinstance(payload, Mapping)
        or payload.get("object") != "page"
        or payload.get("id") != item.page_id
    ):
        return "partial", None, False
    if payload.get("in_trash") is True:
        return "deleted", None, False
    before_last_edited_time = _last_edited_time(payload)
    if before_last_edited_time is None:
        return "partial", None, False

    fragments: list[bytes] = []
    queue = [item.page_id]
    seen: set[str] = set()
    while queue:
        current_id = queue.pop(0)
        if current_id in seen:
            continue
        if len(seen) >= MAX_UNKNOWN_BLOCK_IDS + 1:
            return "partial", None, False
        seen.add(current_id)
        response = _retry_get(
            lambda current_id=current_id: provider.retrieve_page_as_markdown(
                current_id, credential, api_version=NOTION_API_VERSION
            ),
            stats,
            request_pacer=request_pacer,
            before_request_pacing=before_provider_request,
            before_provider_request=lambda: assert_request_authority(
                "retrieve_page_as_markdown"
            ),
            sleep=sleep,
            jitter=jitter,
            max_attempts=max_attempts,
            max_retry_delay_seconds=max_retry_delay_seconds,
        ).response
        if response.status == 401:
            return "partial", None, True
        if response.status != 200:
            return "partial", None, False
        markdown = _parse_markdown_response(response.payload, expected_id=current_id)
        if markdown is None:
            return "partial", None, False
        raw, truncated, unknown_ids = markdown
        fragments.append(raw)
        unresolved_new = [unknown for unknown in unknown_ids if unknown not in seen]
        if truncated and not unresolved_new:
            return "partial", None, False
        if len(seen) + len(queue) + len(unresolved_new) > MAX_UNKNOWN_BLOCK_IDS + 1:
            return "partial", None, False
        queue.extend(unresolved_new)

    metadata_after = _retry_get(
        lambda: provider.retrieve_page(
            item.page_id, credential, api_version=NOTION_API_VERSION
        ),
        stats,
        request_pacer=request_pacer,
        before_request_pacing=before_provider_request,
        before_provider_request=lambda: assert_request_authority("retrieve_page"),
        sleep=sleep,
        jitter=jitter,
        max_attempts=max_attempts,
        max_retry_delay_seconds=max_retry_delay_seconds,
    ).response
    if metadata_after.status == 401:
        return "partial", None, True
    if metadata_after.status != 200:
        if metadata_after.status in _RETRYABLE_GET_STATUSES:
            return "retryable_error", None, False
        return "partial", None, False
    after_payload = metadata_after.payload
    if (
        not isinstance(after_payload, Mapping)
        or after_payload.get("object") != "page"
        or after_payload.get("id") != item.page_id
        or after_payload.get("in_trash") is True
    ):
        return "partial", None, False
    after_last_edited_time = _last_edited_time(after_payload)
    if after_last_edited_time is None or after_last_edited_time != before_last_edited_time:
        return "retryable_error", None, False
    return "recovered", tuple(fragments), False


def _retry_get(
    operation: Callable[[], ProviderResponse],
    stats: _RunStats,
    *,
    request_pacer: ProviderRequestPacer | Callable[[], None],
    before_request_pacing: Callable[[], None],
    before_provider_request: Callable[[], None],
    sleep: Callable[[float], None],
    jitter: Callable[[], float],
    max_attempts: int,
    max_retry_delay_seconds: float,
) -> _RetryResult:
    last = ProviderResponse(status=599, payload=None, headers=None)
    for attempt in range(1, max_attempts + 1):
        try:
            before_request_pacing()
        except RecoveryStorageError:
            raise
        except Exception:
            raise RecoveryStorageError(_ARCHIVE_IDENTITY_CHANGED) from None
        try:
            _pace_before_request(request_pacer)
        except Exception:
            candidate = ProviderResponse(status=599, payload=None, headers=None)
        else:
            stats.paced_request_count += 1
            try:
                before_provider_request()
            except RecoveryExecutionBoundaryError:
                raise
            except RecoveryStorageError:
                raise
            except Exception:
                raise RecoveryStorageError(_ARCHIVE_IDENTITY_CHANGED) from None
            stats.provider_calls += 1
            try:
                candidate = operation()
                if not isinstance(candidate, ProviderResponse):
                    candidate = ProviderResponse(status=599, payload=None, headers=None)
            except Exception:
                candidate = ProviderResponse(status=599, payload=None, headers=None)
        last = candidate
        if candidate.status not in _RETRYABLE_GET_STATUSES:
            return _RetryResult(candidate, attempt)
        if attempt >= max_attempts:
            return _RetryResult(candidate, attempt)
        retry_after = _retry_after_seconds(candidate.headers)
        if retry_after > max_retry_delay_seconds:
            # Retry-After is a minimum, not a suggestion.  The approved run is
            # also bounded, so it must stop rather than sleep for a shorter and
            # therefore non-compliant interval.
            return _RetryResult(candidate, attempt)
        try:
            jitter_value = float(jitter())
        except Exception:
            jitter_value = 0.0
        jitter_value = min(1.0, max(0.0, jitter_value))
        exponential = min(max_retry_delay_seconds, (2.0 ** (attempt - 1)) + jitter_value)
        delay = min(max_retry_delay_seconds, max(retry_after, exponential))
        sleep(delay)
        stats.retry_count += 1
        stats.sleep_seconds += delay
    return _RetryResult(last, max_attempts)


def _pace_before_request(
    request_pacer: ProviderRequestPacer | Callable[[], None],
) -> None:
    if callable(request_pacer) and not hasattr(request_pacer, "before_request"):
        request_pacer()
        return
    request_pacer.before_request()


def _parse_markdown_response(
    payload: Mapping[str, Any] | None,
    *,
    expected_id: str,
) -> tuple[bytes, bool, tuple[str, ...]] | None:
    if not isinstance(payload, Mapping):
        return None
    if payload.get("object") != "page_markdown" or payload.get("id") != expected_id:
        return None
    markdown = payload.get("markdown")
    truncated = payload.get("truncated")
    unknown_raw = payload.get("unknown_block_ids")
    if not isinstance(markdown, str) or not isinstance(truncated, bool):
        return None
    if not isinstance(unknown_raw, list) or len(unknown_raw) > MAX_UNKNOWN_BLOCK_IDS:
        return None
    unknown: list[str] = []
    seen: set[str] = set()
    for raw in unknown_raw:
        try:
            normalized = str(uuid.UUID(str(raw)))
        except (ValueError, AttributeError, TypeError):
            return None
        if normalized not in seen:
            unknown.append(normalized)
            seen.add(normalized)
    try:
        raw_markdown = markdown.encode("utf-8")
    except UnicodeEncodeError:
        return None
    return raw_markdown, truncated, tuple(unknown)


def _last_edited_time(payload: Mapping[str, Any]) -> str | None:
    value = payload.get("last_edited_time")
    if not isinstance(value, str) or not value or len(value) > 128:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if parsed.tzinfo is not None else None


def _resume_checkpoint_row(
    request: RecoveryRequest,
    plan: RecoveryPlan,
    item: RecoveryItem,
    completed_at: str,
    stored: StoredRecovery,
) -> dict[str, Any]:
    return {
        "schema": RESUME_SCHEMA,
        "request_sha256": plan.request_sha256,
        "plan_sha256": plan.plan_sha256,
        "batch_id": request.batch_id,
        "item_id": item.item_id,
        "group_id": item.group_id,
        "page_id": item.page_id,
        "phase": "objects_stored",
        "outcome": "partial",
        "fragments": [
            {
                "object_id": fragment.object_id,
                "sha256": fragment.sha256,
                "byte_size": fragment.byte_size,
            }
            for fragment in stored.fragments
        ],
        "completed_at": completed_at,
    }


def _resume_terminal_row(
    request: RecoveryRequest,
    plan: RecoveryPlan,
    item: RecoveryItem,
    outcome: str,
    completed_at: str,
    stored: StoredRecovery | None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "schema": RESUME_SCHEMA,
        "request_sha256": plan.request_sha256,
        "plan_sha256": plan.plan_sha256,
        "batch_id": request.batch_id,
        "item_id": item.item_id,
        "group_id": item.group_id,
        "page_id": item.page_id,
        "phase": "terminal",
        "outcome": outcome,
        "completed_at": completed_at,
    }
    if stored is not None:
        row["fragments"] = [
            {
                "object_id": fragment.object_id,
                "sha256": fragment.sha256,
                "byte_size": fragment.byte_size,
            }
            for fragment in stored.fragments
        ]
    return row


def _invalid_plan_result(codes: Sequence[str]) -> dict[str, Any]:
    return {
        "ok": False,
        "dry_run": True,
        "lifecycle_action": "notion_page_recovery_plan",
        "reason_code": "notion_page_recovery_manifest_invalid",
        "request_sha256": None,
        "plan_sha256": None,
        "approved_execution_capabilities": dict(
            APPROVED_EXECUTION_CAPABILITIES
        ),
        "counts": {
            "group_count": 0,
            "input_item_count": 0,
            "selected_item_count": 0,
            "unselected_item_count": 0,
            "recovered_verified_count": 0,
            "provider_pending_count": 0,
        },
        "provider_calls": 0,
        "credential_reads": 0,
        "writes": 0,
        "privacy_guards": _privacy_guards(),
        "blockers": list(sorted(set(codes))),
    }


def _invalid_execute_result(codes: Sequence[str]) -> dict[str, Any]:
    return {
        "ok": False,
        "dry_run": False,
        "lifecycle_action": "notion_page_recovery_execute",
        "status_class": "blocked",
        "reason_code": "notion_page_recovery_manifest_invalid",
        "request_sha256": None,
        "plan_sha256": None,
        "counts": {
            "input_item_count": 0,
            "selected_item_count": 0,
            "processed_item_count": 0,
            "pending_item_count": 0,
            "unselected_item_count": 0,
            "replayed_recovered_count": 0,
            "outcomes": {outcome: 0 for outcome in OUTCOMES},
            "total_accounted_count": 0,
        },
        "operations": _zero_operations(),
        "receipt_created": False,
        "privacy_guards": _privacy_guards(),
        "blockers": list(sorted(set(codes))),
    }


def _blocked_execute_result(
    request: RecoveryRequest,
    plan: RecoveryPlan,
    blockers: Sequence[str],
) -> dict[str, Any]:
    selected = len(plan.selected_items)
    return {
        "ok": False,
        "dry_run": False,
        "lifecycle_action": "notion_page_recovery_execute",
        "status_class": "blocked",
        "reason_code": "notion_page_recovery_approval_blocked",
        "request_sha256": plan.request_sha256,
        "plan_sha256": plan.plan_sha256,
        "counts": {
            "input_item_count": request.expected_item_count,
            "selected_item_count": selected,
            "processed_item_count": 0,
            "pending_item_count": selected,
            "unselected_item_count": request.expected_item_count - selected,
            "replayed_recovered_count": 0,
            "outcomes": {outcome: 0 for outcome in OUTCOMES},
            "total_accounted_count": request.expected_item_count,
        },
        "operations": _zero_operations(),
        "receipt_created": False,
        "privacy_guards": _privacy_guards(),
        "blockers": list(sorted(set(blockers))),
    }


def _zero_operations() -> dict[str, Any]:
    return {
        "provider_calls": 0,
        "paced_request_count": 0,
        "credential_resolution_attempts": 0,
        "credential_reads": 0,
        "retry_count": 0,
        "sleep_seconds": 0.0,
        "objects_created": 0,
        "manifest_rows_created": 0,
        "projection_rows_created": 0,
        "resume_rows_created": 0,
    }


def _run_observed_activity(stats: _RunStats) -> bool:
    return any(
        (
            stats.provider_calls,
            stats.paced_request_count,
            stats.credential_resolution_attempts,
            stats.credential_reads,
            stats.retry_count,
            stats.objects_created,
            stats.manifest_rows_created,
            stats.projection_rows_created,
            stats.resume_rows_created,
        )
    )


def _privacy_guards() -> dict[str, bool]:
    return {
        "token_echoed": False,
        "provider_body_echoed": False,
        "page_title_echoed": False,
        "email_echoed": False,
        "provider_url_echoed": False,
        "raw_cursor_echoed": False,
        "raw_cursor_persisted": False,
        "rate_limiter_clock_echoed": False,
    }


def _check_exact_keys(
    value: Mapping[str, Any],
    expected: set[str],
    label: str,
    errors: list[str],
) -> None:
    keys = set(value.keys())
    if keys - expected:
        errors.append(f"{label}_additional_properties_forbidden")
    if expected - keys:
        errors.append(f"{label}_required_property_missing")


def _safe_id_value(value: Any, label: str, errors: list[str]) -> str:
    if not _is_safe_id(value):
        errors.append(f"{label}_invalid")
        return "invalid"
    return str(value)


def _is_safe_id(value: Any) -> bool:
    return isinstance(value, str) and bool(_SAFE_ID_RE.fullmatch(value))


def _sha256_value(value: Any, label: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        errors.append(f"{label}_invalid")
        return "sha256:" + ("0" * 64)
    return value


def _uuid_value(value: Any, errors: list[str]) -> str:
    if not isinstance(value, str):
        errors.append("page_id_invalid")
        return "00000000-0000-0000-0000-000000000000"
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        errors.append("page_id_invalid")
        return "00000000-0000-0000-0000-000000000000"
    return str(parsed)


def _bounded_int(
    value: Any,
    label: str,
    errors: list[str],
    *,
    minimum: int,
    maximum: int,
) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < minimum
        or value > maximum
    ):
        errors.append(f"{label}_invalid")
        return minimum
    return value


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_id(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _digest_part(value: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise RecoveryStorageError("digest_invalid")
    return value.split(":", 1)[1]


def _safe_timestamp(clock: Callable[[], datetime]) -> str:
    try:
        value = clock()
    except Exception as exc:
        raise RecoveryStorageError("clock_failed") from exc
    if not isinstance(value, datetime):
        raise RecoveryStorageError("clock_invalid")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _resolve_credential(
    broker: CredentialBroker | Callable[[ScopeBinding], object],
    scope: ScopeBinding,
) -> object:
    if callable(broker):
        credential = broker(scope)
    else:
        credential = broker.resolve(scope)
    if credential is None:
        raise RuntimeError("credential_unavailable")
    return credential


def _revalidate_credential_authority(credential: object) -> None:
    revalidate = getattr(credential, "revalidate_authority", None)
    if revalidate is None:
        return
    if not callable(revalidate):
        raise RecoveryExecutionBoundaryError("credential_authority_changed")
    try:
        revalidate()
    except Exception:
        raise RecoveryExecutionBoundaryError("credential_authority_changed") from None


def _authorize_credential_provider_request(
    credential: object,
    endpoint_class: str,
) -> None:
    """Consume one broker capability immediately before a provider attempt.

    Injected provider-neutral test credentials may omit this optional method.
    The production ``_NotionBearerSecret`` always exposes it, and fails closed
    when its receipt-backed broker did not bind a claimed capability.
    """

    authorize = getattr(credential, "authorize_provider_request", None)
    if authorize is None:
        return
    if not callable(authorize):
        raise RecoveryExecutionBoundaryError(
            "credential_capability_authorization_failed"
        )
    try:
        authorize(endpoint_class)
    except Exception:
        raise RecoveryExecutionBoundaryError(
            "credential_capability_authorization_failed"
        ) from None


def _close_resolved_credentials(credentials: Iterable[object]) -> bool:
    """Close each distinct broker-owned credential once without detail echo."""

    closed_ids: set[int] = set()
    ok = True
    for credential in credentials:
        identity = id(credential)
        if identity in closed_ids:
            continue
        closed_ids.add(identity)
        close = getattr(credential, "close", None)
        if not callable(close):
            continue
        try:
            close()
        except Exception:
            ok = False
    return ok


def _retry_after_seconds(headers: Mapping[str, str] | None) -> float:
    if not isinstance(headers, Mapping):
        return 0.0
    raw: Any = None
    for key, value in headers.items():
        if isinstance(key, str) and key.lower() == "retry-after":
            raw = value
            break
    try:
        parsed = float(raw)
    except (TypeError, ValueError):
        return 0.0
    if parsed < 0 or not math.isfinite(parsed):
        return 0.0
    return parsed


def _manifest_authority_projection(row: Mapping[str, Any]) -> Mapping[str, Any]:
    """Project the one canonical content authority for an exact object id.

    Page/request provenance belongs to the projection ledger.  Central object
    identity is reusable across captures only when these content, logical,
    media, size, and location facts are exactly equal.
    """

    return {
        name: row.get(name)
        for name in (
            "object_id",
            "sha256",
            "logical_key",
            "mime",
            "size_bytes",
            "locations",
        )
    }


def _projection_authority_projection(row: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return every projection authority field except the retry-local timestamp."""

    projected = dict(row)
    projected.pop("completed_at", None)
    return projected


def _authority_row_state(
    rows: Sequence[Mapping[str, Any]],
    expected: Mapping[str, Any],
    *,
    predicate: Callable[[Mapping[str, Any]], bool],
    authority_projection: Callable[[Mapping[str, Any]], Mapping[str, Any]],
) -> str:
    """Classify an append-only authority identity without reflecting its values."""

    try:
        matches = [row for row in rows if predicate(row)]
        if not matches:
            return "missing"
        if len(matches) != 1:
            raise RecoveryStorageError("recovery_authority_conflict")
        existing_authority = _canonical_json_bytes(
            dict(authority_projection(matches[0]))
        )
        expected_authority = _canonical_json_bytes(
            dict(authority_projection(expected))
        )
    except RecoveryStorageError:
        raise
    except Exception:
        raise RecoveryStorageError("recovery_authority_conflict") from None
    if not secrets.compare_digest(existing_authority, expected_authority):
        raise RecoveryStorageError("recovery_authority_conflict")
    return "equal"


def _local_manifest_location_is_available(
    row: Mapping[str, Any],
    digest: str,
) -> bool:
    logical_key = f"objects/sha256/{digest[:2]}/{digest}"
    locations = row.get("locations")
    return isinstance(locations, list) and any(
        isinstance(location, Mapping)
        and location.get("provider") == "local"
        and location.get("path") == logical_key
        and location.get("availability") == "available"
        for location in locations
    )


class _DuplicateJsonKeyError(ValueError):
    pass


def _reject_duplicate_json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    decoded: dict[str, Any] = {}
    for key, value in pairs:
        if key in decoded:
            raise _DuplicateJsonKeyError
        decoded[key] = value
    return decoded


def _read_jsonl(
    path: Path,
    *,
    archive_root: Path,
) -> tuple[list[Mapping[str, Any]], bool]:
    try:
        payload = _read_archive_file_bytes(archive_root, path)
    except FileNotFoundError:
        return [], False
    except RecoveryStorageError:
        raise
    except OSError as exc:
        raise RecoveryStorageError("private_state_read_failed") from exc
    rows: list[Mapping[str, Any]] = []
    torn = False
    trailing_line_incomplete = bool(payload) and not payload.endswith(
        (b"\n", b"\r")
    )
    lines = payload.splitlines(keepends=True)
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            decoded = json.loads(
                stripped.decode("utf-8"),
                object_pairs_hook=_reject_duplicate_json_pairs,
            )
        except _DuplicateJsonKeyError:
            raise RecoveryStorageError("private_state_invalid") from None
        except (UnicodeDecodeError, json.JSONDecodeError):
            if index == len(lines) - 1 and trailing_line_incomplete:
                torn = True
                break
            raise RecoveryStorageError("private_state_invalid")
        if not isinstance(decoded, Mapping):
            raise RecoveryStorageError("private_state_invalid")
        rows.append(decoded)
    if trailing_line_incomplete:
        torn = True
    return rows, torn


def _verify_file(
    path: Path,
    expected_digest: str,
    expected_size: int,
    *,
    archive_root: Path,
) -> bool:
    try:
        with _open_archive_read(archive_root, path) as handle:
            opened = os.fstat(handle.fileno())
            if opened.st_size != expected_size:
                return False
            digest = hashlib.sha256()
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        named_after = _validate_archive_destination(
            archive_root, path, allow_missing=False
        )
        if not _pacer_same_identity(opened, named_after):
            return False
        return digest.hexdigest() == expected_digest
    except RecoveryStorageError:
        raise
    except FileNotFoundError:
        return False
    except OSError:
        return False


def _write_all(
    handle: Any,
    payload: bytes,
    *,
    before_write: Callable[[], None] | None = None,
) -> None:
    """Write an exact payload or fail without treating short progress as success."""

    view = memoryview(payload)
    written = 0
    try:
        while written < len(view):
            try:
                if before_write is not None:
                    before_write()
                count = handle.write(view[written:])
            except (RecoveryExecutionBoundaryError, RecoveryStorageError):
                raise
            except Exception:
                raise RecoveryStorageError("durable_write_failed") from None
            if (
                not isinstance(count, int)
                or isinstance(count, bool)
                or count <= 0
                or count > len(view) - written
            ):
                raise RecoveryStorageError("durable_write_failed")
            written += count
    finally:
        view.release()


def _file_matches_exact_payload(
    path: Path,
    expected_payload: bytes,
    *,
    archive_root: Path,
) -> bool:
    expected_size = len(expected_payload)
    with _open_archive_read(archive_root, path) as handle:
        opened = os.fstat(handle.fileno())
        actual_payload = (
            handle.read(expected_size + 1)
            if opened.st_size == expected_size
            else b""
        )
    named_after = _validate_archive_destination(
        archive_root,
        path,
        allow_missing=False,
    )
    if named_after is None or not _pacer_same_identity(opened, named_after):
        raise RecoveryStorageError("archive_path_unsafe")
    if opened.st_size != expected_size or len(actual_payload) != expected_size:
        return False
    expected_digest = hashlib.sha256(expected_payload).digest()
    actual_digest = hashlib.sha256(actual_payload).digest()
    return secrets.compare_digest(
        actual_digest,
        expected_digest,
    ) and secrets.compare_digest(
        actual_payload,
        expected_payload,
    )


def _file_matches_payload_at_offset(
    path: Path,
    offset: int,
    expected_payload: bytes,
    *,
    archive_root: Path,
) -> bool:
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise RecoveryStorageError("durable_write_verification_failed")
    expected_size = offset + len(expected_payload)
    with _open_archive_read(archive_root, path) as handle:
        opened = os.fstat(handle.fileno())
        if opened.st_size != expected_size:
            actual_payload = b""
        else:
            handle.seek(offset)
            actual_payload = handle.read(len(expected_payload) + 1)
    named_after = _validate_archive_destination(
        archive_root,
        path,
        allow_missing=False,
    )
    if named_after is None or not _pacer_same_identity(opened, named_after):
        raise RecoveryStorageError("archive_path_unsafe")
    if opened.st_size != expected_size or len(actual_payload) != len(expected_payload):
        return False
    return secrets.compare_digest(actual_payload, expected_payload)


def _archive_target(
    archive_root: Path,
    path: Path,
) -> tuple[Path, Path]:
    try:
        root = Path(os.path.abspath(os.fspath(archive_root)))
        target = Path(os.path.abspath(os.fspath(path)))
        common = Path(os.path.commonpath((str(root), str(target))))
        if os.path.normcase(str(common)) != os.path.normcase(str(root)):
            raise RecoveryStorageError("archive_path_unsafe")
        target.relative_to(root)
    except RecoveryStorageError:
        raise
    except (TypeError, ValueError, OSError):
        raise RecoveryStorageError("archive_path_unsafe") from None
    return root, target


def _ensure_archive_directory_chain(
    archive_root: Path,
    directory: Path,
    *,
    create: bool,
) -> bool:
    """Validate every archive-relative directory hop without resolving links."""

    root, target = _archive_target(archive_root, directory)
    try:
        root_before = os.lstat(root)
    except FileNotFoundError:
        return False
    except OSError:
        raise RecoveryStorageError("archive_path_unsafe") from None
    if _pacer_path_is_reparse(root_before) or not stat_module.S_ISDIR(
        root_before.st_mode
    ):
        raise RecoveryStorageError("archive_path_unsafe")
    current = root
    relative = target.relative_to(root)
    for component in relative.parts:
        current = current / component
        try:
            information = os.lstat(current)
        except FileNotFoundError:
            if not create:
                return False
            try:
                os.mkdir(current, 0o700)
                information = os.lstat(current)
            except FileExistsError:
                information = os.lstat(current)
            except OSError:
                raise RecoveryStorageError("archive_path_unsafe") from None
        except OSError:
            raise RecoveryStorageError("archive_path_unsafe") from None
        if _pacer_path_is_reparse(information) or not stat_module.S_ISDIR(
            information.st_mode
        ):
            raise RecoveryStorageError("archive_path_unsafe")
    try:
        root_after = os.lstat(root)
    except OSError:
        raise RecoveryStorageError("archive_path_unsafe") from None
    if (
        _pacer_path_is_reparse(root_after)
        or not stat_module.S_ISDIR(root_after.st_mode)
        or not _pacer_same_identity(root_before, root_after)
    ):
        raise RecoveryStorageError("archive_path_unsafe")
    return True


def _validate_archive_destination(
    archive_root: Path,
    path: Path,
    *,
    allow_missing: bool,
) -> os.stat_result | None:
    _root, target = _archive_target(archive_root, path)
    parent_exists = _ensure_archive_directory_chain(
        archive_root, target.parent, create=False
    )
    if not parent_exists:
        if allow_missing:
            return None
        raise FileNotFoundError
    try:
        information = os.lstat(target)
    except FileNotFoundError:
        if allow_missing:
            return None
        raise
    except OSError:
        raise RecoveryStorageError("archive_path_unsafe") from None
    if (
        _pacer_path_is_reparse(information)
        or not stat_module.S_ISREG(information.st_mode)
        or int(getattr(information, "st_nlink", 1)) != 1
    ):
        raise RecoveryStorageError("archive_path_unsafe")
    return information


def _archive_file_flags(base: int) -> int:
    return (
        base
        | int(getattr(os, "O_BINARY", 0))
        | int(getattr(os, "O_NOFOLLOW", 0))
    )


def _validate_open_archive_file(
    archive_root: Path,
    path: Path,
    descriptor: int,
) -> os.stat_result:
    opened = os.fstat(descriptor)
    named = _validate_archive_destination(archive_root, path, allow_missing=False)
    if (
        named is None
        or _pacer_path_is_reparse(opened)
        or not stat_module.S_ISREG(opened.st_mode)
        or int(getattr(opened, "st_nlink", 1)) != 1
        or not _pacer_same_identity(opened, named)
    ):
        raise RecoveryStorageError("archive_path_unsafe")
    return opened


@contextmanager
def _open_archive_exclusive_temp(
    archive_root: Path,
    path: Path,
) -> Iterable[Any]:
    _ensure_archive_directory_chain(archive_root, path.parent, create=True)
    _validate_archive_destination(archive_root, path, allow_missing=True)
    descriptor = -1
    try:
        descriptor = os.open(
            path,
            _archive_file_flags(os.O_WRONLY | os.O_CREAT | os.O_EXCL),
            0o600,
        )
        _validate_open_archive_file(archive_root, path, descriptor)
        handle = os.fdopen(descriptor, "wb", buffering=0)
        descriptor = -1
        try:
            yield handle
        finally:
            handle.close()
    except RecoveryStorageError:
        raise
    except OSError:
        raise RecoveryStorageError("archive_path_unsafe") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


@contextmanager
def _open_archive_append(
    archive_root: Path,
    path: Path,
) -> Iterable[Any]:
    _ensure_archive_directory_chain(archive_root, path.parent, create=True)
    _validate_archive_destination(archive_root, path, allow_missing=True)
    descriptor = -1
    try:
        descriptor = os.open(
            path,
            _archive_file_flags(os.O_WRONLY | os.O_APPEND | os.O_CREAT),
            0o600,
        )
        _validate_open_archive_file(archive_root, path, descriptor)
        handle = os.fdopen(descriptor, "ab", buffering=0)
        descriptor = -1
        try:
            yield handle
        finally:
            handle.close()
    except RecoveryStorageError:
        raise
    except OSError:
        raise RecoveryStorageError("archive_path_unsafe") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


@contextmanager
def _open_archive_read(
    archive_root: Path,
    path: Path,
) -> Iterable[Any]:
    _validate_archive_destination(archive_root, path, allow_missing=False)
    descriptor = -1
    try:
        descriptor = os.open(path, _archive_file_flags(os.O_RDONLY))
        _validate_open_archive_file(archive_root, path, descriptor)
        handle = os.fdopen(descriptor, "rb", buffering=0)
        descriptor = -1
        try:
            yield handle
        finally:
            handle.close()
    except (RecoveryStorageError, FileNotFoundError):
        raise
    except OSError:
        raise RecoveryStorageError("archive_path_unsafe") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _read_recovery_archive_id(archive_root: Path) -> str:
    try:
        payload = _read_archive_file_bytes(
            archive_root,
            archive_root / "archive.yml",
            max_bytes=MAX_ARCHIVE_IDENTITY_BYTES,
        )
        document = yaml.load(
            payload.decode("utf-8-sig"),
            Loader=_UniqueKeySafeLoader,
        )
        if not isinstance(document, Mapping):
            raise ValueError("archive_identity_invalid")
        archive_id = document.get("archive_id")
        if not _is_safe_id(archive_id):
            raise ValueError("archive_identity_invalid")
        return str(archive_id)
    except Exception:
        raise RecoveryStorageError(_ARCHIVE_IDENTITY_CHANGED) from None


def _read_archive_file_bytes(
    archive_root: Path,
    path: Path,
    *,
    max_bytes: int | None = None,
) -> bytes:
    with _open_archive_read(archive_root, path) as handle:
        opened = os.fstat(handle.fileno())
        if max_bytes is not None and (
            opened.st_size < 0 or opened.st_size > max_bytes
        ):
            raise RecoveryStorageError("archive_path_unsafe")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if max_bytes is not None and total > max_bytes:
                raise RecoveryStorageError("archive_path_unsafe")
            chunks.append(chunk)
    named_after = _validate_archive_destination(
        archive_root, path, allow_missing=False
    )
    if named_after is None or not _pacer_same_identity(opened, named_after):
        raise RecoveryStorageError("archive_path_unsafe")
    return b"".join(chunks)


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _pacer_path_is_reparse(information: os.stat_result) -> bool:
    reparse_flag = int(
        getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0x00000400)
    )
    return stat_module.S_ISLNK(information.st_mode) or bool(
        int(getattr(information, "st_file_attributes", 0)) & reparse_flag
    )


def _pacer_same_identity(
    first: os.stat_result,
    second: os.stat_result,
) -> bool:
    return (int(first.st_dev), int(first.st_ino)) == (
        int(second.st_dev),
        int(second.st_ino),
    )


def _require_private_pacer_directory(path: Path) -> os.stat_result:
    information = os.lstat(path)
    if _pacer_path_is_reparse(information) or not stat_module.S_ISDIR(
        information.st_mode
    ):
        raise RuntimeError("provider_pacer_failed")
    return information


def _require_private_pacer_file(path: Path) -> os.stat_result:
    information = os.lstat(path)
    if (
        _pacer_path_is_reparse(information)
        or not stat_module.S_ISREG(information.st_mode)
        or int(getattr(information, "st_nlink", 1)) != 1
    ):
        raise RuntimeError("provider_pacer_failed")
    return information


def _prepare_private_pacer_paths(
    archive_root: Path | str,
) -> tuple[Path, Path, Path]:
    """Create only the fixed private pacing directory, rejecting link hops."""

    try:
        supplied = os.fspath(archive_root)
        if not isinstance(supplied, (str, bytes)) or b"\0" in os.fsencode(supplied):
            raise RuntimeError("provider_pacer_failed")
        root = Path(os.path.abspath(supplied))
        _require_private_pacer_directory(root)
        current = root
        for component in _PACER_RELATIVE_ROOT.parts:
            candidate = current / component
            try:
                os.mkdir(candidate, 0o700)
            except FileExistsError:
                pass
            _require_private_pacer_directory(candidate)
            current = candidate
        # Recheck the archive boundary after creation so a lexical root swap is
        # detected before either the lock or state file is opened.
        _require_private_pacer_directory(root)
    except Exception:
        raise RuntimeError("provider_pacer_failed") from None
    return current, current / _PACER_LOCK_NAME, current / _PACER_STATE_NAME


def _private_pacer_open_flags(base: int) -> int:
    return (
        base
        | int(getattr(os, "O_BINARY", 0))
        | int(getattr(os, "O_NOFOLLOW", 0))
    )


def _open_private_pacer_lock(path: Path):
    """Open one non-reparse, single-link regular lock file by exact name."""

    _require_private_pacer_directory(path.parent)
    flags = _private_pacer_open_flags(os.O_RDWR)
    try:
        descriptor = os.open(path, flags | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        _require_private_pacer_file(path)
        descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        named = _require_private_pacer_file(path)
        if (
            _pacer_path_is_reparse(opened)
            or not stat_module.S_ISREG(opened.st_mode)
            or int(getattr(opened, "st_nlink", 1)) != 1
            or not _pacer_same_identity(opened, named)
        ):
            raise RuntimeError("provider_pacer_failed")
        if opened.st_size == 0:
            os.write(descriptor, b"\0")
            os.fsync(descriptor)
        elif opened.st_size != 1:
            raise RuntimeError("provider_pacer_failed")
        return os.fdopen(descriptor, "r+b", buffering=0)
    except Exception:
        os.close(descriptor)
        raise


@contextmanager
def _exclusive_private_pacer_lock(path: Path) -> Iterable[None]:
    """Hold one OS-visible byte-range/flock lock for the archive pacer."""

    handle = _open_private_pacer_lock(path)
    locked = False
    try:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        locked = True
        opened = os.fstat(handle.fileno())
        named = _require_private_pacer_file(path)
        if (
            not _pacer_same_identity(opened, named)
            or named.st_size != 1
            or _pacer_path_is_reparse(opened)
        ):
            raise RuntimeError("provider_pacer_failed")
        yield
    finally:
        try:
            if locked:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _read_private_pacer_state(path: Path) -> float | None:
    try:
        named_before = _require_private_pacer_file(path)
    except FileNotFoundError:
        return None
    descriptor = -1
    try:
        flags = _private_pacer_open_flags(os.O_RDONLY)
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if (
            _pacer_path_is_reparse(opened)
            or not stat_module.S_ISREG(opened.st_mode)
            or int(getattr(opened, "st_nlink", 1)) != 1
            or not _pacer_same_identity(named_before, opened)
        ):
            raise RuntimeError("provider_pacer_failed")
        payload = os.read(descriptor, _PACER_STATE.size + 1)
        named_after = _require_private_pacer_file(path)
        if not _pacer_same_identity(opened, named_after):
            raise RuntimeError("provider_pacer_failed")
    except Exception:
        raise RuntimeError("provider_pacer_failed") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if len(payload) != _PACER_STATE.size:
        raise RuntimeError("provider_pacer_failed")
    try:
        magic, previous = _PACER_STATE.unpack(payload)
    except struct.error:
        raise RuntimeError("provider_pacer_failed") from None
    if magic != _PACER_STATE_MAGIC or not math.isfinite(previous) or previous < 0:
        raise RuntimeError("provider_pacer_failed")
    return float(previous)


def _write_private_pacer_state(
    private_root: Path,
    state_path: Path,
    value: float,
) -> None:
    if not math.isfinite(value) or value < 0:
        raise RuntimeError("provider_pacer_failed")
    _require_private_pacer_directory(private_root)
    payload = _PACER_STATE.pack(_PACER_STATE_MAGIC, float(value))
    temporary = private_root / f".{_PACER_STATE_NAME}.{secrets.token_hex(8)}.tmp"
    descriptor = -1
    try:
        flags = _private_pacer_open_flags(os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        descriptor = os.open(temporary, flags, 0o600)
        opened = os.fstat(descriptor)
        named = _require_private_pacer_file(temporary)
        if not _pacer_same_identity(opened, named):
            raise RuntimeError("provider_pacer_failed")
        view = memoryview(payload)
        written = 0
        while written < len(view):
            count = os.write(descriptor, view[written:])
            if count <= 0:
                raise RuntimeError("provider_pacer_failed")
            written += count
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        try:
            _require_private_pacer_file(state_path)
        except FileNotFoundError:
            pass
        _require_private_pacer_directory(private_root)
        os.replace(temporary, state_path)
        state_information = _require_private_pacer_file(state_path)
        if state_information.st_size != len(payload):
            raise RuntimeError("provider_pacer_failed")
        _fsync_directory(private_root)
    except Exception:
        raise RuntimeError("provider_pacer_failed") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            # The public caller still receives only provider_pacer_failed.
            pass


def _thread_lock_for(path: Path) -> threading.RLock:
    key = os.path.abspath(os.fspath(path))
    with _THREAD_LOCKS_GUARD:
        lock = _THREAD_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _THREAD_LOCKS[key] = lock
        return lock


@contextmanager
def _exclusive_object_manifest_lock(archive_root: Path) -> Iterable[None]:
    """Share the canonical zero-byte object-manifest coordination lock.

    The central ``files.jsonl`` writer contract predates this recovery lane.
    On Windows it is guarded by ``_PersistentCoordinationLock``; on POSIX it is
    a zero-byte flock file.  The generic recovery lock is intentionally not
    used here because that separate contract writes a one-byte sentinel.
    """

    try:
        from .archive_services import _ObjetCaptureManifestLock

        with _ObjetCaptureManifestLock(archive_root):
            yield
    except RecoveryStorageError:
        raise
    except Exception:
        raise RecoveryStorageError("archive_path_unsafe") from None


def _open_archive_lock_file(archive_root: Path, path: Path):
    _ensure_archive_directory_chain(archive_root, path.parent, create=True)
    _validate_archive_destination(archive_root, path, allow_missing=True)
    descriptor = -1
    try:
        descriptor = os.open(
            path,
            _archive_file_flags(os.O_RDWR | os.O_CREAT),
            0o600,
        )
        opened = _validate_open_archive_file(archive_root, path, descriptor)
        if opened.st_size == 0:
            os.write(descriptor, b"\0")
            os.fsync(descriptor)
        elif opened.st_size != 1:
            raise RecoveryStorageError("archive_path_unsafe")
        handle = os.fdopen(descriptor, "r+b", buffering=0)
        descriptor = -1
        return handle
    except RecoveryStorageError:
        raise
    except OSError:
        raise RecoveryStorageError("archive_path_unsafe") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


@contextmanager
def _exclusive_file_lock(
    path: Path,
    *,
    archive_root: Path,
) -> Iterable[None]:
    thread_lock = _thread_lock_for(path)
    with thread_lock:
        handle = _open_archive_lock_file(archive_root, path)
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            opened = os.fstat(handle.fileno())
            named = _validate_archive_destination(
                archive_root, path, allow_missing=False
            )
            if (
                named is None
                or not _pacer_same_identity(opened, named)
                or named.st_size != 1
                or _pacer_path_is_reparse(opened)
            ):
                raise RecoveryStorageError("archive_path_unsafe")
            try:
                yield
            finally:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except RecoveryStorageError:
            raise
        except OSError as exc:
            raise RecoveryStorageError("plan_lock_failed") from exc
        finally:
            handle.close()
